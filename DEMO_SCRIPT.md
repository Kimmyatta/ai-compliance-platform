# AfriSafeBench Demo Script

## Demo Goal

Show that AfriSafeBench is both:

```text
1. an evaluation benchmark for LLM AI safety reasoning
2. a framework-guided governance tool for African healthcare AI deployments
```

Target length: 2-3 minutes.

## 1. Opening

Hi, my name is Kimberly Atta-Peters from the University of St. Thomas, Minnesota.

This project is called AfriSafeBench. It is an Open Track hackathon project that evaluates whether LLMs can identify AI safety and governance risks in African healthcare AI deployment scenarios.

The problem I am addressing is that many AI safety and compliance tools are built around Western regulatory assumptions. But African healthcare deployments often involve different risks: local validation gaps, resource constraints, human oversight challenges, data governance issues, vendor dependency, and unsafe medical advice.

AfriSafeBench asks:

```text
Can LLMs recognize these risks in realistic African healthcare scenarios?
```

## 2. Show The App

In the app, I start on the AI Safety Evaluation page.

The scenario browser contains 25 benchmark scenarios across seven African countries, including Ghana, Kenya, Nigeria, South Africa, Rwanda, Uganda, and Tanzania.

Each scenario has expected AI safety risk categories. These include bias and fairness, human oversight, transparency, safety and reliability, data governance and privacy, monitoring and incident reporting, distribution shift and local validation, vendor dependency, resource-constrained deployment, and unsafe medical advice.

## 3. Run One Scenario

For the demo, I select scenario 001: AI-Assisted Malaria Diagnosis in Rural Ghana.

This scenario describes a malaria diagnosis system trained mostly on Southeast Asian microscopy images but deployed in northern Ghana without local validation. Laboratory technicians are told to rely on the AI output as the primary diagnostic reference.

I choose a model and run the scenario evaluation.

The app returns:

- detected risks
- severity levels
- scenario-specific explanations
- matched risks
- missed risks
- extra risks
- a coverage score

This is the benchmark mode. It measures whether the model identified the expected risks.

## 4. Show Benchmark Results

I evaluated three models across all 25 scenarios, for 75 total evaluations:

```text
llama-3.1-8b-instant
llama-3.3-70b-versatile
openai/gpt-oss-20b
```

The overall mean coverage scores were:

```text
openai/gpt-oss-20b:      72.00%
llama-3.1-8b-instant:    70.67%
llama-3.3-70b-versatile: 68.00%
```

The results show that the models can identify many risks, but they are uneven. They do better on familiar categories like bias, privacy, and general safety. They are weaker on deployment-specific risks like resource-constrained deployment, monitoring and incident reporting, vendor dependency, and local validation.

This matters because those deployment-specific risks are often central to safety in real African healthcare settings.

## 5. Explain Human-Audited Scoring

One challenge is that models often use different wording for the same risk.

For example, a model may say:

```text
Vendor demonstration bias
```

instead of:

```text
Bias and Fairness
```

AfriSafeBench includes rescoring and human-review flags. If a score changes from missed to matched during semantic review, the CSV records that with:

```text
needs_human_review
review_changed_categories
review_notes
```

This makes the scoring transparent instead of hiding manual judgment.

## 6. Show Framework-Guided Mode

The second part is the tool/report mode.

After a scenario has been evaluated, I can generate framework-guided recommendations. The tool retrieves relevant excerpts from governance frameworks, including:

- WHO Ethics and Governance of AI for Health
- NIST AI Risk Management Framework
- UNESCO Recommendation on AI Ethics
- OECD AI Principles
- African Union Continental AI Strategy

Then it generates:

- a framework summary
- prioritized governance recommendations
- a checklist
- limitations and dual-use considerations
- source excerpts

For the malaria diagnosis scenario, the tool recommends local validation using Ghanaian patient samples, monitoring for bias and error, and training technicians to interpret AI outputs rather than relying blindly on them.

This turns the benchmark from only an evaluation into a practical governance assistant.

## 7. Impact

The impact of AfriSafeBench is that it makes African healthcare deployment risks visible in LLM evaluation.

It does not just ask whether a model knows abstract AI ethics terms. It asks whether the model can reason about real deployment conditions: infrastructure, local data, human oversight, vendor control, and post-deployment monitoring.

The project can be extended with more scenarios, expert-reviewed scoring, local-language cases, and country-specific governance context.

## 8. Closing

AfriSafeBench contributes a reusable workflow:

```text
African healthcare AI scenario
-> LLM risk identification
-> benchmark scoring
-> human-audited rescoring flags
-> framework-guided governance recommendations
```

The goal is to support safer AI deployment by evaluating whether models can recognize the risks that matter in African healthcare contexts, and by helping reviewers turn those findings into actionable governance recommendations.
