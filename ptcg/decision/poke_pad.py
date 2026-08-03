"""Poke Pad: que Pokemon merece buscarse.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.estado.agente import ESTADO
from ptcg.cartas.ids import Applin, Bayleef, Chikorita, Dipplin, Meganium
from ptcg.cartas.ids import Applin, Bayleef, Chikorita, Dipplin, Hydrapple_ex, Meganium, SCORE_VETO, Tapu_Bulu
from ptcg.estado.claves import ESTADO_MAZO
from ptcg.motor.contexto import DecisionContext
from ptcg.motor.reglas import _Ajuste, _ReglaFija, _resolver_con_traza


_PP_NON_RULEBOX_IDS = (Chikorita, Bayleef, Meganium, Applin, Dipplin,
                       Tapu_Bulu)


def _pp_buscables(c):
    """Pokemon SIN Rule Box con copias en el mazo (lo unico que Poke Pad
    puede buscar: excluye la linea Hydrapple ex y los demas ex)."""
    cartas = c.cartas_en_mazo
    return {cid: cartas[cid][ESTADO_MAZO] for cid in _PP_NON_RULEBOX_IDS
            if cid in cartas and cartas[cid][ESTADO_MAZO] > 0}


def _pp_es_t1(c):
    return ((c.state.turn == 1 and c.we_go_first)
            or (c.state.turn == 2 and not c.we_go_first))


def _pp_budew_dump(c):
    """Rival abre con Budew ACTIVO y vamos segundos: su Itchy Pollen bloquea
    objetos nuestro proximo turno; este primer turno es el UNICO para usar
    objetos -> jugar TODAS las Poke Pad ahora."""
    return (c.budew_op_index == 0
            and c.state.turn == 2 and not c.we_go_first)


def _v_pp_t1(c):
    s = _pp_buscables(c)
    tiene_applin = (c.field_counts.get(Applin, 0) >= 1
                    or c.hand_counts.get(Applin, 0) >= 1)
    tiene_chik = (c.field_counts.get(Chikorita, 0) >= 1
                  or c.hand_counts.get(Chikorita, 0) >= 1)
    if not tiene_applin and Applin in s and c.bench_count < 5:
        return 12800
    if not tiene_chik and Chikorita in s and c.bench_count < 5:
        return 12600
    if _pp_budew_dump(c):
        return 12400
    return SCORE_VETO


def _pp_evo_valor(c):
    """Mejor evolucion habilitada ESTE turno por una busqueda de Poke Pad
    (0 = ninguna). La foto evolvable es la de inicio de turno sin Forest."""
    s = _pp_buscables(c)
    h, f = c.hand_counts, c.field_counts
    # NO usa `_evolvable_counts`: MEDIDO Y REVERTIDO (ver su nota de alcance).
    evolvable = (c.field_at_turn_start
                 if (not c.forest_in_play and c.field_at_turn_start) else f)
    v = 0
    if (Meganium in s and not c.meganium_in_play
            and h.get(Meganium, 0) == 0):
        if evolvable.get(Bayleef, 0) >= 1:
            v = max(v, 1200)
        elif (c.forest_in_play and evolvable.get(Chikorita, 0) >= 1
                and h.get(Bayleef, 0) >= 1):
            v = max(v, 1100)
    if (Bayleef in s and not c.meganium_in_play
            and h.get(Bayleef, 0) == 0):
        if evolvable.get(Chikorita, 0) >= 1:
            v = max(v, 1000)
            if c.forest_in_play and h.get(Meganium, 0) >= 1:
                v = max(v, 1150)
    if Dipplin in s and h.get(Dipplin, 0) == 0:
        if evolvable.get(Applin, 0) >= 1:
            v = max(v, 950)
            if c.forest_in_play and h.get(Hydrapple_ex, 0) >= 1:
                v = max(v, 1100)
    return v


def _pp_evolucion_pendiente_de_busqueda(c):
    """Alguna pre-evo en juego cuya evolucion NO esta en mano pero SI en el
    mazo: una busqueda la habilita (no cortar por banca llena)."""
    h, f, cartas = c.hand_counts, c.field_counts, c.cartas_en_mazo
    return ((f.get(Chikorita, 0) >= 1 and h.get(Bayleef, 0) == 0
             and cartas.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0)
            or (f.get(Bayleef, 0) >= 1 and h.get(Meganium, 0) == 0
                and cartas.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0)
            or (f.get(Applin, 0) >= 1 and h.get(Dipplin, 0) == 0
                and cartas.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0))


_REGLAS_PP_PLAY = [
    _ReglaFija("sin_buscables",
               lambda c: not _pp_buscables(c),
               lambda c: SCORE_VETO),
    _ReglaFija("primer_turno",
               _pp_es_t1,
               _v_pp_t1),
    _ReglaFija("evolucion_este_turno",
               lambda c: _pp_evo_valor(c) > 0,
               lambda c: (23000 if _pp_evo_valor(c) >= 1100
                          else (22000 if _pp_evo_valor(c) >= 900
                                else 20000))),
    _ReglaFija("asegurar_chikorita",
               lambda c: (Chikorita in _pp_buscables(c)
                          and not c.meganium_in_play
                          and (c.field_counts.get(Chikorita, 0)
                               + c.field_counts.get(Bayleef, 0)
                               + c.field_counts.get(Meganium, 0)) == 0
                          and c.hand_counts.get(Chikorita, 0) == 0
                          and c.bench_count < 5),
               lambda c: 12800),
    _ReglaFija("asegurar_applin",
               lambda c: (Applin in _pp_buscables(c) and c.bench_count < 5),
               lambda c: 12600),
]


_AJUSTES_PP_PLAY = [
    # Buscar Tapu Bulu como sacrificio de 1 premio (pivote vs Lucario).
    _Ajuste("sacrificio_lucario_tapu",
            lambda c, s: (c.lucario_sac_pivot
                          and Tapu_Bulu in _pp_buscables(c)
                          and c.field_counts.get(Tapu_Bulu, 0) == 0
                          and c.hand_counts.get(Tapu_Bulu, 0) == 0
                          and c.bench_count < 5),
            lambda c, s: 13000),
    # Banca llena y sin pre-evo que evolucionar CON UNA BUSQUEDA: guardar
    # el recurso (Poke Pad excluye la linea Dipplin->Hydrapple ex).
    _Ajuste("banca_llena_guardar",
            lambda c, s: (c.bench_count >= 5
                          and not _pp_evolucion_pendiente_de_busqueda(c)
                          and s > 0 and not _pp_budew_dump(c)),
            lambda c, s: SCORE_VETO),
]


def _score_poke_pad_play(ctx: DecisionContext) -> int:
    """Puntua la jugada de Poke Pad (busca un Pokemon SIN Rule Box). Prioriza
    habilitar una evolucion ESTE turno; si no, asegurar basicos; con banca
    llena y sin nada que evolucionar, guarda el recurso. Cuerpo migrado al
    MOTOR DE REGLAS (fase 4)."""
    return _resolver_con_traza("pokepad->play", _REGLAS_PP_PLAY,
                               _AJUSTES_PP_PLAY, ctx, defecto=SCORE_VETO)


class _CtxPPFetch:
    """Ctx del fetch de Poke Pad: carta candidata + derivados del modo."""

    def __init__(self, card_id, hand_counts, field_counts, bench_count,
                 state):
        self.card_id = card_id
        self.hand = hand_counts
        self.campo = field_counts
        self.bench_count = bench_count
        self.first_turn = ((state.turn == 1 and ESTADO.we_go_first) or
                           (state.turn == 2 and not ESTADO.we_go_first))
        self.have_chik = (field_counts.get(Chikorita, 0) >= 1 or
                          hand_counts.get(Chikorita, 0) >= 1)
        self.have_bay = (field_counts.get(Bayleef, 0) >= 1 or
                         hand_counts.get(Bayleef, 0) >= 1)
        self.have_applin = (field_counts.get(Applin, 0) >= 1 or
                            hand_counts.get(Applin, 0) >= 1)
        self.have_dipplin = (field_counts.get(Dipplin, 0) >= 1 or
                             hand_counts.get(Dipplin, 0) >= 1)
        has_evo = False
        if not ESTADO.meganium_in_play and hand_counts.get(Meganium, 0) == 0:
            if field_counts.get(Bayleef, 0) >= 1:
                has_evo = True
            elif (ESTADO.forest_in_play and field_counts.get(Chikorita, 0) >= 1 and
                  hand_counts.get(Bayleef, 0) >= 1):
                has_evo = True
        if (not ESTADO.meganium_in_play and hand_counts.get(Bayleef, 0) == 0 and
                field_counts.get(Chikorita, 0) >= 1):
            has_evo = True
        if (hand_counts.get(Dipplin, 0) == 0 and
                field_counts.get(Applin, 0) >= 1):
            has_evo = True
        self.has_evo = has_evo

__all__ = [
    '_pp_buscables',
    '_pp_es_t1',
    '_pp_budew_dump',
    '_v_pp_t1',
    '_pp_evo_valor',
    '_pp_evolucion_pendiente_de_busqueda',
    '_score_poke_pad_play',
    '_REGLAS_PP_PLAY',
    '_AJUSTES_PP_PLAY',
    '_PP_NON_RULEBOX_IDS',
    '_CtxPPFetch',
]
