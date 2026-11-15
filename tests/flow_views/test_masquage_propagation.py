"""
Propagation des bornes de la photo (change du masquage des sommes, R-144, groupe 6 ; conception D15, décision 14) : moteur Python de `tools/flow_views.py`.

    bash tests/run_all.sh flow_views

Sans base. Données synthétiques seulement (équipe A, produit, semaines du 2026-03). Le cas partagé X23 est joué par test_cas_masquage.py ; ici :
  - le moteur `_propager` (intervalles, relation vide, borne au-dessus de M, limite de balayages) ;
  - la boucle externe et ses deux limites, abaissées dans le test : erreur, rien n'est publié ;
  - la règle du voisin (égalité départagée par la clé, termes latents transparents) et l'ordre des clés (produit après les équipes) ;
  - la lecture la plus stricte décide : un cas où seule la lecture « m = 0 » épingle une cellule ;
  - les constantes `propagation_max(V, M)` et `boucle_max(C)`.
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
S1, S2 = "2026-03-02", "2026-03-09"


def libre(semaine, equipe, crees, sans):
    return (semaine, True, equipe, None, None, crees, sans, 20, 10)


def version(semaine, equipe, numero, trouves):
    return (semaine, True, equipe, numero, trouves, None, None, None, None)


def x23():
    """Cas X23 (conception D15) : équipe A et produit, deux semaines retenues ; le créé de la semaine deux est masqué par la chaîne (24 - 20)."""
    lignes = []
    for equipe in ("A", fv.PRODUIT):
        lignes += [libre(S1, equipe, 20, 10), version(S1, equipe, 1, 10), version(S1, equipe, 2, 6),
                   libre(S2, equipe, 24, 10), version(S2, equipe, 3, 14), version(S2, equipe, 4, 5)]
    return lignes


def photo(lignes, seuil=5, limites=None):
    """Rejoue le masquage de la photo ; renvoie (visibilité par ligne, unité de propagation capturée)."""
    rangees = [dict(zip(NOMS, ligne)) for ligne in lignes]
    vis = [{} for _ in rangees]
    prises = []
    original = fv._UnitePhoto.propager

    def capturer(self, regles, lim):
        prises.append(self)
        return original(self, regles, lim)

    with unittest.mock.patch.object(fv._UnitePhoto, "propager", capturer):
        fv._masque_photo(NOMS, rangees, seuil, [set() for _ in rangees], vis, None, limites)
    return vis, prises[0]


def masquees(vis, lignes, colonne):
    return {(lignes[i][0], lignes[i][2], lignes[i][3]) for i, v in enumerate(vis) if colonne in v and not v[colonne]}


class Constantes(unittest.TestCase):
    def test_propagation_max_est_un_plus_v_fois_deux_m_plus_trois(self):
        self.assertEqual(fv.propagation_max(4, 10), 1 + 4 * (2 * 10 + 3))
        self.assertEqual(fv.propagation_max(0, 7), 1)

    def test_boucle_max_est_c_plus_un(self):
        self.assertEqual(fv.boucle_max(0), 1)
        self.assertEqual(fv.boucle_max(11), 12)


class Moteur(unittest.TestCase):
    def test_une_egalite_resserre_les_bornes_des_trois_termes(self):
        # x0 = x1 + x2 ; x1 = 4 (publié) ; x2 dans [0, 9] ; x0 dans [0, 20]
        lo, hi, vide = fv._propager([0, 4, 0], [20, 4, 9], [("eq", 0, ((0, 1), (1, -1), (2, -1)))], 1000, 50)
        self.assertEqual((lo, hi, vide), ([4, 4, 0], [13, 4, 9], False))

    def test_une_inegalite_ne_borne_que_d_un_cote(self):
        lo, hi, vide = fv._propager([0, 3], [None, 3], [("le", 0, ((0, 1), (1, -1)))], 1000, 50)     # x0 <= x1
        self.assertEqual((lo, hi, vide), ([0, 3], [3, 3], False))

    def test_sans_borne_haute_aucune_borne_basse_n_est_deduite_d_une_egalite(self):
        lo, hi, vide = fv._propager([0, 0], [None, None], [("eq", 0, ((0, 1), (1, -1)))], 1000, 50)
        self.assertEqual((lo, hi, vide), ([0, 0], [None, None], False))

    def test_un_intervalle_vide_est_rendu_comme_tel(self):
        _, _, vide = fv._propager([5, 0], [5, 3], [("eq", 0, ((0, 1), (1, -1)))], 1000, 50)           # x0 = x1 mais 5 > 3
        self.assertTrue(vide)

    def test_une_borne_finie_au_dessus_de_m_leve_l_erreur(self):
        with self.assertRaises(fv.MasquageInstable):
            fv._propager([0, 40], [None, 40], [("le", 0, ((0, 1), (1, -1)))], 10, 50)                 # la borne 40 dépasse M = 10

    def test_limite_de_balayages_atteinte_leve_l_erreur(self):
        relations = [("eq", 0, ((0, 1), (1, -1))), ("eq", 0, ((1, 1), (2, -1)))]
        with self.assertRaises(fv.MasquageInstable):
            fv._propager([0, 0, 7], [None, None, 7], relations, 1000, 1)                              # il faut plusieurs balayages
        lo, hi, _ = fv._propager([0, 0, 7], [None, None, 7], relations, 1000, 10)
        self.assertEqual((lo, hi), ([7, 7, 7], [7, 7, 7]))


class BoucleEtLimites(unittest.TestCase):
    def test_x23_masque_le_trouve_de_cinq_puis_sans_affects_sans_rien_d_autre(self):
        lignes = x23()
        vis, _ = photo(lignes)
        self.assertEqual(masquees(vis, lignes, "found"), {(S2, "A", 4), (S2, fv.PRODUIT, 4)})
        self.assertEqual(masquees(vis, lignes, "defects_created"), {(S2, "A", None), (S2, fv.PRODUIT, None)})
        self.assertEqual(masquees(vis, lignes, "defects_without_affects"), {(S2, "A", None), (S2, fv.PRODUIT, None)})

    def test_la_limite_de_la_boucle_atteinte_erreur_et_rien_de_publie(self):
        with self.assertRaises(fv.MasquageInstable):
            photo(x23(), limites={"boucle": 1})              # X23 demande deux passes qui masquent, puis une stable
        with self.assertRaises(fv.MasquageInstable):
            photo(x23(), limites={"boucle": 2})
        photo(x23(), limites={"boucle": 3})                  # C + 1 n'est jamais atteinte : trois passes suffisent ici

    def test_la_limite_de_balayages_atteinte_erreur_et_rien_de_publie(self):
        with self.assertRaises(fv.MasquageInstable):
            photo(x23(), limites={"balayages": 1})

    def test_la_limite_declaree_de_la_boucle_vaut_c_plus_un_cellules_publiees(self):
        lignes = x23()
        _, unite = photo(lignes)
        # C compte les cellules de comptage publiées au début de la boucle ; la limite par défaut en est C + 1 : la boucle de X23 y tient largement
        self.assertGreater(fv.boucle_max(sum(1 for i, col in unite._cellules() if unite.vis[i][col])), 3)

    def test_une_borne_au_dessus_de_m_dans_une_unite_leve_l_erreur(self):
        with unittest.mock.patch.object(fv, "propagation_max", lambda v, m: 10 ** 6):
            lignes = x23()
            rangees = [dict(zip(NOMS, ligne)) for ligne in lignes]
            vis = [{} for _ in rangees]
            with unittest.mock.patch.object(fv, "_propager", side_effect=fv.MasquageInstable("borne au-dessus de M")) as faux:
                with self.assertRaisesRegex(fv.MasquageInstable, "borne au-dessus de M"):
                    fv._masque_photo(NOMS, rangees, 5, [set() for _ in rangees], vis)
            faux.assert_called()                             # l'erreur vient bien de la propagation de l'unité, pas d'une règle antérieure
            self.assertGreater(faux.call_args[0][3], 0)       # le quatrième argument de _propager est la borne M de l'unité, positive

    def test_une_unite_incoherente_avec_la_lecture_m_libre_n_est_jamais_publiee(self):
        # trouvé 45 pour 35 défauts avec affects (40 - 5) : la lecture « m libre » est vide, erreur et rien n'est publié
        with self.assertRaises(fv.MasquageInstable):
            photo([libre(S1, "A", 40, 5), version(S1, "A", 1, 45)])


class RegleDuVoisinEtOrdreDesCles(unittest.TestCase):
    @staticmethod
    def unite_fictive():
        unite = fv._UnitePhoto.__new__(fv._UnitePhoto)
        unite.seuil = 5
        return unite

    def test_egalite_departagee_par_la_cle(self):
        u = {"relations": [("eq", 0, ((0, 1), (1, -1), (2, -1)))], "cellule": [True, True, True], "publiee": [False, True, True],
             "valeur": [None, 7, 7]}
        y, haut = self.unite_fictive()._voisine(u, 0)
        self.assertEqual((y, haut), (1, 7))                  # la première de l'ordre des clés ; borne de départ : max(seuil - 1, la plus petite des autres)

    def test_la_plus_petite_valeur_gagne_et_la_borne_haute_est_le_plus_grand_de_seuil_moins_un_et_des_autres(self):
        u = {"relations": [("eq", 0, ((0, 1), (1, -1), (2, -1), (3, -1)))], "cellule": [True] * 4, "publiee": [False, True, True, True],
             "valeur": [None, 12, 3, 9]}
        self.assertEqual(self.unite_fictive()._voisine(u, 0), (2, 9))
        u["valeur"] = [None, 12, 3, 4]
        self.assertEqual(self.unite_fictive()._voisine(u, 0), (2, 4))                   # 4 = seuil - 1 : le plus grand de 4 et de 4

    def test_anneau_suivant_quand_aucune_candidate_dans_la_relation_directe(self):
        u = {"relations": [("eq", 0, ((0, 1), (1, -1))), ("eq", 0, ((1, 1), (2, -1)))], "cellule": [True] * 3, "publiee": [False, False, True],
             "valeur": [None, None, 11]}
        # R-20261104-49 Q2 (a) : une voisine seule candidate n'a pas de borne haute ; remplace T − 1 (4 au seuil 5).
        # Autorisé pour ce seul test des intouchables (R-20261104-55).
        self.assertEqual(self.unite_fictive()._voisine(u, 0), (2, None))

    def test_aucune_cellule_publiee_est_une_erreur_interne(self):
        u = {"relations": [("eq", 0, ((0, 1), (1, -1)))], "cellule": [True, True], "publiee": [False, False], "valeur": [None, None]}
        with self.assertRaises(fv.MasquageInstable):
            self.unite_fictive()._voisine(u, 0)

    def test_un_terme_latent_est_transparent_pour_l_anneau(self):
        # x0 est liée au latent 1 seul ; les cellules publiées 2 et 3 sont liées à ce latent : elles sont les candidates de x0
        u = {"relations": [("eq", 0, ((0, 1), (1, -1))), ("eq", 0, ((1, 1), (2, 1), (3, -1)))], "cellule": [True, False, True, True],
             "publiee": [False, False, True, True], "valeur": [None, None, 8, 6]}
        self.assertEqual(self.unite_fictive()._voisine(u, 0), (3, 8))

    def test_les_termes_de_chaque_relation_suivent_l_ordre_des_cles_et_les_relations_leur_premier_terme(self):
        """Parité avec la migration : termes par variable croissante (le produit de P4 en dernier), relations de chaque sorte par premier terme."""
        _, unite = photo(x23())
        relations = unite._construire()["relations"]
        self.assertTrue(relations)
        for sorte, _, termes in relations:
            variables = [v for v, _ in termes]
            self.assertEqual(variables, sorted(variables))
        produits = [r for r in relations if r[0] == "eq" and len(r[2]) >= 2 and r[2][-1][1] == 1 and all(c == -1 for _, c in r[2][:-1])]
        self.assertTrue(produits)                                                    # P4 : équipes (-1) puis le produit (+1)

    def test_les_cellules_du_produit_viennent_apres_celles_des_equipes(self):
        _, unite = photo(x23())
        u = unite._construire()
        rangs = [(unite._cle_ligne(d[1])[0]) for d in u["definition"] if d[0] == "c"]
        self.assertEqual(rangs, sorted(rangs))
        self.assertEqual(set(rangs), {0, 1})
        premiere_du_produit = rangs.index(1)
        self.assertTrue(all(r == 0 for r in rangs[:premiere_du_produit]))


class LectureLaPlusStricte(unittest.TestCase):
    """Décision 14 : les deux lectures de l'excès, la plus stricte décide. Ici seule la lecture « m = 0 » épingle une cellule : semaine un
    créés 40, sans affects 5, trouvés 30 et 20 ; semaine deux créés 43 (masqué par la chaîne : 43 - 40 = 3), sans affects 5, trouvés 20 et 18.
    Lecture « m libre » : les défauts distincts valent de 20 à 38, les créés de 25 à 43 (la chaîne les borne à 44), plusieurs valeurs.
    Lectures de l'attaquant qui parie (M7 a de la fiche R-20261104-6) : « m = 0 » seul laisse les créés de 43 à 44 (U libre) ; « U = 0 et m = 0 » donne
    les défauts distincts 38 et les créés 43 : épinglés (la sévérité de D15 écrit). Les créés restent donc masqués avec sans affects."""
    LIGNES = [libre(S1, "A", 40, 5), version(S1, "A", 1, 30), version(S1, "A", 2, 20),
              libre(S2, "A", 43, 5), version(S2, "A", 3, 20), version(S2, "A", 4, 18)]

    def test_seule_la_lecture_m_nul_epingle_la_cellule(self):
        rangees = [dict(zip(NOMS, ligne)) for ligne in self.LIGNES]
        vis = [{} for _ in rangees]
        prises = []

        def arreter_avant_la_boucle(self, regles, lim):      # l'état après les règles existantes seulement : la chaîne a masqué les créés
            prises.append(self)
        with unittest.mock.patch.object(fv._UnitePhoto, "propager", arreter_avant_la_boucle):
            fv._masque_photo(NOMS, rangees, 5, [set() for _ in rangees], vis)
        unite = prises[0]
        self.assertFalse(vis[3]["defects_created"])                                  # masqué par la chaîne seule
        self.assertTrue(vis[3]["defects_without_affects"])
        u = unite._construire()
        cree = next(v for v, d in enumerate(u["definition"]) if d == ("c", 3, "defects_created"))
        m = next(v for v, d in enumerate(u["definition"]) if d == ("m", 3))
        lo, hi, vide = fv._propager(u["lo"], u["hi"], u["relations"], 10 ** 6, 10 ** 6)
        self.assertFalse(vide)
        self.assertGreater(hi[cree] - lo[cree], 0)                                   # lecture « m libre » : plusieurs valeurs
        self.assertEqual(lo[m], 0)                                                   # le pari « m = 0 » tient pour cette ligne
        libre_u = next(v for v, d in enumerate(u["definition"]) if d == ("U", 3))
        self.assertEqual(lo[libre_u], 0)                                             # le pari « U = 0 » tient aussi
        lo0, hi0 = list(u["lo"]), list(u["hi"])
        lo0[m] = hi0[m] = 0
        lo2, hi2, vide2 = fv._propager(lo0, hi0, u["relations"], 10 ** 6, 10 ** 6)
        self.assertFalse(vide2)
        self.assertEqual((lo2[cree], hi2[cree]), (43, 44))                           # « m = 0 » seul, U libre : deux valeurs
        lo0[libre_u] = hi0[libre_u] = 0
        lo2, hi2, vide2 = fv._propager(lo0, hi0, u["relations"], 10 ** 6, 10 ** 6)
        self.assertFalse(vide2)
        self.assertEqual((lo2[cree], hi2[cree]), (43, 43))                           # « U = 0 et m = 0 » : la valeur unique 43
        # la lecture la plus stricte décide : la boucle masque la voisine, sans affects de la semaine deux
        vis_finale, _ = photo(self.LIGNES)
        self.assertFalse(vis_finale[3]["defects_created"])
        self.assertFalse(vis_finale[3]["defects_without_affects"])
        self.assertTrue(vis[3]["defects_without_affects"])                          # sans la boucle de D15, sans affects restait publiée : c'est elle qui la masque


class LecturesDuTermeLatentParLigne(unittest.TestCase):
    """M7 (a) de la fiche R-20261104-6 : par ligne, les lectures « m_r = 0 », « U_r = 0 » et « U_r = 0 et m_r = 0 » en plus de « m libre » ; une lecture
    vide (contredite par les cellules publiées) est écartée ; une limite atteinte échoue fermé."""
    LIGNES = LectureLaPlusStricte.LIGNES

    @staticmethod
    def signature(u, lo, hi):
        """Quelles variables latentes de la lecture sont fixées à 0 : (m, U)."""
        m = next(v for v, d in enumerate(u["definition"]) if d == ("m", 3))
        libre_u = next(v for v, d in enumerate(u["definition"]) if d == ("U", 3))
        return (hi[m] == 0, hi[libre_u] == 0)

    def lectures_jouees(self):
        _, unite = photo(self.LIGNES)
        u = unite._construire()
        vues = []
        original = fv._propager

        def enregistrer(lo, hi, relations, borne_m, limite):
            vues.append(self.signature(u, lo, hi))
            return original(lo, hi, relations, borne_m, limite)
        with unittest.mock.patch.object(fv, "_propager", enregistrer):
            unite._epingles(u, None)
        return vues

    def test_les_quatre_lectures_sont_jouees_par_ligne(self):
        vues = self.lectures_jouees()
        for lecture in [(False, False), (True, False), (False, True), (True, True)]:
            self.assertIn(lecture, vues)

    def test_une_lecture_vide_est_ecartee(self):
        _, unite = photo(self.LIGNES)
        u = unite._construire()
        original = fv._propager

        def vider_u_nul_et_m_nul(lo, hi, relations, borne_m, limite):
            lo2, hi2, vide = original(lo, hi, relations, borne_m, limite)
            return lo2, hi2, vide or self.signature(u, lo, hi) == (True, True)
        with unittest.mock.patch.object(fv, "_propager", vider_u_nul_et_m_nul):
            vis, _ = photo(self.LIGNES)
        self.assertTrue(vis[3]["defects_without_affects"])                          # sans la lecture « U = 0 et m = 0 », rien n'épingle les créés

    def test_une_limite_atteinte_de_la_lecture_u_nul_leve_masquage_instable(self):
        _, unite = photo(self.LIGNES)
        u = unite._construire()
        original = fv._propager

        def limiter_u_nul(lo, hi, relations, borne_m, limite):
            return original(lo, hi, relations, borne_m, 0 if self.signature(u, lo, hi) == (False, True) else limite)
        with unittest.mock.patch.object(fv, "_propager", limiter_u_nul):
            with self.assertRaises(fv.MasquageInstable):
                unite._epingles(u, None)

    def test_une_limite_atteinte_de_la_lecture_u_nul_et_m_nul_leve_masquage_instable(self):
        _, unite = photo(self.LIGNES)
        u = unite._construire()
        original = fv._propager

        def limiter(lo, hi, relations, borne_m, limite):
            return original(lo, hi, relations, borne_m, 0 if self.signature(u, lo, hi) == (True, True) else limite)
        with unittest.mock.patch.object(fv, "_propager", limiter):
            with self.assertRaises(fv.MasquageInstable):
                unite._epingles(u, None)

    def test_la_lecture_u_nul_est_ecartee_quand_la_borne_basse_de_u_est_positive(self):
        # créés 60, sans 10, trouvés 3 et 2 : U vaut au moins 45, le pari « U = 0 » est contredit avant d'être joué
        lignes = [libre(S1, "A", 60, 10), version(S1, "A", 1, 3), version(S1, "A", 2, 2)]
        _, unite = photo(lignes)
        u = unite._construire()
        libre_u = next(v for v, d in enumerate(u["definition"]) if d[0] == "U")
        vues = []
        original = fv._propager

        def enregistrer(lo, hi, relations, borne_m, limite):
            vues.append(hi[libre_u])
            return original(lo, hi, relations, borne_m, limite)
        with unittest.mock.patch.object(fv, "_propager", enregistrer):
            unite._epingles(u, None)
        self.assertNotIn(0, vues)


class TermeLatentDesVersionsNonRetenues(unittest.TestCase):
    """M1 (a) de la fiche R-20261104-6 : « D + m = somme des trouvés retenus » devient « D + m = somme des trouvés retenus + U », U >= 0 sans borne haute
    (D4 (d) : les versions non retenues forment un terme inconnu de borne basse 0), des deux côtés. Les comptes sont cumulés et une version n'est retenue
    qu'une semaine : les défauts distincts dépassent souvent la somme retenue."""

    def test_crees_60_sans_10_trouves_retenus_3_et_2_la_vue_ne_tombe_plus_en_exception(self):
        lignes = [libre(S1, "A", 60, 10), version(S1, "A", 1, 3), version(S1, "A", 2, 2)]
        vis, _ = photo(lignes)                                                    # avant : MasquageInstable (lecture « m libre » vide)
        # les deux trouvés sont masqués par le seuil ; rien d'autre : les défauts distincts (50) dépassent la somme retenue (5), un terme non retenu
        self.assertEqual(masquees(vis, lignes, "found"), {(S1, "A", 1), (S1, "A", 2)})
        self.assertEqual(masquees(vis, lignes, "defects_created"), set())
        self.assertEqual(masquees(vis, lignes, "defects_without_affects"), set())

    def test_le_terme_latent_n_a_pas_de_borne_haute_et_les_trouves_masques_gardent_plusieurs_valeurs(self):
        lignes = [libre(S1, "A", 60, 10), version(S1, "A", 1, 3), version(S1, "A", 2, 2)]
        _, unite = photo(lignes)
        u = unite._construire()
        latents = [v for v, d in enumerate(u["definition"]) if d[0] == "U"]
        self.assertEqual(len(latents), 1)
        self.assertEqual((u["lo"][latents[0]], u["hi"][latents[0]]), (0, None))
        _, largeurs = unite._epingles(u, None)
        self.assertTrue(all(w is None or w >= 1 for w in largeurs.values()))     # aucune valeur unique

    def test_x23_reste_couvert_avec_le_terme_latent(self):
        lignes = x23()
        vis, _ = photo(lignes)
        self.assertEqual(masquees(vis, lignes, "defects_created"), {(S2, "A", None), (S2, fv.PRODUIT, None)})


class LectureMNulParLigne(unittest.TestCase):
    """M2 (a) : une lecture « m = 0 » par ligne (m_r = 0 seul), et une limite atteinte échoue fermé."""
    @staticmethod
    def produit_avec_une_equipe_sans_version_retenue():
        """Équipe A : deux versions par semaine ; équipe B : aucune ligne de version retenue ; le produit reprend A (B n'a pas de trouvé) et somme les
        créés. Le créé de A de la semaine deux est masqué par la chaîne (33 - 30 = 3) et le pari « m = 0 » de A le fixe : 10 + (10 + 14) = 34 = 30 + 4."""
        P = fv.PRODUIT
        return [libre(S1, "A", 30, 10), version(S1, "A", 1, 12), version(S1, "A", 2, 13), libre(S1, "B", 30, 10),
                (S1, True, P, None, None, 60, 20, 40, 20), version(S1, P, 1, 12), version(S1, P, 2, 13),
                libre(S2, "A", 33, 10), version(S2, "A", 3, 10), version(S2, "A", 4, 14), libre(S2, "B", 33, 10),
                (S2, True, P, None, None, 66, 20, 40, 20), version(S2, P, 3, 10), version(S2, P, 4, 14)]

    def test_une_limite_de_la_lecture_m_nul_atteinte_leve_masquage_instable(self):
        lignes = self.produit_avec_une_equipe_sans_version_retenue()
        photo(lignes)                                                              # sans abaisser la limite : pas d'erreur
        with unittest.mock.patch.object(fv, "propagation_zero_max", lambda v, r: 1):
            with self.assertRaises(fv.MasquageInstable):                           # avant : la lecture était écartée sans bruit, la protection tombait
                photo(lignes)

    def test_chaque_lecture_m_nul_ne_fixe_que_le_m_de_sa_ligne(self):
        lignes = self.produit_avec_une_equipe_sans_version_retenue()
        _, unite = photo(lignes)
        u = unite._construire()
        lectures = []
        original = fv._propager

        def enregistrer(lo, hi, relations, borne_m, limite):
            lectures.append(sum(1 for m in u["latents_m"] if hi[m] == 0))
            return original(lo, hi, relations, borne_m, limite)
        with unittest.mock.patch.object(fv, "_propager", enregistrer):
            unite._epingles(u, None)
        self.assertIn(1, lectures)
        self.assertTrue(all(fixes <= 1 for fixes in lectures[1:]), lectures)        # la première lecture est « m libre » ; chaque pari ne fixe qu'un m

    def test_le_pari_m_nul_d_une_equipe_protege_la_cellule_malgre_l_equipe_sans_ligne_de_version(self):
        """La protection de la décision 14 tient : le pari « m = 0 » de A fixe son créé de la semaine deux (34), sa voisine, sans affects, est masquée."""
        lignes = self.produit_avec_une_equipe_sans_version_retenue()
        vis, _ = photo(lignes)
        self.assertIn((S2, "A", None), masquees(vis, lignes, "defects_created"))
        self.assertIn((S2, "A", None), masquees(vis, lignes, "defects_without_affects"))


class MesureApresPropagation(unittest.TestCase):
    """Tâche 6.6 : `masked-cells` rend la largeur de l'intervalle après propagation ; une cellule d'exactement une unité de large est comptée étroite.
    Cas synthétique : semaine un créés 40, sans affects 5, trouvés 30 et 20 ; semaine deux créés 43 (masqué seul par la chaîne), sans affects 5, trouvés 38
    et 20. La ligne donne des créés de 43 à 63 (défauts distincts de 38 à 58), la chaîne les borne à 44 : l'intervalle va de 43 à 44, largeur 1 ; la
    lecture « m = 0 » (défauts distincts 58, créés 63) est écartée par la chaîne : rien n'est épinglé, les créés restent masqués seuls."""
    LIGNES = [libre(S1, "A", 40, 5), version(S1, "A", 1, 30), version(S1, "A", 2, 20),
              libre(S2, "A", 43, 5), version(S2, "A", 3, 38), version(S2, "A", 4, 20)]

    def test_les_creees_masques_seuls_ont_une_largeur_d_une_unite_apres_propagation(self):
        rangees = [dict(zip(NOMS, ligne)) for ligne in self.LIGNES]
        cellules = fv.masquer_vue(fv.VUE_PHOTO, NOMS, self.LIGNES, 5)
        self.assertIn("masked", cellules[3]["defects_created"])
        self.assertNotIn("masked", cellules[3]["defects_without_affects"])
        self.assertEqual(fv._largeurs_photo(NOMS, rangees, 5)[(3, "defects_created")], 1)
        self.assertEqual(fv._intervalles_chaine(NOMS, rangees, cellules, 5), {3: 1})

    def test_masked_cells_compte_la_cellule_d_une_unite_comme_etroite(self):
        def lire(vue, role=None, **connexion):
            return (NOMS, self.LIGNES) if vue == fv.VUE_PHOTO else ([], [])
        with unittest.mock.patch.object(fv, "lire", lire):
            lignes = fv.cellules_masquees(5, fv.Messages(fv.CATALOGS, "en"))
        self.assertIn("view v_version_quality_photo: 1 created-defects cells masked alone by the week chain, 1 of them one unit wide", lignes)
        vue = next(l for l in lignes if l.startswith("view v_version_quality_photo: ") and "masked cells out of" in l)
        self.assertRegex(vue, r", [1-9]\d* of them one unit wide$")

    def test_une_cellule_sans_borne_haute_n_est_jamais_etroite(self):
        _, largeurs = None, fv._largeurs_photo(NOMS, [dict(zip(NOMS, ligne)) for ligne in x23()], 5)
        masquees = [cle for cle, largeur in largeurs.items() if largeur == float("inf")]
        self.assertTrue(all(largeurs[cle] > 1 for cle in largeurs))
        self.assertGreater(len(largeurs), 0)                              # X23 a des cellules masquées mesurées
        self.assertTrue(all(cle in largeurs for cle in masquees))        # chaque cellule sans borne haute est dans la mesure, avec une largeur infinie


if __name__ == "__main__":
    unittest.main()
