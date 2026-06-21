---
name: devtools
description: Development tools and build system. Auto-invoked when package management, build operations, or dev tooling is needed during task execution.
user-invocable: false
---

# Development Tools

Compétence automatique pour gestion des outils de développement et build nécessaires pendant l'exécution de tâches.

## Auto-invocation

Ce skill est invoqué automatiquement par le model quand:
- Installation ou mise à jour de dépendances est nécessaire
- Un build ou compilation doit être exécuté
- Un package manager doit être utilisé
- Configuration de CI/CD est requise
- Versioning ou release management est nécessaire
- Outils de développement doivent être configurés

## Utilisation automatique

Le model invoque ce skill avec l'opération requise:

```
Besoin: Ajouter une nouvelle dépendance
→ Auto-invoque: /devtools add package-name --version latest

Besoin: Construire le projet pour production
→ Auto-invoque: /devtools build --release --optimize
```

## Opérations supportées

- Package managers (npm, pip, uv, cargo, etc.)
- Systèmes de build (Make, Gradle, Maven, etc.)
- Conteneurisation (Docker, Podman)
- CI/CD pipelines (GitHub Actions, GitLab CI, etc.)
- Versioning et releases
- Résolution de dépendances et conflits
- Caching et optimisation de build
- Outils de test et couverture

## Caractéristiques

- Gestion intelligente des versions
- Détection automatique du système de build
- Résolution de conflits de dépendances
- Caching et optimisations
- Validation des changements de dépendances
- Rapports détaillés de build

## Quand le model l'invoque

Le model invoque automatiquement ce skill quand il détecte:
- Besoin d'ajouter/mettre à jour des dépendances
- Construction du projet requise
- Configuration du build system
- Intégration avec CI/CD
- Optimisation de performance de build
- Troubleshooting de problèmes de dépendances
