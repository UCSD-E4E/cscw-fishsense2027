"""E1g feasibility: recover the beam's vanishing point from the dots alone, in simulation.

Per dive the only unknown is phi, equivalently v, the beam's vanishing point on the dot line.
Every dot gives its position p = v + A/Z (A = f*|O|, known from the mount), and optionally:
  size       s = cs + b/Z               cs = f * divergence: a LASER constant, measured once
  brightness sqrt(S) = kappa (p - v) exp(-c Z)
                                        total power does not grow with range, so there is no
                                        additive constant; c (water absorption) changes per dive
Each cue has one nuisance that trades off against v (cs for size, c for brightness). Fitting
both together partly cancels the two biases. Run:  uv run python e1g_simulation.py
"""
import numpy as np
from scipy.optimize import least_squares

F, A, CS, B = 2850.0, 296.0, 1.0, 4.0
rng = np.random.default_rng(2)


def trial(n=300, zmin=0.5, zmax=4.0, s_noise=0.3, cs_err=0.05, refl=0.3, c_att=0.35, c_err=0.3, cues=("size", "brightness")):
    z = np.exp(rng.uniform(np.log(zmin), np.log(zmax), n))
    p = A / z + rng.normal(0, 1.0, n)
    s = CS + B / z + rng.normal(0, s_noise, n)
    y = np.sqrt(np.exp(rng.normal(0, refl, n)) / z**2 * np.exp(-2 * c_att * z))

    def res(q):
        d, out = q[0], []
        if "size" in cues:
            out.append((s - (CS + cs_err + q[1] / A * (p - d))) / s_noise)
        if "brightness" in cues:
            zz = A / np.clip(p - d, 1, None)
            out.append((y - np.exp(q[-1]) * (p - d) * np.exp(-c_att * (1 + c_err) * zz)) / (y.mean() * refl))
        return np.concatenate(out)

    q0 = [0.0] + ([B] if "size" in cues else []) + ([np.log(y.mean() / p.mean())] if "brightness" in cues else [])
    return np.degrees(least_squares(res, q0).x[0] / F)


if __name__ == "__main__":
    print("median |phi error|, deg, 300 simulated dives each (target 0.05)")
    for cues in (("brightness",), ("size",), ("size", "brightness")):
        for cs_err in (0.0, 0.05, 0.1):
            e = np.median(np.abs([trial(cs_err=cs_err, cues=cues) for _ in range(300)]))
            print(f"  {'+'.join(cues):16s} divergence error {cs_err:.2f} px, absorption 30% off: {e:.3f}")
