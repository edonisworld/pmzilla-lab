"""La vue v_team_flow_inout (change mothra-slices, tâche 36.1, exception F12, conception D35 ; plan R-150, décisions R-20261031-01 Q1 A et Q2 A ;
spec jira-flow-views « Created and done items per team and closed quarter for the product scope »).

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Les tests sans base (SansBase) lisent le fichier de migration, retrouvé par sa description et non par son numéro ; la partie sans base passe par
`bash tests/run_all.sh db`. Les tests avec base (AvecBase) sont pour le dbtest de l'auteur (bash tools/dbtest.sh db) : base jetable, données inventées,
rôle des vues. Ils chargent le jeu synthétique des panneaux (tests/mothra_donnees/panneaux_r150.py) et en comparent les comptes attendus aux cellules.
"""
import re
import sys
import unittest
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mothra_donnees"))

SUFFIXE = "_flow_team_flow_inout.sql"
VUE = "flow.v_team_flow_inout"
SANS_EQUIPE = "(sans équipe)"
PRODUIT = "(produit)"
PLANCHER = 5


def code_de():
    candidats = [m for m in db.lister_migrations() if m.nom.endswith(SUFFIXE)]
    assert len(candidats) == 1, f"une migration *{SUFFIXE} est attendue"
    return candidats[0].chemin.read_text(encoding="utf-8")


def sans_commentaires(texte):
    return re.sub(r"--[^\n]*", "", texte)


class SansBase(unittest.TestCase):
    def test_une_vue_sous_le_proprietaire_sans_donnee_ni_table(self):
        texte = code_de()
        code = sans_commentaires(texte)
        self.assertRegex(texte.splitlines()[0], r"^-- Schéma touché : flow")
        self.assertEqual(re.findall(r"(?i)\bCREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+flow\.(\w+)", code), ["v_team_flow_inout"])
        self.assertLess(re.search(r"(?i)SET\s+LOCAL\s+ROLE\s+pmzilla_owner", code).start(), re.search(r"(?i)CREATE\s+VIEW", code).start())
        self.assertNotRegex(code, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(code, r"(?i)\bPASSWORD\b|\b(CREATE|ALTER|DROP)\s+(ROLE|TABLE)\b|\bLOGIN\b")

    def test_select_au_seul_role_des_vues(self):
        code = sans_commentaires(code_de())
        self.assertEqual(len(re.findall(r"(?i)\bGRANT\b", code)), 1)
        self.assertRegex(code, r"(?is)GRANT\s+SELECT\s+ON\s+flow\.v_team_flow_inout\s+TO\s+pmzilla_flow_views\s*;")
        revoke = re.search(r"(?is)\bREVOKE\b.*?;", code)
        for role in ("PUBLIC", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_quality_views"):
            self.assertRegex(revoke.group(0), rf"\b{role}\b")
        self.assertLess(code.index("REVOKE"), code.index("GRANT"))

    def test_le_numero_est_superieur_a_0029_et_la_migration_se_retrouve_par_son_suffixe(self):
        numeros = {m.nom.split("_", 1)[1]: m.numero for m in db.lister_migrations()}
        self.assertIn(SUFFIXE.lstrip("_"), numeros)
        self.assertGreater(numeros[SUFFIXE.lstrip("_")], numeros["flow_slice1_mask_comptes.sql"])


class AvecBase(unittest.TestCase):
    """Même base jetable que SchemaFlow (migrations appliquées, base supprimée à la fin)."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def charger_panneaux(self, c):
        import jeu_synthetique as jeu
        import panneaux_r150 as pan
        maintenant = datetime.now(timezone.utc)
        c.execute("SET ROLE pmzilla_flow")
        for type_ in (jeu.TYPE_DEFAUT,):
            c.execute("INSERT INTO flow.ref_unplanned_types (type, kind) VALUES (%s, 'defect')", (type_,))
        c.execute("RESET ROLE")
        c.commit()
        jeu.charger(c, maintenant, supplement=pan.supplement(maintenant))
        return pan

    def lire(self, c, colonnes="team, quarter_start, type_group, created, done"):
        c.commit()
        c.execute("SET ROLE pmzilla_flow_views")
        lignes = c.execute(f"SELECT {colonnes} FROM {VUE}").fetchall()
        c.execute("RESET ROLE")
        return lignes

    def trimestre(self, c, k):
        """Début du trimestre clos d'indice k (0 : le dernier clos)."""
        return c.execute("SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') - make_interval(months => 3 * (%s + 1)))::date", (k,)).fetchone()[0]

    # --- attendus du jeu synthétique ---

    @staticmethod
    def contribution_projets_exclus(pan, jeu):
        """Créés et finis des éléments d'un projet exclu (stories et défauts), que la vue ne sait pas retirer : voir le point arrêté de la migration."""
        cree, fini = defaultdict(int), defaultdict(int)
        for equipe, type_, projet, kc, kd, nombre in pan.EXCLUS:
            if projet not in pan.PROJETS_EXCLUS:
                continue
            g = "story" if type_ == pan.TYPE_HISTOIRE else ("defect" if type_ == jeu.TYPE_DEFAUT else None)
            if g is None:
                continue
            if isinstance(kc, int) and 0 <= kc <= 3:
                cree[(equipe, g, kc)] += nombre
            if isinstance(kd, int) and 0 <= kd <= 3:
                fini[(equipe, g, kd)] += nombre
        return cree, fini

    def attendus(self, pan, jeu, avec_projets_exclus):
        cree, fini = defaultdict(int, pan.CREES_ATTENDUS), defaultdict(int, pan.TERMINES_ATTENDUS)
        for (equipe, k), n in pan.CREES_TACHES.items():          # Q2 A : le groupe `story` couvre Story et Task
            cree[(equipe, "story", k)] += n
        for (equipe, k), n in pan.TERMINES_TACHES.items():
            fini[(equipe, "story", k)] += n
        if avec_projets_exclus:
            c_exc, f_exc = self.contribution_projets_exclus(pan, jeu)
            for cle, n in c_exc.items():
                cree[cle] += n
            for cle, n in f_exc.items():
                fini[cle] += n
        return cree, fini

    def cellules(self, c):
        """{(équipe ou None, groupe, k): (créés, finis)} lus dans la vue, masque conservé (None) ; la ligne du produit sous l'équipe PRODUIT."""
        resultat = {}
        for equipe, trimestre, groupe, cree, fini in self.lire(c):
            k = next(k for k in range(3) if self.trimestre(c, k) == trimestre)          # R-20261114-58 : trois trimestres clos (k = 0 à 2)
            resultat[(None if equipe == SANS_EQUIPE else equipe, groupe, k)] = (cree, fini)
        return resultat

    def test_les_comptes_du_jeu_des_panneaux_sont_ceux_de_la_vue_masques_sous_cinq(self):
        import jeu_synthetique as jeu
        c = self.conn()
        pan = self.charger_panneaux(c)
        cree, fini = self.attendus(pan, jeu, avec_projets_exclus=True)       # les projets exclus ne sont pas retirés : point arrêté, voir l'en-tête de la migration
        lues = self.cellules(c)
        equipes_du_jeu = {e for e, _, _ in list(cree) + list(fini)}
        for (equipe, groupe, k), (c_lu, f_lu) in lues.items():
            if equipe in (PRODUIT, None) or equipe not in equipes_du_jeu:      # la ligne sans équipe mêle les jeux des tranches 0 et 1 : comparée à part, plus bas
                continue
            attendu_c, attendu_f = cree.get((equipe, groupe, k), 0), fini.get((equipe, groupe, k), 0)
            self.assertEqual(c_lu, attendu_c if attendu_c >= PLANCHER else None, (equipe, groupe, k, "created"))
            self.assertEqual(f_lu, attendu_f if attendu_f >= PLANCHER else None, (equipe, groupe, k, "done"))

    def test_les_taches_du_jeu_comptent_dans_le_groupe_story_et_font_franchir_le_plancher(self):
        """Équipe W, trimestre 2 : 4 stories et 1 tâche, soit 5 créés et 5 finis, rendus ; équipe W2 (R-20261114-79, avant : équipe W, trimestre 3, hors de la
        fenêtre de trois), trimestre 1 : 1 story et 2 tâches, soit 1 + 2 = 3 créés et 1 + 2 = 3 finis (calcul à la main), sous 5 : masqués."""
        c = self.conn()
        pan = self.charger_panneaux(c)
        lues = self.cellules(c)
        self.assertEqual(lues[(pan.TEMOIN_PETIT, "story", 2)], (5, 5))
        self.assertEqual(lues[(pan.TEMOIN_TACHES, "story", 1)], (None, None))

    @unittest.expectedFailure
    def test_les_projets_exclus_des_rapports_de_flux_sont_retires_OUVERT(self):
        """Point arrêté de la tâche 36.1 : la base ne porte aucune liste des projets exclus (réglage de flux.yaml) ; la vue ne peut pas les retirer. Ce test
        passera quand la table ref_excluded_projects existera : décision de l'auteur R-20261031-27 Q56, change séparé, en place avant toute publication
        de comptes réels. Il cherche la fuite, il ne l'évite pas. (Q57 : T13 passe en priorité au groupe 7 de masking-sums ; la précaution de Q33 vaut aussi
        pour cette vue.)"""
        import jeu_synthetique as jeu
        c = self.conn()
        pan = self.charger_panneaux(c)
        cree, fini = self.attendus(pan, jeu, avec_projets_exclus=False)
        lues = self.cellules(c)
        for (equipe, groupe, k), (c_lu, f_lu) in lues.items():
            if equipe in (PRODUIT, None):
                continue
            attendu_c, attendu_f = cree.get((equipe, groupe, k), 0), fini.get((equipe, groupe, k), 0)
            self.assertEqual(c_lu, attendu_c if attendu_c >= PLANCHER else None, (equipe, groupe, k, "created"))
            self.assertEqual(f_lu, attendu_f if attendu_f >= PLANCHER else None, (equipe, groupe, k, "done"))

    def test_masquer_vue_au_plancher_ne_masque_rien_de_plus_que_la_vue(self):
        """Les lignes publiées par la vue passent dans masquer_vue (fonction de service Python) au plancher : une cellule que la vue montre reste montrée,
        et une cellule que la vue masque (NULL) reste masquée. Parité SQL/Python de la vue, sur le jeu des panneaux."""
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
        import flow_views as fv
        c = self.conn()
        self.charger_panneaux(c)
        noms = ["team", "quarter_start", "type_group", "created", "done"]
        lignes = self.lire(c)
        self.assertTrue(lignes)
        sorties = fv.masquer_vue("v_team_flow_inout", noms, lignes, fv.PLANCHER)
        for ligne, cellules in zip(lignes, sorties):
            for colonne, valeur in (("created", ligne[3]), ("done", ligne[4])):
                masquee = "masked" in cellules[colonne]
                self.assertEqual(masquee, valeur is None, (ligne[0], ligne[1], ligne[2], colonne))
                if not masquee:
                    self.assertEqual(cellules[colonne]["value"], valeur)

    def test_types_de_portefeuille_et_trimestre_en_cours_absents(self):
        c = self.conn()
        self.charger_panneaux(c)
        trimestres = {self.trimestre(c, k) for k in range(3)}
        lignes = self.lire(c)
        self.assertTrue(lignes)
        self.assertLessEqual({l[1] for l in lignes}, trimestres)              # aucun trimestre en cours, aucun trimestre hors de l'année retenue
        self.assertLessEqual({l[2] for l in lignes}, {"story", "defect"})
        lues = self.cellules(c)
        # l'équipe Z (cas vide) n'a que des éléments de portefeuille, d'un projet exclu et du trimestre en cours : jamais de cellule de portefeuille
        for (equipe, groupe, k), (c_lu, f_lu) in lues.items():
            if equipe == "équipe Z":
                self.assertIsNone(c_lu)
                self.assertIsNone(f_lu)

    def test_les_defauts_sans_equipe_sont_a_part_et_dans_le_produit_jamais_chez_une_equipe(self):
        c = self.conn()
        pan = self.charger_panneaux(c)
        lues = self.cellules(c)
        sans_equipe = {k: v for (e, g, k), v in lues.items() if e is None and g == "defect"}
        self.assertTrue(sans_equipe)
        # le jeu de la tranche 0 porte aussi des défauts d'équipe (autres équipes) : l'ensemble est restreint aux équipes du jeu des panneaux ; les défauts
        # sans équipe du jeu des panneaux ne sont chez aucune d'elles, leurs lignes d'équipe de défauts sont celles de V et W
        equipes_de_defauts = {e for (e, g, _) in lues if g == "defect" and e not in (None, PRODUIT)} & set(pan.EQUIPES_PANNEAUX)
        self.assertEqual(equipes_de_defauts, {"équipe V", "équipe W"})
        import jeu_synthetique as jeu
        cree, fini = self.attendus(pan, jeu, avec_projets_exclus=True)          # la vue ne retire pas les projets exclus : point arrêté
        for (e, g, k), (c_lu, f_lu) in lues.items():
            if e in pan.EQUIPES_PANNEAUX and g == "defect":                     # aucun défaut sans équipe n'est compté chez une équipe des panneaux
                attendu_c, attendu_f = cree.get((e, g, k), 0), fini.get((e, g, k), 0)
                self.assertEqual(c_lu, attendu_c if attendu_c >= PLANCHER else None, (e, k, "created"))
                self.assertEqual(f_lu, attendu_f if attendu_f >= PLANCHER else None, (e, k, "done"))

    def test_ligne_du_produit_visible_seulement_si_toutes_les_cellules_d_equipe_de_sa_colonne_le_sont(self):
        c = self.conn()
        self.charger_panneaux(c)
        lues = self.cellules(c)
        familles = defaultdict(list)
        for (equipe, groupe, k), valeurs in lues.items():
            familles[(groupe, k)].append((equipe, valeurs))
        verifie = 0
        for (groupe, k), membres in familles.items():
            produit = [v for e, v in membres if e == PRODUIT]
            equipes = [v for e, v in membres if e != PRODUIT]
            for colonne in (0, 1):
                tout_visible = all(v[colonne] is not None for v in equipes)
                if produit and not tout_visible:
                    self.assertIsNone(produit[0][colonne], (groupe, k, colonne))
                    verifie += 1
                if produit and tout_visible:
                    self.assertEqual(produit[0][colonne], sum(v[colonne] for v in equipes), (groupe, k, colonne))
                    verifie += 1
        self.assertGreater(verifie, 0)

    def test_cellules_de_un_a_quatre_masquees_cinq_rendu_sur_des_stories_et_des_taches(self):
        """Q2 A : le groupe `story` couvre Story et Task. Données inventées d'une base vierge (pas de jeu synthétique)."""
        c = self.conn()
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.teams (name) VALUES ('Alpha'), ('Beta')")
        c.execute("RESET ROLE")
        for equipe, type_, n, pref in ((1, "Story", 3, "S"), (1, "Task", 2, "T"), (2, "Story", 4, "U"), (2, "Task", 1, "V")):
            for i in range(n):
                c.execute("SET ROLE pmzilla_flow")
                c.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, resolved_at, updated_at, team_id) "
                          "SELECT %s, 'PROJ', %s, 'Closed', 'Done', r - interval '3 days', r, now(), %s "
                          "FROM (SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') - interval '2 months') AT TIME ZONE 'UTC' AS r) x",
                          (f"{pref}-{i}", type_, equipe))
                c.execute("RESET ROLE")
        lignes = {l[0]: l for l in self.lire(c)}
        self.assertEqual(lignes["Alpha"][3:], (5, 5))                                      # trois stories et deux tâches : cinq
        self.assertEqual(lignes["Beta"][3:], (5, 5))                                       # quatre stories et une tâche : cinq
        self.assertEqual(lignes[PRODUIT][3:], (10, 10))

    def test_une_equipe_sous_le_plancher_masque_la_ligne_du_produit(self):
        c = self.conn()
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.teams (name) VALUES ('Alpha'), ('Beta')")
        c.execute("RESET ROLE")
        for equipe, n, pref in ((1, 7, "S"), (2, 3, "T")):
            for i in range(n):
                c.execute("SET ROLE pmzilla_flow")
                c.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, resolved_at, updated_at, team_id) "
                          "SELECT %s, 'PROJ', 'Story', 'Closed', 'Done', r - interval '3 days', r, now(), %s "
                          "FROM (SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') - interval '2 months') AT TIME ZONE 'UTC' AS r) x",
                          (f"{pref}-{i}", equipe))
                c.execute("RESET ROLE")
        lignes = {l[0]: l for l in self.lire(c)}
        self.assertEqual(lignes["Alpha"][3:], (7, 7))
        self.assertEqual(lignes["Beta"][3:], (None, None))
        self.assertEqual(lignes[PRODUIT][3:], (None, None))                               # 7 + 3 = 10 se lirait par différence avec la cellule de l'équipe Alpha

    def test_aucune_colonne_n_expose_de_cle_de_projet_de_resolution_ni_de_parent(self):
        c = self.conn()
        self.charger_panneaux(c)
        colonnes = [d.name for d in self.curseur_colonnes(c)]
        self.assertEqual(colonnes, ["team", "quarter_start", "type_group", "created", "done"])
        texte = repr(self.lire(c))
        self.assertNotIn("SYN-", texte)                                                   # clés, projets, sentinelles : aucune ne sort de la vue

    def curseur_colonnes(self, c):
        c.commit()
        c.execute("SET ROLE pmzilla_flow_views")
        curseur = c.execute(f"SELECT * FROM {VUE} LIMIT 0")
        colonnes = curseur.description
        c.execute("RESET ROLE")
        return colonnes

    def test_le_role_des_vues_lit_la_vue_et_aucun_autre_role_ne_la_lit(self):
        c = self.conn()
        self.assertTrue(self.essaie(c, "pmzilla_flow_views", f"SELECT 1 FROM {VUE}"))
        for role in ("pmzilla_flow", "pmzilla_flow_ro", "pmzilla_quality_views"):
            self.assertFalse(self.essaie(c, role, f"SELECT 1 FROM {VUE}"), role)


if __name__ == "__main__":
    unittest.main()
