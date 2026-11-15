"""
Contrôle 6 en mode « tree » de tools/finish_checks.py (change finish-single-b3-b6, B6, design D19) : le mode arbre rend les contrôles 14, 16 puis 6, le 6
d'un arbre suivant la même règle que celui d'une branche, l'arbre à la place du sommet et origin/main pour base ; un enregistrement avec empreinte ne vaut
que par l'empreinte calculée sur l'arbre, un enregistrement sans empreinte par l'absence de changement des fichiers évalués entre son état testé et l'arbre.
Dépôts jetables réels (aide_depot.py) ; l'empreinte est calculée par le vrai tools/posture_eval_fingerprint.py.
"""
import json
import unittest

from aide_depot import AvecDepot

CLAUDE = {"CLAUDE.md": "changé\n"}


class Controle6Arbre(AvecDepot):
    def lance(self, rev):
        code, sortie, _ = self.depot.module("tree", self.depot.arbre(rev), "--json")
        return code, json.loads(sortie)

    @staticmethod
    def c6(r):
        return next(c for c in r["controls"] if c["id"] == "6")

    def test_le_mode_arbre_rend_les_controles_14_16_puis_6(self):
        sommet = self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        code, r = self.lance(sommet)
        self.assertEqual(code, 0)
        self.assertEqual([(c["id"], c["verdict"]) for c in r["controls"]], [("14", "exempt"), ("16", "exempt"), ("6", "exempt")])

    def test_aucun_fichier_evalue_change_sans_objet(self):
        sommet = self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        _, r = self.lance(sommet)
        self.assertEqual(self.c6(r)["phrase"], "contrôle 6 : sans objet (aucun fichier évalué changé)")

    def test_fichier_evalue_change_sans_enregistrement_refuse(self):
        sommet = self.depot.branche("feat/x", CLAUDE)
        code, r = self.lance(sommet)
        self.assertEqual(code, 1)
        c = self.c6(r)
        self.assertEqual((c["verdict"], c["phrase"]), ("refused", "contrôle 6 : refusé : jeu d'essai validant absent"))
        self.assertTrue(c["details"])

    def test_enregistrement_par_empreinte_de_l_arbre_passe(self):
        sommet = self.depot.branche("feat/x", CLAUDE)
        self.depot.enregistrer_essai("2026-01-02", sommet, empreinte=self.depot.empreinte(sommet))
        code, r = self.lance(sommet)
        self.assertEqual(code, 0)
        c = self.c6(r)
        self.assertEqual(c["verdict"], "pass")
        self.assertEqual(c["details"], ["jeu d'essai validant trouvé : 2026-01-02 (1/2) (empreinte des fichiers évalués)"])

    def test_empreinte_d_un_autre_arbre_refuse(self):
        sommet = self.depot.branche("feat/x", CLAUDE)
        self.depot.enregistrer_essai("2026-01-02", sommet, empreinte="v1:" + "0" * 64)
        code, r = self.lance(sommet)
        self.assertEqual((code, self.c6(r)["verdict"]), (1, "refused"))

    def test_un_enregistrement_sans_empreinte_vaut_par_l_absence_de_changement_depuis_son_etat_teste(self):
        sommet = self.depot.branche("feat/x", CLAUDE)
        self.depot.enregistrer_essai("2026-01-02", sommet)
        code, r = self.lance(sommet)
        self.assertEqual((code, self.c6(r)["verdict"]), (0, "pass"))

    def test_un_enregistrement_sans_empreinte_d_un_autre_etat_refuse(self):
        sommet = self.depot.branche("feat/x", CLAUDE)
        self.depot.enregistrer_essai("2026-01-02", self.depot.git("rev-parse", "main"))
        code, r = self.lance(sommet)
        self.assertEqual((code, self.c6(r)["verdict"]), (1, "refused"))

    def test_meme_verdict_du_6_en_mode_arbre_et_en_mode_branche_sur_le_meme_arbre(self):
        for nom, fichiers, avec in (("feat/a", CLAUDE, False), ("feat/b", CLAUDE, True), ("feat/c", {"tools/outil.sh": "un\n"}, False)):
            with self.subTest(nom):
                sommet = self.depot.branche(nom, fichiers)
                if avec:
                    self.depot.enregistrer_essai("2026-01-02", sommet, empreinte=self.depot.empreinte(sommet))
                _, branche = self.depot.json_branche(nom)
                _, arbre = self.lance(sommet)
                self.assertEqual(self.c6(branche), self.c6(arbre))

    def test_le_texte_du_mode_arbre_dit_le_controle_6(self):
        sommet = self.depot.branche("feat/x", CLAUDE)
        code, sortie, _ = self.depot.module("tree", self.depot.arbre(sommet))
        self.assertEqual(code, 1)
        self.assertIn("finish_checks : contrôle 6 : refusé : jeu d'essai validant absent", sortie)
        self.assertIn("1 contrôle(s) refusé(s) sur 3", sortie)

    def test_l_ordre_des_cles_du_controle_6_est_fige_pour_la_lecture_du_train(self):
        # tools/finish_train.sh lit le verdict et les détails du contrôle 6 par expression régulière : « id, verdict, phrase, details » dans cet ordre,
        # le contrôle 6 étant le dernier du mode arbre
        sommet = self.depot.branche("feat/x", CLAUDE)
        _, sortie, _ = self.depot.module("tree", self.depot.arbre(sommet), "--json")
        self.assertRegex(sortie, r'\{"id": "6", "verdict": "refused", "phrase": "[^"]*", "details": \[.*\]\}\], "exit": 1\}$')


if __name__ == "__main__":
    unittest.main()
