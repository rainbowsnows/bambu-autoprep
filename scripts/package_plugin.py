"""Package a single plugin for account upload, or optionally for local stdio."""
from pathlib import Path
import argparse
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/bambu-autoprep'


def package(destination=None, local_mcp=False):
    manifest = json.loads((PLUGIN / 'plugin.json').read_text())
    name, version = manifest['name'], manifest['version']
    assert len(manifest['extensions']['com.openai']['interface']['shortDescription']) <= 30
    destination = Path(destination or ROOT / f"3D-Print-{version}{'-local' if local_mcp else ''}.zip")
    # Explicit allowlist excludes personal config, caches and environments.
    files = [PLUGIN / 'plugin.json', ROOT / 'LICENSE']
    files += sorted((PLUGIN / 'skills').rglob('*.md'))
    files += sorted((PLUGIN / 'mcp').glob('*.py'))
    files += [PLUGIN / 'mcp/requirements.txt']
    if local_mcp:
        files += [PLUGIN / 'mcp.json', PLUGIN / 'mcp/config.example.json']
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            assert path.is_file() and not path.is_symlink()
            relative = Path('LICENSE') if path == ROOT / 'LICENSE' else path.relative_to(PLUGIN)
            archive.write(path, str(Path(name) / relative))
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert all(n.startswith(name + '/') for n in names)
        assert (name + '/mcp.json' in names) == local_mcp
        assert name + '/skills/3d-print/SKILL.md' in names
        assert not any(n.endswith('config.json') for n in names)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--local-mcp', action='store_true')
    parser.add_argument('--output')
    args = parser.parse_args()
    print(package(args.output, args.local_mcp))
