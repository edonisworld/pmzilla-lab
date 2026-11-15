"""
Vue v_team_fix_version_share et sous-commande version-share de tools/flow_views.py (change flow-version-share, spec jira-flow-views
« Ten known views », « Homogeneity reading », « Share columns masked with the counts »).

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -v

Sans base : la lecture de la vue est simulée, le réglage flux.yaml réel n'est jamais lu. Équipes et chiffres inventés.
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

VUE = "v_team_fix_version_share"
NOMS = ["team", "quarter_start", "items", "with_fix_version", "share_percent"]
T1, T2, T3, T4 = date(2025, 10, 1), date(2026, 1, 1), date(2026, 4, 1), date(2026, 7, 1)
FR, EN = Messages(CATALOGS, "fr"), Messages(CATALOGS, "en")
REFERENCE = date(2026, 10, 23)           # date du jour injectée : T2 à T4 sont alors les trois derniers trimestres terminés (T1 sort de la fenêtre)
T5 = date(2026, 10, 1)                   # le trimestre en cours à cette date


def setUpModule():
    global _patch
    _patch = mock.patch.object(fv, "aujourdhui", return_value=REFERENCE)
    _patch.start()


def tearDownModule():
    _patch.stop()


def ligne(equipe, trimestre, items, avec):
    """Une ligne telle que la vue la rend : cellules nulles quand la base masque."""
    part = None if items is None or avec is None else round(100.0 * avec / items, 1)
    return (equipe, trimestre, items, avec, part)


def masquee(equipe, trimestre):
    return (equipe, trimestre, None, None, None)


def serie(equipe, parts):
    """Une équipe sur les trois trimestres (T2 à T4), 100 items par trimestre (la part en % est le nombre avec fix version, de 5 à 95 pour rester
    visible) ; part None = ligne masquée."""
    return [masquee(equipe, q) if p is None else ligne(equipe, q, 100, p) for q, p in zip((T2, T3, T4), parts)]


def lancer(lignes, *argv):
    sortie, erreur = io.StringIO(), io.StringIO()
    with mock.patch.object(fv, "seuil_configure", return_value=fv.PLANCHER), \
            mock.patch.object(fv, "lire", return_value=(NOMS, lignes)) as lecture, \
            contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
        code = fv.main(list(argv))
    return code, sortie.getvalue(), erreur.getvalue(), lecture


class ListeFermee(unittest.TestCase):
    def test_la_vue_est_dans_la_liste_fermee(self):
        self.assertIn(VUE, fv.VUES)
        self.assertEqual(fv.VUE_PART, VUE)
        self.assertEqual(len(fv.VUES), 19)                       # douze depuis version-quality-photo, dix-sept avec les cinq vues de mothra-slices 15.2, dix-huit avec 36.1, dix-neuf avec la couverture (jira-delivery-fields, R-20261102-16 à -36)
        self.assertEqual(len(set(fv.VUES)), 19)
        self.assertNotIn(VUE, fv.VUES_FLOW + fv.VUES_EQUIPES + fv.VUES_QUALITE)
        texte = (RACINE / "db" / "migrations" / "0018_flow_fix_version_share.sql").read_text(encoding="utf-8")
        self.assertIn(f"CREATE VIEW flow.{VUE} AS", texte)

    def test_la_vue_se_lit_sous_le_role_des_vues_de_flow(self):
        requetes, roles = [], []

        class Curseur:
            description = [type("C", (), {"name": n})() for n in NOMS]

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
            fv.lire(VUE)
        self.assertEqual(roles, ["pmzilla_flow_views"])
        self.assertEqual(requetes, [f"SELECT * FROM flow.{VUE}"])

    def test_descriptions_dans_chaque_langue(self):
        for langue, extrait in (("fr", "fix version"), ("en", "fix version")):
            sortie = io.StringIO()
            with mock.patch.object(fv, "seuil_configure", return_value=5), contextlib.redirect_stdout(sortie):
                self.assertEqual(fv.main(["--language", langue, "list"]), 0)
            self.assertIn(VUE, sortie.getvalue())
            self.assertIn(extrait, sortie.getvalue())


class QuatreTrimestresTermines(unittest.TestCase):
    """Décision de l'auteur (R-20261114-49) : la fenêtre est les trois derniers trimestres terminés, sans le trimestre en cours."""

    def test_trimestres_attendus(self):
        self.assertEqual(fv.trimestres_termines(REFERENCE), [T2, T3, T4])
        self.assertEqual(fv.trimestres_termines(date(2026, 10, 1)), [T2, T3, T4])                  # premier jour du trimestre en cours
        self.assertEqual(fv.trimestres_termines(date(2026, 9, 30)), [T1, T2, T3])
        self.assertEqual(fv.trimestres_termines(date(2026, 1, 15)), [date(2025, 4, 1), date(2025, 7, 1), T1])
        self.assertEqual(fv.trimestres_termines(), [T2, T3, T4])                                   # date du jour injectée par le module

    def test_trimestre_en_cours_n_entre_jamais_dans_le_verdict(self):
        lignes = serie("Alpha", [90, 90, 90]) + [ligne("Alpha", T5, 100, 10)]                      # le trimestre en cours est bas : sans effet
        self.assertEqual(fv.verdict_part(NOMS, lignes, 80)["verdict"], "homogeneous")
        lignes = serie("Alpha", [90, 90, 90]) + [ligne("Alpha", T5, 100, 95)]
        self.assertEqual(fv.verdict_part(NOMS, lignes, 80)["verdict"], "homogeneous")

    def test_trimestre_en_cours_ne_remplace_pas_un_trimestre_termine_manquant(self):
        lignes = serie("Alpha", [90, 90, 90])[:2] + [ligne("Alpha", T5, 100, 95)]
        v = fv.verdict_part(NOMS, lignes, 80)
        self.assertEqual(v["verdict"], "not_established")                                          # trois terminés attendus, deux présents
        self.assertEqual(v["not_established"], ["Alpha"])

    def test_trimestre_en_cours_masque_ou_non_ne_change_ni_la_date_ni_le_verdict(self):
        lignes = serie("Alpha", [60, 90, 95]) + [masquee("Alpha", T5)]
        v = fv.verdict_part(NOMS, lignes, 80)
        self.assertEqual((v["verdict"], v["since"]), ("since", T3))
        lignes = serie("Alpha", [90, 90, 90]) + [ligne("Alpha", T5, 100, 10)]
        self.assertIsNone(fv.verdict_part(NOMS, lignes, 80)["since"])

    def test_trimestre_trop_ancien_ignore(self):
        lignes = serie("Alpha", [90, 90, 90]) + [ligne("Alpha", date(2025, 7, 1), 100, 5)]
        self.assertEqual(fv.verdict_part(NOMS, lignes, 80)["verdict"], "homogeneous")

    def test_date_de_reference_injectee_en_parametre(self):
        lignes = serie("Alpha", [90, 90, 90])
        v = fv.verdict_part(NOMS, lignes, 80, reference=date(2027, 1, 5))                          # fenêtre T3..T5 : T2 sort, T5 manque
        self.assertEqual(v["verdict"], "not_established")


class Verdict(unittest.TestCase):
    def test_verdict_homogene(self):
        lignes = serie("Alpha", [90, 95, 95]) + serie("Beta", [80, 90, 85])
        v = fv.verdict_part(NOMS, lignes, 80)
        self.assertEqual(v["verdict"], "homogeneous")
        self.assertIsNone(v["since"])
        self.assertEqual(v["not_established"], [])

    def test_verdict_depuis_une_date(self):
        lignes = serie("Alpha", [60, 90, 95]) + serie("Beta", [70, 85, 90])
        v = fv.verdict_part(NOMS, lignes, 80)
        self.assertEqual(v["verdict"], "since")
        self.assertEqual(v["since"], T3)                       # Alpha et Beta atteignent le plancher à partir du deuxième trimestre de la fenêtre (T3)

    def test_verdict_non_homogene(self):
        lignes = serie("Alpha", [90, 90, 90]) + serie("Beta", [90, 90, 60])
        v = fv.verdict_part(NOMS, lignes, 80)
        self.assertEqual(v["verdict"], "not_homogeneous")
        self.assertIsNone(v["since"])

    def test_dernier_trimestre_non_masque_decide(self):
        lignes = serie("Alpha", [90, 90, 90]) + serie("Beta", [90, 60, None])
        self.assertEqual(fv.verdict_part(NOMS, lignes, 80)["verdict"], "not_homogeneous")

    def test_trimestre_masque_rend_l_equipe_non_etablie_sans_casser_les_autres(self):
        lignes = serie("Alpha", [90, None, 90]) + serie("Beta", [90, 90, 90])
        v = fv.verdict_part(NOMS, lignes, 80)
        self.assertEqual(v["verdict"], "homogeneous")
        self.assertEqual(v["not_established"], ["Alpha"])      # un trimestre illisible : pas « homogène sur les trois trimestres »

    def test_moins_de_quatre_trimestres_non_etablie(self):
        lignes = serie("Alpha", [90, 90, 90])[:2] + serie("Beta", [90, 90, 90])
        v = fv.verdict_part(NOMS, lignes, 80)
        self.assertEqual(v["verdict"], "homogeneous")
        self.assertEqual(v["not_established"], ["Alpha"])

    def test_seule_equipe_incomplete_rien_d_etabli(self):
        v = fv.verdict_part(NOMS, serie("Alpha", [90, None, 90]), 80)
        self.assertEqual(v["verdict"], "not_established")
        self.assertEqual(v["not_established"], ["Alpha"])
        v = fv.verdict_part(NOMS, serie("Alpha", [90, 90, 90])[:2], 80)
        self.assertEqual(v["verdict"], "not_established")

    def test_equipe_incomplete_avec_echec_visible_reste_non_homogene(self):
        lignes = serie("Alpha", [None, 90, 60]) + serie("Beta", [90, 90, 90])
        self.assertEqual(fv.verdict_part(NOMS, lignes, 80)["verdict"], "not_homogeneous")

    def test_seuil_releve_rappele_sur_la_sortie_d_erreur(self):
        sortie, erreur = io.StringIO(), io.StringIO()
        with mock.patch.object(fv, "seuil_configure", return_value=10), \
                mock.patch.object(fv, "lire", return_value=(NOMS, serie("Alpha", [90, 90, 90]))), \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            self.assertEqual(fv.main(["version-share"]), 0)
        self.assertIn(FR("min_cell_raised", min_cell=10, masked=FR("masked")), erreur.getvalue())
        code, _, erreur_simple, _ = lancer(serie("Alpha", [90, 90, 90]), "version-share")
        self.assertEqual(erreur_simple, "")                    # seuil au plancher : rien à rappeler

    def test_equipe_toute_masquee(self):
        lignes = serie("Alpha", [90, 90, 90]) + serie("Petite", [None, None, None])
        v = fv.verdict_part(NOMS, lignes, 80)
        self.assertEqual(v["verdict"], "homogeneous")
        self.assertEqual(v["not_established"], ["Petite"])     # laissée de côté : non établie, jamais comptée comme conforme ni non

    def test_toutes_les_equipes_masquees_rien_d_etabli(self):
        v = fv.verdict_part(NOMS, serie("Petite", [None] * 3), 80)
        self.assertEqual(v["verdict"], "not_established")
        self.assertEqual(v["not_established"], ["Petite"])

    def test_la_ligne_du_produit_n_est_pas_une_equipe(self):
        lignes = serie("Alpha", [90, 90, 90]) + serie("(produit)", [10, 10, 10])
        self.assertEqual(fv.verdict_part(NOMS, lignes, 80)["verdict"], "homogeneous")

    def test_plancher_atteint_compte(self):
        self.assertEqual(fv.verdict_part(NOMS, serie("Alpha", [80, 80, 80]), 80)["verdict"], "homogeneous")

    def test_seuil_en_option(self):
        lignes = serie("Alpha", [85, 85, 85])
        code, sortie, _, _ = lancer(lignes, "--language", "en", "version-share")
        self.assertEqual(code, 0)
        self.assertIn("homogeneous over the three quarters", sortie)
        self.assertIn("80", sortie)                            # plancher par défaut
        code, sortie, _, _ = lancer(lignes, "--language", "en", "version-share", "--floor", "90")
        self.assertEqual(code, 0)
        self.assertIn("not homogeneous", sortie)
        self.assertIn("90", sortie)


NOMS6 = NOMS + ["with_fix_version_min"]


def avec_borne(equipe, trimestre, items, borne):
    """Ligne de la vue pour une équipe à moins de 5 sans version : compte exact et part masqués, borne basse publiée."""
    return (equipe, trimestre, items, None, None, borne)


def complete(equipe, trimestre, items, avec):
    return ligne(equipe, trimestre, items, avec) + (None,)


def serie6(equipe, lignes_par_trimestre):
    return [f(equipe, q) for f, q in zip(lignes_par_trimestre, (T2, T3, T4))]


class BorneBasse(unittest.TestCase):
    """Décision de l'auteur du 2026-10-23 (D10) : la borne est un chiffre publié par la vue, jamais une estimation de la session."""

    def test_borne_au_plancher_donne_une_equipe_au_dessus(self):
        borne = lambda e, q: avec_borne(e, q, 20, 16)                    # 16 / 20 = 80 %
        lignes = serie6("Alpha", [borne, lambda e, q: complete(e, q, 50, 45), borne])
        v = fv.verdict_part(NOMS6, lignes, 80)
        self.assertEqual(v["verdict"], "homogeneous")
        self.assertEqual(v["not_established"], [])

    def test_borne_sous_le_plancher_trimestre_non_etabli(self):
        borne = lambda e, q: avec_borne(e, q, 20, 16)
        lignes = serie6("Alpha", [borne] * 3)
        v = fv.verdict_part(NOMS6, lignes, 90)                              # 80 % publié, plancher 90 : rien d'établi
        self.assertEqual(v["verdict"], "not_established")
        self.assertEqual(v["not_established"], ["Alpha"])

    def test_borne_sous_le_plancher_dans_un_trimestre_rend_l_equipe_non_etablie(self):
        ok = lambda e, q: complete(e, q, 50, 45)
        lignes = serie6("Alpha", [ok, ok, lambda e, q: avec_borne(e, q, 20, 16)]) + serie6("Beta", [ok] * 3)
        v = fv.verdict_part(NOMS6, lignes, 90)
        self.assertEqual(v["verdict"], "homogeneous")
        self.assertEqual(v["not_established"], ["Alpha"])

    def test_la_borne_ne_remplace_pas_un_echec_visible(self):
        ok = lambda e, q: complete(e, q, 50, 45)
        lignes = serie6("Alpha", [ok, ok, lambda e, q: complete(e, q, 40, 20)])
        self.assertEqual(fv.verdict_part(NOMS6, lignes, 80)["verdict"], "not_homogeneous")

    def test_affichage_de_la_borne_sans_valeur_exacte(self):
        texte = fv.rendre(NOMS6, [avec_borne("Alpha", T4, 20, 16)], 5, FR)
        self.assertEqual(texte.splitlines()[-1].split(), ["Alpha", "2026-07-01", "20", "masqué", "masqué", "≥", "16"])
        self.assertIn("with_fix_version_min", texte.splitlines()[0])

    def test_borne_non_affichee_si_les_items_sont_masques(self):
        texte = fv.rendre(NOMS6, [avec_borne("Alpha", T4, 20, 16)], 25, FR)       # seuil relevé au-dessus des items
        self.assertEqual(texte.splitlines()[-1].split(), ["Alpha", "2026-07-01", "masqué", "masqué", "masqué"])

    def test_cellule_sans_borne_affichee_vide(self):
        texte = fv.rendre(NOMS6, [complete("Alpha", T4, 40, 20)], 5, FR)
        self.assertEqual(texte.splitlines()[-1].split(), ["Alpha", "2026-07-01", "40", "20", "50.0"])

    def test_la_borne_ne_change_pas_les_comptes_masques(self):
        self.assertNotIn("with_fix_version_min", fv.COLONNES_COMPTE)       # colonne de la vue, traitée à part : jamais « masqué » en soi


class SansEquipe(unittest.TestCase):
    SANS = "(sans équipe)"

    def test_ecartee_du_verdict(self):
        lignes = serie("Alpha", [90, 90, 90]) + serie(self.SANS, [10, 10, 10])
        v = fv.verdict_part(NOMS, lignes, 80)
        self.assertEqual(v["verdict"], "homogeneous")
        self.assertEqual(v["not_established"], [])             # ni comptée, ni non établie : hors du verdict

    def test_seule_elle_rien_d_etabli(self):
        self.assertEqual(fv.verdict_part(NOMS, serie(self.SANS, [90] * 3), 80)["verdict"], "not_established")

    def test_ligne_a_part_dans_la_sortie(self):
        lignes = serie("Alpha", [90, 90, 90]) + serie(self.SANS, [50, None, 70])
        _, fr, _, _ = lancer(lignes, "version-share")
        self.assertIn("homogène sur les trois trimestres", fr)
        ligne_a_part = [l for l in fr.splitlines() if self.SANS in l]
        self.assertEqual(len(ligne_a_part), 1)
        self.assertIn("50.0", ligne_a_part[0])
        self.assertIn("masqué", ligne_a_part[0])
        _, en, _, _ = lancer(lignes, "--language", "en", "version-share")
        self.assertIn("outside the outcome", [l for l in en.splitlines() if self.SANS in l][0])

    def test_pas_de_ligne_sans_equipe_quand_elle_est_absente(self):
        _, fr, _, _ = lancer(serie("Alpha", [90] * 3), "version-share")
        self.assertNotIn("(sans équipe)", fr)


class SousCommande(unittest.TestCase):
    def test_lit_la_seule_vue_de_la_part_et_ne_montre_aucun_compte(self):
        lignes = serie("Alpha", [90, 90, 90])
        code, sortie, _, lecture = lancer(lignes, "version-share")
        self.assertEqual(code, 0)
        lecture.assert_called_once_with(VUE)
        self.assertIn("homogène sur les trois trimestres", sortie)

    def test_depuis_une_date_dit_la_date_et_equipe_non_etablie_est_nommee(self):
        lignes = serie("Alpha", [60, 90, 95]) + serie("Petite", [None] * 3)
        _, fr, _, _ = lancer(lignes, "version-share")
        self.assertIn("depuis le 2026-04-01", fr)
        self.assertIn("Petite", fr)
        self.assertIn("non établie", fr)
        _, en, _, _ = lancer(lignes, "--language", "en", "version-share")
        self.assertIn("since 2026-04-01", en)
        self.assertIn("not established", en)

    def test_non_homogene_dans_chaque_langue(self):
        lignes = serie("Alpha", [90, 90, 60])
        self.assertIn("non homogène", lancer(lignes, "version-share")[1])
        self.assertIn("not homogeneous", lancer(lignes, "--language", "en", "version-share")[1])

    def test_plancher_hors_zero_a_cent_refuse(self):
        for valeur in ("0", "101", "-5"):
            with mock.patch.object(db, "connect", side_effect=AssertionError("pas de connexion")):
                code, sortie, erreur, _ = lancer([], "version-share", "--floor", valeur)
            self.assertEqual(code, 1, valeur)
            self.assertEqual(sortie, "")
            self.assertTrue(erreur)

    def test_erreur_de_base(self):
        with mock.patch.object(fv, "seuil_configure", return_value=5), \
                mock.patch.object(db, "connect", side_effect=db.ErreurBase("injoignable")):
            erreur = io.StringIO()
            with contextlib.redirect_stderr(erreur):
                self.assertEqual(fv.main(["version-share"]), 1)
        self.assertIn("injoignable", erreur.getvalue())


class Masquage(unittest.TestCase):
    def test_seuil_releve_masque_la_part(self):
        # 12 items, 9 avec fix version : avec = 9 < 10, la part (et le compte) sont masqués ; 3 sans version, sous 10 aussi
        texte = fv.rendre(NOMS, [ligne("Alpha", T4, 12, 9)], 10, FR)
        self.assertIn("2026-07-01", texte)
        corps = texte.splitlines()[-1].split()
        self.assertEqual(corps[-2:], ["masqué", "masqué"])
        self.assertEqual(corps[2], "12")                       # les items restent visibles

    def test_part_visible_quand_tout_atteint_le_seuil(self):
        texte = fv.rendre(NOMS, [ligne("Alpha", T4, 40, 20)], 10, FR)
        self.assertEqual(texte.splitlines()[-1].split()[-2:], ["20", "50.0"])

    def test_part_masquee_quand_le_compte_sans_version_est_sous_le_seuil(self):
        texte = fv.rendre(NOMS, [ligne("Alpha", T4, 20, 14)], 5, FR)      # 6 sans version : visible au seuil 5
        self.assertEqual(texte.splitlines()[-1].split()[-2:], ["14", "70.0"])
        texte = fv.rendre(NOMS, [ligne("Alpha", T4, 20, 14)], 8, FR)      # seuil relevé : 6 sans version < 8, donc masqué
        self.assertEqual(texte.splitlines()[-1].split()[-2:], ["masqué", "masqué"])
        texte = fv.rendre(NOMS, [ligne("Alpha", T4, 20, 16)], 5, EN)      # 4 sans version < 5
        self.assertEqual(texte.splitlines()[-1].split()[-2:], ["masked", "masked"])

    def test_cellule_nulle_de_la_vue_reste_masquee(self):
        texte = fv.rendre(NOMS, [masquee("Petite", T4)], 5, FR)
        self.assertEqual(texte.splitlines()[-1].split()[-3:], ["masqué", "masqué", "masqué"])

    def dernier_produit(self, lignes, seuil):
        texte = fv.rendre(NOMS, lignes, seuil, FR)
        return [l.split() for l in texte.splitlines() if l.startswith("(produit)")][0]

    def test_seuil_releve_une_equipe_masquee_masque_la_ligne_produit(self):
        # seuil 10 : l'équipe B (7 items) est masquée par Python ; le produit (27 items, 13 avec) la redonnerait par différence
        lignes = [ligne("A", T4, 20, 10), ligne("B", T4, 7, 3), ligne("(produit)", T4, 27, 13)]
        self.assertEqual(self.dernier_produit(lignes, 10)[2:], ["masqué", "masqué", "masqué"])

    def test_seuil_releve_somme_sous_le_seuil_masque_la_ligne_produit(self):
        lignes = [ligne("A", T4, 20, 10), ligne("B", T4, 4, 2), ligne("C", T4, 4, 2), ligne("(produit)", T4, 28, 14)]
        self.assertEqual(self.dernier_produit(lignes, 10)[2:], ["masqué", "masqué", "masqué"])

    def test_seuil_releve_somme_au_seuil_masque_quand_meme_la_ligne_produit(self):
        """D3 (change masking-sums) : une cellule du produit exige toutes les cellules d'équipe de sa colonne, quelle que soit la somme masquée
        (avant, une somme masquée de 12 au seuil de 10 laissait le produit visible)."""
        lignes = [ligne("A", T4, 20, 10), ligne("B", T4, 6, 3), ligne("C", T4, 6, 3), ligne("(produit)", T4, 32, 16)]
        self.assertEqual(self.dernier_produit(lignes, 10)[2:], ["masqué", "masqué", "masqué"])
        lignes = [ligne("A", T4, 20, 10), ligne("B", T4, 20, 10), ligne("(produit)", T4, 40, 20)]
        self.assertEqual(self.dernier_produit(lignes, 10)[2:], ["40", "20", "50.0"])

    def test_ligne_produit_d_un_autre_trimestre_intacte(self):
        lignes = [ligne("A", T3, 20, 10), ligne("B", T3, 20, 10), ligne("(produit)", T3, 40, 20),
                  ligne("A", T4, 20, 10), ligne("B", T4, 7, 3), ligne("(produit)", T4, 27, 13)]
        lignes_produit = [l.split() for l in fv.rendre(NOMS, lignes, 10, FR).splitlines() if l.startswith("(produit)")]
        self.assertEqual(lignes_produit[0][2:], ["40", "20", "50.0"])
        self.assertEqual(lignes_produit[1][2:], ["masqué", "masqué", "masqué"])

    def test_la_part_n_est_pas_une_colonne_de_comptage(self):
        self.assertIn("items", fv.COLONNES_COMPTE)
        self.assertIn("with_fix_version", fv.COLONNES_COMPTE)
        self.assertNotIn("share_percent", fv.COLONNES_COMPTE)


if __name__ == "__main__":
    unittest.main()
