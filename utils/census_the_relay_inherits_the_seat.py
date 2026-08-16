"""How often the gust picks the seat the relay inherits instead of the trap.

THE BOARD IT COMES FROM (episode 93486866 vs Marnie's Grimmsnarl ex, LOST; drawn
out in full in `tests/test_the_relay_inherits_the_seat.py`), in one line: step
72, turn 8, six prizes each -- our Tapu Bulu at 20/140 with no energy in front of
three charged Teal Mask Ogerpon ex it will not let past, and the agent gusted a
bare Munkidori that could not attack, so their knockout never came and the seat
stayed shut. The two-prize Grimmsnarl ex with five energies, which a benched
Ogerpon knocks out for 540, scored last of the four candidates.

WHAT IS BEING COUNTED. The candidate arm drives the game; a NEUTRALISED copy of
the same tree is asked for its own choice on the same observation, exactly as
`utils/shadow.py` does, so both see the identical stream of frames and their
tracking evolves together. Per one of OUR decisions:

    ours        decisions the agent took (the denominator)
    menu        ...that were a Boss's Orders TARGET menu -- where the rule
                chooses WHICH body
    flip        ...where the neutralised copy played something ELSE. This is the
                population: the boards where the rule changes a decision at all

The rule speaks in TWO places, so a flip is attributed to whichever one it lands
on and everything left over is a knock-on. Telling the three apart is the whole
point -- a turn that goes differently AFTER a swap it did not make is not
evidence about the swap:

    aim         a flip on a TARGET menu where the body the candidate arm took is
                worth MORE prizes than the one the baseline took
    play        a flip on a menu where the candidate arm PLAYS the Boss's and the
                baseline does not. This is the half the recorded board needed:
                without it the ladder falls to `no_value` and ends the turn with
                the exchange still on the table
    other       the remainder. Knock-ons, and a tie-break inside the same prize
                count

NO LEAKAGE HALF, and that is a property of the rule and not an omission: nothing
in `relay_cashes_the_seat` names a card, an archetype or a matchup flag. It reads
our active's attack and retreat costs, their candidate's attack, our bench's
damage and the two prize counts. So there is no matchup it is allowed to reach
past -- the honest second reading is a DIFFERENT list, and it says how much of
the meta the state actually occurs in.

WHAT IT HAS READ (15 August 2026, 200 games a row):

    list                  menus/game   flips/game   aim    play   other
    marnie_grimmsnarl_1      1.22         0.06        9      0       2
    alakazam_1               1.70         0.00        --     --      --

THE PLAY COLUMN IS ZERO AND THAT IS THE READING, not a broken counter (both
detectors are exercised on the two fixtures of
`tests/test_the_relay_inherits_the_seat.py`). It says the two halves of the card
overlap almost perfectly in practice: wherever the relay state exists, the TRAP
reason has already bought the Supporter, so the play rung changes nothing it was
not going to play anyway. It earns its place as a CONSISTENCY fix -- strip the
trappable bodies from the recorded board and the ladder falls to `no_value` and
ends the turn with the exchange intact -- and not as a source of new plays.

The zero against Alakazam is the matchup and not a blind spot:
`alakazam_line_do_not_promote_the_attacker` is a FORBID above this rung, so the
rule never gets to decide there.

NOT A CONTROL GROUP. `flip` is a decision that changed, not a game that was won:
the winrate question has its own two-arm gate with a `--control` row at the same
N (`utils/gate_the_relay_inherits_the_seat.py`).

⚠️ THE CRITERION, written before this file was run and not moved afterwards:
`flip` at or above **0.05 per game** -- one board in twenty games. The prior that
says the bar is the right order of magnitude, and not a bar drawn around a number
already seen: the frozen corpus reaches ONE Boss's target menu in this state
across its 3 580 decisions, so anything at or above a board in twenty games is
already an order of magnitude more exposure than the record that found it.

Usage:
    python utils/census_the_relay_inherits_the_seat.py --games 200
    python utils/census_the_relay_inherits_the_seat.py --games 200 \
        --opponent deck/real_opponents/alakazam_1.csv
"""

import argparse
import copy
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "tests", _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp                                     # noqa: E402
from cg.api import OptionType, SelectContext              # noqa: E402
from ptcg.cards.ids import Boss_Orders as BOSS_ORDERS      # noqa: E402
from ptcg.cards.tables import card_table                  # noqa: E402
from gate_the_relay_inherits_the_seat import arm          # noqa: E402

DEFAULT_OPPONENT = "deck/real_opponents/marnie_grimmsnarl_1.csv"


def _gust_menu(obs, my_index):
    """Is this frame the TARGET menu of a Boss's Orders?"""
    sel = (obs.get("select") or {})
    if sel.get("context") != int(SelectContext.SWITCH):
        return False
    options = sel.get("option") or []
    return bool(options) and all(
        o.get("type") == int(OptionType.CARD) and o.get("area") == 5
        and o.get("playerIndex") != my_index
        for o in options)


def _plays_the_boss(obs, choice):
    """Does `choice` play a Boss's Orders out of our hand?"""
    if not choice:
        return False
    options = (obs.get("select") or {}).get("option") or []
    if choice[0] >= len(options):
        return False
    o = options[choice[0]]
    if o.get("type") != int(OptionType.PLAY):
        return False
    hand = obs["current"]["players"][obs["current"]["yourIndex"]].get("hand") or []
    idx = o.get("index")
    return (idx is not None and idx < len(hand)
            and hand[idx]["id"] == BOSS_ORDERS)


def _prizes_of(obs, choice):
    """Prizes the chosen gust target hands over, 0 if it cannot be read."""
    if not choice:
        return 0
    options = (obs.get("select") or {}).get("option") or []
    if choice[0] >= len(options):
        return 0
    o = options[choice[0]]
    bench = obs["current"]["players"][o["playerIndex"]]["bench"]
    if o["index"] >= len(bench) or bench[o["index"]] is None:
        return 0
    return _prize_count(bench[o["index"]])


def _prize_count(pkmn):
    """Prizes a body on their bench pays, read off the card table."""
    data = card_table.get(pkmn["id"])
    if data is None:
        return 1
    if getattr(data, "megaEx", False):
        return 3
    return 2 if getattr(data, "ex", False) else 1


def census_game(driver, shadow, deck0, deck1, counts, max_steps=3000):
    """One game driven by `driver`, with `shadow` asked on every frame."""
    from cg import game

    for mod in (driver, shadow):
        sp._reset_si_aplica(mod)
    obs, sd = game.battle_start(list(deck0), list(deck1))
    if obs is None:
        raise RuntimeError(f"battle_start failed: {sd.errorType}")
    steps = 0
    while obs["current"]["result"] == -1 and steps < max_steps:
        choice = driver.agent(obs)
        mirror = shadow.agent(copy.deepcopy(obs))
        counts['ours'] += 1
        menu = _gust_menu(obs, obs["current"]["yourIndex"])
        if menu:
            counts['menu'] += 1
        if list(mirror) != list(choice):
            counts['flip'] += 1
            if menu and _prizes_of(obs, choice) > _prizes_of(obs, mirror):
                counts['aim'] += 1
            elif _plays_the_boss(obs, choice) and not _plays_the_boss(obs, mirror):
                counts['play'] += 1
            else:
                counts['other'] += 1
        obs = game.battle_select(choice)
        steps += 1
    return obs["current"]["result"]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--opponent", default=DEFAULT_OPPONENT)
    ap.add_argument("--progress", type=int, default=50)
    args = ap.parse_args(argv)

    driver = arm("census_candidate", True)
    shadow = arm("census_baseline", False)

    own = sp.read_deck()
    theirs = sp.read_deck(_ROOT / args.opponent)

    counts = Counter()
    for i in range(args.games):
        # The seat alternates so the census is not a reading of one half of the
        # game (docs/improving-the-agent.md: the seat is worth a point where the
        # winrate saturates and five in the contested matchups).
        d0, d1 = (own, theirs) if i % 2 == 0 else (theirs, own)
        census_game(driver, shadow, d0, d1, counts)
        if args.progress and (i + 1) % args.progress == 0:
            print(f"  ... {i + 1}/{args.games}", flush=True)

    n = args.games or 1
    print(f"\n{args.games} games against {Path(args.opponent).stem}")
    print(f"  our decisions                       {counts['ours']:6d} "
          f"({counts['ours'] / n:7.2f}/game)")
    print(f"  ...that were a gust TARGET menu     {counts['menu']:6d} "
          f"({counts['menu'] / n:7.2f}/game)")
    print(f"  ...the neutral arm played OTHERWISE {counts['flip']:6d} "
          f"({counts['flip'] / n:7.2f}/game)   <- THE WRITTEN CRITERION")
    print(f"      AIM   a target worth MORE prizes {counts['aim']:6d} "
          f"({counts['aim'] / n:7.2f}/game)")
    print(f"      PLAY  a Boss's the base declined {counts['play']:6d} "
          f"({counts['play'] / n:7.2f}/game)")
    print(f"      other knock-ons and same-prize   {counts['other']:6d} "
          f"({counts['other'] / n:7.2f}/game)")
    rate = counts['flip'] / n
    print("\n" + ("BELOW the criterion (0.05/game, written before running this)."
                  if rate < 0.05 else
                  "ABOVE the criterion. The winrate still needs its own gate "
                  "with a --control arm at the same N."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
