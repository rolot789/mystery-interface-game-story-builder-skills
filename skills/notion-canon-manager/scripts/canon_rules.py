"""Consistency rules for Canon snapshots. Pure functions: no I/O, no network.

Each rule has a stable ID so QA Issues can cite it as violated_rule.
Time values are TimeSpecs: null, zoned ISO text, or {earliest, latest, label}.
Comparisons are conservative: a rule fires only when a violation is certain.
"""
import heapq
from collections import defaultdict
from datetime import datetime, timedelta

INACTIVE = {'SUPERSEDED', 'REJECTED'}
TIME_OF = {'Event': 'at', 'HistoryEvent': 'at', 'Trace': 'created_at', 'Claim': 'stated_at'}
CORE_FIELDS = {
    'WorldRule': ['rule_type', 'strength'],
    'Organization': ['founded_at', 'structure', 'incentives'],
    'Service': ['launched_at', 'retention', 'access_policy', 'artifacts'],
    'Location': ['place_type', 'connections'],
    'HistoryEvent': ['at'],
    'Term': ['aliases', 'forbidden_aliases'],
}
MAY_BE_EMPTY = {'connections', 'aliases', 'forbidden_aliases'}
RULES = []


def rule(rule_id, level):
    def register(fn):
        RULES.append((rule_id, level, fn))
        return fn
    return register


def instant(text):
    if not isinstance(text, str):
        raise ValueError('timestamp must be text')
    d = datetime.fromisoformat(text.replace('Z', '+00:00'))
    if d.tzinfo is None:
        raise ValueError('timestamp requires timezone')
    return d


def span(value):
    """Parse a TimeSpec into (earliest, latest). None means undecided; a None bound is open."""
    if value is None:
        return None
    if isinstance(value, str):
        d = instant(value)
        return (d, d)
    if isinstance(value, dict) and value and set(value) <= {'earliest', 'latest', 'label'}:
        lo = instant(value['earliest']) if value.get('earliest') is not None else None
        hi = instant(value['latest']) if value.get('latest') is not None else None
        if lo is None and hi is None:
            raise ValueError('time range needs earliest or latest')
        if lo and hi and lo > hi:
            raise ValueError('time range earliest is after latest')
        if 'label' in value and not isinstance(value['label'], str):
            raise ValueError('time label must be text')
        return (lo, hi)
    raise ValueError('time must be null, zoned ISO text or {earliest, latest, label}')


def safe_span(value):
    try:
        return span(value)
    except (TypeError, ValueError, AttributeError):
        return None


def surely_after(a, b):
    """True only when every moment of span a is later than every moment of span b."""
    return bool(a and b and a[0] is not None and b[1] is not None and a[0] > b[1])


def ids(value):
    return [x for x in value if isinstance(x, str)] if isinstance(value, list) else []


def items_of(value):
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def strs(value):
    return [x.strip() for x in value if isinstance(x, str) and x.strip()] if isinstance(value, list) else []


def norm(text):
    return ' '.join(str(text).split()).casefold()


def texts(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for x in value:
            yield from texts(x)
    elif isinstance(value, dict):
        for x in value.values():
            yield from texts(x)


def cycles(graph):
    """Return each cycle found by depth-first search as a closed path."""
    color, found = {}, []
    for start in graph:
        if start in color:
            continue
        color[start] = 1
        path, stack = [start], [(start, iter(graph[start]))]
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                stack.pop()
                path.pop()
                color[node] = 2
            elif color.get(nxt) == 1:
                found.append(path[path.index(nxt):] + [nxt])
            elif nxt not in color and nxt in graph:
                color[nxt] = 1
                path.append(nxt)
                stack.append((nxt, iter(graph[nxt])))
    return found


class Context:
    def __init__(self, snapshot, index):
        self.s = snapshot
        self.index = index
        self.active = {k: e for k, e in index.items() if not (isinstance(e.get('status'), str) and e['status'] in INACTIVE)}
        charter = snapshot.get('charter')
        self.charter = charter if isinstance(charter, dict) else {}
        self.present = safe_span(self.charter.get('present_at'))
        self.links = [x for x in snapshot.get('links', []) if isinstance(x, dict)]
        self._travel = None

    def data(self, e):
        return e.get('data') if isinstance(e, dict) and isinstance(e.get('data'), dict) else {}

    def of(self, *kinds):
        return [e for e in self.active.values() if e.get('kind') in kinds]

    def get(self, id_, kinds=None):
        e = self.index.get(id_) if isinstance(id_, str) else None
        return e if e and (kinds is None or e.get('kind') in kinds) else None

    def when(self, e, key=None):
        return safe_span(self.data(e).get(key or TIME_OF.get(e.get('kind') if e else None, '')))

    def ancestors(self, loc_id):
        chain, seen = [], set()
        while isinstance(loc_id, str) and loc_id in self.index and loc_id not in seen:
            seen.add(loc_id)
            chain.append(loc_id)
            loc_id = self.data(self.index[loc_id]).get('parent_id')
        return chain

    def travel(self, a, b):
        """Shortest known travel minutes between two places; 0 when one contains the other."""
        up_a, up_b = self.ancestors(a), self.ancestors(b)
        if a in up_b or b in up_a:
            return 0
        # Search only below the lowest common ancestor: two rooms in one building are not 0 minutes apart.
        shared = set(up_a) & set(up_b)
        up_a, up_b = [x for x in up_a if x not in shared], [x for x in up_b if x not in shared]
        if self._travel is None:
            self._travel = defaultdict(list)
            for loc in self.of('Location'):
                for c in items_of(self.data(loc).get('connections')):
                    if isinstance(c, dict) and isinstance(c.get('minutes'), (int, float)) and c.get('to') in self.index:
                        self._travel[loc['id']].append((c['to'], c['minutes']))
                        self._travel[c['to']].append((loc['id'], c['minutes']))
        targets, best = set(up_b), {x: 0 for x in up_a}
        heap = [(0, x) for x in up_a]
        while heap:
            cost, node = heapq.heappop(heap)
            if node in targets:
                return cost
            if cost > best.get(node, cost):
                continue
            for nxt, minutes in self._travel.get(node, []):
                if cost + minutes < best.get(nxt, float('inf')):
                    best[nxt] = cost + minutes
                    heapq.heappush(heap, (cost + minutes, nxt))
        return None


@rule('TIME-001', 'ERROR')
def past_before_present(ctx, complete):
    for e in ctx.of('Event', 'HistoryEvent'):
        if surely_after(ctx.when(e), ctx.present):
            yield [e['id']], 'past event is later than charter.present_at'


@rule('TIME-002', 'ERROR')
def preconditions_in_order(ctx, complete):
    for e in ctx.of('Event', 'HistoryEvent'):
        for ref in ids(ctx.data(e).get('preconditions')):
            p = ctx.get(ref, {'Event', 'HistoryEvent'})
            if p and surely_after(ctx.when(p), ctx.when(e)):
                yield [e['id'], ref], f'precondition {ref} occurs after the event'


@rule('TIME-003', 'ERROR')
def trace_after_origin(ctx, complete):
    for e in ctx.of('Trace'):
        t = ctx.when(e)
        origins = [ctx.when(o) for o in map(lambda r: ctx.get(r, {'Event', 'HistoryEvent'}), ids(ctx.data(e).get('origin_ids'))) if o]
        origins = [o for o in origins if o]
        if t and origins and all(surely_after(o, t) for o in origins):
            yield [e['id']], 'trace created before its origin event'


@rule('TIME-004', 'ERROR')
def knowledge_after_source(ctx, complete):
    for e in ctx.of('Knowledge'):
        start = ctx.when(e, 'from')
        sources = [ctx.when(src) for src in map(ctx.get, ids(ctx.data(e).get('acquired_via'))) if src]
        sources = [x for x in sources if x]
        if start and sources and all(surely_after(x, start) for x in sources):
            yield [e['id']], 'knowledge starts before any acquisition source exists'


@rule('TIME-005', 'ERROR')
def exists_before_use(ctx, complete):
    for e in ctx.of('Trace'):
        svc = ctx.get(ctx.data(e).get('service_id'), {'Service'})
        if svc and surely_after(ctx.when(svc, 'launched_at'), ctx.when(e)):
            yield [e['id'], svc['id']], f'trace created before service {svc["id"]} launched'
    for e in ctx.of('Event'):
        for a in ids(ctx.data(e).get('actors')):
            actor = ctx.get(a, {'Organization', 'Service'})
            key = 'founded_at' if actor and actor['kind'] == 'Organization' else 'launched_at'
            if actor and surely_after(ctx.when(actor, key), ctx.when(e)):
                yield [e['id'], a], f'actor {a} did not exist yet'
    for svc in ctx.of('Service'):
        org = ctx.get(ctx.data(svc).get('provider_id'), {'Organization'})
        if org and surely_after(ctx.when(org, 'founded_at'), ctx.when(svc, 'launched_at')):
            yield [svc['id'], org['id']], f'service launched before provider {org["id"]} was founded'


@rule('TIME-006', 'ERROR')
def rule_in_force(ctx, complete):
    for e in ctx.of('Event'):
        t = ctx.when(e)
        for ref in ids(ctx.data(e).get('preconditions')):
            r = ctx.get(ref, {'WorldRule'})
            if r and (surely_after(ctx.when(r, 'valid_from'), t) or surely_after(t, ctx.when(r, 'valid_until'))):
                yield [e['id'], ref], f'rule {ref} is not in force at the event time'


@rule('TIME-007', 'WARNING')
def affiliation_covers_action(ctx, complete):
    for e in ctx.of('Event'):
        t, actors = ctx.when(e), ids(ctx.data(e).get('actors'))
        orgs = [a for a in actors if ctx.get(a, {'Organization'})]
        for c in filter(None, (ctx.get(a, {'Character'}) for a in actors)):
            affs = items_of(ctx.data(c).get('affiliations'))
            if not affs:
                continue
            for org in orgs:
                terms = [(safe_span(x.get('from')), safe_span(x.get('until'))) for x in affs if x.get('org_id') == org]
                if not terms:
                    yield [e['id'], c['id'], org], f'{c["id"]} acts with {org} without an affiliation'
                elif all(surely_after(f, t) or surely_after(t, u) for f, u in terms):
                    yield [e['id'], c['id'], org], f'affiliation of {c["id"]} with {org} does not cover the event time'


@rule('GRAPH-001', 'ERROR')
def no_cycles(ctx, complete):
    deps = {k: [x for x in ids(e.get('depends_on')) + ids(ctx.data(e).get('preconditions')) if x in ctx.index] for k, e in ctx.index.items()}
    for cycle in cycles(deps):
        yield cycle[:-1], 'dependency cycle: ' + ' -> '.join(cycle)
    parents = {e['id']: [ctx.data(e).get('parent_id')] for e in ctx.index.values() if e.get('kind') == 'Organization' and ctx.get(ctx.data(e).get('parent_id'), {'Organization'})}
    for cycle in cycles(parents):
        yield cycle[:-1], 'organization hierarchy cycle: ' + ' -> '.join(cycle)


@rule('SPACE-001', 'ERROR')
def location_hierarchy(ctx, complete):
    parents = {e['id']: [ctx.data(e).get('parent_id')] for e in ctx.index.values() if e.get('kind') == 'Location' and ctx.get(ctx.data(e).get('parent_id'), {'Location'})}
    for cycle in cycles(parents):
        yield cycle[:-1], 'location hierarchy cycle: ' + ' -> '.join(cycle)


def placed_events(ctx):
    by_actor = defaultdict(list)
    for e in ctx.of('Event'):
        d, t = ctx.data(e), ctx.when(e)
        loc = ctx.get(d.get('location_id'), {'Location'})
        if not t or t[0] is None or t[0] != t[1] or not loc:
            continue
        minutes = d.get('duration_minutes') if isinstance(d.get('duration_minutes'), (int, float)) else 0
        for a in ids(d.get('actors')):
            if ctx.get(a, {'Character'}):
                by_actor[a].append((t[0], t[0] + timedelta(minutes=minutes), loc['id'], e['id']))
    return by_actor


@rule('SPACE-002', 'ERROR')
def one_place_at_a_time(ctx, complete):
    for actor, items in placed_events(ctx).items():
        items.sort()
        for i, (s1, e1, l1, id1) in enumerate(items):
            for s2, e2, l2, id2 in items[i + 1:]:
                if (s2 < e1 or s1 == s2) and ctx.travel(l1, l2) != 0:
                    yield [id1, id2, actor], f'{actor} is in {l1} and {l2} at the same time'


@rule('SPACE-003', 'WARNING')
def travel_time(ctx, complete):
    for actor, items in placed_events(ctx).items():
        items.sort()
        for (s1, e1, l1, id1), (s2, e2, l2, id2) in zip(items, items[1:]):
            if s2 < e1 or s1 == s2:
                continue
            need = ctx.travel(l1, l2)
            if need and (s2 - e1) < timedelta(minutes=need):
                yield [id1, id2, actor], f'{actor} needs {need} minutes from {l1} to {l2} but has {int((s2 - e1).total_seconds() // 60)}'


@rule('DATA-001', 'ERROR')
def retention_allows_trace(ctx, complete):
    if not ctx.present:
        return
    for e in ctx.of('Trace'):
        d, t = ctx.data(e), ctx.when(e)
        if d.get('state_at_present', 'PRESENT') != 'PRESENT' or (isinstance(d.get('retention_exception'), str) and d['retention_exception'].strip()):
            continue
        svc = ctx.get(d.get('service_id'), {'Service'})
        if not svc or not t or t[1] is None or not d.get('artifact_type'):
            continue
        for r in items_of(ctx.data(svc).get('retention')):
            if isinstance(r, dict) and r.get('data') == d['artifact_type'] and r.get('after') == 'HARD_DELETE' and type(r.get('keep_days')) is int:
                expiry = t[1] + timedelta(days=r['keep_days'])
                if surely_after(ctx.present, (expiry, expiry)):
                    yield [e['id'], svc['id']], f'{d["artifact_type"]} is hard-deleted after {r["keep_days"]} days under {svc["id"]}, before present_at'


@rule('DATA-002', 'WARNING')
def artifact_declared(ctx, complete):
    for e in ctx.of('Trace'):
        d = ctx.data(e)
        svc = ctx.get(d.get('service_id'), {'Service'})
        if svc and d.get('artifact_type'):
            declared = [a.get('type') for a in items_of(ctx.data(svc).get('artifacts'))]
            if d['artifact_type'] not in declared:
                yield [e['id'], svc['id']], f'artifact type {d["artifact_type"]} is not declared by {svc["id"]}'


@rule('TERM-001', 'WARNING')
def forbidden_alias_used(ctx, complete):
    for term in ctx.of('Term'):
        for alias in strs(ctx.data(term).get('forbidden_aliases')):
            needle = alias.casefold()
            for e in ctx.active.values():
                if e is not term and any(needle in x.casefold() for x in texts([e.get('title'), e.get('data')])):
                    yield [e['id'], term['id']], f'forbidden alias "{alias}" of {term.get("title")} appears'


@rule('TERM-002', 'WARNING')
def names_unique(ctx, complete):
    seen = {}
    for e in ctx.active.values():
        key = (e.get('kind'), norm(e.get('title', '')))
        if key in seen:
            yield [seen[key], e['id']], f'duplicate {e.get("kind")} title "{e.get("title")}"'
        seen.setdefault(key, e['id'])
    names = {}
    for term in ctx.of('Term'):
        for name in [term.get('title', '')] + strs(ctx.data(term).get('aliases')):
            other = names.setdefault(norm(name), term['id'])
            if other != term['id']:
                yield [other, term['id']], f'name "{name}" belongs to two terms'
    for term in ctx.of('Term'):
        for alias in strs(ctx.data(term).get('forbidden_aliases')):
            other = names.get(norm(alias))
            if other and other != term['id']:
                yield [term['id'], other], f'forbidden alias "{alias}" is an accepted name of {other}'


@rule('WORLD-001', 'ERROR')
def charter_scope(ctx, complete):
    if ctx.s.get('schema_version') != 2:
        return
    for x in ids(ctx.charter.get('scope_in')):
        if x not in ctx.index:
            yield [], f'charter.scope_in refers to unknown {x}'
        elif complete and x not in ctx.active:
            yield [x], f'charter.scope_in entity {x} is inactive'
    if complete:
        for key in ['reality_distance', 'premise', 'present_at']:
            if not ctx.charter.get(key):
                yield [], f'completion needs charter.{key}'


@rule('WORLD-002', 'ERROR')
def core_is_detailed(ctx, complete):
    if not complete:
        return
    for e in ctx.active.values():
        if e.get('depth') != 'CORE':
            continue
        d = ctx.data(e)
        for key in CORE_FIELDS.get(e.get('kind'), []):
            v = d.get(key)
            if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v and key not in MAY_BE_EMPTY):
                yield [e['id']], f'CORE {e["kind"]} needs {key}'


@rule('WORLD-003', 'ERROR')
def plot_need_justified(ctx, complete):
    for e in ctx.active.values():
        if e.get('origin') == 'PLOT_NEED' and not (isinstance(e.get('in_world_reason'), str) and e['in_world_reason'].strip()):
            yield [e['id']], 'PLOT_NEED setting needs in_world_reason'


@rule('WORLD-004', 'WARNING')
def exploited_rule_has_gap(ctx, complete):
    for link in ctx.links:
        r = ctx.get(link.get('target'), {'WorldRule'})
        if link.get('kind') == 'exploits' and r and ctx.data(r).get('strength') == 'HARD':
            yield [link.get('source'), r['id']], f'HARD rule {r["id"]} is exploited; describe the gap in exceptions or mark it SOFT'


@rule('FAIR-001', 'WARNING')
def hidden_rule_is_exposed(ctx, complete):
    used = {x.get('target') for x in ctx.links if x.get('kind') == 'exploits'}
    for e in ctx.of('Event'):
        used.update(ids(ctx.data(e).get('preconditions')))
    exposed = set()
    for t in ctx.of('Trace'):
        exposed.update(ids(ctx.data(t).get('origin_ids')))
    for x in ctx.links:
        for a, b in [(x.get('source'), x.get('target')), (x.get('target'), x.get('source'))]:
            if ctx.get(a, {'Trace'}):
                exposed.add(b)
    for rid in sorted(x for x in used if isinstance(x, str)):
        r = ctx.get(rid, {'WorldRule'})
        if r and rid in ctx.active and r.get('visibility') in {'SECRET', 'INSIDER'} and rid not in exposed:
            yield [rid], f'{r.get("visibility")} rule used by the solution has no linked Trace the player can find'


@rule('CLAIM-001', 'WARNING')
def lie_needs_knowledge(ctx, complete):
    for c in ctx.of('Claim'):
        d = ctx.data(c)
        speaker = ctx.get(d.get('speaker_id'), {'Character'})
        if d.get('intent') != 'lie' or not speaker:
            continue
        facts = ids(d.get('fact_ids'))
        if not facts:
            yield [c['id']], 'lie has no fact_ids; name the truth the speaker hides'
            continue
        t = ctx.when(c)
        known = [k for k in ctx.of('Knowledge')
                 if ctx.data(k).get('character_id') == speaker['id'] and ctx.data(k).get('fact_id') in facts
                 and ctx.data(k).get('state') in {'KNOWS', 'BELIEVES', 'SUSPECTS'}
                 and not surely_after(ctx.when(k, 'from'), t) and not surely_after(t, ctx.when(k, 'until'))]
        if not known:
            yield [c['id'], speaker['id']], f'{speaker["id"]} has no knowledge of the related facts when lying'


@rule('LINK-001', 'WARNING')
def knows_deprecated(ctx, complete):
    for link in ctx.links:
        if link.get('kind') == 'knows':
            yield [x for x in [link.get('source'), link.get('target')] if x in ctx.index], f'knows link {link.get("id")} is deprecated; record a Knowledge entity instead'


def describe(f):
    return f'{f["rule"]} {f["ids"][0] if f["ids"] else "snapshot"}: {f["message"]}'


def run(snapshot, index, complete=False):
    ctx = Context(snapshot, index)
    findings = []
    for rule_id, level, fn in RULES:
        try:
            for found_ids, message in fn(ctx, complete):
                findings.append({'rule': rule_id, 'level': level, 'ids': found_ids, 'message': message})
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            findings.append({'rule': rule_id, 'level': 'ERROR', 'ids': [], 'message': 'rule could not run on malformed data: ' + str(exc)})
    return findings
