"""PMZilla Lab : messages de tools/flow_views.py par langue (lot 6 de la base de données)."""

CATALOGS = {
    "fr": {
        "views_title": "Vues agrégées du schéma flow (cellule de moins de {min_cell} tickets : « {masked} »)",
        "unknown_view": "Vue inconnue : {name}. Vues disponibles : {views}.",
        "no_rows": "(aucune ligne)",
        "masked": "<{min_cell}",
        "min_cell_floor": "Seuil de masquage ramené à {min_cell} (jamais en dessous de {floor}).",
        "settings_unreadable": "flux.yaml illisible : seuil de masquage {floor} utilisé.",
        "error": "Erreur : {message}",
        "desc_v_team_status": "tickets par équipe, type, catégorie d'état et état",
        "desc_v_team_weekly_resolved": "tickets résolus par équipe, type et semaine (lundi)",
        "desc_v_team_open_age": "tickets ouverts par équipe, catégorie d'état et tranche d'âge",
        "desc_v_team_dependencies": "liens entre équipes (équipe source, équipe cible, type de lien)",
    },
    "en": {
        "views_title": "Aggregated views of the flow schema (a cell under {min_cell} tickets: \"{masked}\")",
        "unknown_view": "Unknown view: {name}. Available views: {views}.",
        "no_rows": "(no rows)",
        "masked": "<{min_cell}",
        "min_cell_floor": "Masking threshold raised to {min_cell} (never below {floor}).",
        "settings_unreadable": "flux.yaml unreadable: masking threshold {floor} used.",
        "error": "Error: {message}",
        "desc_v_team_status": "tickets by team, type, status category and status",
        "desc_v_team_weekly_resolved": "resolved tickets by team, type and week (Monday)",
        "desc_v_team_open_age": "open tickets by team, status category and age bracket",
        "desc_v_team_dependencies": "links between teams (source team, target team, link type)",
    },
}
