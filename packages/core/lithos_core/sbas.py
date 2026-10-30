"""Small-baseline time-series inversion for unwrapped interferograms.

An independent implementation of the small-baseline least-squares approach published by
Berardino et al. (2002), IEEE TGRS 40(11). Every interferogram measures the change
between two dates, so a network of them gives an overdetermined linear system for the
displacement at each date, solved by SVD. Written from the paper under Apache-2.0; it
shares no code with any GPL package (see docs/licensing.md).

Berardino joins disconnected subsets with a minimum-norm velocity, which draws a flat line
across the gap, so a gap would look like ground that stopped moving. Here the network is
bridged with longer pairs where the archive has them, disconnection is reported, and dates
off the largest subset stay empty.

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
    components: int  # connected subsets among the epochs with data; 1 is an intact network


def find_triplets(pairs: np.ndarray) -> np.ndarray:
    """Rows (ab, bc, ac) of every closed loop of three pairs in the network."""
    row = {(int(a), int(b)): i for i, (a, b) in enumerate(pairs)}
    loops = []
    for (a, b), ab in row.items():
        for (b2, c), bc in row.items():
            if b2 == b and (a, c) in row:
                loops.append((ab, bc, row[(a, c)]))
    return np.array(loops, dtype=int).reshape(-1, 3)


def _reject_by_closure(los_mm: np.ndarray, triplets: np.ndarray, ok: np.ndarray) -> int:
    """Clear pairs that break phase closure, worst first, until every loop closes. The
    three phases of a loop must sum to zero, so a loop that does not contains an
    unwrapping error. Updates `ok` in place and returns how many pairs went."""
    rejected = 0
    while True:
        live = ok[triplets].all(axis=1)
        loops = triplets[live]
        if loops.size == 0:
            return rejected
        closure = los_mm[loops[:, 0]] + los_mm[loops[:, 1]] - los_mm[loops[:, 2]]
        failing = np.abs(closure) > CYCLE_MM / 2.0
        if not failing.any():
            return rejected
        fails = np.bincount(loops[failing].ravel(), minlength=ok.size)
        worst = np.flatnonzero(fails == fails.max())
        if worst.size > 1:  # a tie: a pair in more loops that close is less likely the bad one
            closes = np.bincount(loops[~failing].ravel(), minlength=ok.size)
            worst = worst[closes[worst] == closes[worst].min()]
        ok[worst] = False  # still tied, nothing tells them apart, so none is trusted
        rejected += int(worst.size)


def _subsets(pairs: np.ndarray, n_epochs: int) -> tuple[np.ndarray, int]:
    """Epoch mask of the largest connected subset, and how many subsets there are."""
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
        return seen, 0
    values, counts = np.unique(roots[seen], return_counts=True)
    return seen & (roots == values[np.argmax(counts)]), int(values.size)


def invert_network(
    pairs: np.ndarray,
    los_mm: np.ndarray,
    n_epochs: int,
    triplets: np.ndarray | None = None,
    max_rejections: int = 20,
) -> Inversion:
    """Solve one cell's pair network for displacement at each epoch.

    `pairs` is (n, 2) epoch indices with first < second, `los_mm` the measured change for
    each pair, NaN where it was masked. Pairs that break phase closure go first; then the
    pair that disagrees most with the solved network is dropped, one at a time, while any
    pair is off by more than half a phase cycle. `components` reports a split network;
    epochs outside its largest subset stay NaN.
    """
    empty = np.full(n_epochs, np.nan)
    ok = np.isfinite(los_mm)
    if triplets is None:
        triplets = find_triplets(pairs)
    rejected = _reject_by_closure(los_mm, triplets, ok)

    while True:
        epochs, components = _subsets(pairs[ok], n_epochs)
        if epochs.sum() < 3:
            return Inversion(empty, float("nan"), 0, rejected, components)
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
        worst = int(np.argmax(np.abs(residual)))
        if abs(residual[worst]) > CYCLE_MM / 2.0 and rejected < max_rejections:
            ok[rows[worst]] = False
            rejected += 1
            continue
        solution = empty.copy()
        solution[order[0]] = 0.0
        solution[order[1:]] = x
        rms = float(np.sqrt(np.mean(residual**2)))
        return Inversion(solution, rms, rows.size, rejected, components)


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
