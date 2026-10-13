#!/usr/bin/env python3
"""The Vita's bubble icon and LiveArea images, made from the player's disc.

    .venv/Scripts/python tools/vita/livearea_art.py

Reads this tree's unpacked menu archives (assets/menu-ui, from the disc's
Scene/UI, as tools/release/home_menu_art.py does for the 3DS HOME Menu) and
writes build/vita/sce_sys_art: icon0.png (128x128), livearea/contents/bg.png
(840x500), startup.png (280x158) and template.xml. CMakeLists.txt packs that
folder into the VPK when it exists, else the plain placeholders.
"""
import shutil, sys
from pathlib import Path
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tools/release'), str(ROOT / 'vendor/gclib')]
from home_menu_art import title_scene, decode_tpl, UI

OUT = ROOT / 'build/vita/sce_sys_art'


def indexed(image, path):
    # LiveArea images must be 8-bit indexed PNGs.
    image.convert('RGB').quantize(colors=255, method=Image.Quantize.MEDIANCUT).save(path, optimize=True)


def fit(image, size, background=(255, 255, 255, 255)):
    w, h = image.size
    scale = min(size[0] / w, size[1] / h)
    scaled = image.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    out = Image.new('RGBA', size, background)
    out.alpha_composite(scaled, ((size[0] - scaled.width) // 2, (size[1] - scaled.height) // 2))
    return out


def main():
    contents = OUT / 'livearea/contents'
    contents.mkdir(parents=True, exist_ok=True)
    scene = title_scene()  # 608x456: logo over Mario on his kart, on white
    # Icon: Mario on his kart alone (the title screen without its logo),
    # above the copyright line.
    mario = Image.new('RGBA', (832, 456), (255, 255, 255, 255))
    mario.alpha_composite(decode_tpl(UI / 'Title/title/timg/tt_title_screen_mario2.tpl'), (0, 140))
    mario = mario.crop((112, 0, 720, 456)).crop((286, 170, 596, 392))
    # The Wii logo's blue ring reaches into the top-left corner: paint it white.
    px = mario.load()
    for y in range(min(80, mario.height)):
        for x in range(min(100, mario.width)):
            r, g, b, a = px[x, y]
            # Keep Mario's red cap; everything else in the corner is the ring.
            if not (r > g + 60 and r > b + 60):
                px[x, y] = (255, 255, 255, 255)
    indexed(fit(mario, (128, 128)), OUT / 'icon0.png')
    # Background: the whole title screen; start button: its logo with "Wii".
    indexed(fit(scene, (840, 500)), contents / 'bg.png')
    indexed(fit(scene.crop((0, 8, 608, 156)), (280, 158)), contents / 'startup.png')
    shutil.copyfile(ROOT / 'platform/vita/sce_sys/livearea/contents/template.xml', contents / 'template.xml')
    print('LiveArea art:', OUT)


if __name__ == '__main__':
    main()
