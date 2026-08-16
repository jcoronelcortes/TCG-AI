"""At their match point the front spot goes to the body that absorbs the most.

Scenario (`records/registro_011_pasos_115_hasta_130.json`, step 130, turn 11,
LOST vs Alakazam -- episode 91532527). Four prizes to ONE, their Powerful Hand
has just taken our active Teal Mask Ogerpon ex for 20 x 13 and the forced
promotion offers five bodies with NO energy on any of them:

    US (4 prizes)                        RIVAL (1 prize)
    active  -- knocked out --            active  Alakazam ex 140/140, 1 energy
    bench   Meganium       160                   (Powerful Hand: 20 x hand)
            Hydrapple ex   330           hand    15 cards -> 20 x (15+2) = 340
            Fezandipiti ex 210
            Meowth ex      170
            Tapu Bulu      140

Nobody attacks next turn and nobody knocks anything out: the only thing being
chosen is who takes their next blow. The agent promoted the TAPU BULU -- the
SMALLEST body on the bench -- and the reply went through it with 200 to spare.

Cause: the prize discount, again, on a board where it does not exist.
`_ko_prefer_basic_general` ("with no ready attacker and the opponent one-shotting
even our biggest tank, expose a 1-prize BASIC instead of a 2-prize ex") handed
the Tapu Bulu 8500 + hp/10 = 8514. That sentence buys a turn only while the
cheap body is CHEAPER THAN THEIR PILE; with their pile at ONE a 1-prize corpse
closes their count exactly like a 2-prize one. It is the third member of the
same family the registro_014 record already corrected -- the +3000 prize denial
and `_alakazam_pivot_1prize` -- and it was still priced on the discount.

And nothing was left saying what to do INSTEAD. `_promo_survives` reads the
projector the ordinary way, which is where Powerful Hand prints 0, so every
candidate "survived" and the survival band was asleep; the match-point rules
next to it are either vetoes that cannot fire when every candidate is doomed
(`_mp_cheaper_candidate` is False) or are scoped to the bodies that KNOCK OUT.

Fix, in two parts and deck-agnostic:

  1. the cheap body has to be cheaper: `prize_count(body) < op_prize` in
     `_ko_prefer_basic_general`;
  2. `_mp_last_stand`: when NO body on our bench pays less than their remaining
     pile -- so whichever one goes to the front, their next knockout ends the
     game -- and their reply REMOVES at least one of the candidates, the front
     spot goes to the body that absorbs that reply best. Read with
     `_mp_reply_to` (the projector that counts their HAND) and ordered by
     MARGIN, so the bodies that outlast the blow come first and, among the
     doomed, the one that comes CLOSEST to outlasting it. Their number is an
     UPPER bound -- `20 x (hand + 2)`, and every card they play takes 20 off it
     -- so the biggest margin is the only line that keeps the game alive.

`PROMO_LAST_STAND` (9450) sits below the two branches that are about acting
FIRST -- the guaranteed finisher (9500) and the body that knocks out
(+`PROMO_KO_BONUS`) -- and above the whole cheap-wall family. Bodies that knock
out are left out of the ranking altogether: among knockers the base score
decides, as `PROMO_KO_BONUS` documents.

Measured: ONE flip in 3687 record-corpus decisions (this step) and 15 flips in
76324 shadowed self-play decisions -- 60 mirror games plus 10 against each of
107 opposing decks -- EVERY one of them on a board with their pile at ONE. The
selector spoke on 123 of 152648 scoring menus, and head to head over 1000 games
the change is inside the noise floor (51.1% [48.0-54.2], 0 forfeits), which is
what an event this rare can say: the evidence of improvement is the record and
the unit test, and the gate's answer is that nothing else moved.

Coverage:
  * the record's board and its arithmetic: no energy anywhere, their reply
    removes all five candidates, and the Hydrapple ex is the one it removes by
    the smallest margin;
  * the record's decision: the Hydrapple ex comes up, not the Tapu Bulu;
  * each of the two parts on its own, through the score;
  * the boundaries -- away from match point the cheap basic keeps its board, a
    reply that removes nobody leaves the ordinary criteria alone, an unreadable
    reply chooses nothing, a body that dies anyway is not resurrected -- and the
    one point of HP where that flips, because a body that OUTLASTS a reply which
    ends the game takes the seat over the engine reservation
    (`PROMO_LOSING_SEAT_WALL`) -- and the ordering
    against the branches that act first.
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
from patching import parcheado

MEGANIUM = m.Meganium                 # 160 HP, 1 prize (the Wild Growth engine)
HYDRA = m.Hydrapple_ex                # 330 HP, 2 prizes -- the last stand
FEZ = m.Fezandipiti_ex                # 210 HP, 2 prizes
MEOWTH = m.Meowth_ex                  # 170 HP, 2 prizes
TAPU = m.Tapu_Bulu                    # 140 HP, 1 prize -- what it promoted
OP_ALAKAZAM = m.Alakazam_ex           # id 743: 140 HP, Powerful Hand

_FIX = (ROOT / "tests" / "fixtures"
        / "alakazam_t11_the_last_stand_takes_the_front_step130.json")


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


def _obs():
    with open(_FIX, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _bench_index(obs, card_id):
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    return next(i for i, b in enumerate(mine["bench"])
                if b and b["id"] == card_id)


def _stub(card_id, hp, energies=0):
    from types import SimpleNamespace
    return SimpleNamespace(id=card_id, hp=hp, maxHp=hp, tools=[],
                           energies=[1] * energies, energyCards=[])


def _scores(obs):
    """{card id: score} for the whole promotion menu, spying on the ranking."""
    out = {}

    def spy(context, select, sc, o, my_index, top_n=3):
        for i, opt in enumerate(select.option):
            card = m.get_card(o, opt.area, opt.index, my_index)
            if card is not None:
                out.setdefault(card.id, sc[i])

    with parcheado("_debug_log_decision", spy):
        m.agent(copy.deepcopy(obs))
    return out


def _their_prizes(obs, n):
    obs = copy.deepcopy(obs)
    obs["current"]["players"][1 - obs["current"]["yourIndex"]]["prize"] = [None] * n
    return obs


def _their_hand(obs, n):
    obs = copy.deepcopy(obs)
    obs["current"]["players"][1 - obs["current"]["yourIndex"]]["handCount"] = n
    return obs


# ---------------------------------------------------------------------------
# 1. The record: without this board the test measures nothing
# ---------------------------------------------------------------------------

def test_the_board_is_the_records_one():
    obs = _obs()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert len(mine["prize"]) == 4 and len(theirs["prize"]) == 1, (
        "their match point is the premise: their next knockout wins")
    assert not mine["active"], "the promotion is forced: the active is gone"
    assert theirs["handCount"] == 15

    bodies = {b["id"]: b for b in mine["bench"]}
    assert set(bodies) == {MEGANIUM, HYDRA, FEZ, MEOWTH, TAPU}
    assert all(not b["energies"] for b in mine["bench"]), (
        "no energy anywhere: nobody attacks and nobody knocks anything out")
    # And no candidate is cheap enough to survive their count: with one prize
    # left, every body on the bench pays at least what they still need.
    assert all(m.prize_count(_stub(b["id"], b["hp"])) >= len(theirs["prize"])
               for b in mine["bench"])


def test_their_reply_removes_every_candidate_and_the_hydrapple_by_the_least():
    """Powerful Hand prints 0 damage; counting their hand of 15 it is 340."""
    obs = _obs()
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    alakazam = _stub(OP_ALAKAZAM, 140, energies=1)

    assert m._op_active_attack_damage_to(alakazam, _stub(HYDRA, 330)) == 0, (
        "the ordinary projector is the seam: it reads this attack as zero")

    seen = {}
    for b in mine["bench"]:
        seen[b["id"]] = m._op_active_attack_damage_to(
            alakazam, _stub(b["id"], b["hp"]), op_hand_count=15)
    assert all(dmg >= 0 for dmg in seen.values())
    for b in mine["bench"]:
        assert seen[b["id"]] >= b["hp"], (b["id"], "their reply removes it")

    margin = {b["id"]: b["hp"] - seen[b["id"]] for b in mine["bench"]}
    assert max(margin, key=margin.get) == HYDRA, (
        "the Hydrapple ex is the body their blow clears by the least: 340 "
        "against 330, and every card they play takes 20 off that number")


# ---------------------------------------------------------------------------
# 2. The decision of the record
# ---------------------------------------------------------------------------

def test_the_front_spot_goes_to_the_hydrapple_that_absorbs_the_most():
    obs = _obs()
    assert m.agent(copy.deepcopy(obs)) == [_bench_index(obs, HYDRA)], (
        "at their match point the 1-prize Tapu Bulu is not cheaper: it is the "
        "same last prize in a body 190 HP smaller")


def test_the_last_stand_is_the_score_that_decides_it():
    scores = _scores(_obs())
    assert scores[HYDRA] >= m.PROMO_LAST_STAND
    assert scores[HYDRA] > scores[TAPU]
    assert scores[TAPU] < 8500, (
        "the cheap-wall rule no longer speaks on this board")


# ---------------------------------------------------------------------------
# 3. Each of the two parts, on its own
# ---------------------------------------------------------------------------

def test_the_cheap_wall_needs_a_discount_to_exist():
    """`_ko_prefer_basic_general` is one sentence: hand over a cheap body
    instead of an ex. It must be silent at their match point and awake one
    prize later, where the 1-prize basic really does buy a turn."""
    seen = {}
    original = m.score_option

    def spy(tc, o, score):
        seen.setdefault("wall", tc._ko_prefer_basic_general)
        return original(tc, o, score)

    m.score_option = spy
    try:
        m.agent(copy.deepcopy(_obs()))
        assert seen["wall"] is False, (
            "at op_prize == 1 the cheap body saves nothing")

        seen.clear()
        m.agent(_their_prizes(_obs(), 2))
        assert seen["wall"] is True, "with two prizes the saving is real"
    finally:
        m.score_option = original


def test_the_ranking_is_the_margin_and_not_the_price():
    """The selector itself: the body with the largest margin against their
    reply, and among equals the cheaper one -- never the other way round."""
    seen = {}
    original = m.score_option

    def spy(tc, o, score):
        seen.setdefault("body", tc._mp_last_stand)
        return original(tc, o, score)

    m.score_option = spy
    try:
        m.agent(copy.deepcopy(_obs()))
        assert seen["body"] is not None and seen["body"].id == HYDRA
    finally:
        m.score_option = original


# ---------------------------------------------------------------------------
# 4. The boundaries
# ---------------------------------------------------------------------------

def test_away_from_match_point_the_cheap_basic_still_takes_the_front():
    """With two prizes on their side the 1-prize body denies a real prize: it
    keeps the front spot and the rule that argues for it keeps its board."""
    obs = _their_prizes(_obs(), 2)
    assert m.agent(copy.deepcopy(obs)) == [_bench_index(obs, TAPU)]


def test_a_reply_that_removes_nobody_leaves_the_ordinary_criteria_alone():
    """The blow has to separate the candidates. With their hand nearly empty
    Powerful Hand projects 40, which takes none of the five bodies out, and the
    rule says nothing: who is closest to attacking decides, as always."""
    obs = _their_hand(_obs(), 0)
    seen = {}
    original = m.score_option

    def spy(tc, o, score):
        seen.setdefault("body", tc._mp_last_stand)
        return original(tc, o, score)

    m.score_option = spy
    try:
        m.agent(copy.deepcopy(obs))
        assert seen["body"] is None
    finally:
        m.score_option = original


def test_it_never_resurrects_a_body_that_dies_anyway():
    """`score > 0`. The Meganium line does not go to the active spot -- that
    veto is protecting the Wild Growth multiplier -- and a tank that costs us
    the engine is not a last stand. Bigger than every other candidate and STILL
    removed by their 340, it is not promoted: a last stand that does not stand
    is only the engine thrown away one turn earlier."""
    obs = _obs()
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    for b in mine["bench"]:
        if b["id"] == MEGANIUM:
            b["hp"] = b["maxHp"] = 340        # exactamente su respuesta: cae

    scores = _scores(obs)
    assert scores[MEGANIUM] < 0, "the veto keeps its word"
    assert m.agent(copy.deepcopy(obs)) != [_bench_index(obs, MEGANIUM)]


def test_the_engine_yields_when_it_is_the_only_body_that_OUTLASTS_the_reply():
    """EL LIMITE SE MOVIO UN PUNTO DE VIDA, y esta es su frase.

    Este test decia "un tanque que nos cuesta el motor no es un last stand", y lo
    probaba con un Meganium de 400 -- es decir, con el UNICO cuerpo del banquillo
    que sobrevive a sus 340. Esa version mezclaba dos tableros: el que la regla
    del last stand ordena (todos caen, elige quien cae mejor) y el que
    `THE_SEAT_THAT_LOSES_THE_GAME_YIELDS_TO_THE_WALL` reclama desde
    `PROMO_LOSING_SEAT_WALL` (uno aguanta, y con su monton a UNO ese es el unico
    que deja que haya turno siguiente).

    La reserva del motor es un argumento sobre los turnos que vienen: el doblador
    vale lo que valga el tablero de mañana. Con su monton a uno y un solo cuerpo
    que aguanta, mañana existe si y solo si sube ese. El test de arriba conserva
    la frase original en el tablero donde SI significa algo -- el tanque que cae
    igual -- y este fija la frontera: **340 cae y sigue vetado, 341 aguanta y se
    lleva el asiento**. Un punto de vida, que es exactamente donde la pregunta
    cambia.

    El tablero real que lo trajo no es este sino uno de self-play vs
    `crustle_wall_1` (turno 23, su monton a UNO): alli el Meganium de 160/160 con
    cuatro Grass era el unico que aguantaba los 140 de su Cornerstone Mask
    Ogerpon ex, estaba vetado a SCORE_NEVER, y el asiento se lo llevo un Dipplin
    de 80 que murio con el ultimo premio dentro. Ver
    `tests/test_the_seat_that_loses_the_game_yields_to_the_wall.py`.
    """
    obs = _obs()
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    for b in mine["bench"]:
        if b["id"] == MEGANIUM:
            b["hp"] = b["maxHp"] = 341        # un punto por encima: aguanta

    scores = _scores(obs)
    assert scores[MEGANIUM] >= m.PROMO_LOSING_SEAT_WALL, scores
    assert m.agent(copy.deepcopy(obs)) == [_bench_index(obs, MEGANIUM)]


def test_acting_first_still_outranks_tanking():
    """The ordering the rule is written into: a body that takes a prize, or one
    that is a single attachment from finishing them off, comes up before the
    tank. It is an invariant of the constants, not of a board."""
    assert m.PROMO_LAST_STAND < 9500, "the guaranteed finisher goes first"
    assert m.PROMO_LAST_STAND < m.PROMO_KO_BONUS, (
        "the body that knocks out goes first, and by a whole band")
    assert m.PROMO_LAST_STAND > 8500 + 330 // 10, (
        "and it outranks the cheap wall it replaces, tank-sized HP included")
