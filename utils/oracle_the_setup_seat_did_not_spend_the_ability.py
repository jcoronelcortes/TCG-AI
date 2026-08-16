"""The seat the SETUP gave, graded by the ENGINE'S RULES.

WHY THIS EXISTS. The census
(`utils/gate_the_setup_seat_did_not_spend_the_ability.py --census`) says the two
arms READ the board differently in about half a decision per game -- our
starting active is a Meowth ex in roughly one game in twelve -- and that the
reading CHANGES a choice in one or two games in a hundred. At that exposure a
winrate against the reference bot cannot separate it from nothing, and this
project's rule is to say so rather than to run more games. So the question is
asked the other way round:

    on the exact board the record accuses, does the choice the reading now
    makes roll out better UNDER THE ENGINE'S OWN RULES?

THE BOARD. `records/registro_001_pasos_005_hasta_010.json` step 7, episode
93488655 vs Zoroark ex -- LOST. Our turn 1 going first: the setup dealt our
Meowth ex into the active spot, the hand held no Basic to play, and the Ultra
Ball had already been bought at 31450 -- the price of the UB -> Meowth ex ->
Last-Ditch -> Lillie's engine, which ARMS `_ub_engine_pivot_turn` so that the
fetch completes the chain. The fetch then scored `ub->meowth` at 10 through
`last_ditch_produces_nothing` and bought a Chikorita.

    [0] FETCH Chikorita   1050    <-- what was played
    [1] FETCH Meowth ex   1250    <-- with the reading

THEIR SEAT PLAYS RANDOM BY DEFAULT, and that is not a detail: with `--policy
agent` the oracle plays BOTH seats with our own agent, and a board where our
plan is the one that improves gets its sign inverted by an opponent that plays
our plan too. See [[el-oraculo-juega-los-dos-asientos-con-el-mismo-agente-y-eso-puede-invertir-el-signo]].

K AND THE FLOOR. The floor is MEASURED per board rather than quoted: several
batches of the SAME option with different seeds, and their spread is the floor
this board's delta has to clear.

Usage:
    python utils/oracle_the_setup_seat_did_not_spend_the_ability.py
    python utils/oracle_the_setup_seat_did_not_spend_the_ability.py --k 100 --batches 3
    python utils/oracle_the_setup_seat_did_not_spend_the_ability.py --policy agent
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

RECORD = "records/registro_001_pasos_005_hasta_010.json"
STEP = 7


def mixed_rollout(obs, our_deck, their_deck, forced, seed, agent, us,
                  their_policy="random", max_steps=600):
    """One rollout: our seat under `agent`, theirs under `their_policy`.

    The body of `search_oracle.rollout` with the one line that matters changed
    -- the policy is chosen per FRAME, by whose turn it is. Returns
    (we_won, prizes_they_have_left_minus_ours).
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
        players = cur.get("players") or []
        prizes = [len(p.get("prize") or []) for p in players]
        margin = (prizes[1 - us] - prizes[us]) if len(prizes) == 2 else 0
        return cur.get("result", -1) == us, margin
    finally:
        api.search_end()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, default=100, help="rollouts per batch")
    ap.add_argument("--batches", type=int, default=3,
                    help="batches per option: their spread IS the floor")
    ap.add_argument("--policy", default="random", choices=("random", "agent"),
                    help="the policy THEIR seat plays under")
    args = ap.parse_args(argv)

    import local_engine
    local_engine.load()

    import main as m
    import oracle_the_reserve_does_not_take_the_front as siblings

    steps = json.loads((_ROOT / RECORD).read_text(encoding="utf-8"))["steps"]
    obs = next(p[0]["observation"] for p in steps
               if p[0]["observation"].get("step") == STEP)
    us = obs["current"]["yourIndex"]

    our_deck = sp.read_deck()
    their = siblings._their_deck_for(obs, our_deck, siblings._opponent_lists())
    if their is None:
        raise SystemExit("ninguna lista cierra en 60 para este tablero")
    print(f"{RECORD} paso {STEP} [rival: {their[0]}] "
          f"· su asiento juega '{args.policy}'\n")

    # The two options by CARD, never by index: the menu is the record's and the
    # index of a card in a deck view is not a fact about the decision.
    deck_view = obs["select"]["deck"]
    arms = {}
    for label, card_id in (("FETCH Meowth ex (la lectura)", m.Meowth_ex),
                           ("FETCH Chikorita (lo grabado)", m.Chikorita)):
        idx = next((i for i, o in enumerate(obs["select"]["option"])
                    if deck_view[o["index"]]["id"] == card_id), None)
        if idx is None:
            raise SystemExit(f"la opcion {label} no esta en el menu del paso {STEP}")
        arms[label] = idx

    results = {}
    for label, choice in arms.items():
        rows, margins = [], []
        for b in range(args.batches):
            seed0 = 1000 + 50_000 * b
            wins, margin = 0, 0.0
            for i in range(args.k):
                sp._reset_si_aplica(m)
                won, mg = mixed_rollout(obs, our_deck, their[1], [choice],
                                        seed0 + i, m.agent, us,
                                        their_policy=args.policy)
                wins += 1 if won else 0
                margin += mg
            rows.append(wins)
            margins.append(margin / args.k)
            print(f"  {label:30s} lote {b + 1}  {wins}/{args.k}  "
                  f"margen {margins[-1]:+.2f}", flush=True)
        wr = 100 * sum(rows) / (args.k * len(rows))
        floor = 100 * (max(rows) - min(rows)) / args.k
        mg = sum(margins) / len(margins)
        mg_floor = max(margins) - min(margins)
        results[label] = (wr, floor, mg, mg_floor)
        print(f"  {label:30s} -> {wr:.1f}%   margen {mg:+.2f}   "
              f"suelo propio {floor:.1f} pp / {mg_floor:.2f}\n")

    (wr_a, fa, mg_a, mfa), (wr_b, fb, mg_b, mfb) = list(results.values())
    floor = max(fa, fb)
    mg_floor = max(mfa, mfb)
    print(f"DELTA {wr_a - wr_b:+.1f} pp / {mg_a - mg_b:+.2f} de margen   "
          f"suelo de los tableros {floor:.1f} pp / {mg_floor:.2f}   -> "
          f"{'SUPERA el suelo' if abs(wr_a - wr_b) > floor or abs(mg_a - mg_b) > mg_floor else 'DENTRO del suelo'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
