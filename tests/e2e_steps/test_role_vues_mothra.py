"""
Rôle des vues de Mothra dans les étapes de bout en bout (audit #629, B1, décision R-20261109-01) : les étapes ne posent que le rôle propre à Mothra
(pmzilla_mothra_views) et ne donnent au serveur que sa variable de mot de passe ; la sortie d'erreur du serveur passe sur la sortie standard. Les
étapes sont lues dans le dépôt de l'outil et jamais dans l'arbre testé (R-94).

    bash tests/run_all.sh e2e_steps

Remplace : tests/e2e_steps/test_transition_role_vues.py (transition entre l'ancien rôle des vues et celui de Mothra, tombée avec la fusion de B1).
Retrait : permanent, tant que les étapes posent le rôle des vues de Mothra.

Aucune base, aucun Docker, aucun serveur réel : les étapes sont sourcées, la fonction SQL est factice, le serveur est un petit script écrit dans un
dossier temporaire du test.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
ETAPES = RACINE / "tools" / "e2e_steps.sh"

NOM_ANCIEN = "PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW_VIEWS"
NOM_VUES = "PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS"
PHRASE_ERREUR = "SECRET_MISSING-temoin-sur-la-sortie-d-erreur"

SERVEUR_FACTICE = """#!/bin/bash
echo "ancien=${%s:-absent}" > "$FX/serveur-env"
echo "vues=${%s:-absent}" >> "$FX/serveur-env"
echo "retire=${PMZILLA_LAB_DB_URL:-absent}" >> "$FX/serveur-env"
echo "ancien_fichier=${%s_FILE:-absent}" >> "$FX/serveur-env"
echo "vues_fichier=${%s_FILE:-absent}" >> "$FX/serveur-env"
echo "%s" >&2
exit 1
""" % (NOM_ANCIEN, NOM_VUES, NOM_ANCIEN, NOM_VUES, PHRASE_ERREUR)


def bash(script, env=None):
    """Lance un petit script bash dans un processus neuf ; rend (code, stdout, stderr)."""
    cadre = dict(os.environ)
    cadre.update(env or {})
    fini = subprocess.run(["bash", "-c", script], cwd=RACINE, env=cadre, capture_output=True, text=True, timeout=60)
    return fini.returncode, fini.stdout, fini.stderr


class SqlDuRole(unittest.TestCase):
    def sql_recu(self):
        code, sortie, erreur = bash(
            '. tools/e2e_steps.sh; E2E_SECRET_VUES=temoin-vues; e2e_sql() { echo "<<APPEL"; cat; }; e2e_poser_role_des_vues; echo "rc=$?"'
        )
        self.assertEqual((code, erreur), (0, ""))
        return sortie

    def test_le_role_de_mothra_recoit_le_mot_de_passe(self):
        self.assertIn("ALTER ROLE pmzilla_mothra_views LOGIN PASSWORD 'temoin-vues';", self.sql_recu())

    def test_l_ancien_role_n_est_pas_touche(self):
        self.assertNotIn("pmzilla_flow_views", self.sql_recu())

    def test_un_seul_appel_de_la_fonction_sql(self):
        sql = self.sql_recu()
        self.assertEqual(sql.count("<<APPEL"), 1)
        self.assertTrue(sql.rstrip().endswith("rc=0"))

    def test_sans_mot_de_passe_rien_n_est_envoye(self):
        code, sortie, erreur = bash(
            '. tools/e2e_steps.sh; E2E_SECRET_VUES=""; e2e_sql() { echo APPELE; cat; }; e2e_poser_role_des_vues; echo "rc=$?"'
        )
        self.assertEqual((code, sortie.strip(), erreur), (0, "rc=1", ""))


class ServeurFactice(unittest.TestCase):
    def lancer(self, extra_env=None):
        """Démarre le serveur factice par la vraie fonction des étapes ; rend (sortie standard, erreur standard, contenu de serveur-env)."""
        with tempfile.TemporaryDirectory() as dossier:
            dossier = Path(dossier)
            serveur = dossier / "serveur.sh"
            serveur.write_text(SERVEUR_FACTICE, encoding="utf-8")
            serveur.chmod(0o755)
            env = {"FX": str(dossier), "PMZILLA_LAB_DB_URL": "valeur-a-retirer"}
            env.update(extra_env or {})
            code, sortie, erreur = bash(
                '. tools/e2e_steps.sh; e2e_retraits; E2E_SECRET_VUES=secret-vues-temoin; E2E_SECRET_STOCKAGE=secret-stockage-temoin; '
                'E2E_PORT_BASE=1; E2E_PORT_SERVEUR=2; E2E_RACINE=. ; E2E_CMD_SERVEUR="%s"; '
                'e2e_demarrer_serveur; wait "$E2E_SERVEUR_PID"; echo "rc_serveur=$?"' % serveur,
                env=env,
            )
            self.assertEqual(code, 0)
            return sortie, erreur, (dossier / "serveur-env").read_text(encoding="utf-8")

    def test_le_serveur_recoit_la_variable_des_vues_de_mothra(self):
        _, _, vues = self.lancer()
        self.assertIn("vues=secret-vues-temoin", vues)

    def test_le_serveur_ne_recoit_plus_la_variable_de_l_ancien_role(self):
        _, _, vues = self.lancer({NOM_ANCIEN: "intrus-ancien"})
        self.assertIn("ancien=absent", vues)

    def test_la_variable_des_vues_est_gardee_meme_si_l_environnement_en_porte_deja_une(self):
        _, _, vues = self.lancer({NOM_VUES: "intrus-vues"})
        self.assertIn("vues=secret-vues-temoin", vues)

    def test_les_autres_variables_de_la_base_restent_retirees(self):
        _, _, vues = self.lancer()
        self.assertIn("retire=absent", vues)

    def test_la_sortie_d_erreur_du_serveur_passe_par_la_sortie_standard(self):
        sortie, erreur, _ = self.lancer()
        self.assertIn(PHRASE_ERREUR, sortie)
        self.assertNotIn(PHRASE_ERREUR, erreur)
        self.assertIn("rc_serveur=1", sortie)

    def test_les_variables_file_sont_retirees(self):
        _, _, vues = self.lancer({NOM_VUES + "_FILE": "intrus-vues", NOM_ANCIEN + "_FILE": "intrus-ancien"})
        self.assertIn("ancien_fichier=absent", vues)
        self.assertIn("vues_fichier=absent", vues)

    def test_les_etapes_n_affichent_pas_le_secret(self):
        """Prouve que e2e_demarrer_serveur n'affiche pas le secret (le serveur factice ne l'affiche jamais)."""
        sortie, erreur, _ = self.lancer()
        self.assertNotIn("secret-vues-temoin", sortie + erreur)
        self.assertNotIn("secret-stockage-temoin", sortie + erreur)


if __name__ == "__main__":
    unittest.main()
