"""Puntuacion de las opciones `CARD`.

Rama `o.type == OptionType.CARD` de la cadena de `agent()`, extraida VERBATIM.
Desempaqueta del contexto los 113 campos que lee y devuelve los
10 que reasigna; los demas quedan como estaban, igual que antes.
"""

from cg.api import AreaType, CardType, Pokemon, SelectContext
from ptcg.calculo.carta import get_card, prize_count, prize_count_op
from ptcg.calculo.dano import _attacker_base_damage, _bench_attacker_can_ko, _ko_no_garantizado, _our_effective_damage, _snipe_target_score
from ptcg.calculo.energia import _can_attack_eff, _grass_attach_route_open, _grass_attach_unit, _grass_mult
from ptcg.calculo.tablero import _active_of, _count_hand_play_options
from ptcg.cartas.grupos import GT_FETCH_BONUS
from ptcg.cartas.ids import Applin, Basic_Grass_Energy, Bayleef, Boss_Orders, Bug_Catching_Set, Chikorita, DUNSPARCE_IDS, Dawn, Dipplin, Drednaw, Fezandipiti_ex, Forest_of_Vitality, Grand_Tree, Hydrapple_ex, LANA_SEL_INJUGABLE, LANA_SEL_PLANTA_DEMANDA, LANA_SEL_PLANTA_DESBLOQUEA, LANA_SEL_PLANTA_SOBRANTE, Lanas_Aid, Lillie_Determination, Meganium, Meowth_ex, Night_Stretcher, OUR_ABILITY_IDS, OUR_EX_IDS, Pinsir, Poke_Pad, RETREAT_COST, RIPEN_HEAL_TARGET_SCORE, SCORE_FORBID, SCORE_LOOKAHEAD_PROMOTE_KO, SCORE_LOOKAHEAD_PROMOTE_SAFE, SCORE_NEVER, SCORE_VETO, Sylveon, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball, Unfair_Stamp, Xerosic_Machinations
from ptcg.cartas.lineas import _pokemon_injugable
from ptcg.cartas.puntuacion import MAIN_ATTACKERS, PROMO_DOOMED_PENALTY, PROMO_KO_BONUS, PROMO_MATCH_POINT_VETO, PROMO_PRIZE_PENALTY
from ptcg.cartas.tablas import card_table
from ptcg.decision.boss_orders import _AJUSTES_GUST_ESTORBO, _AJUSTES_GUST_OFENSIVO, _REGLAS_GUST_ESTORBO, _ctx_gust_objetivo
from ptcg.decision.meowth import _CtxMeowthFetch, _MEOWTH_FETCH_SUPPS, _REGLAS_MEOWTH_FETCH
from ptcg.decision.night_stretcher import _REGLAS_NS_APPLIN, _REGLAS_NS_BAYLEEF, _REGLAS_NS_CHIKORITA, _REGLAS_NS_DIPPLIN, _REGLAS_NS_FEZ, _REGLAS_NS_GRASS, _REGLAS_NS_HYDRAPPLE, _REGLAS_NS_MEGANIUM, _REGLAS_NS_MEOWTH, _REGLAS_NS_OGERPON, _REGLAS_NS_PINSIR, _REGLAS_NS_TAPU, _ctx_ns_fetch, _ns_motor_fez_vivo, _ns_motor_meowth_vivo
from ptcg.decision.poke_pad import _CtxPPFetch, _REGLAS_PP_FETCH
from ptcg.decision.ultra_ball import _AJUSTES_UB_HYDRAPPLE, _CtxUBFetch, _REGLAS_UB_APPLIN, _REGLAS_UB_BAYLEEF, _REGLAS_UB_CHIKORITA, _REGLAS_UB_DIPPLIN, _REGLAS_UB_FEZ, _REGLAS_UB_HYDRAPPLE, _REGLAS_UB_MEGANIUM, _REGLAS_UB_MEOWTH, _REGLAS_UB_OGERPON, _REGLAS_UB_PINSIR, _REGLAS_UB_TAPU, _contra_estadio_urgente, _ctx_ub_fetch_hydrapple, _ctx_ub_fetch_meowth
from ptcg.estado.agente import ESTADO
from ptcg.estado.claves import ESTADO_MAZO, ESTADO_PREMIO
from ptcg.motor.reglas import _resolver_con_traza


def puntuar(tc, o, score):
    """Devuelve el puntaje de `o`. Puede devolver `_SALTAR`."""
    _SALTAR = tc._SALTAR
    _TABLA_BCS_FETCH = tc._TABLA_BCS_FETCH
    _TABLA_DAWN_FETCH = tc._TABLA_DAWN_FETCH
    _active_cant_attack_this_turn = tc._active_cant_attack_this_turn
    _active_needs_energy = tc._active_needs_energy
    _active_ready_attacker = tc._active_ready_attacker
    _best_promote_card = tc._best_promote_card
    _best_promote_key = tc._best_promote_key
    _best_supp_in_hand_val = tc._best_supp_in_hand_val
    _best_supp_in_mazo_val = tc._best_supp_in_mazo_val
    _bp = tc._bp
    _cm_use_ex = tc._cm_use_ex
    _conf_is_matchup_attacker = tc._conf_is_matchup_attacker
    _dc = tc._dc
    _deny_evo_via_boss = tc._deny_evo_via_boss
    _descuadre_matchup = tc._descuadre_matchup
    _dragapult_no_tapu = tc._dragapult_no_tapu
    _evo_huerfanos = tc._evo_huerfanos
    _evo_necesarios = tc._evo_necesarios
    _festival_lead_hostil = tc._festival_lead_hostil
    _forced_ko_promote = tc._forced_ko_promote
    _grass_anywhere_enables_syrup_ko = tc._grass_anywhere_enables_syrup_ko
    _grass_enables_promote_ko = tc._grass_enables_promote_ko
    _gt_plan = tc._gt_plan
    _gt_planes_turno = tc._gt_planes_turno
    _gt_quiere_basico = tc._gt_quiere_basico
    _gt_ranking_basicos = tc._gt_ranking_basicos
    _gt_score_seleccion = tc._gt_score_seleccion
    _gust_2prize_via_boss = tc._gust_2prize_via_boss
    _has_bench_attacker = tc._has_bench_attacker
    _ko_prefer_basic_general = tc._ko_prefer_basic_general
    _lana_orden_planta = tc._lana_orden_planta
    _lana_plan = tc._lana_plan
    _ld_lillie_ofrecida = tc._ld_lillie_ofrecida
    _lillie_protected_once = tc._lillie_protected_once
    _lucario_ko_prefer_basic = tc._lucario_ko_prefer_basic
    _lucario_sac_context = tc._lucario_sac_context
    _mega_line_active = tc._mega_line_active
    _meowth_devel_lillie = tc._meowth_devel_lillie
    _meowth_ld_free = tc._meowth_ld_free
    _op_best_damage_vs = tc._op_best_damage_vs
    _op_counter_threat_vs = tc._op_counter_threat_vs
    _our_first_action_turn = tc._our_first_action_turn
    _promo_kos_op = tc._promo_kos_op
    _promo_min_prize = tc._promo_min_prize
    _promo_op_act = tc._promo_op_act
    _promo_survives = tc._promo_survives
    _promo_survivors = tc._promo_survivors
    _promote_setup_ko_attacker = tc._promote_setup_ko_attacker
    _refresh_promote_prefer_basic = tc._refresh_promote_prefer_basic
    _ripen_heal_serial = tc._ripen_heal_serial
    _sel_active_cant_attack = tc._sel_active_cant_attack
    _self_ko_by_own_attack = tc._self_ko_by_own_attack
    _supp_values = tc._supp_values
    _tapu_sac_priority = tc._tapu_sac_priority
    _tb_req = tc._tb_req
    _teal_wall_pivot = tc._teal_wall_pivot
    _ub_meowth_para_manana = tc._ub_meowth_para_manana
    _win_via_boss_gust = tc._win_via_boss_gust
    b = tc.b
    bench_count = tc.bench_count
    bp = tc.bp
    budew_on_op_field = tc.budew_on_op_field
    card = tc.card
    context = tc.context
    ctx = tc.ctx
    discard_counts = tc.discard_counts
    energy_count = tc.energy_count
    energy_score = tc.energy_score
    estimated_op_damage = tc.estimated_op_damage
    field_counts = tc.field_counts
    hand_counts = tc.hand_counts
    has_condition = tc.has_condition
    has_hydrapple = tc.has_hydrapple
    is_confused = tc.is_confused
    itchy_pollen_active = tc.itchy_pollen_active
    meowth_ability_lock = tc.meowth_ability_lock
    my_index = tc.my_index
    my_prize = tc.my_prize
    my_state = tc.my_state
    neutralization_zone_active = tc.neutralization_zone_active
    obs = tc.obs
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
    op_has_typhlosion = tc.op_has_typhlosion
    op_is_aggro_deck = tc.op_is_aggro_deck
    op_is_alakazam_deck = tc.op_is_alakazam_deck
    op_is_comfey_deck = tc.op_is_comfey_deck
    op_is_control_deck = tc.op_is_control_deck
    op_is_cubchoo_deck = tc.op_is_cubchoo_deck
    op_is_dragapult_dusknoir = tc.op_is_dragapult_dusknoir
    op_is_fire_deck = tc.op_is_fire_deck
    op_is_lucario_deck = tc.op_is_lucario_deck
    op_is_sylveon_deck = tc.op_is_sylveon_deck
    op_prize = tc.op_prize
    op_state = tc.op_state
    pid = tc.pid
    scores = tc.scores
    select = tc.select
    state = tc.state
    total_grass = tc.total_grass
    watchtower_in_play = tc.watchtower_in_play

    try:
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
        return score
    finally:
        tc._bp = _bp
        tc._dc = _dc
        tc._has_bench_attacker = _has_bench_attacker
        tc._lillie_protected_once = _lillie_protected_once
        tc._tb_req = _tb_req
        tc.b = b
        tc.bp = bp
        tc.card = card
        tc.energy_count = energy_count
        tc.pid = pid


__all__ = ['puntuar']
