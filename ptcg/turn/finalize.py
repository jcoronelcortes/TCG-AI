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
from ptcg.cards.ids import Applin, BOSS_SCORE_PRIZE_RANK_BASE, Bayleef, Boss_Orders, Bug_Catching_Set, Chikorita, Dipplin, Fezandipiti_ex, Forest_of_Vitality, Grand_Tree, Hydrapple_ex, KO_WINDOW_PLAY_IDS, Lanas_Aid, Lillie_Determination, Meganium, Meowth_ex, Pinsir, Poke_Pad, SCORE_USELESS_ATTACK, SCORE_VETO, SUPP_SCORE_LAST_RESORT_BAND, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball, Xerosic_Machinations
from ptcg.cards.scoring import SCORE_LD_SUPP_COMPROMETIDO, _SUPP_PLAY_IDS
from ptcg.cards.tables import HAND_COST_ABILITY_IDS, HAND_RESET_PLAY_IDS, attack_table, card_table
from ptcg.decision.ultra_ball import _matchup_allows_playing, _ub_cost_destroys_better_card
from ptcg.state.agent_state import AGENT_STATE
from ptcg.state.zones import ZONE_DECK
from ptcg.engine.debug import DEBUG_DECISIONS, _debug_log_decision
from ptcg.turn.ctx import TurnCtx  # noqa: F401
from ptcg.turn.game_plan import plan_of


def finalizar(tc):
    """Returns the option indexes the agent plays this turn."""
    # Unpacking of the context: same names as in agent().
    _order_veto = tc._order_veto
    _active_attack_wins_now = tc._active_attack_wins_now
    _attach_yields_to_teal_dance = tc._attach_yields_to_teal_dance
    _b = tc._b
    _dragapult_no_tapu = tc._dragapult_no_tapu
    _ft_hold_lone_meowth = tc._ft_hold_lone_meowth
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

    # THE BODY THIS TURN PAID FOR (user, registro_012 step 77, episode 91179054
    # vs Mega Starmie ex, LOST). What arms these two flags is not WHICH card did
    # the fetching: it is that a card of OURS spent itself this turn to put that
    # body in hand. The guard used to name `Ultra_Ball`, so the very same chain
    # through a Night Stretcher was invisible: the Stretcher's own selection rule
    # (`fetch_supporter_from_deck`, `_RULES_NS_MEOWTH`) says in its comment
    # "recover Meowth ex TO PUT IT DOWN so Last-Ditch fetches a Supporter",
    # recovered it from the discard for exactly that -- and then the play ladder
    # killed the body with the generic "the active is already a ready attacker"
    # veto (`play.py`, the log 86511741 arm). The Stretcher went to the discard,
    # the Meowth ex stayed dead in hand, the Supporter slot went unused and the
    # turn closed with a 150 chip into a 330 HP wall.
    #
    # It is the same incoherence that `test_both_copies_of_the_fetch_ladder_agree`
    # watches for on the fetch ladder, one layer up: the half that PAYS and the
    # half that EXECUTES answered the same board differently. Reading the source
    # card out of the condition makes the flags say what they always meant -- a
    # search already paid for is completed -- for any recovery or search card,
    # in any deck. The names keep their `_ub_` prefix because ~20 tests and the
    # notes reset them by name; read it as "fetch pending", not "Ultra Ball".
    #
    # `select.effect` is the card of ours resolving the prompt, and this whole
    # function only ever runs on OUR menus, so no opposing effect can arm them.
    if select.effect is not None and context == SelectContext.TO_HAND:
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
            # Chain fetch -> Fezandipiti ex -> Flip the Script: the search is
            # already paid for, the body GOES DOWN (see `_ub_fez_pending`).
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
    # `t1_second_crustle_stadium_before_lillie` of `_RULES_FOREST_PLAY`:
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
    # It is implemented by DEMOTING the Pokemon drop (tier `_TIER_DEVELOP_AFTER_BCS`)
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
    #     (`yields_to_executable_boss`),
    #   * and Boss's is degraded to 20 because it yields to Lillie's with no
    #     benched attacker (`no_bench_attacker_yields_to_lillie`).
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
    if _order_veto and context == SelectContext.MAIN:
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
            elif _aov_i not in _order_veto:
                _aov_otras_vivas = True
        for _aov_idx, (_aov_score, _aov_blockers) in _order_veto.items():
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
    # Why the previous vetoes were not enough: `_meowth_fetch_loses_the_turn`
    # PREDICTS, before benching the Meowth, that the fetch takes the Supporter
    # slot -- but it is not evaluated on OUR FIRST TURN (the anti-donk line
    # benches the Meowth anyway) and, above all, it forces nothing AFTER the fetch.
    # The play scorer decided again from scratch with the new hand and there a
    # board veto governed (`do_not_shuffle_the_last_xerosic`, -1) which ignores that the
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
    # ... BUT THE COMMITMENT ARBITRATES BETWEEN REFILLS, NOT AGAINST A GUST THAT
    # IS CASHING (user, episode 90333949 turn 4, step 47 vs Archaludon, LOST).
    # The floor is 8000 because that clears "the normal band of ANY other
    # Supporter" -- and every Supporter that sentence weighed is a REFILL: Dawn,
    # Lillie's, Lana's, Xerosic. Boss's Orders is not one. It does not refill
    # anything: it rewrites which body is in the active spot, and the whole upper
    # half of its ladder is an attack with a KO already behind it. At 8000 the
    # floor sat above almost that entire ladder, so a fetched refill outranked
    # the finisher it was supposed to be digging FOR.
    #
    # In the record: Boss's on their benched Duraludon (the pre-evolution of
    # Archaludon ex, the deck's real attacker) was worth 5220 -- gust, knock out,
    # a prize and the line cut -- and Lillie's had ALREADY vetoed itself for that
    # exact reason (`yields_to_executable_boss`, -1). The floor resurrected it to
    # 8000, the Boss's went back into the deck with the rest of the hand, and the
    # attack it left us did 150 to a 160 HP Cinderace: no prize.
    #
    # The line is `BOSS_SCORE_PRIZE_RANK_BASE`, and it is the ladder's own seam:
    # at or above it every branch has a prize, a wall or a win behind it
    # (WIN_NOW, GUST_2PRIZE, WIN_VIA_BENCH, WALL_GUST, DODGE_REDIRECT,
    # PRIZE_RANK); below it sit the gusts that take nothing (TRAP 3700, UNLOCK
    # 2600, LOW_VALUE 1500, EMPTY 20) and those DO yield to a refill, commitment
    # or not. Deck-agnostic: it reads the Boss's own score, not a board.
    _ld_gust_cashes = any(
        _ldg_o.type == OptionType.PLAY and _ldg_i < len(scores)
        and scores[_ldg_i] >= BOSS_SCORE_PRIZE_RANK_BASE
        and (lambda _c: _c is not None and _c.id == Boss_Orders)(
            get_card(obs, AreaType.HAND, _ldg_o.index, my_index))
        for _ldg_i, _ldg_o in enumerate(select.option))
    if (AGENT_STATE._ld_supp_comprometido and context == SelectContext.MAIN
            and not state.supporterPlayed and not _ld_gust_cashes):
        for _ld_i, _ld_o in enumerate(select.option):
            if _ld_o.type != OptionType.PLAY or _ld_i >= len(scores):
                continue
            _ld_c = get_card(obs, AreaType.HAND, _ld_o.index, my_index)
            if _ld_c is not None and _ld_c.id == AGENT_STATE._ld_supp_comprometido:
                # ... AND THE COMMITMENT DOES NOT RESURRECT A GUST THE BOARD
                # VETOED (user, episode 91069873 turn 6, step 80 vs Marnie's
                # Grimmsnarl ex, WON in spite of this).
                #
                # Mirror of `_ld_gust_cashes` above: there the committed refill
                # yields to a Boss's that cashes; here the COMMITTED card is the
                # Boss's itself and its own ladder scored it a veto. In the
                # record our Hydrapple ex was in the active spot with the KO
                # already served on their 320 HP Grimmsnarl ex (2 prizes), the
                # Boss's ladder had said so (`no_value`, -1) -- and the floor
                # lifted that -1 to 8000, played it anyway, gusted up a 100 HP
                # Morgrem and the turn cashed ONE prize instead of two.
                #
                # The asymmetry with the founding case is the card, not the
                # board: a refill (Dawn, Lillie's, Lana's, Xerosic) only moves
                # OUR cards, so a commitment -- an argument about a resource
                # already spent -- may overrule the resource veto that stopped
                # it. Boss's Orders is the one Supporter that rewrites the body
                # in the active spot, which is the body we KNOCK OUT: its veto
                # is a decision about PRIZES, and no amount of sunk Meowth ex
                # buys prizes back. Deck-agnostic and reason-agnostic: it reads
                # the Boss's own score, and every live rung of that ladder is
                # above zero (the lowest, EMPTY, is 20).
                if (_ld_c.id == Boss_Orders and scores[_ld_i] <= 0):
                    continue
                scores[_ld_i] = max(scores[_ld_i],
                                    SCORE_LD_SUPP_COMPROMETIDO)

    _play_order_tier = [0] * len(scores)
    if context == SelectContext.MAIN:
        _TIER_WIN_ATTACK = 70
        _TIER_KO_ENERGY = 60
        # The Grand Tree ability goes ABOVE any stadium play: if we put ours down
        # first (Forest, tier STADIUM), the Grand Tree would go to the discard
        # with the free chain uncashed. The `wait_for_the_grand_tree_ability` veto of
        # `_RULES_FOREST_PLAY` covers the same case by score; this tier covers it
        # by ORDER, which is what really rules when two plays live in different
        # tiers.
        _TIER_STADIUM_ABILITY = 55
        _TIER_STADIUM = 50
        # THE FREE DRAW GOES BEFORE THE BODY THAT PAYS FOR THE SEARCH (user,
        # august 2026, records/registro_005 step 50 -- episode 91176376 vs
        # Alakazam, LOST). See `_fez_before_the_search_body` below: Flip the
        # Script above `_TIER_DEVELOP` so the 3 cards are drawn BEFORE Meowth ex
        # is benched to search for a Supporter.
        _TIER_FEZ_BEFORE_SEARCH = 45
        _TIER_DEVELOP = 40
        _TIER_POKE_PAD = 30
        _TIER_BUG_SET = 20
        _TIER_DEVELOP_AFTER_BCS = 15
        _TIER_ENERGY = 10

        # IS THERE A SEARCH BODY WAITING TO BE PAID FOR? (user, august 2026,
        # records/registro_005 step 50 -- episode 91176376 vs Alakazam, LOST).
        #
        # On that turn our Dipplin had been knocked out, so Fezandipiti ex's Flip
        # the Script was live on the bench, and in hand sat a Meowth ex whose
        # entire worth is its Last-Ditch Catch: bench it and search the deck for
        # a Supporter. The agent benched the Meowth (21500), searched out a Dawn,
        # played it -- and only THEN drew the three cards of Flip the Script.
        # Nothing in the scores says to do that: the ability was the highest
        # number on the menu (31700). The Pokemon PLAY simply lives in
        # `_TIER_DEVELOP` (40) and the ability in `_TIER_ENERGY` (10), and the
        # tier decides before the score does.
        #
        # The order is wrong because the two plays are not independent. Flip the
        # Script draws THREE cards for free; the search brings ONE, and charges a
        # two-prize body on the bench for it. Draw first and the search may
        # simply not be needed -- the Supporter we were digging for can be among
        # the three -- and when it still is, it is decided with three more cards
        # of information. Draw second and the Meowth is already sitting on the
        # bench either way. The ability cannot be deferred to make up for it: it
        # is free, ONCE PER TURN, and its condition (being knocked out last turn)
        # dies with the turn.
        #
        # This is the same sentence the Bug Catching Set already writes right
        # below ("with the 2 new cards in hand it is decided BETTER which body
        # goes down"), with a stronger reason: here the body costs two prizes.
        #
        # It PROMOTES the ability rather than demoting the Meowth, and that is
        # not cosmetic. Dropping the Meowth below `_TIER_DEVELOP` would put it
        # behind every other Pokemon in the menu, and with the bench at 4/5 an
        # Applin would take the last seat the search body needs. Drawing three
        # cards earlier cannot invalidate a later play; being outrun to a bench
        # seat can.
        #
        # Deck-agnostic: it names our own two cards and no matchup, no opposing
        # deck and no board shape. It fires only while BOTH are really on the
        # menu, so a Flip the Script that any of its own guards has silenced --
        # the deck-out brake, or the still-standing ordering vetoes that give the
        # turn to Unfair Stamp / Lillie's first -- keeps the old order and the
        # Meowth engine is decided by the rules that already govern it.
        _meowth_play_live = any(
            _fbs_o.type == OptionType.PLAY and _fbs_i < len(scores)
            and scores[_fbs_i] > 0
            and (lambda _c: _c is not None and _c.id == Meowth_ex)(
                get_card(obs, AreaType.HAND, _fbs_o.index, my_index))
            for _fbs_i, _fbs_o in enumerate(select.option))

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

        # Is the ability the parked attachment yields to REALLY going to be
        # played? `_attach_yields_to_teal_dance` is filled from
        # `_teal_dance_slots`, and that set is built from the MENU -- an ability
        # OFFERED, not an ability WANTED:
        #
        #     if _tds_o.type == OptionType.ABILITY and _tds_card.id == Teal_Mask_Ogerpon_ex:
        #         _teal_dance_slots.add((_tds_o.area, _tds_o.index))
        #
        # So when the Teal Dance is offered but VETOED -- the anti-overcharge
        # caps vs Crustle / Cubchoo / Cornerstone, which are the reason those
        # vetoes exist -- the attachment yields the way to a play that is never
        # going to happen. Capping its score to 7000 was harmless (the comment in
        # the ATTACH branch says so: "if the ability were vetoed by another route
        # the attachment is still playable"), but dropping it out of
        # `_TIER_ENERGY` into tier 0 is NOT: down there it loses by ORDER to
        # every tier-0 play, and the free, non-accumulating attachment of the
        # turn goes with it -- most visibly to a refill that then shuffles the
        # very energy into the deck.
        #
        # Same shape as `_stamp_worth_playing` ("it yielded the way to a card
        # that was no longer going to be played") and as the REVOKE ORDERING
        # VETOES block: a deference only stands while its beneficiary is alive.
        # With a live ability nothing changes -- the attachment stays parked next
        # to it and the score decides (Teal Dance 7500 > capped 7000). With none
        # alive, the board behaves like a board with no Teal Dance at all, which
        # is what it is.
        #
        # Census over 4000 self-play games (`log/hand_reset_gate/residual_census.py`):
        # the parked-with-nothing-to-yield-to attachment loses to a live refill
        # in 102 of 139.663 menus (0.073%), and in 75% of them the attachment is
        # in the real development band (5000/7000) rather than the near-worthless
        # one (10-20).
        _attach_park_beneficiary_alive = any(
            _apa_o.type == OptionType.ABILITY and _apa_i < len(scores)
            and scores[_apa_i] > 0
            and (lambda _c: _c is not None and _c.id in HAND_COST_ABILITY_IDS)(
                get_card(obs, _apa_o.area, _apa_o.index, my_index))
            for _apa_i, _apa_o in enumerate(select.option))

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
                if (_po_i in _attach_yields_to_teal_dance
                        and _attach_park_beneficiary_alive):
                    # A pure development attachment with a Teal Dance pending: it
                    # stays in tier 0 next to the ability so the score decides
                    # (Teal Dance 7500 > capped attachment 7000). Only while that
                    # ability is ALIVE -- see `_attach_park_beneficiary_alive`.
                    continue
                _play_order_tier[_po_i] = (
                    _TIER_KO_ENERGY if _po_is_ko_energy else _TIER_ENERGY)
            elif _po_o.type == OptionType.PLAY:
                _po_card = get_card(obs, AreaType.HAND, _po_o.index, my_index)
                if _po_card is not None:
                    _po_data = card_table.get(_po_card.id)
                    if (_po_card.id == Boss_Orders
                            and plan_of(ctx).gust_closes_it_now):
                        # THE GUST THAT CLOSES THE GAME IS THE SAME PLAY AS THE
                        # WINNING ATTACK (user, registro_013 step 126 vs the
                        # mirror, WON suboptimally). The score already said so
                        # (`winning_gust`, 20000), but Boss's is a PLAY and lived
                        # in tier 0, so a Bug Catching Set (tier BUG_SET) and a
                        # Teal Dance (tier ENERGY) beat it by ORDER and the turn
                        # went off building a board for a game that ended two
                        # actions later -- at mutual match point, with the
                        # opponent one prize away as well. Same tier as the
                        # winning finisher, for the same reason it was given to
                        # the retreat of `_win_ko_active_via_promote`: gust and
                        # attack are two halves of one play. It only fires when
                        # the plan's route IS the gust, so a Boss's played for
                        # value keeps its normal tier -- and only when the target
                        # dies to the energy ALREADY on the attacker
                        # (`gust_closes_it_now`): when the KO is one charge away,
                        # the charge goes first and the gust waits its turn
                        # (registro_012 step 227, the Myriad combo).
                        _play_order_tier[_po_i] = _TIER_WIN_ATTACK
                    elif (_po_card.id == Lanas_Aid
                            and plan_of(ctx).lethal_recovery):
                        # THE RECOVERY THAT WINS IS THE FIRST HALF OF THE SAME
                        # PLAY (user, episode 90115646 turn 10 vs Archaludon ex).
                        # Identical failure to the winning gust above, and it was
                        # measured the same way: the score said Lana's Aid, and
                        # an Applin in hand still went down first, because a
                        # Pokemon PLAY sits in `_TIER_DEVELOP` (40) and a
                        # Supporter PLAY in tier 0. Raising the score does not
                        # help -- the tier decides before it.
                        #
                        # Unlike the gust it takes the tier WITH a charge
                        # pending, and that is the point: `ROUTE_RECOVER` always
                        # needs one (`win_needs_charge`), and the charge cannot
                        # happen before the energy is in hand. So this play goes
                        # FIRST of the whole turn -- recovery, then the
                        # attachments (tier KO_ENERGY/ENERGY), then the attack.
                        _play_order_tier[_po_i] = _TIER_WIN_ATTACK
                    elif _po_card.id == Poke_Pad:
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
                        and scores[_po_i] >= 29000
                        and _meowth_play_live):
                    # THE DRAW GOES BEFORE THE SEARCH BODY (see
                    # `_meowth_play_live` in the block header): with a Meowth ex
                    # waiting in hand to be benched for its Last-Ditch Catch, the
                    # free three-card draw is cashed FIRST -- above
                    # `_TIER_DEVELOP`, where the Meowth play lives -- and only
                    # then is the search decided, with three cards more in hand
                    # and possibly no longer needed at all.
                    _play_order_tier[_po_i] = _TIER_FEZ_BEFORE_SEARCH
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
    # Threshold <= 10 = "critical deck", the same one as `deckout_brake_critical_deck`.
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
            # OUR FIRST TURN GOING FIRST behind a tough opener: the lone Meowth
            # ex stays in hand (see `_ft_hold_lone_meowth`). The turn being dead
            # is not a reason to hand over a 2-prize body when the bench costs
            # us nothing -- and the Supporter the fetch brings gets shuffled
            # away by tomorrow's Lillie's anyway.
            and not _ft_hold_lone_meowth
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
            # already have (`_meowth_fetch_loses_the_turn`).
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
                      and _sb_basic_i < 0
                      # OUR FIRST TURN GOING FIRST behind a tough opener: an
                      # empty bench is NOT a danger (nothing on their first
                      # turn reaches 140-210 HP), so the net must not spend the
                      # lone Meowth ex to fill it -- see `_ft_hold_lone_meowth`
                      # for the reasoning and for the Solrock exception. The
                      # Ultra Ball branch above is untouched: digging a real
                      # body is still better than ending.
                      and not (_sbc.id == Meowth_ex and _ft_hold_lone_meowth)):
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
    # `_matchup_allows_playing`, the net stops firing in those cases just as
    # before, but it DOES fire when the target fits the plan: an Ogerpon ex with
    # <2 in play is exactly what the matchup wants to search for, and the Ultra
    # Ball is on its item allowlist. The reason the old comment cited ("burning
    # 2 cards of the deck feeds the mill") was also inaccurate: the Ultra Ball's
    # cost comes from the HAND; only the fetched card comes from the deck.
    # Self-play gate vs deck/opponents/comfey.csv, 6000 games per branch:
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
            # `_matchup_allows_playing`). With no restrictive plan it filters
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
            # Same criterion as the fetch (`last_ditch_produces_nothing`) and as
            # `_ub_dig_meowth_gets_played`.
            _st_meowth_useful = (not state.supporterPlayed
                               and not meowth_ability_lock
                               and _meowth_ld_free
                               and field_counts.get(Meowth_ex, 0) < 2)
            _st_body_ok = lambda cid: (
                _st_plan_ok(cid)
                and (cid != Meowth_ex or _st_meowth_useful))
            # A BODY THAT ONLY SITS ON THE BENCH RESCUES NOTHING ONCE THE BENCH
            # ALREADY COVERS THE PROMOTION (user, registro_002 step 22 vs
            # Marnie, episode 90088766, WON in spite of this). The evolution
            # branch below was already sharpened to "it has to evolve TODAY"
            # ([[ultraball-solo-si-el-objetivo-se-usa-este-turno]]); the basic
            # branch kept the loose reading -- a bench with room plus any basic
            # in the deck -- and a basic put down this turn cannot attack and
            # cannot evolve either, so it buys exactly one bench slot for TWO
            # cards of hand. Here it dug an Applin (40 HP, no Dipplin anywhere)
            # onto a bench that already held Meowth ex and Teal Mask Ogerpon ex,
            # behind a 210 HP active, and paid with the hand's whole engine.
            # The rule the user states: the only reasons to pay for the Ultra
            # Ball are to be able to ATTACK, or to stop being one knockout away
            # from having no bodies. The first is not this net's business (it
            # only fires on turns with no attack); the second is the bench
            # depth. With `bench_count <= 1` a knockout on the active promotes
            # our last body and the next one loses the game, so a fresh body IS
            # the turn -- which is also the case the net was built on (the
            # crustle t2 board with a bench of one). From two bodies up, ending
            # the turn keeps the two cards, and they are worth more than the
            # slot. The item lock keeps the old reading: there the Ultra Ball is
            # use-it-or-lose-it and buying next turn is the whole point.
            _st_basic_useful = (bench_count < 5
                                and (bench_count <= 1 or _st_item_lock)
                                and any(
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
            # `_ub_cost_destroys_better_card`.
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

    # =================================================================
    # WHAT DIES WITH THE TURN IS PLAYED BEFORE THE ATTACK THAT CLOSES IT
    # (user, registro_008 step 111 vs Alakazam, WON with a mistake).
    #
    # State at step 111 (turn 8, our seat):
    #
    #     US                                   OPPONENT
    #     active  Fezandipiti ex 210 4e        active  Alakazam ex 140
    #     bench   Meganium, Meowth ex 10,      bench   Kadabra, 2x 70 HP basics,
    #             2x Teal Mask Ogerpon ex,             Fezandipiti ex
    #             Tapu Bulu
    #     hand    Boss's Orders, XEROSIC'S MACHINATIONS, Ultra Ball,
    #             Lana's Aid, Dawn        supporterPlayed: NO
    #     their hand: 19 cards
    #
    # The menu offered the five plays plus Cruel Arrow. The ranking was
    # attack 8600 (`_active_snipe_ko_now`, 8500 + 100 per prize) > Xerosic 7300
    # (`alakazam_priority_over_boss`) > Boss's 5240. The agent SNIPED and closed
    # the turn with a NINETEEN-card opposing hand untouched and the turn's
    # Supporter slot unspent. Xerosic's Machinations would have sent 16 of those
    # 19 cards to the discard FOREVER (`XEROSIC_HAND_CAP` = 3) -- and against
    # Alakazam that hand is also their damage: Powerful Hand hits for 20 per card.
    #
    # The mistake is not one of value, it is one of ORDER, and no score can fix
    # it: the two plays were never alternatives. A Supporter does not consume the
    # attack and the attack does not consume the Supporter -- but the attack ENDS
    # THE TURN, and the Supporter slot does NOT accumulate. Comparing 8600 with
    # 7300 answers "which of the two is worth more", which is the wrong question;
    # the right one is "which of the two can still be played afterwards", and the
    # answer is only ever the attack. Both lived in tier 0, so the score decided
    # and the free play was thrown away.
    #
    # The net fires only when the turn is ABOUT to close: the winner of the menu
    # (tier, score) is already the attack AND it is winning on score alone, in
    # tier 0. That last condition is what keeps the WINNING finisher out of
    # reach -- it lives in `_TIER_WIN_ATTACK` and nothing matters after the game
    # ends -- and it is written as `tier == 0` rather than as a re-reading of
    # `_active_attack_wins_now` so that every future reason to promote an attack
    # inherits the exemption. Any play parked in a higher tier keeps its turn
    # first and lets this net fire on a later menu. It lifts the best live
    # Supporter just above the attack and touches no tier. On the next menu
    # `supporterPlayed` is on, every Supporter vetoes itself and the attack fires
    # unchanged: the reorder costs the turn nothing.
    #
    # Two limits, both about not burning a card for nothing:
    #
    #   * the Supporter has to score ABOVE `SUPP_SCORE_LAST_RESORT_BAND`. At that
    #     height a scorer is saying "I have NO useful effect today, play me only
    #     because nothing else scores" -- and the slot being free is not a reason
    #     to spend the CARD, which keeps its value for tomorrow.
    #   * BOSS'S ORDERS is excluded. It is the one Supporter that rewrites the
    #     board the attack acts on: gusting changes WHO is in the active spot and
    #     therefore what the attack does, so gust and attack ARE alternatives and
    #     the score comparison between them is the right question. Its order
    #     against the attack is already decided where it belongs -- by its own
    #     ladder, and by `_TIER_WIN_ATTACK` when `gust_closes_it_now` makes the
    #     two halves of a single play.
    #
    # Deck-agnostic: it reads `cardType`, not a card list.
    #
    # -----------------------------------------------------------------
    # THE KO WINDOW IS THE OTHER SLOT THAT DOES NOT ACCUMULATE
    # (user, registro_016 step 150, turn 16 vs Hop's, LOST).
    #
    # The same turn, one card later. Our Teal Mask Ogerpon ex had been knocked
    # out during their turn 15, so the turn opened with the KO window OPEN: the
    # agent cashed Flip the Script (step 145) and the three cards it drew
    # included the UNFAIR STAMP. The menu that followed offered two Ultra Balls,
    # Lana's Aid, Lillie's Determination, the Stamp and Cruel Arrow, with their
    # hand on 6 cards -- above `STAMP_MIN_OP_HAND`, so the card rule said PLAY IT
    # (`_stamp_worth_playing`). The ranking was
    #
    #     attack 8600  >  STAMP 2200  >  Lillie's -1
    #
    # and the agent SNIPED. The turn closed with the Stamp in hand and, worse,
    # with the Supporter slot unspent too: that -1 on Lillie's is
    # `yields_to_unfair_stamp`, the ordering veto by which every Supporter steps
    # aside for a Stamp that is going to be played. Both cards were lost to the
    # same action.
    #
    # The Stamp is an ITEM, so the net above did not look at it -- and the reason
    # the net exists applies to it MORE strongly than to any Supporter. A
    # Supporter kept in hand is played tomorrow; the Stamp carries printed the
    # clause "only if any of your Pokemon were Knocked Out during your opponent's
    # last turn", so tomorrow it is ILLEGAL unless we are knocked out again --
    # which is the opponent's choice, not ours. The window does not accumulate
    # either, and it is rarer than the slot.
    #
    # So the candidate set is widened by exactly that property
    # (`KO_WINDOW_PLAY_IDS`, the printed clause -- not a matchup list, and it
    # holds against every opposing deck) and the free-slot guard moves INSIDE the
    # Supporter half: a window play has no slot to be free, and after a Supporter
    # has been played the Stamp still has to be rescued on the next menu.
    #
    # It needs no floor of its own: `_RULES_STAMP_PLAY` already vetoes the Stamp
    # to -1 whenever it is not worth its single copy (no disruption and no cheap
    # refill, a Lillie's with their hand short, or a Xerosic that goes first),
    # and a vetoed play never enters here. What the net adds is only the ORDER,
    # which is what no score could fix. The two live candidates never collide in
    # practice: while the Stamp is pending every Supporter of the deck is at -1
    # by its own yield, and when Xerosic takes the order it is the Stamp that is
    # at -1 -- so taking the highest-scoring candidate reproduces the order the
    # card rules already agreed on.
    #
    # Self-play gate, 8 matchups x 1200 games per branch (9600 per branch):
    # mean winrate 89.24% with the net vs 88.67% without it (+0.56). Nothing is
    # hurt beyond the noise (the worst cell is archaludon at -1.10, z=-1.42) and
    # the two clearest cells are marnie_grimmsnarl (+3.30, z=2.76) and dragapult
    # (+1.50, z=1.99). The rule stands on the game's own arithmetic -- the
    # attack ends the turn, the slot does not accumulate -- and the gate is only
    # there to rule out that it costs anything.
    # Golden corpus: ONE flip over the 13 records, the very decision above.
    # =================================================================
    if context == SelectContext.MAIN and scores:
        _sba_best_i = max(range(len(scores)),
                          key=lambda i: (_play_order_tier[i], scores[i]))
        if (select.option[_sba_best_i].type == OptionType.ATTACK
                and _play_order_tier[_sba_best_i] == 0):
            _sba_i = -1
            _sba_best = 0
            for _sbai, _sbao in enumerate(select.option):
                if _sbai >= len(scores) or _sbao.type != OptionType.PLAY:
                    continue
                if scores[_sbai] <= _sba_best:
                    continue
                _sbac = get_card(obs, AreaType.HAND, _sbao.index, my_index)
                if _sbac is None or _sbac.id == Boss_Orders:
                    continue
                if _sbac.id not in KO_WINDOW_PLAY_IDS:
                    # The Supporter half: the slot has to still be free, and
                    # the card has to have something to say today.
                    if state.supporterPlayed:
                        continue
                    _sbad = card_table.get(_sbac.id)
                    if _sbad is None or _sbad.cardType != CardType.SUPPORTER:
                        continue
                    if scores[_sbai] <= SUPP_SCORE_LAST_RESORT_BAND:
                        continue
                _sba_i = _sbai
                _sba_best = scores[_sbai]
            if _sba_i >= 0:
                scores[_sba_i] = scores[_sba_best_i] + 100

    # =================================================================
    # WHAT THE HAND PAYS GOES BEFORE THE HAND IS SHUFFLED AWAY
    # (user, registro_002 step 29, turn 2 vs Marnie, LOST).
    #
    # Board: active Teal Mask Ogerpon ex with the single Grass its own Teal Dance
    # had just attached, a SECOND Ogerpon ex on the bench with NO energy and its
    # Teal Dance still unused, and in hand one Basic {G} Energy plus the Lillie's
    # Determination that the Meowth ex's Last-Ditch Catch had fetched two actions
    # earlier. The ranking was
    #
    #     Lillie's 8000  >  Teal Dance 7500  >  attachment 7000
    #
    # and the agent REFILLED. Lillie's shuffles the hand into the deck, so the
    # only Grass on the table went back into the deck without ever reaching a
    # body: the bench Ogerpon spent the turn empty, the free draw of the ability
    # was never taken, and the turn's attachment had nothing left to attach.
    #
    # None of the three numbers is wrong, and that is the point. Teal Dance is at
    # 7500 because of the reserve band ("the Grass is being saved for the ACTIVE,
    # do not spend it on the bench"), the attachment at 7000 because it yielded to
    # that same Teal Dance, and Lillie's at 8000 because the Last-Ditch commitment
    # floors the Supporter it paid a 2-prize body for. The commitment says WHETHER
    # the Supporter is played, never WHEN -- and a reserve is a bet on a card
    # STAYING IN HAND, which is exactly the bet a hand reset cancels. Once the
    # refill is on the menu, "save it for later" buys nothing: there is no later.
    #
    # It cannot be fixed by score, because it is not a value question. Both plays
    # live in tier 0 -- Supporters always do, and a DEGRADED charging ability does
    # too (its `_TIER_ENERGY` promotion asks for >= 29000, the guard that stops it
    # from crushing Ripening Charge and which is deliberately NOT touched here) --
    # so within the tier the bigger number wins whatever the numbers mean. The
    # relation between them is ORDER, and this is where order is decided.
    #
    # The fix is a SWAP, not a boost: the hand-paying plays are lifted just above
    # the refill by a SHARED delta, so their order among themselves is untouched
    # and everything else keeps its place. The refill drops exactly one notch and
    # wins the next menu -- with the ability spent, its slot still free and one
    # card fewer to shuffle away.
    #
    # Deck-agnostic on both halves, and read off the PRINTED TEXT rather than off
    # a card list (see `HAND_RESET_PLAY_IDS` / `HAND_COST_ABILITY_IDS`): any
    # refill that empties the hand (Lillie's, Lacey, Judge, Carmine, the Unfair
    # Stamp) yields to any ability that pays with a card from it (Teal Dance,
    # Ripening Charge, Inferno Fandango...).
    #
    # It does NOT invert the opposite order, which is also right: an ability that
    # PRODUCES cards (Flip the Script's 3-card draw) goes AFTER the refill, since
    # drawing first only feeds those cards back into the deck. That half already
    # exists as `_lillie_blocks_fez_ability` / `_stamp_blocks_supp_chain`, and the
    # two never collide -- the discriminator is which way the cards flow.
    #
    # A VETOED ability (<= 0) is left alone: there the scorer is saying the
    # attachment itself is wrong (the anti-overcharge caps), not that the card is
    # being saved, and shuffling it away costs nothing.
    # =================================================================
    if context == SelectContext.MAIN and scores:
        _hr_reset = SCORE_VETO
        for _hr_i, _hr_o in enumerate(select.option):
            if (_hr_i >= len(scores) or scores[_hr_i] <= 0
                    or _hr_o.type != OptionType.PLAY
                    or _play_order_tier[_hr_i] != 0):
                continue
            _hr_c = get_card(obs, AreaType.HAND, _hr_o.index, my_index)
            if _hr_c is not None and _hr_c.id in HAND_RESET_PLAY_IDS:
                _hr_reset = max(_hr_reset, scores[_hr_i])
        if _hr_reset > 0:
            _hr_payers = []
            for _hr_i, _hr_o in enumerate(select.option):
                if (_hr_i >= len(scores) or scores[_hr_i] <= 0
                        or _hr_o.type != OptionType.ABILITY
                        or _play_order_tier[_hr_i] != 0):
                    continue
                _hr_c = get_card(obs, _hr_o.area, _hr_o.index, my_index)
                if _hr_c is not None and _hr_c.id in HAND_COST_ABILITY_IDS:
                    _hr_payers.append(_hr_i)
            if _hr_payers:
                _hr_delta = _hr_reset + 1 - min(scores[_i] for _i in _hr_payers)
                if _hr_delta > 0:
                    for _hr_i in _hr_payers:
                        scores[_hr_i] += _hr_delta

    desc_indices = [i for i, _ in sorted(
        enumerate(scores),
        key=lambda x: (_play_order_tier[x[0]], x[1]),
        reverse=True)]
    if DEBUG_DECISIONS and context == SelectContext.MAIN:
        # The sentence the turn is under, printed BEFORE the ranking: reading a
        # trace without it means guessing whether a play lost because its score
        # was wrong or because the turn was about something else entirely.
        import sys as _sys_plan
        print(f"[DBG] plan={plan_of(ctx)}", file=_sys_plan.stderr)
    _debug_log_decision(context, select, scores, obs, my_index)

    if context == SelectContext.SETUP_ACTIVE_POKEMON and desc_indices:
        # The starting active is placed FACE DOWN: `my_state.active` holds a
        # None and the card tracking skips it, so the bench selection that comes
        # right afterwards cannot see which body we sent to the active spot. We
        # write it down here, which is the only moment when we know it, so that
        # the "a maximum of 2 in play" cap of SETUP_BENCH_POKEMON counts the
        # active as well (with no Tapu Bulu in hand the starter is a Teal Mask
        # Ogerpon ex, and two more on the bench would make three).
        _sa_card = get_card(obs, AreaType.HAND,
                            select.option[desc_indices[0]].index, my_index)
        AGENT_STATE.setup_active_id = _sa_card.id if _sa_card is not None else None

    if context == SelectContext.SETUP_BENCH_POKEMON:
        wanted = [i for i in desc_indices if scores[i] >= 0]

        if len(wanted) < select.minCount:
            wanted = desc_indices[:select.minCount]
        return wanted[:select.maxCount]

    if _vetoed_stadium_idxs:
        desc_indices = [i for i in desc_indices if i not in _vetoed_stadium_idxs]

    return desc_indices[:select.maxCount]


__all__ = ['finalizar']
