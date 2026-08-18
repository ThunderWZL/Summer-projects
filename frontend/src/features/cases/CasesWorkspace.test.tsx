import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { demoContext } from "../../test/fixtures";
import { CasesWorkspace } from "./CasesWorkspace";

const api = vi.hoisted(() => ({ getDemoContext: vi.fn() }));
vi.mock("../../shared/api", () => ({
  ApiError: class ApiError extends Error {},
  getDemoContext: api.getDemoContext,
}));
vi.mock("./CaseCenterPage", () => ({
  CaseCenterPage: ({ actorRole, onOpenCase }: { actorRole: string | null; onOpenCase: (caseId: string) => void }) => (
    <section aria-label="案件列表">
      <span>queue-role:{actorRole ?? "all"}</span>
      <button type="button" onClick={() => onOpenCase("case-02")}>打开 case-02</button>
    </section>
  ),
}));
vi.mock("../review/CaseDetailPage", () => ({
  CaseDetailPage: ({ caseId, actor, onBack }: { caseId: string; actor: { actor_id: string } | null; onBack: () => void }) => (
    <section aria-label="案件详情">
      <span>{caseId}</span><span>{actor?.actor_id ?? "commands-disabled"}</span>
      <button type="button" onClick={onBack}>返回案件列表</button>
    </section>
  ),
}));

describe("CasesWorkspace", () => {
  beforeEach(() => {
    api.getDemoContext.mockReset();
  });

  it("resolves the externally selected actor and forwards open/back callbacks", async () => {
    api.getDemoContext.mockResolvedValue(demoContext);
    const onSelectCase = vi.fn();
    const { rerender } = render(
      <CasesWorkspace actorId="officer-01" selectedCaseId={null} onSelectCase={onSelectCase} />,
    );
    expect(screen.getByText("queue-role:SITE_SAFETY_OFFICER")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "打开 case-02" }));
    expect(onSelectCase).toHaveBeenCalledWith("case-02");

    rerender(<CasesWorkspace actorId="reviewer-01" selectedCaseId="case-02" onSelectCase={onSelectCase} />);
    await waitFor(() => expect(screen.getByText("reviewer-01")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "返回案件列表" }));
    expect(onSelectCase).toHaveBeenLastCalledWith(null);
  });

  it("keeps case browsing available when context fails and disables detail commands", async () => {
    let rejectContext: (reason: Error) => void = () => undefined;
    api.getDemoContext.mockImplementation(
      () =>
        new Promise((_, reject) => {
          rejectContext = reject;
        }),
    );
    const { rerender } = render(
      <CasesWorkspace actorId="officer-01" selectedCaseId={null} onSelectCase={vi.fn()} />,
    );
    expect(screen.getByRole("region", { name: "案件列表" })).toBeTruthy();
    rejectContext(new Error("offline"));
    await screen.findByRole("status");

    rerender(<CasesWorkspace actorId="officer-01" selectedCaseId="case-02" onSelectCase={vi.fn()} />);
    expect(screen.getByText("commands-disabled")).toBeTruthy();
  });

  it("does not render a second app header or role selector", () => {
    api.getDemoContext.mockResolvedValue(demoContext);
    render(<CasesWorkspace actorId="officer-01" selectedCaseId={null} onSelectCase={vi.fn()} />);
    expect(screen.queryByRole("banner")).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
  });
});
