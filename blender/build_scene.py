"""Build the SlipStream studio scene in Blender (2.93 LTS; also runs on 3.x) from blender/sx01.glb.

    blender -b --python blender/build_scene.py            # writes blender/slipstream_studio.blend
    blender -b --python blender/build_scene.py -- --test  # also renders blender/test.png at 50 %

Dark studio: matte black floor, a hanging dome pendant straight above the airframe (warm spot with a
soft radius, emissive bulb, enamel inside), cool and warm rim panels behind, faint haze in the beam.
"""
import bpy, bmesh, math, os, sys, time
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
GLB = os.path.join(HERE, 'sx01.glb')
OUT = os.path.join(HERE, 'slipstream_studio.blend')
HOVER = 1.0      # airframe centre height (m)
LAMP_Z = 1.72    # rim of the lamp shade

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def coll(name):
    c = bpy.data.collections.new(name); sc.collection.children.link(c); return c


def put(obj, c):
    for u in list(obj.users_collection): u.objects.unlink(obj)
    c.objects.link(obj)


def hide_from(o, camera=None, shadow=None):  # ray visibility: 3.x properties, 2.9x cycles_visibility
    for k, v in (('camera', camera), ('shadow', shadow)):
        if v is None: continue
        if hasattr(o, 'visible_' + k): setattr(o, 'visible_' + k, v)
        else: setattr(o.cycles_visibility, k, v)


def principled(name, color=(0.8, 0.8, 0.8), rough=0.5, metal=0.0, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1); b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    for k, v in kw.items():
        b.inputs[k].default_value = (*v, 1) if isinstance(v, tuple) and len(v) == 3 else v
    return m


def emission(name, color, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (*color, 1); e.inputs['Strength'].default_value = strength
    o = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(e.outputs[0], o.inputs[0])
    return m


# ---------------------------------------------------------------- airframe
sys.path.insert(0, HERE)
import airframe
airframe.import_airframe(GLB, HOVER)

# ---------------------------------------------------------------- studio
C_STUDIO = coll('Studio')
world = bpy.data.worlds.new('Dark studio'); sc.world = world; world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.0016, 0.0017, 0.002, 1)

bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0)); floor = bpy.context.object; floor.name = 'Floor'
floor.data.materials.append(principled('floor_black', (0.006, 0.0062, 0.0066), 0.42, Specular=0.3)); put(floor, C_STUDIO)

# dome pendant
C_LAMP = coll('Pendant lamp')
bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=0.14, location=(0, 0, LAMP_Z))
shade = bpy.context.object; shade.name = 'Lamp_shade'
bm = bmesh.new(); bm.from_mesh(shade.data)
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -1e-5], context='VERTS')
cap = [v for v in bm.verts if v.co.z > 0.137]  # small opening at the top for the cord sleeve
bmesh.ops.delete(bm, geom=cap, context='VERTS')
bm.to_mesh(shade.data); bm.free()
shade.scale.z = 0.95
for p in shade.data.polygons: p.use_smooth = True
shade.data.materials.append(principled('lamp_steel_black', (0.012, 0.012, 0.013), 0.3, 0.85))
shade.data.materials.append(principled('lamp_enamel', (0.85, 0.82, 0.76), 0.45))
sol = shade.modifiers.new('thickness', 'SOLIDIFY'); sol.thickness = 0.0025; sol.offset = -1; sol.material_offset = 1
shade.modifiers.new('subd', 'SUBSURF').levels = 1
put(shade, C_LAMP)
bpy.ops.mesh.primitive_torus_add(major_radius=0.1395, minor_radius=0.0022, major_segments=160, minor_segments=16, location=(0, 0, LAMP_Z))
rim = bpy.context.object; rim.name = 'Lamp_brass_rim'; rim.data.materials.append(principled('lamp_brass', (0.78, 0.56, 0.3), 0.25, 1.0))
for p in rim.data.polygons: p.use_smooth = True
put(rim, C_LAMP)
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.022, depth=0.05, location=(0, 0, LAMP_Z + 0.145))
sleeve = bpy.context.object; sleeve.name = 'Lamp_sleeve'; sleeve.data.materials.append(bpy.data.materials['lamp_steel_black'])
sleeve.modifiers.new('bevel', 'BEVEL').width = 0.003; put(sleeve, C_LAMP)
for p in sleeve.data.polygons: p.use_smooth = True
bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.0028, depth=5, location=(0, 0, LAMP_Z + 0.17 + 2.5))
cord = bpy.context.object; cord.name = 'Lamp_cord'; cord.data.materials.append(principled('cord_fabric', (0.01, 0.01, 0.011), 0.85, Sheen=0.5))
put(cord, C_LAMP)
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.038, location=(0, 0, LAMP_Z + 0.035))
bulb = bpy.context.object; bulb.name = 'Lamp_bulb'; bulb.data.materials.append(emission('bulb_glow', (1.0, 0.78, 0.55), 22))
for p in bulb.data.polygons: p.use_smooth = True
hide_from(bulb, shadow=False); put(bulb, C_LAMP)

def light(name, kind, loc, energy, color, c, **kw):
    d = bpy.data.lights.new(name, kind); d.energy = energy; d.color = color
    for k, v in kw.items(): setattr(d, k, v)
    o = bpy.data.objects.new(name, d); o.location = loc; c.objects.link(o)
    return o

def aim(o, target):
    o.rotation_euler = (Vector(target) - o.location).to_track_quat('-Z', 'Y').to_euler()

spot = light('Lamp_spot', 'SPOT', (0, 0, LAMP_Z + 0.02), 95, (1.0, 0.84, 0.66), C_LAMP,
             spot_size=math.radians(58), spot_blend=0.55, shadow_soft_size=0.06)
spot.rotation_euler = (0, 0, 0)  # straight down
rim_cool = light('Rim_cool', 'AREA', (-2.2, -2.6, 1.9), 220, (0.78, 0.86, 1.0), C_STUDIO, shape='RECTANGLE', size=0.6, size_y=2.2)
aim(rim_cool, (0, 0, HOVER))
rim_warm = light('Rim_warm', 'AREA', (2.4, -2.2, 1.3), 160, (1.0, 0.62, 0.32), C_STUDIO, shape='RECTANGLE', size=0.5, size_y=1.8)
aim(rim_warm, (0, 0, HOVER))
fill = light('Fill_front', 'AREA', (1.2, 3.0, 1.5), 40, (1.0, 0.97, 0.94), C_STUDIO, shape='DISK', size=1.6)
aim(fill, (0, 0, HOVER))
for l in (rim_cool, rim_warm, fill):
    hide_from(l, camera=False)

# faint haze inside the beam only (a volume cone keeps the render cost local)
bpy.ops.mesh.primitive_cone_add(vertices=96, radius1=1.05, radius2=0.12, depth=LAMP_Z + 0.08, location=(0, 0, (LAMP_Z - 0.18) / 2))
haze = bpy.context.object; haze.name = 'Beam_haze'
hm = bpy.data.materials.new('haze_volume'); hm.use_nodes = True; nt = hm.node_tree; nt.nodes.remove(nt.nodes['Principled BSDF'])
pv = nt.nodes.new('ShaderNodeVolumePrincipled'); pv.inputs['Density'].default_value = 0.012; pv.inputs['Anisotropy'].default_value = 0.35
nt.links.new(pv.outputs[0], nt.nodes['Material Output'].inputs['Volume'])
haze.data.materials.append(hm); hide_from(haze, shadow=False); put(haze, C_STUDIO)

# ---------------------------------------------------------------- cameras
C_CAM = coll('Cameras')
target = bpy.data.objects.new('Cam_target', None); target.location = (0, 0, HOVER + 0.02); C_CAM.objects.link(target)

def camera(name, loc, lens, fstop=4.0, tgt=target):
    d = bpy.data.cameras.new(name); d.lens = lens; d.sensor_width = 36
    d.dof.use_dof = True; d.dof.focus_object = target; d.dof.aperture_fstop = fstop
    o = bpy.data.objects.new(name, d); o.location = loc; C_CAM.objects.link(o)
    t = o.constraints.new('TRACK_TO'); t.target = tgt; t.track_axis = 'TRACK_NEGATIVE_Z'; t.up_axis = 'UP_Y'
    return o

hero = camera('Cam_hero', (1.15, 1.45, 1.38), 80, 3.2)
camera('Cam_low_front', (0.12, 1.75, 0.88), 70, 2.8)
camera('Cam_side', (2.1, -0.15, 1.12), 85, 4.0)
camera('Cam_top', (0.62, 0.9, 1.95), 45, 5.6)
el_t = bpy.data.objects.new('Cam_target_electronics', None); el_t.location = (0, 0.01, HOVER + 0.025); C_CAM.objects.link(el_t)
camera('Cam_electronics', (0.36, 0.42, 1.42), 50, 4.0, el_t)
lk_t = bpy.data.objects.new('Cam_target_linkage', None); lk_t.location = (0.056, 0.062, HOVER + 0.006); C_CAM.objects.link(lk_t)
camera('Cam_linkage', (0.25, 0.27, HOVER + 0.028), 70, 11, lk_t)
lamp_t = bpy.data.objects.new('Cam_target_lamp', None); lamp_t.location = (0, 0, 1.36); C_CAM.objects.link(lamp_t)
camera('Cam_wide_with_lamp', (1.55, 2.9, 1.25), 45, 5.6, lamp_t)
sc.camera = hero

# ---------------------------------------------------------------- render settings
sc.render.engine = 'CYCLES'
cy = sc.cycles
cy.device = 'CPU'; cy.samples = 160; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.015
cy.use_denoising = True; cy.denoiser = 'OPENIMAGEDENOISE'
cy.preview_samples = 24
if hasattr(cy, 'use_preview_denoising'): cy.use_preview_denoising = True
cy.max_bounces = 8; cy.diffuse_bounces = 3; cy.glossy_bounces = 4; cy.transmission_bounces = 6; cy.volume_bounces = 0
cy.transparent_max_bounces = 12; cy.caustics_reflective = False; cy.caustics_refractive = False; cy.blur_glossy = 1.0
cy.volume_step_rate = 4.0
sc.render.resolution_x, sc.render.resolution_y = 1080, 1350
sc.render.film_transparent = False
sc.view_settings.view_transform = 'Filmic'
for look in ('Medium High Contrast', 'Filmic - Medium High Contrast'):
    try: sc.view_settings.look = look; break
    except TypeError: pass
sc.view_settings.exposure = 0.0
sc.render.image_settings.file_format = 'PNG'

bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('saved', OUT)

if '--test' in sys.argv:
    sc.render.resolution_percentage = 50; cy.samples = 64
    sc.render.filepath = os.path.join(HERE, 'test.png')
    t = time.time(); bpy.ops.render.render(write_still=True)
    print('render s', round(time.time() - t, 1))
