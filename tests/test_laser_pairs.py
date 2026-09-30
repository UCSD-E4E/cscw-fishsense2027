"""Pins T1/T2: the 755 laser pairs are copies of seeded labels, not independent opinions."""

import numpy as np

from fishsense_cscw import laser_pairs as lp


def test_reproduces_the_effort_studys_755():
    a = lp.load_annotations()
    assert len(lp.pair_images(a)) == 755


def test_booleans_are_parsed_not_truthy():
    """The trap: astype(bool) on 't'/'f' makes every annotation a skip, and 755 becomes 0."""
    a = lp.load_annotations()
    assert a.cancelled.dtype == bool and 0 < a.cancelled.sum() < len(a) / 2


def test_pairs_are_seeded_copies_not_independent_labels():
    p = lp.pairs(lp.load_annotations())
    assert len(p) == 717
    assert (~p.same_project).sum() >= 710
    counts = p.later_action.value_counts()
    assert counts["accepted"] == 626 and counts["moved"] == 85 and counts["none"] == 6
    acc = p[p.later_action == "accepted"]
    assert (acc.distance_px < 1e-6).sum() == 450  # exact copies, to float precision
    assert (acc[acc.canvas == "3987->4014"].distance_px < 1e-6).all()  # every mixed-canvas accept
    assert np.median(p[p.later_action == "moved"].distance_px) < 1.5  # a nudge, not a re-label


def test_anchoring_on_seeds_the_validator_rejects():
    p = lp.pairs(lp.load_annotations())
    t = lp.anchoring(p)
    bad, good = t.loc["seed's source now superseded"], t.loc["seed's source live"]
    assert (bad.accepted, bad.moved) == (189, 57)
    assert good.accept_rate > 0.9 and 0.7 < bad.accept_rate < 0.8
    acc_bad = p[(p.later_action == "accepted") & p.first_superseded]
    dist = lp.live_label_distance(acc_bad)
    assert dist.isna().sum() == 184  # nothing live left on the image
    assert (dist > 5).sum() == 0  # and no accepted seed was ever corrected by >5 px
