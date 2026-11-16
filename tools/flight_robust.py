"""Robustness of the knife-edge flight script: fly it many times through gate C with random disturbances.

    python tools/flight_robust.py 200 --hw '{"J": 1.5e-5}' --set KNF_X=v ...    # 200 draws, report + JSON

Each draw (seeded, so a run repeats): pack charge 20-100 %, per-motor thrust +-3 %, reverse thrust +-15 %, gyro noise
0.02 rad/s, attitude noise 0.3 deg and bias +-1 deg, a sideways gust of up to +-1 m/s^2 near the gate, ESC command
latency 0-6 ms and all-up mass +-3 %. Reports the pass rate, the clearance spread and how the failures happened.
"""
import json, os, random, sys
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render  # noqa: E402

STATE = {3: 'ROLL', 4: 'STOP', 5: 'PUSHPULL', 6: 'LEVEL', 7: 'DONE', 8: 'ABORT', 2: 'POP', 1: 'APPROACH'}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 100
    params = {}
    if '--set' in sys.argv:
        for kv in sys.argv[sys.argv.index('--set') + 1:]:
            if '=' not in kv or kv.startswith('--'): break
            k, v = kv.split('='); params[k] = float(v)
    hw = sys.argv[sys.argv.index('--hw') + 1] if '--hw' in sys.argv else 'null'
    rnd = random.Random(42)
    srv = render.serve()
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True, args=['--ignore-gpu-blocklist', '--use-angle=d3d11'])
        page = render.open_page(browser, 640, 360)
        page.evaluate(f'__SS.hw({hw})')
        mass0 = page.evaluate('__SS.mass()')
        for k in range(n):
            d = {'soc': round(rnd.uniform(0.2, 1.0), 3), 'kT': [round(rnd.gauss(1, 0.03), 4) for _ in range(4)],
                 'kRev': round(rnd.uniform(0.85, 1.15), 3), 'gyroN': 0.02, 'attN': 0.005, 'rollBias': round(rnd.uniform(-1, 1) * 0.01745, 4),
                 'gust': round(rnd.uniform(-1, 1), 3), 'lat': round(rnd.uniform(0, 0.006), 4), 'mass': round(mass0 * rnd.uniform(0.97, 1.03), 4)}
            pert = {kk: d[kk] for kk in ('kT', 'kRev', 'gyroN', 'attN', 'rollBias', 'gust', 'lat')}
            page.evaluate(f"__SS.perturb({json.dumps(pert)}, {k + 1}); __SS.mass({d['mass']})")
            r = page.evaluate(f"__SS.luaRun({d['soc']}, 0.01, {json.dumps(params)})")
            stopped = next((x for x in r['trace'] if x[1] == 4), None)
            at_hit = None
            if r['hit']:
                st = [x[1] for x in r['trace'] if abs(x[2] - r['hit']['s']) < 0.03]
                at_hit = STATE.get(st[-1], st[-1]) if st else None
            edges = r['hit']['edges'] if r['hit'] else None
            side = None
            if edges: side = ['left', 'right', 'bottom', 'top'][min(range(4), key=lambda i: edges[i])]
            results.append({'draw': d, 'passed': r['passed'], 'crashed': r['crashed'], 'clr': r['minClearMM'] if r['passed'] else None,
                            'minY': r['minY'], 'hit_edge': side, 'hit_state': at_hit, 'stopped_before_slot': bool(stopped and stopped[2] > 0)})
            if (k + 1) % 25 == 0:
                ok = sum(x['passed'] for x in results); print(f'{k + 1}/{n}: {ok} passed', flush=True)
        page.evaluate('__SS.perturb(null)'); page.evaluate(f'__SS.mass({mass0})')
        browser.close()
    srv.shutdown()
    ok = [x for x in results if x['passed']]
    print(f'\npassed {len(ok)} of {n} ({100 * len(ok) / n:.0f} %)')
    if ok:
        c = sorted(x['clr'] for x in ok)
        print(f"clearance when it passed: min {c[0]} mm, median {c[len(c) // 2]} mm, max {c[-1]} mm; "
              f"lowest point after the slot {min(x['minY'] for x in ok):.2f} m")
    fails = {}
    for x in results:
        if not x['passed']:
            key = f"{x['hit_edge'] or 'no gate contact'} edge during {x['hit_state'] or '?'}"
            fails[key] = fails.get(key, 0) + 1
    for k, v in sorted(fails.items(), key=lambda kv: -kv[1]): print(f'  {v:4d}  {k}')
    for key, lo, hi in (('soc', 0.2, 0.6), ('soc', 0.6, 1.01)):
        sub = [x for x in results if lo <= x['draw'][key] < hi]
        if sub: print(f"  pack {int(lo * 100)}-{int(min(hi, 1) * 100)} %: {sum(x['passed'] for x in sub)} of {len(sub)} passed")
    out = os.path.join(render.ROOT, 'flight', 'robustness.json')
    json.dump({'params': params, 'hw': json.loads(hw) if hw != 'null' else None, 'n': n, 'results': results}, open(out, 'w'), indent=1)
    print('->', out)


if __name__ == '__main__':
    main()
