"""Plan de planta: cuantas Plantas sabe usar el campo y si desbloquean hoy.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.estado.agente import ESTADO
from ptcg.cartas.puntuacion import MAIN_ATTACKERS
from ptcg.cartas.ids import Basic_Grass_Energy, Hydrapple_ex, Teal_Mask_Ogerpon_ex
from ptcg.calculo.tablero import _active_of
from ptcg.calculo.energia import _grass_ability_slots, _grass_attach_unit
from dataclasses import dataclass


@dataclass
class _PlanPlanta:
    """Lectura de la MESA en clave de ENERGIA (ver `_plan_de_planta`)."""
    unidad: int              # energia EFECTIVA que aporta UNA Planta fisica
    en_mano: int             # Plantas ya disponibles en la mano
    slots_hoy: int           # adjuntes de Planta que aun caben ESTE turno
    nuevas_utiles_hoy: int   # Plantas NUEVAS que llegarian al campo HOY
    desbloquea_hoy: bool     # una Planta NUEVA pone a atacar a un cuerpo HOY
    cartas_para_atacar: int  # Plantas NUEVAS que exige ese desbloqueo
    pendiente: int           # Plantas que piden todos los atacantes en juego
    demanda: int             # Plantas NUEVAS que la mesa sabe usar (<= `tope`)


@dataclass
class _PlanPlanta:
    """Lectura de la MESA en clave de ENERGIA (ver `_plan_de_planta`)."""
    unidad: int              # energia EFECTIVA que aporta UNA Planta fisica
    en_mano: int             # Plantas ya disponibles en la mano
    slots_hoy: int           # adjuntes de Planta que aun caben ESTE turno
    nuevas_utiles_hoy: int   # Plantas NUEVAS que llegarian al campo HOY
    desbloquea_hoy: bool     # una Planta NUEVA pone a atacar a un cuerpo HOY
    cartas_para_atacar: int  # Plantas NUEVAS que exige ese desbloqueo
    pendiente: int           # Plantas que piden todos los atacantes en juego
    demanda: int             # Plantas NUEVAS que la mesa sabe usar (<= `tope`)


def _plan_de_planta(my_state, state, field_counts, hand_counts, tope=3,
                    puede_cambiar=False, habilidades_apagadas=False):
    """Cuantas Plantas NUEVAS sabe usar la mesa, y si alguna DESBLOQUEA un
    ataque HOY.

    Es la lectura de mesa que comparten la decision de JUGAR una carta de
    recuperacion (`_score_lanas_aid_play`) y la de QUE recuperar con ella (rama
    `Lanas_Aid` del contexto TO_HAND). Nacio del registro_018 paso 118 vs
    Crustle (PERDIDA): con Lana's Aid ya jugada, el agente levanto del descarte
    2 Applin + 1 Dipplin -- con la banca LLENA, cartas que no se pueden poner en
    juego -- teniendo delante un Tapu Bulu activo a UNA Planta de disparar Wood
    Hammer y tres Plantas disponibles en el descarte. La rama de seleccion no
    miraba la energia en absoluto (caia al scorer generico, que puntua "formas
    de linea evolutiva"), y la de jugada solo sabia leer a Hydrapple ex.

    Vias por las que una Planta de la MANO llega al campo en un turno:
      * el adjunte MANUAL, si aun no se ha gastado (`state.energyAttached`);
      * una habilidad de carga viva (`_grass_ability_slots`): *Teal Dance* de
        cada Teal Mask Ogerpon ex (solo se carga A SI MISMA) y *Ripening
        Charge* de cada Hydrapple ex (carga a CUALQUIERA de los nuestros).

    `len(energies)` YA es energia efectiva y `_grass_attach_unit()` es lo que
    suma UNA Planta FISICA (2 con Meganium en juego), asi que el deficit de un
    cuerpo se mide en CARTAS: `ceil((req - efectiva) / unidad)`.

    Solo cuentan los cuerpos de `MAIN_ATTACKERS`: es la lista curada de "con
    quien atacamos de verdad", asi que un Chikorita o un Applin de banca nunca
    inventan demanda de energia (`ATTACK_ENERGY_REQ` si les asigna coste).

    `desbloquea_hoy` solo mira al ACTIVO, salvo que `puede_cambiar` diga que hay
    una retirada/cambio disponible: un atacante de banca cargado no ataca hoy si
    no puede subir. Los cuerpos de banca si suman siempre a `pendiente`, que es
    demanda a dos turnos.

    `habilidades_apagadas` (Team Rocket's Watchtower / Iron Thorns activo, la
    bandera `meowth_ability_lock`) borra las dos vias de HABILIDAD: con el lock
    puesto solo queda el adjunte manual, y dar por vivas Teal Dance/Ripening
    inventa desbloqueos que no existen.
    """
    unidad = _grass_attach_unit()
    en_mano = hand_counts.get(Basic_Grass_Energy, 0)
    slots_manual = 0 if state.energyAttached else 1
    slots_hab = (0 if habilidades_apagadas
                 else _grass_ability_slots(state, field_counts))
    slots_hoy = slots_manual + slots_hab
    nuevas_utiles_hoy = max(0, slots_hoy - en_mano)
    n_hydrapple = 0 if habilidades_apagadas else field_counts.get(Hydrapple_ex, 0)

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
            continue                     # ya ataca: no pide energia
        cartas = -(-falta // unidad)     # techo de la division
        pendiente += cartas
        if not es_activo and not puede_cambiar:
            continue                     # cargado o no, hoy no ataca
        # Vias que pueden apuntar a ESTE cuerpo hoy. Teal Dance solo carga a su
        # propio portador; el adjunte manual y Ripening Charge, a cualquiera.
        dirigibles = slots_manual + n_hydrapple
        if cuerpo.id == Teal_Mask_Ogerpon_ex and not habilidades_apagadas:
            dirigibles += 1
        dirigibles = min(dirigibles, slots_hoy)
        if cartas > dirigibles:
            continue                     # ni con todas las vias ataca hoy
        nuevas = cartas - min(en_mano, dirigibles)
        if nuevas <= 0 or nuevas > nuevas_utiles_hoy:
            continue                     # la mano sola ya lo desbloquea / no cabe
        if not desbloquea_hoy or nuevas < cartas_para_atacar:
            desbloquea_hoy = True
            cartas_para_atacar = nuevas

    # La DEMANDA es lo que piden los cuerpos, no la capacidad de adjunte de este
    # turno: la recuperacion va a la MANO, y una Planta guardada sigue sirviendo
    # el turno siguiente. Con todos los atacantes cargados la demanda es 0 y la
    # energia deja de valer.
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
