import type { DemoVideo } from "../../shared/api";
import {
  formatCameraName,
  formatSceneTitle,
  formatTaskLabel,
  formatZoneName,
} from "../cases/format";

interface ChannelCardProps {
  video: DemoVideo;
  configuredTask: string;
  active: boolean;
  starting?: boolean;
  disabled?: boolean;
  streamUrl?: string;
  candidateCount: number;
  onStart(video: DemoVideo): void;
  onStreamError(): void;
}

export function ChannelCard({
  video,
  configuredTask,
  active,
  starting = false,
  disabled = false,
  streamUrl,
  candidateCount,
  onStart,
  onStreamError,
}: ChannelCardProps) {
  const cameraName = formatCameraName(video.camera_id, video.camera_name);
  const zoneName = formatZoneName(video.zone_id, video.zone_name);
  const sceneTitle = formatSceneTitle(video.video_id, video.title);
  const taskLabel = formatTaskLabel(configuredTask);
  const label = `${video.camera_id} ${cameraName}`;
  const status = starting ? "启动中" : active ? "正在分析" : "未开始分析";

  return (
    <section
      className={`channel-card${active ? " channel-card--active" : ""}`}
      aria-label={label}
      aria-busy={starting}
    >
      <header>
        <div>
          <strong>{video.camera_id}</strong>
          <span>{cameraName}</span>
          <span>{zoneName}</span>
        </div>
        <span className="channel-status">{status}</span>
      </header>

      <div className="video-frame">
        {active && streamUrl ? (
          <img
            src={streamUrl}
            alt={`${video.camera_id} 实时标注画面`}
            onError={onStreamError}
          />
        ) : (
          <video
            src={video.content_url}
            aria-label={`${video.camera_id} 演示预览`}
            muted
            playsInline
            preload="metadata"
          />
        )}
      </div>

      <footer>
        <div className="channel-context">
          <span title={sceneTitle}>{sceneTitle}</span>
          <span>当前作业：{taskLabel}</span>
          <span aria-live="polite">候选 {candidateCount}</span>
        </div>
        <button
          type="button"
          onClick={() => onStart(video)}
          disabled={active || starting || disabled}
          aria-label={`开始分析 ${video.camera_id}`}
        >
          {starting ? "启动中" : "开始分析"}
        </button>
      </footer>
    </section>
  );
}
