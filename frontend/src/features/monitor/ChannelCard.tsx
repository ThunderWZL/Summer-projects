import type { DemoVideo } from "../../shared/api";

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
  const label = `${video.camera_id} ${video.camera_name}`;
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
          <span>{video.camera_name}</span>
          <span>{video.zone_name}</span>
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
          <span title={video.title}>当前配置作业：{configuredTask}</span>
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
