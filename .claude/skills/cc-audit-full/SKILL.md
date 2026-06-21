---
name: cc-audit-full
description: Complete project audit combining structure and bug detection with final report and recommendations
trigger: /cc-audit-full
---

# Audit Complet du Projet

Effectue un audit complet combinant vérification de structure et détection de bugs, puis génère un rapport final consolidé.

## Paramètres

- **--fix** (optionnel) — Applique automatiquement toutes les corrections trouvées

## Processus

1. **Phase 1: Audit de structure** — Vérification de cohérence, nommage, ordre top-down, commentaires, code mort, strings utilisateur

2. **Phase 2: Audit de bugs** — Détection des bugs, failles logiques, comportements dangereux

3. **Phase 3: Synthèse** — Génération d'un rapport final avec:
   - Résumé global des problèmes
   - Détails de la structure
   - Détails des bugs (par sévérité et catégorie)
   - Recommandations prioritaires

## Rapport final

Le rapport inclut:
- **Nombre total de problèmes** (structure + bugs)
- **Répartition par type** (structure vs bugs)
- **Criticité des bugs** (critiques, high, medium, low)
- **Catégories de bugs trouvés**
- **Recommandations d'action** prioritaires

## Utilisation

```
/cc-audit-full            # Audit complet
/cc-audit-full --fix      # Audit complet + corrections automatiques
```

## Agents utilisés

- **structure-auditor** — Analyse structure et cohérence
- **bug-finder** — Détecte bugs et failles
- **code-fixer** — Applique corrections (si --fix)

## Durée estimée

Dépend de la taille du projet (5-15 minutes pour un projet moyen).

## Recommandations

Après l'audit:
1. Revue les problèmes de structure (risque de confusion de lecture)
2. Corrige les bugs critiques (criticité ≥ 80) en priorité
3. Refactorise le code mort
4. Harmonise les strings utilisateur
