"""Bug Catching Set: busqueda de Pokemon Insecto.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

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

__all__ = [
    '_v_bcs_base',
    '_REGLAS_BCS_PLAY',
    '_AJUSTES_BCS_PLAY',
]
