"""Plan de planta: cuantas Plantas sabe usar el campo y si desbloquean hoy.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

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

__all__ = [
    '_PlanPlanta',
    '_PlanPlanta',
]
