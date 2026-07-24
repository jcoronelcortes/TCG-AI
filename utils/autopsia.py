"""Autopsia automatica de DERROTAS del self-play.

Fase 6 de la arquitectura de mejora de estrategia. El self-play (fase 3) solo
devuelve un winrate; las partidas perdidas se tiraban -- y son exactamente el
material del que salen las reglas nuevas. Esta pieza juega N partidas contra
un mazo rival (bot generico) o en espejo, GRABA el flujo de decisiones de las
derrotas y les pasa DETECTORES post-hoc que reutilizan las calculadoras del
propio agente (main._attacker_base_damage / main._our_effective_damage):

  - letal_perdido: en un select MAIN habia un ataque del ACTIVO que noqueaba
    al activo rival, y el turno se cerro sin atacar (END/RETREAT). Se marca
    CRITICO si ademas ese KO cobraba los premios que nos faltaban (perdimos
    una partida GANADA).
  - turno_esteril: un turno completo cerrado con END o con un ataque de 0 de
    dano teniendo >= 4 cartas en la mano (la clase del paso 61 vs Dragapult).

Cada hallazgo se escribe como JSON con la OBSERVACION completa del paso (el
formato de los fixtures de tests/) en registros/autopsia/ (git-ignored, datos
locales transitorios): listo para reproducir con main.agent(), convertir en
fixture o barrer con el StateBuilder.

Uso:
    python utils/autopsia.py --rival deck/rivales/cornerstone_cubchoo.csv --partidas 100
    python utils/autopsia.py --espejo --partidas 100
    python utils/autopsia.py --todos --partidas 60   # todos los mazos de deck/rivales/
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp
from cg.api import OptionType, SelectContext

MAX_PASOS = 3000
MANO_MINIMA_ESTERIL = 4


def jugar_grabando(agente, rival, deck_propio, deck_rival, asiento):
    """Juega una partida grabando NUESTRAS decisiones.

    Devuelve (resultado, decisiones) con resultado en {"gana", "pierde",
    "limite", "forfeit"} y decisiones = [{obs, eleccion, paso}].
    """
    from cg import game

    sp._reset_si_aplica(agente)
    sp._reset_si_aplica(rival)
    decks = ((deck_propio, deck_rival) if asiento == 0
             else (deck_rival, deck_propio))
    obs, sd = game.battle_start(list(decks[0]), list(decks[1]))
    if obs is None:
        raise RuntimeError(f"battle_start fallo: {sd.errorType}")
    agentes = {asiento: agente, 1 - asiento: rival}
    decisiones, pasos = [], 0
    try:
        while obs["current"]["result"] == -1 and pasos < MAX_PASOS:
            yi = obs["current"]["yourIndex"]
            try:
                eleccion = agentes[yi].agent(obs)
            except Exception:
                return ("forfeit" if yi == asiento else "gana"), decisiones
            if yi == asiento:
                decisiones.append({"obs": obs, "eleccion": list(eleccion),
                                   "paso": pasos})
            obs = game.battle_select(eleccion)
            pasos += 1
        if obs["current"]["result"] == -1:
            return "limite", decisiones
        return ("gana" if obs["current"]["result"] == asiento
                else "pierde"), decisiones
    finally:
        game.battle_finish()


# --------------------------------------------------------------------------
# Detectores. Reciben las decisiones de UNA partida perdida y devuelven
# hallazgos: {detector, paso, turno, detalle, obs, eleccion}.
# --------------------------------------------------------------------------

def _mi_lado(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]], cur["players"][1 - cur["yourIndex"]]


def _dano_letal_activo(m, obs):
    """Mejor dano de NUESTRO activo al activo rival este paso (o 0)."""
    yo, op = _mi_lado(obs)
    if not (yo.get("active") and yo["active"][0] and
            op.get("active") and op["active"][0]):
        return 0, None
    act, opa = yo["active"][0], op["active"][0]
    e = len(act.get("energies") or [])
    total_grass = 0
    for p in [yo["active"][0]] + list(yo.get("bench") or []):
        if p:
            total_grass += len(p.get("energies") or [])
    bench_n = sum(1 for b in (yo.get("bench") or []) if b)

    class _P:  # adaptador minimo para las calculadoras de main
        def __init__(self, d):
            self.id = d["id"]
            self.hp = d.get("hp")
            self.energies = list(d.get("energies") or [])

            class _C:
                def __init__(self, dd):
                    self.id = dd["id"]
            self.energyCards = [_C(c) for c in (d.get("energyCards") or [])]
            self.tools = [_C(c) for c in (d.get("tools") or [])]

    a, o = _P(act), _P(opa)
    base = m._attacker_base_damage(a.id, o, e, grass_scale=total_grass,
                                   teal_self_energy=e, bench_count=bench_n)
    if base <= 0:
        return 0, o
    meganium = any(p and p["id"] == m.Meganium
                   for p in [yo["active"][0]] + list(yo.get("bench") or []))
    return m._our_effective_damage(a, o, base, meganium, False), o


def detectar(m, decisiones):
    hallazgos = []

    # agrupar decisiones por turno propio
    por_turno = {}
    for d in decisiones:
        por_turno.setdefault(d["obs"]["current"]["turn"], []).append(d)

    for turno, ds in sorted(por_turno.items()):
        mains = [d for d in ds
                 if (d["obs"].get("select") or {}).get("context")
                 == int(SelectContext.MAIN)]
        if not mains:
            continue

        # --- letal_perdido: hubo un paso con KO disponible del activo y el
        # turno se cerro sin ATACAR.
        ataco = any(
            int(d["obs"]["select"]["option"][d["eleccion"][0]].get("type", -1))
            == int(OptionType.ATTACK)
            for d in mains if d["eleccion"])
        if not ataco:
            for d in mains:
                opciones = d["obs"]["select"]["option"]
                if not any(int(o.get("type", -1)) == int(OptionType.ATTACK)
                           for o in opciones):
                    continue
                dano, opa = _dano_letal_activo(m, d["obs"])
                if opa is None or dano <= 0:
                    continue
                if dano >= (opa.hp or 0) > 0:
                    yo, _ = _mi_lado(d["obs"])
                    mis_premios = sum(1 for p in yo.get("prize") or []
                                      if p is None)
                    gana = m.prize_count(opa) >= mis_premios
                    hallazgos.append({
                        "detector": "letal_perdido",
                        "critico": bool(gana),
                        "turno": turno, "paso": d["paso"],
                        "detalle": (f"KO disponible ({dano} >= "
                                    f"{opa.hp}) y el turno cerro "
                                    f"sin atacar"),
                        "eleccion": d["eleccion"],
                        "observation": d["obs"],
                    })
                    break

        # --- turno_esteril: cierre con END o ataque de dano 0 con mano gorda.
        ultimo = mains[-1]
        if not ultimo["eleccion"]:
            continue
        opcion = ultimo["obs"]["select"]["option"][ultimo["eleccion"][0]]
        t = int(opcion.get("type", -1))
        yo, _ = _mi_lado(ultimo["obs"])
        mano = len(yo.get("hand") or [])
        esteril = False
        if t == int(OptionType.END) and mano >= MANO_MINIMA_ESTERIL:
            esteril = True
        elif t == int(OptionType.ATTACK) and mano >= MANO_MINIMA_ESTERIL:
            atk = m.attack_table.get(opcion.get("attackId"))
            dano, _opa = _dano_letal_activo(m, ultimo["obs"])
            if atk is not None and (atk.damage or 0) == 0 and dano == 0:
                esteril = True
        if esteril:
            hallazgos.append({
                "detector": "turno_esteril",
                "critico": False,
                "turno": turno, "paso": ultimo["paso"],
                "detalle": (f"turno cerrado con "
                            f"{'END' if t == int(OptionType.END) else 'ataque de 0'}"
                            f" y {mano} cartas en mano"),
                "eleccion": ultimo["eleccion"],
                "observation": ultimo["obs"],
            })
    return hallazgos


def autopsia(rival_csv, partidas, espejo=False, destino=None):
    import main as m
    destino = destino or (_ROOT / "registros" / "autopsia")
    destino.mkdir(parents=True, exist_ok=True)

    agente = sp.cargar_agente(_ROOT / "main.py", "agente_autopsia")
    deck_propio = sp.leer_deck()
    if espejo:
        rival = sp.cargar_agente(_ROOT / "main.py", "rival_autopsia")
        deck_rival, etiqueta = deck_propio, "espejo"
    else:
        from bot_rival import BotRival
        rival = BotRival()
        deck_rival = sp.leer_deck(rival_csv)
        etiqueta = Path(rival_csv).stem

    marcador = Counter()
    total_hallazgos = []
    for i in range(partidas):
        resultado, decisiones = jugar_grabando(
            agente, rival, deck_propio, deck_rival, asiento=i % 2)
        marcador[resultado] += 1
        if resultado not in ("pierde", "forfeit"):
            continue
        for h in detectar(m, decisiones):
            h["partida"] = i
            h["rival"] = etiqueta
            h["resultado"] = resultado
            total_hallazgos.append(h)

    # persistir: un archivo por partida con hallazgos
    por_partida = {}
    for h in total_hallazgos:
        por_partida.setdefault(h["partida"], []).append(h)
    for num, hs in por_partida.items():
        ruta = destino / f"{etiqueta}_p{num:03d}.json"
        ruta.write_text(json.dumps(
            {"rival": etiqueta, "partida": num, "hallazgos": hs},
            ensure_ascii=False, indent=1))

    print(f"[{etiqueta}] {dict(marcador)}")
    resumen = Counter((h["detector"], h["critico"]) for h in total_hallazgos)
    for (det, critico), n in resumen.most_common():
        print(f"  {det}{' CRITICO' if critico else ''}: {n} "
              f"(en {len(por_partida)} partidas perdidas)")
    if not total_hallazgos:
        print("  sin hallazgos en las derrotas")
    return total_hallazgos


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rival", default=None, help="csv del mazo rival")
    ap.add_argument("--espejo", action="store_true")
    ap.add_argument("--todos", action="store_true",
                    help="autopsia contra todos los mazos de deck/rivales/")
    ap.add_argument("--partidas", type=int, default=100)
    args = ap.parse_args(argv)

    if args.todos:
        for ruta in sorted((_ROOT / "deck" / "rivales").glob("*.csv")):
            autopsia(ruta, args.partidas)
        return 0
    if args.espejo:
        autopsia(None, args.partidas, espejo=True)
        return 0
    if not args.rival:
        print("indica --rival, --espejo o --todos")
        return 1
    autopsia(args.rival, args.partidas)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
