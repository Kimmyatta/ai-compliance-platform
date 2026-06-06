import { useEffect, useMemo, useState } from "react";
import { Database, FileUp, Play, RefreshCw } from "lucide-react";
import {
  createFdaDeviceJob,
  createFdaUploadJob,
  getFdaDevices,
  getFdaJob,
} from "../api/client";
import { RiskBadge } from "../components/RiskBadge";
import { SectionPanel } from "../components/SectionPanel";
import { StatusBadge } from "../components/StatusBadge";
import type {
  FdaAuditDimension,
  FdaAuditJobStatusResponse,
  FdaAuditResponse,
} from "../types/audit";
import { downloadJson, downloadText } from "../utils/download";

const ACTIVE_STATUSES = new Set(["queued", "running"]);

function formatSection(value: string | undefined) {
  if (!value) {
    return "N/A";
  }
  return value;
}

function buildFdaTextReport(result: FdaAuditResponse) {
  const lines = [
    "AI Compliance Platform - FDA AI Device Audit Report",
    `Filename: ${result.filename}`,
    "",
    "Run Summary:",
    `Total Dimensions: ${result.summary.total_dimensions}`,
    `Completed Dimensions: ${result.summary.completed_dimensions}`,
    `Failed Dimensions: ${result.summary.failed_dimensions}`,
    `Skipped Dimensions: ${result.summary.skipped_dimensions}`,
    "",
  ];

  for (const audit of result.audits) {
    lines.push(`Dimension: ${audit.dimension}`);
    lines.push(`Guidance: ${audit.guidance}`);
    lines.push(`Risk Level: ${audit.risk_level || "UNKNOWN"}`);
    lines.push(`Status: ${audit.status}`);
    lines.push("");
    lines.push("Audit Summary:");
    lines.push(audit.parsed.audit_summary || "N/A");
    lines.push("");
    lines.push("Principle Assessment:");
    lines.push(audit.parsed.principle_assessment || "N/A");
    lines.push("");
    lines.push("Guidance-Alignment Gaps:");
    lines.push(audit.parsed.guidance_alignment_gaps || "N/A");
    lines.push("");
    lines.push("Insufficient Public Disclosure:");
    lines.push(audit.parsed.insufficient_public_disclosure || "N/A");
    lines.push("");
    lines.push("Potential Regulatory Concerns:");
    lines.push(audit.parsed.potential_regulatory_concerns || "N/A");
    lines.push("");
    lines.push("Potential Violations:");
    lines.push(audit.parsed.potential_violations || "N/A");
    lines.push("");
    lines.push("Recommendations:");
    lines.push(audit.parsed.recommendations || "N/A");
    lines.push("");
    lines.push("Guidance Sources:");
    lines.push(audit.sources.length ? audit.sources.join("\n") : "N/A");
    lines.push("");
    lines.push("-----");
    lines.push("");
  }

  return lines.join("\n");
}

function AuditDimension({ audit }: { audit: FdaAuditDimension }) {
  return (
    <details className="audit-detail">
      <summary>
        <span>{audit.dimension}</span>
        <RiskBadge risk={audit.risk_level} />
      </summary>
      <div className="audit-detail__content">
        <div className="audit-grid">
          <div>
            <h3>Audit Summary</h3>
            <p>{formatSection(audit.parsed.audit_summary)}</p>
          </div>
          <div>
            <h3>Guidance</h3>
            <p>{audit.guidance}</p>
          </div>
        </div>
        <h3>Principle Assessment</h3>
        <pre>{formatSection(audit.parsed.principle_assessment)}</pre>
        <h3>Guidance Gaps</h3>
        <pre>{formatSection(audit.parsed.guidance_alignment_gaps)}</pre>
        <h3>Insufficient Public Disclosure</h3>
        <pre>{formatSection(audit.parsed.insufficient_public_disclosure)}</pre>
        <h3>Recommendations</h3>
        <pre>{formatSection(audit.parsed.recommendations)}</pre>
        {audit.sources.length ? (
          <>
            <h3>Guidance Sources</h3>
            <ul className="source-list">
              {audit.sources.map((source) => (
                <li key={source}>{source}</li>
              ))}
            </ul>
          </>
        ) : null}
      </div>
    </details>
  );
}

export function FdaAudit() {
  const [devices, setDevices] = useState<string[]>([]);
  const [selectedDevice, setSelectedDevice] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [job, setJob] = useState<FdaAuditJobStatusResponse | null>(null);
  const [loadingDevices, setLoadingDevices] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const activeJob = useMemo(
    () => job && ACTIVE_STATUSES.has(job.status),
    [job],
  );

  async function loadDevices() {
    setLoadingDevices(true);
    setError("");
    try {
      const response = await getFdaDevices();
      setDevices(response.devices);
      setSelectedDevice((current) => current || response.devices[0] || "");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load devices.");
    } finally {
      setLoadingDevices(false);
    }
  }

  async function refreshJob(jobId = job?.job_id) {
    if (!jobId) {
      return;
    }
    const response = await getFdaJob(jobId);
    setJob(response);
  }

  async function startExistingDeviceJob() {
    if (!selectedDevice) {
      setError("Select a cleaned FDA device file first.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const created = await createFdaDeviceJob(selectedDevice, { saveResult: true });
      const response = await getFdaJob(created.job_id);
      setJob(response);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not start FDA audit.");
    } finally {
      setSubmitting(false);
    }
  }

  async function startUploadJob() {
    if (!uploadFile) {
      setError("Choose a FDA submission PDF, DOCX, or TXT file first.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const created = await createFdaUploadJob(uploadFile);
      const response = await getFdaJob(created.job_id);
      setJob(response);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not upload FDA audit.");
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    void loadDevices();
  }, []);

  useEffect(() => {
    if (!activeJob || !job) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      void refreshJob(job.job_id);
    }, 3000);

    return () => window.clearInterval(intervalId);
  }, [activeJob, job?.job_id]);

  return (
    <div className="page-grid">
      <SectionPanel
        title="FDA AI Device Audit"
        description="Run an audit against the FDA AI guidance knowledge base and poll background job results."
        actions={
          <button className="icon-button" onClick={loadDevices} disabled={loadingDevices}>
            <RefreshCw size={16} />
            Refresh
          </button>
        }
      >
        <div className="two-column">
          <div className="control-block">
            <label htmlFor="device-select">Existing cleaned device</label>
            <select
              id="device-select"
              value={selectedDevice}
              onChange={(event) => setSelectedDevice(event.target.value)}
              disabled={loadingDevices || submitting}
            >
              {devices.map((device) => (
                <option value={device} key={device}>
                  {device}
                </option>
              ))}
            </select>
            <button onClick={startExistingDeviceJob} disabled={submitting || !selectedDevice}>
              <Database size={16} />
              Start Device Audit
            </button>
          </div>

          <div className="control-block">
            <label htmlFor="device-upload">Upload FDA submission</label>
            <input
              id="device-upload"
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
              disabled={submitting}
            />
            <button onClick={startUploadJob} disabled={submitting || !uploadFile}>
              <FileUp size={16} />
              Start Uploaded Audit
            </button>
          </div>
        </div>
        {error ? <div className="error-banner">{error}</div> : null}
      </SectionPanel>

      {job ? (
        <SectionPanel
          title="Audit Job"
          description={job.filename}
          actions={
            <div className="button-group">
              {job.result ? (
                <>
                  <button
                    className="icon-button"
                    onClick={() => downloadJson(`fda_audit_${job.result?.filename}`, job.result)}
                  >
                    Download JSON
                  </button>
                  <button
                    className="icon-button"
                    onClick={() =>
                      job.result
                        ? downloadText(
                            `fda_audit_${job.result.filename}`,
                            buildFdaTextReport(job.result),
                          )
                        : undefined
                    }
                  >
                    Download TXT
                  </button>
                </>
              ) : null}
              <button className="icon-button" onClick={() => void refreshJob()} disabled={submitting}>
                <Play size={16} />
                Check Status
              </button>
            </div>
          }
        >
          <div className="job-strip">
            <div>
              <span>Job ID</span>
              <strong>{job.job_id}</strong>
            </div>
            <div>
              <span>Status</span>
              <StatusBadge status={job.status} />
            </div>
            <div>
              <span>Updated</span>
              <strong>{new Date(job.updated_at).toLocaleString()}</strong>
            </div>
            <div>
              <span>Progress</span>
              <strong>{job.progress_percent}%</strong>
            </div>
          </div>

          <div className="progress-block">
            <div className="progress-block__labels">
              <span>{job.message ?? "Waiting for job updates"}</span>
              <strong>
                {job.completed_dimensions} of {job.total_dimensions || "?"} dimensions
              </strong>
            </div>
            <div className="progress-track">
              <div
                className="progress-track__bar"
                style={{ width: `${Math.min(Math.max(job.progress_percent, 0), 100)}%` }}
              />
            </div>
            {job.current_dimension ? (
              <p className="progress-block__dimension">{job.current_dimension}</p>
            ) : null}
          </div>

          {job.error ? <div className="error-banner">{job.error}</div> : null}

          {job.result ? (
            <div className="result-stack">
              <div className="summary-row">
                <div>
                  <span>Total Dimensions</span>
                  <strong>{job.result.summary.total_dimensions}</strong>
                </div>
                <div>
                  <span>Completed</span>
                  <strong>{job.result.summary.completed_dimensions}</strong>
                </div>
                <div>
                  <span>Failed</span>
                  <strong>{job.result.summary.failed_dimensions}</strong>
                </div>
                <div>
                  <span>Skipped</span>
                  <strong>{job.result.summary.skipped_dimensions}</strong>
                </div>
              </div>
              {job.result.audits.map((audit) => (
                <AuditDimension audit={audit} key={audit.dimension} />
              ))}
            </div>
          ) : (
            <div className="empty-state">The audit result will appear here when the job completes.</div>
          )}
        </SectionPanel>
      ) : null}
    </div>
  );
}
