"""Lectura del rival: deficit de ataque, cuerpos inofensivos y mano.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.cartas.ids import ALAKAZAM_ATTACKER_IDS, CRUSTLE_LINE_IDS, DUNSPARCE_IDS
from ptcg.cartas.tablas import attack_table, card_table


def _alakazam_relevo_de_atacante(op_state):
    """vs Alakazam: ¿el gusteo RELEVA a su atacante en vez de regalarselo?

    Abra -> Kadabra -> Alakazam es la UNICA linea atacante del mazo, asi que
    subir con Boss's Orders cualquiera de esos cuerpos ADELANTA su plan: el
    rival evoluciona y ataca con el cuerpo que le pusimos delante (user,
    registro_002 paso 20 vs Alakazam, PERDIDA -- se le subio un Abra teniendo
    ellos el Kadabra en la mano). Ademas Boss's es una RETIRADA GRATIS que les
    regalamos: su activo se va a la banca sin pagar coste.

    El unico gusteo SIN KO que rinde en este matchup es el inverso: su atacante
    (Kadabra/Alakazam) ya esta de ACTIVO y CON energia, y lo mandamos a la banca
    cambiandolo por un cuerpo que no ataca -- un Abra pelado o cualquier cuerpo
    fuera de la linea (p.ej. su Fezandipiti ex). La energia invertida se queda
    parada en la banca y para volver tienen que pagar la retirada.

    Dunsparce nunca cuenta como relevo: es objetivo PROHIBIDO de gusteo
    (`DUNSPARCE_IDS`, regla del user).
    """
    act = op_state.active[0] if op_state.active else None
    if act is None or act.id not in ALAKAZAM_ATTACKER_IDS:
        return False
    if len(act.energies) < 1:
        return False
    for _b in (op_state.bench or []):
        if _b is None or _b.id in DUNSPARCE_IDS:
            continue
        if _b.id in ALAKAZAM_ATTACKER_IDS:
            continue        # cambiar un atacante por otro no releva nada
        return True
    return False


def _op_deficit_de_ataque(pkmn):
    """Energias que le FALTAN a `pkmn` (rival) para poder ATACAR: el coste de
    su ataque mas barato menos las energias que ya tiene (0 si ya puede).

    Es el TERCER numero que decide un gusteo sin KO, junto a las energias
    adjuntas y al coste de retirada (regla del user, registro_006 paso 65 vs
    Dragapult). Los otros dos no bastan: el Dragapult ex y el Drakloak pelados
    EMPATAN en ambos (0 energias, retirada 1) y son objetivos opuestos --
    Dragapult ex ataca con 1 energia, Drakloak necesita 2.

    Se mide por COSTE y nunca por dano: el dano IMPRESO miente en este entorno
    -- Powerful Hand (Alakazam), Cruel Arrow (Fezandipiti ex) y los dos ataques
    de Gardevoir ex figuran con 0 en `attack_table` y todos hacen dano real.

    Deck-agnostico: lee los costes del dato de carta (`card_table` -> ids de
    ataque -> `attack_table`), no de la tabla curada de NUESTRO mazo. Devuelve
    None cuando no se puede saber (carta sin ataques legibles): no se concluye
    nada por sospecha.

    `energies` con getattr: el objetivo del gusteo llega de `get_card()` y el
    resto del constructor del contexto ya lo trata como opcional
    (`len(card.energies) if hasattr(card, 'energies') else 0`). Una excepcion
    aqui seria un forfeit de la partida entera.
    """
    if pkmn is None:
        return None
    data = card_table.get(getattr(pkmn, 'id', 0))
    if data is None:
        return None
    costes = []
    for _aid in (getattr(data, 'attacks', None) or []):
        _atk = attack_table.get(_aid)
        if _atk is None:
            continue
        costes.append(len(getattr(_atk, 'energies', None) or []))
    if not costes:
        return None
    return max(0, min(costes) - len(getattr(pkmn, 'energies', None) or []))


def _op_cuerpo_inofensivo(pkmn):
    """`pkmn` (rival) NO puede atacar en su proximo turno NI adjuntandole una
    energia: TODOS sus ataques cuestan mas de `energias + 1`.

    Es el UMBRAL de `_op_deficit_de_ataque` (deficit >= 2): con deficit 1 el
    adjunte del turno rival ya le paga el ataque. Devuelve False cuando el
    deficit no se puede saber -- no se concluye "inofensivo" por sospecha -- y
    tambien con un ataque de coste 0, que puede usar hoy mismo.
    """
    _deficit = _op_deficit_de_ataque(pkmn)
    return _deficit is not None and _deficit >= 2


def _op_activo_inofensivo(op_state):
    """`_op_cuerpo_inofensivo` aplicado al ACTIVO rival."""
    return _op_cuerpo_inofensivo(op_state.active[0] if op_state.active else None)


def _op_juega_crustle(op_state):
    """¿Hay linea Crustle EN EL TABLERO rival (activo o banca)?"""
    if op_state is None:
        return False
    for _cr_pk in list(op_state.active or []) + list(op_state.bench or []):
        if _cr_pk is not None and _cr_pk.id in CRUSTLE_LINE_IDS:
            return True
    return False


def _op_hand_size(op_state):
    try:
        return len(op_state.hand) if op_state.hand else 0
    except (AttributeError, TypeError):
        return 0


def _op_disruption_belief(op_state, op_supporter_played):
    h = _op_hand_size(op_state)
    if h <= 0:
        return 0.05

    p_one = 2.0 / 40.0
    p_none = (1.0 - p_one) ** h
    p = 1.0 - p_none
    return max(0.05, min(0.85, p))


def _alakazam_relevo_de_atacante(op_state):
    """vs Alakazam: ¿el gusteo RELEVA a su atacante en vez de regalarselo?

    Abra -> Kadabra -> Alakazam es la UNICA linea atacante del mazo, asi que
    subir con Boss's Orders cualquiera de esos cuerpos ADELANTA su plan: el
    rival evoluciona y ataca con el cuerpo que le pusimos delante (user,
    registro_002 paso 20 vs Alakazam, PERDIDA -- se le subio un Abra teniendo
    ellos el Kadabra en la mano). Ademas Boss's es una RETIRADA GRATIS que les
    regalamos: su activo se va a la banca sin pagar coste.

    El unico gusteo SIN KO que rinde en este matchup es el inverso: su atacante
    (Kadabra/Alakazam) ya esta de ACTIVO y CON energia, y lo mandamos a la banca
    cambiandolo por un cuerpo que no ataca -- un Abra pelado o cualquier cuerpo
    fuera de la linea (p.ej. su Fezandipiti ex). La energia invertida se queda
    parada en la banca y para volver tienen que pagar la retirada.

    Dunsparce nunca cuenta como relevo: es objetivo PROHIBIDO de gusteo
    (`DUNSPARCE_IDS`, regla del user).
    """
    act = op_state.active[0] if op_state.active else None
    if act is None or act.id not in ALAKAZAM_ATTACKER_IDS:
        return False
    if len(act.energies) < 1:
        return False
    for _b in (op_state.bench or []):
        if _b is None or _b.id in DUNSPARCE_IDS:
            continue
        if _b.id in ALAKAZAM_ATTACKER_IDS:
            continue        # cambiar un atacante por otro no releva nada
        return True
    return False


def _op_deficit_de_ataque(pkmn):
    """Energias que le FALTAN a `pkmn` (rival) para poder ATACAR: el coste de
    su ataque mas barato menos las energias que ya tiene (0 si ya puede).

    Es el TERCER numero que decide un gusteo sin KO, junto a las energias
    adjuntas y al coste de retirada (regla del user, registro_006 paso 65 vs
    Dragapult). Los otros dos no bastan: el Dragapult ex y el Drakloak pelados
    EMPATAN en ambos (0 energias, retirada 1) y son objetivos opuestos --
    Dragapult ex ataca con 1 energia, Drakloak necesita 2.

    Se mide por COSTE y nunca por dano: el dano IMPRESO miente en este entorno
    -- Powerful Hand (Alakazam), Cruel Arrow (Fezandipiti ex) y los dos ataques
    de Gardevoir ex figuran con 0 en `attack_table` y todos hacen dano real.

    Deck-agnostico: lee los costes del dato de carta (`card_table` -> ids de
    ataque -> `attack_table`), no de la tabla curada de NUESTRO mazo. Devuelve
    None cuando no se puede saber (carta sin ataques legibles): no se concluye
    nada por sospecha.

    `energies` con getattr: el objetivo del gusteo llega de `get_card()` y el
    resto del constructor del contexto ya lo trata como opcional
    (`len(card.energies) if hasattr(card, 'energies') else 0`). Una excepcion
    aqui seria un forfeit de la partida entera.
    """
    if pkmn is None:
        return None
    data = card_table.get(getattr(pkmn, 'id', 0))
    if data is None:
        return None
    costes = []
    for _aid in (getattr(data, 'attacks', None) or []):
        _atk = attack_table.get(_aid)
        if _atk is None:
            continue
        costes.append(len(getattr(_atk, 'energies', None) or []))
    if not costes:
        return None
    return max(0, min(costes) - len(getattr(pkmn, 'energies', None) or []))


def _op_cuerpo_inofensivo(pkmn):
    """`pkmn` (rival) NO puede atacar en su proximo turno NI adjuntandole una
    energia: TODOS sus ataques cuestan mas de `energias + 1`.

    Es el UMBRAL de `_op_deficit_de_ataque` (deficit >= 2): con deficit 1 el
    adjunte del turno rival ya le paga el ataque. Devuelve False cuando el
    deficit no se puede saber -- no se concluye "inofensivo" por sospecha -- y
    tambien con un ataque de coste 0, que puede usar hoy mismo.
    """
    _deficit = _op_deficit_de_ataque(pkmn)
    return _deficit is not None and _deficit >= 2


def _op_activo_inofensivo(op_state):
    """`_op_cuerpo_inofensivo` aplicado al ACTIVO rival."""
    return _op_cuerpo_inofensivo(op_state.active[0] if op_state.active else None)


def _op_juega_crustle(op_state):
    """¿Hay linea Crustle EN EL TABLERO rival (activo o banca)?"""
    if op_state is None:
        return False
    for _cr_pk in list(op_state.active or []) + list(op_state.bench or []):
        if _cr_pk is not None and _cr_pk.id in CRUSTLE_LINE_IDS:
            return True
    return False


def _op_hand_size(op_state):
    try:
        return len(op_state.hand) if op_state.hand else 0
    except (AttributeError, TypeError):
        return 0


def _op_disruption_belief(op_state, op_supporter_played):
    h = _op_hand_size(op_state)
    if h <= 0:
        return 0.05

    p_one = 2.0 / 40.0
    p_none = (1.0 - p_one) ** h
    p = 1.0 - p_none
    return max(0.05, min(0.85, p))

__all__ = [
    '_op_deficit_de_ataque',
    '_op_cuerpo_inofensivo',
    '_op_activo_inofensivo',
    '_op_juega_crustle',
    '_op_hand_size',
    '_op_disruption_belief',
    '_alakazam_relevo_de_atacante',
    '_op_deficit_de_ataque',
    '_op_cuerpo_inofensivo',
    '_op_activo_inofensivo',
    '_op_juega_crustle',
    '_op_hand_size',
    '_op_disruption_belief',
    '_alakazam_relevo_de_atacante',
]
