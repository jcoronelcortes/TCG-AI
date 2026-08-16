"""The defensive pivot, graded by the ENGINE'S RULES -- and by a policy that
does not play their deck with our agent.

WHY THIS FILE IS NOT A COPY OF ITS SIBLINGS. `search_oracle._choose` drives BOTH
seats with the policy it is given, so `policy="agent"` plays the opponent's
Alakazam deck with our Grass agent, out of the SAME `AGENT_STATE` -- one belief,
alternating seats, matchup flags and card tracking clobbered every frame. On the
board this rule was written from that confound does not cancel between the two
options, and the reading it produces is the reverse of every other one:

    both seats = our agent      RETREAT 96-99/100 · ATTACK 64-68/100   (+32 pp for the retreat)
    both seats = random         RETREAT 40/60     · ATTACK 54/60       (+23 pp for the attack)
    OURS agent / THEIRS random  RETREAT 92.5%     · ATTACK 98.5%       (+6.0 pp for the attack)

Three policies, three answers, and only the third one asks the question we mean:
grade OUR choice under OUR policy, against an opponent that is merely legal. The
first is the confound; the second throws away the policy whose choice is being
graded. K=200 x 3 batches per option, and the batches are what says the gap is
real: ATTACK 198/197/196, RETREAT 186/181/188 -- the two ranges do not touch,
which is more than either option's own floor.

A ONE-BOARD INSTRUMENT, on purpose. The census says this rule changes a decision
**0.04 times per game** against `alakazam_1` (8 flips in 27 085 decisions over
200 games), and the self-play gate at n=1500 comes out at **+0.00 pp exactly**
with both arms posting the identical 1459/1500. At that exposure a winrate gate
cannot resolve the rule and says so; the board can.

Usage:
    python utils/oracle_the_pivot_wall_must_survive_the_reply.py            # K=200
    python utils/oracle_the_pivot_wall_must_survive_the_reply.py --k 50
    python utils/oracle_the_pivot_wall_must_survive_the_reply.py --policy agent
"""

import argparse
import json
import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import search_oracle as so  # noqa: E402
import selfplay as sp  # noqa: E402
from cg import api  # noqa: E402

RECORD = "records/registro_011_pasos_112_hasta_127.json"
STEP = 119
SOLAR_BEAM = 1028
RETREAT_TYPE = 12


def mixed_rollout(obs, our_deck, their_deck, forced, seed, agent, us,
                  their_policy="random", max_steps=600):
    """One rollout: our seat under `agent`, theirs under `their_policy`.

    Same body as `search_oracle.rollout`, with the one line that matters
    changed -- the policy is chosen per FRAME, by whose turn it is.
    """
    rng = random.Random(seed)
    det = so.determinize(obs, None, our_deck, their_deck, rng=rng)
    root = api.search_begin(api.to_observation_class(obs), det["your_deck"],
                            det["your_prize"], det["opponent_deck"],
                            det["opponent_prize"], det["opponent_hand"],
                            det["opponent_active"])
    try:
        state = so._step_raw(root.searchId, list(forced))
        steps = 1
        while steps < max_steps:
            ob = state["observation"]
            cur = ob.get("current") or {}
            if cur.get("result", -1) != -1:
                break
            policy = "agent" if cur.get("yourIndex") == us else their_policy
            choice = so._choose(ob, rng, policy, agent)
            if choice is None:
                break
            state = so._step_raw(state["searchId"], choice)
            steps += 1
        cur = (state["observation"].get("current") or {})
        return cur.get("result", -1) == us
    finally:
        api.search_end()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, default=200, help="rollouts per batch")
    ap.add_argument("--batches", type=int, default=3,
                    help="batches per option: their spread IS the floor")
    ap.add_argument("--policy", default="random", choices=("random", "agent"),
                    help="the policy THEIR seat plays under")
    args = ap.parse_args(argv)

    import main as m
    from recorded_deck import deck_of_record, read_list
    import oracle_the_reserve_does_not_take_the_front as siblings

    steps = json.loads((_ROOT / RECORD).read_text(encoding="utf-8"))["steps"]
    obs = next(p[0]["observation"] for p in steps
               if p[0]["observation"].get("step") == STEP)
    us = obs["current"]["yourIndex"]

    with deck_of_record():
        our_deck = read_list()
        their = siblings._their_deck_for(obs, our_deck, siblings._opponent_lists())
        if their is None:
            raise SystemExit("ninguna lista cierra en 60 para este tablero")
        print(f"{RECORD} paso {STEP} [rival: {their[0]}] "
              f"· su asiento juega '{args.policy}'\n")

        options = obs["select"]["option"]
        arms = {
            "ATTACK (Solar Beam)": next(
                i for i, o in enumerate(options) if o.get("attackId") == SOLAR_BEAM),
            "RETREAT (lo grabado)": next(
                i for i, o in enumerate(options) if o.get("type") == RETREAT_TYPE),
        }
        for label, choice in arms.items():
            rows = []
            for b in range(args.batches):
                seed0 = 1000 + 50000 * b
                wins = 0
                for i in range(args.k):
                    sp._reset_si_aplica(m)
                    wins += 1 if mixed_rollout(
                        obs, our_deck, their[1], [choice], seed0 + i,
                        m.agent, us, their_policy=args.policy) else 0
                rows.append(wins)
                print(f"  {label:22s} lote {b + 1}  {wins}/{args.k}", flush=True)
            print(f"  {label:22s} -> {100 * sum(rows) / (args.k * len(rows)):.1f}%"
                  f"   suelo propio {100 * (max(rows) - min(rows)) / args.k:.1f} pp\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
