"""Règles `deny` d'écriture dans un dossier `.git` (change team-names-readable, design D12, tâche 11.1, idée #398, spec tooling-permission-guards).

La session n'écrit jamais dans un dossier `.git` (le `.git/` de l'espace principal, le fichier `.git` d'un worktree, le dossier git commun et son
`worktrees/` : crochets, empreintes, verrou de fin, config), ni avec les outils d'édition, ni par une commande Bash d'écriture. Les commandes git
ordinaires et la lecture restent permises. Une règle deny compare le texte de la commande ou le chemin édité, jamais ce qu'un processus fait une
fois lancé : les limites de D12 (scripts, `sh -c`, `cd .git && …`, `git config`) ne sont pas refusées et sont énoncées plus bas.

 - REGLES_ATTENDUES (223) pour `.claude/settings.json`, dans l'ordre de D12 : 8 règles `Edit(`, 210 règles de commandes de fichiers
   (cp mv rm touch chmod ln mkdir : 140 ; tee : 30 ; sed -i : 40 ; cinq cibles par préfixe), 5 redirections ;
 - REGLES_DEJA_LA (5) sont déjà dans le fichier (verrou de fin de branche), non dupliquées, et doivent y rester.

Conception (même motif que test_settings_deny_push_merge.py) : l'auteur pose les règles (tâche 9.1). La suite reste VERTE avant et après :
 - la matrice des formes s'applique au bloc déclaré, toujours ;
 - les tests « dans le fichier de réglages » sont SAUTÉS tant qu'aucune règle du bloc n'y est, ÉCHOUENT dès que le bloc est partiel (ils nomment
   les règles absentes) et rejouent la matrice contre les règles RÉELLES quand tout y est.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/test_settings_deny_git_dir.py --json            (les 223 règles pour .claude/settings.json)
"""
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import garde_regles  # noqa: E402
from test_settings_deny_story_quality import Moteur  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"

# --- Les règles de D12 --------------------------------------------------------------------------------------------------------------------

EDITION = (
    "Edit(./.git/**)", "Edit(//**/.git/**)", "Edit(~/**/.git/**)", "Edit(**/.git/**)",
    "Edit(./.git)", "Edit(//**/.git)", "Edit(~/**/.git)", "Edit(**/.git)",
)

# Cinq cibles par préfixe, dans cet ordre : un chemin dans un dossier .git, un chemin qui finit par .git, ce chemin suivi d'un argument,
# ce chemin fermé par un guillemet double, ce chemin fermé par un guillemet simple.
CIBLES = ("*.git/*", "*.git", "*.git *", '*.git"*', "*.git'*")

COMMANDES_FICHIERS = ("cp", "mv", "rm", "touch", "chmod", "ln", "mkdir")
PREFIXES_COMMANDE = ("{c} ", "*/{c} ", "*&& {c} ", "*; {c} ")
PREFIXES_TEE = ("tee ", "*/tee ", "*&& tee ", "*; tee ", "*| tee ", "*|tee ")
# Sans espace final : `-i''` et `-i.bak` sont couverts.
PREFIXES_SED = ("sed -i", "*/sed -i", "*&& sed -i", "*; sed -i", "sed * -i", "*/sed * -i", "*&& sed * -i", "*; sed * -i")

REDIRECTIONS = ("Bash(*>*.git/*)", "Bash(*>*.git)", "Bash(*>*.git *)", 'Bash(*>*.git"*)', "Bash(*>*.git'*)")


def _bash(prefixe: str) -> tuple:
    return tuple(f"Bash({prefixe}{cible})" for cible in CIBLES)


FICHIERS = tuple(
    regle
    for commande in COMMANDES_FICHIERS for prefixe in PREFIXES_COMMANDE for regle in _bash(prefixe.format(c=commande))
)
TEE = tuple(regle for prefixe in PREFIXES_TEE for regle in _bash(prefixe))
SED = tuple(regle for prefixe in PREFIXES_SED for regle in _bash(prefixe))

REGLES_ATTENDUES = EDITION + FICHIERS + TEE + SED + REDIRECTIONS

REGLES_DEJA_LA = (
    "Bash(rm *pmzilla-fin-en-cours*)", "Bash(rmdir *pmzilla-fin-en-cours*)", "Bash(mv *pmzilla-fin-en-cours*)",
    "Bash(mkdir *pmzilla-fin-en-cours*)", "Bash(touch *pmzilla-fin-en-cours*)",
)

PHRASE = "règle(s) d'écriture dans .git absente(s) de .claude/settings.json (conception D12)"


def regles_attendues() -> list:
    """Les 223 règles à ajouter à permissions.deny de .claude/settings.json (imprimées par --json)."""
    return list(REGLES_ATTENDUES)


# --- Formes de commande -------------------------------------------------------------------------------------------------------------

ESPACE = "~/PMZilla-Lab/workspace"
ESPACE_ABS = "/Users/quelquun/PMZilla-Lab/workspace"
WORKTREE = "~/PMZilla-Lab/worktrees/wt-feat-x"
WORKTREE_ABS = "/Users/quelquun/PMZilla-Lab/worktrees/wt-feat-x"

# Un argument par cible : dans un dossier .git ; qui finit par .git (le fichier d'un worktree) ; .git suivi d'un autre argument ;
# .git fermé par un guillemet double ; .git fermé par un guillemet simple.
ARGUMENTS = {"*.git/*": ".git/hooks/pre-commit", "*.git": f"{WORKTREE}/.git", "*.git *": ".git x", '*.git"*': '".git"', "*.git'*": "'.git'"}
# Le lanceur d'exemple de chaque préfixe, jusqu'à l'argument (le même texte vaut pour toutes les cibles).
LANCEURS_COMMANDE = {"{c} ": "{c} ", "*/{c} ": "/bin/{c} ", "*&& {c} ": "cd /x && {c} ", "*; {c} ": "true; {c} "}
LANCEURS_TEE = {"tee ": "tee ", "*/tee ": "/usr/bin/tee ", "*&& tee ": "cd /x && tee ", "*; tee ": "true; tee ",
                "*| tee ": "echo x | tee ", "*|tee ": "echo x |tee "}
LANCEURS_SED = {"sed -i": "sed -i '' s/a/b/ ", "*/sed -i": "/usr/bin/sed -i '' s/a/b/ ", "*&& sed -i": "cd /x && sed -i.bak s/a/b/ ",
                "*; sed -i": "true; sed -i s/a/b/ ", "sed * -i": "sed -e s/a/b/ -i ", "*/sed * -i": "/usr/bin/sed -e s/a/b/ -i ",
                "*&& sed * -i": "cd /x && sed -e s/a/b/ -i ", "*; sed * -i": "true; sed -e s/a/b/ -i "}


def cas_par_regle():
    """(règle, commande) : la commande que cette règle, et elle seule, doit refuser."""
    familles = [(commande, LANCEURS_COMMANDE) for commande in COMMANDES_FICHIERS] + [("tee", LANCEURS_TEE), ("sed", LANCEURS_SED)]
    for commande, lanceurs in familles:
        for prefixe, lanceur in lanceurs.items():
            motif = prefixe.format(c=commande)
            for cible in CIBLES:
                yield f"Bash({motif}{cible})", lanceur.format(c=commande) + ARGUMENTS[cible]


# Les refus énumérés par D12 (« Tests first »).
REFUSEES_D12 = (
    "echo x > .git/hooks/pre-commit", "echo x >> .git/pmzilla-run-all-ok", f"printf x > {ESPACE}/.git/pmzilla-dbtest-ok",
    "cp tools/hooks/pre-commit .git/hooks/pre-commit", "mv /tmp/x .git/config", "rm .git/pmzilla-finish-tested", "rm -rf .git", "rm .git",
    "mv .git .git.bak", 'echo "gitdir: /x" > .git', "touch .git/pmzilla-run-all-ok", "echo x | tee .git/hooks/pre-commit",
    "chmod +x .git/hooks/pre-commit", "ln -sf ../../tools/hooks/pre-commit .git/hooks/pre-commit", "mkdir -p .git/hooks",
    "sed -i '' s/a/b/ .git/config", "sed -e s/a/b/ -i .git/config", "/bin/rm .git/x", "cd /x && rm .git/x", "true; touch .git/x",
    f"rm {ESPACE}/.git/worktrees/wt-feat-x/gitdir", f"touch {ESPACE_ABS}/.git/worktrees/wt-feat-x/locked",
    f"echo x > {ESPACE_ABS}/.git/worktrees/wt-feat-x/gitdir", f"mv /tmp/x {ESPACE}/.git/worktrees/wt-feat-x/HEAD",
    # le fichier `.git` d'un worktree et le dossier git commun
    f"rm {WORKTREE}/.git", f"echo 'gitdir: /x' > {WORKTREE_ABS}/.git", f"cp /tmp/x {WORKTREE}/.git", f"mv {WORKTREE_ABS}/.git /tmp/y",
    f"cd {WORKTREE} && rm .git", f"cd {WORKTREE}; rm .git", "rm -f ../../.git/hooks/pre-commit", "chmod 644 .git/pmzilla-fin-en-cours-x",
    f"ln -s /tmp/x {WORKTREE}/.git", "mkdir .git", f"touch {WORKTREE_ABS}/.git",
    # chemin `.git` entre guillemets
    'rm -rf ".git"', "rm -rf '.git'", "mv '.git' x", 'echo x > ".git"',
    # redirections en tout genre
    "echo x 2> .git/hooks/x", "echo x >| .git/config", "date >> .git/pmzilla-run-all-ok", "echo x > ./.git/hooks/post-commit",
    f"echo x | tee -a {ESPACE}/.git/config", "echo x |tee .git/config", "cat x | tee .git/hooks/y",
)

# Effets énoncés par D12 (« Effects stated, not hidden »), assertés refusés.
EFFETS_D12 = (
    "git status 2>&1 | grep .git/", "git status 2>&1 | grep .git", "cat x 2>/dev/null; ls .git/hooks",
    'git commit -m "voir -> .git/hooks"', "ls x 2>&1 | grep .git ",
    "rm -rf remote.git", "rm remote.git/x", "touch remote.git", "cp x remote.git/y", "mv remote.git remote.git.old",
    "cp .git/config /tmp/x",
    'git commit -m "x; rm .git/y"', 'git commit -m "x && touch .git/y"', 'git commit -m "x; rm -rf .git"',
    # forme permise par le cadrage du verrou de fin (R-75), interdite volontairement depuis D12 : aucune écriture dans .git
    "rm .git/pmzilla-notes-sans-rapport/x",
)

# Permis : le bloc ne doit refuser aucun de ces cas (D12, « Allowed, not matched »).
PERMISES_D12 = (
    "git status", "git status --short", "git log", "git log --oneline -3", "git log origin/main..main", "git add tools/x.py",
    "git add .gitignore", "git commit -m x", "git commit -m 'correctif'", "git commit -m 'maj .gitignore et .github'", "git fetch",
    "git fetch origin", "git worktree list", "git rev-parse --git-common-dir", "git rev-parse --show-toplevel", "git diff origin/main",
    "git branch --show-current", f"git -C {WORKTREE} status", f"git -C {WORKTREE} log --oneline -3",
    f"git --git-dir={ESPACE_ABS}/.git log", f"git --git-dir {ESPACE}/.git log --oneline",
    "cat .git/HEAD", "head -3 .git/config", "ls -la .git/hooks", 'grep -rn "rm " .git/hooks', f"cat {ESPACE}/.git/config",
    "tail -5 .git/pmzilla-run-all-ok", "cat .git",
    "touch .gitignore", "echo x >> .gitignore", "sed -i '' s/a/b/ .gitignore", "mkdir -p .github/workflows",
    "mv .gitignore .gitignore.bak", "cp .github/workflows/a.yml .github/workflows/b.yml", "rm .gitattributes",
    "touch tools/x.py", "rm tools/x.py", "mv tools/a.py tools/b.py", "chmod +x tools/x.sh", "ln -s a b", "mkdir -p tmp/x",
    "sed -i '' s/a/b/ tools/x.py", "echo x > tools/x.txt", "echo x | tee tools/x.txt",
    'grep -rn "git push" docs', 'git grep -n "rm .git"', "bash tests/run_all.sh settings_deny", "uv run tools/pilot.py freeze --wait 60",
)

# Limites énoncées par D12 : non refusées par une règle.
LIMITES_D12 = (
    "cd .git && rm hooks/x", "cd .git; touch pmzilla-run-all-ok", "git config core.hooksPath x", "git update-ref refs/x HEAD",
    "install x .git/hooks/y", "dd if=x of=.git/y", "truncate -s 0 .git/y", "rsync x .git/y", "ditto x .git/y", "rmdir .git/x",
    "sed --in-place s/a/b/ .git/config", "sh -c 'rm .git/x'", "bash -c 'touch .git/x'",
)

# Chemins de l'outil d'édition : (chemin, vrai si une règle Edit( du bloc doit le couvrir).
CHEMINS_EDIT_REFUSES = (
    ".git/hooks/pre-commit", "./.git/hooks/pre-commit", ".git/config", "./.git/config", ".git/pmzilla-run-all-ok",
    ".git/worktrees/wt-feat-x/gitdir", ".git", "./.git", "../.git", "../worktrees/wt-feat-x/.git", "tools/.git/x",
    f"{ESPACE_ABS}/.git/hooks/pre-commit", f"{ESPACE_ABS}/.git/config", f"{ESPACE_ABS}/.git/worktrees/wt-feat-x/gitdir",
    f"{WORKTREE_ABS}/.git", f"{ESPACE_ABS}/.git",
    f"{ESPACE}/.git/hooks/pre-commit", f"{ESPACE}/.git/config", f"{WORKTREE}/.git", f"{ESPACE}/.git/worktrees/wt-feat-x/HEAD",
)
CHEMINS_EDIT_PERMIS = (
    ".gitignore", "./.gitignore", ".gitattributes", ".github/workflows/ci.yml", "./.github/workflows/ci.yml", "tools/gitdir.py",
    f"{ESPACE_ABS}/.gitignore", f"{ESPACE_ABS}/.github/workflows/ci.yml", f"{ESPACE}/.gitattributes", f"{WORKTREE}/.gitignore",
    f"{WORKTREE_ABS}/.github/x.yml", "tools/hooks/pre-commit", "docs/pmzilla/installation.md", "remote.gitx/a",
)


def refusees():
    """Toutes les commandes que le bloc doit refuser."""
    yield from REFUSEES_D12
    yield from EFFETS_D12
    for _regle, commande in cas_par_regle():
        yield commande
    yield from REDIRECTIONS_REFUSEES


REDIRECTIONS_REFUSEES = tuple(f"echo x {op} {cible}" for op in (">", ">>", "2>", ">|", "&>") for cible in (
    ".git/hooks/pre-commit", ".git", ".git x", f"{ESPACE}/.git/config", f"{WORKTREE_ABS}/.git"))


def non_refusees(moteur: Moteur, commandes) -> list:
    return [c for c in commandes if moteur.interdite(c)]


def deny_de(chemin: Path) -> list:
    return json.loads(chemin.read_text(encoding="utf-8")).get("permissions", {}).get("deny", [])


# --- Le bloc déclaré ----------------------------------------------------------------------------------------------------------------------

class Declaration(unittest.TestCase):
    def test_comptes(self):
        self.assertEqual(len(EDITION), 8)
        self.assertEqual((len(FICHIERS), len(TEE), len(SED), len(REDIRECTIONS)), (140, 30, 40, 5))
        self.assertEqual(len(FICHIERS) + len(TEE) + len(SED), 210)
        self.assertEqual(len(regles_attendues()), 223)
        self.assertEqual(len([r for r in regles_attendues() if r.endswith(('"*)', "'*)"))]), 86)
        self.assertEqual(len(REGLES_DEJA_LA), 5)

    def test_ordre_de_d12(self):
        regles = regles_attendues()
        self.assertEqual(regles[:8], list(EDITION))
        self.assertEqual(regles[8:148], list(FICHIERS))
        self.assertEqual(regles[148:178], list(TEE))
        self.assertEqual(regles[178:218], list(SED))
        self.assertEqual(regles[218:], list(REDIRECTIONS))

    def test_exemples_litteraux_de_d12(self):
        regles = regles_attendues()
        self.assertEqual(regles[:8], [
            "Edit(./.git/**)", "Edit(//**/.git/**)", "Edit(~/**/.git/**)", "Edit(**/.git/**)",
            "Edit(./.git)", "Edit(//**/.git)", "Edit(~/**/.git)", "Edit(**/.git)",
        ])
        index = regles.index("Bash(rm *.git/*)")
        self.assertEqual(regles[index:index + 10], [
            "Bash(rm *.git/*)", "Bash(rm *.git)", "Bash(rm *.git *)", 'Bash(rm *.git"*)', "Bash(rm *.git'*)",
            "Bash(*/rm *.git/*)", "Bash(*/rm *.git)", "Bash(*/rm *.git *)", 'Bash(*/rm *.git"*)', "Bash(*/rm *.git'*)",
        ])
        index = regles.index("Bash(sed -i*.git/*)")
        self.assertEqual(regles[index:index + 5], [
            "Bash(sed -i*.git/*)", "Bash(sed -i*.git)", "Bash(sed -i*.git *)", 'Bash(sed -i*.git"*)', "Bash(sed -i*.git'*)"])
        self.assertEqual(regles[8:13], ["Bash(cp *.git/*)", "Bash(cp *.git)", "Bash(cp *.git *)", 'Bash(cp *.git"*)', "Bash(cp *.git'*)"])
        self.assertEqual(regles[-5:], ["Bash(*>*.git/*)", "Bash(*>*.git)", "Bash(*>*.git *)", 'Bash(*>*.git"*)', "Bash(*>*.git'*)"])
        self.assertEqual(regles.index("Bash(*|tee *.git'*)"), 177)
        self.assertEqual(regles.index('Bash(*; sed * -i*.git"*)'), 216)
        self.assertIn("Bash(*| tee *.git/*)", regles)
        self.assertIn("Bash(*|tee *.git *)", regles)
        self.assertIn("Bash(sed * -i*.git)", regles)
        self.assertIn("Bash(*; sed * -i*.git *)", regles)

    def test_la_garde_partagee_passe_la_liste(self):
        self.assertEqual(garde_regles.constats(regles_attendues()), [])

    def test_la_garde_partagee_trouve_la_liste_sans_declaration(self):
        texte = Path(__file__).read_text(encoding="utf-8")
        self.assertTrue(garde_regles.imprime_json(texte))
        self.assertEqual(garde_regles._liste_du_module(Path(__file__), garde_regles.CONVENTION), list(REGLES_ATTENDUES))

    def test_aucune_regle_write_ni_notebookedit_ni_cle_vide(self):
        for regle in regles_attendues() + list(REGLES_DEJA_LA):
            self.assertFalse(regle.startswith(("Write(", "NotebookEdit(")), regle)
            self.assertTrue(regle.startswith(("Bash(", "Edit(")) and regle.endswith(")") and regle not in ("Bash()", "Edit()"), regle)

    def test_seules_les_cinq_redirections_commencent_par_etoile_chevron(self):
        etoiles = [r for r in regles_attendues() if r.startswith("Bash(*>")]
        self.assertEqual(etoiles, list(REDIRECTIONS))

    def test_aucune_autre_regle_ne_commence_par_un_joker_nu(self):
        """Hors redirections, une règle `Bash(` commence par le nom de la commande, `*/`, `*&& `, `*; `, `*| ` ou `*|` (tee)."""
        for regle in regles_attendues():
            if not regle.startswith("Bash(") or regle in REDIRECTIONS:
                continue
            motif = regle[len("Bash("):-1]
            self.assertTrue(not motif.startswith("*") or motif.startswith(("*/", "*&& ", "*; ", "*| tee ", "*|tee ")), regle)

    def test_toute_regle_bash_porte_une_cible_git(self):
        for regle in regles_attendues():
            if regle.startswith("Bash("):
                self.assertTrue(regle.endswith(tuple(cible + ")" for cible in CIBLES)), regle)

    def test_aucun_doublon_et_blocs_disjoints(self):
        tout = regles_attendues() + list(REGLES_DEJA_LA)
        self.assertEqual(len(tout), len(set(tout)))
        self.assertEqual(sorted(set(REGLES_DEJA_LA) & set(regles_attendues())), [])

    def test_aucune_regle_de_lecture_ni_de_git_ordinaire(self):
        """Exclus : Read(, lecteurs, git status/log/add/commit/fetch/worktree/rev-parse."""
        for regle in regles_attendues():
            self.assertFalse(regle.startswith("Read("), regle)
            for exclu in ("git status", "git log", "git add", "git commit", "git fetch", "git worktree", "git rev-parse",
                          "Bash(cat ", "Bash(head ", "Bash(grep ", "Bash(ls "):
                self.assertNotIn(exclu, regle)


class MatriceDuBloc(unittest.TestCase):
    """La matrice contre le bloc déclaré, toujours (vert avant comme après la pose)."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(regles_attendues())

    def test_chaque_ecriture_de_d12_est_refusee(self):
        manquantes = [c for c in REFUSEES_D12 if not self.moteur.interdite(c)]
        self.assertEqual(manquantes, [])

    def test_chaque_redirection_est_refusee(self):
        manquantes = [c for c in REDIRECTIONS_REFUSEES if not self.moteur.interdite(c)]
        self.assertEqual(manquantes, [])

    def test_chaque_commande_chaque_prefixe_chaque_cible(self):
        cas = list(cas_par_regle())
        self.assertEqual(len(cas), 210)
        manquantes = [c for _r, c in cas if not self.moteur.interdite(c)]
        self.assertEqual(manquantes, [])

    def test_chaque_regle_de_commande_est_necessaire(self):
        """Sans elle, la commande qui lui est propre passe : aucune des 210 règles n'est redondante."""
        regles = regles_attendues()
        for regle, commande in cas_par_regle():
            self.assertIn(regle, regles)
            reste = Moteur([r for r in regles if r != regle])
            self.assertFalse(reste.interdite(commande), f"règle redondante : {regle} (commande : {commande})")

    def test_chaque_redirection_est_necessaire(self):
        regles = regles_attendues()
        propres = {"Bash(*>*.git/*)": "echo x > .git/hooks/pre-commit", "Bash(*>*.git)": "echo x > .git",
                   "Bash(*>*.git *)": "echo x > .git x", 'Bash(*>*.git"*)': 'echo x > ".git"', "Bash(*>*.git'*)": "echo x > '.git'"}
        for regle, commande in propres.items():
            self.assertTrue(Moteur(regles).interdite(commande), commande)
            self.assertFalse(Moteur([r for r in regles if r != regle]).interdite(commande), f"règle redondante : {regle}")

    def test_les_formes_d_edition_sont_refusees(self):
        for chemin in CHEMINS_EDIT_REFUSES:
            for outil in ("Edit", "Write"):
                self.assertTrue(self.moteur.acces_interdit(outil, chemin), f"{outil}({chemin})")

    def test_chaque_regle_edit_est_necessaire(self):
        """Les formes absolue, du dossier personnel et à profondeur libre couvrent chacune un chemin que les autres laissent passer.

        Les deux formes `./` ne sont pas testées ici : le moteur du test (comme le glob de Claude Code) laisse `**/` couvrir aussi le chemin
        relatif sans dossier, donc `./.git/**` et `./.git` y sont redondantes ; D12 les garde pour la racine du projet."""
        propres = {
            "Edit(//**/.git/**)": f"{ESPACE_ABS}/.git/hooks/pre-commit",
            "Edit(~/**/.git/**)": f"{ESPACE}/.git/hooks/pre-commit", "Edit(**/.git/**)": "tools/.git/x",
            "Edit(//**/.git)": f"{WORKTREE_ABS}/.git", "Edit(~/**/.git)": f"{WORKTREE}/.git",
            "Edit(**/.git)": "../worktrees/wt-feat-x/.git",
        }
        regles = regles_attendues()
        for regle, chemin in propres.items():
            self.assertTrue(Moteur(regles).acces_interdit("Edit", chemin), f"{regle} : {chemin}")
            reste = Moteur([r for r in regles if r != regle])
            self.assertFalse(reste.acces_interdit("Edit", chemin), f"règle redondante : {regle} (chemin : {chemin})")

    def test_gitignore_gitattributes_et_github_ne_sont_pas_couverts(self):
        for chemin in CHEMINS_EDIT_PERMIS:
            for outil in ("Edit", "Write"):
                self.assertFalse(self.moteur.acces_interdit(outil, chemin), f"{outil}({chemin})")

    def test_effets_enonces_par_d12_refuses(self):
        manquantes = [c for c in EFFETS_D12 if not self.moteur.interdite(c)]
        self.assertEqual(manquantes, [])

    def test_commandes_permises_non_refusees(self):
        self.assertEqual(non_refusees(self.moteur, PERMISES_D12), [])

    def test_limites_enoncees_par_d12_non_refusees(self):
        self.assertEqual(non_refusees(self.moteur, LIMITES_D12), [])


# --- Les règles gardées ---------------------------------------------------------------------------------------------------------------

class RegleGardees(unittest.TestCase):
    """Les 5 règles du verrou de fin de branche : elles doivent rester (échoue dès qu'une manque, avant comme après la pose)."""

    @classmethod
    def setUpClass(cls):
        cls.deny = deny_de(REGLAGES)

    def test_les_cinq_regles_sont_dans_settings_json(self):
        manquantes = [r for r in REGLES_DEJA_LA if r not in self.deny]
        self.assertEqual(manquantes, [], f"{len(manquantes)} règle(s) gardée(s) absente(s) de .claude/settings.json : {manquantes}")

    def test_les_cinq_regles_ne_sont_pas_dupliquees(self):
        self.assertEqual([r for r in REGLES_DEJA_LA if self.deny.count(r) > 1], [])

    def test_ces_regles_refusent_toujours_leurs_cas(self):
        moteur = Moteur(list(REGLES_DEJA_LA))
        for commande in ("rm -rf /tmp/pmzilla-fin-en-cours", "rmdir /tmp/pmzilla-fin-en-cours", "mv /tmp/pmzilla-fin-en-cours /tmp/x",
                         "mkdir /tmp/pmzilla-fin-en-cours", "touch /tmp/pmzilla-fin-en-cours"):
            self.assertTrue(moteur.interdite(commande), commande)

    def test_aucune_regle_du_bloc_n_est_deja_dans_le_fichier_hors_pose(self):
        """Une règle du bloc présente seule (sans les autres) est la pose partielle, nommée par les tests du fichier de réglages."""
        presentes = [r for r in regles_attendues() if r in self.deny]
        self.assertIn(len(presentes), (0, 223), f"pose partielle : {len(presentes)} règle(s) sur 223")


class CommandesPermisesEtReglesExistantes(unittest.TestCase):
    """Les commandes permises contre les règles réelles privées de celles du bloc : même résultat avant et après la pose."""

    def test_aucune_regle_existante_ne_refuse_les_commandes_permises(self):
        deny = deny_de(REGLAGES)
        moteur = Moteur([r for r in deny if r not in regles_attendues()])
        self.assertEqual(non_refusees(moteur, PERMISES_D12), [], "refusées par une règle déjà dans .claude/settings.json (hors bloc de D12)")
        for chemin in CHEMINS_EDIT_PERMIS:
            self.assertFalse(moteur.acces_interdit("Edit", chemin), chemin)


# --- Le fichier de réglages réel ---------------------------------------------------------------------------------------------------

class DansLeFichierDeReglages(unittest.TestCase):
    """Tâche 9.1 : l'auteur pose les 223 règles. Sauté avant, échoue si la pose est partielle, rejoue la matrice si tout y est."""

    @classmethod
    def setUpClass(cls):
        cls.deny = deny_de(REGLAGES)
        cls.presentes = [r for r in regles_attendues() if r in cls.deny]
        cls.manquantes = [r for r in regles_attendues() if r not in cls.deny]

    def avant(self):
        if not self.presentes:
            self.fail("règles de D12 pas encore posées (tâche 9.1, l'auteur)")

    def test_les_223_regles_sont_dans_settings_json(self):
        self.avant()
        self.assertEqual(self.manquantes, [], f"{PHRASE} : {', '.join(self.manquantes)}")

    def test_aucun_doublon_ni_regle_write(self):
        self.avant()
        self.assertEqual(len(self.deny), len(set(self.deny)), "doublon dans permissions.deny")
        self.assertEqual([r for r in self.deny if r.startswith(("Write(", "NotebookEdit("))], [])

    def test_les_regles_gardees_restent_apres_la_pose(self):
        self.avant()
        self.assertEqual([r for r in REGLES_DEJA_LA if r not in self.deny], [])

    def test_la_matrice_contre_les_regles_reelles(self):
        self.avant()
        if self.manquantes:
            self.skipTest("règles partielles : voir test_les_223_regles_sont_dans_settings_json")
        reel = Moteur(self.deny)
        refusees_manquantes = [c for c in refusees() if not reel.interdite(c)]
        self.assertEqual(refusees_manquantes[:5], [], f"{len(refusees_manquantes)} commande(s) de D12 non refusée(s) par les règles réelles")
        self.assertEqual(non_refusees(reel, PERMISES_D12), [])
        for chemin in CHEMINS_EDIT_REFUSES:
            self.assertTrue(reel.acces_interdit("Edit", chemin), chemin)
        for chemin in CHEMINS_EDIT_PERMIS:
            self.assertFalse(reel.acces_interdit("Edit", chemin), chemin)


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    else:
        unittest.main()
