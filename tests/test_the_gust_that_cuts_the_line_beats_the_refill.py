"""The gust that cuts their attacking line is the attack, not a Supporter to weigh.

Scenario (user, episode 90333949, turn 4, step 47 vs Archaludon, LOST):

    US                                        RIVAL
    active  Teal Mask Ogerpon ex 110/210 3e   active  Cinderace 160/160  1e
    bench   Bayleef 110                       bench   Duraludon 130/130  4e
            Fezandipiti ex 210
            Applin 40  1e
            Meowth ex 170
            Meowth ex 170
    hand    Night Stretcher, Boss's Orders, Lillie's Determination, Grass
    supporter slot free · energy already attached · prizes 6-6

Cinderace is not their attacker: Turbo Flare searches three Basic Energy and
attaches them TO THEIR BENCH -- it is the engine that was charging the Duraludon,
and Duraludon evolves into Archaludon ex, the deck's real attacker (2 prizes).
The whole turn was there: Boss's on the Duraludon, and Myriad Leaf Shower knocks
it out. What the agent played was Lillie's Determination, which shuffles the
hand -- Boss's included -- back into the deck, and then attacked the Cinderace
for 150 into 160 HP: no prize, and the Duraludon evolved.

The arithmetic is the whole story. Myriad Leaf Shower does "30 more damage for
each Energy attached to BOTH Active Pokemon", and the target of a gust BECOMES
the active:

    vs the Cinderace  30 + 30 x (3 ours + 1 theirs)          = 150 < 160  no KO
    vs the Duraludon  30 + 30 x (3 ours + 4 theirs) - 30 Metal = 210 > 130  KO

Two independent rules had to give way, and each one hid the other:

  1. `_boss_dmg_to`, the damage model the Boss's VALUE layer uses, carried an
     inline copy of that attack that read only OUR energy (30 + 30 x 3 = 120).
     The Duraludon's KO did not exist for it, so no bench prize beat the active
     (`_bo_bench_prize_beats_active`) and the chip rule -- "the attack leaves the
     active under 100 HP, attacking is enough" -- cancelled the Boss's to 0 and
     zeroed `_boss_prize_rank`. The central evaluator `_attacker_base_damage` had
     read the attack right for six records; this copy had drifted from it. The
     same turn proves they disagreed: `boss_ko_threat_preevo`, computed with the
     central one, was True while the value layer said the Boss's was worth 0.

  2. With the value fixed the Boss's scored 5220 and Lillie's vetoed ITSELF for
     exactly this reason (`yields_to_executable_boss`, -1) -- and the Last-Ditch
     commitment resurrected it to 8000. That floor arbitrates between REFILLS
     (Dawn, Lillie's, Lana's, Xerosic: the band it was measured against); Boss's
     is not one, and at 8000 the floor sat above almost its whole ladder, so the
     fetched refill outranked the finisher it had been dug for.

Coverage:
  * the record's board and the two damage readings that decide it;
  * the record's turn, replayed whole (the commitment gets armed at step 39 by
    the Last-Ditch Catch, as in the game): the agent plays Boss's;
  * each fix isolated -- from step 42, with no commitment armed, the damage fix
    alone already flips the decision;
  * the seam of the commitment rule: a gust that takes nothing still yields.
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
from state_builder import C, G, Scenario, pk

OGERPON = m.Teal_Mask_Ogerpon_ex
BOSS = m.Boss_Orders
LILLIE = m.Lillie_Determination
NIGHT_STRETCHER = m.Night_Stretcher
MEOWTH = m.Meowth_ex
APPLIN = m.Applin
XEROSIC = m.Xerosic_Machinations

OP_CINDERACE = 666
OP_DURALUDON = m.Duraludon

_SEQ = (ROOT / "tests" / "fixtures"
        / "archaludon_turn4_the_gust_that_cuts_the_line.json")


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


def _sequence():
    with open(_SEQ, encoding="utf-8") as f:
        return json.load(f)["sequence"]


def _replay(desde=37, hasta=47):
    """Replays OUR frames of the turn in [desde, hasta]; returns (obs, result)."""
    obs = result = None
    for item in _sequence():
        if not (desde <= item["step"] <= hasta):
            continue
        obs = item["observation"]
        result = m.agent(obs)
    return obs, result


def _play_ids(obs):
    """{card id: option index} for every PLAY the menu offers."""
    hand = obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]
    out = {}
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == 7 and o.get("index") is not None:
            out[hand[o["index"]]["id"]] = i
    return out


# ---------------------------------------------------------------------------
# 1. The record: without this board the test measures nothing
# ---------------------------------------------------------------------------

def test_step47_the_board_is_the_records_one():
    obs = _sequence()[-1]["observation"]
    cur = obs["current"]
    assert cur["turn"] == 4 and _sequence()[-1]["step"] == 47
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert cur["supporterPlayed"] is False, "the Supporter slot is still free"
    assert mine["active"][0]["id"] == OGERPON
    assert len(mine["active"][0]["energies"]) == 3, "Myriad Leaf Shower is paid for"
    assert sorted(c["id"] for c in mine["hand"]) == sorted(
        [NIGHT_STRETCHER, BOSS, LILLIE, m.Basic_Grass_Energy])

    assert theirs["active"][0]["id"] == OP_CINDERACE
    assert theirs["active"][0]["hp"] == 160
    assert len(theirs["active"][0]["energies"]) == 1
    # ONE benched body, and it is the pre-evolution of their real attacker.
    assert [p["id"] for p in theirs["bench"]] == [OP_DURALUDON]
    assert theirs["bench"][0]["hp"] == 130
    assert len(theirs["bench"][0]["energies"]) == 4
    assert OP_DURALUDON in m.THREAT_PREEVO_IDS


def test_step47_the_arithmetic_that_decides_the_turn():
    """Myriad Leaf Shower counts BOTH actives: it does not knock out the
    Cinderace and it does knock out the Duraludon it would gust."""
    obs = _sequence()[-1]["observation"]
    cur = obs["current"]
    ours = m.to_observation_class(obs).current.players[cur["yourIndex"]].active[0]
    theirs = m.to_observation_class(obs).current.players[1 - cur["yourIndex"]]
    cinderace, duraludon = theirs.active[0], theirs.bench[0]

    def dmg(target):
        base = m._attacker_base_damage(ours.id, target, len(ours.energies),
                                       grass_scale=len(ours.energies),
                                       teal_self_energy=len(ours.energies),
                                       bench_count=5)
        return m._our_effective_damage(ours, target, base, False, False)

    assert dmg(cinderace) == 150 < cinderace.hp, (
        "attacking the active takes NO prize: that is why the turn is the gust")
    assert dmg(duraludon) >= duraludon.hp, (
        "the gusted Duraludon becomes the active and its 4 energies feed the "
        "attack: it dies even through the Metal resistance")


# ---------------------------------------------------------------------------
# 2. The decision of the record
# ---------------------------------------------------------------------------

def test_step47_plays_boss_orders_not_the_refill():
    obs, result = _replay()
    plays = _play_ids(obs)
    assert BOSS in plays and LILLIE in plays, (
        f"the menu must offer both Supporters: {plays}")
    # The turn armed the commitment by itself, as in the game (Last-Ditch Catch
    # at step 39 fetched the Lillie's). If it were not armed this test would not
    # be measuring the second half of the fix.
    assert m.AGENT_STATE._ld_supp_comprometido == LILLIE

    assert result == [plays[BOSS]], (
        f"the turn is Boss's on the Duraludon (opt {plays[BOSS]}): it takes a "
        f"prize and cuts the Archaludon ex line, while Lillie's "
        f"(opt {plays[LILLIE]}) shuffles the Boss's back into the deck and "
        f"leaves an attack that does 150 into 160 HP; got {result}")


def test_step47_the_gust_is_worth_more_than_attacking_the_active():
    """The score, not just the winner: the gust has to beat the attack on its
    own, or the ordering would be doing the work."""
    obs, _ = _replay()
    plays = _play_ids(obs)
    attack = [i for i, o in enumerate(obs["select"]["option"])
              if o.get("type") == 13]
    assert attack, "the menu offers the attack"
    scores = {}

    _orig = m.finalizar

    def spy(tc):
        scores.update(enumerate(tc.scores))
        return _orig(tc)

    m.finalizar = spy
    try:
        m.agent(obs)
    finally:
        m.finalizar = _orig

    assert scores[plays[BOSS]] >= m.BOSS_SCORE_PRIZE_RANK_BASE, (
        "the gust scores in the band of the branches that have a KO behind them")
    assert scores[plays[BOSS]] > scores[attack[0]]


# ---------------------------------------------------------------------------
# 3. Each fix isolated
# ---------------------------------------------------------------------------

def test_the_damage_fix_alone_flips_it_with_no_commitment():
    """From step 42 the Last-Ditch has not been replayed, so nothing is
    committed: what decides there is only that the Boss's VALUE layer now reads
    the gusted body's energy."""
    obs, result = _replay(desde=42)
    assert m.AGENT_STATE._ld_supp_comprometido == 0, (
        "this sub-sequence must NOT arm the commitment")
    plays = _play_ids(obs)
    assert result == [plays[BOSS]], (
        f"with no commitment in play the fixed damage model already sees the "
        f"KO on the Duraludon and plays Boss's (opt {plays[BOSS]}); got {result}")


def test_the_value_layer_and_the_central_evaluator_agree():
    """The two readings of the same attack, in the same turn. They disagreeing is
    what the record cost: `boss_ko_threat_preevo` (central evaluator) said the
    gust knocks out, and the value layer priced the Boss's at 0."""
    obs, _ = _replay()
    seen = {}
    _orig = m._score_boss_orders_play

    def spy(ctx):
        seen.setdefault("ctx", ctx)
        return _orig(ctx)

    m._score_boss_orders_play = spy
    try:
        m.agent(obs)
    finally:
        m._score_boss_orders_play = _orig

    ctx = seen["ctx"]
    assert ctx.boss_ko_threat_preevo, "the central evaluator sees the gust's KO"
    assert ctx.boss_prize_rank >= 1, (
        "and the value layer no longer cancels it as 'attacking is enough'")


# ---------------------------------------------------------------------------
# 4. The seam of the commitment: a gust that takes NOTHING still yields
# ---------------------------------------------------------------------------

def _synthetic_menu(hand):
    """A neutral mid-game board: nothing on their bench is knocked out, so any
    Boss's here is a gust with no prize behind it."""
    return (Scenario(turn=8, step=60, tac=4)
            .my_active(pk(OGERPON, energies=[G, G]))
            .my_bench(pk(MEOWTH, aparecio=True), APPLIN)
            .my_hand(*hand)
            .op_active(pk(917, energies=[C]))
            .op_bench(pk(843, hp=70, max_hp=70))
            .op_zones(hand=5, deck=30, prizes=5)
            .menu_hand()
            .build())


def test_a_gust_that_takes_nothing_still_yields_to_the_commitment():
    """The rule only lifts the floor for the band of the ladder that has a KO
    behind it. Below it the Boss's takes no prize and the refill, already paid
    for with a 2-prize body, keeps the slot."""
    obs = _synthetic_menu([BOSS, XEROSIC])
    plays = _play_ids(obs)
    assert BOSS in plays and XEROSIC in plays

    m.agent(obs)                       # consumes the per-turn reset
    m.AGENT_STATE._ld_supp_comprometido = XEROSIC
    result = m.agent(obs)

    scores = {}
    _orig = m.finalizar

    def spy(tc):
        scores.update(enumerate(tc.scores))
        return _orig(tc)

    m.finalizar = spy
    try:
        m.agent(obs)
    finally:
        m.finalizar = _orig

    assert scores[plays[BOSS]] < m.BOSS_SCORE_PRIZE_RANK_BASE, (
        "the control is only worth anything if this gust really takes nothing")
    assert result == [plays[XEROSIC]], (
        f"the committed Supporter keeps the slot (opt {plays[XEROSIC]}); "
        f"got {result}")
