"""Règles `deny` du change team-names-readable (design D5, D9, décision b ; spec tooling-permission-guards).

Décision de l'organisation du 2026-10-19 : les noms d'équipe peuvent être lus par la session, par deux vues et par un extrait
(`Flux-Lab/equipes-lisibles.yaml`, écrit par `export_jira_api.py extract-teams`). Rien n'est ouvert en brut : AUCUNE règle `deny` n'est
retirée (option B, décision b), le catalogue des équipes reste fermé avec ses 37 règles. Ce module fait trois choses :

 1. `REGLES_EXTRACT` (16) : les règles de lancement de `extract-teams` que l'auteur ajoute à .claude/settings.json (tâche 9.1), imprimées
    par `python3 tests/settings_deny/test_settings_deny_team_names.py --json` et contrôlées par la garde partagée
    (test_settings_deny_listes_declarees.py) : aucune règle Write(chemin) ni NotebookEdit(chemin), aucune clé vide, aucun doublon ;
 2. `REGLES_A_GARDER` : les règles que le change laisse en place (D5), en tuples LITTÉRAUX par famille (`FAMILLES_D5`, avec le décompte
    de la table de D5), qui ÉCHOUENT dès qu'une manque du vrai fichier, la règle nommée ;
 3. le fichier d'extrait reste lisible (aucune règle Read ni lecteur ne le vise) et une commande qui ne fait que citer la sous-commande
    reste permise.

Conception comme test_settings_deny_rgpd.py : les cas sur le bloc REGLES_EXTRACT sont toujours verts ; les cas contre les vrais réglages
sont SAUTÉS tant que l'auteur n'a posé aucune des 16 règles, ÉCHOUENT si la pose est partielle (règles manquantes nommées) et rejouent
la matrice contre les règles réelles quand tout y est. Les règles gardées et la lisibilité de l'extrait sont vérifiées dans tous les cas.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json. Données d'essai : noms de fichiers fictifs, aucune équipe réelle.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/test_settings_deny_team_names.py --json     (imprime le bloc à copier dans permissions.deny)
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import garde_regles  # noqa: E402
from test_settings_deny_rgpd import Moteur, PREFIXES_TOOLS, regles_de_lancement  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"

SCRIPT = "export_jira_api.py"
SOUS_COMMANDE = "extract-teams"
EXTRAIT = "equipes-lisibles.yaml"

REGLES_EXTRACT = regles_de_lancement(f"{SCRIPT} {SOUS_COMMANDE}", PREFIXES_TOOLS)

# Les 9 lecteurs de base et les 25 autres (même liste que test_settings_deny_r84_flux_lab.py).
LECTEURS_BASE = ("cat", "head", "tail", "less", "more", "grep", "awk", "sed", "cp")
LECTEURS_ETENDUS = ("rg", "bat", "nl", "tac", "rev", "strings", "xxd", "od", "hexdump", "cut", "sort", "uniq", "diff", "cmp", "base64",
                    "view", "vi", "vim", "nano", "rsync", "ditto", "tar", "zip", "ln", "mv")
LECTEURS = LECTEURS_BASE + LECTEURS_ETENDUS
LISTAGES = ("ls", "/bin/ls", "eza", "find", "tree")


def _read3(nom: str) -> list:
    return [f"Read(./Flux-Lab/{nom})", f"Read(//**/Flux-Lab/{nom})", f"Read(~/**/Flux-Lab/{nom})"]


def _lecteurs(lecteurs, motif: str) -> list:
    return [f"Bash({lecteur} *{motif}*)" for lecteur in lecteurs]


# Les règles que le change laisse en place (design D5), famille par famille, en TUPLES LITTÉRAUX copiés du vrai .claude/settings.json
# (revue 8, point A : une génération par famille passait alors que des règles manquaient). Aucune génération ici : une règle ajoutée,
# retirée ou fautive dans ce bloc se voit à la relecture, et le décompte de chaque famille est comparé à la table de D5.
FAMILLE_EXPORTS = (
    "Read(./Flux-Lab/exports/**)",
    "Bash(cat *Flux-Lab/exports*)", "Bash(head *Flux-Lab/exports*)", "Bash(tail *Flux-Lab/exports*)", "Bash(less *Flux-Lab/exports*)",
    "Bash(more *Flux-Lab/exports*)", "Bash(grep *Flux-Lab/exports*)", "Bash(awk *Flux-Lab/exports*)", "Bash(sed *Flux-Lab/exports*)",
    "Bash(cp *Flux-Lab/exports*)",
)
FAMILLE_HISTORIQUE = (
    "Read(./Flux-Lab/historique/**)",
    "Bash(cat *Flux-Lab/historique*)", "Bash(head *Flux-Lab/historique*)", "Bash(tail *Flux-Lab/historique*)",
    "Bash(less *Flux-Lab/historique*)", "Bash(more *Flux-Lab/historique*)", "Bash(grep *Flux-Lab/historique*)",
    "Bash(awk *Flux-Lab/historique*)", "Bash(sed *Flux-Lab/historique*)", "Bash(cp *Flux-Lab/historique*)",
)
FAMILLE_TABLEAUX = (
    "Read(./Flux-Lab/tableaux/**)",
    "Bash(cat *Flux-Lab/tableaux*)", "Bash(head *Flux-Lab/tableaux*)", "Bash(tail *Flux-Lab/tableaux*)", "Bash(less *Flux-Lab/tableaux*)",
    "Bash(more *Flux-Lab/tableaux*)", "Bash(grep *Flux-Lab/tableaux*)", "Bash(awk *Flux-Lab/tableaux*)", "Bash(sed *Flux-Lab/tableaux*)",
    "Bash(cp *Flux-Lab/tableaux*)",
)
FAMILLE_ANCIENNE_TABLE = (
    "Read(./Flux-Lab/equipes-assets.yaml)", "Read(//**/Flux-Lab/equipes-assets.yaml)", "Read(~/**/Flux-Lab/equipes-assets.yaml)",
    "Bash(cat *equipes-assets.yaml*)", "Bash(head *equipes-assets.yaml*)", "Bash(tail *equipes-assets.yaml*)",
    "Bash(less *equipes-assets.yaml*)", "Bash(more *equipes-assets.yaml*)", "Bash(grep *equipes-assets.yaml*)",
    "Bash(awk *equipes-assets.yaml*)", "Bash(sed *equipes-assets.yaml*)", "Bash(cp *equipes-assets.yaml*)",
    "Bash(rg *equipes-assets.yaml*)",
)
FAMILLE_NOMS_SENSIBLES = (
    "Read(./Flux-Lab/noms-sensibles.txt)",
    "Bash(cat *noms-sensibles.txt*)", "Bash(head *noms-sensibles.txt*)", "Bash(tail *noms-sensibles.txt*)",
    "Bash(less *noms-sensibles.txt*)", "Bash(more *noms-sensibles.txt*)", "Bash(grep *noms-sensibles.txt*)",
    "Bash(awk *noms-sensibles.txt*)", "Bash(sed *noms-sensibles.txt*)", "Bash(cp *noms-sensibles.txt*)",
)
FAMILLE_REFERENTIEL = (
    "Read(./Flux-Lab/organisation.yaml)", "Read(//**/Flux-Lab/organisation.yaml)", "Read(~/**/Flux-Lab/organisation.yaml)",
    "Bash(cat *organisation.yaml*)", "Bash(head *organisation.yaml*)", "Bash(tail *organisation.yaml*)",
    "Bash(less *organisation.yaml*)", "Bash(more *organisation.yaml*)", "Bash(grep *organisation.yaml*)",
    "Bash(awk *organisation.yaml*)", "Bash(sed *organisation.yaml*)", "Bash(cp *organisation.yaml*)",
)
FAMILLE_CATALOGUE = (
    "Read(./Flux-Lab/equipes-jira.yaml)", "Read(//**/Flux-Lab/equipes-jira.yaml)", "Read(~/**/Flux-Lab/equipes-jira.yaml)",
    "Bash(cat *equipes-jira.yaml*)", "Bash(head *equipes-jira.yaml*)", "Bash(tail *equipes-jira.yaml*)",
    "Bash(less *equipes-jira.yaml*)", "Bash(more *equipes-jira.yaml*)", "Bash(grep *equipes-jira.yaml*)",
    "Bash(awk *equipes-jira.yaml*)", "Bash(sed *equipes-jira.yaml*)", "Bash(cp *equipes-jira.yaml*)",
    "Bash(rg *equipes-jira.yaml*)", "Bash(bat *equipes-jira.yaml*)", "Bash(nl *equipes-jira.yaml*)", "Bash(tac *equipes-jira.yaml*)",
    "Bash(rev *equipes-jira.yaml*)", "Bash(strings *equipes-jira.yaml*)", "Bash(xxd *equipes-jira.yaml*)",
    "Bash(od *equipes-jira.yaml*)", "Bash(hexdump *equipes-jira.yaml*)", "Bash(cut *equipes-jira.yaml*)",
    "Bash(sort *equipes-jira.yaml*)", "Bash(uniq *equipes-jira.yaml*)", "Bash(diff *equipes-jira.yaml*)",
    "Bash(cmp *equipes-jira.yaml*)", "Bash(base64 *equipes-jira.yaml*)", "Bash(view *equipes-jira.yaml*)",
    "Bash(vi *equipes-jira.yaml*)", "Bash(vim *equipes-jira.yaml*)", "Bash(nano *equipes-jira.yaml*)",
    "Bash(rsync *equipes-jira.yaml*)", "Bash(ditto *equipes-jira.yaml*)", "Bash(tar *equipes-jira.yaml*)",
    "Bash(zip *equipes-jira.yaml*)", "Bash(ln *equipes-jira.yaml*)", "Bash(mv *equipes-jira.yaml*)",
)
FAMILLE_CATALOGUE_TMP = (
    "Read(./Flux-Lab/equipes-jira.tmp)", "Read(//**/Flux-Lab/equipes-jira.tmp)", "Read(~/**/Flux-Lab/equipes-jira.tmp)",
    "Bash(cat *equipes-jira.tmp*)", "Bash(head *equipes-jira.tmp*)", "Bash(tail *equipes-jira.tmp*)",
    "Bash(less *equipes-jira.tmp*)", "Bash(more *equipes-jira.tmp*)", "Bash(grep *equipes-jira.tmp*)",
    "Bash(awk *equipes-jira.tmp*)", "Bash(sed *equipes-jira.tmp*)", "Bash(cp *equipes-jira.tmp*)",
    "Bash(rg *equipes-jira.tmp*)", "Bash(bat *equipes-jira.tmp*)", "Bash(nl *equipes-jira.tmp*)", "Bash(tac *equipes-jira.tmp*)",
    "Bash(rev *equipes-jira.tmp*)", "Bash(strings *equipes-jira.tmp*)", "Bash(xxd *equipes-jira.tmp*)",
    "Bash(od *equipes-jira.tmp*)", "Bash(hexdump *equipes-jira.tmp*)", "Bash(cut *equipes-jira.tmp*)",
    "Bash(sort *equipes-jira.tmp*)", "Bash(uniq *equipes-jira.tmp*)", "Bash(diff *equipes-jira.tmp*)",
    "Bash(cmp *equipes-jira.tmp*)", "Bash(base64 *equipes-jira.tmp*)", "Bash(view *equipes-jira.tmp*)",
    "Bash(vi *equipes-jira.tmp*)", "Bash(vim *equipes-jira.tmp*)", "Bash(nano *equipes-jira.tmp*)",
    "Bash(rsync *equipes-jira.tmp*)", "Bash(ditto *equipes-jira.tmp*)", "Bash(tar *equipes-jira.tmp*)",
    "Bash(zip *equipes-jira.tmp*)", "Bash(ln *equipes-jira.tmp*)", "Bash(mv *equipes-jira.tmp*)",
)
FAMILLE_LISTE_ASSETS = (
    "Read(./Flux-Lab/equipes-assets-complet-*.csv)", "Read(//**/Flux-Lab/equipes-assets-complet-*.csv)",
    "Read(~/**/Flux-Lab/equipes-assets-complet-*.csv)",
    "Bash(cat *equipes-assets-complet*)", "Bash(head *equipes-assets-complet*)", "Bash(tail *equipes-assets-complet*)",
    "Bash(less *equipes-assets-complet*)", "Bash(more *equipes-assets-complet*)", "Bash(grep *equipes-assets-complet*)",
    "Bash(awk *equipes-assets-complet*)", "Bash(sed *equipes-assets-complet*)", "Bash(cp *equipes-assets-complet*)",
    "Bash(rg *equipes-assets-complet*)", "Bash(bat *equipes-assets-complet*)", "Bash(nl *equipes-assets-complet*)",
    "Bash(tac *equipes-assets-complet*)", "Bash(rev *equipes-assets-complet*)", "Bash(strings *equipes-assets-complet*)",
    "Bash(xxd *equipes-assets-complet*)", "Bash(od *equipes-assets-complet*)", "Bash(hexdump *equipes-assets-complet*)",
    "Bash(cut *equipes-assets-complet*)", "Bash(sort *equipes-assets-complet*)", "Bash(uniq *equipes-assets-complet*)",
    "Bash(diff *equipes-assets-complet*)", "Bash(cmp *equipes-assets-complet*)", "Bash(base64 *equipes-assets-complet*)",
    "Bash(view *equipes-assets-complet*)", "Bash(vi *equipes-assets-complet*)", "Bash(vim *equipes-assets-complet*)",
    "Bash(nano *equipes-assets-complet*)", "Bash(rsync *equipes-assets-complet*)", "Bash(ditto *equipes-assets-complet*)",
    "Bash(tar *equipes-assets-complet*)", "Bash(zip *equipes-assets-complet*)", "Bash(ln *equipes-assets-complet*)",
    "Bash(mv *equipes-assets-complet*)",
)
FAMILLE_ARCHIVE = (
    # 6 Read : la famille antérieure (3) et celle du dossier d'archive (3)
    "Read(~/PMZilla-Lab/archives-equipes/**)", "Read(//**/PMZilla-Lab/archives-equipes/**)", "Read(**/archives-equipes/**)",
    "Read(~/PMZilla-Lab/archives/archives-equipes/**)", "Read(~/**/archives-equipes/**)", "Read(//**/archives-equipes/**)",
    # 34 lecteurs
    "Bash(cat *archives-equipes*)", "Bash(head *archives-equipes*)", "Bash(tail *archives-equipes*)", "Bash(less *archives-equipes*)",
    "Bash(more *archives-equipes*)", "Bash(grep *archives-equipes*)", "Bash(awk *archives-equipes*)", "Bash(sed *archives-equipes*)",
    "Bash(cp *archives-equipes*)", "Bash(rg *archives-equipes*)", "Bash(bat *archives-equipes*)", "Bash(nl *archives-equipes*)",
    "Bash(tac *archives-equipes*)", "Bash(rev *archives-equipes*)", "Bash(strings *archives-equipes*)", "Bash(xxd *archives-equipes*)",
    "Bash(od *archives-equipes*)", "Bash(hexdump *archives-equipes*)", "Bash(cut *archives-equipes*)", "Bash(sort *archives-equipes*)",
    "Bash(uniq *archives-equipes*)", "Bash(diff *archives-equipes*)", "Bash(cmp *archives-equipes*)", "Bash(base64 *archives-equipes*)",
    "Bash(view *archives-equipes*)", "Bash(vi *archives-equipes*)", "Bash(vim *archives-equipes*)", "Bash(nano *archives-equipes*)",
    "Bash(rsync *archives-equipes*)", "Bash(ditto *archives-equipes*)", "Bash(tar *archives-equipes*)", "Bash(zip *archives-equipes*)",
    "Bash(ln *archives-equipes*)", "Bash(mv *archives-equipes*)",
    # 5 listages
    "Bash(ls *archives-equipes*)", "Bash(/bin/ls *archives-equipes*)", "Bash(eza *archives-equipes*)", "Bash(find *archives-equipes*)",
    "Bash(tree *archives-equipes*)",
)
FAMILLE_REVUES = (
    "Read(./Flux-Lab/equipes-revues.yaml)", "Read(//**/Flux-Lab/equipes-revues.yaml)", "Read(~/**/Flux-Lab/equipes-revues.yaml)",
    "Bash(cat *equipes-revues.yaml*)", "Bash(head *equipes-revues.yaml*)", "Bash(tail *equipes-revues.yaml*)",
    "Bash(less *equipes-revues.yaml*)", "Bash(more *equipes-revues.yaml*)", "Bash(grep *equipes-revues.yaml*)",
    "Bash(awk *equipes-revues.yaml*)", "Bash(sed *equipes-revues.yaml*)", "Bash(cp *equipes-revues.yaml*)",
    "Bash(rg *equipes-revues.yaml*)", "Bash(bat *equipes-revues.yaml*)", "Bash(nl *equipes-revues.yaml*)", "Bash(tac *equipes-revues.yaml*)",
    "Bash(rev *equipes-revues.yaml*)", "Bash(strings *equipes-revues.yaml*)", "Bash(xxd *equipes-revues.yaml*)",
    "Bash(od *equipes-revues.yaml*)", "Bash(hexdump *equipes-revues.yaml*)", "Bash(cut *equipes-revues.yaml*)",
    "Bash(sort *equipes-revues.yaml*)", "Bash(uniq *equipes-revues.yaml*)", "Bash(diff *equipes-revues.yaml*)",
    "Bash(cmp *equipes-revues.yaml*)", "Bash(base64 *equipes-revues.yaml*)", "Bash(view *equipes-revues.yaml*)",
    "Bash(vi *equipes-revues.yaml*)", "Bash(vim *equipes-revues.yaml*)", "Bash(nano *equipes-revues.yaml*)",
    "Bash(rsync *equipes-revues.yaml*)", "Bash(ditto *equipes-revues.yaml*)", "Bash(tar *equipes-revues.yaml*)",
    "Bash(zip *equipes-revues.yaml*)", "Bash(ln *equipes-revues.yaml*)", "Bash(mv *equipes-revues.yaml*)",
    "Edit(./Flux-Lab/equipes-revues.yaml)", "Edit(//**/Flux-Lab/equipes-revues.yaml)", "Edit(~/**/Flux-Lab/equipes-revues.yaml)",
    "Read(./Flux-Lab/equipes-revues.yaml.tmp)", "Read(//**/Flux-Lab/equipes-revues.yaml.tmp)", "Read(~/**/Flux-Lab/equipes-revues.yaml.tmp)",
)
# Lancements de check-teams, migrate-teams, review-teams : 8 formes chacune (lignes 963-978 et 1272-1279 du fichier) ...
FAMILLE_LANCEMENTS_ANCRES = (
    "Bash(uv run *export_jira_api.py check-teams*)", "Bash(python *export_jira_api.py check-teams*)",
    "Bash(python3 *export_jira_api.py check-teams*)", "Bash(tools/export_jira_api.py check-teams*)",
    "Bash(./tools/export_jira_api.py check-teams*)", "Bash(~/*export_jira_api.py check-teams*)",
    "Bash($HOME/*export_jira_api.py check-teams*)", "Bash(/*export_jira_api.py check-teams*)",
    "Bash(uv run *export_jira_api.py migrate-teams*)", "Bash(python *export_jira_api.py migrate-teams*)",
    "Bash(python3 *export_jira_api.py migrate-teams*)", "Bash(tools/export_jira_api.py migrate-teams*)",
    "Bash(./tools/export_jira_api.py migrate-teams*)", "Bash(~/*export_jira_api.py migrate-teams*)",
    "Bash($HOME/*export_jira_api.py migrate-teams*)", "Bash(/*export_jira_api.py migrate-teams*)",
    "Bash(uv run *export_jira_api.py review-teams*)", "Bash(python *export_jira_api.py review-teams*)",
    "Bash(python3 *export_jira_api.py review-teams*)", "Bash(tools/export_jira_api.py review-teams*)",
    "Bash(./tools/export_jira_api.py review-teams*)", "Bash(~/*export_jira_api.py review-teams*)",
    "Bash($HOME/*export_jira_api.py review-teams*)", "Bash(/*export_jira_api.py review-teams*)",
)
# ... et la famille récente de check-teams (lignes 1458-1471 du fichier), que la génération par famille ne contrôlait pas.
FAMILLE_LANCEMENTS_CHECK_RECENTS = (
    "Bash(uv run */export_jira_api.py check-teams*)", "Bash(uv run export_jira_api.py check-teams*)",
    "Bash(uv run * export_jira_api.py check-teams*)", "Bash(python */export_jira_api.py check-teams*)",
    "Bash(python export_jira_api.py check-teams*)", "Bash(python * export_jira_api.py check-teams*)",
    "Bash(python3 */export_jira_api.py check-teams*)", "Bash(python3 export_jira_api.py check-teams*)",
    "Bash(python3 * export_jira_api.py check-teams*)", "Bash(~/*tools/export_jira_api.py check-teams*)",
    "Bash($HOME/*tools/export_jira_api.py check-teams*)", "Bash(/*tools/export_jira_api.py check-teams*)",
    "Bash(export_jira_api.py check-teams*)", "Bash(./export_jira_api.py check-teams*)",
)
FAMILLE_BASE_DE_DONNEES = (
    "Bash(psql*)", "Bash(*psql *)", "Bash(pg_dump*)", "Bash(pg_restore*)", "Bash(pg_dumpall*)", "Bash(docker*exec*)",
    "Bash(docker*psql*)", "Bash(docker-compose*exec*)", "Bash(docker cp *)", "Bash(docker container cp *)",
    "Bash(docker compose cp *)", "Bash(docker-compose cp *)", "Read(~/.pmzilla-lab/sauvegardes/**)",
)
FAMILLE_SECRETS = (
    "Bash(security find-generic-password*)", "Bash(security *pmzilla-jira*)", "Bash(security *pmzilla-story-analysis*)",
    "Bash(gh auth token*)", "Bash(*/gh auth token*)", "Bash(env *gh auth token*)", "Bash(*/env *gh auth token*)",
)

# Famille -> (décompte annoncé par la table de D5, règles). Le décompte de l'archive est 45 : le fichier compte 6 Read, 34 lecteurs
# et 5 listages (le générateur d'avant en comptait 43 et manquait Read(//**/PMZilla-Lab/archives-equipes/**) et Read(**/archives-equipes/**)).
FAMILLES_D5 = {
    "exports": (10, FAMILLE_EXPORTS),
    "dossier d'historique": (10, FAMILLE_HISTORIQUE),
    "tableaux": (10, FAMILLE_TABLEAUX),
    "ancienne table des équipes": (13, FAMILLE_ANCIENNE_TABLE),
    "noms sensibles": (10, FAMILLE_NOMS_SENSIBLES),
    "référentiel": (12, FAMILLE_REFERENTIEL),
    "catalogue": (37, FAMILLE_CATALOGUE),
    "fichier temporaire du catalogue": (37, FAMILLE_CATALOGUE_TMP),
    "liste Assets": (37, FAMILLE_LISTE_ASSETS),
    "archive de l'ancienne table": (45, FAMILLE_ARCHIVE),
    "liste de revue": (43, FAMILLE_REVUES),
    "lancements check/migrate/review-teams": (24, FAMILLE_LANCEMENTS_ANCRES),
    "lancements récents de check-teams": (14, FAMILLE_LANCEMENTS_CHECK_RECENTS),
    "base de données": (13, FAMILLE_BASE_DE_DONNEES),
    "secrets": (7, FAMILLE_SECRETS),
}

REGLES_A_GARDER = [regle for _, regles in FAMILLES_D5.values() for regle in regles]


def regles_attendues() -> list:
    """Les 16 règles de lancement de `extract-teams` que l'auteur ajoute (tâche 9.1) : aucune ne commence par un joker."""
    return list(REGLES_EXTRACT)


# --- formes de lancement ---
LANCEURS = ("uv run", "uv run --isolated", "uv run python", "uv run python3", "uv run --with pyyaml", "uv run -q",
            "python", "python3", "python3 -I", "python3 -W ignore")
CHEMINS = ("tools/{s}", "./tools/{s}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}",
           "$HOME/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/{s}", "/Users/quelquun/PMZilla-Lab/{s}", "{s}")
EXECUTION_DIRECTE = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
                     "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "{s}", "./{s}")
OPTIONS = ("", " --language en", " --language fr", " --help", " --language=en")

# Lecture de l'extrait : toutes les formes de chemin (outil Read et lecteurs du terminal).
FORMES_LECTEUR = ("Flux-Lab/{f}", "./Flux-Lab/{f}", "/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/{f}",
                  "~/PMZilla-Lab/workspace/Flux-Lab/{f}", "$HOME/PMZilla-Lab/workspace/Flux-Lab/{f}", "{f}", "/tmp/copie/{f}")
CHEMINS_READ_EXTRAIT = ("Flux-Lab/{f}", "./Flux-Lab/{f}", "/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/{f}",
                        "~/PMZilla-Lab/workspace/Flux-Lab/{f}")
LECTEURS_COURANTS = ("cat", "head -n 5", "tail -f", "less", "more", "grep -r secret", "awk '{print $1}'", "sed -n 1,5p", "cp",
                     "rg team", "bat", "nl", "tac", "rev", "strings", "xxd", "od", "hexdump", "cut -d: -f1", "sort -u", "uniq -c",
                     "diff README.md", "cmp README.md", "base64", "view", "vi", "vim", "nano", "rsync -a", "ditto",
                     "tar -cf /tmp/archive.tar", "zip /tmp/archive.zip", "ln -s", "mv")

# Commandes qui ne font que citer la sous-commande ou le nom de l'extrait : permises.
COMMANDES_PERMISES = (
    "grep -rn extract-teams docs/", "grep -n 'extract-teams' tools/export_jira_api.py",
    "grep -rn extract-teams docs/pmzilla/installation.md", "git grep extract-teams -- docs/",
    "git grep -n extract-teams -- tools/export_jira_api_equipes.py", f"git grep {EXTRAIT} -- docs/",
    "rg extract-teams openspec/", "cat tools/export_jira_api_equipes.py", "head -40 tools/export_jira_api.py",
    "git log --oneline -3 -- tools/export_jira_api.py", "uv run tools/export_jira_api.py --help",
    "uv run --with pyyaml python -W ignore -m unittest discover -s tests/export_jira_api -q -f",
    "uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q", "bash tests/run_all.sh settings_deny",
    "python3 tests/settings_deny/test_settings_deny_team_names.py --json",
)


def commandes_refusees():
    """Toutes les formes de lancement de `extract-teams` que la session ne doit pas pouvoir exécuter."""
    sous = SOUS_COMMANDE
    for lanceur, chemin, option in itertools.product(LANCEURS, CHEMINS, OPTIONS):
        yield f"{lanceur} {chemin.format(s=SCRIPT)} {sous}{option}"
    for chemin, option in itertools.product(EXECUTION_DIRECTE, OPTIONS):
        yield f"{chemin.format(s=SCRIPT)} {sous}{option}"


def lectures_de_l_extrait():
    """Commandes du terminal qui lisent l'extrait, sous chaque forme de chemin."""
    for lecteur, forme in itertools.product(LECTEURS_COURANTS, FORMES_LECTEUR):
        yield f"{lecteur} {forme.format(f=EXTRAIT)}"


class BlocExtrait(unittest.TestCase):
    """Le bloc de 16 règles seul, avec le moteur de motifs : toujours vert, avant comme après la pose."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_EXTRACT)

    def test_le_bloc_a_seize_regles_sans_doublon(self):
        self.assertEqual(len(REGLES_EXTRACT), 16)
        self.assertEqual(len(set(REGLES_EXTRACT)), 16)
        self.assertEqual(regles_attendues(), REGLES_EXTRACT)

    def test_la_garde_partagee_passe_sur_le_bloc(self):
        """Aucune règle Write(chemin) ni NotebookEdit(chemin), aucune règle vide ou mal formée, aucun doublon, liste non vide."""
        self.assertEqual(garde_regles.constats(regles_attendues()), [])
        self.assertTrue(garde_regles.imprime_json(Path(__file__).read_text(encoding="utf-8")))

    def test_aucune_regle_ne_commence_par_un_joker(self):
        self.assertEqual([r for r in REGLES_EXTRACT if r.startswith("Bash(*")], [])
        self.assertTrue(all(r.startswith("Bash(") and r.endswith("*)") for r in REGLES_EXTRACT))

    def test_chaque_lanceur_chaque_chemin_chaque_option(self):
        manquantes = [c for c in commandes_refusees() if not self.moteur.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} formes de lancement de {SOUS_COMMANDE} non refusées")

    def test_la_matrice_n_est_pas_vide(self):
        self.assertGreater(len(list(commandes_refusees())), 400)

    def test_les_commandes_qui_ne_font_que_citer_restent_permises(self):
        refusees = [c for c in COMMANDES_PERMISES if self.moteur.interdite(c)]
        self.assertEqual(refusees, [])

    def test_les_autres_sous_commandes_ne_sont_pas_visees_par_le_bloc(self):
        for sous in ("--help", "fields", "check-teams"):
            self.assertFalse(self.moteur.interdite(f"uv run tools/{SCRIPT} {sous}"), sous)


class DansLeFichierDeReglages(unittest.TestCase):
    """Contre les vrais réglages : les règles gardées et l'extrait lisible dans tous les cas, la pose des 16 règles sautée avant."""

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.moteur = Moteur(cls.deny)

    # -- règles gardées (D5, décision b) : échec dès qu'une manque, dans tous les cas
    def test_la_liste_des_regles_gardees_est_sans_doublon(self):
        self.assertEqual(sorted({r for r in REGLES_A_GARDER if REGLES_A_GARDER.count(r) > 1}), [])
        self.assertFalse([r for r in REGLES_A_GARDER if r.startswith(("Write(", "NotebookEdit("))])

    def test_chaque_famille_a_le_decompte_de_la_table_de_d5(self):
        ecarts = {nom: (attendu, len(regles)) for nom, (attendu, regles) in FAMILLES_D5.items() if len(regles) != attendu}
        self.assertEqual(ecarts, {}, "famille : (décompte de D5, règles listées)")
        self.assertEqual([len(r) for _, r in FAMILLES_D5.values()], [10, 10, 10, 13, 10, 12, 37, 37, 37, 45, 43, 24, 14, 13, 7])
        self.assertEqual(len(REGLES_A_GARDER), 322)

    def test_les_regles_gardees_sont_dans_les_reglages(self):
        manquantes = [r for r in REGLES_A_GARDER if r not in self.deny]
        self.assertEqual(manquantes, [], f"{len(manquantes)} règle(s) gardée(s) absente(s) de .claude/settings.json (D5) : "
                                         + " ; ".join(manquantes))

    def test_chaque_famille_est_entierement_dans_les_reglages(self):
        for nom, (_, regles) in FAMILLES_D5.items():
            manquantes = [r for r in regles if r not in self.deny]
            self.assertEqual(manquantes, [], f"famille « {nom} » : {len(manquantes)} règle(s) absente(s) de .claude/settings.json")

    def test_le_catalogue_garde_ses_37_regles(self):
        """Décision b : le catalogue des équipes n'est pas ouvert en brut ; aucune de ses 3 règles Read ni de ses 34 lecteurs ne manque."""
        catalogue = _read3("equipes-jira.yaml") + _lecteurs(LECTEURS, "equipes-jira.yaml")
        self.assertEqual(len(catalogue), 37)
        self.assertEqual([r for r in catalogue if r not in self.deny], [])

    def test_les_regles_read_du_referentiel_et_des_noms_sensibles_sont_gardees(self):
        for regle in ("Read(./Flux-Lab/noms-sensibles.txt)", "Read(./Flux-Lab/organisation.yaml)",
                      "Read(//**/Flux-Lab/organisation.yaml)", "Read(~/**/Flux-Lab/organisation.yaml)"):
            self.assertIn(regle, self.deny)

    def test_les_equipes_ne_sont_pas_lisibles_en_brut(self):
        for fichier in ("equipes-jira.yaml", "organisation.yaml", "equipes-assets.yaml", "noms-sensibles.txt", "equipes-revues.yaml"):
            for lecteur, forme in itertools.product(("cat", "head -n 5", "grep -r x", "sed -n 1,5p", "cp"), FORMES_LECTEUR):
                commande = f"{lecteur} {forme.format(f=fichier)}"
                self.assertTrue(self.moteur.interdite(commande), commande)

    def test_aucune_regle_write_ni_notebookedit_ne_vise_le_dossier_de_flux(self):
        self.assertEqual([d for d in self.deny if "Flux-Lab" in d and d.startswith(("Write(", "NotebookEdit("))], [])

    # -- l'extrait reste lisible, dans tous les cas
    def test_l_extrait_est_lisible_par_l_outil_read(self):
        for chemin in CHEMINS_READ_EXTRAIT:
            self.assertFalse(self.moteur.lecture_interdite(chemin.format(f=EXTRAIT)), chemin)
        self.assertEqual([d for d in self.deny if EXTRAIT in d], [])

    def test_l_extrait_est_lisible_par_les_lecteurs_du_terminal(self):
        refusees = [c for c in lectures_de_l_extrait() if self.moteur.interdite(c)]
        self.assertEqual(refusees[:5], [], f"{len(refusees)} lecture(s) de l'extrait refusée(s)")

    def test_citer_la_sous_commande_reste_permis_avec_les_vrais_reglages(self):
        refusees = [c for c in COMMANDES_PERMISES if self.moteur.interdite(c)]
        self.assertEqual(refusees, [])

    # -- pose des 16 règles : sautée avant, échec si partielle, matrice rejouée si complète
    def exiger_la_pose(self):
        presentes = [r for r in REGLES_EXTRACT if r in self.deny]
        manquantes = [r for r in REGLES_EXTRACT if r not in self.deny]
        if not presentes:
            self.fail("règles de lancement de extract-teams pas encore posées par l'auteur (tâche 9.1)")
        if manquantes:
            self.fail(f"{len(manquantes)} règle(s) de lancement de {SOUS_COMMANDE} absente(s) de .claude/settings.json : "
                      + " ; ".join(manquantes))

    def test_les_16_regles_de_lancement_sont_dans_les_reglages(self):
        self.exiger_la_pose()

    def test_extract_teams_jamais_lance_par_la_session(self):
        self.exiger_la_pose()
        manquantes = [c for c in commandes_refusees() if not self.moteur.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} formes de lancement de {SOUS_COMMANDE} non refusées")


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    else:
        unittest.main()
