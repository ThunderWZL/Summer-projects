import type {
  CaseCommand,
  CaseDetailResponse,
  CaseFilters,
  CaseListResponse,
  CaseSnapshot,
  DemoContext,
} from "./types";

const API_BASE = "";

export class CaseApiError extends Error {
  readonly code: string;
  readonly currentVersion: number | null;

  constructor(message: string, code = "REQUEST_FAILED", currentVersion: number | null = null) {
    super(message);
    this.name = "CaseApiError";
    this.code = code;
    this.currentVersion = currentVersion;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new CaseApiError("无法连接后端，请检查服务是否已启动。", "NETWORK_ERROR");
  }

  if (!response.ok) {
    const fallback = `请求失败（HTTP ${response.status}）`;
    try {
      const payload = (await response.json()) as {
        code?: string;
        message?: string;
        current_version?: number | null;
      };
      throw new CaseApiError(
        payload.message || fallback,
        payload.code || "REQUEST_FAILED",
        payload.current_version ?? null,
      );
    } catch (error) {
      if (error instanceof CaseApiError) throw error;
      throw new CaseApiError(fallback);
    }
  }

  return (await response.json()) as T;
}

export function fetchCases(filters: CaseFilters, signal?: AbortSignal) {
  const params = new URLSearchParams();
  const optional = {
    status: filters.status,
    ppe_type: filters.ppe_type,
    zone_id: filters.zone_id,
    responsible_party_id: filters.responsible_party_id,
    occurred_from: dateBoundaryIso(filters.occurred_from, false),
    occurred_to: dateBoundaryIso(filters.occurred_to, true),
    keyword: filters.keyword.trim(),
  };
  Object.entries(optional).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  if (filters.overdue_only) params.set("overdue_only", "true");
  params.set("page", String(filters.page));
  params.set("page_size", String(filters.page_size));
  return request<CaseListResponse>(`/api/v1/cases?${params}`, { signal });
}

function dateBoundaryIso(value: string, endOfDay: boolean): string {
  if (!value) return "";
  const date = new Date(`${value}T${endOfDay ? "23:59:59" : "00:00:00"}`);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString();
}

export function fetchCaseDetail(caseId: string, signal?: AbortSignal) {
  return request<CaseDetailResponse>(
    `/api/v1/cases/${encodeURIComponent(caseId)}`,
    { signal },
  );
}

export function fetchDemoContext(signal?: AbortSignal) {
  return request<DemoContext>("/api/v1/demo/context", { signal });
}

export async function submitCaseCommand(
  caseId: string,
  command: CaseCommand,
): Promise<CaseSnapshot> {
  const paths: Record<CaseCommand["command_type"], string> = {
    SUBMIT_FACTS: "facts",
    APPROVE_RECTIFICATION: "review",
    REJECT_CASE: "review",
    REQUEST_REINVESTIGATION: "review",
    SUBMIT_RECTIFICATION_EVIDENCE: "rectification-evidence",
    APPROVE_CLOSURE: "recheck",
    REJECT_RECHECK: "recheck",
  };
  const result = await request<{ snapshot: CaseSnapshot; version: number }>(
    `/api/v1/cases/${encodeURIComponent(caseId)}/${paths[command.command_type]}`,
    { method: "POST", body: JSON.stringify(command) },
  );
  return result.snapshot;
}
