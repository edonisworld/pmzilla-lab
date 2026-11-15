"""Table FACTICE des champs de livraison (R-20261114-108, même logique que A-92 : aucun identifiant réel dans le dépôt).

Source unique des tests de livraison (flow_delivery, export_jira_api, history_jira) : les identifiants `customfield_99001` à
`customfield_99025` sont inventés et n'ont aucun rapport avec ceux du Jira de l'organisation, qui vivent dans `delivery_fields` de
Flux-Lab/flux.yaml (hors Git). Les tests des autres suites importent ce module par un `sys.path.insert` de ce dossier ; un écart entre
la forme de cette table et le schéma de `flux_config.DELIVERY_FIELDS_*` est détecté par test_delivery_fields.py de la suite flux_config
(il valide YAML ci-dessous avec le vrai validateur et vérifie que la table couvre tous les noms du schéma).

Remplace : les identifiants réels écrits en dur dans les tests. Retrait : permanent (aucune donnée de l'organisation dans l'arbre public).
"""

SPRINT = "customfield_99001"
RANG = "customfield_99015"

TABLE = {
    "sprint": SPRINT,
    "rank": RANG,
    "assets": {"target": "customfield_99002", "resolution": "customfield_99003",
               "epic_a": "customfield_99004", "epic_b": "customfield_99005"},
    "defect_assets": {"detected": "customfield_99006", "affected": "customfield_99007"},
    "multi_options": {"category_nature": "customfield_99008", "workflow_option": "customfield_99009"},
    "single_options": {"release_target": "customfield_99010", "verification_required": "customfield_99011",
                       "product_safety": "customfield_99012", "isp": "customfield_99013",
                       "code_review_status": "customfield_99014"},
    "flags": {"customer_commitment": "customfield_99016", "source_commitment": "customfield_99017",
              "strategic_objective": "customfield_99018"},
    "defect_options": {"detection_phase": "customfield_99019", "detected_by": "customfield_99020",
                       "installed_base": "customfield_99021"},
    "version_tickets": {"asset": "customfield_99022", "released": "customfield_99023", "started": "customfield_99024",
                        "short_name": "customfield_99025"},
}


def yaml(table: dict | None = None) -> str:
    """Le bloc `delivery_fields` de flux.yaml qui porte la table (le texte que l'auteur colle dans son fichier hors Git)."""
    table = TABLE if table is None else table
    lignes = ["delivery_fields:"]
    for cle, valeur in table.items():
        if isinstance(valeur, dict):
            lignes.append(f"  {cle}:")
            lignes += [f"    {sous}: {identifiant}" for sous, identifiant in valeur.items()]
        else:
            lignes.append(f"  {cle}: {valeur}")
    return "\n".join(lignes) + "\n"
