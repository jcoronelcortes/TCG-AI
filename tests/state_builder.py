"""Constructor de observaciones sinteticas (`Escenario`) para tests de estrategia.

Permite fabricar estados de juego QUE NUNCA OCURRIERON en partidas reales
(condiciones de borde, barridos parametricos) sin depender de registros ni de
mutar JSON a mano. El builder hace CONTABILIDAD ESTRICTA de las 60 cartas del
mazo propio (deck.csv): cada carta colocada en una zona (campo, mano, descarte,
mazo visible, estadio, efecto) se descuenta de un pool; al construir, el
sobrante debe ser exactamente el numero de premios boca abajo (6 por defecto).
Un estado imposible (mas copias que las del mazo, sobrante distinto de los
premios) lanza `EstadoInconsistente` con un mensaje claro, en vez de producir
una observacion que confundiria el tracking de `main.CARTAS_ACTIVAS_EN_MAZO`.

Uso tipico (ver tests/test_state_builder.py):

    obs = (Escenario(turno=8, paso=69, tac=3)
           .mi_activo(pk(DIPPLIN, energias=[G, G], fisicas=1, pre_evo=[APPLIN]))
           .mi_banca(pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]), OGERPON, MEOWTH)
           .estadio(FOREST)
           .op_activo(pk(KANGASKHAN, hp=160, max_hp=400,
                         energias=[C, G, C, C], tools=[HEROS_CAPE]))
           .op_banca(pk(CRUSTLE, pre_evo=[DWEBBLE]))
           .op_zonas(mano=9, mazo=37, premios=2)
           .mazo(HYDRAPPLE, TAPU, LILLIE, ...)   # contenido visible del mazo
           .mi_descarte(...)                      # resto identificado
           .fetch_ultra_ball()                    # select TO_HAND via Ultra Ball
           .construir())
    eleccion = m.agent(obs)

El rival NO tiene contabilidad (su mazo es desconocido): sus zonas ocultas se
declaran como conteos (`op_zonas`).
"""

from collections import Counter
from pathlib import Path

from cg.api import (AreaType, CardType, EnergyType, OptionType, SelectContext,
                    SelectType, all_attack, all_card_data)

_ROOT = Path(__file__).resolve().parents[1]

# Datos de carta para defaults (HP maximo, deteccion de Pokemon).
_CARD_TABLE = {c.cardId: c for c in all_card_data()}
# Ataques por id: `menu_mano(con_ataque=True)` necesita el coste para emitir
# solo los ataques que el activo puede pagar (como hace el simulador).
_ATTACK_TABLE = {a.attackId: a for a in all_attack()}

# Energias abreviadas para specs legibles.
C = int(EnergyType.COLORLESS)
G = int(EnergyType.GRASS)

BASIC_GRASS = 1        # id de la Basic Grass Energy (deck.csv)
BOSS_ORDERS = 1182     # id de Boss's Orders (deck.csv)
ULTRA_BALL = 1121      # id de la Ultra Ball (deck.csv)
TEAL_MASK_OGERPON_EX = 96    # id del Teal Mask Ogerpon ex (habilidad Teal Dance)
FOREST_OF_VITALITY = 1261    # id del estadio propio (deck.csv)
GRAND_TREE = 1249      # id del estadio ACE SPEC de evolucion instantanea
_PREMIOS_DEFECTO = 6


class EstadoInconsistente(AssertionError):
    """El escenario declarado no cuadra con las 60 cartas de deck.csv."""


def _leer_deck_csv():
    csv = (_ROOT / "deck.csv").read_text().split("\n")
    return [int(csv[i]) for i in range(60)]


def pk(card_id, hp=None, max_hp=None, energias=(), fisicas=None,
       pre_evo=(), tools=(), aparecio=False):
    """Spec de un Pokemon en juego.

    energias: lista de EnergyType EFECTIVAS (con Meganium, 1 Grass fisica
        cuenta [G, G]). Un int N equivale a [G]*N.
    fisicas: numero de CARTAS de energia adjuntas (default: len(energias)).
        Para el lado propio consumen Basic Grass del pool.
    pre_evo: ids de las cartas pre-evolucion apiladas debajo.
    tools: ids de las herramientas adjuntas.
    """
    if isinstance(energias, int):
        energias = [G] * energias
    energias = list(energias)
    if fisicas is None:
        fisicas = len(energias)
    data = _CARD_TABLE.get(card_id)
    base_hp = data.hp if data is not None else 0
    if max_hp is None:
        max_hp = base_hp
    if hp is None:
        hp = max_hp
    return {
        "id": card_id, "hp": hp, "maxHp": max_hp, "energias": energias,
        "fisicas": fisicas, "pre_evo": list(pre_evo), "tools": list(tools),
        "aparecio": aparecio,
    }


def _como_spec(x):
    return x if isinstance(x, dict) else pk(x)


class Escenario:

    def __init__(self, turno=2, paso=1, tac=0, primer_jugador=0,
                 energia_jugada=False, partidario_jugado=False,
                 estadio_jugado=False, retirado=False, premios_propios=None):
        self._turno = turno
        self._paso = paso
        self._tac = tac
        self._primer_jugador = primer_jugador
        self._energia_jugada = energia_jugada
        self._partidario_jugado = partidario_jugado
        self._estadio_jugado = estadio_jugado
        self._retirado = retirado
        self._n_premios = (_PREMIOS_DEFECTO if premios_propios is None
                           else premios_propios)

        self._pool = Counter(_leer_deck_csv())
        self._serial_mio = iter(range(0, 60))
        self._serial_op = iter(range(60, 120))

        self._mi_activo = None
        self._mi_banca = []
        self._mi_mano = []
        self._mi_descarte = []
        self._mazo_visible = None
        self._estadio = None
        self._efecto = None

        self._op_activo_spec = None
        self._op_banca = []
        self._op_descarte = []
        self._op_mano = 0
        self._op_mazo = 30
        self._op_premios = 6

        self._select = None

    # ------------------------------------------------------------------
    # Contabilidad del pool propio
    # ------------------------------------------------------------------
    def _tomar(self, card_id, zona):
        if self._pool[card_id] <= 0:
            raise EstadoInconsistente(
                f"no quedan copias de la carta {card_id} en deck.csv para "
                f"colocar en {zona} (ya se usaron todas)")
        self._pool[card_id] -= 1
        return {"id": card_id, "playerIndex": 0, "serial": next(self._serial_mio)}

    def _pokemon_mio(self, spec):
        spec = _como_spec(spec)
        carta = self._tomar(spec["id"], "campo")
        e_cards = [self._tomar(BASIC_GRASS, "energia adjunta")
                   for _ in range(spec["fisicas"])]
        pre = [self._tomar(cid, "pre-evolucion") for cid in spec["pre_evo"]]
        tools = [self._tomar(cid, "herramienta") for cid in spec["tools"]]
        return {
            "id": spec["id"], "serial": carta["serial"], "playerIndex": 0,
            "hp": spec["hp"], "maxHp": spec["maxHp"],
            "appearThisTurn": spec["aparecio"],
            "energies": spec["energias"], "energyCards": e_cards,
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
            "energies": spec["energias"], "energyCards": e_cards,
            "tools": tools, "preEvolution": pre,
        }

    # ------------------------------------------------------------------
    # Zonas propias
    # ------------------------------------------------------------------
    def mi_activo(self, spec):
        self._mi_activo = self._pokemon_mio(spec)
        return self

    def mi_banca(self, *specs):
        self._mi_banca = [self._pokemon_mio(s) for s in specs]
        return self

    def mi_mano(self, *ids):
        self._mi_mano = [self._tomar(cid, "mano") for cid in ids]
        return self

    def mi_descarte(self, *ids):
        self._mi_descarte = [self._tomar(cid, "descarte") for cid in ids]
        return self

    def estadio(self, card_id, del_rival=False):
        """Estadio en mesa.

        `del_rival=True` para estadios que NO estan en deck.csv (los baja el
        rival): no consumen pool propio. Es el caso de Grand Tree, cuya
        habilidad es de uso compartido -- la usan los DOS jugadores.
        """
        if del_rival:
            self._estadio = {"id": card_id, "playerIndex": 1,
                             "serial": next(self._serial_op)}
        else:
            self._estadio = self._tomar(card_id, "estadio")
        return self

    def mazo(self, *ids):
        """Contenido VISIBLE del mazo propio (orden = orden del array)."""
        self._mazo_visible = [self._tomar(cid, "mazo") for cid in ids]
        return self

    def resto_al_descarte(self):
        """Manda al descarte todo el pool restante menos los premios.

        Requiere `mazo(...)` declarado antes (si no, no se sabria que parte
        del resto es mazo y que parte descarte). Comodo para barridos donde
        el contenido exacto del descarte no importa.
        """
        if self._mazo_visible is None:
            raise EstadoInconsistente(
                "resto_al_descarte() requiere haber declarado antes mazo(...)")
        sobran = sum(self._pool.values()) - self._n_premios
        if sobran < 0:
            raise EstadoInconsistente(
                f"quedan {sum(self._pool.values())} cartas en el pool, menos "
                f"que los {self._n_premios} premios: el escenario coloco de mas")
        for cid in sorted(self._pool.elements()):
            if sobran == 0:
                break
            self._mi_descarte.append(self._tomar(cid, "descarte"))
            sobran -= 1
        return self

    # ------------------------------------------------------------------
    # Zonas del rival (sin contabilidad: su mazo es desconocido)
    # ------------------------------------------------------------------
    def op_activo(self, spec):
        self._op_activo_spec = self._pokemon_op(spec)
        return self

    def op_banca(self, *specs):
        self._op_banca = [self._pokemon_op(s) for s in specs]
        return self

    def op_descarte(self, *ids):
        self._op_descarte = [{"id": cid, "playerIndex": 1,
                              "serial": next(self._serial_op)} for cid in ids]
        return self

    def op_zonas(self, mano=0, mazo=30, premios=6):
        self._op_mano = mano
        self._op_mazo = mazo
        self._op_premios = premios
        return self

    # ------------------------------------------------------------------
    # Selects
    # ------------------------------------------------------------------
    def fetch_ultra_ball(self, candidatos=None):
        """Select TO_HAND de la Ultra Ball sobre el mazo visible.

        candidatos: ids elegibles; por defecto, TODOS los Pokemon del mazo
        (comportamiento real de la Ultra Ball). Cada copia es una opcion.
        Consume una Ultra Ball del pool (la carta 'en efecto').
        """
        if self._mazo_visible is None:
            raise EstadoInconsistente(
                "fetch_ultra_ball() requiere haber declarado antes mazo(...)")
        self._efecto = self._tomar(ULTRA_BALL, "efecto (Ultra Ball en juego)")

        def es_candidato(cid):
            if candidatos is not None:
                return cid in candidatos
            data = _CARD_TABLE.get(cid)
            return data is not None and data.cardType == CardType.POKEMON

        opciones = [
            {"type": int(OptionType.CARD), "area": int(AreaType.DECK),
             "index": i, "playerIndex": 0}
            for i, carta in enumerate(self._mazo_visible)
            if es_candidato(carta["id"])]
        if not opciones:
            raise EstadoInconsistente(
                "fetch_ultra_ball() sin ningun candidato en el mazo declarado")
        self._select = {
            "type": int(SelectType.CARD),
            "context": int(SelectContext.TO_HAND),
            "minCount": 0, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": opciones,
            "deck": list(self._mazo_visible),
            "contextCard": None,
            "effect": self._efecto,
        }
        return self

    def menu_attach_energia(self):
        """Select MAIN minimo: adjuntar la 1a Basic Grass de la mano.

        Genera una opcion ATTACH por CADA Pokemon propio en juego (activo
        inPlayArea=4; banca inPlayArea=5/inPlayIndex=k) mas END, con el
        mismo esquema que el simulador real. Requiere una Basic Grass en
        mi_mano() y energia_jugada=False.
        """
        if self._energia_jugada:
            raise EstadoInconsistente(
                "menu_attach_energia() con energia_jugada=True no tendria "
                "opciones ATTACH")
        idx_e = next((i for i, c in enumerate(self._mi_mano)
                      if c["id"] == BASIC_GRASS), None)
        if idx_e is None:
            raise EstadoInconsistente(
                "menu_attach_energia() requiere una Basic Grass en mi_mano()")
        opciones = []
        if self._mi_activo is not None:
            opciones.append({"type": int(OptionType.ATTACH),
                             "area": int(AreaType.HAND), "index": idx_e,
                             "inPlayArea": int(AreaType.ACTIVE),
                             "inPlayIndex": 0})
        for k in range(len(self._mi_banca)):
            opciones.append({"type": int(OptionType.ATTACH),
                             "area": int(AreaType.HAND), "index": idx_e,
                             "inPlayArea": int(AreaType.BENCH),
                             "inPlayIndex": k})
        opciones.append({"type": int(OptionType.END)})
        self._select = {
            "type": int(SelectType.MAIN),
            "context": int(SelectContext.MAIN),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": opciones,
            "deck": None,
            "contextCard": None,
            "effect": None,
        }
        return self

    def menu_teal_dance(self):
        """Select MAIN con la HABILIDAD Teal Dance ademas del adjunte manual.

        Emite una opcion ABILITY (area ACTIVE/BENCH, index del slot) por cada
        Teal Mask Ogerpon ex propio en juego, las opciones ATTACH de la 1a
        Basic Grass de la mano y END, como el menu real de un turno en el que
        aun no se ha adjuntado energia.
        """
        idx_e = next((i for i, c in enumerate(self._mi_mano)
                      if c["id"] == BASIC_GRASS), None)
        if idx_e is None:
            raise EstadoInconsistente(
                "menu_teal_dance() requiere una Basic Grass en mi_mano(): "
                "Teal Dance adjunta una Planta DE LA MANO")
        opciones = []
        if (self._mi_activo is not None
                and self._mi_activo["id"] == TEAL_MASK_OGERPON_EX):
            opciones.append({"type": int(OptionType.ABILITY),
                             "area": int(AreaType.ACTIVE), "index": 0})
        for k, p in enumerate(self._mi_banca):
            if p["id"] == TEAL_MASK_OGERPON_EX:
                opciones.append({"type": int(OptionType.ABILITY),
                                 "area": int(AreaType.BENCH), "index": k})
        if not opciones:
            raise EstadoInconsistente(
                "menu_teal_dance() requiere un Teal Mask Ogerpon ex en juego")
        if not self._energia_jugada:
            if self._mi_activo is not None:
                opciones.append({"type": int(OptionType.ATTACH),
                                 "area": int(AreaType.HAND), "index": idx_e,
                                 "inPlayArea": int(AreaType.ACTIVE),
                                 "inPlayIndex": 0})
            for k in range(len(self._mi_banca)):
                opciones.append({"type": int(OptionType.ATTACH),
                                 "area": int(AreaType.HAND), "index": idx_e,
                                 "inPlayArea": int(AreaType.BENCH),
                                 "inPlayIndex": k})
        opciones.append({"type": int(OptionType.END)})
        self._select = {
            "type": int(SelectType.MAIN),
            "context": int(SelectContext.MAIN),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": opciones,
            "deck": None,
            "contextCard": None,
            "effect": None,
        }
        return self

    def menu_mano(self, con_retirada=False, con_adjunte=False,
                  con_ataque=False):
        """Select MAIN generico: una opcion PLAY por cada carta de la mano, mas
        (opcionalmente) las ATTACH de la 1a Basic Grass, RETREAT y/o los ATTACK
        del activo, mas END.

        Pensado para escenarios donde lo que se mide es QUE carta se juega, sin
        el ruido de un menu completo del simulador. `con_ataque` emite un ATTACK
        por cada ataque del activo cuyo coste de energia puede pagar YA (mismo
        criterio que el simulador), para poder medir ataque-vs-retirada.
        """
        opciones = [{"type": int(OptionType.PLAY), "index": i}
                    for i in range(len(self._mi_mano))]
        if con_adjunte:
            idx_e = next((i for i, c in enumerate(self._mi_mano)
                          if c["id"] == BASIC_GRASS), None)
            if idx_e is None:
                raise EstadoInconsistente(
                    "menu_mano(con_adjunte=True) requiere una Basic Grass en "
                    "mi_mano()")
            if self._mi_activo is not None:
                opciones.append({"type": int(OptionType.ATTACH),
                                 "area": int(AreaType.HAND), "index": idx_e,
                                 "inPlayArea": int(AreaType.ACTIVE),
                                 "inPlayIndex": 0})
            for k in range(len(self._mi_banca)):
                opciones.append({"type": int(OptionType.ATTACH),
                                 "area": int(AreaType.HAND), "index": idx_e,
                                 "inPlayArea": int(AreaType.BENCH),
                                 "inPlayIndex": k})
        if con_ataque:
            if self._mi_activo is None:
                raise EstadoInconsistente(
                    "menu_mano(con_ataque=True) requiere mi_activo(...)")
            _act_data = _CARD_TABLE.get(self._mi_activo["id"])
            _disp = len(self._mi_activo["energies"])
            for _aid in (getattr(_act_data, 'attacks', None) or ()):
                _atk = _ATTACK_TABLE.get(_aid)
                if _atk is None:
                    continue
                if len(getattr(_atk, 'energies', None) or ()) > _disp:
                    continue
                opciones.append({"type": int(OptionType.ATTACK),
                                 "attackId": _aid})
        if con_retirada:
            opciones.append({"type": int(OptionType.RETREAT)})
        opciones.append({"type": int(OptionType.END)})
        self._select = {
            "type": int(SelectType.MAIN),
            "context": int(SelectContext.MAIN),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": opciones,
            "deck": None,
            "contextCard": None,
            "effect": None,
        }
        return self

    def fetch_descarte(self, efecto_id, cuantas=1, solo=None):
        """Select TO_HAND de una carta de RECUPERACION (Night Stretcher, Lana's
        Aid...) sobre el descarte propio ya declarado. Consume una copia de
        `efecto_id` del pool (la carta 'en efecto').

        `cuantas` es el `maxCount` del menu: 1 para Night Stretcher, 3 para
        Lana's Aid. `solo` restringe las opciones a esos ids del descarte, como
        hace el simulador con los filtros de la carta (Lana's Aid solo ofrece
        Pokemon SIN Regla y Energias Basicas: nada de ex).
        """
        if not self._mi_descarte:
            raise EstadoInconsistente(
                "fetch_descarte() requiere haber declarado antes mi_descarte(...)")
        self._efecto = self._tomar(efecto_id, "efecto (recuperacion en juego)")
        opciones = [{"type": int(OptionType.CARD),
                     "area": int(AreaType.DISCARD), "index": i,
                     "playerIndex": 0}
                    for i, carta in enumerate(self._mi_descarte)
                    if solo is None or carta["id"] in solo]
        if not opciones:
            raise EstadoInconsistente(
                "fetch_descarte(solo=...) no deja ninguna opcion en el descarte")
        self._select = {
            "type": int(SelectType.CARD),
            "context": int(SelectContext.TO_HAND),
            "minCount": 1, "maxCount": max(1, min(cuantas, len(opciones))),
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": opciones,
            "deck": None,
            "contextCard": None,
            "effect": self._efecto,
        }
        return self

    def objetivo_carga_habilidad(self, banca_idx=None):
        """Select ATTACH_FROM: a QUE Pokemon propio adjunta la Planta una
        habilidad de carga ya activada (Ripening Charge de Hydrapple ex...).

        Emite una opcion CARD por el activo (area ACTIVE) y una por cada slot de
        banca (area BENCH), igual que el simulador real. El portador de la
        habilidad es el activo o, si se indica `banca_idx`, ese slot de banca:
        ya esta en juego, asi que NO consume otra copia del pool.
        """
        if self._mi_activo is None:
            raise EstadoInconsistente(
                "objetivo_carga_habilidad() requiere mi_activo(...)")
        portador = (self._mi_activo if banca_idx is None
                    else self._mi_banca[banca_idx])
        self._efecto = {"id": portador["id"], "playerIndex": 0,
                        "serial": portador["serial"]}
        opciones = [{"type": int(OptionType.CARD),
                     "area": int(AreaType.ACTIVE), "index": 0,
                     "playerIndex": 0}]
        opciones += [{"type": int(OptionType.CARD),
                      "area": int(AreaType.BENCH), "index": k,
                      "playerIndex": 0}
                     for k in range(len(self._mi_banca))]
        self._select = {
            "type": int(SelectType.CARD),
            "context": int(SelectContext.ATTACH_FROM),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": opciones,
            "deck": None,
            "contextCard": None,
            "effect": self._efecto,
        }
        return self

    def promocion_tras_retirada(self):
        """Select SWITCH: elegir quien SUBE de la banca al retirar el activo.

        Es el prompt que el simulador emite justo despues de pagar el coste de
        retirada (verificado con `cg.api.search_begin/search_step`: contexto
        SWITCH, opciones CARD sobre la BANCA propia). Se distingue de
        `promocion_desde_banca` (TO_ACTIVE), que es la promocion FORZADA tras un
        KO y puede caer en el turno rival.
        """
        if not self._mi_banca:
            raise EstadoInconsistente(
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
                       for k in range(len(self._mi_banca))],
            "deck": None,
            "contextCard": None,
            "effect": None,
        }
        return self

    def promocion_desde_banca(self):
        """Select TO_ACTIVE: promover un Pokemon de la banca tras retirar/KO."""
        if not self._mi_banca:
            raise EstadoInconsistente(
                "promocion_desde_banca() requiere mi_banca(...)")
        self._select = {
            "type": int(SelectType.CARD),
            "context": int(SelectContext.TO_ACTIVE),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": [{"type": int(OptionType.CARD),
                        "area": int(AreaType.BENCH), "index": k,
                        "playerIndex": 0}
                       for k in range(len(self._mi_banca))],
            "deck": None,
            "contextCard": None,
            "effect": None,
        }
        return self

    def menu_gusteo(self):
        """Select de OBJETIVO de Boss's Orders: una opcion por cada Pokemon de
        la BANCA RIVAL. Consume una copia de Boss's Orders del pool (la carta
        'en efecto', ya jugada) y marca el Supporter como gastado."""
        if not self._op_banca:
            raise EstadoInconsistente("menu_gusteo() requiere op_banca(...)")
        self._tomar(BOSS_ORDERS, "efecto")
        self._partidario_jugado = True
        self._select = {
            "type": int(SelectType.CARD),
            "context": int(SelectContext.SWITCH),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": [{"type": int(OptionType.CARD),
                        "area": int(AreaType.BENCH), "index": k,
                        "playerIndex": 1}
                       for k in range(len(self._op_banca))],
            "deck": None,
            "contextCard": None,
            "effect": {"id": BOSS_ORDERS, "playerIndex": 0, "serial": 500},
        }
        return self

    def menu_grand_tree(self, con_forest=False, con_evolucion_mano=False):
        """Select MAIN con la HABILIDAD del estadio Grand Tree.

        Emite la opcion ABILITY sobre el area STADIUM (como hace el simulador
        con las habilidades de estadio), opcionalmente el PLAY de una Forest of
        Vitality de la mano y/o las EVOLVE disponibles desde la mano, y END.
        """
        if self._estadio is None or self._estadio["id"] != GRAND_TREE:
            raise EstadoInconsistente(
                "menu_grand_tree() requiere estadio(GRAND_TREE, ...)")
        opciones = [{"type": int(OptionType.ABILITY),
                     "area": int(AreaType.STADIUM), "index": 0}]
        if con_forest:
            idx = next((i for i, c in enumerate(self._mi_mano)
                        if c["id"] == FOREST_OF_VITALITY), None)
            if idx is None:
                raise EstadoInconsistente(
                    "menu_grand_tree(con_forest=True) requiere una Forest of "
                    "Vitality en mi_mano()")
            opciones.append({"type": int(OptionType.PLAY), "index": idx})
        if con_evolucion_mano:
            en_juego = ([self._mi_activo] if self._mi_activo else []) + self._mi_banca
            for i, c in enumerate(self._mi_mano):
                data = _CARD_TABLE.get(c["id"])
                pre = getattr(data, "evolvesFrom", None) if data else None
                if not pre:
                    continue
                for j, p in enumerate(en_juego):
                    p_data = _CARD_TABLE.get(p["id"])
                    if p_data is None or p_data.name != pre:
                        continue
                    opciones.append({
                        "type": int(OptionType.EVOLVE),
                        "area": int(AreaType.HAND), "index": i,
                        "inPlayArea": int(AreaType.ACTIVE if j == 0
                                          else AreaType.BENCH),
                        "inPlayIndex": 0 if j == 0 else j - 1})
        opciones.append({"type": int(OptionType.END)})
        self._select = {
            "type": int(SelectType.MAIN),
            "context": int(SelectContext.MAIN),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": opciones,
            "deck": None,
            "contextCard": None,
            "effect": None,
        }
        return self

    def seleccion_grand_tree_en_juego(self):
        """Sub-seleccion "que Pokemon MIO evoluciona" servida por Grand Tree.

        Una opcion CARD por cada Pokemon propio en juego, con `select.effect`
        apuntando al estadio.
        """
        if self._estadio is None or self._estadio["id"] != GRAND_TREE:
            raise EstadoInconsistente(
                "seleccion_grand_tree_* requiere estadio(GRAND_TREE, ...)")
        opciones = []
        if self._mi_activo is not None:
            opciones.append({"type": int(OptionType.CARD),
                             "area": int(AreaType.ACTIVE), "index": 0,
                             "playerIndex": 0})
        for k in range(len(self._mi_banca)):
            opciones.append({"type": int(OptionType.CARD),
                             "area": int(AreaType.BENCH), "index": k,
                             "playerIndex": 0})
        self._select = {
            "type": int(SelectType.CARD),
            "context": int(SelectContext.EVOLVES_FROM),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": opciones,
            "deck": None,
            "contextCard": None,
            "effect": dict(self._estadio),
        }
        return self

    def seleccion_grand_tree_mazo(self, *ids):
        """Sub-seleccion "que carta traigo del mazo" servida por Grand Tree.

        `ids` son las cartas OFRECIDAS (ya declaradas en `mazo(...)`); se
        emiten como opciones CARD sobre el area DECK.
        """
        if self._estadio is None or self._estadio["id"] != GRAND_TREE:
            raise EstadoInconsistente(
                "seleccion_grand_tree_* requiere estadio(GRAND_TREE, ...)")
        if self._mazo_visible is None:
            raise EstadoInconsistente(
                "seleccion_grand_tree_mazo() requiere mazo(...) declarado")
        opciones = []
        for cid in ids:
            idx = next((i for i, c in enumerate(self._mazo_visible)
                        if c["id"] == cid), None)
            if idx is None:
                raise EstadoInconsistente(
                    f"la carta {cid} no esta en el mazo declarado")
            opciones.append({"type": int(OptionType.CARD),
                             "area": int(AreaType.DECK), "index": idx,
                             "playerIndex": 0})
        self._select = {
            "type": int(SelectType.CARD),
            "context": int(SelectContext.TO_FIELD),
            "minCount": 1, "maxCount": 1,
            "remainDamageCounter": 0, "remainEnergyCost": 0,
            "option": opciones,
            "deck": list(self._mazo_visible),
            "contextCard": None,
            "effect": dict(self._estadio),
        }
        return self

    # ------------------------------------------------------------------
    # Construccion final
    # ------------------------------------------------------------------
    def construir(self):
        if self._mi_activo is None:
            raise EstadoInconsistente("falta mi_activo(...)")
        if self._op_activo_spec is None:
            raise EstadoInconsistente("falta op_activo(...)")
        if self._select is None:
            raise EstadoInconsistente(
                "falta el select (p.ej. fetch_ultra_ball())")

        restante = sum(self._pool.values())
        if self._mazo_visible is not None:
            # Con mazo declarado, el sobrante son exactamente los premios.
            if restante != self._n_premios:
                sobra = {k: v for k, v in self._pool.items() if v > 0}
                raise EstadoInconsistente(
                    f"la contabilidad no cuadra: con el mazo declarado deben "
                    f"sobrar exactamente {self._n_premios} cartas (premios "
                    f"boca abajo) y sobran {restante}: {sobra}. Ajusta "
                    f"descarte/mano/mazo o usa resto_al_descarte().")
            deck_count = len(self._mazo_visible)
        else:
            deck_count = restante - self._n_premios
            if deck_count < 0:
                raise EstadoInconsistente(
                    f"quedan {restante} cartas sin colocar, menos que los "
                    f"{self._n_premios} premios: el escenario coloco de mas")

        mi_player = {
            "active": [self._mi_activo],
            "bench": self._mi_banca,
            "benchMax": 5,
            "deckCount": deck_count,
            "discard": self._mi_descarte,
            "prize": [None] * self._n_premios,
            "handCount": len(self._mi_mano),
            "hand": self._mi_mano,
            "poisoned": False, "burned": False, "asleep": False,
            "paralyzed": False, "confused": False,
        }
        op_player = {
            "active": [self._op_activo_spec],
            "bench": self._op_banca,
            "benchMax": 5,
            "deckCount": self._op_mazo,
            "discard": self._op_descarte,
            "prize": [None] * self._op_premios,
            "handCount": self._op_mano,
            "hand": None,
            "poisoned": False, "burned": False, "asleep": False,
            "paralyzed": False, "confused": False,
        }
        current = {
            "turn": self._turno,
            "turnActionCount": self._tac,
            "yourIndex": 0,
            "firstPlayer": self._primer_jugador,
            "supporterPlayed": self._partidario_jugado,
            "stadiumPlayed": self._estadio_jugado,
            "energyAttached": self._energia_jugada,
            "retreated": self._retirado,
            "result": -1,
            "stadium": [self._estadio] if self._estadio else [],
            "looking": None,
            "players": [mi_player, op_player],
        }
        return {
            "step": self._paso,
            "remainingOverageTime": 60000,
            "logs": [],
            "select": self._select,
            "current": current,
        }
