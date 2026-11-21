"""Regenerate the source offer after staging new distributable source files."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from drum_midi.source_offer import is_source_path


def main():
    result = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z'], capture_output=True, check=True)
    names = result.stdout.decode('utf-8').split('\0')
    target = ROOT / 'src/drum_midi/source_manifest.json'
    files = sorted({name for name in names if is_source_path(name)} | {'src/drum_midi/source_manifest.json'})
    target.write_text(json.dumps({'files': files}, indent=2) + '\n', encoding='utf-8')
    print(f'Source manifest: {len(files)} explicitly listed files')


if __name__ == '__main__':
    main()
