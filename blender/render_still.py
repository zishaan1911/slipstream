"""Render one still from the studio scene without changing the .blend.

    blender -b blender/slipstream_studio.blend --python blender/render_still.py -- CAMERA OUT.png [--pct 50] [--samples 64] [--xray]

--xray hides the shell and its decals and shows the depth camera, for shots of the electronics.
"""
import bpy, sys, time
a = sys.argv[sys.argv.index('--') + 1:]
cam, out = a[0], a[1]
opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d
sc = bpy.context.scene
sc.camera = bpy.data.objects[cam]
sc.render.resolution_percentage = opt('--pct', 100)
sc.cycles.samples = opt('--samples', sc.cycles.samples)
if '--xray' in a:
    for o in bpy.data.objects:
        if o.name.startswith('Shell'): o.hide_render = True
    for o in bpy.data.collections['Depth camera (under shell)'].objects: o.hide_render = False
sc.render.filepath = out
t = time.time(); bpy.ops.render.render(write_still=True); print('render s', round(time.time() - t, 1))
