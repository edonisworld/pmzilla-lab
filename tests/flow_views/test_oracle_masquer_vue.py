"""
L'oracle de masquage appliqué à la fonction de service masquer_vue (change masking-sums, R-144, conception D8 ; revue, M1).

    bash tests/run_all.sh flow_views

Sans base : masquer_vue est une fonction pure, appliquée aux comptes bruts au plancher (elle redonne alors la vue). Chaque famille de relations
est une règle `publier(table, seuil) -> image` au sens de oracle_masquage.py, sur de petites tables tirées avec des graines fixes :
  - le retard : les cinq tranches d'une ligne et leur total (« M » : total masqué, jamais un None, pour ne pas compter comme cellule) ;
  - la ligne libre de la photo : défauts créés, sans affects et deux trouvés par version, avec la relation vraie des données
    (créés - sans affects = défauts distincts, entre le plus grand trouvé et leur somme) ;
  - les noms et identifiants : le compte d'un nom et ceux de ses identifiants, Jira propre (le compte est la somme des identifiants, cas le
    plus défavorable de la revue, m1).
L'élagage ne garde que les tables dont les cellules visibles sont celles de l'image observée (une cellule visible publie sa valeur exacte) ;
la règle complète est ensuite rejouée sur ces tables seulement. Le test échoue sur toute fuite : valeur unique ou somme unique sous le seuil.
Chiffres inventés ; aucune ligne du Jira réel.
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

# L'oracle (tests/oracle_masquage/oracle_masquage.py) est pur : il n'importe que la bibliothèque standard ; chargé par son chemin, sans rien de la base.
_spec = importlib.util.spec_from_file_location("oracle_masquage", RACINE / "tests" / "oracle_masquage" / "oracle_masquage.py")
oracle = importlib.util.module_from_spec(_spec)
sys.modules["oracle_masquage"] = oracle
_spec.loader.exec_module(oracle)

SEUIL = fv.PLANCHER
GRAINES = (3, 8, 21)


def cellule(c):
    return "M" if "masked" in c else c["value"]


def visibles_egaux(observe, largeur):
    """Élagage : les cellules visibles de l'image observée (colonnes avant `largeur`) sont les valeurs brutes."""
    def elaguer(lignes):
        return all(v is None or v == "M" or ligne[j] == v
                   for ligne, vue in zip(lignes, observe) for j, v in enumerate(vue[:largeur]))
    return elaguer


def sans_fuite(testcase, publier, brut, valeurs, coherente, largeur):
    observe = publier(brut, SEUIL)
    elaguer_visibles = visibles_egaux(observe, largeur)
    resultat = oracle.analyser(publier, brut, SEUIL, valeurs=valeurs, elaguer=lambda l: all(coherente(x) for x in l) and elaguer_visibles(l))
    testcase.assertGreaterEqual(resultat["compatibles"], 1, f"la table brute {brut} doit rester compatible avec son image")
    testcase.assertEqual(resultat["fuites"], [], f"fuite pour {brut} : image {observe}")
    return resultat


# ---------------------------------------------------------------------------------------------------------------------------------------
# Retard : cinq tranches et leur total
# ---------------------------------------------------------------------------------------------------------------------------------------

def publier_retard(table, seuil):
    ligne = ("A", "2026-04-01", sum(table[0]), *table[0])
    c = fv.masquer_vue(fv.VUE_RETARD, ["team", "quarter_start", "items", *fv.SEAUX_RETARD], [ligne], seuil)[0]
    return (tuple(None if "masked" in c[b] else c[b]["value"] for b in fv.SEAUX_RETARD) + (cellule(c["items"]),),)


class Retard(unittest.TestCase):
    def tables(self, graine):
        hasard = random.Random(graine)
        return [(tuple(hasard.choice([0, 1, 2, 3, 4, 5, 6, 7]) for _ in fv.SEAUX_RETARD),) for _ in range(3)]

    def verifier(self, brut):
        sans_fuite(self, publier_retard, brut, range(0, 13), lambda ligne: True, 5)

    def test_tables_tirees_graine_3(self):
        for brut in self.tables(3):
            self.verifier(brut)

    def test_tables_tirees_graine_8(self):
        for brut in self.tables(8):
            self.verifier(brut)

    def test_tables_tirees_graine_21(self):
        for brut in self.tables(21):
            self.verifier(brut)

    def test_deux_tranches_masquees_de_somme_dix_entre_trois_visibles(self):
        self.verifier(((2, 3, 6, 5, 5),))                       # somme masquée 5 : au seuil
        self.verifier(((4, 1, 6, 5, 5),))
        self.verifier(((0, 0, 7, 8, 9),))                       # deux zéros masqués : somme nulle, la ligne complète le complément


# ---------------------------------------------------------------------------------------------------------------------------------------
# Photo : la ligne sans version (défauts créés, sans affects) et ses trouvés par version
# ---------------------------------------------------------------------------------------------------------------------------------------

NOMS_PHOTO = ["week_start", "n_adopted", "team", "version_no", "found", "defects_created", "defects_without_affects", "resolved_week",
              "resolved_week_defects"]


def publier_libre(table, seuil):
    crees, sans, f1, f2 = table[0]
    lignes = [("2026-03-02", True, "A", None, None, crees, sans, 20, 10),
              ("2026-03-02", True, "A", 1, f1, None, None, None, None),
              ("2026-03-02", True, "A", 2, f2, None, None, None, None)]
    c = fv.masquer_vue(fv.VUE_PHOTO, NOMS_PHOTO, lignes, seuil)
    return ((c[0]["defects_created"]["value"] if "masked" not in c[0]["defects_created"] else None,
             c[0]["defects_without_affects"]["value"] if "masked" not in c[0]["defects_without_affects"] else None,
             c[1]["found"]["value"] if "masked" not in c[1]["found"] else None,
             c[2]["found"]["value"] if "masked" not in c[2]["found"] else None),)


def coherente_libre(ligne):
    """La relation vraie : créés = sans affects + défauts distincts avec affects, entre le plus grand trouvé et leur somme ; un trouvé peut être nul
    (une ligne de version à zéro existe et compte comme terme caché, décision de la revue 4)."""
    crees, sans, f1, f2 = ligne
    return sans <= crees and max(f1, f2) <= crees - sans <= f1 + f2


class LigneLibreDeLaPhoto(unittest.TestCase):
    def tables(self, graine):
        hasard = random.Random(graine)
        tables = []
        while len(tables) < 3:
            f1, f2 = hasard.randint(1, 8), hasard.randint(1, 8)
            distincts = hasard.randint(max(f1, f2), f1 + f2)
            sans = hasard.choice([0, 3, 5, 9])
            tables.append(((sans + distincts, sans, f1, f2),))
        return tables

    def verifier(self, brut):
        self.assertTrue(coherente_libre(brut[0]), brut)
        # Propriété du point fixe (décision du 2026-10-27) : la relation publiée ne laisse jamais une seule cellule cachée (relue par différence)
        publiee = publier_libre(brut, SEUIL)[0]
        self.assertNotEqual(sum(v is None for v in publiee), 1, f"une seule cellule cachée pour {brut} : image {publiee}")
        sans_fuite(self, publier_libre, brut, range(0, max(brut[0]) + 1), coherente_libre, 4)

    def test_tables_tirees_graine_3(self):
        for brut in self.tables(3):
            self.verifier(brut)

    def test_tables_tirees_graine_8(self):
        for brut in self.tables(8):
            self.verifier(brut)

    def test_tables_tirees_graine_21(self):
        for brut in self.tables(21):
            self.verifier(brut)

    def test_temoin_l_oracle_voit_la_fuite_d_une_regle_sans_complement(self):
        """Témoin négatif : sans règle de ligne à compléter (seule la cellule sous 5 est masquée), 13 - 5 = 8 force les deux trouvés à 4."""
        def naive(table, seuil):
            crees, sans, f1, f2 = table[0]
            return ((crees, sans, None if f1 < seuil else f1, None if f2 < seuil else f2),)
        brut = ((13, 5, 4, 4),)
        resultat = oracle.analyser(naive, brut, SEUIL, valeurs=range(0, 14),
                                   elaguer=lambda l: all(coherente_libre(x) for x in l) and visibles_egaux(naive(brut, SEUIL), 4)(l))
        self.assertEqual(resultat["intervalles"], {(0, 2): (4, 4), (0, 3): (4, 4)})
        self.assertEqual(len(resultat["fuites"]), 2)

    def test_cas_b1_deux_trouves_de_quatre_dont_la_difference_est_huit(self):
        self.verifier(((13, 5, 4, 4),))                         # créés 13, sans affects 5 : 8 = somme des bornes hautes (30 et 22 dans le cas X12b)

    def test_cas_x12_ligne_publiee_en_entier_avec_un_exces_de_deux(self):
        self.verifier(((16, 5, 7, 6),))                         # trouvés 7 et 6, défauts distincts 11 : excès 2 (40, 10, 20 et 12 dans le cas X12)

    def test_cas_x18_exces_nul_une_seule_cellule_cachee_serait_lue_par_difference(self):
        self.verifier(((20, 8, 6, 6),))                         # distincts 12 = 6 + 6 : excès nul, sans affects (8) masqué par D5-e, les créés avec lui


# ---------------------------------------------------------------------------------------------------------------------------------------
# Noms et identifiants : le compte d'un nom et ceux de ses identifiants
# ---------------------------------------------------------------------------------------------------------------------------------------

NOMS_EQUIPES = ["team", "team_type", "tickets"]
NOMS_IDS = ["team", "jira_team_id", "tickets"]
NOMS_STATUT = ["team", "type", "status_category", "status", "tickets"]


def publier_noms(table, seuil):
    compte, *identifiants = table[0]
    equipes = [("N", None, compte)]
    ids = [("N", f"id{k}", v) for k, v in enumerate(identifiants, start=1)]
    # D5-a : comptes de statut du nom (un grand, une cellule de 1 quand le compte le permet), comme la vue des statuts les publie au plancher
    cellules_statut = [compte - 1, 1] if compte >= 2 else [compte]
    statuts = [("N", "Story", "Done", f"s{k}", None if v < seuil else v) for k, v in enumerate(cellules_statut)]
    liees_statut = {"v_team_status": (NOMS_STATUT, statuts)}
    nom = fv.masquer_vue("v_teams", NOMS_EQUIPES, equipes, seuil, liees={"v_team_jira_ids": (NOMS_IDS, ids), **liees_statut})
    # la vue des identifiants lit la vue des noms telle qu'elle est publiée (le compte masqué est un nul), jamais le compte brut (revue 2, m3)
    publiee = [("N", None, None if "masked" in nom[0]["tickets"] else nom[0]["tickets"]["value"])]
    cellules = fv.masquer_vue("v_team_jira_ids", NOMS_IDS, ids, seuil, liees={"v_teams": (NOMS_EQUIPES, publiee), **liees_statut})
    return ((None if "masked" in nom[0]["tickets"] else nom[0]["tickets"]["value"],)
            + tuple(None if "masked" in c["tickets"] else c["tickets"]["value"] for c in cellules),)


def coherente_noms(ligne):
    """Jira propre : le compte du nom est la somme de ses identifiants, chacun d'au moins 1 (une ligne de GROUP BY)."""
    return all(v >= 1 for v in ligne[1:]) and ligne[0] == sum(ligne[1:])


class NomsEtIdentifiants(unittest.TestCase):
    def tables(self, graine):
        hasard = random.Random(graine)
        tables = []
        for _ in range(4):
            ids = tuple(hasard.choice([1, 2, 3, 4, 5, 5, 6, 8]) for _ in range(hasard.randint(1, 3)))
            tables.append(((sum(ids),) + ids,))
        return tables

    def verifier(self, brut):
        sans_fuite(self, publier_noms, brut, range(1, max(brut[0]) + 1), coherente_noms, len(brut[0]))

    # Tâche 5.11 (décision de l'auteur du 2026-10-27) : un nom masqué masque TOUS ses identifiants visibles ; masquer le seul plus petit
    # épinglait la cellule masquée (ex. 19 ; 6, 5, 8 et 14 ; 1, 8, 5, cas partagés X16 et X17).
    def test_tables_tirees_graine_3(self):
        for brut in self.tables(3):
            self.verifier(brut)

    def test_tables_tirees_graine_8(self):
        for brut in self.tables(8):
            self.verifier(brut)

    def test_tables_tirees_graine_21(self):
        for brut in self.tables(21):
            self.verifier(brut)

    def test_cas_fixes_de_la_revue(self):
        self.verifier(((8, 4, 4),))                             # X2
        self.verifier(((14, 4, 4, 6),))                         # M2 (a)
        self.verifier(((8, 3, 5),))                             # M2 (a), le complément masque le nom
        self.verifier(((28, 28),))                              # un seul identifiant, le compte du nom égal au sien


# ---------------------------------------------------------------------------------------------------------------------------------------
# Photo sur trois semaines retenues : la relation (somme, différence, chaîne) ne laisse jamais une seule cellule cachée (décision du 2026-10-27)
# ---------------------------------------------------------------------------------------------------------------------------------------

SEMAINES_PHOTO = ("2026-03-02", "2026-03-09", "2026-03-16")


def publier_semaines(table, seuil):
    """Une équipe, trois semaines : (créés, sans affects, trouvé 1, trouvé 2) par semaine, publiés à l'identique de la vue au plancher."""
    lignes = []
    for k, (semaine, (crees, sans, f1, f2)) in enumerate(zip(SEMAINES_PHOTO, table)):
        lignes += [(semaine, True, "A", None, None, crees, sans, 20, 10), (semaine, True, "A", 2 * k + 1, f1, None, None, None, None),
                   (semaine, True, "A", 2 * k + 2, f2, None, None, None, None)]
    cellules = fv.masquer_vue(fv.VUE_PHOTO, NOMS_PHOTO, lignes, seuil)
    valeur = lambda c: None if "masked" in c else c["value"]
    return [(valeur(cellules[3 * k]["defects_created"]), valeur(cellules[3 * k]["defects_without_affects"]),
             valeur(cellules[3 * k + 1]["found"]), valeur(cellules[3 * k + 2]["found"])) for k in range(3)]


def largeurs_intervalles_creees(publiee):
    """Largeur de chaque intervalle où se place un créé masqué seul par la chaîne des semaines : « créés = sans affects + défauts distincts », les
    défauts distincts allant de max(trouvés) à leur somme, soit une largeur de somme - max (la plus petite des deux valeurs avec deux termes)."""
    largeurs = []
    for crees, sans, f1, f2 in publiee:
        if crees is None and None not in (sans, f1, f2):
            largeurs.append(f1 + f2 - max(f1, f2))
    return largeurs


class SemainesDeLaPhoto(unittest.TestCase):
    def test_largeurs_des_intervalles_de_creees_masques_seuls(self):
        """La propriété rapporte la liste des largeurs, une par semaine concernée."""
        # M3 (R-20261104-6) : tables remplacées, attendu gardé. D15 pose la lecture « m = 0 » : un créé masqué seul par la chaîne serait épinglé à
        # sans affects + somme des trouvés, et sa voisine masquée, sauf si la chaîne exclut cette valeur ; la chaîne la borne en dessous dans les tables de M8 ci-dessous.
        # M8 (R-20261104-12) : tables de la section C de la revue du 2026-11-04 (S2 masqué par la chaîne : 22 - 18 = 4 et 28 - 25 = 3 ; S1 et S3 ont un
        # excès d'au moins 5), attendus [8] et [7] d'origine gardés ; sous « U = 0 et m = 0 » la lecture est vide (28 > 22, 30 > 29) et écartée.
        self.assertEqual(largeurs_intervalles_creees(publier_semaines([(18, 10, 7, 6), (22, 10, 8, 10), (50, 20, 20, 15)], SEUIL)), [8])
        self.assertEqual(largeurs_intervalles_creees(publier_semaines([(25, 5, 14, 11), (28, 5, 7, 18), (40, 10, 18, 20)], SEUIL)), [7])
        self.assertEqual(largeurs_intervalles_creees([(None, 10, 6, 6), (40, 10, 6, 6), (None, None, None, None)]), [6])

    def test_aucun_intervalle_d_une_seule_unite_sur_les_tables_tirees(self):
        for graine in (3, 8, 21, 34):
            for table in self.tables(graine):
                for largeur in largeurs_intervalles_creees(publier_semaines(table, SEUIL)):
                    self.assertGreaterEqual(largeur, 2, f"intervalle d'une unité : table {table}")

    def tables(self, graine):
        hasard = random.Random(graine)
        tables = []
        for _ in range(6):
            semaines = []
            for _ in SEMAINES_PHOTO:
                f1, f2 = hasard.randint(1, 12), hasard.randint(1, 12)
                distincts = hasard.randint(max(f1, f2), f1 + f2)
                sans = hasard.choice([0, 3, 5, 9, 10, 13, 20])
                semaines.append((sans + distincts, sans, f1, f2))
            tables.append(semaines)
        return tables

    def verifier(self, table):
        publiee = publier_semaines(table, SEUIL)
        for semaine in publiee:                                          # somme et différence : jamais une seule cellule cachée
            cachees = [j for j, v in enumerate(semaine) if v is None]
            # seule exception : les créés masqués seuls par la chaîne des semaines (D5-d) ; « créés = sans affects + défauts distincts » ne les fixe
            # qu'à un intervalle (les défauts distincts valent de max(trouvés) à leur somme), jamais à une valeur
            self.assertIn(len(cachees), (0, 2, 3, 4) if cachees != [0] else (1,), f"une seule cellule cachée : table {table}, image {publiee}")
        for colonne in (0, 1):                                           # chaîne : deux semaines publiées voisines ne diffèrent pas de 1 à 4
            valeurs = [s[colonne] for s in publiee if s[colonne] is not None]
            for a, b in zip(valeurs, valeurs[1:]):
                self.assertNotIn(abs(a - b), range(1, SEUIL), f"écart de {abs(a - b)} entre semaines publiées : table {table}, image {publiee}")

    def test_tables_tirees_graine_3(self):
        for table in self.tables(3):
            self.verifier(table)

    def test_tables_tirees_graine_8(self):
        for table in self.tables(8):
            self.verifier(table)

    def test_tables_tirees_graine_21(self):
        for table in self.tables(21):
            self.verifier(table)

    def test_cas_x20_trois_semaines(self):
        self.verifier([(40, 10, 16, 20), (45, 20, 25, 25), (50, 13, 20, 23)])       # 10, 20, 13 : l'écart 3 apparaît quand D2 masque 20


# ---------------------------------------------------------------------------------------------------------------------------------------
# Ligne du produit de la photo : l'ordre D3, puis D5-d (semaines enchaînées), puis D2 (tâche 5.12, D13, question 12)
# ---------------------------------------------------------------------------------------------------------------------------------------

S1, S2, S3 = "2026-03-02", "2026-03-09", "2026-03-16"


def libre(semaine, equipe, crees, sans):
    return (semaine, True, equipe, None, None, crees, sans, None, None)


def version_produit(semaine, trouves, numero=1):
    return (semaine, True, fv.PRODUIT, numero, trouves, None, None, None, None)


def version_equipe(semaine, equipe, trouves, numero=1):
    return (semaine, True, equipe, numero, trouves, None, None, None, None)


def masquees_photo(lignes, colonnes=("defects_created", "defects_without_affects")):
    """Ensemble des (semaine, équipe, version, colonne) masqués parmi les colonnes jugées des lignes libres."""
    cellules = fv.masquer_vue(fv.VUE_PHOTO, NOMS_PHOTO, lignes, SEUIL)
    return {(l[0], l[2], c) for l, cel in zip(lignes, cellules) if l[3] is None for c in colonnes if "masked" in cel[c]}


class OrdreDeLaLigneProduit(unittest.TestCase):
    """Chaque test fixe deux étapes voisines : un autre ordre publie une autre cellule (l'autre résultat est donné en commentaire)."""

    def test_d3_avant_d5_d_la_semaine_masquee_par_d3_sort_de_la_chaine(self):
        """Créés du produit 50, 55, 58 ; la cellule de l'équipe A de la semaine 2 est cachée. D3 masque le produit de S2, puis la chaîne relie S1 et S3
        (écart 8 : publié). Avec D5-d avant D3, la chaîne lit 55 puis 58 (écart 3) et masquerait S3."""
        # M4 (R-20261104-6) : équipes rendues cohérentes avec le produit (P4 : 30 + 20, 25 + 30, 38 + 20), attendu inchangé ; les anciens comptes d'équipe
        # (40 + 40 pour 50) violaient la relation de la ligne du produit.
        # Données réécrites (R-20261106-22 et R-20261106-23, écart D4 (d) rétabli) : une ligne sans ligne de version a toujours ses créés masqués par D2, qui
        # passerait avant D3 et D5-d ; chaque équipe et le produit ont maintenant deux versions par semaine (excès de 5 à 10 sur les défauts distincts),
        # mêmes créés, mêmes sans affects, mêmes attendus. Les trouvés du produit sont les sommes de ceux des équipes.
        lignes = [libre(S1, "A", 30, 5), libre(S2, "A", None, 5), libre(S3, "A", 38, 5),
                  libre(S1, "B", 20, 5), libre(S2, "B", 30, 5), libre(S3, "B", 20, 5),
                  libre(S1, fv.PRODUIT, 50, 10), libre(S2, fv.PRODUIT, 55, 10), libre(S3, fv.PRODUIT, 58, 10)]
        for semaine, a, b in ((S1, (15, 15), (10, 10)), (S2, (10, 15), (15, 15)), (S3, (19, 19), (10, 10))):
            for numero in (1, 2):
                lignes += [version_equipe(semaine, "A", a[numero - 1], numero), version_equipe(semaine, "B", b[numero - 1], numero),
                           version_produit(semaine, a[numero - 1] + b[numero - 1], numero)]
        # sans affects de la semaine 2 suit les créés cachés (la paire D11 : le tout moins la partie) ; seule la colonne des créés est en jeu ici
        self.assertEqual({m for m in masquees_photo(lignes) if m[2] == "defects_created"},
                         {(S2, "A", "defects_created"), (S2, fv.PRODUIT, "defects_created")})

    def test_d5_d_avant_d2_la_chaine_masque_sans_affects_puis_d2_masque_les_crees(self):
        """Produit S1 : créés 60, sans affects 30 ; S2 : 70 et 33 (écart 3 : la chaîne D5-d masque sans affects). Deux trouvés publiés par semaine (20
        et 15, 25 et 17 : défauts distincts 30 et 37, excès 5 et 5) : D2 voit sans affects de S2 masqué et, avec un seul terme caché, masque les créés.
        Le test fixe le résultat, pas l'ordre : avec la boucle à point fixe de D13 (chaîne puis D2, repassés jusqu'à stabilité), D2 d'abord donne le
        même résultat à la deuxième passe ; seule une passe unique laisserait les créés publiés. Une mutation qui inverse `chainer` et `completer`
        dans `boucle` ne ferait donc pas échouer ce test (remarque de la revue Opus du 2026-11-04) : il n'affirme pas l'ordre D5-d puis D2."""
        # M3 (R-20261104-6), M8 (R-20261104-12) : lignes d'équipe retirées (la relation P4 ne les lie pas au produit) ; données cohérentes avec P2 (deux
        # trouvés par semaine, excès d'au moins 5) ; attendu gardé. Avec un seul trouvé de 40 pour 30 défauts distincts, la donnée était incohérente.
        lignes = [libre(S1, fv.PRODUIT, 60, 30), libre(S2, fv.PRODUIT, 70, 33),
                  version_produit(S1, 20, 1), version_produit(S1, 15, 2), version_produit(S2, 25, 3), version_produit(S2, 17, 4)]
        self.assertEqual(masquees_photo(lignes), {(S2, fv.PRODUIT, "defects_without_affects"), (S2, fv.PRODUIT, "defects_created")})

    def test_d3_avant_d2_la_cellule_masquee_par_d3_est_lue_par_d2(self):
        """Semaine S1 : sans affects de l'équipe A caché, créés 12 et sans affects 7 au produit, deux trouvés masqués (1 et 4). D3 masque sans affects du
        produit, D2 masque alors les créés (12 = 4 + 2 x 4). Avec D2 avant D3, D2 voit sans affects publié (excès 12 - 7 = 5 : rien à masquer) et les
        créés resteraient. (Données d'origine, sans ligne de version d'équipe : créés 60, sans affects 30, un trouvé publié de 40 ; réécrites selon
        R-20261106-24.)"""
        # M3 (R-20261104-6) : le trouvé 40 dépassait les défauts distincts du produit (60 - 30 = 30), donnée incohérente avec P2 : 30, même résultat de
        # D2 ; D15 ajoute deux cellules à l'attendu (une cellule masquée qui n'a plus qu'une valeur masque une voisine) : les créés de A et sans affects de B.
        # Données réécrites, assertion gardée (R-20261106-24 (a), après R-20261106-22 et R-20261106-23 : écart D4 (d) rétabli, une équipe sans ligne de
        # version a toujours ses créés masqués par D2, qui passait avant D3). Chaque équipe a une ligne de version, le produit en a deux, toutes deux
        # masquées : A 6 / 2 (sans affects caché, primaire), trouvé v3 = 4 ; B 6 / 5 (sans affects caché, la paire : 6 - 5 < 5), trouvé v1 = 1 ; produit
        # 12 / 7, trouvés v1 = 1 et v3 = 4. D3 masque sans affects du produit (7) ; D2 voit alors deux termes cachés et une somme 12 = 4 + 2 x 4 : il masque
        # les créés. Avec D2 avant D3, sans affects publié, l'excès 12 - 7 - 0 = 5 n'est ni sous le seuil ni égal à 0 ou à 2 x 4 : les créés resteraient.
        # D15 : les créés du produit (12 = A 6 + B 6, P4) épinglés masquent les créés de A (règle « d15 », borne 6), puis sans affects de A ; B.c reste
        # publié. Vérifié par l'oracle : DonneesReecritesDeLOracle, tests/oracle_masquage/test_oracle_ecart_d4d.py.
        lignes = [libre(S1, "A", 6, 2), version_equipe(S1, "A", 4, 3), libre(S1, "B", 6, 5), version_equipe(S1, "B", 1, 1),
                  libre(S1, fv.PRODUIT, 12, 7), version_produit(S1, 1, 1), version_produit(S1, 4, 3)]
        # Revue finale du 2026-11-04 (point 2) : l'attendu d'origine, en égalité stricte sur les cinq cellules, (S1, B, sans affects) comprise, est rétabli.
        # Ce n'est pas un sur-masquage : sous la lecture « U = 0 », D_P + m_P = 30 et D_P >= 30 donnent D_P = 30, P.sans = 30 et A.sans = 15 (valeur
        # unique au premier passage, A.créés et B.créés étant publiés) ; A.sans, première dans l'ordre des clés, masque sa voisine la plus petite
        # (B.sans) ; au second passage, P.créés épinglé masque A.créés. La condition de R-20261104-12 (un oracle qui montre B.sans sûre) n'est pas remplie.
        self.assertEqual(masquees_photo(lignes),
                         {(S1, "A", "defects_without_affects"), (S1, fv.PRODUIT, "defects_without_affects"), (S1, fv.PRODUIT, "defects_created"),
                          (S1, "A", "defects_created"), (S1, "B", "defects_without_affects")})

    def test_d5_d_avant_d2_cascade_de_d15_sur_une_cellule_d_equipe(self):
        """M3 (R-20261104-6), test neuf : D3, D5-d et D2 laissent publiés les créés de l'équipe A ; le produit (créés masqués par D2) les donne par P4
        (créés du produit 12 = A 6 + B 6 ; à l'origine 60 = A 30 + B 30, réécrit selon R-20261106-24), D15 les masque donc comme voisine d'une cellule
        épinglée. Sans la propagation, la cellule d'équipe reste publiée."""
        # Données réécrites, assertions gardées (R-20261106-24 (a), après R-20261106-22 et R-20261106-23) : celles du test précédent, où chaque équipe a
        # une ligne de version et le produit deux trouvés masqués. Créés du produit 12 = A 6 + B 6 (P4) ; D3, D5-d et D2 laissent publiés les créés de A,
        # D2 masque ceux du produit, D15 masque ceux de A comme voisine des créés du produit épinglés.
        lignes = [libre(S1, "A", 6, 2), version_equipe(S1, "A", 4, 3), libre(S1, "B", 6, 5), version_equipe(S1, "B", 1, 1),
                  libre(S1, fv.PRODUIT, 12, 7), version_produit(S1, 1, 1), version_produit(S1, 4, 3)]
        with unittest.mock.patch.object(fv._UnitePhoto, "propager", lambda self, regles, limites: None):
            sans_propagation = masquees_photo(lignes)
        self.assertNotIn((S1, "A", "defects_created"), sans_propagation)
        self.assertIn((S1, "A", "defects_created"), masquees_photo(lignes))


if __name__ == "__main__":
    unittest.main()
