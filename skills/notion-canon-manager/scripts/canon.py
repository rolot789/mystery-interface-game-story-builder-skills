#!/usr/bin/env python3
"""Offline Canon tools. No credentials, network writes or model calls."""
import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

import canon_rules as rules
import canon_views

WORLD_KINDS = {'WorldRule', 'Organization', 'Service', 'Location', 'HistoryEvent', 'Term'}
V2_KINDS = {'Location', 'HistoryEvent', 'Term'}
KINDS = WORLD_KINDS | {'Character', 'Event', 'Fact', 'Claim', 'Knowledge', 'Trace', 'Choice', 'Ending'}
STATUSES = {'DRAFT', 'PROPOSED', 'CONFIRMED', 'SUPERSEDED', 'REJECTED'}
REVIEWS = {'NOT_CHECKED', 'VALID', 'NEEDS_REVIEW', 'BLOCKED'}
DEPTHS = {'CORE', 'SUPPORTING', 'MENTION'}
VISIBILITY = {'PUBLIC', 'INSIDER', 'SECRET'}
ORIGINS = {'FOUNDATION', 'PLOT_NEED'}
REALITY = {'REAL', 'REAL_PLUS', 'ALTERNATE', 'INVENTED'}
OWNERS = {
    **dict.fromkeys(WORLD_KINDS, 'mystery-world-builder'),
    **dict.fromkeys(['Character', 'Knowledge', 'Claim'], 'character-knowledge-builder'),
    **dict.fromkeys(['Event', 'Fact', 'Trace', 'Choice', 'Ending'], 'mystery-plot-builder'),
}
TEXT = {
    'WorldRule': ['statement', 'scope', 'exceptions', 'grounding'],
    'Organization': ['purpose', 'economy', 'operations', 'culture', 'daily_life'],
    'Service': ['purpose', 'users', 'normal_use', 'data_lifecycle', 'permissions', 'failures'],
    'Location': ['description', 'access', 'rhythm'],
    'HistoryEvent': ['summary', 'consequences', 'public_account'],
    'Term': ['definition', 'register'],
    'Character': ['identity', 'motive', 'daily_life', 'relationships'],
    'Event': ['action', 'result'],
    'Fact': ['statement', 'basis'],
    'Claim': ['statement', 'audience', 'intent'],
    'Knowledge': ['state'],
    'Trace': ['origin_type', 'summary', 'access', 'distortion'],
    'Choice': ['prompt', 'known_information'],
    'Ending': ['consequences'],
}
OPTIONAL_TEXT = {
    'WorldRule': ['violation_cost'],
    'Organization': ['structure', 'incentives', 'reputation', 'conflicts', 'formal_vs_actual'],
    'Location': ['place_type'],
    'Character': ['routine', 'voice'],
    'Knowledge': ['cannot_know'],
    'Trace': ['artifact_type', 'retention_exception'],
}
DATA_ENUMS = {
    'WorldRule': {'rule_type': {'PHYSICAL', 'TECHNICAL', 'LEGAL', 'ORGANIZATIONAL', 'SOCIAL_NORM', 'ECONOMIC', 'BELIEF'}, 'strength': {'HARD', 'SOFT'}},
    'Trace': {'state_at_present': {'PRESENT', 'DELETED', 'ALTERED'}},
}
REFS = {
    'WorldRule': {'enforced_by': {'Organization'}},
    'Organization': {'parent_id': {'Organization'}, 'hq_location_id': {'Location'}},
    'Service': {'provider_id': {'Organization'}},
    'Location': {'parent_id': {'Location'}},
    'HistoryEvent': {'preconditions': {'HistoryEvent', 'WorldRule'}, 'legacy_ids': WORLD_KINDS},
    'Term': {'refers_to': KINDS},
    'Character': {'home_location_id': {'Location'}},
    'Event': {'actors': {'Character', 'Organization', 'Service'}, 'preconditions': {'Event', 'Fact', 'WorldRule', 'HistoryEvent'}, 'location_id': {'Location'}},
    'Fact': {'event_id': {'Event'}, 'world_rule_id': {'WorldRule'}},
    'Claim': {'speaker_id': {'Character', 'Organization', 'Service'}, 'fact_ids': {'Fact'}},
    'Knowledge': {'character_id': {'Character'}, 'fact_id': {'Fact'}, 'acquired_via': {'Event', 'Trace', 'Claim'}},
    'Trace': {'origin_ids': {'Event', 'WorldRule', 'Service', 'HistoryEvent'}, 'author_id': {'Character', 'Organization', 'Service'}, 'service_id': {'Service'}},
}
LIST_REFS = {'actors', 'preconditions', 'acquired_via', 'origin_ids', 'fact_ids', 'enforced_by', 'legacy_ids'}
REQUIRED_REFS = {'Service': ['provider_id'], 'Event': ['actors', 'preconditions'], 'Claim': ['speaker_id'], 'Knowledge': ['character_id', 'fact_id', 'acquired_via'], 'Trace': ['origin_ids']}
TIME_KEYS = ['at', 'stated_at', 'created_at', 'from', 'until', 'valid_from', 'valid_until', 'founded_at', 'launched_at']
LINKS = {
    'supports': ({'Trace'}, {'Fact', 'Claim'}),
    'contradicts': ({'Trace'}, {'Fact', 'Claim'}),
    'generates': ({'Event', 'Service'}, {'Trace'}),
    'knows': ({'Character'}, {'Fact'}),
    'depends_on': (KINDS, KINDS),
    'related': (KINDS, KINDS),
    'entails': ({'WorldRule'}, {'WorldRule', 'Organization', 'Service', 'Location', 'Term'}),
    'exploits': ({'Event'}, {'WorldRule', 'Service'}),
}
# A change at either end of these links puts the other end up for review.
BOTH_WAYS = {'supports', 'contradicts', 'exploits'}
BEGIN = '## Canon Managed Data'
END = '## User Notes'


def canonical(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
def digest(x): return hashlib.sha256(canonical(x).encode()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def integer(x): return type(x) is int and x >= 0
def scalar(x): return type(x) in (str, int, float, bool) and (not isinstance(x, float) or abs(x) != float('inf'))
def text(x): return isinstance(x, str) and bool(x.strip())
# Membership test that tolerates malformed (unhashable) values instead of raising.
def one_of(x, values): return (x is None or isinstance(x, (str, int, float, bool))) and x in values
def number(x): return type(x) in (int, float) and x >= 0


def time_ok(x):
    try:
        rules.span(x)
        return True
    except (TypeError, ValueError, AttributeError):
        return False


def ref_to(kinds):
    return lambda x, index: isinstance(x, str) and x in index and index[x].get('kind') in kinds


def enum(values):
    return lambda x, index: one_of(x, values)


OPS = {'read', 'edit', 'delete', 'restore', 'export'}
# Structured list fields: {key: (check, required)} for each item.
ITEMS = {
    ('Service', 'changes'): {'at': (lambda x, i: time_ok(x), True), 'summary': (lambda x, i: text(x), True)},
    ('Service', 'retention'): {
        'data': (lambda x, i: text(x), True),
        'keep_days': (lambda x, i: x is None or integer(x), True),
        # null when data is kept forever and nothing happens on expiry.
        'after': (enum({'HARD_DELETE', 'SOFT_DELETE', 'ARCHIVE', None}), True),
        'exceptions': (lambda x, i: isinstance(x, str), False),
    },
    ('Service', 'access_policy'): {
        'role': (lambda x, i: text(x), True),
        'data': (lambda x, i: text(x), True),
        'ops': (lambda x, i: isinstance(x, list) and all(one_of(o, OPS) for o in x), True),
        'condition': (lambda x, i: isinstance(x, str), False),
    },
    ('Service', 'artifacts'): {'type': (lambda x, i: text(x), True), **{k: (lambda x, i: isinstance(x, str), False) for k in ['timestamp_source', 'edit_trace', 'delete_trace', 'read_receipt']}},
    ('Character', 'affiliations'): {
        'org_id': (ref_to({'Organization'}), True),
        'role': (lambda x, i: text(x), True),
        'from': (lambda x, i: time_ok(x), False),
        'until': (lambda x, i: time_ok(x), False),
    },
    ('Location', 'connections'): {'to': (ref_to({'Location'}), True), 'minutes': (lambda x, i: number(x), True), 'mode': (lambda x, i: isinstance(x, str), False)},
    ('Term', 'aliases'): None,
    ('Term', 'forbidden_aliases'): None,
}
NESTED_REFS = {'Character': {'affiliations': 'org_id'}, 'Location': {'connections': 'to'}}


def condition(c, state):
    if type(c) is bool:
        return c
    if not isinstance(c, dict):
        raise ValueError('condition must be boolean or object')
    if set(c) == {'all'} or set(c) == {'any'}:
        key = next(iter(c))
        vals = c[key]
        if not isinstance(vals, list) or not vals:
            raise ValueError('all/any requires a nonempty list')
        results = [condition(v, state) for v in vals]
        return all(results) if key == 'all' else any(results)
    if set(c) == {'not'}:
        return not condition(c['not'], state)
    if set(c) == {'var', 'eq'}:
        if c['var'] not in state:
            raise ValueError('unknown state variable: ' + str(c['var']))
        if not scalar(c['eq']):
            raise ValueError('eq value must be scalar')
        return type(state[c['var']]) is type(c['eq']) and state[c['var']] == c['eq']
    raise ValueError('unsupported condition keys')


def references(e):
    refs = list(e.get('depends_on', []))
    d = e.get('data', {})
    for key in REFS.get(e.get('kind'), {}):
        value = d.get(key)
        if value is not None:
            refs.extend(value if isinstance(value, list) else [value])
    for key, field in NESTED_REFS.get(e.get('kind'), {}).items():
        refs.extend(x.get(field) for x in rules.items_of(d.get(key)))
    if e.get('kind') == 'Ending':
        refs.extend(x.get('choice_id') for x in rules.items_of(d.get('witness')))
    return [x for x in refs if isinstance(x, str)]


def walk(snapshot, steps):
    state = copy.deepcopy(snapshot['initial_state'])
    entities = {e['id']: e for e in snapshot['entities']}
    used = set()
    if not isinstance(steps, list):
        raise ValueError('witness must be list')
    for step in steps:
        if not isinstance(step, dict) or set(step) != {'choice_id', 'option_id'}:
            raise ValueError('invalid witness step')
        eid = step['choice_id']
        if eid in used:
            raise ValueError('choice repeated: ' + eid)
        e = entities.get(eid)
        if not e or e['kind'] != 'Choice' or one_of(e['status'], {'SUPERSEDED', 'REJECTED'}):
            raise ValueError('unavailable choice: ' + eid)
        d = e['data']
        if not condition(d['available_when'], state):
            raise ValueError('choice precondition failed: ' + eid)
        options = [o for o in d['options'] if o['id'] == step['option_id']]
        if len(options) != 1:
            raise ValueError('option missing/duplicate')
        o = options[0]
        if not condition(o['condition'], state):
            raise ValueError('option precondition failed')
        for k, v in o['effects'].items():
            if k not in state or type(v) is not type(state[k]):
                raise ValueError('undeclared variable or type-changing effect')
            state[k] = v
        used.add(eid)
    return state


def check_charter(s, fail):
    c = s.get('charter')
    if not isinstance(c, dict):
        fail('charter must be object in schema_version 2')
        return
    for key in ['genre_tone', 'premise', 'scope_out', 'timezone']:
        if not isinstance(c.get(key), str):
            fail('charter.' + key + ' must be text')
    if c.get('reality_distance') is not None and not one_of(c.get('reality_distance'), REALITY):
        fail('charter.reality_distance must be null or one of ' + ', '.join(sorted(REALITY)))
    if not isinstance(c.get('scope_in'), list) or not all(isinstance(x, str) for x in c['scope_in']):
        fail('charter.scope_in must be a list of entity IDs')
    if 'present_at' not in c or not time_ok(c['present_at']):
        fail('charter.present_at must be a TimeSpec')


def check_world_fields(e, eid, version, fail):
    kind, d = e['kind'], e['data']
    for key, values in [('depth', DEPTHS), ('visibility', VISIBILITY), ('origin', ORIGINS)]:
        if key in e:
            if not one_of(e[key], values):
                fail(f'{eid}: invalid {key}')
        elif version == 2 and kind in WORLD_KINDS:
            fail(f'{eid}: {key} required for world settings in schema_version 2')
    if 'in_world_reason' in e and not isinstance(e['in_world_reason'], str):
        fail(f'{eid}: in_world_reason must be text')
    for key in OPTIONAL_TEXT.get(kind, []):
        if key in d and not isinstance(d[key], str):
            fail(f'{eid}: data.{key} must be text')
    for key, values in DATA_ENUMS.get(kind, {}).items():
        if key in d and not one_of(d[key], values):
            fail(f'{eid}: data.{key} must be one of ' + ', '.join(sorted(values)))
    if 'duration_minutes' in d and not number(d['duration_minutes']):
        fail(f'{eid}: data.duration_minutes must be a nonnegative number')


def check_items(e, eid, index, fail):
    for (kind, key), spec in ITEMS.items():
        if e['kind'] != kind or key not in e['data']:
            continue
        items = e['data'][key]
        if not isinstance(items, list):
            fail(f'{eid}: data.{key} must be list')
            continue
        for item in items:
            if spec is None:
                ok = isinstance(item, str) and item.strip()
            else:
                ok = isinstance(item, dict) and set(item) <= set(spec) and all(
                    (k in item and check(item[k], index)) if required else (k not in item or check(item[k], index))
                    for k, (check, required) in spec.items())
            if not ok:
                fail(f'{eid}: invalid data.{key} item: {json.dumps(item, ensure_ascii=False)}')


def validate(s, complete=False):
    errors = []
    warnings = []

    def fail(msg): errors.append(msg)

    if not isinstance(s, dict):
        return {'errors': ['snapshot must be object'], 'warnings': [], 'findings': []}
    for k in ['project_id', 'version_id', 'title']:
        if not isinstance(s.get(k), str) or not s[k].strip():
            fail(k + ' must be nonempty string')
    version = s.get('schema_version')
    if version not in (1, 2):
        fail('schema_version must be 1 or 2')
    if version == 2:
        check_charter(s, fail)
    if not integer(s.get('revision')):
        fail('revision must be nonnegative integer')
    state = s.get('initial_state')
    if not isinstance(state, dict) or not all(isinstance(k, str) and scalar(v) for k, v in state.items()):
        fail('initial_state must contain scalar values')
        state = {}
    es, ls, ds, issues = s.get('entities'), s.get('links'), s.get('decisions'), s.get('issues')
    if not all(isinstance(x, list) for x in [es, ls, ds, issues]):
        return {'errors': errors + ['entities, links, decisions, issues must be lists'], 'warnings': warnings, 'findings': []}
    index = {}
    decision_ids = set()
    confirmed_decisions = set()
    allids = set()
    for collection in [es, ls, ds, issues]:
        for item in collection:
            if not isinstance(item, dict):
                fail('record must be object')
                continue
            id_ = item.get('id')
            if not isinstance(id_, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', id_):
                fail('invalid id: ' + str(id_))
                continue
            if id_ in allids:
                fail('duplicate id: ' + id_)
            allids.add(id_)
    for d in ds:
        if not isinstance(d, dict):
            continue
        decision_ids.add(d.get('id'))
        if d.get('status') == 'CONFIRMED' and d.get('answer'):
            confirmed_decisions.add(d.get('id'))
        if not one_of(d.get('status'), STATUSES):
            fail('invalid decision status')
        if not isinstance(d.get('question'), str):
            fail('decision question missing')
        if d.get('status') == 'CONFIRMED' and not d.get('answer'):
            fail('confirmed decision requires user answer')
    for e in es:
        # A non-text kind is reported as unknown below; keeping it out of the index lets later checks trust kind.
        if isinstance(e, dict) and isinstance(e.get('id'), str) and isinstance(e.get('kind'), str):
            index[e['id']] = e
    for e in es:
        if not isinstance(e, dict):
            continue
        eid = e.get('id', '?')
        kind = e.get('kind')
        d = e.get('data')
        if not one_of(kind, KINDS):
            fail(f'{eid}: unknown kind')
            continue
        if kind in V2_KINDS and version != 2:
            fail(f'{eid}: kind {kind} requires schema_version 2')
        if e.get('project_id') != s.get('project_id') or e.get('version_id') != s.get('version_id'):
            fail(f'{eid}: cross-project/version entity')
        if not integer(e.get('revision')):
            fail(f'{eid}: invalid revision')
        if not isinstance(e.get('title'), str) or not e['title'].strip():
            fail(f'{eid}: title missing')
        if e.get('owner') != OWNERS[kind]:
            fail(f'{eid}: wrong owner')
        if not one_of(e.get('status'), STATUSES) or not one_of(e.get('review'), REVIEWS):
            fail(f'{eid}: invalid status/review')
        if not isinstance(e.get('depends_on'), list):
            fail(f'{eid}: depends_on must be list')
        if not isinstance(e.get('decision_refs'), list):
            fail(f'{eid}: decision_refs must be list')
        elif any(x not in decision_ids for x in e['decision_refs']):
            fail(f'{eid}: unknown decision ref')
        if e.get('status') == 'CONFIRMED' and (not e.get('decision_refs') or any(x not in confirmed_decisions for x in e.get('decision_refs', []))):
            fail(f'{eid}: confirmed entity needs confirmed decision provenance')
        if not isinstance(d, dict):
            fail(f'{eid}: data must be object')
            continue
        for key in TEXT[kind]:
            if not text(d.get(key)):
                fail(f'{eid}: data.{key} must be nonempty text (use explicit unresolved text in drafts)')
        for key in TIME_KEYS:
            if key in d and not time_ok(d[key]):
                fail(f'{eid}: invalid time {key} (null, zoned ISO text or {{earliest, latest, label}})')
        check_world_fields(e, eid, version, fail)
        check_items(e, eid, index, fail)
        if kind == 'Knowledge':
            if not one_of(d.get('state'), {'KNOWS', 'BELIEVES', 'SUSPECTS', 'UNKNOWN'}):
                fail(f'{eid}: invalid knowledge state')
            if d.get('state') != 'UNKNOWN' and not d.get('acquired_via') and not d.get('initial_basis'):
                fail(f'{eid}: knowledge acquisition missing')
            start, stop = rules.safe_span(d.get('from')), rules.safe_span(d.get('until'))
            if rules.surely_after(start, stop) or (start and stop and start[0] is not None and start[0] == stop[1]):
                fail(f'{eid}: invalid knowledge interval')
        if kind == 'Claim' and not one_of(d.get('intent'), {'truthful', 'lie', 'mistaken', 'uncertain'}):
            fail(f'{eid}: invalid claim intent')
        if kind == 'Trace' and not one_of(d.get('origin_type'), {'event', 'routine', 'system'}):
            fail(f'{eid}: invalid trace origin')
        if kind == 'Choice':
            try:
                condition(d['available_when'], state)
                if not isinstance(d['options'], list) or len(d['options']) < 2:
                    raise ValueError('at least two options required')
                seen = set()
                for o in d['options']:
                    if not isinstance(o, dict) or not isinstance(o.get('id'), str) or not o.get('label') or o['id'] in seen:
                        raise ValueError('invalid/duplicate option')
                    seen.add(o['id'])
                    condition(o['condition'], state)
                    if not isinstance(o['effects'], dict):
                        raise ValueError('effects must be object')
                    for k, v in o['effects'].items():
                        if k not in state or type(v) is not type(state[k]):
                            raise ValueError('undeclared variable or effect type mismatch')
            except (KeyError, TypeError, ValueError) as exc:
                fail(f'{eid}: {exc}')
        if kind == 'Ending':
            try:
                condition(d['condition'], state)
                if type(d['exclusive']) is not bool:
                    raise ValueError('exclusive must be boolean')
                if not isinstance(d['witness'], list):
                    raise ValueError('witness must be list')
            except (KeyError, TypeError, ValueError) as exc:
                fail(f'{eid}: {exc}')
    for eid, e in index.items():
        if not one_of(e.get('kind'), KINDS) or not isinstance(e.get('data'), dict) or not isinstance(e.get('depends_on'), list):
            continue
        for ref in references(e):
            if ref not in index:
                fail(f'{eid}: dangling ref {ref}')
            elif not one_of(e.get('status'), {'SUPERSEDED', 'REJECTED'}) and one_of(index[ref].get('status'), {'SUPERSEDED', 'REJECTED'}):
                fail(f'{eid}: active reference to inactive {ref}')
        for key, allowed in REFS.get(e['kind'], {}).items():
            val = e['data'].get(key)
            if key in LIST_REFS and val is not None and not isinstance(val, list):
                fail(f'{eid}: {key} must be list')
            if val is None:
                continue
            vals = val if isinstance(val, list) else [val]
            if any(not isinstance(x, str) or x not in index or not one_of(index[x].get('kind'), allowed) for x in vals):
                fail(f'{eid}: wrong reference type {key}')
        for key in REQUIRED_REFS.get(e['kind'], []):
            if key not in e['data']:
                fail(f'{eid}: missing {key}')
    for link in ls:
        if not isinstance(link, dict):
            continue
        a = index.get(link.get('source')) if isinstance(link.get('source'), str) else None
        b = index.get(link.get('target')) if isinstance(link.get('target'), str) else None
        kind = link.get('kind')
        if not one_of(kind, LINKS) or not a or not b:
            fail('invalid/dangling link: ' + str(link.get('id')))
            continue
        sa, tb = LINKS[kind]
        if a['kind'] not in sa or b['kind'] not in tb:
            fail('invalid link endpoint types: ' + link['id'])
        if not link.get('reason'):
            fail('link needs reason: ' + link['id'])
    findings = rules.run(s, index, complete)
    for f in findings:
        (errors if f['level'] == 'ERROR' else warnings).append(rules.describe(f))
    if not errors:
        endings = [e for e in es if e['kind'] == 'Ending' and not one_of(e['status'], {'SUPERSEDED', 'REJECTED'})]
        for e in endings:
            try:
                endstate = walk(s, e['data']['witness'])
                if not condition(e['data']['condition'], endstate):
                    fail(e['id'] + ': witness does not reach ending')
                if e['data']['exclusive']:
                    hits = [x['id'] for x in endings if condition(x['data']['condition'], endstate)]
                    if len(hits) > 1:
                        fail(e['id'] + ': exclusive ending overlaps on witness: ' + ','.join(hits))
            except (KeyError, TypeError, ValueError) as exc:
                fail(e['id'] + ': ' + str(exc))
        if complete and len(endings) < 2:
            fail('completion needs at least two endings')
    for i in issues:
        if not isinstance(i, dict):
            continue
        if not one_of(i.get('severity'), {'BLOCKER', 'MAJOR', 'MINOR'}) or not one_of(i.get('status'), {'OPEN', 'RESOLVED', 'ACCEPTED'}):
            fail('invalid QA issue state')
        if any(x not in index for x in i.get('affected_ids', [])):
            fail('QA refers to unknown entity')
        if complete and i.get('severity') == 'BLOCKER' and i.get('status') != 'RESOLVED':
            fail('unresolved blocker: ' + i.get('id', '?'))
    if complete:
        active = [e for e in es if isinstance(e, dict) and not one_of(e.get('status'), {'SUPERSEDED', 'REJECTED'})]
        for kind in ['WorldRule', 'Organization', 'Service', 'Character', 'Event', 'Fact', 'Trace', 'Choice', 'Ending']:
            if not any(e.get('kind') == kind for e in active):
                fail('completion missing ' + kind)
        if any(e.get('status') != 'CONFIRMED' or e.get('review') != 'VALID' for e in active):
            fail('completion requires confirmed, reviewed active entities')
        if s.get('pending_decisions'):
            fail('completion has pending decisions; classify/defer peripheral items before finalization')
    warnings.append('Semantic causality, knowledge plausibility and full-path fairness require narrative review.')
    return {'errors': errors, 'warnings': warnings, 'findings': findings}


def impact(s, ids):
    index = {e['id']: e for e in s['entities']}
    if any(x not in index for x in ids):
        raise ValueError('unknown changed entity')
    graph = {k: set() for k in index}
    for e in index.values():
        for ref in references(e):
            if ref in graph:
                graph[ref].add(e['id'])
    for link in s['links']:
        a, b = link['source'], link['target']
        if link['kind'] == 'depends_on':
            a, b = b, a
        if a in graph:
            graph[a].add(b)
        # Evidence must be re-read when the claim or fact it bears on changes.
        if link['kind'] in BOTH_WAYS and b in graph:
            graph[b].add(a)
    seen = set(ids)
    queue = list(ids)
    while queue:
        for target in graph.get(queue.pop(0), set()):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return {'changed': sorted(ids), 'needs_review': sorted(seen - set(ids)), 'note': 'Explicit dependency closure; also review semantic dependencies.'}


# Headings already published in Notion pages must not change: the sync planner
# compares rendered text to detect human edits. Only add labels for new keys.
LABELS = {'statement': '내용', 'scope': '적용 범위', 'exceptions': '예외', 'grounding': '설정 근거', 'purpose': '존재 목적', 'economy': '재원과 사업', 'operations': '운영', 'culture': '문화', 'daily_life': '일상', 'identity': '정체성', 'motive': '동기', 'relationships': '관계', 'users': '사용자', 'normal_use': '정상 이용', 'data_lifecycle': '데이터 수명', 'permissions': '권한', 'failures': '실패와 지원', 'action': '행동', 'result': '결과', 'basis': '근거', 'summary': '기록 개요', 'access': '접근 경로', 'distortion': '왜곡', 'prompt': '선택 쟁점', 'known_information': '선택 당시의 정보', 'consequences': '결과',
          'description': '묘사', 'rhythm': '생활 리듬', 'public_account': '통념', 'definition': '정의', 'register': '사용 집단과 어조', 'structure': '구조와 의사결정', 'incentives': '평가와 보상', 'reputation': '평판', 'conflicts': '내부 갈등', 'formal_vs_actual': '공식 규정과 실제 관행', 'violation_cost': '위반 대가', 'routine': '일과', 'voice': '말투', 'cannot_know': '알 수 없는 것', 'rule_type': '규칙 유형', 'strength': '강도', 'place_type': '장소 유형', 'artifact_type': '기록 유형', 'state_at_present': '현재 상태', 'retention_exception': '보존 예외'}
KIND_LABELS = {'HistoryEvent': {'summary': '실제로 일어난 일', 'consequences': '현재에 남은 흔적'}, 'Location': {'access': '출입 조건'}}


def managed(e):
    labels = {**LABELS, **KIND_LABELS.get(e.get('kind'), {})}
    lines = [BEGIN, '### 설정 내용']
    for k, v in e.get('data', {}).items():
        if isinstance(v, str) and v and not k.endswith('_id'):
            lines.extend(['#### ' + labels.get(k, k), v])
    lines.extend(['### 구조화 원본', '```json', json.dumps(e, ensure_ascii=False, indent=2), '```', ''])
    return '\n'.join(lines)


def extract(body):
    if body.count(BEGIN) != 1 or body.count(END) != 1:
        raise ValueError('managed/user markers missing or ambiguous')
    a = body.index(BEGIN)
    b = body.index(END)
    if a >= b:
        raise ValueError('marker order invalid')
    part = body[a:b].strip()
    m = re.search(r'### 구조화 원본\n```json\n(.*)\n```$', part, re.S)
    if not m:
        raise ValueError('managed JSON block malformed')
    return json.loads(m.group(1)), body[a:b]


def empty_snapshot(project_id, version_id, title):
    return {
        'schema_version': 2, 'project_id': project_id, 'version_id': version_id, 'title': title, 'revision': 0,
        'charter': {'genre_tone': '', 'reality_distance': None, 'premise': '', 'scope_in': [], 'scope_out': '', 'timezone': '', 'present_at': None},
        'initial_state': {}, 'entities': [], 'links': [], 'decisions': [], 'issues': [], 'pending_decisions': [], 'session': {},
    }


def checked(s):
    report = validate(s)
    if report['errors']:
        raise ValueError('; '.join(report['errors']))
    return s


def main():
    import canon_migrate
    p = argparse.ArgumentParser(description=__doc__)
    sp = p.add_subparsers(dest='cmd', required=True)
    n = sp.add_parser('new')
    n.add_argument('--project-id', required=True)
    n.add_argument('--version-id', required=True)
    n.add_argument('--title', required=True)
    n.add_argument('--output', required=True)
    for name in ['validate', 'impact', 'render', 'migrate', 'bible', 'timeline', 'page']:
        q = sp.add_parser(name)
        q.add_argument('snapshot')
        if name == 'validate':
            q.add_argument('--complete', action='store_true')
        if name == 'impact':
            q.add_argument('ids', nargs='+')
        if name == 'render':
            q.add_argument('entity_id')
        if name == 'migrate':
            q.add_argument('--output', required=True)
        if name == 'timeline':
            q.add_argument('--character')
        if name == 'page':
            q.add_argument('page', choices=canon_views.PAGES)
    a = p.parse_args()
    if a.cmd == 'new':
        with open(a.output, 'x') as f:
            json.dump(empty_snapshot(a.project_id, a.version_id, a.title), f, ensure_ascii=False, indent=2)
        return
    s = read(a.snapshot)
    if a.cmd == 'validate':
        result = validate(s, a.complete)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(bool(result['errors']))
    if a.cmd == 'migrate':
        out = canon_migrate.migrate(s)
        with open(a.output, 'x') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        result = validate(out)
        print(json.dumps({'output': a.output, 'migration_issues': [i['id'] for i in out['issues'] if i.get('violated_rule') == 'MIGRATION'], **result}, ensure_ascii=False, indent=2))
        sys.exit(bool(result['errors']))
    checked(s)
    if a.cmd == 'impact':
        print(json.dumps(impact(s, a.ids), ensure_ascii=False, indent=2))
    elif a.cmd == 'render':
        e = next((e for e in s['entities'] if e['id'] == a.entity_id), None)
        if e is None:
            raise ValueError('entity not found')
        print(managed(e) + '\n' + END + '\n사용자가 직접 남기는 메모. 확정 설정 변경은 변경 요청으로 기록한다.\n')
    elif a.cmd == 'bible':
        print(canon_views.bible(s))
    elif a.cmd == 'timeline':
        print(canon_views.timeline(s, a.character))
    elif a.cmd == 'page':
        print(canon_views.page_summary(s, a.page, validate(s)))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
