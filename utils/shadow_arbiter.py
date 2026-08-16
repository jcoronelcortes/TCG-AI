"""The arbiter in SHADOW over the frozen corpus: disagreements, graded.

Phase S2 §5.3 (docs/plan-la-busqueda-en-juego-2026-08-15.md). Nothing here
plays a game. For each sampled historical decision the arbiter is asked the
same question the agent answered, with the machinery a live game would use:

  * determinization `opponent_obs=None` (the play-time-legal path);
  * the opponent's deck RESAMPLED PER ROLLOUT from the S1 posterior
    (`ptcg.opponent.prior`) -- K rollouts average over which deck they
    brought as well as over the shuffle;
  * the MIXED rollout policy (`fast_policy.as_mixed_agent`: our seat fast,
    theirs random) -- the symmetric form measured WORSE than random and two
    oracles showed the opponent's policy alone can flip a verdict's sign;
  * the verdict logic of `ptcg.search.arbiter` with the board's own floor.

The population that matters is the DISAGREEMENTS. Each one is graded with
the TRUE-DECK grader: the corpus record's filename names the list the
opponent actually played, so both choices are re-rolled at higher K under
that list (their hand still sampled -- the frozen bundle keeps one seat).
`prize_swing = margin(arbiter) - margin(historical)`; a swing above the
grader's own floor is an ENDORSED disagreement, and the ranked file of those
is the morning's reading list (phase S6).

The historical choice comes from `tests/corpus/frozen_decisions.json`,
aligned BY WALK ORDER with the record's ACTIVE selects (its `paso` field is
null); a record whose walk length disagrees with its snapshot is dropped and
counted, never silently realigned.

Usage:
    python utils/shadow_arbiter.py --n 600 --k 50 --k-grade 100 \
        --out log/noche-2026-08-16/shadow
    python utils/shadow_arbiter.py --selftest   # fast_policy vs random
"""

import argparse
import gzip
import json
import random
import statistics
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import search_oracle as so  # noqa: E402
from cg import api  # noqa: E402
import ptcg.search.fast_policy as fp  # noqa: E402
from ptcg.opponent.prior import OpponentPrior  # noqa: E402
from ptcg.search.arbiter import arbitrate  # noqa: E402

FROZEN = _ROOT / "tests" / "corpus" / "frozen_records.json.gz"
SNAPSHOT = _ROOT / "tests" / "corpus" / "frozen_decisions.json"


def _safe_end():
    """`search_end` on every path -- but only once an arena exists."""
    if hasattr(api, "agent_ptr"):
        api.search_end()


def _true_list_of(record_name):
    stem = record_name.rsplit(".", 1)[0]
    return "_".join(stem.split("_")[2:-1])


def _our_deck():
    lines = (_ROOT / "deck.csv").read_text().split("\n")
    return [int(lines[i]) for i in range(60)]


def _walk(rec):
    """(step_order, obs) for every ACTIVE select of the record's own seat."""
    seat = rec["seat"]
    out = []
    for step in rec["steps"]:
        for item in step:
            obs = item.get("observation") or {}
            if item.get("status") != "ACTIVE" or not obs.get("select"):
                continue
            if (obs.get("current") or {}).get("yourIndex") != seat:
                continue
            out.append(obs)
    return out


def collect_candidates(corpus, snapshot, prior, max_options):
    """Joined (record, order, obs, historical) rows the shadow can arbitrate."""
    rows, dropped = [], []
    for name, rec in sorted(corpus.items()):
        decs = (snapshot.get(name) or {}).get("decisiones") or []
        walk = _walk(rec)
        if len(decs) != len(walk):
            dropped.append((name, len(walk), len(decs)))
            continue
        true_list = _true_list_of(name)
        true_deck = next((deck for n, _a, _w, _c, deck in prior.entries
                          if n == true_list), None)
        if true_deck is None:
            dropped.append((name, len(walk), -1))
            continue
        for order, (obs, dec) in enumerate(zip(walk, decs)):
            sel = obs["select"]
            options = sel.get("option") or []
            if not 2 <= len(options) <= max_options:
                continue
            if (sel.get("maxCount") or 1) > 1 or len(dec["eleccion"]) != 1:
                continue
            rows.append({"record": name, "order": order, "obs": obs,
                         "turno": dec["turno"], "detalle": dec["detalle"],
                         "historical": dec["eleccion"][0],
                         "true_list": true_list, "true_deck": true_deck})
    return rows, dropped


def make_rollout_one(obs, us, our_deck, prior, seed_base, max_steps):
    def rollout_one(option, i):
        rng = random.Random(seed_base + option * 100_003 + i)
        _name, their = prior.sample_deck(obs, rng, seat=1 - us)
        try:
            r = so.rollout(obs, None, our_deck, their, [option],
                           seed=seed_base + option * 100_003 + i,
                           policy="agent", agent=fp.as_mixed_agent(us, rng),
                           max_steps=max_steps)
        except so.DeterminizationError:
            return None
        finally:
            _safe_end()
        pl = r["prizes_left"]
        margin = (pl[1 - us] - pl[us]) if len(pl) == 2 else 0.0
        return {"won": r["won"], "margin": margin}
    return rollout_one


def grade_with_true_deck(obs, us, our_deck, true_deck, option, k, seed0):
    """Mean margin of `option` under the list they actually played."""
    wins, margins = 0, []
    for i in range(k):
        rng = random.Random(seed0 + i)
        try:
            r = so.rollout(obs, None, our_deck, true_deck, [option],
                           seed=seed0 + i, policy="agent",
                           agent=fp.as_mixed_agent(us, rng))
        except so.DeterminizationError:
            continue
        finally:
            _safe_end()
        pl = r["prizes_left"]
        if len(pl) == 2:
            wins += r["won"]
            margins.append(pl[1 - us] - pl[us])
    if not margins:
        return None
    return {"margin": sum(margins) / len(margins),
            "winrate": wins / len(margins), "worlds": len(margins)}


def selftest():
    """Requirement (i) of fast_policy, reproducible: mixed must beat random."""
    import local_engine
    import selfplay as sp

    lib = local_engine.load()
    deck_us = sp.read_deck(str(_ROOT / "deck.csv"))
    deck_them = sp.read_deck(
        str(_ROOT / "deck" / "real_opponents_500" / "crustle_wall_1.csv"))
    battle, obs, other = so._a_board(deck_us, deck_them, lib)
    try:
        us = obs["current"]["yourIndex"]
        decks = {0: deck_us, 1: deck_them}
        ours, theirs = decks[us], decks[1 - us]
        K = 100
        r1 = so.score_option(obs, other, ours, theirs, [0], k=K, seed0=0)
        r2 = so.score_option(obs, other, ours, theirs, [0], k=K, seed0=10_000)
        mixed = so.score_option(obs, other, ours, theirs, [0], k=K,
                                policy="agent",
                                agent=fp.as_mixed_agent(us, random.Random(3)),
                                seed0=0)
        floor_wr = abs(r1["wins"] - r2["wins"]) / K
        floor_mg = abs((r1["margin"] or 0) - (r2["margin"] or 0))
        dw = (mixed["wins"] - r1["wins"]) / K
        dm = (mixed["margin"] or 0) - (r1["margin"] or 0)
        separa = (dw > 0 or dm > 0) and (abs(dw) > floor_wr
                                         or abs(dm) > floor_mg)
        print(f"AZAR {r1['wins']}/{K} margen {r1['margin']:+.2f} · suelo "
              f"{100 * floor_wr:.0f} pp / {floor_mg:.2f}")
        print(f"MIXTA {mixed['wins']}/{K} margen {mixed['margin']:+.2f} · "
              f"delta {100 * dw:+.0f} pp / {dm:+.2f} -> "
              f"{'SEPARA' if separa else 'NO SEPARA'}")
        return 0 if separa else 1
    finally:
        _safe_end()
        battle.finish()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(FROZEN))
    ap.add_argument("--snapshot", default=str(SNAPSHOT))
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--k", type=int, default=50)
    ap.add_argument("--k-grade", type=int, default=100)
    ap.add_argument("--max-options", type=int, default=5)
    ap.add_argument("--wall", type=float, default=5.0)
    ap.add_argument("--max-steps", type=int, default=600)
    ap.add_argument("--seed", type=int, default=20_260_816)
    ap.add_argument("--out", default=None)
    ap.add_argument("--progress", type=int, default=50)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    prior = OpponentPrior.load()
    with gzip.open(args.corpus) as fh:
        corpus = json.load(fh)
    snapshot = json.load(open(args.snapshot))
    our_deck = _our_deck()

    candidates, dropped = collect_candidates(corpus, snapshot, prior,
                                             args.max_options)
    rng = random.Random(args.seed)
    rng.shuffle(candidates)
    sample = candidates[:args.n]
    print(f"candidatos {len(candidates)} · muestra {len(sample)} · "
          f"registros caidos por desalineacion {len(dropped)}")

    rows, times = [], []
    reasons = {}
    t_run = time.perf_counter()
    for j, cand in enumerate(sample):
        obs = cand["obs"]
        us = obs["current"]["yourIndex"]
        n_options = len(obs["select"]["option"])
        seed_base = args.seed + cand["order"] * 7 + hash(cand["record"]) % 10_000
        rollout_one = make_rollout_one(obs, us, our_deck, prior, seed_base,
                                       args.max_steps)
        t0 = time.perf_counter()
        idx, diag = arbitrate(n_options, rollout_one, k=args.k,
                              wall_s=args.wall)
        dt = time.perf_counter() - t0
        times.append(dt)
        reasons[diag["reason"]] = reasons.get(diag["reason"], 0) + 1

        row = {"record": cand["record"], "order": cand["order"],
               "turno": cand["turno"], "detalle": cand["detalle"],
               "true_list": cand["true_list"],
               "historical": cand["historical"], "arbiter": idx,
               "reason": diag["reason"], "seconds": round(dt, 3)}
        if idx is not None and idx != cand["historical"]:
            g_arb = grade_with_true_deck(obs, us, our_deck,
                                         cand["true_deck"], idx,
                                         args.k_grade, seed_base + 500_000)
            g_his = grade_with_true_deck(obs, us, our_deck,
                                         cand["true_deck"],
                                         cand["historical"],
                                         args.k_grade, seed_base + 600_000)
            g_flo = grade_with_true_deck(obs, us, our_deck,
                                         cand["true_deck"],
                                         cand["historical"],
                                         args.k_grade, seed_base + 700_000)
            if g_arb and g_his and g_flo:
                floor = abs(g_his["margin"] - g_flo["margin"])
                swing = g_arb["margin"] - g_his["margin"]
                row.update({"margin_arbiter": round(g_arb["margin"], 3),
                            "margin_historical": round(g_his["margin"], 3),
                            "grade_floor": round(floor, 3),
                            "prize_swing": round(swing, 3),
                            "endorsed": swing > floor})
        rows.append(row)
        if args.progress and (j + 1) % args.progress == 0:
            print(f"  {j + 1}/{len(sample)} · "
                  f"{time.perf_counter() - t_run:.0f}s · razones {reasons}")

    disagreements = [r for r in rows if r["arbiter"] is not None
                     and r["arbiter"] != r["historical"]]
    endorsed = [r for r in disagreements if r.get("endorsed")]
    exceptions = sum(v for r, v in reasons.items()
                     if r and r.startswith("exception"))
    verdicts = reasons.get("verdict", 0)
    agree = sum(1 for r in rows if r["arbiter"] == r["historical"])

    print(f"\ndecisiones {len(rows)} · veredictos {verdicts} "
          f"({agree} de acuerdo, {len(disagreements)} desacuerdos, "
          f"{len(endorsed)} RESPALDADOS por el graduador de lista verdadera)")
    print(f"abstenciones por razon: "
          f"{ {k: v for k, v in reasons.items() if k != 'verdict'} }")
    if times:
        print(f"tiempo por decision: mediana {statistics.median(times):.2f}s "
              f"· p99 {sorted(times)[int(0.99 * (len(times) - 1))]:.2f}s "
              f"· total {sum(times) / 60:.1f} min")
    rate_exc = exceptions / max(1, len(rows))
    print(f"excepciones {exceptions}/{len(rows)} = {rate_exc:.1%} -> "
          f"{'PASA' if rate_exc < 0.01 else 'FALLA'} (criterio <1%)")

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "resumen.json").write_text(json.dumps({
            "n": len(rows), "reasons": reasons, "agree": agree,
            "disagreements": len(disagreements), "endorsed": len(endorsed),
            "exception_rate": rate_exc,
            "median_s": statistics.median(times) if times else None,
            "dropped_records": dropped,
        }, indent=1))
        ranked = sorted(disagreements,
                        key=lambda r: -abs(r.get("prize_swing") or 0))
        (out / "desacuerdos.json").write_text(json.dumps(ranked, indent=1))
        print(f"escrito {out}/resumen.json y desacuerdos.json")
    return 0 if rate_exc < 0.01 else 1


if __name__ == "__main__":
    raise SystemExit(main())
