"""
L'oracle de masquage appliqué à la photo de plusieurs semaines avec produit (change du masquage des sommes, R-144, groupe 6, tâche 6.3 ; conception D8 amendée le
2026-10-28 et D15).

    bash tests/run_all.sh db     (la partie sans base : ce fichier n'ouvre aucune base)

L'oracle (tests/db/oracle_masquage.py, pur) joue la règle exactement comme elle est publiée : `masquer_vue` appliquée aux comptes bruts au plancher, avec
sa ligne du produit, sa chaîne de semaines, sa propagation et sa règle du voisin. Il n'énumère que les cellules masquées (les cellules publiées sont
fixées), sur un domaine plus large que le tirage plus le seuil. Propriété : aucune cellule masquée, ni aucun excès sous le seuil, n'a une seule valeur
possible, toutes les relations croisées. Largeur : le texte de la tâche 6.3 dit que celle de l'oracle égale celle de D15 ou est plus large ; c'est vrai
sur X23 et sur presque toutes les cellules des graines, mais une graine a une cellule dont l'oracle est plus étroit (3 contre 4 : D15
est une relaxation par intervalles). L'écart est fixé par un test et signalé à l'auteur, jamais tranché ici. Cas fixe : X23 fuit
sans D15 et ne fuit plus avec. Données inventées (équipes A et B, semaines de mars 2026) ; aucune ligne du Jira réel.
"""
import importlib.util
import random
import sys
import unittest
import unittest.mock
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

_spec = importlib.util.spec_from_file_location("oracle_masquage", RACINE / "tests" / "oracle_masquage" / "oracle_masquage.py")
oracle = importlib.util.module_from_spec(_spec)
sys.modules["oracle_masquage"] = oracle
_spec.loader.exec_module(oracle)

SEUIL = fv.PLANCHER
NOMS = ["week_start", "n_adopted", "team", "version_no", "found", "defects_created", "defects_without_affects", "resolved_week", "resolved_week_defects"]
PRODUIT = fv.PRODUIT
SEMAINES = ("2026-03-02", "2026-03-09", "2026-03-16")


class Photo:
    """Une unité : la structure des lignes d'équipe (semaine, équipe, version ; None pour la ligne sans version) et leurs cellules brutes (créés et sans
    affects pour une ligne sans version, le trouvé pour une ligne de version). Le produit est la somme des équipes, comme dans la vue."""

    def __init__(self, structure):
        self.structure = list(structure)

    def lignes(self, table):
        lignes = []
        for (semaine, equipe, vno), cellules in zip(self.structure, table):
            if vno is None:
                lignes.append((semaine, True, equipe, None, None, cellules[0], cellules[1], 20, 10))
            else:
                lignes.append((semaine, True, equipe, vno, cellules[0], None, None, None, None))
        for semaine in sorted({s for s, _, _ in self.structure}):
            libres = [c for (s, _, v), c in zip(self.structure, table) if s == semaine and v is None]
            lignes.append((semaine, True, PRODUIT, None, None, sum(c[0] for c in libres), sum(c[1] for c in libres), 20 * len(libres), 10 * len(libres)))
            for vno in sorted({v for s, _, v in self.structure if s == semaine and v is not None}):
                trouves = [c[0] for (s, _, v), c in zip(self.structure, table) if s == semaine and v == vno]
                lignes.append((semaine, True, PRODUIT, vno, sum(trouves), None, None, None, None))
        return lignes

    @staticmethod
    def brutes(lignes):
        return tuple((l[5], l[6]) if l[3] is None else (l[4],) for l in lignes)

    def complet(self, table):
        return self.brutes(self.lignes(table))

    def publier(self, table, seuil):
        cellules = fv.masquer_vue(fv.VUE_PHOTO, NOMS, self.lignes(table), seuil)
        image = []
        for ligne, c in zip(self.lignes(table), cellules):
            colonnes = ("defects_created", "defects_without_affects") if ligne[3] is None else ("found",)
            image.append(tuple(None if "masked" in c[col] else c[col]["value"] for col in colonnes))
        return tuple(image)

    def groupes(self):
        """(semaine, équipe) -> (rang de la ligne sans version, rangs des lignes de version)."""
        groupes = {}
        for rang, (semaine, equipe, vno) in enumerate(self.structure):
            libre, versions = groupes.setdefault((semaine, equipe), [None, []])
            if vno is None:
                groupes[(semaine, equipe)][0] = rang
            else:
                versions.append(rang)
        return groupes

    def coherente_groupe(self, table, libre, versions, pari_nul=False):
        """Le monde de l'oracle est celui où U = 0 (aucun défaut avec affects hors des versions retenues : les tables brutes n'ont pas de terme latent).
        `pari_nul` joue en plus la lecture « m = 0 » de l'attaquant (M7 a de la fiche R-20261104-6) : les défauts distincts valent la somme des trouvés."""
        crees, sans = table[libre]
        trouves = [table[r][0] for r in versions]
        if crees < sans:
            return False
        distincts = crees - sans
        if pari_nul:
            return distincts == sum(trouves)
        return (max(trouves) if trouves else 0) <= distincts <= sum(trouves)

    def coherente(self, table, pari=None):
        return all(self.coherente_groupe(table, libre, versions, pari == cle)
                   for cle, (libre, versions) in self.groupes().items() if libre is not None)

    def elaguer(self, table, pari=None):
        for cle, (libre, versions) in self.groupes().items():
            if libre is None:
                continue
            cellules = [table[libre][0], table[libre][1]] + [table[r][0] for r in versions]
            if None not in cellules and not self.coherente_groupe(table, libre, versions, pari == cle):
                return False
        return True

    def quantites(self, table):
        """L'excès m de chaque ligne à compléter : somme des trouvés moins les défauts distincts (créés - sans affects)."""
        sorties = {}
        for (semaine, equipe), (libre, versions) in self.groupes().items():
            if libre is not None and versions:
                sorties[(semaine, equipe)] = sum(table[r][0] for r in versions) - (table[libre][0] - table[libre][1])
        return sorties

    def analyser(self, brut, domaine=None):
        brut = tuple(tuple(c) for c in brut)
        if domaine is None:
            domaine = range(0, max(v for ligne in brut for v in ligne) + SEUIL + 1)
        return oracle.analyser_masquees(self.publier, brut, SEUIL, domaine, self.complet, self.coherente, self.elaguer, self.quantites)

    def analyser_paris_m_nul(self, brut, domaine=None):
        """La lecture « m = 0 » jouée par l'oracle (M7 a), une ligne à la fois comme l'attaquant : {(semaine, équipe): résultat} pour chaque ligne à
        compléter qui a une cellule masquée et dont le pari n'est pas contredit par l'image (au moins une table compatible). Sans `quantites` : l'excès
        nul est le pari lui-même, pas un secret. Une fuite ici est une cellule masquée à valeur unique sous le pari."""
        brut = tuple(tuple(c) for c in brut)
        if domaine is None:
            domaine = range(0, max(v for ligne in brut for v in ligne) + SEUIL + 1)
        observe = self.publier(brut, SEUIL)
        resultats = {}
        for cle, (libre, versions) in self.groupes().items():
            rangs = ([libre] if libre is not None else []) + versions
            if libre is None or not versions or not any(v is None for r in rangs for v in observe[r]):
                continue
            resultat = oracle.analyser_masquees(self.publier, brut, SEUIL, domaine, self.complet, lambda t, c=cle: self.coherente(t, c),
                                                lambda t, c=cle: self.elaguer(t, c))
            if resultat["compatibles"]:
                resultats[cle] = resultat
        return resultats


S1, S2, S3 = SEMAINES
X23_STRUCTURE = [(S1, "A", None), (S1, "A", 1), (S1, "A", 2), (S2, "A", None), (S2, "A", 3), (S2, "A", 4)]
X23_BRUT = ((20, 10), (10,), (6,), (24, 10), (14,), (5,))


def sans_propagation():
    """La règle d'avant D15 : les règles existantes seules (D3, D5-d et D2 jusqu'à leur point fixe), sans propager les bornes."""
    return unittest.mock.patch.object(fv._UnitePhoto, "propager", lambda self, regles, limites: None)


class UniteDeLOracle(unittest.TestCase):
    """Tests propres des variantes de l'oracle, sur une règle de deux cellules à somme fixée."""

    @staticmethod
    def publier(table, seuil):
        a, b = table[0]
        return ((None if a < seuil else a, None if b < seuil else b), (a + b,))

    def test_seules_les_cellules_masquees_sont_enumerees(self):
        compatibles = oracle.tables_compatibles_masquees(self.publier, ((2, 3),), SEUIL, range(0, 12))
        self.assertEqual(len(compatibles), 4)                                  # a + b = 5 avec a, b sous 5 : (1,4), (2,3), (3,2), (4,1) ; 0 + 5 et 5 + 0 publieraient 5
        self.assertTrue(all(t[0][0] + t[0][1] == 5 for t in compatibles))

    def test_une_cellule_masquee_sous_le_seuil_a_plusieurs_valeurs_sans_fuite(self):
        def publier(table, seuil):
            return ((None if table[0][0] < seuil else table[0][0],), (table[1][0],))
        resultat = oracle.analyser_masquees(publier, ((3,), (9,)), SEUIL, range(0, 12), lambda t: t, quantites=lambda t: {"q": t[0][0] + 1})
        self.assertEqual(resultat["fuites"], [])
        self.assertEqual(resultat["intervalles"][(0, 0)], (0, 4))
        self.assertEqual(resultat["quantites"]["q"], (1, 5))

    def test_une_cellule_a_valeur_unique_est_signalee(self):
        def publier(table, seuil):
            return ((None,), (table[0][0],))                                 # la cellule est masquée mais publiée à côté : une seule valeur
        resultat = oracle.analyser_masquees(publier, ((3,),), SEUIL, range(0, 12), lambda t: t)
        self.assertEqual(len(resultat["fuites"]), 1)
        self.assertIn("valeur unique", resultat["fuites"][0])

    def test_une_quantite_cachee_fixee_sous_le_seuil_est_une_fuite(self):
        def publier(table, seuil):
            return ((None,), (table[0][0] % 2,))                             # la parité est publiée : la quantité « 4 si pair » est fixée
        resultat = oracle.analyser_masquees(publier, ((3,),), SEUIL, range(0, 12), lambda t: t, quantites=lambda t: {"fixe": 1 if t[0][0] % 2 else 2})
        self.assertTrue(any("quantité cachée" in f for f in resultat["fuites"]))


class X23DeLOracle(unittest.TestCase):
    def test_x23_fuit_sans_la_propagation(self):
        """Avant D15 : le créé de la semaine deux est masqué par la chaîne seule ; la ligne (au moins 10 + 14) et la chaîne (au plus 20 + 4) le fixent à 24."""
        photo = Photo(X23_STRUCTURE)
        with sans_propagation():
            resultat = photo.analyser(X23_BRUT, domaine=range(0, 30))
        self.assertGreaterEqual(resultat["compatibles"], 1)
        self.assertEqual(resultat["intervalles"][(3, 0)], (24, 24))
        self.assertTrue(any("(3, 0) = 24" in fuite for fuite in resultat["fuites"]), resultat["fuites"])

    def test_x23_ne_fuit_plus_avec_la_propagation(self):
        photo = Photo(X23_STRUCTURE)
        resultat = photo.analyser(X23_BRUT, domaine=range(0, 30))
        self.assertGreaterEqual(resultat["compatibles"], 1)
        self.assertEqual(resultat["fuites"], [])
        self.assertGreaterEqual(resultat["plus_etroite"], 1)

    def test_la_largeur_de_l_oracle_egale_celle_de_d15_ou_la_depasse(self):
        photo = Photo(X23_STRUCTURE)
        resultat = photo.analyser(X23_BRUT, domaine=range(0, 30))
        lignes = photo.lignes(X23_BRUT)
        d15 = fv._largeurs_photo(NOMS, [dict(zip(NOMS, l)) for l in lignes], SEUIL)
        colonne = {0: "defects_created", 1: "defects_without_affects"}
        verifiees = 0
        for (i, j), largeur in resultat["largeurs"].items():
            nom = "found" if lignes[i][3] is not None else colonne[j]
            self.assertGreaterEqual(largeur, d15[(i, nom)], f"cellule {(i, j)} {nom}")      # le sens du texte de 6.3 : sur X23, l'oracle égale D15 ou est plus large
            verifiees += 1
        self.assertGreaterEqual(verifiees, 6)


def table_tiree(graine):
    """Deux équipes, trois semaines, deux versions par semaine : comptes cohérents (défauts distincts entre le plus grand trouvé et leur somme)."""
    hasard = random.Random(graine)
    structure, brut = [], []
    for equipe in ("A", "B"):
        for k, semaine in enumerate(SEMAINES):
            f1, f2 = hasard.choice([8, 9, 10, 11]), hasard.choice([8, 9, 10, 11])
            distincts = f1 + f2 - hasard.choice([5, 6, 7])      # un excès de 5 à 7 (défauts à plusieurs affects versions) : la ligne reste publiée en entier
            sans = hasard.choice([10, 11, 20, 21, 30, 31, 40])
            structure += [(semaine, equipe, None), (semaine, equipe, 2 * k + 1), (semaine, equipe, 2 * k + 2)]
            brut += [(sans + distincts, sans), (f1,), (f2,)]
    return structure, tuple(brut)


GRAINES = (1, 5, 6, 10, 11, 16)    # graines fixes, choisies pour que l'unité ait une à deux cellules d'équipe masquées (l'énumération reste de quelques secondes)
MAX_INCONNUES = 2                  # cellules d'équipe masquées au plus : au-delà, l'énumération est trop longue (limite assumée de l'oracle)
_ANALYSES: list = []


def analyses():
    """Les unités des graines fixes et leur analyse par l'oracle, calculées une seule fois : (graine, photo, brut, résultat)."""
    if not _ANALYSES:
        for graine in GRAINES:
            structure, brut = table_tiree(graine)
            photo = Photo(structure)
            try:
                image = photo.publier(brut, SEUIL)
            except fv.MasquageInstable:
                continue
            inconnues = sum(1 for ligne in image[:len(brut)] for v in ligne if v is None)
            if 1 <= inconnues <= MAX_INCONNUES:
                _ANALYSES.append((graine, photo, brut, photo.analyser(brut)))
    return _ANALYSES


class PropositionSurLesUnitesTirees(unittest.TestCase):
    """Propriété de D8 amendée : aucune cellule masquée, aucun excès sous le seuil n'a une seule valeur possible, toutes les relations croisées."""

    def test_des_unites_sont_analysees(self):
        self.assertGreaterEqual(len(analyses()), 4, "trop peu d'unités tirées avec des cellules masquées à énumérer : changer les graines")
        self.assertIn(6, [g for g, *_ in analyses()], "la graine 6 doit rester analysée (revue finale du 2026-11-04, cas 4 de M8)")

    def test_aucune_fuite_sur_les_unites_tirees(self):
        for graine, photo, brut, resultat in analyses():
            with self.subTest(graine=graine):
                self.assertGreaterEqual(resultat["compatibles"], 1, f"la table brute de la graine {graine} doit rester compatible avec son image")
                self.assertEqual(resultat["fuites"], [], f"fuite pour la graine {graine} : {brut}")

    def test_largeur_de_l_oracle_contre_celle_de_d15_ecart_connu_avec_le_texte_de_6_3(self):
        """Le texte de 6.3 : la largeur de l'oracle égale celle de D15 ou est plus large. Sur les graines, c'est vrai de presque toutes les cellules (D15
        accorde à l'attaquant la règle enregistrée de chaque cellule masquée : plus étroit que l'exact), mais deux graines ont une cellule dont l'oracle est
        plus étroit que D15 (3 contre 4 pour la graine 10 : la relaxation par intervalles perd de l'information ; la graine 6 en avait un, 8 contre 9, avant
        M1 et M7). Écart signalé à l'auteur, jamais tranché ici : ce test fixe la liste des graines concernées, il échoue si elle change."""
        colonne = {0: "defects_created", 1: "defects_without_affects"}
        plus_etroites = {}
        for graine, photo, brut, resultat in analyses():
            lignes = photo.lignes(brut)
            d15 = fv._largeurs_photo(NOMS, [dict(zip(NOMS, l)) for l in lignes], SEUIL)
            for (i, j), largeur in resultat["largeurs"].items():
                nom = "found" if lignes[i][3] is not None else colonne[j]
                self.assertGreaterEqual(d15[(i, nom)], 1, f"graine {graine}, cellule {(i, j)} {nom} : D15 ne laisse jamais une seule valeur")
                if largeur < d15[(i, nom)]:
                    plus_etroites[graine] = (largeur, d15[(i, nom)])
        # M8 (R-20261104-12) : la graine 6 n'a plus d'écart (8 contre 9) depuis M1 et M7 : elle reste analysée et sans fuite (test précédent), D15 y
        # donne des largeurs de 2 contre 8 à l'oracle (lectures « U = 0 » et « m = 0 » jouées par ligne) ; la liste attendue est celle de la revue.
        self.assertEqual(plus_etroites, {10: (3, 4)})


class RestrictionsDuMoteurContreLOracle(unittest.TestCase):
    """M5 de la fiche R-20261104-6 : les écarts 3 et 5 restreignent D15 ; la condition de l'auteur est que l'oracle ne trouve, dans aucun des deux cas, une
    cellule masquée par D15 que le moteur publie. Une restriction qui démasquerait une cellule de D15 se verrait ici comme une valeur unique d'une cellule
    masquée, ou comme un excès fixé sous le seuil sur une ligne à plusieurs termes."""

    def test_ecart_3_l_exemption_d_un_exces_fixe_ne_vaut_que_pour_une_ligne_a_un_seul_terme_retenu(self):
        # un seul terme : m = 0 par structure (l'oracle le voit fixé, c'est la structure de la ligne et non un secret) ; aucune cellule n'a une valeur unique
        photo = Photo([(S1, "A", None), (S1, "A", 1)])
        resultat = photo.analyser(((30, 10), (20,)))
        self.assertTrue(all("quantité cachée" in f for f in resultat["fuites"]), resultat["fuites"])
        # plusieurs termes, excès sous le seuil (25 - 5 = 20 défauts distincts pour 22 trouvés) : l'excès n'est pas fixé, aucune fuite d'aucune sorte
        photo = Photo([(S1, "A", None), (S1, "A", 1), (S1, "A", 2)])
        for brut in (((25, 5), (18,), (4,)), ((25, 5), (14,), (9,))):
            resultat = photo.analyser(brut)
            self.assertEqual(resultat["fuites"], [], brut)
            self.assertGreater(resultat["compatibles"], 0)

    @staticmethod
    def unite_toute_publiee(structure, brut):
        """L'unité de la photo, ses règles non appliquées puis toutes ses cellules rendues publiées : seul le contrôle de l'excès de D15 (étape 4) peut
        alors épingler quelque chose, puisqu'aucune cellule n'est masquée."""
        photo = Photo(structure)
        rangees = [dict(zip(NOMS, ligne)) for ligne in photo.lignes(brut)]
        vis = [{} for _ in rangees]
        prises = []

        def capturer(self, regles, limites):
            prises.append(self)
        with unittest.mock.patch.object(fv._UnitePhoto, "propager", capturer):
            fv._masque_photo(NOMS, rangees, SEUIL, [set() for _ in rangees], vis)
        for i, cellules in enumerate(vis):
            vis[i] = {c: True for c in cellules}
        return prises[0]

    def test_ecart_3_le_moteur_n_epingle_l_exces_que_hors_exemption(self):
        """M10 (a) de la revue finale du 2026-11-04 (R-20261104-13) : un excès fixé sous le seuil dans la lecture « U = 0 » de sa ligne est épinglé
        quand la ligne a plusieurs termes retenus (excès 22 - 20 = 2 ; avant la correction, le contrôle ne lisait que « m libre », où U sans borne
        haute laisse l'excès libre : jamais épinglé) ; une ligne à un seul terme retenu (excès nul par structure) est exemptée."""
        unite = self.unite_toute_publiee([(S1, "A", None), (S1, "A", 1), (S1, "A", 2)], ((25, 5), (18,), (4,)))
        u = unite._construire()
        epingle, _ = unite._epingles(u, None)
        self.assertIsNotNone(epingle, "l'excès fixé à 2 dans « U = 0 » doit être épinglé")
        self.assertEqual(u["definition"][epingle][0], "m")
        unite = self.unite_toute_publiee([(S1, "A", None), (S1, "A", 1)], ((30, 10), (20,)))
        u = unite._construire()
        epingle, _ = unite._epingles(u, None)
        self.assertIsNone(epingle, "un seul terme retenu : l'excès nul est m = 0 par structure, exempté")

    def test_m10_un_exces_fixe_d_au_moins_le_seuil_n_epingle_rien(self):
        """Seul un excès fixé sous le seuil est épinglé : un excès de 7, fixé dans la lecture « U = 0 », n'épingle pas sa variable (le pari « m = 0 »
        et « U = 0 et m = 0 » ne sont jamais contrôlés : m = 0 y est le pari lui-même)."""
        unite = self.unite_toute_publiee([(S1, "A", None), (S1, "A", 1), (S1, "A", 2)], ((25, 5), (18,), (9,)))      # 27 - 20 = 7
        u = unite._construire()
        epingle, _ = unite._epingles(u, None)
        self.assertTrue(epingle is None or u["definition"][epingle][0] == "c", epingle)

    def test_ecart_5_une_cellule_sans_borne_haute_garde_toujours_au_moins_deux_valeurs_pour_l_oracle(self):
        """Écart 5 (a) : l'exception de BORNES « seule la règle primaire » est caduque, une cellule sans règle n'a pas de borne haute. L'oracle ne trouve
        aucune cellule masquée du moteur, borne haute ou non, dont la largeur serait nulle (X23 et les unités tirées)."""
        verifiees = 0
        photo = Photo(X23_STRUCTURE)
        cas = [(photo, X23_BRUT, range(0, 30))] + [(p, b, None) for _, p, b, _ in analyses()]
        for p, brut, domaine in cas:
            resultat = p.analyser(brut, domaine=domaine) if domaine is not None else p.analyser(brut)
            lignes = p.lignes(brut)
            d15 = fv._largeurs_photo(NOMS, [dict(zip(NOMS, l)) for l in lignes], SEUIL)
            colonne = {0: "defects_created", 1: "defects_without_affects"}
            for (i, j), largeur in resultat["largeurs"].items():
                nom = "found" if lignes[i][3] is not None else colonne[j]
                self.assertGreaterEqual(largeur, 1, f"cellule {(i, j)} {nom} fixée par l'oracle")            # sans borne haute ou non, jamais une valeur unique
                self.assertGreaterEqual(d15[(i, nom)], 1)
                verifiees += 1
            self.assertEqual(resultat["fuites"], [])
        self.assertGreaterEqual(verifiees, 6)


CAS_A_12_STRUCTURE = [(S1, "A", None), (S1, "B", None), (S1, "B", 1)]
CAS_A_12_BRUT = ((12, 12), (40, 27), (13,))


def fuites_hors_exemption(photo, fuites):
    """Les fuites, moins la seule exemption admise par l'écart 3 : la quantité cachée (l'excès m) d'une ligne à un seul terme retenu, nulle par
    structure. Toute cellule masquée à valeur unique, et l'excès de toute autre ligne, restent des fuites."""
    un_seul_terme = {cle for cle, (libre, versions) in photo.groupes().items() if libre is not None and len(versions) == 1}
    return [f for f in fuites if not (f.startswith("quantité cachée") and any(str(cle) in f for cle in un_seul_terme))]


class CasInventeEquipeADeLOracle(unittest.TestCase):
    """Condition de la tâche 20.1 (C7 de la revue de masquage des groupes 6 et 20 ; réponse Q3 (a) de l'auteur du 2026-11-05) : le cas inventé (12, 12) de
    la revue 19.1 (A créés 12, sans affects 12, sans ligne de version ; B créés 40, sans affects 27, trouvé 13 ; produit la somme). Aucune cellule masquée
    n'a une valeur unique, ni dans « m libre » ni sous le pari « m = 0 » ; seule l'exemption de l'écart 3 est filtrée (l'excès de B, un seul terme retenu,
    m_B = 0 par structure)."""

    def test_aucune_fuite_hors_exemption_d_un_seul_terme(self):
        photo = Photo(CAS_A_12_STRUCTURE)
        resultat = photo.analyser(CAS_A_12_BRUT)
        self.assertGreaterEqual(resultat["compatibles"], 1)
        self.assertEqual(fuites_hors_exemption(photo, resultat["fuites"]), [], resultat["fuites"])
        for cle, pari in photo.analyser_paris_m_nul(CAS_A_12_BRUT).items():
            self.assertGreaterEqual(pari["compatibles"], 1, cle)
            self.assertEqual(fuites_hors_exemption(photo, pari["fuites"]), [], cle)


CAS_3_STRUCTURE =[(S1, "A", None), (S1, "A", 1), (S1, "A", 2), (S2, "A", None), (S2, "A", 3), (S2, "A", 4)]
CAS_3_BRUT = ((40, 5), (30,), (20,), (43, 5), (20,), (18,))


class LectureMNulDeLOracle(unittest.TestCase):
    """M7 (a) de la fiche R-20261104-6 : l'oracle joue aussi la lecture « m = 0 » (le monde de ses tables est déjà celui où U = 0), une ligne à la fois.
    Sans cela, la condition de M5 (aucune restriction ne démasque une cellule que D15 masque) n'était tenue que pour la lecture « m libre »."""

    def test_le_cas_3_fuit_sans_la_propagation_sous_u_nul_et_m_nul(self):
        """Témoin : sans D15, le créé de la semaine deux (masqué par la chaîne seule) vaut 43 sous le pari ; l'oracle le voit."""
        photo = Photo(CAS_3_STRUCTURE)
        with sans_propagation():
            paris = photo.analyser_paris_m_nul(CAS_3_BRUT)
        self.assertIn((S2, "A"), paris)
        self.assertTrue(any("(3, 0) = 43" in fuite for fuite in paris[(S2, "A")]["fuites"]), paris[(S2, "A")]["fuites"])

    def test_le_cas_3_ne_fuit_plus_avec_la_propagation_sous_u_nul_et_m_nul(self):
        photo = Photo(CAS_3_STRUCTURE)
        paris = photo.analyser_paris_m_nul(CAS_3_BRUT)
        for cle, resultat in paris.items():
            self.assertEqual(resultat["fuites"], [], cle)

    def test_x23_et_les_unites_tirees_ne_fuient_pas_sous_la_lecture_m_nul(self):
        cas = [(Photo(X23_STRUCTURE), X23_BRUT, range(0, 30))] + [(p, b, None) for _, p, b, _ in analyses()]
        for photo, brut, domaine in cas:
            for cle, resultat in photo.analyser_paris_m_nul(brut, domaine).items():
                self.assertEqual(resultat["fuites"], [], f"{cle} : {brut}")


class ExcesFixeSousLeSeuil(unittest.TestCase):
    """M11 (a) de la revue finale du 2026-11-04 (R-20261104-13), premier cas : un excès m_r fixé sous le seuil dans « U = 0 » sur une ligne à plusieurs
    termes dont une cellule est masquée (un trouvé sous le seuil). Après M10 (a), l'oracle (monde U = 0, l'excès comme quantité protégée) ne trouve
    aucune valeur unique, ni de cellule masquée, ni de l'excès."""

    def test_aucune_valeur_unique_sur_une_ligne_a_cellules_masquees_et_exces_sous_le_seuil(self):
        photo = Photo([(S1, "A", None), (S1, "A", 1), (S1, "A", 2)])
        # excès 22 - 20 = 2 ; 23 - 22 = 1 ; 20 - 20 = 0 ; 23 - 21 = 2 : chaque ligne a un trouvé sous 5 (masqué) et un excès sous le seuil
        for brut in (((25, 5), (18,), (4,)), ((27, 5), (19,), (4,)), ((24, 4), (17,), (3,)), ((26, 5), (18,), (3,))):
            with self.subTest(brut=brut):
                self.assertTrue(any(v is None for ligne in photo.publier(brut, SEUIL) for v in ligne), "la ligne doit avoir une cellule masquée")
                resultat = photo.analyser(brut)
                self.assertGreater(resultat["compatibles"], 0)
                self.assertEqual(resultat["fuites"], [], brut)


SEUIL_7 = 7


class NulleAuSeuilReleve:
    """M11 (a), second cas : seuil relevé à 7 et une cellule nulle de la vue (sans affects de la ligne sans version) dans une colonne que BORNES dit
    « primaire seule ». Une équipe, une ligne sans version et deux versions. Table brute : ((créés, sans), (trouvé 1,), (trouvé 2,)). La nulle n'est
    pas libre (M12) : `publier` rejoue la vue au plancher sur la table complète et n'écarte que les candidates où sans affects ne sort pas nulle."""

    @staticmethod
    def lignes(t):
        (a, s), (f1,), (f2,) = t
        return [(S1, True, "A", None, None, a, s, 20, 10), (S1, True, "A", 1, f1, None, None, None, None), (S1, True, "A", 2, f2, None, None, None, None)]

    @staticmethod
    def image(lignes, seuil):
        cellules = fv.masquer_vue(fv.VUE_PHOTO, NOMS, lignes, seuil)
        return [tuple(None if "masked" in c[col] else c[col]["value"] for col in (("defects_created", "defects_without_affects") if l[3] is None
                                                                                   else ("found",))) for l, c in zip(lignes, cellules)]

    @classmethod
    def publier(cls, t, seuil):
        """M12 (R-20261104-14) : la vue est rejouée au plancher sur la table candidate complète, sans affects réel compris ; une candidate dont sans affects
        ne sort pas nulle au plancher est écartée (« ecartee », jamais égale à l'image observée) ; les cellules nulles du plancher sont ensuite remises à
        None dans les lignes que l'on masque au seuil (la vue relevée est lue sur la publication du plancher, pas sur des comptes bruts)."""
        lignes = cls.lignes(t)
        try:
            plancher = cls.image(lignes, SEUIL)
            if plancher[0][1] is not None:
                return "ecartee"
            relevees = [lignes[0][:5] + plancher[0] + lignes[0][7:]] + [l[:4] + (p[0],) + l[5:] for l, p in zip(lignes[1:], plancher[1:])]
            return tuple(cls.image(relevees, seuil))
        except fv.MasquageInstable:
            return "instable"

    @staticmethod
    def coherente(t):
        """Monde U = 0 : les défauts distincts (créés - sans affects) sont entre le plus grand trouvé et leur somme."""
        (a, s), (f1,), (f2,) = t
        return a >= s and max(f1, f2) <= a - s <= f1 + f2

    @classmethod
    def elaguer(cls, t):
        (a, s), (f1,), (f2,) = t
        return True if None in (a, s, f1, f2) else cls.coherente(t)

    @staticmethod
    def quantites(t):
        (a, s), (f1,), (f2,) = t
        return {"exces": f1 + f2 - (a - s)}


class Ecart5NulleAuSeuilReleve(unittest.TestCase):
    def test_aucune_valeur_unique_pour_une_nulle_a_seuil_releve_dans_une_colonne_primaire_seule(self):
        verifiees = 0
        # sans affects sous le plancher : la nulle vient de la règle primaire ; au plancher ou au-dessus : elle vient de D2 (le trouvé masqué de la ligne)
        for brut in (((30, 3), (20,), (3,)), ((31, 4), (21,), (2,)), ((30, 8), (20,), (3,)), ((30, 7), (21,), (4,))):
            with self.subTest(brut=brut):
                plancher = NulleAuSeuilReleve.image(NulleAuSeuilReleve.lignes(brut), SEUIL)
                self.assertIsNone(plancher[0][1], "sans affects sort nulle au plancher")
                image = NulleAuSeuilReleve.publier(brut, SEUIL_7)
                self.assertNotIn(image, ("instable", "ecartee"))
                self.assertIsNone(image[0][1], "sans affects, nulle dans la vue, est masquée")
                resultat = oracle.analyser_masquees(NulleAuSeuilReleve.publier, brut, SEUIL_7, range(0, max(max(c) for c in brut) + SEUIL_7 + 1),
                                                    lambda t: t, NulleAuSeuilReleve.coherente, NulleAuSeuilReleve.elaguer, NulleAuSeuilReleve.quantites)
                self.assertGreater(resultat["compatibles"], 0)
                self.assertEqual(resultat["fuites"], [], f"{brut} : intervalles {resultat['intervalles']}")
                verifiees += 1
        self.assertEqual(verifiees, 4)


if __name__ == "__main__":
    unittest.main()
