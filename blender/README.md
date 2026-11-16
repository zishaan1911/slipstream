# Blender studio

Photoreal stills of SX-01 in Cycles. Built for Blender 2.93 LTS (runs on older GPUs; 3.x also works).

1. `python tools/export_glb.py` exports the airframe from `slipstream.html` to `blender/sx01.glb`.
2. `blender -b --python blender/build_scene.py` builds `slipstream_studio.blend`: dark studio, hanging dome lamp,
   rim lights, faint haze in the beam, and cameras (`Cam_hero`, `Cam_low_front`, `Cam_side`, `Cam_top`,
   `Cam_electronics`, `Cam_wide_with_lamp`).
3. `blender -b blender/slipstream_studio.blend --python blender/add_parts.py` swaps in the detailed Sketchfab parts
   from `blender/assets/` (see `CREDITS.md`).
4. `blender -b blender/slipstream_studio.blend --python blender/render_still.py -- Cam_hero out.png [--xray]`
   renders a still; `--xray` hides the shell to show the electronics.
