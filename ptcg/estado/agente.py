"""`EstadoAgente`: el estado mutable que persiste ENTRE turnos.

Ola 3 del refactor (docs/main-refactor-arquitectura.md). Hasta aqui todo eran
traslados verbatim; esto es lo primero que REESCRIBE codigo, porque cada
`ko_last_turn` pasa a ser `ESTADO.ko_last_turn`.

POR QUE UN OBJETO Y NO NOMBRES SUELTOS
  `from ptcg.estado.agente import ko_last_turn` COPIA el valor en el momento del
  import: cuando main.py lo reasigna, el modulo que lo importo asi sigue viendo
  el valor viejo. No lanza excepcion, no rompe ningun test que fije el global por
  su cuenta -- simplemente el agente decide mal en partida. Con un objeto no hay
  nada que copiar: `ESTADO` nunca se reasigna, solo sus campos, y todos los
  modulos miran el mismo. Lo vigila utils/lint_arquitectura.py (R1).

  Ya ha pasado dos veces con nombres que NO eran estado y aun asi se comportaron
  como tal: `card_table` (Ola 2) y `_score_xerosic_play` (Ola 4). Ambos casos son
  la misma trampa vista desde otro angulo.

EL RESET ES UNO SOLO
  Antes habia dos copias a mano del reinicio -- el fixture `reset_main_state` de
  tests/test_main.py y `golden_corpus.reset_agente` --, que hay que acordarse de
  actualizar cada vez que nace un global. Ahora `reset()` es la unica fuente.
"""

from ptcg.cartas.costes import ATTACK_ENERGY_REQ_BASE
from ptcg.motor.plan import AttackPlan

# Valor centinela de `_log_turno_en_curso`: aun no se sabe de que turno son los
# logs que estamos leyendo.
_TURNO_LOG_DESCONOCIDO = -1


class EstadoAgente:
    """Estado del agente que sobrevive entre llamadas a `agent()`.

    Los campos se documentan donde se usan; aqui solo viven sus valores
    iniciales, que son los que tenia main.py a nivel de modulo.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Deja el estado como al arrancar una partida nueva."""
        # --- Ultra Ball: intenciones que cruzan de un turno al siguiente ------
        self._ub_meowth_pending = False
        # Hermano del anterior para la cadena UB -> Fezandipiti ex -> Flip the Script
        # (user, registro_006 paso 90, episodio 88710543 vs Mega Lucario): si la Ultra
        # Ball ELIGIO buscar Fezandipiti ex (objetivo `fez_tras_ko`, 1050: solo se elige
        # con la habilidad VIVA), hay que COMPLETAR la jugada y bajarlo. Se paga con dos
        # cartas del descarte, asi que dejarlo muerto en la mano -- o peor, barajarlo de
        # vuelta al mazo con el propio Unfair Stamp del turno -- tira la Ultra Ball
        # entera y con ella el robo de 3 de Flip the Script, que es UNA VEZ POR TURNO y
        # solo vive el turno posterior al KO. Se resetea por turno.
        self._ub_fez_pending = False
        # Motor UB->Meowth->Lillie's sobre el tier de energia (user, registro_008
        # paso 58 vs Archaludon ex): se arma cuando `_ub_engine_refresh_pivot` puntua
        # la Ultra Ball a 31450; el FETCH de esa UB (decision posterior, cuando las
        # energias ya se descartaron y las condiciones del pivote no se pueden
        # recomputar) lo consume para elegir Meowth ex. Se resetea por turno.
        self._ub_engine_pivot_turn = False

        # --- Poke Pad / Last-Ditch: compromisos del turno --------------------
        self._poke_pad_target_id = 0
        # EL SUPPORTER QUE TRAJO EL LAST-DITCH SE JUEGA (user, registro_002 paso 22 vs
        # Alakazam, GANADA con error). Bajar un Meowth ex de la mano cuesta un cuerpo de
        # 2 premios en la banca y su UNICO pago es el Supporter que trae Last-Ditch
        # Catch: si ese Supporter se queda muerto en la mano, la jugada entera fue un
        # regalo. Aqui se anota QUE Supporter trajo el fetch de un Meowth ex bajado ESTE
        # turno; mientras el hueco de Supporter siga libre, ese id se queda con el turno
        # (los demas Supporters de la mano ceden). Se resetea por turno.
        #
        # Es la OTRA MITAD de `_meowth_fetch_pierde_el_turno`: aquel predice, ANTES de
        # bajar el Meowth, que el fetch va a ganar el hueco; este COBRA la prediccion
        # despues. Solo se arma con el cuerpo PAGADO (`appearThisTurn`): el Last-Ditch
        # de un Meowth de turnos anteriores es gratis y puede guardar el Supporter para
        # el turno siguiente sin haber regalado nada (mismo criterio que `_meowth_skip_fetch`).
        self._ld_supp_comprometido = 0

        # --- caches por turno ------------------------------------------------
        # Serial del Pokemon ACTIVO cuya HABILIDAD ofrecio el ultimo MENU PRINCIPAL del
        # turno (None si ninguna). Ver el bloque que lo actualiza dentro de agent().
        self._td_ability_serial = None
        self._dodge_immune_serial = None
        self._dodge_immune_turn = -1

        # --- el plan de ataque y el turno en curso ---------------------------
        self.plan = AttackPlan()
        self.pre_turn = 0
        self.we_go_first = False

        # --- lectura de NUESTRO tablero (se recalcula cada turno) ------------
        self.meganium_in_play = False
        self.forest_in_play = False
        self._field_at_turn_start = {}
        # Plantas adjuntadas a NUESTROS Pokemon en el turno en curso (se acumula desde
        # los logs ATTACH en cada llamada a agent() y se reinicia al cambiar de turno).
        # Sirve para saber cuantas HABILIDADES de carga (Teal Dance / Ripening Charge)
        # quedan vivas cuando el adjunte MANUAL ya se gasto.
        self._grass_attaches_this_turn = 0

        # --- KOs y ventana de premios ----------------------------------------
        self.ko_last_turn = False
        self._ko_detected_this_turn = False
        self._prev_op_prize = 6
        # Turno en curso segun los logs: indice del jugador, None = ENTRE TURNOS,
        # -1 = aun no hemos visto ningun TURN_START/TURN_END.
        self._log_turno_en_curso = _TURNO_LOG_DESCONOCIDO
        # `state.turn` en que vimos el ultimo KO PROPIO dentro del turno del rival
        # (habilita Flip the Script / Unfair Stamp) y fuera de el (no los habilita).
        self._ko_propio_en_turno_rival = -99
        self._ko_propio_fuera_del_turno_rival = -99

        # --- matchup rival detectado ------------------------------------------
        self.op_is_crustle_deck = False
        self.op_is_cornerstone_deck = False
        self.op_has_mega_kangaskhan = False
        # Flags por turno (P0.2): denegacion de premios activa en el campo RIVAL.
        # Se refrescan al inicio de agent() junto a meganium_in_play.
        self._op_prize_denial_pecharunt = False   # Pecharunt ex (141) en el campo rival
        self._op_prize_denial_gengar = False      # Mega Gengar ex (772) en el campo rival
        self._festival_grounds_in_play = False  # Festival Grounds (1245) en mesa, de quien sea

        # --- coste de ataque EFECTIVO de este turno ---------------------------
        # Copia de la tabla base sobre la que `_aplicar_impuesto_tera` aplica el
        # +1 de Nighttime Mine a nuestros Tera. Se recalcula SIEMPRE desde la
        # base, para que el impuesto no se acumule entre turnos ni entre partidas.
        self.ATTACK_ENERGY_REQ = dict(ATTACK_ENERGY_REQ_BASE)

        # --- creencia sobre el mazo -------------------------------------------
        # `CARTAS_ACTIVAS_EN_MAZO[card_id][ZONA]` = cuantas copias hay en cada
        # zona. Lo llena `_init_cartas_tracking()` desde deck.csv y lo van
        # moviendo `_move_card_state` y `_update_cartas_tracking`.
        self.CARTAS_ACTIVAS_EN_MAZO = {}
        self._cartas_first_scan_done = False
        self._cartas_prizes_identified = False
        self._cartas_last_turn = -1

        # --- dano rival proyectado -------------------------------------------
        # Dano proyectado del snipe rival a UN Pokemon de nuestra banca (se recalcula
        # cada llamada a agent() a partir de OP_BENCH_SNIPE_DAMAGE y del campo rival).
        self._op_bench_snipe_dmg = 0
        # Goteo RECURRENTE que encaja cada uno de NUESTROS cuerpos con habilidad entre
        # dos turnos nuestros: FREEZING_SHROUD_COUNTER x Froslass en juego x los DOS
        # chequeos de la ronda. 0 sin Froslass. (Ver "LA VENTANA DE REGALO".)
        self._op_chip_per_round = 0
        # Dano DIRIGIBLE por Adrena-Brain a cualquiera de nuestros Pokemon este turno.
        self._op_movable_dmg = 0
        # Tablero RIVAL por turno: datos que necesitan las proyecciones de dano y que NO
        # viajan en la firma de `_op_active_attack_damage_to`. Se refrescan al inicio de
        # agent(), en el mismo bloque que los flags de denegacion de premios.
        self._op_bench_count = 0              # escala Do the Wave (20 x banca rival)


# Instancia unica. NUNCA se reasigna: los modulos guardan una referencia a este
# objeto, asi que reasignarlo aqui los dejaria mirando al viejo.
ESTADO = EstadoAgente()


__all__ = [
    'EstadoAgente',
    'ESTADO',
]
