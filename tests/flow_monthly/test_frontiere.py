"""
Tests de tools/flow_monthly.py : frontière de lecture, confidentialité de la sortie et du résumé, langue, refus dans une session Claude
Code, absence de module de base de données (change monthly-flow-orchestrator, R-48). Faux outils, réglages inventés.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/flow_monthly -q -f
"""
import ast
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_flow_monthly import Decor, MARQUES, REGLAGES, TOOLS, aujourdhui, hier  # noqa: E402
import flow_monthly as fm                                             # noqa: E402
import flow_monthly_messages as msgs                                  # noqa: E402
from messages import check_catalogs                                   # noqa: E402


class Enregistreur:
    """Enregistre les chemins que le processus ouvre, liste ou inspecte sous la racine du décor (crochet d'audit et os.stat/lstat)."""

    def __init__(self, racine: Path):
        self.racine = str(racine)
        self.actif = False
        self.chemins: list[str] = []

    def noter(self, chemin) -> None:
        if self.actif and isinstance(chemin, (str, bytes, os.PathLike)):
            texte = os.fsdecode(chemin)
            if texte.startswith(self.racine):
                self.chemins.append(texte)

    def hook(self, evenement, args):
        if self.actif and evenement in ("open", "os.listdir", "os.scandir", "glob.glob", "os.walk", "os.rename", "os.remove",
                                        "os.mkdir", "os.chmod", "shutil.copyfile") and args:
            self.noter(args[0])


ENREGISTREUR: Enregistreur | None = None


def _crochet(evenement, args):
    if ENREGISTREUR is not None:
        ENREGISTREUR.hook(evenement, args)


sys.addaudithook(_crochet)


class Frontiere(Decor):
    def enregistrer(self, *argv: str, env=None):
        global ENREGISTREUR
        e = Enregistreur(self.racine)
        vrai_stat, vrai_lstat = os.stat, os.lstat

        def stat(chemin, *a, **k):
            e.noter(chemin)
            return vrai_stat(chemin, *a, **k)

        def lstat(chemin, *a, **k):
            e.noter(chemin)
            return vrai_lstat(chemin, *a, **k)
        ENREGISTREUR = e
        try:
            with mock.patch.object(os, "stat", stat), mock.patch.object(os, "lstat", lstat):
                e.actif = True
                try:
                    resultat = self.lancer(*argv, env=env)
                finally:
                    e.actif = False
        finally:
            ENREGISTREUR = None
        return resultat, e.chemins

    def autorises(self, chemins: list[str]) -> list[str]:
        reglages = str(self.flux / "flux.yaml")
        rapports = str(self.rapports)
        return [c for c in chemins if c != reglages and c != rapports and not c.startswith(rapports + os.sep)]

    def test_run_complet_seuls_les_reglages_et_les_rapports_sont_touches(self):
        r, chemins = self.enregistrer("--language", "en")
        self.assertEqual(r.code, 0, r.sortie)
        self.assertTrue(chemins)
        self.assertEqual(self.autorises(chemins), [])
        self.assertTrue(any(c.endswith("flux.yaml") for c in chemins))
        self.assertTrue(any(c.startswith(str(self.rapports)) for c in chemins))

    def test_arret_au_premier_ecart_meme_frontiere(self):
        self.codes(history_jira=1)
        r, chemins = self.enregistrer("--language", "en")
        self.assertEqual(r.code, 1)
        self.assertEqual(self.autorises(chemins), [])

    def test_dry_run_meme_frontiere(self):
        r, chemins = self.enregistrer("--language", "en", "--dry-run")
        self.assertEqual(r.code, 0)
        self.assertEqual(self.autorises(chemins), [])

    def test_refus_dans_une_session_claude_code_ne_lit_rien(self):
        env = {**self.env, "CLAUDECODE": "1"}
        r, chemins = self.enregistrer("--language", "en", env=env)
        self.assertEqual(r.code, 3, r.sortie)
        self.assertIn("Refused inside a Claude Code session: run it in the Terminal", r.sortie)
        self.assertEqual(chemins, [])
        self.assertEqual(self.appels(), [])

    def test_refus_en_francais_et_aucune_option_de_contournement(self):
        env = {**self.env, "CLAUDECODE": "1"}
        for argv in ([], ["--force"], ["--dry-run"], ["--from", "dashboard"]):
            r = self.lancer(*argv, env=env)
            self.assertEqual(r.code, 3, (argv, r.sortie))
            self.assertIn("Lancement refusé dans une session Claude Code : lancez-le dans le Terminal", r.sortie)
        self.assertEqual(self.appels(), [])

    def test_aucune_connexion_a_la_base_ni_au_trousseau(self):
        arbre = ast.parse((TOOLS / "flow_monthly.py").read_text(encoding="utf-8"))
        importes = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                importes |= {a.name.split(".")[0] for a in noeud.names}
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                importes.add(noeud.module.split(".")[0])
        interdits = {"db", "flow_store", "psycopg", "flux_jira", "flow_import", "flow_compare", "flow_views", "history_jira",
                     "history_common", "export_jira_api", "dependencies_jira", "keyring", "requests", "httpx"}
        self.assertEqual(importes & interdits, set())
        self.assertTrue(importes <= set(sys.stdlib_module_names) | {"yaml", "yaml_strict", "messages", "flow_monthly_messages"}, importes)
        source = (TOOLS / "flow_monthly.py").read_text(encoding="utf-8")
        self.assertNotIn("find-generic-password", source)
        self.assertNotIn("pmzilla-jira", source)


class Confidentialite(Decor):
    def sans_marque(self, texte: str, contexte: str) -> None:
        for marque in MARQUES:
            self.assertNotIn(marque, texte, f"{contexte} : « {marque} » dans la sortie ou le résumé")

    def test_run_silencieux(self):
        r = self.lancer("--language", "en")
        self.assertEqual(r.code, 0, r.sortie)
        self.sans_marque(self.toute_la_sortie_et_le_resume(r), "run silencieux")

    def test_run_silencieux_en_francais(self):
        r = self.lancer()
        self.sans_marque(self.toute_la_sortie_et_le_resume(r), "run en français")

    def test_dry_run(self):
        r = self.lancer("--language", "en", "--dry-run")
        self.sans_marque(r.sortie, "dry run")

    def test_echec_d_une_etape(self):
        for outil in ("export_jira_api", "flow_import", "flux_jira", "dependencies_jira", "flow_board"):
            self.setUp()
            self.codes_de({outil: 1})
            r = self.lancer("--language", "en")
            self.assertEqual(r.code, 1, (outil, r.sortie))
            self.sans_marque(self.toute_la_sortie_et_le_resume(r), f"échec de {outil}")

    def test_echec_de_l_historique(self):
        self.codes(history_jira=3)
        r = self.lancer("--language", "en")
        self.sans_marque(self.toute_la_sortie_et_le_resume(r), "échec de l'historique")

    def test_refus_prerequis_et_mois_deja_fait(self):
        self.ecrire_reglages(REGLAGES.replace("dependencies: both", "dependencies: partout"))
        self.sans_marque(self.lancer("--language", "en").sortie, "valeur invalide")
        self.ecrire_reglages(REGLAGES.replace("name: serieunzz", "name: serieunzz-db"))
        self.sans_marque(self.lancer("--language", "en").sortie, "suffixe réservé")
        self.ecrire_reglages(REGLAGES.replace("name: seriedeuxzz", "name: serieunzz"))
        self.sans_marque(self.lancer("--language", "en").sortie, "nom en double")
        self.ecrire_reglages(REGLAGES)
        self.resume_ecrit(aujourdhui(), "complete")
        self.sans_marque(self.lancer("--language", "en").sortie, "mois déjà fait")

    def test_refus_claude_code_et_usage(self):
        self.sans_marque(self.lancer("--language", "en", env={**self.env, "CLAUDECODE": "1"}).sortie, "Claude Code")
        self.sans_marque(self.lancer("--from", "inconnue").sortie, "étape inconnue")

    def test_la_sortie_d_aide_ne_nomme_aucune_valeur(self):
        r = self.lancer("--help")
        self.assertEqual(r.code, 0)
        self.assertIn("usage", r.sortie.lower())
        self.sans_marque(r.sortie, "aide")

    def test_resume_sans_nom_ni_sortie_d_outil(self):
        self.lancer("--language", "en", "--verbose")
        texte = self.resume()
        self.sans_marque(texte, "résumé")
        self.assertNotIn("SORTIE-OUTIL", texte)
        self.assertNotIn("api-", texte)                                   # aucun nom de fichier du dossier des exports


class Langue(Decor):
    def test_catalogues_coherents(self):
        self.assertEqual(check_catalogs(msgs.CATALOGS), [])

    def test_phrases_cles_francaises_d_un_run_complet(self):
        r = self.lancer()
        for phrase in ("Étape 1/9 : export", "Étape 4/9 : flow (série 1)", "Étape export réussie (", "Suivi mensuel terminé : 9 étapes sur 9, 0 sautées"):
            self.assertIn(phrase, r.sortie)
        self.assertNotIn("Step ", r.sortie)
        self.assertNotIn("Monthly run", r.sortie)

    def test_phrases_cles_francaises_d_un_arret(self):
        self.codes(flow_import=1)
        r = self.lancer()
        self.assertIn("Arrêt à l'étape import : code de sortie 1", r.sortie)
        self.assertEqual(r.sortie.strip().splitlines()[-1], "Pour reprendre : uv run tools/flow_monthly.py --from import")
        self.assertNotIn("Stopped", r.sortie)
        self.assertNotIn("Écart entre la base et le CSV", r.sortie)             # la phrase de l'écart de parité n'existe plus

    def test_prerequis_en_francais(self):
        self.ecrire_reglages("jira_site: x\n")
        r = self.lancer()
        self.assertEqual(r.code, 3)
        self.assertIn("Prérequis manquant : ", r.sortie)

    def test_langue_anglaise_aucun_mot_francais_dans_les_lignes_de_l_orchestrateur(self):
        r = self.lancer("--language", "en")
        for ligne in r.sortie.splitlines():
            self.assertNotRegex(ligne, r"Étape|Arrêt|Suivi|Pour reprendre|Lancement|essai|Prérequis", ligne)

    def test_chaque_appel_d_outil_porte_la_langue_choisie(self):
        for langue in ("en", "fr"):
            self.setUp()
            self.lancer("--language", langue)
            for a in self.appels():
                if a["outil"] == "flow_board":
                    self.assertEqual(a["args"][a["args"].index("--language") + 1], langue)
                else:
                    self.assertEqual(a["args"][a["args"].index("--language") + 1], langue, a)

    def test_langue_inconnue(self):
        r = self.lancer("--language", "de")
        self.assertEqual(r.code, 2)
        self.assertEqual(self.appels(), [])


class AucunCheminDeFichier(Decor):
    """Décision D8 : l'orchestrateur ne construit plus aucun nom d'export ni de rapport ; les outils passent par la base."""

    def test_aucune_fonction_de_chemin(self):
        for nom in ("chemin_export", "chemin_rapport", "CODE_ENTREE_MANQUANTE"):
            self.assertFalse(hasattr(fm, nom), nom)

    def test_aucune_etape_de_comparaison(self):
        self.assertEqual(fm.ETAPES, ("export", "import", "history", "flow", "dependencies", "dashboard", "retention"))


class AideEnProcessusReel(unittest.TestCase):
    def test_help_sort_avec_0_meme_dans_une_session_claude_code(self):
        env = {**os.environ, "CLAUDECODE": "1"}
        r = subprocess.run([sys.executable, "-B", str(TOOLS / "flow_monthly.py"), "--help"], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("usage", r.stdout.lower())
        for option in ("--dry-run", "--from", "--date", "--force", "--verbose", "--language", "--open"):
            self.assertIn(option, r.stdout)

    def test_lancement_reel_dans_une_session_claude_code_est_refuse(self):
        env = {**os.environ, "CLAUDECODE": "1"}
        r = subprocess.run([sys.executable, "-B", str(TOOLS / "flow_monthly.py")], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("Lancement refusé dans une session Claude Code", r.stdout)


if __name__ == "__main__":
    unittest.main()
