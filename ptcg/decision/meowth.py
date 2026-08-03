"""Meowth ex: Last-Ditch Catch y la prediccion de valor.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

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

__all__ = [
    '_CtxMeowthFetch',
    '_MEOWTH_FETCH_SUPPS',
]
