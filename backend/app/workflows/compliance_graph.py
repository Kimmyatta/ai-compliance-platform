from langgraph.graph import END, StateGraph

from backend.app.workflows.agents import (
    compliance_review_agent,
    escalation_agent,
    intake_agent,
    report_generation_agent,
    retrieval_agent,
    risk_scoring_agent,
)
from backend.app.workflows.compliance_state import ComplianceWorkflowState


def should_continue(state: ComplianceWorkflowState) -> str:
    if state.get("status") == "failed":
        return "failed"
    return "continue"


def should_escalate_after_report(state: ComplianceWorkflowState) -> str:
    if state.get("escalation_required"):
        return "escalate"
    return "complete"


def build_compliance_graph():
    graph = StateGraph(ComplianceWorkflowState)

    graph.add_node("intake", intake_agent)
    graph.add_node("retrieval", retrieval_agent)
    graph.add_node("compliance_review", compliance_review_agent)
    graph.add_node("risk_scoring", risk_scoring_agent)
    graph.add_node("report_generation", report_generation_agent)
    graph.add_node("escalation", escalation_agent)

    graph.set_entry_point("intake")

    graph.add_conditional_edges(
        "intake",
        should_continue,
        {
            "continue": "retrieval",
            "failed": END,
        },
    )

    graph.add_conditional_edges(
        "retrieval",
        should_continue,
        {
            "continue": "compliance_review",
            "failed": END,
        },
    )

    graph.add_conditional_edges(
        "compliance_review",
        should_continue,
        {
            "continue": "risk_scoring",
            "failed": END,
        },
    )

    graph.add_edge("risk_scoring", "report_generation")

    graph.add_conditional_edges(
        "report_generation",
        should_escalate_after_report,
        {
            "escalate": "escalation",
            "complete": END,
        },
    )

    graph.add_edge("escalation", END)

    return graph.compile()


compliance_graph = build_compliance_graph()
