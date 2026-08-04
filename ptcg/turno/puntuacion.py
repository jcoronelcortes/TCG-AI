"""Puntuacion de una opcion del menu: la cadena if/elif por `o.type`.

Extraida VERBATIM del bucle de `agent()` (Ola 6). Desempaqueta el contexto a
locales con los MISMOS nombres, de modo que el cuerpo es exactamente el que
estaba en main.py, y en `finally` devuelve al contexto las variables que la
cadena reasigna (las leen iteraciones posteriores).
"""

from cg.api import AreaType, CardType, EnergyType, OptionType, Pokemon, SelectContext, SpecialConditionType
from ptcg.calculo.carta import get_card, prize_count, prize_count_op
from ptcg.calculo.dano import _attacker_base_damage, _bench_attacker_can_ko, _ko_no_garantizado, _op_active_attack_damage_to, _our_effective_damage, _powerful_hand_proyectado, _snipe_target_score, _ventana_de_regalo
from ptcg.calculo.energia import _can_attack_eff, _grass_attach_route_open, _grass_attach_unit, _grass_mult, _ogerpon_base_phys_cap, _physical_energy, _retreat_grass_units
from ptcg.calculo.tablero import _active_of, _count_hand_play_options
from ptcg.cartas.grupos import GT_FETCH_BONUS, GT_PLAY_BASICO_BONUS, GT_SCORE_CADENA_COMPLETA, GT_SCORE_SOLO_FASE1
from ptcg.cartas.ids import Applin, Basic_Grass_Energy, Bayleef, Boss_Orders, Budew, Bug_Catching_Set, CUBCHOO_ALLOWED_PLAY_IDS, Chikorita, Cornerstone_Mask_Ogerpon_ex, Crustle_Fighting, Crustle_Grass, Cubchoo, DECK_ITEM_IDS, DUNSPARCE_IDS, Dawn, Dipplin, Dragapult_ex, Drednaw, Dwebble_Fighting, Dwebble_Grass, EEVEE_IDS, FEZ_DRAW_ABILITY_SCORE, Fezandipiti_ex, Forest_of_Vitality, Grand_Tree, Hydrapple_ex, LANA_SEL_INJUGABLE, LANA_SEL_PLANTA_DEMANDA, LANA_SEL_PLANTA_DESBLOQUEA, LANA_SEL_PLANTA_SOBRANTE, Lanas_Aid, Lillie_Determination, Meganium, Meowth_ex, Night_Stretcher, OP_BENCH_SNIPE_DAMAGE, OUR_ABILITY_IDS, OUR_EX_IDS, Pinsir, Poke_Pad, RETREAT_COST, RIPEN_HEAL_ABILITY_SCORE, RIPEN_HEAL_EX_ABILITY_SCORE, RIPEN_HEAL_TARGET_SCORE, SCORE_CARGA_ACTIVO_ATAQUE, SCORE_CARGA_ACTIVO_REMATE, SCORE_DEVELOP_BASE, SCORE_FORBID, SCORE_ITEM_BASE, SCORE_LOOKAHEAD_PROMOTE_KO, SCORE_LOOKAHEAD_PROMOTE_SAFE, SCORE_NEVER, SCORE_VETO, Sylveon, TAPU_WAIT_FOR_ITEMS_SCORE, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball, Unfair_Stamp, Xerosic_Machinations
from ptcg.cartas.lineas import _pokemon_injugable
from ptcg.cartas.puntuacion import MAIN_ATTACKERS, PROMO_DOOMED_PENALTY, PROMO_KO_BONUS, PROMO_MATCH_POINT_VETO, PROMO_PRIZE_PENALTY
from ptcg.cartas.tablas import card_table
from ptcg.decision.boss_orders import _AJUSTES_GUST_ESTORBO, _AJUSTES_GUST_OFENSIVO, _REGLAS_GUST_ESTORBO, _ctx_gust_objetivo
from ptcg.decision.bug_catching_set import _score_bug_catching_set_play
from ptcg.decision.disrupcion import _score_unfair_stamp_play, _score_xerosic_play
from ptcg.decision.meowth import _CtxMeowthFetch, _MEOWTH_FETCH_SUPPS, _REGLAS_MEOWTH_FETCH
from ptcg.decision.night_stretcher import _REGLAS_NS_APPLIN, _REGLAS_NS_BAYLEEF, _REGLAS_NS_CHIKORITA, _REGLAS_NS_DIPPLIN, _REGLAS_NS_FEZ, _REGLAS_NS_GRASS, _REGLAS_NS_HYDRAPPLE, _REGLAS_NS_MEGANIUM, _REGLAS_NS_MEOWTH, _REGLAS_NS_OGERPON, _REGLAS_NS_PINSIR, _REGLAS_NS_TAPU, _ctx_ns_fetch, _ns_motor_fez_vivo, _ns_motor_meowth_vivo
from ptcg.decision.poke_pad import _CtxPPFetch, _REGLAS_PP_FETCH, _score_poke_pad_play
from ptcg.decision.supporters import _score_dawn_play, _score_lanas_aid_play
from ptcg.decision.ultra_ball import _AJUSTES_UB_HYDRAPPLE, _CtxUBFetch, _REGLAS_UB_APPLIN, _REGLAS_UB_BAYLEEF, _REGLAS_UB_CHIKORITA, _REGLAS_UB_DIPPLIN, _REGLAS_UB_FEZ, _REGLAS_UB_HYDRAPPLE, _REGLAS_UB_MEGANIUM, _REGLAS_UB_MEOWTH, _REGLAS_UB_OGERPON, _REGLAS_UB_PINSIR, _REGLAS_UB_TAPU, _contra_estadio_urgente, _ctx_ub_fetch_hydrapple, _ctx_ub_fetch_meowth
from ptcg.estado.agente import ESTADO
from ptcg.estado.claves import ESTADO_MAZO, ESTADO_PREMIO
from ptcg.motor.reglas import _resolver_con_traza
from ptcg.turno.ctx_puntuacion import PuntuacionCtx, REASIGNADAS  # noqa: F401


# Centinela: la cadena ya hizo `scores.append` por su cuenta (lo que en el
# bucle original era un `continue`).
_SALTAR = object()


def puntuar_opcion(tc, o, score):
    """Puntaje de la opcion `o`. Mayor = mejor; negativo = veto.

    Puede devolver `_SALTAR`, y entonces el llamador NO debe apilar nada.
    """
    # Desempaquetado: mismos nombres que en agent().
    _SALTAR = tc._SALTAR
    _TABLA_BCS_FETCH = tc._TABLA_BCS_FETCH
    _TABLA_DAWN_FETCH = tc._TABLA_DAWN_FETCH
    _ability_order_veto = tc._ability_order_veto
    _ability_unlock_retreat_attack = tc._ability_unlock_retreat_attack
    _ability_unlock_retreat_ko = tc._ability_unlock_retreat_ko
    _active_already_kos = tc._active_already_kos
    _active_attack_wins_now = tc._active_attack_wins_now
    _active_cant_attack_this_turn = tc._active_cant_attack_this_turn
    _active_doomed_real = tc._active_doomed_real
    _active_hydra_cannot_ko = tc._active_hydra_cannot_ko
    _active_hydra_ready = tc._active_hydra_ready
    _active_needs_energy = tc._active_needs_energy
    _active_ready_attacker = tc._active_ready_attacker
    _active_snipe_ko_now = tc._active_snipe_ko_now
    _active_snipe_ko_prizes = tc._active_snipe_ko_prizes
    _alakazam_pivot_1prize = tc._alakazam_pivot_1prize
    _alk_ld_engine_vivo = tc._alk_ld_engine_vivo
    _ara_act = tc._ara_act
    _atk = tc._atk
    _attach_cede_a_teal_dance = tc._attach_cede_a_teal_dance
    _attach_enable_retreat_attack = tc._attach_enable_retreat_attack
    _attach_enable_retreat_ko = tc._attach_enable_retreat_ko
    _b = tc._b
    _bcs_playable_in_hand = tc._bcs_playable_in_hand
    _bdg_retreat_ko = tc._bdg_retreat_ko
    _bench_attacker_ready = tc._bench_attacker_ready
    _bench_has_chargeable = tc._bench_has_chargeable
    _best_promote_card = tc._best_promote_card
    _best_promote_key = tc._best_promote_key
    _best_supp_in_hand_val = tc._best_supp_in_hand_val
    _best_supp_in_mazo_id = tc._best_supp_in_mazo_id
    _best_supp_in_mazo_val = tc._best_supp_in_mazo_val
    _bp = tc._bp
    _bp_e = tc._bp_e
    _bp_eff = tc._bp_eff
    _carga_activo_falta = tc._carga_activo_falta
    _carga_activo_habilita_ataque = tc._carga_activo_habilita_ataque
    _carga_activo_remata = tc._carga_activo_remata
    _cm_use_ex = tc._cm_use_ex
    _conf_can_attack_pkmn = tc._conf_can_attack_pkmn
    _conf_is_matchup_attacker = tc._conf_is_matchup_attacker
    _conf_should_attack = tc._conf_should_attack
    _conf_should_retreat = tc._conf_should_retreat
    _cubchoo_lock_stuck = tc._cubchoo_lock_stuck
    _cuerpo_condenado = tc._cuerpo_condenado
    _dc = tc._dc
    _deny_evo_via_boss = tc._deny_evo_via_boss
    _descuadre_matchup = tc._descuadre_matchup
    _dmg_vs_wall = tc._dmg_vs_wall
    _dragapult_no_tapu = tc._dragapult_no_tapu
    _e = tc._e
    _eff = tc._eff
    _energy_in_hand = tc._energy_in_hand
    _energy_score_base = tc._energy_score_base
    _enough_after_priorities = tc._enough_after_priorities
    _enough_for_both = tc._enough_for_both
    _evo_huerfanos = tc._evo_huerfanos
    _evo_necesarios = tc._evo_necesarios
    _ex_stuck_promo_ready = tc._ex_stuck_promo_ready
    _extra_energy_enables_ko = tc._extra_energy_enables_ko
    _festival_lead_hostil = tc._festival_lead_hostil
    _forced_ko_promote = tc._forced_ko_promote
    _grass_anywhere_enables_syrup_ko = tc._grass_anywhere_enables_syrup_ko
    _grass_enables_promote_ko = tc._grass_enables_promote_ko
    _gt_plan = tc._gt_plan
    _gt_planes = tc._gt_planes
    _gt_planes_turno = tc._gt_planes_turno
    _gt_prompt_si_no = tc._gt_prompt_si_no
    _gt_quiere_basico = tc._gt_quiere_basico
    _gt_raiz_en_juego = tc._gt_raiz_en_juego
    _gt_ranking_basicos = tc._gt_ranking_basicos
    _gt_score_seleccion = tc._gt_score_seleccion
    _gt_veta_etapa_ex = tc._gt_veta_etapa_ex
    _gust_2prize_via_boss = tc._gust_2prize_via_boss
    _has_bench_attacker = tc._has_bench_attacker
    _hydra_pivot_active = tc._hydra_pivot_active
    _hydra_wall_pivot = tc._hydra_wall_pivot
    _hydrapple_bench_needs_energy = tc._hydrapple_bench_needs_energy
    _ko_prefer_basic_general = tc._ko_prefer_basic_general
    _lana_orden_planta = tc._lana_orden_planta
    _lana_plan = tc._lana_plan
    _ld_lillie_ofrecida = tc._ld_lillie_ofrecida
    _lillie_blocks_fez_ability = tc._lillie_blocks_fez_ability
    _lillie_protected_once = tc._lillie_protected_once
    _lucario_ko_prefer_basic = tc._lucario_ko_prefer_basic
    _lucario_other_sac_available = tc._lucario_other_sac_available
    _lucario_riolu_gust = tc._lucario_riolu_gust
    _lucario_sac_available = tc._lucario_sac_available
    _lucario_sac_context = tc._lucario_sac_context
    _lucario_sac_pivot = tc._lucario_sac_pivot
    _mega_line_active = tc._mega_line_active
    _meowth_antidonk_now = tc._meowth_antidonk_now
    _meowth_devel_lillie = tc._meowth_devel_lillie
    _meowth_fetch_pierde_el_turno = tc._meowth_fetch_pierde_el_turno
    _meowth_fetch_redundante = tc._meowth_fetch_redundante
    _meowth_fetch_ya_en_mano = tc._meowth_fetch_ya_en_mano
    _meowth_immune_boss_engine = tc._meowth_immune_boss_engine
    _meowth_ld_free = tc._meowth_ld_free
    _meowth_skip_fetch = tc._meowth_skip_fetch
    _no_second_attacker_path = tc._no_second_attacker_path
    _nonex_active_hits_wall = tc._nonex_active_hits_wall
    _ogerpon_lethal_focus_serial = tc._ogerpon_lethal_focus_serial
    _op_act = tc._op_act
    _op_best_damage_vs = tc._op_best_damage_vs
    _op_counter_threat_vs = tc._op_counter_threat_vs
    _our_first_action_turn = tc._our_first_action_turn
    _our_first_turn = tc._our_first_turn
    _p = tc._p
    _prize_denial_pivot = tc._prize_denial_pivot
    _promo_kos_op = tc._promo_kos_op
    _promo_min_prize = tc._promo_min_prize
    _promo_op_act = tc._promo_op_act
    _promo_survives = tc._promo_survives
    _promo_survivors = tc._promo_survivors
    _promote_setup_ko_attacker = tc._promote_setup_ko_attacker
    _ready_attacker_count = tc._ready_attacker_count
    _refresh_promote_prefer_basic = tc._refresh_promote_prefer_basic
    _reserve_energy_for_hydra_evolve = tc._reserve_energy_for_hydra_evolve
    _reserve_hydra_active_charge = tc._reserve_hydra_active_charge
    _ripen_bench_ready_pivot = tc._ripen_bench_ready_pivot
    _ripen_bench_tapu_ko_pivot = tc._ripen_bench_tapu_ko_pivot
    _ripen_heal_ex = tc._ripen_heal_ex
    _ripen_heal_serial = tc._ripen_heal_serial
    _ripen_retreat_ko_pivot = tc._ripen_retreat_ko_pivot
    _score_boss_orders_play = tc._score_boss_orders_play
    _score_forest_of_vitality_play = tc._score_forest_of_vitality_play
    _score_lillie_determination_play = tc._score_lillie_determination_play
    _score_night_stretcher_play = tc._score_night_stretcher_play
    _score_ultra_ball_play = tc._score_ultra_ball_play
    _sel_active_cant_attack = tc._sel_active_cant_attack
    _self_ko_by_own_attack = tc._self_ko_by_own_attack
    _sid = tc._sid
    _stamp_blocks_supp_chain = tc._stamp_blocks_supp_chain
    _suicide_loses = tc._suicide_loses
    _suicide_only_draws = tc._suicide_only_draws
    _suicide_swap_win_promote = tc._suicide_swap_win_promote
    _supp_values = tc._supp_values
    _tapu_future_charge = tc._tapu_future_charge
    _tapu_sac_enable_retreat = tc._tapu_sac_enable_retreat
    _tapu_sac_pivot = tc._tapu_sac_pivot
    _tapu_sac_priority = tc._tapu_sac_priority
    _tb_req = tc._tb_req
    _teal_dance_ko_pivot = tc._teal_dance_ko_pivot
    _teal_dance_slots = tc._teal_dance_slots
    _teal_wall_pivot = tc._teal_wall_pivot
    _ub_meowth_para_manana = tc._ub_meowth_para_manana
    _wall_ko_promote = tc._wall_ko_promote
    _win_ko_active_via_promote = tc._win_ko_active_via_promote
    _win_via_boss_gust = tc._win_via_boss_gust
    active_hp_ratio = tc.active_hp_ratio
    active_ko_likely = tc.active_ko_likely
    b = tc.b
    bench_count = tc.bench_count
    bp = tc.bp
    budew_on_op_field = tc.budew_on_op_field
    can_attack = tc.can_attack
    can_switch = tc.can_switch
    card = tc.card
    condition_blocks_action = tc.condition_blocks_action
    condition_risky_attack = tc.condition_risky_attack
    condition_urgency = tc.condition_urgency
    context = tc.context
    ctx = tc.ctx
    data = tc.data
    discard_counts = tc.discard_counts
    energy_count = tc.energy_count
    energy_score = tc.energy_score
    estimated_op_damage = tc.estimated_op_damage
    evaluate_supporters = tc.evaluate_supporters
    field_counts = tc.field_counts
    hand_counts = tc.hand_counts
    has_condition = tc.has_condition
    has_hydrapple = tc.has_hydrapple
    has_ogerpon = tc.has_ogerpon
    has_switch_card = tc.has_switch_card
    is_confused = tc.is_confused
    itchy_pollen_active = tc.itchy_pollen_active
    meowth_ability_lock = tc.meowth_ability_lock
    my_index = tc.my_index
    my_prize = tc.my_prize
    my_state = tc.my_state
    neutralization_zone_active = tc.neutralization_zone_active
    obs = tc.obs
    op_active_dodge_immune = tc.op_active_dodge_immune
    op_active_is_kangaskhan = tc.op_active_is_kangaskhan
    op_bench_snipe_threat = tc.op_bench_snipe_threat
    op_double_attack_pending = tc.op_double_attack_pending
    op_has_ability_immune_active = tc.op_has_ability_immune_active
    op_has_dragapult = tc.op_has_dragapult
    op_has_dreepy_line = tc.op_has_dreepy_line
    op_has_dwebble_bench = tc.op_has_dwebble_bench
    op_has_ethan_preevo = tc.op_has_ethan_preevo
    op_has_ex_immune_active = tc.op_has_ex_immune_active
    op_has_ex_immune_bench = tc.op_has_ex_immune_bench
    op_has_froslass = tc.op_has_froslass
    op_has_latias_ex = tc.op_has_latias_ex
    op_has_mega_starmie_active = tc.op_has_mega_starmie_active
    op_has_typhlosion = tc.op_has_typhlosion
    op_is_aggro_deck = tc.op_is_aggro_deck
    op_is_alakazam_deck = tc.op_is_alakazam_deck
    op_is_beedrill_deck = tc.op_is_beedrill_deck
    op_is_comfey_deck = tc.op_is_comfey_deck
    op_is_control_deck = tc.op_is_control_deck
    op_is_cubchoo_deck = tc.op_is_cubchoo_deck
    op_is_dragapult_dusknoir = tc.op_is_dragapult_dusknoir
    op_is_drednaw_deck = tc.op_is_drednaw_deck
    op_is_fire_deck = tc.op_is_fire_deck
    op_is_greninja_deck = tc.op_is_greninja_deck
    op_is_hop_deck = tc.op_is_hop_deck
    op_is_iron_thorns_deck = tc.op_is_iron_thorns_deck
    op_is_lucario_deck = tc.op_is_lucario_deck
    op_is_mirror = tc.op_is_mirror
    op_is_sylveon_deck = tc.op_is_sylveon_deck
    op_kang_ko_target = tc.op_kang_ko_target
    op_prize = tc.op_prize
    op_state = tc.op_state
    pid = tc.pid
    pokemon = tc.pokemon
    scores = tc.scores
    select = tc.select
    stadium_id = tc.stadium_id
    state = tc.state
    total_grass = tc.total_grass
    watchtower_in_play = tc.watchtower_in_play

    try:
        if o.type == OptionType.NUMBER:
            score = o.number
    
        elif o.type == OptionType.YES:
            score = 1
            if _gt_prompt_si_no:
                # Los dos pasos de Grand Tree son opcionales ("puede buscar"),
                # asi que el simulador puede pedir confirmacion. Se acepta
                # SIEMPRE: no hay forma fiable de saber si el prompt es el paso
                # 1 (buscar la Fase 1) o el paso 2 (la Fase 2), y decir "no" al
                # paso 1 tira la cadena entera. La preferencia por NO construir
                # una Etapa 2 ex contra un rival que las inmuniza se aplica
                # donde si es seguro: en la ELECCION del objetivo
                # (`_gt_planes(..., veta_etapa_ex=True)` deja esa cadena en
                # Fase 1 y hace ganar a la linea no-ex).
                score = 10000
            elif context == SelectContext.ACTIVATE:
    
                score = 10
                if _meowth_skip_fetch:
                    score = SCORE_VETO
            elif context == SelectContext.IS_FIRST:
    
                score = SCORE_VETO
                ESTADO.we_go_first = True
            elif context == SelectContext.COIN_HEAD:
    
                score = 2
    
        elif o.type == OptionType.NO:
            if _gt_prompt_si_no:
                score = SCORE_VETO
            elif context == SelectContext.IS_FIRST:
                score = 2
                ESTADO.we_go_first = False
            elif context == SelectContext.ACTIVATE and _meowth_skip_fetch:
                score = 10
    
        elif o.type == OptionType.CARD:
            card = get_card(obs, o.area, o.index, o.playerIndex)
            if card is not None:
                energy_count = 0
                if isinstance(card, Pokemon):
                    energy_count = len(card.energies)
    
                if (select.effect is not None
                        and select.effect.id == Grand_Tree
                        and getattr(o, 'playerIndex', my_index) == my_index):
                    # Sub-selecciones de la habilidad de Grand Tree (que Basico
                    # evoluciona / que Fase 1 y Fase 2 se traen del mazo). Van
                    # ANTES de cualquier otro handler de CARD: comparten
                    # contexto (TO_FIELD / EVOLVES_FROM / TO_HAND...) con
                    # selecciones de otras cartas y sin este corte caerian en el
                    # scorer equivocado.
                    scores.append(_gt_score_seleccion(
                        o, card, _gt_plan, _gt_planes_turno, my_state,
                        field_counts))
                    return _SALTAR   # ya hizo scores.append por su cuenta
    
                if (context == SelectContext.DAMAGE
                        and isinstance(card, Pokemon)
                        and getattr(o, 'playerIndex', my_index) != my_index):
                    # Seleccion de OBJETIVO de dano de un ataque que golpea a
                    # cualquier Pokemon rival (p.ej. Cruel Arrow de Fezandipiti
                    # ex, 100 fijo). Antes NO habia handler para este contexto y
                    # el argmax caia en la opcion 0 (el activo) (user,
                    # registro_015 paso 139 vs Crustle, PERDIDA: se apuntaba al
                    # Crustle activo, INMUNE al dano de nuestros ex por su
                    # habilidad, con un Dwebble de 70 HP noqueable en banca).
                    # Regla: evaluar TODOS los Pokemon rivales con el dano
                    # EFECTIVO (`_our_effective_damage` aplica la inmunidad ex
                    # de Crustle, Neutralization Zone, debilidad/resistencia...):
                    # 1) mejor un objetivo NOQUEADO (mas premios > mas cargado >
                    #    mas vida = mas desarrollado); 2) si nadie muere, chip
                    #    al que MAS cerca queda del KO; 3) inmunes (dano 0) solo
                    #    como ultimo recurso (la seleccion es obligatoria).
                    # El ranking vive en `_snipe_target_score`, la MISMA funcion
                    # que usa el planificador para decidir si atacar en vez de
                    # retirar (`_snipe_best_target`): asi el objetivo que hace
                    # que valga la pena atacar es exactamente el que se acaba
                    # eligiendo aqui, sin que las dos escalas puedan divergir.
                    _dmg_att = (my_state.active[0]
                                if my_state.active and my_state.active[0] is not None
                                else None)
                    _dmg_eff = 0
                    if _dmg_att is not None:
                        _dmg_e = len(_dmg_att.energies) * _grass_mult()
                        _dmg_base = _attacker_base_damage(
                            _dmg_att.id, card, _dmg_e,
                            grass_scale=total_grass,
                            teal_self_energy=_dmg_e,
                            bench_count=bench_count)
                        _dmg_eff = _our_effective_damage(
                            _dmg_att, card, _dmg_base, ESTADO.meganium_in_play,
                            neutralization_zone_active)
                    score = _snipe_target_score(_dmg_eff, card)
                    scores.append(score)
                    return _SALTAR   # ya hizo scores.append por su cuenta
    
                if context == SelectContext.SWITCH or context == SelectContext.TO_ACTIVE:
                    if o.playerIndex == my_index and _lucario_sac_context:
                        # Promover un sacrificio de 1 premio en vez del Ogerpon ex,
                        # para entregar solo 1 premio a Mega Lucario (no 2). Por
                        # defecto conservamos Tapu Bulu y sacrificamos antes
                        # Applin > Chikorita; solo cuando Tapu Bulu es realmente
                        # prioritario (rival con proteccion a ex o motor Hydrapple
                        # ex + Meganium) se sacrifica Tapu Bulu primero.
                        if _tapu_sac_priority:
                            if card.id == Tapu_Bulu:
                                score = 6000
                            elif card.id == Applin:
                                score = 5500
                            elif card.id == Chikorita:
                                score = 5000
                            else:
                                score = 100
                        else:
                            if card.id == Applin:
                                score = 6000
                            elif card.id == Chikorita:
                                score = 5500
                            elif card.id == Tapu_Bulu:
                                score = 200
                            else:
                                score = 100
                    elif o.playerIndex == my_index:
    
                        # Listo-para-atacar via energia efectiva (fuente unica:
                        # ATTACK_ENERGY_REQ). Ahora incluye Pinsir (antes omitido).
                        _can_attack_now = (
                            card.id in MAIN_ATTACKERS
                            and _can_attack_eff(card.id, energy_count))
    
                        _ns_grass_recover_switch = (
                            hand_counts.get(Night_Stretcher, 0) >= 1 and
                            discard_counts.get(Basic_Grass_Energy, 0) >= 1)
                        _grass_attachable_switch = (
                            hand_counts.get(Basic_Grass_Energy, 0) >= 1 or
                            _ns_grass_recover_switch)
                        _forced_promote_switch = not my_state.active
                        _can_attack_with_attach = _can_attack_now
                        if (not _can_attack_now and _grass_attachable_switch
                                and (not state.energyAttached or _forced_promote_switch)):
                            _pkmn_eff_plus1 = energy_count + _grass_attach_unit()
                            if card.id == Hydrapple_ex:
                                _can_attack_with_attach = (_pkmn_eff_plus1 >= 2)
                            elif card.id == Dipplin:
                                _can_attack_with_attach = True
                            elif card.id == Teal_Mask_Ogerpon_ex:
                                _can_attack_with_attach = (_pkmn_eff_plus1 >= 3)
                            elif card.id == Tapu_Bulu:
                                _can_attack_with_attach = (_pkmn_eff_plus1 >= 4)
                            elif card.id == Fezandipiti_ex:
                                _can_attack_with_attach = (_pkmn_eff_plus1 >= 3)
                            elif card.id == Meganium:
                                _can_attack_with_attach = (_pkmn_eff_plus1 >= 4)
    
                        if _can_attack_now:
                            score = 500
                        elif _can_attack_with_attach:
                            score = 350
                        else:
                            score = 100
    
                        if card.hp is not None:
                            score += card.hp // 10
    
                        score += energy_count
    
                        # PROMOVER AL REMATADOR QUE GANA LA PARTIDA (user,
                        # registro_016 paso 184 vs Marnie's Grimmsnarl, EMPATE).
                        # Al retirar, la promocion elegia por "mas tanque que
                        # pueda atacar": subia el Hydrapple ex de 290 PV (350 +
                        # 29 + 60 + 250 = 689) por delante del Teal Mask Ogerpon
                        # ex ya cargado (500 + 10 + 6 = 516)... y el Hydrapple sin
                        # energia no remataba, mientras el Ogerpon a 6 energias
                        # cerraba la partida con Myriad Leaf Shower. Cuando el
                        # candidato NOQUEA al activo rival y ese KO nos da los
                        # premios que faltan (o el rival no tiene banca para
                        # reemplazarlo), promoverlo es decisivo: no hay turno
                        # siguiente que proteger.
                        #
                        # Solo en `SelectContext.SWITCH`, que es la promocion de
                        # NUESTRA retirada voluntaria: ocurre siempre en nuestro
                        # turno y antes de atacar, asi que el remate esta
                        # disponible de verdad. La promocion FORZADA tras un KO
                        # (TO_ACTIVE) puede caer en el turno RIVAL, donde no se
                        # ataca y lo correcto sigue siendo el muro; por eso no se
                        # incluye. `_ko_no_garantizado` y el auto-dano del propio
                        # candidato se comprueban igual que en el resto de
                        # evaluadores de remate: un rematador que se suicida y con
                        # ello cierra la cuenta del rival no gana nada.
                        if context == SelectContext.SWITCH:
                            _wp_opa = _active_of(op_state)
                            _wp_opa_hp = (_wp_opa.hp or 0) if _wp_opa is not None else 0
                            _wp_e = energy_count
                            if (_wp_opa is not None and _wp_opa_hp > 0
                                    and (_can_attack_now or _can_attack_with_attach)
                                    and not _ko_no_garantizado(_wp_opa)
                                    and (my_prize <= prize_count_op(_wp_opa)
                                         or not any(b is not None
                                                    for b in (op_state.bench or [])))
                                    and not (_self_ko_by_own_attack(card, incierto=True)
                                             and op_prize <= prize_count(card))):
                                if not _can_attack_now:
                                    _wp_e = energy_count + _grass_attach_unit()
                                _wp_base = _attacker_base_damage(
                                    card.id, _wp_opa, _wp_e * _grass_mult(),
                                    grass_scale=total_grass, teal_self_energy=_wp_e,
                                    bench_count=bench_count)
                                if (_wp_base > 0 and _our_effective_damage(
                                        card, _wp_opa, _wp_base, ESTADO.meganium_in_play,
                                        neutralization_zone_active) >= _wp_opa_hp):
                                    # Con la energia YA encima el remate es seguro;
                                    # si depende de un adjunte pendiente, vale algo
                                    # menos (pero sigue por encima de todo bono de
                                    # muro/desarrollo de este bloque).
                                    score += 20000 if _can_attack_now else 18000
    
                        # Negacion de premios al promover (user): si al rival le
                        # faltan <=2 premios para ganar, preferir DECISIVAMENTE
                        # subir un cuerpo de 1 premio que YA pueda atacar antes que
                        # un ex (2 premios), para que un KO rival no cierre la
                        # partida. Solo BONIFICA a los no-ex atacantes (nunca
                        # penaliza al ex): si el unico cuerpo capaz de atacar es un
                        # ex, se sigue promoviendo con normalidad.
                        if (op_prize <= 2 and _can_attack_now
                                and prize_count(card) <= 1):
                            score += 3000
    
                        # DESCUADRE DE PREMIOS al promover (user, vs Raging Bolt y
                        # Mega Abomasnow ex). Si NADIE en la banca puede noquear al
                        # activo rival este turno, el promovido va a caer ante su
                        # one-shot: subir el cuerpo de 1 premio (muro barato), nunca
                        # un ex de 2. Con un atacante capaz de noquear, la promocion
                        # normal (que ya lo prefiere) sigue mandando.
                        if _descuadre_matchup and prize_count(card) <= 1:
                            _rb_opa = _active_of(op_state)
                            _rb_alguien_ko = (
                                _rb_opa is not None
                                and _bench_attacker_can_ko(
                                    my_state, _rb_opa, ESTADO.meganium_in_play,
                                    total_grass, bench_count, total_grass,
                                    neutralization_zone_active))
                            if not _rb_alguien_ko:
                                score += 2500
    
                        # Al retirar un activo CONFUNDIDO, priorizar subir a un
                        # atacante del matchup que YA pueda atacar (p.ej. Dipplin
                        # vs Crustle) por encima de un muro que no ataca este
                        # turno (p.ej. un ex al que Crustle es inmune). Evita
                        # subir al Pokemon equivocado tras curar la confusion.
                        if (is_confused and _can_attack_now
                                and _conf_is_matchup_attacker(card.id)):
                            score += 2000
    
                        if not _can_attack_now and not _can_attack_with_attach:
                            if card.hp is not None:
    
                                score += card.hp // 5
    
                                if estimated_op_damage > 0 and card.hp > estimated_op_damage:
                                    score += 80
                                elif estimated_op_damage > 0 and card.hp <= estimated_op_damage:
                                    score -= 20
    
                        if _teal_wall_pivot and card.id == Hydrapple_ex:
                            # Pivote defensivo con Teal Dance: subir al cuerpo mas
                            # fuerte (Hydrapple ex, muro de 330) aunque no pueda
                            # atacar aun. Bono decisivo para elegirlo al promover.
                            score += 4000
    
                        if card.id == Hydrapple_ex:
                            score += 60
                            if _can_attack_now:
    
                                _syrup_dmg = 30 + 30 * total_grass
                                score += min(_syrup_dmg // 10, 30)
                            elif _can_attack_with_attach:
    
                                score += 250
                            if _cm_use_ex and (_can_attack_now or _can_attack_with_attach):
                                # Matchup Crustle + Mega Kangaskhan ex: subir
                                # NUESTRO ex para atacar al Mega y conservar los
                                # no-ex para Crustle.
                                score += 500
                        elif card.id == Tapu_Bulu:
                            if _can_attack_now:
                                score += 50
                            if _cm_use_ex:
                                # Reservar Tapu Bulu para Crustle (lo noquea de un
                                # golpe): NO subirlo contra el Mega Kangaskhan ex,
                                # que atacamos con nuestros ex.
                                score -= 500
                            elif op_has_ex_immune_active or ESTADO.op_is_crustle_deck:
                                score += 80
                            if ESTADO.op_is_cornerstone_deck:
    
                                score += 120
                        elif card.id == Teal_Mask_Ogerpon_ex:
                            score += 30
                            if _cm_use_ex and (_can_attack_now or _can_attack_with_attach):
                                # Subir NUESTRO ex para atacar al Mega Kangaskhan
                                # ex y conservar los no-ex (Tapu Bulu) para Crustle.
                                score += 500
                        elif card.id == Dipplin:
                            score += 15
                            if op_has_ex_immune_active:
                                score += 40
    
                            if (ESTADO.op_is_crustle_deck and state.retreated and
                                    energy_count == 0 and
                                    hand_counts.get(Night_Stretcher, 0) >= 1 and
                                    hand_counts.get(Basic_Grass_Energy, 0) == 0 and
                                    discard_counts.get(Basic_Grass_Energy, 0) >= 1):
                                score += 5000
                        elif card.id == Meganium:
                            if (op_has_ex_immune_active or ESTADO.op_is_crustle_deck) and _can_attack_now:
    
                                score += 120
                            else:
                                score -= 80
                        elif card.id == Meowth_ex:
                            score -= 100
                        elif card.id == Fezandipiti_ex:
                            score -= 100
                        elif card.id == Chikorita:
                            score -= 60
                        elif card.id == Bayleef:
                            score -= 50
                        elif card.id == Applin:
                            score -= 70
    
                        # Regla (user, log 86607718 turno 2, vs Crustle): al
                        # PROMOVER (p.ej. tras retirar un Chikorita activo) cuando
                        # NINGUN cuerpo puede atacar al muro este turno, subir un EX
                        # tanque como muro desechable -- primer candidato Teal Mask
                        # Ogerpon ex (210 HP) -- y RESERVAR a Tapu Bulu en la banca
                        # (nuestro atacante clave que noquea a Crustle) para cargarlo
                        # a salvo. Solo cuando NADIE ataca: si Tapu ya puede atacar,
                        # su +80 vs Crustle sigue mandando. No aplica al reparto
                        # Crustle + Mega Kangaskhan ex (_cm_use_ex).
                        if (ESTADO.op_is_crustle_deck and not _cm_use_ex
                                and not _can_attack_now
                                and not _can_attack_with_attach):
                            if card.id == Teal_Mask_Ogerpon_ex:
                                score += 300
                            elif card.id == Tapu_Bulu:
                                score -= 300
    
                        _op_act_wsel = op_state.active[0] if op_state.active else None
                        if _op_act_wsel is not None and isinstance(card, Pokemon):
                            _op_act_wsel_data = card_table.get(_op_act_wsel.id)
                            _card_wsel_data = card_table.get(card.id)
                            if (_card_wsel_data is not None and getattr(_card_wsel_data, 'weakness', None) is not None and
                                    _op_act_wsel_data is not None and
                                    getattr(_op_act_wsel_data, 'energyType', None) == _card_wsel_data.weakness):
                                score -= 250
    
                            _op_dmg_vs_card = max(_op_best_damage_vs(card),
                                                  _op_counter_threat_vs(card))
                            if _op_dmg_vs_card > 0:
                                if _op_dmg_vs_card >= card.hp:
                                    score -= SCORE_LOOKAHEAD_PROMOTE_KO
                                elif _op_dmg_vs_card <= card.hp * 0.4:
                                    score += SCORE_LOOKAHEAD_PROMOTE_SAFE
    
                        _forest_available = (ESTADO.forest_in_play or
                                             hand_counts.get(Forest_of_Vitality, 0) >= 1)
    
                        if card.id == Applin and _forest_available:
    
                            _has_dipplin_hand = (hand_counts.get(Dipplin, 0) >= 1)
                            _has_hydrapple_hand = (hand_counts.get(Hydrapple_ex, 0) >= 1)
                            _has_energy_hand = (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                                                not state.energyAttached)
                            if _has_dipplin_hand and _has_hydrapple_hand:
    
                                _evo_bonus = 600
                                if _has_energy_hand:
                                    _evo_bonus += 150
    
                                _bench_grass_energy = 0
                                for _bp in my_state.bench:
                                    if _bp is not None and _bp.id != card.id:
                                        _bench_grass_energy += len(_bp.energies)
                                if _bench_grass_energy >= 1:
                                    _evo_bonus += 100
    
                                _mega_evolvable = (ESTADO.meganium_in_play or
                                    (hand_counts.get(Meganium, 0) >= 1 and
                                     (field_counts.get(Bayleef, 0) >= 1 or
                                      (field_counts.get(Chikorita, 0) >= 1 and
                                       hand_counts.get(Bayleef, 0) >= 1 and _forest_available))))
                                if _mega_evolvable:
                                    _evo_bonus += 100
                                score += _evo_bonus
                            elif _has_dipplin_hand:
    
                                _evo_bonus = 300
                                if _has_energy_hand:
                                    _evo_bonus += 100
                                if op_has_ex_immune_active:
                                    _evo_bonus += 150
                                score += _evo_bonus
    
                        elif card.id == Chikorita and _forest_available:
    
                            _has_bayleef_hand = (hand_counts.get(Bayleef, 0) >= 1)
                            _has_meganium_hand = (hand_counts.get(Meganium, 0) >= 1)
                            if _has_bayleef_hand and _has_meganium_hand and not ESTADO.meganium_in_play:
    
                                pass
                            elif _has_bayleef_hand and not ESTADO.meganium_in_play:
    
                                pass
    
                        elif card.id == Dipplin and not has_hydrapple:
    
                            if hand_counts.get(Hydrapple_ex, 0) >= 1 and _forest_available:
                                _evo_bonus = 500
                                _has_energy_hand = (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                                                    not state.energyAttached)
                                if _has_energy_hand:
                                    _evo_bonus += 150
                                _bench_grass_energy = 0
                                for _bp in my_state.bench:
                                    if _bp is not None and _bp.id != card.id:
                                        _bench_grass_energy += len(_bp.energies)
                                if _bench_grass_energy >= 1:
                                    _evo_bonus += 100
                                score += _evo_bonus
                            elif hand_counts.get(Hydrapple_ex, 0) >= 1:
    
                                pass
    
                        elif card.id == Bayleef and not ESTADO.meganium_in_play:
    
                            if hand_counts.get(Meganium, 0) >= 1 and _forest_available:
    
                                _has_bench_attacker = any(
                                    bp is not None and bp.id in (Hydrapple_ex, Dipplin,
                                        Teal_Mask_Ogerpon_ex, Tapu_Bulu)
                                    for bp in my_state.bench)
                                if _has_bench_attacker:
    
                                    pass
    
                        if card.id in (Chikorita, Bayleef, Meganium):
                            _meg_designated_attacker = False
                            if (card.id == Meganium and len(card.energies) >= 4 and
                                    (ESTADO.op_is_crustle_deck or ESTADO.op_is_cornerstone_deck)):
                                _meg_other_atk_p = any(
                                    bp is not None and (
                                        (bp.id == Dipplin and len(bp.energies) >= 1) or
                                        (bp.id == Tapu_Bulu and len(bp.energies) >= 4) or
                                        (bp.id == Pinsir and len(bp.energies) >= 2))
                                    for bp in my_state.bench)
                                if not _meg_other_atk_p:
                                    _meg_designated_attacker = True
                            # vs Alakazam (user, registro_010 paso 127): un
                            # Meganium (1 premio) LISTO para atacar es un atacante
                            # DESIGNADO -- lo preferimos como activo antes que un ex
                            # de 2 premios, aunque haya otros atacantes de banca. Sin
                            # esto el veto de "Meganium activo" (-10000) impedia
                            # promoverlo tras retirar el ex (_alakazam_pivot_1prize).
                            elif (card.id == Meganium and op_is_alakazam_deck
                                    and _can_attack_now):
                                _meg_designated_attacker = True
                            # Neutralization Zone (id 1247, user): bajo la zona,
                            # nuestros ex (recuadro de regla) NO danan a un activo
                            # rival SIN recuadro (1 premio). Si el activo rival es
                            # no-ex y Meganium (no-ex, 140) puede atacar, Meganium
                            # es el atacante DESIGNADO: KO/dana al activo mientras
                            # los ex hacen 0. Sin esto el veto "Meganium activo"
                            # (SCORE_NEVER) lo hundia y se promovia un ex inutil.
                            elif (card.id == Meganium and _can_attack_now
                                    and neutralization_zone_active):
                                _nz_meg_op_act = (op_state.active[0]
                                                  if op_state.active else None)
                                _nz_meg_data = (card_table.get(_nz_meg_op_act.id)
                                                if _nz_meg_op_act is not None else None)
                                if not (_nz_meg_data
                                        and (_nz_meg_data.ex or _nz_meg_data.megaEx)):
                                    _meg_designated_attacker = True
                            # PROMOCION FORZADA TRAS KO: el turno en que subimos
                            # el cuerpo es el turno RIVAL -- nadie ataca ya --,
                            # asi que "listo para atacar" se mide con la energia
                            # del PROXIMO turno, no con la de ahora (user,
                            # registro_013 paso 71 vs Crustle, PERDIDA).
                            #
                            # Alli el KO nos dejo sin activo con el Crustle rival
                            # a 70 PV. Meganium en banca tenia 1 Planta = 2
                            # efectivas (Wild Growth) y otra Planta en la mano:
                            # subiendolo, el proximo turno adjuntamos y llega a
                            # 4 -> Solar Beam 140 remata al Crustle. Y es el
                            # UNICO que lo remata: Mysterious Rock Inn anula el
                            # dano de nuestros ex, asi que Ogerpon/Fezandipiti
                            # pegan 0. `_best_promote_card` ya lo habia elegido
                            # (contempla inmunidad a ex, inmunidad de habilidad,
                            # debilidad y el adjunte del proximo turno), pero
                            # este veto de "la linea Meganium no va al activo"
                            # (-10000) hundia su bono (+4000) y se promovia un
                            # Ogerpon ex que ni ataca ni dana -> turno regalado.
                            # El veto protege el motor Wild Growth desde la
                            # BANCA, y esa proteccion es CARA de perder: si el
                            # cuerpo activo cae, cada Planta vuelve a valer 1 y
                            # todo el tablero se queda a medias. Por eso la
                            # exencion exige REMATE, no solo "es el mejor
                            # candidato": el veto cede unicamente cuando el
                            # selector consciente del KO senala a este cuerpo Y
                            # su golpe NOQUEA al activo rival el proximo turno
                            # (`_best_promote_key[0] == 1`). Medido: exentar sin
                            # exigir KO cuesta -3.6 pp vs Crustle/Kangaskhan
                            # (68.1% vs 71.7%, n=1000) -- subia la linea
                            # Chikorita/Bayleef/Meganium a cambio de nada.
                            elif (_forced_ko_promote
                                    and _best_promote_card is not None
                                    and card is _best_promote_card
                                    and _best_promote_key is not None
                                    and _best_promote_key[0] == 1):
                                _meg_designated_attacker = True
                            if _meg_designated_attacker:
                                score += 400
                            elif bench_count > 1:
                                score = SCORE_NEVER
    
                        if op_has_ex_immune_active and card.id not in OUR_EX_IDS:
                            score += 150
                        elif op_has_ex_immune_active and card.id in OUR_EX_IDS:
                            score -= 80
    
                        if op_has_ability_immune_active and card.id not in OUR_ABILITY_IDS:
                            score += 180
                        elif op_has_ability_immune_active and card.id in OUR_ABILITY_IDS:
                            score -= 100
    
                        if op_is_fire_deck and card.id == Hydrapple_ex and _can_attack_now:
                            score += 40
    
                        if op_is_control_deck and card.id == Tapu_Bulu and _can_attack_now:
                            score += 50
    
                        _op_is_drednaw_active = (op_state.active and op_state.active[0] is not None
                                                 and op_state.active[0].id == Drednaw)
                        if _op_is_drednaw_active:
                            if card.id == Meganium and _can_attack_now:
                                score += 250
                            elif card.id == Meganium and _can_attack_with_attach:
                                score += 200
                            elif card.id == Dipplin and _can_attack_now:
                                score += 180
                            elif card.id == Dipplin and _can_attack_with_attach:
                                score += 150
                            elif card.id == Hydrapple_ex:
                                score -= 150
                            elif card.id == Tapu_Bulu:
                                score -= 150
    
                        _op_is_sylveon_active = (op_state.active and op_state.active[0] is not None
                                                 and op_state.active[0].id == Sylveon)
                        if _op_is_sylveon_active:
                            if card.id == Tapu_Bulu and _can_attack_now:
                                score += 280
                            elif card.id == Meganium and _can_attack_now:
                                score += 260
                            elif card.id == Tapu_Bulu and _can_attack_with_attach:
                                score += 220
                            elif card.id == Meganium and _can_attack_with_attach:
                                score += 200
                            elif card.id == Dipplin and _can_attack_now:
                                score += 180
                            elif card.id == Dipplin and _can_attack_with_attach:
                                score += 150
                            elif card.id in OUR_EX_IDS:
                                score -= 200
    
                        if neutralization_zone_active:
    
                            _op_act_nz = op_state.active[0] if op_state.active else None
                            _op_act_nz_rb = False
                            if _op_act_nz is not None:
                                _op_act_nz_data = card_table[_op_act_nz.id]
                                _op_act_nz_rb = (_op_act_nz_data.ex or _op_act_nz_data.megaEx)
                            if not _op_act_nz_rb:
    
                                if card.id == Tapu_Bulu and _can_attack_now:
                                    score += 250
                                elif card.id == Meganium and _can_attack_now:
                                    score += 220
                                elif card.id == Tapu_Bulu and _can_attack_with_attach:
                                    score += 200
                                elif card.id == Meganium and _can_attack_with_attach:
                                    score += 180
                                elif card.id == Dipplin and _can_attack_now:
                                    score += 160
                                elif card.id == Dipplin and _can_attack_with_attach:
                                    score += 140
                                elif card.id in OUR_EX_IDS:
                                    score -= 200
    
                        if o.index == ESTADO.plan.attacker - 1:
                            score += 120
    
                        if card.id == Dipplin and hand_counts.get(Hydrapple_ex, 0) >= 1:
                            score += 80
                        elif card.id == Bayleef and hand_counts.get(Meganium, 0) >= 1:
                            score -= 30
                        elif card.id == Applin and hand_counts.get(Dipplin, 0) >= 1:
                            if ESTADO.forest_in_play and hand_counts.get(Hydrapple_ex, 0) >= 1:
                                score += 60
                            else:
                                score += 20
                        elif card.id == Chikorita and hand_counts.get(Bayleef, 0) >= 1:
                            if ESTADO.forest_in_play and hand_counts.get(Meganium, 0) >= 1:
                                score -= 30
                            else:
                                score += 5
    
                        if has_condition:
                            score += 50
    
                        # --- Promocion vs activo INMUNE a ex (Crustle) -------
                        # Solo cuando el Pokemon inmune esta ACTIVO (no basta
                        # con que este en banca): Crustle activo anula el dano de
                        # NUESTROS ex, por lo que un ex no ataca pero sirve de
                        # MURO. Regla: subir un atacante no-ex que SI dane a
                        # Crustle si puede atacar; si ninguno puede, subir un ex
                        # como muro (con energia primero; si ninguno tiene
                        # energia, primero Teal Mask Ogerpon ex).
                        if op_has_ex_immune_active:
                            _crus_is_our_ex = card.id in OUR_EX_IDS
                            # En la promocion FORZADA tras un KO el cuerpo que
                            # sube no ataca este turno (es el turno rival): el
                            # criterio correcto es si ataca el PROXIMO turno,
                            # contando el adjunte de la mano (x2 con Wild
                            # Growth). Con el criterio "ataca AHORA" un Meganium
                            # a 2/4 efectivas no contaba como atacante y el muro
                            # ex (+3000) se llevaba la plaza aunque haga 0 dano
                            # al Crustle -- user, registro_013 paso 71, PERDIDA.
                            _crus_nonex_attacker = (
                                not _crus_is_our_ex
                                and (_can_attack_now
                                     or (_forced_ko_promote
                                         and _can_attack_with_attach)))
                            if _crus_nonex_attacker:
                                # Atacante no-ex que SI dana a Crustle: prioridad maxima.
                                score += 6000
                            elif _crus_is_our_ex:
                                # Muro ex: con energia primero; si no, Teal Mask primero.
                                if energy_count >= 1:
                                    score += 3000 + energy_count * 10
                                elif card.id == Teal_Mask_Ogerpon_ex:
                                    score += 2500
                                else:
                                    score += 2000
    
                        # Bono decisivo al mejor atacante contra el ACTIVO rival
                        # (calculado antes del bucle segun dano efectivo). Vale
                        # para cualquier activo: Mega/normal -> el que pega mas
                        # fuerte (Hydrapple ex); Crustle/Cornerstone -> el mejor
                        # no-ex / no-habilidad.
                        if (_best_promote_card is not None
                                and card is _best_promote_card
                                and not (_descuadre_matchup
                                         and _best_promote_key is not None
                                         and _best_promote_key[0] == 0)):
                            # vs Raging Bolt / Mega Abomasnow, un "mejor candidato"
                            # que NO noquea es solo un ex condenado: sin el bono, el
                            # +2500 del cuerpo de 1 premio decide el muro.
                            score += 4000
    
                        # Regla (user) vs Mega Lucario sin atacante en banca:
                        # promover primero un BASICO (Applin prioritario) o, si no
                        # hay basico, Dipplin. El resto de cuerpos (ex, Fases 1/2
                        # que no sean Dipplin) conservan su score actual, asi que
                        # si no hay basico ni Dipplin sigue la logica normal.
                        if _lucario_ko_prefer_basic:
                            _luc_prom_data = card_table.get(card.id)
                            _luc_is_basic = (
                                _luc_prom_data is not None
                                and not getattr(_luc_prom_data, 'stage1', False)
                                and not getattr(_luc_prom_data, 'stage2', False))
                            if card.id == Applin:
                                score = 9000
                            elif _luc_is_basic:
                                score = 8500
                            elif card.id == Dipplin:
                                score = 8000
    
                        # Regla (user, log 86345562 p55): preferir subir un
                        # BASICO de 1 premio (Applin) en vez de un ex de 2 premios
                        # cuando ningun cuerpo puede atacar y tenemos Lillie's para
                        # refrescar. Conserva los ex -y su energia- a salvo en la
                        # banca. No hay basico -> sigue la promocion normal (ex).
                        if _refresh_promote_prefer_basic:
                            _ref_pb_data = card_table.get(card.id)
                            _ref_is_basic = (
                                _ref_pb_data is not None
                                and not getattr(_ref_pb_data, 'stage1', False)
                                and not getattr(_ref_pb_data, 'stage2', False))
                            if card.id not in OUR_EX_IDS and _ref_is_basic:
                                if card.id == Applin:
                                    score = 6000
                                else:
                                    score = 5500
                                # Desempate por VIDA entre basicos de 1 premio
                                # (user, registro_009 paso 61 vs Dragapult): la
                                # regla de arriba nacio para preferir un basico
                                # frente a un ex, pero entre DOS basicos subia
                                # siempre el Applin de 40 PV -- un premio regalado
                                # y ademas pieza de la linea Hydrapple que
                                # queremos evolucionar en la banca. Con un cuerpo
                                # de 1 premio realmente resistente disponible
                                # (Tapu Bulu, 140 PV) el muro es ese: aguanta el
                                # turno rival y es el que estamos cargando.
                                if (card.hp or 0) >= 100:
                                    score = 6100
    
                        # Descuadre generalizado (user, registro_004 paso 37):
                        # sin atacante de banca y con el rival one-shoteando incluso
                        # a nuestro cuerpo mas tanque, promover un BASICO de 1 premio
                        # (Applin prioritario) o Dipplin en vez de un ex de 2. Mismos
                        # scores que `_lucario_ko_prefer_basic` para conducta identica
                        # en cualquier mazo. Desempate por VIDA entre basicos.
                        if _ko_prefer_basic_general:
                            _gpb_data = card_table.get(card.id)
                            _gpb_is_basic = (
                                _gpb_data is not None
                                and not getattr(_gpb_data, 'stage1', False)
                                and not getattr(_gpb_data, 'stage2', False))
                            if card.id == Applin:
                                score = 9000
                            elif _gpb_is_basic and card.id not in OUR_EX_IDS:
                                score = 8500 + (card.hp or 0) // 10
                            elif card.id == Dipplin:
                                score = 8000
    
                        # Promover al atacante CASI listo que remata el proximo
                        # turno (user, registro_009 p111): domina al muro basico y
                        # a cualquier otra rama de promocion. Ver
                        # `_promote_setup_ko_attacker`.
                        if (_promote_setup_ko_attacker is not None
                                and card is _promote_setup_ko_attacker):
                            score = 9500
    
                        # ANTI-CUBCHOO: no promover un cuerpo que quedaria CLAVADO
                        # (user, registro_036 paso 146). Mismo principio que el veto
                        # de evolucion vs Cubchoo: contra un mazo que bloquea y
                        # descarta energia, subir al activo un Pokemon con coste de
                        # retirada ALTO que no puede pagarlo lo deja atrapado alli.
                        # Al retirar tras Teal Dance, Hydrapple ex (retirada 3, 2
                        # energias efectivas -> clavado) ganaba 623 a 555 al Teal
                        # Mask Ogerpon ex (retirada 1, 4 energias), que ademas
                        # tambien NOQUEA y conserva la movilidad para el proximo
                        # pivote. Es una PENALIZACION, no un veto: si el cuerpo
                        # lento es la unica opcion, sigue siendo el promovido.
                        if (op_is_cubchoo_deck and score > 0
                                and isinstance(card, Pokemon)):
                            _cp_rc = RETREAT_COST.get(card.id, 1)
                            if _cp_rc >= 3 and len(card.energies) < _cp_rc:
                                score -= 300
    
                        # SUPERVIVENCIA (user, registro_005 paso 64). Ajuste
                        # TERMINAL: va despues de todas las ramas de promocion
                        # para tener la ultima palabra. Ver el bloque que calcula
                        # `_promo_survivors` / `_promo_min_prize`.
                        #
                        # Las DOS exenciones de abajo (el que noquea y el remate
                        # garantizado) comparten una premisa: el cuerpo promovido
                        # llega vivo a NUESTRO turno y ataca primero. Bajo
                        # Festival Lead esa premisa es falsa -- el rival repite
                        # el ataque en cuanto elegimos-, asi que un candidato que
                        # NO sobrevive pierde ambas y cae al tramo de
                        # supervivencia/premios. Ver `op_double_attack_pending`.
                        _promo_llega_a_atacar = not (
                            op_double_attack_pending
                            and isinstance(card, Pokemon)
                            and not _promo_survives(card))
                        if (score > 0 and isinstance(card, Pokemon)
                                and _promo_op_act is not None
                                and _promo_llega_a_atacar
                                and _promo_kos_op(card)):
                            # PRIORIDAD DEL QUE NOQUEA (user): subir el atacante
                            # cargado en vez del tanque SOLO cuando ese atacante
                            # noquea al rival. Cobrar el premio manda aunque
                            # despues muera; si no noquea, gobiernan la
                            # supervivencia y los premios de abajo.
                            score += PROMO_KO_BONUS
                        elif (_promote_setup_ko_attacker is not None
                                and card is _promote_setup_ko_attacker
                                and _promo_llega_a_atacar):
                            # REMATE GARANTIZADO EL PROXIMO TURNO (user,
                            # registro_007 paso 126): la promocion tras un KO se
                            # resuelve al FINAL del turno rival, asi que el
                            # siguiente turno es NUESTRO y este cuerpo ataca
                            # PRIMERO. Ni la penalizacion por condenado ni la de
                            # premios aplican: el rival no llega a golpearlo.
                            # Sin esta exencion el -1500 por ser un ex de 2
                            # premios hundia los 9500 de
                            # `_promote_setup_ko_attacker` (8000) por debajo del
                            # muro basico de `_ko_prefer_basic_general`
                            # (8500+vida/10), justo lo que la nota de esa regla
                            # decia impedir: se subia un Tapu Bulu a 1/4 energias
                            # -sin ataque y con retirada 3- en vez del Ogerpon ex
                            # a 2/3 que remataba al Grimmsnarl ex por debilidad.
                            pass
                        elif (score > 0 and isinstance(card, Pokemon)
                                and _promo_op_act is not None):
                            if _promo_survivors > 0:
                                # 1) Hay quien aguanta: el que muere sin cobrar
                                #    premio deja de ser candidato. Penalizacion
                                #    (no veto) para conservar el orden relativo
                                #    entre los condenados si no queda otra.
                                if not _promo_survives(card):
                                    score -= PROMO_DOOMED_PENALTY
                            elif _promo_min_prize is not None:
                                # 2) No aguanta nadie: entregar los MENOS premios
                                #    posibles. Refuerza las reglas de descuadre
                                #    que ya prefieren un cuerpo de 1 premio.
                                score -= (PROMO_PRIZE_PENALTY
                                          * (prize_count(card) - _promo_min_prize))
    
                        # MATCH POINT (user, log 88971843 paso 117). Cuando al
                        # rival le basta con noquear ESTE cuerpo para llevarse
                        # el ultimo premio, subir un condenado no es un mal
                        # intercambio: es perder la partida. Mientras exista
                        # ALGUN candidato que aguante, el condenado deja de ser
                        # una opcion -- VETO, no penalizacion, para que ningun
                        # bono pueda comprarlo (los 20000 del que noquea, los
                        # 9500 del remate garantizado, los 8500+ del muro
                        # basico). Va DESPUES de toda la cadena, con la ultima
                        # palabra.
                        #
                        # Dos guardas lo mantienen estrecho:
                        #   * `_promo_survivors > 0`: si no aguanta NADIE la
                        #     partida esta perdida igual y manda la regla de
                        #     premios de arriba (no vetamos la banca entera).
                        #   * el que LLEGA a atacar y NOQUEA queda exento: ahi
                        #     cobramos premio antes de morir y la jugada puede
                        #     cerrar la partida a nuestro favor. Bajo Festival
                        #     Lead `_promo_llega_a_atacar` ya es False para los
                        #     condenados, asi que la exencion no se abre.
                        #
                        # Con el dano rival ilegible (proyeccion 0) TODOS
                        # "sobreviven" y esto no dispara: sin evidencia no se
                        # veta nada.
                        if (_forced_ko_promote and isinstance(card, Pokemon)
                                and _promo_op_act is not None
                                and _promo_survivors > 0
                                and op_prize <= prize_count(card)
                                and not _promo_survives(card)
                                and not (_promo_llega_a_atacar
                                         and _promo_kos_op(card))):
                            score = PROMO_MATCH_POINT_VETO
    
                        # DESEMPATE ENTRE SUPERVIVIENTES (user, prioridades 3 y
                        # 4). Resuelta ya la supervivencia (1) y protegido el
                        # multiplicador Wild Growth (2, via el veto "la linea
                        # Meganium no va al activo"), entre los cuerpos que
                        # AGUANTAN y ninguno noquea manda: primero el que este
                        # mas CERCA de poder atacar -- se mide en ADJUNTES, no
                        # en energias, porque con Meganium en juego una Planta
                        # vale dos-- y a igualdad el que ceda MENOS premios.
                        # Un tanque de 160 PV que no atacara en tres turnos vale
                        # menos que uno de 140 que ataca al siguiente.
                        #
                        # Acotado a 0..450: manda sobre el score BASE de la
                        # promocion -- que ronda 150-250 y ordena por vida, que
                        # es justo el criterio que el user pone por DEBAJO de
                        # estos dos-- y queda muy por debajo de cualquier regla
                        # decisiva (+4000 del mejor atacante, 8000-9500 de las
                        # ramas con nombre, +20000 del que noquea), que siguen
                        # teniendo la ultima palabra. Con 60 puntos no llegaba:
                        # medido en un empate real, un Ogerpon ex de 210 PV a
                        # TRES adjuntes de atacar seguia ganandole a un Tapu
                        # Bulu de 140 a DOS (193 vs 144 de base).
                        #
                        # Se excluye al que NOQUEA: entre noqueadores decide el
                        # score base, como documenta PROMO_KO_BONUS. Y ojo, la
                        # prioridad (3)+(4) YA es decisiva -y en este mismo
                        # orden- dentro de `_promote_setup_ko_attacker`
                        # (`_ps_key`); esto cubre el hueco que aquella regla
                        # deja fuera: los candidatos cuyo ataque completado NO
                        # remata al activo rival.
                        if (_forced_ko_promote and isinstance(card, Pokemon)
                                and score > 0
                                and _promo_op_act is not None
                                and _promo_survivors > 0
                                and _promo_survives(card)
                                and not _promo_kos_op(card)):
                            _tb_req = ESTADO.ATTACK_ENERGY_REQ.get(card.id)
                            if _tb_req is None:
                                _tb_pasos = 3      # no ataca: lo mas lejos
                            else:
                                _tb_falta = max(0, _tb_req - len(card.energies))
                                _tb_unit = max(1, _grass_attach_unit())
                                _tb_pasos = min(3, -(-_tb_falta // _tb_unit))
                            score += 300 - 100 * _tb_pasos
                            if prize_count(card) <= 1:
                                score += 150
                    else:
    
                        # Objetivo del GUSTEO de Boss's Orders: migrado al MOTOR DE
                        # REGLAS (fase 4). Definiciones y comentarios estrategicos en
                        # _REGLAS_GUST_ESTORBO / _AJUSTES_GUST_* (antes de agent()).
                        if card.id in DUNSPARCE_IDS:
                            # Regla (usuario): NUNCA gustear un Dunsparce (ids 65 y
                            # 305), ni en modo estorbo ni en modo ofensivo.
                            score = SCORE_FORBID
                        else:
                            _gt_ctx = _ctx_gust_objetivo(
                                card, o, my_state, op_state, state, hand_counts,
                                total_grass, bench_count, neutralization_zone_active,
                                op_is_alakazam_deck, op_has_latias_ex,
                                (op_has_dragapult or op_has_dreepy_line),
                                (op_has_typhlosion or op_has_ethan_preevo),
                                my_prize=my_prize)
                            # NOTA (ciclo jul 2026, MEDIDO Y REVERTIDO): se
                            # intento decidir el modo POR CANDIDATO (con
                            # `not _gt_ctx.can_ko` en esta condicion) para
                            # que un objetivo noqueable tras retirar --
                            # Dwebble 650 vs Kangaskhan-traba 800 -- evaluara
                            # en ofensivo con el activo trabado. Ver la nota
                            # gemela en `crustle_gust_worth_it`: -1.4 puntos
                            # vs crustle con n=4000/rama, revertido en bloque.
                            if _active_cant_attack_this_turn or _sel_active_cant_attack:
                                score = _resolver_con_traza(
                                    "boss->objetivo/estorbo", _REGLAS_GUST_ESTORBO,
                                    _AJUSTES_GUST_ESTORBO, _gt_ctx, defecto=-200)
                            else:
                                score = _resolver_con_traza(
                                    "boss->objetivo", [], _AJUSTES_GUST_OFENSIVO,
                                    _gt_ctx, defecto=0)
                elif context == SelectContext.SETUP_ACTIVE_POKEMON:
    
                    if card.id == Tapu_Bulu:
                        # Regla (user): si al COMENZAR la partida tenemos un Tapu
                        # Bulu en la mano, es SIEMPRE nuestro Pokemon inicial
                        # activo. Es el atacante no-ex de referencia (1 premio,
                        # 220 de dano con Wood Hammer, y el unico que dana a los
                        # rivales que anulan ex o habilidades), asi que arranca
                        # en el activo para ir cargandolo desde el turno 1 y no
                        # exponer un ex de 2 premios de salida. Tope por encima
                        # del Teal Mask Ogerpon ex (100), que era el preferido.
                        score = 200
                    elif card.id == Teal_Mask_Ogerpon_ex:
                        score = 100
                    elif card.id in (Chikorita, Applin) and hand_counts.get(card.id, 0) >= 2:
    
                        score = 7
                    elif card.id == Applin:
                        score = 5
                    elif card.id == Chikorita:
                        score = 3
                    elif card.id == Meowth_ex:
                        score = 0
                    else:
                        score = 1
    
                elif context == SelectContext.SETUP_BENCH_POKEMON:
    
                    if card.id == Chikorita:
                        score = 8
    
                        if op_is_fire_deck or op_is_aggro_deck:
                            score = 10
                    elif card.id == Applin:
                        score = 7
    
                        if op_bench_snipe_threat:
                            score = 4
                        elif op_is_fire_deck or op_is_aggro_deck:
                            score = 8
                    elif card.id == Teal_Mask_Ogerpon_ex:
                        score = 6
    
                        if op_is_fire_deck:
                            score = 7
                    elif card.id == Meowth_ex:
    
                        score = SCORE_VETO
                    elif card.id == Fezandipiti_ex:
                        # Al comienzo de la partida (setup) NO bajamos Fezandipiti
                        # ex a la banca salvo que sea el UNICO Pokemon de la mano
                        # (obligados a poner un basico). Fezandipiti ex es debil a
                        # Lucha ({F}) y vale 2 premios, y su habilidad Flip the
                        # Script solo sirve tras ser noqueado; bajarlo de salida
                        # regala un KO de 2 premios facil (critico vs Mega Lucario,
                        # que NO es detectable aun en el setup: el rival no ha
                        # revelado su activo). Si hay otro Pokemon en la mano, lo
                        # conservamos (se puede bajar mas tarde cuando convenga).
                        _setup_hand_poke = 0
                        for _shp in (my_state.hand or []):
                            _shp_data = card_table.get(_shp.id)
                            if _shp_data is not None and _shp_data.cardType == CardType.POKEMON:
                                _setup_hand_poke += 1
                        if _setup_hand_poke <= 1:
                            score = 2
                            if op_has_froslass:
                                score = 0
                            if op_bench_snipe_threat:
                                score = 1
                        else:
                            score = SCORE_VETO
                    elif card.id == Tapu_Bulu:
    
                        if ESTADO.meganium_in_play and (op_has_ex_immune_active or op_has_ex_immune_bench):
                            score = 3
                        elif ESTADO.op_is_crustle_deck:
                            score = 3
                        else:
                            score = SCORE_VETO
                    elif card.id == Pinsir:
    
                        if ESTADO.op_is_crustle_deck or op_is_sylveon_deck or ESTADO.op_is_cornerstone_deck:
                            score = 3
                        elif op_has_ex_immune_active or op_has_ex_immune_bench:
                            score = 2
                        else:
                            score = SCORE_VETO
    
                elif context == SelectContext.TO_HAND:
                    score = 200 - hand_counts[card.id] * 100
    
                    is_bcs_selection = (select.effect is not None and select.effect.id == Bug_Catching_Set)
    
                    if is_bcs_selection:
                        # Bloque migrado al MOTOR DE REGLAS (fase 4):
                        # definiciones y comentarios estrategicos en
                        # _TABLA_BCS_FETCH / _REGLAS_BCS_* (antes de agent()).
                        # El bonus por copias premiadas se conserva inline.
                        score = 100
                        _bcs_ctx = _ctx_ns_fetch(
                            my_state, state, hand_counts, field_counts,
                            bench_count, total_grass, has_hydrapple,
                            _active_needs_energy, op_has_ex_immune_active,
                            op_has_ex_immune_bench, op_is_lucario_deck,
                            meowth_ability_lock, _best_supp_in_hand_val,
                            _best_supp_in_mazo_val,
                            dragapult_no_tapu=_dragapult_no_tapu)
                        _bcs_entrada = _TABLA_BCS_FETCH.get(card.id)
                        if _bcs_entrada is not None:
                            _bcs_et, _bcs_reglas, _bcs_defecto = _bcs_entrada
                            score = _resolver_con_traza(
                                _bcs_et, _bcs_reglas, [], _bcs_ctx,
                                defecto=_bcs_defecto)
    
                        if card.id in ESTADO.CARTAS_ACTIVAS_EN_MAZO:
                            prized_copies = ESTADO.CARTAS_ACTIVAS_EN_MAZO[card.id][ESTADO_PREMIO]
                            total_copies = sum(ESTADO.CARTAS_ACTIVAS_EN_MAZO[card.id].values())
                            if prized_copies > 0 and total_copies - prized_copies <= 1:
                                score += 100
    
                    elif select.effect is not None and select.effect.id == Poke_Pad:
    
                        # Bloque migrado al MOTOR DE REGLAS (fase 4):
                        # definiciones y comentarios estrategicos en
                        # _REGLAS_PP_FETCH (antes de agent()).
                        score = _resolver_con_traza(
                            "pp->fetch", _REGLAS_PP_FETCH, [],
                            _CtxPPFetch(card.id, hand_counts, field_counts,
                                        bench_count, state),
                            defecto=10)
    
                    elif select.effect is not None and select.effect.id == Night_Stretcher:
    
                        score = 50
    
                        # Bloque migrado al MOTOR DE REGLAS (fase 4):
                        # definiciones y comentarios estrategicos en
                        # _REGLAS_NS_* (antes de agent()). Los post-ajustes
                        # transversales de abajo se conservan inline.
                        _ns_ctx = _ctx_ns_fetch(
                            my_state, state, hand_counts, field_counts,
                            bench_count, total_grass, has_hydrapple,
                            _active_needs_energy, op_has_ex_immune_active,
                            op_has_ex_immune_bench, op_is_lucario_deck,
                            meowth_ability_lock, _best_supp_in_hand_val,
                            _best_supp_in_mazo_val,
                            grass_enables_syrup_ko=(
                                (_grass_anywhere_enables_syrup_ko
                                 or _grass_enables_promote_ko)
                                and _grass_attach_route_open(
                                    state, field_counts,
                                    abilities_off=meowth_ability_lock)),
                            ld_free=_meowth_ld_free,
                            dragapult_no_tapu=_dragapult_no_tapu)
    
                        _ns_tablas = {
                            Basic_Grass_Energy: ("ns->grass",
                                                 _REGLAS_NS_GRASS, 300),
                            Fezandipiti_ex: ("ns->fez", _REGLAS_NS_FEZ, 10),
                            Chikorita: ("ns->chikorita",
                                        _REGLAS_NS_CHIKORITA, 40),
                            Applin: ("ns->applin", _REGLAS_NS_APPLIN, 80),
                            Teal_Mask_Ogerpon_ex: ("ns->ogerpon",
                                                   _REGLAS_NS_OGERPON, 20),
                            Tapu_Bulu: ("ns->tapu", _REGLAS_NS_TAPU, 50),
                            Pinsir: ("ns->pinsir", _REGLAS_NS_PINSIR, 15),
                            Meowth_ex: ("ns->meowth",
                                        _REGLAS_NS_MEOWTH, 15),
                            Hydrapple_ex: ("ns->hydrapple",
                                           _REGLAS_NS_HYDRAPPLE, 30),
                            Meganium: ("ns->meganium",
                                       _REGLAS_NS_MEGANIUM, 30),
                            Dipplin: ("ns->dipplin", _REGLAS_NS_DIPPLIN, 30),
                            Bayleef: ("ns->bayleef", _REGLAS_NS_BAYLEEF, 30),
                        }
                        _ns_entrada = _ns_tablas.get(card.id)
                        if _ns_entrada is not None:
                            _ns_et, _ns_reglas, _ns_defecto = _ns_entrada
                            score = _resolver_con_traza(
                                _ns_et, _ns_reglas, [], _ns_ctx,
                                defecto=_ns_defecto)
    
                        if card.id in ESTADO.CARTAS_ACTIVAS_EN_MAZO and card.id != Basic_Grass_Energy:
                            entry = ESTADO.CARTAS_ACTIVAS_EN_MAZO[card.id]
                            if entry[ESTADO_MAZO] == 0 and entry[ESTADO_PREMIO] >= 1:
                                score += 200
                            elif entry[ESTADO_MAZO] == 0 and entry[ESTADO_PREMIO] == 0:
                                score += 150
    
                        if ESTADO.op_is_crustle_deck or ESTADO.op_is_cornerstone_deck:
                            # La ENERGIA es matchup-agnostica y NUNCA se veta
                            # (registro_008 paso 75 vs Mega Starmie con
                            # Cornerstone de TECH en banca): la whitelist
                            # aplastaba la Planta (1300, habilitaba el Syrup
                            # Storm del Hydrapple activo ESTE turno via el
                            # adjunte manual pendiente) y recuperaba un Tapu
                            # Bulu muerto en mano (50). La Planta ademas carga
                            # al propio Tapu, el atacante de estos matchups.
                            if ESTADO.op_is_cornerstone_deck and not ESTADO.op_is_crustle_deck:
                                _cc_sel_valid = (Tapu_Bulu, Pinsir,
                                                 Basic_Grass_Energy)
                            else:
                                _cc_sel_valid = (Tapu_Bulu, Pinsir, Applin, Chikorita,
                                                 Dipplin, Bayleef, Meganium,
                                                 Basic_Grass_Energy)
                            # El MOTOR DE ROBO tampoco se veta por matchup: con
                            # el turno muerto y la mano seca, la whitelist
                            # anti-ex dejaba de opcion unica un cuerpo de
                            # desarrollo que no se juega, y el turno siguiente
                            # se repite sin cartas. Misma excepcion que la
                            # ENERGIA de arriba (ver `_ns_motor_*_vivo`).
                            _cc_motor = (
                                _ns_ctx.turno_muerto and _ns_ctx.mano_agotada
                                and ((card.id == Meowth_ex
                                      and _ns_motor_meowth_vivo(_ns_ctx))
                                     or (card.id == Fezandipiti_ex
                                         and _ns_motor_fez_vivo(_ns_ctx))))
                            if card.id not in _cc_sel_valid and not _cc_motor:
                                score = SCORE_VETO
    
                    elif select.effect is not None and select.effect.id == Ultra_Ball:
    
                        score = 100
    
                        hand_play_options, supporters_in_hand = _count_hand_play_options(
                            hand_counts, field_counts, bench_count, state.energyAttached)
                        hand_is_weak = (hand_play_options <= 1 and len(my_state.hand) <= 4)
                        has_energy_for_teal = hand_counts.get(Basic_Grass_Energy, 0) >= 1
    
                        # NO usa `_evolvable_counts`: MEDIDO Y REVERTIDO.
                        _ub_evolvable = ESTADO._field_at_turn_start if (not ESTADO.forest_in_play and ESTADO._field_at_turn_start) else field_counts
    
                        _t1_going_second_meowth = (
                            state.turn == 2 and not ESTADO.we_go_first and
                            not state.supporterPlayed and
                            hand_counts.get(Lillie_Determination, 0) == 0 and
                            field_counts.get(Meowth_ex, 0) < 2 and
                            bench_count < 5 and
                            ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0 and
                            ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)
    
                        _t1_going_second_need_ogerpon = (
                            state.turn == 2 and not ESTADO.we_go_first and
                            bench_count == 0 and
                            any(field_counts.get(pid, 0) >= 1 for pid in (Applin, Chikorita)) and
                            not any(hand_counts.get(pid, 0) >= 1
                                    for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                                Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir)))
    
                        _t1_going_first_need_basic = (
                            state.turn == 1 and ESTADO.we_go_first and
                            bench_count == 0 and
                            not any(hand_counts.get(pid, 0) >= 1
                                    for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                                Tapu_Bulu, Fezandipiti_ex, Pinsir)))
    
                        # Regla (user, log 85850698 paso 5, GANADO vs Lucario):
                        # cuando solo tenemos UN Pokemon en juego (banca vacia) y
                        # NINGUN Pokemon jugable en la mano, la busqueda de Ultra
                        # Ball debe traer SIEMPRE Meowth ex (Basico que ademas, al
                        # bajarlo, busca un Supporter = Lillie's Determination para
                        # refrescar la mano el proximo turno) en vez de Ogerpon ex.
                        # EXCEPCION: si YA tenemos una Lillie's Determination en la
                        # mano, no hace falta el fetch de Meowth ex -> se prefiere
                        # Ogerpon ex (atacante). Requiere Meowth ex y Lillie's en el
                        # mazo, sin Watchtower (que anula su habilidad) y < 2 Meowth
                        # ex ya en juego.
                        _ub_only_active_in_play = (bench_count == 0)
                        _ub_no_playable_basic_hand = not any(
                            hand_counts.get(pid, 0) >= 1
                            for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                        Tapu_Bulu, Fezandipiti_ex, Pinsir, Meowth_ex))
                        _ub_prefer_meowth_develop = (
                            _ub_only_active_in_play
                            and _ub_no_playable_basic_hand
                            and hand_counts.get(Lillie_Determination, 0) == 0
                            and not meowth_ability_lock
                            and field_counts.get(Meowth_ex, 0) < 2
                            and bench_count < 5
                            and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0
                            and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)
    
                        # -----------------------------------------------------
                        # Prioridad Dipplin vs Meowth ex en la busqueda (user):
                        # Solo se PRIVILEGIA buscar Dipplin en 3 casos:
                        #  1) Ya se jugo una Lillie's Determination antes (esta en
                        #     el descarte).
                        #  2) Rival anti-ex (Crustle / Sylveon / Cornerstone ex) y
                        #     podemos ATACAR este turno con Dipplin (el Applin a
                        #     evolucionar ya tiene energia para el ataque de 1).
                        #  3) Tenemos estadio (Forest) + Hydrapple ex en mano y
                        #     podemos evolucionar a Hydrapple ex y ADEMAS atacar
                        #     (Syrup Storm requiere 2 de energia efectiva).
                        # Si no se cumple ninguno, Meowth ex tiene prioridad para
                        # refrescar la mano, SIN importar lo que haya en la mano.
                        # -----------------------------------------------------
                        # Fix (user, log 86585073 turno 4, vs Marnie, GANADA): que
                        # ya se haya jugado una Lillie's Determination NO basta para
                        # privilegiar a Dipplin/Hydrapple sobre Meowth ex en la
                        # busqueda si AUN quedan Lillie's en el MAZO. Meowth ex (al
                        # bajarlo, su habilidad Last-Ditch Catch busca un Supporter)
                        # sigue siendo la mejor busqueda para refrescar la mano cuando
                        # la linea Hydrapple no aporta ataque (Hydrapple ex es un ex
                        # de 2 premios que aqui no puede atacar). Solo se privilegia a
                        # Dipplin por "Lillie ya jugada" cuando el motor de Lillie's
                        # esta AGOTADO (ninguna copia queda en el mazo); si aun hay
                        # copias, Meowth ex conserva prioridad (regla
                        # lillie_en_mazo_refresco de _REGLAS_UB_MEOWTH).
                        _dp_lillie_played = (
                            discard_counts.get(Lillie_Determination, 0) >= 1
                            and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                                Lillie_Determination, {}).get(ESTADO_MAZO, 0) == 0)
    
                        _dp_applin_energy = 0
                        for _dp_bp in (my_state.bench or []):
                            if _dp_bp is not None and _dp_bp.id == Applin:
                                _dp_applin_energy = max(_dp_applin_energy,
                                                        len(_dp_bp.energies))
    
                        _dp_anti_ex = (
                            (ESTADO.op_is_crustle_deck or op_is_sylveon_deck or
                             ESTADO.op_is_cornerstone_deck)
                            and _dp_applin_energy >= ESTADO.ATTACK_ENERGY_REQ.get(Dipplin, 1))
    
                        _dp_can_grass_now = (not state.energyAttached and
                                             hand_counts.get(Basic_Grass_Energy, 0) >= 1)
                        _dp_hydra_req = ESTADO.ATTACK_ENERGY_REQ.get(Hydrapple_ex, 2)
                        _dp_hydra_line = (
                            ESTADO.forest_in_play and
                            hand_counts.get(Hydrapple_ex, 0) >= 1 and
                            _dp_applin_energy >= 1 and
                            (_dp_applin_energy >= _dp_hydra_req or
                             (_dp_can_grass_now and
                              _dp_applin_energy + _grass_attach_unit() >= _dp_hydra_req)))
    
                        # FASE E4 del plan de Marnie ("prioridad de busqueda vs
                        # Marnie: linea Hydrapple > Meowth ex"): PROBADA Y NO
                        # IMPLEMENTADA, y el motivo es util para el proximo
                        # ciclo. Sumar un disyuntor "ancla Hydrapple" aqui SI
                        # hace efecto -- sube el fetch de Dipplin de 150 a 800 --
                        # pero no decide NUNCA: cambio 0 decisiones en los 929
                        # pasos de los registros y 0 tambien en el escenario
                        # sintetico fabricado a proposito para ella. La razon es
                        # que `cede_a_dipplin_prioritario` (10) vive al FINAL de
                        # `_REGLAS_UB_MEOWTH`, por detras de la familia
                        # `hydra_muerto_prefiere_meowth` /
                        # `meganium_muerto_prefiere_meowth` /
                        # `sin_atacante_prefiere_meowth` (1000-1250), que es
                        # justo la que dispara en los tableros de este matchup.
                        #
                        # O sea: el verdadero hook de E4 no es `_dipplin_priority`
                        # sino esa familia, y darle la vuelta es un INTERCAMBIO,
                        # no un arreglo -- esas reglas dicen "si la evolucion no
                        # aporta hoy y no hay atacante, refresca", cada una con su
                        # registro detras, y E4 dice lo contrario apoyandose en
                        # UNA partida (la 3). Con el winrate saturado (~96% vs el
                        # bot pilotando Marnie) el harness no puede arbitrar ese
                        # intercambio, asi que no se cambia a ciegas.
                        _dipplin_priority = (_dp_lillie_played or _dp_anti_ex or
                                             _dp_hydra_line)
    
                        # Hydrapple ex traido para evolucionar un Dipplin YA en juego
                        # este turno (rama de score 980), pero que quedaria MUERTO: sin
                        # energia suficiente para Syrup Storm (2 efectiva). Buscar un
                        # Hydrapple ex que no ataca solo tiene sentido si NO hay una
                        # jugada mejor. Cuando el motor de refresco Meowth ex ->
                        # Last-Ditch Catch -> Lillie's Determination esta disponible,
                        # traer Meowth ex (rehace la mano y abre opciones de energia /
                        # atacante) supera a un Hydrapple ex inerte que ademas una
                        # Lillie's posterior podria barajar de vuelta al mazo
                        # (registro 004, paso ~62 vs Iono, PERDIDA). Solo aplica si
                        # Hydrapple ex NO puede atacar este turno.
                        _ub_hydra_evolvable_now = (
                            not has_hydrapple and _ub_evolvable.get(Dipplin, 0) >= 1)
                        _ub_hydra_can_attack_now = False
                        if _ub_hydra_evolvable_now:
                            _ub_best_dip_e = -1
                            for _hp in (([my_state.active[0]] if my_state.active else [])
                                        + list(my_state.bench or [])):
                                if _hp is not None and _hp.id == Dipplin:
                                    if len(_hp.energies) > _ub_best_dip_e:
                                        _ub_best_dip_e = len(_hp.energies)
                            if _ub_best_dip_e >= 0:
                                _ub_hdip_can_attach = (
                                    not state.energyAttached
                                    and hand_counts.get(Basic_Grass_Energy, 0) >= 1)
                                _ub_hdip_after = _ub_best_dip_e + (
                                    _grass_attach_unit() if _ub_hdip_can_attach else 0)
                                if _ub_hdip_after >= ESTADO.ATTACK_ENERGY_REQ.get(Hydrapple_ex, 2):
                                    _ub_hydra_can_attack_now = True
                        _ub_hydra_dead_prefer_meowth = (
                            _ub_hydra_evolvable_now
                            and not _ub_hydra_can_attack_now
                            and not meowth_ability_lock
                            and field_counts.get(Meowth_ex, 0) < 2
                            and bench_count < 5
                            and not state.supporterPlayed
                            and hand_counts.get(Lillie_Determination, 0) == 0
                            and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0
                            and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)
    
                        # Analogo a _ub_hydra_dead_prefer_meowth, pero para la linea
                        # Meganium (Chikorita->Bayleef->Meganium). Un Meganium traido
                        # con Ultra Ball es INUTIL este turno si no hay un Bayleef en
                        # juego que evolucionar (ni Forest+Bayleef en mano para
                        # encadenar): con solo la linea baja en juego (p.ej. Chikorita)
                        # el Meganium es mera preparacion (score 200) y no aporta ataque.
                        # Si ademas NO tenemos un atacante LISTO, preferimos traer
                        # Meowth ex para bajarlo, que su Last-Ditch Catch busque una
                        # Lillie's y refrescar la mano/opciones. Cubre incluso el caso
                        # de un 2o Meowth ex con uno ya en banca (el activo Chikorita
                        # solo hace chip, no es atacante real). (user, registro 004
                        # paso 35 vs Mega Lucario, GANADA)
                        _ub_mega_evolvable_now = (
                            not ESTADO.meganium_in_play and _ub_evolvable.get(Bayleef, 0) >= 1)
                        _ub_mega_chain_now = (
                            not ESTADO.meganium_in_play
                            and _ub_evolvable.get(Chikorita, 0) >= 1
                            and (ESTADO.forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1)
                            and hand_counts.get(Bayleef, 0) >= 1)
                        _ub_mega_dead_prefer_meowth = (
                            not ESTADO.meganium_in_play
                            and not _ub_mega_evolvable_now
                            and not _ub_mega_chain_now
                            and not _active_ready_attacker
                            and not meowth_ability_lock
                            and field_counts.get(Meowth_ex, 0) < 2
                            and bench_count < 5
                            and not state.supporterPlayed
                            and hand_counts.get(Lillie_Determination, 0) == 0
                            and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0
                            and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)
    
                        # Regla (user, registro_004 paso 29, vs Mega Starmie):
                        # generaliza _ub_mega_dead_prefer_meowth. Aunque una
                        # evolucion SEA jugable este turno (p.ej. hay un Bayleef
                        # en juego para subir Meganium), si NO tenemos NINGUN
                        # atacante USABLE este turno la Ultra Ball debe traer
                        # Meowth ex (bajarlo -> Last-Ditch Catch busca Lillie's ->
                        # refrescar la mano y abrir opciones) en vez de una
                        # evolucion que no aportara ataque ahora. Un atacante es
                        # "usable" si: (a) el ACTIVO puede atacar ya, o (b) hay un
                        # atacante LISTO en banca Y el activo puede pagar su coste
                        # de retirada para SUBIRLO al activo. En este registro el
                        # activo (Tapu Bulu, 0 energia, coste 3) no puede
                        # retirarse, asi que el Ogerpon ex cargado de banca esta
                        # atascado -> no hay atacante usable.
                        _uba_act = my_state.active[0] if my_state.active else None
                        _ub_active_can_retreat = (
                            _uba_act is not None
                            and len(_uba_act.energies) >= RETREAT_COST.get(_uba_act.id, 1))
                        _ub_bench_ready_attacker = any(
                            _bp is not None and _bp.id in MAIN_ATTACKERS
                            and _can_attack_eff(_bp.id, len(_bp.energies))
                            for _bp in (my_state.bench or []))
                        _ub_usable_attacker = (
                            _active_ready_attacker
                            or (_ub_active_can_retreat and _ub_bench_ready_attacker))
                        _ub_no_attacker_prefer_meowth = (
                            not _ub_usable_attacker
                            and not meowth_ability_lock
                            and field_counts.get(Meowth_ex, 0) < 2
                            and bench_count < 5
                            and not state.supporterPlayed
                            and hand_counts.get(Lillie_Determination, 0) == 0
                            and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0
                            and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)
    
                        # Cadena migrada al MOTOR DE REGLAS (fase 4): las
                        # definiciones y comentarios estrategicos viven en
                        # _REGLAS_UB_* (antes de agent()). PTCG_DEBUG
                        # imprime la traza de cada resolucion.
                        _ub_fetch_ctx = _CtxUBFetch(
                            hand=hand_counts, campo=field_counts,
                            evolvable=_ub_evolvable, bench_count=bench_count,
                            prefer_meowth_develop=_ub_prefer_meowth_develop,
                            t1_going_second_need_ogerpon=_t1_going_second_need_ogerpon,
                            t1_going_first_need_basic=_t1_going_first_need_basic,
                            has_energy_for_teal=has_energy_for_teal,
                            dipplin_priority=_dipplin_priority,
                            has_hydrapple=has_hydrapple,
                            op_ex_immune_active=op_has_ex_immune_active,
                            op_ex_immune_bench=op_has_ex_immune_bench,
                            no_attacker_prefer_meowth=_ub_no_attacker_prefer_meowth)
    
                        if card.id == Meowth_ex:
                            _ub_meo_ctx = _ctx_ub_fetch_meowth(
                                hand_counts, field_counts, bench_count,
                                state.turn, meowth_ability_lock,
                                _supp_values, _ub_prefer_meowth_develop,
                                _ub_hydra_dead_prefer_meowth,
                                _ub_mega_dead_prefer_meowth,
                                _ub_no_attacker_prefer_meowth,
                                _t1_going_second_meowth, _dipplin_priority,
                                _active_cant_attack_this_turn,
                                _mega_line_active, op_is_dragapult_dusknoir,
                                supporter_played=state.supporterPlayed,
                                ld_free=_meowth_ld_free,
                                meowth_manana=_ub_meowth_para_manana(ctx))
                            score = _resolver_con_traza(
                                "ub->meowth", _REGLAS_UB_MEOWTH, [],
                                _ub_meo_ctx, defecto=10)
    
                        elif card.id == Teal_Mask_Ogerpon_ex:
                            score = _resolver_con_traza(
                                "ub->ogerpon", _REGLAS_UB_OGERPON, [],
                                _ub_fetch_ctx, defecto=100)
    
                        elif state.turn == 2 and not ESTADO.we_go_first:
                            score = 10
    
                        elif card.id == Meganium:
                            score = _resolver_con_traza(
                                "ub->meganium", _REGLAS_UB_MEGANIUM, [],
                                _ub_fetch_ctx, defecto=100)
    
                        elif card.id == Hydrapple_ex:
                            # Rama migrada al MOTOR DE REGLAS (piloto fase
                            # 4): definiciones y comentarios estrategicos en
                            # _REGLAS_UB_HYDRAPPLE / _AJUSTES_UB_HYDRAPPLE
                            # (antes de agent()). PTCG_DEBUG imprime la traza.
                            if not has_hydrapple:
                                _ub_hyd_ctx = _ctx_ub_fetch_hydrapple(
                                    my_state, state, hand_counts,
                                    field_counts, _ub_evolvable,
                                    op_has_ex_immune_active,
                                    op_has_ex_immune_bench,
                                    _ub_hydra_dead_prefer_meowth)
                                score = _resolver_con_traza(
                                    "ub->hydrapple",
                                    _REGLAS_UB_HYDRAPPLE,
                                    _AJUSTES_UB_HYDRAPPLE,
                                    _ub_hyd_ctx, defecto=100)
                            else:
                                score = 20
    
                        elif card.id == Bayleef:
                            score = _resolver_con_traza(
                                "ub->bayleef", _REGLAS_UB_BAYLEEF, [],
                                _ub_fetch_ctx, defecto=150)
    
                        elif card.id == Dipplin:
                            score = _resolver_con_traza(
                                "ub->dipplin", _REGLAS_UB_DIPPLIN, [],
                                _ub_fetch_ctx, defecto=150)
    
                        elif card.id == Chikorita:
                            score = _resolver_con_traza(
                                "ub->chikorita", _REGLAS_UB_CHIKORITA, [],
                                _ub_fetch_ctx, defecto=200)
    
                        elif card.id == Applin:
                            score = _resolver_con_traza(
                                "ub->applin", _REGLAS_UB_APPLIN, [],
                                _ub_fetch_ctx, defecto=180)
    
                        elif card.id == Tapu_Bulu:
                            score = _resolver_con_traza(
                                "ub->tapu", _REGLAS_UB_TAPU, [],
                                _ub_fetch_ctx, defecto=50)
    
                        elif card.id == Pinsir:
                            score = _resolver_con_traza(
                                "ub->pinsir", _REGLAS_UB_PINSIR, [],
                                _ub_fetch_ctx, defecto=15)
    
                        elif card.id == Fezandipiti_ex:
                            score = _resolver_con_traza(
                                "ub->fez", _REGLAS_UB_FEZ, [],
                                _ub_fetch_ctx, defecto=10)
    
                        if card.id in ESTADO.CARTAS_ACTIVAS_EN_MAZO:
                            entry = ESTADO.CARTAS_ACTIVAS_EN_MAZO[card.id]
                            prized = entry[ESTADO_PREMIO]
                            total_copies = sum(entry.values())
                            accessible = total_copies - prized
    
                            if prized > 0 and accessible <= 1:
                                score += 150
    
                            if hand_counts.get(card.id, 0) >= 1:
                                score -= 150
    
                        # ORDEN DE LA LINEA DE EVOLUCION (user, registro_006
                        # paso 79 vs Marnie, PERDIDA). Con un Applin en banca y
                        # NINGUN Dipplin (ni en juego ni en mano), la Ultra Ball
                        # traia Hydrapple ex -- que no puede evolucionar nada y
                        # se queda muerto en la mano -- porque su rama
                        # `applin_evolucionable` (180) mas el bonus de copia
                        # premiada (+150 = 330) superaba al Dipplin (150), que
                        # es el eslabon que de VERDAD falta. La linea de
                        # Meganium ya lo hacia bien (Bayleef 850 > Meganium
                        # 200); esto iguala la de Hydrapple.
                        # Va DESPUES del bonus de escasez para tener la ULTIMA
                        # palabra: ese +150 es el que resucitaba la carta
                        # muerta. Si el eslabon no esta en el mazo no aparece
                        # entre las opciones, y con la banca llena la propia
                        # Ultra Ball ya se CANCELA antes de jugarse
                        # (`_evolve_possible_in_play`).
                        if card.id in _evo_huerfanos:
                            score = min(score, 30)
                        elif card.id in _evo_necesarios and score >= 50:
                            # `score >= 50` respeta los clamps de "carta
                            # muerta" (20/25/40) por si una rama futura los
                            # aplica a un eslabon intermedio.
                            score = max(score, 900)
    
                    elif select.effect is not None and select.effect.id == Meowth_ex:
    
                        # Bloque migrado al MOTOR DE REGLAS (fase 4):
                        # definiciones y comentarios estrategicos en
                        # _REGLAS_MEOWTH_FETCH (antes de agent()). Solo los
                        # Supporters entran al motor; el resto conserva el 50.
                        score = 50
                        if card.id in _MEOWTH_FETCH_SUPPS:
                            _mf_ctx = _CtxMeowthFetch(
                                card.id, _supp_values.get(card.id, 0),
                                hand_counts, _supp_values,
                                len(my_state.hand) if my_state.hand else 0,
                                (field_counts.get(Hydrapple_ex, 0) >= 1 or
                                 field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1),
                                getattr(op_state, 'handCount', 0),
                                (_active_cant_attack_this_turn
                                 or _sel_active_cant_attack),
                                _win_via_boss_gust, _gust_2prize_via_boss,
                                _deny_evo_via_boss, _meowth_devel_lillie,
                                op_is_alakazam_deck, _our_first_action_turn,
                                _ld_lillie_ofrecida)
                            score = _resolver_con_traza(
                                "meowth->fetch", _REGLAS_MEOWTH_FETCH, [],
                                _mf_ctx, defecto=50)
    
                    elif select.effect is not None and select.effect.id == Dawn:
    
                        # Bloque migrado al MOTOR DE REGLAS (fase 4):
                        # definiciones y comentarios estrategicos en
                        # _TABLA_DAWN_FETCH / _REGLAS_DAWN_* (antes de
                        # agent()).
                        _dawn_ctx = _ctx_ns_fetch(
                            my_state, state, hand_counts, field_counts,
                            bench_count, total_grass, has_hydrapple,
                            _active_needs_energy, op_has_ex_immune_active,
                            op_has_ex_immune_bench, op_is_lucario_deck,
                            meowth_ability_lock, _best_supp_in_hand_val,
                            _best_supp_in_mazo_val,
                            dragapult_no_tapu=_dragapult_no_tapu)
                        _dawn_entrada = _TABLA_DAWN_FETCH.get(card.id)
                        if _dawn_entrada is not None:
                            _dawn_et, _dawn_reglas, _dawn_defecto = _dawn_entrada
                            score = _resolver_con_traza(
                                _dawn_et, _dawn_reglas, [], _dawn_ctx,
                                defecto=_dawn_defecto)
                        else:
                            score = 50 - hand_counts.get(card.id, 0) * 30
    
                    else:
    
                        if card.id == Chikorita:
                            if field_counts[Chikorita] + field_counts[Bayleef] + field_counts[Meganium] >= 1:
                                score -= 150
                            else:
                                score += 80
                        elif card.id == Bayleef:
                            if field_counts[Chikorita] >= 1 or field_counts[Bayleef] >= 1:
                                score += 60
                            else:
                                score -= 50
                        elif card.id == Meganium:
                            if (field_counts[Bayleef] >= 1 or field_counts[Chikorita] >= 1) and not ESTADO.meganium_in_play:
                                score += 100
                            elif ESTADO.meganium_in_play:
                                score -= 200
                            else:
                                score -= 50
                        elif card.id == Applin:
                            if field_counts[Applin] + field_counts[Dipplin] + field_counts[Hydrapple_ex] >= 2:
                                score -= 100
                            else:
                                score += 60
                        elif card.id == Dipplin:
                            if field_counts[Applin] >= 1:
                                score += 70
                            else:
                                score -= 30
    
                            if op_has_ex_immune_active or op_has_ex_immune_bench:
                                score += 80
                        elif card.id == Hydrapple_ex:
                            if field_counts[Dipplin] >= 1 or field_counts[Applin] >= 1:
                                score += 90
                            elif has_hydrapple:
                                score -= 150
                            else:
                                score -= 30
                        elif card.id == Teal_Mask_Ogerpon_ex:
                            if field_counts[card.id] < 2:
                                score += 50
                            else:
                                score -= 100
                        elif card.id == Meowth_ex:
                            if field_counts[card.id] >= 1:
                                score -= 150
                            else:
                                score += 20
                        elif card.id == Fezandipiti_ex:
                            if field_counts[card.id] >= 1:
                                score -= 200
                            else:
                                score += 15
                        elif card.id == Forest_of_Vitality:
                            if not ESTADO.forest_in_play:
                                score += 70
                            else:
                                score -= 100
                        elif card.id == Basic_Grass_Energy:
                            if not state.energyAttached:
                                score += 40
                            else:
                                score -= 5
                        elif card.id == Tapu_Bulu:
                            if field_counts[card.id] >= 1:
                                score -= 100
                            elif ESTADO.meganium_in_play and (op_has_ex_immune_active or op_has_ex_immune_bench):
                                score += 60
                            else:
                                score -= 10
    
                    # LANA'S AID: LA MESA DECIDE QUE SE LEVANTA (user,
                    # registro_018 paso 118 vs Crustle, PERDIDA).
                    #
                    # Mesa: Tapu Bulu ACTIVO con 2 energias efectivas (Wood
                    # Hammer pide 4) y dos Meganium en juego, asi que UNA Planta
                    # vale {G}{G} y lo pone a atacar en el acto; banca LLENA
                    # (5/5); mano con un solo Hydrapple ex; descarte con 4
                    # Plantas, 2 Applin y 1 Dipplin. El agente jugo Lana's Aid
                    # -- la carta correcta -- y levanto 2 Applin + 1 Dipplin:
                    # con la banca llena y ningun Applin en juego, TRES cartas
                    # que no se pueden jugar. El turno murio sin atacar.
                    #
                    # La causa era estructural: Lana's Aid no tenia rama propia
                    # y caia al scorer generico de arriba, que solo sabe leer
                    # FORMAS de linea evolutiva ("¿me falta este eslabon?") y no
                    # mira ni la energia ni el hueco de banca. Sus numeros
                    # (Applin 260 > Dipplin 250 > Planta 240) decidian el menu.
                    #
                    # Aqui se sustituyen por la lectura de mesa, en tres bandas:
                    #   1. `desbloquea_hoy`: las Plantas que ponen a atacar a un
                    #      cuerpo ESTE turno. Un premio hoy gana a cualquier
                    #      desarrollo -- mismo criterio que `ns->grass`.
                    #   2. `demanda`: las que un atacante EN JUEGO sigue
                    #      pidiendo; siguen valiendo aunque no se adjunten hoy,
                    #      porque van a la MANO y el proximo turno se juegan.
                    #   3. el resto de Plantas cae por debajo del desarrollo.
                    # Y el desarrollo pierde su valor si la carta no se puede
                    # poner en juego (`_pokemon_injugable`).
                    #
                    # El ordinal (`_lana_orden_planta`) es lo que evita el fallo
                    # simetrico: con demanda 1 y 4 Plantas en el descarte, sin el
                    # las 4 empatarian arriba y se llevarian las 3 elecciones.
                    if _lana_plan is not None:
                        if card.id == Basic_Grass_Energy:
                            _lana_orden = _lana_orden_planta.get(len(scores), 0)
                            if (_lana_plan.desbloquea_hoy
                                    and _lana_orden < _lana_plan.cartas_para_atacar):
                                score = LANA_SEL_PLANTA_DESBLOQUEA
                            elif _lana_orden < _lana_plan.demanda:
                                score = LANA_SEL_PLANTA_DEMANDA
                            else:
                                score = LANA_SEL_PLANTA_SOBRANTE
                        elif _pokemon_injugable(card.id, field_counts,
                                                bench_count,
                                                my_state.benchMax):
                            score = LANA_SEL_INJUGABLE
    
                    # Matchup vs Cubchoo: Lana's Aid y Night Stretcher SOLO
                    # recuperan Energias Basicas del descarte, nunca Pokemon.
                    # El ataque de Cubchoo deja a nuestro activo sin poder
                    # atacar el proximo turno, asi que aprovechamos el turno
                    # para recargar energia y no gastamos estas cartas en
                    # recuperar Pokemon.
                    if (op_is_cubchoo_deck and select.effect is not None and
                            select.effect.id in (Night_Stretcher, Lanas_Aid)):
                        if card.id == Basic_Grass_Energy:
                            score = max(score, 900)
                        else:
                            score = SCORE_VETO
    
                    # GRAND TREE: TRAER LA RAIZ DE LA CADENA (regla del user,
                    # "si no tenemos el Pokemon basico lo podemos buscar en el
                    # mazo o recuperar de la pila de descarte"). Con el estadio
                    # en mesa (o una copia en la mano lista para bajarse) y
                    # NINGUN Basico en juego que sirva de raiz, la busqueda del
                    # turno debe traer ese Basico: bajarlo hoy convierte el
                    # proximo turno en una Etapa 2 gratis. Vale para CUALQUIER
                    # buscador (Ultra Ball, Bug Catching Set, Poke Pad) y para
                    # la recuperacion del descarte (Night Stretcher, Lana's
                    # Aid), porque el bono se aplica al FINAL del contexto
                    # TO_HAND, comun a todos ellos.
                    #
                    # Es un DESEMPATE, no una anulacion: `GT_FETCH_BONUS` (600)
                    # se suma sobre el score ya resuelto y NUNCA resucita una
                    # opcion vetada -- las whitelists de matchup y los vetos por
                    # coste siguen mandando.
                    if (_gt_quiere_basico and score > SCORE_VETO
                            and card.id in _gt_ranking_basicos):
                        score += GT_FETCH_BONUS
                        if card.id == max(_gt_ranking_basicos,
                                          key=_gt_ranking_basicos.get):
                            # La raiz que lleva al mejor cuerpo, por delante de
                            # las demas (mismo criterio que `_gt_planes`).
                            score += 100
    
                elif context == SelectContext.DISCARD:
    
                    score = 50
    
                    _has_recovery = (hand_counts.get(Night_Stretcher, 0) >= 1 or
                                    hand_counts.get(Lanas_Aid, 0) >= 1 or
                                    ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Night_Stretcher, {}).get(ESTADO_MAZO, 0) > 0 or
                                    ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Lanas_Aid, {}).get(ESTADO_MAZO, 0) > 0)
    
                    _ns_in_hand = (hand_counts.get(Night_Stretcher, 0) >= 1)
    
                    _total_supps_in_hand = (hand_counts.get(Lillie_Determination, 0) +
                                           hand_counts.get(Boss_Orders, 0) +
                                           hand_counts.get(Dawn, 0) +
                                           hand_counts.get(Lanas_Aid, 0) +
                                           hand_counts.get(Xerosic_Machinations, 0))
                    _protect_last_supporter = (not state.supporterPlayed and _total_supps_in_hand <= 1)
    
                    _refresh_supps_in_hand = (hand_counts.get(Lillie_Determination, 0) +
                                              hand_counts.get(Dawn, 0))
                    _protect_refresh_supporter = (not state.supporterPlayed and
                                                  _refresh_supps_in_hand <= 1)
    
                    _ogerpon_on_field = (field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1)
                    _ogerpon_playable = (hand_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1 and bench_count < 5)
                    _teal_dance_possible = ((_ogerpon_on_field or _ogerpon_playable) and
                                            hand_counts[Basic_Grass_Energy] >= 1)
    
                    _has_teal_dance_target = (bench_count >= 1 or
                                             hand_counts.get(Applin, 0) >= 1 or
                                             hand_counts.get(Chikorita, 0) >= 1 or
                                             hand_counts.get(Tapu_Bulu, 0) >= 1 or
                                             _ogerpon_playable)
                    _teal_dance_possible = _teal_dance_possible and _has_teal_dance_target
    
                    if card.id == Basic_Grass_Energy:
                        energy_in_hand = hand_counts[Basic_Grass_Energy]
    
                        if _teal_dance_possible:
    
                            if energy_in_hand >= 4:
                                score = 85
                            elif energy_in_hand >= 3:
                                score = 75
                            elif energy_in_hand == 2:
    
                                score = 18
                            else:
    
                                score = 2
                        else:
    
                            if energy_in_hand >= 4:
                                score = 92
                            elif energy_in_hand >= 3:
                                score = 85
                            elif energy_in_hand >= 2:
                                score = 70
                            else:
                                score = 35
                                if state.energyAttached:
                                    score = 65
    
                        if _has_recovery:
                            score += 5
    
                        if _ns_in_hand:
                            score += 5
    
                        energy_in_mazo = ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Basic_Grass_Energy, {}).get(ESTADO_MAZO, 0)
                        if energy_in_mazo >= 5:
                            score += 5
    
                    elif card.id == Forest_of_Vitality:
                        # Contra-estadio CRITICO (user, registro_005 paso 62 vs
                        # cornerstone_cubchoo, PERDIDA): el rival controla un
                        # estadio HOSTIL -- Neutralization Zone (1247) anula el
                        # dano de nuestros ex al activo de 1 premio (no podemos
                        # atacar) y Team Rocket's Watchtower (1256) apaga las
                        # Habilidades. La UNICA forma de removerlo es jugar
                        # NUESTRO estadio (Forest) para reemplazarlo. Cuando nos
                        # FUERZAN a descartar (Xerosic's Machinations) y Forest es
                        # nuestra unica copia jugable, es una carta CLAVE: hay que
                        # conservarla y soltar otra cosa (Ultra Ball / Tapu Bulu).
                        # Antes, con Meganium+Hydrapple en juego, Forest puntuaba
                        # 70 (descartable) SIN mirar el estadio hostil rival, y el
                        # agente lo tiraba -- perdiendo el unico modo de recuperar
                        # el ataque. El estadio propio en el DESCARTE no cuenta:
                        # solo se juega desde la mano.
                        _forest_counters_op_stadium = _contra_estadio_urgente(
                            neutralization_zone_active, watchtower_in_play,
                            ESTADO.forest_in_play, _festival_lead_hostil)
                        if (_forest_counters_op_stadium
                                and hand_counts.get(Forest_of_Vitality, 0) <= 1):
                            score = 2
                        elif ESTADO.forest_in_play:
                            score = 95
                        elif hand_counts[Forest_of_Vitality] > 1:
                            score = 88
                        elif ESTADO.meganium_in_play and has_hydrapple:
                            score = 70
                        elif ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Forest_of_Vitality, {}).get(ESTADO_MAZO, 0) >= 2:
                            score = 55
                        else:
                            score = 15
    
                    elif card.id == Meganium:
                        if ESTADO.meganium_in_play:
                            score = 95
                        elif field_counts.get(Bayleef, 0) >= 1:
                            # Solo es "casi intocable" cuando la linea esta lista de
                            # verdad: con un Bayleef en juego Meganium esta a una sola
                            # evolucion. Tener solo Chikorita NO cuenta (faltan dos
                            # evoluciones), asi que en ese caso cae a las ramas de
                            # abajo y queda mas descartable que un supporter sin jugar.
                            score = 3
                        elif ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) >= 1:
                            score = 40
                        else:
                            score = 20
    
                    elif card.id == Bayleef:
                        if ESTADO.meganium_in_play:
                            score = 88
                        elif field_counts.get(Chikorita, 0) >= 1:
                            score = 3
                        elif hand_counts.get(Bayleef, 0) > 1:
                            score = 75
                        elif ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) >= 1:
                            score = 50
                        else:
                            score = 25
    
                    elif card.id == Chikorita:
                        if ESTADO.meganium_in_play:
                            score = 85
                        elif field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) >= 1:
                            score = 75
                        elif hand_counts.get(Chikorita, 0) > 1:
                            score = 72
                        elif _ns_in_hand:
                            score = 62
                        elif _has_recovery:
                            score = 55
                        else:
                            score = 18
    
                    elif card.id == Applin:
                        if has_hydrapple:
                            score = 83
                        elif field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) >= 1:
                            score = 72
                        elif hand_counts.get(Applin, 0) > 1:
                            score = 70
                        elif _ns_in_hand:
                            score = 60
                        elif _has_recovery:
                            score = 52
                        else:
                            score = 18
    
                    elif card.id == Tapu_Bulu:
                        if field_counts.get(Tapu_Bulu, 0) >= 1:
                            score = 95
                        elif ESTADO.meganium_in_play and (op_has_ex_immune_active or op_has_ex_immune_bench):
                            score = 5
                        elif op_has_ex_immune_active or op_has_ex_immune_bench:
                            score = 20
                        else:
                            score = 90
    
                    elif card.id == Pinsir:
    
                        if field_counts.get(Pinsir, 0) >= 1:
                            score = 95
                        elif op_has_ex_immune_active or op_has_ex_immune_bench:
                            score = 15
                        else:
                            score = 90
    
                    elif card.id == Hydrapple_ex:
                        if ESTADO.op_is_crustle_deck or op_has_ex_immune_active or op_has_ex_immune_bench:
    
                            score = 96
                        elif has_hydrapple and hand_counts.get(Hydrapple_ex, 0) > 1:
                            score = 55
                        elif has_hydrapple:
                            score = 30
                        elif field_counts.get(Dipplin, 0) >= 1 or field_counts.get(Applin, 0) >= 1:
                            score = 3
                        elif (hand_counts.get(Dipplin, 0) >= 1 and
                              (ESTADO.forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                              ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) > 0):
                            score = 3
                        else:
                            score = 12
    
                    elif card.id == Teal_Mask_Ogerpon_ex:
                        if field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2:
                            score = 65
                        elif field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1:
                            score = 25
                        else:
                            score = 8
    
                    elif card.id == Dipplin:
                        if has_hydrapple and not (op_has_ex_immune_active or op_has_ex_immune_bench):
                            score = 55
                        elif field_counts.get(Applin, 0) >= 1:
                            score = 5
                        elif (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                              (ESTADO.forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                              ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) > 0):
                            score = 3
                        elif op_has_ex_immune_active or op_has_ex_immune_bench:
                            score = 8
                        else:
                            score = 18
    
                    elif card.id == Meowth_ex:
                        if field_counts.get(Meowth_ex, 0) >= 1:
                            score = 82
                        elif bench_count >= 5 and state.supporterPlayed:
    
                            score = 65
                        else:
    
                            score = 2
    
                    elif card.id == Fezandipiti_ex:
                        if field_counts.get(Fezandipiti_ex, 0) >= 1:
                            score = 82
                        elif ESTADO.ko_last_turn and bench_count < 5:
    
                            score = SCORE_NEVER
                        else:
    
                            score = 38
    
                    elif card.id == Boss_Orders:
                        if (ESTADO.op_is_crustle_deck or op_has_dwebble_bench) and hand_counts.get(Boss_Orders, 0) <= 1:
    
                            score = 2
                        elif hand_counts.get(Boss_Orders, 0) > 1:
                            score = 85
                        elif _protect_last_supporter:
                            score = 12
                        elif budew_on_op_field or op_has_dwebble_bench:
                            score = 10
                        elif op_prize <= 3:
                            score = 20
                        elif state.turn <= 5 and hand_counts.get(Dawn, 0) >= 1:
    
                            score = 30
                        else:
                            # Copia unica de Boss's Orders: aunque ya hayamos jugado
                            # el supporter del turno, conserva valor a futuro (gust al
                            # banco para rematar/desviar), asi que NO es descarte libre.
                            # Se protege, pero MENOS que Lillie's: si hay que soltar un
                            # supporter para pagar un coste, cae Boss's antes que Lillie's.
                            score = 22
    
                    elif card.id == Lillie_Determination:
                        if _lillie_protected_once:
                            # Copia sobrante (ya conservamos una): descartable.
                            score = 72
                        else:
                            _lillie_protected_once = True
                            if _protect_last_supporter:
    
                                score = 5
                            elif _protect_refresh_supporter:
    
                                score = 2
                            elif state.turn <= 5 and not state.supporterPlayed:
    
                                score = 8
                            elif hand_counts.get(Lillie_Determination, 0) > 1:
                                # Hay duplicados y ya jugamos supporter: conservamos
                                # una copia (puntaje bajo) y las demas seran las
                                # descartables via la rama de arriba.
                                score = 20
                            elif len(my_state.hand) >= 6:
                                # Copia unica: aun con el supporter ya jugado, Lillie's
                                # conserva valor a futuro (robo/mano nueva). Se protege
                                # POR DEBAJO de Boss's (Lillie tiene prioridad de
                                # conservacion), de modo que Boss's cae primero.
                                score = 16
                            else:
                                score = 14
    
                    elif card.id == Dawn:
                        if ESTADO.meganium_in_play and has_hydrapple:
                            score = 75
                        elif _protect_last_supporter:
                            score = 12
                        elif _protect_refresh_supporter:
                            score = 3
                        elif state.turn <= 5 and (hand_counts.get(Lillie_Determination, 0) >= 1 or
                                                  hand_counts.get(Boss_Orders, 0) >= 1):
    
                            score = 55
                        elif not ESTADO.meganium_in_play or not has_hydrapple:
                            score = 15
                        else:
                            score = 50
    
                    elif card.id == Lanas_Aid:
    
                        if hand_counts.get(Lanas_Aid, 0) > 1:
                            score = 80
                        elif _protect_last_supporter:
                            score = 12
                        elif len(my_state.discard) <= 2:
                            score = 75
                        else:
                            score = 35
    
                    elif card.id == Xerosic_Machinations:
                        # Xerosic's Machinations (user): vs Alakazam es la carta
                        # que capa Powerful Hand (20 x carta en la mano rival) --
                        # PROTEGERLA como se protege la linea de Meganium. En
                        # otros mazos es moderadamente descartable (disrupcion
                        # generica, unica copia).
                        if op_is_alakazam_deck:
                            score = 5
                        else:
                            score = 60
    
                    elif card.id == Night_Stretcher:
                        # Night Stretcher solo recupera un Pokemon o una Energia
                        # BASICA del descarte. Regla (user): NO jugarlo si el UNICO
                        # objetivo recuperable es Energia basica que NO podemos usar
                        # este turno (ya adjuntamos energia: state.energyAttached).
                        # Recuperar una energia muerta malgasta la carta sin aportar
                        # nada. Si hay un Pokemon recuperable, o aun podemos adjuntar
                        # la energia (energyAttached False), el veto NO aplica.
                        _ns_disc_poke = any(
                            (card_table.get(_dc.id) is not None
                             and card_table[_dc.id].cardType == CardType.POKEMON)
                            for _dc in my_state.discard)
                        _ns_disc_basic_energy = any(
                            _dc.id == Basic_Grass_Energy
                            for _dc in my_state.discard)
                        _ns_only_dead_energy = (
                            not _ns_disc_poke
                            and _ns_disc_basic_energy
                            and state.energyAttached)
                        if _ns_only_dead_energy:
                            score = SCORE_VETO
                        elif hand_counts.get(Night_Stretcher, 0) > 1:
                            score = 78
                        elif len(my_state.discard) <= 1:
                            score = 70
                        else:
                            score = 30
    
                    elif card.id == Bug_Catching_Set:
                        if hand_counts.get(Bug_Catching_Set, 0) > 1:
                            score = 76
                        elif itchy_pollen_active:
                            score = 85
                        else:
                            score = 45
    
                    elif card.id == Ultra_Ball:
    
                        if hand_counts.get(Ultra_Ball, 0) > 1:
                            score = 95
                        else:
                            score = 38
    
                    elif card.id == Poke_Pad:
                        if itchy_pollen_active:
                            score = 85
                        else:
                            score = 55
    
                    elif card.id == Unfair_Stamp:
    
                        score = SCORE_NEVER
    
                    # Estrategia vs Comfey (user, registro_005): descarte por
                    # Xerosic's Machinations (nos deja SOLO 3 cartas en la mano). La
                    # prioridad de MANTENER es: Energias > Night Stretcher > Lana's
                    # Aid > Unfair Stamp > resto de entrenadores. El score aqui es de
                    # DESCARTE (mayor = se descarta antes), asi que las cartas a
                    # MANTENER llevan score BAJO. Un Ogerpon ex EXTRA (ya hay 2 en
                    # juego) es inutil -> se descarta; si aun caben (<2), se conserva
                    # por encima de los entrenadores porque es el plan del matchup.
                    if op_is_comfey_deck:
                        if card.id == Basic_Grass_Energy:
                            score = 80
                        elif card.id == Teal_Mask_Ogerpon_ex:
                            score = (850 if field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2
                                     else 120)
                        elif card.id == Night_Stretcher:
                            score = 300
                        elif card.id == Bug_Catching_Set:
                            # Surtidor de Plantas del matchup (ver allowlist):
                            # se conserva junto a NS/Lana's, bajo la energia.
                            score = 350
                        elif card.id == Lanas_Aid:
                            score = 400
                        elif card.id == Unfair_Stamp:
                            score = 500
                        else:
                            score = 850
    
                elif context == SelectContext.RECOVER_SPECIAL_CONDITION:
    
                    if hasattr(card, 'id'):
                        score = 50
                elif context == SelectContext.AFFECT_SPECIAL_CONDITION:
    
                    score = 50
                elif context == SelectContext.ATTACH_FROM:
                    score = energy_score(card, o.area == AreaType.ACTIVE)
                    # Objetivo de Ripening Charge cuando la habilidad se juega
                    # POR LA CURACION (ver `_ripen_heal_serial`): la Planta va al
                    # cuerpo que muere al golpe proyectado y que con +30 sobrevive.
                    # 39500 gana a todo el desarrollo normal y queda BAJO el
                    # atacante futuro (_tapu_future_charge, 40000) y bajo las
                    # cargas letales (41000/42000), que ademas ya vetan el flag.
                    if (_ripen_heal_serial is not None and score > 0
                            and getattr(card, 'serial', None) == _ripen_heal_serial):
                        score = max(score, RIPEN_HEAL_TARGET_SCORE)
    
        elif o.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            if card is None:
                score = SCORE_VETO
            else:
                data = card_table[card.id]
                if data.cardType == CardType.POKEMON:
                    score = SCORE_DEVELOP_BASE
    
                    _block_4th_ex = False
                    if ((ESTADO.op_is_crustle_deck or ESTADO.op_is_cornerstone_deck)
                            and card.id in OUR_EX_IDS
                            # Meowth ex es UTILIDAD (Last-Ditch busca Boss's para
                            # gustear la banca cuando el activo es inmune): no
                            # cuenta como un 4o atacante ex y no se bloquea.
                            and not (card.id == Meowth_ex
                                     and _meowth_immune_boss_engine)
                            # Fezandipiti ex con Flip the Script VIVA
                            # (ko_last_turn) tampoco es un "4o atacante": bajarlo
                            # roba 3 cartas ESTE turno (registro_008 paso 74 vs
                            # Mega Starmie con Cornerstone de tech: el bloqueo
                            # del 4o ex aplastaba el 22000 del refill y el draw
                            # se perdia). Sin la habilidad viva, el veto sigue.
                            and not (card.id == Fezandipiti_ex
                                     and ESTADO.ko_last_turn)):
                        _ex_in_play = sum(field_counts.get(_ex_id, 0)
                                          for _ex_id in OUR_EX_IDS)
                        if _ex_in_play >= 3:
                            _block_4th_ex = True
    
                    # CUERPO ex REDUNDANTE CON POWERFUL HAND LETAL (user,
                    # registro_010 paso 150 vs Alakazam, PERDIDA -- log
                    # 88903365). Vs Alakazam el remate del rival no es su activo:
                    # es Boss's Orders (3 copias en su mazo) + Powerful Hand
                    # (20 x su mano, y su mano CRECE). Cuando ese dano proyectado
                    # ya MATA de un golpe al cuerpo que ibamos a bajar y al rival
                    # le bastan 2 premios para cerrar, un ex DUPLICADO en la banca
                    # no es desarrollo: es un remate servido. En el registro
                    # bajamos un TERCER Teal Mask Ogerpon ex (210 PV) con la mano
                    # rival en 12 (Powerful Hand proyectado 280); al turno
                    # siguiente gustearon un Ogerpon ex de banca y lo noquearon con
                    # 220 para sus 2 ultimos premios.
                    #
                    # Alcance DELIBERADAMENTE estrecho, para no tocar el desarrollo
                    # normal del matchup:
                    #   * solo COPIAS REDUNDANTES (`field_counts[card.id] >= 1`):
                    #     la PRIMERA copia de cualquier ex sigue bajando -- puede
                    #     ser el unico atacante o el motor del turno;
                    #   * solo con `op_prize <= 2`: si al rival le faltan 3+
                    #     premios, un objetivo mas no cierra la partida;
                    #   * solo si Powerful Hand REMATA ese cuerpo (>= PV impresos);
                    #   * exento Meowth ex con motor vivo (`_alk_ld_engine_vivo` /
                    #     `_meowth_immune_boss_engine`): es UTILIDAD -- su
                    #     Last-Ditch busca justo el Xerosic que capa Powerful
                    #     Hand -- y exento Fezandipiti ex con Flip the Script viva
                    #     (roba 3 ESTE turno), igual que en el bloque de arriba.
                    # Los overrides de "busqueda ya pagada" (`_ub_meowth_pending`
                    # / `_ub_fez_pending`) van DESPUES en la rama, asi que un
                    # cuerpo ya cavado con Ultra Ball nunca se queda muerto en la
                    # mano por este veto.
                    _alk_ex_redundante_letal = False
                    if (op_is_alakazam_deck and card.id in OUR_EX_IDS
                            and op_prize <= 2
                            and field_counts.get(card.id, 0) >= 1
                            and not (card.id == Meowth_ex
                                     and (_alk_ld_engine_vivo
                                          or _meowth_immune_boss_engine))
                            and not (card.id == Fezandipiti_ex
                                     and ESTADO.ko_last_turn)):
                        _alk_hp_cuerpo = getattr(data, 'hp', 0) or 0
                        if (_alk_hp_cuerpo and _powerful_hand_proyectado(
                                getattr(op_state, 'handCount', 0))
                                >= _alk_hp_cuerpo):
                            _alk_ex_redundante_letal = True
    
                    if _block_4th_ex or _alk_ex_redundante_letal:
                        score = SCORE_VETO
                    elif card.id == Chikorita:
    
                        _meg_line_count = field_counts[Chikorita] + field_counts[Bayleef] + field_counts[Meganium]
                        _max_meg_line = 2 if (ESTADO.op_is_crustle_deck or ESTADO.op_is_cornerstone_deck) else 1
                        if _meg_line_count >= _max_meg_line:
                            score = SCORE_VETO
                        else:
                            _forest_avail = ESTADO.forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1
    
                            if (op_has_mega_starmie_active and
                                    not (_forest_avail and hand_counts.get(Bayleef, 0) >= 1)):
                                score = SCORE_VETO
                            else:
                                score = 21500
                                if op_is_mirror or op_is_fire_deck or ESTADO.op_is_crustle_deck:
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
                            ESTADO.forest_in_play and hand_counts.get(Dipplin, 0) >= 1)
    
                        # FASE E3 (plan Marnie, seccion 4): un Applin RECIEN
                        # bajado tiene 40 PV y no tiene habilidad, asi que no
                        # paga el goteo de Froslass -- pero el snipe automatico
                        # (30) mas UN contador movido por Adrena-Brain ya lo
                        # matan. Dejarlo un turno suelto en la banca es un premio
                        # REGALADO (partida 3). Forest of Vitality deja evolucionar
                        # Pokemon Planta el turno en que se juegan, asi que la
                        # linea entera cabe en un turno: la regla es RESERVAR las
                        # piezas hasta poder encadenarlas, no bajar el basico
                        # "para ir montando". Misma forma que el veto de Mega
                        # Starmie de mas abajo y que el de Dragapult de aqui al
                        # lado; lo que cambia es que el umbral sale de la VENTANA
                        # DE REGALO y no de una lista de mazos. Sin Munkidori en
                        # mesa `_op_movable_dmg` es 0, el snipe pelado (30) no
                        # llega a los 40 PV y la regla no se enciende.
                        _applin_hp_impreso = getattr(
                            card_table.get(Applin), 'hp', 0) or 0
                        _applin_regalado = (
                            ESTADO._op_movable_dmg > 0
                            and _applin_hp_impreso > 0
                            and _applin_hp_impreso <= _ventana_de_regalo(
                                card, False, ESTADO._op_bench_snipe_dmg))
    
                        if bench_count >= 5:
                            score = SCORE_VETO
                        elif _dragapult_snipe_setup and not _applin_evolvable_now:
                            score = SCORE_VETO
                        elif _applin_regalado and not _applin_evolvable_now:
                            score = SCORE_VETO
                        elif (op_is_cubchoo_deck and
                                field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0)
                                + field_counts.get(Hydrapple_ex, 0) >= 1):
                            # Matchup Cubchoo (user): solo UNA linea
                            # Applin->Dipplin->Hydrapple ex en juego a la vez. Si ya
                            # hay un miembro de la linea en mesa, no bajar otro Applin.
                            score = SCORE_VETO
                        else:
                            _forest_avail = ESTADO.forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1
    
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
                            ESTADO.meganium_in_play or
                            field_counts.get(Bayleef, 0) >= 1 or
                            field_counts.get(Chikorita, 0) >= 1)
                        if (ESTADO.op_is_crustle_deck or ESTADO.op_is_cornerstone_deck) and \
                                not ESTADO.op_has_mega_kangaskhan and \
                                field_counts[card.id] >= 2:
    
                            score = SCORE_VETO
                        elif bench_count >= 5:
                            score = SCORE_VETO
                        elif field_counts[card.id] >= 2:
    
                            if hand_counts.get(Basic_Grass_Energy, 0) >= 1:
                                score = 20500
                            elif ESTADO.op_has_mega_kangaskhan and _meg_line_present:
    
                                score = 20500
                            else:
                                score = SCORE_VETO
                        else:
                            score = 21000
                    elif card.id == Meowth_ex:
    
                        if meowth_ability_lock:
                            # Team Rocket's Watchtower anula la habilidad de
                            # Meowth ex (Pokemon incoloro): no bajarlo a la banca.
                            score = SCORE_VETO
                        elif _stamp_blocks_supp_chain:
                            # ERROR DE SECUENCIA (user, registro_004 p34 vs Mega
                            # Starmie ex; registro_008 paso 90 vs Alakazam): con
                            # Unfair Stamp (Item ACE SPEC) JUGABLE este turno
                            # (`_stamp_blocks_supp_chain` = nos noquearon el turno
                            # pasado + el Sello sigue en mano), NO bajar Meowth ex
                            # para buscar NINGUN Supporter: el Sello BARAJA TODA la
                            # mano al mazo, asi que el Supporter que trae el
                            # Last-Ditch Catch se pierde de inmediato y ademas
                            # expusimos un cuerpo de 2 premios en la banca. El
                            # propio Sello ya refresca (robamos 5) y disrumpe (el
                            # rival solo roba 2), asi que el fetch es redundante.
                            # Orden correcto: items -> Unfair Stamp -> y solo
                            # DESPUES, si hace falta, bajar Meowth ex (el Sello es
                            # Item: al jugarse sale de la mano, el flag pasa a
                            # False y la cadena Meowth se re-habilita).
                            #
                            # POSICION (paso 90, GANADA suboptima): este veto
                            # estaba DEBAJO de los motores Boss's via Meowth
                            # (_win_via_boss_gust/_gust_2prize_via_boss 22500,
                            # _deny_evo_via_boss 22000, _meowth_immune_boss_engine
                            # 22000), exentos con el argumento de que "buscan un
                            # Boss's que se JUEGA este turno, no se baraja". Ese
                            # argumento es FALSO: `_REGLAS_BOSS_PLAY` veta el Boss's
                            # con `cede_a_unfair_stamp` (y lo mismo hacen los
                            # scorers de Xerosic/Lillie's/Dawn/Lana's: TODOS los
                            # `_SUPP_PLAY_IDS` ceden al Sello), asi que el Boss's
                            # buscado NO se puede jugar este turno y encima se
                            # baraja al mazo. Con `_gust_2prize_via_boss` activo
                            # (Fezandipiti ex de 210 PV en banca rival, rematable
                            # por Wood Hammer) el agente bajaba Meowth ex, cavaba
                            # el Boss's, jugaba el Sello -- que devolvia el Boss's
                            # al mazo -- y solo lo recupero por SUERTE entre las 5
                            # cartas robadas. Por eso el veto va ARRIBA de todo:
                            # mientras el Sello siga jugable ningun fetch de
                            # Supporter puede pagar. Deck-agnostico: no nombra
                            # cartas del rival ni arquetipos.
                            score = SCORE_VETO
                        elif ((_win_via_boss_gust or _gust_2prize_via_boss)
                                and hand_counts.get(Boss_Orders, 0) == 0
                                and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Boss_Orders, {}).get(ESTADO_MAZO, 0) > 0
                                and field_counts[card.id] < 2
                                and _meowth_ld_free
                                and bench_count < 5):
                            # Motor Boss's ganador via Meowth ex (user, registro_011
                            # paso 148 vs Dragapult ex, GANADA): jugar Meowth ex
                            # para que Last-Ditch Catch busque Boss's Orders (que
                            # esta en el MAZO, no en la mano) y rematar gusteando+
                            # noqueando (win_via_boss_gust: p.ej. a 1 premio de
                            # ganar, gustear un basico fragil de banca -Dreepy 70-
                            # que el activo NOQUEA, en vez de atacar al activo rival
                            # que NO muere). Se permite incluso con UN Meowth ex ya
                            # en juego (field < 2) SIEMPRE que su Last-Ditch siga
                            # disponible este turno (`_meowth_ld_free`): el Meowth de
                            # banca de turnos anteriores ya gasto su habilidad, pero
                            # uno NUEVO desde la mano vuelve a buscar. Antes exigia
                            # `field_counts == 0`, por lo que con un Meowth ya en
                            # banca esta linea ganadora no se veia y el agente
                            # atacaba sin noquear.
                            score = 22500
                        elif (_deny_evo_via_boss
                                and hand_counts.get(Boss_Orders, 0) == 0
                                and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                                    Boss_Orders, {}).get(ESTADO_MAZO, 0) > 0
                                and field_counts[card.id] < 2
                                and _meowth_ld_free
                                and bench_count < 5
                                and not state.supporterPlayed):
                            # Motor Boss's de VALOR via Meowth ex (plan motor
                            # Meowth, mejora A): el rival tiene una pre-evo de
                            # linea ex ENERGIZADA en banca (Gabite/Duraludon/
                            # Morgrem...) que NOQUEAMOS tras gustearla, y el
                            # Boss's esta en el MAZO. La maquinaria in-hand
                            # (`_boss_deny_evo`) exige Boss's en mano y el veto
                            # de abajo (`_active_ready_attacker`) mataba el
                            # fallback generico: no habia NINGUN camino y el
                            # agente atacaba al muro dejando evolucionar la
                            # amenaza. Bajar Meowth -> Last-Ditch busca Boss's
                            # (1280) -> gustear+noquear la pre-evo. 22000: bajo
                            # el remate ganador (22500), sobre devel-lillie y
                            # turno muerto (21800). Con Boss's YA en mano no
                            # dispara (el motor in-hand lo juega directo sin
                            # gastar el cuerpo Meowth).
                            score = 22000
                        elif _meowth_immune_boss_engine:
                            # Motor Boss's vs ACTIVO INMUNE (user: Hydrapple ex vs
                            # Cornerstone Mask Ogerpon ex activo + Mega Lucario ex
                            # en banca): el activo rival ANULA a nuestro atacante
                            # (Cornerstone anula habilidad; Crustle/Sylveon anulan
                            # ex; Neutralization Zone anula ex vs 1-premio) -> el
                            # ataque hace 0. Con Boss's en el MAZO (no en mano),
                            # bajar Meowth ex para que Last-Ditch Catch lo busque,
                            # gustear un objetivo ATACABLE de la banca y rematarlo,
                            # en vez de atacar al muro inmune por 0. 22000: nivel de
                            # los otros motores Boss's, sobre refresco/turno muerto.
                            # Con Boss's YA en mano no dispara (se juega directo).
                            # Deck-agnostico.
                            score = 22000
                        elif (field_counts[card.id] < 2
                                and _meowth_ld_free
                                and bench_count < 5
                                and not state.supporterPlayed
                                and hand_counts.get(Lillie_Determination, 0) == 0
                                and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                                    Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0
                                and (len(my_state.hand) if my_state.hand else 0) <= 2
                                and _ready_attacker_count <= 1
                                and _ara_act is not None
                                and _ara_act.id not in OUR_EX_IDS
                                and prize_count(_ara_act) == 1
                                and (not op_has_froslass)):
                            # Motor de refresco Meowth -> Lillie's en TABLERO POBRE
                            # (user, registro_006 paso 57 vs Alakazam, GANADA): el
                            # activo es un atacante CHIP de 1 premio (Dipplin) que
                            # PUEDE noquear al activo rival pero es fragil, NO hay
                            # ningun atacante LISTO en banca (_ready_attacker_count
                            # <= 1, solo el propio activo) y la mano es minima
                            # (<= 2 cartas). Aunque el activo pueda atacar/noquear,
                            # bajar Meowth ex NO consume el ataque: se banca el
                            # Basico, Last-Ditch Catch trae Lillie's, se refresca la
                            # mano (roba 6) para armar un SEGUNDO atacante y DESPUES
                            # se ataca en el mismo turno (no perdemos el KO). A
                            # diferencia del refresco generico de abajo (exige
                            # field==0 y que el activo NO noquee), aqui se permite
                            # con UN Meowth ya en banca (field<2, con su Last-Ditch
                            # aun libre) y AUNQUE el activo noquee. Gates estrictos
                            # (mano<=2, unico atacante = el chip activo de 1 premio,
                            # sin Froslass) para no exponer un 2o Meowth (2 premios)
                            # salvo en tablero realmente pobre. Deck-agnostico.
                            score = 21600
                        elif (field_counts[card.id] < 2
                                and _meowth_ld_free
                                and bench_count <= 1
                                and not state.supporterPlayed
                                and not meowth_ability_lock
                                and not op_has_froslass
                                and hand_counts.get(Lillie_Determination, 0) == 0
                                and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                                    Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0
                                and _active_ready_attacker
                                and _ready_attacker_count <= 1
                                and my_prize >= 3
                                and _no_second_attacker_path
                                and _active_doomed_real):
                            # Motor de refresco Meowth -> Lillie's SIN atacante de
                            # repuesto (user, registro_006 paso 78 vs Mega Lucario
                            # ex): el activo (Ogerpon ex) PUEDE atacar pero NO noquea
                            # y el rival lo remata el proximo turno (remate REAL, no
                            # el heuristico active_ko_likely que subestima a Mega
                            # Lucario); la banca NO tiene ningun ATACANTE (solo un
                            # basico de utilidad) y desde la mano NO hay forma de
                            # montar un 2o atacante este turno (ni basico atacante
                            # jugable ni evolucion legal: la linea Hydrapple/Dipplin
                            # esta atascada sin Applin/Dipplin en juego). Bajar
                            # Meowth ex NO consume el ataque: Last-Ditch Catch trae
                            # Lillie's, se refresca la mano (roba 6) para encontrar
                            # piezas de atacante y DESPUES se ataca/retira en el mismo
                            # turno. Se permite con UN Meowth ya en banca (field<2,
                            # con su Last-Ditch libre) y AUNQUE el activo sea un ex.
                            # Gates estrictos (unico atacante = el activo condenado,
                            # sin camino a 2o atacante, no en rango de remate propio,
                            # sin Froslass) para no exponer un cuerpo de 2 premios
                            # salvo en tablero realmente pobre. `bench_count <= 1`:
                            # solo en tablero MUY fino (<=1 cuerpo en banca) donde hay
                            # que cavar; con 2+ cuerpos preferimos el retiro-sacrificio
                            # limpio del descuadre ([[descuadre-generalizado-ex-...]])
                            # sin comprometer Lillie's ni exponer un 2o Meowth.
                            # Deck-agnostico.
                            score = 21550
                        elif (_active_ready_attacker
                                and field_counts[card.id] == 0
                                and bench_count < 5
                                and not state.supporterPlayed
                                and hand_counts.get(Lillie_Determination, 0) == 0
                                and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                                    Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0
                                and (len(my_state.hand) if my_state.hand else 0) <= 4
                                and _ready_attacker_count <= 2
                                and not (ESTADO.plan.attacker == 0
                                         and ESTADO.plan.remain_hp is not None
                                         and ESTADO.plan.remain_hp <= 0)
                                and not meowth_ability_lock
                                and (not op_has_froslass
                                     or _ready_attacker_count <= 1)):
                            # Regla (user, logs 86592502 turno 9 vs Archaludon ex,
                            # 86593647 turno 4 vs Mega Starmie ex y 86699707 paso 51
                            # vs Marnie's Grimmsnarl ex, todas PERDIDAS):
                            # EXCEPCION al veto de abajo. Aunque el activo YA pueda
                            # atacar, si la MANO es DEBIL (<=4 cartas) y aun queda una
                            # Lillie's Determination en el MAZO, bajar Meowth ex para
                            # que su habilidad Last-Ditch Catch traiga Lillie's y
                            # jugarla (baraja la mano y roba 6) da MUCHAS mas opciones
                            # de juego y ataque que jugar un cuerpo REDUNDANTE (2o
                            # Teal Mask Ogerpon ex, 21000) o lanzar un ataque DEBIL no
                            # letal (Dipplin ~1100) vs un muro de 330 HP. Se exige que
                            # haya un atacante listo pero POCOS (<=2: si ya hay muchos
                            # listos no hace falta refrescar), que el ataque del activo
                            # NO sea letal (si noquea, se ataca y se cobra el premio),
                            # que no se haya jugado Supporter y que no este anulada su
                            # habilidad (Watchtower siempre veta). Froslass tambien
                            # veta EXCEPTO cuando nuestro UNICO atacante listo es el
                            # propio activo (_ready_attacker_count <= 1) y su ataque
                            # NO es letal: ahi no hay presion real (un chip vs el muro)
                            # y cavar por Lillie's vale mas que el riesgo de banquear
                            # Meowth ex ante Froslass (caso 86699707: activo Dipplin
                            # chip vs Grimmsnarl ex 320 HP). Supera al cuerpo
                            # redundante (21500 > 21000) para que Meowth ex gane.
                            score = 21500
                        elif (_active_ready_attacker
                                and field_counts[card.id] == 0
                                and bench_count <= 1
                                and bench_count < 5
                                and (active_ko_likely or active_hp_ratio <= 0.2)
                                and not meowth_ability_lock
                                and not state.supporterPlayed
                                and hand_counts.get(Lillie_Determination, 0) == 0
                                and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                                    Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0):
                            # EXCEPCION al veto de abajo (user, registro_014 paso
                            # 107, vs Marnie): el activo era un Teal Mask Ogerpon
                            # ex a 10/210 PV -- se cae al primer golpe -- y la
                            # banca tenia UN solo Pokemon. Aunque el activo sea un
                            # atacante LISTO, bajar Meowth ex aqui es gratis: no
                            # consume el ataque (se baja el Basico y se ataca
                            # despues en el mismo turno) y encadena Last-Ditch
                            # Catch -> Lillie's -> rehacer la mano, dando cuerpo
                            # de repuesto para cuando caiga el activo y muchas mas
                            # opciones de juego. El veto de abajo (log 86511741 vs
                            # Mega Abomasnow) esta pensado para un activo SANO con
                            # banca desarrollada, donde el cuerpo de 2 premios no
                            # compensa; con el activo condenado y la banca vacia
                            # la situacion se invierte. Se puntua por debajo del
                            # refresco pleno (21500) y por encima del ataque.
                            score = 21400
                        elif (_active_ready_attacker
                                and field_counts[card.id] == 0):
                            # Regla (user, log 86511741 paso 57, vs Mega Abomasnow
                            # ex, PERDIDA): si nuestro ACTIVO ya es un atacante
                            # LISTO para atacar este turno, NO bajamos Meowth ex
                            # solo para buscar un Supporter. Es un cuerpo de 2
                            # premios y no necesitamos partidario: preferimos
                            # desarrollar con Ultra Ball/Dawn (p.ej. buscar Teal
                            # Mask Ogerpon ex y acelerar energia con Teal Dance) o
                            # atacar directamente. La gustada LETAL con Boss's ya se
                            # resolvio en la rama anterior (_win_via_boss_gust).
                            score = SCORE_VETO
                        elif (hand_counts.get(Lillie_Determination, 0) >= 1
                                and field_counts[card.id] == 0):
                            # Regla (user): si YA tenemos Lillie's Determination EN
                            # LA MANO, NO se juega Meowth ex en NINGUN turno; se
                            # despliega el resto y se juega Lillie's. Bajar Meowth ex
                            # solo malgastaria un cuerpo de 2 premios y su busqueda
                            # de Supporter, porque Lillie's baraja TODA la mano en el
                            # mazo -> la carta buscada se perderia. La gustada LETAL
                            # con Boss's se maneja antes (rama _win_via_boss_gust).
                            # Si Lillie's NO esta en la mano pero SI en el mazo, este
                            # veto NO aplica: se deja pasar a `_meowth_devel_lillie`
                            # para bajar Meowth ex, BUSCAR Lillie's y jugarla.
                            score = SCORE_VETO
                        elif (_bcs_playable_in_hand
                                and hand_counts.get(Lillie_Determination, 0) >= 1
                                and field_counts[card.id] == 0
                                and not (_win_via_boss_gust or _gust_2prize_via_boss)):
    
                            score = SCORE_VETO
                        elif (_meowth_devel_lillie
                                and hand_counts.get(Meowth_ex, 0) >= 1
                                and hand_counts.get(Lillie_Determination, 0) == 0
                                and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0
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
                                and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                                    Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0
                                and not op_has_froslass
                                and not (state.turn == 1 and ESTADO.we_go_first)):
    
                            score = 21700
                        elif field_counts[card.id] >= 1:
                            score = SCORE_VETO
                        elif bench_count >= 5:
                            score = SCORE_VETO
                        elif state.turn == 1 and ESTADO.we_go_first:
    
                            _other_basics_in_hand = any(
                                hand_counts.get(pid, 0) >= 1
                                for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                            Tapu_Bulu, Fezandipiti_ex, Pinsir))
                            if bench_count == 0 and not _other_basics_in_hand:
                                score = 19000
                            else:
                                score = SCORE_VETO
                        elif state.turn == 2 and not ESTADO.we_go_first:
    
                            if (not state.supporterPlayed and
                                    _best_supp_in_hand_val < 500 and
                                    _best_supp_in_mazo_id == Lillie_Determination and
                                    _best_supp_in_mazo_val >= 650):
                                score = 20500
                            else:
                                score = SCORE_VETO
                        elif state.supporterPlayed:
                            score = SCORE_VETO
                        elif op_has_froslass:
                            # Normalmente NO se banca Meowth ex (2 premios) contra
                            # Froslass (pinga la banca). EXCEPCION (user, registro_008
                            # paso 84, vs Marnie/Froslass, PERDIDA): en un TURNO
                            # MUERTO -- el activo no puede ATACAR ni RETIRARSE (0
                            # energia < coste de retirada), no hay atacante de banca
                            # que subir y no hay cartas en mano para habilitar un
                            # ataque -- con hueco en banca y el motor de refresco en
                            # el MAZO (Meowth ex -> Last-Ditch Catch busca Lana's Aid
                            # o Lillie's Determination), bajar Meowth ex es la UNICA
                            # jugada util: recuperar 3 energias del descarte (Lana's
                            # Aid) o refrescar la mano (Lillie's) abre opciones de
                            # ataque los proximos turnos. La eleccion Lana's/Lillie's
                            # la resuelve la busqueda del Supporter.
                            _mw_act_reloc = my_state.active[0] if my_state.active else None
                            _mw_can_retreat = (
                                _mw_act_reloc is not None
                                and len(_mw_act_reloc.energies)
                                >= RETREAT_COST.get(_mw_act_reloc.id, 1))
                            _mw_engine_in_mazo = (
                                ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                                    Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0
                                or ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                                    Lanas_Aid, {}).get(ESTADO_MAZO, 0) > 0)
                            if (_active_cant_attack_this_turn
                                    and not _mw_can_retreat
                                    and field_counts[card.id] == 0
                                    and bench_count < 5
                                    and not state.supporterPlayed
                                    and hand_counts.get(Lillie_Determination, 0) == 0
                                    and _mw_engine_in_mazo):
                                score = 21600
                            else:
                                score = SCORE_VETO
                        elif (_active_cant_attack_this_turn and
                              not state.supporterPlayed and
                              hand_counts.get(Lillie_Determination, 0) == 0 and
                              ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0):
    
                            score = 21800
                        elif (bench_count >= 1 and
                              hand_counts.get(Lillie_Determination, 0) >= 1 and
                              hand_counts.get(Ultra_Ball, 0) >= 1 and
                              not (ESTADO.op_is_crustle_deck or op_is_drednaw_deck or op_is_sylveon_deck) and
                              not (_best_supp_in_mazo_id == Boss_Orders and _best_supp_in_mazo_val >= 650)):
    
                            score = SCORE_VETO
                        elif _best_supp_in_hand_val >= 500:
    
                            _boss_in_mazo = ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Boss_Orders, {}).get(ESTADO_MAZO, 0) > 0
                            _boss_val = _supp_values.get(Boss_Orders, 0)
                            if ESTADO.op_is_crustle_deck and _boss_in_mazo and _boss_val >= 900 and hand_counts.get(Boss_Orders, 0) == 0:
                                score = 21500
                            elif (op_is_drednaw_deck and _boss_in_mazo and _boss_val >= 650
                                  and hand_counts.get(Boss_Orders, 0) == 0):
    
                                score = 21500
                            elif (op_is_sylveon_deck and _boss_in_mazo and _boss_val >= 650
                                  and hand_counts.get(Boss_Orders, 0) == 0):
    
                                score = 21500
                            else:
                                score = SCORE_VETO
                        else:
    
                            _meowth_score = SCORE_VETO
                            _target_id = _best_supp_in_mazo_id
                            _target_val = _best_supp_in_mazo_val
    
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
    
                                _forest_avail = ESTADO.forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1
                                if _forest_avail:
                                    _meowth_score = 20500
                            elif _target_id == Lanas_Aid and _target_val >= 600:
    
                                _meowth_score = 20000
    
                            score = _meowth_score
    
                        # VALIDACION FINAL: el Supporter que el Last-Ditch Catch
                        # traeria YA esta en la mano -> la busqueda es redundante
                        # y bajar Meowth ex solo regala un cuerpo de 2 premios.
                        # Se cancela la jugada (el turno sigue y el Supporter se
                        # juega por su propia escalera). Va al FINAL de la cadena
                        # para tener la ultima palabra tambien sobre los motores
                        # de arriba (Boss's ganador 22500, deny-evo 22000...):
                        # esos miran solo si el BOSS'S esta en mano, no cual
                        # seria el fetch real -- en el registro_010 el motor
                        # apuntaba a Boss's pero el fetch acabo trayendo el
                        # Xerosic que ya teniamos. Ver `_meowth_fetch_prediccion`.
                        #
                        # `_meowth_fetch_pierde_el_turno` es la otra mitad del
                        # mismo chequeo: el fetch traeria algo que NO tenemos,
                        # pero un Supporter de la mano se lleva el UNICO hueco
                        # del turno, asi que la carta buscada tampoco se juega
                        # hoy (registro_004 paso 36: Lillie's buscada vs Xerosic
                        # en mano). Mismo sitio y mismo efecto: cancelar la
                        # jugada y seguir el turno con el Supporter de la mano.
                        if ((_meowth_fetch_redundante
                             or _meowth_fetch_pierde_el_turno) and score > 0):
                            score = SCORE_VETO
                    elif card.id == Fezandipiti_ex:
    
                        # Con Lillie's Determination + Teal Mask Ogerpon ex +
                        # energia de Planta en la mano, la jugada correcta es bajar
                        # Teal (futuro atacante), usar Teal Dance y despues jugar
                        # Lillie's Determination para refrescar la mano. La habilidad
                        # de Fezandipiti (Flip the Script) solo roba hasta 3 cartas,
                        # asi que con la mano cargada no aporta y gastaria el turno /
                        # la banca en un no-atacante. Dejamos que Teal (21000) gane.
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
                        elif (op_is_lucario_deck or ESTADO.op_is_crustle_deck
                              or ESTADO.op_is_cornerstone_deck or op_is_sylveon_deck
                              # FASE E1 (plan Marnie, D5): con FROSLASS en mesa
                              # la banca no es un sitio seguro. Fezandipiti ex
                              # tiene HABILIDAD, asi que paga el peaje de
                              # Freezing Shroud (20 por ronda por Froslass) sin
                              # que el rival gaste nada, y son DOS premios que
                              # Munkidori puede rematar donde estan. Partida 2:
                              # Meowth ex y Fezandipiti ex ocuparon banca los 13
                              # turnos absorbiendo 40/ronda cada uno. Mismo
                              # criterio que ya aplicaba a Meowth ex (ver el
                              # `elif op_has_froslass` de su rama): solo se baja
                              # si se COBRA hoy -- Flip the Script viva
                              # (ko_last_turn) -- o si la banca esta VACIA, donde
                              # un KO al activo seria la derrota.
                              or op_has_froslass):
                            # Contra Mega Lucario (Lucha), Crustle, Cornerstone
                            # Ogerpon y Sylveon: Fezandipiti ex vale 2 premios y su
                            # habilidad Flip the Script solo sirve tras ser noqueado.
                            # NO lo bajamos por desarrollo al comienzo de la partida.
                            # Si la habilidad esta viva (ko_last_turn) se conserva la
                            # ruta normal. Si no, esperamos al final del turno y solo
                            # lo bajamos como ULTIMO recurso cuando la banca esta
                            # VACIA: sin banca, un KO a nuestro activo el proximo
                            # turno = derrota. Con score bajo (500) cualquier
                            # desarrollo real (basico ~20000) se juega antes; Fez solo
                            # cae si no queda otra forma de tener un cuerpo en juego.
                            if ESTADO.ko_last_turn:
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
    
                            if ESTADO.ko_last_turn:
                                fez_score = 22000
    
                                if len(my_state.hand) <= 3:
                                    fez_score = 22500
    
                            if not ESTADO.ko_last_turn and bench_count <= 2:
                                _all_bench_basics = True
                                for _bp_fez in my_state.bench:
                                    if _bp_fez is not None:
                                        _bp_fez_data = card_table.get(_bp_fez.id)
                                        if _bp_fez_data and (getattr(_bp_fez_data, 'stage1', False) or
                                                             getattr(_bp_fez_data, 'stage2', False)):
                                            _all_bench_basics = False
                                            break
                                # Contra Mega Lucario (tipo Lucha) NO bajamos
                                # Fezandipiti ex solo por "desarrollo": es debil a
                                # Lucha ({F}) y vale 2 premios, y su habilidad Flip
                                # the Script esta muerta si no nos noquearon el
                                # turno anterior. Bajarlo asi solo regala un KO de
                                # 2 premios facil. Con la habilidad viva
                                # (ko_last_turn) se conserva la ruta de 22000.
                                if _all_bench_basics and not op_is_lucario_deck:
                                    fez_score = max(fez_score, 15000)
    
                            score = fez_score
                    elif card.id == Tapu_Bulu:
    
                        _tapu_first_turn = (state.turn <= 2)
                        _tapu_in_play_count = (
                            (1 if (my_state.active and my_state.active[0] is not None) else 0)
                            + bench_count)
    
                        _op_is_crustle_like = (
                            ESTADO.op_is_crustle_deck or op_has_ability_immune_active or
                            ESTADO.op_is_cornerstone_deck or op_is_sylveon_deck or
                            op_has_ex_immune_active or op_has_ex_immune_bench or
                            op_is_iron_thorns_deck)
    
                        # Respaldo del UNICO atacante del matchup (autopsia
                        # iron_thorns p030 t2, paso 1 plan jul 2026): contra un
                        # rival que anula nuestro motor de habilidades o hace 0
                        # nuestro dano ex (_op_is_crustle_like), Tapu Bulu es EL
                        # atacante -- y si el unico que tenemos en juego es el
                        # ACTIVO, cuando caiga no hay relevo. El veto de copia
                        # redundante (abajo) se evaluaba ANTES de las ramas de
                        # matchup y el 2o Tapu moria en mano (END con 7 cartas).
                        # Guards: exactamente 1 en juego, ese 1 es el activo, y
                        # el matchup es de muro/lock. 21800: bajo la prioridad
                        # de la 1a copia (22000+), sobre el desarrollo generico.
                        _tapu_backup_vs_lock = (
                            field_counts[card.id] == 1 and
                            _op_is_crustle_like and
                            my_state.active and my_state.active[0] is not None
                            and my_state.active[0].id == Tapu_Bulu)
    
                        # vs DRAGAPULT no se baja con el tablero desarrollado
                        # (>2 Pokemon en juego). Ver `_dragapult_no_tapu`: aqui
                        # es donde se aplica, y va PRIMERO en la cadena porque
                        # las ramas de abajo (en particular la de
                        # `_tapu_in_play_count >= 4 and meganium_in_play`, que
                        # es la que lo bajo en el registro_003 paso 43) no
                        # miran el matchup. El veto cede ante el muro
                        # (`_op_is_crustle_like`): ahi Tapu es el unico
                        # atacante y manda la colision de matchups.
                        if _dragapult_no_tapu and not _op_is_crustle_like:
                            score = SCORE_VETO
                        elif field_counts[card.id] >= 1:
                            if _tapu_backup_vs_lock:
                                score = 21800
                            else:
                                score = SCORE_VETO
                        elif (_tapu_in_play_count >= 4 and not _op_is_crustle_like and
                              ESTADO.meganium_in_play and not _tapu_first_turn):
    
                            score = 16000
                        elif (_tapu_in_play_count > 2 and not ESTADO.op_is_crustle_deck
                                and not op_is_iron_thorns_deck
                                # Cornerstone (autopsia p004 t2): Tapu Bulu es
                                # EL atacante del matchup (los Ogerpon/Hydrapple
                                # con habilidad hacen 0); la aglomeracion no
                                # justifica dejarlo muerto en mano.
                                and not ESTADO.op_is_cornerstone_deck
                                and not op_has_ability_immune_active):
    
                            score = SCORE_VETO
                        elif ESTADO.op_is_crustle_deck:
    
                            score = 22000
                            if ESTADO.meganium_in_play:
                                score = 22500
                        elif op_has_ability_immune_active or ESTADO.op_is_cornerstone_deck:
    
                            score = 22500
                        elif op_is_iron_thorns_deck:
                            # Iron Thorns ex (P1.4 plan B, autopsia iron_thorns
                            # p007 t16): con Initialization delante, Teal Dance /
                            # Ripening / Last-Ditch estan muertas y el agente
                            # cerraba el turno con Tapu Bulu EN MANO (66 turnos
                            # esteriles en 15 derrotas). Tapu es el atacante
                            # manual sin habilidad: bajarlo es el plan A, como
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
    
                            # Bajar Tapu Bulu vs Mega Lucario solo cuando es el
                            # sacrificio prioritario (rival con proteccion a ex o
                            # motor Hydrapple ex + Meganium) o cuando no hay otro
                            # basico de 1 premio (Applin / Chikorita) disponible.
                            # Si hay alternativa desechable, conservamos Tapu Bulu.
                            score = 21500
                        elif _tapu_first_turn:
    
                            score = SCORE_VETO
                        elif not ESTADO.meganium_in_play:
    
                            score = SCORE_VETO
                        else:
    
                            score = 16000
    
                        # Tapu Bulu solo se baja despues de jugar todos los items
                        # ("artefactos") que el juego considere jugar. Si aun queda
                        # algun item en la mano, rebajamos la prioridad de Tapu Bulu
                        # por debajo de la banda de items utiles: los items que valen
                        # la pena (puntaje mas alto) se juegan primero y, cuando solo
                        # queden items sin valor (puntaje bajo), Tapu Bulu vuelve a
                        # ganar y se baja. Aplica SOLO a Tapu Bulu.
                        _tapu_items_pending = any(
                            hand_counts.get(_it_id, 0) >= 1 for _it_id in DECK_ITEM_IDS)
                        if _tapu_items_pending and score > TAPU_WAIT_FOR_ITEMS_SCORE:
                            score = TAPU_WAIT_FOR_ITEMS_SCORE
                    elif card.id == Pinsir:
    
                        score = SCORE_VETO
    
                    if (ESTADO._poke_pad_target_id > 0 and card.id == ESTADO._poke_pad_target_id and
                            bench_count < 5):
                        if score <= 0:
                            score = 21000
    
                    if (ESTADO._ub_meowth_pending and card.id == Meowth_ex and
                            field_counts[Meowth_ex] < 2 and _meowth_ld_free
                            and bench_count < 5
                            and not state.supporterPlayed
                            and not _stamp_blocks_supp_chain):
                        # `_ub_meowth_pending` (una Ultra Ball previa trajo Meowth ex)
                        # fuerza bajarlo para encadenar Last-Ditch Catch -> buscar el
                        # Supporter (Lillie's) y REFRESCAR la mano. Regla del user
                        # (registro_008 paso 71 vs Hop's, GANADA): si la Ultra Ball
                        # ELIGIO buscar Meowth ex, hay que COMPLETAR la jugada y
                        # bajarlo SIEMPRE -- aunque el activo ya sea un atacante
                        # listo: bajar Meowth a la banca NO impide atacar despues, y
                        # dejarlo muerto en mano desperdicia la Ultra Ball entera
                        # (aqui la mano quedaba VACIA tras atacar; Meowth -> Lillie's
                        # la refresca). Antes exigia `not _active_ready_attacker` y
                        # con el Hydrapple listo se atacaba sin bajarlo. La guarda
                        # correcta es `not state.supporterPlayed`: si el Supporter YA
                        # se jugo este turno (registro 006 paso 57 vs Alakazam), la
                        # Lillie's buscada ni se podria jugar y bajar un cuerpo de 2
                        # premios es redundante -> ahi se mantiene atacar.
                        # GUARD Unfair Stamp (user, registro_008 paso 115, episodio
                        # 87676139 vs Mega Lucario, PERDIDA): con un Unfair Stamp
                        # JUGABLE en mano (`_stamp_blocks_supp_chain`: nos noquearon
                        # el turno pasado y el Sello sigue en mano), este override
                        # NO aplica: bajar Meowth ANTES del Stamp desperdicia el
                        # Last-Ditch (el Supporter buscado -Lillie's- se BARAJA al
                        # mazo con el Sello sin poder jugarse) y expone un cuerpo
                        # de 2 premios. Orden correcto: items -> Unfair Stamp ->
                        # y solo DESPUES bajar Meowth ex si vuelve a estar
                        # disponible. Sin el guard, este override (21000) pisaba el
                        # veto Stamp+ko_last_turn de la cadena principal.
                        if score <= 0:
                            score = 21000
    
                    _alk_meowth_hand_engine = (
                        card.id == Meowth_ex and op_is_alakazam_deck
                        and not state.supporterPlayed
                        and getattr(op_state, 'handCount', 0) >= 6
                        and hand_counts.get(Xerosic_Machinations, 0) == 0
                        and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                            Xerosic_Machinations, {}).get(ESTADO_MAZO, 0) > 0
                        and field_counts[Meowth_ex] < 2 and _meowth_ld_free
                        and bench_count < 5
                        and not _stamp_blocks_supp_chain
                        # ...y solo si la HABILIDAD va a usarse de verdad (user,
                        # log 88162677 paso 16 vs Alakazam, PERDIDA): con dos
                        # Lillie's en la mano en NUESTRO PRIMER TURNO, este motor
                        # bajaba el Meowth ex (21500, y ademas eximia al veto
                        # generico "no bajar Meowth si ya hay Lillie's en mano")
                        # y en el paso siguiente el prompt de Last-Ditch Catch
                        # RECHAZABA el fetch por `_meowth_skip_fetch` -- el mismo
                        # tablero, dos respuestas opuestas. Resultado: un cuerpo
                        # de 2 premios regalado en la banca, la Lillie's jugada
                        # igual y cero valor. Atando el motor al MISMO predicado
                        # que la habilidad las dos decisiones no pueden volver a
                        # contradecirse. Los casos que justificaron el motor
                        # (registro_006 p76, registro_008 p85, registro_010 p147)
                        # tienen `_meowth_devel_lillie` False -- tablero ya
                        # desarrollado o sin Lillie's en mano --, asi que
                        # `_meowth_fetch_ya_en_mano` es False y siguen bajando el
                        # Meowth para cavar el Xerosic.
                        and not _meowth_fetch_ya_en_mano)
                    if _alk_meowth_hand_engine:
                        # Motor Xerosic vs Alakazam con Meowth ex YA en mano
                        # (user, registro_006 paso 76 vs Alakazam, GANADA): con
                        # el Supporter libre, la mano rival gorda (>=6 -> Powerful
                        # Hand nos noquea el proximo turno) y el Xerosic aun en
                        # el MAZO, bajar el Meowth ex SIEMPRE -- aunque el activo
                        # sea un atacante listo (bajarlo no impide atacar): Last-
                        # Ditch Catch busca el Xerosic, se juega (rival a 3
                        # cartas) y DESPUES se ataca. Es la version "en mano" de
                        # la cadena Ultra Ball -> Meowth -> Xerosic (rama
                        # `_ub_meowth_pending` de arriba); la reserva del ultimo
                        # slot de banca vs Alakazam existe justo para esto.
                        # 21500: SOBRE el rush de desarrollo (Applin con Forest
                        # = 21200) -- con UN solo slot de banca, bajar el Applin
                        # bloquea el motor Xerosic para siempre y Powerful Hand
                        # (20 x 11 = 220) nos noquea (user, registro_010
                        # paso 147 vs Alakazam, PERDIDA: el agente bajo el
                        # Applin y los DOS Meowth ex murieron en mano).
                        if score < 21500:
                            score = 21500
    
                    # DESCUADRE DE PREMIOS (user, registro_002 paso 27 vs Raging
                    # Bolt/Ogerpon PERDIDA; y registro_002 vs Mega Abomasnow ex):
                    # estos mazos ONE-SHOTEAN a cualquiera de nuestros ex (Raging
                    # Bolt con Bellowing Thunder; Mega Abomasnow ex con su ataque).
                    # Siempre que nuestro activo sea un ex que NO puede noquear al
                    # activo rival este turno, bajar un cuerpo de UN premio (Tapu
                    # Bulu el preferido: es ademas el atacante no-ex) para luego
                    # retirar el ex y ponerlo delante -- si nos noquean, ceden 1
                    # premio y no 2, y el rival necesita KOs de 2-3 para ganar.
                    # Solo si aun no hay un cuerpo de 1 premio en la banca (con uno
                    # basta para el pivote). `_descuadre_matchup` ya excluye nuestro
                    # primer turno partiendo primeros. (sin guard de score: el boost
                    # debe anteponerse a los vetos genericos de desarrollo, que no
                    # conocen este plan)
                    if _descuadre_matchup:
                        _rb_act = my_state.active[0] if my_state.active else None
                        _rb_data = card_table.get(card.id)
                        _rb_es_1premio_basico = (
                            _rb_data is not None
                            and not _rb_data.ex and not _rb_data.megaEx
                            and not _rb_data.stage1 and not _rb_data.stage2)
                        _rb_banca_con_1premio = any(
                            bp is not None and prize_count(bp) == 1
                            for bp in (my_state.bench or []))
                        if (_rb_es_1premio_basico
                                and _rb_act is not None
                                and _rb_act.id in OUR_EX_IDS
                                and not _active_already_kos
                                and not _rb_banca_con_1premio):
                            score = 21850 if card.id == Tapu_Bulu else 21700
    
                    # Matchup Cubchoo (user, cambio 5): la banca SOLO puede tener,
                    # vs este mazo, la linea de Hydrapple ex (Applin/Dipplin/
                    # Hydrapple ex, una), la linea de Meganium (Chikorita/Bayleef/
                    # Meganium, una), hasta DOS Teal Mask Ogerpon ex y UN Meowth ex
                    # (solo cuando haga falta para BUSCAR una Lillie's Determination
                    # del mazo). El resto de Pokemon (Tapu Bulu, Fezandipiti ex,
                    # Pinsir...) NO se juega. Se aplica tras las excepciones de
                    # poke_pad/ub_meowth y ANTES del fallback de banca vacia (mas
                    # abajo), que sigue garantizando que nunca nos quedemos sin
                    # Pokemon en juego (jugada legal forzada).
                    if op_is_cubchoo_deck:
                        _CUB_ALLOWED_PLAY = CUBCHOO_ALLOWED_PLAY_IDS
                        # COLISION DE MATCHUPS (user, registro_004 turno 4): con
                        # un Cornerstone Mask Ogerpon ex rival en juego, su
                        # Cornerstone Stance anula el dano de TODOS nuestros
                        # Pokemon CON habilidad -- incluidos Teal Mask Ogerpon ex
                        # e Hydrapple ex, que esta lista SI permite. El unico
                        # atacante real pasa a ser Tapu Bulu, que la lista
                        # excluia: el agente bajaba un 2o Ogerpon ex (dano 0) y
                        # dejaba a Tapu muerto en la mano. Se amplia la whitelist
                        # con Tapu Bulu SOLO en ese caso; sin Cornerstone el plan
                        # anti-Cubchoo queda intacto.
                        if op_has_ability_immune_active or ESTADO.op_is_cornerstone_deck:
                            _CUB_ALLOWED_PLAY = _CUB_ALLOWED_PLAY + (Tapu_Bulu,)
                        if card.id not in _CUB_ALLOWED_PLAY:
                            score = SCORE_VETO
                        elif (card.id == Teal_Mask_Ogerpon_ex
                                and field_counts[card.id] >= 2):
                            # No mas de dos Teal Mask Ogerpon ex en juego.
                            score = SCORE_VETO
                        elif card.id == Meowth_ex:
                            # Un solo Meowth ex y solo si hay una Lillie's
                            # Determination que buscar en el mazo (no ya en mano).
                            _cub_meowth_ok = (
                                field_counts[Meowth_ex] == 0
                                and hand_counts.get(Lillie_Determination, 0) == 0
                                and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                                    Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)
                            if not _cub_meowth_ok:
                                score = SCORE_VETO
    
                    # Reserva de banca vs Alakazam (user): con UN solo slot libre
                    # (bench_count == 4) y un Xerosic's Machinations aun en el
                    # MAZO, no llenar el ultimo slot con un cuerpo que no avanza
                    # el plan: se reserva para Meowth ex, que busca el Xerosic
                    # (capar Powerful Hand = 20 x carta en la mano rival). Se
                    # vetan los cuerpos REDUNDANTES (duplicado de algo ya en
                    # juego, o Fezandipiti ex: un 2-premios sin rol vs Alakazam);
                    # se permiten Meowth ex y las primeras copias de las lineas de
                    # ataque (Chikorita/Applin/Tapu...). El rescate anti-softlock de
                    # banca vacia (mas abajo) exige bench_count == 0, asi que nunca
                    # entra en conflicto con esta regla (bench_count == 4).
                    #
                    # CONDICION DEL MOTOR (user, registro_010 paso 150 vs
                    # Alakazam, PERDIDA -- log 88903365): antes se exigia
                    # `field_counts[Meowth_ex] == 0`, es decir "ningun Meowth ex
                    # en juego". Eso contradice al propio motor que la reserva
                    # protege: `_alakazam_dig_xerosic_engine` y la rama PLAY de
                    # Meowth ex admiten una SEGUNDA copia mientras queden < 2 en
                    # campo y la Last-Ditch del turno siga libre (`_meowth_ld_free`
                    # -- el Meowth de banca de turnos anteriores ya gasto la suya,
                    # pero uno NUEVO desde la mano vuelve a buscar). Con un Meowth
                    # ex ya banqueado la reserva se apagaba y el agente metia en el
                    # ultimo hueco un TERCER Teal Mask Ogerpon ex (score 20500,
                    # tier DEVELOP, que ademas manda por ORDEN sobre todo lo demas).
                    # Acto seguido la Ultra Ball SI cavo el 2o Meowth ex... que se
                    # quedo MUERTO en la mano con la banca llena: sin Last-Ditch no
                    # hubo Xerosic, el rival ataco con 11 cartas en mano (Powerful
                    # Hand = 220) y remato con Boss's Orders sobre un Teal Mask
                    # Ogerpon ex de banca (210 PV) para sus 2 ultimos premios.
                    # Se exige ademas que quede un Meowth ex ALCANZABLE (mano o
                    # mazo): sin cuerpo que ocupe el hueco no hay nada que
                    # reservar. Las tres condiciones viven juntas en
                    # `_alk_ld_engine_vivo` (calculado junto a `_meowth_ld_free`).
                    if (op_is_alakazam_deck and bench_count == 4
                            and _alk_ld_engine_vivo
                            and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                                Xerosic_Machinations, {}).get(ESTADO_MAZO, 0) > 0
                            and score > 0
                            and card.id != Meowth_ex):
                        if (field_counts.get(card.id, 0) >= 1
                                or card.id == Fezandipiti_ex):
                            score = SCORE_VETO
    
                    # Req H: vs Mega Lucario con un Riolu gusteable+noqueable en
                    # la banca rival y banca propia establecida, NO desarrollar
                    # ni refrescar la mano: cedemos la jugada a Boss's Orders
                    # (gustear + noquear al Riolu para cortar su linea). Vetamos
                    # el desarrollo de CUALQUIER Pokemon (tier DEVELOP) para que
                    # Boss's (supporter, tier 0) sea la jugada elegida. El flag
                    # exige bench_count>=2, asi que el rescate anti-softlock de
                    # mas abajo (banca vacia) nunca entra en conflicto.
                    #
                    # EXENCION: Fezandipiti ex con Flip the Script VIVA (user,
                    # registro_006 paso 91, episodio 88710543 vs Mega Lucario,
                    # GANADA por suerte). Bajarlo NO es "desarrollar ni refrescar
                    # la mano": es un Pokemon, no consume el Supporter del turno,
                    # asi que el Boss's al que este veto cede el turno se sigue
                    # jugando despues. Vetarlo era, encima, un BLOQUEO CIRCULAR de
                    # tres piezas (misma clase que el paso 78): el Fezandipiti
                    # recien cavado con la Ultra Ball no bajaba (este veto), el
                    # Boss's no se jugaba (`cede_a_unfair_stamp`) y el Unfair Stamp
                    # se quedaba en 2000 (`mano_con_pokemon_o_evo`: "primero baja
                    # el Pokemon"). Ganaba el Sello por descarte y BARAJABA al mazo
                    # el Fezandipiti que acababa de costar dos cartas -- y con el,
                    # el propio Boss's al que este veto le cedia el turno. La rama
                    # de Fezandipiti ya decide sola el caso vs Lucha: con la
                    # habilidad muerta NO se baja (2 premios regalados), con la
                    # habilidad viva vale 22000. Este veto la pisaba en silencio.
                    if _lucario_riolu_gust and not (
                            card.id == Fezandipiti_ex and ESTADO.ko_last_turn
                            and field_counts.get(Fezandipiti_ex, 0) == 0
                            and bench_count < 5):
                        score = SCORE_VETO
    
                    # COMPLETAR LA CADENA UB -> FEZANDIPITI EX (user,
                    # registro_006 pasos 90-91, episodio 88710543 vs Mega
                    # Lucario). Si la Ultra Ball de ESTE turno eligio buscar
                    # Fezandipiti ex (`_ub_fez_pending`; el objetivo
                    # `fez_tras_ko` solo se elige con la habilidad VIVA), el
                    # cuerpo BAJA: la busqueda ya se pago con dos descartes y el
                    # unico motivo de cavarlo es cobrar Flip the Script este
                    # turno. En el registro, el veto de ORDEN de Req H
                    # (`_lucario_riolu_gust`) dejaba el Fezandipiti en la mano y
                    # el Unfair Stamp lo BARAJABA de vuelta al mazo: Ultra Ball,
                    # dos cartas y el robo de 3, todo a la basura (solo se
                    # recupero por SUERTE entre las 5 cartas del Sello).
                    # Va DESPUES de todos los vetos de la rama, igual que el
                    # override hermano de Meowth ex, porque son justo esos vetos
                    # los que contradicen una busqueda ya pagada. Los limites
                    # FISICOS siguen mandando (banca llena / copia ya en juego) y
                    # la habilidad tiene que estar viva.
                    if (ESTADO._ub_fez_pending and card.id == Fezandipiti_ex
                            and score <= 0
                            and ESTADO.ko_last_turn
                            and field_counts.get(Fezandipiti_ex, 0) == 0
                            and bench_count < 5):
                        score = 22000
    
                    # Rescate anti-softlock: con la banca vacia, subir un basico
                    # que quedo en <=0 para poder desplegarlo (jugada legal).
                    # EXCEPCION: en nuestro primer turno, con una Lillie's
                    # Determination jugable en mano, NO forzamos a Meowth ex a la
                    # banca (respetamos el veto: se despliega el resto y se juega
                    # Lillie's; si tras jugar Lillie's sigue sin haber banca,
                    # supporterPlayed pasa a True y este rescate se rehabilita para
                    # bajar Meowth ex como ultimo recurso). Esto aplica AUNQUE ya
                    # tengamos un Meowth ex en juego (p.ej. como activo): bajar un
                    # SEGUNDO Meowth ex es aun mas inutil (su busqueda de Supporter
                    # se baraja con Lillie's y expone otro cuerpo de 2 premios).
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
    
                    # Guard anti-DONK del primer turno partiendo PRIMEROS
                    # (user, registro_001 pasos 6-7 vs Cinderace/Archaludon,
                    # PERDIDA): banca VACIA, solo el basico activo, y el ACTIVO
                    # rival tiene un ataque de UNA energia cuyo dano proyectado
                    # (debilidad incluida, via _op_active_attack_damage_to que
                    # asume el adjunte rival: 0e+1) NOQUEA a nuestro activo
                    # (Turbo Flare 50 x2 Fuego->Planta = 100 >= Chikorita 70).
                    # Sin banca, ese KO en su primer turno es DERROTA
                    # instantanea. Bajar Meowth ex SI aunque haya Lillie's en
                    # mano: yendo primeros el Supporter NI SIQUIERA es jugable
                    # este turno (el motor no lo ofrece), asi que el motivo del
                    # hold ("jugar Lillie's y no barajar el fetch") no aplica.
                    # Meowth es el cuerpo que evita la derrota y su Last-Ditch
                    # trae una Lillie's para el proximo turno. Si el rival NO
                    # proyecta el donk, se mantiene la conducta previa (no
                    # bajarlo: regla no-meowth-para-lillie).
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
                            ESTADO._field_at_turn_start.get(Meowth_ex, 0)
                            if ESTADO._field_at_turn_start is not None else False)
                        if meowth_ability_lock:
                            # Team Rocket's Watchtower anula la habilidad de los
                            # Pokemon {C}: bajar Meowth ex ahora NO activaria
                            # Last-Ditch Catch (no busca Supporter). No lo jugamos
                            # hasta reemplazar el estadio (p.ej. con Forest).
                            score = SCORE_VETO
                        elif _meowth_played_this_turn:
                            score = SCORE_VETO
                        elif field_counts[Meowth_ex] >= 2:
                            score = SCORE_VETO
                        elif field_counts[Meowth_ex] >= 1 and score <= 0:
                            score = SCORE_VETO
                        elif (hand_counts.get(Lillie_Determination, 0) >= 1
                              # EXCEPCION motor Xerosic vs Alakazam (user,
                              # registro_008 paso 85, episodio 88119461,
                              # PERDIDA): con la mano rival GORDA (15 cartas ->
                              # Powerful Hand 20x17=340 nos one-shotea) el fetch
                              # de Last-Ditch NO apunta a Lillie's sino al
                              # XEROSIC del mazo (capar la mano rival a 3). Que
                              # haya una Lillie's en mano no lo hace redundante:
                              # la escalera del fetch vs Alakazam con mano rival
                              # >=6 ya elige Xerosic. Sin esta excepcion el veto
                              # pisaba el 21500 del motor y el agente gusteaba
                              # con Boss's dejando Powerful Hand cargado.
                              and not _alk_meowth_hand_engine):
                            # Regla (user, registro_003 p17 vs Archaludon): NUNCA
                            # bajar Meowth ex para buscar (Last-Ditch Catch) una
                            # Lillie's Determination si YA tenemos una en la mano:
                            # el fetch es redundante y expone un cuerpo de 2 premios.
                            # Primero se juega la Lillie's que tenemos. UNICA
                            # EXCEPCION: nuestro PRIMER turno partiendo PRIMERO, con
                            # la banca VACIA y un solo BASICO en el activo distinto
                            # de Tapu Bulu (hace falta desarrollar banca). Si tras
                            # jugar Lillie's seguimos sin banca, el rescate anti-
                            # softlock (supporterPlayed=True, sin Lillie's en mano)
                            # rehabilita bajar Meowth como ultimo recurso.
                            _mw_act = my_state.active[0] if my_state.active else None
                            _mw_act_data = (card_table.get(_mw_act.id)
                                            if _mw_act is not None else None)
                            _mw_lone_basic = (
                                _mw_act is not None and _mw_act.id != Tapu_Bulu
                                and _mw_act_data is not None
                                and not getattr(_mw_act_data, 'stage1', False)
                                and not getattr(_mw_act_data, 'stage2', False))
                            # Regla del PRIMER TURNO (user, log 88461779 vs
                            # Alakazam): con Lillie's Determination ya en la
                            # mano NO se hace NADA por bajar o buscar un Meowth
                            # ex -- ni desde la mano ni con Ultra Ball. Meowth
                            # ex en el primer turno existe SOLO para traer la
                            # Lillie's que no tenemos. La excepcion de
                            # DESARROLLO (banca vacia + basico solitario) ya no
                            # basta por si sola: se exige ademas el DONK
                            # PROYECTADO (`_meowth_antidonk_now`), donde el
                            # Meowth no se baja por su busqueda sino como cuerpo
                            # que evita perder la partida en el acto (user,
                            # registro_001 pasos 6-7 vs Cinderace). Sin donk,
                            # se despliega el resto de la mano y la Lillie's se
                            # juega en cuanto sea legal.
                            _mw_dev_exc = (
                                _our_first_turn and ESTADO.we_go_first
                                and bench_count == 0 and _mw_lone_basic
                                and _meowth_antidonk_now)
                            if not _mw_dev_exc:
                                score = SCORE_VETO
    
                        # Regla (user, registro_004 paso 60 vs Abomasnow, PERDIDA):
                        # Meowth ex solo sirve para Last-Ditch Catch -> BUSCAR un
                        # Supporter del mazo. Si YA jugamos un Supporter este turno
                        # (`supporterPlayed`), ese fetch es INUTIL (no se puede jugar
                        # un segundo Supporter este turno), asi que bajar un cuerpo de
                        # 2 premios es puro desperdicio. El veto normal (-1) NO basta:
                        # empata por puntaje con un ataque no-KO vetado (tambien -1) y
                        # ganaba el desempate por indice (Meowth aparece antes que el
                        # ataque). Con SCORE_FORBID cae por debajo del ataque (-1) y
                        # del fin de turno (SCORE_NEVER=-10000), asi que NUNCA se elige
                        # sobre atacar o terminar. UNICA excepcion preservada: el
                        # rescate anti-softlock con banca VACIA (bench_count==0 y
                        # score>0, unico caso legitimo de bajar Meowth con Supporter
                        # ya jugado, para no quedarnos sin Pokemon en juego). El resto
                        # -mano debil, segundo Meowth, cualquier fetch redundante- se
                        # prohibe. La condicion no depende del veto previo, asi que es
                        # robusta aun en replay de una sola observacion.
                        if (state.supporterPlayed
                                and not (bench_count == 0 and score > 0)):
                            score = SCORE_FORBID
    
                    # Estrategia vs Comfey (user, registro_005): SOLO bajar Teal
                    # Mask Ogerpon ex, MAXIMO 2 en juego, y nada mas. Es el mejor
                    # atacante del matchup (facil de cargar y de retirar cuando lo
                    # confunde Brambleghast). EXCEPCION de ARRANQUE: si no tenemos
                    # ningun Ogerpon ex en juego NI en la mano y aun no hay ningun
                    # cuerpo en juego (banca+activo vacios), bajamos un starter con
                    # prioridad Applin > Chikorita > cualquiera para poder partir.
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
                            # RELEVO ANTI-BENCH-OUT (autopsia comfey jul 2026):
                            # con la BANCA VACIA -- aunque el activo siga vivo,
                            # que es justo lo que `_cf_has_body` no distinguia --
                            # bajar un Basico no es "avanzar el plan", es no
                            # perder la partida en el acto: si noquean al activo
                            # y no hay relevo, es bench-out y se acabo. Y a
                            # diferencia de todo lo demas que este plan restringe,
                            # bajar un cuerpo de la MANO no adelgaza el mazo ni
                            # una carta, que es lo unico que la defensa anti-mill
                            # tiene que proteger; "vs Comfey solo se baja Teal
                            # Mask Ogerpon ex" dice con QUE atacamos, no obliga a
                            # quedarse sin cuerpos. Medido (n=250): el bench-out
                            # es el 82% de nuestras derrotas vs comfey (14 de 17;
                            # 5.6% de las partidas frente al 0.4-2% del resto de
                            # matchups), con mediana en el turno 5. En el menu
                            # capturado, con CERO Pokemon en banca, el PLAY del
                            # Fezandipiti ex valia 22000 y esta rama lo aplastaba
                            # a -1. Solo BASICOS: una Fase 1/2 no se banquea.
                            _cf_data = card_table.get(card.id)
                            _cf_es_basico = (
                                _cf_data is not None
                                and not getattr(_cf_data, 'stage1', False)
                                and not getattr(_cf_data, 'stage2', False))
                            _cf_relevo_urgente = (bench_count == 0
                                                  and _cf_es_basico)
                            if _cf_need_starter or _cf_relevo_urgente:
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
                        # Refactor Prioridad 1: rama extraida a `_score_forest_of_vitality_play`.
                        score = _score_forest_of_vitality_play(ctx)
                    elif card.id == Bug_Catching_Set:
                        # Refactor Prioridad 1: rama extraida a `_score_bug_catching_set_play`.
                        score = _score_bug_catching_set_play(ctx)
                    elif card.id == Ultra_Ball:
                        # Refactor Prioridad 1 (Paso 1): rama extraida a `_score_ultra_ball_play`.
                        score = _score_ultra_ball_play(ctx)
                    elif card.id == Night_Stretcher:
                        # Refactor Prioridad 1: rama extraida a `_score_night_stretcher_play`.
                        score = _score_night_stretcher_play(ctx)
                    elif card.id == Poke_Pad:
                        # Refactor Prioridad 1: rama extraida a `_score_poke_pad_play`.
                        score = _score_poke_pad_play(ctx)
                    elif card.id == Unfair_Stamp:
                        # Refactor Prioridad 1: rama extraida a `_score_unfair_stamp_play`.
                        score = _score_unfair_stamp_play(ctx)
                    elif card.id == Boss_Orders:
                        # Refactor Prioridad 1: rama extraida a `_score_boss_orders_play`.
                        score = _score_boss_orders_play(ctx)
                    elif card.id == Xerosic_Machinations:
                        # Xerosic's Machinations (user): disrupcion de mano rival,
                        # clave vs Alakazam (Powerful Hand = 20 x carta en su mano).
                        score = _score_xerosic_play(ctx)
                    elif card.id == Lillie_Determination:
                        # Refactor Prioridad 1: rama extraida a `_score_lillie_determination_play`.
                        score = _score_lillie_determination_play(ctx)
                    elif card.id == Dawn:
                        # Rama extraida a `_score_dawn_play` (la comparte el
                        # predictor `_supp_play_score`).
                        score = _score_dawn_play(ctx)
                    elif card.id == Lanas_Aid:
                        # Refactor Prioridad 1: rama extraida a `_score_lanas_aid_play`.
                        score = _score_lanas_aid_play(ctx, score)
    
                    # Estrategia vs Comfey (user, registro_005): las UNICAS cartas de
                    # ENTRENADOR que se juegan son Lillie's Determination, Lana's Aid
                    # y Boss's Orders (supporters), mas Ultra Ball y Night Stretcher
                    # (items del plan, Regla 5). El resto -Dawn, Unfair Stamp, otros
                    # items y estadios- NO se juegan: se descartan/ignoran (-1). Las
                    # reglas propias de Lillie's (mano>=10) y Lana's (>=2 energias) ya
                    # se aplicaron arriba; aqui solo se veta lo que NO esta en la lista.
                    # Bug Catching Set ENTRA en la lista (autopsia comfey jul
                    # 2026): en 178/186 turnos esteriles tardios teniamos 0
                    # Plantas en MANO (Hammer/Fan nos secan y el veto de BCS
                    # cortaba el surtidor) -> sin Planta no hay adjunte NI Teal
                    # Dance y Myriad nunca llega a 3 energias: perdiamos por
                    # premios SIN COBRAR NI UNO en partidas de 40+ turnos. BCS
                    # trae hasta 2 Plantas/Pokemon {G} del top-7; el coste de
                    # adelgazar el mazo 2 cartas es menor que no atacar nunca.
                    #
                    # EXCEPCION: EL CONTRA-ESTADIO NO SE VETA NUNCA (user, log
                    # 88359220 pasos 60-76, PERDIDA -- registro_008). El rival
                    # bajo NEUTRALIZATION ZONE, que impide a nuestros Pokemon ex
                    # atacar a Pokemon que NO son ex -- y su tablero entero son
                    # no-ex (Comfey/Yveltal/Shaymin). Con eso, TODOS nuestros
                    # atacantes ex quedan apagados... incluido el Teal Mask
                    # Ogerpon ex que ES el plan del matchup. Teniamos DOS Forest
                    # of Vitality en la mano y el scorer les daba 28000 (la
                    # urgencia estaba bien detectada), pero esta allowlist las
                    # bajaba a -1 por no estar en la lista: el turno entero se
                    # jugo bajo el candado y el estadio rival siguio en mesa.
                    # La regla general -- deck-agnostica -- es que una whitelist
                    # de matchup describe QUE cartas hacen avanzar el plan, y no
                    # puede vetar la carta que LEVANTA UN CANDADO RIVAL que
                    # desactiva ese mismo plan: sin quitar el estadio no hay
                    # plan que ejecutar. Mismo criterio que ya usaba el veto de
                    # estadio de primer turno (`_replace_opp_stadium_ok`) y que
                    # el scorer de DESCARTE, que protege justo esta carta con
                    # `_forest_counters_op_stadium` -- se estaba conservando en
                    # la mano una carta que luego era ilegal jugar.
                    # Gate de self-play vs deck/rivales/comfey_yveltal_nz.csv
                    # (el mazo de ESTA partida, cosechado con
                    # utils/cosechar_deck_rival.py; ningun rival del repo
                    # llevaba la Zone y por eso el gate no cubria el caso):
                    # 94.2% con el arreglo vs 74.2% sin el, 8000 partidas por
                    # rama. +20 puntos.
                    _quita_candado_rival = (
                        data.cardType == CardType.STADIUM
                        and _contra_estadio_urgente(
                            neutralization_zone_active, watchtower_in_play,
                            ESTADO.forest_in_play, _festival_lead_hostil))
                    if (op_is_comfey_deck and score > 0
                            and not _quita_candado_rival
                            and card.id not in (
                                Lillie_Determination, Lanas_Aid, Boss_Orders,
                                Ultra_Ball, Night_Stretcher, Bug_Catching_Set)):
                        score = SCORE_VETO
    
                # =========================================================
                # GRAND TREE (id 1249) en la MANO -- solo se activa si el mazo
                # cargado lo lleva; con deck.csv actual es codigo inerte, pero
                # la peticion es que la logica sirva "para cualquier tipo de
                # mazo".
                # =========================================================
                if card.id == Grand_Tree:
                    if state.stadiumPlayed or stadium_id == Grand_Tree:
                        score = SCORE_VETO
                    elif _our_first_turn:
                        # No podemos evolucionar Basicos en nuestro primer
                        # turno: bajarlo ahora solo se lo REGALA al rival, que
                        # si podra usarlo en el suyo.
                        score = SCORE_VETO
                    elif _gt_planes(my_state, ESTADO.CARTAS_ACTIVAS_EN_MAZO,
                                    field_counts, _our_first_turn,
                                    veta_etapa_ex=_gt_veta_etapa_ex):
                        # Hay una cadena que se cobra EN ESTE MISMO TURNO: el
                        # estadio se paga solo. Por encima del Forest (que
                        # como maximo vale 29000) porque produce cuerpo nuevo.
                        score = 30000
                    elif _gt_raiz_en_juego:
                        # La raiz esta en juego pero salio hoy: la cadena se
                        # cobra el turno que viene. Sigue mereciendo la pena
                        # bajarlo ya (y de paso quita el estadio rival).
                        score = 20000 if stadium_id != 0 else 12000
                    else:
                        # Sin raiz no hay nada que evolucionar: se conserva.
                        # Solo se juega para BORRAR un estadio rival molesto.
                        score = (14000 if _contra_estadio_urgente(
                            neutralization_zone_active, watchtower_in_play,
                            ESTADO.forest_in_play, _festival_lead_hostil) else SCORE_VETO)
    
                # Bajar el BASICO que sirve de raiz a Grand Tree (regla del
                # user: conseguirlo "para asi luego jugar el estadio"). Bono
                # aditivo y pequeno -- desempata contra otros cuerpos de
                # desarrollo sin pisar los motores ya existentes -- y solo
                # cuando no hay ya una raiz en juego.
                elif (_gt_quiere_basico and score > 0
                        and card.id in _gt_ranking_basicos
                        and data is not None
                        and data.cardType == CardType.POKEMON):
                    score += GT_PLAY_BASICO_BONUS
    
                # FASE E2 del plan de Marnie ("preferir relleno sin habilidad"):
                # MEDIDA E INERTE, no se implementa. Un bono de desempate de 500
                # a los cuerpos que no pagan el peaje de Freezing Shroud cambio
                # CERO decisiones -- en los 929 pasos de los registros y en los
                # sondeos sinteticos -- porque entre nuestros Basicos no hay
                # ninguna pareja que compita de verdad en la banda de desarrollo:
                # Meowth ex y Fezandipiti ex los deciden sus propios motores (por
                # encima de 21000, y ambos YA gateados por `op_has_froslass`), y
                # el unico rival real de Tapu Bulu es un 2o Teal Mask Ogerpon ex,
                # que puntua muy por encima del desempate por ser el atacante del
                # plan. Ver el criterio del propio plan: "una regla que dispara 0
                # veces es INERTE y no se mide por winrate".
        elif o.type == OptionType.ATTACH:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            if card is not None and pokemon is not None:
                score = energy_score(pokemon, o.inPlayArea == AreaType.ACTIVE)
                if o.inPlayArea == AreaType.ACTIVE:
    
                    # vs Crustle, Tapu Bulu ACTIVO es nuestro atacante PRINCIPAL
                    # (no-ex; el unico que daña al muro inmune a ex): tiene SIEMPRE
                    # la primera prioridad de carga, desde el primer turno. El veto
                    # generico de "no cargar el activo inicial" (Ogerpon/Tapu en
                    # nuestro primer turno, pensado para no desperdiciar energia
                    # sobrecargando el atacante de arranque) NO debe degradarlo:
                    # sin carga, Tapu nunca llega a sus 4 energias para Wood Hammer
                    # (user, registro_002 paso 17 vs Crustle, PERDIDA: el agente
                    # cargaba un Applin de banca en vez del Tapu Bulu activo). Solo
                    # se exime a Tapu Bulu; Ogerpon ex sigue vetado (no daña al muro).
                    _ft_veto_ids = ((Teal_Mask_Ogerpon_ex,) if ESTADO.op_is_crustle_deck
                                    else (Teal_Mask_Ogerpon_ex, Tapu_Bulu))
                    if (((state.turn == 1 and ESTADO.we_go_first) or
                            (state.turn == 2 and not ESTADO.we_go_first))
                            and my_state.active and my_state.active[0] is not None
                            and my_state.active[0].id in _ft_veto_ids
                            # ...salvo que esa carga REMATE hoy (anti-DONK): el
                            # veto de primer turno existe para no desperdiciar
                            # energia, no para renunciar a un KO.
                            and not _carga_activo_remata):
                        if _lucario_sac_pivot:
                            # Cargar el Ogerpon ex activo: al retirarlo despues,
                            # conservara energia en la banca (paga el coste de
                            # retirada y deja un atacante cargado a salvo).
                            score = 8500
                        else:
                            score = SCORE_VETO
                    elif _tapu_sac_enable_retreat:
                        # Adjuntar energia al ex activo (2 premios) para alcanzar
                        # su coste de retirada y poder pivotar a un Tapu Bulu ya
                        # cargado que noquea al activo rival (user, log 86029588
                        # turno 16 paso 148, vs Alakazam/Dunsparce). El coste de
                        # retirada de Fezandipiti ex es 1, asi que UNA Planta ya
                        # habilita la retirada este mismo turno -> subir a Tapu y
                        # rematar. Antes se puntuaba 8000, pero un Dipplin de
                        # BANCA a 0 energia puntua 8150 (8000+150) y GANABA el
                        # desempate, desperdiciando la energia en un no-atacante y
                        # rompiendo la linea de KO. Se sube por encima de cualquier
                        # desarrollo de banca (Dipplin/Applin/Tapu no letales) para
                        # que el adjunte al activo gane; sigue por debajo de una
                        # carga LETAL de este turno (41000/42000).
                        score = 24000
                    elif _attach_enable_retreat_ko:
                        # Adjunte que habilita retirada + KO de banca (user,
                        # registro_034 paso 141 vs Terrakion): es una linea
                        # LETAL de este turno, asi que puntua en la banda de
                        # las cargas letales (41000): sobre Teal Dance
                        # (31500-31600) y las cargas de banca (~30000), bajo
                        # el remate directo del activo (42000). El resto de la
                        # cadena (RETREAT via plan con can_switch, promocion,
                        # ataque) ya la resuelve la maquinaria existente una
                        # vez la retirada es legal.
                        score = 41000
                    elif _attach_enable_retreat_attack:
                        # Misma linea sin KO (user, log 88162794 turnos 11/13 vs
                        # Archaludon ex): el activo no puede atacar ni retirarse y
                        # el atacante de banca solo hace CHIP. La Planta va al
                        # ACTIVO para pagar la retirada: 80-140 de dano valen mas
                        # que cerrar el turno sin atacar. Banda 31200 (la que citan
                        # las ramas de Teal Dance como "el adjunte manual"): por
                        # encima de cualquier carga de banca (<=31150, incluida la
                        # de Ripening al mejor atacante) y por debajo de todo lo
                        # que habilita un KO este turno (31300+, 31500, 41000).
                        score = 31200
                    elif (ESTADO.plan.attacker == 0 and ESTADO.plan.energy
                            # La banda de `_carga_activo_habilita_ataque` (31300)
                            # esta calibrada contra el motor UB (31450) y Teal
                            # Dance (31500): el bonus de desempate la cruzaria.
                            and not _carga_activo_habilita_ataque):
                        score += 200
    
                    elif (ESTADO.plan.attacker >= 1 and has_ogerpon and score > 31000
                            and not ESTADO.op_is_crustle_deck and not ESTADO.op_is_cornerstone_deck
                            and not (_win_via_boss_gust or _gust_2prize_via_boss)
                            # ...ni cuando esta carga es la que hace atacar al
                            # activo HOY (remate o unico ataque del turno).
                            and not _carga_activo_remata
                            and not _carga_activo_habilita_ataque):
                        # NO degradar el adjunte al activo si hay una jugada
                        # GANADORA / de 2 premios via Boss's que se apoya en cargar
                        # el activo (user, registro_012 paso 227 vs Iono): Myriad
                        # Leaf Shower de Ogerpon cuenta la energia de AMBOS activos,
                        # asi que cargar el activo + gustear un Bellibolt ex
                        # energizado lo noquea (2 premios). El remate ganador
                        # (energy_score=42000) debe prevalecer sobre este downgrade
                        # (pensado para no sobrecargar el activo cuando ataca un
                        # cuerpo de banca), que si no borraria la linea de KO.
    
                        _attach_active_pkmn = my_state.active[0] if my_state.active else None
                        _attach_needs_for_retreat = False
                        if _attach_active_pkmn is not None:
                            _attach_rc = RETREAT_COST.get(_attach_active_pkmn.id, 1)
                            _attach_curr_e = len(_attach_active_pkmn.energies)
                            if _attach_curr_e < _attach_rc:
                                _attach_needs_for_retreat = True
                        if not _attach_needs_for_retreat:
                            score = 7500
                else:
                    if ESTADO.plan.attacker == 1 + o.inPlayIndex and ESTADO.plan.energy:
                        score += 200
    
                    _our_first_turn_attach = ((state.turn == 1 and ESTADO.we_go_first) or
                                              (state.turn == 2 and not ESTADO.we_go_first))
                    _active_blocked_ft = (
                        my_state.active and my_state.active[0] is not None
                        and my_state.active[0].id in (Teal_Mask_Ogerpon_ex, Tapu_Bulu))
                    if _our_first_turn_attach and _active_blocked_ft and len(pokemon.energies) < 1:
                        _BENCH_ATTACKER_PRIORITY = {
                            Hydrapple_ex: 900,
                            Dipplin: 850,
                            Teal_Mask_Ogerpon_ex: 800,
                            Tapu_Bulu: 750,
                            Pinsir: 650,
                            # Priorizamos la linea de Hydrapple ex (Applin ->
                            # Dipplin -> Hydrapple ex), que acelera energia y
                            # carga a Tapu Bulu en un turno, por encima de la
                            # linea de Meganium (Chikorita).
                            Applin: 500,
                            Chikorita: 400,
                            Fezandipiti_ex: 200,
                        }
                        _bench_prio = _BENCH_ATTACKER_PRIORITY.get(pokemon.id)
                        if _bench_prio is not None:
                            score = max(score, 8000 + _bench_prio)
    
                    # Nunca cargar manualmente energia a un Meowth ex de BANCA: es un
                    # no-atacante y la energia se desperdicia. El unico uso valido de
                    # Meowth ex para el adjunte manual es en el ACTIVO, para pagar su
                    # retirada cuando haga falta (lo gestiona la rama AreaType.ACTIVE
                    # via energy_score). Se veta SIEMPRE, sin importar el turno ni si
                    # es el unico objetivo de banca disponible.
                    if pokemon.id == Meowth_ex:
                        score = SCORE_VETO
    
                if _bcs_playable_in_hand and not itchy_pollen_active and score > 9000 \
                        and not (_tapu_future_charge
                                 and o.inPlayArea != AreaType.ACTIVE
                                 and pokemon is not None
                                 and pokemon.id == Tapu_Bulu) \
                        and not (_carga_activo_remata
                                 and o.inPlayArea == AreaType.ACTIVE):
                    # Bug Catching Set primero... salvo que la carga al ACTIVO
                    # remate este turno: el KO no espera a una busqueda.
                    score = 9000
    
                if _teal_dance_ko_pivot and hand_counts.get(Basic_Grass_Energy, 0) <= 1:
                    # Pivote Teal Dance (log 85802744 turno 16): con una
                    # sola Energia Planta en mano, RESERVARLA para Teal Dance en
                    # el activo (adjunta + ROBA y habilita la retirada de coste 1
                    # para subir al atacante no-ex que noquea al muro Crustle). Se
                    # veta cualquier adjunte manual para que no robe la Planta ni
                    # supere a Teal Dance por el tier ENERGY del orden de jugada.
                    score = SCORE_VETO
    
                # Teal Dance PRECEDE al adjunte manual (user, registro_004 paso
                # 28, vs Mega Starmie): si vamos a cargar energia MANUALMENTE a
                # un Teal Mask Ogerpon ex que TODAVIA puede usar Teal Dance este
                # turno (su opcion ABILITY sigue disponible en este mismo slot),
                # se veta el adjunte manual. Teal Dance adjunta la Planta Y ROBA
                # una carta, asi que se juega PRIMERO; tras usarla la habilidad
                # desaparece y, si aun se quiere una 2a energia, el adjunte
                # manual se puntua con normalidad en el paso siguiente. Esto
                # corrige el orden impuesto por el tier ENERGY (que hacia ganar
                # al adjunte manual pese a que Teal Dance puntua mas alto).
                if (score > 0
                        and pokemon is not None
                        and pokemon.id == Teal_Mask_Ogerpon_ex
                        and (o.inPlayArea, o.inPlayIndex) in _teal_dance_slots):
                    score = SCORE_VETO
    
                # GENERALIZACION de la precedencia anterior (user, registro_002
                # paso 20, vs Marnie): Teal Dance no solo precede al adjunte
                # sobre el PROPIO Ogerpon. Mientras quede una Teal Dance por
                # usar este turno, un adjunte manual que sea mero DESARROLLO
                # (el objetivo NO queda listo para atacar con esa energia) cede
                # ante ella. Teal Dance gasta la misma Planta de la mano, pero
                # ademas ROBA una carta y NO consume el adjunte manual del
                # turno: es estrictamente mejor que gastar el adjunte en un
                # cuerpo que no va a atacar.
                #
                # En el registro, el Ogerpon ex ACTIVO ya habia usado su Teal
                # Dance ese turno, asi que el adjunte al activo quedaba vetado
                # por la regla de primer turno y la Teal Dance del Ogerpon ex de
                # BANCA caia a la banda degradada (7500); el unico objetivo que
                # quedaba, un Chikorita de banca, ganaba con 8400 (base 8000 de
                # energy_score + boost de desarrollo) y desperdiciaba la unica
                # Planta en un cuerpo que con 1 energia no es atacante.
                #
                # Se CAPA (no se veta) por debajo de la banda degradada de Teal
                # Dance (7500) en vez de anular la jugada: si la habilidad
                # estuviera vetada por otra via, el adjunte sigue siendo jugable
                # y no se cuelga el turno. "Listo para atacar" exige ATACANTE
                # REAL (MAIN_ATTACKERS): Chikorita/Applin/Bayleef figuran en
                # ATTACK_ENERGY_REQ por su ataque de chip, pero no son atacantes.
                #
                # No basta con capar el score: el ORDEN DE JUGADA manda por
                # tier y el adjunte manual vive en _TIER_ENERGY, mientras que
                # una Teal Dance degradada (7500) se queda en tier 0 (su
                # promocion exige >= 29000, guard que NO se toca: evita que una
                # Teal Dance degradada aplaste por tier a Ripening Charge). Por
                # eso el indice se marca aqui y mas abajo se deja el adjunte en
                # tier 0, para que dentro del mismo tier decida el score
                # (Teal Dance 7500 > adjunte capado 7000).
                # Solo la BANDA DE DESARROLLO (< 9000: la base 8000 de
                # energy_score y el boost de banca del primer turno, max 8900).
                # Los adjuntes con override estrategico puntuan muy por encima
                # (8500 sacrificio Lucario, 24000 pivote Tapu, 31000+ cargas,
                # 41000 el que habilita retirada hacia un KO de banca) y NO son
                # desarrollo: ceder ahi romperia lineas letales de este turno.
                if (pokemon is not None and _teal_dance_slots
                        and 0 < score < 9000
                        and not (pokemon.id in MAIN_ATTACKERS
                                 and _can_attack_eff(
                                     pokemon.id,
                                     len(pokemon.energies)
                                     + _grass_attach_unit()))):
                    score = min(score, 7000)
                    _attach_cede_a_teal_dance.add(len(scores))
    
        elif o.type == OptionType.EVOLVE:
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            # La carta de evolucion normalmente viene de la MANO, pero la
            # habilidad de Grand Tree la saca del MAZO. Se respeta `o.area`
            # cuando el simulador la informa (para el juego normal vale HAND,
            # asi que el comportamiento no cambia) en vez de asumir la mano.
            _evo_area = o.area if o.area is not None else AreaType.HAND
            card = get_card(obs, _evo_area, o.index, my_index)
            if (card is not None and select.effect is not None
                    and select.effect.id == Grand_Tree):
                # Evolucion servida por Grand Tree: la decide el plan del
                # estadio, no las bandas de la evolucion desde la mano (que
                # asumen que se gasta una carta de la mano y que el cuerpo ya
                # estaba elegido).
                _gt_evo_score = _gt_score_seleccion(
                    o, card, _gt_plan, _gt_planes_turno, my_state, field_counts)
                if pokemon is not None and _gt_plan is not None:
                    # Desempate por el Basico elegido: la opcion apunta a la
                    # vez a la carta y al cuerpo, asi que el objetivo del plan
                    # tiene que ganar.
                    if getattr(pokemon, 'serial', None) == _gt_plan.serial:
                        _gt_evo_score += 5000
                scores.append(_gt_evo_score)
                return _SALTAR   # ya hizo scores.append por su cuenta
            if card is not None and pokemon is not None:
                _is_active = (o.inPlayArea == AreaType.ACTIVE)
                _pkmn_energy = len(pokemon.energies)
                _has_energy_in_hand = (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and not state.energyAttached)
    
                score = 9000 + _pkmn_energy
    
                if card.id == Meganium:
                    score = 35000
                    # vs Cornerstone Mask Ogerpon ex (user, registro_004 turno 4):
                    # su Cornerstone Stance anula el dano de TODOS nuestros Pokemon
                    # CON habilidad (Teal Mask Ogerpon ex, Hydrapple ex, Dipplin...),
                    # asi que el unico atacante real es Tapu Bulu (Bayleef solo hace
                    # chip). Meganium no dana a Cornerstone -- tambien tiene
                    # habilidad -- pero su Wild Growth DUPLICA cada Planta, y con el
                    # en juego Tapu Bulu ataca con 2 Plantas FISICAS en vez de 4.
                    # Montar la linea es por tanto prioritario en este matchup.
                    if (op_is_fire_deck or op_is_mirror or ESTADO.op_is_crustle_deck
                            or op_has_ability_immune_active
                            or ESTADO.op_is_cornerstone_deck):
                        score = 35500
    
                    if pokemon.id == Chikorita:
                        score += 500
    
                elif card.id == Hydrapple_ex:
                    score = 33000
    
                    if ESTADO.op_is_crustle_deck and op_kang_ko_target:
    
                        score = 34500
                    elif ESTADO.op_is_crustle_deck and op_active_is_kangaskhan:
    
                        score = 33000
                    elif ESTADO.op_is_crustle_deck:
                        score = SCORE_VETO
                    elif op_is_fire_deck:
                        score = 33500
    
                    elif op_is_drednaw_deck:
                        _other_dipplin_count = field_counts.get(Dipplin, 0)
                        _has_hydrapple_already = field_counts.get(Hydrapple_ex, 0) >= 1
                        if _has_hydrapple_already:
    
                            score = 22000
                        elif _other_dipplin_count >= 2:
    
                            score = 32500
                        elif _other_dipplin_count >= 1 and not _is_active:
    
                            score = 32000
                        else:
    
                            score = 22000
    
                    elif op_is_sylveon_deck and op_has_ex_immune_active:
                        _other_dipplin_count = field_counts.get(Dipplin, 0)
                        _has_hydrapple_already = field_counts.get(Hydrapple_ex, 0) >= 1
    
                        _tapu_ready_sv = any(
                            bp is not None and bp.id == Tapu_Bulu and
                            len(bp.energies) * _grass_mult() >= 4
                            for bp in list(my_state.active or []) + list(my_state.bench))
                        if _tapu_ready_sv:
                            score = 32500
                        elif _has_hydrapple_already:
                            score = 22000
                        elif _other_dipplin_count >= 2:
                            score = 32500
                        elif _other_dipplin_count >= 1 and not _is_active:
                            score = 32000
                        else:
                            score = 22000
    
                    if pokemon.id == Applin and not ESTADO.op_is_crustle_deck:
                        score += 500
    
                    # ── Regla: no malgastar un KO letal de Dipplin ──────────
                    # Si el activo es un Dipplin al que, cargandole 1 energia
                    # Grass este turno, "Do the Wave" (20 x banca) noquearia al
                    # Pokemon activo rival, PERO al evolucionar a Hydrapple ex NO
                    # podriamos noquear este turno (Syrup Storm exige 2 energias),
                    # NO evolucionamos: conservamos el Dipplin para atacar y
                    # llevarnos el KO. Reglas del usuario:
                    #   (1) Dipplin noquea y Hydrapple no -> NO evolucionar.
                    #   (2) Dipplin no noquea -> evolucionar con normalidad.
                    #   (3) sin energia disponible -> evolucionar (protege Dipplin).
                    if _is_active and pokemon.id == Dipplin:
                        _dip_can_attack_now = (_pkmn_energy >= 1 or _has_energy_in_hand)
                        if _dip_can_attack_now:
                            _op_act_evo = (op_state.active[0]
                                           if op_state.active and op_state.active[0] is not None
                                           else None)
                            if _op_act_evo is not None and (_op_act_evo.hp or 0) > 0:
                                _dip_dmg = _our_effective_damage(
                                    pokemon, _op_act_evo, 20 * bench_count,
                                    ESTADO.meganium_in_play, neutralization_zone_active)
                                _dip_kos = (_dip_dmg > 0 and _dip_dmg >= (_op_act_evo.hp or 0))
                                # Energia efectiva de Hydrapple ex tras evolucionar
                                # (hereda la energia del Dipplin + posible adjunto).
                                _hydra_eff = _pkmn_energy * _grass_mult()
                                if _has_energy_in_hand:
                                    _hydra_eff += _grass_attach_unit()
                                _hydra_kos = False
                                if _hydra_eff >= ESTADO.ATTACK_ENERGY_REQ[Hydrapple_ex]:
                                    _hydra_grass = total_grass + (1 if _has_energy_in_hand else 0)
                                    _hydra_dmg = _our_effective_damage(
                                        pokemon, _op_act_evo, 30 + 30 * _hydra_grass,
                                        ESTADO.meganium_in_play, neutralization_zone_active)
                                    _hydra_kos = (_hydra_dmg > 0 and _hydra_dmg >= (_op_act_evo.hp or 0))
                                if _dip_kos and not _hydra_kos:
                                    score = SCORE_VETO
    
                elif card.id == Bayleef:
    
                    if _is_active:
                        if has_condition and condition_blocks_action:
    
                            score = 34000 + condition_urgency
                        elif not can_switch:
    
                            score = 31300
                        else:
                            # Activo evolucionable (p.ej. Chikorita) que SI puede
                            # cambiar de activo. Por defecto NO se evoluciona en el
                            # activo (dejaria un Bayleef fragil arriba). Dos
                            # escenarios ajustan este veto:
                            _evo_active_rc = RETREAT_COST.get(pokemon.id, 1)
                            _evo_active_eff = _pkmn_energy * _grass_mult()
                            _evo_can_attach_now = (
                                hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                                not state.energyAttached)
                            _evo_eff_after_attach = _evo_active_eff + (
                                _grass_attach_unit() if _evo_can_attach_now else 0)
                            if _evo_active_eff >= _evo_active_rc:
                                # Escenario 1: ya tiene energia cargada para pagar
                                # la retirada -> conviene RETIRARLO primero y
                                # evolucionarlo ya en la banca. Se mantiene el veto;
                                # la logica de retiro sube un atacante de banca y el
                                # Chikorita evoluciona despues desde la banca.
                                score = SCORE_VETO
                            elif (hand_counts.get(Lillie_Determination, 0) >= 1
                                    and not state.supporterPlayed):
                                # Escenario 2: no puede pagar la retirada con su
                                # energia actual, pero tenemos Lillie's Determination
                                # en mano y podremos cargar energia despues de
                                # jugarla -> evolucionamos el activo a Bayleef ahora.
                                score = 31300
                            elif _evo_eff_after_attach >= _evo_active_rc:
                                # Escenario 1 (variante): se le puede cargar energia
                                # este turno para pagar la retirada -> retirar primero
                                # y evolucionar en banca. Se mantiene el veto.
                                score = SCORE_VETO
                            else:
                                score = SCORE_VETO
                    else:
                        score = 32000
                        if op_is_fire_deck or op_is_mirror or ESTADO.op_is_crustle_deck:
                            score = 32500
                        if op_is_cubchoo_deck:
                            # Cambio 4 (user): la linea de Meganium es la PRIORIDAD
                            # principal de evolucion vs Cubchoo, por delante de la
                            # linea de Hydrapple ex (Dipplin->Hydrapple = 33000).
                            # Meganium final ya vale 35000 (> este 34000).
                            score = 34000
    
                elif card.id == Dipplin:
    
                    if _pkmn_energy >= 1 or _has_energy_in_hand:
                        score = 31500
                        if op_has_ex_immune_active or op_has_ex_immune_bench:
                            if not has_hydrapple:
                                score = 32000
    
                        if op_is_drednaw_deck:
                            score = 33000
    
                        elif op_is_sylveon_deck:
                            score = 32500
                    else:
    
                        score = 25000
                        if op_is_drednaw_deck:
                            score = 31000
                        elif op_is_sylveon_deck:
                            score = 30500
    
                if _is_active and active_ko_likely and score > 0 and card.id != Meganium:
                    _evo_effective_energy = _pkmn_energy * _grass_mult()
                    if _has_energy_in_hand:
                        _evo_effective_energy += _grass_attach_unit()
                    _evo_can_attack = False
                    if card.id == Hydrapple_ex:
                        _evo_can_attack = (_evo_effective_energy >= 2)
                    elif card.id == Dipplin:
                        _evo_can_attack = (_pkmn_energy >= 1 or _has_energy_in_hand)
                    elif card.id == Bayleef:
                        _evo_can_attack = False
    
                    if not _evo_can_attack and not (has_condition and _is_active):
                        score = 8000
    
                    elif _evo_can_attack and card.id != Hydrapple_ex:
    
                        _evo_data = card_table.get(card.id)
                        _evo_max_hp = _evo_data.hp if (_evo_data and hasattr(_evo_data, 'hp')) else 0
    
                        _current_damage = pokemon.maxHp - pokemon.hp if hasattr(pokemon, 'maxHp') else 0
                        _evo_hp_after = _evo_max_hp - max(0, _current_damage)
    
                        _evo_op_damage = estimated_op_damage
                        if _evo_data:
                            _op_act = _active_of(op_state)
                            if _op_act is not None:
                                _op_act_data = card_table.get(_op_act.id)
                                if (_op_act_data and hasattr(_evo_data, 'weakness') and
                                        hasattr(_op_act_data, 'energyType') and
                                        _evo_data.weakness == _op_act_data.energyType):
    
                                    _base_op_dmg = 0
                                    if _op_act_data.attacks:
                                        for _atk in _op_act_data.attacks:
                                            if hasattr(_atk, 'damage') and _atk.damage is not None:
                                                _base_op_dmg = max(_base_op_dmg, _atk.damage)
                                    _evo_op_damage = _base_op_dmg * 2
                                elif (hasattr(_evo_data, 'weakness') and
                                      hasattr(_op_act_data, 'energyType') and
                                      _evo_data.weakness != _op_act_data.energyType):
    
                                    _base_op_dmg = 0
                                    if _op_act_data.attacks:
                                        for _atk in _op_act_data.attacks:
                                            if hasattr(_atk, 'damage') and _atk.damage is not None:
                                                _base_op_dmg = max(_base_op_dmg, _atk.damage)
                                    _evo_op_damage = _base_op_dmg
    
                        _evo_survives = (_evo_hp_after > _evo_op_damage)
    
                        if not _evo_survives:
    
                            _bench_has_same_preevo = False
                            for _bp in my_state.bench:
                                if _bp is not None and _bp.id == pokemon.id:
                                    _bench_has_same_preevo = True
                                    break
    
                            if _bench_has_same_preevo and not (has_condition and _is_active):
    
                                score = 8000
    
                # ANTI-CUBCHOO: NO evolucionar a un cuerpo LENTO que no llega a
                # su ataque (user, registro_034 paso 131 vs Cubchoo, PERDIDA).
                # Ese mazo bloquea y descarta energia, asi que un Pokemon con
                # coste de retirada ALTO (Hydrapple ex: 3) que ademas NO alcanza
                # su requisito de ataque queda CLAVADO: ni ataca ni se retira, y
                # regala un cuerpo de 2 premios plantado en el activo. En aquel
                # turno el Dipplin activo tenia 0 energias y aun asi se
                # evoluciono a Hydrapple ex (33000), quedando inutil el resto de
                # la partida.
                #
                # El gate es el COSTE DE RETIRADA (>= 3), que es la razon real:
                # en nuestro mazo solo lo cumple Hydrapple ex (Meganium/Bayleef/
                # Dipplin cuestan 2), pero asi cubre cualquier evolucion futura
                # igual de lenta. Va al FINAL de la rama para tener la ultima
                # palabra sobre las subidas de score de arriba.
                #
                # SOLO vs Cubchoo (`op_is_cubchoo_deck`): en el resto de
                # matchups la evolucion es desarrollo normal -- se recarga y se
                # retira sin problema, y el muro de 330 PV compensa.
                if (op_is_cubchoo_deck and score > 0
                        and RETREAT_COST.get(card.id, 1) >= 3):
                    # Energia con la que contaria el cuerpo YA evolucionado: la
                    # que hereda de la pre-evolucion mas el adjunte manual si
                    # sigue disponible este turno.
                    _cub_evo_eff = _pkmn_energy
                    if _has_energy_in_hand:
                        _cub_evo_eff += _grass_attach_unit()
                    if _cub_evo_eff < ESTADO.ATTACK_ENERGY_REQ.get(card.id, 99):
                        score = SCORE_VETO
    
                if has_condition and _is_active and score > 0:
                    score += condition_urgency
    
        elif o.type == OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            if card is not None:
                if card.id == Grand_Tree:
                    # HABILIDAD DE GRAND TREE (estadio compartido, id 1249):
                    # cadena Basico -> Fase 1 -> Fase 2 sacada del mazo, gratis
                    # y una vez por turno. `_gt_plan` ya trae el mejor objetivo
                    # (ver el bloque `_gt_*`); aqui solo se decide CUANTO vale
                    # la jugada. Si no hay plan ejecutable -- primer turno,
                    # ningun Basico elegible, cadena agotada en el mazo -- se
                    # veta: activarla sin objetivo solo baraja el mazo.
                    if _gt_plan is None:
                        score = SCORE_VETO
                    elif _gt_plan.stage2_id:
                        score = GT_SCORE_CADENA_COMPLETA
                    else:
                        # Cadena que se detiene en Fase 1 (Fase 2 agotada o
                        # desaconsejada por el matchup anti-ex). Sigue siendo
                        # desarrollo gratis, pero por debajo de la cadena
                        # completa y de la evolucion a Meganium desde la mano.
                        score = GT_SCORE_SOLO_FASE1
                elif card.id == Teal_Mask_Ogerpon_ex:
    
                    _ogerpon_energy = len(card.energies) if isinstance(card, Pokemon) else 0
    
                    _crustle_atk_needs_grass = False
                    if ESTADO.op_is_crustle_deck and hand_counts.get(Basic_Grass_Energy, 0) == 1:
                        for _cng in (list(my_state.active or []) + list(my_state.bench or [])):
                            if _cng is None:
                                continue
                            _cng_e = len(_cng.energies)
                            if ((_cng.id == Tapu_Bulu and _cng_e < 4) or
                                    (_cng.id == Dipplin and _cng_e < 1) or
                                    (_cng.id == Pinsir and _cng_e < 2)):
                                _crustle_atk_needs_grass = True
                                break
    
                    _td_ko_on_active = False
                    if (o.area == AreaType.ACTIVE
                            and op_state.active and op_state.active[0] is not None
                            and not op_has_ex_immune_active
                            and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
                        _td_op_act = op_state.active[0]
                        _td_op_hp = _td_op_act.hp or 0
                        _td_eff_now = _ogerpon_energy
                        _td_eff_after = _ogerpon_energy + _grass_attach_unit()
                        # Myriad Leaf Shower = 30 + 30 por CADA energia unida a
                        # AMBOS activos (la propia MAS la del activo rival); de ahi
                        # el `_td_eff_now + _td_opp_e` de abajo. (El comentario
                        # anterior decia "solo energia propia": era un error ya
                        # corregido en `_attacker_base_damage`, el codigo siempre
                        # sumo las dos.) Se pasa por _our_effective_damage para
                        # aplicar debilidad Y RESISTENCIA (user, registro_012 paso
                        # 93: Duraludon resiste -30 a Planta, asi que Teal Dance
                        # habilita el KO al pasar de 4 a >=5 energias efectivas).
                        # `card` es el propio Teal Mask Ogerpon ex.
                        _td_opp_e = len(getattr(_td_op_act, 'energies', []) or [])
                        _td_base_now = (30 + 30 * (_td_eff_now + _td_opp_e)
                                        if _td_eff_now >= 3 else 0)
                        _td_base_after = (30 + 30 * (_td_eff_after + _td_opp_e)
                                          if _td_eff_after >= 3 else 0)
                        _td_dmg_now = _our_effective_damage(
                            card, _td_op_act, _td_base_now,
                            ESTADO.meganium_in_play, neutralization_zone_active)
                        _td_dmg_after = _our_effective_damage(
                            card, _td_op_act, _td_base_after,
                            ESTADO.meganium_in_play, neutralization_zone_active)
                        _td_ko_now = (_td_dmg_now > 0 and _td_dmg_now >= _td_op_hp)
                        _td_ko_after = (_td_dmg_after > 0 and _td_dmg_after >= _td_op_hp)
                        _td_ko_on_active = (_td_ko_after and not _td_ko_now)
                    # Teal Dance del Ogerpon FOCO de carga letal (bench o activo):
                    # se usa para acercarlo a las 3 energias del KO por debilidad
                    # (user, registro_006 paso 62). A diferencia de `_td_ko_on_active`
                    # (solo el ACTIVO), esto cubre un Ogerpon de BANCA que luego se
                    # promueve. Exige que aun no llegue a 3 (no sobrecargar).
                    _td_is_lethal_focus = (
                        _ogerpon_lethal_focus_serial is not None
                        and isinstance(card, Pokemon)
                        and getattr(card, 'serial', None) == _ogerpon_lethal_focus_serial
                        and _ogerpon_energy < 3)
                    if hand_counts[Basic_Grass_Energy] < 1:
                        score = SCORE_VETO
                    elif _carga_activo_remata and o.area == AreaType.ACTIVE:
                        # El ACTIVO que llega a su ataque LETAL con esta carga es
                        # este mismo Ogerpon: su Teal Dance adjunta la Planta Y
                        # ROBA, asi que hereda la banda del remate.
                        score = SCORE_CARGA_ACTIVO_REMATE
                    elif _carga_activo_habilita_ataque and o.area == AreaType.ACTIVE:
                        # Espejo sin KO: la Planta deja atacar al Ogerpon activo
                        # (y roba) en un turno que si no seria esteril.
                        score = SCORE_CARGA_ACTIVO_ATAQUE
                    elif ((_carga_activo_remata or _carga_activo_habilita_ataque)
                            and o.area != AreaType.ACTIVE
                            and hand_counts[Basic_Grass_Energy]
                                <= _carga_activo_falta):
                        # Teal Dance solo se adjunta a SI MISMA: en un Ogerpon de
                        # BANCA se comeria la Planta que el ACTIVO necesita para
                        # rematar hoy. Se veta mientras la mano no de para ambos
                        # (user, registro_006 paso 67 vs Marnie's Grimmsnarl).
                        score = SCORE_VETO
                    elif ((_attach_enable_retreat_ko
                           or _ability_unlock_retreat_ko)
                            and o.area == AreaType.ACTIVE):
                        # TEAL DANCE que habilita la retirada hacia un atacante de
                        # banca LETAL (user, registro_036 paso 146 vs Cubchoo).
                        # `_attach_enable_retreat_ko` ya detecta la linea completa
                        # -- activo sin energia para retirarse + atacante de banca
                        # que NOQUEA -- y le da 41000 al adjunte MANUAL sobre el
                        # activo. Pero si ese activo es un Teal Mask Ogerpon ex con
                        # Teal Dance viva, el adjunte manual se veta por la
                        # precedencia "Teal Dance antes que el adjunte" y la linea
                        # se perdia entera: el agente acababa cargando un cuerpo de
                        # banca cualquiera (alli, un Tapu Bulu a 10 PV) y el KO no
                        # ocurria.
                        #
                        # La precedencia es correcta -- Teal Dance adjunta la misma
                        # Planta Y ADEMAS ROBA --, lo que faltaba era que la propia
                        # Teal Dance heredase la prioridad de esa linea letal. Va
                        # ANTES de los topes de energia por matchup (Cubchoo,
                        # Alakazam/Hop's, Crustle): esto no es sobrecargar, es la
                        # unica forma de pagar el coste de retirada.
                        #
                        # `_teal_dance_ko_pivot`/`_teal_wall_pivot` (31600) cubren
                        # solo el caso del MURO inmune con un atacante NO-ex; aqui
                        # el activo rival es atacable y el letal de banca es otro
                        # ex, asi que ninguno de los dos disparaba.
                        score = 41000
                    elif ((_attach_enable_retreat_attack
                           or _ability_unlock_retreat_attack)
                            and o.area == AreaType.ACTIVE):
                        # Espejo no-letal del caso anterior (log 88162794 turnos
                        # 11/13): si el activo que necesita la energia para
                        # retirarse es este Ogerpon, su propia Teal Dance paga el
                        # coste Y ROBA, asi que hereda la prioridad del pivote --
                        # justo por encima del adjunte manual (31200) para no
                        # perder el robo, y por debajo de las lineas de KO (31500).
                        score = 31250
                    elif _td_ko_on_active or _td_is_lethal_focus:
    
                        score = 31500
                    elif _grass_anywhere_enables_syrup_ko:
                        # Teal Dance como ACELERADOR del Syrup Storm del
                        # Hydrapple ex ACTIVO (user, registro_006 paso 68 vs Mega
                        # Abomasnow ex, PERDIDA): la Planta suma al recuento de
                        # TODOS nuestros Pokemon, asi que este Ogerpon no
                        # necesita ganar nada con ella -- de hecho aqui los dos
                        # Ogerpon de banca ya estaban a 4 energias y la rama
                        # `_ogerpon_energy >= 3` los VETABA por "sobrecarga",
                        # dejando muerta en la mano la Planta que subia el
                        # ataque de 330 a 390 sobre 350 PV. Va ANTES de los
                        # topes por matchup (Cubchoo / Alakazam / Hop's /
                        # Crustle) por la misma razon que `_td_ko_on_active`:
                        # esto no es sobrecargar, es rematar.
                        #
                        # Desempate entre varios Ogerpon: la Planta habilita el
                        # mismo KO caiga donde caiga, asi que se prefiere el que
                        # AUN NO llega a su propio ataque (< 3 efectivas) -- de
                        # paso queda listo como segundo atacante -- sobre el que
                        # ya estaba cargado (registro_008 paso 94).
                        score = 31500 if _ogerpon_energy < 3 else 31490
                    elif (op_is_cubchoo_deck and
                            _physical_energy(_ogerpon_energy)
                            >= (2 if ESTADO.meganium_in_play else 4)):
                        # Matchup Cubchoo (user): no sobrecargar al Ogerpon con
                        # Teal Dance mas alla del tope FISICO (2 con Meganium / 4
                        # sin). len(energies) viene DUPLICADO por Wild Growth con
                        # Meganium, por eso convertimos a cartas fisicas antes de
                        # comparar. No se necesita mas energia para atacar.
                        # Excepcion: si habilita un KO (arriba, _td_ko_on_active).
                        score = SCORE_VETO
                    elif ((op_is_alakazam_deck or op_is_hop_deck)
                            and _physical_energy(_ogerpon_energy)
                            >= _ogerpon_base_phys_cap(ESTADO.meganium_in_play,
                                                      op_is_hop_deck)):
                        # Regla (user, vs Alakazam y vs Hop's): tope de energia
                        # para Teal Mask Ogerpon ex via Teal Dance. Base FISICA =
                        # 2 con Meganium (Wild Growth duplica cada Planta), 3 sin
                        # Meganium vs Hop's y 4 sin Meganium vs Alakazam. En
                        # BANCA es DURO; en el ACTIVO la energia extra solo se
                        # permite si HABILITA el KO al activo rival, caso ya
                        # resuelto arriba por _td_ko_on_active (31500) -- la
                        # UNICA razon para pasar del tope con Teal Dance. Fuera
                        # de esa excepcion no sobrecargamos: reservamos energia.
                        # len(energies) es EFECTIVA => se pasa a cartas fisicas.
                        score = SCORE_VETO
                    elif _teal_wall_pivot and o.area == AreaType.ACTIVE:
                        # Activo condenado (Teal Mask Ogerpon ex) que no puede
                        # atacar + Hydrapple ex (muro) en banca: usar Teal Dance
                        # en el ACTIVO (adjunta Grass + ROBA 1) para habilitar su
                        # retirada (coste 1) y luego subir al cuerpo mas fuerte.
                        # Debe GANAR al adjunte manual (~31200) para aprovechar el
                        # robo y no malgastar la energia del turno.
                        score = 31600
                    elif _teal_dance_ko_pivot and o.area == AreaType.ACTIVE:
                        # Pivote Teal Dance -> retirar -> promover atacante letal
                        # (user, log 85802744 turno 16): activo Teal Mask Ogerpon
                        # ex bloqueado por el muro Crustle que aun no puede
                        # retirarse, con un atacante no-ex LISTO en banca (Tapu
                        # Bulu, 220 de dano) que noquea al muro. Teal Dance en el
                        # activo adjunta la Planta (+ROBA) y habilita la retirada
                        # de coste 1 para subir a Tapu y noquear el proximo paso.
                        # Debe GANAR al adjunte manual a Dipplin (~31000).
                        score = 31600
                    elif (((ESTADO.op_is_crustle_deck and not op_kang_ko_target)
                            or ESTADO.op_is_cornerstone_deck
                            or op_has_ability_immune_active)
                            and _physical_energy(_ogerpon_energy) >= 2):
                        # Regla (user, vs Crustle, log 86583376 paso 84): un Teal
                        # Mask Ogerpon ex no puede tener mas de DOS energias
                        # FISICAS cargadas via Teal Dance. Contra el muro Crustle
                        # (que inmuniza a nuestros ex) Ogerpon no ataca al muro,
                        # asi que reservamos energia y no lo sobrecargamos. La
                        # UNICA excepcion (Ogerpon ACTIVO cuya 3a energia habilita
                        # el KO del activo rival) ya se resolvio arriba con
                        # _td_ko_on_active (31500). Se conserva ademas el bypass
                        # op_kang_ko_target (KO de Mega Kangaskhan ex con Hydrapple
                        # ex, donde la energia extra sube el dano de Syrup Storm).
                        # len(energies) es EFECTIVA (Wild Growth duplica) => se
                        # pasa a cartas fisicas con _physical_energy.
                        #
                        # EXTENSION a Cornerstone (autopsia v2.1 p025 t20, ciclo
                        # jul 2026; mismo patron que d801d57 amplio la whitelist
                        # anti-Cubchoo): Cornerstone Stance anula el dano de
                        # nuestros Pokemon CON habilidad, asi que este Ogerpon
                        # tampoco ataca alli -- y el agente le acumulo 3 fisicas
                        # via Teal Dance (un cuerpo muerto de 6 efectivas)
                        # mientras Tapu Bulu, EL atacante del matchup, moria de
                        # hambre a 1 fisica con la mano sin energia. El tope de
                        # 2 redirige el excedente: la regla de energy_score
                        # "cornerstone -> Tapu +22000" ya existia y ahora la
                        # energia le llega. `op_has_ability_immune_active` cubre
                        # ademas cualquier muro anti-habilidad posicional
                        # (Sylveon...). La excepcion _td_ko_on_active (arriba)
                        # sigue cubriendo el activo rival atacable del mazo
                        # mixto (Cubchoo/Beartic delante).
                        score = SCORE_VETO
                    elif _crustle_atk_needs_grass:
    
                        score = 7500
                    elif _reserve_energy_for_hydra_evolve and o.area != AreaType.ACTIVE:
    
                        score = 7500
                    elif _ogerpon_energy >= 3:
    
                        if (o.area == AreaType.ACTIVE
                                and (_win_via_boss_gust or _gust_2prize_via_boss)):
                            # Combo Myriad ganador (user, registro_012 paso 227
                            # vs Iono, PERDIDA): este turno hay un remate via
                            # Boss's Orders (gustear de la banca rival un
                            # objetivo que NOQUEAMOS para cobrar los premios que
                            # faltan) y el atacante es este Ogerpon activo. Sin
                            # esta rama, el veto de abajo ("ya tiene >=3 energias
                            # y ya noquea al activo rival, no gastes mas Plantas")
                            # mataba la habilidad, y como el adjunte manual al
                            # activo esta vetado a su vez por la PRECEDENCIA de
                            # Teal Dance, la energia acababa en un cuerpo de
                            # banca y la linea ganadora se perdia. El objetivo
                            # del gusteo no es el activo rival: la energia extra
                            # es justo la que sube Myriad hasta su vida. Score
                            # sobre las demas ramas de Teal Dance (31600) y
                            # >= 29000, para conservar el tier ENERGY y jugarse
                            # ANTES del PLAY de Boss's (tier 0).
                            score = 31700
                        elif _extra_energy_enables_ko(Teal_Mask_Ogerpon_ex, _ogerpon_energy):
                            score = 29000
                        elif _active_already_kos and o.area != AreaType.ACTIVE:
    
                            score = 31050
                        elif (o.area == AreaType.ACTIVE and _bench_attacker_ready
                                and not _active_already_kos):
    
                            score = 31050
                        else:
                            score = SCORE_VETO
                    elif _active_hydra_ready:
    
                        score = 31300
                    elif (_active_needs_energy and not _enough_for_both and ESTADO.plan.attacker < 1
                            and not (
                                ((state.turn == 1 and ESTADO.we_go_first) or
                                 (state.turn == 2 and not ESTADO.we_go_first))
                                and o.area == AreaType.ACTIVE
                                and card.id in (Teal_Mask_Ogerpon_ex, Tapu_Bulu))):
    
                        score = 7500
                    elif _reserve_hydra_active_charge and o.area != AreaType.ACTIVE:
    
                        score = 7500
                    elif _hydrapple_bench_needs_energy and not _enough_after_priorities:
    
                        score = 7500
                    elif (o.area != AreaType.ACTIVE and
                            ((not _active_needs_energy) or _enough_for_both)):
    
                        score = 31500
                    else:
    
                        score = 31000
                elif card.id == Hydrapple_ex:
    
                    _hydra_energy = len(card.energies) if isinstance(card, Pokemon) else 0
                    # Guard (user, log 85848966 paso 76, GANADO vs Crustle): NO
                    # activar Ripening Charge si la Grass extra no tiene destino
                    # util. Ripening Charge (una vez activada) OBLIGA a adjuntar
                    # a algun Pokemon; si el activo es un Tapu Bulu YA cargado
                    # (>=4 efectivas) y en banca no hay ningun atacante que
                    # necesite energia (Tapu<4ef, Dipplin sin energia o
                    # Meganium<4ef), energy_score (ATTACH_FROM) devuelve -1 para
                    # TODAS las opciones -> el desempate elige la 1a (el ACTIVO)
                    # y se sobrecarga al Tapu ya listo, malgastando una carta de
                    # Grass de la mano (que con Meganium sirve para retiradas /
                    # el proximo turno). Espeja el override de energy_score
                    # (~L4326). Como Hydrapple ex es ex y NO daña a Crustle, no
                    # se pierde ningun Syrup Storm letal al no activarla.
                    _ripen_wasted_vs_crustle = False
                    if ESTADO.op_is_crustle_deck:
                        _rip_act = my_state.active[0] if my_state.active else None
                        _rip_active_tapu_full = (
                            _rip_act is not None and _rip_act.id == Tapu_Bulu
                            and len(_rip_act.energies) * _grass_mult() >= 4)
                        if _rip_active_tapu_full:
                            _rip_bench_needs = any(
                                _bp is not None and (
                                    (_bp.id == Tapu_Bulu and len(_bp.energies) * _grass_mult() < 4)
                                    or (_bp.id == Dipplin and len(_bp.energies) < 1)
                                    or (_bp.id == Meganium and len(_bp.energies) * _grass_mult() < 4))
                                for _bp in (my_state.bench or []))
                            _ripen_wasted_vs_crustle = not _rip_bench_needs
                    if hand_counts[Basic_Grass_Energy] < 1:
                        score = SCORE_VETO
                    elif _carga_activo_remata:
                        # Ripening Charge adjunta a CUALQUIERA de nuestros
                        # Pokemon: es la via de carga que completa el coste de
                        # ataque del ACTIVO cuando el adjunte manual no basta (o
                        # ya se gasto). El objetivo -- el ACTIVO -- lo fija
                        # energy_score / ATTACH_FROM con la misma banda.
                        score = SCORE_CARGA_ACTIVO_REMATE
                    elif _carga_activo_habilita_ataque:
                        # Espejo sin KO: sin esta carga el activo no ataca y el
                        # turno se cierra en blanco.
                        score = SCORE_CARGA_ACTIVO_ATAQUE
                    elif _ripen_retreat_ko_pivot and o.area == AreaType.ACTIVE:
                        # Pivote Ripening -> retirar -> promover Tapu letal vs
                        # Crustle (user, log 86028607 turno 22): activo Hydrapple
                        # ex bloqueado por el muro con un Tapu de banca YA LISTO
                        # (220 de dano) que noquea a Crustle. Activar Ripening
                        # Charge para adjuntar una Planta al PROPIO Hydrapple y
                        # alcanzar su coste de retirada (efectivo), habilitando
                        # retirarlo y subir a Tapu para rematar. Debe GANAR a
                        # Teal Dance / adjuntes normales; el objetivo (activo
                        # Hydrapple) se fija en energy_score (ATTACH_FROM).
                        score = 31600
                    elif _ripen_bench_tapu_ko_pivot and o.area == AreaType.ACTIVE:
                        # Pivote Ripening -> cargar Tapu de banca a letal ->
                        # retirar Hydrapple -> promover Tapu -> noquear al muro
                        # (user, log 86182112 paso 82): activo Hydrapple ex
                        # bloqueado por el muro Crustle y YA retirable, con un
                        # Tapu de banca en 2 efectivas que con 1 Planta mas llega
                        # a 4 (Wood Hammer 220, letal). Activar Ripening Charge
                        # para adjuntar la 2a Planta a Tapu (objetivo fijado en
                        # energy_score / ATTACH_FROM, +20000) en vez de malgastar
                        # el adjunte en Teal Dance sobre Ogerpon. Ver
                        # _ripen_bench_tapu_ko_pivot (~L4395).
                        score = 31600
                    elif _ripen_wasted_vs_crustle:
                        score = SCORE_VETO
                    elif _ability_unlock_retreat_ko:
                        # Ripening Charge que DESBLOQUEA LA RETIRADA hacia un
                        # atacante de banca LETAL (user, registro_014 paso 137 vs
                        # Alakazam). Espejo exacto de la rama homonima de Teal
                        # Dance: `_ability_unlock_retreat_ko` detecta la linea
                        # completa (activo sin energia para retirarse + cuerpo de
                        # banca que NOQUEA) y, a diferencia del adjunte manual,
                        # sigue viva con `energyAttached` ya gastado porque la
                        # habilidad adjunta aparte. Misma banda letal (41000): por
                        # encima de cualquier carga de desarrollo. El objetivo
                        # (el ACTIVO) se fija en energy_score / ATTACH_FROM.
                        score = 41000
                    elif _ability_unlock_retreat_attack:
                        # Espejo no-letal: el atacante de banca solo hace CHIP,
                        # pero el activo no ataca ni se retira, asi que el turno
                        # entero depende de esta Planta. Banda 31250, la misma que
                        # usa Teal Dance para este caso.
                        score = 31250
                    elif _hydra_energy >= 2:
                        if _extra_energy_enables_ko(Hydrapple_ex, _hydra_energy):
                            score = 29000
                        elif (o.area == AreaType.ACTIVE and _active_hydra_cannot_ko
                                and _bench_has_chargeable):
    
                            score = 30000
                        elif _tapu_future_charge:
                            # El activo ya asegura el KO: usamos Ripening Charge
                            # (adjunta a cualquier Pokemon) para poner una 2a
                            # energia en Tapu Bulu de banca y dejarlo listo
                            # (2 fisicas = 4 efectivas con Meganium). El objetivo
                            # Tapu Bulu se elige en energy_score (ATTACH_FROM).
                            score = 30000
                        elif _ripen_heal_serial is not None:
                            # Ripening Charge por su CURACION (user, registro_008
                            # paso 122 vs Marnie's Grimmsnarl ex, PERDIDA): el
                            # Hydrapple ya llega a su ataque, asi que la rama de
                            # abajo VETABA la habilidad y la ultima Planta de la
                            # mano se iba por el adjunte MANUAL (14000) -- misma
                            # energia en el campo pero SIN los 30 de curacion.
                            # Con el Dipplin de banca a 20/80 y Shadow Bullet
                            # metiendo 30 automaticos cada turno, esos 30 son la
                            # diferencia entre conservar el cuerpo y regalar un
                            # premio. El objetivo se fija en ATTACH_FROM.
                            #
                            # Si el cuerpo que sale de la ventana es un ex son
                            # DOS premios y la curacion gana tambien a Teal Dance
                            # (31500): un robo de una carta no vale dos premios
                            # (user, partida 2 turno 10 -- el agente eligio Teal
                            # Dance sobre el Ogerpon ex de banca a 80 PV, que
                            # murio ese mismo turno con 5 Plantas encima).
                            score = (RIPEN_HEAL_EX_ABILITY_SCORE if _ripen_heal_ex
                                     else RIPEN_HEAL_ABILITY_SCORE)
                        elif _ripen_bench_ready_pivot:
                            # SEGUNDO ATACANTE con la habilidad (user,
                            # registro_014 paso 137 vs Alakazam): el Hydrapple ya
                            # llega a su ataque, asi que todas las ramas de arriba
                            # miran solo si la Planta le sirve A EL y la habilidad
                            # se VETABA -- las Plantas acababan de forraje en el
                            # coste de una Ultra Ball. Pero Ripening Charge adjunta
                            # a CUALQUIERA de nuestros Pokemon: si con ella un
                            # atacante REAL de banca pasa de "no llega" a LISTO,
                            # es un cuerpo mas que ataca el proximo turno (o este
                            # mismo, si se retira el activo) por una carta que no
                            # tenia otro destino. Banda 30000, la de las demas
                            # cargas de banca por habilidad (`_tapu_future_charge`).
                            score = 30000
                        else:
                            score = SCORE_VETO
                    elif _active_needs_energy and not _enough_for_both and o.area != AreaType.ACTIVE:
    
                        score = 7500
                    else:
    
                        _hydra_eff = _hydra_energy * _grass_mult()
                        if _hydra_eff < 2:
    
                            if _hydra_energy == 0 and o.area != AreaType.ACTIVE:
                                score = 31150
                            else:
                                score = 31100
                        else:
    
                            score = 30500
                elif card.id == Fezandipiti_ex:
                    # Orden correcto Unfair Stamp -> Flip the Script: mientras
                    # tengamos Unfair Stamp jugable este turno (nos noquearon el
                    # turno anterior y sigue en la mano) primero se juega Unfair
                    # Stamp y DESPUES la habilidad de Fezandipiti. Asi el Stamp
                    # no baraja de vuelta las 3 cartas que roba la habilidad;
                    # quedan 5 (Stamp) + 3 (habilidad) = 8 cartas. Unfair Stamp
                    # es Item: al jugarse sale de la mano y _stamp_blocks_supp_chain
                    # pasa a False, re-habilitando la habilidad (30000).
                    # Ademas, si tenemos Lillie's Determination en la mano (y aun
                    # no jugamos Supporter), la jugamos ANTES que la habilidad.
                    #
                    # ATENCION (user, registro_006 paso 78 vs Archaludon ex,
                    # PERDIDA): los dos son vetos de ORDEN, no de VALOR -- dicen
                    # "primero X, DESPUES la habilidad". Si X no se va a jugar en
                    # este menu no hay "despues" y el veto se convierte en una
                    # perdida seca: Flip the Script es UNA VEZ POR TURNO y su
                    # condicion (nos noquearon el turno anterior) no vuelve. Por
                    # eso se registran como veto DIFERIBLE en
                    # `_ability_order_veto` y se revocan mas abajo (ver el bloque
                    # "REVOCAR VETOS DE ORDEN"), en vez de matar la habilidad
                    # aqui de forma incondicional. El freno de deck-out, que si
                    # es un veto de VALOR, se evalua ANTES y no se revoca nunca.
                    if getattr(my_state, 'deckCount', 60) <= 4:
                        # FRENO DE DECK-OUT (autopsia crustle jul 2026): con
                        # el mazo en <=4, robar 3 con Flip the Script deja el
                        # mazo a <=1 y el robo obligatorio del proximo turno
                        # nos pone al borde de perder por deck-out. El draw
                        # opcional no vale la partida.
                        score = SCORE_VETO
                    else:
                        # BANDA (user, registro_006 pasos 95-102, episodio
                        # 88710543 vs Mega Lucario): el robo de 3 va ANTES de
                        # gastar la energia del turno. Con 30000 la habilidad
                        # perdia contra Teal Dance (31300) y Ripening Charge
                        # (31100) menu tras menu y el turno se cerraba con la
                        # habilidad SIN USAR -- gratis, UNA VEZ POR TURNO y con
                        # su condicion (que nos noquearan) muerta al acabar el
                        # turno. Ademas el orden correcto es este por
                        # informacion: las 3 cartas nuevas pueden traer Plantas,
                        # asi que decidir los adjuntes DESPUES del robo es
                        # estrictamente mejor que al contrario. Se queda por
                        # DEBAJO de las bandas letales de esas mismas habilidades
                        # (41000/41900: la habilidad que HABILITA el KO de hoy
                        # sigue primero) y del remate ganador (_TIER_WIN_ATTACK):
                        # si la partida se cierra este turno, robar no aporta.
                        score = FEZ_DRAW_ABILITY_SCORE
                        _ab_order_blockers = tuple(
                            _blk_id for _blk_id, _blk_on in (
                                (Unfair_Stamp, _stamp_blocks_supp_chain),
                                (Lillie_Determination, _lillie_blocks_fez_ability))
                            if _blk_on)
                        if _ab_order_blockers:
                            _ability_order_veto[len(scores)] = (
                                score, _ab_order_blockers)
                            score = SCORE_VETO
                elif card.id == Meowth_ex:
    
                    score = 30000
                elif card.id == 1267:
                    score = 1
                else:
                    score = 29000
    
        elif o.type == OptionType.RETREAT:
    
            _active_reloc = my_state.active[0] if my_state.active else None
    
            # Regla (user, log 86510119 paso 26, vs Dragapult, PERDIDA): si al
            # retirar el activo la promocion volveria a subir un Pokemon de la
            # MISMA especie que el que estamos retirando, la retirada no cambia
            # nada y solo malgasta la energia del coste de retirada. Se cancela
            # (score = SCORE_VETO) para dejar al Pokemon en el activo. Dos casos:
            #   (a) todos los candidatos de banca son la misma especie que el
            #       activo (el unico candidato es el mismo Pokemon), o
            #   (b) la promocion prefiere subir un BASICO de 1 premio (tenemos
            #       Lillie's Determination y NINGUN atacante de banca listo para
            #       atacar este turno, rival no inmune a ex/habilidad) y ese
            #       basico volveria a ser la especie del activo (p.ej. Applin
            #       activo con otro Applin en banca): subir Applin por Applin no
            #       aporta nada.
            _same_species_retreat = False
            if _active_reloc is not None:
                _ss_bench = [bp for bp in (my_state.bench or [])
                             if bp is not None and isinstance(bp, Pokemon)]
                if _ss_bench:
                    # (a) Caso literal: no hay ningun candidato de otra especie.
                    _ss_only_same = all(bp.id == _active_reloc.id
                                        for bp in _ss_bench)
    
                    # (b) Caso "preferir basico": reproducimos la condicion de la
                    # promocion (`_refresh_promote_prefer_basic`).
                    _ss_grass_attach = (
                        hand_counts.get(Basic_Grass_Energy, 0) >= 1
                        and not state.energyAttached)
                    _ss_bench_atk_ready = False
                    for bp in _ss_bench:
                        if bp.id not in MAIN_ATTACKERS:
                            continue
                        _ss_e = len(bp.energies)
                        if _can_attack_eff(bp.id, _ss_e) or (
                                _ss_grass_attach
                                and _can_attack_eff(
                                    bp.id, _ss_e + _grass_attach_unit())):
                            _ss_bench_atk_ready = True
                            break
                    _ss_prefer_basic = (
                        hand_counts.get(Lillie_Determination, 0) >= 1
                        and not op_has_ex_immune_active
                        and not op_has_ability_immune_active
                        and not _ss_bench_atk_ready)
                    _ss_act_data = card_table.get(_active_reloc.id)
                    _ss_act_is_basic = (
                        _ss_act_data is not None
                        and not getattr(_ss_act_data, 'stage1', False)
                        and not getattr(_ss_act_data, 'stage2', False))
                    # Basicos no-ex candidatos de banca (los que la promocion
                    # preferiria como muro de 1 premio).
                    _ss_bench_basics = []
                    for bp in _ss_bench:
                        _bp_d = card_table.get(bp.id)
                        if (_bp_d is not None
                                and not getattr(_bp_d, 'stage1', False)
                                and not getattr(_bp_d, 'stage2', False)
                                and bp.id not in OUR_EX_IDS):
                            _ss_bench_basics.append(bp.id)
                    # El basico promovido es de la especie del activo si: el
                    # activo es Applin (basico de maxima prioridad) y hay otro
                    # Applin en banca, o todos los basicos candidatos son de la
                    # especie del activo (suba el que suba, misma especie).
                    _ss_same_basic = False
                    if _ss_bench_basics:
                        if _active_reloc.id == Applin:
                            _ss_same_basic = (Applin in _ss_bench_basics)
                        else:
                            _ss_same_basic = (
                                Applin not in _ss_bench_basics
                                and all(_b == _active_reloc.id
                                        for _b in _ss_bench_basics))
                    _ss_prefer_same = (
                        _ss_prefer_basic and _ss_act_is_basic
                        and _active_reloc.id not in OUR_EX_IDS
                        and _ss_same_basic)
    
                    _same_species_retreat = _ss_only_same or _ss_prefer_same
    
            # Regla: Meganium activo + Hydrapple ex en banca + rival SIN
            # proteccion-ex (no Crustle/Sylveon/inmunes a ex) => retirar Meganium
            # para promover a Hydrapple ex (atacante/motor clave). Meganium sigue
            # en banca, asi que Wild Growth se mantiene. NO aplica vs muros
            # inmunes a ex, donde Hydrapple ex (ex) no podria golpear.
            _meg_retreat_for_hydra = False
            if (_active_reloc is not None and _active_reloc.id == Meganium
                    and can_switch
                    and not (ESTADO.op_is_crustle_deck or op_has_ex_immune_active
                             or op_has_ex_immune_bench or op_is_sylveon_deck)):
                for _mrh_bp in (my_state.bench or []):
                    if _mrh_bp is not None and _mrh_bp.id == Hydrapple_ex:
                        _meg_retreat_for_hydra = True
                        break
    
            _grd_prefer_attack = False
            if (_active_reloc is not None and can_switch
                    and not (ESTADO.op_is_crustle_deck or ESTADO.op_is_cornerstone_deck)):
                _grd_opa = (op_state.active[0]
                            if (op_state.active and op_state.active[0] is not None)
                            else None)
                _grd_opa_hp = (_grd_opa.hp or 0) if _grd_opa is not None else 0
                _grd_opa_e = len(_grd_opa.energies) if _grd_opa is not None else 0
    
                def _grd_damage(_p):
                    _e = len(_p.energies)
                    _eff = _e * _grass_mult()
                    if _p.id == Hydrapple_ex and _eff >= 2:
                        return 30 + 30 * total_grass
                    if _p.id == Teal_Mask_Ogerpon_ex and _eff >= 3:
                        return 30 + 30 * (_e + _grd_opa_e)
                    if _p.id == Dipplin and _e >= 1:
                        return 100
                    if _p.id == Tapu_Bulu and _eff >= 4:
                        return 220
                    if _p.id == Fezandipiti_ex and _eff >= 3:
                        return 100
                    if _p.id == Pinsir and _eff >= 2:
                        return 100
                    if _p.id == Meganium and _eff >= 4:
                        return 140
                    return 0
    
                _grd_active_can_attack = _grd_damage(_active_reloc) > 0
                _grd_any_ko = False
                for _grd_p in ([_active_reloc] + list(my_state.bench)):
                    if _grd_p is None:
                        continue
                    _grd_d = _grd_damage(_grd_p)
                    if _grd_d > 0 and _grd_opa_hp > 0 and _grd_d >= _grd_opa_hp:
                        _grd_any_ko = True
                        break
                if _grd_active_can_attack and not _grd_any_ko:
                    _grd_prefer_attack = True
    
            _active_can_ko_now = False
            if (can_attack and _active_reloc is not None
                    and op_state.active and op_state.active[0] is not None):
                _acn_op = op_state.active[0]
                _acn_e = len(_active_reloc.energies)
                _acn_eff = _acn_e * _grass_mult()
                _acn_base = 0
                if _active_reloc.id == Dipplin and _acn_e >= 1:
                    _acn_base = 20 * bench_count
                elif _active_reloc.id == Hydrapple_ex and _acn_eff >= 2:
                    _acn_base = 30 + 30 * total_grass
                elif _active_reloc.id == Teal_Mask_Ogerpon_ex and _acn_eff >= 3:
                    # Myriad cuenta la energia de AMBOS activos.
                    _acn_base = 30 + 30 * (
                        _acn_e + len(getattr(_acn_op, 'energies', []) or []))
                elif _active_reloc.id == Tapu_Bulu and _acn_eff >= 4:
                    _acn_base = 220
                elif _active_reloc.id == Fezandipiti_ex and _acn_eff >= 3:
                    _acn_base = 100
                elif _active_reloc.id == Meganium and _acn_eff >= 4:
                    _acn_base = 140
                elif _active_reloc.id == Pinsir and _acn_eff >= 2:
                    _acn_base = 100
                if _acn_base > 0:
                    _acn_dmg = _our_effective_damage(
                        _active_reloc, _acn_op, _acn_base,
                        ESTADO.meganium_in_play, neutralization_zone_active)
                    if _acn_dmg > 0 and _acn_dmg >= (_acn_op.hp or 0):
                        _active_can_ko_now = True
    
            # El activo TAMBIEN "puede noquear ahora" cuando su ataque elige
            # objetivo y el KO esta en la BANCA rival (Cruel Arrow de Fezandipiti
            # ex; user, registro_004 paso 54 vs Alakazam). Sin esto el bloque de
            # arriba solo miraba al activo rival, `_active_can_ko_now` salia
            # False y la retirada -- que ademas DESCARTA la energia del snipe --
            # ganaba el menu tirando un premio gratis.
            # `_active_kos_op_active` conserva el sentido ESTRICTO (el KO cae
            # sobre el activo rival) para los pivotes que comparan premios.
            _active_kos_op_active = _active_can_ko_now
            if _active_snipe_ko_now:
                _active_can_ko_now = True
    
            # Proteger a Hydrapple ex: si nuestro Hydrapple ex activo va a ser
            # noqueado el proximo turno y no puede tomar un KO este turno, es
            # mejor retirarlo y promover un atacante de banca no-ex (p.ej.
            # Dipplin) que si pueda atacar. Hydrapple ex es clave para acelerar
            # energia y cargar a Tapu Bulu en un solo turno, asi que evitamos
            # entregarlo (2 premios) por nada.
            _hydra_ex_protect_retreat = False
            if (_active_reloc is not None and _active_reloc.id == Hydrapple_ex
                    and can_switch and active_ko_likely
                    and not _active_can_ko_now):
                for _hpr_bp in my_state.bench:
                    if _hpr_bp is None:
                        continue
                    _hpr_e = len(_hpr_bp.energies)
                    _hpr_eff = _hpr_e * _grass_mult()
                    if _hpr_bp.id == Dipplin and _hpr_e >= 1:
                        _hydra_ex_protect_retreat = True
                        break
                    elif _hpr_bp.id == Tapu_Bulu and _hpr_eff >= 4:
                        _hydra_ex_protect_retreat = True
                        break
                    elif _hpr_bp.id == Meganium and _hpr_eff >= 4:
                        _hydra_ex_protect_retreat = True
                        break
                    elif _hpr_bp.id == Pinsir and _hpr_eff >= 2:
                        _hydra_ex_protect_retreat = True
                        break
    
            # Regla (user): si un Hydrapple ex de BANCA (ya con >=2 efectivas)
            # puede subir al activo y rematar con un Syrup Storm LETAL sobre el
            # activo rival, retirar el activo actual para promoverlo y ganar la
            # partida. Solo cuando se puede cambiar (can_switch). La promocion
            # posterior elige a ese Hydrapple ex via `_best_promote_card`.
            # IMPORTANTE (user, log 86338560 paso 114, GANADA vs Mega Lucario):
            # NO retirar el activo si el PROPIO activo YA puede rematar este turno
            # (`_active_can_ko_now`). En ese caso subir a otro Hydrapple ex de
            # banca (mismo tipo, con MENOS energia) solo pagaria el coste de
            # retirada y reduciria el ataque sin ganar nada: el activo debe atacar.
            # EXCEPCION (user, log 86412738 paso 145 vs Hops; GENERALIZADA en log
            # 86505760 paso 55, GANADA vs Alakazam): aunque el activo YA pueda
            # noquear, si es un ex FRAGIL (2 premios, distinto de Hydrapple y con
            # menos HP que el muro 330) y un Hydrapple ex de BANCA TAMBIEN puede
            # rematar (Syrup Storm letal), SIEMPRE se prefiere retirar y atacar con
            # el Hydrapple ex: mismo KO pero deja el muro de 330 HP como activo en
            # vez de exponer el ex fragil (Hydrapple aguanta ataques mayores que
            # Ogerpon en turnos futuros). Regla del user: siempre que un Hydrapple
            # ex de banca pueda derrotar al rival, es nuestro atacante prioritario.
            # UNICA excepcion: no pivotar si atacar con el activo YA gana la partida
            # este turno (my_prize <= premios del activo rival): ahi no hay turno
            # futuro que proteger, se ataca directo. El pivote NO aplica cuando el
            # activo es NO-ex (retirarlo para exponer un ex de 2 premios seria peor)
            # ni cuando el activo ya es el propio Hydrapple ex.
            _active_ex_fragile_pivot = (
                _active_reloc is not None
                and _active_can_ko_now
                and _active_reloc.id in OUR_EX_IDS
                and _active_reloc.id != Hydrapple_ex
                and (_active_reloc.maxHp or 0) < 330
                and op_state.active and op_state.active[0] is not None
                and not (my_prize <= prize_count_op(op_state.active[0])))
            _hydra_lethal_promote = False
            if (_active_reloc is not None and can_switch
                    and (not _active_can_ko_now or _active_ex_fragile_pivot)
                    and op_state.active and op_state.active[0] is not None):
                _hlp_opa = op_state.active[0]
                _hlp_opa_hp = _hlp_opa.hp or 0
                # Syrup Storm escala con el Grass DEL CAMPO, y la retirada
                # DESCARTA la energia del activo para pagar su coste: hay que
                # medir el dano con el Grass que quedara DESPUES del retiro
                # (user, registro_011 paso 138 vs Dragapult, PERDIDA). Alli el
                # activo era un Tapu Bulu con 3 Plantas (6 efectivas): con el
                # Grass previo (10) Syrup Storm daba 330 y "noqueaba" al
                # Dragapult ex de 320, pero al retirar se descartaban esas 3
                # Plantas y el ataque real quedaba en 150. Mismo patron que
                # `_bo_grass_after` en la seleccion del gusteo.
                _hlp_ret_cost = RETREAT_COST.get(_active_reloc.id, 1)
                _hlp_grass_after = max(
                    0, total_grass - (0 if has_switch_card
                                      else _retreat_grass_units(_hlp_ret_cost)))
                for _hlp_bp in (my_state.bench or []):
                    if _hlp_bp is None or _hlp_bp.id != Hydrapple_ex:
                        continue
                    if len(_hlp_bp.energies) * _grass_mult() < 2:
                        continue  # no puede pagar Syrup Storm
                    # El pivote de "ex fragil" (`_active_ex_fragile_pivot`) es
                    # el UNICO que retira un activo que YA noquea: no gana ni un
                    # premio (los dos cuerpos son ex de 2) y encima paga la
                    # energia del coste de retirada. Lo unico que lo justifica es
                    # dejar delante al cuerpo que AGUANTA MAS -- y eso se mide
                    # con la vida ACTUAL, no con el HP IMPRESO (user,
                    # registro_014 paso 166 vs Alakazam). Alli el "muro de 330"
                    # era un Hydrapple ex a 90/330 y el activo un Teal Mask
                    # Ogerpon ex a 210/210: los dos noqueaban al Alakazam, asi
                    # que retirar solo servia para poner delante al cuerpo que
                    # muere. `_active_ex_fragile_pivot` mide la fragilidad con
                    # `maxHp < 330`, que es una constante de la carta y no
                    # sabe nada del dano ya recibido; esta comparacion es la que
                    # mira el tablero. Mejora ESTRICTA: empatados, el cambio
                    # sigue costando la energia de la retirada. Mismo criterio
                    # que `_pdx_act_margin` en `_prize_denial_pivot` ("el que
                    # AGUANTA va delante"). No toca la rama de activo
                    # ESTANCADO (`not _active_can_ko_now`), donde el pivote si
                    # compra el KO que no teniamos.
                    if (_active_ex_fragile_pivot
                            and (_hlp_bp.hp or 0) <= (_active_reloc.hp or 0)):
                        continue
                    # No promover un Hydrapple ex al que el activo rival NOQUEA
                    # (user): regalaria 2 premios. En el registro el Hydrapple
                    # estaba a 70/330 y el rival a 2 premios, asi que promoverlo
                    # entregaba la partida. Lo correcto era atacar con el activo.
                    _hlp_dmg_rival = _op_active_attack_damage_to(
                        _hlp_opa, _hlp_bp,
                        getattr(op_state, 'handCount', None))
                    if _hlp_dmg_rival >= (_hlp_bp.hp or 0):
                        continue
                    _hlp_dmg = _our_effective_damage(
                        _hlp_bp, _hlp_opa, 30 + 30 * _hlp_grass_after,
                        ESTADO.meganium_in_play, neutralization_zone_active)
                    if _hlp_dmg > 0 and _hlp_opa_hp > 0 and _hlp_dmg >= _hlp_opa_hp:
                        _hydra_lethal_promote = True
                        break
    
            # Regla (user, log 86583929 turno 4, vs Alakazam, PERDIDA): pivote de
            # KO con Teal Mask Ogerpon ex. Si el activo esta ESTANCADO (no puede
            # noquear este turno, p.ej. un Fezandipiti ex sin las 3 energias de su
            # ataque) y en la banca hay un Teal Mask Ogerpon ex que, al PROMOVERLO
            # y usar Teal Dance, alcanza >=3 energias EFECTIVAS y su Myriad Leaf
            # Shower NOQUEA al activo rival, retirar el activo para subir al Ogerpon
            # y rematar. La Planta que necesita Teal Dance se obtiene de la mano o,
            # con Night Stretcher, recuperando una Planta del descarte -- incluida
            # la que el propio coste de retirada acaba de descartar del activo. El
            # scorer greedy evaluaba a los Ogerpon de banca a su energia ACTUAL
            # (via _grd_damage/_bench_attacker_can_ko, que exigen >=3 efectivas) y
            # nunca modelaba la rampa de Teal Dance tras promover, por eso no "veia"
            # esta linea. Solo si el rival NO inmuniza a nuestros ex (Ogerpon no
            # daña a Crustle/Sylveon). len(energies) es EFECTIVA (Wild Growth de
            # Meganium duplica cada Planta): sin Meganium un Ogerpon a 1 Planta
            # llega a 2 tras Teal Dance (<3) y el detector no dispara.
            # El "activo estancado" que exige este pivote ya no es simplemente
            # `not _active_can_ko_now`: un Fezandipiti ex activo con Cruel Arrow
            # letal sobre la BANCA rival SI tiene premio hoy (user, registro_004
            # paso 54). Retirarlo cuesta su energia y expone otro cuerpo, asi que
            # el pivote solo se le impone cuando el KO del Ogerpon vale MAS
            # premios que el del snipe; empatado o por debajo, se ataca.
            _olp_active_stuck = not _active_can_ko_now
            if (not _olp_active_stuck and _active_snipe_ko_now
                    and not _active_kos_op_active
                    and op_state.active and op_state.active[0] is not None):
                _olp_active_stuck = (prize_count_op(op_state.active[0])
                                     > _active_snipe_ko_prizes)
    
            _ogerpon_lethal_promote = False
            if (_active_reloc is not None and can_switch
                    and _olp_active_stuck
                    and _active_reloc.id != Teal_Mask_Ogerpon_ex
                    and not op_has_ex_immune_active
                    and op_state.active and op_state.active[0] is not None):
                _olp_opa = op_state.active[0]
                _olp_opa_hp = _olp_opa.hp or 0
                _olp_op_e = len(_olp_opa.energies)
                # Planta disponible para Teal Dance: en mano, o recuperable con
                # Night Stretcher desde el descarte (o desde la energia que la
                # retirada acaba de descartar del activo, que en nuestro mazo es
                # Planta).
                # Y ademas tiene que QUEDAR una via para ponerla en el campo
                # (user, registro_004 paso 54): alli habia una Planta en mano,
                # pero el adjunte manual ya estaba gastado y los tres Ogerpon
                # habian usado su Teal Dance, asi que el "remate" era imposible y
                # la retirada (8900) aplastaba al ataque real del Fezandipiti.
                # `_grass_attach_route_open` mira justo eso: adjunte manual libre
                # o alguna habilidad de carga aun sin usar.
                _olp_ruta_ok = _grass_attach_route_open(
                    state, field_counts, abilities_off=meowth_ability_lock)
                _olp_grass_ok = _olp_ruta_ok and (
                    hand_counts.get(Basic_Grass_Energy, 0) >= 1
                    or (hand_counts.get(Night_Stretcher, 0) >= 1
                        and (discard_counts.get(Basic_Grass_Energy, 0) >= 1
                             or _physical_energy(len(_active_reloc.energies)) >= 1)))
                if _olp_grass_ok:
                    for _olp_bp in (my_state.bench or []):
                        if _olp_bp is None or _olp_bp.id != Teal_Mask_Ogerpon_ex:
                            continue
                        _olp_eff_after = len(_olp_bp.energies) + _grass_attach_unit()
                        if _olp_eff_after < 3:
                            continue
                        _olp_dmg = _our_effective_damage(
                            _olp_bp, _olp_opa,
                            30 + 30 * (_olp_eff_after + _olp_op_e),
                            ESTADO.meganium_in_play, neutralization_zone_active)
                        if _olp_dmg > 0 and _olp_opa_hp > 0 and _olp_dmg >= _olp_opa_hp:
                            _ogerpon_lethal_promote = True
                            break
    
            # Regla (user): un Tapu Bulu CARGADO en el activo que puede noquear
            # al Pokemon activo rival NO debe retirarse; debe atacar. Al no ser
            # ex, si lo noquean solo entrega 1 premio, asi que conviene rematar
            # con el en lugar de gastar el pivote a Hydrapple ex (que si es
            # noqueado entrega 2 premios). Por eso vetamos el retiro/promocion.
            # EXCEPCION: en matchups ex-inmunes (Crustle / Cornerstone /
            # Sylveon), si el activo rival NO pertenece a la linea ex-inmune
            # (no requiere a Tapu para ser danado) y hay un Pokemon de banca que
            # lo puede rematar, SI retiramos a Tapu Bulu para reservarlo como
            # atacante clave contra los muros con proteccion ex. Si el activo
            # rival ES de la linea ex-inmune, Tapu Bulu ataca (es quien puede
            # con esos muros).
            if (_active_reloc is not None and _active_reloc.id == Tapu_Bulu
                    and _active_can_ko_now):
                _tapu_ex_immune_match = (ESTADO.op_is_crustle_deck
                                         or ESTADO.op_is_cornerstone_deck
                                         or op_is_sylveon_deck)
                _tapu_opa_id = (op_state.active[0].id
                                if op_state.active
                                and op_state.active[0] is not None else None)
                _tapu_opa_is_immune_line = (
                    _tapu_opa_id in {
                        Crustle_Grass, Crustle_Fighting, Dwebble_Grass,
                        Dwebble_Fighting, Sylveon,
                        Cornerstone_Mask_Ogerpon_ex}
                    or _tapu_opa_id in EEVEE_IDS)
                _tapu_reserve = (_tapu_ex_immune_match
                                 and not _tapu_opa_is_immune_line
                                 and not op_has_ex_immune_active)
                if not _tapu_reserve:
                    # Tapu Bulu debe atacar: no lo retiramos para promover.
                    _hydra_lethal_promote = False
    
            _op_active_is_cubchoo = bool(
                op_state.active and op_state.active[0] is not None
                and op_state.active[0].id == Cubchoo)
            _cub_bench_attacker_ready = any(
                _bp_cub is not None and _conf_can_attack_pkmn(_bp_cub)
                for _bp_cub in (my_state.bench or []))
    
            # DESCUADRE DE PREMIOS (user, registro_002 paso 27 vs Raging Bolt; y
            # vs Mega Abomasnow ex). Nuestro activo es un ex de 2 premios que NO
            # puede noquear al activo rival este turno y hay un cuerpo de UN
            # premio en la banca (bajado por la regla del PLAY o previo):
            # RETIRAR el ex y promover el 1-premio. Su atacante one-shotea a
            # cualquiera de los nuestros, asi que quien este delante va a caer:
            # que el KO rival pague 1 premio y no 2 (su mazo, todo ex de 2-3
            # premios, necesita KOs grandes para ganar a tiempo).
            _raging_sac_pivot = (
                _descuadre_matchup
                and _active_reloc is not None
                and _active_reloc.id in OUR_EX_IDS
                and not _active_can_ko_now
                and can_switch
                and any(bp is not None and prize_count(bp) == 1
                        for bp in (my_state.bench or [])))
    
            # DESCUADRE GENERALIZADO (user, registro_004 paso 37 vs Mega Lucario
            # ex): mismo patron que `_raging_sac_pivot` pero para CUALQUIER mazo,
            # detectado con el remate rival REAL en vez de una lista fija de
            # matchups. Nuestro activo es un ex (2 premios) que SI puede atacar
            # pero cuyo ataque NO noquea al activo rival (`not _active_can_ko_now`)
            # y el ataque del activo rival NOQUEA a nuestro ex el proximo turno
            # (`_op_active_attack_damage_to` >= HP). Si ademas NO hay ningun
            # atacante LISTO en la banca (no tenemos jugada mejor que preservar el
            # ex) y hay un cuerpo de 1 premio para poner delante, RETIRAR el ex y
            # sacrificar el 1-premio: si atacaramos no noqueariamos y el ex moriria
            # el proximo turno regalando 2 premios; retirandolo cedemos solo 1
            # premio y conservamos el ex -con su energia- en la banca para
            # re-promoverlo tras el KO. La promocion elige el basico mas barato
            # (`_lucario_ko_prefer_basic` / `_ko_prefer_basic_general`). Excluye
            # los muros inmunes a ex en el activo rival (ahi el ex no ataca y ya
            # hay logica dedicada: `_ex_stuck_promo_ready` / `_nonex_active_hits_wall`).
            # No sacrificar-retirar cuando estamos EN RANGO DE REMATE (my_prize<=2):
            # ahi hay que RACEAR/rematar, no ceder tempo (user, test Dragapult win
            # engine, my_prize=1 -> atacar). El descuadre defensivo solo aplica
            # cuando aun faltan >=3 KOs para ganar, donde frenar el 2x1 importa.
            # El retiro-sacrificio se POSPONE mientras queden jugadas de desarrollo
            # de este turno (user, registro_004 paso 36): un Supporter aun sin
            # jugar (p.ej. Xerosic, que descarta mano rival) o un ATACANTE basico
            # en mano que podemos poner en banca (montar el proximo atacante) valen
            # mas que retirar YA -- retirar y desarrollar no son excluyentes en el
            # mismo turno, asi que primero se desarrolla y el retiro sale al final
            # (paso 37, con la mano ya vaciada de esas jugadas). No se pospone por
            # items sueltos de bajo valor (p.ej. Unfair Stamp), que no aportan mas
            # que el retiro con el activo condenado al frente.
            _doomed_pending_play = False
            for _dpo in select.option:
                if _dpo.type != OptionType.PLAY:
                    continue
                _dpc = get_card(obs, AreaType.HAND, _dpo.index, my_index)
                if _dpc is None:
                    continue
                _dpd = card_table.get(_dpc.id)
                if (_dpd is not None
                        and getattr(_dpd, 'cardType', None) == CardType.SUPPORTER
                        and not state.supporterPlayed):
                    _doomed_pending_play = True
                    break
                if (_dpc.id in MAIN_ATTACKERS and bench_count < 5
                        and _dpd is not None
                        and not getattr(_dpd, 'stage1', False)
                        and not getattr(_dpd, 'stage2', False)):
                    _doomed_pending_play = True
                    break
    
            _doomed_ex_sac_pivot = False
            if (not _raging_sac_pivot
                    and not _doomed_pending_play
                    and _active_reloc is not None
                    and _active_reloc.id in OUR_EX_IDS
                    and not _active_can_ko_now
                    and can_switch
                    and my_prize >= 3
                    and not _bench_attacker_ready
                    and not op_has_ex_immune_active
                    and op_state.active and op_state.active[0] is not None
                    and any(bp is not None and prize_count(bp) == 1
                            for bp in (my_state.bench or []))):
                _des_opa = op_state.active[0]
                _des_op_dmg = _op_active_attack_damage_to(
                    _des_opa, _active_reloc, getattr(op_state, 'handCount', None))
                # GUARDA DEL SNIPE (user, registro_004 t4 vs Marnie's
                # Grimmsnarl, PERDIDA): esconder el ex en la banca solo niega
                # premios si ALLI SOBREVIVE. Contra un atacante que ademas pega
                # a la banca (Shadow Bullet: 180 al activo + 30 a un banquillo;
                # Phantom Dive, Jetting Blow...) un ex ya herido por debajo de
                # ese chip muere igual, y entonces la retirada CONCEDE MAS:
                #   quedarse  -> 2 premios (el ex activo noqueado)
                #   retirarse -> 1 (el cuerpo promovido) + 2 (el ex sniped) = 3
                # La aritmetica nunca favorece retirarse en ese caso: como
                # mucho empata (si el snipe iba a matar otro cuerpo de banca
                # igual de caro), asi que el pivote se apaga.
                #
                # Se mide con el ATACANTE concreto (`OP_BENCH_SNIPE_DAMAGE` del
                # ACTIVO rival), no con el flag de mesa `_op_bench_snipe_dmg`:
                # ese cae a `OP_BENCH_SNIPE_DEFAULT` en cuanto hay CUALQUIER
                # amenaza de goteo en juego, y apagar el pivote por un sniper
                # que no esta al frente cuesta partidas (medido vs
                # crustle/Kangaskhan: -3.1 puntos con la version amplia).
                _des_snipe = OP_BENCH_SNIPE_DAMAGE.get(_des_opa.id, 0)
                if (_des_op_dmg >= (_active_reloc.hp or 0)
                        and _des_snipe < (_active_reloc.hp or 0)):
                    _doomed_ex_sac_pivot = True
    
            if _suicide_swap_win_promote:
                # RELEVO DEL REMATE SUICIDA (user, registro_016 paso 184 vs
                # Marnie's Grimmsnarl, EMPATE): el ataque del activo noquea pero
                # su AUTO-DANO lo mata, y con ese cadaver el rival cobra su
                # ultimo premio -> empate (o derrota). En la banca hay un
                # rematador que gana LIMPIO: retirar para promoverlo es la unica
                # jugada que convierte el 0-0 en victoria, asi que va por encima
                # de cualquier otro motivo de retiro (incluidos los pivotes
                # letales de Hydrapple/Ogerpon, que persiguen el MISMO premio con
                # menos urgencia). El tier de orden de jugada (`_TIER_WIN_ATTACK`)
                # la sube ademas por encima de cargas y desarrollo, que si no
                # dominarian por TIER pese a su menor score.
                score = 9600
            elif _win_ko_active_via_promote:
                # MATCH POINT AL ACTIVO (user, registro_010 paso 144 vs Marnie's
                # Grimmsnarl ex, PERDIDA): noquear al ACTIVO rival cobra los
                # premios que faltan y el rematador esta en la BANCA. Es la
                # MISMA jugada que el relevo del remate suicida -- cerrar la
                # partida este turno --, asi que comparte score y `_TIER_WIN_ATTACK`:
                # sin el tier, cualquier carga de energia (tier ENERGY) la
                # aplastaria por ORDEN pese a valer menos. Excluyente con
                # `_suicide_swap_win_promote`: la bandera exige que el activo
                # ACTUAL no remate.
                score = 9600
            elif _hydra_lethal_promote:
                # Retirar el activo para promover al Hydrapple ex de banca cuyo
                # Syrup Storm es LETAL y rematar. Maxima prioridad de retiro.
                score = 9000
            elif _ogerpon_lethal_promote:
                # Retirar el activo estancado para promover un Teal Mask Ogerpon
                # ex de banca y rematar con Myriad Leaf Shower tras Teal Dance
                # (user, log 86583929 turno 4 vs Alakazam). Prioridad de retiro
                # equiparada a la del pivote de Hydrapple: cobrar el premio AHORA.
                # Las acciones posteriores (Night Stretcher para recuperar la
                # Planta, Teal Dance sobre el nuevo activo y el ataque) ya las
                # habilitan sus scorers (_td_ko_on_active da 31500 al Teal Dance
                # que habilita el KO, y el scorer de ATTACK remata si es letal).
                score = 8900
            elif (_op_active_is_cubchoo and can_switch
                    and not _cub_bench_attacker_ready):
                # Matchup vs Cubchoo: su ataque deja a nuestro activo sin poder
                # atacar el proximo turno. Retirar ahora para subir a un Pokemon
                # de banca que TAMPOCO puede atacar (sin energia suficiente) solo
                # lo expone al mismo ataque y desperdicia el pivote. Mientras no
                # haya un atacante LISTO en banca, NO se retira: se mantiene el
                # activo (Cubchoo pega poco) y se aprovecha el turno para cargar
                # energia hasta dejar listo a un atacante de banca. Cuando ese
                # atacante este cargado, _cub_bench_attacker_ready sera True y se
                # permitira el retiro para subirlo y atacar en nuestro turno.
                score = SCORE_VETO
            elif (_lucario_sac_pivot and _lucario_sac_available
                    and bench_count >= 1 and can_switch):
                # Retirar el Ogerpon ex para no entregar 2 premios al Mega Lucario;
                # despues promoveremos un sacrificio de 1 premio.
                score = 8000
            elif _conf_should_retreat:
                score = 4000 + condition_urgency
            elif _hydra_ex_protect_retreat:
    
                score = 6000
            elif (_ex_stuck_promo_ready or _cubchoo_lock_stuck) and can_switch:
                # Nuestro activo es un ex bloqueado por un muro inmune (Crustle /
                # Sylveon) y hay un atacante no-ex LISTO en banca: retirar para
                # promover al que SI golpea al muro (el mas fuerte se elige en
                # `_best_promote_card`). Evita malgastar el turno atacando por 0.
                # `_cubchoo_lock_stuck`: mismo patron con el activo Hydrapple ex
                # BLOQUEADO por Snotted Up y un atacante de banca listo (paso 82).
                score = 6000
            elif _hydra_pivot_active:
                # Pivote defensivo: retirar al activo fragil y subir a Hydrapple
                # ex (vida completa) que tambien noquea. Prioridad alta para que
                # gane sobre atacar con el activo fragil (que moriria el proximo
                # turno). El plan ya apunta a Hydrapple, por lo que la opcion de
                # ATACAR con el activo queda suprimida (plan.attacker >= 1).
                score = 6500
            elif _teal_wall_pivot and can_switch:
                # Activo Teal Mask Ogerpon ex condenado que NO puede atacar: ya
                # se uso Teal Dance (adjunto 1 Grass -> paga la retirada de 1).
                # Retirar y subir al cuerpo mas fuerte de banca (Hydrapple ex,
                # 330 HP) aunque aun no pueda atacar: no regalar el activo por
                # nada y poner un muro. La promocion elige el de mas vida.
                score = 6450
            elif _hydra_wall_pivot:
                # Activo Teal Mask Ogerpon ex condenado que SI puede atacar pero
                # NO noquea (muro Hydrapple ex sano en banca). Retirar y subir al
                # muro (330 HP) que sobrevive al remate rival y sigue atacando
                # (Syrup Storm 330), en vez de atacar con el Ogerpon fragil que
                # moriria regalando 2 premios. El plan apunta a Hydrapple, asi que
                # ATACAR con el activo queda suprimido (plan.attacker >= 1).
                score = 6450
            elif _tapu_sac_pivot:
                # Sacrificio de premios (user): nuestro activo es un ex de 2
                # premios en riesgo y un Tapu Bulu de banca (1 premio) listo puede
                # noquear al activo rival. Retirar el ex y subir a Tapu Bulu para
                # atacar: mismo KO, pero si nos noquean entregamos 1 premio en vez
                # de 2. Prioridad alta: gana incluso cuando el activo tambien puede
                # noquear ahora (_active_can_ko_now). El plan apunta a Tapu, asi que
                # la opcion de ATACAR con el activo queda suprimida (plan.attacker>=1).
                score = 6600
            elif _raging_sac_pivot:
                # Descuadre vs Raging Bolt (ver el flag arriba). 6540: junto a
                # los demas sacrificios de premios (6450-6600), sobre el veto
                # generico "el activo puede atacar" (_grd_prefer_attack) que
                # aqui seria un error: atacar sin noquear regala 2 premios.
                score = 6540
            elif _prize_denial_pivot:
                # Negacion de premios (user): retirar el ex activo CONDENADO (2
                # premios) que si atacamos igual moriria el proximo turno dando al
                # rival los premios para GANAR, y subir un cuerpo de 1 premio que
                # ataca. Asi el KO rival del proximo turno NO cierra la partida. El
                # plan apunta a ese cuerpo (plan.attacker>=1), por lo que ATACAR con
                # el activo condenado queda suprimido.
                score = 6550
            elif _doomed_ex_sac_pivot:
                # Descuadre generalizado (user, registro_004 paso 37 vs Mega
                # Lucario ex): el ex activo puede atacar pero NO noquea y el rival
                # lo remata el proximo turno, sin atacante de banca listo. Retirar
                # el ex y sacrificar un cuerpo de 1 premio (cede 1 en vez de 2 y
                # preserva el ex). Mismo tier que los demas sacrificios de premios,
                # por debajo del veto "el activo puede atacar" que aqui seria un
                # error (atacar sin noquear regala 2 premios).
                score = 6530
            elif _meg_retreat_for_hydra and not _active_can_ko_now:
                # Meganium activo: subir a Hydrapple ex de banca (rival sin
                # proteccion-ex). Prioridad alta para que gane sobre atacar con
                # Meganium o mantenerlo. Excepcion: si Meganium noquea AHORA
                # (_active_can_ko_now) se queda para tomar el premio.
                score = 6400
            elif _wall_ko_promote is not None and can_switch:
                # RELEVO LETAL CONTRA EL MURO (user, registro_018 paso 113 vs
                # Crustle, PERDIDA): el activo golpea al muro pero NO lo remata y
                # en banca hay un cuerpo no bloqueado que SI (Meganium 140 vs
                # Crustle de 170 <- Tapu Bulu 220). Retirar y rematar. Va por
                # ENCIMA del veto `_nonex_active_hits_wall` -- que ya se apaga en
                # este caso -- y de los pivotes de sacrificio: cobrar el premio
                # ahora manda. El plan apunta al relevo, asi que ATACAR con el
                # activo queda suprimido.
                score = 6700
            elif _nonex_active_hits_wall:
                # user, log 86406907 paso 87, GANADA vs Crustle: nuestro activo
                # es un atacante NO-ex (p.ej. Meganium) que SI golpea al muro
                # inmune-a-ex (Crustle activo). NUNCA se retira: retirarlo solo
                # promoveria un ex de banca que hace 0 al muro. Debe ATACAR.
                score = SCORE_VETO
            elif _grd_prefer_attack:
    
                score = SCORE_VETO
            elif _active_can_ko_now:
    
                score = SCORE_VETO
            elif ESTADO.plan.attacker >= 1:
    
                _retreat_active = my_state.active[0] if my_state.active else None
                _retreat_active_can_attack = False
                if _retreat_active is not None:
                    _ra_eff = len(_retreat_active.energies) * _grass_mult()
                    _ra_can_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                                      not state.energyAttached)
                    _ra_eff_after = _ra_eff + (_grass_attach_unit() if _ra_can_attach else 0)
                    if _retreat_active.id == Hydrapple_ex:
                        _retreat_active_can_attack = (_ra_eff_after >= 2)
                    elif _retreat_active.id == Dipplin:
                        _retreat_active_can_attack = (len(_retreat_active.energies) >= 1 or _ra_can_attach)
                    elif _retreat_active.id == Teal_Mask_Ogerpon_ex:
                        _retreat_active_can_attack = (_ra_eff_after >= 3)
                    elif _retreat_active.id == Tapu_Bulu:
                        _retreat_active_can_attack = (_ra_eff_after >= 4)
                    elif _retreat_active.id == Pinsir:
                        _retreat_active_can_attack = (_ra_eff_after >= 2)
                    elif _retreat_active.id == Fezandipiti_ex:
                        _retreat_active_can_attack = (_ra_eff_after >= 3)
    
                if not _retreat_active_can_attack:
    
                    score = 3500
                else:
    
                    score = 2500
            elif my_state.active and my_state.active[0] is not None:
                active = my_state.active[0]
                active_energy = len(active.energies)
    
                _our_first_turn = (state.turn == 1 and ESTADO.we_go_first) or (state.turn == 2 and not ESTADO.we_go_first)
    
                NON_ATTACKERS = (Meganium, Meowth_ex, Chikorita, Bayleef, Applin)
    
                # Meganium incluido: puede atacar (req 4 efectivo) y debe contar
                # como atacante disponible en banca. Fuente unica: MAIN_ATTACKERS.
                STRATEGIC_ATTACKERS = MAIN_ATTACKERS
    
                _bench_ready_for_retreat = False
                for bp in my_state.bench:
                    if bp is None:
                        continue
                    _brr_e = len(bp.energies)
                    _brr_eff = _brr_e * _grass_mult()
                    if bp.id == Hydrapple_ex and _brr_eff >= 2:
                        _bench_ready_for_retreat = True
                        break
                    elif bp.id == Dipplin and _brr_e >= 1:
                        _bench_ready_for_retreat = True
                        break
                    elif bp.id == Teal_Mask_Ogerpon_ex and _brr_eff >= 3:
                        _bench_ready_for_retreat = True
                        break
                    elif bp.id == Tapu_Bulu and _brr_eff >= 4:
                        _bench_ready_for_retreat = True
                        break
                    elif bp.id == Fezandipiti_ex and _brr_eff >= 3:
                        _bench_ready_for_retreat = True
                        break
                    elif bp.id == Meganium and _brr_eff >= 4:
                        _bench_ready_for_retreat = True
                        break
    
                _BASIC_OR_STAGE1_NONEX = (
                    Applin, Dipplin, Chikorita, Bayleef, Tapu_Bulu, Pinsir)
                _fase58_promo_ready = any(
                    bp is not None and bp.id in _BASIC_OR_STAGE1_NONEX
                    for bp in my_state.bench)
    
                _meg_only_attacker_retreat = False
                if ((ESTADO.op_is_crustle_deck or ESTADO.op_is_cornerstone_deck) and
                        can_switch and active.id != Meganium):
    
                    _opa_km = (op_state.active[0]
                               if (op_state.active and op_state.active[0] is not None)
                               else None)
                    _opa_km_hp = (_opa_km.hp or 0) if _opa_km is not None else 0
    
                    def _meg_blk_ko(_p):
                        # ¿este atacante no-ex noquea al activo rival (Crustle) este turno?
                        # len(energies) YA es la energia EFECTIVA (Wild Growth ya
                        # aplicado en la observacion) -> Solar Beam (140) con 4.
                        if _p is None or _opa_km is None or _opa_km_hp <= 0:
                            return False
                        _e = len(_p.energies)
                        _eff = _e * _grass_mult()
                        _base = 0
                        if _p.id == Dipplin and _e >= 1:
                            _base = 20 * bench_count
                        elif _p.id == Tapu_Bulu and _eff >= 4:
                            _base = 220
                        elif _p.id == Pinsir and _eff >= 2:
                            _base = 100
                        elif _p.id == Meganium and _eff >= 4:
                            _base = 140
                        if _base <= 0:
                            return False
                        return _our_effective_damage(
                            _p, _opa_km, _base, ESTADO.meganium_in_play,
                            neutralization_zone_active) >= _opa_km_hp
    
                    _other_atk_ready_meg = any(
                        _mp_meg is not None and _mp_meg.id != Meganium and
                        _meg_blk_ko(_mp_meg)
                        for _mp_meg in ([active] + list(my_state.bench)))
    
                    _meganium_bench_ready_meg = any(
                        bp is not None and bp.id == Meganium and _meg_blk_ko(bp)
                        for bp in my_state.bench)
    
                    _act_ko_rival_meg = False
                    if (can_attack and op_state.active and
                            op_state.active[0] is not None):
                        _opa_meg = op_state.active[0]
                        _opa_meg_e = len(_opa_meg.energies)
                        _act_base_meg = 0
                        if active.id == Teal_Mask_Ogerpon_ex:
                            _act_base_meg = 30 + 30 * (len(active.energies) + _opa_meg_e)
                        elif active.id == Hydrapple_ex:
                            _act_base_meg = 30 + 30 * total_grass
                        if _act_base_meg > 0:
                            _act_dmg_meg = _our_effective_damage(
                                active, _opa_meg, _act_base_meg,
                                ESTADO.meganium_in_play, neutralization_zone_active)
                            if _act_dmg_meg >= (_opa_meg.hp or 0) and _act_dmg_meg > 0:
                                _act_ko_rival_meg = True
                    if (not _other_atk_ready_meg and _meganium_bench_ready_meg and
                            not _act_ko_rival_meg):
                        _meg_only_attacker_retreat = True
    
                if _meg_only_attacker_retreat:
    
                    score = 3500
    
                elif ((ESTADO.op_is_crustle_deck or ESTADO.op_is_cornerstone_deck) and
                      active.id == Teal_Mask_Ogerpon_ex):
                    if not can_switch:
                        score = SCORE_VETO
                    else:
    
                        _tmo_ko_rival = False
                        _opa_tmo = (op_state.active[0]
                                    if (op_state.active and op_state.active[0] is not None)
                                    else None)
                        if can_attack and _opa_tmo is not None:
                            _opa_tmo_e = len(_opa_tmo.energies)
                            _tmo_base = 30 + 30 * (len(active.energies) + _opa_tmo_e)
                            _tmo_dmg = _our_effective_damage(
                                active, _opa_tmo, _tmo_base,
                                ESTADO.meganium_in_play, neutralization_zone_active)
                            if _tmo_dmg >= (_opa_tmo.hp or 0) and _tmo_dmg > 0:
                                _tmo_ko_rival = True
                        if _tmo_ko_rival:
                            score = SCORE_VETO
                        else:
    
                            _tmo_attacker_ready = False
                            for bp in my_state.bench:
                                if bp is None:
                                    continue
                                _bp_e = len(bp.energies)
                                _bp_eff = _bp_e * _grass_mult()
                                if bp.id == Pinsir and _bp_eff >= 2:
                                    _tmo_attacker_ready = True
                                    break
                                elif bp.id == Tapu_Bulu and _bp_eff >= 4:
                                    _tmo_attacker_ready = True
                                    break
                                elif (ESTADO.op_is_crustle_deck and
                                      bp.id == Dipplin and _bp_e >= 1):
                                    _tmo_attacker_ready = True
                                    break
                                elif (ESTADO.op_is_crustle_deck and
                                      bp.id == Meganium and _bp_eff >= 4):
                                    _tmo_attacker_ready = True
                                    break
                                elif (not op_has_ex_immune_active and
                                      bp.id == Hydrapple_ex and _bp_eff >= 2):
                                    _tmo_attacker_ready = True
                                    break
                                elif (not op_has_ex_immune_active and
                                      bp.id == Teal_Mask_Ogerpon_ex and _bp_eff >= 3):
                                    _tmo_attacker_ready = True
                                    break
                            if _tmo_attacker_ready:
                                score = 3400
                            else:
                                score = SCORE_VETO
                elif (not can_attack) and can_switch and _bench_ready_for_retreat:
    
                    # GUARDA "no cambiar un ex por un cuerpo peor" (user,
                    # registro_009 vs Archaludon ex): retirar un ex del ACTIVO
                    # solo compensa si el cuerpo que sube (a) NOQUEA al activo
                    # rival -- cobra premio YA, sea de 1 o de 2 -- o (b) aguanta
                    # AL MENOS lo mismo que el que baja (pivote a un muro igual
                    # o mayor). Cambiar un Hydrapple ex de 330 PV por un Teal
                    # Mask Ogerpon ex de 210 "porque el segundo puede atacar"
                    # tira el muro y pone delante un cuerpo de 2 premios mas
                    # facil de derrotar: el rival cobra lo mismo con menos
                    # esfuerzo. Y si el que sube ni remata ni aguanta, el chip
                    # no paga el cambio. Deck-agnostica: mira vida, KO efectivo
                    # y coste de retirada, no cartas concretas.
                    _xx_act = active
                    _xx_op = _active_of(op_state)
                    _xx_act_hp = (_xx_act.hp or 0) if _xx_act is not None else 0
                    _xx_vale = False
                    if _xx_act is None or _xx_act.id not in OUR_EX_IDS:
                        _xx_vale = True   # el activo no es un ex: regla no aplica
                    else:
                        for _xx_bp in (my_state.bench or []):
                            if _xx_bp is None:
                                continue
                            _xx_req = ESTADO.ATTACK_ENERGY_REQ.get(_xx_bp.id)
                            if _xx_req is None:
                                continue
                            _xx_e = len(_xx_bp.energies)
                            if _xx_e * _grass_mult() < _xx_req:
                                continue  # no es un atacante listo
                            if (_xx_bp.hp or 0) >= _xx_act_hp:
                                _xx_vale = True   # pivote a un muro igual o mayor
                                break
                            if _xx_op is not None:
                                _xx_base = _attacker_base_damage(
                                    _xx_bp.id, _xx_op, _xx_e * _grass_mult(),
                                    grass_scale=max(
                                        0, total_grass - _retreat_grass_units(
                                            RETREAT_COST.get(_xx_act.id, 1))),
                                    teal_self_energy=_xx_e,
                                    bench_count=bench_count)
                                if _xx_base > 0 and _our_effective_damage(
                                        _xx_bp, _xx_op, _xx_base,
                                        ESTADO.meganium_in_play,
                                        neutralization_zone_active) >= (
                                            _xx_op.hp or 0):
                                    _xx_vale = True
                                    break
                    score = 3200 if _xx_vale else SCORE_VETO
    
                elif (ESTADO.op_is_cornerstone_deck and can_switch and
                      active.id in OUR_ABILITY_IDS and
                      op_state.active and op_state.active[0] is not None and
                      op_state.active[0].id == Cornerstone_Mask_Ogerpon_ex):
                    _cs_tapu_ready = any(
                        bp is not None and bp.id == Tapu_Bulu and
                        len(bp.energies) >= 4
                        for bp in my_state.bench)
                    if _cs_tapu_ready:
                        score = 3400
                    else:
                        score = SCORE_VETO
    
                elif (ESTADO.op_is_crustle_deck and can_switch and
                      active.id in OUR_EX_IDS):
    
                    _cr_op_act = op_state.active[0] if op_state.active else None
                    _cr_ex_can_ko = False
                    if can_attack and _cr_op_act is not None:
                        _cr_op_e = len(_cr_op_act.energies)
                        _cr_base = 0
                        if active.id == Teal_Mask_Ogerpon_ex:
                            _cr_base = 30 + 30 * (len(active.energies) + _cr_op_e)
                        elif active.id == Hydrapple_ex:
                            _cr_base = 30 + 30 * total_grass
                        if _cr_base > 0:
                            _cr_dmg = _our_effective_damage(
                                active, _cr_op_act, _cr_base,
                                ESTADO.meganium_in_play, neutralization_zone_active)
                            if _cr_dmg >= (_cr_op_act.hp or 0) and _cr_dmg > 0:
                                _cr_ex_can_ko = True
                    if _cr_ex_can_ko:
                        score = SCORE_VETO
                    else:
                        _crustle_bench_atk = False
                        for bp in my_state.bench:
                            if bp is None:
                                continue
                            _ce_eff = len(bp.energies) * _grass_mult()
                            if ((bp.id == Tapu_Bulu and _ce_eff >= 4) or
                                    (bp.id == Dipplin and len(bp.energies) >= 1) or
                                    (bp.id == Meganium and _ce_eff >= 4)):
                                _crustle_bench_atk = True
                                break
                        if _crustle_bench_atk:
                            score = 3400
                        else:
                            score = SCORE_VETO
    
                elif (active.id in OUR_EX_IDS and (not can_attack) and can_switch
                      and estimated_op_damage >= (active.hp or 0)
                      and _fase58_promo_ready):
                    score = 3300
    
                elif active.id == Fezandipiti_ex and ESTADO.plan.attacker == 0:
                    score = SCORE_VETO
    
                elif (active.id == Fezandipiti_ex and
                      state.turn == 2 and not ESTADO.we_go_first):
                    score = SCORE_VETO
    
                elif active.id in NON_ATTACKERS:
    
                    _has_bench_attacker = False
                    for bp in my_state.bench:
                        if bp is not None and bp.id in STRATEGIC_ATTACKERS:
                            _has_bench_attacker = True
                            break
    
                    _bench_has_only_non_attackers = True
                    for bp in my_state.bench:
                        if bp is not None and bp.id in STRATEGIC_ATTACKERS:
                            _bench_has_only_non_attackers = False
                            break
    
                    _HAND_PLAYABLE_ATTACKERS = (Tapu_Bulu, Teal_Mask_Ogerpon_ex)
                    _has_attacker_in_hand = False
                    if bench_count < 5:
                        for _hpa_id in _HAND_PLAYABLE_ATTACKERS:
                            if (hand_counts.get(_hpa_id, 0) >= 1 and
                                    field_counts.get(_hpa_id, 0) == 0):
                                _has_attacker_in_hand = True
                                break
    
                        if (not _has_attacker_in_hand and
                                hand_counts.get(Fezandipiti_ex, 0) >= 1 and
                                field_counts.get(Fezandipiti_ex, 0) == 0 and
                                state.turn > 1):
                            _has_attacker_in_hand = True
    
                    # ¿Hay en la banca un atacante REALMENTE listo para atacar
                    # este turno? No basta con que exista un atacante por
                    # identidad (p.ej. un Teal ex): debe tener la energia
                    # efectiva suficiente (Wild Growth incluido), o poder
                    # completarla adjuntando UNA energia de Planta este turno.
                    # Sin esta comprobacion se retiraba el activo para subir a
                    # un atacante SIN cargar, que tampoco podia atacar,
                    # desperdiciando el turno y el coste de retirada.
                    _grass_attach_this_turn = (
                        hand_counts.get(Basic_Grass_Energy, 0) >= 1
                        and not state.energyAttached)
                    _bench_attacker_ready = False
                    for bp in my_state.bench:
                        if bp is None or bp.id not in STRATEGIC_ATTACKERS:
                            continue
                        _bar_req = ESTADO.ATTACK_ENERGY_REQ.get(bp.id)
                        if _bar_req is None:
                            continue
                        _bar_eff = len(bp.energies) * _grass_mult()
                        if _bar_eff >= _bar_req:
                            _bench_attacker_ready = True
                            break
                        if (_grass_attach_this_turn
                                and _bar_eff + _grass_attach_unit() >= _bar_req):
                            _bench_attacker_ready = True
                            break
    
                    # Pivote de rescate: si el activo es una pre-evolucion FRAGIL
                    # (Chikorita/Bayleef) CONDENADA este turno (probable KO) y en la
                    # banca hay un cuerpo que SOBREVIVE al mejor golpe rival, conviene
                    # RETIRAR aunque el atacante de banca no pueda atacar todavia:
                    # resguardamos la pre-evolucion (se evoluciona luego en banca),
                    # subimos un muro que aguanta y refrescamos la mano (Lillie's se
                    # habilita tras evolucionar). Mantener el cuerpo de poca vida al
                    # frente solo lo entrega gratis y frena la linea de evolucion.
                    _fragile_doomed_pivot = False
                    if (can_switch and active.id in (Chikorita, Bayleef)
                            and (active_ko_likely
                                 or estimated_op_damage >= (active.hp or 0))):
                        for _fdp_bp in my_state.bench:
                            if _fdp_bp is None:
                                continue
                            if (_fdp_bp.hp or 0) > _op_best_damage_vs(_fdp_bp):
                                _fragile_doomed_pivot = True
                                break
    
                    # Pivote de LINEA EVOLUTIVA (user, registro_003 paso 29 vs
                    # Dragapult, PERDIDA): el activo es un Chikorita con Bayleef
                    # en la mano. El scorer de EVOLVE ya VETA evolucionar en el
                    # ACTIVO cuando la pre-evolucion puede pagar su retirada
                    # ("conviene RETIRARLO primero y evolucionarlo ya en la
                    # banca", ver la rama Bayleef/_is_active), pero aqui el
                    # retiro quedaba vetado porque el atacante de banca (Tapu
                    # Bulu) aun no tenia energia, asi que el agente se quedaba
                    # con el Chikorita arriba y gastaba el turno en Growl (0 de
                    # dano) con la linea de Meganium muerta en la mano. Retirar
                    # es la jugada: sube un cuerpo con mas vida y el Chikorita
                    # evoluciona en la BANCA -- con Forest of Vitality en juego,
                    # incluso la cadena Chikorita->Bayleef->Meganium entera este
                    # mismo turno. Ademas Wild Growth de Meganium DUPLICA cada
                    # Planta: baja de 4 a 2 las Plantas FISICAS que Tapu Bulu
                    # necesita para Wood Hammer. Solo si la pre-evolucion puede
                    # evolucionar de verdad este turno (lleva en juego desde el
                    # inicio del turno, o Forest lo permite aunque acabe de
                    # jugarse) y hay un cuerpo en banca al que promover.
                    _evo_line_bench_pivot = (
                        can_switch
                        and active.id == Chikorita
                        and hand_counts.get(Bayleef, 0) >= 1
                        and bench_count >= 1
                        and not _active_can_ko_now
                        and (ESTADO.forest_in_play
                             or not getattr(active, 'appearThisTurn', False)))
    
                    if active.id in (Chikorita, Bayleef, Meganium):
    
                        # Regla (user, log 86607718 turno 2, vs Crustle, PERDIMOS):
                        # vs Crustle, si el ACTIVO es un Chikorita y NO hay ningun
                        # Chikorita en la banca, la prioridad es RETIRARLO (para
                        # evolucionarlo a Meganium en banca y subir un cuerpo util),
                        # AUNQUE en la banca no haya todavia un atacante LISTO (el
                        # veto de "atacante de banca sin energia" de abajo lo
                        # bloqueaba). Chikorita activo es un lastre que no daña al
                        # muro. Requiere poder retirar (can_switch: ya cargamos 1
                        # Planta al Chikorita, ver energy_score) y tener un cuerpo en
                        # banca al que promover. La promocion prefiere un atacante y,
                        # si no hay, un ex (Ogerpon ex primero, ver _best_promote).
                        if (ESTADO.op_is_crustle_deck and active.id == Chikorita
                                and field_counts.get(Chikorita, 0) <= 1
                                and bench_count >= 1):
                            score = 6500
                        elif _has_bench_attacker and _bench_attacker_ready:
                            score = 6000
                        elif _fragile_doomed_pivot:
                            # Activo fragil condenado: retirar para subir un cuerpo
                            # que sobrevive y resguardar la pre-evolucion, aunque el
                            # atacante de banca no pueda atacar aun. Gana sobre atacar
                            # con un cuerpo que morira el proximo turno.
                            score = 5800
                        elif _evo_line_bench_pivot:
                            # Chikorita activo con Bayleef en mano: retirar para
                            # montar la linea de Meganium en la BANCA (ver el
                            # comentario del flag). Va por debajo de los pivotes
                            # de rescate pero POR ENCIMA de los dos vetos de
                            # "atacante de banca sin cargar", que son los que
                            # dejaban al Chikorita atacando por chip.
                            score = 5700
                        elif _has_bench_attacker and not _bench_attacker_ready:
                            # Hay un atacante en banca pero SIN energia para
                            # atacar este turno: retirar ahora solo subiria un
                            # cuerpo que tampoco ataca. Mejor mantener el activo
                            # y seguir cargando al atacante de la banca.
                            score = SCORE_VETO
                        elif _bench_has_only_non_attackers and _has_attacker_in_hand:
    
                            score = SCORE_VETO
                        else:
                            score = 5500
                    elif active.id == Meowth_ex:
    
                        _ATK_REQS_RETREAT = {
                            Hydrapple_ex: 2, Dipplin: 1, Teal_Mask_Ogerpon_ex: 3,
                            Tapu_Bulu: 4, Fezandipiti_ex: 3,
                        }
                        _has_ready_bench_for_meowth = False
                        for bp in my_state.bench:
                            if bp is None or bp.id not in _ATK_REQS_RETREAT:
                                continue
                            _bp_eff_m = len(bp.energies) * _grass_mult()
                            if _bp_eff_m >= _ATK_REQS_RETREAT[bp.id]:
                                _has_ready_bench_for_meowth = True
                                break
    
                        _meowth_data_r = card_table.get(Meowth_ex)
                        _op_act_r = op_state.active[0] if op_state.active else None
                        _op_act_data_r = card_table.get(_op_act_r.id) if _op_act_r is not None else None
                        _meowth_weak_to_op = (
                            _meowth_data_r is not None and getattr(_meowth_data_r, 'weakness', None) is not None and
                            _op_act_data_r is not None and
                            getattr(_op_act_data_r, 'energyType', None) == _meowth_data_r.weakness)
                        _safe_chargeable_body = False
                        if _meowth_weak_to_op:
                            for bp in my_state.bench:
                                if bp is None:
                                    continue
                                _bp_data_r = card_table.get(bp.id)
                                _bp_weak_r = (
                                    _bp_data_r is not None and getattr(_bp_data_r, 'weakness', None) is not None and
                                    _op_act_data_r is not None and
                                    getattr(_op_act_data_r, 'energyType', None) == _bp_data_r.weakness)
                                if _bp_weak_r:
                                    continue
                                _bp_e_r = len(bp.energies)
                                _bp_eff_r = _bp_e_r * _grass_mult()
    
                                if bp.id == Teal_Mask_Ogerpon_ex and _bp_eff_r >= 2:
                                    _safe_chargeable_body = True
                                    break
                                elif bp.id == Hydrapple_ex and _bp_eff_r >= 2:
                                    _safe_chargeable_body = True
                                    break
                                elif bp.id == Dipplin and _bp_e_r >= 1:
                                    _safe_chargeable_body = True
                                    break
                                elif bp.id == Tapu_Bulu and _bp_eff_r >= 4:
                                    _safe_chargeable_body = True
                                    break
                                elif bp.id == Meganium and _bp_eff_r >= 4:
                                    _safe_chargeable_body = True
                                    break
    
                        if _meowth_weak_to_op and _safe_chargeable_body:
                            score = 6000
                        elif _has_ready_bench_for_meowth:
                            score = 5000
                        else:
                            score = SCORE_VETO
                    elif _has_bench_attacker:
                        score = 3000
                    elif _bench_has_only_non_attackers and _has_attacker_in_hand:
    
                        score = SCORE_VETO
                    else:
                        score = 2500
    
                elif active.id in STRATEGIC_ATTACKERS:
    
                    # Listo-para-atacar via energia efectiva (fuente unica:
                    # ATTACK_ENERGY_REQ). El branch ya garantiza pertenencia a
                    # STRATEGIC_ATTACKERS (= MAIN_ATTACKERS).
                    _active_can_attack = _can_attack_eff(active.id, active_energy)
    
                    if not _active_can_attack:
    
                        _has_ready_bench = False
                        for bp in my_state.bench:
                            if bp is None:
                                continue
                            # Cuenta cualquier atacante principal listo en banca
                            # (incluye Meganium, antes omitido).
                            if (bp.id in MAIN_ATTACKERS
                                    and _can_attack_eff(bp.id, len(bp.energies))):
                                _has_ready_bench = True
                                break
    
                        if _has_ready_bench:
                            score = 2500
                        else:
                            score = SCORE_VETO
    
                    elif (can_switch
                          and estimated_op_damage > 0
                          and estimated_op_damage >= (active.hp or 0)
                          and not (ESTADO.plan.remain_hp is not None
                                   and ESTADO.plan.remain_hp <= 0)):
                        # RETIRO DEFENSIVO: nuestro atacante activo PUEDE atacar
                        # pero sera noqueado el proximo turno (dano estimado del
                        # rival >= sus HP) y atacar con el no noquea al activo
                        # rival. Si en la banca hay un atacante MAS resistente
                        # que sobrevive al ataque rival y puede atacar tras subir,
                        # retirarse a el evita la derrota (muro que ademas
                        # presiona). Sin esto el codigo asume "si puedo atacar,
                        # ataco" y deja morir al activo condenado.
                        _def_retreat_target = False
                        for bp in my_state.bench:
                            if bp is None or bp.id not in MAIN_ATTACKERS:
                                continue
                            if (bp.hp or 0) <= _op_best_damage_vs(bp):
                                continue  # tambien seria noqueado el proximo turno
                            if _can_attack_eff(bp.id, len(bp.energies)):
                                _def_retreat_target = True
                                break
                        if _def_retreat_target:
                            score = 5600
                        else:
                            score = SCORE_VETO
    
                    elif (active.id in (Hydrapple_ex, Tapu_Bulu) and
                          op_state.active and op_state.active[0] is not None and
                          op_state.active[0].id == Drednaw):
                        _has_shell_bypass_bench = False
                        for bp in my_state.bench:
                            if bp is None:
                                continue
                            _bp_energy = len(bp.energies)
                            _bp_effective = _bp_energy * _grass_mult()
                            if bp.id == Meganium and _bp_effective >= 4:
                                _has_shell_bypass_bench = True
                                break
                            elif bp.id == Dipplin and _bp_energy >= 1:
                                _has_shell_bypass_bench = True
                                break
                        if _has_shell_bypass_bench:
                            score = 5500
                        else:
                            score = SCORE_VETO
    
                    elif (active.id in OUR_EX_IDS and
                          op_state.active and op_state.active[0] is not None and
                          op_state.active[0].id == Sylveon):
                        _has_nonex_bench = False
                        for bp in my_state.bench:
                            if bp is None:
                                continue
                            _bp_energy = len(bp.energies)
                            _bp_effective = _bp_energy * _grass_mult()
                            if bp.id == Tapu_Bulu and _bp_effective >= 4:
                                _has_nonex_bench = True
                                break
                            elif bp.id == Meganium and _bp_effective >= 4:
                                _has_nonex_bench = True
                                break
                            elif bp.id == Dipplin and _bp_energy >= 1:
                                _has_nonex_bench = True
                                break
                        if _has_nonex_bench:
                            score = 5500
                        else:
                            score = SCORE_VETO
    
                    elif (neutralization_zone_active and active.id in OUR_EX_IDS):
                        _has_nz_bypass_bench = False
                        for bp in my_state.bench:
                            if bp is None:
                                continue
                            _bp_energy = len(bp.energies)
                            _bp_effective = _bp_energy * _grass_mult()
                            if bp.id == Tapu_Bulu and _bp_effective >= 4:
                                _has_nz_bypass_bench = True
                                break
                            elif bp.id == Meganium and _bp_effective >= 4:
                                _has_nz_bypass_bench = True
                                break
                            elif bp.id == Dipplin and _bp_energy >= 1:
                                _has_nz_bypass_bench = True
                                break
                            elif bp.id == Pinsir and _bp_effective >= 2:
                                _has_nz_bypass_bench = True
                                break
    
                        _op_act = op_state.active[0] if op_state.active else None
                        _op_act_has_rb = False
                        if _op_act is not None:
                            _op_act_data = card_table[_op_act.id]
                            _op_act_has_rb = (_op_act_data.ex or _op_act_data.megaEx)
                        if _has_nz_bypass_bench and not _op_act_has_rb:
                            score = 5000
                        else:
                            score = SCORE_VETO
                    else:
                        score = SCORE_VETO
                else:
                    score = SCORE_VETO
            else:
                score = SCORE_VETO
    
            # Cancelar la retirada si solo reubicaria al mismo Pokemon (misma
            # especie) al activo: es inutil y malgasta la energia del coste de
            # retirada (user, log 86510119 paso 26). Ver `_same_species_retreat`.
            # EXCEPCION (user, registro_005 vs Comfey): si el activo esta CONFUNDIDO
            # (Brambleghast), retirarlo para promover un cuerpo de la MISMA especie
            # SI aporta: el nuevo activo NO esta confundido y puede atacar sin la
            # moneda. Con dos Teal Mask Ogerpon ex (el plan del matchup) este es el
            # caso normal, asi que no se veta la retirada de escape de confusion.
            if (_same_species_retreat and score > 0 and not _conf_should_retreat
                    and not _suicide_swap_win_promote):
                score = SCORE_VETO
    
            # Pivote vs Alakazam (user, registro_010 paso 127): retirar el ex
            # activo para promover un cuerpo de 1 premio (Meganium/Tapu Bulu) que
            # NOQUEA al activo rival (ver `_alakazam_pivot_1prize`). Debe SUPERAR
            # al ataque del ex de 2 premios (score ~1100) para que el motor retire
            # en vez de atacar con el ex; sigue por debajo del umbral de
            # "Supporter antes de retirar" (2000) para respetar ese orden.
            if _alakazam_pivot_1prize:
                score = max(score, 6000)
    
            # Regla (user, registro 004 paso 53 vs Archaludon ex, GANADA):
            # SIEMPRE jugar el Supporter (Dawn / Lillie's / Lana's Aid) ANTES de
            # retirar. Retirar primero desaprovecha lo que el Supporter aporta al
            # resto del turno (p.ej. Dawn busca la linea Applin -> Dipplin ->
            # Hydrapple ex que se evoluciona con Forest ESTE mismo turno, y solo
            # despues conviene retirar el Fezandipiti ex y promover al Hydrapple
            # ex). El retiro NO lo bloquea jugar el Supporter (sigue disponible
            # despues), asi que se POSPONE: se rebaja su score por debajo de la
            # jugada del Supporter (>=2400) para que el motor elija primero el
            # Supporter y re-evalue el retiro en la siguiente decision.
            # EXCEPCION: el relevo del remate suicida CIERRA la partida este turno
            # (user, registro_016 paso 184). No hay "resto del turno" al que el
            # Supporter pueda aportar nada, y posponer el retiro es justo lo que
            # deja al agente atacando con el suicida y firmando el empate.
            if (score > 2000 and not state.supporterPlayed
                    and not _suicide_swap_win_promote):
                _rt_supp_first = any(
                    hand_counts.get(_sid, 0) >= 1 and _supp_values.get(_sid, 0) > 0
                    for _sid in (Dawn, Lillie_Determination, Lanas_Aid))
                if _rt_supp_first:
                    score = 2000
    
            # Regla anti-Cubchoo (user, registro_004 paso 47/49 vs
            # cornerstone_cubchoo, PERDIDA): el mazo de Cubchoo/Beartic bloquea
            # nuestro activo cada turno -- Snotted Up (506) y Sheer Cold (507)
            # dejan al Defensor "sin poder usar ataques" el turno siguiente --,
            # forzandonos a RETIRAR para atacar con otro cuerpo. Su atacante es
            # debilisimo (no nos noquea), pero como nos obliga a retirarnos una y
            # otra vez, CADA retirada que DESCARTA energia (coste pagado con la
            # energia del activo, sin carta de cambio gratis) sangra el recurso
            # que mas escasea contra este control. Contra ESTE mazo eliminamos la
            # retirada-pivote voluntaria: si retirar solo cambiaria de atacante y
            # gastaria energia, es preferible PASAR y conservarla. El activo NO
            # esta en peligro de KO (Cubchoo pega 10), asi que quedarse no cuesta
            # nada. Salvaguarda `not active_ko_likely`: si el activo SI va a morir
            # (p.ej. Beartic Sheer Cold sobre un cuerpo fragil), se permite la
            # retirada de rescate. La regla se limita a este matchup: contra
            # cualquier otro mazo la retirada-pivote sigue siendo correcta.
            # EXCEPCION: retirada que NOQUEA y no destruye inversion (user,
            # registro_036 paso 146). Las dos reglas del usuario conviven asi:
            #
            #  - registro_004 p47 (PASAR): el activo es un Ogerpon ex con TRES
            #    Plantas fisicas encima. Retirar tira una de esas tres: destruye
            #    energia ya invertida en el tablero, que es justo el recurso que
            #    el control de Cubchoo nos niega. Aunque haya KO detras, se pasa.
            #  - registro_036 p146 (RETIRAR): el activo tiene CERO energia -- no
            #    ataca ni se retira, es peso muerto. La Planta la ponemos nosotros
            #    ESE turno (Teal Dance, que ademas roba) con el unico proposito de
            #    pagar la retirada. No se destruye nada acumulado: se convierte
            #    una carta de la mano en un premio.
            #
            # Discriminante: energia FISICA del activo <= coste de retirada, es
            # decir que no queda excedente que perder. Mas `_bdg_retreat_ko` (el
            # mismo detector de `_attach_enable_retreat_ko`) para exigir que haya
            # KO de verdad y no un pivote pelado.
            _cc_ret_cost_pre = (RETREAT_COST.get(_active_reloc.id, 1)
                                if _active_reloc is not None else 1)
            _cc_cashes_dead_body = (
                _bdg_retreat_ko
                and _active_reloc is not None
                and _physical_energy(
                    len(_active_reloc.energies)) <= _cc_ret_cost_pre)
            # El relevo del remate suicida gana la partida AHORA: conservar
            # energia para turnos futuros no significa nada si no hay futuro.
            #
            # COLISION Cubchoo <-> muro inmune (autopsia cornerstone_cubchoo,
            # jul 2026): `_ex_stuck_promo_ready` -- nuestro activo esta
            # BLOQUEADO por el muro (Cornerstone anula a los cuerpos con
            # Habilidad; Crustle/Sylveon a los ex) y en la banca hay un atacante
            # que SI le pega -- tambien exime. El veto existe para no destruir
            # energia invertida en el tablero, pero la energia de un cuerpo que
            # hace CERO al activo rival no esta invertida: esta muerta, y la
            # retirada es la unica via para convertirla en dano. Medido en 250
            # partidas vs cornerstone_cubchoo: con el muro delante, Tapu Bulu
            # cargado a >=4 en banca y la retirada LEGAL, subiamos a Tapu solo
            # el 13.7% de las veces en las derrotas por premios (36% en las
            # ganadas; vs Crustle -- mismo escenario SIN Cubchoo en el mazo --
            # es el 82.6-100%). El activo era Teal Mask Ogerpon ex en 167 de 169
            # de esos menus y el turno se cerraba ATACANDO por 0 (67 veces).
            if (op_is_cubchoo_deck and score > 0 and not active_ko_likely
                    and not _cubchoo_lock_stuck
                    and not _cc_cashes_dead_body
                    and not _ex_stuck_promo_ready
                    and not _suicide_swap_win_promote
                    and _active_reloc is not None):
                _cc_ret_cost = RETREAT_COST.get(_active_reloc.id, 1)
                _cc_wastes_energy = (
                    not has_switch_card
                    and _cc_ret_cost >= 1
                    and _physical_energy(
                        len(_active_reloc.energies)) >= _cc_ret_cost)
                if _cc_wastes_energy:
                    score = SCORE_VETO
    
        elif o.type == OptionType.ATTACK:
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
    
        elif o.type == OptionType.END:
    
            if can_attack:
                _end_attack_is_risky = (
                    condition_risky_attack and
                    not (ESTADO.plan.remain_hp is not None and ESTADO.plan.remain_hp <= 0))
                if _conf_should_attack or not _end_attack_is_risky:
                    score = SCORE_NEVER
    
        elif o.type == OptionType.SPECIAL_CONDITION:
    
            if context == SelectContext.RECOVER_SPECIAL_CONDITION:
    
                if o.specialConditionType is not None:
                    if o.specialConditionType == SpecialConditionType.PARALYZE:
                        score = 500
                    elif o.specialConditionType == SpecialConditionType.SLEEP:
                        score = 400
                    elif o.specialConditionType == SpecialConditionType.CONFUSE:
                        score = 300
                    elif o.specialConditionType == SpecialConditionType.POISON:
                        score = 200
                    elif o.specialConditionType == SpecialConditionType.BURN:
                        score = 150
            elif context == SelectContext.AFFECT_SPECIAL_CONDITION:
    
                if o.specialConditionType is not None:
                    if o.specialConditionType == SpecialConditionType.PARALYZE:
                        score = 500
                    elif o.specialConditionType == SpecialConditionType.SLEEP:
                        score = 400
                    elif o.specialConditionType == SpecialConditionType.CONFUSE:
                        score = 350
                    elif o.specialConditionType == SpecialConditionType.POISON:
                        score = 200
                    elif o.specialConditionType == SpecialConditionType.BURN:
                        score = 150
        return score
    finally:
        # Arrastre entre iteraciones: corre tambien cuando la cadena sale
        # por el centinela, igual que hacia el `continue`.
            tc._atk = _atk
            tc._b = _b
            tc._bench_attacker_ready = _bench_attacker_ready
            tc._bp = _bp
            tc._bp_e = _bp_e
            tc._bp_eff = _bp_eff
            tc._dc = _dc
            tc._e = _e
            tc._eff = _eff
            tc._energy_in_hand = _energy_in_hand
            tc._has_bench_attacker = _has_bench_attacker
            tc._lillie_protected_once = _lillie_protected_once
            tc._op_act = _op_act
            tc._our_first_turn = _our_first_turn
            tc._sid = _sid
            tc._tb_req = _tb_req
            tc.b = b
            tc.bp = bp
            tc.card = card
            tc.data = data
            tc.energy_count = energy_count
            tc.pid = pid
            tc.pokemon = pokemon


__all__ = ['puntuar_opcion', '_SALTAR']
