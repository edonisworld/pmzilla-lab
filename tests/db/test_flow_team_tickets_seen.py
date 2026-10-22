"""Vue des équipes vues sur les tickets, pour la revue du catalogue de check-teams (change database-only, D13, tâche 14.6).

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Les tests sans base (SansBase) tournent toujours : lecture du fichier de migration. Les autres utilisent la base jetable de
test_flow_schema.py et sont sautés sans elle (bash tools/dbtest.sh db). La migration est retrouvée par sa description
(flow_team_tickets_seen), pas par son numéro. Données inventées.
"""
import re
import unittest

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402

VUE = "flow.v_team_tickets_seen"


def fichier_migration():
    candidats = [m for m in db.lister_migrations() if m.nom.endswith("_flow_team_tickets_seen.sql")]
    return candidats[0] if len(candidats) == 1 else None


class SansBase(unittest.TestCase):
    def texte(self):
        migration = fichier_migration()
        self.assertIsNotNone(migration, "une migration *_flow_team_tickets_seen.sql est attendue")
        return migration.chemin.read_text(encoding="utf-8")

    def code(self):
        return re.sub(r"--[^\n]*", "", self.texte())

    def test_une_vue_sous_le_proprietaire_sans_donnee_ni_mot_de_passe_ni_role(self):
        texte = self.texte()
        self.assertRegex(texte.splitlines()[0], r"^-- Schéma touché : flow")
        code = self.code()
        self.assertEqual(len(re.findall(r"(?i)\bCREATE\s+(?:OR\s+REPLACE\s+)?VIEW\b", code)), 1)
        self.assertRegex(code, r"(?is)SET\s+LOCAL\s+ROLE\s+pmzilla_owner\s*;.*CREATE\s+VIEW\s+flow\.v_team_tickets_seen\s+AS")
        self.assertNotRegex(code, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(code, r"(?i)\bPASSWORD\b")
        self.assertNotRegex(code, r"(?i)\b(CREATE|ALTER|DROP)\s+(ROLE|TABLE|FUNCTION)\b")
        self.assertNotRegex(code, r"(?i)\bLOGIN\b")

    def test_select_au_seul_role_en_lecture_seule_et_les_autres_droits_retires(self):
        code = self.code()
        grants = re.findall(r"(?is)\bGRANT\b.*?;", code)
        self.assertEqual(len(grants), 1, grants)
        self.assertRegex(grants[0], r"(?is)GRANT\s+SELECT\s+ON\s+flow\.v_team_tickets_seen\s+TO\s+pmzilla_flow_ro\s*;")
        revoke = re.search(r"(?is)\bREVOKE\b.*?;", code)
        self.assertIsNotNone(revoke)
        for role in ("PUBLIC", "pmzilla_flow", "pmzilla_flow_views", "pmzilla_quality_views"):
            self.assertRegex(revoke.group(0), rf"\b{role}\b")
        self.assertLess(code.index("REVOKE"), code.index("GRANT"))

    def test_aucun_masquage_et_aucune_colonne_de_cle_ni_d_etiquette(self):
        code = self.code()
        self.assertNotIn("mask_count", code)
        vue = re.search(r"(?is)CREATE\s+VIEW\s+flow\.v_team_tickets_seen\s+AS(.*?);", code).group(1)
        alias = re.findall(r"(?i)\bAS\s+([a-z_]+)", vue)
        self.assertEqual(alias, ["team_id", "team_name", "tickets"])
        for nom in alias:
            self.assertNotIn("key", nom)
            self.assertNotIn("label", nom)
        self.assertRegex(vue, r"(?i)out_of_export_at\s+IS\s+NULL")
        self.assertRegex(vue, r"(?i)FROM\s+flow\.issue_teams")

    def test_la_migration_suit_celle_de_l_historique_et_le_numero_est_libre(self):
        numeros = {m.nom.split("_", 1)[1]: m.numero for m in db.lister_migrations()}
        self.assertGreater(numeros["flow_team_tickets_seen.sql"], numeros["flow_history_not_found.sql"])
        liste = sorted(numeros.values())
        self.assertEqual(liste, list(range(1, len(liste) + 1)))                                         # sans trou ni doublon


class AvecBase(unittest.TestCase):
    """Même base jetable que SchemaFlow (migrations appliquées, base supprimée à la fin)."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def ecrit(self, c, role, sql):
        """Vrai si l'écriture réussit ; toute erreur de la base (droits ou vue non modifiable) est un refus."""
        try:
            with c.transaction():
                c.execute(f"SET LOCAL ROLE {role}")
                c.execute(sql)
                return True
        except db.psycopg.Error:
            return False

    def jeu(self, c):
        """Alpha : un ticket vu et un ticket sorti de l'export ; Beta : un ticket partagé avec Alpha ; Gamma : aucun ticket."""
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.teams (name) VALUES ('Alpha'), ('Beta'), ('Gamma')")
        for cle, sortie in (("PROJ-1", False), ("PROJ-2", True), ("PROJ-3", False), ("PROJ-4", False)):
            c.execute("INSERT INTO flow.issues (key, project, type, status, created_at, updated_at, team_id, out_of_export_at) "
                      "VALUES (%s, 'PROJ', 'Story', 'Open', now(), now(), 1, CASE WHEN %s THEN now() END)", (cle, sortie))
        c.execute("INSERT INTO flow.issue_teams (issue_key, team_id, position) VALUES "
                  "('PROJ-1', 1, 1), ('PROJ-2', 1, 1), ('PROJ-3', 1, 1), ('PROJ-3', 2, 2)")      # PROJ-4 : aucune équipe
        c.execute("RESET ROLE")
        c.commit()

    def test_contenu_sortis_de_l_export_ecartes_deux_equipes_comptees_chacune_un_compte_de_un_montre(self):
        c = self.conn()
        self.jeu(c)
        c.execute("SET ROLE pmzilla_flow_ro")
        lignes = c.execute(f"SELECT team_id, team_name, tickets FROM {VUE} ORDER BY team_id").fetchall()
        c.execute("RESET ROLE")
        self.assertEqual(lignes, [(1, "Alpha", 2), (2, "Beta", 1)])     # PROJ-2 écarté, PROJ-3 sous les deux équipes, PROJ-4 nulle part, Gamma absente

    def test_le_role_en_lecture_seule_lit_la_vue_les_autres_roles_sont_refuses(self):
        c = self.conn()
        self.jeu(c)
        self.assertTrue(self.essaie(c, "pmzilla_flow_ro", f"SELECT * FROM {VUE}"))
        for role in ("pmzilla_flow_views", "pmzilla_quality_views", "pmzilla_flow", "pmzilla_cases", "pmzilla_knowledge_ro"):
            self.assertFalse(self.essaie(c, role, f"SELECT * FROM {VUE}"), role)

    def test_aucun_role_n_ecrit_la_vue(self):
        c = self.conn()
        self.jeu(c)
        # La vue (GROUP BY) n'est pas modifiable : PostgreSQL refuse l'écriture (ObjectNotInPrerequisiteState) avant tout contrôle de
        # droits, ce que essaie() ne compte pas comme un refus. La preuve de l'absence de droit est donc has_table_privilege ; l'essai
        # d'écriture reste, et toute erreur y vaut refus (une écriture qui réussit fait toujours échouer le test).
        for role in ("pmzilla_flow_ro", "pmzilla_flow", "pmzilla_flow_views"):
            for droit in ("INSERT", "UPDATE", "DELETE"):
                self.assertFalse(c.execute("SELECT has_table_privilege(%s, %s, %s)", (role, VUE, droit)).fetchone()[0], (role, droit))
            self.assertFalse(self.ecrit(c, role, f"INSERT INTO {VUE} (team_id, team_name, tickets) VALUES (9, 'X', 1)"), role)
            self.assertFalse(self.ecrit(c, role, f"DELETE FROM {VUE}"), role)

    def test_aucune_colonne_ne_porte_cle_ni_etiquette(self):
        c = self.conn()
        colonnes = [r[0] for r in c.execute("SELECT column_name FROM information_schema.columns "
                                            "WHERE table_schema = 'flow' AND table_name = 'v_team_tickets_seen' ORDER BY ordinal_position")]
        self.assertEqual(colonnes, ["team_id", "team_name", "tickets"])


if __name__ == "__main__":
    unittest.main()
