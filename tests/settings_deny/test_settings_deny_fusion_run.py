"""Règles du fragment 38 : fusion, `git pull` et dossier d'exécution (dossier de décision 2026-10-26-alleger-les-fins, section 12, failles B1 et M5 ;
sous-issue R-148/u2 ; fichier d'étape de l'auteur fusion-run-reglages ; spec tooling-permission-guards).

Constat : hors du verrou de fin, une session pouvait déplacer `main` local (`git merge` sans -C depuis l'espace de travail, `git pull`) ; des commits posés
là partiraient au prochain push de `main` sans contrôle de contenu. Le point d'entrée du dossier d'exécution (`~/PMZilla-Lab/run/`) n'était protégé que
par des règles Edit et par les sous-commandes git du fragment 16. Une fois le fragment 38 posé, la session ne peut plus (une règle deny compare le texte
de la commande, jamais le dossier ni la branche) :
 - lancer `git merge`, sous aucune forme : nue, `git -* merge` (`-C <dossier>` worktree compris, `-c k=v`, `--no-pager`, `--git-dir`), chemin absolu de git,
   `env`, après `cd`, `&&`, `||`, `&`, `|`, `;` (et `&&git`, `;git`, `&git`, `|git` sans espace) ;
 - lancer `git pull`, sous les mêmes formes ;
 - déplacer `main` local sous TOUTES les formes (même dans un worktree) : `update-ref refs/heads/main`, `update-ref main`, `branch -f main`, `checkout -B main`,
   `switch -C main` ;
 - depuis l'espace de travail principal (commande qui le NOMME : `git -C`, `cd … &&`, `--git-dir`) : `rebase`, `reset`, `update-ref`, `cherry-pick`
   (`git -C <worktree> rebase main` reste permis) ;
 - écrire dans le dossier d'exécution par `cp`, `mv`, `rsync`, `ln`, `rm`, `sed -i`, `tee` ou une redirection `>` (gabarit du fragment 27). L'outil Write
   est déjà refusé par les règles `Edit(**/PMZilla-Lab/run/**)` du fragment 16 (une règle Edit couvre Edit, Write et NotebookEdit ; Claude Code ignore
   `Write(chemin)`, la garde partagée la refuse) : le module vérifie qu'elles sont toujours là. La règle `Edit(**/PMZilla-Lab/run/**)`, relative au projet,
   ne couvre pas `~/PMZilla-Lab/run` à elle seule (le dossier n'est pas sous le projet) : ce sont les formes `Edit(~/PMZilla-Lab/run/**)` et
   `Edit(//**/PMZilla-Lab/run/**)` qui le couvrent.

VOIE PERMISE : intégrer main : git -C <worktree> rebase main (ou `git rebase main` dans la session ouverte dans le worktree). `git merge-base`,
`git merge-tree` et `git mergetool` restent permis sous toutes les formes (y compris avec -C, y compris sur l'espace de travail principal) : aucune règle n'est
de la forme `git merge*` ; chaque règle exige `merge` suivi d'un espace ou de la fin de la commande. Le fichier d'étape ramène pour cela les cinq règles
`… merge*` du fragment 26 à leurs formes exactes `… merge` et `… merge *` (FUSION_ESPACE_ANCIENNES, remplacées à la pose).

EFFETS : voir ci-dessous. Écart assumé avec la convention « pas de joker nu » du fragment 26 : les règles de chaînage (`*& git merge …`, `*| git merge …`,
`*; git merge …`, `*;git merge …`, `*&git merge …`, `*|git merge …`) et celles du dossier d'exécution (`*& cp …`, `*| cp …`, `*;cp …`, `*>…`)
commencent par `*`, comme celles du fragment 27 (test dédié ci-dessous). Limites déclarées (LIMITES_CONNUES) : retour à la ligne, `$(…)`, accents graves, verbe
cité ou échappé, casse, tabulation, alias, enveloppe hors liste, `git reset --hard` nu et `rebase` nu dans l'espace de travail (non vus par les règles ; refusés en
session par reference-transaction dès qu'ils déplaceraient main, u13), `update-ref` avec option avant la ref, formes longues de `branch -f`/`checkout -B`/`switch -C`, `touch`/`mkdir`/`chmod`/`dd`/`install`/
`tar -C`/`unzip -d`/`curl -o`/`ditto`, chemins relatifs, variables, casse et chemins non normalisés vers le dossier d'exécution, `&&cp` ou `||rm` sans espace.

Conception (même motif que test_settings_deny_session_runner.py) : ce module est écrit AVANT la pose par le fichier d'étape de l'auteur :
 - la matrice s'applique au bloc déclaré, toujours : verte avant comme après ;
 - les tests du fichier réel sont SAUTÉS tant que rien n'est posé, ÉCHOUENT si la pose est partielle (ils nomment ce qui manque) et rejouent la matrice
   contre les règles réelles quand tout est posé ;
 - les commandes permises sont aussi vérifiées contre les règles réelles privées de celles du bloc : le résultat est le même avant et après la pose.
Aucune commande n'est lancée ; le test lit .claude/settings.json et .claude/deny/ORDRE.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/test_settings_deny_fusion_run.py --json           (règles deny du fragment 38)
    python3 tests/settings_deny/test_settings_deny_fusion_run.py --lignes 38      (le fragment 38, une règle par ligne)
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import garde_regles  # noqa: E402
from test_settings_deny import motif_en_regex  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"
ORDRE = RACINE / ".claude" / "deny" / "ORDRE"
NOM_38 = "38-fusion-run.txt"
FRAGMENT_38 = RACINE / ".claude" / "deny" / NOM_38


def pose_declaree() -> bool:
    """Vrai dès que le fragment 38 ou son nom dans ORDRE est là (fichiers suivis, commités avec la pose) : les tests du fichier réel ne sont alors plus sautés.
    Partagé avec test_settings_deny_push_merge.py."""
    return FRAGMENT_38.is_file() or NOM_38 in ORDRE.read_text(encoding="utf-8").split()

VOIE_PERMISE = "intégrer main : git -C <worktree> rebase main"

# --- Fusion et pull -------------------------------------------------------------------------------------------------------------------

LANCEURS_GIT = ("git", "*/git", "env *git", "*/env *git")
# Six chaînages (le joker rend `*| git` valable pour `|` et `||`, `*& git` pour `&` et `&&`) : `|`, `||`, `&`, `&&`, `;`, avec un espace avant git ;
# `&&git` (couvert par `*&git`), `;git`, `&git` et `|git` sans espace (revue de contrôle du 2026-10-26, m1 et m3). Le retour à la ligne, `$(…)` et les accents graves restent des limites connues.
CHAINAGES = ("*& git", "*| git", "*; git", "*;git", "*&git", "*|git")


def regles_du_verbe(verbe: str) -> list:
    """Quarante-quatre règles par verbe : quatre formes (verbe nu, verbe et suite, `-*` puis verbe nu, `-*` puis verbe et suite) sous chacun des quatre lanceurs
    (nu, chemin absolu de git, env, chemin absolu de env) et des sept chaînages (couvrent aussi `cd … && git …`). `git -* <verbe>` couvre `-C <dossier>`,
    `-c k=v`, `--no-pager`, `--git-dir=…` et `--work-tree=…` (il remplace les anciennes formes `-C *` et `--git-dir*`). Chaque règle exige le verbe suivi d'un
    espace ou de la fin."""
    regles = []
    for lanceur in LANCEURS_GIT + CHAINAGES:
        regles += [f"Bash({lanceur} {verbe})", f"Bash({lanceur} {verbe} *)", f"Bash({lanceur} -* {verbe})", f"Bash({lanceur} -* {verbe} *)"]
    return regles


DENY_MERGE = tuple(regles_du_verbe("merge"))
DENY_PULL = tuple(regles_du_verbe("pull"))

# --- Déplacement de main sous toutes les formes (revue de contrôle du 2026-10-26, M3) -------------------------------------------------
# `update-ref refs/heads/main`, `update-ref main`, `branch -f main`, `checkout -B main` et `switch -C main` déplacent `main` local : refusés sous toutes les
# formes (nue, -C quel qu'il soit, env, chemin absolu de git, chaînages), pas seulement vers l'espace principal. `git reset --hard` nu dans l'espace de travail
# n'est pas vu par les règles ; refusé en session par reference-transaction dès qu'il déplacerait main (u13).
VERBES_MAIN = ("update-ref refs/heads/main", "update-ref main", "branch -f main", "checkout -B main", "switch -C main")
DENY_MAIN = tuple(regle for verbe in VERBES_MAIN for regle in regles_du_verbe(verbe))

# --- Autres verbes depuis l'espace de travail principal (décision 2 de l'auteur) -----------------------------------------------------
# Une règle compare le texte, jamais le dossier : seules les commandes qui NOMMENT l'espace principal sont refusées (`git -C <worktree> rebase main`
# reste permis ; `git rebase main` nu dans l'espace principal n'est pas vu : limite connue). Mêmes formes que le fragment 26 : -C (avec et sans barre
# finale, sous les quatre lanceurs), `cd … && git`, `cd … ; git`, `--git-dir`.
VERBES_ESPACE = ("rebase", "reset", "update-ref", "cherry-pick")
ESPACES = ("*PMZilla-Lab/workspace", "*PMZilla-Lab/workspace/")


def regles_espace() -> list:
    prefixes = [f"{lanceur} -C {espace}" for lanceur in LANCEURS_GIT for espace in ESPACES]
    prefixes += ["cd *PMZilla-Lab/workspace && git", "cd *PMZilla-Lab/workspace; git", "git --git-dir*PMZilla-Lab/workspace/.git"]
    return [regle for prefixe in prefixes for verbe in VERBES_ESPACE for regle in (f"Bash({prefixe} {verbe})", f"Bash({prefixe} {verbe} *)")]


DENY_ESPACE = tuple(regles_espace())

# --- Dossier d'exécution (gabarit du fragment 27) -------------------------------------------------------------------------------------

CIBLES_RUN = ("*PMZilla-Lab/run/*", "*PMZilla-Lab/run", "*PMZilla-Lab/run *", '*PMZilla-Lab/run"*', "*PMZilla-Lab/run'*")
COMMANDES_FICHIERS = ("cp", "mv", "rsync", "ln", "rm")
COMMANDES_SED = ("sed -i*", "sed * -i*")
# Chaînages (revue de contrôle du 2026-10-26, m2) : `*& ` couvre `&` et `&&`, `*| ` couvre `|` et `||`, `*; ` et `*;` (sans espace) couvrent `;`.
PREFIXES_COMMANDE = ("{c} ", "*/{c} ", "*& {c} ", "*| {c} ", "*; {c} ", "*;{c} ")
PREFIXES_TEE = ("tee ", "*/tee ", "*& tee ", "*| tee ", "*; tee ", "*;tee ", "*|tee ")


def _cibles(prefixe: str) -> tuple:
    return tuple(f"Bash({prefixe}{cible})" for cible in CIBLES_RUN)


DENY_RUN_FICHIERS = tuple(
    regle for commande in COMMANDES_FICHIERS for prefixe in PREFIXES_COMMANDE for regle in _cibles(prefixe.format(c=commande))
)
DENY_RUN_SED = tuple(
    regle for commande in COMMANDES_SED for prefixe in PREFIXES_COMMANDE for regle in _cibles(prefixe.format(c=commande))
)
DENY_RUN_TEE = tuple(regle for prefixe in PREFIXES_TEE for regle in _cibles(prefixe))
DENY_RUN_REDIRECTION = tuple(f"Bash(*>{cible})" for cible in CIBLES_RUN)
DENY_RUN = DENY_RUN_FICHIERS + DENY_RUN_SED + DENY_RUN_TEE + DENY_RUN_REDIRECTION

REGLES_38 = DENY_MERGE + DENY_PULL + DENY_MAIN + DENY_ESPACE + DENY_RUN

# Les cinq règles du fragment 26 (`… merge*`) que le fichier d'étape remplace par leurs formes exactes (`… merge` et `… merge *`) : décision 1 de l'auteur,
# pour que merge-base, merge-tree et mergetool restent permis partout. Source unique : test_settings_deny_push_merge.py les importe.
FUSION_ESPACE_ANCIENNES = (
    "Bash(git -C *PMZilla-Lab/workspace merge*)", "Bash(git -C *PMZilla-Lab/workspace/ merge*)",
    "Bash(cd *PMZilla-Lab/workspace && git merge*)", "Bash(cd *PMZilla-Lab/workspace; git merge*)",
    "Bash(git --git-dir*PMZilla-Lab/workspace/.git merge*)",
)

# Les règles Edit du fragment 16 qui refusent déjà l'outil Write sur le dossier d'exécution : elles doivent rester dans le fichier.
EDIT_RUN = ("Edit(~/PMZilla-Lab/run/**)", "Edit(//**/PMZilla-Lab/run/**)", "Edit(**/PMZilla-Lab/run/**)")


def regles_attendues() -> list:
    """La liste imprimée par --json, contrôlée par la garde partagée (test_settings_deny_listes_declarees)."""
    return list(REGLES_38)


# --- Formes de commande ---------------------------------------------------------------------------------------------------------------

WORKTREE = "~/PMZilla-Lab/worktrees/wt-feat-x"
WORKTREE_ABS = "/Users/quelquun/PMZilla-Lab/worktrees/wt-feat-x"
ESPACE = "~/PMZilla-Lab/workspace"
RUN = "~/PMZilla-Lab/run"
RUN_ABS = "/Users/quelquun/PMZilla-Lab/run"

# `{}` reçoit la suite de la commande git (après `git`) : verbe et arguments.
FORMES_GIT = (
    "git {}", "git -C " + WORKTREE + " {}", "git -C " + WORKTREE_ABS + " {}", "git -C " + ESPACE + " {}", "git -C . {}", "git -C '" + WORKTREE + "' {}",
    "/usr/bin/git {}", "/usr/bin/git -C " + WORKTREE + " {}",
    "env GIT_TRACE=1 git {}", "env GIT_TRACE=1 git -C " + WORKTREE + " {}", "env PMZILLA_NO_EVALS=1 git -C " + WORKTREE_ABS + " {}",
    "/usr/bin/env GIT_TRACE=1 git {}", "/usr/bin/env GIT_TRACE=1 git -C " + WORKTREE + " {}",
    "cd " + WORKTREE + " && git {}", "cd " + WORKTREE + "; git {}", "cd " + ESPACE + " && git {}", "cd " + WORKTREE + " && git -C . {}",
    "git status && git {}", "git fetch; git {}", "git status && git -C " + WORKTREE + " {}", "git fetch; git -C " + WORKTREE + " {}",
    "git --git-dir=" + ESPACE + "/.git {}", "git --git-dir " + WORKTREE + "/.git {}", "git --git-dir=" + WORKTREE_ABS + "/.git --work-tree=" + WORKTREE_ABS + " {}",
)
SUITES_MERGE = ("merge", "merge main", "merge --no-ff feat/x", "merge --ff-only feat/x", "merge --abort", "merge origin/main", "merge --squash feat/x")
SUITES_PULL = ("pull", "pull origin main", "pull --rebase", "pull --ff-only", "pull origin feat/x")

# Formes nommées par la consigne de l'auteur, une par refus (un test chacune).
FUSION_NUE = ("git merge main", "git merge", "git merge --no-ff feat/x", "git merge --abort")
FUSION_C_WORKTREE = (f"git -C {WORKTREE} merge main", f"git -C {WORKTREE_ABS} merge --no-ff feat/x", f"git -C {WORKTREE} merge --abort", "git -C . merge main",
                     f"git -C {WORKTREE_ABS} merge")
FUSION_CHEMIN_ABSOLU = ("/usr/bin/git merge main", f"/usr/bin/git -C {WORKTREE} merge main", "/opt/homebrew/bin/git merge --abort")
FUSION_ENV = ("env GIT_TRACE=1 git merge main", f"env GIT_TRACE=1 git -C {WORKTREE} merge main", "/usr/bin/env GIT_TRACE=1 git merge main",
              f"/usr/bin/env GIT_TRACE=1 git -C {WORKTREE} merge main", "env PMZILLA_NO_EVALS=1 git merge main")
FUSION_CD = (f"cd {WORKTREE} && git merge main", f"cd {WORKTREE}; git merge main", f"cd {ESPACE} && git merge --no-ff feat/x",
             f"cd {WORKTREE} && git -C . merge main", f"cd {ESPACE}/.claude/worktrees/x && git merge main", "git fetch && git merge origin/main",
             "git status; git merge main")
# Chaînages : `|`, `||`, `&`, `&&git` et `;git` sans espace (décision 3 de l'auteur), avec et sans -C, devant git merge et git pull.
FUSION_CHAINAGES = ("git status || git merge main", "git status | git merge main", "git status & git merge main", "git status &&git merge main",
                    "git status;git merge main", f"git status || git -C {WORKTREE} merge main", f"git status | git -C {WORKTREE} merge --no-ff x",
                    f"git status & git -C {WORKTREE} merge", f"git status &&git -C {WORKTREE} merge main", f"git status;git -C {WORKTREE} merge main",
                    "false || git merge --abort", "true &&git merge", "echo x;git merge main")
PULL_CHAINAGES = ("git status || git pull", "git status | git pull", "git status & git pull", "git status &&git pull", "git status;git pull",
                  f"git status || git -C {WORKTREE} pull", f"git status | git -C {WORKTREE} pull --rebase", f"git status & git -C {WORKTREE} pull origin main",
                  f"git status &&git -C {WORKTREE} pull", f"git status;git -C {WORKTREE} pull", "false || git pull origin main", "echo x;git pull")
FUSION_GIT_DIR = (f"git --git-dir={ESPACE}/.git merge main", f"git --git-dir {WORKTREE}/.git merge main",
                  f"git --git-dir={WORKTREE_ABS}/.git --work-tree={WORKTREE_ABS} merge --no-ff feat/x")
PULL_NU = ("git pull", "git pull origin main", "git pull --rebase", "git pull --ff-only origin main")
PULL_C = (f"git -C {WORKTREE} pull", f"git -C {WORKTREE_ABS} pull --rebase", f"git -C {ESPACE} pull origin main", "git -C . pull")
PULL_CHEMIN_ABSOLU = ("/usr/bin/git pull", f"/usr/bin/git -C {WORKTREE} pull origin main")
PULL_ENV = ("env GIT_TRACE=1 git pull", f"env GIT_TRACE=1 git -C {WORKTREE} pull", "/usr/bin/env GIT_TRACE=1 git pull",
            f"/usr/bin/env GIT_TRACE=1 git -C {WORKTREE} pull --rebase")
PULL_CD = (f"cd {WORKTREE} && git pull", f"cd {WORKTREE}; git pull --rebase", f"cd {ESPACE} && git pull origin main", "git fetch && git pull")
PULL_GIT_DIR = (f"git --git-dir={ESPACE}/.git pull", f"git --git-dir {WORKTREE}/.git pull origin main")

# Depuis l'espace de travail principal (décision 2) : rebase, reset, update-ref, cherry-pick, branch -f main, checkout -B main, switch -C main.
ESPACE_ABS = "/Users/quelquun/PMZilla-Lab/workspace"
FORMES_ESPACE = (
    "git -C " + ESPACE + " {}", "git -C " + ESPACE_ABS + " {}", "git -C " + ESPACE + "/ {}", "git -C " + ESPACE_ABS + "/ {}", "/usr/bin/git -C " + ESPACE + " {}",
    "env GIT_TRACE=1 git -C " + ESPACE_ABS + " {}", "/usr/bin/env GIT_TRACE=1 git -C " + ESPACE + "/ {}", "cd " + ESPACE + " && git {}",
    "cd " + ESPACE_ABS + "; git {}", "git --git-dir=" + ESPACE_ABS + "/.git {}", "git --git-dir " + ESPACE + "/.git {}",
)
SUITES_ESPACE = ("rebase main", "rebase --abort", "rebase", "reset", "reset --hard origin/main", "update-ref refs/heads/main abc123", "cherry-pick abc123",
                 "branch -f main", "branch -f main origin/main", "checkout -B main origin/main", "switch -C main origin/main")
ESPACE_REFUSEES = tuple(forme.format(suite) for forme, suite in itertools.product(FORMES_ESPACE, SUITES_ESPACE))

# Formes de fusion et de pull que `git -* <verbe>` et les chaînages sans espace ferment (revue de contrôle du 2026-10-26, m1) : options avant le verbe,
# `--git-dir` hors forme nue, `|git` et `&git` sans espace. Elles étaient des limites connues.
FUSION_OPTIONS = ("git -c user.name=x merge main", "git --no-pager merge main", "git --work-tree=x merge main", f"git -c x=y -C {WORKTREE} merge main",
                  "env GIT_TRACE=1 git --git-dir=x merge main", f"/usr/bin/git --git-dir={WORKTREE}/.git merge main",
                  f"git status && git --git-dir={WORKTREE}/.git merge main", f"cd {WORKTREE} && git --git-dir=.git merge main",
                  "git status |git merge main", "git status|git merge main", "git status &git merge main", "git status&git merge main", "git status&&git merge main")
PULL_OPTIONS = ("git -c x=y pull", "git --no-pager pull", "env GIT_TRACE=1 git --git-dir=x pull", "/usr/bin/git --git-dir=x pull", "git status |git pull",
                "git status|git pull origin main", "git status &git pull", "git status&git pull", f"git -c x=y -C {WORKTREE} pull --rebase")

# Déplacement de main sous TOUTES les formes (M3) : nue, -C quel qu'il soit, env, chemin absolu de git, chaînages, options avant le verbe.
SUITES_MAIN = ("update-ref refs/heads/main abc123", "update-ref refs/heads/main", "update-ref main abc123", "branch -f main", "branch -f main origin/main",
               "checkout -B main origin/main", "checkout -B main", "switch -C main origin/main", "switch -C main")
FORMES_MAIN = FORMES_GIT + FORMES_ESPACE + ("git status |git {}", "git status&git {}", "git status &git {}", "git -c x=y {}", "git --no-pager {}",
                                            "git -c x=y -C " + WORKTREE + " {}", "git status || git -C . {}", "git status | git {}")
MAIN_REFUSEES = tuple(forme.format(suite) for forme, suite in itertools.product(FORMES_MAIN, SUITES_MAIN))

ECRITURES_RUN_CP = (f"cp x.txt {RUN}/x.txt", f"cp -r x {RUN}", f"cp x {RUN_ABS}/sous/dossier/y", f"cp {RUN}/a.txt b.txt", f"cp x '{RUN}'",
                    f'cp x "{RUN_ABS}"', f"cp x {RUN}/", f"cd {WORKTREE} && cp x {RUN}/x", f"cd {WORKTREE}; cp x {RUN_ABS}/x", f"/bin/cp x {RUN}/x")
ECRITURES_RUN_MV = (f"mv x.txt {RUN}/x.txt", f"mv x {RUN}", f"mv x {RUN_ABS}/sous/y", f"mv {RUN}/a.txt b.txt", f"mv x '{RUN}'", f'mv x "{RUN_ABS}"',
                    f"cd {WORKTREE} && mv x {RUN}/x", f"cd {WORKTREE}; mv x {RUN_ABS}/x", f"/bin/mv x {RUN}/x")
ECRITURES_RUN_RSYNC = (f"rsync -a x {RUN}/", f"rsync -a x/ {RUN_ABS}/sous/", f"rsync -a {RUN}/ sauvegarde/", f"rsync x '{RUN}'", f'rsync x "{RUN_ABS}"',
                       f"cd {WORKTREE} && rsync -a x {RUN}/", f"cd {WORKTREE}; rsync -a x {RUN_ABS}/", "/usr/bin/rsync -a x ~/PMZilla-Lab/run")
ECRITURES_RUN_LN = (f"ln -s a {RUN}/x", f"ln a {RUN_ABS}/x", f"ln -sf {RUN}/x y", f"ln -s a '{RUN}/x'", f'ln -s a "{RUN_ABS}"', f"cd {WORKTREE} && ln -s a {RUN}/x",
                    f"cd {WORKTREE}; ln -s a {RUN_ABS}/x", f"/bin/ln -s a {RUN}/x")
ECRITURES_RUN_RM = (f"rm {RUN}/x", f"rm -rf {RUN_ABS}/sous", f"rm -f {RUN}/a {RUN}/b", f"rm -r '{RUN}'", f'rm -r "{RUN_ABS}"', f"cd {WORKTREE} && rm {RUN}/x",
                    f"cd {WORKTREE}; rm -rf {RUN_ABS}", f"/bin/rm {RUN}/x", f"rm -rf {RUN}")
ECRITURES_RUN_SED = (f"sed -i '' s/a/b/ {RUN}/x", f"sed -i s/a/b/ {RUN_ABS}/x", f"sed -i.bak s/a/b/ {RUN}/x", f"sed -n -i s/a/b/ {RUN}/x", f"sed -E -i '' s/a/b/ {RUN_ABS}/x",
                     f"sed -e s/a/b/ -i {RUN}/x", f"sed -i s/a/b/ '{RUN}/x'", f"cd {WORKTREE} && sed -i '' s/a/b/ {RUN}/x", f"cd {WORKTREE}; sed -i s/a/b/ {RUN_ABS}/x",
                     f"/usr/bin/sed -i '' s/a/b/ {RUN}/x", f"/usr/bin/sed -E -i s/a/b/ {RUN}/x")
ECRITURES_RUN_TEE = (f"tee {RUN}/x.txt", f"tee -a {RUN_ABS}/x.txt", f"echo x | tee {RUN}/x.txt", f"echo x |tee {RUN_ABS}/x.txt", f"cd {WORKTREE} && tee {RUN}/x",
                     f"cd {WORKTREE}; tee {RUN}/x", f"/usr/bin/tee {RUN}/x", f"cat a | tee -a '{RUN}'", f'cat a | tee "{RUN_ABS}"')
# Chaînages du dossier d'exécution (m2) : `||`, `|`, `&` et `;` sans espace, devant chaque commande d'écriture.
ECRITURES_RUN_CHAINAGES = (f"x || cp a {RUN}/x", f"x & rm {RUN}/x", f"x;rm {RUN}/x", f"x;cp a {RUN}/x", f"x | mv a {RUN}/x", f"x || rsync -a a {RUN}/",
                           f"x & ln -s a {RUN}/x", f"x;ln -s a {RUN_ABS}/x", f"x;sed -i s/a/b/ {RUN}/x", f"x || sed -i '' s/a/b/ {RUN_ABS}/x", f"x & tee {RUN}/x",
                           f"x;tee {RUN}/x", f"x; rm {RUN}/x", f"x && cp a {RUN}/x", f"x | rm -rf {RUN_ABS}", f"x;mv a {RUN}/x", f"x || tee -a {RUN}/x",
                           f"x ;rm {RUN}/x")
ECRITURES_RUN_REDIRECTION = (f"echo x > {RUN}/x.txt", f"echo x >> {RUN_ABS}/x.txt", f"echo x >{RUN}/x", f"cat a b > {RUN}", f"echo x > '{RUN}'", f'echo x > "{RUN_ABS}"',
                             f"printf x 2> {RUN}/err", f"bash tools/x.sh &> {RUN}/log")

# EFFETS énoncés : commandes qui ne font que nommer le texte (ou lire) et que les règles refusent aussi. Assertés refusés.
EFFETS = (
    "git -C <worktree> commit -m \"... merge ...\" (ou « pull », « pull request ») : refusé, car `git -C * merge *` et `git -C * pull *` se lisent n'importe où "
    "après -C ; idem sous `env`, `/usr/bin/git`, `--git-dir` ; un message de commit passe par git commit -F <fichier du dossier de travail>",
    "Dès qu'une commande COMMENCE par `git -<option>` (y compris `-C`, `-c`, `--no-pager`, `--work-tree`, `--git-dir`) ou par `env … git`, ou contient `/git -<option>` "
    "ou un chaînage `& git -`, `| git -`, `; git -`, le mot « merge » ou « pull » isolé (précédé d'un espace, suivi "
    "d'un espace ou de la fin) est refusé n'importe où après : `git -C <worktree> log --grep merge`, `git -C <worktree> grep -n git merge docs`, "
    "`git -C <worktree> log -- pull` ; collé à un guillemet (`grep -n \"git merge\"`) il passe, par défaut de motif ; voie permise : l'outil Grep, l'outil Read, "
    "et `git commit -F <fichier du dossier de travail>` pour un message",
    "Les chaînages `*& git`, `*| git`, `*; git`, `*&git`, `*|git` et `*;git` (devant merge et pull) refusent aussi un message de commit, un corps d'issue ou une recherche qui "
    "écrit « && git merge … », « | git pull … » ou « ;git pull … » ; un corps d'issue passe par tools/gh_issue.py avec --body-file, une recherche par l'outil Grep",
    "`git merge` est refusé dans un worktree comme dans l'espace de travail : pour intégrer main, utiliser « " + VOIE_PERMISE + " » (aucune règle ne refuse "
    "git rebase dans un worktree) ; `git merge-base`, `git merge-tree` et `git mergetool` restent permis PARTOUT, l'espace de travail principal compris : les règles "
    "du fragment 26 sont des formes exactes (`… merge` et `… merge *`), plus `merge*`",
    "Depuis l'espace de travail principal, `git -C <espace> rebase|reset|update-ref|cherry-pick …` est refusé (aussi `cd <espace> && git …`, `--git-dir`, sous env et "
    "chemin absolu) : un message ou une recherche qui écrit un de ces textes après -C <espace> l'est aussi",
    "`update-ref refs/heads/main`, `update-ref main`, `branch -f main`, `checkout -B main` et `switch -C main` sont refusés sous TOUTES les formes, dans un worktree "
    "comme dans l'espace principal (nue, `-C` quel qu'il soit, `-c k=v`, `--no-pager`, `--git-dir`, env, chemin absolu de git, chaînages) : une commande qui écrit un de ces "
    "textes après git, même dans un message de commit chaîné, l'est aussi ; `git -C <worktree> branch -f x main` et `checkout -B feat/y` restent permis",
    "cp, mv, rsync, ln, rm, sed -i, tee et > : refusés aussi pour LIRE ou COPIER depuis le dossier d'exécution (`cp ~/PMZilla-Lab/run/x .`, `rsync -a ~/PMZilla-Lab/run/ s/`), "
    "et pour toute redirection `>` qui précède le nom du dossier d'exécution (`2>&1` compris) : lire un fichier de ce dossier par l'outil Read",
    "Après un git -C, une seule commande par appel, sans &&, ; ni tube ; pour lire un fichier, Read (décision de l'auteur du 2026-10-27 : une commande qui commence par `git -<option>` "
    "refuse le mot « merge » ou « pull » isolé n'importe où après, et un chaînage `&& git merge …` ou `| git pull …` aussi ; le plus simple est de ne rien chaîner)",
)
EFFETS_COMMANDES = (
    f"git -C {WORKTREE} commit -m \"pas de merge main ici\"", f"git -C {WORKTREE} commit -m \"corrige le pull request\"",
    f"env PMZILLA_NO_EVALS=1 git -C {WORKTREE_ABS} commit -m \"note : merge de la branche\"", "git commit -m \"x && git merge main\"",
    "git commit -m \"x; git pull origin main\"", "git commit -m \"x | git merge main\"", "git commit -m \"x || git pull origin main\"", "git commit -m \"x & git merge main\"",
    "git commit -m \"x;git pull origin main\"", "git commit -m \"x &&git merge main\"", f"git --git-dir={ESPACE}/.git log --grep x merge main",
    # décision 6 : le mot isolé après git -C, git --git-dir, env … git, ou /git
    f"git -C {WORKTREE} log --grep merge", f"git -C {WORKTREE} grep -n git merge docs", f"git -C {WORKTREE} log -- pull", f"git -C {WORKTREE} log --grep pull",
    f"git -C {WORKTREE_ABS} log --oneline --grep merge", f"env GIT_TRACE=1 git -C {WORKTREE} log --grep merge", f"/usr/bin/git -C {WORKTREE} log -- pull",
    f"git --git-dir={WORKTREE_ABS}/.git log --grep merge", f"echo x | /usr/bin/git -C {WORKTREE} log --grep merge",
    "git commit -m \"x; git update-ref main abc\"", f"git -C {WORKTREE} log --grep \"x\" -- update-ref main",
    f"cp {RUN}/a.txt .", f"cat x 2>&1 | tee {RUN}/log", f"echo ok >/dev/null; ls {RUN}; echo x > {RUN}/y", f"rsync -a {RUN}/ sauvegarde/", f"ln -s {RUN}/x y",
    f"sed -i '' s/a/b/ x.txt {RUN}/y", f"rm -f {RUN}/x",
)

# Limites connues, DÉCLARÉES : formes que les règles par motif ne voient pas, parce que le motif est ancré sur le début de la commande, sur un texte exact ou
# sur une liste d'enveloppes. Elles PASSENT aujourd'hui ; ce n'est pas une garantie mais un état connu. Défense qui reste : la lecture des commandes par
# l'auteur et l'instruction de CLAUDE.md. Le crochet pre-merge-commit n'agit que lorsqu'un autre jeton tient le verrou de fin et une avance rapide ne le
# déclenche pas (architecture.md) : il n'est pas une défense contre ces formes. `git reset --hard` nu n'est pas vu par les règles ; refusé en session par reference-transaction dès qu'il déplacerait main (u13). Si une
# règle les refuse un jour, le test échoue et c'est ce tuple qui change.
LIMITES_CONNUES = (
    # espace double entre git et le verbe (les options avant le verbe, `-c k=v`, `--no-pager`, `--git-dir`, sont refusées depuis la revue du 2026-10-26 : `git -* merge`)
    "git  merge main", "git  pull",
    # enveloppes absentes de la liste (env, chemin absolu de env, cd, && et ;)
    "nice git merge main", "time git merge main", "nohup git merge main", "command git merge main", "exec git merge main", "time git pull",
    "git status && env GIT_TRACE=1 git merge main", "cd ~/PMZilla-Lab/worktrees/wt-feat-x && env GIT_TRACE=1 git merge main",
    # affectation de variable devant la commande, sous-shell, interpréteur, pipe
    "FOO=1 git merge main", "FOO=1 git pull", "(git merge main)", "sh -c 'git merge main'", "bash -c \"git merge main\"", "echo main | xargs git merge",
    # alias git défini ailleurs
    "git m main",
    # le mot « merge » ou « pull » collé à un guillemet n'est pas isolé (suivi d'un espace ou de la fin) : une recherche qui le cite entre guillemets passe,
    # et `/git` sans -C ne voit pas un « merge » qui n'est pas le verbe (ces formes sont permises par défaut de motif, pas par choix)
    "git -C ~/PMZilla-Lab/worktrees/wt-feat-x grep -n \"git merge\"", "git -C ~/PMZilla-Lab/worktrees/wt-feat-x grep -n \"git merge\" -- docs",
    "git -C ~/PMZilla-Lab/worktrees/wt-feat-x grep -n \"git pull\" -- docs", "echo x | /usr/bin/git log --grep merge",
    # décision 3 : retour à la ligne, substitution de commande, accents graves, verbe cité ou échappé, casse, tabulation, `|git` sans espace
    "git status\ngit merge main", "git status\ngit pull", "$(git merge main)", "echo $(git merge main)", "`git merge main`", "echo `git pull`",
    "git \"merge\" main", "git 'merge' main", "git \\merge main", "git mer\\ge main", "git \"pull\"", "GIT merge main", "Git pull", "git MERGE main",
    "git\tmerge main", "git\tpull", "git merge\tmain",
    # chaînage sous une enveloppe absente de la liste (`env`, `nice`) : `*& git` attend git juste après le séparateur
    "git status && nice git merge main", "git status |env GIT_TRACE=1 git pull",
    # déplacement de main : formes que les verbes de VERBES_MAIN ne voient pas (option entre le verbe et la branche, forme longue ou groupée, verbe cité)
    "git update-ref -m x refs/heads/main abc123", "git update-ref --no-deref refs/heads/main abc", "git update-ref -d refs/heads/main",
    "git branch --force main origin/main", "git checkout -fB main origin/main", "git switch --force-create main origin/main", "git checkout -B 'main' origin/main",
    "git status && env GIT_TRACE=1 git update-ref main abc",
    # décision 2, déplacement de main depuis l'espace principal : la commande ne nomme pas l'espace, ou le nomme sous une forme que le motif n'attend pas
    # (`git reset --hard` nu dans l'espace de travail : non vu par les règles ; refusé en session par reference-transaction dès qu'il déplacerait main, u13)
    "git rebase main", "git reset --hard origin/main", "git cherry-pick abc123", "git -C . rebase main", "git -C . reset --hard", "cd ~/PMZilla-Lab/workspace/ && git rebase main",
    "cd ~/PMZilla-Lab/workspace/ ; git reset --hard", "cd ~/PMZilla-Lab/workspace && env GIT_TRACE=1 git reset --hard",
    "git branch -fM main",
    # autres déplacements de main (revue de contrôle, m2) : renommage ou copie de branche vers main, fetch dont la destination est main ; non vus par
    # les règles de CE fragment ; refusés en session par reference-transaction dès qu'ils déplaceraient main (u13), sauf `branch -C` (écriture hors transaction).
    # `git branch -M|-C … main` (et `branch -fM main`, plus haut) sont refusés par le fragment 39 (test_settings_deny_garde_main_session.py) ; `fetch` reste ici
    "git branch -M x main", "git branch -C x main", "git fetch . x:main", "git fetch origin +main:main",
    "git -c x=y -C ~/PMZilla-Lab/workspace rebase main", "git -C ~/PMZilla-Lab/workspace  rebase main",
    "git status && git -C ~/PMZilla-Lab/workspace rebase main", "git -C ~/PMZilla-Lab/workspace/.. reset --hard",
    # décision 4 : écriture dans le dossier d'exécution par un autre outil que cp, mv, rsync, ln, rm, sed -i, tee, > (le fragment 16 refuse déjà les
    # sous-commandes git et l'outil Edit)
    "touch ~/PMZilla-Lab/run/x", "mkdir ~/PMZilla-Lab/run/x", "mkdir -p ~/PMZilla-Lab/run/x/y", "chmod +x ~/PMZilla-Lab/run/x", "dd if=a of=~/PMZilla-Lab/run/x",
    "install -m 644 x ~/PMZilla-Lab/run/x", "tar -C ~/PMZilla-Lab/run -xf a.tar", "unzip -d ~/PMZilla-Lab/run a.zip", "curl -o ~/PMZilla-Lab/run/x https://exemple.org",
    "ditto x ~/PMZilla-Lab/run/x", "sed --in-place s/a/b/ ~/PMZilla-Lab/run/x", "sed -ni s/a/b/p ~/PMZilla-Lab/run/x", "perl -pi -e s/a/b/ ~/PMZilla-Lab/run/x",
    "python3 -c 'x' ~/PMZilla-Lab/run/x", "echo x | dd of=~/PMZilla-Lab/run/x", "truncate -s 0 ~/PMZilla-Lab/run/x",
    # le dossier d'exécution atteint par un lien, un chemin relatif, une variable, une casse ou un chemin non normalisé
    "cp x ../run/x", "cp x $RUNDIR/x", "cd ~/PMZilla-Lab/run && cp x y", "cd ~/PMZilla-Lab/run; echo x > y", "cd ~/PMZilla-Lab/run && rm x", "rm run/x",
    "rm ../run/x", "cp x ~/pmzilla-lab/run/x", "cp x ~/PMZILLA-LAB/RUN/x", "cp x ~/PMZilla-Lab/workspace/../run/x", "rm -rf ~/PMZilla-Lab//run/x",
    "rm ~/PMZilla-Lab/./run/x", "ln -s ~/PMZilla-Lab/worktrees/../run/x y", "cp x \"$HOME/PMZilla-Lab\"/run/x", "cp x ~/PMZilla-Lab/'run'/x",
    # chaînage sans espace après `&&` ou `||` (les règles couvrent `*& `, `*| `, `*; ` et `*;`)
    "x &&cp a ~/PMZilla-Lab/run/x", "x ||rm ~/PMZilla-Lab/run/x", "x&&mv a ~/PMZilla-Lab/run/x",
)

COMMANDES_PERMISES = (
    # la voie permise : intégrer main par rebase
    "git rebase main", f"git -C {WORKTREE} rebase main", f"git -C {WORKTREE_ABS} rebase main", f"cd {WORKTREE} && git rebase main",
    f"env PMZILLA_NO_EVALS=1 git -C {WORKTREE} rebase main", "git rebase --abort", "git rebase --continue", f"git -C {WORKTREE} rebase --abort",
    # merge-base et merge-tree restent permis, nus, avec -C, sous env, après cd, avec un chemin absolu
    "git merge-base main HEAD", "git merge-base --is-ancestor main HEAD", "git merge-tree main feat/x", "git merge-tree --write-tree main feat/x",
    f"git -C {WORKTREE} merge-base main HEAD", f"git -C {WORKTREE_ABS} merge-tree main feat/x", f"git -C {WORKTREE} merge-base --is-ancestor main HEAD",
    "env GIT_TRACE=1 git merge-base main HEAD", f"env GIT_TRACE=1 git -C {WORKTREE} merge-tree main feat/x", f"cd {WORKTREE} && git merge-base main HEAD",
    f"cd {WORKTREE}; git merge-tree main feat/x", "git fetch && git merge-base main HEAD", "git status; git merge-tree main feat/x",
    "/usr/bin/git merge-base main HEAD", f"/usr/bin/git -C {WORKTREE} merge-tree main feat/x", f"git --git-dir={WORKTREE_ABS}/.git merge-base main HEAD",
    f"git --git-dir {WORKTREE}/.git merge-tree main feat/x", "git merge-file a b c", "git mergetool", f"git -C {WORKTREE} mergetool",
    # espace de travail principal : lecture, fetch, merge-base, merge-tree et mergetool restent permis (le fragment 26 n'est plus `merge*`) ; rebase, reset,
    # cherry-pick, update-ref, branch -f main, checkout -B main et switch -C main restent permis dans un worktree
    f"git -C {ESPACE} merge-base main HEAD", f"git -C {ESPACE_ABS} merge-tree main feat/x", f"git -C {ESPACE}/ merge-base a b", f"cd {ESPACE} && git merge-base a b",
    f"cd {ESPACE_ABS}; git merge-tree a b", f"git --git-dir={ESPACE_ABS}/.git merge-base a b", f"git -C {ESPACE} mergetool", f"git -C {ESPACE} merge-file a b c",
    f"git -C {ESPACE} status", f"git -C {ESPACE} log --oneline -3", f"git -C {ESPACE} fetch", f"git -C {ESPACE} checkout feat/x", f"git -C {ESPACE} branch --show-current",
    f"cd {ESPACE} && git status", f"git -C {ESPACE}/.claude/worktrees/x rebase main", f"git -C {ESPACE_ABS}/.claude/worktrees/x reset --hard HEAD~1",
    f"git -C {WORKTREE} reset --hard HEAD~1", f"git -C {WORKTREE} reset --soft HEAD~1", f"git -C {WORKTREE} cherry-pick abc123", f"git -C {WORKTREE_ABS} update-ref refs/heads/x abc",
    f"git -C {WORKTREE} branch -f x main", f"git -C {WORKTREE} checkout -B feat/y", f"git -C {WORKTREE} switch -C feat/y", f"git -C {WORKTREE} branch -f main-x abc",
    f"cd {WORKTREE} && git reset --hard", f"env GIT_TRACE=1 git -C {WORKTREE_ABS} rebase --onto main a b", "git reset --hard HEAD~1", "git cherry-pick abc123",
    "git switch -C feat/y", "git checkout -B feat/y", f"git -C {ESPACE}-copie rebase main", f"git -C {ESPACE}x reset",
    # lecture et autres commandes git
    "git status", f"git -C {WORKTREE} status", "git log --oneline -5", "git log --merges --oneline -5", "git log --no-merges --oneline -5", f"git -C {WORKTREE} log --merges",
    "git branch --merged main", f"git -C {WORKTREE} branch --no-merged main", "git fetch", "git fetch origin", f"git -C {WORKTREE} fetch", "git diff main...HEAD",
    "git show --first-parent HEAD", "git cherry -v main", "git commit -m \"integre main par rebase\"", "git commit -F docs/message.txt",
    f"env PMZILLA_NO_EVALS=1 git -C {WORKTREE} commit -F /tmp/x/message.txt", f"git -C {WORKTREE} commit -F docs/message.txt",
    f"git -C {WORKTREE} commit -m \"fusion de la branche\"", "git commit -m \"voir la demande de fusion\"", "git add tests/x.py", f"git -C {WORKTREE} add tests/x.py",
    "git grep -n \"git merge\" -- docs", "git grep -n \"git pull\" -- docs", "git grep -n merge", "grep -n \"git merge\" docs/pmzilla/installation.md",
    "gh pr list", "gh pr view 12", "bash tests/run_all.sh settings_deny", "uv run tools/pilot.py freeze --check", "bash tools/worktree.sh feat/x",
    "bash tools/run_worktree.sh status", "git pull-request-notes", "git pullrequest", "git mergex main",
    # dossier d'exécution : lecture, listes, copies et redirections qui ne le touchent pas
    f"ls {RUN}", f"cat {RUN}/x.txt", f"head -5 {RUN_ABS}/x.txt", f"git -C {RUN} status", f"git -C {RUN} log --oneline -3", f"diff {RUN}/x.txt x.txt",
    f"rm x.txt", f"rm -rf {WORKTREE}/tmp", "rsync -a a/ ~/PMZilla-Lab/worktrees/y/", "ln -s a b", f"sed -n 5p {RUN}/x.txt", f"sed -e s/a/b/ {RUN_ABS}/x.txt", "sed -i '' s/a/b/ x.txt",
    f"sed -i s/a/b/ {WORKTREE}/x.txt", "rm ~/PMZilla-Lab/run-notes/x", "rm ~/PMZilla-Lab/runner/x", "ln -s a ~/PMZilla-Lab/run-notes/x", "rsync -a x ~/PMZilla-Lab/runner/",
    f"cp x.txt {WORKTREE}/x.txt", f"cp -r x ~/PMZilla-Lab/runner/y", "cp x ~/PMZilla-Lab/run-notes/y", "cp x ~/PMZilla-Lab/workspace/run/y", "mv x ~/PMZilla-Lab/worktrees/y",
    f"tee {WORKTREE}/x.txt", "echo x > /private/tmp/claude-501/x/scratchpad/y.txt", f"echo x > {WORKTREE}/x.txt", "echo x > ~/PMZilla-Lab/runner/y", "echo x > ~/PMZilla-Lab/run-notes/y",
    "python3 tests/settings_deny/test_settings_deny_fusion_run.py --json",
)


def commandes_refusees():
    """Toutes les formes de fusion, de pull et d'écriture dans le dossier d'exécution que la session ne doit pas exécuter."""
    for forme, suite in itertools.product(FORMES_GIT, SUITES_MERGE + SUITES_PULL):
        yield forme.format(suite)
    for famille in (FUSION_NUE, FUSION_C_WORKTREE, FUSION_CHEMIN_ABSOLU, FUSION_ENV, FUSION_CD, FUSION_CHAINAGES, FUSION_GIT_DIR, PULL_NU, PULL_C, PULL_CHEMIN_ABSOLU,
                    PULL_ENV, PULL_CD, PULL_CHAINAGES, PULL_GIT_DIR, ESPACE_REFUSEES, ECRITURES_RUN_CP, ECRITURES_RUN_MV, ECRITURES_RUN_RSYNC, ECRITURES_RUN_LN,
                    ECRITURES_RUN_RM, ECRITURES_RUN_SED, ECRITURES_RUN_TEE, ECRITURES_RUN_REDIRECTION, ECRITURES_RUN_CHAINAGES, FUSION_OPTIONS, PULL_OPTIONS,
                    MAIN_REFUSEES, EFFETS_COMMANDES):
        yield from famille


class Moteur:
    def __init__(self, regles):
        self.motifs = [motif_en_regex(r[len("Bash("):-1]) for r in regles if r.startswith("Bash(")]

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)


class Matrice:
    """Cas communs au bloc REGLES_38 et aux règles réelles ; `self.moteur` est fourni par la classe qui les mélange."""

    def verifier_formes_refusees(self):
        manquantes = [c for c in commandes_refusees() if not self.moteur.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} forme(s) non refusée(s)")

    def verifier_formes_permises(self):
        refusees = [c for c in COMMANDES_PERMISES if self.moteur.interdite(c)]
        self.assertEqual(refusees, [], "commande(s) permise(s) refusée(s) : règle trop large")


class BlocFusionRun(Matrice, unittest.TestCase):
    """Le moteur de motifs appliqué au bloc à poser : vert avant comme après la pose."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_38)

    def refuses(self, commandes):
        for commande in commandes:
            self.assertTrue(self.moteur.interdite(commande), commande)

    def permises(self, commandes):
        for commande in commandes:
            self.assertFalse(self.moteur.interdite(commande), commande)

    # --- déclaration -----------------------------------------------------------------------------------------------------------------

    def test_le_bloc_est_fait_de_regles_bash_sans_doublon(self):
        self.assertEqual(len(REGLES_38), len(set(REGLES_38)))
        self.assertTrue(all(r.startswith("Bash(") and r.endswith(")") for r in REGLES_38))
        self.assertEqual(garde_regles.constats(REGLES_38), [])

    def test_les_comptes(self):
        self.assertEqual((len(DENY_MERGE), len(DENY_PULL), len(DENY_ESPACE), len(DENY_RUN_FICHIERS), len(DENY_RUN_SED), len(DENY_RUN_TEE), len(DENY_RUN_REDIRECTION)),
                         (40, 40, 88, 150, 60, 35, 5))
        self.assertEqual(len(DENY_MAIN), 200)
        self.assertEqual(len(REGLES_38), 618)

    def test_la_garde_partagee_trouve_la_liste(self):
        texte = Path(__file__).read_text(encoding="utf-8")
        self.assertTrue(garde_regles.imprime_json(texte))
        self.assertEqual(garde_regles._liste_du_module(Path(__file__), garde_regles.CONVENTION), list(REGLES_38))

    def test_aucune_regle_write_ni_notebookedit(self):
        """Claude Code ignore `Write(chemin)` : l'outil Write sur le dossier d'exécution est couvert par les règles Edit du fragment 16."""
        self.assertEqual([r for r in REGLES_38 if r.startswith(("Write(", "NotebookEdit(", "Edit("))], [])

    def test_aucune_regle_n_attrape_merge_base_ni_merge_tree(self):
        """Jamais `git merge*` : chaque règle de fusion ou de pull exige le verbe suivi d'un espace ou de la fin de la commande."""
        for regle in DENY_MERGE + DENY_PULL + DENY_MAIN:
            self.assertFalse(regle.endswith(("merge*)", "pull*)")), regle)
            self.assertNotIn("merge-", regle)
            self.assertNotIn("merge*", regle)
            self.assertNotIn("pull*", regle)
        self.assertNotIn("Bash(git merge*)", REGLES_38)

    def test_les_regles_a_joker_nu_sont_celles_de_chainage_et_du_dossier_d_execution(self):
        """Écart assumé avec la convention du fragment 26 (comme le fragment 27) : seules ces règles commencent par `*` sans `/`."""
        jokers = sorted(r for r in REGLES_38 if r.startswith("Bash(*") and not r.startswith(("Bash(*/", "Bash(*PMZilla-Lab")))
        attendus = [r for r in DENY_MERGE + DENY_PULL + DENY_MAIN if r.startswith(("Bash(*&", "Bash(*;", "Bash(*|"))]
        attendus += [r for r in DENY_RUN if r.startswith(("Bash(*&", "Bash(*;", "Bash(*|", "Bash(*>"))]
        self.assertEqual(jokers, sorted(attendus))

    def test_les_regles_du_dossier_d_execution_nomment_le_dossier(self):
        for regle in DENY_RUN:
            self.assertIn("PMZilla-Lab/run", regle)

    # --- un test par refus -----------------------------------------------------------------------------------------------------------

    def test_git_merge_nu_est_refuse(self):
        self.refuses(FUSION_NUE)

    def test_git_merge_avec_c_est_refuse_y_compris_dans_un_worktree(self):
        self.refuses(FUSION_C_WORKTREE)

    def test_git_merge_par_chemin_absolu_est_refuse(self):
        self.refuses(FUSION_CHEMIN_ABSOLU)

    def test_git_merge_sous_env_est_refuse(self):
        self.refuses(FUSION_ENV)

    def test_git_merge_apres_cd_ou_chainage_est_refuse(self):
        self.refuses(FUSION_CD)

    def test_git_merge_avec_git_dir_est_refuse(self):
        self.refuses(FUSION_GIT_DIR)

    def test_git_merge_apres_un_chainage_sans_espace_ou_par_pipe_est_refuse(self):
        self.refuses(FUSION_CHAINAGES)

    def test_git_pull_apres_un_chainage_sans_espace_ou_par_pipe_est_refuse(self):
        self.refuses(PULL_CHAINAGES)

    def test_git_merge_avec_options_ou_chainage_sans_espace_est_refuse(self):
        """Revue de contrôle du 2026-10-26, m1 : `git -* merge` couvre `-c k=v`, `--no-pager`, `--git-dir` ; `*|git` et `*&git` ferment `|git` et `&git`."""
        self.refuses(FUSION_OPTIONS)

    def test_git_pull_avec_options_ou_chainage_sans_espace_est_refuse(self):
        self.refuses(PULL_OPTIONS)

    def test_depuis_l_espace_principal_rebase_reset_update_ref_cherry_pick_et_main_sont_refuses(self):
        self.refuses(ESPACE_REFUSEES)

    def test_chaque_verbe_de_l_espace_principal_est_refuse_sous_chaque_forme(self):
        for forme, verbe in itertools.product(FORMES_ESPACE, VERBES_ESPACE):
            self.refuses((forme.format(verbe), forme.format(verbe + " x")))

    def test_main_ne_se_deplace_sous_aucune_forme(self):
        """M3 : update-ref refs/heads/main, update-ref main, branch -f main, checkout -B main, switch -C main sont refusés nus, avec -C quel qu'il soit, sous
        env, par chemin absolu, chaînés, dans un worktree comme dans l'espace principal."""
        self.refuses(MAIN_REFUSEES)
        for verbe in VERBES_MAIN:
            for forme in FORMES_MAIN:
                self.refuses((forme.format(verbe), forme.format(verbe + " x")))

    def test_les_autres_branches_et_refs_restent_permises(self):
        self.permises((f"git -C {WORKTREE} branch -f x main", f"git -C {WORKTREE} branch -f main-x abc", f"git -C {WORKTREE} checkout -B feat/y",
                       f"git -C {WORKTREE} switch -C feat/y", f"git -C {WORKTREE_ABS} update-ref refs/heads/x abc", "git update-ref refs/heads/feat/main abc",
                       "git checkout -B feat/main", "git switch -C main-copie", "git branch -f mainx"))

    def test_les_ecritures_dans_le_dossier_d_execution_apres_un_chainage_sont_refusees(self):
        self.refuses(ECRITURES_RUN_CHAINAGES)

    def test_rebase_dans_un_worktree_reste_permis(self):
        self.permises((f"git -C {WORKTREE} rebase main", f"git -C {WORKTREE_ABS} rebase main", f"git -C {ESPACE}/.claude/worktrees/x rebase main",
                       f"git -C {WORKTREE} reset --hard HEAD~1", f"git -C {WORKTREE} branch -f x main", "git rebase main"))

    def test_les_regles_de_l_espace_nomment_l_espace_principal(self):
        for regle in DENY_ESPACE:
            self.assertIn("PMZilla-Lab/workspace", regle)

    def test_cp_mv_rsync_ln_rm_sed_sont_refuses_aussi_pour_lire(self):
        self.refuses((f"rsync -a {RUN}/ x/", f"ln -s {RUN}/x y", f"rm {RUN}/x", f"sed -i '' s/a/b/ y {RUN}/z"))

    def test_rsync_dans_le_dossier_d_execution_est_refuse(self):
        self.refuses(ECRITURES_RUN_RSYNC)

    def test_ln_dans_le_dossier_d_execution_est_refuse(self):
        self.refuses(ECRITURES_RUN_LN)

    def test_rm_dans_le_dossier_d_execution_est_refuse(self):
        self.refuses(ECRITURES_RUN_RM)

    def test_sed_i_dans_le_dossier_d_execution_est_refuse(self):
        self.refuses(ECRITURES_RUN_SED)

    def test_git_pull_nu_est_refuse(self):
        self.refuses(PULL_NU)

    def test_git_pull_avec_c_est_refuse(self):
        self.refuses(PULL_C)

    def test_git_pull_par_chemin_absolu_est_refuse(self):
        self.refuses(PULL_CHEMIN_ABSOLU)

    def test_git_pull_sous_env_est_refuse(self):
        self.refuses(PULL_ENV)

    def test_git_pull_apres_cd_ou_chainage_est_refuse(self):
        self.refuses(PULL_CD)

    def test_git_pull_avec_git_dir_est_refuse(self):
        self.refuses(PULL_GIT_DIR)

    def test_cp_dans_le_dossier_d_execution_est_refuse(self):
        self.refuses(ECRITURES_RUN_CP)

    def test_mv_dans_le_dossier_d_execution_est_refuse(self):
        self.refuses(ECRITURES_RUN_MV)

    def test_tee_dans_le_dossier_d_execution_est_refuse(self):
        self.refuses(ECRITURES_RUN_TEE)

    def test_redirection_dans_le_dossier_d_execution_est_refusee(self):
        self.refuses(ECRITURES_RUN_REDIRECTION)

    def test_chaque_forme_de_fusion_et_de_pull_sur_chaque_verbe_et_option(self):
        manquantes = [forme.format(suite) for forme, suite in itertools.product(FORMES_GIT, SUITES_MERGE + SUITES_PULL)
                      if not self.moteur.interdite(forme.format(suite))]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} forme(s) non refusée(s)")

    def test_chaque_famille_de_regles_de_fusion_est_necessaire(self):
        """Sans la famille (jeu de règles d'un même lanceur), au moins une forme de fusion passe : aucune famille n'est morte."""
        familles = {"nu": ("Bash(git merge", "Bash(git -"), "chemin": ("Bash(*/git ",), "env": ("Bash(env ",),
                    "chemin-env": ("Bash(*/env ",), "chainage": ("Bash(*&", "Bash(*|", "Bash(*;")}
        formes = tuple(FUSION_NUE + FUSION_C_WORKTREE + FUSION_CHEMIN_ABSOLU + FUSION_ENV + FUSION_CD + FUSION_GIT_DIR)
        for nom, prefixes in familles.items():
            reste = Moteur([r for r in REGLES_38 if not (r.startswith(prefixes) and " merge" in r)])
            passent = [c for c in formes if not reste.interdite(c)]
            self.assertTrue(passent, f"famille redondante : {nom}")

    # --- permis et effets ------------------------------------------------------------------------------------------------------------

    def test_lecture_rebase_merge_base_merge_tree_et_commits_restent_permis(self):
        self.verifier_formes_permises()

    def test_la_voie_permise_est_ecrite_et_permise(self):
        self.assertEqual(VOIE_PERMISE, "intégrer main : git -C <worktree> rebase main")
        self.permises((f"git -C {WORKTREE} rebase main", f"git -C {WORKTREE_ABS} rebase main", "git rebase main"))
        self.assertTrue(any(VOIE_PERMISE in effet for effet in EFFETS))

    def test_merge_base_et_merge_tree_restent_permis_sous_toutes_les_formes(self):
        for forme, verbe in itertools.product(FORMES_GIT, ("merge-base main HEAD", "merge-base --is-ancestor a b", "merge-tree main feat/x",
                                                           "merge-tree --write-tree a b", "merge-file a b c", "mergetool")):
            self.assertFalse(self.moteur.interdite(forme.format(verbe)), forme.format(verbe))

    def test_merge_base_avec_c_est_permis(self):
        self.permises((f"git -C {WORKTREE} merge-base main HEAD", f"git -C {WORKTREE_ABS} merge-tree main feat/x", "git -C . merge-base a b"))

    def test_merge_tree_avec_c_est_permis(self):
        self.permises((f"git -C {WORKTREE} merge-tree main feat/x", f"env GIT_TRACE=1 git -C {WORKTREE} merge-tree a b", f"cd {WORKTREE} && git merge-tree a b"))

    def test_les_effets_sont_refuses_et_ecrits(self):
        self.assertGreaterEqual(len(EFFETS), 5)
        self.refuses(EFFETS_COMMANDES)

    def test_les_limites_connues_passent_et_sont_declarees(self):
        """Chaque limite déclarée passe les règles du bloc : le tuple décrit l'état réel, ni plus ni moins."""
        self.assertEqual(len(LIMITES_CONNUES), len(set(LIMITES_CONNUES)))
        refusees = [c for c in LIMITES_CONNUES if self.moteur.interdite(c)]
        self.assertEqual(refusees, [], "limite(s) déclarée(s) maintenant refusée(s) : la retirer de LIMITES_CONNUES")


class ReglesExistantes(unittest.TestCase):
    """Les commandes permises contre les règles réelles privées de celles du bloc : même résultat avant et après la pose."""

    @classmethod
    def setUpClass(cls):
        deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        # privées aussi des cinq règles `… merge*` du fragment 26, que la même pose remplace par leurs formes exactes : résultat identique avant et après
        cls.moteur = Moteur([r for r in deny if r not in REGLES_38 and r not in FUSION_ESPACE_ANCIENNES])

    def test_commandes_permises_non_refusees_par_les_regles_d_avant(self):
        self.assertEqual([c for c in COMMANDES_PERMISES if self.moteur.interdite(c)], [])

    def test_la_fusion_le_pull_et_l_ecriture_dans_run_ne_sont_pas_deja_refuses(self):
        """Garde le sens du bloc : sans lui, ces trois familles de commandes ne sont pas refusées par une règle d'avant."""
        for commande in (f"git -C {WORKTREE} merge main", "git pull", f"git -C {WORKTREE} pull", f"cp x {RUN}/x", f"echo x > {RUN}/x", f"tee {RUN}/x",
                         f"git -C {ESPACE} rebase main", f"git -C {ESPACE} reset --hard", f"rm {RUN}/x", f"rsync -a x {RUN}/", f"ln -s a {RUN}/x", f"sed -i s/a/b/ {RUN}/x"):
            self.assertFalse(self.moteur.interdite(commande), commande)


class DansLeFichierDeReglages(unittest.TestCase):
    """La pose par l'auteur : sautée avant, échoue si elle est partielle, passe si tout y est."""

    @classmethod
    def setUpClass(cls):
        permissions = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]
        cls.deny = permissions["deny"]
        cls.allow = permissions.get("allow", [])
        cls.manquantes = [r for r in REGLES_38 if r not in cls.deny]

    # Désherbage du 2026-10-28 (D79) : les branches de saut « fragment 38 pas encore posé » sont retirées. Le fragment 38 est dans ORDRE et dans settings.json,
    # la pose est déclarée : ces branches ne se déclenchaient plus, et elles auraient masqué une pose partielle.

    def test_la_pose_declaree_est_complete(self):
        """Le fragment 38 absent d'un côté seulement (fichier sans ORDRE, ou ORDRE sans fichier) est une pose partielle."""
        self.assertTrue(FRAGMENT_38.is_file(), f"{NOM_38} absent de .claude/deny/ alors qu'ORDRE le nomme")
        self.assertIn(NOM_38, ORDRE.read_text(encoding="utf-8").split(), f"{NOM_38} présent sans être dans .claude/deny/ORDRE")

    def test_les_regles_deny_sont_dans_settings_json(self):
        self.assertEqual(self.manquantes, [], f"pose partielle : {len(self.manquantes)} règle(s) de REGLES_38 absente(s) de .claude/settings.json")

    def test_les_anciennes_regles_merge_etoile_du_fragment_26_sont_retirees(self):
        self.assertEqual([r for r in FUSION_ESPACE_ANCIENNES if r in self.deny], [], "forme `merge*` encore là : merge-base serait refusé dans l'espace principal")

    def test_le_fragment_38_est_dans_ordre_apres_la_pose(self):
        self.assertIn(NOM_38, ORDRE.read_text(encoding="utf-8").split(), "fragment 38 absent de .claude/deny/ORDRE")
        fragment = RACINE / ".claude" / "deny" / NOM_38
        self.assertTrue(fragment.is_file(), f"{NOM_38} absent")
        lignes = [ligne for ligne in fragment.read_text(encoding="utf-8").splitlines() if ligne.strip()]
        self.assertEqual(lignes, list(REGLES_38))

    def test_les_regles_edit_du_fragment_16_refusent_toujours_l_outil_write_sur_run(self):
        """Une règle Edit couvre Edit, Write et NotebookEdit : le dossier d'exécution reste protégé contre l'outil Write (avant comme après la pose)."""
        self.assertEqual([r for r in EDIT_RUN if r not in self.deny], [])
        self.assertEqual([r for r in self.deny if "PMZilla-Lab/run" in r and r.startswith(("Write(", "NotebookEdit("))], [])

    def test_aucune_regle_allow_ne_permet_merge_pull_ni_l_ecriture_dans_run(self):
        autres = [r for r in self.allow if "git merge" in r or "git pull" in r or "PMZilla-Lab/run" in r or r in ("Bash(git *)", "Bash(*)")]
        self.assertEqual(autres, [])

    def test_la_matrice_des_formes_contre_les_regles_reelles(self):
        if self.manquantes:
            self.fail("règles manquantes : " + " ; ".join(self.manquantes[:10]))
        matrice = type("MatriceReelle", (Matrice, unittest.TestCase), {"moteur": Moteur(self.deny)})("verifier_formes_refusees")
        matrice.verifier_formes_refusees()
        matrice.verifier_formes_permises()


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    elif "--lignes" in sys.argv:
        print("\n".join(regles_attendues()))
    else:
        unittest.main()
