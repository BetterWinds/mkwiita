#!/usr/bin/env python3
"""Generates the headers tools/build.py made for the 3DS, for the Vita CMake build.

    python tools/vita/gen_headers.py <output dir>

content_version.hpp: the content stamp (the same fingerprint the asset
builder writes to content.txt), version and What's New text.
shader_data.hpp: empty. The Vita build has no PICA shader binary; the
citro3d layer (platform/vita/src/c3d_*.cpp) supplies GLSL ports instead.
"""
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tools/release')]
from build_cia import content_fingerprint


def write_if_changed(path, text):
    if not path.is_file() or path.read_text() != text:
        path.write_text(text)


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    news = [l.rstrip() for l in (ROOT / 'tools/release/WHATS_NEW.txt').read_text(encoding='utf-8').splitlines() if l.strip()]
    if any(not l.isascii() or '"' in l or '\\' in l for l in news):
        raise SystemExit('WHATS_NEW.txt: ASCII lines only, no quotes or backslashes')
    stamp = '#pragma once\n// Converted game files this code expects (tools/release/build_cia.py).\n'
    stamp += '#define MKW_CONTENT "' + content_fingerprint() + '"\n'
    stamp += '#define MKW_VERSION "' + (ROOT / 'tools/release/VERSION').read_text().strip() + '"\n'
    stamp += '#define MKW_WHATS_NEW "' + '\\n'.join(news) + '"\n'
    stamp += '#define MKW_QUICK_UPDATE 0\n'
    write_if_changed(out / 'content_version.hpp', stamp)
    write_if_changed(out / 'shader_data.hpp', '#pragma once\n#include <cstdint>\n'
                     '// No PICA binary on the Vita: platform/vita/src/c3d_shader.cpp holds the GLSL ports.\n'
                     'alignas(4) static const uint8_t mkw_shader[4]={0,0,0,0};\n')


if __name__ == '__main__':
    main()
