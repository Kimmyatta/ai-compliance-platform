# AfriSafeBench: Evaluating LLM Recognition of AI Safety and Governance Risks in African Healthcare AI Deployments

## Abstract

AfriSafeBench is an evaluation benchmark and governance-support tool for assessing whether large language models can identify AI safety and governance risks in African healthcare AI deployment scenarios. I created 25 scenario-based test cases across seven African countries and ten risk categories, including bias, human oversight, local validation, data governance, vendor dependency, resource-constrained deployment, and unsafe medical advice. I evaluated three Groq-accessible models over 75 total evaluations using a 0/1/2 scoring rubric with human-audited rescoring flags for semantic matches. The best overall mean coverage was `openai/gpt-oss-20b` at 72.00%, followed by `llama-3.1-8b-instant` at 70.67% and `llama-3.3-70b-versatile` at 68.00%. AfriSafeBench also includes a framework-guided report mode that retrieves relevant guidance from WHO, NIST, UNESCO, OECD, and African Union documents to generate governance recommendations for corrected benchmark reviews.

## Authors and Affiliations

Author: Kimberly Atta-Peters  
Affiliation: University of St. Thomas, Minnesota

## Track and Sub-Track

Hackathon track: Open Track  
Regional focus: Africa / Global South healthcare AI deployment  
Project type: Evaluation + Tool

## 1. Introduction

Healthcare AI systems are increasingly being deployed in settings where clinical infrastructure, data availability, language, disease burden, procurement conditions, and regulatory capacity differ from the environments in which many AI systems are developed and validated. In African healthcare contexts, an AI model may be trained on non-local data, deployed through fragile connectivity, used by under-resourced clinical teams, or governed through vendor contracts that limit transparency and local control.

These risks matter for AI safety because failures may not appear only as technical errors. They may appear as biased triage, overreliance on automated outputs, failure to validate tools locally, unclear accountability, unsafe medical advice, weak incident reporting, or vendor dependency that undermines continuity of care.

AfriSafeBench addresses the question:

```text
Can LLMs identify AI safety and governance risks in African healthcare AI deployment scenarios?
```

The project contributes both an evaluation benchmark and a practical tool. The benchmark measures whether models detect expected risk categories. The tool/report mode uses recognized AI governance frameworks to generate recommendations after risks are identified or missed.

## 2. Related Work

AfriSafeBench builds on several lines of work:

- AI risk management and governance frameworks, including the NIST AI Risk Management Framework, WHO guidance on AI for health, UNESCO's Recommendation on the Ethics of AI, OECD AI Principles, and the African Union Continental AI Strategy.
- Scenario-based AI safety evaluation, where models are tested on realistic deployment cases rather than abstract definitions.
- LLM-as-reviewer workflows, where language models assist in compliance, risk review, and governance documentation.
- Retrieval-augmented generation, where framework documents are chunked, embedded, retrieved, and used to ground model outputs.

The project differs from generic compliance tools by centering African healthcare deployment conditions. It also differs from a pure chatbot by producing structured benchmark scores, model comparisons, missed-risk analysis, and framework-grounded recommendations.

## 3. Methodology

### 3.1 Scenario Dataset

I created a benchmark dataset of 25 African healthcare AI deployment scenarios. The scenarios cover seven countries:

- Ghana
- Kenya
- Nigeria
- South Africa
- Rwanda
- Uganda
- Tanzania

Each scenario includes:

- scenario ID
- title
- country
- healthcare context
- deployment description
- expected risk categories
- severity
- researcher-defined explanation

The dataset is stored at:

```text
data/afrisafebench_scenarios.json
```

### 3.2 Risk Categories

The benchmark uses ten AI safety and governance risk categories:

- Bias and Fairness
- Human Oversight
- Transparency and Explainability
- Safety and Reliability
- Data Governance and Privacy
- Monitoring and Incident Reporting
- Distribution Shift and Local Validation
- Vendor Dependency
- Resource-Constrained Deployment
- Misinformation or Unsafe Medical Advice

These categories were grounded in the selected governance frameworks but written in practical language suitable for scenario review.

### 3.3 Models Evaluated

I evaluated three Groq-accessible models:

| Model | Role in comparison |
| --- | --- |
| `llama-3.1-8b-instant` | smaller, faster Llama baseline |
| `llama-3.3-70b-versatile` | larger Llama model |
| `openai/gpt-oss-20b` | different model family |

Each model reviewed all 25 scenarios, giving 75 total evaluations.

### 3.4 Evaluation Prompt

Each model received the scenario text and was asked to identify AI safety and governance risks, explain why each risk was present in the scenario, assign severity, and return valid JSON. The prompt required scenario-specific evidence and discouraged generic statements.

The expected model output schema was:

```json
{
  "identified_risks": [
    {
      "risk": "brief risk label",
      "explanation": "specific explanation referencing scenario details",
      "severity": "Low | Medium | High"
    }
  ],
  "overall_assessment": "2-3 sentence summary"
}
```

### 3.5 Scoring Rubric

For each scenario, expected risk categories were compared against model-detected risks. Each expected category was scored:

| Score | Meaning |
| ---: | --- |
| 2 | Risk identified with scenario-specific explanation |
| 1 | Risk identified but explanation generic or vague |
| 0 | Risk missed or incorrectly identified |

Outputs include matched risks, missed risks, extra risks, raw score, max score, coverage score, and category-level scores.

Because models often use different wording for the same concept, rescoring includes human-review flags. If a category changed from missed to matched during rescoring, the result is marked with `needs_human_review`, `review_changed_categories`, and `review_notes`. This preserves transparency rather than silently inflating scores.

### 3.6 Framework-Guided Tool Mode

AfriSafeBench also includes a tool/report mode. Framework PDFs are stored, extracted, cleaned, chunked, embedded, and indexed with FAISS. The current framework corpus includes:

- NIST AI Risk Management Framework
- WHO Ethics and Governance of AI for Health
- UNESCO Recommendation on the Ethics of AI
- OECD AI Principles
- African Union Continental AI Strategy

The tool mode can generate recommendations from either a live scenario review or a corrected/rescored benchmark review. It retrieves relevant framework chunks and asks the LLM to produce:

- framework summary
- prioritized recommendations
- governance checklist
- limitations and dual-use considerations
- retrieved framework sources

This separates evaluation from assistance: benchmark mode measures model performance, while tool/report mode helps a human reviewer respond to the identified risks.

## 4. Results

### 4.1 Overall Model Performance

The completed benchmark contains:

```text
25 scenarios x 3 models = 75 evaluations
```

Mean coverage score by model:

| Model | Mean Coverage |
| --- | ---: |
| `openai/gpt-oss-20b` | 72.00% |
| `llama-3.1-8b-instant` | 70.67% |
| `llama-3.3-70b-versatile` | 68.00% |

The models performed similarly overall. The strongest mean score came from `openai/gpt-oss-20b`, but the margin was small enough that no model should be treated as reliably complete across all risk types.

### 4.2 Category-Level Findings

Some risk categories were more consistently recognized than others.

Average coverage and miss rate by category across the three evaluated models:

| Risk Category | Avg. Coverage | Approx. Miss Rate |
| --- | ---: | ---: |
| Bias and Fairness | 95.83% | 4.17% |
| Data Governance and Privacy | 86.67% | 13.33% |
| Safety and Reliability | 83.33% | 16.67% |
| Transparency and Explainability | 74.08% | 25.92% |
| Misinformation or Unsafe Medical Advice | 73.33% | 26.67% |
| Human Oversight | 72.73% | 27.27% |
| Distribution Shift and Local Validation | 63.33% | 36.67% |
| Monitoring and Incident Reporting | 59.26% | 40.74% |
| Vendor Dependency | 58.33% | 41.67% |
| Resource-Constrained Deployment | 27.78% | 72.22% |

This suggests that models may be better at identifying familiar AI ethics concepts, such as bias and privacy, than deployment-specific governance risks, such as sustainability, infrastructure fragility, post-deployment monitoring, and local validation.

### 4.3 Human-Audited Rescoring Finding

One important methodological finding is that 40 of 75 evaluations, or 53.3%, required human-review flags after rescoring. This did not mean the models were always wrong; often the model identified a valid risk using different wording than the automated scorer expected. For example, a model might describe "vendor demonstration bias" rather than explicitly saying "Bias and Fairness."

This finding is important because it shows that fully automated benchmark scoring can undercount valid model performance when risk categories are semantically correct but phrased differently. AfriSafeBench therefore records `needs_human_review`, `review_changed_categories`, and `review_notes` rather than silently changing the scores. This makes the benchmark more transparent and highlights a broader challenge for AI safety evaluation: scoring systems need to account for semantic variation without over-crediting vague answers.

### 4.4 Framework-Guided Report Mode

To demonstrate the framework-guided report mode, I ran the tool on a representative sample of five scenarios across all three models, generating 15 governance reports with an average of 3.8 recommendations per report. These reports had a priority distribution of 35 High-priority recommendations, 21 Medium-priority recommendations, and 1 Low-priority recommendation.

Initial framework-guided reports produced recommendations such as:

- validate the AI system using local patient samples
- monitor for bias and errors after deployment
- train health workers to interpret model outputs
- establish review processes for borderline or contested decisions
- document vendor update and accountability procedures

The retrieved sources were primarily WHO AI for Health excerpts and African Union Continental AI Strategy excerpts, showing that the tool can connect scenario-specific risks to recognized governance guidance.

### 4.5 Notable Patterns

**Hardest scenario: Community Health Worker Support Tool in Uganda (Scenario 017)**

The lowest-performing scenario across all three models was Scenario 017, with an average coverage score of 11.11%. Two of the three models scored 0%. The expected risks — Vendor Dependency, Resource-Constrained Deployment, and Human Oversight — were present as subtle structural risks rather than explicit clinical failures. The scenario describes a tool funded by a donor whose cycle ends in eight months with no confirmed maintenance plan, and health workers who report they would not know how to conduct assessments without it. Models consistently described surface-level concerns such as data insecurity and clinical content obsolescence without identifying the underlying sustainability and dependency risks. This suggests models struggle most when risks are embedded in governance and funding structures rather than clinical decision-making workflows.

**Biggest model divergence: Maternal Health Risk Scoring in Kenya (Scenario 002)**

Scenario 002 showed the greatest model divergence: a 100 percentage point spread. `llama-3.1-8b-instant` scored 100%, `llama-3.3-70b-versatile` scored 66.67%, and `openai/gpt-oss-20b` scored 0%. All three received identical scenario text and prompts. The 0% result was not a parsing failure but a complete mismatch between identified and expected risk categories. A second major divergence occurred in Scenario 025, AI Birth Asphyxia Detection in Rwanda, where `llama-3.3-70b-versatile` scored 0% while `openai/gpt-oss-20b` scored 100%. These divergences suggest model-specific reasoning patterns influence risk identification independent of model size.

**Severity finding: no meaningful difference**

High-severity scenarios averaged 69.94% coverage while Medium-severity scenarios averaged 70.83%, less than one percentage point difference. Models did not apply greater scrutiny to scenarios where patient harm risk was highest. For deployment in real-world healthcare AI governance, this is a significant limitation.

**Healthcare context finding: maternal health is the hardest context**

Malaria diagnosis and tuberculosis screening scenarios averaged 100% coverage, while maternal health scenarios averaged only 41.67%, the lowest of any context. Maternal health scenarios involve more complex multi-stakeholder risk profiles including community health worker dependency, rural-urban data gaps, and resource continuity risks. The gap between infectious disease contexts, where risks are technically explicit, and maternal health contexts, where risks are systemic and governance-oriented, may reflect a broader pattern in how LLMs reason about structural versus clinical risk.

**Country finding: Kenya had the lowest average coverage**

Kenya scenarios averaged 63.89%, the lowest of any country, spanning maternal health, medical imaging, clinical decision support, and telemedicine: a diverse set with complex overlapping risk profiles. Ghana averaged the highest at 81.48%. Country-level differences should be interpreted cautiously given the small number of scenarios per country, but the pattern warrants attention in future benchmark expansions.

## 5. Discussion

AfriSafeBench shows that LLMs can identify many AI safety risks in African healthcare scenarios, but performance is uneven. The models often detected obvious privacy, bias, and clinical safety concerns. They were less reliable on risks that require reasoning about local deployment conditions, such as infrastructure constraints, vendor continuity, local validation, and post-deployment monitoring.

This matters because those weaker categories are central to real-world safety in African healthcare settings. A model that can describe bias in general terms but misses local validation, resource constraints, or incident reporting may still be unsafe as a governance assistant.

The framework-guided report mode helps address this by using the benchmark result as input to a governance workflow. If a model misses a risk, that missed category can still be passed into the framework-guided report so the final recommendation does not ignore it. This makes the system useful both as an evaluation artifact and as a practical review assistant.

## 6. Limitations and Dual-Use Considerations

### Limitations

- The dataset contains 25 scenarios, which is useful for a hackathon prototype but not enough for broad model capability claims.
- Scenarios are written in English and may not capture local-language clinical communication patterns.
- Expected risks are researcher-defined and should be reviewed by African healthcare, legal, and policy experts.
- Automated scoring depends on keyword and semantic matching; even with human-review flags, scoring can miss valid paraphrases or over-credit weak matches.
- The framework-guided report is not country-specific legal advice.
- The model evaluations used available Groq models and may change as model versions, APIs, and rate limits change.

### Dual-Use Considerations

The benchmark could be misused to train models to game the expected categories without improving real safety reasoning. It could also be used to produce superficial governance reports that appear authoritative but lack expert review.

Mitigations include:

- requiring scenario-specific explanations rather than category labels alone
- retaining missed-risk outputs
- adding human-review flags when rescoring changes results
- showing retrieved framework sources
- clearly stating that framework guidance supports, but does not replace, clinical, legal, or policy expertise

### Future Improvements

With more time, the project would:

- expand the dataset beyond 25 scenarios
- include local-language and multilingual scenarios
- validate expected risks with domain experts
- add inter-rater review for scoring
- compare additional local and open-weight models
- generate aggregate visual dashboards
- improve framework retrieval diversity across WHO, NIST, UNESCO, OECD, and AU sources
- add country-specific legal and regulatory context where appropriate

## 7. Conclusion

AfriSafeBench provides a practical evaluation benchmark and tool for African healthcare AI governance. The benchmark shows that LLMs can identify many risks but remain uneven on deployment-specific governance concerns. The tool/report mode helps convert risk detection into framework-guided recommendations, making the project useful for both model evaluation and practical AI safety review.

The main contribution is a reusable workflow:

```text
African healthcare deployment scenario
-> LLM risk identification
-> scored benchmark result
-> human-audited rescoring flags
-> framework-guided governance recommendations
```

This workflow can be extended into a larger benchmark for evaluating whether AI systems understand safety risks in Global South healthcare contexts.

## References

1. National Institute of Standards and Technology. *Artificial Intelligence Risk Management Framework (AI RMF 1.0)*. 2023.
2. World Health Organization. *Ethics and Governance of Artificial Intelligence for Health*. 2021.
3. UNESCO. *Recommendation on the Ethics of Artificial Intelligence*. 2021.
4. OECD. *OECD AI Principles*. 2019.
5. African Union. *Continental Artificial Intelligence Strategy*. 2024.
