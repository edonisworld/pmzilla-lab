"""
Cas partagés de contre-exemples du masquage (change masking-sums, R-144, tâches 1.2 et 1.6 ; conception D4 « Shared counter-example cases »).

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -v

Le fichier contrats/cas-masquage.json porte X1 à X12 en données synthétiques. Ce joueur Python rejoue chaque cas contre
flow_views.masquer_vue(vue, noms, lignes, seuil, liees=…) : un test fixe par cas (test_cas_<identifiant>), qui lit ses données dans le fichier.
Le test de consommation échoue en nommant l'identifiant quand un cas du fichier n'est pas joué par un joueur de `players` (test absent, sauté,
sorte inconnue), et quand `players` liste `npm` sans joueur TypeScript. Un cas ignoré est un échec, jamais un saut.
Rouges avant la tâche 3.1 (masquer_vue n'existe pas encore) ; X6a, X7, X9 et X2c sont des régressions : verts dès que la fonction existe.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

FICHIER = RACINE / "contrats" / "cas-masquage.json"
SORTES_JOUEES = ("masquer_vue", "echantillon_h1")      # + echantillon_h1 : tâche 22.1, D16, R-20261106-18 (taille d'échantillon de H1, cas H1a à H1c)
ATTENDUS = [f"X{n}" for n in range(1, 13)]
RE_EQUIPE_SYNTHETIQUE = re.compile(r"^(?:[A-G]|N|\(produit\))$")
RE_IDENTIFIANT = re.compile(r"^id\d$")


def charger(chemin: Path = FICHIER) -> dict:
    return json.loads(chemin.read_text(encoding="utf-8"))


def tableau(vue: dict) -> tuple[list[str], list[tuple]]:
    noms = vue["columns"]
    return noms, [tuple(ligne.get(n) for n in noms) for ligne in vue["rows"]]


def cellules_masquees(cas: dict) -> list[list]:
    """Rejoue un cas contre masquer_vue ; renvoie les paires [rang, colonne] des colonnes jugées dont la cellule est masquée."""
    noms, lignes = tableau(cas)
    liees = {nom: tableau(vue) for nom, vue in cas.get("related", {}).items()} or None
    sorties = fv.masquer_vue(cas["view"], noms, lignes, cas["threshold"], liees=liees)
    masquees = []
    for rang, cellules in enumerate(sorties):
        for colonne in cas["cells"]:
            cellule = cellules[colonne]
            if "masked" in cellule:
                assert cellule == {"value": None, "masked": "under_threshold", "threshold": cas["threshold"]}, (cas["id"], rang, colonne, cellule)
                masquees.append([rang, colonne])
    return masquees


def ordonnees(paires) -> list[list]:
    return sorted([list(p) for p in paires], key=lambda p: (p[0], p[1]))


def cas_non_joues(donnees: dict, classe, racine_mothra: Path | None = None) -> list[str]:
    """Identifiants (ou « npm ») qu'un joueur listé dans `players` ne joue pas : sorte inconnue, test absent ou sauté ; « npm » listé sans
    fichier TypeScript qui nomme cas-masquage sous mothra/."""
    manquants = []
    if "python" in donnees["players"]:
        for cas in donnees["cases"]:
            test = getattr(classe, f"test_cas_{cas['id']}", None)
            if cas.get("kind") not in SORTES_JOUEES or test is None or getattr(test, "__unittest_skip__", False):
                manquants.append(cas["id"])
    if "npm" in donnees["players"]:
        joueur_ts = False
        non_listes: list[str] = []
        if racine_mothra is not None and racine_mothra.is_dir():
            for chemin in racine_mothra.rglob("*.ts"):
                if "node_modules" in chemin.parts:
                    continue
                texte = chemin.read_text(encoding="utf-8", errors="replace")
                if "cas-masquage" not in texte:
                    continue
                # un fichier TypeScript qui nomme le fichier de cas n'est un joueur que s'il liste chaque identifiant de cas (entre guillemets)
                absents = [c["id"] for c in donnees["cases"] if not re.search(rf"""["'`]{re.escape(c['id'])}["'`]""", texte)]
                if not absents:
                    joueur_ts = True
                    break
                non_listes = absents
        if not joueur_ts:
            manquants.extend([f"npm:{i}" for i in non_listes] if non_listes else ["npm"])
    return manquants


class JoueurPython(unittest.TestCase):
    """Un test fixe par contre-exemple, données lues dans contrats/cas-masquage.json (tâche 1.2)."""

    @classmethod
    def setUpClass(cls):
        cls.cas = {c["id"]: c for c in charger()["cases"]}

    def jouer(self, identifiant: str):
        cas = self.cas[identifiant]
        self.assertEqual(ordonnees(cellules_masquees(cas)), ordonnees(cas["masked"]), f"{identifiant} : {cas['title']}")

    def test_cas_X1(self):
        self.jouer("X1")

    def test_cas_X2(self):
        self.jouer("X2")

    def test_cas_X2b(self):
        self.jouer("X2b")

    def test_cas_X1b(self):
        self.jouer("X1b")                      # m1 : nom masqué par complément, identifiant visible : le plus petit identifiant visible l'est aussi

    def test_cas_X2c(self):
        self.jouer("X2c")                      # régression : une différence nulle n'est pas protégée

    def test_cas_X2d(self):
        self.jouer("X2d")                      # m1 : nom masqué par l'écart avec l'identifiant (D5-b), l'identifiant visible l'est aussi

    def test_cas_X2e(self):
        self.jouer("X2e")                      # M2 (a) : identifiants 4, 4 et 6, nom à 14 : la borne haute est le plus grand de 4 et du plus petit visible

    def test_cas_X2f(self):
        self.jouer("X2f")                      # M2 (a) : identifiants 3 et 5, nom à 8 : le nom est masqué après le complément

    def test_cas_X3(self):
        self.jouer("X3")

    def test_cas_X4(self):
        self.jouer("X4")

    def test_cas_X5(self):
        self.jouer("X5")

    def test_cas_X6a(self):
        self.jouer("X6a")                      # régression : au plancher, corrigé par R-140

    def test_cas_X6b(self):
        self.jouer("X6b")                      # seuil de 10 : rouge avant D5-c

    def test_cas_X7(self):
        self.jouer("X7")                       # régression : intervalle étroit permis, mesuré

    def test_cas_X8(self):
        self.jouer("X8")

    def test_cas_X8c(self):
        self.jouer("X8c")                      # X8 avec des trouvés de 30 et 33 : la chaîne des semaines isolée de la règle de l'excès

    def test_cas_X8b(self):
        self.jouer("X8b")                      # M2 (c) : la chaîne des semaines du produit se lit après D3, sur les cellules publiées

    def test_cas_X9(self):
        self.jouer("X9")                       # régression : règle B de R-140

    def test_cas_X10(self):
        self.jouer("X10")

    def test_cas_X11(self):
        self.jouer("X11")

    def test_cas_X12(self):
        self.jouer("X12")

    def test_cas_X12b(self):
        self.jouer("X12b")                     # B1 : deux trouvés masqués de 4, créés 30 et sans affects 22 : 8 = somme des bornes hautes


    def test_cas_X12c(self):
        self.jouer("X12c")                     # revue 2, B1 : un seul terme masqué publié (une version non retenue ne se voit pas dans les lignes)

    def test_cas_X12d(self):
        self.jouer("X12d")                     # revue 2, B2 : créés 30, sans affects 10, trouvés 18, 4 et 2, excès 4 : somme dérivée 2 sous le seuil

    def test_cas_X18(self):
        self.jouer("X18")                      # fuite du tri Opus : D5-e masque sans affects seul, D2 repasse jusqu'au point fixe et masque les créés

    def test_cas_X21(self):
        self.jouer("X21")                      # revue 4, M1 : un trouvé nul retenu est un terme caché (3 termes cachés, somme 12 = 3 x 4)

    def test_cas_X20(self):
        self.jouer("X20")                      # revue 3 : D5-d dans la boucle, après D2 : 10 et 13 côte à côte sont masqués

    def test_cas_X19(self):
        self.jouer("X19")                      # revue 3, M1 : le retard du produit boucle (b3 puis b4), la vue SQL aussi

    def test_cas_X14(self):
        self.jouer("X14")                      # 5.11 : nom masqué par complément, identifiants visibles 15 et 8 : tous deux masqués

    def test_cas_X15(self):
        self.jouer("X15")                      # revue 2, M4 : nom sous le seuil, un identifiant visible : il est masqué

    # Relation T3 (masking-sums D17, R-20261031-07) : rouges avant la tâche 13.3 (masquer_vue ne lit pas encore la vue hebdomadaire liée)
    def test_cas_X26a(self):
        self.jouer("X26a")                     # règle (a) : débit masqué, les quatre lignes Story et Task de 1 sont retirées, la ligne Bug reste

    def test_cas_X26b(self):
        self.jouer("X26b")                     # règle (b) : une ligne masquée, reste 3

    def test_cas_X26c(self):
        self.jouer("X26c")                     # règle (b) : reste égal au nombre de lignes masquées (S = k)

    def test_cas_X26d(self):
        self.jouer("X26d")                     # règle (b) : reste égal à quatre fois ce nombre au plancher (S = 4k)

    def test_cas_X26e(self):
        self.jouer("X26e")                     # règle (b) : 2 <= k < S < seuil

    def test_cas_X26f(self):
        self.jouer("X26f")                     # témoin vert : S = 5, k = 2, rien n'est épinglé

    def test_cas_X23(self):
        self.jouer("X23")                      # D15, groupe 6 : la chaîne et la ligne croisées, le créé de la semaine deux vaut 24 (rouge avant 6.4)

    def test_cas_X16(self):
        self.jouer("X16")                      # 5.11 : nom 19, identifiants 6, 5, 8 : tous masqués

    def test_cas_X17(self):
        self.jouer("X17")                      # 5.11 : nom 14, identifiants 1, 8, 5 : tous les visibles masqués

    # Identifiants alignés sur le design (revue 21.2) : X40a à X40f deviennent X42a à X42f, le cas des quatre trimestres à 5 devient X40.
    def test_cas_X42a(self):
        self.jouer("X42a")                     # R-20261106-39 : items_old = 0 montré quand items_ct l'est (rouge avant la règle)

    def test_cas_X42b(self):
        self.jouer("X42b")                     # R-20261106-39 : l'année à 0 masquée parce qu'un trimestre est masqué (rouge avant la règle)

    def test_cas_X42c(self):
        self.jouer("X42c")                     # R-20261106-39 : items_old masqué (3) avec items_ct visible, borne basse 1

    def test_cas_X42d(self):
        self.jouer("X42d")                     # R-20261106-39 : voisin, items_ct masqué au seuil relevé : le zéro reste masqué

    def test_cas_X42e(self):
        self.jouer("X42e")                     # R-20261106-39 : voisin, quatre trimestres à 0 visibles : l'année à 0 est visible (rouge avant la règle)

    def test_cas_X42f(self):
        self.jouer("X42f")                     # R-20261106-39 : voisin, seuil relevé à 10 : 0 montré, 9 masqué (rouge avant la règle)

    # Tâche 22.1, D16 : les quatre statistiques « sans les anciens » et la taille d'échantillon de H1 (R-20261105-30, R-20261106-18)
    def test_cas_X39(self):
        self.jouer("X39")                      # items_lt = items_ct = 8, items_old masqué, statistiques données (2.0, 6.0, 3.0, 7.0) mais masquées avec lui ; items_old dans [1, 7] (R-20261106-59)

    def test_cas_X40(self):
        self.jouer("X40")                      # R-20261106-59, Q2 (a) : quatre trimestres à 5, items_old à 4 partout, statistique annuelle donnée mais masquée, items_old de l'année masqué

    def test_cas_X41(self):
        self.jouer("X41")                      # R-20261106-59 : effectif 6, items_old masqué (3), statistiques masquées avec lui ; items_old dans [1, 5]

    def jouer_echantillon(self, identifiant: str):
        self.jouer(identifiant)                # les paires masquées, comme masquer_vue
        cas = self.cas[identifiant]
        noms, lignes = tableau(cas)
        sorties = fv.masquer_vue(cas["view"], noms, lignes, cas["threshold"])
        attendu = cas["sampleSize"]
        rang = attendu["row"]
        self.assertEqual(fv.taille_echantillon_h1(sorties[rang], "lead"), attendu["lead"], f"{identifiant} : lead")
        self.assertEqual(fv.taille_echantillon_h1(sorties[rang], "cycle"), attendu["cycle"], f"{identifiant} : cycle")

    def test_cas_H1a(self):
        self.jouer_echantillon("H1a")          # items_old montré : taille 14

    def test_cas_H1b(self):
        self.jouer_echantillon("H1b")          # items_old masqué (3) : aucune taille

    def test_cas_H1c(self):
        self.jouer_echantillon("H1c")          # items_old masqué par le complément (17, reste 3) : aucune taille, aucune borne basse


class Consommation(unittest.TestCase):
    def test_le_fichier_est_bien_forme_et_couvre_x1_a_x12(self):
        donnees = charger()
        self.assertIn("python", donnees["players"])
        identifiants = [c["id"] for c in donnees["cases"]]
        self.assertEqual(len(identifiants), len(set(identifiants)), "identifiant en double")
        for attendu in ATTENDUS:
            self.assertTrue(any(re.fullmatch(rf"{attendu}[a-z]?", i) for i in identifiants), f"contre-exemple absent : {attendu}")
        for cas in donnees["cases"]:
            for champ in ("id", "kind", "title", "regression", "view", "threshold", "cells", "columns", "rows", "masked"):
                self.assertIn(champ, cas, f"{cas.get('id')} : champ {champ}")
            self.assertGreaterEqual(cas["threshold"], fv.PLANCHER, cas["id"])
            for colonne in cas["cells"]:
                self.assertIn(colonne, cas["columns"], f"{cas['id']} : colonne jugée absente des colonnes")

    def test_donnees_synthetiques_seulement(self):
        for cas in charger()["cases"]:
            vues = [cas] + list(cas.get("related", {}).values())
            for vue in vues:
                for ligne in vue["rows"]:
                    equipe = ligne.get("team")
                    if equipe is not None:
                        self.assertRegex(equipe, RE_EQUIPE_SYNTHETIQUE, f"{cas['id']} : nom d'équipe non synthétique")
                    if ligne.get("jira_team_id") is not None:
                        self.assertRegex(ligne["jira_team_id"], RE_IDENTIFIANT, f"{cas['id']} : identifiant non synthétique")

    def test_tous_les_cas_sont_joues_par_le_joueur_python(self):
        manquants = cas_non_joues(charger(), JoueurPython, RACINE / "mothra")
        self.assertEqual([m for m in manquants if not m.startswith("npm")], [], "cas non joués par le joueur Python")

    def test_npm_n_est_liste_qu_avec_un_joueur_typescript(self):
        donnees = charger()
        if "npm" in donnees["players"]:
            self.assertEqual([m for m in cas_non_joues(donnees, JoueurPython, RACINE / "mothra") if m.startswith("npm")], [],
                             "players liste npm sans joueur TypeScript qui liste chaque identifiant")

    def test_un_fichier_typescript_qui_nomme_le_fichier_sans_lister_chaque_identifiant_n_est_pas_un_joueur(self):
        faux = {"players": ["npm"], "cases": [{"id": "X1", "kind": "masquer_vue"}, {"id": "X2", "kind": "masquer_vue"}]}
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            (racine / "joueur.test.ts").write_text("import cas from '../contrats/cas-masquage.json'\nconst joues = ['X1']\n", encoding="utf-8")
            self.assertEqual(cas_non_joues(faux, JoueurPython, racine), ["npm:X2"])
            (racine / "joueur.test.ts").write_text("import cas from '../contrats/cas-masquage.json'\nconst joues = ['X1', \"X2\"]\n", encoding="utf-8")
            self.assertEqual(cas_non_joues(faux, JoueurPython, racine), [])

    def test_chaque_cas_donne_une_entree_non_masquee_la_ou_une_regle_doit_agir_ou_est_un_temoin_de_format(self):
        """Revue R-144, m2 : une cellule attendue masquée déjà nulle en entrée ne prouve aucune règle. Chaque cas qui attend des cellules masquées
        en donne au moins une dont la valeur d'entrée n'est pas nulle, sinon il porte `witness` (témoin de format, annoncé comme tel)."""
        for cas in charger()["cases"]:
            if not cas["masked"] or cas.get("witness") is True:
                continue
            noms, lignes = tableau(cas)
            agit = any(lignes[rang][noms.index(colonne)] is not None for rang, colonne in cas["masked"])
            self.assertTrue(agit, f"{cas['id']} : toutes les cellules attendues masquées sont déjà nulles en entrée, ni règle ni témoin déclaré")

    def test_un_cas_ignore_par_le_joueur_fait_echouer_la_consommation(self):
        faux = {"players": ["python"], "cases": [
            {"id": "Z99", "kind": "masquer_vue"},                       # aucun test_cas_Z99
            {"id": "X1", "kind": "inconnue"},                           # sorte inconnue
            {"id": "X2", "kind": "masquer_vue"},
        ]}
        self.assertEqual(cas_non_joues(faux, JoueurPython), ["Z99", "X1"])

    def test_un_cas_saute_fait_echouer_la_consommation(self):
        class Saute(unittest.TestCase):
            @unittest.skip("sauté")
            def test_cas_S1(self):
                pass

        faux = {"players": ["python"], "cases": [{"id": "S1", "kind": "masquer_vue"}]}
        self.assertEqual(cas_non_joues(faux, Saute), ["S1"])

    def test_npm_liste_sans_joueur_typescript_fait_echouer_la_consommation(self):
        faux = {"players": ["python", "npm"], "cases": []}
        with tempfile.TemporaryDirectory() as dossier:
            vide = Path(dossier)
            self.assertEqual(cas_non_joues(faux, JoueurPython, vide), ["npm"])
            (vide / "contrat.test.ts").write_text("import cas from '../contrats/cas-masquage.json'\n", encoding="utf-8")
            self.assertEqual(cas_non_joues(faux, JoueurPython, vide), [])


if __name__ == "__main__":
    unittest.main()
