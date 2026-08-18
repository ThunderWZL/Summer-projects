import { useEffect, useMemo, useState } from "react";

import { CaseApiError, fetchCases } from "./api";
import {
  formatCaseReference,
  formatDateTime,
  formatZoneName,
  PPE_LABELS,
  STATUS_LABELS,
} from "./format";
import type {
  ActorRole,
  CaseFilters,
  CaseListItem,
  CaseListResponse,
  CaseStatus,
  DemoContext,
  PpeType,
} from "./types";

const DEFAULT_FILTERS: CaseFilters = {
  status: "",
  ppe_type: "",
  zone_id: "",
  responsible_party_id: "",
  occurred_from: "",
  occurred_to: "",
  overdue_only: false,
  keyword: "",
  page: 1,
  page_size: 20,
};

const VERIFIED_PPE: PpeType[] = ["helmet", "gloves", "vest"];

const CASE_CATEGORIES = [
  { key: "needs-facts", label: "待安全员补充现场事实", description: "需要补全作业或现场信息" },
  { key: "pending-review", label: "待项目安全审核人审核", description: "等待确认违规及整改要求" },
  { key: "rectification", label: "待安全员提交整改证据", description: "等待上传整改照片和说明" },
  { key: "recheck", label: "待项目安全审核人复查", description: "等待确认整改结果" },
  { key: "overdue", label: "已逾期", description: "已超过整改期限" },
  { key: "system", label: "系统分析中", description: "正在进行语义复核或智能调查" },
  { key: "closed", label: "已关闭", description: "无需继续处理" },
] as const;

type CaseCategoryKey = typeof CASE_CATEGORIES[number]["key"];

const STATUS_CATEGORIES: Record<CaseStatus, CaseCategoryKey> = {
  YOLO_CANDIDATE: "system",
  VLM_REVIEWED: "system",
  VLM_REJECTED: "closed",
  INVESTIGATING: "system",
  NEEDS_HUMAN_FACTS: "needs-facts",
  REINVESTIGATE: "system",
  PENDING_REVIEW: "pending-review",
  HUMAN_REJECTED: "closed",
  RECTIFICATION_OPEN: "rectification",
  RECHECK_PENDING: "recheck",
  CLOSED: "closed",
};

type RemovableFilterKey = Exclude<keyof CaseFilters, "page" | "page_size" | "status">;

interface ActiveFilter {
  key: RemovableFilterKey;
  label: string;
}

function readFiltersFromUrl(): CaseFilters {
  if (typeof window === "undefined") return DEFAULT_FILTERS;
  const params = new URLSearchParams(window.location.search);
  const page = Number(params.get("page"));
  const pageSize = Number(params.get("page_size"));
  return {
    ...DEFAULT_FILTERS,
    status: "",
    ppe_type: (params.get("ppe_type") as PpeType | null) ?? "",
    zone_id: params.get("zone_id") ?? "",
    responsible_party_id: params.get("responsible_party_id") ?? "",
    occurred_from: params.get("occurred_from") ?? "",
    occurred_to: params.get("occurred_to") ?? "",
    overdue_only: params.get("overdue_only") === "true",
    keyword: params.get("keyword") ?? "",
    page: Number.isInteger(page) && page > 0 ? page : 1,
    page_size: [10, 20, 50].includes(pageSize) ? pageSize : 20,
  };
}

function writeFiltersToUrl(filters: CaseFilters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value === "" || value === false || key === "page_size" && value === 20) return;
    if (key === "page" && value === 1) return;
    params.set(key, String(value));
  });
  const query = params.toString();
  window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
}

interface CaseCenterPageProps {
  actorRole: ActorRole | null;
  context: DemoContext | null;
  onOpenCase: (caseId: string) => void;
}

export function CaseCenterPage({ actorRole, context, onOpenCase }: CaseCenterPageProps) {
  const [filters, setFilters] = useState<CaseFilters>(readFiltersFromUrl);
  const [draftKeyword, setDraftKeyword] = useState(filters.keyword);
  const [response, setResponse] = useState<CaseListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    writeFiltersToUrl(filters);
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    const requestFilters: CaseFilters = {
      ...filters,
      status: actorRole === "SITE_SAFETY_OFFICER" ? "RECTIFICATION_OPEN" : "",
    };
    fetchCases(requestFilters, controller.signal)
      .then(setResponse)
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof CaseApiError ? reason.message : "事件列表加载失败。");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [actorRole, filters, reloadToken]);

  const activeFilterCount = useMemo(
    () =>
      [
        filters.ppe_type,
        filters.zone_id,
        filters.responsible_party_id,
        filters.occurred_from,
        filters.occurred_to,
        filters.overdue_only,
        filters.keyword,
      ].filter(Boolean).length,
    [filters],
  );

  const activeFilters = useMemo<ActiveFilter[]>(() => {
    const items: ActiveFilter[] = [];
    const zone = context?.zones.find((candidate) => candidate.zone_id === filters.zone_id);
    const partyName = context?.responsible_parties.find(
      (party) => party.party_id === filters.responsible_party_id,
    )?.name;

    if (filters.keyword) items.push({ key: "keyword", label: `关键词：${filters.keyword}` });
    if (filters.ppe_type) items.push({ key: "ppe_type", label: PPE_LABELS[filters.ppe_type] });
    if (filters.zone_id) {
      items.push({
        key: "zone_id",
        label: formatZoneName(filters.zone_id, zone?.name ?? "其他作业区域"),
      });
    }
    if (filters.responsible_party_id) {
      items.push({ key: "responsible_party_id", label: partyName ?? "其他责任主体" });
    }
    if (filters.occurred_from) {
      items.push({ key: "occurred_from", label: `起始：${filters.occurred_from}` });
    }
    if (filters.occurred_to) {
      items.push({ key: "occurred_to", label: `截止：${filters.occurred_to}` });
    }
    if (filters.overdue_only) items.push({ key: "overdue_only", label: "仅看已逾期" });
    return items;
  }, [context, filters]);

  function updateFilter<K extends keyof CaseFilters>(key: K, value: CaseFilters[K]) {
    setFilters((current) => ({ ...current, [key]: value, page: key === "page" ? Number(value) : 1 }));
  }

  function applyKeyword(event: React.FormEvent) {
    event.preventDefault();
    updateFilter("keyword", draftKeyword.trim());
  }

  function clearFilter(key: RemovableFilterKey) {
    if (key === "keyword") setDraftKeyword("");
    setFilters((current) => ({
      ...current,
      [key]: key === "overdue_only" ? false : "",
      page: 1,
    }));
  }

  function clearAllFilters() {
    setDraftKeyword("");
    setFilters(DEFAULT_FILTERS);
  }

  const stats = response?.statistics;
  const pagination = response?.pagination;
  const visibleItems = useMemo(
    () => (response?.items ?? []).filter(
      (item) => actorRole !== "SITE_SAFETY_OFFICER" || item.status === "RECTIFICATION_OPEN",
    ),
    [actorRole, response],
  );
  const categorizedItems = useMemo(
    () => CASE_CATEGORIES.map((category) => ({
      ...category,
      items: visibleItems.filter((item) => getCaseCategory(item) === category.key),
    })).filter((category) => category.items.length > 0),
    [visibleItems],
  );

  return (
    <main className="case-center" aria-labelledby="case-center-title">
      <section className="case-center__intro">
        <div>
          <p className="case-kicker">安全事件分级处理</p>
          <h1 id="case-center-title">
            {actorRole === "SITE_SAFETY_OFFICER" ? "处理待提交整改证据的事件" : "先处理需要人判断的事件"}
          </h1>
          <p className="case-center__lede">
            {actorRole === "SITE_SAFETY_OFFICER"
              ? "这里只显示等待现场安全员提交整改证据的事件。"
              : "AI 已完成初步筛选。请按当前队列顺序补充事实、完成审核或确认整改结果。"}
          </p>
        </div>
      </section>

      <section className="triage-summary" aria-label="队列摘要">
        {actorRole === "SITE_SAFETY_OFFICER" ? (
          <>
            <SummaryStat label="待提交整改证据" value={stats?.rectification_open_count} />
            <SummaryStat label="当前页已逾期" value={visibleItems.filter((item) => item.overdue).length} tone="danger" />
          </>
        ) : (
          <>
            <SummaryStat label="待人工处理" value={stats?.open_count} />
            <SummaryStat label="已逾期" value={stats?.overdue_count} tone="danger" />
            <SummaryStat label="待补事实" value={stats?.needs_human_facts_count} />
            <SummaryStat label="待项目审核" value={stats?.pending_review_count} />
            <SummaryStat
              label="平均关闭"
              value={stats?.average_closure_minutes == null ? "—" : `${stats.average_closure_minutes} 分`}
            />
          </>
        )}
        {actorRole !== "SITE_SAFETY_OFFICER" && stats?.top_repeat_risk ? (
          <p className="triage-summary__risk">
            高频区域 <strong>{formatZoneName(stats.top_repeat_risk.zone_id, stats.top_repeat_risk.zone_name)}</strong>
            <span>{PPE_LABELS[stats.top_repeat_risk.ppe_type]}</span>
          </p>
        ) : null}
      </section>

      <div className="case-center__layout">
        <aside className="case-filters" aria-label="筛选事件">
          <div className="case-filters__heading">
            <h2>筛选</h2>
            <span>{activeFilterCount ? `${activeFilterCount} 项生效` : "全部事件"}</span>
          </div>

          <form onSubmit={applyKeyword} className="case-search">
            <label htmlFor="case-keyword">搜索</label>
            <div className="case-search__control">
              <i aria-hidden="true" />
              <input
                id="case-keyword"
                value={draftKeyword}
                onChange={(event) => setDraftKeyword(event.target.value)}
                placeholder="事件编号或关键词"
              />
              <button className="case-visually-hidden" type="submit">搜索</button>
            </div>
          </form>

          <FilterSelect
            label="防护装备"
            value={filters.ppe_type}
            onChange={(value) => updateFilter("ppe_type", value as PpeType | "")}
            options={VERIFIED_PPE.map((ppe) => [ppe, PPE_LABELS[ppe]])}
          />
          <FilterSelect
            label="区域"
            value={filters.zone_id}
            onChange={(value) => updateFilter("zone_id", value)}
            options={(context?.zones ?? []).map((zone) => [zone.zone_id, formatZoneName(zone.zone_id, zone.name)])}
          />
          <FilterSelect
            label="责任主体"
            value={filters.responsible_party_id}
            onChange={(value) => updateFilter("responsible_party_id", value)}
            options={(context?.responsible_parties ?? [])
              .filter((party) => party.active)
              .map((party) => [party.party_id, party.name])}
          />

          <div className="case-filter-dates">
            <label>
              <span>发生日期起</span>
              <input
                type="date"
                value={filters.occurred_from}
                onChange={(event) => updateFilter("occurred_from", event.target.value)}
              />
            </label>
            <label>
              <span>发生日期止</span>
              <input
                type="date"
                value={filters.occurred_to}
                onChange={(event) => updateFilter("occurred_to", event.target.value)}
              />
            </label>
          </div>

          <label className="case-checkbox">
            <input
              type="checkbox"
              checked={filters.overdue_only}
              onChange={(event) => updateFilter("overdue_only", event.target.checked)}
            />
            <span>仅看已逾期事件</span>
          </label>

          <button
            className="case-filter-reset"
            type="button"
            disabled={!activeFilterCount}
            onClick={clearAllFilters}
          >
            清除全部筛选
          </button>
        </aside>

        <section className="case-results" aria-live="polite">
          <header className="case-results__heading">
            <div>
              <p className="case-results__kicker">人工处理队列</p>
              <h2>人工复核队列</h2>
              <p>{pagination ? `共 ${pagination.total_items} 起事件` : "正在读取事件总数"}</p>
            </div>
            <label className="case-page-size">
              每页
              <select
                value={filters.page_size}
                onChange={(event) => updateFilter("page_size", Number(event.target.value))}
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
              </select>
            </label>
          </header>

          {activeFilters.length ? (
            <div className="case-filter-summary" aria-label="当前筛选条件">
              <span>当前筛选</span>
              <div>
                {activeFilters.map((filter) => (
                  <button
                    key={filter.key}
                    type="button"
                    onClick={() => clearFilter(filter.key)}
                    aria-label={`移除筛选：${filter.label}`}
                  >
                    {filter.label}<b aria-hidden="true">×</b>
                  </button>
                ))}
                <button className="case-filter-summary__clear" type="button" onClick={clearAllFilters}>
                  清除全部
                </button>
              </div>
            </div>
          ) : null}

          {loading && !response ? <CaseQueueSkeleton /> : null}

          {error ? (
            <div className="case-state case-state--error" role="alert">
              <span>数据连接失败</span>
              <h3>无法读取事件队列</h3>
              <p>{error}</p>
              <button type="button" onClick={() => setReloadToken((value) => value + 1)}>
                重新加载
              </button>
            </div>
          ) : null}

          {!loading && !error && visibleItems.length === 0 ? (
            <div className="case-state">
              <span>暂无结果</span>
              <h3>{actorRole === "SITE_SAFETY_OFFICER" ? "没有待提交整改证据的事件" : "当前筛选下没有事件"}</h3>
              <p>{actorRole === "SITE_SAFETY_OFFICER" ? "当前没有需要现场安全员处理的整改事件。" : "可以调整区域或时间范围，再重新查看。"}</p>
              {actorRole !== "SITE_SAFETY_OFFICER" ? (
                <button type="button" onClick={clearAllFilters}>查看全部事件</button>
              ) : null}
            </div>
          ) : null}

          {!error && visibleItems.length ? (
            <div className={`review-groups${loading ? " is-refreshing" : ""}`}>
              {categorizedItems.map((category) => (
                <section
                  key={category.key}
                  className={`review-group review-group--${category.key}`}
                  aria-labelledby={`case-category-${category.key}`}
                >
                  <header className="review-group__heading">
                    <div>
                      <h3 id={`case-category-${category.key}`}>{category.label}</h3>
                      <p>{category.description}</p>
                    </div>
                    <strong>{category.items.length} 起</strong>
                  </header>
                  <ol className="review-queue">
                    {category.items.map((item, index) => (
                      <CaseQueueItem
                        key={item.case_id}
                        item={item}
                        sequence={index + 1}
                        onOpenCase={onOpenCase}
                      />
                    ))}
                  </ol>
                </section>
              ))}
            </div>
          ) : null}

          {pagination && pagination.total_pages > 1 ? (
            <nav className="case-pagination" aria-label="事件分页">
              <button
                type="button"
                disabled={pagination.page <= 1}
                onClick={() => updateFilter("page", pagination.page - 1)}
              >
                上一页
              </button>
              <span>
                第 <strong>{pagination.page}</strong> / {pagination.total_pages} 页
              </span>
              <button
                type="button"
                disabled={pagination.page >= pagination.total_pages}
                onClick={() => updateFilter("page", pagination.page + 1)}
              >
                下一页
              </button>
            </nav>
          ) : null}
        </section>
      </div>
    </main>
  );
}

function SummaryStat({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: number | string | undefined;
  tone?: "default" | "danger";
}) {
  return (
    <p className={`summary-stat summary-stat--${tone}`}>
      <span>{label}</span>
      <strong>{value ?? "—"}</strong>
    </p>
  );
}

function getCaseCategory(item: CaseListItem): CaseCategoryKey {
  return item.overdue ? "overdue" : STATUS_CATEGORIES[item.status];
}

function CaseQueueItem({
  item,
  sequence,
  onOpenCase,
}: {
  item: CaseListItem;
  sequence: number;
  onOpenCase: (caseId: string) => void;
}) {
  return (
    <li className={item.overdue && sequence <= 2 ? "is-priority" : undefined}>
      <article
        role="link"
        tabIndex={0}
        onClick={() => onOpenCase(item.case_id)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") onOpenCase(item.case_id);
        }}
      >
        <div className="review-order">
          <strong>{String(sequence).padStart(2, "0")}</strong>
          <span className={`urgency-label urgency-label--${item.urgency.toLowerCase()}`}>
            {item.urgency === "HIGH" ? "高风险" : item.urgency === "MEDIUM" ? "中风险" : "低风险"}
          </span>
        </div>
        <div className="review-identity">
          <h4>{getCaseTitle(item)}</h4>
          <p><span>{formatZoneName(item.zone_id, item.zone_name)}</span><span>{PPE_LABELS[item.ppe_type]}</span></p>
          <code title={item.case_id}>{formatCaseReference(item.case_id)}</code>
        </div>
        <div className="review-reason">
          <span>{item.status === "CLOSED" ? "处理结果" : "需要人工处理"}</span>
          <strong>{getReviewReason(item.status)}</strong>
        </div>
        <div className={`review-deadline${item.overdue ? " is-overdue" : ""}`}>
          <span>{item.rectification_due_at ? "整改期限" : "发生时间"}</span>
          <strong>
            {item.overdue
              ? formatOverdue(item.rectification_due_at)
              : formatDateTime(item.rectification_due_at ?? item.occurred_at)}
          </strong>
          <small>{item.responsible_party_name ?? "责任主体待确认"}</small>
        </div>
        <div className="review-next">
          <span>下一步</span>
          <strong>{STATUS_LABELS[item.status]}</strong>
        </div>
        <span className="review-arrow" aria-hidden="true">→</span>
      </article>
    </li>
  );
}

function getCaseTitle(item: CaseListItem): string {
  return `${formatZoneName(item.zone_id, item.zone_name)}人员未佩戴${PPE_LABELS[item.ppe_type]}`;
}

function formatOverdue(dueAt: string | null): string {
  if (!dueAt) return "已逾期";
  const due = new Date(dueAt).getTime();
  if (!Number.isFinite(due)) return "已逾期";
  const elapsedHours = Math.max(1, Math.floor((Date.now() - due) / 3_600_000));
  if (elapsedHours < 24) return `已逾期 ${elapsedHours}h`;
  const days = Math.floor(elapsedHours / 24);
  const hours = elapsedHours % 24;
  return `已逾期 ${days}d${hours ? ` ${hours}h` : ""}`;
}

function getReviewReason(status: CaseStatus): string {
  const reasons: Record<CaseStatus, string> = {
    YOLO_CANDIDATE: "等待语义复核",
    VLM_REVIEWED: "确认复核结论",
    VLM_REJECTED: "检查异常结果",
    INVESTIGATING: "等待调查结论",
    NEEDS_HUMAN_FACTS: "缺少现场事实",
    REINVESTIGATE: "需要重新调查",
    PENDING_REVIEW: "等待项目审核",
    HUMAN_REJECTED: "处理人工驳回",
    RECTIFICATION_OPEN: "跟进整改进度",
    RECHECK_PENDING: "确认整改证据",
    CLOSED: "处理已完成",
  };
  return reasons[status];
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: [string, string][];
  onChange: (value: string) => void;
}) {
  return (
    <label className="case-filter-select">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">全部</option>
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </select>
    </label>
  );
}

function CaseQueueSkeleton() {
  return (
    <div className="queue-skeleton" aria-label="正在加载事件">
      {Array.from({ length: 7 }, (_, index) => (
        <div key={index} />
      ))}
    </div>
  );
}
