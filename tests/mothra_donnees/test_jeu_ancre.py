"""
Le jeu synthétique de la tranche 0 ne dépend plus de l'heure du chargement pour ses Story « Done » (R-20261105-16).

Module pur : aucune base, aucune connexion. Il refait en Python, au plus court, ce que lit le tableau « lead time » de l'e2e
(tests/e2e/squelette.spec.ts:31) :
  - la fenêtre des trois derniers trimestres terminés (R-20261114-49 ; quatre avant) et les semaines du lundi UTC de flow.v_team_lead_time_throughput ;
  - la règle T3 (b) de flow.v_t3_withheld, db/migrations/0030_flow_t3_withheld.sql:76-78, lectures à cheval comprises (0030:56-71),
    les lignes hebdomadaires groupées par (équipe, type, semaine) comme 0030:47-54 ;
  - l'ordre des équipes de l'écran, celui des identifiants opaques (identifiantEquipe de mothra/contract/src/equipe.ts).
Source : la vue et le contrat, jamais ce module. Un écart entre eux et cette réplique n'est détecté que par l'e2e squelette (cellule
« value » attendue) : aucun test de la suite db ne compare la réplique à la vue, et la réplique de identifiantEquipe n'est vérifiée que
par l'e2e (aucune voie permise n'exécute le TypeScript depuis ce module). Remplace : rien. Retrait : avec la règle T3 (b) ou avec l'ancre
du jeu.

    bash tests/run_all.sh mothra_donnees
"""
from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jeu_synthetique as jeu  # noqa: E402

DEBUT = datetime(2026, 11, 1, tzinfo=timezone.utc)
INSTANTS = [DEBUT + timedelta(hours=5 * i) for i in range(5256)]      # toutes les 5 h sur 3 ans


def debut_trimestre(d: date) -> date:
    return date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)


def mois_plus(d: date, mois: int) -> date:
    n = d.year * 12 + d.month - 1 + mois
    return date(n // 12, n % 12 + 1, 1)


def ancre(maintenant: datetime) -> datetime:
    """Lundi 00:00 UTC de la semaine qui contient (début du dernier trimestre terminé + 21 jours), décision R-20261105-16."""
    jour = mois_plus(debut_trimestre(maintenant.astimezone(timezone.utc).date()), -3) + timedelta(days=21)
    lundi = jour - timedelta(days=jour.weekday())
    return datetime(lundi.year, lundi.month, lundi.day, tzinfo=timezone.utc)


def lundi(instant: datetime) -> date:
    d = instant.astimezone(timezone.utc).date()
    return d - timedelta(days=d.weekday())


def _imul(a: int, b: int) -> int:
    return (a * b) & 0xFFFFFFFF


def identifiant_equipe(nom: str) -> str:
    """Réplique de identifiantEquipe (cyrb64 sur les unités UTF-16 du nom), mothra/contract/src/equipe.ts:14."""
    h1, h2 = 0xDEADBEEF, 0x41C6CE57
    unites = nom.encode("utf-16-le")
    for i in range(0, len(unites), 2):
        c = unites[i] | (unites[i + 1] << 8)
        h1, h2 = _imul(h1 ^ c, 2654435761), _imul(h2 ^ c, 1597334677)
    h1 = _imul(h1 ^ (h1 >> 16), 2246822507) ^ _imul(h2 ^ (h2 >> 13), 3266489909)
    h2 = _imul(h2 ^ (h2 >> 16), 2246822507) ^ _imul(h1 ^ (h1 >> 13), 3266489909)
    return f"{h2:08x}{h1:08x}"


def story_done(tickets: list[dict]) -> list[dict]:
    return [t for t in tickets if t["equipe"] and t["categorie"] == "Done" and t["type"] in ("Story", "Task")]


def trimestres_publies(maintenant: datetime, tickets: list[dict]) -> dict[str, list[date]]:
    """Par équipe, les trimestres de la fenêtre dont le débit est publié : n >= 5 et non retiré par T3 (a) ou (b), 0030:73-78."""
    q0 = debut_trimestre(maintenant.astimezone(timezone.utc).date())
    fenetre = {mois_plus(q0, -3 * k) for k in range(1, 4)}
    par_equipe: dict[str, list[tuple[str, datetime]]] = {}
    for t in story_done(tickets):
        par_equipe.setdefault(t["equipe"], []).append((t["type"], t["resolu"]))
    publies: dict[str, list[date]] = {}
    for equipe, resolus in par_equipe.items():
        semaines: dict[tuple[str, date], int] = {}          # une ligne hebdomadaire par (équipe, type, semaine), 0030:47-54
        for type_, r in resolus:
            semaines[(type_, lundi(r))] = semaines.get((type_, lundi(r)), 0) + 1
        debits: dict[date, int] = {}
        for _, r in resolus:
            q = debut_trimestre(r.astimezone(timezone.utc).date())
            if q in fenetre:
                debits[q] = debits.get(q, 0) + 1
        publies[equipe] = []
        for q, n in debits.items():
            fin = mois_plus(q, 3)
            retire = n < 5                                                                  # règle (a)
            for avec_debut in (False, True):
                for avec_fin in (False, True):
                    lues = [c for (_, s), c in semaines.items()
                            if s + timedelta(7) > q and s < fin
                            and ((s >= q and s + timedelta(7) <= fin) or (s < q and avec_debut) or (s + timedelta(7) > fin and avec_fin))]
                    k = sum(1 for c in lues if c < 5)
                    s_ = n - sum(c for c in lues if c >= 5)
                    if k >= 1 and k <= s_ <= 4 * k and not (k >= 2 and s_ >= 5 and s_ != k and s_ != 4 * k):
                        retire = True                                                       # règle (b)
            if not retire:
                publies[equipe].append(q)
    return publies


class DatesAncrees(unittest.TestCase):
    def test_story_done_identiques_relativement_a_l_ancre(self):
        reference = [(t["cle"], t["resolu"] - ancre(DEBUT), t["cree"] - ancre(DEBUT)) for t in story_done(jeu.construire(DEBUT))]
        bascules = [datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc), datetime(2027, 1, 1, 0, 0, tzinfo=timezone.utc),
                    datetime(2027, 3, 31, 23, 59, tzinfo=timezone.utc), datetime(2027, 4, 1, 0, 0, tzinfo=timezone.utc)]   # trimestre et année
        for maintenant in (DEBUT + timedelta(hours=7), DEBUT + timedelta(hours=12, minutes=35), DEBUT + timedelta(days=3, hours=18),
                           *bascules, *INSTANTS[::97]):
            a = ancre(maintenant)
            autre = [(t["cle"], t["resolu"] - a, t["cree"] - a) for t in story_done(jeu.construire(maintenant))]
            self.assertEqual(autre, reference, maintenant.isoformat())


class PremiereEquipePubliee(unittest.TestCase):
    def test_premiere_equipe_affichee_publiee_sur_trois_ans(self):
        rouges = []
        for maintenant in INSTANTS:
            publies = trimestres_publies(maintenant, jeu.construire(maintenant))
            premiere = min(publies, key=identifiant_equipe)          # les équipes qui ont une ligne dans la fenêtre
            if not publies[premiere] or not publies.get("équipe C") or not publies.get("équipe A"):
                rouges.append(maintenant.isoformat())
        self.assertEqual(rouges[:5], [], f"{len(rouges)} instants sur {len(INSTANTS)} sans trimestre publié pour la première équipe, C ou A")

    def test_la_premiere_equipe_est_l_equipe_c(self):
        self.assertEqual(min(jeu.EQUIPES_GENERIQUES, key=identifiant_equipe), "équipe C")


class SemainesTemoins(unittest.TestCase):
    def test_semaines_temoins_de_une_a_deux_story_done(self):
        # Sur les équipes publiées seulement (A et C) : des lignes hebdomadaires (équipe, type, semaine) de 1 et de 2 Story « Done ».
        for maintenant in INSTANTS[::53]:
            tickets = jeu.construire(maintenant)
            publiees = {e for e, trimestres in trimestres_publies(maintenant, tickets).items() if trimestres}
            self.assertLessEqual({"équipe A", "équipe C"}, publiees, maintenant.isoformat())
            semaines: dict[tuple[str, str, date], int] = {}
            for t in story_done(tickets):
                if t["equipe"] in publiees and t["type"] == "Story":
                    cle = (t["equipe"], t["type"], lundi(t["resolu"]))
                    semaines[cle] = semaines.get(cle, 0) + 1
            comptes = set(semaines.values())
            self.assertIn(1, comptes, maintenant.isoformat())
            self.assertIn(2, comptes, maintenant.isoformat())


if __name__ == "__main__":
    unittest.main()
