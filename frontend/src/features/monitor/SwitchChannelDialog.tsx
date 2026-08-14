interface SwitchChannelDialogProps {
  open: boolean;
  currentChannelName: string;
  nextChannelName: string;
  onCancel(): void;
  onConfirm(): void;
}

export function SwitchChannelDialog({
  open,
  currentChannelName,
  nextChannelName,
  onCancel,
  onConfirm,
}: SwitchChannelDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="dialog-backdrop">
      <section
        className="switch-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="switch-dialog-title"
        aria-describedby="switch-dialog-description"
      >
        <h2 id="switch-dialog-title">切换分析通道</h2>
        <div id="switch-dialog-description">
          <p>
            {currentChannelName}：旧会话将停止，但已发现事件会保留。
          </p>
          <p>即将切换至 {nextChannelName}。</p>
        </div>
        <div className="dialog-actions">
          <button type="button" onClick={onCancel} autoFocus>
            取消
          </button>
          <button
            type="button"
            onClick={onConfirm}
            aria-label={`确认切换至 ${nextChannelName}`}
          >
            确认切换
          </button>
        </div>
      </section>
    </div>
  );
}
