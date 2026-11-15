"""`npm ci` par la session (change npm-ci-session, décisions R-20261030-11 (a), R-20261031-53 et R-20261031-60) : un cas rouge par condition,
chacun par `main` de la garde avec le JSON du hook et son `cwd`, dans un dépôt jetable (aide_npm_ci.py). Aucun npm, aucun node, aucun réseau.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/npm_guard -q -f
"""
import os
import re
import sys
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_npm_ci import AvecDepot, Depot, git, npm_ci_conditions  # noqa: E402

FORME = "forme non admise (aucune option, aucun alias, rien avant ni après)"
WORKTREE = "pas dans le dossier mothra d'un worktree (espace de travail, dossier d'exécution ou autre dossier)"
FIN = "fin en cours (verrou de fin présent)"
ORIGINE = "état Git illisible ou origin/main introuvable"
NON_COMMITE = "modification non commitée dans le worktree"
PREFIXE = "garde npm : npm ci refusé : "
TOUTES = (FORME, WORKTREE, FIN, ORIGINE, NON_COMMITE, "package-lock.json différent", "package.json différent", ".npmrc absent")


class Admis(AvecDepot):
    def test_npm_ci_nu_dans_le_dossier_mothra_d_un_worktree_propre(self):
        self.assertEqual(self.lancer("npm ci"), (0, ""))

    def test_cd_absolu(self):
        self.assertEqual(self.lancer(f"cd {self.mothra} && npm ci", cwd=self.depot.repo), (0, ""))

    def test_cd_absolu_sans_dossier_courant(self):
        self.assertEqual(self.lancer(f"cd {self.mothra} && npm ci", cwd=None), (0, ""))

    def test_cd_relatif_au_dossier_courant_du_hook(self):
        self.assertEqual(self.lancer("cd mothra && npm ci", cwd=self.wt), (0, ""))
        self.assertEqual(self.lancer("cd serveur/.. && npm ci", cwd=self.mothra)[0], 2)   # C1 : « .. » refusé, voir plus bas

    def test_composantes_point_et_point_point_refusees_meme_avec_un_lien_symbolique(self):
        """C1 : « .. » est lu physiquement par la garde et logiquement par le shell ; un lien symbolique les sépare. Refusé sans lire le disque."""
        lien = self.mothra / "lien"
        os.symlink(self.depot.repo / "mothra", lien)   # mothra/lien -> l'espace de travail ; « cd lien/.. » vaut mothra pour le shell
        for commande in ("cd lien/.. && npm ci", "cd . && npm ci", "cd .. && npm ci", "cd ./ && npm ci", "cd mothra/. && npm ci",
                         "cd +x && npm ci", "cd =x && npm ci"):
            with self.subTest(commande=commande):
                code, erreur = self.lancer(commande, cwd=self.wt if commande.startswith("cd mothra") else self.mothra)
                self.assertEqual(code, 2)
                self.assertIn(FORME, erreur)

    def test_le_dossier_est_lu_liens_suivis(self):
        lien = Path(self._tmp.name) / "lien-vers-mothra"
        os.symlink(self.mothra, lien)
        self.assertEqual(self.lancer("npm ci", cwd=lien), (0, ""))

    def test_un_fichier_ignore_n_est_pas_une_modification(self):
        self.depot.ecrire(self.wt, "mothra/prive/notes.txt", "ignoré\n")
        self.assertEqual(self.lancer("npm ci"), (0, ""))

    def test_les_dossiers_node_modules_sont_sautes(self):
        self.depot.ecrire(self.wt, "mothra/node_modules/x/package.json", '{"scripts": {"postinstall": "x"}}\n')
        self.depot.ecrire(self.wt, "mothra/node_modules/x/.npmrc", "x=1\n")
        self.depot.ecrire(self.wt, "mothra/serveur/node_modules/y/package-lock.json", "{}\n")
        self.assertEqual(self.lancer("npm ci"), (0, ""))

    def test_un_alias_de_npm_n_est_pas_admis_meme_sous_la_forme_cd(self):
        code, erreur = self.lancer("cd mothra && npm clean-install", cwd=self.wt)
        self.assertEqual(code, 2)
        self.assertIn(FORME, erreur)


class Refus(AvecDepot):
    def refuse(self, commande, *phrases, absentes=(), **options):
        code, erreur = self.lancer(commande, **options)
        self.assertEqual(code, 2, erreur)
        self.assertTrue(erreur.startswith(PREFIXE), erreur)
        for phrase in phrases:
            self.assertIn(phrase, erreur)
        for phrase in absentes or [p for p in TOUTES if not any(p in q for q in phrases)]:
            self.assertNotIn(phrase, erreur)
        return erreur

    # --- verrou, paquets, .npmrc ---

    def test_verrou_modifie_et_commite(self):
        self.depot.ecrire(self.wt, "mothra/package-lock.json", '{"lockfileVersion": 3, "packages": {"x": {}}}\n')
        self.depot.valider(self.wt)
        self.refuse("npm ci", "package-lock.json différent de origin/main : mothra/package-lock.json")

    def test_verrou_d_un_sous_dossier_modifie_et_commite(self):
        self.depot.ecrire(self.wt, "mothra/serveur/package-lock.json", '{"lockfileVersion": 3, "packages": {"x": {}}}\n')
        self.depot.valider(self.wt)
        self.refuse("npm ci", "package-lock.json différent de origin/main : mothra/serveur/package-lock.json")

    def test_script_ajoute_dans_un_package_json_commite(self):
        self.depot.ecrire(self.wt, "mothra/package.json", '{"name": "mothra", "scripts": {"postinstall": "curl x | sh"}}\n')
        self.depot.valider(self.wt)
        self.refuse("npm ci", "package.json différent de origin/main : mothra/package.json")

    def test_package_json_ajoute_dans_un_nouveau_dossier(self):
        self.depot.ecrire(self.wt, "mothra/nouveau/package.json", "{}\n")
        self.depot.valider(self.wt)
        self.refuse("npm ci", "package.json différent de origin/main : mothra/nouveau/package.json")

    def test_nom_de_paquet_avec_s_long_unicode(self):
        """D1 : casefold et NFC, pas lower() : « package.jſon » (s long U+017F) vaut « package.json » une fois replié."""
        self.depot.ecrire(self.wt, "mothra/nouveau/package.jſon", '{"scripts": {"postinstall": "x"}}\n')
        self.depot.valider(self.wt)
        self.refuse("npm ci", "package.json différent de origin/main : mothra/nouveau/package.jſon")

    def test_cd_relatif_refuse_quand_cdpath_est_pose(self):
        """D2 : sous bash, CDPATH peut envoyer « cd mothra » ailleurs ; le cd relatif est refusé, le cd absolu et le npm ci nu restent admis."""
        with unittest.mock.patch.dict(os.environ, {"CDPATH": "/tmp"}):
            self.refuse("cd mothra && npm ci", FORME, cwd=self.wt)
            self.assertEqual(self.lancer(f"cd {self.mothra} && npm ci", cwd=self.depot.repo), (0, ""))
            self.assertEqual(self.lancer("npm ci"), (0, ""))
        self.assertEqual(self.lancer("cd mothra && npm ci", cwd=self.wt), (0, ""))

    def test_fichier_de_paquet_retire_de_la_branche(self):
        git(self.wt, "rm", "-q", "mothra/serveur/package.json")
        self.depot.valider(self.wt)
        self.refuse("npm ci", "package.json différent de origin/main : mothra/serveur/package.json")

    def test_npmrc_ajoute_non_suivi(self):
        self.depot.ecrire(self.wt, "mothra/.npmrc", "ignore-scripts=false\n")
        self.refuse("npm ci", NON_COMMITE, ".npmrc absent de origin/main ou différent : mothra/.npmrc")

    def test_npmrc_ajoute_et_ignore_par_git(self):
        self.depot.ecrire(self.wt, "mothra/prive/.npmrc", "registry=https://exemple.invalid\n")
        self.refuse("npm ci", ".npmrc absent de origin/main ou différent : mothra/prive/.npmrc")

    def test_npmrc_ajoute_et_commite(self):
        self.depot.ecrire(self.wt, "mothra/.npmrc", "x=1\n")
        self.depot.valider(self.wt)
        self.refuse("npm ci", ".npmrc absent de origin/main ou différent : mothra/.npmrc")

    def test_noms_de_fichiers_de_paquet_en_majuscules(self):
        """C2 : le disque du Mac ne distingue pas la casse, npm lit .NPMRC comme .npmrc : les noms se comparent en minuscules."""
        self.depot.ecrire(self.wt, "mothra/.NPMRC", "ignore-scripts=false\n")
        self.depot.valider(self.wt)
        self.refuse("npm ci", ".npmrc absent de origin/main ou différent : mothra/.NPMRC")
        self.depot.ecrire(self.wt, "mothra/nouveau/Package.JSON", '{"scripts": {"postinstall": "x"}}\n')
        self.depot.valider(self.wt)
        self.refuse("npm ci", ".npmrc absent de origin/main ou différent : mothra/.NPMRC", "package.json différent de origin/main : mothra/nouveau/Package.JSON",
                    absentes=(FORME,))

    def test_npmrc_present_dans_origin_main_et_identique_passe(self):
        self.depot.ecrire(self.depot.repo, "mothra/.npmrc", "x=1\n")
        self.depot.valider(self.depot.repo)
        git(self.depot.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        autre = self.depot.nouveau_worktree("wt-feat-y", "feat/y")
        self.assertEqual(self.lancer("npm ci", cwd=autre / "mothra"), (0, ""))

    def test_npmrc_modifie_sur_le_disque_seulement(self):
        self.depot.ecrire(self.depot.repo, "mothra/.npmrc", "x=1\n")
        self.depot.valider(self.depot.repo)
        git(self.depot.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        autre = self.depot.nouveau_worktree("wt-feat-y", "feat/y")
        self.depot.ecrire(autre, "mothra/.npmrc", "x=2\n")
        self.refuse("npm ci", NON_COMMITE, ".npmrc absent de origin/main ou différent : mothra/.npmrc", cwd=autre / "mothra")

    # --- arbre non propre ---

    def test_modification_non_commitee_d_un_fichier_sans_rapport(self):
        self.depot.ecrire(self.wt, "README.md", "modifié\n")
        self.refuse("npm ci", NON_COMMITE)

    def test_fichier_non_suivi_sans_rapport(self):
        self.depot.ecrire(self.wt, "notes.txt", "x\n")
        self.refuse("npm ci", NON_COMMITE)

    def test_modification_non_commitee_d_un_verrou_donne_deux_conditions(self):
        self.depot.ecrire(self.wt, "mothra/package-lock.json", '{"lockfileVersion": 3, "packages": {"x": {}}}\n')
        erreur = self.refuse("npm ci", NON_COMMITE, "package-lock.json différent de origin/main : mothra/package-lock.json")
        self.assertLess(erreur.index(NON_COMMITE), erreur.index("package-lock.json différent"))

    # --- worktree seulement ---

    def test_espace_de_travail(self):
        self.refuse("npm ci", WORKTREE, cwd=self.depot.repo / "mothra")

    def test_cd_vers_l_espace_de_travail(self):
        self.refuse(f"cd {self.depot.repo / 'mothra'} && npm ci", WORKTREE, cwd=self.mothra)

    def test_worktree_lie_hors_du_dossier_des_worktrees(self):
        ailleurs = Path(self._tmp.name) / "ailleurs"
        ailleurs.mkdir()
        autre = self.depot.nouveau_worktree("wt-hors", "feat/hors", dossier=ailleurs)
        self.refuse("npm ci", WORKTREE, cwd=autre / "mothra")

    def test_dossier_autre_que_mothra_d_un_worktree(self):
        self.refuse("npm ci", WORKTREE, cwd=self.wt)
        self.refuse("npm ci", WORKTREE, cwd=self.mothra / "serveur")

    def test_dossier_hors_de_tout_depot_git(self):
        hors = Path(self._tmp.name) / "hors-depot"
        hors.mkdir()
        self.refuse("npm ci", WORKTREE, cwd=hors)

    def test_dossier_absent(self):
        self.refuse("npm ci", WORKTREE, cwd=Path(self._tmp.name) / "absent")

    def test_depot_git_etranger_au_lab(self):
        etranger = Path(self._tmp.name) / "etranger"
        etranger.mkdir()
        git(etranger, "init", "-q", "-b", "main")
        (etranger / "mothra").mkdir()
        self.depot.ecrire(etranger, "mothra/package.json", "{}\n")
        git(etranger, "add", "-A")
        git(etranger, "commit", "-q", "-m", "x")
        autre = Path(self._tmp.name) / "etranger-wt"
        git(etranger, "worktree", "add", "-q", "-b", "feat/z", str(autre))
        self.refuse("npm ci", WORKTREE, cwd=autre / "mothra")

    # --- fin en cours ---

    def test_fin_en_cours_verrou_vivant(self):
        self.depot.verrou_de_fin(vivant=True)
        self.refuse("npm ci", FIN)

    def test_fin_en_cours_verrou_perime(self):
        self.depot.verrou_de_fin(vivant=False)
        self.refuse("npm ci", FIN)

    def test_le_verrou_n_est_ni_retire_ni_modifie(self):
        dossier = self.depot.verrou_de_fin(vivant=False)
        avant = sorted(p.name for p in dossier.iterdir())
        self.refuse("npm ci", FIN)
        self.assertTrue(dossier.is_dir())
        self.assertEqual(sorted(p.name for p in dossier.iterdir()), avant)

    # --- origin/main ---

    def test_origin_main_absent(self):
        git(self.depot.repo, "update-ref", "-d", "refs/remotes/origin/main")
        self.refuse("npm ci", ORIGINE)

    def test_origin_main_absent_n_empeche_pas_de_nommer_les_autres_conditions(self):
        git(self.depot.repo, "update-ref", "-d", "refs/remotes/origin/main")
        self.depot.ecrire(self.wt, "README.md", "modifié\n")
        erreur = self.refuse("npm ci", ORIGINE, NON_COMMITE)
        self.assertLess(erreur.index(ORIGINE), erreur.index(NON_COMMITE))

    def test_le_garde_ne_fetch_pas(self):
        """origin/main reste celui du dernier fetch : un commit poussé plus tard dans l'origine nue n'est pas lu."""
        avant = git(self.depot.repo, "rev-parse", "refs/remotes/origin/main")
        self.assertEqual(self.lancer("npm ci"), (0, ""))
        self.assertEqual(git(self.depot.repo, "rev-parse", "refs/remotes/origin/main"), avant)

    # --- la forme ---

    def test_formes_refusees(self):
        formes = (
            "npm ci --offline", "npm ci --ignore-scripts", "npm ci --no-audit", "npm --prefix mothra ci", "npm -w server ci",
            "npm --workspace=web ci", "npm --loglevel silent ci",
            "npm clean-install", "npm ic", "npm install-clean", "npm cleanInstall", "npm isntall-clean",
            "env npm ci", "env NODE_ENV=test npm ci", "timeout 600 npm ci", "/opt/homebrew/bin/npm ci",
            "~/.local/share/fnm/aliases/default/bin/npm ci", "sh -c 'npm ci'", "bash -c 'npm ci'", "time npm ci", "nohup npm ci",
            "cd x; npm ci", "cd mothra; npm ci", "npm ci && npm test", "npm ci; echo ok", "npm ci | tail", "npm ci > sortie.txt",
            "npm ci 2>&1", "echo x && npm ci", "ls && cd mothra && npm ci", "cd mothra && npm ci && npm test", "cd mothra && npm ci | tail",
            "A=1 npm ci", "NODE_ENV=test npm ci", "(npm ci)", "{ npm ci; }", "npm ci &", "npm ci # note", "npm ci\nls", "npm ci\n",
            "npm  ci --force", "cd mothra && cd .. && npm ci", "cd -P mothra && npm ci", "cd && npm ci",
            "cd mothra && env npm ci", "npm ci $(echo)", "echo $(npm ci)",
            'cd "$D" && npm ci', "cd $D && npm ci", "cd ~ && npm ci", "cd ~/x && npm ci", "cd * && npm ci", "cd mo* && npm ci",
            "cd mothra/{a,b} && npm ci", "cd $(pwd) && npm ci", "cd `pwd` && npm ci", "cd ${HOME}/x && npm ci", "cd '' && npm ci",
        )
        for commande in formes:
            with self.subTest(commande=commande):
                self.refuse(commande, FORME, cwd=self.wt if commande.startswith("cd mothra") else self.mothra)

    def test_forme_refusee_arrete_les_autres_conditions(self):
        self.depot.ecrire(self.wt, "README.md", "modifié\n")
        self.depot.verrou_de_fin()
        erreur = self.refuse("npm ci --offline", FORME)
        self.assertNotIn(";", erreur.split(PREFIXE, 1)[1].split(". Une session", 1)[0])

    def test_npm_ci_nu_sans_dossier_courant(self):
        self.refuse("npm ci", FORME, cwd=None)

    def test_cd_relatif_sans_dossier_courant(self):
        self.refuse("cd mothra && npm ci", FORME, cwd=None)

    def test_dossier_courant_relatif_ou_vide(self):
        for cwd in ("mothra", ""):
            with self.subTest(cwd=cwd):
                self.refuse("npm ci", FORME, cwd=cwd)

    def test_dossier_courant_qui_n_est_pas_un_texte(self):
        from aide_npm_ci import npm_guard
        import contextlib
        import io
        import json
        erreur = io.StringIO()
        entree = json.dumps({"tool_name": "Bash", "tool_input": {"command": "npm ci"}, "cwd": 3})
        with contextlib.redirect_stderr(erreur):
            self.assertEqual(npm_guard.main([], entree, worktrees=self.depot.worktrees), 2)
        self.assertIn(FORME, erreur.getvalue())

    # --- formes hors npm ci : le chemin habituel ---

    def test_les_autres_commandes_npm_gardent_leur_message(self):
        code, erreur = self.lancer("npm install fastify")
        self.assertEqual(code, 2)
        self.assertTrue(erreur.startswith("garde npm : refusé : npm install"), erreur)
        code, erreur = self.lancer("npm ci && npm install")
        self.assertEqual(code, 2)
        self.assertTrue(erreur.startswith("garde npm : refusé : npm ci; npm install"), erreur)

    def test_commande_permise_apres_npm_ci_admis(self):
        self.assertEqual(self.lancer("npm test"), (0, ""))


class CrochetEnProcessus(AvecDepot):
    """Le script lancé comme Claude Code le lance : le JSON du hook sur l'entrée standard, avec son cwd. Le dossier des worktrees est alors
    celui que résout le module des chemins du lab : le dossier `worktrees` à côté du dossier de contenu (ici `repo`), ou la variable du
    lab PMZILLA_LAB_WORKTREES quand elle est posée."""

    def lancer_script(self, commande, **variables):
        import json
        import subprocess
        env = {k: v for k, v in os.environ.items() if k != "PMZILLA_LAB_WORKTREES" and not k.startswith("GIT_")}
        env.update(variables)
        return subprocess.run([sys.executable, str(Path(__file__).resolve().parents[2] / "tools" / "npm_guard.py")],
                              input=json.dumps({"tool_name": "Bash", "tool_input": {"command": commande}, "cwd": str(self.mothra)}),
                              capture_output=True, text=True, timeout=30, env=env)

    def test_dossier_des_worktrees_resolu_par_le_module_des_chemins(self):
        """B1 : le dossier de contenu vient de la racine de code de la garde ou de PMZILLA_LAB_WORKSPACE, jamais du dépôt visé."""
        r = self.lancer_script("npm ci", PMZILLA_LAB_WORKSPACE=str(self.depot.repo))
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_depot_jetable_avec_un_dossier_worktrees_voisin_refuse(self):
        """B1, cas rouge : sans la variable du lab, le lab est celui de la garde ; un dépôt hors de lui n'est pas admis même avec un
        dossier `worktrees` à côté de lui."""
        r = self.lancer_script("npm ci")
        self.assertEqual(r.returncode, 2)
        self.assertIn(WORKTREE, r.stderr)

    def test_depot_jetable_voisin_refuse_en_processus_sans_parametre(self):
        import contextlib
        import io
        import json
        import npm_guard
        erreur = io.StringIO()
        entree = json.dumps({"tool_name": "Bash", "tool_input": {"command": "npm ci"}, "cwd": str(self.mothra)})
        with unittest.mock.patch.dict(os.environ, {}, clear=False), contextlib.redirect_stderr(erreur):
            os.environ.pop("PMZILLA_LAB_WORKSPACE", None)
            self.assertEqual(npm_guard.main([], entree), 2)
        self.assertIn(WORKTREE, erreur.getvalue())

    def test_variable_du_lab_vers_un_autre_depot_refuse(self):
        r = self.lancer_script("npm ci", PMZILLA_LAB_WORKSPACE=self._tmp.name)
        self.assertEqual(r.returncode, 2)
        self.assertIn(WORKTREE, r.stderr)

    def test_variable_du_lab_vers_un_autre_dossier(self):
        r = self.lancer_script("npm ci", PMZILLA_LAB_WORKSPACE=str(self.depot.repo), PMZILLA_LAB_WORKTREES=str(Path(self._tmp.name) / "autre"))
        self.assertEqual(r.returncode, 2)
        self.assertIn(WORKTREE, r.stderr)
        self.assertNotIn("Traceback", r.stderr)


class LigneAfficheeParWorktree(unittest.TestCase):
    """R-20261110-35 : la commande que tools/worktree.sh affiche sans terminal (après son préfixe « non installées : ») est une forme
    admise par la garde npm ; la même avec --offline ne l'est pas. Remplace : rien. Retrait : avec l'exception de la garde (npm-ci-session)."""

    PREFIXE = "dépendances npm de Mothra non installées : "

    def commande_affichee(self, dossier):
        source = (Path(__file__).resolve().parents[2] / "tools" / "worktree.sh").read_text(encoding="utf-8")
        trouve = re.search(r"a_taper=\"\$\(printf '([^']*)' \"\$dossier/mothra\"\)\"", source)
        self.assertIsNotNone(trouve, "la construction de a_taper n'est plus reconnue dans tools/worktree.sh")
        self.assertIn(f'echo "{self.PREFIXE}$a_taper"', source)
        return trouve.group(1).replace("%q", dossier + "/mothra")

    def test_la_ligne_affichee_est_admise_par_la_garde(self):
        ligne = self.commande_affichee("/chemin/du/lab/worktrees/wt-essai")
        self.assertEqual(ligne, "cd /chemin/du/lab/worktrees/wt-essai/mothra && npm ci")
        self.assertIsNotNone(npm_ci_conditions.forme_admise(ligne, "/"))

    def test_la_variante_avec_offline_n_est_pas_admise(self):
        ligne = self.commande_affichee("/chemin/du/lab/worktrees/wt-essai") + " --offline"
        self.assertIsNone(npm_ci_conditions.forme_admise(ligne, "/"))


if __name__ == "__main__":
    unittest.main()
