"""Scoring one menu option: dispatch table by `o.type`.

Every large branch lives in `ptcg/turno/opciones/<type>.py` and receives the
same context; the short ones live together in `menores.py`. This used to be an
if/elif chain of 6,628 lines in a single file: to touch how a retreat is scored
you had to go in there and locate its 1,425.

Each module unpacks from the context ONLY the fields it reads and returns ONLY
the ones it reassigns. That is equivalent to the single write-back of before: a
branch that does not touch a field leaves it as it was.
"""

from cg.api import OptionType

from ptcg.turno.opciones import card
from ptcg.turno.opciones import play
from ptcg.turno.opciones import attach
from ptcg.turno.opciones import evolve
from ptcg.turno.opciones import ability
from ptcg.turno.opciones import retreat
from ptcg.turno.opciones import attack
from ptcg.turno.opciones import menores
from ptcg.turno.puntuacion_centinela import _SALTAR  # noqa: F401


_TABLA = {
    OptionType.CARD: card.puntuar,
    OptionType.PLAY: play.puntuar,
    OptionType.ATTACH: attach.puntuar,
    OptionType.EVOLVE: evolve.puntuar,
    OptionType.ABILITY: ability.puntuar,
    OptionType.RETREAT: retreat.puntuar,
    OptionType.ATTACK: attack.puntuar,
}


def puntuar_opcion(tc, o, score):
    """Score of option `o`. Higher = better; negative = veto.

    It may return `_SALTAR`, in which case the caller must NOT append anything.
    """
    fn = _TABLA.get(o.type)
    return fn(tc, o, score) if fn is not None else menores.puntuar(tc, o, score)


__all__ = ['puntuar_opcion', '_SALTAR']
