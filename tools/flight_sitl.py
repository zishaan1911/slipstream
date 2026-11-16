"""Run flight/knife_edge.lua (the ArduPilot script) against the simulator through gate C, headless.

    python tools/flight_sitl.py                  # 100 / 50 / 20 % packs, summary per run
    python tools/flight_sitl.py --trace 1        # also print the state/roll/output timeline of the 100 % run
    python tools/flight_sitl.py --set KNF_XOFF=-0.09 KNF_APEX=-0.13   # try parameter values
    python tools/flight_sitl.py --hw '{"J": 1.5e-5}'   # what-if hardware (rotor inertia, ESC limits, gate height)

The script runs unchanged in fengari (Lua 5.3) on a mock of the ArduPilot scripting API (flight/sim_mock.lua);
see __SS.luaRun in slipstream.html.
"""
import json, os, sys
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render  # noqa: E402

NAMES = {0: 'IDLE', 1: 'APPROACH', 2: 'POP', 3: 'ROLL', 4: 'STOP', 5: 'PUSHPULL', 6: 'LEVEL', 7: 'DONE', 8: 'ABORT'}


def run(page, soc, params, every=0.01):
    return page.evaluate(f'__SS.luaRun({soc}, {every}, {json.dumps(params)})')


def main():
    params = {}
    if '--set' in sys.argv:
        for kv in sys.argv[sys.argv.index('--set') + 1:]:
            if '=' not in kv or kv.startswith('--'): break
            k, v = kv.split('='); params[k] = float(v)
    srv = render.serve()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True, args=['--ignore-gpu-blocklist', '--use-angle=d3d11'])
        page = render.open_page(browser, 640, 360)
        if '--hw' in sys.argv: print('hardware', page.evaluate(f"__SS.hw({sys.argv[sys.argv.index('--hw') + 1]})"), flush=True)
        for soc in (1, 0.5, 0.2):
            r = run(page, soc, params)
            print(f"pack {int(soc * 100):3d} %  passed={r['passed']}  crashed={r['crashed']}  clearance={r['minClearMM']} mm  "
                  f"min height after slot={r['minY']} m  end={r['phase']}  err={r['err']}", flush=True)
            if r['hit']: print('   hit', r['hit'])
            if soc == 1 and '--trace' in sys.argv:
                print('   messages:', r['msgs'])
                print('   t      state     s      y    roll  M1   M2   M3   M4  | rpm FL FR RL RR')
                for row in r['trace']:
                    t, st, s, y, roll, *rest = row
                    if -1.2 < s < 1.6:
                        print(f"   {t:6.3f} {NAMES.get(st, st):9s} {s:5.2f} {y:6.3f} {int(roll):5d} " + ' '.join(f'{int(v):4d}' for v in rest[:4]) + '  | ' + ' '.join(f'{int(v):6d}' for v in rest[4:]))
        browser.close()
    srv.shutdown()


if __name__ == '__main__':
    main()
