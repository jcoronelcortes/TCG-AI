"""Bug Catching Set: busqueda de Pokemon Insecto.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.motor.reglas import _resolver_con_traza
from ptcg.motor.contexto import DecisionContext
from ptcg.estado.claves import ESTADO_MAZO
from ptcg.cartas.tablas import card_table
from ptcg.cartas.ids import Applin, Basic_Grass_Energy, Bayleef, Chikorita, Dipplin, Hydrapple_ex, Meganium, Teal_Mask_Ogerpon_ex
from cg.api import CardType, EnergyType
from ptcg.cartas.ids import Basic_Grass_Energy, SCORE_BELIEF_DIG_ENERGY, SCORE_VETO, Teal_Mask_Ogerpon_ex
from ptcg.motor.reglas import _Ajuste, _ReglaFija


def _v_bcs_base(w):
    v = 10500
    if (w.field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1
            and w.hand_counts[Basic_Grass_Energy] >= 1):
        v -= 100
    return v


_REGLAS_BCS_PLAY = [
    _ReglaFija("sin_elegibles_en_mazo",
               lambda w: w.elegibles == 0,
               lambda w: SCORE_VETO),
    # Freno de deck-out (paso 4 plan jul 2026; autopsia v2 vs crustle: 4/19
    # derrotas POR DECKOUT y cola de deckCount 0-5 en t20+, el pendiente de
    # a7df1ce). Con el mazo critico -- mismo umbral familiar que el freno de
    # Lillie's (<=10), aqui <=8 -- Bug Catching Set adelgaza 1-2 cartas del
    # mazo: puro reloj perdido contra un rival stall. EXCEPCION energia seca
    # (la que motivo el BCS del plan anti-mill vs Comfey, b393426): sin
    # Planta en mano y con el adjunte del turno pendiente, cavar la energia
    # habilita atacar HOY, y eso vale mas que el reloj.
    _ReglaFija("freno_deckout_mazo_critico",
               lambda w: (getattr(w.my_state, 'deckCount', 60) <= 8
                          and not (w.hand_counts[Basic_Grass_Energy] == 0
                                   and not w.state.energyAttached)),
               lambda w: SCORE_VETO),
    _ReglaFija("base",
               lambda w: True,
               _v_bcs_base),
]


_AJUSTES_BCS_PLAY = [
    _Ajuste("prob_encontrar",
            lambda w, s: s > 0,
            lambda w, s: s + (800 if w.p_find >= 0.9
                              else (500 if w.p_find >= 0.7
                                    else (200 if w.p_find >= 0.5
                                          else -300)))),
    _Ajuste("piezas_alto_valor",
            lambda w, s: s > 0 and w.alto_valor >= 1,
            lambda w, s: s + (600 if w.alto_valor >= 3
                              else (400 if w.alto_valor >= 2 else 200))),
    _Ajuste("lineas_incompletas",
            lambda w, s: s > 0 and (not w.meganium_in_play
                                    or not w.has_hydrapple),
            lambda w, s: s + (300 if (not w.meganium_in_play
                                      and not w.has_hydrapple) else 150)),
    _Ajuste("energia_seca",
            lambda w, s: (s > 0 and w.hand_counts[Basic_Grass_Energy] == 0
                          and not w.state.energyAttached),
            lambda w, s: s + 200),
    _Ajuste("cavar_energia_belief",
            lambda w, s: (s > 0 and w.hand_counts[Basic_Grass_Energy] == 0
                          and not w.state.energyAttached
                          and w.energy_starved_low_draw
                          and w.energia_mazo > 0),
            lambda w, s: s + SCORE_BELIEF_DIG_ENERGY),
    # Con Poke Pad jugable (y sin Itchy Pollen), BCS cede: tope 9000.
    _Ajuste("tope_si_pokepad_jugable",
            lambda w, s: (w.pp_playable_in_hand
                          and not w.itchy_pollen_active and s > 9000),
            lambda w, s: 9000),
]


class _CtxBCS:
    """Wrapper del DecisionContext para Bug Catching Set: precomputa las
    estadisticas del mazo (elegibles, piezas de alto valor, p_find de 7
    miradas) una sola vez; el resto delega via __getattr__."""

    def __init__(self, ctx):
        self.c = ctx
        f = ctx.field_counts
        grass, energia, alto_valor = 0, 0, 0
        for cid, states in ctx.cartas_en_mazo.items():
            if states[ESTADO_MAZO] <= 0:
                continue
            copias = states[ESTADO_MAZO]
            cdata = card_table.get(cid)
            if cid == Basic_Grass_Energy:
                energia += copias
            elif cdata and cdata.cardType == CardType.POKEMON:
                if cdata.energyType == EnergyType.GRASS:
                    grass += copias
                    if (cid == Meganium and not ctx.meganium_in_play
                            and (f.get(Bayleef, 0) >= 1
                                 or f.get(Chikorita, 0) >= 1)):
                        alto_valor += copias
                    elif (cid == Hydrapple_ex and not ctx.has_hydrapple
                            and (f.get(Dipplin, 0) >= 1
                                 or f.get(Applin, 0) >= 1)):
                        alto_valor += copias
                    elif (cid == Bayleef and not ctx.meganium_in_play
                            and f.get(Chikorita, 0) >= 1):
                        alto_valor += copias
                    elif (cid == Dipplin and not ctx.has_hydrapple
                            and f.get(Applin, 0) >= 1):
                        alto_valor += copias
                    elif (cid == Chikorita and not ctx.meganium_in_play
                            and f.get(Chikorita, 0) + f.get(Bayleef, 0)
                                + f.get(Meganium, 0) == 0):
                        alto_valor += copias
                    elif (cid == Applin and not ctx.has_hydrapple
                            and f.get(Applin, 0) + f.get(Dipplin, 0)
                                + f.get(Hydrapple_ex, 0) == 0):
                        alto_valor += copias
                    elif (cid == Teal_Mask_Ogerpon_ex
                            and f.get(Teal_Mask_Ogerpon_ex, 0) < 2):
                        alto_valor += copias
        self.energia_mazo = energia
        self.elegibles = grass + energia
        self.alto_valor = alto_valor
        total = sum(v[ESTADO_MAZO] for v in ctx.cartas_en_mazo.values())
        self.total_mazo = total
        if self.elegibles == 0:
            self.p_find = 0.0
        elif total <= 7:
            self.p_find = 1.0
        else:
            p_miss, restante = 1.0, total
            for _ in range(min(7, total)):
                if restante <= 0:
                    break
                p_miss *= (restante - self.elegibles) / restante
                restante -= 1
            self.p_find = 1.0 - p_miss

    def __getattr__(self, nombre):
        return getattr(self.c, nombre)


def _score_bug_catching_set_play(ctx: DecisionContext) -> int:
    """Puntua la jugada de Bug Catching Set (mira 7 y coge Planta/Energia).
    Cuerpo migrado al MOTOR DE REGLAS (fase 4): estadisticas del mazo
    precomputadas en _CtxBCS, contribuciones como ajustes con nombre."""
    return _resolver_con_traza("bcs->play", _REGLAS_BCS_PLAY,
                               _AJUSTES_BCS_PLAY, _CtxBCS(ctx), defecto=0)

__all__ = [
    '_v_bcs_base',
    '_REGLAS_BCS_PLAY',
    '_AJUSTES_BCS_PLAY',
    '_CtxBCS',
    '_score_bug_catching_set_play',
]
