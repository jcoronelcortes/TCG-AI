"""Sixteen boolean flags nobody had written a law for.

(Seventeen since `op_has_ex_shield` joined the STICKY list in August 2026: it is
matchup memory of exactly the shape the third bullet below describes -- their
Acerola's Mischief leaves nothing on the board once its turn is over, so the
only law that can be checked about it is that it never falls. Eighteen since
`op_is_marnie_deck` joined it for the same reason: the gust ladder it feeds
reorders the target AWAY from the line that names the deck, so it has to hold
on the turns when no Marnie's body is on the board at all.)

The invariant monitor watched three promises and printed, on every run, how many
boolean flags on `AGENT_STATE` it could NOT watch. The number was **16**, and
one of them was `we_go_first` -- the flag that the same night turned out to be
assigned from inside a SCORER (`ptcg/turn/options/minor.py`, once per option
scored, so its value is the last option's). The monitor could not see it because
nobody had written down what the flag promises.

The mechanical part of closing that blind spot was never "write 16 premises",
because the sixteen are not one shape. Forcing them into one would have produced
a detector that fires on correct play, which is the failure mode this repository
has paid for five times. They are three:

  * **MIRRORS** (7). Beliefs recomputed at the top of `agent()` straight from
    the observation: `we_go_first`, `meganium_in_play`, `forest_in_play`,
    `full_metal_lab_in_play`, `_festival_grounds_in_play`, and the two
    prize-denial reads. The law is EQUALITY with the board, rebuilt here from
    the raw observation and never by calling the agent's own helper -- that
    would restate the belief instead of reconciling it. Same shape as
    DECK_BELIEF, and strong for the same reason: the truth comes from outside
    the agent.
  * **STICKY** (6). Matchup memory is one-way ON PURPOSE -- the comment on
    `op_is_starmie_deck` says a matchup forgotten the turn the Staryu retreats
    "is a matchup we would re-learn one KO too late". A premise that must still
    hold would be exactly the wrong law: the board stops showing the Crustle and
    the flag must STAY UP. What is checkable is the fall.
  * **EXEMPT** (3), with the reason written down. `_xerosic_played_this_turn`,
    `_ko_detected_this_turn` and `ko_last_turn` are accumulated from the LOG
    stream inside a turn, and a single observation carries nothing to reconcile
    them against. Watching them needs a different instrument, not a premise.
    Saying so is worth more than leaving them in an anonymous blind-spot count.

RESULT: the blind spot is **16 -> 0**, and over 600 honest games FLAG_MIRROR is
zero -- the seven beliefs agree with the board on every decision. That negative
result is the point: it also scopes the `we_go_first` defect precisely. The
mirror can only speak while `state.firstPlayer >= 0`, which is the same guard
the agent's own assignment carries, so a wrong value can exist only INSIDE the
IS_FIRST menu, before the coin is resolved. Everywhere else it is provably right.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "utils"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from ptcg.cards import ids
from ptcg.state.agent_state import AgentState
from invariant_monitor import (MIRRORS, PROMISES, SIN_PREMISA, STICKY,
                               check_flag_mirrors, check_sticky_flags,
                               unregistered_flags)


class _Mod:
    """The monitor only ever reaches the agent through `mod.AGENT_STATE`."""

    def __init__(self, **flags):
        self.AGENT_STATE = AgentState()
        self.AGENT_STATE.reset()
        for name, value in flags.items():
            setattr(self.AGENT_STATE, name, value)


def _obs(stadium=(), mine=(), theirs=(), first_player=-1, your_index=0):
    """`firstPlayer` is -1 by default: the coin unresolved, which is the one
    board where the `we_go_first` mirror is not allowed to speak. Every test
    that is not ABOUT that flag therefore does not have to carry it."""
    return {"current": {
        "yourIndex": your_index,
        "firstPlayer": first_player,
        "turn": 3,
        "stadium": [{"id": c} for c in stadium],
        "players": [
            {"active": [{"id": c} for c in mine[:1]],
             "bench": [{"id": c} for c in mine[1:]],
             "benchMax": 5, "hand": []},
            {"active": [{"id": c} for c in theirs[:1]],
             "bench": [{"id": c} for c in theirs[1:]],
             "benchMax": 5, "hand": []},
        ],
    }}


# ---------------------------------------------------------------------------
# 1. Every flag is accounted for, by name
# ---------------------------------------------------------------------------

def test_no_boolean_flag_is_left_without_a_law():
    assert unregistered_flags(_Mod()) == []


def test_the_sixteen_are_where_the_triage_put_them():
    """Named one by one on purpose. A flag that quietly moves between the three
    lists changes what is being CHECKED about it, and that is a decision, not a
    refactor."""
    espejos = {name for name, _w, _a, _e in MIRRORS}
    pegajosas = {name for name, _w in STICKY}
    assert espejos == {
        "we_go_first", "meganium_in_play", "forest_in_play",
        "full_metal_lab_in_play", "_festival_grounds_in_play",
        "_op_prize_denial_pecharunt", "_op_prize_denial_gengar"}
    assert pegajosas == {
        "op_is_crustle_deck", "op_is_cornerstone_deck", "op_is_starmie_deck",
        "op_has_mega_kangaskhan", "op_has_ex_shield", "op_is_marnie_deck",
        "_cards_first_scan_done", "_cards_prizes_identified"}
    assert set(SIN_PREMISA) == {
        "_xerosic_played_this_turn", "_ko_detected_this_turn", "ko_last_turn"}
    assert len(espejos | pegajosas | set(SIN_PREMISA)) == 18
    # and the three that already had one are untouched
    assert {n for n, _w, _p in PROMISES} == {
        "_ub_engine_pivot_turn", "_ub_meowth_pending", "_ub_fez_pending"}


def test_every_exemption_carries_a_reason():
    for name, motivo in SIN_PREMISA.items():
        assert len(motivo) > 30, f"{name} esta exenta sin explicar por que"


# ---------------------------------------------------------------------------
# 2. The mirrors: both directions, on both answers
# ---------------------------------------------------------------------------

def test_the_belief_that_matches_the_board_is_silent():
    mod = _Mod(meganium_in_play=True, forest_in_play=True)
    obs = _obs(stadium=[ids.Forest_of_Vitality], mine=[ids.Meganium])
    assert check_flag_mirrors(obs, mod) == []


def test_a_belief_the_board_denies_is_caught():
    mod = _Mod(meganium_in_play=True)
    fallos = check_flag_mirrors(_obs(mine=[ids.Chikorita]), mod)
    assert any("meganium_in_play" in f for f in fallos)


def test_a_board_the_belief_missed_is_caught_too():
    """The other direction, and it is not the same bug: a rule that asks "is the
    Meganium out?" and gets False stops planning around a body that is there."""
    mod = _Mod(meganium_in_play=False)
    fallos = check_flag_mirrors(_obs(mine=[ids.Meganium]), mod)
    assert any("meganium_in_play" in f for f in fallos)


def test_the_stadium_mirrors_do_not_answer_for_each_other():
    """Three flags read the same slot, so a mirror that asked "is there any
    stadium" would pass on the wrong one. Here the board IS the Full Metal Lab
    and both beliefs say so except the Forest, which is the only finding."""
    mod = _Mod(forest_in_play=True, full_metal_lab_in_play=True)
    fallos = check_flag_mirrors(_obs(stadium=[ids.Full_Metal_Lab]), mod)
    assert [f.split()[0] for f in fallos] == ["forest_in_play"]


def test_the_prize_denial_reads_look_at_THEIR_side():
    """The seat matters: our own body would be the opposite finding."""
    mod = _Mod(_op_prize_denial_gengar=True)
    assert check_flag_mirrors(
        _obs(theirs=[ids.Mega_Gengar_ex]), mod) == []
    fallos = check_flag_mirrors(_obs(mine=[ids.Mega_Gengar_ex]), mod)
    assert any("_op_prize_denial_gengar" in f for f in fallos)


def test_we_go_first_agrees_with_the_engine():
    mod = _Mod(we_go_first=True)
    assert check_flag_mirrors(_obs(first_player=0, your_index=0), mod) == []
    fallos = check_flag_mirrors(_obs(first_player=1, your_index=0), mod)
    assert any("we_go_first" in f for f in fallos)


def test_before_the_coin_the_mirror_says_NOTHING():
    """`firstPlayer` is -1 until the coin resolves, and the agent's own
    assignment carries the same guard. Asking outside that window would be the
    monitor reporting its own coarseness as a defect of the agent -- which is
    the exact mistake five detectors in this repository have already made.

    It is also what scopes the standing `we_go_first` defect: the flag is
    provably right wherever this check can speak, so a wrong value can only
    live inside the IS_FIRST menu itself."""
    mod = _Mod(we_go_first=True)
    assert check_flag_mirrors(_obs(first_player=-1), mod) == []
    mod = _Mod(we_go_first=False)
    assert check_flag_mirrors(_obs(first_player=-1), mod) == []


# ---------------------------------------------------------------------------
# 3. The sticky ones: the law is the FALL, not the premise
# ---------------------------------------------------------------------------

def test_a_matchup_that_stays_up_is_not_a_finding():
    mod = _Mod(op_is_crustle_deck=True)
    memoria = {}
    assert check_sticky_flags(mod, memoria) == []
    assert check_sticky_flags(mod, memoria) == []


def test_a_matchup_remembered_and_then_forgotten_is():
    mod = _Mod(op_is_crustle_deck=True)
    memoria = {}
    check_sticky_flags(mod, memoria)
    mod.AGENT_STATE.op_is_crustle_deck = False
    fallos = check_sticky_flags(mod, memoria)
    assert any("op_is_crustle_deck" in f and "DOWN" in f for f in fallos)


def test_a_flag_that_was_never_up_cannot_fall():
    """Most games never see a Crustle. A flag that is False from the first
    decision to the last is the normal case and must be silent."""
    mod = _Mod(op_is_crustle_deck=False)
    memoria = {}
    for _ in range(5):
        assert check_sticky_flags(mod, memoria) == []


def test_the_fall_is_reported_once_not_on_every_step():
    """A matchup forgotten on turn 4 would otherwise print on every decision of
    the rest of the game, which is how one defect becomes forty thousand lines
    (see `_ub_meowth_pending`)."""
    mod = _Mod(op_is_starmie_deck=True)
    memoria = {}
    check_sticky_flags(mod, memoria)
    mod.AGENT_STATE.op_is_starmie_deck = False
    assert len(check_sticky_flags(mod, memoria)) == 1
    assert check_sticky_flags(mod, memoria) == []
