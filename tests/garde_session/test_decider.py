"""Garde de session, niveau 1 (change session-guard-n1, tâche 7.1) : la fonction pure `decider` de tools/garde_session.py, une classe de test par
règle du design (D4 et D6) et le cas de l'analyseur en échec (D1). Chaque refus nomme sa classe de l'audit #629.

    bash tests/run_all.sh garde_session

Aucun processus : la fonction lit la commande par l'analyseur de tools/npm_guard.py. Le contrôle de la configuration effective de Git (D4) est coupé
ici ; test_configuration_effective.py le couvre sur des dépôts jetables.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide import Arbre, g  # noqa: E402


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = Arbre()

    @classmethod
    def tearDownClass(cls):
        cls.a.fermer()

    def refuse(self, cle, commandes, cwd=None):
        for commande in commandes:
            with self.subTest(commande=commande):
                self.assertEqual(self.a.cle(commande, cwd), cle)

    def passe(self, commandes, cwd=None):
        for commande in commandes:
            with self.subTest(commande=commande):
                self.assertIsNone(self.a.cle(commande, cwd))


class GitPoussee(Base):
    """A1 : push, send-pack et http-push, après des options globales normalisées, sous tous les lanceurs."""

    def test_push_et_ses_deux_cousins(self):
        self.refuse("A1", ("git push", "git push origin main", "git send-pack x", "git http-push x", "git push --dry-run"))

    def test_options_globales_devant_push(self):
        self.refuse("A1", ("git -c k=v push", "git --no-pager push", "git -P push", "git -p push", "git --work-tree=/chemin/fictif push",
                           "git -C /x push", "git -C /x -C y push origin", "git --git-dir=/x/.git push", "git --git-dir /x/.git push",
                           "git --namespace n push", "git --bare push", "git --literal-pathspecs push", "git -c core.quotepath=false push"))

    def test_lanceurs_et_chaines(self):
        self.refuse("A1", ("env git push", "/usr/bin/git push", "command git push", "exec git push", "cd /x && git push", "cd /x; git push",
                           "ls | git push", "bash -c 'git push'", "sh -c \"cd x && git push origin\"", "echo $(git push)", "nohup git push",
                           "time git push", "xargs git push", "FOO=1 git push", "git status && git push"))


class GitAlias(Base):
    """A2 : toute sous-commande hors des deux classes est refusée, alias compris."""

    def test_alias_et_sous_commande_inconnue(self):
        self.refuse("A2", ("git bm x main", "git foo", "git clone x", "git --weird status", "git ph origin", "git -C x ph"))

    def test_les_sous_commandes_admises_passent(self):
        self.passe(("git status", "git log --oneline -3", "git show abc:f", "git diff HEAD", "git rev-parse HEAD", "git ls-files", "git grep -n x",
                    "git blame f", "git cat-file -p x", "git describe", "git shortlog", "git fetch", "git version", "git help", "git --version", "git",
                    "git for-each-ref", "git worktree list", "git branch", "git branch -a", "git branch --show-current", "git merge-base a b",
                    "git add x", "git commit -m x", "git rebase main", "git -C /x rebase main", "git restore --staged x", "git switch x",
                    "git cherry-pick abc", "git revert abc", "git mv a b", "git rm a", "git clean -n", "git tag v1", "git notes list", "git stash",
                    "git stash list", "git worktree add ../x", "git am p", "git apply p"),   # git reset --soft : refusé (R-20261108-04, 3 a)
                    cwd=self.a.wt)


class GitArbres(Base):
    """A3 : git qui écrit l'arbre de l'espace de travail ou de run ; la même commande dans un worktree reste permise."""

    def test_ecritures_de_l_arbre_de_l_espace(self):
        self.refuse("A3", ("git reset --hard", "git reset --hard HEAD~1", "git checkout -- .", "git checkout -- tools/x.py", "git checkout .",
                           "git restore x", "git restore --staged x", "git stash pop", "git stash apply", "git apply p.diff"), cwd=self.a.espace)

    def test_par_option_globale_et_par_cd(self):
        self.refuse("A3", (f"git -C {self.a.espace} reset --hard", f"git -C {self.a.espace}/ restore x", f"git --work-tree={self.a.espace} reset --hard",
                           f"cd {self.a.espace} && git restore x", "git -C ~/PMZilla-Lab/workspace restore x", f"git -C {self.a.run} apply p"),
                    cwd=self.a.wt)

    def test_arbre_de_run(self):
        self.refuse("A3", ("git reset --hard", "git restore x"), cwd=self.a.run)

    def test_meme_commande_dans_un_worktree(self):
        self.passe(("git checkout -- .", "git restore x", "git stash pop", "git apply p.diff"), cwd=self.a.wt)
        # R-20261108-06 point 2 : `--hard` est refusé sous toutes ses formes dans un worktree
        self.refuse("A6-reset", ("git reset --hard", f"git -C {self.a.wt} reset --hard"), cwd=self.a.wt)

    def test_commandes_de_l_espace_qui_restent_permises(self):
        self.passe(("git checkout main", "git checkout -b x", "git stash", "git stash list", "git status", "git commit -m x",
                    "git add x"), cwd=self.a.espace)


class GitSecurityEtScripts(Base):
    """A4 : `security` sous toutes ses formes. A5 : les scripts du fragment 07, sous tous les lanceurs et toutes les formes de chemin."""

    def test_security_sous_toutes_ses_formes(self):
        self.refuse("A4", ("security", "security -q", "security find-generic-password -s x", "/usr/bin/security -q", "env security -q",
                           "command security x", "exec security x", "xcrun security x", "bash -c 'security dump-keychain -d'", "FOO=1 security x",
                           "sudo security x", "ls && security x", "echo $(security x)", "env -i /usr/bin/security x"))

    def test_nommer_security_sans_le_lancer_passe(self):
        self.passe(("echo security", "grep -n security docs/x.md", "ls security-notes", "cat docs/security.md"))

    def test_scripts_reserves_par_chaque_lanceur(self):
        for script in sorted(g.SCRIPTS_RESERVES):
            formes = (f"bash tools/{script}", f"sh ./tools/{script}", f"zsh ~/PMZilla-Lab/workspace/tools/{script}", f"source tools/{script}",
                      f". tools/{script}", f"tools/{script}", f"./tools/{script}", f"/x/tools/{script} --y", f"uv run tools/{script}",
                      f"nohup bash tools/{script}", f"time bash tools/{script}", f"env FOO=1 bash tools/{script}", f"exec tools/{script}",
                      f"command tools/{script}", f"bash -x tools/{script} a b", f"cd /x && bash {script}", f"bash $HOME/PMZilla-Lab/run/tools/{script}")
            self.refuse("A5", formes)

    def test_launchctl_des_routines(self):
        self.refuse("A5", ("launchctl unload ~/Library/LaunchAgents/com.pmzilla.db-backup.plist", "launchctl kickstart gui/501/com.pmzilla.offsite-copy"))

    def test_lire_ou_versionner_un_script_reserve_passe(self):
        self.passe(("cat tools/finish_train.sh", "git add tools/finish_train.sh", "bash tests/run_all.sh x", "bash tools/db_up.sh", "head -5 tools/doctor.sh",
                    "launchctl list"))


class GitConfiguration(Base):
    """A6 : crochets sautés, réglages hors liste blanche, git config en écriture, variables qui déplacent la configuration."""

    def test_options_qui_sautent_les_crochets(self):
        self.refuse("A6-saute", ("git commit --no-verify -m x", "git commit --no-verif -m x", "git commit --no-v -m x", "git commit -n -m x",
                                 "git commit -anm x", "git commit -nm x", "git commit -m x -n", "git rebase --no-verify", "git merge --no-verify x",
                                 "git am --no-verify p", "git -C /x commit --no-verify"), cwd=self.a.wt)

    def test_commits_ordinaires(self):
        self.passe(("git commit -m x", "git commit -am x", "git commit -mnew", "git commit -m 'note --no-verify'", "git commit -F msg", "git commit --amend --no-edit",
                    "git commit -m -n", "git log -n 5", "git commit -S -m x"), cwd=self.a.wt)

    def test_reglages_hors_liste_blanche(self):
        self.refuse("A6-reglage", ("git -c core.hooksPath=/x commit -m y", "git -c core.hookspath=/x status", "git -c CORE.HOOKSPATH=/x status",
                                   "git -c include.path=x status", "git -c user.name=x status", "git -c alias.p=push status",
                                   "git --config-env=core.hooksPath=V status", "git --config-env core.hookspath=V status",
                                   "git -c core.quotepath=false -c core.editor=x status"))

    def test_reglages_de_la_liste_blanche(self):
        self.passe(("git -c core.quotepath=false status", "git -c color.ui=always log", "git -c Color.UI=always log", "git -c advice.detachedHead=false log",
                    "git -c core.quotePath=off diff"))

    def test_git_config_en_ecriture(self):
        self.refuse("A6-config", ("git config core.hooksPath /x", "git config --global core.hookspath /x", "git config --add a b", "git config --unset a",
                                  "git config --unset-all a", "git config --replace-all a b", "git config --rename-section a b",
                                  "git config --remove-section a", "git config --edit", "git config -e", "git config set a b", "git config unset a",
                                  "git config user.name Bob", "git config --local a b"))

    def test_git_config_en_lecture(self):
        self.passe(("git config --get user.name", "git config user.name", "git config --list", "git config -l", "git config get user.name",
                    "git config --get-all core.hooksPath", "git config --show-origin --list", "git config list", "git config --get-regexp alias"))

    def test_variables_qui_deplacent_la_configuration(self):
        self.refuse("A6-variable", ("GIT_DIR=/x git status", "GIT_CONFIG_COUNT=1 git status", "env GIT_TRACE=1 git status", "export GIT_CONFIG_GLOBAL=/x; git status",
                                    "HOME=/tmp git status", "XDG_CONFIG_HOME=/x git status",
                                    "declare -x GIT_X=1", "GIT_TRACE=1 echo hi", "/usr/bin/env GIT_TRACE=1 git push-not", "typeset GIT_X=1",
                                    "cd /x && GIT_DIR=y ls", "bash -c 'GIT_DIR=y ls'"))

    def test_variables_ordinaires(self):
        self.passe(("PMZILLA_NO_EVALS=1 git status", "export FOO=1", "FOO=1 git status", "env FOO=1 git status", "GITHUB=1 ls"))


class Gh(Base):
    """B : `gh` hors de la liste fermée (issue view, issue list, --version), options lues où qu'elles soient ; variables de gh."""

    def test_gh_hors_liste(self):
        self.refuse("B", ("gh pr create", "gh pr merge 3", "gh pr list", "gh workflow run x", "gh secret set X", "gh variable set X", "gh gist create",
                          "gh run rerun 1", "gh repo sync", "gh alias set a b", "gh extension install x", "gh auth token", "gh api x", "gh label create x",
                          "gh release create v1", "gh project list", "gh", "gh --help", "gh issue", "gh issue create", "gh issue comment 3",
                          "gh issue edit 3", "gh foo", "env gh pr create", "/opt/homebrew/bin/gh pr list", "echo x | gh pr create", "gh -R o/r pr list",
                          "gh issue --repo o/r create"))

    def test_la_liste_fermee(self):
        self.passe(("gh issue view 12", "gh issue list", "gh issue list --label x --json number", "gh issue view 12 --comments", "gh --version",
                    "gh -R o/r issue view 3", "gh issue --repo o/r view 3", "gh issue --repo=o/r list", "env gh issue view 3",
                    "/opt/homebrew/bin/gh issue list", "gh --hostname h issue view 3"))

    def test_variables_de_gh(self):
        self.refuse("B-variable", ("GH_TOKEN=x gh issue list", "env GH_HOST=h gh issue view 1", "export GH_CONFIG_DIR=/x; gh issue list", "GH_TOKEN=x echo hi",
                                   "declare -x GH_TOKEN=x"))


class GhIssue(Base):
    """C3 : tools/gh_issue.py se lance depuis la copie de l'espace de travail seulement ; le lire reste permis."""

    def test_depuis_la_copie_de_l_espace(self):
        self.passe(("uv run tools/gh_issue.py status R-62 x", "python3 tools/gh_issue.py --help", "tools/gh_issue.py x", "./tools/gh_issue.py x",
                    f"uv run {self.a.espace}/tools/gh_issue.py x", "python3 ~/PMZilla-Lab/workspace/tools/gh_issue.py --help",
                    "uv run --with pyyaml tools/gh_issue.py x"), cwd=self.a.espace)

    def test_depuis_la_copie_de_l_espace_par_son_chemin_dans_un_worktree(self):
        self.passe((f"uv run {self.a.espace}/tools/gh_issue.py x", "uv run ~/PMZilla-Lab/workspace/tools/gh_issue.py x",
                    "python3 ~/PMZilla-Lab/workspace/tools/gh_issue.py x"), cwd=self.a.wt)

    def test_depuis_une_autre_copie(self):
        self.refuse("C3", ("uv run tools/gh_issue.py x", "python3 tools/gh_issue.py --help", "tools/gh_issue.py x", "./tools/gh_issue.py x",
                           f"uv run {self.a.wt}/tools/gh_issue.py x", "uv run $X/tools/gh_issue.py x", f"cd {self.a.wt} && uv run tools/gh_issue.py x",
                           "python3 -I tools/gh_issue.py x", f"uv run {self.a.run}/tools/gh_issue.py x"), cwd=self.a.wt)
        self.refuse("C3", ("uv run tools/gh_issue.py x",), cwd=self.a.run)

    def test_lire_le_script_passe(self):
        self.passe(("cat tools/gh_issue.py", "head -40 tools/gh_issue.py", "grep -n def tools/gh_issue.py", "git add tools/gh_issue.py", "ls tools/gh_issue.py"),
                   cwd=self.a.wt)


class EcrituresDuShell(Base):
    """C : redirections, tee, cp, mv, rm, ln, sed -i, touch, chmod et dd of= vers un chemin protégé (workspace, run, réglages partout)."""

    def test_vers_l_espace_de_travail(self):
        self.refuse("C", ("echo x > tools/npm_guard.py", "echo x >> .claude/settings.json", "echo x >| tools/hooks/pre-commit", "echo x &> tools/pipe_guard.py",
                          "tee tools/hooks/pre-commit", "tee -a .claude/deny/26-git-push-merge.txt", "cp /tmp/x tools/pipe_guard.py", "cp -t tools/hooks /tmp/x",
                          "cp a tools/hooks/", "mv x tools/garde_session.py", "rm tools/hooks/pre-commit", "rm -f tools/lab_paths.py", "ln -sf /tmp/x tools/lab_paths.py",
                          "sed -i s/a/b/ tools/npm_guard.py", "sed -i '' s/a/b/ .claude/deny/26-git-push-merge.txt", "sed -i.bak s/a/b/ tools/gh_issue.py",
                          "touch .claude/settings.json", "chmod +x tools/hooks/pre-commit", "dd if=/dev/zero of=tools/gh_issue.py",
                          "cd tools && echo x > npm_guard.py", "cd tools/hooks && tee pre-commit", "cat a | tee tools/secret_scan.py", "mv tools/hooks/pre-commit /tmp/x"),
                    cwd=self.a.espace)

    def test_par_chemin_absolu_ou_personnel(self):
        self.refuse("C", (f"echo x > {self.a.espace}/tools/pipe_guard.py", "echo x > ~/PMZilla-Lab/workspace/tools/pipe_guard.py",
                          f"tee {self.a.run}/tools/hooks/pre-commit", f"cp x {self.a.run}/.claude/settings.json"), cwd=self.a.wt)

    def test_reglages_partout(self):
        self.refuse("C", (f"echo x > {self.a.wt}/.claude/settings.json", "echo x > .claude/settings.json", "echo x > ~/.claude/settings.json",
                          "echo x > ~/.claude/settings.local.json", f"tee -a {self.a.wt}/.claude/settings.local.json", f"sed -i s/a/b/ {self.a.autre}/.claude/settings.base.json"),
                    cwd=self.a.wt)

    def test_ce_qui_reste_permis(self):
        self.passe(("echo x > tools/npm_guard.py", "tee tools/hooks/pre-commit", "echo x > .claude/deny/x.txt", "rm tools/lab_paths.py", "touch tools/hooks/x"), cwd=self.a.wt)
        self.passe(("echo x > notes.txt", "cp tools/npm_guard.py /tmp/x", "cat tools/npm_guard.py", "rm /tmp/x", "sed -n 1,5p tools/npm_guard.py",
                    "touch tools/nouvel_outil.py", "echo x > tools/hooks.txt", "ls > /tmp/x", "echo x > /dev/null", "git log > /tmp/log", "sed -i s/a/b/ notes.txt",
                    "cp a b", "chmod +x tools/outil_libre.sh", "dd if=a of=/tmp/b", "ln -s a b"), cwd=self.a.espace)


class VariablesDeReglage(Base):
    """E : l'affectation d'une variable de réglage des gardes refuse la commande, unset et env -u compris ; la nommer seulement passe."""

    def test_affectations(self):
        self.refuse("E", ("PMZILLA_SKIP_GREEN_CHECK=1 git status", "FINISH_LOCK_TOKEN=x ls", "export PMZILLA_LAB_WORKSPACE=/x", "env PMZILLA_LAB_RUN=/x ls",
                          "DB_BACKUP_SAUVEGARDES=/x ls", "DB_BACKUP_FOO=1 ls", "PRE_PUSH_RUNNER=true ls", "PMZILLA_GH=/x/gh ls", "CDPATH=/x ls", "declare -x PMZILLA_NOMS=/x",
                          "CLAUDECODE= ls", "CI_LOCAL_PREUVES_INDEX=x ls", "PMZILLA_AFTER_COMMIT=1 ls", "PMZILLA_FINISH_LOCK_MAX_AGE=99999 ls", "ls && FINISH_LOCK_NAME=x ls",
                          "bash -c 'PMZILLA_LAB_DATA=/x ls'"))

    def test_unset_et_env_moins_u(self):
        self.refuse("E", ("unset PMZILLA_SKIP_GREEN_CHECK", "unset FINISH_LOCK_TOKEN", "env -u FINISH_LOCK_TOKEN ls", "env -uCLAUDECODE ls",
                          "env --unset=CLAUDECODE ls", "env --unset CLAUDECODE ls", "unset DB_BACKUP_X"))

    def test_les_nommer_sans_les_poser_passe(self):
        self.passe(("grep -n PMZILLA_SKIP docs/x.md", "echo $PMZILLA_LAB_RUN", "PMZILLA_NO_EVALS=1 git commit -m x", "PMZILLA_LAB_DB_PORT=5433 bash tests/run_all.sh x",
                    "unset FOO", "env -u FOO ls", "echo FINISH_LOCK_TOKEN", "FOO=1 ls"), cwd=self.a.wt)


class Docker(Base):
    """G : docker sur la vraie base, compose du projet du lab, montages, destructions ; les noms viennent du fichier compose, jamais de la garde."""

    def test_conteneur_avec_montage(self):
        self.refuse("G", ("docker run -v volume-fictif:/data image-fictive", "docker run --rm -v /Users/x:/data img", "docker run --volume=pmzilla-lab_pgdata:/d img",
                          "docker run --mount type=bind,src=/,dst=/h img", "docker create -v x:/y img", "docker container run -v x:/y img",
                          "docker run -v /var/run/docker.sock:/var/run/docker.sock img", "docker run --volumes-from db img", "docker run -vx:/y img",
                          "docker run --mount=type=volume,src=pmzilla-lab_pgdata,dst=/d img", "docker -H unix:///x run -v a:/b img",
                          "docker run img --privileged -v /:/h"))

    def test_compose_du_projet_du_lab(self):
        self.refuse("G", ("docker compose run service-fictif", "docker compose up -d", "docker compose -p pmzilla-lab ps", "docker compose -f docker-compose.yml ps",
                          "docker-compose ps", "docker compose --project-name pmzilla-lab logs", "docker -H unix:///x compose ps",
                          f"docker compose -f {self.a.espace}/docker-compose.yml ps", f"docker compose --project-directory {self.a.wt} ps"), cwd=self.a.espace)
        self.refuse("G", ("docker compose ps",), cwd=self.a.wt)

    def test_compose_destructif_quel_que_soit_le_projet(self):
        self.refuse("G", ("docker compose down -v", "docker compose down --volumes", "docker compose -p autre down -v", "docker-compose down -v"), cwd=self.a.autre)

    def test_destructions(self):
        self.refuse("G", ("docker volume rm pmzilla-lab_pgdata", "docker volume remove x", "docker volume prune", "docker system prune --volumes",
                          "docker system prune -a --volumes", "colima delete", "limactl delete colima", "colima delete --force"), cwd=self.a.autre)

    def test_ce_qui_reste_permis(self):
        self.passe(("docker ps", "docker images", "docker run --rm hello-world", "docker run --rm img echo hi", "docker compose -p autre ps",
                    f"docker compose -f {self.a.autre}/docker-compose.yml ps", "docker logs x", "docker volume ls", "docker system prune", "colima status",
                    "limactl list", "docker -H unix:///x ps", "docker volume inspect x"), cwd=self.a.autre)
        self.passe(("docker compose ps", "docker compose up -d"), cwd=self.a.autre)
        self.passe(("docker compose -p autre ps",), cwd=self.a.espace)

    def test_fichier_compose_illisible_refuse_les_compose(self):
        self.assertEqual(self.a.cle("docker compose ps", self.a.autre, compose=self.a.tmp + "/absent.yml"), "G")


class SkillEnQuarantaine(Base):
    """H : toute commande qui nomme le skill en quarantaine ou ses scripts est refusée."""

    def test_nommer_le_skill(self):
        self.refuse("H", ("cat .claude/quarantaine/bmad-eval-runner/SKILL.md.quarantaine", "ls .claude/skills/bmad-eval-runner",
                          "python3 .claude/skills/bmad-eval-runner/scripts/run.py", "echo bmad-eval-runner", "grep -n bmad-eval-runner x"))

    def test_les_autres_skills_passent(self):
        self.passe(("ls .claude/skills", "echo eval", "cat .claude/skills/bmad-help/SKILL.md"))


class AnalyseurEnEchec(Base):
    """D1 : une analyse en échec refuse seulement si le texte brut contient un mot surveillé."""

    def test_mot_surveille_refuse(self):
        for commande in ("git push 'oops", "security '", 'bash -c "gh pr create', "echo $(git push", "docker run -v a:/b 'x", "ls && git status \"",
                         "FINISH_LOCK_TOKEN=x ls '", "cat .claude/skills/bmad-eval-runner/x '", "tee tools/hooks/x '"):
            with self.subTest(commande=commande):
                self.assertEqual(self.a.cle(commande), "entree-illisible")

    def test_sans_mot_surveille_passe(self):
        self.passe(("echo 'abc", 'echo "abc', "echo $(abc", "ls 'x", "cat a | grep 'b"))

    def test_imbrication_excessive(self):
        profonde = "$(" * 12 + "git push" + ")" * 12
        self.assertEqual(self.a.cle(profonde), "entree-illisible")
        self.assertIsNone(self.a.cle("$(" * 12 + "ls" + ")" * 12))


class CommandesOrdinaires(Base):
    """Le travail courant d'une session passe : aucune règle ne doit gêner ces commandes."""

    def test_commandes_courantes(self):
        self.passe(("ls -la", "cat tools/npm_guard.py", "uv run tools/pilot.py freeze --check && bash tests/run_all.sh garde_session", "bash tests/run_all.sh settings_deny",
                    "git -C ~/PMZilla-Lab/worktrees/wt-feat-essai rebase main", "uv run tools/roadmap.py next --budget 2h", "gh issue list", "python3 -W ignore x.py",
                    "echo 'git push' > /tmp/x", "grep -n 'git push' docs/x.md", "git commit -F msg.txt", "head -40 tools/garde_session.py", "node --version",
                    "git log --oneline -5 -- tools/hooks/pre-commit"), cwd=self.a.wt)


class Verdicts(unittest.TestCase):
    """D10 : le verdict porte la classe, la clé, la forme et la voie ; le message est l'unique ligne du design."""

    def test_message(self):
        v = g.verdict("A1")
        self.assertEqual(g.message(v), "garde de session : refusé : A1 : git push, send-pack ou http-push. Voie permise : le train lancé par l'auteur.")
        self.assertEqual((v.classe, v.cle), ("A1", "A1"))

    def test_la_table_du_design(self):
        attendu = {
            "A1": ("A1", "git push, send-pack ou http-push", "le train lancé par l'auteur"),
            "A2": ("A2", "sous-commande git inconnue ou alias", "la sous-commande git écrite en toutes lettres"),
            "A3": ("A3", "git qui écrit l'arbre de l'espace de travail ou de run", "la même commande dans un worktree"),
            "A4": ("A4", "security", "aucune en session : le Trousseau reste à l'auteur"),
            "A5": ("A5", "script réservé à l'auteur", "un fichier d'étape de l'auteur"),
            "A6-saute": ("A6", "option qui saute les crochets", "la même commande sans cette option"),
            "A6-reglage": ("A6", "réglage git hors liste blanche", "les clés core.quotepath, color.* et advice.* seulement"),
            "A6-config": ("A6", "git config en écriture", "git config en lecture ; un réglage passe par un fichier d'étape de l'auteur"),
            "A6-variable": ("A6", "variable qui déplace la configuration de git", "la même commande sans cette variable"),
            "A6-hookspath": ("A6", "core.hooksPath défini", "le signaler à l'auteur"),
            "A6-liens": ("A6", "liens des crochets non conformes", "le signaler à l'auteur, qui réinstalle les crochets"),
            "B": ("B", "gh hors liste fermée", "gh issue view ou gh issue list ; pour écrire, tools/gh_issue.py"),
            "B-variable": ("B", "variable de gh", "la même commande sans cette variable"),
            "C3": ("C3", "gh_issue.py hors de la copie de l'espace de travail", "la copie de l'espace de travail, par son chemin"),
            "C": ("C", "écriture du shell vers un chemin protégé",
                  "une branche dans un worktree, puis un train ; un réglage passe par un fichier d'étape de l'auteur"),
            "E": ("E", "variable de réglage des gardes", "la même commande sans cette variable"),
            "G": ("G", "docker sur la vraie base, compose du projet, montage de l'hôte ou destruction", "bash tools/ci_local.sh run <branche>"),
            "H": ("H", "skill en quarantaine", "aucune avant le go ou no-go de BMAD 7 et une revue Opus"),
            "entree-illisible": ("—", "entrée illisible", "relancer la commande ; si le refus revient, le signaler"),
            "erreur-interne": ("—", "erreur interne de la garde", "relancer la commande ; si le refus revient, le signaler"),
        }
        self.assertEqual(g.FORMES, attendu)

    def test_chaque_verdict_a_sa_classe_ecrite_dans_le_message(self):
        for cle in g.FORMES:
            with self.subTest(cle=cle):
                self.assertIn(f": {g.FORMES[cle][0]} : ", g.message(g.verdict(cle)))


class ErreurInterne(Base):
    def test_une_exception_d_une_regle_refuse(self):
        original = g.regle_git
        g.regle_git = lambda args, c: 1 / 0
        try:
            self.assertEqual(self.a.cle("git status"), "erreur-interne")
        finally:
            g.regle_git = original


if __name__ == "__main__":
    unittest.main()
