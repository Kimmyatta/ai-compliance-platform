import { useEffect, useMemo, useRef, useState } from "react";
import { FileUp, Play, RefreshCw } from "lucide-react";
import {
  evaluateAiSafetyScenario,
  evaluateAiSafetyText,
  generateAiSafetyFrameworkGuidance,
  generateAiSafetyFrameworkGuidanceFromRescored,
  getAiSafetyModels,
  getAiSafetyRescoredReviews,
  getAiSafetyScenarios,
  runAiSafetyBenchmark,
  uploadAiSafetyDocument,
} from "../api/client";
import { RiskBadge } from "../components/RiskBadge";
import { SectionPanel } from "../components/SectionPanel";
import type {
  AiSafetyBenchmarkResponse,
  AiSafetyEvaluationResponse,
  AiSafetyFrameworkGuidedReportResponse,
  AiSafetyModel,
  AiSafetyRescoredReview,
  AiSafetyRisk,
  AiSafetyScenario,
} from "../types/audit";
import { downloadJson, downloadText } from "../utils/download";

function parseCategories(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function percent(value: number) {
  return `${Math.round(value)}%`;
}

function buildAiSafetyTextReport(result: AiSafetyEvaluationResponse) {
  const lines = [
    "AfriSafeBench - AI Safety Assessment Report",
    `Scenario ID: ${result.scenario_id ?? "N/A"}`,
    `Title: ${result.title}`,
    `Country: ${result.country || "N/A"}`,
    `Healthcare Context: ${result.healthcare_context || "N/A"}`,
    `Model: ${result.model}`,
    "",
    "Scenario Summary:",
    result.overall_assessment || "N/A",
    "",
    "Detected AI Safety Risks:",
  ];

  for (const risk of result.identified_risks) {
    lines.push(`- ${risk.risk} (${risk.severity})`);
    lines.push(`  Explanation: ${risk.explanation || "N/A"}`);
  }

  lines.push("");
  lines.push("Scoring:");
  lines.push(`Raw Score: ${result.scoring.raw_score}/${result.scoring.max_score}`);
  lines.push(`Coverage Score: ${percent(result.scoring.coverage_score)}`);
  lines.push(`Matched Risks: ${result.scoring.matched_risks.join(", ") || "None"}`);
  lines.push(`Missed Risks: ${result.scoring.missed_risks.join(", ") || "None"}`);
  lines.push(`Extra Risks: ${result.scoring.extra_risks.join(", ") || "None"}`);
  lines.push("");
  lines.push("Recommendations:");
  lines.push(result.report.recommendations.join("\n") || "N/A");
  lines.push("");
  lines.push("Limitations and Dual-Use Considerations:");
  lines.push(result.report.limitations_and_dual_use_considerations.join("\n") || "N/A");

  return lines.join("\n");
}

function RiskDetail({ risk }: { risk: AiSafetyRisk }) {
  return (
    <details className="audit-detail">
      <summary>
        <span>{risk.risk}</span>
        <RiskBadge risk={risk.severity} />
      </summary>
      <div className="audit-detail__content">
        <h3>Scenario-Specific Explanation</h3>
        <p>{risk.explanation || "N/A"}</p>
      </div>
    </details>
  );
}

function AggregateTable({
  title,
  rows,
}: {
  title: string;
  rows: Record<string, number>;
}) {
  return (
    <div className="table-wrap">
      <h3>{title}</h3>
      <table>
        <thead>
          <tr>
            <th>Group</th>
            <th>Coverage</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(rows).map(([key, value]) => (
            <tr key={key}>
              <td>{key}</td>
              <td>{percent(value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NestedAggregate({
  title,
  data,
}: {
  title: string;
  data: Record<string, Record<string, number>>;
}) {
  return (
    <div className="result-stack">
      <h3>{title}</h3>
      {Object.entries(data).map(([model, rows]) => (
        <AggregateTable title={model} rows={rows} key={model} />
      ))}
    </div>
  );
}

export function AiSafetyEvaluation() {
  const [scenarios, setScenarios] = useState<AiSafetyScenario[]>([]);
  const [models, setModels] = useState<AiSafetyModel[]>([]);
  const [rescoredReviews, setRescoredReviews] = useState<AiSafetyRescoredReview[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState("");
  const [selectedModel, setSelectedModel] = useState("llama-3.3-70b-versatile");
  const [selectedRescoredReviewId, setSelectedRescoredReviewId] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [customTitle, setCustomTitle] = useState("");
  const [customCountry, setCustomCountry] = useState("");
  const [customText, setCustomText] = useState("");
  const [expectedCategories, setExpectedCategories] = useState("");
  const [result, setResult] = useState<AiSafetyEvaluationResponse | null>(null);
  const [frameworkGuidance, setFrameworkGuidance] =
    useState<AiSafetyFrameworkGuidedReportResponse | null>(null);
  const [benchmark, setBenchmark] = useState<AiSafetyBenchmarkResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [benchmarkSubmitting, setBenchmarkSubmitting] = useState(false);
  const [frameworkSubmitting, setFrameworkSubmitting] = useState(false);
  const [error, setError] = useState("");
  const benchmarkInFlightRef = useRef(false);

  const selectedScenario = useMemo(
    () => scenarios.find((scenario) => scenario.scenario_id === selectedScenarioId),
    [scenarios, selectedScenarioId],
  );

  async function loadReferenceData() {
    setLoading(true);
    setError("");
    try {
      const [scenarioResponse, modelResponse] = await Promise.all([
        getAiSafetyScenarios(),
        getAiSafetyModels(),
      ]);
      setScenarios(scenarioResponse.scenarios);
      setModels(modelResponse.models);
      setSelectedScenarioId((current) => current || scenarioResponse.scenarios[0]?.scenario_id || "");
      setSelectedModel((current) => current || modelResponse.models[0]?.id || "llama-3.3-70b-versatile");
      const reviewResponse = await getAiSafetyRescoredReviews();
      setRescoredReviews(reviewResponse.reviews);
      setSelectedRescoredReviewId(
        (current) => current || reviewResponse.reviews[0]?.review_id || "",
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load AfriSafeBench reference data.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function runScenarioEvaluation() {
    if (!selectedScenarioId) {
      setError("Select an AfriSafeBench scenario first.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const response = await evaluateAiSafetyScenario(selectedScenarioId, selectedModel);
      setResult(response);
      setFrameworkGuidance(null);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not run AI safety evaluation.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function runSelectedModelBenchmark() {
    if (benchmarkInFlightRef.current) {
      return;
    }
    benchmarkInFlightRef.current = true;
    setBenchmarkSubmitting(true);
    setError("");
    try {
      const response = await runAiSafetyBenchmark([selectedModel]);
      setBenchmark(response);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not run the selected-model benchmark.",
      );
    } finally {
      benchmarkInFlightRef.current = false;
      setBenchmarkSubmitting(false);
    }
  }

  async function runCustomTextEvaluation() {
    if (!customText.trim()) {
      setError("Paste a deployment scenario or document excerpt first.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const response = await evaluateAiSafetyText({
        title: customTitle || "Custom African healthcare AI deployment scenario",
        country: customCountry,
        text: customText,
        expected_risk_categories: parseCategories(expectedCategories),
        model: selectedModel,
      });
      setResult(response);
      setFrameworkGuidance(null);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not evaluate the custom scenario.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function runUploadEvaluation() {
    if (!uploadFile) {
      setError("Choose a document first.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const response = await uploadAiSafetyDocument(uploadFile, {
        title: customTitle,
        country: customCountry,
        expectedRiskCategories: parseCategories(expectedCategories),
        model: selectedModel,
      });
      setResult(response);
      setFrameworkGuidance(null);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not evaluate the uploaded document.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function runFrameworkGuidance() {
    if (!result?.scenario_id) {
      setError("Framework-guided recommendations are available for benchmark scenarios.");
      return;
    }
    setFrameworkSubmitting(true);
    setError("");
    try {
      const response = await generateAiSafetyFrameworkGuidance(result.scenario_id, {
        model: selectedModel,
        detected_risks: result.identified_risks,
        missed_risks: result.scoring.missed_risks,
        k: 6,
      });
      setFrameworkGuidance(response);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not generate framework-guided recommendations.",
      );
    } finally {
      setFrameworkSubmitting(false);
    }
  }

  async function runRescoredFrameworkGuidance() {
    const selectedReview = rescoredReviews.find(
      (review) => review.review_id === selectedRescoredReviewId,
    );
    if (!selectedReview) {
      setError("Choose a corrected review first.");
      return;
    }
    setFrameworkSubmitting(true);
    setError("");
    try {
      const response = await generateAiSafetyFrameworkGuidanceFromRescored(
        selectedReview.scenario_id,
        {
          source_model: selectedReview.model,
          guidance_model: selectedModel,
          k: 6,
        },
      );
      setFrameworkGuidance(response);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not generate framework guidance from the corrected review.",
      );
    } finally {
      setFrameworkSubmitting(false);
    }
  }

  useEffect(() => {
    void loadReferenceData();
  }, []);

  return (
    <div className="page-grid">
      <SectionPanel
        title="AfriSafeBench Scenario Evaluation"
        description="Run the exact benchmark prompt and 0/1/2 rubric against African healthcare AI deployment scenarios."
        actions={
          <button className="icon-button" onClick={loadReferenceData} disabled={loading}>
            <RefreshCw size={16} />
            Refresh
          </button>
        }
      >
        <div className="two-column">
          <div className="control-block">
            <label htmlFor="scenario-select">Scenario browser</label>
            <select
              id="scenario-select"
              value={selectedScenarioId}
              onChange={(event) => setSelectedScenarioId(event.target.value)}
              disabled={loading || submitting}
            >
              {scenarios.map((scenario) => (
                <option value={scenario.scenario_id} key={scenario.scenario_id}>
                  {scenario.scenario_id} - {scenario.title}
                </option>
              ))}
            </select>
            <label htmlFor="model-select">Groq model</label>
            <select
              id="model-select"
              value={selectedModel}
              onChange={(event) => setSelectedModel(event.target.value)}
              disabled={submitting}
            >
              {models.map((model) => (
                <option value={model.id} key={model.id}>
                  {model.label}
                </option>
              ))}
            </select>
            <button onClick={runScenarioEvaluation} disabled={submitting || !selectedScenarioId}>
              <Play size={16} />
              Run Single Scenario
            </button>
            <button
              className="button-secondary"
              onClick={runSelectedModelBenchmark}
              disabled={benchmarkSubmitting || !selectedModel}
            >
              <Play size={16} />
              {benchmarkSubmitting ? "Running Benchmark" : "Run 25 With Selected Model"}
            </button>
          </div>

          <div className="control-block">
            <label htmlFor="document-upload">Upload deployment document</label>
            <input
              id="document-upload"
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
              disabled={submitting}
            />
            <label htmlFor="custom-title">Document title</label>
            <input
              id="custom-title"
              value={customTitle}
              onChange={(event) => setCustomTitle(event.target.value)}
              placeholder="Maternal health assistant rollout memo"
            />
            <label htmlFor="custom-country">Country</label>
            <input
              id="custom-country"
              value={customCountry}
              onChange={(event) => setCustomCountry(event.target.value)}
              placeholder="Kenya"
            />
            <button onClick={runUploadEvaluation} disabled={submitting || !uploadFile}>
              <FileUp size={16} />
              Evaluate Upload
            </button>
          </div>
        </div>

        <div className="control-block custom-scenario-block">
          <label htmlFor="rescored-review-select">Corrected review for framework guidance</label>
          <select
            id="rescored-review-select"
            value={selectedRescoredReviewId}
            onChange={(event) => setSelectedRescoredReviewId(event.target.value)}
            disabled={loading || frameworkSubmitting || !rescoredReviews.length}
          >
            {rescoredReviews.map((review) => (
              <option value={review.review_id} key={review.review_id}>
                {review.scenario_id} - {review.model} - {percent(review.coverage_score)}
              </option>
            ))}
          </select>
          <button
            className="button-secondary"
            onClick={runRescoredFrameworkGuidance}
            disabled={frameworkSubmitting || !selectedRescoredReviewId}
          >
            <Play size={16} />
            {frameworkSubmitting ? "Generating" : "Framework Guidance From Corrected Review"}
          </button>
        </div>

        <div className="control-block custom-scenario-block">
          <label htmlFor="expected-categories">Expected risk categories for uploaded/custom scoring</label>
          <input
            id="expected-categories"
            value={expectedCategories}
            onChange={(event) => setExpectedCategories(event.target.value)}
            placeholder="Bias and Fairness, Human Oversight"
          />
          <label htmlFor="custom-scenario">Custom scenario text</label>
          <textarea
            id="custom-scenario"
            value={customText}
            onChange={(event) => setCustomText(event.target.value)}
            placeholder="Paste an African healthcare AI deployment scenario or governance document excerpt."
          />
          <button
            className="button-secondary"
            onClick={runCustomTextEvaluation}
            disabled={submitting || !customText.trim()}
          >
            <Play size={16} />
            Evaluate Text
          </button>
        </div>

        {selectedScenario ? (
          <div className="scenario-preview">
            <div>
              <span>Country</span>
              <strong>{selectedScenario.country}</strong>
            </div>
            <div>
              <span>Healthcare Context</span>
              <strong>{selectedScenario.healthcare_context || "N/A"}</strong>
            </div>
            <div>
              <span>Benchmark Severity</span>
              <RiskBadge risk={selectedScenario.risk_severity || selectedScenario.severity} />
            </div>
            <p>{selectedScenario.scenario_description}</p>
          </div>
        ) : null}

        {error ? <div className="error-banner">{error}</div> : null}
      </SectionPanel>

      {result ? (
        <SectionPanel
          title="AI Safety Assessment Report"
          description={result.title}
          actions={
            <div className="button-group">
              <button
                className="icon-button"
                onClick={runFrameworkGuidance}
                disabled={frameworkSubmitting || !result.scenario_id}
              >
                <Play size={16} />
                {frameworkSubmitting ? "Generating" : "Framework Guidance"}
              </button>
              <button
                className="icon-button"
                onClick={() => downloadJson(`afrisafebench_${result.scenario_id || "document"}`, result)}
              >
                Download JSON
              </button>
              <button
                className="icon-button"
                onClick={() =>
                  downloadText(
                    `afrisafebench_${result.scenario_id || "document"}`,
                    buildAiSafetyTextReport(result),
                  )
                }
              >
                Download TXT
              </button>
            </div>
          }
        >
          <div className="job-strip">
            <div>
              <span>Model</span>
              <strong>{result.model}</strong>
            </div>
            <div>
              <span>Score</span>
              <strong>
                {result.scoring.raw_score}/{result.scoring.max_score}
              </strong>
            </div>
            <div>
              <span>Coverage</span>
              <strong>{percent(result.scoring.coverage_score)}</strong>
            </div>
            <div>
              <span>Expected Risks</span>
              <strong>{result.expected_risk_categories.length}</strong>
            </div>
          </div>

          <div className="audit-grid">
            <div>
              <h3>Scenario Summary</h3>
              <p>{result.overall_assessment || "N/A"}</p>
            </div>
            <div>
              <h3>Missed Risks</h3>
              <p>{result.scoring.missed_risks.join(", ") || "None"}</p>
            </div>
          </div>

          <div className="summary-row">
            <div>
              <span>Matched Risks</span>
              <strong>{result.scoring.matched_risks.length}</strong>
            </div>
            <div>
              <span>Missed Risks</span>
              <strong>{result.scoring.missed_risks.length}</strong>
            </div>
            <div>
              <span>Extra Risks</span>
              <strong>{result.scoring.extra_risks.length}</strong>
            </div>
            <div>
              <span>Detected Risks</span>
              <strong>{result.identified_risks.length}</strong>
            </div>
          </div>

          <div className="result-stack">
            {result.identified_risks.map((risk, index) => (
              <RiskDetail risk={risk} key={`${risk.risk}-${index}`} />
            ))}
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Expected Risk Category</th>
                  <th>Score</th>
                  <th>Matched Output</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(result.scoring.scores_by_category).map(([category, score]) => (
                  <tr key={category}>
                    <td>{category}</td>
                    <td>{score.score}</td>
                    <td>{score.matched_risk || "Missed"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="audit-detail__content limitations-block">
            <h3>Recommendations</h3>
            <ul className="source-list">
              {result.report.recommendations.length ? (
                result.report.recommendations.map((item) => <li key={item}>{item}</li>)
              ) : (
                <li>No missed-risk recommendations generated.</li>
              )}
            </ul>
            <h3>Limitations and Dual-Use Considerations</h3>
            <ul className="source-list">
              {result.report.limitations_and_dual_use_considerations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </SectionPanel>
      ) : null}

      {frameworkGuidance ? (
        <SectionPanel
          title="Framework-Guided Recommendations"
          description={`${frameworkGuidance.title} - ${frameworkGuidance.model}`}
          actions={
            <button
              className="icon-button"
              onClick={() =>
                downloadJson(
                  `afrisafebench_framework_guidance_${frameworkGuidance.scenario_id || "document"}`,
                  frameworkGuidance,
                )
              }
            >
              Download JSON
            </button>
          }
        >
          <div className="audit-grid">
            <div>
              <h3>Framework Summary</h3>
              <p>{frameworkGuidance.framework_summary || "N/A"}</p>
            </div>
            <div>
              <h3>Country Context</h3>
              <p>{frameworkGuidance.country || "N/A"}</p>
            </div>
          </div>

          <div className="result-stack">
            {frameworkGuidance.recommendations.map((item, index) => (
              <details className="audit-detail" open={index === 0} key={`${item.recommendation}-${index}`}>
                <summary>
                  <span>{item.recommendation}</span>
                  <RiskBadge risk={item.priority} />
                </summary>
                <div className="audit-detail__content">
                  <h3>Rationale</h3>
                  <p>{item.rationale || "N/A"}</p>
                  <h3>Related Risks</h3>
                  <p>{item.related_risks.join(", ") || "N/A"}</p>
                  <h3>Framework Sources</h3>
                  <p>{item.framework_sources.join(", ") || "N/A"}</p>
                </div>
              </details>
            ))}
          </div>

          <div className="audit-detail__content limitations-block">
            <h3>Governance Checklist</h3>
            <ul className="source-list">
              {frameworkGuidance.governance_checklist.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <h3>Retrieved Framework Sources</h3>
            <ul className="source-list">
              {frameworkGuidance.sources.map((source, index) => (
                <li key={`${source.source}-${index}`}>
                  <strong>{source.source}</strong>: {source.excerpt}
                </li>
              ))}
            </ul>
            <h3>Limitations and Dual-Use Considerations</h3>
            <ul className="source-list">
              {frameworkGuidance.limitations_and_dual_use_considerations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </SectionPanel>
      ) : null}

      {benchmark ? (
        <SectionPanel
          title="Full Benchmark Results"
          description={`${benchmark.scenario_count} scenarios x ${benchmark.models.length} models = ${benchmark.evaluation_count} evaluations`}
          actions={
            <button
              className="icon-button"
              onClick={() => downloadJson("afrisafebench_full_benchmark", benchmark)}
            >
              Download JSON
            </button>
          }
        >
          <div className="summary-row">
            {Object.entries(benchmark.aggregate.mean_coverage_score_by_model).map(
              ([model, score]) => (
                <div key={model}>
                  <span>{model}</span>
                  <strong>{percent(score)}</strong>
                </div>
              ),
            )}
          </div>

          <NestedAggregate
            title="Coverage By Risk Category"
            data={benchmark.aggregate.coverage_score_by_risk_category}
          />
          <NestedAggregate
            title="Coverage By Country"
            data={benchmark.aggregate.coverage_score_by_country}
          />
          <NestedAggregate
            title="Coverage By Severity"
            data={benchmark.aggregate.coverage_score_by_severity}
          />
        </SectionPanel>
      ) : null}
    </div>
  );
}
