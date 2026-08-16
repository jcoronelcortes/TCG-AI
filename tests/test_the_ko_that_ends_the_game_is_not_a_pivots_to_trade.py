"""The KO that ENDS the game is not a pivot's to trade away.

Scenario (user, episode 93675887 steps 172-173, turn 15, vs Alakazam -- WON, in
spite of this):

    US (1 prize)                              OPPONENT (3 prizes)
    active **Meganium 130/160, 4 energies**   active **Dunsparce 70/70, 0 en.**
    bench  Hydrapple ex 330/330, 4 en.        bench  Fezandipiti ex 210/210
           Fezandipiti ex 210                        Dunsparce 70/70
           Meowth ex 170, Meowth ex 170
           Hydrapple ex 90/330
    hand   Dawn, Tapu Bulu, **Boss's Orders**,
           Ogerpon ex x2, Forest, Ultra Ball

One prize left and *Solar Beam* (140) in front of a **70 HP Dunsparce**: attacking
takes the last prize and the game is over. The agent played **Boss's Orders** to
gust their benched Fezandipiti ex, then retreated Meganium, promoted the Hydrapple
ex and swung with *Syrup Storm* -- handing the opponent a whole extra turn to win a
game that was already won.

Why it fired
------------
`_active_attack_wins_now` was **True** and the attack still scored **1100**. The
finisher tier in the ATTACK scorer is gated on `plan.attacker == 0`, and the plan
said **1**: the attack loop had correctly chosen the active (SCORE_WIN_GAME + 524,
beating every bench candidate), and the Hydrapple ex pivot then overwrote it,
because a 330 HP body on the bench ENDURES MORE than a Meganium at 130.

The machinery to stop exactly that already existed -- `_active_win_plan` captures
the active's winning plan before the pivots and restores it after them -- but its
condition read only ONE of the two ways a turn ends the game: the opponent with an
**empty bench**, who cannot promote a replacement (registro_016 p138 vs Crustle).
The ordinary way, **the KO takes the prizes we were missing**, was not there, so on
every board where we are at match point the pivots were free to trade the winning
swing for a sturdier body. Durability, prize denial and mismatch are all arguments
about the NEXT turn; a turn that closes the game does not have one.

The fix is deck-agnostic by construction: it reads our prize count and the target's
own prize value (`prize_count_op`), never an archetype or a card list, and it keeps
the two brakes the later `_active_attack_wins_now` carries -- the KO must be
GUARANTEED (`_ko_not_guaranteed`) and it must not be the SUICIDAL finisher that
draws (registro_016 p184 vs Marnie).

It is the same sentence the Boss's ladder already states twice from the other side
(`winning_finisher_on_the_active_after_retreating`,
`the_field_ability_wins_on_the_active`); what was missing was saying it on the PLAN,
which is what every one of those consumers reads.

Measurement: 3 flips in the frozen corpus, all in the same turn of
`registro_046_festival_lead_8_asiento0` (turn 16, at 1 prize, with a 150-damage
Myriad Leaf Shower in front of an 80 HP Dipplin -- the agent used to play Night
Stretcher, evolve and retreat before winning the same game). One test board moved:
`test_archaludon_pivot_when_the_tank_really_knocks_out` was asked its question at
match point, where the pivot has nothing to answer.
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

_FIX_172 = ROOT / "tests" / "fixtures" / "alakazam_the_ko_that_ends_the_game_step172.json"
_FIX_173 = ROOT / "tests" / "fixtures" / "alakazam_the_ko_that_ends_the_game_step173.json"

MEGANIUM = m.Meganium
HYDRAPPLE = m.Hydrapple_ex
DUNSPARCE = 305  # Dunsparce (JTG print), one of m.DUNSPARCE_IDS
BOSS = m.Boss_Orders
SOLAR_BEAM = 1028

_PLAY = 7
_ATTACK = 13
_RETREAT = 12


@pytest.fixture(autouse=True)
def _reset():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs(path):
    with open(path, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _index_of(obs, tipo, **campos):
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") != tipo:
            continue
        if all(o.get(k) == v for k, v in campos.items()):
            return i
    raise AssertionError(f"no hay opcion {tipo} {campos} en {obs['select']['option']}")


# ---------------------------------------------------------------------------
# 1. The scenario: without it the test measures nothing
# ---------------------------------------------------------------------------

def test_one_prize_left_and_solar_beam_in_front_of_a_seventy_hp_body():
    obs = _obs(_FIX_173)
    mine = obs["current"]["players"][0]
    theirs = obs["current"]["players"][1]

    # Match point: one prize, and the body in front is worth exactly one.
    assert len(mine["prize"]) == 1
    front = theirs["active"][0]
    assert front["id"] == DUNSPARCE and front["hp"] == 70
    assert not m.card_table[DUNSPARCE].ex

    # Solar Beam reaches it four times over, with the energy already attached.
    active = mine["active"][0]
    assert active["id"] == MEGANIUM and len(active["energies"]) == 4

    # And the alternative the record took was on the table: the Boss's in hand
    # with the Supporter slot free, and a bench full of sturdier bodies.
    assert any(c["id"] == BOSS for c in mine["hand"])
    assert not obs["current"]["supporterPlayed"]
    assert any(b is not None and b["id"] == HYDRAPPLE and b["hp"] == 330
               for b in mine["bench"])


# ---------------------------------------------------------------------------
# 2. The decision, on both selects of the turn
# ---------------------------------------------------------------------------

def test_it_attacks_and_closes_the_game_instead_of_gusting():
    obs = _obs(_FIX_173)
    assert m.agent(obs) == [_index_of(obs, _ATTACK, attackId=SOLAR_BEAM)], (
        "a un premio, con el activo noqueando al cuerpo de delante, la partida "
        "se cierra atacando: ni Boss's Orders ni retirada"
    )


def test_the_same_turn_one_select_earlier():
    """Step 172, the first MAIN of the turn, with the whole menu still open:
    attachments, abilities, the Boss's. The finisher outranks all of it."""
    obs = _obs(_FIX_172)
    assert m.agent(obs) == [_index_of(obs, _ATTACK, attackId=SOLAR_BEAM)]


# ---------------------------------------------------------------------------
# 3. The mechanism: the plan keeps the attack on the ACTIVE
# ---------------------------------------------------------------------------

def test_the_pivot_does_not_take_the_plan_off_the_active():
    obs = _obs(_FIX_173)
    m.agent(obs)
    assert m.AGENT_STATE.plan.attacker == 0, (
        "el pivote de Hydrapple ex se llevaba el plan (attacker 0 -> 1) y con "
        "el ataque fuera de su escalon de finisher la Boss's ganaba el turno"
    )
    assert m.AGENT_STATE.plan.target == 0
    assert m.AGENT_STATE.plan.remain_hp <= 0


# ---------------------------------------------------------------------------
# 4. The other side of the sentence: with the game NOT ending, the pivot lives
# ---------------------------------------------------------------------------

def test_with_prizes_left_over_the_pivot_is_a_question_again():
    """The same board with four more prizes on our side: the KO no longer ends
    the game, so 'who is standing when they reply' is worth asking and the
    Hydrapple ex pivot is allowed to answer it. The guard is about the WIN, not
    about disabling the pivots."""
    obs = _obs(_FIX_173)
    obs["current"]["players"][0]["prize"] += [None] * 4
    assert len(obs["current"]["players"][0]["prize"]) == 5

    m.agent(obs)
    assert m.AGENT_STATE.plan.attacker != 0
