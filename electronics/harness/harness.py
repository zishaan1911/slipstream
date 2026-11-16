"""SX-01 wiring harness: one parts list + netlist that drives both the 3D airframe and the wiring diagram.

    python electronics/harness/harness.py

Writes electronics/harness/harness.json, embeds it in slipstream.html (between the harness-data script tags),
and writes electronics/harness/harness.html (wiring diagram + wire list with lengths measured from the 3D routes).

Coordinates are airframe body axes in metres (three.js convention: x right, y up, z aft; the nose is -z).
Points written {"arm": i, "p": [x, y, z]} ride on arm i: x across the arm, z along it (negative = outboard).
The top carbon plate's upper face is at y = 0.016, its lower face at 0.013; the bottom plate's upper face at -0.0164.
"""
import json, math, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LINK = json.load(open(os.path.join(ROOT, 'electronics', 'linkage', 'linkage.json')))
LEGS = json.load(open(os.path.join(ROOT, 'electronics', 'linkage', 'legs.json')))

GEO = dict(hingeX=0.068, hingeZ=0.07, armL=0.26, aOpen=math.radians(45), propY=0.03)
ARMS = [dict(side=-1, end=-1, name='FL'), dict(side=1, end=-1, name='FR'), dict(side=-1, end=1, name='RL'), dict(side=1, end=1, name='RR')]
L = GEO['armL']
ARM_Y = -0.001
UNDER = ARM_Y - 0.0025 - 0.0012          # wire centre just under the arm plate
PLATE = 0.0185                           # wire centre lying on the top plate

def mp(arm, x, z):                       # canonical front-right (x, z) -> arm's quadrant
    return [arm['side'] * x, -arm['end'] * z]

def AP(i, x, y, z):                      # point riding on arm i
    return {'arm': i, 'p': [round(x, 5), round(y, 5), round(z, 5)]}

def P(x, y, z):
    return [round(x, 5), round(y, 5), round(z, 5)]

# ---------------------------------------------------------------- servo placement from the linkage synthesis
S = LINK['servo_shaft']; G = math.radians(LINK['servo_yaw_deg'])
U = (math.cos(G), math.sin(G))
def servo_pose(arm):
    sx, sz = mp(arm, *S)
    ux, uz = arm['side'] * U[0], -arm['end'] * U[1]
    ex, ez = mp(arm, S[0] + U[0] * 0.0161, S[1] + U[1] * 0.0161)   # lead exit: far end of the case, near its top
    return dict(shaft=P(sx, 0.016, sz), axis=[round(ux, 5), round(uz, 5)], lead=P(ex, 0.031, ez))

# ---------------------------------------------------------------- components
C = {}
def comp(cid, name, part, sch, **kw):
    C[cid] = dict(name=name, part=part, sch=sch, **kw)

comp('BAT', 'Flight battery', 'LiPo 4S1P 2200 mAh 75C, XT60', [80, 60], rail='VBAT 12.8-16.8 V')
comp('XT60', 'Main connector', 'XT60 pair (battery male / frame female)', [250, 60])
comp('ESC', '4-in-1 ESC', '45 A per channel, BLHeli_32, current sensor, 30x30 mm', [430, 200])
comp('CAP', 'Bulk capacitor', '1000 uF 35 V low-ESR on ESC pads', [430, 60])
comp('FC', 'Flight controller', 'STM32H7, 5 V BEC, 30x30 mm, stacked above ESC', [430, 420])
comp('HUB', 'Servo power board', '7.4 V 5 A BEC + four 3-pin servo headers', [700, 420], rail='SERVO 7.4 V',
     at=P(0, 0.0175, -0.078), size=P(0.03, 0.0016, 0.022))
comp('BUCK', '12 V buck', 'Synchronous buck, 12 V 3 A, 500 kHz', [700, 120], rail='COMP 12 V',
     at=P(0, 0.0175, 0.052), size=P(0.024, 0.0016, 0.016))
comp('CM4', 'Companion computer', 'Raspberry Pi CM4 on 12 V carrier board', [940, 120])
comp('CAM', 'Depth camera', 'Compact stereo depth module, 50 mm, USB-C', [1160, 60])
comp('FAN', 'Heatsink fan', '30 mm 5 V fan', [1160, 200])
comp('GIMBAL', 'Gimbal camera', '2-axis brushless gimbal + 4K action camera, 12 V, serial control', [1300, 470],
     at=P(0, -0.0255, -0.07))
comp('RX', 'Receiver', '2.4 GHz serial receiver, dual antenna', [700, 600],
     at=P(-0.02, 0.0175, 0.128), size=P(0.016, 0.002, 0.012))
for i, a in enumerate(ARMS):
    comp('M%d' % (i + 1), 'Motor %s' % a['name'], '2807 1300 KV, 7" tri-blade', [180 + i * 180, 760 - 0], arm=i)
    comp('S%d' % (i + 1), 'Fold servo %s' % a['name'], 'HV micro servo 2.5 kg cm, 7.4 V, inverted through top plate', [880 + (i % 2) * 150, 560 + (i // 2) * 120],
         arm=i, **servo_pose(a))
    comp('LED%d' % (i + 1), 'Nav LED %s' % a['name'], 'WS2812B in the motor pod base, %s' % ('white (front)' if a['end'] < 0 else 'red (rear)'), [180 + i * 180, 900], arm=i)

# ---------------------------------------------------------------- cables
W = []
def cable(cid, name, frm, to, cores, awg, route, pitch=None, design_A=0.5, conn=''):
    W.append(dict(id=cid, name=name, frm=frm, to=to, cores=[dict(net=n, color=c, a=pa, b=pb) for n, c, pa, pb in cores],
                  awg=awg, route=route, pitch=pitch or OD[awg] * 1.05, design_A=design_A, conn=conn))

OD = {12: 0.0034, 14: 0.0029, 16: 0.0024, 18: 0.0020, 20: 0.0017, 22: 0.0014, 24: 0.0012, 26: 0.0010, 28: 0.0009, 30: 0.0008}
OHM_PER_M = {12: 0.00521, 14: 0.00829, 16: 0.0132, 18: 0.0210, 20: 0.0333, 22: 0.0530, 24: 0.0842, 26: 0.134, 28: 0.213, 30: 0.339}

# battery -> XT60 (pack lead, exits the rear face of the pack) and XT60 -> ESC battery pads (round the rear plate edge)
for pol, col, o in (('+', 'red', 0.004), ('-', 'black', -0.004)):
    net = 'VBAT' if pol == '+' else 'GND'
    cable('W0%s' % ('1' if pol == '+' else '2'), 'Pack lead %s' % pol, 'BAT', 'XT60', [(net, col, pol, 'B' + pol)], 12,
          [P(o, 0.03, 0.033), P(o * 1.4, 0.036, 0.06), P(o, 0.03, 0.1), P(o, 0.025, 0.12)], design_A=60, conn='soldered / XT60 male')
    cable('W0%s' % ('3' if pol == '+' else '4'), 'Frame lead %s' % pol, 'XT60', 'ESC', [(net, col, 'F' + pol, 'BAT' + pol)], 12,
          [P(o, 0.022, 0.134), P(o * 1.6, 0.01, 0.142), P(o * 2, -0.004, 0.13), P(o * 2, -0.008, 0.06), P(o * 2, -0.0102, 0.019)], design_A=60, conn='XT60 female / ESC pads')

# ESC -> motors: three phase wires per arm, between the plates, a service loop round the hinge, under the arm,
# up through the motor mount's centre hole
PH = [('A', 'black'), ('B', 'black'), ('C', 'black')]
for i, a in enumerate(ARMS):
    s, e = a['side'], a['end']
    route = [P(s * 0.0185, -0.0102, e * 0.0155), P(s * 0.03, -0.0075, e * 0.034), P(s * 0.05, -0.0058, e * 0.056),
             AP(i, 0, UNDER, -0.012), AP(i, 0, UNDER, -0.05), AP(i, 0, UNDER, -(L - 0.03)), AP(i, 0, -0.0045, -(L - 0.006)), AP(i, 0, 0.0035, -L)]
    cable('W1%d' % (i + 1), 'Motor %s phases' % a['name'], 'ESC', 'M%d' % (i + 1),
          [('M%d_%s' % (i + 1, p), c, 'M%d%s' % (i + 1, p), p) for p, c in PH], 18, route, design_A=30, conn='soldered both ends')
    # nav LED: thin 3-core from the FC LED pad, alongside the phase wires, to the LED beyond the motor
    lroute = [P(s * 0.016, -0.0012, e * 0.016), P(s * 0.032, -0.0068, e * 0.04), P(s * 0.052, -0.0062, e * 0.06),
              AP(i, 0.0034, UNDER, -0.014), AP(i, 0.0034, UNDER, -(L - 0.03)), AP(i, 0.005, -0.012, -(L - 0.012)), AP(i, 0.002, -0.0205, -L)]
    cable('W2%d' % (i + 1), 'Nav LED %s' % a['name'], 'FC', 'LED%d' % (i + 1),
          [('5V', 'red', 'LED5V', 'VDD'), ('LED%d_DIN' % (i + 1), 'white', 'LED%d' % (i + 1), 'DIN'), ('GND', 'black', 'GND', 'GND')], 30, lroute, design_A=0.06,
          conn='FC pads / soldered')

# ESC <-> FC: 8-way JST-SH ribbon at the stack's front-left corner
cable('W30', 'ESC-FC harness', 'ESC', 'FC',
      [('VBAT', 'red', 'VBAT', 'VBAT'), ('GND', 'black', 'GND', 'GND'), ('CURR', 'grey', 'CURR', 'CURR'), ('TLM', 'grey', 'TLM', 'TLM'),
       ('M1', 'grey', 'S1', 'M1'), ('M2', 'grey', 'S2', 'M2'), ('M3', 'grey', 'S3', 'M3'), ('M4', 'grey', 'S4', 'M4')], 30,
      [P(-0.0165, -0.0098, -0.006), P(-0.0205, -0.0072, -0.006), P(-0.0205, -0.0040, -0.006), P(-0.0165, -0.0014, -0.006)], pitch=0.001, design_A=1.0,
      conn='JST-SH 8-pin both ends')

# VBAT pigtails off the ESC pads: to the servo power board (front) and the 12 V buck (rear)
cable('W31', 'VBAT to servo board', 'ESC', 'HUB', [('VBAT', 'red', 'BAT+', 'VIN'), ('GND', 'black', 'BAT-', 'GND')], 20,
      [P(0.012, -0.0102, 0.019), P(0.028, -0.004, 0.012), P(0.034, 0.004, -0.005), P(0.034, PLATE, -0.016), P(0.028, PLATE, -0.03),
       P(0.026, PLATE, -0.058), P(0.016, PLATE, -0.072)], design_A=5, conn='soldered / JST-XH 2-pin')
cable('W32', 'VBAT to 12 V buck', 'ESC', 'BUCK', [('VBAT', 'red', 'BAT+', 'VIN'), ('GND', 'black', 'BAT-', 'GND')], 20,
      [P(-0.012, -0.0102, 0.019), P(-0.028, -0.004, 0.02), P(-0.034, 0.004, 0.016), P(-0.034, PLATE, 0.022), P(-0.026, PLATE, 0.04), P(-0.013, PLATE, 0.05)],
      design_A=3, conn='soldered / JST-XH 2-pin')
cable('W33', '12 V to carrier', 'BUCK', 'CM4', [('COMP_12V', 'red', 'VOUT', '12V'), ('GND', 'black', 'GND', 'GND')], 22,
      [P(0.013, PLATE, 0.052), P(0.02, 0.019, 0.064), P(0.018, 0.0205, 0.074), P(0.018, 0.0213, 0.082)], design_A=2, conn='JST-PH 2-pin')

# FC -> servo board signal cable (S1..S4 + GND), forward between the plates and up through the front-right window
cable('W34', 'Servo signals', 'FC', 'HUB',
      [('SRV%d' % k, 'white', 'S%d' % (k + 4), 'SIG%d' % k) for k in range(1, 5)] + [('GND', 'black', 'GND', 'GND')], 30,
      [P(0.0, -0.0012, -0.0165), P(0.004, 0.003, -0.04), P(0.02, 0.006, -0.098), P(0.026, 0.009, -0.116), P(0.026, 0.0165, -0.12),
       P(0.02, PLATE, -0.104), P(0.0, PLATE, -0.09)], pitch=0.001, design_A=0.02, conn='JST-GH 5-pin both ends')

# servo leads: brown/red/orange, from the lead exit on top of each inverted servo, down onto the plate, to the board
for i, a in enumerate(ARMS):
    s, e = a['side'], a['end']; sp = servo_pose(a); lx, ly, lz = sp['lead']
    hx, hz = s * 0.0115, (-0.083 if e < 0 else -0.073)
    if e < 0:   # front servos: straight in to the board
        route = [sp['lead'], P(lx - s * 0.006, 0.026, lz + 0.002), P(s * 0.03, PLATE, -0.056), P(s * 0.022, PLATE, -0.068), P(hx, 0.0195, hz)]
    else:       # rear servos: forward in the gap between the battery and the front servo
        route = [sp['lead'], P(lx - s * 0.006, 0.026, lz - 0.002), P(s * 0.026, PLATE, 0.036), P(s * 0.025, PLATE, 0.0), P(s * 0.025, PLATE, -0.05), P(s * 0.02, PLATE, -0.064), P(hx, 0.0195, hz)]
    cable('W4%d' % (i + 1), 'Servo %s lead' % a['name'], 'S%d' % (i + 1), 'HUB',
          [('GND', 'brown', 'GND', 'GND'), ('SERVO_7V4', 'red', 'V+', 'V+%d' % (i + 1)), ('SRV%d' % (i + 1), 'orange', 'SIG', 'SIG%d' % (i + 1))], 26, route,
          design_A=1.2, conn='servo lead / 3-pin 2.54 mm')

# gimbal camera under the belly: 12 V from the buck, serial control from the FC; both go down through the right-hand
# side slots of the plates and forward inside the belly pan
cable('W70', 'Gimbal 12 V', 'BUCK', 'GIMBAL', [('COMP_12V', 'red', 'VOUT2', '12V'), ('GND', 'black', 'GND', 'GND')], 24,
      [P(0.013, PLATE, 0.054), P(0.028, PLATE, 0.036), P(0.034, 0.012, 0.02), P(0.034, -0.004, 0.012), P(0.034, -0.0195, 0.0),
       P(0.03, -0.021, -0.03), P(0.014, -0.021, -0.058), P(0.014, -0.0265, -0.062)], design_A=0.45, conn='JST-PH 2-pin / gimbal board')
cable('W71', 'Gimbal control', 'FC', 'GIMBAL', [('UART3_TX', 'yellow', 'TX3', 'RX'), ('UART3_RX', 'green', 'RX3', 'TX'), ('GND', 'black', 'GND', 'GND')], 30,
      [P(0.016, -0.0012, -0.0135), P(0.028, -0.006, -0.02), P(0.034, -0.012, -0.018), P(0.034, -0.0195, -0.016),
       P(0.028, -0.021, -0.04), P(0.006, -0.021, -0.058), P(0.006, -0.0265, -0.062)], pitch=0.001, design_A=0.01, conn='JST-GH 4-pin / gimbal board')

# companion computer: UART to the FC (down through the rear-left window), USB-C from the depth camera, fan
cable('W50', 'CM4-FC telemetry UART', 'CM4', 'FC', [('UART1_TX', 'yellow', 'TX', 'RX1'), ('UART1_RX', 'green', 'RX', 'TX1'), ('GND', 'black', 'GND', 'GND')], 30,
      [P(-0.022, 0.0213, 0.108), P(-0.024, 0.017, 0.116), P(-0.024, 0.009, 0.115), P(-0.016, 0.004, 0.08), P(-0.012, 0.002, 0.04), P(-0.012, -0.0012, 0.0165)],
      pitch=0.001, design_A=0.01, conn='JST-GH 4-pin / 40-pin header')
cable('W51', 'Depth camera USB-C', 'CAM', 'CM4', [('USB3', 'black', 'USB-C', 'USB')], 22,
      [P(0.026, 0.0325, -0.118), P(0.031, 0.029, -0.1), P(0.03, 0.027, -0.03), P(0.03, 0.026, 0.0), P(0.022, 0.0258, 0.078)], pitch=0.0036, design_A=0.9, conn='USB-C both ends')
cable('W52', 'Fan', 'CM4', 'FAN', [('FAN_5V', 'red', 'FAN+', '+'), ('GND', 'black', 'GND', '-')], 30,
      [P(0.03, 0.0245, 0.104), P(0.026, 0.031, 0.11), P(0.012, 0.0386, 0.11)], design_A=0.1, conn='JST-SH 2-pin')

# receiver: serial to the FC through the rear-left window, two antenna coax leads to the antenna tubes
cable('W60', 'Receiver serial', 'RX', 'FC', [('5V', 'red', '5V', '5V'), ('GND', 'black', 'GND', 'GND'), ('CRSF_TX', 'yellow', 'TX', 'RX2'), ('CRSF_RX', 'green', 'RX', 'TX2')], 30,
      [P(-0.02, PLATE, 0.122), P(-0.022, 0.0165, 0.119), P(-0.022, 0.008, 0.112), P(0.004, 0.005, 0.07), P(0.01, 0.002, 0.035), P(0.012, -0.0012, 0.0165)],
      pitch=0.001, design_A=0.15, conn='JST-SH 4-pin both ends')
for k, s in enumerate((-1, 1)):
    r = [P(-0.02 + s * 0.006, PLATE, 0.133), P(-0.02 + s * 0.012, 0.03, 0.137), P(s * 0.03, 0.019, 0.13)] if s > 0 else [P(-0.026, PLATE, 0.131), P(-0.03, 0.017, 0.129)]
    cable('W6%d' % (k + 1), 'Antenna %s' % ('left' if s < 0 else 'right'), 'RX', 'RX', [('RF%d' % (k + 1), 'black', 'ANT%d' % (k + 1), 'ANT%d' % (k + 1))], 30, r,
          pitch=0.0011, design_A=0, conn='IPEX / antenna')

# ---------------------------------------------------------------- geometry helpers (same maths as armPoint() in the page)
def arm_theta(a, ang):
    if a['end'] < 0: return ang if a['side'] < 0 else -ang
    return math.pi - ang if a['side'] < 0 else ang - math.pi

def resolve(pt, ang=GEO['aOpen']):
    if isinstance(pt, dict):
        a = ARMS[pt['arm']]; th = arm_theta(a, ang); c, s = math.cos(th), math.sin(th); x, y, z = pt['p']
        return (a['side'] * GEO['hingeX'] + x * c + z * s, y, a['end'] * GEO['hingeZ'] - x * s + z * c)
    return tuple(pt)

def catmull_len(pts, n=24):
    def lerp(p0, p1, p2, p3, t):
        return tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t * t + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t ** 3) for k in range(3))
    q = [pts[0]] + pts + [pts[-1]]; total = 0; prev = pts[0]
    for i in range(1, len(q) - 2):
        for j in range(1, n + 1):
            p = lerp(q[i - 1], q[i], q[i + 1], q[i + 2], j / n); total += math.dist(prev, p); prev = p
    return total

for w in W:
    ln = catmull_len([resolve(p) for p in w['route']])
    w['length_mm'] = round(ln * 1000 + 15)       # +15 mm for strip/termination and slack
    r = OHM_PER_M[w['awg']] * w['length_mm'] / 1000
    w['ohm'] = round(r, 5); w['drop_mV'] = round(r * w['design_A'] * 1000 * (2 if len(w['cores']) > 1 and w['design_A'] > 0.5 else 1), 1)

DATA = dict(
    note='Generated by electronics/harness/harness.py; do not edit by hand.',
    colors=dict(red='#b3261e', black='#1a1b1d', brown='#5a3a24', orange='#e0861f', yellow='#e3c02a', green='#2f8f4e', white='#e9e9e6', grey='#7a7f86'),
    od=OD, linkage=LINK, legs=LEGS, components=C, cables=W)

if __name__ == '__main__':
    out = json.dumps(DATA, separators=(',', ':'))
    json.dump(DATA, open(os.path.join(HERE, 'harness.json'), 'w', newline='\n'), indent=1)
    page = os.path.join(ROOT, 'slipstream.html'); s = open(page, encoding='utf-8').read()
    tag = '<script type="application/json" id="harness-data">'
    if tag in s:
        s = re.sub(re.escape(tag) + r'.*?</script>', lambda m: tag + out + '</script>', s, count=1, flags=re.S)
    else:
        s = s.replace('<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>',
                      tag + out + '</script>\n<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>', 1)
    open(page, 'w', encoding='utf-8', newline='\n').write(s)
    tot = sum(w['length_mm'] * len(w['cores']) for w in W)
    print(len(C), 'components,', len(W), 'cables,', sum(len(w['cores']) for w in W), 'conductors,', round(tot / 1000, 2), 'm of wire')
