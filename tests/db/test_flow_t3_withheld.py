"""Relation T3 contre les vues, base jetable (change masking-sums, D17, R-20261031-07, tâche 13.1 ; cas partagés X26a à X26f de contrats/cas-masquage.json).

    bash tools/dbtest.sh db

Écrit sans être lancé par l'agent de la tâche 13.1 (les modules de tests/db sont lancés par l'auteur seul). Les mêmes chiffres que les cas partagés : le
trimestre précédent (décalage -3), deux semaines entières (lundi UTC, mercredi de résolution), une équipe par cas. Rouges avant la migration de
flow.v_t3_withheld (tâche 13.2) : le débit masqué laissait lire ses lignes, un débit visible laissait lire la somme des lignes masquées.
Rôle de lecture : pmzilla_flow_views, comme le lecteur. Données inventées : équipes Alpha et Beta.
"""
import re
import unittest

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402

VUE_LT = "flow.v_team_lead_time_throughput"
VUE_HEBDO = "flow.v_team_weekly_resolved"
VUE_INTERNE = "flow.v_t3_withheld"
ROLES = ("pmzilla_flow_views", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_quality_views", "pmzilla_cases", "pmzilla_knowledge_ro")


class SansBase(unittest.TestCase):
    def test_migration_de_la_vue_interne_presente_et_derniere(self):
        migrations = [m for m in db.lister_migrations() if m.nom.endswith("_flow_t3_withheld.sql")]
        self.assertEqual(len(migrations), 1)
        # relatif : numérotée juste après la migration 0029 de main (les migrations qui suivront, 36.1 et 38 de mothra-slices, prennent leur numéro au rebase)
        precedente = [m for m in db.lister_migrations() if m.nom.endswith("_flow_slice1_mask_comptes.sql")]
        self.assertEqual(migrations[0].numero, precedente[0].numero + 1)
        code = re.sub(r"--[^\n]*", "", migrations[0].chemin.read_text(encoding="utf-8"))
        self.assertRegex(code, r"(?is)SET\s+LOCAL\s+ROLE\s+pmzilla_owner")
        self.assertNotRegex(code, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")


class AvecBase(unittest.TestCase):
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def equipes(self, c):
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.teams (name) VALUES ('Alpha'), ('Beta')")
        c.execute("RESET ROLE")

    def ticket(self, c, cle, equipe, type_, semaine, decalage=-3):
        """Un ticket terminé le mercredi de la semaine `semaine` (0 ou 1) du trimestre décalé de `decalage` mois, entièrement dans le trimestre."""
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, resolved_at, updated_at, team_id) "
                  "SELECT %s, 'PROJ', %s, 'Closed', 'Done', r - interval '10 days', r, now(), %s "
                  "FROM (SELECT (date_trunc('week', date_trunc('quarter', now() AT TIME ZONE 'UTC') + make_interval(months => %s) "
                  "+ make_interval(days => %s)) + interval '2 days') AT TIME ZONE 'UTC' AS r) x",
                  (cle, type_, equipe, decalage, 20 + 7 * semaine))
        c.execute("RESET ROLE")

    def remplir(self, c, equipe, type_, semaine, n, decalage=-3):
        for i in range(n):
            self.ticket(c, f"{equipe}-{type_}-{semaine}-{decalage}-{i}", equipe, type_, semaine, decalage)

    def lire(self, c, requete):
        c.commit()
        c.execute("SET ROLE pmzilla_flow_views")
        try:
            return c.execute(requete).fetchall()
        finally:
            c.execute("RESET ROLE")

    def debit(self, c):
        """{équipe : débit du trimestre précédent tel que la vue le publie (None si masqué)}"""
        return {l[0]: l[1] for l in self.lire(c, f"SELECT team, throughput FROM {VUE_LT} WHERE period = 'quarter'")}

    def hebdo(self, c):
        return self.lire(c, f"SELECT team, type, week_start, tickets FROM {VUE_HEBDO} ORDER BY team, type, week_start")

    def jouer(self, cellules, equipe=1, nom="Alpha"):
        """Crée les tickets (type, semaine, nombre) de l'équipe `equipe` et rend (débit publié, lignes hebdomadaires de l'équipe)."""
        c = self.conn()
        self.equipes(c)
        for type_, semaine, n in cellules:
            self.remplir(c, equipe, type_, semaine, n)
        return self.debit(c).get(nom), [l for l in self.hebdo(c) if l[0] == nom]

    # --- cas partagés X26a à X26f -----------------------------------------------------------------------------------------------------------------------

    def test_x26a_debit_masque_les_quatre_lignes_de_un_sont_retirees_la_ligne_bug_reste(self):
        debit, lignes = self.jouer([("Story", 0, 1), ("Task", 0, 1), ("Story", 1, 1), ("Task", 1, 1), ("Bug", 0, 12)])
        self.assertIsNone(debit)
        self.assertEqual([(l[1], l[3]) for l in lignes], [("Bug", 12)])

    def test_x26b_une_ligne_masquee_reste_3_le_debit_est_masque_et_les_lignes_retirees(self):
        debit, lignes = self.jouer([("Story", 0, 12), ("Task", 0, 8), ("Story", 1, 3)])
        self.assertIsNone(debit)
        self.assertEqual(lignes, [])

    def test_x26c_reste_egal_au_nombre_de_lignes_masquees(self):
        debit, lignes = self.jouer([("Story", 0, 12), ("Task", 0, 11), ("Story", 1, 1), ("Task", 1, 1)])
        self.assertIsNone(debit)
        self.assertEqual(lignes, [])

    def test_x26d_reste_egal_a_quatre_fois_le_nombre_de_lignes_masquees(self):
        debit, lignes = self.jouer([("Story", 0, 12), ("Task", 0, 11), ("Story", 1, 4), ("Task", 1, 4)])
        self.assertIsNone(debit)
        self.assertEqual(lignes, [])

    def test_x26e_reste_sous_le_seuil_avec_deux_lignes_masquees(self):
        debit, lignes = self.jouer([("Story", 0, 12), ("Task", 0, 11), ("Story", 1, 1), ("Task", 1, 2)])
        self.assertIsNone(debit)
        self.assertEqual(lignes, [])

    def test_x26f_temoin_vert_reste_5_rien_n_est_epingle_tout_est_publie(self):
        debit, lignes = self.jouer([("Story", 0, 12), ("Task", 0, 11), ("Story", 1, 3), ("Task", 1, 2)])
        self.assertEqual(debit, 28)
        self.assertEqual(sorted(((l[1], l[3]) for l in lignes), key=lambda x: (x[0], -1 if x[1] is None else x[1])),
                         [("Story", None), ("Story", 12), ("Task", None), ("Task", 11)])

    # --- autres propriétés ------------------------------------------------------------------------------------------------------------------------------

    def test_aucune_ligne_masquee_rien_a_cacher_tout_est_publie(self):
        debit, lignes = self.jouer([("Story", 0, 6), ("Task", 1, 7)])
        self.assertEqual(debit, 13)
        self.assertEqual(sorted(l[3] for l in lignes), [6, 7])

    def test_une_autre_equipe_n_est_pas_touchee(self):
        c = self.conn()
        self.equipes(c)
        for type_, semaine, n in (("Story", 0, 12), ("Task", 0, 8), ("Story", 1, 3)):      # Alpha : X26b
            self.remplir(c, 1, type_, semaine, n)
        for type_, semaine, n in (("Story", 0, 6), ("Task", 1, 7)):                          # Beta : rien à cacher
            self.remplir(c, 2, type_, semaine, n)
        self.assertEqual(self.debit(c), {"Alpha": None, "Beta": 13})
        self.assertEqual([(l[0], l[3]) for l in self.hebdo(c)], [("Beta", 6), ("Beta", 7)])

    def test_les_tickets_sans_equipe_gardent_leurs_lignes(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, None, "Story", 0, 2)                                                 # sans équipe : jamais retiré, masqué par sa propre règle
        lignes = self.hebdo(c)
        self.assertEqual([(l[0], l[1], l[3]) for l in lignes], [("(sans équipe)", "Story", None)])

    def test_la_vue_interne_n_est_lisible_par_aucun_role(self):
        c = self.conn()
        for role in ROLES:
            self.assertFalse(self.essaie(c, role, f"SELECT * FROM {VUE_INTERNE}"), role)

    def test_la_vue_interne_liste_l_equipe_et_le_trimestre_retires(self):
        c = self.conn()
        self.equipes(c)
        for type_, semaine, n in (("Story", 0, 12), ("Task", 0, 8), ("Story", 1, 3)):
            self.remplir(c, 1, type_, semaine, n)
        c.commit()
        lignes = c.execute(f"SELECT team, quarter_start FROM {VUE_INTERNE}").fetchall()
        quarter = c.execute("SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') - interval '3 months')::date").fetchone()[0]
        self.assertEqual(lignes, [("Alpha", quarter)])

    def test_colonnes_inchangees(self):
        c = self.conn()
        colonnes = {vue: [r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'flow' "
                                                  "AND table_name = %s ORDER BY ordinal_position", (vue,))]
                    for vue in ("v_team_weekly_resolved", "v_team_lead_time_throughput")}
        self.assertEqual(colonnes["v_team_weekly_resolved"], ["team", "type", "week_start", "tickets"])
        self.assertEqual(colonnes["v_team_lead_time_throughput"],
                         ["team", "period", "quarter_start", "throughput", "items_lt", "lead_median_days", "lead_p85_days", "items_ct",
                          "cycle_median_days", "cycle_p85_days", "items_old", "items_without_commitment",
                          # R-20261106-58 : les quatre colonnes de D16 (migration 0038), et elles seules, en fin de liste
                          "lead_median_days_excl_old", "lead_p85_days_excl_old", "cycle_median_days_excl_old", "cycle_p85_days_excl_old"])
        for vue in colonnes:
            self.assertTrue(self.essaie(c, "pmzilla_flow_views", f"SELECT * FROM flow.{vue}"), vue)
        # v_team_lead_time_throughput (0026) : SELECT au seul rôle des vues
        for role in ("pmzilla_quality_views", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_cases"):
            self.assertFalse(self.essaie(c, role, "SELECT * FROM flow.v_team_lead_time_throughput"), role)
        # v_team_weekly_resolved (0002, droits par défaut du lot 1, conservés par 0030) : les droits de main ; seuls les rôles qui ne la lisaient pas sont testés
        for role in ("pmzilla_quality_views", "pmzilla_cases"):
            self.assertFalse(self.essaie(c, role, "SELECT * FROM flow.v_team_weekly_resolved"), role)

    def test_annee_groupee_masquee_des_qu_un_trimestre_est_retire_par_t3(self):
        """Revue de T3, B1 : q1 = 1 (masqué), q2 = 6 avec une ligne masquée (la règle (b) échoue : le débit est retiré), q3 visible (R-20261114-58 : trois
        trimestres au lieu de quatre, un seul trimestre visible). Deux trimestres masqués dont la somme fait 7 ne tiennent pas la règle de série seule
        (flow.fuite_serie n'est pas monotone) : l'année sortait publiée, et q2 se lisait par sa médiane. L'année doit sortir masquée."""
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "Story", 0, 1, decalage=-9)                        # q1 : 1 ticket
        self.remplir(c, 1, "Story", 0, 5, decalage=-6)                        # q2 : 6 tickets, la ligne Task de 1 est masquée, k = 1, S = 1
        self.remplir(c, 1, "Task", 0, 1, decalage=-6)
        self.remplir(c, 1, "Story", 0, 15, decalage=-3)                       # q3 visible
        lignes = self.lire(c, f"SELECT period, quarter_start, throughput, items_lt FROM {VUE_LT} WHERE team = 'Alpha' ORDER BY period, quarter_start")
        annee = [l for l in lignes if l[0] == "pooled_year"][0]
        self.assertEqual(annee[2:], (None, None))
        trimestres = [l for l in lignes if l[0] == "quarter"]
        self.assertEqual([l[2] for l in trimestres], [None, None, 15])


if __name__ == "__main__":
    unittest.main()
