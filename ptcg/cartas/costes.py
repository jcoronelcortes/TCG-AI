"""Coste de ataque BASE de nuestros atacantes.

Es la tabla sin impuestos: el coste impreso en la carta. `_aplicar_impuesto_tera`
construye a partir de ella la tabla EFECTIVA del turno (`ESTADO.ATTACK_ENERGY_REQ`),
sumando +1 a nuestros Tera cuando Nighttime Mine esta en mesa.

Vivio en main.py como `ATTACK_ENERGY_REQ` hasta la Ola 3 y era la trampa mas
sutil del refactor: parecia una constante, la leian 56 sitios, y sin embargo se
REESCRIBIA en cada llamada a agent(). No aparecia en ninguna sentencia `global`
porque mutar un dict no lo exige. Ahora la parte constante esta aqui y la parte
que cambia vive donde le corresponde, en el estado.
"""

from ptcg.cartas.ids import *  # noqa: F401,F403


ATTACK_ENERGY_REQ_BASE = {
    Hydrapple_ex: 2, Dipplin: 1, Teal_Mask_Ogerpon_ex: 3,
    Tapu_Bulu: 4, Fezandipiti_ex: 3, Meganium: 4, Pinsir: 2,
    Bayleef: 2, Applin: 1, Chikorita: 1,
}


__all__ = ['ATTACK_ENERGY_REQ_BASE']
