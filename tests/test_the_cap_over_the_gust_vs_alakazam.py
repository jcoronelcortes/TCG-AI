"""vs Alakazam, the Last-Ditch fetch brings the cap, not the two-prize gust.

Scenario (`records/registro_006_pasos_059_hasta_070.json`, step 62, episode
89638367 vs Alakazam -- LOST):

    US                                     RIVAL (Alakazam)
    active  Teal Mask Ogerpon ex 210       active  Alakazam 140 (1 energy)
            (6 effective energies)         bench   Fezandipiti ex 210
    bench   Meganium 160                           Kadabra 80, Abra 50,
            Applin 40                              Dunsparce 70
            Meowth ex 170 (just benched)
    hand    Hydrapple ex, Poke Pad         hand    16 CARDS
    prizes  5 left                         prizes  4 left
    the Last-Ditch prompt offers: Lillie's x2, **Boss's Orders**,
    Lana's Aid, **Xerosic's Machinations**

The fetch took Boss's Orders. The turn then gusted the benched Fezandipiti ex
and knocked it out for two prizes (5 -> 3), which reads as a good turn and is
not: the opponent ended it holding SIXTEEN cards, so Powerful Hand (20 x card in
their hand) answered for 320 -- more than any body we own -- and took the
Ogerpon ex that was carrying six energies. Two prizes for two prizes, and the
side that lost six turns of charging was ours.

The gust also SAVED the threat. Boss's switches their active out; the Alakazam
went to the bench and came back untouched, and our attack that turn was already
doing 240 to it where it stood. The line the fetch gave up was: cap their hand
to three, attack the active Alakazam, knock it out. One prize instead of two,
and the deck that does 320 a turn is left with no attacker and no hand.

Why no existing rule caught it. The PLAY scorer has known since step 85 of this
same game that vs Alakazam the cap beats any gust that does not win outright:
`alakazam_priority_over_boss` scores Xerosic 7000 over BOSS_SCORE_GUST_2PRIZE
6800. But that rule can only speak once BOTH cards are in hand. Here they were
both still in the deck and it was the FETCH that chose which one would ever
arrive -- and the fetch ladder ordered them the other way round, `winning_boss`
1300 over `xerosic_alakazam` 1260. A search that hand-picks the card the play
scorer would then refuse to play first is a hole no amount of tuning on the play
side can close.

Rule: **in the Last-Ditch fetch, vs Alakazam with a fat opposing hand, Xerosic's
Machinations outranks a Boss's Orders that does not WIN the game this turn.**
The exemption is the same one the play scorer already carries: a gust that ends
the game still rules (`alakazam_yields_to_winning_gust` there,
`not c.win_via_boss` here).

The guards are inherited, not new: the rule fires exactly where
`xerosic_alakazam` fires -- an Alakazam opponent, their hand at 6+ (Powerful
Hand 120+), and either a hand left to play or an attacker already settled. It
cannot reach any other matchup, and it cannot reach a turn where the cap was not
already the fetch's second choice.

Implementation: the rule `xerosic_priority_over_boss` in
`_RULES_MEOWTH_FETCH` (`ptcg/decision/meowth.py`, and its twin in `main.py`,
which is the list the pre-bench prediction resolves).
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
            / "alakazam_t6_the_cap_over_the_gust_step62.json")
_PLAY_FIXTURE = (ROOT / "tests" / "fixtures"
                 / "alakazam_t6_the_cap_is_played_step66.json")

BOSS = m.Boss_Orders
XEROSIC = m.Xerosic_Machinations
LILLIE = m.Lillie_Determination
LANAS = m.Lanas_Aid
OGERPON = m.Teal_Mask_Ogerpon_ex
MEOWTH = m.Meowth_ex
FEZANDIPITI = m.Fezandipiti_ex
ALAKAZAM = m.Alakazam_ex


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    yield
    m._init_cards_tracking()


def _obs(fixture=_FIXTURE):
    return copy.deepcopy(json.load(open(fixture, encoding="utf-8"))["observation"])


def _offered(obs):
    """The card ids the Last-Ditch prompt is offering, in option order."""
    deck = obs["select"]["deck"]
    return [deck[o["index"]]["id"] for o in obs["select"]["option"]]


def _idx_fetch(obs, card_id):
    ids = _offered(obs)
    return ids.index(card_id) if card_id in ids else -1


def _ctx(card_id, **kw):
    """A candidate of the fetch on the board of the record.

    Defaults are the record's: an Alakazam opponent at 16 cards, our Ogerpon ex
    settled as the attacker, a gust worth two prizes waiting on their bench and
    no gust that wins the game.
    """
    field = dict(win_via_boss=False, gust2_via_boss=True, deny_evo_via_boss=False,
                 devel_lillie=False, alakazam=True, op_hand_count=16,
                 hand_size=2, strong_attacker=True, active_cant_attack=False,
                 first_turn=False, lillie_alcanzable=True)
    field.update(kw)
    return m._CtxMeowthFetch(
        card_id, 0, {}, {}, field["hand_size"], field["strong_attacker"],
        field["op_hand_count"], field["active_cant_attack"],
        field["win_via_boss"], field["gust2_via_boss"],
        field["deny_evo_via_boss"], field["devel_lillie"], field["alakazam"],
        field["first_turn"], field["lillie_alcanzable"])


def _score(card_id, **kw):
    value, _ = m._resolve_rules(m._RULES_MEOWTH_FETCH, [], _ctx(card_id, **kw), 50)
    return value


# ---------------------------------------------------------------------------
# 1. The record: the scenario, and then the decision
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_last_ditch_prompt_of_the_record():
    o = _obs()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    op = cur["players"][1 - cur["yourIndex"]]

    assert o["select"]["effect"]["id"] == MEOWTH, (
        "el escenario es el prompt del Last-Ditch Catch del Meowth ex")
    assert cur["supporterPlayed"] is False, "el Supporter del turno sigue libre"
    assert op["handCount"] == 16, (
        "mano rival de 16 cartas: Powerful Hand pega 320")
    assert op["active"][0]["id"] == ALAKAZAM and op["active"][0]["hp"] == 140
    assert any(p["id"] == FEZANDIPITI for p in op["bench"]), (
        "el ex de 2 premios que el gusteo se llevo sigue en su banca")
    assert mine["active"][0]["id"] == OGERPON, "atacante ya montado"
    assert len(mine["prize"]) == 5 and len(op["prize"]) == 4, (
        "vamos por detras en premios: 5 contra 4")
    assert BOSS in _offered(o) and XEROSIC in _offered(o), (
        "el prompt ofrecia AMBAS cartas: el menu mide la prioridad")


def test_the_fetch_brings_the_xerosic_not_the_boss():
    """The regression of the record: `winning_boss` scored 1300 and outbid the
    1260 of `xerosic_alakazam`."""
    o = _obs()
    assert m.agent(o) == [_idx_fetch(o, XEROSIC)], (
        "con mano rival de 16 y Alakazam enfrente, el Last-Ditch trae el tope "
        "(Xerosic's Machinations), no el gusteo de 2 premios")


def test_the_fetched_xerosic_is_played_the_same_turn():
    """What the fetch brings has to be usable TODAY -- otherwise the Meowth ex
    was a two-prize body given away for a card that sleeps in hand.

    The second fixture is step 66 of the same record -- the menu where the turn
    plays the Supporter it fetched, with the attack still on the table -- and
    the ONE edit that makes it the counterfactual: the card the Last-Ditch
    brought is a Xerosic's Machinations instead of the Boss's Orders. Everything
    else is the recorded board.
    """
    o = _obs(_PLAY_FIXTURE)
    cur = o["current"]
    hand = cur["players"][cur["yourIndex"]]["hand"]
    idx = next(i for i, op in enumerate(o["select"]["option"])
               if op.get("type") == int(m.OptionType.PLAY)
               and hand[op["index"]]["id"] == XEROSIC)
    assert cur["supporterPlayed"] is False
    assert m.agent(o) == [idx], (
        "el Xerosic recien buscado se juega este mismo turno: capar 16 cartas "
        "es lo que baja Powerful Hand de 320 a 60")


# ---------------------------------------------------------------------------
# 2. The band: what the new rule beats and what still beats it
# ---------------------------------------------------------------------------

def test_the_cap_beats_the_two_prize_gust():
    assert _score(XEROSIC) > _score(BOSS) > 0, (
        "el tope gana al gusteo de 2 premios, pero el gusteo sigue siendo una "
        "opcion valida (no es un veto)")


def test_the_cap_beats_the_deny_evo_gust():
    """`boss_deny_evo` (1280) is the other gust band, and the play scorer's
    `alakazam_priority_over_boss` steps over it too."""
    assert (_score(XEROSIC, gust2_via_boss=False, deny_evo_via_boss=True)
            > _score(BOSS, gust2_via_boss=False, deny_evo_via_boss=True))


def test_the_gust_that_wins_the_game_still_rules():
    """The one exemption, the same as the play scorer's
    `alakazam_yields_to_winning_gust`: with the game endable this turn the cap
    is worth nothing."""
    assert (_score(BOSS, win_via_boss=True)
            > _score(XEROSIC, win_via_boss=True))


def test_a_copy_already_in_hand_is_still_not_worth_fetching():
    """`copy_already_in_hand` goes ahead of the whole matchup ladder: bringing a
    second Xerosic while holding one adds nothing, because only one Supporter
    is played per turn."""
    ctx = _ctx(XEROSIC)
    ctx.hand = {XEROSIC: 1}
    value, _ = m._resolve_rules(m._RULES_MEOWTH_FETCH, [], ctx, 50)
    assert value == 40


def test_our_first_turn_still_belongs_to_lillie():
    """`first_turn_lillie_only` / `first_turn_rest_yields_to_lillie` also go
    ahead of it: on turn 1 the cap is premature against any deck
    (`records/.../alakazam_t1_going_second_lillie_over_xerosic_step11.json`)."""
    assert (_score(LILLIE, first_turn=True)
            > _score(XEROSIC, first_turn=True))


# ---------------------------------------------------------------------------
# 3. The boundaries: where the rule may not reach
# ---------------------------------------------------------------------------

def test_outside_the_alakazam_matchup_the_gust_keeps_the_fetch():
    """No Powerful Hand, no reason to cap: against every other deck a benched
    ex worth two prizes is what the Last-Ditch goes for."""
    assert (_score(BOSS, alakazam=False)
            > _score(XEROSIC, alakazam=False))


@pytest.mark.parametrize("op_hand", [3, 4, 5])
def test_a_small_opposing_hand_does_not_buy_the_cap(op_hand):
    """The inherited guard: below 6 cards the cap takes little away and
    `xerosic_alakazam` does not fire either."""
    assert (_score(BOSS, op_hand_count=op_hand)
            > _score(XEROSIC, op_hand_count=op_hand))


def test_with_no_attacker_and_no_hand_the_gust_keeps_the_fetch():
    """The other inherited guard: with nothing settled to attack with AND an
    empty hand, `xerosic_alakazam` never fired, and the new rule carries the
    same condition so it cannot fire where that one would not."""
    assert (_score(BOSS, strong_attacker=False, hand_size=2)
            > _score(XEROSIC, strong_attacker=False, hand_size=2))


def test_the_prediction_and_the_real_fetch_score_the_same():
    """`main._RULES_MEOWTH_FETCH` is the list the pre-bench prediction resolves
    and `ptcg.decision.meowth._RULES_MEOWTH_FETCH` the one the prompt resolves.
    They are two objects: if only one of them learns the rule, the agent decides
    to bench the Meowth for a card its own prompt will not bring."""
    import ptcg.decision.meowth as pkg
    names = lambda rules: [r.name for r in rules]
    assert names(m._RULES_MEOWTH_FETCH) == names(pkg._RULES_MEOWTH_FETCH)
    ctx = _ctx(XEROSIC)
    assert (m._resolve_rules(m._RULES_MEOWTH_FETCH, [], ctx, 50)
            == m._resolve_rules(pkg._RULES_MEOWTH_FETCH, [], ctx, 50))
