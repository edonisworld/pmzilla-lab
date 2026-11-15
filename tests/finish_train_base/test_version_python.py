"""
Faux 65 du train automatique (design D3) : la garde de version de tools/finish_train.sh. Après le contrôle d'usage et avant le premier appel
de `python3` des étapes, le train vérifie que `python3` existe dans le PATH et vaut 3.10 ou plus ; sinon il refuse en 76, étape « version de python3 »,
sans lancer d'autre commande `python3`, sans rien fusionner.
"""
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain  # noqa: E402

PHRASE = "calcul impossible (python3 3.10 ou plus introuvable) ; rien n'est fusionné"
BANNIERE = "===== arrêt à version de python3 : rien n'est fusionné ====="
# ce que le train lance avant la garde (résolution des dossiers du lab, journal) ; le faux PATH « sans python3 » ne porte que ces outils
OUTILS_SYSTEME = ("git", "dirname", "basename", "cat", "rm", "mktemp", "mkfifo", "tee", "sleep", "pkill", "date", "mkdir", "readlink", "sort",
                  "tr", "sed", "awk", "grep", "head", "tail", "ls", "uname", "env", "id", "ps", "cut", "wc", "touch", "cp", "mv", "perl", "sh", "bash")


class GardeDeVersion(AvecTrain):
    def faux_python(self, version: str = "3.9.6") -> tuple:
        """Un `python3` factice qui journalise ses appels et répond comme un interpréteur de la version donnée (la vérification échoue)."""
        dossier = self.t.dossier / "faux-python"
        dossier.mkdir()
        journal = self.t.dossier / "python-appels.log"
        faux = dossier / "python3"
        faux.write_text(f'#!/bin/bash\necho "$*" >> "{journal}"\n[ "$1" != "--version" ] || echo "Python {version}"\nexit 1\n', encoding="utf-8")
        faux.chmod(0o755)
        return dossier, journal

    def path_avec(self, premier: Path) -> str:
        return f"{premier}:{self.t.bin}:{self.t.bin_lsof}:{os.environ.get('PATH', '')}"

    def lance_refuse(self, extra: dict):
        self.t.branche("feat/x")
        avant = self.t.instantane()
        r = self.t.lance("feat/x", entree="o\n", extra=extra)
        self.code(r, 76, PHRASE)
        self.contient(r, BANNIERE)
        self.assertIn(BANNIERE, self.t.log())
        self.rien_ne_change(avant)
        self.assertEqual(self.t.appels("runner"), [])
        self.assertFalse((self.t.etat / "ci-appels").exists(), "le passage du conteneur a été lancé")
        self.absent(r, "train : 1 branche(s)")   # aucune étape après la garde
        return r

    def test_python_3_9_en_tete_du_path_donne_76_avant_tout_autre_appel(self):
        dossier, journal = self.faux_python("3.9.6")
        self.lance_refuse({"PATH": self.path_avec(dossier)})
        appels = journal.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(appels), 1, f"un seul appel de python3 avant le refus, vu : {appels}")
        self.assertIn("-c", appels[0])

    def test_un_python_3_9_ne_laisse_aucun_enregistrement_du_journal_des_trains(self):
        dossier, journal = self.faux_python("3.9.6")
        self.lance_refuse({"PATH": self.path_avec(dossier)})
        self.assertEqual(list(self.t.data.rglob("*.jsonl")), [])

    def test_aucun_python3_dans_le_path_donne_76(self):
        outils = self.t.dossier / "outils-sans-python"
        outils.mkdir()
        for nom in OUTILS_SYSTEME:
            chemin = shutil.which(nom)
            if chemin and not (outils / nom).exists():
                (outils / nom).symlink_to(chemin)
        self.assertFalse((outils / "python3").exists())
        self.lance_refuse({"PATH": f"{self.t.bin}:{outils}"})

    def test_le_path_par_defaut_de_launchd_donne_76_quand_le_python_du_systeme_est_ancien(self):
        systeme = Path("/usr/bin/python3")
        if systeme.exists():
            lu = subprocess.run([str(systeme), "-c", "import sys; print(int(sys.version_info >= (3, 10)))"], capture_output=True, text=True)
            if lu.stdout.strip() == "1":
                self.skipTest("le python3 du système (/usr/bin/python3) est 3.10 ou plus sur cette machine : la passe du Mac en est la preuve")
        self.lance_refuse({"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"})


if __name__ == "__main__":
    unittest.main()
