"""Scoring one menu option: dispatch table by `o.type`.

Every large branch lives in `ptcg/turn/options/<type>.py` and receives the
same context; the short ones live together in `menores.py`. This used to be an
if/elif chain of 6,628 lines in a single file: to touch how a retreat is scored
you had to go in there and locate its 1,425.

Each module unpacks from the context ONLY the fields it reads and returns ONLY
the ones it reassigns. That is equivalent to the single write-back of before: a
branch that does not touch a field leaves it as it was.
"""

from cg.api import OptionType

from ptcg.turn.options import card
from ptcg.turn.options import play
from ptcg.turn.options import attach
from ptcg.turn.options import evolve
from ptcg.turn.options import ability
from ptcg.turn.options import retreat
from ptcg.turn.options import attack
from ptcg.turn.options import minor
from ptcg.turn.scoring_sentinel import _SALTAR  # noqa: F401


_TABLE = {
    OptionType.CARD: card.score_play,
    OptionType.PLAY: play.score_play,
    OptionType.ATTACH: attach.score_play,
    OptionType.EVOLVE: evolve.score_play,
    OptionType.ABILITY: ability.score_play,
    OptionType.RETREAT: retreat.score_play,
    OptionType.ATTACK: attack.score_play,
}


def score_option(tc, o, score):
    """Score of option `o`. Higher = better; negative = veto.

    It may return `_SALTAR`, in which case the caller must NOT append anything.
    """
    fn = _TABLE.get(o.type)
    return fn(tc, o, score) if fn is not None else minor.score_play(tc, o, score)


__all__ = ['score_option', '_SALTAR']
