"""Scoring of the `PLAY` options.

The `o.type == OptionType.PLAY` branch of the `agent()` chain, extracted
VERBATIM. It unpacks from the context the 87 fields it reads and returns the
5 it reassigns; the rest stay as they were, just like before.
"""

from cg.api import AreaType, CardType, EnergyType
from ptcg.calc.card import get_card, prize_count
from ptcg.calc.damage import _powerful_hand_proyectado, _ventana_de_regalo
from ptcg.calc.energy import _grass_mult
from ptcg.cards.groups import GT_PLAY_BASICO_BONUS
from ptcg.cards.ids import Applin, Basic_Grass_Energy, Bayleef, Boss_Orders, Budew, Bug_Catching_Set, CUBCHOO_ALLOWED_PLAY_IDS, Chikorita, DECK_ITEM_IDS, Dawn, Dipplin, Dragapult_ex, Fezandipiti_ex, Forest_of_Vitality, Grand_Tree, Hydrapple_ex, Lanas_Aid, Lillie_Determination, Meganium, Meowth_ex, Night_Stretcher, OUR_EX_IDS, Pinsir, Poke_Pad, RETREAT_COST, SCORE_DEVELOP_BASE, SCORE_FORBID, SCORE_ITEM_BASE, SCORE_VETO, TAPU_WAIT_FOR_ITEMS_SCORE, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball, Unfair_Stamp, Xerosic_Machinations
from ptcg.cards.tables import card_table
from ptcg.decision.bug_catching_set import _score_bug_catching_set_play
from ptcg.decision.disruption import _score_unfair_stamp_play, _score_xerosic_play
from ptcg.decision.poke_pad import _score_poke_pad_play
from ptcg.decision.supporters import _score_dawn_play, _score_lanas_aid_play
from ptcg.decision.ultra_ball import _counter_stadium_urgent
from ptcg.state.agent_state import AGENT_STATE
from ptcg.state.zones import ZONE_DECK


def puntuar(tc, o, score):
    """Returns the score of `o`. It may return `_SALTAR`."""
    _active_already_kos = tc._active_already_kos
    _active_cant_attack_this_turn = tc._active_cant_attack_this_turn
    _active_doomed_real = tc._active_doomed_real
    _active_ready_attacker = tc._active_ready_attacker
    _alk_ld_engine_alive = tc._alk_ld_engine_alive
    _ara_act = tc._ara_act
    _bcs_playable_in_hand = tc._bcs_playable_in_hand
    _best_supp_in_hand_val = tc._best_supp_in_hand_val
    _best_supp_in_deck_id = tc._best_supp_in_deck_id
    _best_supp_in_deck_val = tc._best_supp_in_deck_val
    _deny_evo_via_boss = tc._deny_evo_via_boss
    _prize_mismatch_matchup = tc._prize_mismatch_matchup
    _dragapult_no_tapu = tc._dragapult_no_tapu
    _festival_lead_hostil = tc._festival_lead_hostil
    _gt_planes = tc._gt_planes
    _gt_quiere_basico = tc._gt_quiere_basico
    _gt_root_in_play = tc._gt_root_in_play
    _gt_basics_ranking = tc._gt_basics_ranking
    _gt_vetoes_ex_stage = tc._gt_vetoes_ex_stage
    _gust_2prize_via_boss = tc._gust_2prize_via_boss
    _lucario_other_sac_available = tc._lucario_other_sac_available
    _lucario_riolu_gust = tc._lucario_riolu_gust
    _lucario_sac_pivot = tc._lucario_sac_pivot
    _meowth_antidonk_now = tc._meowth_antidonk_now
    _meowth_devel_lillie = tc._meowth_devel_lillie
    _meowth_fetch_loses_the_turn = tc._meowth_fetch_loses_the_turn
    _meowth_fetch_redundante = tc._meowth_fetch_redundante
    _meowth_fetch_already_in_hand = tc._meowth_fetch_already_in_hand
    _meowth_immune_boss_engine = tc._meowth_immune_boss_engine
    _meowth_ld_free = tc._meowth_ld_free
    _no_second_attacker_path = tc._no_second_attacker_path
    _our_first_turn = tc._our_first_turn
    _ready_attacker_count = tc._ready_attacker_count
    _score_boss_orders_play = tc._score_boss_orders_play
    _score_forest_of_vitality_play = tc._score_forest_of_vitality_play
    _score_lillie_determination_play = tc._score_lillie_determination_play
    _score_night_stretcher_play = tc._score_night_stretcher_play
    _score_ultra_ball_play = tc._score_ultra_ball_play
    _stamp_blocks_supp_chain = tc._stamp_blocks_supp_chain
    _supp_values = tc._supp_values
    _tapu_sac_priority = tc._tapu_sac_priority
    _win_via_boss_gust = tc._win_via_boss_gust
    active_hp_ratio = tc.active_hp_ratio
    active_ko_likely = tc.active_ko_likely
    b = tc.b
    bench_count = tc.bench_count
    bp = tc.bp
    card = tc.card
    ctx = tc.ctx
    data = tc.data
    field_counts = tc.field_counts
    hand_counts = tc.hand_counts
    has_hydrapple = tc.has_hydrapple
    itchy_pollen_active = tc.itchy_pollen_active
    meowth_ability_lock = tc.meowth_ability_lock
    my_index = tc.my_index
    my_prize = tc.my_prize
    my_state = tc.my_state
    neutralization_zone_active = tc.neutralization_zone_active
    obs = tc.obs
    op_bench_snipe_threat = tc.op_bench_snipe_threat
    op_has_ability_immune_active = tc.op_has_ability_immune_active
    op_has_ex_immune_active = tc.op_has_ex_immune_active
    op_has_ex_immune_bench = tc.op_has_ex_immune_bench
    op_has_froslass = tc.op_has_froslass
    op_has_mega_starmie_active = tc.op_has_mega_starmie_active
    op_is_aggro_deck = tc.op_is_aggro_deck
    op_is_alakazam_deck = tc.op_is_alakazam_deck
    op_is_beedrill_deck = tc.op_is_beedrill_deck
    op_is_comfey_deck = tc.op_is_comfey_deck
    op_is_cubchoo_deck = tc.op_is_cubchoo_deck
    op_is_dragapult_dusknoir = tc.op_is_dragapult_dusknoir
    op_is_drednaw_deck = tc.op_is_drednaw_deck
    op_is_fire_deck = tc.op_is_fire_deck
    op_is_greninja_deck = tc.op_is_greninja_deck
    op_is_iron_thorns_deck = tc.op_is_iron_thorns_deck
    op_is_lucario_deck = tc.op_is_lucario_deck
    op_is_mirror = tc.op_is_mirror
    op_is_sylveon_deck = tc.op_is_sylveon_deck
    op_prize = tc.op_prize
    op_state = tc.op_state
    pid = tc.pid
    stadium_id = tc.stadium_id
    state = tc.state
    watchtower_in_play = tc.watchtower_in_play

    try:
        card = get_card(obs, AreaType.HAND, o.index, my_index)
        if card is None:
            score = SCORE_VETO
        else:
            data = card_table[card.id]
            if data.cardType == CardType.POKEMON:
                score = SCORE_DEVELOP_BASE
        
                _block_4th_ex = False
                if ((AGENT_STATE.op_is_crustle_deck or AGENT_STATE.op_is_cornerstone_deck)
                        and card.id in OUR_EX_IDS
                        # Meowth ex is UTILITY (Last-Ditch searches for a Boss's to
                        # gust the bench when the active is immune): it does
                        # not count as a 4th ex attacker and is not blocked.
                        and not (card.id == Meowth_ex
                                 and _meowth_immune_boss_engine)
                        # A Fezandipiti ex with Flip the Script ALIVE
                        # (ko_last_turn) is not a "4th attacker" either: putting it down
                        # draws 3 cards THIS turn (registro_008 step 74 vs
                        # Mega Starmie with a tech Cornerstone: the 4th-ex block
                        # crushed the 22000 of the refill and the draw
                        # was lost). Without the ability alive, the veto stands.
                        and not (card.id == Fezandipiti_ex
                                 and AGENT_STATE.ko_last_turn)):
                    _ex_in_play = sum(field_counts.get(_ex_id, 0)
                                      for _ex_id in OUR_EX_IDS)
                    if _ex_in_play >= 3:
                        _block_4th_ex = True
        
                # A REDUNDANT ex BODY WITH A LETHAL POWERFUL HAND (user,
                # registro_010 step 150 vs Alakazam, LOST -- log
                # 88903365). vs Alakazam the opponent's finisher is not their active:
                # it is Boss's Orders (3 copies in their deck) + Powerful Hand
                # (20 x their hand, and their hand GROWS). When that projected damage
                # already KILLS in one hit the body we were about to put down and the
                # opponent only needs 2 prizes to close, a DUPLICATE ex on the bench
                # is not development: it is a finisher served up. In the record
                # we put down a THIRD Teal Mask Ogerpon ex (210 HP) with the opposing
                # hand at 12 (projected Powerful Hand 280); on the following
                # turn they gusted a benched Ogerpon ex and knocked it out with
                # 220 for their last 2 prizes.
                #
                # DELIBERATELY narrow scope, so as not to touch normal
                # development in the matchup:
                #   * only REDUNDANT COPIES (`field_counts[card.id] >= 1`):
                #     the FIRST copy of any ex is still put down -- it may
                #     be the only attacker or the engine of the turn;
                #   * only with `op_prize <= 2`: if the opponent is 3+
                #     prizes away, one more target does not close the game;
                #   * only if Powerful Hand FINISHES that body (>= printed HP);
                #     and Fezandipiti ex with Flip the Script alive is exempt
                #     (it draws 3 THIS turn), as in the block above.
                # The "search already paid for" overrides (`_ub_meowth_pending`
                # / `_ub_fez_pending`) come LATER in the branch, so a
                # body already dug out with Ultra Ball is never left dead in
                # hand by this veto.
                _alk_ex_redundante_letal = False
                if (op_is_alakazam_deck and card.id in OUR_EX_IDS
                        and op_prize <= 2
                        and field_counts.get(card.id, 0) >= 1
                        and not (card.id == Meowth_ex
                                 and (_alk_ld_engine_alive
                                      or _meowth_immune_boss_engine))
                        and not (card.id == Fezandipiti_ex
                                 and AGENT_STATE.ko_last_turn)):
                    _alk_body_hp = getattr(data, 'hp', 0) or 0
                    if (_alk_body_hp and _powerful_hand_proyectado(
                            getattr(op_state, 'handCount', 0))
                            >= _alk_body_hp):
                        _alk_ex_redundante_letal = True
        
                if _block_4th_ex or _alk_ex_redundante_letal:
                    score = SCORE_VETO
                elif card.id == Chikorita:
        
                    _meg_line_count = field_counts[Chikorita] + field_counts[Bayleef] + field_counts[Meganium]
                    _max_meg_line = 2 if (AGENT_STATE.op_is_crustle_deck or AGENT_STATE.op_is_cornerstone_deck) else 1
                    if _meg_line_count >= _max_meg_line:
                        score = SCORE_VETO
                    else:
                        _forest_avail = AGENT_STATE.forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1
        
                        if (op_has_mega_starmie_active and
                                not (_forest_avail and hand_counts.get(Bayleef, 0) >= 1)):
                            score = SCORE_VETO
                        else:
                            score = 21500
                            if op_is_mirror or op_is_fire_deck or AGENT_STATE.op_is_crustle_deck:
                                score = 21700
                            elif op_is_aggro_deck or op_is_beedrill_deck:
                                score = 21700
                            elif op_is_greninja_deck or op_is_dragapult_dusknoir:
                                score = 21600
        
                            if _forest_avail and hand_counts.get(Bayleef, 0) >= 1:
                                score += 200
                elif card.id == Applin:
        
                    _drag_snipe_charged = False
                    for _dp in (([op_state.active[0]]
                                 if (op_state.active and op_state.active[0] is not None)
                                 else [])
                                + [b for b in op_state.bench if b is not None]):
                        if _dp.id == Dragapult_ex:
                            if (EnergyType.FIRE in _dp.energies and
                                    EnergyType.PSYCHIC in _dp.energies):
                                _drag_snipe_charged = True
                                break
                    _op_active_free_retreat = bool(
                        op_state.active and op_state.active[0] is not None and
                        (op_state.active[0].id == Budew or
                         RETREAT_COST.get(op_state.active[0].id, 1) == 0))
                    _dragapult_snipe_setup = _drag_snipe_charged and _op_active_free_retreat
                    _applin_evolvable_now = (
                        AGENT_STATE.forest_in_play and hand_counts.get(Dipplin, 0) >= 1)
        
                    # PHASE E3 (Marnie plan, section 4): an Applin JUST
                    # put down has 40 HP and no ability, so it does not
                    # pay the Froslass drip -- but the automatic snipe
                    # (30) plus ONE counter moved by Adrena-Brain already
                    # kill it. Leaving it loose on the bench for a turn is a prize
                    # GIVEN AWAY (game 3). Forest of Vitality allows evolving
                    # Grass Pokemon on the turn they are played, so the
                    # whole line fits in one turn: the rule is to KEEP the
                    # pieces until they can be chained, not to put the basic down
                    # "to start building". Same shape as the Mega
                    # Starmie veto further down and as the Dragapult one right
                    # next to it; what changes is that the threshold comes from the GIFT
                    # WINDOW and not from a list of decks. Without Munkidori on
                    # the field `_op_movable_dmg` is 0, the bare snipe (30) does not
                    # reach the 40 HP and the rule does not switch on.
                    _applin_hp_impreso = getattr(
                        card_table.get(Applin), 'hp', 0) or 0
                    _applin_regalado = (
                        AGENT_STATE._op_movable_dmg > 0
                        and _applin_hp_impreso > 0
                        and _applin_hp_impreso <= _ventana_de_regalo(
                            card, False, AGENT_STATE._op_bench_snipe_dmg))
        
                    if bench_count >= 5:
                        score = SCORE_VETO
                    elif _dragapult_snipe_setup and not _applin_evolvable_now:
                        score = SCORE_VETO
                    elif _applin_regalado and not _applin_evolvable_now:
                        score = SCORE_VETO
                    elif (op_is_cubchoo_deck and
                            field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0)
                            + field_counts.get(Hydrapple_ex, 0) >= 1):
                        # Cubchoo matchup (user): only ONE
                        # Applin->Dipplin->Hydrapple ex line in play at a time. If there is
                        # already a member of the line on the board, do not put another Applin down.
                        score = SCORE_VETO
                    else:
                        _forest_avail = AGENT_STATE.forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1
        
                        if (op_has_mega_starmie_active and
                                not (_forest_avail and hand_counts.get(Dipplin, 0) >= 1)):
                            score = SCORE_VETO
                        else:
                            score = 21200
        
                            if field_counts[Applin] >= 1:
                                score = 20800
        
                            if _forest_avail and hand_counts.get(Dipplin, 0) >= 1:
                                score += 200
        
                            if (op_is_fire_deck or op_is_aggro_deck) and not has_hydrapple:
                                score += 300
        
                            if op_bench_snipe_threat and not _forest_avail:
                                if field_counts[Applin] + field_counts[Dipplin] + field_counts[Hydrapple_ex] >= 1:
                                    score = 18000
        
                                elif hand_counts.get(Dipplin, 0) == 0:
                                    score -= 500
                elif card.id == Teal_Mask_Ogerpon_ex:
                    _meg_line_present = (
                        AGENT_STATE.meganium_in_play or
                        field_counts.get(Bayleef, 0) >= 1 or
                        field_counts.get(Chikorita, 0) >= 1)
                    if (AGENT_STATE.op_is_crustle_deck or AGENT_STATE.op_is_cornerstone_deck) and \
                            not AGENT_STATE.op_has_mega_kangaskhan and \
                            field_counts[card.id] >= 2:
        
                        score = SCORE_VETO
                    elif bench_count >= 5:
                        score = SCORE_VETO
                    elif field_counts[card.id] >= 2:
        
                        if hand_counts.get(Basic_Grass_Energy, 0) >= 1:
                            score = 20500
                        elif AGENT_STATE.op_has_mega_kangaskhan and _meg_line_present:
        
                            score = 20500
                        else:
                            score = SCORE_VETO
                    else:
                        score = 21000
                elif card.id == Meowth_ex:
        
                    if meowth_ability_lock:
                        # Team Rocket's Watchtower cancels the ability of
                        # Meowth ex (a Colorless Pokemon): do not bench it.
                        score = SCORE_VETO
                    elif _stamp_blocks_supp_chain:
                        # SEQUENCING ERROR (user, registro_004 p34 vs Mega
                        # Starmie ex; registro_008 step 90 vs Alakazam): with an
                        # Unfair Stamp (an ACE SPEC Item) PLAYABLE this turn
                        # (`_stamp_blocks_supp_chain` = we were knocked out last
                        # turn + the Stamp is still in hand), do NOT put Meowth ex down
                        # to search for ANY Supporter: the Stamp SHUFFLES THE WHOLE
                        # hand into the deck, so the Supporter the
                        # Last-Ditch Catch brings is lost immediately and we have also
                        # exposed a 2-prize body on the bench. The
                        # Stamp itself already refills (we draw 5) and disrupts (the
                        # opponent only draws 2), so the fetch is redundant.
                        # Correct order: items -> Unfair Stamp -> and only
                        # AFTERWARDS, if needed, put Meowth ex down (the Stamp is an
                        # Item: once played it leaves the hand, the flag becomes
                        # False and the Meowth chain is re-enabled).
                        #
                        # POSITION (step 90, WON suboptimally): this veto
                        # used to sit BELOW the Boss's-via-Meowth engines
                        # (_win_via_boss_gust/_gust_2prize_via_boss 22500,
                        # _deny_evo_via_boss 22000, _meowth_immune_boss_engine
                        # 22000), exempt on the argument that they "search for
                        # a Boss's that IS PLAYED this turn, it is not shuffled". That
                        # argument is FALSE: `_RULES_BOSS_PLAY` vetoes the Boss's
                        # with `cede_a_unfair_stamp` (and the same is done by the
                        # Xerosic/Lillie's/Dawn/Lana's scorers: ALL the
                        # `_SUPP_PLAY_IDS` yield to the Stamp), so the fetched Boss's
                        # canNOT be played this turn and on top of that gets
                        # shuffled into the deck. With `_gust_2prize_via_boss` active
                        # (a 210 HP Fezandipiti ex on the opposing bench, finishable
                        # by Wood Hammer) the agent put Meowth ex down, dug out
                        # the Boss's, played the Stamp -- which returned the Boss's
                        # to the deck -- and only recovered it by LUCK among the 5
                        # cards drawn. That is why the veto goes ABOVE everything:
                        # while the Stamp is still playable no Supporter
                        # fetch can pay off. Deck-agnostic: it names no
                        # opposing cards or archetypes.
                        score = SCORE_VETO
                    elif ((_win_via_boss_gust or _gust_2prize_via_boss)
                            and hand_counts.get(Boss_Orders, 0) == 0
                            and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Boss_Orders, {}).get(ZONE_DECK, 0) > 0
                            and field_counts[card.id] < 2
                            and _meowth_ld_free
                            and bench_count < 5):
                        # Winning Boss's engine via Meowth ex (user, registro_011
                        # step 148 vs Dragapult ex, WON): play Meowth ex
                        # so that Last-Ditch Catch searches for Boss's Orders (which
                        # is in the DECK, not in hand) and finish by gusting+
                        # knocking out (win_via_boss_gust: e.g. 1 prize away from
                        # winning, gust a fragile basic from the bench -- a 70 HP Dreepy --
                        # that the active KNOCKS OUT, instead of attacking the opposing active
                        # which does NOT die). It is allowed even with ONE Meowth ex already
                        # in play (field < 2) AS LONG AS its Last-Ditch is still
                        # available this turn (`_meowth_ld_free`): the benched Meowth
                        # from previous turns has already spent its ability, but
                        # a NEW one from hand searches again. It used to require
                        # `field_counts == 0`, so with a Meowth already on the
                        # bench this winning line was invisible and the agent
                        # attacked without knocking out.
                        score = 22500
                    elif (_deny_evo_via_boss
                            and hand_counts.get(Boss_Orders, 0) == 0
                            and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                                Boss_Orders, {}).get(ZONE_DECK, 0) > 0
                            and field_counts[card.id] < 2
                            and _meowth_ld_free
                            and bench_count < 5
                            and not state.supporterPlayed):
                        # VALUE Boss's engine via Meowth ex (Meowth engine
                        # plan, improvement A): the opponent has a charged
                        # pre-evolution of an ex line on the bench (Gabite/Duraludon/
                        # Morgrem...) that we KNOCK OUT after gusting it, and the
                        # Boss's is in the DECK. The in-hand machinery
                        # (`_boss_deny_evo`) requires a Boss's in hand and the veto
                        # below (`_active_ready_attacker`) killed the
                        # generic fallback: there was NO path at all and the
                        # agent attacked the wall letting the threat
                        # evolve. Put Meowth down -> Last-Ditch searches for Boss's
                        # (1280) -> gust+knock out the pre-evolution. 22000: below
                        # the winning finisher (22500), above devel-lillie and
                        # the dead turn (21800). With a Boss's ALREADY in hand it does not
                        # fire (the in-hand engine plays it directly without spending the Meowth body).
                        score = 22000
                    elif _meowth_immune_boss_engine:
                        # Boss's engine vs an IMMUNE ACTIVE (user: Hydrapple ex vs
                        # an active Cornerstone Mask Ogerpon ex + Mega Lucario ex
                        # on the bench): the opposing active CANCELS our attacker
                        # (Cornerstone cancels abilities; Crustle/Sylveon cancel
                        # ex; the Neutralization Zone cancels ex vs 1-prize) -> the
                        # attack does 0. With a Boss's in the DECK (not in hand),
                        # put Meowth ex down so Last-Ditch Catch searches for it,
                        # gust an ATTACKABLE target from the bench and finish it,
                        # instead of attacking the immune wall for 0. 22000: the level of
                        # the other Boss's engines, above refill/dead turn.
                        # With a Boss's ALREADY in hand it does not fire (it is played directly).
                        # Deck-agnostic.
                        score = 22000
                    elif (field_counts[card.id] < 2
                            and _meowth_ld_free
                            and bench_count < 5
                            and not state.supporterPlayed
                            and hand_counts.get(Lillie_Determination, 0) == 0
                            and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                                Lillie_Determination, {}).get(ZONE_DECK, 0) > 0
                            and (len(my_state.hand) if my_state.hand else 0) <= 2
                            and _ready_attacker_count <= 1
                            and _ara_act is not None
                            and _ara_act.id not in OUR_EX_IDS
                            and prize_count(_ara_act) == 1
                            and (not op_has_froslass)):
                        # Meowth -> Lillie's refill engine on a POOR BOARD
                        # (user, registro_006 step 57 vs Alakazam, WON): the
                        # active is a 1-prize CHIP attacker (Dipplin) that
                        # CAN knock out the opposing active but is fragile, there is NO
                        # READY attacker on the bench (_ready_attacker_count
                        # <= 1, only the active itself) and the hand is minimal
                        # (<= 2 cards). Even though the active can attack/knock out,
                        # putting Meowth ex down does NOT consume the attack: the Basic is
                        # benched, Last-Ditch Catch brings Lillie's, the hand is
                        # refilled (draw 6) to assemble a SECOND attacker and AFTERWARDS
                        # we attack in the same turn (we do not lose the KO). Unlike
                        # the generic refill below (which requires field==0 and the active
                        # NOT to knock out), here it is allowed with ONE Meowth already on the
                        # bench (field<2, with its Last-Ditch still free) and EVEN IF
                        # the active knocks out. Strict gates (hand<=2, the only attacker
                        # being the active 1-prize chip body, no Froslass) so as not
                        # to expose a 2nd Meowth (2 prizes) except on a really poor
                        # board. Deck-agnostic.
                        score = 21600
                    elif (field_counts[card.id] < 2
                            and _meowth_ld_free
                            and bench_count <= 1
                            and not state.supporterPlayed
                            and not meowth_ability_lock
                            and not op_has_froslass
                            and hand_counts.get(Lillie_Determination, 0) == 0
                            and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                                Lillie_Determination, {}).get(ZONE_DECK, 0) > 0
                            and _active_ready_attacker
                            and _ready_attacker_count <= 1
                            and my_prize >= 3
                            and _no_second_attacker_path
                            and _active_doomed_real):
                        # Meowth -> Lillie's refill engine WITH NO spare
                        # attacker (user, registro_006 step 78 vs Mega Lucario
                        # ex): the active (Ogerpon ex) CAN attack but does NOT knock out
                        # and the opponent finishes it next turn (the REAL finisher, not
                        # the active_ko_likely heuristic that underestimates Mega
                        # Lucario); the bench has NO ATTACKER (only a
                        # utility basic) and from hand there is NO way to
                        # assemble a 2nd attacker this turn (neither a playable basic
                        # attacker nor a legal evolution: the Hydrapple/Dipplin line
                        # is stuck without an Applin/Dipplin in play). Putting
                        # Meowth ex down does NOT consume the attack: Last-Ditch Catch brings
                        # Lillie's, the hand is refilled (draw 6) to find
                        # attacker pieces and AFTERWARDS we attack/retreat in the same
                        # turn. It is allowed with ONE Meowth already on the bench (field<2,
                        # with its Last-Ditch free) and EVEN IF the active is an ex.
                        # Strict gates (the only attacker being the doomed active,
                        # no path to a 2nd attacker, not in our own finishing range,
                        # no Froslass) so as not to expose a 2-prize body
                        # except on a really poor board. `bench_count <= 1`:
                        # only on a VERY thin board (<=1 body on the bench) where
                        # digging is necessary; with 2+ bodies we prefer the clean
                        # retreat-sacrifice of the mismatch ([[descuadre-generalizado-ex-...]])
                        # without committing Lillie's or exposing a 2nd Meowth.
                        # Deck-agnostic.
                        score = 21550
                    elif (_active_ready_attacker
                            and field_counts[card.id] == 0
                            and bench_count < 5
                            and not state.supporterPlayed
                            and hand_counts.get(Lillie_Determination, 0) == 0
                            and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                                Lillie_Determination, {}).get(ZONE_DECK, 0) > 0
                            and (len(my_state.hand) if my_state.hand else 0) <= 4
                            and _ready_attacker_count <= 2
                            and not (AGENT_STATE.plan.attacker == 0
                                     and AGENT_STATE.plan.remain_hp is not None
                                     and AGENT_STATE.plan.remain_hp <= 0)
                            and not meowth_ability_lock
                            and (not op_has_froslass
                                 or _ready_attacker_count <= 1)):
                        # Rule (user, logs 86592502 turn 9 vs Archaludon ex,
                        # 86593647 turn 4 vs Mega Starmie ex and 86699707 step 51
                        # vs Marnie's Grimmsnarl ex, all LOST):
                        # an EXCEPTION to the veto below. Even if the active can ALREADY
                        # attack, if the HAND is WEAK (<=4 cards) and there is still a
                        # Lillie's Determination left in the DECK, putting Meowth ex down so
                        # that its Last-Ditch Catch ability brings Lillie's and
                        # playing it (shuffle the hand and draw 6) gives MANY more play
                        # and attack options than playing a REDUNDANT body (a 2nd
                        # Teal Mask Ogerpon ex, 21000) or throwing a WEAK non-lethal
                        # attack (Dipplin ~1100) at a 330 HP wall. It requires that
                        # there be a ready attacker but FEW (<=2: if there are already many
                        # ready there is no need to refill), that the active's attack
                        # NOT be lethal (if it knocks out, we attack and take the prize),
                        # that no Supporter has been played and that its ability is not
                        # cancelled (Watchtower always vetoes). Froslass also
                        # vetoes EXCEPT when our ONLY ready attacker is the
                        # active itself (_ready_attacker_count <= 1) and its attack
                        # is NOT lethal: there is no real pressure there (a chip vs the wall)
                        # and digging for Lillie's is worth more than the risk of benching
                        # Meowth ex against Froslass (case 86699707: an active Dipplin
                        # chipping vs a 320 HP Grimmsnarl ex). It beats the
                        # redundant body (21500 > 21000) so Meowth ex wins.
                        score = 21500
                    elif (_active_ready_attacker
                            and field_counts[card.id] == 0
                            and bench_count <= 1
                            and bench_count < 5
                            and (active_ko_likely or active_hp_ratio <= 0.2)
                            and not meowth_ability_lock
                            and not state.supporterPlayed
                            and hand_counts.get(Lillie_Determination, 0) == 0
                            and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                                Lillie_Determination, {}).get(ZONE_DECK, 0) > 0):
                        # An EXCEPTION to the veto below (user, registro_014 step
                        # 107, vs Marnie): the active was a Teal Mask Ogerpon
                        # ex at 10/210 HP -- it falls to the first hit -- and the
                        # bench had ONE single Pokemon. Even though the active is a
                        # READY attacker, putting Meowth ex down here is free: it does not
                        # consume the attack (the Basic is benched and we attack
                        # afterwards in the same turn) and it chains Last-Ditch
                        # Catch -> Lillie's -> rebuild the hand, giving a spare body
                        # for when the active falls and many more
                        # play options. The veto below (log 86511741 vs
                        # Mega Abomasnow) is meant for a HEALTHY active with a
                        # developed bench, where the 2-prize body does not pay off;
                        # with the active doomed and the bench empty
                        # the situation is reversed. It is scored below the
                        # full refill (21500) and above the attack.
                        score = 21400
                    elif (_active_ready_attacker
                            and field_counts[card.id] == 0):
                        # Rule (user, log 86511741 step 57, vs Mega Abomasnow
                        # ex, LOST): if our ACTIVE is already an attacker
                        # READY to attack this turn, we do NOT put Meowth ex down
                        # just to search for a Supporter. It is a 2-prize
                        # body and we do not need a supporter: we prefer
                        # developing with Ultra Ball/Dawn (e.g. searching for a Teal
                        # Mask Ogerpon ex and accelerating energy with Teal Dance) or
                        # attacking directly. The LETHAL gust with Boss's was already
                        # resolved in the previous branch (_win_via_boss_gust).
                        score = SCORE_VETO
                    elif (hand_counts.get(Lillie_Determination, 0) >= 1
                            and field_counts[card.id] == 0):
                        # Rule (user): if we ALREADY have a Lillie's Determination IN
                        # HAND, Meowth ex is NOT played on ANY turn; we
                        # deploy the rest and play Lillie's. Putting Meowth ex down
                        # would only waste a 2-prize body and its Supporter
                        # search, because Lillie's shuffles the WHOLE hand into the
                        # deck -> the fetched card would be lost. The LETHAL gust
                        # with Boss's is handled earlier (the _win_via_boss_gust branch).
                        # If Lillie's is NOT in hand but IS in the deck, this
                        # veto does NOT apply: it falls through to `_meowth_devel_lillie`
                        # to put Meowth ex down, SEARCH for Lillie's and play it.
                        score = SCORE_VETO
                    elif (_bcs_playable_in_hand
                            and hand_counts.get(Lillie_Determination, 0) >= 1
                            and field_counts[card.id] == 0
                            and not (_win_via_boss_gust or _gust_2prize_via_boss)):
        
                        score = SCORE_VETO
                    elif (_meowth_devel_lillie
                            and hand_counts.get(Meowth_ex, 0) >= 1
                            and hand_counts.get(Lillie_Determination, 0) == 0
                            and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Lillie_Determination, {}).get(ZONE_DECK, 0) > 0
                            and field_counts[card.id] == 0
                            and bench_count < 5):
        
                        score = 21800
                    elif _bcs_playable_in_hand and bench_count >= 1:
        
                        score = SCORE_VETO
                    elif (field_counts[card.id] == 1
                            and bench_count < 5
                            and _active_cant_attack_this_turn
                            and not state.supporterPlayed
                            and hand_counts.get(Lillie_Determination, 0) == 0
                            and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                                Lillie_Determination, {}).get(ZONE_DECK, 0) > 0
                            and not op_has_froslass
                            and not (state.turn == 1 and AGENT_STATE.we_go_first)):
        
                        score = 21700
                    elif field_counts[card.id] >= 1:
                        score = SCORE_VETO
                    elif bench_count >= 5:
                        score = SCORE_VETO
                    elif state.turn == 1 and AGENT_STATE.we_go_first:
        
                        _other_basics_in_hand = any(
                            hand_counts.get(pid, 0) >= 1
                            for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                        Tapu_Bulu, Fezandipiti_ex, Pinsir))
                        if bench_count == 0 and not _other_basics_in_hand:
                            score = 19000
                        else:
                            score = SCORE_VETO
                    elif state.turn == 2 and not AGENT_STATE.we_go_first:
        
                        if (not state.supporterPlayed and
                                _best_supp_in_hand_val < 500 and
                                _best_supp_in_deck_id == Lillie_Determination and
                                _best_supp_in_deck_val >= 650):
                            score = 20500
                        else:
                            score = SCORE_VETO
                    elif state.supporterPlayed:
                        score = SCORE_VETO
                    elif op_has_froslass:
                        # Normally Meowth ex (2 prizes) is not benched against
                        # Froslass (which pings the bench). EXCEPTION (user, registro_008
                        # step 84, vs Marnie/Froslass, LOST): on a DEAD
                        # TURN -- the active can neither ATTACK nor RETREAT (0
                        # energy < the retreat cost), there is no benched attacker
                        # to bring up and there are no cards in hand to enable an
                        # attack -- with room on the bench and the refill engine in
                        # the DECK (Meowth ex -> Last-Ditch Catch searches for Lana's Aid
                        # or Lillie's Determination), putting Meowth ex down is the ONLY
                        # useful play: recovering 3 energies from the discard (Lana's
                        # Aid) or refilling the hand (Lillie's) opens up attack
                        # options in the coming turns. The Lana's/Lillie's choice
                        # is resolved by the Supporter search.
                        _mw_act_reloc = my_state.active[0] if my_state.active else None
                        _mw_can_retreat = (
                            _mw_act_reloc is not None
                            and len(_mw_act_reloc.energies)
                            >= RETREAT_COST.get(_mw_act_reloc.id, 1))
                        _mw_engine_in_deck = (
                            AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                                Lillie_Determination, {}).get(ZONE_DECK, 0) > 0
                            or AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                                Lanas_Aid, {}).get(ZONE_DECK, 0) > 0)
                        if (_active_cant_attack_this_turn
                                and not _mw_can_retreat
                                and field_counts[card.id] == 0
                                and bench_count < 5
                                and not state.supporterPlayed
                                and hand_counts.get(Lillie_Determination, 0) == 0
                                and _mw_engine_in_deck):
                            score = 21600
                        else:
                            score = SCORE_VETO
                    elif (_active_cant_attack_this_turn and
                          not state.supporterPlayed and
                          hand_counts.get(Lillie_Determination, 0) == 0 and
                          AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Lillie_Determination, {}).get(ZONE_DECK, 0) > 0):
        
                        score = 21800
                    elif (bench_count >= 1 and
                          hand_counts.get(Lillie_Determination, 0) >= 1 and
                          hand_counts.get(Ultra_Ball, 0) >= 1 and
                          not (AGENT_STATE.op_is_crustle_deck or op_is_drednaw_deck or op_is_sylveon_deck) and
                          not (_best_supp_in_deck_id == Boss_Orders and _best_supp_in_deck_val >= 650)):
        
                        score = SCORE_VETO
                    elif _best_supp_in_hand_val >= 500:
        
                        _boss_in_deck = AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Boss_Orders, {}).get(ZONE_DECK, 0) > 0
                        _boss_val = _supp_values.get(Boss_Orders, 0)
                        if AGENT_STATE.op_is_crustle_deck and _boss_in_deck and _boss_val >= 900 and hand_counts.get(Boss_Orders, 0) == 0:
                            score = 21500
                        elif (op_is_drednaw_deck and _boss_in_deck and _boss_val >= 650
                              and hand_counts.get(Boss_Orders, 0) == 0):
        
                            score = 21500
                        elif (op_is_sylveon_deck and _boss_in_deck and _boss_val >= 650
                              and hand_counts.get(Boss_Orders, 0) == 0):
        
                            score = 21500
                        else:
                            score = SCORE_VETO
                    else:
        
                        _meowth_score = SCORE_VETO
                        _target_id = _best_supp_in_deck_id
                        _target_val = _best_supp_in_deck_val
        
                        if _target_id == Boss_Orders and _target_val >= 650:
        
                            _meowth_score = 21000
                        elif _target_id == Lillie_Determination and _target_val >= 650:
        
                            _ATK_REQS_MEOWTH = {
                                Hydrapple_ex: 2, Dipplin: 1, Teal_Mask_Ogerpon_ex: 3,
                                Tapu_Bulu: 4, Meganium: 4, Fezandipiti_ex: 3,
                                Pinsir: 2,
                            }
                            _ready_attackers = 0
        
                            _m_act = my_state.active[0] if my_state.active else None
                            if _m_act is not None and _m_act.id in _ATK_REQS_MEOWTH:
                                _m_eff = len(_m_act.energies) * _grass_mult()
                                if _m_eff >= _ATK_REQS_MEOWTH[_m_act.id]:
                                    _ready_attackers += 1
        
                            for _m_bp in my_state.bench:
                                if _m_bp is not None and _m_bp.id in _ATK_REQS_MEOWTH:
                                    _m_bp_eff = len(_m_bp.energies) * _grass_mult()
                                    if _m_bp_eff >= _ATK_REQS_MEOWTH[_m_bp.id]:
                                        _ready_attackers += 1
        
                            _m_hand_size = len(my_state.hand) if my_state.hand else 0
                            if _ready_attackers <= 2 and _m_hand_size < 4:
                                _meowth_score = 20500
        
                        elif _target_id == Dawn and _target_val >= 700:
        
                            _forest_avail = AGENT_STATE.forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1
                            if _forest_avail:
                                _meowth_score = 20500
                        elif _target_id == Lanas_Aid and _target_val >= 600:
        
                            _meowth_score = 20000
        
                        score = _meowth_score
        
                    # FINAL VALIDATION: the Supporter the Last-Ditch Catch
                    # would bring is ALREADY in hand -> the search is redundant
                    # and putting Meowth ex down only gives away a 2-prize body.
                    # The play is cancelled (the turn goes on and the Supporter is
                    # played through its own ladder). It goes at the END of the chain
                    # so it also has the last word over the engines
                    # above (winning Boss's 22500, deny-evo 22000...):
                    # those only look at whether the BOSS'S is in hand, not at what
                    # the real fetch would be -- in registro_010 the engine
                    # pointed at Boss's but the fetch ended up bringing the
                    # Xerosic we already had. See `_meowth_fetch_prediccion`.
                    #
                    # `_meowth_fetch_loses_the_turn` is the other half of the
                    # same check: the fetch would bring something we do NOT have,
                    # but a Supporter from hand takes the turn's ONLY
                    # slot, so the fetched card is not played
                    # today either (registro_004 step 36: a fetched Lillie's vs a Xerosic
                    # in hand). Same place and same effect: cancel the
                    # play and carry on the turn with the Supporter from hand.
                    if ((_meowth_fetch_redundante
                         or _meowth_fetch_loses_the_turn) and score > 0):
                        score = SCORE_VETO
                elif card.id == Fezandipiti_ex:
        
                    # With Lillie's Determination + Teal Mask Ogerpon ex +
                    # Grass energy in hand, the correct play is to put
                    # Teal down (a future attacker), use Teal Dance and then play
                    # Lillie's Determination to refill the hand. Fezandipiti's
                    # ability (Flip the Script) only draws up to 3 cards,
                    # so with a full hand it adds nothing and would spend the turn /
                    # the bench on a non-attacker. We let Teal (21000) win.
                    _fez_prefer_teal_lillie = (
                        hand_counts.get(Lillie_Determination, 0) >= 1
                        and not state.supporterPlayed
                        and hand_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1
                        and field_counts[Teal_Mask_Ogerpon_ex] < 2
                        and hand_counts.get(Basic_Grass_Energy, 0) >= 1
                        and bench_count < 5)
        
                    if _fez_prefer_teal_lillie:
        
                        score = SCORE_VETO
                    elif field_counts[card.id] >= 1:
                        score = SCORE_VETO
                    elif bench_count >= 5:
                        score = SCORE_VETO
                    elif (op_is_lucario_deck or AGENT_STATE.op_is_crustle_deck
                          or AGENT_STATE.op_is_cornerstone_deck or op_is_sylveon_deck
                          # PHASE E1 (Marnie plan, D5): with FROSLASS on the field
                          # the bench is not a safe place. Fezandipiti ex
                          # has an ABILITY, so it pays the toll of
                          # Freezing Shroud (20 per round per Froslass) without
                          # the opponent spending anything, and it is TWO prizes that
                          # Munkidori can finish off where they stand. Game 2:
                          # Meowth ex and Fezandipiti ex occupied the bench for 13
                          # turns absorbing 40/round each. The same
                          # criterion already applied to Meowth ex (see the
                          # `elif op_has_froslass` of its branch): it is only put down
                          # if it PAYS OFF today -- Flip the Script alive
                          # (ko_last_turn) -- or if the bench is EMPTY, where
                          # a KO on the active would be the loss.
                          or op_has_froslass):
                        # Against Mega Lucario (Fighting), Crustle, Cornerstone
                        # Ogerpon and Sylveon: Fezandipiti ex is worth 2 prizes and its
                        # Flip the Script ability only works after being knocked out.
                        # We do NOT put it down for development at the start of the game.
                        # If the ability is alive (ko_last_turn) the normal route is
                        # kept. If not, we wait until the end of the turn and only
                        # put it down as a LAST resort when the bench is
                        # EMPTY: with no bench, a KO on our active next
                        # turn = a loss. With a low score (500) any
                        # real development (a basic ~20000) is played first; Fez only
                        # comes down if there is no other way to have a body in play.
                        if AGENT_STATE.ko_last_turn:
                            score = 22000
                            if len(my_state.hand) <= 3:
                                score = 22500
                        elif bench_count == 0:
                            score = 500
                        else:
                            score = SCORE_VETO
                    elif state.turn == 1:
        
                        if bench_count == 1:
                            score = 15000
                        else:
                            score = SCORE_VETO
                    else:
                        fez_score = SCORE_VETO
        
                        if AGENT_STATE.ko_last_turn:
                            fez_score = 22000
        
                            if len(my_state.hand) <= 3:
                                fez_score = 22500
        
                        if not AGENT_STATE.ko_last_turn and bench_count <= 2:
                            _all_bench_basics = True
                            for _bp_fez in my_state.bench:
                                if _bp_fez is not None:
                                    _bp_fez_data = card_table.get(_bp_fez.id)
                                    if _bp_fez_data and (getattr(_bp_fez_data, 'stage1', False) or
                                                         getattr(_bp_fez_data, 'stage2', False)):
                                        _all_bench_basics = False
                                        break
                            # Against Mega Lucario (a Fighting type) we do NOT put
                            # Fezandipiti ex down just for "development": it is weak to
                            # Fighting ({F}) and worth 2 prizes, and its Flip
                            # the Script ability is dead if we were not knocked out the
                            # previous turn. Putting it down like that only gives away a KO of
                            # 2 easy prizes. With the ability alive
                            # (ko_last_turn) the 22000 route is kept.
                            if _all_bench_basics and not op_is_lucario_deck:
                                fez_score = max(fez_score, 15000)
        
                        score = fez_score
                elif card.id == Tapu_Bulu:
        
                    _tapu_first_turn = (state.turn <= 2)
                    _tapu_in_play_count = (
                        (1 if (my_state.active and my_state.active[0] is not None) else 0)
                        + bench_count)
        
                    _op_is_crustle_like = (
                        AGENT_STATE.op_is_crustle_deck or op_has_ability_immune_active or
                        AGENT_STATE.op_is_cornerstone_deck or op_is_sylveon_deck or
                        op_has_ex_immune_active or op_has_ex_immune_bench or
                        op_is_iron_thorns_deck)
        
                    # Backup of the matchup's ONLY attacker (iron_thorns
                    # autopsy p030 t2, step 1 of the jul 2026 plan): against an
                    # opponent that cancels our ability engine or makes our ex
                    # damage 0 (_op_is_crustle_like), Tapu Bulu is THE
                    # attacker -- and if the only one we have in play is the
                    # ACTIVE, when it falls there is no relief. The redundant-copy
                    # veto (below) used to be evaluated BEFORE the matchup branches
                    # and the 2nd Tapu died in hand (END with 7 cards).
                    # Guards: exactly 1 in play, that 1 is the active, and
                    # the matchup is a wall/lock one. 21800: below the priority
                    # of the 1st copy (22000+), above generic development.
                    _tapu_backup_vs_lock = (
                        field_counts[card.id] == 1 and
                        _op_is_crustle_like and
                        my_state.active and my_state.active[0] is not None
                        and my_state.active[0].id == Tapu_Bulu)
        
                    # vs DRAGAPULT it is not put down with the board developed
                    # (>2 Pokemon in play). See `_dragapult_no_tapu`: this is
                    # where it is applied, and it goes FIRST in the chain because
                    # the branches below (in particular the
                    # `_tapu_in_play_count >= 4 and meganium_in_play` one, which
                    # is the one that put it down in registro_003 step 43) do not
                    # look at the matchup. The veto yields to the wall
                    # (`_op_is_crustle_like`): there Tapu is the only
                    # attacker and the matchup collision rules.
                    if _dragapult_no_tapu and not _op_is_crustle_like:
                        score = SCORE_VETO
                    elif field_counts[card.id] >= 1:
                        if _tapu_backup_vs_lock:
                            score = 21800
                        else:
                            score = SCORE_VETO
                    elif (_tapu_in_play_count >= 4 and not _op_is_crustle_like and
                          AGENT_STATE.meganium_in_play and not _tapu_first_turn):
        
                        score = 16000
                    elif (_tapu_in_play_count > 2 and not AGENT_STATE.op_is_crustle_deck
                            and not op_is_iron_thorns_deck
                            # Cornerstone (autopsy p004 t2): Tapu Bulu is
                            # THE attacker of the matchup (the Ogerpon/Hydrapple
                            # with abilities do 0); crowding does not
                            # justify leaving it dead in hand.
                            and not AGENT_STATE.op_is_cornerstone_deck
                            and not op_has_ability_immune_active):
        
                        score = SCORE_VETO
                    elif AGENT_STATE.op_is_crustle_deck:
        
                        score = 22000
                        if AGENT_STATE.meganium_in_play:
                            score = 22500
                    elif op_has_ability_immune_active or AGENT_STATE.op_is_cornerstone_deck:
        
                        score = 22500
                    elif op_is_iron_thorns_deck:
                        # Iron Thorns ex (P1.4 plan B, iron_thorns autopsy
                        # p007 t16): with Initialization in front, Teal Dance /
                        # Ripening / Last-Ditch are dead and the agent
                        # closed the turn with Tapu Bulu IN HAND (66 sterile
                        # turns across 15 losses). Tapu is the manual
                        # attacker with no ability: putting it down is plan A, as
                        # vs Cornerstone.
                        score = 22000
                    elif op_is_sylveon_deck:
        
                        score = 22000
                    elif op_has_ex_immune_active or op_has_ex_immune_bench:
        
                        score = 21000
                        if has_hydrapple:
                            score = 22000
                    elif (_lucario_sac_pivot and bench_count < 5
                            and (_tapu_sac_priority
                                 or not _lucario_other_sac_available)):
        
                        # Put Tapu Bulu down vs Mega Lucario only when it is the
                        # priority sacrifice (an opponent with ex protection or the
                        # Hydrapple ex + Meganium engine) or when there is no other
                        # 1-prize basic (Applin / Chikorita) available.
                        # If there is a disposable alternative, we keep Tapu Bulu.
                        score = 21500
                    elif _tapu_first_turn:
        
                        score = SCORE_VETO
                    elif not AGENT_STATE.meganium_in_play:
        
                        score = SCORE_VETO
                    else:
        
                        score = 16000
        
                    # Tapu Bulu is only put down after playing every item
                    # ("artefact") the game considers worth playing. If there is still
                    # an item in hand, we lower Tapu Bulu's priority
                    # below the band of useful items: the items that are
                    # worth it (a higher score) are played first and, when only
                    # worthless items are left (a low score), Tapu Bulu wins again
                    # and comes down. It applies ONLY to Tapu Bulu.
                    _tapu_items_pending = any(
                        hand_counts.get(_it_id, 0) >= 1 for _it_id in DECK_ITEM_IDS)
                    if _tapu_items_pending and score > TAPU_WAIT_FOR_ITEMS_SCORE:
                        score = TAPU_WAIT_FOR_ITEMS_SCORE
                elif card.id == Pinsir:
        
                    score = SCORE_VETO
        
                if (AGENT_STATE._poke_pad_target_id > 0 and card.id == AGENT_STATE._poke_pad_target_id and
                        bench_count < 5):
                    if score <= 0:
                        score = 21000
        
                if (AGENT_STATE._ub_meowth_pending and card.id == Meowth_ex and
                        field_counts[Meowth_ex] < 2 and _meowth_ld_free
                        and bench_count < 5
                        and not state.supporterPlayed
                        and not _stamp_blocks_supp_chain):
                    # `_ub_meowth_pending` (an earlier Ultra Ball brought Meowth ex)
                    # forces putting it down to chain Last-Ditch Catch -> search for the
                    # Supporter (Lillie's) and REFILL the hand. User's rule
                    # (registro_008 step 71 vs Hop's, WON): if the Ultra Ball
                    # CHOSE to search for Meowth ex, the play has to be COMPLETED and it
                    # has to be put down ALWAYS -- even if the active is already a ready
                    # attacker: benching the Meowth does NOT prevent attacking afterwards, and
                    # leaving it dead in hand wastes the whole Ultra Ball
                    # (here the hand was left EMPTY after attacking; Meowth -> Lillie's
                    # refills it). It used to require `not _active_ready_attacker` and
                    # with the Hydrapple ready it attacked without putting it down. The correct
                    # guard is `not state.supporterPlayed`: if the Supporter has ALREADY
                    # been played this turn (registro 006 step 57 vs Alakazam), the
                    # fetched Lillie's could not even be played and putting a 2-prize
                    # body down is redundant -> there attacking is kept.
                    # Unfair Stamp GUARD (user, registro_008 step 115, episode
                    # 87676139 vs Mega Lucario, LOST): with a PLAYABLE Unfair Stamp
                    # in hand (`_stamp_blocks_supp_chain`: we were knocked out
                    # last turn and the Stamp is still in hand), this override
                    # does NOT apply: putting the Meowth down BEFORE the Stamp wastes the
                    # Last-Ditch (the fetched Supporter -- Lillie's -- is SHUFFLED into the
                    # deck with the Stamp without being playable) and exposes a 2-prize
                    # body. Correct order: items -> Unfair Stamp ->
                    # and only AFTERWARDS put Meowth ex down if it becomes
                    # available again. Without the guard, this override (21000) overrode the
                    # Stamp+ko_last_turn veto of the main chain.
                    if score <= 0:
                        score = 21000
        
                _alk_meowth_hand_engine = (
                    card.id == Meowth_ex and op_is_alakazam_deck
                    and not state.supporterPlayed
                    and getattr(op_state, 'handCount', 0) >= 6
                    and hand_counts.get(Xerosic_Machinations, 0) == 0
                    and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                        Xerosic_Machinations, {}).get(ZONE_DECK, 0) > 0
                    and field_counts[Meowth_ex] < 2 and _meowth_ld_free
                    and bench_count < 5
                    and not _stamp_blocks_supp_chain
                    # ...and only if the ABILITY is really going to be used (user,
                    # log 88162677 step 16 vs Alakazam, LOST): with two
                    # Lillie's in hand on OUR FIRST TURN, this engine
                    # put the Meowth ex down (21500, and it also exempted
                    # the generic veto "do not put Meowth down if there is already a Lillie's in hand")
                    # and on the next step the Last-Ditch Catch prompt
                    # REJECTED the fetch through `_meowth_skip_fetch` -- the same
                    # board, two opposite answers. Result: a 2-prize
                    # body given away on the bench, the Lillie's played
                    # anyway and zero value. Tying the engine to the SAME predicate
                    # as the ability means the two decisions can never
                    # contradict each other again. The cases that justified the engine
                    # (registro_006 p76, registro_008 p85, registro_010 p147)
                    # have `_meowth_devel_lillie` False -- a board that is already
                    # developed or with no Lillie's in hand -- so
                    # `_meowth_fetch_already_in_hand` is False and they still put the
                    # Meowth down to dig out the Xerosic.
                    and not _meowth_fetch_already_in_hand)
                if _alk_meowth_hand_engine:
                    # Xerosic engine vs Alakazam with a Meowth ex ALREADY in hand
                    # (user, registro_006 step 76 vs Alakazam, WON): with
                    # the Supporter free, the opposing hand fat (>=6 -> Powerful
                    # Hand knocks us out next turn) and the Xerosic still in
                    # the DECK, put the Meowth ex down ALWAYS -- even if the active
                    # is a ready attacker (putting it down does not prevent attacking): Last-
                    # Ditch Catch searches for the Xerosic, it is played (opponent down to 3
                    # cards) and AFTERWARDS we attack. It is the "in hand" version of
                    # the chain Ultra Ball -> Meowth -> Xerosic (the
                    # `_ub_meowth_pending` branch above); the reservation of the last
                    # bench slot vs Alakazam exists precisely for this.
                    # 21500: ABOVE the development rush (an Applin with Forest
                    # = 21200) -- with ONE single bench slot, putting the Applin down
                    # blocks the Xerosic engine forever and Powerful Hand
                    # (20 x 11 = 220) knocks us out (user, registro_010
                    # step 147 vs Alakazam, LOST: the agent put the
                    # Applin down and BOTH Meowth ex died in hand).
                    if score < 21500:
                        score = 21500
        
                # PRIZE MISMATCH (user, registro_002 step 27 vs Raging
                # Bolt/Ogerpon LOST; and registro_002 vs Mega Abomasnow ex):
                # these decks ONE-SHOT any of our ex (Raging
                # Bolt with Bellowing Thunder; Mega Abomasnow ex with its attack).
                # Whenever our active is an ex that canNOT knock out the
                # opposing active this turn, put a ONE-prize body down (Tapu
                # Bulu preferred: it is also the non-ex attacker) so we can then
                # retreat the ex and put it in front -- if we are knocked out, we
                # concede 1 prize and not 2, and the opponent needs KOs of 2-3 to win.
                # Only if there is not already a 1-prize body on the bench (one
                # is enough for the pivot). `_prize_mismatch_matchup` already excludes our
                # first turn when going first. (no score guard: the boost
                # has to come before the generic development vetoes, which do not
                # know about this plan)
                if _prize_mismatch_matchup:
                    _rb_act = my_state.active[0] if my_state.active else None
                    _rb_data = card_table.get(card.id)
                    _rb_es_1premio_basico = (
                        _rb_data is not None
                        and not _rb_data.ex and not _rb_data.megaEx
                        and not _rb_data.stage1 and not _rb_data.stage2)
                    _rb_bench_with_1prize = any(
                        bp is not None and prize_count(bp) == 1
                        for bp in (my_state.bench or []))
                    if (_rb_es_1premio_basico
                            and _rb_act is not None
                            and _rb_act.id in OUR_EX_IDS
                            and not _active_already_kos
                            and not _rb_bench_with_1prize):
                        score = 21850 if card.id == Tapu_Bulu else 21700
        
                # Cubchoo matchup (user, change 5): against this deck the bench
                # may ONLY hold the Hydrapple ex line (Applin/Dipplin/
                # Hydrapple ex, one), the Meganium line (Chikorita/Bayleef/
                # Meganium, one), up to TWO Teal Mask Ogerpon ex and ONE Meowth ex
                # (only when it is needed to SEARCH for a Lillie's Determination
                # from the deck). The other Pokemon (Tapu Bulu, Fezandipiti ex,
                # Pinsir...) are NOT played. It is applied after the
                # poke_pad/ub_meowth exceptions and BEFORE the empty-bench fallback
                # (further down), which still guarantees that we never run out of
                # Pokemon in play (a forced legal play).
                if op_is_cubchoo_deck:
                    _CUB_ALLOWED_PLAY = CUBCHOO_ALLOWED_PLAY_IDS
                    # MATCHUP COLLISION (user, registro_004 turn 4): with
                    # an opposing Cornerstone Mask Ogerpon ex in play, its
                    # Cornerstone Stance cancels the damage of ALL our
                    # Pokemon WITH an ability -- including Teal Mask Ogerpon ex
                    # and Hydrapple ex, which this list DOES allow. The only
                    # real attacker becomes Tapu Bulu, which the list
                    # excluded: the agent put down a 2nd Ogerpon ex (0 damage) and
                    # left Tapu dead in hand. The whitelist is widened
                    # with Tapu Bulu ONLY in that case; without Cornerstone the
                    # anti-Cubchoo plan is untouched.
                    if op_has_ability_immune_active or AGENT_STATE.op_is_cornerstone_deck:
                        _CUB_ALLOWED_PLAY = _CUB_ALLOWED_PLAY + (Tapu_Bulu,)
                    if card.id not in _CUB_ALLOWED_PLAY:
                        score = SCORE_VETO
                    elif (card.id == Teal_Mask_Ogerpon_ex
                            and field_counts[card.id] >= 2):
                        # No more than two Teal Mask Ogerpon ex in play.
                        score = SCORE_VETO
                    elif card.id == Meowth_ex:
                        # A single Meowth ex and only if there is a Lillie's
                        # Determination to search for in the deck (not already in hand).
                        _cub_meowth_ok = (
                            field_counts[Meowth_ex] == 0
                            and hand_counts.get(Lillie_Determination, 0) == 0
                            and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                                Lillie_Determination, {}).get(ZONE_DECK, 0) > 0)
                        if not _cub_meowth_ok:
                            score = SCORE_VETO
        
                # Bench reservation vs Alakazam (user): with ONE single free slot
                # (bench_count == 4) and a Xerosic's Machinations still in the
                # DECK, do not fill the last slot with a body that does not advance
                # the plan: it is reserved for Meowth ex, which searches for the Xerosic
                # (capping Powerful Hand = 20 x card in the opponent's hand). The
                # REDUNDANT bodies are vetoed (a duplicate of something already in
                # play, or Fezandipiti ex: a 2-prize body with no role vs Alakazam);
                # Meowth ex and the first copies of the attacking lines
                # (Chikorita/Applin/Tapu...) are allowed. The anti-softlock empty-bench
                # rescue (further down) requires bench_count == 0, so it never
                # conflicts with this rule (bench_count == 4).
                #
                # ENGINE CONDITION (user, registro_010 step 150 vs
                # Alakazam, LOST -- log 88903365): it used to require
                # `field_counts[Meowth_ex] == 0`, that is "no Meowth ex
                # in play". That contradicts the very engine the reservation
                # protects: `_alakazam_dig_xerosic_engine` and the Meowth ex PLAY
                # branch accept a SECOND copy while there are < 2 in
                # play and the turn's Last-Ditch is still free (`_meowth_ld_free`
                # -- the benched Meowth from previous turns has already spent its own,
                # but a NEW one from hand searches again). With a Meowth
                # ex already benched the reservation switched off and the agent put into the
                # last slot a THIRD Teal Mask Ogerpon ex (score 20500,
                # tier DEVELOP, which also rules by ORDER over everything else).
                # Immediately afterwards the Ultra Ball DID dig out the 2nd Meowth ex... which
                # stayed DEAD in hand with the bench full: with no Last-Ditch there
                # was no Xerosic, the opponent attacked with 11 cards in hand (Powerful
                # Hand = 220) and finished with Boss's Orders on a benched Teal Mask
                # Ogerpon ex (210 HP) for their last 2 prizes.
                # It is also required that a Meowth ex remain REACHABLE (hand or
                # deck): with no body to fill the slot there is nothing to
                # reserve. The three conditions live together in
                # `_alk_ld_engine_alive` (computed alongside `_meowth_ld_free`).
                if (op_is_alakazam_deck and bench_count == 4
                        and _alk_ld_engine_alive
                        and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                            Xerosic_Machinations, {}).get(ZONE_DECK, 0) > 0
                        and score > 0
                        and card.id != Meowth_ex):
                    if (field_counts.get(card.id, 0) >= 1
                            or card.id == Fezandipiti_ex):
                        score = SCORE_VETO
        
                # Req H: vs Mega Lucario with a gustable+knockable Riolu on
                # the opposing bench and our own bench established, do NOT develop
                # or refill the hand: we yield the play to Boss's Orders
                # (gust + knock out the Riolu to cut their line). We veto
                # the development of ANY Pokemon (tier DEVELOP) so that
                # Boss's (a supporter, tier 0) is the chosen play. The flag
                # requires bench_count>=2, so the anti-softlock rescue
                # further down (empty bench) never conflicts.
                #
                # EXEMPTION: Fezandipiti ex with Flip the Script ALIVE (user,
                # registro_006 step 91, episode 88710543 vs Mega Lucario,
                # WON by luck). Putting it down is NOT "developing or refilling
                # the hand": it is a Pokemon, it does not consume the turn's Supporter,
                # so the Boss's this veto yields the turn to is still
                # played afterwards. Vetoing it was, on top of that, a CIRCULAR BLOCK of
                # three pieces (the same class as step 78): the Fezandipiti
                # just dug out with the Ultra Ball was not put down (this veto), the
                # Boss's was not played (`cede_a_unfair_stamp`) and the Unfair Stamp
                # stayed at 2000 (`mano_con_pokemon_o_evo`: "put the Pokemon down first").
                # The Stamp won by elimination and SHUFFLED into the deck
                # the Fezandipiti that had just cost two cards -- and with it,
                # the very Boss's this veto was yielding the turn to. The Fezandipiti
                # branch already decides the vs-Fighting case on its own: with the
                # ability dead it is NOT put down (2 prizes given away), with the
                # ability alive it is worth 22000. This veto overrode it silently.
                if _lucario_riolu_gust and not (
                        card.id == Fezandipiti_ex and AGENT_STATE.ko_last_turn
                        and field_counts.get(Fezandipiti_ex, 0) == 0
                        and bench_count < 5):
                    score = SCORE_VETO
        
                # COMPLETING THE UB -> FEZANDIPITI EX CHAIN (user,
                # registro_006 steps 90-91, episode 88710543 vs Mega
                # Lucario). If THIS turn's Ultra Ball chose to search for
                # Fezandipiti ex (`_ub_fez_pending`; the `fez_tras_ko`
                # target is only chosen with the ability ALIVE), the
                # body GOES DOWN: the search has already been paid for with two discards and the
                # only reason to dig it out is to cash in Flip the Script this
                # turn. In the record, the Req H ORDERING veto
                # (`_lucario_riolu_gust`) left the Fezandipiti in hand and
                # the Unfair Stamp SHUFFLED it back into the deck: the Ultra Ball,
                # two cards and the 3-card draw, all in the bin (it was only
                # recovered by LUCK among the Stamp's 5 cards).
                # It goes AFTER all the branch's vetoes, just like the
                # twin Meowth ex override, because it is precisely those vetoes
                # that contradict an already paid-for search. The PHYSICAL
                # limits still rule (full bench / copy already in play) and
                # the ability has to be alive.
                if (AGENT_STATE._ub_fez_pending and card.id == Fezandipiti_ex
                        and score <= 0
                        and AGENT_STATE.ko_last_turn
                        and field_counts.get(Fezandipiti_ex, 0) == 0
                        and bench_count < 5):
                    score = 22000
        
                # Anti-softlock rescue: with an empty bench, raise a basic
                # that was left at <=0 so it can be deployed (a legal play).
                # EXCEPTION: on our first turn, with a playable Lillie's
                # Determination in hand, we do NOT force Meowth ex onto the
                # bench (we respect the veto: the rest is deployed and
                # Lillie's is played; if after playing Lillie's there is still no bench,
                # supporterPlayed becomes True and this rescue is re-enabled to
                # put Meowth ex down as a last resort). This applies EVEN IF we already
                # have a Meowth ex in play (e.g. as the active): putting a
                # SECOND Meowth ex down is even more useless (its Supporter search
                # is shuffled away with Lillie's and it exposes another 2-prize body).
                _meowth_first_turn_hold = (
                    card.id == Meowth_ex
                    and _our_first_turn
                    and hand_counts.get(Lillie_Determination, 0) >= 1
                    and not state.supporterPlayed)
                if (bench_count == 0 and score <= 0
                        and not _meowth_first_turn_hold and
                        not (getattr(data, 'stage1', False) or
                             getattr(data, 'stage2', False))):
                    if card.id in OUR_EX_IDS:
                        score = 80
                    else:
                        score = 150
        
                # Anti-DONK guard for the first turn going FIRST
                # (user, registro_001 steps 6-7 vs Cinderace/Archaludon,
                # LOST): an EMPTY bench, only the active basic, and the opposing
                # ACTIVE has a ONE-energy attack whose projected damage
                # (weakness included, via _op_active_attack_damage_to which
                # assumes the opponent's attachment: 0e+1) KNOCKS OUT our active
                # (Turbo Flare 50 x2 Fire->Grass = 100 >= Chikorita 70).
                # With no bench, that KO on their first turn is an instant
                # LOSS. Put Meowth ex down YES even if there is a Lillie's in
                # hand: going first the Supporter is NOT EVEN playable
                # this turn (the engine does not offer it), so the reason for the
                # hold ("play Lillie's and do not shuffle the fetch away") does not apply.
                # Meowth is the body that avoids the loss and its Last-Ditch
                # brings a Lillie's for the next turn. If the opponent does NOT
                # project the donk, the previous behaviour is kept (do not
                # put it down: the no-meowth-para-lillie rule).
                if card.id == Meowth_ex and _meowth_antidonk_now:
                    score = 21900
        
                _dip_act = my_state.active[0] if my_state.active else None
                if (_dip_act is not None and _dip_act.id == Dipplin
                        and bench_count < 5
                        and card.id not in OUR_EX_IDS
                        and not (getattr(data, 'stage1', False) or
                                 getattr(data, 'stage2', False))
                        and op_state.active and op_state.active[0] is not None):
                    _dip_can_attack = (
                        len(_dip_act.energies) >= 1
                        or (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                            and not state.energyAttached))
                    if _dip_can_attack:
                        _dip_op_act = op_state.active[0]
                        _dip_op_hp = _dip_op_act.hp or 0
                        _dwave_now = 20 * bench_count
                        _dwave_boost = 20 * (bench_count + 1)
                        _dip_td = card_table.get(_dip_op_act.id)
                        if _dip_td is not None:
                            if _dip_td.weakness == EnergyType.GRASS:
                                _dwave_now *= 2
                                _dwave_boost *= 2
                            elif _dip_td.resistance == EnergyType.GRASS:
                                _dwave_now -= 30
                                _dwave_boost -= 30
                        _dip_ko_now = (_dwave_now >= _dip_op_hp and _dwave_now > 0)
                        _dip_ko_boost = (_dwave_boost >= _dip_op_hp and _dwave_boost > 0)
                        if _dip_ko_boost and not _dip_ko_now:
        
                            score = max(score, 21900)
        
                if card.id == Meowth_ex:
                    _meowth_played_this_turn = (
                        field_counts[Meowth_ex] >
                        AGENT_STATE._field_at_turn_start.get(Meowth_ex, 0)
                        if AGENT_STATE._field_at_turn_start is not None else False)
                    if meowth_ability_lock:
                        # Team Rocket's Watchtower cancels the ability of
                        # {C} Pokemon: putting Meowth ex down now would NOT activate
                        # Last-Ditch Catch (it does not search for a Supporter). We do not play it
                        # until the stadium is replaced (e.g. with Forest).
                        score = SCORE_VETO
                    elif _meowth_played_this_turn:
                        score = SCORE_VETO
                    elif field_counts[Meowth_ex] >= 2:
                        score = SCORE_VETO
                    elif field_counts[Meowth_ex] >= 1 and score <= 0:
                        score = SCORE_VETO
                    elif (hand_counts.get(Lillie_Determination, 0) >= 1
                          # Xerosic engine EXCEPTION vs Alakazam (user,
                          # registro_008 step 85, episode 88119461,
                          # LOST): with the opposing hand FAT (15 cards ->
                          # Powerful Hand 20x17=340 one-shots us) the Last-Ditch
                          # fetch does NOT point at Lillie's but at the
                          # XEROSIC in the deck (capping the opposing hand to 3). Having
                          # a Lillie's in hand does not make it redundant:
                          # the fetch ladder vs Alakazam with an opposing hand
                          # >=6 already chooses Xerosic. Without this exception the veto
                          # overrode the engine's 21500 and the agent gusted
                          # with Boss's leaving Powerful Hand loaded.
                          and not _alk_meowth_hand_engine):
                        # Rule (user, registro_003 p17 vs Archaludon): NEVER
                        # put Meowth ex down to search (Last-Ditch Catch) for a
                        # Lillie's Determination if we ALREADY have one in hand:
                        # the fetch is redundant and it exposes a 2-prize body.
                        # The Lillie's we have is played first. The ONLY
                        # EXCEPTION: our FIRST turn going FIRST, with
                        # an EMPTY bench and a single BASIC in the active spot other
                        # than Tapu Bulu (the bench needs developing). If after
                        # playing Lillie's we still have no bench, the anti-
                        # softlock rescue (supporterPlayed=True, no Lillie's in hand)
                        # re-enables putting Meowth down as a last resort.
                        _mw_act = my_state.active[0] if my_state.active else None
                        _mw_act_data = (card_table.get(_mw_act.id)
                                        if _mw_act is not None else None)
                        _mw_lone_basic = (
                            _mw_act is not None and _mw_act.id != Tapu_Bulu
                            and _mw_act_data is not None
                            and not getattr(_mw_act_data, 'stage1', False)
                            and not getattr(_mw_act_data, 'stage2', False))
                        # FIRST TURN rule (user, log 88461779 vs
                        # Alakazam): with a Lillie's Determination already in
                        # hand NOTHING is done to put down or search for a Meowth
                        # ex -- neither from hand nor with Ultra Ball. Meowth
                        # ex on the first turn exists ONLY to bring the
                        # Lillie's we do not have. The DEVELOPMENT
                        # exception (empty bench + a lone basic) is no longer
                        # enough on its own: the PROJECTED DONK
                        # (`_meowth_antidonk_now`) is also required, where
                        # the Meowth is not put down for its search but as a body
                        # that prevents losing the game on the spot (user,
                        # registro_001 steps 6-7 vs Cinderace). Without a donk,
                        # the rest of the hand is deployed and the Lillie's is
                        # played as soon as it is legal.
                        _mw_dev_exc = (
                            _our_first_turn and AGENT_STATE.we_go_first
                            and bench_count == 0 and _mw_lone_basic
                            and _meowth_antidonk_now)
                        if not _mw_dev_exc:
                            score = SCORE_VETO
        
                    # Rule (user, registro_004 step 60 vs Abomasnow, LOST):
                    # Meowth ex is only good for Last-Ditch Catch -> SEARCHING for a
                    # Supporter from the deck. If we have ALREADY played a Supporter this turn
                    # (`supporterPlayed`), that fetch is USELESS (a second Supporter
                    # cannot be played this turn), so putting a 2-prize body
                    # down is pure waste. The normal veto (-1) is NOT enough:
                    # it ties on score with a vetoed non-KO attack (also -1) and
                    # won the tie-break by index (Meowth appears before the
                    # attack). With SCORE_FORBID it falls below the attack (-1) and
                    # below ending the turn (SCORE_NEVER=-10000), so it is NEVER chosen
                    # over attacking or ending. The ONLY preserved exception: the
                    # anti-softlock rescue with an EMPTY bench (bench_count==0 and
                    # score>0, the only legitimate case of putting Meowth down with the Supporter
                    # already played, so we do not end up with no Pokemon in play). Everything else
                    # -- a weak hand, a second Meowth, any redundant fetch -- is
                    # forbidden. The condition does not depend on the previous veto, so it is
                    # robust even when replaying a single observation.
                    if (state.supporterPlayed
                            and not (bench_count == 0 and score > 0)):
                        score = SCORE_FORBID
        
                # Strategy vs Comfey (user, registro_005): ONLY put Teal
                # Mask Ogerpon ex down, a MAXIMUM of 2 in play, and nothing else. It is the best
                # attacker of the matchup (easy to charge and to retreat when
                # Brambleghast confuses it). OPENING EXCEPTION: if we have
                # no Ogerpon ex in play NOR in hand and there is still no
                # body in play (bench+active empty), we put down a starter with
                # priority Applin > Chikorita > anything, so we can get going.
                if op_is_comfey_deck:
                    _cf_og_field = field_counts.get(Teal_Mask_Ogerpon_ex, 0)
                    _cf_og_hand = hand_counts.get(Teal_Mask_Ogerpon_ex, 0)
                    if card.id == Teal_Mask_Ogerpon_ex:
                        score = 22000 if _cf_og_field < 2 else -1
                    else:
                        _cf_has_body = (
                            bench_count >= 1
                            or (my_state.active and my_state.active[0] is not None))
                        _cf_need_starter = (
                            _cf_og_field == 0 and _cf_og_hand == 0
                            and not _cf_has_body)
                        # ANTI-BENCH-OUT RELIEF (comfey autopsy jul 2026):
                        # with an EMPTY BENCH -- even if the active is still alive,
                        # which is exactly what `_cf_has_body` did not distinguish --
                        # putting a Basic down is not "advancing the plan", it is not
                        # losing the game on the spot: if they knock the active out
                        # and there is no relief, it is a bench-out and it is over. And
                        # unlike everything else this plan restricts,
                        # putting a body down from HAND does not thin the deck by
                        # a single card, which is the only thing the anti-mill defence
                        # has to protect; "vs Comfey only Teal
                        # Mask Ogerpon ex is put down" says WHAT we attack with, it does not force us
                        # to run out of bodies. Measured (n=250): the bench-out
                        # is 82% of our losses vs comfey (14 of 17;
                        # 5.6% of the games against 0.4-2% in the other
                        # matchups), with a median at turn 5. In the captured
                        # menu, with ZERO Pokemon on the bench, the PLAY of
                        # the Fezandipiti ex was worth 22000 and this branch crushed it
                        # to -1. BASICS only: a Stage 1/2 is not benched.
                        _cf_data = card_table.get(card.id)
                        _cf_es_basico = (
                            _cf_data is not None
                            and not getattr(_cf_data, 'stage1', False)
                            and not getattr(_cf_data, 'stage2', False))
                        _cf_relief_urgent = (bench_count == 0
                                              and _cf_es_basico)
                        if _cf_need_starter or _cf_relief_urgent:
                            if card.id == Applin:
                                score = 21000
                            elif card.id == Chikorita:
                                score = 20500
                            else:
                                score = 20000
                        else:
                            score = SCORE_VETO
        
            else:
                score = SCORE_ITEM_BASE
        
                supporter_boost = 500 if itchy_pollen_active else 0
                if card.id == Forest_of_Vitality:
                    # Priority 1 refactor: branch extracted to `_score_forest_of_vitality_play`.
                    score = _score_forest_of_vitality_play(ctx)
                elif card.id == Bug_Catching_Set:
                    # Priority 1 refactor: branch extracted to `_score_bug_catching_set_play`.
                    score = _score_bug_catching_set_play(ctx)
                elif card.id == Ultra_Ball:
                    # Priority 1 refactor (step 1): branch extracted to `_score_ultra_ball_play`.
                    score = _score_ultra_ball_play(ctx)
                elif card.id == Night_Stretcher:
                    # Priority 1 refactor: branch extracted to `_score_night_stretcher_play`.
                    score = _score_night_stretcher_play(ctx)
                elif card.id == Poke_Pad:
                    # Priority 1 refactor: branch extracted to `_score_poke_pad_play`.
                    score = _score_poke_pad_play(ctx)
                elif card.id == Unfair_Stamp:
                    # Priority 1 refactor: branch extracted to `_score_unfair_stamp_play`.
                    score = _score_unfair_stamp_play(ctx)
                elif card.id == Boss_Orders:
                    # Priority 1 refactor: branch extracted to `_score_boss_orders_play`.
                    score = _score_boss_orders_play(ctx)
                elif card.id == Xerosic_Machinations:
                    # Xerosic's Machinations (user): disruption of the opponent's hand,
                    # key vs Alakazam (Powerful Hand = 20 x card in their hand).
                    score = _score_xerosic_play(ctx)
                elif card.id == Lillie_Determination:
                    # Priority 1 refactor: branch extracted to `_score_lillie_determination_play`.
                    score = _score_lillie_determination_play(ctx)
                elif card.id == Dawn:
                    # Branch extracted to `_score_dawn_play` (shared with the
                    # `_supp_play_score` predictor).
                    score = _score_dawn_play(ctx)
                elif card.id == Lanas_Aid:
                    # Priority 1 refactor: branch extracted to `_score_lanas_aid_play`.
                    score = _score_lanas_aid_play(ctx, score)
        
                # Strategy vs Comfey (user, registro_005): the ONLY TRAINER
                # cards that are played are Lillie's Determination, Lana's Aid
                # and Boss's Orders (supporters), plus Ultra Ball and Night Stretcher
                # (the plan's items, Rule 5). The rest -- Dawn, Unfair Stamp, other
                # items and stadiums -- are NOT played: they are discarded/ignored (-1). The
                # rules specific to Lillie's (hand>=10) and Lana's (>=2 energies) were
                # already applied above; here only what is NOT on the list is vetoed.
                # Bug Catching Set IS ON the list (comfey autopsy jul
                # 2026): in 178/186 late sterile turns we had 0
                # Grass in HAND (Hammer/Fan dry us out and the BCS veto
                # cut off the supply) -> with no Grass there is no attachment NOR Teal
                # Dance and Myriad never reaches 3 energies: we lost on
                # prizes WITHOUT TAKING A SINGLE ONE in games of 40+ turns. BCS
                # brings up to 2 Grass/{G} Pokemon from the top 7; the cost of
                # thinning the deck by 2 cards is smaller than never attacking.
                #
                # EXCEPTION: THE COUNTER-STADIUM IS NEVER VETOED (user, log
                # 88359220 steps 60-76, LOST -- registro_008). The opponent
                # played the NEUTRALIZATION ZONE, which stops our ex Pokemon
                # attacking Pokemon that are NOT ex -- and their whole board is
                # non-ex (Comfey/Yveltal/Shaymin). With that, ALL our
                # ex attackers are switched off... including the Teal Mask
                # Ogerpon ex that IS the matchup's plan. We had TWO Forest
                # of Vitality in hand and the scorer gave them 28000 (the
                # urgency was correctly detected), but this allowlist
                # lowered them to -1 for not being on the list: the whole turn
                # was played under the lock and the opposing stadium stayed on the field.
                # The general -- deck-agnostic -- rule is that a matchup
                # whitelist describes WHICH cards advance the plan, and it
                # cannot veto the card that LIFTS AN OPPOSING LOCK that
                # disables that very plan: without removing the stadium there is no
                # plan to execute. The same criterion the first-turn stadium veto
                # already used (`_replace_opp_stadium_ok`) and the
                # DISCARD scorer, which protects exactly this card with
                # `_forest_counters_op_stadium` -- we were keeping in
                # hand a card that was then illegal to play.
                # Self-play gate vs deck/opponents/comfey_yveltal_nz.csv
                # (the deck from THIS game, harvested with
                # utils/harvest_opponent_deck.py; no opponent in the repo
                # ran the Zone and that is why the gate did not cover the case):
                # 94.2% with the fix vs 74.2% without it, 8000 games per
                # branch. +20 points.
                _removes_opponent_lock = (
                    data.cardType == CardType.STADIUM
                    and _counter_stadium_urgent(
                        neutralization_zone_active, watchtower_in_play,
                        AGENT_STATE.forest_in_play, _festival_lead_hostil))
                if (op_is_comfey_deck and score > 0
                        and not _removes_opponent_lock
                        and card.id not in (
                            Lillie_Determination, Lanas_Aid, Boss_Orders,
                            Ultra_Ball, Night_Stretcher, Bug_Catching_Set)):
                    score = SCORE_VETO
        
            # =========================================================
            # GRAND TREE (id 1249) in HAND -- it is only activated if the loaded
            # deck runs it; with the current deck.csv it is inert code, but
            # the request is that the logic should work "for any kind of
            # deck".
            # =========================================================
            if card.id == Grand_Tree:
                if state.stadiumPlayed or stadium_id == Grand_Tree:
                    score = SCORE_VETO
                elif _our_first_turn:
                    # We cannot evolve Basics on our first
                    # turn: putting it down now only GIVES it to the opponent, who
                    # will be able to use it on theirs.
                    score = SCORE_VETO
                elif _gt_planes(my_state, AGENT_STATE.ACTIVE_CARDS_IN_DECK,
                                field_counts, _our_first_turn,
                                vetoes_ex_stage=_gt_vetoes_ex_stage):
                    # There is a chain that pays off IN THIS VERY TURN: the
                    # stadium pays for itself. Above the Forest (which
                    # is worth at most 29000) because it produces a new body.
                    score = 30000
                elif _gt_root_in_play:
                    # The root is in play but came down today: the chain pays
                    # off next turn. It is still worth
                    # putting down now (and it removes the opposing stadium along the way).
                    score = 20000 if stadium_id != 0 else 12000
                else:
                    # With no root there is nothing to evolve: it is kept.
                    # It is only played to REMOVE an annoying opposing stadium.
                    score = (14000 if _counter_stadium_urgent(
                        neutralization_zone_active, watchtower_in_play,
                        AGENT_STATE.forest_in_play, _festival_lead_hostil) else SCORE_VETO)
        
            # Putting down the BASIC that serves as the root for Grand Tree (user's
            # rule: get it "so we can play the stadium afterwards"). An additive
            # and small bonus -- it breaks ties against other development
            # bodies without stepping on the existing engines -- and only
            # when there is not already a root in play.
            elif (_gt_quiere_basico and score > 0
                    and card.id in _gt_basics_ranking
                    and data is not None
                    and data.cardType == CardType.POKEMON):
                score += GT_PLAY_BASICO_BONUS
        return score
    finally:
        tc.b = b
        tc.bp = bp
        tc.card = card
        tc.data = data
        tc.pid = pid


__all__ = ['puntuar']
