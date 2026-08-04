"""Generates the records that feed the golden corpus (tests/golden_corpus.py).

WHY IT EXISTS
  The corpus replays recorded games and compares OUR decisions against a
  snapshot: any change to main.py that flips a historical decision fails
  with the exact diff. But its source data (`registros/registro_*.json`) are
  replays of Kaggle episodes -- git-ignored and transient -- so as
  soon as they are cleaned up the corpus goes BLIND and its test comes out as a `skip`. It was
  like that throughout the whole wave refactor.

  This script removes that dependency: it plays games with the local simulator and
  records them in the same format, so the corpus can be regenerated whenever
  it is needed without waiting to download replays.

WHAT IT PLAYS AGAINST
  Against the REAL leaderboard decks (`deck/rivales_reales/`), piloted by
  the generic bot -- not against ourselves. A mirror corpus would measure a
  much narrower distribution of boards, and it would also be redundant with
  `utils/sombra.py`, which already plays self-play. What the corpus contributes is a
  FIXED set of concrete situations, with its snapshot, that survives without
  needing to keep a copy of the previous version.

FORMAT
  The same as the replays: `{"steps": [[{"status", "observation"}], ...]}`. The
  local engine gives one observation per step (that of the player who acts), so
  each step carries a single item; `reproducir_registro` filters by ACTIVE status,
  the presence of `select` and `yourIndex`, and that fits just the same.

Usage:
    python utils/grabar_corpus.py                    # 12 games, 12 opponents
    python utils/grabar_corpus.py --partidas 20
    python utils/grabar_corpus.py --rivales deck/rivales_reales --semilla 3
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

REGISTROS = _ROOT / "registros"
MAX_PASOS = 3000


def _grabar_partida(agente, bot, deck_nuestro, deck_rival, nuestro_asiento):
    """Plays a game and returns its `steps` in replay format."""
    from cg import game

    sp._reset_si_aplica(agente)
    sp._reset_si_aplica(bot)
    d0, d1 = ((deck_nuestro, deck_rival) if nuestro_asiento == 0
              else (deck_rival, deck_nuestro))
    obs, sd = game.battle_start(list(d0), list(d1))
    if obs is None:
        raise RuntimeError(f"battle_start fallo: errorType={sd.errorType}")

    agentes = {nuestro_asiento: agente, 1 - nuestro_asiento: bot}
    steps, pasos = [], 0
    while obs["current"]["result"] == -1 and pasos < MAX_PASOS:
        yi = obs["current"]["yourIndex"]
        # It is ALWAYS recorded, including the bot's turns: the corpus filters by
        # seat when replaying, and saving the whole stream makes it possible to reconstruct
        # the context of a decision when reviewing a flip.
        steps.append([{"status": "ACTIVE", "observation": json.loads(json.dumps(obs))}])
        try:
            obs = game.battle_select(agentes[yi].agent(obs))
        except Exception as e:
            return steps, f"error_p{yi}: {type(e).__name__}: {e}"
        pasos += 1
    return steps, obs["current"]["result"]


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--partidas", type=int, default=12)
    ap.add_argument("--rivales", default=str(_ROOT / "deck" / "rivales_reales"))
    ap.add_argument("--semilla", type=int, default=0,
                    help="desde que rival empezar a repartir (rota la seleccion)")
    ap.add_argument("--main", default="main.py")
    args = ap.parse_args()

    rivales = sorted(Path(args.rivales).glob("*.csv"))
    if not rivales:
        raise SystemExit(f"no hay mazos rivales en {args.rivales}")

    # A different opponent per game, spread along the list so as not to
    # pick twelve variants of the same archetype.
    paso = max(1, len(rivales) // args.partidas)
    elegidos = [rivales[(args.semilla + i * paso) % len(rivales)]
                for i in range(args.partidas)]

    agente = sp.cargar_agente(_ROOT / args.main, "corpus_agente")
    from bot_rival import BotRival
    bot = BotRival()
    deck_nuestro = sp.leer_deck()

    REGISTROS.mkdir(exist_ok=True)
    for viejo in REGISTROS.glob("registro_*.json"):
        viejo.unlink()

    total_pasos = 0
    for i, rival in enumerate(elegidos):
        # Alternating seats: our decisions are not the same going
        # first as going second, and the corpus must cover both.
        asiento = i % 2
        steps, resultado = _grabar_partida(
            agente, bot, deck_nuestro, sp.leer_deck(rival), asiento)
        nombre = f"registro_{i:03d}_{rival.stem}_asiento{asiento}.json"
        (REGISTROS / nombre).write_text(
            json.dumps({"steps": steps}, ensure_ascii=False), encoding="utf-8")
        total_pasos += len(steps)
        print(f"  {nombre}  {len(steps):4d} pasos  resultado={resultado}")

    print(f"\n{len(elegidos)} registros, {total_pasos} pasos en {REGISTROS}")
    print("Ahora: python tests/golden_corpus.py --actualizar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
