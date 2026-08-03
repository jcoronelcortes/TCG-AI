"""Estadios: Forest of Vitality y Grand Tree.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.estado.agente import ESTADO
from ptcg.cartas.ids import Forest_of_Vitality
from cg.api import AreaType
from typing import NamedTuple
from ptcg.cartas.ids import Applin, Bayleef, Chikorita, Dipplin, Hydrapple_ex, Meganium, Poke_Pad, Ultra_Ball
from ptcg.cartas.tablas import card_table
from ptcg.estado.claves import ESTADO_MAZO


class _GrandTreePlan(NamedTuple):
    """Una ejecucion concreta de la habilidad de Grand Tree."""
    area: int          # AreaType del Basico a evolucionar (ACTIVE / BENCH)
    index: int         # indice dentro de esa area
    serial: int        # serial del Basico (identidad estable entre llamadas)
    basic_id: int
    stage1_id: int
    stage2_id: int     # 0 = la cadena se detiene EXPRESAMENTE en Fase 1
    valor: int


def _gt_slots_propios(my_state):
    """`(area, index, pokemon)` de todos nuestros Pokemon en juego."""
    salida = []
    activo = (my_state.active[0]
              if getattr(my_state, 'active', None) else None)
    if activo is not None:
        salida.append((AreaType.ACTIVE, 0, activo))
    for k, pkmn in enumerate(getattr(my_state, 'bench', None) or []):
        if pkmn is not None:
            salida.append((AreaType.BENCH, k, pkmn))
    return salida


def _gt_valor_cuerpo(card_id):
    """Valor deck-agnostico del cuerpo que deja una evolucion: PV (termino
    dominante) + bono por tener Habilidad. No se usa el dano impreso porque los
    ataques que escalan (Syrup Storm, Do the Wave) lo declaran como 0."""
    data = card_table.get(card_id)
    if data is None:
        return 0
    valor = data.hp or 0
    if getattr(data, 'skills', None):
        valor += 40
    return valor


def _gt_premios_de(card_id):
    """Premios que entrega esa carta al ser noqueada (sin tools ni denegacion:
    aqui solo se usa para comparar Basico vs evolucion)."""
    data = card_table.get(card_id)
    if data is None:
        return 1
    return 3 if data.megaEx else 2 if data.ex else 1


def _fv_cadena_evolutiva(c):
    """Jugar Forest habilita evolucionar ESTE turno alguna linea presente
    (o bajable desde la mano encadenando basico+evolucion)."""
    h, f = c.hand_counts, c.field_counts
    meg_fetchable = (
        c.cartas_en_mazo.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0 and
        (h.get(Poke_Pad, 0) >= 1 or h.get(Ultra_Ball, 0) >= 1))
    if f.get(Chikorita, 0) >= 1 and not c.meganium_in_play:
        if h.get(Bayleef, 0) >= 1 or h.get(Meganium, 0) >= 1:
            return True
    if f.get(Bayleef, 0) >= 1 and not c.meganium_in_play:
        if h.get(Meganium, 0) >= 1 or meg_fetchable:
            return True
    if f.get(Applin, 0) >= 1:
        if h.get(Dipplin, 0) >= 1 or h.get(Hydrapple_ex, 0) >= 1:
            return True
    if f.get(Dipplin, 0) >= 1 and not c.has_hydrapple:
        if h.get(Hydrapple_ex, 0) >= 1:
            return True
    if (h.get(Chikorita, 0) >= 1 and
            f[Chikorita] + f[Bayleef] + f[Meganium] == 0 and
            h.get(Bayleef, 0) >= 1):
        return True
    if (h.get(Applin, 0) >= 1 and
            f[Applin] + f[Dipplin] == 0 and
            h.get(Dipplin, 0) >= 1):
        return True
    return False


def _v_fv_neutralization(c):
    f = c.field_counts
    if (f.get(Chikorita, 0) >= 1 or f.get(Applin, 0) >= 1
            or f.get(Dipplin, 0) >= 1):
        return 29000
    return 28000


def _v_fv_cadena(c):
    v = 22000 if c.stadium_id != 0 else 21900
    if c.op_is_fire_deck or c.op_is_aggro_deck or c.op_is_beedrill_deck:
        v += 200
    return v


def _v_fv_temprano(c):
    if c.op_is_fire_deck or c.op_is_aggro_deck or c.op_is_mirror:
        return 15000
    return 14000


def _forest_disponible(c):
    return ESTADO.forest_in_play or c.hand.get(Forest_of_Vitality, 0) >= 1

__all__ = [
    '_GrandTreePlan',
    '_gt_slots_propios',
    '_gt_valor_cuerpo',
    '_gt_premios_de',
    '_fv_cadena_evolutiva',
    '_v_fv_neutralization',
    '_v_fv_cadena',
    '_v_fv_temprano',
    '_forest_disponible',
]
