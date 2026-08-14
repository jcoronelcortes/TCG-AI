"""Where the agent's own scorer says it has no opinion — and what the RULES say.

D2 of phase D. The oracle (`utils/search_oracle.py`) does not have to replace the
scorer to be useful; it only has to break the ties the scorer cannot. That is the
cheapest possible first job for it and the population is already on record: the
280 Ripening ↔ Teal Dance ties of
[[el-adjunte-del-turno-y-la-habilidad-empatan-sobre-el-mismo-cuerpo]], where
making `ABILITY:150` the owner was measured and REVERTED, and C2's TIER-vs-score
rows ([[c2-y-los-280-empates-son-el-mismo-eje-el-orden-del-teal-dance]]).

**A tie here is: the top two options share a TIER and their scores are within ε.**
The tier is what decides first (`ptcg/turn/finalize.py`), so two options in
different tiers are not tied however close their numbers are — the order already
settled them.

WHAT IT RUNS ON. The frozen corpus: 50 records, deterministic, and every
observation in it carries `search_begin_input`, which is what the oracle needs to
open a search. Two consequences the report must carry:

  * the corpus keeps **one seat's** observations, so the opponent's hand is
    SAMPLED rather than read (`determinize(opponent_obs=None)`). Every grade here
    is against a legal world, not the true one;
  * the corpus was played with the list of before 14 August, so the replay runs
    under THAT list ([[una-repeticion-es-una-partida-de-la-lista-de-su-dia]]) and
    the oracle is handed the same sixty.

THE CRITERION, and it is the plan's, written before the run:

  * the oracle prefers one side by more than the measured noise floor, over a
    class of population ≥ 30 → **a rule to write**, ranked, not written here;
  * the preference is inside the floor → the tie is a genuine indifference.
    **Record it and stop paying attention to it.** That is a real result and, on
    a scorer this heavily tuned, the likely one.

⚠️ **K=20 is not enough.** The oracle's own floor says its worst pair of batches
of the SAME option disagrees by 30 pp at K=20 and by 8 at K=50. Nothing here runs
below K=50, and the floor is re-measured in the same run rather than quoted from
another day.
"""

import argparse
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import search_oracle as so  # noqa: E402
from cg import api  # noqa: E402

_FINALIZE = "ptcg.turn.finalize"
_SINK = "TIER_CENSUS_SINK"
_RECORD = re.compile(r"registro_\d+_(.+)_asiento(\d)\.json")
_DECK_DIRS = ("deck/real_opponents_500", "deck/real_opponents", "deck/opponents")


def opponent_deck_of(record_name):
    """The opposing 60 the record was played against, by its own file name."""
    import selfplay as sp

    match = _RECORD.match(record_name)
    if not match:
        return None
    stem = match.group(1)
    for base in _DECK_DIRS:
        path = _ROOT / base / f"{stem}.csv"
        if path.exists():
            return sp.read_deck(str(path))
    return None


def collect_ties(agent, eps, only=None, verbose=True):
    """Replay the corpus and return every MAIN menu whose top two are tied."""
    import golden_corpus as gc
    from tier_inversion_census import _label, espacios_del_agente

    spaces = {name: space for name, space in espacios_del_agente(agent)}
    space = spaces.get(_FINALIZE)
    if space is None or _SINK not in space:
        raise SystemExit(f"no seam {_SINK} in {_FINALIZE}: no census")
    card_table = space["card_table"]
    get_card = space["get_card"]
    select_context = space["SelectContext"]
    option_type = space["OptionType"]

    here = {"obs": None, "record": None}
    found, menus = [], [0]

    def sink(context, select, scores, tiers, obs, my_index):
        if context != select_context.MAIN or len(scores) < 2:
            return
        menus[0] += 1
        order = sorted(range(len(scores)), key=lambda i: (tiers[i], scores[i]),
                       reverse=True)
        a, b = order[0], order[1]
        if tiers[a] != tiers[b]:
            return                      # the ORDER settled it, not the number
        gap = abs(scores[a] - scores[b])
        if gap > eps:
            return
        found.append({
            "record": here["record"],
            "turn": obs.current.turn,
            "action": obs.current.turnActionCount,
            "obs": here["obs"],
            "options": (a, b),
            "scores": (scores[a], scores[b]),
            "tier": tiers[a],
            "gap": gap,
            "labels": (_label(select, obs, my_index, a, card_table, get_card, option_type),
                       _label(select, obs, my_index, b, card_table, get_card, option_type)),
        })

    records = gc.frozen_records()
    previous = space[_SINK]
    space[_SINK] = sink
    try:
        for name, data in sorted(records.items()):
            if only and only not in name:
                continue
            here["record"] = name
            seat = data.get("seat")
            if seat not in (0, 1):
                seat = gc.our_index(data)
            agent_mod = agent
            gc.reset_agent(agent_mod)
            for step in data.get("steps", []):
                for item in step:
                    obs = item.get("observation") or {}
                    cur = obs.get("current") or {}
                    if (item.get("status") != "ACTIVE" or not obs.get("select")
                            or cur.get("yourIndex") != seat):
                        continue
                    here["obs"] = obs
                    agent_mod.agent(obs)
    finally:
        space[_SINK] = previous
    if verbose:
        print(f"{menus[0]} menus MAIN, {len(found)} empates "
              f"(mismo tier, |gap| <= {eps})")
    return found


def collect_ties_selfplay(agent, eps, games, their_deck, our_deck, lib,
                          seed0=1, verbose=True):
    """The same census over games we drive ourselves, for two reasons.

    The corpus is fifty records and a class of eleven cannot be closed on it. And
    driving both seats means the OPPONENT'S observation is in hand, so these ties
    are graded against their real hand instead of a sampled one — a strictly
    stronger claim than anything the corpus can support.
    """
    from cg.battle import Battle
    from opponent_bot import OpponentBot
    from tier_inversion_census import _label, espacios_del_agente

    spaces = {name: space for name, space in espacios_del_agente(agent)}
    space = spaces[_FINALIZE]
    card_table = space["card_table"]
    get_card = space["get_card"]
    select_context = space["SelectContext"]
    option_type = space["OptionType"]

    here = {"obs": None, "other": None, "game": None}
    found, menus = [], [0]

    def sink(context, select, scores, tiers, obs, my_index):
        if context != select_context.MAIN or len(scores) < 2:
            return
        menus[0] += 1
        order = sorted(range(len(scores)), key=lambda i: (tiers[i], scores[i]),
                       reverse=True)
        a, b = order[0], order[1]
        if tiers[a] != tiers[b] or abs(scores[a] - scores[b]) > eps:
            return
        found.append({
            "record": f"selfplay_{here['game']}", "turn": obs.current.turn,
            "action": obs.current.turnActionCount, "obs": here["obs"],
            "opponent_obs": here["other"], "options": (a, b),
            "scores": (scores[a], scores[b]), "tier": tiers[a],
            "gap": abs(scores[a] - scores[b]),
            "labels": (_label(select, obs, my_index, a, card_table, get_card, option_type),
                       _label(select, obs, my_index, b, card_table, get_card, option_type)),
        })

    previous = space[_SINK]
    space[_SINK] = sink
    try:
        for game in range(games):
            here["game"] = game
            bot = OpponentBot()
            us = game % 2                      # alternate seats, as the gate does
            decks = (our_deck, their_deck) if us == 0 else (their_deck, our_deck)
            battle = Battle(list(decks[0]), list(decks[1]), seed=seed0 + game, lib=lib)
            last = {}
            try:
                agent._init_cards_tracking()
                steps = 0
                while battle.result == -1 and steps < 400:
                    obs = battle.obs
                    seat = obs["current"]["yourIndex"]
                    last[seat] = obs
                    if seat == us:
                        here["obs"], here["other"] = obs, last.get(1 - us)
                        choice = agent.agent(obs)
                    else:
                        choice = bot.agent(obs)
                    battle.select(choice)
                    steps += 1
            except Exception:                  # noqa: BLE001 - a dead game is not a finding
                pass
            finally:
                battle.finish()
            if verbose and (game + 1) % 20 == 0:
                print(f"  ... {game + 1} partidas, {len(found)} empates", flush=True)
    finally:
        space[_SINK] = previous
    if verbose:
        print(f"{menus[0]} menus MAIN en {games} partidas, {len(found)} empates")
    return found


def _class_of(tie):
    """The tie CLASS: what kind of choice it is, not which board it was on."""
    a, b = tie["labels"]
    return " ~ ".join(sorted((str(a).split(" ")[0], str(b).split(" ")[0])))


def grade(ties, our_deck, k=50, limit=None, verbose=True,
          fixed_opponent=None):
    """Roll out both sides of each tie and return the rows."""
    rows = []
    for n, tie in enumerate(ties if limit is None else ties[:limit]):
        their_deck = (fixed_opponent if fixed_opponent is not None
                      else opponent_deck_of(tie["record"]))
        if their_deck is None:
            continue
        try:
            other = tie.get("opponent_obs")
            a = so.score_option(tie["obs"], other, our_deck, their_deck,
                                [tie["options"][0]], k=k, seed0=7000 + 10 * n)
            b = so.score_option(tie["obs"], other, our_deck, their_deck,
                                [tie["options"][1]], k=k, seed0=9000 + 10 * n)
        except (so.DeterminizationError, ValueError) as exc:
            rows.append({**tie, "error": str(exc)[:120]})
            continue
        rows.append({**tie, "a": a, "b": b,
                     "delta_margin": (a["margin"] or 0) - (b["margin"] or 0),
                     "delta_wins": (a["wins"] - b["wins"]) / k})
        if verbose and (n + 1) % 10 == 0:
            print(f"  ... {n + 1} empates juzgados", flush=True)
    return rows


def noise_floor(ties, our_deck, k=50, samples=6):
    """The floor MEASURED IN THIS RUN: same option, two independent batches."""
    gaps_margin, gaps_wr = [], []
    for n, tie in enumerate(ties[:samples]):
        their_deck = opponent_deck_of(tie["record"])
        if their_deck is None:
            continue
        try:
            a = so.score_option(tie["obs"], None, our_deck, their_deck,
                                [tie["options"][0]], k=k, seed0=100 + 10 * n)
            b = so.score_option(tie["obs"], None, our_deck, their_deck,
                                [tie["options"][0]], k=k, seed0=5000 + 10 * n)
        except (so.DeterminizationError, ValueError):
            continue
        gaps_margin.append(abs((a["margin"] or 0) - (b["margin"] or 0)))
        gaps_wr.append(abs(a["wins"] - b["wins"]) / k)
    if not gaps_margin:
        return None
    return {"margin_median": statistics.median(gaps_margin),
            "margin_worst": max(gaps_margin),
            "wr_median": statistics.median(gaps_wr),
            "wr_worst": max(gaps_wr),
            "pairs": len(gaps_margin)}


def report(rows, floor, min_population=30):
    """By CLASS, with the criterion applied and its three verdicts named."""
    by_class = defaultdict(list)
    for row in rows:
        if "error" in row:
            continue
        by_class[_class_of(row)].append(row)

    errores = [r for r in rows if "error" in r]
    print(f"\n{len(rows)} empates juzgados, {len(errores)} sin poder juzgar")
    if errores:
        muestras = {e["error"][:60] for e in errores}
        for m in sorted(muestras)[:4]:
            print(f"    {m}")
    if floor:
        print(f"\nSUELO DE RUIDO de ESTA corrida ({floor['pairs']} pares, misma opcion): "
              f"margen mediana {floor['margin_median']:.2f} / PEOR {floor['margin_worst']:.2f}"
              f"   winrate mediana {100*floor['wr_median']:.0f} pp / PEOR "
              f"{100*floor['wr_worst']:.0f} pp")
    # THE FLOOR IS PER TIE, THE CLAIM IS PER CLASS, and confusing the two is how
    # this report would have hidden every finding it has. The floor above is the
    # noise of ONE tie's delta; a class of n ties averages it down by sqrt(n).
    # So the threshold is the class's own standard error, and the floor stays on
    # the page as the sanity check that a single row means anything at all.
    print(f"\n{'clase':<34}{'n':>5}{'margen A-B':>12}{'IC95':>18}  veredicto")
    print("-" * 100)
    for clase, filas in sorted(by_class.items(), key=lambda kv: -len(kv[1])):
        deltas = [f["delta_margin"] for f in filas]
        media = statistics.mean(deltas)
        se = (statistics.stdev(deltas) / len(deltas) ** 0.5) if len(deltas) > 1 else None
        ic = 1.96 * se if se else None
        excluye = ic is not None and abs(media) > ic
        if len(filas) < min_population:
            verdict = f"poblacion < {min_population}: no se concluye"
        elif not excluye:
            verdict = "INDIFERENCIA: el empate es real, dejar de mirarlo"
        else:
            lado = "la PRIMERA" if media > 0 else "la SEGUNDA"
            verdict = f"REGLA A ESCRIBIR: el oraculo prefiere {lado}"
        rango = f"[{media - ic:+.3f}, {media + ic:+.3f}]" if ic else "-"
        print(f"{clase:<34}{len(filas):>5}{media:>+12.3f}{rango:>18}  {verdict}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--eps", type=float, default=0.0,
                    help="score distance that counts as a tie (default 0: exact)")
    ap.add_argument("--k", type=int, default=50,
                    help="rollouts per option; below 50 the floor eats the answer")
    ap.add_argument("--limit", type=int, default=None,
                    help="judge only the first N ties (a smoke run)")
    ap.add_argument("--only", default=None, help="substring of the record name")
    ap.add_argument("--games", type=int, default=0,
                    help="instead of the corpus, drive N self-play games -- which "
                         "also puts the opponent's REAL hand in hand")
    ap.add_argument("--opponent", default="deck/real_opponents_500/crustle_wall_1.csv",
                    help="opposing deck for --games")
    ap.add_argument("--class-only", default=None,
                    help="grade only the ties of this class, e.g. 'ABILITY ~ ATTACH'")
    ap.add_argument("--dump", default=None, metavar="CSV",
                    help="write one row per tie, so any view can be recomputed "
                         "without rolling the dice again")
    ap.add_argument("--collect-only", action="store_true",
                    help="count the ties and stop, without any rollout")
    args = ap.parse_args(argv)

    import local_engine
    import selfplay as sp
    from recorded_deck import PRE_2026_08_14, read_list

    local_engine.load()
    agent = sp.load_agent(_ROOT / "main.py", "d2")
    our_deck = read_list(PRE_2026_08_14)

    import golden_corpus as gc
    from recorded_deck import deck_of_record

    if args.games:
        their = sp.read_deck(str(_ROOT / args.opponent))
        our_deck = read_list(_ROOT / "deck.csv")     # self-play plays TODAY's list
        ties = collect_ties_selfplay(agent, args.eps, args.games, their,
                                     our_deck, local_engine.load())
        fixed = their
    else:
        with deck_of_record():
            ties = collect_ties(agent, args.eps, only=args.only)
        fixed = None
    if args.class_only:
        ties = [t for t in ties if _class_of(t) == args.class_only]
        print(f"  filtrado a la clase {args.class_only!r}: {len(ties)} empates")
    if args.collect_only or not ties:
        by_class = defaultdict(int)
        for tie in ties:
            by_class[_class_of(tie)] += 1
        for clase, n in sorted(by_class.items(), key=lambda kv: -kv[1]):
            print(f"  {clase:<44}{n:>5}")
        return 0

    if args.k < 50:
        print(f"ATENCION: K={args.k} esta por debajo del suelo utilizable (50). "
              "Los veredictos de abajo no valen.")
    floor = noise_floor(ties, our_deck, k=args.k)
    rows = grade(ties, our_deck, k=args.k, limit=args.limit,
                 fixed_opponent=fixed)
    if args.dump:
        import csv as _csv

        with open(args.dump, "w", encoding="utf-8-sig", newline="") as fh:
            w = _csv.writer(fh)
            w.writerow(["record", "turn", "action", "clase", "label_a", "label_b",
                        "tier", "wins_a", "wins_b", "margin_a", "margin_b",
                        "delta_margin", "error"])
            for r in rows:
                w.writerow([r["record"], r["turn"], r["action"], _class_of(r),
                            r["labels"][0], r["labels"][1], r["tier"],
                            (r.get("a") or {}).get("wins"), (r.get("b") or {}).get("wins"),
                            (r.get("a") or {}).get("margin"), (r.get("b") or {}).get("margin"),
                            r.get("delta_margin"), r.get("error", "")])
        print(f"filas en {args.dump}")
    report(rows, floor)
    api.search_end()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
