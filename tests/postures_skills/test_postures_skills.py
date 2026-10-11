"""
Les quatre skills de posture traduits en anglais (lot 6 de la version anglaise) : renvois, chemins, formules, copies communes.

    uv run --with pyyaml python -m unittest discover -s tests/postures_skills -v

Lecture seule du dépôt (skills, vocabulaire) ; les scripts tournent dans des dossiers temporaires. Aucun accès à Flux-Lab/
ni au sanctum réel.
"""
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
SKILLS = RACINE / ".claude" / "skills"
POSTURES = ["delivery", "discovery", "scaling", "facilitation"]
ANCIENS_NOMS = {  # fiches de capacité renommées au lot 6 (ancien nom -> nouveau nom)
    "choisir-lire-metriques": "choose-and-read-metrics", "diagnostiquer-flux": "diagnose-flow",
    "qualite-integree": "built-in-quality", "revoir-rituel": "review-ritual",
    "cadrer-probleme": "frame-problem", "concevoir-experimentation": "design-experiment",
    "formuler-hypotheses": "formulate-hypotheses",
    "coordination-multi-equipes": "multi-team-coordination", "diagnostiquer-topologie": "diagnose-topology",
    "evaluer-projet-okr": "assess-okr-project", "plateforme-comme-produit": "platform-as-product",
    "concevoir-atelier": "design-workshop", "posture-accompagnement": "coaching-stance",
    "preparer-questionnement": "prepare-questioning", "preparer-retrospective": "prepare-retrospective",
}
RENVOI = re.compile(r"references/([A-Za-z0-9_.-]+\.md)")
# renvois qui ne sont pas des fiches : un chemin d'exemple de la convention BMAD (SKILL.md) et une consigne d'un script de
# création de capacités qui n'est jamais atteinte (EVOLVABLE = False) ; ils existent à l'identique dans l'original
RENVOIS_HORS_FICHES = {"guide.md", "capability-authoring.md"}


def skill(posture: str) -> Path:
    return SKILLS / f"pmzilla-{posture}-bmad"


def fichiers_texte(posture: str, sans_memlog: bool = False):
    for chemin in sorted(skill(posture).rglob("*")):
        if chemin.is_file() and chemin.suffix in (".md", ".py", ".toml") and "__pycache__" not in chemin.parts:
            if sans_memlog and chemin.name == ".memlog.md":
                continue
            yield chemin


class Renvois(unittest.TestCase):
    def test_chaque_renvoi_a_une_fiche_pointe_vers_un_fichier_existant(self):
        for posture in POSTURES:
            for chemin in fichiers_texte(posture, sans_memlog=True):
                for nom in set(RENVOI.findall(chemin.read_text(encoding="utf-8"))) - RENVOIS_HORS_FICHES:
                    with self.subTest(posture=posture, fichier=chemin.name, renvoi=nom):
                        self.assertTrue((skill(posture) / "references" / nom).is_file(),
                                        f"{chemin.relative_to(RACINE)} renvoie à references/{nom}, absent")

    def test_chaque_fiche_declare_son_propre_nom(self):
        for posture in POSTURES:
            for fiche in sorted((skill(posture) / "references").glob("*.md")):
                en_tete = re.match(r"---\n(.*?)\n---", fiche.read_text(encoding="utf-8"), re.S)
                if fiche.name == "prompt-quality-canon.md":      # fichier du squelette BMAD, sans en-tête
                    continue
                with self.subTest(fiche=str(fiche.relative_to(RACINE))):
                    self.assertIsNotNone(en_tete)
                    self.assertEqual(yaml.safe_load(en_tete.group(1)).get("name"), fiche.stem)

    def test_les_fiches_ont_des_noms_anglais_en_kebab_case_et_les_anciens_noms_ont_disparu(self):
        for posture in POSTURES:
            for fiche in (skill(posture) / "references").glob("*.md"):
                self.assertRegex(fiche.stem, r"^[a-z]+(-[a-z]+)*$", fiche.name)
                self.assertNotIn(fiche.stem, ANCIENS_NOMS, f"{fiche} porte encore un ancien nom")
            for chemin in fichiers_texte(posture, sans_memlog=True):
                texte = chemin.read_text(encoding="utf-8")
                for ancien in ANCIENS_NOMS:
                    with self.subTest(fichier=str(chemin.relative_to(RACINE)), ancien=ancien):
                        self.assertNotIn(ancien, texte)

    def test_les_quinze_fiches_renommees_existent(self):
        presents = {f.stem for p in POSTURES for f in (skill(p) / "references").glob("*.md")}
        self.assertEqual(sorted(set(ANCIENS_NOMS.values()) - presents), [])

    def test_les_capacites_du_modele_citent_une_fiche_existante(self):
        for posture in POSTURES:
            texte = (skill(posture) / "assets" / "CAPABILITIES-template.md").read_text(encoding="utf-8")
            codes = re.findall(r"^\| ([A-Z]{2}) \|.*references/([\w.-]+)", texte, re.M)
            with self.subTest(posture=posture):
                self.assertGreaterEqual(len(codes), 3)
                for _, nom in codes:
                    self.assertTrue((skill(posture) / "references" / nom).is_file(), nom)


class SansCheminAbsolu(unittest.TestCase):
    def test_aucun_modele_ne_contient_de_chemin_absolu_ni_de_variable_de_chemin(self):
        for posture in POSTURES:
            for chemin in sorted((skill(posture) / "assets").glob("*.md")) + [skill(posture) / "SKILL.md"]:
                texte = chemin.read_text(encoding="utf-8")
                with self.subTest(fichier=str(chemin.relative_to(RACINE))):
                    self.assertNotRegex(texte, r"/(Users|home)/[^/\s]+/")
                    self.assertNotIn("{project_root}", texte)
                    self.assertNotIn("{sanctum_path}", texte)

    def test_aucun_fichier_du_skill_ne_contient_le_chemin_du_workspace(self):
        for posture in POSTURES:
            for chemin in fichiers_texte(posture):
                self.assertNotIn(str(RACINE), chemin.read_text(encoding="utf-8"), str(chemin))


class CopiesCommunes(unittest.TestCase):
    """Les deux scripts et le canon de qualité des prompts existent en quatre copies : elles ne diffèrent que par la posture."""

    def normalise(self, chemin: Path, posture: str) -> str:
        texte = chemin.read_text(encoding="utf-8")
        texte = texte.replace(f"pmzilla-{posture}-bmad", "pmzilla-P-bmad")
        return re.sub(rf"\b{posture}\b", "P", texte, flags=re.I)

    def test_scripts_identiques_a_la_posture_pres(self):
        for script in ("wake.py", "init-sanctum.py"):
            copies = {p: self.normalise(skill(p) / "scripts" / script, p) for p in POSTURES}
            for posture in POSTURES[1:]:
                with self.subTest(script=script, posture=posture):
                    self.assertEqual(copies[posture], copies["delivery"])

    def test_prompt_quality_canon_identique(self):
        copies = {p: (skill(p) / "references" / "prompt-quality-canon.md").read_text(encoding="utf-8") for p in POSTURES}
        for posture in POSTURES[1:]:
            self.assertEqual(copies[posture], copies["delivery"], posture)


class Formules(unittest.TestCase):
    def bloc(self, posture: str) -> str:
        texte = (skill(posture) / "assets" / "CREED-template.md").read_text(encoding="utf-8")
        debut = texte.index("## Reply language and fixed formulas")
        fin = texte.index("\n## ", debut + 5)
        return texte[debut:fin]

    def test_le_bloc_de_formules_est_au_meme_endroit_dans_les_quatre_creed(self):
        """Juste après Core Values et avant Standing Orders (les règles qu'il gouverne), dans l'ordre des sections."""
        ordres = {}
        for posture in POSTURES:
            texte = (skill(posture) / "assets" / "CREED-template.md").read_text(encoding="utf-8")
            titres = re.findall(r"(?m)^## (.+)$", texte)
            ordres[posture] = titres
            with self.subTest(posture=posture):
                self.assertEqual(titres.count("Reply language and fixed formulas"), 1)
                position = titres.index("Reply language and fixed formulas")
                self.assertEqual(titres[position - 1], "Core Values")
                self.assertEqual(titres[position + 1], "Standing Orders")
        for posture in POSTURES[1:]:
            self.assertEqual(ordres[posture], ordres["delivery"], posture)

    def test_le_bloc_est_identique_dans_les_quatre_creed(self):
        blocs = {p: self.bloc(p) for p in POSTURES}
        for posture in POSTURES[1:]:
            self.assertEqual(blocs[posture], blocs["delivery"], posture)

    def test_le_bloc_contient_toutes_les_formules_de_vocabulaire_yaml(self):
        vocabulaire = yaml.safe_load((RACINE / "tests" / "postures" / "vocabulaire.yaml").read_text(encoding="utf-8"))
        for posture in POSTURES:
            bloc = self.bloc(posture)
            for langue, valeurs in ((l, v) for l, v in vocabulaire.items() if isinstance(v, dict)):   # sans posture_names
                attendues = [valeurs["posture_tag"].replace("{posture}", "X"), valeurs["posture_tag"].replace("{posture}", "Critic"),
                             valeurs["out_of_library"], valeurs["hypothesis"], valeurs["critic_final_title"],
                             *valeurs["source_separation"]]
                for formule in attendues:
                    with self.subTest(posture=posture, langue=langue, formule=formule):
                        self.assertIn(formule, bloc)


class TitresDeRegistres(unittest.TestCase):
    """Les postures reprennent les titres et statuts déjà présents dans MEMORY.md ; les nouveaux sont en anglais (lot 6)."""

    REGLE_MG = ("**Language of the registers.** Use the section headings and the status values that MEMORY.md already contains, whatever their language "
                "(a sanctum created in French keeps its French headings and values). When you create a register, or a status value that MEMORY.md does not have yet, "
                "use the English ones given below. Never rename or translate what is already there; the table gives the French equivalents so you can recognise them.")
    REGLE_MODELE = ("_Register headings and status values: if this file already has some, keep them as they are, in whatever language; "
                    "new ones are written in English, as below (see `references/memory-guidance.md`)._")
    REGLE_FIRST_BREATH = ("Use the headings and status values MEMORY.md already contains, whatever their language; write a new register or value in English, "
                          "as listed in `references/memory-guidance.md` (which gives the French equivalents used by sanctums created in French).")
    REGLE_CREED = ("Use the headings and status values that MEMORY.md already contains, whatever their language; write new ones in English "
                   "(`references/memory-guidance.md` lists the French equivalents).")

    def lire(self, posture: str, relatif: str) -> str:
        return (skill(posture) / relatif).read_text(encoding="utf-8")

    def tableau(self, posture: str) -> list[tuple[str, str]]:
        texte = self.lire(posture, "references/memory-guidance.md")
        lignes = re.findall(r"(?m)^\| (.+?) \| (.+?) \|$", texte.split("| English (new sanctum)")[1])
        return [(e, f) for e, f in lignes if not e.startswith("---")]

    def test_la_meme_regle_dans_les_quatre_postures(self):
        for posture in POSTURES:
            with self.subTest(posture=posture):
                self.assertIn(self.REGLE_MG, self.lire(posture, "references/memory-guidance.md"))
                self.assertIn(self.REGLE_MODELE, self.lire(posture, "assets/MEMORY-template.md"))
                self.assertIn(self.REGLE_FIRST_BREATH, self.lire(posture, "references/first-breath.md"))
                self.assertIn(self.REGLE_CREED, self.lire(posture, "assets/CREED-template.md"))

    def test_les_titres_du_modele_sont_la_colonne_anglaise_du_tableau(self):
        for posture in POSTURES:
            anglais = [e for e, _ in self.tableau(posture)]
            titres = re.findall(r"(?m)^## (.+)$", self.lire(posture, "assets/MEMORY-template.md"))
            with self.subTest(posture=posture):
                self.assertGreaterEqual(len(titres), 3)
                for titre in titres:
                    self.assertIn(titre, anglais)

    def test_le_francais_des_registres_n_est_que_dans_le_tableau(self):
        """Les titres et statuts français ne figurent que dans la colonne française du tableau de memory-guidance.md."""
        for posture in POSTURES:
            francais = {f.strip("`") for _, f in self.tableau(posture)}
            francais = {m for f in francais for m in re.split(r"`, `|, ", f)}
            for chemin in fichiers_texte(posture, sans_memlog=True):
                texte = chemin.read_text(encoding="utf-8")
                if chemin.name == "memory-guidance.md":
                    texte = texte.split("| English (new sanctum)")[0] + texte.split("Link them by identifier")[1]
                for valeur in francais:
                    with self.subTest(posture=posture, fichier=chemin.name, valeur=valeur):
                        self.assertNotIn(valeur, texte)

    def test_les_valeurs_anglaises_de_statut_sont_dans_le_tableau(self):
        statuts = {"delivery": ["to be confirmed", "confirmed", "lifted", "in progress"],
                   "discovery": ["to test", "validated", "invalidated", "in progress"],
                   "scaling": ["open", "being handled", "removed", "established", "partial", "missing", "undetermined", "not yet observed"],
                   "facilitation": ["not yet noted"]}
        for posture, valeurs in statuts.items():
            tableau = " ".join(e for e, _ in self.tableau(posture))
            for valeur in valeurs:
                with self.subTest(posture=posture, valeur=valeur):
                    self.assertIn(f"`{valeur}`", tableau)


class Reveil(unittest.TestCase):
    """wake.py : racine et sanctum imprimés, calculés depuis l'emplacement du script."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.racine = Path(self.temp.name).resolve()
        shutil.copytree(SKILLS, self.racine / ".claude" / "skills", ignore=shutil.ignore_patterns("__pycache__"))
        (self.racine / "CLAUDE.md").write_text("# Test\n", encoding="utf-8")

    def wake(self, posture: str, *arguments: str, racine: Path | None = None, script: Path | None = None):
        script = script or (racine or self.racine) / ".claude" / "skills" / f"pmzilla-{posture}-bmad" / "scripts" / "wake.py"
        return subprocess.run([sys.executable, str(script), *arguments], capture_output=True, text=True,
                              env={"PATH": "/usr/bin:/bin"})

    def test_premier_reveil_imprime_la_racine_et_le_sanctum_sans_argument(self):
        for posture in POSTURES:
            fait = self.wake(posture)
            with self.subTest(posture=posture):
                self.assertEqual(fait.returncode, 0, fait.stderr)
                self.assertIn("MODE: FIRST_BREATH", fait.stdout)
                self.assertIn(f"Project root: {self.racine}", fait.stdout)
                self.assertIn(f"Sanctum: {self.racine / '_bmad' / 'memory' / f'pmzilla-{posture}-bmad'}", fait.stdout)

    def test_sanctum_cree_puis_reveil_dans_les_deux_emplacements_du_script(self):
        for posture in POSTURES:
            skill_copie = self.racine / ".claude" / "skills" / f"pmzilla-{posture}-bmad"
            fait = subprocess.run([sys.executable, str(skill_copie / "scripts" / "init-sanctum.py"), str(self.racine), str(skill_copie)],
                                  capture_output=True, text=True)
            self.assertEqual(fait.returncode, 0, fait.stderr)
            sanctum = self.racine / "_bmad" / "memory" / f"pmzilla-{posture}-bmad"
            for texte in (sanctum / "CREED.md", sanctum / "CAPABILITIES.md"):
                self.assertNotRegex(texte.read_text(encoding="utf-8"), r"/(Users|home|private|var)/", str(texte))
            for script in (skill_copie / "scripts" / "wake.py", sanctum / "scripts" / "wake.py"):
                sortie = self.wake(posture, script=script)
                with self.subTest(posture=posture, script=script.parent.parent.name):
                    self.assertEqual(sortie.returncode, 0, sortie.stderr)
                    self.assertIn("MODE: WAKING", sortie.stdout)
                    self.assertIn(f"Project root: {self.racine}", sortie.stdout)
                    self.assertIn(f"Sanctum: {sanctum}", sortie.stdout)

    def test_wake_n_ecrit_rien_dans_le_sanctum_ni_dans_la_racine(self):
        """wake.py est en lecture seule : l'arbre (hors __pycache__ du module de la liste) est identique avant et après."""
        def empreinte():
            return {str(f.relative_to(self.racine)): (f.stat().st_size, f.read_bytes())
                    for f in sorted(self.racine.rglob("*")) if f.is_file() and "__pycache__" not in f.parts}
        for posture in POSTURES:
            skill_copie = self.racine / ".claude" / "skills" / f"pmzilla-{posture}-bmad"
            subprocess.run([sys.executable, str(skill_copie / "scripts" / "init-sanctum.py"), str(self.racine), str(skill_copie)],
                           capture_output=True, text=True, check=True)
            avant = empreinte()
            for options in ((), ("--pulse",), (str(self.racine),)):
                self.assertEqual(self.wake(posture, *options).returncode, 0)
            self.assertEqual(empreinte(), avant, posture)

    def test_le_code_de_wake_ne_contient_aucune_ecriture(self):
        for posture in POSTURES:
            code = (skill(posture) / "scripts" / "wake.py").read_text(encoding="utf-8")
            code = re.sub(r'"""[\s\S]*?"""', "", code)
            for motif in (r"\.write_text\(", r"\.write_bytes\(", r"open\([^)]*['\"][wax]", r"\.mkdir\(", r"\.unlink\(", r"shutil\.", r"os\.(remove|rename|makedirs)"):
                with self.subTest(posture=posture, motif=motif):
                    self.assertIsNone(re.search(motif, code))

    def commande_de_reveil(self, posture: str) -> list[str]:
        """La commande du pas « Wake » de SKILL.md, telle qu'écrite, avec {skill-name} et {project-root} remplacés."""
        texte = (self.racine / ".claude" / "skills" / f"pmzilla-{posture}-bmad" / "SKILL.md").read_text(encoding="utf-8")
        ligne = next(l for l in texte.splitlines() if l.startswith("1. **Wake.**"))
        ecrite = re.search(r"`(uv run [^`]*wake\.py[^`]*)`", ligne).group(1)
        return shlex.split(ecrite.replace("{skill-name}", f"pmzilla-{posture}-bmad").replace("{project-root}", str(self.racine)))

    def test_la_commande_de_reveil_de_skill_md_fonctionne_depuis_la_racine_du_projet(self):
        """Lot 6, correctif : `uv run scripts/wake.py` (chemin relatif au skill) échouait quand la séance l'appelait depuis la racine
        (« Failed to spawn »). La commande écrite dans SKILL.md est lancée telle quelle, depuis la racine, contre un sanctum temporaire."""
        uv = shutil.which("uv")
        if not uv:
            self.skipTest("uv absent")
        env = {"PATH": "/usr/bin:/bin:" + str(Path(uv).parent), "HOME": str(Path.home()), "UV_OFFLINE": "1"}
        for posture in POSTURES:
            commande = self.commande_de_reveil(posture)
            with self.subTest(posture=posture):
                self.assertEqual(commande[:3], ["uv", "run", f".claude/skills/pmzilla-{posture}-bmad/scripts/wake.py"])
                self.assertTrue((self.racine / commande[2]).is_file())
                # 1. sans sanctum : premier souffle
                premier = subprocess.run(commande, cwd=self.racine, capture_output=True, text=True, env=env)
                self.assertEqual(premier.returncode, 0, premier.stderr)
                self.assertIn("MODE: FIRST_BREATH", premier.stdout)
                self.assertNotIn("Failed to spawn", premier.stderr)
                # 2. avec un sanctum temporaire : réveil
                skill_copie = self.racine / ".claude" / "skills" / f"pmzilla-{posture}-bmad"
                subprocess.run([sys.executable, str(skill_copie / "scripts" / "init-sanctum.py"), str(self.racine), str(skill_copie)],
                               capture_output=True, text=True, check=True)
                reveil = subprocess.run(commande, cwd=self.racine, capture_output=True, text=True, env=env)
                self.assertEqual(reveil.returncode, 0, reveil.stderr)
                self.assertIn("MODE: WAKING", reveil.stdout)
                self.assertIn(f"Project root: {self.racine}", reveil.stdout)
                self.assertEqual(reveil.stderr, "")

    def test_l_ancienne_forme_relative_au_skill_echoue_depuis_la_racine_et_n_est_plus_ecrite(self):
        """Témoin : la forme d'avant échoue depuis la racine ; aucun SKILL.md ne l'écrit plus."""
        uv = shutil.which("uv")
        if not uv:
            self.skipTest("uv absent")
        env = {"PATH": "/usr/bin:/bin:" + str(Path(uv).parent), "HOME": str(Path.home()), "UV_OFFLINE": "1"}
        ancienne = subprocess.run(["uv", "run", "scripts/wake.py", str(self.racine)], cwd=self.racine, capture_output=True, text=True, env=env)
        self.assertNotEqual(ancienne.returncode, 0)
        self.assertIn("scripts/wake.py", ancienne.stderr)
        for posture in POSTURES:
            self.assertNotIn("run scripts/wake.py", (skill(posture) / "SKILL.md").read_text(encoding="utf-8"))

    def test_la_ligne_de_reveil_est_identique_dans_les_quatre_skill_md(self):
        lignes = {}
        for posture in POSTURES:
            texte = (skill(posture) / "SKILL.md").read_text(encoding="utf-8")
            ligne = next(l for l in texte.splitlines() if l.startswith("1. **Wake.**"))
            lignes[posture] = ligne.replace(f"pmzilla-{posture}-bmad", "pmzilla-P-bmad")
        for posture in POSTURES[1:]:
            self.assertEqual(lignes[posture], lignes["delivery"], posture)

    def test_un_argument_different_est_signale_et_ignore(self):
        autre = self.racine / "ailleurs"
        autre.mkdir()
        fait = self.wake("delivery", str(autre))
        self.assertEqual(fait.returncode, 0, fait.stderr)
        self.assertIn("argument ignored", fait.stderr)
        self.assertIn(f"Project root: {self.racine}", fait.stdout)

    def test_l_argument_identique_ne_produit_aucun_avertissement(self):
        fait = self.wake("delivery", str(self.racine))
        self.assertEqual(fait.stderr, "")


if __name__ == "__main__":
    unittest.main()
