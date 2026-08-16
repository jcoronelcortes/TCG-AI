"""Cuantas veces el asiento de delante ES la partida, y cuantas cambia la jugada.

LA FRASE (`THE_SEAT_THAT_LOSES_THE_GAME_YIELDS_TO_THE_WALL`). Si la respuesta
proyectada de su activo NOQUEA al cuerpo de delante y ese cadaver paga TODO lo
que les queda de monton, quedarse pierde la partida; si en la banca hay uno que
aguanta ese mismo ataque, el asiento es de ese.

SON DOS MENUS Y LA FRASE ES LA MISMA EN LOS DOS, que es justo el modo de fallo
que este repositorio lleva registrado ("arreglar una rama de un par y dejar a su
gemela es como se perdio este turno"):

  * LA RETIRADA -- `_wall_that_outlasts_the_losing_reply`, peldaño 6750 de
    `ptcg/turn/options/retreat.py`, un escalon por encima de
    `_grd_prefer_attack` ("el activo puede atacar y nadie noquea -> ataca"),
    que es quien se comia estos tableros.
  * LA PROMOCION -- `_losing_seat_survivor`, `PROMO_LOSING_SEAT_WALL` (12000) al
    final de la cadena de `ptcg/turn/options/card.py`, por encima de las
    reservas que guardan un cuerpo en la banca PARA LOS TURNOS QUE VIENEN. A su
    match point no vienen.

EL REGISTRO es `records/registro_009_pasos_088_hasta_110.json` paso 110
(episodio 93638940 vs Mega Froslass ex / Mega Starmie ex, PERDIDA): Tapu Bulu de
90 delante, su monton a UN premio, Resentful Refrain proyectado -- con la tabla
de escalado -- en 150, y un Hydrapple ex de 330/330 en la banca con la retirada
ya pagada.

POR QUE UN CENSO. El tablero es raro por construccion (hace falta su match point
Y una respuesta letal Y un superviviente en la banca), asi que ningun winrate con
el suelo de ruido de este banco -- medio punto -- puede arbitrarlo. Lo que se
puede contar es cuantas veces aparece, cuantas veces cambia la jugada y si toca
algo que no deberia tocar.

QUE CUENTA, por menu PRINCIPAL con retirada ofrecida:

    asked    menus con una opcion de RETIRADA sobre la mesa.
    fires    ...de esos, en cuantos la bandera esta encendida
             (`_losing_seat_pivot`): el tablero entero de la regla.
    flips    ...y en cuantos CAMBIA lo que el agente juega. Se mide replayando
             la observacion entera dos veces, con la bandera puesta y quitada,
             no comparando puntuaciones: lo que decide el turno son los tiers de
             `finalize.py`, no el argmax crudo.
    escapes  flips en los que la eleccion nueva NO es la retirada. Tiene que ser
             CERO: la regla solo levanta un veto de un peldaño, y si mueve otra
             cosa esta tocando lo que no es suyo.
    seats    promociones SIMULADAS justo despues de cada disparo: abrir la
             retirada no compra nada si el otro menu sienta a un cadaver.
    doomed   ...de esas, las que suben un cuerpo que tampoco aguanta. Este
             contador es el que descubrio la segunda mitad de la frase.

Y la mitad de la PROMOCION, sobre los menus REALES del juego (SWITCH tras
nuestra retirada y TO_ACTIVE tras un noqueo):

    P.asked  menus de promocion.
    P.fires  ...con la eleccion en juego: alguien de la banca cae a una
             respuesta que cierra la partida y alguien la aguanta
             (`_losing_seat_choice`).
    P.flips  ...y el asiento cambia con la bandera.
    P.saved  ...hacia un cuerpo que AGUANTA. Tiene que ser IGUAL a P.flips: es
             la invariante entera de la regla, que solo levanta supervivientes.

LO MEDIDO (16 de agosto de 2026, LAS DOS MITADES PUESTAS):

    LA RETIRADA
    corpus congelado   931 menus, fires   3 (0,32 %), flips 0, escapes 0
    registros locales   42 menus, fires   6,           flips 1  <- el hallazgo
    self-play vs crustle_wall_1                400: fires 72 (0,86 %), flips 15
    self-play vs mega_starmie_1                400: fires 64 (0,97 %), flips  8
    self-play vs mega_lopunny_mega_froslass_1  250: fires  6 (0,15 %), flips  0
    self-play vs alakazam_1 / dragapult_1      400: fires  0  -> inerte

    Todo flip observado es ATACAR, JUGAR o PASAR -> RETIRARSE, que es la frase.
    Y `doomed` = **0** en todas las corridas desde que existe la segunda mitad:
    era 2 de 19 vs crustle antes de escribirla.

    LA PROMOCION
    corpus congelado    180 menus, fires  6 (3,33 %), flips  0
    self-play vs crustle_wall_1     1528 menus, fires 72 (4,71 %), flips 20
    self-play vs mega_starmie_1      908 menus, fires 33 (3,63 %), flips  3
    self-play vs alakazam_1          920 menus, fires  2 (0,22 %), flips  0

    **P.saved == P.flips en todas**: cada asiento que la regla mueve va a un
    cuerpo que aguanta la respuesta. Esa igualdad es la invariante entera.

EL TABLERO QUE OBLIGO A ESCRIBIR LA SEGUNDA MITAD lo encontro este censo, no un
humano leyendo una partida: `doomed` marcaba 2 de 19 vs `crustle_wall_1`. Esta
capturado en
`tests/fixtures/crustle_their_match_point_the_engine_yields_the_seat.json` --
turno 23, su monton a UNO, su Cornerstone Mask Ogerpon ex pegando 140, y de
nuestra banca solo el Meganium de 160/160 aguanta. Estaba **vetado a
SCORE_NEVER** ("la linea del Meganium no sube a activo", cuya unica exencion esta
escrita para la promocion FORZADA), asi que el asiento se lo llevo un Dipplin de
80 con -4745: el menos malo de una mesa entera de negativos.

Y EL WINRATE NO ARBITRA NINGUNA DE LAS DOS, como se esperaba de disparos del
1-5 %. A 1500 partidas por brazo: `crustle_wall_1` **-0,7 / +2,1 / +0,2**,
`mega_starmie_1` **+1,1 / -1,5** (y **-0,8 / +2,3 / -1,0** con solo la primera
mitad, con el diferencial de premios plano: +2,27 vs +2,29, +2,49 vs +2,35,
+2,31 vs +2,35), y la lista del propio registro **+0,1** sobre un matchup
saturado al 97 %. El signo cambia entre corridas: eso es el suelo de ruido del
banco, no una lectura. Lo que arbitra es el censo.

Uso:
    python utils/census_the_seat_that_loses_the_game.py --frozen
    python utils/census_the_seat_that_loses_the_game.py --records records
    python utils/census_the_seat_that_loses_the_game.py --games 200 \\
        --opponent deck/real_opponents/mega_lopunny_mega_froslass_1.csv
"""

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "utils"), str(_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m  # noqa: E402
from cg.api import OptionType, SelectContext  # noqa: E402
from golden_corpus import reset_agent  # noqa: E402

# La lista contra la que el tablero aparece: es la del registro, y la unica de
# `deck/real_opponents/` cuyo remate escala con NUESTRA mano.
DEFAULT_OPPONENT = "deck/real_opponents/mega_lopunny_mega_froslass_1.csv"


class Tally:
    def __init__(self):
        self.asked = 0
        self.fires = 0
        self.flips = 0
        self.escapes = 0
        self.seats = 0
        self.seats_doomed = 0
        # La mitad de la PROMOCION, contada sobre los menus reales del juego
        # (SWITCH tras una retirada y TO_ACTIVE tras un noqueo), no sobre los
        # simulados de `seats`.
        self.promo_asked = 0
        self.promo_fires = 0
        self.promo_flips = 0
        self.promo_rescued = 0
        self.boards = []

    def report(self):
        print(f"  asked   {self.asked:5d}  menus con retirada ofrecida")
        print(f"  fires   {self.fires:5d}  ...con el asiento perdedor "
              f"({100.0 * self.fires / max(1, self.asked):.2f} %)")
        print(f"  flips   {self.flips:5d}  ...y la jugada cambia")
        print(f"  escapes {self.escapes:5d}  ...hacia algo que NO es la retirada"
              f"  {'OK' if not self.escapes else '<-- REVISAR'}")
        print(f"  seats   {self.seats:5d}  promociones simuladas tras el pivote")
        print(f"  doomed  {self.seats_doomed:5d}  ...que suben un cuerpo que NO "
              f"aguanta  {'OK' if not self.seats_doomed else '<-- REVISAR'}")
        print(f"  P.asked {self.promo_asked:5d}  menus de PROMOCION reales")
        print(f"  P.fires {self.promo_fires:5d}  ...con la eleccion en juego "
              f"({100.0 * self.promo_fires / max(1, self.promo_asked):.2f} %)")
        print(f"  P.flips {self.promo_flips:5d}  ...y el asiento cambia")
        print(f"  P.saved {self.promo_rescued:5d}  ...hacia un cuerpo que "
              f"AGUANTA  {'OK' if self.promo_rescued == self.promo_flips else '<-- REVISAR'}")
        for b in self.boards[:20]:
            print(f"    {b}")


def _fires(obs):
    """True si `_losing_seat_pivot` esta encendida en ESTE menu."""
    seen = []
    original = m.score_option

    def spy(ctx, option, score):
        if not seen:
            seen.append(bool(getattr(ctx, "_losing_seat_pivot", False)))
        return original(ctx, option, score)

    m.score_option = spy
    try:
        m.agent(obs)
    finally:
        m.score_option = original
    return seen[0] if seen else False


def _choice(obs, flag):
    prev = m.THE_SEAT_THAT_LOSES_THE_GAME_YIELDS_TO_THE_WALL
    m.THE_SEAT_THAT_LOSES_THE_GAME_YIELDS_TO_THE_WALL = flag
    try:
        return m.agent(obs)
    finally:
        m.THE_SEAT_THAT_LOSES_THE_GAME_YIELDS_TO_THE_WALL = prev


def _retreat_index(obs):
    for i, o in enumerate(obs.get("select", {}).get("option", [])):
        if o.get("type") == int(OptionType.RETREAT):
            return i
    return None


def _fires_promo(obs):
    """`(en_juego, superviviente)` de ESTE menu de promocion."""
    seen = []
    original = m.score_option

    def spy(ctx, option, score):
        if not seen:
            seen.append((bool(getattr(ctx, "_losing_seat_choice", False)),
                         getattr(ctx, "_losing_seat_survivor", None)))
        return original(ctx, option, score)

    m.score_option = spy
    try:
        m.agent(obs)
    finally:
        m.score_option = original
    return seen[0] if seen else (False, None)


def census_promotion(obs, tally, label=""):
    """Un menu de PROMOCION real -- SWITCH tras nuestra retirada o TO_ACTIVE
    tras un noqueo. Mide la otra mitad de la frase: cuando la eleccion esta en
    juego (alguien cae, alguien aguanta), a quien se sienta con la bandera y
    sin ella."""
    import copy
    tally.promo_asked += 1
    on_flag, survivor = _fires_promo(copy.deepcopy(obs))
    if not on_flag:
        return
    tally.promo_fires += 1
    on = _choice(copy.deepcopy(obs), True)
    off = _choice(copy.deepcopy(obs), False)
    if on == off:
        return
    tally.promo_flips += 1
    cur = obs["current"]
    bench = cur["players"][cur["yourIndex"]]["bench"]

    class _B:
        def __init__(s, d):
            s.id = d["id"]; s.hp = d.get("hp"); s.maxHp = d.get("maxHp")
            s.energies = list(d.get("energies") or [])
            s.energyCards = []; s.tools = []
    seated = bench[obs["select"]["option"][on[0]]["index"]]
    if seated is not None and survivor is not None and survivor(_B(seated)):
        tally.promo_rescued += 1
    tally.boards.append(
        f"{label}: PROMOCION {off} -> {on} "
        f"({seated and seated['id']}, {seated and seated.get('hp')} PV)")


def census_observation(obs, tally, label=""):
    """Un menu. La observacion se replaya ENTERA dos veces: la eleccion del
    agente es lo unico que dice si la regla cambia algo."""
    select = obs.get("select") or {}
    if select.get("context") in (int(SelectContext.SWITCH),
                                 int(SelectContext.TO_ACTIVE)):
        census_promotion(obs, tally, label)
        return
    if select.get("context") != int(SelectContext.MAIN):
        return
    idx = _retreat_index(obs)
    if idx is None:
        return
    tally.asked += 1
    import copy
    if not _fires(copy.deepcopy(obs)):
        return
    tally.fires += 1
    on = _choice(copy.deepcopy(obs), True)
    off = _choice(copy.deepcopy(obs), False)
    if on == off:
        return
    tally.flips += 1
    if on != [idx]:
        tally.escapes += 1
    opts = obs["select"]["option"]

    def _name(choice):
        if not choice:
            return "?"
        o = opts[choice[0]]
        return OptionType(o["type"]).name
    tally.boards.append(f"{label}: {_name(off)}{off} -> {_name(on)}{on} "
                        f"(retirada = [{idx}])")
    _census_the_promotion(obs, tally, label)


def _census_the_promotion(obs, tally, label):
    """LAS DOS MITADES TIENEN QUE DECIR LO MISMO.

    Abrir la retirada no compra nada si el menu de PROMOCION -- que es otro
    `agent()`, con su propia escalera -- sienta a un cuerpo que cae al mismo
    golpe. Aqui se fabrica el SWITCH que el simulador emite justo despues de
    cobrar el coste (con el peaje ya pagado, como hace `promote_after_retreat`
    de `tests/state_builder.py`) y se comprueba que el cuerpo que sube es uno de
    los que aguantan.

    NO ES UNA REGLA, ES UNA MEDIDA. Si algun dia sale distinto de cero, la
    correccion es la mitad que falta: hoy la escalera de promocion ya ordena por
    supervivencia y por vida, y estos son los tableros donde eso se comprueba.
    """
    import copy
    from cg.api import AreaType, SelectContext as _SC, SelectType
    from ptcg.calc.damage import (_op_active_attack_damage_to,
                                  _wall_that_outlasts_the_losing_reply)

    obs = copy.deepcopy(obs)
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]
    if not mine.get("active") or not mine["active"][0] or not mine.get("bench"):
        return
    active = mine["active"][0]
    mine["discard"] = list(mine.get("discard") or []) + list(
        active.get("energyCards") or [])
    active["energyCards"], active["energies"] = [], []
    cur["retreated"] = True
    obs["select"] = {
        "type": int(SelectType.CARD), "context": int(_SC.SWITCH),
        "minCount": 1, "maxCount": 1,
        "remainDamageCounter": 0, "remainEnergyCost": 0,
        "option": [{"type": int(OptionType.CARD), "area": int(AreaType.BENCH),
                    "index": k, "playerIndex": 0}
                   for k in range(len(mine["bench"]))],
        "deck": None, "contextCard": None, "effect": None,
    }
    try:
        choice = m.agent(obs)[0]
    except Exception:
        return
    seated = mine["bench"][choice]
    if seated is None:
        return
    tally.seats += 1

    # Aguanta o no, con la misma lectura que abrio la retirada.
    class _P:
        def __init__(self, d):
            self.id = d["id"]
            self.hp = d.get("hp")
            self.maxHp = d.get("maxHp")
            self.energies = list(d.get("energies") or [])
            self.energyCards = []
            self.tools = []

    reply = _op_active_attack_damage_to(
        _P(theirs["active"][0]), _P(seated), theirs.get("handCount"),
        scaled=True)
    if reply >= (seated.get("hp") or 0):
        tally.seats_doomed += 1
        alt = ", ".join(
            f"{b['id']}:{b.get('hp')}vs"
            f"{_op_active_attack_damage_to(_P(theirs['active'][0]), _P(b), theirs.get('handCount'), scaled=True)}"
            for b in mine["bench"] if b)
        tally.boards.append(
            f"{label}: PROMOCION CONDENADA -> {seated['id']} "
            f"({seated.get('hp')} PV contra {reply}) | banca: {alt} "
            f"| su activo {theirs['active'][0]['id']}")


def census_records(records, tally):
    for name, log in sorted(records.items()):
        reset_agent(m)
        for step in log.get("steps", []):
            for entry in step:
                obs = (entry or {}).get("observation") or {}
                # SOLO los items ACTIVE, como el corpus dorado: la entrada del
                # otro asiento lleva una copia rancia de nuestro tablero y
                # contarla multiplica un mismo menu por los turnos que dure.
                if (entry or {}).get("status") != "ACTIVE" or not obs.get("select"):
                    continue
                try:
                    census_observation(obs, tally,
                                       f"{name} paso {obs.get('step')}")
                except Exception:
                    continue


def _local_records(directory):
    out = {}
    for path in sorted(Path(directory).glob("registro_*.json")):
        out[path.name] = json.loads(path.read_text(encoding="utf-8"))
    return out


def census_selfplay(games, opponent, tally):
    """Partidas completas, censando el menu ANTES de que el agente lo juegue.

    El bot lleva la lista rival y nosotros el mazo de `deck.csv`. La partida se
    juega con la bandera PUESTA (el arbol de hoy) y cada menu se replaya aparte
    con las dos: medir la rama apagada jugando otra partida no compara los
    mismos tableros, porque en cuanto una decision cambia las dos partidas ya no
    son la misma.
    """
    import selfplay as sp
    from opponent_bot import OpponentBot
    deck_op = sp.read_deck(opponent) if opponent else None
    real_agent = m.agent

    class _Seat:
        """Nuestro asiento: censa y luego contesta con el agente de verdad."""

        @staticmethod
        def agent(obs):
            try:
                census_observation(obs, tally, "selfplay")
            except Exception:
                pass
            return real_agent(obs)

    for _ in range(games):
        reset_agent(m)
        try:
            sp.play_game(_Seat, OpponentBot(), deck1=deck_op)
        except Exception as exc:      # una partida rota no es un censo roto
            print(f"  (partida descartada: {type(exc).__name__})")
            continue


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--records", default=None)
    ap.add_argument("--frozen", action="store_true")
    ap.add_argument("--games", type=int, default=0)
    ap.add_argument("--opponent", default=DEFAULT_OPPONENT)
    args = ap.parse_args(argv)

    tally = Tally()
    if args.frozen:
        import golden_corpus as gc
        print("CORPUS CONGELADO")
        census_records(gc.frozen_records(), tally)
        tally.report()
        tally = Tally()
    if args.records:
        print(f"REGISTROS LOCALES ({args.records})")
        census_records(_local_records(args.records), tally)
        tally.report()
        tally = Tally()
    if args.games:
        print(f"SELF-PLAY ({args.games} partidas vs {args.opponent})")
        census_selfplay(args.games, args.opponent, tally)
        tally.report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
