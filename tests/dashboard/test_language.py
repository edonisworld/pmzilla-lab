"""
Tests de la langue du tableau de bord (--language fr|en, tools/dashboard_messages.py).

    uv run --with pyyaml python -m unittest discover -s tests/dashboard -v

Les mêmes données inventées que test_dashboard.py. L'instantané anglais est reference_en.html (même dossier, les
scénarios l'un après l'autre) ; l'heure de génération y est remplacée par GENERATED. Pour le régénérer après un
changement voulu d'un texte : PMZILLA_UPDATE_REFERENCE=1 puis relire le diff.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_dashboard as base  # noqa: E402

sys.path.insert(0, str(base.SCRIPT.parent))
from dashboard_messages import CATALOGS  # noqa: E402
from messages import check_catalogs  # noqa: E402

REFERENCE = Path(__file__).resolve().parent / "reference_en.html"


def page(root: Path, env: dict, *options) -> tuple[subprocess.CompletedProcess, str]:
    sortie = root / "page.html"
    full = {**base.without_cases_variables(os.environ), **env, "PMZILLA_LAB_TODAY": "2026-10-12"}
    result = subprocess.run([sys.executable, str(base.RUNNER), "--output", str(sortie), *options], capture_output=True,
                            text=True, env=full, timeout=120)
    texte = sortie.read_text(encoding="utf-8") if sortie.exists() else ""
    return result, re.sub(r"(Generated on |Généré le )\d{2,4}[/-]\d{2}[/-]\d{2,4} \d{2}:\d{2}", r"\1GENERATED", texte)


def scenarios(*options) -> str:
    """Quatre pages : toutes les sources, un seul passage de veille, rappels sans rapport récent, aucune source."""
    morceaux = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env = base.donnees_completes(root)
        morceaux.append(page(root, env, *options)[1])
        log = root / "logs" / "pmzilla-watch.log"
        log.write_text(log.read_text(encoding="utf-8").split("=== 2026-10-11")[0], encoding="utf-8")
        morceaux.append(page(root, env, *options)[1])
        ws = root / "workspace"
        (ws / "_bmad-output" / "pmzilla" / "miroir" / "miroir-2026-10.md").unlink()
        (ws / "Flux-Lab" / "rapports" / "evolution-equipe-x-2026-10-10.md").unlink()
        base.write(ws / "Flux-Lab" / "rapports" / "flux-equipe-x-2026-08-01.md", "# ancien\n")
        morceaux.append(page(root, env, *options)[1])
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env = {"PMZILLA_LAB_WORKSPACE": str(root / "absent-ws"), "PMZILLA_LAB_DATA": str(root / "absent-data"),
               "PMZILLA_LAB_LOGS": str(root / "absent-logs")}
        morceaux.append(page(root, env, *options)[1])
    return "\n<!-- ===== -->\n".join(m.replace("</section>", "</section>\n") for m in morceaux)


class Langue(unittest.TestCase):
    def test_catalogues_coherents(self):
        self.assertEqual(check_catalogs(CATALOGS), [])

    def test_instantane_anglais(self):
        sortie = scenarios("--language", "en")
        if os.environ.get("PMZILLA_UPDATE_REFERENCE") == "1":
            REFERENCE.write_text(sortie, encoding="utf-8")
        self.assertEqual(sortie, REFERENCE.read_text(encoding="utf-8"))

    def test_sans_option_c_est_le_francais(self):
        defaut = scenarios()
        self.assertEqual(defaut, scenarios("--language", "fr"))
        self.assertIn('<html lang="fr">', defaut)
        self.assertIn("Suites en retard (1)", defaut)
        self.assertIn("Expérimentations en attente de résultat", defaut)

    def test_page_anglaise_balise_et_forme(self):
        en = REFERENCE.read_text(encoding="utf-8")
        self.assertIn('<html lang="en">', en)
        self.assertNotIn('<html lang="fr">', en)
        for texte in ("Overdue follow-ups (1)", "2026-10-05", "3 consecutive days", "$0.40", "<title>PMZilla Lab dashboard</title>",
                      "Experiments awaiting a result"):
            self.assertIn(texte, en)
        for cle in base.SECTIONS:                         # les identifiants de section ne changent pas
            self.assertIn(f'<section id="{cle}">', en)
        self.assertNotIn("—", en)

    def test_ancien_nom_langue_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, _ = page(root, base.donnees_completes(root), "--langue", "en")
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("« --langue » n'existe plus ; utiliser « --language »", result.stderr)

    def test_pas_de_francais_dans_la_page_anglaise(self):
        # les données inventées (équipe, Livre Sans Auteur, textes du journal et du miroir...) restent telles quelles
        en = REFERENCE.read_text(encoding="utf-8")
        visible = re.sub(r"<(title|td|li|pre)>.*?</\1>", "", en, flags=re.S)       # cellules et listes de données
        visible = re.sub(r"<style>.*?</style>", "", visible, flags=re.S)
        for mot in re.findall(r"\b(?:Suites?|Échéance|Périmètre|Bibliothèque|Qualité|À faire|Généré|données du|jours?|passages?|"
                              r"pas encore|aucune?|livres?|articles? de la|Régressions|Coût|sans auteur)\b", visible):
            if mot in ("passage", "passages"):
                continue                                   # mot anglais aussi
            self.fail(f"mot français « {mot} » dans la page anglaise")


if __name__ == "__main__":
    unittest.main()
