"""The DEAD turn does not end: it gusts the body that cannot answer.

User, registro_004 step 60 vs Alakazam, LOST (episode 90099795). Turn 4: our
Applin had just climbed Dipplin -> Hydrapple ex and was left with one of the two
energies its attack costs, the attachment of the turn was already spent, and no
body on the bench reached its own cost either. Nothing on the board knocked
anything out. All that was left in hand was a Boss's Orders and a Tapu Bulu, and
the Supporter of the turn had not been played. The agent chose END: the Boss's
stayed in hand for a game we went on to lose.

Their board was the answer. Their Alakazam ex was attacking from the front for
one energy, and behind it there was a Fezandipiti ex with no energy whose attack
costs three. Bringing it up costs them the turn twice over: it cannot answer from
the active spot even after an attachment, and it cannot go back to the bench
without attaching an energy TO IT and burning it on the retreat.

Why nothing saw it: the stall scan of `evaluate_supporters` only measures the
RETREAT gap and demands two. Every body on their bench had retreat one and no
energy -- a gap of one -- so it found nothing, the Boss's was left at zero value
and the `no_value` veto closed the turn. The gap alone was never the right
reading: what makes a trap is the PAIR, cannot answer AND cannot leave, which is
exactly the reading the target selector already used to decide WHO comes up once
the Boss's is played. `_boss_trap_gust` adds the missing half and
`gust_traps_their_turn` gives it the last rung of the Boss's ladder.

Deck-agnostic: nothing here names the Alakazam line. The exclusions are the ones
the relief of an attacker already made -- Dunsparce, the known threat
pre-evolutions (a bare Drakloak reads as harmless and then evolves into the
Dragapult ex that replaces the one we sent away), the walls and the ability
locker -- plus the Basics when a Latias ex retreats them for free.

Golden corpus: 2 flips, both END -> PLAY Boss's Orders, both of them dead turns
of this same class (registro_004 step 60 and registro_008 step 81).
"""

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Scenario, pk, G

HYDRAPPLE, DIPPLIN, APPLIN = m.Hydrapple_ex, m.Dipplin, m.Applin
OGERPON, CHIKORITA, MEOWTH = m.Teal_Mask_Ogerpon_ex, m.Chikorita, m.Meowth_ex
BOSS, TAPU = m.Boss_Orders, m.Tapu_Bulu

ALAKAZAM, KADABRA, ABRA = m.Alakazam_ex, m.Kadabra, m.Abra
FEZANDIPITI = m.Fezandipiti_ex
DUNSPARCE = 305
DRAKLOAK, DUSCLOPS = m.Drakloak, m.Dusclops


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _board(op_bench, menu="hand"):
    """The board of step 60: our Hydrapple ex at 1 of the 2 energies of Ripening
    Rush, the attachment of the turn spent, no benched attacker within reach and
    a hand of Boss's Orders + Tapu Bulu.

    `menu="hand"` measures WHETHER the Boss's is played; `menu="gust"` measures
    WHO it brings up.
    """
    sc = (Scenario(turn=4, step=60, tac=5, own_prizes=6, energy_played=True,
                   stadium_played=True)
          .my_active(pk(HYDRAPPLE, energies=[G], fisicas=1,
                        pre_evo=[APPLIN, DIPPLIN]))
          .my_bench(pk(CHIKORITA), pk(MEOWTH),
                    pk(OGERPON, energies=[G, G], fisicas=2),
                    pk(OGERPON, energies=[G], fisicas=1))
          .op_active(pk(ALAKAZAM, hp=140, max_hp=140, energies=[G],
                        pre_evo=[ABRA]))
          .op_bench(*op_bench)
          .op_zones(hand=8, deck=27, prizes=5))
    if menu == "gust":
        sc = sc.my_hand(TAPU).deck().menu_gust().rest_to_discard()
    else:
        sc = sc.my_hand(BOSS, TAPU).deck().rest_to_discard().menu_hand()
    return sc.build()


def _their_bench():
    """Their bench at step 60: two Kadabra, a second Alakazam ex, a Dunsparce
    ... and the bare Fezandipiti ex, the only trap among them."""
    return [pk(KADABRA, hp=80, max_hp=80, pre_evo=[ABRA]),
            pk(FEZANDIPITI, hp=210, max_hp=210),
            pk(ALAKAZAM, hp=140, max_hp=140, pre_evo=[ABRA]),
            pk(KADABRA, hp=80, max_hp=80, pre_evo=[ABRA]),
            pk(DUNSPARCE, hp=70, max_hp=70)]


# ---------------------------------------------------------------------------
# 1. The board really is the dead turn of the record
# ---------------------------------------------------------------------------

def test_the_turn_is_dead_and_the_gap_of_one_hides_the_trap():
    obs = _board(_their_bench())
    yo = obs["current"]["yourIndex"]
    mine = obs["current"]["players"][yo]
    theirs = obs["current"]["players"][1 - yo]

    # Not one body of ours reaches its own attack cost.
    for p in mine["active"] + [b for b in mine["bench"] if b]:
        req = m.ATTACK_ENERGY_REQ.get(p["id"])
        assert req is None or len(p["energies"]) < req

    # Their active DOES attack: there is something to relieve.
    act = m.to_observation_class(copy.deepcopy(obs)).current.players[1 - yo].active[0]
    assert not m._op_body_is_harmless(act)

    # Every body on their bench has retreat 1 and no energy: a gap of exactly 1,
    # which is what the old stall scan (threshold 2) could not see.
    for b in theirs["bench"]:
        assert m.RETREAT_COST.get(b["id"], 0) - len(b["energies"]) == 1

    # The menu is the one of the record: PLAY Boss's | PLAY Tapu Bulu | END.
    assert [o["type"] for o in obs["select"]["option"]] == [7, 7, 14]


# ---------------------------------------------------------------------------
# 2. The Boss's is played instead of ending the turn
# ---------------------------------------------------------------------------

def test_the_dead_turn_plays_the_bosss_instead_of_ending():
    assert m.agent(copy.deepcopy(_board(_their_bench()))) == [0], (
        "the turn has no attack and no knockout: the Supporter goes away with "
        "the hand if it is not played, and their bench holds a body that "
        "neither answers nor retreats")


def test_without_a_trap_on_their_bench_the_bosss_is_kept():
    """The control. The same dead turn, but their whole bench attacks after an
    attachment: bringing any of them up hands them the body they wanted in front
    and pays their retreat for free."""
    only_attackers = [pk(KADABRA, hp=80, max_hp=80, pre_evo=[ABRA]),
                      pk(ALAKAZAM, hp=140, max_hp=140, pre_evo=[ABRA]),
                      pk(DUNSPARCE, hp=70, max_hp=70)]
    assert m.agent(copy.deepcopy(_board(only_attackers))) != [0], (
        "with no body that stays stuck in front, the gust only pays their "
        "retreat: the Boss's is kept")


# ---------------------------------------------------------------------------
# 3. Who comes up: the body that cannot answer
# ---------------------------------------------------------------------------

def test_the_fezandipiti_comes_up_not_the_alakazam_line():
    """Index 1 of their bench is the Fezandipiti ex. The Kadabra and the second
    Alakazam ex evolve or attack from the active spot for one energy, and the
    Dunsparce is a forbidden target."""
    obs = _board(_their_bench(), menu="gust")
    assert obs["current"]["players"][1]["bench"][1]["id"] == FEZANDIPITI
    assert m.agent(copy.deepcopy(obs)) == [1]


# ---------------------------------------------------------------------------
# 4. The exclusions of the trap: measured on the predicate, not on the board
# ---------------------------------------------------------------------------

def test_a_bare_threat_preevolution_is_not_a_trap():
    """A Drakloak with no energy reads as harmless by COST (its attack costs 2),
    but it evolves IN THE ACTIVE SPOT into the Dragapult ex that replaces the one
    we sent to the bench. That is why the detector skips the known threat
    pre-evolutions -- the same exclusion the relief of an attacker makes."""
    obs = _board([pk(DRAKLOAK, hp=90, max_hp=90)])
    drakloak = m.to_observation_class(copy.deepcopy(obs)).current.players[1].bench[0]
    assert m._op_body_is_harmless(drakloak)
    assert DRAKLOAK in m.EX_PREEVO_IDS or DRAKLOAK in m.THREAT_PREEVO_IDS
    assert m.agent(copy.deepcopy(obs)) != [0]


def test_a_wall_is_never_the_trap_we_bring_up():
    """The walls and the ability locker attack for three, so bare they read as
    harmless -- and they are the last bodies we want in front, because from the
    active spot they cancel our attackers or switch off our abilities."""
    for wall in sorted(m.GUST_TRAP_IDS):
        obs = _board([pk(wall)])
        assert m.agent(copy.deepcopy(obs)) != [0], (
            f"{wall} is in GUST_TRAP_IDS: bringing it up is not a denial")
