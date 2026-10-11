"""
Tests de la langue du journal (--language fr|en, tools/journal_lab_messages.py).

    uv run --with pyyaml python -m unittest discover -s tests/journal_lab -v

Les mêmes données inventées que test_journal_lab.py. L'instantané anglais est reference_en.md (même dossier) ;
pour le régénérer après un changement voulu d'un texte : PMZILLA_UPDATE_REFERENCE=1 puis relire le diff.
"""
import contextlib
import io
import os
import re
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_journal_lab as base  # noqa: E402

journal = base.journal
from journal_lab_messages import CATALOGS  # noqa: E402
from messages import check_catalogs  # noqa: E402

REFERENCE = Path(__file__).resolve().parent / "reference_en.md"
DEUXIEME = ("type: coaching\nperimetre: rôle Product Owner\ntente: Échange.\nconstat: Clair.\ndate: 2026-09-20\n"
            "suites:\n  - quoi: Clarifier le critère d'acceptation\n    pour: Product Owner\n    echeance: 2026-10-30\n")
BASE = "type: rétro\nperimetre: équipe Alpha\ntente: A.\nconstat: B.\n"
REFUS = [BASE.replace("A.\nconstat: B.\n", "A.\n"), BASE + "personne: X\n", BASE.replace("rétro", "soirée"),
         BASE + "posture: magie\n", BASE + "date: 2026-12-01\n", BASE + "date: hier\n", BASE.replace("A.", "x" * 601),
         "- une\n- liste\n", BASE + "suites:\n  - quoi: Faire\n    pour: SM\n", BASE + "suites:\n  - juste du texte\n",
         BASE + "experience: truc\n", BASE + "suites:\n  - quoi: Faire\n    echeance: 2026-10-10\n"]


class Langue(base.Base):
    def scenario(self, *langue) -> str:
        """Toutes les sorties du journal pour une langue, une section par commande."""
        morceaux = []

        def lancer(*arguments, aujourdhui=base.AUJOURDHUI):
            try:
                sortie = self.cli(*arguments, *langue, aujourdhui=aujourdhui)
            except SystemExit as erreur:
                sortie = f"[exit] {erreur.code}\n"
            morceaux.append(f"$ {' '.join(a for a in arguments if not a.endswith('.yaml'))}\n{sortie}")

        lancer("add", str(self.fichier(base.ENTREE, "un.yaml")))
        lancer("add", str(self.fichier(DEUXIEME, "deux.yaml")))
        for n, texte in enumerate(REFUS):
            lancer("add", str(self.fichier(texte, f"refus{n}.yaml")))
        lancer("add", str(self.tmp / "absent.yaml"))
        lancer("follow-ups")
        lancer("follow-ups", "--scope", "PRODUCT owner")
        lancer("follow-ups", "--scope", "inconnu")
        lancer("follow-ups", aujourdhui="2026-10-03")
        lancer("update", "J-20261001-1.s1", "faite", "--note", "Fait sur place.")
        lancer("update", "J-20261001-1.s2", "abandonnee")
        lancer("update", "J-20261001-1.x", "conclue")
        lancer("update", "J-20261001-1.x", "faite")
        lancer("update", "J-20261001-1.s1", "conclue")
        lancer("update", "J-1.s9", "faite")
        lancer("update", "J-20261001-1.x", "conclue", "--note", "Hypothèse confirmée.")
        lancer("follow-ups", "--all")
        lancer("review", "--since", "2026-09-01")
        lancer("review", "--since", "2026-09-01", "--scope", "product owner")
        return "\n".join(morceaux).replace(str(self.tmp), "<tmp>")

    def test_catalogues_coherents(self):
        self.assertEqual(check_catalogs(CATALOGS), [])

    def test_instantane_anglais(self):
        sortie = self.scenario("--language", "en")
        if os.environ.get("PMZILLA_UPDATE_REFERENCE") == "1":
            REFERENCE.write_text(sortie, encoding="utf-8")
        self.assertEqual(sortie, REFERENCE.read_text(encoding="utf-8"))

    def test_sans_option_c_est_le_francais(self):
        sans_option = self.scenario()
        shutil.rmtree(journal.JOURNAL_DIR)
        self.assertEqual(sans_option, self.scenario("--language", "fr"))
        self.assertIn("Séance notée : J-20261001-1", sans_option)

    def test_valeurs_de_statut_ecrites_en_francais(self):
        self.scenario("--language", "en")
        statuts = {s["statut"] for e in self.entrees() for s in e["suites"]}
        self.assertEqual(statuts, {"ouverte", "faite", "abandonnee"})
        self.assertEqual(self.entrees()[0]["experience"]["statut"], "conclue")

    def test_ancien_nom_langue_refuse_avec_le_nom_actuel(self):
        self.ajouter()
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur), self.assertRaises(SystemExit) as stop:
            self.cli("follow-ups", "--langue", "en")
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("« --langue »", erreur.getvalue())
        self.assertIn("« --language »", erreur.getvalue())
        self.assertIn("Follow-ups (open) as of", self.cli("follow-ups", "--language", "en"))

    def test_pas_de_francais_dans_la_sortie_anglaise(self):
        # les données inventées des tests (équipe Alpha, rétro, Échange...) et les valeurs de statut écrites restent en français
        texte = REFERENCE.read_text(encoding="utf-8")
        for ligne in texte.splitlines():
            if ligne.startswith("$ "):
                continue
            for mot in re.findall(r"\b(?:séance|suites?(?!\[)|pour le|expérience|hypothèse|ouvertes|retard|promises)\b", ligne):
                self.fail(f"mot français « {mot} » dans la sortie anglaise : {ligne}")


if __name__ == "__main__":
    unittest.main()
