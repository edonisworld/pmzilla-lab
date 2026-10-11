# Métriques de flux : ancien, au 2026-10-04

Période : 2026-03-30 au 2026-09-27 (26 semaines complètes). Types : tous. Agrégats calculés en local à partir d'un export Jira ; aucun ticket n'est cité.

## Débit
- 58 éléments terminés, soit 2.2 par semaine en moyenne (médiane 2) ; 2 semaine(s) sans aucun élément terminé.
- Par semaine, de la plus ancienne à la plus récente : 1, 2, 0, 3, 1, 1, 0, 2, 2, 2, 4, 1, 2, 6, 2, 2, 1, 1, 2, 2, 1, 3, 3, 5, 1, 8.
- Motifs de clôture comptés comme livrés : Done 58.
- Clos sans livraison, exclus du débit, du lead time et des prévisions : Rejected 25, Duplicate 22.

## Arrivées et sorties

Arrivées : tickets créés pendant la période, mêmes types et mêmes exclusions que le débit. Sorties : éléments terminés comptés comme livrés (le débit). Différence : arrivées moins sorties ; positive, le stock de tickets ouverts grossit, négative, il diminue.

| Semaine (début) | Arrivées | Sorties | Différence |
|---|---|---|---|
| 2026-03-30 | 4 | 1 | +3 |
| 2026-04-06 | 5 | 2 | +3 |
| 2026-04-13 | 6 | 0 | +6 |
| 2026-04-20 | 7 | 3 | +4 |
| 2026-04-27 | 5 | 1 | +4 |
| 2026-05-04 | 11 | 1 | +10 |
| 2026-05-11 | 4 | 0 | +4 |
| 2026-05-18 | 11 | 2 | +9 |
| 2026-05-25 | 8 | 2 | +6 |
| 2026-06-01 | 8 | 2 | +6 |
| 2026-06-08 | 3 | 4 | -1 |
| 2026-06-15 | 5 | 1 | +4 |
| 2026-06-22 | 3 | 2 | +1 |
| 2026-06-29 | 4 | 6 | -2 |
| 2026-07-06 | 10 | 2 | +8 |
| 2026-07-13 | 6 | 2 | +4 |
| 2026-07-20 | 7 | 1 | +6 |
| 2026-07-27 | 3 | 1 | +2 |
| 2026-08-03 | 5 | 2 | +3 |
| 2026-08-10 | 9 | 2 | +7 |
| 2026-08-17 | 4 | 1 | +3 |
| 2026-08-24 | 8 | 3 | +5 |
| 2026-08-31 | 10 | 3 | +7 |
| 2026-09-07 | 5 | 5 | 0 |
| 2026-09-14 | 4 | 1 | +3 |
| 2026-09-21 | 9 | 8 | +1 |
| **Total** | **164** | **58** | **+106** |

- Moyenne par semaine : 6.3 arrivées, 2.2 sorties.
- Note : les tickets créés puis rejetés, ou restés sans mouvement, comptent dans les arrivées, mais jamais dans les sorties (les motifs de clôture exclus ne sont pas du débit) : la différence ne mesure donc pas une croissance du travail réel. Un ticket dormant (plus de 365 jours) n'entre dans les arrivées que si sa création tombe dans la période, ce qui suppose une période de plus de 52 semaines. Les arrivées dépendent aussi de la requête de l'export.

### Par équipe

| Équipe | Arrivées | Sorties | Différence |
|---|---|---|---|
| (sans équipe) | 50 | 19 | +31 |
| Equipe A | 32 | 12 | +20 |
| Equipe B | 42 | 16 | +26 |
| Equipe C | 40 | 11 | +29 |

## Lead time (de la création à la résolution)
- Tous types : P50 45 j · P70 81 j · P85 98 j · P95 115 j.
- Bug (14 terminés) : P50 52 j · P70 81 j · P85 105 j · P95 113 j.
- Story (30 terminés) : P50 42 j · P70 82 j · P85 98 j · P95 116 j.
- Task (14 terminés) : P50 50 j · P70 74 j · P85 98 j · P95 104 j.

## Travail en cours
- WIP : 50 éléments en cours (In Review 23, Testing 14, In Progress 13) ; 33 éléments à faire.
- Âge des éléments en cours depuis leur début : P50 122 j · P70 165 j · P85 198 j · P95 234 j.
- Âge depuis leur création : P50 138 j · P70 177 j · P85 222 j · P95 247 j.
- 27 élément(s) en cours sont plus âgés (base : début) que le lead time P85 des éléments terminés.
- Éléments en cours depuis plus de 30 / 90 / 180 / 365 / 730 jours : 41 / 27 / 10 / 0 / 0.

### Âge par état (base : début)

| État | Éléments | Âge P50 | Âge P85 | Plus de 90 j | Plus de 365 j |
|---|---|---|---|---|---|
| In Review | 23 | 117 j | 220 j | 12 | 0 |
| Testing | 14 | 139 j | 180 j | 10 | 0 |
| In Progress | 13 | 61 j | 197 j | 5 | 0 |

### Files avant engagement : âge des éléments à faire, par état

Un élément peut attendre longtemps avant d'être commencé : ce temps n'entre ni dans le WIP ni dans le lead time d'un élément pas encore terminé. « Depuis la catégorie » part du dernier changement de catégorie d'état Jira (entrée en analyse ou en définition, par exemple), quand il est connu.

| État | Éléments | Âge P50 (création) | Âge P85 (création) | Âge P50 (catégorie) | Plus de 90 j | Plus de 365 j |
|---|---|---|---|---|---|---|
| Open | 15 | 136 j | 177 j | n/d | 11 | 0 |
| Backlog | 12 | 116 j | 190 j | n/d | 7 | 0 |
| To Do | 6 | 175 j | 192 j | n/d | 5 | 0 |

- Loi de Little (WIP actuel / débit moyen) : à ce rythme, un élément reste en moyenne environ 157 jours en cours ; à comparer à l'âge des éléments en cours et au lead time médian.

## Par équipe

| Équipe | Terminés | Débit / sem. | Lead time P50 | Lead time P85 | WIP | Âge WIP P50 | WIP > 90 j |
|---|---|---|---|---|---|---|---|
| (sans équipe) | 19 | 0.7 | 51 j | 100 j | 11 | 42 j | 3 |
| Equipe A | 12 | 0.5 | 60 j | 98 j | 13 | 145 j | 9 |
| Equipe B | 16 | 0.6 | 56 j | 96 j | 13 | 122 j | 7 |
| Equipe C | 11 | 0.4 | 35 j | 92 j | 13 | 152 j | 8 |

Éléments terminés par semaine et par équipe, de la plus ancienne à la plus récente (des semaines à zéro entre deux pics signalent des clôtures groupées) :

- (sans équipe) : 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 3, 0, 1, 0, 1, 1, 1, 1, 2, 0, 1, 1, 1, 0, 0, 3
- Equipe A : 0, 1, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 2, 1, 1, 0, 0, 0, 1, 0, 1, 0, 1, 0, 1
- Equipe B : 1, 1, 0, 1, 0, 0, 0, 2, 1, 0, 0, 1, 0, 4, 0, 0, 0, 0, 0, 0, 0, 1, 0, 2, 0, 2
- Equipe C : 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 2, 2, 1, 2


## Prévisions Monte Carlo (10 000 simulations sur le débit des semaines de la période)
- Terminer 50 éléments : 23 semaines avec 50 % de chances, 27 avec 85 %, 29 avec 95 %.

## Comment lire ce rapport

- **P50 (médiane)** : la moitié des éléments sont en dessous, l'autre moitié au-dessus. C'est le cas typique.
- **P85** : 85 % des éléments sont en dessous, 15 % au-dessus. Il sert à s'engager : « dans 85 % des cas, moins de X jours ». P70 et P95 se lisent de la même façon, avec 70 % et 95 %.
- **Pourquoi des percentiles et pas une moyenne** : quelques tickets très longs tirent la moyenne vers le haut. Les percentiles ne se laissent pas entraîner par ces cas extrêmes.
- **Lead time** : de la création à la résolution, pour les éléments terminés seulement. **Âge** : depuis le dernier changement de catégorie d'état (à défaut, depuis la création), pour les éléments encore en cours. Le lead time ne voit que ce qui finit ; l'âge montre ce qui reste coincé.
- **WIP** : les éléments en cours. **WIP actif** : travaillé en ce moment. **WIP en attente** : dans un état d'attente listé dans flux.yaml, comme « Ready for ». **WIP dormant** : non terminé et sans changement d'état depuis plus de 365 jours (seulement quand un export des dormants est fourni). Un ticket dormant n'est ni actif ni en attente.
- **Arrivées et sorties** : les tickets créés et les éléments terminés, semaine par semaine. Si les arrivées dépassent durablement les sorties, le stock grossit. Les arrivées comptent aussi les tickets rejetés.
- **Loi de Little** : le nombre d'éléments en cours divisé par le débit moyen donne une durée moyenne de séjour. À lire avec prudence quand les arrivées dépassent durablement les sorties.
- **Prévision Monte Carlo** : 10 000 tirages dans le débit des semaines passées. Elle dit en combien de semaines de débit le stock actuel s'écoulerait si rien de nouveau n'entrait. Ce n'est pas une date.

Exemples tirés de ce rapport :
- L'âge P85 des éléments en cours est de 198 jours : 15 % des éléments en cours y sont depuis plus de 198 jours.
- Le lead time P85 est de 98 jours : 85 % des éléments terminés l'ont été en moins de 98 jours.

## Limites
- Le lead time compte depuis la création du ticket, attente dans le backlog comprise : ce n'est pas un cycle time.
- Les prévisions supposent que le débit des prochaines semaines ressemble à celui de la période, et que les éléments sont de taille comparable.
