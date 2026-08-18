import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AnalysisEvent } from "../../shared/ws";
import { MonitorPage } from "./MonitorPage";
import {
  analysisSession,
  demoVideos,
  worksiteConfigurations,
} from "../../test/fixtures";

const apiMocks = vi.hoisted(() => ({
  listDemoVideos: vi.fn(),
  getWorksiteConfigurations: vi.fn(),
  startAnalysisSession: vi.fn(),
  updateCameraWorksite: vi.fn(),
}));

interface CapturedHandlers {
  onEvent(event: AnalysisEvent): void;
  onDisconnect(event: {
    intentional: boolean;
    code: number;
    reason: string;
  }): void;
  onProtocolError(error: Error): void;
}

const wsMocks = vi.hoisted(() => ({
  connections: [] as Array<{
    close: ReturnType<typeof vi.fn>;
    handlers: CapturedHandlers;
  }>,
  connectAnalysisEvents: vi.fn(),
}));

vi.mock("../../shared/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../shared/api")>()),
  listDemoVideos: apiMocks.listDemoVideos,
  getWorksiteConfigurations: apiMocks.getWorksiteConfigurations,
  startAnalysisSession: apiMocks.startAnalysisSession,
  updateCameraWorksite: apiMocks.updateCameraWorksite,
}));

vi.mock("../../shared/ws", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../shared/ws")>()),
  connectAnalysisEvents: wsMocks.connectAnalysisEvents,
}));

beforeEach(() => {
  apiMocks.listDemoVideos.mockReset().mockResolvedValue(demoVideos);
  apiMocks.getWorksiteConfigurations
    .mockReset()
    .mockResolvedValue(worksiteConfigurations);
  apiMocks.startAnalysisSession.mockReset().mockResolvedValue(analysisSession);
  apiMocks.updateCameraWorksite.mockReset();
  wsMocks.connections.length = 0;
  wsMocks.connectAnalysisEvents.mockReset().mockImplementation(
    (_url: string, handlers: CapturedHandlers) => {
      const connection = { close: vi.fn(), handlers };
      wsMocks.connections.push(connection);
      return connection;
    },
  );
});

describe("MonitorPage", () => {
  it("loads its catalog under React StrictMode", async () => {
    render(
      <StrictMode>
        <MonitorPage />
      </StrictMode>,
    );

    expect(await screen.findByText("CAM-06")).toBeTruthy();
  });

  it("shows loading, then renders all six channels", async () => {
    let resolveVideos!: (videos: typeof demoVideos) => void;
    apiMocks.listDemoVideos.mockReturnValue(
      new Promise((resolve) => {
        resolveVideos = resolve;
      }),
    );

    render(<MonitorPage />);
    expect(screen.getByRole("status").textContent).toContain("加载六路监控");

    resolveVideos(demoVideos);
    expect(await screen.findByText("CAM-06")).toBeTruthy();
    expect(screen.getAllByRole("region", { name: /CAM-/ })).toHaveLength(6);
  });

  it("shows an empty state when the backend has no demo videos", async () => {
    apiMocks.listDemoVideos.mockResolvedValue([]);

    render(<MonitorPage />);

    expect(await screen.findByText("暂无演示视频")).toBeTruthy();
  });

  it("shows a load error and retries the REST request", async () => {
    apiMocks.listDemoVideos
      .mockRejectedValueOnce(new Error("backend unavailable"))
      .mockResolvedValueOnce(demoVideos);

    render(<MonitorPage />);
    expect((await screen.findByRole("alert")).textContent).toContain(
      "无法加载监控通道",
    );

    fireEvent.click(screen.getByRole("button", { name: "重试加载" }));
    expect(await screen.findByText("CAM-06")).toBeTruthy();
    expect(apiMocks.listDemoVideos).toHaveBeenCalledTimes(2);
  });

  it("starts the first selected channel and opens its event stream", async () => {
    render(<MonitorPage />);

    fireEvent.click(
      await screen.findByRole("button", { name: "开始分析 CAM-01" }),
    );

    await waitFor(() => {
      expect(apiMocks.startAnalysisSession).toHaveBeenCalledWith("video-01");
      expect(wsMocks.connectAnalysisEvents).toHaveBeenCalledWith(
        analysisSession.events_url,
        expect.any(Object),
      );
    });
    expect(screen.getByText("正在分析")).toBeTruthy();
    expect(
      screen.getByRole("img", { name: "CAM-01 实时标注画面" }),
    ).toBeTruthy();
  });

  it("saves a custom camera rule and immediately updates its Chinese display", async () => {
    apiMocks.updateCameraWorksite.mockResolvedValue({
      camera_id: "CAM-02",
      mode: "CUSTOM",
      preset_id: null,
      name: "临时材料检查区",
      required_ppe: ["helmet", "vest"],
    });
    render(
      <MonitorPage configurationOpen onCloseConfiguration={vi.fn()} />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "配置 CAM-02" }));
    fireEvent.change(screen.getByRole("combobox", { name: "场地方案" }), {
      target: { value: "CUSTOM" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "自定义场地名称" }), {
      target: { value: "临时材料检查区" },
    });
    fireEvent.click(screen.getByRole("checkbox", { name: "需要防护手套" }));
    fireEvent.click(screen.getByRole("button", { name: "保存 CAM-02 配置" }));

    await waitFor(() => {
      expect(apiMocks.updateCameraWorksite).toHaveBeenCalledWith("CAM-02", {
        mode: "CUSTOM",
        name: "临时材料检查区",
        required_ppe: ["helmet", "vest"],
      });
    });
    expect(screen.getByText("当前场地：临时材料检查区")).toBeTruthy();
    expect(screen.getByText("防护要求：安全帽、安全背心")).toBeTruthy();
  });

  it("shows a failed first start and retries the requested channel through REST", async () => {
    apiMocks.startAnalysisSession
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(analysisSession);
    render(<MonitorPage />);

    fireEvent.click(
      await screen.findByRole("button", { name: "开始分析 CAM-01" }),
    );

    expect((await screen.findByRole("alert")).textContent).toContain(
      "无法启动分析",
    );
    fireEvent.click(screen.getByRole("button", { name: "重新启动分析" }));
    await waitFor(() => {
      expect(apiMocks.startAnalysisSession).toHaveBeenCalledTimes(2);
      expect(apiMocks.startAnalysisSession).toHaveBeenLastCalledWith("video-01");
    });
  });

  it("prevents duplicate start requests while a session is being created", async () => {
    let resolveSession!: (session: typeof analysisSession) => void;
    apiMocks.startAnalysisSession.mockReturnValue(
      new Promise((resolve) => {
        resolveSession = resolve;
      }),
    );
    render(<MonitorPage />);
    const start = await screen.findByRole("button", {
      name: "开始分析 CAM-01",
    });

    fireEvent.click(start);
    fireEvent.click(start);

    expect(apiMocks.startAnalysisSession).toHaveBeenCalledTimes(1);
    resolveSession(analysisSession);
    await screen.findByText("正在分析");
  });

  it("cancels or confirms a switch and closes the old socket only on confirm", async () => {
    const nextSession = {
      ...analysisSession,
      session_id: "analysis-session-02",
      video_id: "video-02",
      stream_url:
        "/api/v1/analysis-sessions/analysis-session-02/stream.mjpg",
      events_url: "/ws/v1/analysis-sessions/analysis-session-02/events",
    };
    apiMocks.startAnalysisSession
      .mockResolvedValueOnce(analysisSession)
      .mockResolvedValueOnce(nextSession);
    render(<MonitorPage />);

    fireEvent.click(
      await screen.findByRole("button", { name: "开始分析 CAM-01" }),
    );
    await screen.findByText("正在分析");
    fireEvent.click(screen.getByRole("button", { name: "开始分析 CAM-02" }));
    expect((await screen.findByRole("dialog")).textContent).toContain(
      "旧会话将停止，但已发现事件会保留",
    );

    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(apiMocks.startAnalysisSession).toHaveBeenCalledTimes(1);
    expect(wsMocks.connections[0].close).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "开始分析 CAM-02" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "确认切换至 CAM-02" }),
    );
    await waitFor(() => {
      expect(apiMocks.startAnalysisSession).toHaveBeenLastCalledWith("video-02");
      expect(wsMocks.connections[0].close).toHaveBeenCalledOnce();
    });
    expect(screen.getByRole("img", { name: "CAM-02 实时标注画面" })).toBeTruthy();
  });

  it("shows an explicit failure on abnormal WebSocket close and restarts via REST", async () => {
    const restarted = {
      ...analysisSession,
      session_id: "analysis-session-retry",
      stream_url:
        "/api/v1/analysis-sessions/analysis-session-retry/stream.mjpg",
      events_url: "/ws/v1/analysis-sessions/analysis-session-retry/events",
    };
    apiMocks.startAnalysisSession
      .mockResolvedValueOnce(analysisSession)
      .mockResolvedValueOnce(restarted);
    render(<MonitorPage />);
    fireEvent.click(
      await screen.findByRole("button", { name: "开始分析 CAM-01" }),
    );
    await waitFor(() => expect(wsMocks.connections).toHaveLength(1));

    act(() => {
      wsMocks.connections[0].handlers.onDisconnect({
        intentional: false,
        code: 1006,
        reason: "",
      });
    });

    expect(screen.getByRole("alert").textContent).toContain("后端连接已断开");
    expect(screen.queryByText("正在分析")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "重新启动分析" }));
    await waitFor(() => {
      expect(apiMocks.startAnalysisSession).toHaveBeenCalledTimes(2);
      expect(apiMocks.startAnalysisSession).toHaveBeenLastCalledWith("video-01");
    });
  });

  it("clears the running state when the MJPEG image fails", async () => {
    render(<MonitorPage />);
    fireEvent.click(
      await screen.findByRole("button", { name: "开始分析 CAM-01" }),
    );
    const stream = await screen.findByRole("img", {
      name: "CAM-01 实时标注画面",
    });

    fireEvent.error(stream);

    expect(screen.getByRole("alert").textContent).toContain("标注画面连接失败");
    expect(screen.queryByText("正在分析")).toBeNull();
    expect(wsMocks.connections[0].close).toHaveBeenCalledOnce();
  });

  it("closes the event stream when the backend finishes the session", async () => {
    render(<MonitorPage />);
    fireEvent.click(
      await screen.findByRole("button", { name: "开始分析 CAM-01" }),
    );
    await waitFor(() => expect(wsMocks.connections).toHaveLength(1));

    act(() => {
      wsMocks.connections[0].handlers.onEvent({
        event_id: "event-finished",
        sequence: 1,
        event_type: "SESSION_FINISHED",
        session_id: analysisSession.session_id,
        occurred_at: "2026-08-07T09:10:00+08:00",
        case_id: null,
        playback_ms: 600_000,
        payload: { candidate_count: 1, case_count: 1 },
      });
    });

    expect(wsMocks.connections[0].close).toHaveBeenCalledOnce();
    expect(screen.queryByText("正在分析")).toBeNull();
  });
});
