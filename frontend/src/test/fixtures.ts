import type {
  AnalysisSession,
  DemoContext,
  DemoVideo,
} from "../shared/api";
import type { AnalysisEvent } from "../shared/ws";

export const demoVideos: DemoVideo[] = Array.from({ length: 6 }, (_, index) => {
  const number = String(index + 1).padStart(2, "0");
  return {
    video_id: `video-${number}`,
    camera_id: `CAM-${number}`,
    camera_name: `测试区 ${number} 机位`,
    zone_id: `zone-${number}`,
    zone_name: `测试区 ${number}`,
    title: `演示视频 ${number}`,
    duration_ms: 600_000,
    scenario_started_at: "2026-08-07T09:00:00+08:00",
    content_url: `/api/v1/demo/videos/video-${number}/content`,
  };
});

export const demoContext: DemoContext = {
  cameras: demoVideos.map((video) => ({
    camera_id: video.camera_id,
    name: video.camera_name,
    zone_id: video.zone_id,
  })),
  zones: demoVideos.map((video) => ({
    zone_id: video.zone_id,
    name: video.zone_name,
    zone_type: "DEMO",
  })),
  work_permits: [
    {
      permit_id: "wp-0101",
      zone_id: "zone-01",
      task_code: "GENERAL_WORK",
      hazards: ["falling_objects"],
      responsible_party_id: "party-01",
      starts_at: "2026-08-07T08:00:00+08:00",
      ends_at: "2026-08-07T18:00:00+08:00",
      status: "ACTIVE",
    },
  ],
  task_ppe_matrix: [
    {
      task_code: "GENERAL_WORK",
      name: "一般作业",
      hazards: ["falling_objects"],
      required_ppe: ["helmet"],
      exception_note: null,
      rectification_window_minutes: 30,
    },
  ],
  responsible_parties: [
    {
      party_id: "party-01",
      name: "施工一组",
      kind: "CONTRACTOR_TEAM",
      zone_id: "zone-01",
      active: true,
    },
  ],
  users: [
    {
      actor_id: "officer-01",
      name: "现场安全员",
      role: "SITE_SAFETY_OFFICER",
      active: true,
    },
    {
      actor_id: "reviewer-01",
      name: "项目安全审核人",
      role: "PROJECT_SAFETY_REVIEWER",
      active: true,
    },
  ],
};

export const analysisSession: AnalysisSession = {
  session_id: "analysis-session-01",
  video_id: "video-01",
  stage: "STARTING",
  stream_url: "/api/v1/analysis-sessions/analysis-session-01/stream.mjpg",
  events_url: "/ws/v1/analysis-sessions/analysis-session-01/events",
};

export function progressEvent(
  sequence: number,
  candidateCount: number,
  sessionId = analysisSession.session_id,
): AnalysisEvent {
  return {
    event_id: `event-${sequence}`,
    sequence,
    event_type: "SESSION_PROGRESS",
    session_id: sessionId,
    occurred_at: "2026-08-07T09:00:01+08:00",
    case_id: null,
    playback_ms: 1_000,
    payload: {
      stage: "INFERENCING",
      progress: 0.5,
      message: null,
      inference_fps: 24,
      candidate_count: candidateCount,
      case_count: candidateCount,
    },
  };
}

export function candidateEvent(
  sequence: number,
  sessionId = analysisSession.session_id,
): AnalysisEvent {
  return {
    event_id: `event-${sequence}`,
    sequence,
    event_type: "CANDIDATE_CREATED",
    session_id: sessionId,
    occurred_at: "2026-08-07T09:00:02+08:00",
    case_id: "case-01",
    playback_ms: 2_000,
    payload: {
      candidate_id: "candidate-01",
      ppe_type: "helmet",
      confidence: 0.91,
      candidate_occurred_at: "2026-08-07T09:00:02+08:00",
      person_track_id: "track-01",
    },
  };
}
