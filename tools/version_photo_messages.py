"""PMZilla Lab : messages de tools/version_photo.py par langue (change version-quality-photo, décision D14).

Aucun message ne contient de clé de ticket, d'équipe, de nom de version ni de valeur de réglage : seulement des effectifs, des dates de
semaine et les phrases clés de la décision D14 du change (design.md). La raison d'une adoption de N n'est jamais imprimée.
"""

CATALOGS = {
    "fr": {
        # phrases clés de D14 (code 0)
        "reconstruct_done": "reconstruction : {weeks} semaines, {versions} versions, {partial} semaines partielles",
        "reconstruct_warning": "avertissement : une reconstruction relancée est plus partielle, la purge a avancé",
        "reconstruct_kept": "avertissement : {n} semaines reconstruites plus anciennes gardées telles quelles, plus recalculables",
        "photo_taken": "photo prise : semaine du {date}, {rows} lignes",
        "no_history": "défauts sans historique de fix version : {n}",
        "n_adopted": "N adopté : {n} semaines, le {date}",
        "n_warning": "avertissement : N modifié après une première adoption, signalé dans la vue",
        # change version-release-date, décision D9 : après les lignes de reconstruct et de take, dans cet ordre
        "versions_no_release_date": "versions sans date de sortie : {n}",
        "versions_conflicting_release": "versions aux attributs de sortie divergents : {n}",
        # refus (code 3, rien n'est écrit)
        "session": "Refusé dans une session Claude Code",
        "defect_types_missing": "types de défaut non réglés",
        "reconstruction_exists": "reconstruction déjà faite : utiliser --replace",
        "photo_exists": "photo déjà prise pour cette semaine : utiliser --replace",
        "n_exists": "N déjà adopté : donner --reason",
        "crossing_masking_missing": "adoption de N refusée : le masquage des croisements équipes x versions n'est pas encore en place (feature R-144)",
        "crossing_masking_version": "adoption de N refusée : version installée {installed}, version attendue {expected}, raison : propagation des bornes D15 non installée",
        "settings_refused": "Prérequis refusé : réglages invalides ({what})",
        "settings_unreadable": "Prérequis refusé : fichier de réglages illisible",
        # erreurs
        "error": "Erreur : {name}",
        "usage": "Erreur d'utilisation : option, sous-commande ou valeur inconnue",
        "language": "Erreur d'utilisation : langue inconnue (fr ou en attendu)",
    },
    "en": {
        "reconstruct_done": "reconstruction: {weeks} weeks, {versions} versions, {partial} partial weeks",
        "reconstruct_warning": "warning: a reconstruction run again is more partial, the purge has moved on",
        "reconstruct_kept": "warning: {n} older reconstructed weeks kept as they are, no longer recomputable",
        "photo_taken": "photo taken: week of {date}, {rows} rows",
        "no_history": "defects without fix version history: {n}",
        "n_adopted": "N adopted: {n} weeks, on {date}",
        "n_warning": "warning: N modified after a first adoption, shown in the view",
        "versions_no_release_date": "versions without release date: {n}",
        "versions_conflicting_release": "versions with conflicting release attributes: {n}",
        "session": "Refused inside a Claude Code session",
        "defect_types_missing": "defect types not set",
        "reconstruction_exists": "reconstruction already done: use --replace",
        "photo_exists": "photo already taken for this week: use --replace",
        "n_exists": "N already adopted: give --reason",
        "crossing_masking_missing": "N adoption refused: masking of team x version crossings is not yet in place (feature R-144)",
        "crossing_masking_version": "N adoption refused: installed version {installed}, expected version {expected}, reason: D15 bounds propagation not installed",
        "settings_refused": "Prerequisite refused: invalid settings ({what})",
        "settings_unreadable": "Prerequisite refused: settings file unreadable",
        "error": "Error: {name}",
        "usage": "Usage error: unknown option, subcommand or value",
        "language": "Usage error: unknown language (fr or en expected)",
    },
}
