import { useMemo, useState } from "react";

import { CaseApiError } from "../cases/api";
import {
  formatLongDateTime,
  ROLE_LABELS,
  STATUS_LABELS,
  TASK_OPTIONS,
} from "../cases/format";
import type {
  CaseCommand,
  CaseDetailResponse,
  DemoContext,
  DemoUser,
  JsonValue,
} from "../cases/types";
import { RectificationEvidenceGallery } from "./RectificationEvidenceGallery";

interface CaseActionPanelProps {
  detail: CaseDetailResponse;
  actor: DemoUser | null;
  context: DemoContext | null;
  submitting: boolean;
  onSubmit: (command: CaseCommand) => Promise<void>;
  onUploadEvidence: (evidenceId: string, file: File) => Promise<string>;
}

export function CaseActionPanel({
  detail,
  actor,
  context,
  submitting,
  onSubmit,
  onUploadEvidence,
}: CaseActionPanelProps) {
  const snapshot = detail.snapshot;
  const parties = useMemo(
    () =>
      (context?.responsible_parties ?? []).filter(
        (party) => party.active && party.zone_id === detail.zone_id,
      ),
    [context, detail.zone_id],
  );

  if (!actor) {
    return <ActionUnavailable text="角色目录尚未加载，当前不能提交人工操作。" />;
  }

  if (actor.role === "SITE_SAFETY_OFFICER") {
    if (snapshot.status === "NEEDS_HUMAN_FACTS") {
      return (
        <FactsForm
          actor={actor}
          version={snapshot.version}
          submitting={submitting}
          onSubmit={onSubmit}
        />
      );
    }
    if (snapshot.status === "RECTIFICATION_OPEN") {
      return (
        <EvidenceForm
          actor={actor}
          version={snapshot.version}
          submitting={submitting}
          onSubmit={onSubmit}
          onUploadEvidence={onUploadEvidence}
        />
      );
    }
  }

  if (actor.role === "PROJECT_SAFETY_REVIEWER") {
    if (snapshot.status === "PENDING_REVIEW") {
      return (
        <ReviewForm
          actor={actor}
          detail={detail}
          parties={parties}
          submitting={submitting}
          onSubmit={onSubmit}
        />
      );
    }
    if (snapshot.status === "RECHECK_PENDING") {
      return (
        <RecheckForm
          actor={actor}
          detail={detail}
          submitting={submitting}
          onSubmit={onSubmit}
        />
      );
    }
  }

  return (
    <ActionUnavailable
      text={`${ROLE_LABELS[actor.role]}在“${STATUS_LABELS[snapshot.status]}”阶段没有可执行操作。请切换角色或等待流程进入下一阶段。`}
    />
  );
}

function FactsForm({
  actor,
  version,
  submitting,
  onSubmit,
}: FormSharedProps) {
  const [taskCode, setTaskCode] = useState("");
  const [siteNote, setSiteNote] = useState("");
  const [reason, setReason] = useState("");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const facts: Record<string, JsonValue> = {};
    if (taskCode.trim()) facts.task_code = taskCode.trim();
    if (siteNote.trim()) facts.site_note = siteNote.trim();
    if (!Object.keys(facts).length) return;
    await onSubmit({
      command_type: "SUBMIT_FACTS",
      actor_id: actor.actor_id,
      expected_version: version,
      reason: reason.trim(),
      facts,
    });
  }

  return (
    <form className="action-form" onSubmit={handleSubmit}>
      <ActionHeading title="补充现场事实" actor={actor} />
      <p className="action-form__hint">只提交现场可以确认的信息；防护装备是否适用仍由作业规则自动判断。</p>
      <label>
        <span>作业类型（可选）</span>
        <select value={taskCode} onChange={(event) => setTaskCode(event.target.value)}>
          <option value="">请选择现场作业</option>
          {TASK_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
      <label>
        <span>现场补充说明</span>
        <textarea value={siteNote} onChange={(event) => setSiteNote(event.target.value)} rows={3} placeholder="记录当前作业、许可或其他可核验事实" />
      </label>
      <ReasonField value={reason} onChange={setReason} />
      <button className="action-primary" disabled={submitting || !reason.trim() || (!taskCode.trim() && !siteNote.trim())}>
        {submitting ? "正在提交…" : "提交事实并重新调查"}
      </button>
    </form>
  );
}

function EvidenceForm({
  actor,
  version,
  submitting,
  onSubmit,
  onUploadEvidence,
}: FormSharedProps & {
  onUploadEvidence: (evidenceId: string, file: File) => Promise<string>;
}) {
  const [description, setDescription] = useState("");
  const [evidenceDrafts, setEvidenceDrafts] = useState(() => [emptyEvidenceDraft()]);
  const [reason, setReason] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (evidenceDrafts.some((draft) => !draft.file || !draft.capturedAt)) return;
    setUploading(true);
    setUploadError(null);
    try {
      const uploadedEvidence = await Promise.all(
        evidenceDrafts.map(async (draft) => ({
          evidence_id: draft.evidenceId,
          image_url: await onUploadEvidence(draft.evidenceId, draft.file!),
          captured_at: new Date(draft.capturedAt).toISOString(),
          note: draft.note.trim() || null,
        })),
      );
      await onSubmit({
        command_type: "SUBMIT_RECTIFICATION_EVIDENCE",
        actor_id: actor.actor_id,
        expected_version: version,
        reason: reason.trim(),
        description: description.trim(),
        evidence: uploadedEvidence,
      });
    } catch (error) {
      setUploadError(
        error instanceof CaseApiError || error instanceof Error
          ? error.message
          : "整改图片上传失败，请重试。",
      );
    } finally {
      setUploading(false);
    }
  }

  function updateEvidenceDraft(index: number, patch: Partial<EvidenceDraft>) {
    setEvidenceDrafts((current) =>
      current.map((draft, draftIndex) => draftIndex === index ? { ...draft, ...patch } : draft),
    );
  }

  return (
    <form className="action-form" onSubmit={handleSubmit}>
      <ActionHeading title="提交整改证据" actor={actor} />
      <label>
        <span>整改说明</span>
        <textarea required value={description} onChange={(event) => setDescription(event.target.value)} rows={3} placeholder="说明采取了什么整改措施" />
      </label>
      <div className="evidence-draft-list">
        {evidenceDrafts.map((draft, index) => (
          <fieldset className="evidence-draft" key={draft.draftId}>
            <legend>整改证据 {index + 1}</legend>
            <label>
              <span>证据图片</span>
              <input
                required
                type="file"
                aria-label="证据图片"
                accept="image/jpeg,image/png,image/webp"
                onChange={(event) => updateEvidenceDraft(index, { file: event.target.files?.[0] ?? null })}
              />
              <small>支持 JPEG、PNG、WebP，单张不超过 5 MB。</small>
            </label>
            <label>
              <span>拍摄时间</span>
              <input required type="datetime-local" value={draft.capturedAt} onChange={(event) => updateEvidenceDraft(index, { capturedAt: event.target.value })} />
            </label>
            <label>
              <span>图片备注（可选）</span>
              <input value={draft.note} onChange={(event) => updateEvidenceDraft(index, { note: event.target.value })} placeholder="例如：整改前、整改后或拍摄位置" />
            </label>
            {evidenceDrafts.length > 1 ? (
              <button className="evidence-draft__remove" type="button" onClick={() => setEvidenceDrafts((current) => current.filter((_, draftIndex) => draftIndex !== index))}>
                移除此项
              </button>
            ) : null}
          </fieldset>
        ))}
      </div>
      <button className="evidence-draft__add" type="button" onClick={() => setEvidenceDrafts((current) => [...current, emptyEvidenceDraft()])}>
        添加另一张证据
      </button>
      <ReasonField value={reason} onChange={setReason} />
      {uploadError ? <div className="action-upload-error" role="alert">{uploadError}</div> : null}
      <button className="action-primary" disabled={submitting || uploading || !description.trim() || evidenceDrafts.some((draft) => !draft.file || !draft.capturedAt) || !reason.trim()}>
        {uploading ? "正在上传图片…" : submitting ? "正在提交…" : "提交并进入复查"}
      </button>
    </form>
  );
}

interface EvidenceDraft {
  draftId: string;
  evidenceId: string;
  file: File | null;
  capturedAt: string;
  note: string;
}

let nextEvidenceDraftId = 1;

function emptyEvidenceDraft(): EvidenceDraft {
  return {
    draftId: `evidence-draft-${nextEvidenceDraftId++}`,
    evidenceId: createEvidenceId(),
    file: null,
    capturedAt: "",
    note: "",
  };
}

function createEvidenceId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `manual-${crypto.randomUUID()}`;
  }
  return `manual-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function ReviewForm({
  actor,
  detail,
  parties,
  submitting,
  onSubmit,
}: {
  actor: DemoUser;
  detail: CaseDetailResponse;
  parties: NonNullable<DemoContext>["responsible_parties"];
  submitting: boolean;
  onSubmit: (command: CaseCommand) => Promise<void>;
}) {
  const applicable = Boolean(
    detail.snapshot.investigation?.required_ppe.includes(detail.snapshot.ppe_type),
  );
  const [decision, setDecision] = useState<"approve" | "reinvestigate" | "reject">(
    applicable ? "approve" : "reinvestigate",
  );
  const recommendedPartyId =
    detail.snapshot.investigation?.rectification_recommendation?.responsible_party_id ?? "";
  const [partyId, setPartyId] = useState(
    parties.some((party) => party.party_id === recommendedPartyId)
      ? recommendedPartyId
      : "",
  );
  const [dueAt, setDueAt] = useState("");
  const [reason, setReason] = useState("");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const shared = {
      actor_id: actor.actor_id,
      expected_version: detail.snapshot.version,
      reason: reason.trim(),
    };
    if (decision === "approve") {
      if (!dueAt) return;
      await onSubmit({
        command_type: "APPROVE_RECTIFICATION",
        ...shared,
        responsible_party_id: partyId,
        rectification_due_at: new Date(dueAt).toISOString(),
      });
      return;
    }
    await onSubmit({
      command_type: decision === "reject" ? "REJECT_CASE" : "REQUEST_REINVESTIGATION",
      ...shared,
    });
  }

  return (
    <form className="action-form" onSubmit={handleSubmit}>
      <ActionHeading title="项目审核" actor={actor} />
      <fieldset className="decision-tabs">
        <legend>审核决定</legend>
        <button type="button" aria-pressed={decision === "approve"} className={decision === "approve" ? "is-active" : ""} disabled={!applicable} onClick={() => setDecision("approve")}>批准整改</button>
        <button type="button" aria-pressed={decision === "reinvestigate"} className={decision === "reinvestigate" ? "is-active" : ""} onClick={() => setDecision("reinvestigate")}>退回调查</button>
        <button type="button" aria-pressed={decision === "reject"} className={decision === "reject" ? "is-active" : ""} onClick={() => setDecision("reject")}>驳回事件</button>
      </fieldset>
      {!applicable ? (
        <div className="action-guard">
          当前调查未确认该防护装备为作业必需项，因此不能批准整改。可退回调查或驳回事件。
        </div>
      ) : null}
      {decision === "approve" ? (
        <>
          <label>
            <span>整改责任主体</span>
            <select required value={partyId} onChange={(event) => setPartyId(event.target.value)}>
              <option value="">请选择</option>
              {parties.map((party) => <option key={party.party_id} value={party.party_id}>{party.name}</option>)}
            </select>
          </label>
          <label>
            <span>整改期限</span>
            <input required type="datetime-local" value={dueAt} onChange={(event) => setDueAt(event.target.value)} />
            <small>必须晚于服务端当前时间。</small>
          </label>
        </>
      ) : null}
      <ReasonField value={reason} onChange={setReason} label={decision === "approve" ? "审核理由" : "处理理由"} />
      <button
        className={decision === "reject" ? "action-danger" : "action-primary"}
        disabled={submitting || !reason.trim() || (decision === "approve" && (!applicable || !partyId || !dueAt))}
      >
        {submitting ? "正在提交…" : decision === "approve" ? "确认批准整改" : decision === "reject" ? "确认驳回事件" : "确认退回调查"}
      </button>
    </form>
  );
}

function RecheckForm({
  actor,
  detail,
  submitting,
  onSubmit,
}: Omit<FormSharedProps, "version"> & { detail: CaseDetailResponse }) {
  const [decision, setDecision] = useState<"close" | "reject">("close");
  const [conclusion, setConclusion] = useState("");
  const [reason, setReason] = useState("");
  const latestSubmission = [...detail.human_submissions]
    .reverse()
    .find((submission) => submission.submission_type === "RECTIFICATION_EVIDENCE");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    await onSubmit({
      command_type: decision === "close" ? "APPROVE_CLOSURE" : "REJECT_RECHECK",
      actor_id: actor.actor_id,
      expected_version: detail.snapshot.version,
      reason: reason.trim(),
      recheck_conclusion: conclusion.trim(),
    });
  }

  return (
    <form className="action-form" onSubmit={handleSubmit}>
      <ActionHeading title="复查整改" actor={actor} />
      <section className="rectification-review" aria-labelledby="rectification-review-title">
        <span>现场提交</span>
        <h4 id="rectification-review-title">整改说明与证据</h4>
        {latestSubmission ? (
          <>
            <p className="rectification-review__meta">
              {latestSubmission.actor_name} · {formatLongDateTime(latestSubmission.created_at)}
            </p>
            <p className="rectification-review__reason">提交理由：{latestSubmission.reason}</p>
          </>
        ) : null}
        <p>{detail.snapshot.rectification_description ?? "现场尚未提交整改说明。"}</p>
        {detail.snapshot.rectification_evidence.length ? (
          <RectificationEvidenceGallery evidence={detail.snapshot.rectification_evidence} />
        ) : (
          <small>现场尚未提交整改图片。</small>
        )}
      </section>
      <fieldset className="decision-tabs">
        <legend>复查决定</legend>
        <button type="button" aria-pressed={decision === "close"} className={decision === "close" ? "is-active" : ""} onClick={() => setDecision("close")}>通过并关闭</button>
        <button type="button" aria-pressed={decision === "reject"} className={decision === "reject" ? "is-active" : ""} onClick={() => setDecision("reject")}>退回整改</button>
      </fieldset>
      <label>
        <span>复查结论</span>
        <textarea required value={conclusion} onChange={(event) => setConclusion(event.target.value)} rows={4} placeholder="对照整改前后证据，记录复查结论" />
      </label>
      <ReasonField value={reason} onChange={setReason} />
      <button className={decision === "close" ? "action-primary" : "action-danger"} disabled={submitting || !conclusion.trim() || !reason.trim()}>
        {submitting ? "正在提交…" : decision === "close" ? "确认关闭事件" : "退回继续整改"}
      </button>
    </form>
  );
}

interface FormSharedProps {
  actor: DemoUser;
  version: number;
  submitting: boolean;
  onSubmit: (command: CaseCommand) => Promise<void>;
}

function ActionHeading({ title, actor }: { title: string; actor: DemoUser }) {
  return (
    <div className="action-form__heading">
      <div>
        <span>人工操作</span>
        <h3>{title}</h3>
      </div>
      <small>
        {actor.name === ROLE_LABELS[actor.role]
          ? actor.name
          : `${actor.name} · ${ROLE_LABELS[actor.role]}`}
      </small>
    </div>
  );
}

function ReasonField({
  value,
  onChange,
  label = "操作理由",
}: {
  value: string;
  onChange: (value: string) => void;
  label?: string;
}) {
  return (
    <label>
      <span>{label}</span>
      <textarea required value={value} onChange={(event) => onChange(event.target.value)} rows={3} placeholder="说明判断依据，内容将进入审计时间线" />
    </label>
  );
}

function ActionUnavailable({ text }: { text: string }) {
  return (
    <div className="action-unavailable">
      <span>当前角色</span>
      <h3>当前没有可执行操作</h3>
      <p>{text}</p>
    </div>
  );
}
