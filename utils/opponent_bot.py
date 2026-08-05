"""Generic opposing bot: it pilots ANY deck legally and consistently.

It is not a good player and does not try to be: it is the REFERENCE OPPONENT of the
--opponent mode of utils/selfplay.py. Being fixed and deterministic in its rules
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

MEASUREMENT NOTE (user, records/marnie): until 2026-08-02 the bot did NOT use
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
MAX_ABILITIES_PER_TURN = 8
# Damage per damage counter.
DAMAGE_PER_COUNTER = 10


class BotRival:

    def __init__(self):
        self._attacks = {a.attackId: a for a in all_attack()}
        self._damage = {a.attackId: a.damage for a in all_attack()}
        self._cards = {c.cardId: c for c in all_card_data()}
        self._turn = None
        self._habilidades_usadas = set()
        self._activaciones = 0
        # Counters the current effect is going to move/place (it is set in the
        # AMOUNT select and consumed by the DESTINATION select).
        self._contadores = 1

    # -- utilities ----------------------------------------------------------

    def _reset_turn(self, turn):
        self._turn = turn
        self._habilidades_usadas = set()
        self._activaciones = 0
        self._contadores = 1

    def _pokemon_de(self, obs, opcion, own_index=None):
        """The Pokemon `opcion` points at, or None if the option does not point at one."""
        cur = obs.get("current") or {}
        players = cur.get("players") or []
        pi = opcion.get("playerIndex")
        if pi is None:
            pi = own_index
        if pi is None or pi >= len(players):
            return None
        player = players[pi] or {}
        area = opcion.get("area")
        idx = opcion.get("index") or 0
        try:
            if area == int(AreaType.ACTIVE):
                pk = (player.get("active") or [None])[0]
            elif area == int(AreaType.BENCH):
                pk = (player.get("bench") or [])[idx]
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

    def _damage_taken(self, pk):
        if not pk:
            return -1
        return max(0, (pk.get("maxHp") or 0) - (pk.get("hp") or 0))

    def _effective_damage(self, attacker, defensor, attack_id):
        """The attack's printed damage, x2 if the defender is weak to the
        attacker's type. Deliberately approximate: the attacks that scale (Syrup Storm,
        Myriad Leaf Shower) declare their base, not their real damage."""
        base = self._damage.get(attack_id) or 0
        if base <= 0 or not attacker or not defensor:
            return base
        atk = self._cards.get(attacker.get("id"))
        dfd = self._cards.get(defensor.get("id"))
        if atk is None or dfd is None:
            return base
        if dfd.weakness is not None and dfd.weakness == atk.energyType:
            return base * 2
        return base

    def _best_damage_of(self, attacker, defensor):
        """The best effective damage `attacker` can do to `defensor` with
        any of its attacks (without checking whether it can pay the cost)."""
        data = self._cards.get((attacker or {}).get("id"))
        if data is None:
            return 0
        return max((self._effective_damage(attacker, defensor, aid)
                    for aid in (data.attacks or ())), default=0)

    def _ability_needs_energy(self, card_id):
        """The card's ability is CONDITIONED on carrying energy."""
        data = self._cards.get(card_id)
        for skill in getattr(data, "skills", None) or ():
            if "Energy attached" in (getattr(skill, "text", "") or ""):
                return True
        return False

    # -- dispatch -----------------------------------------------------------

    def agent(self, obs):
        sel = obs.get("select") or {}
        options = sel.get("option") or []
        if not options:
            return []
        cur = obs.get("current") or {}
        if cur.get("turn") != self._turn:
            self._reset_turn(cur.get("turn"))
        context = sel.get("context")

        if context == int(SelectContext.MAIN):
            return self._menu_principal(obs, options)

        if context in (int(SelectContext.REMOVE_DAMAGE_COUNTER_COUNT),
                        int(SelectContext.DAMAGE_COUNTER_COUNT)):
            return self._cuantos_contadores(options)

        if context == int(SelectContext.REMOVE_DAMAGE_COUNTER):
            return self._origen_de_contadores(obs, options, sel)

        if context in (int(SelectContext.DAMAGE_COUNTER),
                        int(SelectContext.DAMAGE_COUNTER_ANY)):
            return self._destino_de_contadores(obs, options, sel)

        if context in (int(SelectContext.SWITCH),
                        int(SelectContext.TO_ACTIVE)):
            return self._pick_active(obs, options, sel)

        tipos = {o.get("type") for o in options}
        if int(OptionType.YES) in tipos or int(OptionType.NO) in tipos:
            return self._si_no(context, options)

        minimo = sel.get("minCount") or 0
        k = minimo if minimo > 0 else min(1, sel.get("maxCount") or 1)
        k = min(k, len(options))
        return list(range(k))

    # -- main menu ----------------------------------------------------------

    def _menu_principal(self, obs, options):
        by_type = {}
        for i, o in enumerate(options):
            by_type.setdefault(o.get("type"), []).append(i)

        attachments = by_type.get(int(OptionType.ATTACH))
        if attachments:
            return [self._best_attachment(obs, options, attachments)]

        evoluciones = by_type.get(int(OptionType.EVOLVE))
        if evoluciones:
            return [self._best_evolution(obs, options, evoluciones)]

        plays = by_type.get(int(OptionType.PLAY))
        if plays:
            return [plays[0]]

        ability = self._pick_ability(by_type.get(int(OptionType.ABILITY)),
                                           options)
        if ability is not None:
            return [ability]

        ataques = by_type.get(int(OptionType.ATTACK))

        # With no attack available, RETREATING is the only thing that changes anything: a
        # body that does not hit, nailed in the active spot, loses the game on its own.
        retreats = by_type.get(int(OptionType.RETREAT))
        if not ataques and retreats:
            return [retreats[0]]

        if ataques:
            cur = obs.get("current") or {}
            yo = cur.get("yourIndex", 0)
            players = cur.get("players") or []
            my_active = None
            their_active = None
            if len(players) > max(yo, 1 - yo):
                my_active = ((players[yo] or {}).get("active") or [None])[0]
                their_active = ((players[1 - yo] or {}).get("active") or [None])[0]
            best = max(ataques, key=lambda i: self._effective_damage(
                my_active, their_active, options[i].get("attackId")))
            return [best]

        fin = by_type.get(int(OptionType.END))
        if fin:
            return [fin[0]]
        return [0]

    def _best_evolution(self, obs, options, indices):
        """The HIGHEST stage evolution first and, on a tie, the ACTIVE's."""
        def key(i):
            o = options[i]
            data = self._cards.get(self._id_in_hand(obs, o))
            etapa = 2 if getattr(data, "stage2", False) else \
                1 if getattr(data, "stage1", False) else 0
            to_active = o.get("inPlayArea") == int(AreaType.ACTIVE)
            return (-etapa, 0 if to_active else 1, i)
        return min(indices, key=key)

    def _id_in_hand(self, obs, opcion):
        cur = obs.get("current") or {}
        yo = cur.get("yourIndex", 0)
        players = cur.get("players") or []
        if yo >= len(players):
            return None
        hand = (players[yo] or {}).get("hand") or []
        idx = opcion.get("index")
        if opcion.get("area") != int(AreaType.HAND) or idx is None:
            return None
        try:
            return (hand[idx] or {}).get("id")
        except (IndexError, TypeError):
            return None

    def _best_attachment(self, obs, options, attachments):
        """To the ACTIVE, unless it already has energy and there is a body with an ability
        conditioned on energy still dry: that engine goes first."""
        cur = obs.get("current") or {}
        yo = cur.get("yourIndex", 0)
        players = cur.get("players") or []
        active = None
        if yo < len(players):
            active = ((players[yo] or {}).get("active") or [None])[0]
        to_active = [i for i in attachments
                     if options[i].get("inPlayArea") == int(AreaType.ACTIVE)]

        if active and len(active.get("energies") or []) >= 1:
            for i in attachments:
                target_path = self._pokemon_de(
                    obs,
                    {"area": options[i].get("inPlayArea"),
                     "index": options[i].get("inPlayIndex"),
                     "playerIndex": yo})
                if (target_path and not (target_path.get("energies") or [])
                        and self._ability_needs_energy(target_path.get("id"))):
                    return i

        return to_active[0] if to_active else attachments[0]

    def _pick_ability(self, indices, options):
        """One activation per Pokemon and per turn, with a hard per-turn cap."""
        if not indices or self._activaciones >= MAX_ABILITIES_PER_TURN:
            return None
        for i in indices:
            key = (options[i].get("area"), options[i].get("index"))
            if key in self._habilidades_usadas:
                continue
            self._habilidades_usadas.add(key)
            self._activaciones += 1
            return i
        return None

    # -- damage counters ----------------------------------------------------

    def _cuantos_contadores(self, options):
        """Always the MAXIMUM: moving 1 out of 3 wastes the ability."""
        best = max(range(len(options)),
                    key=lambda i: options[i].get("number") or 0)
        self._contadores = options[best].get("number") or 1
        return [best]

    def _origen_de_contadores(self, obs, options, sel):
        """Where they are taken from: the body of ITS OWN carrying the most damage."""
        k = max(1, sel.get("minCount") or 1)
        order = sorted(
            range(len(options)),
            key=lambda i: -self._damage_taken(self._pokemon_de(obs, options[i])))
        return sorted(order[:min(k, len(options))])

    def _destino_de_contadores(self, obs, options, sel):
        """Where they are placed: the OPPOSING body that dies with these counters (the
        more prizes, the better) and, if none dies, the one with the least HP."""
        cur = obs.get("current") or {}
        yo = cur.get("yourIndex", 0)
        damage = DAMAGE_PER_COUNTER * max(1, self._contadores)

        opponents = [i for i in range(len(options))
                   if options[i].get("playerIndex") not in (None, yo)]
        candidates = opponents or list(range(len(options)))

        def key(i):
            pk = self._pokemon_de(obs, options[i], own_index=yo)
            if not pk:
                return (2, 0, 0)
            hp = pk.get("hp") or 0
            if i in opponents:
                # First the ones that DIE, and among them the ones worth more prizes.
                return (0 if hp <= damage else 1, -self._prizes(pk), hp)
            # If only its own bodies are left, the one that hurts least: the healthiest.
            return (2, 0, -hp)

        k = max(1, sel.get("minCount") or 1)
        order = sorted(candidates, key=key)
        return sorted(order[:min(k, len(candidates))])

    # -- who goes to the active spot ----------------------------------------

    def _pick_active(self, obs, options, sel):
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
        players = cur.get("players") or []
        k = max(1, sel.get("minCount") or 1)

        opponents = [i for i in range(len(options))
                   if options[i].get("playerIndex") not in (None, yo)]
        if opponents:
            my_active = None
            if yo < len(players):
                my_active = ((players[yo] or {}).get("active") or [None])[0]

            def gust_key(i):
                pk = self._pokemon_de(obs, options[i])
                if not pk:
                    return (2, 0, 0)
                hp = pk.get("hp") or 0
                muere = self._best_damage_of(my_active, pk) >= hp
                return (0 if muere else 1, -self._prizes(pk), hp)

            order = sorted(opponents, key=gust_key)
            return sorted(order[:min(k, len(opponents))])

        def own_key(i):
            pk = self._pokemon_de(obs, options[i], own_index=yo)
            if not pk:
                return (0, 0)
            return (-len(pk.get("energies") or []), -(pk.get("hp") or 0))

        order = sorted(range(len(options)), key=own_key)
        return sorted(order[:min(k, len(options))])

    # -- yes / no -----------------------------------------------------------

    def _si_no(self, context, options):
        prefiere_no = context in (int(SelectContext.MULLIGAN),
                                   int(SelectContext.MORE_DEVOLVE))
        buscado = int(OptionType.NO) if prefiere_no else int(OptionType.YES)
        for i, o in enumerate(options):
            if o.get("type") == buscado:
                return [i]
        return [0]
