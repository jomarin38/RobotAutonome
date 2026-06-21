---
name: readme-writer
description: Write or update README.md with installation, usage, features, and architecture sections. Use when creating or improving the project's README.
---

# README Writer

Crée et améliore le README.md du projet avec une approche complète et structurée.

## Fonctionnalités

- Exploration complète de l'architecture et des features
- Génération de sections README bien structurées
- Exemples d'utilisation fonctionnels et testés
- Documentation d'installation et configuration
- Schémas textuels de l'architecture
- Quick start et common tasks
- Badges et liens pertinents
- Table des matières automatique

## Utilisation

```bash
/readme-writer                   # Analyser et rapporter sur le README actuel
/readme-writer --create          # Créer un nouveau README complet
/readme-writer --update          # Actualiser le README existant
/readme-writer --add-section "Installation"  # Ajouter une section
```

## Sections générées

- **Overview** — Description du projet en 1-2 phrases
- **Features** — Liste des capacités principales
- **Installation** — Instructions détaillées par plateforme
- **Quick Start** — Exemple minimal pour démarrer
- **Usage** — Guide d'utilisation avec exemples
- **Architecture** — Diagramme textuel de la structure
- **Configuration** — Options de configuration disponibles
- **Development** — Instructions pour dev et testing
- **Contributing** — Guidelines de contribution
- **License** — Informations de license

## Processus

1. **Exploration** — `explorer-global` scanne l'architecture complète
2. **Analyse** — `explorer-precise` localise les points clés (main, config, examples)
3. **Rédaction** — `documentation-writer` crée le README avec structure et exemples
4. **Validation** — Vérifie que les exemples sont exécutables et précis

## Agents utilisés

- **explorer-global** — Comprendre l'architecture générale
- **explorer-precise** — Identifier les points d'entrée, exemples, configuration
- **documentation-writer** — Écrire le contenu README professionnel
- **test-engineer** — Valider que les exemples fonctionnent

## Résultat

Un README.md professionnel contenant:
- Structure claire et navigable
- Exemples d'utilisation fonctionnels
- Instructions complètes
- Liens vers documentation détaillée
- Badges et informations pertinentes
