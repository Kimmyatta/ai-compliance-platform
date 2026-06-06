import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { getFdaJobs } from "../api/client";
import { SectionPanel } from "../components/SectionPanel";
import { StatusBadge } from "../components/StatusBadge";
import type { FdaAuditJobStatusResponse } from "../types/audit";

export function AuditHistory() {
  const [jobs, setJobs] = useState<FdaAuditJobStatusResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadJobs() {
    setLoading(true);
    setError("");
    try {
      const response = await getFdaJobs();
      setJobs(response.jobs);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load jobs.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadJobs();
  }, []);

  return (
    <SectionPanel
      title="FDA Audit History"
      description="Local in-memory jobs from the currently running FastAPI server."
      actions={
        <button className="icon-button" onClick={loadJobs} disabled={loading}>
          <RefreshCw size={16} />
          Refresh
        </button>
      }
    >
      {error ? <div className="error-banner">{error}</div> : null}
      {jobs.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Filename</th>
                <th>Job ID</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.job_id}>
                  <td>
                    <StatusBadge status={job.status} />
                  </td>
                  <td>{job.filename}</td>
                  <td className="mono">{job.job_id}</td>
                  <td>{new Date(job.updated_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">No FDA audit jobs are currently stored in this server session.</div>
      )}
    </SectionPanel>
  );
}
