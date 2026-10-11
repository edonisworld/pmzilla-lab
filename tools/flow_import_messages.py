"""PMZilla Lab : messages de tools/flow_import.py par langue (lot 6, import de Jira en base).

Aucun message ne contient de clé de ticket, de nom d'équipe ni de valeur de champ : seulement des effectifs, des noms de
fichiers et des noms de colonnes de l'export. Les erreurs de la base (db.ErreurBase) sont affichées telles quelles, sans
être passées par ce catalogue.
"""

CATALOGS = {
    "fr": {
        "dry_run_notice": "Essai à blanc (--dry-run) : comptes calculés dans la base, rien n'est écrit.",
        "tickets_summary": "Tickets lus : {read} ; insérés : {inserted} ; mis à jour : {updated} ; inchangés : {unchanged} ; "
                           "écartés illisibles : {unreadable}.",
        "teams_links_summary": "Équipes créées : {teams} ; liens ajoutés : {links_added} ; liens retirés : {links_removed}.",
        "transitions_summary": "Transitions ajoutées : {added} ; ignorées sans ticket : {orphans} ; illisibles : {unreadable}.",
        "history_marked": "Tickets marqués « avec historique » (une entrée du cache, avec ou sans transition) : {marked} nouveau(x).",
        "no_history_notice": "Sans --history : aucune transition importée.",
        "column_missing": "{file} : colonne {column} absente de l'export (voir les noms de colonnes de flux.yaml). "
                          "Seuls les CSV de export_jira_api.py sont lus (uv run tools/export_jira_api.py export). Rien n'a été écrit.",
        "updated_unreadable": "{file} : la colonne {column} contient une valeur vide ou illisible. Rien n'a été écrit.",
        "file_unreadable": "{file} : fichier illisible.",
        "file_empty": "{file} : fichier vide.",
        "timezone_unknown": "export_timezone de flux.yaml : fuseau horaire inconnu.",
        "cache_missing": "--history : cache introuvable ({path}). Lance d'abord tools/history_jira.py collect.",
        "cache_unreadable": "--history : cache illisible.",
        "unexpected_error": "Erreur inattendue ({name}) : rien n'a été écrit.",
    },
    "en": {
        "dry_run_notice": "Dry run (--dry-run): counts computed in the database, nothing is written.",
        "tickets_summary": "Tickets read: {read}; inserted: {inserted}; updated: {updated}; unchanged: {unchanged}; "
                           "discarded as unreadable: {unreadable}.",
        "teams_links_summary": "Teams created: {teams}; links added: {links_added}; links removed: {links_removed}.",
        "transitions_summary": "Transitions added: {added}; ignored without ticket: {orphans}; unreadable: {unreadable}.",
        "history_marked": "Tickets marked \"with history\" (a cache entry, with or without a transition): {marked} new.",
        "no_history_notice": "Without --history: no transitions imported.",
        "column_missing": "{file}: column {column} is missing from the export (see the column names in flux.yaml). "
                          "Only the CSV files of export_jira_api.py are read (uv run tools/export_jira_api.py export). Nothing was written.",
        "updated_unreadable": "{file}: column {column} holds an empty or unreadable value. Nothing was written.",
        "file_unreadable": "{file}: file unreadable.",
        "file_empty": "{file}: file is empty.",
        "timezone_unknown": "export_timezone in flux.yaml: unknown time zone.",
        "cache_missing": "--history: cache not found ({path}). Run tools/history_jira.py collect first.",
        "cache_unreadable": "--history: cache unreadable.",
        "unexpected_error": "Unexpected error ({name}): nothing was written.",
    },
}
