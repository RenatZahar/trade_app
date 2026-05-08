"""Collector contract and selection for main-pipeline training data.

Responsibility:
- choose the active data collector (`legacy`, later `wallet-stats`);
- define the request/result boundary between orchestration and data collection;
- adapt collector-specific implementations to one downstream contract:
  train DataFrame + profit-test DataFrame + metadata.

Non-responsibility:
- do not run model training, evaluation, or model saving here;
- do not put low-level SQL/Dask transformation helpers here unless they are
  private to one collector implementation.
"""

from dataclasses import dataclass, field
import logging

from . import wallet_stats_operations as wallet_stats_ops


DEFAULT_COLLECTOR = "legacy"
WALLET_STATS_COLLECTOR = "wallet-stats"
SUPPORTED_COLLECTORS = (DEFAULT_COLLECTOR, WALLET_STATS_COLLECTOR)

logger = logging.getLogger("app")


@dataclass(frozen=True)
class CollectorRequest:
    test_fraction: float
    filter_params: dict
    correlation_type: str
    time_window: dict
    chunk_size: int
    seed: int | None = None


@dataclass(frozen=True)
class CollectedTrainingData:
    train_df: object
    profit_test_df: object
    metadata: dict = field(default_factory=dict)


def normalize_collector_name(collector_name):
    collector = collector_name or DEFAULT_COLLECTOR
    return collector.strip().lower()


def collect_correlation_training_data(
    collector_name,
    request: CollectorRequest,
):
    collector = normalize_collector_name(collector_name)
    logger.info("Active main pipeline collector: %s", collector)

    if collector == DEFAULT_COLLECTOR:
        from . import data_operations as do

        train_df, profit_test_df = do.get_corelation_by_tmsp_df(
            request.test_fraction,
            request.filter_params,
            request.correlation_type,
            request.time_window,
            request.chunk_size,
            seed=request.seed,
        )
        return CollectedTrainingData(
            train_df=train_df,
            profit_test_df=profit_test_df,
            metadata={
                "collector": collector,
                "source": "data_operations.get_corelation_by_tmsp_df",
            },
        )

    if collector == WALLET_STATS_COLLECTOR:
        train_df, profit_test_df, metadata = (
            wallet_stats_ops.collect_correlation_training_data_with_wallet_stats(
                request,
            )
        )
        return CollectedTrainingData(
            train_df=train_df,
            profit_test_df=profit_test_df,
            metadata=metadata,
        )

    raise ValueError(
        f"Unknown main pipeline collector: {collector}. "
        f"Supported collectors: {', '.join(SUPPORTED_COLLECTORS)}"
    )
