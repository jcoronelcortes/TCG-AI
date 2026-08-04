"""Ultra Ball: the search orchestrator and its vetoes.

Extracted VERBATIM from main.py by utils/extraer_definiciones.py
(docs/project-history.md). Its purity is verified by
utils/pureza.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.motor.reglas import _Ajuste, _ReglaFija
from ptcg.cartas.ids import Applin, Bayleef, Chikorita, Dipplin, Fezandipiti_ex, Forest_of_Vitality, Hydrapple_ex, Lillie_Determination, Meganium, Meowth_ex, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.decision.estadios import _forest_disponible
from ptcg.calculo.energia import _grass_attach_unit
from ptcg.calculo.dano import _attacker_base_damage, _our_effective_damage
from ptcg.estado.agente import ESTADO
from ptcg.decision.disrupcion import _sello_merece_jugarse
from ptcg.cartas.ids import Applin, Basic_Grass_Energy, Bayleef, Boss_Orders, Chikorita, Dawn, Dipplin, Fezandipiti_ex, Forest_of_Vitality, Hydrapple_ex, Lanas_Aid, Lillie_Determination, Meganium, Meowth_ex, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Unfair_Stamp
from ptcg.calculo.tablero import _active_of
from ptcg.calculo.energia import count_total_grass_energy
from dataclasses import dataclass
from typing import NamedTuple
from ptcg.cartas.ids import Applin, Basic_Grass_Energy, Bayleef, Boss_Orders, Bug_Catching_Set, CUBCHOO_ALLOWED_PLAY_IDS, Chikorita, Dawn, Dipplin, Fezandipiti_ex, Forest_of_Vitality, Hydrapple_ex, Lanas_Aid, Lillie_Determination, Meganium, Meowth_ex, Night_Stretcher, Pinsir, SCORE_CANCEL, SCORE_VETO, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball, Unfair_Stamp, XEROSIC_SCORE_LAST_RESORT, Xerosic_Machinations
from ptcg.estado.claves import ESTADO_MAZO
from ptcg.decision.disrupcion import _score_xerosic_play
from ptcg.decision.poke_pad import _pp_es_t1


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
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo
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
         CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0) or
        (field_counts.get(Bayleef, 0) >= 1 and
         hand_counts.get(Meganium, 0) == 0 and
         CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0) or
        (field_counts.get(Applin, 0) >= 1 and
         hand_counts.get(Dipplin, 0) == 0 and
         CARTAS_ACTIVAS_EN_MAZO.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0) or
        (field_counts.get(Dipplin, 0) >= 1 and
         hand_counts.get(Hydrapple_ex, 0) == 0 and
         CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0 and
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
         CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0 and
         (forest_in_play or _field_at_turn_start.get(Chikorita, 0) >= 1)) or
        (field_counts.get(Bayleef, 0) >= 1 and
         hand_counts.get(Meganium, 0) == 0 and
         CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0 and
         (forest_in_play or _field_at_turn_start.get(Bayleef, 0) >= 1)) or
        (field_counts.get(Applin, 0) >= 1 and
         hand_counts.get(Dipplin, 0) == 0 and
         CARTAS_ACTIVAS_EN_MAZO.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0 and
         (forest_in_play or _field_at_turn_start.get(Applin, 0) >= 1)) or
        (field_counts.get(Dipplin, 0) >= 1 and
         hand_counts.get(Hydrapple_ex, 0) == 0 and
         CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0 and
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
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo
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

            _ub_has_basic_in_mazo = False
            for _surv_id in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                             Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir):
                if CARTAS_ACTIVAS_EN_MAZO.get(_surv_id, {}).get(ESTADO_MAZO, 0) > 0:
                    _ub_has_basic_in_mazo = True
                    break
            if _ub_has_basic_in_mazo:
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
            CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0 and
            CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)
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
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo

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
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo

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


def _ub_forraje_real(ctx, protegida) -> int:
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
    the other cost vetoes protecting a Supporter use the SAME arithmetic."""
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
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo

    _ub_discardable_without_lillie = 0
    for _ub_llid, _ub_llcnt in hand_counts.items():
        if _ub_llid in (Ultra_Ball, protegida, Unfair_Stamp):
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
            elif (hand_counts.get(Dipplin, 0) >= 1 and
                  (forest_in_play or
                   hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                  CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) > 0):
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
                  CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) > 0):
                _ub_ll_fodder = False
        elif _ub_llid == Meganium:
            _ub_ll_fodder = not (field_counts.get(Bayleef, 0) >= 1)
        elif _ub_llid == Bayleef:
            _ub_ll_fodder = not (field_counts.get(Chikorita, 0) >= 1)
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
            # `_ub_forraje_real(prot=Xerosic)` counted 2 (Boss's + Lillie's), so
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
    `generico_mano_muy_grande` branch (opposing hand >= 7 without an Alakazam
    across the table), where the arithmetic is the same. Measured in matchup
    self-play (400-2000 games vs the crustle / dragapult / hops bots) the effect
    outside Alakazam is neutral."""
    if ctx.hand_counts.get(Xerosic_Machinations, 0) < 1:
        return False
    if ctx.state.supporterPlayed:
        return False
    if _score_xerosic_play(ctx) <= XEROSIC_SCORE_LAST_RESORT:
        return False
    return _ub_forraje_real(ctx, Xerosic_Machinations) < 2


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

        if _ub_forraje_real(ctx, Lillie_Determination) < 2:

            _ub_cancel_for_lillie = True

    return _ub_cancel_for_lillie


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
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo

    _ub_cancel_for_meowth = False
    if (hand_counts.get(Meowth_ex, 0) >= 1 and
          field_counts.get(Meowth_ex, 0) == 0 and
          bench_count < 5 and
          not state.supporterPlayed and
          CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0):

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


def _contra_estadio_urgente(neutralization_zone_active, watchtower_in_play,
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


def _matchup_permite_bajar(cid, field_counts, op_is_comfey_deck,
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
    that is played TOMORROW (`_ub_meowth_para_manana`)."""
    return bool(budew_on_op_field or op_has_dragapult or op_has_dreepy_line)


def _ub_coste_destruye_carta_mejor(ctx) -> bool:
    """Would the Ultra Ball's COST (discarding 2) force us to throw away a card
    BETTER than what the search brings? It groups the four cost vetoes of
    phase C (`_ub_cancel_stamp` / `_ub_cancel_fez` / `_ub_cancel_lillie` /
    `_ub_cancel_meowth` / `_ub_cancel_xerosic`): they all share the same count
    (`_ub_forraje_real`) -- the cards in hand that the DISCARD scorer WOULD let
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
                or _ub_cancel_xerosic(ctx))


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
    if c.cartas_en_mazo.get(
            Xerosic_Machinations, {}).get(ESTADO_MAZO, 0) < 1:
        return False
    if c.field_counts.get(Meowth_ex, 0) >= 2 or c.bench_count >= 5:
        return False
    _meowth_in_hand = hand.get(Meowth_ex, 0) >= 1
    _meowth_diggable = (
        c.cartas_en_mazo.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) >= 1
        and hand.get(Ultra_Ball, 0) >= 1)
    return _meowth_in_hand or _meowth_diggable


def _ub_cavar_meowth_se_juega(ctx) -> bool:
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
    campo: dict           # field_counts
    evolvable: dict       # _ub_evolvable (start-of-turn snapshot)
    dipplin_evo_atk: bool         # the active Dipplin evolves AND attacks this turn
    op_ex_immune_active: bool
    op_ex_immune_bench: bool
    hydra_dead_prefer_meowth: bool  # _ub_hydra_dead_prefer_meowth


@dataclass
class _CtxUBMeowth:
    hand: dict                  # hand_counts
    campo: dict                 # field_counts
    bench_count: int
    turno: int                  # state.turn
    watchtower: bool            # watchtower_in_play (cancels Last-Ditch)
    supp_values: dict           # _supp_values
    lillie_in_mazo: int
    any_supp_in_mazo: bool
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
    # TOMORROW, under the Item lock of Itchy Pollen (see `_ub_meowth_para_manana`):
    # the fetch MUST complete that purchase even if the Last-Ditch produces nothing
    # today.
    meowth_manana: bool = False


@dataclass
class _CtxUBFetch:
    hand: dict
    campo: dict
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
    if c.campo.get(Teal_Mask_Ogerpon_ex, 0) >= 1:
        v = 200
    return v


def _v_ub_ogerpon_teal(c):
    v = 700
    if c.campo.get(Teal_Mask_Ogerpon_ex, 0) == 0:
        v = 800
    if c.hand.get(Basic_Grass_Energy, 0) >= 2:
        v += 100
    return v


def _v_ub_chikorita_t1(c):
    v = 850
    if (c.campo.get(Applin, 0) >= 1
            or c.campo.get(Teal_Mask_Ogerpon_ex, 0) >= 1):
        v = 900
    elif c.campo.get(Chikorita, 0) >= 1:
        v = 200
    if c.hand.get(Bayleef, 0) >= 1:
        v += 50
    return v


def _v_ub_applin_t1(c):
    v = 800
    if (c.campo.get(Chikorita, 0) >= 1
            or c.campo.get(Teal_Mask_Ogerpon_ex, 0) >= 1):
        v = 850
    elif c.campo.get(Applin, 0) >= 1:
        v = 180
    if c.hand.get(Dipplin, 0) >= 1:
        v += 50
    return v


def _eval_ub_best_target(field_counts, hand_counts, meganium_in_play, has_hydrapple,
                         forest_in_play, op_has_ex_immune_active, op_has_ex_immune_bench,
                         op_prize, bench_count, state, ko_last_turn,
                         _best_supp_in_mazo_val, supporters_in_hand, hand_is_weak,
                         has_energy_for_teal, _we_go_first=False,
                         _best_supp_in_hand_val=0,
                         op_is_crustle_deck=False, op_is_cornerstone_deck=False,
                         op_active_is_budew=False, meowth_ability_lock=False,
                         op_hand_count=None):
    ub_best_target = 0

    _bench_full = (bench_count >= 5)

    _hand_total = sum(hand_counts.values())

    if state.turn == 2 and not _we_go_first:

        if (not state.supporterPlayed and
                hand_counts.get(Lillie_Determination, 0) == 0 and
                field_counts.get(Meowth_ex, 0) < 2 and
                bench_count < 5 and
                not meowth_ability_lock and
                ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0):
            _lillie_in_mazo = ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0)
            if _lillie_in_mazo > 0:
                ub_best_target = max(ub_best_target, 1100)
            elif any(ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(sid, {}).get(ESTADO_MAZO, 0) > 0
                     for sid in (Dawn, Lanas_Aid)):
                ub_best_target = max(ub_best_target, 950)

        if bench_count == 0:
            _has_basic_in_hand_t1s = any(hand_counts.get(pid, 0) >= 1
                                         for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                                     Tapu_Bulu, Meowth_ex, Fezandipiti_ex,
                                                     Pinsir))
            _active_is_weak_basic = any(field_counts.get(pid, 0) >= 1
                                        for pid in (Applin, Chikorita))
            if not _has_basic_in_hand_t1s and _active_is_weak_basic:
                if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0:
                    ub_best_target = max(ub_best_target, 1050)

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
                ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0 and
                ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0):
            return 1100

        _has_basic_in_hand = any(hand_counts.get(pid, 0) >= 1
                                 for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                             Tapu_Bulu, Fezandipiti_ex, Pinsir))
        if bench_count >= 1 or _has_basic_in_hand:
            return 0

        _best_t1_val = 0

        if (field_counts.get(Teal_Mask_Ogerpon_ex, 0) == 0 and
                ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0):
            _val = 950
            if hand_counts.get(Basic_Grass_Energy, 0) >= 1:
                _val = 1000
            _best_t1_val = max(_best_t1_val, _val)

        if (field_counts.get(Chikorita, 0) == 0 and
                ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Chikorita, {}).get(ESTADO_MAZO, 0) > 0):
            _val = 850
            if field_counts.get(Applin, 0) >= 1 or field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1:
                _val = 900
            if hand_counts.get(Bayleef, 0) >= 1:
                _val += 50
            _best_t1_val = max(_best_t1_val, _val)

        if (field_counts.get(Applin, 0) == 0 and
                ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) > 0):
            _val = 800
            if field_counts.get(Chikorita, 0) >= 1 or field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1:
                _val = 850
            if hand_counts.get(Dipplin, 0) >= 1:
                _val += 50
            _best_t1_val = max(_best_t1_val, _val)

        ub_best_target = max(ub_best_target, _best_t1_val)
        return ub_best_target

    # The Stamp only blocks the Supporter chain if it is really going to be played
    # (a card rule: `_sello_merece_jugarse`). Without `op_hand_count` the gate
    # falls back to the previous behaviour.
    _stamp_blocks_supp_chain = (ko_last_turn
                                and hand_counts.get(Unfair_Stamp, 0) >= 1
                                and _sello_merece_jugarse(op_hand_count,
                                                          _hand_total))

    _supp_in_hand_is_inferior = False
    if supporters_in_hand >= 1 and _best_supp_in_mazo_val >= 600:

        if _best_supp_in_mazo_val > _best_supp_in_hand_val + 100:
            _supp_in_hand_is_inferior = True

    meowth_viable = (
        not _stamp_blocks_supp_chain and
        not (state.turn <= 1 and _we_go_first) and
        not state.supporterPlayed and
        not meowth_ability_lock and
        (supporters_in_hand == 0 or _supp_in_hand_is_inferior) and
        field_counts.get(Meowth_ex, 0) == 0 and
        bench_count < 5 and
        ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0 and
        _best_supp_in_mazo_val > 200
    )

    if not meowth_viable and op_is_crustle_deck:
        _boss_in_mazo = ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Boss_Orders, {}).get(ESTADO_MAZO, 0) > 0
        _boss_val_ub = _best_supp_in_mazo_val
        if (_boss_in_mazo and _boss_val_ub >= 900 and
                not state.supporterPlayed and
                not meowth_ability_lock and
                field_counts.get(Meowth_ex, 0) == 0 and
                bench_count < 5 and
                hand_counts.get(Boss_Orders, 0) == 0 and
                ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0):
            meowth_viable = True
    if meowth_viable:
        meowth_val = _best_supp_in_mazo_val
        if state.turn <= 2:
            meowth_val += 200
        elif hand_is_weak:
            meowth_val += 100
        ub_best_target = max(ub_best_target, meowth_val)

    if has_energy_for_teal and field_counts.get(Teal_Mask_Ogerpon_ex, 0) < 2 and bench_count < 5:
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0:
            val = 650
            if field_counts.get(Teal_Mask_Ogerpon_ex, 0) == 0:
                val = 750
            if hand_counts.get(Basic_Grass_Energy, 0) >= 2:
                val += 100
            ub_best_target = max(ub_best_target, val)

    if (has_energy_for_teal and
            field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2 and
            bench_count < 5 and
            field_counts.get(Hydrapple_ex, 0) >= 1):
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0:

            _td_dmg_bonus = 60 if meganium_in_play else 30
            val = 500 + _td_dmg_bonus * 2

            if hand_counts.get(Basic_Grass_Energy, 0) >= 2:
                val += 150

            if field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2:
                val += 50
            ub_best_target = max(ub_best_target, val)

    # It does NOT use `_evolvable_counts` (the cleaned-up snapshot): MEASURED AND
    # REVERTED. See the scope note in `_evolvable_counts`.
    _evolvable = ESTADO._field_at_turn_start if (not forest_in_play and ESTADO._field_at_turn_start) else field_counts

    if not meganium_in_play:
        if _evolvable.get(Bayleef, 0) >= 1:
            # Same criterion as the Bayleef / Dipplin branches below (and as
            # `_ub_evolve_needs_search`): if the evolution is ALREADY in hand, the
            # line evolves WITHOUT Ultra Ball and searching for a 2nd copy adds
            # nothing -- it only burns the card and 2 discards (user, registro_004 step
            # 35 vs Cynthia's Garchomp: Meganium in hand and it dug for it anyway).
            if (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0
                    and hand_counts.get(Meganium, 0) == 0):
                ub_best_target = max(ub_best_target, 1000)
        elif _evolvable.get(Chikorita, 0) >= 1 and field_counts.get(Bayleef, 0) >= 1:

            if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0:
                if forest_in_play:

                    ub_best_target = max(ub_best_target, 1000)
                else:
                    # A Bayleef just evolved THIS turn (there was a Chikorita at the
                    # start of the turn) and WITHOUT Forest: it will not be able to evolve
                    # into Meganium until the NEXT turn. Searching for Meganium now is only
                    # preparation, it adds nothing this turn, so the priority is lowered so
                    # as not to spend an Ultra Ball + 2 discards on an unusable piece if
                    # there are better targets or few safe discards (with >=2 safe discards
                    # and no better target it is still searched for).
                    ub_best_target = max(ub_best_target, 280)
        elif _evolvable.get(Chikorita, 0) >= 1:

            if (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0
                    and hand_counts.get(Bayleef, 0) == 0):
                # It is only worth searching for a Bayleef if we do not already have one
                # in hand: with a Chikorita in play, a single Bayleef is enough to
                # evolve it. If we already have it, the Ultra Ball adds nothing for
                # this line (and would spend 2 discarded cards on a duplicate).
                ub_best_target = max(ub_best_target, 850)

            elif (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0 and
                  (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                  hand_counts.get(Bayleef, 0) >= 1):
                _prot = 1
                if not forest_in_play:
                    _prot += 1
                if _hand_total - 1 - _prot >= 2:
                    ub_best_target = max(ub_best_target, 900)

        elif not _bench_full and field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) == 0:
            if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Chikorita, {}).get(ESTADO_MAZO, 0) > 0:
                _has_mega_evo_in_mazo = (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0 or
                                         ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0)
                _has_mega_evo_in_hand = (hand_counts.get(Bayleef, 0) >= 1 or hand_counts.get(Meganium, 0) >= 1)
                _forest_available = (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1)

                _can_chain_mega = False
                if _forest_available and hand_counts.get(Bayleef, 0) >= 1:
                    _prot = 1
                    if not forest_in_play:
                        _prot += 1
                    if _hand_total - 1 - _prot >= 2:
                        _can_chain_mega = True
                        ub_best_target = max(ub_best_target, 700)
                if not _can_chain_mega:
                    if _has_mega_evo_in_mazo or _has_mega_evo_in_hand:
                        ub_best_target = max(ub_best_target, 500)
                    else:
                        ub_best_target = max(ub_best_target, 200)

    if not has_hydrapple:
        if _evolvable.get(Dipplin, 0) >= 1:
            # With the Hydrapple ex ALREADY in hand the line evolves without Ultra
            # Ball (see the twin Meganium branch above).
            if (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                    Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0
                    and hand_counts.get(Hydrapple_ex, 0) == 0):
                ub_best_target = max(ub_best_target, 950)
        elif _evolvable.get(Applin, 0) >= 1 and field_counts.get(Dipplin, 0) >= 1:

            if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0:
                if forest_in_play:
                    ub_best_target = max(ub_best_target, 950)
                else:
                    # A Dipplin just evolved THIS turn (there was an Applin at the start
                    # of the turn) and WITHOUT Forest: it will not be able to evolve into
                    # Hydrapple ex until the NEXT turn. Searching for Hydrapple now is only
                    # preparation; the priority is lowered so as not to spend an Ultra Ball +
                    # 2 discards on an unusable piece if there are better targets or few safe
                    # discards (with >=2 safe discards and no better target it is still
                    # searched for).
                    ub_best_target = max(ub_best_target, 280)
        elif _evolvable.get(Applin, 0) >= 1:

            if (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0
                    and hand_counts.get(Dipplin, 0) == 0):
                # Same criterion as Bayleef: do not search for a Dipplin if there is
                # already one in hand (a single Dipplin is enough to evolve the only Applin).
                ub_best_target = max(ub_best_target, 800)

            elif (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0 and
                  (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                  hand_counts.get(Dipplin, 0) >= 1):
                _prot = 1
                if not forest_in_play:
                    _prot += 1
                if _hand_total - 1 - _prot >= 2:
                    ub_best_target = max(ub_best_target, 850)
        elif not _bench_full and field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) == 0:
            if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) > 0:
                _has_hydra_evo_in_mazo = (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0 or
                                           ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0)
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

                            ub_best_target = max(ub_best_target, 950)
                        else:

                            ub_best_target = max(ub_best_target, 600)
                if not _can_chain_hydra:
                    if _has_hydra_evo_in_mazo or _has_hydra_evo_in_hand:
                        ub_best_target = max(ub_best_target, 450)
                    else:
                        ub_best_target = max(ub_best_target, 180)

    if not _bench_full and not has_energy_for_teal and field_counts.get(Teal_Mask_Ogerpon_ex, 0) < 2:
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0:
            if field_counts.get(Teal_Mask_Ogerpon_ex, 0) == 0 and bench_count <= 2:
                ub_best_target = max(ub_best_target, 350)

    if not _bench_full and field_counts.get(Tapu_Bulu, 0) == 0:
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Tapu_Bulu, {}).get(ESTADO_MAZO, 0) > 0:
            if meganium_in_play and (op_has_ex_immune_active or op_has_ex_immune_bench):
                val = 750
                if has_hydrapple:
                    val = 850
                ub_best_target = max(ub_best_target, val)

    if not _bench_full and field_counts.get(Pinsir, 0) == 0:
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Pinsir, {}).get(ESTADO_MAZO, 0) > 0:
            if op_is_crustle_deck or op_is_cornerstone_deck:
                val = 900
                if meganium_in_play:
                    val = 950
                ub_best_target = max(ub_best_target, val)

    if (not _bench_full and not _stamp_blocks_supp_chain and
            not hand_is_weak and not state.supporterPlayed and
            field_counts.get(Meowth_ex, 0) == 0 and supporters_in_hand == 0 and
            _best_supp_in_mazo_val >= 500):
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0:
            if state.turn <= 4:
                ub_best_target = max(ub_best_target, min(_best_supp_in_mazo_val, 500))

    if not _bench_full and field_counts.get(Fezandipiti_ex, 0) == 0:
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Fezandipiti_ex, {}).get(ESTADO_MAZO, 0) > 0:
            if ko_last_turn:
                ub_best_target = max(ub_best_target, 1050)

    return ub_best_target


def _ub_engine_refresh_pivot(ctx) -> bool:
    """The UB -> Meowth -> Lillie's engine BEFORE spending the energies in hand
    (user, registro_008 steps 58-61 vs Archaludon ex, LOST): with the active
    Hydrapple ex unable to KNOCK OUT the opponent, the bench underdeveloped
    (<=1) and the hand holding 2+ energies (cheap fodder for the Ultra Ball's
    discard), the agent attached an energy and used Ripening Charge with the
    other -- the hand was left at [UB, Boss's] and the Ultra Ball DIED (with no
    2 cards to discard). The correct line: play the UB NOW (discarding the 2
    energies), search for Meowth ex, put it down (Last-Ditch -> Lillie's) and
    refill: the new hand develops the bench, and Syrup Storm scales with the
    TOTAL Grass on the field. The turn's attachment is still available AFTER
    the refill."""
    state = ctx.state
    if state.supporterPlayed:
        return False
    hand_counts = ctx.hand_counts
    # Cheap fodder: the UB's discard eats the 2 energies, not the Boss's.
    if hand_counts.get(Basic_Grass_Energy, 0) < 2:
        return False
    # With Lillie's or Meowth ALREADY in hand the engine does not need the UB now.
    if (hand_counts.get(Lillie_Determination, 0) >= 1
            or hand_counts.get(Meowth_ex, 0) >= 1):
        return False
    # An underdeveloped bench: the whole reason for the refill (growing the field).
    if ctx.bench_count > 1:
        return False
    cartas = ctx.cartas_en_mazo
    if cartas.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) <= 0:
        return False
    if cartas.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) <= 0:
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


def _ctx_ub_fetch_hydrapple(my_state, state, hand_counts, field_counts,
                            ub_evolvable, op_ex_immune_active,
                            op_ex_immune_bench, hydra_dead_prefer_meowth):
    # If the active is a Dipplin that can evolve into Hydrapple ex and
    # attack this turn (Syrup Storm requires 2 effective energy).
    activo = my_state.active[0] if my_state.active else None
    evo_atk = False
    if (activo is not None
            and activo.id == Dipplin
            and ub_evolvable.get(Dipplin, 0) >= 1):
        e_ahora = len(activo.energies)
        puede_adjuntar = (not state.energyAttached
                          and hand_counts.get(Basic_Grass_Energy, 0) >= 1)
        e_despues = e_ahora + _grass_attach_unit()
        req = ESTADO.ATTACK_ENERGY_REQ.get(Hydrapple_ex, 2)
        if e_ahora >= req or (puede_adjuntar and e_despues >= req):
            evo_atk = True
    return _CtxUBHydrapple(
        hand=hand_counts, campo=field_counts, evolvable=ub_evolvable,
        dipplin_evo_atk=evo_atk,
        op_ex_immune_active=op_ex_immune_active,
        op_ex_immune_bench=op_ex_immune_bench,
        hydra_dead_prefer_meowth=hydra_dead_prefer_meowth)


def _uh_preparar_hydra_prox_turno(c):
    """With Dipplin already in play, Hydrapple ex is ONE single evolution away:
    it is worth bringing even if it cannot be evolved this very turn if
    (A) Dipplin is the ONLY Grass Pokemon in play, or (B) the Meganium line
    would develop but canNOT evolve into Meganium this turn. EXCEPT if it is
    better to search for a Bayleef usable NOW (an evolvable Chikorita, no
    Bayleef in hand, with a Bayleef in the deck)."""
    grass_ids = (Applin, Dipplin, Hydrapple_ex, Chikorita, Bayleef,
                 Meganium, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Pinsir)
    grass_en_juego = sum(c.campo.get(pid, 0) for pid in grass_ids)
    dipplin_unico_grass = (grass_en_juego == c.campo.get(Dipplin, 0))

    puede_evo_meganium_ya = (
        not ESTADO.meganium_in_play and (
            c.evolvable.get(Bayleef, 0) >= 1
            or (c.evolvable.get(Chikorita, 0) >= 1
                and (ESTADO.forest_in_play
                     or c.hand.get(Forest_of_Vitality, 0) >= 1)
                and c.hand.get(Bayleef, 0) >= 1)))
    linea_meganium_dev = (
        not ESTADO.meganium_in_play and (
            c.hand.get(Bayleef, 0) >= 1
            or c.hand.get(Meganium, 0) >= 1
            or ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0
            or ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0))
    buscar_bayleef_ya = (
        not ESTADO.meganium_in_play
        and c.evolvable.get(Chikorita, 0) >= 1
        and c.hand.get(Bayleef, 0) == 0
        and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0)

    return (dipplin_unico_grass
            or (linea_meganium_dev
                and not puede_evo_meganium_ya
                and not buscar_bayleef_ya))


def _ctx_ub_fetch_meowth(hand_counts, field_counts, bench_count, turno,
                         watchtower, supp_values, prefer_meowth_develop,
                         hydra_dead_prefer_meowth, mega_dead_prefer_meowth,
                         no_attacker_prefer_meowth, t1_going_second_meowth,
                         dipplin_priority, active_cant_attack,
                         mega_line_active, dragapult,
                         supporter_played=False, ld_free=True,
                         meowth_manana=False):
    return _CtxUBMeowth(
        hand=hand_counts, campo=field_counts, bench_count=bench_count,
        turno=turno, watchtower=watchtower, supp_values=supp_values,
        lillie_in_mazo=ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
            Lillie_Determination, {}).get(ESTADO_MAZO, 0),
        any_supp_in_mazo=any(
            ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(sid, {}).get(ESTADO_MAZO, 0) > 0
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
        meowth_manana=meowth_manana)


def _um_boss_engine_vs_crustle(c):
    """vs Crustle, Meowth ex is used to bring Boss's Orders (a gust) via
    Last-Ditch: with no Boss's in hand, with copies in the deck and with a
    valuable projected gust (_supp_values)."""
    return (ESTADO.op_is_crustle_deck
            and c.hand.get(Boss_Orders, 0) == 0
            and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                Boss_Orders, {}).get(ESTADO_MAZO, 0) > 0
            and c.supp_values.get(Boss_Orders, 0) >= 900)


def _um_es_primer_turno(c):
    """OUR first turn of play (turn 1 going first, turn 2 going second)."""
    return ((c.turno == 1 and ESTADO.we_go_first)
            or (c.turno == 2 and not ESTADO.we_go_first))


def _v_ub_chikorita_arrancar(c):
    if _forest_disponible(c) and c.hand.get(Bayleef, 0) >= 1:
        return 880
    if (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0
            or ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0
            or c.hand.get(Bayleef, 0) >= 1):
        return 700
    return 200


def _v_ub_applin_arrancar(c):
    if _forest_disponible(c) and c.hand.get(Dipplin, 0) >= 1:
        return 980 if c.hand.get(Hydrapple_ex, 0) >= 1 else 800
    if (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0
            or ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0
            or c.hand.get(Dipplin, 0) >= 1):
        return 650
    return 180


_REGLAS_UB_HYDRAPPLE = [
    # Evolving the active Dipplin AND attacking this turn is worth more than the
    # Fezandipiti refill (1050): the fetch's top priority.
    _ReglaFija("dipplin_evo_ataca",
               lambda c: c.dipplin_evo_atk,
               lambda c: 1200),
    _ReglaFija("dipplin_evolucionable",
               lambda c: c.evolvable.get(Dipplin, 0) >= 1,
               lambda c: 980),
    _ReglaFija("applin_evolucionable_full_linea",
               lambda c: (c.evolvable.get(Applin, 0) >= 1
                          and (ESTADO.forest_in_play
                               or c.hand.get(Forest_of_Vitality, 0) >= 1)
                          and c.hand.get(Dipplin, 0) >= 1),
               lambda c: 900),
    _ReglaFija("applin_evolucionable",
               lambda c: c.evolvable.get(Applin, 0) >= 1,
               lambda c: 180),
    _ReglaFija("applin_en_campo",
               lambda c: c.campo.get(Applin, 0) >= 1,
               lambda c: 130),
]


_AJUSTES_UB_HYDRAPPLE = [
    _Ajuste("preparar_hydra_prox_turno",
            lambda c, s: (c.campo.get(Dipplin, 0) >= 1 and s < 860
                          and _uh_preparar_hydra_prox_turno(c)),
            lambda c, s: 860),
    # Against decks with EX IMMUNITY (e.g. Crustle), Hydrapple ex is an ex
    # attacker that cannot damage them: a dead card, it yields to the Meganium
    # line or the non-ex attackers. EXCEPTION `evo_doomed_hittable`: if it
    # evolves the doomed active Dipplin and the opposing active is NOT
    # immune (Kangaskhan ex), the clamp does not apply (an evolution and
    # survival pivot: 80 HP -> 330 HP).
    _Ajuste("clamp_ex_muerto_vs_crustle",
            lambda c, s: (not (c.dipplin_evo_atk
                               and not c.op_ex_immune_active)
                          and (ESTADO.op_is_crustle_deck
                               or c.op_ex_immune_active
                               or c.op_ex_immune_bench)),
            lambda c, s: min(s, 40)),
    # Hydrapple ex would be dead this turn (it does not attack) and the
    # Meowth ex -> Lillie's refill engine is available: it yields the search to
    # Meowth ex (1000), which rebuilds the hand.
    _Ajuste("cede_a_meowth_refresco",
            lambda c, s: c.hydra_dead_prefer_meowth,
            lambda c, s: min(s, 150)),
]


_REGLAS_UB_MEOWTH = [
    # FIRST TURN: the Ultra Ball only digs for Meowth ex to bring Lillie's
    # Determination (user, log 88461779 vs Alakazam, LOST). If the Lillie's
    # is ALREADY in hand there is nothing to search for (and the veto on playing
    # the Meowth would leave it dead in hand); if there is NONE left in the deck,
    # the Last-Ditch fetch would not bring the refill that justifies the cost. In
    # both cases the Ultra Ball searches for something else (an evolution line, an
    # attacker). It goes FIRST: neither the pivot engine nor the Boss's vs Crustle
    # engine lifts this rule on the first turn.
    _ReglaFija("primer_turno_solo_para_lillie",
               lambda c: (_um_es_primer_turno(c)
                          and (c.hand.get(Lillie_Determination, 0) >= 1
                               or c.lillie_in_mazo <= 0)),
               lambda c: 10),
    # Team Rocket's Watchtower cancels Meowth ex's ability (a Colorless
    # Pokemon): do not search for it with the Ultra Ball.
    _ReglaFija("watchtower_anula_habilidad",
               lambda c: c.watchtower,
               lambda c: 10),
    # ITEM LOCK TOMORROW: the Ultra Ball was played EXACTLY to dig out this
    # body (`_ub_meowth_para_manana`, registro_002 step 17 vs Dragapult), so
    # the fetch has to complete the purchase. It goes ABOVE
    # `last_ditch_no_produce`: it is true that the ability produces nothing today --
    # that is the point, the Meowth ex is put down TOMORROW, when there will be no
    # Items left to search for it and the Supporter slot is free again.
    _ReglaFija("bloqueo_de_items_manana",
               lambda c: c.meowth_manana,
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
    #      `_ub_cavar_meowth_se_juega`).
    # On that turn 6 we had played Lillie's and the Ultra Ball still brought
    # a Meowth ex (1000, beating Chikorita/Meganium/Bayleef); the agent chained
    # a SECOND Ultra Ball to dig out the other Meowth ex and ended up attacking
    # anyway, 4 cards of hand (Forest, Xerosic, Dipplin, Lana's) for two dead
    # bodies. It goes with the "the ability does not work" vetoes (Watchtower) and
    # above the pivot engines, which in any case require a free Supporter
    # (`_ub_engine_refresh_pivot` / `_alakazam_dig_xerosic_engine`).
    _ReglaFija("last_ditch_no_produce",
               lambda c: c.supporter_played or not c.ld_free,
               lambda c: 10),
    # With Lillie's ALREADY in hand the Meowth ex fetch is redundant (its only
    # purpose is to search for Lillie's); a useful evolution is better. EXCEPTION:
    # vs Crustle, Meowth ex brings Boss's Orders (a gust), not a refill. (user,
    # log 86339167 step 23, LOST vs Mega Starmie)
    _ReglaFija("lillie_ya_en_mano_redundante",
               lambda c: (c.hand.get(Lillie_Determination, 0) >= 1
                          and not _um_boss_engine_vs_crustle(c)
                          and not ESTADO._ub_engine_pivot_turn),
               lambda c: 10),
    # UB->Meowth->Lillie's engine (registro_008 step 58 vs Archaludon,
    # LOST): the Ultra Ball was played FOR the pivot; the fetch MUST
    # complete the chain. Above development (1000-1250) and evolutions.
    _ReglaFija("engine_pivot_turn",
               lambda c: ESTADO._ub_engine_pivot_turn,
               lambda c: 1300),
    # The only Pokemon in play + no playable Basic + no Lillie's in hand:
    # put Meowth down, search for Lillie's and refill.
    _ReglaFija("develop_unico_pokemon",
               lambda c: c.prefer_meowth_develop,
               lambda c: 1250),
    # The only big evolution (Hydrapple ex on top of Dipplin) would be
    # dead this turn: refilling with Meowth/Lillie's opens more options.
    _ReglaFija("hydra_muerto_prefiere_meowth",
               lambda c: c.hydra_dead_prefer_meowth,
               lambda c: 1000),
    # The Meganium line adds nothing this turn and there is no ready attacker.
    _ReglaFija("meganium_muerto_prefiere_meowth",
               lambda c: c.mega_dead_prefer_meowth,
               lambda c: 1000),
    # With no USABLE attacker this turn (neither an active that attacks nor a
    # promotable benched one): the refill beats an evolution without an attack.
    # >1000 to beat a playable Meganium. (registro_004 step 29 vs Mega Starmie)
    _ReglaFija("sin_atacante_prefiere_meowth",
               lambda c: c.no_attacker_prefer_meowth,
               lambda c: 1250),
    _ReglaFija("t1_saliendo_segundos",
               lambda c: c.t1_going_second_meowth,
               lambda c: 1200),
    _ReglaFija("t1_saliendo_primeros_no",
               lambda c: c.turno == 1 and ESTADO.we_go_first,
               lambda c: 10),
    _ReglaFija("ya_dos_meowth_en_juego",
               lambda c: c.campo.get(Meowth_ex, 0) >= 2,
               lambda c: 10),
    _ReglaFija("un_meowth_y_activo_ataca",
               lambda c: (c.campo.get(Meowth_ex, 0) >= 1
                          and not c.active_cant_attack),
               lambda c: 10),
    _ReglaFija("banca_llena",
               lambda c: c.bench_count >= 5,
               lambda c: 10),
    # A condition that favours Dipplin holds: Meowth yields.
    _ReglaFija("cede_a_dipplin_prioritario",
               lambda c: c.dipplin_priority,
               lambda c: 10),
    _ReglaFija("linea_mega_activa_con_lillie",
               lambda c: c.mega_line_active and c.lillie_in_mazo > 0,
               lambda c: 1150),
    _ReglaFija("vs_dragapult_con_lillie",
               lambda c: c.dragapult and c.lillie_in_mazo > 0,
               lambda c: 985),
    _ReglaFija("motor_boss_vs_crustle",
               _um_boss_engine_vs_crustle,
               lambda c: 1100),
    # No condition favouring Dipplin: Meowth ex has PRIORITY to refill
    # (searching for Lillie's), regardless of the hand.
    _ReglaFija("lillie_en_mazo_refresco",
               lambda c: c.lillie_in_mazo > 0,
               lambda c: 1000),
    # Another supporter in the deck: refill anyway.
    _ReglaFija("otro_supporter_en_mazo",
               lambda c: c.any_supp_in_mazo,
               lambda c: 850),
]


_REGLAS_UB_OGERPON = [
    # It yields the search to Meowth ex (hand refill): Ogerpon ex would only
    # be brought here if we ALREADY had a Lillie's in hand.
    _ReglaFija("cede_a_meowth_develop",
               lambda c: c.prefer_meowth_develop,
               lambda c: 200),
    _ReglaFija("t1_segundos_necesita_ogerpon",
               lambda c: c.t1_going_second_need_ogerpon,
               lambda c: 1050),
    _ReglaFija("t1_primeros_necesita_basico",
               lambda c: c.t1_going_first_need_basic,
               _v_ub_ogerpon_t1_primeros),
    _ReglaFija("ya_dos_ogerpon",
               lambda c: c.campo.get(Teal_Mask_Ogerpon_ex, 0) >= 2,
               lambda c: 350 if (c.has_energy_for_teal
                                 and c.bench_count < 5) else 15),
    _ReglaFija("energia_para_teal_dance",
               lambda c: c.has_energy_for_teal and c.bench_count < 5,
               _v_ub_ogerpon_teal),
    _ReglaFija("primer_ogerpon_banca_corta",
               lambda c: (c.campo.get(Teal_Mask_Ogerpon_ex, 0) == 0
                          and c.bench_count <= 2),
               lambda c: 300),
]


_REGLAS_UB_MEGANIUM = [
    _ReglaFija("meganium_ya_en_juego",
               lambda c: ESTADO.meganium_in_play,
               lambda c: 25),
    # vs Cornerstone: Wild Growth doubles every Grass and lowers the cost of
    # Tapu Bulu -- the ONLY attacker that damages Cornerstone -- from 4 physical
    # Grass to 2. With the line already started in play, completing it is the
    # priority search even though Meganium itself cannot damage it.
    _ReglaFija("linea_mega_habilita_tapu_vs_cornerstone",
               lambda c: (ESTADO.op_is_cornerstone_deck
                          and (c.campo.get(Chikorita, 0) >= 1
                               or c.campo.get(Bayleef, 0) >= 1)),
               lambda c: 1050),
    _ReglaFija("bayleef_evolucionable",
               lambda c: c.evolvable.get(Bayleef, 0) >= 1,
               lambda c: 1000),
    _ReglaFija("cadena_chikorita_completa",
               lambda c: (c.evolvable.get(Chikorita, 0) >= 1
                          and _forest_disponible(c)
                          and c.hand.get(Bayleef, 0) >= 1),
               lambda c: 950),
    _ReglaFija("chikorita_evolucionable",
               lambda c: c.evolvable.get(Chikorita, 0) >= 1,
               lambda c: 200),
    _ReglaFija("chikorita_en_campo",
               lambda c: c.campo.get(Chikorita, 0) >= 1,
               lambda c: 150),
]


_REGLAS_UB_BAYLEEF = [
    _ReglaFija("meganium_ya_en_juego",
               lambda c: ESTADO.meganium_in_play,
               lambda c: 20),
    _ReglaFija("bayleef_ya_en_campo",
               lambda c: c.campo.get(Bayleef, 0) >= 1,
               lambda c: 20),
    # There is already a Bayleef IN HAND: searching for another is redundant (one
    # is enough for the only Chikorita); do not waste the UB or its discard.
    _ReglaFija("bayleef_ya_en_mano",
               lambda c: c.hand.get(Bayleef, 0) >= 1,
               lambda c: 20),
    # vs Cornerstone, Bayleef is the intermediate step towards Meganium (which
    # doubles the Grass and leaves Tapu Bulu attacking with 2 physical) and it is
    # also one of the two bodies WITHOUT an ability that do damage it.
    _ReglaFija("linea_mega_vs_cornerstone",
               lambda c: (ESTADO.op_is_cornerstone_deck
                          and c.campo.get(Chikorita, 0) >= 1),
               lambda c: 1000),
    _ReglaFija("chikorita_evolucionable",
               lambda c: c.evolvable.get(Chikorita, 0) >= 1,
               lambda c: 950 if (c.hand.get(Meganium, 0) >= 1
                                 and ESTADO.forest_in_play) else 850),
    _ReglaFija("chikorita_en_campo",
               lambda c: c.campo.get(Chikorita, 0) >= 1,
               lambda c: 200),
]


_REGLAS_UB_DIPPLIN = [
    _ReglaFija("hydrapple_ya_en_juego",
               lambda c: c.has_hydrapple,
               lambda c: 20),
    _ReglaFija("dipplin_ya_en_campo",
               lambda c: c.campo.get(Dipplin, 0) >= 1,
               lambda c: 20),
    # Same criterion as Bayleef: a redundant duplicate.
    _ReglaFija("dipplin_ya_en_mano",
               lambda c: c.hand.get(Dipplin, 0) >= 1,
               lambda c: 20),
    # Dipplin is only favoured with _dipplin_priority; otherwise Meowth ex
    # refills better and Dipplin drops so as not to steal its search.
    _ReglaFija("applin_evolucionable",
               lambda c: c.evolvable.get(Applin, 0) >= 1,
               lambda c: ((920 if (c.hand.get(Hydrapple_ex, 0) >= 1
                                   and ESTADO.forest_in_play) else 800)
                          if c.dipplin_priority else 150)),
    _ReglaFija("applin_en_campo",
               lambda c: c.campo.get(Applin, 0) >= 1,
               lambda c: 200),
    _ReglaFija("rival_anti_ex",
               lambda c: c.op_ex_immune_active or c.op_ex_immune_bench,
               lambda c: 600 if c.evolvable.get(Applin, 0) >= 1 else 150),
]


_REGLAS_UB_CHIKORITA = [
    _ReglaFija("t1_primeros_necesita_basico",
               lambda c: c.t1_going_first_need_basic,
               _v_ub_chikorita_t1),
    _ReglaFija("meganium_ya_en_juego",
               lambda c: ESTADO.meganium_in_play,
               lambda c: 30),
    _ReglaFija("linea_meganium_ya_iniciada",
               lambda c: (c.campo.get(Chikorita, 0)
                          + c.campo.get(Bayleef, 0)
                          + c.campo.get(Meganium, 0)) > 0,
               lambda c: 150),
    _ReglaFija("arrancar_linea_meganium",
               lambda c: True,
               _v_ub_chikorita_arrancar),
]


_REGLAS_UB_APPLIN = [
    _ReglaFija("t1_primeros_necesita_basico",
               lambda c: c.t1_going_first_need_basic,
               _v_ub_applin_t1),
    _ReglaFija("hydrapple_ya_en_juego",
               lambda c: c.has_hydrapple,
               lambda c: 25),
    _ReglaFija("linea_hydra_ya_iniciada",
               lambda c: (c.campo.get(Applin, 0)
                          + c.campo.get(Dipplin, 0)
                          + c.campo.get(Hydrapple_ex, 0)) > 0,
               lambda c: 120),
    _ReglaFija("arrancar_linea_hydra",
               lambda c: True,
               _v_ub_applin_arrancar),
]


_REGLAS_UB_TAPU = [
    _ReglaFija("tapu_ya_en_campo",
               lambda c: c.campo.get(Tapu_Bulu, 0) >= 1,
               lambda c: 15),
    # A non-ex attacker against ex-immune opponents, with Meganium doubling
    # its energy; better still if Hydrapple ex already covers the ex role.
    _ReglaFija("anti_ex_con_meganium",
               lambda c: (ESTADO.meganium_in_play
                          and (c.op_ex_immune_active
                               or c.op_ex_immune_bench)),
               lambda c: 850 if c.has_hydrapple else 750),
]


_REGLAS_UB_PINSIR = [
    _ReglaFija("anti_ex",
               lambda c: (c.campo.get(Pinsir, 0) == 0
                          and (ESTADO.op_is_crustle_deck
                               or ESTADO.op_is_cornerstone_deck)),
               lambda c: 900),
]


_REGLAS_UB_FEZ = [
    # Refill after a KO with Flip the Script (a benched Fezandipiti ex draws 3 when
    # we are knocked out). It is a good search IF we already have a usable attacker
    # or if the Meowth ex -> Last-Ditch -> Lillie's engine is NOT available. But if
    # there is NO usable attacker and Meowth ex + Lillie's are STILL in the deck (an
    # intact refill engine, `no_attacker_prefer_meowth`), it is better to bring
    # Meowth ex: putting it down searches for Lillie's and rebuilds the WHOLE hand
    # (up to 8 cards), opening many more options than Fezandipiti's 3-card draw
    # (user). Fez yields and its branch falls back to the default (10); Meowth ex
    # (`sin_atacante_prefiere_meowth`=1250 or other refill branches) wins the
    # search. Deck-agnostic.
    _ReglaFija("refill_tras_ko",
               lambda c: (c.campo.get(Fezandipiti_ex, 0) == 0
                          and ESTADO.ko_last_turn and c.bench_count < 5
                          and not c.no_attacker_prefer_meowth),
               lambda c: 1050),
]

__all__ = [
    '_UBFlags',
    '_ub_derive_flags',
    '_ub_terminal_overrides',
    '_ub_cancel_stamp',
    '_ub_cancel_fez',
    '_ub_forraje_real',
    '_ub_cancel_xerosic',
    '_ub_cancel_lillie',
    '_ub_cancel_meowth',
    '_contra_estadio_urgente',
    '_matchup_permite_bajar',
    '_bloqueo_de_items_inminente',
    '_ub_coste_destruye_carta_mejor',
    '_alakazam_dig_xerosic_engine',
    '_ub_cavar_meowth_se_juega',
    '_CtxUBHydrapple',
    '_CtxUBMeowth',
    '_CtxUBFetch',
    '_v_ub_ogerpon_t1_primeros',
    '_v_ub_ogerpon_teal',
    '_v_ub_chikorita_t1',
    '_v_ub_applin_t1',
    '_ub_engine_refresh_pivot',
    '_uh_preparar_hydra_prox_turno',
    '_um_boss_engine_vs_crustle',
    '_um_es_primer_turno',
    '_v_ub_chikorita_arrancar',
    '_v_ub_applin_arrancar',
    '_eval_ub_best_target',
    '_ctx_ub_fetch_hydrapple',
    '_ctx_ub_fetch_meowth',
    '_AJUSTES_UB_HYDRAPPLE',
    '_REGLAS_UB_APPLIN',
    '_REGLAS_UB_BAYLEEF',
    '_REGLAS_UB_CHIKORITA',
    '_REGLAS_UB_DIPPLIN',
    '_REGLAS_UB_FEZ',
    '_REGLAS_UB_HYDRAPPLE',
    '_REGLAS_UB_MEGANIUM',
    '_REGLAS_UB_MEOWTH',
    '_REGLAS_UB_OGERPON',
    '_REGLAS_UB_PINSIR',
    '_REGLAS_UB_TAPU',
]
