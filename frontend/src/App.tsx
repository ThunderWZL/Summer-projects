import { useState } from "react";

import { MonitorPage } from "./features/monitor/MonitorPage";

type DemoActorId = "officer-01" | "reviewer-01";

export function App() {
  const [actorId, setActorId] = useState<DemoActorId>("officer-01");

  return (
    <div className="app-shell">
      <header className="topbar">
        <span className="brand">SitePPE Agent</span>
        <nav aria-label="主导航">
          <span aria-current="page">监控台</span>
        </nav>
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
      </header>
      <main>
        <MonitorPage />
      </main>
    </div>
  );
}
