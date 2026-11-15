"""Migration du masquage des sommes et contre-exemples contre les vues (change masking-sums, R-144 ; tâches 1.3, 1.4 et 2.1 ; conception D2 à D5, D8, D9, D12).

    bash tools/dbtest.sh db

La lecture statique du fichier de migration (tâche 2.1) est dans tests/flow_views/test_masquage_migration_statique.py (sans base, lancée par
tests/run_all.sh flow_views). Les classes d'ici utilisent la base jetable de test_flow_schema.py et sont sautées sans elle : contre-exemples X1 à X12 contre les vues (tâche 1.3, rouges avant la migration pour X1 à X5, X8, X10 à X12 ; X6a, X9 verts
déjà), marqueur flow.masking_version() et colonnes inchangées, parité de masquer_vue au plancher avec la vue de la part sur des tables tirées avec des
graines fixes (tâche 1.4, rouge tant que masquer_vue n'existe pas). Données inventées : équipes A à G, identifiants id1 et id2, noms de version synthétiques.
"""
import datetime as dt
import random
import unittest

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402
import test_flow_fix_version_share as part   # noqa: E402
import test_flow_version_photo_views as photo   # noqa: E402
import flow_views as fv         # noqa: E402

PART = "flow.v_team_fix_version_share"
COLONNES_PART = ["team", "quarter_start", "items", "with_fix_version", "share_percent", "with_fix_version_min"]
COLONNES_RETARD = photo.COLONNES_RETARD
COLONNES_VUES = {"v_team_fix_version_share": COLONNES_PART, "v_team_fix_version_lag": COLONNES_RETARD,
                 "v_version_quality_photo": photo.COLONNES_PHOTO, "v_teams": ["team", "team_type", "tickets"],
                 "v_team_jira_ids": ["team", "jira_team_id", "tickets"]}


def normaliser(ligne):
    return tuple(None if v is None else float(v) for v in ligne)


class AvecBase(unittest.TestCase):
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def creer_equipes(self, c, noms):
        c.execute("SET ROLE pmzilla_flow")
        for nom in noms:
            c.execute("INSERT INTO flow.teams (name) VALUES (%s)", (nom,))
        c.execute("RESET ROLE")

    def lire(self, c, requete):
        c.commit()
        c.execute("SET ROLE pmzilla_flow_views")
        try:
            return c.execute(requete).fetchall()
        finally:
            c.execute("RESET ROLE")


class MarqueurEtColonnes(AvecBase):
    def test_colonnes_inchangees_des_cinq_vues(self):
        c = self.conn()
        for vue, attendues in COLONNES_VUES.items():
            colonnes = [r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'flow' "
                                                "AND table_name = %s ORDER BY ordinal_position", (vue,))]
            self.assertEqual(colonnes, attendues, vue)

    def test_marqueur_version_deux_pour_le_role_d_import_seulement(self):
        """La migration de la propagation des bornes (groupe 6, D15) relève le marqueur à 2 ; celle des sommes le posait à 1 (D9)."""
        c = self.conn()
        c.execute("SET ROLE pmzilla_flow")
        self.assertEqual(c.execute("SELECT flow.masking_version()").fetchone()[0], 2)
        c.execute("RESET ROLE")
        c.commit()
        for role in ("pmzilla_flow_views", "pmzilla_flow_ro", "pmzilla_quality_views", "pmzilla_cases", "pmzilla_knowledge_ro"):
            self.assertFalse(self.essaie(c, role, "SELECT flow.masking_version()"), role)

    def test_execute_de_la_fonction_du_point_fixe_au_seul_role_des_vues(self):
        """flow.photo_serie et flow.retard_d2 : EXECUTE au seul rôle des vues (PostgreSQL le vérifie pour le lecteur de la vue, pas pour son
        propriétaire) ; la lecture de la vue photo sous ce rôle est dans
        ContreExemplesPhoto.test_photo_lue_sous_le_role_des_vues_qui_appelle_la_fonction."""
        appels = ("SELECT * FROM flow.photo_serie(ARRAY[20]::bigint[], ARRAY[8]::bigint[], ARRAY[true], ARRAY[true], "
                  "ARRAY[0]::bigint[], ARRAY[0]::bigint[], ARRAY[12]::bigint[])",
                  "SELECT * FROM flow.retard_d2(10, 10, 10, 10, 13, true, true, true, true, true, true)")
        c = self.conn()
        for appel in appels:
            self.assertTrue(self.essaie(c, "pmzilla_flow_views", appel), appel)
            for role in ("pmzilla_flow", "pmzilla_flow_ro", "pmzilla_quality_views", "pmzilla_cases", "pmzilla_knowledge_ro"):
                self.assertFalse(self.essaie(c, role, appel), f"{role} {appel}")

    def test_droits_des_vues_recreees(self):
        c = self.conn()
        for vue in COLONNES_VUES:
            self.assertTrue(self.essaie(c, "pmzilla_flow_views", f"SELECT * FROM flow.{vue}"), vue)
            for role in ("pmzilla_quality_views", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_cases"):
                self.assertFalse(self.essaie(c, role, f"SELECT * FROM flow.{vue}"), f"{role} {vue}")


class ContreExemplesPart(AvecBase):
    """X3, X4, X5 et X10 contre v_team_fix_version_share (cas de contrats/cas-masquage.json, mêmes chiffres)."""
    ticket = part.AvecBase.ticket
    remplir = part.AvecBase.remplir
    debut_trimestre = part.AvecBase.debut_trimestre

    def part_par_equipe(self, c):
        lignes = self.lire(c, f"SELECT team, items, with_fix_version, share_percent FROM {PART}")
        return {l[0]: normaliser(l[1:]) for l in lignes}

    def test_x3_produit_masque_quand_deux_cellules_de_quatre_sont_masquees(self):
        c = self.conn()
        self.creer_equipes(c, "ABCD")
        for equipe, nom, total, avec in ((1, "A", 4, 2), (2, "B", 4, 2), (3, "C", 20, 10), (4, "D", 20, 18)):
            self.remplir(c, equipe, nom, total, avec)
        lignes = self.part_par_equipe(c)
        self.assertEqual((lignes["A"], lignes["B"]), ((None, None, None), (None, None, None)))
        self.assertEqual((lignes["C"], lignes["D"]), ((20.0, 10.0, 50.0), (20.0, None, None)))
        self.assertEqual(lignes["(produit)"], (None, None, None))                  # 48 = 8 + 40 : la somme 8 = 4k se lirait

    def test_x4_produit_masque_quand_cinq_equipes_d_un_item_sont_masquees(self):
        c = self.conn()
        self.creer_equipes(c, "ABCDEFG")
        for equipe, nom in enumerate("ABCDE", start=1):
            self.remplir(c, equipe, nom, 1, 1 if equipe <= 2 else 0)
        self.remplir(c, 6, "F", 20, 10)
        self.remplir(c, 7, "G", 20, 18)
        lignes = self.part_par_equipe(c)
        for nom in "ABCDE":
            self.assertEqual(lignes[nom], (None, None, None), nom)
        self.assertEqual((lignes["F"], lignes["G"]), ((20.0, 10.0, 50.0), (20.0, None, None)))
        self.assertEqual(lignes["(produit)"], (None, None, None))                  # la somme masquée 5 = somme des bornes basses (cinq équipes d'un item)

    def test_x5_detail_du_produit_masque_les_items_restent(self):
        c = self.conn()
        self.creer_equipes(c, "ABC")
        self.remplir(c, 1, "A", 20, 20)
        self.remplir(c, 2, "B", 20, 4)
        self.remplir(c, 3, "C", 20, 10)
        lignes = self.part_par_equipe(c)
        self.assertEqual((lignes["A"], lignes["B"], lignes["C"]), ((20.0, None, None), (20.0, None, None), (20.0, 10.0, 50.0)))
        self.assertEqual(lignes["(produit)"], (60.0, None, None))                  # 34 avec fix version : A + B = 24, A <= 20 et B <= 4 se liraient

    def test_x10_cinq_items_aucun_avec_fix_version_les_items_sont_masques(self):
        c = self.conn()
        self.creer_equipes(c, "AB")
        self.remplir(c, 1, "A", 5, 0)
        self.remplir(c, 2, "B", 20, 10)
        lignes = self.part_par_equipe(c)
        self.assertEqual(lignes["A"], (None, None, None))                           # la borne absente donnerait « avec = 0 »
        self.assertEqual(lignes["B"], (20.0, 10.0, 50.0))
        self.assertEqual(lignes["(produit)"], (None, None, None))

    def test_la_borne_basse_est_toujours_publiee_pour_le_cas_courant(self):
        c = self.conn()
        self.creer_equipes(c, "ABC")
        self.remplir(c, 1, "A", 20, 18)
        self.remplir(c, 2, "B", 20, 10)
        self.remplir(c, 3, "C", 20, 10)
        lignes = self.lire(c, f"SELECT team, with_fix_version_min FROM {PART}")
        self.assertEqual({l[0]: l[1] for l in lignes}["A"], 16)


class ContreExemplesRetard(AvecBase):
    """X6a (au plancher, déjà corrigé) et X9 (régression) contre v_team_fix_version_lag, avec les gabarits des tests de la vue du retard."""
    ticket = photo.AvecBase.ticket
    remplir = photo.AvecBase.remplir
    paniers = staticmethod(photo.AvecBase.paniers)
    lire_photo = photo.AvecBase.lire

    def retard(self, c):
        return {l["team"]: l for l in self.lire_photo(c, photo.RETARD)}

    def test_x6a_vingt_items_dont_dix_huit_avec_version_ligne_cachee_par_la_part(self):
        c = self.conn()
        self.creer_equipes(c, "A")
        self.remplir(c, 1, "A", photo.PLEINE[:18], sans_fix=2)
        part_a = [l for l in self.lire_photo(c, PART) if l["team"] == "A"][0]
        self.assertEqual((part_a["items"], part_a["with_fix_version"], part_a["with_fix_version_min"]), (20, None, 16))
        for ligne in self.lire_photo(c, photo.RETARD):
            for colonne in COLONNES_RETARD[2:]:
                self.assertIsNone(ligne[colonne], f"{ligne['team']} {colonne}")

    def test_x9_produit_des_colonnes_un_a_quatre_masque_la_cinq_reste(self):
        c = self.conn()
        self.creer_equipes(c, "ABCD")
        for equipe, (nom, valeurs) in enumerate((("A", (10, 2, 20, 20, 20)), ("B", (10, 1, 20, 20, 20)),
                                                 ("C", (20, 20, 2, 10, 20)), ("D", (20, 20, 1, 10, 20))), start=1):
            self.remplir(c, equipe, nom, self.paniers(*valeurs))
        produit = self.retard(c)["(produit)"]
        for colonne in COLONNES_RETARD[3:7]:
            self.assertIsNone(produit[colonne], colonne)
        self.assertEqual((produit["items"], produit["no_history"]), (286, 80))


class ContreExemplesEquipes(AvecBase):
    """X1, X2, X2b et X2c contre v_teams et v_team_jira_ids."""
    NOM = "N"

    def passage(self, c):
        c.execute("SET ROLE pmzilla_flow")
        run = c.execute("INSERT INTO flow.raw_runs (kind, queries_searched, all_queries) VALUES ('export', 2, true) RETURNING id").fetchone()[0]
        c.execute("RESET ROLE")
        return run

    def ticket(self, c, cle, equipe, statut="Open", categorie="To Do"):
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, updated_at, team_id) "
                  "VALUES (%s, 'PROJ', 'Story', %s, %s, now(), now(), %s)", (cle, statut, categorie, equipe))
        c.execute("INSERT INTO flow.issue_teams (issue_key, team_id, position) VALUES (%s, %s, 1)", (cle, equipe))
        c.execute("RESET ROLE")

    def instantane(self, c, run, cle, identifiant):
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.raw_issue_snapshots (issue_key, run_id, updated_at, project, type, status, created_at, content_hash, teams) "
                  "VALUES (%s, %s, now(), 'PROJ', 'Story', 'Open', now(), 'h', %s::jsonb)",
                  (cle, run, '[{"name": "%s", "jira_team_id": %s}]' % (self.NOM, "null" if identifiant is None else f'"{identifiant}"')))
        c.execute("RESET ROLE")

    def tickets_de_la_vue(self, c, vue="v_teams"):
        """v_teams : {équipe: tickets} ; v_team_jira_ids : {(équipe, identifiant): tickets}."""
        if vue == "v_team_jira_ids":
            return {(l[0], l[1]): l[2] for l in self.lire(c, "SELECT team, jira_team_id, tickets FROM flow.v_team_jira_ids")}
        return {l[0]: l[1] for l in self.lire(c, "SELECT team, tickets FROM flow.v_teams")}

    def nom_avec_identifiants(self, c, repartition):
        """Équipe N (id 1) : un ticket par entrée de `repartition` (identifiant Jira, nombre) ; None : aucun identifiant sur ces tickets."""
        self.creer_equipes(c, [self.NOM])
        run = self.passage(c)
        numero = 0
        for identifiant, nombre in repartition:
            for _ in range(nombre):
                cle = f"PROJ-{numero}"
                numero += 1
                self.ticket(c, cle, 1)
                self.instantane(c, run, cle, identifiant)
        c.commit()

    def test_x1_ecart_d_un_avec_une_cellule_de_statut_masquee(self):
        c = self.conn()
        self.creer_equipes(c, ["A"])
        for i in range(10):
            self.ticket(c, f"PROJ-{i}", 1, "Closed", "Done")
        for i in range(10, 22):
            self.ticket(c, f"PROJ-{i}", 1, "Resolved", "Done")
        self.ticket(c, "PROJ-22", 1, "Blocked", "In Progress")                      # 23 tickets : 10 + 12 visibles, une cellule masquée de 1
        self.assertIsNone(self.tickets_de_la_vue(c)["A"])                          # sans la règle, 23 - 22 = 1 donnerait la cellule masquée

    def test_x2_deux_identifiants_de_quatre_tickets_le_nom_est_masque(self):
        c = self.conn()
        self.nom_avec_identifiants(c, (("id1", 4), ("id2", 4)))
        self.assertIsNone(self.tickets_de_la_vue(c)[self.NOM])                      # 8 = 2 x 4 : chaque identifiant se lirait 4
        self.assertEqual(set(self.tickets_de_la_vue(c, "v_team_jira_ids").values()), {None})

    def test_x2b_un_identifiant_de_vingt_huit_pour_trente_le_nom_est_masque(self):
        c = self.conn()
        self.nom_avec_identifiants(c, (("id1", 28), (None, 2)))
        self.assertIsNone(self.tickets_de_la_vue(c)[self.NOM])                      # les deux tickets sans identifiant se liraient par différence
        # 5.11 (option A élargie) : le nom est masqué, donc tous ses identifiants visibles le sont aussi (ici le seul, 28)
        self.assertIsNone(self.tickets_de_la_vue(c, "v_team_jira_ids")[(self.NOM, "id1")])

    def test_m1_nom_masque_par_complement_son_identifiant_visible_est_masque(self):
        """Cas principal de m1 : le compte du nom est masqué par les comptes de statut (X1), son seul identifiant, visible, l'est aussi."""
        c = self.conn()
        self.creer_equipes(c, [self.NOM])
        run = self.passage(c)
        for i in range(23):
            statut, categorie = ("Closed", "Done") if i < 10 else ("Resolved", "Done") if i < 22 else ("Blocked", "In Progress")
            self.ticket(c, f"PROJ-{i}", 1, statut, categorie)
            self.instantane(c, run, f"PROJ-{i}", "id1")
        c.commit()
        self.assertIsNone(self.tickets_de_la_vue(c)[self.NOM])                      # 23 - (10 + 12) = 1 : la cellule de statut masquée se lirait
        self.assertIsNone(self.tickets_de_la_vue(c, "v_team_jira_ids")[(self.NOM, "id1")])

    def test_m2a_identifiants_4_4_et_6_pour_un_nom_de_14_borne_haute_du_plus_petit_visible(self):
        c = self.conn()
        self.nom_avec_identifiants(c, (("id1", 4), ("id2", 4), ("id3", 6)))
        self.assertEqual(self.tickets_de_la_vue(c)[self.NOM], 14)                   # la somme masquée 8 n'est pas 2 x max(4, 6) : rien à masquer
        identifiants = self.tickets_de_la_vue(c, "v_team_jira_ids")
        self.assertEqual((identifiants[(self.NOM, "id1")], identifiants[(self.NOM, "id2")], identifiants[(self.NOM, "id3")]), (None, None, 6))

    def test_m2a_identifiants_3_et_5_pour_un_nom_de_8_le_complement_masque_le_nom(self):
        c = self.conn()
        self.nom_avec_identifiants(c, (("id1", 3), ("id2", 5)))
        self.assertIsNone(self.tickets_de_la_vue(c)[self.NOM])                      # 3 masqué se lit par 8 - 5 : le 5 est masqué, puis 8 = 2 x 4
        self.assertEqual(set(self.tickets_de_la_vue(c, "v_team_jira_ids").values()), {None})

    def test_x2c_comptes_egaux_le_nom_est_montre(self):
        c = self.conn()
        self.nom_avec_identifiants(c, (("id1", 30),))
        self.assertEqual(self.tickets_de_la_vue(c)[self.NOM], 30)                   # une différence nulle n'est pas protégée
        self.assertEqual(self.tickets_de_la_vue(c, "v_team_jira_ids")[(self.NOM, "id1")], 30)

    def test_deux_identifiants_visibles_ecart_de_deux_le_nom_est_masque(self):
        c = self.conn()
        self.creer_equipes(c, [self.NOM])
        run = self.passage(c)
        for i in range(30):                                                         # 20 portent id1, 12 portent id2, deux portent les deux : 30 tickets
            cle = f"PROJ-{i}"
            self.ticket(c, cle, 1)
            c.execute("SET ROLE pmzilla_flow")
            equipes = []
            if i < 20:
                equipes.append('{"name": "N", "jira_team_id": "id1"}')
            if i >= 18:
                equipes.append('{"name": "N", "jira_team_id": "id2"}')
            c.execute("INSERT INTO flow.raw_issue_snapshots (issue_key, run_id, updated_at, project, type, status, created_at, content_hash, teams) "
                      "VALUES (%s, %s, now(), 'PROJ', 'Story', 'Open', now(), 'h', %s::jsonb)", (cle, run, "[" + ", ".join(equipes) + "]"))
            c.execute("RESET ROLE")
        c.commit()
        self.assertIsNone(self.tickets_de_la_vue(c)[self.NOM])                      # 20 + 12 - 30 = 2
        identifiants = self.tickets_de_la_vue(c, "v_team_jira_ids")
        self.assertEqual((identifiants[(self.NOM, "id1")], identifiants[(self.NOM, "id2")]), (None, None))      # 5.11 : le nom est masqué, tous ses identifiants visibles (20 et 12) le sont


class ContreExemplesPhoto(AvecBase):
    """X8, X11 et X12 contre v_version_quality_photo (N adopté à 6 semaines)."""
    version = photo.AvecBase.version
    semaine = photo.AvecBase.semaine
    ligne_version = photo.AvecBase.ligne_version
    ligne_libre = photo.AvecBase.ligne_libre
    adopter = photo.AvecBase.adopter
    lire_photo = photo.AvecBase.lire

    def libres(self, c, equipe):
        return sorted([l for l in self.lire_photo(c) if l["team"] == equipe and l["version_no"] is None], key=lambda l: l["week_start"])

    def test_x8_trois_defauts_crees_entre_deux_semaines_retenues(self):
        c = self.conn()
        semaine_1, semaine_2 = photo.LUNDI, photo.LUNDI + dt.timedelta(days=35)
        no1 = self.version(c, nom="v-un", sortie=photo.SORTIE)                      # semaine retenue : celle du 2026-11-02
        no2 = self.version(c, nom="v-deux", sortie=dt.date(2027, 1, 20))            # le lundi de sa semaine est le 2027-01-18, six semaines avant : le 2026-12-07
        self.semaine(c, semaine_1, "reconstructed")
        self.semaine(c, semaine_2, "reconstructed")
        self.ligne_version(c, semaine_1, "A", no1, found=25)
        self.ligne_libre(c, semaine_1, "A", creees=40, sans_affects=15, resolus=20, resolus_defauts=10)
        self.ligne_version(c, semaine_2, "A", no2, found=28)
        self.ligne_libre(c, semaine_2, "A", creees=43, sans_affects=15, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)
        premiere, seconde = self.libres(c, "A")
        # attente actuelle (cas partagé X8, calculée par masquer_vue) : l'excès est nul (25 - 25), D5-e masque sans affects et le point fixe les créés
        self.assertIsNone(premiere["defects_created"])
        self.assertIsNone(seconde["defects_created"])

    def test_x8c_trois_defauts_crees_entre_deux_semaines_retenues_chaine_isolee(self):
        """Cas partagé X8c (données cohérentes, revue 4) : semaine 1 créés 40, sans affects 15, trouvés 20 et 10 (distincts 25, excès 5) ; semaine 2
        créés 43, sans affects 15, trouvés 20 et 15 (distincts 28, excès 7) ; D5-e ne masque rien, la chaîne des semaines masque seule la seconde.
        Le créé masqué reste ouvert : la chaîne permet 36 à 44 sauf 40, la relation 35 à 50, l'intersection compte huit valeurs."""
        c = self.conn()
        semaine_1, semaine_2 = photo.LUNDI, photo.LUNDI + dt.timedelta(days=35)
        self.semaine(c, semaine_1, "reconstructed")
        self.semaine(c, semaine_2, "reconstructed")
        for k, (lundi, sortie, crees, trouves) in enumerate(((semaine_1, photo.SORTIE, 40, (20, 10)), (semaine_2, dt.date(2027, 1, 20), 43, (20, 15)))):
            for j, found in enumerate(trouves):
                self.ligne_version(c, lundi, "A", self.version(c, nom=f"v-{k}-{j}", sortie=sortie), found=found)
            self.ligne_libre(c, lundi, "A", creees=crees, sans_affects=15, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)
        premiere, seconde = self.libres(c, "A")
        self.assertEqual(premiere["defects_created"], 40)
        self.assertIsNone(seconde["defects_created"])                               # 43 - 40 = 3 se lirait

    def test_x21_un_trouve_nul_retenu_est_un_terme_cache_comme_en_python(self):
        """Revue 4, M1 (cas partagé X21) : versions retenues V1 6, V2 4, V3 4, V4 0 (ligne à zéro) ; non retenues V5 2 et V6 2 ; sans affects 10, créés
        28. Trois termes retenus cachés (n_publies = 3), somme 12 = 3 x 4 : sans affects est masqué, comme en Python (k = 3). Sans la ligne à zéro, le
        SQL aurait lu n_publies = 2 et n_caches = 4 et publié."""
        c = self.conn()
        self.semaine(c, photo.LUNDI, "reconstructed")
        for k, found in enumerate((6, 4, 4, 0)):
            self.ligne_version(c, photo.LUNDI, "A", self.version(c, nom=f"v-r{k}", sortie=photo.SORTIE), found=found)
        for k in range(2):
            self.ligne_version(c, photo.LUNDI, "A", self.version(c, nom=f"v-n{k}", sortie=None), found=2)
        self.ligne_libre(c, photo.LUNDI, "A", creees=28, sans_affects=10, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)
        libre = self.libres(c, "A")[0]
        self.assertIsNone(libre["defects_without_affects"])
        self.assertEqual(libre["defects_created"], 28)

    def test_x11_deux_versions_retenues_la_meme_semaine_le_produit_est_masque(self):
        c = self.conn()
        no1 = self.version(c, nom="v-un", sortie=photo.SORTIE)
        no2 = self.version(c, nom="v-deux", sortie=photo.SORTIE)
        self.semaine(c, photo.LUNDI, "reconstructed")
        for equipe, trouves in (("A", (3, 4)), ("B", (3, 4)), ("C", (20, 20))):
            self.ligne_version(c, photo.LUNDI, equipe, no1, found=trouves[0])
            self.ligne_version(c, photo.LUNDI, equipe, no2, found=trouves[1])
        self.ligne_libre(c, photo.LUNDI, "A", creees=30, sans_affects=23, resolus=20, resolus_defauts=6)
        self.ligne_libre(c, photo.LUNDI, "B", creees=30, sans_affects=23, resolus=20, resolus_defauts=6)
        self.ligne_libre(c, photo.LUNDI, "C", creees=60, sans_affects=20, resolus=20, resolus_defauts=6)
        self.adopter(c, 6)
        lignes = [l for l in self.lire_photo(c) if l["team"] is not None and l["version_no"] is not None]
        trouves = {(l["team"], l["version_no"]): l["found"] for l in lignes}
        self.assertEqual({k: v for k, v in trouves.items() if k[0] in ("A", "B")}, {(e, n): None for e in "AB" for n in (no1, no2)})
        self.assertEqual((trouves[("C", no1)], trouves[("C", no2)]), (20, 20))
        self.assertEqual((trouves[("(produit)", no1)], trouves[("(produit)", no2)]), (None, None))      # 6 et 8 : A1 + B1 = 6 pinglerait A1 = B1 = 3

    def test_b1_deux_trouves_de_quatre_masques_creees_30_sans_affects_22_la_somme_des_bornes_hautes(self):
        """Revue R-144, B1 : 30 - 22 = 8 = Σtrouvés - m avec Σtrouvés <= 8 et m >= 0 : chaque trouvé vaudrait 4 ; sans affects est masqué, dans la
        ligne de l'équipe et dans celle du produit (même cas partagé X12b dans contrats/cas-masquage.json)."""
        c = self.conn()
        no1 = self.version(c, nom="v-un", sortie=photo.SORTIE)
        no2 = self.version(c, nom="v-deux", sortie=photo.SORTIE)
        self.semaine(c, photo.LUNDI, "reconstructed")
        self.ligne_version(c, photo.LUNDI, "A", no1, found=4)
        self.ligne_version(c, photo.LUNDI, "A", no2, found=4)
        self.ligne_libre(c, photo.LUNDI, "A", creees=30, sans_affects=22, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)
        for equipe in ("A", "(produit)"):
            libre = [l for l in self.lire_photo(c) if l["team"] == equipe and l["version_no"] is None][0]
            self.assertIsNone(libre["defects_without_affects"], equipe)
            self.assertIsNone(libre["without_affects_share_percent"], equipe)
            self.assertEqual(libre["defects_created"], 30, equipe)

    def test_x12_ligne_publiee_en_entier_l_exces_ne_se_lit_pas(self):
        c = self.conn()
        no1 = self.version(c, nom="v-un", sortie=photo.SORTIE)
        no2 = self.version(c, nom="v-deux", sortie=photo.SORTIE)
        self.semaine(c, photo.LUNDI, "reconstructed")
        self.ligne_version(c, photo.LUNDI, "A", no1, found=20)
        self.ligne_version(c, photo.LUNDI, "A", no2, found=12)
        self.ligne_libre(c, photo.LUNDI, "A", creees=40, sans_affects=10, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)
        libre = self.libres(c, "A")[0]
        self.assertIsNone(libre["defects_created"])                                # point fixe : sans affects masqué seul se lirait par différence
        self.assertIsNone(libre["defects_without_affects"])                        # 32 - (40 - 10) = 2 défauts à deux affects versions
        self.assertIsNone(libre["without_affects_share_percent"])

    def test_photo_lue_sous_le_role_des_vues_qui_appelle_la_fonction(self):
        """Une ligne retenue fait appeler flow.photo_serie par la vue ; la lecture sous pmzilla_flow_views réussit (sans EXECUTE accordé à ce rôle,
        PostgreSQL la refuserait : « permission denied for function photo_serie »)."""
        c = self.conn()
        no = self.version(c, nom="v-un", sortie=photo.SORTIE)
        self.semaine(c, photo.LUNDI, "reconstructed")
        self.ligne_version(c, photo.LUNDI, "A", no, found=12)
        self.ligne_libre(c, photo.LUNDI, "A", creees=20, sans_affects=8, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)
        lignes = self.lire(c, "SELECT team FROM flow.v_version_quality_photo WHERE version_no IS NULL AND team IS NOT NULL")
        self.assertEqual(sorted(l[0] for l in lignes), ["(produit)", "A"])

    def test_x18_exces_nul_sans_affects_puis_les_crees_sont_masques_equipe_et_produit(self):
        """Cas partagé X18 (décision du 2026-10-27) : créés 20, un trouvé visible de 12, sans affects 8. D5-e masque sans affects, D2 repasse
        jusqu'au point fixe : seul caché, il se lirait 20 - 12 = 8 ; les créés sont masqués aussi, sur la ligne d'équipe et sur celle du produit."""
        c = self.conn()
        no = self.version(c, nom="v-un", sortie=photo.SORTIE)
        self.semaine(c, photo.LUNDI, "reconstructed")
        self.ligne_version(c, photo.LUNDI, "A", no, found=12)
        self.ligne_libre(c, photo.LUNDI, "A", creees=20, sans_affects=8, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)
        for equipe in ("A", "(produit)"):
            libre = self.lignes_libres(c)[equipe]
            self.assertEqual((libre["defects_created"], libre["defects_without_affects"], libre["without_affects_share_percent"]), (None, None, None), equipe)

    def test_x20_trois_semaines_d5_d_apres_d2_dix_et_treize_cote_a_cote_sont_masques(self):
        """Cas partagé X20 (décision du 2026-10-27, point fixe complet) : équipe A au plancher ; S1 créés 40, sans affects 10, trouvés 16 et 20 ; S2 45,
        20, un trouvé 25 ; S3 50, 13, trouvés 20 et 23. D2 masque sans affects de S2 (excès 0), 10 et 13 se retrouvent côte à côte (écart 3, D5-d) :
        la boucle masque S3 ; les créés de S2 et S3 le sont avec eux. S1 reste publiée."""
        c = self.conn()
        semaines = [(photo.LUNDI, photo.SORTIE), (photo.LUNDI + dt.timedelta(days=35), dt.date(2027, 1, 20)),
                    (photo.LUNDI + dt.timedelta(days=70), dt.date(2027, 2, 24))]
        donnees = [(40, 10, (16, 20)), (45, 20, (25,)), (50, 13, (20, 23))]
        for rang, ((lundi, sortie), (crees, sans, trouves)) in enumerate(zip(semaines, donnees)):
            self.semaine(c, lundi, "reconstructed")
            for k, found in enumerate(trouves):
                self.ligne_version(c, lundi, "A", self.version(c, nom=f"v-{rang}-{k}", sortie=sortie), found=found)    # toutes retenues
            self.ligne_libre(c, lundi, "A", creees=crees, sans_affects=sans, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)
        libres = self.libres(c, "A")
        self.assertEqual([(l["defects_created"], l["defects_without_affects"]) for l in libres], [(40, 10), (None, None), (None, None)])

    def lignes_libres(self, c):
        return {l["team"]: l for l in self.lire_photo(c) if l["team"] is not None and l["version_no"] is None}

    def test_b1_revue_2_version_non_retenue_un_seul_terme_masque_publie_sans_affects_masque(self):
        """Revue 2, B1 : créés 30, sans affects 20, une version retenue de 4 trouvés (masquée), une version non retenue de 6 : le Python, qui ne voit
        que les lignes publiées, a un seul terme masqué et masque sans affects ; le SQL masque au moins autant (n_publies = 1 puis n_caches = 2)."""
        c = self.conn()
        no1 = self.version(c, nom="v-un", sortie=photo.SORTIE)
        no2 = self.version(c, nom="v-deux", sortie=dt.date(2027, 6, 16))            # non retenue pour la semaine du jeu
        self.semaine(c, photo.LUNDI, "reconstructed")
        self.ligne_version(c, photo.LUNDI, "A", no1, found=4)
        self.ligne_version(c, photo.LUNDI, "A", no2, found=6)
        self.ligne_libre(c, photo.LUNDI, "A", creees=30, sans_affects=20, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)
        for equipe, libre in self.lignes_libres(c).items():
            self.assertIsNone(libre["defects_without_affects"], equipe)
            self.assertEqual(libre["defects_created"], 30, equipe)

    def test_b2_revue_2_trois_trouves_dix_huit_quatre_deux_exces_quatre(self):
        """Revue 2, B2 : créés 30, sans affects 10, trouvés 18 (visible), 4 et 2 (masqués), excès 4 : somme dérivée 2 sous 5, sans affects masqué
        dans la ligne de l'équipe et dans celle du produit (cas partagé X12d)."""
        c = self.conn()
        nos = [self.version(c, nom=f"v-{i}", sortie=photo.SORTIE) for i in range(3)]
        self.semaine(c, photo.LUNDI, "reconstructed")
        for no, trouves in zip(nos, (18, 4, 2)):
            self.ligne_version(c, photo.LUNDI, "A", no, found=trouves)
        self.ligne_libre(c, photo.LUNDI, "A", creees=30, sans_affects=10, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)
        for equipe, libre in self.lignes_libres(c).items():
            self.assertIsNone(libre["defects_without_affects"], equipe)
            self.assertIsNone(libre["without_affects_share_percent"], equipe)

    def remplir_semaines(self, c, equipes, semaines):
        """`semaines` : liste de (lundi, sortie) ; `equipes` : nom -> liste, par semaine, de (créés, sans affects, trouvés) où trouvés est un tuple
        d'un ou deux trouvés (un par version, dans l'ordre) ou None. Deux versions par semaine retenue, comme M3 côté Python (tests/flow_views) :
        un trouvé donné à une seule version laisse l'autre sans ligne ; la ligne du produit de la vue est la somme des équipes (D3). Chaque trouvé
        reste au plus égal aux défauts distincts créés - sans affects (P2, D15)."""
        for rang, (lundi, sortie) in enumerate(semaines):
            nos = [self.version(c, nom=f"v-{rang}-{k}", sortie=sortie) for k in range(2)]
            self.semaine(c, lundi, "reconstructed")
            for equipe, par_semaine in equipes.items():
                crees, sans, trouves = par_semaine[rang]
                for no, found in zip(nos, trouves or ()):
                    self.ligne_version(c, lundi, equipe, no, found=found)
                self.ligne_libre(c, lundi, equipe, creees=crees, sans_affects=sans, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)

    SEMAINES = [(photo.LUNDI, photo.SORTIE), (photo.LUNDI + dt.timedelta(days=35), dt.date(2027, 1, 20)),
                (photo.LUNDI + dt.timedelta(days=70), dt.date(2027, 2, 24))]

    def test_ordre_produit_d3_avant_d5_d_les_creees_du_produit_de_la_derniere_semaine_restent_publiees(self):
        """Tâche 5.12, mêmes données que le test de l'oracle de tests/flow_views (D3 avant D5-d). Équipe A : créés 40, 3, 40 (la semaine 2 est sous
        5, masquée) ; équipe B : 10, 52, 18 ; produit : 50, 55, 58. Deux trouvés par version et par semaine (A : 25 et 20, aucun en semaine 2 ;
        B : 5 et 5, 30 et 27, 12 et 11), chacun au plus égal aux défauts distincts (P2, D15). D3 masque le produit de la semaine 2, la chaîne relie 50 et 58 (écart 8) :
        la semaine 3 reste publiée. Avec D5-d avant D3, 55 puis 58 (écart 3) masquerait la semaine 3. Test de la vue seule : il fixe l'ordre côté
        SQL, que la parité tirée au hasard (PariteLigneLibre) ne contraint pas ; il ne compare pas encore à masquer_vue."""
        c = self.conn()
        self.remplir_semaines(c, {"A": [(40, 5, (25, 20)), (3, 0, None), (40, 5, (25, 20))],
                                  "B": [(10, 5, (5, 5)), (52, 5, (30, 27)), (18, 5, (12, 11))]}, self.SEMAINES)
        produit = self.libres(c, "(produit)")
        self.assertEqual([l["defects_created"] for l in produit], [50, None, 58])

    def test_ordre_produit_d5_d_avant_d2_la_chaine_masque_sans_affects_puis_d2_masque_les_crees(self):
        """Tâche 5.12 (D5-d avant D2). A : créés 30 et 45, sans affects 15 et 25 ; B : 30 et 25, 15 et 8 ; produit : 60 et 70, 30 et 33 (écart 3
        entre les semaines : sans affects masqué par la chaîne). Deux trouvés par semaine (A : 10 et 10, 15 et 10 ; B : 10 et 10, 12 et 10) : D2, qui voit sans affects masqué, masque
        les créés. Avec D2 avant D5-d, les créés de la semaine 2 resteraient publiés."""
        c = self.conn()
        self.remplir_semaines(c, {"A": [(30, 15, (10, 10)), (45, 25, (15, 10))], "B": [(30, 15, (10, 10)), (25, 8, (12, 10))]}, self.SEMAINES[:2])
        produit = self.libres(c, "(produit)")
        self.assertEqual([(l["defects_created"], l["defects_without_affects"]) for l in produit], [(60, 30), (None, None)])

    def test_ordre_produit_d3_avant_d2_la_cellule_masquee_par_d3_est_lue_par_d2(self):
        """Tâche 5.12 (D3 avant D2). A : créés 30, sans affects 3 (masqué, sous 5), sans trouvé ; B : créés 40, sans affects 27, un trouvé de 13 (égal aux
        défauts distincts, P2) ; produit : 70 et 30. Le test fixe le résultat, pas l'ordre : avec une équipe sans ligne de version et un trouvé au plus égal
        aux défauts distincts (P2), l'excès du produit est au plus 0, et D2 masque sans affects du produit qu'il passe avant ou après D3. L'ordre D3 puis D2
        n'est plus discriminé par ce test (données d'origine, trouvé 50, incohérentes avec P2). Données ratifiées par l'auteur le 2026-11-05 (réponse Q1 (a))."""
        c = self.conn()
        self.remplir_semaines(c, {"A": [(30, 3, None)], "B": [(40, 27, (13,))]}, self.SEMAINES[:1])
        produit = self.libres(c, "(produit)")[0]
        self.assertEqual((produit["defects_created"], produit["defects_without_affects"]), (None, None))

    def test_ecart_d_retabli_semaine_sans_terme_le_sql_et_le_python_masquent_la_ligne(self):
        """Écart (d) de D4 (tâche 5.3), levé le 2026-11-05 (R-20261105-6 Q4 (a)) puis RÉTABLI par l'auteur le 2026-11-06 (R-20261106-22 et
        R-20261106-23, qui remplacent cette levée) : une semaine retenue sans ligne par version pour l'équipe, ou le produit, se lit comme dans 0022
        (m = 0, excès sous 5) ; D2 et D5-e s'y appliquent, dans le SQL (migration 0036) comme dans le Python : sans affects est masqué, puis les créés,
        pour l'équipe et pour le produit. Témoin de l'écart rétabli : (40, 10) publiés avant, (None, None) maintenant."""
        c = self.conn()
        self.version(c, nom="v-un", sortie=photo.SORTIE)
        self.semaine(c, photo.LUNDI, "reconstructed")
        self.ligne_libre(c, photo.LUNDI, "A", creees=40, sans_affects=10, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)
        vue = self.lignes_libres(c)
        brutes = [("2026-11-02", True, "A", None, None, 40, 10, 20, 10), ("2026-11-02", True, fv.PRODUIT, None, None, 40, 10, 20, 10)]
        noms = ["week_start", "n_adopted", "team", "version_no", "found", "defects_created", "defects_without_affects", "resolved_week",
                "resolved_week_defects"]
        cellules = fv.masquer_vue("v_version_quality_photo", noms, brutes, fv.PLANCHER)
        for equipe, sortie in zip(("A", fv.PRODUIT), cellules):
            with self.subTest(equipe=equipe):
                self.assertEqual((vue[equipe]["defects_created"], vue[equipe]["defects_without_affects"]), (None, None))
                self.assertEqual((sortie["defects_created"].get("value"), sortie["defects_without_affects"].get("value")), (None, None))
                self.assertIn("masked", sortie["defects_without_affects"])


class ParitePart(AvecBase):
    """Tâche 1.4, conception D4 : masquer_vue au plancher, appliquée aux comptes bruts, redonne la vue de la part, sur des tables tirées avec des graines fixes."""
    ticket = part.AvecBase.ticket
    remplir = part.AvecBase.remplir
    debut_trimestre = part.AvecBase.debut_trimestre
    GRAINES = (11, 23, 37)
    DECALAGES = (-3, -6, -9)                                                         # un trimestre terminé par table tirée (R-20261114-58 : trois trimestres)
    TIRAGES = 4                                                                      # les quatre tirages d'origine : le quatrième est joué par un test neuf

    def tirer(self, graine):
        """Par trimestre, de trois à cinq équipes ; items de 0 à 25 (les petits dominent), avec fix version de 0 à items."""
        hasard = random.Random(graine)
        tables = []
        for _ in range(self.TIRAGES):
            equipes = {}
            for nom in "ABCDE"[:hasard.randint(3, 5)]:
                items = hasard.choice([0, 1, 2, 3, 4, 5, 5, 6, 8, 10, 14, 20, 25])
                if items:
                    equipes[nom] = (items, hasard.randint(0, items))
            tables.append(equipes)
        return tables

    def brutes(self, equipes, trimestre):
        noms = COLONNES_PART
        lignes = [(nom, trimestre, n, f, round(100.0 * f / n, 1), None) for nom, (n, f) in sorted(equipes.items())]
        if equipes:
            n, f = sum(v[0] for v in equipes.values()), sum(v[1] for v in equipes.values())
            lignes.append(("(produit)", trimestre, n, f, round(100.0 * f / n, 1), None))
        return noms, lignes

    def parite(self, graine, tirages=slice(0, 3), decalages=None):
        """`tirages` : les tables jouées (les trois premières par défaut, au décalage de DECALAGES ; le quatrième tirage, au décalage -3, par un test neuf)."""
        decalages = decalages or self.DECALAGES
        c = self.conn()
        self.creer_equipes(c, "ABCDE")
        tables = self.tirer(graine)[tirages]
        for decalage, equipes in zip(decalages, tables):
            for nom, (n, f) in equipes.items():
                self.remplir(c, "ABCDE".index(nom) + 1, nom, n, f, decalage, prefixe=f"{nom}{graine}")
        publiees = {(l[0], l[1]): normaliser(l[2:5]) for l in self.lire(c, f"SELECT team, quarter_start, items, with_fix_version, share_percent FROM {PART}")}
        for decalage, equipes in zip(decalages, tables):
            if not equipes:
                continue
            trimestre = self.debut_trimestre(c, decalage)
            noms, lignes = self.brutes(equipes, trimestre)
            cellules = fv.masquer_vue("v_team_fix_version_share", noms, lignes, fv.PLANCHER)
            for ligne, sortie in zip(lignes, cellules):
                attendu = publiees[(ligne[0], trimestre)]
                obtenu = tuple(None if "masked" in sortie[col] else float(sortie[col]["value"]) for col in ("items", "with_fix_version", "share_percent"))
                self.assertEqual(obtenu, attendu, f"graine {graine}, trimestre {decalage}, équipe {ligne[0]}, table {equipes}")

    def test_parite_graine_11(self):
        self.parite(11)

    def test_parite_graine_23(self):
        self.parite(23)

    def test_parite_graine_37(self):
        self.parite(37)

    # Quatrième tirage de chaque graine (R-20261114-58) : même tirage qu'à l'origine (les trois premiers sont consommés de la même façon), joué seul au décalage -3.
    # L'attendu est celui d'origine : masquer_vue au plancher, appliquée aux comptes bruts du tirage, comparée à la vue publiée ; il n'est pas lu dans la vue.
    def test_parite_graine_11_quatrieme_tirage_de_test_parite_graine_11(self):
        self.parite(11, tirages=slice(3, 4), decalages=(-3,))

    def test_parite_graine_23_quatrieme_tirage_de_test_parite_graine_23(self):
        self.parite(23, tirages=slice(3, 4), decalages=(-3,))

    def test_parite_graine_37_quatrieme_tirage_de_test_parite_graine_37(self):
        self.parite(37, tirages=slice(3, 4), decalages=(-3,))


def valeur_publiee(cellule):
    return None if "masked" in cellule else cellule["value"]


class PariteRetard(AvecBase):
    """Revue 2, M1 (tâche 5.3) : le retard, SQL contre masquer_vue au plancher (la part brute en vue liée, D5-c), sur des tables tirées, graines fixes."""
    ticket = photo.AvecBase.ticket
    remplir = photo.AvecBase.remplir
    lire_photo = photo.AvecBase.lire
    debut_trimestre = part.AvecBase.debut_trimestre
    VALEURS = [0, 1, 2, 3, 4, 5, 6, 8, 12, 20]

    def parite(self, graine):
        hasard = random.Random(graine)
        paniers = {}
        for nom in "ABCD"[:hasard.randint(2, 4)]:
            valeurs = tuple(hasard.choice(self.VALEURS) for _ in range(5))
            if sum(valeurs):
                paniers[nom] = valeurs
        return self.comparer(graine, paniers)

    def test_cas_fixe_x19_le_produit_complete_en_chaine_comme_le_python(self):
        """Revue 3, M1 (cas partagé X19) : A = (4, 4, 5, 5, 6), B = (6, 6, 5, 5, 7) ; produit (10, 10, 10, 10, 13), b1 et b2 cachés par D3. La
        règle du produit boucle : b3 puis b4 sont masqués, b5 et les items restent. Une seule étape ne masquerait que b3."""
        produit = self.comparer("X19", {"A": (4, 4, 5, 5, 6), "B": (6, 6, 5, 5, 7)})["(produit)"]
        self.assertEqual([produit[c] for c in COLONNES_RETARD[2:]], [53, None, None, None, None, 13])

    def comparer(self, graine, paniers):
        c = self.conn()
        self.creer_equipes(c, "ABCD")
        for nom, valeurs in paniers.items():
            self.remplir(c, "ABCD".index(nom) + 1, nom, [-1] * valeurs[0] + [3] * valeurs[1] + [20] * valeurs[2] + [60] * valeurs[3] + [None] * valeurs[4])
        trimestre = self.debut_trimestre(c, -3)
        lignes = [(nom, trimestre, sum(v), *v) for nom, v in sorted(paniers.items())]
        total = tuple(sum(v[i] for v in paniers.values()) for i in range(5))
        lignes.append(("(produit)", trimestre, sum(total), *total))
        brutes_part = [(nom, trimestre, sum(v) + 5, sum(v), round(100.0 * sum(v) / (sum(v) + 5), 1), None) for nom, v in sorted(paniers.items())]
        brutes_part.append(("(produit)", trimestre, sum(total) + 5 * len(paniers), sum(total),
                            round(100.0 * sum(total) / (sum(total) + 5 * len(paniers)), 1), None))
        cellules = fv.masquer_vue(fv.VUE_RETARD, COLONNES_RETARD, lignes, fv.PLANCHER, liees={fv.VUE_PART: (COLONNES_PART, brutes_part)})
        publiees = {l["team"]: l for l in self.lire_photo(c, photo.RETARD)}
        for ligne, sortie in zip(lignes, cellules):
            for colonne in COLONNES_RETARD[2:]:
                self.assertEqual(valeur_publiee(sortie[colonne]), publiees[ligne[0]][colonne], f"graine {graine}, {ligne[0]}, {colonne}, table {paniers}")
        return publiees

    def test_parite_graine_2(self):
        self.parite(2)

    def test_parite_graine_5(self):
        self.parite(5)

    def test_parite_graine_9(self):
        self.parite(9)

    def test_parite_graine_14(self):
        self.parite(14)


class PariteNoms(AvecBase):
    """Revue 2, M1 : noms et identifiants, SQL contre masquer_vue au plancher (Jira propre : le compte du nom est la somme de ses identifiants)."""
    ticket = ContreExemplesEquipes.ticket
    passage = ContreExemplesEquipes.passage
    VALEURS = [1, 2, 3, 4, 5, 5, 6, 8, 9]

    def parite(self, graine):
        hasard = random.Random(graine)
        c = self.conn()
        noms = {nom: tuple(hasard.choice(self.VALEURS) for _ in range(hasard.randint(1, 3))) for nom in "ABCD"[:hasard.randint(2, 4)]}
        self.creer_equipes(c, sorted(noms))
        run = self.passage(c)
        numero = 0
        for equipe, nom in enumerate(sorted(noms), start=1):
            for k, nombre in enumerate(noms[nom], start=1):
                for _ in range(nombre):
                    cle = f"PROJ-{numero}"
                    numero += 1
                    self.ticket(c, cle, equipe)
                    c.execute("SET ROLE pmzilla_flow")
                    c.execute("INSERT INTO flow.raw_issue_snapshots (issue_key, run_id, updated_at, project, type, status, created_at, content_hash, teams) "
                              "VALUES (%s, %s, now(), 'PROJ', 'Story', 'Open', now(), 'h', %s::jsonb)", (cle, run, '[{"name": "%s", "jira_team_id": "id%s%d"}]' % (nom, nom, k)))
                    c.execute("RESET ROLE")
        c.commit()
        c.execute("SET ROLE pmzilla_flow_views")
        sql_noms = {l[0]: l[1] for l in c.execute("SELECT team, tickets FROM flow.v_teams").fetchall()}
        sql_ids = {(l[0], l[1]): l[2] for l in c.execute("SELECT team, jira_team_id, tickets FROM flow.v_team_jira_ids").fetchall()}
        c.execute("RESET ROLE")
        noms_t, noms_i, noms_s = ["team", "team_type", "tickets"], ["team", "jira_team_id", "tickets"], ["team", "type", "status_category", "status", "tickets"]
        equipes = [(nom, None, sum(v)) for nom, v in sorted(noms.items())]
        ids = [(nom, f"id{nom}{k}", n) for nom, v in sorted(noms.items()) for k, n in enumerate(v, start=1)]
        statuts = [(nom, "Story", "To Do", "Open", sum(v)) for nom, v in sorted(noms.items())]
        liees_statut = {"v_team_status": (noms_s, statuts)}
        py_noms = fv.masquer_vue("v_teams", noms_t, equipes, fv.PLANCHER, liees={"v_team_jira_ids": (noms_i, ids), **liees_statut})
        publiee = [(e[0], None, valeur_publiee(c_["tickets"])) for e, c_ in zip(equipes, py_noms)]
        py_ids = fv.masquer_vue("v_team_jira_ids", noms_i, ids, fv.PLANCHER, liees={"v_teams": (noms_t, publiee), **liees_statut})
        for e, cellule in zip(equipes, py_noms):
            self.assertEqual(valeur_publiee(cellule["tickets"]), sql_noms[e[0]], f"graine {graine}, nom {e[0]}, table {noms}")
        for i, cellule in zip(ids, py_ids):
            self.assertEqual(valeur_publiee(cellule["tickets"]), sql_ids[(i[0], i[1])], f"graine {graine}, {i[0]} {i[1]}, table {noms}")

    def test_parite_graine_4(self):
        self.parite(4)

    def test_parite_graine_17(self):
        self.parite(17)

    def test_parite_graine_29(self):
        self.parite(29)

    def test_parite_graine_41(self):
        self.parite(41)


class PariteLigneLibre(AvecBase):
    """Revue 2, M1 : la photo (trouvés par version, ligne sans version, ligne du produit), une semaine retenue, SQL contre masquer_vue au plancher."""
    version = photo.AvecBase.version
    semaine = photo.AvecBase.semaine
    ligne_version = photo.AvecBase.ligne_version
    ligne_libre = photo.AvecBase.ligne_libre
    adopter = photo.AvecBase.adopter
    lire_photo = photo.AvecBase.lire
    NOMS = ["week_start", "n_adopted", "team", "version_no", "found", "defects_created", "defects_without_affects", "resolved_week", "resolved_week_defects"]

    def parite(self, graine):
        hasard = random.Random(graine)
        c = self.conn()
        no1 = self.version(c, nom="v-un", sortie=photo.SORTIE)
        no2 = self.version(c, nom="v-deux", sortie=photo.SORTIE)
        self.semaine(c, photo.LUNDI, "reconstructed")
        lundi = photo.LUNDI.isoformat()
        equipes = {}
        for nom in "ABC"[:hasard.randint(2, 3)]:
            f1, f2 = hasard.choice([1, 2, 3, 4, 5, 6, 8, 12]), hasard.choice([1, 2, 3, 4, 5, 6, 8, 12])
            distincts = hasard.randint(max(f1, f2), f1 + f2)
            sans = hasard.choice([0, 3, 5, 9, 15])
            equipes[nom] = (f1, f2, sans + distincts, sans)
            self.ligne_version(c, photo.LUNDI, nom, no1, found=f1)
            self.ligne_version(c, photo.LUNDI, nom, no2, found=f2)
            self.ligne_libre(c, photo.LUNDI, nom, creees=sans + distincts, sans_affects=sans, resolus=20, resolus_defauts=10)
        self.adopter(c, 6)
        brutes = []
        for nom, (f1, f2, crees, sans) in sorted(equipes.items()):
            brutes += [(lundi, True, nom, no1, f1, None, None, None, None), (lundi, True, nom, no2, f2, None, None, None, None),
                       (lundi, True, nom, None, None, crees, sans, 20, 10)]
        s = lambda i: sum(v[i] for v in equipes.values())
        brutes += [(lundi, True, "(produit)", no1, s(0), None, None, None, None), (lundi, True, "(produit)", no2, s(1), None, None, None, None),
                   (lundi, True, "(produit)", None, None, s(2), s(3), 20 * len(equipes), 10 * len(equipes))]
        cellules = fv.masquer_vue("v_version_quality_photo", self.NOMS, brutes, fv.PLANCHER)
        publiees = {(l["team"], l["version_no"]): l for l in self.lire_photo(c) if l["team"] is not None}
        for ligne, sortie in zip(brutes, cellules):
            cle = (ligne[2], ligne[3])
            colonnes = ("found",) if ligne[3] is not None else ("defects_created", "defects_without_affects")
            for colonne in colonnes:
                self.assertEqual(valeur_publiee(sortie[colonne]), publiees[cle][colonne], f"graine {graine}, {cle}, {colonne}, table {equipes}")

    def test_parite_graine_6(self):
        self.parite(6)

    def test_parite_graine_13(self):
        self.parite(13)

    def test_parite_graine_22(self):
        self.parite(22)

    def test_parite_graine_35(self):
        self.parite(35)


if __name__ == "__main__":
    unittest.main()
