"""An energy that reaches no cost is worth less than a card.

Record (user, episode 92493855 step 55, turn 6 vs a Dragapult ex deck, LOST).
No matchup flag is on -- this is the generic board:

    US                                        THEM
    active  Tapu Bulu 140/140, 0 of 4         active  Munkidori 110/110
    bench   Teal Mask Ogerpon ex 210/210,     bench   Dragapult ex 320/320 with
            THREE Grass -- READY                      TWO energies (ready),
    hand    ONE Basic {G} Energy, Boss's,             Fezandipiti ex, Drakloak,
            Lillie's, Xerosic's, Night                Dreepy, Budew
            Stretcher, 2x Meganium, Bayleef,
            Hydrapple ex

The whole energy question of the turn was where that ONE Grass went, and the
hand's evolutions were all dead (Meganium needs a Bayleef in play, Hydrapple ex
a Dipplin, and there was neither). Two destinations: the ACTIVE Tapu Bulu, or
the benched Ogerpon's own Teal Dance.

The agent charged the Tapu Bulu (23010: the "+15000 future attacker" band of
`_energy_score_base` for a Tapu under four energies) and the Teal Dance came
back VETOED for overcharging a body that already covered its cost. Both
readings are wrong on the same board and for the same reason: THAT ENERGY WAS
NEVER GOING TO BE PAID OUT. Wood Hammer costs four and the Tapu was at zero;
its retreat costs three, so it could not even step aside for the Ogerpon that
WAS ready; and with no Meganium in play each Grass counts once. Their Dragapult
ex knocked the Tapu over with our Grass still on it.

THE RULE (`_attach_reaches_no_cost`, main.py). Before asking who deserves the
energy -- `energy_score`'s question, untouched -- ask whether ANY body of ours
is brought by it to a cost it can pay: a real attacker (MAIN_ATTACKERS) that
becomes able to attack, or the ACTIVE crossing its retreat cost. Nothing but
our own arithmetic goes into it, so it reads the same against every deck.

Three boundaries, and each one is a test below:

  * THE HORIZON IS TWO ATTACHMENTS. A body one attachment short today is ready
    next turn off the turn's own energy; two or more short is waiting on cards
    nobody promised. Without this, the rule swallowed
    [[test_the_parked_attachment_yields_to_nobody]]'s board -- an ACTIVE
    Ogerpon ex at 1 of 3 with a benched one already at 3 -- where the
    attachment IS the first of the two steps that arm the body in front.
  * THE TURN MUST HAVE NO ATTACK IN THE MENU. "Save the Grass" is a real
    answer while the board is still doing something with the turn. The
    boundary is [[test_state_builder]]'s Myriad combo: an active Ogerpon at
    four energies already knocking the opposing active out, where the extra
    Grass changes nothing and the card is worth more in hand.
  * EVERY PER-MATCHUP CAP STILL RULES. The escape is the LAST rung of the
    ability's overcharge block, so Cubchoo, Alakazam/Hop's, Crustle and
    Cornerstone are all asked first and still say no.

And the widened yield in `attach.py` only opens where the dance would
otherwise be VETOED -- an Ogerpon that already covers its cost. Where it is
still short the dance is a normal live play and the pre-existing block already
parks the attachment next to it; without that guard the clause fired 26 times
in 174 games against the meta decks for a weighted matrix delta of +0.00, and
narrowed it fires once.

WHAT IT MEASURED, so the next person does not have to re-run it. 174 games
against the meta decks with the instrumented copy
([[instrumentar-selfplay-parchear-la-copia-del-agente]]): the ability escape
fires 5 times and decides 4 of them; the widened yield adds 1 capped
attachment. Paired matrix (87 matchups, 17.381 games, `--seeds`): 84 of 87
decks move EXACTLY +0.0, weighted delta -0.01 points, prize delta -0.006. The
affected group is real but tiny, which is the case
[[politica-neutro-se-revierte-salvo-valor-ilegal]] calls a blind instrument
rather than a saturated one -- the generic bot barely reaches the board.

Coverage: the record's board flips to Teal Dance; the three boundaries above,
each measured by moving the board across them and back; and the predicate on
its own, over the horizon it draws.
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
from cg.api import OptionType
from golden_corpus import reset_agent
from patching import parcheado

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "dragapult_step55_the_attachment_reaches_no_cost.json")

GRASS = m.Basic_Grass_Energy
OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu


@pytest.fixture(autouse=True)
def reset_main_state():
    reset_agent(m)
    yield
    reset_agent(m)


def _board():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _mine(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def _decide(obs):
    """The option the agent picks on `obs`."""
    return obs["select"]["option"][m.agent(obs)[0]]


def _kind(option):
    return option["type"]


# ---------------------------------------------------------------------------
# 0. The board is the one the record had: both plays are really on the menu
# ---------------------------------------------------------------------------

def test_the_menu_offers_both_the_attachment_and_the_dance():
    """Without both on the menu the test measures nothing."""
    obs = _board()
    kinds = [o["type"] for o in obs["select"]["option"]]
    assert int(OptionType.ATTACH) in kinds, "the manual attachment has to be offered"
    assert int(OptionType.ABILITY) in kinds, "the Teal Dance has to be offered"
    assert int(OptionType.ATTACK) not in kinds, "the turn has no attack: that is the premise"

    mine = _mine(obs)
    assert mine["active"][0]["id"] == TAPU and not mine["active"][0]["energies"]
    assert mine["bench"][0]["id"] == OGERPON and len(mine["bench"][0]["energies"]) == 3
    assert [c["id"] for c in mine["hand"]].count(GRASS) == 1


# ---------------------------------------------------------------------------
# 1. The record's board: the Grass goes to the dance, not to the doomed Tapu
# ---------------------------------------------------------------------------

def test_the_dead_attachment_yields_to_the_teal_dance():
    obs = _board()
    option = _decide(obs)
    assert _kind(option) == int(OptionType.ABILITY), (
        "with the Tapu Bulu four attachments from Wood Hammer and three from "
        f"its own retreat, the Grass buys the dance and its card; chose {option}")


# ---------------------------------------------------------------------------
# 2. The horizon: one attachment short is a plan, two or more is a hope
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("energies_on_the_tapu, expected", [
    # 0 of 4: three attachments from Wood Hammer AND three from its own
    # retreat of 3 -- nothing is within reach. The record.
    (0, OptionType.ABILITY),
    # 1 of 4: still two attachments from the attack, but now exactly two from
    # the RETREAT -- and paying that retreat is what brings up the Ogerpon
    # that is already armed. A body within reach is a body within reach,
    # whichever of the two costs it reaches.
    (1, OptionType.ATTACH),
    (2, OptionType.ATTACH),    # 2 of 4: this one plus one more arms Wood Hammer
    (3, OptionType.ATTACH),    # 3 of 4: this one arms it
])
def test_the_horizon_is_two_attachments(energies_on_the_tapu, expected):
    """The Tapu Bulu is walked up to its costs and the decision flips exactly
    where the horizon says it should."""
    obs = _board()
    tapu = _mine(obs)["active"][0]
    tapu["energies"] = [1] * energies_on_the_tapu
    tapu["energyCards"] = [{"id": GRASS, "playerIndex": 0, "serial": 900 + k}
                           for k in range(energies_on_the_tapu)]
    option = _decide(obs)
    assert _kind(option) == int(expected), (
        f"with the active Tapu Bulu at {energies_on_the_tapu} of 4 the turn's "
        f"energy should go to {expected!r}; chose {option}")


# ---------------------------------------------------------------------------
# 3. A turn with an attack in it is not a dead turn
# ---------------------------------------------------------------------------

def test_an_attack_on_the_menu_closes_the_rule():
    """The rule only opens on a turn that is buying nothing else. With an
    attack offered the overcharge veto comes back and the Grass is not danced
    away."""
    obs = _board()
    obs["select"]["option"].append({"type": int(OptionType.ATTACK), "attackId": 1})
    option = _decide(obs)
    assert _kind(option) != int(OptionType.ABILITY), (
        f"with an attack on the menu the dance keeps its veto; chose {option}")


# ---------------------------------------------------------------------------
# 4. A dance that is still SHORT is not this rule's business
# ---------------------------------------------------------------------------

def test_a_short_ogerpon_is_the_old_rule_not_this_one():
    """With the benched Ogerpon under its cost the dance was never vetoed, so
    the widened yield must not open: the ability wins for the reason it always
    did, and the attachment keeps whatever number `energy_score` gave it."""
    obs = _board()
    ogerpon = _mine(obs)["bench"][0]
    ogerpon["energies"] = [1]
    ogerpon["energyCards"] = [{"id": GRASS, "playerIndex": 0, "serial": 950}]

    seen = {}

    def spy(context, select, scores, o, my_index, top_n=3):
        seen["scores"] = list(scores)

    with parcheado("_debug_log_decision", spy):
        option = _decide(obs)

    assert _kind(option) == int(OptionType.ABILITY), (
        f"a short Ogerpon's dance is a live play on its own; chose {option}")
    attach_active = [i for i, o in enumerate(obs["select"]["option"])
                     if o["type"] == int(OptionType.ATTACH)
                     and o["inPlayArea"] == 4][0]
    assert seen["scores"][attach_active] > 7000, (
        "the widened yield must not touch the attachment on a board where the "
        "dance was never vetoed")


# ---------------------------------------------------------------------------
# 5. The predicate on its own
# ---------------------------------------------------------------------------

def test_the_flag_is_off_once_a_body_is_within_reach():
    """`_attach_reaches_no_cost` is a property of the WHOLE field, so a body
    that comes within two attachments anywhere on the board closes it -- here
    a benched Hydrapple ex, which needs two."""
    obs = _board()
    seen = {}

    def spy(context, select, scores, o, my_index, top_n=3):
        seen["scores"] = list(scores)

    with parcheado("_debug_log_decision", spy):
        m.agent(obs)
        without = seen["scores"]

        reset_agent(m)
        obs2 = _board()
        _mine(obs2)["bench"].append({
            "appearThisTurn": False, "energies": [], "energyCards": [],
            "hp": 210, "id": m.Hydrapple_ex, "maxHp": 210, "playerIndex": 0,
            "preEvolution": [], "serial": 300, "tools": []})
        m.agent(obs2)
        with_reach = seen["scores"]

    ability = [i for i, o in enumerate(obs["select"]["option"])
               if o["type"] == int(OptionType.ABILITY)][0]
    assert without[ability] > 0, "with nothing within reach the dance is a play"
    assert with_reach[ability] <= 0, (
        "a Hydrapple ex two attachments from Syrup Storm is a body that cashes "
        "the Grass: the overcharge veto comes back")
