"""ENERGY: how much a body has, how much it can still get, what that pays for.

Energy is this deck's currency, and almost every wrong answer in this file
shows up as a projected knockout that does not happen. Four ideas run through
it; the rest is arithmetic on top of them.

1. EFFECTIVE vs PHYSICAL energy -- the distinction to keep straight.

   Meganium's Wild Growth makes each basic Grass count as {G}{G}, and the
   OBSERVATION ALREADY APPLIES IT: a body with one Grass card under a Meganium
   lists two entries in `energies`. So `len(energies)` is EFFECTIVE energy and
   can be compared to an attack cost directly, while the number of CARDS is
   `_physical_energy(len(energies))`.

   Which one a question wants depends on what is being spent. Attack costs and
   damage scaling are effective. Caps, retreat payment and anything that moves
   cards to the discard are physical -- a retreat paid under Meganium discards
   one card and removes TWO effective units, and confusing the two overstates
   the damage left on the field by exactly that factor.

   `_grass_attach_unit` is the bridge: what ONE freshly attached Grass is worth
   in effective terms, 2 with Meganium and 1 without.

2. THE THREE ATTACH ROUTES. Energy reaches a body by manual attachment (once a
   turn, any target), Ripening Charge (Hydrapple ex, any target) or Teal Dance
   (Ogerpon, itself only, and regardless of where it stands). The
   `_grass_ability_slots*` and `_grass_attach_slots_for` family counts how many
   of those are still open, per target. They estimate CONSERVATIVELY: an
   overshoot merely means a play is not proposed, while an undershoot would
   have the agent plan an attachment it cannot make.

3. REACHABLE energy. "Available energy" used to mean a Grass in hand with the
   attachment unspent, which cost a game -- energy in the DISCARD with a Night
   Stretcher in hand is just as available, and so is the energy the retreat
   under consideration is about to put there. The block introduced by
   `_grass_attach_slots_for` documents that loss and is the single answer to
   the question now.

4. THE CAPS. Bodies have matchup-dependent ceilings on how much energy is worth
   sinking into them (`_ogerpon_base_phys_cap`, `_ripen_energy_capped`). These
   are measured judgements, not card rules, and they exist so the deck does not
   pour its whole engine into a body that cannot convert it -- see the
   `topes-energia` family in the project's decision history.

STATE, NOT DATA: `AGENT_STATE.ATTACK_ENERGY_REQ` is the attack cost table FOR
THIS TURN, rebuilt from the base each turn so Nighttime Mine's +1 on our Tera
(`_aplicar_impuesto_tera`) cannot accumulate. It is also a CURATED list of the
bodies we genuinely attack with, which is why `_can_attack_eff` is not derived
from card data -- doing so would promote Meowth ex to an attacker in some
twenty places. `_min_attack_cost` is the deck-agnostic fallback for cards the
curated table has never heard of.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.state.agent_state import AGENT_STATE
from ptcg.cards.tables import attack_table, card_table
from ptcg.cards.ids import (Applin, Basic_Grass_Energy, Chikorita,
                            GRASS_DOUBLER_IDS, Hydrapple_ex, Night_Stretcher,
                            RETREAT_COST, Tapu_Bulu, Teal_Mask_Ogerpon_ex)
from ptcg.cards.groups import Nighttime_Mine, OUR_TERA_IDS
from ptcg.cards.costs import ATTACK_ENERGY_REQ_BASE
from ptcg.calc.board import _active_of
from cg.api import EnergyType


def _grass_mult():
    # The game observation ALREADY applies Meganium's Wild Growth: every PHYSICAL
    # basic Grass energy appears DUPLICATED in the `energies` list, so
    # len(energies) IS the EFFECTIVE energy. That is why this multiplier is 1
    # (it is kept as a function so the inherited `raw * _grass_mult()` sites keep
    # returning effective energy without being rewritten).
    return 1


def _ogerpon_base_phys_cap(meganium, is_hop):
    # BASE cap of PHYSICAL energies on a Teal Mask Ogerpon ex (user's rule).
    # With Meganium in play: 2 physical (Wild Growth doubles them => 4 effective,
    # more than enough for Myriad Leaf Shower, cost 3). Without Meganium: 3 vs the
    # Hop's deck ("it cannot have more than three energies attached") and 4 in the
    # other capped matchups (Alakazam). Single source of truth for the manual
    # attachment, Ripening Charge and Teal Dance.
    if meganium:
        return 2
    return 3 if is_hop else 4


def count_total_grass_energy(my_state) -> int:
    """Grass energy across our WHOLE field, active and bench together.

    The field total, not a per-body count, because our scaling attacks are
    written against the whole board: Syrup Storm reads this number, which is
    why paying a retreat anywhere can weaken an attack somewhere else.
    Effective units -- Wild Growth is already applied in the observation.
    """
    total = 0
    for pokemon in my_state.active + my_state.bench:
        if pokemon is None:
            continue
        for e in pokemon.energies:
            if e == EnergyType.GRASS:
                total += 1
    return total


def calc_syrup_storm_damage(my_state, has_meganium: bool) -> int:
    """Syrup Storm's damage: 30, plus 30 per Grass on our whole field.

    `has_meganium` IS DELIBERATELY INERT, and the empty branch below is what is
    left of the correction it used to apply. Wild Growth is already reflected
    in the observation, so the Grass count is effective before it gets here and
    doubling again would be counting Meganium twice.

    The parameter survives because ~all callers pass it positionally, and
    `tests/test_main_units.py` pins both values to the same answer so nobody
    re-introduces the double count. Do not delete it without that test.
    """
    total_grass = count_total_grass_energy(my_state)
    if has_meganium:

        pass
    return 30 + 30 * total_grass


def _grass_attach_unit():
    # EFFECTIVE energy provided by ONE freshly attached basic Grass energy (from
    # hand or recovered). With Meganium's Wild Growth in play one physical Grass
    # provides {G}{G} = 2 effective; without Meganium, 1.
    return 2 if AGENT_STATE.meganium_in_play else 1


def energy_after_evolution(pokemon, evo_card_id, grass_to_attach=0):
    """EFFECTIVE energy the body would count on THE INSTANT it evolves.

    `len(energies)` is already effective (the observation applies Wild Growth,
    see `_grass_mult`), and that is enough for every body ALREADY in play. It is
    not enough for the one we are about to create: the card being played may be
    the doubler ITSELF. A Bayleef carrying two physical Grass reads 2 effective
    today and swings Solar Beam -- cost 4 -- the moment it becomes a Meganium.
    Asking "can it attack once it evolves" with today's reading answers no, and
    the whole point of the question is the board AFTER the play.

    `grass_to_attach` is the number of PHYSICAL basic Grass the turn can still
    put on it (0 or 1: the manual attachment), converted at the rate that will
    be in force ONCE THE CARD IS DOWN -- which is why it is not simply
    `_grass_attach_unit()`: that reads the board of before the play.
    """
    unit = _grass_attach_unit()
    if pokemon is None:
        return max(0, grass_to_attach) * unit
    eff = len(getattr(pokemon, 'energies', None) or [])
    if evo_card_id in GRASS_DOUBLER_IDS and not AGENT_STATE.meganium_in_play:
        # Wild Growth switches on WITH this evolution: every physical Grass
        # already on the body goes from providing one to providing two.
        eff += sum(1 for _e in (getattr(pokemon, 'energyCards', None) or [])
                   if getattr(_e, 'id', 0) == Basic_Grass_Energy)
        unit = 2
    return eff + max(0, grass_to_attach) * unit


def _pending_grass_extra_eff(active, hand_grass, energy_attached):
    """EFFECTIVE Grass energy our ACTIVE can still gain THIS TURN, from the
    manual attachment AND from its own Teal Dance.

    SINGLE SOURCE OF TRUTH for the two places that ask "how hard does our active
    hit after finishing this turn's charging": the winning-gust detector
    (`_win_via_boss_gust` in agent()) and the gust TARGET scorer
    (`_ctx_gust_target`). They used to disagree -- the detector projected Teal
    Dance, the target scorer did not -- and the whole point of the Boss's is that
    the body we AIM AT is the body the detector promised (registro_014 step 154
    vs Alakazam, WON in spite of this: opponent on 2 prizes with a benched
    Fezandipiti ex, our active Ogerpon ex at 4 effective energy. The detector saw
    Teal Dance -> 6 effective -> Myriad Leaf Shower 30+30x6 = 210 = the exact HP
    of the Fezandipiti ex = the last two prizes, scored the Boss's as
    `winning_gust` 20000 and, on that promise, VETOED the Xerosic that caps
    Powerful Hand. The target scorer then read the same active as 4 effective
    energy -> 150 damage -> "no KO on the Fezandipiti" and gusted the Abra
    instead: one prize, and neither the game nor the cap).

    Teal Dance is only counted when the MAIN menu of this turn OFFERED the
    ability on this same body (`AGENT_STATE._td_ability_serial`, the way the rest
    of the file detects a usable ability): once used, the engine stops offering
    it and the projection switches itself off. Both charges come out of the SAME
    hand, hence the `min` against the Grass we hold.

    Returns EFFECTIVE energy (Wild Growth already applied by
    `_grass_attach_unit`), which is what `_attacker_base_damage` expects.
    """
    if active is None or hand_grass < 1:
        return 0
    manual = 1 if not energy_attached else 0
    teal = 1 if (getattr(active, 'id', None) == Teal_Mask_Ogerpon_ex
                 and AGENT_STATE._td_ability_serial is not None
                 and getattr(active, 'serial', None)
                 == AGENT_STATE._td_ability_serial) else 0
    return min(hand_grass, manual + teal) * _grass_attach_unit()


def _grass_ability_slots(state, field_counts):
    """Grass charging abilities (Teal Dance on each Teal Mask Ogerpon ex +
    Ripening Charge on each Hydrapple ex) that can STILL attach this turn.

    Each one is "once during your turn" and per Pokemon, so the capacity is the
    number of bearers in play. The ones already used are estimated from the
    logs: of all the Grass energies attached this turn, ONE is the manual
    attachment if `state.energyAttached` is already set; the rest can only have
    come from an ability. The estimate is conservative: if it overshoots, the
    play is simply not proposed (it never invents an impossible charge)."""
    capacidad = (field_counts.get(Teal_Mask_Ogerpon_ex, 0)
                 + field_counts.get(Hydrapple_ex, 0))
    usadas = AGENT_STATE._grass_attaches_this_turn - (1 if state.energyAttached else 0)
    return max(0, capacidad - max(0, usadas))


def _grass_ability_slots_active(state, my_state, field_counts):
    """Ability charges that can still put a Grass energy ON THE ACTIVE.

    A subset of `_grass_ability_slots`: Ripening Charge (Hydrapple ex) attaches
    to ANY of our Pokemon, so every bearer in play counts; Teal Dance (Teal Mask
    Ogerpon ex) attaches ONLY to itself, so it only counts when the Ogerpon IS
    the active.

    EACH CHARGE IS BILLED TO THE CAPACITY THAT SPENT IT (user, registro_004
    step 56, episode 92558163 vs a Marnie deck, LOST). The capacity above is a
    SUBSET -- only the routes that reach the active -- and the count of charges
    already used was the WHOLE set, so abilities that were never in this
    capacity were being subtracted from it. Two benched Teal Dances were enough
    to make a live Ripening Charge invisible: the function answered 0 while the
    engine was, at that very moment, asking us where to put that Ripening
    Charge's Grass. With the active Tapu Bulu one attachment short of Wood
    Hammer and their active at 70 HP, `_charge_active_finishes` never looked and
    the turn ended without attacking.

    So a Grass that landed on a BENCHED Teal Mask Ogerpon ex is credited to that
    Ogerpon's own dance -- at most one per body, and a route that could never
    have charged the active anyway -- and only the remainder is billed here.
    Deck-agnostic: it reads which of OUR bodies took a Grass this turn and what
    each of our two charging abilities can reach, nothing about the opponent.

    The estimate stays conservative in the same direction as before, capped by
    the total charges still alive (`_grass_ability_slots`). It can still run
    long in one ambiguous board -- a Ripening Charge aimed AT a benched Ogerpon
    reads exactly like that Ogerpon's dance -- and there it claims a route that
    is gone; what it can buy with it is nothing, since with no route left the
    engine offers no attachment for the preference to steer."""
    capacidad = field_counts.get(Hydrapple_ex, 0)
    _act = _active_of(my_state)
    if _act is not None and _act.id == Teal_Mask_Ogerpon_ex:
        capacidad += 1
    usadas = AGENT_STATE._grass_attaches_this_turn - (1 if state.energyAttached else 0)
    danced = sum(
        1 for _bp in (my_state.bench or [])
        if _bp is not None and _bp.id == Teal_Mask_Ogerpon_ex
        and getattr(_bp, 'serial', None)
        in AGENT_STATE._grass_attach_targets_this_turn)
    usadas = max(0, usadas) - danced
    return min(max(0, capacidad - max(0, usadas)),
               _grass_ability_slots(state, field_counts))


def _grass_attach_route_open(state, field_counts, abilities_off=False):
    """Whether there is any route to put ONE Grass energy from hand onto the
    field this turn: the manual attachment if it is still available, or a live
    charging ability."""
    if not state.energyAttached:
        return True
    if abilities_off:
        return False
    return _grass_ability_slots(state, field_counts) >= 1


def _physical_energy(effective_len):
    # Converts EFFECTIVE energy (len(energies), already doubled by OUR Meganium's
    # Wild Growth) into PHYSICAL energy cards. With Meganium each physical Grass
    # counts as 2 effective, so physical = effective // 2; without Meganium,
    # effective == physical.
    return effective_len // 2 if AGENT_STATE.meganium_in_play else effective_len


def _ripen_energy_capped(pokemon, ogerpon_phys_cap=None):
    """True if `pokemon` is already at its cap of physical energies, that is,
    if `energy_score` would veto sending it one more Grass. It mirrors the hard
    caps of energy_score (Chikorita 1, Applin 1, Tapu Bulu 2/4, Ogerpon by
    matchup) so that Ripening Charge's healing never points at a vetoed body.
    `ogerpon_phys_cap` is the matchup's PHYSICAL cap for Teal Mask Ogerpon ex
    (Cubchoo/Alakazam/Hop's); None = no matchup cap."""
    phys = _physical_energy(len(getattr(pokemon, 'energies', []) or []))
    pid = getattr(pokemon, 'id', 0)
    if pid in (Chikorita, Applin):
        return phys >= 1
    if pid == Tapu_Bulu:
        return phys >= (2 if AGENT_STATE.meganium_in_play else 4)
    if pid == Teal_Mask_Ogerpon_ex:
        if AGENT_STATE.op_is_crustle_deck and phys >= 2:
            return True
        if ogerpon_phys_cap is not None and phys >= ogerpon_phys_cap:
            return True
    return False


def _retreat_cards(retreat_cost):
    # Number of PHYSICAL energy cards needed to pay `retreat_cost` (expressed in
    # EFFECTIVE units). With Meganium each Grass pays for two (ceiling division).
    # 0 if the cost is <= 0.
    if retreat_cost <= 0:
        return 0
    return -(-retreat_cost // _grass_attach_unit())


def _retreat_grass_units(retreat_cost):
    """EFFECTIVE Grass units that DISAPPEAR from the field when paying a
    retreat of `retreat_cost` symbols.

    The cost is paid with whole CARDS, and with Meganium's Wild Growth each
    physical Grass is worth TWO units: retreating for ONE symbol erases TWO
    units from the count that Syrup Storm scales with. Subtracting the cost in
    symbols (or the number of cards) overestimates the damage by exactly that
    factor -- user, registro_006 step 78 vs Archaludon ex (LOST): the plan
    believed the benched Hydrapple ex knocked out (10-1 = 9 units -> 300 - 30
    resistance = 270 = exact HP) when the reality after retreating was 8 units
    -> 240, and the attack log confirms the 240."""
    return _retreat_cards(retreat_cost) * _grass_attach_unit()


# ---------------------------------------------------------------------------
# REACHABLE energy: the Grass a body can still receive THIS turn
# ---------------------------------------------------------------------------
# Why this block exists (user, registro_004 step 45 vs Mega Lucario ex, LOST).
# Board on our turn 4: active Teal Mask Ogerpon ex at 80/210 with ONE Grass (two
# effective with Meganium's Wild Growth, one short of Myriad's three), an
# untouched Ogerpon ex on the bench with another one, Night Stretcher in hand, no
# energy in hand and NO energy in the discard. Every scorer that had to answer
# "can anybody attack this turn?" answered no, the retreat was vetoed
# (retreat.py, `_has_ready_bench`), the turn plan read `prizes_today=0` and the
# turn ended without attacking. `utils/turn_explorer.py` on that same observation
# finds the prize:
#
#     RETREAT -> NIGHT STRETCHER -> TEAL DANCE -> ATTACK
#
# The retreat is what makes the rest legal. Paying it discards the Grass off the
# retreating body, and THAT is the card Night Stretcher brings back to hand for
# Teal Dance to attach to the promoted Ogerpon: two physical Grass = four
# effective >= the three of Myriad Leaf Shower. Before the retreat the discard
# held only trainers and the simulator did not even offer the Stretcher.
#
# So the mistake was never a missing rule, it was a definition: "available
# energy" meant `Basic_Grass_Energy in hand and not energyAttached`, copied into
# four scorers. Energy sitting in the discard with a Stretcher in hand is exactly
# as available -- and so is the energy the retreat we are weighing is about to
# put there. These three functions are the single answer to that question.

def _grass_attach_slots_for(pokemon, state, field_counts, abilities_off=False):
    """Attach routes that can still put a Grass energy ON `pokemon` this turn.

    Generalises the two counters above by TARGET. The manual attachment and
    Ripening Charge (Hydrapple ex) reach any of our Pokemon; Teal Dance attaches
    only to the Ogerpon that uses it, so it counts for that body alone -- and it
    counts wherever the body stands, because the ability does not care about the
    Active Spot (which is what makes the promoted attacker chargeable).

    Same conservative estimate of already-spent ability charges as
    `_grass_ability_slots`: if it overshoots, the play is simply not proposed.
    """
    slots = 0 if state.energyAttached else 1
    if abilities_off:
        return slots
    capacity = (field_counts or {}).get(Hydrapple_ex, 0)
    if pokemon is not None and getattr(pokemon, 'id', 0) == Teal_Mask_Ogerpon_ex:
        capacity += 1
    used = AGENT_STATE._grass_attaches_this_turn - (1 if state.energyAttached else 0)
    return slots + max(0, capacity - max(0, used))


def _retreat_grass_to_discard(pokemon):
    """PHYSICAL Grass cards that paying `pokemon`'s retreat sends to the discard.

    The counterpart of `_retreat_grass_units`, which answers what LEAVES the
    field; this one answers what ARRIVES in the discard, where Night Stretcher
    can reach it. Capped by what the body actually carries: a retreat it cannot
    pay is not offered by the simulator and must not be counted on here.
    """
    if pokemon is None:
        return 0
    needed = _retreat_cards(RETREAT_COST.get(getattr(pokemon, 'id', 0), 0))
    if needed <= 0:
        return 0
    carried = _physical_energy(len(getattr(pokemon, 'energies', []) or []))
    return min(needed, carried)


def _retreat_payable(pokemon):
    """Can `pokemon` pay its own retreat with the energy it carries?

    In a scorer the question is already answered -- the simulator only offers a
    retreat it can charge for -- but the turn plan weighs the PROMOTE route
    without a menu in front of it, and a route that cannot pay its first step is
    not a route.
    """
    if pokemon is None:
        return False
    needed = _retreat_cards(RETREAT_COST.get(getattr(pokemon, 'id', 0), 0))
    if needed <= 0:
        return True
    return _physical_energy(len(getattr(pokemon, 'energies', []) or [])) >= needed


def _retreat_cards_missing(pokemon):
    """PHYSICAL Grass cards `pokemon` still has to receive before it can retreat.

    THE COST IS PRINTED IN SYMBOLS AND PAID IN CARDS, and subtracting one from
    the other is the mistake this function exists to stop. Every rule that
    finances a retreat -- "the charge goes to the active until it can step
    aside" -- has to know how many CARDS are missing, and the obvious
    `RETREAT_COST[id] - physical_energy(...)` answers in neither unit: it
    subtracts cards from symbols. Without Meganium the two agree and the error
    is invisible; with Wild Growth in play each Grass pays for TWO symbols, so
    the wrong arithmetic asks for twice the Grass the retreat needs and the rule
    goes silent on a board it was written for.

    User, registro_008 step 105 vs Team Rocket (LOST, episode 92484395): active
    Hydrapple ex at 150/330 with one Grass (2 of its 3 retreat symbols), a
    healthy 330 twin on the bench that takes the same knockout, and exactly ONE
    Grass in hand. `_hydra_fragile_pivot` matched the board and its
    completability check demanded 3 - 1 = 2 Grass; the retreat needed
    ceil(3/2) - 1 = ONE. The pivot never fired, the wounded body stayed in
    front, attacked, and died to the reply for two prizes.

    0 when it can already pay -- the mirror of `_retreat_payable`, which is the
    same question asked as a yes/no.
    """
    if pokemon is None:
        return 0
    needed = _retreat_cards(RETREAT_COST.get(getattr(pokemon, 'id', 0), 0))
    if needed <= 0:
        return 0
    carried = _physical_energy(len(getattr(pokemon, 'energies', []) or []))
    return max(0, needed - carried)


def _reachable_grass_for(pokemon, state, my_state, hand_counts, field_counts,
                         extra_discard_grass=0, abilities_off=False):
    """PHYSICAL Basic Grass cards we can still ATTACH to `pokemon` this turn.

    Two ceilings, and the smaller one wins: the CARDS we can get into hand (the
    ones already there, plus one per Night Stretcher for every Grass in the
    discard) and the ROUTES that can put them on that body. `extra_discard_grass`
    is the retreat's own payment when the caller is weighing a retreat -- see the
    block comment above.

    Returns PHYSICAL cards; multiply by `_grass_attach_unit()` for effective
    energy. Deliberately left out: Lana's Aid and Ultra Ball, which also reach
    the discard or the deck but spend the Supporter slot or a two-card cost that
    the caller cannot see from here.
    """
    available = hand_counts.get(Basic_Grass_Energy, 0)
    stretchers = hand_counts.get(Night_Stretcher, 0)
    if stretchers > 0:
        in_discard = sum(1 for c in (getattr(my_state, 'discard', None) or [])
                         if getattr(c, 'id', 0) == Basic_Grass_Energy)
        available += min(stretchers, in_discard + max(0, extra_discard_grass))
    if available <= 0:
        return 0
    return min(available,
               _grass_attach_slots_for(pokemon, state, field_counts,
                                       abilities_off))


def _aplicar_impuesto_tera(stadium_cards) -> bool:
    """Raises the cost of our Tera by +1 if Nighttime Mine is on the field.

    Returns whether the mine is active. It must be called at the START of
    agent(), before any scoring: if it were done further down, the blocks that
    had already read the cost would keep the old value -- the same failure the
    `energy_score` ceiling documents (which is why it lives in the wrapper and
    not at the end of the function).
    """
    activa = any(getattr(c, 'id', 0) == Nighttime_Mine
                 for c in (stadium_cards or []))
    for _tid in OUR_TERA_IDS:
        _base = ATTACK_ENERGY_REQ_BASE.get(_tid)
        if _base is not None:
            AGENT_STATE.ATTACK_ENERGY_REQ[_tid] = _base + (1 if activa else 0)
    return activa


def _can_attack_eff(card_id, raw_energy):
    # True if the card can attack. raw_energy = len(energies) is ALREADY the
    # effective energy (the observation applies Wild Growth), so it is compared
    # directly.
    #
    # It is deliberately NOT generalised to `_min_attack_cost`:
    # `ATTACK_ENERGY_REQ` is not just card data, it is the CURATED list of "bodies
    # we really attack with". Meowth ex (which has an attack) is out precisely so
    # that no rule treats it as an attacker -- see the hard veto of Meowth ex on
    # the bench. Deriving the cost from card data here would turn it into an
    # attacker in ~20 places in the file.
    _req = AGENT_STATE.ATTACK_ENERGY_REQ.get(card_id)
    return _req is not None and raw_energy >= _req


def _min_attack_cost(card_id):
    """Minimum energy `card_id` needs in order to attack, DERIVED FROM THE
    CARD DATA (`card_table` -> attack ids -> `attack_table`).

    Deck-agnostic complement to `ATTACK_ENERGY_REQ`, which only covers the cards
    of the current deck.csv. It is used as a LAST resort, for bodies the curated
    configuration does not know (another deck loaded into deck.csv).

    Returns None when it cannot be known (unknown card, no attacks, or only
    zero-cost attacks -- there energy unlocks nothing).
    """
    data = card_table.get(card_id)
    if data is None:
        return None
    costs = []
    for _aid in (getattr(data, 'attacks', None) or []):
        _atk = attack_table.get(_aid)
        if _atk is None:
            continue
        _n = len(getattr(_atk, 'energies', None) or [])
        if _n > 0:
            costs.append(_n)
    return min(costs) if costs else None

__all__ = [
    '_grass_mult',
    '_ogerpon_base_phys_cap',
    'count_total_grass_energy',
    'calc_syrup_storm_damage',
    '_grass_attach_unit',
    'energy_after_evolution',
    '_pending_grass_extra_eff',
    '_grass_ability_slots',
    '_grass_ability_slots_active',
    '_grass_attach_route_open',
    '_physical_energy',
    '_can_attack_eff',
    '_aplicar_impuesto_tera',
    '_min_attack_cost',
    '_ripen_energy_capped',
    '_retreat_cards',
    '_retreat_grass_units',
    '_grass_attach_slots_for',
    '_retreat_grass_to_discard',
    '_retreat_payable',
    '_retreat_cards_missing',
    '_reachable_grass_for',
]
