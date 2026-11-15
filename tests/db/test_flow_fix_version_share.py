"""Versions courantes et vue de la part des items terminés avec une fix version (change flow-version-share, tâches 2.2 et 3.1 ; spec
jira-flow-raw-layer « Snapshot versions column », jira-flow-views « Fix version share view » et « Fix version share masking »).

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Les tests sans base (SansBase) tournent toujours : lecture des fichiers de migration, retrouvés par leur description et non par leur
numéro. Les autres utilisent la base jetable de test_flow_schema.py et sont sautés sans elle (bash tools/dbtest.sh db). Données inventées.
"""
import re
import unittest

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402

VUE = "flow.v_team_fix_version_share"
SECRET = "VersionSecreteEpsilon"


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
    def test_colonne_des_versions_courantes(self):
        texte = code_de("_flow_current_versions.sql")
        code = sans_commentaires(texte)
        self.assertRegex(texte.splitlines()[0], r"^-- Schéma touché : flow")
        self.assertRegex(code, r"(?is)SET\s+LOCAL\s+ROLE\s+pmzilla_owner\s*;")
        self.assertRegex(code, r"(?is)ALTER\s+TABLE\s+flow\.raw_issue_snapshots\s+ADD\s+COLUMN\s+current_versions\s+jsonb")
        self.assertNotRegex(code, r"(?is)current_versions\s+jsonb\s+NOT\s+NULL")           # nulle : un instantané ancien ne suit pas les versions
        self.assertNotRegex(code, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(code, r"(?i)\bPASSWORD\b|\b(CREATE|ALTER|DROP)\s+ROLE\b|\bLOGIN\b")

    def test_table_liee_au_ticket_avec_cascade_sans_droit_pour_le_role_des_vues(self):
        code = sans_commentaires(code_de("_flow_current_versions.sql"))
        table = re.search(r"(?is)CREATE\s+TABLE\s+flow\.issue_current_versions\s*\((.*?)\)\s*;", code)
        self.assertIsNotNone(table)
        self.assertRegex(table.group(1), r"(?is)issue_key\s+text\s+NOT\s+NULL\s+REFERENCES\s+flow\.issues\s*\(key\)\s+ON\s+DELETE\s+CASCADE")
        self.assertRegex(table.group(1), r"(?is)kind\s+text\s+NOT\s+NULL\s+CHECK\s*\(kind\s+IN\s*\('fix',\s*'affects'\)\)")
        self.assertRegex(table.group(1), r"(?is)PRIMARY\s+KEY\s*\(issue_key,\s*kind,\s*name\)")
        revoke = re.search(r"(?is)\bREVOKE\b.*?;", code)
        self.assertIsNotNone(revoke)
        for role in ("PUBLIC", "pmzilla_flow_views", "pmzilla_quality_views"):
            self.assertRegex(revoke.group(0), rf"\b{role}\b")
        self.assertNotRegex(code, r"(?i)GRANT\s+[^;]*pmzilla_flow_views")

    def test_la_vue_est_une_seule_vue_sous_le_proprietaire_sans_donnee(self):
        texte = code_de("_flow_fix_version_share.sql")
        code = sans_commentaires(texte)
        self.assertRegex(texte.splitlines()[0], r"^-- Schéma touché : flow")
        self.assertEqual(len(re.findall(r"(?i)\bCREATE\s+(?:OR\s+REPLACE\s+)?VIEW\b", code)), 1)
        self.assertRegex(code, r"(?is)SET\s+LOCAL\s+ROLE\s+pmzilla_owner\s*;.*CREATE\s+VIEW\s+flow\.v_team_fix_version_share\s+AS")
        self.assertNotRegex(code, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(code, r"(?i)\bPASSWORD\b|\b(CREATE|ALTER|DROP)\s+(ROLE|TABLE)\b|\bLOGIN\b")

    def test_select_au_seul_role_des_vues(self):
        code = sans_commentaires(code_de("_flow_fix_version_share.sql"))
        grants = re.findall(r"(?is)\bGRANT\b.*?;", code)
        self.assertEqual(len(grants), 1, grants)
        self.assertRegex(grants[0], r"(?is)GRANT\s+SELECT\s+ON\s+flow\.v_team_fix_version_share\s+TO\s+pmzilla_flow_views\s*;")
        revoke = re.search(r"(?is)\bREVOKE\b.*?;", code)
        self.assertIsNotNone(revoke)
        for role in ("PUBLIC", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_quality_views"):
            self.assertRegex(revoke.group(0), rf"\b{role}\b")
        self.assertLess(code.index("REVOKE"), code.index("GRANT"))

    def test_colonnes_de_la_vue_sans_cle_ni_nom_de_version(self):
        code = sans_commentaires(code_de("_flow_fix_version_share.sql"))
        vue = re.search(r"(?is)CREATE\s+VIEW\s+flow\.v_team_fix_version_share\s+AS(.*?);", code).group(1)
        self.assertNotRegex(vue, r"(?i)\bname\s+AS\b|v\.name|\bv\.kind\s+AS")                 # jamais le nom d'une version dans une colonne
        self.assertRegex(vue, r"(?i)out_of_export_at\s+IS\s+NULL")
        self.assertRegex(vue, r"(?i)generate_series\s*\(\s*1\s*,\s*4\s*\)")                    # quatre trimestres terminés, jamais le courant (k = 0)
        self.assertRegex(vue, r"(?i)issue_current_versions")
        self.assertRegex(vue, r"(?i)'fix'")
        self.assertRegex(vue, r"(?i)e\.n\s*-\s*4\s+END\s+AS\s+with_fix_version_min")              # la borne : items - 4, jamais le compte exact
        self.assertNotRegex(vue, r"(?i)\bf\b\s*-\s*\d+[^,]*AS\s+with_fix_version_min")

    def test_les_migrations_se_suivent_sans_trou(self):
        numeros = {m.nom.split("_", 1)[1]: m.numero for m in db.lister_migrations()}
        self.assertEqual(numeros["flow_fix_version_share.sql"], numeros["flow_current_versions.sql"] + 1)
        self.assertGreater(numeros["flow_current_versions.sql"], numeros["flow_team_name_views.sql"])
        liste = sorted(numeros.values())
        self.assertEqual(liste, list(range(1, len(liste) + 1)))


class AvecBase(unittest.TestCase):
    """Même base jetable que SchemaFlow (migrations appliquées, base supprimée à la fin)."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def debut_trimestre(self, c, decalage_mois=0):
        """Premier jour du trimestre courant, décalé de `decalage_mois` mois (UTC, comme la vue)."""
        return c.execute("SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') + make_interval(months => %s))::date",
                         (decalage_mois,)).fetchone()[0]

    def ticket(self, c, cle, equipe, decalage_mois=-3, avec_version=False, type_="Story", resolu=True, sorti=False, affects_seulement=False):
        """Un ticket de l'équipe (numéro de ligne) résolu au milieu du trimestre décalé, avec ou sans fix version."""
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, resolved_at, updated_at, team_id, "
                  "out_of_export_at) VALUES (%s, 'PROJ', %s, 'Closed', 'Done', now() - interval '2 years', "
                  "CASE WHEN %s THEN (date_trunc('quarter', now() AT TIME ZONE 'UTC') + make_interval(months => %s) "
                  "+ interval '40 days') AT TIME ZONE 'UTC' END, now(), %s, CASE WHEN %s THEN now() END)",
                  (cle, type_, resolu, decalage_mois, equipe, sorti))
        if avec_version:
            c.execute("INSERT INTO flow.issue_current_versions (issue_key, kind, name) VALUES (%s, 'fix', %s)", (cle, SECRET))
        if affects_seulement:
            c.execute("INSERT INTO flow.issue_current_versions (issue_key, kind, name) VALUES (%s, 'affects', %s)", (cle, SECRET))
        c.execute("RESET ROLE")

    def equipes(self, c):
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.teams (name) VALUES ('Alpha'), ('Beta'), ('Gamma')")
        c.execute("RESET ROLE")

    def lignes(self, c):
        c.commit()
        c.execute("SET ROLE pmzilla_flow_views")
        lignes = c.execute(f"SELECT team, quarter_start, items, with_fix_version, share_percent FROM {VUE}").fetchall()
        c.execute("RESET ROLE")
        return sorted(lignes, key=lambda l: (l[0], l[1]))          # tri en Python : l'ordre d'une collation ne dépend pas des signes

    def remplir(self, c, equipe, nom, total, avec, decalage_mois=-3, prefixe=None):          # -3 : le dernier trimestre terminé
        prefixe = prefixe or nom
        for i in range(total):
            self.ticket(c, f"{prefixe}-{decalage_mois}-{i}", equipe, decalage_mois, avec_version=i < avec)

    def test_colonnes_dans_l_ordre(self):
        c = self.conn()
        colonnes = [r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'flow' "
                                            "AND table_name = 'v_team_fix_version_share' ORDER BY ordinal_position")]
        self.assertEqual(colonnes, ["team", "quarter_start", "items", "with_fix_version", "share_percent", "with_fix_version_min"])

    def lignes_borne(self, c):
        c.commit()
        c.execute("SET ROLE pmzilla_flow_views")
        lignes = c.execute(f"SELECT team, items, with_fix_version, share_percent, with_fix_version_min FROM {VUE}").fetchall()
        c.execute("RESET ROLE")
        return {l[0]: l[1:] for l in lignes}

    def test_borne_basse_publiee_sans_valeur_exacte(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", 20, 18)          # deux sans version : le nombre exact et la part restent masqués, la borne est items - 4
        self.remplir(c, 2, "B", 20, 10)
        self.remplir(c, 3, "C", 20, 10)
        par_equipe = self.lignes_borne(c)
        self.assertEqual(par_equipe["Alpha"], (20, None, None, 16))
        self.assertEqual(par_equipe["Beta"], (20, 10, 50, None))
        # change masking-sums, D3 : les items sont visibles chez toutes les équipes, le produit les montre ; le détail d'Alpha est masqué, celui du produit aussi
        self.assertEqual(par_equipe["(produit)"], (60, None, None, None))

    def test_la_borne_ne_depend_que_des_items_visibles(self):
        c = self.conn()
        self.equipes(c)
        for decalage, sans_version in ((-3, 0), (-6, 1), (-9, 4)):             # un trimestre par cas : la même borne pour 0, 1 ou 4 sans version
            self.remplir(c, 1, "A", 20, 20 - sans_version, decalage)
            self.remplir(c, 2, "B", 20, 10, decalage)
            self.remplir(c, 3, "C", 20, 10, decalage)
        c.commit()
        c.execute("SET ROLE pmzilla_flow_views")
        lignes = c.execute(f"SELECT items, with_fix_version, share_percent, with_fix_version_min FROM {VUE} WHERE team = 'Alpha'").fetchall()
        c.execute("RESET ROLE")
        self.assertEqual(lignes, [(20, None, None, 16)] * 3)

    def test_borne_absente_hors_du_cas(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", 3, 3)            # items sous 5 : rien
        self.remplir(c, 2, "B", 20, 14)          # six sans version : la part exacte est montrée, pas de borne
        self.remplir(c, 3, "C", 20, 10)
        par_equipe = self.lignes_borne(c)
        self.assertEqual(par_equipe["Alpha"], (None, None, None, None))
        self.assertEqual(par_equipe["Beta"], (20, 14, 70, None))

    def test_deux_equipes_a_borne_ne_redonnent_pas_de_valeur_exacte(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", 20, 18)
        self.remplir(c, 2, "B", 20, 17)          # trois sans version : la somme des sans version (5) atteint le seuil
        self.remplir(c, 3, "C", 20, 10)
        par_equipe = self.lignes_borne(c)
        self.assertEqual((par_equipe["Alpha"], par_equipe["Beta"]), ((20, None, None, 16), (20, None, None, 16)))
        # change masking-sums, D3 : le détail du produit exige le détail visible chez toutes les équipes (la somme des deux cellules masquées ne se lit plus)
        self.assertEqual(par_equipe["(produit)"], (60, None, None, None))

    def test_part_par_equipe_et_trimestre(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", 10, 5)          # cinq avec, cinq sans : le détail exact est visible (D10)
        debut = self.debut_trimestre(c, -3)
        self.assertEqual(self.lignes(c), [("(produit)", debut, 10, 5, 50), ("Alpha", debut, 10, 5, 50)])

    def test_quatre_derniers_trimestres_termines(self):
        c = self.conn()
        self.equipes(c)
        for decalage in (0, -3, -6, -9, -12, -15):
            self.remplir(c, 1, "A", 10, 10, decalage)
        trimestres = {l[1] for l in self.lignes(c) if l[0] == "Alpha"}
        # R-20261114-58 : le trimestre en cours (0) et les quatrième (-12) et cinquième (-15) terminés sont hors vue ; seuls les trois derniers terminés y sont
        self.assertEqual(trimestres, {self.debut_trimestre(c, d) for d in (-3, -6, -9)})
        self.assertNotIn(self.debut_trimestre(c, 0), trimestres)

    def test_item_termine_dans_le_trimestre_en_cours_n_est_pas_compte(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", 10, 5, -3)          # cinq sans version : ni l'équipe ni le produit ne sont masqués
        self.remplir(c, 1, "B", 7, 7, 0)                          # sept items terminés ce trimestre : ni dans l'équipe ni dans le produit
        lignes = self.lignes(c)
        self.assertEqual([l[2] for l in lignes if l[0] == "Alpha"], [10])
        self.assertEqual([l[2] for l in lignes if l[0] == "(produit)"], [10])
        self.assertNotIn(self.debut_trimestre(c, 0), {l[1] for l in lignes})

    def test_epics_sorties_de_l_export_et_non_resolus_ecartes(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", 10, 10)
        for i in range(6):
            self.ticket(c, f"E-{i}", 1, type_="Epic", avec_version=True)
            self.ticket(c, f"S-{i}", 1, sorti=True, avec_version=True)
            self.ticket(c, f"O-{i}", 1, resolu=False, avec_version=True)
        self.assertEqual([l[2] for l in self.lignes(c) if l[0] == "Alpha"], [10])

    def test_version_d_affects_seule_ne_compte_pas(self):
        c = self.conn()
        self.equipes(c)
        for i in range(12):          # six avec fix version, six avec affects seule : le compte sans version (6) atteint 5, les comptes exacts sont lisibles
            self.ticket(c, f"A-{i}", 1, avec_version=i < 6, affects_seulement=i >= 6)
        self.assertEqual([l[3] for l in self.lignes(c) if l[0] == "Alpha"], [6])

    def test_masquage_sous_cinq(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", 20, 10)
        self.remplir(c, 2, "B", 3, 3)
        self.remplir(c, 3, "C", 20, 10)
        par_equipe = {l[0]: l[2:] for l in self.lignes(c)}
        self.assertEqual(par_equipe["Beta"], (None, None, None))
        self.assertEqual(par_equipe["Alpha"], (20, 10, 50))

    def test_masquage_complementaire(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", 20, 16)          # quatre sans version : le détail est masqué, le total reste montré
        self.remplir(c, 2, "B", 20, 3)           # trois avec version
        self.remplir(c, 3, "C", 20, 10)
        par_equipe = {l[0]: l[2:] for l in self.lignes(c)}
        self.assertEqual(par_equipe["Alpha"], (20, None, None))
        self.assertEqual(par_equipe["Beta"], (20, None, None))
        self.assertEqual(par_equipe["Gamma"], (20, 10, 50))

    def test_masquage_de_la_ligne_produit(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", 20, 10)
        self.remplir(c, 2, "B", 3, 3)            # une seule cellule d'équipe masquée : le produit la redonnerait par différence
        produit = [l for l in self.lignes(c) if l[0] == "(produit)"]
        self.assertEqual([p[2:] for p in produit], [(None, None, None)])

    def test_produit_visible_sans_cellule_masquee(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", 20, 10)
        self.remplir(c, 2, "B", 10, 5)
        produit = [l for l in self.lignes(c) if l[0] == "(produit)"]
        self.assertEqual([p[2:] for p in produit], [(30, 15, 50)])

    def test_aucun_nom_de_version_dans_la_vue(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", 10, 10)
        self.assertNotIn(SECRET, repr(self.lignes(c)))

    def test_droits(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", 10, 10)
        c.commit()
        self.assertTrue(self.essaie(c, "pmzilla_flow_views", f"SELECT * FROM {VUE}"))
        for role in ("pmzilla_quality_views", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_cases"):
            self.assertFalse(self.essaie(c, role, f"SELECT * FROM {VUE}"), role)
        for role in ("pmzilla_flow_views", "pmzilla_quality_views", "pmzilla_flow_ro"):
            self.assertFalse(self.essaie(c, role, "SELECT * FROM flow.issue_current_versions"), role)
        for droit in ("INSERT", "UPDATE", "DELETE"):
            self.assertFalse(c.execute("SELECT has_table_privilege('pmzilla_flow_views', %s, %s)", (VUE, droit)).fetchone()[0], droit)

    def test_colonne_des_versions_courantes_nulle_pour_un_ancien_instantane(self):
        c = self.conn()
        ligne = c.execute("SELECT data_type, is_nullable FROM information_schema.columns WHERE table_schema = 'flow' "
                          "AND table_name = 'raw_issue_snapshots' AND column_name = 'current_versions'").fetchone()
        self.assertEqual(ligne, ("jsonb", "YES"))

    def test_table_brute_toujours_sans_mise_a_jour(self):
        c = self.conn()
        self.assertFalse(c.execute("SELECT has_table_privilege('pmzilla_flow', 'flow.raw_issue_snapshots', 'UPDATE')").fetchone()[0])
        self.assertTrue(c.execute("SELECT has_table_privilege('pmzilla_flow', 'flow.raw_issue_snapshots', 'INSERT')").fetchone()[0])

    def test_suppression_en_cascade_du_ticket(self):
        c = self.conn()
        self.equipes(c)
        self.ticket(c, "PROJ-1", 1, avec_version=True)
        c.execute("SET ROLE pmzilla_flow")
        c.execute("DELETE FROM flow.issues WHERE key = 'PROJ-1'")
        self.assertEqual(c.execute("SELECT count(*) FROM flow.issue_current_versions").fetchone()[0], 0)
        c.execute("RESET ROLE")


if __name__ == "__main__":
    unittest.main()
