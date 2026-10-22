"""Langue des messages de tools/flow_views.py (option --language fr|en), sans base : aucune connexion n'est ouverte.

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -v

Le réglage flux.yaml réel n'est jamais lu : le seuil configuré est remplacé par 5.
"""
import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import db  # noqa: E402
import flow_views as fv  # noqa: E402
from flow_views_messages import CATALOGS  # noqa: E402
from messages import Messages  # noqa: E402


def lancer(*argv: str) -> tuple[int, str, str]:
    sortie, erreur = io.StringIO(), io.StringIO()
    with mock.patch.object(fv, "seuil_configure", return_value=fv.PLANCHER), \
            contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
        code = fv.main(list(argv))
    return code, sortie.getvalue(), erreur.getvalue()


class Langue(unittest.TestCase):
    def test_vue_inconnue_dans_chaque_langue(self):
        with mock.patch.object(db, "connect", side_effect=AssertionError("pas de connexion")):
            self.assertIn("Vue inconnue : issues", lancer("show", "issues")[2])                  # français par défaut
            self.assertIn("Vue inconnue : issues", lancer("--language", "fr", "show", "issues")[2])
            code, _, erreur = lancer("--language", "en", "show", "issues")
        self.assertEqual(code, 1)
        self.assertIn("Unknown view: issues. Available views: v_team_status", erreur)
        self.assertNotIn("Vue inconnue", erreur)

    def test_liste_des_vues_dans_chaque_langue(self):
        _, fr, _ = lancer("list")
        _, en, _ = lancer("--language", "en", "list")
        self.assertIn("Vues agrégées du schéma flow", fr)
        self.assertIn("tickets par équipe", fr)
        self.assertIn("Aggregated views of the flow schema", en)
        self.assertIn("tickets by team, type, status category and status", en)
        self.assertNotIn("Vues agrégées", en)
        for vue in fv.VUES:
            self.assertIn(vue, en)

    def test_descriptions_des_deux_vues_des_noms_d_equipe_dans_chaque_langue(self):
        """Change team-names-readable, conception D10."""
        _, fr, _ = lancer("list")
        _, en, _ = lancer("--language", "en", "list")
        self.assertIn("équipes connues de la base, avec leur type et leurs tickets dans l'export", fr)
        self.assertIn("identifiants d'équipe Jira vus sur les tickets, par nom d'équipe", fr)
        self.assertIn("teams known to the database, with their type and their tickets in the export", en)
        self.assertIn("Jira team identifiers seen on tickets, by team name", en)
        self.assertNotIn("équipes connues de la base", en)
        self.assertNotIn("teams known to the database", fr)
        for vue in ("v_teams", "v_team_jira_ids"):
            self.assertIn(vue, fr)
            self.assertIn(vue, en)

    def test_erreur_de_base_dans_chaque_langue(self):
        with mock.patch.object(db, "connect", side_effect=db.ErreurBase("injoignable")):
            self.assertIn("Erreur : injoignable", lancer("show", "v_team_status")[2])
            self.assertIn("Error: injoignable", lancer("--language", "en", "show", "v_team_status")[2])

    def test_seuil_releve_sous_le_plancher_dans_chaque_langue(self):
        with mock.patch.object(db, "connect", side_effect=db.ErreurBase("x")):
            self.assertIn("Seuil de masquage ramené à 5", lancer("show", "v_team_status", "--min-cell", "2")[2])
            self.assertIn("Masking threshold raised to 5", lancer("--language", "en", "show", "v_team_status", "--min-cell", "2")[2])

    def test_rendu_sans_ligne_et_cellule_masquee_dans_chaque_langue(self):
        en, fr = Messages(CATALOGS, "en"), Messages(CATALOGS, "fr")
        self.assertEqual(fv.rendre(["team", "tickets"], [], 5, fr), "(aucune ligne)")
        self.assertEqual(fv.rendre(["team", "tickets"], [], 5, en), "(no rows)")
        self.assertRegex(fv.rendre(["team", "tickets"], [("Alpha", 2)], 5, en), r"Alpha\s+masked$")    # idée #417 : le mot de la langue
        self.assertRegex(fv.rendre(["team", "tickets"], [("Alpha", 2)], 5, fr), r"Alpha\s+masqué$")

    def test_seuil_releve_rappele_dans_chaque_langue(self):
        with mock.patch.object(db, "connect", side_effect=db.ErreurBase("x")):
            self.assertIn("Seuil de masquage : 12 tickets (une cellule sous ce seuil s'écrit « masqué »).",
                          lancer("show", "v_team_status", "--min-cell", "12")[2])
            self.assertIn("Masking threshold: 12 tickets (a cell under this threshold is written \"masked\").",
                          lancer("--language", "en", "show", "v_team_status", "--min-cell", "12")[2])


if __name__ == "__main__":
    unittest.main()
