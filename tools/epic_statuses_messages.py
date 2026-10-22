"""PMZilla Lab : messages de tools/epic_statuses.py par langue (change jira-gdpr-alignment, tâche 10).

Aucun message ne contient de clé de ticket, de titre, d'équipe, de personne, d'étiquette, de version ni de nom de fichier : seulement
des comptes (« masqué » / « masked » sous cinq, idée #417), des noms de statuts dans le rapport et des libellés fixes. Les phrases clés sont celles de la
décision D19 du change (design.md).
"""

CATALOGS = {
    "fr": {
        "report_written": "relevé des statuts des épics écrit",
        "no_epic": "aucun épic trouvé",
        "refused_session": "Refusé dans une session Claude Code",
        "epics_line": "épics : {n}",
        "statuses_line": "statuts : {n}",
        "u_language": "langue inconnue (fr ou en)",
        "u_option": "option inconnue ou invalide",
        "export_unreadable": "réglages illisibles",
        "export_files_retired": "les fichiers d'export ne sont plus lus : la base est la seule source",
        "history_path_retired": "--history ne prend aucun fichier : l'historique est lu dans la base",
        "no_history_in_db": "aucun historique dans la base : lancez d'abord la collecte de l'historique",
        "report_title": "Statuts des épics au {date}",
        "report_intro": "Comptes par statut, tirés de la base (tickets et historique). Tout compte inférieur à cinq est écrit « masqué ».",
        "cell_masked": "masqué",
        "report_epics": "Épics lus : {n}",
        "history_absent": "Historique absent : passages et transitions non observés.",
        "col_status": "Statut",
        "col_current": "Épics actuellement",
        "col_passages": "Passages observés",
        "col_outgoing": "Transitions sortantes les plus fréquentes",
        "none_cell": "-",
        "mapping_not_validated": "Correspondance non validée : aucune date de validation dans discovery_workflow, rien n'est calculé "
                                 "sur elle.",
        "mapped_not_observed": "Mappés mais non observés",
        "mapped_not_observed_none": "Aucun statut mappé n'est absent des statuts observés.",
    },
    "en": {
        "report_written": "epic statuses report written",
        "no_epic": "no epic found",
        "refused_session": "Refused inside a Claude Code session",
        "epics_line": "epics: {n}",
        "statuses_line": "statuses: {n}",
        "u_language": "unknown language (fr or en)",
        "u_option": "unknown or invalid option",
        "export_unreadable": "settings unreadable",
        "export_files_retired": "export files are no longer read: the database is the only source",
        "history_path_retired": "--history takes no file: the history is read from the database",
        "no_history_in_db": "no history in the database: run the history collection first",
        "report_title": "Epic statuses on {date}",
        "report_intro": "Counts per status, taken from the database (tickets and history). Every count below five is written \"masked\".",
        "cell_masked": "masked",
        "report_epics": "Epics read: {n}",
        "history_absent": "History absent: passages and transitions not observed.",
        "col_status": "Status",
        "col_current": "Epics currently",
        "col_passages": "Passages observed",
        "col_outgoing": "Most frequent outgoing transitions",
        "none_cell": "-",
        "mapping_not_validated": "Mapping not validated: no validation date in discovery_workflow, nothing is computed on it.",
        "mapped_not_observed": "Mapped but not observed",
        "mapped_not_observed_none": "No mapped status is absent from the observed statuses.",
    },
}
