import { useEffect, useState } from "react";
import { Activity, ClipboardCheck, History, ShieldCheck } from "lucide-react";
import { getHealth } from "./api/client";
import { AuditHistory } from "./pages/AuditHistory";
import { FdaAudit } from "./pages/FdaAudit";
import { PrivacyReview } from "./pages/PrivacyReview";
import type { HealthResponse } from "./types/audit";

type AppPage = "fda" | "privacy" | "history";

const pages: Array<{
  id: AppPage;
  label: string;
  icon: typeof ClipboardCheck;
}> = [
  { id: "fda", label: "FDA AI Device Audit", icon: ClipboardCheck },
  { id: "privacy", label: "Privacy Review", icon: ShieldCheck },
  { id: "history", label: "Audit History", icon: History },
];

export default function App() {
  const [activePage, setActivePage] = useState<AppPage>("fda");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState("");

  useEffect(() => {
    let ignore = false;

    getHealth()
      .then((response) => {
        if (!ignore) {
          setHealth(response);
        }
      })
      .catch((error) => {
        if (!ignore) {
          setHealthError(error instanceof Error ? error.message : "FastAPI is not reachable.");
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">AI</div>
          <div>
            <strong>AI Compliance</strong>
            <span>Regulatory audit platform</span>
          </div>
        </div>
        <nav>
          {pages.map((page) => {
            const Icon = page.icon;
            return (
              <button
                className={activePage === page.id ? "nav-button nav-button--active" : "nav-button"}
                key={page.id}
                onClick={() => setActivePage(page.id)}
              >
                <Icon size={18} />
                {page.label}
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <h1>{pages.find((page) => page.id === activePage)?.label}</h1>
            <p>FastAPI-backed workflows for FDA AI audit and privacy compliance review.</p>
          </div>
          <div className={healthError ? "api-state api-state--error" : "api-state"}>
            <Activity size={16} />
            <span>{healthError ? "API offline" : health ? "API online" : "Checking API"}</span>
          </div>
        </header>

        {healthError ? <div className="error-banner">{healthError}</div> : null}
        {health ? (
          <div className="index-strip">
            <div>
              <span>Privacy Index</span>
              <strong>{health.privacy_index_available ? "Available" : "Missing"}</strong>
            </div>
            <div>
              <span>FDA Guidance Index</span>
              <strong>{health.fda_guidance_index_available ? "Available" : "Missing"}</strong>
            </div>
          </div>
        ) : null}

        {activePage === "fda" ? <FdaAudit /> : null}
        {activePage === "privacy" ? <PrivacyReview /> : null}
        {activePage === "history" ? <AuditHistory /> : null}
      </main>
    </div>
  );
}
