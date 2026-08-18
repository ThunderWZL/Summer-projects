import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  getWorksiteConfigurations,
  getDemoContext,
  listDemoVideos,
  startAnalysisSession,
  updateCameraWorksite,
} from "./api";
import { analysisSession, demoContext, demoVideos } from "../test/fixtures";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("monitor REST client", () => {
  it("loads the frozen demo video and context responses", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(demoVideos))
      .mockResolvedValueOnce(jsonResponse(demoContext));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listDemoVideos()).resolves.toEqual(demoVideos);
    await expect(getDemoContext()).resolves.toEqual(demoContext);
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/demo/videos",
      "/api/v1/demo/context",
    ]);
  });

  it("starts analysis by sending only video_id", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(analysisSession, { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(startAnalysisSession("video-01")).resolves.toEqual(
      analysisSession,
    );
    const [, init] = fetchMock.mock.calls[0];
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/analysis-sessions");
    expect(init).toMatchObject({
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    expect(JSON.parse(String(init?.body))).toEqual({ video_id: "video-01" });
  });

  it("loads and updates user-facing worksite configurations", async () => {
    const configurations = {
      presets: [
        {
          preset_id: "MATERIAL_CUTTING",
          name: "物料切割",
          required_ppe: ["helmet", "gloves", "vest"],
        },
      ],
      cameras: [
        {
          camera_id: "CAM-01",
          mode: "PRESET",
          preset_id: "MATERIAL_CUTTING",
          name: "物料切割",
          required_ppe: ["helmet", "gloves", "vest"],
        },
      ],
    };
    const updated = {
      camera_id: "CAM-01",
      mode: "CUSTOM",
      preset_id: null,
      name: "临时检修区",
      required_ppe: ["helmet", "vest"],
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(configurations))
      .mockResolvedValueOnce(jsonResponse(updated));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getWorksiteConfigurations()).resolves.toEqual(configurations);
    await expect(
      updateCameraWorksite("CAM-01", {
        mode: "CUSTOM",
        name: "临时检修区",
        required_ppe: ["helmet", "vest"],
      }),
    ).resolves.toEqual(updated);
    expect(fetchMock.mock.calls[1][0]).toBe(
      "/api/v1/demo/worksite-configurations/CAM-01",
    );
    expect(fetchMock.mock.calls[1][1]).toMatchObject({
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
    });
  });

  it("maps every JSON failure through the frozen ErrorResponse", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        jsonResponse(
          {
            code: "ANALYSIS_VIDEO_NOT_FOUND",
            message: "analysis video video-99 was not found",
            current_version: null,
          },
          { status: 404 },
        ),
      ),
    );

    const error = await startAnalysisSession("video-99").catch(
      (reason: unknown) => reason,
    );
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      name: "ApiError",
      code: "ANALYSIS_VIDEO_NOT_FOUND",
      message: "analysis video video-99 was not found",
      currentVersion: null,
    });
  });

  it("turns a transport failure into an explicit retryable client error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockRejectedValue(new TypeError("Failed to fetch")),
    );

    const error = await listDemoVideos().catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      code: "NETWORK_ERROR",
      message: "无法连接后端服务",
      currentVersion: null,
    });
  });
});

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}
