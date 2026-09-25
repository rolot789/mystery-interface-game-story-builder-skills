#!/usr/bin/env python3
"""Generate Notion MCP requests; never execute network mutations."""
import argparse
import json
import re
import sys
import uuid
from pathlib import Path
import canon
ASSETS=Path(__file__).resolve().parents[1]/'assets'
BLUE=json.loads((ASSETS/'notion-blueprint.json').read_text())
TEMPLATES=json.loads((ASSETS/'page-templates.json').read_text())

def uid(value):
    if not isinstance(value,str):raise ValueError('Notion ID must be returned UUID')
    return str(uuid.UUID(value.removeprefix('collection://')))
def ds(reg,key):return uid(reg['data_sources'][key])
def request(key,tool,args):return {'operation_key':key,'tool':tool,'arguments':args}
def key(reg,id_):return '/'.join([reg['project_id'],reg['version_id'],id_])
def wrap(reg,id_,title,data,revision=0):return {'id':id_,'project_id':reg['project_id'],'version_id':reg['version_id'],'title':title,'revision':revision,'data':data}

def event_time(value):
    # Exact times keep the v1 property shape; uncertain ranges use start/end.
    if isinstance(value,str):return {'date:Event Time:start':value,'date:Event Time:is_datetime':1}
    if isinstance(value,dict):
        start=value.get('earliest') or value.get('latest');p={'date:Event Time:start':start,'date:Event Time:is_datetime':1}
        if value.get('earliest') and value.get('latest'):p['date:Event Time:end']=value['latest']
        return p
    return {}

# Date shown on the world timeline view for kinds that carry a year-like anchor.
TIMELINE={'Event':'at','HistoryEvent':'at','Organization':'founded_at','Service':'launched_at'}
def edge(value,first):
    if isinstance(value,str):return value
    if isinstance(value,dict):return value.get('earliest' if first else 'latest') or value.get('latest' if first else 'earliest')
def timeline(e):
    d=e['data']
    if e['kind'] in TIMELINE:return event_time(d.get(TIMELINE[e['kind']]))
    if e['kind']=='WorldRule' and d.get('valid_from'):return event_time({k:v for k,v in [('earliest',edge(d['valid_from'],True)),('latest',edge(d.get('valid_until'),False))] if v})
    return {}

def version_data(s):
    data={'initial_state':s['initial_state'],'pending_decisions':s.get('pending_decisions',[])}
    if 'charter' in s:data['charter']=s['charter']
    return data

def bootstrap(reg,phase):
    out=[];pages=reg.get('pages',{});sources=reg.get('data_sources',{})
    if phase=='root':
        if reg.get('hub_page_id'):return []
        args={'pages':[{'properties':{'title':reg['title']},'content':TEMPLATES['hub']}]}
        if reg.get('parent_page_id'):args['parent']={'page_id':uid(reg['parent_page_id'])}
        elif not reg.get('workspace_root_requested'):raise ValueError('choose parent or explicit workspace-root destination before creating')
        out.append(request('bootstrap/hub','notion_create_pages',args))
    elif phase=='pages':
        hub=uid(reg['hub_page_id'])
        for page,title in BLUE['pages'].items():
            if page not in pages:out.append(request('bootstrap/page/'+page,'notion_create_pages',{'parent':{'page_id':hub},'pages':[{'properties':{'title':title},'content':TEMPLATES[page]}]}))
    elif phase=='databases':
        parent=uid(pages['management'])
        for name,spec in BLUE['databases'].items():
            if name in sources:continue
            ddl='CREATE TABLE ('+', '.join('"'+k+'" '+v for k,v in spec['properties'].items())+')'
            out.append(request('bootstrap/db/'+name,'notion_create_database',{'parent':{'page_id':parent},'title':spec['title'],'schema':ddl}))
    elif phase=='relations':
        applied=reg.get('relations_applied',[])
        for name,spec in BLUE['databases'].items():
            for prop,target in spec['relations'].items():
                op=name+'/'+prop
                if op in applied:continue
                out.append(request('bootstrap/relation/'+op,'notion_update_data_source',{'data_source_id':ds(reg,name),'statements':'ADD COLUMN "'+prop+'" RELATION(\''+ds(reg,target)+'\')'}))
    elif phase=='version':
        if reg.get('version_page_id'):return []
        version=wrap(reg,'VERSION',reg['version_id'],{'initial_state':{},'pending_decisions':[]},0)
        props={'Name':reg['version_id'],'Key':key(reg,'VERSION'),'Version ID':reg['version_id'],'Status':'ACTIVE','Current Revision':0,'Revision':0,'Content Hash':canon.digest(version)}
        out.append(request('bootstrap/version/'+reg['version_id'],'notion_create_pages',{'parent':{'data_source_id':ds(reg,'versions')},'pages':[{'properties':props,'content':canon.managed(version)+'\n'+canon.END+'\n'}]}))
    elif phase=='views':
        version=uid(reg['version_page_id'])
        for view in BLUE['views']:
            op=reg['version_id']+'/'+view['key']
            if op in reg.get('views',{}):continue
            filters=[]
            if view['database']!='versions':filters.append('"Version" = "'+version+'"')
            if view.get('filter'):filters.append('('+view['filter']+')')
            by,order=view.get('sort',['Name','ASC'])
            dsl=('FILTER '+' AND '.join(filters)+'; ' if filters else '')+'SHOW '+', '.join('"'+x+'"' for x in view['show'])+'; SORT BY "'+by+'" '+order
            out.append(request('bootstrap/view/'+op,'notion_create_view',{'parent_page_id':uid(pages[view['page']]),'data_source_id':ds(reg,view['database']),'name':view['name']+' · '+reg['version_id'],'type':view['type'],'configure':dsl}))
    return out

def desired_records(s,reg,collection):
    v=[uid(reg['version_page_id'])];out=[];entity_pages=reg.get('entity_pages',{})
    def targets(ids):
        return [uid(entity_pages[x]) for x in ids]
    if collection=='entities':
        for e in s['entities']:
            d=e['data'];summary=next((d[k] for k in ['statement','summary','purpose','description','definition'] if isinstance(d.get(k),str)),e['title'])
            p={'Name':e['title'],'Key':key(reg,e['id']),'Entity ID':e['id'],'Kind':e['kind'],'Version':v,'Canon':e['status'],'Review':e['review'],'Owner':e['owner'],'Summary':summary[:1000]}
            p.update(timeline(e))
            p.update({name:e[k] for k,name in [('depth','Depth'),('visibility','Visibility'),('origin','Origin')] if k in e})
            out.append((e,p))
    elif collection=='versions':
        obj=wrap(reg,'VERSION',reg['version_id'],version_data(s),s['revision'])
        out.append((obj,{'Name':reg['version_id'],'Key':key(reg,'VERSION'),'Version ID':reg['version_id'],'Current Revision':s['revision'],'Status':'ACTIVE'}))
    elif collection=='sessions':
        sess=s.get('session',{})
        if not sess:return []
        if not sess.get('id'):raise ValueError('session id required')
        obj=wrap(reg,sess['id'],sess.get('title',sess['id']),sess,s['revision'])
        out.append((obj,{'Name':obj['title'],'Key':key(reg,obj['id']),'Version':v,'Phase':sess.get('phase',''),'Next Question':sess.get('next_question',''),'Sync':sess.get('sync_state','PENDING_SYNC')}))
    else:
        for row in s[collection]:
            obj=wrap(reg,row['id'],row.get('title',row['id']),row,row.get('revision',s['revision']))
            p={'Name':obj['title'],'Key':key(reg,obj['id']),'Version':v}
            if collection=='links':p.update({'Relation':row['kind'],'Source':targets([row['source']]),'Target':targets([row['target']]),'Reason':row['reason']})
            elif collection=='decisions':p.update({'Status':row['status'],'Question':row['question'],'Answer':row.get('answer',''),'Rationale':row.get('rationale',''),'Affected':targets(row.get('affected_ids',[]))})
            elif collection=='issues':p.update({'Severity':row['severity'],'Status':row['status'],'Affected':targets(row.get('affected_ids',[]))})
            out.append((obj,p))
    return out

def upsert(s,reg,remote,collection):
    if reg['project_id']!=s['project_id'] or reg['version_id']!=s['version_id']:raise ValueError('registry/snapshot scope mismatch')
    report=canon.validate(s)
    if report['errors']:raise ValueError('; '.join(report['errors']))
    if remote.get('complete') is not True:raise ValueError('remote lookup must be complete for all requested keys')
    found={}
    for r in remote.get('records',[]):
        k=r['properties']['Key']
        if k in found:raise ValueError('duplicate remote Key: '+k)
        found[k]=r
    out=[]
    for obj,props in desired_records(s,reg,collection):
        k=props['Key'];hash_=canon.digest(obj);props.update({'Revision':obj['revision'],'Content Hash':hash_})
        existing=found.get(k)
        if not existing:
            if k in reg.get('bases',{}):raise ValueError('previously known record missing; resolve deletion or lookup scope: '+k)
            out.append(request('create/'+k,'notion_create_pages',{'parent':{'data_source_id':ds(reg,collection)},'pages':[{'properties':props,'content':canon.managed(obj)+'\n'+canon.END+'\n사용자 메모.'}]}));continue
        remote_obj,old=canon.extract(existing['body']);rp=existing['properties'];actual=canon.digest(remote_obj)
        if rp.get('Content Hash')!=actual or rp.get('Revision')!=remote_obj.get('revision'):raise ValueError('remote content/metadata divergence: '+k)
        # A user may edit the readable portion; do not discard those edits.
        if old.strip()!=canon.managed(remote_obj).strip():raise ValueError('remote readable content changed: '+k)
        if actual==hash_:
            if any(rp.get(x)!=val for x,val in props.items()):raise ValueError('remote property divergence: '+k)
            continue
        base=reg.get('bases',{}).get(k)
        if not base or base.get('hash')!=actual or base.get('revision')!=rp['Revision']:raise ValueError('stale/missing base: '+k)
        if obj['revision']<=rp['Revision']:raise ValueError('changed record revision must advance: '+k)
        page=uid(existing['page_id'])
        out.append(request('content/'+k,'notion_update_page',{'page_id':page,'command':'update_content','content_updates':[{'old_str':old,'new_str':canon.managed(obj)+'\n'}],'allow_async':False}))
        out.append(request('properties/'+k,'notion_update_page',{'page_id':page,'command':'update_properties','properties':props,'allow_async':False}))
    return out

def parse_type(text):
    m=re.fullmatch(r'\s*(MULTI_SELECT|SELECT)\s*\((.*)\)\s*',text,re.S)
    if not m:return re.split(r'[\s(]',text.strip(),maxsplit=1)[0].upper(),None
    return m.group(1),[(n.replace("''","'"),c or None) for n,c in re.findall(r"'((?:[^']|'')*)'(?:\s*:\s*(\w+))?",m.group(2))]
def select_type(kind,options):return kind+'('+', '.join("'"+n.replace("'","''")+"'"+(':'+c if c else '') for n,c in options)+')'

def upgrade(reg,current):
    """Plan additive schema changes from the fetched schema to the current template; never drop or retype."""
    out=[]
    for name,spec in BLUE['databases'].items():
        if not isinstance(current.get(name),dict):raise ValueError('fetch the data source and pass its current schema: '+name)
        have=current[name];statements=[]
        for prop,want in spec['properties'].items():
            if prop not in have:statements.append('ADD COLUMN "'+prop+'" '+want);continue
            wkind,wopts=parse_type(want);hkind,hopts=parse_type(have[prop])
            if hkind!=wkind:raise ValueError(f'{name}.{prop} is {hkind} but the template expects {wkind}; resolve it by hand')
            missing=[(n,c) for n,c in wopts or [] if n not in {x for x,_ in hopts}]
            # ALTER ... SET replaces the whole option list: keep every existing option and color, then append.
            if missing:statements.append('ALTER COLUMN "'+prop+'" SET '+select_type(hkind,hopts+missing))
        if statements:out.append(request('upgrade/'+BLUE['template_version']+'/'+name,'notion_update_data_source',{'data_source_id':ds(reg,name),'statements':'; '.join(statements)}))
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);sp=p.add_subparsers(dest='cmd',required=True)
    b=sp.add_parser('bootstrap');b.add_argument('registry');b.add_argument('--phase',required=True,choices=['root','pages','databases','relations','version','views'])
    g=sp.add_parser('upgrade');g.add_argument('registry');g.add_argument('schema')
    u=sp.add_parser('upsert');u.add_argument('snapshot');u.add_argument('registry');u.add_argument('remote');u.add_argument('--collection',required=True,choices=['entities','links','decisions','issues','sessions','versions'])
    a=p.parse_args();reg=canon.read(a.registry)
    if a.cmd=='bootstrap':out=bootstrap(reg,a.phase)
    elif a.cmd=='upgrade':out=upgrade(reg,canon.read(a.schema))
    else:out=upsert(canon.read(a.snapshot),reg,canon.read(a.remote),a.collection)
    print(json.dumps({'executed':False,'operations':out},ensure_ascii=False,indent=2))
if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,TypeError,OSError) as exc:print(str(exc),file=sys.stderr);sys.exit(2)
