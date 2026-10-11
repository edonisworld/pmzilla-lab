"""flux_jira.py : sous-commandes, options et réglages en anglais (plan de la version anglaise, 7.4 à 7.6).

Les anciens noms d'options, de réglages et de sous-commandes sont refusés, avec le nom actuel. `config migrate` réécrit un
flux.yaml d'avant le lot 8 ; il est testé sur un dossier temporaire, jamais sur Flux-Lab/. Le rapport d'un fichier migré
est celui du fichier écrit avec les nouveaux noms."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import test_flux_jira as fx  # noqa: E402

ANCIEN_YAML = """etats_en_cours: [In Progress, In Review, Doing, Validation]
etats_a_faire: [Open, Waiting]
etats_attente: [Ready for]
projets_exclus: [DEF]
motifs_fermetures_groupees: [Done]
seuil_fermetures_groupees: 5
colonnes:
  etat: [Status]
"""
NOUVEAU_YAML = """in_progress_states: [In Progress, In Review, Doing, Validation]
todo_states: [Open, Waiting]
waiting_states: [Ready for]
excluded_projects: [DEF]
batch_closure_resolutions: [Done]
batch_closure_threshold: 5
columns:
  status: [Status]
"""


def lancer_brut(ws: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(ws)}
    return subprocess.run(["uv", "run", str(fx.SCRIPT), *args], env=env, capture_output=True, text=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name)
        lignes = fx.construire(__import__("random").Random(7), "ABC", fx.WORKFLOW_1, 30, ["Equipe A", "Equipe B"],
                               ["Story", "Bug"])
        self.export = self.ws / "export.csv"
        fx.ecrire_csv(self.export, lignes)

    def calculer(self, nom: str, yaml_texte: str, *options: str) -> tuple[str, str]:
        fx.ecrire_yaml(self.ws, yaml_texte)
        r = lancer_brut(self.ws, "compute", str(self.export), "--name", nom, "--today", fx.AUJOURDHUI.isoformat(),
                        "--no-comparison", *options)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rapport = (self.ws / "Flux-Lab" / "rapports" / f"flux-{nom}-{fx.AUJOURDHUI.isoformat()}.md").read_text(encoding="utf-8")
        return rapport, r.stderr


class AncienEtNouveau(Base):
    def test_anciens_noms_de_reglages_refuses_avec_le_nom_actuel(self):
        fx.ecrire_yaml(self.ws, ANCIEN_YAML)
        r = lancer_brut(self.ws, "compute", str(self.export), "--name", "a", "--today", fx.AUJOURDHUI.isoformat(), "--no-comparison")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("« etats_en_cours » n'existe plus ; utiliser « in_progress_states »", r.stdout + r.stderr)
        self.assertFalse(list((self.ws / "Flux-Lab" / "rapports").glob("flux-a-*")))
        _, erreur_nouveau = self.calculer("a", NOUVEAU_YAML)
        self.assertEqual(erreur_nouveau, "")

    def test_anciennes_options_refusees_avec_le_nom_actuel(self):
        fx.ecrire_yaml(self.ws, NOUVEAU_YAML)
        for ancien, nouveau_nom in (("--nom", "--name"), ("--aujourdhui", "--today"), ("--sans-comparaison", "--no-comparison"),
                                    ("--perimetre", "--scope"), ("--semaines", "--weeks")):
            r = lancer_brut(self.ws, "compute", str(self.export), ancien, "x")
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn(f"« {ancien} » n'existe plus ; utiliser « {nouveau_nom} »", r.stderr)
        self.assertFalse(list((self.ws / "Flux-Lab" / "rapports").glob("flux-*")))

    def test_anciens_noms_de_sous_commandes_refuses(self):
        for ancien in ("statuts", "calcul", "comparer"):
            r = lancer_brut(self.ws, ancien, str(self.export))
            self.assertEqual(r.returncode, 2, ancien)
            self.assertIn("invalid choice", r.stderr)

    def test_statuses_et_compare_existent(self):
        fx.ecrire_yaml(self.ws, NOUVEAU_YAML)
        r = lancer_brut(self.ws, "statuses", str(self.export))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("in_progress_states et todo_states", r.stdout)
        self.assertNotIn("etats_en_cours", r.stdout)
        self.calculer("c", NOUVEAU_YAML)
        r = lancer_brut(self.ws, "compare", "--name", "c")
        self.assertNotIn("invalid choice", r.stderr)

    def test_reglages_par_defaut_ecrits_avec_les_noms_anglais(self):
        r = lancer_brut(self.ws, "compute", str(self.export), "--name", "d", "--today", fx.AUJOURDHUI.isoformat(),
                        "--no-comparison")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ecrit = (self.ws / "Flux-Lab" / "flux.yaml").read_text(encoding="utf-8")
        for cle in ("columns:", "in_progress_states:", "todo_states:", "excluded_resolutions:",
                    "portfolio_types:", "excluded_projects:", "waiting_states:", "uncounted_segments:", "commitment_point: ready",
                    "team_separator:", "batch_closure_threshold:", "batch_closure_resolutions:"):
            self.assertIn(cle, ecrit)
        for ancien in ("colonnes:", "etats_en_cours:", "motifs_exclus:", "point_engagement:"):
            self.assertNotIn(ancien, ecrit)
        self.assertIn("  review_verification:", ecrit)
        self.assertEqual(r.stderr, "")


class ConfigMigrate(Base):
    def test_migrate_reecrit_le_fichier_et_garde_l_ancien(self):
        fx.ecrire_yaml(self.ws, "# mes réglages\n" + ANCIEN_YAML)
        r = lancer_brut(self.ws, "config", "migrate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        dossier = self.ws / "Flux-Lab"
        self.assertEqual((dossier / "flux.yaml.avant-migration").read_text(encoding="utf-8"), "# mes réglages\n" + ANCIEN_YAML)
        nouveau = (dossier / "flux.yaml").read_text(encoding="utf-8")
        self.assertEqual(nouveau, "# mes réglages\n" + NOUVEAU_YAML)
        self.assertIn("etats_en_cours -> in_progress_states", r.stdout)
        self.assertIn("colonnes.etat -> status", r.stdout)
        self.assertNotIn("In Progress", r.stdout)                                   # aucune valeur affichée
        self.assertEqual(r.stderr, "")
        r = lancer_brut(self.ws, "config", "migrate")
        self.assertIn("Rien à migrer", r.stdout)

    def test_dry_run_n_ecrit_rien(self):
        fx.ecrire_yaml(self.ws, ANCIEN_YAML)
        r = lancer_brut(self.ws, "config", "migrate", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Changements qui seraient faits", r.stdout)
        self.assertEqual((self.ws / "Flux-Lab" / "flux.yaml").read_text(encoding="utf-8"), ANCIEN_YAML)
        self.assertFalse((self.ws / "Flux-Lab" / "flux.yaml.avant-migration").exists())

    def test_sans_fichier(self):
        (self.ws / "Flux-Lab").mkdir()
        r = lancer_brut(self.ws, "config", "migrate")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("introuvable", r.stderr + r.stdout)

    def test_le_fichier_migre_donne_le_meme_rapport_sans_avertissement(self):
        attendu, _ = self.calculer("m", NOUVEAU_YAML)
        fx.ecrire_yaml(self.ws, ANCIEN_YAML)
        lancer_brut(self.ws, "config", "migrate")
        r = lancer_brut(self.ws, "compute", str(self.export), "--name", "m", "--today", fx.AUJOURDHUI.isoformat(), "--no-comparison")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stderr, "")
        rapport = (self.ws / "Flux-Lab" / "rapports" / f"flux-m-{fx.AUJOURDHUI.isoformat()}.md").read_text(encoding="utf-8")
        self.assertEqual(rapport, attendu)


GRAND_ANCIEN_YAML = """etats_en_cours: [In Progress, In Review]
etats_a_faire: [Open]
etats_attente: [In Review]
motifs_exclus: [Rejected]
TYPES_LIGNE
projets_exclus: [DEF]
projets_perimetre: []
separateur_equipes: ";"
seuil_fermetures_groupees: 3
motifs_fermetures_groupees: [Done]
colonnes:
  debut: [Status Category Changed]
  equipe: [Team]
  motif: [Resolution]
  resolu: [Resolved]
"""


class GrandeMigration(Base):
    """Réglages calculés avec les anciens noms, puis avec les nouveaux : mêmes rapports (types, projets, colonnes)."""

    def rapport(self, nom: str) -> str:
        r = lancer_brut(self.ws, "compute", str(self.export), "--name", nom, "--today", fx.AUJOURDHUI.isoformat(), "--no-comparison")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return (self.ws / "Flux-Lab" / "rapports" / f"flux-{nom}-{fx.AUJOURDHUI.isoformat()}.md").read_text(encoding="utf-8")

    def verifier(self, ligne_types: str):
        fx.ecrire_yaml(self.ws, GRAND_ANCIEN_YAML.replace("TYPES_LIGNE", ligne_types))
        r = lancer_brut(self.ws, "compute", str(self.export), "--name", "g", "--today", fx.AUJOURDHUI.isoformat(), "--no-comparison")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)                    # l'ancien fichier est refusé
        r = lancer_brut(self.ws, "config", "migrate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("portfolio_types", (self.ws / "Flux-Lab" / "flux.yaml").read_text(encoding="utf-8"))
        nouveau = self.rapport("g")
        self.assertIn("Écartés du débit", nouveau)          # le réglage de types a bien joué après la migration

    def test_types_portefeuille_ancien_nom_refuse_puis_migre(self):
        self.verifier("types_portefeuille: [Bug]")

    def test_types_exclus_ancien_nom_refuse_avec_portfolio_types_puis_migre(self):
        fx.ecrire_yaml(self.ws, "types_exclus: [Bug]\n")
        r = lancer_brut(self.ws, "compute", str(self.export), "--name", "h", "--today", fx.AUJOURDHUI.isoformat(), "--no-comparison")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("« types_exclus » n'existe plus ; utiliser « portfolio_types »", r.stdout + r.stderr)
        self.verifier("types_exclus: [Bug]")

    def test_les_deux_cles_dans_flux_yaml_bloquent_la_migration_sans_rien_ecrire(self):
        texte = GRAND_ANCIEN_YAML.replace("TYPES_LIGNE", "types_exclus: [SecretA]\ntypes_portefeuille: [SecretB]")
        fx.ecrire_yaml(self.ws, texte)
        for options in (("--dry-run",), ()):
            r = lancer_brut(self.ws, "config", "migrate", *options)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("Migration impossible", r.stdout)
            self.assertIn("L5 et L6 : « types_exclus » et « types_portefeuille » donnent la même clé « portfolio_types »", r.stdout)
            self.assertNotIn("Secret", r.stdout + r.stderr)
        self.assertEqual((self.ws / "Flux-Lab" / "flux.yaml").read_text(encoding="utf-8"), texte)
        self.assertFalse((self.ws / "Flux-Lab" / "flux.yaml.avant-migration").exists())

    def test_la_sortie_donne_le_chemin_complet_sans_valeurs(self):
        fx.ecrire_yaml(self.ws, GRAND_ANCIEN_YAML.replace("TYPES_LIGNE", "types_portefeuille: [SecretB]"))
        r = lancer_brut(self.ws, "config", "migrate", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("L6 : projets_exclus -> excluded_projects", r.stdout)
        self.assertIn("L12 : colonnes.debut -> category_changed", r.stdout)
        self.assertNotIn("SecretB", r.stdout)
        self.assertNotIn("DEF", r.stdout)


if __name__ == "__main__":
    unittest.main()
