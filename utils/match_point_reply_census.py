"""When the knockout we take is the one that loses the game: is there anything
left to write a rule about, and does the projection that says so come true?

WHERE THIS PICKS UP. `utils/promoted_reply_census.py` counted the nested
populations down to "and a surviving relay had the SAME knockout" -- the board
`_relay_saves_the_game` (ptcg/turn/options/retreat.py) now acts on, 8 of 3674
decisions. What it left uncounted is the REMAINDER of the same shelf: the boards
where their promoted reply closes their count, a retreat is on the menu, and no
benched body takes that knockout -- but one of them would still be STANDING when
the reply lands. Retreating there gives up a prize to survive. That is a
different and much more expensive play than the one already written, and this
tool is the cheap half of deciding whether it is worth measuring properly.

It answers the two questions in one pass, and the second one is the point.

  1. THE POPULATION. Of the boards where `op_wins_after_ko` is true, with an
     attack and a retreat both on the menu, how do they split:

        SAME_KO     a relay takes the same knockout and outlasts the reply
                    (already covered, and it costs nothing: the prize is
                    collected either way)
        SURVIVOR    no relay takes the knockout, but a benched body outlasts
                    the reply -- the candidate rule's population
        NOTHING     every body we could put in front dies to the same reply:
                    the game is lost and no retreat saves it

  2. DOES THE PROJECTION COME TRUE? A population is not a licence. The flag is a
     PREDICTION -- "they close it on the reply" -- and the defensive machinery
     of this agent has measured negative three separate times when it was made
     to fire on readings that were not as good as they looked. So for every
     board where the flag was true and we ATTACKED anyway, this records what
     actually happened:

        CLOSED     the game ended in a loss on their very next turn -- the
                   projection was right and the prize we took was the last thing
                   we did
        LOST LATER we lost, but not there
        SURVIVED   we did not lose on the reply at all: the projection was
                   pessimistic, and a rule that pays a prize for it is paying
                   for nothing

     Read `CLOSED` against the run's own baseline loss rate. A bad board is a
     bad board; what would justify the rule is the reply arriving ON SCHEDULE,
     not merely a losing game around it.

MEASURED, and it closed the question it was built to open. 300 mirror games
(19 018 decisions) and 300 games over the 87 real opponent decks (20 660):

                                              mirror        real opponents
    the shelf                              248 (1.30%)          5 (0.02%)
      SAME_KO                                5                  0
      SURVIVOR                               9                  0
      NOTHING                              234 (94.4%)          5
    attacked and the game CLOSED on the
    reply (NOTHING bucket, the only one
    with a sample)                        32 of 59 (54.2%)    1 of 1

Two readings, and both point the same way. The shelf is almost entirely boards
that were ALREADY lost -- 94% of it -- so a rule has 3.6% of it to live in, which
is 9 decisions in 19 018, and only ONE of those nine was the attack-or-retreat
decision at all (the other eight are mid-turn menus where the flag is true and
the agent is doing something else). And the flag is a COIN FLIP as a prediction:
it says the reply ends the game, and the reply ends the game a little over half
the time.

That is the asymmetry that decided the shape of the rule that WAS written.
`_relay_saves_the_game` pays the retreat's energy and cashes the same prize
either way, so a reading that is right half the time still never costs a prize.
Paying a prize to survive on the same reading -- the wider pivot this tool was
built to price -- would be paying it for a coin flip, on a population of one
decision in nineteen thousand. Dropped before it was written.

Usage:
    python utils/match_point_reply_census.py --games 300
    python utils/match_point_reply_census.py --games 200 --mirror
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cg import game  # noqa: E402
from cg.api import OptionType  # noqa: E402

import selfplay as sp  # noqa: E402

SAME_KO = "SAME_KO"
SURVIVOR = "SURVIVOR"
NOTHING = "NOTHING"


class Census:

    def __init__(self, m):
        self.m = m
        self.n = Counter()
        self.boards = []          # one row per flagged board
        self.games = []           # one row per game: result and its flagged boards
        self.pending = []         # flagged boards of the game being played

    # -- per decision ---------------------------------------------------
    def observe(self, obs, choice):
        m = self.m
        plan = getattr(m.AGENT_STATE, "turn_plan", None)
        if plan is None:
            return
        self.n["decisions"] += 1
        if not getattr(plan, "op_wins_after_ko", False):
            return
        self.n["reply_closes_their_count"] += 1

        select = obs.get("select") or {}
        options = select.get("option") or []
        has = {o.get("type") for o in options}
        if int(OptionType.RETREAT) not in has or int(OptionType.ATTACK) not in has:
            self.n["no_retreat_offered"] += 1
            return
        self.n["retreat_was_on_the_menu"] += 1

        bucket = self._classify(obs)
        self.n[bucket] += 1
        chose = self._label(options, choice)
        row = {
            "turn": obs["current"]["turn"],
            "their_prizes": plan.op_prize,
            "bucket": bucket,
            "chose": chose,
        }
        self.boards.append(row)
        # Only an ATTACK leaves the doomed body in front; the prediction is
        # about what happens next, so a turn that retreated is not a test of it.
        if chose == "ATTACK":
            self.n[f"{bucket}_attacked"] += 1
            self.pending.append(row)

    def _classify(self, obs):
        """SAME_KO / SURVIVOR / NOTHING for the bench we have right now."""
        m = self.m
        st = m.to_observation_class(obs).current
        mine = st.players[st.yourIndex]
        theirs = st.players[1 - st.yourIndex]
        active = (mine.active or [None])[0]
        op_active = (theirs.active or [None])[0]
        if active is None or op_active is None:
            return NOTHING

        hand = getattr(theirs, "handCount", None)
        reply = m._promoted_reply_damage(mine, theirs, hand)
        bench_n = sum(1 for p in (mine.bench or []) if p is not None)
        total_grass = m.count_total_grass_energy(mine)
        grass_after = max(0, total_grass - m._retreat_grass_units(
            m.RETREAT_COST.get(active.id, 1)))

        # The same predicate the rule uses, so the two cannot drift apart.
        if m._bench_finisher_that_survives(
                mine, op_active, m.AGENT_STATE.meganium_in_play, bench_n,
                grass_after, False, reply, m.prize_count(active)):
            return SAME_KO
        # ... and the wider question: anything at all that is still standing.
        for body in (mine.bench or []):
            if body is None:
                continue
            if m.prize_count(body) > m.prize_count(active):
                continue
            if (body.hp or 0) > reply:
                return SURVIVOR
        return NOTHING

    def _label(self, options, choice):
        if not choice or choice[0] >= len(options):
            return "?"
        return OptionType(options[choice[0]]["type"]).name

    # -- per game -------------------------------------------------------
    def finish_game(self, result, last_turn):
        """`result`: 1 we won, 0 we lost, None the step cap cut the game off."""
        if result is None:
            self.n["games_unfinished"] += 1
            self.pending = []
            return
        self.n["games"] += 1
        if result == 0:
            self.n["games_lost"] += 1
        for row in self.pending:
            # `turn` counts one per PLAYER turn, so their reply is `turn + 1`;
            # +2 leaves room for the promotion the knockout forces.
            if result == 0 and last_turn <= row["turn"] + 2:
                verdict = "CLOSED"
            elif result == 0:
                verdict = "LOST_LATER"
            else:
                verdict = "SURVIVED"
            self.n[f"{row['bucket']}_{verdict}"] += 1
            row["verdict"] = verdict
        self.pending = []

    # -- report ---------------------------------------------------------
    def report(self):
        n = self.n
        base = n["decisions"] or 1
        print(f"\ndecisions seen                            {n['decisions']:7d}")
        for key, label in (
                ("reply_closes_their_count",
                 "their promoted reply closes their count"),
                ("retreat_was_on_the_menu", "... with attack AND retreat offered")):
            print(f"{label:42s} {n[key]:7d}  ({100 * n[key] / base:5.2f}%)")
        if n["no_retreat_offered"]:
            print(f"{'(closed, no retreat offered)':42s} {n['no_retreat_offered']:7d}")

        shelf = n["retreat_was_on_the_menu"] or 1
        print("\n   how that shelf splits:")
        for bucket, label in (
                (SAME_KO, "SAME_KO   relay takes the same KO (rule exists)"),
                (SURVIVOR, "SURVIVOR  no KO, but a body outlasts the reply"),
                (NOTHING, "NOTHING   everything dies to the same reply")):
            print(f"   {label:52s} {n[bucket]:5d}  ({100 * n[bucket] / shelf:5.1f}% "
                  f"of the shelf, {100 * n[bucket] / base:.2f}% of decisions)")

        print(f"\ngames played {n['games']}, lost {n['games_lost']} "
              f"({100 * n['games_lost'] / max(1, n['games']):.1f}% baseline loss rate)")
        print("\n   and when we ATTACKED on one of those boards, what happened:")
        for bucket in (SAME_KO, SURVIVOR, NOTHING):
            attacked = n[f"{bucket}_attacked"]
            if not attacked:
                print(f"   {bucket:9s} attacked {attacked:5d}")
                continue
            closed = n[f"{bucket}_CLOSED"]
            later = n[f"{bucket}_LOST_LATER"]
            alive = n[f"{bucket}_SURVIVED"]
            print(f"   {bucket:9s} attacked {attacked:5d}   "
                  f"CLOSED on the reply {closed:5d} ({100 * closed / attacked:5.1f}%)   "
                  f"lost later {later:5d}   survived {alive:5d}")

        rows = [b for b in self.boards if b["bucket"] == SURVIVOR][:15]
        if rows:
            print("\n   SURVIVOR boards (the candidate rule's population):")
            for b in rows:
                print(f"     turn {b['turn']:3d}  their prizes {b['their_prizes']}  "
                      f"chose {b['chose']:8s} -> {b.get('verdict', '-')}")


def run(games, opponents=None, mirror=False, progress=50):
    m = sp.load_agent(str(_ROOT / "main.py"), "census_match_point")
    deck = sp.read_deck()
    decks = []
    if not mirror:
        for path in sorted((_ROOT / (opponents or "deck/real_opponents")).glob("*.csv")):
            try:
                sp.read_deck(path)
            except (ValueError, IndexError):
                continue
            decks.append(path)
    if mirror or not decks:
        rival = sp.load_agent(str(_ROOT / "main.py"), "census_rival")
        rival_decks = [None]
    else:
        from opponent_bot import OpponentBot
        rival, rival_decks = OpponentBot(), decks

    census = Census(m)
    for i in range(games):
        sp._reset_si_aplica(m)
        sp._reset_si_aplica(rival)
        path = rival_decks[i % len(rival_decks)]
        their = deck if path is None else sp.read_deck(path)
        seat = i % 2
        d0, d1 = (deck, their) if seat == 0 else (their, deck)
        obs, _sd = game.battle_start(list(d0), list(d1))
        if obs is None:
            continue
        agents = {seat: m, 1 - seat: rival}
        steps, last_turn, result = 0, 0, None
        try:
            while obs and obs["current"]["result"] == -1 and steps < 3000:
                yi = obs["current"]["yourIndex"]
                last_turn = obs["current"]["turn"]
                choice = agents[yi].agent(obs)
                if yi == seat:
                    census.observe(obs, choice)
                obs = game.battle_select(choice)
                steps += 1
            if obs is not None:
                # `result` is the WINNING SEAT once the game is over, which is
                # how utils/selfplay.py reads it (`"ganador": winner`), not a
                # per-seat 0/1. -1 means the step cap was hit, and a game that
                # never finished is not evidence about a reply arriving.
                raw = obs["current"]["result"]
                result = None if raw == -1 else (1 if raw == seat else 0)
                last_turn = obs["current"]["turn"]
        finally:
            game.battle_finish()
        census.finish_game(result, last_turn)
        if progress and (i + 1) % progress == 0:
            print(f"  ... {i+1}/{games}  decisions={census.n['decisions']} "
                  f"shelf={census.n['retreat_was_on_the_menu']}")
    return census


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--games", type=int, default=300)
    parser.add_argument("--opponents", default="deck/real_opponents")
    parser.add_argument("--mirror", action="store_true",
                        help="play the agent against itself instead")
    parser.add_argument("--progress", type=int, default=50)
    args = parser.parse_args(argv)
    run(args.games, args.opponents, args.mirror, args.progress).report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
