---
name: cc-audit-bugs
description: Search for bugs in the project and generate a detailed categorized report with criticality scores
trigger: /cc-audit-bugs
---

# Audit de Bugs du Projet

Recherche les bugs, failles logiques et comportements dangereux dans le code Python.

## Paramètres

- **--fix** (optionnel) — Applique automatiquement les corrections pour les bugs critiques (criticité ≥ 50)

## Catégories de bugs

- **Logique** — Conditions incorrectes, boucles infinies, état incohérent
- **Sécurité** — Injections, accès non autorisé, validation insuffisante
- **Concurrence** — Race conditions, deadlocks, synchronisation manquante
- **Ressources** — Fuites mémoire, fichiers non fermés, connections non libérées
- **Type** — Incompatibilités de type, conversions dangereuses
- **Erreur Handling** — Exceptions non catchées, erreurs non propagées
- **Performance** — Algorithmes inefficaces, boucles mal optimisées
- **Edge Cases** — Off-by-one errors, empty containers, None handling

## Rapport de sortie

Tableau structuré avec:
- **Nom** — Nom court du bug
- **Explication** — Description détaillée et pourquoi c'est un problème
- **Catégorie** — Type de bug
- **Localisation** — Chemin:ligne ou fonction.méthode
- **Correction** — Instructions précises pour corriger
- **Criticité** — Score de 0-100

Les bugs sont triés par criticité (les plus graves en premier).

## Résumé final

- Nombre total de bugs
- Répartition par sévérité (critique, high, medium, low)
- Répartition par catégorie

## Utilisation

```
/cc-audit-bugs            # Audit seul
/cc-audit-bugs --fix      # Audit + fix bugs critiques (≥50)
```

## Agent utilisé

- **bug-finder** — Détecte bugs et failles logiques
- **code-fixer** — Applique les corrections (si --fix)
