import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChannelCard } from "./ChannelCard";
import { demoVideos } from "../../test/fixtures";

describe("ChannelCard", () => {
  it("keeps the channel preview playing before analysis starts", () => {
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
        worksiteConfiguration={{
          camera_id: "CAM-01",
          mode: "PRESET",
          preset_id: "MATERIAL_CUTTING",
          name: "物料切割",
          required_ppe: ["helmet", "gloves", "vest"],
        }}
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
    expect(screen.getByText(/当前场地.*物料切割/)).toBeTruthy();
    expect(
      screen.getByText(/防护要求.*安全帽.*防护手套.*安全背心/),
    ).toBeTruthy();
    expect(screen.queryByText(/安全1|MATERIAL_CUTTING/)).toBeNull();
    expect(screen.getByText("实时播放")).toBeTruthy();
    const preview = screen.getByLabelText("CAM-01 实时画面");
    expect(preview).toBeInstanceOf(HTMLVideoElement);
    expect((preview as HTMLVideoElement).autoplay).toBe(true);
    expect((preview as HTMLVideoElement).loop).toBe(true);
    expect((preview as HTMLVideoElement).muted).toBe(true);
    expect((preview as HTMLVideoElement).playsInline).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "开始分析 CAM-01" }));
    expect(onStart).toHaveBeenCalledWith(video);
  });

  it("exposes the active state through text and an accessible annotated stream", () => {
    const onStreamError = vi.fn();
    render(
      <ChannelCard
        video={demoVideos[0]}
        worksiteConfiguration={{
          camera_id: "CAM-01",
          mode: "CUSTOM",
          preset_id: null,
          name: "临时检查区",
          required_ppe: ["helmet", "vest"],
        }}
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
