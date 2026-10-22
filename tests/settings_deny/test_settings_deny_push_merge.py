"""Règles `deny` du push et de la fusion (change team-names-readable, design D11, tâche 10.1, idée #387, spec tooling-permission-guards).

La session ne pousse jamais (`git push` sous toutes ses formes, `--dry-run` compris), n'utilise ni `--force` ni `--no-verify` sur une commande
git, ne fusionne pas dans l'espace de travail principal et ne fusionne pas de pull request (`gh pr merge`). Les scripts de fin que l'auteur
lance hors de toute session ne sont pas concernés. Une règle deny compare le texte de la commande, jamais le dossier ni la branche : la fusion
nue (`git merge`) ne peut pas être limitée à l'espace principal dans le fichier partagé, d'où deux blocs :
 - REGLES_ATTENDUES (32) pour `.claude/settings.json` : push, force, saut des crochets, fusion qui nomme l'espace principal, `gh pr merge` ;
 - REGLES_LOCALES (4) pour `.claude/settings.local.json` de l'espace principal (ignoré par Git, jamais porté par un worktree) : `git merge` nu.
Question ouverte 2 de D11, tranchée par l'auteur : ces 4 règles vivent UNIQUEMENT dans `.claude/settings.local.json` de l'espace principal ;
le repli vers `.claude/settings.json` n'est plus accepté, et un test échoue (partout, worktree compris) si l'une d'elles y figure.
REGLES_DEJA_LA (6) sont déjà dans le fichier, non dupliquées, et doivent y rester.

Conception (même motif que test_settings_deny_archives.py) : l'auteur pose les règles (tâche 9.1). La suite reste VERTE avant et après :
 - la matrice des formes s'applique aux blocs déclarés, toujours ;
 - les tests « dans le fichier de réglages » sont SAUTÉS tant qu'aucune règle du bloc n'y est, ÉCHOUENT dès que le bloc est partiel (ils nomment
   les règles absentes) et rejouent la matrice contre les règles RÉELLES quand tout y est ;
 - le fichier local n'est lu que si `.git` est un dossier (espace principal) ; dans un worktree `.git` est un fichier et le test est sauté.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json et, dans l'espace principal, .claude/settings.local.json.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/test_settings_deny_push_merge.py --json            (les 32 règles pour .claude/settings.json)
    python3 tests/settings_deny/test_settings_deny_push_merge.py --json --local    (les 4 règles pour .claude/settings.local.json)
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import garde_regles  # noqa: E402
from test_settings_deny_story_quality import Moteur  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"
REGLAGES_LOCAUX = RACINE / ".claude" / "settings.local.json"
# Sans tools/build_edition.py (exclu de l'édition), l'arbre est celui de l'édition : le refus de la fusion nue vit dans les réglages locaux
# de l'auteur (D11), que l'édition n'a pas (limite connue de ses notes de version).
ARBRE_EDITION = not (RACINE / "tools" / "build_edition.py").is_file()

PUSH = (
    "Bash(git push*)", "Bash(git -C * push*)", "Bash(git --git-dir* push*)", "Bash(cd * && git push*)", "Bash(cd *; git push*)",
    "Bash(env *git push*)", "Bash(env *git -C * push*)", "Bash(*/git push*)", "Bash(*/git -C * push*)", "Bash(*/env *git push*)",
    "Bash(*/env *git -C * push*)",
)
FORCE = (
    "Bash(git *--force*)", "Bash(*/git *--force*)", "Bash(env *git *--force*)", "Bash(*/env *git *--force*)",
    "Bash(cd * && git *--force*)", "Bash(cd *; git *--force*)",
)
SANS_CROCHETS = (
    "Bash(git *--no-verify*)", "Bash(*/git *--no-verify*)", "Bash(env *git *--no-verify*)", "Bash(*/env *git *--no-verify*)",
    "Bash(cd * && git *--no-verify*)", "Bash(cd *; git *--no-verify*)",
)
FUSION_ESPACE = (
    "Bash(git -C *PMZilla-Lab/workspace merge*)", "Bash(git -C *PMZilla-Lab/workspace/ merge*)",
    "Bash(cd *PMZilla-Lab/workspace && git merge*)", "Bash(cd *PMZilla-Lab/workspace; git merge*)",
    "Bash(git --git-dir*PMZilla-Lab/workspace/.git merge*)",
)
FUSION_PR = ("Bash(gh pr merge*)", "Bash(*/gh pr merge*)", "Bash(env *gh pr merge*)", "Bash(*/env *gh pr merge*)")
REGLES_ATTENDUES = PUSH + FORCE + SANS_CROCHETS + FUSION_ESPACE + FUSION_PR

REGLES_LOCALES = ("Bash(git merge*)", "Bash(*/git merge*)", "Bash(env *git merge*)", "Bash(*/env *git merge*)")

REGLES_DEJA_LA = (
    "Bash(git -C *edition-en* push*)", "Bash(cd *edition-en* && git push*)", "Bash(cd *edition-en*; git push*)",
    "Bash(git --git-dir*edition-en* push*)", "Bash(git -C *PMZilla-Lab/run* push*)", "Bash(git -C *PMZilla-Lab/run* merge*)",
)

PHRASE_PARTAGE = "règle(s) push et fusion absente(s) de .claude/settings.json (conception D11)"
PHRASE_LOCAL = "règle(s) de fusion absente(s) de .claude/settings.local.json de l'espace principal (conception D11)"


def regles_attendues() -> list:
    """Les 32 règles à ajouter à permissions.deny de .claude/settings.json (imprimées par --json)."""
    return list(REGLES_ATTENDUES)


def regles_locales() -> list:
    """Les 4 règles de fusion nue pour .claude/settings.local.json de l'espace principal (imprimées par --json --local)."""
    return list(REGLES_LOCALES)


# --- Formes de commande -------------------------------------------------------------------------------------------------------------

ESPACE = "~/PMZilla-Lab/workspace"
ESPACE_ABS = "/Users/quelquun/PMZilla-Lab/workspace"
WORKTREE = "~/PMZilla-Lab/worktrees/wt-feat-x"

# Un lanceur par forme de D11 ; `{}` reçoit la suite de la commande git (après `git`).
ENVELOPPES = (
    "git {}", "/usr/bin/git {}", "env GIT_TRACE=1 git {}", "/usr/bin/env GIT_TRACE=1 git {}",
    f"cd {WORKTREE} && git {{}}", f"cd {WORKTREE}; git {{}}",
)
SUITES_PUSH = ("", " origin feat/team-names-readable", " origin main", " --dry-run", " --force-with-lease", " --tags", " -u origin feat/x")

# Formes de push : nue, -C, --git-dir, cd &&, cd ;, env, chemin absolu de git, chemin absolu de env, avec et sans -C.
STEMS_PUSH = (
    "git push", f"git -C {ESPACE} push", f"git -C {WORKTREE} push", f"git --git-dir={ESPACE_ABS}/.git push",
    f"git --git-dir {WORKTREE}/.git push", f"cd {ESPACE} && git push", f"cd {WORKTREE}; git push",
    "env GIT_TRACE=1 git push", f"env GIT_TRACE=1 git -C {WORKTREE} push",
    "/usr/bin/git push", f"/usr/bin/git -C {WORKTREE} push",
    "/usr/bin/env GIT_TRACE=1 git push", f"/usr/bin/env GIT_TRACE=1 git -C {WORKTREE} push",
)

COMMANDES_FORCE = ("checkout --force main", "branch --force feat/x main", "clean --force", "reset --hard --force")
COMMANDES_SANS_CROCHETS = ("commit --no-verify -m x", "commit -m x --no-verify", "commit --amend --no-verify --no-edit", "merge --no-verify x")

STEMS_PR = ("gh pr merge", "gh pr merge 12", "gh pr merge 12 --squash --delete-branch", "env GH_TRACE=1 gh pr merge 12",
            "/usr/local/bin/gh pr merge 12", "/usr/bin/env GH_TRACE=1 gh pr merge 12 --auto")

FUSIONS_ESPACE = (
    f"git -C {ESPACE} merge feat/x", f"git -C {ESPACE_ABS} merge --no-ff feat/x", f"git -C {ESPACE}/ merge feat/x",
    f"git -C {ESPACE_ABS}/ merge feat/x", f"cd {ESPACE} && git merge feat/x", f"cd {ESPACE_ABS} && git merge --ff-only feat/x",
    f"cd {ESPACE}; git merge feat/x", f"cd {ESPACE_ABS}; git merge feat/x", f"git --git-dir={ESPACE_ABS}/.git merge feat/x",
    f"git --git-dir={ESPACE}/.git merge feat/x",
)

FUSIONS_NUES = ("git merge main", "git merge --no-ff feat/x", "git merge --abort", "/usr/bin/git merge main", "env GIT_TRACE=1 git merge main",
                "/usr/bin/env GIT_TRACE=1 git merge main")

# Permis : le bloc partagé ne doit refuser aucun de ces cas (D11).
PERMISES_PARTAGE = (
    "git status", "git status --short", "git log origin/main..main", "git log --oneline -3", "git fetch", "git fetch origin",
    "git diff origin/main", "git commit -m x", "git commit -m 'correctif'", "git add tools/x.py", "git branch --show-current",
    "git merge main", "git merge --no-ff feat/x", f"git -C {WORKTREE} merge main", f"cd {WORKTREE} && git merge main",
    f"cd {WORKTREE}; git merge main", f"git -C {ESPACE}/.claude/worktrees/x merge main", f"cd {ESPACE}/.claude/worktrees/x && git merge main",
    f"git -C {ESPACE} status", f"git -C {ESPACE} log origin/main..main", f"git -C {ESPACE} fetch",
    'grep -n "git push" docs/pmzilla/installation.md', 'grep -rn "git push --force" openspec', 'grep -rn "git push" docs',
    'grep -n "--no-verify" docs/pmzilla/installation.md', 'rg "git push" docs', 'git grep -n "git push"', 'git grep -n "gh pr merge"',
    "gh pr list", "gh pr view 12", "gh pr status", "gh pr diff 12", "gh issue list",
    "bash tests/run_all.sh settings_deny", "uv run tools/pilot.py freeze --wait 60",
)

# Effets énoncés par D11, assertés refusés (« Effects stated, not hidden »).
EFFETS_PARTAGE = (
    f"git -C {WORKTREE} commit -m 'prêt à push'", "git commit -m 'sans --no-verify'", "git commit -m 'sans --force'",
    'git grep -n "--force" tools', 'git grep -n "--no-verify" tools',
)
# Effets du bloc local : `git merge-base` et `git mergetool` sont refusés aussi dans l'espace principal.
EFFETS_LOCAL = ("git merge-base main feat/x", "git mergetool")
PERMISES_LOCAL = ("git status", "git log origin/main..main", "git fetch", "git commit -m x", "gh pr list", 'grep -n "git merge" docs')


def refusees_partage():
    """Toutes les commandes que le bloc partagé doit refuser."""
    for stem, suite in itertools.product(STEMS_PUSH, SUITES_PUSH):
        yield f"{stem}{suite}"
    for enveloppe, commande in itertools.product(ENVELOPPES, COMMANDES_FORCE):
        yield enveloppe.format(commande)
    for enveloppe, commande in itertools.product(ENVELOPPES, COMMANDES_SANS_CROCHETS):
        yield enveloppe.format(commande)
    yield from STEMS_PR
    yield from FUSIONS_ESPACE
    yield from EFFETS_PARTAGE


def refusees_locales():
    for commande in FUSIONS_NUES:
        yield commande
    yield from EFFETS_LOCAL


def non_refusees(moteur: Moteur, commandes) -> list:
    return [c for c in commandes if moteur.interdite(c)]


def deny_de(chemin: Path) -> list:
    return json.loads(chemin.read_text(encoding="utf-8")).get("permissions", {}).get("deny", [])


def est_espace_principal() -> bool:
    """Dans l'espace principal `.git` est un dossier, dans un worktree c'est un fichier (le code ne le suppose pas : il le teste)."""
    return (RACINE / ".git").is_dir()


# --- Les blocs déclarés ---------------------------------------------------------------------------------------------------------------

class Declaration(unittest.TestCase):
    def test_comptes(self):
        self.assertEqual((len(PUSH), len(FORCE), len(SANS_CROCHETS), len(FUSION_ESPACE), len(FUSION_PR)), (11, 6, 6, 5, 4))
        self.assertEqual(len(regles_attendues()), 32)
        self.assertEqual(len(regles_locales()), 4)
        self.assertEqual(len(REGLES_DEJA_LA), 6)

    def test_les_deux_listes_passent_la_garde_partagee(self):
        self.assertEqual(garde_regles.constats(regles_attendues()), [])
        self.assertEqual(garde_regles.constats(regles_locales()), [])

    def test_la_garde_partagee_trouve_la_liste_sans_declaration(self):
        texte = Path(__file__).read_text(encoding="utf-8")
        self.assertTrue(garde_regles.imprime_json(texte))
        self.assertEqual(garde_regles._liste_du_module(Path(__file__), garde_regles.CONVENTION), list(REGLES_ATTENDUES))

    def test_aucune_regle_write_ni_notebookedit_ni_cle_vide(self):
        for regle in regles_attendues() + regles_locales() + list(REGLES_DEJA_LA):
            self.assertFalse(regle.startswith(("Write(", "NotebookEdit(")), regle)
            self.assertTrue(regle.startswith("Bash(") and regle.endswith(")") and regle != "Bash()", regle)

    def test_aucune_regle_ne_commence_par_un_joker_nu(self):
        """`*/git …` est permis (le `/` impose un chemin avant la commande) ; `*git …` ou `* …` ne l'est pas."""
        for regle in regles_attendues() + regles_locales():
            motif = regle[len("Bash("):-1]
            self.assertTrue(not motif.startswith("*") or motif.startswith("*/"), regle)

    def test_blocs_disjoints_et_sans_doublon(self):
        tout = regles_attendues() + regles_locales() + list(REGLES_DEJA_LA)
        self.assertEqual(len(tout), len(set(tout)))

    def test_les_quatre_regles_locales_sont_les_formes_nues(self):
        self.assertEqual(regles_locales(), ["Bash(git merge*)", "Bash(*/git merge*)", "Bash(env *git merge*)", "Bash(*/env *git merge*)"])

    def test_les_regles_deja_la_ne_sont_pas_reprises_dans_les_blocs(self):
        self.assertEqual(sorted(set(REGLES_DEJA_LA) & set(regles_attendues() + regles_locales())), [])


class MatriceDesBlocs(unittest.TestCase):
    """La matrice contre les blocs déclarés, toujours (vert avant comme après la pose)."""

    @classmethod
    def setUpClass(cls):
        cls.partage = Moteur(regles_attendues())
        cls.local = Moteur(regles_locales())

    def test_chaque_forme_de_push_est_refusee_sur_chaque_branche_et_option(self):
        manquantes = [f"{s}{o}" for s, o in itertools.product(STEMS_PUSH, SUITES_PUSH) if not self.partage.interdite(f"{s}{o}")]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} forme(s) de push non refusée(s)")

    def test_le_push_est_refuse_par_chaque_famille_de_regle(self):
        """Chaque règle de push est nécessaire : sans elle, au moins une forme de STEMS_PUSH passe."""
        for regle in PUSH:
            reste = Moteur([r for r in regles_attendues() if r != regle])
            passent = [f"{s}{o}" for s, o in itertools.product(STEMS_PUSH, ("", " --dry-run")) if not reste.interdite(f"{s}{o}")]
            self.assertTrue(passent, f"règle redondante : {regle}")

    def test_force_et_saut_des_crochets(self):
        for enveloppe, commande in itertools.product(ENVELOPPES, COMMANDES_FORCE + COMMANDES_SANS_CROCHETS):
            texte = enveloppe.format(commande)
            self.assertTrue(self.partage.interdite(texte), texte)

    def test_chaque_regle_de_force_et_de_crochets_est_necessaire(self):
        for regle in FORCE + SANS_CROCHETS:
            reste = Moteur([r for r in regles_attendues() if r != regle])
            passent = [e.format(c) for e in ENVELOPPES for c in COMMANDES_FORCE + COMMANDES_SANS_CROCHETS
                       if not reste.interdite(e.format(c))]
            self.assertTrue(passent, f"règle redondante : {regle}")

    def test_fusion_de_pull_request(self):
        for commande in STEMS_PR:
            self.assertTrue(self.partage.interdite(commande), commande)

    def test_fusion_qui_nomme_l_espace_principal(self):
        for commande in FUSIONS_ESPACE:
            self.assertTrue(self.partage.interdite(commande), commande)

    def test_la_fusion_nue_est_refusee_par_le_bloc_local(self):
        for commande in FUSIONS_NUES:
            self.assertTrue(self.local.interdite(commande), commande)

    def test_effets_enonces_par_d11_refuses(self):
        for commande in EFFETS_PARTAGE:
            self.assertTrue(self.partage.interdite(commande), commande)
        for commande in EFFETS_LOCAL:
            self.assertTrue(self.local.interdite(commande), commande)

    def test_commandes_permises_non_refusees_par_le_bloc_partage(self):
        self.assertEqual(non_refusees(self.partage, PERMISES_PARTAGE), [])

    def test_commandes_permises_non_refusees_par_le_bloc_local(self):
        self.assertEqual(non_refusees(self.local, PERMISES_LOCAL), [])

    def test_le_bloc_partage_ne_refuse_pas_la_fusion_nue(self):
        for commande in FUSIONS_NUES:
            self.assertFalse(self.partage.interdite(commande), commande)

    def test_le_bloc_local_ne_refuse_ni_le_push_ni_la_fusion_de_pull_request(self):
        for commande in ("git push", "gh pr merge 12"):
            self.assertFalse(self.local.interdite(commande), commande)


# --- Les règles gardées ---------------------------------------------------------------------------------------------------------------

class RegleGardees(unittest.TestCase):
    """Les 6 règles déjà dans le fichier : elles doivent y rester (échoue dès qu'une manque, avant comme après la pose)."""

    @classmethod
    def setUpClass(cls):
        cls.deny = deny_de(REGLAGES)

    def test_les_six_regles_sont_dans_settings_json(self):
        manquantes = [r for r in REGLES_DEJA_LA if r not in self.deny]
        self.assertEqual(manquantes, [], f"{len(manquantes)} règle(s) gardée(s) absente(s) de .claude/settings.json : {manquantes}")

    def test_les_six_regles_ne_sont_pas_dupliquees(self):
        doublons = [r for r in REGLES_DEJA_LA if self.deny.count(r) > 1]
        self.assertEqual(doublons, [])

    def test_ces_regles_refusent_toujours_leurs_cas(self):
        moteur = Moteur([r for r in REGLES_DEJA_LA])
        for commande in ("git -C ~/PMZilla-Lab/edition-en push", "cd ~/PMZilla-Lab/edition-en && git push",
                         "cd ~/PMZilla-Lab/edition-en; git push", "git --git-dir=~/PMZilla-Lab/edition-en/.git push",
                         "git -C ~/PMZilla-Lab/run push", "git -C ~/PMZilla-Lab/run merge main"):
            self.assertTrue(moteur.interdite(commande), commande)

    def test_aucune_des_quatre_regles_de_fusion_nue_n_est_dans_settings_json(self):
        """Le fichier partagé ne porte jamais la fusion nue : elle bloquerait les fusions dans les worktrees (D11). Tourne partout."""
        presentes = [r for r in regles_locales() if r in self.deny]
        self.assertEqual(presentes, [], f"règle(s) de fusion nue interdite(s) dans .claude/settings.json (à poser dans settings.local.json) : {presentes}")

    def test_aucune_regle_des_blocs_n_est_deja_dans_le_fichier_hors_pose(self):
        """Une règle des blocs présente seule (sans les autres) est la pose partielle, nommée par les tests du fichier de réglages."""
        presentes = [r for r in regles_attendues() if r in self.deny]
        self.assertIn(len(presentes), (0, 32), f"pose partielle : {len(presentes)} règle(s) sur 32")


class CommandesPermisesEtReglesExistantes(unittest.TestCase):
    """Les commandes permises contre les règles réelles privées de celles des blocs : même résultat avant et après la pose."""

    def test_aucune_regle_existante_ne_refuse_les_commandes_permises(self):
        deny = deny_de(REGLAGES)
        moteur = Moteur([r for r in deny if r not in regles_attendues() and r not in regles_locales()])
        refusees = non_refusees(moteur, PERMISES_PARTAGE)
        self.assertEqual(refusees, [], "refusées par une règle déjà dans .claude/settings.json (hors blocs de D11)")


# --- Le fichier de réglages réel ---------------------------------------------------------------------------------------------------

class DansLeFichierDeReglages(unittest.TestCase):
    """Tâche 9.1 : l'auteur pose les 32 règles. Sauté avant, échoue si la pose est partielle, rejoue la matrice si tout y est."""

    @classmethod
    def setUpClass(cls):
        cls.deny = deny_de(REGLAGES)
        cls.presentes = [r for r in regles_attendues() if r in cls.deny]
        cls.manquantes = [r for r in regles_attendues() if r not in cls.deny]

    def avant(self):
        if not self.presentes:
            self.fail("règles de D11 pas encore posées (tâche 9.1, l'auteur)")

    def test_les_32_regles_sont_dans_settings_json(self):
        self.avant()
        self.assertEqual(self.manquantes, [], f"{PHRASE_PARTAGE} : {', '.join(self.manquantes)}")

    def test_aucun_doublon_ni_regle_write(self):
        self.avant()
        self.assertEqual(len(self.deny), len(set(self.deny)), "doublon dans permissions.deny")
        self.assertEqual([r for r in self.deny if r.startswith(("Write(", "NotebookEdit("))], [])

    def test_la_matrice_contre_les_regles_reelles(self):
        self.avant()
        if self.manquantes:
            self.skipTest("règles partielles : voir test_les_32_regles_sont_dans_settings_json")
        reel = Moteur(self.deny)
        refusees = [c for c in refusees_partage() if not reel.interdite(c)]
        self.assertEqual(refusees[:5], [], f"{len(refusees)} commande(s) de D11 non refusée(s) par les règles réelles")
        self.assertEqual(non_refusees(reel, PERMISES_PARTAGE), [])


class DansLeFichierLocal(unittest.TestCase):
    """Le fichier local de l'espace principal : lu seulement quand `.git` est un dossier ; échoue une fois le bloc partagé posé et une règle manquante."""

    @classmethod
    def setUpClass(cls):
        cls.partage_pose = bool(set(regles_attendues()) & set(deny_de(REGLAGES)))

    def regles_du_local(self) -> list:
        """Les règles de `.claude/settings.local.json` de l'espace principal (liste vide s'il n'existe pas) ; aucun repli vers settings.json."""
        if REGLAGES_LOCAUX.is_file():
            return deny_de(REGLAGES_LOCAUX)
        return []

    def avant(self):
        if not est_espace_principal():
            self.skipTest("worktree : .git est un fichier, le fichier local de l'espace principal n'est pas lu")
        if ARBRE_EDITION and not REGLAGES_LOCAUX.is_file():
            self.skipTest("réglages locaux de l'auteur absents : arbre de l'édition (D11)")
        if not self.partage_pose:
            self.fail("règles de D11 pas encore posées (tâche 9.1, l'auteur)")

    def test_les_quatre_regles_de_fusion_nue_sont_posees(self):
        self.avant()
        presentes = self.regles_du_local()
        manquantes = [r for r in regles_locales() if r not in presentes]
        self.assertEqual(manquantes, [], f"{PHRASE_LOCAL} : {', '.join(manquantes)}")

    def test_la_fusion_nue_est_refusee_par_les_regles_reelles(self):
        self.avant()
        reel = Moteur(self.regles_du_local())
        refusees = [c for c in refusees_locales() if not reel.interdite(c)]
        self.assertEqual(refusees, [], PHRASE_LOCAL)

    def test_les_regles_locales_passent_la_garde(self):
        self.avant()
        if not REGLAGES_LOCAUX.is_file():
            self.skipTest("pas de fichier local : voir test_les_quatre_regles_de_fusion_nue_sont_posees")
        self.assertEqual(garde_regles.constats(deny_de(REGLAGES_LOCAUX)), [])


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_locales() if "--local" in sys.argv else regles_attendues(), indent=2, ensure_ascii=False))
    else:
        unittest.main()
