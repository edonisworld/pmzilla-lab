"""
Contrôle du registre des codes de sortie des scripts de fin (tools/finish_codes.yaml), partagé par test_registre_codes.py et, plus tard, par
les suites qui voudront relire le registre.

Extraction des codes d'un script shell (documentée ici, une seule règle) :
  - on lit le texte du script ligne à ligne et on écarte les lignes entièrement en commentaire (premier caractère non blanc : « # ») ;
  - « refus <n> » rend le code <n> quand <n> est un entier écrit en toutes lettres de chiffres, suivi d'un espace puis d'un guillemet (« refus 14 "… »)
    ou d'une barre de continuation (« refus 14 \\ ») : la forme des appels de la fonction refus() des scripts. L'aide imprimée et les
    en-têtes écrivent « refus 3, 4, 19 » ou « (refus 14) » : sans guillemet derrière le nombre, ils ne comptent pas ;
  - « exit <n> » rend le code <n> (« exit 0 », « trap 'exit 130' INT ») ;
  - une sortie CALCULÉE (« exit "$code" », « exit $? »,« refus "$code" … », « sortir "$…" » : le mot exit, refus ou sortir suivi d'un « $ » ; ou
    une ligne qui commence par « exec » suivi d'une commande : l'enveloppe de la fin unique, retirée par B9, passait la main au train, dont le code est le sien,
    finish-single-b7-b9 D7) n'est pas extraite comme code, et le test la REFUSE tant que le registre ne la liste pas dans « sorties_dynamiques »
    (script, motif : un morceau de la ligne, raison). Aujourd'hui : la fonction refus() des scripts (le code est son premier argument, un
    littéral à chaque appel, extrait) et le « exec » de l'enveloppe. Un code « utilise » qu'un script ne rend que par une telle sortie déclarée
    porte « rendu_par: transmission ». Une redirection (« exec 3>&1 », « exec > fichier ») n'est pas une sortie : elle ne passe pas la main ;
  - un texte d'aide qui contiendrait « exit <n> » ou « refus <n> "… » en clair serait pris pour un code : aucun script de fin n'en contient.

Limites de l'extraction (connues, non couvertes) :
  - modules sourcés non suivis : tools/finish_lock.sh, tools/finish_merge.sh et tools/finish_env.sh sont sourcés par le
    script de fin (ou par d'autres outils) mais seul le texte du fichier déclaré dans « scripts » est lu ; ces modules n'ont aujourd'hui aucun exit au niveau principal
    (leurs fonctions rendent par return) ; un exit ou un refus ajouté à l'un d'eux ne serait pas vu ;
  - une chaîne passée à « sh -c » ou « bash -c » (le texte d'un exit y est lu comme n'importe quelle ligne, mais une valeur composée à
    l'exécution ne l'est pas) ;
  - un commentaire en fin de ligne (« exit 4 # exit 99 ») : la ligne entière compte, le « exit 99 » du commentaire serait pris pour un code ;
  - un code rendu par un sous-processus (un script lancé dont le code est transmis sans « exit ») : à déclarer dans « sorties_dynamiques ».
"""
import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml

REGISTRE = "tools/finish_codes.yaml"
ORIGINES = {"utilise", "reserve", "jamais_rendu"}
RENDUS_PAR = {"transmission"}
SIGNAUX = {129, 130, 143}
# Codes que plusieurs scripts déclarent sans que ce soit un doublon : le succès, les trois signaux (tous les scripts), et le 20 (npm pour
# finish_branch.sh, usage pour finish_worktree.sh : ces deux scripts seulement, jusqu'à B9 qui les retire). Valeur : None (tous les scripts) ou
# l'ensemble des scripts permis.
PARTAGES = {
    0: None,
    129: None,
    130: None,
    143: None,
    20: {"finish_branch", "finish_worktree"},
}

MOTIF_REFUS = re.compile(r"""\brefus\s+(\d+)(?=\s+["'\\])""")
MOTIF_EXIT = re.compile(r"\bexit\s+(\d+)\b")
MOTIF_CALCULE = re.compile(r"""\b(?:exit|refus|sortir)\s+["']?\$""")
MOTIF_EXEC = re.compile(r"^\s*exec\s+[A-Za-z_/.]")


def extraire_codes(texte: str) -> set:
    codes = set()
    for ligne in texte.splitlines():
        if ligne.lstrip().startswith("#"):
            continue
        codes.update(int(m.group(1)) for m in MOTIF_REFUS.finditer(ligne))
        codes.update(int(m.group(1)) for m in MOTIF_EXIT.finditer(ligne))
    return codes


def sorties_calculees(texte: str) -> list:
    """Lignes (sans leur indentation) qui rendent un code calculé : exit, refus ou sortir suivi d'un « $ », ou « exec » suivi d'une commande."""
    lignes = []
    for ligne in texte.splitlines():
        if ligne.lstrip().startswith("#"):
            continue
        if MOTIF_CALCULE.search(ligne) or MOTIF_EXEC.search(ligne):
            lignes.append(ligne.strip())
    return lignes


def charger(racine: Path) -> dict:
    """Le registre. Lève FileNotFoundError (absent) ou ValueError (illisible, ou pas un dictionnaire)."""
    texte = (Path(racine) / REGISTRE).read_text(encoding="utf-8")
    try:
        donnees = yaml.safe_load(texte)
    except yaml.YAMLError as erreur:
        raise ValueError(f"YAML illisible : {type(erreur).__name__}") from None
    if not isinstance(donnees, dict):
        raise ValueError("le registre n'est pas un dictionnaire")
    return donnees


def _entier(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _change_ouvert(racine: Path, change: str) -> bool:
    return change != "archive" and (Path(racine) / "openspec" / "changes" / change).is_dir()


def _forme(registre: dict) -> tuple:
    """(messages, entrées valides) : champs, origines, bornes. Une entrée invalide n'est pas contrôlée plus loin."""
    messages, valides = [], []
    scripts = registre.get("scripts")
    if not isinstance(scripts, dict) or not scripts:
        return ["scripts : section absente ou vide"], []
    for nom, d in scripts.items():
        if not isinstance(d, dict) or not isinstance(d.get("fichier"), str):
            messages.append(f"scripts : {nom} sans champ fichier")
    codes = registre.get("codes")
    if not isinstance(codes, list):
        return messages + ["codes : section absente ou pas une liste"], []
    for i, c in enumerate(codes, start=1):
        if not isinstance(c, dict):
            messages.append(f"codes : entrée {i} pas un dictionnaire")
            continue
        script, code, origine = c.get("script"), c.get("code"), c.get("origine")
        nom = f"{script} : code {code}"
        erreurs = []
        if script not in scripts:
            erreurs.append(f"{nom} : script inconnu (déclaré dans scripts : {', '.join(scripts)})")
        if not _entier(code) or not 0 <= code <= 255:
            erreurs.append(f"{nom} : code hors des bornes 0 à 255")
        if not isinstance(c.get("sens"), str) or not c["sens"].strip():
            erreurs.append(f"{nom} : sens absent ou vide")
        if origine not in ORIGINES:
            erreurs.append(f"{nom} : origine {origine!r} inconnue (attendu : {', '.join(sorted(ORIGINES))})")
        elif origine == "reserve":
            if not (isinstance(c.get("change"), str) and c["change"] and isinstance(c.get("tache"), str) and c["tache"]):
                erreurs.append(f"{nom} : un code réservé nomme son change et sa tache (champs change et tache)")
        elif "change" in c or "tache" in c:
            erreurs.append(f"{nom} : origine {origine} sans champ change ni tache (seule la réservation les porte)")
        if "rendu_par" in c:
            if origine != "utilise":
                erreurs.append(f"{nom} : rendu_par réservé aux codes utilise (origine {origine})")
            elif c["rendu_par"] not in RENDUS_PAR:
                erreurs.append(f"{nom} : rendu_par {c['rendu_par']!r} inconnu (attendu : {', '.join(sorted(RENDUS_PAR))})")
        messages.extend(erreurs)
        if not erreurs:
            valides.append(c)
    return messages, valides


def _lire_scripts(racine: Path, registre: dict) -> dict:
    """nom du script -> texte, ou None quand le fichier est absent."""
    textes = {}
    for nom, d in registre["scripts"].items():
        if isinstance(d, dict) and isinstance(d.get("fichier"), str):
            chemin = Path(racine) / d["fichier"]
            textes[nom] = chemin.read_text(encoding="utf-8") if chemin.is_file() else None
    return textes


def _reservations(racine: Path, valides: list, textes: dict) -> list:
    messages, vus = [], set()
    changes = Path(racine) / "openspec" / "changes"
    for c in valides:
        if c["origine"] != "reserve":
            continue
        change, tache, script = c["change"], c["tache"], c["script"]
        rendu = textes.get(script) is not None and c["code"] in extraire_codes(textes[script])
        if not _change_ouvert(racine, change):
            archives = sorted(p.name for p in (changes / "archive").glob(f"*-{change}") if p.is_dir()) if (changes / "archive").is_dir() else []
            if archives and rendu:
                messages.append(f"change {change} archivé ({archives[-1]}) : la réservation du code {c['code']} de {script} est périmée, "
                                f"le script rend ce code : passer à utilise (et retirer change et tache)")
            elif archives:
                messages.append(f"change {change} archivé ({archives[-1]}) : la réservation du code {c['code']} de {script} est périmée, "
                                f"le script ne rend pas ce code : passer à jamais_rendu, ou retirer l'entrée")
            else:
                messages.append(f"change {change} absent de openspec/changes : la réservation du code {c['code']} de {script} n'a plus de change")
            continue
        if (change, tache) in vus:
            continue
        vus.add((change, tache))
        fichier = changes / change / "tasks.md"
        texte = fichier.read_text(encoding="utf-8") if fichier.is_file() else ""
        if not re.search(rf"^- \[[ xX]\] {re.escape(tache)}(?=\s)", texte, re.M):
            messages.append(f"change {change} : tâche {tache} absente de tasks.md (réservation du code {c['code']} de {script})")
    return messages


def _usage(racine: Path, registre: dict, valides: list, textes: dict, infos: list) -> list:
    messages = []
    par_script = defaultdict(dict)
    for c in valides:
        par_script[c["script"]].setdefault(c["code"], c)
    dynamiques = _declarations_dynamiques(registre)[0]
    for nom, d in registre["scripts"].items():
        if not isinstance(d, dict) or not isinstance(d.get("fichier"), str):
            continue
        if textes[nom] is None:
            if not d.get("facultatif"):
                messages.append(f"{nom} : {d['fichier']} absent (script obligatoire du registre)")
            continue
        rendus = extraire_codes(textes[nom])
        declares = par_script.get(nom, {})
        for code in sorted(rendus - set(declares)):
            messages.append(f"{nom} : code {code} rendu par {d['fichier']} et non déclaré dans {REGISTRE}")
        for code, c in sorted(declares.items()):
            if c["origine"] == "utilise" and code not in rendus:
                if c.get("rendu_par") == "transmission" and dynamiques.get(nom):
                    continue
                messages.append(f"{nom} : code {code} déclaré utilise, mais {d['fichier']} ne le rend pas (retirer l'entrée, la passer en reserve ou en "
                                f"jamais_rendu, ou déclarer rendu_par: transmission quand une sortie calculée le rend)")
            elif c["origine"] == "reserve" and code in rendus:
                if _change_ouvert(racine, c["change"]):
                    infos.append(f"code {code} de {nom} réservé par {c['change']} (change ouvert) : déjà rendu par {d['fichier']}, accepté ; "
                                 f"à l'archivage du change, passer l'entrée à utilise")
                # change archivé ou absent : déjà signalé par _reservations
            elif c["origine"] == "jamais_rendu" and code in rendus:
                messages.append(f"{nom} : code {code} déclaré jamais rendu, mais {d['fichier']} le rend déjà : passer l'entrée à utilise")
    return messages


def _declarations_dynamiques(registre: dict) -> tuple:
    """(déclarations valides par script, messages de forme) de la rubrique « sorties_dynamiques »."""
    messages, par_script = [], defaultdict(list)
    liste = registre.get("sorties_dynamiques") or []
    if not isinstance(liste, list):
        return par_script, ["sorties_dynamiques : pas une liste"]
    scripts = registre.get("scripts") or {}
    for i, d in enumerate(liste, start=1):
        if not isinstance(d, dict):
            messages.append(f"sorties_dynamiques : entrée {i} pas un dictionnaire")
            continue
        if d.get("script") not in scripts:
            messages.append(f"sorties_dynamiques : entrée {i} : script {d.get('script')!r} inconnu")
        elif not (isinstance(d.get("motif"), str) and d["motif"].strip()):
            messages.append(f"sorties_dynamiques : entrée {i} sans motif")
        elif not (isinstance(d.get("raison"), str) and d["raison"].strip()):
            messages.append(f"sorties_dynamiques : entrée {i} ({d['script']}) sans raison")
        else:
            par_script[d["script"]].append(d)
    return par_script, messages


def _dynamiques(registre: dict, valides: list, textes: dict) -> list:
    par_script, messages = _declarations_dynamiques(registre)
    for nom, d in registre["scripts"].items():
        texte = textes.get(nom)
        if texte is None:
            continue
        lignes = sorties_calculees(texte)
        for ligne in lignes:
            if not any(decl["motif"] in ligne for decl in par_script.get(nom, [])):
                messages.append(f"{nom} : sortie calculée non déclarée dans sorties_dynamiques : {ligne}")
        for decl in par_script.get(nom, []):
            if not any(decl["motif"] in ligne for ligne in lignes):
                messages.append(f"{nom} : sortie dynamique déclarée {decl['motif']!r} absente de {d['fichier']} (retirer l'entrée de sorties_dynamiques)")
    for c in valides:
        if c.get("rendu_par") and textes.get(c["script"]) is not None and not par_script.get(c["script"]):
            messages.append(f"{c['script']} : code {c['code']} : rendu_par {c['rendu_par']} sans sortie calculée déclarée dans sorties_dynamiques")
    return messages


def analyser(racine: Path) -> tuple:
    """(écarts, informations) du registre pour l'arbre `racine`. Les informations n'échouent pas (code réservé déjà rendu)."""
    racine = Path(racine)
    infos = []
    try:
        registre = charger(racine)
    except FileNotFoundError:
        return [f"{REGISTRE} absent"], infos
    except (ValueError, OSError, UnicodeDecodeError) as erreur:
        return [f"{REGISTRE} illisible : {erreur}"], infos
    messages, valides = _forme(registre)
    if "scripts" not in registre or not isinstance(registre["scripts"], dict):
        return messages, infos
    for (script, code), n in sorted(Counter((c["script"], c["code"]) for c in valides).items()):
        if n > 1:
            messages.append(f"{script} : code {code} déclaré {n} fois : un code, deux sens (un seul sens par code)")
    par_code = defaultdict(set)
    for c in valides:
        par_code[c["code"]].add(c["script"])
    for code, scripts in sorted(par_code.items()):
        permis = PARTAGES.get(code, set())
        if len(scripts) > 1 and (code not in PARTAGES or (permis is not None and not scripts <= permis)):
            decrits = ", ".join(f"{k} ({' et '.join(sorted(v))} seulement)" if v else str(k) for k, v in sorted(PARTAGES.items()))
            messages.append(f"code {code} déclaré par {' et '.join(sorted(scripts))} : un code, un script (partages permis : {decrits})")
    textes = _lire_scripts(racine, registre)
    messages.extend(_reservations(racine, valides, textes))
    messages.extend(_usage(racine, registre, valides, textes, infos))
    messages.extend(_dynamiques(registre, valides, textes))
    return messages, infos


def ecarts(racine: Path) -> list:
    """Liste des écarts du registre (vide : tout concorde) pour l'arbre `racine`."""
    return analyser(racine)[0]
