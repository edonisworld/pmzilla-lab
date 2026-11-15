"""Les vues sur les trois derniers trimestres clos (change de trois trimestres clos, R-20261114-45, -49, -51 ; conception D1, D2, D3, D4).

    bash tools/dbtest.sh db

Les tests sans base (SansBase) lisent les fichiers de migration : la fonction de fenêtre, ses droits, la dernière définition de chaque vue (aucun
`generate_series(1, 4)`, un seul appel de la fonction de fenêtre) et la limite déclarée de D3 dans les commentaires. Les tests avec base (AvecBase) sont pour la preuve
en conteneur de la session et le dbtest de l'auteur : base jetable, données inventées, rôle des vues. Les attendus sont calculés à la main, jamais lus dans la vue.
"""
import re
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402
import test_flow_slice1_views as s1   # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import flow_views as fv  # noqa: E402

SUFFIXE = "_flow_trois_trimestres_clos.sql"
VUES = ("v_team_fix_version_share", "v_team_fix_version_lag", "v_t3_withheld", "v_team_lead_time_throughput", "v_task_without_team_share",
        "v_team_blocked_share", "v_unplanned_share", "v_team_ready_queue", "v_team_flow_inout", "v_team_delivery_fields_coverage")
VUES_COMMENTEES = tuple(v for v in VUES if v != "v_t3_withheld")          # la vue interne n'a pas de lecteur : pas de limite à lire
LIMITE_FR = "le plus ancien des trois trimestres peut perdre au plus un jour et quelques heures les derniers jours d'un trimestre (environ 1 %)"
LIMITE_EN = "the oldest of the three quarters may lose at most one day and a few hours on the last days of a quarter (about 1 %)"


def code_de():
    candidats = [m for m in db.lister_migrations() if m.nom.endswith(SUFFIXE)]
    assert len(candidats) == 1, f"une migration *{SUFFIXE} est attendue"
    return candidats[0].chemin.read_text(encoding="utf-8")


def sans_commentaires(texte):
    return re.sub(r"--[^\n]*", "", texte)


def definitions_finales():
    """La dernière définition (CREATE [OR REPLACE] VIEW) de chaque vue de flow après toutes les migrations, dans l'ordre des fichiers."""
    sql = "\n".join(sans_commentaires(m.chemin.read_text(encoding="utf-8")) for m in db.lister_migrations())
    vues = {}
    for m in re.finditer(r"(?is)\bCREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+flow\.(\w+)\s+AS(.*?);", sql):
        vues[m.group(1)] = m.group(2)
    return vues


class SansBase(unittest.TestCase):
    def test_la_fonction_de_fenetre_est_pure_et_sans_droit_public(self):
        code = sans_commentaires(code_de())
        self.assertRegex(code, r"(?is)CREATE\s+FUNCTION\s+flow\.closed_quarter_starts\(anchor\s+timestamptz\)\s+RETURNS\s+date\[\]\s+LANGUAGE\s+sql\s+IMMUTABLE\s+PARALLEL\s+SAFE"
                               r"\s+SET\s+search_path\s*=\s*pg_catalog,\s*pg_temp")
        corps = re.search(r"(?is)CREATE\s+FUNCTION\s+flow\.closed_quarter_starts.*?\$\$(.*?)\$\$", code).group(1)
        self.assertNotRegex(corps, r"(?i)\bFROM\s+flow\.|\bflow\.\w+\s*\(")             # aucune table ni vue lue
        self.assertRegex(code, r"(?is)REVOKE\s+ALL\s+ON\s+FUNCTION\s+flow\.closed_quarter_starts\(timestamptz\)\s+FROM\s+PUBLIC\s*;")
        self.assertRegex(code, r"(?is)GRANT\s+EXECUTE\s+ON\s+FUNCTION\s+flow\.closed_quarter_starts\(timestamptz\)\s+TO\s+pmzilla_flow_views,\s*pmzilla_mothra_views\s*;")
        self.assertEqual(len(re.findall(r"(?i)\bGRANT\b", code)), 1)                    # aucun GRANT de vue : les droits des vues sont conservés

    def test_les_dix_vues_sont_recreees_sous_le_proprietaire_sans_donnee_ni_table(self):
        code = sans_commentaires(code_de())
        self.assertEqual(sorted(re.findall(r"(?i)\bCREATE\s+OR\s+REPLACE\s+VIEW\s+flow\.(\w+)", code)), sorted(VUES))
        self.assertNotRegex(code, r"(?i)\bCREATE\s+VIEW\b")
        self.assertLess(re.search(r"(?i)SET\s+LOCAL\s+ROLE\s+pmzilla_owner", code).start(), re.search(r"(?i)CREATE\s+FUNCTION", code).start())
        self.assertNotRegex(code, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(code, r"(?i)\bPASSWORD\b|\b(CREATE|ALTER|DROP)\s+(ROLE|TABLE)\b|\bLOGIN\b")

    def test_garde_statique_aucune_fenetre_de_quatre_dans_la_derniere_definition_d_une_vue(self):
        """Garde de D2 : sa source est la fonction de fenêtre ; un écart (une vue qui garde sa fenêtre de quatre, ou une fenêtre écrite à la main) est un test rouge.
        Remplace : rien. Retrait : avec la fonction de fenêtre."""
        vues = definitions_finales()
        for vue in VUES:
            self.assertNotRegex(vues[vue], r"(?i)generate_series\s*\(\s*1\s*,\s*4\s*\)", vue)
            self.assertIn("flow.closed_quarter_starts(now())", vues[vue], vue)
        for vue, corps in vues.items():                                                 # aucune autre vue de flow n'écrit une fenêtre de trimestres à la main
            if vue not in VUES:
                self.assertNotRegex(corps, r"(?i)make_interval\s*\(\s*months\s*=>\s*3\s*\*\s*k\b", vue)

    def test_garde_statique_aucune_colonne_renommee_par_une_migration_n_est_lue_sous_son_ancien_nom(self):
        """Une vue recopiée de sa dernière définition TEXTUELLE peut citer une colonne que PostgreSQL a renommée depuis, sans réécrire la vue (0034 renomme cinq colonnes de
        flow.issue_delivery_fields, que la vue de 0033 suit sans qu'aucun fichier la réécrive). Source : les ALTER TABLE ... RENAME COLUMN des migrations antérieures à 0040 ;
        un écart est un test rouge. Remplace : rien. Retrait : avec la migration 0040."""
        propre = [m for m in db.lister_migrations() if m.nom.endswith(SUFFIXE)][0]
        code = sans_commentaires(propre.chemin.read_text(encoding="utf-8"))
        renommages = []
        for m in db.lister_migrations():
            if m.numero >= propre.numero:
                continue
            renommages += re.findall(r"(?is)ALTER\s+TABLE\s+(\S+)\s+RENAME\s+COLUMN\s+(\w+)\s+TO\s+(\w+)", sans_commentaires(m.chemin.read_text(encoding="utf-8")))
        anciens = {ancien for _, ancien, _ in renommages}
        self.assertTrue({"release_target", "verification_required", "product_safety", "isp", "code_review_status"} <= anciens)       # 0034, au moins
        for table, ancien, nouveau in renommages:
            self.assertNotRegex(code, rf"(?i)\b\w+\.{ancien}\b", f"{table} : {ancien} (renommée {nouveau}) ne doit plus être lue sous son ancien nom")

    def test_la_limite_de_d3_est_dans_le_commentaire_de_chaque_vue_trimestrielle(self):
        code = sans_commentaires(code_de())
        for vue in VUES_COMMENTEES:
            commentaire = re.search(rf"(?is)COMMENT\s+ON\s+VIEW\s+flow\.{vue}\s+IS\s+'((?:[^']|'')*)'\s*;", code)
            self.assertIsNotNone(commentaire, vue)
            texte = commentaire.group(1).replace("''", "'")
            self.assertIn(LIMITE_FR, texte, vue)
            self.assertIn(LIMITE_EN, texte, vue)


class AvecBase(unittest.TestCase):
    """Même base jetable que SchemaFlow (migrations appliquées, base supprimée à la fin), avec les aides de test_flow_slice1_views.py sans ses tests."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie
    equipes = s1.AvecBase.equipes
    ticket = s1.AvecBase.ticket
    lignes = s1.AvecBase.lignes
    quarter = s1.AvecBase.quarter
    remplir = s1.AvecBase.remplir
    definitions = s1.AvecBase.definitions

    # --- la fonction de fenêtre ---

    def debuts(self, c, ancre):
        return c.execute("SELECT flow.closed_quarter_starts(%s::timestamptz)", (ancre,)).fetchone()[0]

    def test_la_fonction_sur_des_ancres_fixes(self):
        c = self.conn()
        # attendus à la main : le trimestre de l'ancre moins 1, 2 et 3 trimestres, le plus récent d'abord
        self.assertEqual(self.debuts(c, "2027-03-31 23:00:00+00"), [date(2026, 10, 1), date(2026, 7, 1), date(2026, 4, 1)])      # dernier jour d'un trimestre
        self.assertEqual(self.debuts(c, "2027-04-01 00:00:00+00"), [date(2027, 1, 1), date(2026, 10, 1), date(2026, 7, 1)])      # premier jour d'un trimestre
        self.assertEqual(self.debuts(c, "2028-02-29 12:00:00+00"), [date(2027, 10, 1), date(2027, 7, 1), date(2027, 4, 1)])      # 29 février 2028
        self.assertEqual(self.debuts(c, "2027-03-31 21:00:00-05"), [date(2027, 1, 1), date(2026, 10, 1), date(2026, 7, 1)])      # 2027-04-01 02:00 UTC : lu en UTC

    def test_la_fonction_egale_la_fonction_python_chaque_jour_de_2027_a_2030(self):
        c = self.conn()
        c.execute("SET TIME ZONE 'UTC'")
        lues = c.execute("SELECT d::date, flow.closed_quarter_starts(d) FROM generate_series('2027-01-01 12:00+00'::timestamptz, '2030-12-31 12:00+00'::timestamptz, "
                         "interval '1 day') AS g(d) ORDER BY 1").fetchall()
        self.assertEqual(len(lues), 1461)                                            # 2027, 2028 (bissextile), 2029 et 2030
        for jour, debuts in lues:
            self.assertEqual(debuts, fv.trois_trimestres_clos(datetime(jour.year, jour.month, jour.day, 12, tzinfo=timezone.utc)), jour)

    def test_aucun_trimestre_partiel_hors_les_deux_derniers_jours_d_un_trimestre(self):
        """D3 : la recherche d'export couvre 364 jours (52 semaines) ; hors les deux derniers jours UTC d'un trimestre, le plus ancien des trois est entier. Les
        jours exacts sont comptés à minuit. Sur ces deux jours, le plus ancien départ reste à moins de PERIODE_MAX_JOURS + 1 jour (366)."""
        c = self.conn()
        c.execute("SET TIME ZONE 'UTC'")
        trop_vieux_hors_derniers_jours = c.execute(
            "SELECT g.d::date FROM generate_series('2027-01-01 00:00+00'::timestamptz, '2030-12-31 00:00+00'::timestamptz, interval '1 day') AS g(d) "
            "WHERE g.d::date < (date_trunc('quarter', g.d) + interval '3 months')::date - 2 "
            "AND g.d::date - (flow.closed_quarter_starts(g.d))[3] > 364").fetchall()
        self.assertEqual(trop_vieux_hors_derniers_jours, [])
        trop_vieux = c.execute(
            "SELECT g.d::date FROM generate_series('2027-01-01 00:00+00'::timestamptz, '2030-12-31 00:00+00'::timestamptz, interval '1 day') AS g(d) "
            "WHERE g.d::date - (flow.closed_quarter_starts(g.d))[3] > 365 + 1").fetchall()
        self.assertEqual(trop_vieux, [])

    def test_droits_de_la_fonction(self):
        c = self.conn()
        for role in ("pmzilla_flow_views", "pmzilla_mothra_views"):
            self.assertTrue(self.essaie(c, role, "SELECT flow.closed_quarter_starts(now())"), role)
        for role in ("pmzilla_flow", "pmzilla_flow_ro", "pmzilla_quality_views", "pmzilla_cases"):
            self.assertFalse(self.essaie(c, role, "SELECT flow.closed_quarter_starts(now())"), role)

    # --- les vues ---

    def trimestres_lus(self, c, vue):
        return {l[0] for l in self.lignes(c, f"flow.{vue}", "quarter_start") if l[0] is not None}

    def test_chaque_vue_ne_rend_que_les_trois_trimestres_clos(self):
        """Six éléments Story, Task et défauts par trimestre (aux décalages 0, -3, -6, -9 et -12) : aucune ligne du trimestre en cours ni du quatrième clos."""
        c = self.conn()
        self.equipes(c)
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.ref_unplanned_types (type, kind) VALUES ('SYN-type-defaut', 'defect')")
        c.execute("RESET ROLE")
        for decalage in (0, -3, -6, -9, -12):
            self.remplir(c, 1, 6, decalage, "S")
            self.remplir(c, 1, 6, decalage, "T", type_="Task")
        attendus = {self.quarter(c, d) for d in (-3, -6, -9)}
        for vue in ("v_team_lead_time_throughput", "v_task_without_team_share", "v_team_blocked_share", "v_unplanned_share", "v_team_flow_inout",
                    "v_team_delivery_fields_coverage"):
            self.assertEqual(self.trimestres_lus(c, vue), attendus, vue)

    def test_la_part_de_fix_version_et_le_retard_ne_rendent_que_les_trois_trimestres_clos(self):
        c = self.conn()
        self.equipes(c)
        for decalage in (0, -3, -6, -9, -12):
            self.remplir(c, 1, 10, decalage, "F")
            c.execute("SET ROLE pmzilla_flow")
            for i in range(10):
                c.execute("INSERT INTO flow.issue_current_versions (issue_key, kind, name) VALUES (%s, 'fix', 'SYN-version')", (f"F-{decalage}-{i}",))
            c.execute("RESET ROLE")
        attendus = {self.quarter(c, d) for d in (-3, -6, -9)}
        for vue in ("v_team_fix_version_share", "v_team_fix_version_lag"):
            self.assertEqual(self.trimestres_lus(c, vue), attendus, vue)

    def test_la_file_prete_ne_rend_que_les_trois_trimestres_clos(self):
        """Tâche 2.1 : v_team_ready_queue (0026). Six éléments prêts à la fin de chaque trimestre d'un décalage d (ouverts à cette fin : résolus le 40e jour du
        trimestre suivant, un passage au statut prêt dix jours avant la fin) : les décalages 3 (prêts à la fin du trimestre en cours), 0, -3, -6 et -9 donnent
        les fins des trimestres en cours, -3, -6, -9 et -12. Attendu à la main : une ligne de six pour chacun des trimestres -3, -6 et -9, aucune pour le
        trimestre en cours ni pour le quatrième clos."""
        c = self.conn()
        self.equipes(c)
        self.definitions(c, statuts=[("SYN-pret", "ready", True, True)])
        for decalage in (3, 0, -3, -6, -9):
            for i in range(6):
                cle = f"R{decalage}-{i}"
                self.ticket(c, cle, 1, decalage=decalage, jours=60)
                c.execute("SET ROLE pmzilla_flow")
                c.execute("INSERT INTO flow.transitions (issue_key, transitioned_at, to_status) "
                          "SELECT key, (date_trunc('quarter', now() AT TIME ZONE 'UTC') + make_interval(months => %s) - interval '10 days') AT TIME ZONE 'UTC', 'SYN-pret' "
                          "FROM flow.issues WHERE key = %s", (decalage, cle))
                c.execute("RESET ROLE")
        lues = {l[0]: l[1] for l in self.lignes(c, "flow.v_team_ready_queue", "quarter_start, ready")}
        self.assertEqual(lues, {self.quarter(c, -3): 6, self.quarter(c, -6): 6, self.quarter(c, -9): 6})

    def test_la_vue_interne_t3_ne_lit_que_les_trois_trimestres_clos(self):
        """Tâche 2.1 : flow.v_t3_withheld (0030). Un seul ticket par trimestre (aux décalages 0, -3, -6, -9 et -12) : le débit est sous le plancher, la règle (a)
        retire le trimestre. Attendu à la main : les seuls trimestres -3, -6 et -9 sont retirés, ni le trimestre en cours ni le quatrième clos. La vue interne se lit
        sous le propriétaire de la connexion, comme dans test_flow_t3_withheld.py."""
        c = self.conn()
        self.equipes(c)
        for decalage in (0, -3, -6, -9, -12):
            self.remplir(c, 1, 1, decalage, "W")
        c.commit()
        lues = c.execute("SELECT team, quarter_start FROM flow.v_t3_withheld").fetchall()
        self.assertEqual(sorted(lues), sorted(("Alpha", self.quarter(c, d)) for d in (-3, -6, -9)))

    def test_la_ligne_groupee_est_la_somme_des_trois_trimestres_quand_tout_est_visible(self):
        c = self.conn()
        self.equipes(c)
        for decalage, n in ((-3, 6), (-6, 7), (-9, 8)):
            self.remplir(c, 1, n, decalage, "A")
        lignes = self.lignes(c, s1.VUE_LT, "period, quarter_start, throughput, items_lt")
        trimestres = [l for l in lignes if l[0] == "quarter"]
        annee = [l for l in lignes if l[0] == "pooled_year"][0]
        self.assertEqual(sorted(l[2] for l in trimestres), [6, 7, 8])
        self.assertEqual(sorted(l[3] for l in trimestres), [6, 7, 8])
        self.assertEqual((annee[2], annee[3]), (21, 21))                          # à la main : 6 + 7 + 8 = 21, pour le débit comme pour items_lt
