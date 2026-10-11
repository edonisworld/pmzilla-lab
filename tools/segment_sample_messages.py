"""PMZilla Lab : messages de tools/segment_sample.py par langue (plan de la version anglaise, lot 3, étape 2).

Le français reproduit à l'octet près les textes du script avant le lot 3. Ne passent pas par ce catalogue : les noms
d'états de Jira, les noms de segments des réglages (affichés en anglais avec --language en pour les segments par défaut),
les clés de tickets et les messages de flux_jira.py (lecture de l'historique, des exports et du périmètre), qui sont ceux
du script flux_jira.py.
"""

CATALOGS = {
    "fr": {
        # valeurs affichées à la place des repères internes
        "origin_creation": "(création)",
        "destination_resolved": "(résolu depuis le segment)",
        "no_project": "(sans projet)",
        "percent": "{value} %",
        # colonnes des tableaux de tickets
        "col_key": "Clé",
        "col_project": "Projet",
        "col_days_cumulative": "Jours cumulés",
        "col_visits": "Visites",
        "col_entry_longest": "Entrée (visite la plus longue)",
        "col_exit": "Sortie",
        "col_days_visit": "Jours de cette visite",
        "col_origin": "Origine",
        "col_destination": "Destination",
        "col_age_current": "Âge de la visite en cours (j)",
        "col_entry": "Entrée",
        "col_days_cumulative_previous": "Jours cumulés (visites précédentes comprises)",
        "col_visits_current": "Visites (en cours comprise)",
        "col_current_state": "État actuel",
        # en-tête et population
        "title": "# Échantillon du segment « {segment} »",
        "period": "\nPériode : {start} au {end} ({weeks} semaines complètes au plus), calcul au {today}.",
        "batch_discarded": "\nFermetures en lot écartées (--exclude-batch-closures) : {tickets} tickets sortis du segment, "
                           "{passages} passages de « {waiting} » à « {start} ». Tous les calculs ci-dessous sont faits sans eux.",
        "batch_no_time": "{count} tickets livrés sans heure de résolution : jamais comptés en lot.",
        "key_and_states_only": "Clés et états seulement ; rien n'est écrit sur le disque.",
        "states_header": "\n## États du segment (réglage {setting})\n",
        "setting_custom": "« segments » de flux.yaml",
        "setting_default": "par défaut de history_common.py",
        "other_segments": "\nAutres segments, en nombre d'états : {segments}.",
        "population": "\n## Population\n\n{count} tickets lus après écartement, {without_history} sans historique dans le cache.",
        "population_discarded": "\n## Population\n\n{count} tickets lus après écartement ({discarded} écartés), "
                                "{without_history} sans historique dans le cache.",
        "nothing_left": "\nAucun ticket sorti du segment pendant la période : rien à échantillonner.",
        "left_summary": "\nTickets sortis du segment pendant la période : {count} ; temps cumulé P50 {p50} j, "
                        "P85 {p85} j, moyenne {mean} j, maximum {max} j.",
        "visits_per_ticket": "Visites par ticket : 1 visite {one}, 2 visites ou plus {many}.",
        "longest_header": "\n## Les {count} plus longs (temps cumulé)\n",
        "near_median_header": "\n## {count} tickets proches de la médiane (tirage au hasard, graine {seed})\n",
        "near_median_window": "Fenêtre : de {low} à {high} j (P40 à P60) ; {candidates} candidats.\n",
        "near_median_shortage": "Attention : seulement {found} candidat(s) pour {asked} demandés.\n",
        "oldest_header": "\n## Les {count} plus anciens encore dans le segment (sur {total})\n",
        # --by-state
        "state_time_header": "\n## Temps par état du segment (population de {count} tickets sortis)\n",
        "state_time_columns": "| État | Tickets passés par l'état | Total (j) | Part du temps du segment | P50 (j) | P85 (j) |",
        "state_time_total": "\nTotal du segment : {total} j (somme des temps cumulés). P50 et P85 : jours passés dans "
                            "l'état par ticket, cumulés sur les visites, parmi les tickets passés par l'état.",
        "group_longest": "plus long",
        "group_near_median": "tiré près de la médiane",
        "group_still_in": "encore dans le segment",
        "detail_header": "\n## Détail par état des tickets de l'échantillon\n",
        "detail_columns": "| Clé | Groupe | Total (j) | {states} |",
        "detail_note": "\n« - » : le ticket n'est pas passé par l'état. Pour un ticket encore dans le segment, le total et "
                       "le détail comprennent la visite en cours, jusqu'à la date du calcul.",
        "grouped_header": "\n## Sorties groupées des {count} plus longs\n",
        "grouped_columns": "| Clé | Sortie de la visite la plus longue | Autres tickets sortis du segment ce jour-là |",
        "grouped_reference": "\nRepère : sur les {days} jours où au moins un ticket de la population est sorti du "
                             "segment, P50 {p50} et P85 {p85} sorties par jour, maximum {max} le {date}.",
        # --starts
        "starts_header": "\n## Passages de « {waiting} » à « {start} » par projet\n",
        "starts_summary": "{passages} passages dans les visites terminées de la population, {tickets} tickets "
                          "concernés. Projets listés : au moins {minimum} passages ; {below} projet(s) sous le seuil "
                          "({below_passages} passages) non listés.\n",
        "starts_none": "Aucun projet n'atteint le seuil.",
        "starts_columns": "| Projet | Passages | Jours distincts | Jours les plus chargés retenus (20 %) | "
                          "Part des passages sur ces jours | Part attendue au hasard (à jours actifs égaux) | "
                          "95e centile des tirages (à jours actifs égaux) | Plus concentré que le hasard à jours actifs égaux | "
                          "Jours distincts attendus au hasard | 5e centile des jours distincts | Ratio jours observés / attendus | "
                          "Moins de jours actifs que le hasard | P50 de l'attente avant le passage (j) |",
        "starts_above_yes": "oui",
        "starts_above_no": "non",
        "starts_wait_note": "\nL'attente est le temps passé en « {waiting} » juste avant le passage. Les passages comptés "
                            "sont ceux des visites terminées, quelle que soit leur date, plusieurs par ticket en cas d'allers-retours.",
        "starts_expected_note": "Les deux mesures tirent les passages du projet au hasard, avec remise, sur les {days} jours "
                                "ouvrés (lundi au vendredi, jours fériés français retirés, hors Alsace-Moselle) du {start} au {end} ; "
                                "{draws} tirages, graine {seed}, chaque tirage ayant le même nombre de passages que le réel. "
                                "Concentration à jours actifs égaux : chaque tirage garde son propre nombre de jours distincts et "
                                "la règle des 20 % de jours les plus chargés (arrondis au-dessus) lui est appliquée ; « oui » si la "
                                "part observée dépasse strictement le 95e centile de ces parts. Comme elle suppose les jours actifs "
                                "donnés, elle ne voit pas un projet qui n'a que peu de jours actifs : un projet qui démarre en rafales "
                                "sort presque toujours « oui ». Jours actifs : le nombre de jours distincts observé est comparé à "
                                "celui des tirages (moyenne, 5e centile, rapport observé / attendu) sans rien lui imposer ; « oui » "
                                "si le nombre observé est strictement sous le 5e centile des tirages, c'est-à-dire moins de jours "
                                "actifs que le hasard n'en produit. Dans la population, {outside} passage(s) tombent un week-end, "
                                "un jour férié ou hors période : le modèle ne les connaît pas.",
        # arrêts
        "resolved_column_missing": "Colonne « Resolved » absente de l'export : ajoutez-la (voir flux_jira.py statuses).",
        "key_column_missing": "L'export n'a pas de colonne de clé, impossible de relier les tickets à leur historique.",
        "scope_no_ticket": "--scope : aucun ticket des projets demandés dans l'export.",
        "segment_not_computed": "--segment : « {segment} » n'est pas un segment calculé ({segments}).",
        "batch_threshold_invalid": "--exclude-batch-closures : batch_closure_threshold (flux.yaml) : un nombre entier d'au moins 2.",
        "starts_states_outside": "--starts : état(s) hors du segment « {segment} » : {states}.",
    },
    "en": {
        "origin_creation": "(creation)",
        "destination_resolved": "(resolved from the segment)",
        "no_project": "(no project)",
        "percent": "{value}%",
        "col_key": "Key",
        "col_project": "Project",
        "col_days_cumulative": "Cumulative days",
        "col_visits": "Visits",
        "col_entry_longest": "Entry (longest visit)",
        "col_exit": "Exit",
        "col_days_visit": "Days of this visit",
        "col_origin": "Origin",
        "col_destination": "Destination",
        "col_age_current": "Age of the current visit (d)",
        "col_entry": "Entry",
        "col_days_cumulative_previous": "Cumulative days (previous visits included)",
        "col_visits_current": "Visits (current one included)",
        "col_current_state": "Current status",
        "title": "# Sample of the segment \"{segment}\"",
        "period": "\nPeriod: {start} to {end} ({weeks} full weeks at most), computed on {today}.",
        "batch_discarded": "\nBatch closures discarded (--exclude-batch-closures): {tickets} tickets that left the segment, "
                           "{passages} moves from \"{waiting}\" to \"{start}\". Every figure below is computed without them.",
        "batch_no_time": "{count} delivered tickets without a resolution time: never counted as a batch.",
        "key_and_states_only": "Keys and statuses only; nothing is written to disk.",
        "states_header": "\n## Statuses of the segment ({setting})\n",
        "setting_custom": "\"segments\" setting of flux.yaml",
        "setting_default": "default of history_common.py",
        "other_segments": "\nOther segments, by number of statuses: {segments}.",
        "population": "\n## Population\n\n{count} tickets read after discarding, {without_history} without history in the cache.",
        "population_discarded": "\n## Population\n\n{count} tickets read after discarding ({discarded} discarded), "
                                "{without_history} without history in the cache.",
        "nothing_left": "\nNo ticket left the segment during the period: nothing to sample.",
        "left_summary": "\nTickets that left the segment during the period: {count}; cumulative time P50 {p50} d, "
                        "P85 {p85} d, mean {mean} d, maximum {max} d.",
        "visits_per_ticket": "Visits per ticket: 1 visit {one}, 2 visits or more {many}.",
        "longest_header": "\n## The {count} longest (cumulative time)\n",
        "near_median_header": "\n## {count} tickets near the median (random draw, seed {seed})\n",
        "near_median_window": "Window: from {low} to {high} d (P40 to P60); {candidates} candidates.\n",
        "near_median_shortage": "Warning: only {found} candidate(s) for {asked} requested.\n",
        "oldest_header": "\n## The {count} oldest still in the segment (out of {total})\n",
        "state_time_header": "\n## Time per status of the segment (population of {count} tickets that left)\n",
        "state_time_columns": "| Status | Tickets that went through the status | Total (d) | Share of segment time | P50 (d) | P85 (d) |",
        "state_time_total": "\nSegment total: {total} d (sum of the cumulative times). P50 and P85: days spent in the "
                            "status per ticket, summed over the visits, among the tickets that went through the status.",
        "group_longest": "longest",
        "group_near_median": "drawn near the median",
        "group_still_in": "still in the segment",
        "detail_header": "\n## Per-status detail of the sampled tickets\n",
        "detail_columns": "| Key | Group | Total (d) | {states} |",
        "detail_note": "\n\"-\": the ticket did not go through the status. For a ticket still in the segment, the total and "
                       "the detail include the current visit, up to the computation date.",
        "grouped_header": "\n## Grouped exits of the {count} longest\n",
        "grouped_columns": "| Key | Exit of the longest visit | Other tickets that left the segment that day |",
        "grouped_reference": "\nBenchmark: over the {days} days when at least one ticket of the population left the "
                             "segment, P50 {p50} and P85 {p85} exits per day, maximum {max} on {date}.",
        "starts_header": "\n## Moves from \"{waiting}\" to \"{start}\" by project\n",
        "starts_summary": "{passages} moves in the finished visits of the population, {tickets} tickets "
                          "concerned. Projects listed: at least {minimum} moves; {below} project(s) below the "
                          "threshold ({below_passages} moves) not listed.\n",
        "starts_none": "No project reaches the threshold.",
        "starts_columns": "| Project | Moves | Distinct days | Busiest days kept (20%) | "
                          "Share of moves on these days | Share expected at random (equal active days) | "
                          "95th percentile of the draws (equal active days) | More concentrated than chance at equal active days | "
                          "Distinct days expected at random | 5th percentile of the distinct days | Ratio observed / expected days | "
                          "Fewer active days than chance | P50 of the wait before the move (d) |",
        "starts_above_yes": "yes",
        "starts_above_no": "no",
        "starts_wait_note": "\nThe wait is the time spent in \"{waiting}\" just before the move. The moves counted "
                            "are those of finished visits, whatever their date, several per ticket when tickets go back and forth.",
        "starts_expected_note": "Both measures draw the project's moves at random, with replacement, over the {days} working days "
                                "(Monday to Friday, French public holidays removed, Alsace-Moselle excepted) from {start} to {end}; "
                                "{draws} draws, seed {seed}, each draw having the same number of moves as the real data. "
                                "Concentration at equal active days: each draw keeps its own number of distinct days and the rule "
                                "of the 20% busiest days (rounded up) is applied to it; \"yes\" if the observed share is strictly above "
                                "the 95th percentile of these shares. Because it takes the active days as given, it does not see a "
                                "project that has only few active days: a project that starts in bursts almost always comes out "
                                "\"yes\". Active days: the observed number of distinct days is compared with that of the draws "
                                "(mean, 5th percentile, observed / expected ratio) without imposing anything on it; \"yes\" if the "
                                "observed number is strictly below the 5th percentile of the draws, that is, fewer active days than "
                                "chance produces. In the population, {outside} move(s) fall on a weekend, a public holiday or "
                                "outside the period: the model does not know them.",
        "resolved_column_missing": "Column \"Resolved\" missing from the export: add it (see flux_jira.py statuses).",
        "key_column_missing": "The export has no key column, so tickets cannot be linked to their history.",
        "scope_no_ticket": "--scope: no ticket of the requested projects in the export.",
        "segment_not_computed": "--segment: \"{segment}\" is not a computed segment ({segments}).",
        "batch_threshold_invalid": "--exclude-batch-closures: batch_closure_threshold (flux.yaml): an integer of at least 2.",
        "starts_states_outside": "--starts: status(es) outside the segment \"{segment}\": {states}.",
    },
}
