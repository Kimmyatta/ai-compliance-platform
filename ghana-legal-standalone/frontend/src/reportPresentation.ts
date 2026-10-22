import type { EvidenceClaim } from './api';

export const applicationLabels = { notice_and_cure: 'Notice and cure', remedial_access: 'Remedial access', material_breach: 'Material breach' };

export const reportSections = [
  { title: 'Case Summary', scopes: ['case_fact', 'contract_term'], empty: 'No claim-level case summary is available in this draft.' },
  { title: 'Relevant Judgments', scopes: ['general_principle', 'authority_case_only'], empty: 'No claim about the reviewed authorities is available in this draft.' },
  { title: 'How They Relate to Your Case', scopes: ['comparison'], empty: 'No claim-level comparison is available in this draft.' },
  { title: 'Possible Arguments and Next Steps', scopes: [], empty: 'No claim-level arguments or next steps are available in this draft.' },
  { title: 'Uncertainties', scopes: ['not_established'], empty: 'No separate unresolved-point claims were recorded. This does not establish that the case is complete.' },
] as const;

export function groupReportClaims(claims: EvidenceClaim[]) {
  return reportSections.map(section => ({
    ...section,
    claims: claims.filter(claim => claim.application_topic
      ? section.title === 'How They Relate to Your Case'
      : (section.scopes as readonly string[]).includes(claim.scope)),
  }));
}

export function statementAssessment(claim: EvidenceClaim): { label: string; caution: boolean } {
  if (claim.evidence_check === 'flagged' || claim.check_issues.length > 0) {
    return { label: 'Evidence check failed - lawyer review required', caution: true };
  }
  if (claim.wording_origin === 'review_question') {
    return { label: claim.application_alignment === 'aligned_sources' ? 'Review question - no legal conclusion' : 'Evidence gap - review required', caution: true };
  }
  if (claim.scope === 'not_established' || claim.evidence_check === 'no_evidence' || claim.verification?.origin === 'evidence_gate') {
    return { label: 'Insufficient evidence', caution: true };
  }
  if (claim.verification?.origin === 'policy_gate' || (claim.scope === 'comparison' && claim.semantic_status === 'supported')) {
    return { label: 'Lawyer review required - support not accepted', caution: true };
  }
  if (claim.scope === 'case_fact' && claim.semantic_status === 'supported') {
    return { label: claim.factual_origin === 'case_document'
      ? 'AI checked against document wording - not factual proof'
      : 'AI checked against entered summary only - not document verification', caution: true };
  }
  switch (claim.semantic_status) {
    case 'supported': return { label: 'AI assessment: supported - not lawyer-approved', caution: false };
    case 'contradicted': return { label: 'AI assessment: contradicted by reviewed evidence', caution: true };
    case 'insufficient_evidence': return { label: 'Insufficient evidence', caution: true };
    default: return { label: 'Not assessed - lawyer review required', caution: true };
  }
}
