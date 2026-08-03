"""Lectura de tablero: activo, evolucionables y opciones de mano.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.cartas.ids import Applin, Basic_Grass_Energy, Bayleef, Boss_Orders, Chikorita, Dawn, Dipplin, Hydrapple_ex, Lanas_Aid, Lillie_Determination, Meganium, Teal_Mask_Ogerpon_ex, Xerosic_Machinations


def _active_of(state):
    # Pokemon activo de `state`, o None si no hay activo. Centraliza el patron
    # repetido `state.active[0] if state.active and state.active[0] is not None
    # else None`.
    if state is None:
        return None
    _act = getattr(state, "active", None)
    return _act[0] if _act and _act[0] is not None else None


def _evolvable_counts(field_counts, at_turn_start, forest_in_play_flag):
    """Pre-evoluciones que de verdad se pueden EVOLUCIONAR este turno.

    Con Forest of Vitality en mesa la restriccion de "no salio este turno"
    desaparece: manda la foto ACTUAL del campo. Sin Forest hace falta que el
    cuerpo estuviera en juego al EMPEZAR el turno... y que SIGA AHI.

    Ese segundo requisito faltaba (user, registro_006 paso 84 vs Marnie): la
    foto de inicio de turno NO se decrementa cuando esa misma pre-evo se
    consume evolucionando durante el turno. El turno arranco con un Applin en
    banca, se evoluciono a Dipplin en el paso 79 y a partir de ahi la foto
    seguia diciendo "hay un Applin evolucionable". Con eso la Night Stretcher
    se jugo para recuperar un Dipplin que ya no tenia sobre que subir: carta
    muerta en la mano, que el Unfair Stamp del mismo turno barajo al mazo.

    Se toma el MINIMO por especie: presente AHORA y presente al principio. Es
    el mismo criterio que ya escribian A MANO `_ub_evolve_now_search` y
    `_lillie_evolve_now` (`field_counts >= 1 and (forest or inicio >= 1)`):
    esos dos nunca tuvieron el bug, la foto congelada si.

    ALCANCE (MEDIDO): solo las DOS caras de la Night Stretcher -- `_CtxNSPlay`
    (jugarla) y `evolvable_ns` (que recuperar). El mismo idiom vive en otros
    cuatro sitios (Ultra Ball x2, Poke Pad, Lillie's) y depurarlos TAMBIEN
    costo **-4.7 puntos vs Crustle/Kangaskhan** (68.6% vs 73.3%, n=1000);
    acotado a la Night Stretcher el mismo matchup da **+2.4** (72.5% vs 70.1%,
    n=1000). En esos cuatro la foto "sucia" esta haciendo de proxy de algo que
    si vale -- probablemente "esta linea sigue viva aunque ya haya evolucionado
    hoy", que es lo que sostiene el desarrollo en un matchup largo. Se
    revirtieron a proposito: no unificarlos sin volver a medir ese matchup.
    (Los deltas son SIEMPRE los de la misma corrida: el nivel absoluto del bot
    se mueve ~3 puntos entre corridas, el delta pareado no.)

    Foto vacia = sin dato (primer menu del turno, antes de rellenarla): manda
    la actual, igual que el idiom original (`{}` es falsy).
    """
    if forest_in_play_flag or not at_turn_start:
        return field_counts
    return {cid: min(n, field_counts.get(cid, 0))
            for cid, n in at_turn_start.items()}


def _count_hand_play_options(hand_counts, field_counts, bench_count, energy_attached):
    play_options = 0

    if hand_counts.get(Meganium, 0) >= 1 and field_counts.get(Bayleef, 0) >= 1:
        play_options += 2
    if hand_counts.get(Bayleef, 0) >= 1 and field_counts.get(Chikorita, 0) >= 1:
        play_options += 2
    if hand_counts.get(Hydrapple_ex, 0) >= 1 and field_counts.get(Dipplin, 0) >= 1:
        play_options += 2
    if hand_counts.get(Dipplin, 0) >= 1 and field_counts.get(Applin, 0) >= 1:
        play_options += 2

    supporters_in_hand = (hand_counts.get(Lillie_Determination, 0) + hand_counts.get(Boss_Orders, 0) +
                         hand_counts.get(Dawn, 0) +
                         hand_counts.get(Lanas_Aid, 0) +
                         hand_counts.get(Xerosic_Machinations, 0))
    play_options += supporters_in_hand

    if hand_counts.get(Basic_Grass_Energy, 0) >= 1 and not energy_attached:
        play_options += 1

    if bench_count < 5:
        for bcid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex):
            if hand_counts.get(bcid, 0) >= 1:
                play_options += 1
    return play_options, supporters_in_hand

__all__ = [
    '_active_of',
    '_evolvable_counts',
    '_count_hand_play_options',
]
