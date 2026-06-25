from snower.decision import ConsensusStrategy, Decision, MajorityStrategy
from snower.review import Assessment, Criterion, CriterionType, Phase


def _inclusion():
    return Assessment(
        criterion=Criterion(id="ic1", name="Peer reviewed", type=CriterionType.inclusion),
        phase=Phase(id="title", name="Title screening"),
    )


def _exclusion():
    return Assessment(
        criterion=Criterion(id="ec1", name="Out of scope", type=CriterionType.exclusion),
        phase=Phase(id="title", name="Title screening"),
    )


class DescribeMajorityStrategy:
    def it_returns_included_when_more_inclusions(self):
        s = MajorityStrategy()
        assert s.decide([_inclusion(), _inclusion(), _exclusion()]) == Decision.included

    def it_returns_excluded_when_more_exclusions(self):
        s = MajorityStrategy()
        assert s.decide([_exclusion(), _exclusion(), _inclusion()]) == Decision.excluded

    def it_returns_undecided_on_a_tie(self):
        s = MajorityStrategy()
        assert s.decide([_inclusion(), _exclusion()]) == Decision.undecided

    def it_returns_undecided_with_no_reviews(self):
        s = MajorityStrategy()
        assert s.decide([]) == Decision.undecided


class DescribeConsensusStrategy:
    def it_returns_included_when_all_agree_on_inclusion(self):
        s = ConsensusStrategy()
        assert s.decide([_inclusion(), _inclusion()]) == Decision.included

    def it_returns_excluded_when_all_agree_on_exclusion(self):
        s = ConsensusStrategy()
        assert s.decide([_exclusion(), _exclusion()]) == Decision.excluded

    def it_returns_undecided_on_mixed_reviews(self):
        s = ConsensusStrategy()
        assert s.decide([_inclusion(), _exclusion()]) == Decision.undecided

    def it_returns_undecided_with_no_reviews(self):
        s = ConsensusStrategy()
        assert s.decide([]) == Decision.undecided

    def it_returns_included_for_a_single_inclusion_review(self):
        s = ConsensusStrategy()
        assert s.decide([_inclusion()]) == Decision.included

    def it_returns_excluded_for_a_single_exclusion_review(self):
        s = ConsensusStrategy()
        assert s.decide([_exclusion()]) == Decision.excluded
