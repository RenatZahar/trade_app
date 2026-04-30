import random
from collections.abc import Sequence
from typing import Any
from typing import TypeVar

T = TypeVar("T")


def sample_sequence(items: Sequence[T], sample_size: int, seed: int | None = None) -> list[T]:
    if sample_size < 0:
        raise ValueError("sample_size must be greater than or equal to 0")
    if sample_size > len(items):
        raise ValueError("sample_size must not be greater than items length")

    rng = random.Random(seed)
    return rng.sample(list(items), sample_size)


def sample_fraction(items: Sequence[T], fraction: float, seed: int | None = None) -> list[T]:
    if not 0 <= fraction <= 1:
        raise ValueError("fraction must be between 0 and 1")

    return sample_sequence(items, int(len(items) * fraction), seed=seed)


def model_params_with_seed(model_params: dict[str, Any], seed: int | None = None) -> dict[str, Any]:
    params = dict(model_params)
    if seed is not None:
        params.setdefault("random_state", seed)
    return params
