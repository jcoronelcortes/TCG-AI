"""Convierte los mazos del leaderboard en rivales MEDIBLES para el self-play.

Fase 9 de la arquitectura de mejora de estrategia. `utils/construir_mazos_meta.py`
define a mano rivales sinteticos que "no pretenden ser las listas exactas del
meta"; aqui partimos de las listas EXACTAS que descargo
`utils/descargar_mazos_competidores.py` desde el leaderboard.

Hace dos cosas, y la segunda es la importante:

1. DEDUPLICA. Los 100 mazos del top-100 son ~39 listas unicas: los 49 mazos
   del arquetipo dominante son 6 listas con similitud 0.99. Medir contra los
   100 gasta el presupuesto de partidas en repetir el mismo matchup en vez de
   en reducir el ruido. Cada lista unica se queda con el PESO DE META que le
   corresponde (cuantos de los 100 mazos eran esa lista).

2. CRIBA POR PILOTABILIDAD. Estas son listas reales, con trainers que el bot
   generico (utils/bot_rival.py) puede no saber usar: su politica para un
   select desconocido es "las primeras minCount opciones". Un mazo que el bot
   no sabe pilotar no mide el matchup, mide que el bot se atasca -- y devuelve
   un winrate nuestro altisimo y FALSO.

   Es la misma leccion que el bot sin habilidades (memoria del proyecto: el
   harness era CIEGO a los mazos cuyo motor es una habilidad, y toda regla
   contra ese motor salia NEUTRA por construccion). Antes de creerse un
   numero de matchup hay que comprobar que el rival puede EJECUTAR su mazo.

   La criba enfrenta al bot pilotando la lista real contra el bot pilotando
   nuestro deck.csv, y exige tres cosas:
     * que no haga jugadas ilegales (forfeits ~ 0),
     * que las partidas TERMINEN (pocas por limite de pasos),
     * que gane algo (un mazo que el bot no arranca pierde casi siempre).

   Lo que no pasa la criba NO se tira: se guarda en no_pilotables/ y se
   reporta, porque saber que parte del meta no sabemos medir es informacion,
   no un fallo.

Salida en deck/rivales_reales/:
    <arquetipo>_<n>.csv   una lista real por archivo (60 ids, formato del proyecto)
    pesos.csv             peso de meta y resultado de la criba de cada lista
    no_pilotables/        las listas rechazadas, para inspeccion

Uso:
    python utils/rivales_reales.py                     # dedupe + criba
    python utils/rivales_reales.py --partidas 60       # criba mas fina
    python utils/rivales_reales.py --sin-criba         # solo dedupe (rapido)

Despues, la matriz consume el corpus y sus pesos:
    python utils/matriz_matchups.py --rivales deck/rivales_reales --pesos
"""

import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Umbrales de la criba. Laxos a proposito: el objetivo es descartar el mazo
# que el bot NO puede jugar, no exigir que lo juegue bien.
#
# MIN_WINRATE esta CALIBRADO contra un mazo trampa (los 17 Pokemon de una lista
# real + 43 energias de un tipo que ninguno de sus ataques paga): legal, pero
# sin motor. Ese mazo gana 10%, mientras que las 39 listas reales van de 26.7%
# a 88.3%. El 15% cae en el hueco entre ambos. Con el 5% inicial el mazo trampa
# pasaba la criba, que es justo el falso negativo que esta criba existe para
# evitar -- si se cambia este umbral, hay que rehacer esa comprobacion.
MAX_FORFEITS = 0.02      # jugadas ilegales del lado rival
MAX_LIMITES = 0.15       # partidas que no terminan dentro del tope de pasos
MIN_WINRATE = 0.15       # por debajo, el mazo no arranca (ver calibracion arriba)


def slug(texto):
    """Nombre de archivo estable a partir del arquetipo."""
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t or "sin_arquetipo"


def cargar_corpus(origen):
    """Lee los mazos descargados y los agrupa por lista IDENTICA.

    Devuelve la lista de grupos ordenada de mayor a menor peso de meta.
    """
    indice = {}
    ruta_indice = origen / "indice.csv"
    if ruta_indice.is_file():
        with ruta_indice.open(encoding="utf-8-sig", newline="") as fh:
            for fila in csv.DictReader(fh):
                indice[fila.get("archivo", "")] = fila.get("arquetipo", "")

    grupos = {}
    total = 0
    for ruta in sorted(origen.glob("mazo_*.csv")):
        mazo = [int(x) for x in ruta.read_text(encoding="utf-8").split() if x.strip()]
        if len(mazo) != 60:
            print(f"  aviso: {ruta.name} tiene {len(mazo)} cartas, se omite")
            continue
        total += 1
        clave = tuple(sorted(Counter(mazo).items()))
        grupo = grupos.setdefault(
            clave, {"mazo": sorted(mazo), "copias": 0, "arquetipos": Counter()}
        )
        grupo["copias"] += 1
        grupo["arquetipos"][indice.get(ruta.name, "")] += 1

    salida = []
    for grupo in grupos.values():
        arq = grupo["arquetipos"].most_common(1)[0][0] if grupo["arquetipos"] else ""
        salida.append(
            {
                "mazo": grupo["mazo"],
                "copias": grupo["copias"],
                "peso_meta": grupo["copias"] / total if total else 0.0,
                "arquetipo": arq,
            }
        )
    salida.sort(key=lambda g: (-g["peso_meta"], g["arquetipo"], g["mazo"]))

    # Nombre por arquetipo, numerado por peso descendente dentro del arquetipo.
    por_arquetipo = Counter()
    for grupo in salida:
        base = slug(grupo["arquetipo"])
        por_arquetipo[base] += 1
        grupo["nombre"] = f"{base}_{por_arquetipo[base]}"
    return salida, total


def cribar(grupo, partidas, deck_referencia):
    """¿Puede el bot generico pilotar esta lista? Bot(real) vs Bot(nuestro mazo)."""
    import selfplay as sp
    from bot_rival import BotRival

    # Instancias separadas: el bot lleva estado por turno y compartirlo entre
    # los dos asientos mezclaria los contadores de habilidades de ambos.
    stats = sp.torneo(
        BotRival(), BotRival(), partidas,
        deck_candidato=list(grupo["mazo"]), deck_base=list(deck_referencia),
    )
    decididas = stats["candidato"] + stats["base"]
    wr = stats["candidato"] / decididas if decididas else 0.0
    forfeits = stats["errores_candidato"] / partidas if partidas else 0.0
    limites = stats["limites"] / partidas if partidas else 0.0

    motivos = []
    if forfeits > MAX_FORFEITS:
        motivos.append(f"jugadas ilegales {100 * forfeits:.0f}%")
    if limites > MAX_LIMITES:
        motivos.append(f"partidas sin terminar {100 * limites:.0f}%")
    if wr < MIN_WINRATE:
        motivos.append(f"no arranca (gana {100 * wr:.0f}%)")
    return {
        "wr_criba": wr, "forfeits": forfeits, "limites": limites,
        "admitido": not motivos, "motivo": "; ".join(motivos),
    }


def escribir(grupos, salida):
    salida.mkdir(parents=True, exist_ok=True)
    rechazados = salida / "no_pilotables"
    for viejo in salida.glob("*.csv"):
        viejo.unlink()
    if rechazados.is_dir():
        for viejo in rechazados.glob("*.csv"):
            viejo.unlink()

    filas = []
    for grupo in grupos:
        destino = salida if grupo["admitido"] else rechazados
        destino.mkdir(parents=True, exist_ok=True)
        (destino / f"{grupo['nombre']}.csv").write_text(
            "\n".join(str(cid) for cid in grupo["mazo"]) + "\n", encoding="utf-8"
        )
        filas.append(
            {
                "archivo": f"{grupo['nombre']}.csv",
                "arquetipo": grupo["arquetipo"],
                "peso_meta": round(grupo["peso_meta"], 4),
                "mazos_origen": grupo["copias"],
                "estado": "admitido" if grupo["admitido"] else "no_pilotable",
                "wr_criba": ("" if grupo.get("wr_criba") is None
                             else round(grupo["wr_criba"], 3)),
                "forfeits": ("" if grupo.get("forfeits") is None
                             else round(grupo["forfeits"], 3)),
                "limites": ("" if grupo.get("limites") is None
                            else round(grupo["limites"], 3)),
                "motivo": grupo.get("motivo", ""),
            }
        )
    with (salida / "pesos.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)
    return filas


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--origen", default=str(_ROOT / "decks_competidores"))
    ap.add_argument("--salida", default=str(_ROOT / "deck" / "rivales_reales"))
    ap.add_argument("--partidas", type=int, default=40,
                    help="partidas de criba por lista unica (default 40)")
    ap.add_argument("--referencia", default=str(_ROOT / "deck.csv"),
                    help="mazo contra el que se criba (default: el nuestro)")
    ap.add_argument("--sin-criba", action="store_true",
                    help="solo deduplicar, sin medir pilotabilidad")
    ap.add_argument("--top", type=int, default=None,
                    help="cribar solo las N listas de mayor peso (el resto se omite)")
    args = ap.parse_args(argv)

    origen = Path(args.origen)
    if not origen.is_dir():
        print(f"ERROR: no existe {origen}", file=sys.stderr)
        return 1

    print("== 1/3 Deduplicando el corpus ==")
    grupos, total = cargar_corpus(origen)
    if not grupos:
        print("ERROR: no se encontro ningun mazo", file=sys.stderr)
        return 1
    print(f"{total} mazos  ->  {len(grupos)} listas unicas")
    cubierto = sum(g["peso_meta"] for g in grupos[: args.top]) if args.top else 1.0
    if args.top:
        grupos = grupos[: args.top]
        print(f"Limitado a las {len(grupos)} de mayor peso ({100 * cubierto:.0f}% del meta)")

    if args.sin_criba:
        for grupo in grupos:
            grupo.update(admitido=True, wr_criba=None, forfeits=None,
                         limites=None, motivo="sin cribar")
    else:
        print(f"\n== 2/3 Criba de pilotabilidad ({args.partidas} partidas por lista) ==")
        import selfplay as sp
        deck_ref = sp.leer_deck(args.referencia)
        for n, grupo in enumerate(grupos, start=1):
            resultado = cribar(grupo, args.partidas, deck_ref)
            grupo.update(resultado)
            marca = "ok " if grupo["admitido"] else "NO "
            print(f"  {marca}{grupo['nombre']:<28} peso {100 * grupo['peso_meta']:4.0f}%  "
                  f"gana {100 * grupo['wr_criba']:5.1f}%  "
                  f"({n}/{len(grupos)}) {grupo['motivo']}", flush=True)

    print("\n== 3/3 Escritura ==")
    filas = escribir(grupos, Path(args.salida))
    admitidos = [g for g in grupos if g["admitido"]]
    peso_ok = sum(g["peso_meta"] for g in admitidos)
    print(f"Listas admitidas: {len(admitidos)}/{len(grupos)}  ->  {args.salida}")
    print(f"COBERTURA DE META MEDIBLE: {100 * peso_ok:.1f}%")
    if len(admitidos) < len(grupos):
        print("\nNo pilotables (el harness no puede medir esta parte del meta):")
        for g in grupos:
            if not g["admitido"]:
                print(f"  {g['nombre']:<28} peso {100 * g['peso_meta']:4.0f}%  {g['motivo']}")
    print(f"\nPesos en {Path(args.salida) / 'pesos.csv'} ({len(filas)} filas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
