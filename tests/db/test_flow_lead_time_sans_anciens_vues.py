"""Les quatre statistiques « sans les anciens » de flow.v_team_lead_time_throughput contre la base (change masking-sums, tâche 22.1 ; migrations 0037 et 0038 ;
conception D16 ; R-20261105-30, R-20261106-39, R-20261106-52, R-20261106-59 ; revue 21.2, constat 1).

    bash tools/dbtest.sh db

Écrit pour le dbtest de l'auteur et pour la preuve en conteneur de la session : aucune de ces classes ne tourne sans la base jetable de test_flow_schema.py et aucune n'est
lancée par une session hors conteneur. Trois choses sont jouées sur les mêmes lignes synthétiques (équipes inventées Alpha, Beta, Gamma) :

  (a) 0037 puis 0038 : la vue de 0037 (son texte, relu dans le fichier et créé en vue temporaire) et la vue de 0038 donnent les mêmes valeurs aux douze colonnes
      existantes, ligne à ligne ;
  (b) X39 (huit éléments dont trois anciens : items_old masqué, quatre statistiques nulles), le cas des trois trimestres de 5 avec quatre anciens chacun (X40 : tous les
      items_old et les statistiques de l'année nuls) et les cas du zéro (X42a : zéro montré avec items_ct ; X42b : l'année à zéro masquée parce qu'un trimestre l'est) ;
  (c) une statistique montrée (items_old montré, reste d'au moins 5 : les percentiles excluent les anciens) et une statistique absente (items_old masqué).

Les rangs et les valeurs sont ceux de `masquer_vue` (cas partagés de contrats/cas-masquage.json) : la vue au plancher donne les cellules du lecteur. Données inventées.
"""
import re
import unittest

import test_flow_slice1_views as s1   # noqa: E402
from test_flow_slice1_views import VUE_LT, sans_commentaires  # noqa: E402
import test_flow_schema as fs   # noqa: E402

SUFFIXE_0037 = "_flow_lead_time_old_zero.sql"
EXISTANTES = ("team, period, quarter_start, throughput, items_lt, lead_median_days, lead_p85_days, items_ct, cycle_median_days, cycle_p85_days, "
              "items_old, items_without_commitment")
NOUVELLES = ("lead_median_days_excl_old", "lead_p85_days_excl_old", "cycle_median_days_excl_old", "cycle_p85_days_excl_old")
TOUTES_NOUVELLES = ", ".join(NOUVELLES)


def corps_0037():
    from test_db import db
    candidats = [m for m in db.lister_migrations() if m.nom.endswith(SUFFIXE_0037)]
    assert len(candidats) == 1, f"une migration *{SUFFIXE_0037} est attendue"
    code = sans_commentaires(candidats[0].chemin.read_text(encoding="utf-8"))
    trouve = re.search(r"(?is)CREATE\s+OR\s+REPLACE\s+VIEW\s+flow\.v_team_lead_time_throughput\s+AS\s+(WITH.*?)\s*;\s*RESET\s+ROLE", code)
    assert trouve, "la vue de 0037 est introuvable"
    return trouve.group(1)


class AvecBase(unittest.TestCase):
    """Même base jetable que SchemaFlow, avec les aides de tests/db/test_flow_slice1_views.py (cohorte, passage, trimestre) sans ses tests."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie
    equipes = s1.AvecBase.equipes
    ticket = s1.AvecBase.ticket
    lignes = s1.AvecBase.lignes
    quarter = s1.AvecBase.quarter
    remplir = s1.AvecBase.remplir
    definitions = s1.AvecBase.definitions
    passage = s1.AvecBase.passage
    cohorte = s1.AvecBase.cohorte
    annee = s1.AvecBase.annee
    trimestre = s1.AvecBase.trimestre
    STATUT_PRET = s1.AvecBase.STATUT_PRET

    def jeu(self, c):
        """Alpha : X39 (huit éléments dont trois anciens, trimestre -3) et un trimestre de 20 sans ancien (-6). Beta : trois trimestres de 5, quatre anciens chacun (X40).
        Gamma : trois trimestres de 20 dont un de 4 éléments (-3), sans ancien, et un trimestre de 20 dont six anciens (-9). R-20261114-58 : trois trimestres, le
        décalage -12 est hors vue."""
        self.equipes(c)
        self.definitions(c, statuts=[self.STATUT_PRET])
        self.cohorte(c, 1, -3, "A", 8, 0, anciens=3)
        self.cohorte(c, 1, -6, "A", 20, 0)
        for decalage in (-3, -6, -9):
            self.cohorte(c, 2, decalage, "B", 5, 0, anciens=4)
        self.cohorte(c, 3, -3, "G", 4, 0)
        self.cohorte(c, 3, -6, "G", 20, 0)
        self.cohorte(c, 3, -9, "G", 20, 0, anciens=6)

    def ligne(self, c, equipe, decalage):
        """(items_old, quatre statistiques) du trimestre décalé d'une équipe, ou de l'année groupée (decalage None)."""
        colonnes = f"team, quarter_start, period, items_old, {TOUTES_NOUVELLES}"
        for l in self.lignes(c, VUE_LT, colonnes):
            if l[0] == equipe and ((decalage is None and l[2] == "pooled_year") or (decalage is not None and l[1] == self.quarter(c, decalage))):
                return l[3:]
        self.fail(f"ligne absente : {equipe} {decalage}")

    # --- (a) 0037 puis 0038 sur les mêmes lignes ---------------------------------------------------------------------------------------------------------------

    def test_les_douze_colonnes_existantes_sont_celles_de_0037_ligne_a_ligne(self):
        c = self.conn()
        self.jeu(c)
        c.commit()
        c.execute(f"CREATE TEMP VIEW v_lead_0037 AS {corps_0037()}")
        avant = c.execute(f"SELECT {EXISTANTES} FROM pg_temp.v_lead_0037 ORDER BY team, period, quarter_start").fetchall()
        apres = c.execute(f"SELECT {EXISTANTES} FROM {VUE_LT} ORDER BY team, period, quarter_start").fetchall()
        self.assertTrue(avant)
        self.assertEqual(apres, avant)

    def test_les_colonnes_sont_les_douze_puis_les_quatre_et_les_droits_sont_ceux_de_0037(self):
        c = self.conn()
        colonnes = [r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'flow' "
                                            "AND table_name = 'v_team_lead_time_throughput' ORDER BY ordinal_position")]
        self.assertEqual(colonnes, [x.strip() for x in EXISTANTES.split(",")] + list(NOUVELLES))
        self.assertTrue(self.essaie(c, "pmzilla_flow_views", f"SELECT * FROM {VUE_LT}"))
        for role in ("pmzilla_quality_views", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_cases"):
            self.assertFalse(self.essaie(c, role, f"SELECT * FROM {VUE_LT}"), role)

    # --- (b) X39, X40, X42a, X42b contre la vue ----------------------------------------------------------------------------------------------------------------

    def test_X39_huit_elements_dont_trois_anciens_items_old_et_les_quatre_statistiques_masques(self):
        c = self.conn()
        self.jeu(c)
        o, *stats = self.ligne(c, "Alpha", -3)
        self.assertIsNone(o)                                    # trois : sous le seuil, masqué
        self.assertEqual(stats, [None] * 4)                     # la statistique n'est jamais montrée avec items_old masqué
        alpha = [l for l in self.lignes(c, VUE_LT, "team, quarter_start, throughput, items_lt, items_ct") if l[0] == "Alpha" and l[1] == self.quarter(c, -3)][0]
        self.assertEqual(alpha[2:], (8, 8, 8))     # revue de contrôle 21.2, C1 : la ligne d'Alpha ; les effectifs sont montrés, seule items_old ne l'est pas

    def test_X40_trois_trimestres_de_5_avec_quatre_anciens_chacun_tout_est_masque_y_compris_l_annee(self):
        c = self.conn()
        self.jeu(c)
        for decalage in (-3, -6, -9):
            self.assertEqual(self.ligne(c, "Beta", decalage), (None, None, None, None, None), decalage)
        self.assertEqual(self.ligne(c, "Beta", None), (None, None, None, None, None))      # items_old de l'année et statistiques de l'année nuls

    def test_X42a_le_zero_d_items_old_est_montre_avec_items_ct_et_les_statistiques_aussi(self):
        c = self.conn()
        self.jeu(c)
        o, lead_med, lead_p85, cycle_med, cycle_p85 = self.ligne(c, "Alpha", -6)
        self.assertEqual(o, 0)
        self.assertEqual((float(lead_med), float(lead_p85), float(cycle_med), float(cycle_p85)), (20.0, 20.0, 5.0, 5.0))

    def test_X42b_l_annee_a_zero_est_masquee_parce_qu_un_trimestre_l_est(self):
        c = self.conn()
        self.jeu(c)
        self.assertIsNone(self.ligne(c, "Gamma", -3)[0])        # quatre éléments : le trimestre est masqué
        self.assertEqual(self.ligne(c, "Gamma", None), (None, None, None, None, None))

    # --- (c) une statistique montrée, une absente ---------------------------------------------------------------------------------------------------------------

    def test_une_statistique_montree_exclut_les_anciens_du_calcul(self):
        c = self.conn()
        self.jeu(c)
        o, lead_med, lead_p85, cycle_med, cycle_p85 = self.ligne(c, "Gamma", -9)       # 20 éléments dont six anciens (créés 500 jours avant) : items_old 6, reste 14
        self.assertEqual(o, 6)
        self.assertEqual((float(lead_med), float(lead_p85), float(cycle_med), float(cycle_p85)), (20.0, 20.0, 5.0, 5.0))
        pour_gamma = [l for l in self.lignes(c, VUE_LT, "team, quarter_start, lead_p85_days") if l[0] == "Gamma" and l[1] == self.quarter(c, -9)][0]
        self.assertEqual(float(pour_gamma[2]), 500.0)           # la statistique existante compte les anciens (500 jours), la nouvelle non (20)

    def test_une_statistique_absente_quand_items_old_est_masque(self):
        c = self.conn()
        self.jeu(c)
        o, *stats = self.ligne(c, "Alpha", -3)
        self.assertIsNone(o)
        self.assertTrue(all(s is None for s in stats))


if __name__ == "__main__":
    unittest.main()
