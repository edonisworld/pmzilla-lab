"""Tables et vue des champs de livraison (change jira-delivery-fields, design D3, D9, D10 ; spec jira-flow-delivery-fields, jira-flow-views,
jira-flow-raw-layer, jira-flow-retention).

    bash tests/run_all.sh db                 (partie sans base : lecture des deux migrations)
    bash tools/dbtest.sh db                  (partie avec base : à lancer par l'auteur ; base jetable, données inventées)

Les migrations se retrouvent par leur suffixe, jamais par leur numéro dans le code des tests ; leurs noms complets, 0032_flow_delivery_fields.sql,
0033_flow_delivery_fields_view.sql et 0034_flow_delivery_option_ids.sql (R-20261102-50, -51), ne sont écrits qu'ici, pour que le sélecteur de
suites (tools/select_suites.py) les rattache à cette suite.
"""
import re
import unittest

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402

SUFFIXE_TABLES = "_flow_delivery_fields.sql"
SUFFIXE_VUE = "_flow_delivery_fields_view.sql"
VUE = "flow.v_team_delivery_fields_coverage"
TABLES = ("issue_delivery_fields", "sprints", "issue_current_sprints", "issue_current_asset_versions", "issue_delivery_options",
          "issue_defect_fields", "issue_sprint_periods", "issue_asset_version_periods", "release_versions", "raw_version_snapshots")
DU_TICKET = ("issue_delivery_fields", "issue_current_sprints", "issue_current_asset_versions", "issue_delivery_options",
             "issue_defect_fields", "issue_sprint_periods", "issue_asset_version_periods")
ROLES_SANS_DROIT = ("pmzilla_flow_views", "pmzilla_quality_views", "pmzilla_flow_ro")


def code_de(suffixe):
    candidats = [m for m in db.lister_migrations() if m.nom.endswith(suffixe)]
    assert len(candidats) == 1, f"une migration *{suffixe} est attendue"
    return candidats[0].chemin.read_text(encoding="utf-8")


def sans_commentaires(texte):
    return re.sub(r"--[^\n]*", "", texte)


class SansBase(unittest.TestCase):
    def test_les_tables_sont_creees_sous_le_proprietaire_sans_donnee_ni_role(self):
        code = sans_commentaires(code_de(SUFFIXE_TABLES))
        self.assertEqual(sorted(re.findall(r"(?i)\bCREATE\s+TABLE\s+flow\.(\w+)", code)), sorted(TABLES))
        self.assertRegex(code, r"(?i)ALTER\s+TABLE\s+flow\.raw_issue_snapshots\s+ADD\s+COLUMN\s+delivery\s+jsonb")
        self.assertLess(re.search(r"(?i)SET\s+LOCAL\s+ROLE\s+pmzilla_owner", code).start(), re.search(r"(?i)CREATE\s+TABLE", code).start())
        self.assertNotRegex(code, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(code, r"(?i)\bPASSWORD\b|\b(CREATE|ALTER|DROP)\s+ROLE\b|\bLOGIN\b")

    def test_aucun_droit_aux_roles_des_vues_ni_a_la_lecture_seule(self):
        code = sans_commentaires(code_de(SUFFIXE_TABLES))
        self.assertNotRegex(code, r"(?is)GRANT\s+[^;]*\bTO\s+[^;]*pmzilla_flow_views")
        self.assertNotRegex(code, r"(?is)GRANT\s+[^;]*\bTO\s+[^;]*pmzilla_flow_ro")
        revokes = " ".join(re.findall(r"(?is)\bREVOKE\b.*?;", code))
        for role in ("PUBLIC", "pmzilla_flow_ro", "pmzilla_flow_views", "pmzilla_quality_views"):
            self.assertIn(role, revokes)

    def test_la_table_brute_des_versions_est_en_ajout_seulement(self):
        code = sans_commentaires(code_de(SUFFIXE_TABLES))
        self.assertRegex(code, r"(?is)GRANT\s+SELECT,\s*INSERT,\s*DELETE\s+ON\s+flow\.raw_version_snapshots\s+TO\s+pmzilla_flow\s*;")
        self.assertNotRegex(code, r"(?is)GRANT[^;]*\bUPDATE\b[^;]*raw_version_snapshots")

    def test_les_tables_d_un_ticket_partent_avec_lui(self):
        code = sans_commentaires(code_de(SUFFIXE_TABLES))
        for table in DU_TICKET:
            bloc = re.search(rf"(?is)CREATE\s+TABLE\s+flow\.{table}\s*\((.*?)\n\);", code).group(1)
            self.assertRegex(bloc, r"(?i)REFERENCES\s+flow\.issues\s*\(key\)\s+ON\s+DELETE\s+CASCADE", table)

    def test_numero_oppose_a_la_vue_la_vue_suit_les_tables(self):
        numeros = {m.nom.split("_", 1)[1]: m.numero for m in db.lister_migrations()}
        self.assertEqual(numeros[SUFFIXE_VUE.lstrip("_")], numeros[SUFFIXE_TABLES.lstrip("_")] + 1)

    def test_aucun_nom_ni_cle_de_ticket_de_version_dans_les_colonnes(self):
        code = sans_commentaires(code_de(SUFFIXE_TABLES)).lower()
        for interdit in ("sprint_name", "goal", "board", "customer_name", "summary", "version_key", "ticket_key", "assignee", "reporter"):
            self.assertNotIn(interdit, code)


class AvecBase(unittest.TestCase):
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def ticket(self, c, cle, equipe=None, type_="Story", resolu=False):
        c.execute("SET ROLE pmzilla_flow")
        if equipe:
            c.execute("INSERT INTO flow.teams (name) VALUES (%s) ON CONFLICT DO NOTHING", (equipe,))
        resolu_sql = ("(date_trunc('quarter', now() AT TIME ZONE 'UTC') - interval '3 months' + interval '10 days')" if resolu else "NULL")
        c.execute(f"INSERT INTO flow.issues (key, project, type, status, status_category, created_at, resolved_at, updated_at, team_id) "
                  f"VALUES (%s, 'PROJ', %s, 'Closed', 'Done', now() - interval '400 days', {resolu_sql}, now(), "
                  f"(SELECT id FROM flow.teams WHERE name = %s))", (cle, type_, equipe))
        c.execute("RESET ROLE")

    def test_les_roles_des_vues_et_de_lecture_seule_ne_lisent_aucune_table(self):
        c = self.conn()
        for table in TABLES:
            for role in ROLES_SANS_DROIT:
                self.assertFalse(self.essaie(c, role, f"SELECT * FROM flow.{table}"), f"{role} {table}")
            self.assertTrue(self.essaie(c, "pmzilla_flow", f"SELECT * FROM flow.{table}"), table)

    def test_les_tables_d_un_ticket_partent_en_cascade(self):
        c = self.conn()
        self.ticket(c, "PROJ-1")
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.sprints (sprint_id, state) VALUES ('31', 'closed')")
        c.execute("INSERT INTO flow.issue_delivery_fields (issue_key, isp_id) VALUES ('PROJ-1', '5')")          # R-20261102-51 : identifiant d'option, colonne isp_id
        c.execute("INSERT INTO flow.issue_current_sprints VALUES ('PROJ-1', '31')")
        c.execute("INSERT INTO flow.issue_current_asset_versions VALUES ('PROJ-1', 'target', '101'), ('PROJ-1', 'detected', '201')")
        c.execute("INSERT INTO flow.issue_delivery_options VALUES ('PROJ-1', 'workflow_option', 1, '7')")          # R-20261102-51 : plus de colonne value
        c.execute("INSERT INTO flow.issue_defect_fields (issue_key, detection_phase) VALUES ('PROJ-1', 'production')")          # R-20261102-35 : code fermé
        c.execute("INSERT INTO flow.issue_sprint_periods VALUES ('PROJ-1', '31', now(), NULL)")
        c.execute("INSERT INTO flow.issue_asset_version_periods VALUES ('PROJ-1', 'target', '101', now(), NULL)")
        c.execute("DELETE FROM flow.issues WHERE key = 'PROJ-1'")
        for table in DU_TICKET:
            self.assertEqual(c.execute(f"SELECT count(*) FROM flow.{table}").fetchone()[0], 0, table)
        self.assertEqual(c.execute("SELECT count(*) FROM flow.sprints").fetchone()[0], 1)          # la ligne de sprint part avec la purge, non en cascade
        c.execute("RESET ROLE")

    def test_phase_de_detection_en_code_ferme_seulement(self):
        # R-20261102-35 / R-20261102-51 : la contrainte issue_defect_fields_phase_code refuse toute valeur hors production, piloting, other.
        c = self.conn()
        self.ticket(c, "PROJ-1")
        c.execute("SET ROLE pmzilla_flow")
        for code in ("production", "piloting", "other"):
            c.execute("DELETE FROM flow.issue_defect_fields")
            c.execute("INSERT INTO flow.issue_defect_fields (issue_key, detection_phase) VALUES ('PROJ-1', %s)", (code,))
        c.execute("DELETE FROM flow.issue_defect_fields")
        for libre in ("Production", "ZzPhaseLibre"):
            with self.assertRaises(db.psycopg.errors.CheckViolation):
                with c.transaction():
                    c.execute("INSERT INTO flow.issue_defect_fields (issue_key, detection_phase) VALUES ('PROJ-1', %s)", (libre,))
        c.execute("RESET ROLE")

    def test_aucune_colonne_de_valeur_d_option_dans_les_tables(self):
        # R-20261102-51 : les colonnes de valeur supprimées par la migration de correction n'existent plus.
        c = self.conn()
        colonnes = {(t, n) for t, n in c.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'flow' "
                                                 "AND table_name IN ('issue_delivery_options', 'issue_defect_fields', 'issue_delivery_fields')")}
        for interdite in (("issue_delivery_options", "value"), ("issue_defect_fields", "detected_by"), ("issue_defect_fields", "installed_base"),
                          ("issue_delivery_fields", "isp"), ("issue_delivery_fields", "release_target")):
            self.assertNotIn(interdite, colonnes)

    def test_numero_opaque_attribue_par_la_base_a_la_premiere_vue(self):
        c = self.conn()
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.release_versions (object_id, short_name) VALUES ('101', 'a'), ('102', 'b')")
        numeros = [r[0] for r in c.execute("SELECT number FROM flow.release_versions ORDER BY object_id")]
        self.assertEqual(len(set(numeros)), 2)
        # Point de sauvegarde : l'erreur attendue n'interrompt que lui ; la transaction reste utilisable pour RESET ROLE.
        with self.assertRaises(db.psycopg.errors.GeneratedAlways):
            with c.transaction():
                c.execute("INSERT INTO flow.release_versions (object_id, number) VALUES ('103', 99)")
        c.execute("RESET ROLE")

    def test_un_ticket_qui_perd_tous_ses_champs_perd_ses_lignes_a_l_import(self):
        import datetime as dt
        import flow_raw
        T = dt.datetime(2026, 9, 1, 10, tzinfo=dt.timezone.utc)

        def instantane(delivery, maj):
            i = {"issue_key": "PROJ-1", "project": "PROJ", "type": "Story", "status": "Open", "status_category": "To Do",
                 "created_at": T, "resolved_at": None, "resolution": None, "status_category_changed_at": None, "story_points": None,
                 "updated_at": maj, "parent_key": None, "teams": [], "links": [], "delivery": delivery}
            i["content_hash"] = flow_raw.empreinte(i)
            return i

        c = self.conn()
        c.execute("SET ROLE pmzilla_flow")
        livraison = {"sprints": [{"id": "31", "state": "closed", "start": None, "end": None, "complete": None}],
                     "assets": {"target": ["101"]}}
        magasin = flow_raw.MagasinBase(c)
        magasin.enregistrer(genre="export", nb_requetes=1, toutes=True, vus=["PROJ-1"],
                            instantanes={"PROJ-1": instantane(livraison, T + dt.timedelta(days=1))})
        flow_raw.deriver(c, maintenant=T + dt.timedelta(days=2))
        self.assertEqual(c.execute("SELECT count(*) FROM flow.issue_current_sprints").fetchone()[0], 1)
        magasin.enregistrer(genre="export", nb_requetes=1, toutes=True, vus=["PROJ-1"],
                            instantanes={"PROJ-1": instantane(None, T + dt.timedelta(days=3))})
        flow_raw.deriver(c, maintenant=T + dt.timedelta(days=4))
        self.assertEqual(c.execute("SELECT count(*) FROM flow.issue_current_sprints").fetchone()[0], 0)
        self.assertEqual(c.execute("SELECT count(*) FROM flow.issue_current_asset_versions").fetchone()[0], 0)
        c.execute("RESET ROLE")

    def test_la_table_brute_des_versions_est_en_ajout_seulement(self):
        c = self.conn()
        self.assertTrue(self.essaie(c, "pmzilla_flow", "SELECT * FROM flow.raw_version_snapshots"))
        self.assertFalse(self.essaie(c, "pmzilla_flow", "UPDATE flow.raw_version_snapshots SET content_hash = 'x'"))
        c.execute("SET ROLE pmzilla_flow")
        run = c.execute("INSERT INTO flow.raw_runs (kind) VALUES ('export') RETURNING id").fetchone()[0]
        c.execute("INSERT INTO flow.raw_version_snapshots (run_id, object_id, content, content_hash) VALUES (%s, '101', '{}', 'h')", (run,))
        c.execute("DELETE FROM flow.raw_version_snapshots")
        c.execute("RESET ROLE")

    def test_colonne_delivery_des_instantanes_nulle_par_defaut(self):
        c = self.conn()
        colonne = c.execute("SELECT data_type, is_nullable FROM information_schema.columns WHERE table_schema = 'flow' "
                            "AND table_name = 'raw_issue_snapshots' AND column_name = 'delivery'").fetchone()
        self.assertEqual(colonne, ("jsonb", "YES"))

    # --- vue de couverture -------------------------------------------------------------------------------------------

    def lire(self, c):
        c.commit()
        c.execute("SET ROLE pmzilla_flow_views")
        lignes = c.execute(f"SELECT team, item_kind, items, with_sprint, with_target_version FROM {VUE} ORDER BY team, item_kind").fetchall()
        c.execute("RESET ROLE")
        return lignes

    def remplir(self, c, equipe, n, avec_sprint, avec_cible=0, type_="Story", debut=0):
        for i in range(debut, debut + n):
            cle = f"{equipe[:2].upper()}-{type_[:1]}{i}"
            self.ticket(c, cle, equipe, type_, resolu=True)
            c.execute("SET ROLE pmzilla_flow")
            if i - debut < avec_sprint:
                c.execute("INSERT INTO flow.sprints (sprint_id) VALUES ('9') ON CONFLICT DO NOTHING")
                c.execute("INSERT INTO flow.issue_current_sprints VALUES (%s, '9')", (cle,))
            if i - debut < avec_cible:
                c.execute("INSERT INTO flow.issue_current_asset_versions VALUES (%s, 'target', '101')", (cle,))
            c.execute("RESET ROLE")

    def test_une_equipe_un_trimestre_douze_stories_sept_avec_sprint(self):
        c = self.conn()
        self.remplir(c, "Alpha", 12, 7)
        self.assertEqual(self.lire(c), [("Alpha", "story", 12, 7, None)])

    def test_epics_comptees_sur_une_ligne_a_part(self):
        c = self.conn()
        self.remplir(c, "Alpha", 6, 0)
        self.remplir(c, "Alpha", 8, 0, type_="Epic")
        self.assertEqual([(l[1], l[2]) for l in self.lire(c)], [("epic", 8), ("story", 6)])

    def test_peu_de_remplis_masque_le_compte(self):
        c = self.conn()
        self.remplir(c, "Alpha", 12, 3)
        self.assertEqual(self.lire(c), [("Alpha", "story", 12, None, None)])

    def test_peu_de_non_remplis_masque_le_compte(self):
        c = self.conn()
        self.remplir(c, "Alpha", 20, 0, avec_cible=18)
        self.assertEqual(self.lire(c), [("Alpha", "story", 20, None, None)])

    def test_moins_de_cinq_items_masque_les_items(self):
        c = self.conn()
        self.remplir(c, "Alpha", 4, 4)
        self.assertEqual(self.lire(c), [("Alpha", "story", None, None, None)])

    def test_ticket_sorti_de_l_export_et_trimestre_en_cours_ecartes(self):
        c = self.conn()
        self.remplir(c, "Alpha", 6, 0)
        c.execute("SET ROLE pmzilla_flow")
        c.execute("UPDATE flow.issues SET out_of_export_at = now() WHERE key = 'AL-S0'")
        c.execute("RESET ROLE")
        self.assertEqual(self.lire(c), [("Alpha", "story", 5, None, None)])          # cinq items restent : à peine visibles


if __name__ == "__main__":
    unittest.main()
