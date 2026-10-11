"""
Tests de l'étape database du script d'installation (change install-script, design D10, D14, D15). Écrits avant le code.

L'étape tourne ici dans le processus (étapes : une fausse étape `repo` déjà faite, puis la vraie étape database), avec le PATH du décor :
seuls les simulacres sont appelés.

    python3 -W ignore -m unittest discover -s tests/install_lab -p "test_database.py" -q -f
"""
import contextlib
import io
import os
import sys
import unittest
from unittest import mock

from aide_install import TOOLS_REELS, CasDeBase

sys.path.insert(0, str(TOOLS_REELS))
import install_lab as noyau            # noqa: E402
import install_lab_context as c        # noqa: E402
import install_lab_database as bd      # noqa: E402

REPO_FAIT = c.Etape("repo", ("fresh",), (), lambda ctx: True, lambda ctx: c.Resultat(c.DEJA))

# docker : « info » répond selon le drapeau docker-ko ; « compose ps » montre la base saine quand le drapeau db-up est posé
DOCKER = (
    'case "$*" in\n'
    '  *"info"*) [ -e "$INSTALL_LAB_ETAT/docker-ko" ] && exit 1; exit 0 ;;\n'
    '  *"compose ps"*) if [ -e "$INSTALL_LAB_ETAT/db-up" ]; then\n'
    '      if [ -e "$INSTALL_LAB_ETAT/db-malsaine" ]; then echo "db  Up 2 minutes (unhealthy)"; else echo "db  Up 2 minutes (healthy)"; fi\n'
    '    fi; exit 0 ;;\n'
    'esac\nexit 0')
# uv : « migrate --dry-run » dit « Rien à appliquer. » quand le drapeau migre est posé ; « migrate » le pose
UV = (
    'case "$*" in\n'
    '  *"migrate --dry-run"*) if [ -e "$INSTALL_LAB_ETAT/migre" ]; then echo "Rien à appliquer."; else echo "1 migration(s) en attente"; fi; exit 0 ;;\n'
    '  *"migrate"*) [ -e "$INSTALL_LAB_ETAT/migrate-echec" ] && exit 1; : > "$INSTALL_LAB_ETAT/migre"; exit 0 ;;\n'
    'esac\nexit 0')


class EtapeDatabase(CasDeBase):
    def setUp(self):
        super().setUp()
        self.fx.simulacre("docker", DOCKER)
        self.fx.simulacre("uv", UV)

    def lancer(self, reponses="y\ny\n", a_blanc=False, etat=None):
        """Lance l'étape database ; rend (code de sortie, sortie, appels, contexte)."""
        ctx = c.Contexte(racine=self.fx.racine, maison=self.fx.maison, a_blanc=a_blanc)
        ctx.etat.update(etat or {})
        avant = len(self.fx.lire_appels())
        sortie = io.StringIO()
        with mock.patch.dict(os.environ, self.fx.environnement(), clear=True), \
                mock.patch("sys.stdin", io.StringIO(reponses)), contextlib.redirect_stdout(sortie):
            resultats = noyau.lancer_etapes(ctx, [REPO_FAIT, *bd.ETAPES], seule="database")
        self.passage = resultats["database"]
        return noyau.code_de_sortie(resultats), sortie.getvalue(), self.fx.lire_appels()[avant:], ctx

    # --- sondes ------------------------------------------------------------------------------------------------------------
    def test_base_prete_lit_compose_ps(self):
        ctx = c.Contexte(racine=self.fx.racine, maison=self.fx.maison)
        with mock.patch.dict(os.environ, self.fx.environnement(), clear=True):
            self.assertFalse(bd.base_prete(ctx))
            self.fx.drapeau("db-up")
            self.assertTrue(bd.base_prete(ctx))
            self.fx.drapeau("db-malsaine")
            self.assertFalse(bd.base_prete(ctx), "une base « unhealthy » n'est pas prête")
            self.fx.retirer("docker")
            self.fx.drapeau("db-malsaine", False)
            self.assertFalse(bd.base_prete(ctx), "docker absent : pas prête, sans exception")

    # --- scénarios nominaux ------------------------------------------------------------------------------------------------------
    def test_demarre_puis_migre(self):
        code, sortie, appels, ctx = self.lancer()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.passage.etat, c.FAIT)
        demarrage = [a for a in appels if a.startswith("db_up.sh")]
        migration = [a for a in appels if a.startswith("uv ") and "migrate" in a and "--dry-run" not in a]
        self.assertEqual(len(demarrage), 1, appels)
        self.assertEqual(len(migration), 1, appels)
        self.assertLess(appels.index(demarrage[0]), appels.index(migration[0]))
        self.assertTrue(self.fx.a_drapeau("db-up") and self.fx.a_drapeau("migre"))
        self.assertTrue(ctx.etat["base_ok"])

    def test_jamais_role_password(self):
        _, _, appels, _ = self.lancer()
        self.assertEqual([a for a in appels if "role-password" in a], [])

    def test_base_saine_migrations_en_attente_ne_redemarre_pas(self):
        self.fx.drapeau("db-up")
        code, sortie, appels, ctx = self.lancer(reponses="y\n")
        self.assertEqual(code, 0, sortie)
        self.assertEqual([a for a in appels if a.startswith("db_up.sh")], [])
        self.assertTrue(self.fx.a_drapeau("migre"))
        self.assertTrue(ctx.etat["base_ok"])

    def test_second_passage_deja_fait(self):
        self.lancer()
        code, sortie, appels, ctx = self.lancer(reponses="")
        self.assertEqual(code, 0, sortie)
        self.assertIn("step database: already done, skipped", sortie)
        self.assertEqual(self.passage.etat, c.DEJA)
        self.assertEqual(self.fx.appels_qui_changent(appels), [])

    def test_etat_partage_apres_deja_fait(self):
        self.fx.drapeau("db-up")
        self.fx.drapeau("migre")
        _, _, _, ctx = self.lancer(reponses="")
        self.assertTrue(ctx.etat.get("base_ok"), "la sonde pose le drapeau pour les étapes suivantes")

    # --- confirmation, passage à blanc ---------------------------------------------------------------------------------------------
    def test_reponse_vide_refuse_et_ne_change_rien(self):
        avant = self.fx.empreinte()
        code, sortie, appels, ctx = self.lancer(reponses="\n")
        self.assertEqual(code, 4, sortie)
        self.assertEqual(self.passage.etat, c.REFUSE)
        self.assertEqual(self.fx.appels_qui_changent(appels), [])
        self.assertEqual(self.fx.empreinte(), avant)
        self.assertFalse(ctx.etat.get("base_ok"))

    def test_refus_de_la_migration_ne_marque_pas_la_base_prete(self):
        code, sortie, appels, ctx = self.lancer(reponses="y\nn\n")
        self.assertEqual(code, 4, sortie)
        self.assertFalse(ctx.etat.get("base_ok"))
        self.assertFalse(self.fx.a_drapeau("migre"))

    def test_passage_a_blanc_ne_change_rien(self):
        avant = self.fx.empreinte()
        code, sortie, appels, ctx = self.lancer(reponses="", a_blanc=True)
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.passage.etat, c.A_BLANC)
        self.assertIn("dry run: would run bash ", sortie)
        self.assertIn("db_up.sh", sortie)
        self.assertEqual(self.fx.appels_qui_changent(appels), [])
        self.assertEqual(self.fx.empreinte(), avant)

    # --- moteur de conteneurs --------------------------------------------------------------------------------------------------------
    def test_moteur_absent_reporte_sans_commande(self):
        self.fx.drapeau("docker-ko")
        code, sortie, appels, ctx = self.lancer(reponses="")
        self.assertEqual(code, 4, sortie)
        self.assertEqual(self.passage.etat, c.REPORTE)
        self.assertEqual(self.passage.detail, "container runtime not available")
        self.assertFalse(ctx.etat["base_ok"])
        self.assertEqual(self.fx.appels_qui_changent(appels), [])

    def test_drapeau_runtime_refuse_prime_sur_la_sonde(self):
        code, sortie, appels, ctx = self.lancer(reponses="", etat={"runtime_ok": False})
        self.assertEqual(self.passage.etat, c.REPORTE)
        self.assertEqual(self.passage.detail, "container runtime not available")
        self.assertEqual([a for a in appels if a.startswith("docker info")], [], "le drapeau dispense de sonder")
        self.assertFalse(ctx.etat["base_ok"])

    def test_drapeau_runtime_ok_dispense_de_sonder(self):
        self.fx.drapeau("docker-ko")      # la sonde dirait non, mais le drapeau de l'étape prereqs fait foi
        code, sortie, appels, ctx = self.lancer(etat={"runtime_ok": True})
        self.assertEqual(code, 0, sortie)
        self.assertTrue(ctx.etat["base_ok"])

    # --- mot de passe introuvable (code de sortie 3) ------------------------------------------------------------------------------------
    def test_entree_du_trousseau_absente_action_manuelle(self):
        self.fx.drapeau("db-sans-mot-de-passe")
        code, sortie, appels, ctx = self.lancer(reponses="y\n")
        self.assertEqual(code, 4, sortie)
        self.assertEqual(self.passage.etat, c.MANUEL)
        self.assertIn("manual action needed: create the Keychain entry of the database", sortie)
        commande = 'security add-generic-password -s pmzilla-test-db -a "$USER" -w'
        self.assertIn(commande, sortie.splitlines()[[i for i, l in enumerate(sortie.splitlines()) if "manual action needed" in l][0] + 1])
        self.assertEqual(ctx.manuel, [commande])
        self.assertNotIn("pmzilla-lab-db", sortie, "le service vient de db.py du dépôt factice, jamais d'une constante")
        self.assertFalse(ctx.etat["base_ok"])
        self.assertIn("database-dependent steps deferred", ctx.reportes)
        self.assertEqual([a for a in appels if a.startswith("uv ") and "migrate" in a and "--dry-run" not in a], [], "pas de migration")

    def test_la_detection_ne_depend_pas_de_la_phrase_francaise(self):
        corps = (self.fx.racine / "tools" / "db_up.sh")
        corps.write_text('#!/bin/sh\necho "db_up.sh $*" >> "$INSTALL_LAB_APPELS"\necho "anything"\nexit 3\n', encoding="utf-8")
        _, sortie, _, _ = self.lancer(reponses="y\n")
        self.assertEqual(self.passage.etat, c.MANUEL, sortie)

    def test_aucun_appel_du_trousseau_et_aucun_mot_de_passe(self):
        self.fx.drapeau("db-sans-mot-de-passe")
        _, sortie, appels, _ = self.lancer(reponses="y\n")
        self.assertEqual([a for a in appels if a.startswith("security")], [])
        self.assertNotRegex(sortie, r"-w\s+\S")

    # --- échecs ------------------------------------------------------------------------------------------------------------------------
    def test_echec_du_demarrage_nomme_etape_et_commande(self):
        self.fx.drapeau("db-echec")
        code, sortie, appels, ctx = self.lancer(reponses="y\n")
        self.assertEqual(code, 1, sortie)
        self.assertEqual(self.passage.etat, c.ECHEC)
        self.assertIn("step database: failed: bash ", sortie)
        self.assertIn("db_up.sh", sortie.split("failed:")[1])
        self.assertFalse(ctx.etat.get("base_ok"))
        self.assertEqual([a for a in appels if a.startswith("uv ") and "migrate" in a and "--dry-run" not in a], [])

    def test_echec_de_la_migration_nomme_etape_et_commande(self):
        self.fx.drapeau("migrate-echec")
        code, sortie, appels, ctx = self.lancer()
        self.assertEqual(code, 1, sortie)
        self.assertIn("step database: failed: uv run ", sortie)
        self.assertIn("db.py migrate", sortie)
        self.assertFalse(ctx.etat.get("base_ok"))


if __name__ == "__main__":
    unittest.main()
