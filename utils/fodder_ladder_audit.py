"""The cost pays with the FUEL of the body the search is buying.

THE PENDING QUESTION, written down after `registro_002` step 15 (episode
91529732, turn 2 vs Cynthia's Garchomp ex, LOST) and never measured. The hand
was {Bayleef 50, Grass 80, Meganium 40, Hydrapple ex 3, Grass 80} and the cost
took BOTH Grass -- the highest score falls first -- to buy a Teal Mask Ogerpon
ex whose only route to doing anything is Teal Dance: attach a Grass FROM HAND
and draw. It kept a Bayleef and a Meganium that could not enter play for two
turns: no Chikorita in play, none in hand.

WHY THE LADDER PRICES IT THAT WAY. Energy is the cheapest fodder because there
are twelve of them in the deck. But what makes it cheap is the QUANTITY, not the
ACCESS: with no Lillie's and no Night Stretcher there is no way to touch another
one this turn or the next, while an orphaned evolution is a genuinely dead card.
`_ub_real_fodder` already counts that Bayleef and that Meganium as real fodder,
so the two modules disagree and the ladder is the one that is wrong.

WHAT THIS MEASURES, and only this. For every DISCARD menu, it counts the times a
Basic Grass Energy is scored ABOVE (= falls sooner than) an evolution the agent
itself calls ORPHANED -- `_evo_link_state`, pre-evolution neither in play nor in
hand. The orphan reading is the agent's own, read off the scoring context; this
file re-implements no rule and asserts no fix.

IT DOES NOT FIX IT, on purpose. Re-ordering the ladder touches EVERY forced
discard, not just the Ultra Ball cost, and the memory of this project says so:
that change deserves its own record, its own census and its own gate. What was
missing was the number, and the number is the point of running the census first.

READ THE COLUMNS. `energias` is how many Grass the hand still holds: the whole
argument is about access, so a menu that drops one of five is a different event
from a menu that drops the last two. `[COSTE]` marks our own Ultra Ball -- the
board the finding was written on -- against a discard forced by their card.

Usage:
    python utils/fodder_ladder_audit.py
    python utils/fodder_ladder_audit.py --dump log/forraje.json
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402
from duplicate_protection_audit import instrumentar, replay  # noqa: E402


def contradicciones(captura, energia_id):
    """(score of the energy, orphan id, its score) for every inversion here.

    An inversion is the energy scoring STRICTLY higher than an orphan: higher
    means discarded sooner, so the fuel leaves and the dead card stays.
    """
    energias = [(cid, s) for cid, _, s in captura.opciones if cid == energia_id]
    huerfanas = [(cid, nombre, s) for cid, nombre, s in captura.opciones
                 if cid in captura.huerfanos and cid != energia_id]
    salida = []
    for _, score_e in energias:
        for cid, nombre, score_h in huerfanas:
            if score_e > score_h:
                salida.append((score_e, cid, nombre, score_h))
    return salida, len(energias)


def informe(capturas, energia_id, records):
    menus = [c for c in capturas if c.opciones]
    con_huerfana = [c for c in menus if c.huerfanos]
    print(f"\nEL COSTE Y EL COMBUSTIBLE -- {len(menus)} menus de DESCARTE en "
          f"{records} registros, {len(con_huerfana)} con alguna evolucion "
          f"HUERFANA sobre la mesa")

    # ONE ROW PER (menu, orphan), not per pair of cards. Three Grass in hand
    # above one dead Meganium is one inversion seen three times, and printing it
    # three times reads as three findings.
    filas, por_carta, pares = [], Counter(), 0
    for captura in menus:
        inversiones, energias = contradicciones(captura, energia_id)
        pares += len(inversiones)
        peor = {}
        for score_e, cid, nombre, score_h in inversiones:
            previo = peor.get(cid)
            if previo is None or score_e > previo[0]:
                peor[cid] = (score_e, nombre, score_h)
            por_carta[nombre] += 0        # keep the key, count menus below
        for cid, (score_e, nombre, score_h) in peor.items():
            filas.append((score_e - score_h, score_e, nombre, score_h,
                          energias, captura))
            por_carta[nombre] += 1

    if not filas:
        print("  ninguna: la energia nunca cae antes que una evolucion huerfana")
        print("\nESO NO CIERRA LA PREGUNTA, la acota: el corpus congelado no "
              "contiene el tablero de registro_002 paso 15, y con "
              "[[el-motor-espera-al-turno-que-puede-ejecutarlo]] esa Ultra Ball "
              "ya no llega a jugarse. La lectura honesta es que el evento es "
              "raro aqui, no que no exista.")
        return filas

    # Sorted on the numbers only: the capture rides along in the tuple and two
    # of them are not comparable.
    filas.sort(key=lambda f: (f[0], f[1], f[3]), reverse=True)
    print(f"  {len(filas)} inversiones (la energia cae antes que la carta muerta) "
          f"en {len({id(f[5]) for f in filas})} menus, {pares} pares carta a carta")
    print("\n  delta  energia  huerfana                      su score  energias  donde")
    for delta, score_e, nombre, score_h, energias, captura in filas:
        print(f"  {delta:>5}  {score_e:>7}  {nombre:<28} {score_h:>8}  "
              f"{energias:>8}  {captura.registro} t{captura.turno} "
              f"a{captura.accion}{'  [COSTE]' if not captura.forzado else ''}")
    print("\n  por carta:", ", ".join(f"{n} x{c}" for n, c in por_carta.most_common()))
    print("\nESTO ES UNA MEDIDA, NO UN ARREGLO. Reordenar la escalera toca TODO "
          "descarte forzado, no solo la Ultra Ball, y merece su propio registro, "
          "su propio censo y su propio gate. Lo que faltaba era el numero.")
    return filas


def auto_test(capturas, energia_id):
    """Both halves, on what the corpus can prove without planting anything.

    SENSITIVITY: the comparison has to be capable of firing at all, so the
    capture must contain at least one menu that holds BOTH an energy and an
    orphaned evolution. Without that board the zero below would mean "nothing
    looked", and this file's whole subject is telling those two apart.

    SPECIFICITY: an orphan is never compared against itself, and a menu with no
    orphan can produce no inversion.
    """
    print("AUTO-TEST (las dos mitades) ...", flush=True)
    fallos = []
    menus = [c for c in capturas if c.opciones]
    comparables = [c for c in menus
                   if c.huerfanos
                   and any(cid == energia_id for cid, _, _ in c.opciones)
                   and any(cid in c.huerfanos for cid, _, _ in c.opciones)]
    if not comparables:
        fallos.append("ningun menu del corpus tiene a la vez una energia y una "
                      "evolucion huerfana en la mano: el cero no seria una medida")
    for captura in menus:
        if not captura.huerfanos and contradicciones(captura, energia_id)[0]:
            fallos.append(f"{captura.registro} no tiene huerfanas y produjo una "
                          "inversion: la lectura del tablero esta mal")
            break
    for f in fallos:
        print(f"  AUTO-TEST FALLA: {f}")
    if not fallos:
        print(f"  AUTO-TEST OK: {len(comparables)} menus donde la comparacion "
              f"puede dispararse\n", flush=True)
    return fallos


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dump", default=None, help="write the inversions as json")
    ap.add_argument("--self-test", action="store_true",
                    help="run only the two halves and report whether they hold")
    args = ap.parse_args(argv)

    agente = sp.load_agent(_ROOT / "main.py", "forraje")
    energia_id = agente.Basic_Grass_Energy
    capturas = []
    restaurar = instrumentar(agente, capturas)
    try:
        records = replay(agente, capturas)
        fallos = auto_test(capturas, energia_id)
        if args.self_test:
            return 1 if fallos else 0
        if fallos:
            print("\nAUTO-TEST FALLIDO: la auditoria queda INVALIDA y no se "
                  "imprime.")
            return 1
        filas = informe(capturas, energia_id, records)
        if args.dump:
            destino = Path(args.dump)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(json.dumps([
                {"delta": d, "score_energia": se, "huerfana": n,
                 "score_huerfana": sh, "energias_en_mano": e,
                 "registro": c.registro, "turno": c.turno, "accion": c.accion,
                 "coste_propio": not c.forzado}
                for d, se, n, sh, e, c in filas], indent=2, ensure_ascii=False))
            print(f"\ninversiones -> {destino}")
    finally:
        restaurar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
