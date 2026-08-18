import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const observations = vi.hoisted(() => ({
  monitorMounts: vi.fn(),
  caseProps: vi.fn(),
}));

vi.mock("./features/monitor/MonitorPage", async () => {
  const { useEffect, useState } = await import("react");
  return {
    MonitorPage: ({
      configurationOpen,
      onCloseConfiguration,
    }: {
      configurationOpen: boolean;
      onCloseConfiguration(): void;
    }) => {
      const [running, setRunning] = useState(false);
      useEffect(() => observations.monitorMounts(), []);
      return (
        <section aria-label="监控台工作区">
          <button type="button" onClick={() => setRunning(true)}>启动监控</button>
          {running ? <span>监控运行中</span> : null}
          {configurationOpen ? (
            <section aria-label="场地配置已打开">
              <button type="button" onClick={onCloseConfiguration}>关闭配置</button>
            </section>
          ) : null}
        </section>
      );
    },
  };
});

vi.mock("./features/cases/CasesWorkspace", () => ({
  CasesWorkspace: (props: {
    actorId: string;
    selectedCaseId: string | null;
    onSelectCase: (caseId: string | null) => void;
  }) => {
    observations.caseProps(props);
    return (
      <section aria-label="案件工作区">
        <span>actor:{props.actorId}</span>
        <span>case:{props.selectedCaseId ?? "list"}</span>
        <button type="button" onClick={() => props.onSelectCase("case-02")}>打开案件</button>
      </section>
    );
  },
}));

describe("App", () => {
  beforeEach(() => {
    window.location.hash = "";
    observations.monitorMounts.mockClear();
    observations.caseProps.mockClear();
  });

  it("defaults to monitor and navigates to cases without remounting either workspace", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "启动监控" }));

    expect(screen.getByRole("link", { name: "监控台" }).getAttribute("aria-current")).toBe("page");
    fireEvent.click(screen.getByRole("link", { name: "案件中心" }));

    expect(screen.getByText("监控运行中")).toBeTruthy();
    expect(screen.getByRole("link", { name: "案件中心" }).getAttribute("aria-current")).toBe("page");
    expect(observations.monitorMounts).toHaveBeenCalledOnce();
  });

  it("opens a case hash deep link and falls back to monitor for an unknown hash", () => {
    window.location.hash = "#/cases/case-02";
    render(<App />);
    expect(screen.getByText("case:case-02")).toBeTruthy();

    window.location.hash = "#/unknown";
    fireEvent(window, new HashChangeEvent("hashchange"));

    expect(screen.getByRole("link", { name: "监控台" }).getAttribute("aria-current")).toBe("page");
  });

  it("shows configuration on monitor and role selection only in cases", () => {
    render(<App />);
    expect(screen.queryByRole("combobox", { name: "当前角色" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "配置" }));
    expect(screen.getByRole("region", { name: "场地配置已打开" })).toBeTruthy();

    fireEvent.click(screen.getByRole("link", { name: "案件中心" }));
    fireEvent.change(screen.getByRole("combobox", { name: "当前角色" }), {
      target: { value: "reviewer-01" },
    });

    expect(screen.getByText("actor:reviewer-01")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "配置" })).toBeNull();
  });
});
