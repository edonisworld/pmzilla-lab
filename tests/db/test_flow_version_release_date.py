"""Date de sortie et drapeau des versions courantes (change version-release-date, tâches 2.1 et 3.3 ; spec jira-flow-import « Current versions
derived », jira-flow-version-photo « Release dates filled from the stored current versions »).

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Les tests sans base (SansBase) tournent toujours : lecture du fichier de migration, retrouvé par sa description et non par son numéro. Les
autres utilisent la base jetable de test_flow_schema.py et sont sautés sans elle (bash tools/dbtest.sh db). Données inventées.
"""
import datetime as dt
import re
import unittest

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402

SUFFIXE = "_flow_version_release_date.sql"
SECRET = "zzversion-secrete"


def migration():
    candidats = [m for m in db.lister_migrations() if m.nom.endswith(SUFFIXE)]
    return candidats[0] if len(candidats) == 1 else None


def code():
    m = migration()
    assert m is not None, f"une migration *{SUFFIXE} est attendue"
    return m.chemin.read_text(encoding="utf-8")


def sans_commentaires(texte):
    return re.sub(r"--[^\n]*", "", texte)


class SansBase(unittest.TestCase):
    def test_deux_colonnes_nulles_sur_la_table_des_versions_courantes(self):
        texte = code()
        sql = sans_commentaires(texte)
        self.assertRegex(texte.splitlines()[0], r"^-- Schéma touché : flow")
        self.assertRegex(sql, r"(?is)SET\s+LOCAL\s+ROLE\s+pmzilla_owner\s*;")
        alter = re.search(r"(?is)ALTER\s+TABLE\s+flow\.issue_current_versions(.*?);", sql)
        self.assertIsNotNone(alter)
        self.assertRegex(alter.group(1), r"(?is)ADD\s+COLUMN\s+release_date\s+date\s*,")
        self.assertRegex(alter.group(1), r"(?is)ADD\s+COLUMN\s+released\s+boolean\s*$")
        self.assertNotRegex(alter.group(1), r"(?i)NOT\s+NULL|DEFAULT")
        self.assertEqual(len(re.findall(r"(?i)\bADD\s+COLUMN\b", sql)), 2)             # aucun autre attribut de version

    def test_aucun_droit_donnee_ni_role_ni_donnee(self):
        sql = sans_commentaires(code())
        self.assertNotRegex(sql, r"(?i)\b(GRANT|REVOKE)\b")                              # droits inchangés
        self.assertNotRegex(sql, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(sql, r"(?i)\bPASSWORD\b|\b(CREATE|DROP)\s+(ROLE|TABLE)\b|\bLOGIN\b")

    def test_numerotee_apres_la_derniere_sans_trou(self):
        numeros = {m.nom.split("_", 1)[1]: m.numero for m in db.lister_migrations()}
        nom = SUFFIXE.lstrip("_")
        suivantes = {"flow_masquage_somme.sql", "cycle_referential.sql", "mothra_schema.sql", "flow_definitions.sql", "flow_slice1_views.sql", "mothra_sheet_context.sql", "quality_patient_detection.sql", "flow_slice1_mask_comptes.sql", "flow_t3_withheld.sql", "flow_team_flow_inout.sql", "flow_delivery_fields.sql", "flow_delivery_fields_view.sql", "flow_delivery_option_ids.sql", "flow_masquage_propagation.sql", "flow_masquage_ecart_d4d.sql", "flow_lead_time_old_zero.sql", "flow_lead_time_without_old.sql", "mothra_views_role.sql", "flow_trois_trimestres_clos.sql"}   # + 0040, trois trimestres clos (R-20261114-49) ; + 0039, rôle propre à Mothra (R-20261107-26 décision 3 (a), A-80) ; + 0038, 22.1 (R-20261105-30, R-20261106-52) ; + 0037, 22.1 (R-20261106-39) ; + 0036, R-20261106-22 et R-20261106-23 ; + masquage, groupe 6 (R-144, 0035) ; + jira-delivery-fields, R-20261102-16 à -36 ; 0034, R-20261102-51 (liste fermée des migrations suivantes, étendue comme pour 0032 et 0033)   # masking-sums (R-144) vient juste après, sans trou
        self.assertEqual(numeros[nom], max(n for k, n in numeros.items() if k not in suivantes))
        self.assertEqual(sorted(numeros.values()), list(range(1, len(numeros) + 1)))
        self.assertEqual(numeros[nom], numeros["flow_version_photo_views.sql"] + 1)


class AvecBase(unittest.TestCase):
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def ticket(self, c, cle):
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, updated_at) "
                  "VALUES (%s, 'PROJ', 'Bug', 'Closed', 'Done', now(), now())", (cle,))
        c.execute("RESET ROLE")

    def test_colonnes_nulles_de_types_date_et_boolean(self):
        c = self.conn()
        lignes = c.execute("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema = 'flow' "
                           "AND table_name = 'issue_current_versions' AND column_name IN ('release_date', 'released') ORDER BY column_name").fetchall()
        self.assertEqual(lignes, [("release_date", "date", "YES"), ("released", "boolean", "YES")])

    def test_ligne_sans_attributs_garde_des_valeurs_nulles(self):
        c = self.conn()
        self.ticket(c, "PROJ-1")
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.issue_current_versions (issue_key, kind, name) VALUES ('PROJ-1', 'fix', %s)", (SECRET,))
        self.assertEqual(c.execute("SELECT release_date, released FROM flow.issue_current_versions").fetchone(), (None, None))
        c.execute("UPDATE flow.issue_current_versions SET release_date = %s, released = TRUE", (dt.date(2029, 7, 14),))
        self.assertEqual(c.execute("SELECT release_date, released FROM flow.issue_current_versions").fetchone(), (dt.date(2029, 7, 14), True))
        c.execute("RESET ROLE")

    def test_droits_inchanges_aucun_autre_role_ne_lit_les_colonnes(self):
        c = self.conn()
        for role in ("pmzilla_flow_views", "pmzilla_quality_views", "pmzilla_flow_ro"):
            self.assertFalse(self.essaie(c, role, "SELECT release_date, released FROM flow.issue_current_versions"), role)
        self.assertTrue(self.essaie(c, "pmzilla_flow", "SELECT release_date, released FROM flow.issue_current_versions"))

    def test_suppression_en_cascade_du_ticket(self):
        c = self.conn()
        self.ticket(c, "PROJ-1")
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.issue_current_versions (issue_key, kind, name, release_date, released) "
                  "VALUES ('PROJ-1', 'fix', %s, %s, TRUE)", (SECRET, dt.date(2029, 7, 14)))
        c.execute("DELETE FROM flow.issues WHERE key = 'PROJ-1'")
        self.assertEqual(c.execute("SELECT count(*) FROM flow.issue_current_versions").fetchone()[0], 0)
        c.execute("RESET ROLE")


if __name__ == "__main__":
    unittest.main()
