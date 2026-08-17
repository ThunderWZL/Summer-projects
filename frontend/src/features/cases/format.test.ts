import { describe, expect, it } from "vitest";

import {
  formatCameraName,
  formatCaseReference,
  formatFieldLabel,
  formatInvestigationItem,
  formatInvestigationValue,
  formatModelLabel,
  formatSceneTitle,
  formatTaskLabel,
  formatToolLabel,
  formatVlmVerdict,
  formatZoneName,
} from "./format";

describe("user-facing domain labels", () => {
  it("translates task, field, and investigation codes", () => {
    expect(formatTaskLabel("MATERIAL_CUTTING")).toBe("物料切割");
    expect(formatFieldLabel("task_code")).toBe("作业类型");
    expect(formatInvestigationValue("task_source", "active_work_permit")).toBe("有效作业许可");
    expect(formatInvestigationItem("human_task_conflicts_with_active_permit")).toBe("现场填写的作业与有效许可不一致");
    expect(formatToolLabel("search_authoritative_requirements")).toBe("检索安全规范依据");
  });

  it("replaces demo file-derived scene names", () => {
    expect(formatCameraName("CAM-02", "无背心2切割物料机位")).toBe("切割作业机位 B");
    expect(formatZoneName("zone-05", "无头盔无手套无背心组装区")).toBe("木料组装区");
    expect(formatSceneTitle("video-no-ppe", "无头盔无手套无背心｜组装木料")).toBe("木料组装｜三类防护均缺失");
  });

  it("presents model results without raw provider values", () => {
    expect(formatVlmVerdict("CONFIRMED")).toBe("确认违规");
    expect(formatModelLabel("openai_compat", "qwen3.6-35b-a3b")).toBe("通义千问多模态复核");
  });

  it("shortens internal case identifiers for display", () => {
    expect(formatCaseReference("case-candidate-d99c68db-8dbe-5dfd-a15e-bfeae61eae6a")).toBe("事件 D99C68DB");
  });
});
