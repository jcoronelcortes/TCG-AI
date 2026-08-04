"""Puntuacion de una opcion del menu: tabla de despacho por `o.type`.

Cada rama grande vive en `ptcg/turno/opciones/<tipo>.py` y recibe el mismo
contexto; las cortas van juntas en `menores.py`. Antes era una cadena
if/elif de 6.628 lineas en un solo archivo: para tocar como se puntua una
retirada habia que entrar ahi y localizar sus 1.425.

Cada modulo desempaqueta del contexto SOLO los campos que lee y devuelve
SOLO los que reasigna. Es equivalente al write-back unico de antes: una
rama que no toca un campo lo deja como estaba.
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
    """Puntaje de la opcion `o`. Mayor = mejor; negativo = veto.

    Puede devolver `_SALTAR`, y entonces el llamador NO debe apilar nada.
    """
    fn = _TABLA.get(o.type)
    return fn(tc, o, score) if fn is not None else menores.puntuar(tc, o, score)


__all__ = ['puntuar_opcion', '_SALTAR']
