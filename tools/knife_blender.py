"""Render the knife-edge through gate C in Blender (Eevee) with the manoeuvre infographic on top.

    python tools/knife_blender.py                 # -> renders/videos/knife_blender.mp4
    python tools/knife_blender.py --frames 1:60   # a slice, for a quick look (frames are kept)
    python tools/knife_blender.py --skip-export --list 1,120,240   # test frames from the last export

1. the sim (headless Edge) flies the run and exports it with eased slow motion: the airframe's pose, every moving
   part, prop angles that follow the signed rotor speed, and a smooth camera dolly -> blender/knife_anim.json;
   the infographic for each frame -> renders/frames/knife_overlay/
2. Blender keys it all on the studio scene, builds the gate wall and renders -> renders/frames/knife_bl/
3. each frame gets its infographic and ffmpeg encodes the video
Needs blender/sx01.glb swapped into the scene first (tools/export_glb.py, then blender/update_airframe.py).
"""
import base64, json, os, shutil, subprocess, sys, time
from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render  # noqa: E402  (shared page server + browser setup)

ROOT = render.ROOT
BLENDER = os.environ.get('BLENDER', r'C:\Users\Zishaan\blender\blender-2.93.18-windows-x64\blender.exe')
ANIM = os.path.join(ROOT, 'blender', 'knife_anim.json')
OVL = os.path.join(ROOT, 'renders', 'frames', 'knife_overlay')
BL = os.path.join(ROOT, 'renders', 'frames', 'knife_bl')
COMP = os.path.join(ROOT, 'renders', 'frames', 'knife_comp')
OUT = os.path.join(ROOT, 'renders', 'videos', 'knife_blender.mp4')
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d


def export():
    srv = render.serve()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True,
                                     args=['--ignore-gpu-blocklist', '--enable-gpu', '--use-angle=d3d11', '--enable-unsafe-swiftshader'])
        page = render.open_page(browser, 1080, 1920)
        anim = page.evaluate('__REC.knifeAnim(30)')
        json.dump(anim, open(ANIM, 'w'))
        print('animation:', anim['n'], 'frames,', len(anim['local']), 'moving parts, marks', anim['marks'], flush=True)
        shutil.rmtree(OVL, ignore_errors=True); os.makedirs(OVL)
        for i in range(anim['n']):
            url = page.evaluate(f'__REC.knifeOverlay({i})')
            open(os.path.join(OVL, f'o_{i + 1:04d}.png'), 'wb').write(base64.b64decode(url.split(',', 1)[1]))
        browser.close()
    srv.shutdown()
    return anim


def main():
    anim = json.load(open(ANIM)) if '--skip-export' in sys.argv else export()
    frames = arg('--frames', f"1:{anim['n']}")
    if '--skip-render' not in sys.argv:
        if not arg('--frames') and not arg('--list'): shutil.rmtree(BL, ignore_errors=True)
        t = time.time()
        subprocess.run([BLENDER, '-b', os.path.join(ROOT, 'blender', 'slipstream_studio.blend'), '--python',
                        os.path.join(ROOT, 'blender', 'render_knife.py'), '--', ANIM, BL, '--frames', frames,
                        '--pct', arg('--pct', '100'), '--samples', arg('--samples', '48'), '--key', arg('--key', '900'),
                        '--cam-k', arg('--cam-k', '0.7')] + (['--list', arg('--list')] if arg('--list') else []), check=True)
        print('blender', round(time.time() - t), 's', flush=True)
    shutil.rmtree(COMP, ignore_errors=True); os.makedirs(COMP)
    fa, fb = (int(v) for v in frames.split(':'))
    todo = [int(v) for v in arg('--list').split(',')] if arg('--list') else range(fa, fb + 1)
    for k, f in enumerate(todo):
        ov = Image.open(os.path.join(OVL, f'o_{f:04d}.png')).convert('RGBA')   # infographic at full size, crisp
        im = Image.open(os.path.join(BL, f'f_{f:04d}.jpg')).convert('RGBA').resize(ov.size, Image.LANCZOS)
        Image.alpha_composite(im, ov).convert('RGB').save(os.path.join(COMP, f'c_{k:04d}.jpg'), quality=95)
    if arg('--list'): print('test frames ->', COMP); return
    out = OUT if not arg('--frames') else OUT.replace('.mp4', '_part.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(anim['fps']), '-i', os.path.join(COMP, 'c_%04d.jpg'),
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], check=True)
    print('->', out)


if __name__ == '__main__':
    main()
