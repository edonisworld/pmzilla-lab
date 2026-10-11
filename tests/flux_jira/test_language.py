"""Langue de flux_jira.py : catalogue de messages, option --language, instantané anglais (lot 3, étape 2).

    uv run --with pyyaml --with numpy python -m unittest discover -s tests/flux_jira -v

- le catalogue français et le catalogue anglais ont les mêmes clés et les mêmes champs ;
- chaque clé est utilisée par le script, et chaque clé utilisée existe ;
- sans option, la sortie est la sortie française (rapport de référence inchangé) ; `--language fr` donne la même chose ;
- `--language en` sur les mêmes données inventées que les autres tests donne l'instantané reference_en.md
  (le régénérer après un changement voulu : PMZILLA_UPDATE_REFERENCE=1) ;
- les rapports JSON ne changent pas avec la langue, le nom des fichiers non plus ;
- l'ancien `--langue` est refusé, avec le nom actuel.
Le scénario (scenario_language.py) tourne une fois en français et une fois en anglais, dans des dossiers temporaires :
aucune donnée réelle, aucun appel à Jira.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
sys.path.insert(0, str(ICI.parent.parent / "tools"))
import scenario_language as sc  # noqa: E402
import test_flux_jira as fx  # noqa: E402
from flux_jira_messages import CATALOGS  # noqa: E402
from messages import check_catalogs  # noqa: E402

REFERENCE = ICI / "reference_en.md"
SOURCE = (ICI.parent.parent / "tools" / "flux_jira.py").read_text(encoding="utf-8")
SORTIES: dict = {}


def setUpModule():
    SORTIES["fr"] = sc.jouer(None)
    SORTIES["en"] = sc.jouer("en")


def decouper(texte: str) -> tuple[str, dict[str, str]]:
    """Sortie d'une étape : (console, {fichier écrit: contenu})."""
    principal, *fichiers = texte.split("\n--- file ")
    return principal, {bloc.split(" ---\n", 1)[0]: bloc.split(" ---\n", 1)[1] for bloc in fichiers}


def instantane(sorties: dict) -> str:
    """Console de chaque étape et noms des fichiers écrits ; le contenu des fichiers est dans la console (Markdown) ou
    vérifié à part (JSON)."""
    morceaux = []
    for nom, texte in sorties.items():
        principal, fichiers = decouper(texte)
        morceaux.append(f"===== {nom} =====\n{principal.rstrip(chr(10))}\n"
                        + "".join(f"written: {chemin}\n" for chemin in fichiers))
    return "\n".join(morceaux)


class Catalogues(unittest.TestCase):
    def test_memes_cles_et_memes_champs(self):
        self.assertEqual(check_catalogs(CATALOGS), [])

    def test_chaque_cle_utilisee_existe(self):
        utilisees = set(re.findall(r'\btr\("([a-z0-9_]+)"', SOURCE))
        self.assertEqual(sorted(utilisees - set(CATALOGS["fr"])), [])

    def test_chaque_cle_du_catalogue_est_utilisee(self):
        dynamiques = {cle for cle in CATALOGS["fr"] if cle.startswith("segment_")}      # libelle_segment : f"segment_{nom}"
        inutilisees = [cle for cle in CATALOGS["fr"] if f'"{cle}"' not in SOURCE and f"'{cle}'" not in SOURCE
                       and cle not in dynamiques]
        self.assertEqual(inutilisees, [])

    def test_pas_de_vieux_nom_dans_l_anglais(self):
        vieux = ["types_portefeuille", "projets_exclus", "etats_attente", "seuil_fermetures_groupees",
                 "separateur_equipes", "point_engagement", "--perimetre", "--rafraichir", "--historique", "--langue"]
        for cle, texte in CATALOGS["en"].items():
            for nom in vieux:
                self.assertNotIn(nom, texte, cle)


class FrancaisInchange(unittest.TestCase):
    def test_sans_option_comme_avec_language_fr_et_comme_la_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            fx.ecrire_yaml(ws, "")                                    # sans flux.yaml, le premier lancement le crée et le dit
            args = ("compute", str(fx.ICI / "ancien_export.csv"), "--name", "ancien", "--today",
                    fx.AUJOURDHUI.isoformat(), "--no-comparison")
            par_defaut = fx.lancer(ws, *args)
            rapport = (ws / "Flux-Lab" / "rapports" / "flux-ancien-2026-10-04.md").read_text(encoding="utf-8")
            avec_option = fx.lancer(ws, *args, "--language", "fr")
            self.assertEqual(par_defaut, avec_option)
            # rapport gelé d'avant la suppression de --dormants : seule la phrase du glossaire sur les dormants change
        attendu = (fx.ICI / "ancien_rapport.md").read_text(encoding="utf-8").replace(
            "(seulement quand un export des dormants est fourni)",
            "(déduit de l'historique des états, option --dormant-from-history)")
        self.assertEqual(rapport, attendu)

    def test_le_francais_du_scenario_n_est_pas_de_l_anglais(self):
        self.assertIn("Métriques de flux", SORTIES["fr"]["compute-simple"])
        self.assertIn("Comment lire ce rapport", SORTIES["fr"]["compute-simple"])

    def test_langue_inconnue_refusee(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(["uv", "run", str(fx.SCRIPT), "compare", "--language", "de"],
                               env={**os.environ, "PMZILLA_LAB_WORKSPACE": tmp}, capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("--language", r.stderr)


class Anglais(unittest.TestCase):
    def test_instantane_anglais(self):
        courant = instantane(SORTIES["en"])
        if os.environ.get("PMZILLA_UPDATE_REFERENCE") == "1":
            REFERENCE.write_text(courant, encoding="utf-8")
        self.assertEqual(courant, REFERENCE.read_text(encoding="utf-8"),
                         "instantané anglais différent : relire le diff, puis PMZILLA_UPDATE_REFERENCE=1 pour le régénérer")

    def test_le_rapport_ecrit_est_dans_la_langue_demandee(self):
        for langue in ("fr", "en"):
            principal, fichiers = decouper(SORTIES[langue]["compute-newer-with-comparison"])
            md = fichiers["rapports/flux-s-2026-10-04.md"]
            self.assertIn(md.rstrip("\n"), principal)
            self.assertEqual(md.startswith("# Flow metrics"), langue == "en")
            evolution = fichiers["rapports/evolution-s-2026-10-04.md"]
            self.assertEqual(evolution.startswith("# Flow evolution"), langue == "en")

    def test_memes_fichiers_et_memes_json_dans_les_deux_langues(self):
        for nom, texte in SORTIES["fr"].items():
            _, fichiers_fr = decouper(texte)
            _, fichiers_en = decouper(SORTIES["en"][nom])
            self.assertEqual(sorted(fichiers_fr), sorted(fichiers_en), nom)       # y compris le nom du rapport
            for chemin in fichiers_fr:
                if chemin.endswith(".json"):
                    self.assertEqual(json.loads(fichiers_fr[chemin]), json.loads(fichiers_en[chemin]), f"{nom} {chemin}")

    def test_pas_de_reste_de_francais(self):
        mots = re.compile(r"\b(le|la|les|des|pour|dans|avec|sans|est|sont|une|du|au|aux|et|ou|par|sur|semaines?|équipes?|"
                          r"jours?|éléments?|aucune?|rapport|tickets? (?:livrés?|terminés?))\b|[éèêëàâùûôîç]", re.IGNORECASE)
        trouves = []
        for numero, ligne in enumerate(instantane(SORTIES["en"]).splitlines(), 1):
            if "->" in ligne or "missing key(s)" in ligne:      # config migrate (ancien -> nouveau) ; clés JSON citées telles quelles
                continue
            trouve = mots.search(ligne)
            if trouve:
                trouves.append(f"{numero}: {trouve.group(0)} | {ligne[:120]}")
        self.assertEqual(trouves, [])

    def test_aucun_vieux_nom_de_reglage_ou_d_option_dans_l_anglais(self):
        vieux = re.compile(r"types_portefeuille|projets_exclus|etats_attente|seuil_fermetures_groupees|separateur_equipes|"
                           r"point_engagement|--perimetre|--rafraichir|--historique|--langue|--motifs-fermetures")
        trouves = [ligne[:120] for ligne in instantane(SORTIES["en"]).splitlines()
                   if vieux.search(ligne) and "->" not in ligne]
        self.assertEqual(trouves, [])


class AncienNomLangue(unittest.TestCase):
    def test_langue_est_refusee_avec_le_nom_actuel(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            fx.ecrire_yaml(ws, "")
            r = subprocess.run(["uv", "run", str(fx.SCRIPT), "statuses", str(fx.ICI / "ancien_export.csv"), "--langue", "en"],
                               env={**os.environ, "PMZILLA_LAB_WORKSPACE": str(ws)}, capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("« --langue » n'existe plus ; utiliser « --language »", r.stderr)
            self.assertEqual(r.stdout, "")

    def test_langue_avant_le_message_d_import(self):
        sys.path.insert(0, str(ICI.parent.parent / "tools"))
        import flux_jira
        self.assertEqual(flux_jira.langue_demandee(["compute", "--language", "en"]), "en")
        self.assertEqual(flux_jira.langue_demandee(["compute", "--language=en"]), "en")
        self.assertEqual(flux_jira.langue_demandee(["compute", "--language", "xx"]), "fr")
        self.assertEqual(flux_jira.langue_demandee(["compute"]), "fr")


if __name__ == "__main__":
    unittest.main()
