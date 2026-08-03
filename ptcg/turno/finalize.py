"""Cierre del turno: orden de jugada por tiers, rescates y eleccion final.

Extraido VERBATIM de la cola de `agent()` (Ola 5). Recibe un `TurnoCtx` y
desempaqueta sus campos a locales con los MISMOS nombres, de modo que el
cuerpo de abajo es exactamente el que estaba en main.py -- sin reescribir una
sola linea de logica. Funciona porque es la COLA de la funcion: nada
posterior lee lo que muta, asi que no hace falta escritura de vuelta.
"""

from cg.api import AreaType, CardType, OptionType, SelectContext
from ptcg.calculo.carta import get_card, prize_count_op
from ptcg.calculo.dano import _attacker_base_damage
from ptcg.calculo.energia import _grass_mult
from ptcg.calculo.rival import _op_juega_crustle
from ptcg.calculo.tablero import _active_of
from ptcg.cartas.ids import Applin, Bayleef, Bug_Catching_Set, Chikorita, Dipplin, Fezandipiti_ex, Forest_of_Vitality, Grand_Tree, Hydrapple_ex, Lillie_Determination, Meganium, Meowth_ex, Pinsir, Poke_Pad, SCORE_USELESS_ATTACK, SCORE_VETO, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball, Xerosic_Machinations
from ptcg.cartas.puntuacion import SCORE_LD_SUPP_COMPROMETIDO, _SUPP_PLAY_IDS
from ptcg.cartas.tablas import attack_table, card_table
from ptcg.decision.ultra_ball import _matchup_permite_bajar, _ub_coste_destruye_carta_mejor
from ptcg.estado.agente import ESTADO
from ptcg.estado.claves import ESTADO_MAZO
from ptcg.motor.depuracion import _debug_log_decision
from ptcg.turno.ctx import TurnoCtx  # noqa: F401


def finalizar(tc):
    """Devuelve los indices de opcion que juega el agente este turno."""
    # Desempaquetado del contexto: mismos nombres que en agent().
    _ability_order_veto = tc._ability_order_veto
    _active_attack_wins_now = tc._active_attack_wins_now
    _attach_cede_a_teal_dance = tc._attach_cede_a_teal_dance
    _b = tc._b
    _dragapult_no_tapu = tc._dragapult_no_tapu
    _item_lock_incoming = tc._item_lock_incoming
    _ld_card = tc._ld_card
    _ld_opt = tc._ld_opt
    _lucario_sac_pivot = tc._lucario_sac_pivot
    _meowth_fetch_id = tc._meowth_fetch_id
    _meowth_fetch_pierde_el_turno = tc._meowth_fetch_pierde_el_turno
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
                ESTADO._poke_pad_target_id = _best_pp_id

    if (_lucario_sac_pivot and select.effect is not None
            and select.effect.id == Poke_Pad and context == SelectContext.TO_HAND):
        # Tapu Bulu SOLO se fuerza como objetivo de Poke Pad cuando de verdad
        # aporta:
        #   * el rival juega un mazo con proteccion a ex (Crustle / Cornerstone
        #     Ogerpon / Sylveon), donde nuestros ex hacen 0 dano, o
        #   * ya tenemos Hydrapple ex cargado + Meganium en juego, que permite
        #     bajar Tapu Bulu y cargarlo al instante (con Meganium 2 energias
        #     cuentan como 4, asi que puede atacar de inmediato).
        # En cualquier otro caso (p.ej. este mismo escenario anti-Lucario) la
        # prioridad la decide el scoring normal: Applin > Chikorita >
        # evoluciones de Pokemon en juego que no tengamos en mano, y Tapu Bulu
        # queda como ultima opcion. Ademas no se trae un Tapu Bulu redundante
        # si ya tenemos uno en mano o en juego.
        _tapu_already = (hand_counts.get(Tapu_Bulu, 0) >= 1 or
                         field_counts.get(Tapu_Bulu, 0) >= 1)
        if (not _tapu_already) and _tapu_sac_priority:
            for _pp_sac_idx, _pp_sac_opt in enumerate(select.option):
                _pp_sac_card = get_card(obs, _pp_sac_opt.area, _pp_sac_opt.index, my_index)
                if _pp_sac_card is not None and _pp_sac_card.id == Tapu_Bulu:
                    if _pp_sac_idx < len(scores):
                        scores[_pp_sac_idx] = 99999
                    ESTADO._poke_pad_target_id = Tapu_Bulu
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
            ESTADO._ub_meowth_pending = True
        if _best_ub_id == Fezandipiti_ex and _best_ub_score > 10:
            # Cadena UB -> Fezandipiti ex -> Flip the Script: la busqueda ya
            # esta pagada, el cuerpo BAJA (ver `_ub_fez_pending`).
            ESTADO._ub_fez_pending = True

    # Cadena Meowth ex -> Last-Ditch Catch -> Supporter: se anota el Supporter
    # elegido para que el resto del turno lo JUEGUE (ver
    # `_ld_supp_comprometido`). Mismo patron que los dos bloques de arriba: el
    # id se saca del argmax de `scores` sobre las opciones del prompt.
    if (select.effect is not None and select.effect.id == Meowth_ex
            and context == SelectContext.TO_HAND and not state.supporterPlayed):
        # Solo con el cuerpo PAGADO este turno: el Last-Ditch de un Meowth ex
        # que ya estaba en juego es gratis y no compromete el turno.
        _ld_serial = getattr(select.effect, 'serial', None)
        _ld_cuerpo_pagado = False
        for _ld_pk in (my_state.bench or []) + (my_state.active or []):
            if (_ld_pk is not None and _ld_pk.id == Meowth_ex
                    and getattr(_ld_pk, 'appearThisTurn', False)
                    and (_ld_serial is None
                         or getattr(_ld_pk, 'serial', None) == _ld_serial)):
                _ld_cuerpo_pagado = True
                break
        if _ld_cuerpo_pagado:
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
                ESTADO._ld_supp_comprometido = _best_ld_id

    _vetoed_stadium_idxs = set()
    _our_first_turn_guard = ((ESTADO.we_go_first and state.turn == 1) or
                             (not ESTADO.we_go_first and state.turn == 2))
    _replace_opp_stadium_ok = (
        (not ESTADO.we_go_first) and state.turn == 2 and
        stadium_id != 0 and stadium_id != Forest_of_Vitality)
    # vs CRUSTLE, SALIENDO SEGUNDOS: el estadio se baja ANTES de la Lillie's
    # (regla del user). Espejo por ORDEN de la regla
    # `t1_segundos_crustle_estadio_antes_de_lillie` de `_REGLAS_FOREST_PLAY`:
    # sin esta excepcion el veto duro de aqui (-99999) aplastaba el score que
    # aquella regla concede y el estadio se iba al mazo con el barajeo de
    # Lillie's. El mazo Crustle no juega estadio (o lleva una o dos copias),
    # asi que el nuestro no corre el riesgo que motiva el veto general.
    _crustle_stadium_before_lillie = (
        (not ESTADO.we_go_first) and state.turn == 2
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
    # ORDEN DE JUGADA (contexto MAIN): imponer la secuencia solicitada
    #   1) estadio  2) Bug Catching Set  3) basicos + evoluciones
    #   4) Poke Pad  5) cargar energia
    # El estadio solo aparece jugable a partir del turno 3 (en el turno 1/2
    # queda vetado mas arriba), asi que su tier solo actua "despues del
    # segundo turno". La energia que habilita un KO/ataque letal ESTE turno
    # conserva prioridad maxima (excepcion). Solo se reordenan estas 5
    # categorias entre si mediante una clave (tier, score): los tiers altos
    # se juegan primero y, dentro del mismo tier, decide el score original.
    # El resto de opciones (Ultra Ball, supporters, ataque, etc.) mantiene su
    # tier 0 y su puntaje. Solo se promueve una opcion jugable (score > 0),
    # de modo que los vetos (-1) se siguen respetando.
    #
    # BUG CATCHING SET ANTES DE BAJAR UN POKEMON (user, log 88166559 paso 6 vs
    # Archaludon, GANADA con error): mirar los 7 de arriba y coger hasta 2
    # Pokemon {G} / Energia Planta cambia QUE cuerpo bajamos y con QUE lo
    # cargamos, asi que decidir el cuerpo ANTES de esa informacion es decidir a
    # ciegas. Alli el agente bajo el Meowth ex (motor Lillie's, 21800) teniendo
    # el BCS (12200) en la mano, y el BCS acabo trayendo un Chikorita -- un
    # cuerpo de UN premio, mejor candidato de banca que un ex de dos -- con el
    # slot ya gastado. Ademas el motor Meowth->Lillie's BARAJA la mano entera:
    # un BCS que siga en mano al jugar Lillie's se pierde en el mazo, asi que el
    # orden no es cosmetico. Reordenar no cuesta nada porque jugar el BCS no
    # consume la bajada de Pokemon (ni el adjunte, ni el ataque): el cuerpo baja
    # despues, en el mismo turno, ya con las 2 cartas nuevas en la mano. Cubre
    # igual el caso "bajo un Ogerpon, hago Teal Dance y sale un BCS": el BCS
    # recien robado se juega ANTES del siguiente cuerpo.
    #
    # Se implementa DEMOTANDO la bajada de Pokemon (tier `_TIER_DEVELOP_TRAS_BCS`)
    # en vez de promoviendo el BCS: asi la regla toca SOLO lo que pidio el user
    # -- las EVOLUCIONES conservan `_TIER_DEVELOP` y siguen precediendo al BCS
    # (promoverlo adelantaba tambien la evolucion a Hydrapple ex y rompia sus
    # dos tests). Consecuencia transitiva aceptada: con BCS y Poke Pad a la vez
    # en la mano, la bajada tambien cede al Poke Pad -- coherente, los dos son
    # cartas de "cavar 7 antes de comprometerse".
    #
    # La demotion solo se aplica si el BCS esta OFRECIDO en este mismo menu y con
    # score REAL (>0): si no fuera jugable, posponer el cuerpo lo dejaria sin
    # bajar. Los tiers se renumeran con huecos (x10) para poder insertar el nuevo
    # nivel conservando TODOS los demas ordenes relativos.
    # =================================================================

    # =================================================================
    # REVOCAR VETOS DE ORDEN SOBRE HABILIDADES (user, registro_006 paso 78 vs
    # Archaludon ex, PERDIDA).
    #
    # Estado del paso 78 (turno 6, nos noquearon el Ogerpon ex el turno anterior):
    #
    #     NOSOTROS                                RIVAL
    #     activo  Teal Mask Ogerpon ex 210 3e     activo  Archaludon ex 400 3e
    #     banca   Bayleef, Meowth ex, 2x Applin,  banca   Duraludon 10, Duraludon 130,
    #             Fezandipiti ex (recien bajado)          Fezandipiti ex
    #     mano    Lillie's Determination, Boss's Orders, Bayleef
    #
    # El menu ofrecia CUATRO jugadas: Lillie's (score -1), Boss's (20), la
    # habilidad Flip the Script del Fezandipiti ex recien bajado (VETADA) y
    # atacar (1100). El agente ATACO y cerro el turno, tirando el robo de 3
    # cartas. Es una perdida seca y no recuperable: Flip the Script es UNA VEZ
    # POR TURNO y su condicion de activacion (que nos noquearan un Pokemon en el
    # turno anterior) desaparece con el turno.
    #
    # La causa es un BLOQUEO CIRCULAR entre tres reglas correctas por separado:
    #   * la habilidad se veta porque "primero Lillie's Determination, DESPUES
    #     la habilidad" (`_lillie_blocks_fez_ability`),
    #   * Lillie's se veta porque cede a un Boss's ejecutable
    #     (`cede_a_boss_ejecutable`),
    #   * y Boss's se degrada a 20 porque cede a Lillie's sin atacante de banca
    #     (`sin_atacante_banca_cede_a_lillie`).
    # Ninguna de las tres se juega y la habilidad muere con el turno.
    #
    # El arreglo ataca la clase entera del error, no este trio: un veto de ORDEN
    # ("primero X") solo es valido mientras X sea REALMENTE jugable en este menu.
    # Se revoca en dos casos, y es agnostico del mazo rival (solo mira nuestra
    # mano y el menu):
    #
    #   (a) NINGUN bloqueador esta ofrecido y jugable (score > 0) en este mismo
    #       menu -- si no se puede jugar X, no hay "despues de X". Cubre el paso
    #       78 (Lillie's vetada) y cualquier bloqueador que quede en la mano por
    #       falta de objetivo legal.
    #   (b) el bloqueador esta ofrecido y jugable, pero PIERDE contra atacar /
    #       pasar y no queda ninguna otra jugada viva: el turno se cierra en esta
    #       misma accion, asi que "despues de X" tampoco va a llegar. Se exige
    #       que el bloqueador puntue POR DEBAJO de la mejor jugada que cierra el
    #       turno, y que las unicas opciones vivas sean bloqueadores o cierres de
    #       turno -- con ese recorte todas viven en el tier 0, no hay tier que
    #       pueda reordenarlas y la comparacion de scores es exacta.
    #
    # Fuera de esos dos casos el veto se mantiene y el orden pedido (Unfair Stamp
    # / Lillie's Determination antes de la habilidad) se respeta tal cual: si el
    # bloqueador gana el menu se juega el primero y, al salir de la mano, el veto
    # se apaga solo en el menu siguiente.
    # =================================================================
    if _ability_order_veto and context == SelectContext.MAIN:
        # Bloqueadores REALMENTE jugables ahora: {id de carta: score}.
        _aov_playable = {}
        # Mejor score entre las jugadas que CIERRAN el turno, y si hay alguna
        # jugada viva que no sea un cierre de turno ni un PLAY de la mano.
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
                # (b): el bloqueador vive, asi que solo se revoca si el turno se
                # cierra YA -- ninguna otra jugada viva y el bloqueador por
                # debajo del ataque/pasar.
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
    # EL SUPPORTER QUE TRAJO EL LAST-DITCH SE JUEGA (user, registro_002 paso 22
    # vs Alakazam, GANADA con error). Ese turno el agente encadeno bien --
    # Ultra Ball -> Meowth ex -> Last-Ditch Catch -> Lillie's Determination --
    # y acto seguido jugo el DAWN que ya tenia en la mano: la Lillie's recien
    # buscada se quedo muerta y el cuerpo de 2 premios en la banca, gratis.
    #
    # Por que no bastaban los vetos previos: `_meowth_fetch_pierde_el_turno`
    # PREDICE, antes de bajar el Meowth, que el fetch se lleva el hueco de
    # Supporter -- pero no se evalua en NUESTRO PRIMER TURNO (la linea anti-donk
    # baja el Meowth igual) y, sobre todo, no obliga a nada DESPUES del fetch. El
    # scorer de jugada volvia a decidir desde cero con la mano nueva y ahi
    # gobernaba un veto de tablero (`no_barajar_ultimo_xerosic`, -1) que ignora
    # que la Lillie's ya esta PAGADA con un cuerpo de 2 premios.
    #
    # La regla es de COMPROMISO, no de valor: una vez gastado el recurso, el
    # Supporter que trajo se queda con el unico hueco del turno. Se implementa
    # con UN SOLO gesto -- un PISO de score aplicado con `max()` -- y NO con un
    # veto a los demas Supporters de la mano. Las dos mitades se midieron por
    # separado (self-play vs 4 mazos rivales, 1500 partidas por celda, 6000 por
    # variante):
    #
    #     sin la regla          83.45%
    #     piso + veto al resto  82.78%   (-0.67)
    #     SOLO PISO             83.85%   (+0.40)   <- esta
    #     solo veto             83.45%   ( 0.00)
    #
    # El piso (8000) ya esta por encima de la banda normal de CUALQUIER otro
    # Supporter (el mas alto es Xerosic, ~7300), asi que el compromiso gana el
    # hueco sin necesidad de vetar a nadie. Lo unico que anadia el veto era
    # ganarle tambien a un Supporter DECISIVO (score > 8000: un Boss's que gana
    # la partida, un remate) -- justo el caso en el que el compromiso DEBE
    # ceder. Por eso quitarlo no solo no rompe la regla: la mejora.
    #
    # Deck-agnostica: no nombra cartas. Se desarma sola cuando el Supporter ya
    # no esta ofrecido (descartado como coste, barajado...) o cuando el hueco ya
    # se gasto (`supporterPlayed`).
    # =================================================================
    if (ESTADO._ld_supp_comprometido and context == SelectContext.MAIN
            and not state.supporterPlayed):
        for _ld_i, _ld_o in enumerate(select.option):
            if _ld_o.type != OptionType.PLAY or _ld_i >= len(scores):
                continue
            _ld_c = get_card(obs, AreaType.HAND, _ld_o.index, my_index)
            if _ld_c is not None and _ld_c.id == ESTADO._ld_supp_comprometido:
                scores[_ld_i] = max(scores[_ld_i],
                                    SCORE_LD_SUPP_COMPROMETIDO)

    _play_order_tier = [0] * len(scores)
    if context == SelectContext.MAIN:
        _TIER_WIN_ATTACK = 70
        _TIER_KO_ENERGY = 60
        # La habilidad de Grand Tree va POR ENCIMA de cualquier jugada de
        # estadio: si primero bajaramos el nuestro (Forest, tier STADIUM), el
        # Grand Tree se iria al descarte con la cadena gratis sin cobrar. El
        # veto `esperar_habilidad_grand_tree` de `_REGLAS_FOREST_PLAY` cubre el
        # mismo caso por score; este tier lo cubre por ORDEN, que es lo que de
        # verdad manda cuando dos jugadas viven en tiers distintos.
        _TIER_STADIUM_ABILITY = 55
        _TIER_STADIUM = 50
        _TIER_DEVELOP = 40
        _TIER_POKE_PAD = 30
        _TIER_BUG_SET = 20
        _TIER_DEVELOP_TRAS_BCS = 15
        _TIER_ENERGY = 10

        # Jugada de Bug Catching Set realmente disponible AHORA (ofrecida en el
        # menu y con score > 0): mientras exista, bajar un Pokemon cede.
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
                    and _active_attack_wins_now and ESTADO.plan.attacker == 0):
                # Remate ganador con el activo: tier MAXIMO para ejecutarlo antes
                # que cualquier carga/desarrollo y cerrar la partida (paso 125).
                _play_order_tier[_po_i] = _TIER_WIN_ATTACK
            elif (_po_o.type == OptionType.RETREAT
                    and (_suicide_swap_win_promote
                         or _win_ko_active_via_promote)):
                # Relevo del remate suicida (user, registro_016 paso 184): mismo
                # tier que el remate ganador, porque es la MISMA jugada -- cerrar
                # la partida este turno, solo que el rematador esta en la banca.
                # Sin este tier, la retirada (score 9600, tier 0) la aplastaba por
                # ORDEN cualquier carga de energia (tier ENERGY) pese a valer
                # menos: el turno se gastaba en adjuntar y el remate no llegaba.
                _play_order_tier[_po_i] = _TIER_WIN_ATTACK
            elif _po_o.type == OptionType.EVOLVE:
                _play_order_tier[_po_i] = _TIER_DEVELOP
            elif _po_o.type == OptionType.ATTACH:
                _po_is_ko_energy = (
                    getattr(ESTADO.plan, 'energy', False)
                    and ESTADO.plan.remain_hp is not None
                    and ESTADO.plan.remain_hp <= 0
                    and ESTADO.plan.attacker >= 0
                    and ((_po_o.inPlayArea == AreaType.ACTIVE
                          and ESTADO.plan.attacker == 0)
                         or (_po_o.inPlayArea != AreaType.ACTIVE
                             and ESTADO.plan.attacker == 1 + _po_o.inPlayIndex)))
                # Fix (user, log 86506312 paso 97, vs Alakazam): NO tratar la
                # carga al ACTIVO como "energia de KO" (tier 6) cuando
                # `_tapu_future_charge` esta activo. Ese flag ya garantiza que el
                # activo (Hydrapple ex) NOQUEA con su energia ACTUAL y que hay
                # Meganium en juego (cada Planta cuenta doble), asi que la energia
                # extra en el activo es INNECESARIA. Sin esta exclusion, el tier
                # KO_ENERGY del activo aplastaba (6 > 1) la carga de Tapu Bulu de
                # banca (`_tapu_future_charge`, score 40000, tier ENERGY),
                # desperdiciando la energia en un atacante ya listo en vez de
                # preparar al atacante FUTURO. Al bajar el activo a tier ENERGY,
                # la carga de Tapu (40000) gana el desempate dentro del mismo tier.
                if (_tapu_future_charge
                        and _po_o.inPlayArea == AreaType.ACTIVE):
                    _po_is_ko_energy = False
                if _po_i in _attach_cede_a_teal_dance:
                    # Adjunte de mero desarrollo con una Teal Dance pendiente:
                    # se queda en tier 0 junto a la habilidad para que decida
                    # el score (Teal Dance 7500 > adjunte capado 7000).
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
                        # Motor UB->Meowth->Lillie's ANTES del adjunte (user,
                        # registro_008 paso 58 vs Archaludon ex, PERDIDA): el
                        # pivote `_ub_engine_refresh_pivot` puntua la UB a 31450,
                        # pero los items van en tier 0 y el adjunte manual (tier
                        # ENERGY=1, ~31410) la aplastaba por tier pese al score.
                        # Mismo patron que Teal Dance (abajo): subirla al tier
                        # ENERGY para que DENTRO del tier decida el score
                        # (31450 > 31410). Solo aplica con el score del pivote
                        # (>31000); la UB normal (<=12500) conserva su tier 0.
                        _play_order_tier[_po_i] = _TIER_ENERGY
                    elif _po_data is not None and _po_data.cardType == CardType.STADIUM:
                        _play_order_tier[_po_i] = _TIER_STADIUM
                    elif _po_data is not None and _po_data.cardType == CardType.POKEMON:
                        # Bajar un Pokemon cede al Bug Catching Set pendiente
                        # (ver la cabecera del bloque): con las 2 cartas nuevas
                        # en la mano se decide MEJOR que cuerpo baja.
                        _play_order_tier[_po_i] = (
                            _TIER_DEVELOP if _bcs_play_idx < 0
                            else _TIER_DEVELOP_TRAS_BCS)
            elif _po_o.type == OptionType.ABILITY:
                # Teal Dance PRECEDE al adjunte manual (user, registro_004 paso
                # 28, vs Mega Starmie): la habilidad Teal Dance de Teal Mask
                # Ogerpon ex adjunta 1 Planta Y ROBA una carta, asi que debe
                # jugarse ANTES que cualquier adjunte manual de energia. Sin
                # esto, la habilidad quedaba en tier 0 (por debajo del tier
                # ENERGY=1 de los adjuntes) y el orden de jugada anteponia una
                # carga manual pese a que Teal Dance puntua mucho mas alto,
                # desperdiciando el robo. Al ponerla en tier ENERGY, dentro del
                # mismo tier decide el score (Teal Dance ~31500 gana). Las
                # cargas de KO letal de ESTE turno siguen en tier KO_ENERGY=6.
                # GUARD (user, registro_009 paso 113 vs Mega Lucario, PERDIDA):
                # la promocion solo aplica cuando Teal Dance puntua como jugada
                # REAL (>= 29000: sus ramas van de 29000 a 31600). Sin el
                # guard, una Teal Dance DEGRADADA (7500: reservas de energia,
                # anti-sobrecarga...) dominaba por TIER a todo el tier 0 --
                # incluida Ripening Charge a 31100, que cargaba el Hydrapple ex
                # ACTIVO (1 energia) para el KO de 3 premios al Mega Lucario ex
                # (Syrup Storm 210 >= 160). El agente regaba la energia
                # recuperada en un Ogerpon de banca y perdia el remate.
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
                    # Flip the Script en el MISMO tier que las habilidades de
                    # carga (user, registro_006 pasos 95-102 vs Mega Lucario): en
                    # tier 0 la aplastaba por ORDEN cualquier Teal Dance /
                    # Ripening Charge promovida, y el turno se cerraba con el robo
                    # de 3 sin cobrar. Dentro del tier decide el score, que ya
                    # codifica la prioridad correcta: habilidad que HABILITA el KO
                    # de hoy (41000+) > Flip the Script (31700) > cargas de
                    # desarrollo (<= 31600). La habilidad VETADA (deck-out o veto
                    # de ORDEN sin revocar) se queda en tier 0, como las demas.
                    _play_order_tier[_po_i] = _TIER_ENERGY
                elif (_po_ab_card is not None
                        and _po_ab_card.id == Hydrapple_ex
                        and scores[_po_i] >= 29000):
                    # Ripening Charge debe competir en el TIER de ENERGIA con Teal
                    # Dance (arriba), igual que ella, cuando puntua como jugada
                    # REAL (>= 29000). Cubre DOS casos:
                    #   * el Hydrapple ex ACTIVO bloqueado del pivote retirar->
                    #     promover (registro_008 paso 82 vs Cubchoo), y
                    #   * cargar el Hydrapple ex de BANCA VACIO como ATACANTE
                    #     FUTURO (user, registro_006 paso 80 vs Mega Lucario): sin
                    #     esto la Ripening (31150) quedaba en tier 0 y la Teal Dance
                    #     de un Ogerpon YA cargado (tier ENERGY, 31050) la dominaba
                    #     por TIER pese a su MENOR score -> se regaba la energia en
                    #     el Ogerpon sobrecargado y el Hydrapple ex se quedaba sin
                    #     energia para un ataque futuro.
                    # Dentro del tier decide el score, que ya codifica la prioridad
                    # correcta: Teal Dance que HABILITA un KO (31500) > cargar el
                    # Hydrapple de banca (31150) > Teal Dance de Ogerpon cargado
                    # (31050). Las Ripening DEGRADADAS (7500: reservas) quedan en
                    # tier 0 (mismo guard que Teal Dance).
                    _play_order_tier[_po_i] = _TIER_ENERGY

    # =================================================================
    # RESCATE ANTI-TURNO ESTERIL (user, registro_009 paso 61 vs Dragapult,
    # PERDIDA). Estado: Chikorita activo (50/70), Tapu Bulu y Applin en banca
    # sin cargar, y en la mano Unfair Stamp + Bayleef + Meganium + Meowth ex +
    # Xerosic + LILLIE'S DETERMINATION, con 6 premios (Lillie's roba OCHO). El
    # agente cerro el turno con Growl (ataque de 0 de dano) y dejo TODA la mano
    # muerta: el scorer de Lillie's la vetaba por `_lillie_evolve_now` (habia
    # una linea evolutiva "evolucionable este turno") mientras la evolucion
    # real estaba bloqueada por el veto de evolucionar en el activo, asi que
    # ninguna de las dos jugadas ocurria.
    #
    # Red de seguridad independiente de que veto falle: si la MEJOR jugada del
    # turno es terminar, o atacar con un ataque que NO hace dano alguno
    # (Growl), el turno no produce NADA -- y refrescar la mano (robar 6/8)
    # siempre es mejor que eso. Se levanta el veto de Lillie's y se pone por
    # encima de esa jugada esteril. El ataque de 0 de dano se detecta con el
    # dano IMPRESO del ataque ofrecido y con `_attacker_base_damage` (que cubre
    # los ataques que escalan, p.ej. Do the Wave de Dipplin), asi que un ataque
    # de chip real (que si quita vida) NO cuenta como turno esteril.
    # Excepcion conservada: vs Alakazam con Xerosic en mano no se baraja el cap
    # de Powerful Hand (razon CONCRETA: se perderia el acceso a esa carta).
    #
    # RESERVA ANTI-DECK-OUT, antes "vs Comfey NUNCA" (user, log 88359220 paso 33
    # vs Comfey/Yveltal, PERDIDA -- registro_003). El turno ya estaba cerrado
    # (evolucion + Bug Catching Set + 2 Ogerpon + adjunte hechos) y el agente
    # termino con Lillie's en la mano y el Supporter del turno SIN JUGAR: el
    # Supporter NO se acumula, un turno sin jugarlo lo tira a la basura.
    # La exencion vieja era una prohibicion por MATCHUP; su motivo real es
    # aritmetico -- Lillie's baraja la mano al mazo y roba 6 (8 con los 6
    # premios intactos), asi que su delta de mazo es (mano - 1) - robo y vs un
    # mazo de mill eso puede acercarnos al deck-out. Se sustituye por esa
    # aritmetica, que es DECK-AGNOSTICA (protege igual contra cualquier mill) y
    # no bloquea el rescate cuando el mazo lo aguanta de sobra: alli el mazo
    # tenia 38 cartas y el refresco lo dejaba en 33, ni de lejos deck-out.
    # Umbral <= 10 = "mazo critico", el mismo de `freno_deckout_mazo_critico`.
    # El rescate solo pisa el "no hacer nada", asi que en los turnos vs Comfey
    # que SI producen algo (el plan solo-Ogerpon) la reserva sigue intacta.
    _lil_robo = 8 if my_prize >= 6 else 6
    _lil_mazo_tras_refresco = (getattr(my_state, 'deckCount', 60)
                               + max(0, sum(hand_counts.values()) - 1)
                               - _lil_robo)
    if (context == SelectContext.MAIN and not state.supporterPlayed
            and _lil_mazo_tras_refresco > 10
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
            _mejor_i = max(range(len(scores)),
                           key=lambda i: (_play_order_tier[i], scores[i]))
            _mejor_o = select.option[_mejor_i]
            _turno_esteril = False
            if _mejor_o.type == OptionType.END or scores[_mejor_i] <= 0:
                _turno_esteril = True
            elif _mejor_o.type == OptionType.ATTACK:
                _est_act = _active_of(my_state)
                _est_op = _active_of(op_state)
                _est_atk = attack_table.get(getattr(_mejor_o, 'attackId', None))
                _est_impreso = getattr(_est_atk, 'damage', 0) or 0
                _est_base = 0
                if _est_act is not None:
                    _est_e = len(_est_act.energies)
                    _est_base = _attacker_base_damage(
                        _est_act.id, _est_op, _est_e * _grass_mult(),
                        grass_scale=total_grass, teal_self_energy=_est_e,
                        bench_count=bench_count)
                _turno_esteril = (_est_impreso <= 0 and _est_base <= 0)
            if _turno_esteril:
                scores[_rescate_lil] = max(1500, scores[_mejor_i] + 100)

    # =================================================================
    # RESCATE DE TURNO MUERTO CON MEOWTH EX (user, registro_002 paso 18 vs
    # Cubchoo, PERDIDA). Hermano del rescate de Lillie's de arriba, para cuando
    # la Lillie's NO esta en la mano sino en el MAZO: si la MEJOR jugada del
    # turno es TERMINAR y tenemos un Meowth ex en la mano cuyo Last-Ditch Catch
    # puede traer un Supporter JUGABLE este turno, bajarlo es estrictamente
    # mejor que no hacer nada -- refresca la mano y abre opciones. En aquel
    # turno 2 el activo era un Meowth ex que no ataca, la banca era Tapu Bulu
    # (0 energias, necesita 4) y un Applin, la mano no tenia ninguna jugada, y
    # el agente cerro el turno con un Meowth ex en la mano que ademas ACABABA DE
    # BUSCAR con una Ultra Ball (dos descartes gastados en una carta que luego
    # se nego a jugar).
    #
    # Va DESPUES de todos los vetos y solo pisa el "no hacer nada", asi que
    # ninguna regla de matchup se debilita mientras quede cualquier jugada real:
    # el veto anti-Cubchoo de un 2o Meowth ex (`field_counts[Meowth_ex] == 0`)
    # sigue vigente en todo turno que produzca algo. Deck-agnostico.
    if (context == SelectContext.MAIN and scores
            and not state.supporterPlayed
            and not meowth_ability_lock
            and bench_count < 5
            and _meowth_ld_free
            and field_counts.get(Meowth_ex, 0) < 2
            and hand_counts.get(Meowth_ex, 0) >= 1
            # SIN NINGUN ATACANTE LISTO: el turno esta muerto por falta de
            # DESARROLLO, que es justo lo que arregla refrescar la mano. Con
            # atacantes listos un turno muerto significa otra cosa (el activo
            # rival es un muro inmune, estamos bloqueados...) y ahi anadir un
            # cuerpo de 2 premios no destraba nada: el plan es Boss's/pivote.
            # Sin este gate el rescate disparaba en turnos 12-16 con 2-4
            # atacantes listos contra el muro de Cornerstone.
            and _ready_attacker_count == 0
            # El fetch tiene que aportar algo: Supporter en el MAZO que no
            # tengamos ya en la mano (ver `_meowth_fetch_prediccion`) y que no
            # pierda el UNICO hueco de Supporter del turno contra uno que ya
            # tenemos (`_meowth_fetch_pierde_el_turno`).
            and _meowth_fetch_id is not None
            and not _meowth_fetch_redundante
            and not _meowth_fetch_pierde_el_turno):
        _mw_rescate = -1
        for _mwi, _mwo in enumerate(select.option):
            if _mwi >= len(scores) or _mwo.type != OptionType.PLAY:
                continue
            _mwcard = get_card(obs, AreaType.HAND, _mwo.index, my_index)
            if _mwcard is not None and _mwcard.id == Meowth_ex:
                _mw_rescate = _mwi
                break
        if _mw_rescate >= 0:
            _mw_mejor_i = max(range(len(scores)),
                              key=lambda i: (_play_order_tier[i], scores[i]))
            _mw_mejor_o = select.option[_mw_mejor_i]
            if (_mw_mejor_o.type == OptionType.END
                    or scores[_mw_mejor_i] <= 0):
                scores[_mw_rescate] = max(1500, scores[_mw_mejor_i] + 100)

    # =================================================================
    # RED DE SEGURIDAD ANTI-BANCA-VACIA (user, registro_002 paso 15 vs Mega
    # Starmie ex, PERDIDA): NUNCA terminar el turno con la banca VACIA si podemos
    # desarrollarla. Con un solo basico en el activo y sin banca, si el rival
    # noquea ese activo PERDEMOS la partida (no hay a quien promover). Si la mejor
    # jugada seria TERMINAR (o cualquier jugada esteril de score <= 0) y existe una
    # opcion que pone un Pokemon en banca --una Ultra Ball que busca un basico, o
    # bajar un basico de la mano-- se prioriza esa jugada por encima del fin de
    # turno. Preferencia: el BUSCADOR (trae un atacante util, p.ej. Ogerpon ex, que
    # ademas acelera con Teal Dance) sobre bajar un basico cualquiera. NO aplica si
    # atacar ya GANA la partida (no hay turno futuro que proteger). Es una RED
    # FINAL: se ejecuta AUNQUE los vetos individuales de cada jugada (Meowth ex con
    # Supporter ya jugado, hold de Lillie's, etc.) la hayan tumbado a <= 0. Deck-
    # agnostico.
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
                and ESTADO.plan.remain_hp is not None and ESTADO.plan.remain_hp <= 0):
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
                        and any(ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(_b, {}).get(
                                    ESTADO_MAZO, 0) > 0
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
    # RED ANTI-TURNO-ESTERIL con Ultra Ball (autopsias jul 2026: el cluster de
    # turnos 2 esteriles con UB vetada aparecio en CUATRO matchups distintos --
    # iron_thorns, cornerstone, comfey y crustle_kangaskhan, 13/31 hallazgos t2
    # en este ultimo). La red anterior solo cubre banca VACIA; esta cubre el
    # resto: si la mejor jugada del turno es TERMINAR (o cualquier cosa de
    # score <= 0) y una Ultra Ball vetada tiene un objetivo UTIL en el mazo,
    # cavar con la UB siempre produce mas que END. "Util" = un basico
    # desplegable (banca con hueco) o una EVOLUCION enlazada a un cuerpo ya en
    # juego (jugable el proximo turno). Guarda: no si atacar ya gana.
    #
    # "UTIL" LO DECIDE EL PLAN DEL MATCHUP, NO UNA PROHIBICION POR MAZO
    # (barrido jul 2026, a raiz de los dos fallos del log 88359220). La guarda
    # `not op_is_comfey_deck` era un proxy tosco de una pregunta concreta: vs
    # Comfey el plan solo deja bajar Teal Mask Ogerpon ex (max 2), asi que
    # cavar cualquier OTRO cuerpo trae una carta que el propio plan vetara al
    # bajarla -- dos cartas de mano por nada. Preguntado via
    # `_matchup_permite_bajar`, la red deja de disparar en esos casos igual que
    # antes, pero SI dispara cuando el objetivo entra en el plan: un Ogerpon ex
    # con <2 en juego es justo lo que el matchup quiere buscar, y la Ultra Ball
    # esta en su allowlist de items. El motivo que citaba el comentario viejo
    # ("quemar 2 cartas del mazo alimenta el mill") ademas no era exacto: el
    # coste de la Ultra Ball sale de la MANO; del mazo solo sale la buscada.
    # Gate de self-play vs deck/rivales/comfey.csv, 6000 partidas por rama:
    # 91.7% con el cambio vs 91.2% sin el (+0.5 puntos, DENTRO DEL RUIDO: el
    # cambio se sostiene por el razonamiento, el gate solo descarta que reste).
    #
    # vs CUBCHOO la guarda SE MANTIENE. Alli el END conservador es politica
    # deliberada del matchup ([[anti-cubchoo-no-retirada-pivote]]) y no un
    # proxy de nada: filtrar por `CUBCHOO_ALLOWED_PLAY_IDS` en vez de apagar la
    # red MIDIO PEOR en el mismo gate -- 68.7% vs 70.0% en 6000 partidas por
    # rama (-1.3 puntos, z~-1.7). Se revirtio esa mitad del barrido.
    # GUARDA DE PRIMER TURNO (user, registro_002 pasos 24/27 vs Ceruledge,
    # PERDIDA): en nuestro primer turno de accion (turn <= 2) la red solo
    # aplica con banca <= 2 (desarrollo REAL pendiente, como el caso crustle
    # t2 con banca 1 que la motivo). Con la banca ya poblada (4/5) y la mano
    # llena de valor futuro (Xerosic/Stamp/Lana's/evoluciones), la UB quema 2
    # cartas utiles para traer un basico redundante: el agente encadeno DOS
    # UB descartando Xerosic+Meganium+Lana's+Dipplin por 2 Meowth ex muertos.
    # La unica UB legitima de primer turno con tablero hecho es la del caso
    # Budew/Dragapult, que vive en `_ub_first_turn_allowed`, no aqui.
    if (context == SelectContext.MAIN and scores and bench_count > 0
            and not op_is_cubchoo_deck
            and (state.turn > 2 or bench_count <= 2)
            and sum(hand_counts.values()) >= 3):
        _st_best_i = max(range(len(scores)),
                         key=lambda i: (_play_order_tier[i], scores[i]))
        _st_best_o = select.option[_st_best_i]
        _st_sterile = (_st_best_o.type == OptionType.END
                       or scores[_st_best_i] <= 0)
        # UN TURNO QUE ACABA ATACANDO DE VERDAD NO ES UN TURNO MUERTO (user,
        # registro_006 paso 98 vs Mega Lucario ex, PERDIDA). La premisa de esta
        # red es "la alternativa a cavar es TERMINAR sin hacer nada", y por eso
        # cavar siempre produce mas. Pero `scores[best] <= 0` no significa END:
        # un ATAQUE normal puntua -1 por defecto (es el fallback del argmax), y
        # los Items no consumen el ataque -- asi que en aquel turno la Ultra
        # Ball no salvaba nada, solo pagaba 2 cartas de mano ANTES de un Syrup
        # Storm de 210 que se iba a lanzar igual (y se lanzo, paso 104).
        # Se mide el ataque igual que el rescate de Lillie's de mas arriba
        # (dano impreso o base > 0) y se descartan los ataques ya marcados como
        # inutiles por inmunidad (SCORE_USELESS_ATTACK).
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
                and ESTADO.plan.remain_hp is not None and ESTADO.plan.remain_hp <= 0):
            _st_opa = op_state.active[0] if op_state.active else None
            if _st_opa is not None and op_prize <= prize_count_op(_st_opa):
                _st_wins = True
        if _st_sterile and not _st_wins:
            _st_en_mazo = lambda cid: (
                ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(cid, {}).get(ESTADO_MAZO, 0) > 0)
            # EXCEPCION de bloqueo de items (user): con Budew en el campo rival
            # -- o contra Dragapult, que lo lleva y puede bajarlo -- la Ultra
            # Ball es "usala o pierdela": el proximo turno no se podran jugar
            # items. Solo en ese caso se permite cavar algo que sirva para el
            # turno SIGUIENTE en vez de para este. Mismo predicado que usa la
            # cadena UB->Meowth->Lillie's (`_bloqueo_de_items_inminente`).
            _st_item_lock = _item_lock_incoming
            # El plan del matchup filtra los objetivos: un cuerpo que la rama
            # PLAY vetara al bajarlo no salva ningun turno (ver
            # `_matchup_permite_bajar`). Sin plan restrictivo no filtra nada.
            _st_plan_ok = lambda cid: _matchup_permite_bajar(
                cid, field_counts, op_is_comfey_deck, op_is_cubchoo_deck,
                cubchoo_allow_tapu=(op_has_ability_immune_active
                                    or ESTADO.op_is_cornerstone_deck),
                dragapult_no_tapu=_dragapult_no_tapu)
            # Meowth ex solo cuenta como objetivo UTIL si su Last-Ditch Catch
            # puede producir algo este turno (user, registro_006 pasos 98-104):
            # es un cuerpo de 2 premios cuyo unico valor es buscar un Supporter,
            # asi que con el Supporter del turno ya jugado, con la habilidad
            # bloqueada (Watchtower) o con la Last-Ditch ya gastada
            # (`_meowth_ld_free`), la rama PLAY lo vetara al bajarlo y la Ultra
            # Ball habra quemado 2 cartas por una carta muerta. Mismo criterio
            # que el fetch (`last_ditch_no_produce`) y que
            # `_ub_cavar_meowth_se_juega`.
            _st_meowth_util = (not state.supporterPlayed
                               and not meowth_ability_lock
                               and _meowth_ld_free
                               and field_counts.get(Meowth_ex, 0) < 2)
            _st_cuerpo_ok = lambda cid: (
                _st_plan_ok(cid)
                and (cid != Meowth_ex or _st_meowth_util))
            _st_basico_util = (bench_count < 5 and any(
                _st_en_mazo(_b) and _st_cuerpo_ok(_b) for _b in (
                    Chikorita, Applin, Teal_Mask_Ogerpon_ex, Tapu_Bulu,
                    Meowth_ex, Fezandipiti_ex)))
            # La pre-evolucion tiene que poder EVOLUCIONAR ESTE TURNO (user,
            # registro_003 vs Mega Abomasnow ex): con el Applin recien bajado
            # (`appearThisTurn`, sin Forest of Vitality) no hay forma de
            # evolucionar, asi que buscar su evolucion no produce nada este
            # turno -- y la Ultra Ball cuesta DOS cartas de la mano. Se mira
            # cuerpo a cuerpo (`appearThisTurn`), no por especie: con dos
            # Applin, uno recien bajado y otro asentado, la linea SI sale.
            # Con la amenaza de bloqueo de items se conserva el criterio
            # anterior (basta con que la pre-evo este en juego: sirve para el
            # turno siguiente, que es justo lo que se esta comprando).
            def _st_evolucionable(pre_id):
                for _stp in ((my_state.active or []) + (my_state.bench or [])):
                    if _stp is None or _stp.id != pre_id:
                        continue
                    if (_st_item_lock or ESTADO.forest_in_play
                            or not getattr(_stp, 'appearThisTurn', False)):
                        return True
                return False
            _st_evo_util = any(
                _st_evolucionable(_pre) and _st_en_mazo(_evo)
                and _st_plan_ok(_evo)
                for _pre, _evo in ((Applin, Dipplin), (Chikorita, Bayleef),
                                   (Bayleef, Meganium), (Dipplin, Hydrapple_ex)))
            # No se cava lo que YA se podria jugar (user, registro_003 paso 25
            # vs Mega Abomasnow ex, PERDIDA): si el menu ya ofrece bajar un
            # Pokemon de la mano (o evolucionar) y el scorer lo ha VETADO, el
            # turno no esta muerto por falta de cuerpos -- esta muerto porque
            # bajar otro cuerpo no aporta. Cavar con la Ultra Ball trae mas de
            # lo mismo y ademas quema DOS cartas: alli descartaba Meganium (la
            # Fase 2 de la linea) + Dawn para traer un SEGUNDO Meowth ex que
            # luego no jugaba. Terminar el turno es estrictamente mejor.
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
                _st_basico_util = False
                _st_evo_util = False
            # EL VETO POR COSTE NO SE REVOCA POR TURNO ESTERIL (user, log
            # 88359220 pasos 8-14 vs Comfey/Yveltal, PERDIDA -- registro_001).
            # Escenario: NUESTRO primer turno saliendo PRIMEROS (no hay ataque
            # ni Supporter en el menu: el turno es esteril POR REGLA, no por
            # mala construccion), activo Chikorita + Fezandipiti ex en banca,
            # mano {Ultra Ball, Lillie's Determination, Bayleef, Grass, Unfair
            # Stamp}. `_score_ultra_ball_play` la VETO correctamente por coste
            # (`_ub_cancel_lillie`: el unico forraje real es la Grass -- el
            # Bayleef enlaza con el Chikorita del activo y el Unfair Stamp
            # nunca se descarta -- asi que pagar los 2 descartes se lleva por
            # delante el Lillie's), pero esta red lo resucitaba a 200 y el
            # agente descartaba Grass + Lillie's para cavar un Meowth ex...
            # cuya Last-Ditch Catch volvia a buscar OTRO Lillie's. Balance:
            # -3 cartas de mano y un cuerpo de 2 premios regalado, para acabar
            # con la MISMA carta que ya teniamos.
            # La distincion es general y vale para cualquier mazo: los vetos
            # que esta red puede revocar son los de CONSERVADURISMO ("no hay
            # objetivo util", "es pronto"), porque ante un turno muerto cavar
            # siempre produce mas que END. El veto por COSTE es aritmetica de
            # cartas -- la Ultra Ball vale MENOS que lo que hay que descartar
            # para jugarla -- y esa desigualdad no cambia porque el turno este
            # muerto: END conserva el Supporter / la pieza de evolucion para
            # el turno siguiente, que es estrictamente mas que cambiarlos por
            # un basico redundante. Ver `_ub_coste_destruye_carta_mejor`.
            if _ub_coste_destruye_carta_mejor(ctx):
                _st_basico_util = False
                _st_evo_util = False
            if _st_basico_util or _st_evo_util:
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
