"""PMZilla Lab : messages de `check-teams` et `migrate-teams` (change team-mapping, design D11), fusionnés dans le catalogue de
tools/export_jira_api_messages.py.

Aucune phrase ne porte de libellé, de nom, de clé de ticket ni de personne : des nombres, des identifiants, des chemins de clé avec
leur ligne et les noms fixes de colonnes ou de types. La seule exception est la liste des libellés distinctifs de migrate-teams
(design D9), imprimée dans le Terminal de l'auteur.
"""

CATALOGS_EQUIPES = {
    "fr": {
        "session": "Refusé dans une session Claude Code",
        # check-teams
        "teams_consistent": "sources d'équipes cohérentes : référentiel {referential} identifiants, catalogue {catalogue} identifiants, "
                            "{obsolete} obsolètes",
        "table_not_covered": "identifiants de l'ancienne table non couverts : {count}",
        "table_ids_to_place": "identifiants à placer : {ids}",
        "review_seen": "équipes du catalogue vues sur des tickets de l'export, à revoir : {entries} entrées, {tickets} tickets comptés par entrée",
        "review_reviewed": "équipes du catalogue vues sur des tickets, déjà revues : {entries} entrées",
        "review_ids": "identifiants à revoir : {ids}",
        "review_added": "identifiants ajoutés à la liste de revue : {count}",
        "review_already": "identifiants déjà dans la liste de revue : {count}",
        "review_unknown": "identifiant hors du catalogue des équipes extérieures, rien n'est écrit : {ids}",
        "review_unreachable": "base injoignable : revue du catalogue sautée",
        "review_no_ticket": "aucun ticket dans la base : revue du catalogue sautée",
        "without_identifier": "équipes du référentiel sans identifiant : {count}",
        "without_identifier_paths": "équipes sans identifiant : {paths}",
        "absent_from_assets": "identifiants du référentiel absents d'Assets : {count}",
        "absent_from_assets_ids": "identifiants absents d'Assets : {ids}",
        "inactive_in_assets": "équipes du référentiel avec un identifiant inactif ou abandonné dans Assets : {count}",
        "inactive_in_assets_ids": "identifiants inactifs ou abandonnés dans Assets : {ids}",
        "different_types": "équipes du référentiel aux identifiants de types différents : {count}",
        "different_types_ids": "identifiants de types différents : {ids}",
        "forced_listed": "équipes du référentiel au type forcé : {count}",
        "forced_line": "type forcé en {path} : {forced}, type Assets : {assets}",
        "assets_type_none": "aucun",
        "assets_type_different": "types différents",
        "forced_differs": "équipes du référentiel au type forcé différent du type déduit : {count}",
        "forced_differs_ids": "identifiants des équipes au type forcé différent du type déduit : {ids}",
        "forced_not_needed": "types forcés devenus inutiles, à retirer : {count}",
        "forced_not_needed_paths": "types forcés à retirer : {paths}",
        "types_changed": "types d'équipe changés dans Assets depuis l'écriture du catalogue : {count}",
        "types_changed_ids": "identifiants au type changé : {ids}",
        "assets_used": "liste Assets utilisée : {file}",
        "assets_none": "aucune liste Assets trouvée : contrôles sautés : identifiants du référentiel absents d'Assets, équipes du "
                       "référentiel inactives dans Assets, types d'équipe changés dans Assets",
        # migrate-teams
        "assets_read": "liste Assets lue : {total} objets, {active} actifs, {draft} brouillons (écrits comme actifs), "
                       "{inactive} inactifs, {discarded} abandonnés",
        "short_name_fallback": "nom_court vide, libellé repris : {total} lignes ({active} actives, {inactive} inactives, "
                               "{draft} brouillons écrits comme actifs, {discarded} abandonnées)",
        "table_compared": "ancienne table et liste Assets comparées : {only_table} identifiants seulement dans la table, "
                          "{only_list} seulement dans la liste, {different} avec un libellé différent",
        "table_only_ids": "identifiants seulement dans l'ancienne table : {ids}",
        "catalogue_written": "catalogue écrit : {entries} entrées, {named} identifiants nommés comme une équipe du référentiel, "
                             "à placer dans le référentiel",
        "named_like_ids": "identifiants nommés comme une équipe du référentiel : {ids}",
        "types_written": "types d'équipe écrits : {development} développement, {verification} vérification, "
                         "{product} gestion de produit, {other} autres",
        "written_obsolete": "entrées écrites obsolètes (inactives ou abandonnées dans Assets) : {count}",
        "written_obsolete_ids": "identifiants écrits obsolètes : {ids}",
        "mixed_statuses": "entrées aux objets actifs et inactifs, écrites non obsolètes : {count}",
        "mixed_statuses_ids": "identifiants des entrées aux statuts mêlés : {ids}",
        "labels_proposed": "libellés à ajouter à la liste des noms sensibles : {count}",
        "labels_left_out": "libellés écartés par le filtre : {count}",
        "labels_left_out_common": "libellés écartés comme mots courants : {count}",
        "catalogue_present": "catalogue déjà présent : rien n'est écrit",
        "assets_absent": "liste Assets absente ou hors du dossier des flux : rien n'est écrit",
        "assets_missing_column": "liste Assets refusée : colonne manquante {column}",
        "assets_empty_line": "liste Assets refusée : ligne vide à la ligne {line}",
        "assets_unknown_column": "liste Assets refusée : colonne inconnue en position {position}",
        "assets_empty_cell": "liste Assets refusée : {column} vide, {count} lignes concernées (première : ligne {line})",
        "assets_empty_both": "liste Assets refusée : libelle et nom_court vides sur la même ligne, {count} lignes concernées "
                             "(première : ligne {line})",
        "assets_bad_id": "liste Assets refusée : id non numérique à la ligne {line}",
        "assets_bad_type": "liste Assets refusée : type autre que les quatre sous-types de Team à la ligne {line}",
        "assets_bad_status": "liste Assets refusée : statut autre que active, draft, inactive ou discarded à la ligne {line}",
        "assets_duplicate_id": "liste Assets refusée : identifiant en double aux lignes {lines}",
        "assets_label_two_types": "liste Assets refusée : même libellé avec deux types aux lignes {lines}",
        "assets_unreadable": "liste Assets refusée : fichier illisible",
        # extract-teams (change team-names-readable, design D10) : des effectifs seulement, jamais un nom
        "extract_written": "extrait des noms d'équipes écrit : {referential} équipes du référentiel, dont {without} sans identifiant ; "
                           "{catalogue} entrées du catalogue",
        "extract_no_source": "aucune source d'équipes à extraire : ni référentiel ni catalogue ; rien n'est écrit",
        "extract_not_written": "extrait des noms d'équipes non écrit : {error}",
    },
    "en": {
        "session": "Refused inside a Claude Code session",
        "teams_consistent": "team sources consistent: referential {referential} identifiers, catalogue {catalogue} identifiers, "
                            "{obsolete} obsolete",
        "table_not_covered": "former table identifiers not covered: {count}",
        "table_ids_to_place": "identifiers to place: {ids}",
        "review_seen": "catalogue teams seen on export tickets, to review: {entries} entries, {tickets} tickets counted per entry",
        "review_reviewed": "catalogue teams seen on export tickets, already reviewed: {entries} entries",
        "review_ids": "identifiers to review: {ids}",
        "review_added": "identifiers added to the review list: {count}",
        "review_already": "identifiers already in the review list: {count}",
        "review_unknown": "not an outside catalogue identifier, nothing written: {ids}",
        "review_unreachable": "database unreachable: catalogue review skipped",
        "review_no_ticket": "no ticket in the database: catalogue review skipped",
        "without_identifier": "referential teams without identifier: {count}",
        "without_identifier_paths": "teams without identifier: {paths}",
        "absent_from_assets": "referential identifiers absent from Assets: {count}",
        "absent_from_assets_ids": "identifiers absent from Assets: {ids}",
        "inactive_in_assets": "referential teams with an identifier inactive or discarded in Assets: {count}",
        "inactive_in_assets_ids": "identifiers inactive or discarded in Assets: {ids}",
        "different_types": "referential teams with identifiers of different types: {count}",
        "different_types_ids": "identifiers with different types: {ids}",
        "forced_listed": "referential teams with a forced type: {count}",
        "forced_line": "forced type at {path}: {forced}, Assets type: {assets}",
        "assets_type_none": "none",
        "assets_type_different": "different types",
        "forced_differs": "referential teams whose forced type differs from the deduced type: {count}",
        "forced_differs_ids": "identifiers of teams with a forced type different from the deduced type: {ids}",
        "forced_not_needed": "forced types no longer needed, to remove: {count}",
        "forced_not_needed_paths": "forced types to remove: {paths}",
        "types_changed": "team types changed in Assets since the catalogue was written: {count}",
        "types_changed_ids": "identifiers with a changed type: {ids}",
        "assets_used": "assets list used: {file}",
        "assets_none": "no assets list found: checks skipped: referential identifiers absent from Assets, referential teams inactive "
                       "in Assets, team types changed in Assets",
        "assets_read": "assets list read: {total} objects, {active} active, {draft} draft (written as active), "
                       "{inactive} inactive, {discarded} discarded",
        "short_name_fallback": "short name empty, label used: {total} lines ({active} active, {inactive} inactive, "
                               "{draft} draft written as active, {discarded} discarded)",
        "table_compared": "former table and assets list compared: {only_table} identifiers only in the table, "
                          "{only_list} only in the list, {different} with a different label",
        "table_only_ids": "identifiers only in the former table: {ids}",
        "catalogue_written": "catalogue written: {entries} entries, {named} identifiers named like a referential team, "
                             "to place in the referential",
        "named_like_ids": "identifiers named like a referential team: {ids}",
        "types_written": "team types written: {development} development, {verification} verification, "
                         "{product} product management, {other} other",
        "written_obsolete": "entries written obsolete (inactive or discarded in Assets): {count}",
        "written_obsolete_ids": "identifiers written obsolete: {ids}",
        "mixed_statuses": "entries with active and inactive objects, written not obsolete: {count}",
        "mixed_statuses_ids": "identifiers of entries with mixed statuses: {ids}",
        "labels_proposed": "labels to add to the sensitive-names list: {count}",
        "labels_left_out": "labels left out by the filter: {count}",
        "labels_left_out_common": "labels left out as common words: {count}",
        "catalogue_present": "catalogue already present: nothing written",
        "assets_absent": "assets list absent or outside the flow folder: nothing written",
        "assets_missing_column": "assets list refused: missing column {column}",
        "assets_empty_line": "assets list refused: empty line at line {line}",
        "assets_unknown_column": "assets list refused: unknown column at position {position}",
        "assets_empty_cell": "assets list refused: {column} empty, {count} lines concerned (first: line {line})",
        "assets_empty_both": "assets list refused: label and short name empty on the same line, {count} lines concerned "
                             "(first: line {line})",
        "assets_bad_id": "assets list refused: non-numeric id at line {line}",
        "assets_bad_type": "assets list refused: type other than the four Team sub-types at line {line}",
        "assets_bad_status": "assets list refused: status other than active, draft, inactive or discarded at line {line}",
        "assets_duplicate_id": "assets list refused: identifier listed twice at lines {lines}",
        "assets_label_two_types": "assets list refused: same label with two types at lines {lines}",
        "assets_unreadable": "assets list refused: unreadable file",
        "extract_written": "team-names extract written: {referential} referential teams, {without} without identifier; "
                           "{catalogue} catalogue entries",
        "extract_no_source": "no team source to extract: neither referential nor catalogue; nothing written",
        "extract_not_written": "team-names extract not written: {error}",
    },
}
