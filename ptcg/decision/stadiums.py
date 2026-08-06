"""Stadiums: Forest of Vitality and Grand Tree.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.state.agent_state import AGENT_STATE
from ptcg.cards.ids import Forest_of_Vitality
from cg.api import AreaType
from typing import NamedTuple
from ptcg.cards.ids import Applin, Bayleef, Chikorita, Dipplin, Hydrapple_ex, Meganium, Poke_Pad, Ultra_Ball
from ptcg.cards.tables import card_table
from ptcg.state.zones import ZONE_DECK


class _GrandTreePlan(NamedTuple):
    """One concrete execution of the Grand Tree ability."""
    area: int          # AreaType of the Basic to evolve (ACTIVE / BENCH)
    index: int         # index inside that area
    serial: int        # serial of the Basic (stable identity between calls)
    basic_id: int
    stage1_id: int
    stage2_id: int     # 0 = the chain stops EXPRESSLY at Stage 1
    value: int
    # Preference between two plans of EQUAL value, which in practice means two
    # copies of the same Basic: `evolution_body_bias` (the damaged body is the
    # one that gains from evolving, the intact one is the one that can wait).
    # It is kept OUT of `value` on purpose -- the value scale moves in steps of
    # 1200-2000 between chains and a body term must not perturb the choice of
    # CHAIN, only the choice of body inside it.
    body_bias: int = 0


def _gt_slots_propios(my_state):
    """`(area, index, pokemon)` of every Pokemon of ours in play."""
    output = []
    active = (my_state.active[0]
              if getattr(my_state, 'active', None) else None)
    if active is not None:
        output.append((AreaType.ACTIVE, 0, active))
    for k, pkmn in enumerate(getattr(my_state, 'bench', None) or []):
        if pkmn is not None:
            output.append((AreaType.BENCH, k, pkmn))
    return output


def _gt_body_value(card_id):
    """Deck-agnostic value of the body an evolution leaves behind: HP (dominant
    term) + a bonus for having an Ability. Printed damage is not used because
    the attacks that scale (Syrup Storm, Do the Wave) declare it as 0."""
    data = card_table.get(card_id)
    if data is None:
        return 0
    value = data.hp or 0
    if getattr(data, 'skills', None):
        value += 40
    return value


def _gt_prizes_of(card_id):
    """Prizes that card hands over when knocked out (without tools or denial:
    here it is only used to compare Basic vs evolution)."""
    data = card_table.get(card_id)
    if data is None:
        return 1
    return 3 if data.megaEx else 2 if data.ex else 1


def _fv_evolution_chain(c):
    """Playing Forest enables evolving some line present THIS turn (or one that
    can be put down from hand by chaining basic+evolution)."""
    h, f = c.hand_counts, c.field_counts
    meg_fetchable = (
        c.cards_in_deck.get(Meganium, {}).get(ZONE_DECK, 0) > 0 and
        (h.get(Poke_Pad, 0) >= 1 or h.get(Ultra_Ball, 0) >= 1))
    if f.get(Chikorita, 0) >= 1 and not c.meganium_in_play:
        if h.get(Bayleef, 0) >= 1 or h.get(Meganium, 0) >= 1:
            return True
    if f.get(Bayleef, 0) >= 1 and not c.meganium_in_play:
        if h.get(Meganium, 0) >= 1 or meg_fetchable:
            return True
    if f.get(Applin, 0) >= 1:
        if h.get(Dipplin, 0) >= 1 or h.get(Hydrapple_ex, 0) >= 1:
            return True
    if f.get(Dipplin, 0) >= 1 and not c.has_hydrapple:
        if h.get(Hydrapple_ex, 0) >= 1:
            return True
    if (h.get(Chikorita, 0) >= 1 and
            f[Chikorita] + f[Bayleef] + f[Meganium] == 0 and
            h.get(Bayleef, 0) >= 1):
        return True
    if (h.get(Applin, 0) >= 1 and
            f[Applin] + f[Dipplin] == 0 and
            h.get(Dipplin, 0) >= 1):
        return True
    return False


def _v_fv_neutralization(c):
    f = c.field_counts
    if (f.get(Chikorita, 0) >= 1 or f.get(Applin, 0) >= 1
            or f.get(Dipplin, 0) >= 1):
        return 29000
    return 28000


def _v_fv_chain(c):
    v = 22000 if c.stadium_id != 0 else 21900
    if c.op_is_fire_deck or c.op_is_aggro_deck or c.op_is_beedrill_deck:
        v += 200
    return v


def _v_fv_temprano(c):
    if c.op_is_fire_deck or c.op_is_aggro_deck or c.op_is_mirror:
        return 15000
    return 14000


def _forest_disponible(c):
    return AGENT_STATE.forest_in_play or c.hand.get(Forest_of_Vitality, 0) >= 1

__all__ = [
    '_GrandTreePlan',
    '_gt_slots_propios',
    '_gt_body_value',
    '_gt_prizes_of',
    '_fv_evolution_chain',
    '_v_fv_neutralization',
    '_v_fv_chain',
    '_v_fv_temprano',
    '_forest_disponible',
]
