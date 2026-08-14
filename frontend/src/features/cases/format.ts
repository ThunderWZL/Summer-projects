import type {
  ActorRole,
  CaseStatus,
  FrameRole,
  PpeType,
  TimelineSource,
} from "./types";

export const PPE_LABELS: Record<PpeType, string> = {
  helmet: "安全帽",
  gloves: "防护手套",
  vest: "高可视背心",
  goggles: "护目镜",
  boots: "安全靴",
};

export const STATUS_LABELS: Record<CaseStatus, string> = {
  YOLO_CANDIDATE: "待 VLM 复核",
  VLM_REVIEWED: "语义复核通过",
  VLM_REJECTED: "语义复核未通过",
  INVESTIGATING: "调查中",
  NEEDS_HUMAN_FACTS: "待补现场事实",
  REINVESTIGATE: "待重新调查",
  PENDING_REVIEW: "待项目审核",
  HUMAN_REJECTED: "人工驳回",
  RECTIFICATION_OPEN: "整改进行中",
  RECHECK_PENDING: "待复查",
  CLOSED: "已关闭",
};

export const ROLE_LABELS: Record<ActorRole, string> = {
  SITE_SAFETY_OFFICER: "现场安全员",
  PROJECT_SAFETY_REVIEWER: "项目安全审核人",
};

export const FRAME_LABELS: Record<FrameRole, string> = {
  BEFORE: "发生前",
  REPRESENTATIVE: "代表帧",
  AFTER: "发生后",
};

export const SOURCE_LABELS: Record<TimelineSource, string> = {
  YOLO: "视觉发现",
  VLM: "语义复核",
  AGENT: "调查 Agent",
  HUMAN: "人工操作",
};

export function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatLongDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatDuration(durationMs: number): string {
  if (durationMs < 1_000) return `${durationMs} 毫秒`;
  if (durationMs < 60_000) return `${(durationMs / 1_000).toFixed(1)} 秒`;
  return `${Math.floor(durationMs / 60_000)} 分 ${Math.round((durationMs % 60_000) / 1_000)} 秒`;
}

export function formatJsonValue(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}
