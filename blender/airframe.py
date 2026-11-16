"""Import the exported SX-01 airframe (blender/sx01.glb) into the open scene and upgrade its materials.

Shared by build_scene.py (fresh scene) and update_airframe.py (swap the airframe in an existing, edited scene).
"""
import bpy


def coll(name):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c)
    return c


def put(obj, c):
    for u in list(obj.users_collection): u.objects.unlink(obj)
    c.objects.link(obj)


def emission(name, color, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (*color, 1); e.inputs['Strength'].default_value = strength
    o = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(e.outputs[0], o.inputs[0])
    return m


def bsdf(m):
    return next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if m and m.use_nodes else None


def carbon_material():
    m = bpy.data.materials.get('carbon_fibre')
    if m: return m
    m = bpy.data.materials.new('carbon_fibre'); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (260, 260, 260)
    ck = nt.nodes.new('ShaderNodeTexChecker'); ck.inputs['Color1'].default_value = (0.018, 0.019, 0.021, 1); ck.inputs['Color2'].default_value = (0.045, 0.047, 0.05, 1)
    ck.inputs['Scale'].default_value = 1.0
    wv = nt.nodes.new('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.inputs['Scale'].default_value = 2.0
    mix = nt.nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MULTIPLY'; mix.inputs['Fac'].default_value = 0.35
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], ck.inputs['Vector']); nt.links.new(mp.outputs['Vector'], wv.inputs['Vector'])
    nt.links.new(ck.outputs['Color'], mix.inputs[1]); nt.links.new(wv.outputs['Color'], mix.inputs[2])
    nt.links.new(mix.outputs['Color'], b.inputs['Base Color'])
    rr = nt.nodes.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = 0.28; rr.inputs['To Max'].default_value = 0.45
    nt.links.new(ck.outputs['Fac'], rr.inputs['Value']); nt.links.new(rr.outputs['Result'], b.inputs['Roughness'])
    b.inputs['Metallic'].default_value = 0.0; b.inputs['Clearcoat'].default_value = 1.0; b.inputs['Clearcoat Roughness'].default_value = 0.06
    b.inputs['Anisotropic'].default_value = 0.4
    return m


LED = {'ledG': (0.2, 1.0, 0.35), 'ledB': (0.2, 0.45, 1.0), 'ledR': (1.0, 0.08, 0.05), 'ledW': (1.0, 0.95, 0.9)}


def import_airframe(glb, hover, matrix=None):
    """import glb into 'SX-01 airframe'; place its root at (0, 0, hover), or at a saved world matrix"""
    c_drone = coll('SX-01 airframe')
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=glb)
    imported = [o for o in bpy.data.objects if o not in before]
    for o in imported: put(o, c_drone)
    # the depth camera sits under the shell's visor: kept, but hidden (enable it for x-ray / exploded shots)
    c_sensor = coll('Depth camera (under shell)')
    for o in [o for o in imported if o.name.startswith('Sensor_')]:
        put(o, c_sensor); o.hide_render = True; o.hide_viewport = True
    root = bpy.data.objects['SX-01']
    if matrix is not None: root.matrix_world = matrix
    else: root.location = (0, 0, hover)
    carbon = carbon_material()
    for o in imported:
        if o.type != 'MESH': continue
        for slot in o.material_slots:
            m = slot.material
            if not m: continue
            base = m.name.split('.')[0]
            if base == 'carbon': slot.material = carbon; continue
            if base in LED: slot.material = emission('led_' + base, LED[base], 12); continue
            b = bsdf(m)
            if not b: continue
            if base.startswith('mat_ffffff') or o.name.startswith('Shell_mat'):   # the white shell
                m.name = 'shell_white'
                b.inputs['Roughness'].default_value = 0.32; b.inputs['Clearcoat'].default_value = 0.9
                b.inputs['Clearcoat Roughness'].default_value = 0.05; b.inputs['Subsurface'].default_value = 0.0
            elif base == 'prop':
                b.inputs['Base Color'].default_value = (0.02, 0.022, 0.025, 1); b.inputs['Roughness'].default_value = 0.18
                b.inputs['Clearcoat'].default_value = 0.6
            elif base in ('alu', 'aluDark', 'chrome', 'gold', 'copper'):
                b.inputs['Anisotropic'].default_value = 0.5 if base.startswith('alu') else 0.0
            elif base.startswith('wire') or base in ('tpu', 'rubber', 'velcro'):
                b.inputs['Sheen'].default_value = 0.3
        if o.data.polygons:  # smooth shading everywhere; custom normals from glTF are kept
            o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
    return root, imported
