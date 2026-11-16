"""Tune flight/knife_edge.lua parameters by flying the script through gate C in the simulator.

    python tools/flight_tune.py grid KNF_RI_WMAX=6,8,10 KNF_LEAD=0.06,0.1     # every combination, 100 % pack
    python tools/flight_tune.py search KNF_XOFF:0.01 KNF_APEX:0.01 ...         # coordinate search from the
                                                                               # current values, 100/50/20 % packs
    --base KNF_X=v ...   start values      --packs 1,0.5,0.2   packs to score     --rounds 3

Score: the worst clearance over the packs [mm]; a crash scores -1000 + how far it got, so the search can climb out.
A run must also bottom out more than 0.3 m above the floor after the slot.
"""
import itertools, json, os, sys, time
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render  # noqa: E402


def args_after(flag):
    if flag not in sys.argv: return []
    out = []
    for a in sys.argv[sys.argv.index(flag) + 1:]:
        if a.startswith('--'): break
        out.append(a)
    return out


def summarise(r):
    tr = r['trace']
    rolled = [x for x in tr if x[1] in (3, 4)]
    stop = next((x for x in tr if x[1] == 4), None)
    hit = r['hit']
    return {'passed': r['passed'], 'crashed': r['crashed'], 'clr': r['minClearMM'], 'minY': r['minY'], 'hit': (hit['s'], hit['roll'], hit['edges']) if hit else None,
            'maxRoll': max((x[4] for x in rolled), default=None), 'stopS': stop[2] if stop else None, 'err': r['err']}


def score(rs):
    """Worst over the packs of: clearance [mm] if it passed, else how deep it hit the slot edge (negative) -
    continuous across pass and crash, so a search can climb towards a pass."""
    worst = 1e9
    for r in rs:
        if r['err']: return -2000
        if r['crashed'] or not r['passed']:
            v = min(r['hit'][2]) if r['hit'] else -1000
        elif r['minY'] < 0.3: v = -300
        else: v = r['clr']
        worst = min(worst, v)
    return worst


def main():
    mode = sys.argv[1]
    base = {k: float(v) for k, v in (a.split('=') for a in args_after('--base'))}
    packs = [float(x) for x in (args_after('--packs') or ['1,0.5,0.2'])[0].split(',')]
    srv = render.serve()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True, args=['--ignore-gpu-blocklist', '--use-angle=d3d11'])
        page = render.open_page(browser, 640, 360)
        if args_after('--hw'): print('hardware', page.evaluate(f"__SS.hw({args_after('--hw')[0]})"), flush=True)

        def fly(params, pks):
            return [summarise(page.evaluate(f'__SS.luaRun({soc}, 0.01, {json.dumps(params)})')) for soc in pks]

        if mode == 'random':   # KEY=lo:hi ... sample uniformly, screen on the first pack, confirm the best on all packs
            import random
            random.seed(int((args_after('--seed') or ['1'])[0]))
            head = []
            for a in sys.argv[2:]:
                if a.startswith('--'): break
                head.append(a)
            ranges = {k: tuple(float(x) for x in v.split(':')) for k, v in (a.split('=') for a in head)}
            n = int((args_after('--n') or ['200'])[0])
            screened = []
            for i in range(n):
                params = dict(base, **{k: round(random.uniform(lo, hi), 4) for k, (lo, hi) in ranges.items()})
                sc = score(fly(params, packs[:1]))
                screened.append((sc, params))
                if (i + 1) % 25 == 0:
                    top = max(screened, key=lambda x: x[0]); print(f'{i + 1}/{n} best screen {top[0]}', flush=True)
            screened.sort(key=lambda x: -x[0])
            for sc, params in screened[:12]:
                rs = fly(params, packs)
                print('CONFIRM', score(rs), json.dumps(params), [(r['clr'], r['maxRoll'], r['stopS'], r['minY']) for r in rs], flush=True)
        elif mode == 'grid':
            axes = [(k, [float(x) for x in v.split(',')]) for k, v in (a.split('=') for a in sys.argv[2:] if '=' in a and not a.startswith('--'))]
            for combo in itertools.product(*[v for _, v in axes]):
                params = dict(base, **{k: v for (k, _), v in zip(axes, combo)})
                t = time.time(); rs = fly(params, packs)
                print(json.dumps({k: params[k] for k, _ in axes}), score(rs), [(r['clr'], r['maxRoll'], r['stopS'], r['minY'], r['hit']) for r in rs],
                      f'{time.time() - t:.0f}s', flush=True)
        else:
            head = []
            for a in sys.argv[2:]:
                if a.startswith('--'): break
                head.append(a)
            steps = {k: float(v) for k, v in (a.split(':') for a in head)}
            cur = dict(base)
            defaults = page.evaluate('(async () => { const r = await __SS.luaRun(1, 1, {}); return r.params; })()')
            for k in steps: cur.setdefault(k, defaults[k])
            best = score(fly(cur, packs)); print('start', json.dumps(cur), best, flush=True)
            for rnd in range(int((args_after('--rounds') or ['3'])[0])):
                improved = False
                for k, st in steps.items():
                    for sgn in (1, -1):
                        while True:
                            trial = dict(cur, **{k: round(cur[k] + sgn * st, 5)})
                            sc = score(fly(trial, packs))
                            if sc > best:
                                cur, best, improved = trial, sc, True
                                print(f'  {k} -> {cur[k]}  score {best}', flush=True)
                            else:
                                break
                print(f'round {rnd + 1}: score {best}  {json.dumps(cur)}', flush=True)
                if not improved: break
                steps = {k: v / 2 for k, v in steps.items()}
            print('BEST', best, json.dumps(cur))
        browser.close()
    srv.shutdown()


if __name__ == '__main__':
    main()
