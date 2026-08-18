import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { WorksiteConfigurations } from "../../shared/api";
import { demoVideos } from "../../test/fixtures";
import { WorksiteConfigurationDialog } from "./WorksiteConfigurationDialog";

const configurations: WorksiteConfigurations = {
  presets: [
    {
      preset_id: "MATERIAL_CUTTING",
      name: "物料切割",
      required_ppe: ["helmet", "gloves", "vest"],
    },
    {
      preset_id: "CLIMBING_WORK",
      name: "攀爬作业",
      required_ppe: ["helmet", "gloves", "vest"],
    },
  ],
  cameras: demoVideos.map((video) => ({
    camera_id: video.camera_id,
    mode: "PRESET" as const,
    preset_id: "MATERIAL_CUTTING",
    name: "物料切割",
    required_ppe: ["helmet", "gloves", "vest"],
  })),
};

describe("WorksiteConfigurationDialog", () => {
  it("configures any camera with a custom name and three Chinese PPE choices", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <WorksiteConfigurationDialog
        open
        videos={demoVideos}
        configurations={configurations}
        disabled={false}
        onClose={vi.fn()}
        onSave={onSave}
      />,
    );

    expect(
      screen.getByRole("dialog", { name: "监控场地配置" }),
    ).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /配置 CAM-/ })).toHaveLength(6);
    expect(screen.queryByText("MATERIAL_CUTTING")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "配置 CAM-02" }));
    fireEvent.change(screen.getByRole("combobox", { name: "场地方案" }), {
      target: { value: "CUSTOM" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "自定义场地名称" }), {
      target: { value: "临时材料检查区" },
    });
    fireEvent.click(screen.getByRole("checkbox", { name: "需要防护手套" }));
    fireEvent.click(screen.getByRole("button", { name: "保存 CAM-02 配置" }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith("CAM-02", {
        mode: "CUSTOM",
        name: "临时材料检查区",
        required_ppe: ["helmet", "vest"],
      });
    });
  });

  it("prevents configuration changes while a channel is being analyzed", () => {
    render(
      <WorksiteConfigurationDialog
        open
        videos={demoVideos}
        configurations={configurations}
        disabled
        onClose={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByRole("status").textContent).toContain(
      "分析结束后才能修改场地配置",
    );
    expect(
      (screen.getByRole("button", {
        name: "保存 CAM-01 配置",
      }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });
});
