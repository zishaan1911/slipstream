"""Realistic Cycles materials for the SX-01 airframe, from CC0 ambientCG scans plus procedural detail.

    blender -b blender/slipstream_studio.blend --python blender/materials.py    # apply to the scene and save
    (update_airframe.py applies it automatically after importing a new airframe)

Every surface gets a render-time Bevel node (0.6 mm) feeding its normal, so hard edges of boxes, plates and
PCBs catch light the way machined and moulded parts do. Textures are box-projected in object space, so no UVs
are needed. Texture sets live in blender/assets/ambientcg/<id>/ (1K JPG, CC0; see CREDITS.md):
  Fabric004 carbon weave, Metal009 linear-brushed steel, Metal051A circular-brushed aluminium,
  Rubber004 rubber, Plastic006 / Plastic010 plastic micro-surface.
"""
import bpy, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, 'assets', 'ambientcg')
BEVEL_R = 0.0006


def _img(nt, path, color):
    n = nt.nodes.new('ShaderNodeTexImage')
    n.image = bpy.data.images.load(path, check_existing=True)
    n.image.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
    n.projection = 'BOX'; n.projection_blend = 0.25
    return n


def _maps(asset):
    d = os.path.join(TEX, asset); out = {}
    if not os.path.isdir(d): return out
    for f in os.listdir(d):
        for key in ('Color', 'Roughness', 'NormalGL', 'Metalness'):
            if f.endswith('_' + key + '.jpg'): out[key] = os.path.join(d, f)
    return out


def build(mat, base, rough=(0.3, 0.3), metal=0.0, asset=None, scale=60.0, normal=0.6, coat=0.0, coat_rough=0.05,
          use_color=False, tint=None, subsurface=0.0, sheen=0.0, aniso=0.0):
    """Rebuild a material: optional scan textures (box-projected) + bevelled normal into one Principled BSDF."""
    mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear(); L = nt.links.new
    out = nt.nodes.new('ShaderNodeOutputMaterial'); b = nt.nodes.new('ShaderNodeBsdfPrincipled'); L(b.outputs[0], out.inputs[0])
    b.inputs['Base Color'].default_value = (*base, 1); b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough[0]
    b.inputs['Clearcoat'].default_value = coat; b.inputs['Clearcoat Roughness'].default_value = coat_rough
    b.inputs['Subsurface'].default_value = subsurface; b.inputs['Sheen'].default_value = sheen
    b.inputs['Anisotropic'].default_value = aniso
    if subsurface:
        b.inputs['Subsurface Radius'].default_value = (0.002, 0.0018, 0.0015); b.inputs['Subsurface Color'].default_value = (*base, 1)
    bev = nt.nodes.new('ShaderNodeBevel'); bev.inputs['Radius'].default_value = BEVEL_R; bev.samples = 6
    maps = _maps(asset) if asset else {}
    if maps:
        tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (scale, scale, scale)
        L(tc.outputs['Object'], mp.inputs['Vector'])
        if 'Roughness' in maps:
            r = _img(nt, maps['Roughness'], False); L(mp.outputs[0], r.inputs['Vector'])
            mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = rough[0]; mr.inputs['To Max'].default_value = rough[1]
            L(r.outputs['Color'], mr.inputs['Value']); L(mr.outputs['Result'], b.inputs['Roughness'])
        if 'NormalGL' in maps and normal > 0:
            n = _img(nt, maps['NormalGL'], False); L(mp.outputs[0], n.inputs['Vector'])
            nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = normal
            L(n.outputs['Color'], nm.inputs['Color']); L(nm.outputs['Normal'], bev.inputs['Normal'])
        if use_color and 'Color' in maps:
            c = _img(nt, maps['Color'], True); L(mp.outputs[0], c.inputs['Vector'])
            if tint:
                mix = nt.nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MULTIPLY'; mix.inputs['Fac'].default_value = 1.0
                mix.inputs[2].default_value = (*tint, 1); L(c.outputs['Color'], mix.inputs[1]); L(mix.outputs[0], b.inputs['Base Color'])
            else:
                L(c.outputs['Color'], b.inputs['Base Color'])
    L(bev.outputs['Normal'], b.inputs['Normal'])
    if coat:   # the clear coat stays smooth over textured bases, like real lacquer
        cb = nt.nodes.new('ShaderNodeBevel'); cb.inputs['Radius'].default_value = BEVEL_R; cb.samples = 6
        L(cb.outputs['Normal'], b.inputs['Clearcoat Normal'])
    return mat


def base_color(mat, default=(0.5, 0.5, 0.5)):
    if mat and mat.use_nodes:
        for n in mat.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED': return tuple(n.inputs['Base Color'].default_value[:3])
    return default


RECIPES = {
    # ceramic-white shell: warm white, glossy lacquer, faint orange-peel, a touch of translucency
    'shell_white': lambda m, c: build(m, (0.87, 0.86, 0.84), (0.14, 0.24), asset='Plastic010', scale=40, normal=0.12, coat=1.0, coat_rough=0.025, subsurface=0.04),
    'carbon_fibre': lambda m, c: build(m, (0.02, 0.02, 0.022), (0.22, 0.4), asset='Fabric004', scale=140, normal=0.9, coat=1.0, coat_rough=0.04, use_color=True, tint=(0.35, 0.36, 0.38), aniso=0.3),
    'alu': lambda m, c: build(m, (0.82, 0.83, 0.85), (0.22, 0.38), metal=1.0, asset='Metal009', scale=90, normal=0.3, aniso=0.6),
    'aluDark': lambda m, c: build(m, (0.42, 0.43, 0.45), (0.28, 0.42), metal=1.0, asset='Metal009', scale=90, normal=0.3, aniso=0.5),
    'chrome': lambda m, c: build(m, (0.92, 0.92, 0.93), (0.05, 0.12), metal=1.0, asset='Metal009', scale=120, normal=0.1),
    'orange': lambda m, c: build(m, (0.9, 0.32, 0.07), (0.25, 0.4), metal=1.0, asset='Metal051A', scale=55, normal=0.4, aniso=0.6),
    'blackAl': lambda m, c: build(m, (0.025, 0.026, 0.028), (0.32, 0.46), metal=0.9, asset='Metal009', scale=90, normal=0.25),
    'gimbal_alu': lambda m, c: build(m, (0.05, 0.052, 0.056), (0.34, 0.48), metal=0.9, asset='Metal009', scale=90, normal=0.25),
    'leg_graphite': lambda m, c: build(m, (0.035, 0.036, 0.04), (0.3, 0.42), metal=0.85, asset='Metal009', scale=60, normal=0.2, coat=0.3),
    'rubber': lambda m, c: build(m, (0.018, 0.018, 0.02), (0.75, 0.95), asset='Rubber004', scale=250, normal=0.6),
    'tpu': lambda m, c: build(m, (0.04, 0.04, 0.045), (0.6, 0.85), asset='Rubber004', scale=250, normal=0.4),
    'velcro': lambda m, c: build(m, (0.015, 0.015, 0.017), (0.85, 1.0), asset='Fabric004', scale=300, normal=1.0, sheen=0.4),
    'plastic': lambda m, c: build(m, c, (0.35, 0.5), asset='Plastic006', scale=80, normal=0.25),
    'servo_case': lambda m, c: build(m, c, (0.38, 0.52), asset='Plastic006', scale=80, normal=0.25),
    'servo_horn': lambda m, c: build(m, c, (0.4, 0.55), asset='Plastic010', scale=80, normal=0.2),
    'zip': lambda m, c: build(m, c, (0.4, 0.55), asset='Plastic010', scale=80, normal=0.2),
    'xt60': lambda m, c: build(m, c, (0.35, 0.5), asset='Plastic006', scale=80, normal=0.2),
    'chip': lambda m, c: build(m, (0.02, 0.02, 0.022), (0.35, 0.5), asset='Plastic006', scale=120, normal=0.2),
    'pcb': lambda m, c: build(m, c, (0.3, 0.45), asset='Plastic006', scale=150, normal=0.15, coat=0.4),
    'pcbG': lambda m, c: build(m, c, (0.3, 0.45), asset='Plastic006', scale=150, normal=0.15, coat=0.4),
    'pcb_green': lambda m, c: build(m, c, (0.3, 0.45), asset='Plastic006', scale=150, normal=0.15, coat=0.4),
    'copper': lambda m, c: build(m, (0.85, 0.42, 0.22), (0.2, 0.35), metal=1.0, asset='Metal051A', scale=200, normal=0.5),
    'gold': lambda m, c: build(m, (0.95, 0.72, 0.35), (0.15, 0.25), metal=1.0),
    'graphite': lambda m, c: build(m, c, (0.35, 0.5), metal=0.4, asset='Metal009', scale=90, normal=0.2),
    'prop': lambda m, c: build(m, (0.015, 0.016, 0.018), (0.2, 0.34), asset='Plastic006', scale=60, normal=0.15, coat=0.5),
    'glassBlk': lambda m, c: build(m, (0.01, 0.01, 0.012), (0.03, 0.06), coat=1.0, coat_rough=0.01),
    'lens': lambda m, c: build(m, (0.005, 0.006, 0.008), (0.02, 0.04), metal=0.4, coat=1.0, coat_rough=0.01),
    'sensor_window': lambda m, c: build(m, (0.006, 0.007, 0.009), (0.02, 0.04), coat=1.0, coat_rough=0.01),
}


def apply(objects=None):
    """Rebuild every recognised airframe material once (shared materials are only rebuilt the first time)."""
    objs = objects if objects is not None else [o for o in bpy.data.objects if o.type == 'MESH']
    done, wires, decals = set(), 0, 0
    for o in objs:
        if o.type != 'MESH': continue
        for slot in o.material_slots:
            m = slot.material
            if not m or m.name in done: continue
            key = m.name.split('.')[0]
            if key in ('carbon',):
                key = 'carbon_fibre'
            if key in RECIPES:
                RECIPES[key](m, base_color(m)); done.add(m.name)
            elif key.startswith('wire_'):
                build(m, base_color(m), (0.42, 0.55), asset='Plastic006', scale=200, normal=0.15, sheen=0.25); done.add(m.name); wires += 1
            elif key.startswith('mat_'):   # unnamed inline colours from the sim: moulded plastic with their own colour
                build(m, base_color(m), (0.38, 0.52), asset='Plastic006', scale=80, normal=0.2); done.add(m.name)
            elif key == 'label' and m.use_nodes:   # printed labels: keep the print, add a thin lacquer
                for n in m.node_tree.nodes:
                    if n.type == 'BSDF_PRINCIPLED': n.inputs['Clearcoat'].default_value = 0.6; n.inputs['Clearcoat Roughness'].default_value = 0.08
                done.add(m.name); decals += 1
    bevelled = 0
    for m in bpy.data.materials:   # everything else (the Sketchfab parts' own textures): just round the edges
        if m.name in done or not m.use_nodes: continue
        nt = m.node_tree
        if any(n.type == 'BEVEL' for n in nt.nodes): continue
        for b in [n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED']:
            bev = nt.nodes.new('ShaderNodeBevel'); bev.inputs['Radius'].default_value = BEVEL_R; bev.samples = 6
            src = b.inputs['Normal'].links[0].from_socket if b.inputs['Normal'].is_linked else None
            if src: nt.links.new(src, bev.inputs['Normal'])   # keep the part's own normal map under the bevel
            nt.links.new(bev.outputs['Normal'], b.inputs['Normal']); bevelled += 1
    print('materials rebuilt:', len(done), '(wires', wires, ', labels', decals, '), bevel added to', bevelled, 'others')
    return done


if __name__ == '__main__':
    apply()
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_mainfile(compress=True)
    print('saved', bpy.data.filepath)
