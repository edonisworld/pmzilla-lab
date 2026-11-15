"""Vues v_version_quality_photo et v_team_fix_version_lag (change version-quality-photo, tâches 4.1 à 4.3 ; spec jira-flow-views, database-roles-views).

    bash tools/dbtest.sh db

Les tests sans base (SansBase) tournent toujours : lecture du fichier de migration, retrouvé par sa description et non par son numéro. Les autres
utilisent la base jetable de test_flow_schema.py et sont sautés sans elle. Données inventées.
"""
import datetime as dt
import re
import unittest

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402

PHOTO = "flow.v_version_quality_photo"
RETARD = "flow.v_team_fix_version_lag"
SECRET = "zzversionsecrete"
COLONNES_PHOTO = ["run_id", "source", "coverage", "week_start", "taken_at", "n_adopted", "n_modified_after_reading", "n_previous_weeks",
                  "n_previous_adopted_on", "n_weeks", "n_adopted_on", "team", "version_no", "release_date", "released",
                  "found", "found_open", "corrected_at_week", "corrected_now", "reopened", "defects_created", "defects_without_affects",
                  "resolved_week", "resolved_week_defects", "correction_share_percent", "without_affects_share_percent"]
COMPTES_ET_PARTS = COLONNES_PHOTO[15:]
COLONNES_RETARD = ["team", "quarter_start", "items", "before_or_at_resolution", "within_7_days", "within_30_days", "later", "no_history"]
SEAUX = COLONNES_RETARD[3:]
LUNDI = dt.date(2026, 11, 2)                       # un lundi : la semaine retenue pour une sortie du mercredi 2026-12-16 avec N = 6
SORTIE = dt.date(2026, 12, 16)                     # le lundi de sa semaine est le 2026-12-14 ; 6 semaines avant : le 2026-11-02
# 25 items, cinq par panier (avant, sous 7 jours, sous 30 jours, plus tard, sans historique) : aucun zéro, aucune cellule masquée. Un zéro masqué
# compte comme une cellule masquée (décision du 2026-10-23) : une équipe dont les items tombent dans un ou deux paniers perd sa plus petite cellule.
PLEINE = [-1] * 5 + [3] * 5 + [20] * 5 + [60] * 5 + [None] * 5


def migration(suffixe):
    candidats = [m for m in db.lister_migrations() if m.nom.endswith(suffixe)]
    return candidats[0] if len(candidats) == 1 else None


def code_de(suffixe):
    m = migration(suffixe)
    assert m is not None, f"une migration *{suffixe} est attendue"
    return m.chemin.read_text(encoding="utf-8")


def sans_commentaires(texte):
    return re.sub(r"--[^\n]*", "", texte)


class SansBase(unittest.TestCase):
    def test_deux_vues_sous_le_proprietaire_sans_table_ni_donnee(self):
        texte = code_de("_flow_version_photo_views.sql")
        code = sans_commentaires(texte)
        self.assertRegex(texte.splitlines()[0], r"^-- Schéma touché : flow")
        self.assertEqual(re.findall(r"(?i)\bCREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(flow\.\w+)", code), [PHOTO, RETARD])
        self.assertRegex(code, r"(?is)SET\s+LOCAL\s+ROLE\s+pmzilla_owner\s*;.*CREATE\s+VIEW")
        self.assertNotRegex(code, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(code, r"(?i)\bPASSWORD\b|\b(CREATE|ALTER|DROP)\s+(ROLE|TABLE)\b|\bLOGIN\b")

    def test_select_au_seul_role_des_vues(self):
        code = sans_commentaires(code_de("_flow_version_photo_views.sql"))
        grants = re.findall(r"(?is)\bGRANT\b.*?;", code)
        self.assertEqual(len(grants), 1, grants)
        self.assertRegex(grants[0], r"(?is)GRANT\s+SELECT\s+ON\s+flow\.v_version_quality_photo,\s*flow\.v_team_fix_version_lag\s+TO\s+pmzilla_flow_views\s*;")
        revoke = re.search(r"(?is)\bREVOKE\b.*?;", code).group(0)
        for role in ("PUBLIC", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_quality_views"):
            self.assertRegex(revoke, rf"\b{role}\b")
        self.assertNotRegex(revoke, r"pmzilla_flow_views")
        self.assertLess(code.index("REVOKE"), code.index("GRANT"))

    def test_aucun_nom_de_version_ni_raison_dans_les_vues(self):
        code = sans_commentaires(code_de("_flow_version_photo_views.sql"))
        self.assertNotRegex(code, r"(?i)version_photo_versions\s+\w+\s*\n?.*\.name\b|\bv\.name\b|\.reason\b|\breason\b")
        self.assertNotRegex(code, r"(?i)\b(issue_key|i\.key)\s+AS\b")                    # aucune clé n'est jamais une colonne de sortie

    def test_retard_lit_le_detail_de_la_part_et_masque_le_produit_par_colonne_entiere(self):
        """Décision 1 du 2026-10-23 : (a) la ligne d'équipe et celle du produit ne sont montrées que si la vue de la part montre son détail ; (b) une
        cellule du produit exige toutes les cellules d'équipe de la colonne (bool_and), plus le complément de ligne du produit."""
        code = sans_commentaires(code_de("_flow_version_photo_views.sql"))
        retard = code[code.index("CREATE VIEW flow.v_team_fix_version_lag"):]
        self.assertRegex(retard, r"(?is)FROM\s+flow\.v_team_fix_version_share\s+WHERE\s+team\s*<>\s*'\(produit\)'\s+AND\s+with_fix_version\s+IS\s+NOT\s+NULL")
        self.assertRegex(retard, r"(?is)FROM\s+flow\.v_team_fix_version_share\s+WHERE\s+team\s*=\s*'\(produit\)'\s+AND\s+with_fix_version\s+IS\s+NOT\s+NULL")
        self.assertEqual(len(re.findall(r"(?i)\bbool_and\(", retard)), 6)
        self.assertNotRegex(retard, r"(?i)\bf[1-5n]\b")                           # les anciens drapeaux de fuite du produit n'existent plus

    def test_garde_structurelle_avant_n(self):
        """Les lignes retenues passent par une jointure avec l'adoption courante : vide tant que le registre de N l'est."""
        code = sans_commentaires(code_de("_flow_version_photo_views.sql"))
        self.assertRegex(code, r"(?is)retenues\s+AS\s*\(.*?CROSS\s+JOIN\s+courante\b.*?release_date\s+IS\s+NOT\s+NULL")
        self.assertRegex(code, r"(?is)JOIN\s+retenues\s+rt\s+ON")
        self.assertRegex(code, r"(?is)SELECT\s+DISTINCT\s+week_start\s+FROM\s+retenues")

    def test_les_migrations_se_suivent_sans_trou(self):
        numeros = {m.nom.split("_", 1)[1]: m.numero for m in db.lister_migrations()}
        self.assertEqual(numeros["flow_version_photo_views.sql"], numeros["flow_version_photo.sql"] + 1)
        liste = sorted(numeros.values())
        self.assertEqual(liste, list(range(1, len(liste) + 1)))


class AvecBase(unittest.TestCase):
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    # --- fabrication (rôle d'import) --------------------------------------------------------------------------------
    def semaine(self, c, lundi, source="live", couverture="complete"):
        c.execute("SET ROLE pmzilla_flow")
        existant = c.execute("SELECT id FROM flow.version_photo_runs WHERE source = 'reconstructed'").fetchone() if source == "reconstructed" else None
        if existant:                                                           # les semaines reconstruites du jeu d'essai vont dans un même passage
            run = existant[0]
        else:
            run = c.execute("INSERT INTO flow.version_photo_runs (taken_at, source) VALUES ('2026-10-23T14:00:00+00', %s) RETURNING id", (source,)).fetchone()[0]
        c.execute("INSERT INTO flow.version_photo_weeks (week_start, run_id, coverage) VALUES (%s, %s, %s)", (lundi, run, couverture))
        c.execute("RESET ROLE")
        return run

    def version(self, c, nom=SECRET, sortie=None, sortie_drapeau=None):
        c.execute("SET ROLE pmzilla_flow")
        no = c.execute("INSERT INTO flow.version_photo_versions (name, release_date, released) VALUES (%s, %s, %s) RETURNING version_no",
                       (nom, sortie, sortie_drapeau)).fetchone()[0]
        c.execute("RESET ROLE")
        return no

    def ligne_version(self, c, lundi, equipe, no, found, found_open=0, at_week=0, now=0, reopened=0):
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.version_photo_rows (week_start, team, version_no, found, found_open, corrected_at_week, corrected_now, reopened) "
                  "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", (lundi, equipe, no, found, found_open, at_week, now, reopened))
        c.execute("RESET ROLE")

    def ligne_libre(self, c, lundi, equipe, creees, sans_affects=0, resolus=0, resolus_defauts=0):
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.version_photo_rows (week_start, team, defects_created, defects_without_affects, resolved_week, resolved_week_defects) "
                  "VALUES (%s, %s, %s, %s, %s, %s)", (lundi, equipe, creees, sans_affects, resolus, resolus_defauts))
        c.execute("RESET ROLE")

    def adopter(self, c, semaines, jour="2026-11-20", raison=None):
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.version_photo_n (weeks, adopted_on, reason) VALUES (%s, %s, %s)", (semaines, jour, raison))
        c.execute("RESET ROLE")

    def lire(self, c, vue=PHOTO, colonnes="*", ou=""):
        c.commit()
        c.execute("SET ROLE pmzilla_flow_views")
        noms = [d.name for d in c.execute(f"SELECT {colonnes} FROM {vue} LIMIT 0").description]
        lignes = c.execute(f"SELECT {colonnes} FROM {vue} {ou}").fetchall()
        c.execute("RESET ROLE")
        return [dict(zip(noms, l)) for l in lignes]

    def jeu_complet(self, c):
        """Une version à sortie connue, une semaine retenue (2026-11-02) et deux semaines voisines, trois équipes aux comptes visibles."""
        no = self.version(c, sortie=SORTIE, sortie_drapeau=False)
        for lundi in (LUNDI - dt.timedelta(days=7), LUNDI, LUNDI + dt.timedelta(days=7)):
            self.semaine(c, lundi, "reconstructed")
            for equipe in ("Alpha", "Beta", "Gamma"):
                self.ligne_version(c, lundi, equipe, no, found=20, found_open=10, at_week=8, now=12, reopened=6)
                self.ligne_libre(c, lundi, equipe, creees=28, sans_affects=8, resolus=20, resolus_defauts=6)     # D = 28 - 8 = 20 = found (D15, P2)
        return no

    # --- colonnes et droits -----------------------------------------------------------------------------------------
    def test_colonnes_dans_l_ordre(self):
        c = self.conn()
        for vue, attendues in (("v_version_quality_photo", COLONNES_PHOTO), ("v_team_fix_version_lag", COLONNES_RETARD)):
            colonnes = [r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'flow' "
                                                "AND table_name = %s ORDER BY ordinal_position", (vue,))]
            self.assertEqual(colonnes, attendues, vue)

    def test_droits_des_deux_vues(self):
        c = self.conn()
        self.semaine(c, LUNDI)
        c.commit()
        for vue in (PHOTO, RETARD):
            self.assertTrue(self.essaie(c, "pmzilla_flow_views", f"SELECT * FROM {vue}"), vue)
            for role in ("pmzilla_quality_views", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_cases", "pmzilla_knowledge_ro"):
                self.assertFalse(self.essaie(c, role, f"SELECT * FROM {vue}"), f"{role} {vue}")
            for droit in ("INSERT", "UPDATE", "DELETE"):
                self.assertFalse(c.execute("SELECT has_table_privilege('pmzilla_flow_views', %s, %s)", (vue, droit)).fetchone()[0], droit)
        for table in fs.TABLES_PHOTO:
            self.assertFalse(self.essaie(c, "pmzilla_flow_views", f"SELECT * FROM flow.{table}"), table)

    # --- 4.1 : aucun compte avant N ---------------------------------------------------------------------------------
    def test_garde_aucun_compte_ni_part_tant_que_n_n_est_pas_adopte(self):
        c = self.conn()
        self.jeu_complet(c)                                                   # des comptes de 5 et plus, une date de sortie connue, aucun N
        self.semaine(c, LUNDI + dt.timedelta(days=14), "live")
        lignes = self.lire(c)
        self.assertEqual(len(lignes), 4)                                       # une ligne de couverture par semaine photographiée
        for ligne in lignes:
            for colonne in COMPTES_ET_PARTS:
                self.assertIsNone(ligne[colonne], f"{colonne} : un compte ou une part avant N")
            self.assertIsNone(ligne["team"])
            self.assertIsNone(ligne["version_no"])
            self.assertFalse(ligne["n_adopted"])

    def test_couverture_avant_n(self):
        c = self.conn()
        for i in range(10):
            self.semaine(c, dt.date(2026, 8, 10) + dt.timedelta(days=7 * i), "reconstructed", "partial" if i < 2 else "complete")
        self.semaine(c, dt.date(2026, 10, 19), "live")
        lignes = self.lire(c)
        self.assertEqual(len(lignes), 11)
        self.assertEqual(sum(1 for l in lignes if l["source"] == "reconstructed"), 10)
        self.assertEqual(sum(1 for l in lignes if l["coverage"] == "partial"), 2)
        self.assertEqual({l["n_adopted"] for l in lignes}, {False})
        self.assertEqual({l["n_modified_after_reading"] for l in lignes}, {False})
        self.assertEqual({(l["n_previous_weeks"], l["n_previous_adopted_on"]) for l in lignes}, {(None, None)})

    def test_dates_de_sortie_nulles_apres_n_couverture_seulement(self):
        c = self.conn()
        no = self.version(c)                                                   # date de sortie nulle (D3)
        self.semaine(c, LUNDI)
        self.ligne_version(c, LUNDI, "Alpha", no, found=20)
        self.adopter(c, 6)
        lignes = self.lire(c)
        self.assertEqual(len(lignes), 1)
        self.assertIsNone(lignes[0]["team"])
        self.assertTrue(lignes[0]["n_adopted"])
        for colonne in COMPTES_ET_PARTS:
            self.assertIsNone(lignes[0][colonne])

    # --- 4.2 : semaines retenues et masquage ------------------------------------------------------------------------
    def test_semaine_retenue_n_semaines_avant_la_semaine_de_sortie(self):
        c = self.conn()
        no = self.jeu_complet(c)
        self.adopter(c, 6)
        lignes = self.lire(c)
        avec_equipe = [l for l in lignes if l["team"] is not None]
        self.assertEqual({l["week_start"] for l in avec_equipe}, {LUNDI})
        self.assertEqual({l["version_no"] for l in avec_equipe if l["version_no"] is not None}, {no})
        self.assertEqual({l["n_weeks"] for l in avec_equipe}, {6})
        self.assertEqual({l["n_adopted_on"] for l in avec_equipe}, {dt.date(2026, 11, 20)})
        couverture = [l for l in lignes if l["team"] is None]
        self.assertEqual(len(couverture), 3)                                   # les trois semaines gardent leur ligne de couverture
        self.assertEqual({l["week_start"] for l in couverture}, {LUNDI - dt.timedelta(days=7), LUNDI, LUNDI + dt.timedelta(days=7)})
        equipe_alpha = [l for l in avec_equipe if l["team"] == "Alpha" and l["version_no"] == no][0]
        self.assertEqual((equipe_alpha["found"], equipe_alpha["found_open"], equipe_alpha["corrected_now"], equipe_alpha["release_date"]),
                         (20, 10, 12, SORTIE))
        self.assertFalse(equipe_alpha["released"])

    def test_sortie_un_lundi_la_semaine_de_sortie_est_celle_du_lundi(self):
        c = self.conn()
        no = self.version(c, sortie=dt.date(2026, 12, 14), sortie_drapeau=True)            # le lundi lui-même
        self.semaine(c, LUNDI)
        self.ligne_version(c, LUNDI, "Alpha", no, found=20)
        self.adopter(c, 6)
        self.assertEqual([l["found"] for l in self.lire(c) if l["team"] == "Alpha"], [20])

    def test_sortie_un_dimanche_meme_semaine_de_sortie(self):
        c = self.conn()
        no = self.version(c, sortie=dt.date(2026, 12, 20), sortie_drapeau=True)            # le dimanche de la semaine du 2026-12-14
        self.semaine(c, LUNDI)
        self.ligne_version(c, LUNDI, "Alpha", no, found=20)
        self.adopter(c, 6)
        self.assertEqual([l["found"] for l in self.lire(c) if l["team"] == "Alpha"], [20])

    def test_masquage_sous_cinq_et_paires(self):
        c = self.conn()
        no = self.version(c, sortie=SORTIE)
        self.semaine(c, LUNDI)
        self.ligne_version(c, LUNDI, "Alpha", no, found=20, found_open=17, at_week=6, now=12, reopened=2)
        self.ligne_version(c, LUNDI, "Beta", no, found=3, found_open=1, at_week=0, now=3, reopened=0)
        self.adopter(c, 6)
        alpha = [l for l in self.lire(c) if l["team"] == "Alpha"][0]
        self.assertEqual(alpha["found"], 20)
        self.assertIsNone(alpha["found_open"])                                   # 20 - 17 = 3 sous 5 : l'ouvert est masqué, le trouvé reste
        self.assertEqual(alpha["corrected_now"], 12)
        self.assertEqual(alpha["corrected_at_week"], 6)                          # 12 - 6 = 6 : la partie 6 et le reste 6 sont visibles
        self.assertIsNone(alpha["reopened"])                                     # deux rouverts : sous 5
        beta = [l for l in self.lire(c) if l["team"] == "Beta"][0]
        for colonne in ("found", "found_open", "corrected_at_week", "corrected_now", "reopened"):
            self.assertIsNone(beta[colonne], colonne)

    def test_partie_visible_quand_partie_et_reste_atteignent_cinq(self):
        c = self.conn()
        no = self.version(c, sortie=SORTIE)
        self.semaine(c, LUNDI)
        self.ligne_version(c, LUNDI, "Alpha", no, found=20, found_open=10, at_week=6, now=12, reopened=6)
        self.adopter(c, 6)
        alpha = [l for l in self.lire(c) if l["team"] == "Alpha"][0]
        self.assertEqual((alpha["found_open"], alpha["corrected_at_week"], alpha["reopened"]), (10, 6, 6))

    def test_ligne_produit_masquee_quand_une_seule_cellule_d_equipe_est_masquee(self):
        c = self.conn()
        no = self.version(c, sortie=SORTIE)
        self.semaine(c, LUNDI)
        self.ligne_version(c, LUNDI, "Alpha", no, found=20, found_open=10, at_week=6, now=12, reopened=6)
        self.ligne_version(c, LUNDI, "Beta", no, found=3, found_open=1, at_week=0, now=3, reopened=0)
        self.adopter(c, 6)
        produit = [l for l in self.lire(c) if l["team"] == "(produit)" and l["version_no"] is not None][0]
        self.assertIsNone(produit["found"])                                      # Beta est la seule cellule masquée : la différence la redonnerait
        self.assertIsNone(produit["corrected_now"])

    def test_ligne_produit_visible_sans_cellule_masquee(self):
        c = self.conn()
        self.jeu_complet(c)
        self.adopter(c, 6)
        produit = [l for l in self.lire(c) if l["team"] == "(produit)" and l["version_no"] is not None]
        self.assertEqual(len(produit), 1)
        self.assertEqual((produit[0]["found"], produit[0]["found_open"], produit[0]["corrected_now"]), (60, 30, 36))

    def test_ligne_produit_masquee_quand_les_cellules_masquees_font_moins_de_cinq(self):
        c = self.conn()
        no = self.version(c, sortie=SORTIE)
        self.semaine(c, LUNDI)
        for equipe in ("Alpha", "Beta", "Gamma"):
            self.ligne_version(c, LUNDI, equipe, no, found=20, found_open=10, at_week=6, now=12, reopened=6)
        self.ligne_version(c, LUNDI, "Delta", no, found=2, found_open=1, at_week=0, now=2, reopened=0)
        self.ligne_version(c, LUNDI, "Epsilon", no, found=2, found_open=1, at_week=0, now=1, reopened=0)
        self.adopter(c, 6)
        produit = [l for l in self.lire(c) if l["team"] == "(produit)" and l["version_no"] is not None][0]
        self.assertIsNone(produit["found"])                                      # deux cellules masquées dont la somme (4) est sous 5

    def libre_de(self, c, equipe):
        return [l for l in self.lire(c) if l["team"] == equipe and l["version_no"] is None][0]

    def test_sans_affects_masque_quand_tous_les_termes_de_la_ligne_sont_publies_et_l_exces_est_sous_cinq(self):
        """Décision 1 du 2026-10-23, révisée par masking-sums (D5-e) : la ligne « créés = sans affects + trouvés » est entièrement publiée et l'excès
        des trouvés (12) sur les défauts avec affects (20 - 8 = 12) est nul : le nombre de défauts à plusieurs affects versions se lirait, sans affects
        est masqué avec sa part ; seul caché, il se lirait par différence (20 - 12 = 8) : D2 repasse jusqu'au point fixe (décision du 2026-10-27,
        cas partagé X18) et masque aussi les défauts créés de la ligne d'équipe. La ligne du produit (ici l'équipe est seule) suit : D3 masque les deux
        colonnes parce que les cellules de l'équipe le sont. Même règle que le test « sans affects au seuil relevé masque les créés quand aucun
        terme n'est caché » de tests/flow_views : la vue ne doit rendre sans affects par différence ni sur l'équipe ni sur le produit. Parité Python :
        test_sans_affects_ligne_du_produit_un_seul_terme_masque_par_les_equipes_masque_les_crees (tests/flow_views/test_photo_versions.py,
        mêmes données)."""
        c = self.conn()
        no = self.version(c, sortie=SORTIE)
        self.semaine(c, LUNDI)
        self.ligne_version(c, LUNDI, "Alpha", no, found=12)
        self.ligne_libre(c, LUNDI, "Alpha", creees=20, sans_affects=8, resolus=20, resolus_defauts=6)
        self.adopter(c, 6)
        libre = self.libre_de(c, "Alpha")
        self.assertEqual((libre["defects_created"], libre["defects_without_affects"]), (None, None))
        self.assertIsNone(libre["without_affects_share_percent"])
        self.assertEqual(float(libre["correction_share_percent"]), 30.0)
        produit = self.libre_de(c, "(produit)")
        self.assertEqual((produit["defects_created"], produit["defects_without_affects"]), (None, None))      # D3 puis D2 sur la ligne du produit
        self.assertIsNone(produit["without_affects_share_percent"])
        self.assertEqual(float(produit["correction_share_percent"]), 30.0)                                  # les autres comptes ne sont pas concernés
        trouve = [l for l in self.lire(c) if l["team"] == "(produit)" and l["version_no"] is not None][0]
        self.assertEqual(trouve["found"], 12)                                                               # le trouvé du produit reste visible

    def test_sans_affects_masque_quand_un_seul_terme_est_cache(self):
        """Décision 1 : une version non retenue cette semaine (date de sortie nulle) cache son trouvé ; seul terme caché, il se retrouverait
        par défauts créés moins sans affects moins le trouvé visible : sans affects est masqué, avec sa part ; D2 repasse (point fixe, décision du
        2026-10-27) : sans affects masqué et un seul terme caché, les défauts créés de la ligne d'équipe sont masqués à leur tour."""
        c = self.conn()
        no = self.version(c, sortie=SORTIE)
        cache = self.version(c, nom=SECRET + "2")                               # aucune date de sortie : jamais retenue
        self.semaine(c, LUNDI)
        self.ligne_version(c, LUNDI, "Alpha", no, found=12)
        self.ligne_version(c, LUNDI, "Alpha", cache, found=6)
        self.ligne_libre(c, LUNDI, "Alpha", creees=25, sans_affects=7, resolus=20, resolus_defauts=6)
        self.adopter(c, 6)
        libre = self.libre_de(c, "Alpha")
        self.assertIsNone(libre["defects_created"])
        self.assertIsNone(libre["defects_without_affects"])
        self.assertIsNone(libre["without_affects_share_percent"])
        self.assertEqual(float(libre["correction_share_percent"]), 30.0)         # les autres comptes et parts ne sont pas concernés
        produit = self.libre_de(c, "(produit)")                                 # D3 masque sans affects du produit ; un seul terme caché : les créés aussi
        self.assertEqual((produit["defects_created"], produit["defects_without_affects"]), (None, None))      # sinon l'attaquant lit 13

    def test_sans_affects_masque_quand_deux_termes_caches_non_retenus_font_cinq_ou_plus(self):
        """V retenue 12, deux non retenues de 3 et 3, créés 25, sans affects 7. La passe n_publies (aucun terme caché publié : excès 12 - (25 - 7)
        = -6, sous 5, D5-e) l'emporte sur la passe n_caches (somme 6, au moins 5) : sans affects est masqué. Publiée, la ligne fixerait la somme
        des non retenues à 6. Point fixe : sans affects masqué et aucun terme caché publié, les défauts créés le sont aussi."""
        c = self.conn()
        no = self.version(c, sortie=SORTIE)
        self.semaine(c, LUNDI)
        self.ligne_version(c, LUNDI, "Alpha", no, found=12)
        for i, trouves in enumerate((3, 3)):                                     # deux termes cachés de somme 6
            self.ligne_version(c, LUNDI, "Alpha", self.version(c, nom=f"{SECRET}-c{i}"), found=trouves)
        self.ligne_libre(c, LUNDI, "Alpha", creees=25, sans_affects=7, resolus=20, resolus_defauts=6)
        self.adopter(c, 6)
        libre = self.libre_de(c, "Alpha")
        self.assertEqual((libre["defects_created"], libre["defects_without_affects"]), (None, None))

    def test_sans_affects_masque_quand_deux_termes_caches_font_moins_de_cinq(self):
        c = self.conn()
        no = self.version(c, sortie=SORTIE)
        self.semaine(c, LUNDI)
        self.ligne_version(c, LUNDI, "Alpha", no, found=12)
        for i in range(2):
            self.ligne_version(c, LUNDI, "Alpha", self.version(c, nom=f"{SECRET}-c{i}"), found=2)           # deux termes cachés de somme 4
        self.ligne_libre(c, LUNDI, "Alpha", creees=25, sans_affects=7, resolus=20, resolus_defauts=6)
        self.adopter(c, 6)
        libre = self.libre_de(c, "Alpha")
        self.assertIsNone(libre["defects_created"])                              # point fixe : sans affects masqué, aucun terme caché publié
        self.assertIsNone(libre["defects_without_affects"])

    def test_defaut_a_deux_affects_versions_compte_dans_deux_trouves_pas_dans_deux_crees(self):
        """Décision 1 : un défaut peut porter plusieurs affects versions (clé : ticket, genre, nom). Ici huit défauts portent V et sept portent aussi W :
        la somme des trouvés (15) dépasse les défauts distincts avec affects (8) ; sans affects (2) est sous 5, aucun terme n'est caché : les
        défauts créés sont masqués avec lui, la relation n'est jamais publiée en entier."""
        c = self.conn()
        no = self.version(c, sortie=SORTIE)
        no2 = self.version(c, nom=SECRET + "2", sortie=SORTIE)
        self.semaine(c, LUNDI)
        self.ligne_version(c, LUNDI, "Alpha", no, found=8)
        self.ligne_version(c, LUNDI, "Alpha", no2, found=7)
        self.ligne_libre(c, LUNDI, "Alpha", creees=10, sans_affects=2, resolus=20, resolus_defauts=6)
        self.adopter(c, 6)
        libre = self.libre_de(c, "Alpha")
        self.assertIsNone(libre["defects_without_affects"])
        self.assertIsNone(libre["defects_created"])
        self.assertIsNone(libre["without_affects_share_percent"])
        self.assertEqual(float(libre["correction_share_percent"]), 30.0)

    def test_sans_affects_masque_et_terme_cache_les_defauts_crees_sont_masques(self):
        """Sans affects masqué (sous 5), trouvé retenu 22, un terme caché de 6 (version non retenue, invisible dans les lignes publiées). Publiés,
        les créés (30) donneraient sans affects = 30 - 22 = 8 à l'attaquant qui ne voit pas la version non retenue : ils sont masqués aussi (la
        plus stricte des passes n_publies et n_caches)."""
        c = self.conn()
        no = self.version(c, sortie=SORTIE)
        cache = self.version(c, nom=SECRET + "2")
        self.semaine(c, LUNDI)
        self.ligne_version(c, LUNDI, "Alpha", no, found=22)
        self.ligne_version(c, LUNDI, "Alpha", cache, found=6)
        self.ligne_libre(c, LUNDI, "Alpha", creees=30, sans_affects=2, resolus=20, resolus_defauts=6)
        self.adopter(c, 6)
        libre = self.libre_de(c, "Alpha")
        self.assertEqual((libre["defects_created"], libre["defects_without_affects"]), (None, None))

    def test_terme_retenu_mais_masque_cache_sans_affects_equipe_et_produit(self):
        """Revue du 2026-10-23 : V = 20 et W = 3, les deux versions retenues. W est retenue mais sa cellule (sous 5) est masquée : un terme caché, de
        valeur 3. Sans affects (8, visible par sa paire) serait retrouvé comme créés (31) moins V (20) moins 3 : il est masqué, les créés restent. La
        ligne du produit suit la même règle par la voie des termes du produit (sans elle, les créés seraient masqués à sa place)."""
        c = self.conn()
        no = self.version(c, sortie=SORTIE)
        no2 = self.version(c, nom=SECRET + "2", sortie=SORTIE)                   # retenue elle aussi : le terme n'est pas caché par la non-retenue
        self.semaine(c, LUNDI)
        self.ligne_version(c, LUNDI, "Alpha", no, found=20)
        self.ligne_version(c, LUNDI, "Alpha", no2, found=3)
        self.ligne_libre(c, LUNDI, "Alpha", creees=31, sans_affects=8, resolus=20, resolus_defauts=6)
        self.adopter(c, 6)
        lignes = self.lire(c)
        w = [l for l in lignes if l["team"] == "Alpha" and l["version_no"] == no2][0]
        self.assertIsNone(w["found"])                                            # retenue mais masquée
        libre = self.libre_de(c, "Alpha")
        self.assertEqual(libre["defects_created"], 31)
        self.assertIsNone(libre["defects_without_affects"])
        self.assertIsNone(libre["without_affects_share_percent"])
        produit = self.libre_de(c, "(produit)")
        self.assertEqual(produit["defects_created"], 31)
        self.assertIsNone(produit["defects_without_affects"])

    def test_zero_masque_compte_comme_cellule_masquee_dans_la_ligne_produit(self):
        """Décision C du 2026-10-23 : un zéro ne se retrouve pas par différence entre le produit et les équipes visibles."""
        c = self.conn()
        no = self.version(c, sortie=SORTIE)
        self.semaine(c, LUNDI)
        self.ligne_version(c, LUNDI, "Alpha", no, found=20, found_open=10, at_week=12, now=20, reopened=10)
        self.ligne_version(c, LUNDI, "Beta", no, found=20, found_open=10, at_week=12, now=20, reopened=0)      # un zéro : rouverts
        self.adopter(c, 6)
        lignes = [l for l in self.lire(c) if l["version_no"] is not None]
        beta = [l for l in lignes if l["team"] == "Beta"][0]
        produit = [l for l in lignes if l["team"] == "(produit)"][0]
        self.assertIsNone(beta["reopened"])
        self.assertIsNone(produit["reopened"])                                   # Beta est la seule cellule masquée, zéro compris : jamais redonnée

    def test_parts_de_la_ligne_libre(self):
        c = self.conn()
        no = self.version(c, sortie=SORTIE)
        no2 = self.version(c, nom=SECRET + "2", sortie=SORTIE)
        self.semaine(c, LUNDI)
        self.ligne_version(c, LUNDI, "Alpha", no, found=12)
        self.ligne_version(c, LUNDI, "Alpha", no2, found=6)                      # tous les termes publiés : rien n'est caché
        self.ligne_libre(c, LUNDI, "Alpha", creees=20, sans_affects=8, resolus=20, resolus_defauts=6)
        self.adopter(c, 6)
        libre = [l for l in self.lire(c) if l["team"] == "Alpha" and l["version_no"] is None][0]
        self.assertEqual((libre["defects_created"], libre["defects_without_affects"], libre["resolved_week"], libre["resolved_week_defects"]),
                         (20, 8, 20, 6))
        self.assertEqual(float(libre["correction_share_percent"]), 30.0)
        self.assertEqual(float(libre["without_affects_share_percent"]), 40.0)
        for colonne in COMPTES_ET_PARTS[:5]:
            self.assertIsNone(libre[colonne], colonne)

    def test_part_masquee_avec_sa_partie(self):
        c = self.conn()
        no = self.version(c, sortie=SORTIE)
        self.semaine(c, LUNDI)
        self.ligne_version(c, LUNDI, "Alpha", no, found=20)
        self.ligne_libre(c, LUNDI, "Alpha", creees=20, sans_affects=3, resolus=20, resolus_defauts=17)
        self.adopter(c, 6)
        libre = [l for l in self.lire(c) if l["team"] == "Alpha" and l["version_no"] is None][0]
        self.assertEqual(libre["resolved_week"], 20)
        self.assertIsNone(libre["defects_created"])                              # sans affects masqué et aucun terme caché : les créés le sont aussi
        self.assertIsNone(libre["defects_without_affects"])
        self.assertIsNone(libre["without_affects_share_percent"])
        self.assertIsNone(libre["resolved_week_defects"])                        # 20 - 17 = 3
        self.assertIsNone(libre["correction_share_percent"])

    def test_aucune_colonne_ne_porte_la_somme_du_trouve_et_du_corrige(self):
        c = self.conn()
        colonnes = [r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'flow' "
                                            "AND table_name = 'v_version_quality_photo'")]
        self.assertEqual([k for k in colonnes if "total" in k or "sum" in k or "both" in k], [])

    def test_aucun_nom_de_version_dans_la_vue(self):
        c = self.conn()
        self.jeu_complet(c)
        self.adopter(c, 6, raison="zzraison")
        self.adopter(c, 8, jour="2026-12-01", raison="zzraison")
        texte = repr(self.lire(c))
        self.assertNotIn(SECRET, texte)
        self.assertNotIn("zzraison", texte)

    # --- 4.3 : N modifié après lecture ------------------------------------------------------------------------------
    def test_n_modifie_apres_lecture(self):
        c = self.conn()
        self.jeu_complet(c)
        self.adopter(c, 6, jour="2026-11-20")
        lignes = self.lire(c)
        self.assertEqual({l["n_modified_after_reading"] for l in lignes}, {False})
        self.assertEqual({(l["n_previous_weeks"], l["n_previous_adopted_on"]) for l in lignes}, {(None, None)})
        self.adopter(c, 7, jour="2026-12-01", raison="zzraison")
        lignes = self.lire(c)
        self.assertEqual({l["n_modified_after_reading"] for l in lignes}, {True})              # couverture comprise
        self.assertEqual({(l["n_previous_weeks"], l["n_previous_adopted_on"]) for l in lignes}, {(6, dt.date(2026, 11, 20))})
        retenues = [l for l in lignes if l["team"] is not None]
        self.assertEqual({l["n_weeks"] for l in retenues}, {7})                                # la dernière adoption est la valeur effective
        self.assertEqual({l["n_adopted_on"] for l in retenues}, {dt.date(2026, 12, 1)})
        self.assertEqual({l["week_start"] for l in retenues}, {dt.date(2026, 10, 26)})        # sept semaines avant la semaine de sortie du 2026-12-14
        for ligne in lignes:
            self.assertNotIn("reason", ligne)

    # --- vue du retard ----------------------------------------------------------------------------------------------
    def ticket(self, c, cle, equipe, resolu_jours, premiere_apres_jours=None, type_="Story", trimestre=-3, sorti=False, avec_fix=True):
        """Un ticket résolu au milieu du trimestre décalé, avec une fix version courante (sauf `avec_fix=False`) et, sauf None, une première période
        posée N jours après."""
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, resolved_at, updated_at, team_id, out_of_export_at) "
                  "VALUES (%s, 'PROJ', %s, 'Closed', 'Done', now() - interval '2 years', "
                  "(date_trunc('quarter', now() AT TIME ZONE 'UTC') + make_interval(months => %s) + interval '40 days') AT TIME ZONE 'UTC', now(), %s, "
                  "CASE WHEN %s THEN now() END)", (cle, type_, trimestre, equipe, sorti))
        if avec_fix:
            c.execute("INSERT INTO flow.issue_current_versions (issue_key, kind, name) VALUES (%s, 'fix', %s)", (cle, SECRET))
        if avec_fix and premiere_apres_jours is not None:
            c.execute("INSERT INTO flow.issue_version_periods (issue_key, version, added_at) SELECT %s, %s, resolved_at + make_interval(days => %s) "
                      "FROM flow.issues WHERE key = %s", (cle, SECRET, premiere_apres_jours, cle))
        c.execute("RESET ROLE")

    def equipes(self, c):
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.teams (name) VALUES ('Alpha'), ('Beta'), ('Gamma'), ('Delta')")
        c.execute("RESET ROLE")

    def remplir(self, c, equipe, nom, repartition, sans_fix=5):
        """`repartition` : décalages en jours (None : sans historique), un ticket chacun. `sans_fix` : autant d'items résolus du même trimestre sans
        fix version, pour que le détail de la part (migration 0018 : ni avec ni sans sous 5) soit visible, condition de la ligne du retard (décision
        1(a) du 2026-10-23)."""
        for i, decalage in enumerate(repartition):
            self.ticket(c, f"{nom}-{i}", equipe, 0, decalage)
        for i in range(sans_fix):
            self.ticket(c, f"{nom}-sf{i}", equipe, 0, avec_fix=False)

    def part_par_equipe(self, c):
        return {l["team"]: l for l in self.lire(c, "flow.v_team_fix_version_share")}

    def retard_par_equipe(self, c):
        lignes = self.lire(c, RETARD)
        return {l["team"]: l for l in lignes}

    def test_retard_lisible_avant_n_et_sans_photo(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", PLEINE)
        ligne = self.retard_par_equipe(c)["Alpha"]
        self.assertEqual((ligne["items"], ligne["later"]), (25, 5))              # cinq de ces items reçoivent leur première fix version 60 jours après
        self.assertEqual(self.lire(c, PHOTO), [])                                # aucune photo, aucune adoption

    def test_retard_quatre_paniers(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", [-3] * 6 + [0] * 0 + [5] * 6 + [20] * 6 + [60] * 6 + [None] * 6)
        ligne = self.retard_par_equipe(c)["Alpha"]
        self.assertEqual((ligne["items"], ligne["before_or_at_resolution"], ligne["within_7_days"], ligne["within_30_days"], ligne["later"],
                          ligne["no_history"]), (30, 6, 6, 6, 6, 6))

    def test_retard_avant_ou_a_la_resolution_compte_zero_jour(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", [0] * 6 + [7] * 6 + [30] * 6 + [31] * 6 + [None] * 6)
        ligne = self.retard_par_equipe(c)["Alpha"]
        self.assertEqual((ligne["before_or_at_resolution"], ligne["within_7_days"], ligne["within_30_days"], ligne["later"]), (6, 6, 6, 6))

    def test_retard_ecarte_les_epics_les_sortis_et_les_non_resolus(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", [40] * 10)
        for i in range(6):
            self.ticket(c, f"E-{i}", 1, 0, 40, type_="Epic")
            self.ticket(c, f"S-{i}", 1, 0, 40, sorti=True)
        self.assertEqual(self.retard_par_equipe(c)["Alpha"]["items"], 10)

    def test_retard_masquage_cellule_sous_cinq_et_plus_petite_cellule_visible(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", [-1] * 3 + [3] * 6 + [20] * 6 + [60] * 6 + [None] * 6)       # 27 items : trois avant, six dans chacun des autres paniers
        self.remplir(c, 2, "B", PLEINE * 2)
        self.remplir(c, 3, "C", PLEINE * 2)
        alpha = self.retard_par_equipe(c)["Alpha"]
        self.assertEqual(alpha["items"], 27)
        self.assertIsNone(alpha["before_or_at_resolution"])
        self.assertIsNone(alpha["within_7_days"])                               # les cellules masquées font 3 : la plus petite visible l'est aussi
        self.assertEqual((alpha["within_30_days"], alpha["later"], alpha["no_history"]), (6, 6, 6))
        beta = self.retard_par_equipe(c)["Beta"]
        self.assertEqual((beta["items"], beta["before_or_at_resolution"], beta["later"]), (50, 10, 10))

    def test_retard_un_zero_masque_compte_comme_cellule_masquee(self):
        """Décision C du 2026-10-23 : des zéros masqués, de somme nulle, se retrouveraient par différence avec les items."""
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", [40] * 10)                                       # dix items tous « plus tard » : quatre zéros
        ligne = self.retard_par_equipe(c)["Alpha"]
        self.assertEqual(ligne["items"], 10)
        for colonne in SEAUX:
            self.assertIsNone(ligne[colonne], colonne)                            # la seule cellule visible aurait redonné les zéros par différence

    def test_retard_produit_jamais_une_seule_cellule_masquee(self):
        """Revue du 2026-10-23 : un compartiment du produit masqué parce qu'une cellule d'équipe l'est déjà compte parmi les masqués ; une valeur
        de 2 ne se retrouve pas par différences successives entre le produit et les équipes visibles."""
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", PLEINE * 2)
        self.remplir(c, 2, "B", [-1] * 2 + [3] * 11)                             # 13 items : [2, 11, 0, 0, 0]
        self.remplir(c, 3, "C", PLEINE * 2)
        lignes = self.retard_par_equipe(c)
        beta, produit = lignes["Beta"], lignes["(produit)"]
        self.assertEqual(beta["items"], 13)
        for colonne in SEAUX:
            self.assertIsNone(beta[colonne], colonne)                             # 2 sous 5, puis la plus petite cellule visible (11)
        self.assertEqual(produit["items"], 113)
        self.assertNotEqual(len([k for k in SEAUX if produit[k] is None]), 1)     # jamais une seule cellule masquée avec des items visibles
        for colonne in SEAUX:
            self.assertIsNone(produit[colonne], colonne)                          # chaque colonne porte une cellule d'équipe masquée, zéros compris

    def test_retard_ligne_masquee_quand_la_part_masque_le_detail_exemple_des_dix_huit(self):
        """Décision 1(a) du 2026-10-23 : une équipe de 20 items dont 18 avec fix version. La part masque 18 (sans fix version : 2, sous 5) ; le retard
        ne doit plus montrer items = 18, ni aucune cellule de cette ligne, ni celles du produit."""
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", PLEINE[:18], sans_fix=2)
        part = self.part_par_equipe(c)
        self.assertEqual(part["Alpha"]["items"], 20)
        self.assertIsNone(part["Alpha"]["with_fix_version"])                       # la part masque 18
        for ligne in self.lire(c, RETARD):
            for colonne in COLONNES_RETARD[2:]:
                self.assertIsNone(ligne[colonne], f"{ligne['team']} {colonne} : 18 se retrouverait par items")

    def test_retard_ligne_visible_quand_le_detail_de_la_part_l_est(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", PLEINE, sans_fix=5)
        self.assertIsNotNone(self.part_par_equipe(c)["Alpha"]["with_fix_version"])
        ligne = self.retard_par_equipe(c)["Alpha"]
        self.assertEqual((ligne["items"], ligne["later"]), (25, 5))

    def test_retard_une_equipe_masquee_par_la_part_masque_le_produit_du_trimestre(self):
        """Une équipe dont le détail de la part est masqué n'a aucune cellule visible : aucune colonne du produit n'est montrée, items compris."""
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", PLEINE * 2)
        self.remplir(c, 2, "B", PLEINE * 2)
        self.remplir(c, 3, "C", PLEINE[:18], sans_fix=2)
        lignes = self.retard_par_equipe(c)
        for colonne in COLONNES_RETARD[2:]:
            self.assertIsNone(lignes["Gamma"][colonne], colonne)
            self.assertIsNone(lignes["(produit)"][colonne], colonne)
        self.assertEqual(lignes["Alpha"]["items"], 50)

    @staticmethod
    def paniers(b1, b2, b3, b4, b5):
        """Décalages (jours) d'une équipe dont les cinq paniers valent b1 à b5."""
        return [-1] * b1 + [3] * b2 + [20] * b3 + [60] * b4 + [None] * b5

    def test_retard_contre_exemple_a_quatre_equipes_produit_des_colonnes_un_a_quatre_masque(self):
        """Décision 1(b) du 2026-10-23 : A = [10, 2, 20, 20, 20], B = [10, 1, 20, 20, 20], C = [20, 20, 2, 10, 20], D = [20, 20, 1, 10, 20]. Chaque
        équipe masque son petit nombre et sa plus petite cellule visible (A et B : colonnes 1 et 2 ; C et D : colonnes 3 et 4). Avant : produit visible
        sur les colonnes 1 et 4 et A2 + B2 = 3 déductible. Après : le produit des colonnes 1 à 4 est masqué ; la colonne 5, visible chez toutes les
        équipes, reste."""
        c = self.conn()
        self.equipes(c)
        for no, (equipe, nom, valeurs) in enumerate((("1", "A", (10, 2, 20, 20, 20)), ("2", "B", (10, 1, 20, 20, 20)),
                                                     ("3", "C", (20, 20, 2, 10, 20)), ("4", "D", (20, 20, 1, 10, 20)))):
            self.remplir(c, int(equipe), nom, self.paniers(*valeurs))
        lignes = self.retard_par_equipe(c)
        for equipe, masquees in (("Alpha", (0, 1)), ("Beta", (0, 1)), ("Gamma", (2, 3)), ("Delta", (2, 3))):
            for i, colonne in enumerate(SEAUX[:4]):
                self.assertEqual(lignes[equipe][colonne] is None, i in masquees, f"{equipe} {colonne}")
            self.assertIsNotNone(lignes[equipe]["no_history"], equipe)
        produit = lignes["(produit)"]
        for colonne in SEAUX[:4]:
            self.assertIsNone(produit[colonne], colonne)
        self.assertEqual((produit["items"], produit["no_history"]), (286, 80))

    def test_retard_masquage_items_sous_cinq(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", [40] * 3)
        self.remplir(c, 2, "B", [40] * 10)
        alpha = self.retard_par_equipe(c)["Alpha"]
        for colonne in COLONNES_RETARD[2:]:
            self.assertIsNone(alpha[colonne], colonne)

    def test_retard_ligne_produit(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", PLEINE * 2)
        self.remplir(c, 2, "B", PLEINE * 2)
        produit = self.retard_par_equipe(c)["(produit)"]
        self.assertEqual((produit["items"], produit["before_or_at_resolution"], produit["later"]), (100, 20, 20))
        self.remplir(c, 3, "C", [40] * 3)                                       # une seule cellule d'équipe masquée : le produit la redonnerait
        produit = self.retard_par_equipe(c)["(produit)"]
        self.assertIsNone(produit["items"])
        self.assertIsNone(produit["later"])

    def test_retard_trois_derniers_trimestres_termines(self):
        c = self.conn()
        self.equipes(c)
        for trimestre in (0, -3, -6, -9, -12, -15):
            for i in range(6):
                self.ticket(c, f"T{trimestre}-{i}", 1, 0, 40, trimestre=trimestre)
        c.commit()
        trimestres = {l["quarter_start"] for l in self.lire(c, RETARD) if l["team"] == "Alpha"}
        self.assertEqual(len(trimestres), 3)
        self.assertNotIn(c.execute("SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC'))::date").fetchone()[0], trimestres)

    def test_retard_aucun_nom_de_version(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, "A", [40] * 10)
        self.assertNotIn(SECRET, repr(self.lire(c, RETARD)))


if __name__ == "__main__":
    unittest.main()
