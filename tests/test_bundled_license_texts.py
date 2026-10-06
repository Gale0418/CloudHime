"""Authenticate the vendored copies, including platform checkout behavior."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_upstream_license_copies_match_recorded_bytes_and_digests():
    folder = ROOT / 'packaging/third-party-licenses'
    receipt = json.loads((folder / 'sources.json').read_text(encoding='utf-8'))
    assert {
        'qt-6.10.1/LGPL-3.0-only.txt', 'qt-6.10.1/GPL-3.0-only.txt',
        'llama-1d1d9a9ed/LICENSE',
        'primp-1.3.1/LICENSE', 'pywinrt-3.2.1/LICENSE',
    } <= {entry['path'] for entry in receipt['files']}
    for entry in receipt['files']:
        assert entry['url'].startswith((
            'https://raw.githubusercontent.com/', 'https://download.qt.io/official_releases/',
            'https://developer.download.nvidia.com/compute/cuda/redist/',
            'https://doc.qt.io/qt-6.10/',
            'https://static.crates.io/crates/',
            'https://github.com/deedy5/primp/archive/refs/tags/',
        ))
        content = (folder / entry['path']).read_bytes()
        assert len(content) == entry['bytes']
        assert hashlib.sha256(content).hexdigest() == entry['sha256']
    assert b'The ggml authors' in (folder / 'llama-1d1d9a9ed/LICENSE').read_bytes()


def test_license_resources_are_bundled_without_newline_conversion():
    assert "('packaging/third-party-licenses', 'third-party-licenses')" in (ROOT / 'CloudHime.spec').read_text(encoding='utf-8')
    attributes = (ROOT / '.gitattributes').read_text(encoding='utf-8')
    assert '/packaging/third-party-licenses/**/*.txt -text' in attributes
    assert '/packaging/third-party-licenses/**/LICENSE* -text' in attributes
