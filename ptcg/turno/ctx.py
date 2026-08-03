"""`TurnoCtx`: el pizarron que cruza las fases de `agent()`.

Ola 5 del refactor. `agent()` era una funcion de 15.471 lineas cuyas fases se
comunicaban por variables locales; partirla exige darles un sitio explicito.

No son 1.756 campos, que es lo que `agent()` llega a asignar: en cada corte solo
sobreviven las que se leen despues. En el corte del `finalize` -- justo tras el
bucle de puntuacion -- son 40. Elegir POR DONDE cortar segun ese numero
(y no por el orden del archivo) es lo que hace la ola abordable.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class TurnoCtx:
    """Lo que la cola de `agent()` necesita del resto del turno."""

    _ability_order_veto: Any = None
    _active_attack_wins_now: Any = None
    _attach_cede_a_teal_dance: Any = None
    _b: Any = None
    _dragapult_no_tapu: Any = None
    _item_lock_incoming: Any = None
    _ld_card: Any = None
    _ld_opt: Any = None
    _lucario_sac_pivot: Any = None
    _meowth_fetch_id: Any = None
    _meowth_fetch_pierde_el_turno: Any = None
    _meowth_fetch_redundante: Any = None
    _meowth_ld_free: Any = None
    _ready_attacker_count: Any = None
    _suicide_swap_win_promote: Any = None
    _tapu_future_charge: Any = None
    _tapu_sac_priority: Any = None
    _win_ko_active_via_promote: Any = None
    bench_count: Any = None
    context: Any = None
    ctx: Any = None
    field_counts: Any = None
    hand_counts: Any = None
    i: Any = None
    meowth_ability_lock: Any = None
    my_index: Any = None
    my_prize: Any = None
    my_state: Any = None
    obs: Any = None
    op_has_ability_immune_active: Any = None
    op_is_alakazam_deck: Any = None
    op_is_comfey_deck: Any = None
    op_is_cubchoo_deck: Any = None
    op_prize: Any = None
    op_state: Any = None
    scores: Any = None
    select: Any = None
    stadium_id: Any = None
    state: Any = None
    total_grass: Any = None


__all__ = ['TurnoCtx']
