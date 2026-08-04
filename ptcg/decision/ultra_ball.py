"""Ultra Ball: el orquestador de busqueda y sus vetos.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.motor.reglas import _Ajuste, _ReglaFija
from ptcg.cartas.ids import Applin, Bayleef, Chikorita, Dipplin, Fezandipiti_ex, Forest_of_Vitality, Hydrapple_ex, Lillie_Determination, Meganium, Meowth_ex, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.decision.estadios import _forest_disponible
from ptcg.calculo.energia import _grass_attach_unit
from ptcg.calculo.dano import _attacker_base_damage, _our_effective_damage
from ptcg.estado.agente import ESTADO
from ptcg.decision.disrupcion import _sello_merece_jugarse
from ptcg.cartas.ids import Applin, Basic_Grass_Energy, Bayleef, Boss_Orders, Chikorita, Dawn, Dipplin, Fezandipiti_ex, Forest_of_Vitality, Hydrapple_ex, Lanas_Aid, Lillie_Determination, Meganium, Meowth_ex, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Unfair_Stamp
from ptcg.calculo.tablero import _active_of
from ptcg.calculo.energia import count_total_grass_energy
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


def _eval_ub_best_target(field_counts, hand_counts, meganium_in_play, has_hydrapple,
                         forest_in_play, op_has_ex_immune_active, op_has_ex_immune_bench,
                         op_prize, bench_count, state, ko_last_turn,
                         _best_supp_in_mazo_val, supporters_in_hand, hand_is_weak,
                         has_energy_for_teal, _we_go_first=False,
                         _best_supp_in_hand_val=0,
                         op_is_crustle_deck=False, op_is_cornerstone_deck=False,
                         op_active_is_budew=False, meowth_ability_lock=False,
                         op_hand_count=None):
    ub_best_target = 0

    _bench_full = (bench_count >= 5)

    _hand_total = sum(hand_counts.values())

    if state.turn == 2 and not _we_go_first:

        if (not state.supporterPlayed and
                hand_counts.get(Lillie_Determination, 0) == 0 and
                field_counts.get(Meowth_ex, 0) < 2 and
                bench_count < 5 and
                not meowth_ability_lock and
                ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0):
            _lillie_in_mazo = ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0)
            if _lillie_in_mazo > 0:
                ub_best_target = max(ub_best_target, 1100)
            elif any(ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(sid, {}).get(ESTADO_MAZO, 0) > 0
                     for sid in (Dawn, Lanas_Aid)):
                ub_best_target = max(ub_best_target, 950)

        if bench_count == 0:
            _has_basic_in_hand_t1s = any(hand_counts.get(pid, 0) >= 1
                                         for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                                     Tapu_Bulu, Meowth_ex, Fezandipiti_ex,
                                                     Pinsir))
            _active_is_weak_basic = any(field_counts.get(pid, 0) >= 1
                                        for pid in (Applin, Chikorita))
            if not _has_basic_in_hand_t1s and _active_is_weak_basic:
                if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0:
                    ub_best_target = max(ub_best_target, 1050)

        return ub_best_target

    if state.turn == 1 and _we_go_first:
        # Regla vs Budew activo: si el rival abre con Budew en el ACTIVO, su
        # ataque Itchy Pollen nos bloqueara los Items durante NUESTRO proximo
        # turno. Por eso, si no tenemos Lillie's en mano pero si una Ultra Ball,
        # debemos usarla AHORA para buscar Meowth ex, jugarlo y que su habilidad
        # nos traiga una Lillie's (supporter, jugable aun bajo el bloqueo de
        # items) para el siguiente turno. Prioridad maxima e independiente del
        # desarrollo del banco.
        if (op_active_is_budew and
                hand_counts.get(Lillie_Determination, 0) == 0 and
                hand_counts.get(Meowth_ex, 0) == 0 and
                field_counts.get(Meowth_ex, 0) == 0 and
                bench_count < 5 and
                not state.supporterPlayed and
                not meowth_ability_lock and
                ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0 and
                ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0):
            return 1100

        _has_basic_in_hand = any(hand_counts.get(pid, 0) >= 1
                                 for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                             Tapu_Bulu, Fezandipiti_ex, Pinsir))
        if bench_count >= 1 or _has_basic_in_hand:
            return 0

        _best_t1_val = 0

        if (field_counts.get(Teal_Mask_Ogerpon_ex, 0) == 0 and
                ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0):
            _val = 950
            if hand_counts.get(Basic_Grass_Energy, 0) >= 1:
                _val = 1000
            _best_t1_val = max(_best_t1_val, _val)

        if (field_counts.get(Chikorita, 0) == 0 and
                ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Chikorita, {}).get(ESTADO_MAZO, 0) > 0):
            _val = 850
            if field_counts.get(Applin, 0) >= 1 or field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1:
                _val = 900
            if hand_counts.get(Bayleef, 0) >= 1:
                _val += 50
            _best_t1_val = max(_best_t1_val, _val)

        if (field_counts.get(Applin, 0) == 0 and
                ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) > 0):
            _val = 800
            if field_counts.get(Chikorita, 0) >= 1 or field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1:
                _val = 850
            if hand_counts.get(Dipplin, 0) >= 1:
                _val += 50
            _best_t1_val = max(_best_t1_val, _val)

        ub_best_target = max(ub_best_target, _best_t1_val)
        return ub_best_target

    # El Sello solo bloquea la cadena de Supporters si de verdad va a jugarse
    # (regla de carta: `_sello_merece_jugarse`). Sin `op_hand_count` el gate
    # cae al comportamiento previo.
    _stamp_blocks_supp_chain = (ko_last_turn
                                and hand_counts.get(Unfair_Stamp, 0) >= 1
                                and _sello_merece_jugarse(op_hand_count,
                                                          _hand_total))

    _supp_in_hand_is_inferior = False
    if supporters_in_hand >= 1 and _best_supp_in_mazo_val >= 600:

        if _best_supp_in_mazo_val > _best_supp_in_hand_val + 100:
            _supp_in_hand_is_inferior = True

    meowth_viable = (
        not _stamp_blocks_supp_chain and
        not (state.turn <= 1 and _we_go_first) and
        not state.supporterPlayed and
        not meowth_ability_lock and
        (supporters_in_hand == 0 or _supp_in_hand_is_inferior) and
        field_counts.get(Meowth_ex, 0) == 0 and
        bench_count < 5 and
        ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0 and
        _best_supp_in_mazo_val > 200
    )

    if not meowth_viable and op_is_crustle_deck:
        _boss_in_mazo = ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Boss_Orders, {}).get(ESTADO_MAZO, 0) > 0
        _boss_val_ub = _best_supp_in_mazo_val
        if (_boss_in_mazo and _boss_val_ub >= 900 and
                not state.supporterPlayed and
                not meowth_ability_lock and
                field_counts.get(Meowth_ex, 0) == 0 and
                bench_count < 5 and
                hand_counts.get(Boss_Orders, 0) == 0 and
                ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0):
            meowth_viable = True
    if meowth_viable:
        meowth_val = _best_supp_in_mazo_val
        if state.turn <= 2:
            meowth_val += 200
        elif hand_is_weak:
            meowth_val += 100
        ub_best_target = max(ub_best_target, meowth_val)

    if has_energy_for_teal and field_counts.get(Teal_Mask_Ogerpon_ex, 0) < 2 and bench_count < 5:
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0:
            val = 650
            if field_counts.get(Teal_Mask_Ogerpon_ex, 0) == 0:
                val = 750
            if hand_counts.get(Basic_Grass_Energy, 0) >= 2:
                val += 100
            ub_best_target = max(ub_best_target, val)

    if (has_energy_for_teal and
            field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2 and
            bench_count < 5 and
            field_counts.get(Hydrapple_ex, 0) >= 1):
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0:

            _td_dmg_bonus = 60 if meganium_in_play else 30
            val = 500 + _td_dmg_bonus * 2

            if hand_counts.get(Basic_Grass_Energy, 0) >= 2:
                val += 150

            if field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2:
                val += 50
            ub_best_target = max(ub_best_target, val)

    # NO usa `_evolvable_counts` (la foto depurada): MEDIDO Y REVERTIDO.
    # Ver la nota de alcance en `_evolvable_counts`.
    _evolvable = ESTADO._field_at_turn_start if (not forest_in_play and ESTADO._field_at_turn_start) else field_counts

    if not meganium_in_play:
        if _evolvable.get(Bayleef, 0) >= 1:
            # Mismo criterio que las ramas de Bayleef / Dipplin de abajo (y que
            # `_ub_evolve_needs_search`): si la evolucion YA esta en la mano, la
            # linea evoluciona SIN Ultra Ball y buscar una 2a copia no aporta
            # nada -- solo quema la carta y 2 descartes (user, registro_004 paso
            # 35 vs Cynthia's Garchomp: Meganium en mano y aun asi cavaba).
            if (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0
                    and hand_counts.get(Meganium, 0) == 0):
                ub_best_target = max(ub_best_target, 1000)
        elif _evolvable.get(Chikorita, 0) >= 1 and field_counts.get(Bayleef, 0) >= 1:

            if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0:
                if forest_in_play:

                    ub_best_target = max(ub_best_target, 1000)
                else:
                    # Bayleef recien evolucionado ESTE turno (habia Chikorita al
                    # inicio del turno) y SIN Forest: no se podra evolucionar a
                    # Meganium hasta el PROXIMO turno. Buscar Meganium ahora es solo
                    # preparacion, no aporta este turno, asi que se rebaja la
                    # prioridad para no gastar Ultra Ball + 2 descartes en una pieza
                    # inusable si hay mejores objetivos o pocos descartes seguros
                    # (con >=2 descartes seguros y sin mejor objetivo aun se busca).
                    ub_best_target = max(ub_best_target, 280)
        elif _evolvable.get(Chikorita, 0) >= 1:

            if (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0
                    and hand_counts.get(Bayleef, 0) == 0):
                # Solo vale buscar Bayleef si NO tenemos ya uno en la mano:
                # con una Chikorita en juego, un unico Bayleef basta para
                # evolucionarla. Si ya lo tenemos, la Ultra Ball no aporta nada
                # para esta linea (y gastaria 2 cartas de descarte por un duplicado).
                ub_best_target = max(ub_best_target, 850)

            elif (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0 and
                  (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                  hand_counts.get(Bayleef, 0) >= 1):
                _prot = 1
                if not forest_in_play:
                    _prot += 1
                if _hand_total - 1 - _prot >= 2:
                    ub_best_target = max(ub_best_target, 900)

        elif not _bench_full and field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) == 0:
            if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Chikorita, {}).get(ESTADO_MAZO, 0) > 0:
                _has_mega_evo_in_mazo = (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0 or
                                         ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0)
                _has_mega_evo_in_hand = (hand_counts.get(Bayleef, 0) >= 1 or hand_counts.get(Meganium, 0) >= 1)
                _forest_available = (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1)

                _can_chain_mega = False
                if _forest_available and hand_counts.get(Bayleef, 0) >= 1:
                    _prot = 1
                    if not forest_in_play:
                        _prot += 1
                    if _hand_total - 1 - _prot >= 2:
                        _can_chain_mega = True
                        ub_best_target = max(ub_best_target, 700)
                if not _can_chain_mega:
                    if _has_mega_evo_in_mazo or _has_mega_evo_in_hand:
                        ub_best_target = max(ub_best_target, 500)
                    else:
                        ub_best_target = max(ub_best_target, 200)

    if not has_hydrapple:
        if _evolvable.get(Dipplin, 0) >= 1:
            # Con el Hydrapple ex YA en la mano la linea evoluciona sin Ultra
            # Ball (ver la rama gemela de Meganium arriba).
            if (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                    Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0
                    and hand_counts.get(Hydrapple_ex, 0) == 0):
                ub_best_target = max(ub_best_target, 950)
        elif _evolvable.get(Applin, 0) >= 1 and field_counts.get(Dipplin, 0) >= 1:

            if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0:
                if forest_in_play:
                    ub_best_target = max(ub_best_target, 950)
                else:
                    # Dipplin recien evolucionado ESTE turno (habia Applin al inicio
                    # del turno) y SIN Forest: no se podra evolucionar a Hydrapple ex
                    # hasta el PROXIMO turno. Buscar Hydrapple ahora es solo
                    # preparacion; se rebaja la prioridad para no gastar Ultra Ball +
                    # 2 descartes en una pieza inusable si hay mejores objetivos o
                    # pocos descartes seguros (con >=2 descartes seguros y sin mejor
                    # objetivo aun se busca).
                    ub_best_target = max(ub_best_target, 280)
        elif _evolvable.get(Applin, 0) >= 1:

            if (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0
                    and hand_counts.get(Dipplin, 0) == 0):
                # Mismo criterio que Bayleef: no buscar Dipplin si ya hay uno en
                # la mano (un Dipplin basta para evolucionar la unica Applin).
                ub_best_target = max(ub_best_target, 800)

            elif (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0 and
                  (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                  hand_counts.get(Dipplin, 0) >= 1):
                _prot = 1
                if not forest_in_play:
                    _prot += 1
                if _hand_total - 1 - _prot >= 2:
                    ub_best_target = max(ub_best_target, 850)
        elif not _bench_full and field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) == 0:
            if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) > 0:
                _has_hydra_evo_in_mazo = (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0 or
                                           ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0)
                _has_hydra_evo_in_hand = (hand_counts.get(Dipplin, 0) >= 1 or hand_counts.get(Hydrapple_ex, 0) >= 1)
                _forest_available = (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1)

                _can_chain_hydra = False
                if _forest_available and hand_counts.get(Dipplin, 0) >= 1:
                    _prot = 1
                    if not forest_in_play:
                        _prot += 1
                    if hand_counts.get(Hydrapple_ex, 0) >= 1:
                        _prot += 1
                    if _hand_total - 1 - _prot >= 2:
                        _can_chain_hydra = True
                        if hand_counts.get(Hydrapple_ex, 0) >= 1:

                            ub_best_target = max(ub_best_target, 950)
                        else:

                            ub_best_target = max(ub_best_target, 600)
                if not _can_chain_hydra:
                    if _has_hydra_evo_in_mazo or _has_hydra_evo_in_hand:
                        ub_best_target = max(ub_best_target, 450)
                    else:
                        ub_best_target = max(ub_best_target, 180)

    if not _bench_full and not has_energy_for_teal and field_counts.get(Teal_Mask_Ogerpon_ex, 0) < 2:
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0:
            if field_counts.get(Teal_Mask_Ogerpon_ex, 0) == 0 and bench_count <= 2:
                ub_best_target = max(ub_best_target, 350)

    if not _bench_full and field_counts.get(Tapu_Bulu, 0) == 0:
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Tapu_Bulu, {}).get(ESTADO_MAZO, 0) > 0:
            if meganium_in_play and (op_has_ex_immune_active or op_has_ex_immune_bench):
                val = 750
                if has_hydrapple:
                    val = 850
                ub_best_target = max(ub_best_target, val)

    if not _bench_full and field_counts.get(Pinsir, 0) == 0:
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Pinsir, {}).get(ESTADO_MAZO, 0) > 0:
            if op_is_crustle_deck or op_is_cornerstone_deck:
                val = 900
                if meganium_in_play:
                    val = 950
                ub_best_target = max(ub_best_target, val)

    if (not _bench_full and not _stamp_blocks_supp_chain and
            not hand_is_weak and not state.supporterPlayed and
            field_counts.get(Meowth_ex, 0) == 0 and supporters_in_hand == 0 and
            _best_supp_in_mazo_val >= 500):
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0:
            if state.turn <= 4:
                ub_best_target = max(ub_best_target, min(_best_supp_in_mazo_val, 500))

    if not _bench_full and field_counts.get(Fezandipiti_ex, 0) == 0:
        if ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Fezandipiti_ex, {}).get(ESTADO_MAZO, 0) > 0:
            if ko_last_turn:
                ub_best_target = max(ub_best_target, 1050)

    return ub_best_target


def _ub_engine_refresh_pivot(ctx) -> bool:
    """Motor UB -> Meowth -> Lillie's ANTES de gastar las energias de la mano
    (user, registro_008 pasos 58-61 vs Archaludon ex, PERDIDA): con el Hydrapple
    ex activo que NO puede NOQUEAR al rival, la banca subdesarrollada (<=1) y la
    mano con 2+ energias (forraje barato para el descarte de la Ultra Ball), el
    agente adjuntaba una energia y usaba Ripening Charge con la otra -- la mano
    quedaba en [UB, Boss's] y la Ultra Ball MORIA (sin 2 cartas que descartar).
    La linea correcta: jugar la UB YA (descartando las 2 energias), buscar
    Meowth ex, bajarlo (Last-Ditch -> Lillie's) y refrescar: la mano nueva
    desarrolla la banca, y Syrup Storm escala con el Grass TOTAL del campo.
    El adjunte del turno sigue disponible DESPUES del refresco."""
    state = ctx.state
    if state.supporterPlayed:
        return False
    hand_counts = ctx.hand_counts
    # Forraje barato: el descarte de la UB come las 2 energias, no el Boss's.
    if hand_counts.get(Basic_Grass_Energy, 0) < 2:
        return False
    # Con Lillie's o Meowth YA en mano el motor no necesita la UB ahora.
    if (hand_counts.get(Lillie_Determination, 0) >= 1
            or hand_counts.get(Meowth_ex, 0) >= 1):
        return False
    # Banca subdesarrollada: la razon de ser del refresco (crecer el campo).
    if ctx.bench_count > 1:
        return False
    cartas = ctx.cartas_en_mazo
    if cartas.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) <= 0:
        return False
    if cartas.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) <= 0:
        return False
    if ctx.field_counts.get(Meowth_ex, 0) >= 2:
        return False
    # El activo NO noquea al activo rival NI CON el adjunte del turno: sin
    # remate a la vista, ampliar recursos vale mas que cargar energia suelta.
    act = ctx.my_state.active[0] if ctx.my_state.active else None
    op_act = _active_of(ctx.op_state)
    if act is None or op_act is None:
        return False
    total_grass = count_total_grass_energy(ctx.my_state)
    eff_e = len(act.energies) + 1
    base = _attacker_base_damage(act.id, op_act, eff_e,
                                 grass_scale=total_grass + 1,
                                 teal_self_energy=eff_e,
                                 bench_count=ctx.bench_count)
    if base <= 0:
        return True
    dmg = _our_effective_damage(act, op_act, base,
                                ctx.meganium_in_play,
                                ctx.neutralization_zone_active)
    return dmg < (op_act.hp or 0)


def _ctx_ub_fetch_hydrapple(my_state, state, hand_counts, field_counts,
                            ub_evolvable, op_ex_immune_active,
                            op_ex_immune_bench, hydra_dead_prefer_meowth):
    # Si el activo es un Dipplin que puede evolucionar a Hydrapple ex y
    # atacar este turno (Syrup Storm requiere 2 de energia efectiva).
    activo = my_state.active[0] if my_state.active else None
    evo_atk = False
    if (activo is not None
            and activo.id == Dipplin
            and ub_evolvable.get(Dipplin, 0) >= 1):
        e_ahora = len(activo.energies)
        puede_adjuntar = (not state.energyAttached
                          and hand_counts.get(Basic_Grass_Energy, 0) >= 1)
        e_despues = e_ahora + _grass_attach_unit()
        req = ESTADO.ATTACK_ENERGY_REQ.get(Hydrapple_ex, 2)
        if e_ahora >= req or (puede_adjuntar and e_despues >= req):
            evo_atk = True
    return _CtxUBHydrapple(
        hand=hand_counts, campo=field_counts, evolvable=ub_evolvable,
        dipplin_evo_atk=evo_atk,
        op_ex_immune_active=op_ex_immune_active,
        op_ex_immune_bench=op_ex_immune_bench,
        hydra_dead_prefer_meowth=hydra_dead_prefer_meowth)


def _uh_preparar_hydra_prox_turno(c):
    """Con Dipplin ya en juego, Hydrapple ex esta a UNA sola evolucion:
    conviene traerlo aunque NO se pueda evolucionar este mismo turno si
    (A) Dipplin es el UNICO Pokemon de planta en juego, o (B) la linea
    Meganium se desarrollaria pero NO se puede evolucionar a Meganium este
    turno. EXCEPTO si conviene mas buscar Bayleef usable YA (Chikorita
    evolucionable, sin Bayleef en mano, con Bayleef en el mazo)."""
    grass_ids = (Applin, Dipplin, Hydrapple_ex, Chikorita, Bayleef,
                 Meganium, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Pinsir)
    grass_en_juego = sum(c.campo.get(pid, 0) for pid in grass_ids)
    dipplin_unico_grass = (grass_en_juego == c.campo.get(Dipplin, 0))

    puede_evo_meganium_ya = (
        not ESTADO.meganium_in_play and (
            c.evolvable.get(Bayleef, 0) >= 1
            or (c.evolvable.get(Chikorita, 0) >= 1
                and (ESTADO.forest_in_play
                     or c.hand.get(Forest_of_Vitality, 0) >= 1)
                and c.hand.get(Bayleef, 0) >= 1)))
    linea_meganium_dev = (
        not ESTADO.meganium_in_play and (
            c.hand.get(Bayleef, 0) >= 1
            or c.hand.get(Meganium, 0) >= 1
            or ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0
            or ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0))
    buscar_bayleef_ya = (
        not ESTADO.meganium_in_play
        and c.evolvable.get(Chikorita, 0) >= 1
        and c.hand.get(Bayleef, 0) == 0
        and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0)

    return (dipplin_unico_grass
            or (linea_meganium_dev
                and not puede_evo_meganium_ya
                and not buscar_bayleef_ya))


def _ctx_ub_fetch_meowth(hand_counts, field_counts, bench_count, turno,
                         watchtower, supp_values, prefer_meowth_develop,
                         hydra_dead_prefer_meowth, mega_dead_prefer_meowth,
                         no_attacker_prefer_meowth, t1_going_second_meowth,
                         dipplin_priority, active_cant_attack,
                         mega_line_active, dragapult,
                         supporter_played=False, ld_free=True,
                         meowth_manana=False):
    return _CtxUBMeowth(
        hand=hand_counts, campo=field_counts, bench_count=bench_count,
        turno=turno, watchtower=watchtower, supp_values=supp_values,
        lillie_in_mazo=ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
            Lillie_Determination, {}).get(ESTADO_MAZO, 0),
        any_supp_in_mazo=any(
            ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(sid, {}).get(ESTADO_MAZO, 0) > 0
            for sid in (Lillie_Determination, Boss_Orders, Dawn, Lanas_Aid)),
        prefer_meowth_develop=prefer_meowth_develop,
        hydra_dead_prefer_meowth=hydra_dead_prefer_meowth,
        mega_dead_prefer_meowth=mega_dead_prefer_meowth,
        no_attacker_prefer_meowth=no_attacker_prefer_meowth,
        t1_going_second_meowth=t1_going_second_meowth,
        dipplin_priority=dipplin_priority,
        active_cant_attack=active_cant_attack,
        mega_line_active=mega_line_active,
        dragapult=dragapult,
        supporter_played=supporter_played,
        ld_free=ld_free,
        meowth_manana=meowth_manana)


def _um_boss_engine_vs_crustle(c):
    """vs Crustle, Meowth ex sirve para traer Boss's Orders (gust) via
    Last-Ditch: sin Boss's en mano, con copias en el mazo y con un gusteo
    valioso proyectado (_supp_values)."""
    return (ESTADO.op_is_crustle_deck
            and c.hand.get(Boss_Orders, 0) == 0
            and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                Boss_Orders, {}).get(ESTADO_MAZO, 0) > 0
            and c.supp_values.get(Boss_Orders, 0) >= 900)


def _um_es_primer_turno(c):
    """NUESTRO primer turno de juego (turno 1 saliendo primeros, turno 2
    saliendo segundos)."""
    return ((c.turno == 1 and ESTADO.we_go_first)
            or (c.turno == 2 and not ESTADO.we_go_first))


def _v_ub_chikorita_arrancar(c):
    if _forest_disponible(c) and c.hand.get(Bayleef, 0) >= 1:
        return 880
    if (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0
            or ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0
            or c.hand.get(Bayleef, 0) >= 1):
        return 700
    return 200


def _v_ub_applin_arrancar(c):
    if _forest_disponible(c) and c.hand.get(Dipplin, 0) >= 1:
        return 980 if c.hand.get(Hydrapple_ex, 0) >= 1 else 800
    if (ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0
            or ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0
            or c.hand.get(Dipplin, 0) >= 1):
        return 650
    return 180


_REGLAS_UB_HYDRAPPLE = [
    # Evolucionar el Dipplin activo Y atacar este turno vale mas que el
    # refill de Fezandipiti (1050): prioridad maxima del fetch.
    _ReglaFija("dipplin_evo_ataca",
               lambda c: c.dipplin_evo_atk,
               lambda c: 1200),
    _ReglaFija("dipplin_evolucionable",
               lambda c: c.evolvable.get(Dipplin, 0) >= 1,
               lambda c: 980),
    _ReglaFija("applin_evolucionable_full_linea",
               lambda c: (c.evolvable.get(Applin, 0) >= 1
                          and (ESTADO.forest_in_play
                               or c.hand.get(Forest_of_Vitality, 0) >= 1)
                          and c.hand.get(Dipplin, 0) >= 1),
               lambda c: 900),
    _ReglaFija("applin_evolucionable",
               lambda c: c.evolvable.get(Applin, 0) >= 1,
               lambda c: 180),
    _ReglaFija("applin_en_campo",
               lambda c: c.campo.get(Applin, 0) >= 1,
               lambda c: 130),
]


_AJUSTES_UB_HYDRAPPLE = [
    _Ajuste("preparar_hydra_prox_turno",
            lambda c, s: (c.campo.get(Dipplin, 0) >= 1 and s < 860
                          and _uh_preparar_hydra_prox_turno(c)),
            lambda c, s: 860),
    # Contra mazos con INMUNIDAD A EX (p.ej. Crustle), Hydrapple ex es un
    # atacante ex que no puede danarlos: carta muerta, cede ante la linea
    # Meganium o los atacantes no-ex. EXCEPCION `evo_doomed_hittable`: si
    # evoluciona al Dipplin activo condenado y el activo rival NO es
    # inmune (Kangaskhan ex), el clamp no aplica (pivote de evolucion y
    # supervivencia: 80 PV -> 330 PV).
    _Ajuste("clamp_ex_muerto_vs_crustle",
            lambda c, s: (not (c.dipplin_evo_atk
                               and not c.op_ex_immune_active)
                          and (ESTADO.op_is_crustle_deck
                               or c.op_ex_immune_active
                               or c.op_ex_immune_bench)),
            lambda c, s: min(s, 40)),
    # Hydrapple ex quedaria muerto este turno (no ataca) y el motor de
    # refresco Meowth ex -> Lillie's esta disponible: cede la busqueda a
    # Meowth ex (1000), que rehace la mano.
    _Ajuste("cede_a_meowth_refresco",
            lambda c, s: c.hydra_dead_prefer_meowth,
            lambda c, s: min(s, 150)),
]


_REGLAS_UB_MEOWTH = [
    # PRIMER TURNO: la Ultra Ball solo cava Meowth ex para traer Lillie's
    # Determination (user, log 88461779 vs Alakazam, PERDIDA). Si la Lillie's
    # YA esta en la mano no hay nada que buscar (y el veto de jugar Meowth la
    # dejaria muerta en la mano); si NO queda ninguna en el mazo, el fetch de
    # Last-Ditch no traeria el refresco que justifica el gasto. En ambos casos
    # la Ultra Ball busca otra cosa (una linea de evolucion, un atacante). Va
    # PRIMERO: ni el motor de pivote ni el de Boss's vs Crustle levantan esta
    # regla en el primer turno.
    _ReglaFija("primer_turno_solo_para_lillie",
               lambda c: (_um_es_primer_turno(c)
                          and (c.hand.get(Lillie_Determination, 0) >= 1
                               or c.lillie_in_mazo <= 0)),
               lambda c: 10),
    # Team Rocket's Watchtower anula la habilidad de Meowth ex (Pokemon
    # incoloro): no buscarlo con la Ultra Ball.
    _ReglaFija("watchtower_anula_habilidad",
               lambda c: c.watchtower,
               lambda c: 10),
    # BLOQUEO DE ITEMS MAÑANA: la Ultra Ball se jugo EXACTAMENTE para cavar este
    # cuerpo (`_ub_meowth_para_manana`, registro_002 paso 17 vs Dragapult), asi
    # que el fetch tiene que completar la compra. Va POR ENCIMA de
    # `last_ditch_no_produce`: es cierto que hoy la habilidad no produce nada --
    # ese es el punto, el Meowth ex se baja MAÑANA, cuando ya no habra Items
    # para buscarlo y el hueco de Supporter vuelva a estar libre.
    _ReglaFija("bloqueo_de_items_manana",
               lambda c: c.meowth_manana,
               lambda c: 1250),
    # LA LAST-DITCH TIENE QUE PODER PRODUCIR ALGO ESTE TURNO (user,
    # registro_006 pasos 98-104 vs Mega Lucario ex, PERDIDA). Meowth ex vale
    # EXCLUSIVAMENTE por su Last-Ditch Catch -> Supporter; el cuerpo en si es
    # un regalo de 2 premios. Hay dos formas de que la habilidad no produzca
    # nada, y ninguna se comprobaba aqui:
    #   1) `supporter_played`: el Supporter del turno YA se jugo, asi que el
    #      que traiga el fetch se queda muerto en la mano (y la rama PLAY veta
    #      el Meowth por [[no-meowth-si-supporter-ya-jugado]]).
    #   2) `not ld_free`: algun Meowth ex en juego APARECIO ESTE TURNO, asi que
    #      la unica Last-Ditch del turno ya se gasto (ver `_meowth_ld_free` y
    #      `_ub_cavar_meowth_se_juega`).
    # En aquel turno 6 habiamos jugado Lillie's y aun asi la Ultra Ball trajo
    # Meowth ex (1000, ganando a Chikorita/Meganium/Bayleef); el agente encadeno
    # una SEGUNDA Ultra Ball para cavar el otro Meowth ex y termino atacando
    # igual, 4 cartas de mano (Forest, Xerosic, Dipplin, Lana's) por dos cuerpos
    # muertos. Va con los vetos de "la habilidad no funciona" (Watchtower) y por
    # encima de los motores de pivote, que de todas formas exigen el Supporter
    # libre (`_ub_engine_refresh_pivot` / `_alakazam_dig_xerosic_engine`).
    _ReglaFija("last_ditch_no_produce",
               lambda c: c.supporter_played or not c.ld_free,
               lambda c: 10),
    # Con Lillie's YA en mano el fetch de Meowth ex es redundante (su unico
    # proposito es buscar Lillie's); mejor una evolucion util. EXCEPCION:
    # vs Crustle, Meowth ex trae Boss's Orders (gust), no refresco. (user,
    # log 86339167 paso 23, PERDIDA vs Mega Starmie)
    _ReglaFija("lillie_ya_en_mano_redundante",
               lambda c: (c.hand.get(Lillie_Determination, 0) >= 1
                          and not _um_boss_engine_vs_crustle(c)
                          and not ESTADO._ub_engine_pivot_turn),
               lambda c: 10),
    # Motor UB->Meowth->Lillie's (registro_008 paso 58 vs Archaludon,
    # PERDIDA): la Ultra Ball se jugo POR el pivote; el fetch DEBE
    # completar la cadena. Sobre desarrollo (1000-1250) y evoluciones.
    _ReglaFija("engine_pivot_turn",
               lambda c: ESTADO._ub_engine_pivot_turn,
               lambda c: 1300),
    # Unico Pokemon en juego + sin Basico jugable + sin Lillie's en mano:
    # bajar Meowth, buscar Lillie's y refrescar.
    _ReglaFija("develop_unico_pokemon",
               lambda c: c.prefer_meowth_develop,
               lambda c: 1250),
    # La unica evolucion grande (Hydrapple ex sobre Dipplin) quedaria
    # muerta este turno: refrescar con Meowth/Lillie's abre mas opciones.
    _ReglaFija("hydra_muerto_prefiere_meowth",
               lambda c: c.hydra_dead_prefer_meowth,
               lambda c: 1000),
    # La linea Meganium no aporta este turno y no hay atacante listo.
    _ReglaFija("meganium_muerto_prefiere_meowth",
               lambda c: c.mega_dead_prefer_meowth,
               lambda c: 1000),
    # Sin atacante USABLE este turno (ni activo que ataque ni banca
    # subible): el refresco supera a una evolucion sin ataque. >1000 para
    # ganar a un Meganium jugable. (registro_004 paso 29 vs Mega Starmie)
    _ReglaFija("sin_atacante_prefiere_meowth",
               lambda c: c.no_attacker_prefer_meowth,
               lambda c: 1250),
    _ReglaFija("t1_saliendo_segundos",
               lambda c: c.t1_going_second_meowth,
               lambda c: 1200),
    _ReglaFija("t1_saliendo_primeros_no",
               lambda c: c.turno == 1 and ESTADO.we_go_first,
               lambda c: 10),
    _ReglaFija("ya_dos_meowth_en_juego",
               lambda c: c.campo.get(Meowth_ex, 0) >= 2,
               lambda c: 10),
    _ReglaFija("un_meowth_y_activo_ataca",
               lambda c: (c.campo.get(Meowth_ex, 0) >= 1
                          and not c.active_cant_attack),
               lambda c: 10),
    _ReglaFija("banca_llena",
               lambda c: c.bench_count >= 5,
               lambda c: 10),
    # Se cumple una condicion que privilegia a Dipplin: Meowth cede.
    _ReglaFija("cede_a_dipplin_prioritario",
               lambda c: c.dipplin_priority,
               lambda c: 10),
    _ReglaFija("linea_mega_activa_con_lillie",
               lambda c: c.mega_line_active and c.lillie_in_mazo > 0,
               lambda c: 1150),
    _ReglaFija("vs_dragapult_con_lillie",
               lambda c: c.dragapult and c.lillie_in_mazo > 0,
               lambda c: 985),
    _ReglaFija("motor_boss_vs_crustle",
               _um_boss_engine_vs_crustle,
               lambda c: 1100),
    # Sin condicion que privilegie a Dipplin: Meowth ex tiene PRIORIDAD
    # para refrescar (buscar Lillie's), sin importar la mano.
    _ReglaFija("lillie_en_mazo_refresco",
               lambda c: c.lillie_in_mazo > 0,
               lambda c: 1000),
    # Otro supporter en el mazo: refrescar igualmente.
    _ReglaFija("otro_supporter_en_mazo",
               lambda c: c.any_supp_in_mazo,
               lambda c: 850),
]


_REGLAS_UB_OGERPON = [
    # Cede la busqueda a Meowth ex (refresco de mano): solo se traeria
    # Ogerpon ex aqui si YA tuvieramos Lillie's en la mano.
    _ReglaFija("cede_a_meowth_develop",
               lambda c: c.prefer_meowth_develop,
               lambda c: 200),
    _ReglaFija("t1_segundos_necesita_ogerpon",
               lambda c: c.t1_going_second_need_ogerpon,
               lambda c: 1050),
    _ReglaFija("t1_primeros_necesita_basico",
               lambda c: c.t1_going_first_need_basic,
               _v_ub_ogerpon_t1_primeros),
    _ReglaFija("ya_dos_ogerpon",
               lambda c: c.campo.get(Teal_Mask_Ogerpon_ex, 0) >= 2,
               lambda c: 350 if (c.has_energy_for_teal
                                 and c.bench_count < 5) else 15),
    _ReglaFija("energia_para_teal_dance",
               lambda c: c.has_energy_for_teal and c.bench_count < 5,
               _v_ub_ogerpon_teal),
    _ReglaFija("primer_ogerpon_banca_corta",
               lambda c: (c.campo.get(Teal_Mask_Ogerpon_ex, 0) == 0
                          and c.bench_count <= 2),
               lambda c: 300),
]


_REGLAS_UB_MEGANIUM = [
    _ReglaFija("meganium_ya_en_juego",
               lambda c: ESTADO.meganium_in_play,
               lambda c: 25),
    # vs Cornerstone: Wild Growth duplica cada Planta y baja el coste de
    # Tapu Bulu -- el UNICO atacante que dana a Cornerstone -- de 4 Plantas
    # fisicas a 2. Con la linea ya iniciada en juego, completarla es la
    # busqueda prioritaria aunque Meganium en si no pueda danarlo.
    _ReglaFija("linea_mega_habilita_tapu_vs_cornerstone",
               lambda c: (ESTADO.op_is_cornerstone_deck
                          and (c.campo.get(Chikorita, 0) >= 1
                               or c.campo.get(Bayleef, 0) >= 1)),
               lambda c: 1050),
    _ReglaFija("bayleef_evolucionable",
               lambda c: c.evolvable.get(Bayleef, 0) >= 1,
               lambda c: 1000),
    _ReglaFija("cadena_chikorita_completa",
               lambda c: (c.evolvable.get(Chikorita, 0) >= 1
                          and _forest_disponible(c)
                          and c.hand.get(Bayleef, 0) >= 1),
               lambda c: 950),
    _ReglaFija("chikorita_evolucionable",
               lambda c: c.evolvable.get(Chikorita, 0) >= 1,
               lambda c: 200),
    _ReglaFija("chikorita_en_campo",
               lambda c: c.campo.get(Chikorita, 0) >= 1,
               lambda c: 150),
]


_REGLAS_UB_BAYLEEF = [
    _ReglaFija("meganium_ya_en_juego",
               lambda c: ESTADO.meganium_in_play,
               lambda c: 20),
    _ReglaFija("bayleef_ya_en_campo",
               lambda c: c.campo.get(Bayleef, 0) >= 1,
               lambda c: 20),
    # Ya hay un Bayleef EN LA MANO: buscar otro es redundante (uno basta
    # para la unica Chikorita); no malgastar la UB ni su descarte.
    _ReglaFija("bayleef_ya_en_mano",
               lambda c: c.hand.get(Bayleef, 0) >= 1,
               lambda c: 20),
    # vs Cornerstone, Bayleef es el paso intermedio hacia Meganium (que
    # duplica la Planta y deja a Tapu Bulu atacando con 2 fisicas) y ademas
    # es uno de los dos cuerpos SIN habilidad que si le hacen dano.
    _ReglaFija("linea_mega_vs_cornerstone",
               lambda c: (ESTADO.op_is_cornerstone_deck
                          and c.campo.get(Chikorita, 0) >= 1),
               lambda c: 1000),
    _ReglaFija("chikorita_evolucionable",
               lambda c: c.evolvable.get(Chikorita, 0) >= 1,
               lambda c: 950 if (c.hand.get(Meganium, 0) >= 1
                                 and ESTADO.forest_in_play) else 850),
    _ReglaFija("chikorita_en_campo",
               lambda c: c.campo.get(Chikorita, 0) >= 1,
               lambda c: 200),
]


_REGLAS_UB_DIPPLIN = [
    _ReglaFija("hydrapple_ya_en_juego",
               lambda c: c.has_hydrapple,
               lambda c: 20),
    _ReglaFija("dipplin_ya_en_campo",
               lambda c: c.campo.get(Dipplin, 0) >= 1,
               lambda c: 20),
    # Mismo criterio que Bayleef: duplicado redundante.
    _ReglaFija("dipplin_ya_en_mano",
               lambda c: c.hand.get(Dipplin, 0) >= 1,
               lambda c: 20),
    # Solo se privilegia a Dipplin con _dipplin_priority; si no, Meowth ex
    # refresca mejor y Dipplin baja para no robarle la busqueda.
    _ReglaFija("applin_evolucionable",
               lambda c: c.evolvable.get(Applin, 0) >= 1,
               lambda c: ((920 if (c.hand.get(Hydrapple_ex, 0) >= 1
                                   and ESTADO.forest_in_play) else 800)
                          if c.dipplin_priority else 150)),
    _ReglaFija("applin_en_campo",
               lambda c: c.campo.get(Applin, 0) >= 1,
               lambda c: 200),
    _ReglaFija("rival_anti_ex",
               lambda c: c.op_ex_immune_active or c.op_ex_immune_bench,
               lambda c: 600 if c.evolvable.get(Applin, 0) >= 1 else 150),
]


_REGLAS_UB_CHIKORITA = [
    _ReglaFija("t1_primeros_necesita_basico",
               lambda c: c.t1_going_first_need_basic,
               _v_ub_chikorita_t1),
    _ReglaFija("meganium_ya_en_juego",
               lambda c: ESTADO.meganium_in_play,
               lambda c: 30),
    _ReglaFija("linea_meganium_ya_iniciada",
               lambda c: (c.campo.get(Chikorita, 0)
                          + c.campo.get(Bayleef, 0)
                          + c.campo.get(Meganium, 0)) > 0,
               lambda c: 150),
    _ReglaFija("arrancar_linea_meganium",
               lambda c: True,
               _v_ub_chikorita_arrancar),
]


_REGLAS_UB_APPLIN = [
    _ReglaFija("t1_primeros_necesita_basico",
               lambda c: c.t1_going_first_need_basic,
               _v_ub_applin_t1),
    _ReglaFija("hydrapple_ya_en_juego",
               lambda c: c.has_hydrapple,
               lambda c: 25),
    _ReglaFija("linea_hydra_ya_iniciada",
               lambda c: (c.campo.get(Applin, 0)
                          + c.campo.get(Dipplin, 0)
                          + c.campo.get(Hydrapple_ex, 0)) > 0,
               lambda c: 120),
    _ReglaFija("arrancar_linea_hydra",
               lambda c: True,
               _v_ub_applin_arrancar),
]


_REGLAS_UB_TAPU = [
    _ReglaFija("tapu_ya_en_campo",
               lambda c: c.campo.get(Tapu_Bulu, 0) >= 1,
               lambda c: 15),
    # Atacante no-ex contra rivales inmunes a ex, con Meganium duplicando
    # su energia; mejor aun si Hydrapple ex ya cubre el rol ex.
    _ReglaFija("anti_ex_con_meganium",
               lambda c: (ESTADO.meganium_in_play
                          and (c.op_ex_immune_active
                               or c.op_ex_immune_bench)),
               lambda c: 850 if c.has_hydrapple else 750),
]


_REGLAS_UB_PINSIR = [
    _ReglaFija("anti_ex",
               lambda c: (c.campo.get(Pinsir, 0) == 0
                          and (ESTADO.op_is_crustle_deck
                               or ESTADO.op_is_cornerstone_deck)),
               lambda c: 900),
]


_REGLAS_UB_FEZ = [
    # Refill tras KO con Flip the Script (Fezandipiti ex de banca roba 3 al
    # noquearnos). Es buena busqueda SI ya tenemos un atacante usable o si el
    # motor Meowth ex -> Last-Ditch -> Lillie's NO esta disponible. Pero si NO
    # hay atacante usable y AUN queda Meowth ex + Lillie's en el mazo (motor de
    # refresco intacto, `no_attacker_prefer_meowth`), es preferible traer Meowth
    # ex: bajarlo busca Lillie's y rehace TODA la mano (hasta 8 cartas), abriendo
    # muchas mas opciones que el robo de 3 de Fezandipiti (user). Fez cede y su
    # rama cae al defecto (10); Meowth ex (`sin_atacante_prefiere_meowth`=1250 u
    # otras ramas de refresco) gana la busqueda. Deck-agnostico.
    _ReglaFija("refill_tras_ko",
               lambda c: (c.campo.get(Fezandipiti_ex, 0) == 0
                          and ESTADO.ko_last_turn and c.bench_count < 5
                          and not c.no_attacker_prefer_meowth),
               lambda c: 1050),
]

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
    '_ub_engine_refresh_pivot',
    '_uh_preparar_hydra_prox_turno',
    '_um_boss_engine_vs_crustle',
    '_um_es_primer_turno',
    '_v_ub_chikorita_arrancar',
    '_v_ub_applin_arrancar',
    '_eval_ub_best_target',
    '_ctx_ub_fetch_hydrapple',
    '_ctx_ub_fetch_meowth',
    '_AJUSTES_UB_HYDRAPPLE',
    '_REGLAS_UB_APPLIN',
    '_REGLAS_UB_BAYLEEF',
    '_REGLAS_UB_CHIKORITA',
    '_REGLAS_UB_DIPPLIN',
    '_REGLAS_UB_FEZ',
    '_REGLAS_UB_HYDRAPPLE',
    '_REGLAS_UB_MEGANIUM',
    '_REGLAS_UB_MEOWTH',
    '_REGLAS_UB_OGERPON',
    '_REGLAS_UB_PINSIR',
    '_REGLAS_UB_TAPU',
]
