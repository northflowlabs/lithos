"""Small-baseline time-series inversion for unwrapped interferograms.

An independent implementation of the small-baseline least-squares approach published by
Berardino et al. (2002), IEEE TGRS 40(11). Every interferogram measures the change
between two dates, so a network of them gives an overdetermined linear system for the
displacement at each date. Written from the paper under Apache-2.0; it shares no code
with any GPL package (see docs/licensing.md).

Sign convention: positive displacement is motion towards the satellite.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Sentinel-1 C-band radar wavelength.
WAVELENGTH_MM = 55.46576
# One full phase cycle of unwrapping error, in millimetres of line-of-sight motion.
CYCLE_MM = WAVELENGTH_MM / 2.0


def phase_to_los_mm(phase_rad: np.ndarray) -> np.ndarray:
    """Unwrapped phase to line-of-sight displacement, positive towards the satellite."""
    return -phase_rad * WAVELENGTH_MM / (4.0 * np.pi)


@dataclass
class Inversion:
    displacement_mm: np.ndarray  # one value per epoch, NaN where the network has no link
    residual_rms_mm: float
    pairs_used: int
    pairs_rejected: int


def _largest_component(pairs: np.ndarray, n_epochs: int) -> np.ndarray:
    """Boolean epoch mask of the largest connected group in the pair network."""
    parent = np.arange(n_epochs)

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = int(parent[i])
        return i

    for a, b in pairs:
        parent[find(int(a))] = find(int(b))
    roots = np.array([find(i) for i in range(n_epochs)])
    seen = np.isin(np.arange(n_epochs), pairs)
    if not seen.any():
        return seen
    values, counts = np.unique(roots[seen], return_counts=True)
    return seen & (roots == values[np.argmax(counts)])


def invert_network(
    pairs: np.ndarray,
    los_mm: np.ndarray,
    n_epochs: int,
    max_rejection_rounds: int = 3,
) -> Inversion:
    """Solve one pixel's pair network for displacement at each epoch.

    `pairs` is (n, 2) epoch indices with first < second, `los_mm` the measured change for
    each pair, NaN where it was masked. A pair that disagrees with the rest of its network
    by more than half a phase cycle is an unwrapping error and is dropped before the
    network is solved again. Epochs outside the largest connected network stay NaN.
    """
    empty = np.full(n_epochs, np.nan)
    ok = np.isfinite(los_mm)
    rejected = 0
    solution = empty
    rms = float("nan")

    for _ in range(max_rejection_rounds + 1):
        used = pairs[ok]
        epochs = _largest_component(used, n_epochs)
        if epochs.sum() < 3:
            return Inversion(empty, float("nan"), 0, rejected)
        keep = ok & epochs[pairs[:, 0]] & epochs[pairs[:, 1]]
        order = np.flatnonzero(epochs)
        column = {int(e): c - 1 for c, e in enumerate(order)}  # the first epoch is the datum
        rows = np.flatnonzero(keep)
        design = np.zeros((rows.size, order.size - 1))
        for r, k in enumerate(rows):
            a, b = int(pairs[k, 0]), int(pairs[k, 1])
            if column[a] >= 0:
                design[r, column[a]] = -1.0
            if column[b] >= 0:
                design[r, column[b]] = 1.0
        observed = los_mm[rows]
        x, *_ = np.linalg.lstsq(design, observed, rcond=None)
        residual = observed - design @ x
        rms = float(np.sqrt(np.mean(residual**2)))
        solution = empty.copy()
        solution[order[0]] = 0.0
        solution[order[1:]] = x
        worst = np.abs(residual) > CYCLE_MM / 2.0
        if not worst.any():
            return Inversion(solution, rms, rows.size, rejected)
        ok[rows[worst]] = False
        rejected += int(worst.sum())
    return Inversion(solution, rms, int(ok.sum()), rejected)


def decompose_vertical_east(
    los_a: np.ndarray,
    los_b: np.ndarray,
    unit_a: tuple[float, float],
    unit_b: tuple[float, float],
) -> tuple[np.ndarray, np.ndarray]:
    """Vertical and east motion from two viewing geometries.

    `unit_a` and `unit_b` are the (east, up) components of each line-of-sight unit vector,
    pointing at the satellite. North motion is neglected, as Sentinel-1 barely sees it.
    """
    system = np.array([[unit_a[0], unit_a[1]], [unit_b[0], unit_b[1]]])
    east, up = np.linalg.solve(system, np.stack([los_a, los_b]).reshape(2, -1))
    return up.reshape(los_a.shape), east.reshape(los_a.shape)
