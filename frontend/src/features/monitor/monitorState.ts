import type { AnalysisSession } from "../../shared/api";
import type { AnalysisEvent } from "../../shared/ws";

type CandidatePayload = Extract<
  AnalysisEvent,
  { event_type: "CANDIDATE_CREATED" }
>["payload"];

export interface MonitorFailure {
  source: "websocket" | "mjpeg" | "protocol" | "backend";
  message: string;
  videoId: string;
  retryable?: boolean;
}

export interface MonitorState {
  activeSession: AnalysisSession | null;
  candidateCount: number;
  caseCount: number;
  candidateCountsByVideo: Record<string, number>;
  caseCountsByVideo: Record<string, number>;
  lastCandidate: CandidatePayload | null;
  failure: MonitorFailure | null;
}

export type MonitorAction =
  | { type: "SESSION_STARTED"; session: AnalysisSession }
  | { type: "SESSION_START_FAILED"; videoId: string; message: string }
  | { type: "ANALYSIS_EVENT"; event: AnalysisEvent }
  | {
      type: "TRANSPORT_FAILED";
      sessionId: string;
      source: "websocket" | "mjpeg" | "protocol";
      message: string;
    };

export function createInitialMonitorState(): MonitorState {
  return {
    activeSession: null,
    candidateCount: 0,
    caseCount: 0,
    candidateCountsByVideo: {},
    caseCountsByVideo: {},
    lastCandidate: null,
    failure: null,
  };
}

function withAuthoritativeCounts(
  state: MonitorState,
  videoId: string,
  candidateCount: number,
  caseCount: number,
): MonitorState {
  return {
    ...state,
    candidateCount,
    caseCount,
    candidateCountsByVideo: {
      ...state.candidateCountsByVideo,
      [videoId]: candidateCount,
    },
    caseCountsByVideo: {
      ...state.caseCountsByVideo,
      [videoId]: caseCount,
    },
  };
}

export function monitorReducer(
  state: MonitorState,
  action: MonitorAction,
): MonitorState {
  if (action.type === "SESSION_STARTED") {
    const videoId = action.session.video_id;
    return {
      ...state,
      activeSession: action.session,
      candidateCount: 0,
      caseCount: 0,
      candidateCountsByVideo: {
        ...state.candidateCountsByVideo,
        [videoId]: 0,
      },
      caseCountsByVideo: {
        ...state.caseCountsByVideo,
        [videoId]: 0,
      },
      lastCandidate: null,
      failure: null,
    };
  }

  if (action.type === "SESSION_START_FAILED") {
    return {
      ...state,
      activeSession: null,
      failure: {
        source: "backend",
        message: action.message,
        videoId: action.videoId,
        retryable: true,
      },
    };
  }

  if (action.type === "TRANSPORT_FAILED") {
    if (state.activeSession?.session_id !== action.sessionId) {
      return state;
    }
    return {
      ...state,
      activeSession: null,
      failure: {
        source: action.source,
        message: action.message,
        videoId: state.activeSession.video_id,
        retryable: true,
      },
    };
  }

  const { event } = action;
  if (state.activeSession?.session_id !== event.session_id) {
    return state;
  }
  const videoId = state.activeSession.video_id;

  if (event.event_type === "SESSION_PROGRESS") {
    return withAuthoritativeCounts(
      state,
      videoId,
      event.payload.candidate_count,
      event.payload.case_count,
    );
  }
  if (event.event_type === "CANDIDATE_CREATED") {
    return { ...state, lastCandidate: event.payload };
  }
  if (event.event_type === "SESSION_FINISHED") {
    return {
      ...withAuthoritativeCounts(
        state,
        videoId,
        event.payload.candidate_count,
        event.payload.case_count,
      ),
      activeSession: null,
    };
  }
  if (event.event_type === "SESSION_FAILED") {
    return {
      ...state,
      activeSession: null,
      failure: {
        source: "backend",
        message: event.payload.message,
        videoId,
        retryable: event.payload.retryable,
      },
    };
  }
  return state;
}
