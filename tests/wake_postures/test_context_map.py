"""
La carte du contexte au réveil des postures (organisation-context, design D9 ; tâche 8.1) : section « CONTEXT MAP » du script wake.py des
quatre postures, après la liste des ouvrages hors bibliothèque.

    uv run --with pyyaml python -m unittest discover -s tests/wake_postures -v

Racine factice dans un dossier temporaire (skills, outils copiés, catalogue fictif) et dossier de contexte inventé (tests/context_lab/
fixtures_context.py) : jamais le vrai. Lecture seule, un seul fichier lu (la carte), les originaux jamais touchés.
"""
import contextlib
import io
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tests" / "context_lab"))
from fixtures_context import (CORPS_UNIQUE, NOM_EXTRAIT, NOM_GENERIQUE, NOM_SENSIBLE, SENTINELLE, Contexte, Surveillant,  # noqa: E402
                              note)

POSTURES = ["delivery", "discovery", "scaling", "facilitation"]
OUTILS_COPIES = ("outside_library.py", "references_postures.yaml", "context_lab.py", "lab_paths.py", "sensitive_names.py",
                 "identifiants_personnels.py")
CARTE = note(title="Carte du contexte", kind="map", body="## Périmètre produit\n\nUn produit inventé.\n\n## Forums\n\nUn forum mensuel.\n")


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.racine = Path(self.temp.name).resolve() / "workspace"
        (self.racine / "tools").mkdir(parents=True)
        shutil.copytree(RACINE / ".claude" / "skills", self.racine / ".claude" / "skills",
                        ignore=shutil.ignore_patterns("__pycache__", "bmad-*"))
        for nom in OUTILS_COPIES:
            shutil.copy2(RACINE / "tools" / nom, self.racine / "tools" / nom)
        (self.racine / "catalogue.yaml").write_text("{}\n", encoding="utf-8")
        (self.racine / "CLAUDE.md").write_text("# Test\n", encoding="utf-8")
        self.ctx = Contexte(notes={"carte-contexte.md": CARTE})
        self.addCleanup(self.ctx.close)

    def env(self, **extra):
        base = {"PATH": "/usr/bin:/bin", "PMZILLA_LAB_CATALOGUE": str(self.racine / "catalogue.yaml"),
                "PMZILLA_LAB_WORKSPACE": str(self.racine), "PMZILLA_LAB_CONTEXT": str(self.ctx.dossier),
                "PMZILLA_LAB_SENSITIVE_NAMES": str(self.ctx.liste), "PMZILLA_LAB_TODAY": "2026-10-18"}
        base.update(extra)
        return base

    def script(self, posture):
        return self.racine / ".claude" / "skills" / f"pmzilla-{posture}-bmad" / "scripts" / "wake.py"

    def wake(self, posture="delivery", **extra):
        fait = subprocess.run([sys.executable, str(self.script(posture))], capture_output=True, text=True, env=self.env(**extra))
        self.assertEqual(fait.returncode, 0, fait.stderr)
        return fait.stdout

    def section(self, sortie):
        self.assertIn("===== CONTEXT MAP", sortie)
        return sortie.split("===== CONTEXT MAP", 1)[1]


class Carte(Base):
    def test_carte_presente_dates_et_corps_pour_chaque_posture(self):
        for posture in POSTURES:
            with self.subTest(posture=posture):
                sortie = self.wake(posture)
                section = self.section(sortie)
                self.assertIn("Context map: 2026-09-01 · declarative · review 2027-03-01", section)
                self.assertNotIn("STALE", section)
                self.assertIn("## Périmètre produit", section)
                self.assertIn("Un forum mensuel.", section)
                self.assertGreater(sortie.index("CONTEXT MAP"), sortie.index("WORKS ABSENT FROM THE LIBRARY"))

    def test_carte_a_revoir_porte_la_marque(self):
        section = self.section(self.wake(PMZILLA_LAB_TODAY="2027-03-02"))
        self.assertIn("STALE (review due since 2027-03-01)", section)

    def test_carte_longue_coupee_a_la_limite(self):
        lignes = [f"ligne numero {n}" for n in range(1, 121)]
        self.ctx.ecrire("carte-contexte.md", note(title="Longue", kind="map", body="\n".join(lignes) + "\n"))
        section = self.section(self.wake())
        self.assertIn("ligne numero 80", section)
        self.assertNotIn("ligne numero 81", section)
        self.assertIn("(map truncated)", section)

    def test_carte_courte_pas_de_marque_de_coupure(self):
        self.assertNotIn("(map truncated)", self.section(self.wake()))

    def test_pas_de_carte(self):
        (self.ctx.notes / "carte-contexte.md").unlink()
        self.ctx.ecrire("2026-09-01-autre.md", note(body=f"{CORPS_UNIQUE}\n"))
        sortie = self.wake()
        self.assertIn("no context map", self.section(sortie))
        self.assertNotIn(CORPS_UNIQUE, sortie)

    def test_aucune_autre_note_n_est_imprimee(self):
        self.ctx.ecrire("2026-09-01-autre.md", note(body=f"{CORPS_UNIQUE}\n"))
        self.assertNotIn(CORPS_UNIQUE, self.wake())

    def test_pas_de_dossier_de_contexte(self):
        sortie = self.wake(PMZILLA_LAB_CONTEXT=str(self.ctx.tmp / "absent"))
        self.assertIn("no context folder", self.section(sortie))

    def test_carte_sans_marque_de_carte_ou_invalide(self):
        self.ctx.ecrire("carte-contexte.md", note(title="Pas une carte", body="x\n"))
        self.assertIn("no context map", self.section(self.wake()))
        self.ctx.ecrire("carte-contexte.md", note(title="Sans source", kind="map", sans=("source",)))
        self.assertIn("context map invalid: header field missing: source", self.section(self.wake()))

    def test_outil_absent_le_reveil_continue(self):
        (self.racine / "tools" / "context_lab.py").unlink()
        sortie = self.wake()
        self.assertIn("(context map not computed:", sortie)
        self.assertIn("WORKS ABSENT FROM THE LIBRARY", sortie)

    def test_la_formule_hors_bibliotheque_n_apparait_pas_dans_la_section(self):
        section = self.section(self.wake()).casefold()
        for formule in ("hors bibliothèque", "outside the library"):
            self.assertNotIn(formule, section)


class Garde(Base):
    """La carte contrôlée avant d'être imprimée (context-index-name-guard, design D5 ; tâches 2.3 et 2.4)."""

    CORPS = ["## Périmètre produit", "Un produit inventé.", "## Forums", "Un forum mensuel."]

    def carte(self, *lignes):
        """Écrit une carte dont le corps porte les lignes données ; renvoie le texte."""
        texte = note(title="Carte du contexte", kind="map", body="\n".join([*self.CORPS, *lignes]) + "\n")
        self.ctx.ecrire("carte-contexte.md", texte)
        return texte

    def ligne_de(self, texte, contenu):
        return texte.splitlines().index(contenu) + 1

    def assertSansCorps(self, section):
        for ligne in self.CORPS:
            self.assertNotIn(ligne, section)
        self.assertNotIn("Context map:", section)

    def test_nom_de_la_liste_dans_la_carte(self):
        texte = self.carte(f"le rôle voit {NOM_SENSIBLE}")
        section = self.section(self.wake())
        self.assertIn(f"context map not shown: sensitive name in line {self.ligne_de(texte, f'le rôle voit {NOM_SENSIBLE}')}", section)
        self.assertSansCorps(section)
        self.assertNotIn(NOM_SENSIBLE, section)

    def test_nom_de_l_extrait_dans_la_carte_pour_chaque_posture(self):
        texte = self.carte(f"avec {NOM_EXTRAIT}")
        self.ctx.ecrire_extrait()
        numero = self.ligne_de(texte, f"avec {NOM_EXTRAIT}")
        for posture in POSTURES:
            with self.subTest(posture=posture):
                fait = subprocess.run([sys.executable, str(self.script(posture))], capture_output=True, text=True, env=self.env())
                self.assertEqual(fait.returncode, 0, fait.stderr)
                section = self.section(fait.stdout)
                self.assertIn(f"context map not shown: extract team name in line {numero}", section)
                self.assertSansCorps(section)
                self.assertNotIn(NOM_EXTRAIT, fait.stdout + fait.stderr)

    def test_nom_generique_de_l_extrait_la_carte_s_imprime(self):
        self.carte(f"avec {NOM_GENERIQUE}")
        self.ctx.ecrire_extrait()
        section = self.section(self.wake())
        self.assertIn("Context map: 2026-09-01", section)

    def test_liste_absente(self):
        sortie = self.wake(PMZILLA_LAB_SENSITIVE_NAMES=str(self.ctx.tmp / "absente.txt"))
        section = self.section(sortie)
        self.assertIn("context map not shown: sensitive-names list unavailable", section)
        self.assertSansCorps(section)

    def test_liste_vide_avec_un_extrait(self):
        self.ctx.ecrire_extrait()
        self.ctx.liste.write_text("# rien\n", encoding="utf-8")
        section = self.section(self.wake())
        self.assertIn("context map not shown: sensitive-names list unavailable", section)

    def test_carte_propre_inchangee(self):
        self.ctx.ecrire_extrait()
        section = self.section(self.wake())
        self.assertIn("Context map: 2026-09-01 · declarative · review 2027-03-01", section)
        self.assertIn("Un forum mensuel.", section)
        self.assertNotIn("not shown", section)

    def test_l_arbre_est_identique_apres_un_refus(self):
        self.carte(f"avec {NOM_EXTRAIT}")
        self.ctx.ecrire_extrait()
        avant, contexte_avant = LectureSeule.empreinte(self), self.ctx.arbre()
        for posture in POSTURES:
            self.wake(posture)
        self.wake(PMZILLA_LAB_SENSITIVE_NAMES=str(self.ctx.tmp / "absente.txt"))
        self.assertEqual(LectureSeule.empreinte(self), avant)
        self.assertEqual(self.ctx.arbre(), contexte_avant)


class LectureSeule(Base):
    def empreinte(self):
        return {str(f.relative_to(self.racine.parent)): f.read_bytes() for f in sorted(self.racine.parent.rglob("*"))
                if f.is_file() and "__pycache__" not in f.parts and "originaux" not in f.parts}

    def test_l_arbre_est_identique_avant_et_apres(self):
        avant = self.empreinte()
        for posture in POSTURES:
            self.wake(posture)
        self.assertEqual(self.empreinte(), avant)

    def test_les_originaux_ne_sont_pas_touches(self):
        script = self.script("delivery")
        sortie = io.StringIO()
        with mock.patch.dict(os.environ, self.env()), mock.patch.object(sys, "argv", [str(script)]), \
                Surveillant(self.ctx.originaux).actif() as surveillant, contextlib.redirect_stdout(sortie):
            module = runpy.run_path(str(script), run_name="reveil")
            self.assertEqual(module["main"](), 0)
        self.assertEqual(surveillant.vus, [])
        self.assertIn("Context map: 2026-09-01", sortie.getvalue())
        self.assertNotIn(SENTINELLE, sortie.getvalue())

    def test_les_quatre_copies_du_code_de_la_carte_sont_identiques(self):
        def normalise(posture):
            texte = self.script(posture).read_text(encoding="utf-8")
            debut = texte.index("def context_map")
            fin = texte.index("def main")
            return texte[debut:fin]
        copies = {p: normalise(p) for p in POSTURES}
        for posture in POSTURES[1:]:
            self.assertEqual(copies[posture], copies["delivery"], posture)


if __name__ == "__main__":
    unittest.main()
