---
name: diagnose
description: System and performance diagnostics. Auto-invoked when system monitoring, profiling, or troubleshooting is needed during task execution.
user-invocable: false
---

# System Diagnostics

Compétence automatique pour diagnostic et monitoring système nécessaires pendant l'exécution de tâches.

## Auto-invocation

Ce skill est invoqué automatiquement par le model quand:
- Une analyse de performance est nécessaire
- Un problème système doit être diagnostiqué
- Les ressources (CPU, mémoire, disque, réseau) doivent être inspectées
- Un processus ou service doit être débogué
- Une fuite mémoire est suspectée
- La charge système doit être analysée

## Utilisation automatique

Le model invoque ce skill avec la demande diagnostic requise:

```
Besoin: Vérifier la consommation mémoire
→ Auto-invoque: /diagnose memory --process-tree

Besoin: Analyser la performance d'une fonction
→ Auto-invoque: /diagnose performance --profile function_name
```

## Opérations supportées

- Monitoring de ressources (CPU, mémoire, disque, réseau)
- Analyse de processus (ps, top, htop, lsof)
- Tracing système (strace, ltrace)
- Analyse de logs
- Profilage de performance
- Identification de fuites mémoire
- Gestion des connexions réseau
- Débogage de problèmes système

## Caractéristiques

- Rapports détaillés avec données collectées
- Interprétation intelligente des résultats
- Identification des anomalies
- Recommandations correctives
- Historique et tendances
- Outils non-invasifs par défaut

## Quand le model l'invoque

Le model invoque automatiquement ce skill quand il détecte:
- Performance dégradée ou comportement anormal
- Besoin de profiling ou benchmark
- Suspicion de fuite de ressources
- Troubleshooting de problèmes système
- Validation que les optimisations ont un effet
- Analyse de goulots d'étranglement
