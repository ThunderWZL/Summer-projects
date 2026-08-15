import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChannelCard } from "./ChannelCard";
import { demoVideos } from "../../test/fixtures";

describe("ChannelCard", () => {
  it("labels the channel, simulated context, preview, and start action", () => {
    const onStart = vi.fn();
    render(
      <ChannelCard
        video={demoVideos[0]}
        configuredTask="GENERAL_WORK"
        active={false}
        candidateCount={0}
        onStart={onStart}
        onStreamError={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("region", { name: "CAM-01 测试区 01 机位" }),
    ).toBeTruthy();
    expect(screen.getByText("测试区 01")).toBeTruthy();
    expect(screen.getByText(/当前配置作业.*GENERAL_WORK/)).toBeTruthy();
    expect(screen.getByText("未开始分析")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "开始分析 CAM-01" }));
    expect(onStart).toHaveBeenCalledWith(demoVideos[0]);
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
