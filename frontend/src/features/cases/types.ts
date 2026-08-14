export type PpeType = "helmet" | "goggles" | "gloves" | "boots" | "vest";

export type CaseStatus =
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

export type ActorRole =
  | "SITE_SAFETY_OFFICER"
  | "PROJECT_SAFETY_REVIEWER";
export type CaseUrgency = "HIGH" | "MEDIUM" | "LOW";
export type FrameRole = "BEFORE" | "REPRESENTATIVE" | "AFTER";
export type TimelineSource = "YOLO" | "VLM" | "AGENT" | "HUMAN";
export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface CaseListItem {
  case_id: string;
  ppe_type: PpeType;
  status: CaseStatus;
  version: number;
  occurred_at: string;
  updated_at: string;
  camera_id: string;
  camera_name: string;
  zone_id: string;
  zone_name: string;
  responsible_party_id: string | null;
  responsible_party_name: string | null;
  rectification_due_at: string | null;
  overdue: boolean;
  urgency: CaseUrgency;
}

export interface Pagination {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

export interface RepeatRiskSummary {
  zone_id: string;
  zone_name: string;
  ppe_type: PpeType;
  case_count: number;
}

export interface CaseStatistics {
  open_count: number;
  needs_human_facts_count: number;
  pending_review_count: number;
  rectification_open_count: number;
  recheck_pending_count: number;
  overdue_count: number;
  average_closure_minutes: number | null;
  top_repeat_risk: RepeatRiskSummary | null;
}

export interface CaseListResponse {
  items: CaseListItem[];
  pagination: Pagination;
  statistics: CaseStatistics;
}

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface EvidenceFrame {
  timestamp_ms: number;
  image_url: string;
  image_width: number;
  image_height: number;
  frame_role: FrameRole;
  person_box: BoundingBox;
  observation_box: BoundingBox | null;
  observation_confidence: number | null;
}

export interface CandidateEvidence {
  candidate_id: string;
  session_id: string;
  camera_id: string;
  person_track_id: string;
  ppe_type: PpeType;
  evidence_kind:
    | "NEGATIVE_CLASS_DETECTION"
    | "MISSING_POSITIVE_ASSOCIATION";
  confidence: number;
  model_name: string;
  model_version: string | null;
  weights_sha256: string | null;
  aggregation_method: string;
  aggregation_parameters: Record<string, JsonValue>;
  occurred_at: string;
  first_seen_ms: number;
  last_seen_ms: number;
  frames: EvidenceFrame[];
}

export interface VlmReviewResult {
  candidate_id: string;
  verdict: "CONFIRMED" | "REJECTED" | "UNCERTAIN";
  person_track_id: string;
  ppe_type: PpeType;
  association: "MATCHED" | "AMBIGUOUS";
  body_part_visible: boolean;
  persistent: boolean;
  poster_or_reflection: boolean;
  evidence_sufficient: boolean;
  evidence_timestamps_ms: number[];
  reason: string;
  model_name: string;
  model_provider: string;
  model_parameters: Record<string, JsonValue>;
  reviewed_at: string;
}

export interface Citation {
  document_title: string;
  standard_no: string | null;
  section: string;
  effective_date: string | null;
  source_url: string;
  excerpt: string;
}

export interface RectificationRecommendation {
  responsible_party_id: string;
  due_at: string;
  reason: string;
}

export interface InvestigationResult {
  facts: Record<string, JsonValue>;
  conflicts: string[];
  missing_fields: string[];
  applicable_task: string | null;
  hazards: string[];
  required_ppe: PpeType[];
  recommendation: string | null;
  rectification_recommendation: RectificationRecommendation | null;
  citations: Citation[];
  tool_trace: string[];
}

export interface RectificationEvidence {
  evidence_id: string;
  image_url: string;
  captured_at: string;
  note: string | null;
}

export interface CaseTransition {
  from_status: CaseStatus;
  to_status: CaseStatus;
  actor_id: string | null;
  actor_role: ActorRole | null;
  reason: string;
  occurred_at: string;
}

export interface CaseSnapshot {
  case_id: string;
  session_id: string;
  camera_id: string;
  person_track_id: string;
  ppe_type: PpeType;
  status: CaseStatus;
  version: number;
  candidate: CandidateEvidence;
  vlm_review: VlmReviewResult | null;
  investigation: InvestigationResult | null;
  human_facts: Record<string, JsonValue>;
  rectification_responsible_party_id: string | null;
  rectification_due_at: string | null;
  rectification_evidence: RectificationEvidence[];
  rectification_description: string | null;
  recheck_conclusion: string | null;
  created_at: string;
  updated_at: string;
  transitions: CaseTransition[];
}

interface HumanSubmissionBase {
  submission_id: string;
  case_id: string;
  actor_id: string;
  actor_name: string;
  actor_role: ActorRole;
  reason: string;
  created_at: string;
}

export interface FactsSubmissionRecord extends HumanSubmissionBase {
  submission_type: "FACTS";
  facts: Record<string, JsonValue>;
}

export interface EvidenceSubmissionRecord extends HumanSubmissionBase {
  submission_type: "RECTIFICATION_EVIDENCE";
  description: string;
  evidence: RectificationEvidence[];
}

export type HumanSubmissionRecord =
  | FactsSubmissionRecord
  | EvidenceSubmissionRecord;

export interface CaseTimelineItem {
  timeline_item_id: string;
  source: TimelineSource;
  action: string;
  from_status: CaseStatus | null;
  to_status: CaseStatus;
  actor_id: string | null;
  actor_name: string | null;
  actor_role: ActorRole | null;
  reason: string | null;
  occurred_at: string;
}

export interface CaseDetailResponse {
  snapshot: CaseSnapshot;
  camera_name: string;
  zone_id: string;
  zone_name: string;
  zone_type: string;
  video_id: string;
  video_title: string;
  responsible_party_name: string | null;
  responsible_party_kind: string | null;
  citations: Citation[];
  human_submissions: HumanSubmissionRecord[];
  timeline: CaseTimelineItem[];
}

export interface DemoUser {
  actor_id: string;
  name: string;
  role: ActorRole;
  active: boolean;
}

export interface ResponsibleParty {
  party_id: string;
  name: string;
  kind: string;
  zone_id: string;
  active: boolean;
}

export interface ZoneInfo {
  zone_id: string;
  name: string;
  zone_type: string;
}

export interface DemoContext {
  users: DemoUser[];
  responsible_parties: ResponsibleParty[];
  zones: ZoneInfo[];
}

export interface CaseFilters {
  status: CaseStatus | "";
  ppe_type: PpeType | "";
  zone_id: string;
  responsible_party_id: string;
  occurred_from: string;
  occurred_to: string;
  overdue_only: boolean;
  keyword: string;
  page: number;
  page_size: number;
}

export type CaseCommand =
  | {
      command_type: "SUBMIT_FACTS";
      actor_id: string;
      expected_version: number;
      reason: string;
      facts: Record<string, JsonValue>;
    }
  | {
      command_type: "APPROVE_RECTIFICATION";
      actor_id: string;
      expected_version: number;
      reason: string;
      responsible_party_id: string;
      rectification_due_at: string;
    }
  | {
      command_type: "REJECT_CASE" | "REQUEST_REINVESTIGATION";
      actor_id: string;
      expected_version: number;
      reason: string;
    }
  | {
      command_type: "SUBMIT_RECTIFICATION_EVIDENCE";
      actor_id: string;
      expected_version: number;
      reason: string;
      description: string;
      evidence: RectificationEvidence[];
    }
  | {
      command_type: "APPROVE_CLOSURE" | "REJECT_RECHECK";
      actor_id: string;
      expected_version: number;
      reason: string;
      recheck_conclusion: string;
    };
