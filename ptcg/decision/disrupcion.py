"""Disrupcion de la mano rival: Xerosic's Machinations y Unfair Stamp.

Van JUNTOS a proposito: la regla de orden -- Xerosic ANTES del Sello, porque
el Sello deja al rival en 2 cartas igual y lo unico que gana el orden son las
cartas que Xerosic manda al descarte PARA SIEMPRE -- hace que cada scorer
consulte al otro. Separarlos produce un import circular.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.calculo.tablero import _active_of
from ptcg.cartas.ids import Alakazam_ex, Applin, Basic_Grass_Energy, Bayleef, Boss_Orders, Bug_Catching_Set, Chikorita, Dipplin, Fezandipiti_ex, Forest_of_Vitality, Hydrapple_ex, Lillie_Determination, Meganium, Meowth_ex, Night_Stretcher, Poke_Pad, SCORE_VETO, STAMP_MAX_HAND_SACRIFICADA, STAMP_MIN_OP_HAND, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball, Unfair_Stamp, XEROSIC_SCORE_ALAKAZAM, XEROSIC_SCORE_GENERIC, XEROSIC_SCORE_LAST_RESORT, XEROSIC_SCORE_SOBRE_BOSS, XEROSIC_STAMP_ORDEN_MIN_OP_HAND, Xerosic_Machinations
from ptcg.estado.claves import ESTADO_MAZO
from ptcg.motor.contexto import DecisionContext
from ptcg.motor.reglas import _Ajuste, _ReglaFija, _resolver_con_traza


def _sello_merece_jugarse(op_hand_count, my_hand_len) -> bool:
    """Regla de carta del Unfair Stamp (user, agosto 2026): el Sello solo se
    juega si DISRUMPE al rival (mano rival >= `STAMP_MIN_OP_HAND`, porque los
    deja en 2) o si el REFRESCO es barato (sacrificamos <= `STAMP_MAX_HAND_
    SACRIFICADA` cartas, que es la mano SIN el propio Sello). Ver el bloque de
    constantes para el razonamiento completo.

    Vale para CUALQUIER mazo rival: la carta se comporta igual en todos los
    matchups, asi que aqui no entra ninguna whitelist.

    Con `None` (llamador sin ese dato a mano) se devuelve True: la regla solo
    RESTA jugadas, nunca inventa una.
    """
    if op_hand_count is None or my_hand_len is None:
        return True
    return (op_hand_count >= STAMP_MIN_OP_HAND
            or max(0, my_hand_len - 1) <= STAMP_MAX_HAND_SACRIFICADA)


def _stamp_pendiente(c) -> bool:
    """Sello JUGABLE y que ademas MERECE jugarse este turno.

    Fuente UNICA de los vetos de orden que le ceden el paso (Boss's, Lillie's,
    Lana's, Dawn, Xerosic, la cadena Meowth -> Last-Ditch y la habilidad de
    Fezandipiti). Antes bastaba con "nos noquearon + el Sello sigue en mano",
    pero desde que `_sello_merece_jugarse` puede VETAR el Sello ese gate solo
    habria paralizado el turno: se cedia el paso a una carta que ya no se iba a
    jugar. Al compartir predicado, cuando el Sello espera (mano rival <= 2 y
    mano propia grande) los Supporters siguen su curso normal -- y si la mano
    baja de 5 jugando items, el Sello vuelve a estar disponible en el mismo
    turno."""
    return (c.ko_last_turn
            and c.hand_counts.get(Unfair_Stamp, 0) >= 1
            and _sello_merece_jugarse(c.op_hand_count, c.my_hand_len))


def _us_pokemon_jugable(c):
    if c.bench_count >= 5:
        return False
    h, f = c.hand_counts, c.field_counts
    if (h.get(Chikorita, 0) >= 1 and
            f.get(Chikorita, 0) + f.get(Bayleef, 0) + f.get(Meganium, 0) == 0):
        return True
    if (h.get(Applin, 0) >= 1 and
            f.get(Applin, 0) + f.get(Dipplin, 0) == 0):
        return True
    if (h.get(Teal_Mask_Ogerpon_ex, 0) >= 1 and
            f.get(Teal_Mask_Ogerpon_ex, 0) < 2):
        return True
    if h.get(Tapu_Bulu, 0) >= 1 and f.get(Tapu_Bulu, 0) == 0:
        return True
    if (h.get(Meowth_ex, 0) >= 1 and f.get(Meowth_ex, 0) == 0
            and not c.ko_last_turn):
        return True
    if h.get(Fezandipiti_ex, 0) >= 1 and f.get(Fezandipiti_ex, 0) == 0:
        return True
    return False


def _us_evo_jugable(c):
    h, f = c.hand_counts, c.field_counts
    if h.get(Meganium, 0) >= 1 and f.get(Bayleef, 0) >= 1 and not c.meganium_in_play:
        return True
    if h.get(Bayleef, 0) >= 1 and f.get(Chikorita, 0) >= 1:
        return True
    if h.get(Hydrapple_ex, 0) >= 1 and f.get(Dipplin, 0) >= 1:
        return True
    if h.get(Dipplin, 0) >= 1 and f.get(Applin, 0) >= 1:
        return True
    return False


def _us_item_jugable(c):
    if c.itchy_pollen_active:
        return False
    h = c.hand_counts
    return (h.get(Bug_Catching_Set, 0) >= 1
            or (h.get(Ultra_Ball, 0) >= 1 and c.my_hand_len >= 3)
            or h.get(Night_Stretcher, 0) >= 1
            or h.get(Poke_Pad, 0) >= 1)


def _us_bonus_matchup(c):
    if c.op_is_alakazam_deck:
        return 400
    if c.op_is_control_deck or c.op_is_slowking_deck:
        return 350
    if c.op_is_gardevoir_deck:
        return 300
    if c.op_is_zoroark_deck:
        return 250
    return 0


def _xr_antes_del_sello(c):
    """¿Xerosic's Machinations se juega ANTES del Unfair Stamp?

    Los dos caben en el MISMO turno -- el Sello es un ITEM (ACE SPEC) y
    Xerosic un Supporter --, asi que aqui no se elige una carta: se elige el
    ORDEN. Y las dos hacen cosas distintas con la mano rival:

      * Unfair Stamp la **BARAJA de vuelta a su mazo** y le da 2 cartas.
      * Xerosic la **DESCARTA** hasta dejarle 3.

    Jugando Xerosic PRIMERO el rival pierde `op_hand - 3` cartas para siempre
    y el Sello lo deja igualmente en 2: mismo tablero al cerrar el turno, con
    medio mazo rival en el descarte. Al reves esas cartas vuelven al mazo y el
    Sello ademas baraja NUESTRO Xerosic (registro_008 paso 90 vs Alakazam: el
    Sello se llevo Boss's y Xerosic, y solo se recupero uno por suerte).

    El coste es real -- el hueco de Supporter se gasta ANTES del refresco del
    Sello, asi que las 5 cartas nuevas ya no pueden pagar otro Supporter --,
    de ahi el umbral `XEROSIC_STAMP_ORDEN_MIN_OP_HAND`: solo cuando lo que se
    quema supera una mano entera. Se auto-revoca: en cuanto Xerosic se juega,
    `supporterPlayed` pasa a True y el Sello recupera su score normal en el
    mismo turno.
    """
    return (c.ko_last_turn
            and c.hand_counts.get(Unfair_Stamp, 0) >= 1
            and c.hand_counts.get(Xerosic_Machinations, 0) >= 1
            and not c.state.supporterPlayed
            and c.op_hand_count >= XEROSIC_STAMP_ORDEN_MIN_OP_HAND)


_REGLAS_STAMP_PLAY = [
    # REGLA DE CARTA (user, agosto 2026): sin disrupcion (mano rival <= 2) ni
    # refresco barato (sacrificamos > 4 cartas) el Sello NO se juega. No es un
    # veto de orden: no lo revoca ninguna otra carta del turno, solo cambia si
    # cambia el tablero (p.ej. la mano propia baja jugando items). Ver
    # `_sello_merece_jugarse`.
    _ReglaFija("sin_disrupcion_ni_refresco",
               lambda c: not _sello_merece_jugarse(c.op_hand_count,
                                                   c.my_hand_len),
               lambda c: SCORE_VETO),
    # VETO DE ORDEN, no de valor (user, jul 2026): con la mano rival gigante,
    # Xerosic va primero y el Sello espera al mismo turno. Se exige que el
    # Xerosic vaya a jugarse DE VERDAD (score por encima del ultimo recurso):
    # si alguno de sus guards lo tumba a `XEROSIC_SCORE_LAST_RESORT` -- p.ej.
    # `alakazam_cede_a_gusteo_ganador`, donde el turno lo decide un Boss's --
    # el Sello no le cede el paso a nadie y se juega normal. Ver
    # `_xr_antes_del_sello`.
    _ReglaFija("cede_el_orden_a_xerosic",
               lambda c: (_xr_antes_del_sello(c)
                          and _score_xerosic_play(c)
                          > XEROSIC_SCORE_LAST_RESORT),
               lambda c: SCORE_VETO),
    # Regla (user): con Lillie's en mano y rival con <= 3 cartas, NO jugar
    # el Sello: su disrupcion aporta poco y refrescar NUESTRA mano rinde
    # mas (el Stamp barajaria la Lillie's; jugadas excluyentes).
    _ReglaFija("cede_a_lillie_mano_rival_corta",
               lambda c: (c.hand_counts.get(Lillie_Determination, 0) >= 1
                          and c.op_hand_count <= 3
                          and not c.state.supporterPlayed),
               lambda c: SCORE_VETO),
    # El valor base sube cuanto MENOS uso alternativo tenga la mano este
    # turno (Pokemon/evo < item < energia/estadio < nada = 7500).
    _ReglaFija("mano_con_pokemon_o_evo",
               lambda c: _us_pokemon_jugable(c) or _us_evo_jugable(c),
               lambda c: 2000),
    _ReglaFija("mano_con_item",
               _us_item_jugable,
               lambda c: 2500),
    _ReglaFija("mano_con_energia_o_estadio",
               lambda c: ((c.hand_counts[Basic_Grass_Energy] >= 1
                           and not c.state.energyAttached)
                          or (c.hand_counts.get(Forest_of_Vitality, 0) >= 1
                              and not c.forest_in_play)),
               lambda c: 3000),
]


# Todos los ajustes exigen `s > 0`: son bonificaciones al valor de una jugada
# que SE VA A HACER, no deben resucitar un veto. Sin el guard, un Sello vetado
# (SCORE_VETO = -1) salia del resolver en +399 solo por `bonus_matchup` vs
# Alakazam -- que es justo el matchup donde vive el veto de orden
# `cede_el_orden_a_xerosic`.
_AJUSTES_STAMP_PLAY = [
    _Ajuste("turno_temprano",
            lambda c, s: s > 0 and c.state.turn <= 4,
            lambda c, s: s + 300),
    _Ajuste("vamos_perdiendo_premios",
            lambda c, s: s > 0 and c.my_prize > c.op_prize + 1,
            lambda c, s: s + 200),
    _Ajuste("bonus_matchup",
            lambda c, s: s > 0 and _us_bonus_matchup(c) != 0,
            lambda c, s: s + _us_bonus_matchup(c)),
    _Ajuste("aggro_y_perdiendo",
            lambda c, s: (s > 0
                          and (c.op_is_aggro_deck or c.op_is_beedrill_deck)
                          and c.my_prize > c.op_prize),
            lambda c, s: s + 350),
]


def _score_unfair_stamp_play(ctx: DecisionContext) -> int:
    """Puntua la jugada de Unfair Stamp (refresco de mano). Cuerpo migrado al
    MOTOR DE REGLAS (fase 4): reglas y comentarios en _REGLAS_STAMP_PLAY."""
    return _resolver_con_traza("stamp->play", _REGLAS_STAMP_PLAY,
                               _AJUSTES_STAMP_PLAY, ctx, defecto=7500)


def _xr_letal_proyectado(c):
    """Disparo TEMPRANO anti-Alakazam: con mano rival 4-5, si el Alakazam YA
    esta activo y su Powerful Hand proyectado (20 x (mano + 2)) NOQUEA a
    nuestro activo, capar la mano AHORA (esperar mano >= 6 regala el KO)."""
    if not (c.op_is_alakazam_deck and 4 <= c.op_hand_count < 6
            and c.my_state.active and c.my_state.active[0] is not None):
        return False
    op_act = _active_of(c.op_state)
    return (op_act is not None and op_act.id == Alakazam_ex
            and 20 * (c.op_hand_count + 2)
                >= (c.my_state.active[0].hp or 0))


def _xr_copia_respaldo(c):
    """2a copia de Xerosic accesible (mano o mazo): la 1a se juega TEMPRANO
    (mano rival >= 4); el segundo cap tardio es destructivo. Sin respaldo,
    timing conservador (user, julio 2026: -1 Poke Pad +1 Xerosic)."""
    return (c.hand_counts.get(Xerosic_Machinations, 0) >= 2
            or c.cartas_en_mazo.get(
                Xerosic_Machinations, {}).get(ESTADO_MAZO, 0) >= 1)


def _xr_gate_alakazam(c):
    """vs Alakazam (la razon de ser de la carta): mano rival >= 6 (Powerful
    Hand 120+), KO proyectado sobre nuestro activo, o copia de respaldo con
    la mano rival ya creciendo (>= 4)."""
    return (c.op_is_alakazam_deck
            and (c.op_hand_count >= 6 or _xr_letal_proyectado(c)
                 or (_xr_copia_respaldo(c) and c.op_hand_count >= 4)))


_REGLAS_XEROSIC_PLAY = [
    _ReglaFija("supporter_ya_jugado",
               lambda c: c.state.supporterPlayed,
               lambda c: SCORE_VETO),
    # Sin efecto si la mano rival ya tiene <= 3 (p.ej. tras Unfair Stamp
    # este mismo turno): no quemar el Supporter para nada.
    _ReglaFija("mano_rival_ya_corta",
               lambda c: c.op_hand_count <= 3,
               lambda c: SCORE_VETO),
    # Con KO el turno pasado y Stamp en mano, el Sello va PRIMERO (es Item
    # y rebaraja NUESTRA mano). Mismo gate que Boss's/Lana's/Dawn.
    # EXCEPCION (user, jul 2026): con la mano rival GIGANTE el orden se
    # invierte -- el Sello solo devuelve esas cartas al mazo, Xerosic las
    # DESCARTA, y los dos caben en el mismo turno. Ver `_xr_antes_del_sello`;
    # el otro lado del cambio es `cede_el_orden_a_xerosic` en el Sello.
    _ReglaFija("cede_a_unfair_stamp",
               lambda c: (_stamp_pendiente(c)
                          and not _xr_antes_del_sello(c)),
               lambda c: SCORE_VETO),
    # Boss's Orders solo tiene prioridad cuando GANA la partida (user,
    # registro_006 paso 85): ahi Xerosic cede y el Boss's (WIN_NOW 20000)
    # remata. Antes se cedia tambien ante `boss_win_via_bench` (un gusteo
    # letal que solo cobra UN premio), y con ello el agente cambiaba capar
    # la mano rival por un premio suelto.
    _ReglaFija("alakazam_cede_a_gusteo_ganador",
               lambda c: (_xr_gate_alakazam(c) and c.win_via_boss_gust
                          and c.hand_counts.get(Boss_Orders, 0) >= 1),
               lambda c: XEROSIC_SCORE_LAST_RESORT),
    # Sin ataque y mano corta: el desarrollo (Lillie's) vale mas que la
    # disrupcion este turno.
    _ReglaFija("alakazam_cede_a_lillie_mano_corta",
               lambda c: (_xr_gate_alakazam(c) and c.active_cant_attack
                          and sum(c.hand_counts.values()) <= 3
                          and c.hand_counts.get(Lillie_Determination, 0) >= 1),
               lambda c: XEROSIC_SCORE_LAST_RESORT),
    # Con la mano rival ya MINIMA (<= 4: capar solo le quita 1 carta) el valor
    # de disrupcion de Xerosic es marginal (Powerful Hand baja 20 de dano); si
    # tenemos Lillie's Determination en mano (refresco + desarrollo, sobre todo
    # cuando la buscamos con Meowth ex y por tanto es la jugada prevista) esta
    # vale mas. Cede el Supporter del turno a Lillie's (user, registro_002 paso
    # 17 vs Alakazam, PERDIDA: turno 2, rival con 4 cartas, el agente jugo
    # Xerosic en vez de la Lillie's recien buscada con Meowth ex). Distinto de
    # `alakazam_cede_a_lillie_mano_corta` (que gatea NUESTRA mano <= 3 + activo
    # que no ataca): aqui el gate es la mano RIVAL minima, sin condicion sobre
    # la nuestra. Va ANTES de `alakazam_prioridad_sobre_boss`/`_capar_mano`
    # porque esas dispararian 7000/5900 aunque solo se le quite 1 carta.
    _ReglaFija("alakazam_cede_a_lillie_mano_rival_minima",
               lambda c: (_xr_gate_alakazam(c)
                          and c.op_hand_count <= 4
                          and c.hand_counts.get(Lillie_Determination, 0) >= 1),
               lambda c: XEROSIC_SCORE_LAST_RESORT),
    # PRIORIDAD SOBRE BOSS'S (user, registro_006 paso 85 vs Alakazam,
    # PERDIDA): con Boss's Orders en mano y el rival a 16 cartas, el agente
    # jugo Boss's (gusteo de 2 premios, 6800) en vez de Xerosic (6200) y
    # dejo la mano rival intacta: su Powerful Hand (20 x carta de su mano)
    # siguio pegando 320 y arraso. Capar la mano vale mas que cualquier
    # gusteo que NO gane la partida; el gusteo GANADOR ya retorno arriba
    # (regla `alakazam_cede_a_gusteo_ganador`). Se puntua por encima de
    # BOSS_SCORE_GUST_2PRIZE (6800), que era la banda que ganaba, y por
    # debajo de BOSS_SCORE_WIN_NOW (20000).
    _ReglaFija("alakazam_prioridad_sobre_boss",
               lambda c: (_xr_gate_alakazam(c)
                          and c.hand_counts.get(Boss_Orders, 0) >= 1),
               lambda c: (XEROSIC_SCORE_SOBRE_BOSS
                          + min(300, 50 * (c.op_hand_count - 4))
                          + c.supporter_boost)),
    # Capar Powerful Hand: escala con la mano rival (5900-6200). Gana a
    # Lillie's hydra-cargado (5800); bajo WIN_NOW/GUST_2PRIZE y pivotes.
    _ReglaFija("alakazam_capar_mano",
               _xr_gate_alakazam,
               lambda c: (XEROSIC_SCORE_ALAKAZAM
                          + min(300, 50 * (c.op_hand_count - 4))
                          + c.supporter_boost)),
    # Generico: quitarle 4+ cartas es valor real, pero sin Powerful Hand va
    # por debajo de Lillie's/Lana's/Boss's utiles. Solo mano rival >= 7.
    _ReglaFija("generico_mano_muy_grande",
               lambda c: c.op_hand_count >= 7,
               lambda c: XEROSIC_SCORE_GENERIC + c.supporter_boost),
    # defecto: ultimo recurso (mano rival 4-6 sin matchup Alakazam).
]


def _score_xerosic_play(ctx: DecisionContext) -> int:
    """Puntua jugar Xerosic's Machinations (id 1197): el rival descarta hasta
    quedarse con 3. En el mazo por el matchup Alakazam (Powerful Hand hace 20
    por carta de su mano). Cuerpo migrado al MOTOR DE REGLAS (fase 4)."""
    return _resolver_con_traza("xerosic->play", _REGLAS_XEROSIC_PLAY, [],
                               ctx, defecto=XEROSIC_SCORE_LAST_RESORT)

__all__ = [
    '_xr_antes_del_sello',
    '_xr_letal_proyectado',
    '_xr_copia_respaldo',
    '_xr_gate_alakazam',
    '_score_xerosic_play',
    '_REGLAS_XEROSIC_PLAY',
    '_sello_merece_jugarse',
    '_stamp_pendiente',
    '_us_pokemon_jugable',
    '_us_evo_jugable',
    '_us_item_jugable',
    '_us_bonus_matchup',
    '_score_unfair_stamp_play',
    '_REGLAS_STAMP_PLAY',
    '_AJUSTES_STAMP_PLAY',
]
