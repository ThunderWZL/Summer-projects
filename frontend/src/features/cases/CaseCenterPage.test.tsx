import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  CaseListItem,
  CaseListResponse,
  CaseStatus,
} from "./types";
import { CaseCenterPage } from "./CaseCenterPage";

const api = vi.hoisted(() => ({ fetchCases: vi.fn() }));

vi.mock("./api", () => ({
  CaseApiError: class CaseApiError extends Error {},
  fetchCases: api.fetchCases,
}));

const response: CaseListResponse = {
  items: [
    makeCase("case-facts", "NEEDS_HUMAN_FACTS", "待补事实区"),
    makeCase("case-review", "PENDING_REVIEW", "项目审核区"),
    makeCase("case-evidence", "RECTIFICATION_OPEN", "整改证据区"),
    makeCase("case-recheck", "RECHECK_PENDING", "整改复查区"),
    makeCase("case-closed", "CLOSED", "已关闭区"),
    makeCase("case-overdue", "RECTIFICATION_OPEN", "逾期整改区", true),
    makeCase("case-analysis", "INVESTIGATING", "系统分析区"),
  ],
  pagination: {
    page: 1,
    page_size: 20,
    total_items: 7,
    total_pages: 1,
  },
  statistics: {
    open_count: 6,
    needs_human_facts_count: 1,
    pending_review_count: 1,
    rectification_open_count: 2,
    recheck_pending_count: 1,
    overdue_count: 1,
    average_closure_minutes: 30,
    top_repeat_risk: null,
  },
};

describe("CaseCenterPage action categories", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
    api.fetchCases.mockReset().mockResolvedValue(response);
  });

  it("replaces the status filter with visible action categories", async () => {
    window.history.replaceState(null, "", "/?status=CLOSED");
    render(
      <CaseCenterPage
        actorRole="PROJECT_SAFETY_REVIEWER"
        context={null}
        onOpenCase={vi.fn()}
      />,
    );

    await screen.findByRole("heading", { name: "待安全员补充现场事实" });

    expect(api.fetchCases.mock.calls.at(-1)?.[0]).toMatchObject({ status: "" });
    expect(window.location.search).not.toContain("status=");
    expect(screen.queryByText("处理状态")).toBeNull();
    expect(screen.getByRole("heading", { name: "待项目安全审核人审核" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "待安全员提交整改证据" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "待项目安全审核人复查" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "已关闭" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "已逾期" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "系统分析中" })).toBeTruthy();

    const overdueGroup = screen.getByRole("region", { name: "已逾期" });
    expect(within(overdueGroup).getByText("逾期整改区人员未佩戴防护手套")).toBeTruthy();
    expect(screen.getAllByText("逾期整改区人员未佩戴防护手套")).toHaveLength(1);
  });

  it("limits the site safety officer queue to rectification evidence cases", async () => {
    render(
      <CaseCenterPage
        actorRole="SITE_SAFETY_OFFICER"
        context={null}
        onOpenCase={vi.fn()}
      />,
    );

    await waitFor(() => expect(api.fetchCases).toHaveBeenCalled());
    expect(api.fetchCases.mock.calls.at(-1)?.[0]).toMatchObject({
      status: "RECTIFICATION_OPEN",
    });
    expect(await screen.findByText("整改证据区人员未佩戴防护手套")).toBeTruthy();
    expect(screen.getByText("逾期整改区人员未佩戴防护手套")).toBeTruthy();
    expect(screen.getByText("待提交整改证据")).toBeTruthy();
    expect(screen.queryByText("待项目审核")).toBeNull();
    expect(screen.queryByText("项目审核区人员未佩戴防护手套")).toBeNull();
    expect(screen.queryByText("待安全员补充现场事实")).toBeNull();
  });
});

function makeCase(
  caseId: string,
  status: CaseStatus,
  zoneName: string,
  overdue = false,
): CaseListItem {
  return {
    case_id: caseId,
    ppe_type: "gloves",
    status,
    version: 1,
    occurred_at: "2026-08-18T09:00:00+08:00",
    updated_at: "2026-08-18T09:00:00+08:00",
    camera_id: "CAM-TEST",
    camera_name: "测试机位",
    zone_id: `zone-${caseId}`,
    zone_name: zoneName,
    responsible_party_id: null,
    responsible_party_name: null,
    rectification_due_at: overdue ? "2026-08-17T09:00:00+08:00" : null,
    overdue,
    urgency: overdue ? "HIGH" : "MEDIUM",
  };
}
