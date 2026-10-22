"""Contrôles launchd, watch, backup, et offsite (tâche 3.3) : gabarits du dépôt, heures dues, noms et nombres de fichiers seulement."""
import datetime
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_doctor import SCHEMAS, SENTINELLE, TOOLS, Labo, gabarits_launchd  # noqa: E402


class Launchd(Labo):
    TACHES = "toutes"

    def test_toutes_installees_et_chargees(self):
        niveau, _, _ = self.niveau("launchd")
        self.assertEqual(niveau, "ok")

    def test_installee_mais_non_chargee(self):
        self.installer_tache("com.pmzilla.db-backup", charge=False)
        niveau, entree, p = self.niveau("launchd")
        self.assertEqual((niveau, entree["reason"]["key"]), ("problem", "not_loaded"))
        self.assertIn("com.pmzilla.db-backup", self.lancer().stdout)
        self.assertEqual(p.returncode, 1)
        self.assertEqual([a for a in self.appels() if a.startswith("launchctl") and not a.startswith("launchctl print")], [])

    def test_etat_du_json_sans_nom_de_tache(self):
        self.installer_tache("com.pmzilla.db-backup", charge=False)
        _, entree, _ = self.niveau("launchd")
        self.assertEqual(entree["reason"]["counts"], {"not_loaded": 1})
        self.assertNotIn("com.pmzilla", json.dumps(entree))

    def test_tache_non_installee_n_est_pas_un_probleme(self):
        self.desinstaller_tache("com.pmzilla.offsite-copy")
        niveau, entree, _ = self.niveau("launchd")
        self.assertEqual(niveau, "ok")
        self.assertEqual(entree["reason"]["counts"]["not_set_up"], 1)

    def test_aucune_tache_installee_ignore(self):
        for etiquette in gabarits_launchd():
            self.desinstaller_tache(etiquette)
        niveau, entree, p = self.niveau("launchd")
        self.assertEqual((niveau, entree["reason"]["key"]), ("skipped", "none_installed"))
        self.assertEqual(p.returncode, 0)

    def test_gabarits_du_depot(self):
        self.assertIn("com.pmzilla.watch", gabarits_launchd())
        self.assertIn("com.pmzilla.db-backup", gabarits_launchd())

    def test_aucune_commande_qui_change_quelque_chose(self):
        self.installer_tache("com.pmzilla.watch", charge=False)
        self.lancer()
        for verbe in ("bootstrap", "bootout", "load", "unload", "kickstart", "enable", "disable", "start", "stop"):
            self.assertEqual([a for a in self.appels() if a.startswith(f"launchctl {verbe}")], [])


class Veille(Labo):
    def cle(self, **env):
        niveau, entree, _ = self.niveau("watch", env=env or None)
        return niveau, entree["reason"]["key"]

    def test_veille_du_jour_reussie(self):
        self.assertEqual(self.cle(), ("ok", "ok"))

    def test_veille_en_echec(self):
        self.ecrire_repere("echoue", code=1)
        niveau, entree, p = self.niveau("watch")
        self.assertEqual((niveau, entree["reason"]["key"]), ("problem", "failed"))
        self.assertEqual(p.returncode, 1)

    def test_termine_quoi_que_dise_le_journal(self):
        self.vider_journal_veille()
        self.ecrire_journal_veille("2026-10-14", "07:10", "echec")
        self.assertEqual(self.cle(), ("ok", "ok"))
        self.vider_journal_veille()
        self.assertEqual(self.cle(), ("ok", "ok"))

    def test_le_journal_seul_ne_suffit_plus(self):
        self.supprimer_repere()
        self.assertEqual(self.cle(), ("problem", "missing"))

    def test_aucun_repere_avant_l_heure_due(self):
        self.supprimer_repere()
        self.assertEqual(self.cle(PMZILLA_LAB_NOW="06:30"), ("skipped", "not_due"))

    def test_aucun_repere_apres_l_heure_due(self):
        self.supprimer_repere()
        self.assertEqual(self.cle(), ("problem", "missing"))

    def test_repere_d_hier_seulement(self):
        self.ecrire_repere("termine", jour="2026-10-13")
        self.assertEqual(self.cle(), ("problem", "missing"))

    def test_repere_illisible_vaut_aucun_repere(self):
        (self.donnees / "veille-du-jour.json").write_text("{pas du json", encoding="utf-8")
        self.assertEqual(self.cle(), ("problem", "missing"))
        (self.donnees / "veille-du-jour.json").write_text("[1, 2]", encoding="utf-8")
        self.assertEqual(self.cle(), ("problem", "missing"))

    def test_heure_due_reglable(self):
        self.supprimer_repere()
        self.assertEqual(self.cle(DOCTOR_WATCH_DUE="11:00"), ("skipped", "not_due"))

    def test_passage_en_cours_avec_verrou(self):
        self.ecrire_repere("commence")
        self.poser_verrou()
        self.assertEqual(self.cle(), ("skipped", "running"))

    def test_passage_commence_sans_verrou_est_interrompu(self):
        self.ecrire_repere("commence")
        niveau, entree, p = self.niveau("watch")
        self.assertEqual((niveau, entree["reason"]["key"]), ("problem", "interrupted"))
        self.assertEqual(p.returncode, 1)

    def test_passage_interrompu(self):
        self.ecrire_repere("interrompu")
        self.assertEqual(self.cle(), ("problem", "interrupted"))

    def test_report_avant_l_heure_limite(self):
        self.ecrire_repere("reporte", essais=1)
        self.assertEqual(self.cle(), ("skipped", "postponed"))

    def test_jour_manque_apres_report(self):
        self.ecrire_repere("reporte", essais=3)
        self.assertEqual(self.cle(PMZILLA_LAB_NOW="22:30"), ("problem", "missed"))

    def test_jour_manque_sans_repere(self):
        self.supprimer_repere()
        self.assertEqual(self.cle(PMZILLA_LAB_NOW="22:30"), ("problem", "missed"))

    def test_heure_limite_incluse(self):
        self.ecrire_repere("reporte")
        self.assertEqual(self.cle(PMZILLA_LAB_NOW="22:00"), ("skipped", "postponed"))
        self.assertEqual(self.cle(PMZILLA_LAB_NOW="22:01"), ("problem", "missed"))

    def test_heure_limite_reglable(self):
        self.supprimer_repere()
        self.assertEqual(self.cle(DOCTOR_WATCH_LATEST="12:00", PMZILLA_LAB_NOW="12:30"), ("problem", "missed"))
        self.assertEqual(self.cle(DOCTOR_WATCH_LATEST="12:00", PMZILLA_LAB_NOW="11:30"), ("problem", "missing"))

    def test_termine_apres_l_heure_limite_reste_ok(self):
        self.assertEqual(self.cle(PMZILLA_LAB_NOW="23:00"), ("ok", "ok"))

    def test_heure_limite_egale_a_celle_de_watch_sh(self):
        import re
        import doctor
        trouve = re.search(r'^HEURE_LIMITE="(\d\d:\d\d)"$', (TOOLS / "watch.sh").read_text(encoding="utf-8"), re.M)
        self.assertIsNotNone(trouve)
        self.assertEqual(doctor.HEURE_LIMITE, trouve.group(1))

    def test_dossier_de_donnees_en_lecture_seule(self):
        if os.geteuid() == 0:
            self.skipTest("root passe outre les droits")
        self.donnees.chmod(0o500)
        self.addCleanup(self.donnees.chmod, 0o700)
        avant = self.fichiers()
        niveau, entree, p = self.niveau("watch")
        self.assertEqual((niveau, entree["reason"]["key"]), ("problem", "record_not_writable"))
        self.assertEqual(p.returncode, 1)
        self.assertEqual(self.fichiers(), avant)

    def test_marqueur_d_alerte_du_jour(self):
        (self.journaux / "pmzilla-watch-alerte").write_text("2026-10-14\n", encoding="utf-8")
        avant = self.fichiers()
        self.assertEqual(self.cle(), ("problem", "record_not_writable"))
        self.assertEqual(self.fichiers(), avant)

    def test_marqueur_d_un_autre_jour_ignore(self):
        (self.journaux / "pmzilla-watch-alerte").write_text("2026-10-13\n", encoding="utf-8")
        self.assertEqual(self.cle(), ("ok", "ok"))

    def test_date_de_paris_sans_variables(self):
        import datetime as dt
        import doctor
        from zoneinfo import ZoneInfo
        env = {"HOME": str(self.maison)}
        avant = dt.datetime.now(ZoneInfo("Europe/Paris"))
        ctx = doctor.construire_contexte(env)
        apres = dt.datetime.now(ZoneInfo("Europe/Paris"))
        self.assertIn(ctx.aujourdhui, (avant.date(), apres.date()))
        self.assertIn(ctx.heure.hour, (avant.hour, apres.hour))

    def test_la_veille_n_est_jamais_lancee_ni_ecrite(self):
        self.ecrire_repere("commence")
        avant = self.fichiers()
        self.lancer()
        self.assertEqual([a for a in self.appels() if "watch.sh" in a or "watch_lab" in a or a.startswith(("uv", "bash", "zsh"))], [])
        self.assertEqual(self.fichiers(), avant)
        self.assertFalse((self.donnees / "veille.verrou").exists())


class Sauvegarde(Labo):
    def test_sauvegarde_complete(self):
        niveau, entree, _ = self.niveau("backup")
        self.assertEqual((niveau, entree["reason"]["counts"]), ("ok", {"found": 4}))

    def test_dossier_absent_apres_l_heure_due(self):
        import shutil
        shutil.rmtree(self.donnees / "sauvegardes")
        niveau, entree, p = self.niveau("backup")
        self.assertEqual((niveau, entree["reason"]["key"]), ("problem", "missing"))
        self.assertEqual(p.returncode, 1)

    def test_dossier_absent_avant_l_heure_due(self):
        import shutil
        shutil.rmtree(self.donnees / "sauvegardes")
        niveau, entree, _ = self.niveau("backup", env={"PMZILLA_LAB_NOW": "07:00"})
        self.assertEqual((niveau, entree["reason"]["key"]), ("skipped", "not_due"))

    def test_sauvegarde_courte_sans_nom_de_fichier_dans_la_sortie(self):
        import shutil
        shutil.rmtree(self.donnees / "sauvegardes")
        self.ecrire_sauvegarde("2026-10-14", SCHEMAS[:2])
        niveau, entree, _ = self.niveau("backup")
        self.assertEqual((niveau, entree["reason"]["key"], entree["reason"]["counts"]), ("problem", "short", {"found": 2, "expected": 4}))
        sortie = self.lancer().stdout + self.lancer("--language", "en").stdout
        for schema in SCHEMAS:
            self.assertNotIn(f"{schema}.dump", sortie)

    def test_trois_schemas_sans_le_dump_partiel_de_quality_est_courte(self):
        import shutil
        shutil.rmtree(self.donnees / "sauvegardes")
        self.ecrire_sauvegarde("2026-10-14", SCHEMAS[:3])
        niveau, entree, _ = self.niveau("backup")
        self.assertEqual((niveau, entree["reason"]["key"], entree["reason"]["counts"]), ("problem", "short", {"found": 3, "expected": 4}))

    def test_statique_les_attendus_sont_ce_qu_ecrit_db_backup(self):
        # schémas par défaut identiques, et un seul dump à nom fixe dans db_backup.sh (le dump partiel de quality) : le « + 1 » de doctor
        import re
        sauvegarde = (TOOLS / "db_backup.sh").read_text(encoding="utf-8")
        doctor = (TOOLS / "doctor.py").read_text(encoding="utf-8")
        schemas = re.search(r'^SCHEMAS="\$\{DB_BACKUP_SCHEMAS:-(.*)\}"$', sauvegarde, re.M).group(1)
        self.assertIn(f'.get("DOCTOR_SCHEMAS") or "{schemas}").split()) + 1', doctor)
        fixes = set(re.findall(r'^\s*fichier="\$CIBLE/([A-Za-z0-9_-]+)\.dump"', sauvegarde, re.M))
        self.assertEqual(fixes, {"quality-sans-texte"})

    def test_seuls_les_dumps_comptent(self):
        import shutil
        shutil.rmtree(self.donnees / "sauvegardes")
        self.ecrire_sauvegarde("2026-10-14", SCHEMAS, suffixe=".txt")
        self.assertEqual(self.niveau("backup")[1]["reason"]["key"], "short")

    def test_sauvegarde_etiquetee_ou_d_hier_ne_compte_pas(self):
        import shutil
        shutil.rmtree(self.donnees / "sauvegardes")
        self.ecrire_sauvegarde("2026-10-13", SCHEMAS)
        self.assertEqual(self.niveau("backup")[1]["reason"]["key"], "missing")

    def test_schemas_reglables(self):
        self.assertEqual(self.niveau("backup", env={"DOCTOR_SCHEMAS": "knowledge cases flow extra"})[1]["reason"]["key"], "short")

    def test_sentinelle_jamais_affichee(self):
        for args in ((), ("--json",), ("--language", "en"), ("--quiet",)):
            p = self.lancer(*args)
            self.assertNotIn(SENTINELLE, p.stdout + p.stderr)

    def test_aucun_fichier_des_sauvegardes_n_est_modifie(self):
        avant = self.fichiers()
        self.lancer()
        self.assertEqual(self.fichiers(), avant)


class HorsDuMac(Labo):
    def test_copie_recente(self):
        self.assertEqual(self.niveau("offsite")[0], "ok")

    def test_non_installe(self):
        self.ecrire_hors_mac(configure=False)
        niveau, entree, p = self.niveau("offsite")
        self.assertEqual((niveau, entree["reason"]["key"]), ("skipped", "not_set_up"))
        self.assertEqual(p.returncode, 0)

    def test_copie_ancienne_avertissement(self):
        self.ecrire_hors_mac(derniere_reussite="2026-10-04")
        niveau, entree, p = self.niveau("offsite")
        self.assertEqual((niveau, entree["reason"]["key"], entree["reason"]["counts"]), ("warning", "warn_old", {"days": 10}))
        self.assertEqual(p.returncode, 0)

    def test_copie_tres_ancienne_probleme(self):
        self.ecrire_hors_mac(derniere_reussite="2026-09-20")
        niveau, entree, p = self.niveau("offsite")
        self.assertEqual((niveau, entree["reason"]["key"]), ("problem", "problem_old"))
        self.assertEqual(p.returncode, 1)

    def test_aucune_copie_reussie(self):
        self.ecrire_hors_mac(derniere_reussite="-")
        niveau, entree, _ = self.niveau("offsite")
        self.assertEqual((niveau, entree["reason"]["key"]), ("problem", "never"))

    def test_ages_reglables(self):
        self.ecrire_hors_mac(derniere_reussite="2026-10-04")
        self.assertEqual(self.niveau("offsite", env={"DOCTOR_OFFSITE_WARN_DAYS": "20"})[0], "ok")

    def test_seule_la_ligne_copy_est_lue(self):
        """Le fichier d'état porte d'autres lignes (série, test de restauration) : ni leur contenu ni la configuration ne sortent."""
        for args in ((), ("--json",)):
            p = self.lancer(*args)
            self.assertNotIn(SENTINELLE, p.stdout)
            self.assertNotIn("serie-db", p.stdout)
        (self.donnees / "offsite" / "statut").write_text("restore-test derniere_reussite=2026-10-13 resultat=ok date=2026-10-13\n", encoding="utf-8")
        self.assertEqual(self.niveau("offsite")[1]["reason"]["key"], "never")

    def test_le_disque_et_le_script_ne_sont_pas_touches(self):
        self.lancer()
        self.assertEqual([a for a in self.appels() if "offsite_backup" in a or "diskutil" in a or a.startswith("mount")], [])

    def test_deux_jours_sans_copie_reussie_avertissement(self):
        """#255 point 2 : au-delà d'un jour sans copie réussie, avertissement (et non plus « ok » à 2 jours)."""
        self.ecrire_hors_mac(derniere_reussite="2026-10-12")
        niveau, entree, _ = self.niveau("offsite")
        self.assertEqual((niveau, entree["reason"]["key"], entree["reason"]["counts"]), ("warning", "warn_old", {"days": 2}))

    def ecrire_journal_copie(self, lignes, jour="2026-10-14"):
        """Faux journal de la copie hors du Mac, dans le faux dossier personnel ; sa date de dernière écriture est `jour`."""
        chemin = self.journaux / "pmzilla-offsite-copy.log"
        chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
        heure = datetime.datetime.fromisoformat(jour + "T12:00:00").timestamp()
        os.utime(chemin, (heure, heure))

    def test_operation_not_permitted_est_un_probleme_meme_avec_une_copie_recente(self):
        self.ecrire_hors_mac(derniere_reussite="2026-10-13")
        self.ecrire_journal_copie(["copie faite", "find: .: Operation not permitted", "copie incomplète : db-2026-10-14 " + SENTINELLE])
        niveau, entree, p = self.niveau("offsite")
        self.assertEqual((niveau, entree["reason"]["key"]), ("problem", "not_permitted"))
        self.assertEqual(p.returncode, 1)
        for args in ((), ("--json",), ("--language", "en")):
            sortie = self.lancer(*args)
            self.assertNotIn(SENTINELLE, sortie.stdout + sortie.stderr)
            self.assertNotIn(str(self.maison), sortie.stdout + sortie.stderr)

    def test_copie_incomplete_dans_le_journal_est_un_probleme(self):
        self.ecrire_hors_mac(derniere_reussite="2026-10-13")
        self.ecrire_journal_copie(["copie incomplète : db-2026-10-14 " + SENTINELLE])
        niveau, entree, _ = self.niveau("offsite")
        self.assertEqual((niveau, entree["reason"]["key"]), ("problem", "incomplete"))

    def test_journal_sain_ou_absent_ne_change_rien(self):
        self.ecrire_hors_mac(derniere_reussite="2026-10-14")
        self.assertEqual(self.niveau("offsite")[0], "ok")
        self.ecrire_journal_copie(["copie faite : db-2026-10-14", "copie faite : bmad-memory-2026-10-14"])
        self.assertEqual(self.niveau("offsite")[0], "ok")

    def test_un_echec_ancien_suivi_d_un_succes_n_est_plus_signale(self):
        """Copie à la main réussie après l'échec planifié : le journal n'a pas été écrit après la dernière réussite."""
        self.ecrire_hors_mac(derniere_reussite="2026-10-14")
        self.ecrire_journal_copie(["find: .: Operation not permitted", "copie faite"], jour="2026-10-14")
        self.assertEqual(self.niveau("offsite")[0], "ok")

    def test_seule_la_fin_du_journal_est_lue(self):
        self.ecrire_hors_mac(derniere_reussite="2026-10-13")
        self.ecrire_journal_copie(["find: .: Operation not permitted"] + ["copie faite"] * 60)
        self.assertEqual(self.niveau("offsite")[0], "ok")

    def test_journal_non_configure_ignore(self):
        self.ecrire_hors_mac(configure=False)
        self.ecrire_journal_copie(["find: .: Operation not permitted"])
        self.assertEqual(self.niveau("offsite")[0], "skipped")


if __name__ == "__main__":
    unittest.main()
