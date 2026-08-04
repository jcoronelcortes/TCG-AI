"""Reading the opponent: attack deficit, harmless bodies and hand.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.cards.ids import ALAKAZAM_ATTACKER_IDS, CRUSTLE_LINE_IDS, DUNSPARCE_IDS
from ptcg.cards.tables import attack_table, card_table


def _alakazam_attacker_relief(op_state):
    """vs Alakazam: does the gust RELIEVE their attacker instead of handing it over?

    Abra -> Kadabra -> Alakazam is the deck's ONLY attacking line, so bringing
    up any of those bodies with Boss's Orders ADVANCES their plan: the opponent
    evolves and attacks with the body we put in front of us (user, registro_002
    step 20 vs Alakazam, LOST -- an Abra was brought up while they held the
    Kadabra in hand). On top of that, Boss's is a FREE RETREAT we give them:
    their active goes to the bench without paying a cost.

    The only gust WITHOUT a KO that pays off in this matchup is the reverse:
    their attacker (Kadabra/Alakazam) is already ACTIVE and CHARGED, and we send
    it to the bench swapping it for a body that does not attack -- a bare Abra or
    any body outside the line (e.g. their Fezandipiti ex). The invested energy
    is left stranded on the bench and to come back they have to pay the retreat.

    Dunsparce never counts as relief: it is a FORBIDDEN gust target
    (`DUNSPARCE_IDS`, user's rule).
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
            continue        # swapping one attacker for another relieves nothing
        return True
    return False


def _op_attack_deficit(pkmn):
    """Energies `pkmn` (opponent) is MISSING in order to ATTACK: the cost of
    its cheapest attack minus the energies it already has (0 if it already can).

    This is the THIRD number that decides a gust without a KO, alongside the
    attached energies and the retreat cost (user's rule, registro_006 step 65 vs
    Dragapult). The other two are not enough: a bare Dragapult ex and a bare
    Drakloak TIE on both (0 energies, retreat 1) and are opposite targets --
    Dragapult ex attacks with 1 energy, Drakloak needs 2.

    It is measured by COST and never by damage: PRINTED damage lies in this
    environment -- Powerful Hand (Alakazam), Cruel Arrow (Fezandipiti ex) and
    both attacks of Gardevoir ex are listed as 0 in `attack_table` and all of
    them deal real damage.

    Deck-agnostic: it reads the costs from the card data (`card_table` -> attack
    ids -> `attack_table`), not from OUR deck's curated table. It returns None
    when it cannot be known (a card with no readable attacks): nothing is
    concluded on suspicion.

    `energies` via getattr: the gust target arrives from `get_card()` and the
    rest of the context constructor already treats it as optional
    (`len(card.energies) if hasattr(card, 'energies') else 0`). An exception
    here would be a forfeit of the whole game.
    """
    if pkmn is None:
        return None
    data = card_table.get(getattr(pkmn, 'id', 0))
    if data is None:
        return None
    costs = []
    for _aid in (getattr(data, 'attacks', None) or []):
        _atk = attack_table.get(_aid)
        if _atk is None:
            continue
        costs.append(len(getattr(_atk, 'energies', None) or []))
    if not costs:
        return None
    return max(0, min(costs) - len(getattr(pkmn, 'energies', None) or []))


def _op_body_is_harmless(pkmn):
    """`pkmn` (opponent) CANNOT attack on its next turn EVEN by attaching one
    energy: ALL of its attacks cost more than `energies + 1`.

    This is the THRESHOLD of `_op_attack_deficit` (deficit >= 2): with a
    deficit of 1 the opponent's attachment for the turn already pays for the
    attack. It returns False when the deficit cannot be known -- "harmless" is
    never concluded on suspicion -- and also with a zero-cost attack, which they
    can use this very turn.
    """
    _deficit = _op_attack_deficit(pkmn)
    return _deficit is not None and _deficit >= 2


def _op_active_is_harmless(op_state):
    """`_op_body_is_harmless` applied to the opposing ACTIVE."""
    return _op_body_is_harmless(op_state.active[0] if op_state.active else None)


def _op_juega_crustle(op_state):
    """Is there a Crustle line ON the opposing BOARD (active or bench)?"""
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


def _alakazam_attacker_relief(op_state):
    """vs Alakazam: does the gust RELIEVE their attacker instead of handing it over?

    Abra -> Kadabra -> Alakazam is the deck's ONLY attacking line, so bringing
    up any of those bodies with Boss's Orders ADVANCES their plan: the opponent
    evolves and attacks with the body we put in front of us (user, registro_002
    step 20 vs Alakazam, LOST -- an Abra was brought up while they held the
    Kadabra in hand). On top of that, Boss's is a FREE RETREAT we give them:
    their active goes to the bench without paying a cost.

    The only gust WITHOUT a KO that pays off in this matchup is the reverse:
    their attacker (Kadabra/Alakazam) is already ACTIVE and CHARGED, and we send
    it to the bench swapping it for a body that does not attack -- a bare Abra or
    any body outside the line (e.g. their Fezandipiti ex). The invested energy
    is left stranded on the bench and to come back they have to pay the retreat.

    Dunsparce never counts as relief: it is a FORBIDDEN gust target
    (`DUNSPARCE_IDS`, user's rule).
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
            continue        # swapping one attacker for another relieves nothing
        return True
    return False


def _op_attack_deficit(pkmn):
    """Energies `pkmn` (opponent) is MISSING in order to ATTACK: the cost of
    its cheapest attack minus the energies it already has (0 if it already can).

    This is the THIRD number that decides a gust without a KO, alongside the
    attached energies and the retreat cost (user's rule, registro_006 step 65 vs
    Dragapult). The other two are not enough: a bare Dragapult ex and a bare
    Drakloak TIE on both (0 energies, retreat 1) and are opposite targets --
    Dragapult ex attacks with 1 energy, Drakloak needs 2.

    It is measured by COST and never by damage: PRINTED damage lies in this
    environment -- Powerful Hand (Alakazam), Cruel Arrow (Fezandipiti ex) and
    both attacks of Gardevoir ex are listed as 0 in `attack_table` and all of
    them deal real damage.

    Deck-agnostic: it reads the costs from the card data (`card_table` -> attack
    ids -> `attack_table`), not from OUR deck's curated table. It returns None
    when it cannot be known (a card with no readable attacks): nothing is
    concluded on suspicion.

    `energies` via getattr: the gust target arrives from `get_card()` and the
    rest of the context constructor already treats it as optional
    (`len(card.energies) if hasattr(card, 'energies') else 0`). An exception
    here would be a forfeit of the whole game.
    """
    if pkmn is None:
        return None
    data = card_table.get(getattr(pkmn, 'id', 0))
    if data is None:
        return None
    costs = []
    for _aid in (getattr(data, 'attacks', None) or []):
        _atk = attack_table.get(_aid)
        if _atk is None:
            continue
        costs.append(len(getattr(_atk, 'energies', None) or []))
    if not costs:
        return None
    return max(0, min(costs) - len(getattr(pkmn, 'energies', None) or []))


def _op_body_is_harmless(pkmn):
    """`pkmn` (opponent) CANNOT attack on its next turn EVEN by attaching one
    energy: ALL of its attacks cost more than `energies + 1`.

    This is the THRESHOLD of `_op_attack_deficit` (deficit >= 2): with a
    deficit of 1 the opponent's attachment for the turn already pays for the
    attack. It returns False when the deficit cannot be known -- "harmless" is
    never concluded on suspicion -- and also with a zero-cost attack, which they
    can use this very turn.
    """
    _deficit = _op_attack_deficit(pkmn)
    return _deficit is not None and _deficit >= 2


def _op_active_is_harmless(op_state):
    """`_op_body_is_harmless` applied to the opposing ACTIVE."""
    return _op_body_is_harmless(op_state.active[0] if op_state.active else None)


def _op_juega_crustle(op_state):
    """Is there a Crustle line ON the opposing BOARD (active or bench)?"""
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
    '_op_attack_deficit',
    '_op_body_is_harmless',
    '_op_active_is_harmless',
    '_op_juega_crustle',
    '_op_hand_size',
    '_op_disruption_belief',
    '_alakazam_attacker_relief',
    '_op_attack_deficit',
    '_op_body_is_harmless',
    '_op_active_is_harmless',
    '_op_juega_crustle',
    '_op_hand_size',
    '_op_disruption_belief',
    '_alakazam_attacker_relief',
]
