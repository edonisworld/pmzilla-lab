"""Règles `deny` des outils de rapport qui lisent la base seule (R-69, change database-only, conception D12, tâches 4.9 et 4.10, étape
utilisateur 13.2, issue #244).

Après le retrait de la voie CSV, `flux_jira.py statuses`, `compute` et `cycles`, `dependencies_jira.py diagnose` et `compute`,
`segment_sample.py` et `history_jira.py check` (avec ou sans clé) lisent tous la base sans option : la session ne les lance plus, ni par
`uv run`, ni par `python`, ni par `python3`, ni en exécution directe. `epic_statuses.py` est déjà couvert par des règles qui commencent
par le lanceur. Complément du 2026-10-19 (bloc REGLES_COMPLEMENT) : `flux_jira.py epics`, qui lit la base et n'avait aucune règle, et
`flow_import.py` et `flow_compare.py`, qui n'avaient qu'une règle par lanceur, reçoivent toutes les formes de lancement. Un `grep` du même texte dans la documentation reste permis, comme `--source db`
cité dans un `grep`, la lecture du code, `flux_jira.py compare` et `config`. Aucune règle qui nomme un de ces outils ou l'option
`--source` ne commence par un joker : chacune commence par le lanceur ou par le chemin du script. Les anciennes règles `Bash(*--source
db*)` (quatre formes) commencent par un joker : l'utilisateur les retire (étape 13.2) et le bloc ci-dessous les remplace.

Même conception que test_settings_deny_epics.py : la suite reste VERTE avant et après l'étape 13.2.
 - le moteur de motifs est appliqué au bloc REGLES_DB_ONLY (celui que l'utilisateur copie), pas au fichier de réglages ;
 - le test « les règles sont dans settings.json » est SAUTÉ tant qu'aucune règle n'y est, ÉCHOUE si certaines seulement y sont (il les
   nomme) ou si une règle à joker initial sur l'option --source y reste, et passe si tout est en place ; la matrice des formes est
   alors rejouée contre les règles RÉELLES.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.

    python3 tests/settings_deny/test_settings_deny_database_only.py --json     (imprime le bloc à copier dans permissions.deny)
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny_rgpd import (CHEMINS_TOOLS, CHEMINS_TOOLS_DIRECTS, LANCEURS, PREFIXES_TOOLS, REGLAGES,  # noqa: E402
                                     Moteur, regles_de_lancement)

# (commande de la règle, options à essayer derrière)
LANCEMENTS = (
    ("flux_jira.py statuses", (" statuses", " statuses --language en", " statuses --source db", " statuses --source=db",
                               " statuses a.csv")),
    ("flux_jira.py compute", (" compute", " compute --name serie-a --weeks 26", " compute --source db --name x",
                              " compute --source=db --history --dormant-from-history --points", " compute a.csv b.csv --name x")),
    ("dependencies_jira.py diagnose", (" diagnose", " diagnose --scope ABC", " diagnose --source db", " diagnose a.csv")),
    ("dependencies_jira.py compute", (" compute", " compute --by project --name x", " compute --source db --name x",
                                      " compute a.csv --by site")),
    ("segment_sample.py", ("", " --segment revue_verification", " --history", " --starts", " a.csv --today 2026-10-18")),
    ("history_jira.py check", (" check", " check --key PROJ-1", " check --dormants export.csv", " check --language en")),
)
REGLES_DB_ONLY = [r for commande, _ in LANCEMENTS for r in regles_de_lancement(commande, PREFIXES_TOOLS)]

# Tâche 14.2 (conception D13) : `check-teams` lit désormais la base (la vue des équipes vues) et reste lancé par l'auteur seul. Règles
# ancrées sur le nom de l'outil, même famille que flow_import ; `migrate-teams` et `review-teams` ne lisent aucune base et ne sont pas visés.
# Bloc à part : les tests contre settings.json restent verts avant l'étape 17.1 (sautés tant qu'aucune de ces règles n'y est).
LANCEMENTS_CHECK_TEAMS = (
    ("export_jira_api.py check-teams", (" check-teams", " check-teams --language en", " check-teams --language fr")),
)
REGLES_CHECK_TEAMS = [r for commande, _ in LANCEMENTS_CHECK_TEAMS for r in regles_de_lancement(commande, PREFIXES_TOOLS)]
COMMANDES_PERMISES_CHECK_TEAMS = (
    'grep -rn "uv run tools/export_jira_api.py check-teams" docs/', "grep -n 'python3 tools/export_jira_api.py check-teams' docs/pmzilla/installation.md",
    'git grep -n "export_jira_api.py check-teams" -- docs/', "grep -n check-teams tools/export_jira_api_equipes.py",
    "uv run tools/export_jira_api.py migrate-teams --help", "uv run tools/export_jira_api.py review-teams --add 50",
    "bash tests/run_all.sh export_jira_api",
)
# Permises par le bloc check-teams, mais refusées dans le vrai fichier par les règles du change team-mapping (groupe 2, tâches 2.1 et 2.2 :
# `Bash(uv run *export_jira_api.py migrate-teams*)` et `review-teams`, le catalogue des équipes n'est jamais lu par la session).
COMMANDES_REFUSEES_PAR_TEAM_MAPPING = (
    "uv run tools/export_jira_api.py migrate-teams --help", "uv run tools/export_jira_api.py review-teams --add 50",
)

# Complément du 2026-10-19 (inventaire avant l'étape 13.2) : `flux_jira.py epics` lit la base et n'avait aucune règle ; `flow_import.py` et
# `flow_compare.py` n'avaient que trois règles, une par lanceur, sans les chemins directs. Bloc à part, même raison que check-teams : les
# tests contre settings.json sont sautés tant que ces règles n'y sont pas toutes.
LANCEMENTS_COMPLEMENT = (
    ("flux_jira.py epics", (" epics", " epics --name pilote", " epics --language en")),
    ("flow_import.py", ("", " a.csv b.csv --mark-absent", " --rebuild --dry-run", " a.csv --history")),
    ("flow_compare.py", (" reports a.md b.md", " data a.csv", " data a.csv --history")),
)
REGLES_COMPLEMENT = [r for commande, _ in LANCEMENTS_COMPLEMENT for r in regles_de_lancement(commande, PREFIXES_TOOLS)]
COMMANDES_PERMISES_COMPLEMENT = (
    'grep -rn "uv run tools/flux_jira.py epics" docs/', 'git grep -n "flow_import.py" -- docs/',
    "grep -n reports tools/flow_compare.py", "cat tools/flow_import.py", "head -40 tools/flow_compare.py",
    "uv run tools/flux_jira.py compare --name serie-a", "uv run tools/flux_jira.py config migrate --dry-run",
    "uv run tools/flow_views.py list", "bash tests/run_all.sh flow_import", "bash tests/run_all.sh flow_compare",
)


def regles_attendues():
    """Le bloc imprimé par --json : REGLES_DB_ONLY, REGLES_CHECK_TEAMS puis REGLES_COMPLEMENT (nom de convention du garde partagé des
    listes --json)."""
    return REGLES_DB_ONLY + REGLES_CHECK_TEAMS + REGLES_COMPLEMENT

# Règles à joker initial à retirer : elles attrapaient l'option --source n'importe où sur la ligne, citations comprises.
REGLES_A_RETIRER = ("Bash(*--source db*)", "Bash(*--source=db*)", "Bash(*--source 'db'*)", 'Bash(*--source "db"*)')

# Commandes permises : aucune règle de REGLES_DB_ONLY ne doit les refuser.
COMMANDES_PERMISES = (
    'grep -rn "uv run tools/flux_jira.py compute" docs/', 'grep -n "uv run tools/flux_jira.py statuses" docs/pmzilla/installation.md',
    'grep -rn "uv run tools/dependencies_jira.py diagnose" docs/', "grep -rn 'python3 tools/segment_sample.py' docs/",
    'grep -rn "uv run tools/history_jira.py check" docs/ .claude/commands/', 'git grep -n "flux_jira.py compute" -- docs/',
    'grep -rn -- "--source db" docs/', "grep -rn '--source db' docs/ openspec/", 'grep -n "--source=db" docs/pmzilla/installation.md',
    'git grep -n -- "--source db"', "cat tools/flux_jira.py", "head -40 tools/dependencies_jira.py", "cat tools/segment_sample.py",
    "grep -n compute tools/flux_jira.py", "git log --oneline -3 -- tools/flux_jira.py", "ls tools",
    "uv run tools/flux_jira.py compare --name serie-a", "python3 tools/flux_jira.py compare --name serie-a --before 2026-09-01",
    "uv run tools/flux_jira.py config migrate --dry-run", "python3 tools/flux_jira.py config migrate",
    "uv run tools/flow_views.py list", "uv run tools/history_jira.py --help", "uv run tools/dependencies_jira.py --help",
    "cat Flux-Lab/rapports/flux-serie-a-2026-10-18.md", "ls Flux-Lab/rapports",
    "bash tests/run_all.sh flux_jira", "bash tests/run_all.sh settings_deny", "bash tests/run_all.sh --staged",
    "uv run --with numpy --with pyyaml python -W ignore -m unittest discover -s tests/flux_jira -q -f",
    "python3 tests/flux_jira/test_flux_jira.py", "python3 tests/dependencies_jira/test_dependencies_jira.py",
)


def commandes_refusees():
    for (commande, options), lanceur, chemin in itertools.product(LANCEMENTS, LANCEURS, CHEMINS_TOOLS):
        script, _, sous = commande.partition(" ")
        for option in options:
            yield f"{lanceur} {chemin.format(s=script)}{option}"
    for (commande, options), chemin in itertools.product(LANCEMENTS, CHEMINS_TOOLS_DIRECTS):
        script = commande.partition(" ")[0]
        for option in options:
            yield f"{chemin.format(s=script)}{option}"
    for lanceur in ("uv run", "python", "python3"):          # les trois façons de lancer nommées par la tâche 4.10
        for commande, options in LANCEMENTS:
            script = commande.partition(" ")[0]
            yield f"{lanceur} tools/{script}{options[0]}"


class Matrice:
    def verifier_formes_refusees(self):
        manquantes = [c for c in commandes_refusees() if not self.moteur.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} formes de lancement non refusées")

    def verifier_formes_permises(self):
        refusees = [c for c in COMMANDES_PERMISES if self.moteur.interdite(c)]
        self.assertEqual(refusees, [])


class BlocDatabaseOnly(Matrice, unittest.TestCase):
    """Le moteur de motifs appliqué au bloc à copier : vert avant comme après l'étape 13.2."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_DB_ONLY)

    def test_aucune_regle_ne_commence_par_un_joker(self):
        for regle in REGLES_DB_ONLY:
            self.assertTrue(regle.startswith("Bash(") and regle.endswith(")"), regle)
            self.assertNotEqual(regle[len("Bash("):][:1], "*", regle)

    def test_le_bloc_n_a_pas_de_doublon(self):
        self.assertEqual(len(REGLES_DB_ONLY), len(set(REGLES_DB_ONLY)))

    def test_les_anciennes_regles_a_joker_ne_sont_pas_dans_le_bloc(self):
        self.assertEqual([r for r in REGLES_A_RETIRER if r in REGLES_DB_ONLY], [])

    def test_uv_run_python_et_python3_refuses_pour_chaque_outil(self):
        for commande, options in LANCEMENTS:
            script = commande.partition(" ")[0]
            for lanceur in ("uv run", "python", "python3"):
                texte = f"{lanceur} tools/{script}{options[0]}"
                self.assertTrue(self.moteur.interdite(texte), texte)

    def test_chaque_outil_chaque_lanceur_chaque_chemin_chaque_option(self):
        self.verifier_formes_refusees()

    def test_l_ancienne_option_source_sur_un_vrai_lancement_est_refusee_par_une_regle_ancree(self):
        for lanceur in ("uv run", "python", "python3", "uv run --with numpy"):
            for texte in (f"{lanceur} tools/flux_jira.py compute --source db", f"{lanceur} tools/flux_jira.py statuses --source=db a.csv",
                          f"{lanceur} tools/dependencies_jira.py compute --source db --name x"):
                self.assertTrue(self.moteur.interdite(texte), texte)

    def test_une_citation_de_la_commande_ou_de_l_option_reste_permise(self):
        for texte in COMMANDES_PERMISES[:10]:
            self.assertFalse(self.moteur.interdite(texte), texte)

    def test_compare_et_config_restent_permis(self):
        for texte in ("uv run tools/flux_jira.py compare --name x", "python3 tools/flux_jira.py config migrate --dry-run",
                      "python tools/flux_jira.py compare"):
            self.assertFalse(self.moteur.interdite(texte), texte)

    def test_ce_qui_reste_permis_autour_des_outils(self):
        self.verifier_formes_permises()


class ReglesExistantes(unittest.TestCase):
    """Les anciennes règles à joker initial sur --source ne sont plus nécessaires et c'est leur seul défaut : une fois le bloc posé,
    les retirer ne laisse aucun lancement réel sans règle (la matrice est rejouée sur le fichier réel sans elles)."""

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]

    def test_le_bloc_seul_couvre_ce_que_les_anciennes_regles_a_joker_couvraient_sur_un_lancement_reel(self):
        moteur = Moteur(REGLES_DB_ONLY + [r for r in self.deny if r not in REGLES_A_RETIRER])
        for lanceur in ("uv run", "python", "python3"):
            for outil in ("flux_jira.py compute", "dependencies_jira.py compute", "dependencies_jira.py diagnose", "flux_jira.py statuses"):
                for forme in (f"{lanceur} tools/{outil} --source db", f"{lanceur} tools/{outil} --source=db --name x"):
                    self.assertTrue(moteur.interdite(forme), forme)


    def test_le_fichier_simule_apres_l_etape_donne_les_memes_resultats_que_le_bloc_seul(self):
        """Simulation de l'étape 13.2 : règles réelles sans les quatre à joker initial, plus le bloc. Aucune règle existante ne refuse une
        commande permise (citation en grep comprise), et chaque forme de lancement est refusée."""
        matrice = type("MatriceSimulee", (Matrice, unittest.TestCase),
                       {"moteur": Moteur(REGLES_DB_ONLY + [r for r in self.deny if r not in REGLES_A_RETIRER])})("verifier_formes_refusees")
        matrice.verifier_formes_refusees()
        matrice.verifier_formes_permises()


class DansLeFichierDeReglages(unittest.TestCase):
    """Étape 13.2 : l'utilisateur ajoute les règles et retire les quatre règles à joker initial. Sauté avant, échoue si l'ajout est
    partiel ou si une règle à retirer reste après l'ajout, passe si tout est en place."""

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.presentes = [r for r in REGLES_DB_ONLY if r in cls.deny]
        cls.manquantes = [r for r in REGLES_DB_ONLY if r not in cls.deny]
        cls.a_retirer = [r for r in REGLES_A_RETIRER if r in cls.deny]

    def test_les_regles_sont_dans_settings_json(self):
        if not self.presentes:
            self.fail("étape 13.2 : l'utilisateur n'a pas encore ajouté les règles des outils de rapport sur la base")
        self.assertEqual(self.manquantes, [], f"{len(self.manquantes)} règle(s) de REGLES_DB_ONLY absente(s) de .claude/settings.json")

    def test_les_regles_a_joker_initial_sur_source_sont_retirees(self):
        if not self.presentes:
            self.fail("étape 13.2 : l'utilisateur n'a pas encore ajouté les règles des outils de rapport sur la base")
        self.assertEqual(self.a_retirer, [], "règle(s) à joker initial à retirer de .claude/settings.json (conception D12)")

    def test_aucune_regle_a_joker_initial_ne_nomme_un_de_ces_outils_ni_source(self):
        if not self.presentes:
            self.fail("étape 13.2 : l'utilisateur n'a pas encore ajouté les règles des outils de rapport sur la base")
        noms = ("flux_jira", "dependencies_jira", "segment_sample", "history_jira", "flow_import", "flow_compare", "epic_statuses",
                "flow_retention", "flow_monthly", "--source")
        fautives = [r for r in self.deny if r.startswith("Bash(*") and any(n in r for n in noms)]
        self.assertEqual(fautives, [])

    def test_la_matrice_des_formes_contre_les_regles_reelles(self):
        if not self.presentes:
            self.fail("étape 13.2 : l'utilisateur n'a pas encore ajouté les règles des outils de rapport sur la base")
        if self.manquantes:
            self.skipTest("règles partielles : voir test_les_regles_sont_dans_settings_json")
        matrice = type("MatriceReelle", (Matrice, unittest.TestCase), {"moteur": Moteur(self.deny)})("verifier_formes_refusees")
        matrice.verifier_formes_refusees()
        matrice.verifier_formes_permises()


def lancements_check_teams_refuses():
    for (commande, options), lanceur, chemin in itertools.product(LANCEMENTS_CHECK_TEAMS, LANCEURS, CHEMINS_TOOLS):
        script = commande.partition(" ")[0]
        for option in options:
            yield f"{lanceur} {chemin.format(s=script)}{option}"
    for (commande, options), chemin in itertools.product(LANCEMENTS_CHECK_TEAMS, CHEMINS_TOOLS_DIRECTS):
        script = commande.partition(" ")[0]
        for option in options:
            yield f"{chemin.format(s=script)}{option}"
    for lanceur in ("uv run", "python", "python3"):
        yield f"{lanceur} tools/export_jira_api.py check-teams"


class BlocCheckTeams(unittest.TestCase):
    """Tâche 14.2 : le bloc de règles de `check-teams`, appliqué par le moteur de motifs ; vert avant comme après l'étape 17.1."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_CHECK_TEAMS)

    def test_aucune_regle_ne_commence_par_un_joker_et_pas_de_doublon(self):
        for regle in REGLES_CHECK_TEAMS:
            self.assertTrue(regle.startswith("Bash(") and regle.endswith(")"), regle)
            self.assertNotEqual(regle[len("Bash("):][:1], "*", regle)
        self.assertEqual(len(REGLES_CHECK_TEAMS), len(set(REGLES_CHECK_TEAMS)))
        self.assertFalse(set(REGLES_CHECK_TEAMS) & set(REGLES_DB_ONLY))

    def test_le_bloc_imprime_n_a_ni_regle_vide_ni_regle_write_ou_notebookedit(self):
        """Garde R-84 sur tout le bloc imprimé par --json : une règle Edit couvre l'écriture, Write et NotebookEdit seraient ignorées."""
        bloc = regles_attendues()
        self.assertTrue(bloc)
        for regle in bloc:
            self.assertTrue(regle[len("Bash("):-1].strip(), regle)
            self.assertFalse(regle.startswith(("Write(", "NotebookEdit(")), regle)
        self.assertEqual(len(bloc), len(set(bloc)))

    def test_un_vrai_lancement_est_refuse_sous_chaque_lanceur_et_chemin(self):
        non_refusees = [c for c in lancements_check_teams_refuses() if not self.moteur.interdite(c)]
        self.assertEqual(non_refusees[:5], [], f"{len(non_refusees)} formes non refusées")

    def test_uv_run_python_et_python3_sont_refuses(self):
        for lanceur in ("uv run", "python", "python3"):
            self.assertTrue(self.moteur.interdite(f"{lanceur} tools/export_jira_api.py check-teams"), lanceur)

    def test_une_citation_ou_une_autre_sous_commande_reste_permise(self):
        refusees = [c for c in COMMANDES_PERMISES_CHECK_TEAMS if self.moteur.interdite(c)]
        self.assertEqual(refusees, [])


class CheckTeamsDansLeFichierDeReglages(unittest.TestCase):
    """Étape 17.1 : l'utilisateur ajoute les règles. Sauté avant, échoue si l'ajout est partiel, passe si tout est en place."""

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.presentes = [r for r in REGLES_CHECK_TEAMS if r in cls.deny]
        cls.manquantes = [r for r in REGLES_CHECK_TEAMS if r not in cls.deny]

    def test_les_regles_sont_dans_settings_json(self):
        # Étape 17.1 faite : le bloc est entièrement posé, une règle manquante est désormais un échec.
        if self.manquantes:
            self.fail(f"étape 17.1 : {len(self.manquantes)} règle(s) de REGLES_CHECK_TEAMS pas encore dans .claude/settings.json")
        self.assertEqual(self.manquantes, [])

    def test_la_matrice_contre_les_regles_reelles(self):
        if not self.presentes or self.manquantes:
            self.fail("étape 17.1 : règles absentes ou partielles")
        moteur = Moteur(self.deny)
        self.assertEqual([c for c in lancements_check_teams_refuses() if not moteur.interdite(c)][:5], [])
        self.assertEqual([c for c in COMMANDES_PERMISES_CHECK_TEAMS
                          if c not in COMMANDES_REFUSEES_PAR_TEAM_MAPPING and moteur.interdite(c)], [])
        # Les règles de team-mapping restent en place : ces deux commandes sont refusées par le vrai fichier.
        self.assertEqual([c for c in COMMANDES_REFUSEES_PAR_TEAM_MAPPING if not moteur.interdite(c)], [])


def lancements_complement_refuses():
    for (commande, options), lanceur, chemin in itertools.product(LANCEMENTS_COMPLEMENT, LANCEURS, CHEMINS_TOOLS):
        script = commande.partition(" ")[0]
        for option in options:
            yield f"{lanceur} {chemin.format(s=script)}{option}"
    for (commande, options), chemin in itertools.product(LANCEMENTS_COMPLEMENT, CHEMINS_TOOLS_DIRECTS):
        script = commande.partition(" ")[0]
        for option in options:
            yield f"{chemin.format(s=script)}{option}"
    for lanceur in ("uv run", "python", "python3"):
        for commande, options in LANCEMENTS_COMPLEMENT:
            yield f"{lanceur} tools/{commande.partition(' ')[0]}{options[0]}"


class BlocComplement(unittest.TestCase):
    """Complément du 2026-10-19 : epics, flow_import et flow_compare, appliqués par le moteur de motifs ; vert avant comme après."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_COMPLEMENT)

    def test_aucune_regle_ne_commence_par_un_joker_et_pas_de_doublon(self):
        for regle in REGLES_COMPLEMENT:
            self.assertTrue(regle.startswith("Bash(") and regle.endswith(")"), regle)
            self.assertNotEqual(regle[len("Bash("):][:1], "*", regle)
        self.assertEqual(len(REGLES_COMPLEMENT), len(set(REGLES_COMPLEMENT)))
        self.assertFalse(set(REGLES_COMPLEMENT) & (set(REGLES_DB_ONLY) | set(REGLES_CHECK_TEAMS)))

    def test_seize_formes_par_commande(self):
        for commande, _ in LANCEMENTS_COMPLEMENT:
            self.assertEqual(len(regles_de_lancement(commande, PREFIXES_TOOLS)), 16, commande)

    def test_un_vrai_lancement_est_refuse_sous_chaque_lanceur_et_chemin(self):
        non_refusees = [c for c in lancements_complement_refuses() if not self.moteur.interdite(c)]
        self.assertEqual(non_refusees[:5], [], f"{len(non_refusees)} formes non refusées")

    def test_une_citation_ou_une_sous_commande_permise_reste_permise(self):
        refusees = [c for c in COMMANDES_PERMISES_COMPLEMENT if self.moteur.interdite(c)]
        self.assertEqual(refusees, [])


class ComplementDansLeFichierDeReglages(unittest.TestCase):
    """Étape 13.2 (geste du 2026-10-19) : complément posé ; échoue s'il n'est pas entièrement dans le fichier, rejoué contre les règles réelles."""

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.manquantes = [r for r in REGLES_COMPLEMENT if r not in cls.deny]

    def test_les_regles_sont_dans_settings_json(self):
        if self.manquantes:
            self.fail(f"étape 13.2 : {len(self.manquantes)} règle(s) de REGLES_COMPLEMENT pas encore dans .claude/settings.json")
        self.assertEqual(self.manquantes, [])

    def test_la_matrice_contre_les_regles_reelles(self):
        if self.manquantes:
            self.fail("étape 13.2 : règles absentes ou partielles")
        moteur = Moteur(self.deny)
        self.assertEqual([c for c in lancements_complement_refuses() if not moteur.interdite(c)][:5], [])
        self.assertEqual([c for c in COMMANDES_PERMISES_COMPLEMENT if moteur.interdite(c)], [])


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    else:
        unittest.main()
