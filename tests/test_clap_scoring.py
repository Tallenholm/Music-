import math

from music_app.ai.clap import rank_labels


def test_rank_labels_softmax_orders_and_filters() -> None:
    ranked = rank_labels([3.0, 1.0, 0.0], ["hip-hop", "rock", "jazz"], threshold=0.1)

    assert [label for label, _ in ranked] == ["hip-hop", "rock"]
    assert ranked[0][1] > ranked[1][1]
    probabilities = rank_labels(
        [3.0, 1.0, 0.0], ["hip-hop", "rock", "jazz"], threshold=0.0
    )
    assert math.isclose(sum(prob for _, prob in probabilities), 1.0, rel_tol=1e-9)


def test_rank_labels_rejects_length_mismatch() -> None:
    try:
        rank_labels([1.0], ["rock", "pop"], threshold=0.0)
    except ValueError as exc:
        assert "same length" in str(exc)
    else:
        raise AssertionError("expected ValueError")
