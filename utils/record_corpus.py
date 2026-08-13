"""Generates the records that feed the golden corpus (tests/golden_corpus.py).

WHY IT EXISTS
  The corpus replays recorded games and compares OUR decisions against a
  snapshot: any change to main.py that flips a historical decision fails
  with the exact diff. But its source data (`records/registro_*.json`) are
  replays of Kaggle episodes -- git-ignored and transient -- so as
  soon as they are cleaned up the corpus goes BLIND and its test comes out as a `skip`. It was
  like that throughout the whole wave refactor.

  This script removes that dependency: it plays games with the local simulator and
  records them in the same format, so the corpus can be regenerated whenever
  it is needed without waiting to download replays.

WHAT IT PLAYS AGAINST
  Against the REAL leaderboard decks (`deck/real_opponents/`), piloted by
  the generic bot -- not against ourselves. A mirror corpus would measure a
  much narrower distribution of boards, and it would also be redundant with
  `utils/shadow.py`, which already plays self-play. What the corpus contributes is a
  FIXED set of concrete situations, with its snapshot, that survives without
  needing to keep a copy of the previous version.

FORMAT
  The same as the replays: `{"steps": [[{"status", "observation"}], ...]}`. The
  local engine gives one observation per step (that of the player who acts), so
  each step carries a single item; `replay_record` filters by ACTIVE status,
  the presence of `select` and `yourIndex`, and that fits just the same.

Usage:
    python utils/record_corpus.py                    # 12 games, 12 opponents
    python utils/record_corpus.py --games 20
    python utils/record_corpus.py --opponents deck/real_opponents --seed 3
"""

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402

RECORDS = _ROOT / "records"
MAX_STEPS = 3000


def _record_game(agent_state, bot, deck_nuestro, opponent_deck, our_seat):
    """Plays a game and returns its `steps` in replay format.

    EACH STEP ALSO CARRIES THE ANSWER TO ITS OWN MENU, under `chosen`. It is a
    different key from the replays' `action` ON PURPOSE, because it holds a
    different thing: a Kaggle replay stores under `action` the move that
    PRODUCED that observation -- the answer to the PREVIOUS menu -- and reading
    the two conventions as one is a bug this project has already paid for
    (`utils/log_replay.py`, which compared every answer against the wrong step
    until August 2026). Naming the key after what it means is what stops the
    next reader from having to know which file they are holding.

    What it buys: any census that has to say WHAT THE AGENT DID -- and not
    merely what the board looked like -- can read it off the record instead of
    inferring it from the engine's logs, which is guesswork the moment a bundle
    is thinned (`utils/sterile_turn_census.py`).
    """
    from cg import game

    sp._reset_si_aplica(agent_state)
    sp._reset_si_aplica(bot)
    d0, d1 = ((deck_nuestro, opponent_deck) if our_seat == 0
              else (opponent_deck, deck_nuestro))
    obs, sd = game.battle_start(list(d0), list(d1))
    if obs is None:
        raise RuntimeError(f"battle_start fallo: errorType={sd.errorType}")

    agentes = {our_seat: agent_state, 1 - our_seat: bot}
    steps, n_steps = [], 0
    while obs["current"]["result"] == -1 and n_steps < MAX_STEPS:
        yi = obs["current"]["yourIndex"]
        # It is ALWAYS recorded, including the bot's turns: the corpus filters by
        # seat when replaying, and saving the whole stream makes it possible to reconstruct
        # the context of a decision when reviewing a flip.
        paso = {"status": "ACTIVE", "observation": json.loads(json.dumps(obs))}
        steps.append([paso])
        try:
            eleccion = agentes[yi].agent(obs)
            paso["chosen"] = list(eleccion) if eleccion is not None else None
            obs = game.battle_select(eleccion)
        except Exception as e:
            return steps, f"error_p{yi}: {type(e).__name__}: {e}"
        n_steps += 1
    return steps, obs["current"]["result"]


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=12)
    ap.add_argument("--opponents", default=str(_ROOT / "deck" / "real_opponents"))
    ap.add_argument("--seed", type=int, default=0,
                    help="which opponent to start dealing from (rotates the selection)")
    ap.add_argument("--main", default="main.py")
    ap.add_argument("--out", default=str(RECORDS),
                    help="destination folder (default: records/). It DELETES the "
                         "registro_*.json already in it, so point it elsewhere to "
                         "keep the hand-split replays")
    args = ap.parse_args()

    opponents = sorted(Path(args.opponents).glob("*.csv"))
    if not opponents:
        raise SystemExit(f"no hay mazos rivales en {args.opponents}")

    # A different opponent per game, spread along the list so as not to
    # pick twelve variants of the same archetype.
    step = max(1, len(opponents) // args.games)
    chosen_ones = [opponents[(args.seed + i * step) % len(opponents)]
                for i in range(args.games)]

    agent_state = sp.load_agent(_ROOT / args.main, "corpus_agente")
    from opponent_bot import OpponentBot
    bot = OpponentBot()
    deck_nuestro = sp.read_deck()

    destino = Path(args.out)
    destino.mkdir(parents=True, exist_ok=True)
    for viejo in destino.glob("registro_*.json"):
        viejo.unlink()

    total_steps = 0
    for i, opponent in enumerate(chosen_ones):
        # Alternating seats: our decisions are not the same going
        # first as going second, and the corpus must cover both.
        seat = i % 2
        steps, result = _record_game(
            agent_state, bot, deck_nuestro, sp.read_deck(opponent), seat)
        name = f"registro_{i:03d}_{opponent.stem}_asiento{seat}.json"
        (destino / name).write_text(
            json.dumps({"steps": steps}, ensure_ascii=False), encoding="utf-8")
        total_steps += len(steps)
        print(f"  {name}  {len(steps):4d} pasos  resultado={result}")

    print(f"\n{len(chosen_ones)} registros, {total_steps} pasos en {destino}")
    print("Ahora: python tests/golden_corpus.py --update")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
