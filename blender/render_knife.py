"""Render the knife-edge through gate C in Eevee, from the flight the sim exports (tools/knife_blender.py runs all of it).

    blender -b blender/slipstream_studio.blend --python blender/render_knife.py -- ANIM.json OUTDIR [--frames A:B | --list 1,90,200] [--pct 100] [--samples 48] [--key 900] [--cam-k 0.7]

ANIM.json comes from __REC.knifeAnim(): per frame the airframe's root pose, the local transform of every moving part
(arms, servo horns, pushrods, legs, leg rods, props), and the camera. The script builds the gate wall, keys everything,
renders JPEG frames to OUTDIR and leaves the .blend untouched.
"""
import bpy, json, math, os, sys
from mathutils import Matrix, Vector

a = sys.argv[sys.argv.index('--') + 1:]
anim = json.load(open(a[0])); OUT = a[1]
opt = lambda k, d: a[a.index(k) + 1] if k in a else d
CAM_K = float(opt('--cam-k', 0.7))
KEY = float(opt('--key', 900))
C = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # three.js (y up) -> Blender (z up)
CI = C.inverted()
sc = bpy.context.scene


def m3(el):   # three.js column-major elements -> Matrix
    return Matrix(((el[0], el[4], el[8], el[12]), (el[1], el[5], el[9], el[13]), (el[2], el[6], el[10], el[14]), (0, 0, 0, 1)))


def conv(el):
    return C @ m3(el) @ CI


def P(v):
    return Vector((v[0], -v[2], v[1]))


# ---------------------------------------------------------------- check the mapping on the exported rest pose
worst = 0.0
for name, el in anim['restLocal'].items():
    ob = bpy.data.objects.get(name)
    if ob is None: print('MISSING', name); continue
    d = max(abs(x - y) for r1, r2 in zip(ob.matrix_basis, conv(el)) for x, y in zip(r1, r2))
    worst = max(worst, d)
print('rest-pose mapping, worst element error', round(worst, 6))


# ---------------------------------------------------------------- keyframes (linear, written straight into F-curves)
def key(ob, mats):
    ob.rotation_mode = 'QUATERNION'
    ob.animation_data_clear()
    act = bpy.data.actions.new(ob.name + '_knife')
    ob.animation_data_create().action = act
    chans = {('location', i): [] for i in range(3)}
    chans.update({('rotation_quaternion', i): [] for i in range(4)}); chans.update({('scale', i): [] for i in range(3)})
    prev = None
    for f, M in enumerate(mats, start=1):
        l, r, s = M.decompose()
        if prev is not None and prev.dot(r) < 0: r.negate()   # keep the quaternion on one hemisphere
        prev = r
        for i in range(3): chans[('location', i)] += [f, l[i]]; chans[('scale', i)] += [f, s[i]]
        for i in range(4): chans[('rotation_quaternion', i)] += [f, r[i]]
    for (path, i), co in chans.items():
        fc = act.fcurves.new(path, index=i)
        fc.keyframe_points.add(len(co) // 2); fc.keyframe_points.foreach_set('co', co)
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
        fc.update()


n = anim['n']
key(bpy.data.objects['SX-01'], [conv(el) for el in anim['root']])
for name, els in anim['local'].items():
    ob = bpy.data.objects.get(name)
    if ob: key(ob, [conv(el) for el in els])

# wires that run onto the arms bend as they fold: shape keys at the sampled fold angles, blended per frame.
# Each Blender wire is found by its vertex count and first vertex (the open-arm geometry it was exported with).
angs, fold = anim['cableAngles'], anim['fold']
C3 = C.to_3x3()
wire_obs = [o for o in bpy.data.objects if o.type == 'MESH' and o.data.shape_keys is None]
matched = 0
for cb in anim['cables']:
    want = C3 @ Vector(cb['first'])
    hit = [o for o in wire_obs if len(o.data.vertices) == cb['n'] and (o.data.vertices[0].co - want).length < 2e-4]
    if not hit: print('wire not found', cb['n'], cb['first']); continue
    o = hit[0]; wire_obs.remove(o); matched += 1
    o.shape_key_add(name='Basis', from_mix=False)
    for k, flat in enumerate(cb['keys']):
        sk = o.shape_key_add(name='fold_%d' % k, from_mix=False)
        co = []
        for j in range(0, len(flat), 3): co += [flat[j], -flat[j + 2], flat[j + 1]]   # three.js -> Blender axes
        sk.data.foreach_set('co', co)
    keys = o.data.shape_keys; keys.use_relative = True
    act = bpy.data.actions.new(o.name + '_fold'); keys.animation_data_create().action = act
    step_a = angs[1] - angs[0]
    curves = [act.fcurves.new('key_blocks["fold_%d"].value' % k) for k in range(len(angs))]
    for fc in curves: fc.keyframe_points.add(n)
    vals = [[] for _ in angs]
    for f, aa in enumerate(fold, start=1):
        x = min(max((aa - angs[0]) / step_a, 0), len(angs) - 1)
        for k in range(len(angs)): vals[k] += [f, max(0.0, 1 - abs(x - k))]
    for fc, co in zip(curves, vals):
        fc.keyframe_points.foreach_set('co', co)
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
        fc.update()
print('fold-bent wires', matched, 'of', len(anim['cables']))

cam_data = bpy.data.cameras.new('Cam_knife'); cam = bpy.data.objects.new('Cam_knife', cam_data); sc.collection.objects.link(cam)
cam_data.sensor_fit = 'VERTICAL'; cam_data.sensor_height = 24; cam_data.lens = 12 / math.tan(math.radians(anim['fovV']) / 2)
cam_data.clip_start = 0.05; cam_data.clip_end = 100
# camera dolly beside the flight on the deck side (+x: Gannet rolls right, deck and livery face it), outside the wall's width so the wall never comes between;
# it follows a zero-lag smoothed copy of the airframe's path and aims half way between that and the airframe
pos = [conv(el).to_translation() for el in anim['root']]
sm = [p.copy() for p in pos]
for _ in range(2):
    for i in range(1, n): sm[i] = sm[i].lerp(sm[i - 1], CAM_K)
    for i in range(n - 2, -1, -1): sm[i] = sm[i].lerp(sm[i + 1], CAM_K)
ease = lambda u: u * u * (3 - 2 * u)
lerp = lambda x, y, u: x + (y - x) * u
mats = []
for i, c in enumerate(sm):
    u = i / (n - 1)
    p = Vector((anim["gate"]["gx"] + lerp(1.7, 2.0, u), c.y - lerp(0.45, 0.05, ease(u)), c.z + lerp(0.18, 0.36, u)))
    t = c.lerp(pos[i], 0.6)
    mats.append(Matrix.Translation(p) @ (t - p).to_track_quat('-Z', 'Y').to_matrix().to_4x4())
key(cam, mats)
sc.camera = cam


# ---------------------------------------------------------------- set: gate wall with the slot, floor, backdrop, lights
for cname in ('Studio', 'Pendant lamp'):
    c = bpy.data.collections.get(cname)
    if c: c.hide_render = True
for o in bpy.data.objects:
    if o.type == 'LIGHT': o.hide_render = True
setc = bpy.data.collections.new('Knife gate'); sc.collection.children.link(setc)


def mat(name, color, rough=0.6, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1); b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal; b.inputs['Clearcoat'].default_value = coat
    return m


def box(name, lo, hi, m):
    lo, hi = Vector(lo), Vector(hi)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(lo + hi) / 2)
    o = bpy.context.active_object; o.name = name; o.scale = hi - lo
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(m)
    for c in o.users_collection: c.objects.unlink(o)
    setc.objects.link(o); return o


g = anim['gate']
wy, t2 = -g['wallZ'], g['wallT'] / 2                      # wall plane in Blender y
x0, x1 = g['gx'] - g['w'] / 2, g['gx'] + g['w'] / 2
z0, z1 = g['gy'] - g['h'] / 2, g['gy'] + g['h'] / 2
W2, H = g['wallW'] / 2, g['wallH']
wallM = mat('gate_wall', (0.80, 0.80, 0.79), 0.55)
frameM = mat('gate_frame', (0.05, 0.055, 0.06), 0.35, 0.6)
box('Gate_left', (-W2, wy - t2, 0), (x0, wy + t2, H), wallM)
box('Gate_right', (x1, wy - t2, 0), (W2, wy + t2, H), wallM)
box('Gate_below', (x0, wy - t2, 0), (x1, wy + t2, z0), wallM)
box('Gate_above', (x0, wy - t2, z1), (x1, wy + t2, H), wallM)
f, d = 0.022, t2 + 0.012                                  # slot frame: anodised rails proud of both faces
box('Slot_left', (x0 - f, wy - d, z0 - f), (x0, wy + d, z1 + f), frameM)
box('Slot_right', (x1, wy - d, z0 - f), (x1 + f, wy + d, z1 + f), frameM)
box('Slot_bottom', (x0, wy - d, z0 - f), (x1, wy + d, z0), frameM)
box('Slot_top', (x0, wy - d, z1), (x1, wy + d, z1 + f), frameM)
tagM, tagW = mat('tag_black', (0.01, 0.01, 0.01), 0.7), mat('tag_white', (0.85, 0.85, 0.85), 0.7)
for sx in (-1, 1):                                        # fiducial tags beside the slot, both faces
    for sy in (-1, 1):
        cx, cz = g['gx'] + sx * (g['w'] / 2 + 0.16), z1 - 0.06
        yy = wy + sy * (t2 + 0.002)
        box('Tag', (cx - 0.07, yy - 0.001, cz - 0.07), (cx + 0.07, yy + 0.001, cz + 0.07), tagW)
        box('Tag', (cx - 0.055, yy - 0.0015 * sy - 0.001, cz - 0.055), (cx + 0.055, yy + 0.0015 * sy + 0.001, cz + 0.055), tagM)

floorM = bpy.data.materials.new('lab_floor'); floorM.use_nodes = True
nt = floorM.node_tree; b = nt.nodes['Principled BSDF']
br = nt.nodes.new('ShaderNodeTexBrick'); br.offset = 0; br.squash = 1
br.inputs['Color1'].default_value = br.inputs['Color2'].default_value = (0.42, 0.43, 0.44, 1)
br.inputs['Mortar'].default_value = (0.12, 0.125, 0.13, 1); br.inputs['Scale'].default_value = 1
br.inputs['Mortar Size'].default_value = 0.008; br.inputs['Brick Width'].default_value = 1; br.inputs['Row Height'].default_value = 1
noise = nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 40
mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = 0.45; mr.inputs['To Max'].default_value = 0.75
nt.links.new(br.outputs['Color'], b.inputs['Base Color']); nt.links.new(noise.outputs['Fac'], mr.inputs['Value'])
nt.links.new(mr.outputs['Result'], b.inputs['Roughness'])
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, wy - 2, 0)); fl = bpy.context.active_object
fl.name = 'Lab_floor'; fl.scale = (16, 34, 1); fl.data.materials.append(floorM)
for c in fl.users_collection: c.objects.unlink(fl)
setc.objects.link(fl)
backM = mat('lab_backdrop', (0.16, 0.165, 0.17), 0.85)
box('Lab_back_wall', (-6.1, wy - 19, 0), (-6.0, wy + 15, 6), backM)   # behind the flight, as seen from the camera

def area(name, loc, rot, size, energy, color=(1, 1, 1), shape=('RECTANGLE', None)):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.color = color
    ld.shape = 'RECTANGLE'; ld.size, ld.size_y = size
    o = bpy.data.objects.new(name, ld); o.location = loc; o.rotation_euler = rot; setc.objects.link(o); return o

area('Key_strip', (0.4, wy - 2.5, 4.4), (0, 0, 0), (2.4, 14), KEY)
area('Fill_camside', (4.5, wy - 2.5, 2.2), (0, math.radians(70), 0), (3, 10), KEY * 0.3, (1.0, 0.97, 0.93))
area('Rim_cool', (-4.5, wy - 2.5, 3.2), (0, -math.radians(60), 0), (2, 10), KEY * 0.25, (0.85, 0.92, 1.0))
w = sc.world
if w and w.use_nodes:
    bg = w.node_tree.nodes.get('Background')
    if bg: bg.inputs['Color'].default_value = (0.03, 0.032, 0.035, 1); bg.inputs['Strength'].default_value = 1.0


# ---------------------------------------------------------------- render settings
sc.render.engine = 'BLENDER_EEVEE'
e = sc.eevee
e.taa_render_samples = int(opt('--samples', 48))
e.use_gtao = True; e.gtao_distance = 0.4
e.use_ssr = True; e.use_ssr_halfres = False
e.use_soft_shadows = True; e.shadow_cube_size = '1024'; e.shadow_cascade_size = '2048'
e.use_motion_blur = True; e.motion_blur_shutter = 0.5
sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
sc.render.resolution_percentage = int(opt('--pct', 100))
sc.render.fps = anim['fps']
fa, fb = (int(v) for v in opt('--frames', '1:%d' % n).split(':'))
sc.frame_start, sc.frame_end = fa, fb
LIST = [int(v) for v in opt('--list', '').split(',') if v]
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 95; sc.render.image_settings.color_mode = 'RGB'
sc.render.filepath = os.path.join(OUT, 'f_')
os.makedirs(OUT, exist_ok=True)
if LIST:   # scattered test frames
    for f in LIST:
        sc.frame_set(f); sc.render.filepath = os.path.join(OUT, 'f_%04d.jpg' % f); bpy.ops.render.render(write_still=True)
    print('rendered frames', LIST, '->', OUT)
else:
    bpy.ops.render.render(animation=True)
    print('rendered frames', fa, 'to', fb, '->', OUT)
