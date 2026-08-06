"""Grass plan: how many Grass energies the field can use and whether they unlock today.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.state.agent_state import AGENT_STATE
from ptcg.cards.scoring import MAIN_ATTACKERS
from ptcg.cards.ids import Basic_Grass_Energy, Hydrapple_ex, Teal_Mask_Ogerpon_ex
from ptcg.calc.board import _active_of
from ptcg.calc.energy import _grass_ability_slots, _grass_attach_unit
from dataclasses import dataclass


@dataclass
class _PlanPlanta:
    """Reading of the BOARD in ENERGY terms (see `_grass_plan`)."""
    unit: int              # EFFECTIVE energy provided by ONE physical Grass
    in_hand: int             # Grass already available in hand
    slots_today: int           # Grass attachments that still fit THIS turn
    new_useful_today: int   # NEW Grass that would reach the field TODAY
    unlocks_today: bool     # a NEW Grass puts a body in attack range TODAY
    cards_to_attack: int  # NEW Grass that this unlock requires
    pendiente: int           # Grass demanded by every attacker in play
    demanda: int             # NEW Grass the board can use (<= `cap`)


def _grass_plan(my_state, state, field_counts, hand_counts, cap=3,
                    can_switch=False, abilities_off=False):
    """How many NEW Grass energies the board can use, and whether any of them
    UNLOCKS an attack TODAY.

    This is the board reading shared by the decision to PLAY a recovery card
    (`_score_lanas_aid_play`) and the decision of WHAT to recover with it (the
    `Lanas_Aid` branch of the TO_HAND context). It was born from registro_018
    step 118 vs Crustle (LOST): with Lana's Aid already played, the agent picked
    2 Applin + 1 Dipplin out of the discard -- with a FULL bench, cards that
    cannot be put into play -- while a Tapu Bulu was active ONE Grass away from
    firing Wood Hammer and three Grass energies sat in the discard. The
    selection branch did not look at energy at all (it fell through to the
    generic scorer, which scores "shapes of an evolution line"), and the play
    branch only knew how to read Hydrapple ex.

    Ways a Grass energy in HAND can reach the field in one turn:
      * the MANUAL attachment, if it has not been spent yet
        (`state.energyAttached`);
      * a live charging ability (`_grass_ability_slots`): *Teal Dance* on each
        Teal Mask Ogerpon ex (which only charges ITSELF) and *Ripening Charge*
        on each Hydrapple ex (which charges ANY of ours).

    `len(energies)` is ALREADY effective energy and `_grass_attach_unit()` is
    what ONE PHYSICAL Grass adds (2 with Meganium in play), so a body's deficit
    is measured in CARDS: `ceil((req - effective) / unit)`.

    Only `MAIN_ATTACKERS` bodies count: that is the curated list of "who we
    really attack with", so a benched Chikorita or Applin never invents energy
    demand (`ATTACK_ENERGY_REQ` does assign them a cost).

    `unlocks_today` only looks at the ACTIVE, unless `can_switch` says a
    retreat/switch is available: a charged benched attacker does not attack
    today if it cannot come up. Benched bodies do always add to `pendiente`,
    which is two-turn demand.

    `abilities_off` (Team Rocket's Watchtower / Iron Thorns active, the
    `meowth_ability_lock` flag) erases both ABILITY routes: with the lock on,
    only the manual attachment is left, and treating Teal Dance/Ripening as
    alive invents unlocks that do not exist.
    """
    unit = _grass_attach_unit()
    in_hand = hand_counts.get(Basic_Grass_Energy, 0)
    slots_manual = 0 if state.energyAttached else 1
    slots_hab = (0 if abilities_off
                 else _grass_ability_slots(state, field_counts))
    slots_today = slots_manual + slots_hab
    new_useful_today = max(0, slots_today - in_hand)
    n_hydrapple = 0 if abilities_off else field_counts.get(Hydrapple_ex, 0)

    unlocks_today = False
    cards_to_attack = 0
    pendiente = 0
    active = _active_of(my_state)
    bodies = ([(active, True)] if active is not None else [])
    bodies += [(bp, False) for bp in (my_state.bench or [])]
    for body, is_active in bodies:
        if body is None or body.id not in MAIN_ATTACKERS:
            continue
        req = AGENT_STATE.ATTACK_ENERGY_REQ.get(body.id)
        if req is None:
            continue
        missing = req - len(body.energies)
        if missing <= 0:
            continue                     # already attacks: asks for no energy
        cards = -(-missing // unit)     # ceiling of the division
        pendiente += cards
        if not is_active and not can_switch:
            continue                     # charged or not, it does not attack today
        # Routes that can point at THIS body today. Teal Dance only charges its own
        # bearer; the manual attachment and Ripening Charge, anyone.
        dirigibles = slots_manual + n_hydrapple
        if body.id == Teal_Mask_Ogerpon_ex and not abilities_off:
            dirigibles += 1
        dirigibles = min(dirigibles, slots_today)
        if cards > dirigibles:
            continue                     # not even with every route does it attack today
        nuevas = cards - min(in_hand, dirigibles)
        if nuevas <= 0 or nuevas > new_useful_today:
            continue                     # the hand alone already unlocks it / does not fit
        if not unlocks_today or nuevas < cards_to_attack:
            unlocks_today = True
            cards_to_attack = nuevas

    # DEMAND is what the bodies ask for, not this turn's attachment capacity: the
    # recovery goes to the HAND, and a Grass energy kept there still works next
    # turn. With every attacker charged the demand is 0 and energy stops being
    # worth anything.
    return _PlanPlanta(
        unit=unit, in_hand=in_hand, slots_today=slots_today,
        new_useful_today=new_useful_today,
        unlocks_today=unlocks_today,
        cards_to_attack=cards_to_attack,
        pendiente=pendiente,
        demanda=min(cap, max(0, pendiente - in_hand)))

__all__ = [
    '_PlanPlanta',
    '_grass_plan',
]
