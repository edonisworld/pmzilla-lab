"""
Tâche 2.2 (change autonomous-trains-observe) : le fichier de la liste prête sous des sessions parallèles, `drop`, `prune` et `list`
(conception D3). Les écritures sont concurrentes pour de vrai (processus enfants).
"""
import json
import os
import stat
import subprocess
import sys
import time
import unittest
from pathlib import Path

from aide_ready import READY, AvecAuto, RACINE

sys.path.insert(0, str(RACINE / "tools"))
import train_ready  # noqa: E402


class Liste(AvecAuto):
    def noms(self):
        return [l.split("\t")[0] for l in self.fichier_liste().read_text(encoding="utf-8").splitlines()[1:]]

    def test_deux_ajouts_en_meme_temps_donnent_une_liste_bien_formee(self):
        self.preparer("feat/a")
        self.preparer("feat/b")
        procs = [subprocess.Popen([sys.executable, "-I", str(READY), "add", nom, "--revue", "faite"], cwd=self.t.lab, env=self.environnement(),
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for nom in ("feat/a", "feat/b")]
        sorties = [p.communicate(timeout=300) for p in procs]
        for p, s in zip(procs, sorties):
            self.assertEqual(p.returncode, 0, s)
        entrees = train_ready.parse_list(self.fichier_liste().read_text(encoding="utf-8"))
        self.assertEqual(sorted(e["branche"] for e in entrees), ["feat/a", "feat/b"])

    def test_ligne_mal_formee_liste_illisible_avec_le_numero_jamais_le_contenu(self):
        self.inscrire("feat/x")
        with open(self.fichier_liste(), "a", encoding="utf-8") as f:
            f.write("MOT-SECRET-DE-LA-LIGNE\tseulement-deux-champs\n")
        r = self.pret("list")
        self.assertEqual(r.code, 4, r.texte)
        self.assertIn("train_ready : liste illisible : ligne 3", r.texte)
        self.assertNotIn("MOT-SECRET-DE-LA-LIGNE", r.texte)
        r = self.pret("drop", "feat/x")
        self.assertEqual(r.code, 4, r.texte)
        self.assertNotIn("MOT-SECRET-DE-LA-LIGNE", r.texte)

    def test_premiere_ligne_absente_ou_autre_format(self):
        self.dossier_train().mkdir(parents=True)
        self.fichier_liste().write_text("# autre format\n", encoding="utf-8")
        r = self.pret("list")
        self.assertEqual(r.code, 4, r.texte)
        self.assertIn("ligne 1", r.texte)

    def test_drop_d_une_branche_listee_et_d_une_branche_absente(self):
        self.inscrire("feat/x")
        self.inscrire("feat/y")
        r = self.pret("drop", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_ready : retirée : feat/x", r.sortie)
        self.assertEqual(self.noms(), ["feat/y"])
        r = self.pret("drop", "feat/fantome")
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_ready : absente de la liste : feat/fantome", r.sortie)
        self.assertEqual(self.noms(), ["feat/y"])

    def poser_verrou_de_train(self, pid=None, liste="B feat/ailleurs\nfin\n"):
        """Un verrou de fin vivant (celui de ce processus) dans le dossier Git commun du dépôt jetable, avec la liste du train."""
        commun = Path(self.t.git("rev-parse", "--path-format=absolute", "--git-common-dir"))
        verrou = commun / "pmzilla-fin-en-cours"
        verrou.mkdir()
        (verrou / "pid").write_text(f"{pid or os.getpid()}\n", encoding="utf-8")
        (verrou / "debut").write_text(f"{int(time.time())}\n", encoding="utf-8")
        (verrou / "branche").write_text("feat/train-x\n", encoding="utf-8")
        (verrou / "jeton").write_text("jeton-du-train\n", encoding="utf-8")
        (verrou / "gel").write_text(liste, encoding="utf-8")
        return verrou

    def test_add_et_drop_refuses_pendant_un_train_code_6_rien_d_ecrit(self):
        """Q1 (a) de R-20261106-71 : la même règle que le gel ciblé (finish_lock.freezes, protected) ; l'espace de travail sur main est gelé même hors liste."""
        self.preparer("feat/a")
        self.inscrire("feat/x")
        avant = self.octets_liste()
        self.poser_verrou_de_train()
        r = self.pret("add", "feat/a", "--revue", "faite")
        self.assertEqual(r.code, 6, r.texte)
        self.assertIn("train_ready : refusée pendant un train (feat/train-x)", r.texte)
        r = self.pret("drop", "feat/x")
        self.assertEqual(r.code, 6, r.texte)
        r = self.pret("add", "feat/a", "--revue", "faite", langue="en")
        self.assertEqual(r.code, 6, r.texte)
        self.assertEqual(self.octets_liste(), avant)

    def test_add_et_drop_depuis_un_worktree_de_branche_hors_liste_refuses_pendant_un_train(self):
        """Revue de contrôle 7.2 : la liste prête est gelée quel que soit le worktree de l'appelant (writes_ready_list)."""
        self.preparer("feat/a")
        self.inscrire("feat/x")
        avant = self.octets_liste()
        self.poser_verrou_de_train(liste="B feat/ailleurs\nfin\n")
        wt = self.t.dossier_worktree("feat/a")
        for args in (("add", "feat/a", "--revue", "faite"), ("drop", "feat/x")):
            r = subprocess.run([sys.executable, "-I", str(READY), *args], cwd=wt, env=self.environnement(), stdin=subprocess.DEVNULL,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 6, r.stdout + r.stderr)
        self.assertEqual(self.octets_liste(), avant)

    def test_add_et_drop_passent_hors_train_jeton_du_train_ou_verrou_perime(self):
        self.inscrire("feat/x")
        self.inscrire("feat/y")
        verrou = self.poser_verrou_de_train()
        r = self.pret("drop", "feat/x", extra={"FINISH_LOCK_TOKEN": "jeton-du-train"})
        self.assertEqual(r.code, 0, r.texte)
        (verrou / "pid").write_text("999999999\n", encoding="utf-8")   # processus inexistant : verrou périmé
        r = self.pret("drop", "feat/y")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.noms(), [])
        r = self.pret("list")
        self.assertEqual(r.code, 0, r.texte)

    def test_list_reste_permis_pendant_un_train(self):
        self.inscrire("feat/x")
        self.poser_verrou_de_train()
        r = self.pret("list")
        self.assertEqual(r.code, 0, r.texte)

    def test_prune_refuse_pendant_un_train_depuis_main_et_depuis_un_worktree_hors_liste(self):
        """R-20261106-72 : prune écrit la liste prête, donc gelé comme add et drop, quel que soit le worktree ; la liste ne change pas."""
        self.preparer("feat/a")
        self.inscrire("feat/x")
        self.t.git("update-ref", "refs/remotes/origin/main", self.t.sommet("feat/x"))   # une ligne que prune retirerait hors train
        avant = self.octets_liste()
        self.poser_verrou_de_train()
        r = self.pret("prune")
        self.assertEqual(r.code, 6, r.texte)
        r = subprocess.run([sys.executable, "-I", str(READY), "prune"], cwd=self.t.dossier_worktree("feat/a"), env=self.environnement(),
                           stdin=subprocess.DEVNULL, capture_output=True, text=True)
        self.assertEqual(r.returncode, 6, r.stdout + r.stderr)
        self.assertEqual(self.octets_liste(), avant)

    def test_prune_retire_les_fusionnees_et_les_disparues_seulement(self):
        for nom in ("feat/x", "feat/y", "feat/z"):
            self.inscrire(nom)
        self.t.git("worktree", "remove", "--force", str(self.t.dossier_worktree("feat/y")))
        self.t.git("branch", "-D", "feat/y")
        self.t.git("update-ref", "refs/remotes/origin/main", self.t.sommet("feat/x"))
        r = self.pret("prune")
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_ready : 2 ligne(s) retirée(s) (fusionnées ou disparues)", r.sortie)
        self.assertEqual(self.noms(), ["feat/z"])

    def test_prune_sans_rien_a_retirer_ne_touche_pas_la_liste(self):
        self.inscrire("feat/x")
        avant = self.octets_liste()
        r = self.pret("prune")
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("0 ligne(s) retirée(s)", r.sortie)
        self.assertEqual(self.octets_liste(), avant)

    def test_list_json_porte_la_validite_calculee_par_la_fonction_du_passage(self):
        self.inscrire("feat/x")
        self.inscrire("feat/y")
        self.commit_dans("feat/x", {"tools/apres.sh": "a\n"})
        r = self.pret("list", "--json")
        self.assertEqual(r.code, 0, r.texte)
        donnees = {l["branche"]: l for l in json.loads(r.sortie)["lignes"]}
        self.assertFalse(donnees["feat/x"]["valide"])
        self.assertEqual(donnees["feat/x"]["raison"], "sommet-change")
        self.assertTrue(donnees["feat/y"]["valide"])
        # le passage, lancé dans sa fenêtre, écarte la même ligne pour la même raison
        p = self.passage()
        self.assertEqual(p.code, 0, p.texte)
        ecartees = {e["branche"]: e["raison"] for e in self.dernier()["ecartees"]}
        self.assertEqual(ecartees.get("feat/x"), donnees["feat/x"]["raison"])

    def test_list_texte_et_list_ne_modifie_rien(self):
        self.inscrire("feat/x")
        avant = self.octets_liste()
        r = self.pret("list")
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_ready : feat/x : prête (valide)", r.sortie)
        self.assertEqual(self.octets_liste(), avant)

    def test_list_d_une_liste_absente_est_vide(self):
        r = self.pret("list")
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_ready : liste vide", r.sortie)

    def test_le_fichier_et_son_dossier_sont_lisibles_par_le_proprietaire_seul(self):
        self.inscrire("feat/x")
        self.assertEqual(stat.S_IMODE(os.stat(self.fichier_liste()).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.dossier_train()).st_mode), 0o700)
        verrou = self.dossier_train() / "pretes.lock"
        self.assertTrue(verrou.exists())
        self.assertEqual(stat.S_IMODE(os.stat(verrou).st_mode), 0o600)

    def test_aucun_fichier_temporaire_ne_reste(self):
        self.inscrire("feat/x")
        self.assertEqual([f.name for f in self.dossier_train().glob(".*tmp*")], [])


if __name__ == "__main__":
    unittest.main()
