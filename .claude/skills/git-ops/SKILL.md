---
name: git-ops
description: Git operations and version control. Auto-invoked when git commands or repository management is needed during task execution.
user-invocable: false
---

# Git Operations

Compétence automatique pour opérations Git nécessaires pendant l'exécution de tâches.

## Auto-invocation

Ce skill est invoqué automatiquement par le model quand:
- Une opération Git est nécessaire (merge, rebase, cherry-pick, branch management)
- L'analyse d'historique ou de branches est requise
- Une stratégie de versioning doit être appliquée
- Un conflit de merge doit être résolu
- La synchronisation avec un repositorrium distant est nécessaire

## Utilisation automatique

Le model invoque ce skill avec la commande/opération Git requise:

```
Besoin: Fusionner une branche feature
→ Auto-invoque: /git-ops merge feature-branch into main --strategy

Besoin: Analyser l'historique pour un bug
→ Auto-invoque: /git-ops blame file.py --range
```

## Opérations supportées

- Merge et rebase (avec stratégie appropriée)
- Cherry-pick de commits
- Gestion de branches (create, delete, rename)
- Analyse d'historique (log, blame, diff)
- Tag et release management
- Stash et reset
- Résolution de conflits

## Caractéristiques

- Dry-run automatique avant opérations destructives
- Validation de l'état du repositorrium
- Stratégies de merge intelligentes
- Prévention des force-push non intentionnels
- Analyse détaillée des conflits

## Quand le model l'invoque

Le model invoque automatiquement ce skill quand il détecte:
- Besoin de branching ou merge pour feature/bugfix
- Nécessité de nettoyer l'historique
- Besoin de synchroniser avec upstream
- Analyse d'historique pour debugging
- Stratégie de versioning à appliquer
