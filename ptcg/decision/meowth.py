"""Meowth ex: Last-Ditch Catch y la prediccion de valor.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

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

__all__ = [
    '_CtxMeowthFetch',
    '_MEOWTH_FETCH_SUPPS',
    '_v_meowth_fetch_valor',
]
