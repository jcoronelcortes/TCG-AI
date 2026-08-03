"""DecisionContext: la instantanea del turno que reciben los scorers.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from dataclasses import dataclass


# =============================================================================
# DecisionContext + scorers extraidos (refactor Prioridad 1)
# -----------------------------------------------------------------------------
# `agent()` es una unica funcion de ~11.800 lineas cuyo bucle de scoring mezcla
# decenas de reglas en un if/elif gigante. Para reducir ese monolito se estan
# extrayendo las ramas de puntuacion a funciones PURAS `_score_*(ctx)` que leen
# un `DecisionContext` construido una sola vez por decision. Cada extraccion es
# un refactor de comportamiento IDENTICO, verificado por la suite de tests.
#
# Estado del refactor: PoC con la rama de Boss's Orders (`_score_boss_orders_play`).
# Al extraer mas ramas se agregan aqui los campos que necesiten; el objetivo es
# que `agent()` acabe orquestando (construye ctx -> mapea opcion a su scorer ->
# argmax) en vez de contener toda la logica inline.
@dataclass
class DecisionContext:
    """Entradas invariantes de una decision (se construye antes del bucle de
    scoring). Los scorers `_score_*` la tratan como SOLO LECTURA."""
    # Objetos de estado compartidos
    state: object
    my_state: object
    op_state: object
    hand_counts: dict
    field_counts: dict
    supp_values: dict
    cartas_en_mazo: dict
    field_at_turn_start: dict
    # Recuento de tablero / premios
    bench_count: int
    my_hand_len: int
    my_prize: int
    op_prize: int
    op_hand_count: int
    meganium_in_play: bool
    forest_in_play: bool
    itchy_pollen_active: bool
    has_hydrapple: bool
    watchtower_in_play: bool
    meowth_ability_lock: bool   # watchtower O Iron Thorns activo (P1.4)
    neutralization_zone_active: bool
    mega_line_active: bool
    active_needs_energy: bool
    evolve_possible_in_play: bool
    energy_starved_low_draw: bool
    pp_playable_in_hand: bool
    can_attack: bool
    best_supp_in_hand_val: int
    best_supp_in_mazo_val: int
    # Flags de matchup / muros del rival
    op_is_alakazam_deck: bool
    op_is_hop_deck: bool
    op_is_comfey_deck: bool
    op_active_is_dunsparce: bool
    op_has_ability_immune_active: bool
    op_has_ex_immune_active: bool
    op_has_ex_immune_bench: bool
    op_is_control_deck: bool
    op_is_slowking_deck: bool
    op_is_gardevoir_deck: bool
    op_is_zoroark_deck: bool
    op_is_aggro_deck: bool
    op_is_beedrill_deck: bool
    op_is_crustle_deck: bool
    op_is_cornerstone_deck: bool
    op_is_fire_deck: bool
    op_is_mirror: bool
    op_kang_ko_target: bool
    stadium_id: int
    # Flags de turno
    ko_last_turn: bool
    our_first_turn: bool
    active_cant_attack: bool
    bdg_retreat_ko: bool
    supporter_boost: int
    we_go_first: bool
    budew_op_index: int
    budew_on_op_field: bool
    lucario_sac_pivot: bool
    win_via_boss_gust: bool
    gust_2prize_via_boss: bool
    # Flags de Boss's Orders (calculados en evaluate_supporters / mas arriba)
    boss_win_via_bench: bool
    boss_dodge_redirect: bool
    boss_defensive_gust: bool
    boss_deny_alakazam_line: bool
    boss_low_value_gust: bool
    boss_prize_rank: int
    boss_ko_threat_preevo: bool
    has_ready_bench_attacker: bool
    # El ACTIVO propio esta CONDENADO (active_ko_likely): las reglas de
    # Boss's/Lillie's lo consultan para no gastar el Supporter en un gusteo
    # de premios cuando no hay relevo en banca (registro_004 vs Team Rocket).
    active_ko_likely: bool
    # El ACTIVO rival es una pre-evo AMENAZA (THREAT_PREEVO_IDS) que DOMINA a
    # todas sus copias de banca (herramienta de vida como Hero's Cape, o >=
    # energias) y nuestro activo puede atacarlo: NO gastar Boss's en gustear la
    # copia debil (registro_007 paso 80 vs Archaludon: aun sin KO por la Cape).
    # Default False: los tests unitarios construyen el ctx directamente.
    boss_active_threat_dominates: bool = False
    # Remate rival REAL sobre nuestro activo, resuelto via attack_table
    # (`_op_active_attack_damage_to` >= HP del activo). El heuristico
    # `active_ko_likely` se apoya en `_op_best_damage_vs`, que lee el dano de
    # un ID de ataque (int) y SIEMPRE da 0: contra un Mega Lucario ex con 2
    # energias (Mega Brave 270) creia que nuestro Ogerpon ex de 210 PV no
    # corria peligro. Las reglas de "activo condenado sin relevo" de
    # Boss's/Lillie's usan AMBOS flags (registro_004 t4 vs Mega Lucario).
    # Default False: los tests unitarios construyen el ctx directamente.
    active_doomed_real: bool = False
    # UNA Planta sobre el ACTIVO paga su coste de retirada y habilita atacar con
    # un cuerpo de banca (`_grass_unlocks_active_retreat`), por la ruta de las
    # HABILIDADES de carga: NO exigen que el adjunte manual del turno siga libre.
    # Las consume la Night Stretcher para saber que la energia del descarte
    # tiene destino (registro_014 paso 141 vs Alakazam).
    # Default False: los tests unitarios construyen el ctx directamente.
    ability_unlock_retreat_ko: bool = False
    ability_unlock_retreat_attack: bool = False
    # GRAND TREE (id 1249). `grand_tree_ability_pending` = el estadio esta en
    # mesa, ofrece su habilidad en ESTE menu y hay un plan de evolucion
    # ejecutable. Lo consulta la regla de Forest of Vitality para NO reemplazar
    # el estadio antes de haber cobrado la cadena gratis (peticion del user).
    # Default False: los tests unitarios construyen el ctx directamente.
    grand_tree_in_play: bool = False
    grand_tree_ability_pending: bool = False
    # El MURO INMUNE A EX (Crustle / Sylveon) esta de ACTIVO rival y nuestro
    # activo lo NOQUEA este turno (dano via `_our_effective_damage`, con el tope
    # de Sturdy aplicado). Lo consulta la regla
    # `rematar_muro_inmune_antes_de_gustear`: gustear moveria al muro a la banca
    # y desperdiciaria la unica ventana en la que un cuerpo NO-ex propio puede
    # matarlo (registro_006 paso 47).
    # Default False: los tests unitarios construyen el ctx directamente.
    ex_immune_wall_ko_ready: bool = False
    # ¿Queda Last-Ditch Catch este turno? False si algun Meowth ex EN JUEGO
    # aparecio este turno (su habilidad ya se gasto y solo se permite una por
    # turno) -> bajar o CAVAR otro Meowth ex no buscaria Supporter.
    meowth_ld_free: bool = True
    # Festival Grounds en mesa Y con la linea Applin/Dipplin rival a la vista:
    # enciende su Festival Lead (doble ataque tras noquearnos el activo). El
    # estadio es de DOBLE FILO -- nuestro Dipplin tambien lo gana--, por eso el
    # flag llega ya filtrado por la linea rival. Ver `_festival_lead_hostil`.
    # Default False: los tests unitarios construyen el ctx directamente.
    festival_lead_hostil: bool = False
    # MATCH POINT contra el ACTIVO rival: noquearlo GANA la partida (vale al
    # menos los premios que nos faltan) y el rematador esta en la BANCA --
    # retirar -> promover -> atacar, con la retirada pagable. Lo consulta la
    # regla `remate_ganador_al_activo_tras_retirar`: gustear cambiaria el activo
    # rival justo por un cuerpo de MENOS premios y tiraria el turno ganador
    # (registro_010 paso 144). Ver el bloque `_win_ko_active_via_promote`.
    # Default False: los tests unitarios construyen el ctx directamente.
    win_ko_active_via_promote: bool = False
    # PESCA DE REMATE (`_PescaRemate` o None): el turno no tiene ningun ataque
    # posible, pero el ROBO del refresco puede traer la energia que desbloquea
    # uno -- con su probabilidad hipergeometrica ya calculada sobre la creencia
    # de mazo. Lo consultan la regla `pescar_energia_para_remate` de Lillie's y
    # la cesion `cede_a_pesca_de_remate` de Boss's (registro_004 paso 49 vs
    # Marnie). Default None: los tests unitarios construyen el ctx directamente.
    pesca_remate: object = None
    # AMENAZA DE BLOQUEO DE ITEMS: el rival puede dejarnos sin Objetos en
    # NUESTRO proximo turno (Budew en su campo, o mazo Dragapult, que lo lleva).
    # Ver `_bloqueo_de_items_inminente`: con esto encima un Item no es un
    # recurso que se guarda, es un recurso que CADUCA -- lo consulta
    # `_ub_meowth_para_manana`.
    # Default False: los tests unitarios construyen el ctx directamente.
    item_lock_incoming: bool = False

__all__ = [
    'DecisionContext',
]
