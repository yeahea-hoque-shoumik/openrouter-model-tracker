from typing import NamedTuple


class Diff(NamedTuple):
    newly_free: frozenset[str]
    became_paid: frozenset[str]
    removed: frozenset[str]

    def __bool__(self) -> bool:
        return bool(self.newly_free or self.became_paid or self.removed)


def compute_diff(previous_free: set[str], current_free: set[str], all_ids: set[str]) -> Diff:
    """Compare the stored free set with the fetched one.

    A model that left the free set is `became_paid` if it is still listed in
    the catalog (`all_ids`), otherwise `removed`.
    """
    dropped = previous_free - current_free
    return Diff(
        newly_free=frozenset(current_free - previous_free),
        became_paid=frozenset(dropped & all_ids),
        removed=frozenset(dropped - all_ids),
    )
