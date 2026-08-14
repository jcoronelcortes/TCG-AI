"""The dying Supporter slot, graded by the ENGINE'S RULES instead of by a bot we
beat 99.5 % of the time.

WHY THIS EXISTS. The firing census of `utils/gate_the_cap_cashes_a_dying_slot.py`
puts the exception at ~0.02 decisions per game and the frozen corpus flips ONE
of its decisions. At that exposure a self-play winrate cannot resolve the rule
however many games it plays -- the reason is in `utils/search_oracle.py`'s own
docstring, the reference bot is saturated -- so the gate is only there to rule
out harm and the question is asked the other way round:

    on the exact boards where the rule changed the choice, does the choice it
    now makes roll out better UNDER THE ENGINE'S OWN RULES?

`search_oracle.rollout` opens a search from the real observation, forces one
option, and plays to the end. K rollouts per option, and the difference is what
the choice was worth.

THE BOARDS ARE NOT INVENTED. Three, and all three were already in the estate
before this rule existed:

  * `registro_005` step 68, the record the rule was written from -- the single
    flip of the frozen corpus, rediscovered here the way the gate finds it: the
    same tree loaded twice with `XEROSIC_FREE_SLOT_HAND` rebound out of reach in
    one arm, replayed side by side.
  * `tests/fixtures/dragapult_step138_no_pivote_hydra_condenado.json` and
  * `tests/fixtures/starmie_t6_the_prize_is_cashed_by_the_body_that_outlasts
    _step54.json` -- two boards captured for OTHER rules that happen to carry
    the same window (slot free, attack winning the menu, their hand at six, the
    cap in hand). They are the evidence the record is not a one-off, and they
    are honest witnesses precisely because nobody chose them for this.

WHAT IS READ, AND WHAT IS SAMPLED. `opponent_obs=None` everywhere: the frozen
bundle keeps one seat's observations. Their hand is therefore drawn from their
unseen multiset like the prizes are, every grade is computed against a LEGAL
world rather than the true one (`hand_sampled` says so in the report), and it is
the same for both options of a board -- which is what keeps the comparison fair.

K AND THE FLOOR. K=100, because the oracle's measured noise floor says K=20 is
worth nothing and K=50 is where it becomes usable. And the floor is measured PER
BOARD rather than quoted: a second batch of the SAME option, different seeds. A
preference that does not clear its own board's floor is not a preference.

Usage:
    python utils/oracle_the_cap_cashes_a_dying_slot.py            # K=100
    python utils/oracle_the_cap_cashes_a_dying_slot.py --k 50
    python utils/oracle_the_cap_cashes_a_dying_slot.py --only corpus
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

FIXTURES = (
    ("dragapult paso 138 (fixture)",
     _ROOT / "tests" / "fixtures"
     / "dragapult_step138_no_pivote_hydra_condenado.json"),
    ("mega starmie paso 54 (fixture)",
     _ROOT / "tests" / "fixtures"
     / "starmie_t6_the_prize_is_cashed_by_the_body_that_outlasts_step54.json"),
)


def _opponent_lists():
    """EVERY list we hold, not one archetype.

    The sibling oracle could name its opponent -- its rule only fires against
    Alakazam. This one fires against anything, and the record's own opponent
    (Mega Lopunny ex / Mega Froslass ex) has no file under `deck/opponents/` at
    all, only under the harvested five hundred. So the list is not asserted, it
    is FOUND: whichever closes the board on sixty cards per seat is the one that
    can host it, and a board no list closes is reported UNGRADEABLE rather than
    skipped in silence.
    """
    out = sorted((_ROOT / "deck" / "opponents").glob("*.csv"))
    out += sorted((_ROOT / "deck" / "real_opponents_500").glob("*.csv"))
    lists = []
    for p in out:
        # The harvested directory also holds its own bookkeeping (`pesos*.csv`,
        # the meta weights). A file that does not parse as sixty ids is not a
        # deck, and it is skipped rather than crashing the run.
        try:
            lists.append((p.stem, sp.read_deck(str(p))))
        except (ValueError, IndexError):
            continue
    return lists


def _their_deck_for(obs, our_deck, lists):
    """The list that can host THIS board, chosen by COVERAGE and not by luck.

    Closing on sixty per seat is necessary and it is not sufficient: `determinize`
    builds the unseen remainder as `Counter(list) - seen`, which silently drops a
    card the board shows but the list does not contain, so an unrelated archetype
    can close the arithmetic by accident. The first draft of this instrument
    graded a Dragapult board under an Alakazam list for exactly that reason.

    So every list that closes is scored by how much of THEIR VISIBLE BOARD it
    actually contains, and the best one wins. The coverage is returned with it
    and printed: a grade computed under a list that does not hold the opponent's
    own cards is a weaker claim, and the report has to be able to say so.
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
    import gate_the_cap_cashes_a_dying_slot as gate

    candidate = sp.load_agent(_ROOT / "main.py", "oracle_arm_with")
    base = gate.neutralise(sp.load_agent(_ROOT / "main.py", "oracle_arm_without"))
    gate.provenance(candidate, base, control=False)
    return candidate, base


def _describe(m, obs, choice):
    import golden_corpus as gc
    return [gc.describe_option(m, obs, i) for i in choice]


def _board(name, obs, our_deck, their, candidate, base, recorded):
    c_with = list(candidate.agent(obs))
    c_without = list(base.agent(obs))
    if c_with == c_without:
        print(f"  AVISO: los dos brazos eligen lo mismo en {name}; "
              f"no hay tablero que graduar")
        return []
    return [{
        "name": f"{name} [rival: {their[0]}]",
        "obs": obs,
        "our_deck": list(our_deck),
        "their_deck": their[1],
        "recorded_list": recorded,
        "with": c_with, "without": c_without,
        "label_with": _describe(candidate, obs, c_with),
        "label_without": _describe(base, obs, c_without),
    }]


def _walk(records, our_deck, lists, candidate, base, boards, ungradeable):
    """Every decision of `records` where the two arms disagree, with its board.

    The walk is `golden_corpus._replay_data`'s, kept side by side for the two
    arms so both see the same history: an agent's belief is built by the
    decisions it has already been asked about, so replaying one arm to the end
    and then the other is not the same experiment.
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
                boards += _board(tag, obs, our_deck, their,
                                 candidate, base, recorded=True)


def _corpus_boards(candidate, base):
    """The boards of the two corpora, and they are NOT the same corpus.

    * `records/` is the harvested REAL games, the ones a human read to find
      this. It is where the rule's own record lives.
    * `tests/corpus/` is the frozen fifty, and every one of them is an Alakazam
      game -- the matchup where the floor vetoes below and the cap scores in the
      thousands above, so the exception is unreachable BY CONSTRUCTION. Walking
      it anyway is the cheap check that says so out loud: zero flips there is
      the claim "this rule does not touch the matchup the card exists for",
      measured rather than asserted.
    """
    import json as _json

    import golden_corpus as gc
    from recorded_deck import deck_of_record, read_list

    lists = _opponent_lists()
    boards, ungradeable = [], []
    with deck_of_record():
        our_deck = read_list()
        vivos = {p.name: _json.loads(p.read_text(encoding="utf-8"))
                 for p in gc.record_files()}
        _walk(vivos, our_deck, lists, candidate, base, boards, ungradeable)
        print(f"  records/: {len(boards)} tableros de {len(vivos)} registros")

        congelados, _ung = [], []
        _walk(gc.frozen_records(), our_deck, lists, candidate, base,
              congelados, _ung)
        print(f"  tests/corpus/ (los cincuenta congelados, TODOS Alakazam): "
              f"{len(congelados)} tableros"
              + ("  <-- inesperado: la excepcion no deberia alcanzar el matchup"
                 if congelados else "  (la excepcion no alcanza el matchup)"))
        boards += congelados
    for tag in ungradeable:
        print(f"  NO GRADUABLE (ninguna lista cierra en 60): {tag}")
    return boards


def _fixture_boards(candidate, base):
    """The two boards the estate already held. The list is DETECTED, not
    assumed: a fixture may predate the current sixty."""
    from recorded_deck import read_list

    lists = _opponent_lists()
    boards = []
    for name, path in FIXTURES:
        if not path.exists():
            print(f"  AUSENTE: {path.name}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        obs = (data["sequence"][-1]["observation"] if "sequence" in data
               else data["observation"])
        for label, deck in (("deck.csv", sp.read_deck(str(_ROOT / "deck.csv"))),
                            ("lista del registro", list(read_list()))):
            their = _their_deck_for(obs, deck, lists)
            if their is None:
                print(f"  {name} con {label}: no cierra con ninguna lista rival")
                continue
            print(f"  {name} con {label}: cierra en sesenta por asiento "
                  f"(rival: {their[0]})")
            boards += _board(f"{name}, {label}", obs, deck, their,
                             candidate, base, recorded=label != "deck.csv")
            break
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
    ap.add_argument("--only", choices=("fixtures", "corpus"), default=None)
    args = ap.parse_args(argv)

    import local_engine
    local_engine.load()

    candidate, base = _arms()
    boards = []
    if args.only != "corpus":
        boards += _fixture_boards(candidate, base)
    if args.only != "fixtures":
        boards += _corpus_boards(candidate, base)
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
            print(f"    con la regla  {b['label_with']} -> "
                  f"{with_rule['wins']}/{args.k}  margen {with_rule['margin']:+.2f}")
            print(f"    sin ella      {b['label_without']} -> "
                  f"{without['wins']}/{args.k}  margen {without['margin']:+.2f}")
            print(f"    delta {100 * d_wr:+.0f} pp / {d_mg:+.2f} margen   "
                  f"suelo del tablero {100 * f_wr:.0f} pp / {f_mg:.2f}   "
                  f"-> {'SUPERA el suelo' if clears else 'dentro del suelo'}"
                  f"{'' if not with_rule['sampled'] else '   [mano rival MUESTREADA]'}",
                  flush=True)
    finally:
        api.search_end()

    print(f"\nRESUMEN: {len(boards)} tableros · {real} a favor de la regla · "
          f"{against} en contra · {floorless} dentro del suelo de su tablero"
          + (f" · {len(broken)} caidos" if broken else ""))
    for line in broken:
        print(f"  CAIDO: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
