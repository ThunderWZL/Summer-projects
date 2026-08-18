import { useEffect, useState, type CSSProperties } from "react";

import {
  CaseApiError,
  fetchCaseDetail,
  submitCaseCommand,
  uploadRectificationEvidenceImage,
} from "../cases/api";
import {
  formatCameraName,
  formatCaseReference,
  formatDuration,
  formatFieldLabel,
  formatInvestigationItem,
  formatInvestigationValue,
  formatLongDateTime,
  formatModelLabel,
  formatNarrative,
  formatSceneTitle,
  formatTaskLabel,
  formatToolLabel,
  formatVlmVerdict,
  formatZoneName,
  FRAME_LABELS,
  PPE_LABELS,
  ROLE_LABELS,
  SOURCE_LABELS,
  STATUS_LABELS,
} from "../cases/format";
import type {
  CaseCommand,
  CaseDetailResponse,
  DemoContext,
  DemoUser,
  EvidenceFrame,
} from "../cases/types";
import { CaseActionPanel } from "./CaseActionPanel";
import { RectificationEvidenceGallery } from "./RectificationEvidenceGallery";

interface CaseDetailPageProps {
  caseId: string;
  actor: DemoUser | null;
  context: DemoContext | null;
  onBack: () => void;
}

export function CaseDetailPage({ caseId, actor, context, onBack }: CaseDetailPageProps) {
  const [detail, setDetail] = useState<CaseDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [commandNotice, setCommandNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchCaseDetail(caseId, controller.signal)
      .then(setDetail)
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof CaseApiError ? reason.message : "事件详情加载失败。");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [actor?.actor_id, caseId, reloadToken]);

  useEffect(() => {
    const refreshLatestDetail = () => setReloadToken((value) => value + 1);
    window.addEventListener("focus", refreshLatestDetail);
    return () => window.removeEventListener("focus", refreshLatestDetail);
  }, [caseId]);

  async function handleCommand(command: CaseCommand) {
    setSubmitting(true);
    setCommandNotice(null);
    try {
      await submitCaseCommand(caseId, command);
      setCommandNotice({ tone: "success", text: "操作已提交，页面已刷新为最新状态。" });
      setReloadToken((value) => value + 1);
    } catch (reason) {
      if (reason instanceof CaseApiError && reason.code === "STALE_CASE_VERSION") {
        setCommandNotice({ tone: "error", text: "事件已被其他人更新。已重新加载最新版本，请检查后再次确认。" });
        setReloadToken((value) => value + 1);
      } else {
        setCommandNotice({
          tone: "error",
          text: reason instanceof CaseApiError ? reason.message : "操作提交失败，请稍后重试。",
        });
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (loading && !detail) return <DetailSkeleton onBack={onBack} />;

  if (error || !detail) {
    return (
      <main className="case-detail case-detail--state">
        <button className="detail-back" type="button" onClick={onBack}>返回事件中心</button>
        <div className="detail-state" role="alert">
          <span>详情暂不可用</span>
          <h1>无法读取事件详情</h1>
          <p>{error ?? "事件不存在或上下文缺失。"}</p>
          <button type="button" onClick={() => setReloadToken((value) => value + 1)}>重新加载</button>
        </div>
      </main>
    );
  }

  const snapshot = detail.snapshot;
  const duration = snapshot.candidate.last_seen_ms - snapshot.candidate.first_seen_ms;
  const applicable = snapshot.investigation?.required_ppe.includes(snapshot.ppe_type);
  const cameraName = formatCameraName(snapshot.camera_id, detail.camera_name);
  const zoneName = formatZoneName(detail.zone_id, detail.zone_name);
  const sceneTitle = formatSceneTitle(detail.video_id, detail.video_title);

  return (
    <main className="case-detail" aria-labelledby="case-detail-title">
      <div className="detail-toolbar">
        <button className="detail-back" type="button" onClick={onBack}>返回事件中心</button>
        <button className="detail-print" type="button" onClick={() => window.print()}>
          打印事件报告
        </button>
      </div>

      <header className="detail-hero">
        <div>
          <p className="case-kicker">安全事件档案</p>
          <h1 id="case-detail-title">{zoneName}人员未佩戴{PPE_LABELS[snapshot.ppe_type]}</h1>
          <p><span title={snapshot.case_id}>{formatCaseReference(snapshot.case_id)}</span> · {cameraName} · {sceneTitle}</p>
        </div>
        <div className="detail-status">
          <span>当前状态 · 版本 {snapshot.version}</span>
          <strong>{STATUS_LABELS[snapshot.status]}</strong>
          <time dateTime={snapshot.updated_at}>更新于 {formatLongDateTime(snapshot.updated_at)}</time>
        </div>
      </header>

      <section className="detail-fact-rail" aria-label="事件摘要">
        <DetailFact label="发生时间" value={formatLongDateTime(snapshot.candidate.occurred_at)} />
        <DetailFact label="持续时间" value={formatDuration(duration)} />
        <DetailFact label="候选置信度" value={`${Math.round(snapshot.candidate.confidence * 100)}%`} />
        <DetailFact label="任务适用性" value={applicable == null ? "待调查" : applicable ? "确认需要" : "不适用"} tone={applicable == null ? "" : applicable ? "patina" : "danger"} />
        <DetailFact label="责任主体" value={detail.responsible_party_name ?? "待审核确认"} />
        <DetailFact label="整改期限" value={snapshot.rectification_due_at ? formatLongDateTime(snapshot.rectification_due_at) : "未设定"} />
      </section>

      <section className="detail-section evidence-section" aria-labelledby="evidence-heading">
        <SectionHeading
          index="01"
          title="关键证据帧"
          description={`${snapshot.candidate.frames.length} 张连续证据 · 人员轨迹 ${snapshot.person_track_id}`}
          id="evidence-heading"
        />
        <div className="evidence-grid">
          {snapshot.candidate.frames.map((frame) => (
            <EvidenceCard key={`${frame.frame_role}-${frame.timestamp_ms}`} frame={frame} />
          ))}
        </div>
      </section>

      <div className="detail-layout">
        <div className="detail-flow">
          <section className="detail-section" aria-labelledby="vlm-heading">
            <SectionHeading index="02" title="AI 语义复核" description="综合核对人员关联、部位可见性和连续证据" id="vlm-heading" />
            {snapshot.vlm_review ? <VlmPanel detail={detail} /> : <MissingBlock text="当前尚无语义复核结果。" />}
          </section>

          <section className="detail-section" aria-labelledby="investigation-heading">
            <SectionHeading index="03" title="调查结论与建议" description="作业规则确定防护要求，智能调查负责汇总依据与处置建议" id="investigation-heading" />
            {snapshot.investigation ? <InvestigationPanel detail={detail} context={context} /> : <MissingBlock text="当前事件尚未形成调查结果。" />}
          </section>

          <section className="detail-section" aria-labelledby="citation-heading">
            <SectionHeading index="04" title="权威引用" description="只有可核验来源才能支撑规范性结论" id="citation-heading" />
            {detail.citations.length ? (
              <div className="citation-list">
                {detail.citations.map((citation, index) => (
                  <article key={`${citation.source_url}-${index}`}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <div>
                      <h3>{citation.document_title}</h3>
                      <p className="citation-meta">{[citation.standard_no, citation.section, citation.effective_date].filter(Boolean).join(" · ")}</p>
                      <blockquote>{citation.excerpt}</blockquote>
                      <a href={citation.source_url} target="_blank" rel="noreferrer">查看权威来源</a>
                    </div>
                  </article>
                ))}
              </div>
            ) : <MissingBlock text="本次调查没有返回可核验引用，因此页面不作“符合规范”等确定性表述。" />}
          </section>

          <section className="detail-section" aria-labelledby="submission-heading">
            <SectionHeading index="05" title="人工提交历史" description="按时间保留现场事实、操作理由和整改证据" id="submission-heading" />
            {detail.human_submissions.length ? (
              <div className="submission-list">
                {detail.human_submissions.map((submission) => (
                  <article key={submission.submission_id}>
                    <header>
                      <div>
                        <strong>{submission.actor_name}</strong>
                        <span>{ROLE_LABELS[submission.actor_role]}</span>
                      </div>
                      <time dateTime={submission.created_at}>{formatLongDateTime(submission.created_at)}</time>
                    </header>
                    <p>{submission.reason}</p>
                    {submission.submission_type === "FACTS" ? (
                      <DefinitionGrid values={submission.facts} />
                    ) : (
                      <div className="submitted-evidence">
                        <p>{submission.description}</p>
                        <RectificationEvidenceGallery evidence={submission.evidence} />
                      </div>
                    )}
                  </article>
                ))}
              </div>
            ) : <MissingBlock text="尚无人工提交记录。" />}
          </section>

          <section className="detail-section" aria-labelledby="timeline-heading">
            <SectionHeading index="06" title="处理时间线" description="记录自动分析与人工处理的关键节点" id="timeline-heading" />
            <ol className="case-timeline">
              {detail.timeline.map((item) => (
                <li key={item.timeline_item_id} className={`timeline--${item.source.toLowerCase()}`}>
                  <div className="timeline-node" />
                  <div>
                    <header>
                      <span>{SOURCE_LABELS[item.source]}</span>
                      <time dateTime={item.occurred_at}>{formatLongDateTime(item.occurred_at)}</time>
                    </header>
                    <h3>{STATUS_LABELS[item.to_status]}</h3>
                    <p>{item.reason ? formatNarrative(item.reason) : "系统自动记录"}</p>
                    <small>{item.actor_name ? `${item.actor_name}${item.actor_role ? ` · ${ROLE_LABELS[item.actor_role]}` : ""}` : "系统自动处理"}</small>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>

        <aside className="detail-action-column" aria-label="当前可执行操作">
          {commandNotice ? <div className={`command-notice command-notice--${commandNotice.tone}`} role="status">{commandNotice.text}</div> : null}
          <CaseActionPanel
            detail={detail}
            actor={actor}
            context={context}
            submitting={submitting}
            onSubmit={handleCommand}
            onUploadEvidence={(evidenceId, file) => {
              if (!actor) throw new CaseApiError("当前角色不可上传整改图片。");
              return uploadRectificationEvidenceImage(
                caseId,
                actor.actor_id,
                evidenceId,
                file,
              );
            }}
          />
          <div className="detail-integrity-note">
            <span>数据保护</span>
            <p>操作成功后会重新加载最新案件；如果案件已被他人更新，系统不会覆盖对方结果。</p>
          </div>
        </aside>
      </div>
    </main>
  );
}

function DetailFact({ label, value, tone = "" }: { label: string; value: string; tone?: "" | "patina" | "danger" }) {
  return <div className={tone ? `detail-fact detail-fact--${tone}` : "detail-fact"}><span>{label}</span><strong>{value}</strong></div>;
}

function SectionHeading({ index, title, description, id }: { index: string; title: string; description: string; id: string }) {
  return <header className="detail-section__heading"><span>{index}</span><div><h2 id={id}>{title}</h2><p>{description}</p></div></header>;
}

function EvidenceCard({ frame }: { frame: EvidenceFrame }) {
  const [failed, setFailed] = useState(false);
  return (
    <figure className={frame.frame_role === "REPRESENTATIVE" ? "evidence-card is-representative" : "evidence-card"}>
      <div
        className="evidence-card__image"
        style={{ aspectRatio: `${frame.image_width} / ${frame.image_height}` }}
      >
        {failed ? (
          <div className="evidence-fallback"><span>图像载入失败</span><button type="button" onClick={() => setFailed(false)}>重试</button></div>
        ) : (
          <>
            <img src={frame.image_url} alt={`${FRAME_LABELS[frame.frame_role]}，视频 ${formatDuration(frame.timestamp_ms)} 处`} onError={() => setFailed(true)} />
            <span className="evidence-box evidence-box--person" style={evidenceBoxStyle(frame.person_box, frame)} aria-hidden="true">
              <i>人员</i>
            </span>
            {frame.observation_box ? (
              <span className="evidence-box evidence-box--observation" style={evidenceBoxStyle(frame.observation_box, frame)} aria-hidden="true">
                <i>缺失装备</i>
              </span>
            ) : null}
          </>
        )}
        <span className="evidence-role">{FRAME_LABELS[frame.frame_role]}</span>
      </div>
      <figcaption>
        <strong>{formatDuration(frame.timestamp_ms)}</strong>
        <span>{frame.image_width} × {frame.image_height}</span>
        <span>{frame.observation_confidence == null ? "人员轨迹关联" : `观测置信度 ${Math.round(frame.observation_confidence * 100)}%`}</span>
      </figcaption>
    </figure>
  );
}

function evidenceBoxStyle(
  box: EvidenceFrame["person_box"],
  frame: EvidenceFrame,
): CSSProperties {
  return {
    left: `${(box.x1 / frame.image_width) * 100}%`,
    top: `${(box.y1 / frame.image_height) * 100}%`,
    width: `${((box.x2 - box.x1) / frame.image_width) * 100}%`,
    height: `${((box.y2 - box.y1) / frame.image_height) * 100}%`,
  };
}

function VlmPanel({ detail }: { detail: CaseDetailResponse }) {
  const review = detail.snapshot.vlm_review!;
  const checks = [
    ["人员关联", review.association === "MATCHED", review.association === "MATCHED" ? "匹配" : "不明确"],
    ["部位可见", review.body_part_visible, review.body_part_visible ? "清楚" : "不可确认"],
    ["跨帧持续", review.persistent, review.persistent ? "成立" : "不成立"],
    ["排除反光", !review.poster_or_reflection, review.poster_or_reflection ? "疑似伪影" : "已排除"],
    ["证据充分", review.evidence_sufficient, review.evidence_sufficient ? "充分" : "不足"],
  ] as const;
  return (
    <div className="vlm-panel">
      <div className="vlm-verdict"><span>复核结论</span><strong className={`verdict--${review.verdict.toLowerCase()}`}>{formatVlmVerdict(review.verdict)}</strong><small>{formatModelLabel(review.model_provider, review.model_name)}</small></div>
      <div className="vlm-checks">{checks.map(([label, pass, value]) => <div key={label} className={pass ? "is-pass" : "is-fail"}><span>{label}</span><strong>{value}</strong></div>)}</div>
      <blockquote>{formatNarrative(review.reason)}</blockquote>
    </div>
  );
}

function InvestigationPanel({ detail, context }: { detail: CaseDetailResponse; context: DemoContext | null }) {
  const investigation = detail.snapshot.investigation!;
  const recommendedParty = context?.responsible_parties.find(
    (party) => party.party_id === investigation.rectification_recommendation?.responsible_party_id,
  );
  return (
    <div className="investigation-panel">
      <div className="investigation-resolver">
        <div><span>适用作业</span><strong>{formatTaskLabel(investigation.applicable_task)}</strong></div>
        <div><span>已识别危害</span><TagList values={investigation.hazards} empty="无" /></div>
        <div><span>作业所需防护装备</span><TagList values={investigation.required_ppe.map((ppe) => PPE_LABELS[ppe])} empty="无额外要求" accent /></div>
        <div><span>待补信息</span><TagList values={investigation.missing_fields.map(formatInvestigationItem)} empty="无" /></div>
        <div><span>信息冲突</span><TagList values={investigation.conflicts.map(formatInvestigationItem)} empty="无" danger={Boolean(investigation.conflicts.length)} /></div>
      </div>
      <div className="agent-advice">
        <span>调查说明与处置建议</span>
        <p>{investigation.recommendation ? formatNarrative(investigation.recommendation) : "未生成处置建议"}</p>
        {investigation.rectification_recommendation ? <div className="agent-recommendation"><strong>建议责任班组：{recommendedParty?.name ?? "待审核确认"}</strong><span>建议期限 {formatLongDateTime(investigation.rectification_recommendation.due_at)}</span><p>{formatNarrative(investigation.rectification_recommendation.reason)}</p></div> : null}
      </div>
      {investigation.tool_trace.length ? (
        <div className="investigation-tools">
          <span>调查核验记录</span>
          <ol>
            {investigation.tool_trace.map((entry, index) => (
              <li key={`${index}-${entry}`}>{formatToolLabel(entry)}</li>
            ))}
          </ol>
        </div>
      ) : null}
      {Object.keys(investigation.facts).length ? <div className="investigation-facts"><span>确认事实</span><DefinitionGrid values={investigation.facts} /></div> : null}
    </div>
  );
}

function DefinitionGrid({ values }: { values: Record<string, unknown> }) {
  const entries = Object.entries(values).filter(([key]) => key !== "zone_id" || !("zone_name" in values));
  return <dl className="definition-grid">{entries.map(([key, value]) => <div key={key}><dt>{formatFieldLabel(key)}</dt><dd>{formatInvestigationValue(key, value)}</dd></div>)}</dl>;
}

function TagList({ values, empty, accent = false, danger = false }: { values: string[]; empty: string; accent?: boolean; danger?: boolean }) {
  if (!values.length) return <em>{empty}</em>;
  return <div className={`tag-list${accent ? " is-accent" : ""}${danger ? " is-danger" : ""}`}>{values.map((value) => <span key={value}>{value}</span>)}</div>;
}

function MissingBlock({ text }: { text: string }) {
  return <div className="detail-missing"><span>暂无数据</span><p>{text}</p></div>;
}

function DetailSkeleton({ onBack }: { onBack: () => void }) {
  return <main className="case-detail"><button className="detail-back" type="button" onClick={onBack}>返回事件中心</button><div className="detail-loading" aria-label="正在加载事件详情"><div /><div /><div /><div /></div></main>;
}
