# SlipStream

**Gannet SX-01 morphing quadrotor · narrow-gap traversal · Seventh Axis Aerial Robotics**

SlipStream is a browser-based simulation of Gannet (model SX-01), a 1.40 kg research quadrotor whose arms fold on servos
so it can squeeze through gaps narrower than its own span, and roll knife-edge through slots narrower
than its folded width.

![SX-01 hero render](renders/stills/01_hero.png)

## What is in here

| Path | What it is |
|---|---|
| `slipstream.html` | The simulator: flight arena, SX-01 airframe, physics, autopilot, experiment console |
| `electronics/spice/` | ngspice models of the power chain: pack and bus, ESC bridge + BLDC, 12 V buck rail |
| `electronics/linkage/` | fold linkage synthesis: servo horn, pushrod and arm lever geometry, transmission angle, torque check |
| `electronics/harness/` | wiring harness parts list + netlist that builds the 3D harness and the wiring diagram (`harness.html`) |
| `blender/` | Cycles studio scene for photoreal stills, fed by the exported airframe |
| `electronics/notebook.html` | Engineering notebook: schematics, waveforms, SPICE vs. flight-model comparison |
| `electronics/build_notebook.py` | Fills the notebook from `spice/results.json` |
| `electronics/apply_feedback.py` | Copies SPICE-fitted constants into the simulator |
| `tools/render.py` | Headless renderer for videos and stills |
| `renders/` | Rendered videos (`videos/`) and stills (`stills/`) |

## Running the simulator

Serve the folder and open the page (fonts and three.js load from public CDNs):

```bash
python -m http.server 8000
```

Then open <http://localhost:8000/slipstream.html>.

- **Controller:** Autonomous cycles through the gates. Assisted and Manual take W A S D, Space/Shift, Q/E;
  F folds, V holds a knife-edge roll.
- **Gates:** A 1200 × 900 mm (open), B 520 × 1100 mm (fold), C 270 × 600 mm (fold + knife-edge).

### Knife-edge through gate C

The folded span (407 mm) is wider than the 270 mm slot, so Gannet passes on its side in five steps
(`renders/videos/knife.mp4` shows them with live rotor speeds):

1. **Pop:** a short ~1.4 g climb about 0.8 s out banks upward speed, so the unpowered coast peaks inside the slot.
2. **Roll:** differential thrust rolls the folded airframe 90°, with collective cut to near zero.
3. **Stop:** all four ESCs actively brake the props to 0 rpm before the slot. On its side, any thrust would push
   it sideways into the slot edge, and with no thrust there is no attitude control, so it coasts at its own roll rate.
4. **Push-pull:** once the tail clears, one side spins forward and the other in reverse (BLHeli_32 3D mode, a
   reversed prop gives ~55 % thrust). Equal and opposite thrust doubles the roll torque with no net sideways force,
   and lift is blended back in over the last 60° of the roll.
5. **Level:** all rotors forward, arms open, and the drop from the coast is caught.

It clears the slot by 25-26 mm on 100, 50 and 20 % packs and bottoms out 0.43-0.64 m above the floor afterwards.
`__SS.knifeTrace()` logs the state, roll and signed rotor speeds through the gate.

`renders/videos/knife_blender.mp4` is the same run rendered in Blender (Eevee) with the infographic composited on:
`python tools/knife_blender.py` exports the flight from the sim with eased slow motion (every moving part, props that
stop and reverse with their rotors, wires bent by the fold as shape keys), keys it onto the studio scene with the gate
wall built to match, renders and encodes. The full run takes about 1 h 45 min on this laptop.
- **Battery:** start a fresh pack at 100, 50 or 20 % charge; toggle battery-voltage compensation.
- **Chassis:** white shell, X-ray, or bare airframe.

## Airframe

- Ceramic-white machined unibody sized from the electronics it carries: `__SS.fit()` checks every internal part
  against the shell's inner wall (2.5 mm wall, 1.3 mm minimum clearance). Smooth, continuous curves: the required
  envelope is dilated and Gaussian-blurred, never cut below what it covers.
- Tight packaging: carbon plates are a narrow spine with a lobe round each fold hinge (`electronics/linkage/plate.py`),
  fold servos sit inside the hinge lobes, a compact 50 mm stereo depth module looks out through three flush windows,
  receiver antennas lie inside the RF-transparent tail, and mocap markers are flush dots.
- Each arm leaves its shoulder at nearly full body depth and tapers to a machined motor pod (nav LED in its base);
  the hinge sits inside the shoulder. Folds 45° to 9° through a servo horn + pushrod linkage
  (`electronics/linkage/design_linkage.py`).
- Four tall landing legs retract with the fold, with no extra actuator (`electronics/linkage/design_legs.py`).
- 2-axis gimbal camera under the belly, on 12 V from the compute buck and serial control from the FC.
- Every conductor comes from one parts list and netlist (`electronics/harness/`), which also draws the wiring diagram.
- Propulsion constants and all-up mass live in `electronics/motor.json` (2807 1300 KV, 7" tri-blade, 1.40 kg).
- Earlier exterior studies are in `concepts/` (render with `python concepts/render_unibody.py`).

## Flight and power model

- Rigid-body flight with cascaded position / attitude control and fold-aware gain scheduling.
- 4S 2200 mAh LiPo per cell: open-circuit voltage curve, ohmic + RC polarisation, coulomb counting, heating.
- Four ESCs with current limit, duty ramp and active braking, driving 2807 1300 KV motors with a DC-equivalent
  model fitted from the SPICE switching simulation.
- 7.4 V servo, 12 V compute and 5 V flight-controller rails; the 12 V rail browns out on deep sag and the
  autopilot performs a failsafe landing.

## SPICE models

```bash
cd electronics/spice
python run_all.py            # needs ngspice on PATH or NGSPICE=...; the buck case takes several minutes
cd ..
python build_notebook.py     # writes notebook.html and feedback.json
python apply_feedback.py     # updates the constants in slipstream.html
```

## Renders

```bash
pip install playwright pillow   # uses the installed Microsoft Edge, no browser download
python tools/render.py videos   # renders/videos/*.mp4 (1080 × 1920)
python tools/render.py stills   # renders/stills/*.png (1080 × 1350)
```

Video encoding uses `ffmpeg` with libx264.
