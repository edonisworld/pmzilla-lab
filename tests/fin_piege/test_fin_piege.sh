#!/bin/bash
# Test du gabarit du piège de sortie des fichiers de fin (R-148/u14, #577, tools/etapes/modele-piege-fin.sh).
# Un fichier de fin factice est construit depuis le gabarit (dossier des étapes remplacé par un dossier temporaire, corps remplacé par une
# commande factice), lancé dans son propre groupe de processus ; le signal part au groupe entier (kill -s … -- -<pgid>), comme un Ctrl-C.
# Cas : INT, TERM et HUP pendant un sleep (journal : la ligne « interrompu … (code N) », le code de sortie et le bandeau « ===== TERMINÉ »,
# avec 130, 143 ou 129 ; le bandeau est la dernière chose écrite, et la dernière ligne du corps le précède) ; sortie normale (code 0, bandeau
# et en-tête du contrôle final une seule fois au journal) ; tee tué à part (KILL) pendant le corps : SIGPIPE au premier echo, code 141.
# Cas témoin : l'ANCIEN bloc (tests/fin_piege/ancien-bloc.sh, recopié de l'ancien modèle des fichiers de fin) est rouge pour TERM et HUP
# (pas de bandeau au journal) : preuve que la suite détecte la régression. Le mécanisme démontré : en bash non interactif, le tee d'une
# substitution de processus ignore SIGINT (comme toute commande en arrière-plan) ; il meurt par TERM ou HUP (terminal fermé), et le premier
# echo de fin() reçoit alors SIGPIPE. Le cas INT ne prouve donc pas la régression : il valide seulement la nouvelle forme.
# Aucun réseau, aucune notification (osascript remplacé), rien dans ~/PMZilla-Lab/etapes/ : HOME, dossier des étapes et PATH sont temporaires.
# Lancement à la main : bash tests/fin_piege/test_fin_piege.sh
set -u
racine="$(cd "$(dirname "$0")/../.." && pwd)"
modele="$racine/tools/etapes/modele-piege-fin.sh"
ancien="$racine/tests/fin_piege/ancien-bloc.sh"
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home"; mkdir -p "$HOME" "$tmp/etapes" "$tmp/bin"
printf '#!/bin/sh\necho "$@" >> "%s/notifications"\n' "$tmp" > "$tmp/bin/osascript"
chmod +x "$tmp/bin/osascript"
export PATH="$tmp/bin:$PATH"
ok=0; ko=0

verifie() { # description condition-vraie (0 = vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1"; ko=$((ko+1)); fi
}

[ -f "$modele" ]; verifie "le gabarit existe" $?
[ -f "$ancien" ]; verifie "l'ancien bloc (cas témoin) existe" $?
[ "$(grep -c '^ETAPE_DIR=' "$modele")" -eq 1 ]; verifie "le gabarit porte la ligne ETAPE_DIR attendue (remplacée par le test)" $?
[ "$(grep -c '^# ===== CORPS DU FICHIER =====$' "$modele")" -eq 1 ]; verifie "le gabarit porte le marqueur du corps" $?
grep -qF '3>&- 4>&-' "$modele"; verifie "le gabarit documente 3>&- 4>&- pour les commandes du corps" $?
grep -qF 'trap '"'"'code=141; exit 141'"'"' PIPE' "$modele"; verifie "le gabarit piège PIPE (code 141)" $?
grep -qF 'mktemp "${TMPDIR:-/tmp}/fin-controle.XXXXXX"' "$modele"; verifie "le gabarit utilise mktemp avec un modèle portable" $?

construire() { # nom corps : écrit $tmp/<nom>.sh depuis le gabarit, jusqu'au marqueur du corps, puis le corps donné
  local nom=$1 corps=$2
  printf '%s\n' "$corps" > "$tmp/corps.txt"
  sed -e "s|^ETAPE_DIR=.*|ETAPE_DIR=\"$tmp/etapes\"|" -e "s|^ETAPE_NOM=\"[^\"]*\"|ETAPE_NOM=\"$nom\"|" "$modele" \
    | awk -v corps="$tmp/corps.txt" '{ print } /^# ===== CORPS DU FICHIER =====$/ { while ((getline l < corps) > 0) print l; exit }' > "$tmp/$nom.sh"
}

construire_ancien() { # nom corps : entête, ancien bloc, contrôle final factice, corps
  local nom=$1 corps=$2
  {
    printf '#!/bin/bash\nset -u\nETAPE_NOM="%s"; ETAPE_VERSION="v1"\nETAPE_DIR="%s"\nA_BLANC=0\n' "$nom" "$tmp/etapes"
    cat "$ancien"
    printf 'controle_final() { echo "--- contrôle final (ancien)"; FINAL_VERT=1; }\n%s\n' "$corps"
  } > "$tmp/$nom.sh"
}

lancer_groupe() { # nom : lance $tmp/<nom>.sh dans un nouveau groupe (pgid = pid), dispositions INT, TERM, HUP, PIPE par défaut ; pid dans $pid
  local nom=$1
  # perl : nouveau groupe de processus et dispositions remises par défaut avant l'exec (sous le lanceur de suites, un processus en
  # arrière-plan hérite de INT ignoré, et bash ne peut alors plus piéger INT)
  perl -e '$SIG{INT} = $SIG{TERM} = $SIG{HUP} = $SIG{PIPE} = "DEFAULT"; setpgrp(0, 0); exec @ARGV' bash "$tmp/$nom.sh" > "$tmp/ecran-$nom" 2>&1 < /dev/null &
  pid=$!
}

attendre_pret() { # libelle : attend le fichier « pret »
  local essais=0
  while [ ! -e "$tmp/etapes/pret" ] && [ "$essais" -lt 2400 ]; do sleep 0.05; essais=$((essais+1)); done   # borne de sécurité de 120 s
  [ -e "$tmp/etapes/pret" ]; verifie "$1 : le fichier factice est arrivé à sa commande longue" $?
}

CORPS_LONG='echo "derniere ligne du corps"; : > "$ETAPE_DIR/pret"; sleep 30 3>&- 4>&-; sortir 0'

cas_signal() { # signal code-attendu
  local sig=$1 attendu=$2 nom="t-$1" rc journal derniere n_corps n_int
  construire "$nom" "$CORPS_LONG"
  rm -f "$tmp/etapes/pret"
  lancer_groupe "$nom"
  attendre_pret "$sig"
  kill -s "$sig" -- "-$pid"
  wait "$pid"; rc=$?
  journal=$(cat "$tmp/etapes/$nom.log" 2>/dev/null)
  [ "$rc" -eq "$attendu" ]; verifie "$sig : code de sortie $attendu (obtenu $rc)" $?
  case "$journal" in *"interrompu : rien n'est fusionné par ce fichier (code $attendu)"*) r=0 ;; *) r=1 ;; esac
  verifie "$sig : le journal porte « interrompu : rien n'est fusionné par ce fichier (code $attendu) »" $r
  case "$journal" in *"code de sortie : $attendu"*) r=0 ;; *) r=1 ;; esac
  verifie "$sig : le journal porte « code de sortie : $attendu »" $r
  [ "$(printf '%s\n' "$journal" | grep -cF "===== TERMINÉ : $nom ")" -eq 1 ]; verifie "$sig : le bandeau TERMINÉ est une fois au journal" $?
  case "$journal" in *"code $attendu (ÉCHEC)"*) r=0 ;; *) r=1 ;; esac
  verifie "$sig : le journal porte « code $attendu (ÉCHEC) »" $r
  [ "$(grep -cF "===== TERMINÉ : $nom " "$tmp/ecran-$nom")" -eq 1 ]; verifie "$sig : le bandeau est aussi tenté à l'écran, une fois" $?
  derniere=$(printf '%s\n' "$journal" | grep -v '^[[:space:]]*$' | tail -1)
  [ "$derniere" = "Tu peux dire « fait » au chef d'orchestre." ]; verifie "$sig : la dernière ligne non vide du journal est la phrase de fin (obtenu : $derniere)" $?
  n_corps=$(printf '%s\n' "$journal" | grep -nF "derniere ligne du corps" | head -1 | cut -d: -f1)
  n_int=$(printf '%s\n' "$journal" | grep -nF "interrompu :" | head -1 | cut -d: -f1)
  [ -n "$n_corps" ] && [ -n "$n_int" ] && [ "$n_corps" -lt "$n_int" ]; verifie "$sig : la dernière ligne du corps précède « interrompu » au journal" $?
}

cas_ancien() { # signal : l'ancien bloc doit être pris en défaut (pas de bandeau au journal)
  local sig=$1 nom="ancien-$1" rc journal
  construire_ancien "$nom" "$CORPS_LONG"
  rm -f "$tmp/etapes/pret"
  lancer_groupe "$nom"
  attendre_pret "ancien bloc, $sig"
  kill -s "$sig" -- "-$pid"
  wait "$pid"; rc=$?
  # on attend que le groupe soit vide (plus aucun processus ne peut écrire au journal), au lieu d'un délai fixe ; borne de 120 s
  essais=0; while kill -0 -- "-$pid" 2>/dev/null && [ "$essais" -lt 2400 ]; do sleep 0.05; essais=$((essais+1)); done
  if kill -0 -- "-$pid" 2>/dev/null; then verifie "cas témoin, $sig : le groupe de processus est vide (borne de 120 s atteinte)" 1; fi
  journal=$(cat "$tmp/etapes/$nom.log" 2>/dev/null)
  case "$journal" in *"===== TERMINÉ : $nom "*) r=1 ;; *) r=0 ;; esac
  verifie "cas témoin, $sig : l'ancien bloc ne laisse pas de bandeau au journal (la suite détecte la régression)" $r
}

cas_signal INT 130
cas_signal TERM 143
cas_signal HUP 129
cas_ancien TERM
cas_ancien HUP

# Tee tué à part pendant le corps : le premier echo qui suit reçoit SIGPIPE, le piège PIPE donne 141, le bandeau est quand même au journal.
construire "t-pipe" 'echo "avant"; kill -KILL "$TEE_PID"; i=0; while kill -0 "$TEE_PID" 2>/dev/null && [ "$i" -lt 6000 ]; do i=$((i+1)); sleep 0.02; done; [ "$i" -lt 6000 ] || : > "$ETAPE_DIR/borne-tee"; echo "apres"; sleep 30 3>&- 4>&-; sortir 0'
lancer_groupe "t-pipe"
wait "$pid"; rc=$?
[ ! -e "$tmp/etapes/borne-tee" ]; verifie "tee tué : le tee a disparu avant la borne de sécurité de 120 secondes" $?
journal=$(cat "$tmp/etapes/t-pipe.log" 2>/dev/null)
[ "$rc" -eq 141 ]; verifie "tee tué : code de sortie 141 (obtenu $rc)" $?
[ "$(printf '%s\n' "$journal" | grep -cF "===== TERMINÉ : t-pipe ")" -eq 1 ]; verifie "tee tué : le bandeau TERMINÉ est une fois au journal" $?
case "$journal" in *"interrompu : rien n'est fusionné par ce fichier (code 141)"*) r=0 ;; *) r=1 ;; esac
verifie "tee tué : le journal porte « interrompu … (code 141) »" $r
case "$journal" in *"code de sortie : 141"*) r=0 ;; *) r=1 ;; esac
verifie "tee tué : le journal porte « code de sortie : 141 »" $r

# Sortie normale : bandeau une seule fois (pas de doublon par le tee et l'écriture directe), au journal comme à l'écran, sans attente du test.
construire "t-normal" 'echo "travail factice"; sortir 0'
bash "$tmp/t-normal.sh" > "$tmp/ecran-t-normal" 2>&1 < /dev/null; rc=$?
journal=$(cat "$tmp/etapes/t-normal.log" 2>/dev/null)
[ "$rc" -eq 0 ]; verifie "normal : code 0 (obtenu $rc)" $?
[ "$(printf '%s\n' "$journal" | grep -cF "===== TERMINÉ : t-normal ")" -eq 1 ]; verifie "normal : bandeau une seule fois au journal" $?
[ "$(grep -cF "===== TERMINÉ : t-normal " "$tmp/ecran-t-normal")" -eq 1 ]; verifie "normal : bandeau une seule fois à l'écran" $?
[ "$(printf '%s\n' "$journal" | grep -cF "code de sortie : 0")" -eq 1 ]; verifie "normal : « code de sortie : 0 » une seule fois" $?
[ "$(printf '%s\n' "$journal" | grep -cF "travail factice")" -eq 1 ]; verifie "normal : la sortie du corps est au journal, une fois" $?
[ "$(printf '%s\n' "$journal" | grep -cF -e "--- contrôle final (gabarit)")" -eq 1 ]; verifie "normal : l'en-tête du contrôle final est une seule fois au journal" $?
derniere=$(printf '%s\n' "$journal" | grep -v '^[[:space:]]*$' | tail -1)
[ "$derniere" = "Tu peux dire « fait » au chef d'orchestre." ]; verifie "normal : la dernière ligne non vide du journal est la phrase de fin (obtenu : $derniere)" $?
case "$journal" in *"interrompu"*) r=1 ;; *) r=0 ;; esac
verifie "normal : aucune mention « interrompu »" $r
[ -f "$tmp/notifications" ]; verifie "la notification passe par le osascript factice (jamais le vrai)" $?

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
