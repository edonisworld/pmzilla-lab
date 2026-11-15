"""Propagation des bornes de la photo contre la base (change du masquage des sommes, R-144, groupe 6, tâches 6.1, 6.5 et 6.6 ; conception D4, D12, D15).

    bash tools/dbtest.sh db

Écrit pour le dbtest de l'auteur : aucune de ces classes ne tourne sans la base jetable de test_flow_schema.py (elles sont sautées sans elle) et aucune
n'est lancée par une session. Le cas partagé X23 contre la vue (6.1), le marqueur 2 (6.2), les limites abaissées de flow.propager_bornes et de
flow.photo_masque, qui lèvent une exception et ne rendent aucune ligne (6.5), la parité de la fonction SQL avec `masquer_vue` au plancher sur des photos
de plusieurs semaines avec produit, tirées avec des graines fixes (6.6). La lecture statique du fichier est dans
tests/flow_views/test_masquage_propagation_statique.py. Données inventées : équipes A à C, semaines de mars 2026, versions synthétiques.
"""
import datetime as dt
import random
import unittest

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402
import test_flow_version_photo_views as photo   # noqa: E402
import flow_views as fv         # noqa: E402

PRODUIT = "(produit)"
NOMS = ["week_start", "n_adopted", "team", "version_no", "found", "defects_created", "defects_without_affects", "resolved_week",
        "resolved_week_defects"]
APPEL = "SELECT * FROM flow.photo_masque(%s::date[], %s::text[], %s::integer[], %s::bigint[], %s::bigint[], %s::integer, %s::bigint)"
S1, S2, S3 = dt.date(2026, 3, 2), dt.date(2026, 3, 9), dt.date(2026, 3, 16)


def cle(ligne):
    """Clé de la fonction : rang de ligne (équipes 0, produit 1), semaine, équipe en ordre d'octets, version (la ligne sans version d'abord)."""
    return (1 if ligne[2] == PRODUIT else 0, ligne[0], ligne[2].encode("utf-8"), -1 if ligne[3] is None else ligne[3])


def tableaux(lignes):
    """Les cinq tableaux de flow.photo_masque pour des lignes au format de NOMS, rangées par la clé ; chaque ligne porte neuf comptes à plat."""
    rangees = sorted(lignes, key=cle)
    val = []
    for ligne in rangees:
        d = dict(zip(NOMS, ligne))
        if ligne[3] is None:
            val += [None] * 5 + [d["defects_created"], d["defects_without_affects"], d["resolved_week"], d["resolved_week_defects"]]
        else:
            val += [d["found"]] + [None] * 8
    return rangees, ([r[0] for r in rangees], [r[2] for r in rangees], [r[3] for r in rangees], val, [0] * len(rangees))


def x23_lignes():
    lignes = []
    for equipe in ("A", PRODUIT):
        lignes += [(S1, True, equipe, None, None, 20, 10, 20, 10), (S1, True, equipe, 1, 10, None, None, None, None),
                   (S1, True, equipe, 2, 6, None, None, None, None), (S2, True, equipe, None, None, 24, 10, 20, 10),
                   (S2, True, equipe, 3, 14, None, None, None, None), (S2, True, equipe, 4, 5, None, None, None, None)]
    return lignes


class AvecBase(unittest.TestCase):
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie
    version = photo.AvecBase.version
    semaine = photo.AvecBase.semaine
    ligne_version = photo.AvecBase.ligne_version
    ligne_libre = photo.AvecBase.ligne_libre
    adopter = photo.AvecBase.adopter
    lire_photo = photo.AvecBase.lire

    def appeler(self, c, requete, parametres=()):
        """Exécute sous le rôle des vues ; renvoie (lignes, erreur) : une exception de la fonction est rendue, jamais levée, et ne laisse aucune ligne."""
        c.commit()
        c.execute("SET ROLE pmzilla_flow_views")
        try:
            return c.execute(requete, parametres).fetchall(), None
        except Exception as erreur:                       # noqa: BLE001 : on rend l'erreur pour la comparer
            c.rollback()
            return [], erreur
        finally:
            c.execute("RESET ROLE")


class MarqueurDeux(AvecBase):
    def test_marqueur_deux_pour_le_role_d_import_seulement(self):
        c = self.conn()
        c.execute("SET ROLE pmzilla_flow")
        self.assertEqual(c.execute("SELECT flow.masking_version()").fetchone()[0], 2)
        c.execute("RESET ROLE")
        c.commit()
        for role in ("pmzilla_flow_views", "pmzilla_flow_ro", "pmzilla_quality_views", "pmzilla_cases", "pmzilla_knowledge_ro"):
            self.assertFalse(self.essaie(c, role, "SELECT flow.masking_version()"), role)

    def test_execute_des_deux_fonctions_au_seul_role_des_vues(self):
        c = self.conn()
        appels = ("SELECT * FROM flow.propager_bornes(ARRAY[0]::bigint[], ARRAY[5]::bigint[], ARRAY[]::smallint[], ARRAY[]::bigint[], "
                  "ARRAY[]::integer[], ARRAY[]::integer[], ARRAY[]::smallint[], 100, 10)",
                  "SELECT * FROM flow.photo_masque(ARRAY[]::date[], ARRAY[]::text[], ARRAY[]::integer[], ARRAY[]::bigint[], ARRAY[]::bigint[])")
        for appel in appels:
            self.assertTrue(self.essaie(c, "pmzilla_flow_views", appel), appel)
            for role in ("pmzilla_flow", "pmzilla_flow_ro", "pmzilla_quality_views", "pmzilla_cases", "pmzilla_knowledge_ro"):
                self.assertFalse(self.essaie(c, role, appel), f"{role} {appel}")


class LimitesEnSql(AvecBase):
    RELATIONS = ("ARRAY[0,0,7]::bigint[], ARRAY[NULL,NULL,7]::bigint[], ARRAY[1,1]::smallint[], ARRAY[0,0]::bigint[], "
                 "ARRAY[1,1,2,2]::integer[], ARRAY[1,2,2,3]::integer[], ARRAY[1,-1,1,-1]::smallint[]")

    def test_propager_bornes_resserre_trois_variables_egales(self):
        c = self.conn()
        lignes, erreur = self.appeler(c, f"SELECT rang, borne_lo, borne_hi, vide, limite_atteinte FROM flow.propager_bornes({self.RELATIONS}, 1000, 10) ORDER BY rang")
        self.assertIsNone(erreur)
        self.assertEqual(lignes, [(1, 7, 7, False, False), (2, 7, 7, False, False), (3, 7, 7, False, False)])

    def test_limite_de_balayages_atteinte_drapeau_sans_exception(self):
        """La fonction reste PARALLEL SAFE (aucun bloc d'exception) : elle rend le drapeau « limite atteinte », l'appelante décide."""
        c = self.conn()
        lignes, erreur = self.appeler(c, f"SELECT limite_atteinte FROM flow.propager_bornes({self.RELATIONS}, 1000, 1)")
        self.assertIsNone(erreur)
        self.assertEqual(lignes, [(True,), (True,), (True,)])

    def test_borne_finie_au_dessus_de_m_drapeau_sans_exception(self):
        c = self.conn()
        lignes, erreur = self.appeler(c, f"SELECT limite_atteinte FROM flow.propager_bornes({self.RELATIONS}, 3, 10)")
        self.assertIsNone(erreur)
        self.assertTrue(all(drapeau for (drapeau,) in lignes) and lignes)

    def test_un_intervalle_vide_est_rendu_avec_son_drapeau(self):
        c = self.conn()
        lignes, erreur = self.appeler(c, "SELECT rang, vide FROM flow.propager_bornes(ARRAY[5,0]::bigint[], ARRAY[5,3]::bigint[], ARRAY[1]::smallint[], "
                                         "ARRAY[0]::bigint[], ARRAY[1,1]::integer[], ARRAY[1,2]::integer[], ARRAY[1,-1]::smallint[], 1000, 10) ORDER BY rang")
        self.assertIsNone(erreur)
        self.assertTrue(all(vide for _, vide in lignes))

    def test_limite_de_la_boucle_externe_atteinte_exception_et_aucune_ligne(self):
        c = self.conn()
        _, tab = tableaux(x23_lignes())
        for limite in (1, 2):
            lignes, erreur = self.appeler(c, APPEL, (*tab, limite, None))
            self.assertIsNotNone(erreur, limite)
            self.assertEqual(lignes, [], limite)
        lignes, erreur = self.appeler(c, APPEL, (*tab, 3, None))                     # trois passes suffisent à X23
        self.assertIsNone(erreur)
        self.assertEqual(len(lignes), 12)

    def test_limite_de_balayages_de_la_photo_atteinte_exception_et_aucune_ligne(self):
        c = self.conn()
        _, tab = tableaux(x23_lignes())
        lignes, erreur = self.appeler(c, APPEL, (*tab, None, 1))
        self.assertIsNotNone(erreur)
        self.assertEqual(lignes, [])

    def test_une_photo_incoherente_avec_la_lecture_m_libre_n_est_jamais_publiee(self):
        c = self.conn()
        lignes = [(S1, True, "A", None, None, 40, 5, 20, 10), (S1, True, "A", 1, 45, None, None, None, None)]     # trouvé 45 pour 35 défauts
        _, tab = tableaux(lignes)
        resultat, erreur = self.appeler(c, APPEL, (*tab, None, None))
        self.assertIsNotNone(erreur)
        self.assertEqual(resultat, [])


class X23ContreLaVue(AvecBase):
    """Cas partagé X23 contre v_version_quality_photo : le créé de la semaine deux (24) est masqué, avec le trouvé de 5 et sans affects, pour l'équipe et
    le produit (rouge avant 6.5 : la vue publiait ces trois cellules)."""

    def test_x23_equipe_et_produit(self):
        c = self.conn()
        s1, s2 = photo.LUNDI, photo.LUNDI + dt.timedelta(days=35)
        self.semaine(c, s1, "reconstructed")
        self.semaine(c, s2, "reconstructed")
        for lundi, sortie, crees, trouves in ((s1, photo.SORTIE, 20, (10, 6)), (s2, dt.date(2027, 1, 20), 24, (14, 5))):
            for j, found in enumerate(trouves):
                self.ligne_version(c, lundi, "A", self.version(c, nom=f"v-{lundi}-{j}", sortie=sortie), found=found)
            self.ligne_libre(c, lundi, "A", creees=crees, sans_affects=10, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)
        lignes = self.lire_photo(c)
        for equipe in ("A", PRODUIT):
            libres = sorted([l for l in lignes if l["team"] == equipe and l["version_no"] is None], key=lambda l: l["week_start"])
            self.assertEqual((libres[0]["defects_created"], libres[0]["defects_without_affects"]), (20, 10), equipe)
            self.assertIsNone(libres[1]["defects_created"], equipe)
            self.assertIsNone(libres[1]["defects_without_affects"], equipe)
            self.assertIsNone(libres[1]["without_affects_share_percent"], equipe)
            trouves = sorted([(l["week_start"], l["found"]) for l in lignes if l["team"] == equipe and l["version_no"] is not None],
                             key=lambda x: (x[0], x[1] is None, x[1]))
            self.assertEqual([f for _, f in trouves if f is not None], [6, 10, 14])
            self.assertEqual(sum(1 for _, f in trouves if f is None), 1, equipe)             # le trouvé de 5 de la semaine deux


def table_tiree(graine, semaine_sans_version_a=None):
    """Deux équipes, trois semaines, deux versions par semaine : comptes cohérents (défauts distincts entre le plus grand trouvé et leur somme).
    Variante (revue 16.1, C4 ; 20.4) : `semaine_sans_version_a` (0, 1 ou 2) retire les lignes de version de l'équipe A pour cette semaine ; A garde sa ligne
    sans version, le produit reste la somme (ses trouvés ne viennent plus que de B) : D_t et sa relation entrent dans la parité tirée au hasard."""
    hasard = random.Random(graine)
    lignes = []
    somme = {}
    for equipe in ("A", "B"):
        for semaine_k, semaine in enumerate((S1, S2, S3)):
            f1, f2 = hasard.choice([1, 2, 3, 5, 6, 8, 12]), hasard.choice([1, 2, 3, 5, 6, 8, 12])
            distincts = hasard.randint(max(f1, f2), f1 + f2)
            sans = hasard.choice([0, 3, 5, 9, 15])
            lignes.append((semaine, True, equipe, None, None, sans + distincts, sans, 20, 10))
            if equipe == "A" and semaine_k == semaine_sans_version_a:
                continue                                                                  # les tirages restent consommés : les autres lignes ne bougent pas
            lignes += [(semaine, True, equipe, 2 * semaine_k + 1, f1, None, None, None, None), (semaine, True, equipe, 2 * semaine_k + 2, f2, None, None, None, None)]
    for semaine_k, semaine in enumerate((S1, S2, S3)):
        equipes = [l for l in lignes if l[0] == semaine]
        crees = sum(l[5] for l in equipes if l[3] is None)
        sans = sum(l[6] for l in equipes if l[3] is None)
        lignes.append((semaine, True, PRODUIT, None, None, crees, sans, 40, 20))
        for numero in (2 * semaine_k + 1, 2 * semaine_k + 2):
            lignes.append((semaine, True, PRODUIT, numero, sum(l[4] for l in equipes if l[3] == numero), None, None, None, None))
    return lignes


class PariteMultiSemaines(AvecBase):
    """Tâche 6.6 : photos de plusieurs semaines avec produit, la fonction SQL au plancher et masquer_vue donnent les mêmes cellules (les autres unités avec le
    groupe 7). Les tables sont tirées sans terme non retenu : l'écart (d) de D4 ne joue pas."""

    def parite(self, graine, semaine_sans_version_a=None):
        c = self.conn()
        lignes = table_tiree(graine, semaine_sans_version_a)
        rangees, tab = tableaux(lignes)
        try:
            python = fv.masquer_vue(fv.VUE_PHOTO, NOMS, rangees, fv.PLANCHER)
            python_erreur = None
        except fv.MasquageInstable as erreur:
            python, python_erreur = None, erreur
        sql, sql_erreur = self.appeler(c, APPEL, (*tab, None, None))
        if python_erreur is not None:
            self.assertIsNotNone(sql_erreur, f"graine {graine} : Python lève {python_erreur}, le SQL doit lever aussi")
            return
        self.assertIsNone(sql_erreur, f"graine {graine} : {sql_erreur}")
        par_rang = {ligne[0]: ligne for ligne in sql}
        for i, (ligne, cellules) in enumerate(zip(rangees, python), start=1):
            applicables = ("found",) if ligne[3] is not None else ("defects_created", "defects_without_affects", "resolved_week", "resolved_week_defects")
            for col in applicables:
                self.assertEqual(par_rang[i][1 + self.indice_sql(col)], "masked" not in cellules[col], f"graine {graine}, ligne {ligne[:4]}, colonne {col}")

    @staticmethod
    def indice_sql(col):
        """Position de la colonne dans (rang, v_found, v_found_open, v_corrected_at_week, v_corrected_now, v_reopened, v_dc, v_dwa, v_rw, v_rwd) moins 1."""
        return {"found": 0, "defects_created": 5, "defects_without_affects": 6, "resolved_week": 7, "resolved_week_defects": 8}[col]

    def test_x23_la_fonction_sql_donne_les_cellules_de_masquer_vue(self):
        rangees, tab = tableaux(x23_lignes())
        python = fv.masquer_vue(fv.VUE_PHOTO, NOMS, rangees, fv.PLANCHER)
        c = self.conn()
        sql, erreur = self.appeler(c, APPEL, (*tab, None, None))
        self.assertIsNone(erreur)
        par_rang = {ligne[0]: ligne for ligne in sql}
        for i, (ligne, cellules) in enumerate(zip(rangees, python), start=1):
            for col in (("found",) if ligne[3] is not None else ("defects_created", "defects_without_affects")):
                self.assertEqual(par_rang[i][1 + self.indice_sql(col)], "masked" not in cellules[col], f"{ligne[:4]} {col}")

    def test_cas_3_lecture_u_nul_et_m_nul_la_fonction_sql_donne_les_cellules_de_masquer_vue(self):
        """M7 (a) de la fiche R-20261104-6 : le créé de la semaine deux (43, masqué par la chaîne) n'est épinglé que par la lecture « U = 0 et m = 0 » ;
        SQL et Python masquent aussi sans affects de la semaine deux."""
        lignes = [(S1, True, "A", None, None, 40, 5, 20, 10), (S1, True, "A", 1, 30, None, None, None, None), (S1, True, "A", 2, 20, None, None, None, None),
                  (S2, True, "A", None, None, 43, 5, 20, 10), (S2, True, "A", 3, 20, None, None, None, None), (S2, True, "A", 4, 18, None, None, None, None)]
        rangees, tab = tableaux(lignes)
        python = fv.masquer_vue(fv.VUE_PHOTO, NOMS, rangees, fv.PLANCHER)
        c = self.conn()
        sql, erreur = self.appeler(c, APPEL, (*tab, None, None))
        self.assertIsNone(erreur)
        par_rang = {ligne[0]: ligne for ligne in sql}
        for i, (ligne, cellules) in enumerate(zip(rangees, python), start=1):
            for col in (("found",) if ligne[3] is not None else ("defects_created", "defects_without_affects")):
                self.assertEqual(par_rang[i][1 + self.indice_sql(col)], "masked" not in cellules[col], f"{ligne[:4]} {col}")
        self.assertIn("masked", python[3]["defects_without_affects"])

    def test_parite_graine_7(self):
        self.parite(7)

    def test_parite_graine_19(self):
        self.parite(19)

    def test_parite_graine_31(self):
        self.parite(31)

    def test_parite_graine_44(self):
        self.parite(44)

    def test_parite_graine_58(self):
        self.parite(58)

    def test_parite_une_equipe_sans_ligne_de_version_graine_7_semaine_2(self):
        """Revue 16.1, C4 : l'équipe A n'a aucune ligne de version la semaine tirée (D_t et sa relation à trois termes entrent dans la parité)."""
        self.parite(7, 1)

    def test_parite_une_equipe_sans_ligne_de_version_graine_31_semaine_3(self):
        self.parite(31, 2)


if __name__ == "__main__":
    unittest.main()
