import type { EvidenceClaim } from './api';

export function visibleDraft(claim: EvidenceClaim) {
  return claim.scope === 'comparison' && claim.evidence_check === 'matched' && !claim.check_issues.length
    && claim.verification?.origin === 'policy_gate' && claim.verification.model_verdict === 'supported'
    && ['contract', 'authority', 'facts'].every(role => claim.spans.some(span => span.role === role && span.source_id !== null));
}
export function visibleObservation(claim: EvidenceClaim) {
  return claim.wording_origin === 'source_text' && claim.evidence_check === 'matched'
    && !claim.check_issues.length && claim.semantic_status === 'supported';
}
