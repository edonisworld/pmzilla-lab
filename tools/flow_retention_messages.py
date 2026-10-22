"""PMZilla Lab : messages de tools/flow_retention.py par langue (change jira-gdpr-alignment, groupe 11).

Aucun message ne contient de clé de ticket, d'équipe, de nom de fichier, d'étiquette, de version ni de valeur de réglage :
seulement des noms de magasins, des effectifs, des âges en jours et les phrases clés de la décision D19 du change (design.md).
"""

CATALOGS = {
    "fr": {
        # phrases clés de D19
        "check_clean": "contrôle de conservation : rien hors règle",
        "check_found": "contrôle de conservation : {n} éléments hors règle",
        "dry_run": "essai : rien n'est supprimé",
        "purge_done": "purge faite",
        "backup_missing": "sauvegarde avant purge absente : lancer d'abord la sauvegarde étiquetée",
        "session": "Refusé dans une session Claude Code",
        # lignes par magasin
        "store_database": "base, tickets au-delà de la règle : {n}",
        "store_raw": "couche brute : {n} instantanés hors règle",
        "store_story_content": "contenu des stories : {n} éléments hors règle",
        "store_csv_route": "fichiers laissés par la voie CSV : {n}",
        "store_points": "fichiers de points plus vieux que l'âge maximal de fichier : {n}",
        "store_backups": "sauvegardes étiquetées dont le dump flux a dépassé la durée de vie : {n}",
        "store_offsite": "copies hors site avec un dump flux trop vieux : {n}",
        "oldest": " (le plus ancien : {days} jours)",
        "offsite_age": " (âge configuré à la copie : {days} jours)",
        # refus et erreurs (libellés fixes)
        "period_above_year": "Prérequis refusé : le réglage retention.period_days dépasse un an",
        "settings_refused": "Prérequis refusé : réglages invalides ({what})",
        "settings_unreadable": "Prérequis refusé : fichier de réglages illisible",
        "error": "Erreur : {name}",
        "usage": "Erreur d'utilisation : option ou sous-commande inconnue",
        "language": "Erreur d'utilisation : langue inconnue (fr ou en attendu)",
    },
    "en": {
        "check_clean": "retention check: nothing out of rule",
        "check_found": "retention check: {n} items out of rule",
        "dry_run": "dry run: nothing deleted",
        "purge_done": "purge done",
        "backup_missing": "pre-purge backup missing: run the labelled backup first",
        "session": "Refused inside a Claude Code session",
        "store_database": "database, tickets past the rule: {n}",
        "store_raw": "raw layer: {n} snapshots out of rule",
        "store_story_content": "story content: {n} items out of rule",
        "store_csv_route": "files left from the CSV route: {n}",
        "store_points": "ageing-points files older than the maximum file age: {n}",
        "store_backups": "labelled backups whose flow dump outlived its lifetime: {n}",
        "store_offsite": "off-site copies holding a flow dump that is too old: {n}",
        "oldest": " (oldest: {days} days)",
        "offsite_age": " (age configured at copy time: {days} days)",
        "period_above_year": "Prerequisite refused: the setting retention.period_days is above one year",
        "settings_refused": "Prerequisite refused: invalid settings ({what})",
        "settings_unreadable": "Prerequisite refused: settings file unreadable",
        "error": "Error: {name}",
        "usage": "Usage error: unknown option or subcommand",
        "language": "Usage error: unknown language (fr or en expected)",
    },
}
