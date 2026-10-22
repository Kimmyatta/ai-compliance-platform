from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MatterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    reference: str = Field(default="", max_length=80)
    description: str = Field(default="", max_length=3000)


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=3000)
    matter_id: str | None = None
    scope: Literal["library", "matter", "both"] = "library"


class ResearchRequest(SearchRequest):
    query: str = Field(min_length=3, max_length=3000)


class CaseRequest(BaseModel):
    matter_id: str


class CaseAnalysisRequest(CaseRequest):
    facts: str = Field(min_length=10, max_length=12000)
    issues: list[str] = Field(min_length=1, max_length=12)
    confirmed: bool = False


class ReviewedQuote(BaseModel):
    source_id: int
    quote: str = Field(min_length=20, max_length=3000)


class TerminationRequest(CaseRequest):
    facts: str = Field(min_length=10, max_length=4000)
    contract: ReviewedQuote
    authority: ReviewedQuote
    confirmed: bool = False
    reasoning_confirmed: bool = False
    role_review_id: str | None = Field(default=None, min_length=1, max_length=80)


class AutomaticEvidenceRequest(CaseRequest):
    model_config = ConfigDict(extra='forbid')
    facts: str = Field(min_length=10, max_length=4000)


class AutomaticTerminationRequest(AutomaticEvidenceRequest):
    selection_id: str = Field(min_length=1, max_length=80)
    confirmed: bool = False


class PassageSelection(BaseModel):
    source_id: int | None
    quote: str = Field(max_length=1600)
    role: Literal['contract_term', 'court_reasoning', 'statutory_text', 'party_allegation', 'background', 'uncertain']


class PassageRoleCheck(BaseModel):
    contract_role: Literal['operative_term', 'party_description', 'uncertain']
    authority_role: Literal['court_reasoning', 'statutory_text', 'party_allegation', 'background', 'uncertain']
    contract_basis_ids: list[str] = Field(max_length=3)
    authority_basis_ids: list[str] = Field(max_length=3)


class TerminationDraft(BaseModel):
    status: Literal["limited_comparison", "insufficient_authority"]
    contract_source_id: int
    authority_source_id: int
    similarities: str = Field(max_length=1200)
    differences: str = Field(max_length=1200)
    supporting_argument: str = Field(max_length=1200)
    adverse_argument: str = Field(max_length=1200)
    unanswered_questions: list[str] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def require_comparison_or_abstention(self):
        if self.status == "limited_comparison" and (not self.similarities.strip() or not self.differences.strip()):
            raise ValueError("A comparison must explain both similarities and differences.")
        if self.status == "insufficient_authority" and (self.supporting_argument.strip() or self.adverse_argument.strip()):
            raise ValueError("Insufficient authority cannot support legal approaches.")
        return self


class ClaimSpan(BaseModel):
    role: Literal["contract", "authority", "facts"]
    text: str = Field(min_length=12, max_length=700)


class AtomicClaim(BaseModel):
    scope: Literal["contract_term", "case_fact", "general_principle", "authority_case_only", "comparison", "not_established"]
    spans: list[ClaimSpan] = Field(max_length=4)
    text: str = Field(min_length=10, max_length=500,
        description="One independently checkable proposition, not a paragraph or a legal verdict.")


class AtomicTerminationDraft(BaseModel):
    claims: list[AtomicClaim] = Field(min_length=1, max_length=8)


class ReferencedObservation(BaseModel):
    scope: Literal['contract_term', 'case_fact', 'general_principle', 'authority_case_only']
    evidence_id: str = Field(min_length=1, max_length=40)


class ApplicationDecision(BaseModel):
    status: Literal['aligned_sources', 'evidence_gap']
    evidence_ids: list[str] = Field(max_length=4)


class NoticeApplication(ApplicationDecision):
    question: Literal['confirm_notice_receipt', 'review_notice_content', 'review_cure_opportunity', 'review_notice_authority_scope']


class AccessApplication(ApplicationDecision):
    question: Literal['identify_access_condition', 'resolve_remedial_access', 'review_access_authority_scope']


class MaterialityApplication(ApplicationDecision):
    question: Literal['identify_materiality_test', 'resolve_alleged_material_breach', 'review_materiality_authority_scope']


class TerminationApplications(BaseModel):
    notice_and_cure: NoticeApplication
    remedial_access: AccessApplication
    material_breach: MaterialityApplication


class FocusedTerminationDraft(BaseModel):
    observations: list[ReferencedObservation] = Field(max_length=4)
    applications: TerminationApplications


class ClaimAssessment(BaseModel):
    claim_id: str = Field(min_length=1, max_length=20)
    evidence: list[ClaimSpan] = Field(max_length=3)
    verdict: Literal["supported", "contradicted", "insufficient_evidence"]
    reason: str = Field(min_length=10, max_length=600)


class VerificationBatch(BaseModel):
    assessments: list[ClaimAssessment] = Field(min_length=1, max_length=4)


class Claim(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    source_ids: list[int] = Field(min_length=1, max_length=12)


class GeneratedReport(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    findings: list[Claim] = Field(min_length=1, max_length=12)
    limitations: list[str] = Field(min_length=1, max_length=10)


class SourceQuote(BaseModel):
    source_id: int
    quote: str = Field(min_length=20, max_length=600)


class CaseFinding(BaseModel):
    category: Literal["comparison", "possible_approach", "evidence_gap"]
    source_ids: list[int] = Field(default_factory=list, max_length=12)
    supporting_quotes: list[SourceQuote] = Field(default_factory=list, max_length=3,
        description="Copy continuous exact source text first; no ellipses or paraphrases.")
    text: str = Field(min_length=1, max_length=6000,
        description="A narrow comparison supported by the quoted reasoning, or an explicit evidence gap.")

    @model_validator(mode="after")
    def require_references_for_comparisons(self):
        if self.category != "evidence_gap" and not self.source_ids:
            raise ValueError("Comparisons and possible legal approaches require source references.")
        if self.category != "evidence_gap" and not self.supporting_quotes:
            raise ValueError("Comparisons and possible legal approaches require supporting quotations.")
        return self


class CaseAnalysisReport(GeneratedReport):
    findings: list[CaseFinding] = Field(min_length=1, max_length=8)


class CaseBrief(BaseModel):
    facts: str = Field(min_length=10, max_length=12000)
    issues: list[str] = Field(min_length=1, max_length=12)
    missing_information: list[str] = Field(max_length=12)


class ExtractiveCaseBrief(BaseModel):
    evidence_ids: list[str] = Field(min_length=1, max_length=10)
    issues: list[str] = Field(min_length=1, max_length=12)
    missing_information: list[str] = Field(max_length=12)


class AuthorityObservation(BaseModel):
    kind: Literal['reasoning', 'decision', 'principle']
    evidence_id: str = Field(min_length=1, max_length=40)


class IssueApplication(BaseModel):
    status: Literal['draft', 'evidence_gap']
    text: str = Field(max_length=450)
    evidence_ids: list[str] = Field(max_length=4)


class IssueApplications(BaseModel):
    similarity: IssueApplication
    difference: IssueApplication
    argument_for_termination: IssueApplication
    argument_against_termination: IssueApplication
    weakness: IssueApplication


class IssueAnalysisDraft(BaseModel):
    observations: list[AuthorityObservation] = Field(max_length=3)
    applications: IssueApplications
