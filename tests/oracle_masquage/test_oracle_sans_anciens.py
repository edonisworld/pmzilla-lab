"""
L'oracle de masquage appliqué aux quatre statistiques « sans les anciens » de v_team_lead_time_throughput (change masking-sums, tâche 22.1 ; conception D16,
« Grouped year without the old items » ; R-20261105-30, R-20261106-52, R-20261106-59).

    bash tests/run_all.sh oracle_masquage     (aucune base)

Règle (R-20261106-59, Q1 (a)) : une statistique sans les anciens n'est montrée que si l'effectif de son genre est montré, si items_old de la même ligne est montré
ET si c - o (ou m - o) vaut au moins le seuil. La visibilité d'une cellule ne dépend que de cellules publiées : aucune inégalité sur un items_old masqué. Une première
version de 0038 montrait la statistique sans condition sur items_old : elle fixait quatre trimestres masqués à c - 1 quand la statistique de l'année était absente, et
items_old à 1 pour un effectif de 6 (fuite trouvée par ce fichier, second regard Opus du 2026-11-06). Le témoin `Temoin` rejoue cette première règle.

Deux lectures, sur de petites familles d'une équipe (1 à 4 trimestres de 5 à 9 éléments, items_lt = items_ct = débit, aucun élément sans engagement), qui
énumèrent toutes les listes d'items_old possibles et cherchent, dans chaque image publiée, une cellule masquée à valeur unique, une somme de cellules masquées
sous le seuil à valeur unique (critère D1) et une cellule masquée qui peut valoir 0 :

  1. Le lecteur Python (`masquer_vue`) sur la vue telle que le SQL la publie au seuil.
  2. La vue elle-même au plancher (règle SQL de 0037 et de la 0038 réécrite), jouée par un port de la règle ici, comme les autres témoins de l'oracle.

Les familles de quatre trimestres de 6, 8 et 9 et celle qui contient un trimestre « tout ancien » (c = o, montré) couvrent la forme générale de la fuite (somme des
marges des trimestres masqués d'au plus 4), pas seulement c = 5. Données inventées (équipe A).
"""
import itertools
import sys
import unittest
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

NOUVELLES = ("lead_median_days_excl_old", "lead_p85_days_excl_old", "cycle_median_days_excl_old", "cycle_p85_days_excl_old")
NOMS = ["team", "period", "quarter_start", "throughput", "items_lt", "lead_median_days", "lead_p85_days", "items_ct", "cycle_median_days",
        "cycle_p85_days", "items_old", "items_without_commitment", *NOUVELLES]
DEBUTS = ("2025-04-01", "2025-07-01", "2025-10-01", "2026-01-01")


def lignes_brutes(comptes, anciens, seuil):
    """Les lignes de la vue : un trimestre par compte, puis l'année groupée. La statistique « sans les anciens » est donnée (2.0) quand m - o atteint le seuil, nulle
    sinon, comme la vue la publie ; le lecteur masque en plus celle d'un items_old masqué."""
    def stats(c, o):
        v = 2.0 if c - o >= seuil else None
        return (v, v, v, v)

    lignes = [("A", "quarter", DEBUTS[i], c, c, 3.0, 9.0, c, 4.0, 8.0, o, 0, *stats(c, o)) for i, (c, o) in enumerate(zip(comptes, anciens))]
    c, o = sum(comptes), sum(anciens)
    lignes.append(("A", "pooled_year", None, c, c, 3.0, 9.0, c, 4.0, 8.0, o, 0, *stats(c, o)))
    return lignes


def image_lecteur(comptes, anciens, seuil):
    """items_old publié de chaque ligne (None si masqué), puis la visibilité de la statistique de lead time de chaque ligne, par `masquer_vue` telle quelle."""
    cellules = fv.masquer_vue(fv.VUE_DEBIT, NOMS, lignes_brutes(comptes, anciens, seuil), seuil)
    olds = tuple(None if "masked" in c["items_old"] else c["items_old"]["value"] for c in cellules)
    drapeaux = tuple("masked" not in c["lead_median_days_excl_old"] and c["lead_median_days_excl_old"]["value"] is not None for c in cellules)
    return olds + drapeaux


def _olds_vue(comptes, anciens, seuil):
    def visible(c, o):
        return o == 0 or (o >= seuil and (c - o == 0 or c - o >= seuil))

    trimestres = [o if visible(c, o) else None for c, o in zip(comptes, anciens)]
    total_c, total_o = sum(comptes), sum(anciens)
    annee = total_o if all(t is not None for t in trimestres) and visible(total_c, total_o) else None
    return tuple(trimestres) + (annee,)


def image_vue_plancher(comptes, anciens, seuil):
    """La vue en SQL au plancher (0037 pour items_old, 0038 réécrite pour la statistique), portée ici : un trimestre montre items_old s'il vaut 0 ou s'il atteint le seuil
    avec un reste nul ou d'au moins le seuil ; l'année le montre seulement si aucun trimestre ne le masque et que la somme suit la même règle ; la statistique est montrée
    quand items_old de la même ligne est montré ET que m - o atteint le seuil (l'effectif étant montré partout, vérifié par la forme des familles), année comprise."""
    olds = _olds_vue(comptes, anciens, seuil)
    reels = tuple(anciens) + (sum(anciens),)
    totaux = tuple(comptes) + (sum(comptes),)
    drapeaux = tuple(o is not None and c - r >= seuil for o, c, r in zip(olds, totaux, reels))
    return olds + drapeaux


def image_premiere_0038(comptes, anciens, seuil):
    """La première règle de 0038 (témoin) : la statistique est montrée sur m - o >= seuil seul, sans condition sur items_old."""
    olds = _olds_vue(comptes, anciens, seuil)
    reels = tuple(anciens) + (sum(anciens),)
    totaux = tuple(comptes) + (sum(comptes),)
    return olds + tuple(c - r >= seuil for c, r in zip(totaux, reels))


_MEMOIRE: dict = {}


def analyser_famille(comptes, seuil, publier):
    """{image: liste des listes d'items_old possibles}. Mémorisé : une famille est énumérée une fois par suite."""
    cle = (comptes, seuil, publier.__name__)
    if cle not in _MEMOIRE:
        groupes = defaultdict(list)
        for anciens in itertools.product(*(range(c + 1) for c in comptes)):
            groupes[publier(comptes, anciens, seuil)].append(anciens)
        _MEMOIRE[cle] = groupes
    return _MEMOIRE[cle]


def fuites(groupes, comptes, seuil):
    """Critère D1 par image : cellule masquée à valeur unique, somme de cellules masquées sous le seuil à valeur unique, cellule masquée qui peut valoir 0. Les
    éléments de l'image au-delà de la ligne de l'année (les drapeaux de statistique) ne sont pas des cellules."""
    trouvees = []
    lignes = len(comptes) + 1
    for image, possibles in groupes.items():
        masquees = [i for i in range(lignes) if image[i] is None]
        for i in masquees:
            valeurs = {sum(p) if i == len(comptes) else p[i] for p in possibles}
            if len(valeurs) == 1:
                trouvees.append(f"valeur unique : image {image}, ligne {i} = {next(iter(valeurs))}")
            if 0 in valeurs:
                trouvees.append(f"borne basse 0 : image {image}, ligne {i}")
        for taille in range(2, len(masquees) + 1):
            for groupe in itertools.combinations(masquees, taille):
                sommes = {sum((sum(p) if i == len(comptes) else p[i]) for i in groupe) for p in possibles}
                if len(sommes) == 1 and next(iter(sommes)) < seuil:
                    trouvees.append(f"somme unique sous le seuil : image {image}, lignes {groupe} = {next(iter(sommes))}")
    return trouvees


FAMILLES_LECTEUR = (
    ((8,), 5), ((6,), 5), ((9,), 5), ((6, 6), 5), ((5, 6, 8), 5), ((5, 5, 5, 5), 5),          # au plancher
    ((8, 9), 7), ((7, 7, 7), 7),                                                             # seuil relevé à 7
    ((5, 8, 9, 6), 5), ((8, 8, 8, 8), 5),                                                    # revue 21.2 : un trimestre « tout ancien » et la forme générale, côté lecteur aussi
)
# R-20261106-59, Q2 (a) : quatre trimestres de 6, 8 et 9 (la forme générale), et une famille dont un trimestre peut être « tout ancien » (c = o, montré) pendant que
# les autres sont masqués (effectifs différents, le premier à 5 : o = c = 5 est montré avec un reste nul).
FAMILLES_VUE = (
    ((8,), 5), ((9,), 5), ((6,), 5), ((8, 9), 5), ((5, 5, 5, 5), 5), ((6, 6, 6, 6), 5), ((8, 8, 8, 8), 5), ((9, 9, 9, 9), 5), ((5, 8, 9, 6), 5),
)


class LecteurPython(unittest.TestCase):
    def test_aucune_fuite_dans_les_familles(self):
        for comptes, seuil in FAMILLES_LECTEUR:
            with self.subTest(comptes=comptes, seuil=seuil):
                self.assertEqual(fuites(analyser_famille(comptes, seuil, image_lecteur), comptes, seuil), [])

    def test_la_statistique_n_est_jamais_montree_avec_items_old_masque(self):
        for comptes, seuil in FAMILLES_LECTEUR:
            for image in analyser_famille(comptes, seuil, image_lecteur):
                lignes = len(comptes) + 1
                for i in range(lignes):
                    if image[i] is None:
                        self.assertFalse(image[lignes + i], (comptes, seuil, image, i))


class VueAuPlancher(unittest.TestCase):
    """La vue SQL réécrite (R-20261106-59, Q1 (a)) : aucune valeur unique, aucune somme unique sous le seuil, aucune borne basse 0."""

    def test_aucune_fuite_dans_les_familles(self):
        for comptes, seuil in FAMILLES_VUE:
            with self.subTest(comptes=comptes):
                self.assertEqual(fuites(analyser_famille(comptes, seuil, image_vue_plancher), comptes, seuil), [])

    def test_la_statistique_n_est_jamais_montree_avec_items_old_masque(self):
        for comptes, seuil in FAMILLES_VUE:
            lignes = len(comptes) + 1
            for image in analyser_famille(comptes, seuil, image_vue_plancher):
                for i in range(lignes):
                    if image[i] is None:
                        self.assertFalse(image[lignes + i], (comptes, image, i))

    def test_X39_items_old_masque_se_lit_dans_un_intervalle_large(self):
        """Cas X39 de D16 sous (a) : items_lt = items_ct = 8, items_old masqué, les quatre statistiques nulles : items_old dans [1, 7] (sept valeurs ; sous la première
        0038 il tenait dans [4, 7])."""
        groupes = analyser_famille((8,), 5, image_vue_plancher)
        possibles = [p for image, ps in groupes.items() if image[0] is None for p in ps]
        self.assertEqual(sorted({p[0] for p in possibles}), [1, 2, 3, 4, 5, 6, 7])

    def test_la_famille_avec_un_trimestre_tout_ancien_contient_des_images_ou_il_est_montre_et_les_autres_masques(self):
        comptes = (5, 8, 9, 6)
        groupes = analyser_famille(comptes, 5, image_vue_plancher)
        trouvees = [image for image in groupes if image[0] == 5 and all(image[i] is None for i in (1, 2, 3))]
        self.assertTrue(trouvees)                      # le premier trimestre (c = o = 5) est montré, les trois autres masqués

    def test_un_effectif_de_6_ne_fixe_pas_items_old(self):
        """Constat du second regard (R-20261106-59) : sous la première 0038, un effectif de 6 avec la statistique montrée fixait items_old à 1. Sous (a), la ligne
        d'un items_old masqué n'a aucune statistique : items_old reste dans [1, 5]. Test d'absence de fuite."""
        groupes = analyser_famille((6,), 5, image_vue_plancher)
        possibles = [p for image, ps in groupes.items() if image[0] is None for p in ps]
        self.assertEqual(sorted({p[0] for p in possibles}), [1, 2, 3, 4, 5])
        self.assertEqual(fuites(groupes, (6,), 5), [])


class Temoin(unittest.TestCase):
    """La première règle de 0038 fuyait : l'oracle la voit (il voit les fuites du second regard)."""

    def test_quatre_trimestres_de_5_avec_la_statistique_annuelle_absente_fixent_chaque_trimestre_a_4(self):
        trouvees = fuites(analyser_famille((5, 5, 5, 5), 5, image_premiere_0038), (5, 5, 5, 5), 5)
        self.assertTrue(any(t.startswith("valeur unique") for t in trouvees), trouvees)

    def test_un_effectif_de_6_avec_la_statistique_montree_fixe_items_old_a_1(self):
        trouvees = fuites(analyser_famille((6,), 5, image_premiere_0038), (6,), 5)
        self.assertTrue(any(t.startswith("valeur unique") for t in trouvees), trouvees)

    def test_quatre_trimestres_de_8_fuient_aussi_sous_la_premiere_regle(self):
        trouvees = fuites(analyser_famille((8, 8, 8, 8), 5, image_premiere_0038), (8, 8, 8, 8), 5)
        self.assertTrue(any(t.startswith("valeur unique") for t in trouvees), trouvees)


if __name__ == "__main__":
    unittest.main()
