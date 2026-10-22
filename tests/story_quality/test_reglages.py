"""
Tests de la lecture stricte du bloc `story_quality` de flux.yaml (change story-quality-audit, tâche 3.5, design D16) : lecture par
tools/flux_config.py, comme les autres blocs (`to_internal` valide, `story_quality` rend les réglages normalisés).

  - le plafond par lancement est obligatoire et un entier positif (refus : ErreurPlafond, que l'outil traduit en code 3) ;
  - les prix, la taille d'échantillon de la relecture pilote et le seuil de récurrence (une part) sont validés ;
  - une clé qui nommerait le chemin de la surcouche est inconnue ; toute clé inconnue est refusée en nommant la clé, jamais la valeur.

Données inventées ; les valeurs « zz » sont distinctives et ne doivent jamais ressortir d'un message.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
import flux_config  # noqa: E402
from yaml_strict import ErreurConfig, charger  # noqa: E402

BLOC = """story_quality:
  queries:
    pilote: "project = ZZPROJ AND type in (Story, Epic)"
  issue_types:
    story: [Story, Récit]
    epic: [Epic]
  acceptance_criteria_field: customfield_10500
  engine:
    model: zzmodele-fictif
    keychain_service: pmzilla-story-quality-zz
    timeout_seconds: 30
    feedback_max_chars: 400
    input_price_per_token: 0.000003
    output_price_per_token: 0.000015
    currency: EUR
    cap_per_launch: 50
  review_sample_size: 8
  grid_twin: tools/story_quality_grid.json
  recurrence_threshold: 0.4
"""


def lire(texte: str) -> dict:
    return flux_config.to_internal(charger(texte, "flux.yaml"), "flux.yaml")


def remplacer(ancien: str, nouveau: str) -> str:
    assert ancien in BLOC, ancien
    return BLOC.replace(ancien, nouveau)


class BlocValide(unittest.TestCase):
    def test_lecture_normalisee(self):
        reglages = flux_config.story_quality(lire(BLOC))
        self.assertEqual(reglages["queries"], [("pilote", "project = ZZPROJ AND type in (Story, Epic)")])
        self.assertEqual(reglages["kinds"], {"Story": "story", "Récit": "story", "Epic": "epic"})
        self.assertEqual(reglages["acceptance_criteria_field"], "customfield_10500")
        self.assertEqual(reglages["engine"]["cap_per_launch"], 50)
        self.assertEqual(reglages["engine"]["currency"], "EUR")
        self.assertEqual(reglages["review_sample_size"], 8)
        self.assertEqual(reglages["recurrence_threshold"], 0.4)
        self.assertEqual(reglages["grid_twin"], "tools/story_quality_grid.json")

    def test_sans_bloc_le_lecteur_rend_none(self):
        self.assertIsNone(flux_config.story_quality(lire("jira_site: https://exemple.atlassian.net\n")))

    def test_les_facultatifs_prennent_leur_valeur_par_defaut(self):
        texte = """story_quality:
  queries: {pilote: "project = ZZPROJ"}
  issue_types: {story: [Story]}
  engine:
    model: m
    keychain_service: s
    input_price_per_token: 0
    output_price_per_token: 0
    cap_per_launch: 1
"""
        reglages = flux_config.story_quality(lire(texte))
        self.assertIsNone(reglages["acceptance_criteria_field"])
        self.assertIsNone(reglages["review_sample_size"])
        self.assertIsNone(reglages["recurrence_threshold"])
        self.assertIsNone(reglages["grid_twin"])
        self.assertEqual(reglages["engine"]["timeout_seconds"], flux_config.MOTEUR_DEFAUTS["timeout_seconds"])
        self.assertEqual(reglages["kinds"], {"Story": "story"})

    def test_un_seuil_de_un_est_une_part_valide(self):
        self.assertEqual(flux_config.story_quality(lire(remplacer("recurrence_threshold: 0.4", "recurrence_threshold: 1")))
                         ["recurrence_threshold"], 1)

    def test_le_bloc_ne_gene_pas_les_autres_reglages(self):
        reglages = lire("jira_site: https://exemple.atlassian.net\n" + BLOC)
        self.assertEqual(reglages["jira_site"], "https://exemple.atlassian.net")
        self.assertIn("story_quality", flux_config.INCHANGEES)


class Refus(unittest.TestCase):
    def refuse(self, texte: str, chemin: str, classe=ErreurConfig):
        with self.assertRaises(classe) as contexte:
            lire(texte)
        message = str(contexte.exception)
        self.assertIn(chemin, message)
        self.assertNotIn("zz", message.lower().replace("pmzilla", ""))      # jamais une valeur distinctive
        return message

    def test_cle_inconnue_nommee_sans_valeur(self):
        self.refuse(BLOC + "  autre_cle: zzvaleur\n", "story_quality.autre_cle")

    def test_une_cle_de_chemin_de_surcouche_est_inconnue(self):
        for cle in ("overlay", "overlay_path", "overlay_file"):
            with self.subTest(cle=cle), self.assertRaises(ErreurConfig) as contexte:
                lire(BLOC + f"  {cle}: /chemin/zzsurcouche.yaml\n")
            self.assertIn(f"story_quality.{cle}", str(contexte.exception))
            self.assertNotIn("zzsurcouche", str(contexte.exception))

    def test_cle_inconnue_du_moteur(self):
        self.refuse(remplacer("    currency: EUR\n", "    currency: EUR\n    skip_confirmation: true\n"),
                    "story_quality.engine.skip_confirmation")

    def test_le_plafond_est_obligatoire(self):
        self.refuse(remplacer("    cap_per_launch: 50\n", ""), "story_quality.engine.cap_per_launch", flux_config.ErreurPlafond)

    def test_le_plafond_est_un_entier_positif(self):
        for valeur in ("0", "-3", "2.5", "true", '"50"', "null"):
            with self.subTest(valeur=valeur):
                self.refuse(remplacer("cap_per_launch: 50", f"cap_per_launch: {valeur}"), "story_quality.engine.cap_per_launch",
                            flux_config.ErreurPlafond)

    def test_l_erreur_de_plafond_est_une_erreur_de_reglage(self):
        self.assertTrue(issubclass(flux_config.ErreurPlafond, ErreurConfig))

    def test_les_prix_sont_des_nombres_positifs_ou_nuls(self):
        for cle in ("input_price_per_token", "output_price_per_token"):
            for valeur in ("-0.1", '"cher"', "true"):
                with self.subTest(cle=cle, valeur=valeur):
                    ancien = f"{cle}: " + ("0.000003" if cle.startswith("input") else "0.000015")
                    self.refuse(remplacer(ancien, f"{cle}: {valeur}"), f"story_quality.engine.{cle}")
            with self.subTest(cle=cle, valeur="absent"):
                ancien = f"    {cle}: " + ("0.000003" if cle.startswith("input") else "0.000015") + "\n"
                self.refuse(remplacer(ancien, ""), f"story_quality.engine.{cle}")

    def test_la_taille_d_echantillon_pilote(self):
        for valeur in ("0", "-1", "1.5", '"8"'):
            with self.subTest(valeur=valeur):
                self.refuse(remplacer("review_sample_size: 8", f"review_sample_size: {valeur}"), "story_quality.review_sample_size")

    def test_le_seuil_de_recurrence_est_une_part(self):
        for valeur in ("0", "1.5", "-0.2", '"0.4"', "true"):
            with self.subTest(valeur=valeur):
                self.refuse(remplacer("recurrence_threshold: 0.4", f"recurrence_threshold: {valeur}"),
                            "story_quality.recurrence_threshold")

    def test_les_bornes_du_moteur(self):
        self.refuse(remplacer("feedback_max_chars: 400", "feedback_max_chars: 5000"), "story_quality.engine.feedback_max_chars")
        self.refuse(remplacer("feedback_max_chars: 400", "feedback_max_chars: 0"), "story_quality.engine.feedback_max_chars")
        self.refuse(remplacer("timeout_seconds: 30", "timeout_seconds: 0"), "story_quality.engine.timeout_seconds")
        self.refuse(remplacer("model: zzmodele-fictif", 'model: ""'), "story_quality.engine.model")

    def test_les_requetes(self):
        self.refuse(remplacer('    pilote: "project = ZZPROJ AND type in (Story, Epic)"\n', ""), "story_quality.queries")
        self.refuse(remplacer("    pilote:", "    nom avec espaces:"), "story_quality.queries")
        self.refuse(remplacer('pilote: "project = ZZPROJ AND type in (Story, Epic)"', 'pilote: ""'), "story_quality.queries.pilote")

    def test_les_types(self):
        self.refuse(remplacer("    epic: [Epic]\n", "    epic: [Epic, Story]\n"), "story_quality.issue_types")
        self.refuse(remplacer("    epic: [Epic]\n", "    epic: [Epic]\n    bug: [Bug]\n"), "story_quality.issue_types.bug")
        self.refuse(remplacer("    epic: [Epic]\n", "    epic: []\n"), "story_quality.issue_types.epic")

    def test_le_champ_des_criteres_d_acceptation(self):
        self.refuse(remplacer("acceptance_criteria_field: customfield_10500", 'acceptance_criteria_field: "champ zz/x"'),
                    "story_quality.acceptance_criteria_field")

    def test_obligatoires_du_bloc(self):
        debut, _, fin = BLOC.partition("  engine:\n")
        sans_moteur = debut + "  review_sample_size: 8\n"
        self.refuse(sans_moteur, "story_quality.engine")
        self.refuse("story_quality:\n  engine: {}\n", "story_quality.queries")
        self.refuse("story_quality:\n", "story_quality")


if __name__ == "__main__":
    unittest.main()
