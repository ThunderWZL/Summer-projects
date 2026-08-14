import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  connectAnalysisEvents,
  parseAnalysisEvent,
  toWebSocketUrl,
} from "./ws";
import { candidateEvent, progressEvent } from "../test/fixtures";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  readonly url: string;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  close = vi.fn();

  constructor(url: string | URL) {
    this.url = String(url);
    FakeWebSocket.instances.push(this);
  }

  receive(value: unknown) {
    this.onmessage?.(
      new MessageEvent("message", { data: JSON.stringify(value) }),
    );
  }

  disconnect(init: { code: number; reason?: string; wasClean: boolean }) {
    this.onclose?.(new CloseEvent("close", init));
  }
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
});

describe("analysis WebSocket client", () => {
  it("converts relative event URLs to ws or wss without changing the path", () => {
    expect(
      toWebSocketUrl(
        "/ws/v1/analysis-sessions/s-01/events",
        "http://localhost:5173/monitor",
      ),
    ).toBe("ws://localhost:5173/ws/v1/analysis-sessions/s-01/events");
    expect(
      toWebSocketUrl(
        "/ws/v1/analysis-sessions/s-01/events",
        "https://siteppe.example/monitor",
      ),
    ).toBe("wss://siteppe.example/ws/v1/analysis-sessions/s-01/events");
    expect(
      toWebSocketUrl(
        "wss://events.siteppe.example/ws/v1/analysis-sessions/s-01/events",
      ),
    ).toBe(
      "wss://events.siteppe.example/ws/v1/analysis-sessions/s-01/events",
    );
    expect(() =>
      toWebSocketUrl("ftp://siteppe.example/events"),
    ).toThrow(/transport/i);
  });

  it("parses a valid AnalysisEvent and rejects a payload that mismatches event_type", () => {
    expect(parseAnalysisEvent(progressEvent(1, 3))).toEqual(
      progressEvent(1, 3),
    );
    expect(() =>
      parseAnalysisEvent({
        ...progressEvent(2, 3),
        event_type: "SESSION_FAILED",
      }),
    ).toThrow(/payload/i);
  });

  it("rejects non-integer sequences and invalid authoritative counts", () => {
    expect(() =>
      parseAnalysisEvent({
        ...progressEvent(1, 3),
        sequence: 1.5,
      }),
    ).toThrow(/sequence/i);
    expect(() =>
      parseAnalysisEvent({
        ...progressEvent(1, 3),
        payload: {
          ...progressEvent(1, 3).payload,
          candidate_count: "3",
        },
      }),
    ).toThrow(/payload/i);
    expect(() =>
      parseAnalysisEvent({
        ...progressEvent(1, 3),
        occurred_at: "2026-08-07T09:00:00",
      }),
    ).toThrow(/AnalysisEvent/i);
  });

  it("delivers only strictly increasing sequences", () => {
    const onEvent = vi.fn();
    connectAnalysisEvents(
      "/ws/v1/analysis-sessions/analysis-session-01/events",
      { onEvent, onDisconnect: vi.fn(), onProtocolError: vi.fn() },
    );
    const socket = FakeWebSocket.instances[0];

    socket.receive(progressEvent(2, 2));
    socket.receive(progressEvent(2, 99));
    socket.receive(progressEvent(1, 99));
    socket.receive(candidateEvent(3));

    expect(onEvent.mock.calls.map(([event]) => event.sequence)).toEqual([2, 3]);
  });

  it("reports invalid server data instead of forwarding it", () => {
    const onEvent = vi.fn();
    const onProtocolError = vi.fn();
    connectAnalysisEvents(
      "/ws/v1/analysis-sessions/analysis-session-01/events",
      { onEvent, onDisconnect: vi.fn(), onProtocolError },
    );

    FakeWebSocket.instances[0].receive({
      ...candidateEvent(1),
      case_id: null,
    });

    expect(onEvent).not.toHaveBeenCalled();
    expect(onProtocolError).toHaveBeenCalledOnce();
  });

  it("distinguishes a client close from an abnormal server disconnect", () => {
    const onDisconnect = vi.fn();
    const connection = connectAnalysisEvents(
      "/ws/v1/analysis-sessions/analysis-session-01/events",
      { onEvent: vi.fn(), onDisconnect, onProtocolError: vi.fn() },
    );
    const firstSocket = FakeWebSocket.instances[0];

    connection.close();
    firstSocket.disconnect({ code: 1000, wasClean: true });
    expect(firstSocket.close).toHaveBeenCalledOnce();
    expect(onDisconnect).toHaveBeenLastCalledWith(
      expect.objectContaining({ intentional: true }),
    );

    connectAnalysisEvents(
      "/ws/v1/analysis-sessions/analysis-session-02/events",
      { onEvent: vi.fn(), onDisconnect, onProtocolError: vi.fn() },
    );
    FakeWebSocket.instances[1].disconnect({ code: 1006, wasClean: false });
    expect(onDisconnect).toHaveBeenLastCalledWith(
      expect.objectContaining({ intentional: false, code: 1006 }),
    );
  });
});
