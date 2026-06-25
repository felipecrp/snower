from abc import ABC, abstractmethod
from enum import Enum
from typing import Iterable


class Decision(str, Enum):
    """Three-state screening outcome for a paper."""

    included = "included"
    excluded = "excluded"
    undecided = "undecided"


class DecisionStrategyType(str, Enum):
    """Persisted key identifying which consensus algorithm a project uses."""

    majority = "majority"
    consensus = "consensus"


class DecisionStrategy(ABC):
    """Base class for decision strategies."""

    @abstractmethod
    def decide(self, reviews: Iterable) -> Decision:
        """Compute a Decision from an iterable of Assessment objects."""


class MajorityStrategy(DecisionStrategy):
    """Included if more reviews favour inclusion; excluded if more favour exclusion; tie → undecided."""

    def decide(self, reviews: Iterable) -> Decision:
        inclusions = 0
        exclusions = 0
        for r in reviews:
            if r.included:
                inclusions += 1
            else:
                exclusions += 1
        if inclusions > exclusions:
            return Decision.included
        if exclusions > inclusions:
            return Decision.excluded
        return Decision.undecided


class ConsensusStrategy(DecisionStrategy):
    """All present reviews must agree; any disagreement or no reviews → undecided."""

    def decide(self, reviews: Iterable) -> Decision:
        seen: list[bool] = [r.included for r in reviews]
        if not seen:
            return Decision.undecided
        if all(seen):
            return Decision.included
        if not any(seen):
            return Decision.excluded
        return Decision.undecided


_REGISTRY: dict[DecisionStrategyType, DecisionStrategy] = {
    DecisionStrategyType.majority: MajorityStrategy(),
    DecisionStrategyType.consensus: ConsensusStrategy(),
}


def strategy_for(type: DecisionStrategyType) -> DecisionStrategy:
    """Return the singleton strategy instance for the given type."""
    return _REGISTRY[type]
