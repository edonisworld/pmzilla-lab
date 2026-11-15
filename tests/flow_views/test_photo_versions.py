"""
Vues v_version_quality_photo et v_team_fix_version_lag dans tools/flow_views.py (change version-quality-photo, tâche 4.4 ; spec jira-flow-views
« Known views », « Photo view masking on the retained weeks », « Shares of the photo view », « Fix version lag masking »), masquées par la fonction
de service masquer_vue (change masking-sums, R-144 : D2 ligne à compléter, D3 ligne du produit, D5-d semaines retenues, D5-e).

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -v

Sans base : la lecture des vues est simulée, le réglage flux.yaml réel n'est jamais lu. Équipes et chiffres inventés.
"""
import contextlib
import io
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import db  # noqa: E402
import flow_views as fv  # noqa: E402
from flow_views_messages import CATALOGS  # noqa: E402
from messages import Messages  # noqa: E402

FR, EN = Messages(CATALOGS, "fr"), Messages(CATALOGS, "en")
NOMS = ["run_id", "source", "coverage", "week_start", "taken_at", "n_adopted", "n_modified_after_reading", "n_previous_weeks",
        "n_previous_adopted_on", "n_weeks", "n_adopted_on", "team", "version_no", "release_date", "released",
        "found", "found_open", "corrected_at_week", "corrected_now", "reopened", "defects_created", "defects_without_affects",
        "resolved_week", "resolved_week_defects", "correction_share_percent", "without_affects_share_percent"]
NOMS_RETARD = ["team", "quarter_start", "items", "before_or_at_resolution", "within_7_days", "within_30_days", "later", "no_history"]
SEMAINE = date(2026, 11, 2)


def photo(**valeurs):
    base = {"run_id": 1, "source": "reconstructed", "coverage": "complete", "week_start": SEMAINE, "taken_at": None, "n_adopted": True,
            "n_modified_after_reading": False}
    base.update(valeurs)
    return tuple(base.get(n) for n in NOMS)


def couverture(semaine=SEMAINE, **valeurs):
    return photo(week_start=semaine, n_adopted=False, **valeurs)


def version(equipe, **comptes):
    return photo(team=equipe, version_no=1, n_weeks=6, **comptes)


def libre(equipe, **comptes):
    return photo(team=equipe, n_weeks=6, **comptes)


def cellules(lignes, seuil=5):
    return fv.masquer_vue(fv.VUE_PHOTO, NOMS, lignes, seuil)


def masquee(seuil=5):
    return {"value": None, "masked": "under_threshold", "threshold": seuil}


def cellules_retard(lignes, seuil, liees=None):
    return fv.masquer_vue(fv.VUE_RETARD, NOMS_RETARD, lignes, seuil, liees)


class ListeFermee(unittest.TestCase):
    def test_les_deux_vues_sont_dans_la_liste_fermee_et_dans_la_migration(self):
        for vue, constante in (("v_version_quality_photo", fv.VUE_PHOTO), ("v_team_fix_version_lag", fv.VUE_RETARD)):
            self.assertEqual(constante, vue)
            self.assertIn(vue, fv.VUES)
            self.assertNotIn(vue, fv.VUES_FLOW + fv.VUES_EQUIPES + fv.VUES_QUALITE)
        self.assertEqual(len(fv.VUES), 19)                       # dix-sept avec les cinq vues de mothra-slices 15.2, dix-huit avec la vue de 36.1, dix-neuf avec la couverture (jira-delivery-fields, R-20261102-16 à -36)
        candidats = sorted((RACINE / "db" / "migrations").glob("*_flow_version_photo_views.sql"))
        self.assertEqual(len(candidats), 1)
        texte = candidats[0].read_text(encoding="utf-8")
        self.assertIn("CREATE VIEW flow.v_version_quality_photo AS", texte)
        self.assertIn("CREATE VIEW flow.v_team_fix_version_lag AS", texte)

    def test_les_vues_se_lisent_sous_le_role_des_vues_de_flow(self):
        for vue, noms in ((fv.VUE_PHOTO, NOMS), (fv.VUE_RETARD, NOMS_RETARD)):
            roles, requetes = [], []

            class Curseur:
                description = [type("C", (), {"name": n})() for n in noms]

                def fetchall(self):
                    return []

            class Connexion:
                def execute(self, sql):
                    requetes.append(sql)
                    return Curseur()

                def close(self):
                    pass

            def connecter(**kwargs):
                roles.append(kwargs["role"])
                return Connexion()

            with mock.patch.object(db, "connect", side_effect=connecter):
                fv.lire(vue)
            self.assertEqual(roles, ["pmzilla_flow_views"])
            self.assertEqual(requetes, [f"SELECT * FROM flow.{vue}"])

    def test_descriptions_dans_chaque_langue(self):
        for langue, extrait in (("fr", "photo de qualité"), ("en", "version quality photo")):
            sortie = io.StringIO()
            with mock.patch.object(fv, "seuil_configure", return_value=5), contextlib.redirect_stdout(sortie):
                self.assertEqual(fv.main(["--language", langue, "list"]), 0)
            for vue in (fv.VUE_PHOTO, fv.VUE_RETARD):
                self.assertIn(vue, sortie.getvalue())
            self.assertIn(extrait, sortie.getvalue())


class CellulesDeLaPhoto(unittest.TestCase):
    def test_ligne_de_couverture_aucune_cellule_masquee(self):
        (c,) = cellules([couverture()])
        for col in fv.COMPTES_PHOTO + tuple(fv.PARTS_PHOTO):
            self.assertEqual(c[col], {"value": None}, col)                      # pas de compte : ni valeur, ni masque
        self.assertEqual((c["source"], c["coverage"], c["n_adopted"]), ({"value": "reconstructed"}, {"value": "complete"}, {"value": False}))

    def test_compte_visible_et_compte_sous_le_seuil_masque_avec_la_raison_et_le_seuil(self):
        a, b = cellules([version("Alpha", found=20, found_open=10, corrected_at_week=None, corrected_now=12, reopened=6),
                         version("Beta", found=None, found_open=None, corrected_at_week=None, corrected_now=None, reopened=None)])
        self.assertEqual((a["found"], a["found_open"], a["corrected_now"], a["reopened"]),
                         ({"value": 20}, {"value": 10}, {"value": 12}, {"value": 6}))
        self.assertEqual(a["corrected_at_week"], masquee())                      # nul de la vue : masqué
        for col in ("found", "found_open", "corrected_now"):
            self.assertEqual(b[col], masquee(), col)
        self.assertEqual(set(masquee()), {"value", "masked", "threshold"})       # jamais « primaire » ni « complémentaire »

    def test_seuil_releve_masque_un_compte_visible_pour_la_vue(self):
        (a,) = cellules([version("Alpha", found=20, found_open=10, corrected_at_week=8, corrected_now=12, reopened=6)], seuil=12)
        self.assertEqual(a["found"], {"value": 20})
        self.assertEqual(a["found_open"], masquee(12))                           # 10 sous 12
        self.assertEqual(a["corrected_now"], {"value": 12})
        self.assertEqual(a["reopened"], masquee(12))
        self.assertEqual(a["corrected_at_week"], masquee(12))

    def test_paire_au_seuil_releve_le_tout_moins_la_partie_compte(self):
        (a,) = cellules([version("Alpha", found=20, found_open=10, corrected_at_week=None, corrected_now=None, reopened=None)], seuil=10)
        self.assertEqual(a["found_open"], {"value": 10})                         # 10 et 20 - 10
        (a,) = cellules([version("Alpha", found=20, found_open=11, corrected_at_week=None, corrected_now=None, reopened=None)], seuil=10)
        self.assertEqual(a["found_open"], masquee(10))                           # 20 - 11 = 9 sous 10 : l'ouvert est masqué, le trouvé reste
        self.assertEqual(a["found"], {"value": 20})

    def test_parts_masquees_avec_leur_partie_ou_leur_tout(self):
        # la version V publie 42 défauts trouvés pour 32 défauts avec affects (40 - 8) : l'excès, 10, est un terme caché que la différence donne ;
        # il atteint le seuil (D5-e : sous le seuil, zéro compris, sans affects serait masqué)
        # M4 (R-20261104-6) : deux versions de 30 et 12 (somme 42, défauts distincts 32 entre le plus grand et la somme) au lieu d'une seule de 42, qui
        # dépassait les défauts distincts ; attendu inchangé.
        deuxieme = photo(team="Alpha", version_no=2, n_weeks=6, found=12)
        _, _, a = cellules([version("Alpha", found=30), deuxieme,
                            libre("Alpha", defects_created=40, defects_without_affects=8, resolved_week=20, resolved_week_defects=6,
                                  correction_share_percent=30.0, without_affects_share_percent=20.0)])
        self.assertEqual((a["correction_share_percent"], a["without_affects_share_percent"]), ({"value": 30.0}, {"value": 20.0}))
        _, _, a = cellules([version("Alpha", found=30), deuxieme,
                            libre("Alpha", defects_created=40, defects_without_affects=8, resolved_week=20, resolved_week_defects=6,
                                  correction_share_percent=30.0, without_affects_share_percent=20.0)], seuil=7)
        self.assertEqual(a["correction_share_percent"], masquee(7))              # 6 sous 7
        self.assertEqual(a["without_affects_share_percent"], {"value": 20.0})
        (a,) = cellules([libre("Alpha", defects_created=20, defects_without_affects=None, resolved_week=20, resolved_week_defects=None,
                               correction_share_percent=None, without_affects_share_percent=None)])
        self.assertEqual((a["correction_share_percent"], a["without_affects_share_percent"]), (masquee(), masquee()))

    def test_ligne_produit_masquee_au_seuil_releve_quand_une_cellule_d_equipe_l_est(self):
        equipes = [version("Alpha", found=20, found_open=10, corrected_at_week=8, corrected_now=12, reopened=6),
                   version("Beta", found=12, found_open=6, corrected_at_week=6, corrected_now=11, reopened=6)]
        produit = photo(team=fv.PRODUIT, version_no=1, n_weeks=6, found=32, found_open=16, corrected_at_week=14, corrected_now=23, reopened=12)
        sortie = cellules(equipes + [produit], seuil=12)
        p = sortie[2]
        self.assertEqual(sortie[1]["found"], {"value": 12})
        self.assertEqual(p["found"], {"value": 32})                              # les deux équipes sont visibles
        self.assertEqual(sortie[1]["corrected_now"], masquee(12))                # 11 sous 12
        self.assertEqual(p["corrected_now"], masquee(12))                        # une cellule d'équipe masquée : le produit la redonnerait
        self.assertEqual(p["found_open"], masquee(12))                           # D3 : deux cellules d'équipe masquées, somme ou non, le produit l'est aussi

    def test_cellule_deja_masquee_par_la_base_masque_le_produit_de_la_colonne(self):
        """D3 : deux cellules d'équipe masquées par la base, même de somme 9 : la colonne du produit est masquée (avant, elle restait)."""
        equipes = [version("Alpha", found=20, found_open=10, corrected_at_week=8, corrected_now=12, reopened=6),
                   version("Beta", found=None, found_open=None, corrected_at_week=None, corrected_now=None, reopened=None),
                   version("Gamma", found=None, found_open=None, corrected_at_week=None, corrected_now=None, reopened=None)]
        produit = photo(team=fv.PRODUIT, version_no=1, n_weeks=6, found=29, found_open=10, corrected_at_week=8, corrected_now=12, reopened=6)
        sortie = cellules(equipes + [produit])
        self.assertEqual(sortie[3]["found"], masquee())

    def test_une_cellule_d_equipe_masquee_masque_le_produit_a_tout_seuil(self):
        equipes = [version("Alpha", found=50, found_open=None, corrected_at_week=None, corrected_now=None, reopened=None),
                   version("Beta", found=None, found_open=None, corrected_at_week=None, corrected_now=None, reopened=None),
                   version("Gamma", found=None, found_open=None, corrected_at_week=None, corrected_now=None, reopened=None)]
        produit = photo(team=fv.PRODUIT, version_no=1, n_weeks=6, found=57)
        for seuil in (5, 10):
            sortie = cellules(equipes + [produit], seuil=seuil)
            self.assertEqual(sortie[0]["found"], {"value": 50})
            self.assertEqual(sortie[3]["found"], masquee(seuil), seuil)
        sortie = cellules(equipes[:2] + [photo(team=fv.PRODUIT, version_no=1, n_weeks=6, found=53)], seuil=5)
        self.assertEqual(sortie[2]["found"], masquee())

    def test_toutes_les_cellules_d_equipe_visibles_le_produit_est_montre(self):
        equipes = [version("Alpha", found=30), version("Beta", found=20)]
        produit = photo(team=fv.PRODUIT, version_no=1, n_weeks=6, found=50)
        self.assertEqual(cellules(equipes + [produit])[2]["found"], {"value": 50})

    def test_sans_affects_au_seuil_releve_un_terme_visible_masque_masque_sans_affects(self):
        """Au seuil relevé, un trouvé de la ligne « créés = sans affects + trouvés » qui passe sous le seuil est un terme caché ; seul, il se
        retrouverait : sans affects et sa part sont masqués."""
        lignes = [version("Alpha", found=20), photo(team="Alpha", version_no=2, n_weeks=6, found=11),
                  libre("Alpha", defects_created=40, defects_without_affects=15)]
        sortie = cellules(lignes, seuil=5)
        self.assertEqual((sortie[2]["defects_created"], sortie[2]["defects_without_affects"]), ({"value": 40}, {"value": 15}))   # excès 31 - 25 = 6
        sortie = cellules(lignes, seuil=12)
        self.assertEqual(sortie[2]["defects_without_affects"], masquee(12))
        self.assertEqual(sortie[2]["without_affects_share_percent"], masquee(12))
        self.assertEqual(sortie[2]["defects_created"], {"value": 40})

    def test_excès_sous_le_seuil_masque_sans_affects_zero_compris(self):
        """D5-e : toute la ligne est publiée ; l'excès des trouvés sur les défauts avec affects (ici 2, puis 0) est sous le seuil : sans affects est
        masqué, avec sa part (X12, la limite connue de R-140 est levée) ; D2 repasse jusqu'au point fixe et masque alors les créés (décision du
        2026-10-27 : sans affects seul caché se lirait par différence)."""
        for trouves, exces in ((32, 2), (30, 0)):
            lignes = [version("Alpha", found=trouves), libre("Alpha", defects_created=40, defects_without_affects=10)]
            sortie = cellules(lignes)
            self.assertEqual(sortie[1]["defects_without_affects"], masquee(), exces)
            self.assertEqual(sortie[1]["without_affects_share_percent"], masquee(), exces)
            self.assertEqual(sortie[1]["defects_created"], masquee(), exces)         # point fixe : une seule cellule cachée se lirait par différence
            self.assertEqual(sortie[0]["found"], {"value": trouves}, exces)

    def test_sans_affects_au_seuil_releve_masque_les_crees_quand_aucun_terme_n_est_cache(self):
        lignes = [version("Alpha", found=20), libre("Alpha", defects_created=40, defects_without_affects=9)]
        sortie = cellules(lignes, seuil=10)
        self.assertEqual(sortie[1]["defects_without_affects"], masquee(10))      # 9 sous 10
        self.assertEqual(sortie[1]["defects_created"], masquee(10))              # aucun terme caché : la différence redonnerait sans affects

    def test_sans_affects_deja_masque_par_la_base_la_ligne_a_completer_s_applique_aux_crees(self):
        """Revue 2, M3 : sans affects nul de la vue est une cellule cachée de la ligne à compléter ; avec un seul terme caché (lui), les défauts créés
        sont masqués, comme le fait la vue (cas « sans affects masqué » de la règle D2)."""
        lignes = [version("Alpha", found=20), libre("Alpha", defects_created=40, defects_without_affects=None)]
        sortie = cellules(lignes, seuil=5)
        self.assertEqual(sortie[1]["defects_without_affects"], masquee())
        self.assertEqual(sortie[1]["defects_created"], masquee())

    def test_sans_affects_termes_masques_somme_sous_le_seuil_ou_aux_bornes_hautes(self):
        """La vue montre créés 40, sans affects 12, V = 20 et masque W et X : somme cachée 40 - 12 - 20 = 8. Au seuil 10, 8 est sous 10 : sans
        affects est masqué. Au seuil 5, 8 = 2 fois 4 (les deux termes valent 4 chacun) : masqué aussi. Au seuil 5 avec créés 41, la somme 9 dépasse
        les bornes hautes : sans affects reste."""
        lignes = [version("Alpha", found=20), photo(team="Alpha", version_no=2, n_weeks=6, found=None),
                  photo(team="Alpha", version_no=3, n_weeks=6, found=None),
                  libre("Alpha", defects_created=40, defects_without_affects=12)]
        sortie = cellules(lignes, seuil=10)
        self.assertEqual(sortie[3]["defects_without_affects"], masquee(10))
        self.assertEqual(sortie[3]["without_affects_share_percent"], masquee(10))
        self.assertEqual(sortie[3]["defects_created"], {"value": 40})
        sortie = cellules(lignes, seuil=5)
        self.assertEqual(sortie[3]["defects_without_affects"], masquee())
        lignes[3] = libre("Alpha", defects_created=41, defects_without_affects=12)
        self.assertEqual(cellules(lignes, seuil=5)[3]["defects_without_affects"], {"value": 12})

    def test_sans_affects_somme_cachee_nulle_avec_un_terme_masque_reste_masque_par_prudence(self):
        """Un terme masqué par la vue compte même quand la somme cachée est nulle (un zéro masqué compte comme une cellule masquée)."""
        lignes = [version("Alpha", found=20), photo(team="Alpha", version_no=2, n_weeks=6, found=None),
                  libre("Alpha", defects_created=40, defects_without_affects=20)]
        sortie = cellules(lignes, seuil=5)
        self.assertEqual(sortie[2]["defects_without_affects"], masquee())

    def test_sans_affects_ligne_du_produit_meme_regle_au_seuil_releve(self):
        lignes = [photo(team=fv.PRODUIT, version_no=1, n_weeks=6, found=20), photo(team=fv.PRODUIT, version_no=2, n_weeks=6, found=None),
                  photo(team=fv.PRODUIT, version_no=3, n_weeks=6, found=None),
                  photo(team=fv.PRODUIT, n_weeks=6, defects_created=40, defects_without_affects=12)]
        sortie = cellules(lignes, seuil=10)
        self.assertEqual(sortie[3]["defects_without_affects"], masquee(10))

    def test_sans_affects_ligne_du_produit_un_seul_terme_masque_par_les_equipes_masque_les_crees(self):
        """Mêmes données que le test de base `test_sans_affects_masque_quand_tous_les_termes_de_la_ligne_sont_publies_...` (tests/db), au plancher.
        Équipe : excès 12 - (20 - 8) = 0 sous 5, sans affects masqué (D5-e) ; une seule cellule cachée se lirait par différence (20 - 12 = 8), D2 repasse
        (point fixe, décision du 2026-10-27) et masque aussi les créés. Produit : D3 masque les deux colonnes parce que les cellules de l'équipe le
        sont. Le trouvé reste."""
        lignes = [version("Alpha", found=12), libre("Alpha", defects_created=20, defects_without_affects=8, resolved_week=20, resolved_week_defects=6),
                  photo(team=fv.PRODUIT, version_no=1, n_weeks=6, found=12),
                  photo(team=fv.PRODUIT, n_weeks=6, defects_created=20, defects_without_affects=8, resolved_week=20, resolved_week_defects=6)]
        sortie = cellules(lignes)
        self.assertEqual((sortie[1]["defects_created"], sortie[1]["defects_without_affects"]), (masquee(), masquee()))
        self.assertEqual((sortie[3]["defects_created"], sortie[3]["defects_without_affects"]), (masquee(), masquee()))
        self.assertEqual(sortie[3]["without_affects_share_percent"], masquee())
        self.assertEqual(sortie[3]["resolved_week"], {"value": 20})
        self.assertEqual(sortie[2]["found"], {"value": 12})

    def test_semaines_retenues_un_ecart_de_un_a_quatre_masque_la_cellule_la_plus_recente(self):
        """D5-d (X8) : les défauts créés d'une équipe à deux semaines retenues, 40 puis 43, donneraient 3 par différence ; zéro n'est pas protégé."""
        # Données réécrites (R-20261106-22 et R-20261106-23, écart D4 (d) rétabli) : une équipe sans ligne de version a ses créés masqués par D2 ; chaque
        # semaine a donc ses lignes de version (trouvés 20 et 15, puis 20 et 18 ou 20 et 20 : excès de 10 sur les défauts distincts), assertions gardées.
        def semaine(jour, crees, sans, trouves):
            lignes = [photo(week_start=jour, team="Alpha", n_weeks=6, defects_created=crees, defects_without_affects=sans)]
            lignes += [photo(week_start=jour, team="Alpha", version_no=k + 1, n_weeks=6, found=f) for k, f in enumerate(trouves)]
            return lignes
        sortie = cellules(semaine(date(2026, 11, 2), 40, 15, (20, 15)) + semaine(date(2026, 11, 9), 43, 15, (20, 18)))
        self.assertEqual((sortie[0]["defects_created"], sortie[3]["defects_created"]), ({"value": 40}, masquee()))
        self.assertEqual((sortie[0]["defects_without_affects"], sortie[3]["defects_without_affects"]), ({"value": 15}, {"value": 15}))
        sortie = cellules(semaine(date(2026, 11, 2), 40, 15, (20, 15)) + semaine(date(2026, 11, 9), 45, 15, (20, 20)))
        self.assertEqual(sortie[3]["defects_created"], {"value": 45})            # 5 atteint le seuil

    def test_rendu_texte_couverture_sans_masque_et_ligne_retenue_avec_masque(self):
        lignes = [couverture(), version("Alpha", found=20, found_open=None, corrected_at_week=None, corrected_now=12, reopened=None)]
        texte = fv.rendre(NOMS, lignes, 5, FR)
        premiere, retenue = texte.splitlines()[2], texte.splitlines()[3]
        self.assertNotIn("masqué", premiere)
        self.assertEqual(retenue.count("masqué"), 3)
        texte_en = fv.rendre(NOMS, lignes, 5, EN)
        self.assertIn("masked", texte_en)
        self.assertNotIn("masqué", texte_en)

    def test_sans_ligne(self):
        self.assertEqual(fv.rendre(NOMS, [], 5, FR), FR("no_rows"))


def retard(equipe, items, *seaux, trimestre=date(2026, 7, 1)):
    return (equipe, trimestre, items, *seaux)


class CellulesDuRetard(unittest.TestCase):
    def test_comptes_visibles(self):
        (a,) = cellules_retard([retard("Alpha", 40, 8, 8, 8, 8, 8)], 5)
        self.assertEqual([a[c]["value"] for c in NOMS_RETARD[2:]], [40, 8, 8, 8, 8, 8])
        (a,) = cellules_retard([retard("Alpha", 40, None, 10, 10, 10, 10)], 5)
        self.assertEqual(a["before_or_at_resolution"], masquee())                # nul de la vue : masqué, jamais « zéro »

    def test_seuil_releve_masque_la_plus_petite_cellule_visible_quand_les_masquees_font_moins_que_le_seuil(self):
        (a,) = cellules_retard([retard("Alpha", 40, 14, 12, 8, 6, None)], 8)
        self.assertEqual(a["items"], {"value": 40})
        self.assertEqual(a["later"], masquee(8))                                 # 6 sous 8
        self.assertEqual(a["within_30_days"], masquee(8))                        # les cellules masquées font 6 sous 8 : la plus petite visible l'est aussi
        self.assertEqual((a["before_or_at_resolution"], a["within_7_days"]), ({"value": 14}, {"value": 12}))

    def test_aucun_complement_quand_les_cellules_masquees_atteignent_le_seuil(self):
        (a,) = cellules_retard([retard("Alpha", 20, None, None, None, 10, None)], 5)
        self.assertEqual(a["later"], {"value": 10})                              # les cellules masquées font 10 : pas de complément

    def test_un_zero_masque_compte_et_la_plus_petite_cellule_visible_l_est_aussi(self):
        """Décision C : trois cellules masquées dont la somme est nulle (des zéros) se retrouveraient par différence avec les items."""
        (a,) = cellules_retard([retard("Alpha", 20, 10, None, None, 10, None)], 5)
        self.assertEqual(a["items"], {"value": 20})
        self.assertEqual(a["before_or_at_resolution"], masquee())                # la plus petite visible (égalité : la première) est masquée aussi
        self.assertEqual(a["later"], {"value": 10})

    def test_une_seule_cellule_masquee_masque_aussi_la_plus_petite_visible(self):
        """D2 : au moins deux cellules masquées ; une seule se retrouverait par différence avec les items."""
        (a,) = cellules_retard([retard("Alpha", 40, 20, 10, 5, 5, None)], 5)
        self.assertEqual(a["no_history"], masquee())
        self.assertEqual((a["within_30_days"], a["later"]), (masquee(), {"value": 5}))      # la plus petite visible, la première à égalité

    def test_cellules_masquees_a_la_somme_des_bornes_hautes_le_total_est_masque(self):
        """D2 : cinq cellules masquées, aucune visible, de somme 20 = 5 fois 4 : chacune vaut 4, les items sont masqués aussi."""
        (a,) = cellules_retard([retard("Alpha", 20, 4, 4, 4, 4, 4)], 5)
        for col in NOMS_RETARD[2:]:
            self.assertEqual(a[col], masquee(), col)

    def test_items_sous_le_seuil_tout_masque(self):
        (a,) = cellules_retard([retard("Alpha", 3, None, None, None, None, None)], 5)
        for col in NOMS_RETARD[2:]:
            self.assertEqual(a[col], masquee(), col)

    def test_ligne_produit_masquee_quand_une_seule_cellule_d_equipe_est_masquee_au_seuil_releve(self):
        lignes = [retard("Alpha", 50, 10, 10, 10, 10, 10), retard("Beta", 40, None, None, 6, 14, 14),
                  retard(fv.PRODUIT, 90, None, None, 16, 24, 24)]
        sortie = cellules_retard(lignes, 10)
        self.assertEqual(sortie[1]["items"], {"value": 40})
        self.assertEqual(sortie[1]["within_30_days"], masquee(10))               # 6 sous 10
        self.assertEqual(sortie[2]["within_30_days"], masquee(10))               # le produit redonnerait cette cellule (16 - 10)
        self.assertEqual(sortie[2]["items"], {"value": 90})
        self.assertEqual((sortie[2]["later"], sortie[2]["no_history"]), ({"value": 24}, {"value": 24}))

    def test_colonne_du_produit_masquee_des_qu_une_cellule_d_equipe_l_est_meme_a_somme_suffisante(self):
        """Décision 1(b) du 2026-10-23 (D3) : une cellule du produit n'est montrée que si TOUTES les cellules d'équipe de la colonne sont
        visibles, au seuil de la vue comme au seuil relevé."""
        lignes = [retard("Alpha", 50, 10, 10, 10, 10, 10), retard("Beta", 40, 10, None, 10, 10, 10), retard("Gamma", 40, 10, None, 10, 10, 10),
                  retard(fv.PRODUIT, 130, 30, 17, 30, 30, 30)]
        for seuil in (5, 10):
            sortie = cellules_retard(lignes, seuil)
            self.assertEqual(sortie[3]["within_7_days"], masquee(seuil), seuil)  # deux cellules d'équipe masquées, de somme 7 : plus de somme qui compte
            self.assertEqual(sortie[3]["later"], {"value": 30}, seuil)           # colonne dont toutes les cellules d'équipe sont visibles
            self.assertEqual(sortie[3]["items"], {"value": 130}, seuil)

    def test_produit_colonne_masquee_par_une_cellule_d_equipe_visible_a_la_vue_mais_sous_le_seuil_releve(self):
        lignes = [retard("Alpha", 50, 10, 10, 10, 10, 10), retard("Beta", 40, 8, 8, 8, 8, 8), retard(fv.PRODUIT, 90, 18, 18, 18, 18, 18)]
        sortie = cellules_retard(lignes, 5)
        self.assertEqual(sortie[2]["later"], {"value": 18})
        sortie = cellules_retard(lignes, 9)
        self.assertEqual(sortie[2]["later"], masquee(9))                         # 8 sous 9 dans Beta : toute la colonne du produit

    def test_contre_exemple_a_quatre_equipes_produit_des_colonnes_un_a_quatre_masque(self):
        """Décision 1(b) : A = [10, 2, 20, 20, 20], B = [10, 1, 20, 20, 20], C = [20, 20, 2, 10, 20], D = [20, 20, 1, 10, 20]. La vue masque dans chaque
        équipe le petit nombre et la plus petite cellule visible (A et B : colonnes 1 et 2 ; C et D : colonnes 3 et 4). Avant : produit visible sur les
        colonnes 1 et 4 et A2 + B2 = 3 déductible. Après : le produit des colonnes 1 à 4 est masqué, la colonne 5 (toutes visibles) reste."""
        lignes = [retard("A", 72, None, None, 20, 20, 20), retard("B", 71, None, None, 20, 20, 20),
                  retard("C", 72, 20, 20, None, None, 20), retard("D", 71, 20, 20, None, None, 20),
                  retard(fv.PRODUIT, 286, 60, 43, 43, 60, 80)]               # le produit tel que l'ancienne règle le laissait paraître
        sortie = cellules_retard(lignes, 5)
        produit = sortie[4]
        for col in NOMS_RETARD[3:7]:
            self.assertEqual(produit[col], masquee(), col)
        self.assertEqual((produit["items"], produit["no_history"]), ({"value": 286}, {"value": 80}))

    def test_une_equipe_sans_aucune_cellule_visible_masque_tout_le_produit(self):
        """Une équipe dont la ligne entière est masquée (la part cache son détail) n'a aucune cellule visible : le produit n'en montre aucune,
        les items compris."""
        lignes = [retard("Alpha", None, None, None, None, None, None), retard("Beta", 40, 8, 8, 8, 8, 8), retard(fv.PRODUIT, 60, 12, 12, 12, 12, 12)]
        sortie = cellules_retard(lignes, 5)
        for col in NOMS_RETARD[2:]:
            self.assertEqual(sortie[2][col], masquee(), col)

    def test_la_ligne_suit_la_part_au_seuil_releve(self):
        """D5-c : une ligne d'équipe dont le détail de la part n'est pas visible au seuil est masquée tout entière (X6b) ; sans la vue de la part
        en paramètre, la règle ne s'applique pas."""
        part = (["team", "quarter_start", "items", "with_fix_version", "share_percent", "with_fix_version_min"],
                [("Alpha", date(2026, 7, 1), 20, 12, 60.0, None)])
        lignes = [retard("Alpha", 12, None, 6, None, None, None)]
        sortie = cellules_retard(lignes, 10, {fv.VUE_PART: part})
        for col in NOMS_RETARD[2:]:
            self.assertEqual(sortie[0][col], masquee(10), col)
        self.assertEqual(cellules_retard(lignes, 10)[0]["items"], {"value": 12})

    def test_rendu_texte(self):
        texte = fv.rendre(NOMS_RETARD, [retard("Beta", 12, 3, None, None, 9, None), retard("Alpha", 20, 10, None, None, 10, None)], 5, FR)
        lignes = texte.splitlines()
        self.assertTrue(lignes[2].startswith("Alpha"))                           # ordre des équipes, jamais celui d'un compte
        self.assertEqual(lignes[3].split()[:3], ["Beta", "2026-07-01", "12"])
        self.assertEqual(lignes[3].count("masqué"), 5)                           # cellules masquées : 3 sous 5, la plus petite visible, trois nuls


if __name__ == "__main__":
    unittest.main()
