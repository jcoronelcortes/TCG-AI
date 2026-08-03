"""Dano: base de nuestros atacantes, KO no garantizado y snipe.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from typing import NamedTuple
from ptcg.cartas.ids import Mega_Hawlucha_ex, Survival_Brace


def _powerful_hand_proyectado(op_hand_count: int) -> int:
    """Dano de Powerful Hand proyectado al PROXIMO turno rival.

    Mismo modelo que `_op_active_attack_damage_to`: 20 x (mano + 2), donde el
    +2 es el robo del turno + el Psychic Draw de evolucionar. Vive suelto (y no
    detras de "su activo es un Alakazam") porque el Alakazam que rematara puede
    estar todavia en la BANCA rival: en su turno promueve, evoluciona y ataca.
    Dentro del matchup `op_is_alakazam_deck` es la unica linea atacante del
    mazo (Abra -> Kadabra -> Alakazam), asi que proyectarla siempre es correcto.
    """
    return 20 * (max(0, op_hand_count) + 2)


def _ko_no_garantizado(op_pokemon):
    """True si el KO del defensor NO esta garantizado aunque el dano proyectado
    sea letal: Mega Hawlucha ex (Tenacious Body: moneda, con cara sobrevive a
    10 PV) o Survival Brace (tool 1155: a vida completa sobrevive a 10 PV).

    Lo consultan SOLO los evaluadores de REMATE que declaran victoria segura
    (`wins_now`, SCORE_WIN_GAME, `_active_attack_wins_now`): contra estos
    cuerpos "ganar este turno" puede fallar y regalar el turno de vuelta. El
    dano/can_ko normal NO se toca (atacarlos sigue siendo la mejor jugada la
    mayoria de veces). Los que sobreviven a vida completa via Sturdy/Resolute
    Heart (FULL_HP_SURVIVE_IDS) no necesitan este predicado porque
    `_our_effective_damage` ya capa su dano a hp-10 y el can_ko sale False."""
    if op_pokemon is None:
        return False
    if op_pokemon.id == Mega_Hawlucha_ex:
        return True
    if (op_pokemon.hp == op_pokemon.maxHp
            and any(getattr(_t, 'id', 0) == Survival_Brace
                    for _t in (getattr(op_pokemon, 'tools', None) or []))):
        return True
    return False


class _ProjTarget(NamedTuple):
    """Objetivo ligero para proyectar el dano rival contra un cuerpo que aun no
    esta en juego (p.ej. la EVOLUCION de una pre-evo de banca). Solo necesita
    `id` (para debilidad/resistencia via card_table); `tools`/`energies` vacios."""
    id: int
    tools: tuple = ()
    energies: tuple = ()


def _snipe_targets(op_state):
    """Pokemon rivales alcanzables por un ataque-snipe: activo + banca."""
    out = []
    if op_state is None:
        return out
    for _p in (list(getattr(op_state, 'active', None) or [])
               + list(getattr(op_state, 'bench', None) or [])):
        if _p is not None:
            out.append(_p)
    return out

__all__ = [
    '_powerful_hand_proyectado',
    '_ProjTarget',
    '_ko_no_garantizado',
    '_snipe_targets',
]
