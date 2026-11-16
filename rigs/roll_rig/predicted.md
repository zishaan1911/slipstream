# Roll rig: predicted traces

What `flight/knife_edge.lua` should do on the roll rig (`KNF_RIG 1`, switch at t = 0, hover throttle before it),
from `__SS.luaRig()`: the same script on the simulator's motor and ESC model with only the roll axis free.
Regenerate with `python tools/rig_predict.py` after the thrust stand has updated the model.

## 7" tri-blade (as built, rotor inertia 2.7e-5 kg m²)

Parameters: `{"KNF_RMODE": 1, "KNF_RACC": 4500, "KNF_RBRK": 3000}`

| Milestone | Predicted |
|---|---|
| roll-in: 0 → stop decision | 200 ms |
| peak roll | 108° |
| roll while the rotors are stopped | 68° to 108° |
| push-pull: start → level hand-over | 258 ms |
| settled within ±3° | 1.03 s after the switch |

Script messages: KNF ROLL, KNF counter: roll 4 p 3.1 wl 1387 wr 564 -> 114, KNF brake: roll 64 p 9.3 wl 275 wr 1026 -> 87 p -1.6, KNF STOP, KNF PUSHPULL, KNF counter: roll 114 p -1.2 wl -866 wr 866 -> -11, KNF brake: roll 59 p -5.3 wl 717 wr -717 -> 48 p 0.6, KNF LEVEL

| t [s] | state | roll [°] | rate [rad/s] | rpm FL | FR | RL | RR |
|---|---|---|---|---|---|---|---|
| 0.004 | ROLL | 0.0 | 0.00 | 10983 | 10983 | 10983 | 10983 |
| 0.071 | ROLL | 2.7 | 2.18 | 12819 | 6439 | 12801 | 6354 |
| 0.138 | ROLL | 28.3 | 10.34 | 9741 | 4837 | 9732 | 4808 |
| 0.204 | STOP | 67.8 | 8.47 | 1660 | 10223 | 1653 | 10198 |
| 0.271 | STOP | 87.2 | 3.00 | -2 | 5743 | -2 | 5717 |
| 0.338 | STOP | 95.9 | 2.02 | 0 | 812 | 0 | 799 |
| 0.404 | STOP | 103.5 | 1.94 | 0 | 2 | 0 | 2 |
| 0.471 | PUSHPULL | 110.7 | 1.85 | -1483 | 1483 | -1483 | 1483 |
| 0.537 | PUSHPULL | 114.4 | -0.78 | -7906 | 7906 | -7906 | 7906 |
| 0.604 | PUSHPULL | 97.4 | -6.75 | -4222 | 4222 | -4222 | 4222 |
| 0.671 | PUSHPULL | 70.9 | -6.73 | 3321 | -3321 | 3321 | -3321 |
| 0.737 | LEVEL | 52.5 | -3.04 | 10081 | -10081 | 10081 | -10081 |
| 0.804 | LEVEL | 25.2 | -8.35 | 8731 | -6261 | 8722 | -6261 |
| 0.871 | LEVEL | 0.4 | -4.29 | 11790 | 1460 | 11778 | 1460 |
| 0.937 | LEVEL | -6.9 | -0.21 | 12549 | 7883 | 12535 | 7887 |
| 1.004 | LEVEL | -4.3 | 1.10 | 11599 | 10166 | 11584 | 10172 |
| 1.071 | LEVEL | -0.6 | 0.72 | 10857 | 11069 | 10842 | 11077 |
| 1.137 | LEVEL | 0.9 | 0.12 | 10719 | 11225 | 10705 | 11233 |
| 1.204 | LEVEL | 0.7 | -0.13 | 10860 | 11093 | 10847 | 11102 |
| 1.271 | LEVEL | 0.2 | -0.11 | 10983 | 10972 | 10971 | 10981 |
| 1.337 | LEVEL | -0.1 | -0.03 | 11017 | 10937 | 11006 | 10946 |
| 1.404 | LEVEL | -0.1 | 0.01 | 11003 | 10951 | 10992 | 10960 |

Full trace: `predicted_7in.csv` (5 ms).

## 6" props (rotor inertia 1.5e-5 kg m²)

Parameters: `{"KNF_RMODE": 1, "KNF_RACC": 10000, "KNF_RBRK": 6500}`

| Milestone | Predicted |
|---|---|
| roll-in: 0 → stop decision | 208 ms |
| peak roll | 96° |
| roll while the rotors are stopped | 87° to 96° |
| push-pull: start → level hand-over | 216 ms |
| settled within ±3° | 0.82 s after the switch |

Script messages: KNF ROLL, KNF counter: roll 7 p 5.2 wl 1513 wr 95 -> 101, KNF brake: roll 85 p 8.2 wl -637 wr 1245 -> 93 p -1.5, KNF STOP, KNF PUSHPULL, KNF counter: roll 85 p -4.3 wl -1001 wr 1001 -> -6, KNF brake: roll 24 p -6.5 wl 991 wr -991 -> 15 p 0.5, KNF LEVEL

| t [s] | state | roll [°] | rate [rad/s] | rpm FL | FR | RL | RR |
|---|---|---|---|---|---|---|---|
| 0.004 | IDLE | 0.0 | 0.00 | 10978 | 10978 | 10978 | 10978 |
| 0.071 | ROLL | 2.3 | 2.15 | 13102 | 4888 | 13081 | 4735 |
| 0.138 | ROLL | 32.0 | 12.49 | 10180 | 3350 | 10175 | 3711 |
| 0.204 | ROLL | 79.1 | 9.99 | -3687 | 10599 | -3691 | 10903 |
| 0.271 | STOP | 95.9 | 0.49 | -1299 | 6729 | -1300 | 7062 |
| 0.338 | STOP | 94.9 | -0.39 | 0 | 21 | 0 | 40 |
| 0.404 | STOP | 93.5 | -0.37 | 0 | 0 | 0 | 0 |
| 0.471 | PUSHPULL | 92.1 | -0.36 | 0 | 0 | 0 | 0 |
| 0.537 | PUSHPULL | 89.1 | -2.03 | -7383 | 7383 | -7383 | 7383 |
| 0.604 | PUSHPULL | 65.1 | -9.54 | -4564 | 4564 | -4564 | 4564 |
| 0.671 | PUSHPULL | 29.5 | -7.98 | 7962 | -7962 | 7962 | -7962 |
| 0.737 | LEVEL | 15.8 | -2.42 | 12140 | -12140 | 12140 | -12140 |
| 0.804 | LEVEL | 4.9 | -2.60 | 11317 | 681 | 11301 | 681 |
| 0.871 | LEVEL | -1.5 | -0.87 | 11805 | 9680 | 11790 | 9680 |
| 0.937 | LEVEL | -2.3 | 0.21 | 11402 | 10530 | 11387 | 10532 |
| 1.004 | LEVEL | -1.0 | 0.38 | 10997 | 10961 | 10983 | 10964 |
| 1.071 | LEVEL | 0.1 | 0.17 | 10870 | 11088 | 10858 | 11092 |
| 1.137 | LEVEL | 0.3 | -0.01 | 10911 | 11047 | 10900 | 11052 |
| 1.204 | LEVEL | 0.2 | -0.05 | 10972 | 10986 | 10962 | 10991 |
| 1.271 | LEVEL | 0.0 | -0.03 | 10997 | 10961 | 10987 | 10967 |
| 1.337 | LEVEL | -0.0 | -0.00 | 10994 | 10964 | 10985 | 10969 |
| 1.404 | LEVEL | -0.0 | 0.01 | 10985 | 10972 | 10976 | 10978 |

Full trace: `predicted_6in.csv` (5 ms).

