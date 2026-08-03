"""Ultra Ball: el orquestador de busqueda y sus vetos.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

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
    """Fase A de _score_ultra_ball_play: flags derivados del contexto (modo
    supervivencia, primer turno, busquedas de evolucion, tablero desarrollado,
    tamano de mano). Cuerpo verbatim (Paso 2 del plan)."""
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

    # Variante ESTRICTA de _evolve_possible_in_play SOLO para el
    # corte de banca llena de Ultra Ball: la excepcion de "hay algo
    # que evolucionar" unicamente cuenta cuando la pieza de
    # evolucion FALTA en la mano y esta en el MAZO (hace falta
    # buscarla con Ultra Ball). Si la evolucion YA esta en la mano,
    # la linea se evoluciona sin Ultra Ball, asi que buscar con ella
    # solo traeria una carta inutil/redundante (banca llena) y hasta
    # podria descartar la propia evolucion como coste.
    # NOTA (user, log 86028607 paso 47, vs Crustle): la busqueda de
    # Hydrapple ex (evolucion del Dipplin) NO cuenta si el rival es
    # inmune a ex (Crustle): la rama TO_HAND rebaja ese objetivo a
    # 40 (carta muerta), asi que la Ultra Ball nunca lo traeria; sin
    # esta excepcion la busqueda "fantasma" de Hydrapple ex saltaba
    # el corte de banca llena y jugaba una Ultra Ball inutil.
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

    # Variante de _ub_evolve_needs_search que ademas exige poder
    # COMPLETAR la evolucion ESTE turno: la pre-evolucion debe
    # poder evolucionar ya (hay Forest of Vitality en juego o la
    # pre-evo estaba en juego al inicio del turno, no salio este
    # turno). Si es asi, buscar con Ultra Ball desarrolla la linea
    # de evolucion AHORA, asi que NO se debe posponer frente a
    # Lillie's Determination (se evoluciona primero y Lillie's se
    # juega despues, sin barajar las piezas ya en mesa).
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

    # Regla (user, log 86028035 paso 53): si YA tenemos un
    # atacante LISTO en el activo (existe opcion de ATACAR este
    # turno) y la banca ya tiene >=2 Pokemon energizados
    # (atacantes potenciales), la Ultra Ball NO debe jugarse para
    # DESARROLLAR mas atacantes de bajo valor descartando energia
    # / Lillie's Determination utiles: conviene atacar y conservar
    # los recursos. Solo se veta el desarrollo redundante; los
    # objetivos de alto valor (>=800: cadena Meowth->Lillie, piezas
    # de evolucion) y las busquedas que habilitan una evolucion
    # pendiente siguen permitidos.
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
    """Fase E de _score_ultra_ball_play: overrides terminales sobre `ub_score`
    ya calculado (rescate supervivencia, Bug Set, gate primer turno, salvaguarda
    banca llena, deferral linea Alakazam). SIEMPRE se aplica; hila y devuelve
    ub_score. Cuerpo verbatim (Paso 2 del plan)."""
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
    # El rescate de supervivencia solo tiene sentido con HUECO en banca: busca
    # un Basico para bajarlo y desarrollar/defender. Con la banca LLENA
    # (bench_count >= 5) no se puede banquear nada, asi que buscar un Basico solo
    # lo llevaria muerto a la mano (pagando 2 descartes). Sin este `bench_count
    # < 5`, el rescate resucitaba la Ultra Ball (a 25000) pese al corte de banca
    # llena, jugando una Ultra Ball inutil (user, registro 006 paso 72 vs Hops,
    # PERDIDA: banca llena, buscaba un Applin que no podia jugar).
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

    # SALVAGUARDA FINAL de banca llena (user, log 86210257
    # paso 86, GANADA vs Mega Starmie). Control EXTRA que tiene
    # la ULTIMA palabra sobre cualquier ruta anterior que
    # hubiera dejado ub_score > 0: con la banca LLENA
    # (bench_count >= 5) y SIN ninguna evolucion que completar
    # en juego (`_evolve_possible_in_play` = no hay una
    # pre-evolucion en mesa cuya siguiente etapa este en mano o
    # en el mazo), Ultra Ball no puede banquear nada nuevo y
    # solo malgasta su coste (descartar 2 cartas utiles, p.ej.
    # un Hydrapple ex + Forest of Vitality) para traer una
    # carta MUERTA a la mano (un Chikorita que no cabe en
    # banca). Duplica el corte de L9029/L9220 pero como override
    # terminal, para que ninguna rama intermedia pueda
    # reactivarla. UNICA excepcion: modo supervivencia (banca
    # vacia), donde bench_count>=5 ya es False de por si.
    if (bench_count >= 5
            and not _evolve_possible_in_play
            and not _ub_survival_mode):
        # -100 (por debajo del piso de veto -1) para que, si el resto de
        # jugadas del turno tambien estan vetadas (ataque/retirada = -1), el
        # argmax prefiera ATACAR/PASAR antes que malgastar esta Ultra Ball
        # inutil por defecto (indice 0). (user, registro 006 paso 72 vs Hops.)
        ub_score = SCORE_CANCEL

    # Secuencia (user, registro 010, paso 64 vs Alakazam): si esta
    # activo el corte de la linea Alakazam (`_boss_deny_alakazam_line`)
    # y todavia tenemos el Boss's Orders en la mano sin jugar,
    # POSPONER la Ultra Ball: jugarla ahora descartaria el propio
    # Boss's como coste (a menudo es el unico fodder). Se rebaja por
    # debajo del Boss's (BOSS_SCORE_PRIZE_RANK_BASE) para que el
    # gusteo se ejecute primero; una vez jugado el Boss's, esta
    # guarda deja de aplicar y la Ultra Ball recupera su score.
    if (_boss_deny_alakazam_line and ub_score > 2000
            and hand_counts.get(Boss_Orders, 0) >= 1
            and not state.supporterPlayed):
        ub_score = 2000

    return ub_score


def _ub_cancel_stamp(ctx) -> bool:
    """Fase C de Ultra Ball: veto por coste (stamp). ¿Jugar UB descartaria
    una carta valiosa como su coste de 2? Predicado puro; conteo verbatim."""
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

        # Las COPIAS SOBRANTES de Ultra Ball (todas menos la
        # que se juega) SI son fodder valido para pagar el
        # coste sin tocar Unfair Stamp. Antes se excluian TODAS
        # las Ultra Ball del conteo, asi que con mano {Unfair
        # Stamp, Ultra Ball, Ultra Ball, Lana's Aid} solo veia
        # 1 descartable (Lana's) y cancelaba la Ultra Ball,
        # terminando el turno sin buscar (user, log 86403004
        # paso 17, PERDIDA vs Iono): la 2a Ultra Ball + Lana's
        # Aid pagan el coste, protegen el Stamp y buscan Meowth
        # ex -> Lillie's.
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
    """Fase C de Ultra Ball: veto por coste (fez). ¿Jugar UB descartaria
    una carta valiosa como su coste de 2? Predicado puro; conteo verbatim."""
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
    """Cuantas cartas de la mano soltaria REALMENTE el scorer de DISCARD antes
    de tocar `protegida` (el "forraje real" con el que se paga el coste de 2 de
    la Ultra Ball). No basta con contar "toda carta distinta de la protegida":
    las piezas de evolucion con su pre-evo en juego, el Fezandipiti ex tras un
    KO o un Meowth ex todavia jugable puntuan MAS BAJO que la carta protegida en
    el bloque `SelectContext.DISCARD`, asi que el motor los conserva y suelta la
    protegida en su lugar. Solo cuenta lo que caeria primero.

    Se excluyen siempre la propia Ultra Ball (es la carta que se juega, no paga
    su coste) y Unfair Stamp (score -10000: nunca se descarta).

    Extraido del cuerpo de `_ub_cancel_lillie` (conteo verbatim) para que los
    demas vetos por coste que protegen un Supporter usen la MISMA aritmetica."""
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
            # Meowth ex esta PROTEGIDO por el scorer de
            # DISCARD (score 2) salvo que: ya tengamos uno
            # en juego (score 82) o la banca este llena Y ya
            # se jugo el supporter del turno (score 65). Solo
            # en esos dos casos es fodder real; en cualquier
            # otro el scorer lo CONSERVA y suelta Lillie's en
            # su lugar (user, log 86412738 paso 115, GANADA
            # vs Hops: mano {UB, Lana's Aid, Lillie's, Meowth
            # ex} con banca llena y supporter sin jugar ->
            # descartaba Lana's + Lillie's y guardaba un
            # Meowth ex ni siquiera jugable).
            if field_counts.get(Meowth_ex, 0) >= 1:
                _ub_ll_fodder = True
            elif bench_count >= 5 and state.supporterPlayed:
                _ub_ll_fodder = True
            else:
                _ub_ll_fodder = False
        elif _ub_llid in (Lillie_Determination, Dawn):
            # Los Supporter de REFRESCO son lo MAS protegido del bloque
            # SelectContext.DISCARD mientras el Supporter del turno siga libre y
            # solo haya una copia (`_protect_refresh_supporter`): Lillie's
            # puntua 2 y Dawn 3, POR DEBAJO de cualquier otra carta que estos
            # vetos protegen (Xerosic vs Alakazam puntua 5). El scorer NUNCA los
            # suelta antes que `protegida`: los conserva y tira la protegida en
            # su lugar. Contarlos como forraje era sobrecontar -- el mismo fallo
            # que el ajuste del log 86401283 ya cerro para las piezas de
            # evolucion, pero del lado de los Supporter.
            #
            # (user, registro_004 pasos 43-64 vs Alakazam, PERDIDA). Turno 4,
            # mano {Boss's x2, Ultra Ball x2, Tapu Bulu, Lillie's}: el motor
            # `_alakazam_dig_xerosic_engine` armo la cadena Ultra Ball -> Meowth
            # ex -> Last-Ditch -> Xerosic (5950 > Lillie's 5000) quemando Tapu
            # Bulu + un Boss's, y la cadena LLEGO a poner el Xerosic en la mano.
            # Con la mano ya en {Boss's, Lillie's, Ultra Ball, Xerosic},
            # `_ub_forraje_real(prot=Xerosic)` contaba 2 (Boss's + Lillie's), asi
            # que `_ub_cancel_xerosic` NO saltaba: la SEGUNDA Ultra Ball (11400,
            # objetivo de valor 800) gano al Xerosic (7200) y pago su coste con
            # el Boss's y con EL PROPIO XEROSIC. Despues cavo un segundo Meowth
            # ex -- inservible, su Last-Ditch ya estaba gastada -- y remato
            # jugando la Lillie's, que barajo ese Meowth de vuelta al mazo.
            # Saldo del turno: Tapu Bulu, 2 Boss's, el Xerosic y las 2 Ultra
            # Ball perdidos para acabar jugando EXACTAMENTE el Supporter que
            # toda la cadena existia para no jugar.
            if (not state.supporterPlayed
                    and (hand_counts.get(Lillie_Determination, 0)
                         + hand_counts.get(Dawn, 0)) <= 1):
                _ub_ll_fodder = False
        if _ub_ll_fodder:
            _ub_discardable_without_lillie += _ub_llcnt
    return _ub_discardable_without_lillie


def _ub_cancel_xerosic(ctx) -> bool:
    """Fase C de Ultra Ball: veto por coste (Xerosic's Machinations).

    vs Alakazam, con la mano rival inflada, Xerosic (el rival descarta hasta
    quedarse con 3) es la jugada del turno: capa Powerful Hand, que pega
    20 x (mano + 2). Si el coste de la Ultra Ball (descartar 2) tuviera que
    comerse ese Xerosic, la Ultra Ball vale MENOS que lo que cuesta.

    (user, registro_006 paso 56 vs Alakazam, PERDIDA -- log 88501752).
    Escenario exacto: mano {Dawn, Xerosic's Machinations, Ultra Ball},
    `supporterPlayed=False`, rival con 11 cartas en mano (Powerful Hand
    proyectado 20 x 13 = 260) y su Alakazam ex acababa de noquear a nuestro
    Meowth ex. El agente jugo la Ultra Ball (11900, banda de item, muy por
    encima del Xerosic a 6200), pago el coste con las DOS unicas cartas que le
    quedaban -- Xerosic Y Dawn -- y trajo un Meganium para evolucionar un
    Bayleef de banca. Balance del turno: mano a 0, Supporter sin jugar, la mano
    rival intacta... y el Meganium que trajo lo habria traido GRATIS el Dawn
    (busca Basico + Fase 1 + Fase 2 del mazo) al turno siguiente, sin descartar
    nada. La linea correcta era Xerosic ahora (rival 11 -> 3 cartas, Powerful
    Hand de 260 a 100) y Dawn el turno siguiente.

    Por eso el veto pregunta por el forraje real: con 2+ cartas de relleno la
    Ultra Ball se paga sin tocar el Xerosic y las dos jugadas conviven en el
    mismo turno (la Ultra Ball es Item, no gasta el Supporter). El veto solo
    salta cuando pagar significa quemar la disrupcion.

    `_score_xerosic_play(ctx) > XEROSIC_SCORE_LAST_RESORT` es el gate: reusa el
    scorer real del Supporter en vez de duplicar sus condiciones, asi que hereda
    todas sus renuncias (mano rival <= 3, Unfair Stamp pendiente, gusteo ganador
    con Boss's, cesion a Lillie's con la mano rival minima). Si Xerosic no es
    una jugada de verdad este turno, no hay nada que proteger.

    Por eso el veto NO se caza al matchup Alakazam: preguntar por el scorer lo
    hace deck-agnostico y tambien cubre la rama `generico_mano_muy_grande` (mano
    rival >= 7 sin Alakazam enfrente), donde la aritmetica es la misma. Medido
    en self-play de matchup (400-2000 partidas vs los bots de crustle /
    dragapult / hops) el efecto fuera de Alakazam es neutro."""
    if ctx.hand_counts.get(Xerosic_Machinations, 0) < 1:
        return False
    if ctx.state.supporterPlayed:
        return False
    if _score_xerosic_play(ctx) <= XEROSIC_SCORE_LAST_RESORT:
        return False
    return _ub_forraje_real(ctx, Xerosic_Machinations) < 2


def _ub_cancel_lillie(ctx) -> bool:
    """Fase C de Ultra Ball: veto por coste (lillie). ¿Jugar UB descartaria
    una carta valiosa como su coste de 2? Predicado puro; conteo verbatim."""
    hand_counts = ctx.hand_counts
    state = ctx.state

    # CANCELAR Ultra Ball si su coste sacrificaria un
    # Lillie's Determination sin haber jugado partidario
    # (user, log 86210811 paso 36/37, GANADA). Escenario:
    # mano pequena {Unfair Stamp, Fezandipiti ex, Ultra
    # Ball, Lillie's}, supporterPlayed=False. El coste de
    # Ultra Ball (descartar 2) protege Unfair Stamp
    # (-10000) y termina descartando Fezandipiti +
    # Lillie's, tirando el partidario a la basura. Lillie's
    # (baraja la mano y roba 6/8) es una jugada MUCHO mejor
    # y debe tener prioridad. Contamos las cartas realmente
    # descartables SIN tocar Lillie's; excluimos tambien
    # Unfair Stamp porque nunca se descarta (score -10000),
    # asi que no puede pagar el coste. Si quedan <2, para
    # pagar Ultra Ball habria que descartar el Lillie's ->
    # se cancela y el partidario gana la decision.
    # AJUSTE (user, log 86401283 paso 32, GANADA vs Alakazam):
    # el conteo INGENUO (toda carta != UB/Lillie's/Unfair
    # Stamp) sobrecontaba fodder. Con mano {UB, Hydrapple ex,
    # Lillie's, Grass} y un Applin en banca, Hydrapple ex es
    # OBJETIVO de evolucion: el scorer de DISCARD lo protege
    # (score 3, POR DEBAJO del Lillie's protegido ~5), asi que
    # NUNCA se descarta y en su lugar cae Lillie's. El conteo
    # ingenuo veia 2 "descartables" (Hydrapple + Grass) y NO
    # cancelaba, tirando el partidario. Ahora solo se cuenta
    # como fodder lo que el scorer de DISCARD SI soltaria antes
    # que Lillie's: se EXCLUYEN las piezas de evolucion / Fez
    # en estado PROTEGIDO (mismos criterios de score bajo del
    # bloque SelectContext.DISCARD).
    _ub_cancel_for_lillie = False
    if (not state.supporterPlayed and
            hand_counts.get(Lillie_Determination, 0) >= 1):

        if _ub_forraje_real(ctx, Lillie_Determination) < 2:

            _ub_cancel_for_lillie = True

    return _ub_cancel_for_lillie


def _ub_cancel_meowth(ctx) -> bool:
    """Fase C de Ultra Ball: veto por coste (meowth). ¿Jugar UB descartaria
    una carta valiosa como su coste de 2? Predicado puro; conteo verbatim."""
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
    """¿Hay un estadio RIVAL en mesa que apaga parte de nuestro motor -o
    enciende el suyo- y que nuestro estadio quitaria? Con nuestro Forest ya en
    mesa no hay nada que levantar.

      * Neutralization Zone: nuestros ex no pueden atacar a Pokemon que no
        sean ex.
      * Team Rocket's Watchtower: los {C} pierden habilidad -> mata la
        Last-Ditch Catch de Meowth ex.
      * Festival Grounds (log 88971843, PERDIDA): no apaga nada nuestro, pero
        ENCIENDE Festival Lead -- su Dipplin repite el ataque en cuanto nos
        noquea el activo, que es como se cierran las partidas contra ese mazo.
        Es el unico de los tres que es de DOBLE FILO (nuestro Dipplin tambien
        lo gana), por eso llega ya filtrado en `festival_lead_hostil`: solo
        cuenta cuando hemos visto la linea Applin/Dipplin del rival.

    Un solo predicado para las DOS caras de la misma decision: el scorer de
    DESCARTE lo usa para no soltar la carta y la rama PLAY para no vetarla. Que
    vivieran separados producia el peor resultado posible -- conservar en la
    mano una carta que luego era ilegal jugar (log 88359220)."""
    return ((neutralization_zone_active or watchtower_in_play
             or festival_lead_hostil)
            and not forest_in_play)


def _matchup_permite_bajar(cid, field_counts, op_is_comfey_deck,
                           op_is_cubchoo_deck, cubchoo_allow_tapu=False,
                           dragapult_no_tapu=False) -> bool:
    """¿El plan del matchup permite BAJAR este Pokemon (y queda cupo)? Espejo
    conservador de las whitelists de la rama PLAY (Comfey: solo Teal Mask
    Ogerpon ex, max 2; Cubchoo: `CUBCHOO_ALLOWED_PLAY_IDS`, max 2 Ogerpon).

    Lo consultan las REDES DE RESCATE del bloque de finalizacion, que hasta
    ahora se apagaban enteras con `not op_is_<mazo>_deck`. La prohibicion por
    matchup era un proxy tosco de esta pregunta: lo que hace inutil cavar vs
    Comfey no es el matchup en si, es que el cuerpo que traeria la busqueda lo
    vetara despues el propio plan (y entonces la Ultra Ball habria quemado dos
    cartas de la mano por una carta muerta). Preguntado asi, la red sigue
    funcionando cuando el objetivo SI entra en el plan -- vs Comfey, un Ogerpon
    ex con menos de 2 en juego es exactamente lo que el matchup quiere.

    Deliberadamente CONSERVADOR: replica el cupo de Ogerpon y las listas, pero
    no las excepciones finas de la rama PLAY (starter de arranque vs Comfey,
    Meowth ex condicionado a que haya Lillie's que buscar vs Cubchoo), que
    tratan como jugable menos de lo que trata la rama PLAY, nunca mas. Si el
    rival no es ninguno de esos dos mazos no hay plan que restrinja nada.

    `dragapult_no_tapu` es el mismo veto que aplica la rama PLAY vs Dragapult
    con >2 Pokemon en juego (ver `_dragapult_no_tapu`): sin el, la red de
    rescate del turno esteril pagaba una Ultra Ball -- dos cartas de la mano --
    por un Tapu Bulu que despues no se podia bajar."""
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
    """¿El rival puede dejarnos SIN Items en NUESTRO proximo turno?

    Budew ataca por CERO energia con *Itchy Pollen* ("durante el proximo turno
    de tu rival no puede jugar cartas de Objeto"). En cuanto esta en el campo
    rival, cada Item de nuestra mano es **usalo o pierdelo**: la Ultra Ball que
    se guarda "para cuando el objetivo sirva" no llega a jugarse nunca. La linea
    Dragapult (Dreepy/Drakloak/Dragapult ex) lo lleva de serie, asi que cuenta
    el matchup entero aunque el Budew no haya aparecido todavia -- puede bajarlo
    y atacar con el en el mismo turno.

    Es la misma nocion que ya usaba la red de rescate del turno esteril
    (finalizacion de `agent()`), ahora con nombre y compartida con la cadena
    UB->Meowth->Lillie's, que bajo esta amenaza puede cavar HOY un cuerpo que se
    juega MAÑANA (`_ub_meowth_para_manana`)."""
    return bool(budew_on_op_field or op_has_dragapult or op_has_dreepy_line)


def _ub_coste_destruye_carta_mejor(ctx) -> bool:
    """¿El COSTE de la Ultra Ball (descartar 2) obligaria a tirar una carta
    MEJOR que lo que la busqueda trae? Agrupa los cuatro vetos por coste de la
    Fase C (`_ub_cancel_stamp` / `_ub_cancel_fez` / `_ub_cancel_lillie` /
    `_ub_cancel_meowth` / `_ub_cancel_xerosic`): todos comparten la misma cuenta
    (`_ub_forraje_real`) -- se enumeran las
    cartas de la mano que el scorer de DISCARD SI soltaria (forraje real) y, si
    quedan menos de 2, pagar la Ultra Ball significa quemar el Supporter / la
    pieza de evolucion / el cuerpo protegido.

    Existe como predicado independiente porque este veto es de naturaleza
    distinta a los demas vetos de Ultra Ball: los otros dicen "no hay objetivo
    util" o "es pronto" (conservadurismo, revocable cuando el turno queda
    esteril), mientras que este dice "la jugada CUESTA mas de lo que trae"
    (aritmetica de cartas, NUNCA revocable por aburrimiento). Los rescates que
    resucitan Ultra Balls vetadas deben consultarlo antes de subir su score."""
    return bool(_ub_cancel_stamp(ctx) or _ub_cancel_fez(ctx)
                or _ub_cancel_lillie(ctx) or _ub_cancel_meowth(ctx)
                or _ub_cancel_xerosic(ctx))


def _alakazam_dig_xerosic_engine(c) -> bool:
    """vs Alakazam con la mano rival en zona de Powerful Hand (>= 6 cartas =
    20 x (6+2) = 160+ de dano proyectado): ¿podemos MONTAR el cap de Xerosic's
    Machinations ESTE turno via el motor Ultra Ball -> Meowth ex -> Last-Ditch
    Catch (busca Xerosic) -> jugar Xerosic? Xerosic reduce la mano rival y con
    ella el dano de Powerful Hand; con un atacante ya listo NO conviene gastar
    el Supporter del turno en Lillie's (refresco redundante) -- se reserva para
    Xerosic y se cava Meowth con la Ultra Ball.

    Requisitos: mazo Alakazam + mano rival >= 6 + Supporter sin jugar; Xerosic
    en el MAZO (si ya esta en mano, su propia escalera lo juega, no hay que
    cavar); Meowth alcanzable (en mano, o en el mazo con Ultra Ball para
    cavarlo); hueco de banca y Last-Ditch libre (field Meowth < 2). Usado por el
    veto de Lillie's y por la prioridad de Ultra Ball. Deck-agnostico dentro del
    matchup Alakazam. `c` puede ser el DecisionContext o el _CtxLillie (ambos
    exponen estos campos, este ultimo por delegacion).

    Umbral mano rival >= 7 (no >= 6 como el gate de JUGAR Xerosic): cavar la
    disrupcion consume un turno entero (Ultra Ball + Meowth + Supporter, sin
    refrescar), inversion que solo se justifica con la mano rival claramente
    inflada -- alineado con `xerosic_generico` del fetch. Con 6 cartas (mano
    base al turno 3-4) el refresco de Lillie's puede valer mas que la disrupcion,
    asi que ahi no se veta ni se prioriza la Ultra Ball."""
    if not (getattr(c, 'op_is_alakazam_deck', False)
            and c.op_hand_count >= 7
            and not c.state.supporterPlayed):
        return False
    # NUNCA en NUESTRO primer turno (user, log 88461779 paso 16 vs Alakazam,
    # PERDIDA): en el primer turno Meowth ex se baja SOLO para traer Lillie's
    # Determination. Sin este corte, este motor armaba la cadena Ultra Ball ->
    # Meowth ex -> Xerosic ya en el turno 1 (la mano rival recien robada ya
    # supera las 7 cartas), gastando la Ultra Ball, el Meowth y el turno para
    # cavar una disrupcion que ni siquiera se puede jugar (yendo primeros el
    # Supporter no es jugable) mientras el tablero se queda sin desarrollar.
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
    """¿El Meowth ex que cavaria la Ultra Ball llegaria a JUGARSE este turno?

    La Ultra Ball solo se juega por un Pokemon que vayamos a JUGAR (user,
    registro_004 paso 35 vs Cynthia's Garchomp, GANADA con error). Un Meowth ex
    vale EXCLUSIVAMENTE por su Last-Ditch Catch, y la regla de la carta permite
    UNA sola Last-Ditch por turno: si el Meowth ex que ya esta en juego APARECIO
    ESTE TURNO, su habilidad ya se gasto (`_meowth_ld_free` False) y un segundo
    Meowth ex no buscaria NADA -- seria un cuerpo de 2 premios en la banca a
    cambio de cero.

    La rama PLAY ya lo sabe: veta el segundo cuerpo salvo por el encadenado
    `_ub_meowth_pending` o el rescate de 21700, y AMBOS exigen `_meowth_ld_free`.
    Este bloque de la cadena UB->Meowth->Supporter era el unico lado que no lo
    comprobaba: miraba solo `field_counts < 2`. En aquel turno teniamos un Meowth
    ex recien banqueado (su Last-Ditch ya habia traido el Boss's Orders) y el
    activo cargado para noquear; la Ultra Ball cavo un SEGUNDO Meowth ex quemando
    Tapu Bulu + Xerosic en el descarte, y la rama PLAY lo veto acto seguido
    (score -1): el cuerpo se quedo muerto en la mano.

    Con la Last-Ditch libre (ningun Meowth en juego, o solo copias de turnos
    anteriores) la cadena SI se completa -- ese es el caso del registro_004 paso
    53 vs Alakazam, donde el 2o Meowth buscado por Ultra Ball si se baja."""
    if not ctx.meowth_ld_free:
        return False
    return ctx.field_counts.get(Meowth_ex, 0) < 2


@dataclass
class _CtxUBHydrapple:
    hand: dict            # hand_counts
    campo: dict           # field_counts
    evolvable: dict       # _ub_evolvable (foto de inicio de turno)
    dipplin_evo_atk: bool         # Dipplin activo evoluciona Y ataca este turno
    op_ex_immune_active: bool
    op_ex_immune_bench: bool
    hydra_dead_prefer_meowth: bool  # _ub_hydra_dead_prefer_meowth


@dataclass
class _CtxUBMeowth:
    hand: dict                  # hand_counts
    campo: dict                 # field_counts
    bench_count: int
    turno: int                  # state.turn
    watchtower: bool            # watchtower_in_play (anula Last-Ditch)
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
    ld_free: bool = True        # _meowth_ld_free (Last-Ditch sin gastar)
    # La Ultra Ball se pago para cavar el Meowth ex que se bajara MAÑANA, bajo
    # el bloqueo de Items del Itchy Pollen (ver `_ub_meowth_para_manana`): el
    # fetch DEBE completar esa compra aunque hoy la Last-Ditch no produzca nada.
    meowth_manana: bool = False


@dataclass
class _CtxUBFetch:
    hand: dict
    campo: dict
    evolvable: dict            # _ub_evolvable (foto de inicio de turno)
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
]
