"""Swap detailed third-party parts (Sketchfab, CC BY 4.0; see CREDITS.md) into the studio scene.

    blender -b blender/slipstream_studio.blend --python blender/add_parts.py

Reads blender/assets/{motor,servo,lipo,prop,cm4}.glb, fits each to the size and place of the simple part
it replaces (found by its dimensions), hides the simple part, and saves the .blend in place.
Re-running is safe: earlier imports are removed first.
"""
import bpy, os, math
import numpy as np
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, 'assets')
sc = bpy.context.scene
body = bpy.data.objects['Body']
B_inv = body.matrix_world.inverted()

# ---------------------------------------------------------------- helpers
def coll(name):
    c = bpy.data.collections.get(name)
    if c:
        for o in list(c.objects): bpy.data.objects.remove(o, do_unlink=True)
    else:
        c = bpy.data.collections.new(name); sc.collection.children.link(c)
    return c

def body_bbox(o):
    """bounding box of a mesh in Body-local coordinates"""
    ps = [B_inv @ (o.matrix_world @ Vector(c)) for c in o.bound_box]
    lo = Vector([min(p[i] for p in ps) for i in range(3)]); hi = Vector([max(p[i] for p in ps) for i in range(3)])
    return lo, hi

def find(prefix, dims, tol=0.0012, sort=False):
    out = []
    for o in bpy.data.objects:
        if o.type != 'MESH' or not o.name.startswith(prefix): continue
        lo, hi = body_bbox(o); d = hi - lo
        a, b = (sorted(d), sorted(dims)) if sort else (d, dims)
        if all(abs(x - y) < tol for x, y in zip(a, b)): out.append((o, lo, hi))
    return out

def hide(objs):
    for o in objs: o.hide_render = True; o.hide_viewport = True

def import_part(name, keep=lambda o: True):
    """import a glb, drop unwanted meshes, join the rest into one object with transforms applied"""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(A, name + '.glb'))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH' and keep(o)]
    for o in new:
        if o not in meshes: bpy.data.objects.remove(o, do_unlink=True)
    for o in meshes:  # bake parent transforms into each mesh, then join
        mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes: o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1: bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    obj.name = 'SF_' + name
    return obj

def verts(obj):
    v = np.empty(len(obj.data.vertices) * 3); obj.data.vertices.foreach_get('co', v); return v.reshape(-1, 3)

def place(src, c, parent, loc, rot_z=0.0, mirror=False, name=None):
    o = src.copy(); o.name = name or src.name  # linked duplicate: shares mesh data
    c.objects.link(o); o.parent = parent; o.matrix_parent_inverse = Matrix.Identity(4)
    o.location = loc; o.rotation_euler = (0, 0, rot_z); o.scale = (-1 if mirror else 1, 1, 1)
    return o

C = coll('Detailed parts (Sketchfab, CC BY)')
LIB = coll('Detailed parts - source meshes'); LIB.hide_render = True; LIB.hide_viewport = True

def to_lib(o):
    for u in list(o.users_collection): u.objects.unlink(o)
    LIB.objects.link(o)

# ---------------------------------------------------------------- motors (open-stator outrunner, Z up, bell dia 160 units)
LEADS = ('polySurface10', 'polySurface11', 'polySurface12', 'polySurface26', 'polySurface27', 'BezierCurve')
motor = import_part('motor', keep=lambda o: not o.name.startswith(LEADS))
s = 0.0352 / 0.160
motor.data.transform(Matrix.Scale(s, 4)); to_lib(motor)
# ---------------------------------------------------------------- propeller: align the disc normal with Z, 7" span
prop = import_part('prop')
V = verts(prop); ctr = V.mean(0); w, vec = np.linalg.eigh(np.cov((V - ctr).T)); ax = Vector(vec[:, 0]).normalized()
if ax.z < 0: ax = -ax
R = ax.rotation_difference(Vector((0, 0, 1))).to_matrix().to_4x4()
prop.data.transform(Matrix.Translation(-Vector(ctr))); prop.data.transform(R)
V = verts(prop); r = np.sqrt(V[:, 0] ** 2 + V[:, 1] ** 2).max()
hub_z = np.median(V[np.sqrt(V[:, 0] ** 2 + V[:, 1] ** 2) < r * 0.08][:, 2]) if (np.sqrt(V[:, 0] ** 2 + V[:, 1] ** 2) < r * 0.08).any() else 0
prop.data.transform(Matrix.Translation((0, 0, -hub_z))); prop.data.transform(Matrix.Scale(0.093 / r, 4)); to_lib(prop)

for i in range(4):
    mg, pg = bpy.data.objects['Motor_%d' % i], bpy.data.objects['Prop_%d' % i]
    hide([o for o in bpy.data.objects if o.type == 'MESH' and (o.name.startswith('Motor_%d_' % i) and '_tpu' not in o.name or o.name.startswith('Prop_%d_' % i))])
    place(motor, C, mg, (0, 0, 0), name='Motor_%d_detailed' % i)
    place(prop, C, pg, (0, 0, 0.002), rot_z=i * 0.7, mirror=i in (1, 2), name='Prop_%d_detailed' % i)

# ---------------------------------------------------------------- fold servos (SG90, mm units, Z up, long axis X)
servo = import_part('servo')
servo.data.transform(Matrix.Scale(0.001, 4)); servo.data.transform(Matrix.Rotation(math.pi / 2, 4, 'Z'))
blk = bpy.data.materials.new('servo_plastic'); blk.use_nodes = True
b = blk.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = (0.012, 0.012, 0.014, 1); b.inputs['Roughness'].default_value = 0.42
servo.data.materials.clear(); servo.data.materials.append(blk); to_lib(servo)
boxes = find('Body_plastic', (0.0125, 0.0235, 0.022))
for k, (o, lo, hi) in enumerate(boxes):
    place(servo, C, body, ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z), name='Servo_%d_detailed' % k)
hide([o for o, _, _ in boxes]); hide([o for o, _, _ in find('Body_plastic', (0.0125, 0.033, 0.002))])
hide([o for o, _, _ in find('Body_label', (0.0, 0.0115, 0.02), sort=True)])

# ---------------------------------------------------------------- LiPo (stands on end in the source; lay it flat, leads to the rear)
lipo = import_part('lipo', keep=lambda o: not any(k in o.name.lower() for k in ('floor', 'xt60', 'xst')))  # airframe has its own leads
V = verts(lipo)
core = V[(np.abs(V[:, 0]) < 1.05) & (np.abs(V[:, 1]) < 1.05) & (np.abs(V[:, 2]) < 2.2)]
lo, hi = core.min(0), core.max(0); c0 = (lo + hi) / 2; d0 = hi - lo
lipo.data.transform(Matrix.Translation(-Vector(c0)))
lipo.data.transform(Matrix.Rotation(math.pi / 2, 4, 'X'))                 # long axis Z -> -Y (top/leads to the rear)
lipo.data.transform(Matrix.Diagonal((0.036 / d0[0], 0.076 / d0[2], 0.03 / d0[1], 1)))
to_lib(lipo)
for o, lo, hi in find('Body_mat_', (0.036, 0.076, 0.03)):
    place(lipo, C, body, tuple((lo + hi) / 2), name='LiPo_detailed'); hide([o])
hide([o for o, _, _ in find('Body_label', (0.0, 0.034, 0.074), sort=True)])

# ---------------------------------------------------------------- companion computer: CM4 on the carrier, replaces module + heatsink + fan
cm4 = import_part('cm4', keep=lambda o: all(abs(v) < 0.031 for v in [(o.matrix_world @ Vector(c)).x for c in o.bound_box]) and
                  all(abs(v) < 0.023 for v in [(o.matrix_world @ Vector(c)).z for c in o.bound_box]))
cm4.data.transform(Matrix.Rotation(math.pi / 2, 4, 'X'))                  # board normal Y -> Z, SoC side up
V = verts(cm4); lo, hi = V.min(0), V.max(0)
cm4.data.transform(Matrix.Translation((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])))
to_lib(cm4)
mod = find('Body_pcb', (0.046, 0.034, 0.003))
carrier = find('Body_pcbG', (0.062, 0.044, 0.0016))
if mod and carrier:
    (o, lo, hi), (_, clo, chi) = mod[0], carrier[0]
    place(cm4, C, body, ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, chi.z + 0.0004), name='CM4_detailed')
    hide([o]); hide([x for x, _, _ in find('Body_blackAl', (0.044, 0.032, 0.003))]); hide([x for x, _, _ in find('Body_blackAl', (0.0011, 0.032, 0.007))])
    hide([x for x, _, _ in find('Body_plastic', (0.0278, 0.0278, 0.0028), tol=0.002)])
    hide([o for o in bpy.data.objects if o.name.startswith('Fan_')])

print('parts:', sorted(o.name for o in C.objects))
bpy.ops.file.pack_all()
bpy.ops.wm.save_mainfile(compress=True)
print('saved', bpy.data.filepath)
