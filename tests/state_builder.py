"""Builder of synthetic observations (`Escenario`) for strategy tests.

It makes it possible to fabricate game states THAT NEVER HAPPENED in real games
(edge conditions, parametric sweeps) without depending on records or
editing JSON by hand. The builder does STRICT ACCOUNTING of the 60 cards of our own
deck (deck.csv): every card placed in a zone (field, hand, discard,
visible deck, stadium, effect) is deducted from a pool; when building, the
remainder must be exactly the number of face-down prizes (6 by default).
An impossible state (more copies than the deck has, a remainder different from the
prizes) raises `EstadoInconsistente` with a clear message, instead of producing
an observation that would confuse the tracking of `main.CARTAS_ACTIVAS_EN_MAZO`.

Typical usage (see tests/test_state_builder.py):

    obs = (Escenario(turno=8, paso=69, tac=3)
           .mi_activo(pk(DIPPLIN, energias=[G, G], fisicas=1, pre_evo=[APPLIN]))
           .mi_banca(pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]), OGERPON, MEOWTH)
           .estadio(FOREST)
           .op_activo(pk(KANGASKHAN, hp=160, max_hp=400,
                         energias=[C, G, C, C], tools=[HEROS_CAPE]))
           .op_banca(pk(CRUSTLE, pre_evo=[DWEBBLE]))
           .op_zonas(mano=9, mazo=37, premios=2)
           .mazo(HYDRAPPLE, TAPU, LILLIE, ...)   # the deck's visible contents
           .mi_descarte(...)                      # the rest, identified
           .fetch_ultra_ball()                    # a TO_HAND select via Ultra Ball
           .construir())
    eleccion = m.agent(obs)

The opponent has NO accounting (their deck is unknown): their hidden zones are
declared as counts (`op_zonas`).
"""

from collections import Counter
from pathlib import Path

from cg.api import (AreaType, CardType, EnergyType, OptionType, SelectContext,
                    SelectType, all_attack, all_card_data)

_ROOT = Path(__file__).resolve().parents[1]

# Card data for the defaults (maximum HP, Pokemon detection).
_CARD_TABLE = {c.cardId: c for c in all_card_data()}
# Attacks by id: `menu_hand(with_attack=True)` needs the cost to emit
# only the attacks the active can pay for (as the simulator does).
_ATTACK_TABLE = {a.attackId: a for a in all_attack()}

# Abbreviated energies for readable specs.
C = int(EnergyType.COLORLESS)
G = int(EnergyType.GRASS)

BASIC_GRASS = 1        # id of the Basic Grass Energy (deck.csv)
BOSS_ORDERS = 1182     # id of Boss's Orders (deck.csv)
ULTRA_BALL = 1121      # id of the Ultra Ball (deck.csv)
TEAL_MASK_OGERPON_EX = 96    # id of Teal Mask Ogerpon ex (the Teal Dance ability)
FOREST_OF_VITALITY = 1261    # id of our own stadium (deck.csv)
GRAND_TREE = 1249      # id of the instant-evolution ACE SPEC stadium
_DEFAULT_PRIZES = 6


class InconsistentState(AssertionError):
    """The declared scenario does not add up to the 60 cards of deck.csv."""


def _read_deck_csv():
    csv = (_ROOT / "deck.csv").read_text().split("\n")
    return [int(csv[i]) for i in range(60)]


def pk(card_id, hp=None, max_hp=None, energies=(), fisicas=None,
       pre_evo=(), tools=(), aparecio=False):
    """Spec of a Pokemon in play.

    energias: a list of EFFECTIVE EnergyType (with Meganium, 1 physical Grass
        counts as [G, G]). An int N is equivalent to [G]*N.
    fisicas: the number of energy CARDS attached (default: len(energias)).
        On our own side they consume Basic Grass from the pool.
    pre_evo: ids of the pre-evolution cards stacked underneath.
    tools: ids of the attached tools.
    """
    if isinstance(energies, int):
        energies = [G] * energies
    energies = list(energies)
    if fisicas is None:
        fisicas = len(energies)
    data = _CARD_TABLE.get(card_id)
    base_hp = data.hp if data is not None else 0
    if max_hp is None:
        max_hp = base_hp
    if hp is None:
        hp = max_hp
    return {
        "id": card_id, "hp": hp, "maxHp": max_hp, "energies": energies,
        "fisicas": fisicas, "pre_evo": list(pre_evo), "tools": list(tools),
        "aparecio": aparecio,
    }


def _como_spec(x):
    return x if isinstance(x, dict) else pk(x)


class Scenario:

    def __init__(self, turn=2, step=1, tac=0, first_player=0,
                 energy_played=False, supporter_played=False,
                 stadium_played=False, retirado=False, own_prizes=None):
        self._turn = turn
        self._step = step
        self._tac = tac
        self._first_player = first_player
        self._energy_played = energy_played
        self._supporter_played = supporter_played
        self._stadium_played = stadium_played
        self._retirado = retirado
        self._n_prizes = (_DEFAULT_PRIZES if own_prizes is None
                           else own_prizes)

        self._pool = Counter(_read_deck_csv())
        self._serial_mio = iter(range(0, 60))
        self._serial_op = iter(range(60, 120))

        self._my_active = None
        self._my_bench = []
        self._my_hand = []
        self._my_discard = []
        self._visible_deck = None
        self._stadium = None
        self._efecto = None

        self._op_active_spec = None
        self._op_bench = []
        self._op_discard = []
        self._op_hand = 0
        self._op_deck = 30
        self._op_prizes = 6

        self._select = None

    # ------------------------------------------------------------------
    # Accounting of our own pool
    # ------------------------------------------------------------------
    def _tomar(self, card_id, zone):
        if self._pool[card_id] <= 0:
            raise InconsistentState(
                f"no quedan copias de la carta {card_id} en deck.csv para "
                f"colocar en {zone} (ya se usaron todas)")
        self._pool[card_id] -= 1
        return {"id": card_id, "playerIndex": 0, "serial": next(self._serial_mio)}

    def _pokemon_mio(self, spec):
        spec = _como_spec(spec)
        card = self._tomar(spec["id"], "campo")
        e_cards = [self._tomar(BASIC_GRASS, "energia adjunta")
                   for _ in range(spec["fisicas"])]
        pre = [self._tomar(cid, "pre-evolucion") for cid in spec["pre_evo"]]
        tools = [self._tomar(cid, "herramienta") for cid in spec["tools"]]
        return {
            "id": spec["id"], "serial": card["serial"], "playerIndex": 0,
            "hp": spec["hp"], "maxHp": spec["maxHp"],
            "appearThisTurn": spec["aparecio"],
            "energies": spec["energies"], "energyCards": e_cards,
            "tools": tools, "preEvolution": pre,
        }

    def _pokemon_op(self, spec):
        spec = _como_spec(spec)
        serial = next(self._serial_op)
        e_cards = [{"id": BASIC_GRASS, "playerIndex": 1,
                    "serial": next(self._serial_op)}
                   for _ in range(spec["fisicas"])]
        pre = [{"id": cid, "playerIndex": 1, "serial": next(self._serial_op)}
               for cid in spec["pre_evo"]]
        tools = [{"id": cid, "playerIndex": 1, "serial": next(self._serial_op)}
                 for cid in spec["tools"]]
        return {
            "id": spec["id"], "serial": serial, "playerIndex": 1,
            "hp": spec["hp"], "maxHp": spec["maxHp"],
            "appearThisTurn": spec["aparecio"],
            "energies": spec["energies"], "energyCards": e_cards,
            "tools": tools, "preEvolution": pre,
        }

    # ------------------------------------------------------------------
    # Our own zones
    # ------------------------------------------------------------------
    def my_active(self, spec):
        self._my_active = self._pokemon_mio(spec)
        return self

    def my_bench(self, *specs):
        self._my_bench = [self._pokemon_mio(s) for s in specs]
        return self

    def my_hand(self, *ids):
        self._my_hand = [self._tomar(cid, "mano") for cid in ids]
        return self

    def my_discard(self, *ids):
        self._my_discard = [self._tomar(cid, "discard") for cid in ids]
        return self

    def stadium(self, card_id, of_the_opponent=False):
        """The stadium on the field.

        `of_the_opponent=True` for stadiums that are NOT in deck.csv (the opponent plays
        them): they do not consume our own pool. That is the case of Grand Tree, whose
        ability is of shared use -- BOTH players use it.
        """
        if of_the_opponent:
            self._stadium = {"id": card_id, "playerIndex": 1,
                             "serial": next(self._serial_op)}
        else:
            self._stadium = self._tomar(card_id, "stadium")
        return self

    def deck(self, *ids):
        """The VISIBLE contents of our own deck (order = the array's order)."""
        self._visible_deck = [self._tomar(cid, "mazo") for cid in ids]
        return self

    def rest_to_discard(self):
        """Sends to the discard all the remaining pool except the prizes.

        It requires `mazo(...)` to have been declared first (otherwise there would be no way
        to know which part of the rest is deck and which part discard). Convenient for sweeps where
        the exact contents of the discard do not matter.
        """
        if self._visible_deck is None:
            raise InconsistentState(
                "resto_al_descarte() requiere haber declarado antes mazo(...)")
        sobran = sum(self._pool.values()) - self._n_prizes
        if sobran < 0:
            raise InconsistentState(
                f"quedan {sum(self._pool.values())} cartas en el pool, menos "
                f"que los {self._n_prizes} premios: el escenario coloco de mas")
        for cid in sorted(self._pool.elements()):
            if sobran == 0:
                break
            self._my_discard.append(self._tomar(cid, "discard"))
            sobran -= 1
        return self

    # ------------------------------------------------------------------
    # The opponent's zones (with no accounting: their deck is unknown)
    # ------------------------------------------------------------------
    def op_active(self, spec):
        self._op_active_spec = self._pokemon_op(spec)
        return self

    def op_bench(self, *specs):
        self._op_bench = [self._pokemon_op(s) for s in specs]
        return self

    def op_discard(self, *ids):
        self._op_discard = [{"id": cid, "playerIndex": 1,
                              "serial": next(self._serial_op)} for cid in ids]
        return self

    def op_zones(self, hand=0, deck=30, prizes=6):
        self._op_hand = hand
        self._op_deck = deck
        self._op_prizes = prizes
        return self

    # ------------------------------------------------------------------
    # Selects
    # ------------------------------------------------------------------
    def fetch_ultra_ball(self, candidates=None):
        """The Ultra Ball's TO_HAND select over the visible deck.

        candidatos: eligible ids; by default, ALL the Pokemon in the deck
        (the Ultra Ball's real behaviour). Each copy is an option.
        It consumes an Ultra Ball from the pool (the card 'in effect').
        """
        if self._visible_deck is None:
            raise InconsistentState(
                "fetch_ultra_ball() requiere haber declarado antes mazo(...)")
        self._efecto = self._tomar(ULTRA_BALL, "efecto (Ultra Ball en juego)")

        def is_candidate(cid):
            if candidates is not None:
                return cid in candidates
            data = _CARD_TABLE.get(cid)
            return data is not None and data.cardType == CardType.POKEMON

        options = [
            {"type": int(OptionType.CARD), "area": int(AreaType.DECK),
             "index": i, "playerIndex": 0}
            for i, card in enumerate(self._visible_deck)
            if is_candidate(card["id"])]
        if not options:
            raise InconsistentState(
                "fetch_ultra_ball() sin ningun candidato en el mazo declarado")
        self._select = {
            "type": int(SelectType.CARD),
            "context": int(SelectContext.TO_HAND),
            "minCount": 0, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": options,
            "deck": list(self._visible_deck),
            "contextCard": None,
            "effect": self._efecto,
        }
        return self

    def menu_attach_energy(self):
        """A minimal MAIN select: attach the 1st Basic Grass from hand.

        It generates one ATTACH option per EACH of our Pokemon in play (the active
        inPlayArea=4; the bench inPlayArea=5/inPlayIndex=k) plus END, with the
        same shape as the real simulator. It requires a Basic Grass in
        my_hand() and energy_played=False.
        """
        if self._energy_played:
            raise InconsistentState(
                "menu_attach_energia() con energia_jugada=True no tendria "
                "opciones ATTACH")
        idx_energy = next((i for i, c in enumerate(self._my_hand)
                      if c["id"] == BASIC_GRASS), None)
        if idx_energy is None:
            raise InconsistentState(
                "menu_attach_energia() requiere una Basic Grass en mi_mano()")
        options = []
        if self._my_active is not None:
            options.append({"type": int(OptionType.ATTACH),
                             "area": int(AreaType.HAND), "index": idx_energy,
                             "inPlayArea": int(AreaType.ACTIVE),
                             "inPlayIndex": 0})
        for k in range(len(self._my_bench)):
            options.append({"type": int(OptionType.ATTACH),
                             "area": int(AreaType.HAND), "index": idx_energy,
                             "inPlayArea": int(AreaType.BENCH),
                             "inPlayIndex": k})
        options.append({"type": int(OptionType.END)})
        self._select = {
            "type": int(SelectType.MAIN),
            "context": int(SelectContext.MAIN),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": options,
            "deck": None,
            "contextCard": None,
            "effect": None,
        }
        return self

    def menu_teal_dance_options(self):
        """A MAIN select with the Teal Dance ABILITY besides the manual attachment.

        It emits one ABILITY option (area ACTIVE/BENCH, the slot's index) per each
        Teal Mask Ogerpon ex of ours in play, the ATTACH options of the 1st
        Basic Grass in hand and END, like the real menu of a turn in which
        energy has not been attached yet.
        """
        idx_energy = next((i for i, c in enumerate(self._my_hand)
                      if c["id"] == BASIC_GRASS), None)
        if idx_energy is None:
            raise InconsistentState(
                "menu_teal_dance() requiere una Basic Grass en mi_mano(): "
                "Teal Dance adjunta una Planta DE LA MANO")
        options = []
        if (self._my_active is not None
                and self._my_active["id"] == TEAL_MASK_OGERPON_EX):
            options.append({"type": int(OptionType.ABILITY),
                             "area": int(AreaType.ACTIVE), "index": 0})
        for k, p in enumerate(self._my_bench):
            if p["id"] == TEAL_MASK_OGERPON_EX:
                options.append({"type": int(OptionType.ABILITY),
                                 "area": int(AreaType.BENCH), "index": k})
        if not options:
            raise InconsistentState(
                "menu_teal_dance() requiere un Teal Mask Ogerpon ex en juego")
        if not self._energy_played:
            if self._my_active is not None:
                options.append({"type": int(OptionType.ATTACH),
                                 "area": int(AreaType.HAND), "index": idx_energy,
                                 "inPlayArea": int(AreaType.ACTIVE),
                                 "inPlayIndex": 0})
            for k in range(len(self._my_bench)):
                options.append({"type": int(OptionType.ATTACH),
                                 "area": int(AreaType.HAND), "index": idx_energy,
                                 "inPlayArea": int(AreaType.BENCH),
                                 "inPlayIndex": k})
        options.append({"type": int(OptionType.END)})
        self._select = {
            "type": int(SelectType.MAIN),
            "context": int(SelectContext.MAIN),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": options,
            "deck": None,
            "contextCard": None,
            "effect": None,
        }
        return self

    def menu_hand(self, with_retreat=False, with_attachment=False,
                  with_attack=False):
        """A generic MAIN select: one PLAY option per card in hand, plus
        (optionally) the ATTACH of the 1st Basic Grass, RETREAT and/or the ATTACK
        options of the active, plus END.

        Designed for scenarios where what is measured is WHICH card is played, without
        the noise of a complete simulator menu. `with_attack` emits one ATTACK
        per attack of the active whose energy cost it can ALREADY pay (the same
        criterion as the simulator), so attack-vs-retreat can be measured.
        """
        options = [{"type": int(OptionType.PLAY), "index": i}
                    for i in range(len(self._my_hand))]
        if with_attachment:
            idx_energy = next((i for i, c in enumerate(self._my_hand)
                          if c["id"] == BASIC_GRASS), None)
            if idx_energy is None:
                raise InconsistentState(
                    "menu_mano(con_adjunte=True) requiere una Basic Grass en "
                    "mi_mano()")
            if self._my_active is not None:
                options.append({"type": int(OptionType.ATTACH),
                                 "area": int(AreaType.HAND), "index": idx_energy,
                                 "inPlayArea": int(AreaType.ACTIVE),
                                 "inPlayIndex": 0})
            for k in range(len(self._my_bench)):
                options.append({"type": int(OptionType.ATTACH),
                                 "area": int(AreaType.HAND), "index": idx_energy,
                                 "inPlayArea": int(AreaType.BENCH),
                                 "inPlayIndex": k})
        if with_attack:
            if self._my_active is None:
                raise InconsistentState(
                    "menu_mano(con_ataque=True) requiere mi_activo(...)")
            _act_data = _CARD_TABLE.get(self._my_active["id"])
            _disp = len(self._my_active["energies"])
            for _aid in (getattr(_act_data, 'attacks', None) or ()):
                _atk = _ATTACK_TABLE.get(_aid)
                if _atk is None:
                    continue
                if len(getattr(_atk, 'energies', None) or ()) > _disp:
                    continue
                options.append({"type": int(OptionType.ATTACK),
                                 "attackId": _aid})
        if with_retreat:
            options.append({"type": int(OptionType.RETREAT)})
        options.append({"type": int(OptionType.END)})
        self._select = {
            "type": int(SelectType.MAIN),
            "context": int(SelectContext.MAIN),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": options,
            "deck": None,
            "contextCard": None,
            "effect": None,
        }
        return self

    def fetch_discard(self, efecto_id, cuantas=1, only=None):
        """A TO_HAND select of a RECOVERY card (Night Stretcher, Lana's
        Aid...) over our own already declared discard. It consumes a copy of
        `efecto_id` from the pool (the card 'in effect').

        `cuantas` is the menu's `maxCount`: 1 for Night Stretcher, 3 for
        Lana's Aid. `solo` restricts the options to those ids from the discard, as
        the simulator does with the card's filters (Lana's Aid only offers
        Pokemon WITHOUT a Rule Box and Basic Energies: no ex).
        """
        if not self._my_discard:
            raise InconsistentState(
                "fetch_descarte() requiere haber declarado antes mi_descarte(...)")
        self._efecto = self._tomar(efecto_id, "efecto (recuperacion en juego)")
        options = [{"type": int(OptionType.CARD),
                     "area": int(AreaType.DISCARD), "index": i,
                     "playerIndex": 0}
                    for i, card in enumerate(self._my_discard)
                    if only is None or card["id"] in only]
        if not options:
            raise InconsistentState(
                "fetch_descarte(solo=...) no deja ninguna opcion en el descarte")
        self._select = {
            "type": int(SelectType.CARD),
            "context": int(SelectContext.TO_HAND),
            "minCount": 1, "maxCount": max(1, min(cuantas, len(options))),
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": options,
            "deck": None,
            "contextCard": None,
            "effect": self._efecto,
        }
        return self

    def ability_charge_target(self, bench_idx=None):
        """An ATTACH_FROM select: to WHICH of our Pokemon an already activated charging
        ability attaches the Grass (Hydrapple ex's Ripening Charge...).

        It emits one CARD option for the active (area ACTIVE) and one per bench
        slot (area BENCH), just like the real simulator. The bearer of the
        ability is the active or, if `bench_idx` is given, that bench slot:
        it is already in play, so it does NOT consume another copy from the pool.
        """
        if self._my_active is None:
            raise InconsistentState(
                "objetivo_carga_habilidad() requiere mi_activo(...)")
        portador = (self._my_active if bench_idx is None
                    else self._my_bench[bench_idx])
        self._efecto = {"id": portador["id"], "playerIndex": 0,
                        "serial": portador["serial"]}
        options = [{"type": int(OptionType.CARD),
                     "area": int(AreaType.ACTIVE), "index": 0,
                     "playerIndex": 0}]
        options += [{"type": int(OptionType.CARD),
                      "area": int(AreaType.BENCH), "index": k,
                      "playerIndex": 0}
                     for k in range(len(self._my_bench))]
        self._select = {
            "type": int(SelectType.CARD),
            "context": int(SelectContext.ATTACH_FROM),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": options,
            "deck": None,
            "contextCard": None,
            "effect": self._efecto,
        }
        return self

    def promote_after_retreat(self):
        """A SWITCH select: choosing who COMES UP from the bench when the active retreats.

        It is the prompt the simulator emits right after paying the retreat
        cost (verified with `cg.api.search_begin/search_step`: a SWITCH
        context, CARD options over our own BENCH). It is distinct from
        `promote_from_bench` (TO_ACTIVE), which is the FORCED promotion after a
        KO and can fall on the opponent's turn.
        """
        if not self._my_bench:
            raise InconsistentState(
                "promocion_tras_retirada() requiere mi_banca(...)")
        self._retirado = True
        self._select = {
            "type": int(SelectType.CARD),
            "context": int(SelectContext.SWITCH),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": [{"type": int(OptionType.CARD),
                        "area": int(AreaType.BENCH), "index": k,
                        "playerIndex": 0}
                       for k in range(len(self._my_bench))],
            "deck": None,
            "contextCard": None,
            "effect": None,
        }
        return self

    def promote_from_bench(self):
        """A TO_ACTIVE select: promoting a Pokemon from the bench after a retreat/KO."""
        if not self._my_bench:
            raise InconsistentState(
                "promocion_desde_banca() requiere mi_banca(...)")
        self._select = {
            "type": int(SelectType.CARD),
            "context": int(SelectContext.TO_ACTIVE),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": [{"type": int(OptionType.CARD),
                        "area": int(AreaType.BENCH), "index": k,
                        "playerIndex": 0}
                       for k in range(len(self._my_bench))],
            "deck": None,
            "contextCard": None,
            "effect": None,
        }
        return self

    def menu_gust(self):
        """The Boss's Orders TARGET select: one option per each Pokemon of
        the OPPOSING BENCH. It consumes a copy of Boss's Orders from the pool (the card
        'in effect', already played) and marks the Supporter as spent."""
        if not self._op_bench:
            raise InconsistentState("menu_gusteo() requiere op_banca(...)")
        self._tomar(BOSS_ORDERS, "efecto")
        self._supporter_played = True
        self._select = {
            "type": int(SelectType.CARD),
            "context": int(SelectContext.SWITCH),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": [{"type": int(OptionType.CARD),
                        "area": int(AreaType.BENCH), "index": k,
                        "playerIndex": 1}
                       for k in range(len(self._op_bench))],
            "deck": None,
            "contextCard": None,
            "effect": {"id": BOSS_ORDERS, "playerIndex": 0, "serial": 500},
        }
        return self

    def menu_grand_tree_options(self, with_forest=False, with_evolution_in_hand=False):
        """A MAIN select with the ABILITY of the Grand Tree stadium.

        It emits the ABILITY option over the STADIUM area (as the simulator does
        with stadium abilities), optionally the PLAY of a Forest of
        Vitality from hand and/or the available EVOLVE options from hand, and END.
        """
        if self._stadium is None or self._stadium["id"] != GRAND_TREE:
            raise InconsistentState(
                "menu_grand_tree() requiere estadio(GRAND_TREE, ...)")
        options = [{"type": int(OptionType.ABILITY),
                     "area": int(AreaType.STADIUM), "index": 0}]
        if with_forest:
            idx = next((i for i, c in enumerate(self._my_hand)
                        if c["id"] == FOREST_OF_VITALITY), None)
            if idx is None:
                raise InconsistentState(
                    "menu_grand_tree(con_forest=True) requiere una Forest of "
                    "Vitality en mi_mano()")
            options.append({"type": int(OptionType.PLAY), "index": idx})
        if with_evolution_in_hand:
            in_play = ([self._my_active] if self._my_active else []) + self._my_bench
            for i, c in enumerate(self._my_hand):
                data = _CARD_TABLE.get(c["id"])
                pre = getattr(data, "evolvesFrom", None) if data else None
                if not pre:
                    continue
                for j, p in enumerate(in_play):
                    p_data = _CARD_TABLE.get(p["id"])
                    if p_data is None or p_data.name != pre:
                        continue
                    options.append({
                        "type": int(OptionType.EVOLVE),
                        "area": int(AreaType.HAND), "index": i,
                        "inPlayArea": int(AreaType.ACTIVE if j == 0
                                          else AreaType.BENCH),
                        "inPlayIndex": 0 if j == 0 else j - 1})
        options.append({"type": int(OptionType.END)})
        self._select = {
            "type": int(SelectType.MAIN),
            "context": int(SelectContext.MAIN),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": options,
            "deck": None,
            "contextCard": None,
            "effect": None,
        }
        return self

    def grand_tree_selection_in_play(self):
        """The "which Pokemon OF MINE evolves" sub-selection served by Grand Tree.

        One CARD option per each of our Pokemon in play, with `select.effect`
        pointing at the stadium.
        """
        if self._stadium is None or self._stadium["id"] != GRAND_TREE:
            raise InconsistentState(
                "seleccion_grand_tree_* requiere estadio(GRAND_TREE, ...)")
        options = []
        if self._my_active is not None:
            options.append({"type": int(OptionType.CARD),
                             "area": int(AreaType.ACTIVE), "index": 0,
                             "playerIndex": 0})
        for k in range(len(self._my_bench)):
            options.append({"type": int(OptionType.CARD),
                             "area": int(AreaType.BENCH), "index": k,
                             "playerIndex": 0})
        self._select = {
            "type": int(SelectType.CARD),
            "context": int(SelectContext.EVOLVES_FROM),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": options,
            "deck": None,
            "contextCard": None,
            "effect": dict(self._stadium),
        }
        return self

    def grand_tree_selection_deck(self, *ids):
        """The "which card do I bring from the deck" sub-selection served by Grand Tree.

        `ids` are the OFFERED cards (already declared in `mazo(...)`); they are
        emitted as CARD options over the DECK area.
        """
        if self._stadium is None or self._stadium["id"] != GRAND_TREE:
            raise InconsistentState(
                "seleccion_grand_tree_* requiere estadio(GRAND_TREE, ...)")
        if self._visible_deck is None:
            raise InconsistentState(
                "seleccion_grand_tree_mazo() requiere mazo(...) declarado")
        options = []
        for cid in ids:
            idx = next((i for i, c in enumerate(self._visible_deck)
                        if c["id"] == cid), None)
            if idx is None:
                raise InconsistentState(
                    f"la carta {cid} no esta en el mazo declarado")
            options.append({"type": int(OptionType.CARD),
                             "area": int(AreaType.DECK), "index": idx,
                             "playerIndex": 0})
        self._select = {
            "type": int(SelectType.CARD),
            "context": int(SelectContext.TO_FIELD),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": options,
            "deck": list(self._visible_deck),
            "contextCard": None,
            "effect": dict(self._stadium),
        }
        return self

    # ------------------------------------------------------------------
    # Final construction
    # ------------------------------------------------------------------
    def build(self):
        if self._my_active is None:
            raise InconsistentState("falta mi_activo(...)")
        if self._op_active_spec is None:
            raise InconsistentState("falta op_activo(...)")
        if self._select is None:
            raise InconsistentState(
                "falta el select (p.ej. fetch_ultra_ball())")

        remaining = sum(self._pool.values())
        if self._visible_deck is not None:
            # With the deck declared, the remainder is exactly the prizes.
            if remaining != self._n_prizes:
                sobra = {k: v for k, v in self._pool.items() if v > 0}
                raise InconsistentState(
                    f"la contabilidad no cuadra: con el mazo declarado deben "
                    f"sobrar exactamente {self._n_prizes} cartas (premios "
                    f"boca abajo) y sobran {remaining}: {sobra}. Ajusta "
                    f"descarte/mano/mazo o usa resto_al_descarte().")
            deck_count = len(self._visible_deck)
        else:
            deck_count = remaining - self._n_prizes
            if deck_count < 0:
                raise InconsistentState(
                    f"quedan {remaining} cartas sin colocar, menos que los "
                    f"{self._n_prizes} premios: el escenario coloco de mas")

        mi_player = {
            "active": [self._my_active],
            "bench": self._my_bench,
            "benchMax": 5,
            "deckCount": deck_count,
            "discard": self._my_discard,
            "prize": [None] * self._n_prizes,
            "handCount": len(self._my_hand),
            "hand": self._my_hand,
            "poisoned": False, "burned": False, "asleep": False,
            "paralyzed": False, "confused": False,
        }
        op_player = {
            "active": [self._op_active_spec],
            "bench": self._op_bench,
            "benchMax": 5,
            "deckCount": self._op_deck,
            "discard": self._op_discard,
            "prize": [None] * self._op_prizes,
            "handCount": self._op_hand,
            "hand": None,
            "poisoned": False, "burned": False, "asleep": False,
            "paralyzed": False, "confused": False,
        }
        current = {
            "turn": self._turn,
            "turnActionCount": self._tac,
            "yourIndex": 0,
            "firstPlayer": self._first_player,
            "supporterPlayed": self._supporter_played,
            "stadiumPlayed": self._stadium_played,
            "energyAttached": self._energy_played,
            "retreated": self._retirado,
            "result": -1,
            "stadium": [self._stadium] if self._stadium else [],
            "looking": None,
            "players": [mi_player, op_player],
        }
        return {
            "step": self._step,
            "remainingOverageTime": 60000,
            "logs": [],
            "select": self._select,
            "current": current,
        }
