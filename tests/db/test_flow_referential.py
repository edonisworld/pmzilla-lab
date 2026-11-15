"""Référentiel des cycles du schéma flow (change cycle-referential-schema, tâche 2.2, conception D2 à D5 ; spec database-roles-views,
exigences « Cycle referential tables in the flow schema », « Cycle referential rights » et « Cycle referential constraints » ;
spec flow-cycle-referential, exigence « A referential load replaces the whole referential in one transaction »).

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

La classe SansBase tourne toujours : lecture statique du fichier de migration. Les autres utilisent la base jetable de
test_flow_schema.py (même fixture) et sont sautées sans elle (bash tools/dbtest.sh db). La migration est retrouvée par sa
description (cycle_referential), pas par son numéro : celui-ci change quand une autre migration fusionne avant elle. Données inventées.
"""
import re
import sys
import unittest
from datetime import date
from pathlib import Path

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import flow_referential as fr   # noqa: E402

TABLES = ("ref_cycles", "ref_labels", "ref_dw_columns", "ref_dw_statuses", "ref_state")
ROLE_IMPORT = "pmzilla_flow"
ROLE_LECTURE = "pmzilla_flow_ro"
ROLE_VUES = "pmzilla_flow_views"
AUTRES_ROLES = ("pmzilla_flow_views", "pmzilla_quality_views", "pmzilla_cases", "pmzilla_cases_ro", "pmzilla_knowledge",
                "pmzilla_knowledge_ro")
NOMS_INTERDITS = {"issue_key", "key", "summary", "title", "description", "assignee", "reporter", "creator", "author", "comment",
                  "po", "product_owner", "person", "person_name", "version", "fix_version", "count", "total"}


def fichier_migration():
    candidats = [m for m in db.lister_migrations() if m.nom.endswith("_cycle_referential.sql")]
    return candidats[0] if len(candidats) == 1 else None


class SansBase(unittest.TestCase):
    def setUp(self):
        migration = fichier_migration()
        self.assertIsNotNone(migration, "une migration *_cycle_referential.sql est attendue")
        self.texte = migration.chemin.read_text(encoding="utf-8")
        self.code = re.sub(r"--[^\n]*", "", self.texte)           # sans les commentaires

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

    def test_les_cinq_tables_sont_creees(self):
        for table in TABLES:
            self.assertRegex(self.code, rf"(?i)CREATE\s+TABLE\s+flow\.{table}\b")
        self.assertEqual(len(re.findall(r"(?i)\bCREATE\s+TABLE\b", self.code)), 5)

    def test_droits_de_la_conception_d4(self):
        self.assertRegex(self.code, r"(?is)GRANT\s+SELECT,\s*INSERT,\s*DELETE\s+ON\s+[^;]*TO\s+pmzilla_flow\s*;")
        self.assertRegex(self.code, r"(?is)GRANT\s+SELECT\s+ON\s+[^;]*TO\s+pmzilla_flow_ro\s*;")
        self.assertRegex(self.code, r"(?is)REVOKE\s+ALL\s+ON\s+[^;]*FROM\s+[^;]*PUBLIC")
        for table in TABLES:
            self.assertIn(f"flow.{table}", re.search(r"(?is)GRANT\s+SELECT,\s*INSERT,\s*DELETE\s+ON\s+([^;]*?)\s+TO\s+pmzilla_flow\s*;",
                                                     self.code).group(1), table)
            self.assertIn(f"flow.{table}", re.search(r"(?is)GRANT\s+SELECT\s+ON\s+([^;]*?)\s+TO\s+pmzilla_flow_ro\s*;", self.code).group(1), table)

    def test_aucun_droit_d_ecriture_autre_que_l_import_et_aucun_update(self):
        for accord in re.findall(r"(?is)\bGRANT\b[^;]*;", self.code):
            self.assertNotRegex(accord, r"(?i)\bUPDATE\b", accord)
            self.assertNotRegex(accord, r"(?i)\bALL\b", accord)

    def test_aucun_droit_au_role_des_vues(self):
        for accord in re.findall(r"(?is)\bGRANT\b[^;]*;", self.code):
            self.assertNotIn(ROLE_VUES, accord)
            self.assertNotIn("pmzilla_quality_views", accord)
        self.assertRegex(self.code, r"(?is)REVOKE\s+ALL\s+ON\s+[^;]*FROM\s+[^;]*pmzilla_flow_views")

    def test_aucune_cle_etrangere_vers_les_tickets(self):
        self.assertNotRegex(self.code, r"(?i)REFERENCES\s+flow\.(issues|issue_teams|transitions|links|teams)\b")


class ReferentielAvecBase(unittest.TestCase):
    """Même base jetable que SchemaFlow (migrations appliquées, base supprimée à la fin)."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def viole(self, c, erreur, sql, params=None):
        with self.assertRaises(erreur):
            with c.transaction():
                c.execute("SET LOCAL ROLE pmzilla_flow")
                c.execute(sql, params)

    def inserer(self, c, sql, params=None):
        with c.transaction():
            c.execute("SET LOCAL ROLE pmzilla_flow")
            c.execute(sql, params)

    def cycle(self, c, cle="2099-C1"):
        self.inserer(c, "INSERT INTO flow.ref_cycles (cycle_key, start_date, end_date) VALUES (%s, '2099-01-05', '2099-02-27')", (cle,))

    def colonne(self, c, nom, position, depart=False, revue=False, pret=False, active=False):
        self.inserer(c, "INSERT INTO flow.ref_dw_columns (name, position, is_start, is_review_passed, is_ready, is_active) "
                        "VALUES (%s, %s, %s, %s, %s, %s)", (nom, position, depart, revue, pret, active))

    # --- structure -----------------------------------------------------------------------------------------------------------------

    def test_cinq_tables_du_proprietaire_et_vides_apres_la_migration(self):
        c = self.conn()
        proprietaires = dict(c.execute("SELECT tablename, tableowner FROM pg_tables WHERE schemaname = 'flow' AND tablename = ANY(%s)",
                                       (list(TABLES),)).fetchall())
        self.assertEqual(set(proprietaires), set(TABLES))
        self.assertEqual(set(proprietaires.values()), {"pmzilla_owner"})
        for table in TABLES:
            self.assertEqual(c.execute(f"SELECT count(*) FROM flow.{table}").fetchone()[0], 0, table)

    def test_aucune_colonne_de_ticket_ni_cle_etrangere_vers_les_tickets(self):
        c = self.conn()
        colonnes = c.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'flow' "
                             "AND table_name = ANY(%s)", (list(TABLES),)).fetchall()
        self.assertTrue(colonnes)
        for table, colonne in colonnes:
            nom = colonne.lower()
            self.assertNotIn(nom, NOMS_INTERDITS, (table, colonne))
            for mot in ("version", "count", "person", "issue", "ticket", "assignee", "summary", "title"):
                self.assertNotIn(mot, nom, (table, colonne))
        cles = c.execute("SELECT tc.table_name, ccu.table_name FROM information_schema.table_constraints tc "
                         "JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name "
                         "AND ccu.constraint_schema = tc.constraint_schema "
                         "WHERE tc.table_schema = 'flow' AND tc.table_name = ANY(%s) AND tc.constraint_type = 'FOREIGN KEY'",
                         (list(TABLES),)).fetchall()
        for _, cible in cles:
            self.assertIn(cible, TABLES)

    def test_seules_colonnes_d_etiquette_du_referentiel(self):
        c = self.conn()
        lignes = c.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'flow' "
                           "AND table_name = ANY(%s) AND column_name ILIKE '%%label%%'", (list(TABLES),)).fetchall()
        self.assertEqual({t for t, _ in lignes}, {fs.TABLE_ETIQUETTES_REFERENTIEL})

    # --- contraintes (conception D2) -------------------------------------------------------------------------------------------------

    def test_forme_de_la_cle_de_cycle(self):
        c = self.conn()
        for cle in ("12.3", "v1.2", "2099-C7", "2099-C0", "99-C1", "2099-eoy"):
            self.viole(c, db.psycopg.errors.CheckViolation,
                       "INSERT INTO flow.ref_cycles (cycle_key, start_date, end_date) VALUES (%s, '2099-01-05', '2099-02-27')", (cle,))
        for cle in ("2099-C1", "2099-C6", "2099-EOY"):
            self.cycle(c, cle)

    def test_fin_de_cycle_pas_avant_le_debut(self):
        c = self.conn()
        self.viole(c, db.psycopg.errors.CheckViolation,
                   "INSERT INTO flow.ref_cycles (cycle_key, start_date, end_date) VALUES ('2099-C1', '2099-02-27', '2099-01-05')")

    def test_cle_de_cycle_unique(self):
        c = self.conn()
        self.cycle(c)
        self.viole(c, db.psycopg.errors.UniqueViolation,
                   "INSERT INTO flow.ref_cycles (cycle_key, start_date, end_date) VALUES ('2099-C1', '2099-03-02', '2099-04-24')")

    def test_cle_de_cycle_sur_une_etiquette_d_un_autre_role_et_cycle_inconnu(self):
        c = self.conn()
        self.cycle(c)
        self.viole(c, db.psycopg.errors.CheckViolation,
                   "INSERT INTO flow.ref_labels (label, role, cycle_key) VALUES ('t-revue', 'epic_review', '2099-C1')")
        self.viole(c, db.psycopg.errors.ForeignKeyViolation,
                   "INSERT INTO flow.ref_labels (label, role, cycle_key) VALUES ('t-cycle', 'cycle', '2099-C5')")
        self.inserer(c, "INSERT INTO flow.ref_labels (label, role, cycle_key) VALUES ('t-cycle', 'cycle', '2099-C1')")

    def test_role_d_etiquette_dans_la_liste_fermee(self):
        c = self.conn()
        self.viole(c, db.psycopg.errors.CheckViolation, "INSERT INTO flow.ref_labels (label, role) VALUES ('t-x', 'inconnu')")
        for i, role in enumerate(("up_merge", "epic_review", "pilot_domain", "ready")):
            self.inserer(c, "INSERT INTO flow.ref_labels (label, role) VALUES (%s, %s)", (f"t-{i}", role))

    def test_etiquette_unique(self):
        c = self.conn()
        self.inserer(c, "INSERT INTO flow.ref_labels (label, role) VALUES ('t-up', 'up_merge')")
        self.viole(c, db.psycopg.errors.UniqueViolation, "INSERT INTO flow.ref_labels (label, role) VALUES ('t-up', 'up_merge')")

    def test_sens_de_confirmation(self):
        c = self.conn()
        self.viole(c, db.psycopg.errors.CheckViolation, "INSERT INTO flow.ref_labels (label, role) VALUES ('t-conf', 'confirmation')")
        self.viole(c, db.psycopg.errors.CheckViolation,
                   "INSERT INTO flow.ref_labels (label, role, meaning) VALUES ('t-conf', 'confirmation', 'autre')")
        self.viole(c, db.psycopg.errors.CheckViolation,
                   "INSERT INTO flow.ref_labels (label, role, meaning) VALUES ('t-pret', 'ready', 'taken_in')")
        self.inserer(c, "INSERT INTO flow.ref_labels (label, role, meaning) VALUES ('t-conf-1', 'confirmation', 'taken_in')")
        self.inserer(c, "INSERT INTO flow.ref_labels (label, role, meaning) VALUES ('t-conf-2', 'confirmation', 'not_taken_in')")

    def test_une_seule_etiquette_de_domaine_et_une_seule_ready(self):
        c = self.conn()
        for role in ("pilot_domain", "ready"):
            self.inserer(c, "INSERT INTO flow.ref_labels (label, role) VALUES (%s, %s)", (f"t-{role}-1", role))
            self.viole(c, db.psycopg.errors.UniqueViolation,
                       "INSERT INTO flow.ref_labels (label, role) VALUES (%s, %s)", (f"t-{role}-2", role))
        for i in (1, 2):                                           # deux up_merge restent permis
            self.inserer(c, "INSERT INTO flow.ref_labels (label, role) VALUES (%s, 'up_merge')", (f"t-up-{i}",))

    def test_colonnes_depart_pret_actif_et_position(self):
        c = self.conn()
        self.colonne(c, "t-a", 1, depart=True, active=True)
        self.viole(c, db.psycopg.errors.UniqueViolation,
                   "INSERT INTO flow.ref_dw_columns (name, position, is_start, is_review_passed, is_ready, is_active) "
                   "VALUES ('t-b', 2, true, false, false, false)")                                   # deuxième colonne de départ
        self.viole(c, db.psycopg.errors.CheckViolation,
                   "INSERT INTO flow.ref_dw_columns (name, position, is_start, is_review_passed, is_ready, is_active) "
                   "VALUES ('t-b', 2, false, false, true, true)")                                    # Ready jamais active
        self.viole(c, db.psycopg.errors.CheckViolation,
                   "INSERT INTO flow.ref_dw_columns (name, position, is_start, is_review_passed, is_ready, is_active) "
                   "VALUES ('t-b', 0, false, false, false, false)")                                  # position positive
        self.viole(c, db.psycopg.errors.UniqueViolation,
                   "INSERT INTO flow.ref_dw_columns (name, position, is_start, is_review_passed, is_ready, is_active) "
                   "VALUES ('t-b', 1, false, false, false, false)")                                  # position unique
        self.viole(c, db.psycopg.errors.UniqueViolation,
                   "INSERT INTO flow.ref_dw_columns (name, position, is_start, is_review_passed, is_ready, is_active) "
                   "VALUES ('t-a', 2, false, false, false, false)")                                  # nom unique
        self.colonne(c, "t-c", 2, pret=True)
        self.viole(c, db.psycopg.errors.UniqueViolation,
                   "INSERT INTO flow.ref_dw_columns (name, position, is_start, is_review_passed, is_ready, is_active) "
                   "VALUES ('t-d', 3, false, false, true, false)")                                   # deuxième colonne Ready

    def test_statut_dans_une_seule_colonne_declaree(self):
        c = self.conn()
        self.colonne(c, "t-a", 1, depart=True, active=True)
        self.colonne(c, "t-b", 2)
        self.inserer(c, "INSERT INTO flow.ref_dw_statuses (status, column_name) VALUES ('t-st', 't-a')")
        self.viole(c, db.psycopg.errors.UniqueViolation, "INSERT INTO flow.ref_dw_statuses (status, column_name) VALUES ('t-st', 't-b')")
        self.viole(c, db.psycopg.errors.ForeignKeyViolation,
                   "INSERT INTO flow.ref_dw_statuses (status, column_name) VALUES ('t-autre', 't-z')")

    def test_une_seule_ligne_d_etat(self):
        c = self.conn()
        self.inserer(c, "INSERT INTO flow.ref_state (mapping_validated_on) VALUES (NULL)")
        self.viole(c, db.psycopg.errors.UniqueViolation, "INSERT INTO flow.ref_state (mapping_validated_on) VALUES ('2099-01-02')")

    # --- droits (conception D4) -------------------------------------------------------------------------------------------------------

    def test_role_d_import_insere_lit_supprime_et_ne_met_pas_a_jour(self):
        c = self.conn()
        insere = "INSERT INTO flow.ref_cycles (cycle_key, start_date, end_date) VALUES ('2099-C1', '2099-01-05', '2099-02-27')"
        self.assertTrue(self.essaie(c, ROLE_IMPORT, insere))
        self.assertTrue(self.essaie(c, ROLE_IMPORT, "SELECT * FROM flow.ref_cycles"))
        self.assertFalse(self.essaie(c, ROLE_IMPORT, "UPDATE flow.ref_cycles SET end_date = '2099-03-06' WHERE cycle_key = '2099-C1'"))
        self.assertTrue(self.essaie(c, ROLE_IMPORT, "DELETE FROM flow.ref_cycles"))
        for table in TABLES:
            self.assertTrue(self.essaie(c, ROLE_IMPORT, f"SELECT * FROM flow.{table}"), table)
            self.assertTrue(self.essaie(c, ROLE_IMPORT, f"DELETE FROM flow.{table}"), table)

    def test_role_en_lecture_seule_lit_et_n_ecrit_pas(self):
        c = self.conn()
        for table in TABLES:
            self.assertTrue(self.essaie(c, ROLE_LECTURE, f"SELECT * FROM flow.{table}"), table)
        insere = "INSERT INTO flow.ref_cycles (cycle_key, start_date, end_date) VALUES ('2099-C1', '2099-01-05', '2099-02-27')"
        self.assertFalse(self.essaie(c, ROLE_LECTURE, insere))
        self.assertFalse(self.essaie(c, ROLE_LECTURE, "DELETE FROM flow.ref_cycles"))
        self.assertFalse(self.essaie(c, ROLE_LECTURE, "UPDATE flow.ref_state SET mapping_validated_on = NULL"))

    def test_role_des_vues_et_roles_des_autres_schemas_sans_aucun_droit(self):
        c = self.conn()
        for role in AUTRES_ROLES:
            for table in TABLES:
                self.assertFalse(self.essaie(c, role, f"SELECT * FROM flow.{table}"), (role, table))

    def test_aucun_role_d_application_ne_cree_ne_modifie_ni_ne_supprime_une_table(self):
        c = self.conn()
        for role in (ROLE_IMPORT, ROLE_LECTURE):
            self.assertFalse(self.essaie(c, role, "ALTER TABLE flow.ref_cycles ADD COLUMN extra integer"), role)
            self.assertFalse(self.essaie(c, role, "DROP TABLE flow.ref_cycles"), role)
            self.assertFalse(self.essaie(c, role, "CREATE TABLE flow.ref_interdite (id integer)"), role)

    # --- fonction d'écriture (flow_referential.ecrire, D5) ---------------------------------------------------------------------------

    def referentiel(self, nombre_de_cycles: int) -> fr.Referentiel:
        cycles = tuple(fr.Cycle(f"2099-C{i}", date(2099, 1, 5), date(2099, 2, 27)) for i in range(1, nombre_de_cycles + 1))
        etiquettes = (fr.Etiquette("t-up-1", "up_merge", None, None), fr.Etiquette("t-up-2", "up_merge", None, None),
                      *(fr.Etiquette(f"t-cycle-{c.cle}", "cycle", c.cle, None) for c in cycles),
                      fr.Etiquette("t-revue", "epic_review", None, None), fr.Etiquette("t-domaine", "pilot_domain", None, None),
                      fr.Etiquette("t-pret", "ready", None, None),
                      fr.Etiquette("t-conf-1", "confirmation", None, "taken_in"),
                      fr.Etiquette("t-conf-2", "confirmation", None, "not_taken_in"))
        colonnes = (fr.Colonne("t-col-a", 1, True, False, False, True), fr.Colonne("t-col-b", 2, False, True, False, True),
                    fr.Colonne("t-col-c", 3, False, False, True, False))
        statuts = (fr.Statut("t-st-a", "t-col-a"), fr.Statut("t-st-b", "t-col-b"), fr.Statut("t-st-c", "t-col-c"))
        return fr.Referentiel(cycles=cycles, etiquettes=etiquettes, colonnes=colonnes, statuts=statuts, valide_le=None)

    def charger(self, c, ref):
        c.execute("SET ROLE pmzilla_flow")
        fr.ecrire(c, ref, {e.etiquette for e in ref.etiquettes})
        c.commit()
        c.execute("RESET ROLE")
        c.commit()

    def cles(self, c):
        return [r[0] for r in c.execute("SELECT cycle_key FROM flow.ref_cycles ORDER BY cycle_key").fetchall()]

    def test_ecrire_remplace_un_referentiel_de_quatre_cycles_par_un_de_deux(self):
        c = self.conn()
        self.charger(c, self.referentiel(4))
        self.assertEqual(self.cles(c), ["2099-C1", "2099-C2", "2099-C3", "2099-C4"])
        premier = c.execute("SELECT loaded_at FROM flow.ref_state").fetchone()[0]
        c.commit()
        self.charger(c, self.referentiel(2))
        self.assertEqual(self.cles(c), ["2099-C1", "2099-C2"])
        self.assertEqual(c.execute("SELECT count(*) FROM flow.ref_labels WHERE role = 'cycle'").fetchone()[0], 2)
        self.assertEqual(c.execute("SELECT count(*) FROM flow.ref_state").fetchone()[0], 1)
        self.assertGreater(c.execute("SELECT loaded_at FROM flow.ref_state").fetchone()[0], premier)

    def test_ecrire_sous_un_autre_role_refuse_sans_rien_ecrire(self):
        c = self.conn()
        with self.assertRaises(fr.ReferentielInvalide) as refus:
            fr.ecrire(c, self.referentiel(2), {e.etiquette for e in self.referentiel(2).etiquettes})
        self.assertEqual(str(refus.exception), "référentiel des cycles : rôle d'écriture inattendu")
        c.rollback()
        self.assertEqual(self.cles(c), [])

    def test_insert_qui_echoue_laisse_le_referentiel_precedent_intact(self):
        c = self.conn()
        self.charger(c, self.referentiel(4))

        class Sabotage:
            """Délègue à la vraie connexion, mais le premier insert d'un statut devient une division par zéro de la base."""

            def __init__(self, reelle):
                self.reelle = reelle

            def execute(self, sql, params=None):
                if " ".join(sql.split()).startswith("INSERT INTO flow.ref_dw_statuses"):
                    return self.reelle.execute("SELECT 1/0")
                return self.reelle.execute(sql, params)

            def transaction(self):
                return self.reelle.transaction()

        c.execute("SET ROLE pmzilla_flow")
        with self.assertRaises(db.psycopg.errors.DivisionByZero):
            fr.ecrire(Sabotage(c), self.referentiel(2), {e.etiquette for e in self.referentiel(2).etiquettes})
        c.rollback()
        c.execute("RESET ROLE")
        c.commit()
        self.assertEqual(self.cles(c), ["2099-C1", "2099-C2", "2099-C3", "2099-C4"])
        self.assertEqual(c.execute("SELECT count(*) FROM flow.ref_labels WHERE role = 'cycle'").fetchone()[0], 4)
        self.assertEqual(c.execute("SELECT count(*) FROM flow.ref_dw_statuses").fetchone()[0], 3)


if __name__ == "__main__":
    unittest.main()
