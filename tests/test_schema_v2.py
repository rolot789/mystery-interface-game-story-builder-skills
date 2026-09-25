import copy
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(os.environ.get('MYSTERY_SKILLS_ROOT', str(Path(__file__).resolve().parents[1] / 'skills')))
MANAGER = next(p.parent for p in ROOT.glob('*/SKILL.md') if '\nname: notion-canon-manager\n' in p.read_text())
sys.path.insert(0, str(MANAGER / 'scripts'))
import canon
import canon_migrate
import canon_rules
import canon_views
import notion_plan

FIXTURES = Path(__file__).resolve().parent / 'fixtures'


def world():
    return json.loads((FIXTURES / 'world_v2.json').read_text())


def legacy():
    return json.loads((FIXTURES / 'legacy_v1.json').read_text())


def entity(s, id_):
    return next(e for e in s['entities'] if e['id'] == id_)


def rules_hit(s, complete=False):
    return {f['rule'] for f in canon.validate(s, complete)['findings']}


class TimeSpec(unittest.TestCase):
    def test_forms(self):
        self.assertIsNone(canon_rules.span(None))
        exact = canon_rules.span('2026-03-01T22:00:00+09:00')
        self.assertEqual(exact[0], exact[1])
        lo, hi = canon_rules.span({'earliest': '2019-09-01T00:00:00+09:00', 'latest': '2019-11-30T00:00:00+09:00', 'label': '2019년 가을'})
        self.assertLess(lo, hi)
        self.assertIsNone(canon_rules.span({'latest': '2019-01-01T00:00:00+09:00'})[0])
        for bad in ['2019', '2026-03-01T22:00:00', {'label': 'x'}, {'earliest': '2020-01-01T00:00:00Z', 'latest': '2019-01-01T00:00:00Z'}, 5]:
            with self.assertRaises(ValueError):
                canon_rules.span(bad)

    def test_overlap_is_not_certain(self):
        autumn = canon_rules.span({'earliest': '2019-09-01T00:00:00+09:00', 'latest': '2019-11-30T00:00:00+09:00'})
        october = canon_rules.span('2019-10-15T00:00:00+09:00')
        self.assertFalse(canon_rules.surely_after(autumn, october))
        self.assertFalse(canon_rules.surely_after(october, autumn))
        self.assertTrue(canon_rules.surely_after(canon_rules.span('2020-01-01T00:00:00+09:00'), autumn))


class WorldFixture(unittest.TestCase):
    def test_complete_world_has_no_findings(self):
        r = canon.validate(world(), True)
        self.assertEqual(r['errors'], [])
        self.assertEqual(r['findings'], [])

    def test_v2_kinds_need_v2(self):
        s = legacy()
        s['entities'].append({**copy.deepcopy(entity(world(), 'LOC-PIER')), 'project_id': 'P-OLD', 'parent_id': None})
        s['entities'][-1]['data'].pop('parent_id')
        self.assertTrue(any('requires schema_version 2' in e for e in canon.validate(s)['errors']))

    def test_world_metadata_required(self):
        s = world()
        del entity(s, 'ORG-ARCHIVE')['visibility']
        self.assertTrue(any('visibility required' in e for e in canon.validate(s)['errors']))

    def test_structured_items_checked(self):
        s = world()
        entity(s, 'SVC-MSG')['data']['access_policy'][0]['ops'] = ['read', 'teleport']
        self.assertTrue(any('access_policy' in e for e in canon.validate(s)['errors']))


class Robustness(unittest.TestCase):
    def test_malformed_values_are_reported_not_raised(self):
        junk = [[{}], {}, 5, None, [None], {'earliest': [1]}]
        base = world()
        for i, e in enumerate(base['entities']):
            for key in list(e['data']) + ['depth', 'status', 'kind']:
                for value in junk:
                    s = copy.deepcopy(base)
                    target = s['entities'][i]
                    (target['data'] if key in target['data'] else target)[key] = value
                    canon.validate(s, True)
        for value in junk:
            s = copy.deepcopy(base)
            s['links'][0]['target'] = value
            s['charter']['reality_distance'] = value
            self.assertTrue(canon.validate(s)['errors'])


class Rules(unittest.TestCase):
    def test_time_001_event_after_present(self):
        s = world()
        entity(s, 'EV2')['data']['at'] = '2026-04-01T00:00:00+09:00'
        self.assertIn('TIME-001', rules_hit(s))

    def test_time_002_uncertain_history_precondition(self):
        s = world()
        entity(s, 'HIST-MERGER')['data']['at'] = {'earliest': '2027-01-01T00:00:00+09:00', 'latest': '2027-12-31T00:00:00+09:00'}
        self.assertIn('TIME-002', rules_hit(s))

    def test_time_005_existence(self):
        s = world()
        entity(s, 'SVC-MSG')['data']['launched_at'] = '2026-03-02T00:00:00+09:00'
        self.assertIn('TIME-005', rules_hit(s))
        s = world()
        entity(s, 'ORG-ARCHIVE')['data']['founded_at'] = '2026-06-01T00:00:00+09:00'
        self.assertIn('TIME-005', rules_hit(s))

    def test_time_006_rule_not_in_force(self):
        s = world()
        entity(s, 'R-RETENTION')['data']['valid_until'] = '2025-12-31T00:00:00+09:00'
        self.assertIn('TIME-006', rules_hit(s))

    def test_time_007_affiliation(self):
        s = world()
        entity(s, 'C1')['data']['affiliations'][0]['until'] = '2025-01-01T00:00:00+09:00'
        self.assertIn('TIME-007', rules_hit(s))

    def test_graph_and_space_hierarchy_cycles(self):
        s = world()
        entity(s, 'LOC-HARBOR')['data']['parent_id'] = 'LOC-PIER'
        self.assertIn('SPACE-001', rules_hit(s))
        s = world()
        s['entities'].append({**copy.deepcopy(entity(s, 'ORG-ARCHIVE')), 'id': 'ORG-SUB', 'title': '기록공사 분소'})
        entity(s, 'ORG-SUB')['data']['parent_id'] = 'ORG-ARCHIVE'
        entity(s, 'ORG-ARCHIVE')['data']['parent_id'] = 'ORG-SUB'
        self.assertIn('GRAPH-001', rules_hit(s))

    def test_space_002_and_003(self):
        s = world()
        entity(s, 'EV2')['data']['at'] = '2026-03-01T22:10:00+09:00'
        self.assertIn('SPACE-002', rules_hit(s))
        s = world()
        entity(s, 'EV2')['data']['at'] = '2026-03-01T22:35:00+09:00'
        hits = rules_hit(s)
        self.assertIn('SPACE-003', hits)
        self.assertNotIn('SPACE-002', hits)

    def test_space_nested_places_do_not_conflict(self):
        s = world()
        entity(s, 'EV2')['data'].update({'at': '2026-03-01T22:10:00+09:00', 'location_id': 'LOC-HARBOR'})
        self.assertFalse({'SPACE-002', 'SPACE-003'} & rules_hit(s))

    def test_data_001_retention(self):
        s = world()
        s['charter']['present_at'] = '2026-04-14T21:00:00+09:00'
        entity(s, 'EV2')['data']['at'] = '2026-03-01T23:00:00+09:00'
        self.assertIn('DATA-001', rules_hit(s))
        entity(s, 'T1')['data']['retention_exception'] = '법적 보존 요청으로 1년 보존'
        self.assertNotIn('DATA-001', rules_hit(s))
        del entity(s, 'T1')['data']['retention_exception']
        entity(s, 'T1')['data']['state_at_present'] = 'DELETED'
        self.assertNotIn('DATA-001', rules_hit(s))

    def test_data_002_undeclared_artifact(self):
        s = world()
        entity(s, 'T1')['data']['artifact_type'] = 'voice_note'
        self.assertIn('DATA-002', rules_hit(s))

    def test_terms(self):
        s = world()
        entity(s, 'F1')['data']['basis'] = '기록청 내부 감사'
        self.assertIn('TERM-001', rules_hit(s))
        s = world()
        s['entities'].append({**copy.deepcopy(entity(s, 'TERM-ARCHIVE')), 'id': 'TERM-2', 'title': '공사'})
        self.assertIn('TERM-002', rules_hit(s))

    def test_world_001_scope_and_completion(self):
        s = world()
        s['charter']['scope_in'].append('NOPE')
        self.assertIn('WORLD-001', rules_hit(s))
        s = world()
        s['charter']['present_at'] = None
        self.assertIn('WORLD-001', rules_hit(s, True))
        self.assertNotIn('WORLD-001', rules_hit(s))

    def test_world_002_core_detail(self):
        s = world()
        del entity(s, 'SVC-MSG')['data']['retention']
        self.assertIn('WORLD-002', rules_hit(s, True))
        entity(s, 'SVC-MSG')['depth'] = 'SUPPORTING'
        self.assertNotIn('WORLD-002', rules_hit(s, True))

    def test_world_003_plot_need(self):
        s = world()
        entity(s, 'LOC-PIER')['origin'] = 'PLOT_NEED'
        self.assertIn('WORLD-003', rules_hit(s))
        entity(s, 'LOC-PIER')['in_world_reason'] = '항만 축소로 폐쇄된 부두'
        self.assertNotIn('WORLD-003', rules_hit(s))

    def test_world_004_and_fair_001(self):
        s = world()
        entity(s, 'R-RETENTION')['data']['strength'] = 'HARD'
        self.assertIn('WORLD-004', rules_hit(s))
        s = world()
        s['entities'] = [e for e in s['entities'] if e['id'] != 'T2']
        self.assertIn('FAIR-001', rules_hit(s))
        entity(s, 'R-RETENTION')['visibility'] = 'PUBLIC'
        self.assertNotIn('FAIR-001', rules_hit(s))

    def test_claim_001(self):
        s = world()
        entity(s, 'K1')['data']['until'] = '2026-03-02T00:00:00+09:00'
        self.assertIn('CLAIM-001', rules_hit(s))
        s = world()
        entity(s, 'CL1')['data']['fact_ids'] = []
        self.assertIn('CLAIM-001', rules_hit(s))

    def test_findings_use_entity_ids(self):
        s = world()
        entity(s, 'EV2')['data']['at'] = '2026-03-01T22:10:00+09:00'
        f = next(x for x in canon.validate(s)['findings'] if x['rule'] == 'SPACE-002')
        self.assertTrue(all(x in {e['id'] for e in s['entities']} for x in f['ids']))


class Impact(unittest.TestCase):
    def test_new_edges(self):
        s = world()
        self.assertIn('EV1', canon.impact(s, ['R-RETENTION'])['needs_review'])
        self.assertIn('C1', canon.impact(s, ['ORG-ARCHIVE'])['needs_review'])
        self.assertIn('LOC-OFFICE', canon.impact(s, ['LOC-PIER'])['needs_review'])


class Migration(unittest.TestCase):
    def setUp(self):
        self.out = canon_migrate.migrate(legacy())

    def test_result_validates(self):
        r = canon.validate(self.out)
        self.assertEqual(r['errors'], [])
        self.assertEqual(self.out['schema_version'], 2)
        self.assertEqual(self.out['revision'], 4)

    def test_charter(self):
        c = self.out['charter']
        self.assertEqual(c['reality_distance'], 'REAL_PLUS')
        self.assertEqual(c['present_at'], '2026-03-14T21:00:00+09:00')
        self.assertTrue(c['premise'].startswith('모든 공공기록'))

    def test_locations_terms_and_tags(self):
        harbor, office, term = entity(self.out, 'WR-HARBOR'), entity(self.out, 'WR-OFFICE'), entity(self.out, 'WR-TERM')
        self.assertEqual((harbor['kind'], harbor['title']), ('Location', '항만 구역'))
        self.assertEqual(harbor['data']['connections'], [{'to': 'WR-OFFICE', 'minutes': 15, 'mode': '도보'}])
        self.assertEqual(office['data']['parent_id'], 'WR-HARBOR')
        self.assertEqual(office['depth'], 'SUPPORTING')
        self.assertEqual(term['data']['forbidden_aliases'], ['기록청', '기록원'])
        org = entity(self.out, 'ORG1')
        self.assertEqual((org['origin'], org['in_world_reason'], org['data']['purpose']), ('PLOT_NEED', '시 재정난으로 위탁', '공공기록 위탁 운영'))
        self.assertEqual(entity(self.out, 'WR-RULE')['review'], 'NEEDS_REVIEW')

    def test_references_repaired(self):
        ev = entity(self.out, 'EV1')['data']
        self.assertEqual((ev['preconditions'], ev['location_id']), (['WR-RULE'], 'WR-OFFICE'))
        self.assertEqual(entity(self.out, 'T1')['data']['origin_ids'], ['EV1'])

    def test_service_lines(self):
        d = entity(self.out, 'SVC1')['data']
        self.assertEqual(d['retention'][0], {'data': 'message', 'keep_days': 30, 'after': 'HARD_DELETE', 'exceptions': '법적 보존 요청 시 1년'})
        self.assertEqual(d['retention'][1]['after'], 'SOFT_DELETE')
        self.assertEqual(d['access_policy'][1]['ops'], ['read'])
        self.assertIn('보존: message', d['data_lifecycle'])

    def test_history_and_knows(self):
        hist = [e for e in self.out['entities'] if e['kind'] == 'HistoryEvent']
        self.assertEqual({e['data']['at']['label'] for e in hist}, {'2019년 가을', '2015년'})
        self.assertFalse(any(l['kind'] == 'knows' for l in self.out['links']))
        self.assertTrue(any(e['kind'] == 'Knowledge' and e['data']['fact_id'] == 'F2' and e['status'] == 'PROPOSED' for e in self.out['entities']))

    def test_unplaced_parts_become_issues(self):
        issues = [i for i in self.out['issues'] if i['violated_rule'] == 'MIGRATION']
        self.assertEqual(issues[0]['id'], 'MIG-1')
        text = ' '.join(i['evidence'] for i in issues)
        for expected in ['없는곳 5분', '공유', '90일', 'T1.origin_ids']:
            self.assertIn(expected, text)

    def test_refuses_v2(self):
        with self.assertRaises(ValueError):
            canon_migrate.migrate(world())


class Views(unittest.TestCase):
    def test_bible(self):
        text = canon_views.bible(world())
        for expected in ['## 연표', '2026-03-14 (토)', '2020-01-01 (수)', '2019년 가을', '- **항만 구역**', '  - **기록공사 본관**', '| message | 30일 | HARD_DELETE |', '| 기록공사 | 공공기록']:
            self.assertIn(expected, text)

    def test_timeline(self):
        text = canon_views.timeline(world(), 'C1')
        self.assertIn('12일 전', text)
        self.assertLess(text.index('야간 기록 삭제'), text.index('윤의 부인'))
        with self.assertRaises(ValueError):
            canon_views.timeline(world(), 'NOPE')


class NotionPlan(unittest.TestCase):
    def reg(self):
        return {'project_id': 'P-HARBOR', 'version_id': 'V1', 'title': '항만 기록', 'workspace_root_requested': True, 'version_page_id': '00000000-0000-0000-0000-000000000002',
                'data_sources': {k: f'00000000-0000-0000-0000-{i:012d}' for i, k in enumerate(notion_plan.BLUE['databases'], 50)}, 'pages': {}, 'bases': {}}

    def test_v2_entities_and_charter(self):
        s = world()
        ops = notion_plan.upsert(s, self.reg(), {'complete': True, 'records': []}, 'entities')
        props = {op['arguments']['pages'][0]['properties']['Entity ID']: op['arguments']['pages'][0]['properties'] for op in ops}
        self.assertEqual(props['HIST-MERGER']['date:Event Time:end'], '2019-11-30T23:59:59+09:00')
        self.assertEqual(props['LOC-PIER']['Summary'], '폐쇄된 부두')
        self.assertEqual(props['EV1']['date:Event Time:start'], '2026-03-01T22:00:00+09:00')
        version = notion_plan.upsert(s, self.reg(), {'complete': True, 'records': []}, 'versions')[0]
        self.assertIn('"charter"', version['arguments']['pages'][0]['content'])

    def test_world_metadata_and_timeline_properties(self):
        ops = notion_plan.upsert(world(), self.reg(), {'complete': True, 'records': []}, 'entities')
        props = {op['arguments']['pages'][0]['properties']['Entity ID']: op['arguments']['pages'][0]['properties'] for op in ops}
        self.assertEqual((props['R-RETENTION']['Depth'], props['R-RETENTION']['Visibility'], props['R-RETENTION']['Origin']), ('CORE', 'INSIDER', 'FOUNDATION'))
        self.assertEqual(props['R-RETENTION']['date:Event Time:start'], '2020-01-01T00:00:00+09:00')
        self.assertEqual(props['ORG-ARCHIVE']['date:Event Time:start'], '2015-01-01T00:00:00+09:00')
        self.assertEqual(props['SVC-MSG']['date:Event Time:start'], '2018-05-01T09:00:00+09:00')
        self.assertNotIn('Depth', props['C1'])

    def test_legacy_records_keep_their_properties(self):
        import test_contracts
        s = test_contracts.sample()
        reg = test_contracts.reg()
        props = {op['arguments']['pages'][0]['properties']['Entity ID']: op['arguments']['pages'][0]['properties'] for op in notion_plan.upsert(s, reg, {'complete': True, 'records': []}, 'entities')}
        for e in s['entities']:
            extra = {k for k in props[e['id']] if k.startswith('date:')} - ({'date:Event Time:start', 'date:Event Time:is_datetime'} if e['kind'] == 'Event' else set())
            self.assertEqual(extra, set())
            self.assertFalse({'Depth', 'Visibility', 'Origin'} & set(props[e['id']]))


class TemplateUpgrade(unittest.TestCase):
    def old_schema(self):
        schema = {name: dict(spec['properties']) for name, spec in notion_plan.BLUE['databases'].items()}
        for prop in ['Depth', 'Visibility', 'Origin']:
            del schema['entities'][prop]
        schema['entities']['Kind'] = "SELECT('WorldRule':default, 'Organization', 'Service', 'Character', 'Event', 'Fact', 'Claim', 'Knowledge', 'Trace', 'Choice', 'Ending', 'Custom kind':pink)"
        schema['links']['Relation'] = "SELECT('supports','contradicts','generates','knows','depends_on','related')"
        schema['entities']['Version'] = "RELATION('00000000-0000-0000-0000-000000000050')"
        return schema

    def reg(self):
        return {'data_sources': {k: f'00000000-0000-0000-0000-{i:012d}' for i, k in enumerate(notion_plan.BLUE['databases'], 50)}}

    def test_additive_upgrade_keeps_existing_options(self):
        ops = {op['operation_key']: op['arguments']['statements'] for op in notion_plan.upgrade(self.reg(), self.old_schema())}
        self.assertEqual(set(ops), {'upgrade/1.1.0/entities', 'upgrade/1.1.0/links'})
        entities = ops['upgrade/1.1.0/entities']
        self.assertIn('ADD COLUMN "Depth" SELECT(', entities)
        self.assertIn("'WorldRule':default", entities)
        self.assertIn("'Custom kind':pink, 'Location', 'HistoryEvent', 'Term')", entities)
        self.assertNotIn('DROP', entities)
        self.assertIn("'related', 'entails', 'exploits')", ops['upgrade/1.1.0/links'])

    def test_upgraded_schema_needs_nothing(self):
        current = {name: dict(spec['properties']) for name, spec in notion_plan.BLUE['databases'].items()}
        current['entities']['User Added'] = 'RICH_TEXT'
        self.assertEqual(notion_plan.upgrade(self.reg(), current), [])

    def test_refuses_retype_and_missing_schema(self):
        schema = self.old_schema()
        schema['entities']['Summary'] = 'NUMBER FORMAT \'dollar\''
        with self.assertRaises(ValueError):
            notion_plan.upgrade(self.reg(), schema)
        schema = self.old_schema()
        del schema['issues']
        with self.assertRaises(ValueError):
            notion_plan.upgrade(self.reg(), schema)

    def test_new_views_only(self):
        reg = {'project_id': 'P', 'version_id': 'V1', 'version_page_id': '00000000-0000-0000-0000-000000000002', 'data_sources': self.reg()['data_sources'],
               'pages': {k: f'00000000-0000-0000-0000-{i:012d}' for i, k in enumerate(notion_plan.BLUE['pages'], 10)}}
        new = {'world_timeline', 'world_places', 'world_services', 'world_terms'}
        reg['views'] = {'V1/' + v['key']: 'returned-id' for v in notion_plan.BLUE['views'] if v['key'] not in new}
        ops = notion_plan.bootstrap(reg, 'views')
        self.assertEqual({op['operation_key'].rsplit('/', 1)[1] for op in ops}, new)
        timeline = next(op for op in ops if op['operation_key'].endswith('world_timeline'))
        self.assertTrue(timeline['arguments']['configure'].endswith('SORT BY "Event Time" ASC'))


if __name__ == '__main__':
    unittest.main()
