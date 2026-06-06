import { useState } from "react";
import { FileText, Upload } from "lucide-react";
import { uploadPrivacyReview } from "../api/client";
import { RiskBadge } from "../components/RiskBadge";
import { SectionPanel } from "../components/SectionPanel";
import type { PrivacyReviewResponse } from "../types/audit";
import { downloadJson, downloadText } from "../utils/download";

function buildPrivacyTextReport(result: PrivacyReviewResponse) {
  const lines = [
    "AI Compliance Platform - Privacy Review Report",
    `Filename: ${result.filename}`,
    "",
  ];

  for (const review of result.reviews) {
    lines.push(`Regulation: ${review.regulation}`);
    lines.push(`Risk Level: ${review.parsed.risk_level || "UNKNOWN"}`);
    lines.push("");
    lines.push("Compliance Summary:");
    lines.push(review.parsed.compliance_summary || "N/A");
    lines.push("");
    lines.push("Compliant Sections:");
    lines.push(review.parsed.compliant_sections || "N/A");
    lines.push("");
    lines.push("Violations Found:");
    lines.push(review.parsed.violations || "N/A");
    lines.push("");
    lines.push("Missing Requirements:");
    lines.push(review.parsed.missing_requirements || "N/A");
    lines.push("");
    lines.push("Recommendations:");
    lines.push(review.parsed.recommendations || "N/A");
    lines.push("");
    lines.push("-----");
    lines.push("");
  }

  return lines.join("\n");
}

export function PrivacyReview() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<PrivacyReviewResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function runReview() {
    if (!file) {
      setError("Choose a privacy policy, privacy notice, DOCX, PDF, or TXT file first.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const response = await uploadPrivacyReview(file);
      setResult(response);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not run privacy review.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-grid">
      <SectionPanel
        title="Privacy Policy Review"
        description="Upload a privacy policy or notice and review it against HIPAA, CCPA, and HITECH."
      >
        <div className="control-block control-block--wide">
          <label htmlFor="privacy-upload">Company privacy document</label>
          <input
            id="privacy-upload"
            type="file"
            accept=".pdf,.docx,.txt"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            disabled={submitting}
          />
          <button onClick={runReview} disabled={submitting || !file}>
            <Upload size={16} />
            Run Privacy Review
          </button>
        </div>
        {error ? <div className="error-banner">{error}</div> : null}
      </SectionPanel>

      <SectionPanel
        title="Privacy Review Results"
        description={result?.filename ?? "No review has been run yet."}
        actions={
          result ? (
            <div className="button-group">
              <button
                className="icon-button"
                onClick={() => downloadJson(`privacy_review_${result.filename}`, result)}
              >
                Download JSON
              </button>
              <button
                className="icon-button"
                onClick={() =>
                  downloadText(
                    `privacy_review_${result.filename}`,
                    buildPrivacyTextReport(result),
                  )
                }
              >
                Download TXT
              </button>
            </div>
          ) : null
        }
      >
        {result ? (
          <div className="result-stack">
            {result.reviews.map((review) => (
              <details className="audit-detail" key={review.regulation}>
                <summary>
                  <span>{review.regulation}</span>
                  <RiskBadge risk={review.parsed.risk_level ?? "UNKNOWN"} />
                </summary>
                <div className="audit-detail__content">
                  <h3>Compliance Summary</h3>
                  <p>{review.parsed.compliance_summary || "N/A"}</p>
                  <h3>Compliant Sections</h3>
                  <pre>{review.parsed.compliant_sections || "N/A"}</pre>
                  <h3>Violations Found</h3>
                  <pre>{review.parsed.violations || "N/A"}</pre>
                  <h3>Missing Requirements</h3>
                  <pre>{review.parsed.missing_requirements || "N/A"}</pre>
                  <h3>Recommendations</h3>
                  <pre>{review.parsed.recommendations || "N/A"}</pre>
                </div>
              </details>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <FileText size={22} />
            Results from HIPAA, CCPA, and HITECH will appear here.
          </div>
        )}
      </SectionPanel>
    </div>
  );
}
