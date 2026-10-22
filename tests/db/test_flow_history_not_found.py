"""Colonnes du suivi des 404 de la collecte de l'historique (change database-only, D5 ; migration du bug du 404 permanent).

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Les tests sans base (SansBase) tournent toujours : lecture du fichier de migration. Les autres utilisent la base jetable de
test_flow_schema.py et sont sautés sans elle (bash tools/dbtest.sh db). La migration est retrouvée par sa description
(flow_history_not_found), pas par son numéro. Données inventées.
"""
import re
import unittest

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402

ROLE_IMPORT = "pmzilla_flow"


def fichier_migration():
    candidats = [m for m in db.lister_migrations() if m.nom.endswith("_flow_history_not_found.sql")]
    return candidats[0] if len(candidats) == 1 else None


class SansBase(unittest.TestCase):
    def test_migration_presente_sans_donnee_ni_mot_de_passe_ni_role_ni_droit(self):
        migration = fichier_migration()
        self.assertIsNotNone(migration, "une migration *_flow_history_not_found.sql est attendue")
        texte = migration.chemin.read_text(encoding="utf-8")
        self.assertRegex(texte.splitlines()[0], r"^-- Schéma touché : flow")
        sans_commentaires = re.sub(r"--[^\n]*", "", texte)
        self.assertNotRegex(sans_commentaires, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s)")           # aucune donnée, aucune mise à jour
        self.assertNotRegex(sans_commentaires, r"(?i)\bPASSWORD\b")
        self.assertNotRegex(sans_commentaires, r"(?i)\b(CREATE|ALTER|DROP)\s+ROLE\b")
        self.assertNotRegex(sans_commentaires, r"(?i)\b(LOGIN|GRANT|REVOKE)\b")                         # aucun droit changé
        self.assertRegex(sans_commentaires, r"(?is)ALTER\s+TABLE\s+flow\.issues\s+ADD\s+COLUMN\s+history_not_found\s+integer\s+NOT\s+NULL\s+DEFAULT\s+0")
        self.assertRegex(sans_commentaires, r"(?is)ADD\s+COLUMN\s+history_gone_at\s+timestamptz\s*;")
        self.assertRegex(sans_commentaires, r"(?is)ALTER\s+TABLE\s+flow\.raw_runs\s+ADD\s+COLUMN\s+errors\s+integer\s+CONSTRAINT")
        self.assertRegex(sans_commentaires, r"(?is)ADD\s+COLUMN\s+not_found\s+integer\s+CONSTRAINT")
        self.assertNotRegex(sans_commentaires, r"(?is)raw_runs.*NOT\s+NULL")                        # nuls pour les passages d'export et d'amorçage

    def test_la_migration_suit_celle_du_type_d_equipe(self):
        numeros = {m.nom.split("_", 1)[1]: m.numero for m in db.lister_migrations()}
        self.assertGreater(numeros["flow_history_not_found.sql"], numeros["flow_team_type.sql"])

    def test_le_nom_des_colonnes_ne_porte_ni_etiquette_ni_cle_ni_version(self):
        for colonne in ("history_not_found", "history_gone_at", "errors", "not_found"):
            for mot in ("label", "key", "version"):
                self.assertNotIn(mot, colonne)

    def test_numero_libre_suivant(self):
        numeros = sorted(m.numero for m in db.lister_migrations())
        self.assertEqual(numeros, list(range(1, len(numeros) + 1)))                                      # sans trou ni doublon


class ColonnesDuSuivi(unittest.TestCase):
    """Même base jetable que SchemaFlow (migrations appliquées, base supprimée à la fin)."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def inserer_ticket(self, c, cle="PROJ-1"):
        c.execute(f"SET ROLE {ROLE_IMPORT}")
        c.execute("INSERT INTO flow.teams (name) VALUES ('Alpha') ON CONFLICT DO NOTHING")
        c.execute("INSERT INTO flow.issues (key, project, type, status, created_at, updated_at, team_id) "
                  "SELECT %s, 'PROJ', 'Story', 'Open', now(), now(), id FROM flow.teams WHERE name = 'Alpha'", (cle,))

    def test_valeurs_par_defaut_d_un_ticket_et_d_un_passage(self):
        c = self.conn()
        self.inserer_ticket(c)
        self.assertEqual(c.execute("SELECT history_not_found, history_gone_at FROM flow.issues").fetchone(), (0, None))
        c.execute("INSERT INTO flow.raw_runs (kind, queries_searched, all_queries) VALUES ('history', 0, false)")
        self.assertEqual(c.execute("SELECT errors, not_found FROM flow.raw_runs").fetchone(), (None, None))     # nuls sans collecte
        c.execute("RESET ROLE")

    def test_le_role_d_import_met_a_jour_le_suivi_d_un_ticket_et_enregistre_les_erreurs_d_un_passage(self):
        c = self.conn()
        self.inserer_ticket(c)
        c.execute("UPDATE flow.issues SET history_not_found = 2 WHERE key = 'PROJ-1'")
        c.execute("UPDATE flow.issues SET history_not_found = 3, history_gone_at = now() WHERE key = 'PROJ-1'")
        self.assertEqual(c.execute("SELECT history_not_found, history_gone_at IS NOT NULL FROM flow.issues").fetchone(), (3, True))
        c.execute("INSERT INTO flow.raw_runs (kind, queries_searched, all_queries, errors, not_found) VALUES ('history', 0, false, 4, 2)")
        self.assertEqual(c.execute("SELECT errors, not_found FROM flow.raw_runs").fetchone(), (4, 2))
        c.execute("RESET ROLE")

    def test_valeurs_negatives_refusees(self):
        c = self.conn()
        self.inserer_ticket(c)
        with self.assertRaises(db.psycopg.errors.CheckViolation):
            with c.transaction():
                c.execute("UPDATE flow.issues SET history_not_found = -1")
        with self.assertRaises(db.psycopg.errors.CheckViolation):
            with c.transaction():
                c.execute("INSERT INTO flow.raw_runs (kind, errors) VALUES ('history', -1)")
        with self.assertRaises(db.psycopg.errors.CheckViolation):
            with c.transaction():
                c.execute("INSERT INTO flow.raw_runs (kind, not_found) VALUES ('history', -1)")
        c.execute("RESET ROLE")

    def test_la_couche_brute_reste_en_ajout_seulement(self):
        c = self.conn()
        self.inserer_ticket(c)
        c.execute("INSERT INTO flow.raw_runs (kind, errors) VALUES ('history', 1)")
        with self.assertRaises(db.psycopg.errors.InsufficientPrivilege):
            with c.transaction():
                c.execute("UPDATE flow.raw_runs SET errors = 0")
        c.execute("RESET ROLE")

    def test_le_role_en_lecture_seule_lit_le_suivi_et_ne_l_ecrit_pas(self):
        c = self.conn()
        self.inserer_ticket(c)
        c.execute("RESET ROLE")
        c.commit()
        self.assertTrue(self.essaie(c, "pmzilla_flow_ro", "SELECT history_not_found, history_gone_at FROM flow.issues"))
        self.assertFalse(self.essaie(c, "pmzilla_flow_ro", "UPDATE flow.issues SET history_not_found = 1"))

    def test_le_role_des_vues_n_a_aucun_acces_et_aucune_vue_ne_lit_ces_colonnes(self):
        c = self.conn()
        self.assertFalse(self.essaie(c, "pmzilla_flow_views", "SELECT history_not_found FROM flow.issues"))
        self.assertFalse(self.essaie(c, "pmzilla_flow_views", "SELECT errors FROM flow.raw_runs"))
        for vue in fs.VUES:
            definition = c.execute("SELECT pg_get_viewdef(%s::regclass)", (f"flow.{vue}",)).fetchone()[0]
            self.assertNotIn("history_not_found", definition, vue)
            self.assertNotIn("history_gone_at", definition, vue)


if __name__ == "__main__":
    unittest.main()
