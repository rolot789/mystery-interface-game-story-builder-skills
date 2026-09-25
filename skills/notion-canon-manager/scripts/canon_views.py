"""Readable views computed from a Canon snapshot.

Weekdays and elapsed time are derived from stored anchors here so that
prose never has to carry a hand-computed date. Each view is built once as a
small document model and rendered either as GitHub Markdown (bible,
timeline) or as Notion-flavored Markdown (page summaries).
"""
import canon_rules as rules

WEEKDAYS = '월화수목금토일'
DRAFT = {'DRAFT', 'PROPOSED'}
PAGES = ['hub', 'workshop', 'world', 'characters', 'truth', 'investigation']
NOTION_ESCAPE = set('\\*~`$[]<>{}|^')
SEVERITY_ORDER = {'BLOCKER': 0, 'MAJOR': 1, 'MINOR': 2}


class Doc:
    """Blocks: ('h', level, text), ('p', text), ('table', headers, rows), ('tree', [(depth, bold, rest)])."""
    def __init__(self):
        self.blocks = []

    def h(self, level, text):
        self.blocks.append(('h', level, text))

    def p(self, text):
        self.blocks.append(('p', text))

    def table(self, headers, rows):
        self.blocks.append(('table', headers, rows))

    def tree(self, items):
        self.blocks.append(('tree', items))


def cell(value, limit=80):
    text = '' if value is None else str(value)
    first = text.strip().split('\n')[0]
    return first[:limit] + '…' if len(first) > limit else first


def markdown(doc):
    out = []
    for block in doc.blocks:
        kind = block[0]
        if kind == 'h':
            out += ['#' * block[1] + ' ' + block[2], '']
        elif kind == 'p':
            out += [block[1], '']
        elif kind == 'table':
            headers, rows = block[1], block[2]
            if rows:
                out += ['| ' + ' | '.join(headers) + ' |', '|' + '---|' * len(headers)]
                out += ['| ' + ' | '.join(cell(x).replace('|', '\\|') for x in row) + ' |' for row in rows]
            else:
                out.append('(없음)')
            out.append('')
        elif kind == 'tree':
            out += ['  ' * d + '- ' + (f'**{b}**' if b else '') + r for d, b, r in block[1]] or ['(없음)']
            out.append('')
    return '\n'.join(out).rstrip('\n') + '\n'


def esc(text):
    return ''.join('\\' + c if c in NOTION_ESCAPE else c for c in str(text))


def notion(doc):
    """Notion-flavored Markdown: tab indentation, <table> blocks, escaped rich text."""
    out = []
    for block in doc.blocks:
        kind = block[0]
        if kind == 'h':
            out.append('#' * min(block[1], 4) + ' ' + esc(block[2]))
        elif kind == 'p':
            out.append(esc(block[1]))
        elif kind == 'table':
            headers, rows = block[1], block[2]
            if not rows:
                out.append('(없음)')
                continue
            out.append('<table header-row="true">')
            for row in [headers] + rows:
                out.append('\t<tr>')
                out += ['\t\t<td>' + esc(cell(x, 300)) + '</td>' for x in row]
                out.append('\t</tr>')
            out.append('</table>')
        elif kind == 'tree':
            out += ['\t' * d + '- ' + (f'**{esc(b)}**' if b else '') + esc(r) for d, b, r in block[1]] or ['(없음)']
    return '\n'.join(out) + '\n'


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

    def names(self, ids):
        return ', '.join(self.name(x) for x in ids or [])

    def dated(self, rows):
        rows.sort(key=lambda r: sort_key(r[0]))
        return [[show(t), elapsed(t, self.present), *rest] for t, *rest in rows]


def world_sections(doc, v, level):
    c = v.charter
    doc.h(level, '세계 헌장')
    doc.table(['항목', '내용'], [
        ['장르와 톤', c.get('genre_tone')], ['현실 거리', c.get('reality_distance') or '미정'], ['핵심 전제', c.get('premise')],
        ['포함 범위', v.names(c.get('scope_in'))], ['제외 범위', c.get('scope_out')], ['기본 시간대', c.get('timezone')]])
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
    doc.h(level, '연표')
    doc.table(['시기', '현재 기준', '항목', '내용'], v.dated(rows))
    if undated:
        doc.p('시기 미정: ' + ', '.join(r[1] for r in undated))
    doc.h(level, '장소')
    locations = v.of('Location')
    children = {}
    for e in locations:
        children.setdefault(e['data'].get('parent_id') if e['data'].get('parent_id') in v.index else None, []).append(e)
    items = []

    def walk(parent, depth, seen):
        for e in sorted(children.get(parent, []), key=lambda x: x['title']):
            if e['id'] in seen:
                continue
            links = ', '.join(f'{v.name(x.get("to"))} {x.get("mode", "")} {x.get("minutes")}분'.replace('  ', ' ') for x in e['data'].get('connections') or [])
            items.append((depth, v.name(e['id']), (f' ({e["data"]["place_type"]})' if e['data'].get('place_type') else '') + f' — 출입: {cell(e["data"].get("access"))}' + (f' · 연결: {links}' if links else '')))
            walk(e['id'], depth + 1, seen | {e['id']})
    walk(None, 0, frozenset())
    doc.tree(items)
    doc.h(level, '조직')
    doc.table(['조직', '상위', '설립', '본거지', '밀도·공개도'], [
        [v.name(e['id']), v.name(e['data'].get('parent_id')), show(e['data'].get('founded_at')) if e['data'].get('founded_at') else '', v.name(e['data'].get('hq_location_id')), f'{e.get("depth", "")} {e.get("visibility", "")}']
        for e in v.of('Organization')])
    doc.h(level, '규칙')
    doc.table(['규칙', '유형', '강도', '유효', '집행', '공개도'], [
        [v.name(e['id']), e['data'].get('rule_type', ''), e['data'].get('strength', ''),
         (show(e['data'].get('valid_from')) if e['data'].get('valid_from') else '') + (' ~ ' + show(e['data'].get('valid_until')) if e['data'].get('valid_until') else ''),
         v.names(e['data'].get('enforced_by')), e.get('visibility', '')]
        for e in v.of('WorldRule')])
    doc.h(level, '정보 환경')
    if not v.of('Service'):
        doc.p('(없음)')
    for e in v.of('Service'):
        d = e['data']
        doc.h(level + 1, v.name(e['id']))
        doc.p(f'제공: {v.name(d.get("provider_id"))} · 출시: {show(d.get("launched_at")) if d.get("launched_at") else "미정"}')
        doc.table(['데이터', '보존', '만료 후'], [[r.get('data'), '영구' if r.get('keep_days') is None else f'{r["keep_days"]}일', r.get('after') or '해당 없음'] for r in d.get('retention') or []])
        doc.table(['역할', '데이터', '허용', '조건'], [[r.get('role'), r.get('data'), ', '.join(r.get('ops') or []), r.get('condition', '')] for r in d.get('access_policy') or []])
        doc.table(['기록 유형', '시각 기준', '수정 흔적', '삭제 흔적', '읽음 표시'], [[a.get('type'), a.get('timestamp_source', ''), a.get('edit_trace', ''), a.get('delete_trace', ''), a.get('read_receipt', '')] for a in d.get('artifacts') or []])
    doc.h(level, '용어집')
    doc.table(['표기', '정의', '사용 집단', '허용 별칭', '금지 별칭'], [
        [v.name(e['id']), e['data'].get('definition'), e['data'].get('register'), ', '.join(e['data'].get('aliases') or []), ', '.join(e['data'].get('forbidden_aliases') or [])]
        for e in sorted(v.of('Term'), key=lambda x: x['title'])])
    doc.h(level, '공개도별 설정')
    doc.tree([(0, label, ': ' + (', '.join(v.name(e['id']) for e in v.active if e.get('visibility') == value) or '(없음)'))
              for value, label in [('PUBLIC', '주민 상식'), ('INSIDER', '내부자 지식'), ('SECRET', '비밀')]])


def bible(s):
    v = View(s)
    doc = Doc()
    doc.h(1, f'{s["title"]} — 세계 바이블')
    doc.p(f'버전 {s["version_id"]} · 리비전 {s["revision"]} · 조사 현재 시점 {show(v.charter.get("present_at"))}')
    doc.p('고정점에서 계산한 요약이다. 요일과 경과 기간은 서술에 직접 적지 말고 이 출력을 인용한다. (제안)은 아직 확정되지 않은 설정이다.')
    world_sections(doc, v, 2)
    return markdown(doc)


def timeline_rows(v, character=None):
    rows = []
    for e in v.active:
        d, kind = e['data'], e['kind']
        if kind == 'Event' and (not character or character in (d.get('actors') or [])):
            rows.append([d.get('at'), '사건', v.name(e['id']), v.name(d.get('location_id')), v.names(d.get('actors'))])
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
    return v.dated(rows)


def timeline(s, character=None):
    v = View(s)
    if character and character not in v.index:
        raise ValueError('unknown character: ' + character)
    doc = Doc()
    doc.h(1, f'{s["title"]} — 시간선' + (f': {v.name(character)}' if character else ''))
    doc.p(f'조사 현재 시점 {show(v.charter.get("present_at"))}')
    doc.table(['시기', '현재 기준', '종류', '항목', '장소·청중·서비스', '관련 인물'], timeline_rows(v, character))
    return markdown(doc)


def span_text(a, b):
    return ' ~ '.join(x for x in [show(a) if a else '', show(b) if b else ''] if x) or '기간 미정'


def page_hub(doc, v, report):
    s, c = v.s, v.charter
    kinds = {}
    for e in v.active:
        kinds[e['kind']] = kinds.get(e['kind'], 0) + 1
    issues = [i for i in s.get('issues', []) if i.get('status') == 'OPEN']
    errors = [f for f in report['findings'] if f['level'] == 'ERROR']
    confirmed = sum(1 for e in v.active if e.get('status') == 'CONFIRMED')
    sess = s.get('session') or {}
    doc.h(3, '진행 현황')
    doc.table(['항목', '현재'], [
        ['버전 · 리비전', f'{s["version_id"]} · {s["revision"]}'],
        ['현실 거리', c.get('reality_distance') or '미정'], ['핵심 전제', c.get('premise') or '미정'],
        ['조사 현재 시점', show(c.get('present_at'))],
        ['설정 수', ', '.join(f'{k} {n}' for k, n in sorted(kinds.items())) or '없음'],
        ['확정된 설정', f'{confirmed} / {len(v.active)}'],
        ['자동 검사', f'오류 {len(errors)} · 경고 {len(report["findings"]) - len(errors)}'],
        ['열린 이슈', ' · '.join(f'{sev} {sum(1 for i in issues if i.get("severity") == sev)}' for sev in SEVERITY_ORDER)],
        ['미정 결정', str(len(s.get('pending_decisions') or []))],
        ['다음 질문', sess.get('next_question') or '없음']])


def page_workshop(doc, v, report):
    s = v.s
    doc.h(3, '미정 결정')
    doc.tree([(0, '', str(x.get('question') or x.get('title') or x) if isinstance(x, dict) else str(x)) for x in s.get('pending_decisions') or []])
    doc.h(3, '열린 검토 이슈')
    issues = sorted([i for i in s.get('issues', []) if i.get('status') == 'OPEN'], key=lambda i: SEVERITY_ORDER.get(i.get('severity'), 9))
    doc.table(['심각도', '이슈', '규칙', '대상', '제안'], [[i.get('severity'), i.get('title'), i.get('violated_rule', ''), v.names(i.get('affected_ids')), i.get('suggested_fix', '')] for i in issues])
    doc.h(3, '자동 검사 결과')
    doc.table(['규칙', '수준', '대상', '내용'], [[f['rule'], '오류' if f['level'] == 'ERROR' else '경고', v.names(f['ids']), f['message']] for f in report['findings']])
    sess = s.get('session') or {}
    if sess.get('next_question'):
        doc.h(3, '다음 질문')
        doc.p(sess['next_question'] + (f' — {sess["next_question_reason"]}' if sess.get('next_question_reason') else ''))


def page_characters(doc, v, report):
    doc.h(3, '인물')
    rows = []
    for e in v.of('Character'):
        d = e['data']
        affs = '; '.join(f'{v.name(a.get("org_id"))} {a.get("role", "")} ({span_text(a.get("from"), a.get("until"))})' for a in d.get('affiliations') or [] if isinstance(a, dict))
        rows.append([v.name(e['id']), d.get('identity'), affs, v.name(d.get('home_location_id')), cell(d.get('voice', ''))])
    doc.table(['인물', '정체성', '소속', '거주지', '말투'], rows)
    doc.h(3, '시점별 지식')
    doc.table(['시작', '인물', '사실', '상태', '획득 경로'], [
        [show(k['data'].get('from')), v.name(k['data'].get('character_id')), v.name(k['data'].get('fact_id')), k['data'].get('state'), v.names(k['data'].get('acquired_via')) or k['data'].get('initial_basis', '')]
        for k in sorted(v.of('Knowledge'), key=lambda k: sort_key(k['data'].get('from')))])
    doc.h(3, '발언')
    doc.table(['시각', '화자', '청중', '의도', '발언', '관련 사실'], [
        [show(c['data'].get('stated_at')), v.name(c['data'].get('speaker_id')), c['data'].get('audience'), c['data'].get('intent'), c['data'].get('statement'), v.names(c['data'].get('fact_ids'))]
        for c in sorted(v.of('Claim'), key=lambda c: sort_key(c['data'].get('stated_at')))])


def page_truth(doc, v, report):
    doc.h(3, '사건 시간선')
    doc.table(['시각', '현재 기준', '사건', '장소', '행위자', '결과'], v.dated([
        [e['data'].get('at'), v.name(e['id']), v.name(e['data'].get('location_id')), v.names(e['data'].get('actors')), e['data'].get('result')] for e in v.of('Event')]))
    doc.h(3, '사실')
    doc.table(['사실', '내용', '근거 사건'], [[v.name(f['id']), f['data'].get('statement'), v.name(f['data'].get('event_id'))] for f in v.of('Fact')])
    doc.h(3, '사건이 이용한 세계의 허점')
    doc.table(['사건', '규칙·서비스', '이유'], [[v.name(x.get('source')), v.name(x.get('target')), x.get('reason')] for x in v.s.get('links', []) if x.get('kind') == 'exploits'])


def page_investigation(doc, v, report):
    doc.h(3, '기록')
    doc.table(['생성 시각', '기록', '서비스·유형', '작성자', '현재 상태', '접근'], [
        [show(t['data'].get('created_at')), v.name(t['id']), ' · '.join(x for x in [v.name(t['data'].get('service_id')), t['data'].get('artifact_type', '')] if x),
         v.name(t['data'].get('author_id')), t['data'].get('state_at_present', 'PRESENT'), t['data'].get('access')]
        for t in sorted(v.of('Trace'), key=lambda t: sort_key(t['data'].get('created_at')))])
    doc.h(3, '근거')
    doc.table(['기록', '관계', '대상', '이유'], [[v.name(x.get('source')), '지지' if x.get('kind') == 'supports' else '반박', v.name(x.get('target')), x.get('reason')]
                                          for x in v.s.get('links', []) if x.get('kind') in {'supports', 'contradicts'}])
    used = {x.get('target') for x in v.s.get('links', []) if x.get('kind') == 'exploits'}
    for e in v.of('Event'):
        used.update(x for x in e['data'].get('preconditions') or [] if v.index.get(x, {}).get('kind') == 'WorldRule')
    exposing = {}
    for t in v.of('Trace'):
        for x in t['data'].get('origin_ids') or []:
            exposing.setdefault(x, []).append(t['id'])
    for x in v.s.get('links', []):
        for a, b in [(x.get('source'), x.get('target')), (x.get('target'), x.get('source'))]:
            if v.index.get(a, {}).get('kind') == 'Trace':
                exposing.setdefault(b, []).append(a)
    doc.h(3, '공정성: 해답에 쓰인 규칙의 노출')
    doc.table(['규칙', '공개도', '드러내는 기록'], [[v.name(r), v.index.get(r, {}).get('visibility', ''), v.names(sorted(set(exposing.get(r, [])))) or '없음']
                                             for r in sorted(x for x in used if x in v.index)])
    doc.h(3, '선택')
    doc.table(['선택', '선택 당시 정보', '옵션'], [[v.name(c['id']), c['data'].get('known_information'), ', '.join(str(o.get('label', '')) for o in c['data'].get('options') or [] if isinstance(o, dict))] for c in v.of('Choice')])
    doc.h(3, '결말')
    rows = []
    for e in v.of('Ending'):
        path = []
        for step in e['data'].get('witness') or []:
            choice = v.index.get(step.get('choice_id'), {})
            label = next((o.get('label') for o in choice.get('data', {}).get('options') or [] if o.get('id') == step.get('option_id')), step.get('option_id'))
            path.append(f'{v.name(step.get("choice_id"))}={label}')
        rows.append([v.name(e['id']), '단일' if e['data'].get('exclusive') else '동시 가능', ' → '.join(path), e['data'].get('consequences')])
    doc.table(['결말', '종류', '도달 경로 예', '결과'], rows)


def page_world(doc, v, report):
    world_sections(doc, v, 3)


BUILDERS = {'hub': page_hub, 'workshop': page_workshop, 'world': page_world, 'characters': page_characters, 'truth': page_truth, 'investigation': page_investigation}


def page_summary(s, page, report):
    """Notion-flavored body of a page's generated "Canon 요약" region (without the region heading)."""
    if page not in BUILDERS:
        raise ValueError('no generated summary for page: ' + page)
    v = View(s)
    doc = Doc()
    doc.p(f'Canon 리비전 {s["revision"]} 기준 자동 요약. 이 영역은 동기화 때 다시 쓰인다.')
    BUILDERS[page](doc, v, report)
    return notion(doc)
