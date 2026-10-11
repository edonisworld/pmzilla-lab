"""PMZilla Lab : messages de tools/export_jira_api.py par langue (plan de la version anglaise, lot 3, étape 2).

Le français reproduit à l'octet près les textes du script avant le lot 3. Ne passent pas par ce catalogue : les noms de
colonnes de l'export Jira (Issue key, Status, Created, Inward issue link…), le libellé « (équipe inconnue) » écrit dans
le CSV (format de données lu par flux_jira.py) et les clés du fichier equipes-assets.yaml. Aucun message ne contient de
jeton, de clé de ticket, de titre ni de nom : seulement des effectifs, des formes de valeurs et des noms de réglages.
"""

CATALOGS = {
    "fr": {
        # réglages
        "jql_exports_not_dict": "jql_exports doit associer un nom à une requête JQL.",
        "jql_name_invalid": "un nom de jql_exports ne contient que des lettres, chiffres, tirets et soulignés.",
        "jql_empty": "la requête « {name} » de jql_exports est vide.",
        "jql_missing": "réglage jql_export (ou jql_exports) manquant dans {file}.",
        "team_field_invalid": "export_team_field doit être un identifiant de champ (customfield_NNNNN).",
        "verification_field_invalid": "export_verification_field doit être un identifiant de champ (customfield_NNNNN).",
        "points_field_invalid": "export_points_field doit être un identifiant de champ (customfield_NNNNN).",
        "timezone_invalid": "export_timezone « {name} » n'est pas un fuseau horaire connu (exemple : {example}).",
        "table_unreadable": "{table} est illisible : le corriger ou le recréer à la main (equipes: {{identifiant: libellé}}).",
        # formes de valeurs du champ d'équipe (jamais le contenu)
        "list_separator": " ; ",
        "form_count": "{form} : {count}",
        "form_empty": "vide",
        "form_text_id": "texte (identifiant seul)",
        "form_text": "texte",
        "form_object": "objet {{{keys}}}",
        "form_empty_list": "liste vide",
        "form_list_of": "liste de {forms}",
        "team_label_options": (
            "Le champ d'équipe ne renvoie pas le libellé de l'équipe (forme reçue : {form}). Rien n'est deviné, rien n'est "
            "écrit. Créer à la main Flux-Lab/equipes-assets.yaml, au format `equipes: {{identifiant: libellé}}`, puis "
            "relancer ; `diagnose` montre la forme du champ. L'export liste ensuite les identifiants à compléter."),
        # diagnose
        "diagnose_no_field": "réglage export_team_field manquant : rien à diagnostiquer pour l'équipe.",
        "diagnose_page": "Page interrogée : {count} ticket(s).",
        "diagnose_no_ticket": "la requête ne renvoie aucun ticket.",
        "diagnose_field_absent": "le champ d'équipe est absent des réponses : vérifier son identifiant et les droits du jeton.",
        "diagnose_forms": "Forme des valeurs du champ d'équipe : {forms}.",
        "diagnose_labels_yes": "Libellés exploitables : oui (texte, ou objet avec un libellé). L'export peut s'écrire.",
        "diagnose_labels_table": "Libellés exploitables : par la table {table} ({count} identifiant(s)). L'export peut "
                                 "s'écrire ; compléter la table si des équipes inconnues s'affichent.",
        "diagnose_labels_no": "Libellés exploitables : non.",
        # fields
        "fields_search_empty": "--search : donner un texte à chercher dans le nom des champs.",
        "fields_unexpected": "réponse de Jira inattendue pour la liste des champs.",
        "fields_count": "{count} champ(s) sur {total} dont le nom contient le texte cherché.",
        # export
        "query_needs_named": "--query demande un réglage jql_exports dans flux.yaml (nom -> requête JQL) ; seul jql_export existe.",
        "query_unknown": "requête « {name} » inconnue. Disponibles : {names}.",
        "output_single_query": "--output ne convient qu'à une seule requête : ajoute --query NOM.",
        "export_summary": "{label}Tickets : {tickets} ; pages : {pages} ; colonnes : {columns} "
                          "(équipe : {team_columns}, liens : {link_columns} pour {link_types} type(s)).",
        "export_no_team_column": "{label}Aucune colonne d'équipe : export_team_field n'est pas réglé.",
        "export_verification": "{label}Colonne « {header} » : {filled} ticket(s) renseigné(s) sur {total} "
                               "(aucune valeur affichée).",
        "export_points": "{label}Colonne « {header} » : {filled} ticket(s) renseigné(s) sur {total} "
                         "(aucune valeur affichée).",
        "export_points_field": "{label}  Champ {field} : renseigné pour {filled} ticket(s) sur {total} ; {conflicts} ticket(s) où un autre "
                               "champ de points est renseigné avec une valeur différente (aucune valeur affichée).",
        "export_points_invalid": "{label}Story points : {count} valeur(s) non numérique(s) écrite(s) vides.",
        "export_unknown_teams": "{label}Équipes inconnues : {identifiers} identifiant(s) distinct(s) absent(s) de la table, "
                                "{tickets} ticket(s) concerné(s), écrits « {unknown} ».",
        "export_unknown_ids": "{label}Complétez {table} (equipes: identifiant -> libellé) avec ces identifiants : {ids}.",
        "export_written": "{label}Fichier écrit : {name} (permissions 600).",
        # sous-commandes retirées
        "retired_teams_table": "la sous-commande teams-table est retirée. Flux-Lab/equipes-assets.yaml se complète à la main "
                               "(equipes: identifiant -> libellé) ; `export_jira_api.py export` liste les identifiants inconnus.",
        "retired_compare": "la sous-commande compare est retirée (l'export manuel CSV n'est plus une voie). Utiliser "
                           "`export_jira_api.py export` ; la comparaison base contre CSV est dans flow_compare.py.",
        # erreurs de main
        "error_line": "Erreur : {message}",
        "unexpected_error": "Erreur inattendue ({name}).",
    },
    "en": {
        "jql_exports_not_dict": "jql_exports must map a name to a JQL query.",
        "jql_name_invalid": "a jql_exports name contains only letters, digits, hyphens and underscores.",
        "jql_empty": "the query \"{name}\" of jql_exports is empty.",
        "jql_missing": "setting jql_export (or jql_exports) is missing in {file}.",
        "team_field_invalid": "export_team_field must be a field identifier (customfield_NNNNN).",
        "verification_field_invalid": "export_verification_field must be a field identifier (customfield_NNNNN).",
        "points_field_invalid": "export_points_field must be a field identifier (customfield_NNNNN).",
        "timezone_invalid": "export_timezone \"{name}\" is not a known time zone (example: {example}).",
        "table_unreadable": "{table} is unreadable: fix or recreate it by hand (equipes: {{identifier: label}}).",
        "list_separator": "; ",
        "form_count": "{form}: {count}",
        "form_empty": "empty",
        "form_text_id": "text (identifier only)",
        "form_text": "text",
        "form_object": "object {{{keys}}}",
        "form_empty_list": "empty list",
        "form_list_of": "list of {forms}",
        "team_label_options": (
            "The team field does not return the team label (shape received: {form}). Nothing is guessed, nothing is "
            "written. Create Flux-Lab/equipes-assets.yaml by hand, in the format `equipes: {{identifier: label}}`, then "
            "run again; `diagnose` shows the shape of the field. The export then lists the identifiers to complete."),
        "diagnose_no_field": "setting export_team_field is missing: nothing to diagnose for the team.",
        "diagnose_page": "Page queried: {count} ticket(s).",
        "diagnose_no_ticket": "the query returns no ticket.",
        "diagnose_field_absent": "the team field is absent from the responses: check its identifier and the token permissions.",
        "diagnose_forms": "Shape of the team field values: {forms}.",
        "diagnose_labels_yes": "Usable labels: yes (text, or object with a label). The export can be written.",
        "diagnose_labels_table": "Usable labels: through the table {table} ({count} identifier(s)). The export can "
                                 "be written; complete the table if unknown teams show up.",
        "diagnose_labels_no": "Usable labels: no.",
        "fields_search_empty": "--search: give a text to look for in the field names.",
        "fields_unexpected": "unexpected response from Jira for the field list.",
        "fields_count": "{count} field(s) out of {total} whose name contains the searched text.",
        "query_needs_named": "--query needs a jql_exports setting in flux.yaml (name -> JQL query); only jql_export exists.",
        "query_unknown": "query \"{name}\" unknown. Available: {names}.",
        "output_single_query": "--output only works with a single query: add --query NAME.",
        "export_summary": "{label}Tickets: {tickets}; pages: {pages}; columns: {columns} "
                          "(team: {team_columns}, links: {link_columns} for {link_types} type(s)).",
        "export_no_team_column": "{label}No team column: export_team_field is not set.",
        "export_verification": "{label}Column \"{header}\": {filled} ticket(s) filled out of {total} "
                               "(no value displayed).",
        "export_points": "{label}Column \"{header}\": {filled} ticket(s) filled out of {total} "
                         "(no value displayed).",
        "export_points_field": "{label}  Field {field}: filled for {filled} ticket(s) out of {total}; {conflicts} ticket(s) where another "
                               "points field is filled with a different value (no value displayed).",
        "export_points_invalid": "{label}Story points: {count} non-numeric value(s) written empty.",
        "export_unknown_teams": "{label}Unknown teams: {identifiers} distinct identifier(s) missing from the table, "
                                "{tickets} ticket(s) affected, written \"{unknown}\".",
        "export_unknown_ids": "{label}Complete {table} (equipes: identifier -> label) with these identifiers: {ids}.",
        "export_written": "{label}File written: {name} (permissions 600).",
        "retired_teams_table": "the teams-table subcommand is retired. Flux-Lab/equipes-assets.yaml is completed by hand "
                               "(equipes: identifier -> label); `export_jira_api.py export` lists the unknown identifiers.",
        "retired_compare": "the compare subcommand is retired (the manual CSV export is no longer a route). Use "
                           "`export_jira_api.py export`; the database-versus-CSV comparison is in flow_compare.py.",
        "error_line": "Error: {message}",
        "unexpected_error": "Unexpected error ({name}).",
    },
}
