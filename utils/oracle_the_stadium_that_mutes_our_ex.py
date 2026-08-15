"""The stadium that mutes our ex, graded by the ENGINE'S RULES.

WHY THIS EXISTS. `NZ_MUTE_ROUTING` teaches the ENERGY ROUTING what the damage
model already knew: under Neutralization Zone every ex of ours does zero to a
body without a Rule Box, so on a board where their whole side is Rule-Box-less
the turn's Grass belongs to our non-ex -- Meganium, Tapu Bulu, Dipplin, Pinsir
-- and not to the Ogerpon ex that Teal Dance would charge nor to the Hydrapple
ex standing mute in front. The two halves are in
`ptcg/turn/options/ability.py` (the dance joins the wall rung it already has for
Crustle and Cornerstone) and `ptcg/turn/energy.py` (the bench halves of the
stadium's own bands stop being development while the front is mute).

WHY NOT THE WINRATE. `utils/gate_the_stadium_that_mutes_our_ex.py --census` says
the board is NOT rare: 3 to 11 mute readings per game against the five meta
lists that get the card down. The winrate still cannot see it, because against
the reference bot those matchups already sit at 95-99 % -- the saturation this
oracle exists for. Measured at n=1000 per list the delta was +0.05 pp overall,
inside the spread the two CONTROL lists (where the arms are provably the same
code) show on the same run.

So the question is asked the other way round, the way its siblings ask it:

    on the exact boards where the reading changed the choice, does the choice it
    now makes roll out better UNDER THE ENGINE'S OWN RULES?

THE BOARDS ARE FOUND, NOT INVENTED: the same tree loaded twice with
`NZ_MUTE_ROUTING` rebound to False in one arm, both corpora replayed side by
side, and every decision the two arms disagree on becomes a board. The record
the reading was written from (`registro_010` step 70) is one of them and is not
privileged over the others.

K AND THE FLOOR. K=100, because the oracle's own measured noise floor says K=20
is worth nothing and K=50 is where it becomes usable; and the floor is measured
PER BOARD -- a second batch of the SAME option with different seeds -- rather
than quoted. A preference that does not clear its own board's floor is not a
preference.

WHAT IT MEASURED (14 August 2026, K=100). Six boards, all six from the record's
own game, and the verdict is SPLIT: three for the reading (turns 12, 14 and 16:
+9, +15 and +9 pp, margins +0.97 / +0.91 / +0.23) and three against (turn 10 at
-2 pp against a 1 pp floor, and both turn-18 boards at -5 and -10 pp). Net +16 pp
and +0.68 of margin over the six, which is not a result to lean on.

READ THE NEGATIVES WITH THIS CAVEAT, because it is not symmetric. No list we
hold is the opponent this record was played against -- a Mesprit / Uxie / Azelf
deck with no ex in it at all -- so `_their_deck_for` grades on proxies that
cover 36-39 % of the board, and those proxies (alakazam, comfey_yveltal_nz)
CARRY EX. The moment the rollout's opponent promotes one, the stadium stops
muting us and the Grass the baseline arm poured into an Ogerpon ex starts
paying: a game the real board could never have produced. The three boards that
came out against are the three where that matters most, and the honest reading
of this file is that it did not settle the question rather than that it settled
it against.

The two turn-18 boards also share a shape worth naming if this is revisited: we
are 5 prizes to 3 down with a 50 HP active, and the Grass moved does NOT put the
Meganium at its cost (0 of 4, one card = 2 effective). That is the same trade
the Cornerstone half of `_wall_atk_needs_grass` already measured and lost by 0.9
points -- "reserve the Grass when it puts the attacker AT its cost, not merely
when the attacker is under it". The NZ arm deliberately keeps the LOOSER Crustle
reading, because tightening it would put the record's own board back on Teal
Dance; the choice is written down here so it can be argued with rather than
rediscovered.

Usage:
    python utils/oracle_the_stadium_that_mutes_our_ex.py
    python utils/oracle_the_stadium_that_mutes_our_ex.py --k 50
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
    """Switch the ROUTING reading off in `agent_module`, in place.

    It is the flag inside that arm's own `ptcg.calc.damage` that has to move:
    `_nz_mutes_our_ex` reads it from its own module globals at call time, and
    the two consumers hold that same function object, so one assignment switches
    both halves. `_our_effective_damage` is untouched and keeps projecting the
    stadium's zero correctly in BOTH arms -- the arms differ in what the routing
    does with that knowledge, not in the knowledge.
    """
    agent_module._our_effective_damage.__globals__['NZ_MUTE_ROUTING'] = False
    return agent_module


def _reading_of(agent_module):
    return agent_module._our_effective_damage.__globals__['NZ_MUTE_ROUTING']


def provenance(candidate, base):
    """Refuse to measure two arms that are secretly the same agent."""
    if candidate is base or candidate._our_effective_damage is base._our_effective_damage:
        raise SystemExit("los dos brazos son el MISMO modulo")
    if not _reading_of(candidate) or _reading_of(base):
        raise SystemExit(
            "los brazos no difieren en NZ_MUTE_ROUTING: "
            f"candidato={_reading_of(candidate)} base={_reading_of(base)}")


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

    candidate = sp.load_agent(_ROOT / "main.py", "oracle_nz_with")
    base = neutralise(sp.load_agent(_ROOT / "main.py", "oracle_nz_without"))
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
            print(f"    con la lectura  {b['label_with']} -> "
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
