"""Predict what the roll rig will record: flight/knife_edge.lua with KNF_RIG = 1 on a simulated rig (only roll free).

    python tools/rig_predict.py          # -> rigs/roll_rig/predicted.md (+ .csv per case)

Cases: the flight hardware (7" props) and lighter 6" props, each with the rotor-aware roll (KNF_RMODE 1) calibrated
on the simulated rig. Compare the real rig's encoder roll, gyro rate and ESC rpm with these.
"""
import csv, json, os, sys
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render  # noqa: E402

CASES = [
    ('7in', '7" tri-blade (as built, rotor inertia 2.7e-5 kg m²)', None, {'KNF_RMODE': 1, 'KNF_RACC': 4500, 'KNF_RBRK': 3000}),
    ('6in', '6" props (rotor inertia 1.5e-5 kg m²)', {'J': 1.5e-5}, {'KNF_RMODE': 1, 'KNF_RACC': 10000, 'KNF_RBRK': 6500}),
]
STATE = {0: 'IDLE', 3: 'ROLL', 4: 'STOP', 5: 'PUSHPULL', 6: 'LEVEL', 7: 'DONE', 8: 'ABORT'}


def main():
    out_dir = os.path.join(render.ROOT, 'rigs', 'roll_rig')
    md = ['# Roll rig: predicted traces', '',
          'What `flight/knife_edge.lua` should do on the roll rig (`KNF_RIG 1`, switch at t = 0, hover throttle before it),',
          'from `__SS.luaRig()`: the same script on the simulator\'s motor and ESC model with only the roll axis free.',
          'Regenerate with `python tools/rig_predict.py` after the thrust stand has updated the model.', '']
    srv = render.serve()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True, args=['--ignore-gpu-blocklist', '--use-angle=d3d11'])
        page = render.open_page(browser, 640, 360)
        for key, label, hw, params in CASES:
            page.evaluate(f'__SS.hw({json.dumps(hw)})')
            r = page.evaluate(f'__SS.luaRig({json.dumps(params)}, 1.4, 0.005)')
            tr = r['trace']
            with open(os.path.join(out_dir, f'predicted_{key}.csv'), 'w', newline='') as f:
                w = csv.writer(f); w.writerow(['t_s', 'state', 'roll_deg', 'roll_rate_rad_s', 'rpm_FL', 'rpm_FR', 'rpm_RL', 'rpm_RR', 'pwm_M1', 'pwm_M2', 'pwm_M3', 'pwm_M4'])
                for row in tr: w.writerow([row[0], STATE.get(row[1], row[1])] + row[2:])
            t_of = lambda st: next((x[0] for x in tr if x[1] == st), None)
            rolling = [x for x in tr if x[1] in (3, 4)]
            stop = [x for x in tr if x[1] == 4]
            level = [x for x in tr if x[1] == 6]
            settle = next((x[0] for x in level if all(abs(y[2]) < 3 for y in level if y[0] >= x[0])), None)
            md += [f'## {label}', '', f'Parameters: `{json.dumps(params)}`', '',
                   '| Milestone | Predicted |', '|---|---|',
                   f'| roll-in: 0 → stop decision | {(t_of(4) - t_of(3)) * 1000:.0f} ms |' if t_of(4) and t_of(3) else '| roll-in | did not reach STOP |',
                   f'| peak roll | {max(x[2] for x in rolling):.0f}° |' if rolling else '| peak roll | - |',
                   f'| roll while the rotors are stopped | {min(x[2] for x in stop):.0f}° to {max(x[2] for x in stop):.0f}° |' if stop else '| stopped | - |',
                   f'| push-pull: start → level hand-over | {(t_of(6) - t_of(5)) * 1000:.0f} ms |' if t_of(6) and t_of(5) else '| push-pull | did not hand over |',
                   f'| settled within ±3° | {settle:.2f} s after the switch |' if settle else '| settled within ±3° | - |',
                   '', f'Script messages: {", ".join(m[1] for m in r["msgs"][1:])}', '',
                   '| t [s] | state | roll [°] | rate [rad/s] | rpm FL | FR | RL | RR |', '|---|---|---|---|---|---|---|---|']
            for row in tr[::8]:
                md.append(f'| {row[0]:.3f} | {STATE.get(row[1], row[1])} | {row[2]:.1f} | {row[3]:.2f} | ' + ' | '.join(str(int(v)) for v in row[4:8]) + ' |')
            md += ['', f'Full trace: `predicted_{key}.csv` (5 ms).', '']
        page.evaluate('__SS.hw(null)')
        browser.close()
    srv.shutdown()
    open(os.path.join(out_dir, 'predicted.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')
    print('wrote', os.path.join(out_dir, 'predicted.md'))


if __name__ == '__main__':
    main()
