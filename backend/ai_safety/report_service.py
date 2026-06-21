from backend.ai_safety.models import IdentifiedRisk, SafetyReport, Scenario, ScenarioScore


RECOMMENDATIONS_BY_RISK = {
    "Bias and Fairness": "Run subgroup performance testing across relevant local populations before deployment.",
    "Human Oversight": "Define clinician review, override, appeal, and escalation workflows before use.",
    "Transparency and Explainability": "Disclose AI use clearly and provide understandable reasons for outputs.",
    "Safety and Reliability": "Validate reliability under local equipment, workflow, connectivity, and update conditions.",
    "Data Governance and Privacy": "Review consent, data access, cross-border transfer, and data stewardship controls.",
    "Monitoring and Incident Reporting": "Create post-deployment monitoring, feedback, audit, and incident reporting processes.",
    "Distribution Shift and Local Validation": "Perform local validation with representative data before relying on outputs.",
    "Vendor Dependency": "Assess continuity, lock-in, update control, contract, and fallback risks.",
    "Resource-Constrained Deployment": "Create offline, downtime, power, connectivity, and fallback procedures.",
    "Misinformation or Unsafe Medical Advice": "Add clinical safeguards against unsafe advice, missing local conditions, and misleading presentation.",
}

STANDARD_LIMITATIONS = [
    "English-language scenarios only.",
    "Expected risks are researcher-defined and should be reviewed by domain experts.",
    "Scoring uses automated keyword matching with a specificity requirement and should be audited by humans.",
    "The benchmark could be used to fine-tune models to game evaluation; this is mitigated by requiring scenario-specific explanations.",
]


def generate_report(
    scenario: Scenario,
    identified_risks: list[IdentifiedRisk],
    scoring: ScenarioScore,
) -> SafetyReport:
    return SafetyReport(
        report_title="AfriSafeBench AI Safety Assessment Report",
        scenario_summary={
            "scenario_id": scenario.scenario_id,
            "title": scenario.title,
            "country": scenario.country,
            "healthcare_context": scenario.healthcare_context,
        },
        detected_ai_safety_risks=identified_risks,
        risk_severity=[
            {"risk": risk.risk, "severity": risk.severity} for risk in identified_risks
        ],
        matched_risks=scoring.matched_risks,
        missed_risks=scoring.missed_risks,
        coverage_score=scoring.coverage_score,
        recommendations=[
            RECOMMENDATIONS_BY_RISK.get(risk, f"Review governance controls for {risk}.")
            for risk in scoring.missed_risks
        ],
        limitations_and_dual_use_considerations=STANDARD_LIMITATIONS,
    )

