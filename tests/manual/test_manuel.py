"""tools/manual.py : le manuel généré, sur un faux dépôt (change user-manual, design D13).

Aucun script du faux dépôt n'est lancé ni importé (sentinelle) ; seul le générateur tourne. Sans réseau, sans base, sans Trousseau.

    uv run python -m unittest discover -s tests/manual
"""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(RACINE / "tests" / "settings_deny"))
import manual  # noqa: E402
import fixtures  # noqa: E402

GENERATEUR = RACINE / "tools" / "manual.py"


def entree(texte, identifiant):
    """Le bloc `### identifiant` jusqu'au prochain titre `###` ou `##`."""
    debut = texte.index(f"\n### {identifiant}\n")
    fin = re.search(r"\n#{2,3} ", texte[debut + 5:])
    return texte[debut:debut + 5 + fin.start()] if fin else texte[debut:]


def section(texte, titre):
    debut = texte.index(f"\n## {titre}\n")
    fin = texte.find("\n## ", debut + 4)
    return texte[debut:] if fin < 0 else texte[debut:fin]


def lancer(*arguments):
    return subprocess.run([sys.executable, str(GENERATEUR), *arguments], capture_output=True, text=True)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dossier = Path(tempfile.mkdtemp(prefix="manuel-test-"))
        cls.sentinelle = cls.dossier / "SENTINELLE"
        cls.depot = cls.dossier / "depot"
        fixtures.construire_depot(cls.depot, cls.sentinelle)
        cls.texte = manual.construire(cls.depot, table=fixtures.TABLE)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dossier, True)


class Perimetre(Base):
    def test_module_de_bibliotheque_ignore(self):
        self.assertIn("### tools/outil_simple.py", self.texte)
        self.assertNotIn("bibliotheque_lib", self.texte)

    def test_hooks_et_modele_planifie_nommes_pas_decrits(self):
        self.assertNotIn("### tools/hooks", self.texte)
        self.assertNotIn("com.exemple.planifie.plist", self.texte)
        fin = section(self.texte, "Hors du manuel")
        self.assertIn("tools/hooks", fin)
        self.assertIn("tools/com.pmzilla.*.plist", fin)
        self.assertTrue(self.texte.rstrip().endswith(fin.strip()), "« Hors du manuel » est la dernière section")

    def test_commande_placee_dans_sa_zone_et_ordre_des_sections(self):
        titres = re.findall(r"^## (.+)$", self.texte, re.M)
        self.assertEqual(titres, ["Flux et Jira", "Base", "Sauvegardes", "Diagnostic (doctor)", "Tests et contrôles",
                                  "Hors du manuel"])
        self.assertIn("### /demo", section(self.texte, "Diagnostic (doctor)"))
        self.assertIn("### tests/run_all.sh", section(self.texte, "Tests et contrôles"))

    def test_ordre_dans_une_section(self):
        zone = section(self.texte, "Flux et Jira")
        self.assertLess(zone.index("### tools/outil_simple.py"), zone.index("### tools/outil_sous.py"))

    def test_commande_hors_table_en_fin_de_manuel_sans_echec(self):
        texte = manual.construire(self.depot, table={})
        self.assertIn("## Non classées", texte)
        self.assertIn("### tools/outil_simple.py", section(texte, "Non classées"))

    def test_titre_et_ligne_de_generation(self):
        self.assertTrue(self.texte.startswith("# Manuel d'utilisation de PMZilla Lab\n"))
        self.assertIn("Généré par uv run tools/manual.py : ne pas modifier à la main.", self.texte)

    def test_commandes_trouvees_pour_le_controle_de_table(self):
        self.assertEqual(manual.commandes_trouvees(self.depot), set(fixtures.TABLE))


class Planification(Base):
    def test_enveloppeur_nomme_par_un_modele(self):
        self.assertIn("lancée aussi par une tâche planifiée", entree(self.texte, "tools/planifie.sh"))

    def test_autre_script_sans_la_note(self):
        self.assertNotIn("lancée aussi par une tâche planifiée", entree(self.texte, "tools/lanceur.sh"))


class SourcesJamaisLancees(Base):
    def test_sentinelle_absente(self):
        self.assertFalse(self.sentinelle.exists())

    def test_corps_de_commande_jamais_lu(self):
        self.assertNotIn("MARQUEUR-CORPS-SECRET", self.texte)


class ContenuDesEntrees(Base):
    def test_role_et_etiquettes(self):
        bloc = entree(self.texte, "tools/outil_simple.py")
        self.assertIn("**Rôle** : Outil simple de démonstration.", bloc)
        self.assertIn("**Qui lance** : Terminal ou Claude Code", bloc)
        self.assertLess(bloc.index("**Rôle**"), bloc.index("**Qui lance**"))
        self.assertLess(bloc.index("**Qui lance**"), bloc.index("**Paramètres**"))
        self.assertLess(bloc.index("**Paramètres**"), bloc.index("**Codes de sortie**"))
        self.assertLess(bloc.index("**Codes de sortie**"), bloc.index("**Exemple**"))

    def test_table_des_parametres(self):
        bloc = entree(self.texte, "tools/outil_simple.py")
        self.assertIn("| Paramètre | Valeurs | Défaut | Obligatoire | Aide |", bloc)
        self.assertIn("| `--mode` | json, text | text | non | Format de sortie |", bloc)
        self.assertIn("| `--verbose` | drapeau | - | non | Bavard |", bloc)
        self.assertIn("| `fichier` | - | - | non | Fichier à lire |", bloc)

    def test_argument_cache_sans_trace(self):
        self.assertNotIn("--secret", self.texte)
        self.assertNotIn("--cache-aussi", self.texte)

    def test_description_du_parseur_ne_remplace_pas_la_docstring(self):
        self.assertNotIn("Description du parseur simple", entree(self.texte, "tools/outil_simple.py"))

    def test_role_non_documente_sans_docstring_ni_description(self):
        self.assertIn("**Rôle** : rôle non documenté", entree(self.texte, "tools/outil_genere.py"))

    def test_sous_commandes(self):
        bloc = entree(self.texte, "tools/outil_sous.py")
        self.assertIn("**Sous-commandes**", bloc)
        for nom, aide in (("test", "Contacte le service distant"), ("local", "Calcul local"), ("calcul", "Calcul avec source")):
            self.assertRegex(bloc, rf"#### {nom}\n+{aide}")
        self.assertIn("| `--delai` | - | 5 | non | Délai en secondes |", bloc)

    def test_sous_commandes_imbriquees_un_niveau(self):
        bloc = entree(self.texte, "tools/outil_sous.py")
        self.assertIn("sous-commandes imbriquées", bloc)
        ligne = [l for l in bloc.splitlines() if "sous-commandes imbriquées" in l][0]
        self.assertIn("un", ligne)
        self.assertIn("deux", ligne)
        self.assertNotIn("#### un", bloc)

    def test_choix_et_defaut(self):
        bloc = entree(self.texte, "tools/outil_sous.py")
        self.assertIn("| `--source` | fichier, db | fichier | non | Source des données |", bloc)

    def test_valeurs_non_litterales(self):
        bloc = entree(self.texte, "tools/outil_sous.py")
        self.assertIn("| `--calculee` | valeur calculée | - | non | Choix calculés |", bloc)
        self.assertIn("| `--aide-calculee` | - | valeur calculée | non | valeur calculée |", bloc)

    def test_groupe_exclusif(self):
        bloc = entree(self.texte, "tools/outil_sous.py")
        self.assertRegex(bloc, r"un seul parmi[^\n]*`--json`[^\n]*`--csv`")

    def test_groupe_d_arguments_rendu_avec_son_parseur(self):
        bloc = entree(self.texte, "tools/outil_sous.py")
        self.assertIn("`--depuis`", bloc)
        self.assertNotIn("Filtres", bloc)

    def test_aide_partagee_dans_le_meme_fichier(self):
        bloc = entree(self.texte, "tools/outil_aide.py")
        self.assertIn("| `--language` | fr, en | fr | non | Langue des messages |", bloc)
        self.assertIn("options ajoutées par une fonction partagée : valeur calculée", bloc)

    def test_script_sans_parseur(self):
        bloc = entree(self.texte, "tools/outil_sans_parseur.py")
        self.assertIn("**Rôle** : Outil sans argparse, lu dans sys.argv.", bloc)
        self.assertIn("uv run tools/outil_sans_parseur.py a.csv b.csv", bloc)
        self.assertIn("paramètres : voir l'usage", bloc)
        self.assertNotIn("Détails ignorés", bloc)

    def test_en_tete_shell(self):
        bloc = entree(self.texte, "tools/lanceur.sh")
        self.assertIn("**Rôle** : PMZilla Lab : lanceur de démonstration. Deuxième ligne du rôle.", bloc)
        self.assertIn("`bash tools/lanceur.sh` : lance tout", bloc)
        self.assertIn("`bash tools/lanceur.sh --seulement` : seulement la moitié", bloc)
        self.assertIn("0 succès", bloc)
        self.assertIn("2 erreur d'usage", bloc)

    def test_shell_sans_en_tete(self):
        bloc = entree(self.texte, "tools/sans_entete.sh")
        self.assertIn("rôle non documenté", bloc)
        self.assertIn("codes de sortie non documentés", bloc)

    def test_commande_slash(self):
        bloc = entree(self.texte, "/demo")
        self.assertIn("**Rôle** : Commande de démonstration pour le manuel", bloc)
        self.assertIn("**Qui lance** : Claude Code seulement", bloc)
        self.assertIn("**Argument** : [fr|en]", bloc)
        self.assertIn("**Modèle** : sonnet", bloc)
        self.assertIn("/demo [fr|en]", bloc)

    def test_run_all_lu_comme_un_script_shell(self):
        bloc = entree(self.texte, "tests/run_all.sh")
        self.assertIn("**Rôle** : Lance toutes les suites de démonstration.", bloc)
        self.assertIn("`bash tests/run_all.sh -v` : en plus, la sortie complète", bloc)


class QuiLance(Base):
    def test_sous_commande_refusee_et_autre_non(self):
        bloc = entree(self.texte, "tools/outil_sous.py")
        sous_test = bloc.split("#### test", 1)[1].split("####", 1)[0]
        sous_local = bloc.split("#### local", 1)[1].split("####", 1)[0]
        self.assertIn("**Qui lance** : Terminal seulement", sous_test)
        self.assertNotIn("**Qui lance**", sous_local, "le libellé de la sous-commande n'est écrit que s'il diffère du script")
        self.assertIn("**Qui lance** : Terminal ou Claude Code", bloc.split("**Sous-commandes**", 1)[0])

    def test_regle_a_option_seule(self):
        bloc = entree(self.texte, "tools/outil_sous.py")
        sous_calcul = bloc.split("#### calcul", 1)[1].split("####", 1)[0]
        self.assertIn("**Qui lance** : Terminal seulement avec `--source db`", sous_calcul)

    def test_script_shell_refuse(self):
        self.assertIn("**Qui lance** : Terminal seulement", entree(self.texte, "tools/lanceur.sh"))

    def test_regle_d_un_ancien_nom_ignoree(self):
        self.assertNotIn("ancien_nom", self.texte)

    def test_reglages_non_modifies(self):
        chemin = self.depot / ".claude" / "settings.json"
        avant = chemin.read_text(encoding="utf-8")
        manual.construire(self.depot, table=fixtures.TABLE)
        self.assertEqual(chemin.read_text(encoding="utf-8"), avant)

    def test_meme_verdict_que_le_test_des_garde_fous(self):
        import manual_deny
        import test_settings_deny as garde
        formes = []
        for lanceur in ("uv run", "python", "python3", "python3 -I", "uv run python"):
            for chemin in garde.CHEMINS:
                for suite in ("test", "collect --scope A", "export", "check --dormants x.csv", "", "calcul --source db"):
                    formes.append(f"{lanceur} {chemin.format(s='history_jira.py')} {suite}".rstrip())
        deny = garde.json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]["deny"]
        regles = [d[len("Bash("):-1] for d in deny if d.startswith("Bash(")]
        motifs = [garde.motif_en_regex(r) for r in regles]
        for forme in formes:
            attendu = any(m.fullmatch(forme) for m in motifs)
            self.assertEqual(manual_deny.interdite(regles, forme), attendu, forme)


class MetavarEtDerogations(Base):
    def sous_bloc(self, texte, sous):
        return texte.split(f"#### {sous}", 1)[1].split("####", 1)[0]

    def test_choix_ecrits_en_metavar(self):
        bloc = self.sous_bloc(entree(self.texte, "tools/outil_sous.py"), "origine")
        self.assertIn("| `--source` | csv, db | csv | non | Origine des données |", bloc)

    def test_regle_a_option_lue_dans_le_metavar(self):
        bloc = self.sous_bloc(entree(self.texte, "tools/outil_sous.py"), "origine")
        self.assertIn("**Qui lance** : Terminal seulement avec `--source db`", bloc)

    def test_derogation_du_script_vaut_pour_toutes_ses_sous_commandes(self):
        texte = manual.construire(self.depot, table=fixtures.TABLE, derogations={("outil_sous.py", None): "raison"})
        bloc = entree(texte, "tools/outil_sous.py")
        self.assertIn("**Qui lance** : Terminal seulement", bloc.split("**Sous-commandes**", 1)[0])
        self.assertNotIn("Claude Code", bloc)
        self.assertNotIn("avec `", bloc)

    def test_derogation_d_une_sous_commande(self):
        texte = manual.construire(self.depot, table=fixtures.TABLE, derogations={("outil_sous.py", "local"): "raison"})
        bloc = entree(texte, "tools/outil_sous.py")
        self.assertIn("**Qui lance** : Terminal ou Claude Code", bloc.split("**Sous-commandes**", 1)[0])
        self.assertIn("**Qui lance** : Terminal seulement", self.sous_bloc(bloc, "local"))

    def test_derogation_d_un_script_shell(self):
        texte = manual.construire(self.depot, table=fixtures.TABLE, derogations={("planifie.sh", None): "raison"})
        self.assertIn("**Qui lance** : Terminal seulement (lancée aussi par une tâche planifiée)", entree(texte, "tools/planifie.sh"))

    def test_sans_derogation_le_libelle_vient_des_regles_deny(self):
        texte = manual.construire(self.depot, table=fixtures.TABLE, derogations={})
        self.assertIn("**Qui lance** : Terminal ou Claude Code", entree(texte, "tools/planifie.sh"))


class CodesDeSortie(Base):
    def test_ligne_codes(self):
        bloc = entree(self.texte, "tools/outil_simple.py")
        for code in ("0 succès", "1 échec", "2 erreur d'usage"):
            self.assertIn(code, bloc)

    def test_section_codes_de_sortie(self):
        bloc = entree(self.texte, "tools/outil_sous.py")
        self.assertIn("0  tout va bien", bloc)
        self.assertIn("3  autre cas", bloc)
        self.assertNotIn("Texte suivant la section", bloc)

    def test_codes_absents(self):
        self.assertIn("codes de sortie non documentés", entree(self.texte, "tools/outil_genere.py"))

    def test_absence_de_codes_ne_fait_pas_echouer(self):
        resultat = lancer("--root", str(self.depot))
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertIn("codes de sortie non documentés", resultat.stdout)


class Exemples(Base):
    def exemple(self, identifiant):
        bloc = entree(self.texte, identifiant)
        correspondance = re.search(r"\*\*Exemple\*\*\n+```[a-z]*\n(.*?)\n```", bloc, re.S)
        return correspondance.group(1) if correspondance else None

    def test_exemple_pris_dans_la_docstring(self):
        self.assertEqual(self.exemple("tools/outil_simple.py"), "uv run tools/outil_simple.py --mode json")

    def test_exemple_pris_dans_l_en_tete_shell(self):
        self.assertEqual(self.exemple("tools/lanceur.sh"), "bash tools/lanceur.sh")

    def test_exemple_genere_depuis_le_parseur(self):
        self.assertEqual(self.exemple("tools/outil_genere.py"), "uv run tools/outil_genere.py voir --genre court --niveau 3")

    def test_marqueur_refuse_et_pas_d_exemple_invente(self):
        bloc = entree(self.texte, "tools/outil_placeholder.py")
        self.assertIsNone(self.exemple("tools/outil_placeholder.py"))
        self.assertIn("**Exemple** : aucun exemple", bloc)
        self.assertNotIn("<cle>", bloc)

    def test_exemple_de_commande_slash(self):
        self.assertEqual(self.exemple("/demo"), "/demo [fr|en]")

    def test_commande_slash_a_indication_marqueur(self):
        self.assertEqual(self.exemple("/marqueur"), "/marqueur")

    def test_aucun_marqueur_dans_un_exemple(self):
        for bloc in re.findall(r"\*\*Exemple\*\*\n+```[a-z]*\n(.*?)\n```", self.texte, re.S):
            for marqueur in ("<", ">", "...", "XXX", "chemin/vers"):
                self.assertNotIn(marqueur, bloc)

    def test_exemple_valide(self):
        self.assertFalse(manual.exemple_valide("uv run tools/autre.py", "outil_simple.py"))
        self.assertFalse(manual.exemple_valide("uv run tools/outil_simple.py <x>", "outil_simple.py"))
        self.assertFalse(manual.exemple_valide("uv run tools/outil_simple.py [--a]", "outil_simple.py"))
        self.assertTrue(manual.exemple_valide("uv run tools/outil_simple.py --a 1", "outil_simple.py"))


class LigneDeCommande(Base):
    def copie(self):
        copie = self.dossier / "copie"
        shutil.rmtree(copie, True)
        shutil.copytree(self.depot, copie)
        return copie

    def test_sans_option_imprime_et_n_ecrit_rien(self):
        copie = self.copie()
        resultat = lancer("--root", str(copie))
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertTrue(resultat.stdout.startswith("# Manuel d'utilisation de PMZilla Lab"))
        self.assertFalse((copie / "docs" / "pmzilla" / "manuel.md").exists())

    def test_ecriture(self):
        copie = self.copie()
        resultat = lancer("--root", str(copie), "--write")
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertRegex(resultat.stdout, r"manual : docs/pmzilla/manuel\.md écrit \(\d+ commandes\)")
        ecrit = (copie / "docs" / "pmzilla" / "manuel.md").read_text(encoding="utf-8")
        self.assertEqual(ecrit, lancer("--root", str(copie)).stdout)

    def test_controle_a_jour(self):
        copie = self.copie()
        lancer("--root", str(copie), "--write")
        resultat = lancer("--root", str(copie), "--check")
        self.assertEqual(resultat.returncode, 0)
        self.assertIn("manual : le manuel est à jour", resultat.stdout)

    def test_controle_perime_sans_rien_changer(self):
        copie = self.copie()
        lancer("--root", str(copie), "--write")
        chemin = copie / "docs" / "pmzilla" / "manuel.md"
        chemin.write_text(chemin.read_text(encoding="utf-8") + "\nmodifié\n", encoding="utf-8")
        avant = chemin.read_text(encoding="utf-8")
        resultat = lancer("--root", str(copie), "--check")
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("manual : le manuel n'est pas à jour : docs/pmzilla/manuel.md ; régénérer avec : uv run tools/manual.py --write",
                      resultat.stdout + resultat.stderr)
        self.assertEqual(chemin.read_text(encoding="utf-8"), avant)

    def test_controle_manuel_absent(self):
        copie = self.copie()
        resultat = lancer("--root", str(copie), "--check")
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("manual : le manuel est absent : docs/pmzilla/manuel.md ; régénérer avec : uv run tools/manual.py --write",
                      resultat.stdout + resultat.stderr)
        self.assertFalse((copie / "docs" / "pmzilla" / "manuel.md").exists())

    def test_option_inconnue(self):
        copie = self.copie()
        resultat = lancer("--root", str(copie), "--inconnue")
        self.assertEqual(resultat.returncode, 2)
        self.assertFalse((copie / "docs" / "pmzilla" / "manuel.md").exists())

    def test_modes_exclusifs(self):
        self.assertEqual(lancer("--root", str(self.copie()), "--write", "--check").returncode, 2)

    def test_racine_introuvable(self):
        self.assertEqual(lancer("--root", str(self.dossier / "absent")).returncode, 2)

    def test_source_illisible(self):
        copie = self.copie()
        (copie / "tools" / "casse.py").write_text("def (:\nif __name__ == '__main__':\n", encoding="utf-8")
        resultat = lancer("--root", str(copie), "--write")
        self.assertEqual(resultat.returncode, 2)
        self.assertIn("manual : source illisible : tools/casse.py (SyntaxError)", resultat.stdout + resultat.stderr)
        self.assertFalse((copie / "docs" / "pmzilla" / "manuel.md").exists())

    def test_aucun_tiret_cadratin_dans_les_messages(self):
        copie = self.copie()
        sortie = "".join(r.stdout + r.stderr for r in (lancer("--root", str(copie), "--check"),
                                                       lancer("--root", str(copie), "--write")))
        self.assertNotIn("—", sortie)

    def test_aucune_sentinelle_apres_la_ligne_de_commande(self):
        self.assertFalse(self.sentinelle.exists())


class Determinisme(Base):
    def test_deux_generations_memes_octets(self):
        self.assertEqual(manual.construire(self.depot, table=fixtures.TABLE).encode(), self.texte.encode())

    def test_deux_racines_memes_octets_sans_chemin_absolu(self):
        autre = self.dossier / "ailleurs" / "autre-depot"
        fixtures.construire_depot(autre, self.dossier / "ailleurs" / "SENTINELLE")
        texte = manual.construire(autre, table=fixtures.TABLE)
        self.assertEqual(texte.encode(), self.texte.encode())
        for racine in (str(self.dossier), str(autre), "/Users/", "/home/"):
            self.assertNotIn(racine, texte)

    def test_forme_du_fichier(self):
        self.assertTrue(self.texte.endswith("\n") and not self.texte.endswith("\n\n"))
        self.assertNotIn("\r", self.texte)
        self.assertEqual([n for n, ligne in enumerate(self.texte.split("\n")) if ligne != ligne.rstrip()], [])

    def test_ni_date_ni_heure(self):
        self.assertNotRegex(self.texte, r"\d{4}-\d{2}-\d{2}")
        self.assertNotRegex(self.texte, r"\b\d{2}:\d{2}\b")


if __name__ == "__main__":
    unittest.main()
