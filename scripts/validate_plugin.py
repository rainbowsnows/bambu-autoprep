"""Validate portable schemas plus catalog/path/skill semantics; no network access."""
from pathlib import Path
import json
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/bambu-autoprep'

def validate():
    for manifest, schema in [('plugin.json','plugin.schema.json'),('mcp.json','mcp.schema.json')]:
        data=json.loads((PLUGIN/manifest).read_text())
        Draft202012Validator(json.loads((ROOT/'schemas'/schema).read_text())).validate(data)
    catalog=json.loads((ROOT/'.agents/plugins/marketplace.json').read_text())
    assert catalog['interface']['displayName']=='3D Print'
    assert len(catalog['plugins'])==1
    entry=catalog['plugins'][0]
    assert entry['name']=='bambu-autoprep'
    assert entry['policy']=={'installation':'AVAILABLE','authentication':'ON_INSTALL'}
    assert entry['source']['source']=='local'
    source=entry['source']['path']
    assert source.startswith('./') and (ROOT/source).resolve().is_relative_to(ROOT)
    assert (ROOT/source/'plugin.json').is_file()
    manifest=json.loads((PLUGIN/'plugin.json').read_text())
    assert manifest['extensions']['com.openai']['interface']['displayName']=='3D Print'
    skill=(PLUGIN/'skills/bambu-autoprep/SKILL.md').read_text()
    front=yaml.safe_load(skill.split('---',2)[1])
    assert front['name']=='3d-print' and front['description']
    server=json.loads((PLUGIN/'mcp.json').read_text())['mcpServers']['bambu-autoprep']
    assert server['type']=='stdio' and server['args']==['${PLUGIN_ROOT}/mcp/server.py']
    assert (PLUGIN/'mcp/server.py').is_file()
    print('PASS: portable manifest, MCP schema, catalog, contained paths and skill metadata')

if __name__=='__main__': validate()
