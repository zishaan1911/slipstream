"""Export the SX-01 airframe from slipstream.html to blender/sx01.glb (named parts, PBR materials, label textures)."""
import base64, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import serve, open_page, ROOT, PORT
from playwright.sync_api import sync_playwright

EXPORTER = 'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/exporters/GLTFExporter.js'
JS = """() => new Promise((res, rej) => {
  const root = __REC.exportPrep();
  new THREE.GLTFExporter().parse(root, buf => {
    const b = new Uint8Array(buf); let s = '';
    for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000));
    res(btoa(s));
  }, { binary: true, onlyVisible: true, embedImages: true, maxTextureSize: 2048 });
})"""

def main():
    srv = serve()
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel='msedge', headless=True, args=['--ignore-gpu-blocklist', '--use-angle=d3d11'])
        page = open_page(br, 800, 600)
        page.add_script_tag(url=EXPORTER)
        data = base64.b64decode(page.evaluate(JS))
        out = os.path.join(ROOT, 'blender', 'sx01.glb')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'wb').write(data)
        print('wrote', out, len(data) >> 10, 'KB')
        br.close()
    srv.shutdown()

if __name__ == '__main__':
    main()
