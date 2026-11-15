"""
Test statique du contrat des vues (contrats/vues.json, mothra-slices D2, tâche 4.2) contre les migrations des schémas flow et quality,
lues comme des fichiers : aucune base, aucun réseau.

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -v

Une vue du contrat doit être créée par une migration (et non supprimée depuis), accordée au rôle de son genre, avoir ses colonnes de compte
masquées par la fonction de masque et ses autres colonnes dans sa définition ; le contrat ne nomme ni table, ni colonne de texte.
"""
import json
import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
CONTRAT = RACINE / "contrats" / "vues.json"
MIGRATIONS = RACINE / "db" / "migrations"

ROLE_PAR_GENRE = {"flow": "pmzilla_flow_views", "quality": "pmzilla_quality_views"}

# Colonnes qui portent du texte de ticket ou de personne : jamais exposées par une vue du contrat (invariant 4 de Mothra).
COLONNES_DE_TEXTE = {
    "key", "issue_key", "title", "summary", "description", "text", "body", "content", "comment",
    "assignee", "reporter", "creator", "author", "person", "email", "user",
}

RE_VUE = re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(\w+)\.(\w+)\s+AS\b(.*?);", re.S | re.I)
RE_SUPPRESSION = re.compile(r"DROP\s+VIEW\s+(?:IF\s+EXISTS\s+)?([^;]+);", re.I)
RE_TABLE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\.(\w+)", re.I)
RE_ACCORD = re.compile(r"GRANT\s+SELECT\s+ON\s+([^;]*?)\s+TO\s+([^;]+);", re.I)
RE_RETRAIT = re.compile(r"REVOKE\s+(?:SELECT|ALL(?:\s+PRIVILEGES)?)\s+ON\s+([^;]*?)\s+FROM\s+([^;]+);", re.I)
RE_NOM = re.compile(r"(\w+)\.(\w+)")


def lire_migrations() -> str:
    morceaux = []
    for fichier in sorted(MIGRATIONS.glob("*.sql")):
        morceaux.append(re.sub(r"--[^\n]*", "", fichier.read_text(encoding="utf-8")))
    return "\n".join(morceaux)


def etat_des_migrations(sql: str) -> tuple:
    """Vues et droits existant après toutes les migrations, créations, suppressions, GRANT et REVOKE suivis dans l'ordre du texte.

    Retourne (vues, accords) : « schéma.nom » vers la dernière définition, et l'ensemble des couples (« schéma.nom », rôle).
    Une suppression de vue efface aussi ses droits ; une vue recréée repart sans droit.
    Limites connues, que ce test statique ne suit pas : DROP … CASCADE d'une table qui emporte une vue, ALTER VIEW … RENAME TO,
    les droits donnés en bloc (ON ALL TABLES IN SCHEMA) et le SQL construit dans un bloc DO ou par EXECUTE format. Une vue du contrat
    dont l'existence ou les droits ne passent que par là serait vue comme absente ou non accordée : le test refuse alors, il ne laisse pas passer.
    """
    evenements = (
        [(m.start(), "creer", m) for m in RE_VUE.finditer(sql)]
        + [(m.start(), "supprimer", m) for m in RE_SUPPRESSION.finditer(sql)]
        + [(m.start(), "accorder", m) for m in RE_ACCORD.finditer(sql)]
        + [(m.start(), "retirer", m) for m in RE_RETRAIT.finditer(sql)]
    )
    vues: dict = {}
    accords: set = set()
    for _, genre, m in sorted(evenements, key=lambda e: e[0]):
        if genre == "creer":
            vues[f"{m.group(1)}.{m.group(2)}"] = m.group(3)
        elif genre == "supprimer":
            for schema, nom in RE_NOM.findall(m.group(1)):
                vues.pop(f"{schema}.{nom}", None)
                accords = {(objet, role) for objet, role in accords if objet != f"{schema}.{nom}"}
        else:
            objets = [o.strip() for o in m.group(1).split(",")]
            roles = [r.strip() for r in m.group(2).split(",")]
            for objet in objets:
                for role in roles:
                    if genre == "accorder":
                        accords.add((objet, role))
                    else:
                        accords.discard((objet, role))
    return vues, accords


def vues_des_migrations(sql: str) -> dict:
    return etat_des_migrations(sql)[0]


def tables_des_migrations(sql: str) -> set:
    return {f"{m.group(1)}.{m.group(2)}" for m in RE_TABLE.finditer(sql)}


def vues_accordees(sql: str) -> set:
    return etat_des_migrations(sql)[1]


def branches_du_select(definition: str) -> list:
    """Éléments de niveau zéro de chaque branche d'un UNION [ALL] de niveau zéro du SELECT final : une liste par branche, la première étant celle
    de colonnes_du_select. Sans UNION, une seule liste."""
    debut = _debut_du_select(definition)
    if debut is None:
        return []
    texte = definition[debut.end():]
    coupes, profondeur = [], 0
    for i, c in enumerate(texte):
        profondeur += (c == "(") - (c == ")")
        if profondeur == 0 and c in "uU" and (i == 0 or not (texte[i - 1].isalnum() or texte[i - 1] == "_")):
            m = re.compile(r"UNION\s+(?:ALL\s+)?SELECT\b", re.I).match(texte, i)
            if m is not None:
                coupes.append((i, m.end()))
    morceaux, depart = [], 0
    for debut_union, fin_union in coupes:
        morceaux.append(texte[depart:debut_union])
        depart = fin_union
    morceaux.append(texte[depart:])
    return [_elements_du_select(m) for m in morceaux]


def _debut_du_select(definition: str):
    debut = re.search(r"\bSELECT\b", definition, re.I)
    if re.match(r"\s*WITH\b", definition, re.I):
        profondeur = 0
        debut = None
        for i, c in enumerate(definition):
            profondeur += (c == "(") - (c == ")")
            precedent = definition[i - 1] if i else " "
            if profondeur == 0 and not (precedent.isalnum() or precedent == "_"):
                debut = re.compile(r"SELECT\b", re.I).match(definition, i)
                if debut is not None:
                    break
    return debut


def _elements_du_select(texte: str) -> list:
    elements, courant, profondeur, i = [], [], 0, 0
    while i < len(texte):
        c = texte[i]
        if profondeur == 0 and re.match(r"FROM\b", texte[i:], re.I) and (i == 0 or not (texte[i - 1].isalnum() or texte[i - 1] == "_")):
            break
        if c == "(":
            profondeur += 1
        elif c == ")":
            profondeur -= 1
        if c == "," and profondeur == 0:
            elements.append("".join(courant).strip())
            courant = []
        else:
            courant.append(c)
        i += 1
    elements.append("".join(courant).strip())
    return elements


def est_compte_masque_sans_alias(element: str) -> bool:
    """Colonne de compte d'une branche d'UNION après la première (sans alias : la colonne se lit par sa position) : `mask_*( … )` ou un
    `CASE WHEN … END` sans ELSE (qui donne un nul sous le seuil), alias facultatif ; jamais un compte nu."""
    if re.match(r"(?:\w+\.)?mask_\w+\(", element, re.I):
        return True
    return re.fullmatch(r"CASE\s+WHEN\b(?:(?!\bELSE\b).)*\bEND(?:\s+AS\s+\w+)?", element, re.I | re.S) is not None


def colonnes_du_select(definition: str) -> list:
    """Éléments de niveau zéro de la liste du premier SELECT, jusqu'au FROM de niveau zéro (ou la fin)."""
    debut = re.search(r"\bSELECT\b", definition, re.I)
    if re.match(r"\s*WITH\b", definition, re.I):
        # vue à expressions de table (WITH …) : le SELECT qui compte est le premier de niveau zéro, celui qui suit la dernière expression
        profondeur = 0
        debut = None
        for i, c in enumerate(definition):
            profondeur += (c == "(") - (c == ")")
            precedent = definition[i - 1] if i else " "
            if profondeur == 0 and not (precedent.isalnum() or precedent == "_"):
                debut = re.compile(r"SELECT\b", re.I).match(definition, i)
                if debut is not None:
                    break
    if debut is None:
        return []
    texte = definition[debut.end():]
    elements, courant, profondeur, i = [], [], 0, 0
    while i < len(texte):
        c = texte[i]
        if profondeur == 0 and re.match(r"FROM\b", texte[i:], re.I) and (i == 0 or not (texte[i - 1].isalnum() or texte[i - 1] == "_")):
            break
        if c == "(":
            profondeur += 1
        elif c == ")":
            profondeur -= 1
        if c == "," and profondeur == 0:
            elements.append("".join(courant).strip())
            courant = []
        else:
            courant.append(c)
        i += 1
    elements.append("".join(courant).strip())
    return elements


def est_compte_masque(element: str, colonne: str) -> bool:
    """L'élément est exactement `[schéma.]mask_*( … ) AS colonne`, parenthèses équilibrées, rien d'autre autour."""
    m = re.match(r"(?:\w+\.)?mask_\w+\(", element, re.I)
    if m is None:
        return False
    profondeur, fin = 1, None
    for i in range(m.end(), len(element)):
        profondeur += (element[i] == "(") - (element[i] == ")")
        if profondeur == 0:
            fin = i
            break
    if fin is None:
        return False
    return re.fullmatch(r"\s+AS\s+" + re.escape(colonne), element[fin + 1:], re.I) is not None


def est_mesure_masquee(element: str, colonne: str) -> bool:
    """Colonne maskable (statistique, part) du SELECT final : `CASE WHEN … END AS colonne` sans ELSE (nul sous le seuil), ou `mask_*( … ) AS colonne`."""
    return est_compte_masque(element, colonne) or (
        re.fullmatch(r"CASE\s+WHEN\b(?:(?!\bELSE\b).)*\bEND\s+AS\s+" + re.escape(colonne), element, re.I | re.S) is not None
    )


def est_colonne_simple(element: str, colonne: str) -> bool:
    """`… AS colonne`, ou bien `colonne` / `alias.colonne` nu."""
    return (
        re.search(r"\bAS\s+" + re.escape(colonne) + r"$", element, re.I) is not None
        or re.fullmatch(r"(?:\w+\.)?" + re.escape(colonne), element, re.I) is not None
    )


def erreurs_contrat(contrat: dict, sql: str) -> list:
    """Écarts entre le contrat et les migrations, chacun nommant la vue ou la colonne en cause."""
    erreurs = []
    vues = vues_des_migrations(sql)
    tables = tables_des_migrations(sql)
    accords = vues_accordees(sql)
    for vue in contrat["views"]:
        nom = f"{vue['schema']}.{vue['name']}"
        if nom in tables:
            erreurs.append(f"table nommée comme une vue : {nom}")
            continue
        if nom not in vues:
            erreurs.append(f"vue absente des migrations : {nom}")
            continue
        if (nom, ROLE_PAR_GENRE[vue["roleKind"]]) not in accords:
            erreurs.append(f"vue non accordée au rôle {ROLE_PAR_GENRE[vue['roleKind']]} : {nom}")
        definition = vues[nom]
        elements = colonnes_du_select(definition)
        for colonne in vue["countColumns"]:
            if not any(est_compte_masque(e, colonne) for e in elements):
                erreurs.append(f"colonne de compte non masquée par la vue : {nom}.{colonne}")
        branches = branches_du_select(definition)
        for rang, branche in enumerate(branches[1:], start=2):       # chaque branche d'UNION : le compte, à la position de la première, est masqué
            for colonne in vue["countColumns"]:
                positions = [k for k, e in enumerate(elements) if est_compte_masque(e, colonne)]
                if positions and (positions[0] >= len(branche) or not est_compte_masque_sans_alias(branche[positions[0]])):
                    erreurs.append(f"colonne de compte non masquée dans la branche {rang} de l'UNION : {nom}.{colonne}")
        for colonne in vue["plainColumns"]:
            if not any(est_colonne_simple(e, colonne) for e in elements):
                erreurs.append(f"colonne absente de la vue : {nom}.{colonne}")
        # R-20261030-49 : statistiques et parts (maskableColumns), masquées par la vue elle-même (CASE WHEN … END sans ELSE, ou mask_*), à la
        # même position dans chaque branche d'UNION ; ajout : ce que le contrôle des colonnes simples faisait pour elles reste fait ici
        for colonne in vue.get("maskableColumns", []):
            if not any(est_mesure_masquee(e, colonne) for e in elements):
                erreurs.append(f"colonne maskable absente ou non masquée par la vue : {nom}.{colonne}")
                continue
            positions = [k for k, e in enumerate(elements) if est_mesure_masquee(e, colonne)]
            for rang, branche in enumerate(branches[1:], start=2):
                if positions[0] >= len(branche) or not est_compte_masque_sans_alias(branche[positions[0]]):
                    erreurs.append(f"colonne maskable non masquée dans la branche {rang} de l'UNION : {nom}.{colonne}")
        for colonne in vue["countColumns"] + vue["plainColumns"] + vue.get("maskableColumns", []):
            if colonne in COLONNES_DE_TEXTE:
                erreurs.append(f"colonne de texte refusée : {nom}.{colonne}")
    return erreurs


FAUX_SQL = """
CREATE TABLE flow.issues (id int, title text);
CREATE TABLE flow.teams (id int, name text);
CREATE VIEW flow.v_a AS
SELECT t.name AS team, i.status, flow.mask_count(count(*)) AS tickets FROM flow.issues i GROUP BY 1, 2;
GRANT SELECT ON flow.v_a TO pmzilla_flow_views;
CREATE VIEW flow.v_nue AS SELECT i.status, count(*) AS tickets FROM flow.issues i GROUP BY 1;
GRANT SELECT ON flow.v_nue TO pmzilla_flow_views;
CREATE VIEW flow.v_sans_accord AS SELECT flow.mask_count(count(*)) AS tickets FROM flow.issues;
CREATE VIEW flow.v_morte AS SELECT flow.mask_count(count(*)) AS tickets FROM flow.issues;
GRANT SELECT ON flow.v_morte TO pmzilla_flow_views;
DROP VIEW flow.v_morte;
CREATE VIEW flow.v_enveloppe AS SELECT coalesce(flow.mask_count(count(*)), 0) AS tickets FROM flow.issues;
GRANT SELECT ON flow.v_enveloppe TO pmzilla_flow_views;
CREATE VIEW flow.v_double AS SELECT flow.mask_count(count(*)) AS links, count(*) AS tickets FROM flow.issues;
GRANT SELECT ON flow.v_double TO pmzilla_flow_views;
CREATE VIEW quality.v_q AS SELECT t.name AS team, quality.mask_count(count(*)) AS stories FROM quality.stories s GROUP BY 1;
GRANT SELECT ON quality.v_q TO pmzilla_quality_views;
CREATE VIEW flow.v_retiree AS SELECT flow.mask_count(count(*)) AS tickets FROM flow.issues;
GRANT SELECT ON flow.v_retiree TO pmzilla_flow_views;
REVOKE ALL ON flow.v_retiree FROM pmzilla_flow_views;
CREATE VIEW flow.v_rendue AS SELECT flow.mask_count(count(*)) AS tickets FROM flow.issues;
REVOKE SELECT ON flow.v_rendue FROM pmzilla_flow_views;
GRANT SELECT ON flow.v_rendue TO pmzilla_flow_views;
CREATE VIEW flow.v_recree AS SELECT flow.mask_count(count(*)) AS tickets FROM flow.issues;
GRANT SELECT ON flow.v_recree TO pmzilla_flow_views;
DROP VIEW flow.v_recree;
CREATE VIEW flow.v_recree AS SELECT flow.mask_count(count(*)) AS tickets FROM flow.issues;
CREATE VIEW flow.v_une AS SELECT flow.mask_count(count(*)) AS tickets FROM flow.issues;
CREATE VIEW flow.v_deux AS SELECT flow.mask_count(count(*)) AS tickets FROM flow.issues;
GRANT SELECT ON flow.v_une, flow.v_deux TO pmzilla_flow_views;
DROP VIEW IF EXISTS flow.v_une, flow.v_deux CASCADE;
CREATE VIEW flow.v_colonnes AS SELECT i.status, count(*) AS tickets, flow.mask_count(count(*)) AS autres FROM flow.issues i;
GRANT SELECT ON flow.v_colonnes TO pmzilla_flow_views;
"""


def faux_contrat(**vue) -> dict:
    base = {"name": "v_a", "schema": "flow", "roleKind": "flow", "countColumns": ["tickets"], "plainColumns": ["team", "status"]}
    base.update(vue)
    return {"views": [base]}


FAUX_SQL_CTE_ET_UNION = """
CREATE VIEW flow.v_cte_nue AS WITH t AS (SELECT flow.mask_count(count(*)) AS tickets FROM flow.issues) SELECT tickets FROM t;
GRANT SELECT ON flow.v_cte_nue TO pmzilla_flow_views;
CREATE VIEW flow.v_cte_ok AS WITH t AS (SELECT count(*) AS n FROM flow.issues) SELECT flow.mask_count(n) AS tickets FROM t;
GRANT SELECT ON flow.v_cte_ok TO pmzilla_flow_views;
CREATE VIEW flow.v_union_ok AS
SELECT 'a' AS team, flow.mask_count(count(*)) AS tickets FROM flow.issues
UNION ALL
SELECT 'b', CASE WHEN count(*) >= 5 THEN count(*) END FROM flow.issues;
GRANT SELECT ON flow.v_union_ok TO pmzilla_flow_views;
CREATE VIEW flow.v_union_nue AS
SELECT 'a' AS team, flow.mask_count(count(*)) AS tickets FROM flow.issues
UNION ALL
SELECT 'b', count(*) FROM flow.issues;
GRANT SELECT ON flow.v_union_nue TO pmzilla_flow_views;
CREATE VIEW flow.v_union_enveloppe AS
SELECT 'a' AS team, flow.mask_count(count(*)) AS tickets FROM flow.issues
UNION ALL
SELECT 'b', coalesce(flow.mask_count(count(*)), 0) FROM flow.issues;
GRANT SELECT ON flow.v_union_enveloppe TO pmzilla_flow_views;
CREATE VIEW flow.v_union_trois AS
SELECT 'a' AS team, flow.mask_count(count(*)) AS tickets FROM flow.issues
UNION ALL
SELECT 'b', flow.mask_count(count(*)) FROM flow.issues
UNION ALL
SELECT 'c', count(*) FROM flow.issues;
GRANT SELECT ON flow.v_union_trois TO pmzilla_flow_views;
"""


class GardeCteEtUnion(unittest.TestCase):
    """Gardes de la tâche 15.2 : vue à expression de table (WITH) et vue à plusieurs branches (UNION ALL, la ligne pooled_year de 0026 comprise)."""

    def erreurs(self, nom):
        return erreurs_contrat(faux_contrat(name=nom, plainColumns=[]), FAUX_SQL_CTE_ET_UNION)

    def test_with_dont_le_masque_est_dans_l_expression_de_table_mais_pas_dans_le_select_final_est_refuse(self):
        self.assertEqual(self.erreurs("v_cte_nue"), ["colonne de compte non masquée par la vue : flow.v_cte_nue.tickets"])

    def test_with_dont_le_select_final_masque_est_accepte(self):
        self.assertEqual(self.erreurs("v_cte_ok"), [])

    def test_union_dont_chaque_branche_masque_est_acceptee(self):
        self.assertEqual(self.erreurs("v_union_ok"), [])

    def test_union_dont_la_deuxieme_branche_laisse_un_compte_nu_est_refusee(self):
        self.assertEqual(self.erreurs("v_union_nue"), ["colonne de compte non masquée dans la branche 2 de l'UNION : flow.v_union_nue.tickets"])

    def test_masque_enveloppe_dans_la_deuxieme_branche_est_refuse(self):
        self.assertEqual(self.erreurs("v_union_enveloppe"),
                         ["colonne de compte non masquée dans la branche 2 de l'UNION : flow.v_union_enveloppe.tickets"])

    def test_la_troisieme_branche_est_controlee_aussi(self):
        self.assertEqual(self.erreurs("v_union_trois"), ["colonne de compte non masquée dans la branche 3 de l'UNION : flow.v_union_trois.tickets"])

    def test_la_ligne_pooled_year_de_0026_est_controlee_branche_par_branche(self):
        vues = vues_des_migrations(lire_migrations())
        branches = branches_du_select(vues["flow.v_team_lead_time_throughput"])
        self.assertEqual(len(branches), 2)
        self.assertEqual(len(branches[0]), len(branches[1]))
        for colonne in ("throughput", "items_lt", "items_ct", "items_old", "items_without_commitment"):
            k = next(k for k, e in enumerate(branches[0]) if est_compte_masque(e, colonne))
            self.assertTrue(est_compte_masque_sans_alias(branches[1][k]), colonne)

    # (c) mask_count_zero refusé comme colonne de compte : non fait. items_without_commitment de 0026 passe par mask_count_zero et le contrat la
    # déclare colonne de compte : une garde qui refuserait mask_count_zero contredirait cette colonne (point arrêté, à décider par l'auteur).


class ContratDesVues(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contrat = json.loads(CONTRAT.read_text(encoding="utf-8"))
        cls.sql = lire_migrations()

    def test_le_contrat_de_la_tranche_0_decrit_une_vue_de_flux(self):
        self.assertEqual([(v["schema"], v["name"], v["roleKind"]) for v in self.contrat["views"]],
                         [("flow", "v_team_status", "flow")] + [("flow", nom, "flow") for nom in (
                             "v_team_lead_time_throughput", "v_task_without_team_share", "v_team_ready_queue", "v_team_blocked_share",
                             "v_unplanned_share", "v_team_flow_inout")])
        self.assertEqual(self.contrat["views"][0]["countColumns"], ["tickets"])

    def test_le_contrat_correspond_aux_migrations(self):
        self.assertEqual(erreurs_contrat(self.contrat, self.sql), [])

    def test_aucune_table_dans_le_contrat(self):
        tables = tables_des_migrations(self.sql)
        for vue in self.contrat["views"]:
            self.assertNotIn(f"{vue['schema']}.{vue['name']}", tables)

    def test_aucune_colonne_de_texte_dans_le_contrat(self):
        for vue in self.contrat["views"]:
            self.assertEqual(COLONNES_DE_TEXTE & set(vue["countColumns"] + vue["plainColumns"]), set())


class GardeDuTest(unittest.TestCase):
    """Le test statique refuse bien : il est éprouvé sur de fausses migrations."""

    def test_un_contrat_correct_passe(self):
        self.assertEqual(erreurs_contrat(faux_contrat(), FAUX_SQL), [])

    def test_vue_absente_des_migrations_nommee(self):
        self.assertEqual(erreurs_contrat(faux_contrat(name="v_inconnue"), FAUX_SQL), ["vue absente des migrations : flow.v_inconnue"])

    def test_vue_supprimee_par_une_migration_nommee(self):
        self.assertEqual(erreurs_contrat(faux_contrat(name="v_morte", plainColumns=[]), FAUX_SQL), ["vue absente des migrations : flow.v_morte"])

    def test_nom_de_table_refuse(self):
        self.assertEqual(erreurs_contrat(faux_contrat(name="issues"), FAUX_SQL), ["table nommée comme une vue : flow.issues"])

    def test_vue_non_accordee_refusee(self):
        erreurs = erreurs_contrat(faux_contrat(name="v_sans_accord", plainColumns=[]), FAUX_SQL)
        self.assertEqual(erreurs, ["vue non accordée au rôle pmzilla_flow_views : flow.v_sans_accord"])

    def test_colonne_de_compte_non_masquee_refusee(self):
        erreurs = erreurs_contrat(faux_contrat(name="v_nue", countColumns=["tickets"], plainColumns=["status"]), FAUX_SQL)
        self.assertEqual(erreurs, ["colonne de compte non masquée par la vue : flow.v_nue.tickets"])

    def test_masque_enveloppe_dans_une_autre_fonction_refuse(self):
        erreurs = erreurs_contrat(faux_contrat(name="v_enveloppe", plainColumns=[]), FAUX_SQL)
        self.assertEqual(erreurs, ["colonne de compte non masquée par la vue : flow.v_enveloppe.tickets"])

    def test_masque_sur_une_autre_colonne_refuse(self):
        erreurs = erreurs_contrat(faux_contrat(name="v_double", plainColumns=[]), FAUX_SQL)
        self.assertEqual(erreurs, ["colonne de compte non masquée par la vue : flow.v_double.tickets"])

    def test_vue_quality_accordee_au_role_quality_acceptee(self):
        contrat = faux_contrat(name="v_q", schema="quality", roleKind="quality", countColumns=["stories"], plainColumns=["team"])
        self.assertEqual(erreurs_contrat(contrat, FAUX_SQL), [])

    def test_vue_quality_accordee_au_role_flow_refusee(self):
        contrat = faux_contrat(name="v_q", schema="quality", roleKind="flow", countColumns=["stories"], plainColumns=["team"])
        self.assertEqual(erreurs_contrat(contrat, FAUX_SQL), ["vue non accordée au rôle pmzilla_flow_views : quality.v_q"])

    def test_droit_retire_par_revoke_refuse(self):
        erreurs = erreurs_contrat(faux_contrat(name="v_retiree", plainColumns=[]), FAUX_SQL)
        self.assertEqual(erreurs, ["vue non accordée au rôle pmzilla_flow_views : flow.v_retiree"])

    def test_droit_rendu_apres_revoke_accepte(self):
        self.assertEqual(erreurs_contrat(faux_contrat(name="v_rendue", plainColumns=[]), FAUX_SQL), [])

    def test_vue_recreee_apres_suppression_repart_sans_droit(self):
        erreurs = erreurs_contrat(faux_contrat(name="v_recree", plainColumns=[]), FAUX_SQL)
        self.assertEqual(erreurs, ["vue non accordée au rôle pmzilla_flow_views : flow.v_recree"])

    def test_drop_view_de_plusieurs_vues_les_supprime_toutes(self):
        for nom in ("v_une", "v_deux"):
            erreurs = erreurs_contrat(faux_contrat(name=nom, plainColumns=[]), FAUX_SQL)
            self.assertEqual(erreurs, [f"vue absente des migrations : flow.{nom}"])

    def test_colonne_simple_cherchee_dans_la_liste_du_select_seulement(self):
        contrat = faux_contrat(name="v_colonnes", countColumns=["autres"], plainColumns=["status", "issues", "tickets"])
        self.assertEqual(erreurs_contrat(contrat, FAUX_SQL), ["colonne absente de la vue : flow.v_colonnes.issues"])

    def test_colonne_de_compte_non_masquee_nommee_meme_si_presente_en_clair(self):
        contrat = faux_contrat(name="v_colonnes", countColumns=["tickets"], plainColumns=[])
        self.assertEqual(erreurs_contrat(contrat, FAUX_SQL), ["colonne de compte non masquée par la vue : flow.v_colonnes.tickets"])

    def test_colonne_de_texte_refusee(self):
        erreurs = erreurs_contrat(faux_contrat(plainColumns=["team", "title"]), FAUX_SQL)
        self.assertIn("colonne de texte refusée : flow.v_a.title", erreurs)

    def test_colonne_inconnue_de_la_vue_nommee(self):
        erreurs = erreurs_contrat(faux_contrat(plainColumns=["team", "sprint"]), FAUX_SQL)
        self.assertEqual(erreurs, ["colonne absente de la vue : flow.v_a.sprint"])


FAUX_SQL_MASKABLES = """
CREATE VIEW flow.v_m AS
SELECT flow.mask_count(count(*)) AS n, CASE WHEN count(*) >= 5 THEN round(avg(x), 1) END AS moyenne FROM flow.issues;
GRANT SELECT ON flow.v_m TO pmzilla_flow_views;
CREATE VIEW flow.v_m_nue AS SELECT flow.mask_count(count(*)) AS n, avg(x) AS moyenne FROM flow.issues;
GRANT SELECT ON flow.v_m_nue TO pmzilla_flow_views;
CREATE VIEW flow.v_m_union AS
SELECT 'a' AS team, flow.mask_count(count(*)) AS n, CASE WHEN count(*) >= 5 THEN 1 END AS moyenne FROM flow.issues
UNION ALL
SELECT 'b', flow.mask_count(count(*)), avg(x) FROM flow.issues;
GRANT SELECT ON flow.v_m_union TO pmzilla_flow_views;
"""


class GardeDesColonnesMaskables(unittest.TestCase):
    """R-20261030-49 : chaque colonne de maskableColumns existe dans le SELECT final de la vue, masquée par la vue, dans chaque branche d'UNION."""

    def erreurs(self, nom, maskables):
        contrat = faux_contrat(name=nom, countColumns=["n"], plainColumns=[], maskableColumns=maskables)
        return erreurs_contrat(contrat, FAUX_SQL_MASKABLES)

    def test_une_colonne_maskable_masquee_par_un_case_est_acceptee(self):
        self.assertEqual(self.erreurs("v_m", ["moyenne"]), [])

    def test_une_colonne_maskable_absente_de_la_migration_est_refusee(self):
        self.assertEqual(self.erreurs("v_m", ["inconnue"]), ["colonne maskable absente ou non masquée par la vue : flow.v_m.inconnue"])

    def test_une_colonne_maskable_nue_est_refusee(self):
        self.assertEqual(self.erreurs("v_m_nue", ["moyenne"]), ["colonne maskable absente ou non masquée par la vue : flow.v_m_nue.moyenne"])

    def test_une_colonne_maskable_nue_dans_la_deuxieme_branche_est_refusee(self):
        self.assertEqual(self.erreurs("v_m_union", ["moyenne"]),
                         ["colonne maskable non masquée dans la branche 2 de l'UNION : flow.v_m_union.moyenne"])

    def test_une_colonne_maskable_de_texte_est_refusee(self):
        self.assertIn("colonne de texte refusée : flow.v_m.title", self.erreurs("v_m", ["title"]))

    def test_les_colonnes_maskables_du_contrat_reel_sont_verifiees_et_non_vides(self):
        contrat = json.loads(CONTRAT.read_text(encoding="utf-8"))
        self.assertTrue(any(v.get("maskableColumns") for v in contrat["views"]))


if __name__ == "__main__":
    unittest.main()
