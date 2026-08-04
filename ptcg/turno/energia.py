"""`_energy_score_base`, extraida VERBATIM de `agent()` (Ola 5).

Capturaba 61 variables del turno; ahora llegan en un contexto que se
desempaqueta al entrar, con los MISMOS nombres, de modo que el cuerpo es
exactamente el que estaba en main.py.
"""

from cg.api import Pokemon
from ptcg.calculo.dano import _our_effective_damage
from ptcg.calculo.energia import _can_attack_eff, _grass_attach_unit, _grass_mult, _ogerpon_base_phys_cap, _physical_energy
from ptcg.cartas.ids import Applin, Basic_Grass_Energy, Bayleef, Chikorita, Dipplin, Fezandipiti_ex, Hydrapple_ex, Meganium, Meowth_ex, NON_ATTACKER_ENERGY_WASTE_IDS, OUR_EX_IDS, Pinsir, RETREAT_COST, SCORE_CARGA_ACTIVO_ATAQUE, SCORE_CARGA_ACTIVO_REMATE, SCORE_VETO, Sylveon, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.cartas.tablas import card_table
from ptcg.estado.agente import ESTADO
from ptcg.turno.energia_ctx import CtxEnergyScoreBase  # noqa: F401


def _energy_score_base(tc, pokemon, active):
    # Desempaquetado de las capturas.
    _ability_unlock_retreat_attack = tc._ability_unlock_retreat_attack
    _ability_unlock_retreat_ko = tc._ability_unlock_retreat_ko
    _active_already_kos = tc._active_already_kos
    _active_hydra_capped = tc._active_hydra_capped
    _active_needs_energy = tc._active_needs_energy
    _active_pokemon = tc._active_pokemon
    _attach_enable_retreat_attack = tc._attach_enable_retreat_attack
    _attach_enable_retreat_ko = tc._attach_enable_retreat_ko
    _bench_attacker_needs_energy = tc._bench_attacker_needs_energy
    _bench_attacker_ready = tc._bench_attacker_ready
    _bench_has_chargeable = tc._bench_has_chargeable
    _carga_activo_habilita_ataque = tc._carga_activo_habilita_ataque
    _carga_activo_remata = tc._carga_activo_remata
    _conf_active = tc._conf_active
    _conf_active_can_attack = tc._conf_active_can_attack
    _conf_active_can_retreat = tc._conf_active_can_retreat
    _conf_bench_attacker_body = tc._conf_bench_attacker_body
    _conf_bench_attacker_ready = tc._conf_bench_attacker_ready
    _conf_can_attack_pkmn = tc._conf_can_attack_pkmn
    _conf_is_matchup_attacker = tc._conf_is_matchup_attacker
    _ctm_applin_bench = tc._ctm_applin_bench
    _ctm_charge_active_dipplin = tc._ctm_charge_active_dipplin
    _ctm_chikorita_bench = tc._ctm_chikorita_bench
    _ctm_tapu_high = tc._ctm_tapu_high
    _cubchoo_lock_stuck = tc._cubchoo_lock_stuck
    _ex_stuck_promo_ready = tc._ex_stuck_promo_ready
    _extra_energy_enables_ko = tc._extra_energy_enables_ko
    _feza_lucario_wall = tc._feza_lucario_wall
    _gust_2prize_via_boss = tc._gust_2prize_via_boss
    _hydra_fragile_pivot = tc._hydra_fragile_pivot
    _meganium_alk_1prize_attacker = tc._meganium_alk_1prize_attacker
    _meganium_alk_future_charge = tc._meganium_alk_future_charge
    _ogerpon_lethal_focus_serial = tc._ogerpon_lethal_focus_serial
    _ogerpon_td_manual_lethal = tc._ogerpon_td_manual_lethal
    _ripen_retreat_ko_pivot = tc._ripen_retreat_ko_pivot
    _tapu_future_charge = tc._tapu_future_charge
    _win_via_boss_gust = tc._win_via_boss_gust
    active_ko_likely = tc.active_ko_likely
    bench_count = tc.bench_count
    field_counts = tc.field_counts
    hand_counts = tc.hand_counts
    has_hydrapple = tc.has_hydrapple
    is_confused = tc.is_confused
    my_state = tc.my_state
    neutralization_zone_active = tc.neutralization_zone_active
    op_has_ex_immune_active = tc.op_has_ex_immune_active
    op_has_ex_immune_bench = tc.op_has_ex_immune_bench
    op_has_froslass = tc.op_has_froslass
    op_is_aggro_deck = tc.op_is_aggro_deck
    op_is_alakazam_deck = tc.op_is_alakazam_deck
    op_is_beedrill_deck = tc.op_is_beedrill_deck
    op_is_cubchoo_deck = tc.op_is_cubchoo_deck
    op_is_drednaw_deck = tc.op_is_drednaw_deck
    op_is_fire_deck = tc.op_is_fire_deck
    op_is_hop_deck = tc.op_is_hop_deck
    op_is_lucario_deck = tc.op_is_lucario_deck
    op_is_sylveon_deck = tc.op_is_sylveon_deck
    op_kang_ko_target = tc.op_kang_ko_target
    op_state = tc.op_state
    state = tc.state
    total_grass = tc.total_grass

    energy_count = len(pokemon.energies)

    # ATACAR CON EL ACTIVO ES LO PRIMERO (ver `_carga_activo_remata`): si la
    # energia que aun puede moverse este turno deja al ACTIVO en su coste de
    # ataque y ese ataque NOQUEA, la carga va al ACTIVO y punto. Va la
    # PRIMERA de toda la funcion, por delante del foco de carga de Ogerpon y
    # de los topes de energia por matchup: esos topes existen para no
    # DESPERDICIAR energia (reservarla para retiradas, no sobrecargar un
    # cuerpo que ya llega), y una energia que cobra un premio HOY no se
    # desperdicia. Solo cede ante el remate GANADOR via Boss's (42000).
    # Cubre el adjunte MANUAL (OptionType.ATTACH) y el objetivo de Ripening
    # Charge (SelectContext.ATTACH_FROM), que puntuan ambos por aqui.
    if active and _carga_activo_remata:
        return SCORE_CARGA_ACTIVO_REMATE

    # OBJETIVO de la linea "Planta al ACTIVO -> RETIRAR -> atacar con el de
    # banca" (user, registro_006 paso 101 vs Alakazam, PERDIDA). Las cuatro
    # banderas ya detectan la linea completa y puntuan el ACTO de cargar (el
    # adjunte manual en su rama de OptionType.ATTACH, las habilidades en las
    # suyas), pero el DESTINO de la energia se decide aqui -- y aqui no habia
    # nada: el ACTIVO caia en la banda generica de desarrollo (~8000) y
    # cualquier cuerpo de banca le ganaba. Resultado: Ripening Charge se
    # activaba "por la linea correcta" y la Planta acababa en un Ogerpon de
    # banca, con el rematador real atrapado detras de un Applin que no podia
    # retirarse. Mismas bandas que usan los consumidores: 41000 (letal) y
    # 31250 (chip). Cubre el adjunte MANUAL (OptionType.ATTACH) y el objetivo
    # de las habilidades de carga (SelectContext.ATTACH_FROM).
    if active and (_attach_enable_retreat_ko or _ability_unlock_retreat_ko):
        return 41000
    if active and (_attach_enable_retreat_attack
                   or _ability_unlock_retreat_attack):
        return 31250

    # Foco de carga letal en UN Ogerpon (ver `_ogerpon_lethal_focus_serial`):
    # concentrar el adjunte manual en ESE cuerpo y NO repartir a otro Ogerpon.
    if (_ogerpon_lethal_focus_serial is not None
            and pokemon.id == Teal_Mask_Ogerpon_ex):
        if getattr(pokemon, 'serial', None) == _ogerpon_lethal_focus_serial:
            return 41700
        return SCORE_VETO
    # Desempate por VIDA (user, log 86212499 paso 151, vs Alakazam, GANADA):
    # cuando hay dos o mas Pokemon IGUALES como objetivo de carga de energia
    # (p.ej. dos Hydrapple ex en banca, uno a 70 hp y otro a 330 hp), SIEMPRE
    # cargar al de MAS vida. Antes ambos caian en la misma rama y obtenian el
    # mismo puntaje entero, asi que el empate lo rompia el orden de opcion
    # (indice de banca menor -> el de 70 hp). Se suma una fraccion DIMINUTA de
    # la vida (< 1 punto: hp/100000, maximo 0.0033) que SOLO altera empates
    # exactos y nunca cruza los umbrales enteros de las demas ramas, de modo
    # que a igualdad de puntaje gana el de mas vida. Cubre el adjunte MANUAL
    # (OptionType.ATTACH) y el objetivo de Ripening Charge
    # (SelectContext.ATTACH_FROM), ya que ambos puntuan via energy_score.
    score = 8000 + (getattr(pokemon, 'hp', 0) or 0) / 100000.0

    # Regla (user, log 86028607 paso 21, vs Crustle, GANAMOS): un Chikorita
    # puede tener como MAXIMO 1 energia. NUNCA adjuntar una 2a energia a un
    # Chikorita (su unico ataque usa 1 energia; el excedente se desperdicia
    # y conviene reservar la energia para atacantes reales o retiradas).
    # Aplica al activo y a la banca, y a cualquier via de adjunte (manual o
    # Ripening Charge). len(energies) es EFECTIVA (Wild Growth de Meganium
    # DUPLICA cada Planta), asi que se convierte a cartas FISICAS.
    if pokemon.id == Chikorita and _physical_energy(energy_count) >= 1:
        return SCORE_VETO

    # Regla (user, registro_004 paso 36, episodio 87675043 vs Mega Lucario,
    # PERDIDA): un Applin puede tener como MAXIMO 1 energia FISICA. Su unico
    # ataque cuesta 1 y evoluciona pronto (Do the Wave de Dipplin tambien
    # cuesta 1), asi que la 2a energia se DESPERDICIA: debe ir a un Ogerpon
    # (Teal Dance / adjunte) o a un atacante futuro. Antes la 2a energia solo
    # recibia una penalizacion blanda (-300 -> 7700) que aun le ganaba a Teal
    # Dance (7500) y el agente sobrecargaba al Applin. Excepciones:
    #   (a) evolucion COMPLETA este turno (Dipplin Y Hydrapple ex en mano,
    #       sin Meganium): la energia extra queda en el futuro Hydrapple ex
    #       (2 efectivas = Syrup Storm listo) -> se deja pasar al ranking
    #       normal (rama _applin_full_evolve_now);
    #   (b) Hydrapple ex NUESTRO ya en juego: la energia en el campo si
    #       potencia Syrup Storm (escala con el Grass TOTAL), pero SOLO como
    #       ULTIMO recurso (score minimo 10) cuando no queda ningun otro
    #       Pokemon que cargar (todo lo demas vetado).
    # Aplica al activo y a la banca, y a cualquier via de adjunte (manual o
    # Ripening Charge). len(energies) es EFECTIVA (Wild Growth de Meganium
    # DUPLICA cada Planta), asi que se convierte a cartas FISICAS.
    if pokemon.id == Applin and _physical_energy(energy_count) >= 1:
        _apl_full_evolve_now = (hand_counts.get(Dipplin, 0) >= 1
                                and hand_counts.get(Hydrapple_ex, 0) >= 1
                                and not ESTADO.meganium_in_play)
        if not _apl_full_evolve_now:
            if field_counts.get(Hydrapple_ex, 0) >= 1:
                return 10
            return SCORE_VETO

    # Regla (user, registro_004 paso 43, episodio 88120517 vs Marnie's
    # Grimmsnarl, GANADA con error): un Dipplin puede tener como MAXIMO 1
    # energia FISICA -- Do the Wave cuesta 1 y su dano NO escala con
    # energia, asi que la 2a se desperdicia y le gana el sitio a Teal
    # Dance / a cargar un Ogerpon hacia Myriad. Excepciones (espejo de la
    # regla de Applin):
    #   (a) evolucion a Hydrapple ESTE turno (Hydrapple ex en mano y el
    #       Dipplin NO aparecio/evoluciono este turno): la 2a energia cae
    #       de inmediato en el Hydrapple (2 efectivas = Syrup Storm
    #       listo). Un Dipplin evolucionado ESTE turno no puede volver a
    #       evolucionar, asi que ahi NO hay excepcion (el caso del
    #       registro: 2a energia a un Dipplin recien evolucionado).
    #   (b) Hydrapple ex NUESTRO ya en juego: ultimo recurso (10), la
    #       energia en campo potencia Syrup Storm pero solo si no queda
    #       nada mejor que cargar.
    if pokemon.id == Dipplin and _physical_energy(energy_count) >= 1:
        _dip_evolve_now = (hand_counts.get(Hydrapple_ex, 0) >= 1
                           and not getattr(pokemon, 'appearThisTurn', False))
        if not _dip_evolve_now:
            if field_counts.get(Hydrapple_ex, 0) >= 1:
                return 10
            return SCORE_VETO

    # Regla (user, log 86607718 turno 2, vs Crustle, PERDIMOS): si empezamos
    # el turno con un Chikorita en el ACTIVO y NINGUN Chikorita en la banca,
    # la prioridad vs Crustle es RETIRARLO (para evolucionarlo a Meganium en
    # la banca y subir un cuerpo util; Chikorita activo es un lastre de 1
    # premio que no ataca al muro). Para poder retirar (coste 1) hace falta
    # cargarle 1 Planta, asi que el adjunte de energia va al Chikorita ACTIVO
    # (0 fisicas) POR ENCIMA de cargar atacantes de banca (p.ej. Tapu Bulu),
    # siempre que exista un cuerpo en banca al que promover tras el retiro.
    # Solo la 1a energia: la regla de "Chikorita max 1" de arriba sigue
    # vigente. Va DESPUES del remate ganador (42000) para no bloquear un KO.
    if (ESTADO.op_is_crustle_deck and active and pokemon.id == Chikorita
            and _physical_energy(energy_count) == 0
            and field_counts.get(Chikorita, 0) <= 1
            and bench_count >= 1
            and not state.energyAttached):
        return 41500

    # Regla (user, log 85855786 paso 141, vs Alakazam, GANAMOS): si este
    # turno existe una jugada GANADORA / de 2 premios via Boss's Orders
    # (gustear al banco rival un objetivo que noqueamos para cobrar los
    # premios que faltan) y ese KO letal se apoya en tener la energia en el
    # ACTIVO (que es el atacante), la carga DEBE ir al ACTIVO. Ganar la
    # partida AHORA es la maxima prioridad y prevalece sobre cargar a Tapu
    # Bulu como atacante FUTURO (`_tapu_future_charge`, 40000), que solo
    # sirve el proximo turno y es irrelevante si ya cerramos la partida.
    # EXCEPCION (user, registro_006 p79 y registro_008 p109-113 vs Alakazam):
    # NO forzar la carga al activo cuando la energia EXTRA no aporta a SU
    # ataque y este YA llega a su requisito; asi no se desperdicia en un activo
    # cargado y fluye a un atacante FUTURO de banca (p.ej. un Hydrapple ex de
    # banca a 0 energias, que ademas de desarrollarse suma al dano de Syrup
    # Storm). Cubre:
    #   - Tapu Bulu / Meganium: dano FIJO con tope duro (Wood Hammer coste 4);
    #     la energia extra no aumenta el dano.
    #   - Hydrapple ex: Syrup Storm escala con el Grass del CAMPO (todos
    #     nuestros Pokemon), NO con la energia PROPIA del atacante; ponerla en
    #     un Hydrapple de banca da EXACTAMENTE el mismo dano este turno y ademas
    #     deja listo un 2o atacante.
    # Ogerpon ex (Myriad) NO entra: su dano escala con su PROPIA energia, asi
    # que ahi el 42000 al activo SIGUE (mas energia agranda/habilita el remate).
    if active and (_win_via_boss_gust or _gust_2prize_via_boss):
        _active_extra_charge_wasted = (
            pokemon.id in (Tapu_Bulu, Meganium, Hydrapple_ex)
            and energy_count >= ESTADO.ATTACK_ENERGY_REQ.get(pokemon.id, 99))
        if not _active_extra_charge_wasted:
            return 42000

    # Regla (user, log 86342087 paso 130, vs Mega Lucario, PERDIMOS): si el
    # activo es un Fezandipiti ex DEBIL a Lucha que sera NOQUEADO por Mega
    # Lucario ex el proximo turno (Mega Brave 270 x2 = 540, 2 premios) y en
    # la banca hay un Hydrapple ex sano (muro 330 que SOBREVIVE el golpe
    # rival), la energia de este turno NO debe ir al Feza condenado (que solo
    # atacaria una vez antes de morir regalando 2 premios) sino al Hydrapple:
    # asi lo dejamos listo (>=2 efectivas) para, tras RETIRAR al Feza (coste
    # 1) y promoverlo, atacar con Syrup Storm. Se veta el adjunte al activo
    # y se prioriza cargar el Hydrapple de banca hasta habilitar su ataque.
    # Va DESPUES del remate ganador (42000) para no bloquear un KO letal.
    if _feza_lucario_wall:
        if active:
            return SCORE_VETO
        if (pokemon.id == Hydrapple_ex
                and len(pokemon.energies) * _grass_mult() < 2):
            return 41000

    # Regla (user): un Tapu Bulu en juego puede tener como MAXIMO 4 energias
    # FISICAS si NO hay Meganium en juego, o 2 si SI hay Meganium. Con
    # Meganium (Wild Growth) cada Planta fisica cuenta DOBLE, asi que 2
    # fisicas = 4 efectivas = suficiente para Wood Hammer (coste 4); sin
    # Meganium hacen falta 4 fisicas. No adjuntar mas: el excedente se
    # desperdicia y conviene reservar la energia. len(energies) es EFECTIVA
    # => se convierte a cartas FISICAS con _physical_energy. Aplica al
    # adjunte manual (OptionType.ATTACH) y al objetivo de Ripening Charge
    # (SelectContext.ATTACH_FROM), activo o banca. Va DESPUES del return de
    # la jugada ganadora (42000) para no bloquear un remate letal.
    if pokemon.id == Tapu_Bulu:
        _tapu_max_phys = 2 if ESTADO.meganium_in_play else 4
        if _physical_energy(energy_count) >= _tapu_max_phys:
            return SCORE_VETO

    # Regla (user, vs Crustle, log 86583376 paso 84): un Teal Mask Ogerpon
    # ex no puede tener mas de DOS energias FISICAS cargadas (por adjunte
    # manual o Ripening Charge). Contra el muro Crustle (que inmuniza a
    # nuestros ex) Ogerpon no puede atacar al muro, asi que RESERVAMOS
    # energia y no lo sobrecargamos. En BANCA el tope es DURO (max 2
    # fisicas). UNICA excepcion para una 3a energia: cuando Ogerpon esta en
    # el ACTIVO y esa energia HABILITA el KO del activo rival
    # (_extra_energy_enables_ko) -- el activo rival no siempre es el muro
    # inmune; puede ser un no-ex al que Ogerpon SI daña. Se conserva ademas
    # el bypass op_kang_ko_target (KO de Mega Kangaskhan ex con Hydrapple
    # ex, donde la energia extra en el tablero sube el dano de Syrup Storm).
    # len(energies) es EFECTIVA (Wild Growth de Meganium duplica cada
    # Planta) => se convierte a cartas FISICAS con _physical_energy.
    if (ESTADO.op_is_crustle_deck and pokemon.id == Teal_Mask_Ogerpon_ex
            and not op_kang_ko_target):
        _crus_phys = _physical_energy(energy_count)
        if not active:
            if _crus_phys >= 2:
                return SCORE_VETO
        else:
            if _crus_phys >= 3:
                return SCORE_VETO
            if (_crus_phys >= 2
                    and not _extra_energy_enables_ko(
                        Teal_Mask_Ogerpon_ex, energy_count)):
                return SCORE_VETO

    # Regla (user, vs Alakazam y vs Hop's): topes de energia para Teal Mask
    # Ogerpon ex (adjunte MANUAL o Ripening Charge). Base FISICA con Meganium
    # en juego = 2 (Wild Growth duplica cada Planta, asi que 2 fisicas = 4
    # efectivas = listo para Myriad Leaf Shower coste 3). Sin Meganium: 4 vs
    # Alakazam y 3 vs Hop's (user: "un Ogerpon no puede tener mas de tres
    # energias cargadas si no tenemos Meganium en juego, o dos si esta
    # Meganium"). En BANCA el tope es DURO: no sobrecargamos, reservamos
    # energia. En el ACTIVO se permite UNA energia FISICA extra SOLO si esa
    # energia es la que HABILITA el KO al activo rival
    # (_extra_energy_enables_ko: el dano actual no noquea pero con +1 si).
    # Una linea GANADORA via Boss's ya devolvio 42000 arriba, asi que este
    # tope no bloquea remates letales. len(energies) es EFECTIVA => se
    # convierte a cartas FISICAS con _physical_energy.
    if (op_is_alakazam_deck or op_is_hop_deck) and pokemon.id == Teal_Mask_Ogerpon_ex:
        _alk_base_phys = _ogerpon_base_phys_cap(ESTADO.meganium_in_play, op_is_hop_deck)
        _alk_phys = _physical_energy(energy_count)
        if not active:
            if _alk_phys >= _alk_base_phys:
                return SCORE_VETO
        else:
            if _alk_phys >= _alk_base_phys + 1:
                return SCORE_VETO
            if (_alk_phys >= _alk_base_phys
                    and not _extra_energy_enables_ko(
                        Teal_Mask_Ogerpon_ex, energy_count)):
                return SCORE_VETO

    # Matchup Cubchoo (user): topes de energia FISICA por Pokemon. Cubchoo
    # bloquea nuestro ataque el proximo turno, asi que no sobrecargamos y
    # RESERVAMOS energias en la MANO para pagar retiradas. DECISION DEL
    # USUARIO (jul 2026, tras la autopsia del mazo mixto Cornerstone/
    # Cubchoo): estos topes NO se relajan aunque el matchup sea el mixto.
    # La razon de la reserva es que estos mazos juegan Boss's Orders y
    # otros partidarios que CAMBIAN nuestro activo: sin energia en mano no
    # se paga la retirada del cuerpo equivocado que nos subieron, y no se
    # vuelve al atacante correcto. La energia "muerta en mano" que ve la
    # autopsia (ATTACH vetado) es el precio deliberado de ese seguro. IMPORTANTE: la
    # observacion DUPLICA cada Planta fisica cuando Meganium esta en juego
    # (Wild Growth), asi que len(energies) es EFECTIVA; la convertimos a
    # cartas FISICAS (_cub_phys) para aplicar los topes que el usuario
    # definio en cartas. Aplica al adjunte manual (OptionType.ATTACH) y al
    # objetivo de Ripening Charge (SelectContext.ATTACH_FROM).
    if op_is_cubchoo_deck:
        _cub_phys = _physical_energy(energy_count)
        if pokemon.id == Teal_Mask_Ogerpon_ex and _cub_phys >= (2 if ESTADO.meganium_in_play else 4):
            return SCORE_VETO
        if pokemon.id == Applin and _cub_phys >= 1:
            return SCORE_VETO
        if pokemon.id == Dipplin and _cub_phys >= (1 if ESTADO.meganium_in_play else 2):
            return SCORE_VETO
        if pokemon.id == Hydrapple_ex and _cub_phys >= (2 if ESTADO.meganium_in_play else 3):
            return SCORE_VETO
        # Linea de Meganium (Chikorita/Bayleef/Meganium): tope de 3 energias
        # FISICAS en toda la linea (regla del usuario, cambio 4).
        if pokemon.id in (Chikorita, Bayleef, Meganium) and _cub_phys >= 3:
            return SCORE_VETO

    # Estado de retirada del ACTIVO propio: para promover un Hydrapple ex
    # LETAL de BANCA hay que RETIRAR el activo, lo que exige energia FISICA
    # en el activo >= su coste de retirada. len(energies) es EFECTIVA (Wild
    # Growth de Meganium DUPLICA cada Planta), pero la retirada se paga con
    # cartas FISICAS, asi que fisica = efectiva // 2 cuando Meganium esta en
    # juego. Si el activo AUN NO puede retirarse, la carga debe ir al ACTIVO
    # para empezar a pagar la retirada, no al Hydrapple de banca (que no
    # ataca desde el banco).
    _hls_my_act = (my_state.active[0]
                   if (my_state.active and my_state.active[0] is not None)
                   else None)
    _hls_act_phys = 0
    _hls_act_rc = 1
    if _hls_my_act is not None:
        _hls_act_eff = len(_hls_my_act.energies)
        _hls_act_phys = _physical_energy(_hls_act_eff)
        _hls_act_rc = RETREAT_COST.get(_hls_my_act.id, 1)
    # El atajo "si el activo es un Hydrapple ex, damos la promocion por
    # buena" solo vale cuando ese Hydrapple YA PUEDE ATACAR: ahi la Planta
    # es fungible (Syrup Storm escala con el Grass de TODO el campo, asi que
    # da igual en que cuerpo caiga) y no hace falta retirar a nadie. Con el
    # Hydrapple activo AUN SIN su coste de ataque la promocion exige
    # retirarlo de verdad (coste 3) y el atajo se convertia en una premisa
    # FALSA: user, registro_006 paso 67 (episodio 88433181, GANADA con
    # error) -- Hydrapple activo a 0 energias, imposible de retirar, y la
    # regla mandaba la Planta al Hydrapple de BANCA "para promoverlo",
    # dejando el turno esteril con el activo rival a 10 PV.
    _hls_act_retreatable = (_hls_my_act is None
                            or (_hls_my_act.id == Hydrapple_ex
                                and not _hydra_fragile_pivot
                                and _can_attack_eff(
                                    Hydrapple_ex,
                                    len(_hls_my_act.energies)))
                            or _hls_act_phys >= _hls_act_rc)

    # Regla (user): si cargar a un Hydrapple ex de BANCA lo deja listo
    # (>=2 efectivas) para un Syrup Storm LETAL sobre el activo rival,
    # priorizar esa carga (Ripening Charge o adjunte manual) por encima de
    # cualquier otra, para poder promoverlo (retirando el activo) y rematar.
    # Va DESPUES del tope Cubchoo (que reserva energia) y ANTES de la carga
    # de Tapu Bulu, porque ganar la partida es la maxima prioridad. SOLO si
    # el activo YA puede retirarse este turno (si no, la carga letal debe ir
    # al ACTIVO, ver bloque siguiente): cargar un Hydrapple de banca que no
    # se puede promover no sirve (no ataca desde el banco).
    if (not active and pokemon.id == Hydrapple_ex
            and _hls_act_retreatable
            and op_state.active and op_state.active[0] is not None):
        _hls_eff_after = energy_count * _grass_mult() + _grass_attach_unit()
        if _hls_eff_after >= 2:
            _hls_opa = op_state.active[0]
            _hls_opa_hp = _hls_opa.hp or 0
            # total_grass es EFECTIVO; adjuntar 1 Grass suma _grass_attach_unit().
            _hls_dmg = _our_effective_damage(
                pokemon, _hls_opa,
                30 + 30 * (total_grass + _grass_attach_unit()),
                ESTADO.meganium_in_play, neutralization_zone_active)
            if _hls_dmg > 0 and _hls_opa_hp > 0 and _hls_dmg >= _hls_opa_hp:
                return 41000

    # Regla (user): si el Hydrapple ex LETAL esta en BANCA pero el activo
    # propio AUN NO puede retirarse (energia fisica < coste de retirada), la
    # carga debe ir al ACTIVO para empezar a pagar la retirada y asi habilitar
    # el retiro -> promocion del Hydrapple -> Syrup Storm letal. Solo si la
    # retirada es COMPLETABLE este turno: hacen falta (coste - fisica actual)
    # Plantas y disponemos de al menos esa cantidad en mano y de suficientes
    # adjuntes (1 manual + una Ripening Charge por cada Hydrapple de banca).
    if (active and _hls_my_act is not None
            and not _hls_act_retreatable
            and _hls_my_act.id != Hydrapple_ex
            and op_state.active and op_state.active[0] is not None):
        _hls_bench_hydra = [
            _bp for _bp in (my_state.bench or [])
            if _bp is not None and _bp.id == Hydrapple_ex
            and len(_bp.energies) >= 2]
        _hls_promote_lethal = False
        if _hls_bench_hydra:
            _hls_opa2 = op_state.active[0]
            _hls_opa2_hp = _hls_opa2.hp or 0
            for _bp in _hls_bench_hydra:
                _hls_bdmg = _our_effective_damage(
                    _bp, _hls_opa2, 30 + 30 * total_grass,
                    ESTADO.meganium_in_play, neutralization_zone_active)
                if _hls_bdmg > 0 and _hls_opa2_hp > 0 and _hls_bdmg >= _hls_opa2_hp:
                    _hls_promote_lethal = True
                    break
        if _hls_promote_lethal:
            _hls_need = _hls_act_rc - _hls_act_phys
            _hls_grass_hand = sum(
                1 for _c in (my_state.hand or [])
                if _c.id == Basic_Grass_Energy)
            _hls_max_attach = 1 + len(_hls_bench_hydra)
            if (_hls_need >= 1 and _hls_grass_hand >= _hls_need
                    and _hls_max_attach >= _hls_need):
                return 41000

    # Regla (user, log 86027506 paso 81, vs Abomasnow, GANADA): si el ACTIVO
    # es un Hydrapple ex FRAGIL y en la banca hay un Hydrapple ex sano y letal
    # (`_hydra_fragile_pivot`), la energia de este turno debe ir al ACTIVO
    # fragil para alcanzar su coste de retirada (3 fisicas) y poder RETIRARLO
    # (protegerlo) -> promover al sano -> Syrup Storm letal. Cubre el adjunte
    # MANUAL (OptionType.ATTACH) y el objetivo de Ripening Charge
    # (SelectContext.ATTACH_FROM). Solo si la retirada es COMPLETABLE este
    # turno: bastan las Plantas de la mano y los adjuntes disponibles (1
    # manual + una Ripening Charge por cada Hydrapple de banca).
    if (active and _hydra_fragile_pivot
            and _hls_my_act is not None
            and _hls_my_act.id == Hydrapple_ex
            and _hls_act_phys < _hls_act_rc):
        _hfp_need = _hls_act_rc - _hls_act_phys
        _hfp_grass_hand = sum(
            1 for _c in (my_state.hand or [])
            if _c.id == Basic_Grass_Energy)
        _hfp_bench_hydra_ct = sum(
            1 for _bp in (my_state.bench or [])
            if _bp is not None and _bp.id == Hydrapple_ex)
        _hfp_max_attach = (0 if state.energyAttached else 1) + _hfp_bench_hydra_ct
        if (_hfp_need >= 1 and _hfp_grass_hand >= _hfp_need
                and _hfp_max_attach >= _hfp_need):
            return 41000

    # Pivote Ripening -> retirar -> promover Tapu letal vs muro inmune (user,
    # log 86028607 turno 22): si _ripen_retreat_ko_pivot esta activo (activo
    # = Hydrapple ex bloqueado por Crustle con un Tapu de banca YA LISTO que
    # noquea al muro), la Planta de Ripening Charge debe ir al PROPIO
    # Hydrapple ACTIVO para alcanzar su coste de retirada (efectivo) y poder
    # retirarlo -> subir a Tapu -> Wood Hammer letal. Cubre el objetivo de
    # Ripening Charge (SelectContext.ATTACH_FROM); el adjunte manual ya se
    # gasto en cargar a Tapu (por eso el pivote solo existe tras esa carga).
    if _ripen_retreat_ko_pivot and active and pokemon.id == Hydrapple_ex:
        return 41000

    # Espejo NO letal de `_carga_activo_remata` (ver el flag): la carga deja
    # al ACTIVO en su coste de ataque pero el ataque no remata. Aun asi es la
    # unica forma de atacar hoy (no hay atacante de banca listo y promovible),
    # y hacer chip vale infinitamente mas que cerrar el turno sin atacar --
    # el mismo razonamiento que `_attach_enable_retreat_attack` (31200), pero
    # sin pagar retirada. Va DESPUES de todas las lineas letales (41000+),
    # que siguen mandando, y ANTES de las cargas de atacantes FUTUROS.
    if active and _carga_activo_habilita_ataque:
        return SCORE_CARGA_ACTIVO_ATAQUE

    # Regla (user, log 85857426 paso 37, vs Mega Lucario, PERDIMOS): NO
    # malgastar el adjunte manual en un Tapu Bulu ACTIVO condenado. Si el
    # activo es un Tapu Bulu que, tras adjuntar 1 Planta, SIGUE sin poder
    # atacar (Wood Hammer necesita 4 efectivas) y SIGUE sin poder retirarse
    # (energia FISICA < coste de retirada 3) — la energia no le sirve este
    # turno y sera noqueado el proximo — y ademas en la banca hay un Teal
    # Mask Ogerpon ex sin cargar (energia < 3) al que Teal Dance puede
    # adjuntar Grass + ROBAR, vetar el adjunte manual (-1). Asi el orden de
    # jugada (ATTACH es tier ENERGY=1, Teal Dance ABILITY es tier 0) ya no
    # antepone la carga desperdiciada y se usa Teal Dance: no se pierde la
    # energia y se roba una carta. Acotado a Mega Lucario (remate rival
    # fijo y alto). Cubre el adjunte MANUAL (OptionType.ATTACH) y el objetivo
    # de Ripening Charge (SelectContext.ATTACH_FROM).
    if (active and pokemon.id == Tapu_Bulu and op_is_lucario_deck
            and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
        _twt_eff_after = energy_count + _grass_attach_unit()
        _twt_phys_after = _physical_energy(energy_count) + 1
        _twt_rc = RETREAT_COST.get(Tapu_Bulu, 3)
        if _twt_eff_after < 4 and _twt_phys_after < _twt_rc:
            for _twt_bp in (my_state.bench or []):
                if (_twt_bp is not None
                        and _twt_bp.id == Teal_Mask_Ogerpon_ex
                        and len(_twt_bp.energies) < 3):
                    return SCORE_VETO

    # Prioridad maxima: cargar Tapu Bulu de banca como atacante futuro
    # cuando el activo ya asegura el KO y Meganium esta en juego. Reusada
    # tanto por la adjuncion manual (OptionType.ATTACH) como por el objetivo
    # de Ripening Charge (SelectContext.ATTACH_FROM).
    if (_tapu_future_charge and not active and pokemon.id == Tapu_Bulu
            and len(pokemon.energies) * _grass_mult() < 4):
        return 40000

    # Cargar Meganium de banca como atacante FUTURO de 1 premio vs Alakazam
    # (140 derrota a la linea Alakazam). Menor prioridad que Tapu Bulu y que
    # las cargas de banca a 0 (26000-30000): 25000 solo gana cuando los
    # atacantes principales ya no necesitan la energia. Cubre adjunte manual
    # y objetivo de Ripening Charge. Ver `_meganium_alk_future_charge`.
    # Meganium ATACANTE de 1 premio ESTE turno vs Alakazam: domina la carga
    # del ex activo (41000) para que el adjunte manual complete su coste y se
    # ataque con el 1-premio (retirar el ex, promover Meganium). Ver flag.
    if (_meganium_alk_1prize_attacker and not active and pokemon.id == Meganium
            and len(pokemon.energies) * _grass_mult() < 4):
        return 43000

    if (_meganium_alk_future_charge and not active and pokemon.id == Meganium
            and len(pokemon.energies) * _grass_mult() < 4):
        return 25000

    if (ESTADO.op_is_crustle_deck or ESTADO.op_is_cornerstone_deck) and \
            pokemon.id == Meganium and energy_count >= 4:
        return SCORE_VETO

    if is_confused and _conf_active is not None:
        if (not active and _conf_is_matchup_attacker(pokemon.id)
                and not _conf_can_attack_pkmn(pokemon)):
            return 40000
        if active and _conf_bench_attacker_ready and not _conf_active_can_retreat:
            _ret_eff_es = energy_count * _grass_mult()
            if _ret_eff_es < RETREAT_COST.get(pokemon.id, 1):
                return 35000
        if (active and not _conf_bench_attacker_body
                and _conf_is_matchup_attacker(pokemon.id)
                and not _conf_active_can_attack):
            return 33000

    if ESTADO.op_is_cornerstone_deck and not ESTADO.op_is_crustle_deck:

        if pokemon.id == Tapu_Bulu:

            if energy_count < 4:
                score += 22000
                if active:
                    score += 100
            else:
                score -= 50
        elif pokemon.id == Pinsir:

            if energy_count < 2:
                score += 23000
                if active:
                    score += 100
            else:
                score -= 50
        elif pokemon.id == Teal_Mask_Ogerpon_ex:

            if active and energy_count == 0:
                _tapu_ready_cs = any(
                    bp is not None and bp.id == Tapu_Bulu and len(bp.energies) >= 4
                    for bp in (my_state.bench or []))
                if _tapu_ready_cs:
                    score += 10
                    score += 40
                else:
                    score -= 500
            else:
                score -= 500
        else:

            if active and energy_count == 0:
                _tapu_ready_cs2 = any(
                    bp is not None and bp.id == Tapu_Bulu and len(bp.energies) >= 4
                    for bp in (my_state.bench or []))
                if _tapu_ready_cs2:
                    score += 10
                    score += 30
                else:
                    score -= 300
            else:
                score -= 300
        return score

    if ESTADO.op_is_crustle_deck:

        # Energia EXCEDENTE: si el Tapu Bulu ACTIVO ya esta cargado (>=4
        # efectivas) puede atacar sin mas, asi que la adjuncion manual de
        # este turno no debe desperdiciarse sobrecargandolo. Se redirige por
        # orden de prioridad: (1) otro Tapu Bulu de banca que aun no llega a
        # 4 efectivas, (2) Dipplin sin energia, (3) Meganium sin sus 4
        # efectivas. Si ninguno la necesita, se GUARDA la energia (score
        # negativo -> el agente no la juega).
        _ctm_act_te = my_state.active[0] if my_state.active else None
        _ctm_active_tapu_full = (
            _ctm_act_te is not None
            and _ctm_act_te.id == Tapu_Bulu
            and len(_ctm_act_te.energies) * _grass_mult() >= 4)
        if _ctm_active_tapu_full:
            if (pokemon.id == Tapu_Bulu and not active
                    and energy_count * _grass_mult() < 4):
                return 40000
            if pokemon.id == Dipplin and energy_count < 1:
                return 39000
            if pokemon.id == Meganium and energy_count * _grass_mult() < 4:
                return 38000
            return SCORE_VETO

        if pokemon.id == Tapu_Bulu:

            # Regla (user, log 85802744 paso 55): si Meganium AUN no esta en
            # juego pero se puede evolucionar ESTE turno (Bayleef en juego +
            # Meganium en mano), Wild Growth doblara las energias fisicas
            # ACTUALES de Tapu Bulu. Si con ese doblado Tapu ya alcanza sus 4
            # efectivas (>= 2 energias fisicas ahora), NO malgastar el adjunte
            # manual sobrecargandolo: se reserva la energia y se evoluciona
            # Meganium, que deja a Tapu listo para atacar sin gastarla. El
            # scorer es codicioso (no simula "evolucionar primero"), por eso
            # aqui, con Meganium fuera de juego, veia a Tapu con solo sus
            # fisicas (< 4) y le daba prioridad de carga.
            _meg_evolvable_now_tapu = (
                not active
                and not ESTADO.meganium_in_play
                and field_counts.get(Bayleef, 0) >= 1
                and hand_counts.get(Meganium, 0) >= 1)
            if _meg_evolvable_now_tapu and energy_count * 2 >= 4:
                return SCORE_VETO

            # len(energies) YA es la energia EFECTIVA (la observacion duplica
            # la Planta por Wild Growth): Wood Hammer necesita 4 efectivas.
            # No sobrecargar mas alla de eso.
            _tapu_eff_ct = energy_count * _grass_mult()
            if _tapu_eff_ct < 4:
                score += 20000
                if _ctm_tapu_high:

                    score += 5000
                if _ctm_chikorita_bench:

                    score += 11000
                if active:
                    score += 100
            else:
                score -= 50
        elif pokemon.id == Teal_Mask_Ogerpon_ex:

            if active and energy_count == 0:

                _tapu_bench_og = any(
                    bp is not None and bp.id in (Tapu_Bulu, Dipplin, Meganium) and
                    len(bp.energies) >= (1 if bp.id == Dipplin else 4)
                    for bp in (my_state.bench or []))
                if _tapu_bench_og:
                    score += 10
                    score += 40
                else:
                    score -= 500
            else:
                score -= 500
        elif pokemon.id == Applin:

            if energy_count < 1:
                score += 22000
                if _ctm_applin_bench and not _ctm_chikorita_bench:

                    score += 6500
                if active:
                    score += 100
            else:
                score -= 40
        elif pokemon.id == Dipplin:

            if _ctm_charge_active_dipplin and active and energy_count < 1:

                score = 50000
            elif _ctm_tapu_high:

                score = SCORE_VETO
            elif energy_count < 1:
                score += 23000
                if active:
                    score += 100
            else:
                score = SCORE_VETO
        elif pokemon.id == Pinsir:

            if energy_count < 2:
                score += 21000
                if active:
                    score += 100
            else:
                score -= 50
        elif pokemon.id == Meganium:

            # Meganium es el duplicador clave contra Crustle; no debe quedarse
            # de muro en el activo. Si esta activo y aun no puede retirarse
            # (0 energias) y hay un atacante no-ex de banca ya cargado para
            # promover, priorizamos cargarle 1 energia: con Wild Growth
            # 1 energia basica = {G}{G}, suficiente para pagar su retirada de 2
            # y sacarlo a la banca el proximo turno.
            _meg_promo_ready = any(
                bp is not None and (
                    (bp.id == Tapu_Bulu and
                     len(bp.energies) * _grass_mult() >= 4) or
                    (bp.id == Dipplin and len(bp.energies) >= 1) or
                    (bp.id == Pinsir and
                     len(bp.energies) * _grass_mult() >= 2))
                for bp in (my_state.bench or []))

            _tapu_in_play_meg = field_counts.get(Tapu_Bulu, 0) >= 1
            _dipplin_in_play_meg = any(
                bp is not None and bp.id == Dipplin
                for bp in (list(my_state.active or []) + list(my_state.bench)))

            # len(energies) YA es la energia EFECTIVA (Wild Growth ya aplicado
            # en la observacion): Solar Beam necesita 4.
            _meg_eff = energy_count * _grass_mult()
            if active and energy_count == 0 and _meg_promo_ready:
                score += 24000
                score += 100
            elif not _tapu_in_play_meg and not _dipplin_in_play_meg and _meg_eff < 4:
                score += 19000
                if active:
                    score += 100
            elif _meg_eff < 4:
                score -= 50
            else:
                score -= 80
        else:

            if (active and pokemon.id in OUR_EX_IDS
                    and (_ex_stuck_promo_ready or _cubchoo_lock_stuck)
                    and energy_count * _grass_mult()
                        < RETREAT_COST.get(pokemon.id, 1)):
                # Nuestro ex activo no puede danar al Crustle (inmune) y hay
                # un atacante no-ex LISTO en banca: cargamos el ex hasta su
                # coste de retirada para poder retirarlo el proximo paso y
                # promover al atacante que SI golpea al Crustle.
                # `_cubchoo_lock_stuck`: activo Hydrapple ex bloqueado por
                # Snotted Up -- enrutar la energia al ACTIVO para habilitar la
                # retirada hacia el atacante de banca (paso 82).
                score += 24000
                score += 100
            elif active:
                score += 10

                _tapu_on_bench = field_counts.get(Tapu_Bulu, 0) >= 1
                if _tapu_on_bench and energy_count == 0:
                    score += 50
                else:
                    score -= 300
            else:
                score -= 300
        return score

    if neutralization_zone_active:
        if pokemon.id == Tapu_Bulu:
            effective_energy = energy_count * _grass_mult()
            if active:
                score += 10
                if effective_energy < 4:
                    score += 23200
                else:
                    score -= 50
            else:
                if effective_energy < 4:
                    score += 600
                else:
                    score -= 80
            return score
        elif pokemon.id == Dipplin:
            if active:
                score += 10
                if energy_count < 1:
                    score += 23200
                else:
                    score -= 30
            else:
                if energy_count < 1:
                    score += 400
                else:
                    score -= 50
            return score
        elif pokemon.id == Pinsir:

            effective_energy = energy_count * _grass_mult()
            if active:
                score += 10
                if effective_energy < 2:
                    score += 23000
                else:
                    score -= 40
            else:
                if effective_energy < 2:
                    score += 380
                else:
                    score -= 60
            return score
        elif pokemon.id == Meganium:

            effective_energy = energy_count * _grass_mult()
            if active:
                score += 10
                if effective_energy < 4:
                    score += 15000
                else:
                    score -= 100
            else:
                if effective_energy < 4:
                    score += 300
                else:
                    score -= 100
            return score
        elif pokemon.id == Teal_Mask_Ogerpon_ex:

            if energy_count >= 2:
                score -= 500
            elif active:
                score += 10
                score += 100
            else:
                score += 200
            return score
        elif pokemon.id in OUR_EX_IDS:

            _op_act_nz_e = op_state.active[0] if op_state.active else None
            _op_nz_e_rb = False
            if _op_act_nz_e is not None:
                _op_nz_e_data = card_table[_op_act_nz_e.id]
                _op_nz_e_rb = (_op_nz_e_data.ex or _op_nz_e_data.megaEx)
            if _op_nz_e_rb:
                pass
            elif active:
                score += 10
                score -= 200
                return score
            else:
                score -= 300
                return score

    if (ESTADO.meganium_in_play and _active_pokemon is not None
            and _active_pokemon.id == Hydrapple_ex
            and len(_active_pokemon.energies) >= 1
            and _bench_has_chargeable
            and not ESTADO.op_is_crustle_deck and not ESTADO.op_is_cornerstone_deck
            and not neutralization_zone_active):

        if active:
            return SCORE_VETO
        _raw_mb = len(pokemon.energies)
        if pokemon.id == Hydrapple_ex:
            return 20000 if _raw_mb < 1 else -1
        if pokemon.id == Teal_Mask_Ogerpon_ex:

            return 19000 if _raw_mb < 2 else 5000
        if pokemon.id == Dipplin:
            return 18000 if _raw_mb < 1 else -1
        if pokemon.id == Meganium:
            return 17000 if _raw_mb < 2 else -1
        if pokemon.id == Tapu_Bulu:
            return 16000 if _raw_mb < 2 else -1
        return SCORE_VETO

    if (_active_hydra_capped and _bench_has_chargeable
            and not ESTADO.op_is_crustle_deck and not ESTADO.op_is_cornerstone_deck
            and not neutralization_zone_active):
        if active:
            return SCORE_VETO
        _eff_bench_sc = energy_count * _grass_mult()
        if pokemon.id == Teal_Mask_Ogerpon_ex:

            if energy_count < 3:
                return 20000 - energy_count * 100
            return SCORE_VETO
        if pokemon.id == Meganium:
            return 18000 if energy_count < 2 else -1
        if pokemon.id == Hydrapple_ex:
            return 16000 if _eff_bench_sc < 2 else -1
        if pokemon.id == Dipplin:
            return 14000 if energy_count < 1 else -1
        if pokemon.id == Applin:
            return 12000 if energy_count < 2 else -1
        if pokemon.id == Tapu_Bulu:
            _tapu_cap_sc = 4
            return 10000 if _eff_bench_sc < _tapu_cap_sc else -1

        return 8000 if energy_count < 1 else -1

    if _active_already_kos and not active and energy_count == 0 \
            and not ESTADO.op_is_crustle_deck and not ESTADO.op_is_cornerstone_deck \
            and not neutralization_zone_active:
        if pokemon.id in NON_ATTACKER_ENERGY_WASTE_IDS:
            return SCORE_VETO
        return {
            Hydrapple_ex: 30000,
            Teal_Mask_Ogerpon_ex: 29000,
            Dipplin: 28000,
            Meganium: 27000,
            Tapu_Bulu: 26000,
        }.get(pokemon.id, 25000)

    _bench_hydra_pre_target = any(
        bp is not None and bp.id in (Dipplin, Applin) and len(bp.energies) < 1
        for bp in (my_state.bench or []))
    if (not ESTADO.op_is_crustle_deck and not ESTADO.op_is_cornerstone_deck
            and not neutralization_zone_active
            and not _active_needs_energy
            and _active_pokemon is not None
            and _active_pokemon.id != Hydrapple_ex
            and _bench_hydra_pre_target):
        if active:
            return SCORE_VETO
        if pokemon.id == Dipplin and energy_count < 1:
            return 24000
        if pokemon.id == Applin and energy_count < 1:
            return 23500

    if active:
        score += 10

        if active_ko_likely:
            _after_energy = energy_count + _grass_attach_unit()
            _after_energy_raw = energy_count + 1

            _can_attack_after = False
            if pokemon.id == Hydrapple_ex:
                _can_attack_after = (_after_energy >= 2)
            elif pokemon.id == Dipplin:
                _can_attack_after = (_after_energy_raw >= 1)
            elif pokemon.id == Teal_Mask_Ogerpon_ex:
                _can_attack_after = (_after_energy >= 3 or _ogerpon_td_manual_lethal)
            elif pokemon.id == Tapu_Bulu:
                _can_attack_after = (_after_energy >= 4)
            elif pokemon.id == Fezandipiti_ex:
                _can_attack_after = (_after_energy >= 3)

            _retreat_cost_pkmn = RETREAT_COST.get(pokemon.id, 1)
            # Energia efectiva tras adjuntar (Wild Growth duplica Planta):
            # 1 energia en Meganium ya paga su retirada de 2.
            _can_retreat_after = (_after_energy >= _retreat_cost_pkmn)

            _has_bench_atk_retreat = False
            for _bp in (my_state.bench or []):
                if _bp is not None and _bp.id in (Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Fezandipiti_ex):
                    _has_bench_atk_retreat = True
                    break

            if not _can_attack_after and (not _can_retreat_after or not _has_bench_atk_retreat):
                return score - 100

        effective_energy = energy_count * _grass_mult()

        if pokemon.id == Hydrapple_ex:
            energy_threshold = 2
            if effective_energy < energy_threshold:
                score += 23200
                if op_is_fire_deck:
                    score += 500
                if op_is_aggro_deck or op_is_beedrill_deck:
                    score += 300
            elif energy_count < 2:

                score += 23200
            elif _extra_energy_enables_ko(Hydrapple_ex, energy_count):

                score += 15000
            elif _bench_attacker_ready and not _active_already_kos:

                score += 23200
            else:
                score -= 100
        elif pokemon.id == Dipplin:
            if energy_count < 1:
                score += 23200
                if op_has_ex_immune_active:
                    score += 500
            else:
                score -= 30
        elif pokemon.id == Teal_Mask_Ogerpon_ex:
            if effective_energy < 3:
                score += 23200
            elif energy_count < 3:

                score += 23200
            elif _extra_energy_enables_ko(Teal_Mask_Ogerpon_ex, energy_count):

                score += 15000
            elif (_bench_attacker_ready and not _bench_attacker_needs_energy
                    and not _active_already_kos):

                score += 23200
            else:

                score -= 100
        elif pokemon.id == Tapu_Bulu:

            if energy_count < 4:
                if ESTADO.meganium_in_play:
                    score += 23200
                    if op_has_ex_immune_active:
                        score += 500
                else:
                    score += 15000
            else:
                score -= 80
        elif pokemon.id == Meganium:

            _sylveon_active = (op_state.active and op_state.active[0] is not None
                               and op_state.active[0].id == Sylveon)
            if op_is_drednaw_deck or _sylveon_active:

                _meg_eff = energy_count * _grass_mult()
                if _meg_eff < 4:
                    score += 23200
                else:
                    score -= 100
            elif energy_count < 2:
                score += 23200
            else:
                score -= 500
        elif pokemon.id in (Chikorita, Bayleef):

            _retreat_cost = RETREAT_COST.get(pokemon.id, 1)
            # Wild Growth duplica la energia basica de Planta para la retirada.
            _cb_ret_eff = energy_count * _grass_mult()
            if _cb_ret_eff < _retreat_cost:
                score += 23200
            else:
                score -= 500
        elif pokemon.id == Meowth_ex:

            # Meowth ex ACTIVO: solo lo cargamos cuando la retirada es NECESARIA,
            # es decir cuando hay un atacante real en banca al que promover. Si
            # no hay a quien pasar, cargarlo no aporta y se demota.
            if energy_count == 0:
                _has_bench_attacker = False
                for _bp in my_state.bench:
                    if _bp is not None and _bp.id in (Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Fezandipiti_ex):
                        _has_bench_attacker = True
                        break
                if _has_bench_attacker:
                    score += 23200
                else:
                    score -= 500
            else:
                score -= 500
        elif pokemon.id == Fezandipiti_ex:

            _fez_eff = energy_count * _grass_mult()
            _fez_eff_after = energy_count + _grass_attach_unit()
            if _fez_eff >= 3:

                score -= 100
            elif _fez_eff_after >= 3:

                score += 23200
            elif energy_count == 0:

                _has_bench_attacker = False
                for _bp in my_state.bench:
                    if _bp is not None and _bp.id in (Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex, Tapu_Bulu):
                        _has_bench_attacker = True
                        break
                if _has_bench_attacker:
                    score += 23200
                else:
                    score += 5000
            else:

                score -= 200
        elif pokemon.id == Pinsir:

            if effective_energy < 2:
                score += 23200
                if op_has_ex_immune_active:
                    score += 500
            else:
                score -= 60

    else:

        if pokemon.id == Teal_Mask_Ogerpon_ex:
            if energy_count < 2:
                score += 400
            elif energy_count < 3:
                score += 250
            elif _extra_energy_enables_ko(Teal_Mask_Ogerpon_ex, energy_count):
                score += 150
            else:
                score -= 100
        elif pokemon.id == Tapu_Bulu:

            if not ESTADO.meganium_in_play:
                score -= 100
            elif op_has_ex_immune_active or op_has_ex_immune_bench:
                if energy_count < 2:
                    score += 350
                else:
                    score -= 80
            elif energy_count < 2:
                score += 100
            else:
                score -= 80
        elif pokemon.id == Hydrapple_ex:

            effective_energy = energy_count * _grass_mult()
            if effective_energy < 2:

                score += 23100
                if op_is_fire_deck:
                    score += 100
                if op_is_aggro_deck or op_is_beedrill_deck:
                    score += 80
            elif energy_count < 2:
                score += 150
                if op_is_fire_deck:
                    score += 100
            elif _extra_energy_enables_ko(Hydrapple_ex, energy_count):
                score += 100
            else:
                score -= 100
        elif pokemon.id == Dipplin:
            if energy_count < 1:
                score += 150
                if op_has_ex_immune_active:
                    score += 80

                if op_is_drednaw_deck:
                    score += 200

                elif op_is_sylveon_deck:
                    score += 150
            else:
                score -= 30
        elif pokemon.id == Applin:

            if energy_count == 0:
                score += 40
            elif energy_count == 1:
                _applin_full_evolve_now = (hand_counts.get(Dipplin, 0) >= 1 and
                                           hand_counts.get(Hydrapple_ex, 0) >= 1)
                if _applin_full_evolve_now and not ESTADO.meganium_in_play:
                    score += 50
                else:
                    score -= 300
            else:
                score -= 400
        elif pokemon.id == Meganium:

            _sylveon_threat = (op_is_sylveon_deck and op_has_ex_immune_active and
                               op_state.active and op_state.active[0] is not None and
                               op_state.active[0].id == Sylveon)
            if op_is_drednaw_deck or _sylveon_threat:
                _meg_eff_bench = energy_count * _grass_mult()
                if _meg_eff_bench < 4:
                    score += 500
                else:
                    score -= 50
            elif energy_count >= 2:
                score -= 100
            elif (has_hydrapple and _active_pokemon is not None and
                  _active_pokemon.id == Hydrapple_ex and energy_count < 1):
                score += 60
            else:
                score -= 50
        elif pokemon.id == Meowth_ex:
            score -= 100
            if op_has_froslass:
                score -= 50
        elif pokemon.id == Fezandipiti_ex:

            _fez_energy_req = 3
            _is_fez_attacker = (ESTADO.plan.attacker >= 1 and
                my_state.bench[ESTADO.plan.attacker - 1] is not None and
                my_state.bench[ESTADO.plan.attacker - 1].id == Fezandipiti_ex)
            if _is_fez_attacker and energy_count < _fez_energy_req:
                score += 300
            elif energy_count < _fez_energy_req and not any(
                p is not None and p.id in (Hydrapple_ex, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Dipplin)
                for p in my_state.bench + list(my_state.active or [])):

                score += 200
            else:
                score -= 100
            if op_has_froslass:
                score -= 50
        elif pokemon.id == Pinsir:

            _pinsir_eff_bench = energy_count * _grass_mult()
            if op_has_ex_immune_active or op_has_ex_immune_bench:
                if _pinsir_eff_bench < 2:
                    score += 350
                else:
                    score -= 60
            elif _pinsir_eff_bench < 2:
                score += 80
            else:
                score -= 60

    return score


__all__ = ['_energy_score_base']
