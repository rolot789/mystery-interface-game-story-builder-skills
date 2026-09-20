import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(os.environ.get('MYSTERY_SKILLS_ROOT',str(Path(__file__).resolve().parents[1]/'skills')))
MANAGER=next(p.parent for p in ROOT.glob('*/SKILL.md') if '\nname: notion-canon-manager\n' in p.read_text())
sys.path.insert(0,str(MANAGER/'scripts'))
import canon
import notion_plan

def sample():
    s={'schema_version':1,'project_id':'P1','version_id':'V1','title':'contract fixture','revision':1,'initial_state':{'result':'pending'},'entities':[],'links':[],'decisions':[{'id':'D1','question':'fixture authorization','answer':'approved fixture','status':'CONFIRMED'}],'issues':[],'pending_decisions':[],'session':{}}
    def add(id_,kind,data):
        s['entities'].append({'id':id_,'project_id':'P1','version_id':'V1','title':id_,'kind':kind,'revision':1,'owner':canon.OWNERS[kind],'status':'CONFIRMED','review':'VALID','depends_on':[],'decision_refs':['D1'],'data':data})
    add('R1','WorldRule',dict.fromkeys(canon.TEXT['WorldRule'],'fixture'))
    add('O1','Organization',dict.fromkeys(canon.TEXT['Organization'],'fixture'))
    add('S1','Service',{**dict.fromkeys(canon.TEXT['Service'],'fixture'),'provider_id':'O1'})
    add('C1','Character',dict.fromkeys(canon.TEXT['Character'],'fixture'))
    add('EV1','Event',{'at':'2026-01-01T00:00:00+00:00','actors':['C1'],'preconditions':['R1'],'action':'fixture','result':'fixture'})
    add('F1','Fact',{'statement':'fixture','basis':'fixture','event_id':'EV1'})
    add('T1','Trace',{'origin_type':'event','origin_ids':['EV1'],'summary':'fixture','access':'fixture','distortion':'none','created_at':None})
    add('K1','Knowledge',{'character_id':'C1','fact_id':'F1','state':'KNOWS','from':None,'until':None,'acquired_via':['T1']})
    add('CH1','Choice',{'prompt':'fixture','known_information':'fixture','available_when':True,'options':[{'id':'a','label':'a','condition':True,'effects':{'result':'a'}},{'id':'b','label':'b','condition':True,'effects':{'result':'b'}}]})
    for label in ['a','b']:
        add('END'+label,'Ending',{'condition':{'var':'result','eq':label},'consequences':'fixture '+label,'exclusive':True,'witness':[{'choice_id':'CH1','option_id':label}]})
    s['links']=[{'id':'L1','kind':'supports','source':'T1','target':'F1','reason':'fixture'}]
    return s

def reg():
    return {'project_id':'P1','version_id':'V1','title':'contract fixture','workspace_root_requested':True,'hub_page_id':'00000000-0000-0000-0000-000000000001','version_page_id':'00000000-0000-0000-0000-000000000002','pages':{k:f'00000000-0000-0000-0000-{i:012d}' for i,k in enumerate(notion_plan.BLUE['pages'],10)},'data_sources':{k:f'00000000-0000-0000-0000-{i:012d}' for i,k in enumerate(notion_plan.BLUE['databases'],50)},'bases':{}}

class Contracts(unittest.TestCase):
    def test_complete_fixture(self):self.assertEqual(canon.validate(sample(),True)['errors'],[])
    def test_cross_project(self):
        s=sample();s['entities'][0]['project_id']='other';self.assertTrue(canon.validate(s)['errors'])
    def test_duplicate_and_dangling(self):
        s=sample();s['entities'].append(copy.deepcopy(s['entities'][0]));self.assertTrue(canon.validate(s)['errors'])
        s=sample();s['entities'][2]['data']['provider_id']='missing';self.assertTrue(canon.validate(s)['errors'])
    def test_unapproved_provenance(self):
        s=sample();s['decisions'][0]['status']='PROPOSED';self.assertTrue(canon.validate(s)['errors'])
    def test_wrong_owner(self):
        s=sample();s['entities'][0]['owner']='mystery-plot-builder';self.assertTrue(canon.validate(s)['errors'])
    def test_knowledge_origin(self):
        s=sample();s['entities'][7]['data']['acquired_via']=[];self.assertTrue(canon.validate(s)['errors'])
    def test_unreachable_and_overlapping_endings(self):
        s=sample();s['entities'][-1]['data']['witness']=[{'choice_id':'CH1','option_id':'a'}];self.assertTrue(canon.validate(s)['errors'])
        s=sample();s['entities'][-1]['data']['condition']=True;self.assertTrue(canon.validate(s)['errors'])
    def test_effects_do_not_write_truth(self):
        s=sample();s['entities'][8]['data']['options'][0]['effects']['F1']=False;self.assertTrue(canon.validate(s)['errors'])
    def test_conditions_and_repeat(self):
        with self.assertRaises(ValueError):canon.condition({'all':[]},{})
        with self.assertRaises(ValueError):canon.walk(sample(),[{'choice_id':'CH1','option_id':'a'}]*2)
    def test_impact_transitive(self):
        r=canon.impact(sample(),['R1']);self.assertIn('K1',r['needs_review']);self.assertIn('F1',r['needs_review'])
    def test_render_round_trip(self):
        e=sample()['entities'][0];body=canon.managed(e)+'\n'+canon.END+'\nmy note';self.assertEqual(canon.extract(body)[0],e)
    def test_blueprint_stages_and_resume(self):
        r=reg();self.assertEqual(notion_plan.bootstrap(r,'root'),[]);self.assertEqual(notion_plan.bootstrap(r,'pages'),[]);self.assertEqual(notion_plan.bootstrap(r,'databases'),[])
        rel=notion_plan.bootstrap(r,'relations');self.assertTrue(rel)
        for op in rel:self.assertIn('RELATION(',op['arguments']['statements'])
        views=notion_plan.bootstrap(r,'views');self.assertEqual(len(views),10)
        r['views']={op['operation_key'].removeprefix('bootstrap/view/'):'returned-id' for op in views};self.assertEqual(notion_plan.bootstrap(r,'views'),[])
    def test_destination_and_id_validation(self):
        with self.assertRaises(ValueError):notion_plan.bootstrap({'project_id':'P1','version_id':'V1','title':'x'},'root')
        with self.assertRaises(ValueError):notion_plan.uid("x'); DROP TABLE a")
    def test_upsert_idempotent_and_notes(self):
        s=sample();r=reg();ops=notion_plan.upsert(s,r,{'complete':True,'records':[]},'entities');rows=[]
        for i,op in enumerate(ops):
            p=op['arguments']['pages'][0];rows.append({'page_id':f'00000000-0000-0000-0000-{100+i:012d}','properties':p['properties'],'body':p['content']+'\nKEEP THIS NOTE'})
        remote={'complete':True,'records':rows}
        self.assertEqual(notion_plan.upsert(s,r,remote,'entities'),[])
        old=rows[0];r['bases'][old['properties']['Key']]={'revision':1,'hash':old['properties']['Content Hash']}
        s['entities'][0]['data']['statement']='changed';s['entities'][0]['revision']=2
        updates=notion_plan.upsert(s,r,remote,'entities');self.assertEqual(len(updates),2)
        patch=updates[0]['arguments']['content_updates'][0];updated=old['body'].replace(patch['old_str'],patch['new_str']);self.assertIn('KEEP THIS NOTE',updated)
    def test_conflicts(self):
        s=sample();r=reg();op=notion_plan.upsert(s,r,{'complete':True,'records':[]},'entities')[0];p=op['arguments']['pages'][0]
        row={'page_id':'00000000-0000-0000-0000-000000000100','properties':p['properties'],'body':p['content']};remote={'complete':True,'records':[row]}
        row['body']=row['body'].replace('#### 내용\nfixture','#### 내용\nhuman edit')
        with self.assertRaises(ValueError):notion_plan.upsert(s,r,remote,'entities')
        with self.assertRaises(ValueError):notion_plan.upsert(s,r,{'complete':False,'records':[]},'entities')
    def test_blocker_cannot_be_accepted_away(self):
        s=sample();s['issues']=[{'id':'Q1','severity':'BLOCKER','status':'ACCEPTED','affected_ids':['F1']}];self.assertTrue(canon.validate(s,True)['errors'])

if __name__=='__main__':unittest.main()
