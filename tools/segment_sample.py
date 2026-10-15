# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "numpy", "psycopg[binary]"]
# ///
"""
PMZilla Lab : échantillon de tickets d'un segment, pour regarder dans l'historique Jira ce qui se cache derrière
un temps par segment (le P50 de « Revue et vérification » d'un rapport de flux, par exemple).

    uv run tools/segment_sample.py <export.csv>... [--segment revue_verification] [--today AAAA-MM-JJ]
                                        [--seed 42] [--longest 6] [--near-median 4] [--oldest 3]
                                        [--by-state] [--starts] [--exclude-batch-closures] [--weeks 26] [--scope ABC,DEF] [--types Story,Bug] [--history CACHE]

Même population et même calcul que la section « Temps par segment » de flux_jira.py compute --history : les
tickets sortis du segment pendant la période (une visite terminée dont la date de sortie tombe dans les semaines
complètes analysées), temps cumulé sur toutes leurs visites terminées du segment. Les exports, le cache, les
réglages de flux.yaml (états des segments, projets et types écartés) et les fonctions de calcul sont ceux de
flux_jira.py : le P50 affiché en tête doit retomber sur celui du rapport. Pour refaire le calcul d'un rapport
daté, passer --today à la date du rapport (la période en dépend).

Sortie, dans le Terminal seulement (rien n'est écrit sur le disque) :
  1. les états qui composent le segment, tels que flux_jira.py les range ;
  2. la population (effectif, P50, P85, moyenne) et la fenêtre « proche de la médiane » (P40 à P60) ;
  3. les plus longs (temps cumulé) ;
  4. un tirage au hasard, à graine fixe, parmi les tickets de la fenêtre proche de la médiane ;
  5. à part, les tickets les plus anciens encore dans le segment (âge de la visite en cours).
Avec --by-state, trois sections de plus :
  6. le temps passé dans chaque état du segment, sur toute la population : total, part du temps du segment, P50 et P85
     parmi les tickets passés par l'état (au moins une période dans l'état, même de 0 jour), nombre de ces tickets ;
  7. le détail des jours par état des tickets de l'échantillon (plus longs, tirés, encore dans le segment) ;
  8. pour les plus longs, le nombre d'autres tickets de la population dont une visite du segment se termine le même jour
     que leur visite la plus longue (sorties groupées), avec le nombre de sorties par jour de la population en repère.
Avec --starts, une section de plus :
  9. les passages de « Ready for Verification » à « Verification - Ongoing » de la population, par projet (jamais de
     clé) : pour chaque projet d'au moins --min-passes passages (20 par défaut), nombre de passages, nombre de jours
     distincts où il y en a eu, part des passages tombés sur les 20 % de jours les plus chargés (arrondis au-dessus,
     au moins un jour), puis deux mesures contre le hasard (1000 tirages, graine --seed, passages du projet tirés
     au hasard sur les jours ouvrés de la période, jours fériés français retirés) :
       - la concentration à jours actifs égaux : part attendue (moyenne des tirages, même règle des 20 % de jours les plus
         chargés appliquée aux jours distincts de chaque tirage), 95e centile des tirages, indicateur « oui » si la part
         observée le dépasse strictement. Elle garde le nombre de jours distincts réel : elle ne voit pas qu'un projet
         n'a que peu de jours actifs ;
       - les jours actifs, sans condition : nombre de jours distincts attendu (moyenne des tirages), 5e centile, rapport
         observé / attendu et indicateur « moins de jours actifs que le hasard » (« oui » si le nombre de jours distincts
         observé est strictement sous le 5e centile) ;
     et le P50 de l'attente en « Ready for Verification » avant chaque passage.
Avec --exclude-batch-closures, les tickets sortis du segment dans une fermeture en lot sont retirés de la population
avant tout calcul : la règle est celle de la section « Fermetures groupées » de flux_jira.py (fonction partagée
flux_jira.tickets_en_fermeture_groupee) : un ticket livré (motif de résolution hors motifs_exclus) dont la résolution
tombe dans la même minute que celle d'au moins seuil_fermetures_groupees - 1 autres du même projet (5 par défaut), parmi
les motifs de motifs_fermetures_groupees (« Done » par défaut), sur les semaines analysées. La sortie dit en tête combien
de tickets et combien de passages (de Ready for Verification à Verification - Ongoing) sont écartés ; la population, le
temps par état, les passages par projet et les jours actifs contre le hasard sont calculés sans eux. Il faut l'heure
dans la date de résolution : sans heure, un ticket n'est jamais en lot. Sans l'option, la sortie ne change pas.
Pour chaque ticket : clé, projet, jours, nombre de visites, dates d'entrée et de sortie de la visite la plus longue,
état d'origine (celui d'où le ticket arrive) et état de destination (celui où il va). Clés et états seulement : le
script ne lit ni titre ni personne (flux_jira.read_export ne les garde pas). Les clés ne vont dans aucun fichier
suivi par Git.

Le tirage est reproductible à données, date de calcul et graine identiques.

Exemple :
    uv run tools/segment_sample.py export.csv
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import random
import sys
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flux_config as cfg
import flux_jira as fj
from messages import Messages, add_language_option
from segment_sample_messages import CATALOGS

commun = fj.commun
ETAT_ATTENTE = "Ready for Verification"       # états du passage suivi par --starts
ETAT_DEBUT = "Verification - Ongoing"
PART_JOURS_CHARGES = 0.20
TIRAGES = 1000                                 # tirages de la part attendue au hasard (--starts)
ORIGINE_CREATION = "(création)"
DESTINATION_RESOLU = "(résolu depuis le segment)"
SANS_PROJET = "(sans projet)"                  # reperes internes des lignes : leur affichage passe par le catalogue


def nom_segment(nom: str, t: Messages) -> str:
    """Nom d'un segment pour l'affichage : le nom anglais en anglais (segments par défaut), le nom du réglage sinon."""
    return cfg.SEGMENTS.get(nom, nom) if t.language == "en" else nom


def origine(periodes: list, visite: dict) -> str:
    """État d'où le ticket arrive : celui de la période qui précède la visite (la création si elle n'a pas de précédente)."""
    return periodes[visite["premier"] - 1][0] if visite["premier"] > 0 else ORIGINE_CREATION


def destination(periodes: list, visite: dict) -> str:
    """État où le ticket va : celui de la période qui suit la visite (une résolution depuis le segment n'en a pas)."""
    suivante = visite["dernier"] + 1
    return periodes[suivante][0] if suivante < len(periodes) else DESTINATION_RESOLU


def jours_par_etat(periodes_t: list, visites: list[dict], canon: dict[str, str]) -> dict[str, int]:
    """Jours passés dans chaque état par un ticket, sur les visites données : la somme des périodes de chaque visite,
    comme flux_jira.visites. Un état traversé sans durée (changement le même jour) apparaît avec 0."""
    jours: dict[str, int] = {}
    for v in visites:
        for etat, debut, fin in periodes_t[v["premier"]:v["dernier"] + 1]:
            nom = canon.get(etat.strip().casefold(), etat)
            jours[nom] = jours.get(nom, 0) + (fin - debut).days
    return jours


def passages(periodes_t: list, visites: list[dict]) -> list[tuple[dt.date, int]]:
    """(date, attente) de chaque passage direct de ETAT_ATTENTE à ETAT_DEBUT à l'intérieur des visites données : la date
    de la transition, et les jours passés dans ETAT_ATTENTE juste avant (la période qui précède le passage)."""
    de, vers = ETAT_ATTENTE.casefold(), ETAT_DEBUT.casefold()
    trouves = []
    for v in visites:
        for i in range(v["premier"], v["dernier"]):
            (etat, debut, fin), suivant = periodes_t[i], periodes_t[i + 1]
            if etat.strip().casefold() == de and suivant[0].strip().casefold() == vers:
                trouves.append((fin, (fin - debut).days))
    return trouves


def analyser(tickets: list[dict], periodes: dict, segment_de: dict[str, str], segment: str,
             debut_periode: dt.date, fin_periode: dt.date, canon: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """(sortis, dedans). Mêmes règles que flux_jira.temps_par_segment : un ticket est « sorti » si une de ses visites
    terminées du segment finit dans la période ; son temps est la somme de toutes ses visites terminées. `canon` range
    le nom d'un état en minuscules vers son nom dans la liste du segment."""
    sortis, dedans = [], []
    for t in tickets:
        periodes_t = periodes.get(t["cle"].upper())
        if periodes_t is None:
            continue
        vues = [v for v in fj.visites(periodes_t, segment_de, ouvert=not t["resolu"]) if v["segment"] == segment]
        terminees = [v for v in vues if not v["en_cours"]]
        if any(debut_periode <= v["fin"] <= fin_periode for v in terminees):
            longue = max(terminees, key=lambda v: (v["jours"], -v["debut"].toordinal()))
            sortis.append({"cle": t["cle"], "projet": t["projet"], "jours": sum(v["jours"] for v in terminees),
                           "visites": len(terminees), "entree": longue["debut"], "sortie": longue["fin"],
                           "jours_visite": longue["jours"], "origine": origine(periodes_t, longue),
                           "destination": destination(periodes_t, longue),
                           "par_etat": jours_par_etat(periodes_t, terminees, canon),
                           "fins": {v["fin"] for v in terminees}, "passages": passages(periodes_t, terminees)})
        courante = next((v for v in vues if v["en_cours"]), None)
        if courante:
            dedans.append({"cle": t["cle"], "projet": t["projet"], "jours": courante["jours"],
                           "cumul": sum(v["jours"] for v in vues), "visites": len(vues),
                           "entree": courante["debut"], "etat": periodes_t[-1][0],
                           "origine": origine(periodes_t, courante),
                           "par_etat": jours_par_etat(periodes_t, vues, canon)})
    return sortis, dedans


def echantillonner(sortis: list[dict], n_longs: int, n_proches: int, graine: int) -> dict:
    """Les n_longs plus longs, puis n_proches tirés au hasard (graine fixe) parmi les tickets dont le temps cumulé est
    entre le P40 et le P60 de la population. Égalités départagées par la clé, pour que le tirage soit reproductible."""
    ordre = sorted(sortis, key=lambda r: (-r["jours"], r["cle"]))
    longs = ordre[:n_longs]
    jours = [r["jours"] for r in sortis]
    bas, haut = (float(np.percentile(jours, 40)), float(np.percentile(jours, 60))) if jours else (0.0, 0.0)
    pris = {r["cle"] for r in longs}
    candidats = sorted((r for r in sortis if bas <= r["jours"] <= haut and r["cle"] not in pris),
                       key=lambda r: r["cle"])
    tires = random.Random(graine).sample(candidats, min(n_proches, len(candidats)))
    return {"longs": longs, "proches": sorted(tires, key=lambda r: (-r["jours"], r["cle"])),
            "candidats": len(candidats), "fenetre": (bas, haut)}


def tableau(lignes: list[dict], colonnes: list[tuple[str, str]], t: Messages) -> list[str]:
    """Tableau Markdown : colonnes = (clé du titre dans le catalogue, clé de la ligne) ; une date s'écrit AAAA-MM-JJ."""
    reperes = {ORIGINE_CREATION: t("origin_creation"), DESTINATION_RESOLU: t("destination_resolved")}
    texte = lambda v: v.isoformat() if isinstance(v, dt.date) else reperes.get(v, str(v))
    sortie = ["| " + " | ".join(t(titre) for titre, _ in colonnes) + " |", "|" + "---|" * len(colonnes)]
    sortie += ["| " + " | ".join(texte(r[k]) for _, k in colonnes) + " |" for r in lignes]
    return sortie


COLONNES_SORTIS = [("col_key", "cle"), ("col_project", "projet"), ("col_days_cumulative", "jours"), ("col_visits", "visites"),
                   ("col_entry_longest", "entree"), ("col_exit", "sortie"),
                   ("col_days_visit", "jours_visite"), ("col_origin", "origine"), ("col_destination", "destination")]
COLONNES_DEDANS = [("col_key", "cle"), ("col_project", "projet"), ("col_age_current", "jours"),
                   ("col_entry", "entree"), ("col_days_cumulative_previous", "cumul"),
                   ("col_visits_current", "visites"), ("col_current_state", "etat"), ("col_origin", "origine")]


def stats_par_etat(sortis: list[dict], etats: list[str]) -> list[dict]:
    """Pour chaque état du segment : tickets passés, total de jours, part du temps du segment, P50 et P85 des jours par
    ticket parmi les tickets passés. Les états sans ticket restent dans la liste, à 0."""
    total = sum(r["jours"] for r in sortis)
    lignes = []
    for etat in etats:
        valeurs = [r["par_etat"][etat] for r in sortis if etat in r["par_etat"]]
        lignes.append({"etat": etat, "tickets": len(valeurs), "total": sum(valeurs),
                       "part": sum(valeurs) / total if total else None,
                       "p50": float(np.percentile(valeurs, 50)) if valeurs else None,
                       "p85": float(np.percentile(valeurs, 85)) if valeurs else None})
    return lignes


def sorties_groupees(sortis: list[dict], longs: list[dict]) -> tuple[list[dict], dict]:
    """Pour chaque ticket de `longs` : nombre d'autres tickets de la population dont une visite du segment se termine le
    jour où se termine sa visite la plus longue. Repère : sorties par jour sur les jours où il y en a eu au moins une."""
    par_jour = Counter(jour for r in sortis for jour in r["fins"])
    par_ticket = [{"cle": r["cle"], "sortie": r["sortie"], "autres": par_jour[r["sortie"]] - 1} for r in longs]
    quotidiennes = sorted(par_jour.values())
    repere = {"jours": len(quotidiennes), "p50": float(np.percentile(quotidiennes, 50)),
              "p85": float(np.percentile(quotidiennes, 85)), "max": quotidiennes[-1],
              "date_max": min(j for j, n in par_jour.items() if n == quotidiennes[-1])}
    return par_ticket, repere


def affichage_par_etat(sortis: list[dict], ech: dict, anciens: list[dict], etats: list[str], t: Messages) -> list[str]:
    """Les trois sections de --by-state."""
    jour = lambda v: "-" if v is None else f"{v:.0f}"
    sortie = [t("state_time_header", count=len(sortis)),
              t("state_time_columns"),
              "|---|---|---|---|---|---|"]
    for r in stats_par_etat(sortis, etats):
        part = "-" if r["part"] is None else t("percent", value=f"{100 * r['part']:.1f}")
        sortie.append(f"| {r['etat']} | {r['tickets']} | {r['total']} | {part} | {jour(r['p50'])} | {jour(r['p85'])} |")
    sortie.append(t("state_time_total", total=sum(r['jours'] for r in sortis)))
    groupes = [(t("group_longest"), ech["longs"]), (t("group_near_median"), ech["proches"]),
               (t("group_still_in"), anciens)]
    sortie += [t("detail_header"),
               t("detail_columns", states=" | ".join(etats)), "|" + "---|" * (len(etats) + 3)]
    for groupe, lignes in groupes:
        for r in lignes:
            total = r.get("cumul", r["jours"])         # plus anciens : visites précédentes comprises
            sortie.append(f"| {r['cle']} | {groupe} | {total} | "
                          + " | ".join(str(r["par_etat"][e]) if e in r["par_etat"] else "-" for e in etats) + " |")
    sortie.append(t("detail_note"))
    par_ticket, repere = sorties_groupees(sortis, ech["longs"])
    sortie += [t("grouped_header", count=len(par_ticket)),
               t("grouped_columns"), "|---|---|---|"]
    sortie += [f"| {r['cle']} | {r['sortie']} | {r['autres']} |" for r in par_ticket]
    sortie.append(t("grouped_reference", days=repere['jours'], p50=f"{repere['p50']:.0f}", p85=f"{repere['p85']:.0f}",
                    max=repere['max'], date=repere['date_max']))
    return sortie


def jours_retenus(jours_distincts: int) -> int:
    """Nombre de jours les plus chargés : 20 % des jours distincts, arrondi au-dessus, au moins un (l'arrondi à 9
    décimales évite qu'un produit comme 0.2 * 15 en virgule flottante fasse monter d'un jour)."""
    return max(1, math.ceil(round(PART_JOURS_CHARGES * jours_distincts, 9)))


def paques(annee: int) -> dt.date:
    """Dimanche de Pâques (calendrier grégorien, algorithme de Meeus, Jones et Butcher)."""
    a, b, c = annee % 19, annee // 100, annee % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mois, jour = divmod(h + l - 7 * m + 114, 31)
    return dt.date(annee, mois, jour + 1)


def jours_feries_france(annee: int) -> set[dt.date]:
    """Les onze jours fériés nationaux de la France métropolitaine (liste en dur, aucune dépendance) : 1er janvier,
    lundi de Pâques, 1er mai, 8 mai, Ascension, lundi de Pentecôte, 14 juillet, 15 août, Toussaint, 11 novembre, Noël.
    Les jours propres à l'Alsace-Moselle (Vendredi saint, 26 décembre) n'y sont pas."""
    p = paques(annee)
    jour = dt.timedelta
    return {dt.date(annee, 1, 1), p + jour(days=1), dt.date(annee, 5, 1), dt.date(annee, 5, 8), p + jour(days=39),
            p + jour(days=50), dt.date(annee, 7, 14), dt.date(annee, 8, 15), dt.date(annee, 11, 1),
            dt.date(annee, 11, 11), dt.date(annee, 12, 25)}


def jours_ouvres(debut: dt.date, fin: dt.date) -> list[dt.date]:
    """Jours du lundi au vendredi entre deux dates incluses, jours fériés français retirés."""
    feries = set().union(*(jours_feries_france(a) for a in range(debut.year, fin.year + 1)))
    return [debut + dt.timedelta(days=i) for i in range((fin - debut).days + 1)
            if (debut + dt.timedelta(days=i)).weekday() < 5 and (debut + dt.timedelta(days=i)) not in feries]


def tirages_au_hasard(passages_: int, jours: int, graine: int, projet: str, tirages: int = TIRAGES) -> list[np.ndarray]:
    """Comptes par jour de chaque tirage : `passages_` passages tombant au hasard (avec remise, de façon uniforme) sur
    `jours` jours, `tirages` fois. Même nombre de passages et même nombre de jours que le réel. La graine dépend du
    projet : le résultat d'un projet ne dépend ni de l'ordre ni de la présence des autres. Les deux mesures (concentration
    et jours actifs) lisent les mêmes tirages."""
    if jours < 1:
        raise ValueError("aucun jour ouvré dans la période")
    rng = np.random.default_rng([graine, zlib.crc32(projet.encode("utf-8"))])
    return [np.bincount(tirage, minlength=jours) for tirage in rng.integers(0, jours, size=(tirages, passages_))]


def reference_hasard(passages_: int, jours: int, graine: int, projet: str, tirages: int = TIRAGES) -> tuple[float, float]:
    """(moyenne, 95e centile) de la part des passages sur les 20 % de jours les plus chargés si `passages_` passages
    tombaient au hasard sur `jours` jours : même règle que la part observée, appliquée aux jours distincts de chaque
    tirage (c'est la concentration à jours actifs égaux : le nombre de jours distincts du tirage est le sien)."""
    parts = []
    for comptes in tirages_au_hasard(passages_, jours, graine, projet, tirages):
        charges = np.sort(comptes[comptes > 0])[::-1]
        parts.append(charges[:jours_retenus(len(charges))].sum() / passages_)
    return float(np.mean(parts)), float(np.percentile(parts, 95))


def reference_jours_actifs(passages_: int, jours: int, graine: int, projet: str, tirages: int = TIRAGES) -> tuple[float, float]:
    """(moyenne, 5e centile) du nombre de jours distincts où tombent `passages_` passages tirés au hasard sur `jours`
    jours : mesure non conditionnelle, sans fixer le nombre de jours actifs au réel."""
    distincts = [int((comptes > 0).sum()) for comptes in tirages_au_hasard(passages_, jours, graine, projet, tirages)]
    return float(np.mean(distincts)), float(np.percentile(distincts, 5))


def moins_de_jours_actifs(jours_observes: int, centile_5: float) -> bool:
    """Nombre de jours distincts observé strictement sous le 5e centile des tirages (tolérance d'arrondi)."""
    return jours_observes < centile_5 - 1e-12


def au_dessus_du_hasard(part: float, centile_95: float) -> bool:
    """Part observée strictement au-dessus du 95e centile des tirages (la tolérance écarte le bruit d'arrondi)."""
    return part > centile_95 + 1e-12


def debuts_par_projet(sortis: list[dict], minimum: int) -> tuple[list[dict], dict]:
    """Par projet : passages, jours distincts, part des passages sur les 20 % de jours les plus chargés, P50 de
    l'attente. Seuls les projets d'au moins `minimum` passages sont listés, triés par passages décroissants puis par
    projet. Retourne aussi les totaux, dont ce qui est sous le seuil."""
    par_projet: dict[str, list] = {}
    for r in sortis:
        par_projet.setdefault(r["projet"], []).extend(r["passages"])
    lignes, sous_seuil = [], []
    for projet, liste in par_projet.items():
        if not liste:
            continue
        if len(liste) < minimum:
            sous_seuil.append(projet)
            continue
        par_jour = sorted(Counter(date for date, _ in liste).values(), reverse=True)
        retenus = jours_retenus(len(par_jour))
        lignes.append({"projet": projet or SANS_PROJET, "passages": len(liste), "jours": len(par_jour),
                       "retenus": retenus, "part": sum(par_jour[:retenus]) / len(liste),
                       "p50": float(np.percentile([attente for _, attente in liste], 50))})
    lignes.sort(key=lambda r: (-r["passages"], r["projet"]))
    total = {"passages": sum(len(r["passages"]) for r in sortis), "tickets": sum(1 for r in sortis if r["passages"]),
             "sous_seuil": len(sous_seuil), "passages_sous_seuil": sum(len(par_projet[p]) for p in sous_seuil)}
    return lignes, total


def affichage_debuts(sortis: list[dict], minimum: int, debut: dt.date, fin: dt.date, graine: int, t: Messages) -> list[str]:
    lignes, total = debuts_par_projet(sortis, minimum)
    ouvres = jours_ouvres(debut, fin)
    ouvres_set = set(ouvres)
    hors = sum(1 for r in sortis for date, _ in r["passages"] if date not in ouvres_set)
    sortie = [t("starts_header", waiting=ETAT_ATTENTE, start=ETAT_DEBUT),
              t("starts_summary", passages=total['passages'], tickets=total['tickets'], minimum=minimum,
                below=total['sous_seuil'], below_passages=total['passages_sous_seuil'])]
    if not lignes:
        return sortie + [t("starts_none")]
    pct = lambda v: t("percent", value=f"{v:.1f}")
    sortie += [t("starts_columns"), "|" + "---|" * 13]
    for r in lignes:
        nom = t('no_project') if r['projet'] == SANS_PROJET else r['projet']
        if not ouvres:                                  # période sans jour ouvré : aucune référence
            sortie.append(f"| {nom} | {r['passages']} | {r['jours']} | {r['retenus']} | {pct(100 * r['part'])} | "
                          + " | ".join(["—"] * 7) + f" | {r['p50']:.0f} |")
            continue
        moyenne, centile_95 = reference_hasard(r["passages"], len(ouvres), graine, r["projet"])
        jours_attendus, centile_5 = reference_jours_actifs(r["passages"], len(ouvres), graine, r["projet"])
        concentre = t("starts_above_yes") if au_dessus_du_hasard(r["part"], centile_95) else t("starts_above_no")
        moins = t("starts_above_yes") if moins_de_jours_actifs(r["jours"], centile_5) else t("starts_above_no")
        sortie.append(f"| {nom} | {r['passages']} | {r['jours']} | {r['retenus']} | {pct(100 * r['part'])} | "
                      f"{pct(100 * moyenne)} | {pct(100 * centile_95)} | {concentre} | "
                      f"{jours_attendus:.1f} | {centile_5:.1f} | {r['jours'] / jours_attendus:.2f} | {moins} | {r['p50']:.0f} |")
    sortie.append(t("starts_wait_note", waiting=ETAT_ATTENTE))
    sortie.append(t("starts_expected_note", days=len(ouvres), start=debut, end=fin, draws=TIRAGES, seed=graine, outside=hors))
    return sortie


def lot_fermetures(tickets: list[dict], settings: dict, premiere: dt.date, derniere: dt.date, t: Messages) -> dict:
    """Clés (en majuscules) des tickets résolus dans une fermeture en lot, et nombre de tickets livrés sans heure de
    résolution. Même population que flux_jira.cmd_calcul : tickets résolus dans les semaines analysées, motifs de
    clôture exclus retirés ; même règle que la section « Fermetures groupées » (flux_jira.tickets_en_fermeture_groupee)."""
    seuil = settings.get("seuil_fermetures_groupees")
    if not isinstance(seuil, int) or isinstance(seuil, bool) or seuil < 2:
        sys.exit(t("batch_threshold_invalid"))
    exclus = {m.casefold() for m in settings.get("motifs_exclus") or []}
    motifs = {str(m).casefold() for m in settings.get("motifs_fermetures_groupees") or []}
    livres = [x for x in tickets if x["resolu"] and premiere <= fj.week_start(x["resolu"]) <= derniere
              and x["motif"].casefold() not in exclus]
    en_lot = fj.tickets_en_fermeture_groupee(livres, seuil, motifs)
    return {"cles": {x["cle"].upper() for x in en_lot},
            "sans_heure": sum(1 for x in livres if not x["resolu_a"])}


def ecarter_lots(sortis: list[dict], lot: dict) -> tuple[list[dict], dict]:
    """(sortis sans les tickets en lot, comptes écartés : tickets et passages de ETAT_ATTENTE à ETAT_DEBUT)."""
    gardes = [r for r in sortis if r["cle"].upper() not in lot["cles"]]
    ecartes = [r for r in sortis if r["cle"].upper() in lot["cles"]]
    return gardes, {"tickets": len(ecartes), "passages": sum(len(r["passages"]) for r in ecartes)}


def preparer(args: argparse.Namespace, t: Messages) -> dict:
    """Lit les exports et le cache, applique les mêmes filtres que flux_jira.cmd_calcul, calcule les chronologies."""
    settings = fj.config()
    tickets, found, _, _ = fj.read_exports(args.export, settings)
    if not found["resolu"]:
        sys.exit(t("resolved_column_missing"))
    if not found.get("cle"):
        sys.exit(t("key_column_missing"))
    perimetre = fj.lire_perimetre(args.perimetre)
    if perimetre:
        tickets = [t for t in tickets if t["projet"] in set(perimetre)]
        if not tickets:
            sys.exit(t("scope_no_ticket"))
    tickets, ecartes = fj.ecarter(tickets, settings, True)
    if args.types:
        types = {k.strip() for k in args.types.split(",")}
        tickets = [t for t in tickets if t["type"] in types]
    today = dt.date.fromisoformat(args.aujourdhui) if args.aujourdhui else dt.date.today()
    last_week = fj.week_start(today) - dt.timedelta(days=7)
    first_week = last_week - dt.timedelta(weeks=args.semaines - 1)
    resolus = [t["resolu"] for t in tickets if t["resolu"]]
    if resolus:
        first_week = max(first_week, fj.week_start(min(resolus)))
    histoires = fj.charger_historique(Path(args.historique).expanduser() if args.historique else fj.HISTORIQUE_DEFAUT,
                                  fuseau=fj.fuseau_des_reglages(settings, fj.T_FR))
    segment_de, noms_segments = commun.table_segments(settings)
    if args.segment not in noms_segments:
        sys.exit(t("segment_not_computed", segment=nom_segment(args.segment, t),
                   segments=", ".join(nom_segment(n, t) for n in noms_segments)))
    lot = lot_fermetures(tickets, settings, first_week, last_week, t) if args.exclure_lots else None
    periodes = {t["cle"].upper(): fj.chronologie(t, histoires[t["cle"].upper()], today)
                for t in tickets if t["cle"] and t["cle"].upper() in histoires}
    etats = {nom: list(liste or []) for nom, liste in (settings.get("segments") or commun.SEGMENTS_PAR_DEFAUT).items()}
    return {"tickets": tickets, "periodes": periodes, "segment_de": segment_de, "etats": etats,
            "personnalises": bool(settings.get("segments")), "ecartes": ecartes, "today": today, "lot": lot,
            "debut": first_week, "fin": last_week + dt.timedelta(days=6)}


OPTIONS_RENOMMEES = {**cfg.OPTIONS_COMMUNES, "--graine": "--seed", "--plus-longs": "--longest", "--proches": "--near-median",
                     "--anciens": "--oldest", "--par-etat": "--by-state", "--debuts": "--starts", "--min-passages": "--min-passes"}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Échantillon de tickets d'un segment (clés et états seulement)")
    parser.add_argument("export", nargs="+", help="un ou plusieurs exports CSV (comme flux_jira.py compute)")
    parser.add_argument("--segment", default="revue_verification", help="segment de flux.yaml (défaut revue_verification)")
    parser.add_argument("--today", dest="aujourdhui", help="date du calcul AAAA-MM-JJ (défaut : aujourd'hui) ; la période en dépend")
    parser.add_argument("--seed", dest="graine", type=int, default=42, help="graine du tirage au hasard (défaut 42)")
    parser.add_argument("--longest", dest="plus_longs", type=int, default=6, help="nombre de tickets les plus longs (défaut 6)")
    parser.add_argument("--near-median", dest="proches", type=int, default=4, help="nombre de tickets tirés près de la médiane (défaut 4)")
    parser.add_argument("--oldest", dest="anciens", type=int, default=3, help="nombre de tickets les plus anciens encore dans le segment")
    parser.add_argument("--by-state", dest="par_etat", action="store_true",
                        help="ajoute le temps par état du segment, le détail de l'échantillon et les sorties groupées")
    parser.add_argument("--starts", dest="debuts", action="store_true",
                        help="ajoute les passages de Ready for Verification à Verification - Ongoing, par projet")
    parser.add_argument("--min-passes", dest="min_passages", type=int, default=20, help="passages minimum d'un projet pour --starts (défaut 20)")
    parser.add_argument("--exclude-batch-closures", dest="exclure_lots", action="store_true",
                        help="retire de la population les tickets sortis du segment dans une fermeture en lot "
                             "(règle de « Fermetures groupées » de flux_jira.py)")
    parser.add_argument("--weeks", dest="semaines", type=int, default=26, help="semaines complètes analysées (défaut 26)")
    parser.add_argument("--scope", dest="perimetre", help="projets du périmètre (clés séparées par des virgules) ou « tous »")
    parser.add_argument("--types", help="types de tickets retenus, séparés par des virgules")
    parser.add_argument("--history", dest="historique", help="cache de l'historique (défaut Flux-Lab/historique/transitions.json)")
    add_language_option(parser)
    args = parser.parse_args(cfg.refuse_old_options(sys.argv[1:] if argv is None else argv, OPTIONS_RENOMMEES))
    args.segment = {v: k for k, v in cfg.SEGMENTS.items()}.get(args.segment, args.segment)   # nom anglais -> nom interne

    t = Messages(CATALOGS, args.language)
    p = preparer(args, t)
    etats_segment = p["etats"][args.segment]
    canon = {e.strip().casefold(): e for e in etats_segment}
    sortis, dedans = analyser(p["tickets"], p["periodes"], p["segment_de"], args.segment, p["debut"], p["fin"], canon)
    sans_historique = sum(1 for t in p["tickets"] if t["cle"].upper() not in p["periodes"])
    lots = None
    if p["lot"] is not None:
        sortis, lots = ecarter_lots(sortis, p["lot"])

    print(t("title", segment=nom_segment(args.segment, t)))
    print(t("period", start=p['debut'], end=p['fin'], weeks=args.semaines, today=p['today']))
    if lots is not None:
        print(t("batch_discarded", tickets=lots["tickets"], passages=lots["passages"], waiting=ETAT_ATTENTE, start=ETAT_DEBUT))
        if p["lot"]["sans_heure"]:
            print(t("batch_no_time", count=p["lot"]["sans_heure"]))
    print(t("key_and_states_only"))
    print(t("states_header", setting=t("setting_custom") if p['personnalises'] else t("setting_default")))
    for etat in etats_segment:
        print(f"- {etat}")
    autres = ", ".join(f"{nom_segment(nom, t)} ({len(liste)})" for nom, liste in p["etats"].items() if nom != args.segment)
    print(t("other_segments", segments=autres))
    print(t("population_discarded", count=len(p['tickets']), discarded=p['ecartes']['total'], without_history=sans_historique)
          if p["ecartes"] else t("population", count=len(p['tickets']), without_history=sans_historique))
    if not sortis:
        print(t("nothing_left"))
        return
    jours = [r["jours"] for r in sortis]
    ech = echantillonner(sortis, args.plus_longs, args.proches, args.graine)
    bas, haut = ech["fenetre"]
    print(t("left_summary", count=len(sortis), p50=f"{np.percentile(jours, 50):.0f}", p85=f"{np.percentile(jours, 85):.0f}",
            mean=f"{np.mean(jours):.1f}", max=max(jours)))
    print(t("visits_per_ticket", one=sum(1 for r in sortis if r['visites'] == 1), many=sum(1 for r in sortis if r['visites'] >= 2)))
    print(t("longest_header", count=len(ech['longs'])))
    print("\n".join(tableau(ech["longs"], COLONNES_SORTIS, t)))
    print(t("near_median_header", count=len(ech['proches']), seed=args.graine))
    print(t("near_median_window", low=f"{bas:.1f}", high=f"{haut:.1f}", candidates=ech['candidats']))
    if len(ech["proches"]) < args.proches:
        print(t("near_median_shortage", found=len(ech['proches']), asked=args.proches))
    print("\n".join(tableau(ech["proches"], COLONNES_SORTIS, t)))
    anciens = sorted(dedans, key=lambda r: (-r["jours"], r["cle"]))[:args.anciens]
    print(t("oldest_header", count=len(anciens), total=len(dedans)))
    print("\n".join(tableau(anciens, COLONNES_DEDANS, t)))
    if args.par_etat:
        print("\n".join(affichage_par_etat(sortis, ech, anciens, etats_segment, t)))
    if args.debuts:
        manquants = [e for e in (ETAT_ATTENTE, ETAT_DEBUT) if e.casefold() not in canon]
        if manquants:
            sys.exit(t("starts_states_outside", segment=nom_segment(args.segment, t), states=", ".join(manquants)))
        print("\n".join(affichage_debuts(sortis, args.min_passages, p["debut"], p["fin"], args.graine, t)))


if __name__ == "__main__":
    main()
