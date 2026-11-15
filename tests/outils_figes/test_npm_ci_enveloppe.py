"""
Tests de l'enveloppe figée npm_ci.sh (R-20261110-24, voie (c) de la question 14) : un worktree du dépôt est accepté et npm est lancé avec exactement
`ci --offline --ignore-scripts` dans le dossier mothra de ce worktree ; tout le reste est refusé sans lancer npm.

Le dossier des outils figés, le relevé et dossiers.conf sont ceux de test_outils_figes.Dossier ; le dépôt est jetable (créé par le test, git réel) et
le faux npm, placé en tête du PATH de l'enveloppe (maison/.local/bin), note ses arguments et son dossier de travail. Aucun vrai npm n'est lancé.

    bash tests/run_all.sh outils_figes
"""
import json
import os
import re
import stat
import subprocess
import sys
import unittest
from pathlib import Path

import test_outils_figes as base

FAUX_NPM = """#!/bin/bash
{{ pwd -P; printf '%s\\n' "$@"; }} > "{aux}/trace-npm.txt"
env > "{aux}/trace-npm-env.txt"
exit "$(cat "{aux}/code-npm.txt" 2>/dev/null || echo 0)"
"""
L96_CHEMIN = "outil figé : argument refusé : chemin"
L96_DOSSIER = "outil figé : argument refusé : dossier"
GIT_ENV = {"PATH": "/usr/bin:/bin", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


class NpmCi(base.Dossier):
    def setUp(self):
        super().setUp()
        self.ecrire(self.figes / "npm_ci.sh", (base.SOURCE / "npm_ci.sh").read_text(encoding="utf-8"))
        npm = self.maison / ".local" / "bin" / "npm"
        self.ecrire(npm, FAUX_NPM.format(aux=self.aux))
        npm.chmod(npm.stat().st_mode | stat.S_IXUSR)
        self.releve()
        self.git(self.workspace, "init", "-q", "-b", "main")
        self.git(self.workspace, "commit", "-q", "--allow-empty", "-m", "debut")

    def git(self, dossier, *args):
        r = subprocess.run(["git", "-C", str(dossier), *args], capture_output=True, text=True, env={**GIT_ENV, "HOME": str(self.base)})
        self.assertEqual(r.returncode, 0, r.stderr)

    def vrai_worktree(self, nom="wt-a", avec_mothra=True):
        chemin = self.worktrees / nom
        self.git(self.workspace, "worktree", "add", "-q", "-b", nom, str(chemin))
        if avec_mothra:
            (chemin / "mothra").mkdir()
        return chemin

    def npm_appele(self):
        return (self.aux / "trace-npm.txt").exists()

    def refuse_npm(self, r, ligne):
        self.assertEqual(r.returncode, 96, r.stdout + r.stderr)
        self.assertEqual(r.stderr.strip(), ligne)
        self.assertFalse(self.npm_appele())

    def test_worktree_valide_npm_ci_offline_sans_scripts_dans_mothra(self):
        wt = self.vrai_worktree()
        r = self.lance("npm_ci.sh", str(wt))
        self.assertEqual(r.returncode, 0, r.stderr)
        lignes = (self.aux / "trace-npm.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lignes, [str((wt / "mothra").resolve()), "ci", "--offline", "--ignore-scripts"])

    def test_environnement_ferme(self):
        wt = self.vrai_worktree()
        r = self.lance("npm_ci.sh", str(wt), env={"NPM_CONFIG_REGISTRY": "x", "NODE_OPTIONS": "--x", "SECRET_SESSION": "s"})
        self.assertEqual(r.returncode, 0, r.stderr)
        env = {l.split("=", 1)[0] for l in (self.aux / "trace-npm-env.txt").read_text(encoding="utf-8").splitlines() if "=" in l}
        self.assertLessEqual(env - base.AJOUTES_PAR_LES_INTERPRETEURS, base.ENV_FERME)

    def test_npm_ci_trouve_npm_dans_l_alias_par_defaut_de_fnm_de_la_maison(self):
        (self.maison / ".local" / "bin" / "npm").unlink()
        fnm = self.maison / ".local" / "share" / "fnm" / "aliases" / "default" / "bin"
        npm = fnm / "npm"
        self.ecrire(npm, FAUX_NPM.format(aux=self.aux))
        npm.chmod(npm.stat().st_mode | stat.S_IXUSR)
        wt = self.vrai_worktree()
        r = self.lance("npm_ci.sh", str(wt), env={"FNM_DIR": str(self.hors)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.npm_appele())
        env = dict(l.split("=", 1) for l in (self.aux / "trace-npm-env.txt").read_text(encoding="utf-8").splitlines() if "=" in l)
        self.assertIn(str(fnm), env["PATH"].split(":"))
        self.assertNotIn(str(self.hors), env["PATH"])

    def test_les_autres_enveloppes_n_ont_pas_le_dossier_fnm_dans_leur_path(self):
        fnm = str(self.maison / ".local" / "share" / "fnm" / "aliases" / "default" / "bin")
        self.assertEqual(self.lance("gh_issue.sh", "list").returncode, 0)
        self.assertNotIn(fnm, self.trace("gh")["env"]["PATH"].split(":"))
        self.assertEqual(self.lance("flow_views.sh", "show", "v").returncode, 0)
        self.assertNotIn(fnm, self.trace("flow")["env"]["PATH"].split(":"))
        self.assertEqual(self.lance("ci_local.sh", "places").returncode, 0)
        env = dict(l.split("=", 1) for l in (self.aux / "trace-ci-env.txt").read_text(encoding="utf-8").splitlines() if "=" in l)
        self.assertNotIn(fnm, env["PATH"].split(":"))
        for nom in ("ci_local.sh", "gh_issue.sh", "flow_views.sh", "worktree.sh", "enveloppe.sh"):
            self.assertNotIn("fnm", (base.SOURCE / nom).read_text(encoding="utf-8"), nom)

    def test_le_code_de_npm_est_rendu_tel_quel(self):
        wt = self.vrai_worktree()
        self.ecrire(self.aux / "code-npm.txt", "7\n")
        self.assertEqual(self.lance("npm_ci.sh", str(wt)).returncode, 7)

    def test_chemin_hors_depot_refuse(self):
        self.refuse_npm(self.lance("npm_ci.sh", str(self.hors)), L96_CHEMIN)

    def test_dossier_avec_un_fichier_git_non_inscrit_refuse(self):
        faux = self.worktree("wt-faux", inscrit=False)
        (faux / "mothra").mkdir()
        self.refuse_npm(self.lance("npm_ci.sh", str(faux)), L96_CHEMIN)

    def test_depot_principal_refuse(self):
        (self.workspace / "mothra").mkdir()
        self.refuse_npm(self.lance("npm_ci.sh", str(self.workspace)), L96_CHEMIN)

    def test_chemin_relatif_refuse(self):
        wt = self.vrai_worktree()
        self.refuse_npm(self.lance("npm_ci.sh", "wt-a", cwd=self.worktrees), L96_CHEMIN)
        self.refuse_npm(self.lance("npm_ci.sh", ".", cwd=wt), L96_CHEMIN)

    def test_chemin_avec_point_point_refuse(self):
        wt = self.vrai_worktree()
        self.refuse_npm(self.lance("npm_ci.sh", f"{wt}/../wt-a"), L96_CHEMIN)

    def test_argument_en_plus_refuse(self):
        wt = self.vrai_worktree()
        self.refuse_npm(self.lance("npm_ci.sh", str(wt), "--force"), L96_CHEMIN)

    def test_aucun_argument_refuse(self):
        self.vrai_worktree()
        self.refuse_npm(self.lance("npm_ci.sh"), L96_CHEMIN)

    def test_chemin_inexistant_refuse(self):
        self.refuse_npm(self.lance("npm_ci.sh", str(self.worktrees / "absent")), L96_CHEMIN)

    def test_worktree_sans_dossier_mothra_refuse(self):
        wt = self.vrai_worktree(avec_mothra=False)
        self.refuse_npm(self.lance("npm_ci.sh", str(wt)), L96_DOSSIER)

    def test_mothra_lien_refuse(self):
        wt = self.vrai_worktree(avec_mothra=False)
        os.symlink(str(self.hors), str(wt / "mothra"))
        self.refuse_npm(self.lance("npm_ci.sh", str(wt)), L96_DOSSIER)

    def test_aucun_message_ne_reprend_le_chemin(self):
        r = self.lance("npm_ci.sh", str(self.hors))
        self.assertNotIn(str(self.hors), r.stdout + r.stderr)

    def test_fichier_different_du_releve_code_97(self):
        wt = self.vrai_worktree()
        chemin = self.figes / "npm_ci.sh"
        chemin.write_text(chemin.read_text(encoding="utf-8") + "# modifié\n", encoding="utf-8")
        r = self.lance("npm_ci.sh", str(wt))
        self.assertEqual(r.returncode, 97)
        self.assertFalse(self.npm_appele())

    def test_la_liste_figee_nomme_l_enveloppe(self):
        self.assertIn(("E", "npm_ci.sh"), base.liste_figee())

    def test_worktree_inscrit_hors_du_dossier_des_worktrees_refuse(self):
        """R-20261110-29 Q2 : un worktree inscrit par git mais hors du dossier des worktrees, ou à deux niveaux dessous, n'est pas accepté."""
        for chemin in (self.base / "autre-wt", self.worktrees / "sous" / "wt-b"):
            with self.subTest(chemin=chemin.relative_to(self.base).as_posix()):
                chemin.parent.mkdir(parents=True, exist_ok=True)
                self.git(self.workspace, "worktree", "add", "-q", "-b", chemin.name, str(chemin))
                (chemin / "mothra").mkdir()
                self.refuse_npm(self.lance("npm_ci.sh", str(chemin)), L96_CHEMIN)

    def test_caractere_de_controle_dans_le_chemin_refuse(self):
        wt = self.vrai_worktree()
        for suffixe in ("\t", "\n", "\x01"):
            with self.subTest(suffixe=repr(suffixe)):
                self.refuse_npm(self.lance("npm_ci.sh", f"{wt}{suffixe}"), L96_CHEMIN)

    def test_barre_finale_refusee(self):
        wt = self.vrai_worktree()
        self.refuse_npm(self.lance("npm_ci.sh", f"{wt}/"), L96_CHEMIN)

    def test_le_texte_de_l_enveloppe_ne_lance_que_git_et_npm(self):
        code = [l for l in (base.SOURCE / "npm_ci.sh").read_text(encoding="utf-8").splitlines() if l.strip() and not l.lstrip().startswith("#")]
        texte = "\n".join(code)
        self.assertEqual(texte.count("npm ci --offline --ignore-scripts"), 1)
        self.assertNotIn("npx", texte)
        self.assertNotIn("install", texte)


class ContratAvecLesGardes(unittest.TestCase):
    """R-20261110-29 Q1 : l'appel de l'enveloppe par la session n'est refusé ni par la garde npm ni par les règles deny (lecture seule des deux)."""

    RACINE = Path(__file__).resolve().parents[2]
    APPELS = ("bash ~/.pmzilla-lab/outils-figes/npm_ci.sh /un/chemin/absolu",
              "bash /Users/quelquun/.pmzilla-lab/outils-figes/npm_ci.sh /un/chemin/absolu")

    def test_la_garde_npm_ne_refuse_pas_l_appel(self):
        sys.path.insert(0, str(self.RACINE / "tools"))
        try:
            import npm_guard
        finally:
            sys.path.pop(0)
        for commande in self.APPELS:
            for cwd in (None, str(self.RACINE), str(self.RACINE / "mothra")):
                with self.subTest(commande=commande, cwd=cwd):
                    donnees = {"tool_name": "Bash", "tool_input": {"command": commande}}
                    if cwd is not None:
                        donnees["cwd"] = cwd
                    self.assertEqual(npm_guard.main([], json.dumps(donnees)), 0)

    def test_aucune_regle_deny_n_apparie_l_appel(self):
        reglages = json.loads((self.RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))
        motifs = []
        for regle in reglages["permissions"]["deny"]:
            if regle.startswith("Bash(") and regle.endswith(")"):
                motif = regle[len("Bash("):-1]
                motifs.append((regle, re.compile("".join(".*" if c == "*" else re.escape(c) for c in motif), re.DOTALL)))
        self.assertTrue(motifs)
        for commande in self.APPELS:
            with self.subTest(commande=commande):
                self.assertEqual([regle for regle, m in motifs if m.fullmatch(commande)], [])


if __name__ == "__main__":
    unittest.main()
