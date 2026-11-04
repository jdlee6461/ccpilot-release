"""POST HOC (external review, instruction 03 §1): hand-computed check of posthoc_review_labels.hop_cost (R3).

Two keys, delta 10. Key 0 probabilities [0.1, 0.4, 0.9], key 1 probabilities [0.0, 0.2, 0.5, 0.7].
Five hops: (key, tau) = (0, 0.3), (0, 0.9), (1, 0.6), (0, inf), (1, 3.0).
Cells with p >= tau: 2, 1, 1, 0, 0  ->  cost 20, 10, 10, 0, 0.
Without the cap the lookup gives for hop 4 (key 0, tau inf): (3 - 7) * 10 = -40, and for hop 5 (key 1, tau 3.0):
q = 2 + 3 = 5 > every stored value -> (7 - 7) * 10 = 0 (key 1 is the last key).
"""
import numpy as np

from confirm2_analysis import CostLookup
from posthoc_review_labels import hop_cost


def test_hop_cost_hand(tmp_path):
    f = tmp_path / "lk.npz"
    np.savez(f, delta=10.0, kid=np.array([5, 8]), v5=np.array([0.1, 0.4, 0.9]), v8=np.array([0.0, 0.2, 0.5, 0.7]))
    lk = CostLookup(f, np.array([5, 5, 8, 5, 8]))
    tau = np.array([0.3, 0.9, 0.6, np.inf, 3.0])
    assert hop_cost(lk, tau).tolist() == [20.0, 10.0, 10.0, 0.0, 0.0]
    assert lk.cost_per_hop(tau).tolist() == [20.0, 10.0, 10.0, -40.0, 0.0]      # the defect without the cap


if __name__ == "__main__":          # no pytest in the ccpilot environment: python tests/test_review_hop_cost.py
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        test_hop_cost_hand(Path(d))
    print("test_hop_cost_hand: ok")
