import { useCallback, useEffect, useState } from "react";
import { api, type ProvidersMeta, type Stats } from "../api/client";
import { CATEGORY_LABELS, PRIORITY_LABELS, STATUS_LABELS, keysOf, providerLabel } from "../labels";

export function StatsPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [cache, setCache] = useState<"HIT" | "MISS" | "UNKNOWN" | null>(null);
  const [meta, setMeta] = useState<ProvidersMeta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, m] = await Promise.all([api.getStats(), api.getProviders()]);
      setStats(s.stats);
      setCache(s.cache);
      setMeta(m);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load statistics.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="stack">
      <section className="panel">
        <div className="panel__head">
          <h2>Statistics</h2>
          <div className="row">
            {cache && (
              <span
                data-testid="cache-state"
                className={`badge ${cache === "HIT" ? "badge--info" : "badge--muted"}`}
                title="Value of the X-Cache response header from /api/stats"
              >
                X-Cache: {cache}
              </span>
            )}
            <button type="button" className="btn" onClick={() => void load()} disabled={loading}>
              Refresh
            </button>
          </div>
        </div>
        <p className="muted small">
          Served from a 30-second Redis cache that is cleared on every new complaint or status change. Press Refresh twice to
          watch a MISS become a HIT.
        </p>
        {error && (
          <p role="alert" className="alert">
            {error}
          </p>
        )}
        {stats && (
          <>
            <p className="big-number">
              {stats.total} <span className="muted">complaints</span>
            </p>
            <div className="grid-3">
              <Bars title="By category" counts={stats.by_category} labels={CATEGORY_LABELS} total={stats.total} />
              <Bars title="By priority" counts={stats.by_priority} labels={PRIORITY_LABELS} total={stats.total} />
              <Bars title="By status" counts={stats.by_status} labels={STATUS_LABELS} total={stats.total} />
            </div>
            <p className="muted small">Computed at {new Date(stats.generated_at).toLocaleTimeString()}</p>
          </>
        )}
      </section>

      {meta && (
        <section className="panel">
          <h2>Triage providers</h2>
          <dl className="kv">
            <dt>Active</dt>
            <dd>{providerLabel(meta.active_provider)}</dd>
            <dt>Fallback</dt>
            <dd>{providerLabel(meta.fallback_provider)}</dd>
            <dt>Triage cache hit rate</dt>
            <dd>
              {Math.round(meta.triage_cache.hit_rate * 100)}% ({meta.triage_cache.hits} hits / {meta.triage_cache.misses}{" "}
              misses)
            </dd>
          </dl>
          <div className="table-wrap">
            <table className="table table--compact">
              <caption className="muted small">Last {meta.recent.length} triage outcomes</caption>
              <thead>
                <tr>
                  <th>When</th>
                  <th>Provider</th>
                  <th>Latency</th>
                  <th>Fallback</th>
                </tr>
              </thead>
              <tbody>
                {meta.recent.map((o) => (
                  <tr key={`${o.complaint_id}-${o.at}`}>
                    <td>{new Date(o.at).toLocaleTimeString()}</td>
                    <td>
                      {providerLabel(o.provider)}
                      {o.cache_hit && <span className="badge badge--info">cached</span>}
                    </td>
                    <td>{o.latency_ms} ms</td>
                    <td>{o.fallback ? `yes (${o.error ?? "error"})` : "no"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function Bars<T extends string>(props: { title: string; counts: Record<string, number>; labels: Record<T, string>; total: number }) {
  return (
    <div>
      <h3>{props.title}</h3>
      <ul className="bars">
        {keysOf(props.labels).map((key) => {
          const n = props.counts[key] ?? 0;
          const pct = props.total ? (n / props.total) * 100 : 0;
          return (
            <li key={key}>
              <span className="bars__label">{props.labels[key]}</span>
              <span className="bars__track">
                <span className="bars__fill" style={{ width: `${pct}%` }} />
              </span>
              <span className="bars__value" data-testid={`count-${key}`}>
                {n}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
