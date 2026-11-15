"""
R-20261112-24 (A-75 de l'audit #629) : la lecture de la surcouche de l'organisation refuse un texte qui cite un nom de la liste ou de
l'extrait des équipes, sans jamais afficher ni journaliser ce nom. Liste et extrait FACTICES (variable de test
PMZILLA_LAB_SENSITIVE_NAMES, extrait voisin de la liste). Noms et textes inventés. Suite : tests/story_quality.

Remplace : rien. Retrait : permanent (propriété de confidentialité des messages de refus).
"""
import unittest

from aide_story_quality import NOM_FICTIF, RESUME, SURCOUCHE, Espace
import sensitive_names  # noqa: E402  (TOOLS est ajouté au chemin par l'aide)

NOM_EXTRAIT = "Quillonbrook"    # seulement dans l'extrait
EXTRAIT = f"referential_teams:\n  - name: {NOM_EXTRAIT}\ncatalogue_teams:\n  - name: Marmotte Atelier\n"


class RefusSansLeNom(Espace):
    def setUp(self):
        super().setUp()
        (self.noms.parent / sensitive_names.NOM_EXTRAIT).write_text(EXTRAIT, encoding="utf-8")

    def verifier(self, nom, texte_surcouche):
        self.ecrire(texte_surcouche)
        code, sortie, erreur = self.lancer("grid")
        self.assertEqual(code, 3)                                              # (a) refus
        self.assertIn("surcouche de l'organisation", erreur)
        self.assertNotIn(nom.lower(), (sortie + erreur).lower())               # (b) jamais le nom
        for fichier in (p for p in self.temp_fichiers() if p != self.fichier):
            self.assertNotIn(nom.lower(), fichier.read_text(encoding="utf-8", errors="ignore").lower(), fichier.name)

    def temp_fichiers(self):
        from pathlib import Path
        a_moi = {self.noms, self.noms.parent / sensitive_names.NOM_EXTRAIT, self.socle}
        return [p for p in Path(self.temp.name).rglob("*") if p.is_file() and p not in a_moi]

    def test_un_nom_de_l_extrait_dans_le_resume_est_refuse_sans_etre_affiche(self):
        self.verifier(NOM_EXTRAIT, SURCOUCHE.replace(RESUME, f"Produit de l'équipe {NOM_EXTRAIT}"))

    def test_un_nom_de_l_extrait_en_majuscules_dans_une_definition_est_refuse_sans_etre_affiche(self):
        self.verifier(NOM_EXTRAIT, SURCOUCHE.replace("La story nomme un rôle.", f"La story nomme {NOM_EXTRAIT.upper()}."))

    def test_un_nom_de_la_liste_est_refuse_sans_etre_affiche(self):
        self.verifier(NOM_FICTIF, SURCOUCHE.replace(RESUME, f"Produit de {NOM_FICTIF}"))

    def test_un_nom_de_l_extrait_comme_cle_est_refuse_sans_etre_affiche(self):
        self.verifier(NOM_EXTRAIT, SURCOUCHE + f"autre:\n  {NOM_EXTRAIT}: valeur\n")


if __name__ == "__main__":
    unittest.main()
