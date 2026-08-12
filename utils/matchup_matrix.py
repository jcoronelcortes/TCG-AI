"""Matchup matrix: the agent's winrate against EACH opposing deck.

By default it measures against `deck/real_opponents/` -- the REAL leaderboard
lists (utils/real_opponents.py), with their meta weight.

The synthetic ones in `deck/opponents/` are still there but they are NO LONGER the default, and
it is worth knowing why: measured against the top-300, **8 of its 17 decks are
archetypes that do not exist in the meta** (Comfey, Iron Thorns, Jellicent, Raging
Bolt, Cornerstone/Cubchoo, Hop's, Fire Gouging, Comfey/Yveltal). Since the matrix
weights every deck equally unless --weights is passed, running it against
that folder spent almost half the game budget on imaginary
opponents -- and a change that won there and lost against Marnie looked
good. They are kept because they are still useful for testing specific MECHANICS
(the Iron Thorns lock, the Comfey mill) that the current meta does not offer.


Phase 8 of the strategy improvement architecture. It walks every CSV in the
opponents folder and plays N games against the generic bot with each of them,
alternating seats. It prints the table sorted from the weakest matchup to the
strongest, with the 95% Wilson interval and the forfeits.

With --base <git-ref> it also prints the per-matchup DELTA against that version:
it detects when a new rule improves one matchup while degrading another (the
Cubchoo/Cornerstone collision class). CAREFUL with the noise: with 200 games the delta
swings +-7 points; only large, consistent deltas are signal.

That +-7 is CONFIRMED by direct measurement (Aug 2026): in a run at 200
games with --base, the 83 decks that could not be affected by the change
-- behaviourally identical code in both arms -- moved between -6.5
and +7.5 points. Hence the --games default rising to 400 and the existence of
--control-card: the warning was written from the start and even so it is easy
to read as signal a delta that fits entirely inside the noise.

With --weights (and the corpus of utils/real_opponents.py) the summary stops being a
simple average: each matchup weighs what that archetype weighs in the real meta. It is the
difference between "I beat 8 of 17 decks" and "I win X% of the games I am going
to play on ladder" -- with a simple average, a +10 against an archetype that is
1% of the field hides a -1 against the one that is 41%.

`--control-card <id>` separates the decks that run that card (the ones the change
CAN affect) from the ones that do not, and compares the deltas of both groups. The control
group runs behaviourally identical code in both arms, so its
dispersion IS the noise of that same run. It is the only cheap way to know
whether a delta is signal: measured here, at 200 games per matchup the control gets
to move from -6.5 to +7.5 points, so a small delta without this breakdown
means nothing.

Usage:
    python utils/matchup_matrix.py --games 400
    python utils/matchup_matrix.py --games 400 --base HEAD~1
    python utils/matchup_matrix.py --base HEAD~1 --control-card 1266
    python utils/matchup_matrix.py --only dragapult,hops
    python utils/matchup_matrix.py --opponents deck/real_opponents --weights
    python utils/matchup_matrix.py --opponents deck/real_opponents --weights --base HEAD~1
"""

import argparse
import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import parallel
import selfplay as sp


def is_deck(path):
    """Is the CSV a list of 60 ids and not something else?

    The opponents directory also contains `pesos.csv`, and it could contain
    any other auxiliary CSV. Without this filter the matrix tries to read it as a
    deck and blows up AFTER having played all the good matchups.
    """
    try:
        lines = [x for x in path.read_text(encoding="utf-8-sig").split() if x.strip()]
    except (OSError, UnicodeDecodeError):
        return False
    if len(lines) != 60:
        return False
    return all(x.lstrip("-").isdigit() for x in lines)


def load_weights(directory):
    """Meta weight per deck, from the pesos.csv of utils/real_opponents.py.

    Without this the matrix treats every opponent equally, which is what
    makes a change get approved for winning against archetypes almost nobody
    plays. It returns {} if there is no pesos.csv.
    """
    import csv

    path = Path(directory) / "pesos.csv"
    if not path.is_file():
        return {}
    weights = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            name = str(row.get("archivo", ""))
            if name.endswith(".csv"):
                name = name[:-4]
            try:
                weights[name] = float(row.get("peso_meta") or 0.0)
            except ValueError:
                continue
    return weights


def _carries_card(path, card_id):
    try:
        return card_id in [int(x) for x in path.read_text().split() if x.strip()]
    except (OSError, ValueError):
        return False


def informe_control(rows, base_by_deck, paths, card_id):
    """Separates the AFFECTED decks (those with the card) from the CONTROL and compares their deltas.

    It is the only cheap way to know whether a delta is signal: the decks that do NOT
    run the card execute behaviourally identical code in both arms,
    so their dispersion IS the noise of that same run -- with no need to
    run a separate calibration.

    Measured in this session: at 200 games per matchup the control group gets
    to move from -6.5 to +7.5 points. Any delta of the affected decks that fits
    in that range is not signal.
    """
    by_name = {r.stem: r for r in paths}
    with_card, without_card = [], []
    for f in rows:
        if f["deck"] not in base_by_deck:
            continue
        delta = f["wr"] - base_by_deck[f["deck"]]["wr"]
        dprem = None
        bp = base_by_deck[f["deck"]].get("dif_premios")
        if f["dif_premios"] is not None and bp is not None:
            dprem = f["dif_premios"] - bp
        path = by_name.get(f["deck"])
        target_path = with_card if (path is not None and _carries_card(path, card_id)) else without_card
        target_path.append((f["deck"], delta, dprem))

    if not with_card or not without_card:
        print(f"\n(control: cannot split by card {card_id}; "
              f"afectados={len(with_card)}, control={len(without_card)})")
        return

    print(f"\n=== CONTROL GROUP (card {card_id}) ===")
    for etiqueta, group in (("AFECTADOS", with_card), ("CONTROL  ", without_card)):
        ds = [d for _, d, _ in group]
        ps = [p for _, _, p in group if p is not None]
        positivos = sum(1 for d in ds if d > 0)
        line = (f"  {etiqueta} n={len(ds):>2}  delta wr {100 * sum(ds) / len(ds):+6.2f}"
                 f"  rango {100 * min(ds):+.1f} a {100 * max(ds):+.1f}"
                 f"  positivos {positivos}/{len(ds)}")
        if ps:
            line += f"  prize delta {sum(ps) / len(ps):+.3f}"
        print(line)
    print("  If the AFFECTED delta fits inside the CONTROL range it is noise: "
          "the control runs identical code in both arms.")


def winrate_ponderado(rows, weights):
    """(expected ladder winrate, measured meta coverage).

    The winrate is normalised over what was ACTUALLY measured, and the coverage is
    returned separately: a number over 60% of the meta is not comparable with one
    over 100%, and hiding that would be the very error this metric exists to correct.
    """
    cobertura = sum(weights.get(f["deck"], 0.0) for f in rows)
    if cobertura <= 0:
        return None, 0.0
    total = sum(weights.get(f["deck"], 0.0) * f["wr"] for f in rows)
    return total / cobertura, cobertura


def error_ponderado(rows, weights):
    """Standard error of the weighted winrate. None if it cannot be computed.

    This is THE number `--allocation` is optimising, and without it the choice
    of schedule cannot be judged: a uniform split and a weighted one spend the
    same games, so the only way one can be better is by producing a tighter
    estimate of the same quantity.

    The weighted winrate is a weighted mean of independent per-deck proportions,
    so its variance is the weighted sum of theirs:

        Var = sum(w_i^2 * p_i(1-p_i)/n_i) / (sum w_i)^2

    Which is exactly why the uniform split is wasteful: it buys precision on
    terms whose w_i^2 is ~0.
    """
    cobertura = sum(weights.get(f["deck"], 0.0) for f in rows)
    if cobertura <= 0:
        return None
    var = 0.0
    for f in rows:
        w = weights.get(f["deck"], 0.0)
        n = f["decididas"]
        if w <= 0 or n <= 0:
            continue
        p = f["wr"]
        var += (w ** 2) * p * (1 - p) / n
    return math.sqrt(var) / cobertura


def allocate(paths, games, weights, mode, floor=None):
    """How many games each matchup gets. Returns {deck stem: games}.

    `mode="uniforme"` is the historical behaviour: every deck gets `--games`.
    Measured 12 August 2026, that is where the budget leaks -- 66 of the 88
    lists in the corpus are 0.33 % of the meta each while the top three are
    53.7 % between them, so a flat schedule spends **75 % of the compute on
    22 % of the meta**.

    `mode="peso"` keeps the SAME TOTAL and redistributes it proportional to
    `peso_meta`, with a floor so the long tail keeps regression coverage rather
    than falling to zero. The floor is what stops this becoming "measure the
    three decks that matter and go blind everywhere else": a matchup at the
    floor still catches a change that breaks it outright, which is most of what
    the tail was ever catching.
    """
    stems = [p.stem for p in paths]
    if mode != "peso" or not weights:
        return {s: games for s in stems}
    floor = games // 4 if floor is None else floor
    total = games * len(stems)
    share = {s: max(weights.get(s, 0.0), 0.0) for s in stems}
    suma = sum(share.values())
    if suma <= 0:
        return {s: games for s in stems}
    presupuesto = total - floor * len(stems)
    if presupuesto <= 0:  # the floor already spends everything
        return {s: games for s in stems}
    out = {}
    for s in stems:
        out[s] = floor + int(round(presupuesto * share[s] / suma))
    return out


def _row(stem, stats):
    dec = stats["candidate"] + stats["base"]
    wr = stats["candidate"] / dec if dec else 0.0
    lo, hi = sp.wilson_95(stats["candidate"], dec)
    pc, pb, prize_diff = sp.prizes_per_game(stats)
    return {
        "deck": stem, "wr": wr, "lo": lo, "hi": hi,
        "decididas": dec, "limites": stats["limites"],
        "forfeits": stats["errores_candidato"],
        "forfeits_bot": stats["errores_base"],
        "premios": pc, "premios_bot": pb, "dif_premios": prize_diff,
    }


def _print_row(f):
    extra = "" if f["dif_premios"] is None else f" premios {f['dif_premios']:+.2f}"
    print(f"  {f['deck']}: {100 * f['wr']:.1f}% "
          f"[{100 * f['lo']:.1f}-{100 * f['hi']:.1f}]{extra} "
          f"(n={f['decididas']}, forfeits nuestros {f['forfeits']})", flush=True)


def medir_paralelo(cand_spec, paths, reparto, bot_first_choice="first",
                   jobs=None, seeds=None, etiqueta=""):
    """The whole matrix through ONE pool, instead of one pool per matchup.

    `bot_first_choice="second"` makes the bot DECLINE the first turn, so the
    coin flip decides who takes it. The default reproduces every figure on
    record: our agent vetoes going first and the bot answers YES, so the matrix
    has only ever measured the going-SECOND half of the game (measured 11 August
    2026: 0 of 60 games first in matchup mode against 30/30 in the mirror).
    Going first was then worth +2.54 points aggregated and +11.00 against
    crustle_kangaskhan, which is exactly where this matrix is weakest.

    Flattening every matchup into a single job list is what keeps the cores fed:
    a pool per deck would pay worker startup 87 times and idle at each deck's
    tail. Measured on the mirror gate: 5.06x at 6 workers, 6.76x at 10.
    """
    matchups = [(p.stem, sp.read_deck(p), reparto[p.stem]) for p in paths]
    total = sum(n for _, _, n in matchups)
    print(f"  {len(matchups)} matchups, {total} partidas{etiqueta}", flush=True)
    jobs_list = parallel.build_matchup_jobs(matchups, seeds=seeds)
    results = parallel.run_jobs(jobs_list, cand_spec,
                                parallel.spec_bot(bot_first_choice),
                                jobs_n=jobs, progress=max(1, total // 10))
    por_mazo = parallel.group_by_tag(results)
    rows = []
    for path in paths:
        stem = path.stem
        stats = sp.new_stats(reparto[stem])
        for seat, r in por_mazo.get(stem, []):
            sp.accumulate(stats, r, seat)
        rows.append(_row(stem, stats))
        _print_row(rows[-1])
    return rows


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--control-card", type=int, default=None, metavar="ID",
                    help="card id that defines the AFFECTED group: it splits the "
                         "decks that carry it from those that do not and compares both "
                         "deltas. Without it, a delta cannot be told apart from noise")
    ap.add_argument("--games", type=int, default=400,
                    help="games per matchup (default 400). Measured: at 200"
                         "                         the per-matchup noise"
                         "                         reaches +-6.5 points")
    ap.add_argument("--candidate", default="main.py")
    ap.add_argument("--base", default=None,
                    help="a git ref: prints the per-matchup delta")
    ap.add_argument("--only", default=None,
                    help="comma-separated list of decks (default: all)")
    ap.add_argument("--opponents", default=str(_ROOT / "deck" / "real_opponents"),
                    help="folder of opponent decks (default:"
                         "                         deck/real_opponents, the"
                         "                         REAL leaderboard lists"
                         "                         with their weights)")
    ap.add_argument("--bot-declines-first", action="store_true",
                    help="the bot declines the first turn, so the coin flip "
                         "decides it. Off by default: the numbers on record are "
                         "all going-second")
    ap.add_argument("--weights", action="store_true",
                    help="weight by real meta share (needs the pesos.csv"
                         "                         produced by"
                         "                         utils/real_opponents.py)")
    ap.add_argument("--jobs", type=int, default=None,
                    help="worker processes (default: performance cores)")
    ap.add_argument("--seeds", default=None,
                    help="engine seeds ('N' or a comma list): both arms replay "
                         "the SAME games. Needs the local engine "
                         "(cg/build_local_engine.sh)")
    ap.add_argument("--allocation", choices=("uniforme", "peso"),
                    default="uniforme",
                    help="how --games is spread. 'uniforme' (default) gives "
                         "every deck the same; 'peso' keeps the same TOTAL and "
                         "redistributes it by meta share with a floor, because "
                         "uniform spends 75%% of the compute on 22%% of the meta")
    args = ap.parse_args(argv)

    seeds = sp.parse_seeds(args.seeds)
    if seeds:
        import local_engine
        local_engine.load()  # fail now, not an hour of games in

    all_decks = sorted(Path(args.opponents).glob("*.csv"))
    paths = [r for r in all_decks if is_deck(r)]
    omitidos = [r.name for r in all_decks if r not in paths]
    if omitidos:
        print(f"(not decks, skipped: {', '.join(omitidos)})")
    if args.only:
        quiere = {s.strip() for s in args.only.split(",")}
        paths = [r for r in paths if r.stem in quiere]
    if not paths:
        print("no opponent decks to measure")
        return 1

    # The weights are loaded BEFORE playing: if they are missing, the error must come out now and
    # not after an hour of games.
    weights = load_weights(args.opponents) if args.weights else {}
    if args.weights and not weights:
        print(f"ERROR: there is no pesos.csv in {args.opponents}. "
              f"Generate it with: python utils/real_opponents.py", file=sys.stderr)
        return 1

    if args.allocation == "peso" and not weights:
        print("ERROR: --allocation peso needs --weights (it is the meta share "
              "that decides the split)", file=sys.stderr)
        return 1
    reparto = allocate(paths, args.games, weights, args.allocation)

    cand_spec = parallel.spec_file(_ROOT / args.candidate)
    print(f"candidato={args.candidate}, {args.games} games per matchup "
          f"(reparto {args.allocation}"
          f"{', semillas ' + args.seeds if seeds else ''})")
    eleccion = "second" if args.bot_declines_first else "first"
    rows = medir_paralelo(cand_spec, paths, reparto, eleccion,
                          jobs=args.jobs, seeds=seeds)

    base_by_deck = {}
    if args.base:
        base_spec = parallel.spec_tree(
            sp.checkout_tree(args.base, "agente_matriz_base"),
            "agente_matriz_base")
        print(f"\nbaseline={args.base}")
        base_by_deck = {f["deck"]: f for f in
                        medir_paralelo(base_spec, paths, reparto, eleccion,
                                       jobs=args.jobs, seeds=seeds)}

    without_weight = [f["deck"] for f in rows if f["deck"] not in weights] if weights else []

    print("\n=== MATCHUP MATRIX (worst -> best) ===")
    width = max(len(f["deck"]) for f in rows)
    for f in sorted(rows, key=lambda x: x["wr"]):
        line = (f"{f['deck']:<{width}}  {100 * f['wr']:5.1f}%  "
                 f"[{100 * f['lo']:.1f}-{100 * f['hi']:.1f}]"
                 f"  n={f['decididas']}")
        if weights:
            line += f"  meta={100 * weights.get(f['deck'], 0.0):4.1f}%"
        if f["forfeits"]:
            line += f"  FORFEITS={f['forfeits']}"
        if f["dif_premios"] is not None:
            line += f"  prem={f['dif_premios']:+.2f}"
        if f["deck"] in base_by_deck:
            delta = f["wr"] - base_by_deck[f["deck"]]["wr"]
            line += f"  delta={100 * delta:+.1f}"
            if weights:
                # What that delta moves the ladder winrate by: a +10 against an
                # archetype that is 1% is worth ten times less than a +1 against the one that is 41%.
                line += f" (pond {100 * delta * weights.get(f['deck'], 0.0):+.2f})"
            base_prem = base_by_deck[f["deck"]].get("dif_premios")
            if f["dif_premios"] is not None and base_prem is not None:
                line += f"  dprem={f['dif_premios'] - base_prem:+.2f}"
        print(line)
    worst = min(rows, key=lambda x: x["wr"])
    print(f"\nMatchup mas debil: {worst['deck']} ({100 * worst['wr']:.1f}%)")

    if args.control_card is not None and base_by_deck:
        informe_control(rows, base_by_deck, paths, args.control_card)
    elif args.control_card is not None:
        print("\n(--control-card needs --base: with no baseline there are no "
              "deltas to split)")

    if weights:
        wr_pond, cobertura = winrate_ponderado(rows, weights)
        media = sum(f["wr"] for f in rows) / len(rows)
        print("\n=== EXPECTED LADDER WINRATE (weighted by meta share) ===")
        if wr_pond is None:
            print("no coverage: none of the measured decks carries a weight")
            return 0
        se = error_ponderado(rows, weights)
        margen = "" if se is None else (
            f"  +-{100 * 1.96 * se:.2f} (IC95 "
            f"{100 * (wr_pond - 1.96 * se):.1f}-"
            f"{100 * (wr_pond + 1.96 * se):.1f})")
        print(f"  ponderado : {100 * wr_pond:5.1f}%{margen}")
        print(f"              over {100 * cobertura:.1f}% of the meta covered")
        print(f"  unweighted: {100 * media:5.1f}%   (simple mean, for comparison)")

        # The weakest matchup is NOT where the most is lost: a 40% against an
        # archetype that is 1% costs less than an 80% against the one that is 41% of the field.
        # This orders by ladder points lost, which is where it is worth
        # investing the effort.
        sangria = [t for t in sorted(
            ((weights.get(f["deck"], 0.0) * (1 - f["wr"]), f) for f in rows),
            key=lambda t: -t[0],
        )[:3] if t[0] > 0]
        if sangria:
            print("\n  Where the most ladder points are lost:")
            for cost, f in sangria:
                print(f"    {f['deck']:<28} {100 * cost:5.2f} pts  "
                      f"(meta {100 * weights.get(f['deck'], 0.0):.0f}%, "
                      f"ganamos {100 * f['wr']:.1f}%)")
        if without_weight:
            print(f"  warning: {len(without_weight)} deck(s) with no weight, left out of the "
                  f"weighted figure: {', '.join(sorted(without_weight)[:5])}"
                  + (" ..." if len(without_weight) > 5 else ""))
        # The weighted prize differential: the metric with resolution. The
        # winrate against the bot is saturated (>93%) and cannot arbitrate a
        # change; the prizes do grade it.
        prem = [f for f in rows if f["dif_premios"] is not None]
        if prem:
            cob_p = sum(weights.get(f["deck"], 0.0) for f in prem)
            if cob_p > 0:
                dif_pond = sum(weights.get(f["deck"], 0.0) * f["dif_premios"]
                               for f in prem) / cob_p
                print(f"\n  Weighted PRIZE DIFFERENTIAL: {dif_pond:+.3f} "
                      f"per game")
                print("  (prizes we take minus the prizes the opponent takes; it has "
                      "resolution where the winrate no longer does)")

        if base_by_deck:
            base_rows = [base_by_deck[f["deck"]] for f in rows
                          if f["deck"] in base_by_deck]
            wr_base, _ = winrate_ponderado(base_rows, weights)
            if wr_base is not None:
                print(f"\n  baseline  : {100 * wr_base:5.1f}%   "
                      f"WEIGHTED DELTA = {100 * (wr_pond - wr_base):+.2f} points")
                print("  (this delta, not the simple mean, is what decides whether the "
                      "change wins ladder games)")
            base_prem = [b for b in base_rows if b.get("dif_premios") is not None]
            if prem and base_prem:
                cob_b = sum(weights.get(b["deck"], 0.0) for b in base_prem)
                if cob_b > 0 and cob_p > 0:
                    dif_b = sum(weights.get(b["deck"], 0.0) * b["dif_premios"]
                                for b in base_prem) / cob_b
                    print(f"  baseline prizes: {dif_b:+.3f}   "
                          f"PRIZE DELTA = {dif_pond - dif_b:+.3f} per game")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
