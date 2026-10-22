"""Liste de revue des entrées extérieures et sous-commande review-teams (change names-and-team-review, groupe 4, tâche 4.1).

    bash tests/run_all.sh export_jira_api </dev/null

Spécifications : jira-flow-export (« Review list of outside entries kept apart from the catalogue », « Outside entries added to the
review list by identifier », « Catalogue entries seen on export tickets signalled for review », « Team subcommands refused inside a
Claude Code session »). Aucun appel à Jira ; référentiel, catalogue et liste de revue INVENTÉS, libellés sentinelles : aucun libellé
ne doit paraître dans la sortie.
"""
import os
import stat
import unittest
from unittest import mock

import yaml

from test_equipes_commandes import Socle, REF_COMPLET, ENTETE, objet
from test_catalogue_export import catalogue, entree

NOM = "equipes-revues.yaml"
CATALOGUE = catalogue(entree("Libelle-Quimbo", "'50', '51'"), entree("Libelle-Wumpa", "'60'"),
                      entree("Libelle-Plinth", "'52'", "    obsolete: true\n"), entree("Libelle-Vexor", "'1'"))


class Base(Socle):
    def sources(self, revue=None):
        self.ecrire("organisation.yaml", REF_COMPLET)
        self.ecrire("equipes-jira.yaml", CATALOGUE)
        if revue is not None:
            self.ecrire(NOM, revue)

    def exporter(self, *libelles):
        """Tickets stockés, un par libellé d'équipe : la vue des équipes vues rend un décompte par nom (database-only, D13)."""
        self.vues = {}
        for nom in libelles:
            self.vues[nom] = self.vues.get(nom, 0) + 1

    def revue(self):
        return yaml.safe_load((self.flux / NOM).read_text(encoding="utf-8"))["reviewed_ids"]


class LectureDeLaListeDeRevue(Base):
    """Lecture stricte (D4) : refus avec chemin de clé et ligne, jamais une valeur ni un libellé."""

    def test_liste_absente_toute_entree_vue_est_nouvelle(self):
        self.sources()
        self.exporter("Libelle-Quimbo", "Libelle-Wumpa")
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("à revoir : 2 entrées, 2 tickets", sortie)
        self.assertIn("déjà revues : 0 entrées", sortie)
        self.assertIn("identifiants à revoir : 50 ; 51 ; 60", sortie)

    def test_cle_de_libelle_refusee_sans_imprimer_le_libelle(self):
        self.sources("reviewed_ids: ['50']\nLibelle-Sentinelle: ['51']\n")
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 1, sortie)
        self.assertIn("equipes-revues.yaml", sortie)
        self.assertIn("L2", sortie)
        self.assertNotIn("Sentinelle", sortie)
        self.assertNotIn("Libelle", sortie)

    def test_cle_inconnue_dans_une_autre_langue(self):
        self.sources("reviewed_ids: ['50']\nautre: 1\n")
        code, sortie = self.lancer("check-teams", "--language", "en")
        self.assertEqual(code, 1, sortie)
        self.assertIn("L2", sortie)

    def test_valeur_qui_n_est_pas_un_identifiant_refusee_sans_la_valeur(self):
        for valeur in ("'Libelle Sentinelle'", "''", "[1]", "{a: 1}", "true"):
            with self.subTest(valeur=valeur):
                self.sources(f"reviewed_ids:\n  - '50'\n  - {valeur}\n")
                code, sortie = self.lancer("check-teams")
                self.assertEqual(code, 1, sortie)
                self.assertIn("reviewed_ids[1]", sortie)
                self.assertIn("L1", sortie)
                self.assertNotIn("Sentinelle", sortie)

    def test_identifiant_en_double_refuse_sans_la_valeur(self):
        self.sources("reviewed_ids: ['50', '51', '50']\n")
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 1, sortie)
        self.assertIn("reviewed_ids[2]", sortie)
        self.assertNotIn("50", sortie.replace("reviewed_ids", ""))

    def test_fichier_qui_n_est_pas_un_bloc_de_cles_refuse(self):
        self.sources("- '50'\n")
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 1, sortie)

    def test_cle_ecrite_deux_fois_refusee(self):
        self.sources("reviewed_ids: ['50']\nreviewed_ids: ['51']\n")
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 1, sortie)

    def test_liste_vide_acceptee(self):
        self.sources("reviewed_ids: []\n")
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)

    def test_identifiants_entiers_acceptes_comme_textes(self):
        self.sources("reviewed_ids: [50, 51]\n")
        self.exporter("Libelle-Quimbo", "Libelle-Wumpa")
        _, sortie = self.lancer("check-teams")
        self.assertIn("déjà revues : 1 entrées", sortie)


class SeparationDesEntreesVues(Base):
    """D5 : déjà revues / nouvelles ; seuls les identifiants des nouvelles sont listés ; code de sortie inchangé."""

    def test_entree_deja_revue_comptee_a_part(self):
        self.sources("reviewed_ids: ['50', '51']\n")
        self.exporter("Libelle-Quimbo", "Libelle-Quimbo", "Libelle-Wumpa")
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("à revoir : 1 entrées, 1 tickets", sortie)
        self.assertIn("déjà revues : 1 entrées", sortie)
        self.assertIn("identifiants à revoir : 60", sortie)
        self.assertNotIn("50", sortie.split("identifiants à revoir")[1])
        self.verifier_neutre(sortie)

    def test_entree_revue_en_partie_reste_nouvelle_avec_ses_seuls_identifiants_manquants(self):
        self.sources("reviewed_ids: ['50']\n")
        self.exporter("Libelle-Quimbo")
        _, sortie = self.lancer("check-teams")
        self.assertIn("à revoir : 1 entrées, 1 tickets", sortie)
        self.assertIn("déjà revues : 0 entrées", sortie)
        self.assertIn("identifiants à revoir : 51", sortie)

    def test_tout_revu_aucune_ligne_d_identifiants(self):
        self.sources("reviewed_ids: ['50', '51', '60']\n")
        self.exporter("Libelle-Quimbo", "Libelle-Wumpa")
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("à revoir : 0 entrées, 0 tickets", sortie)
        self.assertIn("déjà revues : 2 entrées", sortie)
        self.assertNotIn("identifiants à revoir", sortie)

    def test_en_anglais(self):
        self.sources("reviewed_ids: ['60']\n")
        self.exporter("Libelle-Quimbo", "Libelle-Wumpa")
        _, sortie = self.lancer("check-teams", "--language", "en")
        self.assertIn("catalogue teams seen on export tickets, to review: 1 entries, 1 tickets", sortie)
        self.assertIn("catalogue teams seen on export tickets, already reviewed: 1 entries", sortie)
        self.assertIn("identifiers to review: 50; 51", sortie)

    def test_aucune_entree_vue_aucune_ligne_de_revue(self):
        self.sources("reviewed_ids: ['50']\n")
        self.exporter("Equipe A")
        _, sortie = self.lancer("check-teams")
        self.assertNotIn("revue", sortie.replace("liste de revue", ""))
        self.assertNotIn("déjà revues", sortie)

    def test_base_injoignable_ou_vide_la_revue_est_sautee(self):
        self.sources("reviewed_ids: ['50']\n")
        _, sortie = self.lancer("check-teams")
        self.assertIn("base injoignable : revue du catalogue sautée", sortie)
        self.vues = {}
        _, sortie = self.lancer("check-teams")
        self.assertIn("aucun ticket dans la base : revue du catalogue sautée", sortie)

    def test_le_code_4_est_inchange(self):
        self.sources("reviewed_ids: ['50']\n")
        self.ecrire("equipes-assets.yaml", "equipes: {'700': Table X}\n")
        self.exporter("Libelle-Quimbo")
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 4, sortie)

    def test_check_teams_n_ecrit_pas_la_liste(self):
        self.sources("reviewed_ids: ['50']\n")
        self.exporter("Libelle-Quimbo")
        avant = self.etat_du_dossier()
        self.lancer("check-teams")
        self.assertEqual(self.etat_du_dossier(), avant)

    def test_fonction_de_separation(self):
        import export_jira_api_equipes as eq
        vues = {"a": ["1", "2"], "b": ["3"], "c": ["4", "5"]}
        revues, nouvelles = eq.split_seen_entries(vues, ["1", "2", "5"])
        self.assertEqual(revues, ["a"])
        self.assertEqual(nouvelles, {"b": ["3"], "c": ["4"]})
        self.assertEqual(eq.split_seen_entries({}, ["1"]), ([], {}))
        self.assertEqual(eq.split_seen_entries(vues, []), ([], vues))


class MigrationEtListeDeRevue(Base):
    def test_migrate_teams_ne_lit_ni_n_ecrit_ni_ne_supprime_la_liste(self):
        revue = "reviewed_ids:\n  - '50'\n  - '51'\n"
        self.ecrire(NOM, revue)
        self.liste_assets(objet(1, libelle="Zorblax Quimbo"))
        lues = []
        vrai = type(self.flux).read_text
        with mock.patch.object(type(self.flux), "read_text", lambda p, *a, **k: (lues.append(p.name), vrai(p, *a, **k))[1]):
            code, sortie = self.lancer("migrate-teams", "--from-assets", str(self.flux / "equipes-assets-complet-2026-10-16.csv"))
        self.assertEqual(code, 0, sortie)
        self.assertNotIn(NOM, lues)
        self.assertEqual((self.flux / NOM).read_text(encoding="utf-8"), revue)

    def test_la_liste_survit_et_check_teams_la_relit(self):
        self.ecrire(NOM, "reviewed_ids: ['50', '51']\n")
        self.ecrire("organisation.yaml", REF_COMPLET)
        self.liste_assets(objet(50, libelle="Libelle-Quimbo"), objet(51, libelle="Libelle-Quimbo"))
        code, sortie = self.lancer("migrate-teams", "--from-assets", str(self.flux / "equipes-assets-complet-2026-10-16.csv"))
        self.assertEqual(code, 0, sortie)
        self.exporter("Libelle-Quimbo")
        _, sortie = self.lancer("check-teams")
        self.assertIn("déjà revues : 1 entrées", sortie)


class AjoutALaListeDeRevue(Base):
    """D6 : review-teams --add, plusieurs identifiants par commande, tout ou rien."""

    def test_un_identifiant_ajoute_fichier_reserve_au_proprietaire(self):
        self.sources()
        code, sortie = self.lancer("review-teams", "--add", "50")
        self.assertEqual(code, 0, sortie)
        self.assertIn("identifiants ajoutés à la liste de revue : 1", sortie)
        self.assertNotIn("déjà dans la liste de revue", sortie)
        self.assertEqual(self.revue(), ["50"])
        self.assertEqual(stat.S_IMODE((self.flux / NOM).stat().st_mode), 0o600)
        self.verifier_neutre(sortie)

    def test_plusieurs_identifiants_valides_dans_une_commande(self):
        self.sources()
        code, sortie = self.lancer("review-teams", "--add", "50", "51", "60", "52")
        self.assertEqual(code, 0, sortie)
        self.assertIn("identifiants ajoutés à la liste de revue : 4", sortie)
        self.assertEqual(self.revue(), ["50", "51", "52", "60"])

    def test_identifiants_deja_presents_comptes_a_part_en_anglais(self):
        self.sources("reviewed_ids: ['50']\n")
        code, sortie = self.lancer("review-teams", "--add", "50", "51", "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("identifiers added to the review list: 1", sortie)
        self.assertIn("identifiers already in the review list: 1", sortie)
        self.assertEqual(self.revue(), ["50", "51"])

    def test_identifiant_donne_deux_fois_ajoute_une_fois(self):
        self.sources()
        code, sortie = self.lancer("review-teams", "--add", "50", "50")
        self.assertEqual(code, 0, sortie)
        self.assertIn("identifiants ajoutés à la liste de revue : 1", sortie)
        self.assertEqual(self.revue(), ["50"])

    def test_un_identifiant_inconnu_refuse_toute_la_commande_et_n_ecrit_rien(self):
        self.sources("reviewed_ids: ['60']\n")
        avant = self.etat_du_dossier()
        code, sortie = self.lancer("review-teams", "--add", "50", "999", "51")
        self.assertEqual(code, 1, sortie)
        self.assertIn("identifiant hors du catalogue des équipes extérieures, rien n'est écrit : 999", sortie)
        self.assertNotIn("50", sortie)
        self.assertEqual(self.etat_du_dossier(), avant)

    def test_plusieurs_inconnus_listes_dans_la_phrase_en_anglais(self):
        self.sources()
        code, sortie = self.lancer("review-teams", "--add", "50", "998", "999", "--language", "en")
        self.assertEqual(code, 1, sortie)
        self.assertIn("not an outside catalogue identifier, nothing written: 998; 999", sortie)
        self.assertFalse((self.flux / NOM).exists())

    def test_identifiant_d_une_equipe_du_referentiel_refuse(self):
        self.sources()
        code, sortie = self.lancer("review-teams", "--add", "50", "1")
        self.assertEqual(code, 1, sortie)
        self.assertIn("rien n'est écrit : 1", sortie)
        self.assertFalse((self.flux / NOM).exists())

    def test_identifiant_d_une_entree_obsolete_accepte(self):
        self.sources()
        code, sortie = self.lancer("review-teams", "--add", "52")
        self.assertEqual(code, 0, sortie)

    def test_sans_catalogue_tout_identifiant_est_inconnu(self):
        code, sortie = self.lancer("review-teams", "--add", "50")
        self.assertEqual(code, 1, sortie)
        self.assertFalse((self.flux / NOM).exists())

    def test_liste_de_revue_refusee_rien_n_est_ecrit(self):
        self.sources("reviewed_ids: ['50', '50']\n")
        avant = self.etat_du_dossier()
        code, sortie = self.lancer("review-teams", "--add", "51")
        self.assertEqual(code, 1, sortie)
        self.assertEqual(self.etat_du_dossier(), avant)

    def test_aucune_option_de_marquage_global(self):
        self.sources()
        avant = self.etat_du_dossier()
        with mock.patch("pathlib.Path.read_text", side_effect=AssertionError("lu")):
            code, sortie = self.lancer("review-teams", "--add-seen")
            code2, _ = self.lancer("review-teams", "--add", "50", "--add-seen")
        self.assertEqual(code, 2, sortie)
        self.assertEqual(code2, 2)
        self.assertEqual(self.etat_du_dossier(), avant)

    def test_option_add_absente(self):
        self.sources()
        avant = self.etat_du_dossier()
        with mock.patch("pathlib.Path.read_text", side_effect=AssertionError("lu")):
            code, sortie = self.lancer("review-teams")
        self.assertEqual(code, 2, sortie)
        self.assertEqual(self.etat_du_dossier(), avant)

    def test_refus_dans_une_session_avant_toute_lecture(self):
        self.sources()
        avant = self.etat_du_dossier()
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}), mock.patch("pathlib.Path.read_text", side_effect=AssertionError("lu")), \
                mock.patch("pathlib.Path.is_file", side_effect=AssertionError("lu")), \
                mock.patch("pathlib.Path.exists", side_effect=AssertionError("lu")):
            code, sortie = self.lancer("review-teams", "--add", "50")
        self.assertEqual(code, 3, sortie)
        self.assertIn("Refusé dans une session Claude Code", sortie)
        self.assertEqual(self.etat_du_dossier(), avant)

    def test_aucun_appel_a_jira_ni_fichier_temporaire_restant(self):
        self.sources()
        self.lancer("review-teams", "--add", "50")
        self.assertEqual(self.faux.requetes, [])
        self.assertEqual(sorted(p for p in self.fichiers() if p.endswith(".tmp")), [])

    def test_la_commande_est_dans_l_aide(self):
        code, sortie = self.lancer("--help")
        self.assertIn("review-teams", sortie)


if __name__ == "__main__":
    unittest.main()
