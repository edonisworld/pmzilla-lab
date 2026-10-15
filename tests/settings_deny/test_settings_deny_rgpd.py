"""Règles `deny` du change jira-gdpr-alignment (R-58, design D18, tâche 2.3, spec tooling-permission-guards).

La session ne lance jamais : l'outil de conservation tools/flow_retention.py (toute sous-commande), tools/epic_statuses.py, le script de
vérification check_stored_fields.py, ni la sous-commande `cycles` de tools/flux_jira.py (elle lit toujours la base). Elle ne lit pas non
plus Flux-Lab/organisation.yaml (outil Read et lecteurs du terminal). Elle peut lire le code de ces outils, lancer leurs suites de tests,
lire un rapport de Flux-Lab/rapports/, lire Flux-Lab/flux.yaml et lancer `flux_jira.py compute` sur des CSV.

Conception : l'utilisateur n'ajoute les règles à .claude/settings.json qu'à l'étape 15.9. La suite reste donc VERTE avant et après :
 - les tests de correspondance appliquent le moteur de motifs aux règles de REGLES_D18 (le bloc que l'utilisateur copiera), pas au fichier
   de réglages ;
 - le test « les règles sont dans settings.json » est SAUTÉ tant qu'aucune règle n'y est, ÉCHOUE si certaines seulement y sont (il les
   nomme) et passe si toutes y sont ; la matrice des formes est alors rejouée contre les règles RÉELLES (sautée sinon) ;
 - les commandes permises sont aussi vérifiées contre les règles réelles, privées de celles de REGLES_D18 : le résultat est le même avant
   et après l'étape 15.9.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/test_settings_deny_rgpd.py --json     (imprime le bloc à copier dans permissions.deny)
"""
import itertools
import json
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny import motif_en_regex  # noqa: E402
from test_settings_deny_offsite_backup import glob_en_regex  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"

LECTEURS_TERMINAL = ("cat", "head", "tail", "less", "more", "grep", "awk", "sed", "cp")
LANCEURS_REGLES = ("uv run", "python", "python3")
PREFIXES_TOOLS = ("tools/", "./tools/", "~/*tools/", "$HOME/*tools/", "/*tools/", "", "./")
PREFIXES_VERIFICATION = ("openspec/*", "./openspec/*", "~/*openspec/*", "$HOME/*openspec/*", "/*openspec/*", "", "./")


def regles_de_lancement(commande: str, prefixes: tuple) -> list:
    """Règles qui refusent `commande` (script, ou script et sous-commande) sous chaque lanceur et chaque forme de chemin.

    Avec un lanceur : le script précédé d'une barre (tout chemin), nu, ou précédé d'options (`uv run -q X`). Le joker ne se place jamais
    devant « X.py » sans barre ni espace : `python3 tests/…/test_X.py` reste permis. En exécution directe : le chemin au début."""
    regles = []
    for lanceur in LANCEURS_REGLES:
        regles += [f"Bash({lanceur} */{commande}*)", f"Bash({lanceur} {commande}*)", f"Bash({lanceur} * {commande}*)"]
    regles += [f"Bash({prefixe}{commande}*)" for prefixe in prefixes]
    return regles


# Le bloc que l'utilisateur copie dans permissions.deny de .claude/settings.json (étape 15.9) : une chaîne JSON par règle.
REGLES_D18 = (
    regles_de_lancement("flow_retention.py", PREFIXES_TOOLS)
    + regles_de_lancement("epic_statuses.py", PREFIXES_TOOLS)
    + regles_de_lancement("check_stored_fields.py", PREFIXES_VERIFICATION)
    + regles_de_lancement("flux_jira.py cycles", PREFIXES_TOOLS)
    + ["Read(./Flux-Lab/organisation.yaml)", "Read(//**/Flux-Lab/organisation.yaml)", "Read(~/**/Flux-Lab/organisation.yaml)"]
    + [f"Bash({lecteur} *organisation.yaml*)" for lecteur in LECTEURS_TERMINAL]
)

# Formes de lancement à refuser.
LANCEURS = ("uv run", "uv run --isolated", "uv run python", "uv run python3", "uv run --with pyyaml", "uv run -q",
            "python", "python3", "python3 -I", "python3 -W ignore")
CHEMINS_TOOLS = ("tools/{s}", "./tools/{s}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}",
                 "$HOME/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/{s}", "/Users/quelquun/PMZilla-Lab/{s}", "{s}")
CHEMINS_TOOLS_DIRECTS = ("tools/{s}", "./tools/{s}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}",
                         "$HOME/PMZilla-Lab/workspace/tools/{s}", "{s}", "./{s}")
VERIF = "openspec/changes/jira-gdpr-alignment/verification/{s}"
VERIF_ARCHIVE = "openspec/changes/archive/2026-10-20-jira-gdpr-alignment/verification/{s}"
CHEMINS_VERIFICATION = (VERIF, "./" + VERIF, VERIF_ARCHIVE, "/Users/quelquun/PMZilla-Lab/workspace/" + VERIF,
                        "~/PMZilla-Lab/workspace/" + VERIF, "$HOME/PMZilla-Lab/workspace/" + VERIF, "verification/{s}", "../verification/{s}",
                        "{s}")
CHEMINS_VERIFICATION_DIRECTS = (VERIF, "./" + VERIF, VERIF_ARCHIVE, "/Users/quelquun/PMZilla-Lab/workspace/" + VERIF,
                                "~/PMZilla-Lab/workspace/" + VERIF, "$HOME/PMZilla-Lab/workspace/" + VERIF, "{s}", "./{s}")

OPTIONS_RETENTION = ("", " check", " purge", " purge --apply", " check --language en", " purge --apply --language en",
                     " --language en check", " --help")
OPTIONS_STATUTS = ("", " Flux-Lab/exports/a.csv", " a.csv b.csv --history cache.json", " --language en a.csv", " --help")
OPTIONS_VERIFICATION = ("", " --workspace ~/PMZilla-Lab/workspace --data ~/.pmzilla-lab", " --help")
OPTIONS_CYCLES = (" cycles", " cycles --name serie-a", " cycles --name x --scope PROJ", " cycles --source db --name x",
                  " cycles --language en --name x", " cycles --name x --weeks 26")

# (script, chemins avec lanceur, chemins en exécution directe, options)
OUTILS_REFUSES = (
    ("flow_retention.py", CHEMINS_TOOLS, CHEMINS_TOOLS_DIRECTS, OPTIONS_RETENTION),
    ("epic_statuses.py", CHEMINS_TOOLS, CHEMINS_TOOLS_DIRECTS, OPTIONS_STATUTS),
    ("check_stored_fields.py", CHEMINS_VERIFICATION, CHEMINS_VERIFICATION_DIRECTS, OPTIONS_VERIFICATION),
)

DOSSIERS_FLUX = ("Flux-Lab", "./Flux-Lab", "/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab", "~/PMZilla-Lab/workspace/Flux-Lab",
                 "$HOME/PMZilla-Lab/workspace/Flux-Lab")
OPTIONS_LECTEUR = ("", "-n 5 ", "-r ")
CHEMINS_READ = ("Flux-Lab/organisation.yaml", "./Flux-Lab/organisation.yaml", "/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/organisation.yaml",
                "~/PMZilla-Lab/workspace/Flux-Lab/organisation.yaml")

# Commandes permises : aucune règle de REGLES_D18 ne doit les refuser.
COMMANDES_PERMISES = (
    "cat tools/flow_retention.py", "head -40 tools/flow_retention.py", "grep -n purge tools/flow_retention.py",
    "cat tools/flow_retention_messages.py", "sed -n 1,40p tools/epic_statuses.py", "cat tools/epic_statuses.py",
    "cat openspec/changes/jira-gdpr-alignment/verification/check_stored_fields.py",
    "head -30 openspec/changes/jira-gdpr-alignment/verification/check_stored_fields.py",
    "git log --oneline -3 -- tools/flow_retention.py", "ls tests/flow_retention", "ls tests/epic_statuses",
    "bash tests/run_all.sh flow_retention", "bash tests/run_all.sh epic_statuses", "bash tests/run_all.sh --staged",
    "bash tests/run_all.sh settings_deny",
    "uv run --with pyyaml python -W ignore -m unittest discover -s tests/epic_statuses",
    "uv run --with pyyaml python -W ignore -m unittest discover -s tests/epic_statuses -q -f",
    "uv run --with pyyaml python -W ignore -m unittest discover -s tests/flow_retention -q -f",
    "python3 -W ignore -m unittest discover -s tests/flow_retention -q",
    "python3 tests/epic_statuses/test_epic_statuses.py", "python3 tests/flow_retention/test_flow_retention.py",
    "cat Flux-Lab/rapports/statuts-epics-2026-10-13.md", "head -20 ./Flux-Lab/rapports/statuts-epics-2026-10-13.md",
    "grep -n Epic Flux-Lab/rapports/statuts-epics-2026-10-13.md", "cat Flux-Lab/rapports/cycles-serie-a-2026-10-13.md",
    "ls Flux-Lab/rapports", "cat Flux-Lab/flux.yaml", "head Flux-Lab/flux.yaml", "grep -n cycles Flux-Lab/flux.yaml",
    "cat /Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/flux.yaml", "cat ~/PMZilla-Lab/workspace/Flux-Lab/flux.yaml",
    "uv run tools/flux_jira.py compute exports.csv", "uv run tools/flux_jira.py compute exports.csv --name serie-a --source csv",
    "uv run --with numpy tools/flux_jira.py compute exports.csv --name cycles --scope PROJ", "python3 tools/flux_jira.py compute cycles.csv",
    "uv run tools/flux_jira.py statuses exports.csv", "uv run tools/flux_jira.py compare --name serie-a", "cat tools/flux_jira.py",
    "grep -n cycles tools/flux_jira.py", "uv run tools/flow_views.py list",
)
COMMANDES_PERMISES_TERMINAL = tuple(c for c in COMMANDES_PERMISES if not c.startswith("Read:"))
CHEMINS_READ_PERMIS = ("Flux-Lab/flux.yaml", "./Flux-Lab/flux.yaml", "Flux-Lab/rapports/statuts-epics-2026-10-13.md",
                       "./Flux-Lab/rapports/cycles-serie-a-2026-10-13.md", "/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/flux.yaml",
                       "/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/rapports/statuts-epics-2026-10-13.md",
                       "~/PMZilla-Lab/workspace/Flux-Lab/rapports/statuts-epics-2026-10-13.md", "tools/flow_retention.py",
                       "tools/epic_statuses.py", "openspec/changes/jira-gdpr-alignment/verification/check_stored_fields.py")

# Commandes permises que les règles EXISTANTES de settings.json refusent déjà : un défaut des règles d'avant, pas du bloc D18.
# Aucune pour l'instant ; toute entrée est documentée ici avec sa règle.
DEJA_REFUSEES_PAR_LES_REGLES_EXISTANTES: dict = {}


class Moteur:
    """Applique un ensemble de règles `Bash(...)` / `Read(...)` à des commandes et à des chemins."""

    def __init__(self, regles):
        self.motifs = [motif_en_regex(r[len("Bash("):-1]) for r in regles if r.startswith("Bash(")]
        self.lectures = [r[len("Read("):-1] for r in regles if r.startswith("Read(")]

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)

    def lecture_interdite(self, chemin: str) -> bool:
        """Outil Read : « // » = chemin absolu depuis la racine du disque, « ~/ » = depuis le dossier personnel, sinon relatif au dossier."""
        for motif in self.lectures:
            if motif.startswith("//"):
                if chemin.startswith("/") and glob_en_regex(motif[1:]).fullmatch(chemin):
                    return True
            elif motif.startswith("~/"):
                if chemin.startswith("~/") and glob_en_regex(motif).fullmatch(chemin):
                    return True
            elif not chemin.startswith(("/", "~")) and glob_en_regex(motif.removeprefix("./")).fullmatch(chemin.removeprefix("./")):
                return True
        return False


def commandes_refusees():
    """Toutes les formes de lancement et de lecture que la session ne doit pas pouvoir exécuter."""
    for script, chemins, directs, options in OUTILS_REFUSES:
        for lanceur, chemin, option in itertools.product(LANCEURS, chemins, options):
            yield f"{lanceur} {chemin.format(s=script)}{option}"
        for chemin, option in itertools.product(directs, options):
            yield f"{chemin.format(s=script)}{option}"
    for lanceur, chemin, option in itertools.product(LANCEURS, CHEMINS_TOOLS, OPTIONS_CYCLES):
        yield f"{lanceur} {chemin.format(s='flux_jira.py')}{option}"
    for chemin, option in itertools.product(CHEMINS_TOOLS_DIRECTS, OPTIONS_CYCLES):
        yield f"{chemin.format(s='flux_jira.py')}{option}"
    for lecteur, dossier, option in itertools.product(LECTEURS_TERMINAL, DOSSIERS_FLUX, OPTIONS_LECTEUR):
        yield f"{lecteur} {option}{dossier}/organisation.yaml"


class Matrice:
    """Cas communs au bloc REGLES_D18 et aux règles réelles ; `self.moteur` est fourni par la sous-classe."""

    def verifier_formes_refusees(self):
        manquantes = [c for c in commandes_refusees() if not self.moteur.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} formes de lancement ou de lecture non refusées")
        for chemin in CHEMINS_READ:
            self.assertTrue(self.moteur.lecture_interdite(chemin), f"Read({chemin})")

    def verifier_formes_permises(self):
        refusees = [c for c in COMMANDES_PERMISES_TERMINAL if self.moteur.interdite(c)]
        self.assertEqual(refusees, [])
        refusees = [c for c in CHEMINS_READ_PERMIS if self.moteur.lecture_interdite(c)]
        self.assertEqual(refusees, [])


class BlocD18(Matrice, unittest.TestCase):
    """Le moteur de motifs appliqué au bloc à copier : vert avant comme après l'étape 15.9."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_D18)

    def test_le_bloc_n_a_pas_de_doublon_et_n_utilise_que_bash_et_read(self):
        self.assertEqual(len(REGLES_D18), len(set(REGLES_D18)))
        self.assertTrue(all(r.startswith(("Bash(", "Read(")) and r.endswith(")") for r in REGLES_D18))

    def test_chaque_outil_chaque_lanceur_chaque_chemin_chaque_option(self):
        self.verifier_formes_refusees()

    def test_outil_de_conservation_toute_sous_commande(self):
        for lanceur, sous in itertools.product(LANCEURS, ("check", "purge", "purge --apply", "check --language en")):
            commande = f"{lanceur} tools/flow_retention.py {sous}"
            self.assertTrue(self.moteur.interdite(commande), commande)

    def test_cycles_avec_ou_sans_source_et_compute_sur_csv_non_interdit(self):
        for lanceur in LANCEURS:
            for commande in (f"{lanceur} tools/flux_jira.py cycles --name x", f"{lanceur} tools/flux_jira.py cycles --name x --source db",
                             f"{lanceur} tools/flux_jira.py cycles --name x --source csv"):
                self.assertTrue(self.moteur.interdite(commande), commande)
            for commande in (f"{lanceur} tools/flux_jira.py compute exports.csv", f"{lanceur} tools/flux_jira.py compute exports.csv --source csv",
                             f"{lanceur} tools/flux_jira.py compute cycles.csv --name cycles"):
                self.assertFalse(self.moteur.interdite(commande), commande)

    def test_flux_yaml_et_rapports_restent_lisibles(self):
        for lecteur, dossier in itertools.product(LECTEURS_TERMINAL, DOSSIERS_FLUX):
            for fichier in ("flux.yaml", "rapports/statuts-epics-2026-10-13.md"):
                commande = f"{lecteur} {dossier}/{fichier}"
                self.assertFalse(self.moteur.interdite(commande), commande)
        for chemin in CHEMINS_READ_PERMIS:
            self.assertFalse(self.moteur.lecture_interdite(chemin), chemin)

    def test_ce_qui_reste_permis_autour_des_outils(self):
        self.verifier_formes_permises()


class ReglesExistantes(unittest.TestCase):
    """Les commandes permises contre les règles réelles de settings.json privées de celles de REGLES_D18 : même résultat avant et après 15.9.

    Un cas déjà refusé par une règle existante n'est pas un défaut du bloc D18 : il est listé dans DEJA_REFUSEES_PAR_LES_REGLES_EXISTANTES."""

    @classmethod
    def setUpClass(cls):
        deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.moteur = Moteur([r for r in deny if r not in REGLES_D18])

    def test_commandes_permises_non_refusees_par_les_regles_d_avant(self):
        refusees = {c for c in COMMANDES_PERMISES_TERMINAL if self.moteur.interdite(c)}
        self.assertEqual(sorted(refusees - set(DEJA_REFUSEES_PAR_LES_REGLES_EXISTANTES)), [])
        self.assertEqual(sorted(set(DEJA_REFUSEES_PAR_LES_REGLES_EXISTANTES) - refusees), [], "entrée périmée dans le dictionnaire")
        refusees = [c for c in CHEMINS_READ_PERMIS if self.moteur.lecture_interdite(c)]
        self.assertEqual(refusees, [])

    def test_le_fichier_d_organisation_n_est_pas_deja_couvert_par_une_regle_d_avant(self):
        """Garde le sens du bloc : si une règle existante couvrait déjà ces lectures, REGLES_D18 serait redondant."""
        self.assertFalse(self.moteur.lecture_interdite("Flux-Lab/organisation.yaml"))
        self.assertFalse(self.moteur.interdite("cat Flux-Lab/organisation.yaml"))


class DansLeFichierDeReglages(unittest.TestCase):
    """Étape 15.9 : l'utilisateur ajoute les règles. Sauté avant, échoue si l'ajout est partiel, passe si tout y est."""

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.presentes = [r for r in REGLES_D18 if r in cls.deny]
        cls.manquantes = [r for r in REGLES_D18 if r not in cls.deny]

    def test_les_regles_sont_dans_settings_json(self):
        if not self.presentes:
            self.skipTest("étape 15.9 : l'utilisateur n'a pas encore ajouté les règles")
        self.assertEqual(self.manquantes, [], f"{len(self.manquantes)} règle(s) de REGLES_D18 absente(s) de .claude/settings.json")

    def test_la_matrice_des_formes_contre_les_regles_reelles(self):
        if not self.presentes:
            self.skipTest("étape 15.9 : l'utilisateur n'a pas encore ajouté les règles")
        if self.manquantes:
            self.skipTest("règles partielles : voir test_les_regles_sont_dans_settings_json")
        matrice = type("MatriceReelle", (Matrice, unittest.TestCase), {"moteur": Moteur(self.deny)})("verifier_formes_refusees")
        matrice.verifier_formes_refusees()
        matrice.verifier_formes_permises()


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(REGLES_D18, indent=2, ensure_ascii=False))
    else:
        unittest.main()
