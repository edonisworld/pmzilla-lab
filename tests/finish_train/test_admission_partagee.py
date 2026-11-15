"""
finish-single-b3-b6, B4 (design D8 et D12) : la règle d'admission partagée est celle du module tools/finish_admission.sh, que le train
(tools/finish_train.sh) source. Ce fichier prouve le module seul sur des dépôts jetables réels (chaque exemption de la règle des fichiers ignorés, un
lien symbolique compté, un dossier suivi en partie compté, propre ou non, revue enregistrée) et que le train n'en garde aucune copie. Depuis
finish-single-b7-b9 (B9, tâche 1.1), la fin unitaire (tools/finish_worktree.sh, enveloppe du train depuis B78) est retirée : les tests statiques
ci-dessous ne gardent plus que le côté du train. Les comportements du train (motifs de refus) restent prouvés par tests/finish_train/test_admission.py.

Aucun faux : le module est sourcé par un vrai bash du système, git est le vrai git, la liste des branches prêtes est un vrai fichier lu par le
vrai lecteur tools/train_ready.py copié dans le dossier des outils du test. Risque non couvert : le lecteur réel dans un vrai dossier de données du lab.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
OUTILS = RACINE / "tools"
MODULE = OUTILS / "finish_admission.sh"
BASH = "/bin/bash" if os.access("/bin/bash", os.X_OK) else "bash"
HEX = "a" * 40


def lire(chemin):
    return (OUTILS / chemin).read_text(encoding="utf-8")


def code_sans_commentaire(chemin):
    return "\n".join(l for l in lire(chemin).splitlines() if not l.lstrip().startswith("#"))


class Statique(unittest.TestCase):
    """Une seule règle : le module la porte, le train la source et n'en copie rien (D8)."""

    FONCTIONS_DE_LA_REGLE = ("sous_node_modules_mothra", "sous_dist_mothra", "ignored_report")

    def test_le_module_existe_et_definit_la_regle(self):
        self.assertTrue(MODULE.is_file(), "tools/finish_admission.sh absent")
        texte = code_sans_commentaire("finish_admission.sh")
        for nom in ("fa_ignored", "fa_clean", "fa_review_done"):
            self.assertRegex(texte, rf"(?m)^{nom}\(\) \{{", nom)

    def test_le_train_source_le_module(self):
        # finish-single-b7-b9, B9 (tâche 1.1) : l'enveloppe, retirée, n'a plus son côté ; le train garde le sien
        self.assertIn("/finish_admission.sh", code_sans_commentaire("finish_train.sh"))

    def test_aucun_appelant_ne_definit_la_regle(self):
        for script in ("finish_train.sh",):
            texte = code_sans_commentaire(script)
            for nom in self.FONCTIONS_DE_LA_REGLE:
                with self.subTest(script=script, fonction=nom):
                    self.assertNotRegex(texte, rf"(?m)^\w*{nom}\(\)", f"{script} définit encore {nom}")

    def test_aucun_appelant_ne_relit_les_fichiers_ignores_lui_meme(self):
        for script in ("finish_train.sh",):
            with self.subTest(script=script):
                self.assertNotIn("--others --ignored", code_sans_commentaire(script))

    def test_le_module_n_imprime_rien_et_n_a_aucun_exit(self):
        texte = code_sans_commentaire("finish_admission.sh")
        self.assertNotRegex(texte, r"(?m)^\s*exit\b|[;&|]\s*exit\b")
        self.assertNotRegex(texte, r"(?m)^\s*(echo|printf)\b")

    def test_seul_le_module_lit_la_liste_des_branches_pretes(self):
        for script in ("finish_train.sh",):
            with self.subTest(script=script):
                self.assertNotIn("train_ready", code_sans_commentaire(script))
        self.assertIn("train_ready", code_sans_commentaire("finish_admission.sh"))


class AvecDepot(unittest.TestCase):
    """Un dépôt jetable et le module sourcé par un vrai bash."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dossier = Path(self.temp.name).resolve()
        self.depot = self.dossier / "depot"
        self.outils = self.dossier / "outils"
        self.data = self.dossier / "data"
        self.gitconfig = self.dossier / "gitconfig"
        self.gitconfig.write_text("[user]\n\temail = t@example.org\n\tname = test\n[init]\n\tdefaultBranch = main\n", encoding="utf-8")
        self.env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")}
        self.env.update(GIT_CONFIG_GLOBAL=str(self.gitconfig), GIT_CONFIG_SYSTEM="/dev/null", GIT_TERMINAL_PROMPT="0",
                        PMZILLA_LAB_DATA=str(self.data), PMZILLA_LAB_WORKSPACE=str(self.depot))
        self.outils.mkdir()
        for nom in ("finish_admission.sh", "train_ready.py", "train_ready_messages.py", "train_auto_messages.py", "messages.py", "lab_paths.py"):
            if (OUTILS / nom).exists():
                shutil.copy(OUTILS / nom, self.outils / nom)
        self.git("init", "-q", str(self.depot), cwd=self.dossier)
        self.ecrire(".gitignore", "node_modules/\nmothra/front/dist/\n*.sentinelle\n__pycache__/\n.DS_Store\n.claude/settings.local.json\n*.pyc\n")
        self.ecrire("README.md", "x\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "initial")

    def git(self, *args, cwd=None):
        fait = subprocess.run(["git", *args], cwd=cwd or self.depot, env=self.env, capture_output=True, text=True)
        self.assertEqual(fait.returncode, 0, fait.stderr)
        return fait.stdout.strip()

    def ecrire(self, chemin, contenu="x\n"):
        f = self.depot / chemin
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(contenu, encoding="utf-8")

    def exclure(self, motif):
        with open(self.depot / ".git" / "info" / "exclude", "a", encoding="utf-8") as f:
            f.write(motif + "\n")

    def bash(self, script):
        fait = subprocess.run([BASH, "-c", f'. "{self.outils / "finish_admission.sh"}" || exit 99\n{script}'], cwd=self.dossier, env=self.env,
                              capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
        return fait.returncode, fait.stdout, fait.stderr


class Ignores(AvecDepot):
    def ignores(self):
        code, sortie, erreur = self.bash(f'fa_ignored "{self.depot}"; printf "%s\\n" "$FA_IGN_COUNT"; printf "%s\\n" "$FA_IGN_DIRS"')
        self.assertEqual((code, erreur), (0, ""))
        lignes = sortie.split("\n")
        return int(lignes[0]), [l for l in lignes[1:] if l]

    def test_aucun_fichier_ignore(self):
        self.assertEqual(self.ignores(), (0, []))

    def test_un_dossier_de_premier_niveau_une_seule_fois_et_jamais_un_nom_de_fichier(self):
        self.ecrire("sortie/a.sentinelle")
        self.ecrire("sortie/rapports/b.sentinelle")
        n, dossiers = self.ignores()
        self.assertEqual((n, dossiers), (2, ["sortie"]))

    def test_un_fichier_a_la_racine_est_dit_racine(self):
        self.ecrire("fichier.sentinelle")
        self.assertEqual(self.ignores(), (1, ["(racine)"]))

    def test_exceptions_de_reglage_local_de_caches_et_de_ds_store(self):
        self.ecrire(".claude/settings.local.json", "{}\n")
        self.ecrire("__pycache__/m.pyc")
        self.ecrire("tools/__pycache__/m.pyc")
        self.ecrire("tools/m.pyc")
        self.ecrire(".DS_Store")
        self.ecrire("tools/.DS_Store")
        self.assertEqual(self.ignores(), (0, []))

    def test_node_modules_sous_mothra_est_exempte(self):
        self.ecrire("mothra/serveur/node_modules/paquet/index.js")
        self.ecrire("mothra/front/node_modules/p/b.js")
        self.assertEqual(self.ignores(), (0, []))

    def test_node_modules_hors_de_mothra_est_compte(self):
        self.ecrire("outils/node_modules/paquet/index.js")
        self.ecrire("node_modules/racine.js")
        n, dossiers = self.ignores()
        self.assertEqual(n, 2)
        self.assertEqual(sorted(dossiers), ["node_modules", "outils"])

    def test_un_autre_fichier_ignore_sous_mothra_est_compte_a_cote_de_node_modules(self):
        self.ecrire("mothra/serveur/node_modules/paquet/index.js")
        self.ecrire("mothra/serveur/reste.sentinelle")
        self.assertEqual(self.ignores(), (1, ["mothra"]))

    def test_dist_de_mothra_front_est_exempte_et_ailleurs_compte(self):
        self.ecrire("mothra/front/dist/assets/app.js")
        self.assertEqual(self.ignores(), (0, []))
        self.ecrire("autre/dist/app.js", "x\n")
        self.exclure("autre/dist/")
        self.assertEqual(self.ignores(), (1, ["autre"]))

    def lien_vers_dossier(self, chemin):
        cible = self.dossier / "cible-lien"
        cible.mkdir(exist_ok=True)
        (cible / "f.txt").write_text("precieux\n", encoding="utf-8")
        lien = self.depot / chemin
        lien.parent.mkdir(parents=True, exist_ok=True)
        lien.symlink_to(cible)
        return cible

    def test_un_lien_symbolique_node_modules_est_compte_et_sa_cible_intacte(self):
        self.exclure("mothra/serveur/node_modules")
        cible = self.lien_vers_dossier("mothra/serveur/node_modules")
        self.assertEqual(self.ignores(), (1, ["mothra"]))
        self.assertEqual((cible / "f.txt").read_text(encoding="utf-8"), "precieux\n")

    def test_un_lien_symbolique_dist_est_compte(self):
        self.exclure("mothra/front/dist")
        shutil.rmtree(self.depot / "mothra", ignore_errors=True)
        self.lien_vers_dossier("mothra/front/dist")
        self.assertEqual(self.ignores(), (1, ["mothra"]))

    def suivi_en_partie(self, dossier):
        self.ecrire(f"{dossier}/t.js", "t\n")
        self.git("add", "-f", f"{dossier}/t.js")
        self.git("commit", "-q", "-m", "suivi en partie")
        self.ecrire(f"{dossier}/sortie/x", "x\n")

    def test_un_node_modules_suivi_en_partie_est_compte(self):
        self.suivi_en_partie("mothra/serveur/node_modules")
        self.assertEqual(self.ignores(), (1, ["mothra"]))

    def test_un_dist_suivi_en_partie_est_compte(self):
        self.suivi_en_partie("mothra/front/dist")
        self.assertEqual(self.ignores(), (1, ["mothra"]))

    def test_un_nom_non_ascii_est_lu_en_z(self):
        self.ecrire("sortie/é.sentinelle")
        self.ecrire("mothra/serveur/node_modules/pkg/é.js")
        self.assertEqual(self.ignores(), (1, ["sortie"]))

    def test_la_regle_ne_change_ni_les_options_du_shell_ni_le_dossier_courant(self):
        self.ecrire("sortie/a.sentinelle")
        code, sortie, _ = self.bash(f'cd "{self.dossier}"; set -u; before=$(set +o); fa_ignored "{self.depot}"; after=$(set +o)\n'
                                    f'[ "$before" = "$after" ] && [ "$(pwd -P)" = "{self.dossier}" ] && echo stable')
        self.assertEqual((code, sortie.strip()), (0, "stable"))

    def test_le_module_n_imprime_rien(self):
        self.ecrire("sortie/a.sentinelle")
        code, sortie, erreur = self.bash(f'fa_ignored "{self.depot}" >/dev/null; fa_ignored "{self.depot}"')
        self.assertEqual((code, sortie, erreur), (0, "", ""))


class Propre(AvecDepot):
    def propre(self):
        return self.bash(f'fa_clean "{self.depot}"')[0]

    def test_propre(self):
        self.assertEqual(self.propre(), 0)

    def test_un_fichier_non_suivi_modifie_ou_indexe_n_est_pas_propre(self):
        self.ecrire("sale.txt")
        self.assertEqual(self.propre(), 1)
        (self.depot / "sale.txt").unlink()
        self.ecrire("README.md", "autre\n")
        self.assertEqual(self.propre(), 1)
        self.git("add", "README.md")
        self.assertEqual(self.propre(), 1)

    def test_un_fichier_ignore_ne_rend_pas_sale(self):
        self.ecrire("sortie/a.sentinelle")
        self.assertEqual(self.propre(), 0)

    def test_dossier_qui_n_est_pas_un_depot_n_est_pas_propre(self):
        (self.dossier / "vide").mkdir()
        self.assertEqual(self.bash(f'fa_clean "{self.dossier / "vide"}"')[0], 1)


class Revue(AvecDepot):
    """fa_review_done <branche> <sommet> : la ligne de la liste des branches prêtes (lecteur de R-166), au sommet exact, refus par défaut (D12)."""

    FORMAT = "# pmzilla-train-pretes format 1"

    def ecrire_liste(self, *lignes, entete=None):
        dossier = self.data / "train-auto"
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "pretes.tsv").write_text("\n".join([entete or self.FORMAT, *lignes]) + "\n", encoding="utf-8")

    def ligne(self, branche="feat/x", sommet=HEX, revue="faite"):
        return "\t".join((branche, sommet, "b" * 40, revue, "2026-10-30T10:00:00Z"))

    def faite(self, branche="feat/x", sommet=HEX):
        return self.bash(f'fa_review_done "{branche}" "{sommet}"')[0]

    def test_le_sommet_exact_et_la_revue_faite_donnent_vrai(self):
        self.ecrire_liste(self.ligne())
        self.assertEqual(self.faite(), 0)

    def test_un_autre_sommet_est_refuse(self):
        self.ecrire_liste(self.ligne())
        self.assertEqual(self.faite(sommet="c" * 40), 1)
        self.assertEqual(self.faite(sommet=HEX[:12]), 1)   # un sommet abrégé n'est pas le sommet exact

    def test_une_autre_branche_est_refusee(self):
        self.ecrire_liste(self.ligne())
        self.assertEqual(self.faite(branche="feat/y"), 1)

    def test_la_bonne_ligne_parmi_plusieurs(self):
        self.ecrire_liste(self.ligne("feat/a", "d" * 40), self.ligne("feat/x", HEX), self.ligne("feat/z", "e" * 40))
        self.assertEqual(self.faite(), 0)

    def test_revue_non_requise_ne_vaut_pas_revue_faite(self):
        self.ecrire_liste(self.ligne(revue="non-requise"))
        self.assertEqual(self.faite(), 1)

    def test_fichier_absent_donne_faux(self):
        self.assertEqual(self.faite(), 1)

    def test_liste_illisible_donne_faux(self):
        self.ecrire_liste("MOT-SANS-TABULATION")
        self.assertEqual(self.faite(), 1)
        self.ecrire_liste(self.ligne(), entete="# autre format")
        self.assertEqual(self.faite(), 1)

    def test_lecteur_absent_donne_faux(self):
        self.ecrire_liste(self.ligne())
        (self.outils / "train_ready.py").unlink()
        self.assertEqual(self.faite(), 1)

    def test_le_module_ne_modifie_pas_la_liste(self):
        self.ecrire_liste(self.ligne())
        avant = (self.data / "train-auto" / "pretes.tsv").read_bytes()
        self.faite()
        self.faite(sommet="c" * 40)
        self.assertEqual((self.data / "train-auto" / "pretes.tsv").read_bytes(), avant)
        self.assertEqual(sorted(p.name for p in (self.data / "train-auto").iterdir()), ["pretes.tsv"])

    def test_aucune_sortie(self):
        self.ecrire_liste(self.ligne())
        code, sortie, erreur = self.bash(f'fa_review_done feat/x {HEX}; fa_review_done feat/x {"c" * 40}')
        self.assertEqual((sortie, erreur), ("", ""))


if __name__ == "__main__":
    unittest.main()
