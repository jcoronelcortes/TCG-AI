"""Reading a single card: fetching it, what it is worth, what it costs us.

The bottom of the reading stack. Everything above -- damage, energy, the whole
`decision/` layer -- asks its questions about one card through here, which is
why these few functions are among the most-called in the agent.

WHAT LIVES HERE, in the order the file is written:

  * `get_card` -- the ONE way to turn an (area, index) menu reference into the
    actual card. Every scorer starts with it.
  * the PRIZE functions -- how many prizes a body hands over when it falls.
    There are three of them and picking the wrong one is a real bug, so the
    split is spelled out below.
  * `pokemon_score` -- a generic "how valuable is this body", used for ranking
    when no measured rule has an opinion.
  * `is_one_prize_wall` -- the shield we want in front early, recognised by its
    PROPERTIES rather than by name.

THE THREE PRIZE FUNCTIONS, and which one to reach for:

  * `prize_count` -- the printed truth for OUR bodies. What the opponent
    collects when this one of ours is knocked out.
  * `prize_count_op` -- the same question for THEIR bodies, with their prize
    DENIAL applied (Pecharunt ex, Mega Gengar ex). Using `prize_count` on an
    opposing body overstates what a knockout pays us.
  * `ko_front_price_rung` -- not a count but a COMPARISON key, for ranking
    which of our bodies should take the front seat. It clamps at their
    remaining pile, because past that point a dearer corpse costs no more than
    a cheap one.

Purity, and why it is not quite absolute: `prize_count_op` reads the prize
denial flags off `AGENT_STATE`. The flags are refreshed once per turn and read
here as data, so `utils/purity.py` still passes the module -- but it is the one
function in this file whose answer depends on the turn.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from cg.api import AreaType, Card, CardType, EnergyType, Observation, Pokemon
from ptcg.cards.ids import Alakazam_ex, Dusknoir, FIRST_TURN_WALL_MIN_HP, Gardevoir_ex, Meganium, Munkidori_ex, Slowking, Typhlosion
from ptcg.cards.scoring import MAIN_ATTACKERS
from ptcg.cards.tables import card_table
from ptcg.state.agent_state import AGENT_STATE


def get_card(obs: Observation, area: AreaType, index: int, player_index: int) -> Pokemon | Card | None:
    """Resolve an (area, index) reference into the card the option points at.

    A menu option names its card by WHERE IT SITS, not by id, so this is the
    lookup every scorer opens with. Returns a `Pokemon` for the in-play areas
    and a `Card` for the rest; None when the reference does not resolve.

    Two areas do not come from the player's own zones: DECK and LOOKING are
    read off `obs.select`, since they only exist while a search or a reveal is
    open.

    Returning None rather than raising is deliberate -- a menu can offer an
    index into a zone the observation renders differently, and a scorer that
    cannot see the card should decline to score it, not crash a live game.
    """
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
    """How many prizes knocking this body out hands over. Use it on OUR side.

    The base is the card's class -- 3 for a Mega ex, 2 for an ex, 1 otherwise
    -- and then two ATTACHMENTS reduce it, which is why this reads the body in
    play and not just the id: the same card is worth different prizes depending
    on what is stuck to it.

      * Legacy Energy (12) -- one prize less, for anything.
      * Lillie's Pearl (1172) -- one prize less, but only on a Lillie's body,
        which is what the name check enforces.

    For an OPPOSING body use `prize_count_op` instead: their prize denial
    applies there and is not modelled here.
    """
    data = card_table[pokemon.id]
    count = 3 if data.megaEx else 2 if data.ex else 1
    for card in pokemon.energyCards:
        if card.id == 12:
            count -= 1
    for card in pokemon.tools:
        if card.id == 1172 and "Lillie" in data.name:
            count -= 1
    return max(0, count)


def ko_front_price_rung(pokemon: Pokemon, op_prize: int) -> int:
    """What this body COSTS us as the front seat, as a comparable rung.

    The price of a body separates the candidates only while it leaves the
    opponent SHORT of their remaining pile -- the sentence
    `prize_count < op_prize` that prize denial and the match-point veto are
    already written with. Once a price REACHES their pile it stops being
    information (registro_011: at their match point the cheapest corpse closes
    their count exactly like the dearest), so every such body is CLAMPED onto
    the same rung and whatever ranks inside a rung decides between them.

    Used by "THE FRONT SPOT AMONG THE ONES THAT KNOCK OUT" (user, registro_012
    step 172 vs Alakazam) to group the knockers before ordering them by HP. It
    never reorders ACROSS rungs: which price we would rather pay is decided by
    the measured rules that already do it (prize denial, the basic-wall family,
    the Crustle/Kangaskhan split), and a generic tie-break does not get to
    overrule them -- measured, it moved two corpus decisions from a Teal Mask
    Ogerpon ex to the Tapu Bulu those matchups keep on the bench on purpose.
    """
    _price = prize_count(pokemon)
    if op_prize is not None and _price >= op_prize:
        _price = op_prize
    return _price


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
    """A generic "how valuable is this body", for ranking with no better rule.

    The FALLBACK valuation. Where a measured rule has an opinion about a body
    it wins; this is what orders the rest, mostly when choosing a gust target
    among opposing Pokemon that no named rule distinguishes.

    What it adds up, in descending weight: the prizes it hands over (1000
    each, so the class of the body dominates everything else), the investment
    sunk into it (150 per energy, 100 per tool), its evolution stage, a per-card
    correction, and finally its HP as the tie-break.

    The per-card corrections are the ENGINE bodies -- Meganium, Gardevoir ex,
    Typhlosion, Slowking, Dusknoir, Alakazam ex -- worth more than their class
    suggests because they keep the opposing deck running. The penalised ids
    (Kyurem, Lilligant, Nymble, Lugia EX) are the reverse: bodies whose printed
    stats overstate what they actually do. Munkidori gets a bonus only once
    charged, since it is the body that carries Adrena-Brain's damage.

    The numbers are ordinal, not units of anything -- only their order matters.
    """
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

def is_one_prize_wall(card_id: int) -> bool:
    """Is this card the body we want in front while we build the bench?

    Three properties, read off the card and not off a list of ids, so any deck
    gets the rule for free:

      * a BASIC -- it can be put down and promoted the same turn, with no line
        to assemble first;
      * worth ONE prize -- when it falls the opponent is no closer to winning
        than one prize, which is the whole point of hiding an ex behind it;
      * hard to remove (`FIRST_TURN_WALL_MIN_HP`) and an ATTACKER. The HP is
        what buys the turns; being a real attacker is what stops the body from
        being a mute wall that hands the opponent a free tempo prize. A deck
        whose 1-prize basics are all fragile or mute simply never sees this
        rule fire.
    """
    data = card_table.get(card_id)
    if data is None or data.cardType != CardType.POKEMON:
        return False
    if getattr(data, 'ex', False) or getattr(data, 'megaEx', False):
        return False
    if getattr(data, 'stage1', False) or getattr(data, 'stage2', False):
        return False
    if (getattr(data, 'hp', 0) or 0) < FIRST_TURN_WALL_MIN_HP:
        return False
    return card_id in MAIN_ATTACKERS


__all__ = [
    'get_card',
    'ko_front_price_rung',
    'is_one_prize_wall',
    'prize_count',
    'prize_count_op',
    'pokemon_score',
]
