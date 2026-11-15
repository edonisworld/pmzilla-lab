"""
Tests de la migration du contexte des fiches de Mothra (change mothra-slices, tâche 18.1, design D19, D20, D29 ; décision de l'auteur du
2026-10-29) : trois colonnes ajoutées à `mothra.sheets` (portée, date des données, question de direction), droits inchangés.

    bash tools/dbtest.sh db        (passe de l'auteur : les modules de tests/db ne sont pas lancés par une session)

Les tests sans base (classe SansBase) lisent le fichier de migration. Les autres utilisent une base jetable migrée et sont sautés sans base
disponible (DBTEST_PORT). Aucun test n'écrit « dernière migration » : la migration se renumérote au rebase selon l'ordre des fusions.
Données inventées : identifiants pseudonymes u1 et u2.
"""
import re
import unittest

from test_db import db          # noqa: E402
from test_mothra_schema import BaseJetable, COLONNES_INTERDITES, ROLE, errors   # noqa: E402

QUESTIONS = ("scope_growth", "scope_reachability", "predictability", "next_version_quality")


def migration_contexte():
    candidates = [m for m in db.lister_migrations() if re.fullmatch(r"\d{4}_mothra_sheet_context\.sql", m.nom)]
    return candidates[0] if len(candidates) == 1 else None


def migration_schema():
    candidates = [m for m in db.lister_migrations() if re.fullmatch(r"\d{4}_mothra_schema\.sql", m.nom)]
    return candidates[0] if len(candidates) == 1 else None


class SansBase(unittest.TestCase):
    def texte(self):
        migration = migration_contexte()
        self.assertIsNotNone(migration, "une seule migration 'mothra_sheet_context' attendue")
        return migration.chemin.read_text(encoding="utf-8")

    def code(self):
        return "\n".join(ligne.split("--", 1)[0] for ligne in self.texte().splitlines())

    def test_elle_suit_la_migration_du_schema_et_commence_par_le_schema_touche(self):
        self.assertGreater(migration_contexte().numero, migration_schema().numero)
        self.assertRegex(self.texte().splitlines()[0], r"^-- Schéma touché : mothra")

    def test_elle_ne_fait_qu_ajouter_trois_colonnes_a_sheets_sous_le_proprietaire(self):
        code = self.code()
        self.assertRegex(code, r"(?is)SET\s+LOCAL\s+ROLE\s+pmzilla_owner\s*;")
        self.assertEqual(len(re.findall(r"(?i)\bALTER\s+TABLE\b", code)), 1)
        self.assertRegex(code, r"(?i)ALTER\s+TABLE\s+mothra\.sheets\b")
        ajoutees = re.findall(r"(?i)\bADD\s+COLUMN\s+(\w+)", code)
        self.assertEqual(ajoutees, ["scope", "data_date", "management_question"])
        for colonne in ajoutees:
            self.assertIsNone(COLONNES_INTERDITES.search(colonne), colonne)

    def test_aucun_droit_aucune_donnee_aucun_role(self):
        code = self.code()
        self.assertNotRegex(code, r"(?i)\b(GRANT|REVOKE)\b")                              # droits de la migration du schéma inchangés
        self.assertNotRegex(code, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(code, r"(?i)\bPASSWORD\b|\b(CREATE|DROP)\s+(ROLE|TABLE|SCHEMA)\b|\bLOGIN\b")

    def test_les_quatre_questions_de_direction_sont_la_liste_fermee(self):
        trouvees = re.search(r"(?is)management_question\s+IN\s*\((.*?)\)", self.code())
        self.assertIsNotNone(trouvees)
        self.assertEqual(tuple(re.findall(r"'([a-z_]+)'", trouvees.group(1))), QUESTIONS)


class AvecBase(BaseJetable):
    def colonnes(self, c):
        return {r[0]: r[1] for r in c.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'mothra' AND table_name = 'sheets'")}

    def test_les_trois_colonnes_existent_et_les_anciennes_insertions_restent_valides(self):
        c = self.conn()
        colonnes = self.colonnes(c)
        self.assertEqual((colonnes["scope"], colonnes["data_date"], colonnes["management_question"]), ("text", "date", "text"))
        self.execute(c, ROLE, "INSERT INTO mothra.sheets (kind, created_by) VALUES ('h5', 'u1')")

    def test_le_role_du_stockage_ecrit_et_met_a_jour_le_contexte_sans_pouvoir_supprimer(self):
        c = self.conn()
        self.execute(c, ROLE, "INSERT INTO mothra.sheets (kind, created_by, scope, data_date, management_question) "
                              "VALUES ('lead-cycle', 'u1', 'team-a', '2026-10-01', 'predictability')")
        self.execute(c, ROLE, "UPDATE mothra.sheets SET management_question = 'scope_growth' WHERE id = 1")
        ligne = self.execute(c, ROLE, "SELECT scope, data_date::text, management_question FROM mothra.sheets WHERE id = 1").fetchone()
        self.assertEqual(ligne, ("team-a", "2026-10-01", "scope_growth"))
        self.refuse(c, ROLE, "DELETE FROM mothra.sheets")

    def test_les_valeurs_hors_liste_ou_hors_forme_sont_refusees(self):
        c = self.conn()
        for scope, date, question in (("Team A", "2026-10-01", "predictability"),       # code en majuscules et espace
                                      ("team-a", "2026-10-01", "other_question"),        # hors des quatre questions
                                      ("team-a", None, "predictability"),                # portée sans date
                                      (None, "2026-10-01", "predictability")):           # date sans portée
            with self.assertRaises(errors.CheckViolation, msg=(scope, date, question)):
                self.execute(c, ROLE, "INSERT INTO mothra.sheets (kind, created_by, scope, data_date, management_question) "
                                      "VALUES ('lead-cycle', 'u1', %s, %s, %s)", (scope, date, question))


if __name__ == "__main__":
    unittest.main()
