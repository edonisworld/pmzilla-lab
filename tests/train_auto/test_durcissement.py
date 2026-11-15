"""
R-20261030-01 (change autonomous-trains-observe) : six corrections déléguées, chacune avec son test.
1 le marqueur de session reste dans l'environnement des outils appelés ; 2 `add` écrit le sommet évalué ; 3 un worktree disparu est une raison
de refus ; 4 une branche dont le sommet a bougé pendant l'essai est écartée ; 5 le délai tue tout le groupe de processus ; 6 les choix de
`--revue` sont REVIEWS.
"""
import contextlib
import io
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

from aide_auto import AvecAuto, MARQUEUR_SESSION, RACINE

sys.path.insert(0, str(RACINE / "tools"))
import train_auto  # noqa: E402
import train_ready  # noqa: E402

SONDE_BOUGE = """#!/bin/bash
echo "$*" > "@ETAT@/args-essai.txt"
[ -z "$SONDE_BOUGE" ] || @GIT@ -C @CONTENU@ update-ref "refs/heads/$SONDE_BOUGE" refs/heads/main
exit 0
"""

PERE_ET_PETIT_FILS = """import os, subprocess, sys
p = subprocess.Popen(["sleep", "60"])
open(sys.argv[1], "w").write(str(p.pid))
os.system("sleep 60")
if len(sys.argv) > 2:
    open(sys.argv[2], "w").write("fin")   # témoin : écrit seulement si le père est allé au bout de l'attente, donc n'a pas été tué
"""


def est_vivant(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def attendre_la_mort(pid, secondes=5.0):
    fin = time.time() + secondes
    while time.time() < fin:
        if not est_vivant(pid):
            return True
        time.sleep(0.05)
    return not est_vivant(pid)


class Durcissement(AvecAuto):
    def lister(self, *noms):
        lignes = ["# pmzilla-train-pretes format 1"]
        for nom in noms:
            lignes.append("\t".join((nom, self.t.sommet(nom), self.t.arbre(nom), "faite", "2026-10-29T10:00:00Z")))
        self.dossier_train().mkdir(parents=True, exist_ok=True)
        self.fichier_liste().write_text("\n".join(lignes) + "\n", encoding="utf-8")

    # --- 1 le marqueur de session reste
    def test_1_clean_env_garde_le_marqueur_de_session(self):
        env = train_auto.clean_env({MARQUEUR_SESSION: "1", "FINISH_LOCK_TOKEN": "j", "FINISH_TRAIN_RUNNER": "x", "AUTRE": "a"})
        self.assertEqual(env, {MARQUEUR_SESSION: "1", "AUTRE": "a"})

    def test_1_list_reste_permis_en_session(self):
        self.inscrire("feat/x")
        r = self.pret("list", extra={MARQUEUR_SESSION: "1"})
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("feat/x", r.sortie)

    # --- 2 le sommet écrit est le sommet évalué
    def test_2_un_sommet_change_apres_l_evaluation_n_est_pas_note(self):
        self.preparer("feat/x")
        evalue = self.t.sommet("feat/x")
        arbre = self.t.arbre("feat/x")
        reel = train_ready.evaluate_add

        def evaluer_puis_bouger(*args, **kw):
            resultat = reel(*args, **kw)
            self.commit_dans("feat/x", {"tools/apres.sh": "a\n"})   # le sommet bouge entre l'évaluation et l'écriture
            return resultat

        with mock.patch.object(train_ready, "evaluate_add", evaluer_puis_bouger), \
             mock.patch.object(train_ready, "workspace", lambda: self.t.contenu), \
             mock.patch.object(train_ready.lab_paths, "run_tree", lambda ws: self.t.run), \
             mock.patch.object(train_ready, "data_dir", lambda: self.dossier_train()), \
             contextlib.redirect_stdout(io.StringIO()):   # R-20261031-47 : la ligne « preuve » d'add ne remplace plus le bilan de la suite
            code = train_ready.main(["add", "feat/x", "--revue", "faite"])
        self.assertEqual(code, 0)
        self.assertNotEqual(self.t.sommet("feat/x"), evalue, "le test a bien déplacé la branche")
        champs = self.fichier_liste().read_text(encoding="utf-8").splitlines()[1].split("\t")
        self.assertEqual(champs[:3], ["feat/x", evalue, arbre])

    # --- 3 worktree disparu
    def test_3_worktree_disparu_est_une_raison_de_refus(self):
        self.inscrire("feat/x")
        self.t.git("worktree", "remove", "--force", str(self.t.dossier_worktree("feat/x")))
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn({"branche": "feat/x", "raison": "sans-worktree"},
                      [{"branche": e["branche"], "raison": e["raison"]} for e in self.dernier()["ecartees"]])
        self.assertEqual(self.dernier()["retenues"], [])

    # --- 4 sommet changé pendant l'essai
    def test_4_branche_dont_le_sommet_bouge_pendant_l_essai_est_ecartee(self):
        self.preparer("feat/x")
        self.preparer("feat/y")
        self.lister("feat/x", "feat/y")
        self.t.casser_le_module("finish_train.sh", self.t.remplir(SONDE_BOUGE))
        r = self.passage(extra={"SONDE_BOUGE": "feat/x"})
        self.assertEqual(r.code, 0, r.texte)
        d = self.dernier()
        self.assertEqual([b["branche"] for b in d["retenues"]], ["feat/y"])
        self.assertIn({"branche": "feat/x", "raison": "sommet-change"},
                      [{"branche": e["branche"], "raison": e["raison"]} for e in d["ecartees"]])

    # --- 5 délai : tout le groupe est tué
    def test_5_run_command_tue_le_groupe_au_depassement_du_delai(self):
        script = Path(self.temp.name) / "pere.py"
        script.write_text(PERE_ET_PETIT_FILS, encoding="utf-8")
        fichier_pid = Path(self.temp.name) / "petit-fils.pid"
        temoin = Path(self.temp.name) / "pere-alle-au-bout.txt"
        debut = time.time()
        code, _ = train_auto.run_command([sys.executable, "-I", str(script), str(fichier_pid), str(temoin)], self.temp.name, os.environ, 2)
        self.assertEqual(code, 124)
        # R-20261104-11 : le comportement est prouvé par le témoin (absent = le père a été tué avant la fin de son attente de 60 s), pas par la durée ;
        # la borne de 20 s reste en filet, inchangée (elle est 3 fois plus courte que l'attente du père).
        self.assertFalse(temoin.exists(), "le père a été tué avant d'aller au bout de son attente")
        self.assertLess(time.time() - debut, 20)
        self.assertTrue(attendre_la_mort(int(fichier_pid.read_text())), "le petit-fils est mort avec le groupe")

    def test_5_lancer_de_l_aide_tue_le_groupe_au_depassement_du_delai(self):
        script = Path(self.temp.name) / "pere.py"
        script.write_text(PERE_ET_PETIT_FILS, encoding="utf-8")
        fichier_pid = Path(self.temp.name) / "petit-fils-aide.pid"
        with self.assertRaises(subprocess.TimeoutExpired):
            self.lancer(script, [str(fichier_pid)], delai=2)
        self.assertTrue(attendre_la_mort(int(fichier_pid.read_text())), "le petit-fils est mort avec le groupe")

    # --- 6 les choix de --revue sont REVIEWS
    def test_6_les_choix_de_revue_sont_les_valeurs_de_REVIEWS(self):
        sous = train_ready.build_parser()._subparsers._group_actions[0].choices["add"]
        revue = [a for a in sous._actions if "--revue" in a.option_strings][0]
        self.assertEqual(tuple(revue.choices), train_ready.REVIEWS)


if __name__ == "__main__":
    unittest.main()
