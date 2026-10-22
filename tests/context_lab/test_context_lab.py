"""
L'outil des notes de contexte (organisation-context, design D1, D2, D7, D9, D16 ; tâche 3.2) : tools/context_lab.py.

    bash tests/run_all.sh context_lab

Chaque cas bâtit un faux lab dans un dossier temporaire (voir fixtures_context.py) : jamais le vrai dossier de contexte, jamais la vraie
liste des noms sensibles. Aucun accès aux originaux : des surveillants échouent sur tout chemin sous `originaux/`, et la sentinelle
des originaux et le corps des notes ne paraissent dans aucune sortie.
"""
import os
import stat
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures_context import (ANCIEN_DOSSIER, CORPS_UNIQUE, IDENTIFIANT, NOM_EXTRAIT, NOM_GENERIQUE, NOM_SENSIBLE, OUTILS,  # noqa: E402
                              SENTINELLE, Contexte, Surveillant, note, notes_de_reference)


class Base(unittest.TestCase):
    def fabrique(self, **options):
        ctx = Contexte(**options)
        self.addCleanup(ctx.close)
        return ctx

    def assertSansFuite(self, *sorties):
        for sortie in sorties:
            self.assertNotIn(SENTINELLE, sortie)
            self.assertNotIn(CORPS_UNIQUE, sortie)
            self.assertNotIn(NOM_SENSIBLE, sortie)
            self.assertNotIn(IDENTIFIANT, sortie)


class Dossier(Base):
    def test_init_cree_les_deux_sous_dossiers_pour_le_proprietaire_seul(self):
        ctx = self.fabrique(avec_dossier=False)
        code, sortie, erreur = ctx.lancer(["init", "--yes"])
        self.assertEqual(code, 0, erreur)
        for chemin in (ctx.dossier, ctx.originaux, ctx.notes):
            self.assertEqual(stat.S_IMODE(chemin.stat().st_mode), 0o700, chemin.name)

    def test_init_sans_confirmation_ne_cree_rien(self):
        ctx = self.fabrique(avec_dossier=False)
        code, sortie, _ = ctx.lancer(["init"], stdin="n\n")
        self.assertEqual(code, 0)
        self.assertFalse(ctx.dossier.exists())
        code, _, _ = ctx.lancer(["init"], stdin="y\n")
        self.assertEqual(code, 0)
        self.assertTrue(ctx.notes.is_dir())

    def test_dossier_absent_hors_init(self):
        ctx = self.fabrique(avec_dossier=False)
        for argv in (["check"], ["list"], ["add"], ["review", "x.md", "2027-01-01"]):
            with self.subTest(argv):
                code, sortie, erreur = ctx.lancer(argv, stdin=note())
                self.assertEqual(code, 6)
                self.assertIn("context folder not found: run init", erreur)
                self.assertFalse(ctx.dossier.exists())

    def test_dossier_dans_un_arbre_git_refuse(self):
        ctx = self.fabrique()
        depot = ctx.tmp / "depot"
        (depot / "contexte").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(depot)], check=True, capture_output=True)
        env = ctx.env(PMZILLA_LAB_CONTEXT=str(depot / "contexte"))
        for argv in (["init", "--yes"], ["check"], ["list"], ["add"]):
            with self.subTest(argv):
                code, _, erreur = ctx.lancer(argv, stdin=note(), env=env)
                self.assertEqual(code, 2)
                self.assertIn("context folder inside a Git work tree, refused", erreur)
        self.assertEqual(list((depot / "contexte").iterdir()), [])

    def test_dossier_dans_l_espace_de_travail_refuse(self):
        ctx = self.fabrique()
        env = ctx.env(PMZILLA_LAB_CONTEXT=str(ctx.workspace / "contexte"))
        code, _, erreur = ctx.lancer(["init", "--yes"], env=env)
        self.assertEqual(code, 2)
        self.assertIn("context folder inside a Git work tree, refused", erreur)
        self.assertFalse((ctx.workspace / "contexte").exists())

    def test_ancien_dossier_a_cote_du_nouveau(self):
        ctx = self.fabrique()
        (ctx.lab / ANCIEN_DOSSIER).mkdir()
        avant = ctx.arbre()
        for argv in (["init", "--yes"], ["check"], ["list"], ["add"], ["review", "x.md", "2027-01-01"]):
            with self.subTest(argv):
                code, sortie, erreur = ctx.lancer(argv, stdin=note())
                self.assertEqual(code, 2)
                self.assertIn("former context folder still present: finish the move", erreur)
                self.assertEqual(sortie, "")
        self.assertEqual(ctx.arbre(), avant)

    def test_lien_de_compatibilite_refuse_sans_toucher_derriere_le_lien(self):
        ctx = self.fabrique()
        os.symlink(ctx.dossier, ctx.lab / ANCIEN_DOSSIER)
        with Surveillant(ctx.originaux).actif() as surveillant:
            code, _, erreur = ctx.lancer(["check"])
        self.assertEqual(code, 2)
        self.assertIn("former context folder still present: finish the move", erreur)
        self.assertEqual(surveillant.vus, [])


class EnTete(Base):
    def lancer_ajout(self, texte):
        ctx = self.fabrique()
        avant = ctx.arbre()
        code, sortie, erreur = ctx.lancer(["add"], stdin=texte)
        self.assertEqual(ctx.arbre(), avant, "rien n'est écrit")
        return code, sortie + erreur

    def test_chaque_regle_de_l_en_tete_son_code_et_sa_phrase(self):
        cas = [
            ("header missing", "pas d'en-tête\n"),
            ("header field missing: title", note(sans=("title",))),
            ("header field missing: date", note(sans=("date",))),
            ("header field missing: nature", note(sans=("nature",))),
            ("header field missing: source", note(sans=("source",))),
            ("header field missing: review", note(sans=("review",))),
            ("header field not a date: date", note(date="2026-13-45")),
            ("header field not a date: review", note(review="bientôt")),
            ("nature must be declarative or measured", note(nature="rumeur")),
            ("review date must be after the note date", note(date="2026-09-01", review="2026-09-01")),
            ("review date must be after the note date", note(date="2026-09-01", review="2026-08-01")),
            ("kind must be map", note(kind="autre")),
        ]
        for phrase, texte in cas:
            with self.subTest(phrase):
                code, sortie = self.lancer_ajout(texte)
                self.assertEqual(code, 3)
                self.assertIn(phrase, sortie)

    def test_l_ordre_des_regles(self):
        code, sortie = self.lancer_ajout(note(sans=("nature",), review="2026-01-01", date="2026-09-01"))
        self.assertIn("header field missing: nature", sortie)
        code, sortie = self.lancer_ajout(note(date="pas-une-date", nature="rumeur"))
        self.assertIn("header field not a date: date", sortie)

    def test_aucun_champ_n_est_deduit_du_nom_ou_du_corps(self):
        texte = "---\ntitle: T\ndate: 2026-09-01\nnature: declarative\nreview: 2027-01-01\n---\nsource: dans le corps\n"
        code, sortie = self.lancer_ajout(texte)
        self.assertEqual(code, 3)
        self.assertIn("header field missing: source", sortie)


class Ajout(Base):
    def test_note_valide_ecrite_en_600_sans_ligne_du_corps(self):
        ctx = self.fabrique()
        code, sortie, erreur = ctx.lancer(["add"], stdin=note(title="Équipes et flux"))
        self.assertEqual(code, 0, erreur)
        nom = "2026-09-01-equipes-et-flux.md"
        self.assertTrue((ctx.notes / nom).is_file())
        self.assertEqual(stat.S_IMODE((ctx.notes / nom).stat().st_mode), 0o600)
        self.assertIn(f"note written: {nom}", sortie)
        self.assertIn("indexed at the next daily run", sortie)
        self.assertSansFuite(sortie, erreur)

    def test_la_carte_a_un_nom_fixe(self):
        ctx = self.fabrique()
        code, sortie, _ = ctx.lancer(["add"], stdin=note(title="Carte", kind="map"))
        self.assertEqual(code, 0)
        self.assertTrue((ctx.notes / "carte-contexte.md").is_file())
        code, _, erreur = ctx.lancer(["add"], stdin=note(title="Autre carte", kind="map"))
        self.assertEqual(code, 4)

    def test_nom_existant_refuse_octet_pour_octet(self):
        ctx = self.fabrique(notes={"2026-09-01-organisation-de-test.md": note()})
        avant = (ctx.notes / "2026-09-01-organisation-de-test.md").read_bytes()
        code, _, erreur = ctx.lancer(["add"], stdin=note(body="autre corps\n"))
        self.assertEqual(code, 4)
        self.assertIn("note exists, not overwritten: 2026-09-01-organisation-de-test.md", erreur)
        self.assertEqual((ctx.notes / "2026-09-01-organisation-de-test.md").read_bytes(), avant)

    def test_nom_sensible_refuse_avec_le_numero_de_ligne_seulement(self):
        ctx = self.fabrique()
        texte = note(body=f"première ligne\nle rôle voit {NOM_SENSIBLE} souvent\n")
        numero = texte.splitlines().index(f"le rôle voit {NOM_SENSIBLE} souvent") + 1
        avant = ctx.arbre()
        code, sortie, erreur = ctx.lancer(["add"], stdin=texte)
        self.assertEqual(code, 5)
        self.assertIn(f"sensitive name in line {numero}", erreur)
        self.assertSansFuite(sortie, erreur)
        self.assertNotIn("le rôle voit", sortie + erreur)
        self.assertEqual(ctx.arbre(), avant)

    def test_identifiant_personnel_refuse(self):
        ctx = self.fabrique()
        texte = note(body=f"dossier {IDENTIFIANT} ici\n")
        code, sortie, erreur = ctx.lancer(["add"], stdin=texte)
        self.assertEqual(code, 5)
        self.assertRegex(erreur, r"personal identifier in line \d+")
        self.assertSansFuite(sortie, erreur)

    def test_liste_absente_refuse_toute_ecriture(self):
        ctx = self.fabrique(avec_liste=False)
        code, _, erreur = ctx.lancer(["add"], stdin=note())
        self.assertEqual(code, 6)
        self.assertIn("sensitive-names list unavailable: nothing written", erreur)
        self.assertEqual(ctx.arbre(), {})

    def test_liste_vide_refuse_toute_ecriture(self):
        ctx = self.fabrique()
        ctx.liste.write_text("# rien\n", encoding="utf-8")
        code, _, erreur = ctx.lancer(["add"], stdin=note())
        self.assertEqual(code, 6)
        self.assertIn("sensitive-names list unavailable", erreur)


class NomsDeLExtrait(Base):
    """Les noms d'équipes de l'extrait dans la garde (context-index-name-guard, design D4 ; tâches 2.2 et 2.4) : refus avec la position,
    jamais le nom."""

    def test_add_refuse_un_nom_de_l_extrait_avec_sa_ligne_et_sans_le_nom(self):
        ctx = self.fabrique()
        ctx.ecrire_extrait()
        texte = note(body=f"première ligne\nle rôle travaille avec {NOM_EXTRAIT}\n")
        numero = texte.splitlines().index(f"le rôle travaille avec {NOM_EXTRAIT}") + 1
        code, sortie, erreur = ctx.lancer(["add"], stdin=texte)
        self.assertEqual(code, 5)
        self.assertIn(f"extract team name in line {numero}", erreur)
        self.assertNotIn(NOM_EXTRAIT, sortie + erreur)
        self.assertNotIn("Zorblax", sortie + erreur)
        self.assertNotIn("le rôle travaille", sortie + erreur)
        self.assertEqual(ctx.arbre(), {})

    def test_un_nom_generique_de_l_extrait_ne_refuse_pas(self):
        ctx = self.fabrique()
        ctx.ecrire_extrait()
        code, _, erreur = ctx.lancer(["add"], stdin=note(body=f"le rôle voit {NOM_GENERIQUE}\n"))
        self.assertEqual(code, 0, erreur)

    def test_check_signale_le_nom_de_l_extrait_sans_le_nom(self):
        ctx = self.fabrique(notes={"2026-09-01-a.md": note(body=f"x\n{NOM_EXTRAIT}\n")})
        ctx.ecrire_extrait()
        code, sortie, erreur = ctx.lancer(["check"])
        self.assertEqual(code, 1)
        self.assertRegex(sortie, r"invalid: extract team name in line \d+")
        self.assertNotIn(NOM_EXTRAIT, sortie + erreur)

    def test_review_refuse_un_nom_de_l_extrait(self):
        ctx = self.fabrique(notes={"2026-09-01-a.md": note(body=f"{NOM_EXTRAIT}\n")})
        ctx.ecrire_extrait()
        avant = ctx.arbre()
        code, sortie, erreur = ctx.lancer(["review", "2026-09-01-a.md", "2027-06-01"])
        self.assertEqual(code, 5)
        self.assertIn("extract team name in line", erreur)
        self.assertNotIn(NOM_EXTRAIT, sortie + erreur)
        self.assertEqual(ctx.arbre(), avant)

    def test_liste_vide_avec_un_extrait_reste_indisponible(self):
        ctx = self.fabrique()
        ctx.ecrire_extrait()
        ctx.liste.write_text("# rien\n", encoding="utf-8")
        code, sortie, erreur = ctx.lancer(["add"], stdin=note())
        self.assertEqual(code, 6)
        self.assertIn("sensitive-names list unavailable: nothing written", erreur)
        self.assertEqual(ctx.arbre(), {})

    def test_fuite_le_nom_fictif_n_apparait_dans_aucune_sortie(self):
        ctx = self.fabrique(notes={"2026-09-01-a.md": note(body=f"{NOM_EXTRAIT}\n"),
                                   "carte-contexte.md": note(title="Carte", kind="map", body=f"## Forums\n\n{NOM_EXTRAIT}\n")})
        ctx.ecrire_extrait()
        sorties = []
        for argv, stdin in ((["add"], note(title="Autre", body=f"{NOM_EXTRAIT}\n")), (["check"], ""), (["list"], ""),
                            (["review", "2026-09-01-a.md", "2027-06-01"], "")):
            code, sortie, erreur = ctx.lancer(argv, stdin=stdin)
            sorties += [sortie, erreur]
        for texte in sorties:
            self.assertNotIn(NOM_EXTRAIT, texte)
        self.assertIn("extract team name in line", "".join(sorties))


class ControleEtListe(Base):
    def lancer_tout(self, ctx):
        return ctx.lancer(["check"]), ctx.lancer(["list"])

    def test_check_sur_les_notes_de_reference(self):
        ctx = self.fabrique(notes=notes_de_reference())
        code, sortie, erreur = ctx.lancer(["check"])
        self.assertEqual(code, 1)
        self.assertIn("2026-09-01-organisation-de-test.md  2026-09-01  declarative  2027-03-01  ok", sortie)
        self.assertIn("2026-06-01-note-a-revoir.md  2026-06-01  declarative  2026-09-01  stale", sortie)
        self.assertIn("invalid: header field missing: source", sortie)
        self.assertIn("invalid: nature must be declarative or measured", sortie)
        self.assertIn("invalid: review date must be after the note date", sortie)
        self.assertIn("6 notes, 1 stale, 3 invalid", sortie)
        self.assertSansFuite(sortie, erreur)

    def test_une_note_a_revoir_n_est_pas_une_erreur(self):
        ctx = self.fabrique(notes={"2026-06-01-ancienne.md": note(date="2026-06-01", review="2026-09-01")})
        code, sortie, _ = ctx.lancer(["check"])
        self.assertEqual(code, 0)
        self.assertIn("stale", sortie)
        self.assertIn("1 notes, 1 stale, 0 invalid", sortie)

    def test_note_editee_a_la_main_sans_source(self):
        ctx = self.fabrique(notes={"2026-09-01-a.md": note(sans=("source",))})
        code, sortie, _ = ctx.lancer(["check"])
        self.assertEqual(code, 1)
        self.assertIn("invalid: header field missing: source", sortie)

    def test_deuxieme_carte(self):
        ctx = self.fabrique(notes={"carte-contexte.md": note(kind="map"), "2026-09-05-autre-carte.md": note(title="Autre", kind="map")})
        code, sortie, _ = ctx.lancer(["check"])
        self.assertEqual(code, 1)
        self.assertEqual(sortie.count("more than one context map"), 1)
        self.assertIn("2026-09-05-autre-carte.md", sortie.split("more than one context map")[0].splitlines()[-1])

    def test_check_applique_la_confidentialite_et_list_non(self):
        ctx = self.fabrique(notes={"2026-09-01-a.md": note(body=f"{NOM_SENSIBLE}\n"), "2026-09-02-b.md": note(title="B", date="2026-09-02",
                                                                                                     body=f"{IDENTIFIANT}\n")})
        code, sortie, _ = ctx.lancer(["check"])
        self.assertEqual(code, 1)
        self.assertIn("invalid: sensitive name in line", sortie)
        self.assertIn("invalid: personal identifier in line", sortie)
        self.assertSansFuite(sortie)
        code, sortie, _ = ctx.lancer(["list"])
        self.assertEqual(code, 0)
        self.assertNotIn("invalid:", sortie)

    def test_check_sans_liste_le_dit_et_sort_en_1(self):
        ctx = self.fabrique(avec_liste=False, notes={"2026-09-01-a.md": note()})
        code, sortie, erreur = ctx.lancer(["check"])
        self.assertEqual(code, 1)
        self.assertIn("sensitive-names list unavailable", erreur)

    def test_list_n_a_pas_besoin_de_la_liste(self):
        ctx = self.fabrique(avec_liste=False, notes={"2026-09-01-a.md": note()})
        code, sortie, _ = ctx.lancer(["list"])
        self.assertEqual(code, 0)
        self.assertIn("1 notes, 0 stale, 0 invalid", sortie)

    def test_les_fichiers_a_tiret_bas_et_les_sous_dossiers_sont_ignores(self):
        ctx = self.fabrique(notes={"_brouillon.md": note(), "2026-09-01-a.md": note()})
        (ctx.notes / "sous").mkdir()
        (ctx.notes / "sous" / "2026-09-09-b.md").write_text(note(), encoding="utf-8")
        _, sortie, _ = ctx.lancer(["list"])
        self.assertIn("1 notes", sortie)


class Revue(Base):
    def test_seule_la_date_de_revue_change(self):
        ctx = self.fabrique(notes={"2026-09-01-a.md": note(body="ligne 1\nreview: dans le corps\nligne 3\n")})
        avant = (ctx.notes / "2026-09-01-a.md").read_text(encoding="utf-8")
        code, sortie, erreur = ctx.lancer(["review", "2026-09-01-a.md", "2027-05-05"])
        self.assertEqual(code, 0, erreur)
        apres = (ctx.notes / "2026-09-01-a.md").read_text(encoding="utf-8")
        self.assertEqual(apres, avant.replace("review: 2027-03-01", "review: 2027-05-05", 1))
        self.assertIn("review: dans le corps", apres)
        self.assertEqual(stat.S_IMODE((ctx.notes / "2026-09-01-a.md").stat().st_mode), 0o600)
        self.assertSansFuite(sortie, erreur)

    def test_refus_sans_ecriture(self):
        ctx = self.fabrique(notes={"2026-09-01-a.md": note(), "2026-09-02-b.md": note(title="B", body=f"{NOM_SENSIBLE}\n")})
        avant = ctx.arbre()
        cas = [(["review", "inconnue.md", "2027-05-05"], 2, "unknown note"),
               (["review", "../x.md", "2027-05-05"], 2, "unknown note"),
               (["review", "2026-09-01-a.md", "demain"], 3, "header field not a date: review"),
               (["review", "2026-09-01-a.md", "2026-09-01"], 3, "review date must be after the note date"),
               (["review", "2026-09-01-a.md", "2026-01-01"], 3, "review date must be after the note date"),
               (["review", "2026-09-02-b.md", "2027-05-05"], 5, "sensitive name in line")]
        for argv, attendu, phrase in cas:
            with self.subTest(argv):
                code, sortie, erreur = ctx.lancer(argv)
                self.assertEqual(code, attendu)
                self.assertIn(phrase, erreur)
        self.assertEqual(ctx.arbre(), avant)

    def test_liste_absente(self):
        ctx = self.fabrique(avec_liste=False, notes={"2026-09-01-a.md": note()})
        code, _, erreur = ctx.lancer(["review", "2026-09-01-a.md", "2027-05-05"])
        self.assertEqual(code, 6)
        self.assertIn("sensitive-names list unavailable: nothing written", erreur)


class Originaux(Base):
    def test_aucune_sous_commande_ne_touche_aux_originaux(self):
        ctx = self.fabrique(notes=notes_de_reference())
        sorties = []
        with Surveillant(ctx.originaux).actif() as surveillant:
            for argv, stdin in ((["check"], ""), (["list"], ""), (["add"], note(title="Nouvelle")),
                                (["review", "2026-09-01-organisation-de-test.md", "2027-06-06"], ""), (["init", "--yes"], "")):
                code, sortie, erreur = ctx.lancer(argv, stdin=stdin)
                sorties += [sortie, erreur]
        self.assertEqual(surveillant.vus, [])
        self.assertSansFuite(*sorties)
        self.assertEqual((ctx.originaux / "piege.txt").read_text(encoding="utf-8"), SENTINELLE)

    def test_init_sur_un_dossier_absent_ne_surveille_que_l_interieur(self):
        ctx = self.fabrique(avec_dossier=False)
        with Surveillant(ctx.originaux).actif() as surveillant:
            code, _, _ = ctx.lancer(["init", "--yes"])
        self.assertEqual(code, 0)
        self.assertEqual(surveillant.vus, [])


class Ligne_de_commande(Base):
    def test_lancement_reel_par_python(self):
        ctx = self.fabrique(notes={"2026-09-01-a.md": note()})
        fait = subprocess.run([sys.executable, "-B", str(OUTILS / "context_lab.py"), "list"], capture_output=True, text=True, env=ctx.env(),
                              cwd=str(ctx.tmp))
        self.assertEqual(fait.returncode, 0, fait.stderr)
        self.assertIn("1 notes", fait.stdout)
        self.assertNotIn(CORPS_UNIQUE, fait.stdout + fait.stderr)

    def test_usage_incorrect(self):
        ctx = self.fabrique()
        fait = subprocess.run([sys.executable, "-B", str(OUTILS / "context_lab.py"), "inconnue"], capture_output=True, text=True, env=ctx.env(),
                              cwd=str(ctx.tmp))
        self.assertEqual(fait.returncode, 2)

    def test_aucun_chemin_de_l_ancien_dossier_ni_des_originaux_dans_le_texte_de_l_outil(self):
        texte = (OUTILS / "context_lab.py").read_text(encoding="utf-8")
        self.assertNotIn(ANCIEN_DOSSIER, texte)


if __name__ == "__main__":
    unittest.main()
