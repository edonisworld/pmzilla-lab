"""
Contrôle 16 de tools/finish_checks.py (change finish-e2e-proof-shared, tâches 2.1 à 2.3 ; conception D2, D3, D4, D7, D8, D11).

    uv run python -m unittest discover -s tests/finish_checks -v

Modèle : test_finish_checks.py et test_parite.py. Des dépôts jetables avec un dépôt distant nu ; la liste des chemins d'interface est la vraie
(tools/finish_e2e_paths.txt, copiée dans le dépôt jetable) ; l'enregistrement de bout en bout est la vraie forme (une ligne par arbre dans
pmzilla-e2e-ok du dossier Git commun). Les tests de délégation de la fin unitaire au module sont retirés avec elle (finish-single-b7-b9, B9, tâche 1.1).
"""
import unittest

from aide_depot import AvecDepot

PHRASE_REFUS = "contrôle 16 : refusé : preuve de bout en bout absente"
PHRASE_SANS_OBJET = "contrôle 16 : sans objet (chemins d'interface inchangés)"
DETAIL_1 = "Un chemin d'interface de Mothra a changé sans preuve de bout en bout pour cet arbre."
DETAIL_2 = "lancer bash tools/dbtest.sh --e2e puis relancer la fin"
DETAIL_ABSENTE = "liste des chemins d'interface absente ou illisible"
FRONT = {"mothra/front/a.ts": "x\n"}


def controle(resultat: dict, identifiant: str) -> dict:
    return next(c for c in resultat["controls"] if c["id"] == identifiant)


class Controle16Branche(AvecDepot):
    def test_chemin_d_interface_change_sans_preuve_refuse_avec_les_phrases_de_d11(self):
        self.depot.branche("feat/x", FRONT)
        code, r = self.depot.json_branche("feat/x")
        self.assertEqual(code, 1)
        c = controle(r, "16")
        self.assertEqual((c["verdict"], c["phrase"]), ("refused", PHRASE_REFUS))
        self.assertEqual(c["details"], [DETAIL_1, DETAIL_2])

    def test_config_du_serveur_package_json_et_routes_sans_preuve_refuses(self):
        # F18 (#591) : mothra/server/src/ entier et mothra/package.json sont des chemins d'interface ; les routes restent refusées
        for nom, chemin in (("feat/config", "mothra/server/src/config/exemple.ts"), ("feat/manifeste", "mothra/package.json"),
                            ("feat/routes", "mothra/server/src/routes/exemple.ts"),
                            ("feat/manifeste-serveur", "mothra/server/package.json"),
                            ("feat/tsconfig-serveur", "mothra/server/tsconfig.json")):   # R-20261103-31
            with self.subTest(chemin):
                self.depot.branche(nom, {chemin: "x\n"})
                code, r = self.depot.json_branche(nom)
                self.assertEqual(code, 1)
                c = controle(r, "16")
                self.assertEqual((c["verdict"], c["phrase"]), ("refused", PHRASE_REFUS))

    def test_chemin_d_interface_change_avec_la_ligne_du_sommet_passe(self):
        sommet = self.depot.branche("feat/x", FRONT)
        self.depot.enregistrer_e2e(self.depot.arbre(sommet))
        code, r = self.depot.json_branche("feat/x")
        self.assertEqual(code, 0)
        c = controle(r, "16")
        self.assertEqual((c["verdict"], c["phrase"], c["details"]),
                         ("pass", "contrôle 16 : passe", ["preuve de bout en bout trouvée pour l'arbre du sommet"]))

    def test_la_ligne_d_un_autre_arbre_ne_compte_pas(self):
        self.depot.branche("feat/x", FRONT)
        self.depot.enregistrer_e2e(self.depot.arbre("main"))
        code, r = self.depot.json_branche("feat/x")
        self.assertEqual((code, controle(r, "16")["verdict"]), (1, "refused"))

    def test_la_preuve_de_la_base_ne_tient_pas_lieu_de_preuve_de_bout_en_bout(self):
        sommet = self.depot.branche("feat/x", FRONT)
        self.depot.enregistrer_dbtest(self.depot.arbre(sommet))
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(controle(r, "16")["verdict"], "refused")

    def test_aucun_chemin_d_interface_change_sans_objet(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        code, r = self.depot.json_branche("feat/x")
        self.assertEqual(code, 0)
        c = controle(r, "16")
        self.assertEqual((c["verdict"], c["phrase"], c["details"]), ("exempt", PHRASE_SANS_OBJET, []))

    def test_une_entree_retiree_sur_la_branche_reste_exigee_union_avec_origin_main(self):
        # la branche retire l'entrée du front de la liste et change un fichier du front : origin/main porte encore l'entrée
        self.depot.branche("feat/x", {"tools/finish_e2e_paths.txt": "tests/e2e/\n", **FRONT})
        code, r = self.depot.json_branche("feat/x")
        self.assertEqual((code, controle(r, "16")["verdict"]), (1, "refused"))

    def test_une_liste_lisible_nulle_part_refuse_jamais_sans_objet(self):
        # dépôt sans le fichier : le module le lit à aucune révision ; même une branche qui ne change aucun chemin d'interface est refusée
        self.depot.git("rm", "-q", "tools/finish_e2e_paths.txt")
        self.depot.git("commit", "-q", "-m", "retire la liste")
        self.depot.git("push", "-q", "origin", "main")
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        code, r = self.depot.json_branche("feat/x")
        self.assertEqual(code, 1)
        c = controle(r, "16")
        self.assertEqual((c["verdict"], c["phrase"], c["details"]), ("refused", PHRASE_REFUS, [DETAIL_ABSENTE]))

    def test_les_controles_sont_dans_l_ordre_19_5_6_14_16_20(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual([c["id"] for c in r["controls"]], ["19", "5", "6", "14", "16", "20"])   # le 20 s'ajoute (finish-single-b3-b6 D13)
        self.assertEqual(r["format"], 1)

    def test_16_seul_refuse_le_code_de_sortie_est_1(self):
        self.depot.branche("feat/x", FRONT)
        code, r = self.depot.json_branche("feat/x")
        self.assertEqual(code, 1)
        self.assertEqual(self.verdicts(r), {"19": "pass", "5": "pass", "6": "exempt", "14": "exempt", "16": "refused", "20": "exempt"})

    def test_le_16_est_calcule_meme_quand_un_controle_precedent_refuse(self):
        self.depot.branche("feat/nouveau", {"openspec/changes/nouveau/p.md": "n\n", "db/001.sql": "SELECT 2;\n", **FRONT})
        _, r = self.depot.json_branche("feat/nouveau")
        self.assertEqual(self.verdicts(r), {"19": "pass", "5": "refused", "6": "exempt", "14": "refused", "16": "refused", "20": "exempt"})

    def test_meme_verdict_dans_le_texte_et_dans_le_json(self):
        self.depot.branche("feat/x", FRONT)
        code, sortie, _ = self.depot.module("branch", "feat/x")
        self.assertEqual(code, 1)
        self.assertIn("finish_checks : " + PHRASE_REFUS, sortie)
        self.assertIn("  " + DETAIL_1, sortie)
        self.assertIn("  " + DETAIL_2, sortie)
        self.assertIn("feat/x : 1 contrôle(s) refusé(s) sur 6", sortie)


class Controle16Arbre(AvecDepot):
    def lance(self, rev):
        import json
        code, sortie, _ = self.depot.module("tree", self.depot.arbre(rev), "--json")
        return code, json.loads(sortie)

    def test_le_mode_arbre_rend_les_controles_14_puis_16(self):
        sommet = self.depot.branche("feat/x", FRONT)
        code, r = self.lance(sommet)
        self.assertEqual(code, 1)
        self.assertEqual([(c["id"], c["verdict"]) for c in r["controls"]], [("14", "exempt"), ("16", "refused"), ("6", "exempt")])   # R-20261030-41 : le 6 suit (B6, D19)
        self.assertEqual(r["format"], 1)

    def test_l_ordre_des_cles_du_controle_16_est_fige_pour_la_lecture_du_train(self):
        # tools/finish_train.sh lit les détails du contrôle 16 par une expression régulière qui suppose « id, verdict, phrase, details » dans cet ordre,
        # le contrôle 16 étant le dernier du mode arbre : toute autre disposition de la sortie JSON casse cette lecture
        sommet = self.depot.branche("feat/x", FRONT)
        code, sortie, _ = self.depot.module("tree", self.depot.arbre(sommet), "--json")
        self.assertEqual(code, 1)
        self.assertRegex(sortie, r'\{"id": "16", "verdict": "refused", "phrase": "[^"]*", "details": \[.*\]\}, \{"id": "6", .*\}\], "exit": 1\}$')   # R-20261030-41 : le 6 suit le 16

    def test_le_mode_arbre_garde_le_controle_14(self):
        sommet = self.depot.branche("feat/x", {"db/001.sql": "SELECT 2;\n", **FRONT})
        self.depot.enregistrer_e2e(self.depot.arbre(sommet))
        code, r = self.lance(sommet)
        self.assertEqual(code, 1)
        self.assertEqual([(c["id"], c["verdict"]) for c in r["controls"]], [("14", "refused"), ("16", "pass"), ("6", "exempt")])   # R-20261030-41

    def test_la_ligne_d_un_autre_arbre_ne_compte_pas_en_mode_arbre(self):
        sommet = self.depot.branche("feat/x", FRONT)
        self.depot.enregistrer_e2e(self.depot.arbre("main"))
        code, r = self.lance(sommet)
        self.assertEqual((code, r["controls"][1]["verdict"]), (1, "refused"))

    def test_la_ligne_de_l_arbre_passe_en_mode_arbre(self):
        sommet = self.depot.branche("feat/x", FRONT)
        self.depot.enregistrer_e2e(self.depot.arbre(sommet))
        code, r = self.lance(sommet)
        self.assertEqual((code, r["controls"][1]["verdict"]), (0, "pass"))

    def test_aucun_chemin_d_interface_change_sans_objet_en_mode_arbre(self):
        sommet = self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        code, r = self.lance(sommet)
        self.assertEqual((code, r["controls"][1]["verdict"]), (0, "exempt"))

    def test_une_liste_absente_refuse_en_mode_arbre(self):
        self.depot.git("rm", "-q", "tools/finish_e2e_paths.txt")
        self.depot.git("commit", "-q", "-m", "retire la liste")
        self.depot.git("push", "-q", "origin", "main")
        sommet = self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        code, r = self.lance(sommet)
        self.assertEqual(code, 1)
        self.assertEqual((r["controls"][1]["verdict"], r["controls"][1]["details"]), ("refused", [DETAIL_ABSENTE]))

    def test_meme_verdict_du_16_en_mode_arbre_et_en_mode_branche_sur_le_meme_arbre(self):
        # D7, point 4 : une seule fonction pour les deux modes ; mêmes verdicts, avec et sans ligne, chemin changé ou non
        for nom, fichiers, avec_ligne in (("feat/a", FRONT, False), ("feat/b", FRONT, True), ("feat/c", {"tools/outil.sh": "un\n"}, False)):
            with self.subTest(nom):
                sommet = self.depot.branche(nom, fichiers)
                if avec_ligne:
                    self.depot.enregistrer_e2e(self.depot.arbre(sommet))
                _, branche = self.depot.json_branche(nom)
                _, arbre = self.lance(sommet)
                self.assertEqual(controle(branche, "16"), controle(arbre, "16"))

    def test_check_tree_14_reste_pour_ses_appelants(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("finish_checks_copie", self.depot.travail / "tools" / "finish_checks.py")
        module = importlib.util.module_from_spec(spec)
        import sys
        sys.path.insert(0, str(self.depot.travail / "tools"))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.remove(str(self.depot.travail / "tools"))
        sommet = self.depot.branche("feat/x", {"db/001.sql": "SELECT 2;\n"})
        r = module.check_tree_14(self.depot.travail, sommet)
        self.assertEqual([c["id"] for c in r["controls"]], ["14"])
        self.assertEqual(r["exit"], 1)


if __name__ == "__main__":
    unittest.main()
