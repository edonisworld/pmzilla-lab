"""
Tâche 2.5 (change autonomous-trains-observe) : l'essai `finish_train.sh --essai` du dossier d'exécution jetable, avec le VRAI script de fin copié dans
le dépôt jetable (jamais celui du dépôt de travail lancé pour de bon), sa lecture par code de sortie, l'analyseur des refus 62 et 64 épinglé sur
la vraie sortie, un seul nouvel essai, l'arrêt armé sur 65 et 79. Une sonde remplace le script de fin dans trois tests pour voir ce que le passage lui donne.
"""
import ast
import sys
import unittest
from pathlib import Path

from aide_auto import AvecAuto, RACINE
from aide_train import CORPS, jeton

sys.path.insert(0, str(RACINE / "tools"))
import train_auto  # noqa: E402

SONDE = """#!/bin/bash
env | sort > "@ETAT@/env-essai.txt"
echo "$*" > "@ETAT@/args-essai.txt"
if [ -t 0 ]; then echo terminal > "@ETAT@/stdin-essai.txt"; elif read -r -t 1 _x; then echo lu > "@ETAT@/stdin-essai.txt"; else echo ferme > "@ETAT@/stdin-essai.txt"; fi
echo "appel" >> "@ETAT@/appels-essai.txt"
exit "${SONDE_CODE:-0}"
"""


class Essai(AvecAuto):
    def lister(self, *noms):
        lignes = ["# pmzilla-train-pretes format 1"]
        for nom in noms:
            lignes.append("\t".join((nom, self.t.sommet(nom), self.t.arbre(nom), "faite", "2026-10-29T10:00:00Z")))
        self.dossier_train().mkdir(parents=True, exist_ok=True)
        self.fichier_liste().write_text("\n".join(lignes) + "\n", encoding="utf-8")

    def fetchs(self):
        return [l for l in self.t.journal_git() if " fetch " in f" {l} "]

    def poser_sonde(self):
        self.t.casser_le_module("finish_train.sh", self.t.remplir(SONDE))

    # --- l'essai réel
    def test_deux_branches_valides_essai_a_zero_references_inchangees(self):
        self.inscrire("feat/x")
        self.inscrire("feat/y")
        avant = self.t.instantane()
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_auto : observation : 2 branche(s) retenue(s), 0 écartée(s) ; essai code 0", r.sortie)
        d = self.dernier()
        self.assertEqual(d["decision"], "observe")
        self.assertEqual(d["essai"], {"code": 0, "relance": False, "code2": None, "retirees": []})
        self.assertEqual([b["branche"] for b in d["retenues"]], ["feat/x", "feat/y"])
        self.assertEqual([b["sommet"] for b in d["retenues"]], [self.t.sommet("feat/x"), self.t.sommet("feat/y")])
        self.rien_ne_change(avant)
        self.assertEqual(self.t.origin_main(), self.t.main())

    def test_refus_62_une_branche_relancee_une_fois_sans_elle(self):
        self.inscrire("feat/x")
        self.inscrire("feat/y")
        (self.t.dossier_worktree("feat/y") / "tools" / "brouillon.txt").write_text("x\n", encoding="utf-8")   # la fin refuse « worktree pas propre »
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        e = self.dernier()["essai"]
        self.assertEqual((e["code"], e["relance"], e["code2"], e["retirees"]), (62, True, 0, ["feat/y"]))
        self.assertIn("essai code 0", r.sortie)
        self.assertEqual(len(self.fetchs()), 2, "deux essais, jamais trois")

    def test_conflit_64_relance_sans_la_branche_nommee(self):
        self.t.branche("feat/a", {"tools/outil.sh": "version a\n"})
        self.ecrire_empreinte("feat/a")
        self.t.branche("feat/b", {"tools/outil.sh": "version b\n"})
        self.ecrire_empreinte("feat/b")
        self.lister("feat/a", "feat/b")
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        e = self.dernier()["essai"]
        self.assertEqual((e["code"], e["relance"], e["code2"], e["retirees"]), (64, True, 0, ["feat/b"]))

    def test_pas_de_second_nouvel_essai(self):
        # b refusée à l'admission (62), puis a et c, que rien ne séparait à l'admission, entrent en conflit (64) au second essai : pas de troisième
        self.t.branche("feat/a", {"tools/outil.sh": "version a\n"})
        self.ecrire_empreinte("feat/a")
        self.preparer("feat/b")
        self.t.branche("feat/c", {"tools/outil.sh": "version c\n"})
        self.ecrire_empreinte("feat/c")
        self.lister("feat/a", "feat/b", "feat/c")
        (self.t.dossier_worktree("feat/b") / "tools" / "brouillon.txt").write_text("x\n", encoding="utf-8")
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        e = self.dernier()["essai"]
        self.assertEqual((e["code"], e["relance"], e["code2"], e["retirees"]), (62, True, 64, ["feat/b"]))
        self.assertEqual(len(self.fetchs()), 2)
        self.assertIn("essai code 64", r.sortie)

    def test_secret_dans_le_train_65_arme_l_arret_sans_relance(self):
        self.t.branche("feat/x", {"docs/a.txt": f"token = {jeton()}\n"}, suite=[{"docs/a.txt": None}])
        self.ecrire_empreinte("feat/x")
        self.lister("feat/x")
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_auto : arrêt armé après le code 65", r.sortie)
        e = self.dernier()["essai"]
        self.assertEqual((e["code"], e["relance"]), (65, False))
        self.assertTrue((self.dossier_train() / "arret").exists())
        armements = [x for x in self.journal() if x["type"] == "arret"]
        self.assertEqual([x["raison"] for x in armements], ["65"])
        self.assertEqual(len(self.fetchs()), 1)
        for texte in (r.texte, self.tout_le_texte_ecrit()):
            self.assertNotIn(CORPS, texte, "la valeur trouvée n'est écrite nulle part")
        # le passage suivant s'arrête
        r2 = self.passage()
        self.assertIn("train_auto : arrêté (arrêt d'urgence actif)", r2.sortie)

    # --- l'analyseur, épinglé sur la vraie sortie de la fin
    def test_l_analyseur_lit_le_refus_62_de_la_vraie_fin(self):
        self.t.branche("feat/x")
        self.t.branche("feat/y")
        (self.t.dossier_worktree("feat/y") / "tools" / "brouillon.txt").write_text("x\n", encoding="utf-8")
        r = self.t.lance("--essai", "feat/x", "feat/y")
        self.assertEqual(r.code, 62, r.texte)
        self.assertEqual(train_auto.parse_refused(62, r.texte, ["feat/x", "feat/y"]), ["feat/y"])

    def test_l_analyseur_lit_le_conflit_64_de_la_vraie_fin(self):
        self.t.branche("feat/a", {"tools/outil.sh": "version a\n"})
        self.t.branche("feat/b", {"tools/outil.sh": "version b\n"})
        r = self.t.lance("--essai", "feat/a", "feat/b")
        self.assertEqual(r.code, 64, r.texte)
        self.assertEqual(train_auto.parse_refused(64, r.texte, ["feat/a", "feat/b"]), ["feat/b"])

    def test_l_analyseur_ne_rend_rien_quand_aucune_branche_n_est_lisible(self):
        self.assertEqual(train_auto.parse_refused(62, "finish_train : aucune branche admise\n", ["feat/a"]), [])
        self.assertEqual(train_auto.parse_refused(64, "finish_train : construction du train impossible (git merge-tree, code 2)\n", ["feat/a"]), [])
        self.assertEqual(train_auto.parse_refused(62, "  - feat/autre : introuvable en local\n", ["feat/a"]), [], "seules les branches données comptent")

    # --- ce que le passage donne à la fin (sonde)
    def test_entree_fermee_et_aucune_variable_de_la_fin_ni_jeton(self):
        self.preparer("feat/x")
        self.lister("feat/x")
        self.poser_sonde()
        extra = {"FINISH_TRAIN_RUNNER": "bash faux", "FINISH_TRAIN_CI": "faux", "FINISH_TRAIN_MORNING_CHECK": "faux", "FINISH_LOCK_TOKEN": "jeton-herite",
                 "FINISH_TRAIN_LOG_DIR": "/nulle/part"}
        r = self.passage(extra=extra)
        self.assertEqual(r.code, 0, r.texte)
        env = (self.t.etat / "env-essai.txt").read_text(encoding="utf-8")
        self.assertNotIn("FINISH_TRAIN_", env)
        self.assertNotIn("FINISH_LOCK_TOKEN", env)
        self.assertNotIn("CLAUDECODE", env)
        self.assertEqual((self.t.etat / "stdin-essai.txt").read_text(encoding="utf-8").strip(), "ferme")
        self.assertEqual((self.t.etat / "args-essai.txt").read_text(encoding="utf-8").strip(), "--essai feat/x")

    def test_code_79_arme_l_arret(self):
        self.preparer("feat/x")
        self.lister("feat/x")
        self.poser_sonde()
        r = self.passage(extra={"SONDE_CODE": "79"})
        self.assertIn("train_auto : arrêt armé après le code 79", r.sortie)
        self.assertTrue((self.dossier_train() / "arret").exists())

    def test_un_autre_code_est_note_sans_nouvel_essai(self):
        self.preparer("feat/x")
        self.lister("feat/x")
        self.poser_sonde()
        r = self.passage(extra={"SONDE_CODE": "70"})
        self.assertIn("essai code 70", r.sortie)
        self.assertEqual(len((self.t.etat / "appels-essai.txt").read_text(encoding="utf-8").splitlines()), 1)
        self.assertFalse((self.dossier_train() / "arret").exists())

    # --- aucune voie vers un lancement réel
    def test_aucune_option_ni_mode_ne_lance_une_fin_sans_essai(self):
        commande = train_auto.trial_command("/run", ["feat/a", "feat/b"])
        self.assertEqual(commande, ["bash", "/run/tools/finish_train.sh", "--essai", "feat/a", "feat/b"])
        sous_commandes = set(train_auto.build_parser()._subparsers._group_actions[0].choices)
        # Tranche 3 d'autonomous-trains-merge (D5, D6, tâche 9.1) : activation, activer et desactiver s'ajoutent ; aucune ne lance une fin.
        self.assertEqual(sous_commandes, {"pass", "status", "observation", "arret", "reprendre", "plist", "activation", "activer", "desactiver"})
        source = (RACINE / "tools" / "train_auto.py").read_text(encoding="utf-8")
        arbre = ast.parse(source)
        proprietaires = set()
        for noeud in arbre.body:
            if isinstance(noeud, ast.Expr):
                continue   # la docstring du module
            for sous in ast.walk(noeud):
                if isinstance(sous, ast.Constant) and isinstance(sous.value, str) and "finish_train.sh" in sous.value:
                    proprietaires.add(getattr(noeud, "name", "<module>"))
        # Tranche 3 d'autonomous-trains-merge (D9, tâche 9.2) : `train_command` (toujours avec --auto) s'ajoute à `trial_command` (toujours avec --essai) ; aucun autre
        # endroit ne nomme le script de fin. Décision citée : D9 point 3 (le train réel après un essai final à 0), qui lève la restriction d'observation (R-167).
        self.assertEqual(proprietaires, {"trial_command", "train_command"}, "deux endroits nomment le script de fin : l'un ajoute --essai, l'autre --auto")
        self.assertEqual(train_auto.train_command("/run", ["feat/a"]), ["bash", "/run/tools/finish_train.sh", "--auto", "feat/a"])

    def test_aucun_sous_commande_git_qui_ecrit_ou_qui_va_chercher(self):
        arbre = ast.parse((RACINE / "tools" / "train_auto.py").read_text(encoding="utf-8"))
        arbre_ready = ast.parse((RACINE / "tools" / "train_ready.py").read_text(encoding="utf-8"))
        interdits = {"fetch", "push", "pull", "merge", "commit", "update-ref", "reset", "checkout", "tag", "gc", "gh", "stash"}   # « branch » est la sous-commande de finish_checks.py, pas de Git
        vus = set()
        for a in (arbre, arbre_ready):
            for noeud in ast.walk(a):
                if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str) and noeud.value in interdits:
                    vus.add(noeud.value)
        self.assertEqual(vus, set())


if __name__ == "__main__":
    unittest.main()
