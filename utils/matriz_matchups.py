"""Matriz de matchups: winrate del agente contra CADA mazo de deck/rivales/.

Fase 8 de la arquitectura de mejora de estrategia. Recorre todos los CSV de
deck/rivales/ (los arquetipos sinteticos de utils/construir_mazos_meta.py mas
los cosechados) y juega N partidas contra el bot generico con cada uno,
alternando asientos. Imprime la tabla ordenada del matchup mas debil al mas
fuerte, con el intervalo de Wilson 95% y los forfeits.

Con --base <ref-git> imprime ademas el DELTA por matchup contra esa version:
detecta cuando una regla nueva mejora un matchup degradando otro (la clase de
colision Cubchoo/Cornerstone). OJO con el ruido: con 200 partidas el delta
oscila +-7 puntos; solo los deltas grandes y consistentes son senal.

Uso:
    python utils/matriz_matchups.py --partidas 200
    python utils/matriz_matchups.py --partidas 400 --base HEAD~1
    python utils/matriz_matchups.py --solo dragapult,hops
"""

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp
from bot_rival import BotRival


def medir(agente, partidas, rutas):
    bot = BotRival()
    filas = []
    for ruta in rutas:
        deck_rival = sp.leer_deck(ruta)
        stats = sp.torneo(agente, bot, partidas, deck_base=deck_rival)
        dec = stats["candidato"] + stats["base"]
        wr = stats["candidato"] / dec if dec else 0.0
        lo, hi = sp.wilson_95(stats["candidato"], dec)
        filas.append({
            "mazo": ruta.stem, "wr": wr, "lo": lo, "hi": hi,
            "decididas": dec, "limites": stats["limites"],
            "forfeits": stats["errores_candidato"],
            "forfeits_bot": stats["errores_base"],
        })
        print(f"  {ruta.stem}: {100 * wr:.1f}% "
              f"[{100 * lo:.1f}-{100 * hi:.1f}] "
              f"(forfeits nuestros {stats['errores_candidato']})", flush=True)
    return filas


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--partidas", type=int, default=200,
                    help="partidas por matchup (default 200)")
    ap.add_argument("--candidato", default="main.py")
    ap.add_argument("--base", default=None,
                    help="ref de git: imprime el delta por matchup")
    ap.add_argument("--solo", default=None,
                    help="lista de mazos separada por comas (default: todos)")
    ap.add_argument("--rivales", default=str(_ROOT / "deck" / "rivales"))
    args = ap.parse_args(argv)

    rutas = sorted(Path(args.rivales).glob("*.csv"))
    if args.solo:
        quiere = {s.strip() for s in args.solo.split(",")}
        rutas = [r for r in rutas if r.stem in quiere]
    if not rutas:
        print("sin mazos rivales que medir")
        return 1

    agente = sp.cargar_agente(_ROOT / args.candidato, "agente_matriz")
    print(f"candidato={args.candidato}, {args.partidas} partidas por matchup")
    filas = medir(agente, args.partidas, rutas)

    base_por_mazo = {}
    if args.base:
        base = sp.cargar_agente_de_git(args.base, "agente_matriz_base")
        print(f"\nbaseline={args.base}")
        base_por_mazo = {f["mazo"]: f for f in
                         medir(base, args.partidas, rutas)}

    print("\n=== MATRIZ DE MATCHUPS (peor -> mejor) ===")
    ancho = max(len(f["mazo"]) for f in filas)
    for f in sorted(filas, key=lambda x: x["wr"]):
        linea = (f"{f['mazo']:<{ancho}}  {100 * f['wr']:5.1f}%  "
                 f"[{100 * f['lo']:.1f}-{100 * f['hi']:.1f}]"
                 f"  n={f['decididas']}")
        if f["forfeits"]:
            linea += f"  FORFEITS={f['forfeits']}"
        if f["mazo"] in base_por_mazo:
            delta = f["wr"] - base_por_mazo[f["mazo"]]["wr"]
            linea += f"  delta={100 * delta:+.1f}"
        print(linea)
    peor = min(filas, key=lambda x: x["wr"])
    print(f"\nMatchup mas debil: {peor['mazo']} ({100 * peor['wr']:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
