"""The coin of the previous turn decides whether there is anything to attack.

Scenario (user, episode 90325863, turn 8 vs a Dragapult / Azumarill deck, WON
in spite of this). Their turn 7 ends with a Marill in the active spot
declaring Hide:

    {"attackId": 1382, "cardId": 961, "serial": 94, "type": 15}
    {"head": true, "type": 22}

Heads. "During your opponent's next turn, prevent all damage from and effects
of attacks done to this Pokemon." Our turn 8 opens at step 87 with:

    US                                       RIVAL
    active  Hydrapple ex 330/330  2e         active  Marill 70/70  1e   HIDDEN
    bench   Teal Mask Ogerpon ex  4e         bench   Cornerstone Mask Ogerpon ex
            Meganium              2e                 Dragapult ex 320  2e
            Dipplin                                  Azumarill 120
            Chikorita                                Drakloak 90
            Tapu Bulu
    hand    Lillie's, Lillie's, Meowth ex    (bench FULL, 5/5)

What the agent played: Lillie's -- which drew the Boss's Orders, one card too
late, with the turn's only Supporter already spent -- an energy onto the
benched Tapu Bulu, and then Syrup Storm at the Marill. The record scores that
attack itself, at step 99:

    {"cardId": 961, "putDamageCounter": false, "type": 16, "value": 0}

Zero. Turn 8 produced nothing at all. Two turns later the same Marill flipped
Hide again, came up TAILS, and the agent immediately found the line the coin
had been hiding: Boss's Orders on their Dragapult ex, Syrup Storm, two prizes.

Why the turn was invisible: the machinery for this already existed. The
`op_active_dodge_immune` detector vetoes the useless attack, redirects Boss's
Orders to the bench (`_boss_dodge_redirect`) and switches on the Meowth ex ->
Last-Ditch Catch -> Boss's -> gust engine. It was written against ONE card,
Hop's Phantump, because that is the deck the loss it was built for came from.
The effect belongs to the ATTACK, not to the card: twelve attacks in the
environment carry that exact sentence -- Hide, Splashing Dodge, Dig, Fly,
Dive, Agility, Undulate, Swift Flight -- and eleven of them were invisible.

Coverage:
  * the record's own turn, replayed in sequence: the coin is read, the attack
    that resolves for zero is no longer chosen;
  * the tails branch of the SAME record: nothing is switched on, the turn that
    won the game is untouched;
  * the attack table itself, re-derived from the environment's texts, so a new
    card with the same effect fails here instead of silently going unread;
  * the routes to a Boss's Orders when it is NOT in hand, which is what the
    turn actually needed: Meowth ex from hand, Ultra Ball, Night Stretcher;
  * the boundaries: with the Boss's in hand no body is spent to fetch it, with
    a full bench nothing fires, and with the coin on tails every one of these
    routes stays shut.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from cg.api import AreaType, CardType, OptionType, all_attack, all_card_data
from state_builder import Scenario, pk

HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
MEOWTH = m.Meowth_ex
BOSS = m.Boss_Orders
LILLIE = m.Lillie_Determination
ULTRA_BALL = m.Ultra_Ball
NIGHT_STRETCHER = m.Night_Stretcher
GRASS = m.Basic_Grass_Energy
APPLIN = m.Applin
DIPPLIN = m.Dipplin
CHIKORITA = m.Chikorita
TAPU = m.Tapu_Bulu
MEGANIUM = m.Meganium
BAYLEEF = m.Bayleef

OP_MARILL = m.Marill                 # 961, the body that hides
OP_DRAKLOAK = 120                    # 90 HP on their bench: what the gust is for
OP_DRAGAPULT = 121

HEADS_FIXTURE = (ROOT / "tests" / "fixtures"
                 / "marill_turn8_the_coin_came_up_heads.json")
TAILS_FIXTURE = (ROOT / "tests" / "fixtures"
                 / "marill_step99_the_coin_came_up_tails.json")


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m._prev_op_prize = 6
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _heads_turn():
    """The three observations of OUR turn 8, in the order the record has them."""
    with open(HEADS_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observations"]


def _tails_step99():
    with open(TAILS_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _kind(obs, choice):
    """('ATTACK', attackId) / ('PLAY', card_id) / ('ATTACH'|'END', None)."""
    if not choice:
        return ("END", None)
    o = obs["select"]["option"][choice[0]]
    t = o["type"]
    if t == int(OptionType.ATTACK):
        return ("ATTACK", o["attackId"])
    if t == int(OptionType.PLAY):
        mine = obs["current"]["players"][obs["current"]["yourIndex"]]
        return ("PLAY", mine["hand"][o["index"]]["id"])
    if t == int(OptionType.ATTACH):
        return ("ATTACH", None)
    if t == int(OptionType.END):
        return ("END", None)
    return (t, None)


# ---------------------------------------------------------------------------
# 1. The record: without this board the test measures nothing
# ---------------------------------------------------------------------------

def test_the_board_is_the_records_one():
    steps = _heads_turn()
    assert [o["step"] for o in steps] == [87, 88, 89]

    first = steps[0]
    cur = first["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert cur["turn"] == 8
    assert mine["active"][0]["id"] == HYDRAPPLE
    assert len(mine["bench"]) == 5, "the bench is FULL: no Meowth ex can go down"
    assert sorted(c["id"] for c in mine["hand"]) == sorted([LILLIE, LILLIE, MEOWTH])
    assert BOSS not in [c["id"] for c in mine["hand"]], (
        "the Boss's Orders is still in the deck -- that is the whole problem")

    hidden = theirs["active"][0]
    assert hidden["id"] == OP_MARILL and hidden["hp"] == 70
    assert [b["id"] for b in theirs["bench"]] == [117, 121, 315, 120], (
        "their bench is attackable: the gust has somewhere to go")

    # The coin, in the logs of the turn's first observation.
    logs = [l for l in first["logs"] if l.get("type") in (15, 22)]
    assert logs[-2:] == [
        {"attackId": m.Hide_Marill_Atk, "cardId": OP_MARILL,
         "playerIndex": 1, "serial": 94, "type": 15},
        {"head": True, "playerIndex": 1, "type": 22},
    ]

    # And the record's own verdict on the attack that was played anyway.
    zero = [l for l in _tails_step99()["logs"]
            if l.get("type") == 16 and l.get("cardId") == OP_MARILL]
    assert zero and zero[0]["value"] == 0, (
        "the simulator scored our Syrup Storm on the hidden Marill at zero")


def test_the_syrup_storm_that_resolves_for_zero_is_not_played():
    """The turn replayed in sequence, which is how the agent really sees it:
    the coin is only in the logs of the FIRST call, and the flag has to survive
    to the third one, where the attack option appears."""
    choices = []
    for obs in _heads_turn():
        choices.append(_kind(obs, m.agent(obs)))

    assert m.AGENT_STATE._dodge_immune_serial == 94
    assert m.AGENT_STATE._dodge_immune_turn == 8

    assert ("ATTACK", 195) not in choices, (
        "Syrup Storm on a Marill hidden by Hide does zero damage and ends the "
        f"turn: {choices}")


def test_on_tails_nothing_is_switched_on():
    """The same Marill, the same attack, two turns later -- and the coin came
    up TAILS. The record's winning line (Boss's Orders on their Dragapult ex)
    starts here and must not be touched."""
    obs = _tails_step99()
    assert obs["current"]["turn"] == 10
    m.agent(obs)
    assert m.AGENT_STATE._dodge_immune_serial is None, (
        "tails grants no protection: the flag must not be armed")


# ---------------------------------------------------------------------------
# 2. The table: what the detector reads, and the control that keeps it honest
# ---------------------------------------------------------------------------

_DODGE_TEXT = "prevent all damage from and effects of attacks done to this"


def test_the_attack_table_is_the_environments_and_stays_that_way():
    """`COIN_DODGE_ATTACK_IDS` is a literal so it can be read; this re-derives
    it from the environment's own attack texts. If a set adds another card with
    this effect, THIS is what fails -- not a game."""
    derived = {
        a.attackId for a in all_attack()
        if _DODGE_TEXT in (getattr(a, "text", "") or "").lower()
        and "flip a coin" in (getattr(a, "text", "") or "").lower()
    }
    assert derived == set(m.COIN_DODGE_ATTACK_IDS)
    # The two that matter here, by name, so the ids are not just numbers.
    by_id = {a.attackId: a.name for a in all_attack()}
    assert by_id[m.Hide_Marill_Atk] == "Hide"
    assert by_id[m.Splashing_Dodge_Atk] == "Splashing Dodge"
    assert m.Hide_Marill_Atk in m.COIN_DODGE_ATTACK_IDS
    assert m.Splashing_Dodge_Atk in m.COIN_DODGE_ATTACK_IDS, (
        "the case the detector was originally written for must survive")


def test_the_hidden_body_is_the_one_that_flipped_and_it_is_the_marill():
    cards = {c.cardId: c for c in all_card_data()}
    assert cards[OP_MARILL].name == "Marill"
    assert m.Hide_Marill_Atk in cards[OP_MARILL].attacks
    assert cards[m.Azumarill].name == "Azumarill", (
        "the line the Marill evolves into: it is not what hides, but it is "
        "what the gust is competing with on their bench")


# ---------------------------------------------------------------------------
# 3. The routes to a Boss's Orders when it is NOT in hand
# ---------------------------------------------------------------------------

def _hidden_board(hand, heads=True, bench=None, discard=(), turn=8):
    """The record's shape with the bench parameterised.

    The Marill is hidden by the logs, exactly as the simulator delivers them:
    the ATTACK entry gives the serial, the COIN_FLIP entry right after gives
    the side.
    """
    sc = (Scenario(turn=turn, step=1, tac=1, first_player=1)
          .my_active(pk(HYDRAPPLE, pre_evo=[APPLIN, DIPPLIN],
                        energies=2, fisicas=2))
          .my_bench(*(bench if bench is not None
                      else [pk(OGERPON, energies=4, fisicas=4)]))
          .my_hand(*hand)
          .my_discard(*discard)
          .op_active(pk(OP_MARILL, hp=70, max_hp=70, energies=1))
          .op_bench(pk(OP_DRAKLOAK, hp=90, max_hp=90),
                    pk(OP_DRAGAPULT, hp=320, max_hp=320, energies=2))
          .op_zones(hand=4, deck=27, prizes=4))
    obs = sc.menu_hand(with_attack=True).build()
    serial = obs["current"]["players"][1]["active"][0]["serial"]
    obs["logs"] = [
        {"attackId": m.Hide_Marill_Atk, "cardId": OP_MARILL,
         "playerIndex": 1, "serial": serial, "type": 15},
        {"head": heads, "playerIndex": 1, "type": 22},
    ]
    return obs


_FULL_BENCH = [pk(OGERPON, energies=4, fisicas=4),
               pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF], energies=2, fisicas=2),
               pk(DIPPLIN, pre_evo=[APPLIN]),
               pk(CHIKORITA),
               pk(TAPU)]


def test_the_meowth_goes_down_to_dig_out_the_boss_the_hand_does_not_have():
    """The line the record's turn could not play only because its bench was
    full. Meowth ex is benched, its Last-Ditch Catch brings the Boss's Orders
    from the deck and the Supporter slot is still there to play it."""
    obs = _hidden_board([MEOWTH, LILLIE])
    assert _kind(obs, m.agent(obs)) == ("PLAY", MEOWTH), (
        "with their active untouchable, the Lillie's in hand answers nothing: "
        "it draws cards at a body no attack of ours can reach")


def test_on_tails_the_lillie_keeps_the_turn():
    """The control for the rule above, and the one that says it is the COIN
    doing the work: the same board, the same hand, the same everything -- only
    the flip came up tails, so the Hydrapple ex can attack and the Meowth ex is
    a two-prize body with nothing to buy."""
    obs = _hidden_board([MEOWTH, LILLIE], heads=False)
    assert _kind(obs, m.agent(obs)) != ("PLAY", MEOWTH)


def test_a_boss_already_in_hand_is_played_and_no_body_is_spent():
    obs = _hidden_board([BOSS, LILLIE])
    assert _kind(obs, m.agent(obs)) == ("PLAY", BOSS), (
        "the gust is in hand: the Meowth engine exists to reach one, not to "
        "duplicate it")


def test_with_a_full_bench_there_is_no_engine_and_the_dig_is_all_that_is_left():
    """The record's own board. There is nowhere to put the Meowth ex, so
    Lillie's -- digging for tomorrow -- is what is left. The turn is still lost;
    what must not happen is the attack for zero on top of it."""
    obs = _hidden_board([MEOWTH, LILLIE], bench=_FULL_BENCH)
    assert _kind(obs, m.agent(obs)) == ("PLAY", LILLIE)


def test_the_hidden_active_is_not_a_ready_attacker_and_the_attack_is_vetoed():
    obs = _hidden_board([LILLIE])
    options = obs["select"]["option"]
    attacks = [i for i, o in enumerate(options)
               if o["type"] == int(OptionType.ATTACK)]
    assert attacks, "the board must really offer the attack, or nothing is measured"
    assert m.agent(obs)[0] not in attacks


# --- the two searches ------------------------------------------------------

def _ultra_ball_fetch(heads=True):
    """The Ultra Ball's deck-search prompt over a deck holding both a Meowth ex
    and the pieces it usually loses to."""
    sc = (Scenario(turn=8, step=1, tac=2, first_player=1)
          .my_active(pk(HYDRAPPLE, pre_evo=[APPLIN, DIPPLIN],
                        energies=2, fisicas=2))
          .my_bench(pk(OGERPON, energies=4, fisicas=4))
          .my_hand(LILLIE)
          .op_active(pk(OP_MARILL, hp=70, max_hp=70, energies=1))
          .op_bench(pk(OP_DRAKLOAK, hp=90, max_hp=90),
                    pk(OP_DRAGAPULT, hp=320, max_hp=320, energies=2))
          .op_zones(hand=4, deck=27, prizes=4)
          .deck(MEOWTH, BOSS, TAPU, CHIKORITA, APPLIN)
          .fetch_ultra_ball()
          .rest_to_discard())
    obs = sc.build()
    serial = obs["current"]["players"][1]["active"][0]["serial"]
    obs["logs"] = [
        {"attackId": m.Hide_Marill_Atk, "cardId": OP_MARILL,
         "playerIndex": 1, "serial": serial, "type": 15},
        {"head": heads, "playerIndex": 1, "type": 22},
    ]
    return obs


def _fetched(obs, choice):
    o = obs["select"]["option"][choice[0]]
    return obs["select"]["deck"][o["index"]]["id"]


def test_the_ultra_ball_digs_out_the_meowth_that_reaches_the_boss():
    obs = _ultra_ball_fetch()
    assert _fetched(obs, m.agent(obs)) == MEOWTH, (
        "the Ultra Ball cannot fetch the Boss's Orders (a Supporter): the body "
        "it can fetch is the one whose ability reaches it")


def test_on_tails_the_ultra_ball_does_not_chase_the_meowth():
    obs = _ultra_ball_fetch(heads=False)
    assert _fetched(obs, m.agent(obs)) != MEOWTH


def _night_stretcher_fetch(heads=True):
    """The Night Stretcher's recovery prompt with the Meowth ex in the discard
    -- the third route to the Boss's, and the only one left once the deck's
    copies of Meowth ex are gone."""
    sc = (Scenario(turn=8, step=1, tac=2, first_player=1)
          .my_active(pk(HYDRAPPLE, pre_evo=[APPLIN, DIPPLIN],
                        energies=2, fisicas=2))
          .my_bench(pk(OGERPON, energies=4, fisicas=4))
          .my_hand(LILLIE)
          .my_discard(MEOWTH, TAPU, CHIKORITA, GRASS)
          .op_active(pk(OP_MARILL, hp=70, max_hp=70, energies=1))
          .op_bench(pk(OP_DRAKLOAK, hp=90, max_hp=90),
                    pk(OP_DRAGAPULT, hp=320, max_hp=320, energies=2))
          .op_zones(hand=4, deck=27, prizes=4))
    obs = sc.fetch_discard(NIGHT_STRETCHER).build()
    serial = obs["current"]["players"][1]["active"][0]["serial"]
    obs["logs"] = [
        {"attackId": m.Hide_Marill_Atk, "cardId": OP_MARILL,
         "playerIndex": 1, "serial": serial, "type": 15},
        {"head": heads, "playerIndex": 1, "type": 22},
    ]
    return obs


def _recovered(obs, choice):
    mine = obs["current"]["players"][0]
    o = obs["select"]["option"][choice[0]]
    return mine["discard"][o["index"]]["id"]


def test_the_night_stretcher_brings_the_meowth_back_for_the_boss():
    obs = _night_stretcher_fetch()
    assert _recovered(obs, m.agent(obs)) == MEOWTH


def test_on_tails_the_night_stretcher_recovers_something_else():
    obs = _night_stretcher_fetch(heads=False)
    assert _recovered(obs, m.agent(obs)) != MEOWTH


# ---------------------------------------------------------------------------
# 4. The readings themselves, on the helpers
# ---------------------------------------------------------------------------

def test_the_fetch_points_at_the_boss_when_the_active_cannot_be_touched():
    """`_RULES_MEOWTH_FETCH` decides which Supporter the Last-Ditch Catch
    brings. An untouchable active makes `strong_attacker` false, which is what
    fires the `no_attacker*` rules and caps every candidate that is not a
    Lillie's -- the Boss's, the answer, was being punished by the very fact
    that created the problem. In the record it came out behind Dawn."""
    from ptcg.decision.meowth import _CtxMeowthFetch

    def _value(card_id, flag):
        ctx = _CtxMeowthFetch(
            card_id, {BOSS: 500, m.Dawn: 700}.get(card_id, 0),
            {LILLIE: 1}, {}, 3, False, 4, False,
            False, False, False, False, False, False, False, flag)
        return m._resolve_rules(m._RULES_MEOWTH_FETCH, [], ctx, 50)

    blind, blind_trace = _value(BOSS, False)
    assert (blind, blind_trace) == (200, ["no_attacker_medium_hand=200"]), (
        "the control: with their active untouchable there is no ready "
        "attacker, so the generic cap fires and buries the Boss's at the "
        "level of every other candidate")
    assert _value(m.Dawn, False)[0] == blind, (
        "tied with Dawn at the cap -- which is how the record's fetch ended "
        "up choosing Dawn")

    seeing, seeing_trace = _value(BOSS, True)
    assert (seeing, seeing_trace) == (
        1270, ["boss_beats_the_untouchable_active=1270"])
    assert _value(m.Dawn, True)[0] == 200, "only the Boss's is lifted"
    assert _value(LILLIE, True)[0] == 40, (
        "and the copy already in hand still yields, flag or no flag")


def test_the_boss_refinements_are_blind_while_the_card_is_in_the_deck():
    """The reason the Meowth had to be exempted from `_meowth_fetch_loses_the
    _turn` rather than out-scored. The `_bo_*` refinements --
    `_boss_dodge_redirect`, the bench-prize reads, `_boss_win_via_bench` -- are
    computed inside `if hand_counts[Boss_Orders] >= 1`, so `_supp_play_score`
    for a Boss's still in the deck does not come back low: it comes back not
    computed at all (`no_value`, -1)."""
    src = (ROOT / "ptcg" / "turn" / "supporters.py").read_text(encoding="utf-8")
    gate = "if (hand_counts.get(Boss_Orders, 0) >= 1"
    assert gate in src
    assert src.index(gate) < src.index("_boss_dodge_redirect"), (
        "if the refinements ever stop being gated on the card being in hand, "
        "the exemption in `_meowth_fetch_loses_the_turn` should be revisited")


def test_the_base_band_is_not_gated_and_the_crustle_engine_is_alive():
    """The other half of the same reading, and the one that is easy to get
    wrong: the BASE band of `values[Boss_Orders]` -- the `if/elif` chain by
    matchup -- is NOT behind that gate. It reaches 900+ only on branches that
    name an opposing deck (990 the Crustle gust, 980 Drednaw, 950 the Tapu
    line), which is precisely why `_um_boss_engine_vs_crustle` can ask for
    `>= 900` with the Boss's still in the deck and still fire, and why
    `_um_boss_engine_vs_untouchable` must NOT ask for it: a coin dodge has no
    branch of its own and falls to the generic tail (650 / 500 / 0).

    Measured on a real Crustle board rather than argued: 990, with an empty
    hand of Boss's.
    """
    import ptcg.decision.ultra_ball as ub

    seen = {}
    rule = ub._RULES_UB_MEOWTH[0]
    original = rule.when

    def _spy(c):
        seen["supp"] = c.supp_values.get(BOSS, 0)
        seen["hand"] = c.hand.get(BOSS, 0)
        seen["crustle_engine"] = ub._um_boss_engine_vs_crustle(c)
        return original(c)

    CRUSTLE, DWEBBLE = m.Crustle_Grass, m.Dwebble_Grass
    obs = (Scenario(turn=8, step=1, tac=2, first_player=1)
           .my_active(pk(HYDRAPPLE, pre_evo=[APPLIN, DIPPLIN],
                         energies=2, fisicas=2))
           .my_bench(pk(OGERPON, energies=4, fisicas=4))
           .my_hand(LILLIE)
           .op_active(pk(CRUSTLE, hp=150, max_hp=150, energies=2,
                         pre_evo=[DWEBBLE]))
           .op_bench(pk(DWEBBLE, hp=70, max_hp=70),
                     pk(CRUSTLE, hp=150, max_hp=150, pre_evo=[DWEBBLE]))
           .op_zones(hand=4, deck=27, prizes=4)
           .deck(MEOWTH, BOSS, TAPU, CHIKORITA, APPLIN)
           .fetch_ultra_ball()
           .rest_to_discard()
           .build())

    rule.when = _spy
    try:
        choice = m.agent(obs)
    finally:
        rule.when = original

    assert seen["hand"] == 0, "the Boss's is in the deck, not in hand"
    assert seen["supp"] == m.BOSS_PRIORITY_CRUSTLE_GUST == 990
    assert seen["crustle_engine"] is True, (
        "`_um_boss_engine_vs_crustle` is NOT dead code: the Crustle branch of "
        "the base band clears its own >= 900 gate")
    # And the outcome the two engines agree on: dig out the Meowth ex.
    assert _fetched(obs, choice) == MEOWTH


def test_the_gust_target_is_a_body_we_can_actually_reach():
    """`_boss_gust_immune_active` is what every route above hangs off. It asks
    for a bench body that does not reproduce the immunity -- so a bench of
    nothing but ability-immune walls switches all of it back off."""
    obs = _hidden_board([BOSS, LILLIE])
    st = m.to_observation_class(obs).current
    theirs = st.players[1]
    assert any(b is not None and b.id not in m.ABILITY_IMMUNE_IDS
               for b in theirs.bench)
