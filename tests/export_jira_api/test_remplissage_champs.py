"""R-142/u1 : fields --project <clé> --field <identifiant> compte les tickets où chaque champ est rempli.
    bash tests/run_all.sh export_jira_api </dev/null

Faux serveur et données inventées de test_export_jira_api.py. Sentinelles : aucune valeur de champ ni aucune clé de ticket dans la sortie.
"""
from __future__ import annotations

from unittest import mock

from test_export_jira_api import Base, CHAMP, EMAIL, JETON, ex

SENTINELLE = "SENTINELLE_SECRETE"


class Remplissage(Base):
    def setUp(self):
        super().setUp()
        self.faux.champs.append({"id": "components", "name": "Components", "custom": False})
        t = self.faux.tickets
        t["ABC-1"]["components"] = [{"name": SENTINELLE}]
        t["ABC-2"]["components"] = []
        t["ABC-3"]["components"] = None
        t["ABC-9"]["components"] = [{"name": SENTINELLE}, {"name": SENTINELLE + "2"}]
        t["ABC-1"]["customfield_10003"] = 5
        t["ABC-2"]["customfield_10003"] = ""
        t["ABC-3"]["customfield_10003"] = 0           # 0 est une valeur remplie

    def verifier_sobre(self, sortie: str):
        for interdit in (SENTINELLE, "ABC-", "Equipe A", "Equipe B", "Titre secret", JETON, EMAIL, self.url):
            self.assertNotIn(interdit, sortie)

    def test_comptes_justes_pour_un_champ_personnalise(self):
        code, sortie = self.lancer("fields", "--project", "ABC", "--field", CHAMP)
        self.assertEqual(code, 0, sortie)
        lignes = sortie.splitlines()
        self.assertIn("4 ticket(s) du projet ABC", lignes[0])
        self.assertEqual(lignes[1:], [f"  {CHAMP}  [G] Team/s  3/4"])        # ABC-3 a une liste vide
        self.verifier_sobre(sortie)

    def test_components_champ_systeme(self):
        code, sortie = self.lancer("fields", "--project", "ABC", "--field", "components")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sortie.splitlines()[1:], ["  components  Components  2/4"])      # liste vide et None : non remplis
        self.verifier_sobre(sortie)

    def test_champs_systeme_de_version_admis(self):
        # Décision de l'auteur du 2026-10-28 : fixVersions et versions (objets de version) sont admis.
        self.faux.champs.append({"id": "fixVersions", "name": "Fix versions", "custom": False})
        self.faux.champs.append({"id": "versions", "name": "Affects versions", "custom": False})
        t = self.faux.tickets
        t["ABC-1"]["fixVersions"] = [{"name": SENTINELLE + "V"}]
        t["ABC-2"]["fixVersions"] = []
        t["ABC-1"]["versions"] = [{"name": SENTINELLE + "V"}, {"name": SENTINELLE + "W"}]
        t["ABC-3"]["versions"] = [{"id": "7"}]
        code, sortie = self.lancer("fields", "--project", "ABC", "--field", "fixVersions", "--field", "versions")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sortie.splitlines()[1:], ["  fixVersions  Fix versions  1/4", "  versions  Affects versions  2/4"])
        self.assertEqual(self.faux.requetes[0]["fields"], ["fixVersions", "versions"])
        self.verifier_sobre(sortie)

    def test_motif_admis_et_refus_des_autres_champs_systeme(self):
        for ok in ("fixVersions", "versions", "components", "customfield_10003"):
            self.assertTrue(ex.CHAMP_ADMIS.fullmatch(ok), ok)
        for ko in ("assignee", "reporter", "fixversions", "version", "fixVersions2"):
            code, sortie = self.lancer_sans_jeton_ni_appel("fields", "--project", "ABC", "--field", ko)
            self.assertEqual(code, 1, ko)
            self.assertIn(ko, sortie)
            self.assertIn("fixVersions et versions", sortie)       # le message cite la nouvelle liste admise

    def test_plusieurs_champs_dans_l_ordre_demande_sans_doublon(self):
        code, sortie = self.lancer("fields", "--project", "ABC", "--field", "customfield_10003", "--field", "components",
                                   "--field", "customfield_10003")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sortie.splitlines()[1:], ["  customfield_10003  Story Points  2/4", "  components  Components  2/4"])
        self.assertEqual(self.faux.requetes[0]["fields"], ["customfield_10003", "components"])     # rien d'autre n'est demandé
        self.verifier_sobre(sortie)

    def test_echantillon_borne_et_declare(self):
        with mock.patch.object(ex, "ECHANTILLON_REMPLISSAGE", 3):
            code, sortie = self.lancer("fields", "--project", "ABC", "--field", "components")
        self.assertEqual(code, 0, sortie)
        self.assertIn("3 ticket(s) du projet ABC (les 3 derniers créés au plus)", sortie.splitlines()[0])
        self.assertTrue(sortie.splitlines()[1].endswith("/3"))
        self.assertEqual(self.faux.requetes[0]["maxResults"], 3)
        self.assertIn("ORDER BY created DESC", self.faux.requetes[0]["jql"])

    def test_echantillon_borne_sur_plusieurs_pages(self):
        self.faux.taille_page = 1
        with mock.patch.object(ex, "ECHANTILLON_REMPLISSAGE", 2):
            code, sortie = self.lancer("fields", "--project", "ABC", "--field", "components")
        self.assertEqual(code, 0, sortie)
        self.assertIn("2 ticket(s)", sortie.splitlines()[0])
        self.assertEqual(len(self.faux.requetes), 2)

    def test_projet_inconnu_ne_montre_que_le_code(self):
        self.faux.projets = {"ABC"}
        code, sortie = self.lancer("fields", "--project", "ZZZ", "--field", "components")
        self.assertEqual((code, sortie.strip()), (1, "HTTP 400"))

    def lancer_sans_jeton_ni_appel(self, *argv):
        """Lance la commande avec un trousseau espion : il ne doit jamais être lu, et le faux serveur ne reçoit aucun appel."""
        jeton = mock.Mock(return_value=JETON)
        with mock.patch.object(ex.hj, "lire_jeton", jeton):
            code, sortie = self.lancer(*argv)
        jeton.assert_not_called()
        self.assertEqual(self.faux.appels, [])
        return code, sortie

    def test_cle_de_projet_invalide_refusee_avant_jeton_et_appel(self):
        for cle in ('A" OR 1=1 --', "1ABC", "A B", "A" * 51):
            code, sortie = self.lancer_sans_jeton_ni_appel("fields", "--project", cle, "--field", "components")
            self.assertEqual(code, 1, cle)
            self.assertIn("--project : donner une clé de projet", sortie)
        self.assertEqual(self.faux.requetes, [])

    def test_cle_de_projet_de_50_caracteres_admise(self):
        code, sortie = self.lancer("fields", "--project", "A" * 50, "--field", "components")
        self.assertEqual(code, 0, sortie)

    def test_champ_vide_ou_d_espaces_refuse_avant_jeton_et_appel(self):
        for champ in ("", "   "):
            code, sortie = self.lancer_sans_jeton_ni_appel("fields", "--project", "ABC", "--field", champ)
            self.assertEqual(code, 1, repr(champ))
            self.assertIn("--field", sortie)
            self.assertNotIn("Traceback", sortie)

    def test_champs_hors_liste_admise_refuses_avant_jeton_et_appel(self):
        for champ in ("summary", "assignee", "description", "comment", "customfield_", "customfield_abc", "watches"):
            code, sortie = self.lancer_sans_jeton_ni_appel("fields", "--project", "ABC", "--field", champ)
            self.assertEqual(code, 1, champ)
            self.assertIn(champ, sortie)

    def test_customfield_de_personne_refuse_sans_lire_de_ticket(self):
        self.faux.champs.append({"id": "customfield_20001", "name": "Approver", "custom": True, "schema": {"type": "user"}})
        self.faux.champs.append({"id": "customfield_20002", "name": "Reviewers", "custom": True,
                                 "schema": {"type": "array", "items": "user"}})
        for champ in ("customfield_20001", "customfield_20002"):
            code, sortie = self.lancer("fields", "--project", "ABC", "--field", "components", "--field", champ)
            self.assertEqual(code, 1, champ)
            self.assertIn(champ, sortie)
            self.assertNotIn("Approver", sortie)
        self.assertEqual(self.faux.requetes, [])
        self.assertNotIn("POST", {m for m, _ in self.faux.appels})

    def test_est_rempli(self):
        for valeur, attendu in ((None, False), ("", False), ("   ", False), ("x", True), ([], False), ([1], True),
                                ({}, False), ({"value": "x"}, True), ({"name": "x"}, True), ({"id": "1"}, True),
                                ({"autre": "x"}, False), ({"value": ""}, False),
                                ({"type": "doc", "content": []}, False),
                                ({"type": "doc", "version": 1, "content": [{"type": "paragraph"}]}, True),
                                (False, True), (True, True), (0, True)):
            self.assertEqual(ex.est_rempli(valeur), attendu, repr(valeur))

    def test_pagination_jeton_repete_arrete_la_lecture(self):
        self.faux.taille_page = 1
        self.faux.jeton_repete = True
        code, sortie = self.lancer("fields", "--project", "ABC", "--field", "components")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(len(self.faux.requetes), 2)
        self.assertIn("2 ticket(s)", sortie.splitlines()[0])

    def test_pagination_page_vide_avec_jeton_arrete_la_lecture(self):
        pages = iter([{"issues": [{"fields": {"components": [{"name": "x"}]}}], "nextPageToken": "a"},
                      {"issues": [], "nextPageToken": "b"}])
        appels = []

        def json(client, methode, chemin, **kwargs):
            if methode == "GET":
                return [{"id": "components", "name": "Components"}]
            appels.append(kwargs["json"])
            return next(pages)

        with mock.patch.object(ex.hj.Client, "json", json):
            code, sortie = self.lancer("fields", "--project", "ABC", "--field", "components")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(len(appels), 2)
        self.assertEqual(sortie.splitlines()[1:], ["  components  Components  1/1"])

    def test_liste_des_champs_inattendue_dans_la_voie_comptage(self):
        with mock.patch.object(ex.hj.Client, "json", lambda *a, **k: {"inattendu": True}):
            code, sortie = self.lancer("fields", "--project", "ABC", "--field", "components")
        self.assertEqual(code, 1)
        self.assertIn("réponse de Jira inattendue pour la liste des champs", sortie)

    def test_maxresults_de_la_deuxieme_page(self):
        self.faux.taille_page = 1
        with mock.patch.object(ex, "ECHANTILLON_REMPLISSAGE", 3):
            code, sortie = self.lancer("fields", "--project", "ABC", "--field", "components")
        self.assertEqual(code, 0, sortie)
        self.assertEqual([r["maxResults"] for r in self.faux.requetes], [3, 2, 1])

    def test_adf_vide_et_objet_sans_valeur_non_remplis(self):
        t = self.faux.tickets
        t["ABC-1"]["customfield_10003"] = {"type": "doc", "content": []}
        t["ABC-2"]["customfield_10003"] = {"autre": "x"}
        t["ABC-3"]["customfield_10003"] = {"value": "x"}
        t["ABC-9"]["customfield_10003"] = {"type": "doc", "content": [{"type": "paragraph"}]}
        code, sortie = self.lancer("fields", "--project", "ABC", "--field", "customfield_10003")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sortie.splitlines()[1:], ["  customfield_10003  Story Points  2/4"])

    def test_champ_inconnu_refuse_sans_lire_de_ticket(self):
        code, sortie = self.lancer("fields", "--project", "ABC", "--field", "components", "--field", "customfield_99999")
        self.assertEqual(code, 1)
        self.assertIn("customfield_99999", sortie)
        self.assertNotIn("components", sortie)
        self.assertEqual(self.faux.requetes, [])

    def test_options_incompletes_ou_combinees_refusees(self):
        for argv in (("--project", "ABC"), ("--field", "components"), ("--search", "team", "--project", "ABC", "--field", "components")):
            with self.assertRaises(SystemExit) as arret:
                with mock.patch("sys.stderr"):
                    ex.main(["fields", *argv])
            self.assertEqual(arret.exception.code, 2, argv)
        self.assertEqual(self.faux.requetes, [])

    def test_aucune_ecriture_et_anglais(self):
        code, sortie = self.lancer("fields", "--project", "ABC", "--field", "components", "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Sample: 4 ticket(s) of project ABC", sortie)
        self.assertEqual({m for m, _ in self.faux.appels}, {"GET", "POST"})
        self.verifier_sobre(sortie)
