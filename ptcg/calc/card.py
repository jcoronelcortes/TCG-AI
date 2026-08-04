"""Reading cards: access to the observation, prizes and body value.

Extracted VERBATIM from main.py by utils/extraer_definiciones.py
(docs/project-history.md). Its purity is verified by
utils/pureza.py: nothing here touches mutable state or the runtime tables.
"""

from cg.api import AreaType, Card, EnergyType, Observation, Pokemon
from ptcg.cards.ids import Alakazam_ex, Dusknoir, Gardevoir_ex, Meganium, Munkidori_ex, Slowking, Typhlosion
from ptcg.cards.tables import card_table
from ptcg.state.agent_state import AGENT_STATE


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
    """prize_count for OPPONENT Pokemon: applies the prize denial on their
    side (P0.2). Munkidori ex with Pecharunt ex in play yields 1 less; with
    Mega Gengar ex in play, one of our ex knocking out an opposing {D} yields
    1 less (conservative: almost all of our attackers are ex, so the reduction
    is always assumed). Use ONLY on opposing Pokemon: the prizes OUR bodies
    hand over (e.g. our Fezandipiti ex, also {D}) are still measured with
    prize_count."""
    count = prize_count(pokemon)
    if count <= 0:
        return 0
    if AGENT_STATE._op_prize_denial_pecharunt and pokemon.id == Munkidori_ex:
        count -= 1
    if AGENT_STATE._op_prize_denial_gengar:
        _pd_data = card_table.get(pokemon.id)
        if (_pd_data is not None
                and getattr(_pd_data, 'energyType', None) == EnergyType.DARKNESS):
            count -= 1
    return max(0, count)


# NOTE (step 4b of the jul 2026 plan, MEASURED AND REVERTED): a deck-out brake
# for Teal Dance was tried (deck <=5 -> veto the degraded bands <=7500, mirroring
# the brakes of Lillie's and BCS; the ability ALSO draws 1 from the deck). It
# measured consistently NEGATIVE vs Comfey (-1.8 over 1000 and -1.1 over 2000
# games per branch; aggregate ~-1.3) with a benefit vs crustle inside the noise
# (+1.6): against MILL it is the OPPONENT who burns the deck clock -- saving our
# own draws does not buy turns, and the energy tempo towards Myriad is
# everything. Same criterion as the a8c8163 sweep (Cubchoo exemption).
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
    """prize_count for OPPONENT Pokemon: applies the prize denial on their
    side (P0.2). Munkidori ex with Pecharunt ex in play yields 1 less; with
    Mega Gengar ex in play, one of our ex knocking out an opposing {D} yields
    1 less (conservative: almost all of our attackers are ex, so the reduction
    is always assumed). Use ONLY on opposing Pokemon: the prizes OUR bodies
    hand over (e.g. our Fezandipiti ex, also {D}) are still measured with
    prize_count."""
    count = prize_count(pokemon)
    if count <= 0:
        return 0
    if AGENT_STATE._op_prize_denial_pecharunt and pokemon.id == Munkidori_ex:
        count -= 1
    if AGENT_STATE._op_prize_denial_gengar:
        _pd_data = card_table.get(pokemon.id)
        if (_pd_data is not None
                and getattr(_pd_data, 'energyType', None) == EnergyType.DARKNESS):
            count -= 1
    return max(0, count)


# NOTE (step 4b of the jul 2026 plan, MEASURED AND REVERTED): a deck-out brake
# for Teal Dance was tried (deck <=5 -> veto the degraded bands <=7500, mirroring
# the brakes of Lillie's and BCS; the ability ALSO draws 1 from the deck). It
# measured consistently NEGATIVE vs Comfey (-1.8 over 1000 and -1.1 over 2000
# games per branch; aggregate ~-1.3) with a benefit vs crustle inside the noise
# (+1.6): against MILL it is the OPPONENT who burns the deck clock -- saving our
# own draws does not buy turns, and the energy tempo towards Myriad is
# everything. Same criterion as the a8c8163 sweep (Cubchoo exemption).
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
