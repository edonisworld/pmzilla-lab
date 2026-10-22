"""Règle `allow` de `story_quality.py grid` (décision de l'auteur du 2026-10-20, posée avec le bloc du lot 7, mothra-session-guards).

UNE règle, pour `permissions.allow` de .claude/settings.json : `Bash(uv run tools/story_quality.py grid*)`. Elle permet `grid`,
`grid --show`, `grid --show --json` (et `--language`) sans demande, jamais `story_quality.py *`. Les autres formes de lanceur de `grid`
restent ce qu'elles sont (couvertes ailleurs). `collect`, `review`, `analyse` et `coach` restent refusés par les règles deny déjà posées
(REGLES_D13, test_settings_deny_story_quality.py), y compris enchaînés après `grid` dans une même commande (`&&`, `;`, `|`).

Modèle : la précédence deny sur allow de Claude Code est représentée (une commande est refusée dès qu'une règle deny la couvre, permise
seulement si aucune deny ne la couvre et qu'une allow la couvre). Le découpage des commandes composées que fait Claude Code pour les règles
allow n'est PAS représenté : le moteur compare la commande entière, et le motif `grid*` couvre donc textuellement une chaîne `grid && …`.
Les chaînes vers collect, review, analyse et coach sont refusées dans le modèle par les règles deny réelles (`uv run */story_quality.py
collect*` couvre la chaîne entière) ; une chaîne vers une autre commande (`grid && rm x`) n'est arrêtée que par le découpage de Claude Code,
limite déclarée et assertée telle quelle.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.

    python3 tests/settings_deny/test_settings_deny_story_quality_grid.py --allow     (la règle à ajouter à permissions.allow)
"""
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import garde_regles  # noqa: E402
from test_settings_deny_npm import Moteur  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"
REGLE_ALLOW = "Bash(uv run tools/story_quality.py grid*)"
SOUS_COMMANDES_REFUSEES = ("collect", "review", "analyse", "coach")
SAUT = "règle allow de grid non posée"


def regles_allow() -> list:
    return [REGLE_ALLOW]


def permissions() -> dict:
    return json.loads(REGLAGES.read_text(encoding="utf-8")).get("permissions", {})


def decision(deny: list, allow: list, commande: str) -> str:
    """« refusée » si une deny couvre la commande (précédence), « permise » si une allow la couvre, sinon « à demander »."""
    if Moteur(deny).interdite(commande):
        return "refusée"
    if Moteur(allow).interdite(commande):
        return "permise"
    return "à demander"


GRID = "uv run tools/story_quality.py grid"
PERMISES = (GRID, f"{GRID} --show", f"{GRID} --show --json", f"{GRID} --show --language en", f"{GRID} --language en --show --json")
SECONDES = ("uv run tools/story_quality.py {s}", "python3 tools/story_quality.py {s}", "tools/story_quality.py {s} --dry-run",
            "uv run ~/PMZilla-Lab/workspace/tools/story_quality.py {s} --team x")
SEPARATEURS = (" && ", "; ", " | ")


def chaines():
    for premiere in (GRID, f"{GRID} --show"):
        for sep in SEPARATEURS:
            for seconde in SECONDES:
                for s in SOUS_COMMANDES_REFUSEES:
                    yield premiere + sep + seconde.format(s=s)


class Regle(unittest.TestCase):
    def test_une_seule_regle_qui_passe_la_garde(self):
        self.assertEqual(regles_allow(), ["Bash(uv run tools/story_quality.py grid*)"])
        self.assertEqual(garde_regles.constats(regles_allow()), [])

    def test_jamais_story_quality_entier(self):
        for regle in regles_allow():
            self.assertNotIn("story_quality.py *", regle)
            self.assertTrue(regle.endswith(" grid*)"), regle)

    def test_le_motif_couvre_les_formes_de_grid(self):
        moteur = Moteur(regles_allow())
        self.assertEqual([c for c in PERMISES if not moteur.interdite(c)], [])

    def test_le_motif_ne_couvre_aucune_autre_sous_commande_seule(self):
        moteur = Moteur(regles_allow())
        for s in SOUS_COMMANDES_REFUSEES + ("report",):
            for seconde in SECONDES:
                self.assertFalse(moteur.interdite(seconde.format(s=s)), seconde.format(s=s))

    def test_le_motif_couvre_textuellement_une_chaine(self):
        """Limite du modèle, assertée : sans découpage, `grid*` couvre `grid && …` ; la deny tranche (tests suivants)."""
        self.assertTrue(Moteur(regles_allow()).interdite(f"{GRID} && rm x"))


class AvecLesReglesReelles(unittest.TestCase):
    """Les règles deny réelles de .claude/settings.json, avec la règle allow déclarée (posée ou non)."""

    @classmethod
    def setUpClass(cls):
        cls.deny = permissions().get("deny", [])

    def test_grid_permis(self):
        self.assertEqual({c: decision(self.deny, regles_allow(), c) for c in PERMISES}, {c: "permise" for c in PERMISES})

    def test_sous_commandes_refusees_seules(self):
        for s in SOUS_COMMANDES_REFUSEES:
            for seconde in SECONDES:
                commande = seconde.format(s=s)
                self.assertEqual(decision(self.deny, regles_allow(), commande), "refusée", commande)

    def test_sous_commandes_refusees_enchainees_apres_grid(self):
        passees = [c for c in chaines() if decision(self.deny, regles_allow(), c) != "refusée"]
        self.assertEqual(passees[:10], [], f"{len(passees)} chaîne(s) non refusée(s)")


class DansLeFichierDeReglages(unittest.TestCase):
    """Sauté tant que la règle n'est pas dans permissions.allow ; ensuite, elle y est seule de sa famille."""

    def setUp(self):
        self.allow = permissions().get("allow", [])
        if REGLE_ALLOW not in self.allow:
            self.skipTest(SAUT)

    def test_aucune_regle_allow_plus_large_sur_story_quality(self):
        larges = [r for r in self.allow if "story_quality" in r and r != REGLE_ALLOW]
        self.assertEqual(larges, [])

    def test_les_chaines_restent_refusees_avec_le_fichier_reel(self):
        deny = permissions().get("deny", [])
        self.assertEqual([c for c in chaines() if decision(deny, self.allow, c) != "refusée"][:10], [])


if __name__ == "__main__":
    if "--allow" in sys.argv:
        print(json.dumps(regles_allow(), indent=2, ensure_ascii=False))
    else:
        unittest.main()
