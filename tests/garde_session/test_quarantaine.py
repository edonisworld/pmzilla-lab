"""Garde de session, niveau 1 (change session-guard-n1, tâche 9.4, design D11) : quarantaine du skill bmad-eval-runner (classe H) et absence de l'option qui
saute les contrôles de permission dans les skills et les agents.

Trois contrôles statiques de l'arbre :
 - aucun `SKILL.md` de ce skill sous .claude/skills/ ;
 - le dossier de quarantaine .claude/quarantaine/bmad-eval-runner/ contient `SKILL.md.quarantaine` ;
 - aucun fichier de .claude/skills/ ni de .claude/agents/ ne porte l'option de Claude Code qui saute les permissions.

Le fichier d'étape P1 de l'auteur (git mv du skill, renommage de SKILL.md) pose la quarantaine. Tant qu'elle n'est pas posée, les trois tests sont SAUTÉS (le skill,
son adaptateur et sa référence portent encore l'option) ; ils ÉCHOUENT dès qu'elle est posée à moitié, et passent quand tout est posé. Un réinstall de BMAD qui remettrait
le skill ferait échouer le premier contrôle.

Remplace : rien (aujourd'hui rien ne contrôle cette option). Retrait : au go ou no-go de BMAD 7 (4/12) et après une revue Opus (R-20261107-22) ; le fichier d'étape de cette
décision retire ensemble la quarantaine, ces tests et la règle H de la garde.

    bash tests/run_all.sh garde_session
"""
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SKILLS = RACINE / ".claude" / "skills"
AGENTS = RACINE / ".claude" / "agents"
QUARANTAINE = RACINE / ".claude" / "quarantaine"
SKILL = "bmad-eval-runner"
# L'option est écrite en deux morceaux pour que ce fichier ne la porte pas lui-même en clair.
OPTION = "--dangerously" + "-skip-permissions"


def pose_declaree() -> bool:
    return QUARANTAINE.is_dir()


class Quarantaine(unittest.TestCase):
    def setUp(self):
        if not pose_declaree():
            self.skipTest("quarantaine pas encore posée (fichier d'étape P1 de l'auteur)")

    def test_aucun_skill_md_du_skill_sous_les_skills(self):
        self.assertEqual([str(p.relative_to(RACINE)) for p in (SKILLS / SKILL).rglob("SKILL.md")] if (SKILLS / SKILL).exists() else [], [],
                         "le skill est encore chargé : SKILL.md sous .claude/skills/")
        self.assertEqual([str(p.relative_to(RACINE)) for p in SKILLS.rglob("SKILL.md") if p.parent.name == SKILL], [])

    def test_le_dossier_de_quarantaine_porte_le_skill_renomme(self):
        self.assertTrue((QUARANTAINE / SKILL / "SKILL.md.quarantaine").is_file(), "SKILL.md.quarantaine absent de .claude/quarantaine/bmad-eval-runner/")
        self.assertFalse((QUARANTAINE / SKILL / "SKILL.md").exists(), "le skill en quarantaine ne doit plus porter SKILL.md")

    def test_aucune_option_qui_saute_les_permissions_dans_les_skills_et_les_agents(self):
        porteurs = []
        for dossier in (SKILLS, AGENTS):
            if not dossier.is_dir():
                continue
            for fichier in sorted(p for p in dossier.rglob("*") if p.is_file()):
                try:
                    texte = fichier.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                if OPTION in texte:
                    porteurs.append(str(fichier.relative_to(RACINE)))
        self.assertEqual(porteurs, [], "fichier(s) qui portent l'option qui saute les permissions")


class SansPose(unittest.TestCase):
    """Le lecteur de la pose : le contrôle sait dire dans quel état est l'arbre."""

    def test_la_pose_se_lit_sur_le_dossier_de_quarantaine(self):
        self.assertEqual(pose_declaree(), QUARANTAINE.is_dir())

    def test_l_option_n_est_pas_ecrite_en_clair_dans_ce_fichier(self):
        self.assertNotIn(OPTION, Path(__file__).read_text(encoding="utf-8"))

    def test_une_pose_a_moitie_serait_vue(self):
        """Sans pose, le skill porte encore SKILL.md ou l'option ; avec la pose, les trois contrôles de la classe Quarantaine s'appliquent."""
        if pose_declaree():
            self.skipTest("quarantaine posée : les trois contrôles s'appliquent")
        self.assertTrue((SKILLS / SKILL / "SKILL.md").is_file() or not (SKILLS / SKILL).exists())


if __name__ == "__main__":
    unittest.main()
