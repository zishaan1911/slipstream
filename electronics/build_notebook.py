"""Fill notebook_template.html from spice/results.json and the flight model's own equations."""
import json, math, os
from string import Template

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, 'spice', 'results.json')))

# --- flight-model (SlipStream) equations, same constants as the browser sim
MOT = json.load(open(os.path.join(HERE, 'motor.json')))
Kv, Rm, I0, kT, kQ, Rds = MOT['kv'], MOT['rm_phase_to_phase'], MOT['i0'], MOT['kT'], MOT['kQ'], 0.004
Ke = 60 / (2 * math.pi * Kv); Kt = Ke
w_h = math.sqrt(MOT['all_up_mass_kg'] * 9.81 / 4 / kT); V_h = 15.8
w_pop = math.sqrt(MOT['all_up_mass_kg'] * 9.81 * MOT['pop_g'] / 4 / kT)
rpmk = lambda w: '%.1fk' % (w * 60 / (2 * math.pi) / 1000)
iss = kQ * w_h ** 2 / Kt + I0
d_model = (Ke * w_h + Rm * iss) / V_h
ibus_model = d_model * iss + (iss ** 2 * Rds + 0.15 * iss) / V_h
pmech_model = (kQ * w_h ** 2 + Kt * I0) * w_h
eff_model = pmech_model / (ibus_model * V_h)
pack_hover_model = 4 * ibus_model + (7.4 * 0.48) / (0.86 * V_h) + 15.7 / (0.92 * V_h) + 2.6 / (0.86 * V_h)
R_pack = 4 * 0.0035 + 0.004
bus = R['battery_bus']; esc = R['esc']; buck = R.get('buck') or {}
I_surge = bus['low']['ilead_surge']
vmin_model_low = 14.76 - I_surge * R_pack

def f(x, n=2): return '—' if x is None else f'{x:.{n}f}'
def pct(x, n=1): return '—' if x is None else f'{x*100:.{n}f}'

h = esc['hover']; p = esc['pop']
def verdict(model, spice_v, tol=0.04):
    ok = abs(model - spice_v) <= tol * abs(spice_v)
    return ('v-ok', 'agrees') if ok else ('v-fix', 'corrected')
# max steady thrust per rotor at full duty, before (flat Rm) and after (SPICE-fitted R_eff(w), Ke_eff)
def tmax(vb, r0, r1, ke):
    w = 1500.0
    for _ in range(60):
        Rr = r0 + r1 * w; a = Rr * kQ / Kt; c = Rr * I0 - vb
        w = (-ke + math.sqrt(ke * ke - 4 * a * c)) / (2 * a)
    return kT * w * w
r0, r1, kee = esc['reff0'], esc['reff1'], esc['ke_eff']
reff_h = r0 + r1 * w_h
fit_rows = ''
for x in esc['fit']:
    fit_rows += ('<tr><td class="n">%.0f</td><td class="n">%.1fk</td><td class="n">%.0f</td><td class="n">%.2f</td></tr>'
                 % (x['wm'], x['wm'] * 60 / (2 * math.pi) / 1000, x['reff'] * 1000, x['keff'] * 1000))
v = dict(
    d_model=pct(d_model), d_spice=pct(h['duty']),
    ibus_model=f(ibus_model), ibus_spice=f(-h['ibus']),
    eff_model=pct(eff_model), eff_spice=pct(h['eff']),
    pmech=f(h['p_target'], 1), iph_rms=f(h['iph_rms']), iph_pp=f(h['iph_pp']),
    pack_model=f(pack_hover_model, 1), pack_spice=f(bus['full']['ilead_hover'], 1),
    vmin_model=f(vmin_model_low), vmin_spice=f(bus['low']['vmin_surge']), vavg_spice=f(bus['low']['vavg_surge']),
    isurge=f(I_surge, 0),
    vmin_full=f(bus['full']['vmin_surge']),
    vmin_nocap=f(bus['low_nocap']['vmin_surge']),
    rip_cap=f((bus['low']['vmax_hover'] - bus['low']['vmin_hover']) * 1000, 0),
    rip_nocap=f((bus['low_nocap']['vmax_hover'] - bus['low_nocap']['vmin_hover']) * 1000, 0),
    icap_hover=f(bus['low']['icap_rms_hover'], 1), icap_surge=f(bus['low']['icap_rms_surge'], 1),
    pop_ibus=f(-p['ibus'], 1), pop_iph=f(p['iph_rms'], 1), pop_pm=f(p['pmech'], 0), pop_eff=pct(p['eff']), pop_need=f(p['p_need'], 0),
    vin_brown=f(buck.get('vin_at_brown')), vin_drop=f(buck.get('vin_at_drop')),
    vout_reg=f(buck.get('vout_reg'), 3), vstep=f(buck.get('vout_step_min'), 3),
    vrip=f((buck.get('vout_ripple') or 0) * 1000, 0), ilrip=f(buck.get('il_ripple')),
    reff_model='%.0f' % (Rm * 1000), kv=Kv, motor=MOT['motor'], mass='%.2f' % MOT['all_up_mass_kg'], w_h='%.0f' % w_h, rpm_h=rpmk(w_h), rpm_pop=rpmk(w_pop), reff_spice=f(reff_h * 1000, 0), r0=f(r0 * 1000, 0), r1=f(r1 * 1e6, 1), ke_eff=f(kee * 1000, 2),
    tmax_before=f(tmax(15.5, Rm, 0, Ke)), tmax_after=f(tmax(15.5, r0, r1, kee)),
    reff_fit_rows=fit_rows,
)
for key, m_, s_ in [('duty', d_model, h['duty']), ('ibus', ibus_model, -h['ibus']), ('eff', eff_model, h['eff']),
                     ('pack', pack_hover_model, bus['full']['ilead_hover']), ('vmin', vmin_model_low, bus['low']['vmin_surge'])]:
    v['c_' + key], v['t_' + key] = verdict(m_, s_)
# 12 V rail fit fed back into the browser model: v12 = min(12, a*Vbus + b) through the two SPICE points
if buck.get('vin_at_brown') and buck.get('vin_at_drop'):
    # quasi-static rail for the flight model: the 95 % duty ceiling minus a loss term that puts brownout where SPICE found it
    a = 0.95; b = 11.0 - a * buck['vin_at_brown']
    v['fit'] = f'v12 = min(12, {a:.2f}·Vbus − {-b:.2f} V)'; v['fit_a'] = f'{a:.4f}'; v['fit_b'] = f'{b:.4f}'
else:
    v['fit'] = v['fit_a'] = v['fit_b'] = '—'
json.dump(dict(r12a=float(v['fit_a']), r12b=float(v['fit_b']), reff0=r0, reff1=r1, ke_eff=kee), open(os.path.join(HERE, 'feedback.json'), 'w'), indent=1)
html = Template(open(os.path.join(HERE, 'notebook_template.html'), encoding='utf-8').read()).substitute(v)
open(os.path.join(HERE, 'notebook.html'), 'w', encoding='utf-8').write(html)
print(json.dumps(v, indent=1))
