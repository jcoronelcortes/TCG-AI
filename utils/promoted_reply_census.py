"""How often is the knockout we are about to take the one that loses the game?

THE QUESTION. `build_turn_plan` switches its whole defensive half off on the
boards where our own attack knocks their active out: the body that would reply
is on its way to the discard, so `op_prizes_next` is zero and `op_wins_next` is
False. That is right about the body in front and silent about the board -- a
knockout does not end their turn, it forces a PROMOTION, and the bench they
promote from is fully visible in the observation.

`TurnPlan.op_wins_after_ko` now reads that promotion. This tool answers the
question the project's method insists on asking before a rule is written: does
the situation the rule would fix HAPPEN, and often enough to matter? It counts
four nested populations, each one a subset of the one above it:

  1. TURNS WHERE WE TAKE THE KNOCKOUT      -- the boards where the plan goes quiet
  2. ... AND THE PROMOTED BODY REPLIES     -- their best benched attacker knocks
                                              our active out afterwards
  3. ... AND THAT REPLY CLOSES THEIR COUNT -- `op_wins_after_ko`: the knockout we
                                              are taking hands them the game
  4. ... AND WE HAD A CHOICE               -- a body on OUR bench takes the SAME
                                              knockout, hands over no more prizes
                                              and survives what comes up

Only (4) is the population of a rule. (3) minus (4) is the set of boards where
the game was already lost and no retreat saves it -- worth knowing, and not worth
a rule.

The retreat has to be legal in the menu for (4) to be actionable, so it is
counted only on MAIN menus that offer one.

Usage:
    python utils/promoted_reply_census.py                       # 200 mirror games
    python utils/promoted_reply_census.py --games 300 \
        --opponent deck/real_opponents/ogerpon_verde_1.csv
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


def _read_opponent_deck(path):
    return sp.read_deck(path)


class Census:
    """The four nested populations, counted per decision."""

    def __init__(self, m):
        self.m = m
        self.n = Counter()
        self.examples = []

    def observe(self, obs, choice):
        m = self.m
        plan = getattr(m.AGENT_STATE, "turn_plan", None)
        if plan is None:
            return
        select = obs.get("select") or {}
        options = select.get("option") or []
        self.n["decisions"] += 1

        # (1) the plan went quiet because we take the knockout: that is exactly
        # "no reply from the active" while our own attack is lethal.
        takes_ko = (plan.op_prizes_next == 0 and not plan.op_wins_next
                    and plan.prizes_today >= 1)
        if not takes_ko:
            return
        self.n["we_take_the_ko"] += 1

        if plan.op_prizes_after_ko <= 0:
            return
        self.n["promoted_body_replies"] += 1

        if not plan.op_wins_after_ko:
            return
        self.n["reply_closes_their_count"] += 1

        has_retreat = any(o.get("type") == int(OptionType.RETREAT)
                          for o in options)
        has_attack = any(o.get("type") == int(OptionType.ATTACK)
                         for o in options)
        if not (has_retreat and has_attack):
            self.n["no_retreat_offered"] += 1
            return
        self.n["retreat_was_on_the_menu"] += 1

        relay = self._surviving_relay(obs)
        if relay is None:
            return
        self.n["a_relay_could_have_taken_it"] += 1
        if len(self.examples) < 12:
            cur = obs["current"]
            self.examples.append({
                "turn": cur["turn"],
                "their_prizes": plan.op_prize,
                "our_active": relay["active_name"],
                "relay": relay["name"],
                "chose": self._label(options, choice),
            })

    def _surviving_relay(self, obs):
        """A body on our bench that takes the SAME knockout, costs no more
        prizes and outlasts the body they promote. None if there is none."""
        m = self.m
        st = m.to_observation_class(obs).current
        mine = st.players[st.yourIndex]
        theirs = st.players[1 - st.yourIndex]
        active = (mine.active or [None])[0]
        op_active = (theirs.active or [None])[0]
        if active is None or op_active is None:
            return None
        op_bench = [p for p in (theirs.bench or []) if p is not None]
        if not op_bench:
            return None

        import dataclasses
        scale = dataclasses.replace(
            m.AGENT_STATE.op_scale,
            op_bench=max(0, m.AGENT_STATE.op_scale.op_bench - 1))
        promoted_hit = max(
            m._op_active_attack_damage_to(b, active, scaled=True, scale=scale)
            for b in op_bench)

        total_grass = sum(
            len(p.energies or []) for p in
            ([p for p in (mine.active or []) if p is not None]
             + [p for p in (mine.bench or []) if p is not None]))
        bench_n = sum(1 for p in (mine.bench or []) if p is not None)
        active_prizes = m.prize_count(active)

        for body in (mine.bench or []):
            if body is None:
                continue
            if m.prize_count(body) > active_prizes:
                continue
            energy = len(body.energies or [])
            base = m._attacker_base_damage(
                body.id, op_active, energy, total_grass, energy,
                max(0, bench_n - 1))
            if base <= 0:
                continue
            if m._our_effective_damage(body, op_active, base) < (op_active.hp or 0):
                continue
            # ... and it has to outlast what they bring up.
            survives = max(
                m._op_active_attack_damage_to(b, body, scaled=True, scale=scale)
                for b in op_bench) < (body.hp or 0)
            if survives:
                return {"name": self._name(body.id),
                        "active_name": self._name(active.id)}
        return None

    def _name(self, card_id):
        data = self.m.card_table.get(card_id)
        return getattr(data, "name", str(card_id))

    def _label(self, options, choice):
        if not choice or choice[0] >= len(options):
            return "?"
        return OptionType(options[choice[0]]["type"]).name

    def report(self):
        n = self.n
        base = n["decisions"] or 1
        print(f"\ndecisions seen                      {n['decisions']:7d}")
        for key, label in (
                ("we_take_the_ko", "we take the knockout"),
                ("promoted_body_replies", "... the promoted body replies"),
                ("reply_closes_their_count", "... and that closes their count"),
                ("retreat_was_on_the_menu", "... with a retreat on the menu"),
                ("a_relay_could_have_taken_it",
                 "... and a surviving relay had the same KO")):
            print(f"{label:36s} {n[key]:7d}  ({100 * n[key] / base:5.2f}% of decisions)")
        if n["no_retreat_offered"]:
            print(f"{'(closed, no retreat offered)':36s} {n['no_retreat_offered']:7d}")
        if self.examples:
            print("\nboards the rule would act on:")
            for e in self.examples:
                print(f"  turn {e['turn']:3d}  their prizes {e['their_prizes']}  "
                      f"{e['our_active']} in front, {e['relay']} on the bench "
                      f"-> chose {e['chose']}")


def run(games, opponent=None):
    m = sp.load_agent(str(_ROOT / "main.py"), "census_promoted")
    deck = sp.read_deck()
    if opponent:
        from opponent_bot import OpponentBot
        rival, rival_deck = OpponentBot(), _read_opponent_deck(opponent)
    else:
        rival, rival_deck = sp.load_agent(str(_ROOT / "main.py"), "census_rival"), deck

    census = Census(m)
    for i in range(games):
        sp._reset_si_aplica(m)
        sp._reset_si_aplica(rival)
        seat = i % 2
        decks = (deck, rival_deck) if seat == 0 else (rival_deck, deck)
        obs, _sd = game.battle_start(list(decks[0]), list(decks[1]))
        if obs is None:
            continue
        agents = {seat: m, 1 - seat: rival}
        steps = 0
        try:
            while obs and obs["current"]["result"] == -1 and steps < 3000:
                yi = obs["current"]["yourIndex"]
                choice = agents[yi].agent(obs)
                if yi == seat:
                    census.observe(obs, choice)
                obs = game.battle_select(choice)
                steps += 1
        finally:
            game.battle_finish()
    return census


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--games", type=int, default=200)
    parser.add_argument("--opponent", default=None,
                        help="csv of an opposing deck (the generic bot pilots it)")
    args = parser.parse_args(argv)
    run(args.games, args.opponent).report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
