"""Field of small uniformly magnetised magnets (equivalent surface current, Biot-Savart).

A magnet magnetised along unit vector `axis` is a stack of loops carrying the surface
current K = Br / mu0 around its side faces. Each loop is a polygon; straight segments use
the closed-form Biot-Savart result, so the model is exact apart from the loop count.
Units: mm in, mT out.
"""
import numpy as np

MU0 = 4e-7 * np.pi


def _frame(axis):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1.0, 0])
    e1 = np.cross(a, t)
    e1 /= np.linalg.norm(e1)
    return a, e1, np.cross(a, e1)


def _segments_field(p1, p2, r, current):
    """B [T] at points r (N,3) [m] from straight segments p1->p2 (S,3) [m]."""
    a = p1[None, :, :] - r[:, None, :]
    b = p2[None, :, :] - r[:, None, :]
    na = np.linalg.norm(a, axis=2)
    nb = np.linalg.norm(b, axis=2)
    cr = np.cross(a, b)
    den = na * nb * (na * nb + np.einsum("nsk,nsk->ns", a, b))
    f = np.where(den > 1e-30, (na + nb) / np.maximum(den, 1e-30), 0.0)
    return MU0 * current / (4 * np.pi) * np.einsum("ns,nsk->nk", f, cr)


def magnet_field(points_mm, centre_mm, axis, br_t, shape, n_loops=48, n_seg=96):
    """B [mT] at points from a magnet. shape = ('cyl', diameter, length) or ('box', w1, w2, length);
    length is along the magnetisation axis, w1 along the frame's first transverse vector."""
    a, e1, e2 = _frame(axis)
    c = np.asarray(centre_mm, float)
    if shape[0] == "cyl":
        _, dia, length = shape
        phi = np.linspace(0, 2 * np.pi, n_seg + 1)
        ring = (dia / 2) * (np.cos(phi)[:, None] * e1 + np.sin(phi)[:, None] * e2)
    else:
        _, w1, w2, length = shape
        q = np.array([[1, 1], [-1, 1], [-1, -1], [1, -1], [1, 1]], float) * 0.5
        ring = q[:, 0:1] * w1 * e1 + q[:, 1:2] * w2 * e2
    zs = ((np.arange(n_loops) + 0.5) / n_loops - 0.5) * length
    p1 = np.concatenate([c + ring[:-1] + z * a for z in zs]) * 1e-3
    p2 = np.concatenate([c + ring[1:] + z * a for z in zs]) * 1e-3
    current = br_t / MU0 * (length / n_loops) * 1e-3
    pts = np.atleast_2d(np.asarray(points_mm, float)) * 1e-3
    out = np.zeros((len(pts), 3))
    for i in range(0, len(pts), 64):
        out[i:i + 64] = _segments_field(p1, p2, pts[i:i + 64], current)
    return out * 1e3


def _self_test():
    # On the axis of a cylinder magnet: B = Br/2 * ((L/2+z)/sqrt(R^2+(L/2+z)^2) - (z-L/2)/sqrt(R^2+(z-L/2)^2))
    br, d, L = 1.2, 4.0, 2.0
    z = np.array([1.5, 2.0, 3.0, 5.0])
    R = d / 2
    exact = br / 2 * ((L / 2 + z) / np.sqrt(R ** 2 + (L / 2 + z) ** 2) - (z - L / 2) / np.sqrt(R ** 2 + (z - L / 2) ** 2)) * 1e3
    pts = np.stack([np.zeros_like(z), np.zeros_like(z), z], 1)
    got = magnet_field(pts, (0, 0, 0), (0, 0, 1), br, ("cyl", d, L), n_loops=200, n_seg=400)[:, 2]
    err = np.max(np.abs(got / exact - 1))
    assert err < 2e-3, (got, exact)
    return float(err)


if __name__ == "__main__":
    print("max relative error on axis:", _self_test())
