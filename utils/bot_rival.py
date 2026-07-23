"""Bot rival generico: pilota CUALQUIER mazo de forma legal y consistente.

No es un buen jugador y no lo pretende: es el RIVAL DE REFERENCIA del modo
--rival de utils/selfplay.py. Al ser fijo y deterministico en sus reglas
(greedy simple), permite comparar dos versiones de main.py por su winrate
contra el MISMO oponente pilotando el MISMO mazo: el delta entre versiones
es la senal, no el nivel absoluto del bot.

Politica:
  - Menu principal: ATTACH (prefiere el activo) > EVOLVE > PLAY > ATTACK
    (el de mayor dano impreso) > END. Nunca RETREAT ni ABILITY (simplicidad
    y cero riesgo de bucles).
  - Si/No: SI, salvo mulligan y "seguir devolucionando" (NO).
  - Cualquier otro select: las primeras `minCount` opciones (o la primera
    si el minimo es 0): eleccion siempre legal.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cg.api import OptionType, SelectContext, all_attack


class BotRival:

    def __init__(self):
        self._dano = {a.attackId: a.damage for a in all_attack()}

    def agent(self, obs):
        sel = obs.get("select") or {}
        opciones = sel.get("option") or []
        if not opciones:
            return []
        contexto = sel.get("context")

        if contexto == int(SelectContext.MAIN):
            return self._menu_principal(opciones)

        tipos = {o.get("type") for o in opciones}
        if int(OptionType.YES) in tipos or int(OptionType.NO) in tipos:
            return self._si_no(contexto, opciones)

        minimo = sel.get("minCount") or 0
        k = minimo if minimo > 0 else min(1, sel.get("maxCount") or 1)
        k = min(k, len(opciones))
        return list(range(k))

    def _menu_principal(self, opciones):
        por_tipo = {}
        for i, o in enumerate(opciones):
            por_tipo.setdefault(o.get("type"), []).append(i)

        adjuntes = por_tipo.get(int(OptionType.ATTACH))
        if adjuntes:
            al_activo = [i for i in adjuntes
                         if opciones[i].get("inPlayArea") == 4]
            return [al_activo[0] if al_activo else adjuntes[0]]

        evoluciones = por_tipo.get(int(OptionType.EVOLVE))
        if evoluciones:
            return [evoluciones[0]]

        jugadas = por_tipo.get(int(OptionType.PLAY))
        if jugadas:
            return [jugadas[0]]

        ataques = por_tipo.get(int(OptionType.ATTACK))
        if ataques:
            mejor = max(ataques, key=lambda i: self._dano.get(
                opciones[i].get("attackId"), 0))
            return [mejor]

        fin = por_tipo.get(int(OptionType.END))
        if fin:
            return [fin[0]]
        return [0]

    def _si_no(self, contexto, opciones):
        prefiere_no = contexto in (int(SelectContext.MULLIGAN),
                                   int(SelectContext.MORE_DEVOLVE))
        buscado = int(OptionType.NO) if prefiere_no else int(OptionType.YES)
        for i, o in enumerate(opciones):
            if o.get("type") == buscado:
                return [i]
        return [0]
