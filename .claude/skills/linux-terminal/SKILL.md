---
name: linux-terminal
description: Linux/terminal coordination and complex workflows. Auto-invoked when coordinated multi-tool terminal operations are needed during task execution.
user-invocable: false
---

# Linux Terminal Coordination

Compétence automatique pour orchestration de tâches terminal complexes nécessitant coordination entre plusieurs outils.

## Auto-invocation

Ce skill est invoqué automatiquement par le model quand:
- Plusieurs outils terminal doivent être coordonnés
- Une tâche Linux complexe requiert plusieurs étapes
- Opérations shell + git + diagnostic doivent être combinées
- Workflows d'automatisation multi-étapes sont nécessaires
- Troubleshooting complexe nécessite plusieurs outils

## Utilisation automatique

Le model invoque ce skill pour orchestrer des workflows complexes:

```
Besoin: Migrer un projet vers une nouvelle structure
→ Auto-invoque: /linux-terminal migrate-project --from old_structure --to new_structure

Besoin: Diagnostiquer et fixer un problème de build
→ Auto-invoque: /linux-terminal troubleshoot-build --analysis detailed
```

## Opérations supportées

- Coordination de tâches Git + Shell + Diagnostic
- Workflows d'automatisation multi-étapes
- Orchestration de scripts complexes
- Troubleshooting multi-outil
- Déploiement et migrations
- Maintenance système coordonnée
- Intégration continue et validation

## Caractéristiques

- Routing intelligent vers les bons outils (git-ops, shell-exec, diagnose, devtools)
- Gestion du contexte et des dépendances entre étapes
- Rapports consolidés de workflow
- Rollback et recovery automatiques si nécessaire
- Logging détaillé de chaque étape
- Validation progressive des étapes

## Sous-compétences coordonnées

Ce skill coordonne:
- **git-ops** — Pour opérations Git
- **shell-exec** — Pour scripts et commandes shell
- **diagnose** — Pour monitoring et diagnostic
- **devtools** — Pour build et dépendances

## Quand le model l'invoque

Le model invoque automatiquement ce skill quand il détecte:
- Besoin de combiner plusieurs opérations terminal
- Workflows complexes avec dépendances
- Troubleshooting multi-étapes
- Migrations ou refactoring structurel
- Opérations de maintenance système
- Tâches d'intégration continue
