"""
Tests de la langue du miroir de Critic (--language fr|en, tools/critic_mirror_messages.py).

    uv run --with pyyaml python -m unittest discover -s tests/critic_mirror -v

Les mêmes livrables inventés que test_critic_mirror.py. L'instantané anglais est reference_en.md (même dossier) ;
pour le régénérer après un changement voulu d'un texte : PMZILLA_UPDATE_REFERENCE=1 puis relire le diff.
Les objections recopiées sont des extraits de livrables : elles restent dans la langue du livrable, dans les deux langues.
"""
import contextlib
import io
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_critic_mirror as base  # noqa: E402

miroir = base.miroir
from critic_mirror_messages import CATALOGS  # noqa: E402
from messages import check_catalogs  # noqa: E402

REFERENCE = Path(__file__).resolve().parent / "reference_en.md"


class Langue(base.Base):
    def setUp(self):
        super().setUp()
        self.ecrire("2026-10-03-diagnostic-flux.md", base.DIAGNOSTIC)
        self.ecrire("messages/2026-10-10-message.md", base.MESSAGE)
        self.ecrire("2026-10-12-sans-critic.md", "# Livrable\n\n[Posture : Facilitation]\n\nTexte.\n")
        self.ecrire("2026-09-20-ancien.md", base.DIAGNOSTIC)
        self.ecrire("2026-10-08-nu.md", "## Revue de Critic\n\n- Une objection.\n")
        self.ecrire("veille/2026-10-05-synthese.md", "## Ce que Critic conteste\n\n- Un article pèse comme un livre.\n\n"
                                                   "## Sources\n\n- x\n")

    def scenario(self, *langue) -> str:
        return "\n".join(f"$ {' '.join(arguments)}\n{self.lancer(*arguments, *langue)}" for arguments in
                         ((), ("--since", "2026-09-01", "--until", "2026-09-30"), ("--since", "2030-01-01", "--until", "2030-01-02")))

    def test_catalogues_coherents(self):
        self.assertEqual(check_catalogs(CATALOGS), [])

    def test_instantane_anglais(self):
        sortie = self.scenario("--language", "en")
        if os.environ.get("PMZILLA_UPDATE_REFERENCE") == "1":
            REFERENCE.write_text(sortie, encoding="utf-8")
        self.assertEqual(sortie, REFERENCE.read_text(encoding="utf-8"))

    def test_sans_option_c_est_le_francais(self):
        sortie = self.scenario()
        self.assertEqual(sortie, self.scenario("--language", "fr"))
        self.assertIn("# Objections de Critic du 2026-10-01 au 2026-10-15", sortie)
        self.assertIn("livrable de posture · posture Delivery", sortie)

    def test_ancien_nom_langue_refuse_avec_le_nom_actuel(self):
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur), self.assertRaises(SystemExit) as stop:
            self.lancer("--langue", "en")
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("« --langue »", erreur.getvalue())
        self.assertIn("« --language »", erreur.getvalue())
        self.assertIn("# Critic objections from 2026-10-01", self.lancer("--language", "en"))

    def test_grille_de_classement_une_seule_source_dans_les_deux_langues(self):
        """`--categories` : 11 catégories en tableau, dans la langue demandée, sans lire les livrables."""
        for langue, titre, premiere, derniere in (("fr", "## Grille de classement", "hypothèse prise pour un fait", "autre"),
                                                 ("en", "## Classification grid", "hypothesis taken as fact", "other")):
            sortie = self.lancer("--categories", "--language", langue)
            lignes = sortie.splitlines()
            self.assertEqual(lignes[0], titre)
            lignes_categories = [l for l in lignes if l.startswith("| ") and not l.startswith("| Cat") and not l.startswith("|---")]
            self.assertEqual(len(lignes_categories), 11, langue)
            self.assertTrue(lignes_categories[0].startswith(f"| {premiere} |"), langue)
            self.assertTrue(lignes_categories[-1].startswith(f"| {derniere} |"), langue)
            self.assertNotIn("Objections de Critic", sortie)
            self.assertNotIn("objection(s)", sortie)
        self.assertEqual(self.lancer("--categories"), self.lancer("--categories", "--language", "fr"))

    def test_la_commande_ne_recopie_pas_la_grille(self):
        commande = (Path(__file__).resolve().parents[2] / ".claude" / "commands" / "critic-mirror.md").read_text(encoding="utf-8")
        self.assertIn("--categories", commande)
        for langue in ("fr", "en"):
            for n in range(1, 12):
                self.assertNotIn(CATALOGS[langue][f"category_{n}_name"] + " |", commande)

    def test_le_nombre_d_objections_reste_lisible_par_le_tableau_de_bord(self):
        for langue in ("fr", "en"):
            ligne = self.lancer("--language", langue).splitlines()[2]
            self.assertTrue(re.search(r"(\d+) objection", ligne), ligne)

    def test_pas_de_francais_dans_la_sortie_anglaise(self):
        # hors objections recopiées (extraits de livrables inventés, en français) et noms de fichiers inventés
        for ligne in REFERENCE.read_text(encoding="utf-8").splitlines():
            if ligne.startswith(("- O", "$ ", "- 2026")) or (ligne.startswith("## ") and ".md" in ligne and "Deliverables" not in ligne):
                continue
            for mot in re.findall(r"\b(?:livrables?|période|sans|du|au|synthèse|non indiquée)\b", ligne):
                self.fail(f"mot français « {mot} » dans la sortie anglaise : {ligne}")


if __name__ == "__main__":
    unittest.main()
