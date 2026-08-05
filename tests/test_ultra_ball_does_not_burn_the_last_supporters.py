"""The Ultra Ball's cost may not empty a hand whose last cards are Supporters.

Scenario (`records/registro_002_pasos_009_hasta_020.json`, step 16, episode
89628731 vs Alakazam -- WON in spite of this):

    US                                    RIVAL (Alakazam)
    active  Tapu Bulu 140  (no energy)    active  Abra 50
    bench   Tapu Bulu 140  (no energy)    bench   --
            Teal Mask Ogerpon ex 210 (no energy)
    hand    **Ultra Ball**, Xerosic's Machinations,
            Lillie's Determination
    turn's Supporter: ALREADY SPENT (the first Xerosic)

Not one energy on the board and none in hand: there is no attacker this turn and
none next turn either unless the hand is refilled. The agent played the Ultra
Ball, paid its cost of two discards with the Xerosic AND the Lillie's -- the
only two cards it had -- and fetched a Chikorita, a body this matchup does not
care about. The turn ended with a hand of ZERO cards, a board with no energy,
and the one card that could have restarted the hand in the discard pile.

Ending the turn instead keeps both Supporters. Next turn Lillie's Determination
draws a whole new hand, which is the only route back to an attacker; the Xerosic
keeps capping Powerful Hand.

Why every existing veto missed it. The Ultra Ball's cost vetoes
(`_ub_cancel_lillie`, `_ub_cancel_xerosic`, `_ub_cancel_meowth`) are ALL gated
on `not state.supporterPlayed`: they compare the Ultra Ball against a Supporter
that competes with it TODAY. With the turn's Supporter already spent that whole
family goes blind -- and so does the `SelectContext.DISCARD` scorer, which
prices a card by what it does NOW and therefore drops a Supporter that can no
longer be played. The valuation inverts exactly where it should not: the more
useless a Supporter is this turn, the more eagerly the cost eats it, even though
it is precisely the card that carries the whole of the next turn.

The Ultra Ball itself was correctly vetoed (score -1, by the first-turn gate).
What played it was the STERILE-TURN RESCUE NET, which lifts a vetoed Ultra Ball
to 200 when the turn would otherwise be dead. That net already refuses to
revoke a COST veto ([[ub-veto-por-coste-no-se-revoca-por-turno-esteril]]) by
asking `_ub_cost_destroys_better_card` -- but that predicate had nothing to say
here, because every veto inside it required an unplayed Supporter.

Rule: **with the turn's Supporter already spent and a hand of exactly the Ultra
Ball plus two other cards, the Ultra Ball is not played if either of those two
is a Supporter.** It names no card, no target and no matchup -- only the shape
of the hand -- so it holds for any deck.

The bound is WHERE THE COST COMES FROM. The two discards have to be paid out of
SURPLUS. With the Ultra Ball plus exactly two cards there is no surplus: those
two ARE the cost, whatever they are, and the hand ends at zero. Paying with a
Supporter out of a hand of seven is a trade -- something is kept, and the search
usually completes an evolution line the same turn; paying with a Supporter out
of a hand of three is dismantling the engine to bench a body.
`_ub_score_before_overrides` already refuses the Ultra Ball below three cards
for this same reason; this closes the boundary case, where the third card is the
one that would have restarted the hand.

Deliberately NOT extended above three cards. With four or more the same
arithmetic can still burn the last Supporter, but the hand survives -- and the
two measured counter-examples of the sterile-turn net live there
(`abomasnow_t6_ub_con_budew_rival` and `abomasnow_t6_ub_preevo_evolucionable`,
hands of 8 and 7 where the search completes an evolution THIS turn or the
opponent's Budew makes the Item use-it-or-lose-it). Both are pinned below.

Implementation: `_ub_cancel_tomorrow_supporter` in `ptcg/decision/ultra_ball.py`,
joined to `_ub_cost_destroys_better_card` (so the sterile-turn net cannot revoke
it) and to the veto list of `_ub_score_before_overrides`.
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
from tests.state_builder import Escenario, pk

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_t2_ultra_ball_does_not_burn_the_last_supporters_step16.json")

_BUDEW_FIXTURE = (ROOT / "tests" / "fixtures"
                  / "abomasnow_t6_ub_con_budew_rival.json")
_PREEVO_READY_FIXTURE = (ROOT / "tests" / "fixtures"
                         / "abomasnow_t6_ub_preevo_evolucionable.json")

ULTRA_BALL = m.Ultra_Ball
LILLIE = m.Lillie_Determination
XEROSIC = m.Xerosic_Machinations
BOSS = m.Boss_Orders
DAWN = m.Dawn
GRASS = m.Basic_Grass_Energy
TAPU = m.Tapu_Bulu
OGERPON = m.Teal_Mask_Ogerpon_ex
CHIKORITA = m.Chikorita
ABRA = m.Abra


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _obs(fixture):
    return copy.deepcopy(json.load(open(fixture, encoding="utf-8"))["observation"])


def _chosen(obs):
    return obs["select"]["option"][m.agent(obs)[0]]


def _idx_play(obs, card_id):
    """Index of the 'PLAY <card_id>' option in the main menu, or -1."""
    hand = obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(m.OptionType.PLAY) and hand[o["index"]]["id"] == card_id:
            return i
    return -1


def _plays_the_ultra_ball(obs):
    idx = _idx_play(obs, ULTRA_BALL)
    assert idx >= 0, "el escenario no ofrece jugar la Ultra Ball: no mide nada"
    return m.agent(obs)[0] == idx


def _scenario(hand, supporter_played=True):
    """A settled board with the turn's Supporter spent and a menu of the hand.

    Three bodies down and no energy anywhere, exactly as in the record: nothing
    in the position argues for or against the Ultra Ball beyond the shape of the
    hand, which is what these cases measure.
    """
    return (Escenario(turn=4, step=16, tac=3, first_player=1,
                      supporter_played=supporter_played)
            .my_active(pk(TAPU))
            .my_bench(pk(TAPU), pk(OGERPON))
            .my_hand(*hand)
            .op_active(pk(ABRA))
            .op_zonas(hand=3, deck=45, prizes=6)
            .menu_hand()
            .build())


class _Ctx:
    """The minimum `_ub_cancel_tomorrow_supporter` consults.

    Same stub style as `tests/test_ultra_ball_does_not_burn_xerosic.py`: the
    predicate reads the shape of the hand and nothing else, so the board does
    not need to be built to pin its boundaries.
    """

    class _State:
        def __init__(self, supporter_played):
            self.supporterPlayed = supporter_played
            self.turn = 4

    def __init__(self, hand, supporter_played=True):
        self.hand_counts = dict(hand)
        self.my_state = type("S", (), {
            "hand": [object() for _ in range(sum(hand.values()))]})()
        self.state = self._State(supporter_played)


# ---------------------------------------------------------------------------
# 1. The record: the scenario, and then the decision
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_hand_of_three_with_the_supporter_already_spent():
    o = _obs(_FIXTURE)
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]

    assert cur["supporterPlayed"] is True, "el Supporter del turno ya se gasto"
    assert [c["id"] for c in mine["hand"]] == [XEROSIC, LILLIE, ULTRA_BALL]
    assert all(not p["energies"] for p in mine["active"] + mine["bench"]), (
        "no hay ni una energia en el tablero: sin refresco no hay atacante")
    assert _idx_play(o, ULTRA_BALL) >= 0, "el paso ofrecia jugar la Ultra Ball"


def test_the_ultra_ball_is_not_played_with_only_the_two_supporters_left():
    """The regression of the record: the sterile-turn net used to lift it to
    200 and pay its cost with the Xerosic and the Lillie's."""
    o = _obs(_FIXTURE)
    assert _chosen(o).get("type") == int(m.OptionType.END), (
        "con la mano en {Ultra Ball, Xerosic, Lillie's} y el Supporter del "
        "turno gastado, pagar la Ultra Ball quema los dos Supporters y deja la "
        "mano a CERO; esperaba END")


def test_the_cost_veto_is_the_one_that_fires(monkeypatch):
    """It has to be a COST veto -- the group the sterile-turn net may not
    revoke -- and not a conservatism one, which the net would override. The
    context is the PRODUCTION one, captured on the way through: what has to hold
    is that `_ub_cost_destroys_better_card` answers yes for the real board, since
    that is the single question the net asks."""
    seen = []
    original = m._score_ultra_ball_play

    def spy(ctx):
        seen.append((m._ub_cancel_tomorrow_supporter(ctx),
                     m._ub_cost_destroys_better_card(ctx)))
        return original(ctx)

    monkeypatch.setattr(m, "_score_ultra_ball_play", spy)
    m.agent(_obs(_FIXTURE))

    assert seen, "la Ultra Ball ni siquiera se puntuo: el escenario no mide nada"
    assert all(seen), (
        f"esperaba el veto de coste en todas las pasadas, vi {seen}")


# ---------------------------------------------------------------------------
# 2. The shape of the hand decides: any Supporter, any deck
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("supporter", [LILLIE, XEROSIC, BOSS, DAWN])
def test_any_supporter_as_the_last_card_holds_the_ultra_ball(supporter):
    """The rule names no card: the refill Supporters, the gust and the
    disruption are all somebody's next turn."""
    assert not _plays_the_ultra_ball(_scenario([ULTRA_BALL, supporter, GRASS]))


def test_without_a_supporter_the_hand_of_three_still_digs():
    """The boundary: emptying the hand is only a mistake when what goes with it
    is the engine. With no Supporter there is nothing to keep for tomorrow, so
    trading two spare cards for a body is fine."""
    assert _plays_the_ultra_ball(_scenario([ULTRA_BALL, GRASS, GRASS]))


def test_with_the_turn_supporter_still_free_this_is_not_the_rule_that_decides():
    """`not supporterPlayed` belongs to `_ub_cancel_lillie` and company, which
    also weigh what the Supporter would DO this turn. This veto must stay out
    of their way."""
    ctx = _Ctx({ULTRA_BALL: 1, LILLIE: 1, GRASS: 1}, supporter_played=False)
    assert not m._ub_cancel_tomorrow_supporter(ctx)


def test_a_fourth_card_in_hand_lifts_the_hold():
    """Above three cards the cost comes out of surplus: the hand survives the
    payment, so this veto says nothing and the normal valuation decides."""
    ctx = _Ctx({ULTRA_BALL: 1, LILLIE: 1, GRASS: 2})
    assert not m._ub_cancel_tomorrow_supporter(ctx)


def test_two_copies_of_the_same_supporter_are_still_held():
    """A spare copy is normally fodder, but not at this hand size: the two
    discards take both, so the pair ends in the discard, not one kept."""
    ctx = _Ctx({ULTRA_BALL: 1, LILLIE: 2})
    assert m._ub_cancel_tomorrow_supporter(ctx)


# ---------------------------------------------------------------------------
# 3. The two measured counter-examples of the sterile-turn net still dig
# ---------------------------------------------------------------------------

def test_the_budew_item_lock_still_plays_the_ultra_ball():
    """Hand of 8: use it or lose it, and the payment leaves a real hand."""
    assert _chosen(_obs(_BUDEW_FIXTURE)).get("type") == int(m.OptionType.PLAY)


def test_the_search_that_completes_an_evolution_today_still_plays():
    """Hand of 7: the fetched card evolves a settled pre-evolution THIS turn."""
    assert _chosen(_obs(_PREEVO_READY_FIXTURE)).get("type") == int(m.OptionType.PLAY)
