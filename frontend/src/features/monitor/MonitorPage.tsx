import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import {
  getDemoContext,
  listDemoVideos,
  startAnalysisSession,
  type DemoContext,
  type DemoVideo,
} from "../../shared/api";
import {
  connectAnalysisEvents,
  type AnalysisEvent,
  type AnalysisEventsConnection,
} from "../../shared/ws";
import { ChannelCard } from "./ChannelCard";
import { createInitialMonitorState, monitorReducer } from "./monitorState";
import { SwitchChannelDialog } from "./SwitchChannelDialog";

type TransportFailureSource = "websocket" | "mjpeg" | "protocol";

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function taskForVideo(video: DemoVideo, context: DemoContext): string {
  const scenarioTime = Date.parse(video.scenario_started_at);
  const permit = context.work_permits.find((candidate) => {
    if (candidate.zone_id !== video.zone_id || candidate.status !== "ACTIVE") {
      return false;
    }
    const startsAt = Date.parse(candidate.starts_at);
    const endsAt = Date.parse(candidate.ends_at);
    return (
      Number.isFinite(scenarioTime) &&
      Number.isFinite(startsAt) &&
      Number.isFinite(endsAt) &&
      startsAt <= scenarioTime &&
      scenarioTime <= endsAt
    );
  });
  return permit?.task_code ?? "任务待确认";
}

export function MonitorPage() {
  const [videos, setVideos] = useState<DemoVideo[] | null>(null);
  const [context, setContext] = useState<DemoContext | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [pendingVideo, setPendingVideo] = useState<DemoVideo | null>(null);
  const [startingVideoId, setStartingVideoId] = useState<string | null>(null);
  const [state, dispatch] = useReducer(
    monitorReducer,
    undefined,
    createInitialMonitorState,
  );

  const socketRef = useRef<AnalysisEventsConnection | null>(null);
  const latestSessionIdRef = useRef<string | null>(null);
  const mountedRef = useRef(false);
  const loadControllerRef = useRef<AbortController | null>(null);
  const startInFlightVideoIdRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    loadControllerRef.current?.abort();
    const controller = new AbortController();
    loadControllerRef.current = controller;
    setLoadError(false);
    setVideos(null);
    setContext(null);

    try {
      const [nextVideos, nextContext] = await Promise.all([
        listDemoVideos(controller.signal),
        getDemoContext(controller.signal),
      ]);
      if (!mountedRef.current || controller.signal.aborted) {
        return;
      }
      setVideos(nextVideos);
      setContext(nextContext);
    } catch (error) {
      if (
        mountedRef.current &&
        !controller.signal.aborted &&
        !isAbortError(error)
      ) {
        setLoadError(true);
      }
    } finally {
      if (loadControllerRef.current === controller) {
        loadControllerRef.current = null;
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void load();
    return () => {
      mountedRef.current = false;
      loadControllerRef.current?.abort();
      socketRef.current?.close();
      socketRef.current = null;
      latestSessionIdRef.current = null;
    };
  }, [load]);

  const failSession = useCallback(
    (
      sessionId: string,
      source: TransportFailureSource,
      message: string,
    ) => {
      if (latestSessionIdRef.current !== sessionId) {
        return;
      }
      socketRef.current?.close();
      socketRef.current = null;
      latestSessionIdRef.current = null;
      dispatch({ type: "TRANSPORT_FAILED", sessionId, source, message });
    },
    [],
  );

  const handleEvent = useCallback(
    (sessionId: string, event: AnalysisEvent) => {
      if (
        latestSessionIdRef.current !== sessionId ||
        event.session_id !== sessionId
      ) {
        return;
      }
      dispatch({ type: "ANALYSIS_EVENT", event });
      if (
        event.event_type === "SESSION_FINISHED" ||
        event.event_type === "SESSION_FAILED"
      ) {
        socketRef.current?.close();
        socketRef.current = null;
        latestSessionIdRef.current = null;
      }
    },
    [],
  );

  const begin = useCallback(
    async (video: DemoVideo) => {
      if (startInFlightVideoIdRef.current !== null) {
        return;
      }
      startInFlightVideoIdRef.current = video.video_id;
      setStartingVideoId(video.video_id);

      try {
        const session = await startAnalysisSession(video.video_id);
        if (!mountedRef.current) {
          return;
        }

        socketRef.current?.close();
        socketRef.current = null;
        latestSessionIdRef.current = session.session_id;
        dispatch({ type: "SESSION_STARTED", session });
        socketRef.current = connectAnalysisEvents(session.events_url, {
          onEvent: (event) => handleEvent(session.session_id, event),
          onDisconnect: (event) => {
            if (!event.intentional) {
              failSession(
                session.session_id,
                "websocket",
                "连接失败：后端连接已断开",
              );
            }
          },
          onProtocolError: () =>
            failSession(
              session.session_id,
              "protocol",
              "连接失败：实时事件协议错误",
            ),
        });
      } catch (error) {
        if (mountedRef.current) {
          socketRef.current?.close();
          socketRef.current = null;
          latestSessionIdRef.current = null;
          const detail = error instanceof Error ? `：${error.message}` : "";
          dispatch({
            type: "SESSION_START_FAILED",
            videoId: video.video_id,
            message: `无法启动分析${detail}`,
          });
        }
      } finally {
        if (startInFlightVideoIdRef.current === video.video_id) {
          startInFlightVideoIdRef.current = null;
          if (mountedRef.current) {
            setStartingVideoId(null);
          }
        }
      }
    },
    [failSession, handleEvent],
  );

  const chooseVideo = (video: DemoVideo) => {
    if (startInFlightVideoIdRef.current !== null) {
      return;
    }
    if (
      state.activeSession &&
      state.activeSession.video_id !== video.video_id
    ) {
      setPendingVideo(video);
      return;
    }
    if (!state.activeSession) {
      void begin(video);
    }
  };

  if (loadError) {
    return (
      <section className="page-state" role="alert">
        <p>无法加载监控通道</p>
        <button type="button" onClick={() => void load()} aria-label="重试加载">
          重试加载
        </button>
      </section>
    );
  }

  if (!videos || !context) {
    return (
      <section className="page-state" role="status">
        <span>加载六路监控…</span>
      </section>
    );
  }

  if (videos.length === 0) {
    return <section className="page-state">暂无演示视频</section>;
  }

  const activeVideo = videos.find(
    (video) => video.video_id === state.activeSession?.video_id,
  );
  const retryVideo = videos.find(
    (video) => video.video_id === state.failure?.videoId,
  );

  return (
    <section className="monitor-page" aria-label="监控台">
      <header className="monitor-heading">
        <div>
          <p>实时视频分析</p>
          <h1>六路监控台</h1>
        </div>
        {state.failure ? (
          <div className="monitor-alert" role="alert">
            <span>{state.failure.message}</span>
            {retryVideo && state.failure.retryable !== false ? (
              <button
                type="button"
                onClick={() => void begin(retryVideo)}
                disabled={startingVideoId !== null}
              >
                重新启动分析
              </button>
            ) : null}
          </div>
        ) : null}
      </header>

      <div className="video-wall">
        {videos.map((video) => {
          const active = state.activeSession?.video_id === video.video_id;
          return (
            <ChannelCard
              key={video.video_id}
              video={video}
              configuredTask={taskForVideo(video, context)}
              active={active}
              starting={startingVideoId === video.video_id}
              disabled={startingVideoId !== null}
              streamUrl={active ? state.activeSession?.stream_url : undefined}
              candidateCount={state.candidateCountsByVideo[video.video_id] ?? 0}
              onStart={chooseVideo}
              onStreamError={() => {
                if (active && state.activeSession) {
                  failSession(
                    state.activeSession.session_id,
                    "mjpeg",
                    "连接失败：标注画面连接失败",
                  );
                }
              }}
            />
          );
        })}
      </div>

      <SwitchChannelDialog
        open={pendingVideo !== null}
        currentChannelName={activeVideo?.camera_id ?? ""}
        nextChannelName={pendingVideo?.camera_id ?? ""}
        onCancel={() => setPendingVideo(null)}
        onConfirm={() => {
          const nextVideo = pendingVideo;
          setPendingVideo(null);
          if (nextVideo) {
            void begin(nextVideo);
          }
        }}
      />
    </section>
  );
}
