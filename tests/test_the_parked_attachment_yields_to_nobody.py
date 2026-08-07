"""A deference only stands while its beneficiary is alive.

`_attach_yields_to_teal_dance` postpones the manual attachment when a Teal Dance
is pending: the ability attaches the same Grass AND DRAWS, so it goes first. The
attachment is capped to 7000 (below the ability's degraded 7500) and, so that the
score can decide between them, it is also DROPPED OUT of `_TIER_ENERGY` into
tier 0, next to the ability.

The set it reads is built from the MENU, not from the score:

    if _tds_o.type == OptionType.ABILITY and _tds_card.id == Teal_Mask_Ogerpon_ex:
        _teal_dance_slots.add((_tds_o.area, _tds_o.index))

So an ability that is OFFERED but VETOED still parks the attachment. The cap is
harmless there -- the ATTACH branch says as much: "if the ability were vetoed by
another route, the attachment is still playable and the turn does not hang" --
but the TIER is not. Down in tier 0 the attachment loses by ORDER to every
tier-0 play, and the turn's free, non-accumulating attachment goes with it.

Where it bites hardest is against a refill that empties the hand: the energy is
not merely left unattached, it is SHUFFLED INTO THE DECK. Board (a Teal Mask
Ogerpon ex with 3 energies, from the same record as
[[test_the_hand_reset_goes_after_what_the_hand_pays]]):

    Teal Dance  -1 (already at 3 energies: do not overcharge)
    attachment  7000, parked in tier 0 with nothing to yield to
    Lillie's    8000  ->  wins, shuffles the Grass away

Census over 4000 self-play games (`log/hand_reset_gate/residual_census.py`): the
board happens in 102 of 139.663 MAIN menus (0.073%), and in 75% of them the
attachment is in the real development band (5000/7000) rather than the
near-worthless one (10-20).

Fix (`finalizar`): park the attachment only while a hand-paying ability is
actually LIVE (`_attach_park_beneficiary_alive`). With one alive nothing changes;
with none, the board behaves like a board with no Teal Dance at all -- which is
what it is. Same shape as `_stamp_worth_playing` ("it yielded the way to a card
that was no longer going to be played") and as the REVOKE ORDERING VETOES block.

Paired flip census vs HEAD (400 games x 8 matchups, 332.375 decisions): this half
adds ~19 flips (+0.0054 pp) on top of the hand-reset net, and 26 of the 146
sampled flips carry its shape, `PLAY -> ATTACH`.

Coverage: the sweep over the Ogerpon's energy count, which crosses the veto
threshold and shows BOTH sides of the rule with one board -- while the ability
lives it keeps the turn (the parking works), and the moment it is vetoed the
attachment recovers its tier instead of the refill taking the menu.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from golden_corpus import reset_agent

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_step29_the_hand_reset_goes_last.json")

LILLIE = m.Lillie_Determination
OGERPON = m.Teal_Mask_Ogerpon_ex
GRASS = m.Basic_Grass_Energy
BENCH_OGERPON = 3          # its slot on our bench in the record


@pytest.fixture(autouse=True)
def reset_main_state():
    reset_agent(m)
    yield
    reset_agent(m)


def _decide(energies_on_the_benched_ogerpon):
    """Replays the record's menu with the benched Ogerpon at N energies.

    Above the overcharge threshold its Teal Dance is vetoed, which is the whole
    point: the attachment is left parked with nobody to yield to.
    """
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    previous = copy.deepcopy(data["previous_observation"])
    dec = copy.deepcopy(data["observation"])
    mine = dec["current"]["players"][dec["current"]["yourIndex"]]
    ogerpon = mine["bench"][BENCH_OGERPON]
    assert ogerpon["id"] == OGERPON
    ogerpon["energies"] = [7] * energies_on_the_benched_ogerpon
    ogerpon["energyCards"] = [{"id": GRASS, "playerIndex": 1, "serial": 900 + k}
                              for k in range(energies_on_the_benched_ogerpon)]
    m.agent(previous)
    m.AGENT_STATE._ld_supp_comprometido = LILLIE
    choice = m.agent(dec)
    return dec["select"]["option"][choice[0]], dec


def _played_card_id(option, dec):
    if option["type"] != int(m.OptionType.PLAY):
        return None
    mine = dec["current"]["players"][dec["current"]["yourIndex"]]
    return mine["hand"][option["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The board: the refill and the single Grass it would shuffle away
# ---------------------------------------------------------------------------

def test_the_menu_offers_the_teal_dance_whatever_its_score():
    """`_teal_dance_slots` reads the MENU, so the parking happens at 0 energies
    and at 3 alike. Without that the test measures nothing."""
    for n in (0, 3):
        _, dec = _decide(n)
        ability = [o for o in dec["select"]["option"]
                   if o["type"] == int(m.OptionType.ABILITY)]
        attach = [o for o in dec["select"]["option"]
                  if o["type"] == int(m.OptionType.ATTACH)]
        assert len(ability) == 1 and ability[0]["index"] == BENCH_OGERPON
        assert attach, "the manual attachment has to be on the menu too"


# ---------------------------------------------------------------------------
# 2. While the ability lives, the parking is right and stays untouched
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("energies", [0, 1, 2])
def test_a_live_teal_dance_still_keeps_the_turn(energies):
    """The fix must not undo the deference it guards: below the overcharge
    threshold the ability is alive and goes first, as it always did -- it
    attaches the same Grass AND draws."""
    option, _ = _decide(energies)
    assert option["type"] == int(m.OptionType.ABILITY), (
        f"with {energies} energies the Teal Dance is a real play and keeps the "
        f"turn; chose {option}")


# ---------------------------------------------------------------------------
# 3. Vetoed, the attachment recovers its tier instead of losing the energy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("energies", [3, 4])
def test_a_vetoed_teal_dance_parks_nothing(energies):
    """Above the threshold the ability is at -1: there is no "afterwards" to wait
    for, and the refill must not take the menu with the Grass still in hand."""
    option, dec = _decide(energies)
    assert option["type"] == int(m.OptionType.ATTACH), (
        f"with {energies} energies the Teal Dance is vetoed; the turn's "
        f"attachment goes before the refill shuffles the Grass away. "
        f"Chose {option} ({_played_card_id(option, dec)})")


def test_the_refill_is_what_it_would_have_lost_to():
    """Naming the loser matters: the flip is only interesting because the play
    that was winning SHUFFLES THE HAND INTO THE DECK, so the Grass is not merely
    left unattached -- it is gone."""
    _, dec = _decide(3)
    mine = dec["current"]["players"][dec["current"]["yourIndex"]]
    hand = [c["id"] for c in mine["hand"]]
    assert hand.count(LILLIE) == 1 and hand.count(GRASS) == 1
    assert LILLIE in m.HAND_RESET_PLAY_IDS
    assert dec["current"]["supporterPlayed"] is False
