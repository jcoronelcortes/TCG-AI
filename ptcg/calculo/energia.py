"""Energia efectiva: Wild Growth, topes de Ogerpon y coste de ataque.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from cg.api import EnergyType


def _grass_mult():
    # La observacion del juego YA aplica Wild Growth de Meganium: cada energia
    # basica de Planta FISICA aparece DUPLICADA en la lista `energies`, por lo
    # que len(energies) ES la energia EFECTIVA. Por eso este multiplicador es 1
    # (se conserva como funcion para que los sitios `crudo * _grass_mult()`
    # heredados sigan devolviendo la energia efectiva sin reescribirlos).
    return 1


def _ogerpon_base_phys_cap(meganium, is_hop):
    # Tope BASE de energias FISICAS de un Teal Mask Ogerpon ex (regla del user).
    # Con Meganium en juego: 2 fisicas (Wild Growth las duplica => 4 efectivas,
    # de sobra para Myriad Leaf Shower, coste 3). Sin Meganium: 3 vs el mazo de
    # Hop's ("no puede tener mas de tres energias cargadas") y 4 en el resto de
    # matchups con tope (Alakazam). Fuente unica de verdad para el adjunte
    # manual, Ripening Charge y Teal Dance.
    if meganium:
        return 2
    return 3 if is_hop else 4


def count_total_grass_energy(my_state) -> int:
    total = 0
    for pokemon in my_state.active + my_state.bench:
        if pokemon is None:
            continue
        for e in pokemon.energies:
            if e == EnergyType.GRASS:
                total += 1
    return total


def calc_syrup_storm_damage(my_state, has_meganium: bool) -> int:
    total_grass = count_total_grass_energy(my_state)
    if has_meganium:

        pass
    return 30 + 30 * total_grass

__all__ = [
    '_grass_mult',
    '_ogerpon_base_phys_cap',
    'count_total_grass_energy',
    'calc_syrup_storm_damage',
]
