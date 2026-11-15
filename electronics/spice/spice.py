"""Thin ngspice batch runner: parameter overrides, measurement parsing, waveform loading."""
import os, re, subprocess
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, 'build')
NGSPICE = os.environ.get('NGSPICE', r'C:\msys64\mingw64\bin\ngspice_con.exe')
os.makedirs(BUILD, exist_ok=True)


def run(cir, name, params=None, subs=None, timeout=1200):
    src = open(os.path.join(HERE, cir), encoding='utf-8').read()
    for k, v in (params or {}).items():
        src, n = re.subn(rf'^\.param {k}=\S+', f'.param {k}={v}', src, flags=re.M)
        if n != 1:
            raise KeyError(f'{cir}: .param {k} not found')
    out = os.path.join(BUILD, name + '.txt').replace('\\', '/')
    src = src.replace('{OUT}', out)
    for k, v in (subs or {}).items():
        src = src.replace('{' + k + '}', str(v))
    path = os.path.join(BUILD, name + '.cir')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(src)
    r = subprocess.run([NGSPICE, '-b', path], capture_output=True, text=True, cwd=BUILD, timeout=timeout)
    log = r.stdout + r.stderr
    with open(os.path.join(BUILD, name + '.log'), 'w', encoding='utf-8') as f:
        f.write(log)
    meas = {}
    for line in r.stdout.splitlines():
        m = re.match(r'^\s*([a-z_]\w*)\s*=\s*([-+]?[0-9.]+(?:e[-+]?\d+)?)', line, re.I)
        if m:
            meas[m.group(1).lower()] = float(m.group(2))
    errors = [l for l in log.splitlines() if re.search(r'\berror\b', l, re.I) and 'code model' not in l]
    if errors or not os.path.exists(out):
        raise RuntimeError(f'{name} failed:\n' + '\n'.join(errors[:20] or log.splitlines()[-30:]))
    with open(out, encoding='utf-8') as f:
        cols = f.readline().split()
    data = np.loadtxt(out, skiprows=1)
    wave = {c: data[:, i] for i, c in enumerate(cols)}
    return meas, wave
