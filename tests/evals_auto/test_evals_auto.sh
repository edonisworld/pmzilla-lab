#!/bin/sh
# Test de tools/evals_auto.sh : faux HOME, dépôt temporaire, faux uv, claude, curl et osascript qui notent leurs appels.
# Aucun appel à Claude, à Ollama, au réseau ni à une vraie notification. Lancement à la main : sh tests/evals_auto/test_evals_auto.sh
set -u
script="$(cd "$(dirname "$0")/../../tools" && pwd)/evals_auto.sh"
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
tmp=$(cd "$tmp" && pwd -P)
export HOME="$tmp/home"
ws="$HOME/PMZilla-Lab/workspace"
bin="$HOME/.local/bin"
mkdir -p "$ws/tools" "$ws/.claude/commands" "$ws/docs/pmzilla" "$ws/_bmad-output/essais" "$bin"
journal="$tmp/appels"
cp "$script" "$ws/tools/evals_auto.sh"
printf -- '---\ndescription: test\n---\nMets à jour le README. Précision : $ARGUMENTS\n' > "$ws/.claude/commands/update-readme.md"
echo readme > "$ws/README.md"; echo install > "$ws/docs/pmzilla/installation.md"

# faux outils : ils notent leurs arguments ; le faux uv rend un bilan d'essai
printf '#!/bin/sh\nexit 0\n' > "$bin/curl"
printf '#!/bin/sh\nexit 0\n' > "$bin/osascript"
cat > "$bin/claude" <<FAKE
#!/bin/sh
echo "claude: \$*" >> "$journal"
echo "README vérifié"
FAKE
cat > "$bin/uv" <<FAKE
#!/bin/sh
echo "uv: \$*" >> "$journal"
case "\$*" in
  *posture_evals.py*) : > "$ws/_bmad-output/essais/rapport.md"; echo "BILAN 32/32 · 0 régression(s) · $ws/_bmad-output/essais/rapport.md" ;;
esac
exit 0
FAKE
chmod +x "$bin/curl" "$bin/osascript" "$bin/claude" "$bin/uv"

cd "$ws" || exit 1
git init -q . && git config user.email t@example.org && git config user.name test
git add -A && git commit -q -m init --no-verify
ok=0; ko=0

lance() { rm -f "$journal"; sortie=$(zsh "$ws/tools/evals_auto.sh" "$@" 2>&1); code=$?; }
verifie() { # description condition(0 = vraie)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1"; ko=$((ko+1)); fi
}
appele() { grep -q "$1" "$journal" 2>/dev/null; }
dit() { printf '%s' "$sortie" | grep -q "$1"; }

lance
verifie "sans option : code 0" $([ "$code" -eq 0 ]; echo $?)
verifie "sans option : le jeu d'essai est rejoué sur l'état commité" $(appele "posture_evals.py --committed-state"; echo $?)
verifie "sans option : le tableau de bord est régénéré" $(appele "dashboard.py"; echo $?)
verifie "sans option : aucune session claude" $(appele "claude:"; [ $? -ne 0 ]; echo $?)
verifie "sans option : aucun push" $(dit "Push impossible"; [ $? -ne 0 ]; echo $?)
verifie "sans option : le verrou est libéré" $([ ! -d "$HOME/.pmzilla-lab/essais/en-cours.lock" ]; echo $?)

lance --readme
verifie "--readme : le jeu d'essai est rejoué" $(appele "posture_evals.py"; echo $?)
verifie "--readme : la session claude -p est lancée avec le bilan" $(appele "claude: -p .*mode automatique après le jeu d'essai (32/32"; echo $?)
verifie "--readme : la consigne de /update-readme est reprise sans son en-tête" $(appele "Mets à jour le README"; [ $? -eq 0 ] && ! appele "description: test"; echo $?)
verifie "--readme : le push est tenté" $(dit "Push impossible"; echo $?)

echo "modif en cours" >> README.md
lance --readme
verifie "--readme avec README.md modifié : refusé, avec le motif" $(dit "modifications non commitées"; echo $?)
verifie "--readme avec README.md modifié : aucune session claude" $(appele "claude:"; [ $? -ne 0 ]; echo $?)
verifie "--readme avec README.md modifié : le jeu d'essai a tourné quand même" $(appele "posture_evals.py"; echo $?)
git checkout -q README.md
echo "modif en cours" >> docs/pmzilla/installation.md
lance --readme
verifie "--readme avec installation.md modifié : refusé" $(dit "modifications non commitées"; [ $? -eq 0 ] && ! appele "claude:"; echo $?)
lance
verifie "sans --readme, des modifications du README ne gênent pas" $(appele "posture_evals.py"; [ $? -eq 0 ] && ! dit "modifications non commitées"; echo $?)
git checkout -q docs/pmzilla/installation.md

lance --bidon
verifie "option inconnue : code 2 et aucun appel" $([ "$code" -eq 2 ] && [ ! -f "$journal" ]; echo $?)
lance --help
verifie "--help : code 0, décrit --readme, aucun appel" $([ "$code" -eq 0 ] && dit "evals_auto.sh --readme" && [ ! -f "$journal" ]; echo $?)

# --- Passage déjà en cours, service d'embedding absent, notification d'erreur (openspec/test-gaps.md, posture-evals) ---
notifs="$tmp/notifications"
cat > "$bin/osascript" <<FAKE
#!/bin/sh
echo "notification: \$*" >> "$notifs"
exit 0
FAKE
chmod +x "$bin/osascript"
etat="$HOME/.pmzilla-lab/essais"
notifie() { grep -c "notification:" "$notifs" 2>/dev/null || true; }

# un passage est déjà en cours (verrou posé) : le second lancement note une relance et s'arrête sans rien jouer
rm -f "$notifs"; mkdir -p "$etat/en-cours.lock"
lance
verifie "passage en cours : code 0" $([ "$code" -eq 0 ]; echo $?)
verifie "passage en cours : relance demandée et signalée" $([ -f "$etat/a-relancer" ] && dit "relance demandée"; echo $?)
verifie "passage en cours : ni jeu d'essai ni tableau de bord" $([ ! -f "$journal" ]; echo $?)
verifie "passage en cours : le verrou du passage en cours n'est pas libéré" $([ -d "$etat/en-cours.lock" ]; echo $?)
verifie "passage en cours : aucune notification" $([ ! -f "$notifs" ]; echo $?)
rmdir "$etat/en-cours.lock"; rm -f "$etat/a-relancer"

# le service d'embedding ne répond pas : essai reporté (pas joué), code non nul, une notification, verrou libéré
printf '#!/bin/sh\nexit 7\n' > "$bin/curl"; chmod +x "$bin/curl"
rm -f "$notifs"
lance
verifie "service absent : code non nul" $([ "$code" -ne 0 ]; echo $?)
verifie "service absent : essai reporté, avec le motif" $(dit "essai reporté"; echo $?)
verifie "service absent : le jeu d'essai n'est pas joué" $(appele "posture_evals.py"; [ $? -ne 0 ]; echo $?)
verifie "service absent : une seule notification, celle du report" $([ "$(notifie)" = "1" ] && grep -q "reporté" "$notifs"; echo $?)
verifie "service absent : le verrou est libéré" $([ ! -d "$etat/en-cours.lock" ]; echo $?)
printf '#!/bin/sh\nexit 0\n' > "$bin/curl"; chmod +x "$bin/curl"

# un passage sans bilan : notification d'erreur, une seule, et le tableau de bord est quand même régénéré
cat > "$bin/uv" <<FAKE
#!/bin/sh
echo "uv: \$*" >> "$journal"
case "\$*" in
  *posture_evals.py*) echo "Traceback simulé" ; exit 1 ;;
esac
exit 0
FAKE
chmod +x "$bin/uv"
rm -f "$notifs"
lance
verifie "passage sans bilan : message d'erreur dans la sortie" $(dit "Essai sans bilan"; echo $?)
verifie "passage sans bilan : une seule notification, d'erreur" $([ "$(notifie)" = "1" ] && grep -q "en erreur" "$notifs"; echo $?)
verifie "passage sans bilan : le tableau de bord est régénéré" $(appele "dashboard.py"; echo $?)
verifie "passage sans bilan : le verrou est libéré" $([ ! -d "$etat/en-cours.lock" ]; echo $?)

# une relance demandée pendant un passage est jouée à la fin de celui-ci : le faux uv demande la relance (second
# lancement simulé en posant a-relancer) pendant le premier jeu d'essai seulement
cat > "$bin/uv" <<FAKE
#!/bin/sh
echo "uv: \$*" >> "$journal"
case "\$*" in
  *posture_evals.py*)
    if [ ! -f "$tmp/relance-deja-demandee" ]; then : > "$tmp/relance-deja-demandee"; : > "$etat/a-relancer"; fi
    : > "$ws/_bmad-output/essais/rapport.md"; echo "BILAN 32/32 · 0 régression(s) · $ws/_bmad-output/essais/rapport.md" ;;
esac
exit 0
FAKE
chmod +x "$bin/uv"
rm -f "$tmp/relance-deja-demandee" "$etat/a-relancer"
lance
verifie "relance demandée pendant le passage : le jeu d'essai est joué deux fois" $([ "$(grep -c 'posture_evals.py' "$journal")" = "2" ]; echo $?)
verifie "relance demandée pendant le passage : la relance est annoncée" $(dit "relance"; echo $?)
verifie "relance demandée pendant le passage : pas de troisième passage, demande effacée" $([ ! -f "$etat/a-relancer" ]; echo $?)
verifie "relance demandée pendant le passage : le verrou est libéré" $([ ! -d "$etat/en-cours.lock" ]; echo $?)

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
