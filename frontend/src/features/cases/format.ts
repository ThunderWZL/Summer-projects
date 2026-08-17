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
  AGENT: "智能调查",
  HUMAN: "人工操作",
};

export const TASK_OPTIONS = [
  ["MATERIAL_CUTTING", "物料切割"],
  ["BOARD_FASTENING", "木板装订"],
  ["CLIMBING_WORK", "攀爬作业"],
  ["TIMBER_ASSEMBLY", "木料组装"],
  ["GENERAL_SITE_ACTIVITY", "一般现场作业"],
] as const;

const TASK_LABELS = Object.fromEntries(TASK_OPTIONS) as Record<string, string>;

const CAMERA_LABELS: Record<string, string> = {
  "CAM-01": "切割作业机位 A",
  "CAM-02": "切割作业机位 B",
  "CAM-03": "木板装订机位",
  "CAM-04": "攀爬作业机位",
  "CAM-05": "木料组装机位",
  "CAM-06": "多人作业机位",
};

const ZONE_LABELS: Record<string, string> = {
  "zone-01": "切割作业区 A",
  "zone-02": "切割作业区 B",
  "zone-03": "木板装订区",
  "zone-04": "攀爬作业区",
  "zone-05": "木料组装区",
  "zone-06": "综合作业区",
};

const SCENE_LABELS: Record<string, string> = {
  "video-safe-01": "物料切割｜防护齐全",
  "video-no-vest-02": "物料切割｜未穿安全背心",
  "video-no-gloves-01": "木板装订｜未戴防护手套",
  "video-no-vest-gloves-02": "攀爬作业｜未穿背心、未戴手套",
  "video-no-ppe": "木料组装｜三类防护均缺失",
  "video-mixed-wearing": "多人现场｜混合穿戴",
};

const FIELD_LABELS: Record<string, string> = {
  zone: "作业区域",
  zone_id: "作业区域",
  zone_name: "区域名称",
  zone_type: "区域类型",
  active_work_permit: "有效作业许可",
  active_permit_ids: "有效作业许可",
  task_code: "作业类型",
  task_source: "作业确认来源",
  task_ppe_matrix: "防护装备要求",
  site_note: "现场补充说明",
};

const INVESTIGATION_ITEM_LABELS: Record<string, string> = {
  zone: "未找到摄像头对应的作业区域",
  active_work_permit: "缺少当前时段的有效作业许可",
  task_code: "尚未确认当前作业类型",
  task_ppe_matrix: "未配置该作业的防护装备要求",
  invalid_human_task_code: "现场填写的作业类型无效",
  human_task_conflicts_with_active_permit: "现场填写的作业与有效许可不一致",
  multiple_active_permit_tasks: "同一时段存在多个不同作业许可",
};

const TOOL_LABELS: Record<string, string> = {
  list_eligible_responsible_parties: "核对可选整改责任班组",
  search_authoritative_requirements: "检索安全规范依据",
};

const TASK_SOURCE_LABELS: Record<string, string> = {
  active_work_permit: "有效作业许可",
  human_fact: "现场人工补充",
};

const ZONE_TYPE_LABELS: Record<string, string> = {
  CUTTING: "切割作业区",
  CARPENTRY: "木工作业区",
  CLIMBING: "攀爬作业区",
  GENERAL_SITE: "一般施工区",
};

const VLM_VERDICT_LABELS: Record<string, string> = {
  CONFIRMED: "确认违规",
  REJECTED: "未确认违规",
  UNCERTAIN: "证据不足",
};

export function formatTaskLabel(taskCode: string | null): string {
  if (!taskCode) return "作业类型待确认";
  return TASK_LABELS[taskCode] ?? "其他作业";
}

export function formatCameraName(cameraId: string, fallback: string): string {
  return CAMERA_LABELS[cameraId] ?? fallback;
}

export function formatZoneName(zoneId: string, fallback: string): string {
  return ZONE_LABELS[zoneId] ?? fallback;
}

export function formatSceneTitle(videoId: string, fallback: string): string {
  return SCENE_LABELS[videoId] ?? fallback.replace(/\.(mp4|mov|avi)$/i, "");
}

export function formatFieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? "其他现场信息";
}

export function formatInvestigationItem(item: string): string {
  return INVESTIGATION_ITEM_LABELS[item] ?? "其他待核验事项";
}

export function formatToolLabel(tool: string): string {
  return TOOL_LABELS[tool] ?? "执行调查核验";
}

export function formatVlmVerdict(verdict: string): string {
  return VLM_VERDICT_LABELS[verdict] ?? "等待确认";
}

export function formatModelLabel(provider: string, model: string): string {
  if (provider === "openai_compat" && model.toLowerCase().includes("qwen")) {
    return "通义千问多模态复核";
  }
  if (provider === "fixed") return "演示复核模型";
  return "多模态复核模型";
}

export function formatCaseReference(caseId: string): string {
  const uuidPrefix = caseId.match(/[0-9a-f]{8}(?=-[0-9a-f]{4}-)/i)?.[0];
  return `事件 ${(uuidPrefix ?? caseId.replace(/^case-(candidate-)?/, "").slice(0, 8)).toUpperCase()}`;
}

export function formatInvestigationValue(key: string, value: unknown): string {
  if (key === "task_code" && typeof value === "string") return formatTaskLabel(value);
  if (key === "task_source" && typeof value === "string") {
    return TASK_SOURCE_LABELS[value] ?? "系统综合判断";
  }
  if (key === "zone_type" && typeof value === "string") {
    return ZONE_TYPE_LABELS[value] ?? "其他作业区域";
  }
  if (key === "active_permit_ids" && Array.isArray(value)) {
    return value.length ? `${value.length} 张有效许可` : "无有效许可";
  }
  return formatJsonValue(value);
}

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
