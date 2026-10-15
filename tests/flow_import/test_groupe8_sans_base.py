"""Groupe 8 de jira-gdpr-alignment, sans base : fonctions pures de tools/flow_import.py, lecteur des colonnes « Declared Label » et
« Fix Version », refus d'un jeu d'exports incomplet avant toute connexion, lignes de comptes.

    bash tests/run_all.sh flow_import </dev/null

Specs : jira-flow-import (Out-of-export mark, Mark only with a complete export set, Declared labels and fix versions imported,
Tickets past retention not imported). Données inventées (PROJ-n, étiquettes et versions génériques). Les tests qui écrivent dans la
base jetable sont dans test_groupe8_base.py (sautés sans Docker).
"""
import contextlib
import datetime as dt
import io
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import csv_factices as cf
import flow_export_reader as lecteur
import flow_import
import flux_jira
from messages import Messages
from flow_import_messages import CATALOGS

UTC = dt.timezone.utc
ZONE = dt.timezone(dt.timedelta(hours=2))
CREE = dt.datetime(2026, 1, 2, 8, 30, tzinfo=UTC)
ENTETE = cf.ENTETE + ["Declared Label", "Fix Version"]
DECLAREES = {"cycle": {"prefix": "lbl-", "labels": ["lbl-a", "lbl-b"]}}


def e(date, sens, valeur):
    return [date, sens, valeur]


class ConstruirePeriodes(unittest.TestCase):
    def periodes(self, evenements, presentes=None, admises=None, cree=CREE):
        return flow_import.construire_periodes(evenements, presentes, cree, ZONE, admises)

    def test_ajout_puis_retrait_une_periode_fermee(self):
        r = self.periodes([e("2026-02-01T10:00:00.000+0200", "add", "lbl-a"), e("2026-03-01T10:00:00.000+0200", "remove", "lbl-a")])
        self.assertEqual(r, [("lbl-a", dt.datetime(2026, 2, 1, 8, 0, tzinfo=UTC), dt.datetime(2026, 3, 1, 8, 0, tzinfo=UTC))])

    def test_ajout_sans_retrait_periode_ouverte(self):
        r = self.periodes([e("2026-02-01T10:00:00.000+0200", "add", "lbl-a")], ["lbl-a"])
        self.assertEqual(r, [("lbl-a", dt.datetime(2026, 2, 1, 8, 0, tzinfo=UTC), None)])

    def test_present_dans_l_export_sans_evenement_ouvre_a_la_creation(self):
        self.assertEqual(self.periodes([], ["lbl-a", "1.0"]), [("1.0", CREE, None), ("lbl-a", CREE, None)])

    def test_present_sans_evenement_pour_cette_valeur_meme_si_d_autres_ont_des_evenements(self):
        r = self.periodes([e("2026-02-01T10:00:00.000+0200", "add", "lbl-b")], ["lbl-a", "lbl-b"])
        self.assertEqual(r, [("lbl-a", CREE, None), ("lbl-b", dt.datetime(2026, 2, 1, 8, 0, tzinfo=UTC), None)])

    def test_retrait_puis_valeur_encore_dans_l_export_ne_rouvre_pas(self):
        """Les événements font foi : une valeur retirée ne revient pas parce que l'export du jour la montre encore."""
        r = self.periodes([e("2026-02-01T10:00:00.000+0200", "add", "x"), e("2026-03-01T10:00:00.000+0200", "remove", "x")], ["x"])
        self.assertEqual(len(r), 1)
        self.assertIsNotNone(r[0][2])

    def test_deux_cycles_ajout_retrait_ajout(self):
        r = self.periodes([e("2026-02-01T10:00:00+0200", "add", "x"), e("2026-03-01T10:00:00+0200", "remove", "x"),
                           e("2026-04-01T10:00:00+0200", "add", "x")])
        self.assertEqual([(d.month, f.month if f else None) for _, d, f in r], [(2, 3), (4, None)])

    def test_double_ajout_ignore(self):
        r = self.periodes([e("2026-02-01T10:00:00+0200", "add", "x"), e("2026-02-05T10:00:00+0200", "add", "x")])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0][1].day, 1)

    def test_retrait_sans_ajout_ferme_une_periode_ouverte_a_la_creation(self):
        r = self.periodes([e("2026-03-01T10:00:00+0200", "remove", "x")])
        self.assertEqual(r, [("x", CREE, dt.datetime(2026, 3, 1, 8, 0, tzinfo=UTC))])

    def test_retrait_avant_la_creation_ramene_a_la_creation(self):
        r = self.periodes([e("2025-12-01T10:00:00+0200", "remove", "x")])
        self.assertEqual(r, [("x", CREE, CREE)])        # la contrainte de la table exige removed_at >= added_at

    def test_valeur_non_admise_jamais_stockee(self):
        r = self.periodes([e("2026-02-01T10:00:00+0200", "add", "autre"), e("2026-02-01T10:00:00+0200", "add", "lbl-a")],
                          ["autre", "lbl-a"], admises={"lbl-a"})
        self.assertEqual([p[0] for p in r], ["lbl-a"])

    def test_sans_bloc_declare_rien_n_est_admis(self):
        self.assertEqual(self.periodes([e("2026-02-01T10:00:00+0200", "add", "lbl-a")], ["lbl-a"], admises=set()), [])

    def test_date_illisible_ecartee(self):
        self.assertEqual(self.periodes([e("pas une date", "add", "x")]), [])

    def test_colonne_absente_et_aucun_evenement(self):
        self.assertEqual(self.periodes([], None), [])

    def test_date_sans_decalage_lue_dans_le_fuseau_d_export(self):
        r = self.periodes([e("2026-02-01T10:00:00", "add", "x")])
        self.assertEqual(r[0][1], dt.datetime(2026, 2, 1, 8, 0, tzinfo=UTC))


class HorsConservation(unittest.TestCase):
    MAINTENANT = dt.datetime(2026, 10, 13, 12, 0, tzinfo=UTC)

    def ticket(self, cle, resolu):
        return {"cle": cle, "resolu": resolu}

    def test_resolu_avant_la_duree_ecarte(self):
        vieux = self.ticket("PROJ-1", self.MAINTENANT - dt.timedelta(days=366))
        gardes, n = flow_import.ecarter_hors_conservation([vieux], 365, self.MAINTENANT)
        self.assertEqual((gardes, n), ([], 1))

    def test_limite_exacte_et_recent_gardes(self):
        limite = self.ticket("PROJ-1", self.MAINTENANT - dt.timedelta(days=365))
        recent = self.ticket("PROJ-2", self.MAINTENANT - dt.timedelta(days=10))
        gardes, n = flow_import.ecarter_hors_conservation([limite, recent], 365, self.MAINTENANT)
        self.assertEqual((len(gardes), n), (2, 0))

    def test_non_resolu_toujours_garde(self):
        gardes, n = flow_import.ecarter_hors_conservation([self.ticket("PROJ-1", None)], 1, self.MAINTENANT)
        self.assertEqual((len(gardes), n), (1, 0))

    def test_la_duree_est_celle_donnee(self):
        t = self.ticket("PROJ-1", self.MAINTENANT - dt.timedelta(days=40))
        self.assertEqual(flow_import.ecarter_hors_conservation([t], 30, self.MAINTENANT)[1], 1)
        self.assertEqual(flow_import.ecarter_hors_conservation([t], 90, self.MAINTENANT)[1], 0)


class JeuComplet(unittest.TestCase):
    def reglages(self, **jql):
        return cf.reglages(**jql)

    def test_une_requete_nommee_par_fichier_du_meme_jour(self):
        r = self.reglages(jql_exports={"alpha": "a", "beta-2": "b"})
        self.assertTrue(flow_import.jeu_complet(["x/api-beta-2-2026-10-13.csv", "api-alpha-2026-10-13.csv"], r))

    def test_un_fichier_manquant(self):
        r = self.reglages(jql_exports={"alpha": "a", "beta": "b"})
        self.assertFalse(flow_import.jeu_complet(["api-alpha-2026-10-13.csv"], r))

    def test_deux_jours(self):
        r = self.reglages(jql_exports={"alpha": "a", "beta": "b"})
        self.assertFalse(flow_import.jeu_complet(["api-alpha-2026-10-13.csv", "api-beta-2026-10-12.csv"], r))

    def test_fichier_en_double_ou_en_trop(self):
        r = self.reglages(jql_exports={"alpha": "a", "beta": "b"})
        self.assertFalse(flow_import.jeu_complet(["api-alpha-2026-10-13.csv", "api-alpha-2026-10-13.csv"], r))
        self.assertFalse(flow_import.jeu_complet(["api-alpha-2026-10-13.csv", "api-beta-2026-10-13.csv",
                                                  "api-gamma-2026-10-13.csv"], r))

    def test_requete_inconnue(self):
        r = self.reglages(jql_exports={"alpha": "a", "beta": "b"})
        self.assertFalse(flow_import.jeu_complet(["api-alpha-2026-10-13.csv", "api-gamma-2026-10-13.csv"], r))

    def test_fichier_qui_n_est_pas_un_export_de_l_api(self):
        r = self.reglages(jql_exports={"alpha": "a"})
        self.assertFalse(flow_import.jeu_complet(["export.csv"], r))
        self.assertFalse(flow_import.jeu_complet(["api-alpha-13-10-2026.csv"], r))

    def test_requete_unique_sans_nom(self):
        r = self.reglages(jql_export="project = X", jql_exports=None)
        self.assertTrue(flow_import.jeu_complet(["api-2026-10-13.csv"], r))
        self.assertFalse(flow_import.jeu_complet(["api-alpha-2026-10-13.csv"], r))

    def test_aucune_requete_dans_les_reglages(self):
        r = self.reglages(jql_exports=None, jql_export="")
        self.assertFalse(flow_import.jeu_complet(["api-2026-10-13.csv"], r))


class LecteurColonnes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dossier = Path(self.temp.name)

    def lire(self, lignes, entete=ENTETE, periodes=True, declarees=DECLAREES):
        chemin = cf.ecrire(self.dossier / "a.csv", lignes, entete)
        return lecteur.lire_exports([str(chemin)], cf.reglages(declared_labels=declarees), periodes=periodes)

    def ligne(self, cle="PROJ-1", **autres):
        return cf.ligne(cle, **autres)

    def lire_colonnes(self, valeurs_par_colonne):
        """Un CSV où chaque colonne répétée reçoit ses valeurs dans l'ordre (cf.ecrire ne gère que Team répétée)."""
        import csv
        chemin = self.dossier / "b.csv"
        with open(chemin, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Issue key", "Issue Type", "Status", "Created", "Updated"] + list(valeurs_par_colonne))
            w.writerow(["PROJ-1", "Story", "Open", "02/Jan/2026 09:30", "06/Jan/2026 11:15"] + list(valeurs_par_colonne.values()))
        return lecteur.lire_exports([str(chemin)], cf.reglages(declared_labels=DECLAREES), periodes=True)

    def test_colonnes_repetees_lues_et_dedoublonnees(self):
        r = self.lire([self.ligne(**{"Declared Label": "lbl-a"})])
        self.assertEqual(r["tickets"][0]["etiquettes"], ["lbl-a"])
        self.assertEqual(r["tickets"][0]["versions"], [])

    def test_deux_colonnes_d_etiquette_et_de_version(self):
        import csv
        chemin = self.dossier / "c.csv"
        with open(chemin, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Issue key", "Issue Type", "Status", "Created", "Updated",
                        "Declared Label", "Declared Label", "Fix Version", "Fix Version"])
            w.writerow(["PROJ-1", "Story", "Open", "02/Jan/2026 09:30", "06/Jan/2026 11:15", "lbl-a", "lbl-b", "1.0", "1.0"])
        r = lecteur.lire_exports([str(chemin)], cf.reglages(declared_labels=DECLAREES), periodes=True)
        self.assertEqual(r["tickets"][0]["etiquettes"], ["lbl-a", "lbl-b"])
        self.assertEqual(r["tickets"][0]["versions"], ["1.0"])

    def test_etiquette_non_declaree_refusee_et_comptee_sans_son_nom(self):
        r = self.lire([self.ligne("PROJ-1", **{"Declared Label": "lbl-a"}), self.ligne("PROJ-2", **{"Declared Label": "ZZ-inconnue"})])
        self.assertEqual(r["etiquettes_refusees"], 1)
        self.assertEqual([t["cle"] for t in r["tickets"]], ["PROJ-1", "PROJ-2"])        # la ligne est importée, sans l'étiquette
        self.assertEqual(r["tickets"][1]["etiquettes"], [])
        self.assertNotIn("ZZ-inconnue", repr(r))

    def test_sans_bloc_declare_toutes_refusees(self):
        r = self.lire([self.ligne(**{"Declared Label": "lbl-a"})], declarees=None)
        self.assertEqual((r["etiquettes_refusees"], r["tickets"][0]["etiquettes"]), (1, []))

    def test_cellule_vide_ni_stockee_ni_refusee(self):
        r = self.lire([self.ligne()])
        self.assertEqual((r["etiquettes_refusees"], r["tickets"][0]["etiquettes"], r["tickets"][0]["versions"]), (0, [], []))

    def test_colonnes_absentes_donnent_none(self):
        r = self.lire([self.ligne()], entete=cf.ENTETE)
        self.assertEqual((r["tickets"][0]["etiquettes"], r["tickets"][0]["versions"], r["etiquettes_refusees"]), (None, None, 0))

    def test_en_tete_po_ignore_et_jamais_stocke(self):
        r = self.lire([self.ligne(PO="ZZ-personne-distinctive")], entete=ENTETE + ["PO"])
        self.assertNotIn("ZZ-personne-distinctive", repr(r))
        self.assertNotIn("PO", r["tickets"][0])
        self.assertEqual(len(r["tickets"]), 1)

    def test_en_tete_insensible_a_la_casse(self):
        r = self.lire_colonnes({"DECLARED LABEL": "lbl-a", " fix version ": "1.0"})
        self.assertEqual((r["tickets"][0]["etiquettes"], r["tickets"][0]["versions"]), (["lbl-a"], ["1.0"]))

    def test_sans_periodes_le_resultat_ne_porte_ni_etiquette_ni_version(self):
        r = self.lire([self.ligne(**{"Declared Label": "lbl-a", "Fix Version": "9.9"})], periodes=False)
        for chaine in ("lbl-a", "9.9", "'etiquettes':", "'versions':"):
            self.assertNotIn(chaine, repr(r))
        self.assertEqual(r["etiquettes_refusees"], 0)

    def test_comptes_fusionnes_sur_les_lignes_retenues(self):
        chemin_a = cf.ecrire(self.dossier / "a.csv", [self.ligne(**{"Declared Label": "zz"})], ENTETE)
        chemin_b = cf.ecrire(self.dossier / "b.csv", [self.ligne()], ENTETE)
        r = lecteur.lire_exports([str(chemin_a), str(chemin_b)], cf.reglages(declared_labels=DECLAREES), periodes=True)
        self.assertEqual(r["etiquettes_refusees"], 0)       # le dernier fichier l'emporte : la ligne refusée n'est plus retenue


class RefusJeuIncomplet(unittest.TestCase):
    """Le refus a lieu avant toute connexion et avant toute lecture des fichiers : ni la base ni le disque ne sont touchés."""

    def lancer(self, chemins, jql_exports, *options, langue=None):
        reglages = cf.reglages(jql_exports=jql_exports)
        sortie, erreur = io.StringIO(), io.StringIO()
        code = 0
        argv = list(chemins) + list(options) + (["--language", langue] if langue else [])
        with unittest.mock.patch.object(flux_jira, "config", return_value=reglages), \
                unittest.mock.patch.object(flow_import.db, "connect", side_effect=AssertionError("connexion")) as connexion, \
                unittest.mock.patch.object(flow_import.lecteur, "lire_exports", side_effect=AssertionError("lecture")) as lecture, \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            try:
                flow_import.main(argv)
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
        self.assertEqual((connexion.call_count, lecture.call_count), (0, 0))
        return code, sortie.getvalue(), erreur.getvalue()

    def test_un_fichier_manquant(self):
        code, sortie, erreur = self.lancer(["api-alpha-2026-10-13.csv"], {"alpha": "a", "beta": "b"}, "--mark-absent", langue="en")
        self.assertEqual(code, 1)
        self.assertIn("incomplete export set: --mark-absent refused", sortie + erreur)

    def test_fichiers_de_deux_jours(self):
        code, sortie, erreur = self.lancer(["api-alpha-2026-10-13.csv", "api-beta-2026-10-12.csv"], {"alpha": "a", "beta": "b"},
                                           "--mark-absent")
        self.assertEqual(code, 1)
        self.assertIn("jeu d'exports incomplet : --mark-absent refusé", sortie + erreur)

    def test_le_refus_ne_nomme_ni_requete_ni_fichier(self):
        code, sortie, erreur = self.lancer(["zzfichier-distinctif.csv"], {"zzrequete": "a", "beta": "b"}, "--mark-absent",
                                           "--dry-run")
        self.assertEqual(code, 1)
        for chaine in ("zzfichier", "zzrequete", "beta", ".csv"):
            self.assertNotIn(chaine, sortie + erreur)


class Comptes(unittest.TestCase):
    COMPTES = {"read": 3, "unreadable": 0, "teams": 0, "links_added": 0, "links_removed": 0, "inserted": 1, "updated": 0,
               "unchanged": 2, "past_retention": 4, "refused": 5, "marked": 6, "back": 7, "added": 0, "orphans": 0,
               "transitions_unreadable": 0, "history_marked": 0, "label_periods": 8, "version_periods": 9}

    def sortie(self, langue, historique=False):
        tampon = io.StringIO()
        with contextlib.redirect_stdout(tampon):
            flow_import.afficher(self.COMPTES, historique, False, Messages(CATALOGS, langue))
        return tampon.getvalue()

    def test_lignes_de_comptes_en_anglais(self):
        sortie = self.sortie("en")
        for ligne in ("Tickets out of the export: 6 marked, 7 back", "tickets past retention, skipped: 4"):
            self.assertIn(ligne, sortie.splitlines())

    def test_lignes_de_comptes_en_francais(self):
        sortie = self.sortie("fr")
        for ligne in ("Tickets sortis de l'export : 6 marqués, 7 revenus", "tickets au-delà de la conservation, ignorés : 4"):
            self.assertIn(ligne, sortie.splitlines())

    def test_valeurs_refusees_comptees(self):
        self.assertIn("refusées (non déclarées dans les réglages) : 5", self.sortie("fr"))

    def test_periodes_seulement_avec_l_historique(self):
        self.assertNotIn("8", self.sortie("en").split("Tickets read")[1].split("Label values")[0][-5:])
        self.assertIn("declared labels: 8; versions: 9", self.sortie("en", historique=True))
        self.assertNotIn("declared labels:", self.sortie("en"))

    def test_les_nouvelles_lignes_viennent_apres_les_anciennes(self):
        """Les tests existants lisent les nombres de la sortie par rang : les lignes du groupe 8 sont à la fin."""
        lignes = self.sortie("en", historique=True).splitlines()
        self.assertTrue(lignes[-1].startswith("Tickets out of the export"))
        self.assertTrue(any(l.startswith("Tickets marked") for l in lignes[:-3]))


if __name__ == "__main__":
    unittest.main()


class SeuilDesAbsents(unittest.TestCase):
    """--mark-absent refuse un export vide et une part de tickets absents au-delà du seuil (défaut 20 %). Pur : sans base."""

    def test_part_pure(self):
        part = flow_import.part_absents_depassee
        self.assertFalse(part(2, 10, 20))                  # 20 % pile : accepté
        self.assertTrue(part(3, 10, 20))
        self.assertFalse(part(0, 0, 20))                   # rien de stocké : rien à refuser
        self.assertFalse(part(10, 10, 100))                # seuil 100 : jamais de refus
        self.assertTrue(part(1, 3, 20))

    def test_defaut_vingt_pour_cent(self):
        self.assertEqual(flow_import.SEUIL_ABSENTS_DEFAUT, 20)

    def lancer(self, *options, langue=None, lignes=(), tickets_en_base=0):
        """main() avec un jeu complet d'une requête, des fichiers lus, et une fausse base ; rend (code, sortie)."""
        reglages = cf.reglages(jql_exports={"alpha": "a"})
        donnees = {"tickets": [{"cle": c} for c in lignes], "illisibles": 0, "etiquettes_refusees": 0}
        sortie, erreur = io.StringIO(), io.StringIO()
        code = 0
        argv = ["api-alpha-2026-10-13.csv", *options] + (["--language", langue] if langue else [])
        with unittest.mock.patch.object(flux_jira, "config", return_value=reglages), \
                unittest.mock.patch.object(flow_import.lecteur, "lire_exports", return_value=donnees), \
                unittest.mock.patch.object(flow_import.db, "connect") as connexion, \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            try:
                flow_import.main(argv)
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
        return code, sortie.getvalue() + erreur.getvalue(), connexion.call_count

    def test_export_vide_refuse_avant_connexion(self):
        code, texte, connexions = self.lancer("--mark-absent", langue="en")
        self.assertEqual(code, 1)
        self.assertIn("empty export: --mark-absent refused", texte)
        self.assertEqual(connexions, 0)

    def test_export_vide_en_francais(self):
        code, texte, _ = self.lancer("--mark-absent")
        self.assertEqual(code, 1)
        self.assertIn("export vide : --mark-absent refusé", texte)

    def test_export_vide_sans_l_option_n_est_pas_refuse(self):
        _, texte, connexions = self.lancer(langue="en")
        self.assertNotIn("empty export", texte)
        self.assertEqual(connexions, 1)

    def test_pourcentage_invalide_refuse(self):
        for valeur in ("-1", "101", "abc"):
            code, _, connexions = self.lancer("--mark-absent", "--max-absent-percent", valeur, lignes=["PROJ-1"])
            self.assertEqual(code, 2, valeur)
            self.assertEqual(connexions, 0)

    def test_marques_avec_une_fausse_connexion(self):
        """_marques lève ErreurSeuilAbsents quand la part dépasse le seuil, sans rien écrire ; accepte sinon."""
        class Curseur:
            def __init__(self, candidats, total):
                self.candidats, self.total, self.sql = candidats, total, []

            def execute(self, sql, params=()):
                self.sql.append(sql)
                lu = self
                if sql.startswith("SELECT count(*)") and "NOT (key" in sql:
                    lu.derniere = self.candidats
                elif sql.startswith("SELECT count(*)"):
                    lu.derniere = self.total
                return lu

            def fetchone(self):
                return (self.derniere,)

            rowcount = 0
        maintenant = dt.datetime(2026, 10, 13, tzinfo=dt.timezone.utc)
        cur = Curseur(3, 10)
        with self.assertRaises(flow_import.ErreurSeuilAbsents):
            flow_import._marques(cur, ["PROJ-1"], True, maintenant, 20)
        self.assertFalse(any(s.startswith("UPDATE flow.issues SET out_of_export_at = %s") for s in cur.sql))
        cur = Curseur(2, 10)
        flow_import._marques(cur, ["PROJ-1"], True, maintenant, 20)
        self.assertTrue(any(s.startswith("UPDATE flow.issues SET out_of_export_at = %s") for s in cur.sql))
