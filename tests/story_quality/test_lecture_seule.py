"""Collecte des stories en lecture seule et garde du périmètre (change jira-read-only-client) : sondes réelles contre un faux serveur local,
refus codes 5 et 6 sur la sortie d'erreur, filtre des réponses.

    bash tests/run_all.sh story_quality

Faux restants (design D6), déclarés ici : le jeton (JETON, `lire_jeton` remplacé), le magasin du schéma quality en mémoire, le dossier
personnel et la liste des noms sensibles temporaires, la passerelle (`API_ATLASSIAN`) qui pointe sur la machine locale en HTTP simple. Le
réseau, lui, est réel : le faux serveur journalise chaque requête reçue avant tout contrôle. Clés fictives seulement (ZZA, ZZB, ZZC, SUPX).
"""
import re
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from unittest import mock  # noqa: E402

import story_quality_collect as collect  # noqa: E402
from aide_story_quality import (CHAMP_CRITERES, REGLAGES_COLLECTE, REQUETE_A, REQUETE_B, EspaceCollecte, hj,  # noqa: E402
                                ticket)

RECHERCHE = "/rest/api/3/search/jql"
# Paires que les sondes de cette suite doivent voir exactement : tests/history_jira/test_lecture_seule.py les reprend (PAIRES_QUALITE).
PAIRES_ATTENDUES = {("GET", "/rest/api/3/field"), ("POST", RECHERCHE)}


class Sondes(EspaceCollecte):
    def test_sondes_de_collect(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1"))
        vues = set()
        for argv in (("collect",), ("collect", "--query", "alpha")):
            self.faux.brut.clear()
            code, _, erreur = self.lancer(*argv)
            self.assertEqual(code, 0, erreur)
            self.assertTrue(self.faux.brut, "aucune requête reçue")
            for methode, chemin, auth in self.faux.brut:
                api = urlparse(chemin).path[len(self.faux.prefixe):]
                self.assertTrue(auth and chemin.startswith(self.faux.prefixe + "/"), chemin)
                self.assertTrue(any(m == methode and re.fullmatch(p, api) for m, p, _ in hj.lectures_autorisees()), (methode, api))
                vues.add((methode, api))
        self.assertEqual(vues, PAIRES_ATTENDUES)


class Refus(EspaceCollecte):
    def test_refus_pendant_la_collecte_code_5_phrase_sur_la_sortie_d_erreur_rien_de_stocke(self):
        def ecriture(client, jql, champs, une_page=False):
            return client.requete("PUT", "/rest/api/3/issue/ZZA-1/changelog")
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1"))
        with mock.patch.object(collect.eja, "interroger", ecriture):
            code, sortie, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 5, erreur)
        self.assertIn("Jira request refused: write forbidden (PUT)", erreur)
        self.assertEqual((self.magasin.elements, self.magasin.contenus, self.magasin.ecritures), ({}, {}, 0))
        self.assertEqual([m for m, _, _ in self.faux.brut if m not in ("GET", "POST")], [])

    def test_requete_non_restreinte_code_6_aucune_recherche_rien_de_stocke(self):
        self.ecrire_reglages(bloc=REGLAGES_COLLECTE.format(a="status = Done", b=REQUETE_B, criteres=CHAMP_CRITERES))
        code, sortie, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 6, erreur)
        self.assertIn("Jira request refused: outside the declared scope projects", erreur)
        self.assertEqual((self.magasin.elements, self.magasin.ecritures), ({}, 0))
        self.assertEqual([c for _, c, _ in self.faux.brut if RECHERCHE in c], [])
        code, _, erreur = self.lancer("collect")
        self.assertIn("requête Jira refusée : hors des projets déclarés du périmètre", erreur)

    def test_liste_des_projets_refuses_absente_ou_vide_code_6_aucune_requete(self):
        for garde in (["scope_projects: [ZZA, ZZB]"], ["scope_projects: [ZZA, ZZB]", "forbidden_projects: []"],
                      ["scope_projects: [ZZA, ZZB]", "forbidden_projects: SUPX"]):
            self.ecrire_reglages(garde=garde)
            self.faux.brut.clear()
            code, sortie, erreur = self.lancer("collect", "--language", "en")
            self.assertEqual(code, 6, erreur)
            self.assertIn("Jira request refused: setting missing, empty or unreadable (forbidden_projects)", erreur)
            self.assertEqual((self.magasin.elements, self.faux.brut), ({}, []))
            self.assertNotIn("SUPX", erreur)

    def test_liste_des_projets_declares_absente_code_6(self):
        self.ecrire_reglages(garde=["forbidden_projects: [SUPX]"])
        code, _, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 6, erreur)
        self.assertIn("setting missing, empty or unreadable (scope_projects)", erreur)
        self.assertEqual(self.faux.brut, [])


class Perimetre(EspaceCollecte):
    def test_story_d_un_autre_projet_ni_stockee_ni_imprimee_ligne_de_compte(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1"), ticket("ZZC-7", titre="Titre zzretire"))
        code, sortie, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(set(self.magasin.elements), {"ZZA-1"})
        self.assertIn("tickets outside the declared projects set aside: 1", sortie)
        for texte in (sortie, erreur, repr(self.magasin.contenus)):
            self.assertNotIn("ZZC", texte)
            self.assertNotIn("zzretire", texte)
        code, sortie, _ = self.lancer("collect")
        self.assertIn("tickets hors des projets déclarés écartés : 1", sortie)

    def test_aucun_ticket_ecarte_aucune_ligne(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1"))
        code, sortie, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertNotIn("set aside", sortie)

    def test_parent_du_projet_refuse_retire_aucune_cle_stockee(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1", parent="SUPX-2"))
        code, sortie, erreur = self.lancer("collect")
        self.assertEqual(code, 0, erreur)
        self.assertNotIn("SUPX", sortie + erreur + repr(self.magasin.elements) + repr(self.magasin.contenus))


if __name__ == "__main__":
    unittest.main()
