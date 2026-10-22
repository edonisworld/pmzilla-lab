"""Règles `deny` des lecteurs `strings`, `xxd`, `od`, `rg` et `bat` sur les chemins protégés du dossier de flux (audit du 2026-10-20, R13).

Ces cinq lecteurs sont refusés pour le catalogue des équipes, pas pour les six chemins protégés que CLAUDE.md nomme (exports/,
historique/, tableaux/, organisation.yaml, noms-sensibles.txt, equipes-assets.yaml) ni pour la liste des versions de produit
(versions-produit.txt). Chaque chemin garde la clé de ses règles existantes (`Bash(cat *<clé>*)`) : la nouvelle règle est
`Bash(<lecteur> *<clé>*)`, même forme que les lecteurs du catalogue des équipes. La règle `Bash(rg *equipes-assets.yaml*)` est déjà
posée : elle n'est pas dans la liste à ajouter (pas de doublon dans permissions.deny), mais elle est vérifiée comme les autres.

Les règles sont ajoutées à .claude/settings.json par l'auteur seul (fichier d'étape). Tant qu'elles n'y sont pas, les cas de lecture
échouent : c'est attendu, ce fichier se commite avec les règles. `python3 tests/settings_deny/test_settings_deny_lecteurs_flux.py --json`
imprime la liste exacte à copier dans permissions.deny. Aucune commande n'est lancée ; le test ne lit que le fichier de réglages.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
"""
import itertools
import json
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
REGLAGES = RACINE / ".claude" / "settings.json"

LECTEURS = ("strings", "xxd", "od", "rg", "bat")
# Clé de chaque chemin protégé, telle que l'écrivent ses règles existantes `Bash(cat *<clé>*)`.
CLES_DOSSIERS = ("Flux-Lab/exports", "Flux-Lab/historique", "Flux-Lab/tableaux")
CLES_FICHIERS = ("organisation.yaml", "noms-sensibles.txt", "equipes-assets.yaml", "versions-produit.txt")
CLES = CLES_DOSSIERS + CLES_FICHIERS
DEJA_POSEES = ("Bash(rg *equipes-assets.yaml*)",)

LECTEURS_COURANTS = ("strings", "strings -n 8", "xxd", "xxd -l 64", "od", "od -c", "rg équipe", "rg -n x", "bat", "bat --plain")
FORMES = ("Flux-Lab/{f}", "./Flux-Lab/{f}", "/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/{f}",
          "~/PMZilla-Lab/workspace/Flux-Lab/{f}", "$HOME/PMZilla-Lab/workspace/Flux-Lab/{f}")
DANS_LES_DOSSIERS = ("exports/jira.csv", "historique/2026-10.jsonl", "tableaux/flux.md", "exports")
AUTRES_COMMANDES = ("rg flux Flux-Lab/rapports", "bat Flux-Lab/flux.yaml", "bat Flux-Lab/equipes-lisibles.yaml", "od -c README.md",
                    "xxd tools/pipe_guard.py", "strings tests/run_all.sh", "rg exports tools/", "rg historique docs/",
                    "git grep organisation.yaml -- docs/")


def regles_attendues() -> list:
    """Les 34 règles que l'auteur ajoute : 5 lecteurs × 7 chemins, moins la règle rg déjà posée pour equipes-assets.yaml."""
    toutes = [f"Bash({lecteur} *{cle}*)" for cle in CLES for lecteur in LECTEURS]
    return [r for r in toutes if r not in DEJA_POSEES]


def motif_en_regex(motif: str) -> re.Pattern:
    """« Bash(motif) » : le joker * vaut n'importe quelle suite (y compris vide), tout le reste est littéral."""
    return re.compile("".join(".*" if c == "*" else re.escape(c) for c in motif), re.DOTALL)


def moteur(deny: list):
    motifs = [motif_en_regex(d[len("Bash("):-1]) for d in deny if d.startswith("Bash(")]
    return lambda commande: any(m.fullmatch(commande) for m in motifs)


def commandes_refusees():
    for lecteur, forme, chemin in itertools.product(LECTEURS_COURANTS, FORMES, DANS_LES_DOSSIERS + CLES_FICHIERS):
        yield f"{lecteur} {forme.format(f=chemin)}"
    for lecteur, nom in itertools.product(LECTEURS_COURANTS, CLES_FICHIERS):
        yield f"{lecteur} {nom}"
        yield f"{lecteur} /tmp/copie/{nom}"


class LaListe(unittest.TestCase):
    """La liste déclarée, indépendante du fichier de réglages."""

    def test_34_regles_sans_doublon_ni_ecriture(self):
        regles = regles_attendues()
        self.assertEqual(len(regles), 34)
        self.assertEqual(len(set(regles)), 34)
        self.assertFalse([r for r in regles if r.startswith(("Write(", "NotebookEdit("))])
        self.assertFalse(set(regles) & set(DEJA_POSEES))

    def test_la_liste_et_les_regles_deja_posees_refusent_toutes_les_formes(self):
        interdite = moteur(regles_attendues() + list(DEJA_POSEES))
        self.assertEqual([c for c in commandes_refusees() if not interdite(c)][:5], [])

    def test_les_autres_commandes_restent_permises(self):
        interdite = moteur(regles_attendues() + list(DEJA_POSEES))
        self.assertEqual([c for c in AUTRES_COMMANDES if interdite(c)], [])


class DansLeFichierDeReglages(unittest.TestCase):
    """Rouge tant que l'auteur n'a pas posé les 34 règles ; vert ensuite."""

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]

    def test_les_regles_deja_posees_y_sont(self):
        self.assertEqual([r for r in DEJA_POSEES if r not in self.deny], [])

    def test_les_34_regles_sont_dans_settings_json(self):
        manquantes = [r for r in regles_attendues() if r not in self.deny]
        self.assertEqual(manquantes, [], f"{len(manquantes)} règle(s) des lecteurs du dossier de flux absente(s) de .claude/settings.json")

    def test_les_cinq_lecteurs_sont_refuses_par_les_regles_reelles(self):
        interdite = moteur(self.deny)
        non_refusees = [c for c in commandes_refusees() if not interdite(c)]
        self.assertEqual(non_refusees[:5], [], f"{len(non_refusees)} formes non refusées")

    def test_les_autres_commandes_restent_permises_par_les_regles_reelles(self):
        interdite = moteur(self.deny)
        self.assertEqual([c for c in AUTRES_COMMANDES if interdite(c)], [])


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    else:
        unittest.main()
