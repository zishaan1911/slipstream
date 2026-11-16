"""Swap a freshly exported airframe into an existing studio scene, keeping everything else (lights, cameras, edits).

    python tools/export_glb.py
    blender -b blender/slipstream_studio.blend --python blender/update_airframe.py

Removes the old airframe, depth camera and detailed-part objects, imports blender/sx01.glb at the old airframe's
place, re-fits the Sketchfab parts (add_parts.py) and saves the .blend in place.
"""
import bpy, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import airframe

old = bpy.data.objects.get('SX-01')
matrix = old.matrix_world.copy() if old else None
for name in ('SX-01 airframe', 'Depth camera (under shell)', 'Detailed parts (Sketchfab, CC BY)', 'Detailed parts - source meshes'):
    c = bpy.data.collections.get(name)
    if c:
        for o in list(c.objects): bpy.data.objects.remove(o, do_unlink=True)
for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images):  # drop what the old airframe left behind
    for d in list(block):
        if d.users == 0: block.remove(d)

airframe.import_airframe(os.path.join(HERE, 'sx01.glb'), 1.0, matrix)
bpy.context.view_layer.update()  # add_parts measures parts in the body's frame: matrices must be current
import add_parts  # noqa: E402  (fits the detailed parts on import)

bpy.ops.file.pack_all()
bpy.ops.wm.save_mainfile(compress=True)
print('updated', bpy.data.filepath)
