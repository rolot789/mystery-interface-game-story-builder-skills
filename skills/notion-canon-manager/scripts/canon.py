#!/usr/bin/env python3
"""Offline Canon tools. No credentials, network writes or model calls."""
import argparse
import copy
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

KINDS = {'WorldRule','Organization','Service','Character','Event','Fact','Claim','Knowledge','Trace','Choice','Ending'}
STATUSES = {'DRAFT','PROPOSED','CONFIRMED','SUPERSEDED','REJECTED'}
REVIEWS = {'NOT_CHECKED','VALID','NEEDS_REVIEW','BLOCKED'}
OWNERS = {**dict.fromkeys(['WorldRule','Organization','Service'],'mystery-world-builder'), **dict.fromkeys(['Character','Knowledge','Claim'],'character-knowledge-builder'), **dict.fromkeys(['Event','Fact','Trace','Choice','Ending'],'mystery-plot-builder')}
TEXT = {'WorldRule':['statement','scope','exceptions','grounding'], 'Organization':['purpose','economy','operations','culture','daily_life'], 'Service':['purpose','users','normal_use','data_lifecycle','permissions','failures'], 'Character':['identity','motive','daily_life','relationships'], 'Event':['action','result'], 'Fact':['statement','basis'], 'Claim':['statement','audience','intent'], 'Knowledge':['state'], 'Trace':['origin_type','summary','access','distortion'], 'Choice':['prompt','known_information'], 'Ending':['consequences']}
REFS = {'Service':{'provider_id':{'Organization'}}, 'Event':{'actors':{'Character','Organization','Service'},'preconditions':{'Event','Fact','WorldRule'}}, 'Fact':{'event_id':{'Event'},'world_rule_id':{'WorldRule'}}, 'Claim':{'speaker_id':{'Character','Organization','Service'}}, 'Knowledge':{'character_id':{'Character'},'fact_id':{'Fact'},'acquired_via':{'Event','Trace','Claim'}}, 'Trace':{'origin_ids':{'Event','WorldRule','Service'},'author_id':{'Character','Organization','Service'}}}
LINKS = {'supports':({'Trace'},{'Fact','Claim'}), 'contradicts':({'Trace'},{'Fact','Claim'}), 'generates':({'Event','Service'},{'Trace'}), 'knows':({'Character'},{'Fact'}), 'depends_on':(KINDS,KINDS), 'related':(KINDS,KINDS)}
BEGIN='## Canon Managed Data'
END='## User Notes'

def canonical(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(x): return hashlib.sha256(canonical(x).encode()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def integer(x): return type(x) is int and x >= 0
def scalar(x): return type(x) in (str,int,float,bool) and (not isinstance(x,float) or abs(x)!=float('inf'))
def stamp(s):
    if s is None: return None
    d=datetime.fromisoformat(s.replace('Z','+00:00'))
    if d.tzinfo is None: raise ValueError('timestamp requires timezone')
    return d

def condition(c,state):
    if type(c) is bool:return c
    if not isinstance(c,dict):raise ValueError('condition must be boolean or object')
    if set(c)=={'all'} or set(c)=={'any'}:
        key=next(iter(c)); vals=c[key]
        if not isinstance(vals,list) or not vals:raise ValueError('all/any requires a nonempty list')
        results=[condition(v,state) for v in vals]
        return all(results) if key=='all' else any(results)
    if set(c)=={'not'}:return not condition(c['not'],state)
    if set(c)=={'var','eq'}:
        if c['var'] not in state:raise ValueError('unknown state variable: '+str(c['var']))
        if not scalar(c['eq']):raise ValueError('eq value must be scalar')
        return type(state[c['var']]) is type(c['eq']) and state[c['var']]==c['eq']
    raise ValueError('unsupported condition keys')

def references(e):
    refs=list(e.get('depends_on',[]));d=e.get('data',{})
    for key in REFS.get(e.get('kind'),{}):
        value=d.get(key)
        if value is not None:refs.extend(value if isinstance(value,list) else [value])
    if e.get('kind')=='Ending':refs.extend(x.get('choice_id') for x in d.get('witness',[]) if isinstance(x,dict))
    return [x for x in refs if isinstance(x,str)]

def walk(snapshot,steps):
    state=copy.deepcopy(snapshot['initial_state']); entities={e['id']:e for e in snapshot['entities']}; used=set()
    if not isinstance(steps,list):raise ValueError('witness must be list')
    for step in steps:
        if not isinstance(step,dict) or set(step)!={'choice_id','option_id'}:raise ValueError('invalid witness step')
        eid=step['choice_id']
        if eid in used:raise ValueError('choice repeated: '+eid)
        e=entities.get(eid)
        if not e or e['kind']!='Choice' or e['status'] in {'SUPERSEDED','REJECTED'}:raise ValueError('unavailable choice: '+eid)
        d=e['data']
        if not condition(d['available_when'],state):raise ValueError('choice precondition failed: '+eid)
        options=[o for o in d['options'] if o['id']==step['option_id']]
        if len(options)!=1:raise ValueError('option missing/duplicate')
        o=options[0]
        if not condition(o['condition'],state):raise ValueError('option precondition failed')
        for k,v in o['effects'].items():
            if k not in state or type(v) is not type(state[k]):raise ValueError('undeclared variable or type-changing effect')
            state[k]=v
        used.add(eid)
    return state

def validate(s,complete=False):
    errors=[];warnings=[]
    def fail(msg):errors.append(msg)
    if not isinstance(s,dict):return {'errors':['snapshot must be object'],'warnings':[]}
    for k in ['project_id','version_id','title']:
        if not isinstance(s.get(k),str) or not s[k].strip():fail(k+' must be nonempty string')
    if s.get('schema_version')!=1:fail('schema_version must be 1')
    if not integer(s.get('revision')):fail('revision must be nonnegative integer')
    state=s.get('initial_state')
    if not isinstance(state,dict) or not all(isinstance(k,str) and scalar(v) for k,v in state.items()):fail('initial_state must contain scalar values');state={}
    es=s.get('entities');ls=s.get('links');ds=s.get('decisions');issues=s.get('issues')
    if not all(isinstance(x,list) for x in [es,ls,ds,issues]):return {'errors':errors+['entities, links, decisions, issues must be lists'],'warnings':warnings}
    index={};decision_ids=set();confirmed_decisions=set();allids=set()
    for collection in [es,ls,ds,issues]:
        for item in collection:
            if not isinstance(item,dict):fail('record must be object');continue
            id_=item.get('id')
            if not isinstance(id_,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',id_):fail('invalid id: '+str(id_));continue
            if id_ in allids:fail('duplicate id: '+id_)
            allids.add(id_)
    for d in ds:
        if not isinstance(d,dict):continue
        decision_ids.add(d.get('id'))
        if d.get('status')=='CONFIRMED' and d.get('answer'):confirmed_decisions.add(d.get('id'))
        if d.get('status') not in STATUSES:fail('invalid decision status')
        if not isinstance(d.get('question'),str):fail('decision question missing')
        if d.get('status')=='CONFIRMED' and not d.get('answer'):fail('confirmed decision requires user answer')
    for e in es:
        if not isinstance(e,dict):continue
        eid=e.get('id','?');kind=e.get('kind');d=e.get('data')
        if isinstance(eid,str):index[eid]=e
        if kind not in KINDS:fail(f'{eid}: unknown kind');continue
        if e.get('project_id')!=s.get('project_id') or e.get('version_id')!=s.get('version_id'):fail(f'{eid}: cross-project/version entity')
        if not integer(e.get('revision')):fail(f'{eid}: invalid revision')
        if not isinstance(e.get('title'),str) or not e['title'].strip():fail(f'{eid}: title missing')
        if e.get('owner')!=OWNERS[kind]:fail(f'{eid}: wrong owner')
        if e.get('status') not in STATUSES or e.get('review') not in REVIEWS:fail(f'{eid}: invalid status/review')
        if not isinstance(e.get('depends_on'),list):fail(f'{eid}: depends_on must be list')
        if not isinstance(e.get('decision_refs'),list):fail(f'{eid}: decision_refs must be list')
        elif any(x not in decision_ids for x in e['decision_refs']):fail(f'{eid}: unknown decision ref')
        if e.get('status')=='CONFIRMED' and (not e.get('decision_refs') or any(x not in confirmed_decisions for x in e.get('decision_refs',[]))):fail(f'{eid}: confirmed entity needs confirmed decision provenance')
        if not isinstance(d,dict):fail(f'{eid}: data must be object');continue
        for key in TEXT[kind]:
            if not isinstance(d.get(key),str) or not d[key].strip():fail(f'{eid}: data.{key} must be nonempty text (use explicit unresolved text in drafts)')
        for key in ['at','stated_at','created_at','from','until']:
            if key in d:
                try:stamp(d[key])
                except (TypeError,ValueError,AttributeError):fail(f'{eid}: invalid zoned timestamp {key}')
        if kind=='Knowledge':
            if d.get('state') not in {'KNOWS','BELIEVES','SUSPECTS','UNKNOWN'}:fail(f'{eid}: invalid knowledge state')
            if d.get('state')!='UNKNOWN' and not d.get('acquired_via') and not d.get('initial_basis'):fail(f'{eid}: knowledge acquisition missing')
            try:
                if d.get('from') and d.get('until') and stamp(d['from'])>=stamp(d['until']):fail(f'{eid}: invalid knowledge interval')
            except (ValueError,TypeError,AttributeError):pass
        if kind=='Claim' and d.get('intent') not in {'truthful','lie','mistaken','uncertain'}:fail(f'{eid}: invalid claim intent')
        if kind=='Trace' and d.get('origin_type') not in {'event','routine','system'}:fail(f'{eid}: invalid trace origin')
        if kind=='Choice':
            try:
                condition(d['available_when'],state)
                if not isinstance(d['options'],list) or len(d['options'])<2:raise ValueError('at least two options required')
                seen=set()
                for o in d['options']:
                    if not isinstance(o,dict) or not isinstance(o.get('id'),str) or not o.get('label') or o['id'] in seen:raise ValueError('invalid/duplicate option')
                    seen.add(o['id']);condition(o['condition'],state)
                    if not isinstance(o['effects'],dict):raise ValueError('effects must be object')
                    for k,v in o['effects'].items():
                        if k not in state or type(v) is not type(state[k]):raise ValueError('undeclared variable or effect type mismatch')
            except (KeyError,TypeError,ValueError) as exc:fail(f'{eid}: {exc}')
        if kind=='Ending':
            try:
                condition(d['condition'],state)
                if type(d['exclusive']) is not bool:raise ValueError('exclusive must be boolean')
                if not isinstance(d['witness'],list):raise ValueError('witness must be list')
            except (KeyError,TypeError,ValueError) as exc:fail(f'{eid}: {exc}')
    for eid,e in index.items():
        if not isinstance(e.get('data'),dict) or not isinstance(e.get('depends_on'),list):continue
        for ref in references(e):
            if ref not in index:fail(f'{eid}: dangling ref {ref}')
            elif e.get('status') not in {'SUPERSEDED','REJECTED'} and index[ref].get('status') in {'SUPERSEDED','REJECTED'}:fail(f'{eid}: active reference to inactive {ref}')
        for key,allowed in REFS.get(e.get('kind'),{}).items():
            val=e['data'].get(key)
            if key in {'actors','preconditions','acquired_via','origin_ids'} and val is not None and not isinstance(val,list):fail(f'{eid}: {key} must be list')
            if val is None:continue
            vals=val if isinstance(val,list) else [val]
            if any(not isinstance(x,str) or x not in index or index[x]['kind'] not in allowed for x in vals):fail(f'{eid}: wrong reference type {key}')
        required_refs={'Service':['provider_id'],'Event':['actors','preconditions'],'Claim':['speaker_id'],'Knowledge':['character_id','fact_id','acquired_via'],'Trace':['origin_ids']}.get(e['kind'],[])
        for key in required_refs:
            if key not in e['data']:fail(f'{eid}: missing {key}')
    for link in ls:
        if not isinstance(link,dict):continue
        a=index.get(link.get('source'));b=index.get(link.get('target'));kind=link.get('kind')
        if kind not in LINKS or not a or not b:fail('invalid/dangling link: '+str(link.get('id')));continue
        sa,tb=LINKS[kind]
        if a['kind'] not in sa or b['kind'] not in tb:fail('invalid link endpoint types: '+link['id'])
        if not link.get('reason'):fail('link needs reason: '+link['id'])
    if not errors:
        endings=[e for e in es if e['kind']=='Ending' and e['status'] not in {'SUPERSEDED','REJECTED'}]
        for e in endings:
            try:
                endstate=walk(s,e['data']['witness'])
                if not condition(e['data']['condition'],endstate):fail(e['id']+': witness does not reach ending')
                if e['data']['exclusive']:
                    hits=[x['id'] for x in endings if condition(x['data']['condition'],endstate)]
                    if len(hits)>1:fail(e['id']+': exclusive ending overlaps on witness: '+','.join(hits))
            except (KeyError,TypeError,ValueError) as exc:fail(e['id']+': '+str(exc))
        if complete and len(endings)<2:fail('completion needs at least two endings')
    for i in issues:
        if not isinstance(i,dict):continue
        if i.get('severity') not in {'BLOCKER','MAJOR','MINOR'} or i.get('status') not in {'OPEN','RESOLVED','ACCEPTED'}:fail('invalid QA issue state')
        if any(x not in index for x in i.get('affected_ids',[])):fail('QA refers to unknown entity')
        if complete and i.get('severity')=='BLOCKER' and i.get('status')!='RESOLVED':fail('unresolved blocker: '+i.get('id','?'))
    if complete:
        active=[e for e in es if e.get('status') not in {'SUPERSEDED','REJECTED'}]
        for kind in ['WorldRule','Organization','Service','Character','Event','Fact','Trace','Choice','Ending']:
            if not any(e.get('kind')==kind for e in active):fail('completion missing '+kind)
        if any(e.get('status')!='CONFIRMED' or e.get('review')!='VALID' for e in active):fail('completion requires confirmed, reviewed active entities')
        if s.get('pending_decisions'):fail('completion has pending decisions; classify/defer peripheral items before finalization')
    warnings.append('Semantic causality, knowledge plausibility and full-path fairness require narrative review.')
    return {'errors':errors,'warnings':warnings}

def impact(s,ids):
    index={e['id']:e for e in s['entities']}
    if any(x not in index for x in ids):raise ValueError('unknown changed entity')
    graph={k:set() for k in index}
    for e in index.values():
        for ref in references(e):
            if ref in graph:graph[ref].add(e['id'])
    for link in s['links']:
        a,b=link['source'],link['target']
        if link['kind']=='depends_on':a,b=b,a
        if a in graph:graph[a].add(b)
    seen=set(ids);queue=list(ids)
    while queue:
        for target in graph.get(queue.pop(0),set()):
            if target not in seen:seen.add(target);queue.append(target)
    return {'changed':sorted(ids),'needs_review':sorted(seen-set(ids)),'note':'Explicit dependency closure; also review semantic dependencies.'}

def managed(e):
    labels={'statement':'내용','scope':'적용 범위','exceptions':'예외','grounding':'설정 근거','purpose':'존재 목적','economy':'재원과 사업','operations':'운영','culture':'문화','daily_life':'일상','identity':'정체성','motive':'동기','relationships':'관계','users':'사용자','normal_use':'정상 이용','data_lifecycle':'데이터 수명','permissions':'권한','failures':'실패와 지원','action':'행동','result':'결과','basis':'근거','summary':'기록 개요','access':'접근 경로','distortion':'왜곡','prompt':'선택 쟁점','known_information':'선택 당시의 정보','consequences':'결과'}
    lines=[BEGIN,'### 설정 내용']
    for k,v in e.get('data',{}).items():
        if isinstance(v,str) and v and not k.endswith('_id'):
            lines.extend(['#### '+labels.get(k,k),v])
    lines.extend(['### 구조화 원본','```json',json.dumps(e,ensure_ascii=False,indent=2),'```',''])
    return '\n'.join(lines)

def extract(body):
    if body.count(BEGIN)!=1 or body.count(END)!=1:raise ValueError('managed/user markers missing or ambiguous')
    a=body.index(BEGIN);b=body.index(END)
    if a>=b:raise ValueError('marker order invalid')
    part=body[a:b].strip()
    m=re.search(r'### 구조화 원본\n```json\n(.*)\n```$',part,re.S)
    if not m:raise ValueError('managed JSON block malformed')
    return json.loads(m.group(1)),body[a:b]

def main():
    p=argparse.ArgumentParser(description=__doc__);sp=p.add_subparsers(dest='cmd',required=True)
    n=sp.add_parser('new');n.add_argument('--project-id',required=True);n.add_argument('--version-id',required=True);n.add_argument('--title',required=True);n.add_argument('--output',required=True)
    for name in ['validate','impact','render']:
        q=sp.add_parser(name);q.add_argument('snapshot')
        if name=='validate':q.add_argument('--complete',action='store_true')
        if name=='impact':q.add_argument('ids',nargs='+')
        if name=='render':q.add_argument('entity_id')
    a=p.parse_args()
    if a.cmd=='new':
        obj={'schema_version':1,'project_id':a.project_id,'version_id':a.version_id,'title':a.title,'revision':0,'initial_state':{},'entities':[],'links':[],'decisions':[],'issues':[],'pending_decisions':[],'session':{}}
        with open(a.output,'x') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
        return
    s=read(a.snapshot)
    if a.cmd=='validate':
        result=validate(s,a.complete);print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(bool(result['errors']))
    report=validate(s)
    if report['errors']:raise ValueError('; '.join(report['errors']))
    if a.cmd=='impact':print(json.dumps(impact(s,a.ids),ensure_ascii=False,indent=2))
    elif a.cmd=='render':
        e=next((e for e in s['entities'] if e['id']==a.entity_id),None)
        if e is None:raise ValueError('entity not found')
        print(managed(e)+'\n'+END+'\n사용자가 직접 남기는 메모. 확정 설정 변경은 변경 요청으로 기록한다.\n')
if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,TypeError,OSError,json.JSONDecodeError) as exc:print(str(exc),file=sys.stderr);sys.exit(2)
