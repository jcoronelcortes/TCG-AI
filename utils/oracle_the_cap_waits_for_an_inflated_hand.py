"""The prize-dependent Xerosic floor, graded by the ENGINE'S RULES instead of by
a bot we beat 99.5 % of the time.

WHY THIS EXISTS. `utils/gate_the_cap_waits_for_an_inflated_hand.py` measured the
rule at 5000 games per arm and came back NEUTRAL: -0.06 pts against a noise floor
of +0.12 pts taken in the same session with the same code in both arms. The
reason is written in `utils/search_oracle.py`'s own docstring -- the reference bot
is SATURATED, so every close-game capability is priced in a vanishing fraction of
the games -- and the exposure made it worse: the rule moves 7 of 3580 corpus
decisions (0.20 %).

So the question is asked the other way round. Not "does the agent win more games
against the bot", which this instrument cannot answer, but: **on the exact boards
where the rule changed the choice, does the choice it now makes roll out better
under the engine's own rules?** `search_oracle.rollout` opens a search from the
real observation, forces one option, and plays to the end. K rollouts per option
and the difference is what the choice was worth.

THE BOARDS ARE NOT INVENTED. They are the eight the change actually moved:

  * `records/registro_003` step 29, the record the rule was written from -- kept
    in `tests/fixtures/` and, since `records/` was re-harvested on 14 August,
    the only surviving copy of that lost game;
  * the seven flips of the frozen corpus, rediscovered here the way the gate
    finds them: the same tree loaded twice with `XEROSIC_ALAKAZAM_FLOOR_EARLY`
    rebound to the late floor in one arm, replayed side by side, and every
    decision where the two disagree is a board.

WHAT IS READ, AND WHAT IS SAMPLED. `opponent_obs=None` for every board: the
frozen bundle keeps one seat's observations and the fixture is one observation,
so their hand is drawn from their unseen multiset like the prizes are. Every
grade here is therefore computed against a LEGAL world and not the true one --
`hand_sampled` in the report says so, and it is the same for both options of a
board, which is what keeps the comparison fair.

THE LIST OF THE RECORD. The corpus boards are replayed and rolled out under
`recorded_deck.deck_of_record()`, for the reason `golden_corpus.replay_data`
states: today's sixty cards would file the extra copies as prizes and move
decisions on nothing. The fixture's own list is DETECTED rather than assumed --
whichever of the two closes on sixty per seat is the one it was played with, and
the determinization guard is what answers.

K AND THE FLOOR. K=100, because the oracle's measured noise floor says K=20 is
worth nothing (its worst pair of identical batches disagrees by 30 pp) and K=50
is where it becomes usable. And the floor is measured PER BOARD rather than
quoted: a second batch of the SAME option, different seeds. A preference that
does not clear its own board's floor is not a preference.

Usage:
    python utils/oracle_the_cap_waits_for_an_inflated_hand.py            # K=100
    python utils/oracle_the_cap_waits_for_an_inflated_hand.py --k 50
    python utils/oracle_the_cap_waits_for_an_inflated_hand.py --only fixture
"""

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import search_oracle as so  # noqa: E402
import selfplay as sp  # noqa: E402
from cg import api  # noqa: E402

FIXTURE = (_ROOT / "tests" / "fixtures"
           / "alakazam_the_cap_waits_for_an_inflated_hand_step29.json")


def _opponent_lists():
    """Every Alakazam build we hold, because the corpus is not ONE opponent.

    The first run of this instrument passed `deck/opponents/alakazam.csv` to all
    eight boards and died on the second: `seat 1: 24 seen + 0 hand + 6 prize +
    31 deck = 61, not 60`. The fifty frozen records are fifty different games
    against different Alakazam lists, and a board is only gradeable under a list
    that can actually host what is on their side of it. The guard refusing to
    close is the instrument working -- the engine would have accepted the
    61-card world and played a different game -- so the answer is to look for
    the list that fits and to SAY SO when none does.
    """
    out = [(_ROOT / "deck" / "opponents" / "alakazam.csv")]
    out += sorted((_ROOT / "deck" / "real_opponents_500").glob("alakazam*.csv"))
    return [(p.stem, sp.read_deck(str(p))) for p in out if p.exists()]


def _their_deck_for(obs, our_deck, lists):
    """The first Alakazam list under which this board closes on sixty per seat,
    or None -- which makes the board UNGRADEABLE and is reported as such rather
    than skipped in silence."""
    import random

    for label, deck in lists:
        try:
            so.determinize(obs, None, our_deck, deck, rng=random.Random(7))
        except so.DeterminizationError:
            continue
        return label, deck
    return None


def _arms():
    """The two agents the gate uses: with the rule, and with the floor as it was."""
    import gate_the_cap_waits_for_an_inflated_hand as gate

    candidate = sp.load_agent(_ROOT / "main.py", "oracle_arm_with")
    base = gate.neutralise(sp.load_agent(_ROOT / "main.py", "oracle_arm_without"))
    gate.provenance(candidate, base, control=False)
    return candidate, base


def _describe(m, obs, choice):
    import golden_corpus as gc
    return [gc.describe_option(m, obs, i) for i in choice]


def _corpus_boards(candidate, base):
    """Every frozen-corpus decision where the two arms disagree, with its board.

    The walk is `golden_corpus._replay_data`'s, kept side by side for the two
    arms so that both see the same history: an agent's belief is built by the
    decisions it has already been asked about, so replaying one arm to the end
    and then the other is not the same experiment.
    """
    import golden_corpus as gc
    from recorded_deck import deck_of_record, read_list

    lists = _opponent_lists()
    boards, ungradeable = [], []
    with deck_of_record():
        our_deck = read_list()
        for name, data in sorted(gc.frozen_records().items()):
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
                    tag = (f"{name} turno {cur.get('turn')} "
                           f"accion {cur.get('turnActionCount')}")
                    their = _their_deck_for(obs, our_deck, lists)
                    if their is None:
                        ungradeable.append(tag)
                        continue
                    boards.append({
                        "name": f"{tag} [rival: {their[0]}]",
                        "obs": obs,
                        "our_deck": list(our_deck),
                        "their_deck": their[1],
                        "recorded_list": True,
                        "with": c_with, "without": c_without,
                        "label_with": _describe(candidate, obs, c_with),
                        "label_without": _describe(base, obs, c_without),
                    })
    for tag in ungradeable:
        print(f"  NO GRADUABLE (ninguna lista de Alakazam cierra en 60): {tag}")
    return boards


def _fixture_board(candidate, base):
    """The record the rule was written from, and the list it was played with.

    The list is DETECTED: the fixture is a 14 August game and `records/` was
    re-harvested since, so neither `deck.csv` nor the pre-14-August list can be
    assumed. Whichever closes on sixty per seat under `determinize` is the one,
    and if both do the current list wins -- it is the game's own day.
    """
    import random

    from recorded_deck import read_list

    obs = json.loads(FIXTURE.read_text(encoding="utf-8"))["observation"]
    lists = _opponent_lists()
    candidates = [("deck.csv", sp.read_deck(str(_ROOT / "deck.csv"))),
                  ("lista del registro", list(read_list()))]
    chosen, their = None, None
    for label, deck in candidates:
        their = _their_deck_for(obs, deck, lists)
        if their is None:
            print(f"  fixture con {label}: NO cierra con ninguna lista rival")
            continue
        print(f"  fixture con {label}: cierra en sesenta por asiento "
              f"(rival: {their[0]})")
        chosen = (label, deck)
        break
    if chosen is None:
        return []

    c_with = list(candidate.agent(obs))
    c_without = list(base.agent(obs))
    if c_with == c_without:
        print("  AVISO: los dos brazos eligen lo mismo en el fixture; no hay "
              "tablero que graduar aqui")
        return []
    return [{
        "name": f"registro_003 paso 29 (fixture, {chosen[0]}, rival {their[0]})",
        "obs": obs,
        "our_deck": chosen[1],
        "their_deck": their[1],
        "recorded_list": chosen[0] != "deck.csv",
        "with": c_with, "without": c_without,
        "label_with": _describe(candidate, obs, c_with),
        "label_without": _describe(base, obs, c_without),
    }]


def batch(obs, our_deck, their_deck, choice, k, seed0, agent):
    """K rollouts of one option, RESETTING the agent's belief between them.

    `score_option` does not reset, and here it has to: the rollout policy is our
    own agent, whose card tracking persists across calls. Without the reset the
    second rollout of a batch starts with the belief the first one ended with
    and the batch measures a drift instead of an option.
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
    ap.add_argument("--only", choices=("fixture", "corpus"), default=None)
    args = ap.parse_args(argv)

    import local_engine
    local_engine.load()

    candidate, base = _arms()
    boards = []
    if args.only != "corpus":
        boards += _fixture_board(candidate, base)
    if args.only != "fixture":
        boards += _corpus_boards(candidate, base)
    if not boards:
        raise SystemExit("no hay tableros que graduar")

    print(f"\n{len(boards)} tableros, K={args.k} por lote, "
          f"politica = nuestro agente en los dos asientos\n")

    real, against, floorless, broken = 0, 0, 0, []
    try:
        for b in boards:
            their = b["their_deck"]
            # A board that dies mid-batch does not take the run with it: the
            # whole point of a night run is that the morning has a table.
            try:
                with_rule = batch(b["obs"], b["our_deck"], their, b["with"],
                                  args.k, 0, candidate)
                without = batch(b["obs"], b["our_deck"], their, b["without"],
                                args.k, 0, candidate)
                # The board's OWN noise floor: the same option, other seeds.
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
