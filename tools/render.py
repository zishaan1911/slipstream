"""Render SlipStream shots to video and stills with headless Edge.

    python tools/render.py videos            # all video shots -> renders/videos/*.mp4
    python tools/render.py videos hero fold  # selected shots
    python tools/render.py stills            # renders/stills/*.png (4:5, supersampled)
    python tools/render.py test hero 40      # one still for a quick look -> renders/test.jpg

The page exposes window.__REC: setup(w, h), begin(shot) -> frame count, frame(i) -> JPEG data URL.
"""
import base64, functools, http.server, io, os, shutil, subprocess, sys, threading, time
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'renders')
PORT = 8765
VIDEO_SHOTS = ['hero', 'explode', 'xray', 'fold', 'knife', 'slot']
STILLS = [  # (file, shot, frame)
    ('01_hero', 'hero', 60), ('02_hero_side', 'hero', 170), ('03_exploded', 'explode', 150),
    ('04_electronics', 'xray', 270), ('05_folded', 'fold', 75), ('06_top', 'fold', 0),
]


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    h = functools.partial(Quiet, directory=ROOT)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def open_page(browser, w, h):
    page = browser.new_page(viewport={'width': w, 'height': h})
    page.goto(f'http://127.0.0.1:{PORT}/slipstream.html')
    page.wait_for_function('window.__REC && window.__REC.ready', timeout=120000)
    page.evaluate(f'__REC.setup({w}, {h})')
    return page


def grab(page, i):
    url = page.evaluate(f'__REC.frame({i})')
    return None if url is None else base64.b64decode(url.split(',', 1)[1])


def videos(browser, names):
    vdir = os.path.join(OUT, 'videos'); os.makedirs(vdir, exist_ok=True)
    for name in names:
        page = open_page(browser, 1080, 1920)
        n = page.evaluate(f'__REC.begin("{name}")')
        fdir = os.path.join(OUT, 'frames', name)
        shutil.rmtree(fdir, ignore_errors=True); os.makedirs(fdir)
        t0 = time.time(); knife_frames = []
        for i in range(n):
            data = grab(page, i)
            if data is None:  # the shot ended itself
                n = i; break
            with open(os.path.join(fdir, f'f_{i:04d}.jpg'), 'wb') as f:
                f.write(data)
            if name in ('knife', 'slot'):
                st = page.evaluate('__REC.state()')
                if st['knife'] or (abs(st['s']) < 0.25 and not st['replay']):
                    knife_frames.append(i)
            if i % 30 == 0:
                print(f'  {name} {i}/{n}  {(time.time() - t0) / (i + 1):.2f} s/frame', flush=True)
        page.evaluate('__REC.end()'); page.close()
        out = os.path.join(vdir, f'{name}.mp4')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '30', '-i', os.path.join(fdir, 'f_%04d.jpg'),
                        '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], check=True)
        print(f'{name}: {n} frames -> {out}', flush=True)
        if knife_frames:  # keep the frame closest to mid-gate as a 4:5 still
            mid = knife_frames[len(knife_frames) // 2]
            im = Image.open(os.path.join(fdir, f'f_{mid:04d}.jpg'))
            top = (1920 - 1350) // 2
            sdir = os.path.join(OUT, 'stills'); os.makedirs(sdir, exist_ok=True)
            im.crop((0, top, 1080, top + 1350)).save(os.path.join(sdir, f'07_{name}_gate.png'))
        if '--keep-frames' not in sys.argv:
            shutil.rmtree(fdir, ignore_errors=True)  # frames are large; the mp4 is the deliverable


def stills(browser):
    sdir = os.path.join(OUT, 'stills'); os.makedirs(sdir, exist_ok=True)
    page = open_page(browser, 2160, 2700)
    for fname, shot, i in STILLS:
        page.evaluate(f'__REC.begin("{shot}")')
        im = Image.open(io.BytesIO(grab(page, i))).convert('RGB').resize((1080, 1350), Image.LANCZOS)
        im.save(os.path.join(sdir, fname + '.png'))
        page.evaluate('__REC.end()')
        print('still', fname, flush=True)
    page.close()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'videos'
    srv = serve()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True,
                                     args=['--ignore-gpu-blocklist', '--enable-gpu', '--use-angle=d3d11', '--enable-unsafe-swiftshader'])
        if mode == 'videos':
            videos(browser, [a for a in sys.argv[2:] if not a.startswith('--')] or VIDEO_SHOTS)
        elif mode == 'stills':
            stills(browser)
        elif mode == 'test':
            shot, i = sys.argv[2], int(sys.argv[3])
            w, h = (1080, 1350) if len(sys.argv) < 5 else map(int, sys.argv[4].split('x'))
            page = open_page(browser, w, h)
            page.evaluate(f'__REC.begin("{shot}")')
            for k in range(i if shot in ('knife', 'slot') else 0):
                page.evaluate(f'__REC.frame({k})')
            t = time.time(); data = grab(page, i)
            os.makedirs(OUT, exist_ok=True)
            open(os.path.join(OUT, 'test.jpg'), 'wb').write(data)
            print('test frame in', round(time.time() - t, 2), 's', page.evaluate('__REC.state()'))
        browser.close()
    srv.shutdown()


if __name__ == '__main__':
    main()
