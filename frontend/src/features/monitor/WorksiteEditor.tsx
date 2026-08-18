import { useState } from "react";

import type {
  CameraWorksiteConfiguration,
  ConfigurablePpe,
  WorksiteConfigurationUpdate,
  WorksitePreset,
} from "../../shared/api";
import { PPE_LABELS } from "../cases/format";

const CUSTOM_OPTION = "CUSTOM";
const PPE_OPTIONS: ConfigurablePpe[] = ["helmet", "gloves", "vest"];

interface WorksiteEditorProps {
  cameraId: string;
  configuration: CameraWorksiteConfiguration;
  presets: WorksitePreset[];
  disabled: boolean;
  onCancel(): void;
  onSave(update: WorksiteConfigurationUpdate): Promise<void>;
}

function ppeSummary(requiredPpe: ConfigurablePpe[]): string {
  return requiredPpe.length > 0
    ? requiredPpe.map((ppe) => PPE_LABELS[ppe]).join("、")
    : "无需指定防护装备";
}

export function WorksiteEditor({
  cameraId,
  configuration,
  presets,
  disabled,
  onCancel,
  onSave,
}: WorksiteEditorProps) {
  const [selectedOption, setSelectedOption] = useState(
    configuration.mode === "CUSTOM"
      ? CUSTOM_OPTION
      : (configuration.preset_id ?? ""),
  );
  const [customName, setCustomName] = useState(configuration.name);
  const [requiredPpe, setRequiredPpe] = useState<ConfigurablePpe[]>([
    ...configuration.required_ppe,
  ]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const [saved, setSaved] = useState(false);
  const customSelected = selectedOption === CUSTOM_OPTION;
  const selectedPreset = presets.find(
    (preset) => preset.preset_id === selectedOption,
  );

  const togglePpe = (ppe: ConfigurablePpe) => {
    setRequiredPpe((current) =>
      current.includes(ppe)
        ? current.filter((item) => item !== ppe)
        : PPE_OPTIONS.filter((item) => [...current, ppe].includes(item)),
    );
  };

  const submit = async () => {
    const update: WorksiteConfigurationUpdate = customSelected
      ? {
          mode: "CUSTOM",
          name: customName.trim(),
          required_ppe: requiredPpe,
        }
      : { mode: "PRESET", preset_id: selectedOption };
    setSaving(true);
    setSaveError(false);
    setSaved(false);
    try {
      await onSave(update);
      setSaved(true);
    } catch {
      setSaveError(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      className="worksite-editor"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <div className="worksite-editor__title">
        <div><span>正在配置</span><strong>{cameraId}</strong></div>
        <small>当前要求：{ppeSummary(configuration.required_ppe)}</small>
      </div>

      <label htmlFor="worksite-option">场地方案</label>
      <select
        id="worksite-option"
        aria-label="场地方案"
        value={selectedOption}
        disabled={disabled || saving}
        onChange={(event) => {
          const value = event.target.value;
          setSelectedOption(value);
          setSaved(false);
          const preset = presets.find((item) => item.preset_id === value);
          if (preset) setRequiredPpe([...preset.required_ppe]);
        }}
      >
        {presets.map((preset) => (
          <option key={preset.preset_id} value={preset.preset_id}>
            {preset.name}
          </option>
        ))}
        <option value={CUSTOM_OPTION}>自定义场地</option>
      </select>

      {customSelected ? (
        <>
          <label htmlFor="custom-worksite-name">自定义场地名称</label>
          <input
            id="custom-worksite-name"
            aria-label="自定义场地名称"
            value={customName}
            maxLength={40}
            disabled={disabled || saving}
            onChange={(event) => {
              setCustomName(event.target.value);
              setSaved(false);
            }}
          />
          <fieldset disabled={disabled || saving}>
            <legend>需要的防护装备</legend>
            {PPE_OPTIONS.map((ppe) => (
              <label key={ppe}>
                <input
                  type="checkbox"
                  checked={requiredPpe.includes(ppe)}
                  onChange={() => togglePpe(ppe)}
                  aria-label={`需要${PPE_LABELS[ppe]}`}
                />
                {PPE_LABELS[ppe]}
              </label>
            ))}
          </fieldset>
        </>
      ) : (
        <div className="worksite-editor__preset">
          <span>防护要求</span>
          <strong>{ppeSummary(selectedPreset?.required_ppe ?? [])}</strong>
        </div>
      )}

      {saveError ? <p role="alert">保存失败，请检查后端服务后重试。</p> : null}
      {saved ? <p role="status">{cameraId} 配置已保存。</p> : null}
      <div className="dialog-actions">
        <button type="button" onClick={onCancel}>取消</button>
        <button
          type="submit"
          aria-label={`保存 ${cameraId} 配置`}
          disabled={
            disabled ||
            saving ||
            !selectedOption ||
            (customSelected && !customName.trim())
          }
        >
          {saving ? "保存中" : "保存配置"}
        </button>
      </div>
    </form>
  );
}
