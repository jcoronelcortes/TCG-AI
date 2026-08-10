"""T3.1 --- the other half of the reference opponent's policy.

`utils/opponent_bot.py` is the code that decides what ships. Every matchup
number, every A/B verdict and every "this family goes worse" comes out of games
piloted by it, and its docstring records what one untested line of it costs:
until 2026-08-02 it did not use abilities, so the harness was structurally
blind to Marnie's Munkidori engine and **every axis measured against it came
out NEUTRAL by construction**.

`tests/test_opponent_bot.py` pins the ability engine --- the half that defect
was in. This file pins the half nobody has looked at, which is most of the
policy the docstring promises:

  * the ORDER of the main menu (ATTACH > EVOLVE > PLAY > ABILITY > RETREAT >
    ATTACK > END), which decides what the bot spends its turn on;
  * evolution by highest stage, active first on a tie;
  * the attack chosen by damage rather than by menu position;
  * where WEAKNESS actually bites --- and it is not where the docstring implies;
  * the *else* branch of every rule that already has its *then* branch pinned:
    the gust with no KO available, the counters that kill nothing, the
    promotion tie-break;
  * the yes/no policy and the unknown-select fallback.

That last one is not cosmetic. `utils/real_opponents.py` screens real lists for
pilotability precisely because "the first minCount options" is what the bot
does with a card it does not understand, and a deck it cannot pilot **returns a
high and FALSE winrate for us**. The fallback is load-bearing for the honesty
of the whole corpus, and it was unpinned.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "utils") not in sys.path:
    sys.path.insert(0, str(ROOT / "utils"))

from opponent_bot import MAX_ABILITIES_PER_TURN, OpponentBot
from cg.api import AreaType, OptionType, SelectContext

MUNKIDORI = 112       # 1 prize, Darkness
GRIMMSNARL = 648      # ex, 2 prizes, Stage 2, Darkness, WEAK TO GRASS
MORGREM = 647         # 1 prize, Stage 1
MEGANIUM = 710        # 1 prize, Stage 2
TAPU = 920            # Grass, its attack prints 220
OGERPON = 96          # ex, 2 prizes, Grass
HYDRAPPLE = 150       # ex, 2 prizes, Stage 2


def pk(cid, hp, max_hp, energies=0):
    return {"id": cid, "hp": hp, "maxHp": max_hp,
            "energies": [7] * energies, "energyCards": [], "tools": [],
            "preEvolution": [], "serial": cid * 10 + hp}


def obs(select, me_active, me_bench, op_active, op_bench,
        hand=(), yidx=1, turn=6):
    """The observation the bot reads. `yidx` is deliberately 1 and not 0.

    Half the bot's rules split on `playerIndex != yourIndex`, and a seat index
    of 0 makes "their body" and "a falsy index" indistinguishable. The project
    has already paid for that once --- see the harvest that read the wrong seat.
    """
    players = [None, None]
    players[yidx] = {"active": [me_active] if me_active else [],
                     "bench": list(me_bench), "prize": [None] * 4,
                     "hand": list(hand), "handCount": len(hand),
                     "deckCount": 30, "discard": []}
    players[1 - yidx] = {"active": [op_active] if op_active else [],
                         "bench": list(op_bench), "prize": [None] * 4,
                         "hand": [], "handCount": 0, "deckCount": 30,
                         "discard": []}
    return {"current": {"players": players, "yourIndex": yidx, "turn": turn,
                        "result": -1, "stadium": [], "retreated": False,
                        "energyAttached": False, "supporterPlayed": False},
            "select": select, "logs": []}


def sel(context, option, minCount=1, maxCount=1):
    return {"context": int(context), "option": option,
            "minCount": minCount, "maxCount": maxCount, "type": 1}


def opt(tipo, **extra):
    o = {"type": int(tipo)}
    o.update(extra)
    return o


@pytest.fixture
def bot():
    return OpponentBot()


# --- 1. the order of the main menu ------------------------------------------
#
# The order IS the policy. A bot that attacks before it attaches never builds a
# board, and the matchup it measures is its own impatience.

@pytest.mark.parametrize("earlier,later,por_que", [
    (OptionType.ATTACH, OptionType.EVOLVE, "la energia va antes que la evolucion"),
    (OptionType.EVOLVE, OptionType.PLAY, "evolucionar va antes que bajar banca"),
    (OptionType.PLAY, OptionType.ABILITY, "bajar banca va antes que la habilidad"),
    (OptionType.ABILITY, OptionType.ATTACK, "la habilidad va antes que atacar"),
    (OptionType.ATTACK, OptionType.END, "atacar va antes que terminar"),
])
def test_the_menu_is_taken_in_the_documented_order(bot, earlier, later, por_que):
    """The later option is put FIRST in the menu, so position cannot explain it."""
    o = obs(sel(SelectContext.MAIN,
                [opt(later, area=int(AreaType.BENCH), index=0),
                 opt(earlier, area=int(AreaType.ACTIVE), index=0)]),
            pk(TAPU, 100, 100, 1), [pk(MUNKIDORI, 100, 110, 1)],
            pk(MUNKIDORI, 100, 110), [])
    assert bot.agent(o) == [1], por_que


def test_it_does_not_retreat_while_it_has_an_attack(bot):
    """RETREAT is the exception in the ladder: it only fires with no attack.

    Without the guard a gusted body stays nailed in front forever; with the
    guard too loose the bot retreats away from every attack it could make and
    bleeds the energy the retreat discards.
    """
    o = obs(sel(SelectContext.MAIN,
                [opt(OptionType.RETREAT),
                 opt(OptionType.ATTACK, attackId=1326)]),
            pk(TAPU, 100, 100, 2), [pk(MUNKIDORI, 100, 110, 1)],
            pk(MUNKIDORI, 100, 110), [])
    assert bot.agent(o) == [1]


def test_with_no_attack_it_retreats_rather_than_ending(bot):
    o = obs(sel(SelectContext.MAIN,
                [opt(OptionType.END), opt(OptionType.RETREAT)]),
            pk(TAPU, 100, 100, 0), [pk(MUNKIDORI, 100, 110, 1)],
            pk(MUNKIDORI, 100, 110), [])
    assert bot.agent(o) == [1]


# --- 2. evolution: the highest stage, and the active on a tie ---------------

def test_it_evolves_the_highest_stage_first(bot):
    """Stage 2 before Stage 1: that is what gets the big attacker out in time."""
    mano = [{"id": MORGREM}, {"id": MEGANIUM}]
    o = obs(sel(SelectContext.MAIN,
                [opt(OptionType.EVOLVE, area=int(AreaType.HAND), index=0,
                     inPlayArea=int(AreaType.ACTIVE)),
                 opt(OptionType.EVOLVE, area=int(AreaType.HAND), index=1,
                     inPlayArea=int(AreaType.BENCH))]),
            pk(TAPU, 100, 100, 1), [pk(MUNKIDORI, 100, 110)],
            pk(MUNKIDORI, 100, 110), [], hand=mano)
    assert bot.agent(o) == [1], "la Fase 2 de banca pierde contra la Fase 1 de activo"


def test_on_the_same_stage_the_active_evolves_first(bot):
    mano = [{"id": MEGANIUM}, {"id": HYDRAPPLE}]
    o = obs(sel(SelectContext.MAIN,
                [opt(OptionType.EVOLVE, area=int(AreaType.HAND), index=0,
                     inPlayArea=int(AreaType.BENCH)),
                 opt(OptionType.EVOLVE, area=int(AreaType.HAND), index=1,
                     inPlayArea=int(AreaType.ACTIVE))]),
            pk(TAPU, 100, 100, 1), [pk(MUNKIDORI, 100, 110)],
            pk(MUNKIDORI, 100, 110), [], hand=mano)
    assert bot.agent(o) == [1]


# --- 3. the attack: by damage, not by menu position -------------------------

def test_it_attacks_with_the_hardest_hit_and_not_the_first_offered(bot):
    """Seel prints 10 and 30. The 10 is offered first."""
    o = obs(sel(SelectContext.MAIN,
                [opt(OptionType.ATTACK, attackId=1483),   # 10
                 opt(OptionType.ATTACK, attackId=1484)]),  # 30
            pk(1028, 90, 90, 2), [pk(MUNKIDORI, 100, 110)],
            pk(MUNKIDORI, 100, 110), [])
    assert bot.agent(o) == [1]


def test_weakness_does_not_change_which_attack_is_chosen(bot):
    """The honest reading of a rule that looks like it does more than it does.

    `_effective_damage` doubles on the DEFENDER's weakness against the
    ATTACKER's type --- and both attacks of one attacker share that type, so
    the doubling scales every candidate equally and can never reorder them.
    Whoever reads "attacks by effective damage" and expects weakness to pick a
    different attack is reading a promise the code does not make.

    Where the doubling really bites is the gust, and the next test is that one.
    """
    o = obs(sel(SelectContext.MAIN,
                [opt(OptionType.ATTACK, attackId=1484),   # 30, x2 = 60
                 opt(OptionType.ATTACK, attackId=1483)]),  # 10, x2 = 20
            pk(1028, 90, 90, 2), [pk(MUNKIDORI, 100, 110)],
            pk(MUNKIDORI, 100, 110), [])
    assert bot.agent(o) == [0]


def test_weakness_is_what_decides_the_gust_target(bot):
    """Tapu Bulu prints 220 and is Grass; Grimmsnarl ex has 320 HP and is weak to Grass.

    WITH the doubling 440 >= 320, so the ex dies and, being worth two prizes,
    it is the target. WITHOUT it 220 < 320, only the Munkidori dies, and the
    bot gusts a one-prize body instead. The two readings pick different decks
    to be afraid of, which is why this is pinned and not left to the docstring.
    """
    o = obs(sel(SelectContext.SWITCH,
                [opt(OptionType.CARD, playerIndex=0, area=int(AreaType.BENCH),
                     index=0),
                 opt(OptionType.CARD, playerIndex=0, area=int(AreaType.BENCH),
                     index=1)]),
            pk(TAPU, 100, 100, 2), [],
            pk(OGERPON, 210, 210), [pk(MUNKIDORI, 100, 110),
                                    pk(GRIMMSNARL, 320, 320)])
    assert bot.agent(o) == [1], "sin la debilidad x2 el gusteo cobra 1 premio en vez de 2"


def test_with_nothing_it_can_kill_the_gust_takes_the_weakest_body(bot):
    """The *else* branch: no KO available, so the least HP.

    The KO branch has a test; this one did not, and it is the branch that runs
    in most turns of most games.
    """
    o = obs(sel(SelectContext.SWITCH,
                [opt(OptionType.CARD, playerIndex=0, area=int(AreaType.BENCH),
                     index=0),
                 opt(OptionType.CARD, playerIndex=0, area=int(AreaType.BENCH),
                     index=1)]),
            pk(MUNKIDORI, 100, 110, 1), [],
            pk(OGERPON, 210, 210), [pk(HYDRAPPLE, 330, 330),
                                    pk(GRIMMSNARL, 300, 320)])
    assert bot.agent(o) == [1]


# --- 4. promotion: energy first, HP as the tie-break ------------------------

def test_on_equal_energy_the_healthiest_body_is_promoted(bot):
    """The energy half is pinned elsewhere; the tie-break was not."""
    o = obs(sel(SelectContext.SWITCH,
                [opt(OptionType.CARD, playerIndex=1, area=int(AreaType.BENCH),
                     index=0),
                 opt(OptionType.CARD, playerIndex=1, area=int(AreaType.BENCH),
                     index=1)]),
            None, [pk(MUNKIDORI, 60, 110, 2), pk(GRIMMSNARL, 300, 320, 2)],
            pk(OGERPON, 210, 210), [])
    assert bot.agent(o) == [1]


# --- 5. counters that kill nothing ------------------------------------------

def test_counters_that_kill_nothing_go_to_the_weakest_body(bot):
    """Two counters are 20 damage and nothing on their board dies to 20."""
    bot._contadores = 2
    o = obs(sel(SelectContext.DAMAGE_COUNTER,
                [opt(OptionType.CARD, playerIndex=0, area=int(AreaType.BENCH),
                     index=0),
                 opt(OptionType.CARD, playerIndex=0, area=int(AreaType.BENCH),
                     index=1)]),
            pk(MUNKIDORI, 100, 110, 1), [],
            pk(OGERPON, 210, 210), [pk(HYDRAPPLE, 330, 330),
                                    pk(GRIMMSNARL, 120, 320)])
    assert bot.agent(o) == [1]


# --- 6. yes / no ------------------------------------------------------------

def test_it_says_yes_by_default(bot):
    o = obs(sel(SelectContext.ACTIVATE,
                [opt(OptionType.NO), opt(OptionType.YES)]),
            pk(TAPU, 100, 100, 1), [], pk(MUNKIDORI, 100, 110), [])
    assert bot.agent(o) == [1]


@pytest.mark.parametrize("context", [SelectContext.MULLIGAN,
                                     SelectContext.MORE_DEVOLVE])
def test_it_says_no_to_a_mulligan_and_to_devolving_further(bot, context):
    """Two YESes that cost the game: taking a mulligan it did not have to take,
    and devolving its own board past the point of the effect."""
    o = obs(sel(context, [opt(OptionType.YES), opt(OptionType.NO)]),
            pk(TAPU, 100, 100, 1), [], pk(MUNKIDORI, 100, 110), [])
    assert bot.agent(o) == [1]


# --- 7. the fallback that keeps the corpus honest ---------------------------

def test_an_unknown_select_takes_the_first_minCount_options(bot):
    """This is the branch `utils/real_opponents.py` screens lists against.

    Whatever the bot does not understand ends here, and what it does here
    decides whether a real list is piloted or merely survived. An always-legal
    choice is the whole promise; anything cleverer risks being illegal, and
    anything shorter is a forfeit.
    """
    opciones = [opt(OptionType.CARD, index=i) for i in range(5)]
    o = obs(sel(SelectContext.DISCARD, opciones, minCount=2, maxCount=3),
            pk(TAPU, 100, 100, 1), [], pk(MUNKIDORI, 100, 110), [])
    assert bot.agent(o) == [0, 1]


def test_a_select_with_a_minimum_of_zero_still_answers_one_option(bot):
    """`minCount` 0 is not "answer nothing": an empty answer is not always legal."""
    opciones = [opt(OptionType.CARD, index=i) for i in range(3)]
    o = obs(sel(SelectContext.DISCARD, opciones, minCount=0, maxCount=3),
            pk(TAPU, 100, 100, 1), [], pk(MUNKIDORI, 100, 110), [])
    respuesta = bot.agent(o)
    assert respuesta == [0]


def test_every_answer_is_a_legal_index(bot):
    """The cheapest guard there is, over every context this file builds.

    An out-of-range index is an instant loss regardless of strategy, and the
    bot is the one piece of the harness whose crashes are read as OUR winrate.
    """
    casos = [
        sel(SelectContext.MAIN, [opt(OptionType.END)]),
        sel(SelectContext.ACTIVATE, [opt(OptionType.YES), opt(OptionType.NO)]),
        sel(SelectContext.DISCARD, [opt(OptionType.CARD, index=0)], minCount=1),
        sel(SelectContext.SWITCH,
            [opt(OptionType.CARD, playerIndex=1,
                 area=int(AreaType.BENCH), index=0)]),
    ]
    for caso in casos:
        respuesta = bot.agent(obs(caso, pk(TAPU, 100, 100, 1),
                                  [pk(MUNKIDORI, 100, 110, 1)],
                                  pk(MUNKIDORI, 100, 110), []))
        assert respuesta, f"respuesta vacia en contexto {caso['context']}"
        assert all(0 <= i < len(caso["option"]) for i in respuesta), \
            f"indice ilegal {respuesta} en contexto {caso['context']}"


# --- 8. the anti-loop cap ---------------------------------------------------

def test_the_per_turn_ability_cap_is_hard(bot):
    """One activation per Pokemon is not enough on its own.

    A board with more distinct ability bodies than the cap would otherwise let
    the turn run as long as the board is wide. The cap is what makes the bot
    terminate, and a harness whose opponent can hang measures nothing at all.
    """
    banca = [pk(MUNKIDORI, 100, 110, 1) for _ in range(MAX_ABILITIES_PER_TURN + 3)]
    opciones = [opt(OptionType.ABILITY, area=int(AreaType.BENCH), index=i)
                for i in range(len(banca))] + [opt(OptionType.END)]
    fin = len(opciones) - 1

    activadas = 0
    for _ in range(len(opciones) * 2):
        o = obs(sel(SelectContext.MAIN, opciones),
                pk(GRIMMSNARL, 320, 320, 2), banca,
                pk(OGERPON, 210, 210), [])
        respuesta = bot.agent(o)
        if respuesta == [fin]:
            break
        activadas += 1
    else:
        pytest.fail("el bot nunca dejo de activar habilidades: bucle")

    assert activadas == MAX_ABILITIES_PER_TURN
