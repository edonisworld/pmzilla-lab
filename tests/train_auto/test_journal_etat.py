"""
Tâche 2.6 (change autonomous-trains-observe) : le journal, l'état, la garde des noms, `status` et `observation` (conception D7).
Listes de noms fictives (Vexillonia), horloge imposée pour les passages, vrai horloge pour le bilan (il compare avec ce que l'auteur a fusionné).
"""
import json
import sys
import time
import unittest

from aide_auto import AvecAuto, NOM_FICTIF, RACINE, epoch

sys.path.insert(0, str(RACINE / "tools"))
import train_auto  # noqa: E402
import train_auto_messages  # noqa: E402

# Tranche 3 d'autonomous-trains-merge (D9, tâche 9.2) : l'enregistrement du passage gagne `mode`, `train` et `ecartees_essai` ; `main` (le main local du passage) sert au
# compte rendu de D14. Décision citée : D9 « The pass record gains … » ; les autres champs sont inchangés.
CHAMPS_PASSAGE = {"format", "type", "utc", "paris", "caller", "fenetre", "decision", "raison", "retenues", "ecartees", "essai", "doctor", "liste", "duree",
                  "notices", "arret_arme", "mode", "main", "ecartees_essai", "train", "env_job"}


class JournalEtat(AvecAuto):
    def instantane_donnees(self):
        return {f.name: (f.read_bytes(), f.stat().st_mtime_ns) for f in sorted(self.dossier_train().glob("*")) if f.is_file()}

    def lister(self, *noms):
        lignes = ["# pmzilla-train-pretes format 1"]
        for nom in noms:
            lignes.append("\t".join((nom, self.t.sommet(nom), self.t.arbre(nom), "faite", "2026-10-29T10:00:00Z")))
        self.dossier_train().mkdir(parents=True, exist_ok=True)
        self.fichier_liste().write_text("\n".join(lignes) + "\n", encoding="utf-8")

    def ecrire_journal(self, enregistrements):
        self.dossier_train().mkdir(parents=True, exist_ok=True)
        (self.dossier_train() / "journal.jsonl").write_text("".join(json.dumps(r) + "\n" for r in enregistrements), encoding="utf-8")

    # --- un enregistrement par passage, par arret et par reprendre
    def test_un_enregistrement_par_passage_arret_et_reprendre(self):
        self.assertEqual(self.passage(now=epoch(7, 0)).code, 0)   # D13 : 7 h reste hors fenêtre (les passages vont de 8 h à 21 h)
        self.assertEqual(self.auto("arret", "--raison", "essai-manuel").code, 0)
        self.assertEqual(self.auto("reprendre").code, 0)
        self.assertEqual(self.passage(now=epoch(7, 5)).code, 0)
        types = [r["type"] for r in self.journal()]
        self.assertEqual(types, ["passage", "arret", "reprendre", "passage"])
        passage = self.journal()[0]
        self.assertEqual(set(passage), CHAMPS_PASSAGE)
        self.assertEqual((passage["format"], passage["caller"], passage["decision"], passage["raison"]), (1, "terminal", "attente", "hors-fenetre"))
        self.assertEqual(passage["paris"], "2026-10-29 07:00")
        self.assertRegex(passage["utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        arret = self.journal()[1]
        self.assertEqual((arret["raison"], arret["format"]), ("essai-manuel", 1))
        for cle in ("utc", "paris", "caller"):
            self.assertIn(cle, arret)
            self.assertIn(cle, self.journal()[2])

    def test_champs_d_un_passage_qui_observe(self):
        self.inscrire("feat/x")
        self.assertEqual(self.passage().code, 0)
        d = self.dernier()
        self.assertEqual(d["fenetre"], "12:00")
        self.assertEqual(d["liste"], {"lignes": 1, "valides": 1})
        self.assertEqual(set(d["essai"]), {"code", "relance", "code2", "retirees"})
        self.assertIsInstance(d["duree"], int)
        self.assertEqual(d["doctor"], "absent")

    def test_l_etat_est_le_dernier_enregistrement_et_le_resume_de_la_liste(self):
        self.inscrire("feat/x")
        self.passage()
        etat = self.etat()
        self.assertEqual(etat["dernier"], self.dernier())
        self.assertEqual(etat["liste"], {"lignes": 1, "valides": 1})

    def test_purge_des_enregistrements_de_plus_d_un_an(self):
        self.ecrire_journal([
            {"format": 1, "type": "passage", "utc": "2025-10-01T10:00:00Z", "paris": "2025-10-01 12:00", "decision": "rien", "raison": "liste-vide"},
            {"format": 1, "type": "passage", "utc": "2025-11-15T10:00:00Z", "paris": "2025-11-15 11:00", "decision": "attente", "raison": "matin"},
        ])
        self.assertEqual(self.passage(now=epoch(7, 0)).code, 0)
        utcs = [r["utc"] for r in self.journal()]
        self.assertNotIn("2025-10-01T10:00:00Z", utcs)
        self.assertIn("2025-11-15T10:00:00Z", utcs)
        self.assertEqual(len(utcs), 2)

    # --- la garde des noms
    def test_un_nom_sensible_dans_un_nom_de_branche_est_masque_et_ecarte(self):
        nom = f"feat/{NOM_FICTIF}-x"
        self.preparer(nom)
        self.preparer("feat/y")
        self.lister(nom, "feat/y")
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_auto : écartée : branche masquée : nom refusé par la garde", r.sortie)
        d = self.dernier()
        self.assertIn({"branche": "branche masquée", "raison": "nom", "sommet": None}, d["ecartees"])
        self.assertEqual([b["branche"] for b in d["retenues"]], ["feat/y"])
        for texte in (r.texte, self.tout_le_texte_ecrit(), json.dumps(self.etat())):
            self.assertNotIn(NOM_FICTIF, texte, "la sentinelle n'est ni dans la sortie, ni dans le journal, ni dans l'état")

    def test_garde_impossible_donne_garde_noms_avec_des_comptes_seulement(self):
        self.preparer("feat/x")
        self.lister("feat/x")
        r = self.passage(extra={"PMZILLA_LAB_SENSITIVE_NAMES": str(self.t.dossier / "absente.txt")})
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_auto : attente : garde des noms impossible", r.sortie)
        d = self.dernier()
        self.assertEqual((d["decision"], d["raison"]), ("attente", "garde-noms"))
        self.assertEqual((d["retenues"], d["ecartees"]), ([], []))
        self.assertEqual(d["liste"], {"lignes": 1, "valides": 0})
        self.assertNotIn("feat/x", self.tout_le_texte_ecrit())

    # --- status et observation
    def test_status_et_observation_n_ecrivent_rien(self):
        self.inscrire("feat/x")
        self.passage()
        avant = self.instantane_donnees()
        for args in (("status",), ("status", "--json"), ("observation",), ("observation", "--json"), ("observation", "--days", "30")):
            r = self.auto(*args)
            self.assertEqual(r.code, 0, f"{args} : {r.texte}")
        self.assertEqual(self.instantane_donnees(), avant)

    def test_status_permis_en_session(self):
        r = self.auto("status", extra={"CLAUDECODE": "1"})
        self.assertEqual(r.code, 0, r.texte)
        r = self.auto("observation", extra={"CLAUDECODE": "1"})
        self.assertEqual(r.code, 0, r.texte)

    def test_status_sans_passage(self):
        r = self.auto("status")
        self.assertIn("train_auto : aucun passage enregistré ; arrêt absent", r.sortie)

    def test_status_dit_un_etat_illisible(self):
        # revue de contrôle 10.2, point A : un état présent mais illisible est dit par `status`, en texte et en JSON, dans les deux langues, sans rien écrire
        self.dossier_train().mkdir(parents=True, exist_ok=True)
        (self.dossier_train() / "etat.json").write_text("{pas du json", encoding="utf-8")
        avant = self.instantane_donnees()
        r = self.auto("status")
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_auto : état du train automatique illisible : le réparer ou le retirer", r.sortie)
        self.assertNotIn("aucun passage enregistré", r.sortie)
        self.assertTrue(json.loads(self.auto("status", "--json").sortie)["illisible"])
        en = self.auto("status", langue="en")
        self.assertEqual(en.code, 0, en.texte)
        self.assertIn("train_auto: automatic train state unreadable: repair or remove it", en.sortie)
        self.assertEqual(self.instantane_donnees(), avant)

    def test_status_un_etat_qui_n_est_pas_un_objet_est_illisible(self):
        self.dossier_train().mkdir(parents=True, exist_ok=True)
        (self.dossier_train() / "etat.json").write_text("[1, 2]\n", encoding="utf-8")
        self.assertTrue(json.loads(self.auto("status", "--json").sortie)["illisible"])

    def test_status_etat_absent_ou_lisible_n_est_pas_illisible(self):
        self.assertFalse(json.loads(self.auto("status", "--json").sortie)["illisible"])   # absent : rien à lire, pas un état illisible
        self.inscrire("feat/x")
        self.passage()
        donnees = json.loads(self.auto("status", "--json").sortie)
        self.assertFalse(donnees["illisible"])
        self.assertNotIn("illisible", self.auto("status").sortie)

    def test_status_texte_et_json_concordent(self):
        self.inscrire("feat/x")
        self.passage()
        texte = self.auto("status")
        donnees = json.loads(self.auto("status", "--json").sortie)
        d = donnees["dernier"]
        self.assertIn(d["paris"], texte.sortie)
        self.assertIn(train_auto_messages.decision_label(d["decision"]), texte.sortie)
        self.assertIn(train_auto_messages.label(d["raison"]), texte.sortie)
        self.assertIn(f"liste : {donnees['liste']['lignes']} ligne(s), {donnees['liste']['valides']} valide(s)", texte.sortie)
        self.assertIn("arrêt absent", texte.sortie)
        self.assertFalse(donnees["arret"])

    # --- le bilan sur un journal fabriqué
    def test_bilan_fusionnee_apres_observation_ecartee_puis_fusionnee_non_listee_et_jours(self):
        for nom in ("feat/x", "feat/z", "feat/w"):
            self.t.branche(nom)
        sommet = self.t.construire_train(["feat/x", "feat/z", "feat/w"])
        self.t.git("update-ref", "refs/remotes/origin/main", sommet)   # l'auteur a fusionné et poussé
        maintenant = time.time()
        jour1, jour2 = maintenant - 2 * 86400, maintenant - 86400

        def passage(ts, decision, raison, retenues=(), ecartees=(), essai=None):
            return {"format": 1, "type": "passage", "utc": train_auto.iso_utc(ts), "paris": train_auto.paris(ts).strftime("%Y-%m-%d %H:%M"),
                    "caller": "launchd", "fenetre": "12:00", "decision": decision, "raison": raison, "retenues": list(retenues),
                    "ecartees": list(ecartees), "essai": essai, "doctor": "absent", "liste": None, "duree": 1, "notices": [], "arret_arme": None}

        self.ecrire_journal([
            passage(jour1, "observe", "essai", retenues=[{"branche": "feat/x", "sommet": self.t.sommet("feat/x")}],
                    ecartees=[{"branche": "feat/z", "raison": "empreinte", "sommet": self.t.sommet("feat/z")}],
                    essai={"code": 0, "relance": False, "code2": None, "retirees": []}),
            passage(jour1 + 1, "attente", "matin"),
            passage(jour2, "attente", "verrou-fin"),
        ])
        r = self.auto("observation", "--days", "7", "--json")
        self.assertEqual(r.code, 0, r.texte)
        b = json.loads(r.sortie)
        self.assertEqual(b["passages"], 3)
        self.assertEqual(b["jours_observes"], 2)
        self.assertEqual(b["par_decision"], {"observe": 1, "attente": 2})
        self.assertEqual(b["par_raison"], {"essai": 1, "matin": 1, "verrou-fin": 1})
        apres = b["fusionnees_apres_observation"]
        self.assertEqual([x["branche"] for x in apres], ["feat/x"])
        self.assertTrue(2800 <= apres[0]["delai_min"] <= 2960, apres)   # environ deux jours, en minutes
        self.assertEqual(b["fusionnees_ecartees"], [{"branche": "feat/z", "raison": "empreinte"}])
        self.assertEqual(b["fusionnees_non_listees"], ["feat/w"])
        self.assertEqual(b["non_listees"], 1)
        # le texte ne dit que ce que le JSON porte
        t = self.auto("observation", "--days", "7").sortie
        self.assertIn("3 passage(s), 2 jour(s) observé(s)", t)
        self.assertIn("fusionnée après observation : feat/x", t)
        self.assertIn(f"délai {apres[0]['delai_min']} min", t)
        self.assertIn("fusionnée alors qu'elle était écartée : feat/z (empreinte du runner différente de l'arbre)", t)
        self.assertIn("fusionnée sans avoir été listée : feat/w", t)
        self.assertIn("bilan : 1 fusionnée(s) après observation, 1 écartée(s) puis fusionnée(s), 1 non listée(s)", t)

    def test_bilan_ne_compte_pas_une_branche_dont_l_essai_n_etait_pas_a_zero(self):
        self.t.branche("feat/x")
        sommet = self.t.construire_train(["feat/x"])
        self.t.git("update-ref", "refs/remotes/origin/main", sommet)
        ts = time.time() - 3600
        self.ecrire_journal([{"format": 1, "type": "passage", "utc": train_auto.iso_utc(ts), "paris": train_auto.paris(ts).strftime("%Y-%m-%d %H:%M"),
                              "caller": "launchd", "fenetre": "12:00", "decision": "observe", "raison": "essai",
                              "retenues": [{"branche": "feat/x", "sommet": self.t.sommet("feat/x")}], "ecartees": [],
                              "essai": {"code": 70, "relance": False, "code2": None, "retirees": []}, "doctor": "absent", "liste": None,
                              "duree": 1, "notices": [], "arret_arme": None}])
        b = json.loads(self.auto("observation", "--json").sortie)
        self.assertEqual(b["fusionnees_apres_observation"], [])

    def test_bilan_sans_garde_ne_montre_aucun_nom_non_liste(self):
        self.t.branche("feat/w")
        sommet = self.t.construire_train(["feat/w"])
        self.t.git("update-ref", "refs/remotes/origin/main", sommet)
        b = json.loads(self.auto("observation", "--json", extra={"PMZILLA_LAB_SENSITIVE_NAMES": str(self.t.dossier / "absente.txt")}).sortie)
        self.assertEqual((b["non_listees"], b["fusionnees_non_listees"]), (1, []))

    def test_bilan_langue_anglaise(self):
        r = self.auto("observation", langue="en")
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_auto: observation over 7 day(s)", r.sortie)


if __name__ == "__main__":
    unittest.main()
