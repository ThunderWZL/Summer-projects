import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChannelCard } from "./ChannelCard";
import { demoVideos } from "../../test/fixtures";

describe("ChannelCard", () => {
  it("labels the channel, simulated context, preview, and start action", () => {
    const onStart = vi.fn();
    const video = {
      ...demoVideos[0],
      video_id: "video-safe-01",
      camera_name: "安全1切割物料机位",
      zone_name: "安全1切割物料区",
      title: "安全1｜切割物料｜防护齐全",
    };
    render(
      <ChannelCard
        video={video}
        configuredTask="MATERIAL_CUTTING"
        active={false}
        candidateCount={0}
        onStart={onStart}
        onStreamError={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("region", { name: "CAM-01 切割作业机位 A" }),
    ).toBeTruthy();
    expect(screen.getByText("切割作业区 A")).toBeTruthy();
    expect(screen.getByText("物料切割｜防护齐全")).toBeTruthy();
    expect(screen.getByText(/当前作业.*物料切割/)).toBeTruthy();
    expect(screen.queryByText(/安全1|MATERIAL_CUTTING/)).toBeNull();
    expect(screen.getByText("未开始分析")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "开始分析 CAM-01" }));
    expect(onStart).toHaveBeenCalledWith(video);
  });

  it("exposes the active state through text and an accessible annotated stream", () => {
    const onStreamError = vi.fn();
    render(
      <ChannelCard
        video={demoVideos[0]}
        configuredTask="GENERAL_WORK"
        active
        streamUrl="/api/v1/analysis-sessions/analysis-session-01/stream.mjpg"
        candidateCount={3}
        onStart={vi.fn()}
        onStreamError={onStreamError}
      />,
    );

    expect(screen.getByText("正在分析")).toBeTruthy();
    expect(screen.getByText("候选 3")).toBeTruthy();
    const stream = screen.getByRole("img", { name: "CAM-01 实时标注画面" });
    expect(stream.getAttribute("src")).toContain("/stream.mjpg");

    fireEvent.error(stream);
    expect(onStreamError).toHaveBeenCalledOnce();
  });
});
