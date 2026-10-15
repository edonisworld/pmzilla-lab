"""Les quatre lignes du résumé du matin, leurs phrases clés (design D7), le JSON et les codes de sortie (design D2).

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/morning_summary -v
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide import Labo, JOUR, HIER, SENTINELLE, bilan, ms, roadmap  # noqa: E402


class Lignes(Labo):
    def lignes(self, *argv, **options):
        code, sortie, _ = self.lancer(*argv, **options)
        self.assertEqual(code, 0)
        return sortie.splitlines()

    def test_tout_connu_en_francais(self):
        self.tout_connu()
        self.assertEqual(self.lignes(bilans=[bilan(1), bilan(2, decision=True)]), [
            "PMZilla : résumé du matin",
            "Veille : faite, 7 article(s) retenu(s)",
            "Bilans dus : 2, dont 1 décision requise",
            "File : 4 prêt(s)",
            f"Doctor du {HIER} : 2 problème(s)"])

    def test_tout_connu_en_anglais(self):
        self.tout_connu()
        self.assertEqual(self.lignes("--language", "en", bilans=[bilan(1)]), [
            "PMZilla: morning summary",
            "Watch: done, 7 article(s) kept",
            "Reviews due: 1",
            "Queue: 4 ready",
            f"Doctor of {HIER}: 2 problem(s)"])

    def test_rien_de_lisible(self):
        self.assertEqual(self.lignes(bilans=ms.Injoignable()), [
            "PMZilla : résumé du matin", "Veille : état inconnu", "Bilans : base injoignable", "File : pas de cache",
            "Doctor : pas encore vérifié"])

    def test_rien_de_lisible_en_anglais(self):
        self.assertEqual(self.lignes("--language", "en", bilans=ms.Injoignable()), [
            "PMZilla: morning summary", "Watch: state unknown", "Reviews: database unreachable", "Queue: no cache",
            "Doctor: not checked yet"])

    # -- veille ---------------------------------------------------------------------------------------------------
    def test_rattrapage(self):
        self.repere(declencheur="rattrapage")
        self.retenus(3)
        self.assertEqual(self.lignes()[1], "Veille : faite, 3 article(s) retenu(s) (rattrapage)")
        self.assertEqual(self.lignes("--language", "en")[1], "Watch: done, 3 article(s) kept (catch-up)")

    def test_pas_de_pre_tri_aujourd_hui(self):
        self.repere()
        self.retenus(7, date=HIER)                 # la liste simple n'a rien écrit : le fichier est celui du passage précédent
        self.assertEqual(self.lignes()[1], "Veille : faite, pré-tri non fait aujourd'hui")
        self.assertEqual(self.lignes("--language", "en")[1], "Watch: done, no triage today")

    def test_pas_de_fichier_de_decompte(self):
        self.repere()
        self.assertEqual(self.lignes()[1], "Veille : faite, pré-tri non fait aujourd'hui")

    def test_decompte_illisible(self):
        self.repere()
        (self.donnees / "veille-retenus.json").write_text("pas du json", encoding="utf-8")
        self.assertEqual(self.lignes()[1], "Veille : faite, pré-tri non fait aujourd'hui")

    def test_rattrapage_sans_pre_tri(self):
        self.repere(declencheur="rattrapage")
        self.assertEqual(self.lignes()[1], "Veille : faite, pré-tri non fait aujourd'hui (rattrapage)")

    def test_echec_avec_etapes_dans_l_ordre(self):
        self.repere(etat="echoue")
        self.assertEqual(self.lignes("--failed-steps", "collecte, pré-tri")[1], "Veille : 2 étape(s) en échec : collecte, pré-tri")
        self.assertEqual(self.lignes("--language", "en", "--failed-steps", "collecte, pré-tri")[1],
                         "Watch: 2 failed step(s): collecte, pré-tri")

    def test_echec_sans_etapes(self):
        self.repere(etat="echoue")
        self.assertEqual(self.lignes()[1], "Veille : en échec")
        self.assertEqual(self.lignes("--language", "en")[1], "Watch: failed")

    def test_repere_de_la_veille_ou_autre_etat_ou_illisible(self):
        self.repere(date=HIER)
        self.assertEqual(self.lignes()[1], "Veille : état inconnu")
        for etat in ("commence", "reporte", "interrompu"):
            self.repere(etat=etat)
            self.assertEqual(self.lignes()[1], "Veille : état inconnu", etat)
        (self.donnees / "veille-du-jour.json").write_text("{pas du json", encoding="utf-8")
        self.assertEqual(self.lignes()[1], "Veille : état inconnu")
        self.json("veille-du-jour.json", ["liste"])
        self.assertEqual(self.lignes()[1], "Veille : état inconnu")

    def test_les_etapes_ne_changent_pas_une_veille_reussie(self):
        self.repere()
        self.retenus(1)
        self.assertEqual(self.lignes("--failed-steps", "collecte")[1], "Veille : faite, 1 article(s) retenu(s)")

    # -- bilans ---------------------------------------------------------------------------------------------------
    def test_aucun_bilan(self):
        self.assertEqual(self.lignes(bilans=[])[2], "Bilans dus : aucun")
        self.assertEqual(self.lignes("--language", "en", bilans=[])[2], "Reviews due: none")

    def test_deux_dus_dont_un_a_la_limite(self):
        self.assertEqual(self.lignes(bilans=[bilan(1), bilan(2, decision=True)])[2], "Bilans dus : 2, dont 1 décision requise")

    def test_le_jour_et_l_auteur_sont_transmis(self):
        self.lignes(bilans=[])
        self.assertEqual(self.reviews_demandes, [("auteur-de-test", ms.dt.date.fromisoformat(JOUR))])

    def test_sans_auteur_ni_ligne_ni_connexion(self):
        import os
        os.environ.pop("PMZILLA_LAB_CASES_AUTHOR")
        lignes = self.lignes(bilans=[bilan(1)])
        self.assertEqual(len(lignes), 4)
        self.assertFalse(any(l.startswith("Bilans") for l in lignes))
        self.assertEqual(self.reviews_demandes, [])

    def test_auteur_pris_dans_le_fichier_de_la_racine_configuree(self):
        self.auteur_dans_le_fichier()
        self.lignes(bilans=[])
        self.assertEqual(self.reviews_demandes[0][0], "auteur-de-test")

    def test_identifiant_indisponible_distinct_de_base_injoignable(self):
        self.assertEqual(self.lignes(bilans=ms.Indisponible())[2], "Bilans : indisponible")
        self.assertEqual(self.lignes("--language", "en", bilans=ms.Indisponible())[2], "Reviews: unavailable")

    def test_une_erreur_inattendue_de_la_base_dit_injoignable_sans_son_texte(self):
        code, sortie, erreur = self.lancer(bilans=RuntimeError(SENTINELLE))
        self.assertEqual(code, 0)
        self.assertIn("Bilans : base injoignable", sortie)
        self.assertNotIn(SENTINELLE, sortie + erreur)

    # -- file -----------------------------------------------------------------------------------------------------
    def test_file_du_jour_et_cache_ancien(self):
        self.cache(prets=2)
        self.assertEqual(self.lignes()[3], "File : 2 prêt(s)")
        self.cache(prets=4, jour="2026-10-11")
        self.assertEqual(self.lignes()[3], "File : 4 prêt(s) (cache du 2026-10-11)")
        self.assertEqual(self.lignes("--language", "en")[3], "Queue: 4 ready (cache of 2026-10-11)")

    def test_aucune_commande_gh_n_est_lancee(self):
        journal = self.tmp / "gh.log"
        self.stub("gh", f'#!/bin/sh\necho appel >> "{journal}"\nexit 1\n')
        self.cache(prets=2)
        self.lignes()
        self.lancer("--json")
        self.assertFalse(journal.exists())

    def test_pas_de_cache_ou_cache_illisible(self):
        self.assertEqual(self.lignes()[3], "File : pas de cache")
        (self.donnees / roadmap.FICHIER_CACHE).write_text("pas du json", encoding="utf-8")
        self.assertEqual(self.lignes()[3], "File : pas de cache")
        self.assertEqual(self.lignes("--language", "en")[3], "Queue: no cache")

    def test_meme_compte_que_le_rappel_du_debut_de_seance(self):
        self.cache(prets=3, en_cours=2)
        import contextlib, io
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            roadmap.cmd_reminder(None)
        self.assertIn("3 ready", sortie.getvalue())
        self.assertEqual(self.lignes()[3], "File : 3 prêt(s)")

    # -- doctor ---------------------------------------------------------------------------------------------------
    def test_doctor_tout_va_bien_et_problemes(self):
        self.doctor(0)
        self.assertEqual(self.lignes()[4], f"Doctor du {HIER} : tout va bien")
        self.assertEqual(self.lignes("--language", "en")[4], f"Doctor of {HIER}: all good")
        self.doctor(2, date=JOUR)
        self.assertEqual(self.lignes()[4], f"Doctor du {JOUR} : 2 problème(s)")

    def test_doctor_absent_ou_illisible(self):
        self.assertEqual(self.lignes()[4], "Doctor : pas encore vérifié")
        (self.donnees / "doctor-etat.json").write_text("pas du json", encoding="utf-8")
        self.assertEqual(self.lignes()[4], "Doctor : état illisible")
        self.assertEqual(self.lignes("--language", "en")[4], "Doctor: state unreadable")
        self.json("doctor-etat.json", {"version": 1})
        self.assertEqual(self.lignes()[4], "Doctor : état illisible")

    # -- confidentialité ------------------------------------------------------------------------------------------
    def test_aucune_sentinelle_nulle_part(self):
        self.tout_connu()
        for argv in ((), ("--json",), ("--language", "en"), ("--json", "--failed-steps", "collecte")):
            code, sortie, erreur = self.lancer(*argv, bilans=[bilan(1), bilan(2, decision=True)])
            self.assertEqual(code, 0)
            self.assertNotIn(SENTINELLE, sortie + erreur, argv)
            self.assertNotIn(str(self.tmp), sortie + erreur, argv)
            self.assertNotIn("Jalon-A", sortie + erreur, argv)
            self.assertNotIn("R-1", sortie + erreur, argv)

    def test_pas_de_tiret_cadratin(self):
        self.tout_connu()
        for langue in ("fr", "en"):
            self.assertNotIn("—", self.lancer("--language", langue, bilans=[bilan(1)])[1])


class Json(Labo):
    def test_les_quatre_cles_et_les_etats(self):
        self.tout_connu()
        code, sortie, _ = self.lancer("--json", bilans=[bilan(1), bilan(2, decision=True)])
        self.assertEqual(code, 0)
        donnees = json.loads(sortie)
        self.assertEqual(list(donnees), ["watch", "reviews", "queue", "doctor"])
        self.assertEqual(donnees["watch"]["state"], "done")
        self.assertEqual(donnees["watch"]["retained"], 7)
        self.assertEqual((donnees["reviews"]["state"], donnees["reviews"]["due"], donnees["reviews"]["decision_required"]), ("ok", 2, 1))
        self.assertEqual((donnees["queue"]["state"], donnees["queue"]["ready"]), ("ok", 4))
        self.assertEqual((donnees["doctor"]["state"], donnees["doctor"]["problems"], donnees["doctor"]["date"]), ("problems", 2, HIER))

    def test_rien_de_lisible_en_json(self):
        code, sortie, _ = self.lancer("--json", bilans=ms.Injoignable())
        donnees = json.loads(sortie)
        self.assertEqual(code, 0)
        self.assertEqual([donnees[k]["state"] for k in ("watch", "reviews", "queue", "doctor")], ["unknown", "unreachable", "no_cache", "absent"])

    def test_indisponible_et_sans_auteur_en_json(self):
        self.assertEqual(json.loads(self.lancer("--json", bilans=ms.Indisponible())[1])["reviews"]["state"], "unavailable")
        import os
        os.environ.pop("PMZILLA_LAB_CASES_AUTHOR")
        self.assertEqual(json.loads(self.lancer("--json", bilans=[])[1])["reviews"]["state"], "no_author")

    def test_veille_en_echec_en_json(self):
        self.repere(etat="echoue")
        donnees = json.loads(self.lancer("--json", "--failed-steps", "collecte, pré-tri", bilans=[])[1])["watch"]
        self.assertEqual((donnees["state"], donnees["failed_steps"]), ("failed", ["collecte", "pré-tri"]))


class Sorties(Labo):
    def test_option_inconnue_code_2_et_aucune_notification(self):
        code, _, _ = self.lancer("--inconnue", PMZILLA_SUMMARY_NOTIFY="1")
        self.assertEqual(code, 2)
        self.assertEqual(self.notifications(), [])
        self.assertFalse(self.memoire().exists())

    def test_langue_inconnue_code_2(self):
        self.assertEqual(self.lancer("--language", "de")[0], 2)

    def test_les_catalogues_sont_coherents(self):
        import messages
        import morning_summary_messages as mm
        self.assertEqual(messages.check_catalogs(mm.CATALOGS), [])
        for cle in mm.CATALOGS["fr"]:
            for langue in ("fr", "en"):
                self.assertNotIn("—", mm.CATALOGS[langue][cle], cle)

    def test_l_ecriture_est_limitee_a_la_memoire(self):
        self.tout_connu()
        avant = sorted(p.name for p in self.donnees.rglob("*"))
        self.lancer(bilans=[bilan(1)])
        self.lancer("--notify", bilans=[bilan(1)])
        self.lancer("--json", bilans=[bilan(1)])
        self.assertEqual(sorted(p.name for p in self.donnees.rglob("*")), avant)


if __name__ == "__main__":
    unittest.main()
