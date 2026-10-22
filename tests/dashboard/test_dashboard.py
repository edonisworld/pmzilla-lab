"""
Tests du tableau de bord (tools/dashboard.py) sur des données fictives.

    uv run --with pyyaml python -m unittest discover -s tests/dashboard -v

Trois vérifications : la page se génère avec toutes les sources, puis sans aucune, puis avec des sources
illisibles ; dans tous les cas elle ne contient aucun extrait d'article ni de livre, aucun JavaScript
et aucune adresse réseau.

La section bibliothèque lit le schéma knowledge de la base par un lecteur injecté : la page est générée par
run_with_fake_library.py (faux lecteur décrit par un fichier JSON, jamais de vraie base). La classe sur base
jetable est dans test_dashboard_db.py.
"""
import contextlib
import datetime
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "dashboard.py"
RUNNER = Path(__file__).resolve().parent / "run_with_fake_library.py"   # dashboard.py avec le faux lecteur de la bibliothèque
SECTIONS = ["sante", "a-faire", "experimentations", "veille", "bibliotheque", "qualite", "flux", "critic", "composants"]
# textes qui ne doivent jamais se retrouver dans la page
SENTINELLES = ["SENTINELLE_ARTICLE_TEXTE", "SENTINELLE_LIVRE_TEXTE", "SENTINELLE_PASSAGE_ARTICLE",
               "SENTINELLE_PASSAGE_LIVRE", "SENTINELLE_TITRE_ARTICLE"]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rapport(date: str, heure: str, commit: str, ok: int, regression: str, cas: dict, total: int = 6,
            modeles: tuple[str, str] | None = None, non_validant: bool = False) -> str:
    lines = [f"# Jeu d'essai des postures, {date}-{heure}", ""]
    if modeles:
        lines += [f"modèles : sessions {modeles[0]} · juge {modeles[1]}", ""]
    if non_validant:
        lines += [f"**Passage non validant** : le modèle des séances ({modeles[0]}) diffère du modèle habituel.", ""]
    lines += [f"{ok}/{total} vérifications réussies sur 3 cas. État testé : {commit}. Traces brutes : /x.", ""]
    if regression:
        lines += ["## Régressions (réussies au passage précédent)", "", f"- **{regression}** : un critère", ""]
    lines += ["## Synthèse", "", "| Cas | Réussies | Posture | Coût | Tours |", "|---|---|---|---|---|"]
    lines += [f"| {name} | {r} | Delivery | {cost} $ | 3 |" for name, (r, cost) in cas.items()]
    lines += ["", "## discovery-cadrage", "", "> question", ""]
    return "\n".join(lines) + "\n"


def donnees_completes(root: Path) -> dict:
    ws, data, logs = root / "workspace", root / "data", root / "logs"
    write(ws / "Journal-Lab" / "journal.yaml", """
- id: J-1
  date: '2026-10-01'
  type: rétro
  perimetre: équipe Alpha
  suites:
  - {id: J-1.s1, quoi: Décrire la règle, pour: PO, echeance: '2026-10-05', statut: ouverte, note: ''}
  - {id: J-1.s2, quoi: Partager la frise, pour: Scrum Master, echeance: '2026-10-15', statut: ouverte, note: ''}
  experience: {hypothese: Nommer la décision la débloque, signal: latence, bilan_le: '2026-10-10', statut: en cours, resultat: ''}
""")
    write(ws / "watch" / "tri.yaml", "mode: filtre\n")
    write(ws / "_bmad-output" / "essais" / "essai-2026-10-10-100000.md",
          rapport("2026-10-10", "100000", "aaaaaaa1", 5, "", {"cas-un": ("3/3", "0.10"), "cas-deux": ("2/3", "0.20")}))
    write(ws / "_bmad-output" / "essais" / "essai-2026-10-11-100000.md",
          rapport("2026-10-11", "100000", "bbbbbbb2", 6, "cas-un", {"cas-un": ("3/3", "0.15"), "cas-deux": ("3/3", "0.25")},
                  modeles=("défaut", "défaut")))
    write(ws / "_bmad-output" / "essais" / "essai-2026-10-11-150000.md",   # passage non validant : hors de la courbe
          rapport("2026-10-11", "150000", "bbbbbbb2", 4, "", {"cas-un": ("2/3", "0.30"), "cas-deux": ("2/3", "0.30")},
                  modeles=("sonnet", "défaut"), non_validant=True))
    write(ws / "_bmad-output" / "essais" / "essai-2026-10-09-100000.md",   # passage partiel (4 vérifications au lieu de 6)
          rapport("2026-10-09", "100000", "ccccccc3", 3, "", {"cas-un": ("3/3", "0.05")}, total=4))
    write(ws / "_bmad-output" / "pmzilla" / "veille" / "synthese-2026-10-05.md", "# Synthèse\n")
    write(ws / "_bmad-output" / "pmzilla" / "miroir" / "miroir-2026-10.md",
          "# Miroir de Critic, du 2026-09-01 au 2026-10-05 : 12 objections\n\n## Les angles morts\n\nHypothèse prise pour un fait (2 livrables).\n\n## L'évolution\n\nrien\n")
    # le tableau de bord lit la date du miroir dans la date de modification du fichier : la fixer, sinon elle suit le jour d'exécution
    miroir_date = datetime.datetime(2026, 10, 7, 12, 0).timestamp()
    os.utime(ws / "_bmad-output" / "pmzilla" / "miroir" / "miroir-2026-10.md", (miroir_date, miroir_date))
    write(ws / "Flux-Lab" / "rapports" / "evolution-equipe-x-2026-10-10.md",
          "# Évolution\n\n## Ce qui a bougé\n\n- Débit : -30 %\n- WIP : +20 %\n\n## Débit\n\ndétail\n")
    write(ws / "tools" / "mapping_lab.py",
          "MAPPING = {\n    # À re-télécharger d'une autre source :\n    #   Livre Fictif A (Auteur Fictif) F ; Livre Fictif B (Autre Fictif) D ; The Fictive C et The Fictive D (Duo Fictif) F.\n    #   Livre Fictif E (Écrivain Fictif), le livre complet : DO (le fichier actuel est un résumé).\n\n    'x': 'F',\n}\n")
    write(ws / "_bmad-output" / "pmzilla" / "2026-10-10-diagnostic.md",
          "# Diagnostic\n\n## Ce que Critic conteste\n\n1. Première objection.\n2. Seconde objection.\n")
    write(ws / "Watch-Lab" / "watch" / "article.md", "SENTINELLE_ARTICLE_TEXTE")
    write(ws / "Bibliotheque-Lab" / "produit" / "livre.md", "SENTINELLE_LIVRE_TEXTE")
    write(logs / "pmzilla-watch.log", """=== 2026-10-10 07:10 ===
source-a.example : 2 nouveaux
source-b.example : ERREUR Client error '403 Forbidden'
2026-10-10T07:10:35 · 2 nouveaux articles · 1 sources en erreur
[1/1] SENTINELLE_TITRE_ARTICLE · substance 2/5 · 120 s
Partages : 100 liens lus sur Bluesky · 1 nouveaux articles de la veille partagés (4 au total)
50 articles sur la période · 5 à lire · 3 seraient écartés · /x/_a-lire.md
=== 2026-10-11 07:10 ===
source-a.example : 0 nouveaux
source-b.example : ERREUR Client error '403 Forbidden'
[1/1] SENTINELLE_TITRE_ARTICLE · substance 3/5 · 90 s
=== 2026-10-12 07:10 ===
source-a.example : 0 nouveaux
source-b.example : ERREUR Client error '403 Forbidden'
Ollama ne répond pas : pré-tri et indexation reportés au prochain passage
""")
    data.mkdir(parents=True)
    rows = [(1, "a.md", "Livre Avec Auteur", "produit", {"author": "Auteur Un"}),
            (2, "b.md", "Livre Sans Auteur", "flow|tech", {"author": "b.pdf (auteur non indiqué)"}),
            (3, "c.md", "SENTINELLE_TITRE_ARTICLE", "watch", {"author": "site.example (auteur non indiqué)"}),
            (4, "d.md", "Autre article", "watch", {})]
    # le même contenu pour le faux lecteur de la base : section bibliothèque, comptes de la veille, partages et sélections
    fake = root / "fake-library.json"
    write_fake(fake, [{"title": title, "author": meta.get("author"), "collections": coll.split("|"), "passages": 1}
                      for _, _, title, coll, meta in rows],
               watch_counts={"articles": 2, "passages": 2},
               shares={"total": 2, "recent": 2, "first_pick": "2026-10-08", "evaluable": 2, "hits": 1})
    return {"PMZILLA_LAB_WORKSPACE": str(ws), "PMZILLA_LAB_DATA": str(data), "PMZILLA_LAB_LOGS": str(logs),
            "PMZILLA_TEST_FAKE_LIBRARY": str(fake)}


def write_fake(path: Path, books: list[dict] | None = None, error: str | None = None, **extra) -> None:
    """Décrit le faux lecteur ; les comptes de la veille et les partages déjà écrits sont gardés quand on ne les redonne pas."""
    if error:
        write(path, json.dumps({"raise": error}))
        return
    ancien = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    garde = {k: v for k, v in ancien.items() if k in ("watch_counts", "shares")}
    write(path, json.dumps({"books": books or [], **garde, **extra}))


def read_fake(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["books"]


def without_cases_variables(environ) -> dict:
    """Sans l'auteur ni la base des cas de l'utilisateur : la septième section est « pas encore de données », sans connexion.
    Sans faux lecteur hérité non plus : la bibliothèque est vide sauf si le test en décrit une."""
    return {k: v for k, v in environ.items()
            if k not in ("PMZILLA_LAB_CASES_AUTHOR", "PMZILLA_LAB_CASES_DBNAME", "PMZILLA_TEST_FAKE_LIBRARY")}


def generer(root: Path, env_dirs: dict) -> tuple[subprocess.CompletedProcess, str]:
    sortie = root / "page.html"
    env = {**without_cases_variables(os.environ), **env_dirs, "PMZILLA_LAB_TODAY": "2026-10-12"}
    result = subprocess.run([sys.executable, str(RUNNER), "--output", str(sortie)], capture_output=True, text=True, env=env, timeout=120)
    return result, sortie.read_text(encoding="utf-8") if sortie.exists() else ""


class TableauDeBord(unittest.TestCase):
    def verifier_commun(self, page: str) -> None:
        for key in SECTIONS:
            self.assertIn(f'<section id="{key}">', page)
        for sentinelle in SENTINELLES:
            self.assertNotIn(sentinelle, page, "la page contient un extrait d'article ou de livre")
        self.assertNotIn("<script", page)
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)
        self.assertNotIn("—", page, "tiret cadratin")
        self.assertIn("prefers-color-scheme:dark", page)

    def test_anciennes_options_refusees_avec_le_nom_actuel(self):
        with tempfile.TemporaryDirectory() as tmp:
            sortie = Path(tmp) / "ancien.html"
            env = {**without_cases_variables(os.environ), **donnees_completes(Path(tmp)), "PMZILLA_LAB_TODAY": "2026-10-12"}
            r = subprocess.run([sys.executable, str(RUNNER), "--sortie", str(sortie)], capture_output=True, text=True,
                               env=env, timeout=120)
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertFalse(sortie.exists())
            self.assertIn("« --sortie » n'existe plus ; utiliser « --output »", r.stderr)

    def test_avec_toutes_les_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, page = generer(Path(tmp), donnees_completes(Path(tmp)))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.verifier_commun(page)
            self.assertIn("Suites en retard (1)", page)            # échéance du 05/10, aujourd'hui le 12/10
            self.assertIn("Suites à venir dans les 7 jours (1)", page)   # celle du 15/10, à 3 jours
            self.assertIn("Expériences dont le bilan est dû (1)", page)
            self.assertIn("filtre", page)                          # mode du pré-tri
            self.assertIn("source-b.example", page)                # source en erreur
            self.assertIn("3 jours consécutifs", page)
            self.assertIn("Livre Sans Auteur", page)               # livre sans auteur listé
            self.assertNotIn("Livre Avec Auteur</li>", page)
            self.assertIn("<li>Livre Fictif A (Auteur Fictif)</li>", page)   # livres à re-télécharger, un par ligne
            self.assertIn("<li>The Fictive D (Duo Fictif)</li>", page)
            self.assertIn("<li>Livre Fictif E (Écrivain Fictif)</li>", page)
            self.assertIn("à re-télécharger (5)", page)            # total
            self.assertNotIn("Auteur) F", page)                    # pas de code de domaine
            self.assertNotIn("le livre complet", page)             # pas de phrase d'explication
            self.assertIn("<b>1</b> sans auteur ni site", page)    # articles de veille : sans rien
            self.assertIn("<b>1</b> affichés", page)               # et avec « (auteur non indiqué) »
            self.assertIn("2 passages avec au moins un article pré-trié", page)   # le passage sans pré-tri n'est pas tracé
            self.assertIn(">10/10<", page)                         # date JJ/MM sous chaque barre
            self.assertIn(">5/6<", page)                           # score sous chaque point de la courbe
            self.assertIn("(du 01/10/2026 au 12/10/2026) : <b>2</b>", page)   # objections du mois en cours
            self.assertIn("5/6", page)
            self.assertIn("6/6", page)
            self.assertIn("bbbbbbb", page)                         # commit du dernier passage
            self.assertIn("Débit : -30 %", page)                   # section « Ce qui a bougé »
            self.assertIn("Hypothèse prise pour un fait", page)    # angles morts du miroir
            self.assertIn("1 sur 2", page)                         # part des partages proposés : f1 oui, f2 non
            # la veille et les partages viennent de la base : les anciens fichiers (9 articles, 4 partages) ne sont pas ouverts
            self.assertIn("Collection <code>watch</code> : <b>2</b> articles, 2 passages indexés.", page)
            self.assertIn("<b>2</b> au total, 2 sur les 14 derniers jours", page)
            self.assertNotIn("<b>9</b> articles", page)
            self.assertNotIn("<b>4</b> au total", page)
            self.assertIn("0.40 $", page)                          # coût du dernier passage : 0.15 + 0.25
            self.assertIn("1.35 $", page)                          # total d'octobre, partiel et non validant compris : 0.30 + 0.40 + 0.60 + 0.05
            self.assertIn("sessions sonnet, juge habituel", page)  # modèles du passage non validant
            self.assertIn("non validant", page)
            self.assertIn("2 derniers passages complets", page)    # le passage non validant n'est ni dans la courbe ni dans la matrice
            self.assertNotIn('text-anchor="middle">4/6<', page)    # absent de la courbe, présent dans le tableau
            self.assertNotIn("ccccccc", page)                      # le passage partiel n'est ni dans la courbe ni dans le tableau
            self.assertIn("1 passage partiel écarté", page)
            self.assertIn("2 derniers passages complets", page)
            self.assertIn('viewBox="0 0 900', page)                # graphiques pleine largeur, 1 unité = 1 pixel
            self.assertIn("font-size:11.5px", page)                # textes des graphiques lisibles

    def test_un_seul_passage_avec_pretri(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = donnees_completes(root)
            log = root / "logs" / "pmzilla-watch.log"
            first = log.read_text(encoding="utf-8").split("=== 2026-10-11")[0]   # un seul passage, avec pré-tri
            log.write_text(first, encoding="utf-8")
            result, page = generer(root, env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Un seul passage a pré-trié des articles", page)     # une phrase, pas de courbe
            self.assertNotIn("dernier passage avec pré-tri", page)
            self.assertIn("(1 dernier passage)", page)             # pluriel : un seul passage
            self.assertNotIn("1 derniers passages", page)

    def test_le_journal_pmzilla_watch_log_est_lu_et_pas_l_ancien_nom(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = donnees_completes(root)
            _, nouveau = generer(root, env)                         # journal sous le nom actuel (donnees_completes)
            self.assertIn("Nouveaux articles par jour", nouveau)
            self.assertIn("2 nouveaux articles", nouveau)
            self.assertIn("Durée du pré-tri par passage", nouveau)
            log = root / "logs" / "pmzilla-watch.log"
            log.rename(root / "logs" / "pmzilla-veille.log")        # l'ancien nom n'est plus lu
            result, ancien = generer(root, env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("2 nouveaux articles", ancien)
            self.assertNotIn("Durée du pré-tri par passage", ancien)

    def test_tri_yaml_lu_dans_watch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = donnees_completes(root)
            _, page = generer(root, env)                            # watch/tri.yaml : mode filtre
            self.assertIn('<span class="badge ok">filtre</span>', page)
            ws = root / "workspace"
            write(ws / "watch" / "tri.yaml", "mode: observation\n")
            _, nouveau = generer(root, env)
            self.assertIn('<span class="badge warn">observation</span>', nouveau)

    def test_rappels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = donnees_completes(root)
            ws = root / "workspace"
            (ws / "_bmad-output" / "pmzilla" / "miroir" / "miroir-2026-10.md").unlink()
            (ws / "Flux-Lab" / "rapports" / "evolution-equipe-x-2026-10-10.md").unlink()
            write(ws / "Flux-Lab" / "rapports" / "flux-equipe-x-2026-08-01.md", "# ancien\n")
            result, page = generer(root, env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("premier miroir prévu début novembre", page)          # aucun miroir
            self.assertRegex(page, r'Suivi du flux</td><td>[^<]*</td><td>01/08/2026</td><td><span class="badge warn">à faire')
            write(ws / "Flux-Lab" / "rapports" / "flux-equipe-x-2026-10-05.md", "# récent\n")   # rapport de moins d'un mois
            _, page = generer(root, env)
            self.assertRegex(page, r'Suivi du flux</td><td>[^<]*</td><td>05/10/2026</td><td><span class="badge ok">à jour')

    def test_sans_aucune_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "absent-ws").mkdir()    # un dossier de contenu vide : un dossier absent arrête l'outil (code 78, R-77)
            env = {"PMZILLA_LAB_WORKSPACE": str(root / "absent-ws"), "PMZILLA_LAB_DATA": str(root / "absent-data"),
                   "PMZILLA_LAB_LOGS": str(root / "absent-logs")}
            result, page = generer(root, env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.verifier_commun(page)
            self.assertGreaterEqual(page.count("pas encore de données"), 7)
            self.assertNotIn("Traceback", page)

    def test_dossier_de_donnees_sans_fichier_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = donnees_completes(root)
            self.assertEqual(list((root / "data").rglob("*.sqlite")), [])
            result, page = generer(root, env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.verifier_commun(page)
            self.assertEqual(list((root / "data").rglob("*.sqlite")), [])    # aucun fichier de ce type ouvert ni créé
            self.assertEqual(list(root.rglob("*.sqlite")), [])

    def test_sources_illisibles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = donnees_completes(root)
            write(root / "workspace" / "Journal-Lab" / "journal.yaml", "- [pas: {valide")
            write_fake(Path(env["PMZILLA_TEST_FAKE_LIBRARY"]), error="ConnectionError")   # la base ne répond pas
            result, page = generer(root, env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.verifier_commun(page)
            self.assertIn("source illisible", page)
            bibliotheque = page[page.index('<section id="bibliotheque">'):page.index('<section id="qualite">')]
            self.assertEqual(bibliotheque.count("source illisible (ConnectionError)"), 2)   # livres et articles sans auteur
            self.assertIn("<li>Livre Fictif A (Auteur Fictif)</li>", bibliotheque)                # les livres à re-télécharger restent
            self.assertNotIn("message secret", page)                                         # le type de l'erreur, jamais le message


class ExclusionCollections(unittest.TestCase):
    """La section bibliothèque exclut par nom exact `watch`, son ancien nom `veille` et OWN_COLLECTION."""

    def test_comptes_par_nom_exact(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import watch_paths
        exclues = ["watch", "veille", watch_paths.OWN_COLLECTION]
        # noms qui contiennent un mot exclu sans l'être : ces livres sont comptés
        comptees = ["produit|watch-notes", "notes-" + watch_paths.OWN_COLLECTION, "prewatch", "veille-notes"]
        with tempfile.TemporaryDirectory() as tmp:
            env = donnees_completes(Path(tmp))
            fake = Path(env["PMZILLA_TEST_FAKE_LIBRARY"])
            books = read_fake(fake)
            for i, coll in enumerate(exclues + ["flow|" + watch_paths.OWN_COLLECTION] + comptees, start=10):
                books.append({"title": f"Titre {i}", "author": None, "collections": coll.split("|"), "passages": 1})
            write_fake(fake, books)
            result, page = generer(Path(tmp), env)
            self.assertEqual(result.returncode, 0, result.stderr)
            # 2 livres de départ + 4 comptés ajoutés ; 4 exclus (dont un livre « flow|own »)
            self.assertIn("<b>6</b> livres, 6 passages", page)
            # articles de la veille (nom actuel et ancien, par nom exact) : 2 de départ + « watch » + « veille »
            self.assertIn("Articles de la veille sur 4 :", page)


class VeilleDepuisLaBase(unittest.TestCase):
    """Comptes de la veille et partages (design.md D6) : des lecteurs injectés, la même phrase qu'avant, jamais un ancien fichier."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(SCRIPT.parent))
        import dashboard
        cls.dashboard = dashboard

    def setUp(self):
        self.dashboard.set_language("fr")
        self.addCleanup(self.dashboard.set_language, "fr")
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        patcher = unittest.mock.patch.multiple(self.dashboard, WORKSPACE=self.root / "ws", CODE_ROOT=self.root / "ws", DATA=self.root / "data")
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.root / "data").mkdir()

    def comptes(self, **valeurs):
        return lambda: {"articles": 3, "passages": 41, **valeurs}

    def partages(self, **valeurs):
        defaut = {"total": 2, "recent": 1, "first_pick": "2026-10-08", "evaluable": 2, "hits": 1}
        return lambda day: {**defaut, **valeurs}

    def test_compte_de_la_veille(self):
        html = self.dashboard.veille_base_block(self.comptes())
        self.assertEqual(html, "<p>Collection <code>watch</code> : <b>3</b> articles, 41 passages indexés.</p>")
        self.assertIn("<b>1</b> article,", self.dashboard.veille_base_block(self.comptes(articles=1)))

    def test_partage_une_part_sur_deux(self):
        html = self.dashboard.partages_block(self.partages())
        self.assertIn("<b>2</b> au total, 1 sur les 14 derniers jours", html)
        self.assertIn("<b>1 sur 2</b> (50 %)", html)
        self.assertIn("postérieurs au 2026-10-08", html)

    def test_aucun_partage_aucune_selection_aucun_partage_evaluable(self):
        self.assertIn("aucun partage relevé pour l&#x27;instant", self.dashboard.partages_block(self.partages(total=0, recent=0)))
        self.assertIn("la table des 5 à lire est vide", self.dashboard.partages_block(self.partages(first_pick=None)))
        self.assertIn("aucun partage n&#x27;est postérieur", self.dashboard.partages_block(self.partages(evaluable=0, hits=0)))

    def test_le_jour_est_donne_au_lecteur(self):
        vus = []

        def lecteur(day):
            vus.append(day)
            return self.partages()(day)
        with unittest.mock.patch.dict(os.environ, {"PMZILLA_LAB_TODAY": "2026-10-12"}):
            self.dashboard.partages_block(lecteur)
        self.assertEqual(vus, [datetime.date(2026, 10, 12)])

    def test_lecteur_qui_leve_source_illisible_avec_le_type_seulement(self):
        def leve(*args):
            raise ConnectionError("hôte secret injoignable")
        for bloc in (self.dashboard.veille_base_block, self.dashboard.partages_block):
            with self.subTest(bloc=bloc.__name__):
                html = self.dashboard.safe(lambda: bloc(leve))
                self.assertIn("source illisible (ConnectionError)", html)
                self.assertNotIn("hôte secret", html)

    def test_lecteurs_reels_cherches_a_l_appel(self):
        with unittest.mock.patch.object(self.dashboard, "fetch_watch_counts", self.comptes(articles=7)), \
                unittest.mock.patch.object(self.dashboard, "fetch_shares", self.partages(total=9)):
            self.assertIn("<b>7</b> articles", self.dashboard.veille_base_block())
            self.assertIn("<b>9</b> au total", self.dashboard.partages_block())

    def test_lecteur_reel_ouvre_le_role_de_lecture_seule_et_ferme_la_connexion(self):
        class Curseur:
            def __init__(self, ligne):
                self.ligne = ligne

            def fetchone(self):
                return self.ligne

        class Connexion:
            closed = False

            def execute(self, sql, params=()):
                assert "knowledge." in sql and "INSERT" not in sql.upper()
                return Curseur((3, 41) if "watch_collection" in sql or "ANY" in sql else (2, 1, "2026-10-08", 2, 1))

            def close(self):
                self.closed = True

        connexion = Connexion()
        self.assertEqual(self.dashboard.fetch_watch_counts(connect=lambda: connexion), {"articles": 3, "passages": 41})
        self.assertTrue(connexion.closed)

    def test_texte_du_tableau_de_bord_sans_ancien_fichier(self):
        texte = (SCRIPT.parent / "dashboard.py").read_text(encoding="utf-8")
        for ancien in ("tri." + "sqlite", "library." + "sqlite", "sqlite" + "3"):
            self.assertNotIn(ancien, texte)
        self.assertNotIn("SQLite", texte)


class LecteurBibliotheque(unittest.TestCase):
    """Section bibliothèque (design.md D10) : un lecteur injecté, jamais une vraie base."""

    BOOKS = [{"title": "Livre Avec Auteur", "author": "Auteur Un", "collections": ["produit"], "passages": 3},
             {"title": "Livre Sans Auteur", "author": "b.pdf (auteur non indiqué)", "collections": ["flow", "tech"], "passages": 2},
             {"title": "Livre Inconnu", "author": None, "collections": ["facilitation"], "passages": 1},
             {"title": "Article", "author": "site.example (auteur non indiqué)", "collections": ["watch"], "passages": 4},
             {"title": "Ancien article", "author": None, "collections": ["veille"], "passages": 4},
             {"title": "Article personnel", "author": "Auteur Local", "collections": ["own-articles", "watch"], "passages": 4}]

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(SCRIPT.parent))
        import dashboard
        cls.dashboard = dashboard

    def setUp(self):
        self.dashboard.set_language("fr")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        patcher = unittest.mock.patch.multiple(self.dashboard, WORKSPACE=self.root / "ws", CODE_ROOT=self.root / "ws", DATA=self.root / "data",
                                               LOGS=self.root / "logs")
        patcher.start()
        self.addCleanup(patcher.stop)
        write(self.root / "ws" / "tools" / "mapping_lab.py", "MAPPING = {}\n")   # aucun livre à re-télécharger

    def test_livres_depuis_le_lecteur(self):
        html = self.dashboard.livres_block(lambda: self.BOOKS)
        self.assertIn("<b>3</b> livres, 6 passages", html)            # veille, ancien nom et collection personnelle exclus
        self.assertIn("<li>Livre Inconnu</li><li>Livre Sans Auteur</li>", html)   # sans auteur, triés
        self.assertNotIn("Livre Avec Auteur", html)
        self.assertIn("<td>flow</td><td>1</td>", html)
        self.assertIn("<td>facilitation</td><td>1</td>", html)

    def test_articles_sans_auteur_depuis_le_lecteur(self):
        html = self.dashboard.articles_sans_auteur_block(lambda: self.BOOKS)
        self.assertIn("Articles de la veille sur 3 : <b>1</b> sans auteur ni site, <b>1</b> affichés", html)

    def test_lecteur_par_defaut_cherche_a_l_appel(self):
        with unittest.mock.patch.object(self.dashboard, "fetch_library_books", lambda: self.BOOKS):
            html = self.dashboard.section_bibliotheque()
        self.assertIn("<b>3</b> livres", html)

    def test_base_vide(self):
        with unittest.mock.patch.object(self.dashboard, "fetch_library_books", lambda: []):
            html = self.dashboard.section_bibliotheque()
        self.assertEqual(html.count("pas encore de données"), 3)     # livres, à re-télécharger (aucun), articles

    def test_base_qui_ne_repond_pas_source_illisible_type_seulement(self):
        def fetch():
            raise ConnectionError("hôte secret injoignable")
        with unittest.mock.patch.object(self.dashboard, "fetch_library_books", fetch):
            html = self.dashboard.section_bibliotheque()
        self.assertEqual(html.count("source illisible (ConnectionError)"), 2)
        self.assertNotIn("hôte secret", html)

    def test_page_ecrite_et_code_zero_quand_la_base_ne_repond_pas(self):
        def fetch():
            raise ConnectionError("hôte secret")
        sortie = self.root / "page.html"
        with unittest.mock.patch.object(self.dashboard, "fetch_library_books", fetch), \
                unittest.mock.patch.object(self.dashboard, "fetch_running_experiments", fetch), \
                unittest.mock.patch.dict(os.environ, without_cases_variables(os.environ), clear=True):
            with contextlib.redirect_stdout(io.StringIO()):
                code = self.dashboard.main(["--output", str(sortie)])
        self.assertEqual(code, 0)
        page = sortie.read_text(encoding="utf-8")
        self.assertIn("source illisible (ConnectionError)", page)
        self.assertIn('<section id="qualite">', page)

    def test_connexion_role_lecture_delai_court_et_base_nommee(self):
        import db
        appels = []

        class Conn:
            closed = False

            def execute(self, sql, params=()):
                appels.append(sql)
                return self

            def fetchall(self):
                return [("Livre", "Auteur", ["produit", "flow"], 5)]

            def close(self):
                Conn.closed = True

        def connect(**kwargs):
            appels.append(kwargs)
            return Conn()
        with unittest.mock.patch.object(db, "connect", connect), \
                unittest.mock.patch.dict(os.environ, {"PMZILLA_LAB_KNOWLEDGE_DBNAME": "pmzilla_test_nommee"}):
            rows = self.dashboard.fetch_library_books()
        self.assertEqual(appels[0], {"role": "pmzilla_knowledge_ro", "timeout": self.dashboard.CASES_TIMEOUT_SECONDS,
                                     "dbname": "pmzilla_test_nommee"})
        self.assertIn("knowledge.books", appels[1])
        self.assertTrue(Conn.closed)
        self.assertEqual(rows, [{"title": "Livre", "author": "Auteur", "collections": ["produit", "flow"], "passages": 5}])
        environ = {k: v for k, v in os.environ.items() if k != "PMZILLA_LAB_KNOWLEDGE_DBNAME"}
        with unittest.mock.patch.object(db, "connect", connect), unittest.mock.patch.dict(os.environ, environ, clear=True):
            self.dashboard.fetch_library_books()
        self.assertIsNone(appels[2]["dbname"])

    def test_connexion_fermee_meme_si_la_lecture_echoue(self):
        class Conn:
            closed = False

            def execute(self, sql, params=()):
                raise RuntimeError("lecture refusée")

            def close(self):
                Conn.closed = True
        with self.assertRaises(RuntimeError):
            self.dashboard.fetch_library_books(connect=Conn)
        self.assertTrue(Conn.closed)


class Experimentations(unittest.TestCase):
    """Septième section (design.md 8) : le récupérateur est injecté, aucune base n'est jointe."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(SCRIPT.parent))
        import dashboard
        cls.dashboard = dashboard

    def setUp(self):
        self.dashboard.set_language("fr")
        patcher = unittest.mock.patch.dict(os.environ, {"PMZILLA_LAB_CASES_AUTHOR": "auteur-invente"})
        patcher.start()
        self.addCleanup(patcher.stop)
        today = unittest.mock.patch.dict(os.environ, {"PMZILLA_LAB_TODAY": "2026-10-12"})
        today.start()
        self.addCleanup(today.stop)

    ROWS = [  # déjà triées par date de bilan, comme running_experiments
        {"number": 7, "problem": "Problème tardif <b>", "started_on": "2026-08-01", "review_due": "2026-10-01",
         "postponements": 2, "due": True},
        {"number": 9, "problem": "Problème à venir", "started_on": "2026-10-05", "review_due": "2026-11-16",
         "postponements": 0, "due": False}]

    def section(self, fetch):
        return self.dashboard.section_experiences(fetch)

    def test_lignes_comptes_retard_et_ordre(self):
        calls = []

        def fetch(author, day):
            calls.append((author, day))
            return self.ROWS
        html = self.section(fetch)
        self.assertEqual(calls, [("auteur-invente", datetime.date(2026, 10, 12))])
        self.assertIn("Expérimentations en cours (2), bilan dû (1)", html)
        self.assertLess(html.index("Problème tardif"), html.index("Problème à venir"))
        self.assertIn("&lt;b&gt;", html)                       # texte échappé
        self.assertIn("01/10/2026", html)
        self.assertIn("16/11/2026", html)
        self.assertEqual(html.count("bilan dû</span>"), 1)    # un seul drapeau
        self.assertIn("<td>2</td>", html)                      # reports

    def test_page_anglaise(self):
        self.dashboard.set_language("en")
        html = self.section(lambda author, day: self.ROWS)
        self.assertIn("Running experiments (2), review due (1)", html)
        self.assertIn("2026-10-01", html)
        self.assertEqual(html.count("review due</span>"), 1)
        self.assertEqual(self.dashboard.t("section_experiments"), "Experiments awaiting a result")

    def test_revue_due_le_jour_meme_est_visible_et_signalee(self):
        # cas limite : review_due = aujourd'hui (2026-10-12) ; la règle est celle de cases_store (<=), pas « en retard » (<)
        import cases_store
        lignes = [(3, "Problème du jour", datetime.date(2026, 9, 1), datetime.date(2026, 10, 12), 0)]

        def fetch(author, day):
            with unittest.mock.patch.object(cases_store, "_read", return_value=lignes):
                return cases_store.running_experiments(object(), author, day)
        html = self.section(fetch)
        self.assertIn("Expérimentations en cours (1), bilan dû (1)", html)
        self.assertEqual(html.count("bilan dû</span>"), 1)
        self.assertIn("12/10/2026", html)
        self.assertNotIn("en retard", html)

    def test_titre_francais(self):
        self.assertEqual(self.dashboard.t("section_experiments"), "Expérimentations en attente de résultat")

    def test_sans_experience_en_cours(self):
        html = self.dashboard.safe(lambda: self.section(lambda author, day: []))
        self.assertIn("pas encore de données", html)

    def test_sans_auteur(self):
        def fetch(author, day):
            self.fail("aucune lecture sans auteur")
        with unittest.mock.patch.dict(os.environ, {"PMZILLA_LAB_CASES_AUTHOR": ""}), \
                tempfile.TemporaryDirectory() as tmp, unittest.mock.patch.object(self.dashboard, "WORKSPACE", Path(tmp)):
            html = self.dashboard.safe(lambda: self.section(fetch))
        self.assertIn("pas encore de données", html)

    def test_source_illisible(self):
        def fetch(author, day):
            raise ConnectionError("pas de base")
        html = self.dashboard.safe(lambda: self.section(fetch))
        self.assertIn("source illisible (ConnectionError)", html)
        self.assertNotIn("pas de base", html)

    def test_page_complete_avec_recuperateur_injecte(self):
        with unittest.mock.patch.object(self.dashboard, "fetch_running_experiments", lambda author, day: self.ROWS), \
                tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch.multiple(self.dashboard, WORKSPACE=Path(tmp) / "ws", DATA=Path(tmp) / "data", LOGS=Path(tmp) / "logs"):
                page = self.dashboard.build("fr")
        self.assertIn('<section id="experimentations"><h2>Expérimentations en attente de résultat</h2>', page)
        self.assertLess(page.index('id="a-faire"'), page.index('id="experimentations"'))
        self.assertLess(page.index('id="experimentations"'), page.index('id="veille"'))
        self.assertIn("Expérimentations en cours (2), bilan dû (1)", page)
        self.assertNotIn("—", page)


if __name__ == "__main__":
    unittest.main()
