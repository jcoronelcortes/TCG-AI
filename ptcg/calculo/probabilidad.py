"""Hypergeometric probability of the draw.

Extracted VERBATIM from main.py by utils/extraer_definiciones.py
(docs/project-history.md). Its purity is verified by
utils/pureza.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.cartas.puntuacion import MAIN_ATTACKERS
from ptcg.cartas.ids import Basic_Grass_Energy, Hydrapple_ex, RETREAT_COST, Teal_Mask_Ogerpon_ex
from ptcg.calculo.tablero import _active_of
from ptcg.calculo.energia import _grass_ability_slots, _grass_attach_unit, _retreat_grass_units
from ptcg.calculo.dano import _attacker_base_damage, _ko_not_guaranteed, _our_effective_damage
from ptcg.calculo.carta import prize_count_op
from ptcg.estado.claves import ESTADO_MAZO, ESTADO_PREMIO
from ptcg.estado.agente import ESTADO
from ptcg.cartas.ids import FISHING_PRIZES_MIN, FISHING_PROB_MIN
from dataclasses import dataclass
from math import comb as _comb


def _prob_al_menos(successes, population, draws, k):
    """Hypergeometric: P(drawing AT LEAST `k` copies) when drawing `robo`
    cards from a deck of `poblacion` with `exitos` live copies.

    This is the ONLY place in the file where the agent reasons about chance;
    everything else decides from the visible board. `exitos` comes from the deck
    belief (`CARTAS_ACTIVAS_EN_MAZO`), which counts what has NOT been seen: deck
    + face-down prizes. That is why the caller also puts the prizes into
    `poblacion` -- from our side they are indistinguishable from deck cards --
    which leaves the estimate SLIGHTLY conservative (in registro_004: 11 unseen
    Grass out of 48 -> 0.60, against the real 0.63 of the 10 left in a 42-card
    deck). Conservative is what a gate wants."""
    if k <= 0:
        return 1.0
    if successes <= 0 or draws <= 0 or population <= 0 or k > successes:
        return 0.0
    draws = min(draws, population)
    if k > draws:
        return 0.0
    failures = population - successes
    total = _comb(population, draws)
    if total <= 0:
        return 0.0
    fewer_than_k = 0
    for i in range(0, k):
        if i > successes or (draws - i) > failures or (draws - i) < 0:
            continue
        fewer_than_k += _comb(successes, i) * _comb(failures, draws - i)
    return max(0.0, min(1.0, 1.0 - fewer_than_k / total))


@dataclass
class _FinisherFishing:
    """An attack that this turn depends ONLY on the draw bringing energy."""
    attacker_id: int
    from_bench: bool     # requires retreating the active to promote it
    cards_needed: int           # Grass the DRAW has to bring
    damage: int             # projected EFFECTIVE damage on the opposing active
    lethal: bool
    prizes: int          # prizes the KO takes (0 if not lethal)
    draws: int             # cards the refill draws
    outs: int             # live Grass in the deck after shuffling
    universe: int         # cards in the deck after shuffling the hand back
    prob: float


def _belief_deck_and_prizes():
    deck = 0
    prize = 0
    for counts in ESTADO.CARTAS_ACTIVAS_EN_MAZO.values():
        deck += counts.get(ESTADO_MAZO, 0)
        prize += counts.get(ESTADO_PREMIO, 0)
    return deck, prize


def _prob_draw_any(target_ids, draws=1):
    if draws <= 0:
        return 0.0
    if isinstance(target_ids, int):
        target_ids = (target_ids,)
    target_set = set(target_ids)
    deck = 0
    hits = 0
    for cid, counts in ESTADO.CARTAS_ACTIVAS_EN_MAZO.items():
        n = counts.get(ESTADO_MAZO, 0)
        deck += n
        if cid in target_set:
            hits += n
    if deck <= 0 or hits <= 0:
        return 0.0
    draws = min(draws, deck)
    miss = deck - hits
    p_none = 1.0
    for i in range(draws):
        denom = deck - i
        if denom <= 0:
            break
        p_none *= max(0, (miss - i)) / denom
    return 1.0 - p_none


def _prob_card_accessible(card_id):
    counts = ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(card_id)
    if not counts:
        return 0.0
    in_deck = counts.get(ESTADO_MAZO, 0)
    in_prize = counts.get(ESTADO_PREMIO, 0)
    copies = in_deck + in_prize
    if copies <= 0:
        return 0.0
    deck, prize = _belief_deck_and_prizes()
    total_hidden = deck + prize
    if total_hidden <= 0:
        return 1.0 if in_deck > 0 else 0.0
    if prize <= 0:
        return 1.0
    p_all_prized = 1.0
    for i in range(copies):
        denom = total_hidden - i
        if denom <= 0:
            p_all_prized = 0.0
            break
        p_all_prized *= max(0, (prize - i)) / denom
    return 1.0 - p_all_prized


def _finisher_fishing_valid(c):
    """The fishing is good enough to OVERRIDE Lillie's ordering vetoes.

    Gates (all required): a free Supporter slot; NO attack possible this turn
    (neither with the active nor by promoting an already charged benched body --
    if we can attack, the normal ladder rules); the plan TAKES a prize with
    probability >= `PESCA_PROB_MIN`; and no GUARANTEED finisher on the board
    (winning gust or dodge), which always beats a probable KO.

    `pending_evo` (a direct evolution in hand with its pre-evolution in play)
    also blocks: that evolution is played EARLIER by tier and the flag only
    clears on the next re-evaluation, so yielding here does not cost the
    finisher -- and if the evolution is NOT playable today, shuffling its pieces
    away would cost the line."""
    p = getattr(c, 'pesca_remate', None)
    return bool(p is not None
                and not c.state.supporterPlayed
                and not c.can_attack
                and not c.has_ready_bench_attacker
                and not getattr(c, 'pending_evo', False)
                and p.lethal
                and p.prizes >= FISHING_PRIZES_MIN
                and p.prob >= FISHING_PROB_MIN
                and not c.boss_win_via_bench
                and not c.win_via_boss_gust
                and not c.boss_dodge_redirect
                and not c.win_ko_active_via_promote)


def _finisher_fishing(my_state, op_state, state, hand_counts, field_counts,
                     grass_in_deck, draws, shuffles_hand=True,
                     meganium_in_play=False, neutralization_zone_active=False,
                     total_grass=0, bench_count=0, can_switch=False,
                     has_switch_card=False, abilities_off=False):
    """The BEST attack this turn's draw can unlock, with its probability.
    `None` if there is none.

    DAMAGE-AWARE sibling of `_plan_de_planta`: it shares its attachment
    arithmetic (cards = ceil(deficit / `_grass_attach_unit()`), routes that can
    be aimed at a specific body -- manual + Ripening Charge on each Hydrapple ex
    + Teal Dance only on the Ogerpon itself) and adds what that one does not
    look at: WHO is attacked, how much DAMAGE comes out and how many PRIZES it
    takes.

    It was born from registro_004 step 49 vs Marnie (LOST): Teal Mask Ogerpon ex
    ACTIVE with 1 energy (Myriad asks for 3), NOTHING charged on the bench, ZERO
    energy in hand and 6 prizes untouched -- Lillie's draws EIGHT with 10 live
    Grass in 42 cards: 63% of pulling the 2 that are missing. With them Myriad
    Leaf Shower hits 30 + 30 x (3 of ours + 2 of the opponent's) = 180, x2 for
    the Grass WEAKNESS of Marnie's Grimmsnarl ex = 360 >= 320 HP: TWO prizes.
    The agent played Boss's Orders to drag out a 70 HP Snorunt -- a gust that
    also DEGRADES the target (Myriad scales with the energy on the opposing
    active, and the Snorunt came with none) -- and then paid the Ultra Ball by
    discarding BOTH Lillie's, which were already dead cards with the Supporter
    spent.

    `baraja_la_mano=True` (Lillie's, Unfair Stamp) models the real cost of the
    refill: any Grass in hand goes BACK to the deck, so it does not count
    against the deficit and is added to the `outs`.

    The target is ALWAYS the CURRENT opposing active: the refill takes the
    Supporter slot, so there is no Boss's left to change it -- and that is
    exactly the point of the record (gusting changes the target for a worse
    one).
    """
    if op_state is None or not op_state.active or op_state.active[0] is None:
        return None
    target = op_state.active[0]
    if (target.hp or 0) <= 0:
        return None
    if draws <= 0:
        return None

    unit = _grass_attach_unit()
    manual_slots = 0 if state.energyAttached else 1
    n_hydrapple = 0 if abilities_off else field_counts.get(Hydrapple_ex, 0)
    ability_slots = (0 if abilities_off
                 else _grass_ability_slots(state, field_counts))
    slots_today = manual_slots + ability_slots
    if slots_today <= 0:
        return None                       # no route left to put energy in today

    grass_in_hand = hand_counts.get(Basic_Grass_Energy, 0)
    # With a refill that SHUFFLES the hand, the Grass in hand is lost as an
    # immediate resource and reappears as outs in the deck.
    useful_in_hand = 0 if shuffles_hand else grass_in_hand
    outs = grass_in_deck + (grass_in_hand if shuffles_hand else 0)
    # `grass_en_mazo` comes from the belief, which counts EVERYTHING unseen: deck +
    # prizes. The population has to count them the same way so the probability is
    # not inflated (see `_prob_al_menos`). The Supporter being played does not go
    # back to the deck: it is discarded, hence the -1.
    universe = max(1, (getattr(my_state, 'deckCount', 0) or 0)
                   + len(getattr(my_state, 'prize', None) or [])
                   + (max(0, len(my_state.hand or []) - 1) if shuffles_hand else 0))

    active = _active_of(my_state)
    # Cost of the retreat if the finisher is on the BENCH: it is paid with the
    # ACTIVE's energies (whole cards), and that lowers the Grass on the field that
    # Syrup Storm scales with.
    retreat_cost = 0 if has_switch_card else (
        RETREAT_COST.get(active.id, 1) if active is not None else 99)
    retreat_payable = (can_switch
                        and active is not None
                        and (has_switch_card
                             or len(active.energies) >= retreat_cost))
    grass_after_retreat = max(0, total_grass - (0 if has_switch_card
                                               else _retreat_grass_units(retreat_cost)))

    bodies = ([(active, True)] if active is not None else [])
    bodies += [(bp, False) for bp in (my_state.bench or [])]
    best, best_key = None, None
    for body, is_active in bodies:
        if body is None or body.id not in MAIN_ATTACKERS:
            continue
        if not is_active and not retreat_payable:
            continue                      # charged or not, it does not reach the front today
        req = ESTADO.ATTACK_ENERGY_REQ.get(body.id)
        if req is None:
            continue
        missing = req - len(body.energies)
        if missing <= 0:
            continue                      # already attacks: this is not fishing
        cards_needed = -(-missing // unit)
        # Routes that can point at THIS body today (same criterion as
        # `_plan_de_planta`): Teal Dance only charges its bearer.
        targetable = manual_slots + n_hydrapple
        if body.id == Teal_Mask_Ogerpon_ex and not abilities_off:
            targetable += 1
        targetable = min(targetable, slots_today)
        if cards_needed > targetable:
            continue                      # not even with every route does it attack today
        if cards_needed <= min(grass_in_hand, targetable):
            # The HAND already unlocks it: this is not fishing, it is a charge --
            # and with `baraja_la_mano` it would also be the worst possible
            # mistake (shuffling away exactly the energy that wins the turn).
            # The attachment scores in its own tier and is played EARLIER; if it
            # only covers part of the deficit, the later re-evaluation comes back
            # here with the attachment already spent and fewer cards to fish for.
            continue
        from_draw = cards_needed - min(useful_in_hand, targetable)
        if from_draw <= 0:
            continue                      # the hand alone unlocks it: not fishing
        if from_draw > draws:
            continue                      # it does not fit even drawing everything

        grass_scales = ((total_grass if is_active else grass_after_retreat)
                        + cards_needed * unit)
        energy_after = len(body.energies) + cards_needed * unit
        base = _attacker_base_damage(
            body.id, target, energy_after,
            grass_scale=grass_scales,
            teal_self_energy=len(body.energies) + cards_needed,
            bench_count=bench_count)
        if base <= 0:
            continue
        damage = _our_effective_damage(body, target, base, meganium_in_play,
                                     neutralization_zone_active)
        if damage <= 0:
            continue
        lethal = damage >= (target.hp or 0) and not _ko_not_guaranteed(target)
        prizes = prize_count_op(target) if lethal else 0
        prob = _prob_al_menos(outs, universe, draws, from_draw)
        if prob <= 0.0:
            continue
        # Best plan = the one that takes the most prizes; on a tie, the most PROBABLE
        # (fewer cards to fish for), and then the one that deals the most damage. The
        # ACTIVE is preferred over the benched relief: it does not pay a retreat.
        key = (1 if lethal else 0, prizes, round(prob, 6), damage,
                 0 if is_active else -1)
        if best_key is None or key > best_key:
            best_key = key
            best = _FinisherFishing(
                attacker_id=body.id, from_bench=not is_active,
                cards_needed=from_draw, damage=damage, lethal=lethal, prizes=prizes,
                draws=draws, outs=outs, universe=universe, prob=prob)
    return best

__all__ = [
    '_prob_al_menos',
    '_FinisherFishing',
    '_finisher_fishing_valid',
    '_belief_deck_and_prizes',
    '_prob_draw_any',
    '_prob_card_accessible',
    '_finisher_fishing',
]
