export type PpeType =
  | "helmet"
  | "goggles"
  | "gloves"
  | "vest"
  | "safety_shoes";

export type ActorRole =
  | "SITE_SAFETY_OFFICER"
  | "PROJECT_SAFETY_REVIEWER";

export interface DemoVideo {
  video_id: string;
  camera_id: string;
  camera_name: string;
  zone_id: string;
  zone_name: string;
  title: string;
  duration_ms: number;
  scenario_started_at: string;
  content_url: string;
}

export interface CameraInfo {
  camera_id: string;
  name: string;
  zone_id: string;
}

export interface ZoneInfo {
  zone_id: string;
  name: string;
  zone_type: string;
}

export interface WorkPermit {
  permit_id: string;
  zone_id: string;
  task_code: string;
  hazards: string[];
  responsible_party_id: string;
  starts_at: string;
  ends_at: string;
  status: "ACTIVE" | "EXPIRED";
}

export interface TaskPpeMatrix {
  task_code: string;
  hazards: string[];
  required_ppe: PpeType[];
  exception_note: string | null;
  rectification_window_minutes: number;
}

export interface ResponsibleParty {
  party_id: string;
  name: string;
  kind: string;
  zone_id: string;
  active: boolean;
}

export interface DemoUser {
  actor_id: string;
  name: string;
  role: ActorRole;
  active: boolean;
}

export interface DemoContext {
  cameras: CameraInfo[];
  zones: ZoneInfo[];
  work_permits: WorkPermit[];
  task_ppe_matrix: TaskPpeMatrix[];
  responsible_parties: ResponsibleParty[];
  users: DemoUser[];
}

export type AnalysisStage =
  | "STARTING"
  | "READING"
  | "INFERENCING"
  | "STOPPING";

export interface AnalysisSession {
  session_id: string;
  video_id: string;
  stage: AnalysisStage;
  stream_url: string;
  events_url: string;
}

interface ErrorResponse {
  code: string;
  message: string;
  current_version?: number | null;
}

export class ApiError extends Error {
  readonly status: number | null;
  readonly code: string;
  readonly currentVersion: number | null;

  constructor(response: ErrorResponse, status: number | null = null) {
    super(response.message);
    this.name = "ApiError";
    this.status = status;
    this.code = response.code;
    this.currentVersion = response.current_version ?? null;
  }
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.code === "string" &&
    typeof candidate.message === "string" &&
    (candidate.current_version === undefined ||
      candidate.current_version === null ||
      (Number.isInteger(candidate.current_version) &&
        Number(candidate.current_version) >= 1))
  );
}

async function requestJson<T>(
  url: string,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError({
      code: "NETWORK_ERROR",
      message: "无法连接后端服务",
      current_version: null,
    });
  }

  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    const errorBody = isErrorResponse(body)
      ? body
      : {
          code: "HTTP_ERROR",
          message: `请求失败（${response.status}）`,
          current_version: null,
        };
    throw new ApiError(errorBody, response.status);
  }

  return (await response.json()) as T;
}

export function listDemoVideos(signal?: AbortSignal): Promise<DemoVideo[]> {
  return requestJson<DemoVideo[]>("/api/v1/demo/videos", { signal });
}

export function getDemoContext(signal?: AbortSignal): Promise<DemoContext> {
  return requestJson<DemoContext>("/api/v1/demo/context", { signal });
}

export function startAnalysisSession(
  videoId: string,
): Promise<AnalysisSession> {
  return requestJson<AnalysisSession>("/api/v1/analysis-sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_id: videoId }),
  });
}
