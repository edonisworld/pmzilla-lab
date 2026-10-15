"""
Tests de `library_parity.main` (enregistrement, comparaison, codes de sortie) sur une fausse recherche, sans base ni Ollama.

    bash tests/run_all.sh parity

La recherche, l'embedding et la lecture des livres sont injectés ; le dossier de données est toujours un dossier temporaire
(variable PMZILLA_LAB_DATA).
"""
import contextlib
import datetime as dt
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(RACINE / "tests" / "fixtures_library"))
import library_parity as lp          # noqa: E402
import demo_library as demo          # noqa: E402

COMMUNS = [f"livre-{i}.md" for i in range(8)]
AUTRES = [f"autre-{i}.md" for i in range(8)]
YAML = "queries:\n  - {id: q1, lang: fr, query: le flux}\n  - {id: q2, lang: en, query: flow}\n"


class Etat:
    """Ce que la fausse recherche rend et ce qu'elle a reçu."""

    def __init__(self, fichiers):
        self.fichiers, self.construits, self.appels = fichiers, [], []
        self.livres = [["a.md", "h1"], ["b.md", "h2"]]

    def fabrique(self, **options):
        etat = self
        etat.construits.append(options)

        class Voie:
            def search(self, query, collections, limit, since=None, types=None, component="hybrid"):
                etat.appels.append((query, collections, limit, component))
                return [{"file": f, "position": 0, "text": "texte inventé"} for f in etat.fichiers[:limit]]
        return Voie()


class Cadre(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        self.donnees = Path(self.dossier.name) / "donnees"
        self.requetes = Path(self.dossier.name) / "q.yaml"
        self.requetes.write_text(YAML, encoding="utf-8")
        self.instantane = self.donnees / lp.SNAPSHOT_NAME

    def lancer(self, etat, *args, livres=None, today=dt.date(2026, 10, 1), **injections):
        sortie = io.StringIO()
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_DATA": str(self.donnees)}), contextlib.redirect_stdout(sortie):
            code = lp.main([*args, "--queries", str(self.requetes)], factory=lambda **o: etat.fabrique(**o), embed=demo.fake_embed,
                           books_reader=lambda lib: livres if livres is not None else etat.livres, today=today, **injections)
        return code, sortie.getvalue()

    def enregistrer(self, fichiers=COMMUNS, *args, **options):
        etat = Etat(fichiers)
        code, texte = self.lancer(etat, "record", *args, **options)
        self.assertEqual(code, 0, texte)
        return etat


class Enregistrement(Cadre):
    def test_premier_enregistrement_un_fichier_prive_et_des_nombres(self):
        etat = Etat(COMMUNS)
        code, texte = self.lancer(etat, "record")
        self.assertEqual(code, 0)
        self.assertEqual(os.listdir(self.donnees), [lp.SNAPSHOT_NAME])
        self.assertEqual(stat.S_IMODE(self.instantane.stat().st_mode), 0o600)
        self.assertIn(str(self.instantane), texte)
        self.assertIn("2 requêtes", texte)
        self.assertIn("2 livres", texte)
        self.assertNotIn("livre-0.md", texte)
        self.assertNotIn("a.md", texte)

    def test_contenu_de_l_instantane(self):
        self.enregistrer(COMMUNS, "--limit", "5", "--scan", "exact", "--component", "text")
        data = json.loads(self.instantane.read_text(encoding="utf-8"))
        self.assertEqual(data["queries"]["q1"], [[f, 0] for f in COMMUNS[:5]])
        self.assertEqual(data["settings"], {"limit": 5, "scan": "exact", "ef_search": 400, "fulltext": "bm25", "rank_norm": None,
                                            "component": "text", "collections": None})
        self.assertEqual(data["freshness_date"], "2026-10-01")
        self.assertEqual(data["books"], [["a.md", "h1"], ["b.md", "h2"]])
        self.assertEqual(data["queries_fingerprint"], lp.queries_fingerprint(lp.load_queries(self.requetes)))
        self.assertNotIn("texte inventé", self.instantane.read_text(encoding="utf-8"))
        self.assertNotIn("title", data["books"][0])

    def test_composante_par_defaut_sans_parametre_a_l_enregistrement(self):
        etat = self.enregistrer()
        self.assertEqual({a[3] for a in etat.appels}, {"hybrid"})
        self.assertEqual(etat.construits[0]["today"], dt.date(2026, 10, 1))

    def test_instantane_existant_refuse_sans_remplacer(self):
        self.enregistrer()
        avant = self.instantane.read_bytes()
        etat = Etat(AUTRES)
        code, texte = self.lancer(etat, "record")
        self.assertEqual(code, 2)
        self.assertIn("snapshot exists", texte)
        self.assertEqual(self.instantane.read_bytes(), avant)
        self.assertEqual(etat.construits, [])

    def test_remplacement(self):
        self.enregistrer()
        etat = Etat(AUTRES)
        code, _ = self.lancer(etat, "record", "--replace")
        self.assertEqual(code, 0)
        data = json.loads(self.instantane.read_text(encoding="utf-8"))
        self.assertEqual(data["queries"]["q1"][0][0], "autre-0.md")
        self.assertEqual(stat.S_IMODE(self.instantane.stat().st_mode), 0o600)
        self.assertEqual(os.listdir(self.donnees), [lp.SNAPSHOT_NAME])

    def test_base_injoignable_code_2_sans_fichier(self):
        def casse(**options):
            raise ConnectionError("secret")
        sortie = io.StringIO()
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_DATA": str(self.donnees)}), contextlib.redirect_stdout(sortie):
            code = lp.main(["record", "--queries", str(self.requetes)], factory=casse, embed=demo.fake_embed)
        self.assertEqual(code, 2)
        self.assertNotIn("secret", sortie.getvalue())
        self.assertFalse(self.instantane.exists())


class CodeDeSortie(Cadre):
    def test_parite_atteinte_code_0(self):
        self.enregistrer()
        code, texte = self.lancer(Etat(COMMUNS))
        self.assertEqual(code, 0)
        self.assertNotIn("PARITÉ NON ATTEINTE", texte)

    def test_parite_non_atteinte_code_1(self):
        self.enregistrer()
        code, texte = self.lancer(Etat(AUTRES))
        self.assertEqual(code, 1)
        self.assertIn("PARITÉ NON ATTEINTE", texte)

    def test_comparaison_reprend_reglages_et_date_de_l_instantane(self):
        self.enregistrer(COMMUNS, "--limit", "5", "--scan", "exact", "--component", "vector")
        etat = Etat(COMMUNS)
        code, _ = self.lancer(etat, today=dt.date(2030, 1, 1))
        self.assertEqual(code, 0)
        self.assertEqual(etat.construits[0]["scan"], "exact")
        self.assertEqual(etat.construits[0]["today"], dt.date(2026, 10, 1))
        self.assertEqual({(a[2], a[3]) for a in etat.appels}, {(5, "vector")})

    def test_option_identique_aux_reglages_acceptee(self):
        self.enregistrer(COMMUNS, "--scan", "exact")
        code, _ = self.lancer(Etat(COMMUNS), "--scan", "exact")
        self.assertEqual(code, 0)

    def test_aucun_fichier_ecrit_a_la_comparaison(self):
        self.enregistrer()
        avant = self.instantane.read_bytes()
        self.lancer(Etat(AUTRES), "--details")
        self.assertEqual(os.listdir(self.donnees), [lp.SNAPSHOT_NAME])
        self.assertEqual(self.instantane.read_bytes(), avant)

    def test_base_injoignable_code_2(self):
        self.enregistrer()
        def casse(**options):
            raise ConnectionError("secret")
        sortie = io.StringIO()
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_DATA": str(self.donnees)}), contextlib.redirect_stdout(sortie):
            code = lp.main(["--queries", str(self.requetes)], factory=casse, embed=demo.fake_embed)
        self.assertEqual(code, 2)
        self.assertNotIn("secret", sortie.getvalue())


class Refus(Cadre):
    def test_sans_instantane_code_2_avant_toute_requete(self):
        etat = Etat(COMMUNS)
        code, texte = self.lancer(etat)
        self.assertEqual(code, 2)
        self.assertIn("no snapshot: run library_parity.py record first", texte)
        self.assertEqual((etat.construits, etat.appels), ([], []))

    def test_jeu_de_requetes_change_code_2_avant_toute_requete(self):
        self.enregistrer()
        self.requetes.write_text(YAML + "  - {id: q3, lang: fr, query: autre}\n", encoding="utf-8")
        etat = Etat(COMMUNS)
        code, texte = self.lancer(etat)
        self.assertEqual(code, 2)
        self.assertIn("query set changed since the snapshot", texte)
        self.assertEqual((etat.construits, etat.appels), ([], []))

    def test_option_differente_code_2_avant_toute_requete(self):
        self.enregistrer(COMMUNS, "--scan", "ann")
        for option in (("--scan", "exact"), ("--limit", "4"), ("--component", "text"), ("--collections", "watch"), ("--fulltext", "tsvector")):
            with self.subTest(option=option):
                etat = Etat(COMMUNS)
                code, texte = self.lancer(etat, *option)
                self.assertEqual(code, 2)
                self.assertIn("settings differ from the snapshot", texte)
                self.assertEqual((etat.construits, etat.appels), ([], []))


class Livres(Cadre):
    def test_comptes_ajoutes_retires_modifies_sans_noms(self):
        self.enregistrer()
        livres = [["a.md", "autre"], ["c.md", "h3"], ["d.md", "h4"], ["e.md", "h5"]]      # a modifié, b retiré, c d e ajoutés
        code, texte = self.lancer(Etat(COMMUNS), livres=livres)
        self.assertEqual(code, 0)
        self.assertIn("3 livres ajoutés · 1 retirés · 1 modifiés", texte)
        for nom in ("a.md", "c.md", "b.md"):
            self.assertNotIn(nom, texte)

    def test_details_liste_fichier_position_sans_texte(self):
        self.enregistrer()
        code, texte = self.lancer(Etat(AUTRES), "--details")
        self.assertEqual(code, 1)
        self.assertIn("seulement dans l'instantané : livre-0.md:0", texte)
        self.assertIn("seulement maintenant : autre-0.md:0", texte)
        self.assertNotIn("texte inventé", texte)


if __name__ == "__main__":
    unittest.main()
