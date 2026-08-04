"""Puntuacion de las opciones `PLAY`.

Rama `o.type == OptionType.PLAY` de la cadena de `agent()`, extraida VERBATIM.
Desempaqueta del contexto los 87 campos que lee y devuelve los
5 que reasigna; los demas quedan como estaban, igual que antes.
"""

from cg.api import AreaType, CardType, EnergyType
from ptcg.calculo.carta import get_card, prize_count
from ptcg.calculo.dano import _powerful_hand_proyectado, _ventana_de_regalo
from ptcg.calculo.energia import _grass_mult
from ptcg.cartas.grupos import GT_PLAY_BASICO_BONUS
from ptcg.cartas.ids import Applin, Basic_Grass_Energy, Bayleef, Boss_Orders, Budew, Bug_Catching_Set, CUBCHOO_ALLOWED_PLAY_IDS, Chikorita, DECK_ITEM_IDS, Dawn, Dipplin, Dragapult_ex, Fezandipiti_ex, Forest_of_Vitality, Grand_Tree, Hydrapple_ex, Lanas_Aid, Lillie_Determination, Meganium, Meowth_ex, Night_Stretcher, OUR_EX_IDS, Pinsir, Poke_Pad, RETREAT_COST, SCORE_DEVELOP_BASE, SCORE_FORBID, SCORE_ITEM_BASE, SCORE_VETO, TAPU_WAIT_FOR_ITEMS_SCORE, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball, Unfair_Stamp, Xerosic_Machinations
from ptcg.cartas.tablas import card_table
from ptcg.decision.bug_catching_set import _score_bug_catching_set_play
from ptcg.decision.disrupcion import _score_unfair_stamp_play, _score_xerosic_play
from ptcg.decision.poke_pad import _score_poke_pad_play
from ptcg.decision.supporters import _score_dawn_play, _score_lanas_aid_play
from ptcg.decision.ultra_ball import _contra_estadio_urgente
from ptcg.estado.agente import ESTADO
from ptcg.estado.claves import ESTADO_MAZO


def puntuar(tc, o, score):
    """Devuelve el puntaje de `o`. Puede devolver `_SALTAR`."""
    _active_already_kos = tc._active_already_kos
    _active_cant_attack_this_turn = tc._active_cant_attack_this_turn
    _active_doomed_real = tc._active_doomed_real
    _active_ready_attacker = tc._active_ready_attacker
    _alk_ld_engine_vivo = tc._alk_ld_engine_vivo
    _ara_act = tc._ara_act
    _bcs_playable_in_hand = tc._bcs_playable_in_hand
    _best_supp_in_hand_val = tc._best_supp_in_hand_val
    _best_supp_in_mazo_id = tc._best_supp_in_mazo_id
    _best_supp_in_mazo_val = tc._best_supp_in_mazo_val
    _deny_evo_via_boss = tc._deny_evo_via_boss
    _descuadre_matchup = tc._descuadre_matchup
    _dragapult_no_tapu = tc._dragapult_no_tapu
    _festival_lead_hostil = tc._festival_lead_hostil
    _gt_planes = tc._gt_planes
    _gt_quiere_basico = tc._gt_quiere_basico
    _gt_raiz_en_juego = tc._gt_raiz_en_juego
    _gt_ranking_basicos = tc._gt_ranking_basicos
    _gt_veta_etapa_ex = tc._gt_veta_etapa_ex
    _gust_2prize_via_boss = tc._gust_2prize_via_boss
    _lucario_other_sac_available = tc._lucario_other_sac_available
    _lucario_riolu_gust = tc._lucario_riolu_gust
    _lucario_sac_pivot = tc._lucario_sac_pivot
    _meowth_antidonk_now = tc._meowth_antidonk_now
    _meowth_devel_lillie = tc._meowth_devel_lillie
    _meowth_fetch_pierde_el_turno = tc._meowth_fetch_pierde_el_turno
    _meowth_fetch_redundante = tc._meowth_fetch_redundante
    _meowth_fetch_ya_en_mano = tc._meowth_fetch_ya_en_mano
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
        return score
    finally:
        tc.b = b
        tc.bp = bp
        tc.card = card
        tc.data = data
        tc.pid = pid


__all__ = ['puntuar']
