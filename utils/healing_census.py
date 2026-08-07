"""How much of the damage we deal gets healed back before it kills anything?

THE QUESTION. Fifty-five of the ninety-seven real lists carry healing -- every
single Crustle list runs six to eleven cards of it (Jumbo Ice Cream, Hilda, Cook,
Waitress, Potion) -- and the agent does not read one of them. That is not
automatically a hole: the HP in the observation is always current, so no
projection is ever WRONG. What it can be is a bad plan. A rule that reads "the
wall is at 30, it is not a wall any more" is reading a fact that their next
Supporter deletes.

Before writing a rule about it, this counts whether it happens. Per opposing
body, followed by serial across the whole game:

  * DAMAGE WE DEALT       the drops in its hit points on our turns
  * DAMAGE HEALED BACK    the rises, which only a card can produce
  * WOUNDED AND NEVER KILLED   bodies we damaged that were still alive at the end

The number that matters is the ratio: damage that never became a prize. Against
an opponent with no healing it measures the noise floor of the method itself
(evolutions raise maximum HP, which is not healing and is excluded by comparing
same-serial hit points only).

Usage:
    python utils/healing_census.py --opponent deck/real_opponents/crustle_wall_6.csv
    python utils/healing_census.py --opponent ... --games 200
"""

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cg import game  # noqa: E402

import selfplay as sp  # noqa: E402


def _their_bodies(obs, seat):
    """{serial: (card id, hp)} for every opposing body in play."""
    current = obs["current"]
    them = current["players"][1 - seat]
    out = {}
    for body in (them.get("active") or []) + (them.get("bench") or []):
        if body:
            out[body["serial"]] = (body["id"], body["hp"])
    return out


def run(games, opponent):
    driver = sp.load_agent(str(_ROOT / "main.py"), "healing_census")
    deck = sp.read_deck()
    if opponent:
        from opponent_bot import OpponentBot
        rival, rival_deck = OpponentBot(), sp.read_deck(opponent)
    else:
        rival, rival_deck = sp.load_agent(str(_ROOT / "main.py"), "healing_rival"), deck

    totals = Counter()
    healed_by_card = Counter()
    for i in range(games):
        sp._reset_si_aplica(driver)
        sp._reset_si_aplica(rival)
        seat = i % 2
        decks = (deck, rival_deck) if seat == 0 else (rival_deck, deck)
        obs, _sd = game.battle_start(list(decks[0]), list(decks[1]))
        if obs is None:
            continue
        agents = {seat: driver, 1 - seat: rival}
        last = {}
        wounded = defaultdict(int)
        steps = 0
        try:
            while obs and obs["current"]["result"] == -1 and steps < 3000:
                now = _their_bodies(obs, seat)
                for serial, (card_id, hp) in now.items():
                    if serial in last:
                        before = last[serial]
                        if hp < before:
                            totals["damage_dealt"] += before - hp
                            wounded[serial] += before - hp
                        elif hp > before:
                            totals["damage_healed"] += hp - before
                            healed_by_card[card_id] += hp - before
                            wounded[serial] = max(0, wounded[serial] - (hp - before))
                    last[serial] = hp
                # a body that leaves the board was knocked out (or shuffled back)
                for serial in list(last):
                    if serial not in now:
                        totals["bodies_that_left"] += 1
                        wounded.pop(serial, None)
                        last.pop(serial)
                choice = agents[obs["current"]["yourIndex"]].agent(obs)
                obs = game.battle_select(choice)
                steps += 1
        finally:
            game.battle_finish()
        totals["bodies_wounded_alive_at_the_end"] += sum(
            1 for v in wounded.values() if v > 0)
        totals["damage_stranded_at_the_end"] += sum(wounded.values())
    return totals, healed_by_card


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--opponent", default=None)
    args = parser.parse_args(argv)
    totals, by_card = run(args.games, args.opponent)

    dealt = totals["damage_dealt"] or 1
    print(f"\nopponent: {args.opponent or 'mirror'}   games: {args.games}")
    print(f"  damage we dealt to their bodies   {totals['damage_dealt']:8d}")
    print(f"  damage healed back                {totals['damage_healed']:8d}"
          f"   ({100 * totals['damage_healed'] / dealt:5.1f}% of it)")
    print(f"  damage stranded on live bodies    "
          f"{totals['damage_stranded_at_the_end']:8d}"
          f"   ({100 * totals['damage_stranded_at_the_end'] / dealt:5.1f}%)")
    print(f"  bodies that left the board        {totals['bodies_that_left']:8d}")
    print(f"  bodies wounded and still alive    "
          f"{totals['bodies_wounded_alive_at_the_end']:8d}")
    if by_card:
        from cg.api import all_card_data
        names = {c.cardId: c.name for c in all_card_data()}
        print("  healed, by the body that received it:")
        for card_id, amount in by_card.most_common(6):
            print(f"    {names.get(card_id, card_id):28s} {amount:7d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
