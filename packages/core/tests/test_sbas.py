"""The small-baseline solver, on networks whose answer can be worked out by hand."""

from __future__ import annotations

import numpy as np

from lithos_core.sbas import (
    CYCLE_MM,
    decompose_vertical_east,
    find_triplets,
    invert_network,
    phase_to_los_mm,
)

CHAIN = np.array([[0, 1], [1, 2], [2, 3], [0, 2], [1, 3]])


def test_phase_sign_is_positive_towards_the_satellite():
    assert phase_to_los_mm(np.array([-1.0]))[0] > 0


def test_recovers_displacement_from_a_redundant_network():
    truth = np.array([0.0, -2.0, -5.0, -6.0])
    los = truth[CHAIN[:, 1]] - truth[CHAIN[:, 0]]
    solved = invert_network(CHAIN, los, 4)
    assert np.allclose(solved.displacement_mm, truth)
    assert solved.residual_rms_mm < 1e-9


def test_drops_an_unwrapping_error():
    truth = np.array([0.0, -2.0, -5.0, -6.0, -8.0, -11.0])
    pairs = np.array([[i, j] for i in range(6) for j in range(i + 1, min(i + 4, 6))])
    los = truth[pairs[:, 1]] - truth[pairs[:, 0]]
    los[4] += CYCLE_MM
    solved = invert_network(pairs, los, 6)
    assert solved.pairs_rejected >= 1
    assert np.allclose(solved.displacement_mm, truth, atol=1e-6)


def test_finds_closed_loops():
    assert sorted(map(tuple, find_triplets(CHAIN))) == [(0, 1, 3), (1, 2, 4)]


def test_closure_removes_the_pair_that_breaks_most_loops():
    truth = np.array([0.0, -2.0, -5.0, -6.0, -8.0, -11.0])
    pairs = np.array([[i, j] for i in range(6) for j in range(i + 1, min(i + 4, 6))])
    los = truth[pairs[:, 1]] - truth[pairs[:, 0]]
    los[6] -= 2 * CYCLE_MM
    solved = invert_network(pairs, los, 6)
    assert solved.pairs_rejected == 1
    assert np.allclose(solved.displacement_mm, truth, atol=1e-6)


def test_injected_unwrapping_errors_are_found():
    rng = np.random.default_rng(11)
    truth = np.cumsum(rng.normal(-1.0, 1.0, 40))
    truth -= truth[0]
    pairs = np.array([[i, j] for i in range(40) for j in range(i + 1, min(i + 5, 40))])
    triplets = find_triplets(pairs)
    for _ in range(50):
        los = truth[pairs[:, 1]] - truth[pairs[:, 0]] + rng.normal(0, 0.5, len(pairs))
        bad = rng.choice(len(pairs), 6, replace=False)
        los[bad] += rng.choice([-2, -1, 1, 2], 6) * CYCLE_MM
        solved = invert_network(pairs, los, 40, triplets)
        assert np.abs(solved.displacement_mm - (truth - truth[0])).max() < 3.0


def test_a_tied_closure_failure_drops_the_pair_with_least_support():
    # Pair 1 (1 to 2) is bad and sits in one failing loop, tied with both others there, but
    # those two also close a loop each, so only pair 1 goes.
    pairs = np.array([[0, 1], [1, 2], [0, 2], [0, 3], [2, 3], [1, 3]])
    truth = np.array([0.0, -2.0, -5.0, -6.0])
    los = truth[pairs[:, 1]] - truth[pairs[:, 0]]
    los[1] += CYCLE_MM
    solved = invert_network(pairs, los, 4)
    assert np.allclose(solved.displacement_mm, truth, atol=1e-6)


def test_a_split_network_is_reported():
    pairs = np.array([[0, 1], [1, 2], [0, 2], [3, 4]])
    solved = invert_network(pairs, np.array([1.0, 1.0, 2.0, 9.0]), 5)
    assert solved.components == 2


def test_masked_pairs_are_skipped():
    truth = np.array([0.0, -2.0, -5.0, -6.0])
    los = truth[CHAIN[:, 1]] - truth[CHAIN[:, 0]]
    los[3] = np.nan
    assert np.allclose(invert_network(CHAIN, los, 4).displacement_mm, truth)


def test_epochs_off_the_network_stay_empty():
    pairs = np.array([[0, 1], [1, 2], [0, 2], [3, 4]])
    los = np.array([1.0, 1.0, 2.0, 9.0])
    solved = invert_network(pairs, los, 5)
    assert np.allclose(solved.displacement_mm[:3], [0.0, 1.0, 2.0])
    assert np.isnan(solved.displacement_mm[3:]).all()


def test_decomposition_inverts_the_viewing_geometry():
    up, east = -10.0, 2.0
    unit_a, unit_b = (-0.6, 0.78), (0.6, 0.78)
    los_a = np.array([unit_a[0] * east + unit_a[1] * up])
    los_b = np.array([unit_b[0] * east + unit_b[1] * up])
    got_up, got_east = decompose_vertical_east(los_a, los_b, unit_a, unit_b)
    assert np.isclose(got_up[0], up) and np.isclose(got_east[0], east)
