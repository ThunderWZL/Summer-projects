import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { demoContext } from "../../test/fixtures";
import type { CaseDetailResponse, CaseStatus, PpeType } from "../cases/types";
import { CaseActionPanel } from "./CaseActionPanel";

const officer = demoContext.users.find((user) => user.actor_id === "officer-01")!;
const reviewer = demoContext.users.find((user) => user.actor_id === "reviewer-01")!;

function makeDetail(
  status: CaseStatus,
  ppeType: PpeType,
  requiredPpe: PpeType[],
): CaseDetailResponse {
  return {
    snapshot: {
      case_id: "case-action",
      session_id: "session-action",
      camera_id: ppeType === "gloves" ? "CAM-03" : "CAM-02",
      person_track_id: "track-action",
      ppe_type: ppeType,
      status,
      version: status === "NEEDS_HUMAN_FACTS" ? 4 : 7,
      candidate: {
        candidate_id: "candidate-action",
        session_id: "session-action",
        camera_id: "CAM-03",
        person_track_id: "track-action",
        ppe_type: ppeType,
        evidence_kind: "MISSING_POSITIVE_ASSOCIATION",
        confidence: 0.91,
        model_name: "fixture-yolo",
        model_version: null,
        weights_sha256: "a".repeat(64),
        aggregation_method: "fixture_three_frame_window",
        aggregation_parameters: {},
        occurred_at: "2026-08-07T10:00:00+08:00",
        first_seen_ms: 1000,
        last_seen_ms: 2000,
        frames: [],
      },
      vlm_review: null,
      investigation: {
        facts: {}, conflicts: [], missing_fields: [], applicable_task: "TEST_TASK",
        hazards: [], required_ppe: requiredPpe, recommendation: "review",
        rectification_recommendation: null, citations: [], tool_trace: [],
      },
      human_facts: {},
      rectification_responsible_party_id: null,
      rectification_due_at: null,
      rectification_evidence: [],
      rectification_description: null,
      recheck_conclusion: null,
      created_at: "2026-08-07T10:00:00+08:00",
      updated_at: "2026-08-07T10:03:00+08:00",
      transitions: [],
    },
    camera_name: "测试机位",
    zone_id: "zone-01",
    zone_name: "测试区",
    zone_type: "DEMO",
    video_id: "video-01",
    video_title: "测试视频",
    responsible_party_name: null,
    responsible_party_kind: null,
    citations: [],
    human_submissions: [],
    timeline: [],
  };
}

describe("CaseActionPanel", () => {
  it("lets the CAM02 officer submit site_note as structured facts", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <CaseActionPanel
        detail={makeDetail("NEEDS_HUMAN_FACTS", "helmet", ["helmet"])}
        actor={officer}
        context={demoContext}
        submitting={false}
        onSubmit={onSubmit}
      />,
    );
    fireEvent.change(screen.getByLabelText("现场补充说明"), {
      target: { value: "切割作业正在进行" },
    });
    fireEvent.change(screen.getByLabelText("操作理由"), {
      target: { value: "现场核验完成" },
    });
    fireEvent.click(screen.getByRole("button", { name: "提交事实并重新调查" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({
      command_type: "SUBMIT_FACTS",
      actor_id: "officer-01",
      expected_version: 4,
      reason: "现场核验完成",
      facts: { site_note: "切割作业正在进行" },
    }));
  });

  it("allows the CAM03 reviewer to choose approval", () => {
    render(
      <CaseActionPanel
        detail={makeDetail("PENDING_REVIEW", "gloves", ["gloves"])}
        actor={reviewer}
        context={demoContext}
        submitting={false}
        onSubmit={vi.fn()}
      />,
    );

    expect((screen.getByRole("button", { name: "批准整改" }) as HTMLButtonElement).disabled).toBe(false);
    expect(screen.getByText("整改责任主体")).toBeTruthy();
  });

  it("disables CAM04 approval while retaining only return or rejection decisions", () => {
    render(
      <CaseActionPanel
        detail={makeDetail("PENDING_REVIEW", "gloves", ["helmet"])}
        actor={reviewer}
        context={demoContext}
        submitting={false}
        onSubmit={vi.fn()}
      />,
    );

    expect((screen.getByRole("button", { name: "批准整改" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "退回调查" }) as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByRole("button", { name: "驳回事件" }) as HTMLButtonElement).disabled).toBe(false);
    expect(screen.getByText(/不能批准整改/)).toBeTruthy();
  });

  it("does not expose privileged buttons to a role or state mismatch", () => {
    render(
      <CaseActionPanel
        detail={makeDetail("PENDING_REVIEW", "gloves", ["gloves"])}
        actor={officer}
        context={demoContext}
        submitting={false}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByText("当前没有可执行操作")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "批准整改" })).toBeNull();
    expect(screen.queryByRole("button", { name: "驳回事件" })).toBeNull();
  });
});
