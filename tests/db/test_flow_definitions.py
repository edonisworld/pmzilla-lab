"""Définitions de flux du référentiel (change flow-definitions-referential, tâche 2.2, conception D2, D5 et D6 ; spec database-roles-views,
trois exigences ajoutées ; spec flow-cycle-referential, exigence « A referential load replaces the whole referential in one transaction »).

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

La classe SansBase tourne toujours : lecture statique du fichier de migration. L'autre utilise la base jetable de test_flow_schema.py (même
fixture) et est sautée sans elle (bash tools/dbtest.sh db) : écrite sans être lancée par un agent, passe de l'auteur (tâche 9.1). La migration
est retrouvée par sa description (flow_definitions), pas par son numéro. Données inventées.
"""
import re
import sys
import unittest
from datetime import date
from pathlib import Path

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402
import test_flow_referential as tfr   # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import flow_referential as fr   # noqa: E402

TABLES = ("ref_flow_statuses", "ref_unplanned_types", "ref_blocking_link_types")
ROLE_IMPORT = "pmzilla_flow"
ROLE_LECTURE = "pmzilla_flow_ro"
SANS_DROIT = ("pmzilla_flow_views", "pmzilla_quality_views", "pmzilla_cases", "pmzilla_cases_ro", "pmzilla_knowledge", "pmzilla_knowledge_ro")
SEGMENTS = ("definition", "ready", "implementation", "review_verification", "acceptance", "todo", "done")
INSERT_STATUT = "INSERT INTO flow.ref_flow_statuses (status, segment, is_committed, is_ready_queue) VALUES (%s, %s, %s, %s)"


def fichier_migration():
    candidats = [m for m in db.lister_migrations() if m.nom.endswith("_flow_definitions.sql")]
    return candidats[0] if len(candidats) == 1 else None


class SansBase(unittest.TestCase):
    def setUp(self):
        migration = fichier_migration()
        self.assertIsNotNone(migration, "une migration *_flow_definitions.sql est attendue")
        self.texte = migration.chemin.read_text(encoding="utf-8")
        self.code = re.sub(r"--[^\n]*", "", self.texte)

    def test_premiere_ligne_nomme_le_schema_flow(self):
        self.assertRegex(self.texte.splitlines()[0], r"^-- Schéma touché : flow")

    def test_le_role_proprietaire_est_pris_avant_la_premiere_instruction(self):
        premiere = [l.strip() for l in self.code.splitlines() if l.strip()][0]
        self.assertEqual(premiere, "SET LOCAL ROLE pmzilla_owner;")

    def test_aucune_donnee_ni_mot_de_passe_ni_role(self):
        self.assertNotRegex(self.code, r"(?im)^\s*(INSERT|UPDATE|DELETE|COPY)\b")
        self.assertNotRegex(self.code, r"(?i)\bPASSWORD\b")
        self.assertNotRegex(self.code, r"(?i)\b(CREATE|ALTER|DROP)\s+ROLE\b")
        self.assertNotRegex(self.code, r"(?i)\bLOGIN\b")

    def test_les_trois_tables_sont_creees_et_rien_d_autre(self):
        for table in TABLES:
            self.assertRegex(self.code, rf"(?i)CREATE\s+TABLE\s+flow\.{table}\b")
        self.assertEqual(len(re.findall(r"(?i)\bCREATE\s+TABLE\b", self.code)), 3)

    def test_droits_de_la_conception_d6(self):
        ecriture = re.search(r"(?is)GRANT\s+SELECT,\s*INSERT,\s*DELETE\s+ON\s+([^;]*?)\s+TO\s+pmzilla_flow\s*;", self.code)
        lecture = re.search(r"(?is)GRANT\s+SELECT\s+ON\s+([^;]*?)\s+TO\s+pmzilla_flow_ro\s*;", self.code)
        self.assertIsNotNone(ecriture)
        self.assertIsNotNone(lecture)
        for table in TABLES:
            self.assertIn(f"flow.{table}", ecriture.group(1), table)
            self.assertIn(f"flow.{table}", lecture.group(1), table)
        self.assertRegex(self.code, r"(?is)REVOKE\s+ALL\s+ON\s+[^;]*FROM\s+[^;]*PUBLIC")

    def test_aucun_droit_d_ecriture_autre_que_l_import_et_aucun_update(self):
        for accord in re.findall(r"(?is)\bGRANT\b[^;]*;", self.code):
            self.assertNotRegex(accord, r"(?i)\bUPDATE\b", accord)
            self.assertNotRegex(accord, r"(?i)\bALL\b", accord)

    def test_aucun_droit_au_role_des_vues(self):
        for accord in re.findall(r"(?is)\bGRANT\b[^;]*;", self.code):
            self.assertNotIn("pmzilla_flow_views", accord)
            self.assertNotIn("pmzilla_quality_views", accord)
        self.assertRegex(self.code, r"(?is)REVOKE\s+ALL\s+ON\s+[^;]*FROM\s+[^;]*pmzilla_flow_views")

    def test_aucune_cle_etrangere_vers_les_tickets(self):
        self.assertNotRegex(self.code, r"(?i)REFERENCES\s+flow\.")


class DefinitionsAvecBase(unittest.TestCase):
    """Même base jetable que SchemaFlow (migrations appliquées, base supprimée à la fin)."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie
    viole = tfr.ReferentielAvecBase.viole
    inserer = tfr.ReferentielAvecBase.inserer
    referentiel = tfr.ReferentielAvecBase.referentiel
    charger = tfr.ReferentielAvecBase.charger

    def test_trois_tables_du_proprietaire_et_vides_apres_la_migration(self):
        c = self.conn()
        proprietaires = dict(c.execute("SELECT tablename, tableowner FROM pg_tables WHERE schemaname = 'flow' AND tablename = ANY(%s)",
                                       (list(TABLES),)).fetchall())
        self.assertEqual(set(proprietaires), set(TABLES))
        self.assertEqual(set(proprietaires.values()), {"pmzilla_owner"})
        for table in TABLES:
            self.assertEqual(c.execute(f"SELECT count(*) FROM flow.{table}").fetchone()[0], 0, table)

    def test_aucune_cle_etrangere_vers_les_tickets_ni_ailleurs(self):
        c = self.conn()
        cles = c.execute("SELECT count(*) FROM information_schema.table_constraints WHERE table_schema = 'flow' "
                         "AND table_name = ANY(%s) AND constraint_type = 'FOREIGN KEY'", (list(TABLES),)).fetchone()[0]
        self.assertEqual(cles, 0)

    # --- contraintes (conception D2) ---------------------------------------------------------------------------------------------------

    def test_statut_non_vide_et_unique_sans_casse_ni_espaces(self):
        c = self.conn()
        self.viole(c, db.psycopg.errors.CheckViolation, INSERT_STATUT, ("   ", "ready", False, False))
        self.inserer(c, INSERT_STATUT, ("t-statut", "ready", True, True))
        self.viole(c, db.psycopg.errors.UniqueViolation, INSERT_STATUT, ("t-statut", "ready", True, True))
        self.viole(c, db.psycopg.errors.UniqueViolation, INSERT_STATUT, ("  T-STATUT ", "definition", False, False))

    def test_segment_dans_la_liste_fermee(self):
        c = self.conn()
        self.viole(c, db.psycopg.errors.CheckViolation, INSERT_STATUT, ("t-x", "inconnu", False, False))
        for i, segment in enumerate(SEGMENTS):
            self.inserer(c, INSERT_STATUT, (f"t-{i}", segment, False, False))

    def test_todo_et_done_sans_aucun_drapeau(self):
        c = self.conn()
        for segment in ("todo", "done"):
            self.viole(c, db.psycopg.errors.CheckViolation, INSERT_STATUT, ("t-a", segment, True, False))
            self.viole(c, db.psycopg.errors.CheckViolation, INSERT_STATUT, ("t-b", segment, False, True))

    def test_type_non_planifie(self):
        c = self.conn()
        sql = "INSERT INTO flow.ref_unplanned_types (type, kind) VALUES (%s, %s)"
        self.viole(c, db.psycopg.errors.CheckViolation, sql, ("  ", "defect"))
        self.viole(c, db.psycopg.errors.CheckViolation, sql, ("t-type", "support"))
        self.inserer(c, sql, ("t-type", "defect"))
        self.viole(c, db.psycopg.errors.UniqueViolation, sql, (" T-TYPE", "defect"))

    def test_type_de_lien_bloquant(self):
        c = self.conn()
        sql = "INSERT INTO flow.ref_blocking_link_types (type, direction) VALUES (%s, %s)"
        self.viole(c, db.psycopg.errors.CheckViolation, sql, ("", "blocks"))
        self.viole(c, db.psycopg.errors.CheckViolation, sql, ("t-lien", "autre"))
        self.inserer(c, sql, ("t-lien", "blocks"))
        self.inserer(c, sql, ("t-lien-2", "waits_for"))
        self.viole(c, db.psycopg.errors.UniqueViolation, sql, ("T-LIEN ", "waits_for"))

    # --- droits (conception D6) ----------------------------------------------------------------------------------------------------------

    def test_role_d_import_insere_lit_supprime_et_ne_met_pas_a_jour(self):
        c = self.conn()
        self.assertTrue(self.essaie(c, ROLE_IMPORT, "INSERT INTO flow.ref_unplanned_types (type, kind) VALUES ('t', 'defect')"))
        self.assertFalse(self.essaie(c, ROLE_IMPORT, "UPDATE flow.ref_unplanned_types SET kind = 'defect'"))
        for table in TABLES:
            self.assertTrue(self.essaie(c, ROLE_IMPORT, f"SELECT * FROM flow.{table}"), table)
            self.assertTrue(self.essaie(c, ROLE_IMPORT, f"DELETE FROM flow.{table}"), table)

    def test_role_en_lecture_seule_lit_et_n_ecrit_pas(self):
        c = self.conn()
        for table in TABLES:
            self.assertTrue(self.essaie(c, ROLE_LECTURE, f"SELECT * FROM flow.{table}"), table)
            self.assertFalse(self.essaie(c, ROLE_LECTURE, f"DELETE FROM flow.{table}"), table)
        self.assertFalse(self.essaie(c, ROLE_LECTURE, "INSERT INTO flow.ref_unplanned_types (type, kind) VALUES ('t', 'defect')"))

    def test_role_des_vues_de_flux_de_qualite_des_cas_et_de_la_connaissance_sans_aucun_droit(self):
        c = self.conn()
        for role in SANS_DROIT:
            for table in TABLES:
                self.assertFalse(self.essaie(c, role, f"SELECT * FROM flow.{table}"), (role, table))

    def test_aucun_role_d_application_ne_cree_ne_modifie_ni_ne_supprime_une_table(self):
        c = self.conn()
        for role in (ROLE_IMPORT, ROLE_LECTURE):
            for table in TABLES:
                self.assertFalse(self.essaie(c, role, f"ALTER TABLE flow.{table} ADD COLUMN extra integer"), (role, table))
                self.assertFalse(self.essaie(c, role, f"DROP TABLE flow.{table}"), (role, table))
            self.assertFalse(self.essaie(c, role, "CREATE TABLE flow.ref_interdite (id integer)"), role)

    # --- fonction d'écriture ---------------------------------------------------------------------------------------------------------------

    def avec_definitions(self, nombre_de_statuts: int) -> fr.Referentiel:
        statuts = tuple(fr.definir_statut(f"t-flux-{i}", SEGMENTS[i], "ready") for i in range(nombre_de_statuts))
        return fr.Referentiel(**{**self.referentiel(2).__dict__, "statuts_flux": statuts,
                                 "types_non_planifies": (fr.TypeNonPlanifie("t-defaut", "defect"),),
                                 "types_liens_bloquants": (fr.TypeLienBloquant("t-bloque", "blocks"),)})

    def test_ecrire_remplace_les_definitions(self):
        c = self.conn()
        self.charger(c, self.avec_definitions(3))
        self.assertEqual(c.execute("SELECT count(*) FROM flow.ref_flow_statuses").fetchone()[0], 3)
        self.charger(c, self.avec_definitions(1))
        self.assertEqual(c.execute("SELECT count(*) FROM flow.ref_flow_statuses").fetchone()[0], 1)
        self.charger(c, self.referentiel(2))                      # sans définition : les trois tables sont vidées
        for table in TABLES:
            self.assertEqual(c.execute(f"SELECT count(*) FROM flow.{table}").fetchone()[0], 0, table)

    def test_insert_de_definition_qui_echoue_laisse_les_definitions_precedentes(self):
        c = self.conn()
        self.charger(c, self.avec_definitions(3))

        class Sabotage:
            def __init__(self, reelle):
                self.reelle = reelle

            def execute(self, sql, params=None):
                if " ".join(sql.split()).startswith("INSERT INTO flow.ref_blocking_link_types"):
                    return self.reelle.execute("SELECT 1/0")
                return self.reelle.execute(sql, params)

            def transaction(self):
                return self.reelle.transaction()

        c.execute("SET ROLE pmzilla_flow")
        ref = self.avec_definitions(1)
        with self.assertRaises(db.psycopg.errors.DivisionByZero):
            fr.ecrire(Sabotage(c), ref, {e.etiquette for e in ref.etiquettes})
        c.rollback()
        c.execute("RESET ROLE")
        c.commit()
        self.assertEqual(c.execute("SELECT count(*) FROM flow.ref_flow_statuses").fetchone()[0], 3)


if __name__ == "__main__":
    unittest.main()
