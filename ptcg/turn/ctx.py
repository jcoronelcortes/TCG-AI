"""`TurnoCtx`: the scratchpad that crosses the phases of `agent()`.

Wave 5 of the refactor. `agent()` was a 15,471-line function whose phases talked
to each other through local variables; splitting it means giving those variables
an explicit home.

They are not 1,756 fields, which is how many `agent()` ends up assigning: at
each cut point only the ones read afterwards survive. At the `finalize` cut --
right after the scoring loop -- there are 40. Choosing WHERE to cut by that
number (and not by the order of the file) is what makes the wave tractable.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class TurnoCtx:
    """What the tail of `agent()` needs from the rest of the turn."""

    _order_veto: Any = None
    _active_attack_wins_now: Any = None
    _attach_yields_to_teal_dance: Any = None
    _b: Any = None
    _dragapult_no_tapu: Any = None
    _ft_hold_lone_meowth: Any = None
    _item_lock_incoming: Any = None
    _ld_card: Any = None
    _ld_opt: Any = None
    _lucario_sac_pivot: Any = None
    _meowth_fetch_id: Any = None
    _meowth_fetch_loses_the_turn: Any = None
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
