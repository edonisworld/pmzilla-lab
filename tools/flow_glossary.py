"""
PMZilla Lab : glossaire des mesures de flux, en français et en anglais.

Source unique des définitions : les rapports Markdown de flux_jira.py (français) et le tableau de bord
flow_board.py (anglais par défaut, français avec --language fr) les lisent ici, pour qu'ils ne se contredisent jamais.
Les textes sont en Markdown léger (**gras**) ; aucun chiffre n'y est écrit en dur.

ORDRE_RAPPORT : les définitions de « Comment lire ce rapport », dans l'ordre du rapport (REGLES_SEGMENT : celles qui
n'apparaissent que si le rapport a un temps par segment). Les autres entrées servent au tableau de bord.
"""
from __future__ import annotations

ORDRE_RAPPORT = ["p50", "p85", "pourquoi_percentiles", "lead_time_age", "wip", "arrivees", "little", "monte_carlo"]
ORDRE_SEGMENT = ["segment", "engagement", "efficacite", "couverture"]
ORDRE_FERMETURES = ["fermetures_groupees"]      # seulement si le rapport a la section « Fermetures groupées »
ORDRE_PARTAGES = ["tickets_partages"]           # seulement si le rapport a la section « Tickets partagés par équipe »

GLOSSAIRE: dict[str, dict[str, str]] = {
    "fr": {
        "p50": "**P50 (médiane)** : la moitié des éléments sont en dessous, l'autre moitié au-dessus. C'est le cas typique.",
        "p85": "**P85** : 85 % des éléments sont en dessous, 15 % au-dessus. Il sert à s'engager : « dans 85 % des cas, "
               "moins de X jours ». P70 et P95 se lisent de la même façon, avec 70 % et 95 %.",
        "pourquoi_percentiles": "**Pourquoi des percentiles et pas une moyenne** : quelques tickets très longs tirent "
                                "la moyenne vers le haut. Les percentiles ne se laissent pas entraîner par ces cas extrêmes.",
        "lead_time_age": "**Lead time** : de la création à la résolution, pour les éléments terminés seulement. **Âge** : "
                         "depuis le dernier changement de catégorie d'état (à défaut, depuis la création), pour les "
                         "éléments encore en cours. Le lead time ne voit que ce qui finit ; l'âge montre ce qui reste coincé.",
        "wip": "**WIP** : les éléments en cours. **WIP actif** : travaillé en ce moment. **WIP en attente** : dans un "
               "état d'attente listé dans flux.yaml, comme « Ready for ». **WIP dormant** : non terminé et sans "
               "changement d'état depuis plus de 365 jours (déduit de l'historique des états, option --dormant-from-history). Un "
               "ticket dormant n'est ni actif ni en attente.",
        "arrivees": "**Arrivées et sorties** : les tickets créés et les éléments terminés, semaine par semaine. Si les "
                    "arrivées dépassent durablement les sorties, le stock grossit. Les arrivées comptent aussi les "
                    "tickets rejetés.",
        "little": "**Loi de Little** : le nombre d'éléments en cours divisé par le débit moyen donne une durée moyenne "
                  "de séjour. À lire avec prudence quand les arrivées dépassent durablement les sorties.",
        "monte_carlo": "**Prévision Monte Carlo** : 10 000 tirages dans le débit des semaines passées. Elle dit en "
                       "combien de semaines de débit le stock actuel s'écoulerait si rien de nouveau n'entrait. Ce n'est "
                       "pas une date.",
        "segment": "**Segment** : un groupe d'états consécutifs du workflow (définition, prêt, implémentation, revue et "
                   "vérification, acceptation), réglé dans flux.yaml. **Temps par segment** : combien de jours un "
                   "ticket a passé dans les états du segment, en jours calendaires, état initial compris ; le temps est "
                   "cumulé si le ticket revient dans le segment. « Sorti du segment » veut dire : parti vers un autre "
                   "segment pendant la période.",
        "engagement": "**Point d'engagement** : le moment où l'équipe s'engage, ici l'entrée dans le segment réglé par "
                      "commitment_point. **Lead time de livraison** : du point d'engagement à la résolution ; il est "
                      "plus court que le lead time depuis la création, qui compte aussi l'attente dans le backlog.",
        "efficacite": "**Efficacité de flux** : la part du temps passée en état actif, entre le point d'engagement et "
                      "la résolution. Un état d'attente (waiting_states) compte comme du temps perdu à attendre, tout "
                      "autre état comme du temps actif. Une efficacité basse dit que les tickets attendent beaucoup, pas "
                      "que les gens travaillent mal.",
        "fermetures_groupees": "**Fermeture groupée** : au moins N tickets livrés d'un même projet dont la résolution "
                               "tombe dans la même minute (N : batch_closure_threshold de flux.yaml). C'est le signe "
                               "probable d'un changement de statut en masse (nettoyage, migration) plutôt que de "
                               "livraisons au fil de l'eau. Un compte seulement : ces tickets restent dans le débit.",
        "tickets_partages": "**Tickets partagés** : un ticket porté par plusieurs équipes compte une seule fois, pour sa "
                            "première équipe. Pour chaque équipe, la première colonne compte les tickets qui lui sont "
                            "attribués tout en étant partagés, la seconde ceux qu'elle porte sans qu'ils lui soient "
                            "attribués. Une cellule de moins de 5 tickets s'écrit « masqué ».",
        "couverture": "**Couverture** : la part des tickets du rapport dont l'historique est connu. Sous 90 %, les "
                      "chiffres du temps par segment ne décrivent qu'une partie des tickets.",
        # entrées du tableau de bord seulement
        "debit": "**Débit** : le nombre d'éléments terminés (livrés) par semaine. Les clôtures sans livraison (rejet, "
                 "doublon) n'y comptent pas. Une semaine à zéro entre deux pics signale souvent des clôtures groupées.",
        "cfd": "**Diagramme de flux cumulé** : à la fin de chaque semaine, le nombre de tickets dans chaque segment, "
               "empilés, avec les tickets livrés en bas. La largeur d'une bande est le stock de ce segment ; une bande "
               "qui s'élargit est une file qui grossit ; une bande qui reste plate est un flux stable. Calculé à partir "
               "de l'historique des états : les tickets sans historique n'y figurent pas.",
        "aging_wip": "**Âge du WIP** : un point par ticket en cours, placé selon son état (ou son segment) et son âge en "
                     "jours. Aucune clé de ticket. La forme et le libellé distinguent actif, en attente et dormant. Les "
                     "points au-dessus du lead time P85 sont les éléments qui restent coincés.",
        "repartition": "**Répartition du WIP** : la part des éléments en cours qui sont actifs, en attente ou dormants. "
                       "Un WIP majoritairement en attente dit que le travail attend plus qu'il n'avance.",
        "graphe": "**Carte des dépendances** : chaque cercle est une équipe, chaque flèche va de l'équipe qui attend vers "
                  "l'équipe attendue. L'épaisseur est le nombre de dépendances ouvertes. Une dépendance vers un ticket "
                  "hors de l'export est « à état inconnu » et n'est jamais comptée comme ouverte. Les équipes sont "
                  "disposées par le calcul, sans classement.",
        "base": "**Évolution depuis la base** : le rapport de référence daté de la base, comparé à chaque rapport "
                "suivant de la même série. Les rapports calculés avec d'autres options (périmètre, historique) ne "
                "se comparent pas directement.",
    },
    "en": {
        "p50": "**P50 (median)**: half of the items are below, half are above. It is the typical case.",
        "p85": "**P85**: 85% of the items are below, 15% above. It is used to make commitments: \"in 85% of cases, "
               "less than X days\". P70 and P95 read the same way, with 70% and 95%.",
        "pourquoi_percentiles": "**Why percentiles rather than an average**: a few very long tickets pull the average "
                                "up. Percentiles are not dragged along by these extreme cases.",
        "lead_time_age": "**Lead time**: from creation to resolution, for finished items only. **Age**: since the last "
                         "status category change (creation date if there is none), for items still in progress. Lead "
                         "time only sees what finishes; age shows what stays stuck.",
        "wip": "**WIP**: items in progress. **Active WIP**: being worked on right now. **Waiting WIP**: in a waiting "
               "status listed in flux.yaml, such as \"Ready for\". **Dormant WIP**: not finished and with no status "
               "change for more than 365 days (inferred from the status history, option --dormant-from-history). A dormant ticket is neither "
               "active nor waiting.",
        "arrivees": "**Arrivals and departures**: tickets created and items finished, week by week. If arrivals keep "
                    "exceeding departures, the stock grows. Arrivals also count rejected tickets.",
        "little": "**Little's law**: the number of items in progress divided by the average throughput gives an "
                  "average time in the system. Read it with care when arrivals keep exceeding departures.",
        "monte_carlo": "**Monte Carlo forecast**: 10,000 draws from the throughput of past weeks. It says in how many "
                       "weeks of throughput the current stock would drain if nothing new came in. It is not a date.",
        "segment": "**Segment**: a group of consecutive workflow statuses (definition, ready, implementation, review "
                   "and verification, acceptance), set in flux.yaml. **Time in segment**: how many days a ticket spent "
                   "in the statuses of the segment, in calendar days, initial status included; the time adds up if the "
                   "ticket comes back to the segment. \"Left the segment\" means: moved to another segment during the "
                   "period.",
        "engagement": "**Commitment point**: the moment the team commits, here the entry into the segment set by "
                      "commitment_point. **Delivery lead time**: from the commitment point to resolution; it is "
                      "shorter than the lead time from creation, which also counts the wait in the backlog.",
        "efficacite": "**Flow efficiency**: the share of time spent in an active status, between the commitment point "
                      "and resolution. A waiting status (waiting_states) counts as time lost waiting, any other status "
                      "as active time. A low efficiency says tickets wait a lot, not that people work badly.",
        "fermetures_groupees": "**Batched closure**: at least N delivered tickets of the same project whose resolution "
                               "falls in the same minute (N: batch_closure_threshold in flux.yaml). It most likely "
                               "points to a bulk status change (clean-up, migration) rather than deliveries as they "
                               "happen. A count only: these tickets stay in the throughput.",
        "tickets_partages": "**Shared tickets**: a ticket carried by several teams counts once, for its first team. For "
                            "each team, the first column counts the tickets attributed to it while shared, the second "
                            "those it carries without their being attributed to it. A cell under 5 tickets is written \"masked\".",
        "couverture": "**Coverage**: the share of the tickets in the report whose history is known. Below 90%, the "
                      "figures for time in segment only describe part of the tickets.",
        "debit": "**Throughput**: the number of items finished (delivered) per week. Closures without delivery "
                 "(rejected, duplicate) are not counted. A zero week between two peaks often points to batched closures.",
        "cfd": "**Cumulative flow diagram**: at the end of each week, the number of tickets in each segment, stacked, "
               "with delivered tickets at the bottom. The width of a band is the stock of that segment; a widening "
               "band is a growing queue; a flat band is a stable flow. Computed from the status history: tickets "
               "without history are not shown.",
        "aging_wip": "**Aging WIP**: one point per ticket in progress, placed by its status (or segment) and its age in "
                     "days. No ticket key. Shape and label tell active, waiting and dormant apart. Points above the "
                     "P85 lead time are the items that stay stuck.",
        "repartition": "**WIP breakdown**: the share of items in progress that are active, waiting or dormant. A WIP "
                       "that is mostly waiting says work waits more than it moves.",
        "graphe": "**Dependency map**: each circle is a team, each arrow goes from the team that waits to the team "
                  "waited on. Thickness is the number of open dependencies. A dependency on a ticket outside the "
                  "export is \"unknown state\" and is never counted as open. Teams are laid out by the computation, "
                  "with no ranking.",
        "base": "**Change since the baseline**: the reference report dated at the baseline, compared with each later "
                "report of the same series. Reports computed with other options (scope, history) cannot be compared "
                "directly.",
    },
}


def lignes_rapport(langue: str = "fr", segments: bool = False, fermetures: bool = False, partages: bool = False) -> list[str]:
    """Puces Markdown des définitions du rapport, dans l'ordre fixe (avec celles du temps par segment, des fermetures
    groupées et des tickets partagés si demandé)."""
    ids = (ORDRE_RAPPORT + (ORDRE_SEGMENT if segments else []) + (ORDRE_FERMETURES if fermetures else [])
           + (ORDRE_PARTAGES if partages else []))
    return [f"- {GLOSSAIRE[langue][i]}" for i in ids]
