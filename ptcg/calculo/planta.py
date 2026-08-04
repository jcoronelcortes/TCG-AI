"""Grass plan: how many Grass energies the field can use and whether they unlock today.

Extracted VERBATIM from main.py by utils/extraer_definiciones.py
(docs/project-history.md). Its purity is verified by
utils/pureza.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.estado.agente import ESTADO
from ptcg.cartas.puntuacion import MAIN_ATTACKERS
from ptcg.cartas.ids import Basic_Grass_Energy, Hydrapple_ex, Teal_Mask_Ogerpon_ex
from ptcg.calculo.tablero import _active_of
from ptcg.calculo.energia import _grass_ability_slots, _grass_attach_unit
from dataclasses import dataclass


@dataclass
class _PlanPlanta:
    """Reading of the BOARD in ENERGY terms (see `_plan_de_planta`)."""
    unidad: int              # EFFECTIVE energy provided by ONE physical Grass
    en_mano: int             # Grass already available in hand
    slots_hoy: int           # Grass attachments that still fit THIS turn
    nuevas_utiles_hoy: int   # NEW Grass that would reach the field TODAY
    desbloquea_hoy: bool     # a NEW Grass puts a body in attack range TODAY
    cartas_para_atacar: int  # NEW Grass that this unlock requires
    pendiente: int           # Grass demanded by every attacker in play
    demanda: int             # NEW Grass the board can use (<= `tope`)


@dataclass
class _PlanPlanta:
    """Reading of the BOARD in ENERGY terms (see `_plan_de_planta`)."""
    unidad: int              # EFFECTIVE energy provided by ONE physical Grass
    en_mano: int             # Grass already available in hand
    slots_hoy: int           # Grass attachments that still fit THIS turn
    nuevas_utiles_hoy: int   # NEW Grass that would reach the field TODAY
    desbloquea_hoy: bool     # a NEW Grass puts a body in attack range TODAY
    cartas_para_atacar: int  # NEW Grass that this unlock requires
    pendiente: int           # Grass demanded by every attacker in play
    demanda: int             # NEW Grass the board can use (<= `tope`)


def _plan_de_planta(my_state, state, field_counts, hand_counts, tope=3,
                    can_switch=False, abilities_off=False):
    """How many NEW Grass energies the board can use, and whether any of them
    UNLOCKS an attack TODAY.

    This is the board reading shared by the decision to PLAY a recovery card
    (`_score_lanas_aid_play`) and the decision of WHAT to recover with it (the
    `Lanas_Aid` branch of the TO_HAND context). It was born from registro_018
    step 118 vs Crustle (LOST): with Lana's Aid already played, the agent picked
    2 Applin + 1 Dipplin out of the discard -- with a FULL bench, cards that
    cannot be put into play -- while a Tapu Bulu was active ONE Grass away from
    firing Wood Hammer and three Grass energies sat in the discard. The
    selection branch did not look at energy at all (it fell through to the
    generic scorer, which scores "shapes of an evolution line"), and the play
    branch only knew how to read Hydrapple ex.

    Ways a Grass energy in HAND can reach the field in one turn:
      * the MANUAL attachment, if it has not been spent yet
        (`state.energyAttached`);
      * a live charging ability (`_grass_ability_slots`): *Teal Dance* on each
        Teal Mask Ogerpon ex (which only charges ITSELF) and *Ripening Charge*
        on each Hydrapple ex (which charges ANY of ours).

    `len(energies)` is ALREADY effective energy and `_grass_attach_unit()` is
    what ONE PHYSICAL Grass adds (2 with Meganium in play), so a body's deficit
    is measured in CARDS: `ceil((req - effective) / unit)`.

    Only `MAIN_ATTACKERS` bodies count: that is the curated list of "who we
    really attack with", so a benched Chikorita or Applin never invents energy
    demand (`ATTACK_ENERGY_REQ` does assign them a cost).

    `desbloquea_hoy` only looks at the ACTIVE, unless `puede_cambiar` says a
    retreat/switch is available: a charged benched attacker does not attack
    today if it cannot come up. Benched bodies do always add to `pendiente`,
    which is two-turn demand.

    `habilidades_apagadas` (Team Rocket's Watchtower / Iron Thorns active, the
    `meowth_ability_lock` flag) erases both ABILITY routes: with the lock on,
    only the manual attachment is left, and treating Teal Dance/Ripening as
    alive invents unlocks that do not exist.
    """
    unidad = _grass_attach_unit()
    en_mano = hand_counts.get(Basic_Grass_Energy, 0)
    slots_manual = 0 if state.energyAttached else 1
    slots_hab = (0 if abilities_off
                 else _grass_ability_slots(state, field_counts))
    slots_hoy = slots_manual + slots_hab
    nuevas_utiles_hoy = max(0, slots_hoy - en_mano)
    n_hydrapple = 0 if abilities_off else field_counts.get(Hydrapple_ex, 0)

    desbloquea_hoy = False
    cartas_para_atacar = 0
    pendiente = 0
    activo = _active_of(my_state)
    cuerpos = ([(activo, True)] if activo is not None else [])
    cuerpos += [(bp, False) for bp in (my_state.bench or [])]
    for cuerpo, es_activo in cuerpos:
        if cuerpo is None or cuerpo.id not in MAIN_ATTACKERS:
            continue
        req = ESTADO.ATTACK_ENERGY_REQ.get(cuerpo.id)
        if req is None:
            continue
        falta = req - len(cuerpo.energies)
        if falta <= 0:
            continue                     # already attacks: asks for no energy
        cartas = -(-falta // unidad)     # ceiling of the division
        pendiente += cartas
        if not es_activo and not can_switch:
            continue                     # charged or not, it does not attack today
        # Routes that can point at THIS body today. Teal Dance only charges its own
        # bearer; the manual attachment and Ripening Charge, anyone.
        dirigibles = slots_manual + n_hydrapple
        if cuerpo.id == Teal_Mask_Ogerpon_ex and not abilities_off:
            dirigibles += 1
        dirigibles = min(dirigibles, slots_hoy)
        if cartas > dirigibles:
            continue                     # not even with every route does it attack today
        nuevas = cartas - min(en_mano, dirigibles)
        if nuevas <= 0 or nuevas > nuevas_utiles_hoy:
            continue                     # the hand alone already unlocks it / does not fit
        if not desbloquea_hoy or nuevas < cartas_para_atacar:
            desbloquea_hoy = True
            cartas_para_atacar = nuevas

    # DEMAND is what the bodies ask for, not this turn's attachment capacity: the
    # recovery goes to the HAND, and a Grass energy kept there still works next
    # turn. With every attacker charged the demand is 0 and energy stops being
    # worth anything.
    return _PlanPlanta(
        unidad=unidad, en_mano=en_mano, slots_hoy=slots_hoy,
        nuevas_utiles_hoy=nuevas_utiles_hoy,
        desbloquea_hoy=desbloquea_hoy,
        cartas_para_atacar=cartas_para_atacar,
        pendiente=pendiente,
        demanda=min(tope, max(0, pendiente - en_mano)))

__all__ = [
    '_PlanPlanta',
    '_PlanPlanta',
    '_plan_de_planta',
]
