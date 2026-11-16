"""SX-01 carbon plate outline (plan view, body x/z), shared by the linkage synthesis scripts.

A narrow spine (46 mm half-width, chamfered to 30 mm at the ends) with a round lobe around each fold hinge, so
the plates, and the shell around them, stay slim. slipstream.html builds the same outline (plateHalfWidth).
"""
import math

HX, HZ, LOBE = 0.068, 0.070, 0.025
CORE, END_W, Z_END, Z_CH = 0.046, 0.030, 0.135, 0.105


def half_width(z):
    a = abs(z)
    core = CORE if a <= Z_CH else CORE - (CORE - END_W) * (a - Z_CH) / (Z_END - Z_CH)
    d = a - HZ
    lobe = HX + math.sqrt(LOBE * LOBE - d * d) if abs(d) < LOBE else 0.0
    k = 0.008
    return (core + lobe + math.sqrt((core - lobe) ** 2 + k * k)) / 2   # smooth max: fillets where the lobes meet the spine


def outline(n=120):
    zs = [-Z_END + 2 * Z_END * i / n for i in range(n + 1)]
    right = [(half_width(z), z) for z in zs]
    left = [(-half_width(z), z) for z in reversed(zs)]
    return right + left
