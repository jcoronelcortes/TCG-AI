"""A Supporter that says it does nothing may not keep a Meowth ex in hand.

Scenario (`records/registro_004_pasos_045_hasta_052.json`, step 46, episode
89624781 vs Dragapult ex -- WON in spite of this):

    US (6 prizes)                          OPPONENT (6 prizes, 4 cards in hand)
    active  Teal Mask Ogerpon ex, 1 {G}    active  Dreepy 70
    bench   Teal Mask Ogerpon ex, 2 {G}    bench   Drakloak 90
            Applin 40
            Teal Mask Ogerpon ex, 1 {G}
    hand    Xerosic's Machinations, Unfair Stamp, **Meowth ex**,
            Ultra Ball, Hydrapple ex
    stadium Forest of Vitality (ours, already played this turn)

There is no Grass energy in hand, so this turn cannot attach, cannot use Teal
Dance (it attaches from hand) and cannot attack: everything the turn is worth is
in fixing the hand, with three Lillie's Determination alive in the deck and a
Meowth ex whose Last-Ditch Catch reaches them.

The agent spent the turn's Supporter on Xerosic -- against a Dragapult deck,
with the opponent on FOUR cards, so the cap took exactly ONE random card away
and there is no Powerful Hand for it to cap. Straight after, the Ultra Ball paid
its cost with the Meowth ex and the Hydrapple ex, and the turn ended on a hand of
one card.

Three correct rules blocking each other in a circle:

    Lillie's (the one the fetch would bring)   -1   `ultra_ball_completes_the_line`
    Meowth ex                                  -1   `_meowth_fetch_loses_the_turn`
    Xerosic                                    20   its default, XEROSIC_SCORE_LAST_RESORT

The first is an ORDER veto ("play the Ultra Ball first, it completes the
Applin -> Dipplin -> Hydrapple line"). The second read that -1 as the real value
of the fetch and concluded that the fetched Supporter would lose the slot to the
Xerosic already in hand. The third then won the menu by elimination -- at the
height its own scorer uses to say it has no useful effect.

The fix is on the Meowth side: `_meowth_fetch_loses_the_turn` now requires the
in-hand Supporter to win the slot ABOVE `SUPP_SCORE_LAST_RESORT_BAND`, the band
where every Supporter scorer says "play me only because nothing else scores"
(XEROSIC_SCORE_LAST_RESORT and BOSS_SCORE_EMPTY_GUST both sit there). If nothing
we hold does anything today, a fresh Supporter out of the deck is worth the
2-prize body.

Why not the Xerosic side. Leaving Xerosic at 20 keeps it as the net that takes
the slot whenever the Meowth is vetoed for some other reason. Vetoing it there
would let the two yield to each other and lose the Supporter entirely -- the
Lillie's <-> Boss's failure already measured.

It is NOT the first-turn rule of `test_first_turn_lillie_over_xerosic.py`. That
one is gated on our first turn and is silent here, and there Xerosic won at 5950
through `alakazam_cap_the_hand`; here it wins at 20 with nothing to beat.
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

_FIXTURES = ROOT / "tests" / "fixtures"
_MENU = _FIXTURES / "dragapult_t4_meowth_over_the_last_resort_xerosic_step46.json"
# The continuation, reconstructed from the same record: the Meowth ex benched and
# the Last-Ditch Catch prompt over the REAL deck of that game (the deck list is
# the one the record itself shows at step 50).
_LAST_DITCH = _FIXTURES / "dragapult_t4_last_ditch_fetches_the_lillie_step46b.json"

LILLIE = m.Lillie_Determination
XEROSIC = m.Xerosic_Machinations
MEOWTH = m.Meowth_ex
ULTRA_BALL = m.Ultra_Ball
HYDRAPPLE = m.Hydrapple_ex
STAMP = m.Unfair_Stamp
GRASS = m.Basic_Grass_Energy


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs(path):
    return copy.deepcopy(json.load(open(path, encoding="utf-8"))["observation"])


def _idx_play(obs, card_id):
    """Index of the 'PLAY <card_id>' option in the main menu, or -1."""
    cur = obs["current"]
    hand = cur["players"][cur["yourIndex"]]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(m.OptionType.PLAY) and hand[o["index"]]["id"] == card_id:
            return i
    return -1


# ---------------------------------------------------------------------------
# 1. The record: the scenario, and then the decision
# ---------------------------------------------------------------------------

def test_the_fixture_is_a_dead_turn_with_the_supporter_still_free():
    o = _obs(_MENU)
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert cur["turn"] == 4, "no es el primer turno: la regla anterior calla aqui"
    assert cur["supporterPlayed"] is False, "el Supporter del turno sigue libre"
    assert [c["id"] for c in mine["hand"]] == [
        XEROSIC, STAMP, MEOWTH, ULTRA_BALL, HYDRAPPLE]
    assert all(c["id"] != GRASS for c in mine["hand"]), (
        "sin Energia Planta en mano: ni adjunte, ni Teal Dance, ni ataque -- "
        "el turno entero vale lo que valga arreglar la mano")
    assert theirs["handCount"] == 4, (
        "mano rival de 4: capar deja exactamente UNA carta fuera")
    assert m.AGENT_STATE is not None


def test_the_menu_offers_both_the_xerosic_and_the_meowth():
    o = _obs(_MENU)
    assert _idx_play(o, XEROSIC) >= 0 and _idx_play(o, MEOWTH) >= 0, (
        "el paso ofrecia ambas: el menu mide la prioridad")


def test_the_turn_benches_the_meowth_instead_of_the_last_resort_xerosic():
    """The regression of the record: Xerosic won the menu at 20 -- the band of
    'no useful effect' -- because the Meowth was vetoed for losing the turn to
    it."""
    o = _obs(_MENU)
    assert m.agent(o) == [_idx_play(o, MEOWTH)], (
        "con la mano rival en 4 y sin Powerful Hand, el Xerosic no es el "
        "Supporter del turno: el slot es para lo que traiga el Last-Ditch")


# ---------------------------------------------------------------------------
# 2. The chain the fix delivers: Meowth ex -> Lillie's -> Lillie's is played
# ---------------------------------------------------------------------------

def test_the_last_ditch_fetches_the_lillie():
    o = _obs(_LAST_DITCH)
    deck = o["select"]["deck"]
    chosen = m.agent(o)
    assert len(chosen) == 1, "el Last-Ditch se resuelve con UNA carta"
    picked = deck[o["select"]["option"][chosen[0]]["index"]]["id"]
    assert picked == LILLIE, (
        "el turno esta muerto y quedan tres Lillie's vivas: la busqueda es esa")


def test_the_fetched_lillie_is_played_this_turn():
    """The point of the whole chain: the Supporter slot ends on the refill, not
    on the cap. Without this the fix would only have swapped one waste for
    another (a 2-prize body benched for a Supporter that stays in hand)."""
    o = _obs(_LAST_DITCH)
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    mine["hand"].append({"id": LILLIE, "playerIndex": 0, "serial": 26})
    mine["handCount"] = len(mine["hand"])
    cur["turnActionCount"] += 1
    o["select"] = {
        "context": 0, "contextCard": None, "deck": None, "effect": None,
        "maxCount": 1, "minCount": 1,
        "option": [{"index": 0, "type": 7},      # Xerosic
                   {"index": 2, "type": 7},      # Ultra Ball
                   {"index": 4, "type": 7},      # the fetched Lillie's
                   {"type": 12}, {"type": 14}],
        "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 0}
    assert m.agent(o) == [_idx_play(o, LILLIE)]


# ---------------------------------------------------------------------------
# 3. The boundary: the Xerosic that REALLY disrupts still keeps the Supporter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("op_hand", [3, 4, 5, 6])
def test_below_the_band_the_meowth_goes_down(op_hand):
    """Up to an opposing hand of 6 the generic Xerosic stays at its last-resort
    default (or is vetoed outright at <= 3): it never keeps the Meowth in hand."""
    o = _obs(_MENU)
    o["current"]["players"][1 - o["current"]["yourIndex"]]["handCount"] = op_hand
    assert m.agent(o) == [_idx_play(o, MEOWTH)]


@pytest.mark.parametrize("op_hand", [7, 9, 12])
def test_a_xerosic_that_really_disrupts_keeps_the_supporter(op_hand):
    """The other side of the boundary. From 7 cards up, `generic_very_big_hand`
    scores the Xerosic at XEROSIC_SCORE_GENERIC -- a real Supporter for the turn,
    well above the band -- and the prediction correctly keeps the Meowth in hand:
    the fetched Lillie's could not be played today anyway."""
    o = _obs(_MENU)
    o["current"]["players"][1 - o["current"]["yourIndex"]]["handCount"] = op_hand
    assert m.agent(o) == [_idx_play(o, XEROSIC)]


def test_the_band_is_the_shared_one_of_the_supporter_scorers():
    """The threshold is not a new number: it is where the scorers already say
    'no useful effect'."""
    assert m.SUPP_SCORE_LAST_RESORT_BAND == m.XEROSIC_SCORE_LAST_RESORT
    assert m.SUPP_SCORE_LAST_RESORT_BAND == m.BOSS_SCORE_EMPTY_GUST
