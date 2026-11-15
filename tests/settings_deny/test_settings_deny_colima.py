"""Règles `deny` de `colima start` et `colima stop`, et préfixes d'enveloppe de `ci_local.sh build` et `up` (R-20261104-11 Q-D1 et Q-E).

La base réelle tourne dans Docker sous Colima : un arrêt ou un démarrage par une session l'arrêterait brutalement. Ces règles sont des gestes de
l'auteur. Elles durcissent la consigne seule (rien ne les remplaçait) et ferment les préfixes env, nohup, command, time, exec et uv run devant
`ci_local.sh build`, `ci_local.sh up`, `colima start` et `colima stop`. Les règles directes de `ci_local.sh build` et `up` restent dans
test_settings_deny_ci_local.py (source de la liste des formes directes) ; ce module ne couvre que les préfixes, et les formes directes de colima.
Remplace : rien (la consigne seule) ; durcissement pour les préfixes. Condition de retrait : la base réelle ne tourne plus sous Colima.
Les fragments .claude/deny/*.txt n'admettent aucun commentaire (settings_assemble refuse une ligne qui n'est pas Outil(motif)) : ce
texte tient lieu de commentaire de tête de bloc.

Admis : `bash tools/ci_local.sh run <branche>`, `places`, `cle`, `colima status`, `colima list` (lecture).

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/test_settings_deny_colima.py --json
"""
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny import motif_en_regex  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"
FRAGMENT = RACINE / ".claude" / "deny" / "20-rehearsal-ci-local.txt"

ENVELOPPES = ("env", "nohup", "command", "time", "exec", "uv run")
CIBLES_CI = tuple(f"ci_local.sh {s}" for s in ("build", "up"))
CIBLES_COLIMA = tuple(f"colima {s}" for s in ("start", "stop"))
PREFIXES_COLIMA = ("", "./", "/*", "~/*", "$HOME/*")


def formes_enveloppe(cible: str) -> list:
    """Chaque enveloppe devant la cible : avec une barre (chemin), nue, ou précédée d'options."""
    return [f"Bash({e} {forme}{cible}*)" for e in ENVELOPPES for forme in ("*/", "", "* ")]


def formes_colima_directes(cible: str) -> list:
    return [f"Bash({p}{cible}*)" for p in PREFIXES_COLIMA]


REGLES_COLIMA = tuple(r for c in CIBLES_COLIMA for r in formes_colima_directes(c))
REGLES_ENVELOPPES = tuple(r for c in CIBLES_CI + CIBLES_COLIMA for r in formes_enveloppe(c))
REGLES_PRISES = REGLES_COLIMA + REGLES_ENVELOPPES


def regles_attendues() -> list:
    return list(REGLES_PRISES)


class Moteur:
    def __init__(self, regles):
        self.motifs = [motif_en_regex(r[len("Bash("):-1]) for r in regles if r.startswith("Bash(")]

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)


def commandes_refusees():
    for sous in ("start", "stop"):
        for c in (f"colima {sous}", f"colima {sous} --cpu 4", f"./colima {sous}", f"/opt/homebrew/bin/colima {sous}",
                  f"~/bin/colima {sous}", f"$HOME/bin/colima {sous}"):
            yield c
    for e in ENVELOPPES:
        for cible in ("bash tools/ci_local.sh build", "bash tools/ci_local.sh up main", "tools/ci_local.sh build", "ci_local.sh up",
                      "colima start", "colima stop", "colima start --cpu 4", "/opt/homebrew/bin/colima stop"):
            yield f"{e} {cible}"
        yield f"{e} FOO=1 bash tools/ci_local.sh up"


COMMANDES_ADMISES = (
    "bash tools/ci_local.sh run feat/x", "bash tools/ci_local.sh run", "bash tools/ci_local.sh places", "bash tools/ci_local.sh cle",
    "tools/ci_local.sh run main", "env bash tools/ci_local.sh run feat/x", "time bash tools/ci_local.sh places",
    "uv run tools/pilot.py freeze --check", "colima status", "colima list", "env colima status", "colima list --json",
    "git log --oneline -- tools/ci_local.sh", "bash tests/run_all.sh settings_deny",
)


class Bloc(unittest.TestCase):
    """Le moteur appliqué aux listes déclarées seules."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_PRISES)

    def test_pas_de_doublon_et_toutes_ancrees(self):
        self.assertEqual(len(REGLES_PRISES), len(set(REGLES_PRISES)))
        self.assertTrue(all(r.startswith("Bash(") and r.endswith(")") for r in REGLES_PRISES))
        self.assertEqual([r for r in REGLES_PRISES if r.startswith("Bash(*")], [], "règle à joker initial")

    def test_formes_refusees(self):
        manquantes = [c for c in commandes_refusees() if not self.moteur.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} forme(s) non refusée(s)")

    def test_formes_admises(self):
        refusees = [c for c in COMMANDES_ADMISES if self.moteur.interdite(c)]
        self.assertEqual(refusees, [], "commande(s) admise(s) refusée(s) : règle trop large")


class DansLesFichiers(unittest.TestCase):
    """Rouge tant que les règles ne sont pas dans le fragment et dans settings.json."""

    def test_les_regles_sont_dans_le_fragment(self):
        lignes = set(FRAGMENT.read_text(encoding="utf-8").splitlines())
        manquantes = [r for r in REGLES_PRISES if r not in lignes]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} règle(s) absente(s) de 20-rehearsal-ci-local.txt")

    def test_les_regles_sont_dans_settings_json(self):
        deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        manquantes = [r for r in REGLES_PRISES if r not in deny]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} règle(s) absente(s) de .claude/settings.json")

    def test_la_matrice_contre_les_regles_reelles(self):
        deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        moteur = Moteur(deny)
        self.assertEqual([c for c in commandes_refusees() if not moteur.interdite(c)][:5], [])
        self.assertEqual([c for c in COMMANDES_ADMISES if moteur.interdite(c)], [])


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    else:
        unittest.main()
