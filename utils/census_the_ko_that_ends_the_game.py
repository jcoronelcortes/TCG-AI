"""How often is a turn holding a game-ENDING knockout, and who was the plan pointing at?

THE SENTENCE (`_active_win_plan`). When the attack loop has already chosen the
ACTIVE, the knockout is guaranteed and that knockout ENDS THE GAME -- it takes
the prizes we were missing, or the opponent has no body left to promote -- no
pivot below may move `plan.attacker` off the active. Durability, prize denial and
mismatch are arguments about the NEXT turn, and a turn that closes the game does
not have one.

THE RECORD is episode 93675887 step 173 vs Alakazam (WON in spite of it): one
prize left, our Meganium with four energies in front of a 70 HP Dunsparce, and
the Hydrapple ex pivot took the plan because a 330 HP body on the bench endures
more. With `plan.attacker != 0` the ATTACK menu never reaches its finisher tier
(99000), the winning swing was priced at 1100 and Boss's Orders (5600) won the
turn.

WHAT THIS COUNTS, and why it is the BASELINE that gets measured. The fix makes
the population disappear, so counting it on the fixed agent reports zero and
proves nothing. Each arm plays its own games and every one of OUR main menus is
tallied:

    turns       main menus where our active has an attack it can pay for today.
    lethal      ...of those, the ones where that attack knocks the body in
                front out (the agent's own `_our_effective_damage`, so walls,
                resistance and the Grass doubler are priced exactly as the
                agent prices them).
    ends_game   ...of those, the ones where the knockout ENDS the game: it is
                worth the prizes we are missing, or their bench is empty.
    diverted    ...of those, the ones where `plan.attacker` came out NOT 0 --
                the turn was holding the win and the plan was pointing at
                somebody else. THIS is the population the rule is about.
    thrown      ...of those, the ones where the action actually submitted was
                not that attack: the win was not merely mispriced, it was not
                played.

The `--half` control is the point of the second arm: the same count on lists
that cannot produce the board tells a rule that fires from a real shape apart
from a rule that fires from noise.

Usage:
    python utils/census_the_ko_that_ends_the_game.py --games 60
    python utils/census_the_ko_that_ends_the_game.py --games 60 --base HEAD
    python utils/census_the_ko_that_ends_the_game.py --games 60 \
        --opponent deck/real_opponents/alakazam_1.csv
"""

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "utils")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import selfplay as sp  # noqa: E402
import opponent_bot  # noqa: E402

# The lists the board turns up on most: games that reach a low prize count. A
# spread on purpose -- the deck the record came from, a wall that drags games
# out, a disruptor and a fast deck.
DEFAULT_DECKS = (
    "deck/real_opponents/alakazam_1.csv",
    "deck/opponents/crustle_great_tusk_nz.csv",
    "deck/opponents/marnie_grimmsnarl.csv",
    "deck/opponents/dragapult.csv",
)


class Tally:
    """The spy hung on `agent`, one row per main menu of ours.

    It reads the arm's OWN namespace (through `agent.__globals__`) rather than
    an ambient `import main`: `selfplay.load_agent` gives each arm its own
    module tree, and a census that measured the ambient copy would report the
    noise floor of a module nobody is playing with.
    """

    def __init__(self, agent_module):
        self.mod = agent_module
        self.ns = agent_module.agent.__globals__
        self.turns = 0
        self.lethal = 0
        self.ends_game = 0
        self.diverted = 0
        self.thrown = 0
        self._orig = agent_module.agent

    def install(self):
        def wrapped(obs):
            choice = self._orig(obs)
            try:
                self._tally(obs, choice)
            except Exception:
                pass  # a census may not change the game it is watching
            return choice
        self.mod.agent = wrapped
        return self.mod

    # -- the reading -------------------------------------------------------
    def _tally(self, obs, choice):
        ns = self.ns
        OptionType = ns['OptionType']
        sel = obs.get("select") or {}
        if sel.get("type") != 0:      # MAIN only
            return
        options = sel.get("option") or []
        atk_idx = [i for i, o in enumerate(options)
                   if o.get("type") == int(OptionType.ATTACK)]
        if not atk_idx:
            return

        cur = obs["current"]
        me = cur["players"][cur["yourIndex"]]
        them = cur["players"][1 - cur["yourIndex"]]
        if not me.get("active") or me["active"][0] is None:
            return
        if not them.get("active") or them["active"][0] is None:
            return

        self.turns += 1

        state = ns['to_observation_class'](obs).current
        mine = state.players[cur["yourIndex"]].active[0]
        front = state.players[1 - cur["yourIndex"]].active[0]
        my_bench = [b for b in state.players[cur["yourIndex"]].bench if b is not None]

        # The agent's OWN calculators, so walls, resistance, the Grass doubler
        # and the energy requirement are priced exactly as the agent prices
        # them. A census with a second opinion about the damage measures the
        # disagreement between the two, not the board.
        agent_state = ns['AGENT_STATE']
        doubler = agent_state.meganium_in_play
        unit = 2 if doubler else 1
        grass = sum(len(p.energies) * unit
                    for p in [mine] + my_bench)
        base = ns['_attacker_base_damage'](
            mine.id, front, len(mine.energies) * unit,
            grass_scale=grass, teal_self_energy=len(mine.energies) * unit,
            bench_count=len(my_bench))
        if base <= 0:
            return
        dmg = ns['_our_effective_damage'](mine, front, base, doubler, False)
        if dmg < (front.hp or 0):
            return
        self.lethal += 1

        my_prize = len(me.get("prize") or [])
        bench_empty = not any(b is not None for b in (them.get("bench") or []))
        if not (bench_empty or my_prize <= ns['prize_count_op'](front)):
            return
        self.ends_game += 1

        if agent_state.plan.attacker == 0:
            return
        self.diverted += 1

        if choice and choice[0] not in atk_idx:
            self.thrown += 1

    def row(self, label):
        def pct(n):
            return f"{100.0 * n / self.turns:5.1f}%" if self.turns else "    -"
        return (f"{label:<34} turns {self.turns:5d}  lethal {self.lethal:4d}"
                f"  ends_game {self.ends_game:4d}  diverted {self.diverted:4d}"
                f" ({pct(self.diverted)})  thrown {self.thrown:4d}")


def run(agent_spec, decks, games, label):
    if agent_spec == "main.py":
        arm = sp.load_agent(_ROOT / "main.py", "censo_cand")
    else:
        arm = sp.load_agent_from_git(agent_spec, "censo_base")
    tally = Tally(arm)
    tally.install()
    deck = sp.read_deck()
    per_deck = max(1, games // len(decks))
    for path in decks:
        rival = opponent_bot.OpponentBot()
        rival_deck = sp.read_deck(path)
        for n in range(per_deck):
            if n % 2 == 0:
                sp.play_game(arm, rival, deck, rival_deck)
            else:
                sp.play_game(rival, arm, rival_deck, deck)
    print(tally.row(label))
    return tally


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--base", default=None,
                    help="git ref of a second arm (e.g. HEAD): the population "
                         "the fix removes only exists there")
    ap.add_argument("--opponent", action="append", default=None)
    args = ap.parse_args(argv)

    decks = args.opponent or list(DEFAULT_DECKS)
    run("main.py", decks, args.games, "candidate (working tree)")
    if args.base:
        run(args.base, decks, args.games, f"baseline ({args.base})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
