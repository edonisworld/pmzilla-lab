"""
Test statique (aucune base, aucun module de base) de la migration de la vue v_team_flow_inout (mothra-slices tâche 36.1, exception F12, conception D35) :
colonnes, rôle, grain trimestriel clos, ni clé, ni titre, ni personne, ni ligne de ticket, ni grain semaine ou mois, et les deux faces du masquage
(plancher dans la vue, ligne du produit seulement si chaque cellule d'équipe de sa colonne est visible).

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -v

Le numéro de la migration n'est jamais écrit ici : elle se retrouve par son suffixe (renumérotée au rebase si l'ordre de fusion change).
"""
import re
import unittest
from pathlib import Path

from test_contrat_vues import branches_du_select, colonnes_du_select

RACINE = Path(__file__).resolve().parents[2]
MIGRATIONS = RACINE / "db" / "migrations"
SUFFIXE = "_flow_team_flow_inout.sql"
VUE = "v_team_flow_inout"
COLONNES = ["team", "quarter_start", "type_group", "created", "done"]
INTERDITES = ("key", "summary", "title", "description", "assignee", "reporter", "creator", "author", "person", "po", "parent_key", "issue_key",
              "week_start", "month_start", "project")


def sans_commentaires(texte: str) -> str:
    return re.sub(r"--[^\n]*", "", texte)


def fichier() -> Path:
    candidats = sorted(MIGRATIONS.glob(f"*{SUFFIXE}"))
    assert len(candidats) == 1, f"une migration *{SUFFIXE} est attendue"
    return candidats[0]


def code() -> str:
    return sans_commentaires(fichier().read_text(encoding="utf-8"))


def definition(sql: str) -> str:
    return re.search(rf"(?is)CREATE\s+VIEW\s+flow\.{VUE}\s+AS(.*?);\s*(?=RESET\s+ROLE)", sql).group(1)


def elements_finaux(sql: str) -> list:
    """Colonnes du SELECT final de la première branche (avant l'UNION ALL de la ligne du produit)."""
    resultat = []
    for element in colonnes_du_select(definition(sql)):
        m = re.match(r"(?s)(.*?)\s+AS\s+(\w+)$", element.strip())
        resultat.append(m.group(2) if m else element.split(".")[-1].strip())
    return resultat


class MigrationFlowInout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = code()
        cls.vue = definition(cls.sql)

    def test_une_seule_vue_creee_sous_le_proprietaire(self):
        self.assertEqual(re.findall(r"(?i)\bCREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+flow\.(\w+)", self.sql), [VUE])
        self.assertRegex(self.sql, r"(?is)SET\s+LOCAL\s+ROLE\s+pmzilla_owner\s*;")
        self.assertRegex(self.sql, r"(?is)RESET\s+ROLE\s*;")

    def test_ni_table_ni_donnee_ni_mot_de_passe_ni_role(self):
        self.assertNotRegex(self.sql, r"(?i)\bCREATE\s+(TABLE|ROLE)\b|\bALTER\s+TABLE\b|\bDROP\b")
        self.assertNotRegex(self.sql, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(self.sql, r"(?i)\bPASSWORD\b|\bLOGIN\b")

    def test_les_colonnes_sont_celles_du_contrat_dans_l_ordre(self):
        self.assertEqual(elements_finaux(self.sql), COLONNES)

    def test_aucune_colonne_de_cle_de_titre_de_personne_ni_de_grain_semaine_ou_mois(self):
        selection = re.sub(r"(?s)'[^']*'", "''", self.vue)                       # les littéraux ne sont pas des colonnes
        for nom in INTERDITES:
            if nom == "project":
                continue                                                         # lu pour exclure, jamais exposé : voir le test des colonnes finales
            self.assertNotIn(nom, elements_finaux(self.sql), nom)
        self.assertNotRegex(selection, r"(?i)date_trunc\(\s*'(week|month|day)'")
        self.assertNotIn("project", elements_finaux(self.sql))

    def test_grain_trimestre_clos_de_l_annee_retenue(self):
        self.assertRegex(self.vue, r"(?is)date_trunc\(\s*'quarter'")
        self.assertRegex(self.vue, r"(?is)generate_series\(\s*1\s*,\s*4\s*\)")          # les quatre derniers trimestres terminés : jamais le courant

    def test_les_deux_groupes_de_types_et_les_exclusions(self):
        self.assertRegex(self.vue, r"(?is)'story'")
        self.assertRegex(self.vue, r"(?is)'defect'")
        self.assertRegex(self.vue, r"(?is)ref_unplanned_types")                         # types de défaut du référentiel, jamais de liste en dur
        self.assertRegex(self.vue, r"(?is)out_of_export_at\s+IS\s+NULL")
        self.assertRegex(self.vue, r"(?is)NOT\s+IN\s*\(\s*'epic'\s*,\s*'initiative'\s*\)")      # types de portefeuille (R-150, point ouvert pour les projets)

    def test_termine_au_sens_des_rapports_de_flux(self):
        self.assertRegex(self.vue, r"(?is)lower\(\s*\w+\.?status_category\s*\)\s*=\s*'done'")
        self.assertRegex(self.vue, r"(?is)resolved_at\s+IS\s+NOT\s+NULL")

    def test_rattachement_par_l_equipe_du_ticket_seulement(self):
        self.assertRegex(self.vue, r"(?is)LEFT\s+JOIN\s+flow\.teams\s+\w+\s+ON\s+\w+\.id\s*=\s*i\.team_id")
        self.assertNotRegex(self.vue, r"(?is)flow\.links|parent_key|issue_teams")      # jamais par lien, parent ou épic

    def test_sans_equipe_et_ligne_du_produit(self):
        self.assertIn("'(sans équipe)'", self.vue)
        self.assertIn("'(produit)'", self.vue)
        self.assertRegex(self.vue, r"(?is)UNION\s+ALL")

    def test_chaque_compte_passe_par_le_masque_de_la_base_dans_les_deux_branches(self):
        branches = branches_du_select(self.vue)
        self.assertEqual(len(branches), 2)
        for branche in branches:
            self.assertEqual(len(branche), len(COLONNES))
            for position in (3, 4):                                                # created, done
                self.assertTrue(re.match(r"(?is)flow\.mask_count\(", branche[position].strip()), branche[position])

    def test_ligne_du_produit_visible_seulement_si_chaque_cellule_d_equipe_de_sa_colonne_l_est(self):
        self.assertRegex(self.vue, r"(?is)bool_and\(\s*\w+\s*>=\s*5\s*\)")
        self.assertRegex(self.vue, r"(?is)CASE\s+WHEN\s+\w+\.?\w*_ok\s+THEN")

    def test_droits_au_seul_role_des_vues(self):
        brut = fichier().read_text(encoding="utf-8")
        self.assertRegex(brut, rf"(?is)REVOKE\s+ALL\s+ON\s+flow\.{VUE}\s+FROM\s+PUBLIC,\s*pmzilla_flow,\s*pmzilla_flow_ro,\s*pmzilla_quality_views")
        self.assertRegex(brut, rf"(?is)GRANT\s+SELECT\s+ON\s+flow\.{VUE}\s+TO\s+pmzilla_flow_views\s*;")
        self.assertEqual(len(re.findall(r"(?i)\bGRANT\b", sans_commentaires(brut))), 1)

    def test_l_en_tete_dit_la_renumerotation_et_les_relations_non_implementees(self):
        en_tete = fichier().read_text(encoding="utf-8").split("SET LOCAL ROLE", 1)[0]
        self.assertRegex(en_tete, r"(?i)renum")
        self.assertRegex(en_tete, r"T13")
        self.assertRegex(en_tete, r"(?i)projets? exclus")


if __name__ == "__main__":
    unittest.main()
