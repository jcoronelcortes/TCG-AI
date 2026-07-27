"""Reconstruye un mazo rival de 60 cartas a partir de los registros locales.

Escanea las zonas VISIBLES del rival en registros/*.json (campo, descarte,
estadio; las copias se cuentan por serial, que es unico por carta de la
partida) y AMPLIFICA por regla la lista parcial hasta 60 cartas:

  - cada Pokemon visto        -> 4 copias
  - cada Trainer visto        -> 4 copias (Item/Tool/Supporter/Stadium)
  - cada energia ESPECIAL     -> 4 copias
  - cartas ACE SPEC           -> 1 copia (regla del juego, aceSpec en CardData)
  - relleno hasta 60          -> la energia BASICA mas vista

No pretende ser el mazo exacto del rival: es un MAZO DE REFERENCIA
determinista y legal para el modo --rival de utils/selfplay.py (winrate
diferencial de dos versiones de main.py contra el mismo rival fijo).

Uso:
    python utils/cosechar_deck_rival.py --salida deck/rivales/crustle.csv
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_TESTS = _ROOT / "tests"
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from cg.api import CardType, all_card_data
from golden_corpus import nuestro_indice


def cosechar_series(rutas):
    """{serial: card_id} de todas las cartas RIVALES vistas.

    El asiento propio se decide por votacion contra deck.csv (`nuestro_indice`,
    espejo del corpus dorado): no siempre somos el jugador 0. Antes se leia
    `step[0]` (la perspectiva del asiento 0, que puede ser el RIVAL) y se
    filtraba por `serial >= 60` (los seriales son por jugador, asi que eso
    tambien asumia que los nuestros eran 0-59): en un episodio jugado desde el
    asiento 1 el resultado era una copia de NUESTRO propio mazo. Cada carta
    trae `playerIndex`, asi que la pertenencia se lee de ahi.
    """
    serials = {}

    def ver(c, rival):
        if (c and c.get("serial") is not None
                and c.get("playerIndex") == rival):
            serials[(rival, c["serial"])] = c["id"]

    for ruta in rutas:
        with open(ruta, encoding="utf-8") as f:
            data = json.load(f)
        yo = nuestro_indice(data)
        rival = 1 - yo
        for step in data.get("steps", []):
            obs = None
            for item in step:
                _o = item.get("observation") or {}
                if (_o.get("current") or {}).get("yourIndex") == yo:
                    obs = _o
                    break
            if obs is None:
                continue
            cur = obs.get("current")
            if not cur:
                continue
            op = cur["players"][rival]
            for p in (op.get("active") or []) + (op.get("bench") or []):
                if not p:
                    continue
                ver(p, rival)
                for c in (p.get("energyCards", []) + p.get("tools", [])
                          + p.get("preEvolution", [])):
                    ver(c, rival)
            for c in op.get("discard", []):
                ver(c, rival)
            for c in (cur.get("stadium") or []):
                ver(c, rival)
    return serials


def amplificar(conteo_visto, tabla):
    """Amplifica el conteo visto hasta 60 cartas segun la regla documentada."""
    mazo = []
    basicas = {}
    for cid, visto in sorted(conteo_visto.items()):
        data = tabla.get(cid)
        if data is None:
            continue
        tipo = data.cardType
        if tipo == int(CardType.BASIC_ENERGY):
            basicas[cid] = visto
        else:
            copias = 1 if getattr(data, "aceSpec", False) else 4
            mazo.extend([cid] * copias)
    if len(mazo) > 60:
        raise SystemExit(
            f"la amplificacion x4 produce {len(mazo)} cartas (>60): recorta "
            f"a mano la lista de vistos o ajusta la regla")
    relleno = 60 - len(mazo)
    if not basicas:
        raise SystemExit("no se vio ninguna energia basica para el relleno")
    basica = max(basicas, key=basicas.get)
    mazo.extend([basica] * relleno)
    return mazo, basica, relleno


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salida", required=True,
                    help="csv destino (un card id por linea, 60 lineas)")
    ap.add_argument("--registros", default="registros",
                    help="carpeta con registro_*.json")
    args = ap.parse_args(argv)

    rutas = sorted((_ROOT / args.registros).glob("registro_*.json"))
    if not rutas:
        raise SystemExit(f"no hay registros en {args.registros}/")
    serials = cosechar_series(rutas)
    conteo = defaultdict(int)
    for cid in serials.values():
        conteo[cid] += 1

    tabla = {c.cardId: c for c in all_card_data()}
    mazo, basica, relleno = amplificar(conteo, tabla)

    print(f"Cartas rivales vistas ({sum(conteo.values())} en "
          f"{len(rutas)} registros):")
    for cid, visto in sorted(conteo.items()):
        d = tabla.get(cid)
        en_mazo = mazo.count(cid)
        print(f"  {cid:>5} visto x{visto} -> en mazo x{en_mazo}  "
              f"{d.name if d else '?'}")
    print(f"Relleno: {relleno} x {tabla[basica].name}({basica})")

    salida = _ROOT / args.salida
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text("\n".join(str(c) for c in mazo) + "\n")
    print(f"Escrito {salida} ({len(mazo)} cartas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
