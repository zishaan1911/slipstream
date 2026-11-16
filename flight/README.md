# Gannet flight code (ArduPilot)

The knife-edge for the real airframe, written for ArduCopter and tested in the simulator by running the exact
script against its physics. **Not flight tested.** The simulator says what has to be true of the hardware before it
is worth flying; the rigs in `../rigs/` measure that.

| File | What it is |
|---|---|
| `gannet_frame.lua` | the frame: a quad X on the 6DoF scripting mixer with all four motors reversible |
| `knife_edge.lua` | the manoeuvre: approach, pop, roll, stop, push-pull, level; roll-rig mode (`KNF_RIG 1`) |
| `gannet.parm` | ArduCopter parameters: frame, DShot 3D, fold servos, trigger switch, motion capture, gate |
| `sim_mock.lua` | the ArduPilot scripting API, mocked onto the simulator (only for the in-sim runs) |

## Why the 6DoF frame

With DShot ESCs in 3D (bidirectional) mode a PWM of 1500 is stopped, 1000 full reverse and 2000 full forward
([ArduPilot DShot docs](https://ardupilot.org/copter/docs/common-dshot-escs.html); the mapping is in
`AP_HAL_ChibiOS/RCOutput.cpp`, `dshot_send`). Copter's normal mixers force DShot outputs to 1000-2000 for 0-100 %
throttle (`AP_MotorsMulticopter::update_throttle_range`), so on 3D ESCs they would spin the props backwards at idle,
and ArduPilot's docs list reversible ESCs for Plane and Rover only. The **6DoF scripting mixer**
(`FRAME_CLASS 16`, `AP_MotorsMatrix_6DoF_Scripting`) is the exception: `add_motor(..., reversible = true)` centres the
output on 1500 and mixes signed thrust. Gannet flies on it normally; `knife_edge.lua` takes the four outputs directly
(`SRV_Channels:set_output_pwm_chan_timeout`) only from the roll to the end of the push-pull.

## How the manoeuvre runs

| State | Who flies | What happens |
|---|---|---|
| APPROACH | Guided (`set_target_posvelaccel_NED`) | low line toward the gate at `KNF_SPEED`, arms open, then fold |
| POP | Guided | short climb that banks the vertical speed the unpowered coast will lose; ends `KNF_POP_END` before the roll with a free-fall target so the motors are already throttled down |
| ROLL | script, raw outputs | roll right to 90° (positive roll, deck to the east); reversible push-pull or a timed bang-bang (`KNF_RI_*`) |
| STOP | script | all four outputs 1500: the ESCs brake the props to 0 rpm (AM32 "brake on stop") |
| PUSHPULL | script | tail clear: one side forward, the other reverse, lift blended back over the last 60° |
| LEVEL | Guided | outputs released, velocity target arrests the drop, arms open |

Trigger: Guided, armed, `KNF_ENABLE 1`, and the Scripting1 RC switch high. Aborts (back to Guided, hold) when the
override runs longer than `KNF_MAX_T`, or the vehicle leaves Guided or disarms.

## Flight code in the loop

```bash
python tools/flight_sitl.py --trace 1
```

`__SS.luaRun()` in `slipstream.html` loads fengari (Lua 5.3 in the browser), runs `sim_mock.lua` + `knife_edge.lua`
unchanged on the simulator's clock and flies gate C: the script's Guided targets drive the simulator's position
controller, and while it holds the outputs the ESC model takes its signed duty and the body rates follow the
rotors' actual thrust and drag torque (no attitude shortcut). `tools/flight_tune.py` searches the `KNF_*` parameters
(`grid`, `random`, `search`), and `--hw` changes rotor inertia, ESC limits and gate height for what-if runs.
`__SS.luaRig()` flies the same script on a simulated roll rig.

## What the simulator says (November 2026)

The simulator's own knife-edge passes gate C with 25-26 mm to spare, but its attitude model changes thrust
instantly. With the flight script driving the motor model directly, **the knife-edge does not close yet**: the
best settings found overnight clip the slot by 2-6 mm. What decides it:

- **Rotor reversal time.** Taking a rotor from forward to reverse takes about 200 ms on the current hardware
  (2807 1300 KV, 7" tri-blade, rotor inertia 2.7e-5 kg m², 45 A ESC limit; a full brake about 130 ms, a spin-up
  about 140 ms). That is about the whole window between the end of the pop and the slot. Rate feedback either
  overshoots the roll to 100-170° or reaches the slot unfinished.
- **No room to start earlier.** A longer unpowered coast puts the approach line below the floor at gate C's height,
  and a harder pop saturates the motors at low packs.
- **Hidden torques.** A rotor driven into reverse slows faster (45 A drive) than one left to brake (30 A
  regeneration), and a reversed prop makes ~55 % of the thrust, so stopping all four rotors from a push-pull leaves
  a torque that drags the roll back (on the rig: from 87° through level). "Rotors completely stopped" needs the roll
  rate to be zero exactly when the rotors are, which only a controller that knows the rotor speeds can arrange.
- **Rotor-aware control works on the rig.** `KNF_RMODE 1` reads the ESC rpm telemetry and, at every step, predicts
  where the roll would end if it started stopping now (rotor speeds slewing at `KNF_RACC`, braking at `KNF_RBRK`):
  a time-optimal bang-bang that respects the rotors' lag. On the simulated roll rig it rolls to 90° in ~210 ms,
  **holds 87-96° with the rotors stopped** and rolls back level in ~220 ms with 6" props
  (`../rigs/roll_rig/predicted.md`); with 7" props it peaks at 108° and drifts 68-108° while stopped.
- **In flight it still overshoots** (110-160°): the roll starts from pop thrust (~14 k rpm) instead of hover, and by
  the time any counter-torque can act the roll is already committed past 90°. A short symmetric pre-brake
  (`KNF_RI_PRE`) helps only a little.
- **What-if hardware:** raising the gate 0.3 m does not fix it; 60 A ESCs draw more than the 2200 mAh pack can give
  and brown out the 12 V rail; **lighter 6" props (rotor inertia 1.5e-5 kg m²) are the change that matters**.

An overnight bug to know about: test runs used to carry the altitude integrator, rotor speeds and a 12 V brownout
flag from one run into the next (fixed in "Start every run from a clean state"); results before that fix are not
comparable.

## Path to the air

1. **Thrust stand** (`../rigs/thrust_stand`): measure reverse thrust, brake, spin-up and reversal times with the
   flight motor, prop and ESC; `tools/fit_thrust.py --write` and `electronics/apply_feedback.py` put them in the
   simulator. Rerun `flight_sitl.py` and `flight_tune.py`.
2. **Prop choice:** if the measured reversal is near 200 ms, test 6" props on the stand; the simulator wants the
   rotor inertia nearer 1.5e-5 kg m².
3. **Roll rig** (`../rigs/roll_rig`): `KNF_RIG 1`, the roll, stop and push-pull tethered; compare with
   `__SS.luaRig()` until they agree.
4. **Tethered hover** on the 6DoF frame with 3D ESCs (check idle, arming, failsafe behaviour of reversible motors).
5. **Open-air knife-edge** (no gate), then a wide slot, then gate C.

## Known gaps

- Guided's attitude and position controllers keep integrating while the script holds the outputs; on hand-back
  that can kick. The mock does not model it. Watch the first rig and tether logs for it.
- The mock's position controller is the simulator's, not ArduPilot's `AC_PosControl`, so approach and pop tracking
  will differ in detail.
- Roll inertia (0.006 kg m² folded) and the motor and ESC model are estimates until the rigs replace them.
- `KNF_RMODE 1` needs rpm from every ESC (bidirectional DShot, `SERVO_BLH_BDMASK`). Telemetry gives the speed but
  not the direction, so the script tracks each rotor's direction from the commands it sent.
- Not run yet: `tools/flight_robust.py` (noise, gusts, latency, motor spread) needs a setting that passes first.
