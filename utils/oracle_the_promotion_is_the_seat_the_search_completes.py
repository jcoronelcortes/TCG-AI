"""The seat the search completes, graded by the ENGINE'S RULES.

WHY THIS EXISTS. `PROMOTE_SEAT_THE_SEARCH_COMPLETES` widens the
evolution-survivor promotion (`_ev_*`): the evolutions a benched body can wear
next turn are the ones in HAND *plus* the ones a Pokemon-search Supporter in
hand can still buy out of the DECK. Its premise is a narrow board -- our active
knocked out, NOTHING on the bench surviving their projected blow, a
pre-evolution that has been down a turn, the tutor in hand and a copy of the
evolution still in the deck -- and the golden corpus finds exactly ONE decision
in the whole corpus that it flips (`registro_004` step 59 vs Mega Lucario ex).

A winrate cannot resolve a decision that happens once in a corpus. So the
question is asked the other way round, the way its two siblings ask it
(`oracle_the_promotion_bets_when_it_can_walk_back.py`,
`oracle_their_own_drip_finishes_the_body.py`):

    on the exact boards where the rule changed the choice, does the choice it
    now makes roll out better UNDER THE ENGINE'S OWN RULES?

THE BOARDS ARE FOUND, NOT INVENTED: the same tree loaded twice with
`PROMOTE_SEAT_THE_SEARCH_COMPLETES` rebound to False in one arm, both corpora
replayed side by side, and every decision the two arms disagree on becomes a
board. The record the rule was written from is one of them and is not
privileged over the others.

K AND THE FLOOR. K=100, because the oracle's own measured noise floor says K=20
is worth nothing and K=50 is where it becomes usable; and the floor is measured
PER BOARD -- a second batch of the SAME option with different seeds -- rather
than quoted. A preference that does not clear its own board's floor is not a
preference.

Usage:
    python utils/oracle_the_promotion_is_the_seat_the_search_completes.py
    python utils/oracle_the_promotion_is_the_seat_the_search_completes.py --k 50
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


def neutralise(agent_module):
    """Switch the SEARCH route off in `agent_module`, in place.

    The flag is read from main.py's own globals inside the `_ev_*` block, so
    rebinding the module attribute leaves the route already in HAND exactly as
    it was -- which is the whole point: the two arms differ in one sentence.
    """
    agent_module.PROMOTE_SEAT_THE_SEARCH_COMPLETES = False
    return agent_module


def provenance(candidate, base):
    """Refuse to measure two arms that are secretly the same agent."""
    if candidate is base:
        raise SystemExit("los dos brazos son el MISMO modulo")
    if not candidate.PROMOTE_SEAT_THE_SEARCH_COMPLETES or base.PROMOTE_SEAT_THE_SEARCH_COMPLETES:
        raise SystemExit(
            "los brazos no difieren en PROMOTE_SEAT_THE_SEARCH_COMPLETES: "
            f"candidato={candidate.PROMOTE_SEAT_THE_SEARCH_COMPLETES} "
            f"base={base.PROMOTE_SEAT_THE_SEARCH_COMPLETES}")


def _opponent_lists():
    """Every list we hold: the board says which one can host it."""
    out = sorted((_ROOT / "deck" / "opponents").glob("*.csv"))
    out += sorted((_ROOT / "deck" / "real_opponents_500").glob("*.csv"))
    lists = []
    for p in out:
        try:
            lists.append((p.stem, sp.read_deck(str(p))))
        except (ValueError, IndexError):
            continue
    return lists


def _their_deck_for(obs, our_deck, lists):
    """The list that can host THIS board, chosen by COVERAGE and not by luck."""
    from collections import Counter

    them = 1 - obs["current"]["yourIndex"]
    seen = so._ids_seen(obs, them)
    best = None
    for label, deck in lists:
        try:
            so.determinize(obs, None, our_deck, deck, rng=random.Random(7))
        except so.DeterminizationError:
            continue
        hit = sum((seen & Counter(deck)).values())
        total = sum(seen.values()) or 1
        if best is None or hit > best[2]:
            best = (label, deck, hit, total)
    if best is None:
        return None
    return (f"{best[0]} ({100 * best[2] / best[3]:.0f}% de su tablero)",
            best[1])


def _describe(m, obs, choice):
    import golden_corpus as gc
    return [gc.describe_option(m, obs, i) for i in choice]


def _walk(records, our_deck, lists, candidate, base, boards, ungradeable):
    """Every decision of `records` where the two arms disagree, with its board.

    Walked SIDE BY SIDE so both arms see the same history: an agent's belief is
    built by the decisions it has already been asked about.
    """
    import golden_corpus as gc

    for name, data in sorted(records.items()):
        seat = data.get("seat")
        if seat not in (0, 1):
            seat = gc.our_index(data)
        gc.reset_agent(candidate)
        gc.reset_agent(base)
        for step in data.get("steps", []):
            for item in step:
                obs = item.get("observation") or {}
                cur = obs.get("current") or {}
                if (item.get("status") != "ACTIVE" or not obs.get("select")
                        or cur.get("yourIndex") != seat):
                    continue
                c_with = list(candidate.agent(obs))
                c_without = list(base.agent(obs))
                if c_with == c_without:
                    continue
                tag = (f"{name} paso {obs.get('step')} "
                       f"(turno {cur.get('turn')})")
                their = _their_deck_for(obs, our_deck, lists)
                if their is None:
                    ungradeable.append(tag)
                    continue
                boards.append({
                    "name": f"{tag} [rival: {their[0]}]",
                    "obs": obs,
                    "our_deck": list(our_deck),
                    "their_deck": their[1],
                    "with": c_with, "without": c_without,
                    "label_with": _describe(candidate, obs, c_with),
                    "label_without": _describe(base, obs, c_without),
                })


def _corpus_boards(candidate, base):
    """Both corpora: the harvested records and the frozen fifty."""
    import golden_corpus as gc
    from recorded_deck import deck_of_record, read_list

    lists = _opponent_lists()
    boards, ungradeable = [], []
    with deck_of_record():
        our_deck = read_list()
        vivos = {p.name: json.loads(p.read_text(encoding="utf-8"))
                 for p in gc.record_files()}
        _walk(vivos, our_deck, lists, candidate, base, boards, ungradeable)
        print(f"  records/: {len(boards)} tableros de {len(vivos)} registros")

        congelados, _ung = [], []
        _walk(gc.frozen_records(), our_deck, lists, candidate, base,
              congelados, _ung)
        print(f"  tests/corpus/ (los cincuenta congelados): "
              f"{len(congelados)} tableros")
        boards += congelados
        ungradeable += _ung
    for tag in ungradeable:
        print(f"  NO GRADUABLE (ninguna lista cierra en 60): {tag}")
    return boards


def batch(obs, our_deck, their_deck, choice, k, seed0, agent):
    """K rollouts of one option, RESETTING the agent's belief between them."""
    wins, margin, sampled = 0, [], 0
    us = obs["current"]["yourIndex"]
    for i in range(k):
        sp._reset_si_aplica(agent)
        r = so.rollout(obs, None, our_deck, their_deck, choice,
                       seed=seed0 + i, policy="agent", agent=agent.agent)
        wins += 1 if r["won"] else 0
        pl = r["prizes_left"]
        if len(pl) == 2:
            margin.append(pl[1 - us] - pl[us])
        sampled += 1 if r["determinization"].get("hand_sampled") else 0
    return {"wins": wins, "k": k, "sampled": sampled,
            "margin": (sum(margin) / len(margin)) if margin else 0.0}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, default=100, help="rollouts per batch")
    args = ap.parse_args(argv)

    import local_engine
    local_engine.load()

    candidate = sp.load_agent(_ROOT / "main.py", "oracle_arm_with")
    base = neutralise(sp.load_agent(_ROOT / "main.py", "oracle_arm_without"))
    provenance(candidate, base)

    boards = _corpus_boards(candidate, base)
    if not boards:
        raise SystemExit("no hay tableros que graduar")

    print(f"\n{len(boards)} tableros, K={args.k} por lote, "
          f"politica = nuestro agente en los dos asientos\n")

    real, against, floorless, broken = 0, 0, 0, []
    try:
        for b in boards:
            their = b["their_deck"]
            try:
                with_rule = batch(b["obs"], b["our_deck"], their, b["with"],
                                  args.k, 0, candidate)
                without = batch(b["obs"], b["our_deck"], their, b["without"],
                                args.k, 0, candidate)
                floor_b = batch(b["obs"], b["our_deck"], their, b["without"],
                                args.k, 500_000, candidate)
            except Exception as exc:            # noqa: BLE001 - reported, not swallowed
                broken.append(f"{b['name']}: {type(exc).__name__} {exc}")
                print(f"{b['name']}\n    CAIDO: {type(exc).__name__} {exc}",
                      flush=True)
                continue
            d_wr = (with_rule["wins"] - without["wins"]) / args.k
            d_mg = with_rule["margin"] - without["margin"]
            f_wr = abs(without["wins"] - floor_b["wins"]) / args.k
            f_mg = abs(without["margin"] - floor_b["margin"])
            clears = abs(d_wr) > f_wr or abs(d_mg) > f_mg
            if not clears:
                floorless += 1
            elif d_wr > 0 or d_mg > 0:
                real += 1
            else:
                against += 1
            print(f"{b['name']}")
            print(f"    con la busqueda {b['label_with']} -> "
                  f"{with_rule['wins']}/{args.k}  margen {with_rule['margin']:+.2f}")
            print(f"    sin ella       {b['label_without']} -> "
                  f"{without['wins']}/{args.k}  margen {without['margin']:+.2f}")
            print(f"    delta {100 * d_wr:+.0f} pp / {d_mg:+.2f} margen   "
                  f"suelo del tablero {100 * f_wr:.0f} pp / {f_mg:.2f}   "
                  f"-> {'SUPERA el suelo' if clears else 'dentro del suelo'}"
                  f"{'' if not with_rule['sampled'] else '   [mano rival MUESTREADA]'}",
                  flush=True)
    finally:
        api.search_end()

    print(f"\nRESUMEN: {len(boards)} tableros · {real} a favor de la busqueda · "
          f"{against} en contra · {floorless} dentro del suelo de su tablero"
          + (f" · {len(broken)} caidos" if broken else ""))
    for line in broken:
        print(f"  CAIDO: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
