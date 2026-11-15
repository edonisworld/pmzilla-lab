"""Magasin des photos de qualité par version (change version-quality-photo, tâche 1.1 ; spec jira-flow-version-photo, database-roles-views).

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Les tests sans base (SansBase) tournent toujours : lecture du fichier de migration, retrouvé par sa description et non par son numéro.
Les autres utilisent la base jetable de test_flow_schema.py et sont sautés sans elle (bash tools/dbtest.sh db). Données inventées.
"""
import datetime as dt
import re
import unittest

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402

TABLES_PHOTO = ("version_photo_versions", "version_photo_runs", "version_photo_weeks", "version_photo_rows", "version_photo_n")
LUNDI = dt.date(2026, 3, 2)          # un lundi


def migration(suffixe):
    candidats = [m for m in db.lister_migrations() if m.nom.endswith(suffixe)]
    return candidats[0] if len(candidats) == 1 else None


def code_de(suffixe):
    m = migration(suffixe)
    assert m is not None, f"une migration *{suffixe} est attendue"
    return m.chemin.read_text(encoding="utf-8")


def sans_commentaires(texte):
    return re.sub(r"--[^\n]*", "", texte)


class SansBase(unittest.TestCase):
    def test_entete_et_proprietaire(self):
        texte = code_de("_flow_version_photo.sql")
        code = sans_commentaires(texte)
        self.assertRegex(texte.splitlines()[0], r"^-- Schéma touché : flow")
        self.assertRegex(code, r"(?is)SET\s+LOCAL\s+ROLE\s+pmzilla_owner\s*;")
        self.assertNotRegex(code, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(code, r"(?i)\bPASSWORD\b|\b(CREATE|ALTER|DROP)\s+ROLE\b|\bLOGIN\b")

    def test_cinq_tables_sans_cle_etrangere_vers_les_tickets(self):
        code = sans_commentaires(code_de("_flow_version_photo.sql"))
        tables = re.findall(r"(?i)CREATE\s+TABLE\s+flow\.(\w+)", code)
        self.assertEqual(tuple(tables), TABLES_PHOTO)
        for cible in re.findall(r"(?is)REFERENCES\s+flow\.(\w+)", code):
            self.assertIn(cible, TABLES_PHOTO, f"clé étrangère vers {cible}")
        self.assertNotRegex(code, r"(?i)issue_key|\bflow\.issues\b|\bflow\.teams\b")

    def test_aucune_colonne_de_cle_ni_de_personne(self):
        code = sans_commentaires(code_de("_flow_version_photo.sql"))
        self.assertNotRegex(code, r"(?i)\b\w*key\w*\b\s+(text|integer|bigint)")
        self.assertNotRegex(code, r"(?i)\b(title|description|assignee|reporter|author|person|label)\b")

    def test_registre_de_n_en_ajout_seulement_et_revoque_aux_autres(self):
        code = sans_commentaires(code_de("_flow_version_photo.sql"))
        revoke = re.search(r"(?is)\bREVOKE\b.*?;", code)
        self.assertIsNotNone(revoke)
        for role in ("PUBLIC", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_flow_views", "pmzilla_quality_views"):
            self.assertRegex(revoke.group(0), rf"\b{role}\b")
        for table in TABLES_PHOTO:
            self.assertIn(f"flow.{table}", revoke.group(0))
        grants = re.findall(r"(?is)\bGRANT\b.*?;", code)
        self.assertEqual(len(grants), 3, grants)
        # le troisième : la lecture des noms de migrations appliquées, pour la garde d'adopt-n (décision du 2026-10-23)
        self.assertRegex(grants[2], r"(?is)GRANT\s+SELECT\s+ON\s+public\.schema_migrations\s+TO\s+pmzilla_flow\s*;")
        self.assertRegex(grants[1], r"(?is)GRANT\s+SELECT,\s*INSERT\s+ON\s+flow\.version_photo_n\s+TO\s+pmzilla_flow\s*;")
        self.assertNotRegex(grants[1], r"(?i)UPDATE|DELETE")
        self.assertNotIn("version_photo_n", grants[0])
        self.assertLess(code.index("REVOKE"), code.index("GRANT"))
        for grant in grants:                                       # jamais à PUBLIC ni aux rôles de lecture (« public.schema_migrations » est un nom de table)
            self.assertNotRegex(grant, r"(?i)\bTO\s+[^;]*(pmzilla_flow_views|pmzilla_flow_ro|\bPUBLIC\b)")

    def test_une_semaine_une_seule_photo(self):
        code = sans_commentaires(code_de("_flow_version_photo.sql"))
        semaines = re.search(r"(?is)CREATE\s+TABLE\s+flow\.version_photo_weeks\s*\((.*?)\)\s*;", code).group(1)
        self.assertRegex(semaines, r"(?is)week_start\s+date\s+PRIMARY\s+KEY")
        self.assertRegex(semaines, r"(?is)isodow")                              # toujours un lundi

    def test_aucun_index_d_unicite_sur_les_passages(self):
        """Décision du 2026-10-23 : chaque relance de --replace écrit un nouveau passage reconstruit ; l'unicité est celle de la semaine."""
        code = sans_commentaires(code_de("_flow_version_photo.sql"))
        self.assertNotRegex(code, r"(?is)CREATE\s+UNIQUE\s+INDEX\s+\w+\s+ON\s+flow\.version_photo_runs\b")
        self.assertNotIn("une_reconstruction", code)

    def test_sequences_d_identite_revoquees_aux_roles_de_lecture(self):
        code = sans_commentaires(code_de("_flow_version_photo.sql"))
        revoke = re.search(r"(?is)\bREVOKE\s+ALL\s+ON\s+SEQUENCE\b(.*?);", code)
        self.assertIsNotNone(revoke)
        for sequence in ("version_photo_versions_version_no_seq", "version_photo_runs_id_seq", "version_photo_n_id_seq"):
            self.assertIn(f"flow.{sequence}", revoke.group(1))
        self.assertRegex(revoke.group(1), r"(?is)FROM\s+pmzilla_flow_ro\s*,\s*pmzilla_flow_views\b")
        self.assertNotRegex(revoke.group(1), r"pmzilla_flow\s*[,;]|PUBLIC")                 # le rôle d'import garde ses séquences

    def test_la_date_de_sortie_et_le_drapeau_sont_nuls(self):
        code = sans_commentaires(code_de("_flow_version_photo.sql"))
        versions = re.search(r"(?is)CREATE\s+TABLE\s+flow\.version_photo_versions\s*\((.*?)\)\s*;", code).group(1)
        self.assertRegex(versions, r"(?is)release_date\s+date\s*,")
        self.assertRegex(versions, r"(?is)released\s+boolean\s*$")
        self.assertNotRegex(versions, r"(?i)release_date\s+date\s+NOT\s+NULL")

    def test_les_migrations_se_suivent_sans_trou(self):
        numeros = {m.nom.split("_", 1)[1]: m.numero for m in db.lister_migrations()}
        self.assertEqual(numeros["flow_version_photo.sql"], numeros["flow_fix_version_share.sql"] + 1)
        liste = sorted(numeros.values())
        self.assertEqual(liste, list(range(1, len(liste) + 1)))


class AvecBase(unittest.TestCase):
    """Même base jetable que SchemaFlow (migrations appliquées, base supprimée à la fin)."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def semaine(self, c, lundi=LUNDI, source="live", couverture="complete"):
        c.execute("SET ROLE pmzilla_flow")
        run = c.execute("INSERT INTO flow.version_photo_runs (taken_at, source) VALUES (now(), %s) RETURNING id", (source,)).fetchone()[0]
        c.execute("INSERT INTO flow.version_photo_weeks (week_start, run_id, coverage) VALUES (%s, %s, %s)", (lundi, run, couverture))
        c.execute("RESET ROLE")
        return run

    def test_les_cinq_tables_existent(self):
        c = self.conn()
        noms = {r[0] for r in c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'flow' "
                                        "AND table_name LIKE 'version_photo%'")}
        self.assertEqual(noms, set(TABLES_PHOTO))

    def test_aucune_cle_etrangere_vers_les_tickets(self):
        c = self.conn()
        cibles = {r[0] for r in c.execute(
            "SELECT DISTINCT cl.relname FROM pg_constraint k JOIN pg_class cl ON cl.oid = k.confrelid "
            "JOIN pg_class src ON src.oid = k.conrelid JOIN pg_namespace n ON n.oid = src.relnamespace "
            "WHERE k.contype = 'f' AND n.nspname = 'flow' AND src.relname LIKE 'version_photo%'")}
        self.assertLessEqual(cibles, set(TABLES_PHOTO))

    def test_role_d_import_ecrit_et_les_autres_ne_lisent_pas(self):
        c = self.conn()
        self.semaine(c)
        c.commit()
        for table in TABLES_PHOTO:
            self.assertTrue(self.essaie(c, "pmzilla_flow", f"SELECT * FROM flow.{table}"), table)
            for role in ("pmzilla_flow_ro", "pmzilla_flow_views", "pmzilla_quality_views", "pmzilla_cases", "pmzilla_knowledge_ro"):
                self.assertFalse(self.essaie(c, role, f"SELECT * FROM flow.{table}"), f"{role} {table}")
        self.assertTrue(self.essaie(c, "pmzilla_flow", "UPDATE flow.version_photo_weeks SET coverage = 'partial'"))
        self.assertTrue(self.essaie(c, "pmzilla_flow", "DELETE FROM flow.version_photo_weeks"))

    def test_registre_de_n_ni_modifie_ni_supprime(self):
        c = self.conn()
        self.assertTrue(self.essaie(c, "pmzilla_flow", "INSERT INTO flow.version_photo_n (weeks, adopted_on) VALUES (6, '2026-11-20')"))
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.version_photo_n (weeks, adopted_on) VALUES (6, '2026-11-20')")
        c.execute("RESET ROLE")
        c.commit()
        self.assertFalse(self.essaie(c, "pmzilla_flow", "UPDATE flow.version_photo_n SET weeks = 8"))
        self.assertFalse(self.essaie(c, "pmzilla_flow", "DELETE FROM flow.version_photo_n"))
        self.assertFalse(self.essaie(c, "pmzilla_flow", "TRUNCATE flow.version_photo_n"))
        self.assertTrue(self.essaie(c, "pmzilla_flow", "SELECT * FROM flow.version_photo_n"))

    def test_n_positif_seulement(self):
        c = self.conn()
        c.execute("SET ROLE pmzilla_flow")
        with self.assertRaises(db.psycopg.errors.CheckViolation):
            with c.transaction():
                c.execute("INSERT INTO flow.version_photo_n (weeks, adopted_on) VALUES (0, '2026-11-20')")
        c.execute("RESET ROLE")

    def test_deuxieme_photo_de_la_meme_semaine_refusee(self):
        c = self.conn()
        self.semaine(c, LUNDI, "live")
        with self.assertRaises(db.psycopg.errors.UniqueViolation):
            with c.transaction():
                self.semaine(c, LUNDI, "live")
        with self.assertRaises(db.psycopg.errors.UniqueViolation):          # une semaine reconstruite ne recouvre jamais une semaine vivante
            with c.transaction():
                self.semaine(c, LUNDI, "reconstructed")
        self.semaine(c, LUNDI + dt.timedelta(days=7), "live")                # une autre semaine : acceptée

    def test_plusieurs_passages_reconstruits_une_seule_photo_par_semaine(self):
        """Décision du 2026-10-23 : un --replace laisse l'ancien passage (semaines non recalculables) à côté du nouveau ; la clé primaire de la
        semaine garantit une seule photo par semaine."""
        c = self.conn()
        self.semaine(c, LUNDI, "reconstructed", "partial")
        self.semaine(c, LUNDI + dt.timedelta(days=7), "reconstructed")                 # un second passage reconstruit : accepté
        with self.assertRaises(db.psycopg.errors.UniqueViolation):                       # jamais deux photos de la même semaine
            with c.transaction():
                self.semaine(c, LUNDI, "reconstructed")
        c.execute("SET ROLE pmzilla_flow")
        self.assertEqual(c.execute("SELECT count(*) FROM flow.version_photo_runs WHERE source = 'reconstructed'").fetchone()[0], 2)         # le passage de la tentative refusée est annulé avec elle
        c.execute("RESET ROLE")

    def test_sequences_d_identite_ni_lues_ni_utilisees_par_les_roles_de_lecture(self):
        c = self.conn()
        for sequence in ("version_photo_versions_version_no_seq", "version_photo_runs_id_seq", "version_photo_n_id_seq"):
            for role in ("pmzilla_flow_ro", "pmzilla_flow_views"):
                for droit in ("USAGE", "SELECT", "UPDATE"):
                    self.assertFalse(c.execute("SELECT has_sequence_privilege(%s, %s, %s)", (role, f"flow.{sequence}", droit)).fetchone()[0],
                                     f"{role} {sequence} {droit}")
            self.assertTrue(c.execute("SELECT has_sequence_privilege('pmzilla_flow', %s, 'USAGE')", (f"flow.{sequence}",)).fetchone()[0], sequence)

    def test_une_semaine_est_un_lundi(self):
        c = self.conn()
        with self.assertRaises(db.psycopg.errors.CheckViolation):
            with c.transaction():
                self.semaine(c, LUNDI + dt.timedelta(days=1))

    def test_source_et_couverture_dans_la_liste(self):
        c = self.conn()
        with self.assertRaises(db.psycopg.errors.CheckViolation):
            with c.transaction():
                self.semaine(c, LUNDI, source="autre")
        with self.assertRaises(db.psycopg.errors.CheckViolation):
            with c.transaction():
                self.semaine(c, LUNDI, couverture="autre")

    def test_ligne_de_version_ou_ligne_libre_jamais_les_deux(self):
        c = self.conn()
        self.semaine(c)
        c.execute("SET ROLE pmzilla_flow")
        no = c.execute("INSERT INTO flow.version_photo_versions (name) VALUES ('zzversion') RETURNING version_no").fetchone()[0]
        c.execute("INSERT INTO flow.version_photo_rows (week_start, team, version_no, found, found_open, corrected_at_week, "
                  "corrected_now, reopened) VALUES (%s, 'Alpha', %s, 1, 1, 0, 0, 0)", (LUNDI, no))
        c.execute("INSERT INTO flow.version_photo_rows (week_start, team, defects_created, defects_without_affects, resolved_week, "
                  "resolved_week_defects) VALUES (%s, 'Alpha', 1, 0, 3, 1)", (LUNDI,))
        with self.assertRaises(db.psycopg.errors.CheckViolation):
            with c.transaction():
                c.execute("INSERT INTO flow.version_photo_rows (week_start, team, version_no, found, found_open, corrected_at_week, "
                          "corrected_now, reopened, defects_created) VALUES (%s, 'Beta', %s, 1, 1, 0, 0, 0, 1)", (LUNDI, no))
        with self.assertRaises(db.psycopg.errors.UniqueViolation):          # une ligne libre par semaine et équipe
            with c.transaction():
                c.execute("INSERT INTO flow.version_photo_rows (week_start, team, defects_created, defects_without_affects, "
                          "resolved_week, resolved_week_defects) VALUES (%s, 'Alpha', 2, 0, 3, 1)", (LUNDI,))
        c.execute("RESET ROLE")

    def test_registre_des_versions_numero_opaque_et_date_nulle(self):
        c = self.conn()
        c.execute("SET ROLE pmzilla_flow")
        a = c.execute("INSERT INTO flow.version_photo_versions (name) VALUES ('zzversion-a') RETURNING version_no").fetchone()[0]
        b = c.execute("INSERT INTO flow.version_photo_versions (name) VALUES ('zzversion-b') RETURNING version_no").fetchone()[0]
        self.assertEqual(b, a + 1)
        self.assertEqual(c.execute("SELECT release_date, released FROM flow.version_photo_versions WHERE version_no = %s", (a,)).fetchone(),
                         (None, None))
        with self.assertRaises(db.psycopg.errors.UniqueViolation):
            with c.transaction():
                c.execute("INSERT INTO flow.version_photo_versions (name) VALUES ('zzversion-a')")
        c.execute("RESET ROLE")

    def test_la_suppression_d_un_passage_emporte_ses_semaines_et_ses_lignes(self):
        c = self.conn()
        run = self.semaine(c)
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.version_photo_rows (week_start, team, defects_created, defects_without_affects, resolved_week, "
                  "resolved_week_defects) VALUES (%s, 'Alpha', 1, 0, 3, 1)", (LUNDI,))
        c.execute("DELETE FROM flow.version_photo_runs WHERE id = %s", (run,))
        self.assertEqual(c.execute("SELECT count(*) FROM flow.version_photo_weeks").fetchone()[0], 0)
        self.assertEqual(c.execute("SELECT count(*) FROM flow.version_photo_rows").fetchone()[0], 0)
        c.execute("RESET ROLE")


if __name__ == "__main__":
    unittest.main()
