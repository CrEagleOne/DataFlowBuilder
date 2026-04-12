# 🤝 Guide de contribution — Data Flow Builder Pro

Merci de l'intérêt que vous portez à **Data Flow Builder Pro** ! Toutes les contributions sont les bienvenues : corrections de bugs, nouveaux types de champs, améliorations de la documentation ou retours d'expérience.

Ce guide vous explique comment participer dans les meilleures conditions.

---

## 📋 Sommaire

- [Code de conduite](#code-de-conduite)
- [Comment contribuer](#comment-contribuer)
  - [Signaler un bug](#signaler-un-bug)
  - [Proposer une amélioration](#proposer-une-amélioration)
  - [Soumettre du code](#soumettre-du-code)
- [Environnement de développement](#environnement-de-développement)
- [Conventions de code](#conventions-de-code)
- [Commits et branches](#commits-et-branches)
- [Processus de revue](#processus-de-revue)
- [Licence des contributions](#licence-des-contributions)

---

## Code de conduite

En participant à ce projet, vous vous engagez à respecter notre [Code de Conduite](CODE_OF_CONDUCT.md). Merci de le lire avant de commencer.

---

## Comment contribuer

### Signaler un bug

Avant d'ouvrir une issue, vérifiez qu'elle n'existe pas déjà dans la [liste des issues](https://github.com/CrEagleOne/DataFlowBuilder/issues).

Pour signaler un bug, ouvrez une issue en utilisant le **template Bug Report** et renseignez :

- Une description claire et concise du problème
- Les étapes exactes pour le reproduire
- Le comportement attendu vs le comportement observé
- Votre système d'exploitation et la version de Data Flow Builder
- Des captures d'écran si elles sont pertinentes

> **Vulnérabilités de sécurité** : ne les signalez pas via les issues publiques. Contactez-nous directement via les [GitHub Security Advisories](https://github.com/CrEagleOne/DataFlowBuilder/security/advisories/new).

---

### Proposer une amélioration

Vous avez une idée de fonctionnalité ? Ouvrez une issue avec le label `enhancement` et décrivez :

- Le problème que vous cherchez à résoudre
- La solution que vous envisagez
- Les alternatives que vous avez considérées

Les propositions importantes (nouveau type de champ, format de sortie, moteur de génération) feront l'objet d'une discussion avant tout développement, afin d'éviter les efforts inutiles.

---

### Soumettre du code

1. **Forkez** le dépôt et clonez votre fork localement.
2. **Créez une branche** depuis `develop` (voir les conventions ci-dessous).
3. **Développez** votre modification avec des tests si applicable.
4. **Vérifiez** que la CI passe localement (`pytest`, `ruff check .`).
5. **Ouvrez une Pull Request** vers la branche `develop` du dépôt principal.

---

## Environnement de développement

**Prérequis :** Python 3.11+, Git

```bash
# Cloner votre fork
git clone https://github.com/<votre-pseudo>/DataFlowBuilder.git
cd DataFlowBuilder

# Créer et activer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows

# Installer les dépendances (avec outils de développement)
pip install -e ".[dev]"

# Installer les hooks
bash install-hooks.sh

# Lancement de l'appli
python main.py
```

### Lancer les tests

```bash
# Tous les tests
pytest

# Tests unitaires uniquement (si existant)
pytest tests/unit/ -v

# Tests d'intégration uniquement (si existant)
pytest tests/integration/ -v

# Avec rapport de couverture HTML
pytest --cov-report=html
open htmlcov/index.html
```

### Linting et formatage

```bash
# Vérification du style
ruff check .

# Vérification d'un style précis
ruff check --select I001

# Fix les erreurs rencontrées
ruff check --fix 

# Formatage automatique
ruff format .

# Vérification des types
mypy src/

# Vérification du pré-commit
pre-commit run --all-files

# Analyse de sécurité
bandit -r src/
```

---

## Conventions de code

- **Style :** le projet suit [PEP 8](https://peps.python.org/pep-0008/), appliqué via [Ruff](https://github.com/astral-sh/ruff).
- **Typage :** les annotations de type sont obligatoires pour tout nouveau code.
- **Docstrings :** chaque fonction publique doit être documentée (format Google-style).
- **Tests :** tout nouveau comportement doit être accompagné de tests unitaires. La couverture cible sur le module `core/` est ≥ 70 %.
- **Architecture :** respectez la séparation stricte — `ui/` ne doit jamais importer directement depuis `storage.py` ; tout passe par `flow_manager.py`.

### Ajouter un nouveau type de champ

1. Déclarer le sous-type dans `FIELD_SUBTYPES` et `SUBTYPE_CONFIG` dans `core/field_types.py`
2. Implémenter la logique de génération dans `core/data_generator.py`
3. Ajouter les tests dans `tests/test_data_generator.py`
4. Mettre à jour la documentation dans `index.html` (section *Types de champs*)

---

## Commits et branches

### Convention de nommage des commits

Le projet utilise les [Conventional Commits](https://www.conventionalcommits.org/fr) :

| Préfixe | Usage |
|---------|-------|
| `feat:` | Nouvelle fonctionnalité |
| `fix:` | Correction de bug |
| `docs:` | Documentation uniquement |
| `style:` | Formatage, sans changement logique |
| `refactor:` | Refactorisation sans nouveau comportement |
| `test:` | Ajout ou modification de tests |
| `chore:` | Tâches de maintenance (deps, CI…) |

Exemples :
```
feat: ajouter le sous-type alpha/siren
fix: corriger le padding "both" pour les longueurs impaires
docs: mettre à jour la référence du filtre codePostalFilter
chore: bumper Faker à 25.0.0
```

### Convention de nommage des branches

```
feature/<description-courte>   # nouvelle fonctionnalité
fix/<description-courte>       # correction de bug
docs/<description-courte>      # documentation
chore/<description-courte>     # maintenance
```

### Workflow Git

```
main        ←── releases stables (tags vX.Y.Z)
develop     ←── intégration continue (cible des PRs)
feature/*   ←── nouvelles fonctionnalités → PR vers develop
fix/*       ←── corrections → PR vers develop (ou main si critique)
```

---

## Processus de revue

- Toute Pull Request doit passer la CI complète (lint + tests + couverture).
- Une approbation d'un mainteneur est requise avant le merge.
- Les retours de revue sont formulés de façon constructive et bienveillante.
- Le merge est effectué par le mainteneur après approbation.

**Délai de réponse indicatif :** nous nous efforçons de répondre aux PRs et issues sous **7 jours ouvrés**.

---

## Licence des contributions

En soumettant une contribution, vous acceptez qu'elle soit distribuée sous la même licence que le projet (PolyForm Noncommercial License 1.0.0 — voir [`LICENSE.md`](LICENSE.md)). Si vous contribuez dans un cadre professionnel, assurez-vous que votre employeur autorise cette contribution.

---

Merci pour votre contribution — chaque amélioration, même minime, compte !
