"""Run every SX-01 SPICE case, write results.json and waveform plots.

    python run_all.py            # everything (the 12 V buck takes ~7 min)
    python run_all.py --skip-buck
"""
import json, math, os, sys, time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import spice

HERE = os.path.dirname(os.path.abspath(__file__))
PLOTS = os.path.join(HERE, 'plots'); os.makedirs(PLOTS, exist_ok=True)
INK, STEEL, ORANGE, REF, MIST = '#15171a', '#6b7178', '#f26a1b', '#4f6d8f', '#c9ccd1'
plt.rcParams.update({
    'font.family': 'DejaVu Sans Mono', 'font.size': 8.5, 'axes.edgecolor': '#9aa0a6', 'axes.linewidth': 0.8,
    'axes.labelcolor': INK, 'xtick.color': STEEL, 'ytick.color': STEEL, 'axes.grid': True, 'grid.color': '#e6e8eb',
    'grid.linewidth': 0.7, 'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 160, 'savefig.bbox': 'tight',
    'legend.frameon': False, 'legend.fontsize': 8,
})
R = {}


def save(fig, name):
    fig.savefig(os.path.join(PLOTS, name + '.png'), facecolor='white'); plt.close(fig)


# --------------------------------------------------------------- 1. battery, harness, bus capacitance
def battery_bus():
    cases = [('full', 16.40, '1000u', 'Full pack (16.4 V OCV), 1000 µF bulk'),
             ('low', 14.76, '1000u', '20 % pack (14.76 V OCV), 1000 µF bulk'),
             ('low_nocap', 14.76, '1u', '20 % pack, bulk capacitor removed')]
    out, waves = {}, {}
    for key, v, c, label in cases:
        m, w = spice.run('battery_bus.cir', 'bus_' + key, {'vocv': v, 'cbulk': c})
        out[key] = dict(m, label=label, vocv=v); waves[key] = w
    R['battery_bus'] = out
    fig, ax = plt.subplots(2, 1, figsize=(7.2, 4.6), sharex=True, gridspec_kw={'height_ratios': [1.3, 1]})
    for key, col in [('full', INK), ('low', ORANGE), ('low_nocap', REF)]:
        w = waves[key]; t = w['time'] * 1e3
        ax[0].plot(t, w['v(bus)'], color=col, lw=0.9, label=out[key]['label'])
        ax[1].plot(t, w['i(Llead)'], color=col, lw=0.9)
    ax[0].axhline(11.47, color=STEEL, ls='--', lw=0.8); ax[0].text(0.05, 11.6, '12 V rail brownout (from buck sim)', color=STEEL, fontsize=7.5)
    ax[0].set_ylabel('ESC bus voltage [V]'); ax[0].legend(loc='lower left')
    ax[1].set_ylabel('pack current [A]'); ax[1].set_xlabel('time [ms]')
    ax[0].set_title('Hover → take-off surge (4 ESCs ramp to their 45 A limit)', loc='left', fontsize=9, color=INK)
    save(fig, 'bus_surge')
    # zoom on hover ripple
    fig, ax = plt.subplots(figsize=(7.2, 2.4))
    for key, col in [('low', ORANGE), ('low_nocap', REF)]:
        w = waves[key]; t = w['time'] * 1e3; s = (t > 0.6) & (t < 0.8)
        ax.plot(t[s], w['v(bus)'][s], color=col, lw=0.9, label=out[key]['label'])
    ax.set_ylabel('bus voltage [V]'); ax.set_xlabel('time [ms]'); ax.legend(loc='lower left')
    ax.set_title('Hover bus ripple from four interleaved 48 kHz ESCs', loc='left', fontsize=9, color=INK)
    save(fig, 'bus_ripple')


# --------------------------------------------------------------- 2. ESC + BLDC power stage
P_TARGET = 0.0491 * 1087 + 8.68e-3 * 0.7 * 1087   # prop torque at hover x speed + friction (from the flight model)

def esc():
    wm = 1087; te = 2 * math.pi / (wm * 7)
    sweep = []
    for d in [0.60, 0.62, 0.64, 0.66, 0.68, 0.70]:
        m, _ = spice.run('esc_bldc.cir', f'esc_d{int(d*100)}', {'duty': d}, {'TW': 3e-3 - te})
        sweep.append(dict(duty=d, **m))
    # interpolate the duty that delivers the hover power
    ds = np.array([s['duty'] for s in sweep]); ps = np.array([s['pmech'] for s in sweep])
    d_h = float(np.interp(P_TARGET, ps, ds))
    m, w = spice.run('esc_bldc.cir', 'esc_hover', {'duty': round(d_h, 4)}, {'TW': 3e-3 - te})
    pin = -m['ibus'] * 15.8
    hover = dict(m, duty=d_h, pin=pin, eff=m['pmech'] / pin, p_target=P_TARGET)
    # aggressive point: knife-edge pop-up needs ~5.4 N per rotor = 1436 rad/s, on a sagged bus at near-full duty
    wm2 = 1436; te2 = 2 * math.pi / (wm2 * 7)
    m2, w2 = spice.run('esc_bldc.cir', 'esc_pop', {'duty': 0.98, 'wm': wm2, 'vbus': 14.2}, {'TW': 3e-3 - te2})
    pop = dict(m2, duty=0.98, wm=wm2, vbus=14.2, pin=-m2['ibus'] * 14.2, eff=m2['pmech'] / (-m2['ibus'] * 14.2),
               p_need=0.0416e-6 * wm2 ** 3 + 8.68e-3 * 0.7 * wm2)
    # DC-equivalent motor for the flight model: I = (d*Vbus - Ke_eff*w) / R_eff(w), fitted from two duties per speed
    fit = []
    for wf, dd in [(700, (0.42, 0.46)), (1087, (0.62, 0.66)), (1450, (0.86, 0.90))]:
        tf = 2 * math.pi / (wf * 7); P = []
        for d in dd:
            mm, _ = spice.run('esc_bldc.cir', f'fit_{wf}_{int(d*100)}', {'duty': d, 'wm': wf}, {'TW': 3e-3 - tf}); P.append(mm['pmech'])
        slope = (P[1] - P[0]) / (dd[1] - dd[0])
        fit.append(dict(wm=wf, reff=8.68e-3 * wf * 15.8 / slope, keff=(dd[0] - P[0] / slope) * 15.8 / wf, p=P))
    W = np.array([f['wm'] for f in fit]); Rf = np.array([f['reff'] for f in fit])
    k1, k0 = np.polyfit(W, Rf, 1)
    ke_eff = float(np.mean([f['keff'] for f in fit]))
    R['esc'] = dict(sweep=sweep, hover=hover, pop=pop, fit=fit, reff0=float(k0), reff1=float(k1), ke_eff=ke_eff)
    for name, ww, tw, title in [('esc_hover', w, te, f'Hover: 1087 rad/s (10.4k rpm), duty {d_h*100:.1f} %, 15.8 V bus'),
                                 ('esc_pop', w2, te2, 'Knife-edge pop-up: 1436 rad/s (13.7k rpm), duty 98 %, sagged 14.2 V bus')]:
        t = ww['time']; s = t > (3e-3 - 2 * tw)
        tt = (t[s] - t[s][0]) * 1e3
        fig, ax = plt.subplots(3, 1, figsize=(7.2, 5.2), sharex=True, gridspec_kw={'height_ratios': [1.2, 1.2, 0.5]})
        ax[0].plot(tt, ww['v(pa)'][s], color=MIST, lw=0.5, label='phase A terminal (PWM)')
        ax[0].plot(tt, ww['v(n)'][s], color=INK, lw=0.9, label='star point')
        ax[0].set_ylabel('voltage [V]'); ax[0].legend(loc='upper right', ncol=2)
        for k, col in [('i(VsA)', INK), ('i(VsB)', ORANGE), ('i(VsC)', REF)]:
            ax[1].plot(tt, ww[k][s], color=col, lw=0.8, label=k[3])
        ax[1].set_ylabel('phase current [A]'); ax[1].legend(loc='upper right', ncol=3)
        ax[2].step(tt, ww['v(sec)'][s], color=STEEL, lw=0.8, where='post'); ax[2].set_ylabel('sector'); ax[2].set_yticks([0, 2, 4])
        ax[2].set_xlabel('time [ms] (two electrical periods)')
        ax[0].set_title(title, loc='left', fontsize=9, color=INK)
        save(fig, name)
    fig, ax = plt.subplots(figsize=(7.2, 2.5))
    ax.plot(ds * 100, ps, 'o-', color=INK, lw=1, ms=3.5)
    ax.axhline(P_TARGET, color=ORANGE, ls='--', lw=0.9); ax.axvline(d_h * 100, color=ORANGE, ls='--', lw=0.9)
    ax.text(d_h * 100 + 0.1, P_TARGET + 4, f'hover: {d_h*100:.1f} % → {P_TARGET:.0f} W', color=ORANGE, fontsize=7.5)
    ax.set_xlabel('ESC duty [%]'); ax.set_ylabel('shaft power [W]')
    ax.set_title('Duty sweep at hover speed: power is steep in duty because back-EMF nearly balances the bus', loc='left', fontsize=9, color=INK)
    save(fig, 'esc_sweep')


# --------------------------------------------------------------- 3. 12 V buck
def buck():
    m, w = spice.run('buck12.cir', 'buck', timeout=1800)
    R['buck'] = m
    t = w['time'] * 1e3
    fig, ax = plt.subplots(3, 1, figsize=(7.2, 5.4), sharex=True, gridspec_kw={'height_ratios': [1.4, 1, 0.8]})
    ax[0].plot(t, w['v(vin)'], color=STEEL, lw=0.9, label='pack / bus (input)')
    ax[0].plot(t, w['v(out)'], color=INK, lw=0.8, label='12 V rail (output)')
    ax[0].axhline(11.0, color=ORANGE, ls='--', lw=0.8); ax[0].text(0.02, 10.6, 'computer reset threshold 11.0 V', color=ORANGE, fontsize=7.5)
    if 't_brown' in m:
        ax[0].plot([m['t_brown'] * 1e3], [11.0], 'o', color=ORANGE, ms=4)
        ax[0].annotate(f"brownout at Vin = {m['vin_at_brown']:.2f} V", (m['t_brown'] * 1e3, 11.0), (m['t_brown'] * 1e3 - 0.45, 13.4), color=ORANGE, fontsize=7.5, arrowprops=dict(arrowstyle='-', color=ORANGE, lw=0.7))
    ax[0].set_ylabel('voltage [V]'); ax[0].set_ylim(0, 17); ax[0].legend(loc='lower left')
    ax[1].plot(t, w['i(VsL)'], color=INK, lw=0.5); ax[1].set_ylabel('inductor [A]')
    ax[2].plot(t, w['v(dc)'] * 100, color=ORANGE, lw=0.8); ax[2].set_ylabel('duty [%]'); ax[2].set_xlabel('time [ms]')
    ax[0].axvline(0.55, color=STEEL, lw=0.6, ls=':'); ax[0].set_title('Soft-start → vision load step at 0.55 ms (15.7 → 20.2 W) → pack sag through dropout', loc='left', fontsize=9, color=INK)
    save(fig, 'buck')


if __name__ == '__main__':
    t0 = time.time()
    battery_bus(); print('battery/bus done', round(time.time() - t0, 1), 's', flush=True)
    esc(); print('esc done', round(time.time() - t0, 1), 's', flush=True)
    if '--skip-buck' not in sys.argv:
        buck(); print('buck done', round(time.time() - t0, 1), 's', flush=True)
    else:  # reuse the previous buck result (its netlist is unchanged) instead of spending 7 minutes again
        prev = os.path.join(HERE, 'results.json')
        if os.path.exists(prev): R['buck'] = json.load(open(prev)).get('buck')
    json.dump(R, open(os.path.join(HERE, 'results.json'), 'w'), indent=2)
    print(json.dumps(R, indent=1)[:4000])
