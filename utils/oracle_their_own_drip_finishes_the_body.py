"""Their own Freezing Shroud drip, graded by the ENGINE'S RULES instead of by a
bot we beat nine times out of ten.

WHY THIS EXISTS. `utils/gate_their_own_drip_finishes_the_body.py` measures a
winrate against the reference bot, and against the Marnie lists that bot is
already losing most of the games: a rule that turns a lost race into a won one
two turns earlier can be invisible there. So the question is asked the other way
round:

    on the exact boards where the reading changed the choice, does the choice it
    now makes roll out better UNDER THE ENGINE'S OWN RULES?

`search_oracle.rollout` opens a search from the real observation, forces one
option, and plays to the end. K rollouts per option, and the difference is what
the choice was worth.

THE BOARDS ARE NOT INVENTED. They are FOUND, the way the gate finds them: the
same tree loaded twice with `SHROUD_KO_READING` rebound to False in one arm,
every record in `records/` replayed side by side, and every decision the two
arms disagree on becomes a board. The record this rule was written from
(`registro_006` step 90) is one of them and is not privileged over the others.

WHAT IS READ, AND WHAT IS SAMPLED. `opponent_obs=None` everywhere: a record
keeps one seat's observations. Their hand is therefore drawn from their unseen
multiset like the prizes are, every grade is computed against a LEGAL world
rather than the true one (`hand_sampled` says so in the report), and it is the
same for both options of a board -- which is what keeps the comparison fair.

K AND THE FLOOR. K=100, because the oracle's measured noise floor says K=20 is
worth nothing and K=50 is where it becomes usable. And the floor is measured PER
BOARD rather than quoted: a second batch of the SAME option, different seeds. A
preference that does not clear its own board's floor is not a preference.

Usage:
    python utils/oracle_their_own_drip_finishes_the_body.py          # K=100
    python utils/oracle_their_own_drip_finishes_the_body.py --k 50
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


def _opponent_lists():
    """EVERY list we hold, not one archetype: the board says which one can host
    it. A file that does not parse as sixty ids is bookkeeping, not a deck."""
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
    """The list that can host THIS board, chosen by COVERAGE and not by luck.

    Closing on sixty per seat is necessary and not sufficient: `determinize`
    builds the unseen remainder as `Counter(list) - seen`, so an unrelated
    archetype can close the arithmetic by accident while silently dropping the
    very Froslass this rule is about. Every list that closes is scored by how
    much of THEIR VISIBLE BOARD it actually contains, and the best one wins.
    """
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


def _arms():
    import gate_their_own_drip_finishes_the_body as gate

    candidate = sp.load_agent(_ROOT / "main.py", "oracle_arm_with")
    base = gate.neutralise(sp.load_agent(_ROOT / "main.py", "oracle_arm_without"))
    gate.provenance(candidate, base, control=False)
    return candidate, base


def _describe(m, obs, choice):
    import golden_corpus as gc
    return [gc.describe_option(m, obs, i) for i in choice]


def _walk(records, our_deck, lists, candidate, base, boards, ungradeable):
    """Every decision of `records` where the two arms disagree, with its board.

    The two arms are walked SIDE BY SIDE so both see the same history: an
    agent's belief is built by the decisions it has already been asked about,
    and replaying one arm to the end and then the other is a different
    experiment.
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
    """The boards of the two corpora, and they are NOT the same corpus.

    * `records/` is the harvested REAL games, the ones a human read to find
      this. It is where the rule's own record lives.
    * `tests/corpus/` is the frozen fifty, every one of them an Alakazam game --
      a matchup with no Froslass in it, where the reading is the printed HP by
      construction. Walking it anyway is the cheap check that says so out loud:
      zero flips there is the claim "this rule does not leak out of the decks
      that play the card", measured rather than asserted.
    """
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
        print(f"  tests/corpus/ (los cincuenta congelados, TODOS Alakazam, sin "
              f"Froslass): {len(congelados)} tableros"
              + ("  <-- inesperado: la lectura no deberia alcanzar el matchup"
                 if congelados else "  (la lectura no alcanza el matchup)"))
        boards += congelados
    for tag in ungradeable:
        print(f"  NO GRADUABLE (ninguna lista cierra en 60): {tag}")
    return boards


def batch(obs, our_deck, their_deck, choice, k, seed0, agent):
    """K rollouts of one option, RESETTING the agent's belief between them.

    The rollout policy is our own agent, whose card tracking persists across
    calls. Without the reset the second rollout of a batch starts with the
    belief the first one ended with, and the batch measures a drift instead of
    an option.
    """
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
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, default=100, help="rollouts per batch")
    args = ap.parse_args(argv)

    import local_engine
    local_engine.load()

    candidate, base = _arms()
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
            print(f"    con la lectura {b['label_with']} -> "
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

    print(f"\nRESUMEN: {len(boards)} tableros · {real} a favor de la lectura · "
          f"{against} en contra · {floorless} dentro del suelo de su tablero"
          + (f" · {len(broken)} caidos" if broken else ""))
    for line in broken:
        print(f"  CAIDO: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
