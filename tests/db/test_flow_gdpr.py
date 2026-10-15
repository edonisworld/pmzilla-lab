"""
Tests de la migration 0008 (alignement RGPD de l'export Jira, R-58, design D20) : instant « sorti de l'export » sur flow.issues, tables
des périodes d'étiquettes déclarées et de fixVersion, quatre vues agrégées qui écartent les tickets marqués, droits des rôles.

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Les tests sans base (classe SansBase) tournent toujours : lecture du fichier de migration. Les autres utilisent la base jetable de
test_flow_schema.py (même fixture) et sont sautés quand aucun mot de passe ou aucune base n'est disponible
(bash tools/dbtest.sh db). Données inventées : tickets PROJ-n, équipes Alpha et Beta, étiquettes et versions génériques.
"""
import re
import unittest

import test_db as base          # noqa: E402
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402  (module importé, pas la classe : ses tests ne tournent pas deux fois)

SEMAINE = "2026-03-04T10:00:00+00:00"          # un mercredi : toutes les résolutions du jeu tombent dans la même semaine UTC


class BaseJetable(unittest.TestCase):
    """Même base jetable que SchemaFlow : migrations appliquées (0008 comprise), base supprimée à la fin."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def equipes(self, c):
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.teams (name) VALUES ('Alpha'), ('Beta')")
        c.execute("RESET ROLE")

    def inserer(self, c, cle, equipe_id, categorie="To Do", resolu=None, cree="now() - interval '2 days'"):
        """Un ticket sous le rôle d'import. `cree` est une expression SQL fixe du test, jamais une saisie."""
        c.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, resolved_at, updated_at, team_id) "
                  f"VALUES (%s, 'PROJ', 'Story', 'X', %s, {cree}, %s::timestamptz, now(), %s)",
                  (cle, categorie, resolu, equipe_id))

    def marquer(self, c, *cles):
        c.execute("SET ROLE pmzilla_flow")
        c.execute("UPDATE flow.issues SET out_of_export_at = now() WHERE key = ANY(%s)", (list(cles),))
        c.execute("RESET ROLE")

    def demarquer(self, c, *cles):
        c.execute("SET ROLE pmzilla_flow")
        c.execute("UPDATE flow.issues SET out_of_export_at = NULL WHERE key = ANY(%s)", (list(cles),))
        c.execute("RESET ROLE")

    def vue(self, c, sql):
        c.execute("SET ROLE pmzilla_flow_views")
        try:
            return c.execute(sql).fetchall()
        finally:
            c.execute("RESET ROLE")


class ColonneEtTables(BaseJetable):
    def test_colonne_nullable_et_nulle_par_defaut(self):
        c = self.conn()
        self.equipes(c)
        c.execute("SET ROLE pmzilla_flow")
        self.inserer(c, "PROJ-1", 1)
        self.assertIsNone(c.execute("SELECT out_of_export_at FROM flow.issues WHERE key = 'PROJ-1'").fetchone()[0])
        c.execute("UPDATE flow.issues SET out_of_export_at = now() WHERE key = 'PROJ-1'")
        self.assertIsNotNone(c.execute("SELECT out_of_export_at FROM flow.issues WHERE key = 'PROJ-1'").fetchone()[0])
        c.execute("UPDATE flow.issues SET out_of_export_at = NULL WHERE key = 'PROJ-1'")      # on peut le retirer (ticket revenu)
        self.assertIsNone(c.execute("SELECT out_of_export_at FROM flow.issues WHERE key = 'PROJ-1'").fetchone()[0])
        c.execute("RESET ROLE")

    def test_colonnes_des_tables_de_periodes(self):
        c = self.conn()
        for table, nom in ((fs.TABLE_ETIQUETTES, "label"), (fs.TABLE_VERSIONS, "version")):
            colonnes = {r[0]: (r[1], r[2]) for r in c.execute(
                "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                "WHERE table_schema = 'flow' AND table_name = %s", (table,))}
            self.assertEqual(colonnes, {"issue_key": ("text", "NO"), nom: ("text", "NO"),
                                        "added_at": ("timestamp with time zone", "NO"),
                                        "removed_at": ("timestamp with time zone", "YES")}, table)

    def test_cle_etrangere_en_cascade_vers_issues(self):
        c = self.conn()
        for table in (fs.TABLE_ETIQUETTES, fs.TABLE_VERSIONS):
            ligne = c.execute(
                "SELECT ccu.table_name, ccu.column_name, rc.delete_rule FROM information_schema.table_constraints tc "
                "JOIN information_schema.referential_constraints rc ON rc.constraint_name = tc.constraint_name "
                "AND rc.constraint_schema = tc.constraint_schema "
                "JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = rc.unique_constraint_name "
                "AND ccu.constraint_schema = rc.unique_constraint_schema "
                "WHERE tc.table_schema = 'flow' AND tc.table_name = %s AND tc.constraint_type = 'FOREIGN KEY'", (table,)).fetchall()
            self.assertEqual(ligne, [("issues", "key", "CASCADE")], table)

    def test_cle_etrangere_refusee_et_periode_inversee_refusee(self):
        c = self.conn()
        self.equipes(c)
        c.execute("SET ROLE pmzilla_flow")
        self.inserer(c, "PROJ-1", 1)
        with self.assertRaises(db.psycopg.errors.ForeignKeyViolation):
            with c.transaction():
                c.execute(f"INSERT INTO flow.{fs.TABLE_ETIQUETTES} (issue_key, label, added_at) VALUES ('NOPE-1', 'etiquette-a', now())")
        with self.assertRaises(db.psycopg.errors.ForeignKeyViolation):
            with c.transaction():
                c.execute(f"INSERT INTO flow.{fs.TABLE_VERSIONS} (issue_key, version, added_at) VALUES ('NOPE-1', 'version-a', now())")
        for table, colonne in ((fs.TABLE_ETIQUETTES, "label"), (fs.TABLE_VERSIONS, "version")):
            with self.assertRaises(db.psycopg.errors.CheckViolation):
                with c.transaction():
                    c.execute(f"INSERT INTO flow.{table} (issue_key, {colonne}, added_at, removed_at) "
                              "VALUES ('PROJ-1', 'x', '2026-03-02T10:00:00+00:00', '2026-03-01T10:00:00+00:00')")
            c.execute(f"INSERT INTO flow.{table} (issue_key, {colonne}, added_at, removed_at) "      # fermée le jour même : permis
                      "VALUES ('PROJ-1', 'y', '2026-03-02T10:00:00+00:00', '2026-03-02T10:00:00+00:00')")
        c.execute("RESET ROLE")

    def test_une_periode_n_existe_qu_une_fois(self):
        c = self.conn()
        self.equipes(c)
        c.execute("SET ROLE pmzilla_flow")
        self.inserer(c, "PROJ-1", 1)
        for table, colonne in ((fs.TABLE_ETIQUETTES, "label"), (fs.TABLE_VERSIONS, "version")):
            c.execute(f"INSERT INTO flow.{table} (issue_key, {colonne}, added_at) VALUES ('PROJ-1', 'x', '2026-03-02T10:00:00+00:00')")
            with self.assertRaises(db.psycopg.errors.UniqueViolation):
                with c.transaction():
                    c.execute(f"INSERT INTO flow.{table} (issue_key, {colonne}, added_at) "
                              "VALUES ('PROJ-1', 'x', '2026-03-02T12:00:00+02:00')")          # même instant, autre fuseau
            # la même étiquette reposée plus tard est une autre période
            c.execute(f"INSERT INTO flow.{table} (issue_key, {colonne}, added_at) VALUES ('PROJ-1', 'x', '2026-03-09T10:00:00+00:00')")
        c.execute("RESET ROLE")

    def test_version_deplacee_une_periode_fermee_et_une_ouverte(self):
        """Scénario « Version moved » de la capacité jira-flow-labels, côté base : la première version est fermée, la seconde ouverte."""
        c = self.conn()
        self.equipes(c)
        c.execute("SET ROLE pmzilla_flow")
        self.inserer(c, "PROJ-1", 1)
        c.execute(f"INSERT INTO flow.{fs.TABLE_VERSIONS} (issue_key, version, added_at, removed_at) "
                  "VALUES ('PROJ-1', 'version-a', '2026-03-02T10:00:00+00:00', '2026-03-05T10:00:00+00:00')")
        c.execute(f"INSERT INTO flow.{fs.TABLE_VERSIONS} (issue_key, version, added_at) VALUES ('PROJ-1', 'version-b', '2026-03-05T10:00:00+00:00')")
        lignes = c.execute(f"SELECT version, removed_at IS NULL FROM flow.{fs.TABLE_VERSIONS} WHERE issue_key = 'PROJ-1' ORDER BY added_at").fetchall()
        self.assertEqual(lignes, [("version-a", False), ("version-b", True)])
        c.execute("RESET ROLE")

    def test_la_cascade_emporte_les_periodes(self):
        c = self.conn()
        self.equipes(c)
        c.execute("SET ROLE pmzilla_flow")
        for cle in ("PROJ-1", "PROJ-2"):
            self.inserer(c, cle, 1)
            c.execute(f"INSERT INTO flow.{fs.TABLE_ETIQUETTES} (issue_key, label, added_at) VALUES (%s, 'etiquette-a', now())", (cle,))
            c.execute(f"INSERT INTO flow.{fs.TABLE_VERSIONS} (issue_key, version, added_at) VALUES (%s, 'version-a', now())", (cle,))
        c.execute("DELETE FROM flow.issues WHERE key = 'PROJ-1'")
        for table in (fs.TABLE_ETIQUETTES, fs.TABLE_VERSIONS):
            self.assertEqual(c.execute(f"SELECT issue_key FROM flow.{table}").fetchall(), [("PROJ-2",)], table)
        c.execute("RESET ROLE")

    def test_aucune_donnee_inseree_par_la_migration(self):
        c = self.conn()
        for table in fs.TABLES:
            self.assertEqual(c.execute(f"SELECT count(*) FROM flow.{table}").fetchone()[0], 0, table)


class DroitsDesRoles(BaseJetable):
    def test_role_d_import_ecrit_les_periodes_et_met_a_jour_l_instant(self):
        c = self.conn()
        self.equipes(c)
        c.execute("SET ROLE pmzilla_flow")
        self.inserer(c, "PROJ-1", 1)
        c.execute("RESET ROLE")
        c.commit()
        for table, colonne in ((fs.TABLE_ETIQUETTES, "label"), (fs.TABLE_VERSIONS, "version")):
            self.assertTrue(self.essaie(c, "pmzilla_flow", f"INSERT INTO flow.{table} (issue_key, {colonne}, added_at) VALUES ('PROJ-1', 'x', now())"))
            self.assertTrue(self.essaie(c, "pmzilla_flow", f"UPDATE flow.{table} SET removed_at = now() + interval '1 day' WHERE issue_key = 'PROJ-1'"))
            self.assertTrue(self.essaie(c, "pmzilla_flow", f"DELETE FROM flow.{table} WHERE issue_key = 'PROJ-1'"))
        self.assertTrue(self.essaie(c, "pmzilla_flow", "UPDATE flow.issues SET out_of_export_at = now() WHERE key = 'PROJ-1'"))

    def test_role_de_lecture_seule_lit_et_n_ecrit_pas(self):
        c = self.conn()
        self.equipes(c)
        c.execute("SET ROLE pmzilla_flow")
        self.inserer(c, "PROJ-1", 1)
        c.execute(f"INSERT INTO flow.{fs.TABLE_ETIQUETTES} (issue_key, label, added_at) VALUES ('PROJ-1', 'etiquette-a', now())")
        c.execute(f"INSERT INTO flow.{fs.TABLE_VERSIONS} (issue_key, version, added_at) VALUES ('PROJ-1', 'version-a', now())")
        c.execute("RESET ROLE")
        c.commit()
        for table, colonne in ((fs.TABLE_ETIQUETTES, "label"), (fs.TABLE_VERSIONS, "version")):
            self.assertTrue(self.essaie(c, "pmzilla_flow_ro", f"SELECT * FROM flow.{table}"))
            self.assertFalse(self.essaie(c, "pmzilla_flow_ro", f"INSERT INTO flow.{table} (issue_key, {colonne}, added_at) VALUES ('PROJ-1', 'y', now())"))
            self.assertFalse(self.essaie(c, "pmzilla_flow_ro", f"UPDATE flow.{table} SET removed_at = now()"))
            self.assertFalse(self.essaie(c, "pmzilla_flow_ro", f"DELETE FROM flow.{table}"))
        self.assertTrue(self.essaie(c, "pmzilla_flow_ro", "SELECT out_of_export_at FROM flow.issues"))
        self.assertFalse(self.essaie(c, "pmzilla_flow_ro", "UPDATE flow.issues SET out_of_export_at = now()"))

    def test_role_des_vues_ne_lit_ni_les_nouvelles_tables_ni_la_colonne(self):
        c = self.conn()
        for table in (fs.TABLE_ETIQUETTES, fs.TABLE_VERSIONS):
            self.assertFalse(self.essaie(c, "pmzilla_flow_views", f"SELECT * FROM flow.{table}"), table)
            self.assertFalse(self.essaie(c, "pmzilla_flow_views", f"DELETE FROM flow.{table}"), table)
        self.assertFalse(self.essaie(c, "pmzilla_flow_views", "SELECT out_of_export_at FROM flow.issues"))
        self.assertFalse(self.essaie(c, "pmzilla_flow_views", "UPDATE flow.issues SET out_of_export_at = now()"))

    def test_role_des_vues_lit_encore_les_quatre_vues_recreees(self):
        c = self.conn()
        for vue in fs.VUES:
            self.assertTrue(self.essaie(c, "pmzilla_flow_views", f"SELECT * FROM flow.{vue}"), vue)
        # propriétaire des vues inchangé : elles s'exécutent avec les droits du propriétaire, pas ceux du lecteur
        proprietaires = {r[0] for r in c.execute("SELECT viewowner FROM pg_views WHERE schemaname = 'flow'")}
        self.assertEqual(proprietaires, {"pmzilla_owner"})

    def test_autres_roles_sans_droit_sur_les_nouvelles_tables(self):
        c = self.conn()
        for table in (fs.TABLE_ETIQUETTES, fs.TABLE_VERSIONS):
            self.assertFalse(self.essaie(c, "pmzilla_cases", f"SELECT * FROM flow.{table}"), table)
            self.assertFalse(self.essaie(c, "pmzilla_knowledge_ro", f"SELECT * FROM flow.{table}"), table)


class VuesSansTicketsMarques(BaseJetable):
    def test_statut_six_ouverts_dont_un_marque_donne_cinq(self):
        """Scénario « Marked ticket » de la spec database-roles-views."""
        c = self.conn()
        self.equipes(c)
        c.execute("SET ROLE pmzilla_flow")
        for i in range(1, 7):
            self.inserer(c, f"PROJ-{i}", 1)
        c.execute("RESET ROLE")
        c.commit()
        self.assertEqual(self.vue(c, "SELECT team, status_category, tickets FROM flow.v_team_status"), [("Alpha", "To Do", 6)])
        self.marquer(c, "PROJ-1")
        c.commit()
        self.assertEqual(self.vue(c, "SELECT team, status_category, tickets FROM flow.v_team_status"), [("Alpha", "To Do", 5)])
        self.demarquer(c, "PROJ-1")                         # un ticket qui revient dans l'export revient dans la vue
        c.commit()
        self.assertEqual(self.vue(c, "SELECT tickets FROM flow.v_team_status"), [(6,)])

    def test_statut_une_cellule_dont_tous_les_tickets_sont_marques_disparait(self):
        c = self.conn()
        self.equipes(c)
        c.execute("SET ROLE pmzilla_flow")
        for i in range(1, 6):
            self.inserer(c, f"PROJ-{i}", 1)
        c.execute("RESET ROLE")
        self.marquer(c, *[f"PROJ-{i}" for i in range(1, 6)])
        c.commit()
        self.assertEqual(self.vue(c, "SELECT * FROM flow.v_team_status"), [])

    def test_resolutions_par_semaine(self):
        c = self.conn()
        self.equipes(c)
        c.execute("SET ROLE pmzilla_flow")
        for i in range(1, 7):
            self.inserer(c, f"PROJ-{i}", 1, categorie="Done", resolu=SEMAINE)
        c.execute("RESET ROLE")
        c.commit()
        self.assertEqual(self.vue(c, "SELECT tickets FROM flow.v_team_weekly_resolved"), [(6,)])
        self.marquer(c, "PROJ-1")
        c.commit()
        self.assertEqual(self.vue(c, "SELECT tickets FROM flow.v_team_weekly_resolved"), [(5,)])

    def test_age_des_tickets_ouverts(self):
        c = self.conn()
        self.equipes(c)
        c.execute("SET ROLE pmzilla_flow")
        for i in range(1, 7):
            self.inserer(c, f"PROJ-{i}", 1)
        c.execute("RESET ROLE")
        c.commit()
        self.assertEqual(self.vue(c, "SELECT age_bucket, tickets FROM flow.v_team_open_age"), [("0-7 j", 6)])
        self.marquer(c, "PROJ-1")
        c.commit()
        self.assertEqual(self.vue(c, "SELECT age_bucket, tickets FROM flow.v_team_open_age"), [("0-7 j", 5)])

    def liens(self, c):
        """Six tickets Alpha qui bloquent six tickets Beta : une seule cellule de six liens."""
        self.equipes(c)
        c.execute("SET ROLE pmzilla_flow")
        for i in range(1, 7):
            self.inserer(c, f"PROJ-A{i}", 1)
            self.inserer(c, f"PROJ-B{i}", 2)
            c.execute("INSERT INTO flow.links (source_key, target_key, link_type, direction) VALUES (%s, %s, 'Blocks', 'outward')",
                      (f"PROJ-A{i}", f"PROJ-B{i}"))
        c.execute("RESET ROLE")
        c.commit()

    def lues(self, c):
        return {(r[0], r[1], r[2]): r[3] for r in self.vue(c, "SELECT source_team, target_team, link_type, links FROM flow.v_team_dependencies")}

    def test_dependances_ticket_source_marque_lien_ecarte(self):
        c = self.conn()
        self.liens(c)
        self.assertEqual(self.lues(c), {("Alpha", "Beta", "Blocks"): 6})
        self.marquer(c, "PROJ-A1")
        c.commit()
        self.assertEqual(self.lues(c), {("Alpha", "Beta", "Blocks"): 5})

    def test_dependances_cible_marquee_se_lit_comme_hors_export(self):
        """Un lien vers un ticket marqué se lit comme un lien vers un ticket hors export : l'équipe cible est « (sans équipe) »
        (comme une cible absente de la base), la cellule d'un seul lien est masquée."""
        c = self.conn()
        self.liens(c)
        self.marquer(c, "PROJ-B1")
        c.commit()
        self.assertEqual(self.lues(c), {("Alpha", "Beta", "Blocks"): 5, ("Alpha", "(sans équipe)", "Blocks"): None})

    def test_dependances_lien_vers_une_cible_inconnue_se_lit_comme_une_cible_marquee(self):
        c = self.conn()
        self.liens(c)
        c.execute("SET ROLE pmzilla_flow")
        c.execute("UPDATE flow.links SET target_key = 'ABC-9' WHERE target_key = 'PROJ-B1'")      # cible hors de la base
        c.execute("RESET ROLE")
        c.commit()
        inconnue = self.lues(c)
        c.execute("SET ROLE pmzilla_flow")
        c.execute("UPDATE flow.links SET target_key = 'PROJ-B1' WHERE target_key = 'ABC-9'")
        c.execute("RESET ROLE")
        self.marquer(c, "PROJ-B1")
        c.commit()
        self.assertEqual(self.lues(c), inconnue)


class SansBase(unittest.TestCase):
    """Sans base : lecture du fichier de migration (toujours exécutés)."""

    def texte(self):
        return (db.DOSSIER_MIGRATIONS / "0008_flow_gdpr.sql").read_text(encoding="utf-8")

    def test_migration_0008_presente_apres_0007(self):
        noms = [m.nom for m in db.lister_migrations()]
        self.assertIn("0008_flow_gdpr.sql", noms)
        self.assertEqual(noms.index("0008_flow_gdpr.sql"), noms.index("0007_knowledge_watch_triage.sql") + 1)
        self.assertRegex(self.texte().splitlines()[0], r"^-- Schéma touché : flow")

    def test_aucune_donnee_ni_mot_de_passe_ni_role_cree(self):
        texte = self.texte()
        self.assertNotRegex(texte, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s+FROM|COPY\s)")
        self.assertNotRegex(texte, r"(?i)password")
        self.assertNotRegex(texte, r"(?i)CREATE\s+ROLE")

    def test_objets_crees_sous_le_proprietaire(self):
        texte = self.texte()
        self.assertRegex(texte, r"(?m)^SET LOCAL ROLE pmzilla_owner;")
        self.assertLess(texte.index("SET LOCAL ROLE pmzilla_owner"), texte.index("ALTER TABLE flow.issues"))
        self.assertIn("out_of_export_at timestamptz;", texte)                    # nullable, sans NOT NULL ni valeur par défaut
        self.assertNotRegex(texte, r"out_of_export_at\s+timestamptz\s+(NOT|DEFAULT)")

    def test_tables_de_periodes_en_cascade_sans_colonne_personnelle(self):
        texte = self.texte()
        for table in ("issue_label_periods", "issue_version_periods"):
            bloc = re.search(rf"CREATE TABLE flow\.{table} \((.*?)\n\);", texte, re.S)
            self.assertIsNotNone(bloc, table)
            self.assertIn("REFERENCES flow.issues (key) ON DELETE CASCADE", bloc.group(1))
            colonnes = {m.group(1) for m in re.finditer(r"(?m)^\s{4}([a-z_]+)\s+(?:text|timestamptz)\b", bloc.group(1))}
            self.assertEqual(colonnes, {"issue_key", "label" if "label" in table else "version", "added_at", "removed_at"})
        self.assertNotRegex(texte, r"(?i)\b(po|owner_name|person|assignee|reporter|creator|author|email|account)\b\s+text")

    def test_les_quatre_vues_sont_recreees_et_ecartent_les_marques(self):
        texte = self.texte()
        for vue in ("v_team_status", "v_team_weekly_resolved", "v_team_open_age", "v_team_dependencies"):
            bloc = re.search(rf"CREATE OR REPLACE VIEW flow\.{vue} AS(.*?);\n", texte, re.S)
            self.assertIsNotNone(bloc, vue)
            self.assertIn("out_of_export_at IS NULL", bloc.group(1), vue)
        # la vue des dépendances écarte la source ET ignore la cible marquée (jointure externe : lien vers un ticket hors export)
        deps = re.search(r"CREATE OR REPLACE VIEW flow\.v_team_dependencies AS(.*?);\n", texte, re.S).group(1)
        self.assertRegex(deps, r"JOIN flow\.issues s ON s\.key = l\.source_key AND s\.out_of_export_at IS NULL")
        self.assertRegex(deps, r"LEFT JOIN flow\.issues d ON d\.key = l\.target_key AND d\.out_of_export_at IS NULL")
        self.assertNotRegex(texte, r"(?i)DROP\s+VIEW")                           # les droits du rôle des vues sont conservés

    def test_le_role_des_vues_n_obtient_aucun_droit_sur_les_tables(self):
        texte = self.texte()
        for grant in re.findall(r"(?is)GRANT\b.*?;", texte):
            if "pmzilla_flow_views" in grant:
                self.fail(f"la migration 0008 ne doit rien accorder au rôle des vues : {grant}")
        self.assertRegex(texte, r"GRANT SELECT, INSERT, UPDATE, DELETE ON flow\.issue_label_periods, flow\.issue_version_periods TO pmzilla_flow;")
        self.assertRegex(texte, r"GRANT SELECT ON flow\.issue_label_periods, flow\.issue_version_periods TO pmzilla_flow_ro;")


if __name__ == "__main__":
    unittest.main()
