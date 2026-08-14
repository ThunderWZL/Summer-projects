import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SwitchChannelDialog } from "./SwitchChannelDialog";

describe("SwitchChannelDialog", () => {
  it("describes what is stopped and retained, then supports cancel and confirm", () => {
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    render(
      <SwitchChannelDialog
        open
        currentChannelName="CAM-01"
        nextChannelName="CAM-02"
        onCancel={onCancel}
        onConfirm={onConfirm}
      />,
    );

    expect(screen.getByRole("dialog", { name: "切换分析通道" })).toBeTruthy();
    expect(screen.getByText(/CAM-01.*停止/)).toBeTruthy();
    expect(screen.getByText(/已发现事件会保留/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    fireEvent.click(screen.getByRole("button", { name: "确认切换至 CAM-02" }));
    expect(onCancel).toHaveBeenCalledOnce();
    expect(onConfirm).toHaveBeenCalledOnce();
  });
});
