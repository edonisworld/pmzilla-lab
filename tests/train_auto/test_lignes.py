"""
Tâche 2.4 (change autonomous-trains-observe) : le nouveau contrôle de chaque ligne (D3), les exclusions de chemin lues dans le JSON du vrai
finish_checks.py du dossier d'exécution jetable (D4), les worktrees occupés (D5), le plafond, et la liste jamais écrite par le passage.
Les lignes refusées par `train_ready.py add` sont posées à la main (le fichier de la liste), pour que le passage les rencontre quand même.
Faux déclaré : le faux lsof de la carte des processus (PILOT_LSOF) ; risque non couvert : le vrai lsof (tests/pilot et tests/finish_train).
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from aide_auto import AvecAuto, LISTE_PROTEGEE_COMPLETE, RACINE

sys.path.insert(0, str(RACINE / "tools"))
import train_auto  # noqa: E402
import train_auto_messages  # noqa: E402


def libelle(code):
    return train_auto_messages.label(code, "fr")


class Lignes(AvecAuto):
    def lister(self, *noms, revue="faite"):
        """Écrit la liste à la main : sommet et arbre actuels de chaque branche (le fichier a le format de D3)."""
        lignes = ["# pmzilla-train-pretes format 1"]
        for nom in noms:
            lignes.append("\t".join((nom, self.t.sommet(nom), self.t.arbre(nom), revue, "2026-10-29T10:00:00Z")))
        self.dossier_train().mkdir(parents=True, exist_ok=True)
        self.fichier_liste().write_text("\n".join(lignes) + "\n", encoding="utf-8")

    def ecartee(self, r, nom, code):
        self.assertIn(f"train_auto : écartée : {nom} : {libelle(code)}", r.sortie)
        self.assertIn({"branche": nom, "raison": code}, [{"branche": e["branche"], "raison": e["raison"]} for e in self.dernier()["ecartees"]])

    def faux_lsof(self, chemin):
        script = Path(self.temp.name) / "lsof-faux.sh"
        script.write_text(f"#!/bin/sh\nprintf 'p4242\\nn%s\\n' '{chemin}'\n", encoding="utf-8")
        return {"PILOT_LSOF": f"sh {script}"}

    # --- la revérification de D3
    def test_sommet_change_depuis_l_inscription(self):
        self.inscrire("feat/x")
        self.inscrire("feat/y")
        self.commit_dans("feat/x", {"tools/apres.sh": "a\n"})
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_auto : écartée : feat/x : sommet changé depuis l'inscription", r.sortie)
        d = self.dernier()
        self.assertEqual([b["branche"] for b in d["retenues"]], ["feat/y"])
        self.assertEqual(d["decision"], "observe")

    def test_empreinte_changee(self):
        self.inscrire("feat/x")
        self.ecrire_empreinte("feat/x", arbre=self.t.arbre("main"))
        r = self.passage()
        self.ecartee(r, "feat/x", "empreinte")
        self.assertEqual((self.dernier()["decision"], self.dernier()["raison"]), ("rien", "toutes-ecartees"))

    def test_branche_disparue(self):
        self.inscrire("feat/x")
        self.t.git("worktree", "remove", "--force", str(self.t.dossier_worktree("feat/x")))
        self.t.git("branch", "-D", "feat/x")
        self.ecartee(self.passage(), "feat/x", "branche-absente")

    def test_deja_dans_origin_main(self):
        self.inscrire("feat/x")
        self.t.git("update-ref", "refs/remotes/origin/main", self.t.sommet("feat/x"))
        self.ecartee(self.passage(), "feat/x", "deja-fusionnee")

    def test_revue_non_requise_declaree_pour_du_code(self):
        self.preparer("feat/x")
        self.lister("feat/x", revue="non-requise")
        self.ecartee(self.passage(), "feat/x", "revue")

    def test_liste_vide(self):
        r = self.passage()
        self.assertIn("train_auto : rien à faire", r.sortie)
        self.assertEqual(self.dernier()["raison"], "liste-vide")

    def test_liste_illisible(self):
        self.dossier_train().mkdir(parents=True)
        self.fichier_liste().write_text("pas le bon format\n", encoding="utf-8")
        r = self.passage()
        self.assertIn("train_auto : attente : liste prête illisible", r.sortie)
        self.assertEqual((self.dernier()["decision"], self.dernier()["raison"]), ("attente", "liste-illisible"))

    # --- les exclusions de D4, lues du JSON du vrai finish_checks.py
    def exclue(self, fichiers, code, protegee_complete=False):
        if protegee_complete:
            self.poser_liste_protegee_complete()
        self.preparer("feat/x", fichiers)
        self.lister("feat/x")
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        self.ecartee(r, "feat/x", code)
        self.assertEqual((self.dernier()["decision"], self.dernier()["raison"]), ("rien", "toutes-ecartees"))
        self.assertIsNone(self.dernier()["essai"], "aucune ligne valide : aucun essai")

    def test_exclusion_fichier_protege(self):
        self.exclue({"tools/finish_branch.sh": "changé\n"}, "outillage-protege")

    def test_exclusion_chemin_de_claude(self):
        self.exclue({".claude/commands/x.md": "x\n"}, "outillage-protege", protegee_complete=True)

    def test_exclusion_claude_md_dans_un_sous_dossier(self):
        self.exclue({"mothra/CLAUDE.md": "x\n"}, "outillage-protege", protegee_complete=True)

    def test_exclusion_fichier_lu_par_les_postures(self):
        self.exclue({"tests/postures/vocabulaire.yaml": "autre\n"}, "postures")

    def retenue_sans_exclusion(self, nom):
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        d = self.dernier()
        self.assertEqual([b["branche"] for b in d["retenues"]], [nom])
        self.assertEqual(d["ecartees"], [])
        self.assertNotIn("train_auto : écartée :", r.sortie)

    # Réécrits sur la règle de D16 (autonomous-trains-merge, tâche 9.5, R-20261101-61, R-20261107-4 Q2) : avec la revue `faite` au sommet, la base et l'interface de Mothra
    # ne sont plus des exclusions du passage (elles l'étaient dans observe D4) ; le refus de `add --revue non-requise` reste couvert par tests/train_ready/test_ajout.py.
    def test_exclusion_code_de_la_base(self):
        self.preparer("feat/x", {"db/002.sql": "SELECT 2;\n"})
        self.lister("feat/x")
        self.retenue_sans_exclusion("feat/x")

    def test_exclusion_fichier_sensible_seul(self):
        # revue 10.1, constat 7 (D16) : une branche qui ne touche qu'un fichier protégé de classe `sensible` (pas `juge`), avec la revue `faite` au sommet, est retenue
        self.t.commit_main({"tools/finish_protected.txt": LISTE_PROTEGEE_COMPLETE + "tools/flow_views.py  #[sensible]\n"}, "liste protégée avec un fichier sensible", pousser=True)
        self.t.mettre_a_jour_run()
        self.preparer("feat/x", {"tools/flow_views.py": "valeur = 2\n"})
        self.lister("feat/x")
        self.retenue_sans_exclusion("feat/x")

    def test_fichier_sensible_seul_est_vu_comme_protege_sans_revue_faite(self):
        # revue de contrôle 10.2, point C (contre-preuve du constat 7) : sur le même montage, sans revue `faite` le fichier sensible est une raison `outillage-protege` :
        # il est donc bien vu comme protégé, et c'est la revue `faite` qui le laisse passer
        self.t.commit_main({"tools/finish_protected.txt": LISTE_PROTEGEE_COMPLETE + "tools/flow_views.py  #[sensible]\n"}, "liste protégée avec un fichier sensible", pousser=True)
        self.t.mettre_a_jour_run()
        self.preparer("feat/x", {"tools/flow_views.py": "valeur = 2\n"})
        with mock.patch.dict(os.environ, self.environnement(), clear=True):   # l'environnement en liste blanche du dépôt jetable, comme pour un lancement du passage
            sans_revue = train_auto.exclusions(self.t.contenu, self.t.run, "feat/x", revue=None)
            avec_revue = train_auto.exclusions(self.t.contenu, self.t.run, "feat/x", revue="faite")
        self.assertEqual(sans_revue[1], 0)
        self.assertIn("outillage-protege", sans_revue[0])
        self.assertEqual(avec_revue, ([], 0))

    def test_exclusion_chemin_d_interface(self):
        self.poser_liste_front("mothra/front/\n")
        self.preparer("feat/x", {"mothra/front/page.js": "x\n"})
        self.lister("feat/x")
        self.retenue_sans_exclusion("feat/x")

    def test_liste_du_front_absente_ou_vide_donne_controle_impossible(self):
        # R-20261030-01 : jamais une admission par défaut. Une liste sans entrée (commentaire seul), puis une liste retirée de main, refusent
        # la ligne. Une seule branche par test : le fixture est partagé, la liste est retirée dans un second test.
        self.poser_liste_front("")
        self.preparer("feat/x")
        self.lister("feat/x")
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        self.ecartee(r, "feat/x", "controle-impossible")
        self.assertEqual((self.dernier()["decision"], self.dernier()["raison"]), ("rien", "toutes-ecartees"))

    def test_liste_du_front_retiree_de_main_donne_controle_impossible(self):
        self.t.git("rm", "-q", "tools/finish_e2e_paths.txt", cwd=self.t.contenu)
        self.t.git("commit", "-q", "-m", "liste du front retirée", cwd=self.t.contenu)
        self.t.git("push", "-q", "origin", "main")
        self.t.mettre_a_jour_run()
        self.preparer("feat/x")
        self.lister("feat/x")
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        self.ecartee(r, "feat/x", "controle-impossible")

    def test_exclusion_controles_impossibles_quand_finish_checks_sort_en_4(self):
        self.preparer("feat/x")
        self.lister("feat/x")
        self.t.remplacer_finish_checks(4)
        self.ecartee(self.passage(), "feat/x", "controle-impossible")

    def test_aucune_liste_de_chemins_copiee_dans_l_outil(self):
        source = (RACINE / "tools" / "train_auto.py").read_text(encoding="utf-8")
        for motif in ("mothra/front/", "mothra/contract/", "finish_branch.sh\"", "tools/hooks/", "tests/run_all.sh", ".claude/"):
            self.assertNotIn(f'"{motif}', source.replace("\n", " "), f"chemin copié : {motif}")

    # --- les worktrees occupés
    def test_worktree_occupe_exclut_sa_branche_et_les_autres_continuent(self):
        self.preparer("feat/x")
        self.preparer("feat/y")
        self.lister("feat/x", "feat/y")
        extra = self.faux_lsof(self.t.dossier_worktree("feat/x"))
        r = self.passage(extra=extra)
        self.assertEqual(r.code, 0, r.texte)
        self.ecartee(r, "feat/x", "session-active")
        d = self.dernier()
        self.assertEqual([b["branche"] for b in d["retenues"]], ["feat/y"])
        self.assertEqual(d["decision"], "observe")

    def test_une_session_dans_l_espace_de_travail_ne_retarde_pas_le_passage(self):
        self.preparer("feat/x")
        self.lister("feat/x")
        r = self.passage(extra=self.faux_lsof(self.t.contenu))
        self.assertEqual(r.code, 0, r.texte)
        d = self.dernier()
        self.assertEqual([b["branche"] for b in d["retenues"]], ["feat/x"])
        self.assertEqual(d["decision"], "observe")

    # --- le plafond
    def test_plafond_les_premieres_lignes_valides_puis_plafond(self):
        noms = [f"feat/p{k}" for k in range(6)]
        for nom in noms:
            self.preparer(nom)
        self.lister(*noms)
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        d = self.dernier()
        # autonomous-trains-merge D9 point 1 (PLAFOND_TRAIN = 3, Q183) : trois branches retenues au plus dans les deux modes ; la liste garde son plafond de cinq.
        # Décision citée : ce test attendait cinq lignes retenues (CAP de la liste) ; il en attend trois, les suivantes sont écartées par le plafond.
        self.assertEqual([b["branche"] for b in d["retenues"]], noms[:3])
        for nom in noms[3:]:
            self.assertIn({"branche": nom, "raison": "plafond"}, [{"branche": e["branche"], "raison": e["raison"]} for e in d["ecartees"]])
            self.assertIn(f"train_auto : écartée : {nom} : {libelle('plafond')}", r.sortie)

    # --- la liste n'est jamais écrite par le passage
    def test_la_liste_est_inchangee_octet_pour_octet_apres_un_passage(self):
        self.inscrire("feat/x")
        self.commit_dans("feat/x", {"tools/apres.sh": "a\n"})   # une ligne écartée : le passage la voit mais ne la réécrit pas
        self.inscrire("feat/y")
        avant = self.octets_liste()
        self.assertEqual(self.passage().code, 0)
        self.assertEqual(self.octets_liste(), avant)


if __name__ == "__main__":
    unittest.main()
