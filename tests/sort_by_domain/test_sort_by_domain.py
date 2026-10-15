"""
Tests de la ventilation par domaine (tools/sort_by_domain.py) sur un faux MAPPING et de faux fichiers Markdown.

    python3 -m unittest discover -s tests/sort_by_domain -v

Le MAPPING est remplacé le temps du test ; les fichiers sont inventés, dans un dossier temporaire. Jamais
Bibliotheque-MD ni Bibliotheque-Lab. Le dernier groupe de tests lit seulement le texte source de mapping_lab.py
(sans lire un seul livre) pour vérifier la cohérence de MAPPING : codes connus, clés uniques, noms de
fichiers copiés uniques. Ce groupe vaut pour la table privée comme pour la table neutre de l'édition ; ce qui tient
au contenu de la table privée est dans test_mapping_prive.py (absent de l'édition).
"""
import ast
import collections
import contextlib
import io
import shutil
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import sort_by_domain as ventiler  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = self.tmp / "md"
        self.dst = self.tmp / "collections"
        self.src.mkdir()

    def livre(self, relatif: str, texte: str = "contenu inventé") -> Path:
        chemin = self.src / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")
        return chemin

    def lancer(self, mapping: dict, *arguments) -> str:
        arguments = arguments or (str(self.src), str(self.dst))
        sortie = io.StringIO()
        with mock.patch.object(ventiler, "MAPPING", mapping), \
                mock.patch.object(sys, "argv", ["sort_by_domain.py", *arguments]), \
                contextlib.redirect_stdout(sortie):
            ventiler.main()
        return sortie.getvalue()

    def copies(self) -> dict[str, list[str]]:
        return {d.name: sorted(f.name for f in d.glob("*.md")) for d in sorted(self.dst.iterdir()) if d.is_dir()}


class Ventilation(Base):
    def test_repartition_par_domaine_et_multi_domaines(self):
        for nom in ("rayon/flux.md", "rayon/produit.md", "rayon/orga.md", "rayon/atelier.md", "rayon/code.md"):
            self.livre(nom)
        sortie = self.lancer({"rayon/flux.md": "D", "rayon/produit.md": "P", "rayon/orga.md": "O",
                              "rayon/atelier.md": "F", "rayon/code.md": "TD"})
        self.assertEqual(self.copies(), {"flow": ["code.md", "flux.md"], "produit": ["produit.md"],
                                         "organisation": ["orga.md"], "facilitation": ["atelier.md"],
                                         "tech": ["code.md"]})
        for ligne in ("produit : 1", "flow : 2", "organisation : 1", "facilitation : 1", "tech : 1"):
            self.assertIn(ligne, sortie)

    def test_copie_sans_deplacer_ni_modifier_les_originaux(self):
        original = self.livre("rayon/un.md", "texte exact")
        self.lancer({"rayon/un.md": "PD"})
        self.assertEqual(original.read_text(encoding="utf-8"), "texte exact")
        for domaine in ("produit", "flow"):
            self.assertEqual((self.dst / domaine / "un.md").read_text(encoding="utf-8"), "texte exact")

    def test_doublons_ecartes_non_copies(self):
        self.livre("rayon/garde.md")
        self.livre("rayon/doublon.md")
        sortie = self.lancer({"rayon/garde.md": "P", "rayon/doublon.md": ""})
        self.assertEqual(self.copies(), {"produit": ["garde.md"]})
        self.assertIn("Écartés (doublons, à identifier) : 1", sortie)
        self.assertIn("- rayon/doublon.md", sortie)
        self.assertNotIn("Introuvables", sortie)   # un doublon présent n'est pas « introuvable »

    def test_introuvables_signales_et_le_reste_est_copie(self):
        self.livre("rayon/present.md")
        sortie = self.lancer({"rayon/present.md": "P", "rayon/absent.md": "O", "rayon/absent-ecarte.md": ""})
        self.assertIn("Introuvables (nom modifié ?) : 2", sortie)
        self.assertIn("- rayon/absent.md", sortie)
        self.assertEqual(self.copies(), {"produit": ["present.md"]})

    def test_non_classes_signales(self):
        self.livre("rayon/classe.md")
        self.livre("rayon/nouveau.md")
        self.livre("rayon/_rapport_conversion.md")   # fichier de service : jamais signalé
        self.livre("rayon/notes.txt")                # pas du Markdown : ignoré
        sortie = self.lancer({"rayon/classe.md": "P"})
        self.assertIn("Présents mais non classés (nouveaux livres ?) : 1", sortie)
        self.assertIn("- rayon/nouveau.md", sortie)
        self.assertNotIn("_rapport", sortie)
        self.assertNotIn("notes.txt", sortie)

    def test_noms_accentues_nfd_et_nfc(self):
        nfd = unicodedata.normalize("NFD", "rayon/Hôpital apprenant.md")   # comme macOS écrit les noms
        self.livre(nfd)
        sortie = self.lancer({unicodedata.normalize("NFC", "rayon/Hôpital apprenant.md"): "O"})
        self.assertNotIn("Introuvables", sortie)
        self.assertNotIn("non classés", sortie)
        self.assertEqual(sum(len(v) for v in self.copies().values()), 1)

    def test_relance_idempotente(self):
        self.livre("rayon/un.md")
        self.lancer({"rayon/un.md": "PD"})
        self.lancer({"rayon/un.md": "PD"})
        self.assertEqual(self.copies(), {"flow": ["un.md"], "produit": ["un.md"]})

    def test_dossier_source_absent_et_arguments(self):
        with self.assertRaises(SystemExit):
            self.lancer({}, str(self.tmp / "absent"), str(self.dst))
        with self.assertRaises(SystemExit) as erreur:
            self.lancer({}, "un-seul")
        self.assertEqual(erreur.exception.code, 1)

    def test_mapping_vide_ne_cree_aucun_dossier(self):
        self.livre("rayon/un.md")
        sortie = self.lancer({})
        self.assertFalse(self.dst.exists())
        self.assertIn("non classés", sortie)

    def test_code_inconnu_arrete_avant_toute_copie(self):
        self.livre("rayon/un.md")
        self.livre("rayon/deux.md")
        with self.assertRaises(SystemExit) as erreur:
            self.lancer({"rayon/un.md": "P", "rayon/deux.md": "DX"})
        message = str(erreur.exception.code)
        self.assertIn("MAPPING invalide : 1 code(s) de domaine inconnu(s)", message)
        self.assertIn("codes valides : P, D, O, F, T", message)
        self.assertIn("- rayon/deux.md : code « X »", message)
        self.assertIn("Rien n'a été copié", message)
        self.assertFalse(self.dst.exists())     # même le livre valide, classé avant, n'a pas été copié

    def test_tous_les_codes_inconnus_listes_meme_pour_un_fichier_absent(self):
        self.livre("rayon/un.md")
        with self.assertRaises(SystemExit) as erreur:
            self.lancer({"rayon/un.md": "P", "rayon/absent.md": "Z", "rayon/autre.md": "pq"})
        message = str(erreur.exception.code)
        self.assertIn("3 code(s)", message)
        for attendu in ("absent.md : code « Z »", "autre.md : code « p »", "autre.md : code « q »"):
            self.assertIn(attendu, message)
        self.assertFalse(self.dst.exists())

    def test_meme_nom_dans_deux_dossiers_signale_et_rien_n_est_ecrase(self):
        self.livre("a/titre.md", "premier")
        self.livre("b/titre.md", "second")
        self.livre("b/autre.md", "autre livre")
        sortie = self.lancer({"a/titre.md": "P", "b/titre.md": "P", "b/autre.md": "P"})
        self.assertEqual((self.dst / "produit" / "titre.md").read_text(encoding="utf-8"), "premier")
        self.assertEqual(self.copies(), {"produit": ["autre.md", "titre.md"]})
        self.assertIn("Noms de fichiers en double, non copiés (le premier est gardé) : 1", sortie)
        self.assertIn("- b/titre.md\n    même nom que a/titre.md", sortie)
        self.assertIn("produit : 2", sortie)    # compté une fois par livre réellement copié
        self.assertNotIn("non classés", sortie)  # le doublon est classé, pas « nouveau »

    def test_meme_nom_dans_deux_domaines_differents_est_aussi_un_doublon(self):
        """Le serveur de bibliothèque regroupe par nom de fichier : deux livres de même nom dans deux domaines
        seraient pris pour un seul."""
        self.livre("a/titre.md", "premier")
        self.livre("b/titre.md", "second")
        sortie = self.lancer({"a/titre.md": "P", "b/titre.md": "D"})
        self.assertEqual(self.copies(), {"produit": ["titre.md"]})
        self.assertIn("Noms de fichiers en double", sortie)

    def test_doublon_de_nom_a_la_casse_pres(self):
        self.livre("a/Titre.md", "premier")
        self.livre("b/titre.md", "second")
        sortie = self.lancer({"a/Titre.md": "P", "b/titre.md": "P"})
        self.assertEqual(self.copies(), {"produit": ["Titre.md"]})   # sur APFS, un seul des deux survivrait
        self.assertIn("Noms de fichiers en double", sortie)

    def test_un_livre_ecarte_ne_compte_pas_comme_doublon(self):
        self.livre("a/titre.md", "gardé")
        self.livre("b/titre.md", "écarté")
        sortie = self.lancer({"a/titre.md": "P", "b/titre.md": ""})
        self.assertNotIn("en double", sortie)
        self.assertEqual((self.dst / "produit" / "titre.md").read_text(encoding="utf-8"), "gardé")

    def test_relance_apres_doublon_idempotente(self):
        self.livre("a/titre.md", "premier")
        self.livre("b/titre.md", "second")
        for _ in range(2):
            self.lancer({"a/titre.md": "P", "b/titre.md": "P"})
        self.assertEqual((self.dst / "produit" / "titre.md").read_text(encoding="utf-8"), "premier")

    def test_domaine_repete_dans_un_code_copie_une_fois(self):
        self.livre("a/un.md")
        sortie = self.lancer({"a/un.md": "PP"})
        self.assertIn("produit : 1", sortie)


class DossiersRenommes(Base):
    """Les dossiers de la source ont été renommés (« 03 Lean, flux et Kanban/ ») alors que Bibliotheque-MD garde les
    anciens noms (« Lean & Continuous Improvement/ »). La correspondance de MAPPING se fait sur le chemin complet."""

    ANCIEN = "Livres - Ressources/Lean & Continuous Improvement/cfd.md"
    NOUVEAU = "Livres - Ressources/03 Lean, flux et Kanban/cfd.md"

    def test_un_markdown_dans_un_dossier_numerote_n_est_pas_apparie(self):
        self.livre(self.NOUVEAU, "dans le nouveau dossier")
        sortie = self.lancer({self.ANCIEN: "D"})
        self.assertFalse(self.dst.exists())                                         # rien n'est copié
        self.assertIn("Introuvables (nom modifié ?) : 1", sortie)
        self.assertIn(f"- {self.ANCIEN}", sortie)
        self.assertIn("Présents mais non classés (nouveaux livres ?) : 1", sortie)   # signalé, jamais en silence
        self.assertIn(f"- {self.NOUVEAU}", sortie)

    def test_un_doublon_dans_un_dossier_numerote_ne_gene_pas_le_livre_classe(self):
        self.livre(self.ANCIEN, "version classée")
        self.livre(self.NOUVEAU, "doublon du dossier numéroté")
        sortie = self.lancer({self.ANCIEN: "D"})
        self.assertEqual((self.dst / "flow" / "cfd.md").read_text(encoding="utf-8"), "version classée")
        self.assertEqual(self.copies(), {"flow": ["cfd.md"]})
        self.assertNotIn("Introuvables", sortie)
        self.assertIn(f"- {self.NOUVEAU}", sortie)                                  # le doublon est listé comme non classé
        self.assertNotIn("en double", sortie)                                        # pas un doublon de MAPPING

    def test_un_dossier_de_corbeille_hors_de_la_source_ne_gene_pas(self):
        self.livre(self.ANCIEN, "version classée")
        corbeille = self.tmp / "_a_supprimer" / "cfd.md"                             # hors du dossier source
        corbeille.parent.mkdir()
        corbeille.write_text("à supprimer", encoding="utf-8")
        sortie = self.lancer({self.ANCIEN: "D"})
        self.assertNotIn("_a_supprimer", sortie)
        self.assertEqual(self.copies(), {"flow": ["cfd.md"]})


class MappingReel(unittest.TestCase):
    """Cohérence du vrai MAPPING, lu dans le texte source : aucun livre n'est lu."""

    @classmethod
    def setUpClass(cls):
        source = (Path(__file__).resolve().parents[2] / "tools" / "mapping_lab.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        noeud = next(n.value for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "MAPPING")
        prefixe = next(n.value.value for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "R")
        cls.cles = [eval(compile(ast.Expression(k), "mapping", "eval"), {"R": prefixe}) for k in noeud.keys]
        cls.codes = [v.value for v in noeud.values]

    def test_codes_connus_et_sans_repetition(self):
        self.assertTrue(self.cles)
        for cle, codes in zip(self.cles, self.codes):
            self.assertTrue(set(codes) <= set(ventiler.DOMAINS), f"code inconnu : {cle}")
            self.assertEqual(len(set(codes)), len(codes), f"domaine répété : {cle}")

    def test_cles_sous_le_dossier_de_sortie_de_la_conversion(self):
        """convert_books.py --redo-figures ne consulte que les clés dont le premier dossier est celui de la
        conversion (Bibliotheque-MD/Livres - Ressources) : toutes les vraies clés doivent y être."""
        for cle in self.cles:
            self.assertTrue(unicodedata.normalize("NFC", cle).startswith("Livres - Ressources/"), cle)

    def test_les_cibles_de_SOURCES_sont_des_cles_de_mapping_copiees(self):
        import mapping_lab
        for source, cible in mapping_lab.SOURCES.items():
            self.assertIn(unicodedata.normalize("NFC", cible), [unicodedata.normalize("NFC", c) for c in self.cles],
                          f"{source} -> {cible}")
            self.assertTrue(dict(zip(self.cles, self.codes))[cible], f"{cible} est écarté de la ventilation")

    def test_exclusions_avec_raison_et_distinctes_des_sources(self):
        import mapping_lab
        self.assertTrue(mapping_lab.EXCLUSIONS)
        for source, raison in mapping_lab.EXCLUSIONS.items():
            self.assertTrue(raison.strip(), source)
            self.assertNotIn(source, mapping_lab.SOURCES)                        # une source exclue n'est pas aussi reliée

    def test_cles_uniques(self):
        compte = collections.Counter(unicodedata.normalize("NFC", c) for c in self.cles)
        self.assertEqual([c for c, n in compte.items() if n > 1], [])   # une clé répétée écrase l'autre en silence

    def test_noms_de_fichiers_copies_uniques(self):
        noms = collections.Counter(unicodedata.normalize("NFC", c).rsplit("/", 1)[-1]
                                   for c, codes in zip(self.cles, self.codes) if codes)
        self.assertEqual([n for n, k in noms.items() if k > 1], [])

    def test_domaines_documentes(self):
        self.assertEqual(set(ventiler.DOMAINS.values()), {"produit", "flow", "organisation", "facilitation", "tech"})


if __name__ == "__main__":
    unittest.main()
