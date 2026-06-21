import { useEffect, useState } from "react";
import { Activity, ClipboardCheck, History, ShieldCheck, Stethoscope } from "lucide-react";
import { getHealth } from "./api/client";
import { AiSafetyEvaluation } from "./pages/AiSafetyEvaluation";
import { AuditHistory } from "./pages/AuditHistory";
import { FdaAudit } from "./pages/FdaAudit";
import { PrivacyReview } from "./pages/PrivacyReview";
import type { HealthResponse } from "./types/audit";

type AppPage = "ai-safety" | "fda" | "privacy" | "history";

const pages: Array<{
  id: AppPage;
  label: string;
  icon: typeof ClipboardCheck;
}> = [
  { id: "ai-safety", label: "AI Safety Evaluation", icon: Stethoscope },
  { id: "fda", label: "FDA AI Device Audit", icon: ClipboardCheck },
  { id: "privacy", label: "Privacy Review", icon: ShieldCheck },
  { id: "history", label: "Audit History", icon: History },
];

export default function App() {
  const [activePage, setActivePage] = useState<AppPage>("ai-safety");
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
          <div className="brand-mark">AS</div>
          <div>
            <strong>AfriSafeBench</strong>
            <span>AI safety evaluation tool</span>
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
            <p>African healthcare AI deployment risk assessment and governance recommendations.</p>
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
              <span>AfriSafeBench Frameworks</span>
              <strong>{health.afrisafe_frameworks_index_available ? "Available" : "Missing"}</strong>
            </div>
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

        {activePage === "ai-safety" ? <AiSafetyEvaluation /> : null}
        {activePage === "fda" ? <FdaAudit /> : null}
        {activePage === "privacy" ? <PrivacyReview /> : null}
        {activePage === "history" ? <AuditHistory /> : null}
      </main>
    </div>
  );
}
