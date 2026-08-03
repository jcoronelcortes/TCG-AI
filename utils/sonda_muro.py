"""Sonda POR TURNO del atasco detras del muro inmune-a-ex (Crustle/Sylveon).

El censo de `utils/autopsia.py` dejo el matchup Crustle localizado pero no
resuelto: en las derrotas el 64.3% de los turnos se cierran SIN ATACAR (41.7%
en las victorias). Esta sonda responde la pregunta siguiente, que es la que
decide la FORMA del arreglo:

    en los turnos que EMPIEZAN con nuestro ex bloqueado por el muro y con una
    respuesta no-ex ya cargada en la banca, ¿como acaba el turno?

Se mide POR TURNO y no por select a proposito. Un turno normal encadena varios
selects (adjuntar, jugar un supporter y LUEGO retirar), asi que contar selects
mete en el saco de "no hizo nada" a las jugadas intermedias de un turno que si
acabo pivotando: un primer intento conto 85 de 113 "otra cosa" y ese numero era
un artefacto, no un hallazgo.

Los turnos que acaban EN SECO se vuelcan (observacion completa del primer MAIN,
formato de los fixtures de tests/) en registros/sonda_muro/ para poder
reproducir la decision con main.agent() y leer que puntuo por encima del relevo.

Uso:
    python utils/sonda_muro.py --rival deck/rivales_reales/crustle_wall_2.csv
    python utils/sonda_muro.py --rival ... --partidas 80 --volcar 15
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

import selfplay as sp
from bot_rival import BotRival
from cg.api import OptionType, SelectContext

# Atacantes no-ex que SI danan al muro (nuestros ex le hacen 0).
def _respuesta_ids(m):
    return {m.Tapu_Bulu, m.Meganium, m.Dipplin}


def _es_main(obs):
    return (obs.get("select") or {}).get("context") == int(SelectContext.MAIN)


def _tipo_elegido(obs, eleccion):
    try:
        return ((obs.get("select") or {}).get("option") or [])[eleccion[0]].get("type")
    except (IndexError, TypeError, KeyError):
        return None


def _califica(m, obs, asiento):
    """¿Este turno empieza con el ex bloqueado y la respuesta lista en banca?"""
    cur = obs["current"]
    yo = cur["players"][asiento]
    op = cur["players"][1 - asiento]
    act = (yo.get("active") or [None])[0]
    oact = (op.get("active") or [None])[0]
    if not act or not oact:
        return False
    if oact.get("id") not in m.EX_IMMUNE_IDS:
        return False
    if act.get("id") not in m.OUR_EX_IDS:
        return False
    respuestas = _respuesta_ids(m)
    for b in (yo.get("bench") or []):
        if not b or b.get("id") not in respuestas:
            continue
        req = m.ATTACK_ENERGY_REQ.get(b["id"]) or 99
        if len(b.get("energies") or []) * m._grass_mult() >= req:
            return True
    return False


def jugar(m, deck_rival, partidas, volcar, destino):
    from cg import game

    resumen = Counter()
    secos = []
    for i in range(partidas):
        asiento = i % 2
        d0 = sp.leer_deck() if asiento == 0 else deck_rival
        d1 = deck_rival if asiento == 0 else sp.leer_deck()
        obs, sd = game.battle_start(list(d0), list(d1))
        if obs is None:
            continue
        agentes = {asiento: m, 1 - asiento: BotRival()}
        pasos = 0
        turno_actual = None
        estado = None  # dict del turno en curso, si califica
        try:
            while obs["current"]["result"] == -1 and pasos < 3000:
                yi = obs["current"]["yourIndex"]
                turno = obs["current"]["turn"]
                if yi == asiento and _es_main(obs):
                    if turno != turno_actual:
                        # Cierra el turno anterior antes de abrir el nuevo.
                        if estado is not None:
                            resumen[estado["desenlace"]] += 1
                            if estado["desenlace"] == "seco" and len(secos) < volcar:
                                secos.append(estado["obs"])
                        turno_actual = turno
                        estado = ({"desenlace": "seco", "obs": obs}
                                  if _califica(m, obs, asiento) else None)
                try:
                    eleccion = agentes[yi].agent(obs)
                except Exception:
                    break
                if estado is not None and yi == asiento and _es_main(obs):
                    t = _tipo_elegido(obs, eleccion)
                    if t == int(OptionType.ATTACK):
                        estado["desenlace"] = "ataca"
                    elif t == int(OptionType.RETREAT) and estado["desenlace"] == "seco":
                        # Retirar es el pivote; si luego ataca, "ataca" manda.
                        estado["desenlace"] = "retira"
                try:
                    obs = game.battle_select(eleccion)
                except Exception:
                    break
                pasos += 1
            if estado is not None:
                resumen[estado["desenlace"]] += 1
                if estado["desenlace"] == "seco" and len(secos) < volcar:
                    secos.append(estado["obs"])
        finally:
            game.battle_finish()

    if secos:
        destino.mkdir(parents=True, exist_ok=True)
        for n, o in enumerate(secos, start=1):
            (destino / f"seco_{n:03d}.json").write_text(
                json.dumps({"observation": o}, ensure_ascii=False), encoding="utf-8")
    return resumen, len(secos)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rival", default=str(_ROOT / "deck" / "rivales_reales"
                                           / "crustle_wall_2.csv"))
    ap.add_argument("--partidas", type=int, default=60)
    ap.add_argument("--volcar", type=int, default=12,
                    help="cuantos turnos SECOS volcar a disco (0 = ninguno)")
    ap.add_argument("--destino", default=str(_ROOT / "registros" / "sonda_muro"))
    args = ap.parse_args(argv)

    import main as m
    deck_rival = sp.leer_deck(args.rival)
    resumen, n_secos = jugar(m, deck_rival, args.partidas, args.volcar,
                             Path(args.destino))

    total = sum(resumen.values())
    print(f"rival={Path(args.rival).stem}  partidas={args.partidas}")
    print(f"turnos que EMPIEZAN atascados tras el muro con respuesta lista: {total}")
    if not total:
        print("  (ninguno: el estado no se dio, no hay nada que concluir)")
        return 0
    for k in ("ataca", "retira", "seco"):
        v = resumen.get(k, 0)
        print(f"  {k:<7} {v:4d}  ({100 * v / total:5.1f}%)")
    if n_secos:
        print(f"\nvolcados {n_secos} turnos secos en {args.destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
