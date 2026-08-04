"""Genera los registros que alimentan el corpus dorado (tests/golden_corpus.py).

POR QUE EXISTE
  El corpus reproduce partidas grabadas y compara NUESTRAS decisiones contra un
  snapshot: cualquier cambio de main.py que voltee una decision historica falla
  con el diff exacto. Pero sus datos fuente (`registros/registro_*.json`) son
  replays de episodios de Kaggle -- git-ignored y transitorios --, asi que en
  cuanto se limpian el corpus queda CIEGO y su test sale como `skip`. Estuvo asi
  durante todo el refactor por olas.

  Este script quita esa dependencia: juega partidas con el simulador local y las
  graba en el mismo formato, de modo que el corpus se puede regenerar cuando
  haga falta sin esperar a bajar replays.

CONTRA QUE SE JUEGA
  Contra los mazos REALES del leaderboard (`deck/rivales_reales/`), pilotados por
  el bot generico -- no contra nosotros mismos. Un corpus de espejo mediria una
  distribucion de tableros mucho mas estrecha, y ademas seria redundante con
  `utils/sombra.py`, que ya juega self-play. Lo que aporta el corpus es un
  conjunto FIJO de situaciones concretas, con su snapshot, que sobrevive sin
  necesidad de conservar una copia de la version anterior.

FORMATO
  El mismo de los replays: `{"steps": [[{"status", "observation"}], ...]}`. El
  motor local da una observacion por paso (la del jugador que actua), asi que
  cada step lleva un solo item; `reproducir_registro` filtra por status ACTIVE,
  presencia de `select` y `yourIndex`, y eso encaja igual.

Uso:
    python utils/grabar_corpus.py                    # 12 partidas, 12 rivales
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
    """Juega una partida y devuelve sus `steps` en formato de replay."""
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
        # Se graba SIEMPRE, tambien los turnos del bot: el corpus filtra por
        # asiento al reproducir, y guardar el flujo entero permite reconstruir
        # el contexto de una decision al revisar un flip.
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

    # Un rival distinto por partida, repartidos a lo largo de la lista para no
    # coger doce variantes del mismo arquetipo.
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
        # Alternando asiento: nuestras decisiones no son las mismas yendo
        # primero que segundo, y el corpus debe cubrir las dos.
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
