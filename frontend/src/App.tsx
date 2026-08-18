import { useEffect, useState } from "react";

import { MonitorPage } from "./features/monitor/MonitorPage";
import { CasesWorkspace } from "./features/cases/CasesWorkspace";

type DemoActorId = "officer-01" | "reviewer-01";

interface AppRoute {
  casesActive: boolean;
  caseId: string | null;
}

function readRoute(hash: string): AppRoute {
  if (hash === "#/cases") {
    return { casesActive: true, caseId: null };
  }
  if (hash.startsWith("#/cases/")) {
    try {
      return {
        casesActive: true,
        caseId: decodeURIComponent(hash.slice("#/cases/".length)),
      };
    } catch {
      return { casesActive: false, caseId: null };
    }
  }
  return { casesActive: false, caseId: null };
}

export function App() {
  const [actorId, setActorId] = useState<DemoActorId>("officer-01");
  const [configurationOpen, setConfigurationOpen] = useState(false);
  const [hash, setHash] = useState(() => window.location.hash || "#/monitor");

  useEffect(() => {
    const onHashChange = () => {
      setHash(window.location.hash || "#/monitor");
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const { casesActive, caseId } = readRoute(hash);

  function selectCase(id: string | null) {
    window.location.hash = id
      ? `#/cases/${encodeURIComponent(id)}`
      : "#/cases";
  }

  return (
    <div
      className={`app-shell app-shell--${casesActive ? "cases" : "monitor"}`}
    >
      <header className="topbar">
        <span className="brand">SitePPE Agent</span>
        <nav aria-label="主导航">
          <a
            href="#/monitor"
            aria-current={!casesActive ? "page" : undefined}
            onClick={() => setHash("#/monitor")}
          >
            监控台
          </a>
          <a
            href="#/cases"
            aria-current={casesActive ? "page" : undefined}
            onClick={() => {
              setHash("#/cases");
              setConfigurationOpen(false);
            }}
          >
            案件中心
          </a>
        </nav>
        {casesActive ? (
          <label htmlFor="demo-actor">
            当前角色
            <select
              id="demo-actor"
              aria-label="当前角色"
              value={actorId}
              onChange={(event) =>
                setActorId(event.target.value as DemoActorId)
              }
            >
              <option value="officer-01">现场安全员</option>
              <option value="reviewer-01">项目安全审核人</option>
            </select>
          </label>
        ) : (
          <button
            className="topbar-action"
            type="button"
            onClick={() => setConfigurationOpen(true)}
          >
            配置
          </button>
        )}
      </header>
      <main>
        <div hidden={casesActive}>
          <MonitorPage
            configurationOpen={configurationOpen}
            onCloseConfiguration={() => setConfigurationOpen(false)}
          />
        </div>
        <div hidden={!casesActive}>
          <CasesWorkspace
            actorId={actorId}
            selectedCaseId={caseId}
            onSelectCase={selectCase}
          />
        </div>
      </main>
    </div>
  );
}
