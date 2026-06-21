---
name: cc-audit-structure
description: Audit project structure, naming consistency, top-down order, comments, dead code, and user-facing strings
trigger: /cc-audit-structure
---

# Audit de Structure du Projet

Effectue un audit complet de la cohérence et de la structure du code Python.

## Paramètres

- **--fix** (optionnel) — Applique automatiquement les corrections trouvées

## Vérifications effectuées

1. **Cohérence de nommage** — Tous les identificateurs suivent-ils `snake_case`? Y a-t-il des incohérences?

2. **Ordre de définition (Top-Down)** — Les fonctions/méthodes/classes sont-elles définies AVANT d'être appelées? Le code peut-il être lu linéairement sans naviguer vers le bas puis remonter?

3. **Commentaires et docstrings**:
   - À jour et corrects?
   - Commentaires orphelins (code supprimé mais commentaire resté)?
   - Suivent le style (français pour commentaires, anglais pour code)?
   - Manquent-ils des docstrings importants?

4. **Code mort** — Variables inutilisées, imports inutiles, code commenté, fonctions orphelines

5. **Strings utilisateur** — Logs, messages d'erreur et textes suivent-ils la même convention?

## Rapport de sortie

Le rapport inclut:
- **Fichier et ligne** — Localisation précise
- **Type** — Catégorie du problème
- **Sévérité** — low, medium, ou high
- **Description** — Explication du problème
- **Suggestion** — Comment corriger

## Utilisation

```
/cc-audit-structure           # Audit seul
/cc-audit-structure --fix     # Audit + corrections automatiques
```

## Agent utilisé

- **structure-auditor** — Analyse la cohérence et structure du code
