---
name: shell-exec
description: Execute shell commands and scripts. Auto-invoked when bash, scripting, or command-line operations are needed during task execution.
user-invocable: false
---

# Shell Execution

Compétence automatique pour exécution de commandes shell et scripts nécessaires pendant l'exécution de tâches.

## Auto-invocation

Ce skill est invoqué automatiquement par le model quand:
- Une commande shell ou script bash est nécessaire
- Manipulation de fichiers en bulk est requise
- Pipes complexes ou redirections sont nécessaires
- Un script d'automatisation doit être créé et exécuté
- Traitement de texte avec sed/awk/grep est nécessaire
- Des variables d'environnement ou fichiers système doivent être inspectés

## Utilisation automatique

Le model invoque ce skill avec la commande ou script requis:

```
Besoin: Trouver tous les fichiers Python orphelins
→ Auto-invoque: /shell-exec find . -name "*.py" -type f | grep -v __pycache__

Besoin: Créer et exécuter un script de migration
→ Auto-invoque: /shell-exec --create-script migration.sh
```

## Opérations supportées

- Commandes shell simples et complexes
- Pipes et redirections
- Scripts bash avec boucles et conditions
- Traitement de texte (sed, awk, grep)
- Gestion de fichiers et répertoires
- Variables et substitutions
- Exécution de scripts existants

## Caractéristiques

- Exécution avec capture de sortie complète
- Gestion intelligente des erreurs
- Préservation du contexte du répertoire
- Validation syntaxique des scripts
- Environnement d'exécution isolé
- One-liners et multi-line scripts

## Quand le model l'invoque

Le model invoque automatiquement ce skill quand il détecte:
- Besoin d'explorer ou manipuler le système de fichiers
- Opération d'automatisation nécessaire
- Traitement de données en bulk
- Script d'installation ou configuration
- Tâche de maintenance système
- Recherche ou agrégation de données
