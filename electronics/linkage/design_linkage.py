"""Fold linkage synthesis for SX-01: servo horn + pushrod + arm lever, one per arm.

Plan view of the front-right arm (three.js body axes: x right, z aft; the other arms mirror it).
The arm swings about a vertical hinge pin H between a = 45 deg (open) and a = 9 deg (folded), where a is
the angle between the arm and the fore-aft axis. A ball stud on an inboard tab of the arm root (the lever,
radius rl at angle psi from the arm axis) is pushed by a rod of fixed length from a ball link on the servo
horn (radius rh about the servo output shaft S). The servo is mounted inverted through a cut-out in the top
plate, so its horn and the rod run in the gap between the carbon plates, just above the arm.

The search maximises the worst-case transmission angle (rod vs. lever and rod vs. horn, 90 deg ideal) and
keeps the servo sweep inside 60..90 deg, subject to packaging: the servo body must sit on the top plate clear
of the depth camera, the battery and the marker pole, and the rod must clear the hinge pin and standoffs.
Writes linkage.json, which the airframe model reads.
"""
import json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plate

HERE = os.path.dirname(os.path.abspath(__file__))
D = math.radians
H = np.array([0.068, -0.070])              # hinge (x, z)
A_OPEN, A_FOLD = D(45), D(9)
ANG = np.linspace(A_FOLD, A_OPEN, 37)

def arm_dir(a):                             # unit vector along the front-right arm
    return np.array([math.sin(a), -math.cos(a)])

def rot(v, t):
    c, s = math.cos(t), math.sin(t); return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1]])

# servo: SG90 form factor, mounted inverted; body 22.8 x 12.4 mm, mounting tabs 32.3 mm, shaft 5.9 mm from the
# body centre along the long axis. Footprint on the top plate (tabs included), in servo axes (u long, v short).
BODY = (0.0323, 0.0124); SHAFT_OFF = 0.0059
PLATE = plate.outline(80)   # narrow spine + hinge lobes (tight packaging for the unibody shell)
KEEP_OUT_TOP = [  # (xmin, xmax, zmin, zmax) above the top plate
    (-0.027, 0.027, -0.142, -0.110),       # compact depth camera and its mount
    (-0.021, 0.021, -0.045, 0.035),        # battery + straps
    (-0.017, 0.017, -0.092, -0.064),       # servo power board
    (-0.034, 0.034, 0.074, 0.124),         # CM4 carrier
]
POSTS = [((0.04, 0.0), 0.0028), ((0.02, -0.02), 0.0028), ((0.03, -0.11), 0.0028), (tuple(H), 0.0045)]

def inside_plate(p, margin=0.002):
    x, z = p; inside = False; n = len(PLATE)
    for i in range(n):
        (x1, z1), (x2, z2) = PLATE[i], PLATE[(i + 1) % n]
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1: inside = not inside
    if not inside: return False
    return abs(x) <= plate.half_width(z) - margin

def footprint(S, g):
    u, v = np.array([math.cos(g), math.sin(g)]), np.array([-math.sin(g), math.cos(g)])
    c = S + u * SHAFT_OFF
    return c, [c + u * su * BODY[0] / 2 + v * sv * BODY[1] / 2 for su in (-1, 1) for sv in (-1, 1)]

def boxes_overlap(corners, box):
    xs, zs = [p[0] for p in corners], [p[1] for p in corners]
    return not (max(xs) < box[0] or min(xs) > box[1] or max(zs) < box[2] or min(zs) > box[3])

def seg_dist(p, a, b):
    ab = b - a; t = np.clip(np.dot(p - a, ab) / max(np.dot(ab, ab), 1e-12), 0, 1); return np.linalg.norm(a + t * ab - p)

def evaluate(rl, psi, S, rh):
    P = np.array([H + rot(arm_dir(a), psi) * rl for a in ANG])
    Pm = H + rot(arm_dir((A_OPEN + A_FOLD) / 2), psi) * rl
    d = np.linalg.norm(Pm - S)
    if d <= rh * 1.5: return None
    L = math.sqrt(d * d - rh * rh)                       # horn perpendicular to the rod at mid-stroke
    betas, tmin = [], 90.0
    base = math.atan2(*(Pm - S)[::-1])
    prev = None
    for k, p in enumerate(P):
        dv = p - S; dist = np.linalg.norm(dv)
        if not (abs(L - rh) < dist < L + rh): return None
        ca = (rh * rh + dist * dist - L * L) / (2 * rh * dist); ang = math.acos(np.clip(ca, -1, 1))
        phi = math.atan2(dv[1], dv[0]); cands = [phi + ang, phi - ang]
        if prev is None:  # pick the branch whose horn is perpendicular-ish at mid-stroke
            ref = base + math.acos(np.clip(rh / d, -1, 1))
            b = min(cands, key=lambda c: abs(math.remainder(c - ref, 2 * math.pi)))
        else:
            b = min(cands, key=lambda c: abs(math.remainder(c - prev, 2 * math.pi)))
        prev = b; betas.append(b)
        hp = S + rh * np.array([math.cos(b), math.sin(b)]); rod = p - hp
        lev = p - H; t1 = math.degrees(math.acos(abs(np.dot(rod, lev)) / (np.linalg.norm(rod) * np.linalg.norm(lev))))
        hrn = hp - S; t2 = math.degrees(math.acos(abs(np.dot(rod, hrn)) / (np.linalg.norm(rod) * np.linalg.norm(hrn))))
        tmin = min(tmin, t1, t2)
        for c, r in POSTS:
            if seg_dist(np.array(c), hp, p) < r + 0.0025: return None
    sweep = abs(math.degrees(math.remainder(betas[-1] - betas[0], 2 * math.pi)))
    mono = np.all(np.diff(np.unwrap(betas)) > 0) or np.all(np.diff(np.unwrap(betas)) < 0)
    if not mono: return None
    return dict(L=L, betas=betas, sweep=sweep, tmin=tmin, P=P)

# packaging first: shaft positions where some servo yaw fits on the plate (yaw does not affect the kinematics)
FEAS = []
for sx in np.arange(0.022, 0.07, 0.002):
    for sz in np.arange(-0.108, -0.030, 0.002):
        S = np.array([sx, sz])
        if np.linalg.norm(S - H) < 0.012: continue
        for g in np.radians(np.arange(0, 180, 15)):
            c, corners = footprint(S, g)
            if not all(inside_plate(p) for p in corners): continue
            if any(boxes_overlap(corners, bx) for bx in KEEP_OUT_TOP): continue
            if any(np.linalg.norm(np.array(pc) - c) < r + 0.007 for pc, r in POSTS[:3]): continue
            FEAS.append((S, g)); break
print('feasible shaft positions', len(FEAS), flush=True)
best = None
for rl in np.arange(0.008, 0.0145, 0.002):
    for psi in np.radians(np.arange(60, 301, 15)):
        for S, g in FEAS[::2]:
            for rh in (0.006, 0.008, 0.010):
                r = evaluate(rl, psi, S, rh)
                if not r or not (60 <= r['sweep'] <= 90): continue
                score = r['tmin'] - 0.15 * abs(r['sweep'] - 75)
                if best is None or score > best[0]:
                    best = (score, dict(rl=rl, psi=psi, S=S, g=g, rh=rh, **r))
    print('rl', round(rl, 4), 'best so far', None if not best else (round(best[0], 1), round(best[1]['tmin'], 1), round(best[1]['sweep'], 1)), flush=True)
# local refinement around the coarse optimum
s0, b0 = best
for rl in np.arange(b0['rl'] - 0.001, b0['rl'] + 0.0011, 0.0005):
    for psi in b0['psi'] + np.radians(np.arange(-10, 10.1, 2.5)):
        for S, g in FEAS:
            if np.linalg.norm(S - b0['S']) > 0.006: continue
            for rh in np.arange(b0['rh'] - 0.001, b0['rh'] + 0.0011, 0.0005):
                r = evaluate(rl, psi, S, rh)
                if not r or not (60 <= r['sweep'] <= 90): continue
                score = r['tmin'] - 0.15 * abs(r['sweep'] - 75)
                if score > best[0]: best = (score, dict(rl=rl, psi=psi, S=S, g=g, rh=rh, **r))
print('refined', round(best[0], 1), flush=True)
s, b = best
# arm mass properties and torque check (see README in this folder)
m_arm = 0.052 + 0.050 + 0.008 + 0.025 + 0.010      # carbon arm, 2806 motor, 7" prop, TPU guard, wiring (kg)
r_cg = 0.17; I = m_arm * r_cg ** 2 + 0.052 * 0.26 ** 2 / 12
t_fold = 0.45; alpha = 4 * (A_OPEN - A_FOLD) / t_fold ** 2
tau_arm = I * alpha                                    # N m at the hinge, bang-bang profile
ratio = math.radians(b['sweep']) / (A_OPEN - A_FOLD)  # servo rad per arm rad (mean mechanical advantage)
worst_ma = math.sin(math.radians(b['tmin'])) ** 2      # crude: both transmission angles at their worst
tau_servo = tau_arm / ratio / worst_ma
out = dict(
    hinge=list(H), lever_r=round(b['rl'], 4), lever_psi_deg=round(math.degrees(b['psi']), 1),
    servo_shaft=[round(v, 4) for v in b['S']], servo_yaw_deg=round(math.degrees(b['g']), 1), horn_r=b['rh'],
    rod_len=round(b['L'], 5), sweep_deg=round(b['sweep'], 1), min_transmission_deg=round(b['tmin'], 1),
    horn_deg_open=round(math.degrees(b['betas'][-1]), 2), horn_deg_fold=round(math.degrees(b['betas'][0]), 2),
    heights=dict(plate_top=0.016, horn=0.0065, rod=0.0055, stud_base=0.0015),
    torque=dict(arm_mass_kg=m_arm, inertia_kgm2=round(I, 6), fold_time_s=t_fold, hinge_torque_Nm=round(tau_arm, 4),
                servo_torque_Nm=round(tau_servo, 4), servo_torque_kgcm=round(tau_servo / 0.0981, 3),
                servo_rated_kgcm=2.5, margin=round(2.5 * 0.0981 / tau_servo, 1)),
)
json.dump(out, open(os.path.join(HERE, 'linkage.json'), 'w', newline='\n'), indent=2)
print(json.dumps(out, indent=2))
