#!/usr/bin/env python3
"""Check portable suite packaging and local resource links (stdlib only)."""
from pathlib import Path
import json
import re
import sys
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'suite.json').read_text())
errors=[];contracts={}
for name in manifest['skills']:
    folder=root/'skills'/name;p=folder/'SKILL.md'
    if not p.exists():errors.append('missing skill '+name);continue
    text=p.read_text()
    if not text.startswith('---\nname: '+name+'\n'):errors.append('name mismatch '+name)
    if 'description: ' not in text.split('---',2)[1]:errors.append('missing description '+name)
    if not (folder/'agents/openai.yaml').is_file():errors.append('missing UI metadata '+name)
    for md in folder.rglob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)',md.read_text()):
            if '://' in target or target.startswith('#'):continue
            if not (md.parent/target.split('#')[0]).exists():errors.append('broken link '+str(md.relative_to(root))+' -> '+target)
    for js in folder.rglob('*.json'):
        try:json.loads(js.read_text())
        except ValueError:errors.append('invalid JSON '+str(js))
    for md in [p,*folder.rglob('references/*.md'),*folder.rglob('assets/*.md')]:
        if re.search(r'\bTODO\b|\[TODO',md.read_text()):errors.append('unfinished scaffold '+str(md.relative_to(root)))
    # The shared contract is copied so each skill installs alone; copies must not drift.
    if '\n## 공통 계약\n' in text:contracts[name]=text.split('\n## 공통 계약\n',1)[1].strip()
if len(set(contracts.values()))>1:errors.append('common contract drift: '+', '.join(sorted(contracts)))
# Field names must agree between code, the data contract and the domain skills' docs.
manager=root/'skills'/'notion-canon-manager'
contract_path=manager/'references'/'data-contract.md'
if contract_path.exists():
    sys.path.insert(0,str(manager/'scripts'))
    import canon
    contract=contract_path.read_text()
    fields=set(canon.TIME_KEYS)|{k for v in canon.TEXT.values() for k in v}|{k for v in canon.OPTIONAL_TEXT.values() for k in v}|{k for v in canon.REFS.values() for k in v}|{k for v in canon.DATA_ENUMS.values() for k in v}
    for (kind,key),spec in canon.ITEMS.items():fields|={key,*(spec or {})}
    for field in sorted(fields):
        if not re.search(r'(?<![A-Za-z0-9_])'+re.escape(field)+r'(?![A-Za-z0-9_])',contract):errors.append('data contract does not document field '+field)
    snake=re.compile(r'(?<![A-Za-z0-9_./-])([a-z][a-z0-9]*(?:_[a-z0-9]+)+)(?![A-Za-z0-9_(-])')
    not_fields={'deleted_marker','needs_review'}  # an example data value and an impact output key
    for md in (root/'skills').rglob('*.md'):
        if manager in md.parents:continue
        for token in sorted(set(snake.findall(md.read_text()))-not_fields):
            if not re.search(r'(?<![A-Za-z0-9_])'+token+r'(?![A-Za-z0-9_])',contract):errors.append(f'{md.relative_to(root)} names field {token} missing from data contract')
print('\n'.join(errors) if errors else f"Validated {len(manifest['skills'])} skills and local resources")
sys.exit(bool(errors))
