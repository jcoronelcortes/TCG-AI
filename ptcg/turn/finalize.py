"""Closing the turn: play order by tiers, rescues and the final choice.

Extracted VERBATIM from the tail of `agent()` (wave 5). It receives a
`TurnoCtx` and unpacks its fields into locals with the SAME names, so the body
below is exactly the one that was in main.py -- without rewriting a single line
of logic. It works because it is the TAIL of the function: nothing afterwards
reads what it mutates, so no write-back is needed.
"""

from cg.api import AreaType, CardType, OptionType, SelectContext
from ptcg.calc.card import get_card, prize_count_op
from ptcg.calc.damage import _attacker_base_damage
from ptcg.calc.energy import _grass_mult
from ptcg.calc.opponent import _op_juega_crustle
from ptcg.calc.board import _active_of
from ptcg.cards.ids import Applin, Bayleef, Bug_Catching_Set, Chikorita, Dipplin, Fezandipiti_ex, Forest_of_Vitality, Grand_Tree, Hydrapple_ex, Lillie_Determination, Meganium, Meowth_ex, Pinsir, Poke_Pad, SCORE_USELESS_ATTACK, SCORE_VETO, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball, Xerosic_Machinations
from ptcg.cards.scoring import SCORE_LD_SUPP_COMPROMETIDO, _SUPP_PLAY_IDS
from ptcg.cards.tables import attack_table, card_table
from ptcg.decision.ultra_ball import _matchup_allows_playing, _ub_cost_destroys_better_card
from ptcg.state.agent_state import AGENT_STATE
from ptcg.state.zones import ZONE_DECK
from ptcg.engine.debug import _debug_log_decision
from ptcg.turn.ctx import TurnoCtx  # noqa: F401


def finalizar(tc):
    """Returns the option indexes the agent plays this turn."""
    # Unpacking of the context: same names as in agent().
    _ability_order_veto = tc._ability_order_veto
    _active_attack_wins_now = tc._active_attack_wins_now
    _attach_yields_to_teal_dance = tc._attach_yields_to_teal_dance
    _b = tc._b
    _dragapult_no_tapu = tc._dragapult_no_tapu
    _item_lock_incoming = tc._item_lock_incoming
    _ld_card = tc._ld_card
    _ld_opt = tc._ld_opt
    _lucario_sac_pivot = tc._lucario_sac_pivot
    _meowth_fetch_id = tc._meowth_fetch_id
    _meowth_fetch_loses_the_turn = tc._meowth_fetch_loses_the_turn
    _meowth_fetch_redundante = tc._meowth_fetch_redundante
    _meowth_ld_free = tc._meowth_ld_free
    _ready_attacker_count = tc._ready_attacker_count
    _suicide_swap_win_promote = tc._suicide_swap_win_promote
    _tapu_future_charge = tc._tapu_future_charge
    _tapu_sac_priority = tc._tapu_sac_priority
    _win_ko_active_via_promote = tc._win_ko_active_via_promote
    bench_count = tc.bench_count
    context = tc.context
    ctx = tc.ctx
    field_counts = tc.field_counts
    hand_counts = tc.hand_counts
    i = tc.i
    meowth_ability_lock = tc.meowth_ability_lock
    my_index = tc.my_index
    my_prize = tc.my_prize
    my_state = tc.my_state
    obs = tc.obs
    op_has_ability_immune_active = tc.op_has_ability_immune_active
    op_is_alakazam_deck = tc.op_is_alakazam_deck
    op_is_comfey_deck = tc.op_is_comfey_deck
    op_is_cubchoo_deck = tc.op_is_cubchoo_deck
    op_prize = tc.op_prize
    op_state = tc.op_state
    scores = tc.scores
    select = tc.select
    stadium_id = tc.stadium_id
    state = tc.state
    total_grass = tc.total_grass

    if select.effect is not None and select.effect.id == Poke_Pad and context == SelectContext.TO_HAND:
        _best_pp_score = SCORE_VETO
        _best_pp_id = 0
        for _pp_idx, _pp_opt in enumerate(select.option):
            if _pp_idx < len(scores) and scores[_pp_idx] > _best_pp_score:
                _pp_card = get_card(obs, _pp_opt.area, _pp_opt.index, my_index)
                if _pp_card is not None:
                    _best_pp_score = scores[_pp_idx]
                    _best_pp_id = _pp_card.id
        if _best_pp_id > 0 and _best_pp_score > 10:

            _pp_data = card_table.get(_best_pp_id)
            _pp_is_basic = not (_pp_data is not None and
                                (getattr(_pp_data, 'stage1', False) or
                                 getattr(_pp_data, 'stage2', False)))
            if _pp_is_basic:
                AGENT_STATE._poke_pad_target_id = _best_pp_id

    if (_lucario_sac_pivot and select.effect is not None
            and select.effect.id == Poke_Pad and context == SelectContext.TO_HAND):
        # Tapu Bulu is ONLY forced as a Poke Pad target when it really
        # contributes:
        #   * the opponent plays a deck with ex protection (Crustle / Cornerstone
        #     Ogerpon / Sylveon), where our ex do 0 damage, or
        #   * we already have a charged Hydrapple ex + Meganium in play, which
        #     allows putting Tapu Bulu down and charging it instantly (with
        #     Meganium 2 energies count as 4, so it can attack immediately).
        # In any other case (e.g. this very anti-Lucario scenario) the priority is
        # decided by the normal scoring: Applin > Chikorita > evolutions of Pokemon
        # in play that we do not have in hand, and Tapu Bulu is the last option.
        # Besides, a redundant Tapu Bulu is not fetched if we already have one in
        # hand or in play.
        _tapu_already = (hand_counts.get(Tapu_Bulu, 0) >= 1 or
                         field_counts.get(Tapu_Bulu, 0) >= 1)
        if (not _tapu_already) and _tapu_sac_priority:
            for _pp_sac_idx, _pp_sac_opt in enumerate(select.option):
                _pp_sac_card = get_card(obs, _pp_sac_opt.area, _pp_sac_opt.index, my_index)
                if _pp_sac_card is not None and _pp_sac_card.id == Tapu_Bulu:
                    if _pp_sac_idx < len(scores):
                        scores[_pp_sac_idx] = 99999
                    AGENT_STATE._poke_pad_target_id = Tapu_Bulu
                    break

    if select.effect is not None and select.effect.id == Ultra_Ball and context == SelectContext.TO_HAND:
        _best_ub_score = SCORE_VETO
        _best_ub_id = 0
        for _ub_idx, _ub_opt in enumerate(select.option):
            if _ub_idx < len(scores) and scores[_ub_idx] > _best_ub_score:
                _ub_card = get_card(obs, _ub_opt.area, _ub_opt.index, my_index)
                if _ub_card is not None:
                    _best_ub_score = scores[_ub_idx]
                    _best_ub_id = _ub_card.id
        if _best_ub_id == Meowth_ex and _best_ub_score > 10:
            AGENT_STATE._ub_meowth_pending = True
        if _best_ub_id == Fezandipiti_ex and _best_ub_score > 10:
            # Chain UB -> Fezandipiti ex -> Flip the Script: the search is already
            # paid for, the body GOES DOWN (see `_ub_fez_pending`).
            AGENT_STATE._ub_fez_pending = True

    # Chain Meowth ex -> Last-Ditch Catch -> Supporter: the chosen Supporter is
    # noted so the rest of the turn PLAYS it (see `_ld_supp_comprometido`). Same
    # pattern as the two blocks above: the id comes from the argmax of `scores`
    # over the prompt's options.
    if (select.effect is not None and select.effect.id == Meowth_ex
            and context == SelectContext.TO_HAND and not state.supporterPlayed):
        # Only with the body PAID FOR this turn: the Last-Ditch of a Meowth ex that
        # was already in play is free and does not commit the turn.
        _ld_serial = getattr(select.effect, 'serial', None)
        _ld_body_paid_for = False
        for _ld_pk in (my_state.bench or []) + (my_state.active or []):
            if (_ld_pk is not None and _ld_pk.id == Meowth_ex
                    and getattr(_ld_pk, 'appearThisTurn', False)
                    and (_ld_serial is None
                         or getattr(_ld_pk, 'serial', None) == _ld_serial)):
                _ld_body_paid_for = True
                break
        if _ld_body_paid_for:
            _best_ld_score = SCORE_VETO
            _best_ld_id = 0
            for _ld_idx, _ld_opt in enumerate(select.option):
                if _ld_idx < len(scores) and scores[_ld_idx] > _best_ld_score:
                    _ld_card = get_card(obs, _ld_opt.area, _ld_opt.index,
                                        my_index)
                    if _ld_card is not None:
                        _best_ld_score = scores[_ld_idx]
                        _best_ld_id = _ld_card.id
            if _best_ld_id in _SUPP_PLAY_IDS and _best_ld_score > 10:
                AGENT_STATE._ld_supp_comprometido = _best_ld_id

    _vetoed_stadium_idxs = set()
    _our_first_turn_guard = ((AGENT_STATE.we_go_first and state.turn == 1) or
                             (not AGENT_STATE.we_go_first and state.turn == 2))
    _replace_opp_stadium_ok = (
        (not AGENT_STATE.we_go_first) and state.turn == 2 and
        stadium_id != 0 and stadium_id != Forest_of_Vitality)
    # vs CRUSTLE, GOING SECOND: the stadium goes down BEFORE the Lillie's
    # (user's rule). Ordering mirror of the rule
    # `t1_segundos_crustle_estadio_antes_de_lillie` of `_REGLAS_FOREST_PLAY`:
    # without this exception the hard veto here (-99999) crushed the score that
    # rule grants and the stadium went back into the deck with Lillie's shuffle.
    # The Crustle deck does not play a stadium (or runs one or two copies), so
    # ours does not run the risk that motivates the general veto.
    _crustle_stadium_before_lillie = (
        (not AGENT_STATE.we_go_first) and state.turn == 2
        and _op_juega_crustle(op_state)
        and not state.supporterPlayed
        and hand_counts.get(Lillie_Determination, 0) >= 1)
    if (_our_first_turn_guard and not _replace_opp_stadium_ok
            and not _crustle_stadium_before_lillie and select.option):
        for _gi, _go in enumerate(select.option):
            if _gi >= len(scores):
                continue
            if _go.type == OptionType.PLAY:
                _gcard = get_card(obs, AreaType.HAND, _go.index, my_index)
                if _gcard is not None:
                    _gdata = card_table.get(_gcard.id)
                    if _gdata is not None and _gdata.cardType == CardType.STADIUM:
                        scores[_gi] = -99999
                        _vetoed_stadium_idxs.add(_gi)

    # =================================================================
    # PLAY ORDER (MAIN context): enforcing the requested sequence
    #   1) stadium  2) Bug Catching Set  3) basics + evolutions
    #   4) Poke Pad  5) charge energy
    # The stadium only becomes playable from turn 3 onwards (on turns 1/2 it is
    # vetoed further up), so its tier only acts "after the second turn". Energy
    # that enables a KO/lethal attack THIS turn keeps top priority (an
    # exception). Only these 5 categories are reordered among themselves through
    # a (tier, score) key: the high tiers are played first and, within the same
    # tier, the original score decides. The other options (Ultra Ball,
    # supporters, attack, etc.) keep their tier 0 and their score. Only a
    # playable option (score > 0) is promoted, so the vetoes (-1) are still
    # respected.
    #
    # BUG CATCHING SET BEFORE PUTTING A POKEMON DOWN (user, log 88166559 step 6 vs
    # Archaludon, WON with a mistake): looking at the top 7 and taking up to 2 {G}
    # Pokemon / Grass Energy changes WHICH body we put down and WHAT we charge it
    # with, so deciding the body BEFORE that information is deciding blind. There
    # the agent put down the Meowth ex (Lillie's engine, 21800) while holding the
    # BCS (12200) in hand, and the BCS ended up bringing a Chikorita -- a ONE-prize
    # body, a better bench candidate than a two-prize ex -- with the slot already
    # spent. Besides, the Meowth->Lillie's engine SHUFFLES the whole hand: a BCS
    # still in hand when Lillie's is played is lost in the deck, so the order is
    # not cosmetic. Reordering costs nothing because playing the BCS does not
    # consume the Pokemon drop (nor the attachment, nor the attack): the body goes
    # down afterwards, in the same turn, already with the 2 new cards in hand. It
    # equally covers the case "I put down an Ogerpon, use Teal Dance and a BCS comes
    # out": the freshly drawn BCS is played BEFORE the next body.
    #
    # It is implemented by DEMOTING the Pokemon drop (tier `_TIER_DEVELOP_TRAS_BCS`)
    # instead of promoting the BCS: that way the rule touches ONLY what the user
    # asked for -- EVOLUTIONS keep `_TIER_DEVELOP` and still precede the BCS
    # (promoting it also advanced the evolution into Hydrapple ex and broke its two
    # tests). Accepted transitive consequence: with a BCS and a Poke Pad in hand at
    # the same time, the drop also yields to the Poke Pad -- coherent, both are
    # "dig 7 before committing" cards.
    #
    # The demotion is only applied if the BCS is OFFERED in this very menu and with
    # a REAL score (>0): if it were not playable, postponing the body would leave it
    # undropped. The tiers are renumbered with gaps (x10) so the new level can be
    # inserted while keeping ALL the other relative orders.
    # =================================================================

    # =================================================================
    # REVOKING ORDERING VETOES ON ABILITIES (user, registro_006 step 78 vs
    # Archaludon ex, LOST).
    #
    # State at step 78 (turn 6, they knocked out our Ogerpon ex last turn):
    #
    #     US                                      OPPONENT
    #     active  Teal Mask Ogerpon ex 210 3e     active  Archaludon ex 400 3e
    #     bench   Bayleef, Meowth ex, 2x Applin,  bench   Duraludon 10, Duraludon 130,
    #             Fezandipiti ex (just played)            Fezandipiti ex
    #     hand    Lillie's Determination, Boss's Orders, Bayleef
    #
    # The menu offered FOUR plays: Lillie's (score -1), Boss's (20), the Flip the
    # Script ability of the freshly benched Fezandipiti ex (VETOED) and attacking
    # (1100). The agent ATTACKED and closed the turn, throwing away the 3-card
    # draw. It is a dead, unrecoverable loss: Flip the Script is ONCE PER TURN and
    # its activation condition (that one of our Pokemon was knocked out on the
    # previous turn) disappears with the turn.
    #
    # The cause is a CIRCULAR BLOCK between three rules that are each correct on
    # their own:
    #   * the ability is vetoed because "first Lillie's Determination, THEN the
    #     ability" (`_lillie_blocks_fez_ability`),
    #   * Lillie's is vetoed because it yields to an executable Boss's
    #     (`cede_a_boss_ejecutable`),
    #   * and Boss's is degraded to 20 because it yields to Lillie's with no
    #     benched attacker (`sin_atacante_banca_cede_a_lillie`).
    # None of the three is played and the ability dies with the turn.
    #
    # The fix attacks the whole class of error, not this trio: an ORDERING veto
    # ("first X") is only valid while X is REALLY playable in this menu. It is
    # revoked in two cases, and it is agnostic of the opposing deck (it only looks
    # at our hand and the menu):
    #
    #   (a) NO blocker is offered and playable (score > 0) in this very menu -- if
    #       X cannot be played, there is no "after X". It covers step 78 (Lillie's
    #       vetoed) and any blocker left in hand for lack of a legal target.
    #   (b) the blocker is offered and playable, but LOSES against attacking /
    #       passing and there is no other live play left: the turn closes with this
    #       very action, so "after X" is not going to arrive either. The blocker is
    #       required to score BELOW the best play that closes the turn, and the only
    #       live options must be blockers or turn-closers -- with that trimming they
    #       all live in tier 0, no tier can reorder them and the score comparison is
    #       exact.
    #
    # Outside those two cases the veto stands and the requested order (Unfair Stamp
    # / Lillie's Determination before the ability) is respected as is: if the
    # blocker wins the menu it is played first and, on leaving the hand, the veto
    # switches itself off in the next menu.
    # =================================================================
    if _ability_order_veto and context == SelectContext.MAIN:
        # Blockers REALLY playable now: {card id: score}.
        _aov_playable = {}
        # Best score among the plays that CLOSE the turn, and whether there is any
        # live play that is neither a turn-closer nor a PLAY from hand.
        _aov_best_close = SCORE_VETO
        _aov_otras_vivas = False
        for _aov_i, _aov_o in enumerate(select.option):
            if _aov_i >= len(scores) or scores[_aov_i] <= 0:
                continue
            if _aov_o.type in (OptionType.ATTACK, OptionType.END):
                _aov_best_close = max(_aov_best_close, scores[_aov_i])
            elif _aov_o.type == OptionType.PLAY:
                _aov_c = get_card(obs, AreaType.HAND, _aov_o.index, my_index)
                if _aov_c is not None:
                    _aov_playable[_aov_c.id] = max(
                        _aov_playable.get(_aov_c.id, SCORE_VETO),
                        scores[_aov_i])
            elif _aov_i not in _ability_order_veto:
                _aov_otras_vivas = True
        for _aov_idx, (_aov_score, _aov_blockers) in _ability_order_veto.items():
            if _aov_idx >= len(scores) or scores[_aov_idx] > 0:
                continue
            _aov_vivos = [_b for _b in _aov_blockers if _b in _aov_playable]
            if _aov_vivos:
                # (b): the blocker is alive, so it is only revoked if the turn closes
                # RIGHT NOW -- no other live play and the blocker below
                # attacking/passing.
                if _aov_otras_vivas:
                    continue
                if set(_aov_playable) - set(_aov_blockers):
                    continue
                if _aov_best_close <= 0:
                    continue
                if any(_aov_playable[_b] > _aov_best_close for _b in _aov_vivos):
                    continue
            scores[_aov_idx] = _aov_score

    # =================================================================
    # THE SUPPORTER THE LAST-DITCH BROUGHT GETS PLAYED (user, registro_002 step 22
    # vs Alakazam, WON with a mistake). That turn the agent chained correctly --
    # Ultra Ball -> Meowth ex -> Last-Ditch Catch -> Lillie's Determination --
    # and then immediately played the DAWN it already had in hand: the freshly
    # fetched Lillie's stayed dead and the 2-prize body on the bench was free.
    #
    # Why the previous vetoes were not enough: `_meowth_fetch_pierde_el_turno`
    # PREDICTS, before benching the Meowth, that the fetch takes the Supporter
    # slot -- but it is not evaluated on OUR FIRST TURN (the anti-donk line
    # benches the Meowth anyway) and, above all, it forces nothing AFTER the fetch.
    # The play scorer decided again from scratch with the new hand and there a
    # board veto governed (`no_barajar_ultimo_xerosic`, -1) which ignores that the
    # Lillie's is already PAID FOR with a 2-prize body.
    #
    # The rule is about COMMITMENT, not value: once the resource is spent, the
    # Supporter it brought keeps the turn's only slot. It is implemented with A
    # SINGLE gesture -- a score FLOOR applied with `max()` -- and NOT with a veto
    # on the other Supporters in hand. The two halves were measured separately
    # (self-play vs 4 opposing decks, 1500 games per cell, 6000 per variant):
    #
    #     without the rule       83.45%
    #     floor + veto the rest  82.78%   (-0.67)
    #     FLOOR ONLY             83.85%   (+0.40)   <- this one
    #     veto only              83.45%   ( 0.00)
    #
    # The floor (8000) is already above the normal band of ANY other Supporter (the
    # highest is Xerosic, ~7300), so the commitment wins the slot without needing to
    # veto anyone. The only thing the veto added was beating a DECISIVE Supporter
    # too (score > 8000: a Boss's that wins the game, a finisher) -- exactly the
    # case where the commitment MUST yield. That is why removing it does not break
    # the rule: it improves it.
    #
    # Deck-agnostic: it names no cards. It disarms itself when the Supporter is no
    # longer offered (discarded as a cost, shuffled away...) or when the slot has
    # already been spent (`supporterPlayed`).
    # =================================================================
    if (AGENT_STATE._ld_supp_comprometido and context == SelectContext.MAIN
            and not state.supporterPlayed):
        for _ld_i, _ld_o in enumerate(select.option):
            if _ld_o.type != OptionType.PLAY or _ld_i >= len(scores):
                continue
            _ld_c = get_card(obs, AreaType.HAND, _ld_o.index, my_index)
            if _ld_c is not None and _ld_c.id == AGENT_STATE._ld_supp_comprometido:
                scores[_ld_i] = max(scores[_ld_i],
                                    SCORE_LD_SUPP_COMPROMETIDO)

    _play_order_tier = [0] * len(scores)
    if context == SelectContext.MAIN:
        _TIER_WIN_ATTACK = 70
        _TIER_KO_ENERGY = 60
        # The Grand Tree ability goes ABOVE any stadium play: if we put ours down
        # first (Forest, tier STADIUM), the Grand Tree would go to the discard
        # with the free chain uncashed. The `esperar_habilidad_grand_tree` veto of
        # `_REGLAS_FOREST_PLAY` covers the same case by score; this tier covers it
        # by ORDER, which is what really rules when two plays live in different
        # tiers.
        _TIER_STADIUM_ABILITY = 55
        _TIER_STADIUM = 50
        _TIER_DEVELOP = 40
        _TIER_POKE_PAD = 30
        _TIER_BUG_SET = 20
        _TIER_DEVELOP_AFTER_BCS = 15
        _TIER_ENERGY = 10

        # A Bug Catching Set play really available NOW (offered in the menu and
        # with score > 0): while it exists, putting a Pokemon down yields.
        _bcs_play_idx = -1
        for _bcs_i, _bcs_o in enumerate(select.option):
            if (_bcs_o.type != OptionType.PLAY or _bcs_i >= len(scores)
                    or scores[_bcs_i] <= 0):
                continue
            _bcs_c = get_card(obs, AreaType.HAND, _bcs_o.index, my_index)
            if _bcs_c is not None and _bcs_c.id == Bug_Catching_Set:
                _bcs_play_idx = _bcs_i
                break
        for _po_i, _po_o in enumerate(select.option):
            if _po_i >= len(scores) or scores[_po_i] <= 0:
                continue
            if (_po_o.type == OptionType.ATTACK
                    and _active_attack_wins_now and AGENT_STATE.plan.attacker == 0):
                # Winning finisher with the active: MAXIMUM tier so it is executed
                # before any charge/development and closes the game (step 125).
                _play_order_tier[_po_i] = _TIER_WIN_ATTACK
            elif (_po_o.type == OptionType.RETREAT
                    and (_suicide_swap_win_promote
                         or _win_ko_active_via_promote)):
                # Relief of the suicidal finisher (user, registro_016 step 184): the
                # same tier as the winning finisher, because it is the SAME play --
                # closing the game this turn, only with the finisher on the bench.
                # Without this tier, the retreat (score 9600, tier 0) was crushed by
                # ORDER by any energy charge (tier ENERGY) despite being worth less:
                # the turn was spent attaching and the finisher never arrived.
                _play_order_tier[_po_i] = _TIER_WIN_ATTACK
            elif _po_o.type == OptionType.EVOLVE:
                _play_order_tier[_po_i] = _TIER_DEVELOP
            elif _po_o.type == OptionType.ATTACH:
                _po_is_ko_energy = (
                    getattr(AGENT_STATE.plan, 'energy', False)
                    and AGENT_STATE.plan.remain_hp is not None
                    and AGENT_STATE.plan.remain_hp <= 0
                    and AGENT_STATE.plan.attacker >= 0
                    and ((_po_o.inPlayArea == AreaType.ACTIVE
                          and AGENT_STATE.plan.attacker == 0)
                         or (_po_o.inPlayArea != AreaType.ACTIVE
                             and AGENT_STATE.plan.attacker == 1 + _po_o.inPlayIndex)))
                # Fix (user, log 86506312 step 97, vs Alakazam): do NOT treat the
                # charge to the ACTIVE as "KO energy" (tier 6) when
                # `_tapu_future_charge` is on. That flag already guarantees that the
                # active (Hydrapple ex) KNOCKS OUT with its CURRENT energy and that
                # Meganium is in play (each Grass counts double), so the extra energy
                # on the active is UNNECESSARY. Without this exclusion, the active's
                # KO_ENERGY tier crushed (6 > 1) the charge of the benched Tapu Bulu
                # (`_tapu_future_charge`, score 40000, tier ENERGY), wasting the energy
                # on an already-ready attacker instead of preparing the FUTURE attacker.
                # By lowering the active to tier ENERGY, the Tapu charge (40000) wins
                # the tie-break inside the same tier.
                if (_tapu_future_charge
                        and _po_o.inPlayArea == AreaType.ACTIVE):
                    _po_is_ko_energy = False
                if _po_i in _attach_yields_to_teal_dance:
                    # A pure development attachment with a Teal Dance pending: it
                    # stays in tier 0 next to the ability so the score decides
                    # (Teal Dance 7500 > capped attachment 7000).
                    continue
                _play_order_tier[_po_i] = (
                    _TIER_KO_ENERGY if _po_is_ko_energy else _TIER_ENERGY)
            elif _po_o.type == OptionType.PLAY:
                _po_card = get_card(obs, AreaType.HAND, _po_o.index, my_index)
                if _po_card is not None:
                    _po_data = card_table.get(_po_card.id)
                    if _po_card.id == Poke_Pad:
                        _play_order_tier[_po_i] = _TIER_POKE_PAD
                    elif _po_card.id == Bug_Catching_Set:
                        _play_order_tier[_po_i] = _TIER_BUG_SET
                    elif _po_card.id == Ultra_Ball and scores[_po_i] > 31000:
                        # UB->Meowth->Lillie's engine BEFORE the attachment (user,
                        # registro_008 step 58 vs Archaludon ex, LOST): the
                        # `_ub_engine_refresh_pivot` pivot scores the UB at 31450,
                        # but items live in tier 0 and the manual attachment (tier
                        # ENERGY=1, ~31410) crushed it by tier despite the score.
                        # Same pattern as Teal Dance (below): raise it to the ENERGY
                        # tier so that WITHIN the tier the score decides
                        # (31450 > 31410). It only applies with the pivot's score
                        # (>31000); a normal UB (<=12500) keeps its tier 0.
                        _play_order_tier[_po_i] = _TIER_ENERGY
                    elif _po_data is not None and _po_data.cardType == CardType.STADIUM:
                        _play_order_tier[_po_i] = _TIER_STADIUM
                    elif _po_data is not None and _po_data.cardType == CardType.POKEMON:
                        # Putting a Pokemon down yields to a pending Bug Catching
                        # Set (see the block header): with the 2 new cards in hand
                        # it is decided BETTER which body goes down.
                        _play_order_tier[_po_i] = (
                            _TIER_DEVELOP if _bcs_play_idx < 0
                            else _TIER_DEVELOP_AFTER_BCS)
            elif _po_o.type == OptionType.ABILITY:
                # Teal Dance PRECEDES the manual attachment (user, registro_004 step
                # 28, vs Mega Starmie): the Teal Dance ability of Teal Mask
                # Ogerpon ex attaches 1 Grass AND DRAWS a card, so it has to be
                # played BEFORE any manual energy attachment. Without this, the
                # ability stayed in tier 0 (below the ENERGY=1 tier of the
                # attachments) and the play order put a manual charge first even
                # though Teal Dance scores much higher, wasting the draw. By
                # putting it in the ENERGY tier, within the same tier the score
                # decides (Teal Dance ~31500 wins). The lethal KO charges of THIS
                # turn stay in tier KO_ENERGY=6.
                # GUARD (user, registro_009 step 113 vs Mega Lucario, LOST):
                # the promotion only applies when Teal Dance scores as a REAL
                # play (>= 29000: its branches run from 29000 to 31600). Without
                # the guard, a DEGRADED Teal Dance (7500: energy reserves,
                # anti-overcharge...) dominated the whole of tier 0 by TIER --
                # including Ripening Charge at 31100, which charged the ACTIVE
                # Hydrapple ex (1 energy) for the 3-prize KO on the Mega Lucario ex
                # (Syrup Storm 210 >= 160). The agent poured the recovered energy
                # onto a benched Ogerpon and lost the finisher.
                _po_ab_card = get_card(obs, _po_o.area, _po_o.index, my_index)
                if (_po_ab_card is not None
                        and _po_ab_card.id == Grand_Tree):
                    _play_order_tier[_po_i] = _TIER_STADIUM_ABILITY
                elif (_po_ab_card is not None
                        and _po_ab_card.id == Teal_Mask_Ogerpon_ex
                        and scores[_po_i] >= 29000):
                    _play_order_tier[_po_i] = _TIER_ENERGY
                elif (_po_ab_card is not None
                        and _po_ab_card.id == Fezandipiti_ex
                        and scores[_po_i] >= 29000):
                    # Flip the Script in the SAME tier as the charging abilities
                    # (user, registro_006 steps 95-102 vs Mega Lucario): in tier 0
                    # it was crushed by ORDER by any promoted Teal Dance /
                    # Ripening Charge, and the turn closed with the 3-card draw
                    # uncashed. Within the tier the score decides, and it already
                    # encodes the correct priority: an ability that ENABLES today's
                    # KO (41000+) > Flip the Script (31700) > development charges
                    # (<= 31600). A VETOED ability (deck-out or an unrevoked
                    # ORDERING veto) stays in tier 0, like the others.
                    _play_order_tier[_po_i] = _TIER_ENERGY
                elif (_po_ab_card is not None
                        and _po_ab_card.id == Hydrapple_ex
                        and scores[_po_i] >= 29000):
                    # Ripening Charge has to compete in the ENERGY tier with Teal
                    # Dance (above), just like it, when it scores as a REAL play
                    # (>= 29000). It covers TWO cases:
                    #   * the blocked ACTIVE Hydrapple ex of the retreat->promote
                    #     pivot (registro_008 step 82 vs Cubchoo), and
                    #   * charging the EMPTY BENCHED Hydrapple ex as a FUTURE
                    #     ATTACKER (user, registro_006 step 80 vs Mega Lucario):
                    #     without this the Ripening (31150) stayed in tier 0 and the
                    #     Teal Dance of an ALREADY charged Ogerpon (tier ENERGY,
                    #     31050) dominated it by TIER despite its LOWER score -> the
                    #     energy was poured onto the overcharged Ogerpon and the
                    #     Hydrapple ex was left with no energy for a future attack.
                    # Within the tier the score decides, and it already encodes the
                    # correct priority: a Teal Dance that ENABLES a KO (31500) >
                    # charging the benched Hydrapple (31150) > Teal Dance on a
                    # charged Ogerpon (31050). DEGRADED Ripening charges (7500:
                    # reserves) stay in tier 0 (same guard as Teal Dance).
                    _play_order_tier[_po_i] = _TIER_ENERGY

    # =================================================================
    # ANTI-STERILE-TURN RESCUE (user, registro_009 step 61 vs Dragapult,
    # LOST). State: active Chikorita (50/70), Tapu Bulu and Applin on the bench
    # uncharged, and in hand Unfair Stamp + Bayleef + Meganium + Meowth ex +
    # Xerosic + LILLIE'S DETERMINATION, with 6 prizes (Lillie's draws EIGHT). The
    # agent closed the turn with Growl (a 0-damage attack) and left the WHOLE hand
    # dead: the Lillie's scorer vetoed it through `_lillie_evolve_now` (there was
    # an evolution line "evolvable this turn") while the real evolution was blocked
    # by the veto on evolving in the active spot, so neither of the two plays
    # happened.
    #
    # A safety net independent of which veto fails: if the BEST play of the turn is
    # to end, or to attack with an attack that does NO damage at all (Growl), the
    # turn produces NOTHING -- and refilling the hand (drawing 6/8) is always
    # better than that. Lillie's veto is lifted and it is placed above that sterile
    # play. A 0-damage attack is detected with the PRINTED damage of the offered
    # attack and with `_attacker_base_damage` (which covers the attacks that scale,
    # e.g. Dipplin's Do the Wave), so a real chip attack (one that does take HP
    # away) does NOT count as a sterile turn.
    # Exception kept: vs Alakazam with Xerosic in hand the Powerful Hand cap is not
    # shuffled away (a CONCRETE reason: access to that card would be lost).
    #
    # ANTI-DECK-OUT RESERVE, formerly "vs Comfey NEVER" (user, log 88359220 step 33
    # vs Comfey/Yveltal, LOST -- registro_003). The turn was already closed
    # (evolution + Bug Catching Set + 2 Ogerpon + attachment done) and the agent
    # ended with Lillie's in hand and the turn's Supporter UNPLAYED: the Supporter
    # does NOT accumulate, a turn without playing it throws it away.
    # The old exemption was a MATCHUP prohibition; its real reason is arithmetic --
    # Lillie's shuffles the hand into the deck and draws 6 (8 with all 6 prizes
    # untouched), so its deck delta is (hand - 1) - draw and against a mill deck
    # that can bring us closer to deck-out. It is replaced by that arithmetic,
    # which is DECK-AGNOSTIC (it protects equally against any mill) and does not
    # block the rescue when the deck can easily take it: there the deck had 38
    # cards and the refill left it at 33, nowhere near deck-out.
    # Threshold <= 10 = "critical deck", the same one as `freno_deckout_mazo_critico`.
    # The rescue only overrides "doing nothing", so on the turns vs Comfey that DO
    # produce something (the Ogerpon-only plan) the reserve stays intact.
    _lil_draw = 8 if my_prize >= 6 else 6
    _lil_deck_after_refresh = (getattr(my_state, 'deckCount', 60)
                               + max(0, sum(hand_counts.values()) - 1)
                               - _lil_draw)
    if (context == SelectContext.MAIN and not state.supporterPlayed
            and _lil_deck_after_refresh > 10
            and not (op_is_alakazam_deck
                     and hand_counts.get(Xerosic_Machinations, 0) >= 1)):
        _rescate_lil = -1
        for _wi, _wo in enumerate(select.option):
            if _wi >= len(scores) or _wo.type != OptionType.PLAY:
                continue
            if scores[_wi] > 0:
                continue
            _wcard = get_card(obs, AreaType.HAND, _wo.index, my_index)
            if _wcard is not None and _wcard.id == Lillie_Determination:
                _rescate_lil = _wi
                break
        if _rescate_lil >= 0 and scores:
            _best_i = max(range(len(scores)),
                           key=lambda i: (_play_order_tier[i], scores[i]))
            _best_o = select.option[_best_i]
            _sterile_turn = False
            if _best_o.type == OptionType.END or scores[_best_i] <= 0:
                _sterile_turn = True
            elif _best_o.type == OptionType.ATTACK:
                _est_act = _active_of(my_state)
                _est_op = _active_of(op_state)
                _est_atk = attack_table.get(getattr(_best_o, 'attackId', None))
                _est_impreso = getattr(_est_atk, 'damage', 0) or 0
                _est_base = 0
                if _est_act is not None:
                    _est_e = len(_est_act.energies)
                    _est_base = _attacker_base_damage(
                        _est_act.id, _est_op, _est_e * _grass_mult(),
                        grass_scale=total_grass, teal_self_energy=_est_e,
                        bench_count=bench_count)
                _sterile_turn = (_est_impreso <= 0 and _est_base <= 0)
            if _sterile_turn:
                scores[_rescate_lil] = max(1500, scores[_best_i] + 100)

    # =================================================================
    # DEAD-TURN RESCUE WITH MEOWTH EX (user, registro_002 step 18 vs
    # Cubchoo, LOST). Sibling of the Lillie's rescue above, for when the Lillie's
    # is NOT in hand but in the DECK: if the BEST play of the turn is to END and we
    # have a Meowth ex in hand whose Last-Ditch Catch can bring a Supporter that is
    # PLAYABLE this turn, putting it down is strictly better than doing nothing --
    # it refills the hand and opens options. On that turn 2 the active was a Meowth
    # ex that does not attack, the bench was Tapu Bulu (0 energies, it needs 4) and
    # an Applin, the hand had no play at all, and the agent closed the turn with a
    # Meowth ex in hand that had also JUST BEEN FETCHED with an Ultra Ball (two
    # discards spent on a card it then refused to play).
    #
    # It goes AFTER all the vetoes and only overrides "doing nothing", so no
    # matchup rule is weakened while any real play remains: the anti-Cubchoo veto
    # on a 2nd Meowth ex (`field_counts[Meowth_ex] == 0`) is still in force on
    # every turn that produces something. Deck-agnostic.
    if (context == SelectContext.MAIN and scores
            and not state.supporterPlayed
            and not meowth_ability_lock
            and bench_count < 5
            and _meowth_ld_free
            and field_counts.get(Meowth_ex, 0) < 2
            and hand_counts.get(Meowth_ex, 0) >= 1
            # WITH NO READY ATTACKER AT ALL: the turn is dead for lack of
            # DEVELOPMENT, which is exactly what refilling the hand fixes. With
            # ready attackers a dead turn means something else (the opposing
            # active is an immune wall, we are locked...) and there adding a
            # 2-prize body unblocks nothing: the plan is Boss's/a pivot.
            # Without this gate the rescue fired on turns 12-16 with 2-4 ready
            # attackers against the Cornerstone wall.
            and _ready_attacker_count == 0
            # The fetch has to contribute something: a Supporter in the DECK that
            # we do not already have in hand (see `_meowth_fetch_prediccion`) and
            # that does not lose the turn's ONLY Supporter slot against one we
            # already have (`_meowth_fetch_pierde_el_turno`).
            and _meowth_fetch_id is not None
            and not _meowth_fetch_redundante
            and not _meowth_fetch_loses_the_turn):
        _mw_rescate = -1
        for _mwi, _mwo in enumerate(select.option):
            if _mwi >= len(scores) or _mwo.type != OptionType.PLAY:
                continue
            _mwcard = get_card(obs, AreaType.HAND, _mwo.index, my_index)
            if _mwcard is not None and _mwcard.id == Meowth_ex:
                _mw_rescate = _mwi
                break
        if _mw_rescate >= 0:
            _mw_best_i = max(range(len(scores)),
                              key=lambda i: (_play_order_tier[i], scores[i]))
            _mw_best_o = select.option[_mw_best_i]
            if (_mw_best_o.type == OptionType.END
                    or scores[_mw_best_i] <= 0):
                scores[_mw_rescate] = max(1500, scores[_mw_best_i] + 100)

    # =================================================================
    # ANTI-EMPTY-BENCH SAFETY NET (user, registro_002 step 15 vs Mega
    # Starmie ex, LOST): NEVER end the turn with an EMPTY bench if we can develop
    # it. With a single basic in the active spot and no bench, if the opponent
    # knocks that active out WE LOSE the game (there is nobody to promote). If the
    # best play would be to END (or any sterile play with score <= 0) and there is
    # an option that puts a Pokemon on the bench -- an Ultra Ball that searches for
    # a basic, or putting a basic down from hand -- that play is prioritised above
    # ending the turn. Preference: the SEARCH (it brings a useful attacker, e.g.
    # Ogerpon ex, which also accelerates with Teal Dance) over putting down any old
    # basic. It does NOT apply if attacking already WINS the game (there is no
    # future turn to protect). It is a FINAL net: it runs EVEN IF the individual
    # vetoes of each play (Meowth ex with the Supporter already played, holding
    # Lillie's, etc.) knocked it down to <= 0. Deck-agnostic.
    if (context == SelectContext.MAIN and bench_count == 0 and scores):
        _sb_basics_deck = (Chikorita, Applin, Teal_Mask_Ogerpon_ex, Tapu_Bulu,
                           Meowth_ex, Fezandipiti_ex, Pinsir)
        _sb_best_i = max(range(len(scores)),
                         key=lambda i: (_play_order_tier[i], scores[i]))
        _sb_best_o = select.option[_sb_best_i]
        _sb_sterile = (_sb_best_o.type == OptionType.END
                       or scores[_sb_best_i] <= 0)
        _sb_wins = False
        if (_sb_best_o.type == OptionType.ATTACK
                and AGENT_STATE.plan.remain_hp is not None and AGENT_STATE.plan.remain_hp <= 0):
            _sb_opa = op_state.active[0] if op_state.active else None
            if _sb_opa is not None and op_prize <= prize_count_op(_sb_opa):
                _sb_wins = True
        if _sb_sterile and not _sb_wins:
            _sb_fetch_i = -1
            _sb_basic_i = -1
            for _sbi, _sbo in enumerate(select.option):
                if _sbo.type != OptionType.PLAY:
                    continue
                _sbc = get_card(obs, AreaType.HAND, _sbo.index, my_index)
                if _sbc is None:
                    continue
                _sbd = card_table.get(_sbc.id)
                if _sbd is None:
                    continue
                if (_sbc.id == Ultra_Ball and _sb_fetch_i < 0
                        and any(AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(_b, {}).get(
                                    ZONE_DECK, 0) > 0
                                for _b in _sb_basics_deck)):
                    _sb_fetch_i = _sbi
                elif (_sbd.cardType == CardType.POKEMON
                      and not getattr(_sbd, 'stage1', False)
                      and not getattr(_sbd, 'stage2', False)
                      and _sb_basic_i < 0):
                    _sb_basic_i = _sbi
            _sb_pick = _sb_fetch_i if _sb_fetch_i >= 0 else _sb_basic_i
            if _sb_pick >= 0:
                scores[_sb_pick] = max(200, scores[_sb_best_i] + 100)
                _play_order_tier[_sb_pick] = max(
                    _play_order_tier[_sb_pick], _play_order_tier[_sb_best_i])

    # =================================================================
    # ANTI-STERILE-TURN NET with Ultra Ball (jul 2026 autopsies: the cluster of
    # sterile turn-2s with a vetoed UB appeared in FOUR different matchups --
    # iron_thorns, cornerstone, comfey and crustle_kangaskhan, 13/31 t2 findings
    # in the last one). The previous net only covers an EMPTY bench; this one
    # covers the rest: if the best play of the turn is to END (or anything with
    # score <= 0) and a vetoed Ultra Ball has a USEFUL target in the deck,
    # digging with the UB always produces more than END. "Useful" = a deployable
    # basic (a bench with room) or an EVOLUTION linked to a body already in play
    # (playable next turn). Guard: not if attacking already wins.
    #
    # "USEFUL" IS DECIDED BY THE MATCHUP PLAN, NOT BY A PER-DECK PROHIBITION
    # (jul 2026 sweep, prompted by the two failures of log 88359220). The guard
    # `not op_is_comfey_deck` was a crude proxy for a concrete question: vs
    # Comfey the plan only allows putting Teal Mask Ogerpon ex down (max 2), so
    # digging any OTHER body brings a card the plan itself will veto when
    # putting it down -- two cards of hand for nothing. Asked via
    # `_matchup_permite_bajar`, the net stops firing in those cases just as
    # before, but it DOES fire when the target fits the plan: an Ogerpon ex with
    # <2 in play is exactly what the matchup wants to search for, and the Ultra
    # Ball is on its item allowlist. The reason the old comment cited ("burning
    # 2 cards of the deck feeds the mill") was also inaccurate: the Ultra Ball's
    # cost comes from the HAND; only the fetched card comes from the deck.
    # Self-play gate vs deck/rivales/comfey.csv, 6000 games per branch:
    # 91.7% with the change vs 91.2% without it (+0.5 points, INSIDE THE NOISE:
    # the change stands on the reasoning, the gate only rules out that it hurts).
    #
    # vs CUBCHOO the guard IS KEPT. There the conservative END is deliberate
    # matchup policy ([[anti-cubchoo-no-retirada-pivote]]) and not a proxy for
    # anything: filtering by `CUBCHOO_ALLOWED_PLAY_IDS` instead of switching the
    # net off MEASURED WORSE in the same gate -- 68.7% vs 70.0% over 6000 games
    # per branch (-1.3 points, z~-1.7). That half of the sweep was reverted.
    # FIRST-TURN GUARD (user, registro_002 steps 24/27 vs Ceruledge,
    # LOST): on our first turn of action (turn <= 2) the net only applies with a
    # bench <= 2 (REAL development pending, like the crustle t2 case with a bench
    # of 1 that motivated it). With the bench already populated (4/5) and the hand
    # full of future value (Xerosic/Stamp/Lana's/evolutions), the UB burns 2
    # useful cards to bring a redundant basic: the agent chained TWO UBs
    # discarding Xerosic+Meganium+Lana's+Dipplin for 2 dead Meowth ex.
    # The only legitimate first-turn UB with the board already built is the
    # Budew/Dragapult case, which lives in `_ub_first_turn_allowed`, not here.
    if (context == SelectContext.MAIN and scores and bench_count > 0
            and not op_is_cubchoo_deck
            and (state.turn > 2 or bench_count <= 2)
            and sum(hand_counts.values()) >= 3):
        _st_best_i = max(range(len(scores)),
                         key=lambda i: (_play_order_tier[i], scores[i]))
        _st_best_o = select.option[_st_best_i]
        _st_sterile = (_st_best_o.type == OptionType.END
                       or scores[_st_best_i] <= 0)
        # A TURN THAT ENDS BY REALLY ATTACKING IS NOT A DEAD TURN (user,
        # registro_006 step 98 vs Mega Lucario ex, LOST). The premise of this
        # net is "the alternative to digging is to END without doing anything",
        # and that is why digging always produces more. But `scores[best] <= 0`
        # does not mean END: a normal ATTACK scores -1 by default (it is the
        # argmax fallback), and Items do not consume the attack -- so on that
        # turn the Ultra Ball saved nothing, it only paid 2 cards of hand BEFORE
        # a 210 Syrup Storm that was going to be fired anyway (and was fired, at
        # step 104).
        # The attack is measured just like in the Lillie's rescue above (printed
        # or base damage > 0) and attacks already marked as useless by immunity
        # (SCORE_USELESS_ATTACK) are discarded.
        if _st_sterile:
            _st_act = _active_of(my_state)
            _st_opa_dmg = _active_of(op_state)
            for _sta_i, _sta_o in enumerate(select.option):
                if _sta_o.type != OptionType.ATTACK:
                    continue
                if _sta_i < len(scores) and scores[_sta_i] <= SCORE_USELESS_ATTACK:
                    continue
                _sta_atk = attack_table.get(getattr(_sta_o, 'attackId', None))
                _sta_impreso = getattr(_sta_atk, 'damage', 0) or 0
                _sta_base = 0
                if _st_act is not None:
                    _sta_e = len(_st_act.energies)
                    _sta_base = _attacker_base_damage(
                        _st_act.id, _st_opa_dmg, _sta_e * _grass_mult(),
                        grass_scale=total_grass, teal_self_energy=_sta_e,
                        bench_count=bench_count)
                if _sta_impreso > 0 or _sta_base > 0:
                    _st_sterile = False
                    break
        _st_wins = False
        if (_st_best_o.type == OptionType.ATTACK
                and AGENT_STATE.plan.remain_hp is not None and AGENT_STATE.plan.remain_hp <= 0):
            _st_opa = op_state.active[0] if op_state.active else None
            if _st_opa is not None and op_prize <= prize_count_op(_st_opa):
                _st_wins = True
        if _st_sterile and not _st_wins:
            _st_in_deck = lambda cid: (
                AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(cid, {}).get(ZONE_DECK, 0) > 0)
            # ITEM LOCK EXCEPTION (user): with Budew on the opposing field
            # -- or against Dragapult, which runs it and can put it down -- the
            # Ultra Ball is "use it or lose it": next turn items cannot be
            # played. Only in that case is it allowed to dig for something that
            # serves the NEXT turn instead of this one. Same predicate the
            # UB->Meowth->Lillie's chain uses (`_bloqueo_de_items_inminente`).
            _st_item_lock = _item_lock_incoming
            # The matchup plan filters the targets: a body the PLAY branch
            # will veto when putting it down saves no turn (see
            # `_matchup_permite_bajar`). With no restrictive plan it filters
            # nothing.
            _st_plan_ok = lambda cid: _matchup_allows_playing(
                cid, field_counts, op_is_comfey_deck, op_is_cubchoo_deck,
                cubchoo_allow_tapu=(op_has_ability_immune_active
                                    or AGENT_STATE.op_is_cornerstone_deck),
                dragapult_no_tapu=_dragapult_no_tapu)
            # Meowth ex only counts as a USEFUL target if its Last-Ditch Catch
            # can produce something this turn (user, registro_006 steps 98-104):
            # it is a 2-prize body whose only value is fetching a Supporter, so
            # with the turn's Supporter already played, with the ability blocked
            # (Watchtower) or with the Last-Ditch already spent
            # (`_meowth_ld_free`), the PLAY branch will veto it when putting it
            # down and the Ultra Ball will have burned 2 cards for a dead card.
            # Same criterion as the fetch (`last_ditch_no_produce`) and as
            # `_ub_cavar_meowth_se_juega`.
            _st_meowth_useful = (not state.supporterPlayed
                               and not meowth_ability_lock
                               and _meowth_ld_free
                               and field_counts.get(Meowth_ex, 0) < 2)
            _st_body_ok = lambda cid: (
                _st_plan_ok(cid)
                and (cid != Meowth_ex or _st_meowth_useful))
            _st_basic_useful = (bench_count < 5 and any(
                _st_in_deck(_b) and _st_body_ok(_b) for _b in (
                    Chikorita, Applin, Teal_Mask_Ogerpon_ex, Tapu_Bulu,
                    Meowth_ex, Fezandipiti_ex)))
            # The pre-evolution has to be able to EVOLVE THIS TURN (user,
            # registro_003 vs Mega Abomasnow ex): with the Applin just put down
            # (`appearThisTurn`, without Forest of Vitality) there is no way to
            # evolve, so searching for its evolution produces nothing this
            # turn -- and the Ultra Ball costs TWO cards from hand. It is
            # checked body by body (`appearThisTurn`), not by species: with two
            # Applin, one just played and another settled, the line DOES come
            # out. With the item lock threat the previous criterion is kept (it
            # is enough for the pre-evolution to be in play: it serves the next
            # turn, which is exactly what is being bought).
            def _st_evolvable(pre_id):
                for _stp in ((my_state.active or []) + (my_state.bench or [])):
                    if _stp is None or _stp.id != pre_id:
                        continue
                    if (_st_item_lock or AGENT_STATE.forest_in_play
                            or not getattr(_stp, 'appearThisTurn', False)):
                        return True
                return False
            _st_evo_useful = any(
                _st_evolvable(_pre) and _st_in_deck(_evo)
                and _st_plan_ok(_evo)
                for _pre, _evo in ((Applin, Dipplin), (Chikorita, Bayleef),
                                   (Bayleef, Meganium), (Dipplin, Hydrapple_ex)))
            # What could ALREADY be played is not dug for (user, registro_003 step 25
            # vs Mega Abomasnow ex, LOST): if the menu already offers putting a
            # Pokemon down from hand (or evolving) and the scorer has VETOED it, the
            # turn is not dead for lack of bodies -- it is dead because putting
            # another body down adds nothing. Digging with the Ultra Ball brings more
            # of the same and also burns TWO cards: there it discarded Meganium (the
            # Stage 2 of the line) + Dawn to bring a SECOND Meowth ex it then did not
            # play. Ending the turn is strictly better.
            _st_pokemon_en_menu = False
            for _stc_o in select.option:
                if _stc_o.type == OptionType.EVOLVE:
                    _st_pokemon_en_menu = True
                    break
                if _stc_o.type != OptionType.PLAY:
                    continue
                _stc_c = get_card(obs, AreaType.HAND, _stc_o.index, my_index)
                if _stc_c is None or _stc_c.id == Ultra_Ball:
                    continue
                _stc_d = card_table.get(_stc_c.id)
                if (_stc_d is not None
                        and _stc_d.cardType == CardType.POKEMON):
                    _st_pokemon_en_menu = True
                    break
            if _st_pokemon_en_menu and not _st_item_lock:
                _st_basic_useful = False
                _st_evo_useful = False
            # THE COST VETO IS NOT REVOKED BY A STERILE TURN (user, log
            # 88359220 steps 8-14 vs Comfey/Yveltal, LOST -- registro_001).
            # Scenario: OUR first turn going FIRST (there is no attack or
            # Supporter in the menu: the turn is sterile BY RULE, not by bad
            # construction), active Chikorita + Fezandipiti ex on the bench,
            # hand {Ultra Ball, Lillie's Determination, Bayleef, Grass, Unfair
            # Stamp}. `_score_ultra_ball_play` VETOED it correctly by cost
            # (`_ub_cancel_lillie`: the only real fodder is the Grass -- the
            # Bayleef links with the Chikorita in the active spot and the Unfair
            # Stamp is never discarded -- so paying the 2 discards takes the
            # Lillie's down with it), but this net resurrected it at 200 and the
            # agent discarded Grass + Lillie's to dig out a Meowth ex... whose
            # Last-Ditch Catch went and fetched ANOTHER Lillie's. Balance:
            # -3 cards of hand and a 2-prize body given away, to end up with the
            # SAME card we already had.
            # The distinction is general and holds for any deck: the vetoes this
            # net can revoke are the CONSERVATISM ones ("there is no useful
            # target", "it is early"), because facing a dead turn digging always
            # produces more than END. The COST veto is card arithmetic -- the
            # Ultra Ball is worth LESS than what has to be discarded to play it --
            # and that inequality does not change because the turn is dead: END
            # keeps the Supporter / the evolution piece for the next turn, which
            # is strictly more than trading them for a redundant basic. See
            # `_ub_coste_destruye_carta_mejor`.
            if _ub_cost_destroys_better_card(ctx):
                _st_basic_useful = False
                _st_evo_useful = False
            if _st_basic_useful or _st_evo_useful:
                for _sti, _sto in enumerate(select.option):
                    if _sti >= len(scores) or _sto.type != OptionType.PLAY:
                        continue
                    if scores[_sti] > 0:
                        continue
                    _stc = get_card(obs, AreaType.HAND, _sto.index, my_index)
                    if _stc is not None and _stc.id == Ultra_Ball:
                        scores[_sti] = max(200, scores[_st_best_i] + 100)
                        _play_order_tier[_sti] = max(
                            _play_order_tier[_sti],
                            _play_order_tier[_st_best_i])
                        break

    desc_indices = [i for i, _ in sorted(
        enumerate(scores),
        key=lambda x: (_play_order_tier[x[0]], x[1]),
        reverse=True)]
    _debug_log_decision(context, select, scores, obs, my_index)

    if context == SelectContext.SETUP_BENCH_POKEMON:
        wanted = [i for i in desc_indices if scores[i] >= 0]

        if len(wanted) < select.minCount:
            wanted = desc_indices[:select.minCount]
        return wanted[:select.maxCount]

    if _vetoed_stadium_idxs:
        desc_indices = [i for i in desc_indices if i not in _vetoed_stadium_idxs]

    return desc_indices[:select.maxCount]


__all__ = ['finalizar']
