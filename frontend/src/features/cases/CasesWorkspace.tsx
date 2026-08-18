import { useEffect, useMemo, useState } from "react";

import { CaseDetailPage } from "../review/CaseDetailPage";
import { ApiError, getDemoContext } from "../../shared/api";
import { CaseCenterPage } from "./CaseCenterPage";
import type { DemoContext, DemoUser } from "./types";
import "./case-center.css";
import "../review/case-detail.css";

interface CasesWorkspaceProps {
  actorId: string;
  selectedCaseId: string | null;
  onSelectCase: (caseId: string | null) => void;
}

export function CasesWorkspace({
  actorId,
  selectedCaseId,
  onSelectCase,
}: CasesWorkspaceProps) {
  const [context, setContext] = useState<DemoContext | null>(null);
  const [contextError, setContextError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function loadContext() {
      try {
        const result = await getDemoContext(controller.signal);
        setContext(result);
      } catch (reason: unknown) {
        if (!controller.signal.aborted) {
          setContextError(
            reason instanceof ApiError
              ? reason.message
              : "演示角色加载失败。",
          );
        }
      }
    }
    void loadContext();
    return () => controller.abort();
  }, []);

  const activeUsers = useMemo(
    () => context?.users.filter((user) => user.active) ?? [],
    [context],
  );
  const actor = activeUsers.find((user) => user.actor_id === actorId) ?? null;
  const actorRole = actor?.role
    ?? (actorId === "officer-01"
      ? "SITE_SAFETY_OFFICER"
      : actorId === "reviewer-01"
        ? "PROJECT_SAFETY_REVIEWER"
        : null);

  return (
    <div className="case-workspace">
      {contextError ? <ContextNotice message={contextError} /> : null}
      {selectedCaseId ? (
        <CaseDetailPage
          caseId={selectedCaseId}
          actor={actor}
          context={context}
          onBack={() => onSelectCase(null)}
        />
      ) : (
        <CaseCenterPage actorRole={actorRole} context={context} onOpenCase={onSelectCase} />
      )}
    </div>
  );
}

function ContextNotice({ message }: { message: string }) {
  return (
    <div className="case-context-notice" role="status">
      角色与责任主体暂不可用：{message}。列表仍可浏览，人工操作暂不可提交。
    </div>
  );
}

export type { DemoUser };
