"""
Contrôle 20 de tools/finish_checks.py, règle de Node unique et lecture des chemins de la base (change finish-single-b3-b6, tâches 4.1 et 4.2 ;
conception D13, D15, D16).

    uv run python -m unittest discover -s tests/finish_checks -v

Des dépôts jetables avec un dépôt distant nu. Le « node » de ces tests est un vrai processus enfant (R-20261028-26) : un petit script
exécutable, posé en tête du PATH, qui imprime une version ; sa version vient de FAUX_NODE_VERSION. Faux déclaré : ce n'est pas le vrai Node ;
risque non couvert : la sortie d'un vrai « node --version » (le préfixe « v » est couvert, rien d'autre sur la sortie ne l'est) et l'absence
du gestionnaire de versions. Les chemins de la base viennent de la vraie liste tools/finish_db_paths.txt, copiée dans le dépôt jetable.
"""
import json
import os
import stat
import subprocess
import sys
import unittest
from pathlib import Path

from aide_depot import AvecDepot

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import finish_checks  # noqa: E402

BASH = "/bin/bash" if os.access("/bin/bash", os.X_OK) else "bash"
NPM = {"tests/run_all.sh": "#!/bin/bash\nSUITES_NPM=(mothra:mothra)\n", "mothra/.node-version": "26.12.1\n"}
PHRASE_REFUS = "contrôle 20 : refusé : dépendances npm à mettre en conformité avant la fin"


def controle(resultat: dict, identifiant: str) -> dict:
    return next(c for c in resultat["controls"] if c["id"] == identifiant)


class NodeMatches(unittest.TestCase):
    """La règle de D16 : égalité exacte, ou préfixe suivi d'un point ; le « v » de tête est sans effet ; un vide ne correspond jamais."""

    def test_egalite_exacte(self):
        self.assertTrue(finish_checks.node_matches("26.12.1", "26.12.1"))

    def test_le_v_de_tete_est_sans_effet(self):
        self.assertTrue(finish_checks.node_matches("v26.12.1\n", " 26.12.1 "))
        self.assertTrue(finish_checks.node_matches("26.12.1", "v26.12.1"))

    def test_prefixe_suivi_d_un_point(self):
        self.assertTrue(finish_checks.node_matches("22.11.0", "22"))
        self.assertTrue(finish_checks.node_matches("22.11.0", "22.11"))

    def test_prefixe_sans_point_ne_correspond_pas(self):
        self.assertFalse(finish_checks.node_matches("220.1.0", "22"))
        self.assertFalse(finish_checks.node_matches("22.11.0", "22.1"))

    def test_version_differente(self):
        self.assertFalse(finish_checks.node_matches("25.9.0", "26.12.1"))
        self.assertFalse(finish_checks.node_matches("26.12", "26.12.1"))   # le trouvé plus court que l'attendu ne correspond pas

    def test_vide_ne_correspond_jamais(self):
        self.assertFalse(finish_checks.node_matches("", "26.12.1"))
        self.assertFalse(finish_checks.node_matches("26.12.1", ""))
        self.assertFalse(finish_checks.node_matches("", ""))


class SousCommandeNodeMatch(AvecDepot):
    def lance(self, *args):
        fait = subprocess.run([sys.executable, "-I", str(self.depot.travail / "tools" / "finish_checks.py"), "node-match", *args],
                              cwd=self.depot.travail, env=self.depot.env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        return fait.returncode, fait.stdout + fait.stderr

    def test_correspond_sort_0(self):
        self.assertEqual(self.lance("v26.12.1", "26.12.1")[0], 0)

    def test_prefixe_sort_0(self):
        self.assertEqual(self.lance("22.11.0", "22")[0], 0)

    def test_differe_sort_1(self):
        self.assertEqual(self.lance("25.9.0", "26.12.1")[0], 1)

    def test_vide_sort_1(self):
        self.assertEqual(self.lance("", "26.12.1")[0], 1)

    def test_usage_sort_2(self):
        self.assertEqual(self.lance("26.12.1")[0], 2)
        self.assertEqual(self.lance()[0], 2)

    def test_rien_n_est_imprime_sur_la_sortie_standard(self):
        code, sortie = self.lance("25.9.0", "26.12.1")
        self.assertEqual((code, sortie), (1, ""))


class Controle20(AvecDepot):
    def setUp(self):
        super().setUp()
        self.sonde = self.depot.dossier / "sonde"
        self.sonde.mkdir()
        node = self.sonde / "node"
        node.write_text('#!/bin/sh\n[ -z "${FAUX_NODE_ECHEC:-}" ] || exit 127\necho "${FAUX_NODE_VERSION:-v26.12.1}"\n', encoding="utf-8")
        node.chmod(node.stat().st_mode | stat.S_IXUSR)
        self.env = dict(self.depot.env, PATH=f"{self.sonde}{os.pathsep}{os.environ['PATH']}")

    def json(self, branche: str, version: str | None = None):
        env = dict(self.env)
        if version:
            env["FAUX_NODE_VERSION"] = version
        code, sortie, _ = self.depot.module("branch", branche, "--json", env=env)
        return code, json.loads(sortie)

    def ouvre(self, branche: str, fichiers: dict):
        """Crée la branche et la laisse ouverte dans le dossier de travail (la branche est « ouverte » quelque part)."""
        sommet = self.depot.branche(branche, fichiers, revenir=False)
        return sommet

    def test_le_controle_20_est_le_sixieme_et_dernier(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        _, r = self.json("feat/x")
        self.assertEqual([c["id"] for c in r["controls"]], ["19", "5", "6", "14", "16", "20"])

    def test_aucune_suite_npm_sans_objet(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        code, r = self.json("feat/x")
        c = controle(r, "20")
        self.assertEqual((c["verdict"], c["phrase"], c["details"]), ("exempt", "contrôle 20 : sans objet (aucune suite npm déclarée)", []))
        self.assertEqual(code, 0)

    def test_branche_ouverte_nulle_part_sans_objet(self):
        self.depot.branche("feat/x", NPM)   # revient sur main : la branche n'est ouverte dans aucun dossier
        code, r = self.json("feat/x", version="25.9.0")
        c = controle(r, "20")
        self.assertEqual((c["verdict"], c["phrase"]), ("exempt", "contrôle 20 : sans objet (branche ouverte nulle part)"))
        self.assertEqual(code, 0)

    def test_node_conforme_passe(self):
        self.ouvre("feat/x", NPM)
        code, r = self.json("feat/x")
        c = controle(r, "20")
        self.assertEqual((c["verdict"], c["phrase"]), ("pass", "contrôle 20 : passe"))
        self.assertEqual(code, 0)

    def test_node_conforme_avec_le_v_de_tete_et_un_prefixe_attendu(self):
        self.ouvre("feat/x", {**NPM, "mothra/.node-version": "v26\n"})
        _, r = self.json("feat/x", version="v26.1.0")
        self.assertEqual(controle(r, "20")["verdict"], "pass")

    def test_node_different_refuse_avec_la_commande_npm_ci(self):
        self.ouvre("feat/x", NPM)
        code, r = self.json("feat/x", version="v25.9.0")
        c = controle(r, "20")
        self.assertEqual(c["verdict"], "refused")
        self.assertEqual(c["phrase"], PHRASE_REFUS + " (Node 25.9.0 au lieu de 26.12.1, fixé par mothra/.node-version)")
        self.assertIn("choisir la version 26.12.1 de Node, puis :", c["details"])
        lancer = [d for d in c["details"] if d.startswith("lancer : cd ")]
        self.assertEqual(len(lancer), 1, c)
        self.assertTrue(lancer[0].endswith("/travail/mothra && npm ci"), lancer)
        self.assertEqual(code, 1)

    def test_node_introuvable_refuse(self):
        self.ouvre("feat/x", NPM)
        env = dict(self.env, FAUX_NODE_ECHEC="1")   # la sonde échoue comme un Node introuvable ou cassé : sortie 127 sans rien imprimer
        code, sortie, _ = self.depot.module("branch", "feat/x", "--json", env=env)
        c = controle(json.loads(sortie), "20")
        self.assertEqual(c["verdict"], "refused")
        self.assertIn("Node introuvable au lieu de 26.12.1", c["phrase"])
        self.assertEqual(code, 1)

    def test_fichier_node_version_absent_refuse(self):
        self.ouvre("feat/x", {"tests/run_all.sh": NPM["tests/run_all.sh"], "mothra/leger.txt": "x\n"})
        _, r = self.json("feat/x")
        c = controle(r, "20")
        self.assertEqual(c["verdict"], "refused")
        self.assertIn("Node 26.12.1 au lieu de ?, fixé par mothra/.node-version", c["phrase"])

    def test_dossier_absent_reste_l_echec_du_runner(self):
        # la suite déclarée n'a pas de dossier dans l'arbre : rien n'est refusé ici (comme avant)
        self.ouvre("feat/x", {"tests/run_all.sh": NPM["tests/run_all.sh"]})
        _, r = self.json("feat/x", version="25.9.0")
        self.assertEqual(controle(r, "20")["verdict"], "pass")

    def test_une_branche_de_specification_n_est_pas_exemptee_par_le_module(self):
        # le module calcule toujours le 20 ; c'est le mode vérification du script de fin qui saute une branche de spécification
        self.depot.branche("spec/x", {"openspec/changes/a/p.md": "m\n"})
        _, r = self.json("spec/x")
        self.assertEqual(controle(r, "20")["verdict"], "exempt")

    def test_le_controle_20_ne_change_pas_le_texte_des_autres(self):
        self.ouvre("feat/x", NPM)
        code, sortie, _ = self.depot.module("branch", "feat/x", env=dict(self.env, FAUX_NODE_VERSION="25.9.0"))
        self.assertEqual(code, 1)
        self.assertIn("finish_checks : " + PHRASE_REFUS, sortie)
        self.assertIn("feat/x : 1 contrôle(s) refusé(s) sur 6", sortie)

    def test_l_environnement_du_module_est_celui_lu_pour_node(self):
        # le « node » lu est celui du PATH de l'appelant du module, jamais un chemin figé
        self.ouvre("feat/x", NPM)
        code, sortie, _ = self.depot.module("branch", "feat/x", "--json", env=dict(self.env, FAUX_NODE_VERSION="26.12.1"))
        self.assertEqual(controle(json.loads(sortie), "20")["verdict"], "pass")


class CheminsDeLaBaseLusEnUnion(AvecDepot):
    """D15 : les chemins de la base viennent de tools/finish_db_paths.txt, lu en union à origin/main, à main local et au sommet."""

    def test_une_entree_retiree_sur_la_branche_s_applique_encore(self):
        liste = (self.depot.travail / "tools" / "finish_db_paths.txt").read_text(encoding="utf-8")
        self.assertIn("db/\n", liste)
        retiree = "".join(ligne for ligne in liste.splitlines(keepends=True) if ligne.strip() != "db/")
        self.depot.branche("feat/x", {"tools/finish_db_paths.txt": retiree, "db/001.sql": "SELECT 2;\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual({c["id"]: c["verdict"] for c in r["controls"]}["14"], "refused")

    def test_une_entree_ajoutee_sur_main_local_s_applique(self):
        liste = (self.depot.travail / "tools" / "finish_db_paths.txt").read_text(encoding="utf-8")
        self.depot.commit({"tools/finish_db_paths.txt": liste + "docs/base-locale/\n"}, "avance locale")
        self.depot.branche("feat/x", {"docs/base-locale/a.md": "x\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual({c["id"]: c["verdict"] for c in r["controls"]}["14"], "refused")

    def test_un_commentaire_de_fin_de_ligne_et_les_lignes_vides_sont_ignores(self):
        liste = (self.depot.travail / "tools" / "finish_db_paths.txt").read_text(encoding="utf-8")
        self.depot.commit({"tools/finish_db_paths.txt": liste + "\ndocs/commentee/   # fin de ligne\n"}, "entrée commentée")
        self.depot.git("push", "-q", "origin", "main")
        self.depot.branche("feat/x", {"docs/commentee/a.md": "x\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual({c["id"]: c["verdict"] for c in r["controls"]}["14"], "refused")

    def test_liste_absente_partout_refuse_le_14_et_ne_le_sort_jamais_sans_objet(self):
        self.depot.git("rm", "-q", "tools/finish_db_paths.txt")
        self.depot.git("commit", "-q", "-m", "retire la liste")
        self.depot.git("push", "-q", "origin", "main")
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        _, r = self.depot.json_branche("feat/x")
        c14 = controle(r, "14")
        self.assertEqual(c14["verdict"], "refused")
        self.assertIn("illisible", " ".join(c14["details"]))

    def test_le_module_ne_lit_plus_le_texte_du_script_de_fin(self):
        # la liste de données suffit (la lecture du texte du script de fin retiré, finish_branch.sh, est retirée avec lui : finish-single-b7-b9, B9)
        self.depot.branche("feat/x", {"db/001.sql": "SELECT 2;\n"})
        _, r = self.depot.json_branche("feat/x")
        self.assertEqual(controle(r, "14")["verdict"], "refused")


class LireLeJsonPourLeScript(AvecDepot):
    """La sous-commande « extract » : le script de fin lit la sortie JSON du module par elle, une fois (D14)."""

    def sortie_json(self, branche: str) -> str:
        return self.depot.module("branch", branche, "--json")[1]

    def extract(self, texte: str, *args):
        fait = subprocess.run([sys.executable, "-I", str(self.depot.travail / "tools" / "finish_checks.py"), "extract", *args],
                              cwd=self.depot.travail, env=self.depot.env, input=texte, capture_output=True, text=True)
        return fait.returncode, fait.stdout, fait.stderr

    def test_verdicts_dans_l_ordre(self):
        self.depot.branche("feat/x", {"tools/outil.sh": "un\n"})
        code, sortie, _ = self.extract(self.sortie_json("feat/x"), "verdicts")
        self.assertEqual((code, sortie.splitlines()), (0, ["19 pass", "5 pass", "6 exempt", "14 exempt", "16 exempt", "20 exempt"]))

    def test_phrase_et_details_d_un_controle(self):
        self.depot.branche("feat/nouveau", {"tools/outil.sh": "un\n", "openspec/changes/nouveau/p.md": "n\n"})
        texte = self.sortie_json("feat/nouveau")
        self.assertEqual(self.extract(texte, "phrase", "5")[1].strip(), "contrôle 5 : refusé : change OpenSpec non archivé")
        self.assertEqual(self.extract(texte, "details", "5")[1].splitlines(), ["nouveau"])

    def test_sortie_sans_format_1_sort_4(self):
        self.assertEqual(self.extract('{"format": 2, "controls": []}', "verdicts")[0], 4)
        self.assertEqual(self.extract("pas du json", "verdicts")[0], 4)
        self.assertEqual(self.extract("", "verdicts")[0], 4)

    def test_controle_manquant_sort_4(self):
        manquant = json.dumps({"format": 1, "controls": [{"id": "19", "verdict": "pass", "phrase": "p", "details": []}], "exit": 0})
        self.assertEqual(self.extract(manquant, "verdicts")[0], 4)

    def test_les_sorties_3_et_4_du_module_ne_passent_pas_par_extract(self):
        # un enregistrement d'erreur (exit 3 ou 4) n'a pas de contrôles : extract sort 4, le script lit le code du module avant
        erreur = json.dumps({"format": 1, "branch": "x", "controls": [], "exit": 3, "error": "branche non contrôlable : main"})
        self.assertEqual(self.extract(erreur, "verdicts")[0], 4)
        self.assertEqual(self.extract(erreur, "error")[1].strip(), "branche non contrôlable : main")


if __name__ == "__main__":
    unittest.main()
