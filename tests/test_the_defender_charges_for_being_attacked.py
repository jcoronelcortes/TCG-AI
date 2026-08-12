r"""The price of attacking that lives on the DEFENDER, and it is four cards.

Scenario (episode 92355371, turn 3-4 vs *Festival Lead*, LOST):

    their active   Dipplin 80 HP + **Deluxe Bomb**
    our attacker   Teal Mask Ogerpon ex 210/210

*Deluxe Bomb (1167)*: "If the Pokemon this card is attached to is in the Active
Spot and is damaged by an attack from your opponent's Pokemon (EVEN IF THIS
POKEMON IS KNOCKED OUT), put 12 damage counters on the Attacking Pokemon."

That is **120 damage to our own body**, and step 84 of the record shows it being
charged: `serial 5, value -120, putDamageCounter true`. Our Ogerpon ex went to
90/210 and handed over two prizes on the following turn. We survived it by
accident: it was the only body on the table that takes 120 and lives.

    grep -rn "1167\|Deluxe" --include="*.py" .   ->   nothing, until today

WHAT MAKES IT A CLASS RATHER THAN A CARD. `utils/card_text_census.py` was
written to find texts the tree had never heard of, and the first thing it found
was that the same sentence is printed by three more:

    Spiky Energy   (14)     20 to our attacker      17 measurable lists
    Handheld Fan   (1161)   MOVES AN ENERGY off it   8 measurable lists
    Punk Helmet    (1176)   40, {D} holders only     2 measurable lists
    Deluxe Bomb    (1167)  120 to our attacker       0 measurable lists

The card that found the hole is the one we cannot measure against; the class is
testable because of the other three.

WHAT IS MODELLED HERE AND WHAT IS NOT. This is recoil -- our body, our turn, the
same instant as Wood Hammer's self-damage -- so it lands in the same brake:
`_active_self_ko_now`, the sentence that stops a "winning" finisher from
claiming absolute priority when it kills the attacker. It does NOT yet tell the
defensive projection that our active will be standing at less HP when their
reply comes, which is how the real game was lost. That half moves
`_opponent_reply`, machinery this project has measured negative three separate
times when it was made to fire more often, and it gets measured before it is
written.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from main_support import make_card, make_pokemon  # noqa: E402

from ptcg.calc.damage import _defender_punish_damage  # noqa: E402
from ptcg.cards.ids import (ATTACKER_PUNISH_DAMAGE,  # noqa: E402
                            ATTACKER_PUNISH_MOVES_ENERGY,
                            ATTACKER_PUNISH_NEEDS_DARK, Deluxe_Bomb,
                            Dipplin, Handheld_Fan, Punk_Helmet, Spiky_Energy)
from ptcg.cards.tables import card_table  # noqa: E402


# --------------------------------------------------------------------------
# the table says what the cards say


def test_every_id_in_the_table_prints_the_sentence():
    """The table against the printed text, in the direction that rots.

    A table of ids copied from a card is a copy, and copies drift. This is the
    same check the immunity census makes, done here for the three ids that
    carry a number.
    """
    for card_id, damage in ATTACKER_PUNISH_DAMAGE.items():
        data = card_table.get(card_id)
        assert data is not None, f"id {card_id} no existe en el simulador"
        text = " ".join((s.text or "") for s in (data.skills or []))
        assert "Attacking" in text, f"{data.name} no castiga al atacante"
        counters = damage // 10
        assert f"{counters} damage counters" in text, (
            f"{data.name}: la tabla dice {damage} y la carta dice otra cosa")


def test_the_fan_is_not_in_the_damage_table():
    """It moves an energy; it does no damage. Inventing HP for it would be a lie."""
    assert Handheld_Fan in ATTACKER_PUNISH_MOVES_ENERGY
    assert Handheld_Fan not in ATTACKER_PUNISH_DAMAGE


# --------------------------------------------------------------------------
# the reader


def _their_active(*, tools=(), energy_cards=(), card_id=Dipplin):
    return make_pokemon(card_id, hp=80, max_hp=80,
                        tools=[make_card(t) for t in tools],
                        energy_cards=[make_card(e) for e in energy_cards])


def test_the_bomb_charges_a_hundred_and_twenty():
    """The board of episode 92355371, to the number."""
    assert _defender_punish_damage(_their_active(tools=[Deluxe_Bomb])) == 120


def test_a_special_energy_charges_too():
    """Spiky Energy is an ENERGY, not a tool: reading only `tools` misses 17 lists."""
    assert _defender_punish_damage(_their_active(energy_cards=[Spiky_Energy])) == 20


def test_two_of_them_add_up():
    """Nothing in the text makes them exclusive, and summing is the safe side."""
    assert _defender_punish_damage(
        _their_active(tools=[Deluxe_Bomb], energy_cards=[Spiky_Energy])) == 140


def test_the_helmet_asks_for_a_dark_holder():
    """`If the {D} Pokemon this card is attached to`: a Grass Dipplin pays nothing."""
    assert Punk_Helmet in ATTACKER_PUNISH_NEEDS_DARK
    assert _defender_punish_damage(_their_active(tools=[Punk_Helmet])) == 0


def test_a_bare_body_charges_nothing():
    assert _defender_punish_damage(_their_active()) == 0
    assert _defender_punish_damage(None) == 0


# --------------------------------------------------------------------------
# the consumer


def test_the_recoil_kills_the_bodies_this_deck_is_made_of():
    """The reason it is a veto on WHO attacks and not a footnote.

    Deluxe Bomb's 120 is more than the printed HP of our Dipplin (80), our
    Applin (40) and our Chikorita (70). Under Festival Grounds -- where a
    one-prize attacker is supposed to swing twice -- the first wave kills the
    attacker and the second never happens.
    """
    punish = ATTACKER_PUNISH_DAMAGE[Deluxe_Bomb]
    for card_id, name in ((92, "Applin"), (93, "Dipplin"), (917, "Chikorita")):
        data = card_table.get(card_id)
        assert punish >= (data.hp or 0), (
            f"{name} ({data.hp} PV) sobrevive a {punish}: revisar la premisa")
