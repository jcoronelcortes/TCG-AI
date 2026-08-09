"""Things that must never be true, checked on every decision of every game.

T2.1 of docs/night-plan-2026-08-09.md, and the answer to the estate's oldest
structural weakness: the suite is a MEMORY. Almost every file in tests/ is named
after a game that was lost, which is why fixed mistakes stay fixed and why
nothing covers a board no game has produced yet. An invariant needs no human to
know the right play -- it only needs to know what is impossible -- so it can be
checked on thousands of games an hour and turn compute into fixtures.

WHAT IT WATCHES

  * `ILLEGAL_INDEX`    -- a choice outside the option list, or the wrong count.
                          An exception in the container costs a whole game
                          regardless of strategy.
  * `END_EMPTY_BENCH`  -- ending a turn with nothing on the bench, which loses
                          the game the moment the active falls. There is already
                          a last-resort net for this in main.py; this is the
                          check that it holds. It carries the ONE documented
                          exception -- see `_first_turn_going_first` below -- and
                          the first version of this file did not, which turned 16
                          correct plays into a reported defect.
  * `STALE_FLAG`       -- a promise standing while its premise is dead.
  * `STALE_READ`       -- the same promise being READ while its premise is dead,
                          which is the one that can actually mislead a decision.
                          See below.
  * `DECK_BELIEF`      -- the agent's card tracker against the engine's own
                          count. See below: it is the only check here with a
                          source of truth OUTSIDE the agent.
  * `ENERGY_CAP`       -- an energy sent to a body already at its documented
                          cap. The DECISION, not the board: see below.
  * `DOUBLE_ATTACH`    -- a second manual attachment inside one turn.

DECK_BELIEF, and why it is the strongest of these. `AGENT_STATE.ACTIVE_CARDS_IN_DECK`
is a belief the agent maintains about where all 60 cards are, and several rules
read it to decide whether a line is still live at all (`_gt_planes` will not
plan a search for a body whose last copy is in the discard). `_sync_from_state`
rebuilds it by subtraction: total copies minus what it can SEE in hand, in play
and in the discard, with the remainder split between deck and prizes. Nothing in
that arithmetic ever looks at how many cards the engine says are left.

`deckCount` is exactly that number, it comes from libcg, and comparing the two
is therefore a real reconciliation and not a restatement -- the same shape as
the differential oracle, whose whole point is that the truth must come from
somewhere the agent cannot write. A drift here means some card moved by a route
`_process_logs` does not model, and every rule that reads the tracker has been
reasoning about a deck that is not there.

It carries a SENTINEL, and it needed one. Half of all decisions are taken while
the board is mid-effect -- a card drawn but not yet in hand, the opening active
on its way down, a search with the deck spread out -- and on those boards the
engine's own zones do not add up to 60, so `deckCount` counts nothing stable.
The first version had no sentinel and reported 37 799 findings in 38 143
decisions, which is the same over-report the differential oracle had to be
talked out of three times in one night. With the sentinel the identity is
EXACT: over 1 933 self-consistent boards the tracker's deck equals `deckCount`
plus the prizes it has not yet identified, zero drift, which is what makes any
future violation worth reading. The boards skipped are counted and printed.

ENERGY_CAP watches the DECISION, and the first version did not. A cap says "do
not send another energy there"; it does not say a body can never CARRY that
much, because a body can inherit it. An Applin allowed its second energy by its
own documented exception evolves into a Dipplin holding two, over the Dipplin
cap, with nobody having done anything wrong -- and that accounted for 7 of the 7
board-level findings in 300 games. So what is judged is the option chosen and
the body it points at, which is exactly the domain of the rule in
`ptcg/turn/energy.py`.

And only on the BENCH, which is the second correction the measurement forced.
The decision version still reported 2 findings in 300 games, both a second Grass
onto the ACTIVE Dipplin. Tracing the live scorer -- `ptcg/turn/scoring.py`
binds `attach.score_play` into `_TABLE` at import, so the function has to be
replaced THERE and not on the module -- the Dipplin scored 41 000 against the
Ogerpon's -1 and the Bayleef's 7 000. That is the lethal band: the energy pays
the retreat that brings up the body which takes a prize this turn, and the cap
yields to it by design ("this cap does not block lethal finishers"). Correct
play, twice. Every one of those overrides lives inside the ACTIVE branch, so the
bench is where the cap is unconditional and the bench is what is judged.

What it deliberately does NOT watch. The caps that belong to a
CARD are checked -- Chikorita 1, Applin 1, Dipplin 1 -- because they are hard
vetoes in `ptcg/turn/energy.py` with documented exceptions that can be read off
the observation, and they hold in every matchup. The caps that belong to a
MATCHUP are not: the Ogerpon ceiling is `_ogerpon_base_phys_cap(meganium, hop)`
gated by which deck is across the table, plus a separate Cubchoo ladder, plus
one allowance on the active when the extra energy enables the knockout. Writing
that ladder out again here would create a second copy of a rule the first copy
already owns, which is the exact defect class (B) the differential oracle exists
to catch, and it would fail the same way: the copies drift and the monitor
starts reporting the DIFFERENCE between them as if it were the agent's mistake.
A cap with a matchup gate belongs to a unit test, not to a monitor.

DOUBLE_ATTACH is cheap and is expected to stay at zero: the engine does not
offer a second attachment, so this is the harness proving it can see a turn
rather than a likely defect. It is here because a zero that has been checked is
worth more than an assumption, and it costs four lines.

THE ONE FROM THE PLAN THAT IS NOT HERE, and the refusal is the point. The night
plan also lists "never retreat into a body that cannot act next turn". It is not
an invariant, on two counts. First, it is false as stated: measured while gating
the anti-Mega-Starmie pivot, "we cannot attack" holds 9.8-11.4 times per game on
turns 2, 4, 6, 8, 10 -- a turn without an attack available is the ordinary shape
of a development turn, not a rare board. Second, deciding whether the body CAN
act needs the energy-and-cost model the agent already owns, and a second copy of
it here is the class-B duplication this file refuses for the matchup caps. The
retreats worth judging (into a wall, into a mute body) are strategy, and
strategy belongs to self-play and to the tests, not to a monitor whose whole
value is that it needs nobody to know the right play.

STALE_FLAG, and why it is worth its own tool. Of the roughly twenty fixes made
on 7-8 August 2026, FIVE were one shape: a flag on AGENT_STATE armed under some
premise, and consumed later in the same turn after that premise had died. The
canonical one is `_ub_engine_pivot_turn`: main.py:2036 arms it while a bench seat
is free, main.py:3552 clears it only when the TURN changes, and in between a
Pokemon can come down and fill the bench. The flag does not notice. An Ultra Ball
then digs for a body that cannot be played -- two cards spent on a card that
sleeps in hand.

The premise is inside the agent and the flag is a bare bool, so there is nothing
to check unless the premise is written down. That is what `PROMISES` is: a
registry mapping each flag to a predicate over the OBSERVATION that must still
hold while the flag is up. It is seeded with the flags that have already failed,
and every run prints how many boolean flags on AGENT_STATE are NOT registered,
so the blind spot is a number rather than a silence.

STALE_FLAG VERSUS STALE_READ, and why the second one exists. A flag standing on
a dead premise harms nothing if nobody looks at it, and several consumers here
re-check the premise themselves -- which is why the first version of this file
reported 440 stale episodes that were not defects. What can mislead a decision is
a READ: the moment some rule asks "is this promise up?", gets True, and acts on
it while the reason the promise was made no longer holds.

Reads are observable without touching the agent. Every module binds the same
AGENT_STATE object (`from ptcg.state.agent_state import AGENT_STATE` copies the
reference, not the value), so swapping that one instance's `__class__` for a
subclass that overrides `__getattribute__` sees every read from everywhere, and
the class is put back afterwards. A read is recorded only when it returns True --
a guard asking "is it NOT up?" and getting False is exactly the code doing its
job.

WHAT THE READ WATCH ACTUALLY FOUND, and it is a negative result worth writing
down rather than a defect. Over 600 games: 4312 decisions with a promise standing
on a dead premise, of which 743 involved an actual READ. Zero of those are
defects. The single real consumer of `_ub_meowth_pending`
(ptcg/turn/options/play.py:1235) reads it inside a compound condition that
re-checks BOTH halves of the premise itself -- `bench_count < 5` and
`not state.supporterPlayed`. The flag is read, the premise is dead, and the other
terms of the `and` throw the play out anyway.

That is the limit of watching from outside: a read is one term of a condition,
and the terms beside it are invisible here. Detecting G-A properly needs either
static analysis of each read site, or the agent stating its own premises. Both
are design work, not more instrumentation, and STALE_READ is left in place
reporting honestly rather than quietly tuned to zero -- a number that needs its
read site inspected is still worth more than no number.

The good news is the finding itself: all three registered promises ARE guarded
where they are consumed. tests/test_the_promise_is_guarded_where_it_is_read.py
pins that, so removing one of those guards goes red.

VALIDATE IT BEFORE TRUSTING ITS ZERO -- both halves, because a detector has two
ways to be useless and only one of them looks like a result:

  * sensitivity: an injected violation must be caught;
  * specificity: an untouched run must not fire on the invariants that are
    structurally impossible for a correct agent (a legal index, chiefly).

Both run first by default and abort the run if they fail. The first version of
the differential oracle had only the sensitivity half and over-reported by three
orders of magnitude for hours before anyone noticed.

Usage:
    python utils/invariant_monitor.py --games 500
    python utils/invariant_monitor.py --games 2000 --opponent deck/opponents/marnie_grimmsnarl.csv
    python utils/invariant_monitor.py --games 200 --dump log/violations
    python utils/invariant_monitor.py --self-test-only
"""

import argparse
import copy
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402
from cg.api import AreaType, CardType, OptionType  # noqa: E402
from ptcg.cards.ids import Applin, Chikorita, Dipplin, Hydrapple_ex  # noqa: E402
from ptcg.cards.tables import card_table  # noqa: E402
from ptcg.state.zones import ZONE_DECK, ZONE_PRIZE  # noqa: E402

END_OPTION = int(OptionType.END)
ATTACH_OPTION = int(OptionType.ATTACH)


# --------------------------------------------------------------------------
# Reading the board
# --------------------------------------------------------------------------

def my_side(obs):
    try:
        return obs["current"]["players"][obs["current"]["yourIndex"]]
    except (KeyError, IndexError, TypeError):
        return {}


def free_bench_seats(obs):
    side = my_side(obs)
    bench = [b for b in (side.get("bench") or []) if b]
    return max(0, (side.get("benchMax") or 5) - len(bench))


def supporter_spent(obs):
    return bool((obs.get("current") or {}).get("supporterPlayed"))


def our_bodies(obs):
    """Every Pokemon of ours on the field, active first."""
    side = my_side(obs)
    out = list(side.get("active") or [])
    out += [b for b in (side.get("bench") or []) if b]
    return [b for b in out if b]


def hand_counts(obs):
    counts = {}
    for card in (my_side(obs).get("hand") or []):
        counts[card.get("id")] = counts.get(card.get("id"), 0) + 1
    return counts


def field_counts(obs):
    counts = {}
    for body in our_bodies(obs):
        counts[body.get("id")] = counts.get(body.get("id"), 0) + 1
    return counts


# --------------------------------------------------------------------------
# G-A: the premise each promise is written on
# --------------------------------------------------------------------------
#
# Each entry is (flag name, human premise, predicate over the observation that
# must hold WHILE the flag is up). A flag whose premise is false is a promise
# whose reason to exist has died, and the code that reads it cannot tell.

PROMISES = [
    ("_ub_engine_pivot_turn",
     "a free bench seat, so the body the Ultra Ball digs can actually come down",
     lambda obs: free_bench_seats(obs) >= 1),
    ("_ub_meowth_pending",
     "a free bench seat AND the turn's Supporter still unspent -- the Meowth is "
     "only worth digging as the first half of Meowth -> Lillie's",
     lambda obs: free_bench_seats(obs) >= 1 and not supporter_spent(obs)),
    ("_ub_fez_pending",
     "a free bench seat for the Fezandipiti",
     lambda obs: free_bench_seats(obs) >= 1),
]

_REGISTERED = {name for name, _why, _p in PROMISES}


def unregistered_flags(mod):
    """Boolean flags on AGENT_STATE with no premise written down."""
    try:
        state = vars(mod.AGENT_STATE)
    except (AttributeError, TypeError):
        return []
    return sorted(k for k, v in state.items()
                  if isinstance(v, bool) and k not in _REGISTERED)


# --------------------------------------------------------------------------
# Watching the reads
# --------------------------------------------------------------------------

_READS = []          # names read as True since the last clear
_WATCHING = set()


def _install_read_watch(mod):
    """Swap AGENT_STATE's class so every read of a promise is recorded.

    Returns the original class so the caller can put it back. Every module holds
    the SAME AGENT_STATE object, so this observes all of them at once; nothing in
    the agent is modified.
    """
    state = mod.AGENT_STATE
    original = type(state)
    watched = {name for name, _why, _p in PROMISES}

    class _Watched(original):
        def __getattribute__(self, name):
            value = original.__getattribute__(self, name)
            if name in watched and value is True:
                _READS.append(name)
            return value

    try:
        state.__class__ = _Watched
    except TypeError:
        return None            # not swappable: reads simply go unwatched
    _WATCHING.add(id(state))
    return original


def _remove_read_watch(mod, original):
    if original is None:
        return
    try:
        mod.AGENT_STATE.__class__ = original
    except (AttributeError, TypeError):
        pass


# --------------------------------------------------------------------------
# The invariants
# --------------------------------------------------------------------------

def check_illegal_index(obs, choice):
    options = (obs.get("select") or {}).get("option") or []
    if choice is None:
        return "the agent returned None instead of a choice"
    if not isinstance(choice, (list, tuple)):
        return f"the choice is not a list: {type(choice).__name__}"
    for i in choice:
        if not isinstance(i, int) or i < 0 or i >= len(options):
            return f"index {i!r} outside an option list of {len(options)}"
    select = obs.get("select") or {}
    low = select.get("minCount")
    high = select.get("maxCount")
    if isinstance(low, int) and len(choice) < low:
        return f"chose {len(choice)} options with minCount {low}"
    if isinstance(high, int) and high >= 0 and len(choice) > high:
        return f"chose {len(choice)} options with maxCount {high}"
    return None


def first_turn_going_first(obs):
    """The one board where an empty bench is not a danger, and it is deliberate.

    On OUR first turn having gone first, the opponent has not had a turn: nothing
    they can do reaches the 140-210 hp of our opener, so there is no knockout to
    be promoted from. main.py holds the lone Meowth ex back rather than spending
    it to fill the bench (`_ft_hold_lone_meowth`), which is a reasoned trade and
    not an oversight.

    This exception exists because the invariant without it reported 16 violations
    in 500 games and ALL SIXTEEN were this board. An invariant that flags correct
    play is not a weaker detector, it is a broken one: it buries the real finding
    it is supposed to surface.
    """
    current = obs.get("current") or {}
    return (current.get("turn") == 1
            and current.get("firstPlayer") == current.get("yourIndex"))


def could_have_filled_the_bench(obs):
    """Is there a play on the menu that actually puts a body on the bench?

    Ending with an empty bench is only a defect if it was AVOIDABLE. Three
    things make it unavoidable and all three occur: no PLAY option at all, no
    Basic Pokemon in hand, or PLAY options that are items and stadiums -- which
    fill nothing. Measured over 800 games, 20 of 35 empty-bench endings had no
    playable card whatsoever and the other 15 offered only non-Pokemon plays.
    Without this the invariant reports all 35 and buries whatever real one turns
    up later.
    """
    side = my_side(obs)
    hand = side.get("hand") or []
    for opt in ((obs.get("select") or {}).get("option") or []):
        if opt.get("type") != int(OptionType.PLAY):
            continue
        idx = opt.get("index")
        if not isinstance(idx, int) or not (0 <= idx < len(hand)):
            continue
        data = card_table.get(hand[idx].get("id"))
        if data is None:
            continue
        if (getattr(data, "cardType", None) == CardType.POKEMON
                and getattr(data, "basic", False)):
            return True
    return False


def check_end_with_empty_bench(obs, choice):
    options = (obs.get("select") or {}).get("option") or []
    ends = any(0 <= i < len(options)
               and options[i].get("type") == END_OPTION
               for i in (choice or []))
    if not ends:
        return None
    side = my_side(obs)
    bench = [b for b in (side.get("bench") or []) if b]
    if bench:
        return None
    if first_turn_going_first(obs):
        return None
    if not could_have_filled_the_bench(obs):
        return None                      # nothing on the menu fills a bench
    return "ending the turn with an empty bench: the next knockout is the game"


def cards_on_our_field(side):
    """Every physical card of ours in play: bodies, their pre-evolutions, the
    energy attached and the tools."""
    total = 0
    for body in (side.get("active") or []) + [b for b in (side.get("bench") or []) if b]:
        if not body:
            continue
        total += (1 + len(body.get("preEvolution") or [])
                  + len(body.get("energyCards") or [])
                  + len(body.get("tools") or []))
    return total


def board_in_transit(obs, expected_total):
    """True while the ENGINE's own zones do not add up to the whole deck.

    Half of all decisions are taken mid-effect: a card drawn but not yet in
    hand, the opening active still on its way down, a search with the deck
    spread out. On those boards `deckCount` is not a count of anything stable,
    and judging the tracker against it invents a finding on every one of them --
    the first version of this check fired on 37 799 of 38 143 decisions, which
    is the same over-report the differential oracle had to be talked out of.

    So this is the sentinel: the truth has to be self-consistent before it can
    be used as truth. The count of boards skipped is printed, so the blind spot
    is a number rather than a silence.
    """
    side = my_side(obs)
    deck_count = side.get("deckCount")
    if not isinstance(deck_count, int) or not expected_total:
        return True
    seen = (deck_count
            + len(side.get("prize") or [])
            + len(side.get("hand") or [])
            + len(side.get("discard") or [])
            + cards_on_our_field(side)
            + len((obs.get("current") or {}).get("looking") or []))
    return seen != expected_total


def our_deck_seat(seat, opponent):
    """Is this seat actually playing OUR sixty cards?

    Both seats are driven by our agent, which is what makes the monitor cheap.
    With `--opponent`, though, seat 1 is dealt the RIVAL's deck while the agent
    driving it still initialised `ACTIVE_CARDS_IN_DECK` from ours, so its belief
    is about a deck it is not holding and every reconciliation against it is
    nonsense.

    That is not a hypothesis. Run against `alakazam.csv` before this guard
    existed, DECK_BELIEF reported 16 980 findings in 14 579 judged boards, all
    of them "the tracker believes 59 cards are left" -- one card ever leaving a
    deck the agent was never dealt. Sixteen thousand findings that were the
    harness, in a file whose whole subject is detectors reporting themselves.

    The mirror (no `--opponent`) deals our deck to both seats, which is why the
    first measurements were clean and why this went unnoticed until a fixture
    disagreed with them.
    """
    return opponent is None or seat == 0


def check_deck_belief(obs, mod):
    """The agent's card tracker against the engine's own count.

    `AGENT_STATE.ACTIVE_CARDS_IN_DECK` is rebuilt by SUBTRACTION -- total copies
    minus what can be seen in hand, in play and in the discard, with the
    remainder split between the deck and the prizes. Nothing in that arithmetic
    ever looks at `deckCount`, so comparing the two is a real reconciliation.

    The identity, once the prizes are accounted for: what the tracker calls the
    DECK is the engine's `deckCount` plus every prize it has not yet identified.
    Measured over 1 933 self-consistent boards it holds EXACTLY -- zero drift --
    which is what makes a future violation worth reading.
    """
    try:
        belief = mod.AGENT_STATE.ACTIVE_CARDS_IN_DECK
    except AttributeError:
        return []
    if not belief:
        return []
    side = my_side(obs)
    prizes_left = len(side.get("prize") or [])
    believed_deck = sum(entry.get(ZONE_DECK, 0) for entry in belief.values())
    believed_prize = sum(entry.get(ZONE_PRIZE, 0) for entry in belief.values())

    out = []
    expected = side["deckCount"] + (prizes_left - believed_prize)
    if believed_deck != expected:
        out.append(f"the tracker believes {believed_deck} cards are left in the "
                   f"deck; the engine has {side['deckCount']} with "
                   f"{prizes_left - believed_prize} prizes still unidentified")
    if believed_prize > prizes_left:
        out.append(f"the tracker places {believed_prize} cards in the prizes; "
                   f"only {prizes_left} are still face down")
    return out


# The caps that belong to a CARD, not to a matchup -- see the module docstring
# for why the Ogerpon ceiling is deliberately absent. Each entry is
# (card id, name, cap in PHYSICAL energy, why, predicate for the documented
# exception that legitimately allows going over).

def _applin_over_cap_allowed(obs, mod):
    """The two exceptions written into `energy_score` for the Applin cap.

    (a) a COMPLETE evolution in hand -- Dipplin AND Hydrapple ex, no Meganium:
        the second energy ends up on the future Hydrapple ex, so it is not
        wasted; (b) our Hydrapple ex already in play, where a Grass on the field
        scales Syrup Storm and the attachment is allowed as a last resort.
    """
    hand = hand_counts(obs)
    meganium = bool(getattr(mod.AGENT_STATE, "meganium_in_play", False))
    full_evolve = (hand.get(Dipplin, 0) >= 1 and hand.get(Hydrapple_ex, 0) >= 1
                   and not meganium)
    return full_evolve or field_counts(obs).get(Hydrapple_ex, 0) >= 1


def _dipplin_over_cap_allowed(obs, mod):
    """The mirror of the Applin exceptions, for the Dipplin cap."""
    if hand_counts(obs).get(Hydrapple_ex, 0) >= 1:
        return True
    return field_counts(obs).get(Hydrapple_ex, 0) >= 1


CARD_CAPS = [
    (Chikorita, "Chikorita", 1,
     "its only attack costs 1 and the surplus is saved for real attackers",
     lambda obs, mod: False),
    (Applin, "Applin", 1,
     "its attack costs 1 and Dipplin's Do the Wave costs 1 too",
     _applin_over_cap_allowed),
    (Dipplin, "Dipplin", 1,
     "Do the Wave costs 1 and its damage does not scale with energy",
     _dipplin_over_cap_allowed),
]


def _attach_target(obs, option):
    """The body an ATTACH option points at, or None."""
    side = my_side(obs)
    area = option.get("inPlayArea")
    index = option.get("inPlayIndex")
    if not isinstance(index, int):
        return None
    if area == int(AreaType.ACTIVE):
        bodies = side.get("active") or []
    elif area == int(AreaType.BENCH):
        bodies = side.get("bench") or []
    else:
        return None
    if not (0 <= index < len(bodies)):
        return None
    return bodies[index]


def check_energy_caps(obs, mod, choice):
    """The cap is about the DECISION to attach, not about the board.

    Checking the board reports plays that are correct: the Applin exception
    legitimately allows a second energy, and the Applin then EVOLVES into a
    Dipplin carrying both -- a Dipplin over its own cap that nobody put there.
    Measured, that was 7 of the 7 board-level findings in 300 games.

    What `energy_score` actually forbids is sending ANOTHER energy to a body
    already at its cap, so that is what is watched: the option chosen, and the
    body it points at. It covers the manual attachment; Ripening Charge reaches
    the same scorer through a second select (`SelectContext.ATTACH_FROM`) whose
    target is not on this menu, and is not judged here.
    """
    options = (obs.get("select") or {}).get("option") or []
    meganium = bool(getattr(mod.AGENT_STATE, "meganium_in_play", False))
    out = []
    for i in (choice or []):
        if not (isinstance(i, int) and 0 <= i < len(options)):
            continue
        option = options[i]
        if option.get("type") != ATTACH_OPTION:
            continue
        if option.get("inPlayArea") != int(AreaType.BENCH):
            continue          # the ACTIVE has documented overrides -- see above
        body = _attach_target(obs, option)
        if not body:
            continue
        for card_id, name, cap, why, allowed in CARD_CAPS:
            if body.get("id") != card_id:
                continue
            effective = len(body.get("energies") or [])
            physical = effective // 2 if meganium else effective
            if physical < cap:
                continue
            try:
                if allowed(obs, mod):
                    continue
            except Exception:
                continue
            out.append(f"another energy sent to a {name} that already carries "
                       f"{physical} of a cap of {cap}: {why}")
    return out


def check_double_attachment(obs, choice):
    """A second manual attachment inside one turn."""
    if not (obs.get("current") or {}).get("energyAttached"):
        return None
    options = (obs.get("select") or {}).get("option") or []
    for i in (choice or []):
        if 0 <= i < len(options) and options[i].get("type") == ATTACH_OPTION:
            return ("a manual attachment chosen with the turn's attachment "
                    "already spent")
    return None


def check_stale_reads(obs, names):
    """G-A, sharpened. A promise READ as True while its premise is dead."""
    out = []
    seen = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        for flag, why, premise in PROMISES:
            if flag != name:
                continue
            try:
                if not premise(obs):
                    out.append(f"{name} was READ as True while its premise was "
                               f"dead: {why}")
            except Exception:
                pass
    return out


def check_stale_flags(obs, mod):
    """G-A. A promise still up whose premise has died."""
    out = []
    try:
        state = mod.AGENT_STATE
    except AttributeError:
        return out
    for name, why, premise in PROMISES:
        if not getattr(state, name, False):
            continue
        try:
            alive = premise(obs)
        except Exception:
            continue
        if not alive:
            out.append(f"{name} is up but its premise died: {why}")
    return out


# --------------------------------------------------------------------------
# Driving
# --------------------------------------------------------------------------

def over_games(games, opponent=None, saboteur=None, progress=None):
    from cg import game

    agents = [sp.load_agent(str(_ROOT / "main.py"), "inv_p0"),
              sp.load_agent(str(_ROOT / "main.py"), "inv_p1")]
    deck = sp.read_deck()
    op_deck = sp.read_deck(opponent) if opponent else list(deck)

    deck_size = len(deck)
    watched = [(m, _install_read_watch(m)) for m in agents]
    stats = {"games": 0, "decisions": 0, "raised": 0, "reads_watched": 0,
             "skipped_transit": 0, "skipped_foreign_deck": 0}
    findings = []

    def record(kind, detail, obs, game_no, step, seat):
        findings.append({"kind": kind, "detail": detail, "game": game_no,
                         "step": step, "seat": seat, "observation": obs})

    for game_no in range(games):
        for m in agents:
            sp._reset_si_aplica(m)
        obs, _sd = game.battle_start(list(deck), list(op_deck))
        if obs is None:
            continue
        stats["games"] += 1
        steps = 0
        try:
            while obs and obs["current"]["result"] == -1 and steps < 3000:
                yi = obs["current"]["yourIndex"]
                mod = agents[yi]
                snapshot = copy.deepcopy(obs)
                _READS.clear()
                try:
                    choice = mod.agent(obs)
                except Exception as exc:
                    stats["raised"] += 1
                    record("AGENT_RAISED", repr(exc), snapshot, game_no, steps, yi)
                    break
                if saboteur is not None:
                    saboteur(mod)

                bad = check_illegal_index(snapshot, choice)
                if bad:
                    record("ILLEGAL_INDEX", bad, snapshot, game_no, steps, yi)
                else:
                    bad = check_end_with_empty_bench(snapshot, choice)
                    if bad:
                        record("END_EMPTY_BENCH", bad, snapshot, game_no, steps, yi)
                twice = check_double_attachment(snapshot, choice)
                if twice:
                    record("DOUBLE_ATTACH", twice, snapshot, game_no, steps, yi)
                if not our_deck_seat(yi, opponent):
                    stats["skipped_foreign_deck"] += 1
                elif board_in_transit(snapshot, deck_size):
                    stats["skipped_transit"] += 1
                else:
                    for drift in check_deck_belief(snapshot, mod):
                        record("DECK_BELIEF", drift, snapshot, game_no, steps, yi)
                for over in check_energy_caps(snapshot, mod, choice):
                    record("ENERGY_CAP", over, snapshot, game_no, steps, yi)
                reads = list(_READS)
                stats["reads_watched"] += len(reads)
                for stale in check_stale_reads(snapshot, reads):
                    record("STALE_READ", stale, snapshot, game_no, steps, yi)
                for stale in check_stale_flags(snapshot, mod):
                    record("STALE_FLAG", stale, snapshot, game_no, steps, yi)

                if bad and "index" in (bad or ""):
                    break              # an illegal index cannot be resolved
                obs = game.battle_select(choice)
                stats["decisions"] += 1
                steps += 1
        finally:
            game.battle_finish()
        if progress and stats["games"] % progress == 0:
            print(f"  ... {stats['games']}/{games} partidas, "
                  f"{len(findings)} violaciones", flush=True)
    for mod, original in watched:
        _remove_read_watch(mod, original)
    return stats, findings, agents[0]


# --------------------------------------------------------------------------
# Validating the monitor
# --------------------------------------------------------------------------

def _sabotage(mod):
    """Two lies at once: every promise held up, and one card invented.

    The promises must eventually stand on a dead premise, and the extra copy in
    the tracker's deck must show up as a disagreement with `deckCount` -- which
    is the whole point of DECK_BELIEF, so it has to be shown to catch one.
    """
    for name, _why, _p in PROMISES:
        try:
            setattr(mod.AGENT_STATE, name, True)
        except AttributeError:
            pass
    belief = getattr(mod.AGENT_STATE, "ACTIVE_CARDS_IN_DECK", None)
    if belief:
        entry = belief[next(iter(belief))]
        entry[ZONE_DECK] = entry.get(ZONE_DECK, 0) + 1


def _self_test_pure_checkers():
    """The two checkers a saboteur cannot reach, tested on synthetic boards.

    `check_energy_caps` and `check_double_attachment` read the OBSERVATION, and
    the observation is snapshotted before the saboteur runs -- so the only way
    to show they fire is to hand them a board. Both directions are asserted:
    the board that violates and the board that does not, because a checker that
    always fires is as useless as one that never does.
    """
    menu = {"select": {"option": [{"type": ATTACH_OPTION, "area": 2, "index": 0,
                                   "inPlayArea": int(AreaType.BENCH),
                                   "inPlayIndex": 0}]}}
    over = dict(menu, current={"yourIndex": 0, "players": [
        {"active": [], "bench": [{"id": Applin, "energies": [1]}], "hand": []},
    ]})
    if not check_energy_caps(over, _FakeAgentModule(), [0]):
        return ("check_energy_caps did not see a second energy sent to an Applin "
                "that already carries one")
    exempt = dict(menu, current={"yourIndex": 0, "players": [
        {"active": [], "hand": [],
         "bench": [{"id": Applin, "energies": [1]},
                   {"id": Hydrapple_ex, "energies": []}]},
    ]})
    if check_energy_caps(exempt, _FakeAgentModule(), [0]):
        return ("check_energy_caps fired with our Hydrapple ex in play, which is "
                "the documented exception")
    if check_energy_caps(over, _FakeAgentModule(), []):
        return "check_energy_caps fired on a choice that attaches nothing"
    twice = {"current": {"energyAttached": True, "yourIndex": 0, "players": [{}]},
             "select": {"option": [{"type": ATTACH_OPTION}]}}
    if not check_double_attachment(twice, [0]):
        return "check_double_attachment did not see a second attachment"
    if check_double_attachment(twice, []):
        return "check_double_attachment fired on a choice that attaches nothing"
    return None


class _FakeAgentModule:
    """Just enough of an agent module for the pure checkers: no Meganium."""

    class AGENT_STATE:
        meganium_in_play = False


def self_test(games=8, opponent=None):
    print("Auto-test 1/3 (sensibilidad, checkers puros): tableros sinteticos ...",
          flush=True)
    bad = _self_test_pure_checkers()
    if bad:
        print(f"AUTO-TEST FALLIDO: {bad}.", file=sys.stderr)
        return False
    print("  OK: topes y doble adjunte responden en los dos sentidos.", flush=True)

    print("Auto-test 2/3 (sensibilidad): promesas armadas y una carta inventada ...",
          flush=True)
    _stats, findings, _m = over_games(games, opponent=opponent,
                                      saboteur=_sabotage)
    stale = [f for f in findings if f["kind"] == "STALE_FLAG"]
    if not stale:
        print("AUTO-TEST FALLIDO: una promesa sin premisa no se detecto.",
              file=sys.stderr)
        return False
    drift = [f for f in findings if f["kind"] == "DECK_BELIEF"]
    if not drift:
        print("AUTO-TEST FALLIDO: una carta inventada en el mazo no se detecto.",
              file=sys.stderr)
        return False
    print(f"  OK: {len(stale)} STALE_FLAG y {len(drift)} DECK_BELIEF sobre el "
          f"sabotaje.", flush=True)

    print("Auto-test 3/3 (especificidad): sin sabotaje no puede haber indices ilegales ...",
          flush=True)
    stats, honest, _m = over_games(games, opponent=opponent)
    illegal = [f for f in honest if f["kind"] in ("ILLEGAL_INDEX", "AGENT_RAISED")]
    if illegal:
        print(f"AUTO-TEST FALLIDO: {len(illegal)} indices ilegales o excepciones "
              f"en una corrida limpia -- o el agente esta roto, o el checker lo esta.",
              file=sys.stderr)
        for f in illegal[:3]:
            print(f"    {f['kind']}: {f['detail']}", file=sys.stderr)
        return False
    print(f"  OK: {stats['decisions']} decisiones limpias, 0 ilegales.\n", flush=True)
    return True


def dump(findings, where):
    out = Path(where)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for n, f in enumerate(findings):
        name = f"{f['kind'].lower()}_g{f.get('game', 0)}_s{f.get('step', 0)}_{n}.json"
        path = out / name
        path.write_text(json.dumps({"observation": f.pop("observation", None),
                                    "violation": f}, indent=1), encoding="utf-8")
        written.append(str(path))
    return written


def report(stats, findings, mod):
    print("\nMonitor de invariantes")
    print(f"Partidas: {stats['games']}   decisiones: {stats['decisions']}   "
          f"lecturas de promesa vistas: {stats.get('reads_watched', 0)}")
    print(f"Tableros en transito (el motor no cuadra 60, no se juzga el "
          f"seguimiento de cartas): {stats.get('skipped_transit', 0)}")
    if stats.get("skipped_foreign_deck"):
        print(f"Decisiones del asiento que NO juega nuestro mazo (su creencia "
              f"no es sobre su baraja): {stats['skipped_foreign_deck']}")
    pending = unregistered_flags(mod)
    print(f"Promesas con premisa escrita: {len(PROMISES)}   "
          f"banderas booleanas SIN premisa: {len(pending)}")
    if pending:
        print(f"  (sin vigilar: {', '.join(pending)})")
    by_kind = {}
    for f in findings:
        by_kind.setdefault(f["kind"], []).append(f)
    if not findings:
        print("\nViolaciones: NINGUNA. (Los dos auto-tests confirman que el "
              "monitor sabe fallar y sabe callarse.)")
        return
    print("\nViolaciones:")
    for kind, items in sorted(by_kind.items(), key=lambda kv: -len(kv[1])):
        print(f"  {kind}: {len(items)}")
        for f in items[:4]:
            print(f"    partida {f.get('game')} paso {f.get('step')}: {f['detail']}")


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--games", type=int, default=200)
    parser.add_argument("--opponent", default=None)
    parser.add_argument("--dump", default=None)
    parser.add_argument("--progress", type=int, default=None)
    parser.add_argument("--no-self-test", action="store_true")
    parser.add_argument("--self-test-only", action="store_true")
    args = parser.parse_args(argv)

    if not args.no_self_test:
        if not self_test(opponent=args.opponent):
            return 2
        if args.self_test_only:
            return 0

    stats, findings, mod = over_games(args.games, opponent=args.opponent,
                                      progress=args.progress)
    report(stats, findings, mod)
    if args.dump and findings:
        written = dump(findings, args.dump)
        print(f"\n{len(written)} observaciones escritas en {args.dump}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
