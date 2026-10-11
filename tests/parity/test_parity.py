"""
Tests de tools/library_parity.py et du jeu figé tests/parity/queries.yaml, sur deux faux backends (aucune base, aucun Ollama).

    bash tests/run_all.sh parity
"""
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import library_parity as lp  # noqa: E402
import yaml                  # noqa: E402
import identifiants_personnels  # noqa: E402

REQUETES = RACINE / "tests" / "parity" / "queries.yaml"


class Faux:
    """Faux backend : rend toujours les mêmes résultats (fichier, position) pour toute question."""

    def __init__(self, resultats):
        self.resultats, self.appels = resultats, []

    def search(self, query, collections, limit, since=None, types=None):
        self.appels.append((query, collections, types))
        return [{"file": f, "position": p, "text": "texte secret"} for f, p in self.resultats[:limit]]


def jeu(n=8):
    return [("livre-%d.md" % i, i) for i in range(n)]


def requetes(*items):
    return [{"id": i, "lang": "fr", "query": f"question {i}", **extra} for i, extra in items]


class Mesure(unittest.TestCase):
    def mesurer(self, a, b, items, **options):
        rapport = lp.run_parity(items, Faux(a), Faux(b), **options)
        return rapport, lp.verdict(rapport)

    def test_recouvrement_8_sur_8_4_sur_8_0_sur_8(self):
        for communs in (8, 4, 0):
            with self.subTest(communs=communs):
                b = jeu(communs) + [("autre-%d.md" % i, i) for i in range(8 - communs)]
                rapport, _ = self.mesurer(jeu(), b, requetes(("q1", {})))
                self.assertEqual(rapport["rows"][0]["common"], communs)

    def test_moyenne_minimum_et_pire_requete(self):
        a = jeu()

        class Variable(Faux):
            def search(self, query, collections, limit, since=None, types=None):
                communs = {"q1": 8, "q2": 4, "q3": 0}[query.split()[-1]]
                return [{"file": f, "position": p} for f, p in (jeu(communs) + [("x-%d.md" % i, i) for i in range(8 - communs)])]
        rapport = lp.run_parity(requetes(("q1", {}), ("q2", {}), ("q3", {})), Faux(a), Variable([]))
        resultat = lp.verdict(rapport, threshold=0.5)
        self.assertAlmostEqual(resultat["mean"], (1 + 0.5 + 0) / 3)
        self.assertEqual(resultat["min"], 0.0)
        self.assertEqual(resultat["worst"], "q3")
        self.assertEqual(resultat["below"], ["q3"])
        self.assertFalse(resultat["ok"])

    def test_verdict_parite(self):
        _, ok = self.mesurer(jeu(), jeu(), requetes(("q1", {}), ("q2", {})))
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["mean"], 1.0)

    def test_seuil_de_la_moyenne(self):
        b = jeu(7) + [("autre.md", 1)]          # 7 sur 8 partout : moyenne 0,875
        _, ok = self.mesurer(jeu(), b, requetes(("q1", {}), ("q2", {})))
        self.assertTrue(ok["ok"])
        rapport = lp.run_parity(requetes(("q1", {})), Faux(jeu()), Faux(jeu(6) + [("a.md", 1), ("b.md", 2)]))
        self.assertFalse(lp.verdict(rapport)["ok"])                       # 0,75 < 0,85
        self.assertTrue(lp.verdict(rapport, threshold=0.7)["ok"])         # --threshold

    def test_requete_rare_exige_7_sur_8(self):
        b = jeu(6) + [("a.md", 1), ("b.md", 2)]
        _, banal = self.mesurer(jeu(), b, requetes(("q1", {})) , )
        rapport = lp.run_parity(requetes(("q1", {"rare": True})), Faux(jeu()), Faux(b))
        resultat = lp.verdict(rapport, threshold=0.5)
        self.assertEqual(resultat["rare_bad"], ["q1"])
        self.assertFalse(resultat["ok"])

    def test_limite_et_filtres_transmis(self):
        a, b = Faux(jeu(10)), Faux(jeu(10))
        items = requetes(("q1", {"collections": ["watch"], "types": ["figure"]}))
        lp.run_parity(items, a, b, limit=5)
        self.assertEqual(a.appels, b.appels)
        self.assertEqual(a.appels[0][1:], (["watch"], ["figure"]))
        lp.run_parity(items, a, b, collections=["flow"])
        self.assertEqual(a.appels[-1][1], ["flow"])
        rapport = lp.run_parity(items, a, b, limit=5)
        self.assertEqual(rapport["rows"][0]["common"], 5)

    def test_embedding_calcule_avant_la_mesure_de_latence(self):
        vus = []
        lp.run_parity(requetes(("q1", {})), Faux(jeu()), Faux(jeu()), warm=vus.append)
        self.assertEqual(vus, ["question q1"])

    def test_latences(self):
        temps = iter([0.0, 0.010, 0.010, 0.050, 0.050, 0.060, 0.060, 0.200])
        rapport = lp.run_parity(requetes(("q1", {}), ("q2", {})), Faux(jeu()), Faux(jeu()), clock=lambda: next(temps))
        self.assertEqual([round(x, 3) for x in rapport["latency"]["sqlite"]], [0.01, 0.01])
        self.assertEqual([round(x, 3) for x in rapport["latency"]["postgres"]], [0.04, 0.14])
        self.assertAlmostEqual(lp.p95(rapport["latency"]["postgres"]), 0.14)


class Composante(unittest.TestCase):
    def test_composante_transmise_aux_deux_voies_sauf_hybride(self):
        vus = []

        class Espion(Faux):
            def search(self, query, collections, limit, since=None, types=None, component="hybrid"):
                vus.append((query, component))
                return super().search(query, collections, limit, since, types)
        lp.run_parity(requetes(("q1", {})), Espion(jeu()), Espion(jeu()), component="vector")
        self.assertEqual(vus, [("question q1", "vector"), ("question q1", "vector")])
        a2, b2 = Faux(jeu()), Faux(jeu())
        lp.run_parity(requetes(("q1", {})), a2, b2)                     # hybride : les faux backends sans paramètre fonctionnent
        self.assertEqual(len(a2.appels), 1)

    def test_resume_par_defaut_et_verdict_par_requete(self):
        rapport = lp.run_parity(requetes(("q1", {}), ("q2", {})), Faux(jeu()), Faux(jeu()),
                                clock=iter([0.0, 0.010, 0.010, 0.050, 0.050, 0.060, 0.060, 0.200]).__next__)
        rapport["component"] = "text"
        rapport["rows"][1]["common"] = 0      # q1 identique, q2 : rien en commun
        texte = lp.render(rapport, lp.verdict(rapport))
        self.assertIn("plein texte seul", texte)
        lignes = {l.split()[0]: l for l in texte.splitlines() if l.startswith(("q1", "q2"))}
        self.assertIn("ok", lignes["q1"])
        self.assertIn("écart", lignes["q2"])
        self.assertIn("10 ms", lignes["q1"])
        self.assertIn("40 ms", lignes["q1"])


class Plan(unittest.TestCase):
    PLAN = ("Limit  (cost=1.00..2.00 rows=8 width=16) (actual time=480.1..480.2 rows=8 loops=1)\n"
            "  CTE sem\n"
            "    ->  Seq Scan on chunks c  (cost=0.00..90.00 rows=25000 width=8) (actual time=0.1..210.5 rows=25000 loops=1)\n"
            "          Filter: (kind = ANY ('{text}'::text[]))\n"
            "  CTE kw\n"
            "    ->  Custom Scan (ParadeDB Scan) on chunks c_1  (actual time=3.1..3.2 rows=200 loops=1)\n"
            "          Index Cond: (fts_text ||| 'équipe de la production'::text)\n"
            "          Filter: (b.published_on >= '2026-01-01'::text)\n"
            "  InitPlan: embedding [0.12345678,-0.2,0.0001,0.5,0.25,0.1,0.3,0.7,0.9,0.11,0.13,0.17]\n"
            "Planning Time: 0.5 ms\nExecution Time: 481.0 ms")

    def test_plan_sans_litteral_ni_vecteur(self):
        texte = lp.redact_plan(self.PLAN)
        for valeur in ("équipe", "2026-01-01", "0.12345678", "{text}"):
            self.assertNotIn(valeur, texte)
        self.assertIn("Custom Scan (ParadeDB Scan)", texte)          # les nœuds, les index, les nombres de lignes et les temps restent
        self.assertIn("rows=25000", texte)
        self.assertIn("Execution Time: 481.0 ms", texte)

    def test_explain_utilise_explain_analyze_et_annule_la_transaction(self):
        class Curseur:
            def __init__(self):
                self.ordres = []

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, ordre, params=None):
                self.ordres.append((ordre, params))

            def fetchall(self):
                return [(ligne,) for ligne in TestPlan.PLAN.split("\n")]

        class Connexion:
            def __init__(self):
                self.curseur, self.annulee = Curseur(), 0

            def cursor(self):
                return self.curseur

            def rollback(self):
                self.annulee += 1

        TestPlan = self
        connexion = Connexion()
        texte = lp.explain_query(connexion, "SELECT 1", {"x": "valeur-secrete"}, setup=("SET LOCAL hnsw.ef_search = 100",))
        self.assertEqual(connexion.curseur.ordres[0][0], "SET LOCAL hnsw.ef_search = 100")
        self.assertEqual(connexion.curseur.ordres[1], ("EXPLAIN (ANALYZE, BUFFERS) SELECT 1", {"x": "valeur-secrete"}))
        self.assertEqual(connexion.annulee, 1)
        self.assertNotIn("valeur-secrete", texte)

    def test_option_explain_de_la_ligne_de_commande(self):
        with mock.patch.object(lp, "MIGRATIONS", Path(tempfile.mkdtemp())):
            sortie = io.StringIO()
            with contextlib.redirect_stdout(sortie):
                code = lp.main(["--fulltext", "bm25", "--explain", "q1"])
        self.assertEqual(code, 2)                                   # sans la 0005, refus avant toute connexion


class GroupeRestreint(unittest.TestCase):
    """Les requêtes restreintes par collection sont rapportées à part (change filter-before-keyword-limit), sans quitter le verdict global."""

    def rapport(self, items, **options):
        rapport = lp.run_parity(requetes(*items), Faux(jeu()), Faux(jeu()), **options)
        return rapport

    def test_jeu_mixte_une_moyenne_par_groupe_en_plus_du_verdict_global(self):
        rapport = self.rapport([("libre1", {}), ("libre2", {}), ("restreinte", {"collections": ["watch"]})])
        rapport["rows"][2]["common"] = 0              # la restreinte ne recouvre rien, les libres tout
        self.assertEqual([r["restricted"] for r in rapport["rows"]], [False, False, True])
        resultat = lp.verdict(rapport)
        texte = lp.render(rapport, resultat)
        self.assertIn("Requêtes restreintes par collection (écart possible par construction) : 1 · recouvrement moyen 0.000 · minimum 0.000", texte)
        self.assertIn("Requêtes sans restriction : 2 · recouvrement moyen 1.000 · minimum 1.000", texte)
        self.assertIn("Recouvrement moyen : 0.667", texte)                       # le global inclut toujours les restreintes
        self.assertIn("PARITÉ NON ATTEINTE", texte)
        self.assertFalse(resultat["ok"])

    def test_option_globale_toutes_les_requetes_dans_le_groupe_restreint(self):
        rapport = self.rapport([("q1", {}), ("q2", {})], collections=["watch"])
        self.assertTrue(all(r["restricted"] for r in rapport["rows"]))
        texte = lp.render(rapport, lp.verdict(rapport))
        self.assertIn("Requêtes restreintes par collection (écart possible par construction) : 2", texte)
        self.assertNotIn("Requêtes sans restriction", texte)

    def test_aucune_requete_restreinte_aucun_groupe_et_verdict_inchange(self):
        rapport = self.rapport([("q1", {}), ("q2", {})])
        resultat = lp.verdict(rapport)
        texte = lp.render(rapport, resultat)
        self.assertNotIn("restreintes", texte)
        self.assertNotIn("sans restriction", texte)
        self.assertTrue(resultat["ok"])
        self.assertIn("Verdict : PARITÉ au seuil retenu", texte)

    def test_le_groupe_ne_contient_que_des_identifiants_et_des_nombres(self):
        rapport = self.rapport([("restreinte", {"collections": ["watch"]})])
        self.assertNotIn("texte secret", lp.render(rapport, lp.verdict(rapport), details=True))


class EfSearch(unittest.TestCase):
    def test_option_ef_search(self):
        self.assertEqual(lp.build_parser().parse_args([]).ef_search, 400)
        self.assertEqual(lp.build_parser().parse_args([]).scan, "ann")
        self.assertEqual(lp.build_parser().parse_args(["--ef-search", "400"]).ef_search, 400)

    def test_ef_search_hors_bornes_refuse(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            lp.main(["--ef-search", "1001"])


class Rapport(unittest.TestCase):
    def test_rapport_sans_texte_ni_titre(self):
        rapport = lp.run_parity(requetes(("q1", {})), Faux(jeu()), Faux(jeu(2) + [("seul-postgres.md", 9)] * 0))
        texte = lp.render(rapport, lp.verdict(rapport))
        self.assertNotIn("texte secret", texte)
        self.assertNotIn("livre-2.md", texte)                 # résumé par défaut : aucun nom de fichier
        detail = lp.render(rapport, lp.verdict(rapport), details=True)
        self.assertNotIn("texte secret", detail)
        self.assertIn("seulement SQLite : livre-2.md:2", detail)      # les noms de fichiers seulement avec --details
        self.assertIn("PARITÉ NON ATTEINTE", texte)
        self.assertIn("Latence sqlite", texte)
        self.assertIn("Latence postgres", texte)

    def test_aucun_fichier_ecrit(self):
        with tempfile.TemporaryDirectory() as dossier:
            courant = os.getcwd()
            os.chdir(dossier)
            try:
                rapport = lp.run_parity(requetes(("q1", {})), Faux(jeu()), Faux(jeu()))
                lp.render(rapport, lp.verdict(rapport))
                self.assertEqual(os.listdir(dossier), [])
            finally:
                os.chdir(courant)

    def test_bm25_non_disponible_tant_que_la_migration_manque(self):
        sortie = io.StringIO()
        with tempfile.TemporaryDirectory() as vide, mock.patch.object(lp, "MIGRATIONS", Path(vide)):       # un dépôt sans la 0005
            with contextlib.redirect_stdout(sortie):
                code = lp.main(["--fulltext", "bm25"])
        self.assertEqual(code, 2)
        self.assertIn("migration 0005 absente", sortie.getvalue())
        self.assertTrue(list((RACINE / "db" / "migrations").glob("0005_*.sql")))      # le dépôt, lui, l'a

    def test_jeu_de_requetes_invalide_refuse(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "q.yaml"
            for contenu in ("queries: []", "pas: une liste", "queries:\n  - {id: a, lang: fr, query: ''}",
                            "queries:\n  - {id: a, lang: de, query: x}",
                            "queries:\n  - {id: a, lang: fr, query: x}\n  - {id: a, lang: en, query: y}",
                            "queries:\n  - {id: a, lang: fr, query: x, bidon: 1}"):
                chemin.write_text(contenu, encoding="utf-8")
                with self.subTest(contenu=contenu[:30]):
                    with self.assertRaises(lp.ParityError):
                        lp.load_queries(chemin)


class JeuFige(unittest.TestCase):
    def setUp(self):
        self.items = lp.load_queries(REQUETES)

    def test_valide_et_assez_grand(self):
        self.assertGreaterEqual(len(self.items), 35)
        self.assertEqual(len({i["id"] for i in self.items}), len(self.items))

    def test_francais_et_anglais_presents(self):
        langues = {i["lang"] for i in self.items}
        self.assertEqual(langues, {"fr", "en"})
        for langue in ("fr", "en"):
            self.assertGreaterEqual(sum(1 for i in self.items if i["lang"] == langue), 15)

    def test_formulations_courtes_sans_extrait_ni_nom(self):
        for item in self.items:
            self.assertLessEqual(len(item["query"]), 120, item["id"])
            self.assertLessEqual(len(item["query"].split()), 14, item["id"])      # une formulation, jamais une phrase recopiée
            self.assertNotIn("\n", item["query"])
        texte = REQUETES.read_text(encoding="utf-8")
        self.assertNotRegex(texte, r"https?://")
        self.assertNotRegex(texte, r"[A-Z]{2,5}-\d+")      # pas de clé de ticket
        for interdit in ("Alpha", "Beta", "Quantelis", "Jira"):
            self.assertNotIn(interdit, texte)
        for identifiant in identifiants_personnels.identifiants(RACINE):
            self.assertFalse(identifiant in texte.lower(), "queries.yaml contient un identifiant personnel")

    def test_types_et_collections_valides(self):
        for item in self.items:
            self.assertLessEqual(set(item.get("types", [])), {"texte", "figure"}, item["id"])
            self.assertIsInstance(item.get("collections", []), list, item["id"])
        self.assertTrue(any(i.get("rare") for i in self.items))
        self.assertTrue(any(i.get("types") for i in self.items))

    def test_fichier_yaml_lisible_tel_quel(self):
        self.assertIsInstance(yaml.safe_load(REQUETES.read_text(encoding="utf-8")), dict)


if __name__ == "__main__":
    unittest.main()
