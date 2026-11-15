"""
ci-local-runner (design D8, tâche 12.2) : la preuve `conteneur` pour `train_ready.py add` et `list --json`, sur des dépôts jetables.
`conteneur` : `ci/preuves` du dossier de données porte l'arbre avec portable, base et e2e ET pmzilla-run-mac-ok du dossier Git commun le porte aussi.
Ordre de la preuve : complete, conteneur, ciblee. Vrais enfants : l'outil, Git. Le dossier de données est celui du dépôt jetable (jamais le vrai).
Remplace : rien (preuve neuve). Retrait : tombe avec D8 ; `ciblee` tombe avec D10.
"""
import json
import sys
import unittest
from pathlib import Path

from aide_ready import AvecAuto, RACINE

sys.path.insert(0, str(RACINE / "tools"))
import train_auto_messages  # noqa: E402


class PreuveConteneur(AvecAuto):
    def arbre(self, nom):
        return self.t.git("rev-parse", "HEAD^{tree}", cwd=self.t.dossier_worktree(nom))

    def fichier_mac(self, nom):
        commun = self.t.git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=self.t.dossier_worktree(nom))
        return Path(commun) / "pmzilla-run-mac-ok"

    def ecrire_preuves(self, arbre, phases="portable,base,e2e"):
        dossier = self.t.data / "ci"
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "preuves").write_text(f"{arbre}\tcle-d-image\t{phases}\n", encoding="utf-8")

    def ecrire_mac(self, nom, arbre=None):
        self.fichier_mac(nom).write_text((arbre or self.arbre(nom)) + "\n", encoding="utf-8")

    def ecrire_branche(self, nom):
        chemin = self.t.git("rev-parse", "--path-format=absolute", "--git-path", "pmzilla-run-branch-ok", cwd=self.t.dossier_worktree(nom))
        Path(chemin).write_text(f"{self.arbre(nom)}\talpha,beta\n", encoding="utf-8")

    def refus(self, nom, code_raison):
        r = self.pret("add", nom, "--revue", "faite")
        self.assertEqual(r.code, 3, r.texte)
        self.assertIn(f"train_ready : refusée : {nom} : {train_auto_messages.label(code_raison, 'fr')}", r.texte)
        self.assertIsNone(self.octets_liste())

    def lignes_json(self):
        r = self.pret("list", "--json")
        self.assertEqual(r.code, 0, r.texte)
        return json.loads(r.sortie)["lignes"]

    def test_inscription_avec_le_conteneur_et_la_passe_mac(self):
        self.t.branche("feat/x")
        self.ecrire_preuves(self.arbre("feat/x"))
        self.ecrire_mac("feat/x")
        r = self.pret("add", "feat/x", "--revue", "faite")
        self.assertEqual(r.code, 0, r.texte)
        lignes = r.sortie.splitlines()
        self.assertEqual(lignes[-2], f"train_ready : inscrite : feat/x (sommet {self.t.sommet('feat/x')[:12]}, revue faite)")
        self.assertEqual(lignes[-1], "train_ready : preuve : conteneur et passe Mac")

    def test_message_anglais(self):
        self.t.branche("feat/x")
        self.ecrire_preuves(self.arbre("feat/x"))
        self.ecrire_mac("feat/x")
        r = self.pret("add", "feat/x", "--revue", "faite", langue="en")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(r.sortie.splitlines()[-1], "train_ready: proof: container and Mac pass")

    def test_json_d_une_ligne_prouvee_par_le_conteneur(self):
        self.t.branche("feat/x")
        self.ecrire_preuves(self.arbre("feat/x"))
        self.ecrire_mac("feat/x")
        self.assertEqual(self.pret("add", "feat/x", "--revue", "faite").code, 0)
        ligne = self.lignes_json()[0]
        self.assertEqual((ligne["preuve"], ligne["suites"], ligne["valide"]), ("conteneur", [], True))

    def test_le_conteneur_sans_la_passe_mac_est_refuse(self):
        self.t.branche("feat/x")
        self.ecrire_preuves(self.arbre("feat/x"))
        self.refus("feat/x", "empreinte")

    def test_la_passe_mac_sans_le_conteneur_est_refusee(self):
        self.t.branche("feat/x")
        self.ecrire_mac("feat/x")
        self.refus("feat/x", "empreinte")

    def test_deux_phases_sur_trois_sont_refusees(self):
        self.t.branche("feat/x")
        for phases in ("portable,base", "portable,e2e", "base,e2e", "portable"):
            with self.subTest(phases=phases):
                self.ecrire_preuves(self.arbre("feat/x"), phases)
                self.ecrire_mac("feat/x")
                self.refus("feat/x", "empreinte")

    def test_une_preuve_d_un_autre_arbre_est_refusee(self):
        self.t.branche("feat/x")
        self.ecrire_preuves(self.t.arbre("main"))
        self.ecrire_mac("feat/x", self.t.arbre("main"))
        self.refus("feat/x", "sans-empreinte")

    def test_un_commit_de_plus_perime_la_preuve(self):
        self.t.branche("feat/x")
        self.ecrire_preuves(self.arbre("feat/x"))
        self.ecrire_mac("feat/x")
        self.commit_dans("feat/x", {"tools/autre.sh": "a\n"})
        self.refus("feat/x", "sans-empreinte")

    def test_ligne_mal_formee_de_preuves_n_est_pas_une_preuve(self):
        self.t.branche("feat/x")
        (self.t.data / "ci").mkdir(parents=True, exist_ok=True)
        (self.t.data / "ci" / "preuves").write_text(f"{self.arbre('feat/x')}\tportable,base,e2e\n", encoding="utf-8")   # deux champs seulement
        self.ecrire_mac("feat/x")
        self.refus("feat/x", "empreinte")

    def test_le_runner_complet_est_prefere_au_conteneur(self):
        self.preparer("feat/x")
        self.ecrire_preuves(self.arbre("feat/x"))
        self.ecrire_mac("feat/x")
        r = self.pret("add", "feat/x", "--revue", "faite")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(r.sortie.splitlines()[-1], "train_ready : preuve : runner complet")
        self.assertEqual(self.lignes_json()[0]["preuve"], "complete")

    def test_le_conteneur_est_prefere_a_l_empreinte_de_branche(self):
        self.t.branche("feat/x")
        self.ecrire_branche("feat/x")
        self.ecrire_preuves(self.arbre("feat/x"))
        self.ecrire_mac("feat/x")
        r = self.pret("add", "feat/x", "--revue", "faite")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(r.sortie.splitlines()[-1], "train_ready : preuve : conteneur et passe Mac")
        ligne = self.lignes_json()[0]
        self.assertEqual((ligne["preuve"], ligne["suites"]), ("conteneur", []))

    def test_l_empreinte_de_branche_reste_une_preuve_derriere_le_conteneur(self):
        self.t.branche("feat/x")
        self.ecrire_branche("feat/x")
        r = self.pret("add", "feat/x", "--revue", "faite")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(r.sortie.splitlines()[-1], "train_ready : preuve : suites de la branche (2)")


if __name__ == "__main__":
    unittest.main()
