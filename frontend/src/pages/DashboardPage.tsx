import { useCallback, useEffect, useState } from "react";
import { ApiError, api, type Category, type Complaint, type ComplaintPage, type Priority, type Status } from "../api/client";
import { CategoryTag, PriorityBadge, StatusBadge } from "../components/Badges";
import { CATEGORY_LABELS, PRIORITY_LABELS, STATUS_LABELS, keysOf, providerLabel } from "../labels";

const PAGE_SIZE = 10;

interface Filters {
  category: Category | "";
  priority: Priority | "";
  status: Status | "";
}

export function DashboardPage() {
  const [filters, setFilters] = useState<Filters>({ category: "", priority: "", status: "" });
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ComplaintPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Keyed by complaint id so the server's message appears next to the row it is about.
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setData(await api.listComplaints({ ...filters, page, page_size: PAGE_SIZE }));
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Could not load complaints.");
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    void load();
  }, [load]);

  function setFilter<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  }

  async function changeStatus(complaint: Complaint, status: Status) {
    setBusyId(complaint.id);
    setRowErrors(({ [complaint.id]: _dropped, ...rest }) => rest);
    try {
      const updated = await api.changeStatus(complaint.id, status);
      setData((d) => d && { ...d, items: d.items.map((c) => (c.id === updated.id ? updated : c)) });
    } catch (err) {
      // Surface the server's own words, verbatim — e.g. "Invalid status
      // transition 'open' -> 'resolved' (allowed from 'open': in_progress, rejected)".
      const message = err instanceof ApiError ? err.message : "Could not update status.";
      setRowErrors((e) => ({ ...e, [complaint.id]: message }));
    } finally {
      setBusyId(null);
    }
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <section className="panel">
      <div className="panel__head">
        <h2>Operations dashboard</h2>
        <button type="button" className="btn" onClick={() => void load()} disabled={loading}>
          Refresh
        </button>
      </div>

      <div className="filters" role="group" aria-label="Filters">
        <Select label="Category" value={filters.category} options={CATEGORY_LABELS} onChange={(v) => setFilter("category", v)} />
        <Select label="Priority" value={filters.priority} options={PRIORITY_LABELS} onChange={(v) => setFilter("priority", v)} />
        <Select label="Status" value={filters.status} options={STATUS_LABELS} onChange={(v) => setFilter("status", v)} />
      </div>

      {loadError && (
        <p role="alert" className="alert">
          {loadError}
        </p>
      )}

      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Complaint</th>
              <th>Category</th>
              <th>Priority</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((c) => (
              <tr key={c.id} aria-busy={busyId === c.id}>
                <td>
                  <div className="cell-summary">{c.ai_summary ?? c.text}</div>
                  <div className="muted small">
                    {c.location} · {new Date(c.created_at).toLocaleString()} · {providerLabel(c.triaged_by)}
                  </div>
                  {rowErrors[c.id] && (
                    <p role="alert" className="alert alert--inline">
                      {rowErrors[c.id]}
                    </p>
                  )}
                </td>
                <td>
                  <CategoryTag value={c.category} />
                </td>
                <td>
                  <PriorityBadge value={c.priority} />
                </td>
                <td>
                  <StatusBadge value={c.status} />
                </td>
                <td>
                  <StatusActions complaint={c} disabled={busyId === c.id} onChange={(s) => void changeStatus(c, s)} />
                </td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  No complaints match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <nav className="pager" aria-label="Pagination">
        <button type="button" className="btn" disabled={page <= 1 || loading} onClick={() => setPage((p) => p - 1)}>
          ← Previous
        </button>
        <span data-testid="page-info">
          Page {page} of {totalPages} · {data?.total ?? 0} total
        </span>
        <button type="button" className="btn" disabled={page >= totalPages || loading} onClick={() => setPage((p) => p + 1)}>
          Next →
        </button>
      </nav>
    </section>
  );
}

function Select<T extends string>(props: {
  label: string;
  value: T | "";
  options: Record<T, string>;
  onChange: (value: T | "") => void;
}) {
  const id = `filter-${props.label.toLowerCase()}`;
  return (
    <label htmlFor={id} className="filter">
      <span>{props.label}</span>
      <select id={id} value={props.value} onChange={(e) => props.onChange(e.target.value as T | "")}>
        <option value="">All</option>
        {keysOf(props.options).map((k) => (
          <option key={k} value={k}>
            {props.options[k]}
          </option>
        ))}
      </select>
    </label>
  );
}

/**
 * Primary buttons for the transitions the SERVER says are allowed, plus a
 * "set status" menu offering every status. The menu exists on purpose: the
 * frontend does not decide what is valid, it asks, and shows the server's 409
 * when the answer is no.
 */
function StatusActions(props: { complaint: Complaint; disabled: boolean; onChange: (s: Status) => void }) {
  const { complaint, disabled, onChange } = props;
  const allowed = complaint.allowed_transitions ?? [];
  return (
    <div className="actions">
      {allowed.map((s) => (
        <button key={s} type="button" className="btn btn--small" disabled={disabled} onClick={() => onChange(s)}>
          → {STATUS_LABELS[s]}
        </button>
      ))}
      <select
        aria-label={`Set status for complaint ${complaint.id}`}
        value=""
        disabled={disabled}
        onChange={(e) => e.target.value && onChange(e.target.value as Status)}
      >
        <option value="">Set status…</option>
        {keysOf(STATUS_LABELS)
          .filter((s) => s !== complaint.status)
          .map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
      </select>
    </div>
  );
}
