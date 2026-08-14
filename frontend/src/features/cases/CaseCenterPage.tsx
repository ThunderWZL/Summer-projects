import { useEffect, useMemo, useState } from "react";

import { CaseApiError, fetchCases } from "./api";
import { formatDateTime, PPE_LABELS, STATUS_LABELS } from "./format";
import type {
  CaseFilters,
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

const ALL_STATUSES: CaseStatus[] = [
  "YOLO_CANDIDATE",
  "VLM_REVIEWED",
  "INVESTIGATING",
  "NEEDS_HUMAN_FACTS",
  "REINVESTIGATE",
  "PENDING_REVIEW",
  "RECTIFICATION_OPEN",
  "RECHECK_PENDING",
  "VLM_REJECTED",
  "HUMAN_REJECTED",
  "CLOSED",
];

const VERIFIED_PPE: PpeType[] = ["helmet", "gloves", "vest"];

function readFiltersFromUrl(): CaseFilters {
  if (typeof window === "undefined") return DEFAULT_FILTERS;
  const params = new URLSearchParams(window.location.search);
  const page = Number(params.get("page"));
  const pageSize = Number(params.get("page_size"));
  return {
    ...DEFAULT_FILTERS,
    status: (params.get("status") as CaseStatus | null) ?? "",
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
  context: DemoContext | null;
  onOpenCase: (caseId: string) => void;
}

export function CaseCenterPage({ context, onOpenCase }: CaseCenterPageProps) {
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
    fetchCases(filters, controller.signal)
      .then(setResponse)
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof CaseApiError ? reason.message : "事件列表加载失败。");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [filters, reloadToken]);

  const activeFilterCount = useMemo(
    () =>
      [
        filters.status,
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

  function updateFilter<K extends keyof CaseFilters>(key: K, value: CaseFilters[K]) {
    setFilters((current) => ({ ...current, [key]: value, page: key === "page" ? Number(value) : 1 }));
  }

  function applyKeyword(event: React.FormEvent) {
    event.preventDefault();
    updateFilter("keyword", draftKeyword.trim());
  }

  const stats = response?.statistics;
  const pagination = response?.pagination;

  return (
    <main className="case-center" aria-labelledby="case-center-title">
      <section className="case-center__intro">
        <div>
          <p className="case-kicker">EVENT OPERATIONS / 事件中心</p>
          <h1 id="case-center-title">先处理需要人判断的事件</h1>
          <p className="case-center__lede">
            从视觉候选追踪到整改关闭。紧急度、逾期与统计均以服务端结果为准。
          </p>
        </div>
        {stats?.top_repeat_risk ? (
          <div className="repeat-signal" aria-label="区域高频风险">
            <span>区域高频</span>
            <strong>{stats.top_repeat_risk.zone_name}</strong>
            <small>
              {PPE_LABELS[stats.top_repeat_risk.ppe_type]} · {stats.top_repeat_risk.case_count} 起
            </small>
          </div>
        ) : null}
      </section>

      <section className="metric-rail" aria-label="事件统计">
        <Metric label="未关闭" value={stats?.open_count} tone="gold" />
        <Metric label="待补事实" value={stats?.needs_human_facts_count} />
        <Metric label="待项目审核" value={stats?.pending_review_count} />
        <Metric label="已逾期" value={stats?.overdue_count} tone="danger" />
        <Metric
          label="平均关闭"
          value={stats?.average_closure_minutes == null ? "—" : `${stats.average_closure_minutes} 分`}
        />
      </section>

      <div className="case-center__layout">
        <aside className="case-filters" aria-label="筛选事件">
          <div className="case-filters__heading">
            <h2>筛选</h2>
            <span>{activeFilterCount ? `${activeFilterCount} 项生效` : "全部事件"}</span>
          </div>

          <form onSubmit={applyKeyword} className="case-search">
            <label htmlFor="case-keyword">事件编号或关键词</label>
            <div>
              <input
                id="case-keyword"
                value={draftKeyword}
                onChange={(event) => setDraftKeyword(event.target.value)}
                placeholder="例如 CASE-02"
              />
              <button type="submit">查询</button>
            </div>
          </form>

          <FilterSelect
            label="处理状态"
            value={filters.status}
            onChange={(value) => updateFilter("status", value as CaseStatus | "")}
            options={ALL_STATUSES.map((status) => [status, STATUS_LABELS[status]])}
          />
          <FilterSelect
            label="PPE 类型"
            value={filters.ppe_type}
            onChange={(value) => updateFilter("ppe_type", value as PpeType | "")}
            options={VERIFIED_PPE.map((ppe) => [ppe, PPE_LABELS[ppe]])}
          />
          <FilterSelect
            label="区域"
            value={filters.zone_id}
            onChange={(value) => updateFilter("zone_id", value)}
            options={(context?.zones ?? []).map((zone) => [zone.zone_id, zone.name])}
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
            onClick={() => {
              setDraftKeyword("");
              setFilters(DEFAULT_FILTERS);
            }}
          >
            清除全部筛选
          </button>
        </aside>

        <section className="case-results" aria-live="polite">
          <div className="case-results__heading">
            <div>
              <h2>事件队列</h2>
              <p>{pagination ? `共 ${pagination.total_items} 起，按后端队列顺序展示` : "正在读取事件总数"}</p>
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
          </div>

          {loading && !response ? <CaseTableSkeleton /> : null}

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

          {!loading && !error && response?.items.length === 0 ? (
            <div className="case-state">
              <span>0 RESULTS</span>
              <h3>当前筛选下没有事件</h3>
              <p>可以放宽状态、区域或时间范围，再重新查看。</p>
              <button
                type="button"
                onClick={() => {
                  setDraftKeyword("");
                  setFilters(DEFAULT_FILTERS);
                }}
              >
                查看全部事件
              </button>
            </div>
          ) : null}

          {!error && response?.items.length ? (
            <div className={`case-table-wrap${loading ? " is-refreshing" : ""}`}>
              <table className="case-table">
                <thead>
                  <tr>
                    <th>优先级</th>
                    <th>事件 / PPE</th>
                    <th>位置</th>
                    <th>状态</th>
                    <th>责任与期限</th>
                    <th>发生时间</th>
                  </tr>
                </thead>
                <tbody>
                  {response.items.map((item) => (
                    <tr
                      key={item.case_id}
                      tabIndex={0}
                      onClick={() => onOpenCase(item.case_id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") onOpenCase(item.case_id);
                      }}
                    >
                      <td data-label="优先级">
                        <span className={`urgency urgency--${item.urgency.toLowerCase()}`}>
                          {item.urgency === "HIGH" ? "高" : item.urgency === "MEDIUM" ? "中" : "低"}
                        </span>
                        {item.overdue ? <span className="overdue-tag">逾期</span> : null}
                      </td>
                      <td data-label="事件 / PPE">
                        <button className="case-id-link" type="button">
                          {item.case_id}
                        </button>
                        <span className="case-table__secondary">{PPE_LABELS[item.ppe_type]}</span>
                      </td>
                      <td data-label="位置">
                        <strong>{item.zone_name}</strong>
                        <span className="case-table__secondary">{item.camera_name}</span>
                      </td>
                      <td data-label="状态">
                        <span className={`status-text status-text--${item.status.toLowerCase()}`}>
                          {STATUS_LABELS[item.status]}
                        </span>
                      </td>
                      <td data-label="责任与期限">
                        <strong>{item.responsible_party_name ?? "待确认"}</strong>
                        <span className="case-table__secondary">
                          {item.rectification_due_at ? formatDateTime(item.rectification_due_at) : "尚未设定期限"}
                        </span>
                      </td>
                      <td data-label="发生时间">
                        <time dateTime={item.occurred_at}>{formatDateTime(item.occurred_at)}</time>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
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

function Metric({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: number | string | undefined;
  tone?: "default" | "gold" | "danger";
}) {
  return (
    <div className={`metric metric--${tone}`}>
      <span>{label}</span>
      <strong>{value ?? "—"}</strong>
    </div>
  );
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

function CaseTableSkeleton() {
  return (
    <div className="case-skeleton" aria-label="正在加载事件">
      {Array.from({ length: 5 }, (_, index) => (
        <div key={index} />
      ))}
    </div>
  );
}
