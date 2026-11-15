"""
Tests de la lecture par fichier du lecteur de la file (tools/roadmap.py, option --issues-json) : niveau 2 du bac à sable, tâche 7.9
(R-20261109-12, réponse 1). Sous le bac à sable, gh n'a aucun réseau : le lecteur lit les issues et les jalons dans le fichier que la
sous-commande `list` de l'outil d'écriture écrit (--sortie), sans jamais appeler gh. Le faux gh est celui de tests/roadmap : tout appel
est noté dans son journal, et ces tests exigent un journal vide ; la fonction qui lance gh est de plus remplacée par une fonction qui fait
échouer le test si elle est appelée.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/roadmap -q -f
"""
import json
import unittest
from unittest import mock

import roadmap
import roadmap_model as rm
from test_roadmap_github import Base, feature, sous_issue


class LectureParFichier(Base):
    def setUp(self):
        super().setUp()

        def interdit(*args, **kwargs):
            raise AssertionError("gh appelé alors que --issues-json est donné")

        for nom in ("appelle_gh", "lecture_github"):
            q = mock.patch.object(roadmap, nom, interdit)
            q.start()
            self.addCleanup(q.stop)
        self.fichier = self.dir / "issues-lues.json"

    def ecrit(self, *noeuds, jalons=None, avec_jalons=True):
        """Le fichier de la sous-commande `list` : issues normalisées et jalons {titre: état}."""
        issues = [roadmap.normalise(n) for n in noeuds]
        contenu = {"date": "2026-10-11", "issues": issues}
        if avec_jalons:
            contenu["milestones"] = jalons if jalons is not None else {i["milestone"]["title"]: i["milestone"]["state"]
                                                                       for i in issues if i["milestone"]}
        self.fichier.write_text(json.dumps(contenu), encoding="utf-8")

    def lance_fichier(self, *args):
        return self.lance(*args, "--issues-json", str(self.fichier))

    def test_check_lit_le_fichier_sans_appeler_gh(self):
        self.ecrit(feature(1, status="Done", state="CLOSED", milestone="Tarasque", milestone_state="CLOSED",
                           bloc={"done_on": "2026-10-01"}),
                   feature(2, blocked_by=[101]), feature(3, status="Todo"))
        code, sortie, erreur = self.lance_fichier("check")
        self.assertEqual(code, 0, sortie + erreur)
        self.assertEqual(self.appels(), [])

    def test_next_propose_les_features_du_fichier(self):
        self.ecrit(feature(1, bloc={"estimate": "1h"}), feature(2, bloc={"estimate": "30min"}))
        code, sortie, _ = self.lance_fichier("next", "--budget", "2h", "--today", "2026-10-12")
        self.assertEqual(code, 0, sortie)
        self.assertIn("R-1 |", sortie)
        self.assertIn("R-2 |", sortie)
        self.assertEqual(self.appels(), [])

    def test_status_et_show_lisent_le_fichier(self):
        self.ecrit(feature(1, status="In progress", bloc={"started_on": "2026-10-10"}), feature(2, status="Ready"),
                   sous_issue(1, 1, 101))
        code, sortie, _ = self.lance_fichier("status")
        self.assertEqual(code, 0, sortie)
        self.assertIn("ready 1", sortie)
        self.assertIn("in-progress 1", sortie)
        code, sortie, _ = self.lance_fichier("show", "R-1")
        self.assertEqual(code, 0, sortie)
        self.assertIn("R-1/g1 | ", sortie)
        self.assertEqual(self.appels(), [])

    def test_release_notes_lit_le_fichier(self):
        self.ecrit(feature(1, milestone="Hydra"))            # une feature ouverte : aucune note, donc aucune garde de noms à charger
        code, sortie, erreur = self.lance_fichier("release-notes", "--milestone", "Hydra")
        self.assertEqual(code, 0, sortie + erreur)
        self.assertIn("not listed: 1 open feature(s)", erreur)
        self.assertEqual(self.appels(), [])

    def test_batch_lit_les_jalons_du_fichier_et_n_appelle_pas_gh(self):
        self.ecrit(feature(1), jalons={"Hydra": "open"})
        code, _, erreur = self.lance_fichier("batch", "--milestone", "Inconnu", "--today", "2026-10-12")
        self.assertEqual(code, 2)
        self.assertIn("unknown milestone Inconnu", erreur)
        code, _, erreur = self.lance_fichier("batch", "--milestone", "Hydra", "--today", "2026-10-12")
        self.assertNotIn("GitHub unreachable", erreur)
        self.assertEqual(self.appels(), [])

    def test_jalon_ferme_du_fichier_refuse_le_lot(self):
        self.ecrit(feature(1, status="Done", state="CLOSED", milestone="Tarasque", milestone_state="CLOSED",
                           bloc={"done_on": "2026-10-01"}), jalons={"Tarasque": "closed"})
        code, _, erreur = self.lance_fichier("batch", "--milestone", "Tarasque", "--today", "2026-10-12")
        self.assertEqual(code, 2)
        self.assertIn("closed milestone Tarasque", erreur)

    def test_fichier_sans_jalons_les_tire_des_issues(self):
        self.ecrit(feature(1, milestone="Hydra"), avec_jalons=False)
        code, _, erreur = self.lance_fichier("batch", "--milestone", "Hydra", "--today", "2026-10-12")
        self.assertNotIn("unknown milestone", erreur)

    def test_le_fichier_prime_sur_l_instantane_et_sur_origin(self):
        self.origin = ""            # sans origin : la lecture par fichier ne le résout pas
        instantane = self.cache()
        instantane.parent.mkdir(parents=True)
        instantane.write_text(json.dumps({"date": "2026-01-01", "issues": [roadmap.normalise(feature(9, status="Ready"))],
                                          "milestones": {"Hydra": "open"}}), encoding="utf-8")
        avant = instantane.read_text(encoding="utf-8")
        self.ecrit(feature(1, bloc={"estimate": "1h"}))
        code, sortie, _ = self.lance_fichier("next", "--budget", "2h", "--today", "2026-10-12")
        self.assertEqual(code, 0, sortie)
        self.assertIn("R-1 |", sortie)
        self.assertNotIn("R-9", sortie)
        self.assertEqual(instantane.read_text(encoding="utf-8"), avant)      # l'instantané n'est ni lu ni réécrit

    def test_aucun_instantane_ecrit(self):
        self.ecrit(feature(1))
        self.assertEqual(self.lance_fichier("check", "--today", "2026-10-11")[0], 0)
        self.assertFalse(self.cache().exists())

    def test_fichier_absent_code_2(self):
        code, _, erreur = self.lance("check", "--issues-json", str(self.dir / "absent.json"))
        self.assertEqual(code, 2)
        self.assertIn("--issues-json", erreur)
        self.assertEqual(self.appels(), [])

    def test_fichier_mal_forme_code_2(self):
        for contenu in ("pas du json", "[]", json.dumps({"issues": "x"}), json.dumps({"date": "2026-10-11"})):
            self.fichier.write_text(contenu, encoding="utf-8")
            self.assertEqual(self.lance_fichier("check")[0], 2, contenu)

    def test_une_issue_qui_n_a_pas_les_dix_cles_code_2(self):
        """R5 : chaque issue du fichier porte les dix clés de normalise_node ; une clé absente, ou une entrée qui n'est pas un objet, donne 2."""
        complete = roadmap.normalise(feature(1, status="Ready"))
        self.assertEqual(set(complete), set(rm.ISSUE_KEYS))
        self.assertEqual(len(rm.ISSUE_KEYS), 10)
        for cle in rm.ISSUE_KEYS:
            with self.subTest(cle=cle):
                incomplete = {k: v for k, v in complete.items() if k != cle}
                self.fichier.write_text(json.dumps({"date": "2026-10-11", "issues": [incomplete], "milestones": {"Hydra": "open"}}), encoding="utf-8")
                self.assertEqual(self.lance_fichier("check")[0], 2)
        self.fichier.write_text(json.dumps({"date": "2026-10-11", "issues": [complete, "texte"], "milestones": {"Hydra": "open"}}), encoding="utf-8")
        self.assertEqual(self.lance_fichier("check")[0], 2)
        self.assertEqual(self.appels(), [])


class SansOption(Base):
    def test_sans_l_option_la_lecture_reste_celle_de_gh(self):
        """Contrôle : sans --issues-json, le lecteur appelle bien gh (le faux journalisé) : rien n'est changé pour lui."""
        self.depot(feature(1))
        self.assertEqual(self.lance("check", "--today", "2026-10-11")[0], 0)
        self.assertTrue(self.appels())
        self.assertTrue(self.cache().is_file())

    def test_les_alias_du_modele_partage(self):
        self.assertIs(roadmap.REQUETE, rm.GRAPHQL_ISSUES_QUERY)
        noeud = feature(1, status="Ready")
        self.assertEqual(roadmap.normalise(noeud), rm.normalise_node(noeud, roadmap.PROJECT_TITLE))


if __name__ == "__main__":
    unittest.main()
