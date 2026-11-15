"""
L'oracle de masquage appliqué à items_old de v_team_lead_time_throughput, avec le zéro montré (change masking-sums, tâche 22.1, décision de l'auteur
R-20261106-39 ; conception D2 et D16).

    bash tests/run_all.sh oracle_masquage     (aucune base)

Règle publiée : sur toute ligne, trimestres compris, items_old = 0 est montré quand items_ct est montré ; l'année n'est montrée à 0 que si tous ses
items_old trimestriels sont montrés ; sinon la règle de série de `masquer_vue` s'applique ; un items_old masqué alors que items_ct est montré a pour
borne basse 1. L'oracle joue `masquer_vue` telle que publiée sur de petites familles d'une équipe (trimestres et année groupée, items_ct montré partout,
items_lt = débit = items_ct, aucun élément sans engagement) : il énumère toutes les listes d'items_old possibles pour les mêmes items_ct, regroupe celles
qui ont la même image et cherche, dans chaque image, une cellule masquée à valeur unique, une somme de cellules masquées sous le seuil à valeur unique
(critère D1) et une cellule masquée qui peut valoir 0 (borne basse 1). Il rejoue aussi les cas partagés X42a à X42f (anciennement X40a à X40f) et leurs voisins sur leurs seules
cellules masquées. Un témoin montre qu'il voit la fuite d'une règle de série étroite (celle de la vue en SQL) quand les zéros trimestriels sont montrés.
Données inventées (équipe A).
"""
import importlib.util
import itertools
import json
import sys
import unittest
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

_spec = importlib.util.spec_from_file_location("oracle_masquage", RACINE / "tests" / "oracle_masquage" / "oracle_masquage.py")
oracle = importlib.util.module_from_spec(_spec)
sys.modules["oracle_masquage"] = oracle
_spec.loader.exec_module(oracle)

NOMS = ["team", "period", "quarter_start", "throughput", "items_lt", "lead_median_days", "lead_p85_days", "items_ct", "cycle_median_days",
        "cycle_p85_days", "items_old", "items_without_commitment"]
DEBUTS = ("2025-04-01", "2025-07-01", "2025-10-01", "2026-01-01")


def lignes_brutes(comptes, anciens):
    """Les lignes de la famille : un trimestre par compte, puis l'année groupée (sommes). items_lt = débit = items_ct, aucun sans engagement."""
    lignes = [("A", "quarter", DEBUTS[i], c, c, 3.0, 9.0, c, 4.0, 8.0, o, 0) for i, (c, o) in enumerate(zip(comptes, anciens))]
    c, o = sum(comptes), sum(anciens)
    lignes.append(("A", "pooled_year", None, c, c, 3.0, 9.0, c, 4.0, 8.0, o, 0))
    return lignes


def image_anciens(comptes, anciens, seuil):
    """items_old publié de chaque ligne (None si masqué), par `masquer_vue` telle quelle."""
    cellules = fv.masquer_vue(fv.VUE_DEBIT, NOMS, lignes_brutes(comptes, anciens), seuil)
    return tuple(None if "masked" in c["items_old"] else c["items_old"]["value"] for c in cellules)


def images_visibles_ct(comptes, seuil):
    cellules = fv.masquer_vue(fv.VUE_DEBIT, NOMS, lignes_brutes(comptes, (0,) * len(comptes)), seuil)
    return all("masked" not in c["items_ct"] for c in cellules)


_MEMOIRE: dict = {}


def analyser_famille(comptes, seuil, publier=image_anciens):
    """{image: liste des listes d'items_old possibles} pour des items_ct donnés ; les items_ct sont montrés partout (vérifié). Mémorisé : une famille
    est énumérée une fois par suite."""
    cle = (comptes, seuil, publier.__name__)
    if cle not in _MEMOIRE:
        assert images_visibles_ct(comptes, seuil), (comptes, seuil)
        groupes = defaultdict(list)
        for anciens in itertools.product(*(range(c + 1) for c in comptes)):
            groupes[publier(comptes, anciens, seuil)].append(anciens)
        _MEMOIRE[cle] = groupes
    return _MEMOIRE[cle]


def fuites(groupes, comptes, seuil):
    """Critère D1 par image : cellule masquée à valeur unique, somme de cellules masquées sous le seuil à valeur unique, cellule masquée qui peut valoir 0."""
    trouvees = []
    for image, possibles in groupes.items():
        masquees = [i for i, v in enumerate(image) if v is None]
        for i in masquees:
            valeurs = {sum(p) if i == len(comptes) else p[i] for p in possibles}
            if len(valeurs) == 1:
                trouvees.append(f"valeur unique : image {image}, ligne {i} = {next(iter(valeurs))}")
            if 0 in valeurs:
                trouvees.append(f"borne basse 0 : image {image}, ligne {i} (items_ct montré : la borne basse est 1)")
        for taille in range(2, len(masquees) + 1):
            for groupe in itertools.combinations(masquees, taille):
                sommes = {sum((sum(p) if i == len(comptes) else p[i]) for i in groupe) for p in possibles}
                if len(sommes) == 1 and next(iter(sommes)) < seuil:
                    trouvees.append(f"somme unique sous le seuil : image {image}, lignes {groupe} = {next(iter(sommes))}")
    return trouvees


FAMILLES = (
    ((6, 6), 5), ((5, 6, 8), 5), ((5, 5, 5, 5), 5), ((6, 6, 6, 6), 5),     # au plancher
    ((8, 9), 7), ((7, 7, 7), 7),                                           # seuil relevé à 7
)


class FamillesAnciens(unittest.TestCase):
    def test_aucune_fuite_dans_les_familles(self):
        for comptes, seuil in FAMILLES:
            with self.subTest(comptes=comptes, seuil=seuil):
                self.assertEqual(fuites(analyser_famille(comptes, seuil), comptes, seuil), [])

    def test_les_zeros_sont_montres_et_l_annee_a_zero_seulement_si_tout_est_montre(self):
        comptes, seuil = (5, 5, 5, 5), 5
        zero = image_anciens(comptes, (0, 0, 0, 0), seuil)
        self.assertEqual(zero, (0, 0, 0, 0, 0))                                        # R-20261106-39 : trimestres et année à 0 montrés
        un_masque = image_anciens(comptes, (0, 0, 0, 3), seuil)
        self.assertEqual(un_masque, (0, 0, 0, None, None))                             # un trimestre masqué : l'année l'est aussi, les zéros restent montrés

    def test_un_items_old_masque_avec_items_ct_montre_ne_peut_pas_valoir_zero(self):
        for comptes, seuil in FAMILLES:
            for image, possibles in analyser_famille(comptes, seuil).items():
                for i, v in enumerate(image):
                    if v is None:
                        self.assertTrue(all((sum(p) if i == len(comptes) else p[i]) >= 1 for p in possibles), (comptes, seuil, image, i))


def publier_etroit(comptes, anciens, seuil):
    """Règle étroite d'essai, celle de la vue en SQL (fuite_serie) avec les zéros trimestriels montrés : un trimestre montre 0 ou un compte d'au moins le
    seuil dont le reste est 0 ou d'au moins le seuil ; l'année est montrée si elle atteint le seuil et qu'il n'y a ni une seule cellule masquée, ni
    des cellules masquées de somme sous le seuil."""
    def visible(c, o):
        return o == 0 or (o >= seuil and (c - o == 0 or c - o >= seuil))
    trimestres = [o if visible(c, o) else None for c, o in zip(comptes, anciens)]
    masquees = [o for c, o, t in zip(comptes, anciens, trimestres) if t is None]
    annee = sum(anciens)
    fuite = len(masquees) == 1 or (len(masquees) >= 1 and sum(masquees) < seuil)
    return tuple(trimestres) + ((annee if annee >= seuil and not fuite and visible(sum(comptes), annee) else None),)


class Temoin(unittest.TestCase):
    def test_la_regle_de_serie_etroite_avec_des_zeros_montres_fuit(self):
        comptes, seuil = (5, 5, 5, 5), 5
        trouvees = fuites(analyser_famille(comptes, seuil, publier_etroit), comptes, seuil)
        self.assertTrue(any(t.startswith("valeur unique") for t in trouvees), trouvees)     # (0, 0, 4, 4) : année 8, les deux trimestres masqués valent 4


def charger_cas():
    return {c["id"]: c for c in json.loads((RACINE / "contrats" / "cas-masquage.json").read_text(encoding="utf-8"))["cases"]}


class CasPartages(unittest.TestCase):
    """X42a, X42c, X42d, X42e et X42f sur leurs seules cellules masquées (X42b a un trimestre masqué dont les comptes ne sont pas publiés : il n'a
    pas d'items_ct montré à tirer) : tout items_old masqué du cas peut valoir au moins deux valeurs, jamais 0, et toute somme masquée atteint le seuil."""

    def jouer_cas(self, identifiant):
        cas = charger_cas()[identifiant]
        seuil = cas["threshold"]
        lignes = [tuple(r.get(n) for n in cas["columns"]) for r in cas["rows"]]
        equipes = sorted({r[0] for r in lignes})
        for equipe in equipes:
            propres = [r for r in lignes if r[0] == equipe]
            trimestres = [r for r in propres if r[1] == "quarter"]
            comptes = [r[cas["columns"].index("items_ct")] for r in trimestres]
            anciens_vrais = [r[cas["columns"].index("items_old")] for r in trimestres]
            for lot in (comptes,):
                self.assertTrue(all(c is not None for c in lot), identifiant)
            if any(not (c >= seuil) for c in comptes):
                continue
            # l'image du cas (valeurs publiées) est l'image de la liste d'items_old du cas ; ses compatibles : la liste du cas et celles où une seule
            # cellule varie (l'énumération complète de quatre trimestres de 20 est trop longue ; les familles de FAMILLES, petites, la font entière)
            image = image_anciens(tuple(comptes), tuple(anciens_vrais), seuil)
            compatibles = [tuple(anciens_vrais)]
            for i in range(len(comptes)):
                for x in range(comptes[i] + 1):
                    variante = tuple(x if j == i else v for j, v in enumerate(anciens_vrais))
                    if image_anciens(tuple(comptes), variante, seuil) == image:
                        compatibles.append(variante)
            for i, v in enumerate(image):
                if v is None:
                    valeurs = {sum(p) if i == len(comptes) else p[i] for p in compatibles}
                    self.assertGreaterEqual(len(valeurs), 2, (identifiant, equipe, i, valeurs))
                    self.assertGreaterEqual(min(valeurs), 1, (identifiant, equipe, i, valeurs))

    def test_X42a(self):
        self.jouer_cas("X42a")

    def test_X42c(self):
        self.jouer_cas("X42c")

    def test_X42d(self):
        cas = charger_cas()["X42d"]                                     # items_ct masqué (6 sous 8) : rien à tirer, le zéro reste masqué
        self.assertEqual(sorted(map(tuple, cas["masked"])), [(0, "items_ct"), (0, "items_old")])

    def test_X42e(self):
        self.jouer_cas("X42e")

    def test_X42f(self):
        self.jouer_cas("X42f")


if __name__ == "__main__":
    unittest.main()
