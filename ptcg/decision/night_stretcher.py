"""NIGHT STRETCHER: pull one Pokemon or one basic Energy out of the discard.

An Item, so it is free in tempo terms -- the whole decision is about WHAT to
recover and whether recovering anything helps THIS turn. Like the Ultra Ball,
it is two decisions at two different menus: playing the card, and then choosing
its target.

THE SPLIT THAT ORGANISES THE FILE. The card can bring back a BODY or an
ENERGY, and those are judged completely differently:

  * ENERGY (`_ns_e_*`) -- worth it only if the Grass DOES something today, and
    each `_ns_e_*` predicate is one concrete way it can: it makes the active's
    attack lethal, it pays a retreat that unlocks a finisher, it charges the
    body that will be promoted, it turns Syrup Storm into a knockout. If none
    of them fires, a Grass in hand is just a card.
  * A BODY (`_RULES_NS_<NAME>`) -- one rule chain per recoverable body, ranked
    against the board: restart a line that got knocked out, replace an engine
    piece, bring back the attacker the matchup needs.

THE RETREAT THAT FEEDS THE STRETCHER. The subtlety worth knowing before
touching this file: paying a retreat DISCARDS the energy off the retreating
body, which puts a Grass in the discard for this card to recover. So a board
with no Grass in the discard can still have a Stretcher line -- retreat first,
recover the energy that the retreat just spent, attach it to the promoted body.
Missing that cost a real game, and it is why `ptcg/calc/energy.py` counts
REACHABLE energy rather than energy in hand.

THE RECOVERED CARD MUST BE USABLE. Recovering an evolution with no body to
evolve from, or a Basic with a full bench, produces a dead card in hand -- and
worse, one our own Unfair Stamp may shuffle away the same turn. The
`_evolvable_counts` reading (see `ptcg/calc/board.py`) is what guards that, and
Night Stretcher is the one consumer measured to WANT its stricter form.

A note on `_no_attack_today` and `_ns_charge_route_open`: several rules here
turn on "can anybody attack at all this turn". That question is asked through
the shared energy calculators, never re-derived locally, so this card and the
turn plan cannot come to different conclusions about the same board.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.engine.rules import _FixedRule
from ptcg.cards.ids import Applin, Basic_Grass_Energy, Bayleef, Boss_Orders, Chikorita, Dipplin, Fezandipiti_ex, Hydrapple_ex, Meganium, Meowth_ex, Pinsir, SCORE_VETO, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.calc.energy import _can_attack_eff, _grass_attach_route_open, _grass_attach_unit, _retreat_grass_units
from ptcg.calc.damage import _attacker_base_damage, _op_active_attack_damage_to, _our_effective_damage
from ptcg.calc.card import prize_count_op
from ptcg.state.zones import ZONE_DECK
from ptcg.state.agent_state import AGENT_STATE
from ptcg.cards.ids import Applin, Basic_Grass_Energy, Bayleef, Chikorita, Dipplin, Hydrapple_ex, Meganium, Meowth_ex, RETREAT_COST, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.calc.board import _active_of, _evolvable_counts
from ptcg.calc.energy import _grass_mult, calc_syrup_storm_damage, count_total_grass_energy
from dataclasses import dataclass
from ptcg.calc.board import _evolvable_counts
from ptcg.cards.ids import Applin, Basic_Grass_Energy, Bayleef, Chikorita, Dipplin, Fezandipiti_ex, Hydrapple_ex, Meganium, Meowth_ex, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex


class _CtxNSPlay:
    """DecisionContext wrapper for the Night Stretcher scenarios: it adds the
    discard inventory (basics/evolutions/energy) and the evolvable snapshot;
    every other field is delegated to the ctx via __getattr__."""

    _BASICOS = (Chikorita, Applin, Teal_Mask_Ogerpon_ex, Tapu_Bulu,
                Meowth_ex, Fezandipiti_ex, Pinsir)
    _EVOS = (Bayleef, Meganium, Dipplin, Hydrapple_ex)

    def __init__(self, ctx):
        self.c = ctx
        basics, evos, energy = set(), set(), 0
        for card in ctx.my_state.discard:
            if card.id == Basic_Grass_Energy:
                energy += 1
            elif card.id in self._BASICOS:
                basics.add(card.id)
            elif card.id in self._EVOS:
                evos.add(card.id)
        self.basics, self.evos, self.energy = basics, evos, energy
        self.evolvable = _evolvable_counts(ctx.field_counts,
                                           ctx.field_at_turn_start,
                                           ctx.forest_in_play)

    def __getattr__(self, name):
        return getattr(self.c, name)


def _ns_useful_energy_without_grass(w):
    """There is Grass in the DISCARD and none in hand -- so recovering is the
    only way to get energy today. With a Grass already in hand the recovery
    buys nothing this turn and the card is better kept."""
    return (w.energy >= 1
            and w.hand_counts.get(Basic_Grass_Energy, 0) == 0)


def _ns_has_ogerpon_teal(w):
    """An Ogerpon in play that is still short of Myriad's three energies.

    Anywhere -- active or bench -- because Teal Dance charges its own bearer
    regardless of where it stands. That body is a live destination for a
    recovered Grass; a fully charged one is not.
    """
    for bp in w.my_state.bench:
        if (bp is not None and bp.id == Teal_Mask_Ogerpon_ex
                and len(bp.energies) < 3):
            return True
    if w.my_state.active:
        act = w.my_state.active[0]
        if (act is not None and act.id == Teal_Mask_Ogerpon_ex
                and len(act.energies) < 3):
            return True
    return False


def _ns_crustle_allowed_basics(w):
    """Which Basics are worth recovering against the immune-wall matchups.

    Against a wall our ex cannot damage, the only recoveries that matter are
    bodies that can actually hit it. Pure Cornerstone is the stricter case --
    just the two manual attackers -- while Crustle still leaves the evolution
    lines worth rebuilding.
    """
    if w.op_is_cornerstone_deck and not w.op_is_crustle_deck:
        return (Tapu_Bulu, Pinsir)
    return (Tapu_Bulu, Pinsir, Applin, Chikorita)


def _ns_crustle_evos_permitidas(w):
    """Which evolutions are worth recovering in those same matchups.

    None at all against pure Cornerstone: every one of them leads to an ex the
    wall is immune to, so recovering the line spends a card on a body that
    cannot answer.
    """
    if w.op_is_cornerstone_deck and not w.op_is_crustle_deck:
        return ()
    return (Dipplin, Bayleef, Meganium)


@dataclass
class _CtxNS:
    hand: dict
    field: dict
    evolvable_ns: dict
    bench_count: int
    total_grass: int
    has_hydrapple: bool
    active_needs_energy: bool
    op_ex_immune_active: bool
    op_ex_immune_bench: bool
    op_is_lucario: bool
    watchtower: bool
    best_supp_hand_val: int
    best_supp_deck_val: int
    turn: int
    energy_attached: bool
    supporter_played: bool
    act_hyd_ripen: bool          # active Hydrapple ex chargeable with Ripening
    act_og_can_teal_attack: bool  # active Ogerpon that Teal Dance enables
    ns_bench_charge: bool        # vs Crustle: energy for a benched attacker
    ns_evo_saves_doomed: bool    # Hydrapple ex saves a doomed Dipplin
    grass_enables_syrup_ko: bool  # the Grass makes Syrup Storm LETHAL again
    # The Grass, put on OUR ACTIVE, KNOCKS OUT the opposing active TODAY
    # (`_grass_on_active_enables_ko` + a live route to the active).
    grass_makes_the_active_ko: bool = False
    # --- Dead turn: the DRAW engine rules (registro_008 step 67) ------------
    dead_turn: bool = False   # nobody attacks today, not even with one more energy
    hand_exhausted: bool = False   # <=2 cards in hand after paying for the search
    ld_free: bool = True         # _meowth_ld_free (Last-Ditch unspent)
    ko_reciente: bool = False    # ko_last_turn (enables Flip the Script)
    # vs Dragapult with >2 Pokemon in play, Tapu Bulu cannot be PUT DOWN (see
    # `_dragapult_no_tapu`): it is not searched for either -- bringing it to hand
    # only fills the hand with a dead card.
    dragapult_no_tapu: bool = False
    # Their active cannot be touched and their bench can
    # (`_boss_gust_immune_active`): the Meowth ex is recovered for the Boss's
    # Orders its Last-Ditch Catch brings, not for a refill.
    gust_over_immune_active: bool = False


def _v_ns_grass_none_in_hand(c):
    v = 600
    if not c.energy_attached:
        v = 700
    if (c.field.get(Teal_Mask_Ogerpon_ex, 0) >= 1
            and c.hand.get(Basic_Grass_Energy, 0) == 0):
        v = 750
    return v


def _ns_meowth_engine_alive(c):
    """The recovered Meowth ex is PUT DOWN this turn and its Last-Ditch Catch
    brings a Supporter from the deck that is better than anything left in hand."""
    return (not c.watchtower and c.ld_free
            and c.field.get(Meowth_ex, 0) < 2
            and c.bench_count < 5
            and not c.supporter_played
            and c.best_supp_hand_val < 500
            and c.best_supp_deck_val >= 400)


def _ns_fez_engine_alive(c):
    """The recovered Fezandipiti ex is PUT DOWN this turn and Flip the Script
    draws 3 (it requires one of our own KOs on the previous turn)."""
    return (not c.watchtower and c.ko_reciente
            and c.field.get(Fezandipiti_ex, 0) == 0
            and c.bench_count < 5)


def _ns_charge_route_open(w):
    """There is still some route to put a Grass from hand onto the field this
    turn (manual attachment or a live charging ability)."""
    return _grass_attach_route_open(
        w.state, w.field_counts,
        abilities_off=bool(getattr(w, 'meowth_ability_lock', False)))


def _charge_route_to_active(my_state, state, field_counts, abilities_off=False):
    """Whether ONE Grass from hand can still reach the ACTIVE this turn: the
    manual attachment goes wherever we want, Ripening Charge too (it attaches to
    1 of your Pokemon) and Teal Dance only to the Ogerpon that bears it.

    Raw-argument core so the two contexts of the Night Stretcher share ONE
    implementation: the PLAY scorer (which reads a DecisionContext) and the
    FETCH tables (which build `_CtxNS` from the observation)."""
    if not state.energyAttached:
        return True
    if not _grass_attach_route_open(state, field_counts,
                                    abilities_off=abilities_off):
        return False
    act = _active_of(my_state)
    if act is None:
        return False
    if field_counts.get(Hydrapple_ex, 0) >= 1:
        return True
    return act.id == Teal_Mask_Ogerpon_ex


def _ns_charge_route_to_active(w):
    """`_charge_route_to_active` over a DecisionContext."""
    return _charge_route_to_active(
        w.my_state, w.state, w.field_counts,
        abilities_off=bool(getattr(w, 'meowth_ability_lock', False)))


def _grass_on_active_enables_ko(my_state, op_state, bench_count,
                                meganium_in_play, neutralization_zone_active):
    """ONE more Grass ON OUR ACTIVE turns its attack into a KNOCK OUT of the
    opposing active, which it was not without it.

    Deck-agnostic and card-agnostic: all the arithmetic is delegated to the
    central evaluators. `_attacker_base_damage` returns 0 when the attacker does
    not reach `ATTACK_ENERGY_REQ`, so the SAME comparison covers the two cases
    that matter:

      - the active ALREADY attacks and falls short of the KO (the extra Grass
        scales Myriad Leaf Shower / Syrup Storm over the top);
      - the active CANNOT attack at all yet (it is below its cost) and the extra
        Grass both pays for the attack and knocks out.

    `_our_effective_damage` applies weakness, resistance, Neutralization Zone and
    the immunities (Crustle/Cornerstone against our ex, Drednaw, Sturdy), so an
    unreachable target can never make this predicate fire: no matchup guard is
    needed on top of it.

    The caller is responsible for the ROUTE (`_charge_route_to_active`): a Grass
    that cannot be attached to the active this turn knocks nothing out.
    """
    act = _active_of(my_state)
    opp = _active_of(op_state)
    if act is None or opp is None:
        return False
    hp = opp.hp or 0
    if hp <= 0:
        return False
    total = count_total_grass_energy(my_state)
    unit = _grass_attach_unit()
    e = len(act.energies)

    def _eff(_e, _grass):
        base = _attacker_base_damage(
            act.id, opp, _e, grass_scale=_grass, teal_self_energy=_e,
            bench_count=bench_count)
        if base <= 0:
            return 0
        return _our_effective_damage(
            act, opp, base, meganium_in_play, neutralization_zone_active)

    return _eff(e, total) < hp <= _eff(e + unit, total + unit)


def _ns_e_retreat_lethal(w):
    """The Grass in the DISCARD pays the ACTIVE's RETREAT COST and frees a
    benched attacker that KNOCKS OUT this turn (user, registro_021 turn 21).

    Full chain: Night Stretcher -> Grass to hand -> attach to the ACTIVE (which
    cannot attack) -> RETREAT -> promote the ready attacker -> KO. Without this
    first piece the whole chain is unreachable: the remaining links
    (`_attach_enable_retreat_ko`, 41000) require a Grass IN HAND, and here there
    is precisely none -- it is in the discard.

    Deck-agnostic: all the work is done by `_grass_unlocks_active_retreat` (via
    the ctx's `ability_unlock_retreat_ko`), which leans on `RETREAT_COST`,
    `_can_attack_eff` and `_bench_attacker_can_ko` -- no card id at all. It
    covers any blocked active (Fezandipiti ex, Meowth ex, a body from another
    deck) and any benched finisher."""
    return (w.ability_unlock_retreat_ko
            and _ns_useful_energy_without_grass(w)
            and _ns_charge_route_to_active(w))


def _ns_e_retreat_chip(w):
    """NON-lethal version of `_ns_e_retreat_lethal`: the benched attacker only
    does CHIP damage, but the active cannot attack in any way this turn
    (`ability_unlock_retreat_attack` already requires it), so the chip damage is
    worth infinitely more than closing the turn at 0. Same criterion as
    `_attach_enable_retreat_attack` (log 88162794: four turns in a row given
    away without attacking)."""
    return (w.ability_unlock_retreat_attack
            and _ns_useful_energy_without_grass(w)
            and _ns_charge_route_to_active(w))


def _ns_e_active_pays_retreat(w):
    """Energy from the discard so the ACTIVE pays its RETREAT COST and a benched
    body comes up to attack (user, registro_014 step 141 vs Alakazam).

    `_ns_active_below_its_cost` only contemplates the retreat of the MEGANIUM
    LINE (Chikorita/Bayleef/Meganium); with an active Fezandipiti ex at 0
    energies and a ready benched Hydrapple ex it returned False, so the Night
    Stretcher that recovered the Grass from the discard was vetoed for a full
    bench and the turn died without attacking.

    Union of the two variants above. The FULL BENCH cut-off consumes it
    (`_ns_full_bench_keep`); the play's SCORE is produced by
    `_ns_e_retreat_lethal` / `_ns_e_retreat_chip` as scenarios of
    `_ESC_NS_RECUPERACION`."""
    return _ns_e_retreat_lethal(w) or _ns_e_retreat_chip(w)


def _ns_e_syrup_letal(w):
    """The recovered energy turns the ACTIVE Hydrapple's Syrup Storm LETHAL on
    the opposing active (it was not lethal without it)."""
    if not (_ns_useful_energy_without_grass(w)
            and not w.op_is_crustle_deck and not w.op_is_cornerstone_deck):
        return False
    act = w.my_state.active[0] if w.my_state.active else None
    opp = (w.op_state.active[0]
           if (w.op_state.active and w.op_state.active[0] is not None)
           else None)
    if act is None or act.id != Hydrapple_ex or opp is None:
        return False
    if len(act.energies) * _grass_mult() < 2:
        return False
    ahora = calc_syrup_storm_damage(w.my_state, w.meganium_in_play)
    after = ahora + 30 * _grass_attach_unit()
    eff_ahora = _our_effective_damage(
        act, opp, ahora, w.meganium_in_play, w.neutralization_zone_active)
    eff_after = _our_effective_damage(
        act, opp, after, w.meganium_in_play, w.neutralization_zone_active)
    hp = opp.hp or 0
    return eff_ahora < hp <= eff_after and eff_after > 0


def _ns_e_finisher_with_active(w):
    """The recovered Grass, placed on OUR OWN active (manual attachment, Teal
    Dance or Ripening Charge), turns its attack LETHAL.

    It generalises `_ns_e_syrup_letal` to any active attacker (user,
    registro_010 step 123 vs Archaludon ex): active Ogerpon ex with 6 units
    against an Archaludon ex 300/300 with 3 energies and NO bench. Myriad did
    30+30x(6+3) = 300 - 30 resistance = 270: it fell 30 short. With one Grass
    from the discard via Teal Dance it goes up to 30+30x(8+3) = 360 - 30 = 330
    >= 300 and, with the opposing bench empty, that KO WINS the game."""
    if not (_ns_useful_energy_without_grass(w)
            and not w.op_is_crustle_deck and not w.op_is_cornerstone_deck):
        return False
    if not _ns_charge_route_to_active(w):
        return False
    return _grass_on_active_enables_ko(
        w.my_state, w.op_state, w.bench_count,
        w.meganium_in_play, w.neutralization_zone_active)


def _ns_e_finisher_via_promotion(w):
    """The recovered Grass turns this turn's finisher LETHAL with a BENCHED
    attacker that we promote by RETREATING the active.

    Sibling of `_ns_e_syrup_letal` for the case where the finisher is not in the
    active spot yet (user, registro_006 step 78 vs Archaludon ex, LOST):
    Hydrapple ex on the bench with 2 energies, 10 Grass units on the field and
    the opposing active at 270 HP with resistance to Grass. Retreating costs a
    whole card (2 units with Wild Growth), so the real Syrup Storm was 30+30x8 =
    270 - 30 = 240: it did NOT knock out. With ONE Grass from the discard (Night
    Stretcher + Teal Dance, which is still alive even if the manual attachment
    has been spent) the count goes back to 10 -> 330 - 30 = 300 >= 270 and the
    KO hands over TWO prizes. Without modelling it, Night Stretcher never
    entered the analysis of the finisher."""
    if not (_ns_useful_energy_without_grass(w)
            and not w.op_is_crustle_deck and not w.op_is_cornerstone_deck):
        return False
    if not _ns_charge_route_open(w):
        return False
    act = _active_of(w.my_state)
    opp = _active_of(w.op_state)
    if act is None or opp is None or (opp.hp or 0) <= 0:
        return False
    hp = opp.hp or 0
    cost = RETREAT_COST.get(act.id, 1)
    if len(act.energies) < cost:
        return False  # we cannot pay the retreat: there is no promotion
    total = count_total_grass_energy(w.my_state)
    # If the ACTIVE already finishes that same target with what it has, the Grass
    # unlocks nothing: attacking takes the same prizes without spending the Night
    # Stretcher or an energy from the discard.
    _act_eff = len(act.energies) * _grass_mult()
    _act_base = _attacker_base_damage(
        act.id, opp, _act_eff, grass_scale=total,
        teal_self_energy=len(act.energies), bench_count=w.bench_count)
    if _act_base > 0 and _our_effective_damage(
            act, opp, _act_base, w.meganium_in_play,
            w.neutralization_zone_active) >= hp:
        return False
    after_retreat = max(0, total - _retreat_grass_units(cost))
    unit = _grass_attach_unit()

    def _remata(bp, grass):
        e = len(bp.energies)
        base = _attacker_base_damage(
            bp.id, opp, e * _grass_mult(), grass_scale=grass,
            teal_self_energy=e, bench_count=w.bench_count)
        if base <= 0:
            return False
        return _our_effective_damage(
            bp, opp, base, w.meganium_in_play,
            w.neutralization_zone_active) >= hp

    # The line is worth the Night Stretcher only if it can really be EXECUTED and
    # it PAYS (measured in prizes). Without these two guards the scenario reserved
    # the card for a pivot that the rest of the agent then rejected -- the matchup
    # differential paid for it (-3 points in self-play vs iron_thorns and
    # crustle_kangaskhan; with them it goes back to positive):
    #   (a) the promoted body is EXPOSED to the opposing active: if that hit knocks
    #       it out, the pivot gives away its prizes (same guard as
    #       `_bench_pivot_suicidal`);
    #   (b) the KO has to be worth 2+ prizes or WIN the game: burning the Night
    #       Stretcher and an energy for a single prize does not pay off.
    _prizes = prize_count_op(opp)
    _gana = (w.my_prize <= _prizes
             or not any(b is not None for b in (w.op_state.bench or [])))
    if _prizes < 2 and not _gana:
        return False
    for bp in (w.my_state.bench or []):
        if bp is None:
            continue
        if _remata(bp, after_retreat):
            return False  # it already knocks out without the Grass: the card is not needed
    for bp in (w.my_state.bench or []):
        if bp is None:
            continue
        if not _remata(bp, after_retreat + unit):
            continue
        _golpe = _op_active_attack_damage_to(
            opp, bp, getattr(w.op_state, 'handCount', None))
        if not _gana and _golpe >= (bp.hp or 0):
            continue  # promoting it would be giving away its prizes
        return True
    return False


def _ns_e_charge_bench_crustle(w):
    if not (_ns_useful_energy_without_grass(w)
            and not w.state.energyAttached):
        return False
    for bp in (w.my_state.bench or []):
        if bp is None:
            continue
        if bp.id not in (Tapu_Bulu, Teal_Mask_Ogerpon_ex,
                         Hydrapple_ex, Meganium):
            continue
        req = AGENT_STATE.ATTACK_ENERGY_REQ.get(bp.id)
        if req is None:
            continue
        if len(bp.energies) * _grass_mult() < req:
            return True
    return False


def _no_attack_today(my_state, state, field_counts, abilities_off=False):
    """True if NO body of ours can attack this turn, not even by putting ONE
    more energy down.

    Deck-agnostic: it walks the field with `ATTACK_ENERGY_REQ` (the curated list
    of bodies we really attack with) in three passes:
      1) the ACTIVE already pays for its attack with the energy it has;
      2) there is a READY attacker on the bench and the active can pay its
         retreat to bring it up (an attacker stuck on the bench is not an
         attacker);
      3) a charging route is still open (a free manual attachment or a live
         ability such as Teal Dance / Ripening Charge) and ONE more Grass turns
         the active -- or the promotable benched body -- into an attacker.
    If none of them holds, the turn is DEAD for attacking: the only thing that
    produces value is rebuilding the hand. It deliberately does NOT use
    `_active_ready_attacker`: that flag depends on `can_attack`, which is only
    computed in the MAIN menu and is False in the selection sub-menus (TO_HAND),
    where this function lives.
    """
    act = _active_of(my_state)
    if act is not None and _can_attack_eff(act.id, len(act.energies)):
        return False
    bench = [b for b in (my_state.bench or []) if b is not None]
    can_promote = (
        act is not None
        and not getattr(state, 'retreated', False)
        and len(act.energies) >= RETREAT_COST.get(act.id, 1))
    if can_promote and any(_can_attack_eff(b.id, len(b.energies))
                              for b in bench):
        return False
    if _grass_attach_route_open(state, field_counts,
                                abilities_off=abilities_off):
        unit = _grass_attach_unit()
        if act is not None and _can_attack_eff(act.id,
                                               len(act.energies) + unit):
            return False
        if can_promote and any(
                _can_attack_eff(b.id, len(b.energies) + unit)
                for b in bench):
            return False
    return True


def _ctx_ns_fetch(my_state, state, hand_counts, field_counts, bench_count,
                  total_grass, has_hydrapple, active_needs_energy,
                  op_ex_immune_active, op_ex_immune_bench, op_is_lucario,
                  watchtower, best_supp_hand_val, best_supp_deck_val,
                  grass_enables_syrup_ko=False, ld_free=True,
                  dragapult_no_tapu=False, op_state=None,
                  neutralization_zone_active=False,
                  gust_over_immune_active=False):
    """Build the board reading the `_RULES_NS_*` fetch chains score against.

    One context, shared by every recoverable candidate, so the bodies and the
    energy are ranked from the same view. Like the Ultra Ball's, it is reached
    from both the PLAY decision and the later FETCH decision -- the two have to
    agree about what the recovery is for.
    """
    active = my_state.active[0] if my_state.active else None
    # An ACTIVE Ogerpon that does not attack yet (<3 effective) but that with ONE
    # Grass via Teal Dance (an ABILITY, independent of the manual attachment)
    # reaches >=3. Pivot retreat->promote Ogerpon->NS->Teal Dance->attack (user,
    # log 86583929 turn 4 vs Alakazam). len(energies) is EFFECTIVE.
    act_og_can_teal_attack = (
        active is not None and
        active.id == Teal_Mask_Ogerpon_ex and
        len(active.energies) < 3 and
        len(active.energies) + _grass_attach_unit() >= 3 and
        hand_counts[Basic_Grass_Energy] == 0)
    # An active Hydrapple ex that does not attack yet (effective < 2) and with no
    # Grass in hand: recover ENERGY to charge it with Ripening Charge (ability).
    act_hyd_ripen = (
        active is not None and
        active.id == Hydrapple_ex and
        len(active.energies) * _grass_mult() < 2 and
        hand_counts[Basic_Grass_Energy] == 0)
    # Crustle/Cornerstone matchup: recover the Grass to CHARGE a benched
    # attacker while we can still attach it this turn.
    ns_bench_charge = False
    if ((AGENT_STATE.op_is_crustle_deck or AGENT_STATE.op_is_cornerstone_deck) and
            hand_counts[Basic_Grass_Energy] == 0 and
            not state.energyAttached):
        for bp in (my_state.bench or []):
            if bp is None:
                continue
            if bp.id not in (Tapu_Bulu, Teal_Mask_Ogerpon_ex,
                             Hydrapple_ex, Meganium):
                continue
            req = AGENT_STATE.ATTACK_ENERGY_REQ.get(bp.id)
            if req is None:
                continue
            if len(bp.energies) * _grass_mult() < req:
                ns_bench_charge = True
                break
    # Recover Hydrapple ex to EVOLVE a benched Dipplin DOOMED by the opponent's
    # automatic snipe (user, registro_006/008 vs Marnie's Grimmsnarl ex, LOST):
    # with the Dipplin at <= 30 HP, Shadow Bullet kills it by itself next turn and
    # hands over a free prize. The evolution resets the HP (80 -> 330) and along the
    # way turns the doomed body into a wall, so saving it is worth MORE than any
    # development or energy recovery (which only adds damage when the KO is already
    # secured). Unlike `dipplin_evolvable`, this rule does NOT require a
    # Hydrapple ex to be missing from play: here the evolution is not development,
    # it is a rescue.
    ns_evo_saves_doomed = False
    if AGENT_STATE._op_bench_snipe_dmg > 0 and hand_counts.get(Hydrapple_ex, 0) == 0:
        for _nsd in (my_state.bench or []):
            if _nsd is None or _nsd.id != Dipplin:
                continue
            if (_nsd.hp or 0) > AGENT_STATE._op_bench_snipe_dmg:
                continue  # it survives this turn's drip: not urgent
            if getattr(_nsd, 'appearThisTurn', False) and not AGENT_STATE.forest_in_play:
                continue  # it evolved this turn: it cannot evolve again
            ns_evo_saves_doomed = True
            break
    evolvable_ns = _evolvable_counts(field_counts, AGENT_STATE._field_at_turn_start,
                                     AGENT_STATE.forest_in_play)
    # DEAD TURN (user, registro_008 step 67 vs Alakazam, LOST): with no body able
    # to attack today and an empty hand, recovering an EVOLUTION is preparation
    # that never gets played -- the opponent knocks out the active and next turn we
    # still have no cards. The only thing that produces value is the DRAW engine.
    # `hand_exhausted` measures the hand ALREADY without the search card (it was paid
    # when playing it), so 0 = we are left dry.
    dead_turn = _no_attack_today(my_state, state, field_counts,
                                   abilities_off=watchtower)
    hand_exhausted = len(my_state.hand or []) <= 2
    # THE ENERGY THAT TAKES PRIZES TODAY (user, registro_008 step 85 vs Mega
    # Kangaskhan ex, LOST): the fetch tables scored the Grass as DEVELOPMENT
    # ("the active needs energy", 900) and lost to an Applin that was starting a
    # line (800 + 150 for the last copy = 950). But that Grass was not
    # development: the active Ogerpon ex sat at 2 of the 3 energies its attack
    # costs, Teal Dance was unspent and the opposing active -- a 3-prize Mega ex --
    # was at 90 HP. Grass -> Teal Dance -> attack knocked it out. The agent
    # recovered the Applin and ended the turn without attacking.
    # Same criterion as `grass_makes_syrup_storm_lethal`: a prize TODAY beats any
    # development for tomorrow, so it goes into that band and not into the
    # development one.
    grass_makes_the_active_ko = (
        hand_counts.get(Basic_Grass_Energy, 0) == 0
        and _charge_route_to_active(my_state, state, field_counts,
                                    abilities_off=watchtower)
        and _grass_on_active_enables_ko(
            my_state, op_state, bench_count,
            AGENT_STATE.meganium_in_play, neutralization_zone_active))
    return _CtxNS(
        hand=hand_counts, field=field_counts, evolvable_ns=evolvable_ns,
        bench_count=bench_count, total_grass=total_grass,
        has_hydrapple=has_hydrapple,
        active_needs_energy=active_needs_energy,
        op_ex_immune_active=op_ex_immune_active,
        op_ex_immune_bench=op_ex_immune_bench,
        op_is_lucario=op_is_lucario, watchtower=watchtower,
        best_supp_hand_val=best_supp_hand_val,
        best_supp_deck_val=best_supp_deck_val,
        turn=state.turn, energy_attached=state.energyAttached,
        supporter_played=state.supporterPlayed,
        act_hyd_ripen=act_hyd_ripen,
        act_og_can_teal_attack=act_og_can_teal_attack,
        ns_bench_charge=ns_bench_charge,
        ns_evo_saves_doomed=ns_evo_saves_doomed,
        grass_enables_syrup_ko=grass_enables_syrup_ko,
        grass_makes_the_active_ko=grass_makes_the_active_ko,
        dead_turn=dead_turn, hand_exhausted=hand_exhausted,
        ld_free=ld_free, ko_reciente=AGENT_STATE.ko_last_turn,
        dragapult_no_tapu=dragapult_no_tapu,
        gust_over_immune_active=gust_over_immune_active)


def _v_ns_chikorita_arrancar(c):
    v = 800
    if AGENT_STATE.forest_in_play and (c.hand.get(Bayleef, 0) >= 1
                           or c.hand.get(Meganium, 0) >= 1):
        v = 950
    elif c.hand.get(Bayleef, 0) >= 1:
        v = 900
    if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Chikorita, {}).get(ZONE_DECK, 0) == 0:
        v += 100
    else:
        v -= 100
    return v


def _v_ns_applin_arrancar(c):
    v = 700
    if AGENT_STATE.forest_in_play and (c.hand.get(Dipplin, 0) >= 1
                           or c.hand.get(Hydrapple_ex, 0) >= 1):
        v = 870
    elif c.hand.get(Dipplin, 0) >= 1:
        v = 800
    if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Applin, {}).get(ZONE_DECK, 0) == 0:
        v += 100
    else:
        v -= 100
    return v


def _v_ns_ogerpon_pocos(c):
    v = 550
    if c.field.get(Teal_Mask_Ogerpon_ex, 0) == 0:
        v = 700
    if c.bench_count <= 1:
        v += 100
    if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
            Teal_Mask_Ogerpon_ex, {}).get(ZONE_DECK, 0) == 0:
        v += 100
    return v


def _v_ns_meowth_fetch(c):
    v = min(700, c.best_supp_deck_val)
    if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meowth_ex, {}).get(ZONE_DECK, 0) == 0:
        v += 100
    return v


_RULES_NS_GRASS = [
    # The Grass that FINISHES (a lethal Syrup Storm THIS turn) beats any other
    # recovery, evolutions included (registro_006 step 68 vs Mega Abomasnow ex): a
    # prize today is worth more than development for tomorrow.
    _FixedRule("grass_makes_syrup_storm_lethal",
               lambda c: c.grass_enables_syrup_ko,
               lambda c: 1400),
    # Its deck-agnostic sibling: the Grass that, ON THE ACTIVE, turns an attack
    # that does NOT knock out -- or that cannot even be paid for -- into a KO
    # this turn. Same band, same reason: a prize today.
    _FixedRule("grass_makes_the_active_ko",
               lambda c: c.grass_makes_the_active_ko,
               lambda c: 1400),
    # An ACTIVE Hydrapple ex with no attack: charging it with Ripening Charge WINS
    # over any other recovery target.
    _FixedRule("active_hydrapple_ripening",
               lambda c: c.act_hyd_ripen,
               lambda c: 1300),
    _FixedRule("charge_the_bench_vs_crustle",
               lambda c: c.ns_bench_charge,
               lambda c: 950),
    _FixedRule("active_needs_energy",
               lambda c: (c.active_needs_energy
                          and c.hand.get(Basic_Grass_Energy, 0) == 0
                          and not c.energy_attached),
               lambda c: 900),
    _FixedRule("ogerpon_teal_enables_it",
               lambda c: c.act_og_can_teal_attack,
               lambda c: 900),
    _FixedRule("no_grass_in_hand",
               lambda c: c.hand.get(Basic_Grass_Energy, 0) == 0,
               _v_ns_grass_none_in_hand),
    _FixedRule("hydra_with_little_grass",
               lambda c: c.has_hydrapple and c.total_grass < 4,
               lambda c: 450),
    _FixedRule("surplus_grass_in_hand",
               lambda c: c.hand.get(Basic_Grass_Energy, 0) >= 3,
               lambda c: 100),
]


_RULES_NS_FEZ = [
    # Second option of the engine: it yields to Meowth ex (1250), which rebuilds the
    # whole hand via Lillie's instead of drawing 3. The veto vs Lucario is respected
    # (it hits the bench: a 2-prize ex there is a prize given away).
    _FixedRule("draw_engine_on_a_dead_turn",
               lambda c: (c.dead_turn and c.hand_exhausted
                          and not c.op_is_lucario
                          and _ns_fez_engine_alive(c)),
               lambda c: 1200),
    _FixedRule("refill_after_a_ko",
               lambda c: (c.field.get(Fezandipiti_ex, 0) == 0
                          and AGENT_STATE.ko_last_turn and c.bench_count < 5),
               lambda c: 850),
    # vs Lucario (which hits the bench): Fez only as an emergency body with an
    # empty bench; otherwise vetoed.
    _FixedRule("vs_lucario",
               lambda c: c.op_is_lucario,
               lambda c: (200 if (c.field.get(Fezandipiti_ex, 0) == 0
                                  and c.bench_count == 0) else SCORE_VETO)),
    _FixedRule("first_fez",
               lambda c: c.field.get(Fezandipiti_ex, 0) == 0,
               lambda c: 200),
]


_RULES_NS_CHIKORITA = [
    _FixedRule("start_the_meganium_line",
               lambda c: (not AGENT_STATE.meganium_in_play
                          and (c.field.get(Chikorita, 0)
                               + c.field.get(Bayleef, 0)
                               + c.field.get(Meganium, 0)) == 0),
               _v_ns_chikorita_arrancar),
]


_RULES_NS_APPLIN = [
    _FixedRule("hydrapple_already_in_play",
               lambda c: c.has_hydrapple,
               lambda c: 35),
    _FixedRule("start_the_hydra_line",
               lambda c: (c.field.get(Applin, 0)
                          + c.field.get(Dipplin, 0)
                          + c.field.get(Hydrapple_ex, 0)) == 0,
               _v_ns_applin_arrancar),
    _FixedRule("short_bench",
               lambda c: c.bench_count <= 1,
               lambda c: 350),
]


_RULES_NS_OGERPON = [
    _FixedRule("fewer_than_two_ogerpon",
               lambda c: c.field.get(Teal_Mask_Ogerpon_ex, 0) < 2,
               _v_ns_ogerpon_pocos),
    # A 3rd Ogerpon as a Syrup Storm accelerator (Teal Dance adds Grass).
    _FixedRule("third_ogerpon_for_syrup",
               lambda c: (c.bench_count < 5
                          and c.hand.get(Basic_Grass_Energy, 0) >= 1
                          and c.field.get(Hydrapple_ex, 0) >= 1),
               lambda c: 500),
]


_RULES_NS_TAPU = [
    # vs Dragapult with the board already built it cannot be PUT DOWN: not recovered.
    _FixedRule("dragapult_does_not_play_it",
               lambda c: c.dragapult_no_tapu,
               lambda c: SCORE_VETO),
    _FixedRule("tapu_already_on_field",
               lambda c: c.field.get(Tapu_Bulu, 0) >= 1,
               lambda c: 15),
    _FixedRule("anti_ex_with_meganium",
               lambda c: (AGENT_STATE.meganium_in_play
                          and (c.op_ex_immune_active
                               or c.op_ex_immune_bench)),
               lambda c: 800 if c.has_hydrapple else 700),
    _FixedRule("anti_ex",
               lambda c: c.op_ex_immune_active or c.op_ex_immune_bench,
               lambda c: 350),
]


_RULES_NS_PINSIR = [
    _FixedRule("anti_ex",
               lambda c: (c.field.get(Pinsir, 0) == 0
                          and (AGENT_STATE.op_is_crustle_deck
                               or AGENT_STATE.op_is_cornerstone_deck)),
               lambda c: 850),
]


_RULES_NS_MEOWTH = [
    _FixedRule("t1_going_first_no",
               lambda c: c.turn == 1 and AGENT_STATE.we_go_first,
               lambda c: 10),
    # First option of the draw engine on a dead turn: it beats ALL development
    # (see the comment block about _ns_meowth_engine_alive).
    _FixedRule("draw_engine_on_a_dead_turn",
               lambda c: (c.dead_turn and c.hand_exhausted
                          and _ns_meowth_engine_alive(c)),
               lambda c: 1250),
    # THEIR ACTIVE CANNOT BE TOUCHED (user, episode 90325863, turn 8 vs a
    # Dragapult / Azumarill deck): their Marill hid behind a Hide that came up
    # heads. The Night Stretcher then recovers the Meowth ex not to refill but
    # to reach the BOSS'S ORDERS in the deck, the one card that turns the turn
    # back into damage by gusting an attackable body off their bench. It goes
    # ABOVE `fetch_supporter_from_deck`, whose `best_supp_hand_val < 500` gate
    # would switch the line off for the wrong reason: a Lillie's in hand scores
    # far above 500 and answers nothing here.
    _FixedRule("boss_engine_vs_untouchable",
               lambda c: (c.gust_over_immune_active
                          and not c.watchtower
                          and c.hand.get(Boss_Orders, 0) == 0
                          and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                              Boss_Orders, {}).get(ZONE_DECK, 0) > 0
                          and c.field.get(Meowth_ex, 0) < 2
                          and c.ld_free
                          and c.bench_count < 5
                          and not c.supporter_played),
               lambda c: 1300),
    # Recover Meowth ex to put it down so Last-Ditch fetches a Supporter from the
    # deck that beats what is in hand.
    _FixedRule("fetch_supporter_from_deck",
               lambda c: (not c.watchtower
                          and c.field.get(Meowth_ex, 0) == 0
                          and c.bench_count < 5
                          and not c.supporter_played
                          and c.best_supp_hand_val < 500
                          and c.best_supp_deck_val >= 400),
               _v_ns_meowth_fetch),
]


_RULES_NS_HYDRAPPLE = [
    # Rescue of the Dipplin doomed by the snipe: it beats energy (<=950) and all
    # development. See `ns_evo_saves_doomed` in `_ctx_ns_fetch`.
    _FixedRule("save_the_doomed_dipplin_from_the_snipe",
               lambda c: c.ns_evo_saves_doomed,
               lambda c: 1200),
    _FixedRule("dipplin_evolvable",
               lambda c: (c.evolvable_ns.get(Dipplin, 0) >= 1
                          and not c.has_hydrapple),
               lambda c: 980),
    _FixedRule("applin_dipplin_chain_in_hand",
               lambda c: (c.field.get(Applin, 0) >= 1
                          and c.hand.get(Dipplin, 0) >= 1
                          and AGENT_STATE.forest_in_play and not c.has_hydrapple),
               lambda c: 960),
]


_RULES_NS_MEGANIUM = [
    _FixedRule("bayleef_evolvable",
               lambda c: (c.evolvable_ns.get(Bayleef, 0) >= 1
                          and not AGENT_STATE.meganium_in_play),
               lambda c: 990),
    _FixedRule("chikorita_bayleef_chain_in_hand",
               lambda c: (c.field.get(Chikorita, 0) >= 1
                          and c.hand.get(Bayleef, 0) >= 1
                          and AGENT_STATE.forest_in_play and not AGENT_STATE.meganium_in_play),
               lambda c: 975),
]


_RULES_NS_DIPPLIN = [
    _FixedRule("applin_hydra_combo_in_hand",
               lambda c: (c.hand.get(Applin, 0) >= 1
                          and c.hand.get(Hydrapple_ex, 0) >= 1
                          and AGENT_STATE.forest_in_play and c.bench_count < 5),
               lambda c: 970),
    _FixedRule("applin_in_hand_with_forest",
               lambda c: (c.hand.get(Applin, 0) >= 1
                          and AGENT_STATE.forest_in_play and c.bench_count < 5),
               lambda c: 880),
    _FixedRule("applin_evolvable",
               lambda c: (c.evolvable_ns.get(Applin, 0) >= 1
                          and not c.has_hydrapple),
               lambda c: 850),
]


_RULES_NS_BAYLEEF = [
    _FixedRule("chikorita_meganium_combo_in_hand",
               lambda c: (c.hand.get(Chikorita, 0) >= 1
                          and c.hand.get(Meganium, 0) >= 1
                          and AGENT_STATE.forest_in_play and c.bench_count < 5
                          and not AGENT_STATE.meganium_in_play),
               lambda c: 985),
    _FixedRule("chikorita_in_hand_with_forest",
               lambda c: (c.hand.get(Chikorita, 0) >= 1
                          and AGENT_STATE.forest_in_play and c.bench_count < 5
                          and not AGENT_STATE.meganium_in_play),
               lambda c: 910),
    _FixedRule("chikorita_evolvable",
               lambda c: (c.evolvable_ns.get(Chikorita, 0) >= 1
                          and not AGENT_STATE.meganium_in_play),
               lambda c: 870),
]

__all__ = [
    '_CtxNSPlay',
    '_ns_useful_energy_without_grass',
    '_ns_has_ogerpon_teal',
    '_ns_crustle_allowed_basics',
    '_ns_crustle_evos_permitidas',
    '_CtxNS',
    '_v_ns_grass_none_in_hand',
    '_ns_meowth_engine_alive',
    '_ns_fez_engine_alive',
    '_ns_charge_route_open',
    '_charge_route_to_active',
    '_ns_charge_route_to_active',
    '_grass_on_active_enables_ko',
    '_ns_e_retreat_lethal',
    '_ns_e_retreat_chip',
    '_ns_e_active_pays_retreat',
    '_ns_e_syrup_letal',
    '_ns_e_finisher_with_active',
    '_ns_e_finisher_via_promotion',
    '_ns_e_charge_bench_crustle',
    '_v_ns_chikorita_arrancar',
    '_v_ns_applin_arrancar',
    '_v_ns_ogerpon_pocos',
    '_v_ns_meowth_fetch',
    '_ctx_ns_fetch',
    '_no_attack_today',
    '_RULES_NS_APPLIN',
    '_RULES_NS_BAYLEEF',
    '_RULES_NS_CHIKORITA',
    '_RULES_NS_DIPPLIN',
    '_RULES_NS_FEZ',
    '_RULES_NS_GRASS',
    '_RULES_NS_HYDRAPPLE',
    '_RULES_NS_MEGANIUM',
    '_RULES_NS_MEOWTH',
    '_RULES_NS_OGERPON',
    '_RULES_NS_PINSIR',
    '_RULES_NS_TAPU',
]
