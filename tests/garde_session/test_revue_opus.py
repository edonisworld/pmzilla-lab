"""Garde de session, niveau 1 (change session-guard-n1) : les contournements trouvés par la revue Opus de tools/garde_session.py et de l'analyseur partagé
tools/npm_guard.py, chacun avec un test de refus et un test de passage pour la forme légitime voisine. Numéros : ceux des constats de la revue.

    bash tests/run_all.sh garde_session

Aucun processus, sauf les essais du hook (constat 14). Le contrôle de la configuration effective de Git est coupé ici (voir test_configuration_effective.py).
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide import Arbre, RACINE, g  # noqa: E402

OUTIL = RACINE / "tools" / "garde_session.py"


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


class Constat1SousXargs(Base):
    """Sous xargs (et find -exec), les arguments viennent de l'entrée : git et docker sont refusés ; sans sous-commande lisible aussi."""

    def test_git_sous_xargs(self):
        self.refuse("A2", ("echo push | xargs git", "xargs git", "xargs -n1 git status", "echo x | xargs git log", "find . -name x -exec git rm {} ;"))

    def test_git_sans_sous_commande_lisible(self):
        self.refuse("A2", ("git $SOUS", 'git "$SOUS" origin'))

    def test_docker_sous_xargs(self):
        self.refuse("G", ("echo x | xargs docker", "xargs docker run alpine", "xargs docker compose up", "xargs docker-compose up", "find . -exec docker rm {} ;"))

    def test_docker_sans_sous_commande_lisible(self):
        self.refuse("G", ("docker $SOUS -v /:/h alpine", "docker $SOUS"))

    def test_la_forme_voisine_passe(self):
        self.passe(("xargs echo", "echo a | xargs -n1 echo", "find . -name x -exec echo {} ;", "git status", "git log --oneline", "docker ps", "git --version"))

    def test_push_sous_xargs_garde_sa_cle(self):
        self.refuse("A1", ("xargs git push", "echo x | xargs git send-pack"))


class Constat2BinairesGit(Base):
    """`git-<x>` en un mot vaut `git <x>`."""

    def test_binaires_de_poussee(self):
        self.refuse("A1", ("git-push origin main", "git-send-pack x", "/usr/lib/git-core/git-push", "env git-push", "git-http-push x"))

    def test_autres_binaires(self):
        self.refuse("A6-config", ("git-config user.name x", "git-config --add alias.x y"))
        self.refuse("A2", ("git-update-ref refs/heads/x HEAD", "git-receive-pack /depot", "git-upload-pack /depot", "git-foo"))

    def test_la_forme_voisine_passe(self):
        self.passe(("git-log --oneline", "git-status", "git-config --get user.name", "git-diff HEAD"))


class Constat3XcrunEtLaunchctl(Base):
    def test_xcrun_deplie_comme_env(self):
        self.refuse("A1", ("xcrun git push", "xcrun -sdk macosx git push", "xcrun --sdk macosx git push", "xcrun -toolchain x git push origin"))
        self.refuse("A2", ("xcrun git foo",))
        self.refuse("A4", ("xcrun security find-generic-password", "xcrun -sdk macosx security x"))
        self.refuse("G", ("xcrun docker run -v /:/h alpine",))

    def test_xcrun_voisin_passe(self):
        self.passe(("xcrun git status", "xcrun --sdk macosx git log", "xcrun clang --version", "xcrun -sdk macosx --show-sdk-path", "xcrun"))

    def test_launchctl_qui_lance_une_commande(self):
        self.refuse("A5", ("launchctl submit -l x -- /bin/sh", "launchctl asuser 501 /bin/sh", "launchctl bsexec 1 /bin/sh"))

    def test_launchctl_voisin_passe(self):
        self.passe(("launchctl list", "launchctl print system", "launchctl print-disabled system"))


class Constat4OptionsQuiLancent(Base):
    def test_rebase_exec(self):
        self.refuse("A6-commande", ("git rebase --exec make main", "git rebase --exec=make main", "git rebase -x make main", "git rebase -xmake main",
                                    "git rebase -ix make main", "git rebase --ex make main", "git rebase --exe=make main"))

    def test_grep_pager(self):
        self.refuse("A6-commande", ("git grep -O vim x", "git grep -Ovim x", "git grep -nO x", "git grep --open-files-in-pager=vim x",
                                    "git grep --open-files-in-pager vim x", "git grep --open=vim x"))

    def test_upload_pack_et_receive_pack(self):
        self.refuse("A6-commande", ("git fetch --upload-pack=/x/y origin", "git fetch --upload-pack /x/y origin", "git fetch --upl=/x origin",
                                    "git clone --upload-pack=/x/y depot", "git ls-remote --upload-pack=/x depot", "git ls-remote --exec=/x depot"))
        self.refuse("A1", ("git push --receive-pack=/x origin", "git push --exec=/x origin"))

    def test_exec_path(self):
        self.refuse("A6-commande", ("git --exec-path=/tmp/x fetch", "git --exec-path=/tmp/x status"))

    def test_reglage_de_commande_deja_refuse(self):
        self.refuse("A6-reglage", ("git -c core.sshCommand=/x fetch", "git -c core.pager=/x log", "git -c core.fsmonitor=/x status"))

    def test_la_forme_voisine_passe(self):
        self.passe(("git rebase main", "git rebase -i main", "git rebase --continue", "git rebase --abort", "git grep -n foo", "git grep -e foo -- tools",
                    "git grep -l --no-index foo", "git fetch origin", "git fetch --all", "git fetch --prune origin", "git --exec-path", "git log --exclude=x"))


class Constat5DossierCourant(Base):
    def commandes_vers_l_espace(self):
        return (f"cd {self.a.espace} && git restore x", f'cd "$HOME/PMZilla-Lab/workspace" && git restore x', f"cd -P {self.a.espace} && git restore x",
                f"cd -L {self.a.espace} && git restore x", f"cd -e -P {self.a.espace} && git restore x", f"cd -- {self.a.espace} && git restore x")

    def test_cd_saute_ses_options_et_home_est_connue(self):
        self.refuse("A3", self.commandes_vers_l_espace(), cwd=self.a.wt)

    def test_seule_home_est_connue(self):
        self.refuse("A3", ('cd "$PWD" && git restore x', 'cd $OLDPWD && git restore x', 'cd "$CLAUDE_PROJECT_DIR" && git restore x',
                           'cd "$TMPDIR" && git restore x', "cd - && git restore x"), cwd=self.a.wt)

    def test_un_cd_vers_un_dossier_connu_hors_des_arbres_passe(self):
        self.passe((f"cd {self.a.wt} && git restore x", f'cd "$HOME" && git restore x', "cd && git restore x", f"cd -P {self.a.autre} && git restore x"),
                   cwd=self.a.espace)

    def test_pushd_est_suivi(self):
        self.refuse("A3", (f"pushd {self.a.espace} && git restore x", f"pushd {self.a.espace} >/dev/null; git restore x"), cwd=self.a.wt)

    def test_popd_revient_au_dossier_d_avant(self):
        self.passe((f"pushd {self.a.espace} >/dev/null; popd >/dev/null; git restore x",), cwd=self.a.wt)
        self.refuse("A3", (f"pushd {self.a.wt} >/dev/null; popd >/dev/null; git restore x",), cwd=self.a.espace)

    def test_pushd_ou_popd_inconnu(self):
        self.refuse("A3", ("popd && git restore x", "pushd && git restore x", "pushd +1 && git restore x", 'pushd "$X" && git restore x'), cwd=self.a.wt)

    def test_les_redirections_suivent_les_memes_cd(self):
        self.refuse("C", (f"cd -P {self.a.espace} && echo x > tools/hooks/pre-commit", f"pushd {self.a.espace} && echo x > .claude/settings.json"), cwd=self.a.wt)
        self.passe((f"cd -P {self.a.wt} && echo x > tools/hooks/pre-commit",), cwd=self.a.espace)


class Constat6Redirections(Base):
    def protege(self, nom="tools/hooks/pre-commit"):
        return f"{self.a.espace}/{nom}"

    def test_variables_remplacees_avant_la_resolution(self):
        self.refuse("C", ('echo x > "$HOME/PMZilla-Lab/workspace/tools/hooks/pre-commit"', "echo x > ${HOME}/PMZilla-Lab/workspace/.claude/settings.json",
                          "echo x >> $HOME/PMZilla-Lab/workspace/tools/garde_session.py"))

    def test_les_autres_variables_sont_inconnues_mais_leur_fin_compte(self):
        self.refuse("C", ('echo x > "$PWD/.claude/settings.json"', 'echo x > "$CLAUDE_PROJECT_DIR/tools/hooks/pre-commit"',
                          'echo x > "$X/tools/npm_guard.py"', "echo x > $(pwd)/tools/gh_issue.py"))

    def test_les_ecritures_de_toutes_les_formes(self):
        cible = self.protege()
        self.refuse("C", (f"echo x >& {cible}", f"echo x &> {cible}", f"echo x &>> {cible}", f"echo x <> {cible}", f"echo x >> {cible}", f"echo x >| {cible}",
                          f"echo x 2>{cible}", f"echo x 2>& {cible}"))

    def test_la_forme_voisine_passe(self):
        cible = self.protege()
        self.passe(("echo x >&2", "echo x 2>&1", "echo x >&-", "echo x > /dev/null", "ls &> /dev/null", f"cat < {cible}", f"cat <&0", "echo x > $HOME/notes.txt",
                    'echo x > "$X/notes.txt"', 'echo x > "$PWD/tools/autre.py"', "echo x >> $HOME/PMZilla-Lab/workspace/docs/notes.md",
                    f"cat {cible} > /dev/null", "echo x <<< y"))


class Constat7CiblesInconnues(Base):
    def test_ecriture_git_dont_l_arbre_est_inconnu(self):
        self.refuse("A3", ('cd "$X" && git commit -m x', 'git -C "$(pwd)" add x', 'git -C "$X" restore y', 'cd $(mktemp -d) && git add x'), cwd=self.a.wt)

    def test_lecture_git_dont_l_arbre_est_inconnu_passe(self):
        self.passe(('cd "$X" && git status', 'git -C "$(pwd)" log', 'git -C "$X" diff'), cwd=self.a.wt)

    def test_ecriture_git_dont_l_arbre_est_connu_passe(self):
        self.passe((f"git -C {self.a.wt} add x", f'cd "$HOME" && git commit -m x'), cwd=self.a.espace)

    def test_cible_d_ecriture_inconnue_dont_la_fin_est_protegee(self):
        self.refuse("C", ('tee "$X/tools/hooks/pre-commit"', 'cp a "$X/.claude/settings.json"', "cp a $(pwd)/tools/garde_session.py",
                          'sed -i s/a/b/ "$X/tools/npm_guard.py"', 'rm "$X/.claude/settings.local.json"', 'mv a "$X/tools/finish_lock.py"',
                          "touch $PWD/tools/hooks/commit-msg"))

    def test_cible_d_ecriture_inconnue_ordinaire_passe(self):
        self.passe(('tee "$X/notes.txt"', 'cp a "$X/tools/autre.py"', 'sed -i s/a/b/ "$X/docs/a.md"', 'rm "$X/tmp/x"', "touch $PWD/notes"))


class Constat8BrancheSurMain(Base):
    def test_abreviations_des_options_longues(self):
        self.refuse("A6-main", ("git branch --mov --forc main x", "git branch --move --force main x", "git branch --mov -f main x", "git branch --cop --force x main",
                                "git branch --copy --forc x main", "git branch -M main x", "git branch -fm x main"))

    def test_main_sans_tenir_compte_des_majuscules(self):
        self.refuse("A6-main", ("git branch -M Main x", "git branch -M x MAIN", "git branch --mov --forc x Main", "git branch -M x refs/heads/Main"))

    def test_cible_inconnue(self):
        self.refuse("A6-main", ('git branch -M "$X" y', "git branch -M x $(echo main)", "git branch --mov --forc x $Y", "git branch -C a ${B}"))

    def test_la_forme_voisine_passe(self):
        self.passe(("git branch -M feature autre", "git branch --move ancien nouveau", "git branch --mov ancien nouveau", "git branch --forc x",
                    "git branch --list", "git branch --lis", "git branch --show-current", "git branch -d vieille", "git branch -M x autre"))

    def test_ecriture_detectee_sur_les_abreviations(self):
        for mots in (["--dele", "x"], ["--mov", "a", "b"], ["--cop", "a", "b"], ["--forc", "x"], ["--set-upstream-t=origin/x"], ["--unset-up"]):
            with self.subTest(mots=mots):
                self.assertTrue(g._branche_ecrit(mots))
        for mots in (["--lis"], ["--list"], ["--show-cur"], ["--merg", "x"], ["--contain", "x"]):
            with self.subTest(mots=mots):
                self.assertFalse(g._branche_ecrit(mots))
        self.assertEqual(g._canonique_branch("--co"), "--co")   # ambigu (color, column, contains, copy) : laissé tel quel, Git refuse aussi


class Constat9VariablesPoseesSansEgal(Base):
    def test_variables_surveillees_posees_puis_exportees(self):
        self.refuse("A6-variable", ("printf -v GIT_DIR x", "printf -vGIT_DIR x", "printf -v GIT_DIR %s x; export GIT_DIR", "read GIT_DIR", "read -r GIT_DIR",
                                    "for GIT_DIR in a b; do echo x; done", "select GIT_DIR in a b; do break; done", "declare GIT_DIR", "typeset GIT_DIR",
                                    "local GIT_DIR", "readonly GIT_DIR", "export GIT_DIR", "export -n GIT_DIR", "mapfile GIT_DIR", "read HOME",
                                    "read XDG_CONFIG_HOME"))
        self.refuse("E", ("read PMZILLA_GH", "printf -v CI_LOCAL_PREUVES_INDEX %s x", "for PMZILLA_SKIP_GREEN_CHECK in 1; do :; done", "export FINISH_LOCK_TOKEN",
                          "declare DB_BACKUP_SAUVEGARDES", "local CLAUDECODE"))
        self.refuse("B-variable", ("printf -v GH_TOKEN %s x", "read GH_HOST", "export GH_CONFIG_DIR"))

    def test_la_forme_voisine_passe(self):
        self.passe(("export FOO", "read ligne", "read -r a b", "printf -v sortie %s x", "for f in a b; do echo $f; done", "declare -x BAR", "local n",
                    "export PATH_PERSO", "printf '%s' GIT_DIR", "echo GIT_DIR", "export GIT_EDITOR=true; git rebase --continue", "select x in a b; do break; done"))


class Constat10GhIssueEnModule(Base):
    def test_python_m_gh_issue(self):
        self.refuse("C3", ("python3 -m gh_issue", "python -m gh_issue view 1", "python3 -m gh_issue.cli", "python3 -I -m gh_issue", "python3 -Im gh_issue",
                           "python3 -mgh_issue", "python3.14 -W ignore -m gh_issue"))

    def test_python_qui_lit_gh_issue_sur_l_entree(self):
        self.refuse("C3", ("python3 - < tools/gh_issue.py", "python3 < tools/gh_issue.py", "cat tools/gh_issue.py | python3 -", "cat tools/gh_issue.py | python3",
                           "cat tools/gh_issue.py | tr a b | python3 -", "bash -c 'cat tools/gh_issue.py | python3 -'", f"python3 - < {self.a.wt}/tools/gh_issue.py"))

    def test_la_forme_voisine_passe(self):
        self.passe(("python3 -m unittest", "python3 -m json.tool x.json", "cat tools/gh_issue.py", "cat tools/gh_issue.py | wc -l", "python3 - < tools/autre.py",
                    "echo 'print(1)' | python3 -", "python3 tools/gh_issue.py", "grep -n def tools/gh_issue.py", "python3 -c 'print(1)'",
                    "cat tools/gh_issue.py; python3 -"))


class Constat11DockerAmasDOptions(Base):
    def test_volume_dans_un_amas(self):
        self.refuse("G", ("docker run -itv /:/h alpine", "docker run -itv/:/h alpine", "docker run -dv /x:/y alpine", "docker run -v/:/h alpine",
                          "docker create -itv /x:/y alpine", "docker container run -itv /:/h alpine", "docker run --volume /:/h alpine",
                          "docker run --volume=/:/h alpine", "docker run -it --mount type=bind,src=/,dst=/h alpine", "docker run --mount=type=bind,src=/,dst=/h alpine",
                          "docker run --volumes-from x alpine", "docker run -itvx alpine"))

    def test_la_forme_voisine_passe(self):
        self.passe(("docker run -it alpine", "docker run --rm -e A=b -p 80:80 alpine", "docker run -ti --name x alpine", "docker ps -a", "docker run -d -u 1000 alpine",
                    "docker run -itp 80:80 alpine", "docker run -e V=1 alpine"))


class Constat14Crochet(unittest.TestCase):
    """Toute exception sort en 2 ; un autre outil bien formé passe ; seul un objet sans tool_name lisible est refusé."""

    @classmethod
    def setUpClass(cls):
        cls.a = Arbre()

    @classmethod
    def tearDownClass(cls):
        cls.a.fermer()

    def lancer(self, texte, outil=None):
        return subprocess.run([sys.executable, "-I", str(outil or OUTIL)], input=texte, capture_output=True, text=True, cwd=self.a.tmp, timeout=60)

    def test_objet_sans_tool_name_lisible_refuse(self):
        for texte in ("{}", '{"cwd": "/x"}', '{"tool_input": {"command": "ls"}}', '{"tool_name": 3}', '{"tool_name": null}', '{"tool_name": ""}',
                      '{"tool_name": ["Bash"]}', '{"tool_name": {"a": 1}, "tool_input": {"command": "ls"}}'):
            with self.subTest(texte=texte):
                r = self.lancer(texte)
                self.assertEqual((r.returncode, r.stdout), (2, ""))
                self.assertTrue(r.stderr.startswith("garde de session : refusé : — : entrée illisible"))

    def test_objet_bien_forme_d_un_autre_outil_passe(self):
        for outil in ("Edit", "Read", "Write", "Grep", "WebFetch", "mcp__serveur__outil"):
            with self.subTest(outil=outil):
                r = self.lancer(json.dumps({"tool_name": outil, "tool_input": {"file_path": "/x", "command": "git push"}, "cwd": self.a.tmp}))
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_module_voisin_absent_sort_en_2(self):
        with tempfile.TemporaryDirectory() as dossier:
            copie = Path(dossier) / "garde_session.py"
            copie.write_bytes(OUTIL.read_bytes())   # sans npm_guard.py à côté : l'import échoue
            for commande in ("ls", "git push"):
                with self.subTest(commande=commande):
                    r = self.lancer(json.dumps({"tool_name": "Bash", "tool_input": {"command": commande}, "cwd": self.a.tmp}), copie)
                    self.assertEqual((r.returncode, r.stdout), (2, ""))
                    self.assertTrue(r.stderr.startswith("garde de session : refusé"))
                    self.assertNotIn("Traceback", r.stderr)

    def test_module_voisin_absent_laisse_passer_un_autre_outil(self):
        with tempfile.TemporaryDirectory() as dossier:
            copie = Path(dossier) / "garde_session.py"
            copie.write_bytes(OUTIL.read_bytes())
            r = self.lancer(json.dumps({"tool_name": "Edit", "tool_input": {}}), copie)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_octets_illisibles_sur_l_entree_sortent_en_2(self):
        r = subprocess.run([sys.executable, "-I", str(OUTIL)], input=b"\xff\xfe\x00{", capture_output=True, cwd=self.a.tmp, timeout=60)
        self.assertEqual((r.returncode, r.stdout), (2, b""))
        self.assertTrue(r.stderr.decode("utf-8").startswith("garde de session : refusé"))

    def test_lire_entree_rend_none_si_la_lecture_leve(self):
        class Casse:
            def read(self):
                raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "octet invalide")

        class Ferme:
            def read(self):
                raise ValueError("I/O operation on closed file")

        class Memoire:
            def read(self):
                raise MemoryError

        for flux in (Casse(), Ferme(), Memoire()):
            with self.subTest(flux=type(flux).__name__):
                self.assertIsNone(g.lire_entree(flux))

        class Bon:
            def read(self):
                return "texte"
        self.assertEqual(g.lire_entree(Bon()), "texte")

    def test_refuser_rend_2_meme_si_la_sortie_d_erreur_est_cassee(self):
        class Casse:
            def write(self, texte):
                raise BrokenPipeError

            def flush(self):
                raise BrokenPipeError
        original = sys.stderr
        sys.stderr = Casse()
        try:
            self.assertEqual(g.refuser(g.verdict("A1")), 2)
        finally:
            sys.stderr = original

    def test_main_sans_tool_name_rend_2(self):
        self.assertEqual(g.main([], '{"tool_input": {"command": "ls"}}', self.a.contexte()), 2)
        self.assertEqual(g.main([], '{"tool_name": "Edit", "tool_input": {}}', self.a.contexte()), 0)


if __name__ == "__main__":
    unittest.main()
