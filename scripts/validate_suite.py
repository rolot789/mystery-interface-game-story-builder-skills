#!/usr/bin/env python3
"""Check portable suite packaging and local resource links (stdlib only)."""
from pathlib import Path
import json
import re
import sys
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'suite.json').read_text())
errors=[]
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
    if re.search(r'\bTODO\b|\[TODO',text):errors.append('unfinished scaffold '+name)
print('\n'.join(errors) if errors else f"Validated {len(manifest['skills'])} skills and local resources")
sys.exit(bool(errors))
