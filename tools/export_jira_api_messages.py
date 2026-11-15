"""PMZilla Lab : messages de tools/export_jira_api.py par langue (plan de la version anglaise, lot 3, étape 2).

Le français reproduit à l'octet près les textes du script avant le lot 3. Ne passent pas par ce catalogue : les noms de
colonnes de l'export Jira (Issue key, Status, Created, Inward issue link…), le libellé « (équipe inconnue) » écrit dans
le CSV (format de données lu par flux_jira.py), les clés du fichier equipes-assets.yaml et les en-têtes « Declared Label » et
« Fix Version ». Aucun message ne contient de
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
            "aucune source d'équipes : compléter jira_team_ids du référentiel et du catalogue. Le champ d'équipe ne renvoie pas le "
            "libellé de l'équipe (forme reçue : {form}). Rien n'est deviné, rien n'est écrit.\n"
            "Référentiel d'organisation Flux-Lab/organisation.yaml (clés seules) :\n{referential}\n"
            "Catalogue des équipes Flux-Lab/equipes-jira.yaml (clés seules) :\n{catalogue}\n"
            "`diagnose` montre la forme du champ. L'export liste ensuite les identifiants à ajouter."),
        "table_deprecated": "ancienne table des équipes plus lue : supprimer equipes-assets.yaml",
        # diagnose
        "diagnose_no_field": "réglage export_team_field manquant : rien à diagnostiquer pour l'équipe.",
        "diagnose_page": "Page interrogée : {count} ticket(s).",
        "diagnose_no_ticket": "la requête ne renvoie aucun ticket.",
        "diagnose_field_absent": "le champ d'équipe est absent des réponses : vérifier son identifiant et les droits du jeton.",
        "diagnose_forms": "Forme des valeurs du champ d'équipe : {forms}.",
        "diagnose_labels_yes": "Libellés exploitables : oui (texte, ou objet avec un libellé). L'export peut s'écrire.",
        "diagnose_labels_sources": "Libellés exploitables : par les sources d'équipes. L'export peut s'écrire ; compléter "
                                   "jira_team_ids ou le catalogue si des identifiants à ajouter s'affichent.",
        "diagnose_sources": "sources d'équipes : référentiel {referential} identifiants, catalogue {catalogue} identifiants",
        "diagnose_labels_no": "Libellés exploitables : non.",
        # fields
        "fields_search_empty": "--search : donner un texte à chercher dans le nom des champs.",
        "fields_unexpected": "réponse de Jira inattendue pour la liste des champs.",
        "fields_count": "{count} champ(s) sur {total} dont le nom contient le texte cherché.",
        "fields_project_invalid": "--project : donner une clé de projet (lettres, chiffres et _, commençant par une lettre).",
        "fields_unknown": "champ(s) inconnu(s) de Jira : {ids}.",
        "fields_field_empty": "--field : donner un identifiant de champ (customfield_NNNNN, components, fixVersions ou versions), pas un texte vide.",
        "fields_field_not_allowed": "--field : champ(s) non admis : {ids}. Seuls customfield_NNNNN, components, fixVersions et versions sont admis.",
        "fields_field_person": "--field : champ(s) de personne refusé(s) : {ids}.",
        "fields_options_missing": "fields : --search, ou --project avec au moins un --field",
        "fields_options_combined": "fields : --search ne se combine pas avec --project et --field",
        "fields_sample": "Échantillon : {count} ticket(s) du projet {project} (les {limit} derniers créés au plus). Champ, nom, tickets où il est rempli :",
        # export
        "query_needs_named": "--query demande un réglage jql_exports dans flux.yaml (nom -> requête JQL) ; seul jql_export existe.",
        "query_unknown": "requête « {name} » inconnue. Disponibles : {names}.",
        "output_retired": "--output est retirée : l'export écrit dans la base",
        "export_summary": "{label}Tickets : {tickets} ; pages : {pages}.",
        "export_no_team_column": "{label}Aucune équipe lue : export_team_field n'est pas réglé.",
        "export_past_retention": "{label}tickets au-delà de la conservation, non écrits : {count}",
        "export_referential_idle": "équipes du référentiel sans ticket : {count}",
        "export_teams_without_type": "équipes sans type : {count}",
        "export_points": "{label}Story points : {filled} ticket(s) renseigné(s) sur {total} (aucune valeur affichée).",
        "export_points_field": "{label}  Champ {field} : renseigné pour {filled} ticket(s) sur {total} ; {conflicts} ticket(s) où un autre "
                               "champ de points est renseigné avec une valeur différente (aucune valeur affichée).",
        "export_points_invalid": "{label}Story points : {count} valeur(s) non numérique(s) écrite(s) vides.",
        "export_outside": "{label}équipes hors organisation : {identifiers} identifiants, {tickets} tickets",
        "export_obsolete": "{label}tickets sur des équipes obsolètes : {tickets}",
        "export_unknown_teams": "{label}identifiants d'équipe ni dans le référentiel ni dans le catalogue : {identifiers}, "
                                "sur {tickets} tickets",
        "export_unknown_ids": "{label}identifiants à ajouter : {ids}",
        "export_raw_layer": "couche brute : {seen} tickets vus, {added} instantanés ajoutés",
        "raw_password_missing": "mot de passe du rôle d'import absent : le poser avec db.py role-password",
        "raw_db_unreachable": "base injoignable : export arrêté avant tout appel à Jira",
        "export_strict_teams": "identifiants d'équipe inconnus : export incomplet",
        # champs de livraison et tickets de version (jira-delivery-fields, D12) : des nombres, jamais une valeur
        "export_no_version_project": "projet de référence des versions non configuré : attributs des versions ignorés",
        # R-20261114-108 : table des champs de livraison absente de flux.yaml (rien n'est lu, l'export se poursuit, code de sortie inchangé)
        "export_no_delivery_fields": "champs de livraison non configurés (clé delivery_fields absente de flux.yaml) : champs de livraison et attributs des versions non lus, données de livraison déjà stockées conservées, export poursuivi",
        "export_no_version_fields": "champs des tickets de version non configurés (delivery_fields.version_tickets.asset absent de flux.yaml) : attributs des versions ignorés",
        "export_version_tickets": "tickets de version lus : {count}",
        "export_version_other_type": "tickets d'un autre type écartés du projet de référence des versions : {count}",
        "export_version_no_asset": "tickets de version sans actif : {count}",
        "export_version_several_assets": "tickets de version à plusieurs actifs : {count}",
        "export_version_conflicts": "actifs à plusieurs tickets de version : {count}",
        "export_option_filter": "noms courts de version remplacés par le marqueur de nom sensible : {count}",
        "sensitive_list_unavailable": "liste des noms sensibles indisponible : les noms courts de version ne peuvent pas être filtrés, export arrêté.",
        # sous-commandes retirées
        "retired_teams_table": "la sous-commande teams-table est retirée. Les équipes se renseignent à la main dans le référentiel "
                               "(Flux-Lab/organisation.yaml) et le catalogue (Flux-Lab/equipes-jira.yaml) ; "
                               "`export_jira_api.py export` liste les identifiants à ajouter.",
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
            "no team source: fill jira_team_ids in the referential and the catalogue. The team field does not return the team "
            "label (shape received: {form}). Nothing is guessed, nothing is written.\n"
            "Organisation referential Flux-Lab/organisation.yaml (keys only):\n{referential}\n"
            "Team catalogue Flux-Lab/equipes-jira.yaml (keys only):\n{catalogue}\n"
            "`diagnose` shows the shape of the field. The export then lists the identifiers to add."),
        "table_deprecated": "former team table no longer read: delete equipes-assets.yaml",
        "diagnose_no_field": "setting export_team_field is missing: nothing to diagnose for the team.",
        "diagnose_page": "Page queried: {count} ticket(s).",
        "diagnose_no_ticket": "the query returns no ticket.",
        "diagnose_field_absent": "the team field is absent from the responses: check its identifier and the token permissions.",
        "diagnose_forms": "Shape of the team field values: {forms}.",
        "diagnose_labels_yes": "Usable labels: yes (text, or object with a label). The export can be written.",
        "diagnose_labels_sources": "Usable labels: through the team sources. The export can be written; complete "
                                   "jira_team_ids or the catalogue if identifiers to add show up.",
        "diagnose_sources": "team sources: referential {referential} identifiers, catalogue {catalogue} identifiers",
        "diagnose_labels_no": "Usable labels: no.",
        "fields_search_empty": "--search: give a text to look for in the field names.",
        "fields_unexpected": "unexpected response from Jira for the field list.",
        "fields_count": "{count} field(s) out of {total} whose name contains the searched text.",
        "fields_project_invalid": "--project: give a project key (letters, digits and _, starting with a letter).",
        "fields_unknown": "field(s) unknown to Jira: {ids}.",
        "fields_field_empty": "--field: give a field identifier (customfield_NNNNN, components, fixVersions or versions), not an empty text.",
        "fields_field_not_allowed": "--field: field(s) not allowed: {ids}. Only customfield_NNNNN, components, fixVersions and versions are allowed.",
        "fields_field_person": "--field: person field(s) refused: {ids}.",
        "fields_options_missing": "fields: --search, or --project with at least one --field",
        "fields_options_combined": "fields: --search cannot be combined with --project and --field",
        "fields_sample": "Sample: {count} ticket(s) of project {project} (the {limit} most recently created at most). Field, name, tickets where it is filled:",
        "query_needs_named": "--query needs a jql_exports setting in flux.yaml (name -> JQL query); only jql_export exists.",
        "query_unknown": "query \"{name}\" unknown. Available: {names}.",
        "output_retired": "--output is retired: the export writes into the database",
        "export_summary": "{label}Tickets: {tickets}; pages: {pages}.",
        "export_no_team_column": "{label}No team read: export_team_field is not set.",
        "export_past_retention": "{label}tickets past retention, not written: {count}",
        "export_referential_idle": "referential teams without ticket: {count}",
        "export_teams_without_type": "teams without a type: {count}",
        "export_points": "{label}Story points: {filled} ticket(s) filled out of {total} (no value displayed).",
        "export_points_field": "{label}  Field {field}: filled for {filled} ticket(s) out of {total}; {conflicts} ticket(s) where another "
                               "points field is filled with a different value (no value displayed).",
        "export_points_invalid": "{label}Story points: {count} non-numeric value(s) written empty.",
        "export_outside": "{label}teams outside the organisation: {identifiers} identifiers, {tickets} tickets",
        "export_obsolete": "{label}tickets on obsolete teams: {tickets}",
        "export_unknown_teams": "{label}team identifiers in neither the referential nor the catalogue: {identifiers}, "
                                "on {tickets} tickets",
        "export_unknown_ids": "{label}identifiers to add: {ids}",
        "export_raw_layer": "raw layer: {seen} tickets seen, {added} snapshots added",
        "raw_password_missing": "import role password missing: set it with db.py role-password",
        "raw_db_unreachable": "database unreachable: export stopped before any Jira call",
        "export_strict_teams": "unknown team identifiers: export incomplete",
        "export_no_version_project": "version reference project not configured: version attributes skipped",
        "export_no_delivery_fields": "delivery fields not configured (delivery_fields key missing from flux.yaml): delivery fields and version attributes not read, delivery data already stored kept, export continued",
        "export_no_version_fields": "version ticket fields not configured (delivery_fields.version_tickets.asset missing from flux.yaml): version attributes skipped",
        "export_version_tickets": "version tickets read: {count}",
        "export_version_other_type": "tickets of another type set aside from the version reference project: {count}",
        "export_version_no_asset": "version tickets without asset: {count}",
        "export_version_several_assets": "version tickets with several assets: {count}",
        "export_version_conflicts": "assets with conflicting version tickets: {count}",
        "export_option_filter": "version short names replaced by the sensitive-name marker: {count}",
        "sensitive_list_unavailable": "sensitive-names list unavailable: version short names cannot be filtered, export stopped.",
        "retired_teams_table": "the teams-table subcommand is retired. Teams are entered by hand in the referential "
                               "(Flux-Lab/organisation.yaml) and the catalogue (Flux-Lab/equipes-jira.yaml); "
                               "`export_jira_api.py export` lists the identifiers to add.",
        "retired_compare": "the compare subcommand is retired (the manual CSV export is no longer a route). Use "
                           "`export_jira_api.py export`; the database-versus-CSV comparison is in flow_compare.py.",
        "error_line": "Error: {message}",
        "unexpected_error": "Unexpected error ({name}).",
    },
}

# messages de check-teams et migrate-teams (change team-mapping) : même catalogue, fichier à part
from export_jira_api_equipes_messages import CATALOGS_EQUIPES  # noqa: E402

for _langue, _messages in CATALOGS_EQUIPES.items():
    CATALOGS[_langue].update(_messages)
