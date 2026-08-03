"""Energia efectiva: Wild Growth, topes de Ogerpon y coste de ataque.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.estado.agente import ESTADO
from ptcg.cartas.tablas import attack_table, card_table
from ptcg.cartas.ids import Applin, Chikorita, Hydrapple_ex, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.cartas.grupos import Nighttime_Mine, OUR_TERA_IDS
from ptcg.cartas.costes import ATTACK_ENERGY_REQ_BASE
from ptcg.calculo.tablero import _active_of
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


def _grass_attach_unit():
    # Energia EFECTIVA que aporta UNA energia basica de Planta recien adjuntada
    # (desde la mano o recuperada). Con Wild Growth de Meganium en juego una
    # Planta fisica provee {G}{G} = 2 efectivas; sin Meganium, 1.
    return 2 if ESTADO.meganium_in_play else 1


def _grass_ability_slots(state, field_counts):
    """Habilidades de carga de Planta (Teal Dance de cada Teal Mask Ogerpon ex
    + Ripening Charge de cada Hydrapple ex) que AUN pueden adjuntar este turno.

    Cada una es "una vez durante tu turno" y por Pokemon, asi que la capacidad
    es el numero de portadores en juego. Las ya usadas se estiman con los logs:
    de todas las Plantas adjuntadas este turno, UNA es el adjunte manual si
    `state.energyAttached` ya esta puesto; el resto solo pudo venir de una
    habilidad. La estimacion es conservadora: si se pasa de largo, la jugada
    simplemente no se propone (nunca inventa una carga imposible)."""
    capacidad = (field_counts.get(Teal_Mask_Ogerpon_ex, 0)
                 + field_counts.get(Hydrapple_ex, 0))
    usadas = ESTADO._grass_attaches_this_turn - (1 if state.energyAttached else 0)
    return max(0, capacidad - max(0, usadas))


def _grass_ability_slots_activo(state, my_state, field_counts):
    """Cargas por HABILIDAD que todavia pueden dejar una Planta EN EL ACTIVO.

    Subconjunto de `_grass_ability_slots`: Ripening Charge (Hydrapple ex)
    adjunta a CUALQUIERA de nuestros Pokemon, asi que cada portador en juego
    sirve; Teal Dance (Teal Mask Ogerpon ex) adjunta SOLO a si mismo, asi que
    unicamente cuenta cuando el Ogerpon ES el activo. Misma estimacion
    conservadora de habilidades ya usadas que la funcion general (restar de
    este subconjunto todas las cargas por habilidad del turno puede quedarse
    corto, nunca largo: en el peor caso la jugada no se propone)."""
    capacidad = field_counts.get(Hydrapple_ex, 0)
    _act = _active_of(my_state)
    if _act is not None and _act.id == Teal_Mask_Ogerpon_ex:
        capacidad += 1
    usadas = ESTADO._grass_attaches_this_turn - (1 if state.energyAttached else 0)
    return max(0, capacidad - max(0, usadas))


def _grass_attach_route_open(state, field_counts, abilities_off=False):
    """Hay alguna via para poner en el campo UNA Planta de la mano este turno:
    el adjunte manual si sigue disponible, o una habilidad de carga viva."""
    if not state.energyAttached:
        return True
    if abilities_off:
        return False
    return _grass_ability_slots(state, field_counts) >= 1


def _physical_energy(effective_len):
    # Convierte energia EFECTIVA (len(energies), ya doblada por Wild Growth de
    # NUESTRO Meganium) a cartas de energia FISICAS. Con Meganium cada Planta
    # fisica cuenta como 2 efectivas, asi que fisica = efectiva // 2; sin
    # Meganium, efectiva == fisica.
    return effective_len // 2 if ESTADO.meganium_in_play else effective_len


def _ripen_energy_capped(pokemon, ogerpon_phys_cap=None):
    """True si `pokemon` ya esta en su TOPE de energias fisicas, es decir si
    `energy_score` vetaria dirigirle una Planta mas. Espeja los topes duros de
    energy_score (Chikorita 1, Applin 1, Tapu Bulu 2/4, Ogerpon por matchup)
    para que la curacion de Ripening Charge nunca apunte a un cuerpo vetado.
    `ogerpon_phys_cap` es el tope FISICO de Teal Mask Ogerpon ex del matchup
    (Cubchoo/Alakazam/Hop's); None = sin tope de matchup."""
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
    # Numero de cartas de energia FISICAS necesarias para pagar `retreat_cost`
    # (expresado en unidades EFECTIVAS). Con Meganium cada Planta paga por dos
    # (division con techo). 0 si el coste es <= 0.
    if retreat_cost <= 0:
        return 0
    return -(-retreat_cost // _grass_attach_unit())


def _retreat_grass_units(retreat_cost):
    """Unidades EFECTIVAS de Planta que DESAPARECEN del campo al pagar una
    retirada de `retreat_cost` simbolos.

    El coste se paga con CARTAS enteras, y con Wild Growth de Meganium cada
    Planta fisica vale DOS unidades: retirar por UN simbolo borra DOS unidades
    del recuento con el que escala Syrup Storm. Restar el coste en simbolos (o
    el numero de cartas) sobrestima el dano justo por ese factor -- user,
    registro_006 paso 78 vs Archaludon ex (PERDIDA): el plan creia que el
    Hydrapple ex de banca noqueaba (10-1 = 9 unidades -> 300 - 30 resistencia =
    270 = vida exacta) cuando la realidad tras retirar eran 8 unidades -> 240,
    y el log del ataque confirma los 240."""
    return _retreat_cards(retreat_cost) * _grass_attach_unit()


def _aplicar_impuesto_tera(stadium_cards) -> bool:
    """Sube +1 el coste de nuestros Tera si Nighttime Mine esta en mesa.

    Devuelve si la mina esta activa. Debe llamarse al PRINCIPIO de agent(),
    antes de cualquier puntuacion: si se hiciera mas abajo, los bloques que ya
    hubieran leido el coste seguirian con el valor viejo -- el mismo fallo que
    documenta el techo de `energy_score` (por eso va en el envoltorio y no al
    final de la funcion).
    """
    activa = any(getattr(c, 'id', 0) == Nighttime_Mine
                 for c in (stadium_cards or []))
    for _tid in OUR_TERA_IDS:
        _base = ATTACK_ENERGY_REQ_BASE.get(_tid)
        if _base is not None:
            ESTADO.ATTACK_ENERGY_REQ[_tid] = _base + (1 if activa else 0)
    return activa


def _can_attack_eff(card_id, raw_energy):
    # True si la carta puede atacar. raw_energy = len(energies) YA es la energia
    # efectiva (la observacion aplica Wild Growth), asi que se compara directo.
    #
    # NO se generaliza a `_coste_de_ataque_min` a proposito: `ATTACK_ENERGY_REQ`
    # no es solo un dato de carta, es la lista CURADA de "cuerpos con los que
    # de verdad atacamos". Meowth ex (que tiene ataque) esta fuera justamente
    # para que ninguna regla lo trate como atacante -- ver el veto duro de
    # Meowth ex en banca. Derivar el coste del dato de carta aqui lo convertiria
    # en atacante en ~20 puntos del fichero.
    _req = ESTADO.ATTACK_ENERGY_REQ.get(card_id)
    return _req is not None and raw_energy >= _req


def _coste_de_ataque_min(card_id):
    """Energia minima que necesita `card_id` para poder atacar, DERIVADA DEL
    DATO DE CARTA (`card_table` -> ids de ataque -> `attack_table`).

    Complemento deck-agnostico de `ATTACK_ENERGY_REQ`, que solo cubre las
    cartas del deck.csv actual. Se usa como ULTIMO recurso, para cuerpos que la
    configuracion curada no conoce (otro mazo cargado en deck.csv).

    Devuelve None si no se puede saber (carta desconocida, sin ataques, o solo
    con ataques de coste 0 -- ahi la energia no desbloquea nada).
    """
    data = card_table.get(card_id)
    if data is None:
        return None
    costes = []
    for _aid in (getattr(data, 'attacks', None) or []):
        _atk = attack_table.get(_aid)
        if _atk is None:
            continue
        _n = len(getattr(_atk, 'energies', None) or [])
        if _n > 0:
            costes.append(_n)
    return min(costes) if costes else None

__all__ = [
    '_grass_mult',
    '_ogerpon_base_phys_cap',
    'count_total_grass_energy',
    'calc_syrup_storm_damage',
    '_grass_attach_unit',
    '_grass_ability_slots',
    '_grass_ability_slots_activo',
    '_grass_attach_route_open',
    '_physical_energy',
    '_can_attack_eff',
    '_aplicar_impuesto_tera',
    '_coste_de_ataque_min',
    '_ripen_energy_capped',
    '_retreat_cards',
    '_retreat_grass_units',
]
