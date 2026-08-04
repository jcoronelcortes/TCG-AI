"""BASE attack cost of our attackers.

This is the untaxed table: the cost printed on the card. `_aplicar_impuesto_tera`
builds the turn's EFFECTIVE table from it (`ESTADO.ATTACK_ENERGY_REQ`),
adding +1 to our Tera Pokemon while Nighttime Mine is on the field.

It lived in main.py as `ATTACK_ENERGY_REQ` until wave 3 and was the subtlest
trap of the refactor: it looked like a constant, 56 places read it, and yet it
was REWRITTEN on every call to agent(). It never appeared in a `global`
statement because mutating a dict does not require one. Now the constant part
lives here and the part that changes lives where it belongs, in the state.
"""

from ptcg.cards.ids import *  # noqa: F401,F403


ATTACK_ENERGY_REQ_BASE = {
    Hydrapple_ex: 2, Dipplin: 1, Teal_Mask_Ogerpon_ex: 3,
    Tapu_Bulu: 4, Fezandipiti_ex: 3, Meganium: 4, Pinsir: 2,
    Bayleef: 2, Applin: 1, Chikorita: 1,
}


__all__ = ['ATTACK_ENERGY_REQ_BASE']
