"""Scoring of the `ATTACK` options.

The `o.type == OptionType.ATTACK` branch of the `agent()` chain, extracted
VERBATIM. It unpacks from the context the 25 fields it reads and returns the
2 it reassigns; the rest stay as they were, just like before.
"""

from cg.api import AreaType, OptionType
from ptcg.calc.card import get_card, prize_count_op
from ptcg.cards.ids import Applin, Basic_Grass_Energy, Chikorita, Fezandipiti_ex, Hydrapple_ex, Lillie_Determination, Meowth_ex, Pinsir, RETREAT_COST, SCORE_VETO, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball
from ptcg.state.agent_state import AGENT_STATE
from ptcg.state.zones import ZONE_DECK


def score_play(tc, o, score):
    """Returns the score of `o`. It may return `_SALTAR`."""
    _active_attack_wins_now = tc._active_attack_wins_now
    _active_snipe_ko_now = tc._active_snipe_ko_now
    _active_snipe_ko_prizes = tc._active_snipe_ko_prizes
    _conf_should_attack = tc._conf_should_attack
    _energy_in_hand = tc._energy_in_hand
    _nonex_active_hits_wall = tc._nonex_active_hits_wall
    _plan_relay_is_inert = tc._plan_relay_is_inert
    _suicide_loses = tc._suicide_loses
    _suicide_only_draws = tc._suicide_only_draws
    _suicide_swap_win_promote = tc._suicide_swap_win_promote
    bench_count = tc.bench_count
    condition_risky_attack = tc.condition_risky_attack
    field_counts = tc.field_counts
    hand_counts = tc.hand_counts
    itchy_pollen_active = tc.itchy_pollen_active
    my_index = tc.my_index
    my_prize = tc.my_prize
    my_state = tc.my_state
    obs = tc.obs
    op_active_dodge_immune = tc.op_active_dodge_immune
    op_prize = tc.op_prize
    op_state = tc.op_state
    pid = tc.pid
    select = tc.select
    state = tc.state

    try:
        score = 1000
        if AGENT_STATE.plan.attack_index >= 0:
        
            score += 100
        
        # WINNING finisher with the ACTIVE (user, registro_009 step 125 vs
        # Archaludon ex): if the active's attack KNOCKS OUT and WINS the game,
        # it is the highest priority play -- above any charge / development /
        # Teal Dance. The play-order tier (below) also raises it to the maximum
        # so it is executed NOW and closes the game.
        if _active_attack_wins_now and AGENT_STATE.plan.attacker == 0:
            score = 99000
        
        # SNIPE THAT TAKES A PRIZE (user, registro_004 step 54 vs Alakazam):
        # the Cruel Arrow of the active Fezandipiti ex does not reach the wall
        # in front but it KNOCKS OUT on the bench. That attack is a free prize
        # -- it costs no energy and exposes no other body -- and has to beat the
        # "filler" plays that used to win the menu over it (retreat pivots,
        # charges, development). It stays below the winning finishers (99000)
        # and the bigger-KO pivots (8900-9600), which have their own prize
        # guards.
        elif _active_snipe_ko_now and AGENT_STATE.plan.attacker == 0:
            score = 8500 + 100 * _active_snipe_ko_prizes
        
        # SUICIDAL FINISHER (user, registro_016 step 184 vs Marnie's Grimmsnarl,
        # DRAW): the attack's SELF-DAMAGE knocks out our own active and, with
        # that corpse, the opponent takes the last prize they were missing. Two
        # brakes, with different reasons:
        #   * `_suicide_loses`: our KO does NOT close our own count, so
        #     attacking GIVES AWAY the game. Always vetoed -- passing is
        #     strictly better than losing.
        #   * `_suicide_only_draws`: both KOs close both counts -> a DRAW. It is
        #     only vetoed if there is a benched relief that wins CLEANLY
        #     (`_suicide_swap_win_promote`); without relief, the draw is the
        #     best result available and we attack anyway.
        # `plan.attacker == 0` limits the brakes to the attack OF THE ACTIVE,
        # which is the only body whose self-damage the flags measured.
        if (AGENT_STATE.plan.attacker == 0
                and (_suicide_loses
                     or (_suicide_only_draws and _suicide_swap_win_promote))):
            score = SCORE_VETO
        
        if condition_risky_attack:
            if _conf_should_attack:
                score += 300
            elif AGENT_STATE.plan.remain_hp is not None and AGENT_STATE.plan.remain_hp <= 0:
                score += 50
            else:
                score -= 500
        
        _active_is_hydrapple = (my_state.active and my_state.active[0] is not None and
                                my_state.active[0].id == Hydrapple_ex)
        if _active_is_hydrapple and not itchy_pollen_active:
            _atk_is_ko = (AGENT_STATE.plan.remain_hp is not None and AGENT_STATE.plan.remain_hp <= 0)
            if not _atk_is_ko:
        
                _can_add_energy = False
        
                if (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                        not state.energyAttached):
                    _can_add_energy = True
        
                _ogerpon_count = field_counts.get(Teal_Mask_Ogerpon_ex, 0)
                _energy_in_hand = hand_counts.get(Basic_Grass_Energy, 0)
                if _ogerpon_count >= 1 and _energy_in_hand >= 1:
                    _can_add_energy = True
        
                if (hand_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1 and
                        bench_count < 5 and _energy_in_hand >= 1):
                    _can_add_energy = True
        
                if (hand_counts.get(Ultra_Ball, 0) >= 1 and
                        bench_count < 5 and _energy_in_hand >= 1 and
                        AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Teal_Mask_Ogerpon_ex, {}).get(ZONE_DECK, 0) > 0):
                    _hand_size_atk = len(my_state.hand) if my_state.hand else 0
                    if _hand_size_atk >= 3:
                        _can_add_energy = True
        
                if _can_add_energy:
        
                    score = SCORE_VETO
        
        # `_plan_relay_is_inert` (main.py, "the relay that takes no prize does not
        # earn the front spot") is the OTHER menu of the same pointer: the retreat
        # it was justifying is vetoed on that board, so the veto below has to lift
        # in the same breath. Left standing it would forbid the attack for the
        # sake of a retreat that no longer happens, and the turn would be left
        # with no play at all -- which is how registro_004 step 37 ended up
        # spending a Boss's Orders on nothing.
        if (AGENT_STATE.plan.attacker >= 1 and score > 0
                and not _nonex_active_hits_wall
                and not _plan_relay_is_inert):
            _plan_atk_is_winning = False
            if AGENT_STATE.plan.remain_hp is not None and AGENT_STATE.plan.remain_hp <= 0:
                _op_act_plan = op_state.active[0] if op_state.active else None
                if _op_act_plan is not None and my_prize <= prize_count_op(_op_act_plan):
                    _plan_atk_is_winning = True
            if not _plan_atk_is_winning:
        
                _plan_active = my_state.active[0] if my_state.active else None
                _plan_can_retreat = False
                if _plan_active is not None:
                    _plan_rc = RETREAT_COST.get(_plan_active.id, 1)
                    _plan_active_energy = len(_plan_active.energies)
                    if _plan_active_energy >= _plan_rc:
                        _plan_can_retreat = True
                if _plan_can_retreat:
                    score = SCORE_VETO
        
        if (bench_count == 0 and hand_counts.get(Ultra_Ball, 0) >= 1):
            _atk_hand_size = len(my_state.hand) if my_state.hand else 0
            if _atk_hand_size >= 3 and not itchy_pollen_active:
        
                _atk_has_basic_in_hand = any(
                    hand_counts.get(pid, 0) >= 1
                    for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir))
                if not _atk_has_basic_in_hand:
        
                    _atk_has_basic_in_deck = False
                    for _atk_bid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                     Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir):
                        if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(_atk_bid, {}).get(ZONE_DECK, 0) > 0:
                            _atk_has_basic_in_deck = True
                            break
                    if _atk_has_basic_in_deck:
        
                        _atk_is_winning = False
                        if AGENT_STATE.plan.remain_hp is not None and AGENT_STATE.plan.remain_hp <= 0:
                            _op_act_atk = op_state.active[0] if op_state.active else None
                            if _op_act_atk is not None and op_prize <= prize_count_op(_op_act_atk):
                                _atk_is_winning = True
                        if not _atk_is_winning:
                            score = SCORE_VETO
        
        if (state.turn == 2 and not AGENT_STATE.we_go_first
                and hand_counts.get(Lillie_Determination, 0) >= 1):
            _lillie_playable_now = any(
                _lo.type == OptionType.PLAY
                and get_card(obs, AreaType.HAND, _lo.index, my_index) is not None
                and get_card(obs, AreaType.HAND, _lo.index, my_index).id
                == Lillie_Determination
                for _lo in select.option)
            if _lillie_playable_now:
                score = SCORE_VETO
        
        _atk_active = my_state.active[0] if my_state.active else None
        if (_atk_active is not None and _atk_active.id == Meowth_ex
                and bench_count == 0):
            # Meowth ex's attack (Tuck Tail) returns Meowth ex and all of its
            # cards to the hand. If Meowth ex is the ONLY Pokemon in play (empty
            # bench), attacking would leave us with no Pokemon in play => we lose
            # the game. It can only attack if there is at least one Pokemon on the
            # bench to fall back to.
            score = SCORE_VETO
        
        if op_active_dodge_immune:
            score = SCORE_VETO
        return score
    finally:
        tc._energy_in_hand = _energy_in_hand
        tc.pid = pid


__all__ = ['score_play']
