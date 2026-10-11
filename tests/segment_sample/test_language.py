"""Tests de la langue des sorties de segment_sample.py (--language fr|en), sur un faux espace de travail.

    uv run --with pyyaml --with numpy python -m unittest discover -s tests/segment_sample -v

Le même parcours (échantillon, --by-state, --starts, segments réglés, arrêts) est lancé en anglais et comparé à un
instantané versionné (reference_en.md) ; pour le régénérer après un changement voulu : PMZILLA_UPDATE_SNAPSHOTS=1.
Les données sont celles de test_segment_sample.py : aucune donnée réelle. Les réglages de flux.yaml y sont écrits sous
leurs nouveaux noms, pour que flux_config n'ajoute aucun avertissement à la sortie.
"""
import datetime as dt
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_segment_sample as base           # noqa: E402

from messages import check_catalogs           # noqa: E402
from segment_sample_messages import CATALOGS  # noqa: E402

ICI = Path(__file__).resolve().parent
REFERENCE_EN = ICI / "reference_en.md"
D = dt.date.fromisoformat
MOTS_FRANCAIS = re.compile(r"\b(le|la|les|des|du|pour|dans|sur|avec|équipe|semaine|jours|tickets? lus|écartés|"
                           r"aucun|aucune|seulement|selon|plus longs|segment calculé)\b|[éèêàâçùôî]", re.IGNORECASE)
REGLAGES = "excluded_projects: [EXC]\nportfolio_types: [Initiative]\nwaiting_states: ['Ready for', 'On Hold']\n"
_CACHE: dict[tuple, str] = {}


def atelier(racine: Path, reglages: str = REGLAGES) -> "base.Atelier":
    a = base.Atelier(racine)
    (racine / "Flux-Lab" / "flux.yaml").write_text(reglages, encoding="utf-8")
    return a


def lancer(a: "base.Atelier", nom: str, *args: str) -> str:
    env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(a.ws)}
    r = subprocess.run(["uv", "run", str(base.SCRIPT), *args], env=env, capture_output=True, text=True)
    erreurs = "\n".join(l for l in r.stderr.splitlines() if not l.startswith(("Installed ", "Resolved ", "Downloaded ", "Prepared ")))
    sortie = r.stdout + (f"[stderr]\n{erreurs}" if erreurs.strip() else "")      # sans le bruit de uv
    sortie = sortie.replace(str(a.ws), "<ws>")
    return f"## {nom} (exit {r.returncode})\n\n````\n{sortie.rstrip()}\n````\n"


def parcours(*extra: str) -> str:
    """Parcours complet dans la langue demandée (calculé une fois par jeu d'options)."""
    if extra in _CACHE:
        return _CACHE[extra]
    blocs: list[str] = []
    T = ["--today", base.AUJOURDHUI]
    with tempfile.TemporaryDirectory() as tmp:
        a = atelier(Path(tmp))
        base.construire(a)
        e = str(a.ecrire())
        blocs.append(lancer(a, "sample", e, *T, *extra))
        blocs.append(lancer(a, "--by-state", e, *T, "--by-state", *extra))
        blocs.append(lancer(a, "--starts, no project reaches the threshold", e, *T, "--starts", *extra))
        blocs.append(lancer(a, "--near-median beyond the candidates, --oldest, --by-state", e, *T, "--near-median", "100",
                            "--longest", "2", "--oldest", "10", "--by-state", *extra))
        blocs.append(lancer(a, "segment given by its English name", e, *T, "--segment", "review_verification", *extra))
        blocs.append(lancer(a, "--segment unknown", e, *T, "--segment", "whatever", *extra))
        blocs.append(lancer(a, "--scope without a match", e, *T, "--scope", "QQQ", *extra))
        blocs.append(lancer(a, "--starts outside the segment", e, *T, "--segment", "implementation", "--starts", *extra))
        a.ticket("HHH-1", "2026-05-01", base.REVUE, [("2026-05-02", "Open", base.REVUE)], resolu="2026-06-01", motif="Done")
        e = str(a.ecrire())
        blocs.append(lancer(a, "--longest 100, creation and resolution from the segment", e, *T, "--longest", "100", *extra))
        (a.ws / "Flux-Lab" / "flux.yaml").write_text(
            REGLAGES + "segments:\n  review_verification: ['Ready for Verification','Verification - Ongoing']\n  other: [Foo]\n",
            encoding="utf-8")
        blocs.append(lancer(a, "segments set in flux.yaml", e, *T, "--by-state", "--starts", *extra))
    with tempfile.TemporaryDirectory() as tmp:
        a = atelier(Path(tmp))
        a.ticket("RRR-1", "2026-03-01", "Done", [("2026-03-05", "Open", base.IMPL), ("2026-04-08", base.IMPL, "Done")],
                 resolu="2026-04-08", motif="Done")
        blocs.append(lancer(a, "nothing left the segment", str(a.ecrire()), *T, *extra))
        sans_resolu = a.ws / "Flux-Lab" / "exports" / "sans_resolu.csv"
        sans_resolu.write_text("Issue key,Issue Type,Summary,Status,Created\nAAA-1,Story,x,Open,01/Jan/2026 09:00\n", encoding="utf-8")
        blocs.append(lancer(a, "export without a Resolved column", str(sans_resolu), *T, *extra))
        sans_cle = a.ws / "Flux-Lab" / "exports" / "sans_cle.csv"
        sans_cle.write_text("Summary,Status,Created,Resolved\nx,Open,01/Jan/2026 09:00,\n", encoding="utf-8")
        blocs.append(lancer(a, "export without a key column", str(sans_cle), *T, *extra))
    with tempfile.TemporaryDirectory() as tmp:
        a = atelier(Path(tmp))
        a.ticket("RRR-1", "2026-03-01", "Done", [("2026-03-05", "Open", base.IMPL), ("2026-04-08", base.IMPL, "Done")],
                 resolu="2026-04-08", motif="Done")

        def passage(projet, i, jour):
            passe = D("2026-05-01") + dt.timedelta(days=jour - 1)
            a.ticket(f"{projet}-{i}", "2026-04-20", base.IMPL, [
                ("2026-05-01", "Open", base.REVUE), (passe.isoformat(), base.REVUE, "Verification - Ongoing"),
                ((passe + dt.timedelta(days=20)).isoformat(), "Verification - Ongoing", base.IMPL)])
        for i, j in enumerate([11] * 10 + [8] * 7 + [2, 3, 4, 5, 6, 7, 9, 12], 1):
            passage("PPP", i, j)
        for i in range(1, 31):
            passage("QQQ", i, i + 1)
        for i in range(1, 20):
            passage("SSS", i, 3)
        for i in range(1, 22):                                  # des clés sans projet (pas de tiret)
            passe = D("2026-05-01") + dt.timedelta(days=i % 9)
            a.ticket(f"SANSPROJET{i}", "2026-04-20", base.IMPL, [
                ("2026-05-01", "Open", base.REVUE), (passe.isoformat(), base.REVUE, "Verification - Ongoing"),
                ((passe + dt.timedelta(days=20)).isoformat(), "Verification - Ongoing", base.IMPL)])
        e = str(a.ecrire())
        blocs.append(lancer(a, "--starts by project", e, *T, "--starts", *extra))
        blocs.append(lancer(a, "--starts with a higher threshold", e, *T, "--starts", "--min-passes", "100", *extra))
    with tempfile.TemporaryDirectory() as tmp:
        a = atelier(Path(tmp))
        base.construire_lots(a)
        e = str(a.ecrire())
        blocs.append(lancer(a, "batch closures kept", e, *T, "--by-state", "--starts", "--min-passes", "1", *extra))
        blocs.append(lancer(a, "--exclude-batch-closures", e, *T, "--exclude-batch-closures", "--by-state", "--starts",
                            "--min-passes", "1", *extra))
    texte = "\n".join(["# segment_sample.py, test run\n"] + blocs)
    _CACHE[extra] = texte
    return texte


class Langue(unittest.TestCase):
    def test_catalogues_coherents(self):
        self.assertEqual(check_catalogs(CATALOGS), [])

    def test_sortie_anglaise_conforme_a_l_instantane(self):
        sortie = parcours("--language", "en")
        if os.environ.get("PMZILLA_UPDATE_SNAPSHOTS") == "1":
            REFERENCE_EN.write_text(sortie, encoding="utf-8")
        self.assertEqual(sortie, REFERENCE_EN.read_text(encoding="utf-8"))

    def test_pas_de_francais_dans_la_sortie_anglaise(self):
        for numero, ligne in enumerate(parcours("--language", "en").splitlines(), 1):
            self.assertIsNone(MOTS_FRANCAIS.search(ligne), f"ligne {numero} : {ligne}")

    def test_sans_option_la_sortie_est_francaise(self):
        defaut = parcours()
        self.assertIn("# Échantillon du segment « revue_verification »", defaut)
        self.assertIn("(création)", defaut)
        self.assertNotIn("# Sample of the segment", defaut)

    def test_language_fr_explicite_donne_la_sortie_par_defaut(self):
        self.assertEqual(parcours("--language", "fr"), parcours())

    def test_ancienne_option_langue_refusee(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = atelier(Path(tmp))
            base.construire(a)
            env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(a.ws)}
            r = subprocess.run(["uv", "run", str(base.SCRIPT), str(a.ecrire()), "--today", base.AUJOURDHUI,
                                "--langue", "en"], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("« --langue » n'existe plus ; utiliser « --language »", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_langue_inconnue_refusee(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = atelier(Path(tmp))
            base.construire(a)
            env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(a.ws)}
            r = subprocess.run(["uv", "run", str(base.SCRIPT), str(a.ecrire()), "--language", "de"],
                               env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_les_donnees_ne_changent_pas_de_langue(self):
        """Les chiffres, les clés et les états sont les mêmes ; seuls les textes changent."""
        chiffres = lambda t: re.findall(r"\b(?:CCC|BBB|AAA|FFF|GGG|DDD)-\d+\b", t)
        self.assertEqual(chiffres(parcours()), chiffres(parcours("--language", "en")))


if __name__ == "__main__":
    unittest.main()
