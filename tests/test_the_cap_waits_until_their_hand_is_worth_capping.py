"""vs Alakazam the cap is not played until their hand is worth capping: SIX cards.

Scenario (`records/registro_003_pasos_014_hasta_019.json`, episode 91176376,
turn 3 vs Alakazam -- LOST):

    US (6 prizes, seat 1)                      RIVAL (Alakazam, 6 prizes)
    active Tapu Bulu 140, 1 {G}                active Dunsparce 60
    bench  Applin 40 (1 {G}), Fezandipiti ex   bench  Abra x4 (one with 1 {G})
           Hydrapple ex (down this turn)       hand   FOUR cards
    stadium Forest of Vitality (ours)          discard 1
    hand   **Xerosic's Machinations**, Unfair Stamp

The turn's Supporter went on the Xerosic (step 17) with the opponent holding
**four** cards. What it bought: they discarded down to three -- ONE card --
and Powerful Hand went from 20 x (4 + 2) = 120 to 100. What it cost: the only
copy of the card the deck carries FOR this matchup, spent three turns before
their hand was inflated, plus the turn's Supporter slot.

Why it fired. `_xr_gate_alakazam` had two escape hatches under its own
threshold of six, and the second one opened here: a backup copy of Xerosic left
in the deck let the FIRST copy be spent from four cards up ("slow them down now,
keep the second for the late cap"). The replay of the record puts a number on
it -- `[reglas xerosic->play] alakazam_cap_the_hand=5900`, at an opposing hand
of 4.

CARD RULE (user, august 2026): against Alakazam the cap needs SIX cards in the
opposing hand, and that floor has no exceptions -- not a backup copy in the
deck, not the early trigger that fired at 4-5 when the Alakazam was already
active projecting a lethal Powerful Hand. Both branches existed to play the cap
BELOW the floor, and both are gone.

Two things make the rule bite, and they are what this file pins:

  * It is a **veto**, not a demotion. Below the floor the ladder used to fall
    through to `XEROSIC_SCORE_LAST_RESORT` (20), and 20 does not mean "do not
    play it", it means "play it if nothing else scores". The record's menu was
    exactly {play Xerosic, end turn}: the last-resort band would have spent the
    Supporter anyway, by elimination. See `alakazam_needs_six_cards`.

  * It is asked **before the search**, the same way the Meowth ex fetch already
    refuses to bring a Supporter it cannot use. A card the play side vetoes is
    not worth a Last-Ditch Catch -- the Meowth ex is a two-prize body on the
    bench and the fetch brings exactly one card. See
    `alakazam_xerosic_needs_six_cards` in `_RULES_MEOWTH_FETCH`.

The floor is a floor and not a preference: at six the cap is played exactly as
before (`alakazam_cap_the_hand`, 5900+), which is the boundary test below. And
it names the Alakazam matchup only -- against every other deck the generic
branch (opposing hand >= 7) decides as it always did.

See [[la-observacion-manda-en-la-vida-nosotros-solo-calculamos-el-dano]] for the
damage model behind Powerful Hand, and
[[la-regla-general-va-antes-que-su-caso-especial]].
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
            / "alakazam_the_cap_waits_for_six_cards_step17.json")

XEROSIC = m.Xerosic_Machinations
STAMP = m.Unfair_Stamp
LILLIE = m.Lillie_Determination
BOSS = m.Boss_Orders
ABRA = m.Abra
TAPU = m.Tapu_Bulu

_END_TURN = 14      # OptionType.END_TURN
_PLAY = 7           # OptionType.PLAY


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    yield
    m._init_cards_tracking()


def _obs(op_hand=None):
    obs = copy.deepcopy(
        json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    if op_hand is not None:
        cur = obs["current"]
        cur["players"][1 - cur["yourIndex"]]["handCount"] = op_hand
    return obs


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _played(obs, choice):
    """The card id the chosen option plays, or None if it plays nothing."""
    opt = obs["select"]["option"][choice[0]]
    if opt.get("type") != _PLAY:
        return None
    return [c["id"] for c in _mine(obs)["hand"]][opt["index"]]


# ---------------------------------------------------------------------------
# 1. The record: the board, and then the decision
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_menu_that_spent_the_supporter():
    o = _obs()
    cur = o["current"]
    mine, op = cur["players"][cur["yourIndex"]], cur["players"][1 - cur["yourIndex"]]

    assert cur["supporterPlayed"] is False, "el Supporter del turno sigue libre"
    assert [c["id"] for c in mine["hand"]] == [XEROSIC, STAMP], (
        "la mano del paso 17: el tope y el Unfair Stamp")
    assert op["handCount"] == 4, "la mano rival: CUATRO cartas"
    assert any(p["id"] == ABRA for p in op["bench"]), (
        "la linea Alakazam en su banca es lo que enciende el matchup")
    assert mine["active"][0]["id"] == TAPU
    assert [o["select"]["option"][i].get("type")
            for i in range(len(o["select"]["option"]))] == [_PLAY, _END_TURN], (
        "el menu era exactamente {jugar Xerosic, terminar turno}: por eso la "
        "banda de ultimo recurso (20) bastaba para gastarlo por eliminacion")


def test_the_cap_is_not_played_with_four_cards_in_their_hand():
    """The regression of the record: `alakazam_cap_the_hand` scored 5900 at an
    opposing hand of four and burned the Supporter to discard ONE card."""
    o = _obs()
    choice = m.agent(o)
    assert _played(o, choice) != XEROSIC, (
        "con mano rival de 4 el tope no se juega: se guarda para cuando su "
        "mano valga toparla")
    assert o["select"]["option"][choice[0]].get("type") == _END_TURN, (
        "sin otra jugada en el menu, el turno termina con el Xerosic en mano")


@pytest.mark.parametrize("op_hand", [4, 5])
def test_the_floor_holds_under_six(op_hand):
    o = _obs(op_hand)
    assert _played(o, m.agent(o)) != XEROSIC, (
        f"mano rival {op_hand} < 6: por debajo del suelo no se juega")


@pytest.mark.parametrize("op_hand", [6, 7])
def test_at_six_the_cap_is_played_exactly_as_before(op_hand):
    """The boundary in the other direction: the rule is a floor, not a new
    preference. At six -- Powerful Hand already projecting 20 x (6 + 2) = 160 --
    the same board plays the same card."""
    o = _obs(op_hand)
    assert _played(o, m.agent(o)) == XEROSIC, (
        f"mano rival {op_hand} >= 6: el tope se juega como siempre")


# ---------------------------------------------------------------------------
# 2. The veto, not the last-resort band
# ---------------------------------------------------------------------------

class _CtxFloor:
    """The three fields the ladder reads before reaching the new rule."""

    class _S:
        supporterPlayed = False

    def __init__(self, op_hand_count, alakazam=True):
        self.state = self._S()
        self.op_hand_count = op_hand_count
        self.op_is_alakazam_deck = alakazam


@pytest.mark.parametrize("op_hand", [4, 5])
def test_below_the_floor_the_score_is_a_veto_and_not_the_last_resort_band(op_hand):
    """`XEROSIC_SCORE_LAST_RESORT` would still have won the record's menu.

    The distinction is the whole reason `alakazam_needs_six_cards` exists as a
    rule of its own instead of simply letting the gate fail: a Supporter at 20
    is played whenever nothing else scores, and on that turn nothing else did.
    """
    value, trace = m._resolve_rules(
        m._RULES_XEROSIC_PLAY, [], _CtxFloor(op_hand),
        m.XEROSIC_SCORE_LAST_RESORT)
    assert value == m.SCORE_VETO, (
        f"por debajo del suelo el tope esta VETADO, no en la banda de ultimo "
        f"recurso ({m.XEROSIC_SCORE_LAST_RESORT}); obtuvo {value} ({trace})")
    assert any("alakazam_needs_six_cards" in t for t in trace), (
        f"y lo veta la regla del suelo, no otra: {trace}")


# ---------------------------------------------------------------------------
# 3. The same floor, asked BEFORE the search
# ---------------------------------------------------------------------------

def _fetch_score(card_id, **kw):
    """A candidate of the Meowth ex Last-Ditch Catch, on an Alakazam board."""
    field = dict(sv=0, hand_counts={}, supp_values={}, hand_size=4,
                 strong_attacker=True, op_hand_count=4,
                 active_cant_attack=False, win_via_boss=False,
                 gust2_via_boss=False, deny_evo_via_boss=False,
                 devel_lillie=False, alakazam=True, first_turn=False,
                 lillie_alcanzable=True)
    field.update(kw)
    ctx = m._CtxMeowthFetch(
        card_id, field["sv"], field["hand_counts"], field["supp_values"],
        field["hand_size"], field["strong_attacker"], field["op_hand_count"],
        field["active_cant_attack"], field["win_via_boss"],
        field["gust2_via_boss"], field["deny_evo_via_boss"],
        field["devel_lillie"], field["alakazam"], field["first_turn"],
        field["lillie_alcanzable"])
    value, _ = m._resolve_rules(m._RULES_MEOWTH_FETCH, [], ctx, 50)
    return value


@pytest.mark.parametrize("op_hand", [4, 5])
def test_the_last_ditch_does_not_search_for_a_cap_it_cannot_play(op_hand):
    """The Meowth ex is a two-prize body and the fetch brings ONE card: it does
    not spend either on a Supporter the play side has already vetoed."""
    assert _fetch_score(XEROSIC, op_hand_count=op_hand) <= 40, (
        f"mano rival {op_hand} < 6: el Xerosic no es objetivo de la busqueda")
    assert _fetch_score(LILLIE, op_hand_count=op_hand,
                        devel_lillie=True) == 1250, (
        "y el refill sigue siendo un objetivo normal: no se veta la busqueda "
        "entera, solo la carta que no se puede jugar")


def test_at_six_the_last_ditch_searches_for_the_cap_again():
    assert _fetch_score(XEROSIC, op_hand_count=6) >= 1260, (
        "mano rival 6: `xerosic_alakazam` vuelve a mandar sobre el refill")


def test_outside_the_alakazam_matchup_the_ladder_is_untouched():
    """The floor names one matchup. Against any other deck the generic branch
    (opposing hand >= 7) keeps deciding exactly as it did."""
    assert _fetch_score(XEROSIC, alakazam=False, op_hand_count=7) == 1100, (
        "sin Alakazam enfrente, `xerosic_generico` sigue intacto")
    assert _fetch_score(XEROSIC, alakazam=False, op_hand_count=5) <= 50, (
        "y con mano rival de 5 sin Alakazam la escalera decidia ya que no")
