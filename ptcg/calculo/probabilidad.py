"""Probabilidad hipergeometrica del robo.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.cartas.puntuacion import MAIN_ATTACKERS
from ptcg.cartas.ids import Basic_Grass_Energy, Hydrapple_ex, RETREAT_COST, Teal_Mask_Ogerpon_ex
from ptcg.calculo.tablero import _active_of
from ptcg.calculo.energia import _grass_ability_slots, _grass_attach_unit, _retreat_grass_units
from ptcg.calculo.dano import _attacker_base_damage, _ko_no_garantizado, _our_effective_damage
from ptcg.calculo.carta import prize_count_op
from ptcg.estado.claves import ESTADO_MAZO, ESTADO_PREMIO
from ptcg.estado.agente import ESTADO
from ptcg.cartas.ids import PESCA_PREMIOS_MIN, PESCA_PROB_MIN
from dataclasses import dataclass
from math import comb as _comb


def _prob_al_menos(exitos, poblacion, robo, k):
    """Hipergeometrica: P(robar AL MENOS `k` copias) sacando `robo` cartas de
    un mazo de `poblacion` con `exitos` copias vivas.

    Es el UNICO sitio del fichero donde el agente razona con azar; el resto
    decide con el tablero visible. `exitos` sale de la creencia de mazo
    (`CARTAS_ACTIVAS_EN_MAZO`), que cuenta lo que NO se ha visto: mazo + premios
    boca abajo. Por eso el llamador mete tambien los premios en `poblacion` --
    son cartas indistinguibles del mazo desde nuestro lado--, lo que deja la
    estimacion LIGERAMENTE conservadora (en el registro_004: 11 Plantas no
    vistas en 48 -> 0.60, frente al 0.63 real de las 10 que quedaban en el mazo
    de 42). Conservador es lo que se quiere en un gate."""
    if k <= 0:
        return 1.0
    if exitos <= 0 or robo <= 0 or poblacion <= 0 or k > exitos:
        return 0.0
    robo = min(robo, poblacion)
    if k > robo:
        return 0.0
    fallos = poblacion - exitos
    total = _comb(poblacion, robo)
    if total <= 0:
        return 0.0
    menos_de_k = 0
    for i in range(0, k):
        if i > exitos or (robo - i) > fallos or (robo - i) < 0:
            continue
        menos_de_k += _comb(exitos, i) * _comb(fallos, robo - i)
    return max(0.0, min(1.0, 1.0 - menos_de_k / total))


@dataclass
class _PescaRemate:
    """Ataque que este turno SOLO depende de que el robo traiga energia."""
    atacante_id: int
    desde_banca: bool     # exige retirar el activo para promoverlo
    cartas: int           # Plantas que tiene que traer el ROBO
    dano: int             # dano EFECTIVO proyectado sobre el activo rival
    letal: bool
    premios: int          # premios que cobra el KO (0 si no es letal)
    robo: int             # cartas que roba el refresco
    outs: int             # Plantas vivas en el mazo tras barajar
    universo: int         # cartas del mazo tras barajar la mano
    prob: float


def _belief_deck_and_prizes():
    deck = 0
    prize = 0
    for counts in ESTADO.CARTAS_ACTIVAS_EN_MAZO.values():
        deck += counts.get(ESTADO_MAZO, 0)
        prize += counts.get(ESTADO_PREMIO, 0)
    return deck, prize


def _prob_draw_any(target_ids, draws=1):
    if draws <= 0:
        return 0.0
    if isinstance(target_ids, int):
        target_ids = (target_ids,)
    target_set = set(target_ids)
    deck = 0
    hits = 0
    for cid, counts in ESTADO.CARTAS_ACTIVAS_EN_MAZO.items():
        n = counts.get(ESTADO_MAZO, 0)
        deck += n
        if cid in target_set:
            hits += n
    if deck <= 0 or hits <= 0:
        return 0.0
    draws = min(draws, deck)
    miss = deck - hits
    p_none = 1.0
    for i in range(draws):
        denom = deck - i
        if denom <= 0:
            break
        p_none *= max(0, (miss - i)) / denom
    return 1.0 - p_none


def _prob_card_accessible(card_id):
    counts = ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(card_id)
    if not counts:
        return 0.0
    in_deck = counts.get(ESTADO_MAZO, 0)
    in_prize = counts.get(ESTADO_PREMIO, 0)
    copies = in_deck + in_prize
    if copies <= 0:
        return 0.0
    deck, prize = _belief_deck_and_prizes()
    total_hidden = deck + prize
    if total_hidden <= 0:
        return 1.0 if in_deck > 0 else 0.0
    if prize <= 0:
        return 1.0
    p_all_prized = 1.0
    for i in range(copies):
        denom = total_hidden - i
        if denom <= 0:
            p_all_prized = 0.0
            break
        p_all_prized *= max(0, (prize - i)) / denom
    return 1.0 - p_all_prized


def _pesca_remate_valida(c):
    """La pesca es lo bastante buena para PISAR los vetos de orden de Lillie's.

    Gates (todos necesarios): hueco de Supporter libre; NINGUN ataque posible
    este turno (ni con el activo ni promoviendo un cuerpo de banca ya cargado --
    si se puede atacar, manda el ladder normal); el plan COBRA premio con
    probabilidad >= `PESCA_PROB_MIN`; y ningun remate SEGURO en juego (gusteo
    ganador o esquiva), que siempre gana a un KO probable.

    `pending_evo` (evolucion directa en mano con su pre-evo en juego) tambien
    bloquea: esa evolucion se juega ANTES por tier y el flag se apaga solo en la
    reevaluacion siguiente, asi que ceder aqui no cuesta el remate -- y si la
    evolucion NO es jugable hoy, barajar sus piezas si costaria la linea."""
    p = getattr(c, 'pesca_remate', None)
    return bool(p is not None
                and not c.state.supporterPlayed
                and not c.can_attack
                and not c.has_ready_bench_attacker
                and not getattr(c, 'pending_evo', False)
                and p.letal
                and p.premios >= PESCA_PREMIOS_MIN
                and p.prob >= PESCA_PROB_MIN
                and not c.boss_win_via_bench
                and not c.win_via_boss_gust
                and not c.boss_dodge_redirect
                and not c.win_ko_active_via_promote)


def _pesca_de_remate(my_state, op_state, state, hand_counts, field_counts,
                     grass_en_mazo, robo, baraja_la_mano=True,
                     meganium_in_play=False, neutralization_zone_active=False,
                     total_grass=0, bench_count=0, puede_cambiar=False,
                     has_switch_card=False, habilidades_apagadas=False):
    """El MEJOR ataque que el robo de este turno puede desbloquear, con su
    probabilidad. `None` si no hay ninguno.

    Hermano CONSCIENTE DEL DANO de `_plan_de_planta`: comparte su aritmetica de
    adjuntes (cartas = techo(deficit / `_grass_attach_unit()`), vias dirigibles
    al cuerpo concreto -- manual + Ripening Charge de cada Hydrapple ex + Teal
    Dance solo sobre el propio Ogerpon) y le anade lo que aquella no mira: a
    QUIEN se ataca, cuanto DANO sale y cuantos PREMIOS cobra.

    Nace del registro_004 paso 49 vs Marnie (PERDIDA): Teal Mask Ogerpon ex
    ACTIVO con 1 energia (Myriad pide 3), NADA cargado en banca, CERO energia
    en mano y 6 premios intactos -- Lillie's roba OCHO con 10 Plantas vivas en
    42 cartas: 63% de sacar las 2 que faltan. Con ellas Myriad Leaf Shower pega
    30 + 30 x (3 propias + 2 del rival) = 180, x2 por DEBILIDAD Planta del
    Marnie's Grimmsnarl ex = 360 >= 320 PV: DOS premios. El agente jugo Boss's
    Orders para arrastrar un Snorunt de 70 PV -- un gusteo que ademas DEGRADA
    el objetivo (Myriad escala con la energia del activo rival, y el Snorunt
    venia sin energia) -- y despues pago la Ultra Ball descartando las DOS
    Lillie's, que ya eran carta muerta con el Supporter gastado.

    `baraja_la_mano=True` (Lillie's, Unfair Stamp) modela el coste real del
    refresco: las Plantas que hubiera en la mano VUELVEN al mazo, asi que no
    descuentan del deficit y se suman a los `outs`.

    El objetivo es SIEMPRE el activo rival ACTUAL: el hueco de Supporter se lo
    lleva el refresco, asi que no hay Boss's que cambiarlo -- y ese es
    justamente el punto del registro (gustear cambia el objetivo por uno peor).
    """
    if op_state is None or not op_state.active or op_state.active[0] is None:
        return None
    objetivo = op_state.active[0]
    if (objetivo.hp or 0) <= 0:
        return None
    if robo <= 0:
        return None

    unidad = _grass_attach_unit()
    slots_manual = 0 if state.energyAttached else 1
    n_hydrapple = 0 if habilidades_apagadas else field_counts.get(Hydrapple_ex, 0)
    slots_hab = (0 if habilidades_apagadas
                 else _grass_ability_slots(state, field_counts))
    slots_hoy = slots_manual + slots_hab
    if slots_hoy <= 0:
        return None                       # no queda por donde meter energia hoy

    grass_mano = hand_counts.get(Basic_Grass_Energy, 0)
    # Con un refresco que BARAJA la mano, las Plantas de la mano se pierden como
    # recurso inmediato y reaparecen como outs del mazo.
    en_mano_util = 0 if baraja_la_mano else grass_mano
    outs = grass_en_mazo + (grass_mano if baraja_la_mano else 0)
    # `grass_en_mazo` viene de la creencia, que cuenta TODO lo no visto: mazo +
    # premios. La poblacion tiene que contarlos igual para no inflar la
    # probabilidad (ver `_prob_al_menos`). El Supporter que se juega no vuelve
    # al mazo: se descarta, de ahi el -1.
    universo = max(1, (getattr(my_state, 'deckCount', 0) or 0)
                   + len(getattr(my_state, 'prize', None) or [])
                   + (max(0, len(my_state.hand or []) - 1) if baraja_la_mano else 0))

    activo = _active_of(my_state)
    # Coste de la retirada si el rematador esta en la BANCA: se paga con las
    # energias del ACTIVO (cartas enteras), y eso baja el Grass del campo con el
    # que escala Syrup Storm.
    coste_ret = 0 if has_switch_card else (
        RETREAT_COST.get(activo.id, 1) if activo is not None else 99)
    retirada_pagable = (puede_cambiar
                        and activo is not None
                        and (has_switch_card
                             or len(activo.energies) >= coste_ret))
    grass_tras_retirar = max(0, total_grass - (0 if has_switch_card
                                               else _retreat_grass_units(coste_ret)))

    cuerpos = ([(activo, True)] if activo is not None else [])
    cuerpos += [(bp, False) for bp in (my_state.bench or [])]
    mejor, mejor_clave = None, None
    for cuerpo, es_activo in cuerpos:
        if cuerpo is None or cuerpo.id not in MAIN_ATTACKERS:
            continue
        if not es_activo and not retirada_pagable:
            continue                      # cargado o no, hoy no llega al frente
        req = ESTADO.ATTACK_ENERGY_REQ.get(cuerpo.id)
        if req is None:
            continue
        falta = req - len(cuerpo.energies)
        if falta <= 0:
            continue                      # ya ataca: no es una pesca
        cartas = -(-falta // unidad)
        # Vias que pueden apuntar a ESTE cuerpo hoy (mismo criterio que
        # `_plan_de_planta`): Teal Dance solo carga a su portador.
        dirigibles = slots_manual + n_hydrapple
        if cuerpo.id == Teal_Mask_Ogerpon_ex and not habilidades_apagadas:
            dirigibles += 1
        dirigibles = min(dirigibles, slots_hoy)
        if cartas > dirigibles:
            continue                      # ni con todas las vias ataca hoy
        if cartas <= min(grass_mano, dirigibles):
            # La MANO ya lo desbloquea: esto no es una pesca, es una carga --
            # y con `baraja_la_mano` seria ademas el peor error posible
            # (barajar al mazo justo la energia que gana el turno). El adjunte
            # puntua en su propio tier y se juega ANTES; si solo cubre parte
            # del deficit, la reevaluacion posterior vuelve aqui con el
            # adjunte ya gastado y menos cartas que pescar.
            continue
        del_robo = cartas - min(en_mano_util, dirigibles)
        if del_robo <= 0:
            continue                      # la mano sola lo desbloquea: no es pesca
        if del_robo > robo:
            continue                      # ni robandolo todo entra

        escala_grass = ((total_grass if es_activo else grass_tras_retirar)
                        + cartas * unidad)
        energia_tras = len(cuerpo.energies) + cartas * unidad
        base = _attacker_base_damage(
            cuerpo.id, objetivo, energia_tras,
            grass_scale=escala_grass,
            teal_self_energy=len(cuerpo.energies) + cartas,
            bench_count=bench_count)
        if base <= 0:
            continue
        dano = _our_effective_damage(cuerpo, objetivo, base, meganium_in_play,
                                     neutralization_zone_active)
        if dano <= 0:
            continue
        letal = dano >= (objetivo.hp or 0) and not _ko_no_garantizado(objetivo)
        premios = prize_count_op(objetivo) if letal else 0
        prob = _prob_al_menos(outs, universo, robo, del_robo)
        if prob <= 0.0:
            continue
        # Mejor plan = el que mas premios cobra; a igualdad, el mas PROBABLE
        # (menos cartas que pescar), y luego el que mas dano hace. Se prefiere
        # el ACTIVO al relevo de banca: no paga retirada.
        clave = (1 if letal else 0, premios, round(prob, 6), dano,
                 0 if es_activo else -1)
        if mejor_clave is None or clave > mejor_clave:
            mejor_clave = clave
            mejor = _PescaRemate(
                atacante_id=cuerpo.id, desde_banca=not es_activo,
                cartas=del_robo, dano=dano, letal=letal, premios=premios,
                robo=robo, outs=outs, universo=universo, prob=prob)
    return mejor

__all__ = [
    '_prob_al_menos',
    '_PescaRemate',
    '_pesca_remate_valida',
    '_belief_deck_and_prizes',
    '_prob_draw_any',
    '_prob_card_accessible',
    '_pesca_de_remate',
]
