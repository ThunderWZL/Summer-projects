import { useEffect, useRef, useState } from "react";

import type {
  CameraWorksiteConfiguration,
  DemoVideo,
  WorksiteConfigurations,
  WorksiteConfigurationUpdate,
} from "../../shared/api";
import { formatCameraName } from "../cases/format";
import { WorksiteEditor } from "./WorksiteEditor";

interface WorksiteConfigurationDialogProps {
  open: boolean;
  videos: DemoVideo[];
  configurations: WorksiteConfigurations;
  disabled: boolean;
  onClose(): void;
  onSave(cameraId: string, update: WorksiteConfigurationUpdate): Promise<void>;
}

function configurationFor(
  configurations: WorksiteConfigurations,
  cameraId: string,
): CameraWorksiteConfiguration | null {
  return (
    configurations.cameras.find((item) => item.camera_id === cameraId) ?? null
  );
}

export function WorksiteConfigurationDialog({
  open,
  videos,
  configurations,
  disabled,
  onClose,
  onSave,
}: WorksiteConfigurationDialogProps) {
  const [selectedCameraId, setSelectedCameraId] = useState(
    videos[0]?.camera_id ?? "",
  );
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) closeRef.current?.focus();
  }, [open]);

  if (!open) return null;
  const selectedConfiguration = configurationFor(
    configurations,
    selectedCameraId,
  );

  return (
    <div className="dialog-backdrop">
      <section
        className="worksite-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="worksite-dialog-title"
      >
        <header className="worksite-dialog__header">
          <div>
            <p>运行期规则配置</p>
            <h2 id="worksite-dialog-title">监控场地配置</h2>
          </div>
          <button ref={closeRef} type="button" onClick={onClose}>
            关闭
          </button>
        </header>

        <p className="worksite-dialog__hint">
          选择监控通道并设置当前场地。
        </p>
        {disabled ? (
          <p className="worksite-dialog__notice" role="status">
            分析结束后才能修改场地配置。
          </p>
        ) : null}

        <div className="worksite-dialog__body">
          <nav className="worksite-camera-list" aria-label="监控通道配置列表">
            {videos.map((video) => {
              const configuration = configurationFor(
                configurations,
                video.camera_id,
              );
              return (
                <button
                  key={video.camera_id}
                  type="button"
                  className={
                    selectedCameraId === video.camera_id ? "is-selected" : ""
                  }
                  aria-label={`配置 ${video.camera_id}`}
                  aria-pressed={selectedCameraId === video.camera_id}
                  onClick={() => setSelectedCameraId(video.camera_id)}
                >
                  <strong>{video.camera_id}</strong>
                  <span>{formatCameraName(video.camera_id, video.camera_name)}</span>
                  <small>{configuration?.name ?? "场地待配置"}</small>
                </button>
              );
            })}
          </nav>

          {selectedConfiguration ? (
            <WorksiteEditor
              key={`${selectedCameraId}-${selectedConfiguration.mode}-${selectedConfiguration.name}`}
              cameraId={selectedCameraId}
              configuration={selectedConfiguration}
              presets={configurations.presets}
              disabled={disabled}
              onCancel={onClose}
              onSave={(update) => onSave(selectedCameraId, update)}
            />
          ) : (
            <p role="alert">当前通道缺少场地配置。</p>
          )}
        </div>
      </section>
    </div>
  );
}
