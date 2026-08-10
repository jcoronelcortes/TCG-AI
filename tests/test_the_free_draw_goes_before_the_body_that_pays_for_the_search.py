"""The free draw is cashed BEFORE the two-prize body that pays for the search.

Scenario (`records/registro_005_pasos_041_hasta_059.json`, episode 91176376,
turn 5 -- LOST):

    US (6 prizes, seat 1)                      RIVAL (Alakazam)
    active Dipplin 80                          active Alakazam ex 140, 1 {G}
    bench  **Fezandipiti ex** (Flip the         bench  Kadabra x3
           Script LIVE: our Tapu Bulu was
           knocked out last turn)
           Teal Mask Ogerpon ex, Chikorita
    hand   **Meowth ex**, Forest of Vitality, Boss's Orders, Teal Mask Ogerpon ex

The turn benched the Meowth ex (step 50), used its Last-Ditch Catch to search
the deck for a Dawn, played the Dawn -- and only THEN drew the three cards of
Flip the Script. Two of those three cards were a Xerosic's Machinations and a
Meganium.

Nothing in the SCORES says to do that. On that menu the ability was the highest
number by ten thousand points:

    Flip the Script  31700   >   Meowth ex 21500   >   Teal Mask Ogerpon ex 21000

The order came from the TIER, which is read before the score: a Pokemon PLAY
lives in `_TIER_DEVELOP` (40) and an ability in `_TIER_ENERGY` (10). No amount
of scoring could have fixed it.

CARD RULE (user, august 2026), deck-agnostic: when we are about to bench Meowth
ex to search for a Trainer and Fezandipiti ex's ability is available, the
ability goes FIRST and only afterwards is the search re-evaluated.

The arithmetic behind it: Flip the Script draws THREE cards and costs nothing;
the Last-Ditch Catch brings ONE and charges a two-prize body on the bench for
it. Draw first and the search may not be needed at all -- the Supporter we were
digging for can be among the three -- and when it still is, it is decided with
three more cards of information. Draw second and the Meowth is on the bench
either way. And the ability cannot simply be done later: it is free, ONCE PER
TURN, and its condition (being knocked out last turn) dies with the turn.

It is the same sentence the Bug Catching Set tier already writes ("with the 2
new cards in hand it is decided BETTER which body goes down"), with a stronger
reason: here the body costs two prizes.

WHY IT PROMOTES THE ABILITY INSTEAD OF DEMOTING THE MEOWTH. Dropping the Meowth
play below `_TIER_DEVELOP` would also drop it behind every other Pokemon in the
menu, and with the bench at 4/5 an Applin would take the last seat the search
body needs. Drawing three cards earlier cannot invalidate a later play; being
outrun to a bench seat can. See `_TIER_FEZ_BEFORE_SEARCH` in
`ptcg/turn/finalize.py`.

It fires only while BOTH plays are really on the menu, so a Flip the Script that
its own guards have silenced -- the deck-out brake, or the standing ordering
vetoes that give the turn to Unfair Stamp / Lillie's first -- keeps the old
order untouched.

See [[cadena-ultraball-fezandipiti-flip-the-script]] for the band the ability
scores in, [[unfair-stamp-antes-de-bajar-meowth]] for the other half of the
order around this same body, and [[el-tier-de-orden-manda-sobre-la-puntuacion]].
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import main as m  # noqa: E402
from fez_menu import ofrece_flip_the_script, sin_flip_the_script  # noqa: E402

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_the_free_draw_goes_before_the_search_body_step50.json")
# The SAME order on another matchup and another seat: vs Mega Lucario, the
# counterfactual board of `unfair-stamp-antes-de-bajar-meowth` with the Stamp
# already played. It is the deck-agnostic control -- no card of the Alakazam
# deck is anywhere near it.
_LUCARIO_FIXTURE = (ROOT / "tests" / "fixtures"
                    / "lucario_step115_meowth_after_unfair_stamp.json")

MEOWTH = m.Meowth_ex
FEZ = m.Fezandipiti_ex
OGERPON = m.Teal_Mask_Ogerpon_ex

_PLAY = 7
_ABILITY = 10


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    yield
    m._init_cards_tracking()


def _obs(path=_FIXTURE, key="observation"):
    with open(path, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)[key])


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _decide(obs, ub_meowth_pending=False):
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    # AFTER the reset: `reset()` clears the engine flags, so setting it before
    # would test a board that no longer carries the engine under test.
    if ub_meowth_pending:
        m.AGENT_STATE._ub_meowth_pending = True
    choice = m.agent(copy.deepcopy(obs))
    return choice, obs["select"]["option"][choice[0]]


def _played_id(obs, opt):
    if opt.get("type") != _PLAY:
        return None
    return [c["id"] for c in _mine(obs)["hand"]][opt["index"]]


def _ability_card_id(obs, opt):
    if opt.get("type") != _ABILITY:
        return None
    mine = _mine(obs)
    bodies = mine["active"] if opt.get("area") == 4 else mine["bench"]
    return bodies[opt["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The record: the board, and then the order
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_menu_that_benched_the_search_body():
    o = _obs()
    mine = _mine(o)

    assert MEOWTH in [c["id"] for c in mine["hand"]], (
        "el Meowth ex esperaba en la mano: su unico valor es el Last-Ditch")
    assert mine["bench"][0]["id"] == FEZ
    assert ofrece_flip_the_script(o), (
        "Flip the Script viva: nos noquearon el turno pasado")
    assert o["current"]["supporterPlayed"] is False, (
        "el Supporter del turno sigue libre: la busqueda tenia a que jugar")


def test_the_ability_goes_before_benching_the_search_body():
    """The regression of the record: the Meowth went down first (21500 in tier
    DEVELOP) and the 31700 of the ability waited three actions."""
    o = _obs()
    _, opt = _decide(o)
    assert _ability_card_id(o, opt) == FEZ, (
        f"con Flip the Script viva y un Meowth ex en mano, el robo gratis va "
        f"primero; obtuvo {opt}")


def test_afterwards_the_search_is_re_evaluated_and_still_happens():
    """The other half of the rule: it is an ORDER, not a veto.

    Flip the Script is ONCE PER TURN, so on the next menu the ability is no
    longer offered -- and there the Meowth engine decides again, now with three
    more cards in hand. On this board it still wants the search, and takes it.
    """
    o = sin_flip_the_script(_obs())
    _, opt = _decide(o)
    assert _played_id(o, opt) == MEOWTH, (
        f"cobrada la habilidad, la busqueda se re-evalua y sigue en pie; "
        f"obtuvo {opt}")


# ---------------------------------------------------------------------------
# 2. Specificity: it is the SEARCH BODY that moves the ability
# ---------------------------------------------------------------------------

def test_without_the_search_body_the_old_order_stands():
    """The control that keeps the rule from being a general promotion.

    The same board with the Meowth ex swapped for another Teal Mask Ogerpon ex:
    same menu, same options, same ability -- and no body waiting to pay for a
    search. There the ability keeps `_TIER_ENERGY` and development goes first,
    exactly as before.
    """
    o = _obs()
    _mine(o)["hand"][0]["id"] = OGERPON
    _, opt = _decide(o)
    assert opt.get("type") == _PLAY and _played_id(o, opt) == OGERPON, (
        f"sin cuerpo de busqueda en mano la promocion no aplica; obtuvo {opt}")


# ---------------------------------------------------------------------------
# 3. Deck-agnostic: another matchup, another seat
# ---------------------------------------------------------------------------

def test_the_same_order_on_another_matchup():
    o = _obs(_LUCARIO_FIXTURE, "synthetic_post_stamp")
    assert MEOWTH in [c["id"] for c in _mine(o)["hand"]]
    assert ofrece_flip_the_script(o)

    _, opt = _decide(o, ub_meowth_pending=True)
    assert _ability_card_id(o, opt) == FEZ, (
        f"vs Mega Lucario, en el asiento 0 y con el motor `_ub_meowth_pending` "
        f"empujando el Meowth, el robo sigue yendo primero; obtuvo {opt}")
