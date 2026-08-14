import type { AnalysisStage, PpeType } from "./api";

type VlmVerdict = "CONFIRMED" | "REJECTED" | "UNCERTAIN";

type CaseStatus =
  | "YOLO_CANDIDATE"
  | "VLM_REVIEWED"
  | "VLM_REJECTED"
  | "INVESTIGATING"
  | "NEEDS_HUMAN_FACTS"
  | "REINVESTIGATE"
  | "PENDING_REVIEW"
  | "HUMAN_REJECTED"
  | "RECTIFICATION_OPEN"
  | "RECHECK_PENDING"
  | "CLOSED";

type EventBase<
  EventType extends string,
  Payload,
  CaseId extends string | null,
> = {
  event_id: string;
  sequence: number;
  event_type: EventType;
  session_id: string;
  occurred_at: string;
  case_id: CaseId;
  playback_ms: number;
  payload: Payload;
};

export type AnalysisEvent =
  | EventBase<
      "SESSION_PROGRESS",
      {
        stage: AnalysisStage;
        progress: number;
        message: string | null;
        inference_fps: number;
        candidate_count: number;
        case_count: number;
      },
      null
    >
  | EventBase<
      "SESSION_FAILED",
      { error_code: string; message: string; retryable: boolean },
      null
    >
  | EventBase<
      "CANDIDATE_CREATED",
      {
        candidate_id: string;
        ppe_type: PpeType;
        confidence: number;
        candidate_occurred_at: string;
        person_track_id: string;
      },
      string
    >
  | EventBase<
      "VLM_REVIEWED",
      {
        verdict: VlmVerdict;
        evidence_sufficient: boolean;
        reason: string;
        status: CaseStatus;
        version: number;
      },
      string
    >
  | EventBase<
      "CASE_UPDATED",
      {
        status: CaseStatus;
        version: number;
        updated_at: string;
        action: string;
      },
      string
    >
  | EventBase<
      "SESSION_FINISHED",
      { candidate_count: number; case_count: number },
      null
    >;

const EVENT_TYPES = [
  "SESSION_PROGRESS",
  "SESSION_FAILED",
  "CANDIDATE_CREATED",
  "VLM_REVIEWED",
  "CASE_UPDATED",
  "SESSION_FINISHED",
] as const;

const ANALYSIS_STAGES: readonly string[] = [
  "STARTING",
  "READING",
  "INFERENCING",
  "STOPPING",
];
const PPE_TYPES: readonly string[] = [
  "helmet",
  "goggles",
  "gloves",
  "vest",
  "safety_shoes",
];
const VLM_VERDICTS: readonly string[] = [
  "CONFIRMED",
  "REJECTED",
  "UNCERTAIN",
];
const CASE_STATUSES: readonly string[] = [
  "YOLO_CANDIDATE",
  "VLM_REVIEWED",
  "VLM_REJECTED",
  "INVESTIGATING",
  "NEEDS_HUMAN_FACTS",
  "REINVESTIGATE",
  "PENDING_REVIEW",
  "HUMAN_REJECTED",
  "RECTIFICATION_OPEN",
  "RECHECK_PENDING",
  "CLOSED",
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function isNonNegativeNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

function isNonNegativeInteger(value: unknown): value is number {
  return Number.isInteger(value) && Number(value) >= 0;
}

function isPositiveInteger(value: unknown): value is number {
  return Number.isInteger(value) && Number(value) >= 1;
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isAwareDateTime(value: unknown): value is string {
  return (
    isNonEmptyString(value) &&
    /(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

function hasValidPayload(
  eventType: AnalysisEvent["event_type"],
  payload: Record<string, unknown>,
): boolean {
  switch (eventType) {
    case "SESSION_PROGRESS":
      return (
        typeof payload.stage === "string" &&
        ANALYSIS_STAGES.includes(payload.stage) &&
        isNonNegativeNumber(payload.progress) &&
        payload.progress <= 1 &&
        isNullableString(payload.message) &&
        isNonNegativeNumber(payload.inference_fps) &&
        isNonNegativeInteger(payload.candidate_count) &&
        isNonNegativeInteger(payload.case_count)
      );
    case "SESSION_FAILED":
      return (
        isNonEmptyString(payload.error_code) &&
        isNonEmptyString(payload.message) &&
        typeof payload.retryable === "boolean"
      );
    case "CANDIDATE_CREATED":
      return (
        isNonEmptyString(payload.candidate_id) &&
        typeof payload.ppe_type === "string" &&
        PPE_TYPES.includes(payload.ppe_type) &&
        isNonNegativeNumber(payload.confidence) &&
        payload.confidence <= 1 &&
        isAwareDateTime(payload.candidate_occurred_at) &&
        isNonEmptyString(payload.person_track_id)
      );
    case "VLM_REVIEWED":
      return (
        typeof payload.verdict === "string" &&
        VLM_VERDICTS.includes(payload.verdict) &&
        typeof payload.evidence_sufficient === "boolean" &&
        isNonEmptyString(payload.reason) &&
        typeof payload.status === "string" &&
        CASE_STATUSES.includes(payload.status) &&
        isPositiveInteger(payload.version)
      );
    case "CASE_UPDATED":
      return (
        typeof payload.status === "string" &&
        CASE_STATUSES.includes(payload.status) &&
        isPositiveInteger(payload.version) &&
        isAwareDateTime(payload.updated_at) &&
        isNonEmptyString(payload.action)
      );
    case "SESSION_FINISHED":
      return (
        isNonNegativeInteger(payload.candidate_count) &&
        isNonNegativeInteger(payload.case_count)
      );
  }
}

export function toWebSocketUrl(
  eventsUrl: string,
  baseUrl = window.location.href,
): string {
  const url = new URL(eventsUrl, baseUrl);
  if (url.protocol === "https:") {
    url.protocol = "wss:";
  } else if (url.protocol === "http:") {
    url.protocol = "ws:";
  } else if (url.protocol !== "ws:" && url.protocol !== "wss:") {
    throw new Error("events_url must use HTTP or WebSocket transport");
  }
  return url.toString();
}

export function parseAnalysisEvent(value: unknown): AnalysisEvent {
  if (!isRecord(value)) {
    throw new Error("Invalid AnalysisEvent");
  }
  if (!isNonEmptyString(value.event_type)) {
    throw new Error("Invalid event_type");
  }
  const eventType = value.event_type as AnalysisEvent["event_type"];
  if (!(EVENT_TYPES as readonly string[]).includes(eventType)) {
    throw new Error("Invalid event_type");
  }
  if (!isPositiveInteger(value.sequence)) {
    throw new Error("Invalid sequence");
  }
  if (
    !isNonEmptyString(value.event_id) ||
    !isNonEmptyString(value.session_id) ||
    !isAwareDateTime(value.occurred_at) ||
    !isNonNegativeInteger(value.playback_ms)
  ) {
    throw new Error("Invalid AnalysisEvent");
  }
  if (!isRecord(value.payload) || !hasValidPayload(eventType, value.payload)) {
    throw new Error("payload must match event_type");
  }
  const requiresCaseId =
    eventType === "CANDIDATE_CREATED" ||
    eventType === "VLM_REVIEWED" ||
    eventType === "CASE_UPDATED";
  if (
    (requiresCaseId && !isNonEmptyString(value.case_id)) ||
    (!requiresCaseId && value.case_id !== null)
  ) {
    throw new Error("case_id must match event_type");
  }
  return value as AnalysisEvent;
}

export interface AnalysisEventsConnection {
  close(): void;
}

interface AnalysisEventHandlers {
  onEvent(event: AnalysisEvent): void;
  onDisconnect(event: {
    intentional: boolean;
    code: number;
    reason: string;
  }): void;
  onProtocolError(error: Error): void;
}

export function connectAnalysisEvents(
  eventsUrl: string,
  handlers: AnalysisEventHandlers,
): AnalysisEventsConnection {
  const socket = new WebSocket(toWebSocketUrl(eventsUrl));
  let intentional = false;
  let lastSequence = 0;

  socket.onmessage = (message) => {
    try {
      const event = parseAnalysisEvent(JSON.parse(message.data));
      if (event.sequence <= lastSequence) {
        return;
      }
      lastSequence = event.sequence;
      handlers.onEvent(event);
    } catch (error) {
      handlers.onProtocolError(
        error instanceof Error ? error : new Error("Invalid AnalysisEvent"),
      );
    }
  };
  socket.onclose = (event) => {
    handlers.onDisconnect({
      intentional,
      code: event.code,
      reason: event.reason,
    });
  };

  return {
    close() {
      intentional = true;
      socket.close();
    },
  };
}
