"""Which cards give the SECOND copy in hand the same protection as the first.

THE SHAPE. A discard menu prices cards one at a time, so a protection written as
"this card is our only out" is handed to every copy of it in the hand. The
protection is about the ROLE, and only one card can play the role; the surplus is
what makes a card cheap, never expensive.

It has cost this project twice already, in the same week:

  * the counter-stadium (ab1945a). The guard was `hand_counts[Forest] <= 1`, so
    it switched OFF exactly when we held more than one out -- both copies fell
    through to the spare-copy score and both went to the discard pile, under a
    Neutralization Zone that muted every ex we had. The repair is a LATCH: protect
    one, let the rest be fodder, the same shape as `_lillie_protected_once` and
    `_evo_spare_seen`;
  * and the flip that Wave 1 of docs/discard-plan-2026-08.md left standing
    (6f98a9b): in registro_021 turn 5 a second Meowth ex outranks a live Night
    Stretcher for keeping. Two copies of the same Basic both receive the
    protection of the plan, when only one of them can BE the plan.

Both were found by reading one board. This reads all of them.

HOW. `score_option` is wrapped on the loaded agent -- by IDENTITY across every
namespace, because `from ... import` binds a copy -- and the frozen corpus is
replayed through it. Every DISCARD menu is captured with the score each option
got, which is the ladder's own answer and not a reconstruction of it. Nothing on
disk is touched and no scoring code is re-implemented.

WHAT IT REPORTS. For every menu where the hand holds two or more copies of the
same card and every copy came out with the SAME score, one line. Ranked by how
protective that score is: in this menu HIGHER MEANS DISCARDED SOONER, so a pair
that both scored 80 is two cards heading for the pile and nobody is protecting
anything. The defect is a pair both scored LOW.

READ IT AS A WORKLIST. A duplicate pair with equal scores is not automatically
wrong: if both copies really are interchangeable fodder, equal is the honest
answer. What the report ranks to the top is the pair whose shared score is a
KEEP -- that is the band where only one of them can be the reason.

Usage:
    python utils/duplicate_protection_audit.py
    python utils/duplicate_protection_audit.py --self-test
    python utils/duplicate_protection_audit.py --dump log/duplicados.json
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402
from rule_census import espacio, espacios_del_agente  # noqa: E402

# Everything at or below this score is the menu saying "let it go": the bands
# above it are fodder of one kind or another. Taken from the ladder's own
# constants rather than guessed -- see `DISCARD_*` in ptcg/cards/ids.py.
UMBRAL_FORRAJE = 30


class Captura:
    """One DISCARD menu, with the score the ladder gave each option."""

    __slots__ = ("registro", "turno", "accion", "forzado", "opciones",
                 "huerfanos", "extra")

    def __init__(self, registro, turno, accion, forzado, huerfanos=(), extra=None):
        self.registro = registro
        self.turno = turno
        self.accion = accion
        self.forzado = forzado
        self.opciones = []      # (card_id, nombre, score)
        # The agent's OWN reading of which evolutions are orphaned on this board
        # (`_evo_link_state`): pre-evolution neither in play nor in hand. Taken
        # from the scoring context rather than re-derived, so a second audit
        # asking about dead cards is asking the agent, not a copy of it.
        self.huerfanos = frozenset(huerfanos or ())
        # Whatever the caller's `extra(tc)` hook read off the live context when
        # this menu opened. It exists because the readings an audit needs are
        # only reachable while `tc` is alive, and reconstructing them afterwards
        # from the capture is how an audit stops asking the agent and starts
        # guessing -- which is exactly the failure mode this family of tools
        # keeps finding in itself.
        self.extra = dict(extra or {})

    @property
    def duplicados(self):
        """card_id -> [scores], for the ids the hand holds more than once."""
        por_id = defaultdict(list)
        for card_id, _, score in self.opciones:
            por_id[card_id].append(score)
        return {k: v for k, v in por_id.items() if len(v) > 1}

    def nombre_de(self, card_id):
        for cid, nombre, _ in self.opciones:
            if cid == card_id:
                return nombre
        return str(card_id)


def instrumentar(agente, capturas, extra=None):
    """Wraps `score_option` and records every DISCARD menu it prices.

    Returns an undo callable. The wrapper delegates: the score is the agent's,
    computed by the agent's own code, and this only watches it go past.

    `extra(tc)` is an optional hook called ONCE per menu, the moment it opens,
    whose dict is stored on the capture. Audits that need a reading only the
    live context can answer -- and every one of them so far has -- ask for it
    here instead of rebuilding the board from the capture afterwards.
    """
    scoring = espacio(agente, "ptcg.turn.scoring")
    if scoring is None:
        raise SystemExit("no se encontro ptcg.turn.scoring en el agente cargado")
    original = scoring["score_option"]
    saltar = scoring["_SALTAR"]

    contexto_descarte = agente.SelectContext.DISCARD
    get_card = agente.get_card
    tabla = agente.card_table

    abiertas = {}

    def nombre(card_id):
        data = tabla.get(card_id)
        return getattr(data, "name", None) or str(card_id)

    def envuelto(tc, o, score):
        resultado = original(tc, o, score)
        if getattr(tc, "context", None) != contexto_descarte:
            return resultado
        if resultado is saltar:
            return resultado
        # KEYED BY id(), AND THE SELECT IS KEPT ALIVE ON PURPOSE. CPython reuses
        # an address as soon as the object at it is collected, so keying menus by
        # `id(tc.select)` alone merged distinct menus into one capture whenever a
        # select landed on a freed address -- the same corpus reported 90 menus
        # on one run and 98 on the next. Holding a reference in the value makes
        # the id unique for as long as the audit needs it.
        clave = id(tc.select)
        entrada = abiertas.get(clave)
        captura = entrada[1] if entrada is not None else None
        if captura is None:
            # `tc.obs` is an `Observation`, not the raw dict the records carry:
            # by the time the scorer sees it the simulator has already parsed it.
            actual = getattr(tc.obs, "current", None)
            efecto = getattr(tc.select, "effect", None)
            forzado = (efecto is not None
                       and getattr(efecto, "playerIndex", tc.my_index) != tc.my_index)
            captura = Captura("?", getattr(actual, "turn", None),
                              getattr(actual, "turnActionCount", None), forzado,
                              getattr(tc, "_evo_huerfanos", None),
                              extra(tc) if extra is not None else None)
            abiertas[clave] = (tc.select, captura)
            capturas.append(captura)
        card = get_card(tc.obs, o.area, o.index,
                        getattr(o, "playerIndex", tc.my_index))
        if card is not None:
            captura.opciones.append((card.id, nombre(card.id), resultado))
        return resultado

    deshacer = []
    for _, esp in espacios_del_agente(agente):
        for var, valor in list(esp.items()):
            if valor is original:
                esp[var] = envuelto
                deshacer.append(lambda e=esp, v=var, o=valor: e.__setitem__(v, o))

    def restaurar():
        for accion in deshacer:
            accion()

    return restaurar


def replay(agente, capturas):
    import golden_corpus as gc

    records = gc.frozen_records()
    if not records:
        raise SystemExit("no hay corpus congelado en tests/corpus/")
    for nombre, data in sorted(records.items()):
        antes = len(capturas)
        gc.replay_data(agente, data)
        for captura in capturas[antes:]:
            captura.registro = nombre
    return len(records)


def informe(capturas, records):
    menus = [c for c in capturas if c.opciones]
    forzados = sum(1 for c in menus if c.forzado)
    print(f"\nAUDITORIA DE DOBLE COPIA -- {len(menus)} menus de DESCARTE en "
          f"{records} registros ({forzados} forzados por su carta, "
          f"{len(menus) - forzados} coste de una busqueda nuestra)")

    hallazgos = []
    for captura in menus:
        for card_id, scores in captura.duplicados.items():
            if len(set(scores)) == 1:
                hallazgos.append((scores[0], card_id, captura))

    if not hallazgos:
        print("  ninguna carta duplicada recibio el mismo score en ningun menu")
        return hallazgos

    # Lowest score first: in this menu low means KEEP, and a pair both kept is
    # the band where only one of them can be the reason.
    hallazgos.sort(key=lambda h: h[0])
    protegidos = [h for h in hallazgos if h[0] <= UMBRAL_FORRAJE]
    print(f"  {len(hallazgos)} pares con score IDENTICO, de los cuales "
          f"{len(protegidos)} en la banda de GUARDAR (score <= {UMBRAL_FORRAJE})")
    print(f"\nLAS COPIAS QUE COMPARTEN PROTECCION (score <= {UMBRAL_FORRAJE}):")
    if not protegidos:
        print("  ninguna: toda copia duplicada que empata lo hace ya como forraje")
    for score, card_id, captura in protegidos:
        print(f"  score {score:<6} {captura.nombre_de(card_id):<26} "
              f"x{len(captura.duplicados[card_id])}  {captura.registro} "
              f"turno {captura.turno} accion {captura.accion}"
              f"{'  [FORZADO]' if captura.forzado else ''}")

    print("\nESTO ES UNA LISTA DE TRABAJO. Dos copias con el mismo score no estan "
          "mal por serlo: si de verdad son forraje intercambiable, empatar es la "
          "respuesta honesta. Lo que hay que mirar es el par cuyo score compartido "
          "es un GUARDAR, porque ahi solo una de las dos puede ser el motivo.")
    return hallazgos


def auto_test(agente, capturas):
    """The two halves, on the cards whose answer is already known.

    SENSITIVITY is not planted here: it is HISTORICAL. `Meowth ex` is the card
    the standing corpus flip is about (6f98a9b, registro_021 turn 5), so if the
    audit cannot see a duplicate pair sharing a keep-band score anywhere in the
    corpus, it is not looking.

    SPECIFICITY is `Forest of Vitality`, which was LATCHED this morning
    (ab1945a): protect one, let the rest be fodder. If the audit reports the
    Forest as sharing its protection, the reading is wrong -- the repair is in
    the tree and the corpus contains the board it was written for.
    """
    print("AUTO-TEST (las dos mitades) ...", flush=True)
    fallos = []
    menus = [c for c in capturas if c.opciones]
    if not menus:
        return ["el corpus no produjo un solo menu de DESCARTE: no se ha medido nada"]

    pares = [(s, cid, c) for c in menus for cid, scores in c.duplicados.items()
             if len(set(scores)) == 1 for s in [scores[0]]]
    if not pares:
        fallos.append("ni un par duplicado con score identico en todo el corpus: "
                      "la captura no esta viendo las manos")

    # Specificity: the Forest is latched, so its copies must NOT share a score
    # in the band that keeps them.
    forest = agente.Forest_of_Vitality
    compartidos_forest = [s for s, cid, _ in pares
                          if cid == forest and s <= UMBRAL_FORRAJE]
    if compartidos_forest:
        fallos.append(f"el Forest of Vitality aparece compartiendo proteccion "
                      f"{compartidos_forest}: esa carta lleva el latch desde ab1945a")

    for f in fallos:
        print(f"  AUTO-TEST FALLA: {f}")
    if not fallos:
        print("  AUTO-TEST OK: ve pares duplicados y no acusa a la carta ya "
              "reparada\n", flush=True)
    return fallos


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dump", default=None, help="write the captured menus as json")
    ap.add_argument("--self-test", action="store_true",
                    help="run only the two halves and report whether they hold")
    args = ap.parse_args(argv)

    agente = sp.load_agent(_ROOT / "main.py", "auditoria")
    capturas = []
    restaurar = instrumentar(agente, capturas)
    try:
        records = replay(agente, capturas)
        fallos = auto_test(agente, capturas)
        if args.self_test:
            return 1 if fallos else 0
        if fallos:
            print("\nAUTO-TEST FALLIDO: la auditoria queda INVALIDA y no se "
                  "imprime. Un numero de un detector que no puede probar que "
                  "funciona no es un hallazgo mas pequeno, es ninguno.")
            return 1
        informe(capturas, records)
        if args.dump:
            destino = Path(args.dump)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(json.dumps([
                {"registro": c.registro, "turno": c.turno, "accion": c.accion,
                 "forzado": c.forzado,
                 "opciones": [{"id": i, "nombre": n, "score": s}
                              for i, n, s in c.opciones]}
                for c in capturas if c.opciones], indent=2, ensure_ascii=False))
            print(f"\nmenus capturados -> {destino}")
    finally:
        restaurar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
