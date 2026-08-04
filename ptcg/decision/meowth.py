"""Meowth ex: Last-Ditch Catch y la prediccion de valor.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.motor.reglas import _ReglaFija
from ptcg.cartas.ids import Boss_Orders, Lillie_Determination, Xerosic_Machinations
from ptcg.estado.agente import ESTADO
from ptcg.cartas.ids import Boss_Orders, Dawn, Lillie_Determination
from ptcg.cartas.ids import Basic_Grass_Energy, Boss_Orders, Dawn, Lanas_Aid, Lillie_Determination, Xerosic_Machinations


_MEOWTH_FETCH_SUPPS = (Boss_Orders, Dawn, Lillie_Determination,
                       Lanas_Aid, Xerosic_Machinations)


class _CtxMeowthFetch:
    """Ctx del fetch de Last-Ditch: carta candidata + flags del turno."""

    def __init__(self, card_id, sv, hand_counts, supp_values, hand_size,
                 strong_attacker, op_hand_count, active_cant_attack,
                 win_via_boss, gust2_via_boss, deny_evo_via_boss,
                 devel_lillie, alakazam, first_turn=False,
                 lillie_alcanzable=False):
        self.card_id = card_id
        # Nuestro PRIMER turno: la linea anti-donk baja Meowth ex aunque el
        # Supporter ya este en mano, y su fetch conserva la excepcion.
        self.first_turn = first_turn
        # ¿Hay una Lillie's Determination REALMENTE alcanzable por este fetch?
        # (ofrecida entre las opciones del prompt, o viva en el mazo cuando se
        # PREDICE el fetch antes de bajar el Meowth). Sin ella, la regla de
        # primer turno no puede degradar al resto de candidatos.
        self.lillie_alcanzable = lillie_alcanzable
        self.alakazam = alakazam
        self.sv = sv
        self.hand = hand_counts
        self.supp_values = supp_values
        self.hand_size = hand_size
        self.strong_attacker = strong_attacker
        self.op_hand_count = op_hand_count
        self.active_cant_attack = active_cant_attack
        self.win_via_boss = win_via_boss
        self.gust2_via_boss = gust2_via_boss
        self.deny_evo_via_boss = deny_evo_via_boss
        self.devel_lillie = devel_lillie
        self.no_energy_in_hand = (hand_counts.get(Basic_Grass_Energy, 0) == 0)


def _v_meowth_fetch_valor(c):
    score = c.sv
    if c.card_id == Boss_Orders and ESTADO.op_is_crustle_deck:
        score += 100
    # Dawn (busca Basico+Fase1+Fase2 para armar la linea evolutiva) SOLO
    # conviene buscarlo con Meowth ex si tenemos Forest of Vitality (1261) EN
    # JUEGO, que deja evolucionar el mismo turno (rush). SIN Forest en juego
    # no podemos acelerar la evolucion: refrescar la mano con Lillie's
    # Determination da mas opciones de juego/ataque inmediatas. Por eso
    # bajamos el Dawn por debajo del valor de Lillie's para que Meowth ex
    # busque Lillie's, no Dawn. CON Forest en juego Dawn conserva su valor
    # (consistente con el desempate Dawn/Lillie's de ~L6137). (user,
    # registro_004 paso 53 vs Marnie's Grimmsnarl ex, PERDIDA.)
    if (c.card_id == Dawn and not ESTADO.forest_in_play
            and c.supp_values.get(Lillie_Determination, 0) > 0):
        score = min(score,
                    c.supp_values.get(Lillie_Determination, 0) - 50)
    return score


_REGLAS_MEOWTH_FETCH = [
    # PRIMER TURNO = SOLO LILLIE'S (user, log 88461779 paso 16 vs Alakazam,
    # PERDIDA). En NUESTRO primer turno el unico motivo por el que se baja un
    # Meowth ex es traer Lillie's Determination: el turno 1 no ataca, no
    # evoluciona y (yendo primeros) ni siquiera ofrece jugar Supporters, asi
    # que lo unico que decide la partida es cuanta MANO tendremos el turno 2.
    # Cualquier otro Supporter que traiga el Last-Ditch se queda muerto en la
    # mano -- y si el turno 2 jugamos la propia Lillie's, ademas se BARAJA.
    # En aquella partida el fetch trajo un Xerosic's Machinations (rama
    # `xerosic_alakazam`: mano rival >= 6 + atacante fuerte) teniendo cuatro
    # Lillie's en el mazo: se gasto la Ultra Ball, el Meowth ex (cuerpo de 2
    # premios en banca) y el turno entero para NO desarrollar nada.
    # Va PRIMERO en la cadena: ninguna rama de matchup (Xerosic, Boss's,
    # Dawn...) puede secuestrar el fetch del primer turno. Deck-agnostico: si
    # el mazo no tiene Lillie's alcanzable (`lillie_alcanzable`), la regla no
    # degrada a nadie y decide la escalera normal.
    _ReglaFija("primer_turno_solo_lillie",
               lambda c: (c.first_turn
                          and c.card_id == Lillie_Determination),
               lambda c: 1400),
    _ReglaFija("primer_turno_resto_cede_a_lillie",
               lambda c: c.first_turn and c.lillie_alcanzable,
               lambda c: min(c.sv, 40)),
    # COPIA REDUNDANTE (user, registro_010 paso 118 vs Alakazam, GANADA con
    # error): solo se juega UN Supporter por turno, asi que traer una 2a copia
    # de uno que YA esta en la mano no aporta absolutamente nada -- se gasto el
    # Meowth ex (un cuerpo de 2 premios en banca) para duplicar una carta. En
    # aquel turno el fetch trajo un segundo Xerosic's Machinations teniendo uno
    # en mano, en vez del Boss's Orders que era justo lo que el motor que bajo
    # el Meowth queria. Va PRIMERO en la cadena: ninguna otra rama debe poder
    # rescatar un duplicado. 40 (no veto) porque el prompt exige elegir una
    # carta: si TODOS los candidatos fueran duplicados hay que quedarse con
    # alguno. Deck-agnostico.
    _ReglaFija("copia_ya_en_mano",
               lambda c: (c.hand.get(c.card_id, 0) >= 1
                          and not c.first_turn),
               lambda c: 40),
    # Remate ganador / 2 premios via Boss's Orders del MAZO.
    _ReglaFija("boss_ganador",
               lambda c: ((c.win_via_boss or c.gust2_via_boss)
                          and c.card_id == Boss_Orders),
               lambda c: 1300),
    # Gusteo de VALOR (deny-evo) via motor Meowth (plan motor Meowth, mejora
    # A): el Boss's del MAZO corta la pre-evo ENERGIZADA del atacante ex
    # rival. 1280: bajo el remate ganador (1300), sobre Lillie's de
    # refresco/desarrollo (1200-1250) -- con la amenaza en banca, cortar la
    # linea prima sobre refrescar (user, registro_006 paso 82 vs Garchomp).
    _ReglaFija("boss_deny_evo",
               lambda c: (c.deny_evo_via_boss
                          and c.card_id == Boss_Orders),
               lambda c: 1280),
    _ReglaFija("lillie_desarrollo",
               lambda c: (c.devel_lillie
                          and c.card_id == Lillie_Determination),
               lambda c: 1250),
    # Xerosic vs Alakazam (user): con la mano rival gorda (Powerful Hand =
    # 20 x carta), Meowth ex busca Xerosic para capar el dano. Refinado
    # (user, registro_004 paso 53 vs Alakazam, PERDIDA): si YA tenemos un
    # atacante fuerte en juego (Hydrapple/Ogerpon), Xerosic manda AUNQUE
    # nuestra mano quede vacia tras bajar el Meowth (la mano rival de 13
    # cartas = Powerful Hand 260 que noquea todo lo nuestro; capar eso vale
    # mas que refrescar con Lillie's cuando el ataque ya esta resuelto) ->
    # 1260, sobre el Lillie's de desarrollo (1250) y el refresco por mano
    # corta (1200), bajo el Boss's ganador (1300). Sin atacante fuerte se
    # mantiene la regla previa (solo con mano >= 3, a 1200).
    _ReglaFija("xerosic_alakazam",
               lambda c: (c.card_id == Xerosic_Machinations
                          and c.alakazam
                          and c.op_hand_count >= 6
                          and (c.hand_size >= 3 or c.strong_attacker)),
               lambda c: 1260 if c.strong_attacker else 1200),
    # Xerosic GENERICO en el fetch de Last-Ditch (plan motor Meowth, mejora
    # B): contra CUALQUIER mazo con mano rival >= 7, quitarle 4+ cartas es
    # valor real (el scorer generico de Xerosic ya lo juega a 3380 si esta
    # en mano; antes ni era candidato del fetch fuera de Alakazam). 1100:
    # bajo Lillie's de refresco/desarrollo (1200-1250) y los Boss's
    # (1280/1300) -- solo si no hay mejor opcion. Guards:
    # `strong_attacker` (con el ataque ya resuelto la disrupcion vale; SIN
    # atacante fuerte, cavar con Lillie's -escaleras 1000-1200- va primero)
    # y activo-que-no-ataca (que Xerosic no secuestre el fetch del TURNO
    # MUERTO, cuyo sentido es traer Lana's/Lillie's para salir del atasco).
    _ReglaFija("xerosic_generico",
               lambda c: (c.card_id == Xerosic_Machinations
                          and c.op_hand_count >= 7
                          and c.strong_attacker
                          and not c.active_cant_attack),
               lambda c: 1100),
    _ReglaFija("mano_corta",
               lambda c: c.hand_size <= 2,
               lambda c: (1200 if c.card_id == Lillie_Determination
                          else min(c.sv, 100))),
    _ReglaFija("atasco_sin_energia",
               lambda c: c.active_cant_attack and c.no_energy_in_hand,
               lambda c: (1200 if c.card_id == Lillie_Determination
                          else min(c.sv, 150))),
    _ReglaFija("atasco_sin_lillie_en_mano",
               lambda c: (c.active_cant_attack and
                          c.hand.get(Lillie_Determination, 0) == 0),
               lambda c: (1200 if c.card_id == Lillie_Determination
                          else min(c.sv, 150))),
    _ReglaFija("sin_atacante_mano_media",
               lambda c: not c.strong_attacker and c.hand_size <= 5,
               lambda c: (1000 if c.card_id == Lillie_Determination
                          else min(c.sv, 200))),
    _ReglaFija("sin_atacante",
               lambda c: not c.strong_attacker,
               lambda c: (800 if c.card_id == Lillie_Determination
                          else min(c.sv, 400))),
    _ReglaFija("valor_del_supporter",
               lambda c: True,
               _v_meowth_fetch_valor),
]

__all__ = [
    '_CtxMeowthFetch',
    '_MEOWTH_FETCH_SUPPS',
    '_v_meowth_fetch_valor',
    '_REGLAS_MEOWTH_FETCH',
]
