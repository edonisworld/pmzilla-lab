"""
Tests du jeu synthétique de Mothra, tranche 0 (#240, tâche 5.2).

Sans base : la forme du jeu (équipes génériques, clés inventées, dates relatives, comptes témoins, sentinelles).
Avec la base jetable de bash tools/dbtest.sh mothra_donnees (sautés sans DBTEST_PORT) : la vue flow.v_team_status peuplée, des
cellules NULL présentes, aucune sentinelle dans la vue, deux chargements identiques.

    bash tests/run_all.sh mothra_donnees
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest
from collections import Counter
from datetime import timedelta
from pathlib import Path
from unittest import mock

DOSSIER = Path(__file__).resolve().parent
RACINE = DOSSIER.parents[1]
sys.path.insert(0, str(DOSSIER))
sys.path.insert(0, str(RACINE / "tests" / "flow_store"))
import jeu_synthetique as jeu  # noqa: E402
import aide_base  # noqa: E402

MAINTENANT = jeu.INSTANT_FIXE


def comptes_par_cellule(tickets: list[dict]) -> Counter:
    return Counter((t["equipe"] or "(sans équipe)", t["type"], t["categorie"], t["statut"]) for t in tickets)


class FormeDuJeu(unittest.TestCase):
    def setUp(self):
        self.tickets = jeu.construire(MAINTENANT)

    def test_equipes_generiques(self):
        noms = {t["equipe"] for t in self.tickets if t["equipe"]}
        self.assertGreaterEqual(len(noms), 3)
        for nom in noms:
            self.assertRegex(nom, r"^équipe [A-Z]$")

    def test_des_tickets_sans_equipe(self):
        self.assertTrue(any(t["equipe"] is None for t in self.tickets))

    def test_cles_inventees_et_uniques(self):
        cles = [t["cle"] for t in self.tickets]
        self.assertEqual(len(cles), len(set(cles)))
        for cle in cles:
            self.assertRegex(cle, r"^SYN-[1-9][0-9]*$")

    def test_comptes_temoins_1_a_4_et_5(self):
        comptes = set(comptes_par_cellule(self.tickets).values())
        for temoin in (1, 2, 3, 4, 5):
            self.assertIn(temoin, comptes)
        self.assertTrue(any(c > 5 for c in comptes))

    def test_sentinelles_dans_des_colonnes_non_exposees(self):
        for t in self.tickets:
            # colonnes de la vue : équipe, type, catégorie, statut
            for colonne in ("equipe", "type", "categorie", "statut"):
                for sentinelle in jeu.SENTINELLES:
                    self.assertNotIn(sentinelle, str(t[colonne]))
        texte = repr(self.tickets)
        for sentinelle in jeu.SENTINELLES:
            self.assertIn(sentinelle, texte)

    def test_deterministe(self):
        self.assertEqual(jeu.construire(MAINTENANT), jeu.construire(MAINTENANT))

    def test_dates_relatives_a_l_instant_du_chargement(self):
        # R-20261105-16 et R-20261105-17 : les tickets ouverts suivent l'instant du chargement, les tickets « Done » suivent l'ancre de trimestre.
        decalage = timedelta(days=400, minutes=7)
        autre = jeu.construire(MAINTENANT + decalage)
        decalage_ancre = jeu.ancre(MAINTENANT + decalage) - jeu.ancre(MAINTENANT)
        for a, b in zip(self.tickets, autre):
            if a["resolu"] is None:
                self.assertEqual(b["cree"] - a["cree"], decalage)
            self.assertEqual((b["resolu"] is None), (a["resolu"] is None))
            if a["resolu"]:
                self.assertEqual(b["cree"] - a["cree"], decalage_ancre)
                self.assertEqual(b["resolu"] - a["resolu"], decalage_ancre)

    def test_dates_des_done_identiques_quand_l_ancre_ne_bouge_pas(self):
        # Même trimestre, autre heure et autre jour : l'ancre ne bouge pas, les dates des tickets « Done » sont identiques (R-20261105-17).
        decalage = timedelta(days=3, hours=5, minutes=11)
        self.assertEqual(jeu.ancre(MAINTENANT + decalage), jeu.ancre(MAINTENANT))
        autre = jeu.construire(MAINTENANT + decalage)
        for a, b in zip(self.tickets, autre):
            if a["resolu"] is None:
                self.assertEqual(b["cree"] - a["cree"], decalage)
            else:
                self.assertEqual((b["cree"], b["resolu"]), (a["cree"], a["resolu"]))

    def test_dates_coherentes(self):
        for t in self.tickets:
            self.assertLessEqual(t["cree"], MAINTENANT)
            if t["resolu"]:
                self.assertGreaterEqual(t["resolu"], t["cree"])
                self.assertLessEqual(t["resolu"], MAINTENANT)
            self.assertEqual(t["categorie"] == "Done", t["resolu"] is not None)


class ResolutionBornee(unittest.TestCase):
    def test_resolution_jamais_apres_maintenant_moins_une_heure(self):
        # Le jeu de la tranche 0 n'a aucun ticket que la borne rattrape (son dernier « Done » tombe à ancre + 57 jours, avant la fin du
        # dernier trimestre terminé) ; un jeu de 30 tickets résolus (le rang 26 : résolu à ancre + 100 j − 5 j 2 h + 10 j, après l'instant
        # du chargement pour INSTANT_FIXE, donc borné, puis créé 10 jours avant) l'y oblige, pour que le test ne soit pas vide.
        borne_atteinte = False
        for groupes in (jeu.GROUPES, (("équipe A", "Story", "Done", "Done", 30),)):
            with mock.patch.object(jeu, "GROUPES", groupes):
                for decalage in (timedelta(0), timedelta(days=-5), timedelta(days=1), timedelta(hours=3), timedelta(days=200, minutes=13)):
                    maintenant = MAINTENANT + decalage
                    for t in jeu.construire(maintenant):
                        if t["resolu"]:
                            self.assertLessEqual(t["resolu"], maintenant - timedelta(hours=1), t["cle"])
                            self.assertGreaterEqual(t["resolu"], t["cree"], t["cle"])
                            borne_atteinte = borne_atteinte or t["resolu"] == maintenant - timedelta(hours=1)
                        self.assertLessEqual(t["maj"], maintenant, t["cle"])
        self.assertTrue(borne_atteinte, "aucun ticket rattrapé par la borne : le test serait vide")


SCRIPT = DOSSIER / "jeu_synthetique.py"
MESSAGE = "jeu synthétique : base jetable absente"
INSERTION_REELLE = ("INSERT INTO flow.issues (key, project, type, status, created_at, updated_at) "
                    "VALUES (%s, 'PROJET', 'Story', 'To Do', now(), now())")


class ChargeurAvecBase(aide_base.AvecBase):
    """Le chargeur sur la base jetable du test : rôle pris en local, garde contre une copie de données réelles, sous-processus."""

    def lancer(self):
        # os.environ porte déjà l'adresse, le mot de passe et le faux Trousseau de la base du test (aide_base), et les repères de dbtest.sh
        return subprocess.run([sys.executable, "-B", "-I", str(SCRIPT)], capture_output=True, text=True, env=dict(os.environ),
                              stdin=subprocess.DEVNULL, timeout=120)

    def nombre_syn(self) -> int:
        self.conn.rollback()
        return self.conn.execute("SELECT count(*) FROM flow.issues WHERE key LIKE 'SYN-%'").fetchone()[0]

    def utilisateur(self) -> str:
        """current_user de la connexion du test, puis la transaction ouverte par cette lecture est fermée (le chargeur veut une connexion au repos)."""
        nom = self.conn.execute("SELECT current_user").fetchone()[0]
        self.conn.rollback()
        return nom

    def test_sous_processus_sortie_0_et_vue_peuplee(self):
        fait = self.lancer()
        self.assertEqual(fait.returncode, 0, fait.stderr)
        self.assertIn("tickets chargés", fait.stdout)
        self.conn.rollback()
        self.conn.execute("SET ROLE pmzilla_flow_views")
        try:
            lignes = self.conn.execute("SELECT team, tickets FROM flow.v_team_status").fetchall()
        finally:
            self.conn.execute("RESET ROLE")
        self.assertTrue(lignes)
        self.assertTrue(any(ligne[1] is not None for ligne in lignes))
        self.assertEqual(self.nombre_syn(), len(jeu.construire(MAINTENANT)))

    def test_role_rendu_apres_chargement(self):
        avant = self.utilisateur()
        jeu.charger(self.conn, MAINTENANT)
        self.assertEqual(self.utilisateur(), avant)

    def test_role_rendu_apres_refus(self):
        avant = self.utilisateur()
        self.conn.execute(INSERTION_REELLE, ("REEL-1",))
        self.conn.commit()
        with self.assertRaises(jeu.RefusJeu):
            jeu.charger(self.conn, MAINTENANT)
        self.assertEqual(self.utilisateur(), avant)

    def test_connexion_deja_dans_une_transaction_refusee(self):
        self.conn.execute("SELECT 1")
        with self.assertRaises(jeu.RefusJeu):
            jeu.charger(self.conn, MAINTENANT)
        self.assertEqual(self.nombre_syn(), 0)

    def test_connexion_en_autocommit_refusee(self):
        autocommit = aide_base.db.connect(self.url, password=aide_base.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(autocommit.close)
        with self.assertRaises(jeu.RefusJeu):
            jeu.charger(autocommit, MAINTENANT)
        self.assertEqual(autocommit.execute("SELECT count(*) FROM flow.issues").fetchone()[0], 0)

    def test_cle_reelle_refusee_rien_ecrit(self):
        self.conn.execute(INSERTION_REELLE, ("REEL-1",))
        self.conn.commit()
        with self.assertRaises(jeu.RefusJeu) as refus:
            jeu.charger(self.conn, MAINTENANT)
        self.assertEqual(str(refus.exception), MESSAGE)
        self.assertEqual(self.nombre_syn(), 0)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM flow.teams").fetchone()[0], 0)

    def test_nom_d_equipe_reel_refuse_rien_ecrit(self):
        self.conn.execute("INSERT INTO flow.teams (name) VALUES ('Nom hors du jeu')")
        self.conn.commit()
        with self.assertRaises(jeu.RefusJeu):
            jeu.charger(self.conn, MAINTENANT)
        self.assertEqual(self.nombre_syn(), 0)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM flow.teams").fetchone()[0], 1)

    def test_sous_processus_refuse_une_base_a_donnees_reelles(self):
        self.conn.execute(INSERTION_REELLE, ("REEL-1",))
        self.conn.commit()
        fait = self.lancer()
        self.assertEqual(fait.returncode, 2, fait.stderr)
        self.assertIn(MESSAGE, fait.stderr)
        self.assertEqual(self.nombre_syn(), 0)


class VueStatutParEquipe(aide_base.AvecBase):
    def charger(self, maintenant=MAINTENANT):
        self.conn.commit()   # le chargeur veut une connexion au repos
        jeu.charger(self.conn, maintenant)

    def lire_vue(self) -> list[tuple]:
        """La vue lue sous le rôle limité aux vues, comme Mothra la lira."""
        self.conn.execute("SET ROLE pmzilla_flow_views")
        try:
            lignes = self.conn.execute(
                "SELECT team, type, status_category, status, tickets FROM flow.v_team_status ORDER BY 1, 2, 3, 4").fetchall()
        finally:
            self.conn.execute("RESET ROLE")
        return lignes

    def test_vue_peuplee_avec_les_cellules_attendues(self):
        self.charger()
        attendu = comptes_par_cellule(jeu.construire(MAINTENANT))
        lignes = self.lire_vue()
        self.assertEqual(len(lignes), len(attendu))
        for equipe, type_, categorie, statut, tickets in lignes:
            compte = attendu[(equipe, type_, categorie, statut)]
            self.assertEqual(tickets, compte if compte >= 5 else None, (equipe, type_, categorie, statut))

    def test_cellules_nulles_et_cellules_a_5_presentes(self):
        self.charger()
        valeurs = [ligne[4] for ligne in self.lire_vue()]
        self.assertIn(None, valeurs)
        self.assertIn(5, valeurs)
        self.assertTrue(any(v is not None and v > 5 for v in valeurs))

    def test_aucune_sentinelle_ni_cle_dans_la_vue(self):
        self.charger()
        texte = repr(self.lire_vue())
        for sentinelle in jeu.SENTINELLES:
            self.assertNotIn(sentinelle, texte)
        self.assertNotRegex(texte, r"SYN-\d")

    def test_les_sentinelles_sont_bien_dans_les_tables(self):
        self.charger()
        projet = self.conn.execute("SELECT count(*) FROM flow.issues WHERE project = %s", (jeu.SENTINELLES[0],)).fetchone()[0]
        self.assertEqual(projet, len(jeu.construire(MAINTENANT)))

    def test_deterministe_sur_deux_chargements(self):
        self.charger()
        premiere_vue = self.lire_vue()
        premieres_lignes = self.conn.execute("SELECT * FROM flow.issues ORDER BY key").fetchall()
        self.charger()
        self.assertEqual(self.lire_vue(), premiere_vue)
        self.assertEqual(self.conn.execute("SELECT * FROM flow.issues ORDER BY key").fetchall(), premieres_lignes)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM flow.teams").fetchone()[0], 4)

    def test_dates_relatives_au_chargement(self):
        # R-20261105-17, étendue à ce test avec base par R-20261105-20 : les tickets ouverts suivent l'instant du chargement, les tickets
        # « Done » suivent l'ancre de trimestre ; égalités exactes dans les deux cas.
        ouverts = "SELECT min(created_at), max(created_at) FROM flow.issues WHERE resolved_at IS NULL"
        termines = "SELECT min(created_at), max(created_at), min(resolved_at), max(resolved_at) FROM flow.issues WHERE resolved_at IS NOT NULL"
        self.charger()
        avant, avant_t = self.conn.execute(ouverts).fetchone(), self.conn.execute(termines).fetchone()
        self.charger(MAINTENANT + timedelta(days=30))
        apres, apres_t = self.conn.execute(ouverts).fetchone(), self.conn.execute(termines).fetchone()
        self.assertEqual(apres[0] - avant[0], timedelta(days=30))
        self.assertEqual(apres[1] - avant[1], timedelta(days=30))
        decalage_ancre = jeu.ancre(MAINTENANT + timedelta(days=30)) - jeu.ancre(MAINTENANT)
        for a, b in zip(avant_t, apres_t):
            self.assertEqual(b - a, decalage_ancre)


if __name__ == "__main__":
    unittest.main()
