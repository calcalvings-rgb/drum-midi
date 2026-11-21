"""Build the public source offer from an explicit release manifest, never a directory dump."""
from __future__ import annotations
import io
import json
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name('source_manifest.json')
TOP_LEVEL = {'LICENSE', 'README.md', 'README.id.md', 'THIRD_PARTY_NOTICES.md', 'drum_midi.py', 'requirements-web.txt', 'requirements-gui.txt', '.gitignore'}
SOURCE_SUFFIXES = {'.py', '.js', '.mjs', '.cjs', '.css', '.html', '.json', '.md', '.txt', '.toml', '.yaml', '.yml'}


def is_source_path(name):
    if not isinstance(name, str) or not name or '\\' in name:
        return False
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '.' in path.parts:
        return False
    if name in TOP_LEVEL:
        return True
    if path.parts[:2] == ('docs', 'images') and path.suffix == '.png':
        return True
    if len(path.parts) < 2 or path.parts[0] not in {'src', 'tests', 'docs', 'tools'}:
        return False
    if any(part.startswith('.') or part in {'superpowers', '__pycache__'} for part in path.parts):
        return False
    return path.suffix in SOURCE_SUFFIXES or path.name == 'LICENSE'


def build_source_archive(root=None, manifest=None):
    root = Path(root or ROOT).resolve()
    metadata = json.loads(Path(manifest or MANIFEST).read_text(encoding='utf-8'))
    files = metadata.get('files') if isinstance(metadata, dict) else None
    if not isinstance(files, list) or not files or len(files) > 5000 or any(not isinstance(name, str) for name in files):
        raise ValueError('Invalid source manifest')
    output = io.BytesIO()
    total = 0
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in dict.fromkeys(files):
            if not is_source_path(name):
                raise ValueError('Source manifest contains a forbidden path')
            source = root / name
            cursor = source
            while cursor != root:
                if cursor.is_symlink():
                    raise ValueError('Symlinks are not included in the source offer')
                cursor = cursor.parent
            if not source.resolve().is_relative_to(root) or not source.is_file():
                raise ValueError('A manifested source file is unavailable')
            total += source.stat().st_size
            if total > 50 * 1024 * 1024:
                raise ValueError('Source bundle exceeds its size limit')
            archive.writestr('grooveforge-source/' + name, source.read_bytes())
    return output.getvalue()
