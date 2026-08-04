"""Generic opposing bot: it pilots ANY deck legally and consistently.

It is not a good player and does not try to be: it is the REFERENCE OPPONENT of the
--rival mode of utils/selfplay.py. Being fixed and deterministic in its rules
(a simple greedy), it makes it possible to compare two versions of main.py by their winrate
against the SAME opponent piloting the SAME deck: the delta between versions
is the signal, not the bot's absolute level.

Policy:
  - Main menu: ATTACH > EVOLVE > PLAY > ABILITY > RETREAT (only if the
    active canNOT attack) > ATTACK > END.
  - ATTACH: to the ACTIVE, unless the active already has energy and there is in play a
    Pokemon with an ABILITY CONDITIONED ON ENERGY and none attached -- that one
    goes first, because without that energy its ability does not exist.
  - EVOLVE: the HIGHEST stage evolution first (Stage 2 before Stage 1) and,
    on a tie, the ACTIVE's. That is what gets the big attacker out in time.
  - ABILITY: at most ONCE per Pokemon and per turn, with a hard per-turn
    cap (anti-loop: the reason the bot did not use them).
  - RETREAT: only when the active has NO attack available and there is a
    bench. Without this a gusted body stayed nailed in front forever
    and any opposing gust, even without finishing, won the game on its own.
  - ATTACK: the one with the highest EFFECTIVE damage against the defender (weakness x2), not
    the one with the highest printed damage.
  - Moving/placing damage counters (Munkidori's Adrena-Brain and family):
    source = the most damaged body of ITS OWN, amount = the MAXIMUM offered,
    destination = the opposing body that DIES with those counters (the more prizes,
    the better) and, if none dies, the one with the LEAST HP.
  - Choosing its own ACTIVE (a promotion after a KO, the destination of a retreat): the one carrying the most
    energy and, on a tie, the one with the most HP.
  - GUST target (Boss's and family: a SWITCH over the OPPOSING bench): the
    one it can KNOCK OUT, the more prizes the better; if none, the one with the least HP.
  - Yes/No: YES, except on a mulligan and "keep devolving" (NO).
  - Any other select: the first `minCount` options (or the first one
    if the minimum is 0): an always legal choice.

MEASUREMENT NOTE (user, registros/marnie): until 2026-08-02 the bot did NOT use
abilities ("simplicity and zero risk of loops"). That made the harness
BLIND to decks whose engine IS an ability: against Marnie's Grimmsnarl ex the
bot never activated Munkidori's Adrena-Brain, which in the real games
took 5 of the 7 prizes the opponent won WITHOUT ATTACKING. Any rule of ours
against that engine measured with the old bot came out NEUTRAL by construction.
The bot's absolute level changes with this; the DELTAS between versions of
main.py are still comparable (both sides play against the same bot),
but the historical absolute winrates are NO longer comparable with the new ones.

A KNOWN AND MEASURED DEFECT (Aug 2026), left in on purpose: piloting the
dominant Marnie list of the meta, the "the one carrying the most energy" promotion
brings MUNKIDORI up as the active in 51.5% of the steps -- it carries the Darkness because its
Adrena-Brain requires it, but that is a BENCH ability -- while
Grimmsnarl ex, its only attacker, is only in front 13.8% of the time. The bot takes
0.80 prizes on average (0 prizes in 30 of 40 games) despite building the
board well: it gets Grimmsnarl ex onto the field in 83% of the games.

Ordering the promotion by potential damage WAS TRIED and REVERTED. The bot plays
its engine better (Grimmsnarl active 13.8% -> 23.5%, prizes 0.80 -> 1.25), but
it does not buy what was wanted: against that list our winrate only drops from
96.8% to 96.0% -- it stays just as saturated -- and the meta-weighted number does not move
(94.0% -> 93.9%). In exchange it softens other matchups: ogerpon_verde_1 falls from
87.8% to 83.8%. Relieving towards the best benched attacker was also tried:
worse still, because retreating DISCARDS the energy and the bot bleeds out
(prizes 1.20 -> 0.35).

Conclusion for whoever picks this up: the saturation against Marnie does not come from the
promotion, but from the bot not chaining Froslass + Adrena-Brain like a
human (in the real records that deck takes 7 of 18 prizes WITHOUT attacking).
Closing that gap asks for a piloting routine specific to the archetype, not another generic
heuristic -- and that breaks the property that makes this bot useful: being THE SAME
for every deck. In the meantime, against Marnie the metric with resolution
is the PRIZE DIFFERENTIAL (+4.63 out of a possible 6), not the winrate.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cg.api import (AreaType, OptionType, SelectContext, all_attack,
                    all_card_data)

# Hard cap of ability activations per turn. There is no card that
# needs that many: it is the anti-loop belt, not a game rule.
MAX_HABILIDADES_POR_TURNO = 8
# Damage per damage counter.
DANO_POR_CONTADOR = 10


class BotRival:

    def __init__(self):
        self._ataques = {a.attackId: a for a in all_attack()}
        self._dano = {a.attackId: a.damage for a in all_attack()}
        self._cards = {c.cardId: c for c in all_card_data()}
        self._turno = None
        self._habilidades_usadas = set()
        self._activaciones = 0
        # Counters the current effect is going to move/place (it is set in the
        # AMOUNT select and consumed by the DESTINATION select).
        self._contadores = 1

    # -- utilities ----------------------------------------------------------

    def _reset_turno(self, turn):
        self._turno = turn
        self._habilidades_usadas = set()
        self._activaciones = 0
        self._contadores = 1

    def _pokemon_de(self, obs, opcion, indice_propio=None):
        """The Pokemon `opcion` points at, or None if the option does not point at one."""
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

    def _prizes(self, pk):
        data = self._cards.get((pk or {}).get("id"))
        if data is None:
            return 1
        return 3 if data.megaEx else 2 if data.ex else 1

    def _dano_encajado(self, pk):
        if not pk:
            return -1
        return max(0, (pk.get("maxHp") or 0) - (pk.get("hp") or 0))

    def _dano_efectivo(self, atacante, defensor, attack_id):
        """The attack's printed damage, x2 if the defender is weak to the
        attacker's type. Deliberately approximate: the attacks that scale (Syrup Storm,
        Myriad Leaf Shower) declare their base, not their real damage."""
        base = self._dano.get(attack_id) or 0
        if base <= 0 or not atacante or not defensor:
            return base
        atk = self._cards.get(atacante.get("id"))
        dfd = self._cards.get(defensor.get("id"))
        if atk is None or dfd is None:
            return base
        if dfd.weakness is not None and dfd.weakness == atk.energyType:
            return base * 2
        return base

    def _mejor_dano_de(self, atacante, defensor):
        """The best effective damage `atacante` can do to `defensor` with
        any of its attacks (without checking whether it can pay the cost)."""
        data = self._cards.get((atacante or {}).get("id"))
        if data is None:
            return 0
        return max((self._dano_efectivo(atacante, defensor, aid)
                    for aid in (data.attacks or ())), default=0)

    def _habilidad_pide_energia(self, card_id):
        """The card's ability is CONDITIONED on carrying energy."""
        data = self._cards.get(card_id)
        for skill in getattr(data, "skills", None) or ():
            if "Energy attached" in (getattr(skill, "text", "") or ""):
                return True
        return False

    # -- dispatch -----------------------------------------------------------

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

    # -- main menu ----------------------------------------------------------

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

        # With no attack available, RETREATING is the only thing that changes anything: a
        # body that does not hit, nailed in the active spot, loses the game on its own.
        retiradas = por_tipo.get(int(OptionType.RETREAT))
        if not ataques and retiradas:
            return [retiradas[0]]

        if ataques:
            cur = obs.get("current") or {}
            yo = cur.get("yourIndex", 0)
            jugadores = cur.get("players") or []
            mi_activo = None
            su_activo = None
            if len(jugadores) > max(yo, 1 - yo):
                mi_activo = ((jugadores[yo] or {}).get("active") or [None])[0]
                su_activo = ((jugadores[1 - yo] or {}).get("active") or [None])[0]
            best = max(ataques, key=lambda i: self._dano_efectivo(
                mi_activo, su_activo, opciones[i].get("attackId")))
            return [best]

        fin = por_tipo.get(int(OptionType.END))
        if fin:
            return [fin[0]]
        return [0]

    def _mejor_evolucion(self, obs, opciones, indices):
        """The HIGHEST stage evolution first and, on a tie, the ACTIVE's."""
        def clave(i):
            o = opciones[i]
            data = self._cards.get(self._id_en_mano(obs, o))
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
        """To the ACTIVE, unless it already has energy and there is a body with an ability
        conditioned on energy still dry: that engine goes first."""
        cur = obs.get("current") or {}
        yo = cur.get("yourIndex", 0)
        jugadores = cur.get("players") or []
        active = None
        if yo < len(jugadores):
            active = ((jugadores[yo] or {}).get("active") or [None])[0]
        al_activo = [i for i in adjuntes
                     if opciones[i].get("inPlayArea") == int(AreaType.ACTIVE)]

        if active and len(active.get("energies") or []) >= 1:
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
        """One activation per Pokemon and per turn, with a hard per-turn cap."""
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

    # -- damage counters ----------------------------------------------------

    def _cuantos_contadores(self, opciones):
        """Always the MAXIMUM: moving 1 out of 3 wastes the ability."""
        best = max(range(len(opciones)),
                    key=lambda i: opciones[i].get("number") or 0)
        self._contadores = opciones[best].get("number") or 1
        return [best]

    def _origen_de_contadores(self, obs, opciones, sel):
        """Where they are taken from: the body of ITS OWN carrying the most damage."""
        k = max(1, sel.get("minCount") or 1)
        orden = sorted(
            range(len(opciones)),
            key=lambda i: -self._dano_encajado(self._pokemon_de(obs, opciones[i])))
        return sorted(orden[:min(k, len(opciones))])

    def _destino_de_contadores(self, obs, opciones, sel):
        """Where they are placed: the OPPOSING body that dies with these counters (the
        more prizes, the better) and, if none dies, the one with the least HP."""
        cur = obs.get("current") or {}
        yo = cur.get("yourIndex", 0)
        damage = DANO_POR_CONTADOR * max(1, self._contadores)

        rivales = [i for i in range(len(opciones))
                   if opciones[i].get("playerIndex") not in (None, yo)]
        candidatos = rivales or list(range(len(opciones)))

        def clave(i):
            pk = self._pokemon_de(obs, opciones[i], indice_propio=yo)
            if not pk:
                return (2, 0, 0)
            hp = pk.get("hp") or 0
            if i in rivales:
                # First the ones that DIE, and among them the ones worth more prizes.
                return (0 if hp <= damage else 1, -self._prizes(pk), hp)
            # If only its own bodies are left, the one that hurts least: the healthiest.
            return (2, 0, -hp)

        k = max(1, sel.get("minCount") or 1)
        orden = sorted(candidatos, key=clave)
        return sorted(orden[:min(k, len(candidatos))])

    # -- who goes to the active spot ----------------------------------------

    def _elegir_activo(self, obs, opciones, sel):
        """Two cases with the same context:

        * options over OUR bench -- a promotion after a KO or the destination of a
          retreat: the one carrying the most energy comes up (a proxy for "it can attack") and,
          on a tie, the one with the most HP.
        * options over the OPPOSING bench -- it is us gusting (Boss's and
          family): the one we can KNOCK OUT comes up, the more prizes the better; if there
          is no KO, the one with the least HP.
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
                return (0 if muere else 1, -self._prizes(pk), hp)

            orden = sorted(rivales, key=clave_gusteo)
            return sorted(orden[:min(k, len(rivales))])

        def clave_propia(i):
            pk = self._pokemon_de(obs, opciones[i], indice_propio=yo)
            if not pk:
                return (0, 0)
            return (-len(pk.get("energies") or []), -(pk.get("hp") or 0))

        orden = sorted(range(len(opciones)), key=clave_propia)
        return sorted(orden[:min(k, len(opciones))])

    # -- yes / no -----------------------------------------------------------

    def _si_no(self, contexto, opciones):
        prefiere_no = contexto in (int(SelectContext.MULLIGAN),
                                   int(SelectContext.MORE_DEVOLVE))
        buscado = int(OptionType.NO) if prefiere_no else int(OptionType.YES)
        for i, o in enumerate(opciones):
            if o.get("type") == buscado:
                return [i]
        return [0]
