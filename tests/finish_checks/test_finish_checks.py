"""
Scénarios du module de contrôles de fin en lecture seule (tools/finish_checks.py ; change finish-train-foundations, groupe 3, D9 à D14).

    uv run python -m unittest discover -s tests/finish_checks -v

Dépôts Git jetables (tests/finish_checks/aide_depot.py) : un dépôt distant nu pour « origin », de fausses listes, de faux dossiers
d'enregistrements ; le module est lancé comme l'auteur le lancera, sous « python3 -I ». Aucun réseau, aucune base, aucun vrai nom.
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from aide_depot import AvecDepot, Depot

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import finish_checks  # noqa: E402


def instantane(depot: Depot) -> dict:
    """Tout ce qu'une lecture ne doit pas changer : références, index, objets, fichiers de .git (taille et date), arbre de travail."""
    git_dir = Path(depot.git("rev-parse", "--path-format=absolute", "--git-dir"))
    # « git status » sans verrou optionnel : il ne rafraîchit pas l'index, le relevé ne change donc rien lui-même
    etat = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=depot.travail, capture_output=True, text=True,
                          env={**depot.env, "GIT_OPTIONAL_LOCKS": "0"}).stdout
    refs, index, objets = depot.git("for-each-ref"), depot.git("ls-files", "-s"), depot.git("count-objects", "-v")
    fichiers = {str(p.relative_to(git_dir)): (p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(git_dir.rglob("*")) if p.is_file()}
    return {"refs": refs, "index": index, "objets": objets, "git": fichiers, "etat": etat}


class Controle19(AvecDepot):
    def test_autre_change_refuse(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n", "openspec/changes/a/p.md": "modifié\n"})
        code, r = self.depot.json_branche("feat/x")
        self.assertEqual(code, 1)
        c19 = r["controls"][0]
        self.assertEqual((c19["id"], c19["verdict"]), ("19", "refused"))
        self.assertEqual(c19["phrase"], "contrôle 19 : refusé : la branche touche un autre change OpenSpec : a")

    def test_plusieurs_autres_changes_nommes(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n", "openspec/changes/b/p.md": "m\n", "openspec/changes/a/p.md": "m\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertIn("a, b", r["controls"][0]["phrase"])

    def test_son_propre_change_passe(self):
        # le change a est archivé sur la branche a : son dossier actif est supprimé, l'archive est écrite
        self.depot.branche("feat/a", {"tools/outil.sh": "un\n", "openspec/changes/a/p.md": None,
                                      "openspec/changes/archive/2026-01-01-a/p.md": "a\n"})
        code, r = self.depot.json_branche("feat/a")
        self.assertEqual(self.verdicts(r)["19"], "pass")
        self.assertEqual(code, 0, r)

    def test_archive_d_un_autre_change_permise_et_dite(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n", "openspec/changes/archive/2026-01-01-autre/p.md": "a\n"})
        code, r = self.depot.json_branche("feat/x")
        self.assertEqual(code, 0)
        c19 = r["controls"][0]
        self.assertEqual(c19["verdict"], "pass")
        self.assertTrue(any("2026-01-01-autre" in d and "permis" in d for d in c19["details"]), c19)

    def test_branche_de_specification_sans_objet(self):
        self.depot.branche("spec/x", {"openspec/changes/a/p.md": "m\n", "openspec/changes/b/p.md": "m\n"})
        code, r = self.depot.json_branche("spec/x")
        self.assertEqual(code, 0)
        self.assertEqual(self.verdicts(r)["19"], "exempt")
        self.assertEqual(self.verdicts(r)["5"], "exempt")
        self.assertEqual(r["controls"][0]["phrase"], "contrôle 19 : sans objet (branche de spécification)")
        self.assertEqual(r["controls"][1]["phrase"], "contrôle 5 : sans objet (branche de spécification)")


class Controle5(AvecDepot):
    def test_change_lie_par_le_nom_refuse(self):
        self.depot.branche("feat/nouveau", {"tools/outil.sh": "un\n", "openspec/changes/nouveau/p.md": "n\n"})
        code, r = self.depot.json_branche("feat/nouveau")
        self.assertEqual(code, 1)
        c5 = r["controls"][1]
        self.assertEqual((c5["id"], c5["verdict"]), ("5", "refused"))
        self.assertEqual(c5["phrase"], "contrôle 5 : refusé : change OpenSpec non archivé")
        self.assertEqual(c5["details"], ["nouveau"])

    def test_change_lie_par_un_chemin_modifie_refuse(self):
        # le change a est modifié (chemin) : le 19 refuse aussi, le 5 le lie par le chemin
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n", "openspec/changes/a/p.md": "m\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(self.verdicts(r)["5"], "refused")
        self.assertEqual(r["controls"][1]["details"], ["a"])

    def test_change_non_lie_present_passe(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})   # a et b existent sur main, la branche n'y touche pas
        code, r = self.depot.json_branche("feat/x")
        self.assertEqual(code, 0)
        self.assertEqual(self.verdicts(r)["5"], "pass")
        self.assertEqual(r["controls"][1]["phrase"], "contrôle 5 : passe")

    def test_le_dernier_segment_du_nom_lie_le_change(self):
        self.depot.branche("feat/groupe/b", {"tools/outil.sh": "un\n"})
        _, r = self.depot.json_branche("feat/groupe/b")
        self.assertEqual(self.verdicts(r)["5"], "refused")
        self.assertEqual(r["controls"][1]["details"], ["b"])


class Controle6(AvecDepot):
    def test_fichier_evalue_sans_enregistrement_refuse(self):
        self.depot.branche("feat/x", {"CLAUDE.md": "changé\n"})
        code, r = self.depot.json_branche("feat/x")
        self.assertEqual(code, 1)
        c6 = r["controls"][2]
        self.assertEqual((c6["id"], c6["verdict"]), ("6", "refused"))
        self.assertEqual(c6["phrase"], "contrôle 6 : refusé : jeu d'essai validant absent")
        self.assertTrue(c6["details"])

    def test_aucun_fichier_evalue_change_sans_objet(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(r["controls"][2]["verdict"], "exempt")
        self.assertEqual(r["controls"][2]["phrase"], "contrôle 6 : sans objet (aucun fichier évalué changé)")

    def test_enregistrement_par_empreinte_passe(self):
        sommet = self.depot.branche("feat/x", {"CLAUDE.md": "changé\n"})
        self.depot.enregistrer_essai("2026-01-02", sommet, empreinte=self.depot.empreinte(sommet))
        code, r = self.depot.json_branche("feat/x")
        self.assertEqual(self.verdicts(r)["6"], "pass")
        self.assertEqual(code, 0)

    def test_empreinte_d_un_autre_etat_ne_passe_pas(self):
        sommet = self.depot.branche("feat/x", {"CLAUDE.md": "changé\n"})
        self.depot.enregistrer_essai("2026-01-02", sommet, empreinte="v1:" + "0" * 64)
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(self.verdicts(r)["6"], "refused")

    def test_enregistrement_par_etat_teste_passe(self):
        sommet = self.depot.branche("feat/x", {"CLAUDE.md": "changé\n"})
        self.depot.enregistrer_essai("2026-01-02", sommet)
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(self.verdicts(r)["6"], "pass")

    def test_etat_teste_different_refuse(self):
        sommet = self.depot.branche("feat/x", {"CLAUDE.md": "changé\n"})
        self.depot.enregistrer_essai("2026-01-02", self.depot.git("rev-parse", "main"))   # l'état de main n'est pas celui de la branche
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(self.verdicts(r)["6"], "refused")
        self.assertIsNotNone(sommet)

    def test_enregistrement_non_validant_incomplet_rejuge_ou_en_anglais_ne_passe_pas(self):
        sommet = self.depot.branche("feat/x", {"CLAUDE.md": "changé\n"})
        empreinte = self.depot.empreinte(sommet)
        for i, champs in enumerate(({"validant": False}, {"complet": False}, {"rejuge": True}, {"langue": "en"})):
            self.depot.enregistrer_essai(f"2026-02-0{i + 1}", sommet, empreinte=empreinte, **champs)
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(self.verdicts(r)["6"], "refused")

    def test_dossier_des_enregistrements_absent_refuse(self):
        self.depot.branche("feat/x", {"CLAUDE.md": "changé\n"})
        os.rmdir(self.depot.data / "essais")
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(self.verdicts(r)["6"], "refused")

    def test_etat_teste_disparu_refuse_avec_sa_raison(self):
        self.depot.branche("feat/x", {"CLAUDE.md": "changé\n"})
        self.depot.enregistrer_essai("2026-01-02", "f" * 40)
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(self.verdicts(r)["6"], "refused")
        self.assertTrue(any("n'existe plus" in d for d in r["controls"][2]["details"]), r["controls"][2])


class Controle6SansListe(AvecDepot):
    OPTIONS = {"liste_jeu": False}

    def test_liste_absente_refuse_meme_sans_fichier_evalue_change(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        code, r = self.depot.json_branche("feat/x")
        self.assertEqual(code, 1)
        self.assertEqual(self.verdicts(r)["6"], "refused")
        self.assertIn("absente ou vide", " ".join(r["controls"][2]["details"]))


class Controle14(AvecDepot):
    def test_code_de_la_base_sans_passage_refuse(self):
        self.depot.branche("feat/x", {"db/001.sql": "SELECT 2;\n"})
        code, r = self.depot.json_branche("feat/x")
        self.assertEqual(code, 1)
        c14 = r["controls"][3]
        self.assertEqual((c14["id"], c14["verdict"]), ("14", "refused"))
        self.assertEqual(c14["phrase"], "contrôle 14 : refusé : passage dbtest vert absent")

    def test_motif_avec_joker_refuse(self):
        self.depot.branche("feat/x", {"tools/db_nouveau.py": "x = 2\n"})   # « tools/db* »
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(self.verdicts(r)["14"], "refused")

    def test_passage_pour_l_arbre_du_sommet_passe(self):
        sommet = self.depot.branche("feat/x", {"db/001.sql": "SELECT 2;\n"})
        self.depot.enregistrer_dbtest(self.depot.arbre(sommet))
        code, r = self.depot.json_branche("feat/x")
        self.assertEqual((code, self.verdicts(r)["14"]), (0, "pass"))

    def test_passage_d_un_autre_arbre_ne_passe_pas(self):
        self.depot.branche("feat/x", {"db/001.sql": "SELECT 2;\n"})
        self.depot.enregistrer_dbtest(self.depot.arbre("main"))
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(self.verdicts(r)["14"], "refused")

    def test_code_de_la_base_inchange_sans_objet(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(r["controls"][3]["verdict"], "exempt")
        self.assertEqual(r["controls"][3]["phrase"], "contrôle 14 : sans objet (code de la base inchangé)")

    def test_motif_retire_sur_la_branche_exige_toujours_le_passage(self):
        # la branche retire « db/ » de tools/finish_db_paths.txt (finish-single-b3-b6 D15 : la liste n'est plus dans le script de fin) et change
        # un fichier de db/ : union la plus stricte
        liste = (self.depot.travail / "tools" / "finish_db_paths.txt").read_text(encoding="utf-8")
        self.assertIn("db/\n", liste)
        self.depot.branche("feat/x", {"tools/finish_db_paths.txt": "".join(l for l in liste.splitlines(keepends=True) if l.strip() != "db/"),
                                      "db/001.sql": "SELECT 2;\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(self.verdicts(r)["14"], "refused")

    def test_liste_des_fichiers_evalues_ou_la_branche_retire_une_entree_reste_stricte(self):
        liste = (self.depot.travail / "tests" / "postures" / "fichiers-evalues.txt").read_text(encoding="utf-8")
        self.depot.branche("feat/x", {"tests/postures/fichiers-evalues.txt": liste.replace("CLAUDE.md\n", "", 1), "CLAUDE.md": "changé\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(self.verdicts(r)["6"], "refused")


class DeuxRefus(AvecDepot):
    def test_5_et_14_sont_rapportes_ensemble(self):
        self.depot.branche("feat/nouveau", {"openspec/changes/nouveau/p.md": "n\n", "db/001.sql": "SELECT 2;\n"})
        code, r = self.depot.json_branche("feat/nouveau")
        self.assertEqual(code, 1)
        self.assertEqual(self.verdicts(r), {"19": "pass", "5": "refused", "6": "exempt", "14": "refused", "16": "exempt", "20": "exempt"})
        _, sortie, _ = self.depot.module("branch", "feat/nouveau")
        self.assertIn("feat/nouveau : 2 contrôle(s) refusé(s) sur 6", sortie)

    def test_tous_les_controles_passent_dit_en_une_ligne(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        code, sortie, _ = self.depot.module("branch", "feat/x")
        self.assertEqual(code, 0)
        self.assertIn("feat/x : les 6 contrôles passent", sortie)


class NonControlable(AvecDepot):
    def verifie(self, branche, phrase):
        code, sortie, erreur = self.depot.module("branch", branche)
        self.assertEqual(code, 3, (sortie, erreur))
        self.assertIn(phrase, sortie + erreur)

    def test_main(self):
        self.verifie("main", "branche non contrôlable : branche main")

    def test_spike(self):
        self.depot.branche("spike/x", {"tools/outil.sh": "un\n"})
        self.verifie("spike/x", "branche non contrôlable : branche spike/*")

    def test_inconnue(self):
        self.verifie("feat/fantome", "branche non contrôlable : branche locale inconnue")

    def test_train(self):
        self.depot.branche("lot/t", {"tools/outil.sh": "un\n"})
        self.verifie("lot/t", "branche non contrôlable : branche de train lot/* : contrôler chaque branche du train")

    def test_le_json_porte_le_code_et_le_motif(self):
        self.depot.branche("lot/t", {"tools/outil.sh": "un\n"})
        code, r = self.depot.json_branche("lot/t")
        self.assertEqual((code, r["exit"], r["format"]), (3, 3, 1))
        self.assertIn("lot/*", r["error"])


class Calcul(AvecDepot):
    def test_origin_main_absent_sort_4(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        self.depot.git("update-ref", "-d", "refs/remotes/origin/main")
        code, sortie, erreur = self.depot.module("branch", "feat/x")
        self.assertEqual(code, 4)
        self.assertIn("calcul impossible (origin/main introuvable)", sortie + erreur)

    def test_pas_de_base_commune_sort_4(self):
        self.depot.git("checkout", "-q", "--orphan", "feat/orpheline")
        self.depot.commit({"tools/orphelin.sh": "o\n"})
        self.depot.git("checkout", "-q", "main")
        code, sortie, erreur = self.depot.module("branch", "feat/orpheline")
        self.assertEqual(code, 4)
        self.assertIn("calcul impossible (base commune introuvable)", sortie + erreur)

    def test_main_local_en_avance_ne_change_pas_la_base(self):
        # main local porte un commit de plus qu'origin/main (un fichier de la base) : la base est merge-base(origin/main, sommet)
        self.depot.commit({"db/002.sql": "SELECT 3;\n"}, "avance locale")
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})   # la branche contient l'avance locale
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(r["base"], self.depot.git("rev-parse", "origin/main"))
        self.assertEqual(self.verdicts(r)["14"], "refused")   # db/002.sql compte, depuis origin/main

    def test_usage(self):
        code, _, _ = self.depot.module("branch")
        self.assertEqual(code, 2)
        code, _, _ = self.depot.module("inconnu")
        self.assertEqual(code, 2)

    def test_pas_de_trace_de_pile(self):
        code, sortie, erreur = self.depot.module("branch", "feat/x", repo=self.depot.dossier / "absent")
        self.assertEqual(code, 4)
        self.assertIn("calcul impossible (git en échec)", sortie + erreur)
        self.assertNotIn("Traceback", sortie + erreur)


class Arbre14(AvecDepot):
    def lance(self, rev):
        code, sortie, erreur = self.depot.module("tree", self.depot.arbre(rev), "--json")
        r = json.loads(sortie)
        r["c14"] = next(c for c in r["controls"] if c["id"] == "14")   # le 14 se lit par son identifiant (R-20261029-30)
        return code, r

    def test_arbre_neuf_sans_passage_refuse(self):
        sommet = self.depot.branche("feat/x", {"db/001.sql": "SELECT 2;\n"})
        code, r = self.lance(sommet)
        self.assertEqual(code, 1)
        self.assertEqual([(c["id"], c["verdict"]) for c in r["controls"]], [("14", "refused"), ("16", "exempt"), ("6", "exempt")])   # R-20261030-41 : le 6 suit (B6, D19)
        self.assertEqual(r["c14"]["phrase"], "contrôle 14 : refusé : passage dbtest vert absent")

    def test_arbre_avec_son_passage_passe(self):
        sommet = self.depot.branche("feat/x", {"db/001.sql": "SELECT 2;\n"})
        self.depot.enregistrer_dbtest(self.depot.arbre(sommet))
        code, r = self.lance(sommet)
        self.assertEqual((code, r["c14"]["verdict"]), (0, "pass"))

    def test_passage_d_un_autre_arbre_refuse(self):
        sommet = self.depot.branche("feat/x", {"db/001.sql": "SELECT 2;\n"})
        self.depot.enregistrer_dbtest(self.depot.arbre("main"))
        code, _ = self.lance(sommet)
        self.assertEqual(code, 1)

    def test_arbre_sans_changement_de_base_sans_objet(self):
        sommet = self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        code, r = self.lance(sommet)
        self.assertEqual((code, r["c14"]["verdict"]), (0, "exempt"))

    def test_arbre_est_lu_par_son_identifiant_et_depuis_origin_main(self):
        # deux commits : le second revient au contenu d'origin/main pour la base ; l'arbre final ne change rien depuis origin/main
        self.depot.git("checkout", "-q", "-b", "feat/x", "main")
        self.depot.commit({"db/001.sql": "SELECT 2;\n"})
        sommet = self.depot.commit({"db/001.sql": "SELECT 1;\n"})
        self.depot.git("checkout", "-q", "main")
        code, r = self.lance(sommet)
        self.assertEqual((code, r["c14"]["verdict"]), (0, "exempt"))

    def test_arbre_inconnu_sort_4(self):
        code, _, erreur = self.depot.module("tree", "0" * 40)
        self.assertEqual(code, 4)
        self.assertNotIn("Traceback", erreur)

    def test_origin_main_absent_sort_4(self):
        self.depot.git("update-ref", "-d", "refs/remotes/origin/main")
        code, sortie, erreur = self.depot.module("tree", self.depot.arbre("main"))
        self.assertEqual(code, 4)
        self.assertIn("origin/main introuvable", sortie + erreur)


class OutillageProtege(AvecDepot):
    def test_hook_touche_est_dit_et_liste(self):
        self.depot.branche("feat/x", {"tools/hooks/pre-commit": "#!/bin/sh\nexit 0\n"})
        code, sortie, _ = self.depot.module("branch", "feat/x")
        self.assertEqual(code, 0)   # le toucher ne change pas le code de sortie
        self.assertIn("outillage de fin touché : 1 fichier(s)", sortie)   # finish-single-b3-b6 B4, D9 : la ligne unique est remplacée par les deux lignes de classe (liste fictive sans étiquette : juge)
        self.assertNotIn("outil sensible touché", sortie)
        self.assertIn("  - tools/hooks/pre-commit", sortie)

    def test_non_touche(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        code, sortie, _ = self.depot.module("branch", "feat/x")
        self.assertIn("outillage protégé non touché", sortie)
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(r["protected_touched"], [])

    def test_json_liste_les_chemins(self):
        self.depot.branche("feat/x", {"tools/hooks/pre-commit": "x\n", "tests/run_all.sh": "y\n", "tools/outil.sh": "z\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(r["protected_touched"], ["tests/run_all.sh", "tools/hooks/pre-commit"])

    def test_motif_ajoute_par_la_branche_compte_et_motif_retire_reste(self):
        liste = (self.depot.travail / "tools" / "finish_protected.txt").read_text(encoding="utf-8")
        self.depot.branche("feat/x", {"tools/finish_protected.txt": liste.replace("tools/hooks/\n", "", 1) + "docs/\n",
                                      "tools/hooks/pre-commit": "x\n", "docs/n.md": "d\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertIn("tools/hooks/pre-commit", r["protected_touched"])   # retiré sur la branche, encore dans origin/main
        self.assertIn("docs/n.md", r["protected_touched"])                # ajouté sur la branche

    def test_motif_avec_joker(self):
        liste = (self.depot.travail / "tools" / "finish_protected.txt").read_text(encoding="utf-8")
        self.depot.commit({"tools/finish_protected.txt": liste + "tools/lab_paths.*\n"})
        self.depot.git("push", "-q", "origin", "main")
        self.depot.branche("feat/x", {"tools/lab_paths.py": "# m\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(r["protected_touched"], ["tools/lab_paths.py"])

    def test_commande_protected(self):
        self.depot.branche("feat/x", {"tools/hooks/pre-commit": "x\n"}, revenir=False)
        code, sortie, _ = self.depot.module("protected")
        self.assertEqual(code, 0)
        self.assertIn("tools/hooks/", sortie)
        self.assertIn("  - tools/hooks/pre-commit", sortie)
        code, sortie, _ = self.depot.module("protected", "--json")
        r = json.loads(sortie)
        self.assertEqual((r["format"], r["exit"]), (1, 0))
        self.assertIn("tools/hooks/", r["patterns"])
        self.assertEqual(r["touched"], ["tools/hooks/pre-commit"])


class ListeProtegeeIllisible(AvecDepot):
    OPTIONS = {"protegee": False}

    def test_liste_illisible_sort_4(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        code, sortie, erreur = self.depot.module("branch", "feat/x")
        self.assertEqual(code, 4)
        self.assertIn("calcul impossible (liste de l'outillage protégé illisible)", sortie + erreur)
        code, _, _ = self.depot.module("protected")
        self.assertEqual(code, 4)


class Sorties(AvecDepot):
    def test_texte_et_json_donnent_les_memes_verdicts_et_le_meme_code(self):
        self.depot.branche("feat/nouveau", {"openspec/changes/nouveau/p.md": "n\n", "db/001.sql": "SELECT 2;\n", "tools/hooks/pre-commit": "x\n"})
        code_t, texte, _ = self.depot.module("branch", "feat/nouveau")
        code_j, r = self.depot.json_branche("feat/nouveau")
        self.assertEqual(code_t, code_j)
        self.assertEqual(r["exit"], code_j)
        lignes = [ligne for ligne in texte.splitlines()]
        for c in r["controls"]:
            self.assertIn("finish_checks : " + c["phrase"], lignes)
            for detail in c["details"]:
                self.assertIn(("  - " if c["id"] == "5" else "  ") + detail, lignes)   # le contrôle 5 liste les changes comme le script de fin
        for chemin in r["protected_touched"]:
            self.assertIn("  - " + chemin, lignes)

    def test_le_json_porte_les_cles_du_contrat(self):
        sommet = self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(set(r), {"format", "branch", "tip", "base", "base_local", "controls", "runner_proof_touched", "protected_touched", "protected_judges", "protected_sensitive", "exit"})   # B4, D9 : deux champs ajoutés, aucun retiré ; runner_proof_touched ajouté (autonomous-trains-merge D3, R-20261106-28 Q1)
        self.assertIsNone(r["base_local"])   # main local égal à origin/main : pas de seconde base
        self.assertEqual((r["format"], r["branch"], r["tip"]), (1, "feat/x", sommet))
        self.assertEqual([c["id"] for c in r["controls"]], ["19", "5", "6", "14", "16", "20"])
        for c in r["controls"]:
            self.assertEqual(set(c), {"id", "verdict", "phrase", "details"})
            self.assertIn(c["verdict"], ("pass", "refused", "exempt"))

    def test_les_lignes_commencent_par_le_prefixe(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        _, sortie, _ = self.depot.module("branch", "feat/x")
        for ligne in sortie.splitlines():
            if not ligne.startswith("  "):
                self.assertTrue(ligne.startswith("finish_checks : "), ligne)


class LectureSeule(AvecDepot):
    def test_aucune_reference_ni_fichier_ni_objet_ne_change(self):
        self.depot.branche("feat/nouveau", {"openspec/changes/nouveau/p.md": "n\n", "db/001.sql": "SELECT 2;\n", "CLAUDE.md": "c2\n",
                                           "tools/hooks/pre-commit": "x\n"})
        self.depot.branche("lot/t", {"tools/outil.sh": "un\n"})
        sommet = self.depot.git("rev-parse", "feat/nouveau")
        self.depot.enregistrer_essai("2026-01-02", sommet, empreinte=self.depot.empreinte(sommet))
        avant = instantane(self.depot)
        for args in (("branch", "feat/nouveau"), ("branch", "feat/nouveau", "--json"), ("branch", "lot/t"), ("branch", "main"),
                     ("tree", self.depot.arbre("feat/nouveau")), ("protected",), ("protected", "--json")):
            self.depot.module(*args)
        self.assertEqual(instantane(self.depot), avant)

    def test_aucun_acces_reseau_ni_fetch(self):
        # l'origine est un dossier : un fetch réécrirait FETCH_HEAD ; il n'existe pas après les lancements
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        self.depot.module("branch", "feat/x")
        self.assertFalse((self.depot.travail / ".git" / "FETCH_HEAD").exists())


class MainLocal(AvecDepot):
    """Main local différent d'origin/main : seconde base, union des chemins, trois listes (décision de l'auteur du 2026-10-26, D10)."""

    def test_main_local_en_avance_expose_sa_base(self):
        self.depot.commit({"db/002.sql": "SELECT 3;\n"}, "avance locale")
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(r["base"], self.depot.git("rev-parse", "origin/main"))
        self.assertEqual(r["base_local"], self.depot.git("rev-parse", "main"))

    def test_main_local_en_retard_ajoute_les_chemins_de_la_base_distante(self):
        self.depot.commit({"openspec/changes/b/p.md": "avance distante\n"}, "avance distante")
        self.depot.git("push", "-q", "origin", "main")
        self.depot.git("reset", "-q", "--hard", "HEAD~1")
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"}, depuis="origin/main")
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(self.verdicts(r)["19"], "refused")   # depuis main local, le change b est touché par la branche
        self.assertEqual(r["base_local"], self.depot.git("rev-parse", "main"))

    def test_la_liste_des_fichiers_evalues_est_lue_aussi_a_main_local(self):
        # main local seul porte une entrée de plus dans la liste des fichiers évalués : la branche change ce fichier
        liste = (self.depot.travail / "tests" / "postures" / "fichiers-evalues.txt").read_text(encoding="utf-8")
        self.depot.commit({"tests/postures/fichiers-evalues.txt": liste + "tools/outil.sh\n"}, "avance locale")
        self.depot.git("checkout", "-q", "-b", "feat/x", "origin/main")
        self.depot.commit({"tools/outil.sh": "un\n"})
        self.depot.git("checkout", "-q", "main")
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(self.verdicts(r)["6"], "refused")


class ExemptionDeSpecificationStricte(unittest.TestCase):
    """L'exemption « branche de spécification » est refusée dès qu'un chemin n'est pas lu de la même façon par le script (D10)."""

    def test_chemins_ordinaires_exemptes(self):
        self.assertTrue(finish_checks._branche_de_specification(["openspec/changes/a/p.md"]))

    def test_chemin_non_ascii_refuse_l_exemption(self):
        self.assertFalse(finish_checks._branche_de_specification(["openspec/changes/a/p.md", "openspec/changes/a/proposé.md"]))

    def test_guillemet_refuse_l_exemption(self):
        self.assertFalse(finish_checks._branche_de_specification(['openspec/changes/a/p"q.md']))

    def test_saut_de_ligne_refuse_l_exemption(self):
        self.assertFalse(finish_checks._branche_de_specification(["openspec/changes/a/p\nq.md"]))


class MainLocalAbsent(AvecDepot):
    def test_main_local_absent_sort_3(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"}, revenir=False)
        self.depot.git("branch", "-D", "main")
        code, sortie, erreur = self.depot.module("branch", "feat/x")
        self.assertEqual(code, 3)
        self.assertIn("base commune avec main introuvable", sortie + erreur)


class MainLocalProtege(AvecDepot):
    """Fichiers protégés : les deux bases (union) et les trois listes (origin/main, main, sommet), comme D10."""

    def test_commande_protected_compte_depuis_les_deux_bases(self):
        self.depot.commit({"tools/hooks/pre-commit": "#!/bin/sh\nexit 1\n"}, "avance locale")
        self.depot.branche("feat/x", {"tools/hooks/pre-commit": "#!/bin/sh\n"}, revenir=False)   # revient au contenu d'origin/main
        code, sortie, _ = self.depot.module("protected", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(sortie)["touched"], ["tools/hooks/pre-commit"])

    def test_avance_locale_annulee_par_la_branche_reste_comptee(self):
        self.depot.commit({"tools/hooks/pre-commit": "#!/bin/sh\nexit 1\n"}, "avance locale")
        self.depot.branche("feat/x", {"tools/hooks/pre-commit": "#!/bin/sh\n"})   # revient au contenu d'origin/main
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(r["protected_touched"], ["tools/hooks/pre-commit"])

    def test_motif_porte_par_main_local_seul_compte(self):
        liste = (self.depot.travail / "tools" / "finish_protected.txt").read_text(encoding="utf-8")
        self.depot.commit({"tools/finish_protected.txt": liste + "docs/\n"}, "avance locale")
        self.depot.branche("feat/x", {"docs/n.md": "d\n"}, depuis="origin/main")
        _, r = self.depot.json_branche("feat/x")
        self.assertIn("docs/n.md", r["protected_touched"])


class Controle14CheminsDeLaBase(AvecDepot):
    """Décision E1 : les chemins de la base ne sont pas une référence de la fermeture ; le contrôle 14 exige toujours le passage dbtest.
    Depuis finish-single-b3-b6 (D15), ils sont dans tools/finish_db_paths.txt, lu comme la liste protégée."""

    def texte_liste(self):
        return (self.depot.travail / "tools" / "finish_db_paths.txt").read_text(encoding="utf-8")

    def entrees_litterales(self):
        entrees = [e for e in finish_checks.motifs_proteges(self.texte_liste()) if "*" not in e and not e.endswith("/")]
        self.assertGreater(len(entrees), 30)
        return entrees

    def test_chaque_chemin_nomme_de_chemins_base_exige_le_passage(self):
        entrees = self.entrees_litterales()
        motifs = finish_checks.motifs_proteges(self.texte_liste())
        self.assertEqual([e for e in entrees if not finish_checks.couvert(e, motifs)], [])
        sommet = self.depot.branche("feat/x", {e: "changé\n" for e in entrees})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(self.verdicts(r)["14"], "refused")
        self.depot.enregistrer_dbtest(self.depot.arbre(sommet))
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(self.verdicts(r)["14"], "pass")

    def test_un_seul_chemin_nomme_suffit(self):
        entrees = self.entrees_litterales()
        for i, entree in enumerate((entrees[0], entrees[len(entrees) // 2], entrees[-1])):
            with self.subTest(entree):
                self.depot.branche(f"feat/e{i}", {entree: "changé\n"})
                _, r = self.depot.json_branche(f"feat/e{i}")
                self.assertEqual(self.verdicts(r)["14"], "refused")


class Mineurs(AvecDepot):
    """Constats mineurs de la revue (tâche 5.1)."""

    def test_5_echec_de_ls_tree_sort_4(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        reel = finish_checks._git

        def faux(repo, *args):
            if args and args[0] == "ls-tree":
                return subprocess.CompletedProcess(args, 128, b"", b"fatal")
            return reel(repo, *args)
        with mock.patch.object(finish_checks, "_git", faux):
            r = finish_checks.check_branch(self.depot.travail, "feat/x", env=self.depot.env)
        self.assertEqual(r["exit"], 4)
        self.assertEqual(r["error"], "calcul impossible (git en échec)")

    def test_env_retire_les_variables_git_qui_changent_la_lecture(self):
        noms = ("GIT_LITERAL_PATHSPECS", "GIT_GLOB_PATHSPECS", "GIT_NOGLOB_PATHSPECS", "GIT_ICASE_PATHSPECS", "GIT_DIR", "GIT_WORK_TREE",
                "GIT_COMMON_DIR", "GIT_INDEX_FILE")
        with mock.patch.dict(os.environ, {n: "x" for n in noms}):
            env = finish_checks._env()
        for nom in noms:
            self.assertNotIn(nom, env)
        self.assertEqual(env["GIT_OPTIONAL_LOCKS"], "0")

    def test_git_dir_de_l_environnement_ne_detourne_pas_la_lecture(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        env = {**self.depot.env, "GIT_DIR": str(self.depot.dossier / "absent.git"), "GIT_WORK_TREE": str(self.depot.dossier)}
        code, r = self.depot.json_branche("feat/x", env=env)
        self.assertEqual(code, 0, r)

    def test_6_dossier_des_enregistrements_de_l_environnement_est_honore(self):
        sommet = self.depot.branche("feat/x", {"CLAUDE.md": "changé\n"})
        autre = self.depot.dossier / "autres-essais"
        autre.mkdir()
        self.depot.enregistrer_essai("2026-01-02", sommet, empreinte=self.depot.empreinte(sommet), dossier_essais=autre)
        _, r = self.depot.json_branche("feat/x")   # le dossier par défaut est vide
        self.assertEqual(self.verdicts(r)["6"], "refused")
        _, r = self.depot.json_branche("feat/x", env={**self.depot.env, "FINISH_BRANCH_RECORDS": str(autre)})
        self.assertEqual(self.verdicts(r)["6"], "pass")

    def test_6_variable_vide_retombe_sur_le_dossier_de_donnees(self):
        sommet = self.depot.branche("feat/x", {"CLAUDE.md": "changé\n"})
        self.depot.enregistrer_essai("2026-01-02", sommet, empreinte=self.depot.empreinte(sommet))
        _, r = self.depot.json_branche("feat/x", env={**self.depot.env, "FINISH_BRANCH_RECORDS": ""})
        self.assertEqual(self.verdicts(r)["6"], "pass")

    def test_14_ligne_vide_du_registre_ne_passe_pas_un_arbre_vide(self):
        sommet = self.depot.branche("feat/x", {"db/001.sql": "SELECT 2;\n"})
        (self.depot.commun() / "pmzilla-dbtest-ok").write_text("\n\n", encoding="utf-8")
        origine = self.depot.git("rev-parse", "origin/main")
        c14 = finish_checks._controle_14(self.depot.travail, [origine], sommet, "", (origine, sommet))
        self.assertEqual(c14["verdict"], "refused")


if __name__ == "__main__":
    unittest.main()
