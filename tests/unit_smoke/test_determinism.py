import pytest

from modules.teach_and_update_models.determinism import (
    model_params_with_seed,
    sample_fraction,
    sample_sequence,
)


def test_sample_sequence_repeats_with_same_seed():
    items = list(range(20))

    first_sample = sample_sequence(items, 5, seed=13)
    second_sample = sample_sequence(items, 5, seed=13)

    assert first_sample == second_sample


def test_sample_sequence_keeps_input_unchanged():
    items = list(range(10))

    sample_sequence(items, 4, seed=1)

    assert items == list(range(10))


def test_sample_fraction_repeats_with_same_seed_and_expected_size():
    items = list("abcdefghij")

    result = sample_fraction(items, 0.3, seed=7)

    assert result == sample_fraction(items, 0.3, seed=7)
    assert len(result) == 3


def test_sample_sequence_rejects_too_large_sample():
    with pytest.raises(ValueError):
        sample_sequence([1, 2], 3, seed=1)


def test_model_params_with_seed_adds_random_state_without_mutating_source():
    source_params = {"alpha": 0.1}

    result = model_params_with_seed(source_params, seed=21)

    assert result["random_state"] == 21
    assert source_params == {"alpha": 0.1}


def test_model_params_with_seed_keeps_explicit_random_state():
    result = model_params_with_seed({"random_state": 7}, seed=21)

    assert result["random_state"] == 7
