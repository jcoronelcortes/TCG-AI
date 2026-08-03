"""Matriz de matchups: winrate del agente contra CADA mazo rival.

Por defecto mide contra `deck/rivales_reales/` -- las listas REALES del
leaderboard (utils/rivales_reales.py), con su peso de meta.

Los sinteticos de `deck/rivales/` siguen ahi pero YA NO son el default, y
conviene saber por que: medido contra el top-300, **8 de sus 17 mazos son
arquetipos que no existen en el meta** (Comfey, Iron Thorns, Jellicent, Raging
Bolt, Cornerstone/Cubchoo, Hop's, Fuego Gouging, Comfey/Yveltal). Como la matriz
pondera todos los mazos por igual salvo que se pase --pesos, ejecutarla contra
esa carpeta gastaba casi la mitad del presupuesto de partidas en rivales
imaginarios -- y un cambio que ganase ahi y perdiese contra Marnie parecia
bueno. Se conservan porque siguen sirviendo para probar MECANICAS concretas
(el lock de Iron Thorns, el mill de Comfey) que el meta actual no ofrece.


Fase 8 de la arquitectura de mejora de estrategia. Recorre todos los CSV de la
carpeta de rivales y juega N partidas contra el bot generico con cada uno,
alternando asientos. Imprime la tabla ordenada del matchup mas debil al mas
fuerte, con el intervalo de Wilson 95% y los forfeits.

Con --base <ref-git> imprime ademas el DELTA por matchup contra esa version:
detecta cuando una regla nueva mejora un matchup degradando otro (la clase de
colision Cubchoo/Cornerstone). OJO con el ruido: con 200 partidas el delta
oscila +-7 puntos; solo los deltas grandes y consistentes son senal.

Ese +-7 esta CONFIRMADO por medicion directa (ago 2026): en una corrida a 200
partidas con --base, los 83 mazos que no podian verse afectados por el cambio
-- codigo behavioralmente identico en los dos brazos -- se movieron entre -6.5
y +7.5 puntos. De ahi que el default de --partidas suba a 400 y que exista
--control-carta: el aviso estaba escrito desde el principio y aun asi es facil
leer como senal un delta que cabe entero dentro del ruido.

Con --pesos (y el corpus de utils/rivales_reales.py) el resumen deja de ser una
media simple: cada matchup pesa lo que ese arquetipo pesa en el meta real. Es la
diferencia entre "gano a 8 de 17 mazos" y "gano el X% de las partidas que voy a
jugar en ladder" -- con la media simple, un +10 contra un arquetipo que juega el
1% del campo tapa un -1 contra el que juega el 41%.

`--control-carta <id>` separa los mazos que llevan esa carta (los que el cambio
PUEDE afectar) de los que no, y compara los deltas de ambos grupos. El grupo de
control ejecuta codigo behavioralmente identico en los dos brazos, asi que su
dispersion ES el ruido de esa misma corrida. Es la unica forma barata de saber
si un delta es senal: medido aqui, a 200 partidas por matchup el control llega a
moverse de -6.5 a +7.5 puntos, asi que un delta pequeno sin este desglose no
significa nada.

Uso:
    python utils/matriz_matchups.py --partidas 400
    python utils/matriz_matchups.py --partidas 400 --base HEAD~1
    python utils/matriz_matchups.py --base HEAD~1 --control-carta 1266
    python utils/matriz_matchups.py --solo dragapult,hops
    python utils/matriz_matchups.py --rivales deck/rivales_reales --pesos
    python utils/matriz_matchups.py --rivales deck/rivales_reales --pesos --base HEAD~1
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


def es_mazo(ruta):
    """¿El CSV es una lista de 60 ids y no otra cosa?

    El directorio de rivales contiene tambien `pesos.csv`, y podria contener
    cualquier otro CSV auxiliar. Sin este filtro la matriz intenta leerlo como
    mazo y revienta DESPUES de haber jugado todos los matchups buenos.
    """
    try:
        lineas = [x for x in ruta.read_text(encoding="utf-8-sig").split() if x.strip()]
    except (OSError, UnicodeDecodeError):
        return False
    if len(lineas) != 60:
        return False
    return all(x.lstrip("-").isdigit() for x in lineas)


def cargar_pesos(directorio):
    """Peso de meta por mazo, desde el pesos.csv de utils/rivales_reales.py.

    Sin esto la matriz trata a todos los rivales por igual, que es lo que
    hace que un cambio se apruebe por ganar contra arquetipos que casi nadie
    juega. Devuelve {} si no hay pesos.csv.
    """
    import csv

    ruta = Path(directorio) / "pesos.csv"
    if not ruta.is_file():
        return {}
    pesos = {}
    with ruta.open(encoding="utf-8-sig", newline="") as fh:
        for fila in csv.DictReader(fh):
            nombre = str(fila.get("archivo", ""))
            if nombre.endswith(".csv"):
                nombre = nombre[:-4]
            try:
                pesos[nombre] = float(fila.get("peso_meta") or 0.0)
            except ValueError:
                continue
    return pesos


def _lleva_carta(ruta, card_id):
    try:
        return card_id in [int(x) for x in ruta.read_text().split() if x.strip()]
    except (OSError, ValueError):
        return False


def informe_control(filas, base_por_mazo, rutas, card_id):
    """Separa AFECTADOS (mazos con la carta) de CONTROL y compara sus deltas.

    Es la unica forma barata de saber si un delta es senal: los mazos que NO
    llevan la carta ejecutan codigo behavioralmente identico en los dos brazos,
    asi que su dispersion ES el ruido de esa misma corrida -- sin necesidad de
    correr una calibracion aparte.

    Medido en esta sesion: a 200 partidas por matchup el grupo de control llega
    a moverse de -6.5 a +7.5 puntos. Cualquier delta de los afectados que quepa
    en ese rango no es senal.
    """
    por_nombre = {r.stem: r for r in rutas}
    con, sin = [], []
    for f in filas:
        if f["mazo"] not in base_por_mazo:
            continue
        delta = f["wr"] - base_por_mazo[f["mazo"]]["wr"]
        dprem = None
        bp = base_por_mazo[f["mazo"]].get("dif_premios")
        if f["dif_premios"] is not None and bp is not None:
            dprem = f["dif_premios"] - bp
        ruta = por_nombre.get(f["mazo"])
        destino = con if (ruta is not None and _lleva_carta(ruta, card_id)) else sin
        destino.append((f["mazo"], delta, dprem))

    if not con or not sin:
        print(f"\n(control: no se puede separar por la carta {card_id}; "
              f"afectados={len(con)}, control={len(sin)})")
        return

    print(f"\n=== GRUPO DE CONTROL (carta {card_id}) ===")
    for etiqueta, grupo in (("AFECTADOS", con), ("CONTROL  ", sin)):
        ds = [d for _, d, _ in grupo]
        ps = [p for _, _, p in grupo if p is not None]
        positivos = sum(1 for d in ds if d > 0)
        linea = (f"  {etiqueta} n={len(ds):>2}  delta wr {100 * sum(ds) / len(ds):+6.2f}"
                 f"  rango {100 * min(ds):+.1f} a {100 * max(ds):+.1f}"
                 f"  positivos {positivos}/{len(ds)}")
        if ps:
            linea += f"  delta premios {sum(ps) / len(ps):+.3f}"
        print(linea)
    print("  Si el delta de AFECTADOS cabe en el rango de CONTROL, es ruido: "
          "el control corre codigo identico en los dos brazos.")


def winrate_ponderado(filas, pesos):
    """(winrate esperado en ladder, cobertura de meta medida).

    El winrate se normaliza sobre lo REALMENTE medido, y la cobertura se
    devuelve aparte: un numero sobre el 60% del meta no es comparable con uno
    sobre el 100%, y ocultarlo seria el error que esta metrica viene a corregir.
    """
    cobertura = sum(pesos.get(f["mazo"], 0.0) for f in filas)
    if cobertura <= 0:
        return None, 0.0
    total = sum(pesos.get(f["mazo"], 0.0) * f["wr"] for f in filas)
    return total / cobertura, cobertura


def medir(agente, partidas, rutas):
    bot = BotRival()
    filas = []
    for ruta in rutas:
        deck_rival = sp.leer_deck(ruta)
        stats = sp.torneo(agente, bot, partidas, deck_base=deck_rival)
        dec = stats["candidato"] + stats["base"]
        wr = stats["candidato"] / dec if dec else 0.0
        lo, hi = sp.wilson_95(stats["candidato"], dec)
        pc, pb, dif_premios = sp.premios_por_partida(stats)
        filas.append({
            "mazo": ruta.stem, "wr": wr, "lo": lo, "hi": hi,
            "decididas": dec, "limites": stats["limites"],
            "forfeits": stats["errores_candidato"],
            "forfeits_bot": stats["errores_base"],
            "premios": pc, "premios_bot": pb, "dif_premios": dif_premios,
        })
        extra = "" if dif_premios is None else f" premios {dif_premios:+.2f}"
        print(f"  {ruta.stem}: {100 * wr:.1f}% "
              f"[{100 * lo:.1f}-{100 * hi:.1f}]{extra} "
              f"(forfeits nuestros {stats['errores_candidato']})", flush=True)
    return filas


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--control-carta", type=int, default=None, metavar="ID",
                    help="id de carta que define el grupo AFECTADO: separa los "
                         "mazos que la llevan de los que no y compara los dos "
                         "deltas. Sin esto, un delta no se distingue del ruido")
    ap.add_argument("--partidas", type=int, default=400,
                    help="partidas por matchup (default 400). Medido: a 200 el "
                         "ruido por matchup llega a +-6.5 puntos")
    ap.add_argument("--candidato", default="main.py")
    ap.add_argument("--base", default=None,
                    help="ref de git: imprime el delta por matchup")
    ap.add_argument("--solo", default=None,
                    help="lista de mazos separada por comas (default: todos)")
    ap.add_argument("--rivales", default=str(_ROOT / "deck" / "rivales_reales"),
                    help="carpeta de mazos rivales (default: deck/rivales_reales, "
                         "las listas REALES del leaderboard con sus pesos)")
    ap.add_argument("--pesos", action="store_true",
                    help="pondera por frecuencia real en el meta (necesita el "
                         "pesos.csv de utils/rivales_reales.py)")
    args = ap.parse_args(argv)

    todos = sorted(Path(args.rivales).glob("*.csv"))
    rutas = [r for r in todos if es_mazo(r)]
    omitidos = [r.name for r in todos if r not in rutas]
    if omitidos:
        print(f"(no son mazos, se omiten: {', '.join(omitidos)})")
    if args.solo:
        quiere = {s.strip() for s in args.solo.split(",")}
        rutas = [r for r in rutas if r.stem in quiere]
    if not rutas:
        print("sin mazos rivales que medir")
        return 1

    # Los pesos se cargan ANTES de jugar: si faltan, el error debe salir ya y
    # no despues de una hora de partidas.
    pesos = cargar_pesos(args.rivales) if args.pesos else {}
    if args.pesos and not pesos:
        print(f"ERROR: no hay pesos.csv en {args.rivales}. "
              f"Generalo con: python utils/rivales_reales.py", file=sys.stderr)
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

    sin_peso = [f["mazo"] for f in filas if f["mazo"] not in pesos] if pesos else []

    print("\n=== MATRIZ DE MATCHUPS (peor -> mejor) ===")
    ancho = max(len(f["mazo"]) for f in filas)
    for f in sorted(filas, key=lambda x: x["wr"]):
        linea = (f"{f['mazo']:<{ancho}}  {100 * f['wr']:5.1f}%  "
                 f"[{100 * f['lo']:.1f}-{100 * f['hi']:.1f}]"
                 f"  n={f['decididas']}")
        if pesos:
            linea += f"  meta={100 * pesos.get(f['mazo'], 0.0):4.1f}%"
        if f["forfeits"]:
            linea += f"  FORFEITS={f['forfeits']}"
        if f["dif_premios"] is not None:
            linea += f"  prem={f['dif_premios']:+.2f}"
        if f["mazo"] in base_por_mazo:
            delta = f["wr"] - base_por_mazo[f["mazo"]]["wr"]
            linea += f"  delta={100 * delta:+.1f}"
            if pesos:
                # Lo que ese delta mueve el winrate de ladder: un +10 contra un
                # arquetipo del 1% vale 10 veces menos que un +1 contra el 41%.
                linea += f" (pond {100 * delta * pesos.get(f['mazo'], 0.0):+.2f})"
            base_prem = base_por_mazo[f["mazo"]].get("dif_premios")
            if f["dif_premios"] is not None and base_prem is not None:
                linea += f"  dprem={f['dif_premios'] - base_prem:+.2f}"
        print(linea)
    peor = min(filas, key=lambda x: x["wr"])
    print(f"\nMatchup mas debil: {peor['mazo']} ({100 * peor['wr']:.1f}%)")

    if args.control_carta is not None and base_por_mazo:
        informe_control(filas, base_por_mazo, rutas, args.control_carta)
    elif args.control_carta is not None:
        print("\n(--control-carta necesita --base: sin baseline no hay deltas "
              "que separar)")

    if pesos:
        wr_pond, cobertura = winrate_ponderado(filas, pesos)
        media = sum(f["wr"] for f in filas) / len(filas)
        print("\n=== WINRATE ESPERADO EN LADDER (ponderado por meta) ===")
        if wr_pond is None:
            print("sin cobertura: ninguno de los mazos medidos tiene peso")
            return 0
        print(f"  ponderado : {100 * wr_pond:5.1f}%   sobre el "
              f"{100 * cobertura:.1f}% del meta cubierto")
        print(f"  sin pesar : {100 * media:5.1f}%   (media simple, para comparar)")

        # El matchup mas debil NO es donde mas se pierde: un 40% contra un
        # arquetipo del 1% cuesta menos que un 80% contra el que juega el 41%.
        # Esto ordena por puntos de ladder perdidos, que es donde conviene
        # invertir el esfuerzo.
        sangria = [t for t in sorted(
            ((pesos.get(f["mazo"], 0.0) * (1 - f["wr"]), f) for f in filas),
            key=lambda t: -t[0],
        )[:3] if t[0] > 0]
        if sangria:
            print("\n  Donde se pierden mas puntos de ladder:")
            for coste, f in sangria:
                print(f"    {f['mazo']:<28} {100 * coste:5.2f} pts  "
                      f"(meta {100 * pesos.get(f['mazo'], 0.0):.0f}%, "
                      f"ganamos {100 * f['wr']:.1f}%)")
        if sin_peso:
            print(f"  aviso: {len(sin_peso)} mazo(s) sin peso, excluidos del "
                  f"ponderado: {', '.join(sorted(sin_peso)[:5])}"
                  + (" ..." if len(sin_peso) > 5 else ""))
        # Diferencial de premios ponderado: la metrica con resolucion. El
        # winrate contra el bot esta saturado (>93%) y no puede arbitrar un
        # cambio; los premios si graduan.
        prem = [f for f in filas if f["dif_premios"] is not None]
        if prem:
            cob_p = sum(pesos.get(f["mazo"], 0.0) for f in prem)
            if cob_p > 0:
                dif_pond = sum(pesos.get(f["mazo"], 0.0) * f["dif_premios"]
                               for f in prem) / cob_p
                print(f"\n  DIFERENCIAL DE PREMIOS ponderado: {dif_pond:+.3f} "
                      f"por partida")
                print("  (premios que cobramos menos los que cobra el rival; "
                      "tiene resolucion donde el winrate ya no)")

        if base_por_mazo:
            filas_base = [base_por_mazo[f["mazo"]] for f in filas
                          if f["mazo"] in base_por_mazo]
            wr_base, _ = winrate_ponderado(filas_base, pesos)
            if wr_base is not None:
                print(f"\n  baseline  : {100 * wr_base:5.1f}%   "
                      f"DELTA PONDERADO = {100 * (wr_pond - wr_base):+.2f} puntos")
                print("  (este delta, y no la media simple, es lo que decide "
                      "si el cambio gana partidas en ladder)")
            base_prem = [b for b in filas_base if b.get("dif_premios") is not None]
            if prem and base_prem:
                cob_b = sum(pesos.get(b["mazo"], 0.0) for b in base_prem)
                if cob_b > 0 and cob_p > 0:
                    dif_b = sum(pesos.get(b["mazo"], 0.0) * b["dif_premios"]
                                for b in base_prem) / cob_b
                    print(f"  premios baseline: {dif_b:+.3f}   "
                          f"DELTA DE PREMIOS = {dif_pond - dif_b:+.3f} por partida")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
