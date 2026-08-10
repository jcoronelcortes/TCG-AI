"""An Asleep active has one key and it is the evolution card in our hand.

WHERE THIS CAME FROM. `records/registro_007_pasos_040_hasta_050.json` (episode
91172810, turn 7, LOST) against a Crustle / Cubchoo / Spheal deck. Two Spheal
sat on their bench the whole game and never attacked, so nothing in the corpus
ever put our active to sleep -- which is precisely why the hole was still there.
Spheal is worth reading before it does:

    Spheal (id 941) -- Basic, 70 HP, retreat 1
    Powder Snow -- 1 energy, 10 damage.
        "Your opponent's Active Pokemon is now Asleep."

It is the same body as the Cubchoo standing next to it (70 HP, one energy, 10
damage) and it is the same plan: neither of them is trying to win the damage
race, they are buying turns for the Crustle behind them. The difference is what
each lock takes away.

    Snotted Up (Cubchoo)   blocks the ATTACK.   Certain. One turn. RETREAT LEGAL.
    Powder Snow (Spheal)   blocks the ATTACK
                           **and the RETREAT**. A coin per Checkup. EVOLUTION CURES IT.

That second row is the whole rule. Asleep means our active can neither attack
nor pay a retreat, so the ordinary escape from a lock -- pivot to a body that
can act -- is closed too; and our deck has no switching card (deck.csv holds no
Switch and no Escape Rope), so the only way out that is OURS to take is
evolving: a Pokemon that evolves recovers from every Special Condition. The
alternative is the coin of the Pokemon Checkup, and that one is not ours.

WHAT THE AGENT DID BEFORE THIS RULE, measured on the synthetic board below --
an Asleep Dipplin carrying two Grass with Hydrapple ex in hand, against Crustle:

    it ENDED THE TURN.

It could not attack, could not retreat, and declined the one card that gives
back both, because the Hydrapple branch vetoes evolving into the Crustle wall
and the condition bonus only reaches scores that are already positive. The
special case was written for exactly one card -- the Bayleef branch has carried
`has_condition and condition_blocks_action -> 34000` by hand for a long time --
and Chikorita is not the only body that gets put to sleep. The environment holds
ten attacks that sleep our active (Powder Snow is the cheapest of them; Icy
Wind, Sleep Pulse, Hypno Splash, Absolute Snow, Bloom Powder... are the rest),
so the rule is written on the CONDITION and not on the opposing card.

THE GATE, and it is the half that keeps the rule honest: waking up is only worth
an evolution card if the woken body can DO something today -- reach its attack
cost, or pay its retreat with a bench to land on. Waking a body that can do
neither buys nothing this turn and, with a Stage 2 ex, plants two prizes in the
very spot the opponent is locking. That is the loss of registro_034 vs Cubchoo,
and the veto that came out of it keeps its word on those boards: an Asleep
Dipplin with NO energy does not become a Hydrapple ex just because it is asleep.

Coverage:
  * the flip: asleep + a woken body that can attack -> the evolution wins;
  * the control: the same board AWAKE still ends the turn (the wall's veto is
    untouched);
  * the gate, twice: nothing to do after waking -> no evolution, vs Cubchoo and
    vs Crustle;
  * paralysis takes the same key (it is the other condition evolution cures);
  * the Bayleef unlock, which this generalises, keeps its own reading;
  * the census of the environment that makes the rule general rather than a
    second special case.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from cg.api import AreaType, OptionType
from state_builder import C, G, Scenario, pk

SPHEAL = 941        # the body this file is about
CUBCHOO = 506       # its twin: same stats, the lock that does NOT block retreat
CRUSTLE = 345       # the 150 HP body the two of them are buying turns for
DWEBBLE = 344

APPLIN, DIPPLIN, HYDRAPPLE = m.Applin, m.Dipplin, m.Hydrapple_ex
CHIKORITA, BAYLEEF = m.Chikorita, m.Bayleef
OGERPON, TAPU = m.Teal_Mask_Ogerpon_ex, m.Tapu_Bulu
GRASS = m.Basic_Grass_Energy


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


def _asleep(obs, condition="asleep"):
    """Powder Snow has resolved: it is OUR turn and our active is Asleep."""
    obs["current"]["players"][obs["current"]["yourIndex"]][condition] = True
    return obs


def _evolves_the_active(obs):
    """Did the agent put the evolution on the ACTIVE body?"""
    choice = m.agent(obs)
    option = obs["select"]["option"][choice[0]]
    return (option["type"] == int(OptionType.EVOLVE)
            and option["inPlayArea"] == int(AreaType.ACTIVE))


def _ends_the_turn(obs):
    choice = m.agent(obs)
    return obs["select"]["option"][choice[0]]["type"] == int(OptionType.END)


def _board_dipplin(energies, op_active=CRUSTLE):
    """Our Dipplin in front of the wall, with Hydrapple ex in hand.

    `energies` is what the Dipplin carries: 2 is enough for Hydrapple ex to
    attack the moment it evolves (Syrup Storm costs 2), 0 is not enough for
    anything -- and it is not enough for its retreat either, which costs 3.
    """
    return (Scenario(turn=8, step=70, tac=1)
            .my_active(pk(DIPPLIN, energies=[G] * energies, pre_evo=[APPLIN]))
            .my_bench(OGERPON, TAPU)
            .my_hand(HYDRAPPLE, GRASS)
            .op_active(pk(op_active, hp=70 if op_active == CUBCHOO else 150,
                          max_hp=70 if op_active == CUBCHOO else 150,
                          energies=[C],
                          pre_evo=[DWEBBLE] if op_active == CRUSTLE else ()))
            .op_bench(pk(SPHEAL, energies=[C]))
            .op_zones(hand=5, deck=30, prizes=5)
            .menu_evolve()
            .build())


# ---------------------------------------------------------------------------
# 1. The flip
# ---------------------------------------------------------------------------

def test_the_sleeping_active_evolves_instead_of_passing_the_turn():
    """Asleep, two Grass, Hydrapple ex in hand: the card that gives the turn back.

    Before the rule this board ended the turn: no attack (asleep), no retreat
    (asleep), and the evolution vetoed for walking into the Crustle wall.
    """
    assert _evolves_the_active(_asleep(_board_dipplin(2)))


def test_awake_the_wall_veto_keeps_its_word():
    """The control. Take the sleep away and nothing changes: the reason not to
    evolve into Crustle is untouched -- what changed is only what it costs us to
    obey it while the active cannot move."""
    assert _ends_the_turn(_board_dipplin(2))


# ---------------------------------------------------------------------------
# 2. The gate: waking up has to BUY something
# ---------------------------------------------------------------------------

def test_a_woken_body_that_can_do_nothing_is_not_worth_the_card():
    """Asleep with NO energy vs the Cubchoo deck. The Hydrapple ex would wake
    up unable to attack (cost 2) and unable to retreat (cost 3): it would be a
    two-prize body nailed to the spot they are locking. That is registro_034,
    and its veto still owns this board."""
    assert _ends_the_turn(_asleep(_board_dipplin(0, op_active=CUBCHOO)))


def test_the_same_gate_in_front_of_the_wall():
    """The gate is the arithmetic of the woken body, not the opposing deck: the
    same empty Dipplin in front of Crustle also stays asleep. The Grass in hand
    does not rescue it either -- one attachment still falls short of the 2 the
    attack costs."""
    assert _ends_the_turn(_asleep(_board_dipplin(0)))


# ---------------------------------------------------------------------------
# 3. Scope
# ---------------------------------------------------------------------------

def test_paralysis_takes_the_same_key():
    """Evolution cures every Special Condition, and paralysis blocks the same
    two actions. The rule is written on `condition_blocks_action`, which is the
    reading the Bayleef branch already used."""
    assert _evolves_the_active(_asleep(_board_dipplin(2), condition="paralyzed"))


def test_the_bayleef_unlock_keeps_its_own_reading():
    """The special case this generalises. An Asleep Chikorita with Bayleef in
    hand evolves IN FRONT even though a second Chikorita waits on the bench --
    awake, the bench copy is the one that gets the card. Its band is above this
    rule's, so nothing here may move it."""
    def board():
        return (Scenario(turn=8, step=70, tac=1)
                .my_active(pk(CHIKORITA, energies=[G]))
                .my_bench(OGERPON, TAPU, pk(CHIKORITA))
                .my_hand(BAYLEEF, GRASS)
                .op_active(pk(CRUSTLE, hp=150, max_hp=150, energies=[C],
                              pre_evo=[DWEBBLE]))
                .op_bench(pk(SPHEAL, energies=[C]))
                .op_zones(hand=5, deck=30, prizes=5)
                .menu_evolve()
                .build())

    assert not _evolves_the_active(board()), (
        "awake, the card belongs on the bench copy")
    assert _evolves_the_active(_asleep(board()))


# ---------------------------------------------------------------------------
# 4. Why the rule is general and not a second special case
# ---------------------------------------------------------------------------

def test_the_environment_is_full_of_bodies_that_do_what_spheal_does():
    """Spheal is the cheapest sleeper in the format, not the only one.

    If this census ever shrinks to one card the rule could be written on that
    card; while it does not, writing it on the CONDITION is what keeps the other
    nine covered.
    """
    from ptcg.cards.tables import attack_table, card_table

    sleepers = [
        (cid, aid) for cid, c in card_table.items()
        for aid in (c.attacks or [])
        if "your opponent" in (getattr(attack_table.get(aid), "text", "") or "").lower()
        and "asleep" in (getattr(attack_table.get(aid), "text", "") or "").lower()]

    assert len(sleepers) >= 10, sleepers
    assert any(cid == SPHEAL for cid, _ in sleepers)

    powder_snow = next(attack_table[aid] for cid, aid in sleepers if cid == SPHEAL)
    assert powder_snow.damage == 10 and len(powder_snow.energies) == 1, (
        "one energy for a whole turn of ours is the trade Spheal offers")
    assert all(len(attack_table[aid].energies) >= 1 for _, aid in sleepers)


def test_spheal_and_cubchoo_are_the_same_body_with_different_locks():
    """The premise of the file: the deck of registro_007 carries two 70 HP,
    one-energy, 10-damage lock bodies, and only one of them leaves us the
    retreat. The rule exists for the other one."""
    from ptcg.cards.tables import attack_table, card_table

    spheal, cubchoo = card_table[SPHEAL], card_table[CUBCHOO]
    assert spheal.hp == cubchoo.hp == 70

    powder_snow = attack_table[spheal.attacks[0]]
    snotted_up = attack_table[cubchoo.attacks[0]]
    assert powder_snow.damage == snotted_up.damage == 10
    assert len(powder_snow.energies) == len(snotted_up.energies) == 1

    assert "asleep" in powder_snow.text.lower()
    assert "can't use attacks" in snotted_up.text.lower().replace("’", "'")
