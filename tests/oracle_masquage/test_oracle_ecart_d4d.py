"""
L'oracle de masquage sur l'écart D4 (d) rétabli : une ligne d'équipe, ou du produit, sans ligne de version retenue cette semaine-là (R-20261106-22,
qui remplace R-20261105-6 Q4 (a) ; revue du 2026-11-06 des chemins de démasquage de 0035, C1 et C1').

    bash tests/run_all.sh oracle_masquage     (aucune base)

Règle rétablie (celle de flow.photo_serie de 0022, l. 192-196) : sans ligne de version, la relation à compléter se lit avec m = 0 terme caché publié, l'excès
(créés - sans affects - 0) est sous le seuil ou non lu, et D2 masque sans affects puis créés. Même règle pour la ligne du produit.

Trois familles de tests, sur des données inventées (équipe A, semaines de mars 2026) :
  - une semaine sans ligne de version, équipe et produit : toutes les cellules libres sont masquées, l'oracle ne trouve aucune fuite ;
  - plusieurs semaines (la cascade C1' de la revue : une semaine rendue visible change l'ancre de D5-d des semaines suivantes) ;
  - le balayage 0 <= w <= c <= 30 (w : sans affects, c : créés), la vérification de session du 2026-11-05 entrée dans tests/.
Propriété commune : aucune cellule ne devient visible par rapport au comportement de main d'avant 0035 (8aae5db3 et la migration 0022). Le lecteur Python
d'alors ne masquait pas la ligne sans version (il publiait 40 et 10) ; la vue de 0022, elle, la masquait : la référence est donc la plus stricte des deux,
la vue de 0022, rejouée ici par un portage de flow.photo_serie (`serie_0022`), et la ligne rétablie ne doit rien publier de plus.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import flow_views as fv  # noqa: E402
import test_oracle_propagation as tp  # noqa: E402

S1, S2, S3 = tp.S1, tp.S2, tp.S3
SEUIL = tp.SEUIL
COLONNES = ("defects_created", "defects_without_affects")


class PhotoSansTermeLibre(tp.Photo):
    """La photo de l'oracle, avec un monde où les défauts d'une ligne sans ligne de version retenue ne sont pas bornés : les versions non retenues
    portent des défauts (U libre, D4 (d)), la seule relation vraie est créés >= sans affects. Une ligne avec versions garde la cohérence de la classe mère."""

    def coherente_groupe(self, table, libre, versions, pari_nul=False):
        if not versions:
            crees, sans = table[libre]
            return crees >= sans
        return super().coherente_groupe(table, libre, versions, pari_nul)


def serie_0022(crees, sans, ok_dc, ok_dwa, np_, nc, sv):
    """Portage de flow.photo_serie (migration 0022, l. 144-215), la règle d'avant 0035 pour une série de lignes sans version : D5-d puis D2 sur chaque
    semaine, repassés jusqu'à un point fixe. Rend (visibilité des créés, visibilité des sans affects) par semaine. np_ : termes cachés publiés ; nc : tous
    les termes cachés ; sv : somme des trouvés visibles."""
    n = len(crees)
    dc, dwa = list(ok_dc), list(ok_dwa)
    for _ in range(2 * n + 1):
        avant = (list(dc), list(dwa))
        dernier_c = dernier_a = None
        for i in range(n):
            if dc[i]:
                if dernier_c is not None and 1 <= abs(crees[i] - dernier_c) <= 4:
                    dc[i] = False
                else:
                    dernier_c = crees[i]
            if dwa[i]:
                if dernier_a is not None and 1 <= abs(sans[i] - dernier_a) <= 4:
                    dwa[i] = False
                else:
                    dernier_a = sans[i]
        for i in range(n):
            besoin = False
            if dc[i]:
                for m in (np_[i], nc[i]):
                    if dwa[i]:
                        lu = (m >= 1 and (m < 2 or crees[i] - sans[i] - sv[i] < 5 or crees[i] - sans[i] - sv[i] == 4 * m)) \
                            or (m == 0 and sv[i] - (crees[i] - sans[i]) < 5)
                    else:
                        lu = 1 + m < 2 or crees[i] - sv[i] < 5 or crees[i] - sv[i] == 4 * (1 + m)
                    besoin = besoin or lu
            nouveau_dc = dc[i] and not (besoin and not dwa[i])
            nouveau_dwa = dwa[i] and not besoin
            dc[i], dwa[i] = nouveau_dc, nouveau_dwa
        if (dc, dwa) == avant:
            return dc, dwa
    raise AssertionError("le portage de photo_serie ne se stabilise pas")


def publiee_en_0022(photo, brut):
    """Les cellules (créés, sans affects) que la vue de 0022 publie pour la série de l'équipe A : un couple de booléens par semaine, dans l'ordre des
    semaines. Les départs sont les cellules publiées avant la série : la règle primaire (< 5) et la paire (créés - sans affects >= 5)."""
    semaines = sorted({s for s, _, _ in photo.structure})
    crees, sans, np_, nc, sv, ok_dc, ok_dwa = [], [], [], [], [], [], []
    for s in semaines:
        libre = next(c for (sem, _, v), c in zip(photo.structure, brut) if sem == s and v is None)
        trouves = [c[0] for (sem, _, v), c in zip(photo.structure, brut) if sem == s and v is not None]
        crees.append(libre[0])
        sans.append(libre[1])
        np_.append(sum(1 for f in trouves if f < SEUIL))
        nc.append(sum(1 for f in trouves if f < SEUIL))          # aucune version non retenue dans ces cas
        sv.append(sum(f for f in trouves if f >= SEUIL))
        ok_dc.append(libre[0] >= SEUIL)
        ok_dwa.append(libre[1] >= SEUIL and libre[0] - libre[1] >= SEUIL)
    dc, dwa = serie_0022(crees, sans, ok_dc, ok_dwa, np_, nc, sv)
    return list(zip(dc, dwa))


def publiees_maintenant(photo, brut):
    """Pour l'équipe A puis le produit, un couple (créés publiés, sans affects publiés) par semaine, lu dans l'image de masquer_vue au plancher."""
    image = photo.publier(brut, SEUIL)
    lignes = photo.lignes(brut)
    sorties = {}
    for equipe in ("A", fv.PRODUIT):
        par_semaine = {}
        for ligne, cellules in zip(lignes, image):
            if ligne[2] == equipe and ligne[3] is None:
                par_semaine[ligne[0]] = (cellules[0] is not None, cellules[1] is not None)
        sorties[equipe] = [par_semaine[s] for s in sorted(par_semaine)]
    return sorties


class ProprieteCommune:
    """Mixin : les trois affirmations de chaque cas. Les classes filles donnent STRUCTURE, BRUT, VISIBLE_ATTENDU et le domaine de l'oracle."""
    STRUCTURE: list
    BRUT: tuple
    VISIBLE_ATTENDU: list            # par semaine : (créés publiés, sans affects publiés), pour l'équipe A comme pour le produit
    DOMAINE = None

    def setUp(self):
        self.photo = PhotoSansTermeLibre(self.STRUCTURE)

    def test_les_cellules_libres_publiees_sont_celles_attendues_pour_l_equipe_et_le_produit(self):
        maintenant = publiees_maintenant(self.photo, self.BRUT)
        self.assertEqual(maintenant["A"], self.VISIBLE_ATTENDU)
        self.assertEqual(maintenant[fv.PRODUIT], self.VISIBLE_ATTENDU)

    def test_aucune_cellule_ne_devient_visible_par_rapport_a_main_d_avant_0035(self):
        avant = publiee_en_0022(self.photo, self.BRUT)
        maintenant = publiees_maintenant(self.photo, self.BRUT)
        for equipe, lues in maintenant.items():
            for semaine, (apres, ancien) in enumerate(zip(lues, avant)):
                for colonne, (v_apres, v_avant) in zip(COLONNES, zip(apres, ancien)):
                    if v_apres:
                        self.assertTrue(v_avant, f"{equipe}, semaine {semaine + 1}, {colonne} : publiée maintenant, masquée par la vue de 0022")

    def test_l_oracle_ne_trouve_aucune_fuite(self):
        resultat = self.photo.analyser(self.BRUT, domaine=self.DOMAINE)
        self.assertGreaterEqual(resultat["compatibles"], 1, "la table brute doit rester compatible avec son image")
        self.assertEqual(resultat["fuites"], [], resultat["fuites"])


class UneSemaineSansLigneDeVersion(ProprieteCommune, unittest.TestCase):
    """Le cas du test fixe de tests/db/test_masquage_somme_vues.py : A créés 40, sans affects 10, aucune ligne de version ; le produit reprend A. Sans la
    règle, les deux étaient publiés (le garde-fou `nterms > 0` de 0035) ; avec elle, tout est masqué, comme dans 0022."""
    STRUCTURE = [(S1, "A", None)]
    BRUT = ((40, 10),)
    VISIBLE_ATTENDU = [(False, False)]


class PlusieursSemainesCascade(ProprieteCommune, unittest.TestCase):
    """Cascade C1' : la semaine 1 n'a pas de ligne de version (créés 10, sans affects 5), les semaines 2 et 3 en ont deux, de trouvé 5 chacune (défauts
    distincts 5, excès 5). Créés 10, 12, 15 et sans affects 5, 7, 10 : si la semaine 1 reste publiée, elle devient l'ancre de D5-d et masque la
    semaine 2 (écart 2) ; la semaine 3 (écart 5 avec l'ancre) reste publiée. Avec la règle rétablie, la semaine 1 est masquée comme dans 0022 et les
    créés et sans affects de la semaine 3 sont les seuls publiés."""
    STRUCTURE = [(S1, "A", None), (S2, "A", None), (S2, "A", 1), (S2, "A", 2), (S3, "A", None), (S3, "A", 3), (S3, "A", 4)]
    BRUT = ((10, 5), (12, 7), (5,), (5,), (15, 10), (5,), (5,))
    VISIBLE_ATTENDU = [(False, False), (False, False), (True, True)]
    DOMAINE = range(0, 22)


class Balayage(unittest.TestCase):
    """La vérification de session du 2026-11-05 (R-20261105-6, Q4 (a)), entrée dans tests/ : une équipe sans ligne de version, créés c, sans affects w,
    0 <= w <= c <= 30 (496 couples), le produit reprenant l'équipe. Avec la règle rétablie, aucune cellule libre n'est publiée, ni pour l'équipe ni pour
    le produit, et aucune ne l'est de plus que dans 0022."""

    def test_aucune_cellule_publiee_pour_les_496_couples(self):
        verifies = 0
        for c in range(31):
            for w in range(c + 1):
                photo = PhotoSansTermeLibre([(S1, "A", None)])
                brut = ((c, w),)
                maintenant = publiees_maintenant(photo, brut)
                avant = publiee_en_0022(photo, brut)
                for equipe, lues in maintenant.items():
                    self.assertEqual(lues, [(False, False)], f"{equipe}, créés {c}, sans affects {w}")
                    for apres, ancien in zip(lues, avant):
                        for v_apres, v_avant in zip(apres, ancien):
                            self.assertFalse(v_apres and not v_avant, f"{equipe}, créés {c}, sans affects {w}")
                verifies += 1
        self.assertEqual(verifies, 496)

    def test_l_oracle_ne_trouve_aucune_fuite_sur_une_grille_du_balayage(self):
        verifies = 0
        for c, w in ((0, 0), (4, 0), (5, 0), (5, 5), (12, 3), (12, 12), (30, 0), (30, 25), (30, 30)):
            with self.subTest(creees=c, sans_affects=w):
                photo = PhotoSansTermeLibre([(S1, "A", None)])
                resultat = photo.analyser(((c, w),), domaine=range(0, c + SEUIL + 1))
                self.assertGreaterEqual(resultat["compatibles"], 1)
                self.assertEqual(resultat["fuites"], [], resultat["fuites"])
                verifies += 1
        self.assertEqual(verifies, 9)


class DonneesReecritesDeLOracle(unittest.TestCase):
    """R-20261106-24 (a) : les données réécrites des tests existants de flow_views passent par l'oracle, avec les fonctions existantes de
    test_oracle_propagation (`Photo`, `fuites_hors_exemption`, `analyser_paris_m_nul`). La photo de l'oracle ajoute toujours la ligne du produit, somme des
    équipes ; les tests 6, 7, 9 et 10 ont la même ligne du produit (les colonnes des résolus, hors des relations de créés, de sans affects et des trouvés,
    diffèrent seules). Aucune cellule masquée n'a une valeur unique, ni dans « m libre » ni sous le pari « m = 0 » ; seule l'exemption de l'écart 3 (l'excès
    d'une ligne à un seul terme retenu, nul par structure) est filtrée.
    Hors de cette classe, et rapportés à l'auteur : les données de P5DonneUneBorneBasseAUP (tests 4 et 5 ; sept cellules d'équipe masquées sur un domaine
    de 0 à 43, de l'ordre de 10 ** 8 tables à énumérer) ; les cas 1 (X8b), 3 (JeuQ3EchecFerme) et 8 (D3 avant D5-d), dont les données ont des nuls de la vue
    que la photo de l'oracle, à cellules entières, ne représente pas."""

    def verifier(self, structure, brut):
        photo = tp.Photo(structure)
        resultat = photo.analyser(brut)
        self.assertGreaterEqual(resultat["compatibles"], 1, "la table brute doit rester compatible avec son image")
        self.assertEqual(tp.fuites_hors_exemption(photo, resultat["fuites"]), [], resultat["fuites"])
        for cle, pari in photo.analyser_paris_m_nul(brut).items():
            self.assertGreaterEqual(pari["compatibles"], 1, cle)
            self.assertEqual(tp.fuites_hors_exemption(photo, pari["fuites"]), [], (cle, pari["fuites"]))
        return photo

    @staticmethod
    def masquees_libres(photo, brut):
        """(équipe, colonne) masqués des lignes sans version, dans l'image de masquer_vue au plancher."""
        return {(ligne[2], colonne) for ligne, cellules in zip(photo.lignes(brut), photo.publier(brut, SEUIL)) if ligne[3] is None
                for colonne, valeur in zip(COLONNES, cellules) if valeur is None}

    def test_ordre_de_la_ligne_produit_tests_9_et_10(self):
        """OrdreDeLaLigneProduit, d3_avant_d2 et d5_d_avant_d2 (tests/flow_views/test_oracle_masquer_vue.py) : A 6 / 2, trouvé v3 = 4 ; B 6 / 5, trouvé
        v1 = 1. Les cellules masquées sont celles de l'assertion du test 9."""
        structure = [(S1, "A", None), (S1, "A", 3), (S1, "B", None), (S1, "B", 1)]
        brut = ((6, 2), (4,), (6, 5), (1,))
        photo = self.verifier(structure, brut)
        self.assertEqual(self.masquees_libres(photo, brut), {("A", "defects_created"), ("A", "defects_without_affects"), ("B", "defects_without_affects"),
                                                              (fv.PRODUIT, "defects_created"), (fv.PRODUIT, "defects_without_affects")})

    def test_voisine_seule_candidate_tests_6_et_7(self):
        """VoisineSeuleCandidate (tests/flow_views/test_masquage_p5_voisine_seule.py) : B 5 / 4, trouvé v3 = 1 ; C 12 / 4, trouvés v1 = 5 et v3 = 3. Les
        créés de B sont masqués (la voisine seule candidate)."""
        structure = [(S1, "B", None), (S1, "B", 3), (S1, "C", None), (S1, "C", 1), (S1, "C", 3)]
        brut = ((5, 4), (1,), (12, 4), (5,), (3,))
        photo = self.verifier(structure, brut)
        self.assertIn(("B", "defects_created"), self.masquees_libres(photo, brut))

    def test_semaines_retenues_d5_d_cas_11(self):
        """CellulesDeLaPhoto, D5-d 40 puis 43, et 40 puis 45 (tests/flow_views/test_photo_versions.py), une équipe sur deux semaines, deux versions par
        semaine ; la photo de l'oracle y ajoute la ligne du produit (égale à l'équipe), que le test n'a pas."""
        semaines = ("2026-11-02", "2026-11-09")
        structure = [(semaines[0], "Alpha", None), (semaines[0], "Alpha", 1), (semaines[0], "Alpha", 2),
                     (semaines[1], "Alpha", None), (semaines[1], "Alpha", 1), (semaines[1], "Alpha", 2)]
        for brut in (((40, 15), (20,), (15,), (43, 15), (20,), (18,)), ((40, 15), (20,), (15,), (45, 15), (20,), (20,))):
            with self.subTest(brut=brut):
                self.verifier(structure, brut)


if __name__ == "__main__":
    unittest.main()
