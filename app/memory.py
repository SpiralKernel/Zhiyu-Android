"""Evidence-derived student memory. Reads never refresh verification or write state.

Temporal provenance borrows from Graphiti; retrieval borrows relevance/recency
ranking. Review intervals are an explicit heuristic, NOT calibrated FSRS recall
probabilities. The original events remain the source of truth, so corrections,
deleted imports and rule upgrades can always rebuild this projection.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app import ai_policy

VERSION = 'student-memory-2026.10.17-1'
EVIDENCE_WINDOW = 8
HALF_LIFE_DAYS = 30
INTERVALS = (1, 3, 7, 14, 30)
TTL_DAYS = {'question_interest': 7, 'self_report': 7, 'difficulty': 30,
            'guided_success': 14, 'understanding_check': 14, 'reviewed_success': 14}
LABELS = {'question_interest': '正在了解', 'self_report': '待确认',
          'difficulty': '需要巩固', 'guided_success': '正在理解',
          'understanding_check': '待独立验证', 'reviewed_success': '待独立验证'}


def clock():
    return datetime.now(timezone.utc)


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (TypeError, ValueError):
        return None


def day(value):
    return value.astimezone(ZoneInfo('Asia/Shanghai')).date()


def valid_evidence(evidence, at):
    unique = {}
    ordered = [e for e in evidence if timestamp(e['time']) is not None and timestamp(e['time']) <= at]
    for event in sorted(ordered, key=lambda e: (timestamp(e['time']), e['attempt_id'])):
        when = timestamp(event['time'])
        if when is not None and when <= at:
            unique.setdefault(event['identity'], event)
    return list(unique.values())


def practice_summary(evidence, at=None):
    """Time-weighted practice evidence, not a mastery score or recall probability.

    Beijing dates make this stable within one learning day (and cacheable).
    Independent, distinct evidence only; chat observations never enter here.
    """
    at = at or clock()
    items = valid_evidence(evidence, at)
    recent = items[-EVIDENCE_WINDOW:]
    weights = [2 ** (-max(0, (day(at)-day(timestamp(e['time']))).days) / HALF_LIFE_DAYS)
               for e in recent]
    total = sum(weights)
    errors = sum(w for e, w in zip(recent, weights) if not e['correct'])
    return {'model': VERSION, 'window': EVIDENCE_WINDOW, 'half_life_days': HALF_LIFE_DAYS,
            'sample_count': len(recent), 'effective_count': round(total, 3),
            'weighted_error_rate': round(errors / total, 4) if total else None,
            'recent_independent_count': sum((day(at)-day(timestamp(e['time']))).days <= HALF_LIFE_DAYS for e in items),
            'basis': 'independent_distinct_items_only',
            'note': '旧证据每30天权重减半；这是作答证据统计，不是掌握度评分。'}


def resolution(after, evidence):
    """First subsequent run of 3 new correct items across >=2 Beijing dates.

    Later errors cannot resurrect this historical difficulty. They have their
    own provenance and independently update the current practice state.
    """
    streak = []
    for event in evidence:
        if timestamp(event['time']) <= after:
            continue
        if not event['correct']:
            streak = []
            continue
        streak.append(event)
        if len(streak) >= 3 and len({day(timestamp(e['time'])) for e in streak}) >= 2:
            return {'resolved_at': event['time'],
                    'resolved_by': [e['attempt_id'] for e in streak]}
    return None


def supported(note):
    return (note.get('policy_version') == ai_policy.VERSION and
            note.get('validation', {}).get('method') in
            {'independent_ai_review', 'reviewed_import'})


def project(notes, evidence, at=None):
    at = at or clock()
    evidence = valid_evidence(evidence, at)
    ordered = sorted(notes, key=lambda n: (timestamp(n['created_at']) or datetime.min.replace(tzinfo=timezone.utc), n['id']))
    result = []
    for index, note in enumerate(ordered):
        item = {**note, 'memory_version': VERSION, 'resolved_by': [],
                'resolved_at': None, 'superseded_by': None}
        created = timestamp(note['created_at'])
        ttl = TTL_DAYS.get(note['kind'], 7)
        item['expires_at'] = (created + timedelta(days=ttl)).isoformat() if created else None
        item['last_confirmed_at'] = note['created_at'] if supported(note) else None
        age = (at-created).total_seconds()/86400 if created else None
        item['freshness'] = ('unverified' if age is None or age < 0 else
                             'stale' if age >= ttl else 'aging' if age >= ttl/2 else 'fresh')
        item['memory_confidence'] = ('unverified' if item['freshness']=='unverified' else
                                     'stale' if item['freshness']=='stale' else
                                     'low' if item['freshness']=='aging' or not supported(note) else 'medium')
        if created is None or created > at:
            item.update(memory_status='invalid_time', memory_confidence='unverified')
        elif note['kind'] not in {'question_interest', 'self_report'} and not supported(note):
            item.update(memory_status='legacy_unverified', memory_confidence='unverified', freshness='unverified')
        else:
            resolved = resolution(created, evidence) if note['kind'] != 'question_interest' else None
            # Only exact duplicate claims supersede one another; different errors
            # within a type must not silently overwrite each other.
            duplicates = [n for n in ordered[index+1:] if n['kind'] == note['kind']
                          and n['evidence_quote'].strip() == note['evidence_quote'].strip()
                          and timestamp(n['created_at']) is not None
                          and created <= timestamp(n['created_at']) <= at
                          and (n['kind'] in {'question_interest', 'self_report'} or supported(n))]
            if resolved:
                item.update(memory_status='resolved', **resolved)
            elif duplicates:
                item.update(memory_status='superseded', superseded_by=duplicates[-1]['id'])
            elif at >= created + timedelta(days=ttl):
                item.update(memory_status='expired', memory_confidence='stale')
            else:
                item['memory_status'] = 'pending' if note['kind'] == 'self_report' else 'active'
        result.append(item)
    return result


def review(evidence, at=None):
    """Advance spacing only with successful independent work on distinct dates.

    Multiple attempts on the same day cannot extend the interval. A new error
    resets it. No AI observation or retrieval is accepted as a review event.
    """
    at = at or clock()
    items = valid_evidence(evidence, at)
    level, last_day = 0, None
    for event in items:
        current_day = day(timestamp(event['time']))
        if not event['correct']:
            level = 0
        elif current_day != last_day:
            level = min(level + 1, len(INTERVALS))
        last_day = current_day
    last = items[-1] if items else None
    interval = INTERVALS[max(0, level-1)] if last else None
    due_at = timestamp(last['time']) + timedelta(days=interval) if last else None
    return {'model': VERSION, 'interval_days': interval,
            'last_verified_at': last['time'] if last else None,
            'last_verified_id': last['attempt_id'] if last else None,
            'due_at': due_at.isoformat() if due_at else None,
            'due': bool(due_at and at >= due_at),
            'basis': 'independent_distinct_items_spaced_dates',
            'note': '复习间隔是保守调度规则，不是遗忘概率或掌握评分。'}


def apply(group, at=None):
    at = at or clock()
    evidence = valid_evidence(group['evidence'], at)
    memories = project(group.pop('_all_learning_notes', []), evidence, at)
    live = [n for n in memories if n['memory_status'] in {'active', 'pending'}]
    substantive = [n for n in live if n['kind'] != 'question_interest']
    difficulty = [n for n in substantive if n['kind'] == 'difficulty']
    choice = (difficulty or substantive or live)
    label = LABELS[choice[-1]['kind']] if choice else ('待重新确认' if any(
        n['memory_status'] in {'expired', 'legacy_unverified', 'invalid_time'} for n in memories) else None)
    practice_memory = {}
    for event in evidence:
        if event['correct']:
            continue
        resolved = resolution(timestamp(event['time']), evidence)
        expired = at >= timestamp(event['time']) + timedelta(days=30)
        practice_memory[event['attempt_id']] = {
            'memory_status': 'resolved' if resolved else 'expired' if expired else 'active',
            'resolved_by': resolved['resolved_by'] if resolved else []}
    live.sort(key=lambda n: (2 if n['kind']=='difficulty' else 0 if n['kind']=='question_interest' else 1,
                             timestamp(n['created_at']),n['id']))
    group.update(learning_notes=live[-5:], learning_status=label,
                 memory_history=memories, active_observation_count=len(live),
                 practice_memory=practice_memory, review=review(evidence, at), memory_version=VERSION)
    return group


def current_status(group):
    if group['review']['due']:
        return '建议复测'
    if group['status']=='表现稳定' and group.get('learning_status')=='需要巩固':
        return '待独立验证'
    if group['independent_count'] >= 5:
        return group['status']
    return group.get('learning_status') or group['status']


def _grams(text):
    text = ''.join(re.findall(r'[\w]+', text.lower()))
    return {text[i:i+2] for i in range(len(text)-1)}


def retrieve(types, query, focus_type_id=None, limit=8, at=None, context_budget=18000):
    """Input must already be owner/book-scoped by study.state. No DB writes.

    Query text is used only to rank, never to manufacture or validate a memory.
    Memory statements are placed in untrusted learning_material by the caller.
    """
    at = at or clock()
    grams = _grams(query[:16000])
    ranked = []
    for item in types:
        known = bool(item['independent_count'] or item.get('active_observation_count'))
        lexical = len(grams & _grams(item['name']))
        focused = item['id'] == focus_type_id
        if not known and not focused:
            continue
        last = timestamp(item.get('review', {}).get('last_verified_at'))
        fresh = 1 / (1 + max(0, (at-last).days)) if last else 0
        ranked.append((1000*focused + 20*lexical + 2*bool(item.get('review', {}).get('due')) + fresh,
                       focused or lexical > 0, item))
    ranked.sort(key=lambda entry: (-entry[0], entry[2]['id']))
    # With a concrete topic, leave unrelated diagnoses out of the prompt.
    related = [entry for entry in ranked if entry[1]]
    selected = (related if related else ranked[:4])[:max(0, min(limit, 16))]
    result = []
    for _, _, item in selected:
        notes = [n for n in item.get('learning_notes', []) if n.get('memory_status') in {'active', 'pending'}
                 and timestamp(n.get('expires_at')) is not None and timestamp(n['expires_at']) > at]
        evidence = item.get('evidence', [])[-3:]
        entry = {**{k: item.get(k) for k in ('id','name','can_do','status','current_status','learning_status','independent_count','review','evidence_summary')},
                       'learning_notes': [{k:n.get(k) for k in ('id','source','message_id','kind','note','evidence_quote','created_at',
                           'memory_status','memory_confidence','freshness','last_confirmed_at','expires_at','policy_version','validation')} for n in notes[-3:]],
                 'practice_evidence': [{**{k:e.get(k) for k in ('attempt_id','correct','time','source')},
                     'stem':str(e.get('stem',''))[:1200], 'answer':str(e.get('answer',''))[:1200]} for e in evidence],
                 'resolved_observation_count': sum(n['memory_status']=='resolved' for n in item.get('memory_history', []))}
        if len(json.dumps(result+[entry],ensure_ascii=False)) > context_budget:
            break
        result.append(entry)
    return {'version': VERSION, 'retrieved_at': at.isoformat(), 'items': result,
            'note': '读取记忆不构成复习；过期和已解决线索不作为当前困难。'}
