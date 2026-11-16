"""Landing-leg retraction driven by the arm fold (no extra actuator), front-right arm; the others mirror it.

Each leg hangs from a hinge under its arm shell (axis across the arm) and carries a short horn. A rod runs from
a fixed anchor under the body to that horn. When the fold servo swings the arm in about its vertical hinge, the
horn is carried round with it, the rod's fixed length forces the leg to pitch up, and the leg ends up stowed
flat under the arm. Opening the arms deploys the legs again. This is a spatial RSSR linkage.

Arm-local frame (as the airframe model): x across the arm, y up, z along the arm (negative = outboard), origin
on the hinge axis. Leg pitch psi = 0 hangs straight down; positive swings the foot outboard.
Writes legs.json, which the harness data (and so the airframe model) reads.
"""
import json, math, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
D = math.radians
H3 = np.array([0.068, 0.0, -0.070])          # fold hinge, body frame
A_OPEN, A_FOLD = D(45), D(9)
P0 = np.array([0.0, -0.017, -0.085])         # leg hinge, arm-local
LEG = 0.128                                  # hinge to foot tip
PSI_DEP, PSI_STOW = D(20), D(87)


def Ry(t):
    c, s = math.cos(t), math.sin(t); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def to_body(a, p):                           # front-right arm: the pivot is rotated by -a
    return H3 + Ry(-a) @ p


def horn(psi, rh, dl):
    return np.array([0.0, -math.cos(psi + dl), -math.sin(psi + dl)]) * rh


PSI = np.radians(np.linspace(-30, 140, 1361))


def solve_psi(a, rh, dl, B, L, guess):
    hd = np.stack([np.zeros_like(PSI), -np.cos(PSI + dl), -np.sin(PSI + dl)], 1) * rh
    tips = H3 + (P0 + hd) @ Ry(-a).T
    e = np.abs(np.linalg.norm(tips - B, axis=1) - L)
    idx = np.where((e[1:-1] <= e[:-2]) & (e[1:-1] <= e[2:]) & (e[1:-1] < 4e-4))[0] + 1   # roots of the closure error
    if len(idx) == 0: return None
    return PSI[idx[np.argmin(np.abs(PSI[idx] - guess))]]


def evaluate(rh, dl, B, full=True):
    L = np.linalg.norm(to_body(A_OPEN, P0 + horn(PSI_DEP, rh, dl)) - B)
    psis, tmin, guess = [], 90.0, PSI_DEP
    for a in (np.linspace(A_OPEN, A_FOLD, 19) if full else (A_OPEN, (A_OPEN + A_FOLD) / 2, A_FOLD)):
        psi = solve_psi(a, rh, dl, B, L, guess)
        if psi is None: return None
        guess = psi; psis.append(psi)
        rod = to_body(a, P0 + horn(psi, rh, dl)) - B
        tang = Ry(-a) @ np.cross(np.array([1.0, 0, 0]), horn(psi, rh, dl))   # horn tip's direction of travel
        ct = abs(np.dot(rod, tang)) / (np.linalg.norm(rod) * np.linalg.norm(tang) + 1e-12)
        tmin = min(tmin, math.degrees(math.asin(min(1, ct))))
    if np.any(np.diff(psis) <= 0): return None
    return dict(L=L, psis=psis, end=psis[-1], tmin=tmin)


best = None
for rh in (0.008, 0.011, 0.014):
    for dl in np.radians(np.arange(-180, 180, 20)):
        for bx in np.arange(0.035, 0.076, 0.008):
            for by in (-0.03, -0.022):
                for bz in np.arange(-0.115, -0.025, 0.008):
                    B = np.array([bx, by, bz])
                    r = evaluate(rh, dl, B, full=False)
                    if not r or abs(r['end'] - PSI_STOW) > D(8): continue
                    r = evaluate(rh, dl, B)
                    if not r: continue
                    score = -math.degrees(abs(r['end'] - PSI_STOW)) * 3 + min(r['tmin'], 60)
                    if best is None or score > best[0]: best = (score, dict(rh=rh, dl=dl, B=B, **r))
    print('rh', rh, 'best', None if not best else (round(best[0], 1), round(math.degrees(best[1]['end']), 1), round(best[1]['tmin'], 1)), flush=True)

s, b = best
out = dict(
    hinge_local=list(P0), leg_len=LEG, psi_deployed_deg=round(math.degrees(PSI_DEP), 2), psi_stowed_deg=round(math.degrees(b['end']), 2),
    horn_r=b['rh'], horn_offset_deg=round(math.degrees(b['dl']), 2), anchor=[round(v, 4) for v in b['B']], rod_len=round(b['L'], 5),
    min_transmission_deg=round(b['tmin'], 1),
    psi_table_deg=[round(math.degrees(p), 2) for p in b['psis']],   # arm angle 45 -> 9 deg in 2 deg steps
)
json.dump(out, open(os.path.join(HERE, 'legs.json'), 'w', newline='\n'), indent=2)
print(json.dumps(out, indent=2))
