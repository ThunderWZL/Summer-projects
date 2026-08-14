import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

const monitorMocks = vi.hoisted(() => ({
  starts: vi.fn(),
}));

vi.mock("./features/monitor/MonitorPage", async () => {
  const { useState } = await import("react");
  return {
    MonitorPage: () => {
      const [running, setRunning] = useState(false);
      return (
        <section aria-label="监控台">
          <button
            type="button"
            onClick={() => {
              monitorMocks.starts();
              setRunning(true);
            }}
          >
            开始测试监控
          </button>
          {running ? <span>监控运行中</span> : null}
        </section>
      );
    },
  };
});

describe("App", () => {
  it("switches between the frozen demo actors without restarting the monitor", () => {
    render(<App />);
    const role = screen.getByRole("combobox", { name: "当前角色" });
    expect((role as HTMLSelectElement).value).toBe("officer-01");

    fireEvent.click(screen.getByRole("button", { name: "开始测试监控" }));
    expect(screen.getByText("监控运行中")).toBeTruthy();

    fireEvent.change(role, { target: { value: "reviewer-01" } });

    expect((role as HTMLSelectElement).value).toBe("reviewer-01");
    expect(screen.getByText("监控运行中")).toBeTruthy();
    expect(monitorMocks.starts).toHaveBeenCalledOnce();
  });
});
