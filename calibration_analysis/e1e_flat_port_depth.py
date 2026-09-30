"""E1e: can the flat port's own refraction (the axial camera P4 left us) fix phi from the dots?

Refraction at a flat pane makes the camera axial: rays no longer share a viewpoint, so
an image position depends weakly on depth as well as direction. That is the one depth
cue that needs nothing added to the scene. The question is how big it is at the field
angles a laser dot occupies (the dot sits within arctan(|O|/Z) of the axis).

Measured here with P4's exact port model: the dot's image position under the true axial
projection minus the best single-viewpoint (pinhole + radial) fit calibrated at 2 m --
the part no per-dive line fit can absorb. Compare with 0.05 deg of phi (2.5 px) and dot
noise (1-3 px). Run from P4's environment:  ../../wuwnet-fishsense2026/.venv/bin/python e1e_flat_port_depth.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "wuwnet-fishsense2026"))
from fishsense_wuwnet.refraction import FlatPort, field_angle, fit_svp_model, optimal_d0, svp_image_radius  # noqa: E402

F_PX, LASER_OFFSET_M = 2850.0, 0.104
Z = np.array([0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0])
GLASS_M, N_GLASS, N_WATER, HALF_FOV = 0.006, 1.49, 1.342, np.radians(40)


def depth_signature(d0: float) -> np.ndarray:
    port = FlatPort(d0, GLASS_M, N_GLASS, N_WATER)
    coeffs = fit_svp_model(port, HALF_FOV, 2.0, n_radial=3)
    exact = np.tan(field_angle(LASER_OFFSET_M, Z, port))
    return F_PX * (exact - svp_image_radius(LASER_OFFSET_M / Z, coeffs))


if __name__ == "__main__":
    d0_star, _, _ = optimal_d0(GLASS_M, N_GLASS, N_WATER, HALF_FOV)
    print(f"P4 standoff d0* = {d0_star * 1000:.2f} mm.  Rows: exact axial minus fitted pinhole, px.  "
          f"0.05 deg of phi = {F_PX * np.radians(0.05):.2f} px.")
    print(f"{'d0 mm':>7} " + " ".join(f"{z:>7.1f}m" for z in Z) + f"  {'range':>7}  {'1-3 m':>7}")
    for d0 in (d0_star, 0.005, 0.020, 0.050, 0.100):
        e = depth_signature(d0)
        w = e[(Z >= 1) & (Z <= 3)]
        print(f"{d0 * 1000:7.2f} " + " ".join(f"{v:+8.3f}" for v in e) + f"  {np.ptp(e):7.3f}  {np.ptp(w):7.3f}")
