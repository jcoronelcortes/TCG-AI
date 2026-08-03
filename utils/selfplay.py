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
    python utils/selfplay.py --partidas 200 --rival deck/rivales/crustle.csv
        # candidato vs BOT generico pilotando un mazo rival (matchup)
    python utils/selfplay.py --partidas 200 --rival ... --base HEAD~1
        # DIFERENCIAL de matchup: candidato-vs-bot y base-vs-bot; el delta
        # entre ambos winrates es la senal (el nivel absoluto del bot no)

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
    """Carga una instancia independiente de un modulo de agente.

    INDEPENDIENTE INCLUYE SU PROPIO ARBOL `ptcg/`. Desde la Ola 3 del refactor el
    estado que persiste entre turnos vive en `ptcg.estado.agente.ESTADO`, no en
    los globals de main.py. Si se deja `ptcg` en sys.modules, las dos instancias
    importan el MISMO singleton y se pisan el estado: el enfrentamiento deja de
    medir nada y sombra.py reporta flips fantasma (58 en 20 partidas la primera
    vez que paso). Vaciando `ptcg*` antes de cada carga, cada main.py construye
    su propio arbol; los modulos ya cargados conservan sus referencias directas,
    asi que la instancia anterior sigue funcionando con el suyo.

    `cg` NO se toca: `cg/sim.py` llama a `GameInitialize()` al importarse y
    hacerlo dos veces ABORTA el interprete.
    """
    def _ramas_ptcg():
        return [k for k in sys.modules if k == "ptcg" or k.startswith("ptcg.")]

    previos = {k: sys.modules[k] for k in _ramas_ptcg()}
    for k in previos:
        del sys.modules[k]
    try:
        spec = importlib.util.spec_from_file_location(nombre, str(ruta))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        # Y se DEVUELVE el arbol ambiental a sys.modules. La instancia recien
        # creada ya guarda referencias directas al suyo, asi que conserva su
        # propio ESTADO; pero si se dejara el proceso sin el arbol original,
        # cualquier `from ptcg... import` posterior crearia una SEGUNDA copia
        # del paquete -- y quien parchease ahi no afectaria al agente que ya
        # estaba cargado (paso: contaminaba tests/test_xerosic_*).
        for k in _ramas_ptcg():
            del sys.modules[k]
        sys.modules.update(previos)
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


def leer_deck(ruta=None):
    csv = Path(ruta or _ROOT / "deck.csv").read_text().split("\n")
    return [int(csv[i]) for i in range(60)]


def _reset_si_aplica(mod):
    # El bot rival no tiene tracking; solo las instancias de main.py.
    if hasattr(mod, "_init_cartas_tracking"):
        reset_agente(mod)


def _premios_restantes(obs):
    """Premios que le QUEDAN a cada asiento, o None si no se pueden leer."""
    try:
        jugadores = obs["current"]["players"]
        return [len(jugadores[i].get("prize") or []) for i in (0, 1)]
    except (KeyError, IndexError, TypeError):
        return None


def _premios_tomados(pico, final):
    """Premios TOMADOS por cada asiento = lo que ha bajado su PROPIO monton.

    Cada jugador roba de SU monton al noquear, asi que el contador de premios
    de un asiento mide lo que ha cobrado EL, no lo que le han cobrado.
    Verificado sobre el simulador: en 20 de 25 partidas el ganador termina con
    su propio monton a 0 y en ninguna con el del rival a 0 (las otras 5 se
    ganaron por bench-out o deckout, sin agotar premios).

    `pico` es el MAXIMO de premios visto durante la partida, no la lectura de
    `battle_start`: ahi el reparto aun no ha ocurrido y los dos montones valen
    0, con lo que el diferencial salia identicamente 0 en TODOS los matchups.
    Como el monton solo puede bajar, su pico ES el reparto inicial, y de paso
    no hay que fijar el 6 a fuego.

    Devuelve [None, None] si no se pudo leer, para que el agregado sepa
    distinguir "0 premios" de "no medido".
    """
    if not pico or not final or max(pico) <= 0:
        return [None, None]
    return [max(0, pico[i] - final[i]) for i in (0, 1)]


def jugar_partida(agente_p0, agente_p1, deck0=None, deck1=None,
                  max_pasos=MAX_PASOS):
    """Juega una partida completa. Devuelve un dict con el desenlace.

    result: 0/1 (ganador), "limite" (tope de pasos) o "error_pX" (el agente
    del asiento X lanzo excepcion o eligio una opcion invalida -> pierde).

    `premios_tomados`: [p0, p1], los premios que cobro cada asiento. Es la
    metrica de RESOLUCION del harness: el winrate contra el bot generico esta
    saturado (>93% ponderado) y no puede arbitrar un cambio, pero los premios
    si graduan -- contra Marnie las tres partidas de referencia se perdieron
    POR UN PREMIO, y esa magnitud desaparece al colapsarla en gano/perdio.
    Ojo: una partida se puede ganar sin cobrar los 6 (bench-out, deckout), asi
    que el diferencial de premios NO es un winrate disfrazado: mide otra cosa.
    """
    from cg import game

    deck = leer_deck()
    deck0 = deck0 or deck
    deck1 = deck1 or deck
    _reset_si_aplica(agente_p0)
    _reset_si_aplica(agente_p1)

    obs, sd = game.battle_start(list(deck0), list(deck1))
    if obs is None:
        raise RuntimeError(
            f"battle_start fallo: errorPlayer={sd.errorPlayer} "
            f"errorType={sd.errorType}")
    # Pico de premios por asiento. En `battle_start` los montones aun valen 0
    # (no se han repartido), asi que el inicial se descubre sobre la marcha.
    premios_pico = [0, 0]

    def _mirar_premios():
        actual = _premios_restantes(obs)
        if actual:
            for i in (0, 1):
                if actual[i] > premios_pico[i]:
                    premios_pico[i] = actual[i]
        return actual

    _mirar_premios()
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
                        "pasos": pasos, "primer_jugador": primer_jugador,
                        "premios_tomados": _premios_tomados(
                            premios_pico, _premios_restantes(obs))}
            _mirar_premios()
            pasos += 1
        premios = _premios_tomados(premios_pico, _premios_restantes(obs))
        if obs["current"]["result"] == -1:
            return {"result": "limite", "ganador": None, "pasos": pasos,
                    "primer_jugador": primer_jugador,
                    "premios_tomados": premios}
        ganador = obs["current"]["result"]
        return {"result": ganador, "ganador": ganador, "pasos": pasos,
                "primer_jugador": obs["current"]["firstPlayer"]
                if primer_jugador == -1 else primer_jugador,
                "premios_tomados": premios}
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


def torneo(candidato, base, partidas, progreso=None,
           deck_candidato=None, deck_base=None):
    """Enfrenta candidato vs base alternando asientos. Devuelve stats.

    deck_candidato/deck_base: listas de 60 ids; por defecto, deck.csv.
    Cada mazo viaja con su agente al cambiar de asiento.
    """
    stats = {
        "partidas": partidas, "candidato": 0, "base": 0, "limites": 0,
        "errores_candidato": 0, "errores_base": 0,
        "cand_j0": [0, 0], "cand_j1": [0, 0],  # [victorias, jugadas]
        "cand_primero": [0, 0], "cand_segundo": [0, 0],
        "pasos_totales": 0,
        # Metrica de RESOLUCION: el winrate esta saturado contra el bot, los
        # premios no. Se acumulan por AGENTE (no por asiento), porque el
        # candidato alterna de asiento en cada partida.
        "premios_candidato": 0, "premios_base": 0, "partidas_con_premios": 0,
    }
    for i in range(partidas):
        asiento_cand = i % 2
        if asiento_cand == 0:
            p0, p1, d0, d1 = candidato, base, deck_candidato, deck_base
        else:
            p0, p1, d0, d1 = base, candidato, deck_base, deck_candidato
        r = jugar_partida(p0, p1, deck0=d0, deck1=d1)
        stats["pasos_totales"] += r["pasos"]
        premios = r.get("premios_tomados") or [None, None]
        if premios[0] is not None and premios[1] is not None:
            stats["premios_candidato"] += premios[asiento_cand]
            stats["premios_base"] += premios[1 - asiento_cand]
            stats["partidas_con_premios"] += 1
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


def premios_por_partida(stats):
    """(premios/partida del candidato, de la base, diferencial). None si no hay."""
    n = stats.get("partidas_con_premios") or 0
    if not n:
        return (None, None, None)
    pc = stats["premios_candidato"] / n
    pb = stats["premios_base"] / n
    return (pc, pb, pc - pb)


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
    pc, pb, dif = premios_por_partida(stats)
    if pc is not None:
        lineas.append(
            f"Premios/partida: candidato {pc:.2f} - {pb:.2f} base  "
            f"(diferencial {dif:+.2f})")
        lineas.append(
            "  el winrate se satura contra el bot; el diferencial de premios "
            "gradua y detecta cambios que el marcador no ve")
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
    ap.add_argument("--rival", default=None,
                    help="csv de mazo rival: el oponente pasa a ser el BOT "
                         "generico pilotando ese mazo (modo matchup)")
    args = ap.parse_args(argv)

    ruta_cand = _ROOT / args.candidato
    candidato = cargar_agente(ruta_cand, "agente_candidato")

    if args.rival:
        from bot_rival import BotRival
        deck_rival = leer_deck(_ROOT / args.rival)
        bot = BotRival()
        stats = torneo(candidato, bot, args.partidas,
                       progreso=args.progreso or None,
                       deck_base=deck_rival)
        print(informe(stats, args.candidato, f"bot+{args.rival}"))
        if args.base:
            base = cargar_agente_de_git(args.base, "agente_base")
            stats_base = torneo(base, bot, args.partidas,
                                progreso=args.progreso or None,
                                deck_base=deck_rival)
            print()
            print(informe(stats_base, f"{args.base} (git)",
                          f"bot+{args.rival}"))
            dec_c = stats["candidato"] + stats["base"]
            dec_b = stats_base["candidato"] + stats_base["base"]
            wr_c = stats["candidato"] / dec_c if dec_c else 0
            wr_b = stats_base["candidato"] / dec_b if dec_b else 0
            print(f"\nDELTA de matchup (candidato - {args.base}): "
                  f"{100 * (wr_c - wr_b):+.1f} puntos "
                  f"({100 * wr_c:.1f}% vs {100 * wr_b:.1f}%)")
        return 0

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
