"""Lectura de cartas: acceso a la observacion, premios y valor de cuerpo.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from cg.api import AreaType, Card, EnergyType, Observation, Pokemon
from ptcg.cartas.ids import Alakazam_ex, Dusknoir, Gardevoir_ex, Meganium, Munkidori_ex, Slowking, Typhlosion
from ptcg.cartas.tablas import card_table
from ptcg.estado.agente import ESTADO


def get_card(obs: Observation, area: AreaType, index: int, player_index: int) -> Pokemon | Card | None:
    ps = obs.current.players[player_index]
    try:
        match area:
            case AreaType.DECK:
                return obs.select.deck[index]
            case AreaType.HAND:
                return ps.hand[index]
            case AreaType.DISCARD:
                return ps.discard[index]
            case AreaType.ACTIVE:
                return ps.active[index]
            case AreaType.BENCH:
                return ps.bench[index]
            case AreaType.PRIZE:
                return ps.prize[index]
            case AreaType.STADIUM:
                return obs.current.stadium[index]
            case AreaType.LOOKING:
                return obs.current.looking[index]
            case _:
                return None
    except (IndexError, AttributeError, TypeError):
        return None


def prize_count(pokemon: Pokemon) -> int:
    data = card_table[pokemon.id]
    count = 3 if data.megaEx else 2 if data.ex else 1
    for card in pokemon.energyCards:
        if card.id == 12:
            count -= 1
    for card in pokemon.tools:
        if card.id == 1172 and "Lillie" in data.name:
            count -= 1
    return max(0, count)


def prize_count_op(pokemon: Pokemon) -> int:
    """prize_count para Pokemon DEL RIVAL: aplica la denegacion de premios de
    su lado (P0.2). Munkidori ex con Pecharunt ex en juego rinde 1 menos; con
    Mega Gengar ex en juego, el KO de un {D} rival por un ex nuestro rinde 1
    menos (conservador: casi todos nuestros atacantes son ex, asi que se asume
    la reduccion siempre). Usar SOLO sobre Pokemon del rival: los premios que
    entregan NUESTROS cuerpos (p.ej. nuestro Fezandipiti ex, tambien {D}) se
    siguen midiendo con prize_count."""
    count = prize_count(pokemon)
    if count <= 0:
        return 0
    if ESTADO._op_prize_denial_pecharunt and pokemon.id == Munkidori_ex:
        count -= 1
    if ESTADO._op_prize_denial_gengar:
        _pd_data = card_table.get(pokemon.id)
        if (_pd_data is not None
                and getattr(_pd_data, 'energyType', None) == EnergyType.DARKNESS):
            count -= 1
    return max(0, count)


# NOTA (paso 4b plan jul 2026, MEDIDO Y REVERTIDO): se intento un freno de
# deck-out para Teal Dance (mazo <=5 -> vetar las bandas degradadas <=7500,
# espejo de los frenos de Lillie's y BCS; la habilidad ADEMAS roba 1 del
# mazo). Midio NEGATIVO consistente vs Comfey (-1.8 en 1000 y -1.1 en 2000
# partidas por rama; agregado ~-1.3) con beneficio en crustle dentro del
# ruido (+1.6): contra MILL el reloj del mazo lo quema el RIVAL -- ahorrar
# robos propios no compra turnos y el tempo de energia hacia Myriad lo es
# todo. Mismo criterio que el barrido de a8c8163 (exencion Cubchoo).
def pokemon_score(pokemon: Pokemon) -> int:
    data = card_table[pokemon.id]
    score = prize_count(pokemon) * 1000
    score += len(pokemon.energies) * 150
    score += len(pokemon.tools) * 100
    if data.stage2:
        score += 250
    elif data.stage1:
        score += 130

    pid = pokemon.id

    if pid == 144 or pid == 322 or pid == 323 or pid == 337:
        score -= 200
    if pid == 112 and len(pokemon.energies) >= 1:
        score += 300

    if pid == Meganium:
        score += 350
    elif pid == Gardevoir_ex:
        score += 400
    elif pid == Typhlosion:
        score += 350
    elif pid == Slowking:
        score += 400
    elif pid == Dusknoir:
        score += 350
    elif pid == Alakazam_ex:
        score += 300
    score += pokemon.hp
    return score


def get_card(obs: Observation, area: AreaType, index: int, player_index: int) -> Pokemon | Card | None:
    ps = obs.current.players[player_index]
    try:
        match area:
            case AreaType.DECK:
                return obs.select.deck[index]
            case AreaType.HAND:
                return ps.hand[index]
            case AreaType.DISCARD:
                return ps.discard[index]
            case AreaType.ACTIVE:
                return ps.active[index]
            case AreaType.BENCH:
                return ps.bench[index]
            case AreaType.PRIZE:
                return ps.prize[index]
            case AreaType.STADIUM:
                return obs.current.stadium[index]
            case AreaType.LOOKING:
                return obs.current.looking[index]
            case _:
                return None
    except (IndexError, AttributeError, TypeError):
        return None


def prize_count(pokemon: Pokemon) -> int:
    data = card_table[pokemon.id]
    count = 3 if data.megaEx else 2 if data.ex else 1
    for card in pokemon.energyCards:
        if card.id == 12:
            count -= 1
    for card in pokemon.tools:
        if card.id == 1172 and "Lillie" in data.name:
            count -= 1
    return max(0, count)


def prize_count_op(pokemon: Pokemon) -> int:
    """prize_count para Pokemon DEL RIVAL: aplica la denegacion de premios de
    su lado (P0.2). Munkidori ex con Pecharunt ex en juego rinde 1 menos; con
    Mega Gengar ex en juego, el KO de un {D} rival por un ex nuestro rinde 1
    menos (conservador: casi todos nuestros atacantes son ex, asi que se asume
    la reduccion siempre). Usar SOLO sobre Pokemon del rival: los premios que
    entregan NUESTROS cuerpos (p.ej. nuestro Fezandipiti ex, tambien {D}) se
    siguen midiendo con prize_count."""
    count = prize_count(pokemon)
    if count <= 0:
        return 0
    if ESTADO._op_prize_denial_pecharunt and pokemon.id == Munkidori_ex:
        count -= 1
    if ESTADO._op_prize_denial_gengar:
        _pd_data = card_table.get(pokemon.id)
        if (_pd_data is not None
                and getattr(_pd_data, 'energyType', None) == EnergyType.DARKNESS):
            count -= 1
    return max(0, count)


# NOTA (paso 4b plan jul 2026, MEDIDO Y REVERTIDO): se intento un freno de
# deck-out para Teal Dance (mazo <=5 -> vetar las bandas degradadas <=7500,
# espejo de los frenos de Lillie's y BCS; la habilidad ADEMAS roba 1 del
# mazo). Midio NEGATIVO consistente vs Comfey (-1.8 en 1000 y -1.1 en 2000
# partidas por rama; agregado ~-1.3) con beneficio en crustle dentro del
# ruido (+1.6): contra MILL el reloj del mazo lo quema el RIVAL -- ahorrar
# robos propios no compra turnos y el tempo de energia hacia Myriad lo es
# todo. Mismo criterio que el barrido de a8c8163 (exencion Cubchoo).
def pokemon_score(pokemon: Pokemon) -> int:
    data = card_table[pokemon.id]
    score = prize_count(pokemon) * 1000
    score += len(pokemon.energies) * 150
    score += len(pokemon.tools) * 100
    if data.stage2:
        score += 250
    elif data.stage1:
        score += 130

    pid = pokemon.id

    if pid == 144 or pid == 322 or pid == 323 or pid == 337:
        score -= 200
    if pid == 112 and len(pokemon.energies) >= 1:
        score += 300

    if pid == Meganium:
        score += 350
    elif pid == Gardevoir_ex:
        score += 400
    elif pid == Typhlosion:
        score += 350
    elif pid == Slowking:
        score += 400
    elif pid == Dusknoir:
        score += 350
    elif pid == Alakazam_ex:
        score += 300
    score += pokemon.hp
    return score

__all__ = [
    'get_card',
    'prize_count',
    'prize_count_op',
    'pokemon_score',
    'get_card',
    'prize_count',
    'prize_count_op',
    'pokemon_score',
]
