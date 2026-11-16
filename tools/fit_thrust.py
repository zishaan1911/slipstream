"""Fit the simulator's motor and ESC model to a thrust-stand log, and write the result to electronics/motor.json.

    python tools/fit_thrust.py LOG.csv                 # fit and report
    python tools/fit_thrust.py LOG.csv --write         # ... and update electronics/motor.json (then run
                                                       #     electronics/apply_feedback.py to push it into the sim)
    python tools/fit_thrust.py --synthetic OUT.csv     # make a log from the current model (+ noise), to check the
                                                       # pipeline: fitting it must give the model's numbers back

Log columns (CSV, header row): time_s, pwm_us, thrust_N, torque_Nm, voltage_V, current_A, rpm
(rpm mechanical, signed: negative when spinning in reverse). RCbenchmark / Tyto exports are mapped automatically.
Protocol: rigs/thrust_stand/README.md. ESC in 3D (bidirectional) mode: 1500 us stopped, above forward, below reverse.

What it fits
  static holds  -> kT (thrust = kT w^2), kQ (torque = kQ w^2), kRev (reverse/forward thrust at the same speed)
  steps         -> rotor inertia J, ESC current limits (drive, brake), throttle ramp (rise, fall)
                   by replaying the simulator's own motor model (slipstream.html, elecStep) against the measured rpm
"""
import csv, json, math, os, random, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOTOR = os.path.join(ROOT, 'electronics', 'motor.json')
FB = os.path.join(ROOT, 'electronics', 'feedback.json')
TWO_PI = 2 * math.pi
ALIASES = {
    'time_s': ['time_s', 'Time (s)', 'time'],
    'pwm_us': ['pwm_us', 'ESC signal (µs)', 'ESC signal (us)', 'esc_us'],
    'thrust_N': ['thrust_N', 'Thrust (N)'],
    'thrust_kgf': ['Thrust (kgf)'],
    'torque_Nm': ['torque_Nm', 'Torque (N·m)', 'Torque (N.m)'],
    'voltage_V': ['voltage_V', 'Voltage (V)'],
    'current_A': ['current_A', 'Current (A)'],
    'rpm': ['rpm', 'Motor Electrical Speed (RPM)', 'Motor Optical Speed (RPM)'],
}


def model_constants():
    mot = json.load(open(MOTOR)); fb = json.load(open(FB))
    esc = mot.get('esc', {})
    return {'kT': mot['kT'], 'kQ': mot['kQ'], 'kRev': mot.get('k_rev', 0.55), 'J': mot['rotor_inertia'], 'I0': mot['i0'],
            'keEff': fb['ke_eff'], 'reff0': fb['reff0'], 'reff1': fb['reff1'],
            'iLimit': esc.get('i_limit', 45.0), 'iBrake': esc.get('i_brake', 30.0),
            'dutyRise': esc.get('duty_rise', 8.0), 'dutySlew': esc.get('duty_fall', 20.0)}


def simulate(c, t, pwm, volt, w0=0.0):
    """The simulator's ESC + BLDC model (elecStep) driven open-loop by the logged throttle: rotor speed [rad/s]."""
    out, w, d = [], w0, (pwm[0] - 1500) / 500
    for k in range(len(t)):
        if k:
            h_total = t[k] - t[k - 1]
            n = max(1, int(h_total / 0.0005)); h = h_total / n
            target = (pwm[k - 1] - 1500) / 500
            for _ in range(n):
                rate = c['dutyRise'] if abs(target) > abs(d) and target * d >= 0 else c['dutySlew']
                d = min(max(target, d - rate * h), d + rate * h)
                R = c['reff0'] + c['reff1'] * abs(w)
                lo, hi = (-c['iLimit'], c['iBrake']) if d < 0 else (-c['iBrake'], c['iLimit'])
                I = min(max((d * volt[k] - c['keEff'] * w) / R, lo), hi)
                tq = c['keEff'] * I - c['kQ'] * w * abs(w) - c['keEff'] * c['I0'] * (math.copysign(1, w) if abs(w) > 1 else 0)
                w += tq / c['J'] * h
        out.append(w)
    return out


def read_log(path):
    rows = list(csv.DictReader(open(path, encoding='utf-8-sig')))
    cols = {}
    for key, names in ALIASES.items():
        for n in names:
            if rows and n in rows[0]: cols[key] = n; break
    need = ['time_s', 'pwm_us', 'rpm', 'voltage_V']
    miss = [k for k in need if k not in cols]
    if miss: sys.exit(f'log is missing columns: {miss} (have {list(rows[0]) if rows else []})')
    g = lambda r, k: float(r[cols[k]]) if k in cols and r[cols[k]] not in ('', None) else float('nan')
    data = {k: [g(r, k) for r in rows] for k in ALIASES}
    if 'thrust_N' not in cols and 'thrust_kgf' in cols: data['thrust_N'] = [v * 9.80665 for v in data['thrust_kgf']]
    return data


def segments(t, pwm, min_hold):
    segs, i = [], 0
    while i < len(t):
        j = i
        while j + 1 < len(t) and abs(pwm[j + 1] - pwm[i]) < 2: j += 1
        if t[j] - t[i] >= min_hold: segs.append((i, j))
        i = j + 1
    return segs


def fit_static(d):
    t, pwm, rpm = d['time_s'], d['pwm_us'], d['rpm']
    fw, rv = [], []
    for i, j in segments(t, pwm, 2.0):   # mean over the last second of every hold of 2 s or more
        idx = [k for k in range(i, j + 1) if t[k] >= t[j] - 1.0]
        w = sum(rpm[k] for k in idx) / len(idx) * TWO_PI / 60
        T = sum(d['thrust_N'][k] for k in idx) / len(idx)
        Q = sum(d['torque_Nm'][k] for k in idx) / len(idx)
        if abs(w) < 100 or math.isnan(T): continue
        (fw if pwm[i] > 1500 else rv).append((w * w, abs(T), abs(Q)))
    def lsq(pts, k):   # least squares through the origin: y = c * w^2
        pts = [p for p in pts if not math.isnan(p[k])]
        return sum(p[0] * p[k] for p in pts) / sum(p[0] * p[0] for p in pts) if pts else float('nan')
    kT, kQ, kTr = lsq(fw, 1), lsq(fw, 2), lsq(rv, 1)
    return {'kT': kT, 'kQ': kQ, 'kRev': kTr / kT if rv and fw else float('nan'), 'n_fwd': len(fw), 'n_rev': len(rv)}


def nelder_mead(f, x0, step, iters=300):
    n = len(x0); pts = [list(x0)] + [[x0[j] + (step[j] if j == i else 0) for j in range(n)] for i in range(n)]
    vals = [f(p) for p in pts]
    for _ in range(iters):
        order = sorted(range(n + 1), key=lambda i: vals[i]); pts = [pts[i] for i in order]; vals = [vals[i] for i in order]
        cen = [sum(p[j] for p in pts[:-1]) / n for j in range(n)]
        ref = [cen[j] + (cen[j] - pts[-1][j]) for j in range(n)]; fr = f(ref)
        if fr < vals[0]:
            exp = [cen[j] + 2 * (cen[j] - pts[-1][j]) for j in range(n)]; fe = f(exp)
            pts[-1], vals[-1] = (exp, fe) if fe < fr else (ref, fr)
        elif fr < vals[-2]: pts[-1], vals[-1] = ref, fr
        else:
            con = [cen[j] + 0.5 * (pts[-1][j] - cen[j]) for j in range(n)]; fc = f(con)
            if fc < vals[-1]: pts[-1], vals[-1] = con, fc
            else:
                for i in range(1, n + 1):
                    pts[i] = [pts[0][j] + 0.5 * (pts[i][j] - pts[0][j]) for j in range(n)]; vals[i] = f(pts[i])
    return pts[0], vals[0]


def fit_dynamic(d, c):
    t, pwm, volt = d['time_s'], d['pwm_us'], d['voltage_V']
    w_meas = [r * TWO_PI / 60 for r in d['rpm']]
    keys = ['J', 'iLimit', 'iBrake', 'dutyRise', 'dutySlew']
    x0 = [c[k] for k in keys]; scale = [abs(v) for v in x0]

    def err(xn):
        cc = dict(c, **{k: max(1e-9, xn[i] * scale[i]) for i, k in enumerate(keys)})
        sim = simulate(cc, t, pwm, volt, w_meas[0])
        return sum((a - b) ** 2 for a, b in zip(sim, w_meas)) / len(t)
    best, e = nelder_mead(err, [1.0] * len(keys), [0.25] * len(keys))
    fitted = {k: best[i] * scale[i] for i, k in enumerate(keys)}
    return fitted, math.sqrt(e) * 60 / TWO_PI


def step_times(d):
    """Measured time from each throttle step to 90 % of the way to the new speed (reversal, brake, spin-up)."""
    t, pwm, rpm = d['time_s'], d['pwm_us'], d['rpm']
    out = []
    for i, j in segments(t, pwm, 0.5):
        if i == 0: continue
        w0, w1 = rpm[i - 1], sum(rpm[k] for k in range(max(i, j - 20), j + 1)) / len(range(max(i, j - 20), j + 1))
        if abs(w1 - w0) < 1000: continue
        goal = w0 + 0.9 * (w1 - w0)
        k = next((k for k in range(i, j + 1) if (rpm[k] - goal) * (w1 - w0) >= 0), None)
        if k is None: continue
        kind = 'reversal' if w0 * w1 < 0 else ('brake' if abs(w1) < 300 else ('spin-up' if abs(w1) > abs(w0) else 'slow-down'))
        out.append((kind, round(w0), round(w1), round((t[k] - t[i]) * 1000)))
    return out


PROTOCOL = [(1500, 2.0)] + [(1500 + s, 3.0) for s in range(50, 501, 50)] + [(1500, 2.0)] + \
           [(1500 - s, 3.0) for s in range(50, 501, 50)] + [(1500, 2.0)] + \
           [(1800, 1.0), (1500, 1.0), (1800, 1.0), (1200, 1.0), (1800, 1.0), (1500, 1.0)] * 3


def synthetic(path, noise=0.01, rate=500):
    c = model_constants()
    t, pwm, tt = [], [], 0.0
    for p, hold in PROTOCOL:
        for _ in range(int(hold * rate)): t.append(tt); pwm.append(p); tt += 1 / rate
    volt = [16.0] * len(t)
    w = simulate(c, t, pwm, volt)
    rnd = random.Random(1)
    with open(path, 'w', newline='') as f:
        wr = csv.writer(f); wr.writerow(['time_s', 'pwm_us', 'thrust_N', 'torque_Nm', 'voltage_V', 'current_A', 'rpm'])
        for k in range(len(t)):
            T = c['kT'] * w[k] * abs(w[k]) * (1 if w[k] >= 0 else c['kRev'])
            Q = c['kQ'] * w[k] * abs(w[k])
            n = lambda v: v * (1 + noise * rnd.gauss(0, 1))
            wr.writerow([f'{t[k]:.4f}', pwm[k], f'{n(T):.4f}', f'{n(Q):.5f}', f'{volt[k]:.2f}', '', f'{n(w[k] * 60 / TWO_PI):.1f}'])
    print('wrote', path, len(t), 'rows from the current model:', {k: c[k] for k in ('kT', 'kQ', 'kRev', 'J', 'iLimit', 'iBrake', 'dutyRise', 'dutySlew')})


def main():
    if '--synthetic' in sys.argv: return synthetic(sys.argv[sys.argv.index('--synthetic') + 1])
    d = read_log(sys.argv[1]); c = model_constants()
    st = fit_static(d)
    print(f"static   kT {st['kT']:.4g} N/(rad/s)^2   kQ {st['kQ']:.4g} N m/(rad/s)^2   kRev {st['kRev']:.3f}   "
          f"({st['n_fwd']} forward, {st['n_rev']} reverse holds)   model: kT {c['kT']:.4g}, kQ {c['kQ']:.4g}, kRev {c['kRev']}")
    for k in ('kT', 'kQ', 'kRev'):
        if not math.isnan(st[k]): c[k] = st[k]
    print('steps    (kind, rpm from, rpm to, ms to 90 %):')
    for s in step_times(d): print('         ', s)
    dyn, rms = fit_dynamic(d, c)
    print(f"dynamic  J {dyn['J']:.3g} kg m^2   ESC drive {dyn['iLimit']:.1f} A   brake {dyn['iBrake']:.1f} A   "
          f"ramp rise {dyn['dutyRise']:.1f}/s   fall {dyn['dutySlew']:.1f}/s   (rpm rms error {rms:.0f})")
    if '--write' in sys.argv:
        mot = json.load(open(MOTOR))
        mot.update({'kT': round(c['kT'], 10), 'kQ': round(c['kQ'], 12), 'k_rev': round(c['kRev'], 3), 'rotor_inertia': round(dyn['J'], 8),
                    'esc': {'i_limit': round(dyn['iLimit'], 1), 'i_brake': round(dyn['iBrake'], 1),
                            'duty_rise': round(dyn['dutyRise'], 2), 'duty_fall': round(dyn['dutySlew'], 2),
                            'source': 'fit_thrust.py ' + os.path.basename(sys.argv[1])}})
        with open(MOTOR, 'w', newline='\n') as f: json.dump(mot, f, indent=2); f.write('\n')
        print('updated', MOTOR, '-> now run: python electronics/apply_feedback.py')


if __name__ == '__main__':
    main()
