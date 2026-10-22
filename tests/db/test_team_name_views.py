"""Vues des noms d'équipe flow.v_teams et flow.v_team_jira_ids (change team-names-readable, tâche 2.1, conception D2 et D3).

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Les tests sans base (SansBase) tournent toujours : lecture du fichier de migration. Les autres utilisent la base jetable de
test_flow_schema.py et sont sautés sans elle (bash tools/dbtest.sh db). La migration est retrouvée par sa description
(flow_team_name_views), pas par son numéro. Données inventées : équipes Alpha, Beta, Gamma, Delta, Epsilon.
"""
import re
import unittest

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402

V_TEAMS = "flow.v_teams"
V_IDS = "flow.v_team_jira_ids"
COLONNES_TEAMS = ["team", "team_type", "tickets"]
COLONNES_IDS = ["team", "jira_team_id", "tickets"]
MOTS_INTERDITS = ("key", "title", "summary", "description", "person", "assignee", "reporter", "author", "label", "project", "status")
AUTRES_ROLES = ("pmzilla_flow_ro", "pmzilla_flow", "pmzilla_quality_views", "pmzilla_cases", "pmzilla_knowledge_ro")


NOM_MIGRATION = "0014_flow_team_name_views.sql"   # nommée en entier : le sélecteur de suites rattache la migration à tests/db


def fichier_migration():
    candidats = [m for m in db.lister_migrations() if m.nom == NOM_MIGRATION]
    return candidats[0] if len(candidats) == 1 else None


class SansBase(unittest.TestCase):
    def texte(self):
        migration = fichier_migration()
        self.assertIsNotNone(migration, "une migration *_flow_team_name_views.sql est attendue")
        return migration.chemin.read_text(encoding="utf-8")

    def code(self):
        return re.sub(r"--[^\n]*", "", self.texte())

    def test_deux_vues_sous_le_proprietaire_sans_donnee_ni_mot_de_passe_ni_role(self):
        texte = self.texte()
        self.assertRegex(texte.splitlines()[0], r"^-- Schéma touché : flow")
        code = self.code()
        self.assertEqual(len(re.findall(r"(?i)\bCREATE\s+(?:OR\s+REPLACE\s+)?VIEW\b", code)), 2)
        self.assertRegex(code, r"(?is)SET\s+LOCAL\s+ROLE\s+pmzilla_owner\s*;.*CREATE\s+VIEW\s+flow\.v_teams\s+AS.*"
                               r"CREATE\s+VIEW\s+flow\.v_team_jira_ids\s+AS")
        self.assertNotRegex(code, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(code, r"(?i)\bPASSWORD\b")
        self.assertNotRegex(code, r"(?i)\b(CREATE|ALTER|DROP)\s+(ROLE|TABLE|FUNCTION)\b")
        self.assertNotRegex(code, r"(?i)\bLOGIN\b")

    def test_select_au_seul_role_des_vues_et_les_autres_droits_retires(self):
        code = self.code()
        grants = re.findall(r"(?is)\bGRANT\b.*?;", code)
        self.assertEqual(len(grants), 2, grants)
        for vue, grant in zip(("flow.v_teams", "flow.v_team_jira_ids"), grants):
            self.assertRegex(grant, rf"(?is)GRANT\s+SELECT\s+ON\s+{re.escape(vue)}\s+TO\s+pmzilla_flow_views\s*;")
        revokes = re.findall(r"(?is)\bREVOKE\b.*?;", code)
        self.assertEqual(len(revokes), 2, revokes)
        for revoke in revokes:
            for role in ("PUBLIC", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_quality_views"):
                self.assertRegex(revoke, rf"\b{role}\b")
            self.assertNotRegex(revoke, r"pmzilla_flow_views")
        self.assertLess(code.index("REVOKE"), code.index("GRANT"))
        self.assertNotRegex(code, r"(?i)\bGRANT\b[^;]*\bTO\b[^;]*pmzilla_flow_ro")

    def test_colonnes_et_masquage_dans_le_texte_de_la_migration(self):
        code = self.code()
        teams = re.search(r"(?is)CREATE\s+VIEW\s+flow\.v_teams\s+AS(.*?);", code).group(1)
        ids = re.search(r"(?is)CREATE\s+VIEW\s+flow\.v_team_jira_ids\s+AS(.*?);", code).group(1)
        self.assertEqual(re.findall(r"(?i)\bAS\s+([a-z_]+)", teams), ["team", "tickets"])      # team_type : colonne nue
        self.assertRegex(teams, r"(?i)\bteam_type\b")
        self.assertEqual(re.findall(r"(?i)\bAS\s+(team|jira_team_id|tickets)\b", ids), ["team", "jira_team_id", "tickets"])
        for vue in (teams, ids):
            self.assertRegex(vue, r"(?i)flow\.mask_count\(")
            self.assertRegex(vue, r"(?i)out_of_export_at\s+IS\s+NULL")
        self.assertRegex(ids, r"(?i)DISTINCT\s+ON\s*\(\s*\w*\.?issue_key\s*\)")
        self.assertRegex(ids, r"(?i)ORDER\s+BY\s+\w*\.?issue_key\s*,\s*\w*\.?run_id\s+DESC")

    def test_point_c_les_vues_ne_lisent_ni_l_historique_ni_le_type_dans_les_ids_ni_la_couche_brute_dans_v_teams(self):
        code = self.code()
        teams = re.search(r"(?is)CREATE\s+VIEW\s+flow\.v_teams\s+AS(.*?);", code).group(1)
        ids = re.search(r"(?is)CREATE\s+VIEW\s+flow\.v_team_jira_ids\s+AS(.*?);", code).group(1)
        for vue in (teams, ids):
            self.assertNotRegex(vue, r"(?i)\bhistory_not_found\b")
            self.assertNotRegex(vue, r"(?i)\bhistory_gone_at\b")
        self.assertNotRegex(ids, r"(?i)\bteam_type\b")
        self.assertNotRegex(teams, r"(?i)\braw_\w+")

    def test_la_migration_suit_celle_des_equipes_vues_et_le_numero_est_libre(self):
        numeros = {m.nom.split("_", 1)[1]: m.numero for m in db.lister_migrations()}
        self.assertGreater(numeros["flow_team_name_views.sql"], numeros["flow_team_tickets_seen.sql"])
        liste = sorted(numeros.values())
        self.assertEqual(liste, list(range(1, len(liste) + 1)))                                         # sans trou ni doublon


class AvecBase(unittest.TestCase):
    """Même base jetable que SchemaFlow (migrations appliquées, base supprimée à la fin)."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def jeu(self, c):
        """Alpha (Development Team) : 10 tickets dans l'export et 1 sorti de l'export ; Beta (sans type) : 2 tickets ; Gamma
        (Other Team) : aucun ticket ; Delta et Epsilon : un type chacun, sans ticket.
        Instantanés : chaque ticket d'Alpha a un ancien instantané (identifiant 11) puis le dernier (identifiant 12) ; le ticket
        sorti de l'export porte aussi 12 ; ceux de Beta portent 21 ; un ticket porte en plus Gamma sans identifiant."""
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.teams (name, team_type) VALUES ('Alpha', 'Development Team'), ('Beta', NULL), "
                  "('Gamma', 'Other Team'), ('Delta', 'Verification Team'), ('Epsilon', 'Product Management Team')")
        cles_alpha = [f"PROJ-{i}" for i in range(10)]
        cles = cles_alpha + ["PROJ-10", "PROJ-11", "PROJ-12"]
        for cle in cles:
            sortie = "now()" if cle == "PROJ-10" else "NULL"
            c.execute("INSERT INTO flow.issues (key, project, type, status, created_at, updated_at, team_id, out_of_export_at) "
                      f"VALUES (%s, 'PROJ', 'Story', 'Open', now(), now(), 1, {sortie})", (cle,))
        c.execute("INSERT INTO flow.issue_teams (issue_key, team_id, position) VALUES "
                  + ", ".join(f"('{k}', 1, 1)" for k in cles_alpha + ["PROJ-10"])
                  + ", ('PROJ-11', 2, 1), ('PROJ-12', 2, 1)")
        ancien = c.execute("INSERT INTO flow.raw_runs (kind, queries_searched, all_queries) VALUES ('export', 2, true) RETURNING id").fetchone()[0]
        dernier = c.execute("INSERT INTO flow.raw_runs (kind, queries_searched, all_queries) VALUES ('export', 2, true) RETURNING id").fetchone()[0]

        def instantane(cle, passage, equipes):
            c.execute("INSERT INTO flow.raw_issue_snapshots (issue_key, run_id, updated_at, project, type, status, created_at, content_hash, teams) "
                      "VALUES (%s, %s, now(), 'PROJ', 'Story', 'Open', now(), 'h', %s::jsonb)", (cle, passage, equipes))

        for cle in cles_alpha + ["PROJ-10"]:
            instantane(cle, ancien, '[{"name": "Alpha", "jira_team_id": "11"}]')
            instantane(cle, dernier, '[{"name": "Alpha", "jira_team_id": "12"}, {"name": "Gamma", "jira_team_id": null}]'
                       if cle == "PROJ-0" else '[{"name": "Alpha", "jira_team_id": "12"}]')
        for cle in ("PROJ-11", "PROJ-12"):
            instantane(cle, dernier, '[{"name": "Beta", "jira_team_id": "21"}]')
        c.execute("RESET ROLE")
        c.commit()

    def lire(self, c, role, requete):
        c.execute(f"SET ROLE {role}")
        try:
            return c.execute(requete).fetchall()
        finally:
            c.execute("RESET ROLE")

    def colonnes(self, c, vue):
        return [r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'flow' "
                                        "AND table_name = %s ORDER BY ordinal_position", (vue,))]

    def test_les_colonnes_sont_exactement_celles_de_la_conception(self):
        c = self.conn()
        self.assertEqual(self.colonnes(c, "v_teams"), COLONNES_TEAMS)
        self.assertEqual(self.colonnes(c, "v_team_jira_ids"), COLONNES_IDS)

    def test_aucun_nom_de_colonne_ne_porte_un_mot_interdit(self):
        c = self.conn()
        for vue in ("v_teams", "v_team_jira_ids"):
            for colonne in self.colonnes(c, vue):
                for mot in MOTS_INTERDITS:
                    self.assertNotIn(mot, colonne.lower(), f"{vue}.{colonne}")

    def test_le_type_est_celui_qui_est_stocke_nul_sans_type_une_ligne_par_equipe(self):
        c = self.conn()
        self.jeu(c)
        lignes = {r[0]: r[1] for r in self.lire(c, "pmzilla_flow_views", f"SELECT team, team_type, tickets FROM {V_TEAMS}")}
        self.assertEqual(lignes, {"Alpha": "Development Team", "Beta": None, "Gamma": "Other Team", "Delta": "Verification Team",
                                  "Epsilon": "Product Management Team"})          # cinq équipes, quatre types et un type nul, aucun regroupement
        total = self.lire(c, "pmzilla_flow_views", f"SELECT count(*) FROM {V_TEAMS}")[0][0]
        self.assertEqual(total, c.execute("SELECT count(*) FROM flow.teams").fetchone()[0])

    def test_masquage_sous_cinq_zero_compris_et_sortis_de_l_export_ecartes(self):
        c = self.conn()
        self.jeu(c)
        comptes = {r[0]: r[1] for r in self.lire(c, "pmzilla_flow_views", f"SELECT team, tickets FROM {V_TEAMS}")}
        self.assertEqual(comptes["Alpha"], 10)               # dix dans l'export ; le onzième, sorti de l'export, n'est pas compté
        self.assertIsNone(comptes["Beta"])                   # deux : masqués
        self.assertIsNone(comptes["Gamma"])                  # zéro : masqué aussi, jamais un zéro montré
        self.assertIsNone(comptes["Delta"])

    def test_seul_le_dernier_instantane_compte_les_ticket_sortis_et_les_identifiants_nuls_sont_ecartes(self):
        c = self.conn()
        self.jeu(c)
        lignes = {(r[0], r[1]): r[2] for r in self.lire(c, "pmzilla_flow_views", f"SELECT team, jira_team_id, tickets FROM {V_IDS}")}
        self.assertEqual(lignes, {("Alpha", "12"): 10, ("Beta", "21"): None})       # l'identifiant 11 est ancien ; Gamma sans identifiant : aucune ligne
        self.assertNotIn(("Alpha", "11"), lignes)
        self.assertFalse([k for k in lignes if k[0] == "Gamma"])
        self.assertTrue(all(k[1] is not None for k in lignes))

    def test_l_identifiant_n_est_jamais_masque_meme_sous_le_seuil(self):
        c = self.conn()
        self.jeu(c)
        lignes = self.lire(c, "pmzilla_flow_views", f"SELECT jira_team_id, tickets FROM {V_IDS} WHERE team = 'Beta'")
        self.assertEqual(lignes, [("21", None)])

    def test_le_role_des_vues_lit_les_deux_vues_les_autres_roles_sont_refuses(self):
        c = self.conn()
        self.jeu(c)
        for vue in (V_TEAMS, V_IDS):
            self.assertTrue(self.essaie(c, "pmzilla_flow_views", f"SELECT * FROM {vue}"), vue)
            for role in AUTRES_ROLES:
                self.assertFalse(self.essaie(c, role, f"SELECT * FROM {vue}"), f"{role} {vue}")

    def test_le_role_des_vues_reste_refuse_sur_la_table_des_equipes_et_sur_la_couche_brute(self):
        c = self.conn()
        self.jeu(c)
        for sql in ("SELECT * FROM flow.teams", "SELECT team_type FROM flow.teams", "SELECT name FROM flow.teams",
                    "SELECT * FROM flow.raw_issue_snapshots", "SELECT teams FROM flow.raw_issue_snapshots", "SELECT * FROM flow.issue_teams"):
            self.assertFalse(self.essaie(c, "pmzilla_flow_views", sql), sql)

    def test_aucun_role_n_ecrit_les_vues(self):
        c = self.conn()
        self.jeu(c)
        for vue in ("v_teams", "v_team_jira_ids"):
            for role in ("pmzilla_flow_views", "pmzilla_flow_ro", "pmzilla_flow", "pmzilla_quality_views"):
                for droit in ("INSERT", "UPDATE", "DELETE"):
                    self.assertFalse(c.execute("SELECT has_table_privilege(%s, %s, %s)", (role, f"flow.{vue}", droit)).fetchone()[0],
                                     (role, vue, droit))


if __name__ == "__main__":
    unittest.main()
