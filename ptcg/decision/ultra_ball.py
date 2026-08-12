"""Ultra Ball: the search orchestrator and its vetoes.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.engine.rules import _Adjustment, _FixedRule
from ptcg.cards.ids import Applin, Bayleef, Chikorita, Dipplin, Fezandipiti_ex, Forest_of_Vitality, Hydrapple_ex, Lillie_Determination, Meganium, Meowth_ex, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.decision.stadiums import _forest_disponible
from ptcg.calc.energy import _grass_attach_unit
from ptcg.calc.damage import _attacker_base_damage, _our_effective_damage
from ptcg.state.agent_state import AGENT_STATE
from ptcg.decision.disruption import _op_refill_engine, _stamp_buries_the_last_xerosic, _stamp_worth_playing
from ptcg.cards.ids import Applin, Basic_Grass_Energy, Bayleef, Boss_Orders, Chikorita, Dawn, Dipplin, Fezandipiti_ex, Forest_of_Vitality, Hydrapple_ex, Lanas_Aid, Lillie_Determination, Meganium, Meowth_ex, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Unfair_Stamp
from ptcg.calc.board import _active_of
from ptcg.calc.energy import count_total_grass_energy
from dataclasses import dataclass
from typing import NamedTuple
from ptcg.cards.ids import Applin, Basic_Grass_Energy, Bayleef, Boss_Orders, Bug_Catching_Set, CUBCHOO_ALLOWED_PLAY_IDS, Chikorita, Dawn, Dipplin, Fezandipiti_ex, Forest_of_Vitality, Hydrapple_ex, Lanas_Aid, Lillie_Determination, Meganium, Meowth_ex, Night_Stretcher, Pinsir, SCORE_CANCEL, SCORE_VETO, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball, Unfair_Stamp, XEROSIC_BIG_HAND, XEROSIC_SCORE_LAST_RESORT, Xerosic_Machinations
from ptcg.state.zones import ZONE_DECK
from ptcg.cards.lines import _evo_body_in_play, _evo_copies_usable, _evolution_stage, _line_base_benchable
from ptcg.cards.scoring import _SUPP_PLAY_IDS
from ptcg.decision.disruption import _score_xerosic_play, _xr_gate_alakazam
from ptcg.decision.poke_pad import _pp_es_t1
from ptcg.turn.game_plan import plan_of


class _UBFlags(NamedTuple):
    survival_mode: bool
    first_action_turn: bool
    hand_size: int
    evolve_needs_search: bool
    evolve_now_search: bool
    developed_attacker_board: bool


def _ub_derive_flags(ctx) -> _UBFlags:
    """Phase A of _score_ultra_ball_play: flags derived from the context
    (survival mode, first turn, evolution searches, developed board, hand
    size). Verbatim body (step 2 of the plan)."""
    state = ctx.state
    my_state = ctx.my_state
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    we_go_first = ctx.we_go_first
    forest_in_play = ctx.forest_in_play
    can_attack = ctx.can_attack
    _field_at_turn_start = ctx.field_at_turn_start
    ACTIVE_CARDS_IN_DECK = ctx.cards_in_deck
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_has_ex_immune_active = ctx.op_has_ex_immune_active
    op_has_ex_immune_bench = ctx.op_has_ex_immune_bench

    _ub_survival_mode = False
    _our_first_action_turn = (
        (state.turn == 1 and we_go_first) or
        (state.turn == 2 and not we_go_first))
    if bench_count == 0 and _our_first_action_turn:
        _ub_survival_mode = True

    elif bench_count == 0 and state.turn >= 2:
        _ub_survival_mode = True

    # STRICT variant of _evolve_possible_in_play ONLY for the Ultra
    # Ball full-bench cut-off: the "there is something to evolve"
    # exception only counts when the evolution piece is MISSING from
    # hand and is in the DECK (it has to be searched for with Ultra
    # Ball). If the evolution is ALREADY in hand, the line evolves
    # without Ultra Ball, so searching with it would only bring a
    # useless/redundant card (full bench) and might even discard the
    # evolution itself as a cost.
    # NOTE (user, log 86028607 step 47, vs Crustle): the search for
    # Hydrapple ex (Dipplin's evolution) does NOT count if the opponent
    # is immune to ex (Crustle): the TO_HAND branch lowers that target
    # to 40 (a dead card), so the Ultra Ball would never bring it; without
    # this exception the "phantom" Hydrapple ex search skipped the
    # full-bench cut-off and played a useless Ultra Ball.
    _ub_op_ex_immune = (op_is_crustle_deck or
                        op_has_ex_immune_active or
                        op_has_ex_immune_bench)
    _ub_evolve_needs_search = (
        (field_counts.get(Chikorita, 0) >= 1 and
         hand_counts.get(Bayleef, 0) == 0 and
         ACTIVE_CARDS_IN_DECK.get(Bayleef, {}).get(ZONE_DECK, 0) > 0) or
        (field_counts.get(Bayleef, 0) >= 1 and
         hand_counts.get(Meganium, 0) == 0 and
         ACTIVE_CARDS_IN_DECK.get(Meganium, {}).get(ZONE_DECK, 0) > 0) or
        (field_counts.get(Applin, 0) >= 1 and
         hand_counts.get(Dipplin, 0) == 0 and
         ACTIVE_CARDS_IN_DECK.get(Dipplin, {}).get(ZONE_DECK, 0) > 0) or
        (field_counts.get(Dipplin, 0) >= 1 and
         hand_counts.get(Hydrapple_ex, 0) == 0 and
         ACTIVE_CARDS_IN_DECK.get(Hydrapple_ex, {}).get(ZONE_DECK, 0) > 0 and
         not _ub_op_ex_immune))

    # Variant of _ub_evolve_needs_search that also requires being able
    # to COMPLETE the evolution THIS turn: the pre-evolution must be
    # able to evolve already (there is a Forest of Vitality in play or
    # the pre-evolution was in play at the start of the turn, it did
    # not come down this turn). If so, searching with Ultra Ball
    # develops the evolution line NOW, so it must NOT be postponed in
    # favour of Lillie's Determination (we evolve first and Lillie's is
    # played afterwards, without shuffling away the pieces already on
    # the board).
    _ub_evolve_now_search = (
        (field_counts.get(Chikorita, 0) >= 1 and
         hand_counts.get(Bayleef, 0) == 0 and
         ACTIVE_CARDS_IN_DECK.get(Bayleef, {}).get(ZONE_DECK, 0) > 0 and
         (forest_in_play or _field_at_turn_start.get(Chikorita, 0) >= 1)) or
        (field_counts.get(Bayleef, 0) >= 1 and
         hand_counts.get(Meganium, 0) == 0 and
         ACTIVE_CARDS_IN_DECK.get(Meganium, {}).get(ZONE_DECK, 0) > 0 and
         (forest_in_play or _field_at_turn_start.get(Bayleef, 0) >= 1)) or
        (field_counts.get(Applin, 0) >= 1 and
         hand_counts.get(Dipplin, 0) == 0 and
         ACTIVE_CARDS_IN_DECK.get(Dipplin, {}).get(ZONE_DECK, 0) > 0 and
         (forest_in_play or _field_at_turn_start.get(Applin, 0) >= 1)) or
        (field_counts.get(Dipplin, 0) >= 1 and
         hand_counts.get(Hydrapple_ex, 0) == 0 and
         ACTIVE_CARDS_IN_DECK.get(Hydrapple_ex, {}).get(ZONE_DECK, 0) > 0 and
         (forest_in_play or _field_at_turn_start.get(Dipplin, 0) >= 1) and
         not _ub_op_ex_immune))

    # Rule (user, log 86028035 step 53): if we ALREADY have a READY
    # attacker in the active spot (there is an ATTACK option this
    # turn) and the bench already has >=2 charged Pokemon (potential
    # attackers), the Ultra Ball must NOT be played to DEVELOP more
    # low-value attackers by discarding useful energy / Lillie's
    # Determination: it is better to attack and keep the resources.
    # Only redundant development is vetoed; high-value targets (>=800:
    # the Meowth->Lillie chain, evolution pieces) and searches that
    # enable a pending evolution are still allowed.
    _ub_bench_energized = sum(
        1 for _ubp in (my_state.bench or [])
        if _ubp is not None and len(_ubp.energies) >= 1)
    _ub_developed_attacker_board = (
        can_attack and _ub_bench_energized >= 2)

    hand_size = len(my_state.hand) if my_state.hand else 0

    return _UBFlags(
        survival_mode=_ub_survival_mode,
        first_action_turn=_our_first_action_turn,
        hand_size=hand_size,
        evolve_needs_search=_ub_evolve_needs_search,
        evolve_now_search=_ub_evolve_now_search,
        developed_attacker_board=_ub_developed_attacker_board)


def _ub_terminal_overrides(ctx, ub_score, _ub_survival_mode, hand_size, _our_first_action_turn):
    """Phase E of _score_ultra_ball_play: terminal overrides on the already
    computed `ub_score` (survival rescue, Bug Set, first-turn gate, full-bench
    safeguard, Alakazam line deferral). It is ALWAYS applied; it threads and
    returns ub_score. Verbatim body (step 2 of the plan)."""
    hand_counts = ctx.hand_counts
    state = ctx.state
    bench_count = ctx.bench_count
    field_counts = ctx.field_counts
    itchy_pollen_active = ctx.itchy_pollen_active
    we_go_first = ctx.we_go_first
    watchtower_in_play = ctx.meowth_ability_lock
    budew_on_op_field = ctx.budew_on_op_field
    budew_op_index = ctx.budew_op_index
    ACTIVE_CARDS_IN_DECK = ctx.cards_in_deck
    _evolve_possible_in_play = ctx.evolve_possible_in_play
    _boss_deny_alakazam_line = ctx.boss_deny_alakazam_line

    _ub_lillie_in_hand_playable = (
        hand_counts.get(Lillie_Determination, 0) >= 1 and
        not state.supporterPlayed)
    # The survival rescue only makes sense with ROOM on the bench: it searches for
    # a Basic to put down and develop/defend. With a FULL bench (bench_count >= 5)
    # nothing can be benched, so searching for a Basic would only carry it dead to
    # hand (paying 2 discards). Without this `bench_count < 5`, the rescue
    # resurrected the Ultra Ball (at 25000) despite the full-bench cut-off, playing
    # a useless Ultra Ball (user, registro 006 step 72 vs Hops, LOST: full bench,
    # it searched for an Applin it could not play).
    if (_ub_survival_mode and ub_score <= 0 and hand_size >= 3 and
            bench_count < 5 and
            not _ub_lillie_in_hand_playable):

        _ub_has_playable_basic_in_hand = False
        if bench_count < 5:
            for _surv_hand_id in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                  Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir):
                if hand_counts.get(_surv_hand_id, 0) >= 1:
                    _ub_has_playable_basic_in_hand = True
                    break
        if not _ub_has_playable_basic_in_hand:

            _ub_has_basic_in_deck = False
            for _surv_id in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                             Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir):
                if ACTIVE_CARDS_IN_DECK.get(_surv_id, {}).get(ZONE_DECK, 0) > 0:
                    _ub_has_basic_in_deck = True
                    break
            if _ub_has_basic_in_deck:
                ub_score = 25000

    if (hand_counts.get(Bug_Catching_Set, 0) >= 1 and
            not itchy_pollen_active and
            ub_score > 0 and ub_score < 25000):
        ub_score -= 1500

    _ub_first_turn_allowed = True
    if _our_first_action_turn:
        _ub_ft_case1 = (bench_count == 0)
        _ub_ft_case2 = (
            (not we_go_first) and
            not watchtower_in_play and
            hand_counts.get(Meowth_ex, 0) == 0 and
            hand_counts.get(Lillie_Determination, 0) == 0 and
            not state.supporterPlayed and
            field_counts.get(Meowth_ex, 0) < 2 and
            bench_count < 5 and
            ACTIVE_CARDS_IN_DECK.get(Meowth_ex, {}).get(ZONE_DECK, 0) > 0 and
            ACTIVE_CARDS_IN_DECK.get(Lillie_Determination, {}).get(ZONE_DECK, 0) > 0)
        _ub_ft_case3 = (
            (not we_go_first) and
            not watchtower_in_play and
            budew_on_op_field and budew_op_index == 0)
        _ub_first_turn_allowed = (
            _ub_ft_case1 or _ub_ft_case2 or _ub_ft_case3)
    if not _ub_first_turn_allowed:
        ub_score = SCORE_VETO

    # FINAL full-bench SAFEGUARD (user, log 86210257
    # step 86, WON vs Mega Starmie). An EXTRA control that has
    # the LAST word over any earlier route that had left
    # ub_score > 0: with a FULL bench (bench_count >= 5) and
    # with NO evolution to complete in play
    # (`_evolve_possible_in_play` = there is no pre-evolution on
    # the board whose next stage is in hand or in the deck),
    # Ultra Ball cannot bench anything new and only wastes its
    # cost (discarding 2 useful cards, e.g. a Hydrapple ex +
    # Forest of Vitality) to bring a DEAD card to hand (a
    # Chikorita that does not fit on the bench). It duplicates
    # the cut-off of L9029/L9220 but as a terminal override, so
    # that no intermediate branch can reactivate it. The ONLY
    # exception: survival mode (empty bench), where
    # bench_count>=5 is already False by itself.
    if (bench_count >= 5
            and not _evolve_possible_in_play
            and not _ub_survival_mode):
        # -100 (below the veto floor of -1) so that, if the rest of the turn's
        # plays are also vetoed (attack/retreat = -1), the argmax prefers
        # ATTACKING/PASSING over wasting this useless Ultra Ball by default
        # (index 0). (user, registro 006 step 72 vs Hops.)
        ub_score = SCORE_CANCEL

    # Sequence (user, registro 010, step 64 vs Alakazam): if the cut of
    # the Alakazam line is active (`_boss_deny_alakazam_line`) and we
    # still have the Boss's Orders in hand unplayed, POSTPONE the Ultra
    # Ball: playing it now would discard the Boss's itself as a cost
    # (often it is the only fodder). It is lowered below the Boss's
    # (BOSS_SCORE_PRIZE_RANK_BASE) so the gust is executed first; once
    # the Boss's is played, this guard stops applying and the Ultra Ball
    # recovers its score.
    if (_boss_deny_alakazam_line and ub_score > 2000
            and hand_counts.get(Boss_Orders, 0) >= 1
            and not state.supporterPlayed):
        ub_score = 2000

    return ub_score


def _ub_cancel_stamp(ctx) -> bool:
    """Phase C of Ultra Ball: cost veto (stamp). Would playing the UB discard
    a valuable card as its cost of 2? A pure predicate; verbatim counting."""
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    state = ctx.state
    ko_last_turn = ctx.ko_last_turn
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_has_ex_immune_active = ctx.op_has_ex_immune_active
    op_has_ex_immune_bench = ctx.op_has_ex_immune_bench
    has_hydrapple = ctx.has_hydrapple
    forest_in_play = ctx.forest_in_play
    meganium_in_play = ctx.meganium_in_play
    ACTIVE_CARDS_IN_DECK = ctx.cards_in_deck

    _ub_cancel_for_stamp = False
    if hand_counts.get(Unfair_Stamp, 0) >= 1:

        # The SPARE COPIES of Ultra Ball (all but the one
        # being played) ARE valid fodder for paying the
        # cost without touching Unfair Stamp. They all used
        # to be excluded from the count, so with a hand of
        # {Unfair Stamp, Ultra Ball, Ultra Ball, Lana's Aid}
        # it only saw 1 discardable card (Lana's) and cancelled
        # the Ultra Ball, ending the turn without searching
        # (user, log 86403004 step 17, LOST vs Iono): the 2nd
        # Ultra Ball + Lana's Aid pay the cost, protect the
        # Stamp and search for Meowth ex -> Lillie's.
        _ub_discardable_without_stamp = max(
            0, hand_counts.get(Ultra_Ball, 0) - 1)
        for _ub_sid, _ub_scnt in hand_counts.items():
            if _ub_sid in (Ultra_Ball, Unfair_Stamp):
                continue
            _ub_discardable_without_stamp += _ub_scnt
        if _ub_discardable_without_stamp < 2:

            _ub_cancel_for_stamp = True

    return _ub_cancel_for_stamp


def _ub_cancel_fez(ctx) -> bool:
    """Phase C of Ultra Ball: cost veto (fez). Would playing the UB discard
    a valuable card as its cost of 2? A pure predicate; verbatim counting."""
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    state = ctx.state
    ko_last_turn = ctx.ko_last_turn
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_has_ex_immune_active = ctx.op_has_ex_immune_active
    op_has_ex_immune_bench = ctx.op_has_ex_immune_bench
    has_hydrapple = ctx.has_hydrapple
    forest_in_play = ctx.forest_in_play
    meganium_in_play = ctx.meganium_in_play
    ACTIVE_CARDS_IN_DECK = ctx.cards_in_deck

    _ub_cancel_for_fez = False
    if (ko_last_turn and
            hand_counts.get(Fezandipiti_ex, 0) >= 1 and
            field_counts.get(Fezandipiti_ex, 0) == 0 and
            bench_count < 5):

        _ub_discardable_without_fez = 0
        for _ub_fid, _ub_fcnt in hand_counts.items():
            if _ub_fid in (Ultra_Ball, Fezandipiti_ex, Unfair_Stamp):
                continue
            _ub_discardable_without_fez += _ub_fcnt
        if _ub_discardable_without_fez < 2:

            _ub_cancel_for_fez = True

    return _ub_cancel_for_fez


def _ub_real_fodder(ctx, protegida) -> int:
    """How many cards from hand the DISCARD scorer would REALLY let go before
    touching `protegida` (the "real fodder" the Ultra Ball's cost of 2 is paid
    with). Counting "every card other than the protected one" is not enough:
    evolution pieces with their pre-evolution in play, the Fezandipiti ex after
    a KO or a Meowth ex that is still playable score LOWER than the protected
    card in the `SelectContext.DISCARD` block, so the engine keeps them and lets
    the protected one go instead. Only what would fall first is counted.

    The Ultra Ball itself is always excluded (it is the card being played, it
    does not pay its own cost) and so is Unfair Stamp (score -10000: never
    discarded).

    Extracted from the body of `_ub_cancel_lillie` (verbatim counting) so that
    the other cost vetoes protecting a Supporter use the SAME arithmetic.

    `protegida` is ONE card id, or a collection of them, or None. The plural
    form exists because two cards can be protected for the same reason at the
    same time, and asked one at a time the count lets each of them pay for the
    other: with {Xerosic, Lillie's, Dawn} in hand, `protegida=Xerosic` counts
    the Lillie's as fodder and `protegida=Lillie's` counts the Xerosic, so both
    vetoes stay silent and the cost eats the pair (see
    `_ub_cancel_engine_supporters`)."""
    if protegida is None:
        _ub_protegidas = ()
    elif isinstance(protegida, int):
        _ub_protegidas = (protegida,)
    else:
        _ub_protegidas = tuple(protegida)

    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    state = ctx.state
    ko_last_turn = ctx.ko_last_turn
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_has_ex_immune_active = ctx.op_has_ex_immune_active
    op_has_ex_immune_bench = ctx.op_has_ex_immune_bench
    has_hydrapple = ctx.has_hydrapple
    forest_in_play = ctx.forest_in_play

    _ub_bench_max = getattr(getattr(ctx, 'my_state', None), 'benchMax', 5) or 5
    _ub_free_bench = max(0, _ub_bench_max - bench_count)

    _ub_discardable_without_lillie = 0
    for _ub_llid, _ub_llcnt in hand_counts.items():
        if _ub_llid in (Ultra_Ball, Unfair_Stamp) or _ub_llid in _ub_protegidas:
            continue
        _ub_ll_fodder = True
        if _ub_llid == Hydrapple_ex:
            if (op_is_crustle_deck or op_has_ex_immune_active or
                    op_has_ex_immune_bench):
                _ub_ll_fodder = True
            elif has_hydrapple:
                _ub_ll_fodder = True
            elif (field_counts.get(Dipplin, 0) >= 1 or
                  field_counts.get(Applin, 0) >= 1):
                _ub_ll_fodder = False
            # THE OTHER HALF OF THE LINE IN HAND, AND THE BASIC TO WEAR IT.
            # The Forest lets a Basic benched this turn evolve on the spot, so
            # {Applin + Dipplin + Hydrapple ex} in hand is a whole chain in one
            # turn and none of the three pieces is fodder. The Basic has to be
            # IN HAND: with it only in the DECK this protection was circular --
            # it vetoed the only card that could dig the Applin out. See
            # `_line_base_benchable`.
            elif (hand_counts.get(Dipplin, 0) >= 1 and
                  (forest_in_play or
                   hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                  _line_base_benchable(Hydrapple_ex, hand_counts,
                                       _ub_free_bench)):
                _ub_ll_fodder = False
        elif _ub_llid == Dipplin:
            if (has_hydrapple and
                    not (op_has_ex_immune_active or op_has_ex_immune_bench)):
                _ub_ll_fodder = True
            elif field_counts.get(Applin, 0) >= 1:
                _ub_ll_fodder = False
            elif (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                  (forest_in_play or
                   hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                  _line_base_benchable(Dipplin, hand_counts, _ub_free_bench)):
                _ub_ll_fodder = False
        elif _ub_llid == Meganium:
            _ub_ll_fodder = not (field_counts.get(Bayleef, 0) >= 1)
        elif _ub_llid == Bayleef:
            _ub_ll_fodder = not (field_counts.get(Chikorita, 0) >= 1)
        # THE PIECE THE SEARCH UN-ORPHANS IS STILL FODDER **HERE** (user,
        # registro_004 step 33 vs Crustle). The `SelectContext.DISCARD` scorer
        # now keeps the top of a line whose missing link this very Ultra Ball
        # will fetch (`_evo_top_unlocked_by_the_search`), and the reflex is to
        # mirror that rule into this count, which exists to say what the
        # discarder would really let go. It is NOT mirrored, on purpose.
        #
        # That protection is a RANKING among the cards the cost will take, not a
        # claim that the piece is untouchable: the menu takes `minCount` cards
        # whatever the scores say, so with no cheaper card in hand the Meganium
        # still falls and nothing deadlocks. Feeding it here would turn the
        # preference into a VETO -- and the veto would cancel the Ultra Ball
        # that is the only thing that un-orphans the piece, leaving us with
        # neither the link nor the search. It is the same circularity
        # `_line_base_benchable` documents ("THE DECK IS NOT A SEAT"), measured
        # on the frozen corpus: mirroring it cancelled three Ultra Balls
        # (registro_017 turn 8, registro_018 turn 6, registro_029 turn 6) that
        # the discarder was perfectly able to pay for out of the rest of the
        # hand.
        elif _ub_llid == Fezandipiti_ex:
            if (ko_last_turn and
                    field_counts.get(Fezandipiti_ex, 0) == 0 and
                    bench_count < 5):
                _ub_ll_fodder = False
        elif _ub_llid == Meowth_ex:
            # Meowth ex is PROTECTED by the DISCARD scorer
            # (score 2) unless: we already have one in play
            # (score 82) or the bench is full AND the turn's
            # supporter has already been played (score 65). Only
            # in those two cases is it real fodder; in any
            # other one the scorer KEEPS it and lets Lillie's go
            # instead (user, log 86412738 step 115, WON vs
            # Hops: hand {UB, Lana's Aid, Lillie's, Meowth ex}
            # with a full bench and the supporter unplayed ->
            # it discarded Lana's + Lillie's and kept a Meowth
            # ex that was not even playable).
            if field_counts.get(Meowth_ex, 0) >= 1:
                _ub_ll_fodder = True
            elif bench_count >= 5 and state.supporterPlayed:
                _ub_ll_fodder = True
            else:
                _ub_ll_fodder = False
        elif _ub_llid in (Lillie_Determination, Dawn):
            # The REFILL Supporters are the MOST protected cards of the
            # SelectContext.DISCARD block while the turn's Supporter is still free
            # and there is only one copy (`_protect_refresh_supporter`): Lillie's
            # scores 2 and Dawn 3, BELOW any other card these vetoes protect
            # (Xerosic vs Alakazam scores 5). The scorer NEVER lets them go before
            # `protegida`: it keeps them and throws the protected one instead.
            # Counting them as fodder was over-counting -- the same failure the
            # log 86401283 adjustment already closed for the evolution pieces, but
            # on the Supporter side.
            #
            # (user, registro_004 steps 43-64 vs Alakazam, LOST). Turn 4,
            # hand {Boss's x2, Ultra Ball x2, Tapu Bulu, Lillie's}: the
            # `_alakazam_dig_xerosic_engine` engine assembled the chain Ultra Ball ->
            # Meowth ex -> Last-Ditch -> Xerosic (5950 > Lillie's 5000) burning Tapu
            # Bulu + a Boss's, and the chain DID get the Xerosic into hand.
            # With the hand already at {Boss's, Lillie's, Ultra Ball, Xerosic},
            # `_ub_real_fodder(prot=Xerosic)` counted 2 (Boss's + Lillie's), so
            # `_ub_cancel_xerosic` did NOT fire: the SECOND Ultra Ball (11400,
            # a value-800 target) beat the Xerosic (7200) and paid its cost with
            # the Boss's and with THE XEROSIC ITSELF. Then it dug out a second Meowth
            # ex -- useless, its Last-Ditch was already spent -- and finished by
            # playing the Lillie's, which shuffled that Meowth back into the deck.
            # Balance of the turn: Tapu Bulu, 2 Boss's, the Xerosic and the 2 Ultra
            # Balls lost, only to end up playing EXACTLY the Supporter the whole
            # chain existed in order not to play.
            if (not state.supporterPlayed
                    and (hand_counts.get(Lillie_Determination, 0)
                         + hand_counts.get(Dawn, 0)) <= 1):
                _ub_ll_fodder = False
        if _ub_ll_fodder:
            _ub_discardable_without_lillie += _ub_llcnt
        else:
            # A PROTECTED EVOLUTION ONLY PROTECTS THE COPIES THE BOARD CAN WEAR
            # (user, registro_002 step 26 vs Marnie, episode 90181011, LOST).
            # Our first turn, hand {Hydrapple ex x2, Dipplin, Dawn, Xerosic,
            # Ultra Ball} with an Applin on the bench. Every branch above said
            # "protected": both Hydrapple ex for the Applin in play, the Dipplin
            # for the same Applin, Dawn for being the lone refill -> real fodder
            # = 1 (the Xerosic) and `_ub_cancel_no_surplus` killed the Ultra
            # Ball. But ONE Applin can only ever wear ONE Hydrapple ex: the
            # second copy was unplayable cardboard and exactly the card the cost
            # should have eaten. Without the Ultra Ball the turn fell back to
            # Dawn (2680), which with no Forest of Vitality in play searches an
            # evolution line we cannot evolve for two more turns -- instead of
            # Ultra Ball -> Meowth ex -> Last-Ditch -> Lillie's Determination,
            # the refill that actually opens the turn.
            #
            # `_evo_copies_usable` is the same arithmetic the DISCARD scorer now
            # applies (`DISCARD_EVO_SPARE_COPY`), so this count keeps mirroring
            # what the discarder would really let go.
            _ub_usable = _evo_copies_usable(
                _ub_llid, hand_counts, field_counts,
                free_bench=_ub_free_bench)
            if _ub_usable is not None:
                # The same floor of one copy the DISCARD scorer keeps: reaching
                # here means a branch above protected the piece, and this only
                # counts the copies BEYOND the first.
                _ub_discardable_without_lillie += max(
                    0, _ub_llcnt - max(1, _ub_usable))
    return _ub_discardable_without_lillie


def _ub_cancel_xerosic(ctx) -> bool:
    """Phase C of Ultra Ball: cost veto (Xerosic's Machinations).

    vs Alakazam, with the opposing hand inflated, Xerosic (the opponent
    discards down to 3) is the play of the turn: it caps Powerful Hand, which
    hits for 20 x (hand + 2). If the Ultra Ball's cost (discarding 2) had to
    eat that Xerosic, the Ultra Ball is worth LESS than what it costs.

    (user, registro_006 step 56 vs Alakazam, LOST -- log 88501752).
    Exact scenario: hand {Dawn, Xerosic's Machinations, Ultra Ball},
    `supporterPlayed=False`, opponent with 11 cards in hand (projected Powerful
    Hand 20 x 13 = 260) and their Alakazam ex had just knocked out our
    Meowth ex. The agent played the Ultra Ball (11900, item band, far
    above the Xerosic at 6200), paid the cost with the ONLY TWO cards it
    had left -- Xerosic AND Dawn -- and brought a Meganium to evolve a
    benched Bayleef. Balance of the turn: hand at 0, Supporter unplayed, the
    opposing hand untouched... and the Meganium it brought would have been
    brought FOR FREE by the Dawn (which searches Basic + Stage 1 + Stage 2 from
    the deck) on the following turn, without discarding anything. The correct
    line was Xerosic now (opponent 11 -> 3 cards, Powerful Hand from 260 to 100)
    and Dawn the next turn.

    That is why the veto asks about the real fodder: with 2+ filler cards the
    Ultra Ball pays for itself without touching the Xerosic and both plays
    coexist in the same turn (the Ultra Ball is an Item, it does not spend the
    Supporter). The veto only fires when paying means burning the disruption.

    `_score_xerosic_play(ctx) > XEROSIC_SCORE_LAST_RESORT` is the gate: it
    reuses the Supporter's real scorer instead of duplicating its conditions, so
    it inherits all of its concessions (opposing hand <= 3, a pending Unfair
    Stamp, a winning gust with Boss's, yielding to Lillie's with a minimal
    opposing hand). If Xerosic is not a real play this turn, there is nothing to
    protect.

    That is also why the veto is NOT tied to the Alakazam matchup: asking the
    scorer makes it deck-agnostic and also covers the
    `generic_very_big_hand` branch (opposing hand >= 7 without an Alakazam
    across the table), where the arithmetic is the same. Measured in matchup
    self-play (400-2000 games vs the crustle / dragapult / hops bots) the effect
    outside Alakazam is neutral."""
    if ctx.hand_counts.get(Xerosic_Machinations, 0) < 1:
        return False
    if ctx.state.supporterPlayed:
        return False
    if _score_xerosic_play(ctx) <= XEROSIC_SCORE_LAST_RESORT:
        return False
    return _ub_real_fodder(ctx, Xerosic_Machinations) < 2


def _ub_cancel_lillie(ctx) -> bool:
    """Phase C of Ultra Ball: cost veto (lillie). Would playing the UB discard
    a valuable card as its cost of 2? A pure predicate; verbatim counting."""
    hand_counts = ctx.hand_counts
    state = ctx.state

    # CANCEL the Ultra Ball if its cost would sacrifice a
    # Lillie's Determination without having played a
    # supporter (user, log 86210811 step 36/37, WON). Scenario:
    # a small hand {Unfair Stamp, Fezandipiti ex, Ultra
    # Ball, Lillie's}, supporterPlayed=False. The Ultra
    # Ball's cost (discard 2) protects Unfair Stamp
    # (-10000) and ends up discarding Fezandipiti +
    # Lillie's, throwing the supporter away. Lillie's
    # (shuffle the hand and draw 6/8) is a MUCH better
    # play and must take priority. We count the cards
    # really discardable WITHOUT touching Lillie's; we also
    # exclude Unfair Stamp because it is never discarded
    # (score -10000), so it cannot pay the cost. If fewer
    # than 2 remain, paying for the Ultra Ball would mean
    # discarding the Lillie's -> it is cancelled and the
    # supporter wins the decision.
    # ADJUSTMENT (user, log 86401283 step 32, WON vs Alakazam):
    # the NAIVE count (every card != UB/Lillie's/Unfair
    # Stamp) over-counted fodder. With a hand of {UB, Hydrapple ex,
    # Lillie's, Grass} and an Applin on the bench, Hydrapple ex is
    # an evolution TARGET: the DISCARD scorer protects it
    # (score 3, BELOW the protected Lillie's ~5), so it is
    # NEVER discarded and Lillie's falls instead. The naive
    # count saw 2 "discardable" cards (Hydrapple + Grass) and did NOT
    # cancel, throwing the supporter away. Now only what the DISCARD
    # scorer WOULD let go before Lillie's counts as fodder: the
    # evolution pieces / a Fez in a PROTECTED state are EXCLUDED
    # (the same low-score criteria of the SelectContext.DISCARD
    # block).
    _ub_cancel_for_lillie = False
    if (not state.supporterPlayed and
            hand_counts.get(Lillie_Determination, 0) >= 1):

        if _ub_real_fodder(ctx, Lillie_Determination) < 2:

            _ub_cancel_for_lillie = True

    return _ub_cancel_for_lillie


def _ub_cancel_tomorrow_supporter(ctx) -> bool:
    """Phase C of Ultra Ball: cost veto (the Supporter that carries NEXT turn).

    Every other Supporter cost veto (`_ub_cancel_lillie`, `_ub_cancel_xerosic`,
    `_ub_cancel_meowth`) is gated on `not state.supporterPlayed`, because they
    compare the Ultra Ball against a Supporter that competes with it TODAY. Once
    the turn's Supporter has been spent, that whole family goes blind -- and so
    does the `SelectContext.DISCARD` scorer, which prices a card by what it does
    NOW and therefore drops a Supporter that can no longer be played. The
    valuation inverts exactly where it should not: the more useless a Supporter
    is this turn, the more eagerly the Ultra Ball's cost eats it, even though it
    is precisely the card that would carry the whole of the next turn.

    (user, log 89628731 step 16 vs Alakazam -- registro_002, WON in spite of
    this.) Our first turn, going second. Board: Tapu Bulu active and Tapu Bulu +
    Teal Mask Ogerpon ex on the bench, NOT ONE energy in play and none in hand
    (so no attacker, this turn or next, without a refill). Hand of exactly three
    cards: {Ultra Ball, Xerosic's Machinations, Lillie's Determination}, with
    the turn's Supporter already spent on the first Xerosic. The Ultra Ball was
    vetoed (-1) by the first-turn gate, but the sterile-turn rescue net brought
    it back to 200 -- `_ub_cost_destroys_better_card` saw no cost problem
    because every veto in it requires an unplayed Supporter -- and it paid its
    two discards with the Xerosic AND the Lillie's to fetch a Chikorita, a body
    the matchup does not care about. The turn ended with a hand of ZERO cards
    and no way to refill it. Ending the turn keeps both Supporters: next turn
    Lillie's Determination draws a whole new hand, which is the only route back
    to an attacker.

    The rule is deck-agnostic -- it names no card, no target and no matchup,
    only the shape of the hand -- and it is bounded by WHERE THE COST COMES
    FROM. The Ultra Ball's two discards have to be paid out of SURPLUS. With the
    Ultra Ball plus exactly two other cards there is no surplus: those two cards
    ARE the cost, whatever they are, and the hand ends the turn at zero. Paying
    with a Supporter out of a hand of seven is a trade (something is kept, and
    the search usually completes an evolution line the same turn); paying with a
    Supporter out of a hand of three is dismantling the engine to bench a body.
    `_ub_score_before_overrides` already refuses the Ultra Ball below three
    cards for this same reason -- this closes the boundary case, where the third
    card is the one that would have restarted the hand.

    Only ONE Supporter is played per turn, so what has to survive the cost is
    ONE of them, not all. At this hand size that distinction collapses: the two
    discards take everything, so any Supporter in hand is the last one -- a hand
    of {Ultra Ball, Lillie's, Lillie's} ends with both Lillie's in the discard,
    not with one kept.

    Deliberately NOT extended above three cards. With four or more the same
    arithmetic can still burn the last Supporter, but the hand survives and the
    two measured counter-examples of the sterile-turn net live there
    (`abomasnow_t6_ub_con_budew_rival`, `abomasnow_t6_ub_preevo_evolucionable`:
    hands of 8 and 7 where the search completes an evolution THIS turn, or the
    opponent's Budew makes the Item use-it-or-lose-it). Widening the bound
    without a measurement would trade a proven gain for a guess.

    Like the rest of the family this is COST arithmetic, not conservatism, so it
    belongs in `_ub_cost_destroys_better_card` and is never revoked because the
    turn came out sterile. The empty-bench survival rescue still overrides it
    (`_ub_terminal_overrides`): with no bench there is no next turn to save the
    Supporter for."""
    state = ctx.state
    hand_counts = ctx.hand_counts

    if not state.supporterPlayed:
        # The Supporter can still be played TODAY: that case belongs to
        # `_ub_cancel_lillie` / `_ub_cancel_xerosic` / `_ub_cancel_meowth`,
        # which also weigh what the Supporter would DO this turn.
        return False

    # The Ultra Ball itself + the two cards that pay for it. Above this the cost
    # comes out of surplus and this veto has nothing to say.
    _ub_hand_size = len(ctx.my_state.hand) if ctx.my_state.hand else 0
    if _ub_hand_size > 3:
        return False

    return any(hand_counts.get(_ub_sid, 0) >= 1 for _ub_sid in _SUPP_PLAY_IDS)


# The two Supporters an Ultra Ball is never allowed to eat. They are not a
# ranking of "the best Supporters": they are the two halves of the engine this
# deck runs on -- the CAP on Powerful Hand and the REFILL that restarts a dead
# hand -- and both are cards whose whole value is that they are still there on
# the turn they are needed. Anything else in hand is a body, a piece or an
# Item, and the cost is welcome to it.
_UB_ENGINE_SUPPORTERS = (Xerosic_Machinations, Lillie_Determination)


def _ub_engine_supporters_held(ctx):
    """Which of `_UB_ENGINE_SUPPORTERS` are in hand AND are an engine on THIS
    board. The two halves do not answer the same way and neither reading is new:

      * LILLIE'S DETERMINATION is the refill, and this deck has no board on
        which drawing a fresh hand is worth nothing. Holding it is enough.

      * XEROSIC'S MACHINATIONS is a cap, and a cap with nothing to cap is
        cardboard -- vs Marnie, with a small opposing hand, its own play scorer
        says `XEROSIC_SCORE_LAST_RESORT` and the discard ladder prices it as
        fodder at 60. So it is an engine only on the boards where the play
        scorer would spend a Supporter on it: the Alakazam matchup above its
        floor of six (`_xr_gate_alakazam`, the branch `alakazam_cap_the_hand`)
        or any deck with their hand at `XEROSIC_BIG_HAND` (the branch
        `generic_very_big_hand`). Both are readings of the BOARD, which is why
        they can be asked here: unlike `_score_xerosic_play` they do not go
        silent the moment this turn's Supporter has been spent, and the whole
        point of this veto is the turn AFTER that one.

    The measured counter-example is the second bullet's reason for existing:
    `tests/test_the_spare_stage_two_pays_the_ultra_ball.py` (registro_002 step
    26 vs Marnie), where the spare Stage 2 and a dead Xerosic pay for the search
    that opens the turn. Protecting a cap with nothing to cap would have
    cancelled it."""
    _ub_engine = []
    if ctx.hand_counts.get(Lillie_Determination, 0) >= 1:
        _ub_engine.append(Lillie_Determination)
    if (ctx.hand_counts.get(Xerosic_Machinations, 0) >= 1
            and (_xr_gate_alakazam(ctx)
                 or ctx.op_hand_count >= XEROSIC_BIG_HAND)):
        _ub_engine.append(Xerosic_Machinations)
    return _ub_engine


def _ub_cancel_engine_supporters(ctx) -> bool:
    """Phase C of Ultra Ball: cost veto (the cost may not eat the engine).

    CARD RULE, as stated by the user: an Ultra Ball NEVER discards a Xerosic's
    Machinations or a Lillie's Determination, unless the Pokemon it is searching
    for wins the game.

    (user, `records/registro_006_pasos_062_hasta_085.json`, episode 91851762,
    step 81, turn 6 vs Alakazam -- LOST.) Tapu Bulu active with no energy on it
    (no attack this turn), the opponent holding TEN cards, hand of four
    {Xerosic's Machinations, Dawn, Ultra Ball, Lillie's Determination} and the
    turn's Supporter already spent. The menu was exactly {play Ultra Ball, end
    turn}: the Ultra Ball was played, paid its two discards with the **Xerosic
    AND the Lillie's**, and fetched a Chikorita -- a Basic that attacks for
    nothing, on a turn that could not attack at all. The turn ended with a hand
    of {Dawn, Chikorita}, the cap on a 240-damage Powerful Hand in the discard
    pile, and no refill left.

    WHY NOTHING SPOKE. Three vetoes already protect exactly these two cards
    (`_ub_cancel_xerosic`, `_ub_cancel_lillie`, `_ub_cancel_meowth`) and all
    three open with `not state.supporterPlayed`, because they were written to
    settle a competition for TODAY'S Supporter slot. Once that slot is spent
    the family goes blind -- and so does the `SelectContext.DISCARD` scorer,
    which prices a card by what it does now. `_ub_cancel_tomorrow_supporter` was
    written for precisely this blindness, and it is bounded at a hand of three;
    this hand had four. One card outside every net.

    AND A SECOND HOLE, INDEPENDENT OF THE FIRST: the count is asked ONE card at
    a time. `_ub_real_fodder(prot=Xerosic)` saw the Lillie's and called it
    fodder; `_ub_real_fodder(prot=Lillie's)` saw the Xerosic and called it
    fodder. Each of the two cards the cost was about to burn was the other's
    proof that nothing was being burnt. That is why this veto protects them as
    a SET and not one by one -- `_ub_real_fodder` takes a collection for this.

    WHAT IT IS NOT. It is not conservatism about Ultra Balls: it says nothing
    about a hand that can pay out of surplus, which is the ordinary case. It
    fires only when the two discards CANNOT be found among the rest of the hand
    -- exactly the arithmetic of the family it joins -- so a hand with two
    spare cards plays its Ultra Ball and keeps the engine, both.

    THE EXCEPTION IS THE ONE THE USER NAMED: unless the search wins the game.
    Read as `plan_of(ctx).wins_this_turn`, the project's own answer to "is there
    a lethal route today" -- so a Ultra Ball that fetches the finisher of a
    ROUTE_PROMOTE, or the body a lethal line is missing, still pays with
    whatever it has to. A game that ends this turn has no next turn to keep a
    Supporter for. The empty-bench survival rescue overrides it as well, through
    `_ub_terminal_overrides`, for the same reason and by the same route as the
    rest of the family.

    Deck-agnostic in shape, named in cards on purpose: the two ids are this
    deck's engine, the way `_ub_cancel_stamp` names the Unfair Stamp."""
    _ub_held = _ub_engine_supporters_held(ctx)
    if not _ub_held:
        return False
    if plan_of(ctx).wins_this_turn:
        return False
    return _ub_real_fodder(ctx, _ub_held) < 2


def _ub_cancel_meowth(ctx) -> bool:
    """Phase C of Ultra Ball: cost veto (meowth). Would playing the UB discard
    a valuable card as its cost of 2? A pure predicate; verbatim counting."""
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    state = ctx.state
    ko_last_turn = ctx.ko_last_turn
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_has_ex_immune_active = ctx.op_has_ex_immune_active
    op_has_ex_immune_bench = ctx.op_has_ex_immune_bench
    has_hydrapple = ctx.has_hydrapple
    forest_in_play = ctx.forest_in_play
    meganium_in_play = ctx.meganium_in_play
    ACTIVE_CARDS_IN_DECK = ctx.cards_in_deck

    _ub_cancel_for_meowth = False
    if (hand_counts.get(Meowth_ex, 0) >= 1 and
          field_counts.get(Meowth_ex, 0) == 0 and
          bench_count < 5 and
          not state.supporterPlayed and
          ACTIVE_CARDS_IN_DECK.get(Lillie_Determination, {}).get(ZONE_DECK, 0) > 0):

        _ub_safe_without_meowth = 0
        for _ub_cid, _ub_cnt in hand_counts.items():
            if _ub_cid in (Ultra_Ball, Meowth_ex):
                continue
            for _ in range(_ub_cnt):
                if _ub_cid == Basic_Grass_Energy:
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Tapu_Bulu:
                    if field_counts.get(Tapu_Bulu, 0) >= 1:
                        _ub_safe_without_meowth += 1
                    elif not (op_has_ex_immune_active or op_has_ex_immune_bench):
                        _ub_safe_without_meowth += 1
                elif _ub_cid == Pinsir:
                    if field_counts.get(Pinsir, 0) >= 1:
                        _ub_safe_without_meowth += 1
                    elif not (op_has_ex_immune_active or op_has_ex_immune_bench):
                        _ub_safe_without_meowth += 1
                elif _ub_cid == Forest_of_Vitality and (forest_in_play or _ub_cnt > 1):
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Fezandipiti_ex and (field_counts.get(Fezandipiti_ex, 0) >= 1 or not ko_last_turn):
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Chikorita and (field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) + field_counts.get(Meganium, 0) >= 1):
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Applin and (field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) + field_counts.get(Hydrapple_ex, 0) >= 1):
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Meganium and meganium_in_play:
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Bayleef and meganium_in_play:
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Lanas_Aid and _ub_cnt > 1:
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Night_Stretcher and _ub_cnt > 1:
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Bug_Catching_Set and _ub_cnt > 1:
                    _ub_safe_without_meowth += 1

        if _ub_safe_without_meowth < 2:
            _ub_cancel_for_meowth = True

    return _ub_cancel_for_meowth


def _counter_stadium_urgent(neutralization_zone_active, watchtower_in_play,
                            forest_in_play, festival_lead_hostil=False) -> bool:
    """Is there an OPPOSING stadium on the field that switches off part of our
    engine -- or switches theirs on -- and that our stadium would remove? With
    our Forest already on the field there is nothing to lift.

      * Neutralization Zone: our ex cannot attack Pokemon that are not ex.
      * Team Rocket's Watchtower: the {C} lose their ability -> it kills
        Meowth ex's Last-Ditch Catch.
      * Festival Grounds (log 88971843, LOST): it switches nothing of ours
        off, but it SWITCHES ON Festival Lead -- their Dipplin repeats the
        attack as soon as it knocks out our active, which is how games against
        that deck are closed. It is the only one of the three that is
        DOUBLE-EDGED (our Dipplin gains it too), which is why it arrives already
        filtered in `festival_lead_hostil`: it only counts when we have seen the
        opponent's Applin/Dipplin line.

    A single predicate for BOTH faces of the same decision: the DISCARD scorer
    uses it so as not to let the card go and the PLAY branch so as not to veto
    it. Having them live separately produced the worst possible result --
    keeping in hand a card that was then illegal to play (log 88359220)."""
    return ((neutralization_zone_active or watchtower_in_play
             or festival_lead_hostil)
            and not forest_in_play)


def _matchup_allows_playing(cid, field_counts, op_is_comfey_deck,
                           op_is_cubchoo_deck, cubchoo_allow_tapu=False,
                           dragapult_no_tapu=False) -> bool:
    """Does the matchup plan allow PUTTING DOWN this Pokemon (and is there room
    left)? A conservative mirror of the PLAY branch's whitelists (Comfey: only
    Teal Mask Ogerpon ex, max 2; Cubchoo: `CUBCHOO_ALLOWED_PLAY_IDS`, max 2
    Ogerpon).

    The RESCUE NETS of the finalisation block consult it; until now they
    switched off entirely with `not op_is_<deck>_deck`. The per-matchup
    prohibition was a crude proxy for this question: what makes digging useless
    vs Comfey is not the matchup itself, it is that the body the search would
    bring will then be vetoed by the plan itself (and then the Ultra Ball will
    have burned two cards from hand for a dead card). Asked this way, the net
    keeps working when the target DOES fit the plan -- vs Comfey, an Ogerpon
    ex with fewer than 2 in play is exactly what the matchup wants.

    Deliberately CONSERVATIVE: it replicates the Ogerpon quota and the lists,
    but not the fine exceptions of the PLAY branch (the opening starter vs
    Comfey, Meowth ex conditioned on there being a Lillie's to fetch vs
    Cubchoo), which treat less as playable than the PLAY branch does, never
    more. If the opponent is neither of those two decks there is no plan
    restricting anything.

    `dragapult_no_tapu` is the same veto the PLAY branch applies vs Dragapult
    with >2 Pokemon in play (see `_dragapult_no_tapu`): without it, the sterile
    turn rescue net paid for an Ultra Ball -- two cards from hand -- for a Tapu
    Bulu that could not then be put down."""
    if dragapult_no_tapu and cid == Tapu_Bulu:
        return False
    if op_is_comfey_deck:
        return (cid == Teal_Mask_Ogerpon_ex
                and field_counts.get(Teal_Mask_Ogerpon_ex, 0) < 2)
    if op_is_cubchoo_deck:
        _permitidos = CUBCHOO_ALLOWED_PLAY_IDS
        if cubchoo_allow_tapu:
            _permitidos = _permitidos + (Tapu_Bulu,)
        if cid not in _permitidos or cid == Meowth_ex:
            return False
        return not (cid == Teal_Mask_Ogerpon_ex
                    and field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2)
    return True


def _bloqueo_de_items_inminente(budew_on_op_field, op_has_dragapult,
                                op_has_dreepy_line) -> bool:
    """Can the opponent leave us WITHOUT Items on OUR next turn?

    Budew attacks for ZERO energy with *Itchy Pollen* ("during your opponent's
    next turn they cannot play Item cards"). As soon as it is on the opposing
    field, every Item in our hand is **use it or lose it**: the Ultra Ball kept
    "until the target is worth it" never gets played. The Dragapult line
    (Dreepy/Drakloak/Dragapult ex) runs it as standard, so the whole matchup
    counts even if the Budew has not appeared yet -- they can put it down and
    attack with it in the same turn.

    It is the same notion the sterile turn rescue net already used
    (`agent()`'s finalisation), now with a name and shared with the
    UB->Meowth->Lillie's chain, which under this threat can dig TODAY for a body
    that is played TOMORROW (`_ub_meowth_for_tomorrow`)."""
    return bool(budew_on_op_field or op_has_dragapult or op_has_dreepy_line)


def _ub_cancel_no_surplus(ctx) -> bool:
    """Phase C of Ultra Ball: cost veto with NO card to name.

    The rest of the family each protect one card: Lillie's, the Xerosic that
    caps Powerful Hand, the Meowth ex that fetches the Supporter, the Stamp, the
    Fezandipiti after a KO, the Supporter that carries tomorrow. Each counts the
    real fodder AROUND its own protected card. None of them fires when the two
    cards that would pay are protected for DIFFERENT reasons and no single one
    of them is "the" card at stake -- and that is a hand with no surplus at all,
    which is the case the whole family exists for.

    (user, registro_004 step 49, episode 89624781 vs Dragapult ex -- WON in
    spite of this.) Hand of three: Unfair Stamp, Meowth ex and Hydrapple ex, with
    an Applin already on the bench and the turn's Supporter spent. The Stamp is
    never discarded (-10000), so the cost of two took the OTHER TWO, whatever
    they were: it burned the Meowth ex and the Hydrapple ex to fetch a Dipplin --
    the intermediate piece of the very line whose Stage 2 it was throwing away.
    `_ub_cancel_meowth` and `_ub_cancel_lillie` were blind (both require the
    turn's Supporter unplayed) and `_ub_cancel_tomorrow_supporter` names only
    Supporters, so nothing spoke.

    The arithmetic is the one already written: with fewer than two cards the
    DISCARD scorer would really let go, the Ultra Ball cannot be paid for out of
    surplus, so it is not paid for at all. It names no card, no target and no
    matchup -- only the shape of the hand -- and, like the rest of the family, it
    is COST arithmetic and is never revoked because the turn came out sterile.
    The empty-bench survival rescue still overrides it (`_ub_terminal_overrides`):
    with no bench there is no next turn to save anything for.

    The SPARE COPIES of the Ultra Ball are added back. `_ub_real_fodder` skips
    every Ultra Ball in hand, because for the vetoes it was written for the card
    being played must not pay its own cost -- but only ONE copy is being played,
    and a second one is the best fodder in the hand (the DISCARD scorer prices a
    duplicate Ultra Ball at 95, above everything else). Counting them out turned
    a hand of two Ultra Balls plus one protected card into a false cancel."""
    _ubs_spare = max(0, ctx.hand_counts.get(Ultra_Ball, 0) - 1)
    return _ub_real_fodder(ctx, None) + _ubs_spare < 2


def _ub_cost_destroys_better_card(ctx) -> bool:
    """Would the Ultra Ball's COST (discarding 2) force us to throw away a card
    BETTER than what the search brings? It groups the cost vetoes of
    phase C (`_ub_cancel_stamp` / `_ub_cancel_fez` / `_ub_cancel_lillie` /
    `_ub_cancel_meowth` / `_ub_cancel_xerosic` /
    `_ub_cancel_tomorrow_supporter`): they all share the same count
    (`_ub_real_fodder`) -- the cards in hand that the DISCARD scorer WOULD let
    go (real fodder) are enumerated and, if fewer than 2 remain, paying for the
    Ultra Ball means burning the Supporter / the evolution piece / the protected
    body.

    It exists as an independent predicate because this veto is of a different
    nature from the other Ultra Ball vetoes: the others say "there is no useful
    target" or "it is early" (conservatism, revocable when the turn turns out
    sterile), while this one says "the play COSTS more than it brings" (card
    arithmetic, NEVER revocable out of boredom). The rescues that resurrect
    vetoed Ultra Balls must consult it before raising their score."""
    return bool(_ub_cancel_stamp(ctx) or _ub_cancel_fez(ctx)
                or _ub_cancel_lillie(ctx) or _ub_cancel_meowth(ctx)
                or _ub_cancel_xerosic(ctx)
                or _ub_cancel_tomorrow_supporter(ctx)
                or _ub_cancel_engine_supporters(ctx)
                or _ub_cancel_no_surplus(ctx))


def _alakazam_dig_xerosic_engine(c) -> bool:
    """vs Alakazam with the opposing hand in Powerful Hand range (>= 6 cards =
    20 x (6+2) = 160+ projected damage): can we ASSEMBLE the Xerosic's
    Machinations cap THIS turn via the engine Ultra Ball -> Meowth ex ->
    Last-Ditch Catch (fetches Xerosic) -> play Xerosic? Xerosic reduces the
    opposing hand and with it Powerful Hand's damage; with an attacker already
    ready it is NOT worth spending the turn's Supporter on Lillie's (a redundant
    refill) -- it is saved for Xerosic and the Meowth is dug out with the Ultra
    Ball.

    Requirements: an Alakazam deck + opposing hand >= 6 + the Supporter
    unplayed; Xerosic in the DECK (if it is already in hand, its own ladder
    plays it, there is nothing to dig for); Meowth reachable (in hand, or in the
    deck with an Ultra Ball to dig it out); a bench slot and a free Last-Ditch
    (field Meowth < 2). Used by the Lillie's veto and by the Ultra Ball
    priority. Deck-agnostic within the Alakazam matchup. `c` can be the
    DecisionContext or the _CtxLillie (both expose these fields, the latter by
    delegation).

    Threshold of opposing hand >= 7 (not >= 6 like the gate for PLAYING
    Xerosic): digging for the disruption consumes a whole turn (Ultra Ball +
    Meowth + Supporter, without refilling), an investment that is only justified
    with the opposing hand clearly inflated -- aligned with the fetch's
    `xerosic_generico`. With 6 cards (the base hand at turn 3-4) the Lillie's
    refill can be worth more than the disruption, so there it is neither vetoed
    nor is the Ultra Ball prioritised."""
    if not (getattr(c, 'op_is_alakazam_deck', False)
            and c.op_hand_count >= 7
            and not c.state.supporterPlayed):
        return False
    # NEVER on OUR first turn (user, log 88461779 step 16 vs Alakazam,
    # LOST): on the first turn Meowth ex is put down ONLY to bring Lillie's
    # Determination. Without this cut-off, this engine assembled the chain Ultra
    # Ball -> Meowth ex -> Xerosic as early as turn 1 (the freshly drawn opposing
    # hand already exceeds 7 cards), spending the Ultra Ball, the Meowth and the
    # turn to dig for a disruption that cannot even be played (going first the
    # Supporter is not playable) while the board is left undeveloped.
    if _pp_es_t1(c):
        return False
    hand = c.hand_counts
    if hand.get(Xerosic_Machinations, 0) >= 1:
        return False
    if c.cards_in_deck.get(
            Xerosic_Machinations, {}).get(ZONE_DECK, 0) < 1:
        return False
    if c.field_counts.get(Meowth_ex, 0) >= 2 or c.bench_count >= 5:
        return False
    _meowth_in_hand = hand.get(Meowth_ex, 0) >= 1
    _meowth_diggable = (
        c.cards_in_deck.get(Meowth_ex, {}).get(ZONE_DECK, 0) >= 1
        and hand.get(Ultra_Ball, 0) >= 1)
    return _meowth_in_hand or _meowth_diggable


def _ub_dig_meowth_gets_played(ctx) -> bool:
    """Would the Meowth ex the Ultra Ball digs out actually get PLAYED this turn?

    The Ultra Ball is only played for a Pokemon we are going to PLAY (user,
    registro_004 step 35 vs Cynthia's Garchomp, WON with a mistake). A Meowth ex
    is worth EXCLUSIVELY its Last-Ditch Catch, and the card's rule allows ONE
    single Last-Ditch per turn: if the Meowth ex already in play APPEARED THIS
    TURN, its ability is already spent (`_meowth_ld_free` False) and a second
    Meowth ex would search for NOTHING -- it would be a 2-prize body on the
    bench in exchange for zero.

    The PLAY branch already knows this: it vetoes the second body except through
    the `_ub_meowth_pending` chain or the 21700 rescue, and BOTH require
    `_meowth_ld_free`. This block of the UB->Meowth->Supporter chain was the
    only side that did not check it: it only looked at `field_counts < 2`. On
    that turn we had a freshly benched Meowth ex (its Last-Ditch had already
    brought the Boss's Orders) and the active charged to knock out; the Ultra
    Ball dug out a SECOND Meowth ex burning Tapu Bulu + Xerosic into the
    discard, and the PLAY branch vetoed it immediately afterwards (score -1):
    the body stayed dead in hand.

    With the Last-Ditch free (no Meowth in play, or only copies from previous
    turns) the chain DOES complete -- that is the case of registro_004 step
    53 vs Alakazam, where the 2nd Meowth searched for by Ultra Ball is played."""
    if not ctx.meowth_ld_free:
        return False
    return ctx.field_counts.get(Meowth_ex, 0) < 2


@dataclass
class _CtxUBHydrapple:
    hand: dict            # hand_counts
    field: dict           # field_counts
    evolvable: dict       # _ub_evolvable (start-of-turn snapshot)
    dipplin_evo_atk: bool         # the active Dipplin evolves AND attacks this turn
    op_ex_immune_active: bool
    op_ex_immune_bench: bool
    hydra_dead_prefer_meowth: bool  # _ub_hydra_dead_prefer_meowth


@dataclass
class _CtxUBMeowth:
    hand: dict                  # hand_counts
    field: dict                 # field_counts
    bench_count: int
    turn: int                  # state.turn
    watchtower: bool            # watchtower_in_play (cancels Last-Ditch)
    supp_values: dict           # _supp_values
    lillie_in_deck: int
    any_supp_in_deck: bool
    prefer_meowth_develop: bool     # _ub_prefer_meowth_develop
    hydra_dead_prefer_meowth: bool  # _ub_hydra_dead_prefer_meowth
    mega_dead_prefer_meowth: bool   # _ub_mega_dead_prefer_meowth
    no_attacker_prefer_meowth: bool  # _ub_no_attacker_prefer_meowth
    t1_going_second_meowth: bool
    dipplin_priority: bool
    active_cant_attack: bool    # _active_cant_attack_this_turn
    mega_line_active: bool      # _mega_line_active
    dragapult: bool             # op_is_dragapult_dusknoir
    supporter_played: bool = False  # state.supporterPlayed
    ld_free: bool = True        # _meowth_ld_free (Last-Ditch unspent)
    # The Ultra Ball was paid for to dig out the Meowth ex that will be put down
    # TOMORROW, under the Item lock of Itchy Pollen (see `_ub_meowth_for_tomorrow`):
    # the fetch MUST complete that purchase even if the Last-Ditch produces nothing
    # today.
    meowth_tomorrow: bool = False
    # The Supporter ALREADY IN HAND wins the turn's only Supporter slot against
    # anything the Last-Ditch could bring (`_supp_in_hand_takes_the_turn`): the
    # fetch would arrive dead. The deck-agnostic generalisation of
    # `lillie_already_in_hand_redundant`.
    supp_in_hand_takes_the_turn: bool = False
    # An Unfair Stamp that is going to be played THIS TURN (`_stamp_pendiente`).
    # It shuffles our whole hand back into the deck, so anything the Last-Ditch
    # fetches returns to the deck unplayed. See
    # `the_stamp_shuffles_the_last_ditch_supporter`.
    stamp_pending: bool = False
    # Their active cannot be touched and their bench can
    # (`_boss_gust_immune_active`): a dodge on heads, a Cornerstone, a Crustle,
    # the Neutralization Zone. The Meowth ex is then not being dug out for a
    # refill but for the Boss's Orders that turns the turn back into damage.
    gust_over_immune_active: bool = False


@dataclass
class _CtxUBFetch:
    hand: dict
    field: dict
    evolvable: dict            # _ub_evolvable (start-of-turn snapshot)
    bench_count: int
    prefer_meowth_develop: bool
    t1_going_second_need_ogerpon: bool
    t1_going_first_need_basic: bool
    has_energy_for_teal: bool
    dipplin_priority: bool
    has_hydrapple: bool
    op_ex_immune_active: bool
    op_ex_immune_bench: bool
    no_attacker_prefer_meowth: bool = False


def _v_ub_ogerpon_t1_primeros(c):
    v = 950
    if c.hand.get(Basic_Grass_Energy, 0) >= 1:
        v = 1000
    if c.field.get(Teal_Mask_Ogerpon_ex, 0) >= 1:
        v = 200
    return v


def _v_ub_ogerpon_teal(c):
    v = 700
    if c.field.get(Teal_Mask_Ogerpon_ex, 0) == 0:
        v = 800
    if c.hand.get(Basic_Grass_Energy, 0) >= 2:
        v += 100
    return v


def _v_ub_chikorita_t1(c):
    v = 850
    if (c.field.get(Applin, 0) >= 1
            or c.field.get(Teal_Mask_Ogerpon_ex, 0) >= 1):
        v = 900
    elif c.field.get(Chikorita, 0) >= 1:
        v = 200
    if c.hand.get(Bayleef, 0) >= 1:
        v += 50
    return v


def _v_ub_applin_t1(c):
    v = 800
    if (c.field.get(Chikorita, 0) >= 1
            or c.field.get(Teal_Mask_Ogerpon_ex, 0) >= 1):
        v = 850
    elif c.field.get(Applin, 0) >= 1:
        v = 180
    if c.hand.get(Dipplin, 0) >= 1:
        v += 50
    return v


def _ub_target_covered_by_hand(cid, hand_counts, field_counts,
                               free_bench=0) -> bool:
    """Do the copies of `cid` ALREADY IN HAND cover everything the board can do
    with that card this turn? Then the Ultra Ball has nothing to search for.

    The Ultra Ball costs TWO cards from hand. It is only ever worth that price
    for something the turn NEEDS and does not already hold: a card that is
    already in hand is played by taking it out of the hand, for free. Digging a
    second copy pays two discards to obtain exactly the board we already had --
    and the two cards it eats are chosen by the DISCARD scorer, so they are the
    two the hand valued least, not two blanks.

    (user, `records/registro_010_pasos_109_hasta_131.json`, step 112, turn 10 vs
    Mega Lucario ex -- WON in spite of this.) Hand {Ultra Ball, **Meowth ex**,
    Night Stretcher x2, Meganium, Chikorita, Hydrapple ex, Grass}, the turn's
    Supporter free, Hydrapple ex active and a lone Meganium on the bench. The
    Meowth ex branch of `_eval_ub_best_target` only asked whether there was one
    IN PLAY (`field_counts == 0`) and whether a Supporter was reachable in the
    deck, so it valued the Ultra Ball at the height of the refill engine (~1000,
    over the Teal Mask Ogerpon ex at 750 that the Grass in hand could have
    charged) -- and the fetch ladder, which asks the same question the same way,
    took the SECOND Meowth ex. Cost of the turn: the Meganium and the Chikorita
    of our own evolution line discarded to buy a card that was already sitting
    in the hand, while the Ogerpon that turns that loose Grass into damage
    stayed in the deck.

    The arithmetic is the one the evolution branches had already written one
    line at a time ("if the Bayleef / Meganium / Dipplin / Hydrapple ex is
    ALREADY in hand, the line evolves without an Ultra Ball"), lifted to a rule
    with no card in it. `_evo_copies_usable` answers it for the evolutions --
    what bounds a Stage is the number of BODIES underneath it, so with two
    Applins on the bench a second Dipplin in hand is still worth searching for.
    Outside our evolution lines the answer is ONE: a Basic in hand is the body
    this turn puts down, and no board uses two copies of the same body for the
    same job in the same turn (Meowth ex is the clearest case -- one Last-Ditch
    Catch per turn, so the second copy is a 2-prize gift for zero).

    Deck-agnostic: it names no card and no matchup. The copy in hand does not
    have to be PLAYABLE for this to hold -- if the bench is full or the matchup
    vetoes the body, the searched copy is just as dead, and the Ultra Ball is
    already cancelled by its own full-bench safeguards."""
    _in_hand = hand_counts.get(cid, 0)
    if _in_hand < 1:
        return False
    _seats = _evo_copies_usable(cid, hand_counts, field_counts,
                                free_bench=free_bench)
    if _seats is None:
        _seats = 1
    return _in_hand >= max(1, _seats)


def _ub_target_has_no_seat(cid, free_bench) -> bool:
    """Is this Ultra Ball target a BODY with nowhere to sit?

    The twin of `_ub_target_covered_by_hand`, and the other half of the same
    question: the Ultra Ball is only worth two cards for something the turn can
    USE. A card the hand already holds cannot be used twice; a card the board
    has no room for cannot be used at all.

    A card enters play by exactly one of two doors, and the card data says
    which: a BASIC (`_evolution_stage == 0`) needs a free BENCH SEAT, an
    evolution needs a BODY of its line already in play -- and the bench being
    full does not close that second door. So with no free seat the Ultra Ball
    fetching a Basic buys a card that stays in hand until the opponent knocks
    something out, while its cost (two cards, chosen by the discard scorer, so
    the two the hand valued least, not two blanks) is paid TODAY. Nothing in
    our own turn ever frees a seat: retreating swaps bodies, it does not
    shrink the bench (see [[la-retirada-intercambia-cuerpos-la-banca-no-encoge]]).

    (user, `records/registro_004_pasos_039_hasta_063.json`, episode 90891885,
    steps 50-57, turn 4 vs Alakazam -- LOST.) Bench FULL (Fezandipiti ex,
    Dipplin, Applin, Teal Mask Ogerpon ex, Chikorita), hand {Ultra Ball x2,
    **Lillie's Determination x2**, Meganium, Dawn, Teal Mask Ogerpon ex,
    Boss's Orders}. The agent played BOTH Ultra Balls and both fetched a
    **Meowth ex** -- a Basic, with no seat for it -- discarding a Teal Mask
    Ogerpon ex, a Dawn, the Meganium and the Boss's Orders to pay for them.
    Four actions later the Lillie's Determination shuffled the two Meowth back
    into the deck. Two Items, four cards and the whole turn's development for
    exactly nothing.

    Deck-agnostic: it names no card, no line and no matchup -- it reads the
    stage off the card data, so it holds for any deck.csv. See
    [[ultraball-solo-si-el-objetivo-se-usa-este-turno]] and
    [[ub-el-hueco-de-banca-no-vale-dos-cartas]]."""
    if free_bench >= 1:
        return False
    return _evolution_stage(cid) == 0


def _ub_wearable_bodies(my_state, field_counts, evolvable_counts,
                        forest_available):
    """The bodies an Ultra Ball target could be played ON TOP OF this turn,
    counted BODY BY BODY.

    With a Forest of Vitality available the question disappears -- anything on
    the board can be evolved, including what came down this turn -- and the
    whole CURRENT field is the answer. Available means in play OR still in
    hand: the copy in hand is one Item away from lifting the restriction, and
    that is the premise of the one-turn chains this same ladder prices
    (`_can_chain_hydra`, `_v_ub_applin_arrancar`: Applin down this turn +
    Forest from hand + the Dipplin the Ultra Ball fetches + the Hydrapple ex in
    hand = a Stage 2 TODAY). A gate blind to it would veto the very search
    those branches buy. Same reading as `_forest_disponible`.

    Without it, what counts is `appearThisTurn` ON EACH BODY, not the
    start-of-turn snapshot per SPECIES. The snapshot answers "was there one of
    these when the turn began", and that is a different question: with an
    Applin on the bench at the start of the turn, evolving it into Dipplin and
    then benching a FRESH Applin leaves the snapshot still saying `Applin: 1`
    while the only Applin in play cannot be evolved until tomorrow -- the
    Ultra Ball then buys a Dipplin that sleeps in hand. It is the same reading
    `_st_evolvable` (`ptcg/turn/finalize.py`) already writes for the
    anti-sterile-turn net, and for the same reason: "with two Applin, one just
    played and another settled, the line DOES come out" is only true body by
    body.

    `evolvable_counts` (`_ub_evolvable`) stays as the FALLBACK for a state with
    no board to read -- the synthetic states of the unit tests -- so those keep
    the behaviour they were written against. This is deliberately the only
    place the sharpened reading lives: the VALUATION branches of this file
    still hang off the start-of-turn snapshot, whose clean-up is measured and
    reverted (see the scope note in `_evolvable_counts`).
    """
    if forest_available:
        return field_counts
    bodies = []
    if my_state is not None:
        bodies = list(getattr(my_state, 'active', None) or [])
        bodies += list(getattr(my_state, 'bench', None) or [])
    if not bodies:
        return evolvable_counts
    counts = {}
    for pkmn in bodies:
        if pkmn is None or getattr(pkmn, 'appearThisTurn', False):
            continue
        counts[pkmn.id] = counts.get(pkmn.id, 0) + 1
    return counts


def _ub_target_cannot_be_worn(cid, evolvable_counts) -> bool:
    """Is this Ultra Ball target an EVOLUTION with no body that can WEAR IT
    THIS TURN?

    The third gate of the same sentence the other two write: the Ultra Ball
    pays two cards from hand, so it is only ever worth that price for a card
    the turn can USE. `_ub_target_covered_by_hand` refuses what the hand
    already holds, `_ub_target_has_no_seat` refuses a Basic with no bench slot,
    and this one refuses the evolution whose body is not evolvable until the
    NEXT turn -- the same "use it or lose it" arithmetic, read on the third
    door a card has into play.

    A Pokemon that came down THIS TURN cannot be evolved (only a Forest of
    Vitality lifts that, in play or one Item away in hand). So the question is
    asked of the bodies that can be EVOLVED today -- `_ub_wearable_bodies`,
    which reads `appearThisTurn` body by body -- and not of `field_counts`.

    (user, `records/registro_004_pasos_037_hasta_060.json`, episode 91184399,
    steps 43-46, turn 4 vs Marnie -- WON in spite of this.) Bench {Meowth ex,
    **Chikorita played this very turn**}, no Forest. The second Ultra Ball of
    the turn discarded a **Meganium** and a Night Stretcher to fetch a
    **Bayleef** that had nothing to evolve: `_evo_link_state` reads the CURRENT
    field, saw the fresh Chikorita as a seat, called the Bayleef the missing
    LINK and lifted it to 900 -- over the Applin (650) that the empty bench
    seat could have put down at once. Four actions later an Unfair Stamp
    shuffled that Bayleef back into the deck. The VALUE menu had priced the
    Item for an Applin and the FETCH menu spent it on a Bayleef: exactly the
    disagreement between the two menus that these gates exist to close.

    Deck-agnostic: it names no card, no line and no matchup -- the stage and
    the pre-evolution come from the card data (see `_evo_body_in_play`), so it
    holds for any deck.csv. See [[ultraball-solo-si-el-objetivo-se-usa-este-turno]]
    and [[coherencia-menu-prompt-habilidades-disponibles]]."""
    _stage = _evolution_stage(cid)
    if not _stage:                      # None (not a Pokemon) or 0 (a Basic)
        return False
    return not _evo_body_in_play(cid, evolvable_counts)


def _eval_ub_best_target(field_counts, hand_counts, meganium_in_play, has_hydrapple,
                         forest_in_play, op_has_ex_immune_active, op_has_ex_immune_bench,
                         op_prize, bench_count, state, ko_last_turn,
                         _best_supp_in_deck_val, supporters_in_hand, hand_is_weak,
                         has_energy_for_teal, _we_go_first=False,
                         _best_supp_in_hand_val=0,
                         op_is_crustle_deck=False, op_is_cornerstone_deck=False,
                         op_active_is_budew=False, meowth_ability_lock=False,
                         op_hand_count=None, op_state=None, cards_in_deck=None,
                         supp_in_hand_takes_the_turn=False, bench_max=5,
                         our_cap_already_spent=False):
    ub_best_target = 0

    _bench_full = (bench_count >= 5)

    _hand_total = sum(hand_counts.values())

    # The FREE SEATS are counted off the board's own `benchMax`, the same way
    # the fetch ladder of `ptcg/turn/options/card.py` counts them. The two
    # menus have to answer "is there room for this body?" with the same
    # number, or the play branch buys the Item for a target the prompt then
    # refuses (see `_offer` and [[coherencia-menu-prompt-habilidades-disponibles]]).
    _ub_free_bench = max(0, (bench_max or 5) - bench_count)

    # WHAT CAN BE EVOLVED THIS TURN. It does NOT use `_evolvable_counts` (the
    # cleaned-up snapshot): MEASURED AND REVERTED. See the scope note in
    # `_evolvable_counts`. It is read HERE, above `_offer`, because the gate on
    # every target needs it and the turn-1/turn-2 branches return before the
    # evolution ladder below.
    _evolvable = AGENT_STATE._field_at_turn_start if (not forest_in_play and AGENT_STATE._field_at_turn_start) else field_counts

    # ...and the BOARD, for the one question that has to be asked body by body
    # ("can this evolution be worn TODAY", `_ub_wearable_bodies`). The
    # synthetic states of the unit tests carry no `players`, and there the
    # helper falls back to the snapshot.
    _ub_players = getattr(state, 'players', None)
    _ub_seat = getattr(state, 'yourIndex', None)
    _ub_my_state = None
    if _ub_players and isinstance(_ub_seat, int) and 0 <= _ub_seat < len(_ub_players):
        _ub_my_state = _ub_players[_ub_seat]
    _ub_forest_available = (forest_in_play
                            or hand_counts.get(Forest_of_Vitality, 0) >= 1)
    _ub_wearable = _ub_wearable_bodies(_ub_my_state, field_counts, _evolvable,
                                       _ub_forest_available)

    def _offer(cid, value):
        """Offer `value` for searching `cid`, unless the hand ALREADY covers it,
        the board has NO ROOM for it or nothing on the board can WEAR it today.

        The single gate every target of this valuation goes through: the Ultra
        Ball pays two cards from hand, so it is only worth it for something the
        turn needs, does not already hold (`_ub_target_covered_by_hand`) and
        can actually put into play -- a Basic through a free bench seat
        (`_ub_target_has_no_seat`), an evolution through a body that came down
        BEFORE this turn (`_ub_target_cannot_be_worn`). The fetch ladder of
        `ptcg/turn/options/card.py` applies the same three gates, so the two
        menus cannot buy the Item for one target and spend it on another."""
        nonlocal ub_best_target
        if _ub_target_covered_by_hand(cid, hand_counts, field_counts,
                                      _ub_free_bench):
            return
        if _ub_target_has_no_seat(cid, _ub_free_bench):
            return
        if _ub_target_cannot_be_worn(cid, _ub_wearable):
            return
        ub_best_target = max(ub_best_target, value)

    if state.turn == 2 and not _we_go_first:

        if (not state.supporterPlayed and
                hand_counts.get(Lillie_Determination, 0) == 0 and
                field_counts.get(Meowth_ex, 0) < 2 and
                bench_count < 5 and
                not meowth_ability_lock and
                AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meowth_ex, {}).get(ZONE_DECK, 0) > 0):
            _lillie_in_deck = AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Lillie_Determination, {}).get(ZONE_DECK, 0)
            if _lillie_in_deck > 0:
                _offer(Meowth_ex, 1100)
            elif any(AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(sid, {}).get(ZONE_DECK, 0) > 0
                     for sid in (Dawn, Lanas_Aid)):
                _offer(Meowth_ex, 950)

        if bench_count == 0:
            _has_basic_in_hand_t1s = any(hand_counts.get(pid, 0) >= 1
                                         for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                                     Tapu_Bulu, Meowth_ex, Fezandipiti_ex,
                                                     Pinsir))
            _active_is_weak_basic = any(field_counts.get(pid, 0) >= 1
                                        for pid in (Applin, Chikorita))
            if not _has_basic_in_hand_t1s and _active_is_weak_basic:
                if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Teal_Mask_Ogerpon_ex, {}).get(ZONE_DECK, 0) > 0:
                    _offer(Teal_Mask_Ogerpon_ex, 1050)

        return ub_best_target

    if state.turn == 1 and _we_go_first:
        # Rule vs an active Budew: if the opponent opens with Budew in the ACTIVE
        # spot, its Itchy Pollen attack will block our Items during OUR next
        # turn. That is why, if we do not have a Lillie's in hand but we do have an
        # Ultra Ball, we must use it NOW to search for Meowth ex, play it and let its
        # ability bring us a Lillie's (a supporter, still playable under the item
        # lock) for the next turn. Top priority and independent of bench
        # development.
        if (op_active_is_budew and
                hand_counts.get(Lillie_Determination, 0) == 0 and
                hand_counts.get(Meowth_ex, 0) == 0 and
                field_counts.get(Meowth_ex, 0) == 0 and
                bench_count < 5 and
                not state.supporterPlayed and
                not meowth_ability_lock and
                AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meowth_ex, {}).get(ZONE_DECK, 0) > 0 and
                AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Lillie_Determination, {}).get(ZONE_DECK, 0) > 0):
            return 1100

        _has_basic_in_hand = any(hand_counts.get(pid, 0) >= 1
                                 for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                             Tapu_Bulu, Fezandipiti_ex, Pinsir))
        if bench_count >= 1 or _has_basic_in_hand:
            return 0

        _best_t1_val = 0

        if (field_counts.get(Teal_Mask_Ogerpon_ex, 0) == 0 and
                AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Teal_Mask_Ogerpon_ex, {}).get(ZONE_DECK, 0) > 0):
            _val = 950
            if hand_counts.get(Basic_Grass_Energy, 0) >= 1:
                _val = 1000
            _best_t1_val = max(_best_t1_val, _val)

        if (field_counts.get(Chikorita, 0) == 0 and
                AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Chikorita, {}).get(ZONE_DECK, 0) > 0):
            _val = 850
            if field_counts.get(Applin, 0) >= 1 or field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1:
                _val = 900
            if hand_counts.get(Bayleef, 0) >= 1:
                _val += 50
            _best_t1_val = max(_best_t1_val, _val)

        if (field_counts.get(Applin, 0) == 0 and
                AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Applin, {}).get(ZONE_DECK, 0) > 0):
            _val = 800
            if field_counts.get(Chikorita, 0) >= 1 or field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1:
                _val = 850
            if hand_counts.get(Dipplin, 0) >= 1:
                _val += 50
            _best_t1_val = max(_best_t1_val, _val)

        ub_best_target = max(ub_best_target, _best_t1_val)
        return ub_best_target

    # The Stamp only blocks the Supporter chain if it is really going to be played
    # (a card rule: `_stamp_worth_playing`). Without `op_hand_count` the gate
    # falls back to the previous behaviour, and the same holds for the three extra
    # clauses: without `op_state`/`cards_in_deck`/`our_cap_already_spent` they are
    # simply off.
    _stamp_blocks_supp_chain = (ko_last_turn
                                and hand_counts.get(Unfair_Stamp, 0) >= 1
                                and _stamp_worth_playing(
                                    op_hand_count, _hand_total,
                                    op_refill_engine=_op_refill_engine(op_state),
                                    buries_the_last_xerosic=_stamp_buries_the_last_xerosic(
                                        hand_counts, cards_in_deck,
                                        state.supporterPlayed, op_state),
                                    our_cap_already_spent=our_cap_already_spent))

    _supp_in_hand_is_inferior = False
    if supporters_in_hand >= 1 and _best_supp_in_deck_val >= 600:

        if _best_supp_in_deck_val > _best_supp_in_hand_val + 100:
            _supp_in_hand_is_inferior = True

    # ...and the "is the one in hand inferior?" comparison above is BLIND to
    # half the Supporters: `_best_supp_in_hand_val` only censuses
    # Boss's/Dawn/Lillie's/Lana's on the `_supp_values` scale, so a hand holding
    # XEROSIC'S MACHINATIONS reads as 0 and the deck always looks better. That
    # is how registro_004 step 36 (vs Alakazam, LOST) paid an Ultra Ball to dig
    # a Meowth ex for a Lillie's while the Xerosic that caps Powerful Hand sat
    # in hand. `supp_in_hand_takes_the_turn` asks the same question with the
    # scorers that really resolve the slot; see `_supp_in_hand_takes_the_turn`.
    meowth_viable = (
        not _stamp_blocks_supp_chain and
        not (state.turn <= 1 and _we_go_first) and
        not state.supporterPlayed and
        not meowth_ability_lock and
        not supp_in_hand_takes_the_turn and
        (supporters_in_hand == 0 or _supp_in_hand_is_inferior) and
        field_counts.get(Meowth_ex, 0) == 0 and
        bench_count < 5 and
        AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meowth_ex, {}).get(ZONE_DECK, 0) > 0 and
        _best_supp_in_deck_val > 200
    )

    if not meowth_viable and op_is_crustle_deck:
        _boss_in_deck = AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Boss_Orders, {}).get(ZONE_DECK, 0) > 0
        _boss_val_ub = _best_supp_in_deck_val
        if (_boss_in_deck and _boss_val_ub >= 900 and
                not state.supporterPlayed and
                not meowth_ability_lock and
                field_counts.get(Meowth_ex, 0) == 0 and
                bench_count < 5 and
                hand_counts.get(Boss_Orders, 0) == 0 and
                AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meowth_ex, {}).get(ZONE_DECK, 0) > 0):
            meowth_viable = True
    if meowth_viable:
        meowth_val = _best_supp_in_deck_val
        if state.turn <= 2:
            meowth_val += 200
        elif hand_is_weak:
            meowth_val += 100
        _offer(Meowth_ex, meowth_val)

    if has_energy_for_teal and field_counts.get(Teal_Mask_Ogerpon_ex, 0) < 2 and bench_count < 5:
        if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Teal_Mask_Ogerpon_ex, {}).get(ZONE_DECK, 0) > 0:
            val = 650
            if field_counts.get(Teal_Mask_Ogerpon_ex, 0) == 0:
                val = 750
            if hand_counts.get(Basic_Grass_Energy, 0) >= 2:
                val += 100
            _offer(Teal_Mask_Ogerpon_ex, val)

    if (has_energy_for_teal and
            field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2 and
            bench_count < 5 and
            field_counts.get(Hydrapple_ex, 0) >= 1):
        if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Teal_Mask_Ogerpon_ex, {}).get(ZONE_DECK, 0) > 0:

            _td_dmg_bonus = 60 if meganium_in_play else 30
            val = 500 + _td_dmg_bonus * 2

            if hand_counts.get(Basic_Grass_Energy, 0) >= 2:
                val += 150

            if field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2:
                val += 50
            _offer(Teal_Mask_Ogerpon_ex, val)

    if not meganium_in_play:
        if _evolvable.get(Bayleef, 0) >= 1:
            # Same criterion as the Bayleef / Dipplin branches below (and as
            # `_ub_evolve_needs_search`): if the evolution is ALREADY in hand, the
            # line evolves WITHOUT Ultra Ball and searching for a 2nd copy adds
            # nothing -- it only burns the card and 2 discards (user, registro_004 step
            # 35 vs Cynthia's Garchomp: Meganium in hand and it dug for it anyway).
            if (AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meganium, {}).get(ZONE_DECK, 0) > 0
                    and hand_counts.get(Meganium, 0) == 0):
                _offer(Meganium, 1000)
        elif _evolvable.get(Chikorita, 0) >= 1 and field_counts.get(Bayleef, 0) >= 1:

            if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meganium, {}).get(ZONE_DECK, 0) > 0:
                if forest_in_play:

                    _offer(Meganium, 1000)
                else:
                    # A Bayleef just evolved THIS turn (there was a Chikorita at the
                    # start of the turn) and WITHOUT Forest: it will not be able to evolve
                    # into Meganium until the NEXT turn. Searching for Meganium now is only
                    # preparation, it adds nothing this turn, so the priority is lowered so
                    # as not to spend an Ultra Ball + 2 discards on an unusable piece if
                    # there are better targets or few safe discards (with >=2 safe discards
                    # and no better target it is still searched for).
                    _offer(Meganium, 280)
        elif _evolvable.get(Chikorita, 0) >= 1:

            if (AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Bayleef, {}).get(ZONE_DECK, 0) > 0
                    and hand_counts.get(Bayleef, 0) == 0):
                # It is only worth searching for a Bayleef if we do not already have one
                # in hand: with a Chikorita in play, a single Bayleef is enough to
                # evolve it. If we already have it, the Ultra Ball adds nothing for
                # this line (and would spend 2 discarded cards on a duplicate).
                _offer(Bayleef, 850)

            elif (AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meganium, {}).get(ZONE_DECK, 0) > 0 and
                  (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                  hand_counts.get(Bayleef, 0) >= 1):
                _prot = 1
                if not forest_in_play:
                    _prot += 1
                if _hand_total - 1 - _prot >= 2:
                    _offer(Meganium, 900)

        elif not _bench_full and field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) == 0:
            if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Chikorita, {}).get(ZONE_DECK, 0) > 0:
                _has_mega_evo_in_deck = (AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Bayleef, {}).get(ZONE_DECK, 0) > 0 or
                                         AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meganium, {}).get(ZONE_DECK, 0) > 0)
                _has_mega_evo_in_hand = (hand_counts.get(Bayleef, 0) >= 1 or hand_counts.get(Meganium, 0) >= 1)
                _forest_available = (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1)

                _can_chain_mega = False
                if _forest_available and hand_counts.get(Bayleef, 0) >= 1:
                    _prot = 1
                    if not forest_in_play:
                        _prot += 1
                    if _hand_total - 1 - _prot >= 2:
                        _can_chain_mega = True
                        _offer(Chikorita, 700)
                if not _can_chain_mega:
                    if _has_mega_evo_in_deck or _has_mega_evo_in_hand:
                        _offer(Chikorita, 500)
                    else:
                        _offer(Chikorita, 200)

    if not has_hydrapple:
        if _evolvable.get(Dipplin, 0) >= 1:
            # With the Hydrapple ex ALREADY in hand the line evolves without Ultra
            # Ball (see the twin Meganium branch above).
            if (AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                    Hydrapple_ex, {}).get(ZONE_DECK, 0) > 0
                    and hand_counts.get(Hydrapple_ex, 0) == 0):
                _offer(Hydrapple_ex, 950)
        elif _evolvable.get(Applin, 0) >= 1 and field_counts.get(Dipplin, 0) >= 1:

            if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Hydrapple_ex, {}).get(ZONE_DECK, 0) > 0:
                if forest_in_play:
                    _offer(Hydrapple_ex, 950)
                else:
                    # A Dipplin just evolved THIS turn (there was an Applin at the start
                    # of the turn) and WITHOUT Forest: it will not be able to evolve into
                    # Hydrapple ex until the NEXT turn. Searching for Hydrapple now is only
                    # preparation; the priority is lowered so as not to spend an Ultra Ball +
                    # 2 discards on an unusable piece if there are better targets or few safe
                    # discards (with >=2 safe discards and no better target it is still
                    # searched for).
                    _offer(Hydrapple_ex, 280)
        elif _evolvable.get(Applin, 0) >= 1:

            if (AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Dipplin, {}).get(ZONE_DECK, 0) > 0
                    and hand_counts.get(Dipplin, 0) == 0):
                # Same criterion as Bayleef: do not search for a Dipplin if there is
                # already one in hand (a single Dipplin is enough to evolve the only Applin).
                _offer(Dipplin, 800)

            elif (AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Hydrapple_ex, {}).get(ZONE_DECK, 0) > 0 and
                  (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                  hand_counts.get(Dipplin, 0) >= 1):
                _prot = 1
                if not forest_in_play:
                    _prot += 1
                if _hand_total - 1 - _prot >= 2:
                    _offer(Hydrapple_ex, 850)
        elif not _bench_full and field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) == 0:
            if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Applin, {}).get(ZONE_DECK, 0) > 0:
                _has_hydra_evo_in_deck = (AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Dipplin, {}).get(ZONE_DECK, 0) > 0 or
                                           AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Hydrapple_ex, {}).get(ZONE_DECK, 0) > 0)
                _has_hydra_evo_in_hand = (hand_counts.get(Dipplin, 0) >= 1 or hand_counts.get(Hydrapple_ex, 0) >= 1)
                _forest_available = (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1)

                _can_chain_hydra = False
                if _forest_available and hand_counts.get(Dipplin, 0) >= 1:
                    _prot = 1
                    if not forest_in_play:
                        _prot += 1
                    if hand_counts.get(Hydrapple_ex, 0) >= 1:
                        _prot += 1
                    if _hand_total - 1 - _prot >= 2:
                        _can_chain_hydra = True
                        if hand_counts.get(Hydrapple_ex, 0) >= 1:

                            _offer(Applin, 950)
                        else:

                            _offer(Applin, 600)
                if not _can_chain_hydra:
                    if _has_hydra_evo_in_deck or _has_hydra_evo_in_hand:
                        _offer(Applin, 450)
                    else:
                        _offer(Applin, 180)

    if not _bench_full and not has_energy_for_teal and field_counts.get(Teal_Mask_Ogerpon_ex, 0) < 2:
        if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Teal_Mask_Ogerpon_ex, {}).get(ZONE_DECK, 0) > 0:
            if field_counts.get(Teal_Mask_Ogerpon_ex, 0) == 0 and bench_count <= 2:
                _offer(Teal_Mask_Ogerpon_ex, 350)

    if not _bench_full and field_counts.get(Tapu_Bulu, 0) == 0:
        if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Tapu_Bulu, {}).get(ZONE_DECK, 0) > 0:
            if meganium_in_play and (op_has_ex_immune_active or op_has_ex_immune_bench):
                val = 750
                if has_hydrapple:
                    val = 850
                _offer(Tapu_Bulu, val)

    if not _bench_full and field_counts.get(Pinsir, 0) == 0:
        if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Pinsir, {}).get(ZONE_DECK, 0) > 0:
            if op_is_crustle_deck or op_is_cornerstone_deck:
                val = 900
                if meganium_in_play:
                    val = 950
                _offer(Pinsir, val)

    if (not _bench_full and not _stamp_blocks_supp_chain and
            not hand_is_weak and not state.supporterPlayed and
            field_counts.get(Meowth_ex, 0) == 0 and supporters_in_hand == 0 and
            _best_supp_in_deck_val >= 500):
        if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meowth_ex, {}).get(ZONE_DECK, 0) > 0:
            if state.turn <= 4:
                _offer(Meowth_ex, min(_best_supp_in_deck_val, 500))

    if not _bench_full and field_counts.get(Fezandipiti_ex, 0) == 0:
        if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Fezandipiti_ex, {}).get(ZONE_DECK, 0) > 0:
            if ko_last_turn:
                _offer(Fezandipiti_ex, 1050)

    return ub_best_target


def _ub_engine_refresh_pivot(ctx) -> bool:
    """The UB -> Meowth -> Lillie's engine BEFORE spending the energies in hand
    (user, registro_008 steps 58-61 vs Archaludon ex, LOST): with the active
    Hydrapple ex unable to KNOCK OUT the opponent, the bench underdeveloped
    (<=1) and the hand holding two cards of SURPLUS (cheap fodder for the Ultra
    Ball's discard), the agent attached an energy and used Ripening Charge with
    the other -- the hand was left at [UB, Boss's] and the Ultra Ball DIED (with
    no 2 cards to discard). The correct line: play the UB NOW (discarding the 2
    energies), search for Meowth ex, put it down (Last-Ditch -> Lillie's) and
    refill: the new hand develops the bench, and Syrup Storm scales with the
    TOTAL Grass on the field. The turn's attachment is still available AFTER
    the refill.

    The surplus is read by `_ub_real_fodder`, not by counting energies: see the
    block on the fodder test below (registro_006 step 53, the same matchup with
    ONE energy and a dead evolution piece next to it)."""
    state = ctx.state
    if state.supporterPlayed:
        return False
    hand_counts = ctx.hand_counts
    # CHEAP FODDER IS A PROPERTY OF THE HAND, NOT THE NAME OF A CARD (user,
    # registro_006 step 53 vs Archaludon ex, episode 92216882, LOST). Turn 6,
    # six prizes to five, our Tapu Bulu knocked out the turn before:
    #
    #     US                                  RIVAL
    #     active Hydrapple ex 330/330,        active Archaludon ex 400/400
    #            2 Grass, no KO in sight             + tool
    #     bench  Bayleef 110/110 (1 of 5)     bench  Duraludon, Dudunsparce
    #     hand   ULTRA BALL, Hydrapple ex,    stadium Full Metal Lab
    #            Basic {G} Energy
    #
    #     [1] Grass -> Bayleef       score  8000   tier 10
    #     [2] Ultra Ball             score 12400   tier  0
    #     [3] Ripening Charge        score 30000   tier 10   <-- played
    #
    # The board is this pivot's board, letter by letter -- an active that does
    # not knock out, one body on the bench, the turn's Supporter unspent, Meowth
    # ex and Lillie's Determination in the deck -- and the pivot stayed silent
    # for ONE reason: it asked for two Basic {G} Energy and the hand held one.
    # So the Ultra Ball kept its ordinary 12400 in tier 0, Ripening Charge took
    # the order (tier 10 decides before any score), the Grass went from hand to
    # the Bayleef, and with two cards left the Ultra Ball -- which discards TWO
    # -- was no longer on the menu at all. The turn ended with the second
    # Hydrapple ex and the Ultra Ball dead in hand and four empty bench seats.
    #
    # The second fodder card was there the whole time. That second Hydrapple ex
    # was UNPLAYABLE cardboard (no Dipplin in play or in hand, one Hydrapple ex
    # already worn), which is exactly what `_ub_real_fodder` is for: it prices
    # EVERY card in hand by what the DISCARD scorer would really let go, keeping
    # the linked evolution pieces, the lone refill Supporter, the playable
    # Meowth ex and the Stamp. Two energies are one instance of "surplus", not
    # the definition of it -- and naming the card made the rule a rule about one
    # deck's hand. This is the same arithmetic `_ub_cancel_no_surplus` uses, and
    # for the same question ("can the cost be paid out of surplus?"), spare
    # copies of the Ultra Ball included: only one copy is being played and a
    # duplicate is the best fodder in the hand.
    #
    # The pivot's own guards are what keep it honest when the surplus includes
    # the last energy in hand: it only fires with the bench at 1 or less and
    # with the active unable to knock out EVEN WITH the turn's attachment, so
    # the energy the cost eats had no KO to enable -- and the refill it buys is
    # what puts the next ones in hand.
    _ubp_spare = max(0, hand_counts.get(Ultra_Ball, 0) - 1)
    if _ub_real_fodder(ctx, None) + _ubp_spare < 2:
        return False
    # With Lillie's or Meowth ALREADY in hand the engine does not need the UB now.
    if (hand_counts.get(Lillie_Determination, 0) >= 1
            or hand_counts.get(Meowth_ex, 0) >= 1):
        return False
    # An underdeveloped bench: the whole reason for the refill (growing the field).
    if ctx.bench_count > 1:
        return False
    cards = ctx.cards_in_deck
    if cards.get(Meowth_ex, {}).get(ZONE_DECK, 0) <= 0:
        return False
    if cards.get(Lillie_Determination, {}).get(ZONE_DECK, 0) <= 0:
        return False
    if ctx.field_counts.get(Meowth_ex, 0) >= 2:
        return False
    # The active does NOT knock out the opposing active NOT EVEN WITH the turn's
    # attachment: with no finisher in sight, expanding resources is worth more
    # than charging loose energy.
    act = ctx.my_state.active[0] if ctx.my_state.active else None
    op_act = _active_of(ctx.op_state)
    if act is None or op_act is None:
        return False
    total_grass = count_total_grass_energy(ctx.my_state)
    eff_e = len(act.energies) + 1
    base = _attacker_base_damage(act.id, op_act, eff_e,
                                 grass_scale=total_grass + 1,
                                 teal_self_energy=eff_e,
                                 bench_count=ctx.bench_count)
    if base <= 0:
        return True
    dmg = _our_effective_damage(act, op_act, base,
                                ctx.meganium_in_play,
                                ctx.neutralization_zone_active)
    return dmg < (op_act.hp or 0)


class _StateSupporterFree:
    """Read-only view of `state` with the turn's Supporter slot UNSPENT.

    Everything else is delegated to the real state; only `supporterPlayed`
    answers False. It exists so a predicate written for "this turn" can be asked
    about the NEXT one without copying it -- see
    `_ub_engine_waits_for_tomorrow`."""

    supporterPlayed = False

    def __init__(self, state):
        self._state = state

    def __getattr__(self, name):
        return getattr(self._state, name)


class _CtxSupporterFree:
    """DecisionContext view whose `state` is `_StateSupporterFree`."""

    def __init__(self, ctx):
        self.c = ctx
        self.state = _StateSupporterFree(ctx.state)

    def __getattr__(self, name):
        return getattr(self.c, name)


def _ub_engine_waits_for_tomorrow(ctx) -> bool:
    """Is THIS board the engine board of `_ub_engine_refresh_pivot`, missing
    only the Supporter slot that this turn has already spent?

    (user, registro_002 step 14 vs Cynthia's Garchomp ex, episode 91529732,
    LOST.) Our first turn going second. Active Tapu Bulu with nothing attached,
    a single Applin on the bench, the turn's Lillie's Determination already
    played and the attachment already made. Hand of six: {Ultra Ball, 2x Grass
    Energy, Bayleef, Meganium, Hydrapple ex} -- the three evolution pieces are
    dead cards (no Chikorita and no Dipplin in play, none in hand), so the whole
    hand is the Ultra Ball plus its two energies. `_score_ultra_ball_play`
    vetoed the Ultra Ball correctly (-1, the first-turn gate: with the Supporter
    spent there is no chain to run today), END scored 0, and the anti-sterile
    net resurrected it at 200 to dig out a Teal Mask Ogerpon ex. The cost took
    the two Grass -- the only fuel that body has -- and the turn ended with a
    210 HP Pokemon that cannot be charged and a hand of three cards that cannot
    be played. The next turn depended entirely on the card drawn.

    What the net never asks is WHEN the Ultra Ball is worth most. It is not a
    card that expires with the turn: ending here keeps it, and the very next
    turn -- Supporter slot free again -- it IS the engine
    `_ub_engine_refresh_pivot` describes: Ultra Ball -> Meowth ex -> Last-Ditch
    Catch -> a refill
    Supporter -> a whole new hand. Every other condition of that engine is
    already met on this board (an underdeveloped bench, two cheap energies to
    pay the cost, Meowth ex and the Supporter alive in the deck, an active that
    cannot knock anything out); the ONLY thing missing is the slot, and the slot
    comes back by itself. So the comparison the net makes -- "a body versus
    nothing" -- is the wrong one: it is "a body now versus the same search
    tomorrow, plus the two cards it costs, plus the Supporter it would fetch".

    Matchup-agnostic: it names no opposing deck and no target of its own, it
    just asks the engine predicate on a view of the state whose Supporter slot
    is free (`_CtxSupporterFree`) -- the only cards in it are the ones OUR
    refill chain is made of, and they are already that predicate's. Any board
    where waiting one turn turns the search into a refill answers True, whoever
    is sitting across the table. It is deliberately the SECOND question the net
    asks, never a replacement: the empty-bench net runs first (with no bench the
    body has to land today or a knockout ends the game) and the item-lock
    exception is kept by the caller (with Budew about to shut the Items off
    there is no tomorrow to wait for).

    It does NOT touch the evolution branch of the net: completing a line is an
    action TODAY, and this rule only says that buying an inert body is not."""
    if not ctx.state.supporterPlayed:
        # The slot is free NOW: whatever the engine is worth, it is worth it
        # this turn, and `_score_ultra_ball_play` already prices it (31450).
        return False
    return _ub_engine_refresh_pivot(_CtxSupporterFree(ctx))


def _ctx_ub_fetch_hydrapple(my_state, state, hand_counts, field_counts,
                            ub_evolvable, op_ex_immune_active,
                            op_ex_immune_bench, hydra_dead_prefer_meowth):
    # If the active is a Dipplin that can evolve into Hydrapple ex and
    # attack this turn (Syrup Storm requires 2 effective energy).
    active = my_state.active[0] if my_state.active else None
    evo_atk = False
    if (active is not None
            and active.id == Dipplin
            and ub_evolvable.get(Dipplin, 0) >= 1):
        e_ahora = len(active.energies)
        can_attach = (not state.energyAttached
                          and hand_counts.get(Basic_Grass_Energy, 0) >= 1)
        e_after = e_ahora + _grass_attach_unit()
        req = AGENT_STATE.ATTACK_ENERGY_REQ.get(Hydrapple_ex, 2)
        if e_ahora >= req or (can_attach and e_after >= req):
            evo_atk = True
    return _CtxUBHydrapple(
        hand=hand_counts, field=field_counts, evolvable=ub_evolvable,
        dipplin_evo_atk=evo_atk,
        op_ex_immune_active=op_ex_immune_active,
        op_ex_immune_bench=op_ex_immune_bench,
        hydra_dead_prefer_meowth=hydra_dead_prefer_meowth)


def _uh_prepare_hydra_next_turn(c):
    """With Dipplin already in play, Hydrapple ex is ONE single evolution away:
    it is worth bringing even if it cannot be evolved this very turn if
    (A) Dipplin is the ONLY Grass Pokemon in play, or (B) the Meganium line
    would develop but canNOT evolve into Meganium this turn. EXCEPT if it is
    better to search for a Bayleef usable NOW (an evolvable Chikorita, no
    Bayleef in hand, with a Bayleef in the deck)."""
    grass_ids = (Applin, Dipplin, Hydrapple_ex, Chikorita, Bayleef,
                 Meganium, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Pinsir)
    grass_in_play = sum(c.field.get(pid, 0) for pid in grass_ids)
    dipplin_unico_grass = (grass_in_play == c.field.get(Dipplin, 0))

    can_evo_meganium_now = (
        not AGENT_STATE.meganium_in_play and (
            c.evolvable.get(Bayleef, 0) >= 1
            or (c.evolvable.get(Chikorita, 0) >= 1
                and (AGENT_STATE.forest_in_play
                     or c.hand.get(Forest_of_Vitality, 0) >= 1)
                and c.hand.get(Bayleef, 0) >= 1)))
    meganium_line_dev = (
        not AGENT_STATE.meganium_in_play and (
            c.hand.get(Bayleef, 0) >= 1
            or c.hand.get(Meganium, 0) >= 1
            or AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Bayleef, {}).get(ZONE_DECK, 0) > 0
            or AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meganium, {}).get(ZONE_DECK, 0) > 0))
    search_bayleef_now = (
        not AGENT_STATE.meganium_in_play
        and c.evolvable.get(Chikorita, 0) >= 1
        and c.hand.get(Bayleef, 0) == 0
        and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Bayleef, {}).get(ZONE_DECK, 0) > 0)

    return (dipplin_unico_grass
            or (meganium_line_dev
                and not can_evo_meganium_now
                and not search_bayleef_now))


def _ctx_ub_fetch_meowth(hand_counts, field_counts, bench_count, turn,
                         watchtower, supp_values, prefer_meowth_develop,
                         hydra_dead_prefer_meowth, mega_dead_prefer_meowth,
                         no_attacker_prefer_meowth, t1_going_second_meowth,
                         dipplin_priority, active_cant_attack,
                         mega_line_active, dragapult,
                         supporter_played=False, ld_free=True,
                         meowth_tomorrow=False,
                         supp_in_hand_takes_the_turn=False,
                         stamp_pending=False,
                         gust_over_immune_active=False):
    return _CtxUBMeowth(
        hand=hand_counts, field=field_counts, bench_count=bench_count,
        turn=turn, watchtower=watchtower, supp_values=supp_values,
        lillie_in_deck=AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
            Lillie_Determination, {}).get(ZONE_DECK, 0),
        any_supp_in_deck=any(
            AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(sid, {}).get(ZONE_DECK, 0) > 0
            for sid in (Lillie_Determination, Boss_Orders, Dawn, Lanas_Aid)),
        prefer_meowth_develop=prefer_meowth_develop,
        hydra_dead_prefer_meowth=hydra_dead_prefer_meowth,
        mega_dead_prefer_meowth=mega_dead_prefer_meowth,
        no_attacker_prefer_meowth=no_attacker_prefer_meowth,
        t1_going_second_meowth=t1_going_second_meowth,
        dipplin_priority=dipplin_priority,
        active_cant_attack=active_cant_attack,
        mega_line_active=mega_line_active,
        dragapult=dragapult,
        supporter_played=supporter_played,
        ld_free=ld_free,
        meowth_tomorrow=meowth_tomorrow,
        supp_in_hand_takes_the_turn=supp_in_hand_takes_the_turn,
        stamp_pending=stamp_pending,
        gust_over_immune_active=gust_over_immune_active)


def _um_boss_engine_vs_untouchable(c):
    """The Ultra Ball digs out the Meowth ex FOR the Boss's Orders when their
    active cannot be touched and their bench can.

    Sibling of `_um_boss_engine_vs_crustle` with one deliberate difference: it
    does NOT ask `supp_values[Boss_Orders] >= 900`. With the Boss's still in
    the deck -- the only board on which digging for it makes sense -- the
    Supporter scorer has run none of its `_bo_*` refinements (they all live
    inside `if hand_counts[Boss_Orders] >= 1`), so the value is whatever the
    ungated base band left. That band reaches 900+ only on branches that name
    an opposing deck: 990 for the Crustle gust, 980 for Drednaw, 950 for the
    Tapu line. A coin dodge has no such branch and falls to the generic tail
    (650 / 500 / 0), so the gate that keeps the Crustle engine honest would
    shut this one off exactly where it is needed.
    `gust_over_immune_active` already carries the whole reason: their active is
    untouchable, their bench is not.
    """
    return (c.gust_over_immune_active
            and c.hand.get(Boss_Orders, 0) == 0
            and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                Boss_Orders, {}).get(ZONE_DECK, 0) > 0)


def _um_boss_engine_vs_crustle(c):
    """vs Crustle, Meowth ex is used to bring Boss's Orders (a gust) via
    Last-Ditch: with no Boss's in hand, with copies in the deck and with a
    valuable projected gust (_supp_values)."""
    return (AGENT_STATE.op_is_crustle_deck
            and c.hand.get(Boss_Orders, 0) == 0
            and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                Boss_Orders, {}).get(ZONE_DECK, 0) > 0
            and c.supp_values.get(Boss_Orders, 0) >= 900)


def _um_is_first_turn(c):
    """OUR first turn of play (turn 1 going first, turn 2 going second)."""
    return ((c.turn == 1 and AGENT_STATE.we_go_first)
            or (c.turn == 2 and not AGENT_STATE.we_go_first))


def _v_ub_chikorita_arrancar(c):
    if _forest_disponible(c) and c.hand.get(Bayleef, 0) >= 1:
        return 880
    if (AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Bayleef, {}).get(ZONE_DECK, 0) > 0
            or AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meganium, {}).get(ZONE_DECK, 0) > 0
            or c.hand.get(Bayleef, 0) >= 1):
        return 700
    return 200


def _v_ub_applin_arrancar(c):
    if _forest_disponible(c) and c.hand.get(Dipplin, 0) >= 1:
        return 980 if c.hand.get(Hydrapple_ex, 0) >= 1 else 800
    if (AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Dipplin, {}).get(ZONE_DECK, 0) > 0
            or AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Hydrapple_ex, {}).get(ZONE_DECK, 0) > 0
            or c.hand.get(Dipplin, 0) >= 1):
        return 650
    return 180


_RULES_UB_HYDRAPPLE = [
    # Evolving the active Dipplin AND attacking this turn is worth more than the
    # Fezandipiti refill (1050): the fetch's top priority.
    _FixedRule("dipplin_evo_attacks",
               lambda c: c.dipplin_evo_atk,
               lambda c: 1200),
    _FixedRule("dipplin_evolvable",
               lambda c: c.evolvable.get(Dipplin, 0) >= 1,
               lambda c: 980),
    _FixedRule("applin_evolvable_full_line",
               lambda c: (c.evolvable.get(Applin, 0) >= 1
                          and (AGENT_STATE.forest_in_play
                               or c.hand.get(Forest_of_Vitality, 0) >= 1)
                          and c.hand.get(Dipplin, 0) >= 1),
               lambda c: 900),
    _FixedRule("applin_evolvable",
               lambda c: c.evolvable.get(Applin, 0) >= 1,
               lambda c: 180),
    _FixedRule("applin_on_field",
               lambda c: c.field.get(Applin, 0) >= 1,
               lambda c: 130),
]


_AJUSTES_UB_HYDRAPPLE = [
    _Adjustment("prepare_hydra_for_next_turn",
            lambda c, s: (c.field.get(Dipplin, 0) >= 1 and s < 860
                          and _uh_prepare_hydra_next_turn(c)),
            lambda c, s: 860),
    # Against decks with EX IMMUNITY (e.g. Crustle), Hydrapple ex is an ex
    # attacker that cannot damage them: a dead card, it yields to the Meganium
    # line or the non-ex attackers. EXCEPTION `evo_doomed_hittable`: if it
    # evolves the doomed active Dipplin and the opposing active is NOT
    # immune (Kangaskhan ex), the clamp does not apply (an evolution and
    # survival pivot: 80 HP -> 330 HP).
    _Adjustment("clamp_dead_ex_vs_crustle",
            lambda c, s: (not (c.dipplin_evo_atk
                               and not c.op_ex_immune_active)
                          and (AGENT_STATE.op_is_crustle_deck
                               or c.op_ex_immune_active
                               or c.op_ex_immune_bench)),
            lambda c, s: min(s, 40)),
    # Hydrapple ex would be dead this turn (it does not attack) and the
    # Meowth ex -> Lillie's refill engine is available: it yields the search to
    # Meowth ex (1000), which rebuilds the hand.
    _Adjustment("yields_to_meowth_refresh",
            lambda c, s: c.hydra_dead_prefer_meowth,
            lambda c, s: min(s, 150)),
]


_RULES_UB_MEOWTH = [
    # FIRST TURN: the Ultra Ball only digs for Meowth ex to bring Lillie's
    # Determination (user, log 88461779 vs Alakazam, LOST). If the Lillie's
    # is ALREADY in hand there is nothing to search for (and the veto on playing
    # the Meowth would leave it dead in hand); if there is NONE left in the deck,
    # the Last-Ditch fetch would not bring the refill that justifies the cost. In
    # both cases the Ultra Ball searches for something else (an evolution line, an
    # attacker). It goes FIRST: neither the pivot engine nor the Boss's vs Crustle
    # engine lifts this rule on the first turn.
    _FixedRule("first_turn_only_for_lillie",
               lambda c: (_um_is_first_turn(c)
                          and (c.hand.get(Lillie_Determination, 0) >= 1
                               or c.lillie_in_deck <= 0)),
               lambda c: 10),
    # Team Rocket's Watchtower cancels Meowth ex's ability (a Colorless
    # Pokemon): do not search for it with the Ultra Ball.
    _FixedRule("watchtower_cancels_the_ability",
               lambda c: c.watchtower,
               lambda c: 10),
    # NO SEAT, NO BODY, NO ABILITY (user, registro_004 steps 50-57 vs Alakazam,
    # LOST). It used to sit near the bottom of this ladder, below every engine,
    # and that is where it lost: `_ub_engine_pivot_turn` had been armed earlier
    # in the turn -- with the bench at 4 and a slot to spare -- and by the time
    # the Ultra Ball was actually played the Chikorita had filled the bench.
    # The flag does not know that; `engine_pivot_turn` (1300) fired anyway and
    # the fetch bought a Meowth ex that could not be put down.
    #
    # It belongs HERE, with the other "the Last-Ditch cannot produce anything"
    # vetoes: a body that cannot be put down has no ability to use, which is
    # the same thing the Watchtower does to it. No engine outranks that, because
    # every engine that arms itself (`_ub_engine_refresh_pivot`,
    # `_alakazam_dig_xerosic_engine`, `_ub_meowth_for_tomorrow`) already
    # required a free seat when it did: this only stops the promise from
    # outliving the premise. See [[la-cesion-solo-vale-mientras-su-beneficiario-siga-vivo]].
    _FixedRule("full_bench",
               lambda c: c.bench_count >= 5,
               lambda c: 10),
    # THE STAMP SHUFFLES BACK WHATEVER THE LAST-DITCH BRINGS (user, registro_008
    # step 70 vs Marnie's Grimmsnarl, WON suboptimally). A third way for the
    # ability to produce nothing, and the only one that is not on the board but
    # in the ORDER of the turn: with an Unfair Stamp that is going to be played
    # this turn (`_stamp_pendiente`), every `_SUPP_PLAY_IDS` scorer yields the
    # turn to it, so NO Supporter the Last-Ditch could fetch is playable before
    # the Stamp -- and the Stamp shuffles our whole hand into the deck. In that
    # step the Ultra Ball was BOUGHT for the Fezandipiti refill
    # (`refill_after_a_ko`, 1050 -> ub_score 12250) and then spent on a Meowth ex
    # that went straight back to the deck three actions later, together with the
    # Night Stretcher and the Dipplin its cost had already discarded FOREVER.
    #
    # It goes ABOVE `item_lock_tomorrow`: buying a body for TOMORROW is void too
    # when the Stamp returns it to the deck TODAY. It is a rule of the CARD, not
    # of the matchup -- the Stamp reads the same against any opposing deck.
    _FixedRule("the_stamp_shuffles_the_last_ditch_supporter",
               lambda c: c.stamp_pending,
               lambda c: 10),
    # ITEM LOCK TOMORROW: the Ultra Ball was played EXACTLY to dig out this
    # body (`_ub_meowth_for_tomorrow`, registro_002 step 17 vs Dragapult), so
    # the fetch has to complete the purchase. It goes ABOVE
    # `last_ditch_produces_nothing`: it is true that the ability produces nothing today --
    # that is the point, the Meowth ex is put down TOMORROW, when there will be no
    # Items left to search for it and the Supporter slot is free again.
    _FixedRule("item_lock_tomorrow",
               lambda c: c.meowth_tomorrow,
               lambda c: 1250),
    # THE LAST-DITCH HAS TO BE ABLE TO PRODUCE SOMETHING THIS TURN (user,
    # registro_006 steps 98-104 vs Mega Lucario ex, LOST). Meowth ex is worth
    # EXCLUSIVELY its Last-Ditch Catch -> Supporter; the body itself is
    # a 2-prize gift. There are two ways for the ability to produce
    # nothing, and neither was checked here:
    #   1) `supporter_played`: the turn's Supporter has ALREADY been played, so
    #      whatever the fetch brings stays dead in hand (and the PLAY branch vetoes
    #      the Meowth through [[no-meowth-si-supporter-ya-jugado]]).
    #   2) `not ld_free`: some Meowth ex in play APPEARED THIS TURN, so
    #      the turn's only Last-Ditch is already spent (see `_meowth_ld_free` and
    #      `_ub_dig_meowth_gets_played`).
    # On that turn 6 we had played Lillie's and the Ultra Ball still brought
    # a Meowth ex (1000, beating Chikorita/Meganium/Bayleef); the agent chained
    # a SECOND Ultra Ball to dig out the other Meowth ex and ended up attacking
    # anyway, 4 cards of hand (Forest, Xerosic, Dipplin, Lana's) for two dead
    # bodies. It goes with the "the ability does not work" vetoes (Watchtower) and
    # above the pivot engines, which in any case require a free Supporter
    # (`_ub_engine_refresh_pivot` / `_alakazam_dig_xerosic_engine`).
    _FixedRule("last_ditch_produces_nothing",
               lambda c: c.supporter_played or not c.ld_free,
               lambda c: 10),
    # THE BODY IN FRONT CANNOT BE TOUCHED (user, episode 90325863, turn 8 vs
    # a Dragapult / Azumarill deck): their Marill hid behind a Hide that came
    # up heads, so every attack of ours resolves for zero against it. The
    # Ultra Ball is then not digging for a refill -- it is digging for the
    # Meowth ex whose Last-Ditch Catch brings the BOSS'S ORDERS that gusts an
    # attackable body off their bench. It goes right after the vetoes that say
    # the ability cannot work at all (Watchtower, Supporter spent, Last-Ditch
    # spent) and ABOVE `lillie_already_in_hand_redundant`: a Lillie's in hand
    # is no answer to an untouchable active, it only draws cards at it.
    # 1300, the height of the other paid-for chains. Wall-agnostic.
    _FixedRule("boss_engine_vs_untouchable",
               _um_boss_engine_vs_untouchable,
               lambda c: 1300),
    # With Lillie's ALREADY in hand the Meowth ex fetch is redundant (its only
    # purpose is to search for Lillie's); a useful evolution is better. EXCEPTION:
    # vs Crustle, Meowth ex brings Boss's Orders (a gust), not a refill. (user,
    # log 86339167 step 23, LOST vs Mega Starmie)
    #
    # GENERALISED to any Supporter (user, registro_004 step 36 vs Alakazam,
    # episode 90106609, LOST): the redundancy is not "Lillie's is in hand", it
    # is "the Supporter slot of this turn is already taken by something better
    # than what the Last-Ditch can bring". There the card in hand was XEROSIC'S
    # MACHINATIONS against a 10-card hand (Powerful Hand = 20 per card), this
    # rule stayed silent because it only knows Lillie's, and the ladder fell to
    # `lillie_in_deck_refresh` (1000): the Ultra Ball dug out the Meowth ex, the
    # Last-Ditch brought Lillie's, and the committed Lillie's spent the slot AND
    # shuffled the Xerosic back into the deck. `supp_in_hand_takes_the_turn`
    # answers the same question with the real play scorers -- see
    # `_supp_in_hand_takes_the_turn` in main.py.
    _FixedRule("the_turns_supporter_is_already_in_hand",
               lambda c: ((c.hand.get(Lillie_Determination, 0) >= 1
                           or c.supp_in_hand_takes_the_turn)
                          and not _um_boss_engine_vs_crustle(c)
                          and not AGENT_STATE._ub_engine_pivot_turn),
               lambda c: 10),
    # UB->Meowth->Lillie's engine (registro_008 step 58 vs Archaludon,
    # LOST): the Ultra Ball was played FOR the pivot; the fetch MUST
    # complete the chain. Above development (1000-1250) and evolutions.
    _FixedRule("engine_pivot_turn",
               lambda c: AGENT_STATE._ub_engine_pivot_turn,
               lambda c: 1300),
    # The only Pokemon in play + no playable Basic + no Lillie's in hand:
    # put Meowth down, search for Lillie's and refill.
    _FixedRule("develop_the_only_pokemon",
               lambda c: c.prefer_meowth_develop,
               lambda c: 1250),
    # The only big evolution (Hydrapple ex on top of Dipplin) would be
    # dead this turn: refilling with Meowth/Lillie's opens more options.
    _FixedRule("dead_hydra_prefers_meowth",
               lambda c: c.hydra_dead_prefer_meowth,
               lambda c: 1000),
    # The Meganium line adds nothing this turn and there is no ready attacker.
    _FixedRule("dead_meganium_prefers_meowth",
               lambda c: c.mega_dead_prefer_meowth,
               lambda c: 1000),
    # With no USABLE attacker this turn (neither an active that attacks nor a
    # promotable benched one): the refill beats an evolution without an attack.
    # >1000 to beat a playable Meganium. (registro_004 step 29 vs Mega Starmie)
    _FixedRule("no_attacker_prefers_meowth",
               lambda c: c.no_attacker_prefer_meowth,
               lambda c: 1250),
    _FixedRule("t1_going_second",
               lambda c: c.t1_going_second_meowth,
               lambda c: 1200),
    _FixedRule("t1_going_first_no",
               lambda c: c.turn == 1 and AGENT_STATE.we_go_first,
               lambda c: 10),
    _FixedRule("already_two_meowth_in_play",
               lambda c: c.field.get(Meowth_ex, 0) >= 2,
               lambda c: 10),
    _FixedRule("one_meowth_and_the_active_attacks",
               lambda c: (c.field.get(Meowth_ex, 0) >= 1
                          and not c.active_cant_attack),
               lambda c: 10),
    # A condition that favours Dipplin holds: Meowth yields.
    _FixedRule("yields_to_priority_dipplin",
               lambda c: c.dipplin_priority,
               lambda c: 10),
    _FixedRule("mega_line_active_with_lillie",
               lambda c: c.mega_line_active and c.lillie_in_deck > 0,
               lambda c: 1150),
    _FixedRule("vs_dragapult_with_lillie",
               lambda c: c.dragapult and c.lillie_in_deck > 0,
               lambda c: 985),
    _FixedRule("boss_engine_vs_crustle",
               _um_boss_engine_vs_crustle,
               lambda c: 1100),
    # No condition favouring Dipplin: Meowth ex has PRIORITY to refill
    # (searching for Lillie's), regardless of the hand.
    _FixedRule("lillie_in_deck_refresh",
               lambda c: c.lillie_in_deck > 0,
               lambda c: 1000),
    # Another supporter in the deck: refill anyway.
    #
    # NEVER EVALUATED, AND NOT DEAD (user, August 2026, `utils/rule_census.py`:
    # the chain is walked 3 416 times and this `when` is never called). It is
    # the tail of the chain, so the rule above it always fired -- and that rule
    # asks `lillie_in_deck > 0`, which with four Lillie's in a sixty-card deck
    # is nearly always true. The corner this one answers is the late game where
    # the deck has run out of Lillie's and still holds some other Supporter.
    # The workload did not reach it; the game can.
    _FixedRule("another_supporter_in_deck",
               lambda c: c.any_supp_in_deck,
               lambda c: 850),
]


_RULES_UB_OGERPON = [
    # It yields the search to Meowth ex (hand refill): Ogerpon ex would only
    # be brought here if we ALREADY had a Lillie's in hand.
    _FixedRule("yields_to_meowth_develop",
               lambda c: c.prefer_meowth_develop,
               lambda c: 200),
    _FixedRule("t1_second_needs_ogerpon",
               lambda c: c.t1_going_second_need_ogerpon,
               lambda c: 1050),
    _FixedRule("t1_going_first_needs_a_basic",
               lambda c: c.t1_going_first_need_basic,
               _v_ub_ogerpon_t1_primeros),
    _FixedRule("already_two_ogerpon",
               lambda c: c.field.get(Teal_Mask_Ogerpon_ex, 0) >= 2,
               lambda c: 350 if (c.has_energy_for_teal
                                 and c.bench_count < 5) else 15),
    _FixedRule("energy_for_teal_dance",
               lambda c: c.has_energy_for_teal and c.bench_count < 5,
               _v_ub_ogerpon_teal),
    _FixedRule("first_ogerpon_short_bench",
               lambda c: (c.field.get(Teal_Mask_Ogerpon_ex, 0) == 0
                          and c.bench_count <= 2),
               lambda c: 300),
]


_RULES_UB_MEGANIUM = [
    _FixedRule("meganium_already_in_play",
               lambda c: AGENT_STATE.meganium_in_play,
               lambda c: 25),
    # vs Cornerstone: Wild Growth doubles every Grass and lowers the cost of
    # Tapu Bulu -- the ONLY attacker that damages Cornerstone -- from 4 physical
    # Grass to 2. With the line already started in play, completing it is the
    # priority search even though Meganium itself cannot damage it.
    _FixedRule("mega_line_enables_tapu_vs_cornerstone",
               lambda c: (AGENT_STATE.op_is_cornerstone_deck
                          and (c.field.get(Chikorita, 0) >= 1
                               or c.field.get(Bayleef, 0) >= 1)),
               lambda c: 1050),
    _FixedRule("bayleef_evolvable",
               lambda c: c.evolvable.get(Bayleef, 0) >= 1,
               lambda c: 1000),
    _FixedRule("full_chikorita_chain",
               lambda c: (c.evolvable.get(Chikorita, 0) >= 1
                          and _forest_disponible(c)
                          and c.hand.get(Bayleef, 0) >= 1),
               lambda c: 950),
    _FixedRule("chikorita_evolvable",
               lambda c: c.evolvable.get(Chikorita, 0) >= 1,
               lambda c: 200),
    _FixedRule("chikorita_on_field",
               lambda c: c.field.get(Chikorita, 0) >= 1,
               lambda c: 150),
]


_RULES_UB_BAYLEEF = [
    _FixedRule("meganium_already_in_play",
               lambda c: AGENT_STATE.meganium_in_play,
               lambda c: 20),
    _FixedRule("bayleef_already_on_field",
               lambda c: c.field.get(Bayleef, 0) >= 1,
               lambda c: 20),
    # There is already a Bayleef IN HAND: searching for another is redundant (one
    # is enough for the only Chikorita); do not waste the UB or its discard.
    _FixedRule("bayleef_already_in_hand",
               lambda c: c.hand.get(Bayleef, 0) >= 1,
               lambda c: 20),
    # vs Cornerstone, Bayleef is the intermediate step towards Meganium (which
    # doubles the Grass and leaves Tapu Bulu attacking with 2 physical) and it is
    # also one of the two bodies WITHOUT an ability that do damage it.
    _FixedRule("mega_line_vs_cornerstone",
               lambda c: (AGENT_STATE.op_is_cornerstone_deck
                          and c.field.get(Chikorita, 0) >= 1),
               lambda c: 1000),
    _FixedRule("chikorita_evolvable",
               lambda c: c.evolvable.get(Chikorita, 0) >= 1,
               lambda c: 950 if (c.hand.get(Meganium, 0) >= 1
                                 and AGENT_STATE.forest_in_play) else 850),
    _FixedRule("chikorita_on_field",
               lambda c: c.field.get(Chikorita, 0) >= 1,
               lambda c: 200),
]


_RULES_UB_DIPPLIN = [
    _FixedRule("hydrapple_already_in_play",
               lambda c: c.has_hydrapple,
               lambda c: 20),
    _FixedRule("dipplin_already_on_field",
               lambda c: c.field.get(Dipplin, 0) >= 1,
               lambda c: 20),
    # Same criterion as Bayleef: a redundant duplicate.
    _FixedRule("dipplin_already_in_hand",
               lambda c: c.hand.get(Dipplin, 0) >= 1,
               lambda c: 20),
    # Dipplin is only favoured with _dipplin_priority; otherwise Meowth ex
    # refills better and Dipplin drops so as not to steal its search.
    _FixedRule("applin_evolvable",
               lambda c: c.evolvable.get(Applin, 0) >= 1,
               lambda c: ((920 if (c.hand.get(Hydrapple_ex, 0) >= 1
                                   and AGENT_STATE.forest_in_play) else 800)
                          if c.dipplin_priority else 150)),
    _FixedRule("applin_on_field",
               lambda c: c.field.get(Applin, 0) >= 1,
               lambda c: 200),
    _FixedRule("opponent_anti_ex",
               lambda c: c.op_ex_immune_active or c.op_ex_immune_bench,
               lambda c: 600 if c.evolvable.get(Applin, 0) >= 1 else 150),
]


_RULES_UB_CHIKORITA = [
    _FixedRule("t1_going_first_needs_a_basic",
               lambda c: c.t1_going_first_need_basic,
               _v_ub_chikorita_t1),
    _FixedRule("meganium_already_in_play",
               lambda c: AGENT_STATE.meganium_in_play,
               lambda c: 30),
    _FixedRule("meganium_line_already_started",
               lambda c: (c.field.get(Chikorita, 0)
                          + c.field.get(Bayleef, 0)
                          + c.field.get(Meganium, 0)) > 0,
               lambda c: 150),
    _FixedRule("start_the_meganium_line",
               lambda c: True,
               _v_ub_chikorita_arrancar),
]


_RULES_UB_APPLIN = [
    _FixedRule("t1_going_first_needs_a_basic",
               lambda c: c.t1_going_first_need_basic,
               _v_ub_applin_t1),
    _FixedRule("hydrapple_already_in_play",
               lambda c: c.has_hydrapple,
               lambda c: 25),
    _FixedRule("hydra_line_already_started",
               lambda c: (c.field.get(Applin, 0)
                          + c.field.get(Dipplin, 0)
                          + c.field.get(Hydrapple_ex, 0)) > 0,
               lambda c: 120),
    _FixedRule("start_the_hydra_line",
               lambda c: True,
               _v_ub_applin_arrancar),
]


_RULES_UB_TAPU = [
    _FixedRule("tapu_already_on_field",
               lambda c: c.field.get(Tapu_Bulu, 0) >= 1,
               lambda c: 15),
    # A non-ex attacker against ex-immune opponents, with Meganium doubling
    # its energy; better still if Hydrapple ex already covers the ex role.
    _FixedRule("anti_ex_with_meganium",
               lambda c: (AGENT_STATE.meganium_in_play
                          and (c.op_ex_immune_active
                               or c.op_ex_immune_bench)),
               lambda c: 850 if c.has_hydrapple else 750),
]


_RULES_UB_PINSIR = [
    _FixedRule("anti_ex",
               lambda c: (c.field.get(Pinsir, 0) == 0
                          and (AGENT_STATE.op_is_crustle_deck
                               or AGENT_STATE.op_is_cornerstone_deck)),
               lambda c: 900),
]


_RULES_UB_FEZ = [
    # Refill after a KO with Flip the Script (a benched Fezandipiti ex draws 3 when
    # we are knocked out). It is a good search IF we already have a usable attacker
    # or if the Meowth ex -> Last-Ditch -> Lillie's engine is NOT available. But if
    # there is NO usable attacker and Meowth ex + Lillie's are STILL in the deck (an
    # intact refill engine, `no_attacker_prefer_meowth`), it is better to bring
    # Meowth ex: putting it down searches for Lillie's and rebuilds the WHOLE hand
    # (up to 8 cards), opening many more options than Fezandipiti's 3-card draw
    # (user). Fez yields and its branch falls back to the default (10); Meowth ex
    # (`no_attacker_prefers_meowth`=1250 or other refill branches) wins the
    # search. Deck-agnostic.
    _FixedRule("refill_after_a_ko",
               lambda c: (c.field.get(Fezandipiti_ex, 0) == 0
                          and AGENT_STATE.ko_last_turn and c.bench_count < 5
                          and not c.no_attacker_prefer_meowth),
               lambda c: 1050),
]

__all__ = [
    '_UBFlags',
    '_ub_derive_flags',
    '_ub_terminal_overrides',
    '_ub_cancel_stamp',
    '_ub_cancel_fez',
    '_ub_real_fodder',
    '_ub_target_covered_by_hand',
    '_ub_cancel_xerosic',
    '_ub_cancel_lillie',
    '_ub_cancel_tomorrow_supporter',
    '_UB_ENGINE_SUPPORTERS',
    '_ub_engine_supporters_held',
    '_ub_cancel_engine_supporters',
    '_ub_cancel_no_surplus',
    '_ub_cancel_meowth',
    '_counter_stadium_urgent',
    '_matchup_allows_playing',
    '_bloqueo_de_items_inminente',
    '_ub_cost_destroys_better_card',
    '_alakazam_dig_xerosic_engine',
    '_ub_dig_meowth_gets_played',
    '_ub_target_has_no_seat',
    '_ub_target_cannot_be_worn',
    '_ub_wearable_bodies',
    '_CtxUBHydrapple',
    '_CtxUBMeowth',
    '_CtxUBFetch',
    '_v_ub_ogerpon_t1_primeros',
    '_v_ub_ogerpon_teal',
    '_v_ub_chikorita_t1',
    '_v_ub_applin_t1',
    '_ub_engine_refresh_pivot',
    '_StateSupporterFree',
    '_CtxSupporterFree',
    '_ub_engine_waits_for_tomorrow',
    '_uh_prepare_hydra_next_turn',
    '_um_boss_engine_vs_crustle',
    '_um_boss_engine_vs_untouchable',
    '_um_is_first_turn',
    '_v_ub_chikorita_arrancar',
    '_v_ub_applin_arrancar',
    '_eval_ub_best_target',
    '_ctx_ub_fetch_hydrapple',
    '_ctx_ub_fetch_meowth',
    '_AJUSTES_UB_HYDRAPPLE',
    '_RULES_UB_APPLIN',
    '_RULES_UB_BAYLEEF',
    '_RULES_UB_CHIKORITA',
    '_RULES_UB_DIPPLIN',
    '_RULES_UB_FEZ',
    '_RULES_UB_HYDRAPPLE',
    '_RULES_UB_MEGANIUM',
    '_RULES_UB_MEOWTH',
    '_RULES_UB_OGERPON',
    '_RULES_UB_PINSIR',
    '_RULES_UB_TAPU',
]
