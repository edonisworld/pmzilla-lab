"""Les règles du dossier de contexte (organisation-context, design D10) et l'état du fichier de réglages : avant ou après la tâche 9.3.

Module d'aide (aucun test) importé par test_settings_deny_contexte.py, test_settings_autres_regles.py et test_settings_deny_story_quality.py.

`REGLES_D10` : les 107 règles `deny` (113 avant le retrait des 6 règles `Write`) que l'auteur ajoute à `.claude/settings.json` à la tâche 9.3, sous le nom `contexte` du dossier.
Pas de règle `Write(chemin)` ni `NotebookEdit(chemin)` : Claude Code les ignore, `Edit(chemin)` couvre tous les outils d'édition (garde R-84, test_settings_deny_r84_flux_lab.py).
`reposee()` : vrai quand au moins une règle de la liste est déjà dans le fichier. Avant : les règles de l'ancien dossier sont en place ;
après : elles ont disparu et la règle `allow` aussi. Un état mélangé fait échouer test_settings_deny_contexte.py.

    python3 tests/settings_deny/etat_contexte.py --json     (imprime la liste à copier dans permissions.deny)
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
REGLAGES = RACINE / ".claude" / "settings.json"

DOSSIER = "contexte"                                  # le nom du dossier de contexte sous le dossier du lab (design D16)
ANCIEN_DOSSIER = "Contexte" + "-Lab"                  # l'ancien nom, écrit en deux morceaux : jamais en littéral dans un test non plus
ANCIENNE_REGLE_ALLOW = f"Read(~/PMZilla-Lab/{ANCIEN_DOSSIER}/notes/**)"
FICHIER_SURCOUCHE = "surcouche-qualite-stories.yaml"

LECTEURS = ("cat", "head", "tail", "less", "more", "grep", "rg", "awk", "sed", "cp", "strings", "bat", "xxd", "base64")   # les quatorze lecteurs
AUTRES_COMMANDES_ORIGINAUX = ("open", "qlmanage", "mv", "ls", "du", "zcat", "gzcat", "gunzip", "unzip", "textutil", "mdls", "xattr",
                              "ditto", "zip", "ln")
COMMANDES_DOSSIER_ENTIER = ("find", "tree", "rsync", "tar", "ditto", "zip")
FORMES_READ = (f"~/PMZilla-Lab/{DOSSIER}/%s/**", f"//**/{DOSSIER}/%s/**", f"~/**/{DOSSIER}/%s/**", f"**/{DOSSIER}/%s/**")
FORMES_ECRITURE = (f"~/PMZilla-Lab/{DOSSIER}/%s/**", f"//**/{DOSSIER}/%s/**", f"**/{DOSSIER}/%s/**")


def _lecture(sous):
    return [f"Read({forme % sous})" for forme in FORMES_READ]


def _ecriture(sous):
    return [f"Edit({forme % sous})" for forme in FORMES_ECRITURE]


REGLES_ORIGINAUX = tuple(_lecture("originaux") + [f"Bash({l} *{DOSSIER}/originaux*)" for l in LECTEURS + AUTRES_COMMANDES_ORIGINAUX])
REGLES_NOTES = tuple(_lecture("notes") + _ecriture("notes") + [f"Bash({l} *{DOSSIER}/notes*)" for l in LECTEURS])
REGLES_SURCOUCHE = tuple(_lecture("regles") + _ecriture("regles") + [f"Bash({l} *{DOSSIER}/regles*)" for l in LECTEURS]
                         + [f"Bash({l} *{DOSSIER}/*/{FICHIER_SURCOUCHE}*)" for l in LECTEURS])
REGLES_DOSSIER_ENTIER = tuple(f"Bash({c} {forme})" for c in COMMANDES_DOSSIER_ENTIER
                              for forme in (f"*{DOSSIER}", f"*{DOSSIER}/*", f"*{DOSSIER} *"))
REGLES_D10 = REGLES_ORIGINAUX + REGLES_NOTES + REGLES_SURCOUCHE + REGLES_DOSSIER_ENTIER


def reglages() -> dict:
    return json.loads(REGLAGES.read_text(encoding="utf-8"))


def deny_reel() -> list:
    return reglages()["permissions"]["deny"]


def reposee() -> bool:
    """Vrai quand le fichier de réglages porte au moins une règle de D10 (la tâche 9.3 est commencée ou faite)."""
    deny = set(deny_reel())
    return any(r in deny for r in REGLES_D10)


def nom_du_dossier() -> str:
    """Le nom que portent les règles du fichier réel : le nouveau après la tâche 9.3, l'ancien avant."""
    return DOSSIER if reposee() else ANCIEN_DOSSIER


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(list(REGLES_D10), indent=2, ensure_ascii=False))
