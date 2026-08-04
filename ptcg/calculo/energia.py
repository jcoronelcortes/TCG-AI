"""Effective energy: Wild Growth, Ogerpon caps and attack cost.

Extracted VERBATIM from main.py by utils/extraer_definiciones.py
(docs/project-history.md). Its purity is verified by
utils/pureza.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.estado.agente import ESTADO
from ptcg.cartas.tablas import attack_table, card_table
from ptcg.cartas.ids import Applin, Chikorita, Hydrapple_ex, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.cartas.grupos import Nighttime_Mine, OUR_TERA_IDS
from ptcg.cartas.costes import ATTACK_ENERGY_REQ_BASE
from ptcg.calculo.tablero import _active_of
from cg.api import EnergyType


def _grass_mult():
    # The game observation ALREADY applies Meganium's Wild Growth: every PHYSICAL
    # basic Grass energy appears DUPLICATED in the `energies` list, so
    # len(energies) IS the EFFECTIVE energy. That is why this multiplier is 1
    # (it is kept as a function so the inherited `raw * _grass_mult()` sites keep
    # returning effective energy without being rewritten).
    return 1


def _ogerpon_base_phys_cap(meganium, is_hop):
    # BASE cap of PHYSICAL energies on a Teal Mask Ogerpon ex (user's rule).
    # With Meganium in play: 2 physical (Wild Growth doubles them => 4 effective,
    # more than enough for Myriad Leaf Shower, cost 3). Without Meganium: 3 vs the
    # Hop's deck ("it cannot have more than three energies attached") and 4 in the
    # other capped matchups (Alakazam). Single source of truth for the manual
    # attachment, Ripening Charge and Teal Dance.
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


def _grass_attach_unit():
    # EFFECTIVE energy provided by ONE freshly attached basic Grass energy (from
    # hand or recovered). With Meganium's Wild Growth in play one physical Grass
    # provides {G}{G} = 2 effective; without Meganium, 1.
    return 2 if ESTADO.meganium_in_play else 1


def _grass_ability_slots(state, field_counts):
    """Grass charging abilities (Teal Dance on each Teal Mask Ogerpon ex +
    Ripening Charge on each Hydrapple ex) that can STILL attach this turn.

    Each one is "once during your turn" and per Pokemon, so the capacity is the
    number of bearers in play. The ones already used are estimated from the
    logs: of all the Grass energies attached this turn, ONE is the manual
    attachment if `state.energyAttached` is already set; the rest can only have
    come from an ability. The estimate is conservative: if it overshoots, the
    play is simply not proposed (it never invents an impossible charge)."""
    capacidad = (field_counts.get(Teal_Mask_Ogerpon_ex, 0)
                 + field_counts.get(Hydrapple_ex, 0))
    usadas = ESTADO._grass_attaches_this_turn - (1 if state.energyAttached else 0)
    return max(0, capacidad - max(0, usadas))


def _grass_ability_slots_active(state, my_state, field_counts):
    """Ability charges that can still put a Grass energy ON THE ACTIVE.

    A subset of `_grass_ability_slots`: Ripening Charge (Hydrapple ex) attaches
    to ANY of our Pokemon, so every bearer in play counts; Teal Dance (Teal Mask
    Ogerpon ex) attaches ONLY to itself, so it only counts when the Ogerpon IS
    the active. Same conservative estimate of already-used abilities as the
    general function (subtracting every ability charge of the turn from this
    subset can fall short, never long: in the worst case the play is not
    proposed)."""
    capacidad = field_counts.get(Hydrapple_ex, 0)
    _act = _active_of(my_state)
    if _act is not None and _act.id == Teal_Mask_Ogerpon_ex:
        capacidad += 1
    usadas = ESTADO._grass_attaches_this_turn - (1 if state.energyAttached else 0)
    return max(0, capacidad - max(0, usadas))


def _grass_attach_route_open(state, field_counts, abilities_off=False):
    """Whether there is any route to put ONE Grass energy from hand onto the
    field this turn: the manual attachment if it is still available, or a live
    charging ability."""
    if not state.energyAttached:
        return True
    if abilities_off:
        return False
    return _grass_ability_slots(state, field_counts) >= 1


def _physical_energy(effective_len):
    # Converts EFFECTIVE energy (len(energies), already doubled by OUR Meganium's
    # Wild Growth) into PHYSICAL energy cards. With Meganium each physical Grass
    # counts as 2 effective, so physical = effective // 2; without Meganium,
    # effective == physical.
    return effective_len // 2 if ESTADO.meganium_in_play else effective_len


def _ripen_energy_capped(pokemon, ogerpon_phys_cap=None):
    """True if `pokemon` is already at its cap of physical energies, that is,
    if `energy_score` would veto sending it one more Grass. It mirrors the hard
    caps of energy_score (Chikorita 1, Applin 1, Tapu Bulu 2/4, Ogerpon by
    matchup) so that Ripening Charge's healing never points at a vetoed body.
    `ogerpon_phys_cap` is the matchup's PHYSICAL cap for Teal Mask Ogerpon ex
    (Cubchoo/Alakazam/Hop's); None = no matchup cap."""
    phys = _physical_energy(len(getattr(pokemon, 'energies', []) or []))
    pid = getattr(pokemon, 'id', 0)
    if pid in (Chikorita, Applin):
        return phys >= 1
    if pid == Tapu_Bulu:
        return phys >= (2 if ESTADO.meganium_in_play else 4)
    if pid == Teal_Mask_Ogerpon_ex:
        if ESTADO.op_is_crustle_deck and phys >= 2:
            return True
        if ogerpon_phys_cap is not None and phys >= ogerpon_phys_cap:
            return True
    return False


def _retreat_cards(retreat_cost):
    # Number of PHYSICAL energy cards needed to pay `retreat_cost` (expressed in
    # EFFECTIVE units). With Meganium each Grass pays for two (ceiling division).
    # 0 if the cost is <= 0.
    if retreat_cost <= 0:
        return 0
    return -(-retreat_cost // _grass_attach_unit())


def _retreat_grass_units(retreat_cost):
    """EFFECTIVE Grass units that DISAPPEAR from the field when paying a
    retreat of `retreat_cost` symbols.

    The cost is paid with whole CARDS, and with Meganium's Wild Growth each
    physical Grass is worth TWO units: retreating for ONE symbol erases TWO
    units from the count that Syrup Storm scales with. Subtracting the cost in
    symbols (or the number of cards) overestimates the damage by exactly that
    factor -- user, registro_006 step 78 vs Archaludon ex (LOST): the plan
    believed the benched Hydrapple ex knocked out (10-1 = 9 units -> 300 - 30
    resistance = 270 = exact HP) when the reality after retreating was 8 units
    -> 240, and the attack log confirms the 240."""
    return _retreat_cards(retreat_cost) * _grass_attach_unit()


def _aplicar_impuesto_tera(stadium_cards) -> bool:
    """Raises the cost of our Tera by +1 if Nighttime Mine is on the field.

    Returns whether the mine is active. It must be called at the START of
    agent(), before any scoring: if it were done further down, the blocks that
    had already read the cost would keep the old value -- the same failure the
    `energy_score` ceiling documents (which is why it lives in the wrapper and
    not at the end of the function).
    """
    activa = any(getattr(c, 'id', 0) == Nighttime_Mine
                 for c in (stadium_cards or []))
    for _tid in OUR_TERA_IDS:
        _base = ATTACK_ENERGY_REQ_BASE.get(_tid)
        if _base is not None:
            ESTADO.ATTACK_ENERGY_REQ[_tid] = _base + (1 if activa else 0)
    return activa


def _can_attack_eff(card_id, raw_energy):
    # True if the card can attack. raw_energy = len(energies) is ALREADY the
    # effective energy (the observation applies Wild Growth), so it is compared
    # directly.
    #
    # It is deliberately NOT generalised to `_coste_de_ataque_min`:
    # `ATTACK_ENERGY_REQ` is not just card data, it is the CURATED list of "bodies
    # we really attack with". Meowth ex (which has an attack) is out precisely so
    # that no rule treats it as an attacker -- see the hard veto of Meowth ex on
    # the bench. Deriving the cost from card data here would turn it into an
    # attacker in ~20 places in the file.
    _req = ESTADO.ATTACK_ENERGY_REQ.get(card_id)
    return _req is not None and raw_energy >= _req


def _min_attack_cost(card_id):
    """Minimum energy `card_id` needs in order to attack, DERIVED FROM THE
    CARD DATA (`card_table` -> attack ids -> `attack_table`).

    Deck-agnostic complement to `ATTACK_ENERGY_REQ`, which only covers the cards
    of the current deck.csv. It is used as a LAST resort, for bodies the curated
    configuration does not know (another deck loaded into deck.csv).

    Returns None when it cannot be known (unknown card, no attacks, or only
    zero-cost attacks -- there energy unlocks nothing).
    """
    data = card_table.get(card_id)
    if data is None:
        return None
    costs = []
    for _aid in (getattr(data, 'attacks', None) or []):
        _atk = attack_table.get(_aid)
        if _atk is None:
            continue
        _n = len(getattr(_atk, 'energies', None) or [])
        if _n > 0:
            costs.append(_n)
    return min(costs) if costs else None

__all__ = [
    '_grass_mult',
    '_ogerpon_base_phys_cap',
    'count_total_grass_energy',
    'calc_syrup_storm_damage',
    '_grass_attach_unit',
    '_grass_ability_slots',
    '_grass_ability_slots_active',
    '_grass_attach_route_open',
    '_physical_energy',
    '_can_attack_eff',
    '_aplicar_impuesto_tera',
    '_min_attack_cost',
    '_ripen_energy_capped',
    '_retreat_cards',
    '_retreat_grass_units',
]
