"""
Tâche 2.9 (change autonomous-trains-observe, design D9) : les deux éléments de `pilot.py status` pour le train automatique, dans des tests
nouveaux seulement (aucune assertion existante de la suite n'est changée). Un faux laboratoire jetable (aide_pilot.Labo) à qui l'on ajoute, dans
main, les listes que lisent les contrôles (outillage protégé, fichiers évalués, chemins de la base, chemins d'interface) : sans elles, toute
branche serait « contrôles impossibles ». Aucun réseau, aucun gh, aucune écriture par le status.
"""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aide_pilot as A  # noqa: E402


class TrainDansLeStatus(unittest.TestCase):
    def setUp(self):
        self.labo = A.Labo()
        ws = self.labo.ws
        for chemin, contenu in {"tools/finish_protected.txt": "# liste fictive\ntools/hooks/\n", "tests/postures/fichiers-evalues.txt": "CLAUDE.md\n",
                                "tools/finish_branch.sh": "CHEMINS_BASE=(\n  \"db/\"\n)\n",
                                "tools/finish_e2e_paths.txt": "# liste fictive\nmothra/front/\n",
                                "tools/finish_db_paths.txt": "# liste fictive (B5, D15 : la liste des chemins de base remplace CHEMINS_BASE)\ndb/\n",
                                "tools/finish_runner_paths.txt": "# liste fictive (autonomous-trains-merge D3, R-20261106-32 (A))\ntests/run_all.sh\n"}.items():
            (ws / chemin).parent.mkdir(parents=True, exist_ok=True)
            (ws / chemin).write_text(contenu, encoding="utf-8")
        A.git(ws, "add", ".")
        A.git(ws, "commit", "-q", "-m", "listes des contrôles")
        A.git(ws, "push", "-q", "origin", "main")
        self.train = self.labo.donnees / "train-auto"

    # --- aides
    def ecrire_liste(self, *lignes):
        self.train.mkdir(parents=True, exist_ok=True)
        (self.train / "pretes.tsv").write_text("\n".join(["# pmzilla-train-pretes format 1", *lignes]) + "\n", encoding="utf-8")

    def ligne(self, branche, sommet, arbre):
        return "\t".join((branche, sommet, arbre, "faite", "2026-10-29T10:00:00Z"))

    def empreinte(self, wt, arbre):
        chemin = A.git(wt, "rev-parse", "--path-format=absolute", "--git-path", "pmzilla-run-all-ok")
        Path(chemin).write_text(arbre + "\n", encoding="utf-8")

    def etat_dossier(self):
        resultat = {}
        for racine, _, fichiers in os.walk(self.labo.donnees):
            for f in fichiers:
                p = Path(racine) / f
                resultat[str(p.relative_to(self.labo.donnees))] = (p.read_bytes(), p.stat().st_mtime_ns)
        return resultat

    def status(self, **kw):
        r = self.labo.pilot("status", **kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def ligne_du_worktree(self, sortie, debut):
        trouvees = [l for l in sortie.splitlines() if l.startswith(debut)]
        self.assertEqual(len(trouvees), 1, sortie)
        return trouvees[0]

    # --- le drapeau « prête » sur la ligne d'un worktree
    def test_branche_listee_valide(self):
        wt = self.labo.wt_propre
        sommet = A.git(wt, "rev-parse", "HEAD")
        arbre = A.git(wt, "rev-parse", "HEAD^{tree}")
        self.empreinte(wt, arbre)
        self.ecrire_liste(self.ligne(A.BRANCHE_PROPRE, sommet, arbre))
        sortie = self.status()
        self.assertIn("prête (valide)", self.ligne_du_worktree(sortie, "wt-propre"))
        self.assertNotIn("prête", self.ligne_du_worktree(sortie, "wt-sale"))

    def test_branche_listee_avec_un_sommet_perime(self):
        wt = self.labo.wt_propre
        arbre = A.git(wt, "rev-parse", "HEAD^{tree}")
        self.ecrire_liste(self.ligne(A.BRANCHE_PROPRE, A.git(self.labo.ws, "rev-parse", "main"), arbre))   # le sommet noté n'est plus celui de la branche
        sortie = self.status()
        self.assertIn("prête (écartée : sommet changé depuis l'inscription)", self.ligne_du_worktree(sortie, "wt-propre"))

    def test_drapeau_en_anglais(self):
        wt = self.labo.wt_propre
        arbre = A.git(wt, "rev-parse", "HEAD^{tree}")
        self.ecrire_liste(self.ligne(A.BRANCHE_PROPRE, A.git(self.labo.ws, "rev-parse", "main"), arbre))
        r = self.labo.pilot("--language", "en", "status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ready (excluded: tip changed since the addition)", r.stdout)

    def test_liste_illisible_ne_change_rien_au_status(self):
        sans = self.status()
        self.train.mkdir(parents=True)
        (self.train / "pretes.tsv").write_text("pas le bon format\n", encoding="utf-8")
        self.assertEqual(self.status(), sans)

    # --- la ligne « train automatique »
    def poser_etat(self, **dernier):
        self.train.mkdir(parents=True, exist_ok=True)
        enregistrement = {"paris": "2026-10-29 12:05", "decision": "observe", "raison": "essai"}
        enregistrement.update(dernier)
        (self.train / "etat.json").write_text(json.dumps({"format": 1, "dernier": enregistrement, "liste": {"lignes": 0, "valides": 0}}), encoding="utf-8")

    def test_arret_actif(self):
        self.poser_etat()
        (self.train / "arret").write_text("", encoding="utf-8")
        sortie = self.status()
        ligne = [l for l in sortie.splitlines() if l.startswith("train automatique")]
        # D20 (autonomous-trains-merge, tâche 9.6) remplace la ligne de D9 d'autonomous-trains-observe : elle gagne « ; série <k>/5 » (décision citée)
        self.assertEqual(ligne, ["train automatique : observation ; dernier passage 2026-10-29 12:05 Paris : observé (essai de fin) ; arrêt actif ; série 0/5"])
        lignes = sortie.splitlines()
        self.assertTrue(lignes[lignes.index(ligne[0]) - 1].startswith("fin en cours"), "juste après la ligne du verrou de fin")

    def test_arret_absent(self):
        self.poser_etat(decision="attente", raison="matin")
        ligne = [l for l in self.status().splitlines() if l.startswith("train automatique")]
        self.assertEqual(ligne, ["train automatique : observation ; dernier passage 2026-10-29 12:05 Paris : attente (veille ou sauvegarde du jour en cours) ; arrêt absent ; série 0/5"])   # R-20261102-3 et R-20261102-5 (D4), réécrit : phrase ; D20 : « ; série 0/5 »

    def test_arret_seul_sans_etat(self):
        self.train.mkdir(parents=True)
        (self.train / "arret").write_text("", encoding="utf-8")
        ligne = [l for l in self.status().splitlines() if l.startswith("train automatique")]
        self.assertEqual(ligne, ["train automatique : observation ; aucun passage ; arrêt actif ; série 0/5"])   # D20 : « ; série 0/5 »

    # --- D20 : le mode vient de l'activation, la série du journal des trains
    def ecrire_serie(self, n):
        dossier = self.labo.donnees / "trains"
        dossier.mkdir(parents=True, exist_ok=True)
        lignes = []
        for i in range(n):
            tip = f"{i + 1}" * 40
            lignes.append(json.dumps({"format": 1, "heure": "2026-11-06T10:00:00Z", "code": 0, "sens": "fusionne", "mode": "manuel", "n": 2, "sommets": ["a" * 40],
                                      "sommet_train": tip, "main_avant": "9" * 40, "main_apres": tip, "runner": "conteneur", "base": True, "front": False,
                                      "politique": [], "duree_s": 600, "etape": ""}))
        (dossier / "journal.jsonl").write_text("\n".join(lignes) + "\n", encoding="utf-8")

    def ligne_train(self):
        return [l for l in self.status().splitlines() if l.startswith("train automatique")]

    def test_serie_et_mode_de_fusion(self):
        self.poser_etat()
        self.ecrire_serie(5)
        f = self.train / "fusion-active"
        f.write_text(json.dumps({"format": 1, "heure": "2026-11-06T12:00:00Z", "serie": [f"{i}" * 40 for i in range(1, 6)]}), encoding="utf-8")
        f.chmod(0o600)
        self.assertEqual(self.ligne_train(), ["train automatique : fusion automatique ; dernier passage 2026-10-29 12:05 Paris : observé (essai de fin) ; arrêt absent ; série 5/5"])

    def test_activation_invalide(self):
        self.poser_etat()
        self.ecrire_serie(3)
        f = self.train / "fusion-active"
        f.write_text(json.dumps({"format": 1, "heure": "2026-11-06T12:00:00Z", "serie": [f"{i}" * 40 for i in range(1, 6)]}), encoding="utf-8")
        f.chmod(0o600)
        self.assertEqual(self.ligne_train(), ["train automatique : activation invalide ; dernier passage 2026-10-29 12:05 Paris : observé (essai de fin) ; arrêt absent ; série 3/5"])

    def test_le_fichier_d_activation_seul_montre_la_ligne(self):
        self.train.mkdir(parents=True)
        f = self.train / "fusion-active"
        f.write_text("pas du json", encoding="utf-8")
        f.chmod(0o600)
        self.assertEqual(self.ligne_train(), ["train automatique : activation invalide ; aucun passage ; arrêt absent ; série 0/5"])

    def test_serie_en_anglais(self):
        self.poser_etat()
        self.ecrire_serie(2)
        r = self.labo.pilot("--language", "en", "status")
        self.assertIn("auto train: observation; last pass 2026-10-29 12:05 Paris: observed (finish trial); stop absent; series 2/5", r.stdout)

    # --- revue de contrôle 10.2, point A : un état présent mais illisible est dit sur la ligne, sans rien écrire
    def test_etat_illisible_est_dit_sur_la_ligne(self):
        self.train.mkdir(parents=True)
        (self.train / "etat.json").write_text("{pas du json", encoding="utf-8")
        avant = self.etat_dossier()
        self.assertEqual(self.ligne_train(), ["train automatique : observation ; état du train automatique illisible : le réparer ou le retirer ; arrêt absent ; série 0/5"])
        self.assertEqual(self.etat_dossier(), avant)

    def test_etat_illisible_en_anglais(self):
        self.train.mkdir(parents=True)
        (self.train / "etat.json").write_text("{pas du json", encoding="utf-8")
        r = self.labo.pilot("--language", "en", "status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("auto train: observation; automatic train state unreadable: repair or remove it; stop absent; series 0/5", r.stdout)

    # --- sans fichier de train, la sortie est inchangée et rien n'est écrit
    def test_sans_fichier_de_train_la_sortie_est_inchangee_et_rien_n_est_ecrit(self):
        avant = self.etat_dossier()
        sortie = self.status()
        self.assertNotIn("train automatique", sortie)
        self.assertNotIn("prête", sortie)
        self.assertEqual(len(sortie.splitlines()), 7, sortie)   # en-tête, trois worktrees, espace de travail, verrou de fin, dossier d'exécution
        self.assertEqual(self.etat_dossier(), avant)
        self.train.mkdir(parents=True)   # un dossier de train vide ne change rien non plus
        self.assertEqual(self.status(), sortie)
        self.assertFalse(any(self.train.iterdir()), "le status n'a rien écrit dans le dossier de train")

    def test_le_status_n_ecrit_rien_avec_des_fichiers_de_train(self):
        self.poser_etat()
        self.ecrire_liste()
        avant = self.etat_dossier()
        self.status()
        self.assertEqual(self.etat_dossier(), avant)


if __name__ == "__main__":
    unittest.main()
