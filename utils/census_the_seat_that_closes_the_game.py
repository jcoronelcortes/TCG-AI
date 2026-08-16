"""Cuantas promociones forzadas son NUESTRO match point, y por cuanto se deciden.

LA FRASE (`THE_SEAT_THAT_CLOSES_THE_GAME_IS_A_GUARANTEE`,
`PROMO_CLOSER_SEAT`). Cuando nuestro monton de premios lo paga entero el activo
rival (`_promo_ko_wins_the_game`) y `_promote_setup_ko_attacker` nombra un cuerpo
que esta a UNA carga de ese noqueo, ese cuerpo no "cambia bien": TERMINA LA
PARTIDA, y la termina en nuestro turno, que va primero -- la promocion resuelve
al final del suyo. Todo lo que compite con el en esa cadena (el last stand 9450,
el muro barato 8500+hp/10, el atacante que puede retirarse 9200, el peaje del
Tera -500, el doomed de match point -6000, el frente entre los que noquean -1200)
es un argumento sobre llegar vivo a un turno POSTERIOR, y no hay ninguno.

EL REGISTRO es `records/registro_013_pasos_156_hasta_174.json` (episodio
93579160 vs Alakazam, PERDIDA), su ultimo menu: Alakazam a 140/140, nuestro
monton a UN premio, un Meganium en banca con un Grass fisico -- dos simbolos bajo
su propio Wild Growth, a una carta de los cuatro de Solar Beam -- y una Lana's
Aid en mano que saca ese Grass del descarte. El selector lo nombro y el asiento
se decidio igualmente por TRESCIENTOS puntos de desempate generico: 9850 del
Meganium contra 9550 de un Fezandipiti ex de 210 sin energias.

POR QUE UN CENSO Y NO UN WINRATE. El corpus congelado -- cincuenta partidas, 3580
decisiones -- mueve CERO decisiones con la bandera puesta, y el corpus local
tampoco: la eleccion de ese tablero ya era la correcta desde `9e0b8ac`, lo que
cambia es de que depende. Eso es exactamente la forma de cambio que un winrate no
puede resolver (el suelo de ruido de este banco ronda el medio punto). Lo que
arbitra es cuantas veces aparece el tablero y por cuanto se estaba decidiendo,
que es lo que esto cuenta.

QUE CUENTA, por promocion forzada (`_forced_ko_promote`):

    asked       promociones con el puesto activo vacio.
    our_mp      ...de esas, las que son NUESTRO match point
                (`_promo_ko_wins_the_game`).
    named       ...de esas, las que ademas nombran un finalizador
                (`_promote_setup_ko_attacker`): el tablero entero de la regla.
    knocks      ...de esas, las que YA tienen un cuerpo que noquea hoy. Ahi la
                frase no habla: +PROMO_KO_BONUS es duenio de la decision.
    flips       ...de las que quedan, en cuantas la bandera CAMBIA el argmax
                (se puntua cada menu con la bandera puesta y quitada).
    margin      la distancia entre el finalizador y el mejor rival SIN la
                bandera: es el numero que dice si la eleccion dependia de
                adornos. `<=450` es la banda del desempate generico de
                supervivientes, o sea "se decidio por nada".

Uso:
    python utils/census_the_seat_that_closes_the_game.py --games 200
    python utils/census_the_seat_that_closes_the_game.py --records records
    python utils/census_the_seat_that_closes_the_game.py --games 200 \
        --opponent deck/real_opponents/alakazam_1.csv
"""

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "utils")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m  # noqa: E402

# La lista contra la que el tablero aparece mas: la promocion forzada a un premio
# necesita partidas que lleguen al final, y esta es la que las alarga.
DEFAULT_OPPONENT = "deck/real_opponents/alakazam_1.csv"


class _Tally:
    """El espia que cuelga de `score_option`.

    Es la unica funcion por la que pasa CADA opcion de un menu de promocion con
    el contexto ya construido, asi que leer las banderas desde ahi no necesita
    ningun hook dentro de `agent()` y no puede discrepar de lo que el scorer vio.
    """

    def __init__(self):
        self.asked = 0
        self.our_mp = 0
        self.named = 0
        self.knocks = 0
        self.flips = 0
        self.margins = []
        self._seen = set()
        self._cur = None

    def start_menu(self, ctx):
        key = id(ctx)
        if key in self._seen:
            return False
        self._seen.add(key)
        self.asked += 1
        if not getattr(ctx, "_promo_ko_wins_the_game", False):
            return False
        self.our_mp += 1
        # El orden importa: un cuerpo que YA noquea hoy cierra el guard exterior
        # de `_promote_setup_ko_attacker` (pide `_best_promote_key[0] == 0`), asi
        # que se cuenta ANTES que `named` o el finalizador parece no existir en
        # tableros donde lo que pasa es que ya habia algo mejor.
        key_best = getattr(ctx, "_best_promote_key", None)
        if key_best is not None and key_best[0]:
            self.knocks += 1
            return False
        if getattr(ctx, "_promote_setup_ko_attacker", None) is None:
            return False
        self.named += 1
        return True


def _score_both(tally, original, ctx, option, card_of):
    """Puntua la opcion con la bandera puesta y quitada."""
    import ptcg.turn.options.card as cardmod
    prev = cardmod.THE_SEAT_THAT_CLOSES_THE_GAME_IS_A_GUARANTEE
    try:
        cardmod.THE_SEAT_THAT_CLOSES_THE_GAME_IS_A_GUARANTEE = False
        off = original(ctx, option, 0)
        cardmod.THE_SEAT_THAT_CLOSES_THE_GAME_IS_A_GUARANTEE = True
        on = original(ctx, option, 0)
    finally:
        cardmod.THE_SEAT_THAT_CLOSES_THE_GAME_IS_A_GUARANTEE = prev
    return off, on


def install(tally):
    """Envuelve `score_option` y devuelve la funcion original."""
    original = m.score_option
    pending = {}

    def spy(ctx, option, score):
        if getattr(ctx, "_forced_ko_promote", False):
            key = id(ctx)
            if key not in pending:
                pending[key] = tally.start_menu(ctx)
            if pending[key]:
                off, on = _score_both(tally, original, ctx, option, None)
                bucket = tally.__dict__.setdefault("_rows", {})
                bucket.setdefault(key, []).append(
                    (option, off, on,
                     getattr(ctx, "_promote_setup_ko_attacker", None)))
        return original(ctx, option, score)

    m.score_option = spy
    return original


def close(tally):
    """Cierra los menus abiertos y cuenta flips y margenes."""
    for key, rows in tally.__dict__.get("_rows", {}).items():
        if not rows:
            continue
        best_off = max(rows, key=lambda r: r[1])
        best_on = max(rows, key=lambda r: r[2])
        if best_off[0] is not best_on[0]:
            tally.flips += 1
        # El margen es la distancia SIN la bandera entre el finalizador y el
        # mejor de sus rivales: si es pequenio, la partida se estaba jugando a
        # un desempate.
        fin = [r for r in rows if r[3] is not None
               and getattr(r[0], "index", None) == getattr(best_on[0], "index", None)]
        others = [r[1] for r in rows if r is not (fin[0] if fin else None)]
        if fin and others:
            tally.margins.append(fin[0][1] - max(others))


def census_records(record_dir, tally):
    original = install(tally)
    try:
        for record in sorted(Path(record_dir).glob("registro_*.json")):
            log = json.loads(record.read_text(encoding="utf-8"))
            m._init_cards_tracking()
            for step in log.get("steps", []):
                for entry in step:
                    obs = entry.get("observation") or {}
                    if not obs.get("select"):
                        continue
                    try:
                        m.agent(obs)
                    except Exception:
                        continue
    finally:
        m.score_option = original
    close(tally)


def census_selfplay(games, opponent, tally):
    import selfplay as sp
    deck_op = sp.read_deck(opponent) if opponent else None
    original = install(tally)
    try:
        for _ in range(games):
            try:
                sp.play_game(m, m, deck1=deck_op)
            except Exception:
                continue
    finally:
        m.score_option = original
    close(tally)


def report(tally):
    print(f"  asked   {tally.asked:5d}  promociones forzadas")
    print(f"  our_mp  {tally.our_mp:5d}  ...nuestro match point")
    print(f"  knocks  {tally.knocks:5d}  ...ya habia quien noquea hoy (la frase calla)")
    print(f"  named   {tally.named:5d}  ...de las que quedan, con finalizador nombrado")
    live = tally.named
    print(f"  LIVE    {live:5d}  tableros donde la frase decide")
    print(f"  flips   {tally.flips:5d}  ...y cambia el asiento elegido")
    if tally.margins:
        tight = sum(1 for x in tally.margins if 0 < x <= 450)
        print(f"  margen  min {min(tally.margins)}  max {max(tally.margins)}  "
              f"<=450 en {tight} de {len(tally.margins)}")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--records", default=None)
    ap.add_argument("--games", type=int, default=0)
    ap.add_argument("--opponent", default=DEFAULT_OPPONENT)
    args = ap.parse_args(argv)

    tally = _Tally()
    if args.records:
        census_records(args.records, tally)
        print(f"CENSO sobre {args.records}")
    else:
        games = args.games or 100
        census_selfplay(games, args.opponent, tally)
        print(f"CENSO sobre {games} partidas de self-play vs {args.opponent}")
    report(tally)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
