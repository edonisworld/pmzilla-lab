"""
Niveau 2 du bac à sable de Bash, tâche 7.4 (design D5, réserve C-r4) : après un train fusionné et poussé, quand le train change un fichier de la liste fermée des outils
figés et que le dossier outils-figes du dossier de données existe, le train copie les fichiers figés depuis le commit du sommet du train (git show) dans un
dossier de préparation, y réécrit leur relevé avec le script de copie du même commit, puis échange les dossiers (R1 de la revue) ; sans dossier, ou sans fichier
figé changé, il ne fait ni ne dit rien ; une préparation qui échoue est une cause du code 75, le dossier réel restant entier, avec son geste de reprise.
Dépôts jetables réels (aide commune de tests/finish_train) ; la liste fermée du dépôt jetable est courte : une enveloppe et une dépendance.
"""
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain, OUTILS  # noqa: E402

LISTE = "E ci_local.sh\nC tools/dependance.py\n"
PHRASE = "finish_train : outils figés rafraîchis"
OUI_OUI = "o\no\n"   # R-20261110-03 : « o » à la question d'arrivée, puis « o » à la question du rafraîchissement


def sha(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


class OutilsFiges(AvecTrain):
    def prepare(self, dossier=True, conf=True):
        """Pose dans main (poussé, dossier d'exécution à jour) la liste, le script de copie réel, l'enveloppe et la dépendance ; crée le dossier."""
        copie = (OUTILS / "outils_figes" / "rafraichir.sh").read_text(encoding="utf-8")
        self.t.commit_main({"tools/outils_figes/liste.txt": LISTE, "tools/outils_figes/rafraichir.sh": copie,
                            "tools/outils_figes/ci_local.sh": "enveloppe v1\n", "tools/dependance.py": "dependance v1\n"},
                           "outils figés", pousser=True)
        self.t.mettre_a_jour_run()
        self.dest = self.t.data / "outils-figes"
        if dossier:
            self.dest.mkdir(parents=True)
            if conf:
                (self.dest / "dossiers.conf").write_text("maison=/m\n", encoding="utf-8")

    def releve(self) -> dict:
        lignes = (self.dest / "empreintes.sha256").read_text(encoding="utf-8").splitlines()
        return {l.split("  ", 1)[1]: l.split("  ", 1)[0] for l in lignes}

    def test_un_fichier_figé_change_les_copies_et_le_relevé_sont_réécrits(self):
        self.prepare()
        self.t.branche("feat/x", {"tools/dependance.py": "dependance v2\n"})
        r = self.t.lance("feat/x", entree=OUI_OUI)   # R-20261110-03 : la question d'arrivée, puis celle du rafraîchissement
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, PHRASE)
        self.assertEqual((self.dest / "copie" / "tools" / "dependance.py").read_text(encoding="utf-8"), "dependance v2\n")
        self.assertEqual((self.dest / "ci_local.sh").read_text(encoding="utf-8"), "enveloppe v1\n")
        releve = self.releve()
        self.assertEqual(releve["copie/tools/dependance.py"], sha(self.dest / "copie" / "tools" / "dependance.py"))
        self.assertEqual(set(releve), {"ci_local.sh", "copie/tools/dependance.py", "dossiers.conf"})
        self.assertEqual(sorted(p.name for p in self.dest.parent.glob("outils-figes.*")), [])     # ni préparation ni ancien dossier laissés

    def test_une_enveloppe_changée_est_recopiée(self):
        self.prepare()
        self.t.branche("feat/x", {"tools/outils_figes/ci_local.sh": "enveloppe v2\n"})
        r = self.t.lance("feat/x", entree=OUI_OUI)
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, PHRASE)
        self.assertEqual((self.dest / "ci_local.sh").read_text(encoding="utf-8"), "enveloppe v2\n")

    def test_la_liste_changée_declenche_la_copie(self):
        self.prepare()
        self.t.branche("feat/x", {"tools/outils_figes/liste.txt": LISTE + "C tools/autre.py\n", "tools/autre.py": "autre\n"})
        r = self.t.lance("feat/x", entree=OUI_OUI)
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, PHRASE)
        self.assertIn("copie/tools/autre.py", self.releve())

    def test_un_train_sans_fichier_figé_ne_dit_ni_ne_fait_rien(self):
        self.prepare()
        self.t.branche("feat/x", {"tools/sans_rapport.sh": "x\n"})
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.absent(r, "outils figés")
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["dossiers.conf"])

    def test_sans_dossier_des_outils_figes_rien_n_est_dit(self):
        self.prepare(dossier=False)
        self.t.branche("feat/x", {"tools/dependance.py": "dependance v2\n"})
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.absent(r, "outils figés")
        self.assertFalse(self.dest.exists())

    def test_la_copie_en_échec_est_une_cause_du_code_75(self):
        self.prepare(conf=False)                                   # sans dossiers.conf, le script de copie rend 4
        self.t.branche("feat/x", {"tools/dependance.py": "dependance v2\n"})
        r = self.t.lance("feat/x", entree=OUI_OUI)
        self.assertEqual(r.code, 75, r.texte)
        self.contient(r, "finish_train : outils figés non rafraîchis (code 4)", "train fusionné et poussé, fin incomplète",
                      "geste de reprise : le fichier d'étape de copie")
        self.assertFalse((self.dest / "copie").exists())
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), [])                          # le dossier réel est resté tel quel
        self.assertEqual(sorted(p.name for p in self.dest.parent.glob("outils-figes.*")), [])     # la préparation est retirée

    def test_lecture_du_script_la_copie_vient_du_commit_et_precede_le_dossier_d_execution(self):
        """R1, lecture statique : les fichiers viennent de `git show <sommet>:<chemin>`, la préparation (liste des changements comprise) précède la mise à jour du
        dossier d'exécution et l'échange la suit ; aucune commande Git dans l'échange."""
        texte = (OUTILS / "finish_train.sh").read_text(encoding="utf-8")
        self.assertIn('git -C "$WS" show "$1:$2"', texte)
        apres = texte[texte.index("after_push() {"):]
        self.assertLess(apres.index("frozen_prepare"), apres.index("update_run_tree"))
        self.assertLess(apres.index("update_run_tree"), apres.index("frozen_swap"))
        echange = texte[texte.index("frozen_swap() {"):]
        echange = echange[:echange.index("\n}\n")]
        self.assertNotIn("git ", echange)

    def test_un_essai_ou_une_reponse_non_ne_copie_rien(self):
        self.prepare()
        self.t.branche("feat/x", {"tools/dependance.py": "dependance v2\n"})
        for args, entree in ((("--essai", "feat/x"), ""), (("feat/x",), "n\n")):
            r = self.t.lance(*args, entree=entree)
            self.assertEqual(r.code, 0, r.texte)
            self.absent(r, "outils figés")
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["dossiers.conf"])


if __name__ == "__main__":
    unittest.main()
