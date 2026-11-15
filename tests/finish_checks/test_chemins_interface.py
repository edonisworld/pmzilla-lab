"""
Liste des chemins d'interface (mothra-slices, design D12, tâche 8.1 ; finish-e2e-proof-shared, D1 et D7).

Le fichier tools/finish_e2e_paths.txt, source unique, déclare les chemins dont le changement exige la preuve de bout en bout (contrôle 16 de
tools/finish_checks.py, passe du train ; le refus 16 de tools/finish_branch.sh est retiré avec ce script par B9, finish-single-b7-b9). Ce test statique
le garde honnête, sur l'arbre réel du dépôt (fichiers suivis et fichiers neufs non ignorés). Rétabli sous tests/finish_checks par B9 (revue 4.7,
R-20261105-32) : il testait cette liste, pas seulement la fin unitaire retirée ; seule la vérification « pas de tableau CHEMINS_INTERFACE dans
tools/finish_branch.sh » est retirée avec le script :

  - une entrée n'a que l'une des formes de D1 (dossier écrit avec « / » final, chemin de fichier, motif avec « * ») ;
  - aucune copie : aucun fichier suivi de tools/ ne nomme tools/finish_train_e2e.txt et tools/finish_train.sh ne nomme pas le fichier de données
    (il lit le contrôle 16 du module).

  - une entrée qui ne correspond à aucun fichier fait échouer le test, en nommant l'entrée ;
  - un dossier front, contract ou routes de Mothra qui n'est couvert par aucune entrée fait échouer le test, en nommant le dossier.

Exception transitoire, déclarée ici et nulle part ailleurs : EN_ATTENTE nomme les entrées dont les fichiers naissent à la tâche 8.2
(tests/run_e2e.sh et tests/e2e/). Tant que la tâche 8.2 n'a pas livré ces fichiers, ces deux entrées peuvent ne rien désigner ;
dès qu'une entrée de EN_ATTENTE désigne un fichier, le test échoue et demande de la retirer de EN_ATTENTE (la liste doit finir vide).

Les deux contrôles sont aussi testés sur des listes fabriquées, pour prouver qu'ils échouent bien.
"""
import fnmatch
import re
import subprocess
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
LISTE = RACINE / "tools" / "finish_e2e_paths.txt"
TRAIN = RACINE / "tools" / "finish_train.sh"
ANCIEN_NOM = "finish_train_e2e" + ".txt"   # coupé : ce fichier ne se nomme lui-même nulle part
# dossiers de Mothra qui portent l'interface (design D12) : mothra/front, mothra/contract, routes sous mothra/server/src (voir dossiers_hors_liste)
EN_ATTENTE = ()      # tâche 8.2 livrée (tests/run_e2e.sh et tests/e2e/) : la liste est vide, toute entrée doit désigner un fichier


def lire_entrees(texte):
    """Les entrées du fichier de données : une par ligne, « # » commence un commentaire, lignes vides ignorées, espaces de bord retirés."""
    if texte is None:
        return None
    entrees = []
    for ligne in texte.splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if ligne:
            entrees.append(ligne)
    return entrees


def entrees_de_forme_inconnue(entrees):
    """Les entrées qui ne sont ni un dossier à « / » final, ni un chemin de fichier, ni un motif avec « * » (D1) : absolu, « .. », magie de chemin
    Git (« : »), barre inverse ou espace."""
    return [e for e in entrees if e.startswith(("/", ":", "!", "-")) or ".." in e.split("/") or any(c in e for c in "\\ \t\"'?[]{}")]


def correspond(entree, chemin):
    """Même sens qu'un chemin Git donné à git diff : le chemin lui-même, ce qu'il contient s'il désigne un dossier, un motif avec « * »."""
    if chemin == entree or chemin.startswith(entree.rstrip("/") + "/"):
        return True
    return "*" in entree and fnmatch.fnmatchcase(chemin, entree)


def entrees_sans_fichier(entrees, fichiers, en_attente=()):
    """Entrées qui ne désignent aucun fichier, hors celles que EN_ATTENTE tolère."""
    return [e for e in entrees if e not in en_attente and not any(correspond(e, f) for f in fichiers)]


def en_attente_livrees(entrees, fichiers, en_attente):
    """Entrées de EN_ATTENTE qui désignent désormais un fichier (à retirer de EN_ATTENTE), ou qui ne sont plus dans la liste."""
    livrees = [e for e in en_attente if any(correspond(e, f) for f in fichiers)]
    absentes = [e for e in en_attente if e not in entrees]
    return livrees, absentes


def dossiers_hors_liste(entrees, fichiers):
    """Dossiers visés par D12 (mothra/front, mothra/contract, un dossier routes sous mothra/server/src ; hors node_modules) qui tiennent un
    fichier et qu'aucune entrée ne couvre. Un dossier nommé routes, front ou contract ailleurs (mothra/server/test/routes/) n'est pas visé."""
    dossiers = set()
    for chemin in fichiers:
        morceaux = chemin.split("/")
        if morceaux[0] != "mothra" or "node_modules" in morceaux:
            continue
        if len(morceaux) > 2 and morceaux[1] in ("front", "contract"):
            dossiers.add("mothra/" + morceaux[1])
        if morceaux[1:3] == ["server", "src"]:
            for i in range(3, len(morceaux) - 1):   # le dernier morceau est le fichier : jamais pris pour un dossier
                if morceaux[i] == "routes":
                    dossiers.add("/".join(morceaux[:i + 1]))
    return sorted(d for d in dossiers if not any(correspond(e, d + "/x") for e in entrees))


def fichiers_du_depot():
    """Fichiers suivis et fichiers neufs non ignorés sous mothra/, contrats/ et tests/ (les seuls dossiers que visent les entrées), chemins
    relatifs à la racine. Un pathspec explicite : le test ne lit rien du dossier de spécification."""
    sortie = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "mothra", "contrats", "tests"], cwd=RACINE,
                            capture_output=True, text=True, errors="replace", check=True).stdout
    return [f for f in sortie.split("\0") if f]


class ListeDesCheminsInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entrees = lire_entrees(LISTE.read_text(encoding="utf-8") if LISTE.is_file() else None)
        cls.fichiers = fichiers_du_depot() if cls.entrees is not None else []

    def lues(self):
        self.assertIsNotNone(self.entrees, "tools/finish_e2e_paths.txt est absent")
        return self.entrees

    def test_les_entrees_n_ont_que_les_formes_de_d1_et_aucune_n_est_en_double(self):
        self.assertEqual(entrees_de_forme_inconnue(self.lues()), [])
        self.assertEqual(len(self.lues()), len(set(self.lues())), "une entrée est écrite deux fois")

    def test_aucune_copie_de_la_liste_ailleurs(self):
        # source unique (D7, point 1) : ni ancien nom, ni lecture du fichier par le train (le tableau CHEMINS_INTERFACE de la fin unitaire retirée n'est plus vérifié)
        suivis = subprocess.run(["git", "ls-files", "-z", "--", "tools"], cwd=RACINE, capture_output=True, text=True, check=True).stdout.split("\0")
        nommant = [f for f in suivis if f and (RACINE / f).is_file() and ANCIEN_NOM in (RACINE / f).read_text(encoding="utf-8", errors="replace")]
        self.assertEqual(nommant, [], "fichier(s) de tools/ qui nomment l'ancien fichier de la liste du train")
        self.assertNotIn("finish_e2e_paths", TRAIN.read_text(encoding="utf-8"), "le train lit le contrôle 16 du module, jamais le fichier")

    def test_la_liste_du_design_est_declaree_telle_quelle(self):
        self.assertEqual(self.lues(), [
            "mothra/front/", "mothra/contract/", "mothra/server/src/", "contrats/", "mothra/package-lock.json", "mothra/package.json",
            "mothra/server/package.json", "mothra/server/tsconfig.json",
            "tests/e2e/", "tests/run_e2e.sh", "tests/mothra_donnees/"])   # décision F18 (#591) : tout le serveur et package.json, et non plus les seules routes ; R-20261103-31 : manifeste et tsconfig du serveur

    def test_le_serveur_entier_et_package_json_sont_couverts(self):
        # F18 (#591) : la configuration du serveur et le manifeste de Mothra changent l'interface au même titre que les routes
        for chemin in ("mothra/server/src/config/exemple.ts", "mothra/server/src/routes/exemple.ts", "mothra/package.json"):
            self.assertTrue(any(correspond(e, chemin) for e in self.lues()), chemin)
        self.assertIn("mothra/server/src/", self.lues())
        self.assertIn("mothra/package.json", self.lues())
        self.assertNotIn("mothra/server/src/routes/", self.lues(), "l'entrée des routes seules est remplacée par mothra/server/src/")

    def test_build_et_demarrage_de_chaque_paquet_couverts(self):
        # R-20261103-31 (extension de F18) : le manifeste et le tsconfig de chaque paquet de Mothra (build, démarrage) sont couverts ;
        # front et contract le sont par leur dossier entier, le serveur par ses deux entrées ; un voisin sans build ni démarrage reste hors liste
        for chemin in ("mothra/server/package.json", "mothra/server/tsconfig.json", "mothra/front/package.json",
                       "mothra/front/tsconfig.json", "mothra/contract/package.json", "mothra/contract/tsconfig.json"):
            self.assertTrue(any(correspond(e, chemin) for e in self.lues()), chemin)
        self.assertFalse(any(correspond(e, "mothra/server/test/aide.ts") for e in self.lues()), "frontière : les tests du serveur restent hors liste")

    def test_aucune_entree_ne_designe_rien(self):
        self.assertEqual(entrees_sans_fichier(self.lues(), self.fichiers, EN_ATTENTE), [], "entrée(s) qui ne désignent aucun fichier")

    def test_en_attente_se_vide_quand_la_tache_8_2_livre(self):
        livrees, absentes = en_attente_livrees(self.lues(), self.fichiers, EN_ATTENTE)
        self.assertEqual(livrees, [], "ces fichiers existent : retirer l'entrée de EN_ATTENTE")
        self.assertEqual(absentes, [], "EN_ATTENTE nomme une entrée qui n'est plus dans la liste")

    def test_aucun_dossier_front_contract_ou_routes_hors_de_la_liste(self):
        self.assertEqual(dossiers_hors_liste(self.lues(), self.fichiers), [], "dossier(s) de Mothra hors de tools/finish_e2e_paths.txt")

    def test_les_dossiers_de_mothra_existent_et_sont_couverts(self):
        # garde-fou du contrôle lui-même : sur l'arbre réel, les trois dossiers sont vus (sinon le test ci-dessus ne prouverait rien)
        for dossier in ("mothra/front", "mothra/contract", "mothra/server/src/routes"):
            self.assertTrue(any(f.startswith(dossier + "/") for f in self.fichiers), dossier)
            self.assertTrue(any(correspond(e, dossier + "/x") for e in self.lues()), dossier)


class LesControlesEchouentVraiment(unittest.TestCase):
    ENTREES = ["mothra/front/", "mothra/contract/", "mothra/server/src/routes/", "mothra/package-lock.json"]
    FICHIERS = ["mothra/front/src/a.ts", "mothra/contract/src/b.ts", "mothra/server/src/routes/c.ts", "mothra/package-lock.json"]

    def test_une_liste_complete_passe(self):
        self.assertEqual(entrees_sans_fichier(self.ENTREES, self.FICHIERS), [])
        self.assertEqual(dossiers_hors_liste(self.ENTREES, self.FICHIERS), [])

    def test_une_entree_sans_fichier_est_nommee(self):
        self.assertEqual(entrees_sans_fichier(self.ENTREES + ["mothra/absent/"], self.FICHIERS), ["mothra/absent/"])
        self.assertEqual(entrees_sans_fichier(self.ENTREES + ["tests/run_e2e.sh"], self.FICHIERS), ["tests/run_e2e.sh"])

    def test_une_entree_en_attente_est_tolerée_puis_signalee_une_fois_livree(self):
        self.assertEqual(entrees_sans_fichier(self.ENTREES + ["tests/e2e/"], self.FICHIERS, ("tests/e2e/",)), [])
        livrees, absentes = en_attente_livrees(self.ENTREES + ["tests/e2e/"], self.FICHIERS + ["tests/e2e/a.spec.ts"], ("tests/e2e/",))
        self.assertEqual((livrees, absentes), (["tests/e2e/"], []))
        self.assertEqual(en_attente_livrees(self.ENTREES, self.FICHIERS, ("tests/e2e/",)), ([], ["tests/e2e/"]))

    def test_un_dossier_de_routes_hors_de_la_liste_est_nomme(self):
        sans_routes = [e for e in self.ENTREES if "routes" not in e]
        self.assertEqual(dossiers_hors_liste(sans_routes, self.FICHIERS), ["mothra/server/src/routes"])

    def test_un_dossier_front_ou_contract_hors_de_la_liste_est_nomme(self):
        self.assertEqual(dossiers_hors_liste(["mothra/contract/"], self.FICHIERS + ["mothra/front/x.ts"]),
                         ["mothra/front", "mothra/server/src/routes"])
        self.assertEqual(dossiers_hors_liste(self.ENTREES, self.FICHIERS + ["mothra/server/src/nouveau/routes/r.ts"]),
                         ["mothra/server/src/nouveau/routes"])

    def test_node_modules_et_hors_mothra_sont_ignores(self):
        self.assertEqual(dossiers_hors_liste([], ["mothra/node_modules/p/front/x.js", "docs/front/a.md", "tests/routes/b.py"]), [])

    def test_un_dossier_de_tests_nomme_routes_front_ou_contract_n_est_pas_vise(self):
        faux_positifs = ["mothra/server/test/routes/a.test.ts", "mothra/server/test/front/b.ts", "mothra/server/src/lib/contract/c.ts",
                         "mothra/server/test/contract/d.ts", "mothra/tools/front/e.ts"]
        self.assertEqual(dossiers_hors_liste([], faux_positifs), [])

    def test_un_fichier_nomme_comme_un_dossier_n_en_fait_pas_un(self):
        self.assertEqual(dossiers_hors_liste([], ["mothra/server/src/routes"]), [])

    def test_le_fichier_est_lu_sans_ses_commentaires(self):
        texte = '# en-tête\n\na/\n  b.txt   # « pas-une-entree »\n# autre/\nc/*.ts\n'
        self.assertEqual(lire_entrees(texte), ["a/", "b.txt", "c/*.ts"])
        self.assertIsNone(lire_entrees(None))

    def test_les_formes_inconnues_sont_nommees(self):
        self.assertEqual(entrees_de_forme_inconnue(["a/", "b.txt", "c/*.ts"]), [])
        self.assertEqual(entrees_de_forme_inconnue(["/abs/", ":(top)x", "../x", "a b/", "a\\b"]), ["/abs/", ":(top)x", "../x", "a b/", "a\\b"])


if __name__ == "__main__":
    unittest.main()
