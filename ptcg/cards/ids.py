"""Card data: IDs, groups and reference tables.

Extracted VERBATIM from main.py in wave 1 of the refactor
(docs/project-history.md). There is NO logic here: only constants that
depend solely on literals. Nothing in this module may import state or
touch the simulator -- utils/lint_architecture.py (R2) watches it.

main.py re-exports it with `from ptcg.cartas.ids import *`, so the `__all__`
below has to list ALL the names (including the ones starting with `_`, which
`import *` would otherwise skip).
"""


RETREAT_COST = {
    21:1, 22:3, 23:4, 24:2, 25:2, 26:1, 27:1, 28:1, 29:1, 30:3,
    31:1, 32:1, 33:1, 34:1, 35:1, 36:1, 37:4, 38:1, 39:1, 40:1,
    41:3, 42:1, 43:1, 44:3, 46:2, 47:1, 48:2, 49:3, 50:1, 51:2,
    52:1, 53:2, 54:3, 55:3, 56:1, 57:1, 58:3, 59:1, 60:1, 61:2,
    62:2, 63:3, 64:1, 66:3, 67:2, 68:1, 69:1, 70:2, 71:1, 72:2,
    73:1, 74:1, 75:1, 76:2, 77:2, 78:2, 79:2, 80:2, 81:1, 82:2,
    83:2, 84:2, 85:1, 86:2, 87:2, 88:1, 89:1, 90:2, 91:4, 92:1,
    93:2, 94:1, 95:1, 96:1, 97:1, 98:2, 99:1, 100:1, 101:1, 102:1,
    103:1, 104:1, 105:1, 106:1, 107:2, 108:1, 109:1, 110:2, 111:3, 112:1,
    113:2, 114:2, 115:3, 116:2, 117:1, 118:4, 119:1, 120:1, 121:1, 122:1,
    123:1, 124:2, 125:4, 126:1, 127:1, 128:1, 129:2, 130:1, 131:1, 132:2,
    133:3, 134:1, 135:4, 136:1, 137:1, 138:3, 139:1, 140:1, 141:1, 142:1,
    143:1, 144:2, 145:1, 146:2, 147:3, 148:1, 149:1, 150:3, 151:1, 152:1,
    154:2, 155:3, 156:3, 157:2, 158:3, 159:2, 160:1, 161:1, 162:2, 163:3,
    164:1, 165:2, 166:3, 167:3, 168:1, 169:2, 170:2, 171:3, 172:1, 173:1,
    174:1, 175:2, 176:2, 177:1, 178:1, 179:3, 180:1, 181:1, 182:2, 184:2,
    185:1, 186:2, 187:1, 188:1, 189:1, 190:2, 191:2, 192:2, 193:3, 194:1,
    195:2, 196:3, 197:1, 198:2, 199:1, 200:3, 201:3, 202:1, 203:3, 204:2,
    205:2, 206:1, 207:2, 208:2, 209:1, 210:1, 211:1, 212:1, 213:1, 214:1,
    215:1, 216:1, 217:1, 218:2, 219:2, 220:1, 221:1, 222:1, 223:4, 224:2,
    225:3, 226:2, 227:1, 228:2, 229:3, 230:1, 231:1, 232:4, 233:2, 234:2,
    236:2, 237:1, 238:1, 239:2, 240:1, 241:2, 242:1, 243:1, 245:1, 246:1,
    247:1, 248:2, 249:1, 250:2, 251:4, 252:1, 253:3, 254:1, 255:2, 256:2,
    257:2, 258:3, 259:3, 260:1, 261:1, 262:2, 263:3, 264:4, 265:1, 267:1,
    268:2, 269:2, 270:1, 271:1, 272:1, 273:1, 274:1, 275:2, 276:3, 277:1,
    280:1, 281:2, 282:3, 283:4, 284:1, 285:1, 286:1, 287:2, 288:2, 289:3,
    290:3, 291:1, 292:1, 293:2, 294:1, 295:3, 296:3, 297:1, 298:2, 299:2,
    300:2, 301:2, 302:2, 303:2, 304:4, 305:1, 306:3, 307:1, 308:1, 309:1,
    310:2, 311:1, 312:2, 313:1, 314:1, 315:2, 316:2, 317:1, 318:2, 319:1,
    320:2, 321:1, 322:2, 323:1, 324:1, 325:2, 326:2, 327:2, 328:1, 330:1,
    331:1, 332:3, 333:1, 335:1, 336:2, 337:2, 338:2, 339:1, 340:1, 341:1,
    342:1, 343:1, 344:2, 345:3, 346:1, 347:3, 348:3, 349:1, 350:1, 351:1,
    352:1, 353:1, 354:2, 355:2, 356:3, 357:2, 358:1, 359:1, 360:1, 361:1,
    362:1, 363:4, 364:1, 365:1, 366:2, 367:1, 368:1, 369:4, 370:1, 371:2,
    372:4, 374:1, 375:1, 376:1, 377:1, 378:1, 379:1, 380:1, 382:3, 383:3,
    384:1, 385:2, 386:1, 387:1, 388:2, 389:3, 390:2, 391:1, 392:2, 393:2,
    394:1, 395:2, 396:1, 397:1, 398:1, 399:1, 400:1, 401:2, 402:1, 403:1,
    404:2, 405:2, 406:3, 407:2, 408:1, 409:2, 410:1, 411:2, 412:2, 413:2,
    414:1, 415:2, 416:1, 417:1, 418:3, 419:4, 420:2, 421:1, 422:1, 423:3,
    424:4, 425:1, 426:1, 427:2, 428:2, 429:2, 430:2, 431:3, 432:2, 435:2,
    436:2, 437:1, 438:2, 439:2, 440:1, 441:2, 442:3, 443:3, 444:3, 445:1,
    446:1, 447:3, 448:1, 449:2, 450:1, 451:2, 452:3, 453:1, 454:2, 455:3,
    456:1, 457:1, 458:1, 459:3, 460:4, 461:1, 462:2, 463:1, 464:1, 465:2,
    466:1, 467:2, 468:1, 469:1, 470:1, 471:2, 472:2, 473:1, 474:1, 475:1,
    476:1, 478:1, 479:1, 480:1, 481:2, 482:1, 483:1, 484:1, 485:1, 486:1,
    487:1, 488:1, 489:2, 490:1, 491:2, 492:2, 493:1, 494:1, 495:2, 496:1,
    497:1, 498:1, 499:1, 500:1, 501:2, 502:3, 503:3, 504:3, 505:1, 506:2,
    507:3, 508:1, 509:2, 512:2, 513:3, 514:1, 515:2, 516:1, 517:2, 518:1,
    519:1, 520:1, 521:1, 522:1, 523:3, 524:4, 525:1, 526:1, 527:3, 528:2,
    529:3, 530:3, 531:2, 532:2, 533:3, 534:2, 535:3, 536:3, 537:3, 538:2,
    539:2, 540:3, 541:1, 542:1, 543:3, 544:1, 545:2, 546:2, 547:2, 548:2,
    549:2, 550:3, 551:1, 554:1, 555:1, 556:1, 557:1, 558:2, 559:1, 560:1,
    562:1, 563:2, 564:3, 565:1, 566:1, 567:1, 568:3, 569:4, 570:1, 571:1,
    572:2, 573:2, 574:1, 575:1, 576:2, 577:1, 578:1, 579:1, 580:1, 581:2,
    582:2, 583:2, 584:1, 585:1, 586:1, 587:1, 588:2, 589:1, 590:1, 591:1,
    592:2, 593:2, 594:1, 595:1, 596:2, 597:3, 598:3, 599:2, 600:3, 601:3,
    602:1, 603:1, 604:1, 605:1, 606:1, 607:3, 608:1, 609:1, 610:1, 611:2,
    612:2, 613:3, 614:1, 615:1, 616:2, 617:3, 618:3, 619:2, 620:3, 621:1,
    622:2, 623:3, 624:1, 625:2, 626:1, 627:1, 628:1, 629:1, 630:3, 631:2,
    632:1, 633:1, 634:1, 635:1, 636:2, 637:2, 638:1, 639:1, 640:2, 641:3,
    642:1, 643:1, 644:1, 645:2, 646:1, 647:1, 648:2, 650:2, 651:3, 652:4,
    653:1, 654:2, 655:1, 656:1, 657:2, 658:2, 659:1, 660:1, 661:2, 662:4,
    663:2, 664:1, 665:1, 667:2, 668:2, 669:1, 670:1, 671:4, 673:2, 674:3,
    675:1, 676:1, 677:2, 678:2, 679:1, 680:1, 681:1, 682:2, 683:2, 684:3,
    685:4, 686:3, 687:2, 688:1, 690:1, 691:1, 692:1, 693:1, 694:4, 695:2,
    696:2, 697:1, 698:2, 699:2, 700:2, 701:1, 702:1, 703:2, 704:1, 705:1,
    706:2, 707:4, 708:1, 709:2, 710:2, 711:1, 712:1, 714:2, 715:2, 716:2,
    717:2, 718:3, 719:1, 720:1, 721:3, 722:3, 723:4, 724:2, 725:2, 726:1,
    727:1, 728:1, 729:1, 730:2, 731:1, 732:1, 733:2, 734:3, 735:1, 736:1,
    738:1, 739:1, 740:1, 741:1, 742:1, 743:1, 744:1, 745:1, 746:1, 747:2,
    749:1, 750:2, 751:1, 752:3, 753:3, 754:1, 755:1, 756:3, 757:1, 758:1,
    759:1, 760:2, 761:3, 762:1, 763:2, 764:1, 765:1, 766:1, 767:1, 768:1,
    769:1, 770:1, 771:1, 772:2, 773:1, 774:1, 775:1, 776:1, 777:2, 778:1,
    779:1, 780:2, 781:2, 782:1, 783:1, 784:2, 785:2, 786:1, 787:1, 788:2,
    789:2, 790:2, 791:1, 792:2, 793:3, 794:2, 795:1, 796:2, 797:2, 798:2,
    799:2, 800:2, 801:3, 802:4, 803:2, 804:1, 805:2, 806:1, 807:1, 808:1,
    809:1, 810:1, 811:1, 812:1, 813:1, 814:1, 815:1, 816:2, 817:1, 818:2,
    819:2, 820:1, 821:1, 822:1, 823:1, 824:1, 825:1, 826:1, 827:1, 829:1,
    830:2, 831:2, 832:3, 833:1, 834:2, 835:2, 836:2, 837:3, 838:1, 839:2,
    840:2, 841:1, 842:2, 843:1, 844:1, 845:1, 846:1, 847:1, 848:1, 849:1,
    850:1, 851:3, 852:1, 853:3, 854:1, 855:3, 856:3, 857:3, 858:1, 859:1,
    860:1, 861:1, 862:1, 863:1, 864:2, 865:1, 866:2, 867:2, 868:2, 869:2,
    870:1, 871:1, 872:1, 873:1, 874:3, 875:1, 876:1, 877:1, 878:2, 879:2,
    880:1, 881:1, 882:1, 883:1, 884:1, 885:2, 886:1, 887:3, 888:3, 889:4,
    890:3, 891:1, 892:1, 893:2, 894:2, 895:2, 896:2, 897:3, 898:1, 899:1,
    900:1, 901:3, 902:2, 903:2, 904:2, 905:1, 906:2, 907:1, 909:1, 910:1,
    911:2, 912:1, 913:2, 914:3, 915:2, 916:1, 917:1, 918:2, 919:2, 920:3,
    921:3, 922:1, 923:1, 924:1, 925:1, 926:1, 927:1, 928:1, 929:2, 930:2,
    931:3, 932:4, 933:2, 934:2, 935:2, 936:3, 937:1, 938:2, 939:3, 940:2,
    941:2, 942:3, 943:3, 944:3, 945:1, 946:1, 947:1, 948:1, 949:1, 950:1,
    951:1, 952:1, 953:2, 954:1, 955:1, 956:1, 957:1, 958:2, 959:1, 960:1,
    961:1, 962:2, 963:1, 964:1, 965:1, 966:2, 967:2, 968:2, 969:1, 970:1,
    971:3, 972:1, 973:3, 974:1, 975:2, 976:1, 977:3, 978:1, 979:2, 980:3,
    981:3, 982:3, 983:1, 984:1, 985:2, 986:3, 987:1, 988:3, 989:1, 990:1,
    991:4, 992:2, 993:4, 994:2, 995:2, 997:3, 998:2, 999:2, 1000:1, 1001:1,
    1002:1, 1003:1, 1004:1, 1005:1, 1006:1, 1007:1, 1008:1, 1009:2, 1010:2, 1011:1,
    1012:1, 1014:1, 1015:1, 1016:2, 1017:1, 1018:3, 1019:1, 1020:2, 1021:2, 1022:2,
    1023:1, 1024:1, 1025:1, 1026:1, 1027:2, 1028:2, 1029:2, 1030:1, 1031:2, 1032:3,
    1033:3, 1034:3, 1035:1, 1036:1, 1038:1, 1039:1, 1040:1, 1041:2, 1042:1, 1043:1,
    1044:1, 1045:1, 1046:3, 1047:3, 1048:4, 1049:4, 1050:1, 1051:2, 1052:2, 1053:3,
    1054:3, 1056:2, 1057:1, 1058:1, 1059:1, 1060:2, 1061:3, 1062:1, 1063:1, 1065:2,
    1066:2, 1067:3, 1068:1, 1069:1, 1070:1, 1071:1, 1072:4, 1073:1, 1074:4, 1075:1,
    1076:1,
}

Teal_Mask_Ogerpon_ex = 96
Chikorita = 917
Bayleef = 709
Meganium = 710
Applin = 92
Dipplin = 93
Hydrapple_ex = 150
Meowth_ex = 1071
Fezandipiti_ex = 140
Tapu_Bulu = 920

Pinsir = 25

Lillie_Determination = 1227
Boss_Orders = 1182
Lanas_Aid = 1184
Xerosic_Machinations = 1197

Dawn = 1231
Bug_Catching_Set = 1094
Ultra_Ball = 1121
Night_Stretcher = 1097
Unfair_Stamp = 1080
Poke_Pad = 1152
Forest_of_Vitality = 1261
Neutralization_Zone = 1247
Team_Rockets_Watchtower = 1256
# Festival Grounds (1245): the opponent's "Festival Lead" stadium. Just like
# Grand Tree it is SHARED -- what matters is that it is ON THE FIELD, not who
# played it -- and it switches on the Festival Lead ability of ANY Dipplin in
# play (theirs and ours). See `FESTIVAL_LEAD_IDS` and `_festival_grounds_in_play`.
Festival_Grounds = 1245
# Grand Tree (Stadium ACE SPEC): "Once during EACH player's turn, that player
# may search their deck for 1 Stage 1 Pokemon that evolves from one of their
# Basic Pokemon and put it onto that Pokemon to evolve it. If they evolved a
# Pokemon in this way, they may also search for 1 Stage 2 Pokemon that evolves
# from that Pokemon."
#
# It is a SHARED stadium: if the OPPONENT plays it, we can use its ability on
# our turn too (and we search OUR deck). That is why the logic below does not
# require the card to be in deck.csv: it is enough for it to be in play
# (`stadium_id == Grand_Tree`).
#
# Restrictions imposed by the card itself (a reminder of the general rule):
#   * a Basic cannot be evolved on OUR FIRST TURN, and
#   * a Basic PUT INTO PLAY THIS TURN cannot be evolved
#     (`Pokemon.appearThisTurn`).
# There can only be ONE stadium on the field, so Grand Tree and Forest of
# Vitality never coexist: Forest does NOT lift the "came down this turn" veto
# here.
Grand_Tree = 1249
# Maximum Belt (Ace Spec): the opponent's tool that adds +50 damage against our
# active ex Pokemon (before weakness). Modelled in _op_best_damage_vs and
# _op_active_attack_damage_to.
Maximum_Belt = 1158
# Brave Bangle (1175): +30 damage against our ACTIVE ex Pokemon (before
# weakness) ONLY if the holder does NOT have a Rule Box. The Dipplin of the
# Festival Lead deck does not have one, so its Do the Wave reaches our ex with
# +30 (log 88971843 step 116: 20x5 bench = 100, +30 Bangle = 130, which finished
# off the Teal Mask Ogerpon ex at 70 HP). Without modelling it, the defensive
# pivots believed the ex wall survived a hit that in reality arrives boosted --
# the same hole Maximum Belt plugged in the July 2026 audit.
Brave_Bangle = 1175
Basic_Grass_Energy = 1

Budew = 235

Crustle_Grass = 345
Dwebble_Grass = 344
Crustle_Fighting = 533
Dwebble_Fighting = 532
Sylveon = 330

# Comfey mill/control deck (user): Comfey (the only attacker, "Flower Shower"
# makes us draw 3 -> it decks us out), Bramblin (does not attack) evolves into
# Brambleghast, which CONFUSES our active with "Prison Panic". Detected by any
# of the 3.
Comfey = 164
Bramblin = 817
Brambleghast = 818

Munkidori = 112
Froslass = 104
Snorunt = 103
Dragapult_ex = 121
Dreepy = 119
Drakloak = 120
Iron_Thorns_ex = 37
Charizard_ex = 790
Grimmsnarl_ex = 648
Marnies_Impidimp = 646
Marnies_Morgrem = 647
Latias_ex = 184
Cornerstone_Mask_Ogerpon_ex = 117
# NON-ex Cornerstone Mask Ogerpon (no ability, attackable): it does not grant
# immunity, but it GIVES AWAY the Cornerstone archetype (phase 8: autopsy vs
# the cornerstone_cubchoo deck — with only the non-ex/Cubchoo in sight the flag
# did not fire and the anti-Cubchoo whitelist vetoed Tapu Bulu 38 times).
Cornerstone_Mask_Ogerpon = 386
Mega_Kangaskhan_ex = 756

Hops_Phantump = 878
Hops_Trevenant = 879
Splashing_Dodge_Atk = 1266
COIN_FLIP_LOG_TYPE = 22

Mega_Greninja_ex = 40
Mega_Starmie_ex = 1031
Slowking = 163
Slowpoke = 162

Beedrill = -991
Weedle = -992
Kakuna = -993
Zoroark_N = 293
Zorua_N = 292
Alakazam_ex = 743
Abra = 741
Kadabra = 742
# Powerful Hand (Alakazam 743's only attack): printed damage 0 in attack_table
# but real damage = 20 x card in the opponent's hand. Modelled in
# _op_active_attack_damage_to when the caller passes op_hand_count.
POWERFUL_HAND_ATTACK_ID = 1072

# --- VARIABLE opposing damage: the family of attacks with printed damage 0 ----
# Do the Wave (115, Dipplin 93's only attack): printed damage 0 in attack_table
# ("20x") but real damage = 20 x THEIR BENCH. It is the SAME blindness as
# Powerful Hand and it cost the game of log 88971843 (step 117): the agent
# projected 0 against the four bench candidates, so ALL the survival machinery
# (`_promo_survives`, the prudence of `_pb_key`, `_ev_survivor_asis`,
# `_ko_prefer_basic_general`) switched off silently and the promotion was
# decided by the only thing still alive -- "who can attack this turn" -- putting
# up an 80 HP Dipplin to eat 100 with the opponent at 1 prize.
#
# Unlike Powerful Hand, the scale does NOT travel in the signature of
# `_op_active_attack_damage_to` (it needs the opposing bench, not the hand), so
# it is published in the per-turn flag `_op_bench_count`: if it depended on
# every caller passing an extra parameter we would be back to the same silent 0
# in most places.
DO_THE_WAVE_ATTACK_ID = 115

# Festival Lead (Dipplin 93's ability): with Festival Grounds ON THE FIELD, this
# Pokemon may use one of its attacks TWICE; if the first one knocks out our
# active, it attacks AGAIN as soon as we choose the replacement. That is: under
# that stadium, the body we promote after a KO eats a whole hit BEFORE we get to
# play -- exactly the opposite of the premise the promotion branch assumes ("the
# promotion happens on the OPPONENT's turn, where nobody attacks any more").
FESTIVAL_LEAD_IDS = {Dipplin}



ALAKAZAM_LINE_IDS = (Abra, Kadabra, Alakazam_ex)
# The bodies of the line that really ATTACK. Powerful Hand costs a SINGLE
# energy, so an Alakazam with energy on it (or the Kadabra that evolves into it
# that same turn) is an immediate threat; a bare Abra is not.
ALAKAZAM_ATTACKER_IDS = (Kadabra, Alakazam_ex)

# Mega Lopunny ex line: Buneary (basic, id 848) -> Mega Lopunny ex (Stage 1,
# id 849, a 2-prize ex). The attacking basic of this deck is Buneary.
Buneary = 848
Mega_Lopunny_ex = 849
# Cynthia's Garchomp ex line: Gible (basic 379) -> Gabite (Stage 1, 380) ->
# Cynthia's Garchomp ex (Stage 2, 381, a 2-prize ex). The deck comes with
# 1-prize walls (Cynthia's Spiritomb 387, Roselia 341).
Cynthias_Gible = 379
Cynthias_Gabite = 380
Cynthias_Garchomp_ex = 381
Gardevoir_ex = 747
Ralts = 745
Kirlia = 746
Raging_Bolt_ex = 63
Lugia_VSTAR = 337
# Mega Abomasnow ex line: Snover (basic, id 722) -> Mega Abomasnow ex (a
# 3-prize Mega ex, id 723). Its attacker one-shots any of our ex, just like
# Raging Bolt/Bellowing Thunder: same PRIZE MISMATCH plan (putting a 1-prize
# body in front when we cannot knock out the active).
Snover = 722
Mega_Abomasnow_ex = 723
Dusknoir = 133
Duskull = 131
Dusclops = 132
Typhlosion = 354
Cyndaquil = 352
Quilava = 353
Drednaw = 158
Chewtle = 157
Cubchoo = 506
Beartic = 507
Eevee_TWM = 43
Eevee_SFA = 145
Eevee_PRE_ex = 249
Eevee_SSP = 317
EEVEE_IDS = {43, 145, 249, 317}

OUR_EX_IDS = {Teal_Mask_Ogerpon_ex, Hydrapple_ex, Meowth_ex, Fezandipiti_ex}

# Item cards ("artefacts") of our deck. Used to postpone putting Tapu Bulu down
# until the items that are worth playing have been played.
DECK_ITEM_IDS = frozenset({Bug_Catching_Set, Ultra_Ball, Night_Stretcher,
                           Poke_Pad, Unfair_Stamp})

# Both variants of Crustle share the anti-ex ability; the Fighting one (533)
# switched on `op_is_crustle_deck` but was missing here, so the specific damage
# computation believed our ex DID damage it (July 2026 audit).
EX_IMMUNE_IDS = {Crustle_Grass, Crustle_Fighting, Sylveon}

# The Crustle LINE (pre-evolution included). `op_is_crustle_deck` is the
# "ex-immune wall" flag and it also switches on with Sylveon/Eevee, which share
# the immunity but NOT the rest of the deck. Rules that depend on how the
# Crustle deck is BUILT -- e.g. that it barely plays a stadium, see
# `t1_second_crustle_stadium_before_lillie` -- have to look at this list,
# not at the flag.
CRUSTLE_LINE_IDS = {Crustle_Grass, Crustle_Fighting,
                    Dwebble_Grass, Dwebble_Fighting}



ABILITY_IMMUNE_IDS = {Cornerstone_Mask_Ogerpon_ex}

OUR_ABILITY_IDS = {Teal_Mask_Ogerpon_ex, Hydrapple_ex, Meganium, Fezandipiti_ex, Meowth_ex, Dipplin}

# Bodies that are NEVER worth bringing up with Boss's even if they cannot
# attack: the WALLS that cancel our attackers (Crustle/Sylveon vs ex,
# Cornerstone vs abilities) and the LOCKER Iron Thorns ex, whose Initialization
# switches off Teal Dance / Ripening / Last-Ditch / Flip the Script from the
# ACTIVE spot. All five have attacks costing 3, so bare they pass as "harmless"
# (`_op_body_is_harmless`) and would take the preference of a gust without a KO.
GUST_TRAP_IDS = EX_IMMUNE_IDS | ABILITY_IMMUNE_IDS | {Iron_Thorns_ex}

# --- Surviving a KO and new immunities (jul 2026 plan, P0.1/P1.6) ------------
# Bodies that SURVIVE a lethal hit at FULL HP by staying at 10 HP: Crustle 533
# ("Sturdy", already modelled) and Pikachu ex 210 ("Resolute Heart", missing).
# The effective damage is capped at hp-10 in _our_effective_damage, so every
# `can_ko` that goes through there inherits the cap automatically.
Pikachu_ex_Resolute = 210
FULL_HP_SURVIVE_IDS = {Crustle_Fighting, Pikachu_ex_Resolute}

# Mega Hawlucha ex ("Tenacious Body"): against a lethal hit it flips a coin and
# on heads survives at 10 HP -> the KO is NEVER guaranteed. Survival Brace (tool
# 1155): at full HP it survives the KO at 10 HP. The FINISHER evaluators
# (wins_now / SCORE_WIN_GAME / _active_attack_wins_now) consult
# _ko_not_guaranteed so as not to declare a victory that depends on a coin flip
# or a tool; normal damage is NOT altered (attacking them is still worth it).
Mega_Hawlucha_ex = 886
Survival_Brace = 1155

# Farigiraf ex ("Armor Tail"): immune to attack damage from BASIC ex. Of our
# deck it cancels Ogerpon ex / Meowth ex / Fezandipiti ex; Hydrapple ex is a
# Stage 2 and DOES damage it, as do the non-ex (Tapu Bulu, Meganium, Bayleef...).
Farigiraf_ex = 83
OUR_BASIC_EX_IDS = {Teal_Mask_Ogerpon_ex, Meowth_ex, Fezandipiti_ex}

# --- Matchup plans: WHICH Pokemon each one allows putting down ---------------
# Two matchups restrict the bench to a closed list (the rest of our Pokemon are
# vetoed in the PLAY branch): vs Cubchoo the list below, vs Comfey ONLY Teal
# Mask Ogerpon ex (max 2). They live as a constant -- and not as a local tuple
# of the PLAY branch -- because the RESCUE NETS of the finalisation block have
# to consult the same plan: digging out with Ultra Ball a body that the plan
# itself will veto when putting it down does not save a dead turn, it only burns
# two cards from hand (see `_matchup_allows_playing`).
CUBCHOO_ALLOWED_PLAY_IDS = (Applin, Dipplin, Hydrapple_ex,
                            Chikorita, Bayleef, Meganium,
                            Teal_Mask_Ogerpon_ex, Meowth_ex)

# --- The opponent's item lock (jul 2026 plan, P1.5) --------------------------
# Besides Budew's Itchy Pollen (already modelled from the attack log), these
# block our items: Jellicent ex 598 ("Oceanic Curse") and Tyranitar 290
# ("Daunting Gaze") WHILE they are the opposing active, and Galvantula ex 161
# with Fulgurite (attackId 210) during our next turn. With 10+ items in the deck
# (UBx4/BCSx4/NSx2/Stamp/PokePad) the whole engine depends on detecting them.
Jellicent_ex = 598
Tyranitar_Daunting = 290
Galvantula_ex = 161
FULGURITE_ATTACK_ID = 210
OP_ITEM_LOCK_ACTIVE_IDS = {Jellicent_ex, Tyranitar_Daunting}

# --- Ability lock by Iron Thorns ex (jul 2026 plan, P1.4) --------------------
# Iron Thorns ex 37 ("Initialization") as the opposing ACTIVE: the Pokemon with
# a Rule Box on BOTH sides lose their abilities -> Teal Dance, Ripening Charge,
# Last-Ditch Catch and Flip the Script switch off at once (our whole engine).
# It does NOT affect the ones without a Rule Box (Meganium's Wild Growth and
# Dipplin stay alive: Dipplin has no Rule Box; Festival Lead requires a stadium
# we do not play).
OUR_RULEBOX_ABILITY_IDS = {Teal_Mask_Ogerpon_ex, Hydrapple_ex, Fezandipiti_ex,
                           Meowth_ex}

# --- The opponent's prize denial (jul 2026 plan, P0.2) -----------------------
# Munkidori ex 139 ("Oh No You Don't"): if the opponent has Pecharunt ex 141 in
# play, its KO yields 1 prize LESS. Mega Gengar ex 772 ("Shadowy Concealment"):
# while it is in play, the KO of an opposing {D} Pokemon by an ex of OURS yields
# 1 prize less. Without this, `wins_now`/SCORE_WIN_GAME can declare a victory
# that is 1 prize short. They are consulted via `prize_count_op` (only for
# OPPONENT Pokemon: our Fezandipiti ex is also {D} and must NOT be affected).
Munkidori_ex = 139
Pecharunt_ex = 141
Mega_Gengar_ex = 772

# --- Opposing bench burst (jul 2026 plan, P0.3) ------------------------------
# Dusknoir 133 ("Cursed Blast": 13 counters = 130) and Dusclops 132 (5 = 50) add
# EXTRA damage from the bench ON TOP OF the opposing active's attack (the
# ability is used and THEN they attack). `active_ko_likely` has to add it or the
# defensive pivots believe the wall survives a hit that in reality arrives with
# +130.
OP_BENCH_BURST = {Dusknoir: 130, Dusclops: 50}

# AUTOMATIC damage the opponent's attack spreads to ONE Pokemon on OUR bench
# (user, registro_006/008 vs Marnie's Grimmsnarl ex, LOST). Shadow Bullet does
# 180 to the active AND 30 to a benched body EVERY turn, so our low-HP bodies
# (Dipplin 80, Applin 40, Chikorita 70) die by themselves and hand over prizes
# without the opponent spending anything. The agent was blind to that drip:
# `op_bench_snipe_threat` was a boolean only read in the setup. Here it is
# quantified so we can project WHICH body dies next turn and decide whether to
# heal it (Ripening Charge heals 30) or evolve it (evolving resets the HP).
# The values come from each attack's text; the default of 30 is the
# conservative case.
OP_BENCH_SNIPE_DAMAGE = {
    Grimmsnarl_ex: 30,       # Shadow Bullet: 180 + 30 to 1 benched
    Dragapult_ex: 60,        # Phantom Dive: 6 spreadable counters (60 to one)
    Mega_Starmie_ex: 50,     # Jetting Blow: 120 + 50 to 1 benched
    Mega_Greninja_ex: 120,   # Mirage Barrage: 120 to 2 Pokemon
}
OP_BENCH_SNIPE_DEFAULT = 30

# --- THE GIFT WINDOW (user, records/marnie games 1-3, LOST) ----------------
# The three losses were by ONE prize and the opponent took 7 out of 18 prizes
# WITHOUT ATTACKING. The snipe of OP_BENCH_SNIPE_DAMAGE (30) is only a third of
# the threat: the two sources that kill bodies without spending an attack were
# missing.
#
# 1) Freezing Shroud (Froslass): 1 counter on EVERY Pokemon with an ability on
#    BOTH sides at each Pokemon Checkup. There are TWO checkups per round (the
#    end of our turn and the end of theirs), so each Froslass spreads 20 per
#    round to each of our OUR_ABILITY_IDS bodies. With two Froslass, 40.
# 2) Adrena-Brain (Munkidori): it moves up to 3 counters from ONE of THEIR
#    Pokemon to ANY of ours -- active or bench, once per turn per Munkidori with
#    Darkness energy. It is AIMABLE damage: if we heal body A the opponent aims
#    at B.
#
# Careful with two readings that break the intuition:
#   - The Tera of a benched Teal Mask Ogerpon ex prevents damage FROM ATTACKS:
#     it cuts the 30 snipe but NOT Froslass's counters or the ones Munkidori
#     moves (verified: in game 2 the benched Ogerpon died with 60 counters moved
#     by two Munkidori).
#   - Munkidori's ammunition SELF-RENEWS: their own Froslass loads 10 per
#     checkup onto each Munkidori and onto the Grimmsnarl ex (they all have an
#     ability), so the counters on their board today are not the ceiling.
FREEZING_SHROUD_COUNTER = 10   # damage per Freezing Shroud counter
CHECKUPS_PER_ROUND = 2         # Pokemon checkups between two of our turns
ADRENA_BRAIN_MOVE = 30         # counters moved by ONE charged Munkidori

# Ripening Charge (Hydrapple ex) healing on the Pokemon that receives the Grass.
RIPENING_HEAL = 30
# Score of the Ripening Charge TARGET when the ability is used to heal.
RIPEN_HEAL_TARGET_SCORE = 39500
# Score of the Ripening Charge ABILITY played for its healing: above the
# development Teal Dance (31050) and below the one that enables a KO (31500) or
# the retreat pivots (31600). >= 29000 so it rises to the ENERGY tier and
# competes there.
RIPEN_HEAL_ABILITY_SCORE = 31250
# The same ability when the body leaving the window is an ex (TWO prizes)
# -- e.g. the active Teal Mask Ogerpon ex at 20 HP of game 3, which died to 30
# moved counters. There the healing beats Teal Dance (31500): drawing one card
# is not worth two prizes. It stays below the lethal bands (41000+) and below
# the retreat pivots (31600).
RIPEN_HEAL_EX_ABILITY_SCORE = 31550

# Ceiling of the charge on a DOOMED body (phase C of the Marnie plan): the
# opponent can cash it in before our next turn and it does not attack today, so
# the Grass goes to the discard with it. It is a CEILING, not a veto: it sits
# below the whole development band (~8000) and above the last resort of
# Applin/Dipplin with Hydrapple in play (10), which is energy that really yields
# nothing. If there is nothing better left, the energy still lands here.
SCORE_CHARGE_DOOMED = 20
# Floor of `energy_score`'s LETHAL band: from 41000 upwards the energy takes or
# denies a prize TODAY (finishers, retreat pivots, winning gust) and no
# development consideration touches it. Already documented in the comments of
# RIPEN_HEAL_* and of the `_carga_activo_*` family; here it gets a name so the
# phase C ceiling knows where to stop.
SCORE_CHARGE_LETHAL_FLOOR = 41000

# Score of FLIP THE SCRIPT (Fezandipiti ex: drawing 3 after a KO of ours). It
# goes ABOVE the whole family of non-lethal CHARGING abilities -- Teal Dance
# (29000-31500) and Ripening Charge (30500-31600) -- because it is FREE, it is
# ONCE PER TURN and its condition dies with the turn, whereas an attachment that
# does not finish can be made afterwards without losing anything. Besides,
# drawing FIRST decides the attachments better: the 3 new cards may be Grass. It
# is below the LETHAL bands (41000+) and the winning finisher. >= 29000 so it
# rises to the ENERGY tier (if it stayed at tier 0, any charge would step over
# it by ORDER).
FEZ_DRAW_ABILITY_SCORE = 31700

# --- ATTACKING WITH THE ACTIVE COMES FIRST ----------------------------------
# Bands of the `_carga_activo_*` family (see the flags of the same name in
# agent()): charging the ACTIVE up to its ATTACK COST using ALL the charging
# routes still alive this turn (the manual attachment + the charging abilities).
#
# `_charge_active_finishes` (the resulting attack KNOCKS OUT the opposing active):
# 41900. Above ALL the "indirect" lethal charges -- promoting a benched attacker
# (41000), the charging focus of an Ogerpon (41700) -- because attacking with
# the ACTIVE pays no retreat cost and does not depend on the retreat being
# legal. Below the WINNING finisher via Boss's (42000) and the 1-prize attacker
# vs Alakazam (43000), which settle the game / the prize trade.
SCORE_CHARGE_ACTIVE_FINISHER = 41900
# `_charge_active_enables_attack` (the attack does not finish but does CHIP
# damage and without that charge the turn would be STERILE): 31300. Its value is
# NOT in winning duels, but in SKIPPING the energy_score branches that degraded
# the charge to the active (the `score - 100` of `active_ko_likely`, the veto of
# `_active_hydra_capped`, the per-matchup caps, the downgrade to 7500...). That
# is why it stays in a deliberately MODEST band: above the development
# attachment to the active (~31210) and above `_attach_enable_retreat_attack`
# (31200), but BELOW the UB->Meowth->Lillie's engine (31450) and Teal Dance
# (31500) -- with no finisher in sight for the turn, refilling the hand or
# drawing still rules over chip damage. Without a KO there is no hurry: the
# turn's attachment is still alive after those plays.
SCORE_CHARGE_ACTIVE_ATTACK = 31300

NON_ATTACKER_ENERGY_WASTE_IDS = {Meowth_ex, Fezandipiti_ex}

HIGH_PRIORITY_BENCH_TARGETS = {Budew, Munkidori, Froslass, Snorunt, Dreepy, Drakloak, Dwebble_Grass, Dwebble_Fighting}

META_BENCH_TARGETS = {Slowpoke, Slowking, Weedle, Kakuna, Beedrill, Zorua_N, Zoroark_N,
                      Abra, Kadabra, Alakazam_ex, Ralts, Kirlia, Gardevoir_ex,
                      Duskull, Dusclops, Dusknoir, Cyndaquil, Quilava, Typhlosion,
                      Chewtle, Drednaw, Sylveon, 43, 145, 249, 317}

FIRE_POKEMON_IDS = {Charizard_ex, Typhlosion, Cyndaquil, Quilava}

WATER_SNIPE_IDS = {Mega_Greninja_ex, 47}

PSYCHIC_CONTROL_IDS = {Slowking, Alakazam_ex, Gardevoir_ex}

Riolu = 677
Mega_Lucario_ex = 678
Duraludon = 169
# Rocket's Mewtwo line (limitless /decks/337, analysed July 2026): the deck's
# cheap damage engine is Team Rocket's Tarountula (400, 50 HP) -> Team Rocket's
# Spidops (401, Stage 1, a 4-4 line); Team Rocket's Mewtwo ex (431, 280 HP,
# Erasure Ball 160) is the 2-prize finisher (covered by the generic 2-prize
# gust). Cutting the Tarountula with Boss's slows their tempo just like
# Riolu/Duraludon.
Rockets_Tarountula = 400
Rockets_Spidops = 401
Rockets_Mewtwo_ex = 431

THREAT_PREEVO_IDS = {Riolu, Duraludon, Hops_Phantump, Dwebble_Grass, Dwebble_Fighting,
                     Buneary, Rockets_Tarountula}

# Dunsparce (id 65 = TEF, id 305 = JTG): NEVER gust with Boss's Orders (user
# requirement). They are walls that retreat/reposition easily; bringing them up
# as the opposing active with Boss's Orders gains nothing.
DUNSPARCE_IDS = {65, 305}

# Key Pokemon of each deck that are worth knocking out with Boss's Orders from
# the bench EVEN IF our active can knock out the opposing active, when that
# opposing active is NOT a key Pokemon (e.g. a wall with no energy). Example: in
# the Hop deck the key attacker is Hop's Trevenant; its line
# (Trevenant/Phantump) has to be hunted on the bench. The priority between
# targets (with/without energy, evolution vs pre-evolution) is resolved by the
# tier_ko adjustment (_ADJUST_GUST_OFFENSIVE) when choosing the target:
# Trevenant with energy > Trevenant without energy > Phantump with energy >
# Phantump without energy.
KEY_BENCH_ATTACKER_IDS = {Hops_Trevenant, Hops_Phantump}

EX_PREEVO_IDS = {
    Dreepy, Drakloak,
    Riolu,
    Duraludon,
    Zorua_N,
    Abra, Kadabra,
    Ralts, Kirlia,
    Marnies_Impidimp, Marnies_Morgrem,
    Buneary,  # -> Mega Lopunny ex (id 849, a 2-prize ex)
    # Cynthia's Garchomp ex line (user, registro_006 step 82 vs Garchomp,
    # WON with a mistake): the line was NOT in this set, so the deny-evo of
    # Boss's (`_bo_pe_is_ex_preevo_energized` / `_bo_pe_is_ex_line_vs_wall`)
    # never fired: with Tapu Bulu ready, Boss's in hand and a CHARGED Gabite
    # on the opposing bench, the agent knocked out the Spiritomb wall instead
    # of gusting+knocking out the Gabite (pre-evolution of the 2-prize ex
    # attacker). ALWAYS favour cutting the evolution line of Cynthia's
    # Garchomp ex.
    Cynthias_Gible, Cynthias_Gabite,
}

# Pre-evolutions in EX_PREEVO_IDS whose FINAL form is NON-ex (1 prize) in this
# environment, NOT a 2-prize ex. Abra -> Kadabra -> Alakazam (id 743) is the
# only one: the constant `Alakazam_ex = 743` is a misleading name; the card data
# marks ex=False (1 prize). The "deny an EX line" logic (which justifies gusting
# a pre-evolution with Boss's to prevent a 2-PRIZE ATTACKER) must NOT apply to
# this line: gusting+knocking out the pre-evolution yields 1 prize, the same as
# knocking out the active wall, so it is a useless gust.
NONEX_FINAL_PREEVO_IDS = {Abra, Kadabra}

_ID_NAME_EXPECTATIONS = {
    Teal_Mask_Ogerpon_ex: "Ogerpon", Chikorita: "Chikorita", Bayleef: "Bayleef",
    Meganium: "Meganium", Applin: "Applin", Dipplin: "Dipplin",
    Hydrapple_ex: "Hydrapple", Meowth_ex: "Meowth", Fezandipiti_ex: "Fezandipiti",
    Tapu_Bulu: "Tapu",
    Budew: "Budew", Crustle_Grass: "Crustle", Dwebble_Grass: "Dwebble",
    Crustle_Fighting: "Crustle", Dwebble_Fighting: "Dwebble", Sylveon: "Sylveon",
    Munkidori: "Munkidori", Froslass: "Froslass", Snorunt: "Snorunt",
    Dragapult_ex: "Dragapult", Dreepy: "Dreepy", Drakloak: "Drakloak",
    Iron_Thorns_ex: "Iron Thorns", Grimmsnarl_ex: "Grimmsnarl", Latias_ex: "Latias",
    Marnies_Impidimp: "Impidimp", Marnies_Morgrem: "Morgrem",
    Cornerstone_Mask_Ogerpon_ex: "Ogerpon", Slowking: "Slowking", Slowpoke: "Slowpoke",
    Zoroark_N: "Zoroark", Zorua_N: "Zorua", Kadabra: "Kadabra",
    Gardevoir_ex: "Gardevoir", Ralts: "Ralts", Kirlia: "Kirlia",
    Raging_Bolt_ex: "Raging Bolt", Snover: "Snover",
    Mega_Abomasnow_ex: "Abomasnow", Dusknoir: "Dusknoir", Duskull: "Duskull",
    Dusclops: "Dusclops", Typhlosion: "Typhlosion", Cyndaquil: "Cyndaquil",
    Quilava: "Quilava", Drednaw: "Drednaw", Chewtle: "Chewtle",
}


SCORE_WIN_GAME = 50000

# BASE anchors of the PLAY branch: the starting score before the
# matchup/situation adjustments. The other development scores read as "base
# +/- nuance".
SCORE_DEVELOP_BASE = 20000   # base: putting a Pokemon on the bench
SCORE_ITEM_BASE = 10000      # base: playing a card that is NOT a Pokemon (item/supporter)
# Base of the generic value of a Supporter (Boss's/Lana's/Dawn): score = BASE +
# int(value * 1.4) + supporter_boost. Used by the 3 Supporter scorers.
SCORE_SUPPORTER_VALUE_BASE = 2400

# --- Score floors ---
# A NAMED scale of negative values (robustness): they make the ordering of "do
# not play" explicit and stop a real play from ending up below a floor by
# mistake. An incremental migration of magic numbers -> constants; the values
# are EXACTLY the ones already in use (a pure rename, with no behaviour change).
SCORE_VETO = -1          # vetoed / useless play (general floor, the most common)
SCORE_CANCEL = -100      # cancel below the veto floor (e.g. a useless Ultra
                         # Ball) so the index tie-break does not choose it
SCORE_USELESS_ATTACK = -5000  # attacking for 0 damage (immune opponent: ex/ability/wall)
SCORE_NEVER = -10000     # never (e.g. do not discard Unfair Stamp; a non-lethal END)
SCORE_FORBID = -100000   # absolutely forbidden (Dunsparce, free retreat)

SCORE_LOOKAHEAD_EX_TRADE = 250
SCORE_LOOKAHEAD_KO_TRADE = 120
SCORE_LOOKAHEAD_SAFE = 60
SCORE_LOOKAHEAD_PROMOTE_KO = 120
SCORE_LOOKAHEAD_PROMOTE_SAFE = 40

SCORE_BELIEF_DIG_ENERGY = 250

# --- Scale of Lana's Aid RECOVERY (TO_HAND context) -------------------------
# Lana's picks up to 3 cards from the discard, among Pokemon WITHOUT a Rule Box
# and Basic Energies. The choice is ruled by the board reading of
# `_grass_plan`: first the Grass that enables an attack TODAY, then the ones
# a body in play is still asking for, and only then development (which the
# generic scorer scores, in the ~150-280 band). See `_pokemon_injugable` for the
# dead-card floor.
LANA_SEL_GRASS_UNLOCKS = 1400  # the Grass that enables an attack this turn
LANA_SEL_GRASS_DEMAND = 900      # Grass an attacker in play still asks for
LANA_SEL_GRASS_SURPLUS = 120     # more Grass than the board can use
LANA_SEL_INJUGABLE = 5             # it cannot be put into play: last resort

# BASE value of the PLAY layer for having something recoverable in the discard,
# before the need bonuses (short bench, fallen line, Forest, >=3 recoverable,
# matchup). `lana_val` staying EXACTLY at this base means "there is a card down
# there, but the board is not asking for it".
LANA_PLAY_BASE_RECUPERABLE = 300

# Ceiling of the VALUE of playing Lana's Aid (PLAY layer) when what can be put
# into play today is not needed: Energy nobody asks for (every attacker in play
# already reaches `ATTACK_ENERGY_REQ`, or the hand has more Grass than fits this
# turn) or a Pokemon that fits on the bench but that no bonus is claiming. With
# `SCORE_SUPPORTER_VALUE_BASE` = 2400 and the factor of 1.4, it leaves the play
# at ~2540: still playable, but it yields the turn's Supporter to any other one
# with real value (generic Dawn ~2680, Lillie's 5000).
LANA_PLAY_NO_DEMAND = 100

# Priority of Boss's Orders when, against Crustle, our active ex is blocked but
# there is a target on the opposing bench we can hit and that we can knock out
# or leave unable to retreat. It has to beat the draw baits (Lillie's ~650) and
# the rest of the Boss's ladder.
BOSS_PRIORITY_CRUSTLE_GUST = 990

# Score Tapu Bulu is lowered to while there are still items ("artefacts") in
# hand: it sits below the band of useful items (~9800+, or 9000 when an item
# limits itself) and above items that are NOT worth it (a low score). That way
# the useful items are played first and, once none is left, Tapu Bulu wins again
# and is put down. It applies ONLY to Tapu Bulu.
TAPU_WAIT_FOR_ITEMS_SCORE = 8900

# --- Boss's Orders scoring ladder (PLAY branch, ~L9250) ---
# Priority order from highest to lowest when deciding to play Boss's Orders. The
# names document which finisher each branch represents; `supporter_boost` is
# added to all of them (except the "empty" gust). Lillie's base = 5000, so the
# branches >5000 beat refilling with Lillie's and the ones <5000 yield priority
# to it.
BOSS_SCORE_WIN_NOW = 20000           # a gust that WINS the game with the active: top priority
BOSS_SCORE_GUST_2PRIZE = 6800        # gust+knock out a benched ex for 2 prizes (more than the active's 1-prize KO); it beats retreats/pivots (~6600)
BOSS_SCORE_WIN_VIA_BENCH = 5600      # a lethal gust on a bench target
BOSS_SCORE_WALL_GUST = 5500          # opponent with a wall immune (ex/ability) to the active
BOSS_SCORE_DODGE_REDIRECT = 5500     # redirection by dodge
BOSS_SCORE_PRIZE_RANK_BASE = 5200    # a gust that enables a KO (refined by prize_rank)
BOSS_SCORE_LOW_VALUE_GUST = 1500     # a low-value gust
BOSS_SCORE_DEFENSIVE_GUST = 1500     # a defensive gust (vs Crustle)
BOSS_SCORE_UNLOCK_GUST = 2600        # gust to UN-LOCK abilities (Iron Thorns ex active)
BOSS_SCORE_EMPTY_GUST = 20           # a NON-executable gust: yield to Lillie's
XEROSIC_SCORE_ALAKAZAM = 5900        # Xerosic vs Alakazam: cap Powerful Hand (20 x opposing hand). Above a hydra-charged Lillie's (5800); below GUST_2PRIZE (6800) and the defensive pivots (~6600). It yields to boss_win_via_bench through its own guard
XEROSIC_SCORE_GENERIC = 3380         # generic Xerosic with a very large opposing hand (>=7): disruption value, below a typical Lillie's (~3450)
XEROSIC_SCORE_LAST_RESORT = 20       # no clear useful effect: only if no other supporter scores
XEROSIC_SCORE_SOBRE_BOSS = 7000      # vs Alakazam with Boss's in hand: capping the hand beats ANY gust that does not WIN the game (above GUST_2PRIZE 6800); the winning gust (WIN_NOW 20000) is still higher
# --- FINISHER FISHING (see `_finisher_fishing`) ------------------------------
# Lillie's Determination when the turn has no attack available and the draw may
# bring the energy that unlocks a KO. It is placed above the whole Boss's ladder
# that does not WIN the game or take 2 prizes RIGHT NOW (GUST_2PRIZE 6800) and
# above the hydra-charged Lillie's (5800): a probable 2-prize KO is worth more
# than any development gust, and gusting also DEGRADES the target (Myriad Leaf
# Shower scales with the energy on the opposing active).
LILLIE_SCORE_FISHING = 5900
# Minimum probability for the fishing to OVERRIDE Lillie's ordering vetoes (an
# Ultra Ball that completes a line, yielding to an executable gust...). The case
# that motivates it comes out at 0.63 (2 Grass out of 10 live, drawing 8 from
# 42). Below this threshold the refill is still played for its normal value,
# with no privileges.
FISHING_PROB_MIN = 0.35
# Minimum prizes of the fished KO: the fishing only overrides the vetoes if what
# it unlocks TAKES a prize (a probable chip does not pay for shuffling the hand
# away).
FISHING_PRIZES_MIN = 1



XEROSIC_STAMP_ORDEN_MIN_OP_HAND = 10  # minimum opposing hand for Xerosic to be played BEFORE Unfair Stamp: the Stamp leaves them at 2 either way, so the only thing the order buys is the `op_hand - 3` cards Xerosic sends to the discard FOREVER; it is only worth the Supporter slot when that beats a whole hand (>=7 cards)

# --- Unfair Stamp: when the Stamp DESERVES to be played (user, August 2026) --
# The Stamp is an ACE SPEC (Item) that shuffles BOTH hands into the decks and
# deals 5 cards to us and 2 to the opponent. It only has two ways of paying off,
# and the rule requires AT LEAST ONE of them (it is a CARD rule, not a matchup
# one: it holds against any deck):
#
#   (1) DISRUPTION -- it only exists if it TAKES cards away from the opponent.
#       Since it leaves them at exactly 2, with an opposing hand <= 2 it takes
#       nothing away; with 1 card it even GIVES them one (registro_006 step 99
#       vs Marnie: opponent with 1 card, the Stamp left them at 2).
#   (2) REFILL -- we draw 5, but first we shuffle OUR WHOLE hand into the deck.
#       It is worth it while what is sacrificed (the hand WITHOUT the Stamp
#       itself) is <= 4 cards; above that the Stamp burns more playable
#       resources than it returns.
STAMP_MIN_OP_HAND = 3          # minimum opposing hand for the Stamp to DISRUPT (it leaves them at 2)
STAMP_MAX_HAND_SACRIFICADA = 4  # our own cards (hand without the Stamp) that can be shuffled away


__all__ = [
    'RETREAT_COST',
    'Teal_Mask_Ogerpon_ex',
    'Chikorita',
    'Bayleef',
    'Meganium',
    'Applin',
    'Dipplin',
    'Hydrapple_ex',
    'Meowth_ex',
    'Fezandipiti_ex',
    'Tapu_Bulu',
    'Pinsir',
    'Lillie_Determination',
    'Boss_Orders',
    'Lanas_Aid',
    'Xerosic_Machinations',
    'Dawn',
    'Bug_Catching_Set',
    'Ultra_Ball',
    'Night_Stretcher',
    'Unfair_Stamp',
    'Poke_Pad',
    'Forest_of_Vitality',
    'Neutralization_Zone',
    'Team_Rockets_Watchtower',
    'Festival_Grounds',
    'Grand_Tree',
    'Maximum_Belt',
    'Brave_Bangle',
    'Basic_Grass_Energy',
    'Budew',
    'Crustle_Grass',
    'Dwebble_Grass',
    'Crustle_Fighting',
    'Dwebble_Fighting',
    'Sylveon',
    'Comfey',
    'Bramblin',
    'Brambleghast',
    'Munkidori',
    'Froslass',
    'Snorunt',
    'Dragapult_ex',
    'Dreepy',
    'Drakloak',
    'Iron_Thorns_ex',
    'Charizard_ex',
    'Grimmsnarl_ex',
    'Marnies_Impidimp',
    'Marnies_Morgrem',
    'Latias_ex',
    'Cornerstone_Mask_Ogerpon_ex',
    'Cornerstone_Mask_Ogerpon',
    'Mega_Kangaskhan_ex',
    'Hops_Phantump',
    'Hops_Trevenant',
    'Splashing_Dodge_Atk',
    'COIN_FLIP_LOG_TYPE',
    'Mega_Greninja_ex',
    'Mega_Starmie_ex',
    'Slowking',
    'Slowpoke',
    'Beedrill',
    'Weedle',
    'Kakuna',
    'Zoroark_N',
    'Zorua_N',
    'Alakazam_ex',
    'Abra',
    'Kadabra',
    'POWERFUL_HAND_ATTACK_ID',
    'DO_THE_WAVE_ATTACK_ID',
    'FESTIVAL_LEAD_IDS',
    'ALAKAZAM_LINE_IDS',
    'ALAKAZAM_ATTACKER_IDS',
    'Buneary',
    'Mega_Lopunny_ex',
    'Cynthias_Gible',
    'Cynthias_Gabite',
    'Cynthias_Garchomp_ex',
    'Gardevoir_ex',
    'Ralts',
    'Kirlia',
    'Raging_Bolt_ex',
    'Lugia_VSTAR',
    'Snover',
    'Mega_Abomasnow_ex',
    'Dusknoir',
    'Duskull',
    'Dusclops',
    'Typhlosion',
    'Cyndaquil',
    'Quilava',
    'Drednaw',
    'Chewtle',
    'Cubchoo',
    'Beartic',
    'Eevee_TWM',
    'Eevee_SFA',
    'Eevee_PRE_ex',
    'Eevee_SSP',
    'EEVEE_IDS',
    'OUR_EX_IDS',
    'DECK_ITEM_IDS',
    'EX_IMMUNE_IDS',
    'CRUSTLE_LINE_IDS',
    'ABILITY_IMMUNE_IDS',
    'OUR_ABILITY_IDS',
    'GUST_TRAP_IDS',
    'Pikachu_ex_Resolute',
    'FULL_HP_SURVIVE_IDS',
    'Mega_Hawlucha_ex',
    'Survival_Brace',
    'Farigiraf_ex',
    'OUR_BASIC_EX_IDS',
    'CUBCHOO_ALLOWED_PLAY_IDS',
    'Jellicent_ex',
    'Tyranitar_Daunting',
    'Galvantula_ex',
    'FULGURITE_ATTACK_ID',
    'OP_ITEM_LOCK_ACTIVE_IDS',
    'OUR_RULEBOX_ABILITY_IDS',
    'Munkidori_ex',
    'Pecharunt_ex',
    'Mega_Gengar_ex',
    'OP_BENCH_BURST',
    'OP_BENCH_SNIPE_DAMAGE',
    'OP_BENCH_SNIPE_DEFAULT',
    'FREEZING_SHROUD_COUNTER',
    'CHECKUPS_PER_ROUND',
    'ADRENA_BRAIN_MOVE',
    'RIPENING_HEAL',
    'RIPEN_HEAL_TARGET_SCORE',
    'RIPEN_HEAL_ABILITY_SCORE',
    'RIPEN_HEAL_EX_ABILITY_SCORE',
    'SCORE_CHARGE_DOOMED',
    'SCORE_CHARGE_LETHAL_FLOOR',
    'FEZ_DRAW_ABILITY_SCORE',
    'SCORE_CHARGE_ACTIVE_FINISHER',
    'SCORE_CHARGE_ACTIVE_ATTACK',
    'NON_ATTACKER_ENERGY_WASTE_IDS',
    'HIGH_PRIORITY_BENCH_TARGETS',
    'META_BENCH_TARGETS',
    'FIRE_POKEMON_IDS',
    'WATER_SNIPE_IDS',
    'PSYCHIC_CONTROL_IDS',
    'Riolu',
    'Mega_Lucario_ex',
    'Duraludon',
    'Rockets_Tarountula',
    'Rockets_Spidops',
    'Rockets_Mewtwo_ex',
    'THREAT_PREEVO_IDS',
    'DUNSPARCE_IDS',
    'KEY_BENCH_ATTACKER_IDS',
    'EX_PREEVO_IDS',
    'NONEX_FINAL_PREEVO_IDS',
    '_ID_NAME_EXPECTATIONS',
    'SCORE_WIN_GAME',
    'SCORE_DEVELOP_BASE',
    'SCORE_ITEM_BASE',
    'SCORE_SUPPORTER_VALUE_BASE',
    'SCORE_VETO',
    'SCORE_CANCEL',
    'SCORE_USELESS_ATTACK',
    'SCORE_NEVER',
    'SCORE_FORBID',
    'SCORE_LOOKAHEAD_EX_TRADE',
    'SCORE_LOOKAHEAD_KO_TRADE',
    'SCORE_LOOKAHEAD_SAFE',
    'SCORE_LOOKAHEAD_PROMOTE_KO',
    'SCORE_LOOKAHEAD_PROMOTE_SAFE',
    'SCORE_BELIEF_DIG_ENERGY',
    'LANA_SEL_GRASS_UNLOCKS',
    'LANA_SEL_GRASS_DEMAND',
    'LANA_SEL_GRASS_SURPLUS',
    'LANA_SEL_INJUGABLE',
    'LANA_PLAY_BASE_RECUPERABLE',
    'LANA_PLAY_NO_DEMAND',
    'BOSS_PRIORITY_CRUSTLE_GUST',
    'TAPU_WAIT_FOR_ITEMS_SCORE',
    'BOSS_SCORE_WIN_NOW',
    'BOSS_SCORE_GUST_2PRIZE',
    'BOSS_SCORE_WIN_VIA_BENCH',
    'BOSS_SCORE_WALL_GUST',
    'BOSS_SCORE_DODGE_REDIRECT',
    'BOSS_SCORE_PRIZE_RANK_BASE',
    'BOSS_SCORE_LOW_VALUE_GUST',
    'BOSS_SCORE_DEFENSIVE_GUST',
    'BOSS_SCORE_UNLOCK_GUST',
    'BOSS_SCORE_EMPTY_GUST',
    'XEROSIC_SCORE_ALAKAZAM',
    'XEROSIC_SCORE_GENERIC',
    'XEROSIC_SCORE_LAST_RESORT',
    'XEROSIC_SCORE_SOBRE_BOSS',
    'LILLIE_SCORE_FISHING',
    'FISHING_PROB_MIN',
    'FISHING_PRIZES_MIN',
    'XEROSIC_STAMP_ORDEN_MIN_OP_HAND',
    'STAMP_MIN_OP_HAND',
    'STAMP_MAX_HAND_SACRIFICADA',
]
