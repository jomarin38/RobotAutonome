---
name: skill-creator
description: Create or modify skills and agents. Use when you want to author a new skill, update agent instructions, or design custom automation.
---

# Skill Creator

Guide interactif pour créer des skills et agents optimisés.

## Fonctionnalités

- Création de new skills avec descriptions optimisées
- Création d'agents spécialisés avec system prompts structurés
- Validation des frontmatter YAML
- Conseils sur les patterns et les bonnes pratiques
- Génération de références et scripts
- Synchronisation automatique entre user-level et project-level

## Utilisation

```bash
/skill-creator                          # Guide interactif complet
/skill-creator "nom de skill"           # Créer un skill spécifique
/skill-creator --agent "nom d'agent"    # Créer un agent spécifique
/skill-creator --template audit         # Utiliser un template (audit, doc, test, terminal)
```

## Templates disponibles

- **audit** — Code quality and analysis
- **doc** — Documentation and writing
- **test** — Testing and validation
- **terminal** — CLI and system commands
- **dev** — Development tools and workflows

## Structure guidée

Le skill creator te guide pour:

1. **Métadonnées** — Name, description (50-300 chars), trigger
2. **Objectif** — Qu'est-ce que le skill fait et quand on l'utilise
3. **Paramètres** — Arguments acceptés et leurs options
4. **Agents utilisés** — Quels agents sont nécessaires et comment
5. **Flux de travail** — Étapes et ordre d'exécution
6. **Résultat** — Format et contenu du résultat final

## Bonnes pratiques

- Description doit être un **trigger phrase** ("Use when...", "Create...")
- Combiner plusieurs agents pour **workflows complexes**
- Utiliser les references pour du contenu long (> 200 lignes)
- Documenter les limitations et edge cases
- Tester le skill après création

## Résultat

- `SKILL.md` complet avec frontmatter et instructions
- Fichiers references/ si nécessaire
- Scripts/ si besoin de code déterministe
- Synchronisation user-level et project-level
