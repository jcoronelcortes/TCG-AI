"""Probabilidad hipergeometrica del robo.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

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

__all__ = [
    '_prob_al_menos',
    '_PescaRemate',
    '_pesca_remate_valida',
    '_belief_deck_and_prizes',
    '_prob_draw_any',
    '_prob_card_accessible',
]
