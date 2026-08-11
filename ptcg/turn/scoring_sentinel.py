"""The `_SALTAR` sentinel of the scoring chain, in its own module.

It lives apart from the dispatcher and the branches FOR A REASON: the branches
(`ptcg/turn/options/*.py`) return it and whoever calls the dispatcher checks
it. If it lived in `scoring.py`, the dispatcher would import the branches and
the branches would import the dispatcher -- a circular import.

It means "this branch already did its own `scores.append`"; it is what used to
be a `continue` in the original loop of `agent()`.
"""

_SALTAR = object()


__all__ = ['_SALTAR']
