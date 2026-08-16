"""Census of the opponent posterior against the frozen corpus (phase S1).

The question of the plan's §4: does a posterior over the 133 real lists name
the opponent's archetype AT LEAST as early as the signature-card flags, at no
worse precision? The frozen corpus carries the ground truth in every record
name (`registro_012_alakazam_2_asiento0.json` -> the opponent played
`alakazam_2`), so this is measurable without playing a single game.

The flag proxy: the current `op_is_*_deck` flags fire when a signature card
shows up in a visible zone. The earliest ANY such flag can fire is the first
turn a card UNIQUE to the true archetype (across the admitted lists) becomes
visible. That turn is computed per record and the posterior must not be later
(criterion C1).

Pre-registered criteria, printed as PASA/FALLA:
  C1  median first-stable-correct turn of the posterior <= median unique-card
      turn (records where the proxy never fires count in the posterior's
      favour if the posterior does become stable-correct).
  C2  archetype accuracy >= 90 % over the decisions at/after the proxy turn.
  C3  confident-wrong rate < 5 % (P(top-1 archetype) >= 0.8, turn >= 3,
      archetype wrong) -- the four documented flag defects were all
      "confident about the wrong thing".
  C4  zero exceptions, and `prior.ids_seen` agrees with
      `search_oracle._ids_seen` on EVERY board (the engine-free port is only
      trusted while this parity holds).

Usage:
    python utils/opponent_prior_census.py --out log/noche-2026-08-16/t2_censo.json
    python utils/opponent_prior_census.py --records records/   # robustness only
"""

import argparse
import gzip
import json
import statistics
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import search_oracle as so  # noqa: E402  (parity check only)
from ptcg.opponent.prior import OpponentPrior, ids_seen  # noqa: E402

FROZEN = _ROOT / "tests" / "corpus" / "frozen_records.json.gz"
CONFIDENT = 0.8
CONFIDENT_FROM_TURN = 3


def true_list_of(record_name):
    """`registro_012_alakazam_2_asiento0.json` -> `alakazam_2`."""
    stem = record_name.rsplit(".", 1)[0]
    parts = stem.split("_")
    # registro / NNN / <list parts...> / asientoN
    return "_".join(parts[2:-1])


def unique_ids_by_archetype(prior):
    owners = {}
    for _name, arch, _w, counter, _deck in prior.entries:
        for cid in counter:
            owners.setdefault(cid, set()).add(arch)
    unique = {}
    for cid, archs in owners.items():
        if len(archs) == 1:
            unique.setdefault(next(iter(archs)), set()).add(cid)
    return unique


def walk_record(rec, prior, unique_map, true_arch):
    """Per-decision series for one frozen record."""
    seat = rec["seat"]
    opp = 1 - seat
    rows = []
    parity_fail = 0
    proxy_turn = None
    for step in rec["steps"]:
        for item in step:
            obs = item.get("observation") or {}
            if item.get("status") != "ACTIVE" or not obs.get("select"):
                continue
            cur = obs.get("current") or {}
            if cur.get("yourIndex") != seat:
                continue
            turn = cur.get("turn", 0)
            seen = ids_seen(obs, opp)
            if seen != so._ids_seen(obs, opp):
                parity_fail += 1
            if proxy_turn is None and true_arch in unique_map:
                if any(cid in unique_map[true_arch] for cid in seen):
                    proxy_turn = turn
            posterior, hosted = prior.evaluate(obs, opp)
            arch_post = {}
            for name, prob in posterior:
                a = prior.archetype_of(name)
                arch_post[a] = arch_post.get(a, 0.0) + prob
            top_arch, top_p = max(arch_post.items(), key=lambda kv: kv[1])
            rows.append({"turn": turn, "top_arch": top_arch, "p": top_p,
                         "hosted": hosted,
                         "correct": top_arch == true_arch})
    stable = None
    for i, row in enumerate(rows):
        if all(r["correct"] for r in rows[i:]):
            stable = row["turn"]
            break
    return rows, stable, proxy_turn, parity_fail


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(FROZEN))
    ap.add_argument("--records", default=None,
                    help="live records dir: robustness pass, no ground truth")
    ap.add_argument("--out", default=None)
    ap.add_argument("--flat", action="store_true",
                    help="census the pre-registered fallback instead")
    args = ap.parse_args(argv)

    prior = OpponentPrior.flat() if args.flat else OpponentPrior.load()
    unique_map = unique_ids_by_archetype(prior)
    with gzip.open(args.corpus) as fh:
        corpus = json.load(fh)

    per_record, exceptions = [], []
    for name, rec in sorted(corpus.items()):
        true_list = true_list_of(name)
        true_arch = prior.archetype_of(true_list)
        if true_arch is None:
            exceptions.append((name, f"unknown true list {true_list!r}"))
            continue
        try:
            rows, stable, proxy, parity_fail = walk_record(
                rec, prior, unique_map, true_arch)
        except Exception as exc:  # a census that dies mid-run reports it
            exceptions.append((name, repr(exc)))
            continue
        per_record.append({
            "record": name, "true_list": true_list, "true_arch": true_arch,
            "decisions": len(rows), "stable_turn": stable,
            "proxy_turn": proxy, "parity_fail": parity_fail,
            "rows": rows,
        })

    # ----- aggregate ------------------------------------------------------
    stables = [r["stable_turn"] for r in per_record
               if r["stable_turn"] is not None]
    proxies = [r["proxy_turn"] for r in per_record
               if r["proxy_turn"] is not None]
    never_stable = sum(1 for r in per_record if r["stable_turn"] is None)
    never_proxy = sum(1 for r in per_record if r["proxy_turn"] is None)
    post_rows = [row for r in per_record for row in r["rows"]
                 if r["proxy_turn"] is not None
                 and row["turn"] >= r["proxy_turn"]]
    pre_rows = [row for r in per_record for row in r["rows"]
                if r["proxy_turn"] is None or row["turn"] < r["proxy_turn"]]
    conf_rows = [row for r in per_record for row in r["rows"]
                 if row["turn"] >= CONFIDENT_FROM_TURN
                 and row["p"] >= CONFIDENT]
    conf_wrong = sum(1 for row in conf_rows if not row["correct"])
    parity_fails = sum(r["parity_fail"] for r in per_record)

    med_stable = statistics.median(stables) if stables else None
    med_proxy = statistics.median(proxies) if proxies else None
    acc_post = (sum(r["correct"] for r in post_rows) / len(post_rows)
                if post_rows else None)
    acc_pre = (sum(r["correct"] for r in pre_rows) / len(pre_rows)
               if pre_rows else None)
    conf_wrong_rate = conf_wrong / len(conf_rows) if conf_rows else 0.0

    c1 = (med_stable is not None and med_proxy is not None
          and med_stable <= med_proxy)
    c2 = acc_post is not None and acc_post >= 0.90
    c3 = conf_wrong_rate < 0.05
    c4 = not exceptions and parity_fails == 0

    print(f"registros: {len(per_record)}  ·  decisiones: "
          f"{sum(r['decisions'] for r in per_record)}")
    print(f"C1 mediana turno estable posterior {med_stable} vs proxy-flag "
          f"{med_proxy}  (nunca-estable {never_stable}, nunca-proxy "
          f"{never_proxy})  -> {'PASA' if c1 else 'FALLA'}")
    print(f"C2 acierto de arquetipo en/tras el proxy "
          f"{acc_post if acc_post is None else f'{acc_post:.1%}'} "
          f"(antes del proxy: "
          f"{acc_pre if acc_pre is None else f'{acc_pre:.1%}'})"
          f"  -> {'PASA' if c2 else 'FALLA'}")
    print(f"C3 confiado-y-equivocado (p>={CONFIDENT}, turno>="
          f"{CONFIDENT_FROM_TURN}): {conf_wrong}/{len(conf_rows)} = "
          f"{conf_wrong_rate:.1%}  -> {'PASA' if c3 else 'FALLA'}")
    print(f"C4 excepciones {len(exceptions)} · paridad ids_seen fallos "
          f"{parity_fails}  -> {'PASA' if c4 else 'FALLA'}")
    for name, err in exceptions:
        print(f"   EXC {name}: {err}")

    # ----- robustness over live records (no truth) ------------------------
    live = None
    if args.records:
        live = {"files": 0, "decisions": 0, "hosted": 0, "exceptions": 0}
        for path in sorted(Path(args.records).glob("registro_*.json")):
            try:
                data = json.loads(path.read_text())
                for step in data.get("steps", []):
                    for item in step:
                        obs = item.get("observation") or {}
                        if item.get("status") != "ACTIVE" \
                                or not obs.get("select"):
                            continue
                        _post, hosted = prior.evaluate(obs)
                        live["decisions"] += 1
                        live["hosted"] += bool(hosted)
                live["files"] += 1
            except Exception:
                live["exceptions"] += 1
        print(f"records vivos: {live['files']} ficheros, "
              f"{live['decisions']} decisiones, hosted "
              f"{live['hosted']}/{live['decisions']}, excepciones "
              f"{live['exceptions']}")

    verdict = all((c1, c2, c3, c4))
    print(f"VEREDICTO: {'PASA' if verdict else 'FALLA'}"
          f"{' (fallback plano)' if args.flat else ''}")

    if args.out:
        out = {
            "criteria": {"c1": c1, "c2": c2, "c3": c3, "c4": c4},
            "median_stable": med_stable, "median_proxy": med_proxy,
            "acc_post_proxy": acc_post, "acc_pre_proxy": acc_pre,
            "confident_wrong_rate": conf_wrong_rate,
            "never_stable": never_stable, "never_proxy": never_proxy,
            "parity_fails": parity_fails,
            "exceptions": exceptions, "live": live,
            "per_record": [{k: v for k, v in r.items() if k != "rows"}
                           for r in per_record],
        }
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=1))
        print(f"escrito {args.out}")
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
