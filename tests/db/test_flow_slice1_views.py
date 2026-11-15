"""Les cinq vues agrégées de la tranche 1 de Mothra (change mothra-slices, tâche 15.1 ; conception D25, D33 et D34 ; décisions R-20261029-07 à -10 et -20 ;
spec jira-flow-views « Aggregated views per team and quarter feed Mothra's verdicts » et « Statistics of the aggregated views are masked under the floor »).

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Les tests sans base (SansBase) lisent le fichier de migration, retrouvé par sa description et non par son numéro. Les tests avec base (AvecBase)
sont pour le dbtest de l'auteur (bash tools/dbtest.sh db) : base jetable, données inventées, rôle des vues.
"""
import re
import unittest

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402

SUFFIXE = "_flow_slice1_views.sql"
VUE_LT = "flow.v_team_lead_time_throughput"
VUE_PART = "flow.v_task_without_team_share"
VUE_FILE = "flow.v_team_ready_queue"
VUE_BLOQUE = "flow.v_team_blocked_share"
VUE_NON_PLANIFIE = "flow.v_unplanned_share"
NOMS_VUES = ("v_team_lead_time_throughput", "v_task_without_team_share", "v_team_ready_queue", "v_team_blocked_share", "v_unplanned_share")


def code_de():
    candidats = [m for m in db.lister_migrations() if m.nom.endswith(SUFFIXE)]
    assert len(candidats) == 1, f"une migration *{SUFFIXE} est attendue"
    return candidats[0].chemin.read_text(encoding="utf-8")


def sans_commentaires(texte):
    return re.sub(r"--[^\n]*", "", texte)


class SansBase(unittest.TestCase):
    def test_cinq_vues_sous_le_proprietaire_sans_donnee_ni_table(self):
        texte = code_de()
        code = sans_commentaires(texte)
        self.assertRegex(texte.splitlines()[0], r"^-- Schéma touché : flow")
        self.assertEqual(sorted(re.findall(r"(?i)\bCREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+flow\.(\w+)", code)), sorted(NOMS_VUES))
        self.assertLess(re.search(r"(?i)SET\s+LOCAL\s+ROLE\s+pmzilla_owner", code).start(), re.search(r"(?i)CREATE\s+VIEW", code).start())
        self.assertNotRegex(code, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(code, r"(?i)\bPASSWORD\b|\b(CREATE|ALTER|DROP)\s+(ROLE|TABLE)\b|\bLOGIN\b")

    def test_select_au_seul_role_des_vues(self):
        code = sans_commentaires(code_de())
        grants = re.findall(r"(?is)\bGRANT\b.*?;", code)
        self.assertEqual(len(grants), 2, grants)
        liste = r",\s*".join(rf"flow\.{v}" for v in NOMS_VUES)
        self.assertRegex(grants[0], rf"(?is)GRANT\s+SELECT\s+ON\s+{liste}\s+TO\s+pmzilla_flow_views\s*;")
        self.assertRegex(grants[1], r"(?is)GRANT\s+EXECUTE\s+ON\s+FUNCTION\s+flow\.fuite_serie\(bigint\[\],\s*boolean\[\]\),\s*flow\.mask_count_zero\(bigint\)\s+TO\s+pmzilla_flow_views\s*;")
        revoke = re.search(r"(?is)\bREVOKE\b.*?;", code)
        self.assertIsNotNone(revoke)
        for role in ("PUBLIC", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_quality_views"):
            self.assertRegex(revoke.group(0), rf"\b{role}\b")
        self.assertLess(code.index("REVOKE"), code.index("GRANT"))

    def test_rattachement_par_l_equipe_du_ticket_seulement(self):
        code = sans_commentaires(code_de())
        debit = re.search(r"(?is)CREATE\s+VIEW\s+flow\.v_team_lead_time_throughput\s+AS(.*?);", code).group(1)
        self.assertRegex(debit, r"(?i)JOIN\s+flow\.teams\s+t\s+ON\s+t\.id\s*=\s*i\.team_id")
        self.assertNotRegex(debit, r"(?i)flow\.links|parent_key|issue_teams|\bepic\b")      # ni lien, ni parent, ni épic, ni seconde équipe
        self.assertRegex(debit, r"(?i)IN\s*\(\s*'story'\s*,\s*'task'\s*\)")
        self.assertRegex(debit, r"(?i)is_committed")
        self.assertRegex(debit, r"(?i)out_of_export_at\s+IS\s+NULL")
        self.assertRegex(debit, r"(?i)generate_series\s*\(\s*1\s*,\s*4\s*\)")

    def test_aucune_colonne_de_cle_de_titre_ou_de_personne(self):
        code = sans_commentaires(code_de())
        for vue in NOMS_VUES:
            corps = re.search(rf"(?is)CREATE\s+VIEW\s+flow\.{vue}\s+AS(.*?);", code).group(1)
            self.assertNotRegex(corps, r"(?i)\bAS\s+(key|issue_key|title|summary|description|assignee|reporter|creator|author|person)\b")

    def test_la_migration_reserve_sans_les_ecrire_le_cycle_la_file_prete_le_blocage_et_le_non_planifie(self):
        code = sans_commentaires(code_de())
        for table in ("ref_flow_statuses", "ref_unplanned_types", "ref_blocking_link_types"):
            self.assertIn(f"flow.{table}", code)                                   # les définitions se lisent dans le référentiel
        self.assertRegex(code, r"(?i)is_committed")
        self.assertRegex(code, r"(?i)is_ready_queue")
        self.assertNotRegex(code, r"(?i)'(in progress|to do|bug|defect|relates[^']*|blocked[^']*)'")   # aucun nom de statut, de type ni de lien écrit en dur
        self.assertNotRegex(code, r"(?i)\bepic\b")

    def test_la_non_planifie_est_au_niveau_du_produit_sans_colonne_d_equipe(self):
        code = sans_commentaires(code_de())
        corps = re.search(r"(?is)CREATE\s+VIEW\s+flow\.v_unplanned_share\s+AS(.*?);", code).group(1)
        self.assertNotRegex(corps, r"(?i)\bteam\b|flow\.teams|team_id")
        self.assertRegex(corps, r"(?i)ref_unplanned_types")

    def test_la_part_bloquee_lit_des_liens_d_une_autre_equipe_par_les_types_du_referentiel(self):
        code = sans_commentaires(code_de())
        corps = re.search(r"(?is)CREATE\s+VIEW\s+flow\.v_team_blocked_share\s+AS(.*?);\s*CREATE", code + "CREATE").group(1)
        self.assertRegex(corps, r"(?i)ref_blocking_link_types")
        self.assertRegex(corps, r"(?i)autre\.team_id\s*<>\s*d\.team_id")


class AvecBase(unittest.TestCase):
    """Même base jetable que SchemaFlow (migrations appliquées, base supprimée à la fin)."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def equipes(self, c):
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.teams (name) VALUES ('Alpha'), ('Beta'), ('Gamma')")
        c.execute("RESET ROLE")

    def ticket(self, c, cle, equipe, decalage=-3, type_="Story", jours=10, categorie="Done", resolu=True, sorti=False, parent=None):
        """Un ticket résolu au 40e jour du trimestre décalé de `decalage` mois, créé `jours` jours avant sa résolution."""
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, resolved_at, updated_at, team_id, "
                  "out_of_export_at, parent_key) "
                  "SELECT %s, 'PROJ', %s, 'Closed', %s, r - make_interval(days => %s), CASE WHEN %s THEN r END, now(), %s, CASE WHEN %s THEN now() END, %s "
                  "FROM (SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') + make_interval(months => %s) + interval '40 days') AT TIME ZONE 'UTC' AS r) x",
                  (cle, type_, categorie, jours, resolu, equipe, sorti, parent, decalage))
        c.execute("RESET ROLE")

    def lignes(self, c, vue, colonnes):
        c.commit()
        c.execute("SET ROLE pmzilla_flow_views")
        lignes = c.execute(f"SELECT {colonnes} FROM {vue}").fetchall()
        c.execute("RESET ROLE")
        return lignes

    def quarter(self, c, decalage):
        return c.execute("SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') + make_interval(months => %s))::date", (decalage,)).fetchone()[0]

    def remplir(self, c, equipe, n, decalage, prefixe, **kw):
        for i in range(n):
            self.ticket(c, f"{prefixe}-{decalage}-{i}", equipe, decalage=decalage, **kw)

    def test_debit_et_lead_time_par_equipe_et_trimestre_avec_annee_groupee(self):
        c = self.conn()
        self.equipes(c)
        for decalage in (-3, -6, -9):
            self.remplir(c, 1, 6, decalage, "A", jours=10)
        lignes = self.lignes(c, VUE_LT, "team, period, quarter_start, throughput, items_lt, lead_median_days, lead_p85_days")
        trimestres = [l for l in lignes if l[1] == "quarter"]
        self.assertEqual(len(trimestres), 3)
        for l in trimestres:
            self.assertEqual((l[0], l[3], l[4], float(l[5]), float(l[6])), ("Alpha", 6, 6, 10.0, 10.0))
        annee = [l for l in lignes if l[1] == "pooled_year"]
        self.assertEqual(len(annee), 1)
        # R-20261114-58 : trois trimestres de 6 éléments : la ligne groupée est la somme 6 + 6 + 6 = 18 (calcul à la main ; avant : 4 x 6 = 24)
        self.assertEqual((annee[0][0], annee[0][2], annee[0][3], annee[0][4], float(annee[0][5]), float(annee[0][6])), ("Alpha", None, 18, 18, 10.0, 10.0))

    def test_le_trimestre_en_cours_et_les_autres_types_n_ont_pas_de_ligne(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, 6, 0, "E")                               # trimestre en cours : jamais de ligne
        self.remplir(c, 1, 6, -3, "D", type_="Bug")                 # un défaut n'est pas du débit
        self.remplir(c, 1, 6, -3, "P", type_="Epic")
        self.remplir(c, 1, 6, -3, "O", categorie="To Do", resolu=False)
        self.remplir(c, 1, 6, -3, "S", sorti=True)
        self.assertEqual(self.lignes(c, VUE_LT, "team"), [])

    def test_sans_equipe_et_rattachement_par_lien_parent_ou_epic_comptent_pour_aucune_equipe(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, 6, -3, "A")                              # six stories de l'équipe Alpha
        self.ticket(c, "EPIC-1", 1, type_="Epic")
        self.remplir(c, None, 7, -3, "N", type_="Task", parent="EPIC-1")        # sept tâches sans équipe sous l'épic d'une équipe
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.links (source_key, target_key, link_type, direction) VALUES ('N-%s-0', 'A-%s-0', 'Relates', 'outward')" % (-3, -3))
        c.execute("RESET ROLE")
        lignes = self.lignes(c, VUE_LT, "team, period, throughput")
        self.assertEqual(sorted(lignes), [("Alpha", "pooled_year", 6), ("Alpha", "quarter", 6)])
        self.assertEqual(self.lignes(c, VUE_PART, "quarter_start, tasks_done, tasks_without_team, share_percent")[0][1:3], (7, None))      # sept tâches sans équipe, aucune avec équipe : sous le plancher, le nombre sans équipe est masqué

    def test_un_defaut_avec_equipe_n_est_pas_du_debit_et_un_defaut_sans_equipe_n_a_pas_de_ligne(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, 6, -3, "BA", type_="Bug")
        self.remplir(c, None, 6, -3, "BN", type_="Bug")
        self.assertEqual(self.lignes(c, VUE_LT, "team"), [])

    def test_masque_sous_le_plancher_effectif_et_statistiques(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 2, 3, -3, "B")
        lignes = self.lignes(c, VUE_LT, "team, period, throughput, items_lt, lead_median_days, lead_p85_days")
        self.assertEqual(len(lignes), 2)
        for l in lignes:
            self.assertEqual(l[2:], (None, None, None, None))

    def test_annee_groupee_masquee_quand_un_seul_trimestre_est_masque(self):
        c = self.conn()
        self.equipes(c)
        for decalage in (-3, -6):
            self.remplir(c, 1, 6, decalage, "A")
        self.remplir(c, 1, 3, -9, "A")                                # un trimestre masqué, l'année (6 + 6 + 3 = 15 ; avant 21) le redonnerait par différence
        lignes = self.lignes(c, VUE_LT, "period, quarter_start, throughput, items_lt, lead_median_days")
        annee = [l for l in lignes if l[0] == "pooled_year"][0]
        self.assertIsNone(annee[2])
        self.assertIsNone(annee[3])
        self.assertIsNotNone(annee[4])              # l'année a 15 lead times : sa médiane reste montrée
        masque = [l for l in lignes if l[0] == "quarter" and l[1] == self.quarter(c, -9)][0]
        self.assertEqual(masque[2:], (None, None, None))

    def test_annee_groupee_montree_quand_deux_trimestres_masques_font_au_moins_cinq(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, 6, -3, "A")
        self.remplir(c, 1, 3, -6, "A")
        self.remplir(c, 1, 3, -9, "A")
        annee = [l for l in self.lignes(c, VUE_LT, "period, throughput") if l[0] == "pooled_year"][0]
        self.assertEqual(annee[1], 12)                                # 6 + 3 + 3 = 12 (calcul à la main ; avant : 6 + 6 + 3 + 3 = 18) : les deux masqués font 6, au moins cinq

    def test_annee_groupee_masquee_quand_deux_trimestres_masques_font_moins_de_cinq(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, 6, -3, "A")
        self.remplir(c, 1, 2, -6, "A")
        self.remplir(c, 1, 2, -9, "A")
        annee = [l for l in self.lignes(c, VUE_LT, "period, throughput") if l[0] == "pooled_year"][0]
        self.assertIsNone(annee[1])

    def test_lead_time_ecarte_une_resolution_avant_la_creation_mais_le_debit_la_garde(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, 5, -3, "A")
        self.remplir(c, 1, 1, -3, "Z", jours=-2)
        ligne = self.lignes(c, VUE_LT, "throughput, items_lt, lead_median_days")[0]
        self.assertEqual(ligne[0], 6)
        self.assertIsNone(ligne[1])             # règle des paires : un seul item écarté se lirait par soustraction (6 - 5)
        self.assertIsNotNone(ligne[2])          # la médiane des cinq lead times reste montrée

    def test_part_des_taches_terminees_sans_equipe(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, 6, -3, "T", type_="Task")
        self.remplir(c, None, 6, -3, "U", type_="Task")
        self.remplir(c, None, 3, -6, "V", type_="Task")                # trimestre sous le plancher
        self.remplir(c, 1, 9, -6, "W", type_="Task")
        lignes = {l[0]: l for l in self.lignes(c, VUE_PART, "quarter_start, tasks_done, tasks_without_team, share_percent")}
        self.assertEqual(lignes[self.quarter(c, -3)][1:3], (12, 6))
        self.assertEqual(float(lignes[self.quarter(c, -3)][3]), 50.0)
        self.assertEqual(lignes[self.quarter(c, -6)][1:], (12, None, None))   # trois sans équipe : le nombre et la part sont masqués

    def test_part_masquee_quand_les_taches_avec_equipe_sont_sous_le_plancher(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, None, 8, -3, "U", type_="Task")
        self.remplir(c, 1, 3, -3, "T", type_="Task")
        self.assertEqual(self.lignes(c, VUE_PART, "tasks_done, tasks_without_team, share_percent"), [(11, None, None)])

    # --- référentiel des définitions (migration 0025) : noms inventés ---

    def definitions(self, c, statuts=(), types_non_planifies=(), types_liens=()):
        c.execute("SET ROLE pmzilla_flow")
        for statut, segment, engage, file_prete in statuts:
            c.execute("INSERT INTO flow.ref_flow_statuses (status, segment, is_committed, is_ready_queue) VALUES (%s, %s, %s, %s)",
                      (statut, segment, engage, file_prete))
        for type_ in types_non_planifies:
            c.execute("INSERT INTO flow.ref_unplanned_types (type, kind) VALUES (%s, 'defect')", (type_,))
        for type_, sens in types_liens:
            c.execute("INSERT INTO flow.ref_blocking_link_types (type, direction) VALUES (%s, %s)", (type_, sens))
        c.execute("RESET ROLE")

    def passage(self, c, cle, jours_avant_resolution, vers):
        """Un passage vers `vers`, `jours_avant_resolution` jours avant la résolution du ticket."""
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.transitions (issue_key, transitioned_at, from_status, to_status) "
                  "SELECT key, resolved_at - make_interval(days => %s), NULL, %s FROM flow.issues WHERE key = %s", (jours_avant_resolution, vers, cle))
        c.execute("RESET ROLE")

    def test_cycle_time_part_de_la_premiere_entree_dans_un_statut_engage_et_les_sans_engagement_sont_comptes_a_part(self):
        c = self.conn()
        self.equipes(c)
        self.definitions(c, statuts=[("SYN-pret", "ready", True, True), ("SYN-realisation", "implementation", False, False)])
        self.remplir(c, 1, 6, -3, "A", jours=20)
        for i in range(6):
            self.passage(c, f"A--3-{i}", 8, "SYN-realisation")        # un passage non engagé ne commence pas le cycle
            self.passage(c, f"A--3-{i}", 6, "SYN-pret")               # première entrée engagée : 6 jours avant la fin
            self.passage(c, f"A--3-{i}", 2, "SYN-pret")
        self.remplir(c, 1, 5, -6, "B", jours=20)                      # un trimestre sans engagement connu
        lignes = {l[0]: l for l in self.lignes(c, VUE_LT, "quarter_start, items_ct, cycle_median_days, cycle_p85_days, items_without_commitment, items_old")
                  if l[0] is not None}
        t3 = lignes[self.quarter(c, -3)]
        self.assertEqual((t3[1], float(t3[2]), float(t3[3]), t3[4], t3[5]), (6, 6.0, 6.0, 0, 0))   # zéro déductible (débit 6 = items_ct 6) : affiché par mask_count_zero, R-20261029-20 m1 ; items_old : aucun, zéro montré avec items_ct (R-20261106-39)
        t6 = lignes[self.quarter(c, -6)]
        self.assertEqual((t6[1], t6[2], t6[3], t6[4]), (None, None, None, 5))                          # cinq sans engagement : compte à part, aucun cycle time

    def test_un_ticket_cree_plus_d_un_an_avant_son_engagement_est_compte_a_part(self):
        c = self.conn()
        self.equipes(c)
        self.definitions(c, statuts=[("SYN-pret", "ready", True, True)])
        self.remplir(c, 1, 11, -3, "A", jours=500)
        for i in range(11):
            self.passage(c, f"A--3-{i}", 5, "SYN-pret")
        ligne = self.lignes(c, VUE_LT, "items_ct, items_old")[0]
        self.assertEqual(ligne, (11, 11))

    def test_sans_referentiel_aucun_cycle_time(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, 6, -3, "A")
        ligne = self.lignes(c, VUE_LT, "throughput, items_ct, cycle_median_days, items_without_commitment")[0]
        self.assertEqual(ligne, (6, None, None, 6))

    def test_file_prete_lue_a_la_fin_du_trimestre_clos(self):
        c = self.conn()
        self.equipes(c)
        self.definitions(c, statuts=[("SYN-pret", "ready", True, True), ("SYN-realisation", "implementation", False, False)])
        for i in range(6):                                                              # prêts à la fin du trimestre -3, terminés le trimestre suivant
            self.ticket(c, f"R-{i}", 1, decalage=0, jours=60)
            c.execute("SET ROLE pmzilla_flow")
            c.execute("INSERT INTO flow.transitions (issue_key, transitioned_at, to_status) "
                      "SELECT key, (date_trunc('quarter', now() AT TIME ZONE 'UTC') - interval '10 days') AT TIME ZONE 'UTC', 'SYN-pret' FROM flow.issues WHERE key = %s", (f"R-{i}",))
            c.execute("RESET ROLE")
        for i in range(6):                                                              # déjà en réalisation à la fin du trimestre
            self.ticket(c, f"Q-{i}", 1, decalage=0, jours=60)
            c.execute("SET ROLE pmzilla_flow")
            c.execute("INSERT INTO flow.transitions (issue_key, transitioned_at, to_status) "
                      "SELECT key, (date_trunc('quarter', now() AT TIME ZONE 'UTC') - interval '10 days') AT TIME ZONE 'UTC', 'SYN-pret' FROM flow.issues WHERE key = %s", (f"Q-{i}",))
            c.execute("INSERT INTO flow.transitions (issue_key, transitioned_at, to_status) "
                      "SELECT key, (date_trunc('quarter', now() AT TIME ZONE 'UTC') - interval '5 days') AT TIME ZONE 'UTC', 'SYN-realisation' FROM flow.issues WHERE key = %s", (f"Q-{i}",))
            c.execute("RESET ROLE")
        # ces tickets sont résolus le 40e jour du trimestre en cours : ils étaient ouverts à la fin du trimestre précédent
        lignes = self.lignes(c, VUE_FILE, "team, quarter_start, ready")
        self.assertEqual(lignes, [("Alpha", self.quarter(c, -3), 6)])

    def test_part_bloquee_lien_entrant_d_un_type_bloquant_depuis_une_autre_equipe(self):
        c = self.conn()
        self.equipes(c)
        self.definitions(c, types_liens=[("SYN-lien-bloque", "blocks")])
        self.remplir(c, 1, 12, -3, "A")
        self.remplir(c, 2, 12, -3, "B")
        c.execute("SET ROLE pmzilla_flow")
        for i in range(6):                  # six items d'Alpha bloqués par un item de Beta
            c.execute("INSERT INTO flow.links (source_key, target_key, link_type, direction) VALUES (%s, %s, 'SYN-lien-bloque', 'outward')",
                      (f"B--3-{i}", f"A--3-{i}"))
        c.execute("INSERT INTO flow.links (source_key, target_key, link_type, direction) VALUES ('A--3-6', 'A--3-7', 'SYN-lien-bloque', 'outward')")   # même équipe
        c.execute("INSERT INTO flow.links (source_key, target_key, link_type, direction) VALUES ('B--3-6', 'A--3-8', 'SYN-autre-lien', 'outward')")     # type non bloquant
        c.execute("RESET ROLE")
        lignes = {l[0]: l for l in self.lignes(c, VUE_BLOQUE, "team, blocked_n, blocked, share_percent")}
        self.assertEqual((lignes["Alpha"][1], lignes["Alpha"][2], float(lignes["Alpha"][3])), (12, 6, 50.0))
        self.assertEqual(lignes["Beta"][1:], (12, None, None))          # aucun bloqué : zéro, sous le plancher

    def test_non_planifie_au_niveau_du_produit_defauts_sans_equipe_compris(self):
        c = self.conn()
        self.equipes(c)
        self.definitions(c, types_non_planifies=["SYN-type-defaut"])
        self.remplir(c, 1, 6, -3, "A")
        self.remplir(c, None, 3, -3, "D", type_="SYN-type-defaut")
        self.remplir(c, 1, 3, -3, "E", type_="SYN-type-defaut")          # défaut rattaché à une équipe : compté au produit, jamais par équipe
        colonnes = {r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'flow' AND table_name = 'v_unplanned_share'")}
        self.assertEqual(colonnes, {"quarter_start", "unplanned_n", "unplanned", "share_percent"})
        ligne = self.lignes(c, VUE_NON_PLANIFIE, "unplanned_n, unplanned, share_percent")[0]
        self.assertEqual((ligne[0], ligne[1], float(ligne[2])), (12, 6, 50.0))

    # --- revue du 2026-10-29 (R-20261029-20) : année groupée sur les cellules affichées, paires, part bloquée ---

    STATUT_PRET = ("SYN-pret", "ready", True, True)

    def cohorte(self, c, equipe, decalage, prefixe, avec, sans, anciens=0, jours=20):
        """`avec` tickets engagés (passage dans le statut prêt 5 jours avant la fin), dont `anciens` créés plus d'un an avant, et `sans` sans engagement."""
        self.remplir(c, equipe, avec - anciens, decalage, prefixe + "v", jours=jours)
        self.remplir(c, equipe, anciens, decalage, prefixe + "o", jours=500)
        self.remplir(c, equipe, sans, decalage, prefixe + "s", jours=jours)
        for i in range(avec - anciens):
            self.passage(c, f"{prefixe}v-{decalage}-{i}", 5, "SYN-pret")
        for i in range(anciens):
            self.passage(c, f"{prefixe}o-{decalage}-{i}", 5, "SYN-pret")

    def annee(self, c, colonnes):
        return [l for l in self.lignes(c, VUE_LT, f"period, {colonnes}") if l[0] == "pooled_year"][0][1:]

    def trimestre(self, c, decalage, colonnes):
        return [l for l in self.lignes(c, VUE_LT, f"quarter_start, {colonnes}") if l[0] == self.quarter(c, decalage)][0][1:]

    def test_b1_exemple_de_la_revue_g_3_6_0_0_et_c_20_masque_30_30_30(self):
        c = self.conn()
        self.equipes(c)
        self.definitions(c, statuts=[self.STATUT_PRET])
        for decalage, avec, sans in ((-9, 20, 3), (-6, 30, 6), (-3, 30, 0)):
            self.cohorte(c, 1, decalage, "A", avec, sans)
        self.assertEqual(self.trimestre(c, -9, "items_ct, items_without_commitment"), (None, None))      # c masqué par la paire (g = 3), g masqué sous 5
        self.assertEqual(self.trimestre(c, -6, "items_ct, items_without_commitment"), (30, 6))
        self.assertEqual(self.trimestre(c, -3, "items_ct, items_without_commitment"), (30, 0))           # zéro déductible : affiché, non masqué
        # l'année redonnerait c(-9) = 80 - 60 et g(-9) = 9 - 6 : une seule cellule masquée dans chaque série
        # R-20261114-58, calcul à la main : débit de l'année 23 + 36 + 30 = 89 (avant : 23 + 36 + 30 + 30 = 119) ; c : 20 + 30 + 30 = 80 ; g : 3 + 6 + 0 = 9
        self.assertEqual(self.annee(c, "throughput, items_ct, items_without_commitment"), (89, None, None))

    def test_b1_items_lt_une_cellule_masquee_par_la_paire_bien_que_superieure_a_cinq(self):
        c = self.conn()
        self.equipes(c)
        self.remplir(c, 1, 9, -9, "P")
        self.remplir(c, 1, 1, -9, "Z", jours=-3)                       # m = 9 sur n = 10 : masqué par la paire
        for decalage in (-6, -3):
            self.remplir(c, 1, 30, decalage, "A")
        self.assertIsNone(self.trimestre(c, -9, "items_lt")[0])
        self.assertEqual(self.annee(c, "throughput, items_lt")[0], 70)   # R-20261114-58, à la main : 10 + 30 + 30 = 70 (avant : 10 + 90 = 100)
        self.assertIsNone(self.annee(c, "throughput, items_lt")[1])    # 69 (9 + 30 + 30) : le trimestre masqué se déduirait de l'année et des visibles

    def test_b1_items_old_et_m1_pas_d_anciens_sans_items_ct(self):
        c = self.conn()
        self.equipes(c)
        self.definitions(c, statuts=[self.STATUT_PRET])
        self.cohorte(c, 1, -9, "A", 20, 3, anciens=20)                   # items_ct masqué (g = 3) : items_old doit l'être aussi (M1)
        for decalage in (-6, -3):
            self.cohorte(c, 1, decalage, "B", 30, 0, anciens=30)
        self.assertEqual(self.trimestre(c, -9, "items_ct, items_old"), (None, None))
        self.assertEqual(self.trimestre(c, -6, "items_ct, items_old"), (30, 30))

    def test_b1_items_old_masque_par_la_paire_rend_l_annee_masquee(self):
        c = self.conn()
        self.equipes(c)
        self.definitions(c, statuts=[self.STATUT_PRET])
        self.cohorte(c, 1, -9, "A", 20, 0, anciens=17)                   # c - o = 3 : items_old masqué par la paire bien que o >= 5
        for decalage in (-6, -3):
            self.cohorte(c, 1, decalage, "B", 30, 0, anciens=30)
        self.assertIsNone(self.trimestre(c, -9, "items_old")[0])
        self.assertIsNone(self.annee(c, "items_old")[0])

    def test_m2_items_ct_controle_contre_items_lt(self):
        c = self.conn()
        self.equipes(c)
        self.definitions(c, statuts=[self.STATUT_PRET])
        self.remplir(c, 1, 14, -3, "V", jours=20)
        for i in range(14):
            self.passage(c, f"V--3-{i}", 5, "SYN-pret")
        self.remplir(c, 1, 5, -3, "B", jours=-3)                        # cinq résolus avant leur création, sans engagement
        self.remplir(c, 1, 1, -3, "S", jours=20)                        # un sans engagement
        # n = 20, m = 15 (n - m = 5), c = 14, g = 6 : |m - c| = 1, la paire (m, c) masque items_ct
        self.assertEqual(self.trimestre(c, -3, "throughput, items_lt, items_ct"), (20, 15, None))

    def test_m5_part_bloquee_sens_des_liens_et_cas_exclus(self):
        c = self.conn()
        self.equipes(c)
        self.definitions(c, types_liens=[("SYN-lien-bloque", "blocks"), ("SYN-lien-attend", "waits_for")])
        self.remplir(c, 1, 30, -3, "A")
        self.remplir(c, 2, 30, -3, "B")
        c.execute("SET ROLE pmzilla_flow")
        sql = "INSERT INTO flow.links (source_key, target_key, link_type, direction) VALUES (%s, %s, %s, %s)"
        for i in range(0, 5):               # blocks entrant, enregistré du côté du bloqué : source = le bloqué, direction inward
            c.execute(sql, (f"A--3-{i}", f"B--3-{i}", "SYN-lien-bloque", "inward"))
        for i in range(5, 10):              # waits_for : le bloqué dépend de l'autre (sortant de son côté)
            c.execute(sql, (f"A--3-{i}", f"B--3-{i}", "SYN-lien-attend", "outward"))
        for i in range(10, 15):             # waits_for, enregistré du côté de l'autre (entrant)
            c.execute(sql, (f"B--3-{i}", f"A--3-{i}", "SYN-lien-attend", "inward"))
        for i in range(15, 20):             # direction nulle : non lue
            c.execute(sql, (f"B--3-{i}", f"A--3-{i}", "SYN-lien-bloque", None))
        for i in range(20, 25):             # blocks sortant de l'autre équipe : A--3-i est bloqué ; B--3-i, l'élément bloquant, ne l'est pas
            c.execute(sql, (f"B--3-{i}", f"A--3-{i}", "SYN-lien-bloque", "outward"))
        c.execute("RESET ROLE")
        lignes = {l[0]: l for l in self.lignes(c, VUE_BLOQUE, "team, blocked_n, blocked, share_percent")}
        self.assertEqual((lignes["Alpha"][1], lignes["Alpha"][2], float(lignes["Alpha"][3])), (30, 20, 66.7))
        self.assertEqual(lignes["Beta"][1:], (30, None, None))           # les éléments bloquants ne sont pas comptés bloqués

    def test_m5_deux_de_la_meme_equipe_et_equipe_inconnue_ne_bloquent_pas(self):
        c = self.conn()
        self.equipes(c)
        self.definitions(c, types_liens=[("SYN-lien-bloque", "blocks")])
        self.remplir(c, 1, 12, -3, "A")
        self.remplir(c, None, 12, -3, "N")
        c.execute("SET ROLE pmzilla_flow")
        for i in range(6):
            c.execute("INSERT INTO flow.links (source_key, target_key, link_type, direction) VALUES (%s, %s, 'SYN-lien-bloque', 'outward')",
                      (f"N--3-{i}", f"A--3-{i}"))                    # le bloquant n'a pas d'équipe connue : pas une autre équipe
        c.execute("RESET ROLE")
        self.assertEqual(self.lignes(c, VUE_BLOQUE, "team, blocked_n, blocked")[0], ("Alpha", 12, None))

    # --- migration 0029 (décision R-20261030-08) : tasks_without_team, blocked et unplanned passent par flow.mask_count, jamais plus permissifs ---

    # Un cas par trimestre clos (décalages -3, -6, -9) dans une même base : trois cas au plus par test (R-20261114-58 : le quatrième cas de chaque test
    # est joué par un test neuf, « …_quatrieme_cas_de_… », au décalage -3).
    DECALAGES = (-3, -6, -9)

    def vue_au_seuil(self, c, vue, colonnes, seuil, filtre=""):
        """Lignes de la vue sous le rôle des vues, puis cellules de masquer_vue au seuil donné (lecteur de tools/flow_views.py)."""
        import flow_views as fv
        c.commit()
        c.execute("SET ROLE pmzilla_flow_views")
        curseur = c.execute(f"SELECT {colonnes} FROM {vue} {filtre}")
        noms, lignes = [d.name for d in curseur.description], curseur.fetchall()
        c.execute("RESET ROLE")
        return noms, lignes, fv.masquer_vue(vue.split(".")[1], noms, lignes, seuil)

    def bloques(self, c, cas):
        """Alpha : par cas (bloqués, restes) et par trimestre, `bloqués` éléments bloqués par un élément de Beta et `restes` non bloqués."""
        self.equipes(c)
        self.definitions(c, types_liens=[("SYN-lien-bloque", "blocks")])
        for decalage, (bloques, restes) in zip(self.DECALAGES, cas):
            self.remplir(c, 1, bloques + restes, decalage, "A")
            self.remplir(c, 2, bloques, decalage, "B")
            c.execute("SET ROLE pmzilla_flow")
            for i in range(bloques):
                c.execute("INSERT INTO flow.links (source_key, target_key, link_type, direction) VALUES (%s, %s, 'SYN-lien-bloque', 'outward')",
                          (f"B-{decalage}-{i}", f"A-{decalage}-{i}"))
            c.execute("RESET ROLE")
        lignes = self.lignes(c, VUE_BLOQUE, "team, quarter_start, blocked_n, blocked, share_percent")
        return [[l for l in lignes if l[0] == "Alpha" and l[1] == self.quarter(c, d)][0][2:] for d in self.DECALAGES[:len(cas)]]

    def test_0029_bloques_juste_sous_et_au_plancher_et_reste_juste_sous_le_plancher(self):
        c = self.conn()
        cas = ((4, 10), (5, 10), (10, 4))
        attendus = (None, 5, None)
        parts = (False, True, False)
        for (bloques, restes), ligne, attendu, part in zip(cas, self.bloques(c, cas), attendus, parts):
            self.assertEqual((ligne[0], ligne[1], ligne[2] is not None), (bloques + restes, attendu, part), (bloques, restes))

    def test_0029_bloques_juste_sous_et_au_plancher_quatrieme_cas_de_test_0029_bloques_juste_sous_et_au_plancher_et_reste_juste_sous_le_plancher(self):
        """Le quatrième cas du test d'origine (reste juste AU plancher : 10 bloqués, 5 restes), même aide, même borne et même attendu (compte bloqué 10, part
        montrée) ; seul son trimestre change (-3 au lieu de -12)."""
        c = self.conn()
        cas = ((10, 5),)
        attendus = (10,)
        parts = (True,)
        for (bloques, restes), ligne, attendu, part in zip(cas, self.bloques(c, cas), attendus, parts):
            self.assertEqual((ligne[0], ligne[1], ligne[2] is not None), (bloques + restes, attendu, part), (bloques, restes))

    def test_0029_bloques_au_seuil_releve_a_10_cinq_a_neuf_jamais_lisible_en_direct_ni_dans_la_part(self):
        c = self.conn()
        self.bloques(c, ((7, 20), (20, 7), (9, 20)))
        _, _, cellules = self.vue_au_seuil(c, VUE_BLOQUE, "team, quarter_start, blocked_n, blocked, share_percent", 10, "WHERE team = 'Alpha'")
        self.assertEqual(len(cellules), 3)
        for ligne in cellules:
            self.assertIn("masked", ligne["blocked"])
            self.assertIn("masked", ligne["share_percent"])

    def test_0029_bloques_au_seuil_releve_a_10_quatrieme_cas_de_test_0029_bloques_au_seuil_releve_a_10_cinq_a_neuf_jamais_lisible_en_direct_ni_dans_la_part(self):
        """Le quatrième cas du test d'origine : (20, 9), au décalage -3 au lieu de -12 ; même borne (9 sous le seuil relevé de 10), même attendu (masqué)."""
        c = self.conn()
        self.bloques(c, ((20, 9),))
        _, _, cellules = self.vue_au_seuil(c, VUE_BLOQUE, "team, quarter_start, blocked_n, blocked, share_percent", 10, "WHERE team = 'Alpha'")
        self.assertEqual(len(cellules), 1)
        for ligne in cellules:
            self.assertIn("masked", ligne["blocked"])
            self.assertIn("masked", ligne["share_percent"])

    def taches(self, c, cas):
        self.equipes(c)
        for decalage, (sans, avec) in zip(self.DECALAGES, cas):
            self.remplir(c, None, sans, decalage, "U", type_="Task")
            self.remplir(c, 1, avec, decalage, "T", type_="Task")
        lignes = self.lignes(c, VUE_PART, "quarter_start, tasks_done, tasks_without_team, share_percent")
        return [[l for l in lignes if l[0] == self.quarter(c, d)][0][1:] for d in self.DECALAGES[:len(cas)]]

    def test_0029_taches_sans_equipe_juste_sous_et_au_plancher_et_reste_juste_sous_le_plancher(self):
        c = self.conn()
        cas = ((4, 10), (5, 10), (10, 4))
        attendus = (None, 5, None)
        parts = (False, True, False)
        for (sans, avec), ligne, attendu, part in zip(cas, self.taches(c, cas), attendus, parts):
            self.assertEqual((ligne[0], ligne[1], ligne[2] is not None), (sans + avec, attendu, part), (sans, avec))

    def test_0029_taches_sans_equipe_quatrieme_cas_de_test_0029_taches_sans_equipe_juste_sous_et_au_plancher_et_reste_juste_sous_le_plancher(self):
        """Le quatrième cas du test d'origine : (10, 5), même aide, même borne (reste au plancher) et même attendu (compte 10, part montrée) ; trimestre -3 au lieu de -12."""
        c = self.conn()
        cas = ((10, 5),)
        attendus = (10,)
        parts = (True,)
        for (sans, avec), ligne, attendu, part in zip(cas, self.taches(c, cas), attendus, parts):
            self.assertEqual((ligne[0], ligne[1], ligne[2] is not None), (sans + avec, attendu, part), (sans, avec))

    def test_0029_taches_sans_equipe_au_seuil_releve_a_10_cinq_a_neuf_jamais_lisible(self):
        c = self.conn()
        self.taches(c, ((7, 20), (20, 7), (9, 20)))
        _, _, cellules = self.vue_au_seuil(c, VUE_PART, "quarter_start, tasks_done, tasks_without_team, share_percent", 10)
        self.assertEqual(len(cellules), 3)
        for ligne in cellules:
            self.assertIn("masked", ligne["tasks_without_team"])
            self.assertIn("masked", ligne["share_percent"])

    def test_0029_taches_sans_equipe_au_seuil_releve_a_10_quatrieme_cas_de_test_0029_taches_sans_equipe_au_seuil_releve_a_10_cinq_a_neuf_jamais_lisible(self):
        """Le quatrième cas du test d'origine : (20, 9), même borne (9 sous le seuil relevé de 10), même attendu (masqué) ; trimestre -3 au lieu de -12."""
        c = self.conn()
        self.taches(c, ((20, 9),))
        _, _, cellules = self.vue_au_seuil(c, VUE_PART, "quarter_start, tasks_done, tasks_without_team, share_percent", 10)
        self.assertEqual(len(cellules), 1)
        for ligne in cellules:
            self.assertIn("masked", ligne["tasks_without_team"])
            self.assertIn("masked", ligne["share_percent"])

    def non_planifies(self, c, cas):
        self.equipes(c)
        self.definitions(c, types_non_planifies=["SYN-type-defaut"])
        for decalage, (non_planifies, restes) in zip(self.DECALAGES, cas):
            self.remplir(c, 1, restes, decalage, "A")
            self.remplir(c, None, non_planifies, decalage, "D", type_="SYN-type-defaut")
        lignes = self.lignes(c, VUE_NON_PLANIFIE, "quarter_start, unplanned_n, unplanned, share_percent")
        return [[l for l in lignes if l[0] == self.quarter(c, d)][0][1:] for d in self.DECALAGES[:len(cas)]]

    def test_0029_non_planifies_juste_sous_et_au_plancher_et_reste_juste_sous_le_plancher(self):
        c = self.conn()
        cas = ((4, 10), (5, 10), (10, 4))
        attendus = (None, 5, None)
        parts = (False, True, False)
        for (non_planifies, restes), ligne, attendu, part in zip(cas, self.non_planifies(c, cas), attendus, parts):
            self.assertEqual((ligne[0], ligne[1], ligne[2] is not None), (non_planifies + restes, attendu, part), (non_planifies, restes))

    def test_0029_non_planifies_quatrieme_cas_de_test_0029_non_planifies_juste_sous_et_au_plancher_et_reste_juste_sous_le_plancher(self):
        """Le quatrième cas du test d'origine : (10, 5), même aide, même borne (reste au plancher) et même attendu (compte 10, part montrée) ; trimestre -3 au lieu de -12."""
        c = self.conn()
        cas = ((10, 5),)
        attendus = (10,)
        parts = (True,)
        for (non_planifies, restes), ligne, attendu, part in zip(cas, self.non_planifies(c, cas), attendus, parts):
            self.assertEqual((ligne[0], ligne[1], ligne[2] is not None), (non_planifies + restes, attendu, part), (non_planifies, restes))

    def test_0029_non_planifies_au_seuil_releve_a_10_cinq_a_neuf_jamais_lisible(self):
        c = self.conn()
        self.non_planifies(c, ((7, 20), (20, 7), (9, 20)))
        _, _, cellules = self.vue_au_seuil(c, VUE_NON_PLANIFIE, "quarter_start, unplanned_n, unplanned, share_percent", 10)
        self.assertEqual(len(cellules), 3)
        for ligne in cellules:
            self.assertIn("masked", ligne["unplanned"])
            self.assertIn("masked", ligne["share_percent"])

    def test_0029_non_planifies_au_seuil_releve_a_10_quatrieme_cas_de_test_0029_non_planifies_au_seuil_releve_a_10_cinq_a_neuf_jamais_lisible(self):
        """Le quatrième cas du test d'origine : (20, 9), même borne (9 sous le seuil relevé de 10), même attendu (masqué) ; trimestre -3 au lieu de -12."""
        c = self.conn()
        self.non_planifies(c, ((20, 9),))
        _, _, cellules = self.vue_au_seuil(c, VUE_NON_PLANIFIE, "quarter_start, unplanned_n, unplanned, share_percent", 10)
        self.assertEqual(len(cellules), 1)
        for ligne in cellules:
            self.assertIn("masked", ligne["unplanned"])
            self.assertIn("masked", ligne["share_percent"])

    def test_0029_debit_au_seuil_releve_a_10_n_20_c_12_g_8_items_ct_et_g_masques(self):
        """Revue 15.2 : la vue du débit lue sous le rôle des vues puis passée à masquer_vue au seuil 10 : 20 - 12 = 8 ne doit pas se lire."""
        c = self.conn()
        self.equipes(c)
        self.definitions(c, statuts=[self.STATUT_PRET])
        self.cohorte(c, 1, -3, "A", 12, 8)                        # n = 20, c = 12, g = 8
        noms, lignes, cellules = self.vue_au_seuil(c, VUE_LT, "*", 10)
        i = [k for k, l in enumerate(lignes) if l[noms.index("period")] == "quarter"][0]
        self.assertEqual(cellules[i]["throughput"], {"value": 20})
        self.assertIn("masked", cellules[i]["items_ct"])
        self.assertIn("masked", cellules[i]["items_without_commitment"])
        self.assertIn("masked", cellules[i]["cycle_median_days"])

    def test_le_role_des_vues_lit_les_cinq_vues_et_aucune_table(self):
        c = self.conn()
        for vue in (VUE_LT, VUE_PART, VUE_FILE, VUE_BLOQUE, VUE_NON_PLANIFIE):
            self.assertTrue(self.essaie(c, "pmzilla_flow_views", f"SELECT * FROM {vue}"), vue)
            for role in ("pmzilla_flow", "pmzilla_flow_ro", "pmzilla_quality_views"):
                self.assertFalse(self.essaie(c, role, f"SELECT * FROM {vue}"), (vue, role))
        self.assertFalse(self.essaie(c, "pmzilla_flow_views", "SELECT * FROM flow.issues"))


if __name__ == "__main__":
    unittest.main()
