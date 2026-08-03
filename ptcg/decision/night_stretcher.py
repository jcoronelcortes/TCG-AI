"""Night Stretcher: recuperar del descarte.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from dataclasses import dataclass
from ptcg.calculo.tablero import _evolvable_counts
from ptcg.cartas.ids import Applin, Basic_Grass_Energy, Bayleef, Chikorita, Dipplin, Fezandipiti_ex, Hydrapple_ex, Meganium, Meowth_ex, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex


class _CtxNSPlay:
    """Wrapper del DecisionContext para los escenarios de Night Stretcher:
    anade el inventario del descarte (basics/evos/energia) y la foto
    evolvable; el resto de campos delega en el ctx via __getattr__."""

    _BASICOS = (Chikorita, Applin, Teal_Mask_Ogerpon_ex, Tapu_Bulu,
                Meowth_ex, Fezandipiti_ex, Pinsir)
    _EVOS = (Bayleef, Meganium, Dipplin, Hydrapple_ex)

    def __init__(self, ctx):
        self.c = ctx
        basics, evos, energia = set(), set(), 0
        for carta in ctx.my_state.discard:
            if carta.id == Basic_Grass_Energy:
                energia += 1
            elif carta.id in self._BASICOS:
                basics.add(carta.id)
            elif carta.id in self._EVOS:
                evos.add(carta.id)
        self.basics, self.evos, self.energia = basics, evos, energia
        self.evolvable = _evolvable_counts(ctx.field_counts,
                                           ctx.field_at_turn_start,
                                           ctx.forest_in_play)

    def __getattr__(self, nombre):
        return getattr(self.c, nombre)


def _ns_energia_util_sin_planta(w):
    return (w.energia >= 1
            and w.hand_counts.get(Basic_Grass_Energy, 0) == 0)


def _ns_hay_ogerpon_teal(w):
    for bp in w.my_state.bench:
        if (bp is not None and bp.id == Teal_Mask_Ogerpon_ex
                and len(bp.energies) < 3):
            return True
    if w.my_state.active:
        act = w.my_state.active[0]
        if (act is not None and act.id == Teal_Mask_Ogerpon_ex
                and len(act.energies) < 3):
            return True
    return False


def _ns_crustle_basicos_permitidos(w):
    if w.op_is_cornerstone_deck and not w.op_is_crustle_deck:
        return (Tapu_Bulu, Pinsir)
    return (Tapu_Bulu, Pinsir, Applin, Chikorita)


def _ns_crustle_evos_permitidas(w):
    if w.op_is_cornerstone_deck and not w.op_is_crustle_deck:
        return ()
    return (Dipplin, Bayleef, Meganium)


@dataclass
class _CtxNS:
    hand: dict
    campo: dict
    evolvable_ns: dict
    bench_count: int
    total_grass: int
    has_hydrapple: bool
    active_needs_energy: bool
    op_ex_immune_active: bool
    op_ex_immune_bench: bool
    op_is_lucario: bool
    watchtower: bool
    best_supp_hand_val: int
    best_supp_mazo_val: int
    turno: int
    energy_attached: bool
    supporter_played: bool
    act_hyd_ripen: bool          # Hydrapple ex activo cargable con Ripening
    act_og_can_teal_attack: bool  # Ogerpon activo que Teal Dance habilita
    ns_bench_charge: bool        # vs Crustle: energia para atacante de banca
    ns_evo_saves_doomed: bool    # Hydrapple ex salva a un Dipplin condenado
    grass_enables_syrup_ko: bool  # la Planta vuelve LETAL al Syrup Storm
    # --- Turno muerto: el motor de ROBO manda (registro_008 paso 67) --------
    turno_muerto: bool = False   # nadie ataca hoy ni con una energia mas
    mano_agotada: bool = False   # <=2 cartas en mano tras pagar la busqueda
    ld_free: bool = True         # _meowth_ld_free (Last-Ditch sin gastar)
    ko_reciente: bool = False    # ko_last_turn (habilita Flip the Script)
    # vs Dragapult con >2 Pokemon en juego, Tapu Bulu no se podra BAJAR (ver
    # `_dragapult_no_tapu`): tampoco se busca -- traerlo a la mano solo la
    # llena de una carta muerta.
    dragapult_no_tapu: bool = False


def _v_ns_grass_sin_planta(c):
    v = 600
    if not c.energy_attached:
        v = 700
    if (c.campo.get(Teal_Mask_Ogerpon_ex, 0) >= 1
            and c.hand.get(Basic_Grass_Energy, 0) == 0):
        v = 750
    return v


def _ns_motor_meowth_vivo(c):
    """El Meowth ex recuperado se BAJA este turno y su Last-Ditch Catch trae un
    Supporter del mazo mejor que cualquier cosa que quede en la mano."""
    return (not c.watchtower and c.ld_free
            and c.campo.get(Meowth_ex, 0) < 2
            and c.bench_count < 5
            and not c.supporter_played
            and c.best_supp_hand_val < 500
            and c.best_supp_mazo_val >= 400)


def _ns_motor_fez_vivo(c):
    """El Fezandipiti ex recuperado se BAJA este turno y Flip the Script roba 3
    (exige KO propio en el turno anterior)."""
    return (not c.watchtower and c.ko_reciente
            and c.campo.get(Fezandipiti_ex, 0) == 0
            and c.bench_count < 5)

__all__ = [
    '_CtxNSPlay',
    '_ns_energia_util_sin_planta',
    '_ns_hay_ogerpon_teal',
    '_ns_crustle_basicos_permitidos',
    '_ns_crustle_evos_permitidas',
    '_CtxNS',
    '_v_ns_grass_sin_planta',
    '_ns_motor_meowth_vivo',
    '_ns_motor_fez_vivo',
]
