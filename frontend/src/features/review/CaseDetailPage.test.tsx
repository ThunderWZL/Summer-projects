import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { demoContext } from "../../test/fixtures";
import type { CaseDetailResponse } from "../cases/types";
import { fetchCaseDetail } from "../cases/api";
import { CaseDetailPage } from "./CaseDetailPage";

vi.mock("../cases/api", () => ({
  CaseApiError: class CaseApiError extends Error {
    code = "REQUEST_FAILED";
  },
  fetchCaseDetail: vi.fn(),
  submitCaseCommand: vi.fn(),
}));

const detail: CaseDetailResponse = {
  snapshot: {
    case_id: "case-candidate-d99c68db-8dbe-5dfd-a15e-bfeae61eae6a",
    session_id: "analysis-session-01",
    camera_id: "CAM-05",
    person_track_id: "2",
    ppe_type: "gloves",
    status: "INVESTIGATING",
    version: 3,
    candidate: {
      candidate_id: "candidate-01",
      session_id: "analysis-session-01",
      camera_id: "CAM-05",
      person_track_id: "2",
      ppe_type: "gloves",
      evidence_kind: "MISSING_POSITIVE_ASSOCIATION",
      confidence: 0.82,
      model_name: "yolo11n-ppe",
      model_version: "w02",
      weights_sha256: "a".repeat(64),
      aggregation_method: "consecutive-evaluable-observations-v1",
      aggregation_parameters: {},
      occurred_at: "2026-08-07T09:00:02+08:00",
      first_seen_ms: 1767,
      last_seen_ms: 2133,
      frames: [],
    },
    vlm_review: {
      candidate_id: "candidate-01",
      verdict: "CONFIRMED",
      person_track_id: "2",
      ppe_type: "gloves",
      association: "MATCHED",
      body_part_visible: true,
      persistent: true,
      poster_or_reflection: false,
      evidence_sufficient: true,
      evidence_timestamps_ms: [1767, 2000, 2133],
      reason: "人员双手裸露且未佩戴手套。",
      model_name: "qwen3.6-35b-a3b",
      model_provider: "openai_compat",
      model_parameters: {},
      reviewed_at: "2026-08-07T09:00:03+08:00",
    },
    investigation: {
      facts: {
        zone_id: "zone-05",
        zone_name: "无防护组装木料区",
        zone_type: "CARPENTRY",
        task_code: "TIMBER_ASSEMBLY",
        task_source: "active_work_permit",
      },
      conflicts: ["human_task_conflicts_with_active_permit"],
      missing_fields: ["active_work_permit"],
      applicable_task: "TIMBER_ASSEMBLY",
      hazards: ["木料碰撞", "手部伤害"],
      required_ppe: ["helmet", "gloves", "vest"],
      recommendation: "立即补充防护手套。",
      rectification_recommendation: {
        responsible_party_id: "team-carpentry-02",
        due_at: "2026-08-07T10:30:00+08:00",
        reason: "完成手部防护整改。",
      },
      citations: [],
      tool_trace: ["search_authoritative_requirements"],
    },
    human_facts: {},
    rectification_responsible_party_id: null,
    rectification_due_at: null,
    rectification_evidence: [],
    rectification_description: null,
    recheck_conclusion: null,
    created_at: "2026-08-07T09:00:02+08:00",
    updated_at: "2026-08-07T09:00:03+08:00",
    transitions: [],
  },
  camera_name: "无防护组装木料机位",
  zone_id: "zone-05",
  zone_name: "无防护组装木料区",
  zone_type: "CARPENTRY",
  video_id: "video-no-ppe",
  video_title: "无头盔无手套无背心｜组装木料",
  responsible_party_name: null,
  responsible_party_kind: null,
  citations: [],
  human_submissions: [],
  timeline: [{
    timeline_item_id: "timeline-01",
    source: "AGENT",
    action: "INVESTIGATING",
    from_status: "VLM_REVIEWED",
    to_status: "INVESTIGATING",
    actor_id: null,
    actor_name: null,
    actor_role: null,
    reason: null,
    occurred_at: "2026-08-07T09:00:03+08:00",
  }],
};

describe("CaseDetailPage display copy", () => {
  beforeEach(() => {
    vi.mocked(fetchCaseDetail).mockResolvedValue(detail);
  });

  it("shows readable Chinese labels instead of backend codes and file-derived names", async () => {
    const context = {
      ...demoContext,
      responsible_parties: [
        ...demoContext.responsible_parties,
        {
          party_id: "team-carpentry-02",
          name: "木工班组二",
          kind: "班组",
          zone_id: "zone-05",
          active: true,
        },
      ],
    };
    render(
      <CaseDetailPage
        caseId={detail.snapshot.case_id}
        actor={null}
        context={context}
        onBack={vi.fn()}
      />,
    );

    expect(await screen.findByRole("heading", { name: "木料组装区人员未佩戴防护手套" })).toBeTruthy();
    expect(screen.getByText("事件 D99C68DB")).toBeTruthy();
    expect(screen.getByText("确认违规")).toBeTruthy();
    expect(screen.getByText("通义千问多模态复核")).toBeTruthy();
    expect(screen.getAllByText("木料组装").length).toBeGreaterThan(0);
    expect(screen.getByText(/木工班组二/)).toBeTruthy();
    expect(screen.getByText("检索安全规范依据")).toBeTruthy();
    expect(screen.getAllByText("有效作业许可").length).toBeGreaterThan(0);
    expect(screen.getByText("系统自动处理")).toBeTruthy();

    expect(screen.queryByText(/TIMBER_ASSEMBLY|task_code|openai_compat|qwen3\.6|team-carpentry-02|actor null|无防护/)).toBeNull();
  });
});
