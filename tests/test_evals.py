import copy
import json
import os
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get('MYSTERY_SKILLS_ROOT', str(REPO / 'skills')))
MANAGER = next(p.parent for p in ROOT.glob('*/SKILL.md') if '\nname: notion-canon-manager\n' in p.read_text())
sys.path.insert(0, str(MANAGER / 'scripts'))
import canon

SCENARIOS = json.loads((REPO / 'evals' / 'scenarios.json').read_text())['scenarios']
SKILLS = set(json.loads((REPO / 'suite.json').read_text())['skills'])


def locate(snapshot, path):
    """Resolve a patch path; an entity is addressed by its id after "entities"."""
    parent, rest = snapshot, list(path)
    if rest[0] == 'entities':
        parent = next(e for e in snapshot['entities'] if e['id'] == rest[1])
        rest = rest[2:]
        if not rest:
            return snapshot['entities'], snapshot['entities'].index(parent)
    for key in rest[:-1]:
        parent = parent[key]
    return parent, rest[-1]


def apply(snapshot, patch):
    s = copy.deepcopy(snapshot)
    for op in patch:
        if 'set' in op:
            parent, key = locate(s, op['set'])
            parent[key] = copy.deepcopy(op['value'])
        elif 'delete' in op:
            parent, key = locate(s, op['delete'])
            del parent[key]
        else:
            raise ValueError('unknown patch op: ' + json.dumps(op))
    return s


def rules(snapshot, complete):
    return {f['rule'] for f in canon.validate(snapshot, complete)['findings']}


class Scenarios(unittest.TestCase):
    def test_shape(self):
        ids = [x['id'] for x in SCENARIOS]
        self.assertEqual(len(ids), len(set(ids)))
        for x in SCENARIOS:
            self.assertTrue(set(x['skills']) <= SKILLS, x['id'])
            self.assertTrue((REPO / x['fixture']).is_file(), x['id'])
            self.assertTrue(x['prompt'] and x['expect'] and x['avoid'], x['id'])

    def test_ground_truth_matches_validator(self):
        for x in [x for x in SCENARIOS if 'ground_truth' in x]:
            with self.subTest(x['id']):
                truth = x['ground_truth']
                complete = truth.get('complete', False)
                base = json.loads((REPO / x['fixture']).read_text())
                changed = apply(base, truth['patch'])
                self.assertFalse(set(truth['rules']) & rules(base, complete), 'rule already fires before the change')
                if truth['rules']:
                    self.assertTrue(set(truth['rules']) <= rules(changed, complete))
                else:
                    self.assertEqual(canon.validate(changed, complete)['errors'], [])


if __name__ == '__main__':
    unittest.main()
