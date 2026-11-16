"""Draw the SX-01 wiring diagram, wire list and fold-linkage plan from harness.json -> harness.html."""
import html, json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, 'harness.json')))
C, W, LK, COL = D['components'], D['cables'], D['linkage'], D['colors']
esc = html.escape

# ---------------------------------------------------------------- block layout (schematic space, px)
BOX = {
    'BAT': (30, 40, 150, 64), 'XT60': (30, 170, 150, 44), 'CAP': (250, 40, 150, 44),
    'ESC': (250, 150, 170, 250), 'FC': (520, 150, 170, 330),
    'HUB': (800, 40, 170, 190), 'BUCK': (800, 262, 170, 56), 'CM4': (1050, 300, 170, 110),
    'CAM': (1300, 290, 140, 50), 'FAN': (1300, 380, 140, 44), 'RX': (800, 470, 170, 70),
    'S1': (1050, 20, 150, 44), 'S2': (1050, 74, 150, 44), 'S3': (1050, 128, 150, 44), 'S4': (1050, 182, 150, 44),
    'M1': (40, 560, 120, 50), 'M2': (190, 560, 120, 50), 'M3': (340, 560, 120, 50), 'M4': (490, 560, 120, 50),
    'LED1': (640, 560, 110, 44), 'LED2': (765, 560, 110, 44), 'LED3': (890, 560, 110, 44), 'LED4': (1015, 560, 110, 44),
}
SIDE = {  # which side of a block each cable leaves from (block, cable) -> L/R/T/B
}
def side_for(cid, other):
    x, y, w, h = BOX[cid]; ox, oy, ow, oh = BOX[other]
    dx = (ox + ow / 2) - (x + w / 2); dy = (oy + oh / 2) - (y + h / 2)
    if cid in ('ESC', 'FC') and other.startswith(('M', 'LED')): return 'B'
    if other in ('ESC', 'FC') and cid.startswith(('M', 'LED')): return 'T'
    return ('R' if dx > 0 else 'L') if abs(dx) * 0.7 >= abs(dy) else ('B' if dy > 0 else 'T')

ends = {}  # (block, side) -> list of (cable index, end)
for i, w in enumerate(W):
    if w['frm'] == w['to']: continue
    for end, me, other in (('a', w['frm'], w['to']), ('b', w['to'], w['frm'])):
        ends.setdefault((me, side_for(me, other)), []).append((i, end, other))

PITCH = 5.0
anchor = {}  # (cable, end) -> (x, y, side, n)
for (cid, sd), lst in ends.items():
    x, y, w, h = BOX[cid]
    lst.sort(key=lambda t: (BOX[t[2]][1] + BOX[t[2]][3] / 2) if sd in 'LR' else (BOX[t[2]][0] + BOX[t[2]][2] / 2))
    widths = [len(W[i]['cores']) * PITCH + 8 for i, _, _ in lst]
    span = (h if sd in 'LR' else w); total = sum(widths); pos = (span - total) / 2
    for (i, end, other), wd in zip(lst, widths):
        c = pos + wd / 2; pos += wd
        if sd == 'L': anchor[(i, end)] = (x, y + c, sd)
        if sd == 'R': anchor[(i, end)] = (x + w, y + c, sd)
        if sd == 'T': anchor[(i, end)] = (x + c, y, sd)
        if sd == 'B': anchor[(i, end)] = (x + c, y + h, sd)

def route(a, b, lane):
    (x1, y1, s1), (x2, y2, s2) = a, b
    out = {'L': (-1, 0), 'R': (1, 0), 'T': (0, -1), 'B': (0, 1)}
    st = 14 + lane * 7
    p1 = (x1 + out[s1][0] * st, y1 + out[s1][1] * st); p2 = (x2 + out[s2][0] * st, y2 + out[s2][1] * st)
    pts = [(x1, y1), p1]
    if s1 in 'LR' and s2 in 'LR':
        mx = (p1[0] + p2[0]) / 2 + (lane - 2) * 6; pts += [(mx, p1[1]), (mx, p2[1])]
    elif s1 in 'TB' and s2 in 'TB':
        my = (p1[1] + p2[1]) / 2 + (lane - 2) * 6; pts += [(p1[0], my), (p2[0], my)]
    elif s1 in 'LR':
        pts += [(p2[0], p1[1])]
    else:
        pts += [(p1[0], p2[1])]
    pts += [p2, (x2, y2)]
    clean = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - clean[-1][0]) > 0.01 or abs(p[1] - clean[-1][1]) > 0.01: clean.append(p)
    return clean

def offset(pts, o):
    res = []
    for k, p in enumerate(pts):
        nx = ny = 0.0
        for q0, q1 in ((pts[k - 1], p) if k > 0 else (None, None), (p, pts[k + 1]) if k < len(pts) - 1 else (None, None)):
            if q0 is None: continue
            dx, dy = q1[0] - q0[0], q1[1] - q0[1]; L = math.hypot(dx, dy) or 1
            n = (-dy / L, dx / L)
            if abs(n[0]) > abs(nx): nx = n[0]
            if abs(n[1]) > abs(ny): ny = n[1]
        res.append((p[0] + nx * o, p[1] + ny * o))
    return res

paths, labels = [], []
lane_of = {}
for i, w in enumerate(W):
    if w['frm'] == w['to']: continue
    key = (w['frm'], w['to']); lane_of[key] = lane_of.get(key, -1) + 1
    a, b = anchor[(i, 'a')], anchor[(i, 'b')]
    pts = route(a, b, (i % 5))
    n = len(w['cores'])
    group = ['<g class="cable" data-id="%s"><title>%s %s: %s to %s, %d AWG, %d mm</title>' % (w['id'], w['id'], esc(w['name']), w['frm'], w['to'], w['awg'], w['length_mm'], )]
    for k, core in enumerate(w['cores']):
        q = offset(pts, (k - (n - 1) / 2) * PITCH)
        d = 'M' + ' L'.join('%.1f %.1f' % p for p in q)
        group.append('<path class="halo" d="%s"/><path class="core" d="%s" style="stroke:%s"/>' % (d, d, COL.get(core['color'], '#888')))
    mid = pts[len(pts) // 2]
    group.append('<text class="cid" x="%.1f" y="%.1f">%s</text></g>' % (mid[0] + 4, mid[1] - 4, w['id']))
    paths.append(''.join(group))
    # pin labels at each end
    for end, (x, y, sd), names in (('a', a, [c['a'] for c in w['cores']]), ('b', b, [c['b'] for c in w['cores']])):
        lab = '/'.join(dict.fromkeys(names)) if n <= 3 else '%d-way' % n
        anchor_txt = {'L': ('end', x - 3, y - 4), 'R': ('start', x + 3, y - 4), 'T': ('middle', x, y - 5), 'B': ('middle', x, y + 12)}[sd]
        labels.append('<text class="pin" text-anchor="%s" x="%.1f" y="%.1f">%s</text>' % (anchor_txt[0], anchor_txt[1], anchor_txt[2], esc(lab)))

blocks = []
for cid, (x, y, w, h) in BOX.items():
    c = C[cid]
    kind = 'pwr' if cid in ('BAT', 'XT60', 'CAP', 'ESC', 'BUCK', 'HUB') else 'act' if cid[0] in 'MS' and cid[1:].isdigit() else 'ctl'
    blocks.append('<g class="blk %s"><rect x="%d" y="%d" width="%d" height="%d" rx="3"/><text class="bid" x="%d" y="%d">%s</text><text class="bname" x="%d" y="%d">%s</text></g>'
                  % (kind, x, y, w, h, x + 8, y + 16, cid, x + 8, y + 30, esc(c['name'])))
# antennas on the receiver
ax, ay, aw, ah = BOX['RX']
ant = ''.join('<path class="ant" d="M%.1f %.1f v-16 m-6 0 l6 -8 l6 8"/>' % (ax + aw - 30 + k * 16, ay) for k in range(2))

SVG = ('<svg class="sch" viewBox="0 0 1460 640" role="img" aria-label="SX-01 wiring diagram">'
       + ''.join(blocks) + ''.join(paths) + ant + ''.join(labels) + '</svg>')

# ---------------------------------------------------------------- linkage plan (front-right arm, to scale)
SC = 4400; ox, oz = 0.042, -0.108
def tp(x, z): return ((x - ox) * SC, (z - oz) * SC)
H = LK['hinge']; S = LK['servo_shaft']
def lever(a):
    dx, dz = math.sin(a), -math.cos(a); psi = math.radians(LK['lever_psi_deg']); c, s = math.cos(psi), math.sin(psi)
    return (H[0] + (c * dx - s * dz) * LK['lever_r'], H[1] + (s * dx + c * dz) * LK['lever_r'])
def horn(a):
    px, pz = lever(a); vx, vz = px - S[0], pz - S[1]; d = math.hypot(vx, vz); rh, L = LK['horn_r'], LK['rod_len']
    k = math.acos(max(-1, min(1, (rh * rh + d * d - L * L) / (2 * rh * d)))); phi = math.atan2(vz, vx)
    f = (a - math.radians(9)) / math.radians(36); ref = math.radians(LK['horn_deg_fold'] + (LK['horn_deg_open'] - LK['horn_deg_fold']) * f)
    b = min((phi + k, phi - k), key=lambda t: abs(math.remainder(t - ref, 2 * math.pi)))
    return (S[0] + rh * math.cos(b), S[1] + rh * math.sin(b))
lk = []
for a, cls in ((math.radians(45), 'open'), (math.radians(9), 'fold')):
    dx, dz = math.sin(a), -math.cos(a)
    e = (H[0] + dx * 0.03, H[1] + dz * 0.03)
    p, hn = lever(a), horn(a)
    lk.append('<g class="lk %s"><path class="armline" d="M%.1f %.1f L%.1f %.1f"/><path class="lev" d="M%.1f %.1f L%.1f %.1f"/>'
              '<path class="rod" d="M%.1f %.1f L%.1f %.1f"/><path class="hrn" d="M%.1f %.1f L%.1f %.1f"/><circle cx="%.1f" cy="%.1f" r="3.2"/><circle cx="%.1f" cy="%.1f" r="3.2"/></g>'
              % (cls, *tp(*H), *tp(*e), *tp(*H), *tp(*p), *tp(*hn), *tp(*p), *tp(*S), *tp(*hn), *tp(*p), *tp(*hn)))
arc = ' L'.join('%.1f %.1f' % tp(*lever(math.radians(9 + 36 * t / 24))) for t in range(25))
LKSVG = ('<svg class="lksvg" viewBox="0 0 240 290" role="img" aria-label="Fold linkage plan view, open and folded">'
         '<path class="trace" d="M%s"/>' % arc
         + ''.join(lk)
         + '<circle class="pivot" cx="%.1f" cy="%.1f" r="5"/><circle class="pivot" cx="%.1f" cy="%.1f" r="5"/>' % (*tp(*H), *tp(*S))
         + '<text class="lkt" x="%.1f" y="%.1f">hinge</text><text class="lkt" x="%.1f" y="%.1f">servo shaft</text>' % (tp(*H)[0] + 9, tp(*H)[1] + 4, tp(*S)[0] - 70, tp(*S)[1] - 8)
         + '<text class="lkt open" x="8" y="18">open 45°</text><text class="lkt fold" x="8" y="34">folded 9°</text>'
         + '<path class="scale" d="M8 278 h44"/><text class="lkt" x="8" y="271">10 mm</text></svg>')

# ---------------------------------------------------------------- wire list
rows = []
for w in W:
    sw = ''.join('<i class="sw" style="background:%s" title="%s"></i>' % (COL.get(c['color'], '#888'), esc(c['net'])) for c in w['cores'])
    nets = ', '.join(dict.fromkeys(c['net'] for c in w['cores']))
    rows.append('<tr><td class="mono">%s</td><td>%s<div class="sub">%s</div></td><td class="mono">%s → %s</td><td class="mono">%s</td><td class="num">%s</td>'
                '<td class="num">%d</td><td class="num">%d</td><td class="num">%s</td><td class="num">%s</td><td class="sub">%s</td></tr>'
                % (w['id'], esc(w['name']), esc(nets), w['frm'], w['to'], sw, len(w['cores']), w['awg'], w['length_mm'],
                   ('%g A' % w['design_A']) if w['design_A'] else '—', ('%.0f mV' % w['drop_mV']) if w['design_A'] >= 0.5 else '—', esc(w['conn'])))
parts = ''.join('<tr><td class="mono">%s</td><td>%s</td><td class="sub">%s</td></tr>' % (k, esc(v['name']), esc(v['part'])) for k, v in C.items())
tot_m = sum(w['length_mm'] * len(w['cores']) for w in W) / 1000
cond = sum(len(w['cores']) for w in W)
T = LK['torque']

PAGE_T = """<title>SX-01 Wiring Harness</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@500;600;700&family=Barlow:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* layout: an engineering drawing sheet: title block strip, the schematic full width, then linkage plan beside the numbers, then the wire list */
:root {
  --paper: #f3f5f7; --sheet: #ffffff; --ink: #18212b; --muted: #5d6874; --rule: #d3d9df; --accent: #e8661c;
  --pwr: #fbe9df; --ctl: #e6eef6; --act: #eaf1e6; --halo: #ffffff;
  --display: "Barlow Semi Condensed", "Arial Narrow", system-ui, sans-serif; --body: "Barlow", system-ui, sans-serif; --mono: "IBM Plex Mono", ui-monospace, Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --paper: #0f1418; --sheet: #161d23; --ink: #e3e8ed; --muted: #95a1ad; --rule: #2b3640; --accent: #f08440;
  --pwr: #3a2418; --ctl: #1b2a38; --act: #1d2c1d; --halo: #a8b2bc; color-scheme: dark } }
:root[data-theme="dark"] {
  --paper: #0f1418; --sheet: #161d23; --ink: #e3e8ed; --muted: #95a1ad; --rule: #2b3640; --accent: #f08440;
  --pwr: #3a2418; --ctl: #1b2a38; --act: #1d2c1d; --halo: #a8b2bc; color-scheme: dark }
body { background: var(--paper); color: var(--ink); font: 15px/1.55 var(--body); }
.wrap { max-width: 1480px; margin: 0 auto; padding-block: 28px 56px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); display: grid; gap: 22px; }
.tb { display: grid; grid-template-columns: 1fr auto; gap: 16px 32px; align-items: end; border-bottom: 2px solid var(--ink); padding-bottom: 14px; }
h1 { font: 700 clamp(28px, 4vw, 44px)/1.05 var(--display); letter-spacing: .01em; margin: 0; text-wrap: balance; }
h1 em { font-style: normal; color: var(--accent); }
.lede { margin: 8px 0 0; color: var(--muted); max-width: 70ch; }
.dwg { font: 12px/1.6 var(--mono); color: var(--muted); text-align: right; white-space: nowrap; }
.dwg b { color: var(--ink); font-weight: 500; }
.stats { display: flex; flex-wrap: wrap; gap: 10px 28px; font: 500 13px var(--mono); color: var(--muted); }
.stats b { font: 600 22px var(--display); color: var(--ink); margin-right: 6px; }
h2 { font: 600 20px/1.2 var(--display); letter-spacing: .02em; margin: 0 0 10px; text-transform: uppercase; }
.panel { background: var(--sheet); border: 1px solid var(--rule); padding: 18px; min-width: 0; }
.scroll { overflow-x: auto; }
.sch { width: 100%; min-width: 1060px; height: auto; display: block; }
.blk rect { stroke: var(--ink); stroke-width: 1.2; }
.blk.pwr rect { fill: var(--pwr); } .blk.ctl rect { fill: var(--ctl); } .blk.act rect { fill: var(--act); }
.bid { font: 600 13px var(--display); fill: var(--ink); letter-spacing: .04em; }
.bname { font: 11px var(--body); fill: var(--muted); }
.halo { fill: none; stroke: var(--halo); stroke-width: 4.2; stroke-linejoin: round; }
.core { fill: none; stroke-width: 2.2; stroke-linejoin: round; stroke-linecap: round; }
.cable:hover .core { stroke-width: 3; }
.cid { font: 500 9.5px var(--mono); fill: var(--muted); }
.pin { font: 9px var(--mono); fill: var(--muted); }
.ant { fill: none; stroke: var(--ink); stroke-width: 1.3; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 18px; margin-top: 12px; font: 12px var(--mono); color: var(--muted); }
.legend i, .sw { display: inline-block; width: 18px; height: 6px; border-radius: 3px; vertical-align: middle; margin-right: 6px; box-shadow: 0 0 0 1px var(--rule); }
.sw { width: 12px; margin-right: 3px; }
.two { display: grid; grid-template-columns: minmax(0, 320px) minmax(0, 1fr); gap: 22px; }
@media (max-width: 760px) { .two { grid-template-columns: 1fr; } .tb { grid-template-columns: 1fr; } .dwg { text-align: left; } }
.lksvg { width: 100%; max-width: 320px; height: auto; display: block; }
.lk path { fill: none; stroke-width: 2.6; stroke-linecap: round; }
.lk.open path { stroke: var(--ink); } .lk.fold path { stroke: var(--accent); }
.lk .armline { stroke-width: 7; opacity: .22; }
.lk circle { fill: var(--sheet); stroke-width: 1.6; } .lk.open circle { stroke: var(--ink); } .lk.fold circle { stroke: var(--accent); }
.trace { fill: none; stroke: var(--muted); stroke-dasharray: 3 3; stroke-width: 1.2; }
.pivot { fill: var(--ink); }
.lkt { font: 11px var(--mono); fill: var(--muted); } .lkt.open { fill: var(--ink); } .lkt.fold { fill: var(--accent); }
.scale { stroke: var(--ink); stroke-width: 2; }
dl { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px 24px; margin: 0; }
dt { font: 12px var(--mono); color: var(--muted); letter-spacing: .03em; }
dd { margin: 2px 0 0; font: 600 20px var(--display); font-variant-numeric: tabular-nums; }
dd small { font: 400 13px var(--body); color: var(--muted); margin-left: 4px; }
.note { color: var(--muted); max-width: 72ch; margin: 14px 0 0; font-size: 14px; }
table { border-collapse: collapse; width: 100%; min-width: 880px; font-size: 13.5px; }
th { text-align: left; font: 600 12px var(--display); letter-spacing: .06em; text-transform: uppercase; color: var(--muted); border-bottom: 1.5px solid var(--ink); padding: 6px 8px; }
td { border-bottom: 1px solid var(--rule); padding: 7px 8px; vertical-align: top; }
.num { text-align: right; font-variant-numeric: tabular-nums; font-family: var(--mono); font-size: 12.5px; white-space: nowrap; }
.mono { font-family: var(--mono); font-size: 12.5px; white-space: nowrap; }
.sub { color: var(--muted); font-size: 12px; }
</style>
<div class="wrap">
  <header class="tb">
    <div>
      <h1>SX-01 <em>wiring harness</em> and fold linkage</h1>
      <p class="lede">Every conductor in the airframe, drawn from the same parts list and netlist that builds the 3D model. Lengths are measured along each cable's routed path in the model, plus 15 mm for termination.</p>
    </div>
    <div class="dwg">DWG <b>SX-01-EL-002</b> · REV <b>B</b><br>SEVENTH AXIS · SLIPSTREAM<br>generated by electronics/harness/harness.py</div>
  </header>
  <div class="stats"><span><b>%(ncomp)d</b>components</span><span><b>%(ncab)d</b>cables</span><span><b>%(ncond)d</b>conductors</span><span><b>%(tot).1f m</b>of wire</span><span><b>%(sweep).0f°</b>servo sweep for 36° of fold</span></div>
  <section class="panel">
    <h2>Wiring diagram</h2>
    <div class="scroll">%(svg)s</div>
    <div class="legend"><span><i style="background:var(--pwr)"></i>power</span><span><i style="background:var(--ctl)"></i>control / compute</span><span><i style="background:var(--act)"></i>actuators</span><span>colour of each line = insulation colour of that core · hover a cable for its gauge and length</span></div>
  </section>
  <section class="two">
    <div class="panel">
      <h2>Fold linkage</h2>
      %(lk)s
      <p class="note">Front-right arm in plan view; the other three mirror it. Black: open. Orange: folded. Dashed: path of the ball stud.</p>
    </div>
    <div class="panel">
      <h2>Linkage numbers</h2>
      <dl>
        <div><dt>servo horn radius</dt><dd>%(rh).1f<small>mm</small></dd></div>
        <div><dt>pushrod length (ball to ball)</dt><dd>%(rod).2f<small>mm</small></dd></div>
        <div><dt>arm lever radius</dt><dd>%(rl).1f<small>mm at %(psi).1f° to the arm</small></dd></div>
        <div><dt>servo shaft from hinge</dt><dd>%(sh).1f<small>mm</small></dd></div>
        <div><dt>servo sweep / arm sweep</dt><dd>%(sweep).1f° / 36°<small></small></dd></div>
        <div><dt>worst transmission angle</dt><dd>%(tmin).1f°<small>90° is ideal</small></dd></div>
        <div><dt>arm inertia about hinge</dt><dd>%(I).4f<small>kg m²</small></dd></div>
        <div><dt>hinge torque, fold in %(tf).2f s</dt><dd>%(tau).3f<small>N m</small></dd></div>
        <div><dt>servo torque needed / rated</dt><dd>%(ts).2f / %(tr).1f<small>kg cm, %(margin).1f× margin</small></dd></div>
      </dl>
      <p class="note">Each servo is mounted upside down through a cut-out in the top plate, so the horn and pushrod run in the gap between the carbon plates, just above the arm. The hinge pin and its plates carry the thrust and crash loads; the servo only has to swing the arm. With the props spinning about a vertical axis and the arm swinging about another vertical axis, folding puts no gyroscopic load on the servo.</p>
    </div>
  </section>
  <section class="panel">
    <h2>Wire list</h2>
    <div class="scroll"><table>
      <thead><tr><th>ID</th><th>Cable / nets</th><th>From → to</th><th>Cores</th><th class="num">n</th><th class="num">AWG</th><th class="num">Length mm</th><th class="num">Design I</th><th class="num">Drop</th><th>Termination</th></tr></thead>
      <tbody>%(rows)s</tbody>
    </table></div>
    <p class="note">Drop is the round-trip voltage drop at the design current for power cables, from copper resistance at 20 °C. Motor phase drop is line to line at 30 A.</p>
  </section>
  <section class="panel">
    <h2>Parts</h2>
    <div class="scroll"><table style="min-width:640px"><tbody>%(parts)s</tbody></table></div>
  </section>
</div>
"""
PAGE = PAGE_T.replace("%", "%%").replace("%%(", "%(") % dict(ncomp=len(C), ncab=len(W), ncond=cond, tot=tot_m, svg=SVG, lk=LKSVG, rows=''.join(rows), parts=parts,
           rh=LK['horn_r'] * 1000, rod=LK['rod_len'] * 1000, rl=LK['lever_r'] * 1000, psi=LK['lever_psi_deg'],
           sh=math.dist(LK['hinge'], LK['servo_shaft']) * 1000, sweep=LK['sweep_deg'], tmin=LK['min_transmission_deg'],
           I=T['inertia_kgm2'], tf=T['fold_time_s'], tau=T['hinge_torque_Nm'], ts=T['servo_torque_kgcm'], tr=T['servo_rated_kgcm'], margin=T['margin'])
open(os.path.join(HERE, 'harness.html'), 'w', encoding='utf-8', newline='\n').write(PAGE)
print('wrote harness.html', len(PAGE) // 1024, 'KB')
