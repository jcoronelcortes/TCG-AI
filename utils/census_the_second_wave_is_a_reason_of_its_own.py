"""How often the offensive arm of the Festival Grounds pivot fires, and what it
costs the boards it does not belong on.

WHY A CENSUS AND NOT A WINRATE. The change this counts was measured with the
self-play gate first, at N=1000 against `deck/real_opponents/festival_lead_5.csv`,
and the gate cannot resolve it: the candidate read **-0.7 pp** and the CONTROL --
HEAD's own main.py run against HEAD at the same N -- read **-0.4 pp**, with the
prize differential at -0.09 against a floor of -0.06. That is the wall main.py
already names on `switch_off_festival_lead`: *the generic OpponentBot cannot
pilot the Festival Lead deck*, so the board this rule is written for barely
happens in self-play and the rule is measured on the games where it never fired.
What arbitrates instead is FREQUENCY -- how often the arm is even asked, how
often it fires, and the flat zero it has to show on every deck that does not
bring the stadium.

WHAT IT COUNTS, per menu of ours (one row per scored option is collapsed to one
row per menu by counting the RETREAT option only once):

    stadium    Festival Grounds is on the field: the only gate every path here
               lives behind
    pays       `_festival_lead_pays_us_now`: a Dipplin of ours can throw Do the
               Wave at their Active this turn and knock it out
    reserve    `_festival_wave_needs_the_grass`: that Dipplin is UNCHARGED and
               the hand holds the single Grass that charges it -- the card Teal
               Dance used to bank on a benched Ogerpon
    outprizes  `_festival_wave_outprizes_the_front`: every body they can promote
               dies to the same wave, so the swap cashes TWO prizes where the
               body in front is worth one. This is the arm that is new; the
               defensive arm (`active_ko_likely`) is not counted here because it
               predates the change.

THE INERTNESS CLAIM IS THE SECOND HALF, and it is why `--control` exists: the
same counters against a deck that does not carry Festival Grounds must all read
ZERO. Not "small" -- zero, by construction, because `_festival_grounds_in_play`
gates every path and no other list in `deck/opponents/` plays that stadium.

Usage:
    python utils/census_the_second_wave_is_a_reason_of_its_own.py --games 60
    python utils/census_the_second_wave_is_a_reason_of_its_own.py --games 60 \
        --decks deck/real_opponents/festival_lead_1.csv
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import main as m  # noqa: E402

_DEFAULT_DECKS = ["deck/real_opponents/festival_lead_5.csv",
                  "deck/real_opponents/festival_lead_1.csv"]
# The control deck: any list that does not bring the stadium. Marnie is the one
# the rest of the estate uses as its neutral matchup.
_CONTROL_DECK = "deck/opponents/marnie_grimmsnarl.csv"


def census(decks, games, progress=False):
    """Counts over self-play. Returns the Counter so a caller can assert on it."""
    import selfplay as sp
    from opponent_bot import OpponentBot

    agent = sp.load_agent(_ROOT / "main.py", "census_second_wave")
    counts = Counter()
    plain = agent.score_option

    def counted(tc, option, score):
        out = plain(tc, option, score)
        # ONE ROW PER MENU, not per option: the RETREAT option appears exactly
        # once in a MAIN menu, so counting on it is the cheapest way to make the
        # numbers menus and not options. A menu with no retreat is a menu where
        # this pivot could not have fired anyway.
        if option.type != int(m.OptionType.RETREAT):
            return out
        # THE STATE OF THE AGENT UNDER TEST, not this module's. `load_agent`
        # gives the instance its own `ptcg` tree on purpose, so `m.AGENT_STATE`
        # here is a DIFFERENT singleton that no game ever writes to -- reading it
        # is how a census reports a flat zero for a flag that was firing.
        if getattr(agent.AGENT_STATE, "_festival_grounds_in_play", False):
            counts["stadium"] += 1
            if getattr(tc, "_festival_lead_pays_us_now", False):
                counts["pays"] += 1
            if getattr(tc, "_festival_wave_needs_the_grass", False):
                counts["reserve"] += 1
            if getattr(tc, "_festival_wave_outprizes_the_front", False):
                counts["outprizes"] += 1
        counts["menus"] += 1
        return out

    agent.score_option = counted
    for deck in decks:
        their_deck = sp.read_deck(_ROOT / deck)
        for i in range(games):
            counts["games"] += 1
            # SEATS ALTERNATE, like the gate's: the stadium reaches the board on
            # the opponent's turn, so which seat moves first changes how many of
            # our menus ever see it.
            if i % 2 == 0:
                sp.play_game(agent, OpponentBot(), deck1=their_deck)
            else:
                sp.play_game(OpponentBot(), agent, deck0=their_deck)
            if progress and (i + 1) % 20 == 0:
                print(f"  ... {deck} {i + 1}/{games}", flush=True)
    return counts


def report(counts, label):
    print(f"\n{label}")
    print(f"  games                       {counts['games']}")
    print(f"  menus with a retreat        {counts['menus']}")
    print(f"  ...stadium on the field     {counts['stadium']}")
    print(f"  ...the wave is lethal       {counts['pays']}")
    print(f"  ...the Grass is reserved    {counts['reserve']}")
    print(f"  ...and it OUT-PRIZES front  {counts['outprizes']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--games", type=int, default=40,
                    help="games per deck")
    ap.add_argument("--decks", nargs="*", default=_DEFAULT_DECKS)
    ap.add_argument("--control", default=_CONTROL_DECK,
                    help="a deck WITHOUT the stadium; every counter must be 0")
    ap.add_argument("--no-control", action="store_true")
    ap.add_argument("--progress", action="store_true")
    args = ap.parse_args(argv)

    report(census(args.decks, args.games, args.progress), "FESTIVAL LEAD")
    if not args.no_control:
        control = census([args.control], args.games, args.progress)
        report(control, f"CONTROL ({args.control})")
        bad = [k for k in ("stadium", "pays", "reserve", "outprizes")
               if control[k]]
        if bad:
            print(f"\n  ⚠️  the control is NOT inert: {bad}")
            return 1
        print("\n  the control is inert: the stadium gates every path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
