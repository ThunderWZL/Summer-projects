import { useEffect, useMemo, useState } from "react";

import { CaseDetailPage } from "../review/CaseDetailPage";
import { CaseApiError, fetchDemoContext } from "./api";
import { ROLE_LABELS } from "./format";
import { CaseCenterPage } from "./CaseCenterPage";
import type { DemoContext, DemoUser } from "./types";
import "./case-center.css";
import "../review/case-detail.css";

export function CasesWorkspace() {
  const [context, setContext] = useState<DemoContext | null>(null);
  const [contextError, setContextError] = useState<string | null>(null);
  const [selectedActorId, setSelectedActorId] = useState("");
  const [selectedCaseId, setSelectedCaseId] = useState(() => {
    if (typeof window === "undefined") return null;
    return new URLSearchParams(window.location.search).get("case");
  });

  useEffect(() => {
    const controller = new AbortController();
    fetchDemoContext(controller.signal)
      .then((result) => {
        setContext(result);
        const activeUsers = result.users.filter((user) => user.active);
        const reviewer = activeUsers.find((user) => user.role === "PROJECT_SAFETY_REVIEWER");
        setSelectedActorId((current) => current || reviewer?.actor_id || activeUsers[0]?.actor_id || "");
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setContextError(reason instanceof CaseApiError ? reason.message : "演示角色加载失败。");
        }
      });
    return () => controller.abort();
  }, []);

  const activeUsers = useMemo(
    () => context?.users.filter((user) => user.active) ?? [],
    [context],
  );
  const actor = activeUsers.find((user) => user.actor_id === selectedActorId) ?? null;

  function navigateToCase(caseId: string | null) {
    const params = new URLSearchParams(window.location.search);
    if (caseId) params.set("case", caseId);
    else params.delete("case");
    const query = params.toString();
    window.history.pushState(
      null,
      "",
      `${window.location.pathname}${query ? `?${query}` : ""}`,
    );
    setSelectedCaseId(caseId);
  }

  useEffect(() => {
    const handlePopState = () => {
      setSelectedCaseId(new URLSearchParams(window.location.search).get("case"));
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  return (
    <div className="case-workspace">
      <header className="case-workspace__bar">
        <button className="case-brand" type="button" onClick={() => navigateToCase(null)}>
          <span className="case-brand__mark" aria-hidden="true" />
          <span>
            <strong>SitePPE</strong>
            <small>安全事件闭环</small>
          </span>
        </button>
        <div className="case-workspace__context">
          <span className="case-workspace__live"><i /> 演示上下文</span>
          <label>
            <span>当前操作角色</span>
            <select
              value={selectedActorId}
              onChange={(event) => setSelectedActorId(event.target.value)}
              disabled={!activeUsers.length}
            >
              {!activeUsers.length ? <option value="">正在读取角色</option> : null}
              {activeUsers.map((user) => (
                <option key={user.actor_id} value={user.actor_id}>
                  {user.name === ROLE_LABELS[user.role]
                    ? user.name
                    : `${user.name} · ${ROLE_LABELS[user.role]}`}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      {contextError ? <ContextNotice message={contextError} /> : null}
      {selectedCaseId ? (
        <CaseDetailPage
          caseId={selectedCaseId}
          actor={actor}
          context={context}
          onBack={() => navigateToCase(null)}
        />
      ) : (
        <CaseCenterPage context={context} onOpenCase={(caseId) => navigateToCase(caseId)} />
      )}
    </div>
  );
}

function ContextNotice({ message }: { message: string }) {
  return (
    <div className="case-context-notice" role="status">
      角色与责任主体暂不可用：{message}。列表仍可浏览，人工命令暂不可提交。
    </div>
  );
}

export type { DemoUser };
