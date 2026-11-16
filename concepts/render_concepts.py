"""Render the chassis concept sheet: python concepts/render_concepts.py [blade spine facet] -> concepts/concepts_sheet.jpg"""
import base64, io, os, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
from render import serve, PORT
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
CONCEPTS = [('blade', 'A  Blade'), ('spine', 'B  Spine'), ('facet', 'C  Facet')]
SIZES = {'hero': (1000, 750), 'side': (560, 370), 'top': (560, 370)}
SS = 2  # supersample


def main():
    only = sys.argv[1:]
    rows = [c for c in CONCEPTS if not only or c[0] in only]
    srv = serve(); tiles = {}
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel='msedge', headless=True, args=['--ignore-gpu-blocklist', '--use-angle=d3d11'])
        pg = br.new_page(viewport={'width': 800, 'height': 600})
        pg.goto(f'http://127.0.0.1:{PORT}/concepts/concepts.html'); pg.wait_for_function('window.ready', timeout=120000)
        for key, _ in rows:
            for v, (w, h) in SIZES.items():
                url = pg.evaluate(f'render("{key}", "{v}", {w * SS}, {h * SS})')
                tiles[(key, v)] = Image.open(io.BytesIO(base64.b64decode(url.split(',', 1)[1]))).convert('RGB').resize((w, h), Image.LANCZOS)
        br.close()
    srv.shutdown()
    W, RH = 1000 + 560 + 30, 760
    sheet = Image.new('RGB', (W, RH * len(rows) + 10), (11, 12, 14))
    d = ImageDraw.Draw(sheet)
    try: font = ImageFont.truetype('arialbd.ttf', 30)
    except Exception: font = ImageFont.load_default()
    for r, (key, label) in enumerate(rows):
        y = 10 + r * RH
        sheet.paste(tiles[(key, 'hero')], (10, y)); sheet.paste(tiles[(key, 'side')], (1020, y)); sheet.paste(tiles[(key, 'top')], (1020, y + 380))
        d.text((30, y + 20), label, fill=(242, 106, 27), font=font)
    out = os.path.join(HERE, 'concepts_sheet.jpg'); sheet.save(out, quality=90); print('wrote', out)


if __name__ == '__main__':
    main()
