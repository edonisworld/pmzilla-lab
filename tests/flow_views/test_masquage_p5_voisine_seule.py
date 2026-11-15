"""
P5 et la voisine seule candidate (change du masquage des sommes, R-144, groupe 20, tâche 20.1 ; décision R-20261104-49, réponses Q1 (e) et Q2 (a) ;
conception D15, P5 et B15 ; revue 19.1, corrections C1, C2 et C6).

    bash tests/run_all.sh flow_views

Sans base. Données inventées (équipes A, B, produit, une semaine, seuil 5). Tests écrits avant le code (rouges sans lui) :
  - le cas « D3 avant D2 » (A : 30 créés, 3 sans affects, sans version ; B : 40, 27, trouvé 13) : avec P5, la borne basse de U_P vaut au moins 26 dans la
    lecture « m libre », donc les paris « U_P = 0 » ne sont pas joués ;
  - le cas inventé de l'équipe A (12 créés publié, 12 sans affects masqué par la paire, sans ligne de version ; B : 40, 27, trouvé 13) : les cellules masquées
    attendues, à la main (revue 19.1, section 1) : A.w, A.c (règle enregistrée D15), B.w, B.c, P.c et P.w, les trouvés publiés ;
  - la voisine seule candidate (A : 30, 3, sans trouvé ; B : 40, 8, trouvés 32 et 32) : aucune erreur, B.c masqué comme seule candidate restante, règle
    enregistrée D15 sans borne haute, borne de départ sans borne haute ; l'ensemble publié de ce cas n'est pas affirmé (à la main, la lecture « U_B = 0 et
    m_B = 0 » épingle B.c à 72 et masque B.w aussi) ;
  - la relation P5 des sommes n'est pas traversée par la règle du voisin.
Condition de la tâche 20.1 : les cellules attendues du cas inventé de l'équipe A sont écrites d'après la main de la revue 19.1 ; l'oracle (20.4,
`oracle_masquage`) doit confirmer que chacune garde au moins deux valeurs dans chaque lecture, sinon arrêt et rapport à l'auteur.
Depuis l'écart D4 (d) rétabli (R-20261106-22) : les données des tests de P5 et de la voisine seule sont p5_produit_avec_versions et voisine_seule_versions,
où la règle joue sur une ligne qui a des lignes de version et un trouvé masqué (R-20261106-24 (a)) ; le cas inventé de l'équipe A enregistre la règle d2
(R-20261106-23) ; le jeu Q3 est un échec fermé à limite forcée (R-20261106-23 Q1 (a)). Trois noms de tests suivent leur contenu (R-20261106-46).
Replaces: rien (tests neufs). Removal: tombent avec P5 et avec la règle de la voisine seule (B15).
"""
import sys
import unittest
import unittest.mock
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

NOMS = ["week_start", "n_adopted", "team", "version_no", "found", "defects_created", "defects_without_affects", "resolved_week",
        "resolved_week_defects"]
S1 = "2026-03-02"
P = fv.PRODUIT


def libre(equipe, crees, sans, resolus=20, resolus_defauts=10):
    return (S1, True, equipe, None, None, crees, sans, resolus, resolus_defauts)


def version(equipe, numero, trouves):
    return (S1, True, equipe, numero, trouves, None, None, None, None)


def d3_avant_d2():
    """Cas « D3 avant D2 » de la revue 19.1 : A 30 / 3 sans version, B 40 / 27 trouvé 13, produit 70 / 30 trouvé 13."""
    return [libre("A", 30, 3), libre("B", 40, 27), version("B", 1, 13), libre(P, 70, 30, 40, 20), version(P, 1, 13)]


S0 = "2026-02-23"
S2 = "2026-03-09"


def p5_produit_avec_versions():
    """Données réécrites (R-20261106-24 (a), après R-20261106-22 et R-20261106-23 : écart D4 (d) rétabli, une ligne d'équipe sans ligne de version a toujours
    ses créés et sans affects masqués, sans borne). P5 joue sur la ligne du produit de S1, qui a des lignes de version et un trouvé masqué (v2 = 3).
      - S1, rangs 0 à 4 comme dans `d3_avant_d2` : A 36 / 3 sans ligne de version (sans affects primaire, créés masqués par D2) ; B 20 / 5, trouvés v1 = 12
        publié et v2 = 3 caché (un seul terme caché : D2 masque sans affects, puis créés, 20 - 12 = 8 = 4 + 4) ; produit 56 / 8, trouvés 12 et 3.
      - S2 : A 38 / 6, une version de trouvé 32 ; ses créés (38) sont à 2 de ceux de S1 (36) : D5-d les masque, ancre A de S1 (P3 : créés S1 >= 38 - 4).
    Bornes dans « m libre » : D_A de S1 >= 34 - 4 = 30 (créés S2 >= 6 + 32), D_B >= 12, donc D_P >= 42 par P5 et U_P >= 42 - (12 + 4) = 26. Sans la relation
    des sommes de P5, la borne de U_P tombe : les créés et sans affects de B n'ont pas de borne haute, P4 seule ne borne pas D_P."""
    return [libre("A", 36, 3), libre("B", 20, 5), version("B", 1, 12), libre(P, 56, 8, 40, 20), version(P, 1, 12),
            version("B", 2, 3), version(P, 2, 3),
            (S2, True, "A", None, None, 38, 6, 20, 10), (S2, True, "A", 1, 32, None, None, None, None),
            (S2, True, P, None, None, 38, 6, 20, 10), (S2, True, P, 1, 32, None, None, None, None)]


def voisine_seule_versions():
    """Données réécrites (R-20261106-24 (a), après R-20261106-22 et R-20261106-23) : la voisine seule candidate joue sur la ligne de B (rang 1), qui a une ligne
    de version et un trouvé masqué. B : créés 5, sans affects 4 (primaire), une version v3 de trouvé 1 (primaire) ; C (rang 0) : créés 12, sans affects 4
    (primaire), trouvés v1 = 5 et v3 = 3 (caché) ; produit 17 / 8, trouvés v1 = 5 et v3 = 4. Les règles laissent publiés B.c, C.c et les créés du produit ; D15
    épingle une cellule dont la seule cellule publiée de l'anneau est B.c, masqué avec la règle (« d15 », None). Les équipes s'appellent B et C (et non A et
    B) pour que l'équipe de la voisine seule vienne la première dans l'ordre des clés."""
    return [libre("C", 12, 4), libre("B", 5, 4), version("B", 3, 1), version("C", 1, 5), version("C", 3, 3), libre(P, 17, 8, 40, 20), version(P, 1, 5),
            version(P, 3, 4)]


def equipe_a_inventee():
    """Cas inventé de l'équipe A (revue 19.1) : A 12 créés publié, 12 sans affects masqué par la paire, sans ligne de version ; B 40 / 27 trouvé 13."""
    return [libre("A", 12, 12), libre("B", 40, 27), version("B", 1, 13), libre(P, 52, 39, 40, 20), version(P, 1, 13)]


def voisine_seule():
    """Spécification, « Neighbour that was the only candidate » : A 30 / 3 sans trouvé ; B 40 / 8 avec deux trouvés de 32 ; produit 70 / 11."""
    return [libre("A", 30, 3), libre("B", 40, 8), version("B", 1, 32), version("B", 2, 32), libre(P, 70, 11, 40, 20), version(P, 1, 32), version(P, 2, 32)]


def photo(lignes, seuil=5):
    """Rejoue le masquage de la photo ; renvoie (visibilité par ligne, unité de propagation capturée)."""
    rangees = [dict(zip(NOMS, ligne)) for ligne in lignes]
    vis = [{} for _ in rangees]
    prises = []
    original = fv._UnitePhoto.propager

    def capturer(self, regles, lim):
        prises.append(self)
        return original(self, regles, lim)

    with unittest.mock.patch.object(fv._UnitePhoto, "propager", capturer):
        fv._masque_photo(NOMS, rangees, seuil, [set() for _ in rangees], vis, None, None)
    return vis, prises[0]


def avant_la_boucle(lignes, seuil=5):
    """L'état après les règles existantes seulement (D3, D5-d, D2), sans la boucle de D15 : renvoie l'unité."""
    rangees = [dict(zip(NOMS, ligne)) for ligne in lignes]
    vis = [{} for _ in rangees]
    prises = []

    def arreter(self, regles, lim):
        prises.append(self)
    with unittest.mock.patch.object(fv._UnitePhoto, "propager", arreter):
        fv._masque_photo(NOMS, rangees, seuil, [set() for _ in rangees], vis)
    return prises[0]


def masquees(vis, lignes, colonne):
    return {(lignes[i][2], lignes[i][3]) for i, v in enumerate(vis) if colonne in v and not v[colonne]}


class P5DonneUneBorneBasseAUP(unittest.TestCase):
    """Revue 19.1, section 1 : avec P5, D_A est dans [26, 30], D_P >= 39 et U_P >= 26 dans « m libre » ; les paris « U_P = 0 » ne sont pas joués.
    Depuis R-20261106-24 (a), la borne et le pari se lisent sur `p5_produit_avec_versions` (D_A >= 30, D_P >= 42, U_P >= 26) : le cas d'origine n'a plus
    de borne, A sans ligne de version ayant ses deux cellules masquées sans borne (écart D4 (d) rétabli)."""

    def test_u_du_produit_a_une_borne_basse_d_au_moins_26_dans_la_lecture_m_libre(self):
        unite = avant_la_boucle(p5_produit_avec_versions())   # données réécrites, assertion gardée (R-20261106-24 (a))
        u = unite._construire()
        lo, hi, vide = fv._propager(u["lo"], u["hi"], u["relations"], 10 ** 6, 10 ** 6)
        self.assertFalse(vide)
        u_produit = next(v for v, d in enumerate(u["definition"]) if d == ("U", 3))
        self.assertGreaterEqual(lo[u_produit], 26)

    def test_l_equipe_sans_ligne_de_version_a_un_d_latent_et_une_relation_creees_moins_sans_moins_d(self):
        unite = avant_la_boucle(d3_avant_d2())
        u = unite._construire()
        d_a = [v for v, d in enumerate(u["definition"]) if d == ("Dt", 0)]
        self.assertEqual(len(d_a), 1)                                                   # D_t de l'équipe A : sans ligne de version, donc pas de D_r
        self.assertEqual((u["lo"][d_a[0]], u["hi"][d_a[0]]), (0, None))                  # borne basse 0, sans borne haute
        crees = next(v for v, d in enumerate(u["definition"]) if d == ("c", 0, "defects_created"))
        sans = next(v for v, d in enumerate(u["definition"]) if d == ("c", 0, "defects_without_affects"))
        self.assertIn(("eq", 0, tuple(sorted(((crees, 1), (sans, -1), (d_a[0], -1))))), u["relations"])

    def test_la_relation_des_sommes_p5_somme_les_d_des_equipes_et_celui_du_produit(self):
        unite = avant_la_boucle(d3_avant_d2())
        u = unite._construire()
        d_a = next(v for v, d in enumerate(u["definition"]) if d == ("Dt", 0))
        d_b = next(v for v, d in enumerate(u["definition"]) if d == ("D", 1))
        d_p = next(v for v, d in enumerate(u["definition"]) if d == ("D", 3))
        somme = ("eq", 0, tuple(sorted(((d_p, 1), (d_a, -1), (d_b, -1)))))
        self.assertIn(somme, u["relations"])
        self.assertEqual(u["relations"][-1], somme)                                     # P5 vient après P4, la somme est la dernière relation ici
        self.assertTrue(u["hors_anneau"][u["relations"].index(somme)])                  # la somme n'est pas traversée par la règle du voisin
        self.assertEqual(sum(u["hors_anneau"]), 1)                                      # et elle seule

    def test_le_pari_u_nul_du_produit_n_est_pas_joue(self):
        unite = avant_la_boucle(p5_produit_avec_versions())   # données réécrites, assertion gardée (R-20261106-24 (a))
        u = unite._construire()
        u_produit = next(v for v, d in enumerate(u["definition"]) if d == ("U", 3))
        vues = []
        original = fv._propager

        def enregistrer(lo, hi, relations, borne_m, limite):
            vues.append(hi[u_produit])
            return original(lo, hi, relations, borne_m, limite)
        with unittest.mock.patch.object(fv, "_propager", enregistrer):
            unite._epingles(u, None)
        self.assertNotIn(0, vues)                                                       # ni « U = 0 » ni « U = 0 et m = 0 » du produit

    def test_une_semaine_sans_equipe_sans_version_n_a_pas_de_p5(self):
        unite = avant_la_boucle([libre(P, 52, 39, 40, 20), version(P, 1, 13)])
        u = unite._construire()
        self.assertFalse([d for d in u["definition"] if d[0] == "Dt"])
        self.assertEqual(sum(u["hors_anneau"]), 0)


class CasInventeEquipeA(unittest.TestCase):
    """Revue 19.1, contre-exemple A : la fuite (A.w = 12 lu par l'attaquant qui parie U_P = 0) est fermée. Attendu à la main : masqués A.w, A.c, B.w, B.c, P.c
    et P.w ; publiés B.f et P.f. Confirmé par l'oracle : `CasInventeEquipeADeLOracle` (tests/oracle_masquage/test_oracle_propagation.py), aucune fuite
    hors de l'exemption d'un seul terme retenu (réponse Q3 (a) de l'auteur du 2026-11-05)."""

    def test_cellules_masquees_attendues(self):
        lignes = equipe_a_inventee()
        vis, _ = photo(lignes)
        self.assertEqual(masquees(vis, lignes, "defects_created"), {("A", None), ("B", None), (P, None)})
        self.assertEqual(masquees(vis, lignes, "defects_without_affects"), {("A", None), ("B", None), (P, None)})
        self.assertEqual(masquees(vis, lignes, "found"), set())                         # B.f et P.f restent publiés

    def test_le_cree_de_a_est_masque_par_d2(self):
        lignes = equipe_a_inventee()
        vis, unite = photo(lignes)
        self.assertFalse(vis[0]["defects_created"])
        # R-20261106-22 et R-20261106-23 : A n'a aucune ligne de version, l'écart D4 (d) est rétabli et D2 masque A.c avant D15 (règle d2 au lieu de d15) ;
        # la fuite reste fermée (cellules masquées inchangées, test précédent).
        self.assertEqual(unite.regle[(0, "defects_created")][0], "d2")
        self.assertEqual(unite.regle[(0, "defects_without_affects")], ("paire", "defects_created"))

    def test_aucune_exception(self):
        photo(equipe_a_inventee())


class VoisineSeuleCandidate(unittest.TestCase):
    """Spécification, scénario « Neighbour that was the only candidate », et corrections C1 et C6 de la revue 19.1 : B.c est masqué comme seule candidate
    restante, avec la règle enregistrée D15 sans borne haute, et part sans borne haute ; `masquer_vue` ne lève aucune erreur."""

    def test_masquer_vue_ne_leve_aucune_erreur(self):
        lignes = voisine_seule()
        cellules = fv.masquer_vue(fv.VUE_PHOTO, NOMS, lignes, fv.PLANCHER)
        self.assertEqual(len(cellules), len(lignes))

    def test_b_cree_est_masque_avec_la_regle_d15_sans_borne_haute(self):
        lignes = voisine_seule_versions()                                               # données réécrites, assertions gardées (R-20261106-24 (a))
        vis, unite = photo(lignes)
        self.assertFalse(vis[1]["defects_created"])                                     # B.c
        self.assertEqual(unite.regle[(1, "defects_created")], ("d15", None))            # la seule candidate : sans borne haute enregistrée

    def test_b_cree_part_sans_borne_haute_dans_l_unite(self):
        lignes = voisine_seule_versions()                                               # données réécrites, assertion gardée (R-20261106-24 (a))
        _, unite = photo(lignes)
        u = unite._construire()
        b_cree = next(v for v, d in enumerate(u["definition"]) if d == ("c", 1, "defects_created"))
        self.assertEqual((u["lo"][b_cree], u["hi"][b_cree]), (0, None))                 # ni T - 1 ni la valeur de la voisine

    def test_la_regle_du_voisin_rend_none_quand_la_voisine_est_la_seule_candidate(self):
        unite = fv._UnitePhoto.__new__(fv._UnitePhoto)
        unite.seuil = 5
        u = {"relations": [("eq", 0, ((0, 1), (1, -1)))], "cellule": [True, True], "publiee": [False, True], "valeur": [None, 40]}
        self.assertEqual(unite._voisine(u, 0), (1, None))

    def test_une_voisine_avec_une_autre_candidate_garde_la_borne_de_la_formule(self):
        unite = fv._UnitePhoto.__new__(fv._UnitePhoto)
        unite.seuil = 5
        u = {"relations": [("eq", 0, ((0, 1), (1, -1), (2, -1)))], "cellule": [True] * 3, "publiee": [False, True, True], "valeur": [None, 9, 7]}
        self.assertEqual(unite._voisine(u, 0), (2, 9))                                  # max(T - 1, la plus petite des autres) : inchangé

    def test_la_relation_p5_des_sommes_n_est_pas_traversee_par_les_anneaux(self):
        unite = fv._UnitePhoto.__new__(fv._UnitePhoto)
        unite.seuil = 5
        u = {"relations": [("eq", 0, ((0, 1), (1, -1))), ("eq", 0, ((0, 1), (2, -1)))], "cellule": [True] * 3, "publiee": [False, True, True],
             "valeur": [None, 9, 7], "hors_anneau": [False, True]}
        self.assertEqual(unite._voisine(u, 0), (1, None))                                # la cellule 2 n'est liée à x que par la relation P5 : pas candidate
        u["hors_anneau"] = [False, False]
        self.assertEqual(unite._voisine(u, 0), (2, 9))                                   # traversée, elle serait candidate et la plus petite


class JeuQ3EchecFerme(unittest.TestCase):
    """Tâche 20.4, jeu Q3 (R-20261104-50 Q-A (c) ; R-20261104-55 Q2 (a)) : une semaine retenue, une version v, seuil 10.
    Équipe A : sans version 30 créés, 6 sans affects, aucune ligne de v. Équipe B : créés inconnu (masqué), 27 sans affects, ligne de v trouvé inconnu.
    Produit : créés inconnu, 33 sans affects, ligne de v trouvé inconnu. Les cellules inconnues n'ont pas de borne haute : le pari « U_P = 0 » ne peut être
    ni réfuté ni stabilisé, `masquer_vue` lève `MasquageInstable`. Échec fermé voulu : une panne, jamais une fuite ; P6 seulement si la mesure 17.1 montre
    des exceptions. Depuis R-20261106-23 Q1 (a) (écart D4 (d) rétabli) : échec fermé à limite forcée (`_masque_photo`, `{"balayages": 1}`),
    réécrit, jamais retiré ; l'échec fermé atteint par `masquer_vue` reste couvert par test_masquage_propagation.py.
    Replaces: rien. Removal: tombe avec P6 (si elle est décidée) ou avec la règle de l'échec fermé."""

    def test_la_limite_forcee_leve_masquage_instable(self):
        lignes = [libre("A", 30, 6), libre("B", None, 27), version("B", 1, None), libre(P, None, 33, 40, 20), version(P, 1, None)]
        # R-20261106-22 et R-20261106-23 (écart D4 (d) rétabli) : A n'a pas de ligne de version, D2 masque ses créés avant la propagation et le pari « U_P = 0 »
        # ne divergeait plus avec ces données, y compris avec une semaine d'ancrage (S0, A à deux versions). Le test devient un échec fermé à limite forcée
        # (`limites` de `_masque_photo`, clé « balayages » à 1) : la propagation de l'unité ne se stabilise pas en un balayage, MasquageInstable est levée et
        # rien n'est publié. Il reste rouge si la limite cesse de lever.
        lignes += [(S0, True, "A", None, None, 33, 20, 20, 10), (S0, True, "A", 1, 13, None, None, None, None), (S0, True, "A", 2, 13, None, None, None, None)]
        rangees = [dict(zip(NOMS, ligne)) for ligne in lignes]
        with self.assertRaisesRegex(fv.MasquageInstable, r"pas de balayage stable en 1 balayages|une borne finie dépasse M"):
            fv._masque_photo(NOMS, rangees, 10, [set() for _ in rangees], [{} for _ in rangees], None, {"balayages": 1})


if __name__ == "__main__":
    unittest.main()
