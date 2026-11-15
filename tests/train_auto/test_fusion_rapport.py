"""
Tranche 3 d'autonomous-trains-merge, tâches 9.3 et 9.4 (design D10 à D12, D14, D15) : la table des codes du train réel contre le registre
`tools/finish_codes.yaml`, l'arrêt armé, l'exclusion `echec-au-sommet`, l'échec d'un essai rapporté, `merge_report` et `etapes/fusions-auto.md`, la
notification (`TRAIN_AUTO_NOTIFIER`). Dossier du lab jetable ; aucun nom de branche dans le rapport masqué ni dans la notification.

    bash tests/run_all.sh train_auto
"""
import sys
import unittest
from pathlib import Path

import yaml

from aide_fusion import AvecFusion, epoch

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import train_auto  # noqa: E402
import train_auto_messages  # noqa: E402
from aide_auto import NOM_FICTIF  # noqa: E402

ENTETE = ("# Fusions automatiques\n\nÉcrit par train_auto seul, en ajout seul ; jamais modifié par une session.\n\n"
          "| Heure (Paris) | Code (sens) | main | Branches (sommet, revue) | Écartées à l'essai | Durée | Pour l'auteur |\n|---|---|---|---|---|---|---|\n")


class TableDesCodes(unittest.TestCase):
    """D10 : une table, clé par les codes de finish_train du registre ; le registre est la source."""

    def registre(self):
        donnees = yaml.safe_load((RACINE / "tools" / "finish_codes.yaml").read_text(encoding="utf-8"))
        return {c["code"]: c["origine"] for c in donnees["codes"] if c["script"] == "finish_train"}

    def test_chaque_code_utilise_ou_reserve_a_une_ligne_et_aucune_ligne_n_est_inconnue(self):
        registre = self.registre()
        attendus = {code for code, origine in registre.items() if origine in ("utilise", "reserve")}
        self.assertEqual(set(train_auto.CODE_TABLE), attendus,
                         "un code utilise ou reserve du registre sans ligne, ou une ligne qui nomme un code absent du registre")

    def test_les_codes_jamais_rendus_tombent_dans_tout_autre(self):
        registre = self.registre()
        jamais = {code for code, origine in registre.items() if origine == "jamais_rendu"}
        self.assertEqual(jamais, {72, 77})
        for code in jamais:
            self.assertNotIn(code, train_auto.CODE_TABLE)
            h = train_auto.code_handling(code, "refuse")
            self.assertTrue(h["stop"])
            self.assertEqual(h["suite"], "arret-arme")

    def test_un_code_inconnu_n_est_jamais_un_succes(self):
        for code in (1, 5, 124, 137, 255, 99):
            h = train_auto.code_handling(code, "fusionne")
            self.assertEqual((h["stop"], h["suite"]), (True, "arret-arme"), code)

    def test_les_lignes_de_la_conception(self):
        attendus = {
            (0, "fusionne"): ("rien", False, False),
            (0, "essai"): ("anomalie", True, False),
            (0, ""): ("anomalie", True, False),
            (62, "refuse"): ("refusee", False, True), (64, "refuse"): ("conflit", False, True), (66, "refuse"): ("garde-matin", False, False),
            (67, "refuse"): ("verrou-fin", False, False), (69, "refuse"): ("base-rouge", False, True), (70, "refuse"): ("train-rouge", False, True),
            (71, "refuse"): ("runner", False, True), (82, "refuse"): ("e2e-rouge", False, True), (83, "refuse"): ("jeu-essai", False, True),
            (84, "refuse"): ("politique", False, True), (75, "fusionne"): ("incomplete", False, False),
        }
        for code in (60, 61, 63, 68, 76, 78, 80, 81):
            attendus[(code, "refuse")] = ("environnement", False, False)
        for code in (65, 73, 74, 79, 129, 130, 141, 143):
            attendus[(code, "interrompu")] = ("arret-arme", True, False)
        for (code, sens), (suite, arret, refuse) in attendus.items():
            h = train_auto.code_handling(code, sens)
            self.assertEqual((h["suite"], h["stop"], h["refuse"]), (suite, arret, refuse), (code, sens))

    def test_les_suites_pour_l_auteur_sont_celles_de_la_conception(self):
        textes = {"rien": "rien", "anomalie": "anomalie : examiner le journal du train, puis reprendre",
                  "refusee": "branche refusée : la retirer de la liste ou la corriger", "conflit": "conflit : rebaser la branche en conflit",
                  "garde-matin": "garde du matin : le passage suivant réessaie", "verrou-fin": "verrou de fin tenu : le passage suivant réessaie",
                  "base-rouge": "phase base rouge : corriger la branche en cause", "train-rouge": "train rouge : corriger la branche en cause",
                  "runner": "runner non concluant : examiner le journal du train", "e2e-rouge": "phase de bout en bout rouge : corriger la branche en cause",
                  "jeu-essai": "jeu d'essai validant absent : train de l'auteur", "incomplete": "fusionné, fin incomplète : voir les causes",
                  "environnement": "environnement : examiner le journal du train", "arret-arme": "arrêt armé : examiner, puis reprendre"}
        for cle, texte in textes.items():
            self.assertEqual(train_auto_messages.label("suite-" + cle, "fr"), texte)
        self.assertEqual(train_auto.suite_text("politique", "fr", politique=["inactif", "plafond"]),
                         "politique : fusion automatique non activée, plus de 3 branches : train de l'auteur")


def rec_passage(**surcharge):
    base = {"format": 1, "type": "passage", "utc": "2026-11-07T11:05:00Z", "paris": "2026-11-07 12:05", "mode": "fusion", "decision": "train",
            "raison": "fusion-auto", "main": "1" * 40,
            "retenues": [{"branche": "feat/x", "sommet": "a" * 40, "revue": "faite"}, {"branche": "feat/y", "sommet": "b" * 40, "revue": "non-requise"}],
            "ecartees": [], "ecartees_essai": [], "essai": {"code": 0, "relance": False, "code2": None, "retirees": []}, "duree": 900,
            "train": {"code": 0, "sens": "fusionne", "duree": 900, "sommets": ["a" * 40, "b" * 40], "delai": False}, "arret_arme": None, "notices": []}
    base.update(surcharge)
    return base


def rec_train(**surcharge):
    base = {"format": 1, "heure": "2026-11-07T11:20:00Z", "code": 0, "sens": "fusionne", "mode": "auto", "n": 2, "sommets": ["a" * 40, "b" * 40],
            "sommet_train": "c" * 40, "main_avant": "1" * 40, "main_apres": "2" * 40, "runner": "conteneur", "base": False, "front": False,
            "politique": [], "duree_s": 900, "etape": ""}
    base.update(surcharge)
    return base


class MergeReport(unittest.TestCase):
    def test_un_train_fusionne(self):
        r = train_auto.merge_report(rec_passage(), rec_train())
        self.assertEqual((r["code"], r["sens"], r["main_avant"], r["main_apres"], r["duree_min"], r["suite"]), (0, "fusionne", "1" * 40, "2" * 40, 15, "rien"))
        self.assertEqual([(b["nom"], b["sommet"], b["revue"]) for b in r["branches"]], [("feat/x", "a" * 40, "faite"), ("feat/y", "b" * 40, "non-requise")])
        self.assertEqual((r["essai"], r["arret"], r["n"]), (False, False, 2))

    def test_la_ligne_du_rapport(self):
        r = train_auto.merge_report(rec_passage(), rec_train())
        self.assertEqual(train_auto.report_line(r, None, hide=False),
                         "| 2026-11-07 12:05 | 0 (fusionne) | " + "1" * 12 + " -> " + "2" * 12 + " | feat/x (sommet " + "a" * 12 + ", revue Opus du sommet " + "a" * 12
                         + ") ; feat/y (sommet " + "b" * 12 + ", revue non requise) | — | 15 min | rien |")

    def test_un_essai_refuse_montre_le_meme_main_deux_fois(self):
        p = rec_passage(decision="observe", raison="essai", train=None, essai={"code": 70, "relance": False, "code2": None, "retirees": []})
        r = train_auto.merge_report(p, None)
        self.assertEqual((r["essai"], r["code"], r["sens"], r["suite"]), (True, 70, "essai", "train-rouge"))
        self.assertEqual((r["main_avant"], r["main_apres"]), ("1" * 40, "1" * 40))
        self.assertIn("| 70 (essai) | " + "1" * 12 + " -> " + "1" * 12 + " |", train_auto.report_line(r, None, hide=False))

    def test_les_branches_retirees_a_l_essai(self):
        p = rec_passage(ecartees_essai=[{"branche": "feat/z", "code": 62}, {"branche": "feat/w", "code": 64}])
        line = train_auto.report_line(train_auto.merge_report(p, rec_train()), None, hide=False)
        self.assertIn("| feat/z (refusée) ; feat/w (conflit) |", line)

    def test_un_pipe_dans_un_nom_est_echappe(self):
        p = rec_passage(retenues=[{"branche": "feat/a|b", "sommet": "a" * 40, "revue": "faite"}])
        self.assertIn("feat/a\\|b (sommet", train_auto.report_line(train_auto.merge_report(p, rec_train(n=1)), None, hide=False))

    def test_sans_enregistrement_du_train_la_ligne_dit_le_code(self):
        r = train_auto.merge_report(rec_passage(), None)
        self.assertEqual((r["code"], r["main_avant"], r["main_apres"]), (0, "1" * 40, "1" * 40))
        self.assertEqual(r["suite"], "anomalie")

    def test_la_politique_du_code_84(self):
        r = train_auto.merge_report(rec_passage(train={"code": 84, "sens": "refuse", "duree": 5, "sommets": [], "delai": False}),
                                    rec_train(code=84, sens="refuse", politique=["revue-absente", "plafond"]))
        self.assertEqual(r["suite"], "politique")
        self.assertIn("politique : revue Opus absente pour ce sommet, plus de 3 branches : train de l'auteur", train_auto.suite_text(r["suite"], "fr", politique=r["politique"]))


class SansNom(unittest.TestCase):
    def test_une_branche_dont_le_nom_est_sensible_est_masquee_et_une_garde_impossible_donne_les_comptes(self):
        import sensitive_names
        garde = train_auto.Guard.__new__(train_auto.Guard)
        garde.motifs = sensitive_names.patterns([NOM_FICTIF])
        p = rec_passage(retenues=[{"branche": f"feat/{NOM_FICTIF}-x", "sommet": "a" * 40, "revue": "faite"}, {"branche": "feat/ok", "sommet": "b" * 40, "revue": "faite"}],
                        ecartees_essai=[{"branche": f"feat/{NOM_FICTIF}-y", "code": 62}])
        ligne = train_auto.report_line(train_auto.merge_report(p, rec_train()), garde, hide=False)
        self.assertNotIn(NOM_FICTIF, ligne)
        self.assertIn("branche masquée (sommet " + "a" * 12, ligne)
        self.assertIn("feat/ok (sommet", ligne)
        self.assertIn("branche masquée (refusée)", ligne)
        comptes = train_auto.report_line(train_auto.merge_report(p, rec_train()), None, hide=True)
        self.assertNotIn("feat/", comptes)
        self.assertIn("| 2 branche(s) |", comptes)
        self.assertIn("| 1 branche(s) |", comptes)


class Notification(unittest.TestCase):
    def test_texte_du_train_reel(self):
        r = train_auto.merge_report(rec_passage(), rec_train())
        self.assertEqual(train_auto.notification_text(r), "fusionné : 2 branche(s), main " + "2" * 12 + ", revue 1/2, 15 min, code 0")

    def test_texte_d_un_train_refuse_et_arret_arme(self):
        r = train_auto.merge_report(rec_passage(train={"code": 143, "sens": "interrompu", "duree": 10800, "sommets": [], "delai": True}, arret_arme=143),
                                    rec_train(code=143, sens="interrompu", main_apres="1" * 40))
        self.assertTrue(train_auto.notification_text(r).startswith("interrompu : 2 branche(s), main " + "1" * 12 + ", revue 1/2, 15 min, code 143"))
        self.assertTrue(train_auto.notification_text(r).endswith(", arrêt armé"))

    def test_texte_d_un_essai_refuse(self):
        p = rec_passage(decision="observe", raison="essai", train=None, essai={"code": 70, "relance": False, "code2": None, "retirees": []})
        self.assertEqual(train_auto.notification_text(train_auto.merge_report(p, None)),
                         "essai refusé : 2 branche(s), code 70, pour l'auteur : train rouge : corriger la branche en cause")
        p["arret_arme"] = 65
        self.assertTrue(train_auto.notification_text(train_auto.merge_report(dict(p, essai={"code": 65, "relance": False, "code2": None, "retirees": []}), None)).endswith(", arrêt armé"))

    def test_aucun_nom_de_branche_dans_la_notification(self):
        for p, t in ((rec_passage(), rec_train()), (rec_passage(train=None, essai={"code": 70, "relance": False, "code2": None, "retirees": []}), None)):
            texte = train_auto.notification_text(train_auto.merge_report(p, t))
            self.assertNotIn("feat/", texte)


class RapportEtNotificationDuPassage(AvecFusion):
    def test_train_fusionne_ecrit_le_rapport_en_ajout_et_notifie(self):
        self.activer()
        r = self.passage_fusion("feat/x", "feat/y")
        self.assertEqual(r.code, 0, r.texte)
        texte = self.rapport()
        self.assertTrue(texte.startswith(ENTETE), texte)
        lignes = texte[len(ENTETE):].splitlines()
        self.assertEqual(len(lignes), 1)
        self.assertRegex(lignes[0], r"^\| 2026-10-29 12:05 \| 0 \(fusionne\) \| [0-9a-f]{12} -> d{12} \| feat/x \(sommet [0-9a-f]{12}, revue Opus du sommet [0-9a-f]{12}\) ; "
                                    r"feat/y \(sommet [0-9a-f]{12}, revue Opus du sommet [0-9a-f]{12}\) \| — \| 2 min \| rien \|$")
        self.assertEqual(self.notifications(), ["fusionné : 2 branche(s), main " + "d" * 12 + ", revue 2/2, 2 min, code 0"])
        self.assertIn("train_auto : pour l'auteur : rien", r.sortie)

    def test_le_rapport_n_est_jamais_reecrit_et_l_entete_une_seule_fois(self):
        self.activer()
        self.passage_fusion("feat/x")
        premiere = self.rapport()
        self.passage_fusion("feat/y")
        deuxieme = self.rapport()
        self.assertTrue(deuxieme.startswith(premiere), "ajout seul : le début ne change jamais")
        self.assertEqual(deuxieme.count("# Fusions automatiques"), 1)
        self.assertEqual(len(deuxieme[len(ENTETE):].splitlines()), 2)

    def test_rien_d_autre_n_est_ecrit_dans_etapes(self):
        self.activer()
        self.passage_fusion("feat/x")
        self.assertEqual(sorted(p.name for p in (self.t.lab / "etapes").iterdir()), ["fusions-auto.md"])

    def test_un_nom_sensible_est_masque_dans_le_rapport(self):
        self.activer()
        self.preparer(f"feat/{NOM_FICTIF}")
        self.lister(f"feat/{NOM_FICTIF}")
        # le nom est écarté par la garde avant l'essai (raison nom) : aucun train, aucune ligne ; le nom ne doit être ni dans le rapport ni dans les notifications
        self.passage(extra=self.avec_notificateur())
        self.assertNotIn(NOM_FICTIF, (self.rapport() or "") + "".join(self.notifications()))

    def test_ecriture_impossible_du_rapport_la_decision_ne_change_pas(self):
        self.activer()
        (self.t.lab / "etapes").write_text("je suis un fichier", encoding="utf-8")   # le dossier ne peut pas être créé
        r = self.passage_fusion("feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_auto : compte rendu non écrit (écriture impossible)", r.sortie)
        self.assertEqual((self.dernier()["decision"], self.dernier()["train"]["code"]), ("train", 0))
        self.assertIn("rapport_non_ecrit", self.dernier()["notices"])
        self.assertEqual(len(self.notifications()), 1, "la notification part quand même")

    def test_notification_en_echec_est_ignoree_et_journalisee(self):
        self.activer()
        r = self.passage_fusion("feat/x", extra={"NOTIFIER_CODE": "3"})
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_auto : notification non envoyée", r.sortie)
        self.assertIn("notification_non_envoyee", self.dernier()["notices"])
        self.assertEqual(self.dernier()["train"]["code"], 0)

    def test_aucune_notification_sans_notificateur_de_test_n_utilise_osascript_ici(self):
        # TRAIN_AUTO_NOTIFIER remplace la commande ; la commande réelle est celle de D15
        cmd = train_auto.notifier_command("texte")
        self.assertEqual(cmd[:2], ["/usr/bin/osascript", "-e"])
        self.assertEqual(cmd[-1], "texte")
        self.assertIn('display notification (item 1 of argv) with title "Train automatique"', cmd)
        self.assertEqual(train_auto.NOTIFY_TIMEOUT, 10)

    def test_essai_refuse_en_fusion_est_rapporte_une_fois_et_notifie(self):
        self.activer()
        r = self.passage_fusion("feat/x", extra={"FAUX_CODE_ESSAI": "70"})
        texte = self.rapport()
        self.assertIsNotNone(texte)
        ligne = texte[len(ENTETE):].splitlines()
        self.assertEqual(len(ligne), 1)
        self.assertIn("| 70 (essai) |", ligne[0])
        self.assertTrue(ligne[0].endswith("| train rouge : corriger la branche en cause |"), ligne[0])
        self.assertEqual(self.notifications(), ["essai refusé : 1 branche(s), code 70, pour l'auteur : train rouge : corriger la branche en cause"])
        self.assertEqual(self.appels_train(), [])

    def test_essai_65_arme_l_arret_et_le_dit(self):
        self.activer()
        self.passage_fusion("feat/x", extra={"FAUX_CODE_ESSAI": "65"})
        self.assertTrue(self.notifications()[0].endswith(", arrêt armé"))
        self.assertTrue((self.dossier_train() / "arret").exists())

    def test_ni_attente_ni_rien_a_faire_ni_exclusion_ne_sont_rapportes(self):
        self.activer()
        self.passage(now=epoch(21, 0), extra=self.avec_notificateur())   # départ limite : attente
        self.passage(extra=self.avec_notificateur())                    # liste vide : rien à faire
        self.assertIsNone(self.rapport())
        self.assertEqual(self.notifications(), [])

    def test_rien_n_est_rapporte_ni_notifie_en_observation(self):
        self.passage_fusion("feat/x", extra={"FAUX_CODE_ESSAI": "70"})
        self.assertIsNone(self.rapport())
        self.assertEqual(self.notifications(), [])


class Codes(AvecFusion):
    def test_code_zero_et_sens_fusionne_ne_demande_rien(self):
        self.activer()
        self.passage_fusion("feat/x")
        self.assertFalse((self.dossier_train() / "arret").exists())
        self.assertIn("| rien |", self.rapport())

    def test_codes_qui_arment_l_arret(self):
        for code, sens in ((65, "refuse"), (73, "refuse"), (74, "refuse"), (79, "refuse"), (143, "interrompu"), (130, "interrompu"), (72, "refuse")):
            with self.subTest(code=code):
                self.activer_et_vider()
                r = self.passage_fusion("feat/x", extra={"FAUX_CODE_AUTO": str(code), "FAUX_SENS": sens})
                self.assertTrue((self.dossier_train() / "arret").exists(), r.texte)
                self.assertIn(f"train_auto : arrêt armé après le code {code}", r.sortie)
                self.assertTrue(self.notifications()[-1].endswith(", arrêt armé"))

    def test_codes_de_l_environnement_et_du_passage_suivant_n_arment_rien_et_ne_sont_pas_exclus(self):
        for code in (60, 61, 63, 66, 67, 68, 76, 78, 80, 81):
            with self.subTest(code=code):
                self.activer_et_vider()
                r = self.passage_fusion("feat/x", extra={"FAUX_CODE_AUTO": str(code), "FAUX_SENS": "refuse"})
                self.assertFalse((self.dossier_train() / "arret").exists())
                self.assertEqual(self.etat_refuses(), [], "ces codes ne sont pas des refus de contenu : le passage suivant réessaie")
                self.assertEqual(len(self.notifications()), 1)

    def test_code_75_est_fusionne_avec_fin_incomplete(self):
        self.activer()
        self.passage_fusion("feat/x", extra={"FAUX_CODE_AUTO": "75", "FAUX_SENS": "fusionne"})
        self.assertFalse((self.dossier_train() / "arret").exists())
        self.assertIn("| fusionné, fin incomplète : voir les causes |", self.rapport())
        self.assertEqual(self.etat_refuses(), [])

    def test_code_84_rapporte_les_libelles_de_la_politique(self):
        self.activer()
        self.passage_fusion("feat/x", extra={"FAUX_CODE_AUTO": "84", "FAUX_SENS": "refuse", "FAUX_POLITIQUE": "revue-absente"})
        self.assertIn("| politique : revue Opus absente pour ce sommet |", self.rapport())

    def activer_et_vider(self):
        """Une activation valide et un dossier de train neuf pour chaque code : on efface l'arrêt, la liste, le rapport et les notifications."""
        if (self.dossier_train() / "arret").exists():
            self.assertEqual(self.auto("reprendre").code, 0)   # jamais supprimé à la main : un arrêt disparu serait recréé
        for f in (self.dossier_train() / "pretes.tsv", self.fichier_rapport(), self.t.etat / "notifications.txt", self.t.etat / "appels-fin.txt"):
            if f.exists():
                f.unlink()
        if not (self.dossier_train() / "fusion-active").exists():
            self.activer()


class RefusParContenu(AvecFusion):
    """D11 : un train refusé pour son contenu n'est pas rejoué sur les mêmes sommets."""

    def preparer_deux(self):
        self.activer()
        for n in ("feat/x", "feat/y"):
            self.preparer(n)
        self.lister("feat/x", "feat/y")

    def passer(self, extra=None):
        return self.passage(extra=self.avec_notificateur(extra))

    def test_un_train_refuse_n_est_pas_rejoue_sur_les_memes_sommets(self):
        for code in (62, 64, 69, 70, 71, 82, 83, 84):
            with self.subTest(code=code):
                for f in (self.dossier_train() / "etat.json", self.t.etat / "appels-fin.txt", self.t.etat / "notifications.txt"):
                    if f.exists():
                        f.unlink()
                if not (self.dossier_train() / "fusion-active").exists():
                    self.preparer_deux()
                self.lister("feat/x", "feat/y")
                self.passer({"FAUX_CODE_AUTO": str(code), "FAUX_SENS": "refuse"})
                self.assertEqual(len(self.appels_train()), 1)
                refuses = self.etat_refuses()
                self.assertEqual(len(refuses), 1)
                self.assertEqual(refuses[0]["code"], code)
                self.assertEqual(sorted(refuses[0]["sommets"]), sorted([self.t.sommet("feat/x"), self.t.sommet("feat/y")]))
                # le passage suivant exclut les deux lignes, ne lance ni essai ni train
                avant = len(self.appels_fin())
                r = self.passer({"FAUX_CODE_AUTO": "0"})
                self.assertEqual(len(self.appels_fin()), avant, "aucun essai ni train sur les mêmes sommets")
                self.assertIn("train_auto : écartée : feat/x : train refusé sur ce sommet : nouveau commit ou retrait attendu", r.sortie)
                self.assertIn("train_auto : écartée : feat/y : train refusé sur ce sommet : nouveau commit ou retrait attendu", r.sortie)
                self.assertEqual((self.dernier()["decision"], self.dernier()["raison"]), ("rien", "toutes-ecartees"))

    def test_l_exclusion_tombe_quand_le_sommet_change_et_reprendre_n_efface_rien(self):
        self.preparer_deux()
        self.passer({"FAUX_CODE_AUTO": "70", "FAUX_SENS": "refuse"})
        self.assertEqual(self.auto("reprendre").code, 0)
        self.assertEqual(len(self.etat_refuses()), 1, "reprendre n'efface aucune exclusion")
        self.passer()
        self.assertEqual(self.dernier()["raison"], "toutes-ecartees")
        # un nouveau commit sur feat/x : sa ligne est refaite avec la nouvelle preuve ; feat/y reste exclue
        self.commit_dans("feat/x", {"tools/plus.sh": "p\n"})
        self.ecrire_empreinte("feat/x")
        self.lister("feat/x", "feat/y")
        r = self.passer()
        self.assertEqual([b["branche"] for b in self.dernier()["retenues"]], ["feat/x"])
        self.assertIn("train_auto : écartée : feat/y : train refusé sur ce sommet", r.sortie)
        self.assertEqual(self.appels_train()[-1], "--auto feat/x")

    def test_l_exclusion_tombe_quand_la_ligne_est_retiree(self):
        self.preparer_deux()
        self.passer({"FAUX_CODE_AUTO": "70", "FAUX_SENS": "refuse"})
        self.lister("feat/y")   # feat/x retirée de la liste
        self.passer()
        self.assertEqual([e["branche"] for e in self.dernier()["ecartees"]], ["feat/y"])
        self.lister()
        self.passer()
        self.assertEqual(self.etat_refuses(), [], "plus aucune ligne ne porte ces sommets : l'ensemble est oublié")

    def test_le_passage_ne_retire_aucune_ligne_de_la_liste(self):
        self.preparer_deux()
        self.passer({"FAUX_CODE_AUTO": "70", "FAUX_SENS": "refuse"})
        avant = self.octets_liste()
        self.passer()
        self.assertEqual(self.octets_liste(), avant)

    def test_notification_par_sommet_exclu_une_seule_fois(self):
        self.preparer_deux()
        self.passer({"FAUX_CODE_AUTO": "70", "FAUX_SENS": "refuse"})
        apres_le_train = len(self.notifications())
        self.assertEqual(apres_le_train, 1)
        self.passer()
        exclusions = [n for n in self.notifications()[apres_le_train:] if "train refusé sur ce sommet (code 70)" in n]
        self.assertEqual(len(exclusions), 2, "une notification par sommet exclu, au premier passage qui l'exclut")
        self.assertFalse(any("feat/" in n for n in self.notifications()))
        n = len(self.notifications())
        self.passer()
        self.assertEqual(len(self.notifications()), n, "les passages suivants l'écrivent au journal seulement")
        self.assertIn("echec-au-sommet", self.journal_json())

    def test_un_refus_62_n_exclut_que_les_sommets_du_train_refuse(self):
        self.preparer_deux()
        self.passer({"FAUX_CODE_AUTO": "62", "FAUX_SENS": "refuse"})
        self.preparer("feat/z")
        self.lister("feat/x", "feat/y", "feat/z")
        self.passer()
        self.assertEqual([b["branche"] for b in self.dernier()["retenues"]], ["feat/z"])


if __name__ == "__main__":
    unittest.main()
