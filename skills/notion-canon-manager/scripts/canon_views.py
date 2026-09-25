"""Readable Markdown views computed from a Canon snapshot.

Weekdays and elapsed time are derived from stored anchors here so that
prose never has to carry a hand-computed date.
"""
import canon_rules as rules

WEEKDAYS = '월화수목금토일'
DRAFT = {'DRAFT', 'PROPOSED'}


def cell(value):
    text = '' if value is None else str(value)
    first = text.strip().split('\n')[0]
    return (first[:80] + '…' if len(first) > 80 else first).replace('|', '\\|')


def table(headers, rows):
    out = ['| ' + ' | '.join(headers) + ' |', '|' + '---|' * len(headers)]
    out += ['| ' + ' | '.join(cell(x) for x in row) + ' |' for row in rows]
    return out if rows else ['(없음)']


def moment(d):
    return f'{d:%Y-%m-%d} ({WEEKDAYS[d.weekday()]}) {d:%H:%M} UTC{d.isoformat()[19:] or "+00:00"}'


def show(value):
    s = rules.safe_span(value)
    if not s:
        return '시기 미정'
    lo, hi = s
    if lo is not None and lo == hi:
        return moment(lo)
    label = value.get('label') if isinstance(value, dict) else None
    bounds = f'{lo:%Y-%m-%d}' if lo else '?', f'{hi:%Y-%m-%d}' if hi else '?'
    return f'{label} ({bounds[0]} ~ {bounds[1]})' if label else f'{bounds[0]} ~ {bounds[1]}'


def ago(days):
    if days is None:
        return '?'
    return f'{days}일 전' + (f' (약 {days // 365}년)' if days >= 365 else '') if days >= 0 else f'{-days}일 후'


def elapsed(value, present):
    s = rules.safe_span(value)
    if not s or not present:
        return ''
    early = (present[0] - s[1]).days if present[0] and s[1] else None
    late = (present[1] - s[0]).days if present[1] and s[0] else None
    return ago(early) if early == late else f'{ago(early)} ~ {ago(late)}'


def sort_key(value):
    s = rules.safe_span(value)
    bound = s and (s[0] or s[1])
    return (0, bound.timestamp()) if bound else (1, 0)


class View:
    def __init__(self, s):
        self.s = s
        self.charter = s.get('charter') if isinstance(s.get('charter'), dict) else {}
        self.present = rules.safe_span(self.charter.get('present_at'))
        self.active = [e for e in s['entities'] if e.get('status') not in rules.INACTIVE]
        self.index = {e['id']: e for e in s['entities']}

    def of(self, kind):
        return [e for e in self.active if e.get('kind') == kind]

    def name(self, id_):
        e = self.index.get(id_) if isinstance(id_, str) else None
        if not e:
            return id_ or ''
        return e['title'] + (' (제안)' if e.get('status') in DRAFT else '')

    def dated(self, rows):
        rows.sort(key=lambda r: sort_key(r[0]))
        return [[show(t), elapsed(t, self.present), *rest] for t, *rest in rows]


def bible(s):
    v = View(s)
    c = v.charter
    out = [f'# {s["title"]} — 세계 바이블', '', f'버전 {s["version_id"]} · 리비전 {s["revision"]} · 조사 현재 시점 {show(c.get("present_at"))}', '',
           '고정점에서 계산한 요약이다. 요일과 경과 기간은 서술에 직접 적지 말고 이 출력을 인용한다. (제안)은 아직 확정되지 않은 설정이다.', '']
    out += ['## 세계 헌장', ''] + table(['항목', '내용'], [
        ['장르와 톤', c.get('genre_tone')], ['현실 거리', c.get('reality_distance') or '미정'], ['핵심 전제', c.get('premise')],
        ['포함 범위', ', '.join(v.name(x) for x in c.get('scope_in') or [])], ['제외 범위', c.get('scope_out')], ['기본 시간대', c.get('timezone')]]) + ['']
    rows, undated = [], []
    for e in v.of('HistoryEvent'):
        (rows if e['data'].get('at') else undated).append([e['data'].get('at'), v.name(e['id']), e['data'].get('summary')])
    for e in v.of('Organization'):
        if e['data'].get('founded_at'):
            rows.append([e['data']['founded_at'], '설립: ' + v.name(e['id']), e['data'].get('purpose')])
    for e in v.of('Service'):
        if e['data'].get('launched_at'):
            rows.append([e['data']['launched_at'], '출시: ' + v.name(e['id']), e['data'].get('purpose')])
        for ch in e['data'].get('changes') or []:
            rows.append([ch.get('at'), '변경: ' + v.name(e['id']), ch.get('summary')])
    for e in v.of('WorldRule'):
        for key, label in [('valid_from', '시행: '), ('valid_until', '종료: ')]:
            if e['data'].get(key):
                rows.append([e['data'][key], label + v.name(e['id']), e['data'].get('statement')])
    out += ['## 연표', ''] + table(['시기', '현재 기준', '항목', '내용'], v.dated(rows))
    if undated:
        out += ['', '시기 미정: ' + ', '.join(r[1] for r in undated)]
    out += ['', '## 장소', '']
    locations = v.of('Location')
    children = {}
    for e in locations:
        children.setdefault(e['data'].get('parent_id') if e['data'].get('parent_id') in v.index else None, []).append(e)

    def tree(parent, depth, seen):
        for e in sorted(children.get(parent, []), key=lambda x: x['title']):
            if e['id'] in seen:
                continue
            links = ', '.join(f'{v.name(x.get("to"))} {x.get("mode", "")} {x.get("minutes")}분'.replace('  ', ' ') for x in e['data'].get('connections') or [])
            out.append('  ' * depth + f'- **{v.name(e["id"])}**' + (f' ({e["data"]["place_type"]})' if e['data'].get('place_type') else '') + f' — 출입: {cell(e["data"].get("access"))}' + (f' · 연결: {links}' if links else ''))
            tree(e['id'], depth + 1, seen | {e['id']})
    tree(None, 0, frozenset())
    if not locations:
        out.append('(없음)')
    out += ['', '## 조직', ''] + table(['조직', '상위', '설립', '본거지', '밀도·공개도'], [
        [v.name(e['id']), v.name(e['data'].get('parent_id')), show(e['data'].get('founded_at')) if e['data'].get('founded_at') else '', v.name(e['data'].get('hq_location_id')), f'{e.get("depth", "")} {e.get("visibility", "")}']
        for e in v.of('Organization')])
    out += ['', '## 규칙', ''] + table(['규칙', '유형', '강도', '유효', '집행', '공개도'], [
        [v.name(e['id']), e['data'].get('rule_type', ''), e['data'].get('strength', ''),
         (show(e['data'].get('valid_from')) if e['data'].get('valid_from') else '') + (' ~ ' + show(e['data'].get('valid_until')) if e['data'].get('valid_until') else ''),
         ', '.join(v.name(x) for x in e['data'].get('enforced_by') or []), e.get('visibility', '')]
        for e in v.of('WorldRule')])
    out += ['', '## 정보 환경', '']
    for e in v.of('Service'):
        d = e['data']
        out += [f'### {v.name(e["id"])}', '', f'제공: {v.name(d.get("provider_id"))} · 출시: {show(d.get("launched_at")) if d.get("launched_at") else "미정"}', '']
        out += table(['데이터', '보존', '만료 후'], [[r.get('data'), '영구' if r.get('keep_days') is None else f'{r["keep_days"]}일', r.get('after') or '해당 없음'] for r in d.get('retention') or []]) + ['']
        out += table(['역할', '데이터', '허용', '조건'], [[r.get('role'), r.get('data'), ', '.join(r.get('ops') or []), r.get('condition', '')] for r in d.get('access_policy') or []]) + ['']
        out += table(['기록 유형', '시각 기준', '수정 흔적', '삭제 흔적', '읽음 표시'], [[a.get('type'), a.get('timestamp_source', ''), a.get('edit_trace', ''), a.get('delete_trace', ''), a.get('read_receipt', '')] for a in d.get('artifacts') or []]) + ['']
    if not v.of('Service'):
        out += ['(없음)', '']
    out += ['## 용어집', ''] + table(['표기', '정의', '사용 집단', '허용 별칭', '금지 별칭'], [
        [v.name(e['id']), e['data'].get('definition'), e['data'].get('register'), ', '.join(e['data'].get('aliases') or []), ', '.join(e['data'].get('forbidden_aliases') or [])]
        for e in sorted(v.of('Term'), key=lambda x: x['title'])])
    out += ['', '## 공개도별 설정', '']
    for level, label in [('PUBLIC', '주민 상식'), ('INSIDER', '내부자 지식'), ('SECRET', '비밀')]:
        names = [v.name(e['id']) for e in v.active if e.get('visibility') == level]
        out.append(f'- **{label}**: ' + (', '.join(names) if names else '(없음)'))
    return '\n'.join(out) + '\n'


def timeline(s, character=None):
    v = View(s)
    if character and character not in v.index:
        raise ValueError('unknown character: ' + character)
    rows = []
    for e in v.active:
        d, kind = e['data'], e['kind']
        if kind == 'Event' and (not character or character in (d.get('actors') or [])):
            rows.append([d.get('at'), '사건', v.name(e['id']), v.name(d.get('location_id')), ', '.join(v.name(x) for x in d.get('actors') or [])])
        elif kind == 'HistoryEvent' and not character:
            rows.append([d.get('at'), '역사', v.name(e['id']), '', ''])
        elif kind == 'Trace' and (not character or d.get('author_id') == character):
            rows.append([d.get('created_at'), '기록', v.name(e['id']), v.name(d.get('service_id')), v.name(d.get('author_id'))])
        elif kind == 'Claim' and (not character or d.get('speaker_id') == character):
            rows.append([d.get('stated_at'), f'발언({d.get("intent")})', v.name(e['id']), d.get('audience'), v.name(d.get('speaker_id'))])
        elif kind == 'Knowledge' and (not character or d.get('character_id') == character):
            rows.append([d.get('from'), f'앎 시작({d.get("state")})', v.name(d.get('fact_id')), '', v.name(d.get('character_id'))])
        elif kind == 'Character' and character == e['id']:
            for a in d.get('affiliations') or []:
                rows.append([a.get('from'), '소속 시작', f'{v.name(a.get("org_id"))} {a.get("role", "")}', '', ''])
                if a.get('until'):
                    rows.append([a.get('until'), '소속 종료', v.name(a.get('org_id')), '', ''])
    title = f'# {s["title"]} — 시간선' + (f': {v.name(character)}' if character else '')
    return '\n'.join([title, '', f'조사 현재 시점 {show(v.charter.get("present_at"))}', ''] + table(['시기', '현재 기준', '종류', '항목', '장소·청중·서비스', '관련 인물'], v.dated(rows))) + '\n'
