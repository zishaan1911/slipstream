# Thrust stand: measure what the knife-edge depends on

The knife-edge lives or dies on how fast a rotor can change thrust. In the flight-code-in-the-loop runs
(`python tools/flight_sitl.py`) a 90° roll in the ~0.3 s before the slot is about one rotor-reversal time, so these
numbers decide whether the manoeuvre is real. The simulator's values are estimates; this test replaces them.

| Quantity | Simulator now | Why it matters |
|---|---|---|
| reverse / forward thrust at the same speed (`kRev`) | 0.55 (guess) | push-pull roll-back torque |
| rotor + prop inertia (`J`) | 2.7e-5 kg m² (estimate) | every spin-up, brake and reversal |
| ESC drive / brake current limit | 45 A / 30 A | how hard a rotor can be slowed or reversed |
| ESC throttle ramp (rise / fall) | 8 / 20 per s | delay before the current limit is even reached |
| time: 13 k rpm forward → 7 k rpm reverse | ~180 ms (simulated) | roll-in overshoot, push-pull lag |
| time: 13 k rpm → stopped, brake on | ~120 ms (simulated) | when the rotors are really stopped in the slot |

## Hardware

- Stand with thrust and torque load cells and rpm, logging at **200 Hz or more** (Tyto Series 1585 or a load cell +
  HX711 + optical tachometer; ESC rpm telemetry over bidirectional DShot also works).
- One flight motor (2807 1300 KV) with a flight prop (7" tri-blade) and the flight ESC on **AM32 firmware**
  (BLHeli_32 is discontinued). In the ESC configurator: **bidirectional (3D) mode on, brake on stop on**, startup and
  current-limit settings as on the airframe.
- Bench supply 16.0 V, 40 A or more (or a charged 4S pack and record its voltage).
- Polycarbonate shield around the prop, stand clamped down, no one in the prop plane. Reversal steps load the motor
  mount in torque both ways: check the screws after each run.

## Sequence (one log file)

PWM in µs, 3D mode: 1500 stopped, above it forward, below it reverse. `tools/fit_thrust.py` expects this order
(`--synthetic` writes an example log in exactly this shape).

1. **Static forward:** 1500, then 1550 → 2000 in 50 µs steps, 3 s each.
2. **Static reverse:** 1500 for 2 s, then 1450 → 1000 in 50 µs steps, 3 s each. Reverse props are noisier: keep
   the shield on.
3. **Steps, three times:** 1800 (1 s) → 1500 (1 s, brake) → 1800 (1 s) → 1200 (1 s, reversal) → 1800 (1 s) → 1500 (1 s).

Export as CSV with columns `time_s, pwm_us, thrust_N, torque_Nm, voltage_V, current_A, rpm` (RCbenchmark / Tyto
column names are recognised as they are). Rpm must be **signed**: negative in reverse. With an optical sensor that
cannot tell direction, flip the sign wherever the PWM is below 1500 before fitting.

## Fit and feed back into the simulator

```bash
python tools/fit_thrust.py stand.csv
```
```bash
python tools/fit_thrust.py stand.csv --write
```
```bash
python electronics/apply_feedback.py
```

The first prints the static fit (`kT`, `kQ`, `kRev`), every measured step time, and the dynamic fit (inertia, ESC
current limits, ramp) made by replaying the simulator's own motor model against the measured rpm. `--write` stores
them in `electronics/motor.json`; `apply_feedback.py` pushes them into `slipstream.html`. Then rerun
`python tools/flight_sitl.py` and `python tools/flight_tune.py` to see whether the knife-edge still closes.

## Pass marks for the knife-edge as designed

From the what-if runs in `flight/README.md`. Measured reversal (13 k → −7 k rpm) and brake (13 k → 0) times are
what to compare first; the README lists what each hardware change bought in simulation.
