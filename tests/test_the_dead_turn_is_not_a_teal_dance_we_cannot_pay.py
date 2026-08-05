"""A Teal Dance with no Grass in hand is not a route: the turn is stalled.

Scenario (`records/registro_004_pasos_047_hasta_050.json`, step 48, episode
89624233 vs a pure Teal Mask Ogerpon ex deck -- LOST):

    US                                     THEM (Teal Mask Ogerpon ex)
    active  Teal Mask Ogerpon ex  60/240    active  Teal Mask Ogerpon ex 240 (4 energies)
            (1 energy of the 3 it needs)    bench   Teal Mask Ogerpon ex 240 (2 energies)
    bench   Chikorita 100                   stadium Lively Stadium (+30 HP to Basics)
            Teal Mask Ogerpon ex (2 energies)
            Teal Mask Ogerpon ex (1 energy)
    hand    Meganium, Meganium, **Meowth ex**, Hydrapple ex, Hydrapple ex,
            **Xerosic's Machinations**, Tapu Bulu
    turn 4, the Supporter is free, NO Grass energy anywhere in hand

The active cannot attack, cannot be charged and their Ogerpon hits for 180: it
dies on the reply. The agent spent the turn's Supporter on Xerosic -- five cards
off their hand -- and ended the turn with the same board that could not attack.
The play the board was asking for is the one the user described: bench the Meowth
ex, let Last-Ditch Catch bring the Lillie's Determination out of the deck and
play it, which is the only card that can turn up the energy (or the Night
Stretcher) that charges the benched Ogerpon we would promote.

WHY THE AGENT DID NOT SEE IT. Not in the Supporter scale -- that one was right
all along: on this board Lillie's scores 5000 and Xerosic 3380, so the moment the
Lillie's is in hand it wins the slot. The mistake is one step earlier, in the
sentence the turn reads about itself. `_active_cant_attack_this_turn` came out
FALSE, so the dead-turn engine that benches the Meowth (21800) never fired, the
Meowth fell through to the generic ladder -- which vetoes it with a hand of 7 --
and Xerosic was left as the only Supporter on the menu.

And it came out False for a route that did not exist. The stall detector prices
the Teal Dance chain: with N Ogerpon carrying energy it assumes N dances, each
one drawing a card, and asks how likely it is that none of those draws is an
energy. Here N was 3 and the deck held 9 Grass in 41 cards, so it read a 52%
chance of charging and declared the turn playable. But Teal Dance attaches a
Grass FROM HAND and only then draws, and the hand held none: there is no first
dance, no card is drawn, and the three draws it priced never happen. The
simulator says so outright -- the menu of that step offers PLAY, RETREAT and END
and no ABILITY option at all.

Fix: the chain needs a SEED, and the seed is the same census the plan uses
(`_reachable_grass_for`): the Grass in hand plus the one a Night Stretcher pulls
out of the discard, which does land in hand and can pay for a dance. The deck is
deliberately not a source -- the deck is what the chain below is already pricing.

MEASURED. Head-to-head against the version without the fix, 1000 games with
alternating seats: 49.3% [95% CI 46.2-52.4], prizes +0.03 -- neutral, as expected
from how rarely the conjunction happens with the generic bot (0 decision flips in
28.506 self-play decisions across the mirror, the Kangaskhan wall and the
Ogerpon list). It is kept under the ILLEGAL-VALUE exception to the
revert-what-measures-neutral policy, the same one that kept the Nighttime Mine
tax: the agent was not making a worse estimate, it was pricing a play the engine
does not offer.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "ogerpon_t4_the_dead_turn_calls_the_meowth_step48.json")

MEOWTH = m.Meowth_ex
XEROSIC = m.Xerosic_Machinations
GRASS = m.Basic_Grass_Energy
NIGHT_STRETCHER = m.Night_Stretcher
OGERPON = m.Teal_Mask_Ogerpon_ex


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    yield
    m._init_cards_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _idx_play(obs, card_id):
    """Index of the 'PLAY <card_id>' option in the main menu, or -1."""
    hand = _mine(obs)["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(m.OptionType.PLAY) and hand[o["index"]]["id"] == card_id:
            return i
    return -1


def _add_to_hand(obs, card_id, serial=900):
    """One more card in hand. The MENU is left as the step recorded it: what the
    boundary tests read is the reading of the turn, not a synthetic option."""
    cur = obs["current"]
    mine = _mine(obs)
    mine["hand"].append({"id": card_id, "playerIndex": cur["yourIndex"],
                         "serial": serial})
    mine["handCount"] = len(mine["hand"])
    return obs


def _locals_of_agent(obs, keys):
    """The values `agent()` ends the call with, for the locals in `keys`.

    `_active_cant_attack_this_turn` is a local of `agent()`, not a predicate that
    can be called: the sentence the turn reads about itself is built inline. The
    trace is the same technique the project uses to find out why an option won.
    """
    out = {}

    def _trace(frame, event, arg):
        if event == "return" and frame.f_code.co_name == "agent":
            for k in keys:
                out[k] = frame.f_locals.get(k)
        return _trace

    sys.settrace(_trace)
    try:
        m.agent(obs)
    finally:
        sys.settrace(None)
    return out


def _turn_is_stalled(obs):
    return _locals_of_agent(obs, ("_active_cant_attack_this_turn",))[
        "_active_cant_attack_this_turn"]


def _has_seed(obs):
    """Is there a card that can pay for the FIRST Teal Dance?

    What the fix adds. It is read apart from the stall verdict on purpose: past
    the seed the chain still has its own probability to answer, and on this board
    it sits on the knife's edge (0.475 against a threshold of 0.5), so a Grass
    moving from the deck to the hand moves BOTH terms.
    """
    return _locals_of_agent(obs, ("_td_seed",))["_td_seed"]


# ---------------------------------------------------------------------------
# 1. The board: a turn that cannot attack, and an engine that says otherwise
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_stalled_turn_of_the_record():
    o = _obs()
    cur = o["current"]
    mine = _mine(o)

    assert cur["turn"] == 4 and cur["supporterPlayed"] is False
    assert [c["id"] for c in mine["hand"]].count(GRASS) == 0, (
        "el escenario es una mano SIN energia: sin ella no hay Teal Dance")
    assert cur["energyAttached"] is False, "el adjunte del turno sigue libre"

    active = mine["active"][0]
    assert active["id"] == OGERPON and active["hp"] == 60
    assert len(active["energies"]) == 1, (
        "1 de las 3 energias que pide su ataque: el activo no puede atacar")
    assert [len(p["energies"]) for p in mine["bench"]] == [0, 2, 1, 0], (
        "ningun cuerpo de la banca llega tampoco a las 3")


def test_the_engine_does_not_even_offer_the_teal_dance():
    """The binary contradiction: the menu of the step has no ABILITY option.

    It is the whole justification of the fix -- the chain the detector priced is
    not a worse estimate, it is a play the simulator does not offer.
    """
    tipos = {opt.get("type") for opt in _obs()["select"]["option"]}
    assert int(m.OptionType.ABILITY) not in tipos, (
        "sin Grass en mano el motor no ofrece Teal Dance")
    assert int(m.OptionType.ATTACH) not in tipos, (
        "sin Grass en mano tampoco hay adjunte manual")


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_the_dead_turn_benches_the_meowth_instead_of_capping_the_hand():
    """The regression of the record: the Supporter went to Xerosic (3380) and
    the board that could not attack stayed as it was."""
    o = _obs()
    assert _idx_play(o, MEOWTH) >= 0 and _idx_play(o, XEROSIC) >= 0, (
        "el paso ofrecia ambas jugadas: el menu mide la prioridad")
    assert m.agent(o) == [_idx_play(o, MEOWTH)], (
        "en un turno que no puede atacar, el Meowth ex busca la Lillie's "
        "Determination; la disrupcion no arregla un tablero mudo")


def test_the_fetch_points_at_the_lillie_and_the_lillie_takes_the_slot():
    """The other half of the line: benching the Meowth is only worth it because
    the Supporter it brings is the one that gets played.

    `_meowth_fetch_loses_the_turn` predicts both sides on the PLAY scale before
    the body goes down. If the prediction said Xerosic, the same veto that
    cancelled the Meowth in registro_004 step 36 would cancel it here too.
    """
    trazas = _locals_of_agent(_obs(), (
        "_meowth_fetch_id", "_meowth_supp_turn_id",
        "_meowth_supp_turn_val", "_meowth_fetch_loses_the_turn"))
    assert trazas["_meowth_fetch_id"] == m.Lillie_Determination
    assert trazas["_meowth_supp_turn_id"] == m.Lillie_Determination
    assert trazas["_meowth_fetch_loses_the_turn"] is False


# ---------------------------------------------------------------------------
# 3. The boundary: with a seed the chain is real again
# ---------------------------------------------------------------------------

def test_without_a_seed_the_turn_reads_as_stalled():
    """The reading the whole turn hangs on. On the record's board it came out
    False -- 3 Ogerpon with energy and 9 Grass left in 41 cards priced the chain
    at a 52% chance of charging -- with zero dances actually available."""
    o = _obs()
    assert _has_seed(o) is False
    assert _turn_is_stalled(o) is True


def test_one_grass_in_hand_is_a_seed():
    """The fix only removes the chain when nothing can pay for the FIRST dance.
    With a Grass in hand the dance exists and the chain is priced as before."""
    assert _has_seed(_add_to_hand(_obs(), GRASS, serial=901)) is True


def test_a_night_stretcher_over_a_discarded_grass_is_a_seed_too():
    """`_reachable_grass_for` counts it because the card really lands IN HAND:
    the Stretcher takes the energy out of the discard and the dance can pay with
    it that same turn."""
    o = _obs()
    _mine(o)["discard"].append(
        {"id": GRASS, "playerIndex": o["current"]["yourIndex"], "serial": 902})
    assert _has_seed(_add_to_hand(o, NIGHT_STRETCHER, serial=903)) is True


def test_a_night_stretcher_with_no_energy_in_the_discard_is_not_a_seed():
    """The symmetric half: a Stretcher with nothing to fetch does not start a
    dance, so the turn is still the dead one and the Meowth still goes down."""
    o = _add_to_hand(_obs(), NIGHT_STRETCHER, serial=904)
    assert all(c["id"] != GRASS for c in _mine(o)["discard"]), (
        "el escenario no mide nada si ya hay energia en el descarte")
    assert _has_seed(o) is False
    assert _turn_is_stalled(o) is True
    assert m.agent(o) == [_idx_play(o, MEOWTH)]
