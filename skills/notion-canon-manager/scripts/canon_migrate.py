"""Migrate a schema_version 1 snapshot to schema_version 2 without dropping content.

Reads the fixed v1 storage formats defined by mystery-world-builder
(titles "헌장:", "장소:", "용어:", the [DEPTH·VISIBILITY·ORIGIN] tag line,
"보존:", "권한:" and "[연표]" lines). Anything it cannot place exactly is
kept and reported as an OPEN MINOR QA issue with violated_rule MIGRATION.
"""
import copy
import re
from datetime import datetime, timedelta

import canon
import canon_rules as rules

KIND_TITLE = re.compile(r'^\s*(헌장|장소|용어)\s*[:：]\s*(.+?)\s*$')
TAG = re.compile(r'^\[\s*(CORE|SUPPORTING|MENTION)\s*[·,/ ]\s*(PUBLIC|INSIDER|SECRET)\s*[·,/ ]\s*(FOUNDATION|PLOT_NEED)\s*\]$')
REASON = re.compile(r'^세계 내 근거\s*[:：]\s*(.+)$')
ISO = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})')
LINE = {'retention': re.compile(r'^\s*보존\s*[:：]\s*(.+)$'), 'access': re.compile(r'^\s*권한\s*[:：]\s*(.+)$'), 'history': re.compile(r'^\s*\[연표\]\s*(.+)$')}
REALITY_WORDS = [('REAL_PLUS', r'REAL_PLUS|현실\s*\+\s*가상|현실과 가상'), ('ALTERNATE', r'ALTERNATE|대체\s*현실'), ('INVENTED', r'INVENTED|완전\s*가상'), ('REAL', r'\bREAL\b|현실 그대로')]
OPS = {'읽기': 'read', '열람': 'read', '조회': 'read', '수정': 'edit', '편집': 'edit', '삭제': 'delete', '복원': 'restore', '복구': 'restore', '내보내기': 'export', '다운로드': 'export'}
SEASONS = {'봄': (3, 3), '여름': (6, 3), '가을': (9, 3), '겨울': (12, 3)}
NONE_WORDS = {'', '없음', '해당 없음', '-'}
FILLER = '미정 (이관 시 비어 있음)'


class Migration:
    def __init__(self, snapshot):
        if snapshot.get('schema_version') != 1:
            raise ValueError('migrate expects schema_version 1')
        self.s = copy.deepcopy(snapshot)
        self.s['schema_version'] = 2
        self.s['charter'] = canon.empty_snapshot('x', 'x', 'x')['charter']
        self.index = {e['id']: e for e in self.s['entities']}
        self.taken = {x.get('id') for key in ['entities', 'links', 'decisions', 'issues'] for x in self.s[key]}
        self.changed = set()
        self.notes = []

    def note(self, affected, title, evidence, fix):
        self.notes.append((sorted({x for x in affected if x in self.index}), title, evidence, fix))

    def new_id(self, base):
        base = re.sub(r'[^A-Za-z0-9_-]', '-', base).strip('-') or 'MIG'
        candidate, n = base, 1
        while candidate in self.taken:
            n += 1
            candidate = f'{base}-{n}'
        self.taken.add(candidate)
        return candidate

    def offset(self):
        present = rules.safe_span(self.s['charter'].get('present_at'))
        if present and present[0]:
            text = present[0].isoformat()
            return text[-6:] if text[-6] in '+-' else '+00:00'
        return '+00:00'

    def run(self):
        world = [e for e in self.s['entities'] if e.get('kind') in {'WorldRule', 'Organization', 'Service'}]
        for e in world:
            self.tags(e)
        for e in world:
            m = KIND_TITLE.match(e.get('title', '')) if e.get('kind') == 'WorldRule' else None
            if m and m.group(1) == '헌장':
                self.charter(e)
        converted = {}
        for e in world:
            m = KIND_TITLE.match(e.get('title', '')) if e.get('kind') == 'WorldRule' else None
            if m and m.group(1) in {'장소', '용어'}:
                converted[e['id']] = (m.group(1), m.group(2))
        for eid, (label, name) in converted.items():
            (self.location if label == '장소' else self.term)(self.index[eid], name)
        for eid, (label, _) in converted.items():
            if label == '장소':
                self.place(self.index[eid])
        self.repair_refs(set(converted))
        for e in world:
            if e['kind'] == 'Service':
                self.service(e)
        for e in world:
            self.history(e)
        self.knows()
        for e in self.s['entities']:
            if e['id'] in self.changed:
                e['revision'] = e.get('revision', 0) + 1
        self.s['revision'] = self.s.get('revision', 0) + 1
        for n, (affected, title, evidence, fix) in enumerate(self.notes, 1):
            self.s['issues'].append({'id': self.new_id(f'MIG-{n}'), 'title': title, 'severity': 'MINOR', 'affected_ids': affected, 'evidence': evidence, 'violated_rule': 'MIGRATION', 'suggested_fix': fix, 'status': 'OPEN'})
        return self.s

    def tags(self, e):
        field = canon.TEXT[e['kind']][0]
        lines = str(e['data'].get(field, '')).split('\n')
        m = TAG.match(lines[0].strip())
        if m:
            e['depth'], e['visibility'], e['origin'] = m.groups()
            rest = lines[1:]
            if e['origin'] == 'PLOT_NEED' and rest and REASON.match(rest[0].strip()):
                e['in_world_reason'] = REASON.match(rest[0].strip()).group(1).strip()
                rest = rest[1:]
            e['data'][field] = '\n'.join(rest).strip() or FILLER
        else:
            e['depth'], e['visibility'], e['origin'] = 'SUPPORTING', 'PUBLIC', 'FOUNDATION'
            if e.get('status') not in rules.INACTIVE:
                e['review'] = 'NEEDS_REVIEW'
            self.note([e['id']], '밀도·공개도·출처 기본값 적용', f'{e["id"]}의 {field} 첫 줄에 [밀도·공개도·출처] 태그가 없어 SUPPORTING·PUBLIC·FOUNDATION을 넣었다.', '실제 값으로 고치고 검토 상태를 갱신한다.')
        self.changed.add(e['id'])

    def charter(self, e):
        c, d = self.s['charter'], e['data']
        if c['premise']:
            self.note([e['id']], '헌장 규칙이 여러 개', f'{e["id"]}는 첫 헌장 이후의 헌장 규칙이라 charter에 반영하지 않았다.', '하나의 헌장으로 합치고 나머지는 SUPERSEDED로 바꾼다.')
            return
        c['premise'] = d.get('statement', '')
        c['scope_out'] = d.get('scope', '')
        for value, pattern in REALITY_WORDS:
            if re.search(pattern, d.get('grounding', '')):
                c['reality_distance'] = value
                break
        found = ISO.search(d.get('scope', '') + '\n' + d.get('statement', ''))
        if found and rules.safe_span(found.group(0)):
            c['present_at'] = found.group(0)
        self.note([e['id']], '헌장 이관 확인', f'{e["id"]}에서 premise·scope_out·reality_distance={c["reality_distance"]}·present_at={c["present_at"]}를 채웠다. genre_tone·scope_in·timezone은 비어 있다.', 'charter를 확인·보완한 뒤 원래 헌장 규칙을 SUPERSEDED로 바꾼다.')

    def location(self, e, name):
        d = e['data']
        e['kind'], e['title'] = 'Location', name
        e['data'] = {'description': d.get('statement') or FILLER, 'access': d.get('exceptions') or FILLER, 'rhythm': d.get('grounding') or FILLER, '_scope': d.get('scope', '')}
        self.changed.add(e['id'])

    def place(self, e):
        titles = {canon_norm(x['title']): x['id'] for x in self.s['entities'] if x.get('kind') == 'Location'}
        scope, unplaced, connections = e['data'].pop('_scope'), [], []
        for part in [x.strip() for x in scope.split('/') if x.strip()]:
            key, _, rest = part.partition(':')
            key, rest = key.strip(), rest.strip()
            if key == '상위' and titles.get(canon_norm(rest)):
                e['data']['parent_id'] = titles[canon_norm(rest)]
            elif key == '연결':
                for item in [x.strip() for x in re.split(r'[,，]', rest) if x.strip()]:
                    m = re.match(r'^(.+?)\s+(?:(\S+)\s+)?(\d+(?:\.\d+)?)\s*분$', item)
                    target = titles.get(canon_norm(m.group(1))) if m else None
                    if target:
                        conn = {'to': target, 'minutes': float(m.group(3)) if '.' in m.group(3) else int(m.group(3))}
                        if m.group(2):
                            conn['mode'] = m.group(2)
                        connections.append(conn)
                    else:
                        unplaced.append(item)
            else:
                unplaced.append(part)
        e['data']['connections'] = connections
        if unplaced:
            self.note([e['id']], '장소 연결 일부 미해석', f'{e["id"]}의 범위 표기 중 해석하지 못한 부분: ' + ' / '.join(unplaced), '장소 이름을 확인해 parent_id 또는 connections에 직접 넣는다.')

    def term(self, e, name):
        d = e['data']
        e['kind'], e['title'] = 'Term', name
        e['data'] = {'definition': d.get('statement') or FILLER, 'register': d.get('scope') or FILLER,
                     'aliases': self.names(e, d.get('exceptions', ''), '허용 별칭'), 'forbidden_aliases': self.names(e, d.get('grounding', ''), '금지 별칭')}
        self.changed.add(e['id'])

    def names(self, e, value, prefix):
        key, sep, rest = value.partition(':')
        if not sep or key.strip() != prefix:
            if value.strip() not in NONE_WORDS:
                self.note([e['id']], '용어 별칭 미해석', f'{e["id"]}의 "{value}"가 "{prefix}: …" 형식이 아니다.', f'{prefix}을 목록으로 직접 넣는다.')
            return []
        return [x.strip() for x in re.split(r'[,，、·/]', rest) if x.strip() not in NONE_WORDS]

    def repair_refs(self, converted):
        for e in self.s['entities']:
            d, kind = e.get('data', {}), e.get('kind')
            for key, allowed in canon.REFS.get(kind, {}).items():
                value = d.get(key)
                vals = value if isinstance(value, list) else [value]
                bad = [x for x in vals if x in converted and self.index[x]['kind'] not in allowed]
                if not bad:
                    continue
                for x in bad:
                    if kind == 'Event' and key == 'preconditions' and self.index[x]['kind'] == 'Location' and not d.get('location_id'):
                        d['location_id'] = x
                    else:
                        self.note([e['id'], x], '이관된 장소·용어 참조 제거', f'{e["id"]}.{key}가 {x}를 가리켰지만 {self.index[x]["kind"]}는 이 필드에 올 수 없다.', '필요하면 location_id·depends_on·related 링크로 다시 연결한다.')
                if isinstance(value, list):
                    d[key] = [x for x in value if x not in bad]
                else:
                    del d[key]
                self.changed.add(e['id'])

    def service(self, e):
        d, retention, access = e['data'], [], []
        for line in d.get('data_lifecycle', '').split('\n'):
            m = LINE['retention'].match(line)
            if m:
                item = self.retention_item(e, m.group(1))
                if item:
                    retention.append(item)
        for line in d.get('permissions', '').split('\n'):
            m = LINE['access'].match(line)
            if m:
                item = self.access_item(e, m.group(1))
                if item:
                    access.append(item)
        if retention:
            d['retention'] = retention
        if access:
            d['access_policy'] = access

    def retention_item(self, e, raw):
        parts = [x.strip() for x in raw.split('|')]
        if len(parts) < 3:
            self.note([e['id']], '보존 줄 미해석', f'{e["id"]}: "보존: {raw}"', '"보존: 데이터 | 기간 | 만료 후 처리 | 예외" 형식으로 고친다.')
            return None
        data, period, after = parts[:3]
        m = re.search(r'(\d+)\s*(일|개월|달|년)', period)
        if '영구' in period:
            days = None
        elif m:
            days = int(m.group(1)) * {'일': 1, '개월': 30, '달': 30, '년': 365}[m.group(2)]
            if m.group(2) != '일':
                self.note([e['id']], '보존 기간 근사', f'{e["id"]}: "{period}"를 {days}일로 환산했다.', '정확한 일수가 중요하면 keep_days를 고친다.')
        else:
            self.note([e['id']], '보존 기간 미해석', f'{e["id"]}: "{period}"', 'keep_days를 정수 일수 또는 null(영구)로 넣는다.')
            return None
        if re.search(r'영구\s*삭제|완전\s*삭제', after):
            mode = 'HARD_DELETE'
        elif re.search(r'휴지통|복구 가능|임시 삭제|소프트', after):
            mode = 'SOFT_DELETE'
        elif re.search(r'보관|아카이브|이관', after):
            mode = 'ARCHIVE'
        elif after in NONE_WORDS:
            mode = None
        else:
            self.note([e['id']], '만료 후 처리 미해석', f'{e["id"]}: "{after}"', 'after를 HARD_DELETE / SOFT_DELETE / ARCHIVE 중 하나로 넣는다.')
            return None
        item = {'data': data, 'keep_days': days, 'after': mode}
        if len(parts) > 3 and parts[3] not in NONE_WORDS:
            item['exceptions'] = parts[3]
        return item

    def access_item(self, e, raw):
        parts = [x.strip() for x in raw.split('|')]
        if len(parts) < 3:
            self.note([e['id']], '권한 줄 미해석', f'{e["id"]}: "권한: {raw}"', '"권한: 역할 | 데이터 | 허용 동작 | 조건" 형식으로 고친다.')
            return None
        words = [x for x in re.split(r'[·,/\s]+', parts[2]) if x]
        ops = sorted({OPS[w] for w in words if w in OPS})
        unknown = [w for w in words if w not in OPS]
        if unknown or not ops:
            self.note([e['id']], '권한 동작 미해석', f'{e["id"]}: "{parts[2]}"에서 해석하지 못한 말: {", ".join(unknown) or "없음"}', 'ops를 read / edit / delete / restore / export로 넣는다.')
        if not ops:
            return None
        item = {'role': parts[0], 'data': parts[1], 'ops': ops}
        if len(parts) > 3 and parts[3] not in NONE_WORDS:
            item['condition'] = parts[3]
        return item

    def history(self, e):
        for key, value in list(e['data'].items()):
            if not isinstance(value, str):
                continue
            for line in value.split('\n'):
                m = LINE['history'].match(line)
                if not m:
                    continue
                parts = [x.strip() for x in m.group(1).split('|')]
                when, what, legacy = (parts + ['', '', ''])[:3]
                at = self.period(when)
                hid = self.new_id(f'HIST-{e["id"]}')
                h = {'id': hid, 'project_id': e['project_id'], 'version_id': e['version_id'], 'title': (what or when)[:60] or hid, 'kind': 'HistoryEvent', 'revision': 0,
                     'owner': canon.OWNERS['HistoryEvent'], 'status': e['status'], 'review': 'NEEDS_REVIEW', 'depends_on': [], 'decision_refs': list(e.get('decision_refs', [])),
                     'depth': e['depth'], 'visibility': e['visibility'], 'origin': e['origin'],
                     'data': {'at': at, 'summary': (what if at else f'시기: {when}. {what}') or FILLER, 'consequences': legacy or FILLER, 'public_account': '미정 (이관: 통념 서술 없음)', 'preconditions': [], 'legacy_ids': [e['id']]}}
                if 'in_world_reason' in e:
                    h['in_world_reason'] = e['in_world_reason']
                self.s['entities'].append(h)
                self.index[hid] = h
                self.note([hid, e['id']], '연표 항목을 HistoryEvent로 생성', f'{e["id"]}.{key}의 "[연표] {m.group(1)}"에서 {hid}를 만들었다. 시기 해석: {at}', '통념(public_account)과 선후 관계(preconditions)를 채우고 검토한다.')

    def period(self, text):
        text = text.strip()
        if ISO.fullmatch(text) and rules.safe_span(text):
            return text
        off = self.offset()
        m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', text) or re.search(r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일', text)
        if m:
            start = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return window(start, start + timedelta(days=1), off, text)
        m = re.search(r'(\d{4})\s*년\s*(\d{1,2})\s*월', text)
        if m:
            return window(datetime(int(m.group(1)), int(m.group(2)), 1), add_months(int(m.group(1)), int(m.group(2)), 1), off, text)
        m = re.search(r'(\d{4})\s*년\s*(봄|여름|가을|겨울)', text)
        if m:
            month, length = SEASONS[m.group(2)]
            return window(datetime(int(m.group(1)), month, 1), add_months(int(m.group(1)), month, length), off, text)
        m = re.search(r'(\d{4})\s*년', text)
        if m:
            return window(datetime(int(m.group(1)), 1, 1), datetime(int(m.group(1)) + 1, 1, 1), off, text)
        return None

    def knows(self):
        keep = []
        for link in self.s['links']:
            if link.get('kind') != 'knows':
                keep.append(link)
                continue
            char, fact = link.get('source'), link.get('target')
            exists = any(e.get('kind') == 'Knowledge' and e['data'].get('character_id') == char and e['data'].get('fact_id') == fact for e in self.s['entities'])
            if not exists:
                kid = self.new_id(f'KN-{link.get("id")}')
                k = {'id': kid, 'project_id': self.s['project_id'], 'version_id': self.s['version_id'], 'title': f'{char} → {fact}', 'kind': 'Knowledge', 'revision': 0,
                     'owner': canon.OWNERS['Knowledge'], 'status': 'PROPOSED', 'review': 'NEEDS_REVIEW', 'depends_on': [], 'decision_refs': [],
                     'data': {'character_id': char, 'fact_id': fact, 'state': 'KNOWS', 'from': None, 'until': None, 'acquired_via': [], 'initial_basis': link.get('reason') or FILLER}}
                self.s['entities'].append(k)
                self.index[kid] = k
            self.note([char, fact], 'knows 링크를 Knowledge로 이관', f'링크 {link.get("id")}를 제거했다. ' + ('같은 인물·사실의 Knowledge가 이미 있다.' if exists else 'PROPOSED Knowledge 초안을 만들었다.'), 'state·from·acquired_via를 확인한다.')
        self.s['links'] = keep


def canon_norm(text):
    return rules.norm(text)


def add_months(year, month, n):
    month += n
    return datetime(year + (month - 1) // 12, (month - 1) % 12 + 1, 1)


def window(start, stop, off, label):
    fmt = '%Y-%m-%dT%H:%M:%S'
    return {'earliest': start.strftime(fmt) + off, 'latest': (stop - timedelta(seconds=1)).strftime(fmt) + off, 'label': label}


def migrate(snapshot):
    return Migration(snapshot).run()
