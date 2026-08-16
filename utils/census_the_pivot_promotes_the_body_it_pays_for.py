"""Cuantas veces el pivote vs Alakazam paga una retirada que la promocion no
cumple -- medido sobre las partidas reales, no sobre un tablero.

LA PREGUNTA. `_alakazam_pivot_1prize` retira nuestro ex "para subir un cuerpo de
UN premio y entregar 1 en vez de 2". La promocion es otro menu y no conoce esa
frase (`ptcg/turn/options/card.py` solo levanta por su nombre al Meganium en
este matchup, y al Tapu Bulu que noquea, universal). El interruptor
`THE_PIVOT_NEEDS_A_CORPSE_THEY_CAN_TAKE` (main.py) veta el pivote cuando el
asiento se lo va a llevar otro. Esto cuenta CUANTOS tableros toca -- la
exposicion -- antes de discutir si el gate puede resolverla.

QUE MIDE, exactamente: cada decision NUESTRA de una partida contra la linea de
Alakazam se contesta dos veces, con el interruptor encendido y apagado, sobre
DOS copias del arbol (`selfplay.load_agent`, igual que los gates: un arbol
compartido mediria exactamente cero). Se cuentan las que cambian, y de cada una
se imprime la partida, el paso y las dos respuestas.

    python utils/census_the_pivot_promotes_the_body_it_pays_for.py
    python utils/census_the_pivot_promotes_the_body_it_pays_for.py --games 40
    python utils/census_the_pivot_promotes_the_body_it_pays_for.py --all-matchups

Por defecto solo recorre las partidas donde la linea Abra/Kadabra/Alakazam
aparece en su mesa: es el unico matchup donde la regla puede hablar, y
`--all-matchups` esta para comprobar precisamente eso (la fuga debe ser 0).
"""

import argparse
import glob
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "utils"), str(_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import selfplay as sp  # noqa: E402
from golden_corpus import reset_agent  # noqa: E402

FLAGS = ("THE_PIVOT_NEEDS_A_CORPSE_THEY_CAN_TAKE",     # el retiro: ¿hay cadaver?
         "THE_PIVOT_PROMOTES_THE_BODY_IT_PAYS_FOR")    # el asiento: ¿lo cumple?
ALAKAZAM_LINE = (741, 742, 743)
US = "Jose Coronel"


def _seat(record):
    names = (record.get("info") or {}).get("TeamNames") or []
    return names.index(US) if US in names else None


def _their_line(record, seat):
    """Los ids que pasaron por SU mesa en toda la partida."""
    ids = set()
    for step in record.get("steps") or []:
        for item in step:
            cur = ((item.get("observation") or {}).get("current")) or {}
            players = cur.get("players") or []
            if len(players) < 2 or not isinstance(players[1 - seat], dict):
                continue
            theirs = players[1 - seat]
            for body in (theirs.get("active") or []) + (theirs.get("bench") or []):
                if isinstance(body, dict):
                    ids.add(body.get("id"))
    return ids


def _decisions(module, record, seat):
    """Nuestras respuestas, en orden, con el paso en el que se dieron."""
    reset_agent(module)
    out = []
    for index, step in enumerate(record.get("steps") or []):
        for item in step:
            obs = item.get("observation")
            cur = (obs or {}).get("current") or {}
            if (item.get("status") != "ACTIVE" or not isinstance(obs, dict)
                    or not obs.get("select") or cur.get("yourIndex") != seat):
                continue
            out.append((index, module.agent(obs)))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=0,
                        help="tope de partidas (0 = todas las que apliquen)")
    parser.add_argument("--all-matchups", action="store_true",
                        help="no filtrar por la linea de Alakazam")
    parser.add_argument("--outside", action="store_true",
                        help="SOLO las partidas donde esa linea no aparece: es "
                             "lo que mide la fuga, y `--all-matchups` no, "
                             "porque incluye el matchup propio")
    parser.add_argument("--replays", default=str(_ROOT / "log" / "real_games"),
                        help="carpeta de replays")
    parser.add_argument("--only", choices=FLAGS,
                        help="medir UNA de las dos mitades (la otra queda como "
                             "viene en el fichero): las dos son una sola frase "
                             "pero no son un solo mecanismo")
    args = parser.parse_args()

    on = sp.load_agent(_ROOT / "main.py", "pivot_on")
    off = sp.load_agent(_ROOT / "main.py", "pivot_off")
    for flag in (FLAGS if args.only is None else (args.only,)):
        setattr(on, flag, True)
        setattr(off, flag, False)

    files = sorted(glob.glob(str(Path(args.replays) / "*.json")))
    jugadas = tocadas = decisiones = cambios = 0
    for path in files:
        if args.games and jugadas >= args.games:
            break
        try:
            with open(path, encoding="utf-8") as handle:
                record = json.load(handle)
        except (OSError, ValueError):
            continue
        seat = _seat(record)
        if seat is None:
            continue
        _alakazam = bool(_their_line(record, seat) & set(ALAKAZAM_LINE))
        if args.outside:
            if _alakazam:
                continue
        elif not args.all_matchups:
            if not _alakazam:
                continue
        jugadas += 1
        con = _decisions(on, record, seat)
        sin = _decisions(off, record, seat)
        decisiones += len(con)
        flips = [(paso, a, b) for (paso, a), (_, b) in zip(con, sin) if a != b]
        if flips:
            tocadas += 1
            cambios += len(flips)
            for paso, a, b in flips:
                print(f"{Path(path).name} paso {paso}: con={a} sin={b}")

    print(f"\npartidas leidas: {jugadas}   con algun cambio: {tocadas}")
    print(f"decisiones nuestras: {decisiones}   cambiadas: {cambios}"
          + (f"   ({cambios / decisiones:.4f}/decision)" if decisiones else ""))
    print(f"matchup: {'FUERA de Alakazam' if args.outside else ('TODOS' if args.all_matchups else 'linea de Alakazam')}"
          f"   medido: {args.only or ' + '.join(FLAGS)}")


if __name__ == "__main__":
    main()
