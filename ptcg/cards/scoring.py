"""Scoring constants shared by several phases -- and the BANDS they live in.

Every decision the agent makes is a number, and the numbers are not arbitrary:
they are arranged in BANDS, so that what matters more can never be outbid by
what matters less. Read this before adding a constant anywhere, because the
value you pick is a claim about priority, and picking it by eye is how a sound
rule ends up vetoing a decisive one.

THE GLOBAL SCALE (defined in `ptcg/cards/ids.py`, listed here because that is
where the reasoning belongs):

    50000   SCORE_WIN_GAME       ending the game beats everything
    20000   SCORE_DEVELOP_BASE   base for benching a Pokemon
    10000   SCORE_ITEM_BASE      base for playing a non-Pokemon card
        -1  SCORE_VETO           do not play this
      -100  SCORE_CANCEL         below the veto, so an index tie cannot pick it
     -5000  SCORE_USELESS_ATTACK attacking into an immunity
    -10000  SCORE_NEVER          never
   -100000  SCORE_FORBID         illegal or self-harming; absolutely not

Two properties of that scale carry most of the weight. The negatives are
ORDERED rather than a single "no", so that vetoes of different strength do not
collapse into a tie. And a tie is genuinely dangerous: when two options share a
score the MENU ORDER decides, which is the engine's order and not ours -- the
reason several constants below exist purely to keep two rungs apart.

THE PROMOTION BAND, which is what most of this file defines. Choosing who takes
the front seat after a knockout is the decision with the most competing
opinions, so it has its own layered structure:

    +20000  PROMO_KO_BONUS       whoever knocks their active out goes first
     +1200  PROMO_KO_FRONT       ...and among knockers, who outlives whom
     15000  PROMO_CLOSER_SEAT    at OUR match point, the body one attachment
                                 from the knockout that ENDS the game
      9450  PROMO_LAST_STAND     at their match point, who absorbs the reply
     -6000  PROMO_DOOMED_PENALTY a body that dies anyway yields to a survivor
     -1500  PROMO_PRIZE_PENALTY  per extra prize handed over
    -30000  PROMO_MATCH_POINT_VETO   this promotion LOSES the game

Each constant's own comment carries the game that set its value and, more
usefully, the neighbouring numbers it had to clear or stay under. That
arithmetic is the real specification: `PROMO_KO_FRONT` is 1200 because it must
sit above every incidental adjustment in its branch and below every deliberate
one, and the comment enumerates both sides.

WHY A TIE-BREAK MUST STAY SMALL. A generic tie-break exists to order options
that measured rules do not distinguish. Make it large and it starts overruling
rules that were each written from a specific lost game -- which is exactly what
happened when `PROMO_KO_FRONT` was first tried wider, and it moved corpus
decisions onto bodies those matchups deliberately keep back.

The two helpers here, `_SUPP_PLAY_IDS` and `_purchase_of_this_turn`, share one
doctrine: the decision that SPENDS a resource and the decision that prices the
result afterwards must not be able to contradict each other, so both consult
the same source.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.cards.ids import Dipplin, Fezandipiti_ex, Hydrapple_ex, Meganium, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.cards.ids import Boss_Orders, Dawn, Lanas_Aid, Lillie_Determination, Xerosic_Machinations


# Floor of the commitment: above the maximum of any other Supporter in hand
# (Xerosic ~7300 is the highest) so the tie-break does not depend on the deck.
SCORE_LD_SUPP_COMPROMETIDO = 8000


# --- WHICH Supporter will be PLAYED this turn? ------------------------------
# Only ONE Supporter is played per turn, so any decision that SPENDS a resource
# to SEARCH for a Supporter (Meowth ex / Last-Ditch Catch, Poke Pad...) needs to
# know BEFOREHAND who is going to take that single slot. These two helpers are
# the single source of that answer: they dispatch to the SAME `_score_*` the
# scoring loop uses, so the decision to spend the resource and the decision of
# which Supporter ends up being played cannot contradict each other.
_SUPP_PLAY_IDS = (Boss_Orders, Xerosic_Machinations, Lillie_Determination,
                  Dawn, Lanas_Aid)


# Main attackers evaluated in the ready-to-attack blocks.
MAIN_ATTACKERS = (
    Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex,
    Tapu_Bulu, Fezandipiti_ex, Meganium, Pinsir,
)


# WHO GOES IN FRONT OF THE MEGA STARMIE LINE. The top of the user's order and
# the gap between its rungs. The band sits ABOVE the sacrifice menu's own top
# rung (6000, the Chikorita of `_doomed_sac_context`) because it is a different
# question with a different answer: that order asks which of two evolution
# lines we would rather spend, this one asks which body pays ONE prize instead
# of two against a deck that one-shots any ex we leave in front. Seven rungs
# 100 apart -- Tapu Bulu, Applin without energy, Applin with energy, Chikorita,
# Dipplin, Bayleef, Meowth ex -- so no two of them can ever tie and have the
# menu order decide. See STARMIE_SAC_PROMOTE_ORDER in ptcg/cards/ids.py.
OPENING_SAC_PROMOTE_TOP = 7000
OPENING_SAC_PROMOTE_STEP = 100


# Terminal PROMOTION adjustment (see "SURVIVAL WHEN PROMOTING"). The doomed body
# drops far enough to yield to any real survivor (the measured case: a charged
# Ogerpon 4557 -> -1443, below the Hydrapple ex at 259).
PROMO_DOOMED_PENALTY = 6000


# With no survivors, each extra prize we hand over costs this much.
PROMO_PRIZE_PENALTY = 1500


# Whoever KNOCKS OUT the opposing active is promoted above anyone who does not,
# tank included (user). Above the maximum score of the promotion branches
# (9500 = `_promote_setup_ko_attacker`) so that it is a GUARANTEE and does not
# depend on the knocker scoring higher base than the tank:
# `_ko_prefer_basic_general` gives 8500+ to a 1-prize basic and the sturdy wall
# 6100, so a knocker at ~4500 could lose. Among several knockers the base score
# decides -- EXCEPT where `PROMO_KO_FRONT` speaks (see below).
PROMO_KO_BONUS = 20000


# THE FRONT SPOT AMONG THE ONES THAT KNOCK OUT (user, registro_012 step 172 vs
# Alakazam). "Among several knockers the base score decides" was measured false:
# that base score is 500 + `hp // 10` + energies + a flavour bonus per species,
# so between a Teal Mask Ogerpon ex at 210 HP and a Hydrapple ex at 140 -- both
# finishing the same Alakazam -- HP was worth SEVEN points and the flavour
# ninety. This demotes a knocker that an EQUALLY PRICED knocker outlives: the
# knockers are grouped by price (`ko_front_price_rung`) and ordered by current HP
# INSIDE each group. Across prices it says nothing -- which price we would rather
# pay is already decided by rules measured one board at a time.
#
# 1200 sits ABOVE every incidental adjustment of that branch -- the 150 between
# "attacks now" and "attacks after attaching", `hp // 10` (<= 33), the energy
# count, the +-100 per species, the 120/40 of the promotion lookahead, the -250
# for weakness, the -300 of anti-Cubchoo and the +-280 of the Drednaw / Sylveon
# / Neutralization Zone blocks -- and BELOW every deliberate one, which is where
# this generic tie-break has to yield: the +2000 of the matchup attacker when
# confused, the +2500 of the prize mismatch, the +3000 of prize denial, the
# +4000 of the best attacker, the +5000 / +6000 of the anti-wall rules.
#
# It stays inside the knocker band by construction: 20000 - 1200 = 18800, and
# even stacked with the match-point penalty of the sibling rule
# (20000 - 6000 - 1200 = 12800) it is still far above the 9500 of the highest
# body that takes no prize.
PROMO_KO_FRONT = 1200


# THE FRONT SPOT UNDER A LOCK THAT MUTES IT (user, registro_010 step 81 vs a
# Cubchoo stall deck). The tie-break above orders knockers by who OUTLIVES whom,
# and against Cubchoo that question has no content: *Snotted Up* does 10 damage,
# every candidate outlives it, and HP decided the seat. What decides it there is
# MOBILITY -- the lock mutes whatever we put in front, so the body promoted today
# has to buy its way out again tomorrow, and Hydrapple ex pays 3 (two whole Grass
# cards under Wild Growth) where Teal Mask Ogerpon ex pays 1. On the board that
# produced this the two of them knocked out the same 70 HP Cubchoo and the HP
# tie-break handed the seat to the Hydrapple by 1272 points.
#
# 1800 is set by the two numbers it sits between: ABOVE `PROMO_KO_FRONT` (1200)
# plus the -300 of the anti-Cubchoo nail penalty it completes, because those two
# are exactly what it has to overrule; and BELOW the +2000 of the matchup
# attacker when confused, the first of the deliberate rules this must still yield
# to. Like its neighbour it is a penalty on the dominated knocker and never a
# bonus, so it only ever reorders INSIDE the +20000 band: stacked with everything
# that can hit the same body (20000 - 1800 - 1200 - 6000 = 11000) it is still
# above the 9500 of the highest body that takes no prize.
PROMO_KO_ROTATION = 1800


# EL ASIENTO ES DEL CUERPO QUE PAGO LA RETIRADA (user, episode 93519870 step 113
# vs Alakazam). El pivote de este matchup retira nuestro ex diciendo "subo un
# cuerpo de UN premio y entrego 1 en vez de 2", y la promocion que viene despues
# es otro menu que no conoce esa frase: los dos candidatos entran en la misma
# banda (+PROMO_KO_BONUS) y el ex gana por los adornos. En el tablero del
# usuario, un Teal Mask Ogerpon ex con seis Grass a 20557 contra el Dipplin a
# 20525 -- TREINTA Y DOS puntos, y con ellos la premisa entera de la retirada.
#
# Por eso es del tamaño de un desempate, como sus dos vecinos de arriba, y no de
# una banda. 2200 lo fijan los numeros entre los que va: POR ENCIMA de
# `PROMO_KO_FRONT` (1200) -- "quien sobrevive a quien", que es justamente el
# argumento que el pivote compra en contra, porque el cuerpo barato viene a
# morir --, de `PROMO_KO_ROTATION` (1800) y del +2000 del atacante del matchup
# confundido, para no empatar con ninguno (un empate deja decidir al ORDEN DEL
# MENU, que es el del motor y no el nuestro); y MUY POR DEBAJO de
# `PROMO_DOOMED_PENALTY` (6000) y de `PROMO_MATCH_POINT_VETO` (-30000), las
# reglas deliberadas que siguen teniendo la ultima palabra. Apilado con todo lo
# que puede caer sobre el mismo cuerpo sigue dentro de su banda:
# 20000 + 2200 - 6000 - 1800 - 1200 = 13200, por encima de los 9500 del cuerpo
# mas alto que no se lleva ningun premio.
#
# Solo es un BONUS, y solo para el cuerpo de un premio que noquea: nunca baja a
# nadie, asi que no puede invertir un orden que otra regla haya fijado.
PROMO_PIVOT_PAYS_FOR_THE_SEAT = 2200


# THE SEAT COSTS THE COVER IT LEAVES BEHIND (user, pending written 12 August
# 2026 from episode 92355371 step 62 vs Festival Lead, LOST). The Tera of a
# benched Teal Mask Ogerpon ex prevents ALL damage from attacks while it is on
# the BENCH -- `_projected_incoming` returns 0 for it there -- so promoting it
# does two things at once that no rung was charging for: it gives up an
# untouchable body, and it stands TWO prizes in front of an engine that spreads
# knockouts. In the record it came up, ate 120 and sat at 90 of 210, where the
# next Do the Wave took it and the two prizes with it.
#
# A PRICE, NOT A VETO, and deliberately small. The body that KNOCKS OUT still
# goes first (+20000), a body that dies anyway still yields to a survivor
# (-6000) and the prize band still speaks when nobody endures (-1500 each): all
# three are measured rules written from their own lost games, and 500 cannot
# reach any of them. What it does reach is the band where the only argument for
# the ex is that it has the most HP -- on the record's board the Ogerpon scored
# 334 against the Applin's -78, and 412 is the whole distance between "the
# biggest body" and "the cheapest one".
#
# It is charged ONLY on the FORCED promotion, which is where the cover is real:
# on a voluntary retreat we are choosing to spend the turn moving, and the body
# that leaves the bench is being asked for something it can only do in front.
PROMO_TERA_COVER_PRICE = 500


# A named switch rather than an inline condition, so a census, a gate and the
# rules oracle can each measure this price as the ONLY difference between two
# arms.
PROMOTE_TERA_PAYS_FOR_ITS_COVER = True


# MATCH POINT: the opponent only needs to knock this body out to take the last
# prize. That is not a bad trade, it is losing the game -> veto, not a penalty.
# It goes BELOW SCORE_NEVER (-10000) on purpose: other promotion vetoes use that
# exact value (e.g. "the Meganium line does not go active") and a tie at -10000
# would leave the tie-break to the random order of the options, exactly between
# the body that endures and the one that makes us lose.
PROMO_MATCH_POINT_VETO = -30000


# THE LAST STAND: at their match point every body on our bench pays at least
# their remaining pile, so the price tag stops separating the candidates and
# what is left is who absorbs their reply best (`_mp_last_stand`).
#
# 9450 places it just BELOW the two branches that are about acting FIRST -- the
# guaranteed finisher (9500) and, above everything, the body that knocks out
# (+`PROMO_KO_BONUS`) -- and above the whole cheap-wall family (8500 + hp/10 of
# `_ko_prefer_basic_general`, 9000 for an Applin, 6100 for the sturdy basic):
# when their next knockout ends the game, taking a prize or removing their
# attacker still comes first, and handing over a cheaper corpse no longer does.
PROMO_LAST_STAND = 9450


# THE ATTACKER THAT CAN STILL WALK BACK (`_promo_deferred_attacker`). The front
# spot goes to the body that attacks -- today, or after this coming turn's
# attachment -- instead of to a cheap corpse, because the promotion resolves at
# the END of their turn and a body that can pay its own retreat is not obliged
# to be standing there when their reply lands.
#
# 9200 is fixed from both sides. ABOVE the whole cheap-wall family (9000 for an
# Applin, 8500 + hp/10 for a sturdy basic, 6100 for the refill wall), which is
# the family this rule exists to outrank: those hand over the slot to a body
# chosen for how little it costs when it dies, and this one says the dying is
# not settled yet. BELOW the two branches that promise something this one does
# not -- the last stand (9450), where nothing cheaper is left to defer to, and
# the guaranteed finisher (9500), which is this same sentence with a knockout
# attached -- and far below the body that knocks out today (+PROMO_KO_BONUS).
PROMO_DEFERRED_ATTACKER = 9200


# EL ASIENTO QUE CIERRA LA PARTIDA NO SE DESEMPATA (user, registro_013 step 174
# vs Alakazam, episode 93579160, PERDIDA -- deck-agnostic).
#
# Su Alakazam estaba a 140/140 y nuestro monton era de UN premio: ese cuerpo ES
# el resto de nuestra cuenta. En la banca, un Meganium con un Grass fisico -- dos
# simbolos bajo su propio Wild Growth -- a UNA carta de los cuatro de Solar Beam,
# cuyos 140 entierran al Alakazam; y en la mano, la Lana's Aid que saca ese Grass
# del descarte (la ruta (b) de `_promote_setup_ko_attacker`). El selector lo vio y
# lo nombro. Y aun asi el asiento se decidio por TRESCIENTOS puntos:
#
#     Meganium   9500 (finalizador) + 350 de desempate generico = 9850
#     Fezandipiti ex  9450 (`PROMO_LAST_STAND`) + 100           = 9550
#
# Trescientos puntos de un desempate que ordena "a cuantas cargas estas" y "cuantos
# premios cuestas" es TODO lo que separaba la jugada que gana la partida de un muro
# de 210 sin energias que no ataca nunca. `PROMO_KO_BONUS` dice en su propio
# comentario por que eso no vale: el cuerpo que noquea va arriba "so that it is a
# GUARANTEE and does not depend on the knocker scoring higher base than the tank".
# El finalizador a una carga de distancia no tenia esa garantia, y en nuestro
# propio match point es la misma jugada un turno antes.
#
# Y NO ES SOLO EL MARGEN: los tres descuentos que quedan por debajo pueden
# hundirlo del todo, porque los tres son argumentos sobre SOBREVIVIR A SU
# RESPUESTA y en nuestro match point esa respuesta no existe -- nuestro noqueo
# resuelve primero, en nuestro turno, y se lleva el ultimo premio:
#
#     -500   PROMO_TERA_COVER_PRICE   (si el finalizador es un Teal Mask Ogerpon
#                                     ex: 9500 -> 9000, POR DEBAJO del last stand)
#     -6000  el doomed de "match point entre los que noquean" (su guard exime al
#            que noquea HOY, `_promo_kos_op`, que es justo lo que este cuerpo no
#            hace todavia: 9500 -> 3500)
#     -1200  PROMO_KO_FRONT
#
# 15000 esta fijado por los dos lados. POR ENCIMA de 9500 + el maximo del
# desempate de supervivientes (450) y de cualquier otro peldaño de la banda, para
# que la eleccion deje de depender de adornos. POR DEBAJO de `PROMO_KO_BONUS`
# (+20000), que es este mismo cuerpo un turno mas temprano: el que noquea HOY
# tambien cierra la partida -- si `_promo_ko_wins_the_game` es cierto, cualquier
# noqueo del activo rival vale el monton entero -- y no necesita ni la carga ni el
# robo, asi que sigue teniendo la ultima palabra.
PROMO_CLOSER_SEAT = 15000


# Un interruptor con nombre en vez de una condicion en linea, para que un censo,
# un gate y el oraculo de reglas puedan medir esta frase como la UNICA diferencia
# entre dos brazos ([[la-noche-del-12-de-agosto-cuatro-detectores-y-lo-que-encontraron]]).
THE_SEAT_THAT_CLOSES_THE_GAME_IS_A_GUARANTEE = True


# EL MISMO ASIENTO VISTO DESDE EL OTRO LADO DEL TABLERO: SU match point.
#
# `PROMO_CLOSER_SEAT` (arriba) es NUESTRO match point -- el cuerpo que cierra la
# partida no se desempata. Este es su reflejo: cuando el cadaver del cuerpo que
# va a sentarse paga TODO lo que les queda de monton, el asiento es del que
# AGUANTA su respuesta, y esa eleccion tampoco puede depender de un adorno ni de
# una reserva.
#
# LO QUE TIENE QUE SUPERAR, y esto es lo que fija el numero por abajo. En el
# tablero que lo trajo (self-play vs `crustle_wall_1`, turno 23, su monton a UNO)
# el UNICO cuerpo que sobrevivia a sus 140 era un Meganium de 160 -- y estaba
# **vetado a SCORE_NEVER (-10000)** por "la linea del Meganium no sube a activo",
# la reserva que protege el Wild Growth desde la banca. El asiento se lo llevo un
# Dipplin de 80 con -4745, el menos malo de una mesa entera de negativos.
#
# Esa reserva, como los tres descuentos que `PROMO_CLOSER_SEAT` exime, es un
# argumento sobre LOS TURNOS QUE VIENEN: el doblador vale lo que valga el tablero
# de mañana. En su match point no hay mañana si el cuerpo que sentamos cae. Lo
# mismo vale para el veto de precio (`PROMO_MATCH_POINT_VETO`, -30000), que a su
# match point condena a TODOS los candidatos y deja la decision en manos del
# argmax de lo menos negativo.
#
# 12000 esta fijado por los dos lados:
#   POR ENCIMA de SCORE_NEVER (-10000), de PROMO_MATCH_POINT_VETO (-30000) y de
#   toda la banda ordinaria de promocion (base ~150-250, muro barato 8500+hp/10,
#   last stand 9450, finalizador nombrado 9500).
#   POR DEBAJO de PROMO_CLOSER_SEAT (15000) y de PROMO_KO_BONUS (20000): si
#   NUESTRO noqueo cierra la partida primero, su respuesta no llega a existir y
#   sobrevivir a ella no es un argumento. Se aplica como SUELO (`max`), asi que
#   esos dos conservan la ultima palabra sin necesidad de una exencion escrita.
PROMO_LOSING_SEAT_WALL = 12000

# Y el orden ENTRE supervivientes no se pierde: al suelo se le suma la puntuacion
# que el candidato traia, recortada a 0..999. Asi la reserva del motor sigue
# decidiendo cuando hay DOS que aguantan (que es cuando esa reserva si tiene algo
# que decir), y solo deja de decidir cuando el que protege es el unico que vive.
PROMO_LOSING_SEAT_RANK = 999


def _purchase_of_this_turn(card_id, hand, bought_serials):
    """How many copies of `card_id` in `hand` OUR OWN searches bought today.

    The other side of `_SUPP_PLAY_IDS` above, and the same doctrine: the
    decision that SPENDS a resource and the decision that PRICES the hand
    afterwards cannot contradict each other. Here the resource has already been
    spent -- an Ultra Ball, a Meowth ex ability, a Bug Catching Set went and got
    this card -- and the discard ladders, which know only what a card IS, are
    about to price it as if it had always been sitting there.

    A COUNT, not a list of serials, because copies of one card are
    interchangeable: what has to survive the next cost is as many copies as the
    search brought, not the physical ones it brought. `bought_serials` is
    `AGENT_STATE._bought_this_turn` (taken off the MOVE_CARD logs; a DRAW is not
    a purchase). It names no card and no deck.
    """
    if not bought_serials:
        return 0
    return sum(1 for c in hand
               if getattr(c, 'id', None) == card_id
               and getattr(c, 'serial', None) in bought_serials)


__all__ = [
    'SCORE_LD_SUPP_COMPROMETIDO',
    '_SUPP_PLAY_IDS',
    '_purchase_of_this_turn',
    'MAIN_ATTACKERS',
    'PROMO_CLOSER_SEAT',
    'THE_SEAT_THAT_CLOSES_THE_GAME_IS_A_GUARANTEE',
    'PROMO_DEFERRED_ATTACKER',
    'PROMO_DOOMED_PENALTY',
    'PROMO_KO_BONUS',
    'PROMO_KO_FRONT',
    'PROMO_KO_ROTATION',
    'PROMO_LAST_STAND',
    'PROMO_LOSING_SEAT_RANK',
    'PROMO_LOSING_SEAT_WALL',
    'PROMO_MATCH_POINT_VETO',
    'PROMO_PIVOT_PAYS_FOR_THE_SEAT',
    'PROMO_TERA_COVER_PRICE',
    'PROMOTE_TERA_PAYS_FOR_ITS_COVER',
    'PROMO_PRIZE_PENALTY',
    'OPENING_SAC_PROMOTE_TOP',
    'OPENING_SAC_PROMOTE_STEP',
]
