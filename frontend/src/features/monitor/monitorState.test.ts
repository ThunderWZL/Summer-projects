import { describe, expect, it } from "vitest";

import {
  createInitialMonitorState,
  monitorReducer,
} from "./monitorState";
import {
  analysisSession,
  candidateEvent,
  progressEvent,
} from "../../test/fixtures";

describe("monitor state", () => {
  it("keeps exactly one active analysis session", () => {
    const first = monitorReducer(createInitialMonitorState(), {
      type: "SESSION_STARTED",
      session: analysisSession,
    });
    const secondSession = {
      ...analysisSession,
      session_id: "analysis-session-02",
      video_id: "video-02",
    };

    const second = monitorReducer(first, {
      type: "SESSION_STARTED",
      session: secondSession,
    });

    expect(second.activeSession).toEqual(secondSession);
    expect(second.candidateCount).toBe(0);
    expect(second.caseCount).toBe(0);
  });

  it("treats CANDIDATE_CREATED as a reminder without inventing a count", () => {
    const running = monitorReducer(createInitialMonitorState(), {
      type: "SESSION_STARTED",
      session: analysisSession,
    });
    const withCount = monitorReducer(running, {
      type: "ANALYSIS_EVENT",
      event: progressEvent(1, 4),
    });

    const reminded = monitorReducer(withCount, {
      type: "ANALYSIS_EVENT",
      event: candidateEvent(2),
    });

    expect(reminded.candidateCount).toBe(4);
    expect(reminded.lastCandidate).toMatchObject({
      candidate_id: "candidate-01",
      ppe_type: "helmet",
    });
  });

  it("uses backend counts from SESSION_PROGRESS and SESSION_FINISHED", () => {
    const running = monitorReducer(createInitialMonitorState(), {
      type: "SESSION_STARTED",
      session: analysisSession,
    });
    const progressed = monitorReducer(running, {
      type: "ANALYSIS_EVENT",
      event: progressEvent(1, 7),
    });
    const finished = monitorReducer(progressed, {
      type: "ANALYSIS_EVENT",
      event: {
        event_id: "event-02",
        sequence: 2,
        event_type: "SESSION_FINISHED",
        session_id: analysisSession.session_id,
        occurred_at: "2026-08-07T09:10:00+08:00",
        case_id: null,
        playback_ms: 600_000,
        payload: { candidate_count: 9, case_count: 8 },
      },
    });

    expect(progressed).toMatchObject({ candidateCount: 7, caseCount: 7 });
    expect(finished).toMatchObject({
      activeSession: null,
      candidateCount: 9,
      caseCount: 8,
    });
  });

  it.each(["websocket", "mjpeg"] as const)(
    "clears the running state after a %s failure",
    (source) => {
      const running = monitorReducer(createInitialMonitorState(), {
        type: "SESSION_STARTED",
        session: analysisSession,
      });

      const failed = monitorReducer(running, {
        type: "TRANSPORT_FAILED",
        sessionId: analysisSession.session_id,
        source,
        message: "后端连接已断开",
      });

      expect(failed.activeSession).toBeNull();
      expect(failed.failure).toMatchObject({
        source,
        message: "后端连接已断开",
        videoId: "video-01",
      });
    },
  );

  it("records a failed initial REST start against the requested video", () => {
    const failed = monitorReducer(createInitialMonitorState(), {
      type: "SESSION_START_FAILED",
      videoId: "video-01",
      message: "无法启动分析",
    });

    expect(failed.activeSession).toBeNull();
    expect(failed.failure).toMatchObject({
      source: "backend",
      message: "无法启动分析",
      videoId: "video-01",
      retryable: true,
    });
  });

  it("clears the running state when the backend sends SESSION_FAILED", () => {
    const running = monitorReducer(createInitialMonitorState(), {
      type: "SESSION_STARTED",
      session: analysisSession,
    });

    const failed = monitorReducer(running, {
      type: "ANALYSIS_EVENT",
      event: {
        event_id: "event-failed",
        sequence: 1,
        event_type: "SESSION_FAILED",
        session_id: analysisSession.session_id,
        occurred_at: "2026-08-07T09:00:03+08:00",
        case_id: null,
        playback_ms: 3_000,
        payload: {
          error_code: "VLM_PROCESSING_FAILED",
          message: "模型服务不可用",
          retryable: true,
        },
      },
    });

    expect(failed.activeSession).toBeNull();
    expect(failed.failure).toMatchObject({
      source: "backend",
      message: "模型服务不可用",
      retryable: true,
    });
  });

  it("ignores late events from a replaced session", () => {
    const current = monitorReducer(createInitialMonitorState(), {
      type: "SESSION_STARTED",
      session: {
        ...analysisSession,
        session_id: "analysis-session-02",
        video_id: "video-02",
      },
    });

    const unchanged = monitorReducer(current, {
      type: "ANALYSIS_EVENT",
      event: progressEvent(99, 99, "analysis-session-01"),
    });

    expect(unchanged).toEqual(current);
  });
});
