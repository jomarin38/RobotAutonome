---
name: doc-writer
description: Write and update project documentation. Use when you need to create/improve docstrings, guides, API docs, or architectural documentation for the codebase.
---

# Documentation Writer

Crée et améliore la documentation du projet en utilisant une approche multi-agents coordonnée.

## Fonctionnalités

- Exploration du codebase pour identifier les parties à documenter
- Génération de docstrings complets (paramètres, retours, exceptions)
- Création de guides d'utilisation et tutoriels
- Documentation d'API et des modules
- Vérification de la cohérence documentaire
- Mise à jour des docstrings obsolètes

## Utilisation

```bash
/doc-writer                      # Analyser et rapporter les gaps de documentation
/doc-writer --update             # Actualiser toute la documentation
/doc-writer "nom du module"      # Documenter un module spécifique
/doc-writer "nom de fonction"    # Documenter une fonction spécifique
```

## Processus

1. **Exploration** — Utilise les agents `explorer-global` et `explorer-precise` pour cartographier le codebase
2. **Analyse** — Identifie les parties sous-documentées et les docstrings obsolètes
3. **Documentation** — L'agent `documentation-writer` crée une documentation claire avec exemples
4. **Vérification** — Valide que les exemples sont exécutables et les descriptions précises

## Types de documentation générés

- Docstrings complets (Google/NumPy format)
- Guides d'utilisation des modules
- Exemples de code fonctionnels
- Documentation des interfaces publiques
- Guides de contribution
- Notes sur les comportements non-évidents

## Agents utilisés

- **explorer-global** — Comprendre la structure du projet
- **explorer-precise** — Localiser les fonctions/classes à documenter
- **documentation-writer** — Générer la documentation
- **python-type-expert** — Documenter les types avancés

## Résultat

Un rapport détaillant:
- Documentation créée/améliorée
- Fichiers modifiés
- Recommandations pour documentation future
