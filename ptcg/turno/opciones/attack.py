"""Puntuacion de las opciones `ATTACK`.

Rama `o.type == OptionType.ATTACK` de la cadena de `agent()`, extraida VERBATIM.
Desempaqueta del contexto los 25 campos que lee y devuelve los
2 que reasigna; los demas quedan como estaban, igual que antes.
"""

from cg.api import AreaType, OptionType
from ptcg.calculo.carta import get_card, prize_count_op
from ptcg.cartas.ids import Applin, Basic_Grass_Energy, Chikorita, Fezandipiti_ex, Hydrapple_ex, Lillie_Determination, Meowth_ex, Pinsir, RETREAT_COST, SCORE_VETO, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball
from ptcg.estado.agente import ESTADO
from ptcg.estado.claves import ESTADO_MAZO


def puntuar(tc, o, score):
    """Devuelve el puntaje de `o`. Puede devolver `_SALTAR`."""
    _active_attack_wins_now = tc._active_attack_wins_now
    _active_snipe_ko_now = tc._active_snipe_ko_now
    _active_snipe_ko_prizes = tc._active_snipe_ko_prizes
    _conf_should_attack = tc._conf_should_attack
    _energy_in_hand = tc._energy_in_hand
    _nonex_active_hits_wall = tc._nonex_active_hits_wall
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
        if ESTADO.plan.attack_index >= 0:
        
            score += 100
        
        # Remate GANADOR con el ACTIVO (user, registro_009 paso 125 vs
        # Archaludon ex): si el ataque del activo NOQUEA y GANA la partida,
        # es la jugada de maxima prioridad -- por encima de cualquier carga /
        # desarrollo / Teal Dance. El tier de orden de jugada (abajo) tambien
        # la sube al maximo para que se ejecute YA y cierre la partida.
        if _active_attack_wins_now and ESTADO.plan.attacker == 0:
            score = 99000
        
        # SNIPE QUE COBRA PREMIO (user, registro_004 paso 54 vs Alakazam):
        # el Cruel Arrow del Fezandipiti ex activo no llega al muro de
        # delante pero NOQUEA en la banca. Ese ataque es un premio gratis --
        # no cuesta energia ni expone otro cuerpo -- y debe superar a las
        # jugadas "de relleno" que antes le ganaban el menu (pivotes de
        # retirada, cargas, desarrollo). Se queda por debajo de los remates
        # ganadores (99000) y de los pivotes de KO mayor (8900-9600), que
        # tienen sus propias guardas de premios.
        elif _active_snipe_ko_now and ESTADO.plan.attacker == 0:
            score = 8500 + 100 * _active_snipe_ko_prizes
        
        # REMATE SUICIDA (user, registro_016 paso 184 vs Marnie's Grimmsnarl,
        # EMPATE): el AUTO-DANO del ataque noquea a nuestro propio activo y,
        # con ese cadaver, el rival cobra el ultimo premio que le falta. Dos
        # frenos, con motivos distintos:
        #   * `_suicide_loses`: nuestro KO NO cierra nuestra cuenta, asi que
        #     atacar REGALA la partida. Se veta siempre -- pasar es
        #     estrictamente mejor que perder.
        #   * `_suicide_only_draws`: los dos KOs cierran las dos cuentas ->
        #     EMPATE. Solo se veta si existe el relevo de banca que gana
        #     LIMPIO (`_suicide_swap_win_promote`); sin relevo, el empate es
        #     el mejor resultado disponible y se ataca igual.
        # `plan.attacker == 0` acota los frenos al ataque DEL ACTIVO, que es
        # el unico cuerpo cuyo auto-dano midieron los flags.
        if (ESTADO.plan.attacker == 0
                and (_suicide_loses
                     or (_suicide_only_draws and _suicide_swap_win_promote))):
            score = SCORE_VETO
        
        if condition_risky_attack:
            if _conf_should_attack:
                score += 300
            elif ESTADO.plan.remain_hp is not None and ESTADO.plan.remain_hp <= 0:
                score += 50
            else:
                score -= 500
        
        _active_is_hydrapple = (my_state.active and my_state.active[0] is not None and
                                my_state.active[0].id == Hydrapple_ex)
        if _active_is_hydrapple and not itchy_pollen_active:
            _atk_is_ko = (ESTADO.plan.remain_hp is not None and ESTADO.plan.remain_hp <= 0)
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
                        ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0):
                    _hand_size_atk = len(my_state.hand) if my_state.hand else 0
                    if _hand_size_atk >= 3:
                        _can_add_energy = True
        
                if _can_add_energy:
        
                    score = SCORE_VETO
        
        if ESTADO.plan.attacker >= 1 and score > 0 and not _nonex_active_hits_wall:
            _plan_atk_is_winning = False
            if ESTADO.plan.remain_hp is not None and ESTADO.plan.remain_hp <= 0:
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
        
                    _atk_has_basic_mazo = False
                    for _atk_bid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                     Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir):
                        if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(_atk_bid, {}).get(ESTADO_MAZO, 0) > 0:
                            _atk_has_basic_mazo = True
                            break
                    if _atk_has_basic_mazo:
        
                        _atk_is_winning = False
                        if ESTADO.plan.remain_hp is not None and ESTADO.plan.remain_hp <= 0:
                            _op_act_atk = op_state.active[0] if op_state.active else None
                            if _op_act_atk is not None and op_prize <= prize_count_op(_op_act_atk):
                                _atk_is_winning = True
                        if not _atk_is_winning:
                            score = SCORE_VETO
        
        if (state.turn == 2 and not ESTADO.we_go_first
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
            # El ataque de Meowth ex (Tuck Tail) devuelve a Meowth ex y todas
            # sus cartas a la mano. Si Meowth ex es el UNICO Pokemon en juego
            # (banca vacia), atacar nos dejaria sin Pokemon en juego =>
            # perdemos la partida. Solo puede atacar si hay al menos un
            # Pokemon en banca al que retroceder.
            score = SCORE_VETO
        
        if op_active_dodge_immune:
            score = SCORE_VETO
        return score
    finally:
        tc._energy_in_hand = _energy_in_hand
        tc.pid = pid


__all__ = ['puntuar']
