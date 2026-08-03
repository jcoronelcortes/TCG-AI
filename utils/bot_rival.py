"""Bot rival generico: pilota CUALQUIER mazo de forma legal y consistente.

No es un buen jugador y no lo pretende: es el RIVAL DE REFERENCIA del modo
--rival de utils/selfplay.py. Al ser fijo y deterministico en sus reglas
(greedy simple), permite comparar dos versiones de main.py por su winrate
contra el MISMO oponente pilotando el MISMO mazo: el delta entre versiones
es la senal, no el nivel absoluto del bot.

Politica:
  - Menu principal: ATTACH > EVOLVE > PLAY > ABILITY > RETREAT (solo si el
    activo NO puede atacar) > ATTACK > END.
  - ATTACH: al ACTIVO, salvo que el activo ya tenga energia y haya en juego un
    Pokemon con una HABILIDAD CONDICIONADA A ENERGIA y ninguna adjunta -- ese
    va primero, porque sin esa energia su habilidad no existe.
  - EVOLVE: primero la evolucion de MAYOR etapa (Fase 2 antes que Fase 1) y,
    a igualdad, la del ACTIVO. Es lo que saca el atacante grande a tiempo.
  - ABILITY: como mucho UNA VEZ por Pokemon y por turno, con tope duro por
    turno (anti-bucle: el motivo por el que el bot no las usaba).
  - RETREAT: solo cuando el activo no tiene NINGUN ataque disponible y hay
    banca. Sin esto un cuerpo gusteado se quedaba clavado delante para siempre
    y cualquier gusteo rival, aunque no rematara, ganaba la partida sola.
  - ATTACK: el de mayor dano EFECTIVO contra el defensor (debilidad x2), no el
    de mayor dano impreso.
  - Mover/poner contadores de dano (Adrena-Brain de Munkidori y familia):
    origen = el cuerpo PROPIO mas danado, cantidad = la MAXIMA ofrecida,
    destino = el cuerpo rival que MUERE con esos contadores (a mas premios,
    mejor) y, si ninguno muere, el de MENOS vida.
  - Elegir ACTIVO propio (promocion tras KO, destino de retirada): el de mayor
    dano POTENCIAL contra el activo rival (ignorando el coste, porque la
    politica de ATTACH carga al activo y el atacante recien subido se carga
    solo); desempata el dano que YA puede pagar, luego energia y vida.
  - Objetivo de GUSTEO (Boss's y familia: un SWITCH sobre la banca RIVAL): el
    que puede NOQUEAR, a mas premios mejor; si ninguno, el de menos vida.
  - Si/No: SI, salvo mulligan y "seguir devolucionando" (NO).
  - Cualquier otro select: las primeras `minCount` opciones (o la primera
    si el minimo es 0): eleccion siempre legal.

NOTA DE MEDICION (user, registros/marnie): hasta 2026-08-02 el bot NO usaba
habilidades ("simplicidad y cero riesgo de bucles"). Eso hacia el harness
CIEGO a mazos cuyo motor ES una habilidad: contra Marnie's Grimmsnarl ex el
bot no activaba nunca Adrena-Brain de Munkidori, que en las partidas reales
cobro 5 de los 7 premios que el rival gano SIN ATACAR. Cualquier regla nuestra
contra ese motor medida con el bot viejo salia NEUTRA por construccion.
El nivel absoluto del bot cambia con esto; los DELTAS entre versiones de
main.py siguen siendo comparables (ambos lados juegan contra el mismo bot),
pero los winrates absolutos historicos ya NO son comparables con los nuevos.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cg.api import (AreaType, OptionType, SelectContext, all_attack,
                    all_card_data)

# Tope duro de activaciones de habilidad por turno. No hay ninguna carta que
# necesite tantas: es el cinturon anti-bucle, no una regla de juego.
MAX_HABILIDADES_POR_TURNO = 8
# Dano por contador de dano.
DANO_POR_CONTADOR = 10


class BotRival:

    def __init__(self):
        self._ataques = {a.attackId: a for a in all_attack()}
        self._dano = {a.attackId: a.damage for a in all_attack()}
        self._cartas = {c.cardId: c for c in all_card_data()}
        self._turno = None
        self._habilidades_usadas = set()
        self._activaciones = 0
        # Contadores que el efecto en curso va a mover/poner (se fija en el
        # select de CANTIDAD y lo consume el select de DESTINO).
        self._contadores = 1

    # -- utilidades ---------------------------------------------------------

    def _reset_turno(self, turno):
        self._turno = turno
        self._habilidades_usadas = set()
        self._activaciones = 0
        self._contadores = 1

    def _pokemon_de(self, obs, opcion, indice_propio=None):
        """Pokemon al que apunta `opcion`, o None si la opcion no senala uno."""
        cur = obs.get("current") or {}
        jugadores = cur.get("players") or []
        pi = opcion.get("playerIndex")
        if pi is None:
            pi = indice_propio
        if pi is None or pi >= len(jugadores):
            return None
        jugador = jugadores[pi] or {}
        area = opcion.get("area")
        idx = opcion.get("index") or 0
        try:
            if area == int(AreaType.ACTIVE):
                pk = (jugador.get("active") or [None])[0]
            elif area == int(AreaType.BENCH):
                pk = (jugador.get("bench") or [])[idx]
            else:
                return None
        except (IndexError, TypeError):
            return None
        if isinstance(pk, list):
            pk = pk[0] if pk else None
        return pk if isinstance(pk, dict) else None

    def _premios(self, pk):
        data = self._cartas.get((pk or {}).get("id"))
        if data is None:
            return 1
        return 3 if data.megaEx else 2 if data.ex else 1

    def _dano_encajado(self, pk):
        if not pk:
            return -1
        return max(0, (pk.get("maxHp") or 0) - (pk.get("hp") or 0))

    def _dano_efectivo(self, atacante, defensor, attack_id):
        """Dano impreso del ataque, x2 si el defensor es debil al tipo del
        atacante. Aproximado a proposito: los ataques que escalan (Syrup Storm,
        Myriad Leaf Shower) declaran su base, no su dano real."""
        base = self._dano.get(attack_id) or 0
        if base <= 0 or not atacante or not defensor:
            return base
        atk = self._cartas.get(atacante.get("id"))
        dfd = self._cartas.get(defensor.get("id"))
        if atk is None or dfd is None:
            return base
        if dfd.weakness is not None and dfd.weakness == atk.energyType:
            return base * 2
        return base

    def _mejor_dano_de(self, atacante, defensor):
        """Mejor dano efectivo que `atacante` puede hacerle a `defensor` con
        cualquiera de sus ataques (sin mirar si puede pagar el coste)."""
        data = self._cartas.get((atacante or {}).get("id"))
        if data is None:
            return 0
        return max((self._dano_efectivo(atacante, defensor, aid)
                    for aid in (data.attacks or ())), default=0)

    def _dano_pagable_de(self, atacante, defensor):
        """Como `_mejor_dano_de`, pero solo con los ataques que YA puede pagar."""
        data = self._cartas.get((atacante or {}).get("id"))
        if data is None:
            return 0
        disponibles = len((atacante or {}).get("energies") or [])
        mejor = 0
        for aid in (data.attacks or ()):
            atk = self._ataques.get(aid)
            if atk is None:
                continue
            if len(getattr(atk, "energies", None) or []) > disponibles:
                continue
            mejor = max(mejor, self._dano_efectivo(atacante, defensor, aid))
        return mejor

    def _habilidad_pide_energia(self, card_id):
        """La habilidad de la carta esta CONDICIONADA a llevar energia."""
        data = self._cartas.get(card_id)
        for skill in getattr(data, "skills", None) or ():
            if "Energy attached" in (getattr(skill, "text", "") or ""):
                return True
        return False

    # -- despacho -----------------------------------------------------------

    def agent(self, obs):
        sel = obs.get("select") or {}
        opciones = sel.get("option") or []
        if not opciones:
            return []
        cur = obs.get("current") or {}
        if cur.get("turn") != self._turno:
            self._reset_turno(cur.get("turn"))
        contexto = sel.get("context")

        if contexto == int(SelectContext.MAIN):
            return self._menu_principal(obs, opciones)

        if contexto in (int(SelectContext.REMOVE_DAMAGE_COUNTER_COUNT),
                        int(SelectContext.DAMAGE_COUNTER_COUNT)):
            return self._cuantos_contadores(opciones)

        if contexto == int(SelectContext.REMOVE_DAMAGE_COUNTER):
            return self._origen_de_contadores(obs, opciones, sel)

        if contexto in (int(SelectContext.DAMAGE_COUNTER),
                        int(SelectContext.DAMAGE_COUNTER_ANY)):
            return self._destino_de_contadores(obs, opciones, sel)

        if contexto in (int(SelectContext.SWITCH),
                        int(SelectContext.TO_ACTIVE)):
            return self._elegir_activo(obs, opciones, sel)

        tipos = {o.get("type") for o in opciones}
        if int(OptionType.YES) in tipos or int(OptionType.NO) in tipos:
            return self._si_no(contexto, opciones)

        minimo = sel.get("minCount") or 0
        k = minimo if minimo > 0 else min(1, sel.get("maxCount") or 1)
        k = min(k, len(opciones))
        return list(range(k))

    # -- menu principal -----------------------------------------------------

    def _menu_principal(self, obs, opciones):
        por_tipo = {}
        for i, o in enumerate(opciones):
            por_tipo.setdefault(o.get("type"), []).append(i)

        adjuntes = por_tipo.get(int(OptionType.ATTACH))
        if adjuntes:
            return [self._mejor_adjunte(obs, opciones, adjuntes)]

        evoluciones = por_tipo.get(int(OptionType.EVOLVE))
        if evoluciones:
            return [self._mejor_evolucion(obs, opciones, evoluciones)]

        jugadas = por_tipo.get(int(OptionType.PLAY))
        if jugadas:
            return [jugadas[0]]

        habilidad = self._elegir_habilidad(por_tipo.get(int(OptionType.ABILITY)),
                                           opciones)
        if habilidad is not None:
            return [habilidad]

        ataques = por_tipo.get(int(OptionType.ATTACK))

        # Sin ataque disponible, RETIRARSE es lo unico que cambia algo: un
        # cuerpo que no pega clavado en el activo pierde la partida solo.
        retiradas = por_tipo.get(int(OptionType.RETREAT))
        if not ataques and retiradas:
            return [retiradas[0]]

        # RELEVO hacia el mejor atacante: PROBADO Y DESCARTADO (ago 2026).
        # Con Munkidori clavado de activo el 43% de los pasos parecia el paso
        # natural, pero retirar DESCARTA la energia adjunta: el bot se
        # desangraba y llegaba menos veces a atacar. Medido sobre la lista
        # Marnie dominante, empeoraba justo lo que pretendia arreglar --
        # premios del bot 1.20 -> 0.35, Grimmsnarl ex activo 24.6% -> 13.1% --
        # y nuestro winrate volvia a subir de 90.0% a 95.0%. Si alguien lo
        # retoma: el coste de la retirada tiene que entrar en la cuenta, no
        # basta con comparar dano.

        if ataques:
            cur = obs.get("current") or {}
            yo = cur.get("yourIndex", 0)
            jugadores = cur.get("players") or []
            mi_activo = None
            su_activo = None
            if len(jugadores) > max(yo, 1 - yo):
                mi_activo = ((jugadores[yo] or {}).get("active") or [None])[0]
                su_activo = ((jugadores[1 - yo] or {}).get("active") or [None])[0]
            mejor = max(ataques, key=lambda i: self._dano_efectivo(
                mi_activo, su_activo, opciones[i].get("attackId")))
            return [mejor]

        fin = por_tipo.get(int(OptionType.END))
        if fin:
            return [fin[0]]
        return [0]

    def _mejor_evolucion(self, obs, opciones, indices):
        """La evolucion de MAYOR etapa primero y, a igualdad, la del ACTIVO."""
        def clave(i):
            o = opciones[i]
            data = self._cartas.get(self._id_en_mano(obs, o))
            etapa = 2 if getattr(data, "stage2", False) else \
                1 if getattr(data, "stage1", False) else 0
            al_activo = o.get("inPlayArea") == int(AreaType.ACTIVE)
            return (-etapa, 0 if al_activo else 1, i)
        return min(indices, key=clave)

    def _id_en_mano(self, obs, opcion):
        cur = obs.get("current") or {}
        yo = cur.get("yourIndex", 0)
        jugadores = cur.get("players") or []
        if yo >= len(jugadores):
            return None
        mano = (jugadores[yo] or {}).get("hand") or []
        idx = opcion.get("index")
        if opcion.get("area") != int(AreaType.HAND) or idx is None:
            return None
        try:
            return (mano[idx] or {}).get("id")
        except (IndexError, TypeError):
            return None

    def _mejor_adjunte(self, obs, opciones, adjuntes):
        """Al ACTIVO, salvo que ya tenga energia y haya un cuerpo con habilidad
        condicionada a energia todavia seco: ese motor va primero."""
        cur = obs.get("current") or {}
        yo = cur.get("yourIndex", 0)
        jugadores = cur.get("players") or []
        activo = None
        if yo < len(jugadores):
            activo = ((jugadores[yo] or {}).get("active") or [None])[0]
        al_activo = [i for i in adjuntes
                     if opciones[i].get("inPlayArea") == int(AreaType.ACTIVE)]

        if activo and len(activo.get("energies") or []) >= 1:
            for i in adjuntes:
                destino = self._pokemon_de(
                    obs,
                    {"area": opciones[i].get("inPlayArea"),
                     "index": opciones[i].get("inPlayIndex"),
                     "playerIndex": yo})
                if (destino and not (destino.get("energies") or [])
                        and self._habilidad_pide_energia(destino.get("id"))):
                    return i

        return al_activo[0] if al_activo else adjuntes[0]

    def _elegir_habilidad(self, indices, opciones):
        """Una activacion por Pokemon y por turno, con tope duro por turno."""
        if not indices or self._activaciones >= MAX_HABILIDADES_POR_TURNO:
            return None
        for i in indices:
            clave = (opciones[i].get("area"), opciones[i].get("index"))
            if clave in self._habilidades_usadas:
                continue
            self._habilidades_usadas.add(clave)
            self._activaciones += 1
            return i
        return None

    # -- contadores de dano -------------------------------------------------

    def _cuantos_contadores(self, opciones):
        """Siempre el MAXIMO: mover 1 de 3 desperdicia la habilidad."""
        mejor = max(range(len(opciones)),
                    key=lambda i: opciones[i].get("number") or 0)
        self._contadores = opciones[mejor].get("number") or 1
        return [mejor]

    def _origen_de_contadores(self, obs, opciones, sel):
        """De donde se quitan: el cuerpo PROPIO que mas dano lleva encima."""
        k = max(1, sel.get("minCount") or 1)
        orden = sorted(
            range(len(opciones)),
            key=lambda i: -self._dano_encajado(self._pokemon_de(obs, opciones[i])))
        return sorted(orden[:min(k, len(opciones))])

    def _destino_de_contadores(self, obs, opciones, sel):
        """Donde se ponen: el cuerpo RIVAL que muere con estos contadores (a
        mas premios, mejor) y, si ninguno muere, el de menos vida."""
        cur = obs.get("current") or {}
        yo = cur.get("yourIndex", 0)
        dano = DANO_POR_CONTADOR * max(1, self._contadores)

        rivales = [i for i in range(len(opciones))
                   if opciones[i].get("playerIndex") not in (None, yo)]
        candidatos = rivales or list(range(len(opciones)))

        def clave(i):
            pk = self._pokemon_de(obs, opciones[i], indice_propio=yo)
            if not pk:
                return (2, 0, 0)
            hp = pk.get("hp") or 0
            if i in rivales:
                # Primero los que MUEREN, y entre ellos los de mas premios.
                return (0 if hp <= dano else 1, -self._premios(pk), hp)
            # Si solo quedan cuerpos propios, el que menos duele: el mas sano.
            return (2, 0, -hp)

        k = max(1, sel.get("minCount") or 1)
        orden = sorted(candidatos, key=clave)
        return sorted(orden[:min(k, len(candidatos))])

    # -- quien pasa al puesto activo ----------------------------------------

    def _elegir_activo(self, obs, opciones, sel):
        """Dos casos con el mismo contexto:

        * opciones sobre NUESTRA banca -- promocion tras KO o destino de una
          retirada: sube el que mas energia lleva (proxy de "puede atacar") y,
          a igualdad, el de mas vida.
        * opciones sobre la banca RIVAL -- somos nosotros gusteando (Boss's y
          familia): sube el que podamos NOQUEAR, a mas premios mejor; si no
          hay KO, el de menos vida.
        """
        cur = obs.get("current") or {}
        yo = cur.get("yourIndex", 0)
        jugadores = cur.get("players") or []
        k = max(1, sel.get("minCount") or 1)

        rivales = [i for i in range(len(opciones))
                   if opciones[i].get("playerIndex") not in (None, yo)]
        if rivales:
            mi_activo = None
            if yo < len(jugadores):
                mi_activo = ((jugadores[yo] or {}).get("active") or [None])[0]

            def clave_gusteo(i):
                pk = self._pokemon_de(obs, opciones[i])
                if not pk:
                    return (2, 0, 0)
                hp = pk.get("hp") or 0
                muere = self._mejor_dano_de(mi_activo, pk) >= hp
                return (0 if muere else 1, -self._premios(pk), hp)

            orden = sorted(rivales, key=clave_gusteo)
            return sorted(orden[:min(k, len(rivales))])

        # ATACANTE primero, no "el que mas energia lleva". Medido pilotando la
        # lista Marnie dominante del meta: con el criterio de energia el bot
        # ponia delante a MUNKIDORI el 51.5% de sus pasos -- su motor de apoyo,
        # que lleva la Oscura para Adrena-Brain-- mientras Grimmsnarl ex, su
        # unico atacante real, solo estaba activo el 13.8%. Resultado: cobraba
        # 0 premios en 30 de 40 partidas (media 0.80) pese a montar el tablero
        # bien (Grimmsnarl ex en mesa el 83% de las partidas). El bot se
        # regalaba sus propias piezas de apoyo como cuerpo activo.
        #
        # Se ordena por dano POTENCIAL (ignorando el coste, como
        # `_mejor_dano_de`) y no por el pagable: la politica de ATTACH de este
        # bot carga al ACTIVO, asi que el atacante grande recien promovido se
        # carga solo en los turnos siguientes. El pagable-ahora queda de
        # desempate para no subir un cuerpo inerte teniendo uno listo.
        op_activo = None
        if (1 - yo) < len(jugadores):
            op_activo = ((jugadores[1 - yo] or {}).get("active") or [None])[0]

        def clave_propia(i):
            pk = self._pokemon_de(obs, opciones[i], indice_propio=yo)
            if not pk:
                return (0, 0, 0, 0)
            return (-self._mejor_dano_de(pk, op_activo),
                    -self._dano_pagable_de(pk, op_activo),
                    -len(pk.get("energies") or []),
                    -(pk.get("hp") or 0))

        orden = sorted(range(len(opciones)), key=clave_propia)
        return sorted(orden[:min(k, len(opciones))])

    # -- si / no ------------------------------------------------------------

    def _si_no(self, contexto, opciones):
        prefiere_no = contexto in (int(SelectContext.MULLIGAN),
                                   int(SelectContext.MORE_DEVOLVE))
        buscado = int(OptionType.NO) if prefiere_no else int(OptionType.YES)
        for i, o in enumerate(opciones):
            if o.get("type") == buscado:
                return [i]
        return [0]
