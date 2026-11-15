"""Reproduction du constat L2 sur context_lab (audit-kraken/lots/L2-L4.md, partie L2, haute) : le nom de fichier d'une note de contexte n'est pas
soumis à la garde des noms (seul le texte de la note l'est), alors que ce nom est exposé par list_books et read_passage (champ `file`).

Test de l'audit #629, groupe O4, attendu vert. Fausse liste de noms (fixture), aucune valeur réelle.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures_context import AUJOURDHUI, IDENTIFIANT, NOM_SENSIBLE, Contexte, note  # noqa: E402


class ChasseL2NomFichier(unittest.TestCase):
    def test_L2_02_nom_de_fichier_soumis_a_la_garde(self):
        import context_lab
        ctx = Contexte(notes={f"2026-09-05-{NOM_SENSIBLE.lower()}.md": note(title="Organisation neutre", date="2026-09-05")})
        self.addCleanup(ctx.close)
        garde = context_lab.Guard(ctx.env(), None, [IDENTIFIANT], list_path=ctx.liste)
        self.assertFalse(garde.unavailable)
        lignes = context_lab.survey(ctx.notes, AUJOURDHUI, garde)
        self.assertEqual(len(lignes), 1)
        self.assertIsNotNone(lignes[0]["problem"], "le nom du fichier porte un nom de la liste et la garde ne l'a pas vu")


MARQUEUR = "(file name hidden)"
DEUX_MOTS = "Zorb Quillan"                  # nom fictif de deux mots
ACCENTUE = "Éléonore Quivrin"               # nom fictif accentué


def contexte_avec_liste(noms, fichiers):
    """Un faux contexte dont la liste de noms porte `noms`, avec une note valide par nom de fichier de `fichiers`."""
    ctx = Contexte(notes={f: note(title="Organisation neutre", date="2026-09-05") for f in fichiers})
    ctx.liste.write_text("".join(f"{n}\n" for n in noms), encoding="utf-8")
    return ctx


class ChasseL2NomTransformeEnSlug(unittest.TestCase):
    """Revue Opus du commit f8cb0ee4 : la garde du nom voit aussi un nom transformé en slug (tirets, soulignés, accents retirés, casse)."""

    def probleme(self, noms, fichier):
        import context_lab
        ctx = contexte_avec_liste(noms, [fichier])
        self.addCleanup(ctx.close)
        garde = context_lab.Guard(ctx.env(), None, [IDENTIFIANT], list_path=ctx.liste)
        return garde.name_problem(fichier)

    def test_nom_de_deux_mots_en_slug_a_tirets(self):
        self.assertEqual(self.probleme([DEUX_MOTS], "2026-09-05-zorb-quillan.md"), "sensitive name in file name")

    def test_nom_de_deux_mots_avec_soulignes_ou_majuscules(self):
        for fichier in ("2026-09-05-zorb_quillan.md", "2026-09-05-ZORB-QUILLAN.md", "2026-09-05-Zorb_Quillan-point.md"):
            with self.subTest(fichier=fichier):
                self.assertIsNotNone(self.probleme([DEUX_MOTS], fichier))

    def test_nom_accentue_en_slug_sans_accents(self):
        self.assertEqual(self.probleme([ACCENTUE], "2026-09-05-eleonore-quivrin.md"), "sensitive name in file name")

    def test_nom_accentue_garde_ses_accents_dans_le_fichier(self):
        self.assertIsNotNone(self.probleme([ACCENTUE], "2026-09-05-Éléonore-Quivrin.md"))

    def test_nom_sans_accent_dans_la_liste_et_accentue_dans_le_fichier(self):
        self.assertIsNotNone(self.probleme(["Eleonore Quivrin"], "2026-09-05-éléonore-quivrin.md"))

    def test_un_seul_des_deux_mots_ne_declenche_rien(self):
        for fichier in ("2026-09-05-zorb.md", "2026-09-05-quillan-autre.md"):
            with self.subTest(fichier=fichier):
                self.assertIsNone(self.probleme([DEUX_MOTS], fichier))

    def test_nom_neutre_reste_accepte(self):
        self.assertIsNone(self.probleme([DEUX_MOTS, ACCENTUE], "2026-09-05-organisation-neutre.md"))

    def test_nom_colle_a_des_lettres_ne_correspond_pas(self):
        self.assertIsNone(self.probleme([DEUX_MOTS], "2026-09-05-xzorb-quillanx.md"))

    def test_add_refuse_un_titre_dont_le_slug_porte_le_nom(self):
        ctx = contexte_avec_liste([DEUX_MOTS], [])
        self.addCleanup(ctx.close)
        code, sortie, erreur = ctx.lancer(["add"], stdin=note(title="Zorb-Quillan", date="2026-09-05", body="Rien de sensible.\n"))
        self.assertEqual(code, 5, erreur)
        self.assertIn("in file name", erreur)
        self.assertEqual(list(ctx.notes.iterdir()), [])


class ChasseL2NomMasque(unittest.TestCase):
    """Revue Opus du commit f8cb0ee4 : le nom de fichier d'une note que la garde refuse ne s'affiche jamais."""

    def test_check_ne_montre_pas_le_nom_d_une_note_a_nom_sensible(self):
        ctx = contexte_avec_liste([DEUX_MOTS], ["2026-09-05-zorb-quillan.md", "2026-09-05-organisation-neutre.md"])
        self.addCleanup(ctx.close)
        code, sortie, erreur = ctx.lancer(["check"])
        self.assertEqual(code, 1, erreur)
        self.assertNotIn("zorb", (sortie + erreur).lower())
        self.assertNotIn("quillan", (sortie + erreur).lower())
        self.assertIn(MARQUEUR, sortie)
        self.assertIn("invalid: sensitive name in file name", sortie)
        self.assertIn("2026-09-05-organisation-neutre.md", sortie)         # une note saine garde son nom
        self.assertIn("2 notes, 0 stale, 1 invalid", sortie)

    def test_en_tete_invalide_le_nom_est_quand_meme_controle_et_masque(self):
        ctx = Contexte(notes={"2026-09-05-zorb-quillan.md": note(title="Sans source", date="2026-09-05", sans=("source",))})
        ctx.liste.write_text(f"{DEUX_MOTS}\n", encoding="utf-8")
        self.addCleanup(ctx.close)
        import context_lab
        garde = context_lab.Guard(ctx.env(), None, [IDENTIFIANT], list_path=ctx.liste)
        lignes = context_lab.survey(ctx.notes, AUJOURDHUI, garde)
        self.assertEqual(lignes[0]["state"], "invalid: header field missing: source")      # l'état dit toujours la première raison
        code, sortie, erreur = ctx.lancer(["check"])
        self.assertEqual(code, 1)
        self.assertNotIn("zorb", sortie.lower())
        self.assertIn(MARQUEUR, sortie)

    def test_nom_sensible_et_corps_sensible_le_nom_est_masque(self):
        ctx = Contexte(notes={"2026-09-05-zorb-quillan.md": note(title="Autre titre", date="2026-09-05", body=f"{DEUX_MOTS} ici\n")})
        ctx.liste.write_text(f"{DEUX_MOTS}\n", encoding="utf-8")
        self.addCleanup(ctx.close)
        code, sortie, erreur = ctx.lancer(["check"])
        self.assertEqual(code, 1)
        self.assertNotIn("zorb", (sortie + erreur).lower())
        self.assertIn("sensitive name in line", sortie)

    def test_nom_accentue_masque(self):
        ctx = contexte_avec_liste([ACCENTUE], ["2026-09-05-eleonore-quivrin.md"])
        self.addCleanup(ctx.close)
        code, sortie, erreur = ctx.lancer(["check"])
        self.assertEqual(code, 1)
        self.assertNotIn("eleonore", (sortie + erreur).lower())
        self.assertIn(MARQUEUR, sortie)


class ListeNomMasque(unittest.TestCase):
    """Lot 5, question 2c (option a) : `list` ne montre pas un nom de fichier que la garde refuse ; un nom admis reste affiché."""

    def test_list_masque_le_nom_refuse_et_garde_le_nom_admis(self):
        ctx = contexte_avec_liste([DEUX_MOTS], ["2026-09-05-zorb-quillan.md", "2026-09-05-organisation-neutre.md"])
        self.addCleanup(ctx.close)
        code, sortie, erreur = ctx.lancer(["list"])
        self.assertEqual(code, 0, erreur)
        self.assertNotIn("zorb", (sortie + erreur).lower())
        self.assertNotIn("quillan", (sortie + erreur).lower())
        self.assertIn(MARQUEUR, sortie)
        self.assertIn("2026-09-05-organisation-neutre.md", sortie)
        self.assertNotIn("invalid:", sortie)            # list ne fait toujours pas le contrôle de confidentialité
        self.assertIn("2 notes, 0 stale, 0 invalid", sortie)

    def test_list_masque_aussi_un_nom_accentue_ou_a_soulignes(self):
        ctx = contexte_avec_liste([DEUX_MOTS, ACCENTUE], ["2026-09-05-Zorb_Quillan.md", "2026-09-05-eleonore-quivrin.md"])
        self.addCleanup(ctx.close)
        code, sortie, erreur = ctx.lancer(["list"])
        self.assertEqual(code, 0, erreur)
        for mot in ("zorb", "quillan", "eleonore", "quivrin"):
            self.assertNotIn(mot, (sortie + erreur).lower())
        self.assertEqual(sortie.count(MARQUEUR), 2)

    def test_list_sans_nom_refuse_ne_masque_rien(self):
        ctx = contexte_avec_liste([DEUX_MOTS], ["2026-09-05-organisation-neutre.md"])
        self.addCleanup(ctx.close)
        code, sortie, _ = ctx.lancer(["list"])
        self.assertEqual(code, 0)
        self.assertNotIn(MARQUEUR, sortie)
        self.assertIn("2026-09-05-organisation-neutre.md", sortie)


class ListeIndisponibleNomsMasques(unittest.TestCase):
    """R-20261108-03, question 3 (a) : liste des noms absente ou vide (garde indisponible), `check` et `list` masquent TOUS les noms de
    fichier des notes ; le contenu, les états et les codes de sortie ne changent pas."""
    NOMS = ["2026-09-05-organisation-neutre.md", "2026-09-06-autre-note.md"]

    def contexte(self, vide):
        ctx = Contexte(notes={f: note(title="Organisation neutre", date="2026-09-05") for f in self.NOMS}, avec_liste=False)
        self.addCleanup(ctx.close)
        if vide:
            ctx.liste.write_text("# rien\n", encoding="utf-8")
        return ctx

    def verifie(self, vide, commande, code_attendu):
        ctx = self.contexte(vide)
        code, sortie, erreur = ctx.lancer([commande])
        self.assertEqual(code, code_attendu, erreur)
        for nom in self.NOMS:
            self.assertNotIn(nom, sortie + erreur)
        self.assertEqual(sortie.count(MARQUEUR), 2)
        self.assertIn("2 notes, 0 stale, 0 invalid", sortie)
        self.assertIn("sensitive-names list unavailable: confidentiality not checked", erreur)    # list avertit comme check

    def test_list_liste_absente(self):
        self.verifie(False, "list", 0)

    def test_list_liste_vide(self):
        self.verifie(True, "list", 0)

    def test_check_liste_absente(self):
        self.verifie(False, "check", 1)

    def test_check_liste_vide(self):
        self.verifie(True, "check", 1)


if __name__ == "__main__":
    unittest.main()
