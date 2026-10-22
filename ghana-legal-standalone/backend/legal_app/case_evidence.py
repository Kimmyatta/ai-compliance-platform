"""Extractive case evidence. Text matching is provenance, not proof of a fact."""

import re
from collections import deque

from fastapi import HTTPException
from pydantic import ValidationError

from .atomic_claims import normalised
from .focused_claims import TOPICS, evidence_units
from .request_budget import input_tokens, messages_for
from .schemas import ExtractiveCaseBrief


VERSION = 'document_facts_v1'
PATTERNS = {
    'notice_and_cure': re.compile(r'\b(notice|recei\w*|courier|remedy|terminat\w*)\b', re.I),
    'remedial_access': re.compile(r'\b(access|repair\w*|remedial|entry|alternative)\b', re.I),
    'material_breach': re.compile(r'\b(defect\w*|temperatur\w*|excursion\w*|material breach|materiality|calibration|stabilis\w*|power)\b', re.I),
}
DOCUMENT_STATUS = re.compile(r'\b(produced|certificate|invoice|outstanding|missing)\b', re.I)
WARNING = ('Case-document excerpts retain allegations and documentary limitations. '
           'They are not independently proven facts. The entered summary is retained separately '
           'and is not used as documentary proof. Keyword selection can miss relevant evidence.')
BRIEF_TASK = ('Select up to ten case-unit IDs for a proposed factual brief, in chronological order where possible. '
              'The server copies their complete text; never paraphrase or write factual statements. '
              'Prefer units preserving who alleges or disputes a fact, notice receipt, repair-access arrangements '
              'and whether documents were produced. Include their context units when needed for attribution. '
              'Also propose neutral legal issues and specific missing information within the reviewed excerpts, '
              'not conclusions that evidence does not exist in the whole case. Selection is not legal validation.')
BRIEF_UNIT_LIMIT = 350
BRIEF_TEXT_LIMIT = 12000
EVENT_DATE = re.compile(
    r'\b\d{1,2}(?:[-/]\d{1,2})?\s+(?:January|February|March|April|May|June|July|August|'
    r'September|October|November|December)\b|\b\d{4}-\d{2}-\d{2}\b', re.I)
RECEIPT_EVENT = re.compile(r'courier|office receipt|acknowledg\w*.*recei|(?:notice|letter).*receiv|receiv\w*.*(?:notice|letter)', re.I)
ACCESS_EVENT = re.compile(r'propos\w*.*(?:repair|visit)|offer\w*.*(?:entry|access)|(?:refused|denied).*access', re.I)
ACCESS_CONTEXT = re.compile(PATTERNS['remedial_access'].pattern + r'|\b(email chain|evening visit|confirm\w*|agreed|agreement)\b', re.I)
REFERENTIAL_START = re.compile(r'^(?:It|Its|They|Their|This|That|The available|The alternative)\b', re.I)


def _balanced_units(units, sources):
    """Round-robin documents, then pages, without changing any source unit."""
    source_by_id = {s['chunk_id']: s for s in sources}
    documents = {}
    for unit in units:
        source = source_by_id[unit['source_id']]
        document = source.get('document_id', source['chunk_id'])
        page = source.get('locator', source['chunk_id'])
        documents.setdefault(document, {}).setdefault(page, deque()).append(unit)
    queues = [deque(pages.values()) for pages in documents.values()]
    while any(queues):
        for pages in queues:
            if pages:
                page = pages.popleft()
                yield page.popleft()
                if page:
                    pages.append(page)


def _chronology_groups(catalog, sources):
    source_by_id = {s['chunk_id']: s for s in sources}
    pages = {}
    for unit in catalog:
        source = source_by_id[unit['source_id']]
        key = (source.get('document_id', source['chunk_id']), source.get('locator', source['chunk_id']))
        pages.setdefault(key, []).append(unit)
    groups = {}
    for page in pages.values():
        for index, unit in enumerate(page):
            text = unit['text']
            receipt = bool(EVENT_DATE.search(text) and RECEIPT_EVENT.search(text))
            access = bool(ACCESS_EVENT.search(text) or
                          (EVENT_DATE.search(text) and PATTERNS['remedial_access'].search(text)))
            if not receipt and not access:
                continue
            bundle = [unit]
            if index and REFERENTIAL_START.search(text):
                bundle.insert(0, page[index - 1])
            # Keep adjacent attribution/disagreement, not just a date stripped of context.
            context = ACCESS_CONTEXT if access else RECEIPT_EVENT
            for following in page[index + 1:index + (3 if access else 2)]:
                if not context.search(following['text']):
                    break
                bundle.append(following)
            groups[unit['id']] = ('remedial_access' if access else 'notice_and_cure', bundle)
    return groups


def _brief_units(catalog, sources, settings, system):
    eligible = [u for u in catalog if len(u['text']) <= BRIEF_UNIT_LIMIT]
    chosen, mandatory = {}, set()

    def fits(units, limit):
        rows = [u for u in catalog if u['id'] in units]
        if len('\n'.join(u['text'] for u in rows)) > BRIEF_TEXT_LIMIT:
            return False
        return input_tokens(messages_for(system, BRIEF_TASK, {'case_units': rows},
                                         ExtractiveCaseBrief, settings.model), settings.model,
                            ExtractiveCaseBrief) <= limit

    base = input_tokens(messages_for(system, BRIEF_TASK, {'case_units': []},
                                    ExtractiveCaseBrief, settings.model), settings.model, ExtractiveCaseBrief)
    if base > settings.max_input_tokens:
        raise HTTPException(413, 'No complete case-document excerpt fits the brief budget. Review the original documents.')
    reserved_limit = base + (settings.max_input_tokens - base) // 2
    groups = _chronology_groups(catalog, sources)
    queues = [deque(_balanced_units([u for u in eligible if u['id'] in groups and groups[u['id']][0] == topic], sources))
              for topic in ('notice_and_cure', 'remedial_access')]
    # Reserve chronology before generic facts; leave half the available budget for
    # issue/page/document coverage. Bundles are atomic: oversized context is not clipped.
    while any(queues):
        for queue in queues:
            if not queue:
                continue
            anchor = queue.popleft()
            bundle = groups[anchor['id']][1]
            if any(len(u['text']) > BRIEF_UNIT_LIMIT for u in bundle):
                continue
            candidate = {**chosen, **{u['id']: u for u in bundle}}
            if fits(candidate, reserved_limit):
                chosen = candidate
                mandatory.update(u['id'] for u in bundle)

    topics = [deque(_balanced_units([u for u in eligible if pattern.search(u['text'])], sources))
              for pattern in (*PATTERNS.values(), DOCUMENT_STATUS)]
    # One initial opportunity per issue, then round-robin the full document/page catalog.
    candidates = [queue[0] for queue in topics if queue]
    candidates.extend(_balanced_units(eligible, sources))
    for unit in candidates:
        if unit['id'] in chosen:
            continue
        bundle = groups[unit['id']][1] if unit['id'] in groups else [unit]
        if any(len(u['text']) > BRIEF_UNIT_LIMIT for u in bundle):
            continue
        candidate = {**chosen, **{u['id']: u for u in bundle}}
        if fits(candidate, settings.max_input_tokens):
            chosen = candidate
            if unit['id'] in groups:
                mandatory.update(u['id'] for u in bundle)
    selected = [u for u in catalog if u['id'] in chosen]
    omitted = {u['id'] for _, bundle in groups.values() for u in bundle} - mandatory
    return selected, mandatory, omitted


def extractive_brief(intelligence, sources, truncated, system):
    catalog = source_units(sources)
    selected, mandatory, omitted = _brief_units(catalog, sources, intelligence.settings, system)
    if not selected:
        raise HTTPException(413, 'No complete case-document excerpt fits the brief budget. Review the original documents.')
    try:
        draft = ExtractiveCaseBrief.model_validate(intelligence.generate(
            BRIEF_TASK, {'case_units': selected}, ExtractiveCaseBrief, system=system)).model_dump()
    except ValidationError as exc:
        raise HTTPException(502, 'The proposed brief did not contain valid case-document references. No brief was accepted.') from exc
    by_id = {u['id']: u for u in selected}
    ids = draft['evidence_ids']
    if len(ids) != len(set(ids)) or any(key not in by_id for key in ids):
        raise HTTPException(502, 'The proposed brief cited an unavailable or duplicate case-document excerpt. No brief was accepted.')
    # Model preference cannot erase chronology that the server deliberately supplied.
    retained = set(ids) | mandatory
    observations = [u for u in selected if u['id'] in retained]
    source_ids = {u['source_id'] for u in selected}
    supplied_sources = [s for s in sources if s['chunk_id'] in source_ids]
    count = input_tokens(messages_for(system, BRIEF_TASK, {'case_units': selected},
                                     ExtractiveCaseBrief, intelligence.settings.model),
                         intelligence.settings.model, ExtractiveCaseBrief)
    return {'facts': '\n'.join(u['text'] for u in observations), 'issues': draft['issues'],
            'missing_information': draft['missing_information'], 'fact_excerpts': observations,
            'sources': supplied_sources,
            'truncated': truncated or len(selected) < len(catalog), 'factual_origin': 'case_document',
            'coverage': {'units_considered': len(catalog), 'units_supplied': len(selected), 'units_selected': len(observations),
                         'chronology_units_retained': len(mandatory), 'chronology_units_omitted': len(omitted),
                         'passages_considered': len(sources), 'passages_supplied': len(supplied_sources),
                         'input_tokens': count, 'input_budget_tokens': intelligence.settings.max_input_tokens,
                         'source_passages_truncated': bool(truncated),
                         'incomplete': bool(truncated or len(selected) < len(catalog))},
            'warning': ('Extracts from uploaded documents, not independently proven facts. '
                        'Receipt/access chronology is retained alongside AI-selected excerpts; review their source passages.'
                        + (' Some receipt/access evidence could not fit as complete excerpts; review the original documents.' if omitted else ''))}


def source_units(sources):
    result = []
    seen = set()
    groups = {}
    for source in sources:
        key = (source.get('document_id', source['chunk_id']), source.get('locator', source['chunk_id']))
        for unit in evidence_units({'facts': source['text']}).values():
            identity = (key, unit['text'])
            if identity in seen:
                continue
            seen.add(identity)
            row = {**unit, 'id': f"case_{source['chunk_id']}_{unit['id']}", 'source_id': source['chunk_id']}
            result.append(row)
            groups.setdefault(key, []).append(row)
    # Overlapping PDF chunks can start/end mid-sentence. Prefer an available complete
    # containing excerpt from that same page; never reconstruct or splice a quotation.
    covered = {u['id'] for group in groups.values() for u in group
               if any(u['text'] != other['text'] and u['text'] in other['text'] for other in group)}
    return [u for u in result if u['id'] not in covered]


def documentary_facts(store, matter_id):
    sources, truncated = store.matter_passages(matter_id)
    units = source_units(sources)
    queues = {}
    for topic, pattern in {**PATTERNS, 'document_status': DOCUMENT_STATUS}.items():
        matches = [u for u in units if pattern.search(u['text'])]
        # Prioritize documentary receipt and access chronology, not generic clause wording.
        def priority(unit):
            text = unit['text'].lower()
            return (bool(re.search(r'\d', text)) + bool(re.search(
                r'courier|office receipt|proposed a repair|offered entry|email chain|acknowledges|questions|disputes', text)),
                -len(unit['text']))
        queues[topic] = sorted(matches, key=priority, reverse=True)
    chosen, size = {}, 0
    # Reserve room for every topic before filling any one topic's candidates.
    for index in range(max((len(q) for q in queues.values()), default=0)):
        for topic in queues:
            if index >= len(queues[topic]):
                continue
            unit = queues[topic][index]
            if unit['id'] in chosen or len(unit['text']) > 700:
                continue
            if size + len(unit['text']) + 1 <= 4500:
                chosen[unit['id']] = unit
                size += len(unit['text']) + 1
    if not chosen:
        raise HTTPException(422, 'No usable case-document evidence was found for this issue. Upload clearer case documents; an entered summary is not documentary proof.')
    selected, offset = [], 0
    # Retain document order rather than presenting chronology in ranking order.
    for unit in units:
        if unit['id'] not in chosen:
            continue
        row = {**unit, 'corpus_start': offset, 'corpus_end': offset + len(unit['text'])}
        selected.append(row)
        offset = row['corpus_end'] + 1
    text = ' '.join(u['text'] for u in selected)
    topic_units = {topic: [u['id'] for u in selected if pattern.search(u['text'])]
                   for topic, pattern in PATTERNS.items()}
    return {'version': VERSION, 'text': text, 'units': selected, 'topics': topic_units,
            'sources': [s for s in sources if s['chunk_id'] in {u['source_id'] for u in selected}],
            'coverage': {'passages_considered': len(sources), 'units_considered': len(units),
                         'units_selected': len(selected), 'incomplete': truncated or len(selected) < len(units)},
            'warning': WARNING}


def attach_document_sources(claims, basis):
    """Resolve facts-role offsets into original source passages, never the entered summary."""
    for claim in claims:
        if claim['scope'] == 'case_fact':
            claim['factual_origin'] = 'case_document'
        for span in [*claim['spans'], *claim.get('verification', {}).get('evidence', [])]:
            if span['role'] != 'facts':
                continue
            unit = next((u for u in basis['units'] if span['start'] is not None
                         and u['corpus_start'] <= span['start'] and span['end'] <= u['corpus_end']), None)
            if unit:
                span['source_id'] = unit['source_id']
                span['source_start'] = unit['start'] + span['start'] - unit['corpus_start']
                span['source_end'] = span['source_start'] + len(span['text'])
            else:
                claim['check_issues'] = list(dict.fromkeys([*claim['check_issues'], 'unresolved_document_reference']))
                claim['evidence_check'] = 'flagged'
                claim['semantic_status'] = 'not_checked'
        topic = claim.get('application_topic')
        if topic and claim.get('application_alignment') == 'aligned_sources':
            relevant = [u for u in basis['units'] if u['id'] in basis['topics'][topic]]
            if not any(s['role'] == 'facts' and any(s['text'] in u['text'] for u in relevant)
                       for s in claim['spans']):
                claim['check_issues'] = list(dict.fromkeys([*claim['check_issues'], 'irrelevant_topic_evidence']))
                claim['evidence_check'] = 'flagged'
                claim['semantic_status'] = 'not_checked'
    return claims


def validate_saved_basis(store, matter_id, basis):
    if basis.get('version') != VERSION:
        raise HTTPException(409, 'Unknown case-document evidence version; generate a new report.')
    for saved in basis['sources']:
        current = store.source(saved['chunk_id'])
        document = store.document(current['document_id']) if current else None
        if not document or document['kind'] != 'matter' or document['matter_id'] != matter_id:
            raise HTTPException(422, 'Saved case evidence is outside this matter.')
        if current != saved:
            raise HTTPException(409, 'Case-document evidence has changed; generate a new report.')
    source_by_id = {s['chunk_id']: s for s in basis['sources']}
    offset = 0
    for unit in basis['units']:
        source = source_by_id.get(unit['source_id'])
        if (not source or normalised(source['text'])[unit['start']:unit['end']] != unit['text']
                or unit['corpus_start'] != offset or unit['corpus_end'] != offset + len(unit['text'])):
            raise HTTPException(409, 'Saved case-document quotations do not match their sources; regenerate the report.')
        offset = unit['corpus_end'] + 1
    if basis['text'] != ' '.join(u['text'] for u in basis['units']):
        raise HTTPException(409, 'Saved case evidence is inconsistent; regenerate the report.')
    expected_topics = {topic: [u['id'] for u in basis['units'] if pattern.search(u['text'])]
                       for topic, pattern in PATTERNS.items()}
    if basis['topics'] != expected_topics:
        raise HTTPException(409, 'Saved issue evidence is inconsistent; regenerate the report.')
