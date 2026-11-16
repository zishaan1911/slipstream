# Third-party models

The Blender studio scene swaps in these models from Sketchfab, all under
[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
They are resized and repositioned to fit the SX-01 airframe (`add_parts.py`); the servo is recoloured black
and the battery's own leads are left out. Credit the authors wherever renders that show these parts are posted.

| Part on SX-01 | Model | Author |
|---|---|---|
| Motors | [Brushless Motor-4K-MaterialTest](https://sketchfab.com/3d-models/brushless-motor-4k-materialtest-115eeac03b224af7b660b08be6b76fba) | [chiwei](https://sketchfab.com/chiwei2333) |
| Fold servos | [SG90 Servo (1:1 Scale)](https://sketchfab.com/3d-models/sg90-servo-11-scale-c865adb97e32477f8016658e340375b6) | [IQuanix](https://sketchfab.com/iquanix) |
| Flight battery | [Drone_Lipo_battery_4s](https://sketchfab.com/3d-models/drone-lipo-battery-4s-2279697ec4b44d75813fd365d96a4e07) | [3dArenaRaj](https://sketchfab.com/3dArenaRaj) |
| Propellers (scaled to 7") | [5" Tri-Blade Propeller](https://sketchfab.com/3d-models/5-tri-blade-propeller-29c041703a6d49ecb08bc2427d71851a) | [The Van](https://sketchfab.com/thevan) |
| Companion computer | [Raspberry Pi 4 Compute Module (CM4)](https://sketchfab.com/3d-models/raspberry-pi-4-compute-module-cm4-272a7060c84a430ba494b325f56d80f1) | [Vacui](https://sketchfab.com/HunterVacui) |

Suggested caption credit: *Motor by chiwei, servo by IQuanix, LiPo by 3dArenaRaj, prop by The Van, CM4 by Vacui (Sketchfab, CC BY 4.0).*

The `.glb` files go in `blender/assets/` (not committed; download them from the links above while signed in).

# Surface textures

`materials.py` builds the Cycles materials from these [ambientCG](https://ambientcg.com) scans, all
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) (public domain, no credit required; credited here anyway).
They are box-projected in object space at their real-world scale, so the parts need no UVs.

| Used for | Set |
|---|---|
| Carbon plates (weave) | [Fabric004](https://ambientcg.com/view?id=Fabric004) |
| Linear-brushed metal: aluminium, anodised legs and gimbal | [Metal009](https://ambientcg.com/view?id=Metal009) |
| Circular-brushed metal: orange motor rings, copper | [Metal051A](https://ambientcg.com/view?id=Metal051A) |
| Rubber feet, TPU | [Rubber004](https://ambientcg.com/view?id=Rubber004) |
| Moulded plastic, PCBs, wire jackets | [Plastic006](https://ambientcg.com/view?id=Plastic006) |
| Ceramic-white shell (micro-texture under the clear coat), servo horns | [Plastic010](https://ambientcg.com/view?id=Plastic010) |

Download the 1K-JPG zips and unpack each into `blender/assets/ambientcg/<id>/` (not committed).
