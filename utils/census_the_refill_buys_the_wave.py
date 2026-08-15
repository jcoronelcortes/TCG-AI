"""How often the refill is asked to buy the wave, and what it costs elsewhere.

WHY A CENSUS AND NOT A WINRATE FIRST. This is the same wall
`utils/census_the_second_wave_is_a_reason_of_its_own.py` names and main.py
writes on `switch_off_festival_lead`: *the generic OpponentBot cannot pilot the
Festival Lead deck*, so the board the rule is written for is rare in self-play
and a winrate measures the games where the flag never fired. What arbitrates
first is FREQUENCY -- how often the reading is even asked, how often it fires,
and the flat zero it owes every list that does not bring the stadium.

WHAT IT COUNTS, one row per menu of ours (the RETREAT option appears exactly
once in a MAIN menu, so counting on it turns options into menus):

    stadium     Festival Grounds is on the field -- the gate every path here
                lives behind
    pays        `_festival_lead_pays_us_now`: the wave ALREADY knocks their
                Active out. Where this is true the new reading stands aside by
                construction, and the old veto is the one doing the work
    refill      `_festival_refill_buys_the_wave`: the wave does NOT reach yet,
                the bench has seats, at a full bench it would bury their Active
                and every body they could promote behind it, and the Supporter
                slot still holds Lillie's Determination
    changed     ...and the menu really held one of the two decisions the flag
                moves: an EVOLVE onto a Dipplin of ours, or Lillie's itself.
                This is the honest population -- a flag that fires on a menu
                with neither option changes nothing.

THE INERTNESS CLAIM IS THE SECOND HALF, and it is what `--control` is for: on a
deck that cannot put Festival Grounds on the field every counter must read
ZERO. Not "small" -- zero, because `_festival_grounds_in_play` gates the block.

Usage:
    python utils/census_the_refill_buys_the_wave.py --games 60
    python utils/census_the_refill_buys_the_wave.py --games 60 \
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

_DEFAULT_DECKS = ["deck/real_opponents/festival_lead_1.csv",
                  "deck/real_opponents/festival_lead_5.csv"]
# Any list that does not bring the stadium. Marnie is the neutral matchup the
# rest of the estate uses as its control.
_CONTROL_DECK = "deck/opponents/marnie_grimmsnarl.csv"


def census(decks, games, progress=False):
    """Counts over self-play. Returns the Counter so a caller can assert on it."""
    import selfplay as sp
    from opponent_bot import OpponentBot

    agent = sp.load_agent(_ROOT / "main.py", "census_refill_wave")
    counts = Counter()
    plain = agent.score_option

    def counted(tc, option, score):
        out = plain(tc, option, score)
        if option.type != int(m.OptionType.RETREAT):
            return out
        # THE STATE OF THE AGENT UNDER TEST, not this module's: `load_agent`
        # gives the instance its own `ptcg` tree, so `m.AGENT_STATE` here is a
        # different singleton no game ever writes to.
        if getattr(agent.AGENT_STATE, "_festival_grounds_in_play", False):
            counts["stadium"] += 1
            if getattr(tc, "_festival_lead_pays_us_now", False):
                counts["pays"] += 1
            if getattr(tc, "_festival_refill_buys_the_wave", False):
                counts["refill"] += 1
                if _menu_holds_a_decision(agent, tc):
                    counts["changed"] += 1
        counts["menus"] += 1
        return out

    agent.score_option = counted
    for deck in decks:
        their_deck = sp.read_deck(_ROOT / deck)
        for i in range(games):
            counts["games"] += 1
            # SEATS ALTERNATE: the stadium reaches the board on the opponent's
            # turn, so who moves first changes how many of our menus see it.
            if i % 2 == 0:
                sp.play_game(agent, OpponentBot(), deck1=their_deck)
            else:
                sp.play_game(OpponentBot(), agent, deck0=their_deck)
            if progress and (i + 1) % 20 == 0:
                print(f"  ... {deck} {i + 1}/{games}", flush=True)
    return counts


def _menu_holds_a_decision(agent, tc):
    """Does THIS menu offer one of the two options the flag moves?

    Read off the option list rather than the board, for the same reason
    `_evolution_also_fits_the_bench` does: the menu is the authority on what was
    actually legal, and a flag that fires where neither option exists has not
    changed a decision.
    """
    obs = getattr(tc, "obs", None)
    select = getattr(tc, "select", None)
    my_index = getattr(tc, "my_index", None)
    if obs is None or select is None or my_index is None:
        return False
    for o in (getattr(select, "option", None) or []):
        if o.type == int(agent.OptionType.EVOLVE):
            body = agent.get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            if body is not None and body.id == agent.Dipplin:
                return True
        elif o.type == int(agent.OptionType.PLAY):
            card = agent.get_card(obs, agent.AreaType.HAND, o.index, my_index)
            if card is not None and card.id == agent.Lillie_Determination:
                return True
    return False


def report(counts, label):
    games = counts["games"] or 1
    print(f"\n{label}")
    print(f"  games                        {counts['games']}")
    print(f"  menus with a retreat         {counts['menus']}")
    print(f"  ...stadium on the field      {counts['stadium']}")
    print(f"  ...the wave already reaches  {counts['pays']}")
    print(f"  ...THE REFILL BUYS IT        {counts['refill']}"
          f"   ({counts['refill'] / games:.3f}/game)")
    print(f"  ...and the menu held it      {counts['changed']}"
          f"   ({counts['changed'] / games:.3f}/game)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--games", type=int, default=40, help="games per deck")
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
        bad = [k for k in ("stadium", "pays", "refill", "changed") if control[k]]
        if bad:
            print(f"\n  ⚠️  the control is NOT inert: {bad}")
            return 1
        print("\n  the control is inert: the stadium gates the block.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
