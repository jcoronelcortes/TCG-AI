"""Corpus dorado: replay de TODOS los registros con snapshot de decisiones.

Fase 2 de la arquitectura de mejora de estrategia. Los tests con fixtures
cubren los pasos que ya dolieron; el corpus dorado cubre TODAS las decisiones
de los registros actuales: cada cambio en main.py produce un diff explicito
de que decisiones historicas voltea, y cualquier flip inesperado salta a
revision ANTES del merge (la clase de regresion "reaparecio").

Los registros (`registros/*.json`, salida de utils/split_turns.py) son datos
LOCALES y transitorios (git-ignored): se reemplazan cuando se analizan
partidas nuevas. Por eso el snapshot (`registros/decisiones_dorado.json`)
vive junto a ellos (hereda el ignore) y guarda un hash md5 por registro, para
distinguir dos fallos con mensajes distintos:

  1. "el registro cambio en disco" -> regenerar el snapshot (dato nuevo);
  2. "las decisiones cambiaron con los mismos registros" -> TU cambio de
     main.py volteo decisiones historicas: revisar cada flip (¿buscado?).

Uso:
    python tests/golden_corpus.py               # comparar (exit 1 si difiere)
    python tests/golden_corpus.py --actualizar  # revisar diff y reescribir

El replay resetea el estado global del agente ANTES DE CADA ARCHIVO (misma
semantica que los tests con fixtures: cada registro es un segmento que se
reproduce desde frio). Solo se reproducen los items ACTIVE con select.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

RUTA_REGISTROS = _ROOT / "registros"
RUTA_SNAPSHOT = RUTA_REGISTROS / "decisiones_dorado.json"

# OptionType legibles (cg/api.py).
_TIPOS = {0: "NUM", 1: "SI", 2: "NO", 3: "CARTA", 4: "TOOL", 5: "ECARD",
          6: "ENERGIA", 7: "PLAY", 8: "ATTACH", 9: "EVOLVE", 10: "ABILITY",
          11: "DISCARD", 12: "RETREAT", 13: "ATTACK", 14: "END", 15: "SKILL",
          16: "COND"}


def _main_mod():
    os.chdir(_ROOT)  # main.py abre deck.csv con ruta relativa
    import main as m
    return m


def reset_agente(m):
    """Espejo del fixture autouse `reset_main_state` de tests/test_main.py."""
    m._init_cartas_tracking()
    m._cartas_first_scan_done = False
    m._cartas_prizes_identified = False
    m._cartas_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1


def _nombre(m, cid):
    data = m.card_table.get(cid)
    return f"{data.name}({cid})" if data is not None else str(cid)


def describir_opcion(m, obs, idx):
    """Etiqueta legible de la opcion `idx` del select de `obs`."""
    sel = obs["select"]
    if idx >= len(sel["option"]):
        return f"?idx{idx}"
    o = sel["option"][idx]
    t = o.get("type")
    etiqueta = _TIPOS.get(t, f"t{t}")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    try:
        if t == 7:  # PLAY: index sobre la mano
            return f"PLAY {_nombre(m, me['hand'][o['index']]['id'])}"
        if t == 3:  # CARTA: index sobre area (mazo visible, mano, campo...)
            area = o.get("area")
            if area == 1 and sel.get("deck"):
                return f"CARTA {_nombre(m, sel['deck'][o['index']]['id'])}"
            if area == 2 and me.get("hand"):
                return f"CARTA {_nombre(m, me['hand'][o['index']]['id'])}"
            jugador = obs["current"]["players"][o.get("playerIndex", 0)]
            if area == 4 and jugador["active"]:
                return f"CARTA {_nombre(m, jugador['active'][0]['id'])}"
            if area == 5:
                return f"CARTA {_nombre(m, jugador['bench'][o['index']]['id'])}"
            return f"CARTA a{area} i{o.get('index')}"
        if t == 8:  # ATTACH: objetivo en juego
            if o.get("inPlayArea") == 4:
                return f"ATTACH->{_nombre(m, me['active'][0]['id'])}"
            return f"ATTACH->{_nombre(m, me['bench'][o['inPlayIndex']]['id'])}"
        if t == 10:  # ABILITY
            if o.get("area") == 4:
                return f"ABILITY {_nombre(m, me['active'][0]['id'])}"
            return f"ABILITY {_nombre(m, me['bench'][o['index']]['id'])}"
        if t == 13:
            return f"ATTACK id{o.get('attackId')}"
    except (IndexError, KeyError, TypeError):
        return f"{etiqueta} (irresoluble)"
    return etiqueta


def reproducir_registro(m, ruta):
    """Reproduce un registro desde frio y devuelve sus decisiones."""
    with open(ruta, encoding="utf-8") as f:
        data = json.load(f)
    reset_agente(m)
    decisiones = []
    for step in data.get("steps", []):
        item = step[0]
        obs = item.get("observation") or {}
        if item.get("status") != "ACTIVE" or not obs.get("select"):
            continue
        eleccion = m.agent(obs)
        decisiones.append({
            "paso": obs.get("step"),
            "contexto": obs["select"].get("context"),
            "eleccion": list(eleccion),
            "detalle": [describir_opcion(m, obs, i) for i in eleccion],
        })
    return decisiones


def _md5(ruta):
    return hashlib.md5(Path(ruta).read_bytes()).hexdigest()


def archivos_registro():
    return sorted(p for p in RUTA_REGISTROS.glob("registro_*.json"))


def generar_corpus():
    m = _main_mod()
    corpus = {}
    for ruta in archivos_registro():
        corpus[ruta.name] = {
            "md5": _md5(ruta),
            "decisiones": reproducir_registro(m, ruta),
        }
    return corpus


def cargar_snapshot():
    if not RUTA_SNAPSHOT.exists():
        return None
    with open(RUTA_SNAPSHOT, encoding="utf-8") as f:
        return json.load(f)


def guardar_snapshot(corpus):
    with open(RUTA_SNAPSHOT, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1, sort_keys=True)


def comparar(dorado, actual):
    """Devuelve (registros_cambiados, faltantes, nuevos, flips).

    flips: lista de dicts con archivo/paso/dorado/actual, SOLO de archivos
    cuyo md5 coincide (mismos datos, decisiones distintas => cambio de codigo).
    """
    cambiados, flips = [], []
    faltantes = sorted(set(dorado) - set(actual))
    nuevos = sorted(set(actual) - set(dorado))
    for nombre in sorted(set(dorado) & set(actual)):
        oro, hoy = dorado[nombre], actual[nombre]
        if oro["md5"] != hoy["md5"]:
            cambiados.append(nombre)
            continue
        for d_oro, d_hoy in zip(oro["decisiones"], hoy["decisiones"]):
            if d_oro["eleccion"] != d_hoy["eleccion"]:
                flips.append({
                    "archivo": nombre,
                    "paso": d_oro["paso"],
                    "dorado": f"{d_oro['eleccion']} {d_oro['detalle']}",
                    "actual": f"{d_hoy['eleccion']} {d_hoy['detalle']}",
                })
    return cambiados, faltantes, nuevos, flips


def formatear_flips(flips):
    lineas = []
    for f in flips:
        lineas.append(f"  {f['archivo']} paso {f['paso']}:")
        lineas.append(f"    dorado: {f['dorado']}")
        lineas.append(f"    actual: {f['actual']}")
    return "\n".join(lineas)


def main(argv):
    actualizar = "--actualizar" in argv
    actual = generar_corpus()
    dorado = cargar_snapshot()

    if dorado is None:
        guardar_snapshot(actual)
        n = sum(len(v["decisiones"]) for v in actual.values())
        print(f"Snapshot inicial creado: {RUTA_SNAPSHOT.name} "
              f"({len(actual)} registros, {n} decisiones)")
        return 0

    cambiados, faltantes, nuevos, flips = comparar(dorado, actual)

    if cambiados or faltantes or nuevos:
        print("Registros cambiados en disco (datos nuevos, no es un flip):")
        for n in cambiados:
            print(f"  ~ {n}")
        for n in faltantes:
            print(f"  - {n} (ya no existe)")
        for n in nuevos:
            print(f"  + {n} (nuevo)")
    if flips:
        print("DECISIONES VOLTEADAS con los mismos registros "
              "(cambio de codigo):")
        print(formatear_flips(flips))
    if not (cambiados or faltantes or nuevos or flips):
        print("Corpus dorado: sin cambios.")
        return 0

    if actualizar:
        guardar_snapshot(actual)
        print(f"\nSnapshot actualizado: {RUTA_SNAPSHOT}")
        return 0
    print("\n(usa --actualizar para aceptar estos cambios)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
