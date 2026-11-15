#!/bin/bash
# PMZilla Lab : essai du crochet PreToolUse (change deny-rules-review, D9, tâche 1.2 ; idée 399) : Claude Code lit-il encore le champ
# additionalContext d'un crochet PreToolUse ? Ce n'est pas le canal documenté : une mise à jour de Claude Code peut le perdre sans bruit.
#
#   bash tools/essai_crochet_pretooluse.sh      à lancer dans le Terminal, après chaque mise à jour de Claude Code (deux sessions `claude -p`)
#
# Il crée un dossier jetable (mktemp, hors dépôt), y pose un .claude/settings.json de test avec un crochet, puis lance deux sessions non
# interactives courtes qui exécutent `echo essai-crochet` par l'outil Bash : un témoin (crochet PostToolUse, canal documenté : il valide la
# méthode) puis l'essai (crochet PreToolUse). Chaque crochet renvoie un identifiant CANARI-<hasard> et laisse un repère qui prouve qu'il a
# tourné ; la session doit recopier tout identifiant CANARI- reçu, ou répondre AUCUN. Verdict par passage : « lu » (crochet lancé et canari
# dans la réponse), « non lu » (crochet lancé, canari absent), « invalide » (crochet pas lancé). Aucun fichier du dépôt ni réglage du lab.
#
# Fichier d'état (lu par `uv run tools/doctor.py`, contrôle pretooluse) : $PMZILLA_LAB_DATA/essai-crochet-pretooluse.json, par défaut
# ~/.pmzilla-lab/, droits du propriétaire seul. Il porte la version de Claude Code, la date et le verdict. Il est écrit seulement quand le
# témoin est « lu » : verdict « lu » si l'essai l'est aussi (forme B, PreToolUse, possible), verdict « non lu » sinon (retour à la forme A,
# changement de l'entrée seule, D9). Un essai invalide, ou un témoin non lu (méthode non validée), n'écrit rien.
#
# Coût : deux sessions `claude -p` d'un tour, quelques centimes. Refusé dans une session Claude Code (variable CLAUDECODE, code 3).
# Variables : PMZILLA_LAB_DATA (dossier de données), PMZILLA_LAB_TODAY (AAAA-MM-JJ, pour les tests).
# Codes : 0 essai conclu (quel que soit le verdict) ; 1 essai invalide (crochet pas lancé, claude introuvable ou sans version) ;
# 3 lancé dans une session Claude Code.
set -u

if [ -n "${CLAUDECODE:-}" ]; then
  echo "essai-crochet-pretooluse : refusé dans une session Claude Code (deux sessions payantes) ; à lancer dans le Terminal."; exit 3
fi
command -v claude >/dev/null 2>&1 || { echo "claude introuvable dans le PATH : essai impossible"; exit 1; }
VERSION_SORTIE="$(claude --version 2>/dev/null)"
VERSION_BRUTE="$(printf '%s\n' "$VERSION_SORTIE" | head -1)"
# Comme le doctor : le premier numéro de la forme chiffres et points trouvé dans la sortie (préfixe v toléré).
VERSION="$(printf '%s\n' "$VERSION_SORTIE" | grep -oE '[0-9]+(\.[0-9]+)+' | head -1)"
echo "version de Claude Code : ${VERSION_BRUTE:-inconnue}"
[ -n "$VERSION" ] || { echo "version de Claude Code illisible : essai impossible"; exit 1; }

DONNEES="${PMZILLA_LAB_DATA:-$HOME/.pmzilla-lab}"
ETAT="$DONNEES/essai-crochet-pretooluse.json"
JETABLE="$(mktemp -d "${TMPDIR:-/tmp}/essai-crochet.XXXXXX")" || exit 1
trap '[ -d "$JETABLE" ] && rm -rf "$JETABLE"' EXIT
mkdir -p "$JETABLE/.claude" || exit 1
HASARD="$(LC_ALL=C tr -dc 'A-Z0-9' < /dev/urandom | head -c 6)"
PROMPT="Exécute avec l'outil Bash exactement cette commande : echo essai-crochet. Ensuite, réponds sur une seule ligne : recopie mot pour mot tout identifiant qui commence par CANARI- et que tu as reçu dans un contexte additionnel fourni par un crochet ; si tu n'en as reçu aucun, écris exactement AUCUN."

passage() { # evenement (PreToolUse|PostToolUse) canari
  local evenement=$1 canari=$2 crochet="$JETABLE/crochet-$1.sh" reponse verdict
  rm -f "$JETABLE/repere-$evenement"
  cat > "$crochet" <<EOF
#!/bin/bash
cat > /dev/null
touch "$JETABLE/repere-$evenement"
printf '%s' '{"hookSpecificOutput":{"hookEventName":"$evenement","additionalContext":"$canari"}}'
exit 0
EOF
  chmod 700 "$crochet"
  cat > "$JETABLE/.claude/settings.json" <<EOF
{
  "hooks": {
    "$evenement": [
      {"matcher": "Bash", "hooks": [{"type": "command", "command": "$crochet"}]}
    ]
  }
}
EOF
  reponse="$(cd "$JETABLE" && claude -p "$PROMPT" --allowedTools "Bash(echo essai-crochet)" 2>&1 | tail -5)"
  echo "--- $evenement : réponse de la session (5 dernières lignes)"
  echo "$reponse"
  if [ ! -e "$JETABLE/repere-$evenement" ]; then verdict=invalide
  elif printf '%s' "$reponse" | grep -q -- "$canari"; then verdict=lu
  else verdict="non lu"; fi
  echo "--- $evenement : crochet lancé : $([ -e "$JETABLE/repere-$evenement" ] && echo oui || echo non) ; verdict : $verdict"
  eval "VERDICT_$evenement=\"$verdict\""
}

ecrire_etat() { # verdict : « lu » ou « non lu » ; remplace le fichier d'état d'un coup, droits du propriétaire seul
  local verdict=$1 jour="${PMZILLA_LAB_TODAY:-$(date +%F)}" temporaire
  mkdir -p "$DONNEES" || return 1
  temporaire="$(umask 077; mktemp "$DONNEES/.essai-crochet-pretooluse.XXXXXX")" || return 1
  printf '{"version": 1, "claude_version": "%s", "date": "%s", "verdict": "%s"}\n' "$VERSION" "$jour" "$verdict" > "$temporaire" \
    && chmod 600 "$temporaire" && mv -f "$temporaire" "$ETAT" || { rm -f "$temporaire"; return 1; }
  echo "état enregistré : version $VERSION, $jour, verdict « $verdict »"
}

passage PostToolUse "CANARI-POST-$HASARD"
passage PreToolUse "CANARI-PRE-$HASARD"

echo
echo "témoin PostToolUse : $VERDICT_PostToolUse ; essai PreToolUse : $VERDICT_PreToolUse"
if [ "$VERDICT_PostToolUse" = invalide ] || [ "$VERDICT_PreToolUse" = invalide ]; then
  echo "conclusion : essai invalide (un crochet n'a pas tourné) ; aucun état écrit"; exit 1
fi
if [ "$VERDICT_PostToolUse" != lu ]; then
  echo "conclusion : méthode non validée (le témoin PostToolUse n'est pas lu) ; aucune décision, aucun état écrit"; exit 0
fi
if [ "$VERDICT_PreToolUse" = lu ]; then
  echo "conclusion : additionalContext d'un crochet PreToolUse est lu : forme B (PreToolUse) conforme"
  ecrire_etat "lu" || { echo "état non inscriptible : $ETAT"; exit 1; }
else
  echo "conclusion : additionalContext d'un crochet PreToolUse n'est pas lu : retour à la forme A (PostToolUse), changement de l'entrée seule (D9)"
  ecrire_etat "non lu" || { echo "état non inscriptible : $ETAT"; exit 1; }
fi
exit 0
