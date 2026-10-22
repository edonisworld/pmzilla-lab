"""
Cohérence du dump partiel de `quality` (change story-quality-audit, tâche 3.26, design D10 amendé le 2026-10-18, spec database-backup-restore
« The partial quality dump restores coherently »). Test STATIQUE : il lit les migrations et le script de sauvegarde, sans base ni Docker.

Les trois tables du dump partiel (attributs d'équipe, relectures d'équipe, versions de surcouche) ne portent aucun texte de story ni clé de
ticket. Pour qu'elles se restaurent seules dans les tables vides recréées par les migrations, aucune ne doit avoir de clé étrangère vers une
table hors du dump (items, éléments d'équipe, contenus, verdicts, retours de coaching) : le test échoue en NOMMANT la table dès qu'une
migration lui en donne une.

    uv run python -W ignore -m unittest discover -s tests/db -p "test_quality_dump_coherence.py" -q
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
MIGRATIONS = RACINE / "db" / "migrations"
SCRIPT_SAUVEGARDE = RACINE / "tools" / "db_backup.sh"
TABLES_DU_DUMP = ("team_attributes", "team_reviews", "overlay_versions")
AUTRES_TABLES = ("items", "item_teams", "contents", "assessments", "coaching_feedback")


def sans_commentaires(sql: str) -> str:
    return "\n".join(re.sub(r"--.*$", "", ligne) for ligne in sql.splitlines())


def corps_de_table(sql: str, table: str) -> list[str]:
    """Corps (entre parenthèses) de chaque CREATE TABLE quality.<table> du texte SQL."""
    corps = []
    for m in re.finditer(rf"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?quality\.{table}\s*\(", sql, flags=re.I):
        profondeur, i = 1, m.end()
        while i < len(sql) and profondeur:
            profondeur += {"(": 1, ")": -1}.get(sql[i], 0)
            i += 1
        corps.append(sql[m.end():i - 1])
    return corps


def cibles_de_references(texte: str) -> set[str]:
    """Tables visées par un REFERENCES du texte, sans le préfixe de schéma quality."""
    return {m.group(1).split(".")[-1].strip('"').lower() for m in re.finditer(r"REFERENCES\s+([A-Za-z0-9_.\"]+)", texte, flags=re.I)}


def tables_avec_cle_etrangere_hors_du_dump(migrations: list[str], dumpees=TABLES_DU_DUMP) -> list[str]:
    """Noms des tables du dump qui ont (ou gagnent par ALTER TABLE) une clé étrangère vers une table hors du dump."""
    fautives = set()
    for sql in map(sans_commentaires, migrations):
        for table in dumpees:
            textes = corps_de_table(sql, table)
            textes += [m.group(0) for m in re.finditer(rf"ALTER\s+TABLE\s+(?:ONLY\s+)?quality\.{table}\b[^;]*;", sql, flags=re.I)]
            for texte in textes:
                if any(cible not in dumpees for cible in cibles_de_references(texte)):
                    fautives.add(table)
    return sorted(fautives)


def migrations_reelles() -> list[str]:
    return [f.read_text(encoding="utf-8") for f in sorted(MIGRATIONS.glob("*.sql"))]


class Migrations(unittest.TestCase):
    def test_aucune_table_du_dump_n_a_de_cle_etrangere_vers_une_table_hors_du_dump(self):
        fautives = tables_avec_cle_etrangere_hors_du_dump(migrations_reelles())
        self.assertEqual(fautives, [], f"table(s) du dump partiel de quality avec une clé étrangère vers une table hors du dump : {fautives}")

    def test_les_trois_tables_du_dump_sont_creees_par_les_migrations(self):
        sql = sans_commentaires("\n".join(migrations_reelles()))
        for table in TABLES_DU_DUMP:
            self.assertEqual(len(corps_de_table(sql, table)), 1, table)

    def test_le_detecteur_voit_les_references_de_la_migration_0010_hors_du_dump(self):
        """Garde du détecteur : les tables hors du dump ont bien des clés étrangères, et il les voit."""
        sql = sans_commentaires("\n".join(migrations_reelles()))
        self.assertIn("items", cibles_de_references("\n".join(corps_de_table(sql, "item_teams"))))
        self.assertIn("items", cibles_de_references("\n".join(corps_de_table(sql, "assessments"))))
        self.assertIn("items", cibles_de_references("\n".join(corps_de_table(sql, "contents"))))
        self.assertIn("items", cibles_de_references("\n".join(corps_de_table(sql, "coaching_feedback"))))


# Colonnes figées des trois tables du dump partiel (D10) : aucune ne porte de texte de story ni de clé de ticket. Une colonne ajoutée plus
# tard (par CREATE ou ALTER TABLE) fait échouer le test : elle serait dumpée par défaut ; il faut la relire avant de la déclarer ici.
COLONNES_FIGEES = {
    "team_attributes": ["team", "single_po"],
    "team_reviews": ["id", "team", "reviewed_at", "sample_size"],
    "overlay_versions": ["overlay_id", "version", "content_hash", "first_used_at"],
}
DEBUTS_DE_CONTRAINTE = ("primary", "unique", "check", "constraint", "foreign", "exclude", "like")


def colonnes_declarees(migrations: list[str], table: str) -> list[str]:
    """Noms de colonnes d'une table : CREATE TABLE (dans l'ordre), puis ALTER TABLE … ADD [COLUMN]."""
    noms = []
    for sql in map(sans_commentaires, migrations):
        for corps in corps_de_table(sql, table):
            morceaux, profondeur, courant = [], 0, ""
            for c in corps:
                profondeur += {"(": 1, ")": -1}.get(c, 0)
                if c == "," and profondeur == 0:
                    morceaux.append(courant)
                    courant = ""
                else:
                    courant += c
            morceaux.append(courant)
            for m in morceaux:
                mot = m.strip().split()[:1]
                if mot and mot[0].lower() not in DEBUTS_DE_CONTRAINTE:
                    noms.append(mot[0].strip('"'))
        for m in re.finditer(rf"ALTER\s+TABLE\s+(?:ONLY\s+)?quality\.{table}\b([^;]*);", sql, flags=re.I):
            for a in re.finditer(r"ADD\s+(?:COLUMN\s+)?(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_\"]*)", m.group(1), flags=re.I):
                if a.group(1).lower() not in DEBUTS_DE_CONTRAINTE:
                    noms.append(a.group(1).strip('"'))
    return noms


class Colonnes(unittest.TestCase):
    def test_les_colonnes_des_trois_tables_sont_figees(self):
        for table, attendues in COLONNES_FIGEES.items():
            self.assertEqual(colonnes_declarees(migrations_reelles(), table), attendues,
                             f"colonnes de quality.{table} changées : relire qu'aucune ne porte de texte de story ni de clé avant de les déclarer")

    def test_une_colonne_ajoutee_plus_tard_fait_echouer_le_test(self):
        base = Detecteur.BASE
        for suite in ("ALTER TABLE quality.team_reviews ADD COLUMN note text;\n",
                      "ALTER TABLE quality.team_attributes ADD note text NOT NULL DEFAULT '';\n"):
            table = re.search(r"quality\.(\w+)", suite).group(1)
            self.assertNotEqual(colonnes_declarees([base, suite], table), colonnes_declarees([base], table))
        crea = base.replace("single_po boolean NOT NULL DEFAULT false", "single_po boolean NOT NULL DEFAULT false, note text")
        self.assertEqual(colonnes_declarees([crea], "team_attributes"), ["team", "single_po", "note"])
        self.assertEqual(colonnes_declarees([base], "team_attributes"), ["team", "single_po"])
        self.assertEqual(colonnes_declarees([base], "overlay_versions"), ["overlay_id", "version"])       # la contrainte de clé n'est pas une colonne


class Detecteur(unittest.TestCase):
    """Le test statique échoue, en nommant la table, quand une migration ajoute la clé étrangère interdite."""

    BASE = ("CREATE TABLE quality.items (key text PRIMARY KEY);\n"
            "CREATE TABLE quality.team_attributes (team text PRIMARY KEY, single_po boolean NOT NULL DEFAULT false);\n"
            "CREATE TABLE quality.team_reviews (id bigint PRIMARY KEY, team text NOT NULL, sample_size integer);\n"
            "CREATE TABLE quality.overlay_versions (overlay_id text, version text, PRIMARY KEY (overlay_id, version));\n")

    def test_base_saine(self):
        self.assertEqual(tables_avec_cle_etrangere_hors_du_dump([self.BASE]), [])

    def test_cle_etrangere_a_la_creation_vers_la_table_des_elements(self):
        sql = self.BASE.replace("team text NOT NULL, sample_size", "team text NOT NULL REFERENCES quality.items (key), sample_size")
        self.assertEqual(tables_avec_cle_etrangere_hors_du_dump([sql]), ["team_reviews"])

    def test_cle_etrangere_ajoutee_par_une_migration_posterieure(self):
        suite = "ALTER TABLE quality.team_attributes ADD CONSTRAINT fk FOREIGN KEY (team) REFERENCES quality.items (key);\n"
        self.assertEqual(tables_avec_cle_etrangere_hors_du_dump([self.BASE, suite]), ["team_attributes"])

    def test_cle_etrangere_sans_prefixe_de_schema_ou_vers_un_autre_schema(self):
        sql = self.BASE.replace("version text, PRIMARY KEY", "version text REFERENCES public.schema_migrations (numero), PRIMARY KEY")
        self.assertEqual(tables_avec_cle_etrangere_hors_du_dump([sql]), ["overlay_versions"])

    def test_cle_etrangere_entre_deux_tables_du_dump_acceptee(self):
        sql = self.BASE.replace("team text NOT NULL, sample_size", "team text NOT NULL REFERENCES quality.team_attributes (team), sample_size")
        self.assertEqual(tables_avec_cle_etrangere_hors_du_dump([sql]), [])

    def test_un_commentaire_n_est_pas_une_reference(self):
        sql = self.BASE.replace("single_po boolean", "single_po boolean -- REFERENCES quality.items\n,\n  autre boolean")
        self.assertEqual(tables_avec_cle_etrangere_hors_du_dump([sql]), [])


class ScriptDeSauvegarde(unittest.TestCase):
    def test_le_script_nomme_les_trois_tables_une_a_une_et_aucune_autre(self):
        texte = "\n".join(l for l in SCRIPT_SAUVEGARDE.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))
        tables = re.findall(r"-t\s+(quality\.[a-z_]+)", texte)
        self.assertEqual(sorted(tables), sorted(f"quality.{t}" for t in TABLES_DU_DUMP))
        for autre in AUTRES_TABLES:
            self.assertNotIn(f"quality.{autre}", texte)
        self.assertNotRegex(texte, r"-n\s+[\"']?quality\b")


if __name__ == "__main__":
    unittest.main()
