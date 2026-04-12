#!/usr/bin/env bash
# install-hooks.sh
# Configure Git pour utiliser .githooks/ ET installe le framework pre-commit.
# À lancer une seule fois après le clone du repo.
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'

echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║      Installation des git hooks      ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

# ── 1. Vérifier qu'on est dans un repo Git ─────────────────────────────────
if ! git rev-parse --git-dir &>/dev/null; then
  echo -e "${RED}✗ Ce répertoire n'est pas un dépôt Git.${NC}" >&2
  exit 1
fi

# ── 2. Rendre tous les hooks exécutables ───────────────────────────────────
chmod +x .githooks/*
echo -e "${GREEN}✓ Hooks rendus exécutables (.githooks/)${NC}"

# ── 3. Configurer Git pour pointer sur .githooks/ ──────────────────────────
git config core.hooksPath .githooks
echo -e "${GREEN}✓ git config core.hooksPath = .githooks${NC}"

# ── 4. Installer pre-commit framework ──────────────────────────────────────
if command -v pre-commit &>/dev/null; then
  pre-commit install --hook-type pre-commit
  pre-commit install --hook-type commit-msg
  pre-commit install --install-hooks
  echo -e "${GREEN}✓ Framework pre-commit installé et hooks à jour${NC}"
else
  echo -e "${YELLOW}⚠ pre-commit non trouvé. Installez-le :${NC}"
  echo -e "     pip install pre-commit"
  echo -e "     pre-commit install"
fi

# ── 5. Initialiser la baseline detect-secrets ──────────────────────────────
if command -v detect-secrets &>/dev/null; then
  if [ ! -f ".secrets.baseline" ]; then
    detect-secrets scan > .secrets.baseline
    echo -e "${GREEN}✓ Baseline detect-secrets créée (.secrets.baseline)${NC}"
  else
    echo -e "${GREEN}✓ Baseline detect-secrets existante conservée${NC}"
  fi
else
  echo -e "${YELLOW}⚠ detect-secrets non trouvé (optionnel).${NC}"
  echo -e "     pip install detect-secrets"
fi

echo ""
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo -e "${GREEN}  Installation terminée avec succès ! ${NC}"
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo ""
echo -e "Hooks actifs :"
echo -e "  pre-commit        → lint, format, sécurité"
echo -e "  commit-msg        → Conventional Commits"
echo -e "  prepare-commit-msg → auto-ticket depuis branche"
echo -e "  pre-push          → tests + mypy"
echo -e "  post-checkout     → alerte dépendances"
echo -e "  post-merge        → alerte dépendances"
