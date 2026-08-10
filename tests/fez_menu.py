"""The menu one action AFTER Flip the Script, for the Meowth ex engine tests.

Since `_TIER_FEZ_BEFORE_SEARCH` (`ptcg/turn/finalize.py`, august 2026) a live
Flip the Script is cashed BEFORE a Meowth ex is benched to search for a
Supporter: the draw is free, it brings three cards to the one the search brings,
and it may make the search -- and the two-prize body it costs -- unnecessary.

So on any board that offers both, the answer to the first menu is the ability.
That is an ORDER, not a value: what the Meowth engines guard is WHETHER the body
is benched at all, and that question is now read one action later. Flip the
Script is ONCE PER TURN, so at that point the ability is simply no longer in the
menu -- which is exactly what `sin_flip_the_script` builds.

It is not a mutation of the board: no card moves, no counter changes. Only the
option that has already been spent is gone.
"""

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m  # noqa: E402

_ABILITY = 10
_ACTIVE = 4
_BENCH = 5


def _es_flip_the_script(opt, mine):
    if opt.get("type") != _ABILITY:
        return False
    area = opt.get("area")
    if area == _ACTIVE:
        cuerpos = mine.get("active") or []
    elif area == _BENCH:
        cuerpos = mine.get("bench") or []
    else:
        return False
    idx = opt.get("index", -1)
    return (0 <= idx < len(cuerpos)
            and cuerpos[idx] is not None
            and cuerpos[idx].get("id") == m.Fezandipiti_ex)


def sin_flip_the_script(obs):
    """The same observation with the Fezandipiti ex ability already cashed."""
    o = copy.deepcopy(obs)
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    o["select"]["option"] = [
        opt for opt in o["select"]["option"]
        if not _es_flip_the_script(opt, mine)]
    return o


def ofrece_flip_the_script(obs):
    """Is the ability on this menu at all? (the premise of the order)."""
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    return any(_es_flip_the_script(opt, mine)
               for opt in obs["select"]["option"])


__all__ = ['sin_flip_the_script', 'ofrece_flip_the_script']
