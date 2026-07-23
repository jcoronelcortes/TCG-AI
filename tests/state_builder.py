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
                    SelectType, all_card_data)

_ROOT = Path(__file__).resolve().parents[1]

# Datos de carta para defaults (HP maximo, deteccion de Pokemon).
_CARD_TABLE = {c.cardId: c for c in all_card_data()}

# Energias abreviadas para specs legibles.
C = int(EnergyType.COLORLESS)
G = int(EnergyType.GRASS)

BASIC_GRASS = 1        # id de la Basic Grass Energy (deck.csv)
ULTRA_BALL = 1121      # id de la Ultra Ball (deck.csv)
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

    def estadio(self, card_id):
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
