"""
Sous-commandes masked-cells et team-ids-check de tools/flow_views.py (change masking-sums, R-144, tâche 1.5 de l'énoncé de 1.6 ; conception D6 et D11).

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -v

Sans base : la lecture des vues est simulée par des lignes synthétiques qui portent un nom d'équipe et des comptes distinctifs. Chaque ligne de
sortie suit la phrase clé de sa langue, les codes de sortie sont 0, 3 et 1, et ni nom, ni identifiant, ni valeur de compte n'est imprimé.
Rouges avant la tâche 3.2 (les sous-commandes n'existent pas encore).
"""
import contextlib
import io
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import db  # noqa: E402
import flow_views as fv  # noqa: E402

NOM_DISTINCTIF = "ZzEquipeDistinctive"
IDENTIFIANTS = ("918273", "736251", "554433")
GROS, PETIT = 913, 2

COLONNES = {
    "v_team_status": ["team", "type", "status_category", "status", "tickets"],
    "v_team_weekly_resolved": ["team", "type", "week_start", "tickets"],
    "v_team_open_age": ["team", "status_category", "age_bucket", "tickets"],
    "v_team_dependencies": ["source_team", "target_team", "link_type", "links"],
    "v_teams": ["team", "team_type", "tickets"],
    "v_team_jira_ids": ["team", "jira_team_id", "tickets"],
    "v_team_fix_version_share": ["team", "quarter_start", "items", "with_fix_version", "share_percent", "with_fix_version_min"],
    "v_team_fix_version_lag": ["team", "quarter_start", "items", "before_or_at_resolution", "within_7_days", "within_30_days", "later", "no_history"],
    "v_version_quality_photo": ["run_id", "source", "coverage", "week_start", "taken_at", "n_adopted", "n_modified_after_reading",
                                "n_previous_weeks", "n_previous_adopted_on", "n_weeks", "n_adopted_on", "team", "version_no", "release_date",
                                "released", "found", "found_open", "corrected_at_week", "corrected_now", "reopened", "defects_created",
                                "defects_without_affects", "resolved_week", "resolved_week_defects", "correction_share_percent",
                                "without_affects_share_percent"],
    "v_team_lead_time_throughput": ["team", "period", "quarter_start", "throughput", "items_lt", "lead_median_days", "lead_p85_days", "items_ct",
                                    "cycle_median_days", "cycle_p85_days", "items_old", "items_without_commitment"],
    "v_task_without_team_share": ["quarter_start", "tasks_done", "tasks_without_team", "share_percent"],
    "v_team_ready_queue": ["team", "quarter_start", "ready"],
    "v_team_blocked_share": ["team", "quarter_start", "blocked_n", "blocked", "share_percent"],
    "v_unplanned_share": ["quarter_start", "unplanned_n", "unplanned", "share_percent"],
    "v_team_flow_inout": ["team", "quarter_start", "type_group", "created", "done"],
    # jira-delivery-fields, R-20261102-16 à -36 : colonnes de la vue de couverture, dans l'ordre de la migration 0033
    "v_team_delivery_fields_coverage": ["team", "quarter_start", "item_kind", "items", "with_sprint", "with_target_version",
                                        "with_resolution_version", "with_epic_version_a", "with_epic_version_b", "with_category_nature",
                                        "with_workflow_option", "with_release_target", "with_verification_required", "with_product_safety",
                                        "with_isp", "with_code_review_status", "with_portfolio_rank", "with_customer_commitment",
                                        "with_source_commitment", "with_strategic_objective"],
    "quality_by_team": ["team", "item_kind", "criterion_code", "origin", "link", "audited", "met", "not_met", "not_applicable", "undetermined"],
    "quality_coverage_by_team": ["team", "item_kind", "collected", "audited", "empty_acceptance_criteria", "single_po", "core_grid_version",
                                 "overlay_version"],
    "quality_by_product": ["item_kind", "criterion_code", "origin", "link", "audited", "met", "not_met", "not_applicable", "undetermined"],
}


def lignes_de(vue: str, gros: int = GROS, petit: int = PETIT) -> list[tuple]:
    if vue == "v_team_status":
        return [(NOM_DISTINCTIF, "Story", "Done", "Closed", gros), (NOM_DISTINCTIF, "Story", "Done", "Open", petit)]
    return []


def lecture(gros: int = GROS, petit: int = PETIT):
    def lire(vue, *args, **kwargs):
        return COLONNES[vue], lignes_de(vue, gros, petit)
    return lire


def lancer(argv: list[str], lire=None, configure: int = fv.PLANCHER):
    sortie, erreur = io.StringIO(), io.StringIO()
    with mock.patch.object(fv, "seuil_configure", return_value=configure), \
            mock.patch.object(fv, "lire", side_effect=lire or lecture()), \
            contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
        code = fv.main(argv)
    return code, sortie.getvalue(), erreur.getvalue()


def lire_en_erreur(vue, *args, **kwargs):
    raise db.ErreurBase("connexion refusée")


class MaskedCells(unittest.TestCase):
    LIGNE_COLONNE = {"fr": re.compile(r"^vue (\w+), colonne (\w+) : (\d+) cellules masquées sur (\d+)$"),
                     "en": re.compile(r"^view (\w+), column (\w+): (\d+) masked cells out of (\d+)$")}
    LIGNE_VUE = {"fr": re.compile(r"^vue (\w+) : (\d+) cellules masquées sur (\d+), dont (\d+) à une unité de large$"),
                 "en": re.compile(r"^view (\w+): (\d+) masked cells out of (\d+), (\d+) of them one unit wide$")}

    LIGNE_CHAINE = {"fr": re.compile(r"^vue (\w+) : (\d+) cellules de créés masquées seules par la chaîne des semaines, dont (\d+) à une unité de large$"),
                    "en": re.compile(r"^view (\w+): (\d+) created-defects cells masked alone by the week chain, (\d+) of them one unit wide$")}

    def lignes(self, langue: str, *options, lire=None):
        code, sortie, erreur = lancer(["--language", langue, "masked-cells", *options], lire=lire)
        self.assertEqual((code, erreur), (0, ""))
        return sortie.splitlines()

    def test_chaque_ligne_suit_la_phrase_cle_de_sa_langue(self):
        for langue in ("fr", "en"):
            with self.subTest(langue=langue):
                lignes = self.lignes(langue)
                self.assertTrue(lignes)
                for ligne in lignes:
                    self.assertTrue(self.LIGNE_COLONNE[langue].match(ligne) or self.LIGNE_VUE[langue].match(ligne)
                                    or self.LIGNE_CHAINE[langue].match(ligne), ligne)

    @staticmethod
    def photo_avec_chaine():
        """Équipe A, deux semaines : créés 40 puis 43 (écart 3 : la chaîne masque le second), deux trouvés 38 et 10 la seconde semaine : l'intervalle
        du créé masqué seul va de 43 à 44, une unité de large (la lecture « m = 0 » est écartée : les défauts distincts valent au moins 38)."""
        noms = COLONNES["v_version_quality_photo"]

        def ligne(**valeurs):
            return tuple(valeurs.get(n) for n in noms)
        return [ligne(week_start="2026-03-02", team="A", defects_created=40, defects_without_affects=5, resolved_week=20, resolved_week_defects=10),
                ligne(week_start="2026-03-02", team="A", version_no=1, found=30),
                ligne(week_start="2026-03-02", team="A", version_no=2, found=20),
                ligne(week_start="2026-03-09", team="A", defects_created=43, defects_without_affects=5, resolved_week=20, resolved_week_defects=10),
                ligne(week_start="2026-03-09", team="A", version_no=3, found=38),
                # M4 (R-20261104-6), M7 (a) : deuxième trouvé (10) ; avec un seul trouvé, « U = 0 et m = 0 » fixe le créé à 43 (D15 le masque avec sa voisine)
                ligne(week_start="2026-03-09", team="A", version_no=4, found=10)]

    def lecture_photo(self, lignes_photo):
        def lire(vue, *args, **kwargs):
            return COLONNES[vue], (lignes_photo if vue == "v_version_quality_photo" else lignes_de(vue))
        return lire

    def test_compte_des_intervalles_de_creees_masques_seuls_par_la_chaine(self):
        attendu = {"fr": "vue v_version_quality_photo : 1 cellules de créés masquées seules par la chaîne des semaines, dont 1 à une unité de large",
                   "en": "view v_version_quality_photo: 1 created-defects cells masked alone by the week chain, 1 of them one unit wide"}
        for langue in ("fr", "en"):
            with self.subTest(langue=langue):
                lignes = self.lignes(langue, lire=self.lecture_photo(self.photo_avec_chaine()))
                self.assertIn(attendu[langue], lignes)
                vue = next(l for l in lignes if self.LIGNE_VUE[langue].match(l) and self.LIGNE_VUE[langue].match(l).group(1) == "v_version_quality_photo")
                self.assertGreaterEqual(int(self.LIGNE_VUE[langue].match(vue).group(4)), 1)   # la cellule étroite entre aussi dans le compteur de la vue

    def test_les_intervalles_du_produit_sont_comptes_avec_ses_lignes_de_version(self):
        """Revue 4, m2 : la ligne (produit) et ses lignes de version entrent dans le compte, comme celles d'une équipe."""
        noms = COLONNES["v_version_quality_photo"]

        def ligne(**valeurs):
            return tuple(valeurs.get(n) for n in noms)
        lignes = [ligne(week_start="2026-03-02", team="(produit)", defects_created=40, defects_without_affects=5, resolved_week=20, resolved_week_defects=10),
                  ligne(week_start="2026-03-02", team="(produit)", version_no=1, found=30),
                  ligne(week_start="2026-03-02", team="(produit)", version_no=2, found=20),
                  ligne(week_start="2026-03-09", team="(produit)", defects_created=43, defects_without_affects=5, resolved_week=20, resolved_week_defects=10),
                  ligne(week_start="2026-03-09", team="(produit)", version_no=3, found=38),
                  ligne(week_start="2026-03-09", team="(produit)", version_no=4, found=10)]      # M4, M7 (a) : deuxième trouvé, comme ci-dessus
        lignes_en = self.lignes("en", lire=self.lecture_photo(lignes))
        self.assertIn("view v_version_quality_photo: 1 created-defects cells masked alone by the week chain, 1 of them one unit wide", lignes_en)

    def test_sans_intervalle_le_compte_est_nul_et_la_ligne_est_la_meme(self):
        lignes = self.lignes("en", lire=self.lecture_photo([]))
        self.assertIn("view v_version_quality_photo: 0 created-defects cells masked alone by the week chain, 0 of them one unit wide", lignes)

    def test_la_ligne_de_chaine_n_imprime_ni_nom_ni_valeur(self):
        for langue in ("fr", "en"):
            texte = "\n".join(self.lignes(langue, lire=self.lecture_photo(self.photo_avec_chaine())))
            self.assertNotRegex(texte, r"\bA\b.*\b38\b")
            self.assertNotIn("38", texte)

    def test_une_ligne_par_colonne_de_compte_et_une_ligne_par_vue(self):
        for langue in ("fr", "en"):
            with self.subTest(langue=langue):
                lignes = self.lignes(langue)
                vues = [m.group(1) for m in map(self.LIGNE_VUE[langue].match, lignes) if m]
                self.assertEqual(sorted(vues), sorted(fv.VUES))
                colonnes = {(m.group(1), m.group(2)) for m in map(self.LIGNE_COLONNE[langue].match, lignes) if m}
                self.assertIn(("v_team_status", "tickets"), colonnes)
                self.assertIn(("v_team_fix_version_share", "items"), colonnes)
                self.assertIn(("v_team_fix_version_lag", "no_history"), colonnes)

    def test_compte_des_cellules_masquees_sur_une_vue_simple(self):
        attendu = {"fr": ("vue v_team_status, colonne tickets : 1 cellules masquées sur 2",),
                   "en": ("view v_team_status, column tickets: 1 masked cells out of 2",)}
        for langue in ("fr", "en"):
            with self.subTest(langue=langue):
                lignes = self.lignes(langue)
                for ligne in attendu[langue]:
                    self.assertIn(ligne, lignes)
                vue = next(self.LIGNE_VUE[langue].match(l) for l in lignes if self.LIGNE_VUE[langue].match(l)
                           and self.LIGNE_VUE[langue].match(l).group(1) == "v_team_status")
                self.assertEqual(vue.group(2, 3), ("1", "2"))

    def test_aucun_nom_aucun_identifiant_aucune_valeur_dans_la_sortie(self):
        for langue in ("fr", "en"):
            with self.subTest(langue=langue):
                texte = "\n".join(self.lignes(langue))
                self.assertNotIn(NOM_DISTINCTIF, texte)
                self.assertNotIn(str(GROS), texte)
                for identifiant in IDENTIFIANTS:
                    self.assertNotIn(identifiant, texte)

    def test_le_seuil_releve_masque_davantage(self):
        lire = lecture(gros=GROS, petit=8)
        for options, masquees in (((), "0"), (("--min-cell", "10"), "1")):
            code, sortie, _ = lancer(["--language", "en", "masked-cells", *options], lire=lire)
            self.assertEqual(code, 0)
            self.assertIn(f"view v_team_status, column tickets: {masquees} masked cells out of 2", sortie.splitlines())

    def test_le_francais_est_la_langue_par_defaut(self):
        code, sortie, _ = lancer(["masked-cells"])
        self.assertEqual(code, 0)
        self.assertIn("vue v_team_status, colonne tickets : 1 cellules masquées sur 2", sortie.splitlines())

    def test_ecrit_rien_et_ne_lit_que_la_liste_fermee(self):
        lire = mock.Mock(side_effect=lecture())
        with mock.patch.object(fv, "seuil_configure", return_value=fv.PLANCHER), mock.patch.object(fv, "lire", lire), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(fv.main(["masked-cells"]), 0)
        self.assertEqual(sorted(c.args[0] for c in lire.call_args_list), sorted(fv.VUES))

    def test_erreur_de_base_ligne_d_erreur_et_code_1(self):
        for langue, attendu in (("fr", "Erreur : connexion refusée"), ("en", "Error: connexion refusée")):
            with self.subTest(langue=langue):
                code, sortie, erreur = lancer(["--language", langue, "masked-cells"], lire=lire_en_erreur)
                self.assertEqual(code, 1)
                self.assertEqual(sortie, "")
                self.assertEqual(erreur.strip(), attendu)


class TeamIdsCheck(unittest.TestCase):
    def lecture(self, lignes):
        return lambda vue, *args, **kwargs: (COLONNES["v_team_jira_ids"], lignes)

    def test_des_noms_a_nettoyer_code_3_sans_nom_ni_identifiant(self):
        lignes = [("ZzUn", IDENTIFIANTS[0], 20), ("ZzUn", IDENTIFIANTS[1], 12), ("ZzDeux", IDENTIFIANTS[2], 8), ("ZzDeux", "111222", 8),
                  ("ZzTrois", "333444", 30)]
        attendus = {"en": ["team names with several Jira identifiers: 2", "to clean in Jira: a ticket carries one identifier per team"],
                    "fr": ["noms d'équipe à plusieurs identifiants Jira : 2", "à nettoyer dans Jira : un ticket ne porte qu'un identifiant par équipe"]}
        for langue, phrases in attendus.items():
            with self.subTest(langue=langue):
                code, sortie, erreur = lancer(["--language", langue, "team-ids-check"], lire=self.lecture(lignes))
                self.assertEqual((code, erreur), (3, ""))
                self.assertEqual(sortie.splitlines(), phrases)
                for interdit in ("ZzUn", "ZzDeux", "ZzTrois", *IDENTIFIANTS, "111222", "333444"):
                    self.assertNotIn(interdit, sortie)

    def test_propre_code_0_et_compte_nul(self):
        lignes = [("ZzUn", IDENTIFIANTS[0], 20), ("ZzDeux", IDENTIFIANTS[1], 8)]
        attendus = {"en": "team names with several Jira identifiers: 0", "fr": "noms d'équipe à plusieurs identifiants Jira : 0"}
        for langue, phrase in attendus.items():
            with self.subTest(langue=langue):
                code, sortie, erreur = lancer(["--language", langue, "team-ids-check"], lire=self.lecture(lignes))
                self.assertEqual((code, erreur, sortie.splitlines()), (0, "", [phrase]))

    def test_lit_seulement_la_vue_des_identifiants(self):
        lire = mock.Mock(side_effect=self.lecture([]))
        with mock.patch.object(fv, "seuil_configure", return_value=fv.PLANCHER), mock.patch.object(fv, "lire", lire), \
                contextlib.redirect_stdout(io.StringIO()):
            fv.main(["team-ids-check"])
        self.assertEqual([c.args[0] for c in lire.call_args_list], ["v_team_jira_ids"])

    def test_erreur_de_base_ligne_d_erreur_et_code_1(self):
        code, sortie, erreur = lancer(["--language", "en", "team-ids-check"], lire=lire_en_erreur)
        self.assertEqual((code, sortie, erreur.strip()), (1, "", "Error: connexion refusée"))


if __name__ == "__main__":
    unittest.main()
