"""Render the machined-unibody concept sheet -> concepts/unibody_sheet.jpg"""
import base64, io, os, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
from render import serve, PORT
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
SS = 2
SHOTS = [  # (key, view, finish, fold, w, h, label)
    ('open', 'hero', 'grey', 45, 1040, 740, 'Space grey, arms open'),
    ('fold', 'hero', 'grey', 9, 520, 370, 'Arms folded'),
    ('hinge', 'hinge', 'grey', 45, 520, 370, 'Concealed hinge'),
    ('silver', 'low', 'silver', 45, 520, 370, 'Bead-blasted silver'),
    ('white', 'low', 'white', 45, 520, 370, 'Ceramic white'),
    ('top', 'top', 'grey', 45, 520, 370, 'Top'),
]


def main():
    srv = serve(); tiles = {}
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel='msedge', headless=True, args=['--ignore-gpu-blocklist', '--use-angle=d3d11'])
        pg = br.new_page(viewport={'width': 800, 'height': 600})
        pg.goto(f'http://127.0.0.1:{PORT}/concepts/concepts.html'); pg.wait_for_function('window.ready', timeout=120000)
        for key, view, fin, fold, w, h, _ in SHOTS:
            url = pg.evaluate(f'render("unibody", "{view}", {w * SS}, {h * SS}, "{fin}", {fold})')
            tiles[key] = Image.open(io.BytesIO(base64.b64decode(url.split(',', 1)[1]))).convert('RGB').resize((w, h), Image.LANCZOS)
        br.close()
    srv.shutdown()
    sheet = Image.new('RGB', (10 + 1040 + 10 + 520 + 10, 10 + 740 + 10 + 370 + 10), (11, 12, 14))
    d = ImageDraw.Draw(sheet)
    try: font = ImageFont.truetype('arialbd.ttf', 22); big = ImageFont.truetype('arialbd.ttf', 30)
    except Exception: font = big = ImageFont.load_default()
    place = {'open': (10, 10), 'fold': (1060, 10), 'hinge': (1060, 390), 'silver': (10, 760), 'white': (540, 760), 'top': (1060, 760)}
    for key, *_, label in SHOTS:
        x, y = place[key]; sheet.paste(tiles[key], (x, y))
        d.text((x + 18, y + 14), label, fill=(242, 106, 27), font=big if key == 'open' else font)
    out = os.path.join(HERE, 'unibody_sheet.jpg'); sheet.save(out, quality=90); print('wrote', out)


if __name__ == '__main__':
    main()
