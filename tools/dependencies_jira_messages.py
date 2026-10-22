"""PMZilla Lab : catalogue des messages de dependencies_jira.py, en français (référence) et en anglais (lot 3, étape 2).

Le français est exactement ce que le script écrivait avant le catalogue. Les champs `{nom}` sont remplis par
`Messages.__call__` (tools/messages.py). Les clés `swap_N_from` / `swap_N_to` sont les paires de mots que le rapport
« par projet » remplace dans son texte (« équipe » devient « projet »), appliquées dans l'ordre.
"""
from __future__ import annotations

FR = {
    # ---- console : diagnose
    "refused_session": "Refusé dans une session Claude Code",
    "source_retired": "--source est retirée : la base est la seule source",
    "export_files_retired": "les fichiers d'export ne sont plus lus : la base est la seule source",
    "db_unreachable": "Base de données : lecture impossible. {detail}",
    "source_name": "base",
    "tickets_read": "Tickets lus : {n}",
    "recognized_columns": "Colonnes reconnues :",
    "column_missing": "absente",
    "col_cle": "cle", "col_type": "type", "col_etat": "etat", "col_categorie": "categorie", "col_cree": "cree",
    "col_resolu": "resolu", "col_motif": "motif", "col_debut": "debut", "col_equipe": "equipe", "col_parent": "parent",
    "typed_link_columns": "Colonnes de liens typées : {n} ({types} types)",
    "untyped_link_columns": "Colonnes de liens sans type : {names}",
    "no_link_columns": "Aucune colonne de liens : ajoutez « Tickets liés » à la vue Jira et exportez à nouveau.",
    "links_by_type": "Liens par type :",
    "no_type": "(sans type)",
    "flag_no_type": "sans type",
    "flag_blocks": "dépendance (sortant = bloque)",
    "flag_depends": "dépendance (sortant = dépend de)",
    "flag_ignored": "ignoré",
    "decomposition_links": "Liens de décomposition ({type} vers un autre niveau) : {n}, comptés à part",
    "scope_line": "Périmètre : {projects} ({n} tickets ; les autres servent à situer l'autre côté des liens)",
    "exclusion_line": "Projets exclus de la carte : {n} (source : {source})",
    "exclusion_none": "aucun",
    "exclusion_src_option": "option --exclude",
    "exclusion_src_map": "réglage dependency_excluded_projects",
    "exclusion_src_shared": "réglage excluded_projects, commun avec le rapport de flux",
    "exit_empty_exclusion": "--exclude : aucune clé de projet ; donner des clés séparées par des virgules, ou « aucun »",
    "excluded_project_links": "Liens avec le projet exclu {project} : {n} ({side}), comptés à part",
    "mode_line": "Mode : {mode} · dépendances distinctes : {n} · vers un ticket absent de l'export : {outside}",
    "mode_oriented": "orienté",
    "mode_unoriented": "non orienté",
    "mode_none": "aucun",
    "side_awaited_by_export": "attendu par l'export",
    "side_waits_for_export": "attend l'export",
    "side_internal": "interne",
    "export_awaits_it": "l'export l'attend",
    "it_awaits_export": "il attend l'export",
    "unknown_projects": "Projets des tickets liés absents de l'export (Terminal seulement) :",
    "project_in_export": "  (projet déjà dans l'export : tickets filtrés par la requête)",
    "over_30_console": "Plus de 30 % des liens sortent de l'export : élargissez la requête JQL aux projets liés, "
                       "sinon l'équipe de l'autre côté reste inconnue.",
    "unknown_states": "États non terminés ni « en cours » ni « à faire » ({n} tickets) : {states}",
    "hint_status_category": "  Ajoutez la colonne « Status Category » à la vue Jira : elle classe les états de tous les workflows.",
    "tickets_without_team": "Tickets sans équipe : {n}",
    # ---- console : compute et erreurs
    "exit_no_links": "Aucune colonne de liens dans l'export : lancez d'abord la commande diagnose.",
    "report_line": "Rapport : {path}",
    "old_epics_jira": "\nEpics anciens non vivants ({n}). Requête Jira pour voir tous leurs enfants, "
                      "terminés compris, triés par dernière mise à jour (Terminal seulement) :",
    "blockages_terminal_header": "\nBlocages en cours (Terminal seulement, rien n'est écrit) :",
    "blockage_terminal_line": "  {blocked} ({blocked_team}) attend {blocking} ({blocking_team}, {state}) depuis {age} j",
    # ---- noms affichés (les valeurs du JSON restent en français)
    "team_outside_export": "(hors export)",
    "team_without_team": "(sans équipe)",
    "team_without_team_project": "(sans équipe : {project})",
    "state_outside_export": "hors export",
    "state_not_started": "pas commencé",
    "state_in_progress": "en cours",
    "days_value": "{v} j",
    "none_word": "aucun",
    # ---- rapport Markdown
    "title": "# Dépendances : {name}, {date}",
    "summary": "Export : {export} · {tickets} tickets · {deps} dépendances distinctes ({kind}) · "
               "{outside} vers un ticket absent de l'export.",
    "kind_oriented": "liens de blocage, orientés",
    "kind_unoriented": "liens sans type, non orientés",
    "note_untyped": "> Les liens n'ont pas de type : impossible de distinguer un blocage d'une simple relation, "
                    "ni de dire qui attend qui. Les chiffres comptent des liens, pas des blocages. Pour des blocages, "
                    "il faut des colonnes de liens typées (« Inward/Outward issue link (Blocks) »).",
    "note_decomposition": "> Liens de décomposition ({type} relié à un ticket d'un autre niveau) : {n}, hors de la carte "
                          "(réglage portfolio_types). Les liens entre deux tickets de ce niveau restent dans la carte.",
    "note_excluded": "> Liens avec le projet exclu {project} : {n} ({side}), hors de la carte (réglage excluded_projects).",
    "note_outside": "> Plus de 30 % des liens pointent hors de l'export : l'équipe de l'autre côté est inconnue "
                    "(« hors export »). Élargir la requête JQL rendrait la carte plus complète.",
    "sec_brief": "## En bref",
    "brief_open": "- Dépendances ouvertes entre équipes : {n}, réparties sur {pairs} paires "
                  "d'équipes ({tickets} tickets dans le périmètre). Les deux côtés sont "
                  "dans l'export et non terminés.",
    "brief_unknown": "- Dépendances à état inconnu : {n} (l'élément attendu est absent de l'export, "
                     "peut-être déjà terminé). Comptées à part, jamais comme ouvertes.",
    "brief_busiest_oriented": "- Paire la plus chargée : {a} attend {b} ({n} ouvertes, {part} % du total).",
    "brief_busiest_unoriented": "- Paire la plus chargée : {a} et {b} ({n} liens ouverts, {part} % du total).",
    "brief_waiting": "- Éléments en cours qui attendent une autre équipe : {n}.",
    "brief_waiting_old": "- Éléments en cours qui attendent une autre équipe : {n}, plus {old} en cours depuis "
                         "plus d'un an (voir « Blocages anciens »).",
    "brief_loops": "- Boucles entre équipes : {n} (voir « Boucles »).",
    "sec_who": "## Qui dépend de qui",
    "who_reading_oriented": "Lecture : la ligne attend la colonne. « Ouvertes » : les deux éléments sont dans l'export et non "
                            "terminés. « dont entre Epics » : part des ouvertes où les deux éléments sont de niveau portefeuille "
                            "(réglage portfolio_types) ; leur âge mesure la vie d'une épopée, pas une attente de travail. "
                            "« État inconnu » : l'élément attendu est absent de l'export, le dépendant n'est pas terminé. "
                            "« Toutes » : tous les liens, terminés compris.",
    "who_reading_unoriented": "Liens entre équipes dont au moins un côté n'est pas terminé (colonne « Tous » : terminés compris).",
    "head_matrix_oriented": "| Équipe qui attend | Équipe attendue | Ouvertes | dont entre Epics | État inconnu | Toutes |",
    "head_matrix_unoriented": "| Équipe | Équipe | Ouvertes | dont entre Epics | État inconnu | Toutes |",
    "no_externals": "Aucune dépendance entre équipes dans l'export.",
    "internal_dependencies": "Dépendances internes à une même équipe : {n} (non détaillées).",
    "sec_graph": "## Graphe des dépendances ouvertes",
    "graph_legend_oriented": "Flèche : de l'équipe attendue vers l'équipe qui attend ; étiquette : dépendances ouvertes.",
    "graph_legend_unoriented": "Trait : liens ouverts entre deux équipes.",
    "sec_loops": "## Boucles",
    "loops_intro": "Équipes qui s'attendent mutuellement, directement ou par une chaîne (dépendances ouvertes) :",
    "loop_joiner": " attend ",
    "loops_closing": "Une boucle signale souvent un découpage du travail qui coupe un même flux de valeur entre plusieurs "
                     "équipes : une question de frontières d'équipe plus que de coordination.",
    "sec_blockages": "## Blocages en cours",
    "blockages_intro": "Éléments en cours qui attendent un élément non terminé d'une autre équipe. "
                       "Âge : depuis l'entrée en cours (ou la création à défaut).",
    "head_blockages": "| Équipe qui attend | Équipe attendue | État de l'élément attendu | Éléments | dont Epics "
                      "| Âge P50 | Âge P85 | Même date d'entrée |",
    "same_date_flag": "{same} sur {n}",
    "pair_waits": "{a} attend {b}",
    "blockages_note": "Un élément attendu « pas commencé » alors que le dépendant est en cours est le cas le plus "
                      "coûteux : le travail a démarré avant que sa condition soit planifiée.",
    "batch_warning": "Âges à vérifier avant toute lecture : dans {groups}, la plupart des éléments "
                     "sont entrés en cours le même jour. C'est le signe probable d'un changement de statut groupé "
                     "(planification, migration), pas d'un démarrage réel : l'âge peut alors surestimer l'attente.",
    "none_waiting": "Aucun élément en cours n'attend une autre équipe.",
    "sec_unknown_waits": "### Attentes vers un élément hors export",
    "unknown_waits_intro": "Éléments en cours dont l'élément attendu est absent de l'export : impossible de savoir s'il est "
                           "terminé. À vérifier dans Jira avant d'y voir un blocage. Projet Jira de l'élément attendu.",
    "head_unknown_waits": "| Équipe qui attend | Projet attendu | Éléments | Âge P50 | Âge P85 |",
    "sec_old_epics": "### Epics anciens : vivants ou abandonnés ?",
    "old_epics_intro": "Epics ouverts depuis plus de {old} jours et pris dans un lien ouvert entre équipes. "
                       "« Vivant » : un de leurs enfants a changé d'état (s'il est ouvert) ou a été livré dans les {window} "
                       "derniers jours ; une clôture par rejet ou annulation ne compte pas (c'est souvent un nettoyage). « Enfants inactifs » : des enfants existent mais n'ont pas bougé depuis. "
                       "« Sans enfant de livraison » : aucun enfant visible dans l'export, ou seulement des enfants de niveau "
                       "portefeuille (RN Task) ; une RN Task ou une clôture par rejet ne compte pas comme livraison (l'export "
                       "ne garde que les tickets ouverts ou résolus récemment). Les liens d'un Epic qui n'est pas vivant "
                       "décrivent probablement un plan "
                       "abandonné plutôt qu'une attente.",
    "old_epics_total": "Total : {alive} vivants, {inactive} aux enfants inactifs, {none} sans enfant de livraison.",
    "head_old_epics": "| Équipe | Vivants | Enfants inactifs | Sans enfant de livraison |",
    "sec_old_blockages": "### Blocages anciens",
    "old_blockages_intro": "En cours depuis plus de {old} jours : probablement des tickets abandonnés ou mal clos, "
                           "à nettoyer plutôt qu'à débloquer. Exclus du tableau précédent.",
    "head_old_blockages": "| Équipe qui attend | Équipe attendue | Éléments | Le plus ancien |",
    "sec_lead_time": "## Effet sur le lead time ({weeks} dernières semaines)",
    "lead_time_intro": "Comparaison à type de ticket égal. Dépendance externe : l'élément attendait un élément d'une autre "
                       "équipe connue (ni hors export, ni sans équipe). Lead time compté depuis la création, attente en "
                       "backlog comprise. Un type n'apparaît que s'il compte au moins {min} éléments de chaque côté.",
    "head_lead_time": "| Type | Avec dépendance : nombre | P50 | P85 | Sans : nombre | P50 | P85 |",
    "lead_time_correlation": "Corrélation, pas causalité : les éléments avec dépendance sont souvent aussi plus gros ou plus "
                             "incertains. L'écart est une question à poser aux équipes, pas une mesure du coût des dépendances.",
    "lead_time_fragile": " P85 fragile pour : {types} (moins de 30 éléments avec dépendance).",
    "lead_time_none": "Aucun type n'a assez d'éléments des deux côtés pour comparer (avec/sans : {sizes}).",
    # ---- version par projet : mots remplacés dans le texte, dans l'ordre
    "swap_1_from": "à une même équipe", "swap_1_to": "à un même projet",
    "swap_2_from": "d'une autre équipe connue (ni hors export, ni sans équipe)", "swap_2_to": "d'un autre projet",
    "swap_3_from": "Équipes qui s'attendent", "swap_3_to": "Projets qui s'attendent",
    "swap_4_from": "Équipe qui attend", "swap_4_to": "Projet qui attend",
    "swap_5_from": "Équipe attendue", "swap_5_to": "Projet attendu",
    "swap_6_from": "| Équipe | Équipe |", "swap_6_to": "| Projet | Projet |",
    "swap_7_from": "entre équipes", "swap_7_to": "entre projets",
    "swap_8_from": "paires d'équipes", "swap_8_to": "paires de projets",
    "swap_9_from": "une autre équipe", "swap_9_to": "un autre projet",
    "swap_10_from": "même équipe", "swap_10_to": "même projet",
    "swap_11_from": "de l'équipe attendue vers l'équipe qui attend", "swap_11_to": "du projet attendu vers le projet qui attend",
    # ---- rapport par Mission Team ou par site (groupes d'après le référentiel d'organisation)
    "blockage_terminal_line_group": "  {blocked} attend {blocking} ({state}) depuis {age} j",
    "internal_dependencies_group": "Dépendances internes à un même groupe : {n} (le détail par groupe est dans « Tickets et "
                                   "dépendances internes »).",
    "kind_mission_team": "Mission Team",
    "kind_site": "site",
    "group_intro": "Rapport par {kind} : les équipes de l'export sont regroupées d'après le référentiel d'organisation. Les équipes "
                   "que le référentiel ne décrit pas forment le groupe « hors référentiel ». Matrices, blocages et graphe sont "
                   "entre groupes ; les totaux sont ceux du rapport par équipe.",
    "sec_structure": "## Structure",
    "structure_note": "Les effectifs décrivent la structure seulement : aucun chiffre de ce rapport n'est rapporté à un effectif, "
                      "et les groupes sont classés par nom, jamais par un chiffre.",
    "head_structure": "| Groupe ({kind}) | Équipes | Effectif |",
    "sec_group_counts": "## Tickets et dépendances internes",
    "group_internal_intro": "Une dépendance entre deux équipes d'un même groupe ({kind}) est interne au groupe : elle est comptée "
                            "ici et ne figure pas parmi les paires du tableau « Qui dépend de qui ». Le groupe « hors référentiel » "
                            "rassemble les équipes que le référentiel ne décrit pas ; son nombre de tickets est dans ce tableau.",
    "head_group_counts": "| Groupe | Tickets | Dépendances internes |",
    "swap_mt_1_to": "à une même Mission Team",
    "swap_mt_2_to": "d'une autre Mission Team connue (ni hors export, ni sans équipe)",
    "swap_mt_3_to": "Mission Teams qui s'attendent",
    "swap_mt_4_to": "Mission Team qui attend",
    "swap_mt_5_to": "Mission Team attendue",
    "swap_mt_6_to": "| Mission Team | Mission Team |",
    "swap_mt_7_to": "entre Mission Teams",
    "swap_mt_8_to": "paires de Mission Teams",
    "swap_mt_9_to": "une autre Mission Team",
    "swap_mt_10_to": "même Mission Team",
    "swap_mt_11_to": "de la Mission Team attendue vers la Mission Team qui attend",
    "swap_site_1_to": "à un même site",
    "swap_site_2_to": "d'un autre site connu (ni hors export, ni sans équipe)",
    "swap_site_3_to": "Sites qui s'attendent",
    "swap_site_4_to": "Site qui attend",
    "swap_site_5_to": "Site attendu",
    "swap_site_6_to": "| Site | Site |",
    "swap_site_7_to": "entre sites",
    "swap_site_8_to": "paires de sites",
    "swap_site_9_to": "un autre site",
    "swap_site_10_to": "même site",
    "swap_site_11_to": "du site attendu vers le site qui attend",
}

EN = {
    # ---- console : diagnose
    "refused_session": "Refused inside a Claude Code session",
    "source_retired": "--source is retired: the database is the only source",
    "export_files_retired": "export files are no longer read: the database is the only source",
    "db_unreachable": "Database: cannot read. {detail}",
    "source_name": "database",
    "tickets_read": "Tickets read: {n}",
    "recognized_columns": "Recognized columns:",
    "column_missing": "missing",
    "col_cle": "key", "col_type": "type", "col_etat": "status", "col_categorie": "category", "col_cree": "created",
    "col_resolu": "resolved", "col_motif": "resolution", "col_debut": "category_changed", "col_equipe": "team",
    "col_parent": "parent",
    "typed_link_columns": "Typed link columns: {n} ({types} types)",
    "untyped_link_columns": "Untyped link columns: {names}",
    "no_link_columns": "No link columns: add \"Linked Issues\" to the Jira view and export again.",
    "links_by_type": "Links by type:",
    "no_type": "(no type)",
    "flag_no_type": "no type",
    "flag_blocks": "dependency (outward = blocks)",
    "flag_depends": "dependency (outward = depends on)",
    "flag_ignored": "ignored",
    "decomposition_links": "Decomposition links ({type} to another level): {n}, counted separately",
    "scope_line": "Scope: {projects} ({n} tickets; the others are used to locate the other side of the links)",
    "exclusion_line": "Projects excluded from the map: {n} (source: {source})",
    "exclusion_none": "none",
    "exclusion_src_option": "option --exclude",
    "exclusion_src_map": "setting dependency_excluded_projects",
    "exclusion_src_shared": "setting excluded_projects, shared with the flow report",
    "exit_empty_exclusion": '--exclude: no project key; give comma-separated keys, or "none"',
    "excluded_project_links": "Links with excluded project {project}: {n} ({side}), counted separately",
    "mode_line": "Mode: {mode} · distinct dependencies: {n} · to a ticket missing from the export: {outside}",
    "mode_oriented": "oriented",
    "mode_unoriented": "not oriented",
    "mode_none": "none",
    "side_awaited_by_export": "awaited by the export",
    "side_waits_for_export": "waits for the export",
    "side_internal": "internal",
    "export_awaits_it": "the export waits for it",
    "it_awaits_export": "it waits for the export",
    "unknown_projects": "Projects of linked tickets missing from the export (terminal only):",
    "project_in_export": "  (project already in the export: tickets filtered out by the query)",
    "over_30_console": "More than 30% of the links point outside the export: widen the JQL query to the linked projects, "
                       "otherwise the team on the other side stays unknown.",
    "unknown_states": "States that are neither finished, \"in progress\" nor \"to do\" ({n} tickets): {states}",
    "hint_status_category": "  Add the \"Status Category\" column to the Jira view: it classifies the states of all workflows.",
    "tickets_without_team": "Tickets without a team: {n}",
    # ---- console : compute and errors
    "exit_no_links": "No link columns in the export: run the diagnose command first.",
    "report_line": "Report: {path}",
    "old_epics_jira": "\nOld Epics that are not alive ({n}). Jira query to see all their children, "
                      "finished ones included, sorted by last update (terminal only):",
    "blockages_terminal_header": "\nCurrent blockages (terminal only, nothing is written):",
    "blockage_terminal_line": "  {blocked} ({blocked_team}) waits for {blocking} ({blocking_team}, {state}) for {age} d",
    # ---- displayed names (JSON values stay in French)
    "team_outside_export": "(outside export)",
    "team_without_team": "(no team)",
    "team_without_team_project": "(no team: {project})",
    "state_outside_export": "outside export",
    "state_not_started": "not started",
    "state_in_progress": "in progress",
    "days_value": "{v} d",
    "none_word": "none",
    # ---- Markdown report
    "title": "# Dependencies: {name}, {date}",
    "summary": "Export: {export} · {tickets} tickets · {deps} distinct dependencies ({kind}) · "
               "{outside} to a ticket missing from the export.",
    "kind_oriented": "blocking links, oriented",
    "kind_unoriented": "untyped links, not oriented",
    "note_untyped": "> The links have no type: it is impossible to tell a blockage from a simple relation, "
                    "or who waits for whom. The figures count links, not blockages. For blockages, "
                    "typed link columns are needed (\"Inward/Outward issue link (Blocks)\").",
    "note_decomposition": "> Decomposition links ({type} linked to a ticket of another level): {n}, left out of the map "
                          "(setting portfolio_types). Links between two tickets of this level stay in the map.",
    "note_excluded": "> Links with excluded project {project}: {n} ({side}), left out of the map (setting excluded_projects).",
    "note_outside": "> More than 30% of the links point outside the export: the team on the other side is unknown "
                    "(\"outside export\"). Widening the JQL query would make the map more complete.",
    "sec_brief": "## In brief",
    "brief_open": "- Open dependencies between teams: {n}, spread over {pairs} pairs "
                  "of teams ({tickets} tickets in scope). Both sides are "
                  "in the export and not finished.",
    "brief_unknown": "- Dependencies with unknown state: {n} (the awaited item is missing from the export, "
                     "possibly already finished). Counted separately, never as open.",
    "brief_busiest_oriented": "- Busiest pair: {a} waits for {b} ({n} open, {part}% of the total).",
    "brief_busiest_unoriented": "- Busiest pair: {a} and {b} ({n} open links, {part}% of the total).",
    "brief_waiting": "- Items in progress that wait for another team: {n}.",
    "brief_waiting_old": "- Items in progress that wait for another team: {n}, plus {old} in progress for "
                         "more than a year (see \"Old blockages\").",
    "brief_loops": "- Loops between teams: {n} (see \"Loops\").",
    "sec_who": "## Who depends on whom",
    "who_reading_oriented": "Reading: the row waits for the column. \"Open\": both items are in the export and not "
                            "finished. \"of which between Epics\": share of the open ones where both items are portfolio-level "
                            "(setting portfolio_types); their age measures the life of an Epic, not a wait for work. "
                            "\"Unknown state\": the awaited item is missing from the export, the dependent one is not finished. "
                            "\"All\": all links, finished ones included.",
    "who_reading_unoriented": "Links between teams where at least one side is not finished (column \"All\": finished ones included).",
    "head_matrix_oriented": "| Waiting team | Awaited team | Open | of which between Epics | Unknown state | All |",
    "head_matrix_unoriented": "| Team | Team | Open | of which between Epics | Unknown state | All |",
    "no_externals": "No dependencies between teams in the export.",
    "internal_dependencies": "Dependencies within a single team: {n} (not detailed).",
    "sec_graph": "## Graph of open dependencies",
    "graph_legend_oriented": "Arrow: from the awaited team to the waiting team; label: open dependencies.",
    "graph_legend_unoriented": "Line: open links between two teams.",
    "sec_loops": "## Loops",
    "loops_intro": "Teams that wait on each other, directly or through a chain (open dependencies):",
    "loop_joiner": " waits for ",
    "loops_closing": "A loop often signals a split of the work that cuts a single value stream across several "
                     "teams: more a question of team boundaries than of coordination.",
    "sec_blockages": "## Current blockages",
    "blockages_intro": "Items in progress that wait for an unfinished item of another team. "
                       "Age: since entering in progress (or since creation if none).",
    "head_blockages": "| Waiting team | Awaited team | State of the awaited item | Items | of which Epics "
                      "| Age P50 | Age P85 | Same entry date |",
    "same_date_flag": "{same} of {n}",
    "pair_waits": "{a} waits for {b}",
    "blockages_note": "An awaited item that is \"not started\" while the dependent one is in progress is the most "
                      "costly case: the work started before its condition was planned.",
    "batch_warning": "Ages to check before reading anything: in {groups}, most of the items "
                     "entered in progress on the same day. This is probably the sign of a bulk status change "
                     "(planning, migration), not of a real start: the age may then overestimate the wait.",
    "none_waiting": "No item in progress waits for another team.",
    "sec_unknown_waits": "### Waits on an item outside the export",
    "unknown_waits_intro": "Items in progress whose awaited item is missing from the export: it is impossible to know whether it is "
                           "finished. Check in Jira before seeing a blockage in it. Jira project of the awaited item.",
    "head_unknown_waits": "| Waiting team | Awaited project | Items | Age P50 | Age P85 |",
    "sec_old_epics": "### Old Epics: alive or abandoned?",
    "old_epics_intro": "Epics open for more than {old} days and caught in an open link between teams. "
                       "\"Alive\": one of their children changed state (if open) or was delivered in the last {window} "
                       "days; a closure by rejection or cancellation does not count (it is often a clean-up). \"Inactive children\": children exist but have not moved since. "
                       "\"No delivery child\": no child visible in the export, or only portfolio-level children "
                       "(RN Task); an RN Task or a closure by rejection does not count as a delivery (the export "
                       "keeps only open or recently resolved tickets). The links of an Epic that is not alive "
                       "probably describe an abandoned plan "
                       "rather than a wait.",
    "old_epics_total": "Total: {alive} alive, {inactive} with inactive children, {none} with no delivery child.",
    "head_old_epics": "| Team | Alive | Inactive children | No delivery child |",
    "sec_old_blockages": "### Old blockages",
    "old_blockages_intro": "In progress for more than {old} days: probably abandoned or badly closed tickets, "
                           "to clean up rather than unblock. Excluded from the previous table.",
    "head_old_blockages": "| Waiting team | Awaited team | Items | Oldest |",
    "sec_lead_time": "## Effect on lead time (last {weeks} weeks)",
    "lead_time_intro": "Comparison at equal ticket type. External dependency: the item was waiting on an item "
                       "of another known team (neither outside the export nor without a team). Lead time counted from creation, "
                       "backlog wait included. A type appears only if it has at least {min} items on each side.",
    "head_lead_time": "| Type | With dependency: count | P50 | P85 | Without: count | P50 | P85 |",
    "lead_time_correlation": "Correlation, not causation: items with a dependency are often also bigger or more "
                             "uncertain. The gap is a question to ask the teams, not a measure of the cost of dependencies.",
    "lead_time_fragile": " P85 is fragile for: {types} (fewer than 30 items with a dependency).",
    "lead_time_none": "No type has enough items on both sides to compare (with/without: {sizes}).",
    # ---- by-project version: words replaced in the text, in order
    "swap_1_from": "within a single team", "swap_1_to": "within a single project",
    "swap_2_from": "of another known team (neither outside the export nor without a team)", "swap_2_to": "of another project",
    "swap_3_from": "Teams that wait on each other", "swap_3_to": "Projects that wait on each other",
    "swap_4_from": "Waiting team", "swap_4_to": "Waiting project",
    "swap_5_from": "Awaited team", "swap_5_to": "Awaited project",
    "swap_6_from": "| Team | Team |", "swap_6_to": "| Project | Project |",
    "swap_7_from": "between teams", "swap_7_to": "between projects",
    "swap_8_from": "pairs of teams", "swap_8_to": "pairs of projects",
    "swap_9_from": "another team", "swap_9_to": "another project",
    "swap_10_from": "same team", "swap_10_to": "same project",
    "swap_11_from": "from the awaited team to the waiting team", "swap_11_to": "from the awaited project to the waiting project",
    # ---- report by Mission Team or by site (groups from the organisation referential)
    "blockage_terminal_line_group": "  {blocked} waits for {blocking} ({state}) for {age} d",
    "internal_dependencies_group": "Dependencies within a single group: {n} (the detail per group is in \"Tickets and internal "
                                   "dependencies\").",
    "kind_mission_team": "Mission Team",
    "kind_site": "site",
    "group_intro": "Report by {kind}: the teams of the export are grouped through the organisation referential. Teams the "
                   "referential does not describe form the \"outside the referential\" group. Matrices, blockages and graph are "
                   "between groups; the totals are those of the report by team.",
    "sec_structure": "## Structure",
    "structure_note": "Headcounts describe the structure only: no figure of this report is divided by a headcount, and groups "
                      "are ordered by name, never by a figure.",
    "head_structure": "| Group ({kind}) | Teams | Headcount |",
    "sec_group_counts": "## Tickets and internal dependencies",
    "group_internal_intro": "A dependency between two teams of the same group ({kind}) is internal to the group: it is counted "
                            "here and does not appear among the pairs of the \"Who depends on whom\" table. The \"outside the "
                            "referential\" group gathers the teams the referential does not describe; its ticket count is in "
                            "this table.",
    "head_group_counts": "| Group | Tickets | Internal dependencies |",
    "swap_mt_1_to": "within a single Mission Team",
    "swap_mt_2_to": "of another known Mission Team (neither outside the export nor without a team)",
    "swap_mt_3_to": "Mission Teams that wait on each other",
    "swap_mt_4_to": "Waiting Mission Team",
    "swap_mt_5_to": "Awaited Mission Team",
    "swap_mt_6_to": "| Mission Team | Mission Team |",
    "swap_mt_7_to": "between Mission Teams",
    "swap_mt_8_to": "pairs of Mission Teams",
    "swap_mt_9_to": "another Mission Team",
    "swap_mt_10_to": "same Mission Team",
    "swap_mt_11_to": "from the awaited Mission Team to the waiting Mission Team",
    "swap_site_1_to": "within a single site",
    "swap_site_2_to": "of another known site (neither outside the export nor without a team)",
    "swap_site_3_to": "Sites that wait on each other",
    "swap_site_4_to": "Waiting site",
    "swap_site_5_to": "Awaited site",
    "swap_site_6_to": "| Site | Site |",
    "swap_site_7_to": "between sites",
    "swap_site_8_to": "pairs of sites",
    "swap_site_9_to": "another site",
    "swap_site_10_to": "same site",
    "swap_site_11_to": "from the awaited site to the waiting site",
}

CATALOGS = {"fr": FR, "en": EN}
