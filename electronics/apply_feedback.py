"""Copy the SPICE-fitted constants from feedback.json into SlipStream's electrical model.

The flight model keeps one marked line in its EL constants:
    reff0: ..., reff1: ..., keEff: ..., r12a: ..., r12b: ..., // spice-feedback
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
fb = json.load(open(os.path.join(HERE, 'feedback.json')))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'slipstream.html')
src = open(path, encoding='utf-8').read()
line = (f"  reff0: {fb['reff0']:.5f}, reff1: {fb['reff1']:.4e}, keEff: {fb['ke_eff']:.5e}, "
        f"r12a: {fb['r12a']:.4f}, r12b: {fb['r12b']:.4f}, // spice-feedback (electronics/feedback.json)")
src, n = re.subn(r'^  reff0: .*// spice-feedback.*$', line, src, flags=re.M)
if n != 1:
    raise SystemExit('marker line not found in slipstream.html')
mot = json.load(open(os.path.join(HERE, 'motor.json')))
mline = (f"  Kv: {mot['kv']}, Rm: {mot['rm_phase_to_phase']}, I0: {mot['i0']}, J: {mot['rotor_inertia']}, kT: {mot['kT']}, kQ: {mot['kQ']}, "
         f"// motor-feedback (electronics/motor.json: {mot['motor']})")
src, n = re.subn(r'^  Kv: .*// motor-feedback.*$', mline, src, flags=re.M)
if n != 1: raise SystemExit('motor line not found in slipstream.html')
src, n = re.subn(r'^let MASS = [0-9.]+;', f"let MASS = {mot['all_up_mass_kg']};", src, flags=re.M)
if n != 1: raise SystemExit('MASS line not found in slipstream.html')
open(path, 'w', encoding='utf-8', newline='\n').write(src)
print(line.strip()); print(mline.strip())
