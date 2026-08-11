"""The two prizes that were thirty short, and the Grass that was never played.

Scenario (`records/registro_009_pasos_102_hasta_102.json`, step 102, turn 9 vs
Archaludon, episode 91528800):

    US (2 prizes left)                     OPPONENT (4 prizes left)
    active  Hydrapple ex 80/330, 2 {G}     active  **Archaludon ex 300/300**
    bench   **Meganium**,                  bench   Meganium, Ogerpon ex x2,
            Teal Mask Ogerpon ex 6 {G},            Tapu Bulu, Meowth ex
            Tapu Bulu 2 {G},               stadium **Full Metal Lab** (theirs)
            Meowth ex, Teal Mask Ogerpon ex
    hand    Poke Pad, Ogerpon ex, Night Stretcher, Meowth ex,
            **one Basic Grass Energy**, Dipplin, Applin
            (the turn's attachment is still unspent)

Archaludon ex is worth TWO prizes and we have exactly two left: knocking it out
ends the game. The agent attacked at once and the engine logged the answer:

    {'attackId': 195, 'cardId': 150, 'playerIndex': 1, ...}
    {'cardId': 190, 'serial': 21, 'type': 16, 'value': **-270**}

Archaludon ex survived at 30 HP; the opponent healed it 80 on the next step.

THE ARITHMETIC, and it is the same sum as
`test_the_stadium_is_the_finisher_it_was_hiding` with different numbers. Syrup
Storm counts every Grass on OUR side, and Meganium's Wild Growth doubles each
basic Grass already in play, so the observation reports 10 units off 5 physical
cards (2 + 6 + 2): 30 + 30x10 = 330. Archaludon ex RESISTS Grass (-30) and is a
{M} body under Full Metal Lab, which takes 30 more AFTER weakness and
resistance (-30) -> **270** onto a 300 HP body.

Without the stadium the number is 300 and attacking on the spot is right, which
is exactly why the pre-fix agent attacked: `_active_already_kos` read 300 >= 300,
`_active_attack_wins_now` turned it into `_TIER_WIN_ATTACK` (99000) and that
tier does not outrank the menu, it EMPTIES it. The Grass in hand was never
offered to any branch.

THE GRASS IN HAND WAS THE GAME. Played before attacking -- by Teal Dance, which
is free and draws a card, or by the turn's own attachment, which is still
unspent -- it lands as 2 more units (Wild Growth doubles it too): 30 + 30x12 =
390, minus 30 and 30 = **330 >= 300**. Even undoubled it would reach exactly
300. The plays are ordered, not exclusive: the Grass first, the attack after.

THE FIX is already in the tree (`d46ac69`, `_our_effective_damage`'s
`full_metal_lab` default of None = ask the board). This file is the second
board it is pinned on, and it pins the half the first one could not: there the
extra energy had to be fetched out of the discard, here it is in hand and the
question is only whether the turn spends it BEFORE the attack. Checked out at
`d46ac69~1` this same fixture returns the record's `[11]` -- the attack -- and
on HEAD it returns the Grass.
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

from ptcg.calc.damage import _our_effective_damage, _prizes_of_id

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "archaludon_t9_the_last_two_prizes_were_thirty_short_step102.json")

SEAT = 1                       # our seat in the record
ARCHALUDON_EX = 190
HYDRAPPLE_EX = 150
SYRUP_STORM = 195


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _me(obs):
    return obs["current"]["players"][SEAT]


def _option_index(obs, predicate):
    for i, opt in enumerate(obs["select"]["option"]):
        if predicate(i, opt):
            return i
    return None


def _attack_index(obs):
    return _option_index(obs, lambda i, o: o.get("attackId") == SYRUP_STORM)


def _grass_hand_index(obs):
    """Position of the Basic Grass Energy in our hand."""
    for i, card in enumerate(_me(obs)["hand"]):
        if card["id"] == m.Basic_Grass_Energy:
            return i
    return None


def _routes_that_play_the_grass(obs):
    """Every option that puts the Grass in hand onto the board this turn.

    Two of them: the turn's own attachment (type 8, `index` = the card in hand)
    and Teal Dance (type 10 on a Teal Mask Ogerpon ex), which attaches the same
    card for free and draws. Syrup Storm counts the Grass wherever it lands, so
    the body it goes on does not matter here.
    """
    hand_index = _grass_hand_index(obs)
    bench = _me(obs)["bench"]
    routes = []
    for i, opt in enumerate(obs["select"]["option"]):
        if opt.get("type") == 8 and opt.get("index") == hand_index:
            routes.append(i)
        elif (opt.get("type") == 10 and opt.get("area") == 5
                and bench[opt["index"]]["id"] == m.Teal_Mask_Ogerpon_ex):
            routes.append(i)
    return routes


# ---------------------------------------------------------------------------
# 1. The board is the one the record left at 30 HP
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_archaludon_that_survived_at_thirty():
    obs = _obs()
    cur = obs["current"]
    op = cur["players"][1 - SEAT]

    assert cur["stadium"][0]["id"] == m.Full_Metal_Lab
    assert cur["stadium"][0]["playerIndex"] == 1 - SEAT, "their stadium"
    assert op["active"][0]["id"] == ARCHALUDON_EX
    assert op["active"][0]["hp"] == 300 == op["active"][0]["maxHp"]

    me = _me(obs)
    assert me["active"][0]["id"] == HYDRAPPLE_EX
    assert any(p["id"] == m.Meganium for p in me["bench"]), "Wild Growth is on"
    assert _grass_hand_index(obs) is not None, "one Grass in hand"
    assert not cur["energyAttached"], "the turn's attachment is still unspent"


def test_the_knockout_is_the_game_two_prizes_against_our_last_two():
    obs = _obs()
    assert len(_me(obs)["prize"]) == 2
    assert _prizes_of_id(ARCHALUDON_EX) == 2, "the knockout ends the game"


def test_the_ten_units_are_five_cards_and_meganium_doubles_them():
    """The observation reports the doubling for the bodies already in play."""
    me = _me(_obs())
    bodies = me["active"] + me["bench"]
    units = sum(len(p["energies"]) for p in bodies)
    cards = sum(len(p["energyCards"]) for p in bodies)
    assert (units, cards) == (10, 5)
    assert 30 + 30 * units == 330


# ---------------------------------------------------------------------------
# 2. The numbers: 270 with the Grass in hand, 330 with it on the board
# ---------------------------------------------------------------------------

class _Body:
    def __init__(self, card_id, hp, max_hp=None):
        self.id = card_id
        self.hp = hp
        self.maxHp = max_hp or hp
        self.energies = []


def test_the_attack_lands_at_270_and_leaves_the_body_at_thirty():
    """-30 resistance, -30 stadium: the 270 the engine logged."""
    m.AGENT_STATE.full_metal_lab_in_play = True
    damage = _our_effective_damage(_Body(HYDRAPPLE_EX, 80, 330),
                                   _Body(ARCHALUDON_EX, 300), 330)
    assert damage == 270
    assert 300 - damage == 30, "the 30 HP the record left it at"


def test_without_the_stadium_the_same_attack_is_exactly_lethal():
    """300 >= 300 is what the pre-fix agent read, and why it attacked."""
    m.AGENT_STATE.full_metal_lab_in_play = False
    assert _our_effective_damage(_Body(HYDRAPPLE_EX, 80, 330),
                                 _Body(ARCHALUDON_EX, 300), 330) == 300


def test_the_grass_in_hand_carries_the_attack_over_the_three_hundred():
    """Wild Growth doubles it too: +2 units -> 390 printed, 330 delivered."""
    m.AGENT_STATE.full_metal_lab_in_play = True
    assert _our_effective_damage(_Body(HYDRAPPLE_EX, 80, 330),
                                 _Body(ARCHALUDON_EX, 300), 30 + 30 * 12) == 330
    # and even undoubled it would reach the body exactly
    assert _our_effective_damage(_Body(HYDRAPPLE_EX, 80, 330),
                                 _Body(ARCHALUDON_EX, 300), 30 + 30 * 11) == 300


# ---------------------------------------------------------------------------
# 3. The decision: the Grass goes down first, the attack takes the game
# ---------------------------------------------------------------------------

def test_step102_does_not_attack_thirty_short():
    obs = _obs()
    attack = _attack_index(obs)
    assert attack is not None, "the attack IS on the menu; the point is not taking it"
    assert m.agent(obs) != [attack], (
        "Syrup Storm lands at 270 on a 300 HP body: attacking now spends the "
        "turn that wins the game")


def test_step102_puts_the_grass_on_the_board_first():
    obs = _obs()
    routes = _routes_that_play_the_grass(obs)
    assert routes, "the fixture offers both the attachment and Teal Dance"
    assert m.agent(obs)[0] in routes, (
        "one more Grass anywhere on our side is 330 >= 300")


def test_once_the_grass_is_down_the_attack_takes_the_last_two_prizes():
    """The next step of the same turn: the Grass has landed, so attack."""
    obs = _obs()
    me = _me(obs)
    grass = me["hand"].pop(_grass_hand_index(obs))
    me["handCount"] = len(me["hand"])
    me["bench"][-1]["energies"] = [1, 1]            # Wild Growth doubles it
    me["bench"][-1]["energyCards"] = [grass]
    obs["select"]["option"] = [{"index": 0, "type": 7},
                               {"attackId": SYRUP_STORM, "type": 13},
                               {"type": 14}]
    assert m.agent(obs) == [1], "330 >= 300 and Archaludon ex is the last two prizes"


def test_the_route_does_not_depend_on_teal_dance():
    """With the abilities off the menu the turn's own attachment takes it: the
    reading is "one more Grass is lethal", not "use Ogerpon"."""
    obs = _obs()
    obs["select"]["option"] = [o for o in obs["select"]["option"]
                               if o.get("type") != 10]
    routes = _routes_that_play_the_grass(obs)
    assert routes and _attack_index(obs) is not None
    assert m.agent(obs)[0] in routes


def test_the_stadium_is_what_moves_the_decision():
    """The counterfactual through the whole agent: same board, any other
    stadium, and 330-30 = 300 >= 300 makes attacking now the right play."""
    obs = _obs()
    obs["current"]["stadium"] = [{"id": m.Forest_of_Vitality,
                                  "playerIndex": SEAT, "serial": 999}]
    obs["current"]["stadiumPlayed"] = True
    assert m.agent(obs) == [_attack_index(obs)]
