import { useEffect, useState } from "react";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { runtimeConfig } from "./config";
import { DashboardPage } from "./pages/DashboardPage";
import { StatsPage } from "./pages/StatsPage";
import { SubmitPage } from "./pages/SubmitPage";

const VIEWS = {
  submit: { label: "Submit", component: SubmitPage },
  dashboard: { label: "Dashboard", component: DashboardPage },
  stats: { label: "Stats", component: StatsPage },
} as const;

type View = keyof typeof VIEWS;

function viewFromHash(): View {
  const h = window.location.hash.replace("#/", "");
  return h in VIEWS ? (h as View) : "submit";
}

export function App() {
  const [view, setView] = useState<View>(viewFromHash);
  const { environment } = runtimeConfig();

  useEffect(() => {
    const onHash = () => setView(viewFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const Page = VIEWS[view].component;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true">
            ◉
          </span>
          CivicPulse
          <span className="badge badge--muted" title="From /config.js, set at container start">
            {environment}
          </span>
        </div>
        <nav aria-label="Main">
          {(Object.keys(VIEWS) as View[]).map((v) => (
            <a key={v} href={`#/${v}`} className={`nav-link ${v === view ? "nav-link--active" : ""}`} aria-current={v === view ? "page" : undefined}>
              {VIEWS[v].label}
            </a>
          ))}
        </nav>
      </header>
      <main className="container">
        {/* keyed by view: an error in one view is reset when you navigate away */}
        <ErrorBoundary key={view}>
          <Page />
        </ErrorBoundary>
      </main>
    </div>
  );
}
