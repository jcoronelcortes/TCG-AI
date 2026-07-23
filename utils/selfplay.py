"""Harness de self-play: partidas completas agente-vs-agente con el simulador.

Fase 3 de la arquitectura de mejora de estrategia: el gate que mide lo que
ningun test unitario puede medir — si un cambio de regla GANA MAS PARTIDAS.

Carga DOS instancias independientes de main.py (via importlib, cada una con
sus propios globals de tracking) y las enfrenta con cg.game
(battle_start/battle_select). El azar interno del simulador (barajas, monedas)
no es sembrable via API, asi que la varianza se maneja con N partidas y
ALTERNANCIA DE ASIENTOS (el candidato juega la mitad como jugador 0 y la
mitad como jugador 1).

Uso:
    python utils/selfplay.py --partidas 100
        # espejo: main.py vs main.py (sanidad: winrate ~50%)
    python utils/selfplay.py --partidas 200 --base HEAD~1
        # candidato (main.py del arbol de trabajo) vs baseline (git ref)
    python utils/selfplay.py --partidas 200 --base HEAD --candidato otra.py

Salida: marcador, winrate del candidato con intervalo de Wilson 95%, split
por asiento y errores/limites. Una partida donde un agente lanza excepcion o
devuelve una eleccion invalida cuenta como DERROTA de ese agente (forfeit).
"""

import argparse
import importlib.util
import math
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_TESTS = _ROOT / "tests"
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from golden_corpus import reset_agente  # espejo del reset de los tests

MAX_PASOS = 3000


def cargar_agente(ruta, nombre):
    """Carga una instancia independiente de un modulo de agente."""
    spec = importlib.util.spec_from_file_location(nombre, str(ruta))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cargar_agente_de_git(ref, nombre):
    """Carga la version de main.py de un ref de git (baseline)."""
    fuente = subprocess.run(
        ["git", "show", f"{ref}:main.py"], cwd=_ROOT, capture_output=True,
        text=True, check=True).stdout
    with tempfile.NamedTemporaryFile(
            "w", suffix=".py", prefix=f"main_{nombre}_",
            delete=False) as f:
        f.write(fuente)
        ruta = f.name
    return cargar_agente(ruta, nombre)


def leer_deck():
    csv = (_ROOT / "deck.csv").read_text().split("\n")
    return [int(csv[i]) for i in range(60)]


def jugar_partida(agente_p0, agente_p1, deck0=None, deck1=None,
                  max_pasos=MAX_PASOS):
    """Juega una partida completa. Devuelve un dict con el desenlace.

    result: 0/1 (ganador), "limite" (tope de pasos) o "error_pX" (el agente
    del asiento X lanzo excepcion o eligio una opcion invalida -> pierde).
    """
    from cg import game

    deck = leer_deck()
    deck0 = deck0 or deck
    deck1 = deck1 or deck
    reset_agente(agente_p0)
    reset_agente(agente_p1)

    obs, sd = game.battle_start(list(deck0), list(deck1))
    if obs is None:
        raise RuntimeError(
            f"battle_start fallo: errorPlayer={sd.errorPlayer} "
            f"errorType={sd.errorType}")
    agentes = {0: agente_p0, 1: agente_p1}
    pasos = 0
    primer_jugador = -1
    try:
        while obs["current"]["result"] == -1 and pasos < max_pasos:
            yi = obs["current"]["yourIndex"]
            if primer_jugador == -1:
                primer_jugador = obs["current"]["firstPlayer"]
            try:
                eleccion = agentes[yi].agent(obs)
                obs = game.battle_select(eleccion)
            except Exception:
                return {"result": f"error_p{yi}", "ganador": 1 - yi,
                        "pasos": pasos, "primer_jugador": primer_jugador}
            pasos += 1
        if obs["current"]["result"] == -1:
            return {"result": "limite", "ganador": None, "pasos": pasos,
                    "primer_jugador": primer_jugador}
        ganador = obs["current"]["result"]
        return {"result": ganador, "ganador": ganador, "pasos": pasos,
                "primer_jugador": obs["current"]["firstPlayer"]
                if primer_jugador == -1 else primer_jugador}
    finally:
        game.battle_finish()


def wilson_95(victorias, n):
    """Intervalo de Wilson al 95% para una proporcion."""
    if n == 0:
        return (0.0, 1.0)
    z = 1.959963984540054
    p = victorias / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    delta = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centro - delta), min(1.0, centro + delta))


def torneo(candidato, base, partidas, progreso=None):
    """Enfrenta candidato vs base alternando asientos. Devuelve stats."""
    stats = {
        "partidas": partidas, "candidato": 0, "base": 0, "limites": 0,
        "errores_candidato": 0, "errores_base": 0,
        "cand_j0": [0, 0], "cand_j1": [0, 0],  # [victorias, jugadas]
        "cand_primero": [0, 0], "cand_segundo": [0, 0],
        "pasos_totales": 0,
    }
    for i in range(partidas):
        asiento_cand = i % 2
        p0, p1 = ((candidato, base) if asiento_cand == 0
                  else (base, candidato))
        r = jugar_partida(p0, p1)
        stats["pasos_totales"] += r["pasos"]
        if isinstance(r["result"], str) and r["result"].startswith("error"):
            asiento_err = int(r["result"][-1])
            if asiento_err == asiento_cand:
                stats["errores_candidato"] += 1
            else:
                stats["errores_base"] += 1
        if r["ganador"] is None:
            stats["limites"] += 1
        else:
            gano_cand = (r["ganador"] == asiento_cand)
            stats["candidato" if gano_cand else "base"] += 1
            seat = stats["cand_j0"] if asiento_cand == 0 else stats["cand_j1"]
            seat[1] += 1
            seat[0] += int(gano_cand)
            if r["primer_jugador"] == asiento_cand:
                stats["cand_primero"][1] += 1
                stats["cand_primero"][0] += int(gano_cand)
            elif r["primer_jugador"] == 1 - asiento_cand:
                stats["cand_segundo"][1] += 1
                stats["cand_segundo"][0] += int(gano_cand)
        if progreso and (i + 1) % progreso == 0:
            print(f"  ... {i + 1}/{partidas} "
                  f"({stats['candidato']}-{stats['base']})", flush=True)
    return stats


def _pct(v, n):
    return f"{100 * v / n:.1f}%" if n else "n/a"


def informe(stats, etiqueta_cand, etiqueta_base):
    dec = stats["candidato"] + stats["base"]
    lo, hi = wilson_95(stats["candidato"], dec) if dec else (0, 1)
    lineas = [
        f"Self-play: candidato={etiqueta_cand}  vs  base={etiqueta_base}",
        f"Partidas: {stats['partidas']}  (decididas {dec}, "
        f"limite {stats['limites']})",
        f"Marcador: candidato {stats['candidato']} - {stats['base']} base",
        f"Winrate candidato: {_pct(stats['candidato'], dec)} "
        f"[IC95 {100 * lo:.1f}%-{100 * hi:.1f}%]",
        f"  como J0: {_pct(*stats['cand_j0'])} "
        f"({stats['cand_j0'][0]}/{stats['cand_j0'][1]})   "
        f"como J1: {_pct(*stats['cand_j1'])} "
        f"({stats['cand_j1'][0]}/{stats['cand_j1'][1]})",
        f"  saliendo primero: {_pct(*stats['cand_primero'])} "
        f"({stats['cand_primero'][0]}/{stats['cand_primero'][1]})   "
        f"segundo: {_pct(*stats['cand_segundo'])} "
        f"({stats['cand_segundo'][0]}/{stats['cand_segundo'][1]})",
        f"Errores (forfeit): candidato {stats['errores_candidato']}, "
        f"base {stats['errores_base']}",
        f"Pasos totales: {stats['pasos_totales']}",
    ]
    return "\n".join(lineas)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--partidas", type=int, default=100)
    ap.add_argument("--base", default=None,
                    help="ref de git para el baseline (p.ej. HEAD~1); "
                         "sin --base: espejo main.py vs main.py")
    ap.add_argument("--candidato", default="main.py",
                    help="ruta del agente candidato (default: main.py)")
    ap.add_argument("--progreso", type=int, default=20,
                    help="imprime marcador cada N partidas (0 = nunca)")
    args = ap.parse_args(argv)

    ruta_cand = _ROOT / args.candidato
    candidato = cargar_agente(ruta_cand, "agente_candidato")
    if args.base:
        base = cargar_agente_de_git(args.base, "agente_base")
        etiqueta_base = f"{args.base} (git)"
    else:
        base = cargar_agente(ruta_cand, "agente_base_espejo")
        etiqueta_base = f"{args.candidato} (espejo)"

    stats = torneo(candidato, base, args.partidas,
                   progreso=args.progreso or None)
    print(informe(stats, args.candidato, etiqueta_base))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
