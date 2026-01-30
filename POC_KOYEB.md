# POC : Inference Open-Weight pour Inspection Visuelle & Dev Agentique

## Objectif

Déployer un LLM open-weight multimodal sur Koyeb (scale-to-zero) capable de :
1. **Inspection visuelle** — analyser des screenshots, interfaces, documents visuels
2. **Développement agentique** — coder, éditer des fichiers, enchaîner des tool calls
3. **Chaînage d'appels** — boucle autonome perception → raisonnement → action → perception

Pas de serveur MCP côté infra. Pas de fine-tuning. Le modèle expose une API OpenAI-compatible avec vision + function calling. L'orchestration agent tourne côté client.

---

## Choix du modèle

### Retenu : Qwen2.5-VL-72B-Instruct (BF16 pleine précision)

> **Philosophie** : on veut le modèle le plus gros et le plus capable possible, même si c'est pour 2h de compute. Qualité maximale, pas d'économies sur la quantization.

| Critère | Détail |
|---------|--------|
| **Params** | 72B dense — **BF16 pleine précision** (pas de quantization) |
| **VRAM requise** | ~144 GB (nécessite multi-GPU) |
| **Vision** | Images, documents, vidéo, OCR, localisation UI (bounding boxes/points), résolution dynamique |
| **Tool calling** | Format natif Qwen, compatible OpenAI `tools` — chaînage multi-tours |
| **Code** | Entraîné sur du code, capable de générer/éditer du code structuré |
| **Licence** | Qwen License (commercial autorisé avec conditions) |
| **Écosystème** | Backbone de UI-TARS, supporté par vLLM et SGLang |

**Modèle encore plus gros à évaluer :**

| Modèle | Params | Actifs | VRAM BF16 | Statut |
|--------|--------|--------|-----------|--------|
| **Qwen3-VL-235B-A22B** | 235B MoE | 22B | ~470 GB | Si supporté par SGLang — potentiellement le plus capable de tous |
| **InternVL3.5-241B-A28B** | 241B MoE | 28B | ~480 GB | SOTA sur ScreenSpot-v2 (92.9%) |

> Ces modèles MoE nécessitent 8x H100 80GB (640 GB VRAM totale). À tester si Koyeb propose ce type d'instances.

**Pourquoi Qwen2.5-VL-72B comme baseline :**

| Alternative | Verdict |
|-------------|---------|
| Qwen3-VL-235B-A22B | Le candidat ultime si le support inference est mature. À tester en priorité. |
| UI-TARS-1.5-7B | Meilleur agent GUI pur (42.5% OSWorld) mais trop petit et conçu pour le pilotage d'interface, pas pour le dev agentique. |
| Qwen3-VL-72B | Plus récent (sept. 2025), mais le support SGLang/vLLM est moins mature. À réévaluer en phase 2. |
| Qwen2.5-VL-7B | Fallback uniquement — qualité insuffisante pour de l'inspection visuelle exigeante. |
| DeepSeek-V3.2 | Meilleur sur MCPMark (37%) mais text-only, pas de vision native. |

---

## Moteur d'inférence

### Retenu : SGLang

| Critère | Détail |
|---------|--------|
| **Débit** | 6.4x supérieur aux alternatives sur les workloads agentiques (multi-tours, tool calling) |
| **Pourquoi** | RadixAttention : réutilise le KV cache des préfixes communs entre les tours. Quand l'agent enchaîne 10-20 tool calls, le system prompt + historique + définitions d'outils sont recalculés une seule fois. |
| **API** | OpenAI-compatible (`/v1/chat/completions` avec `tools`) |
| **Multi-GPU** | Tensor parallelism natif |
| **Alternative** | vLLM si SGLang pose des problèmes de compatibilité avec Qwen2.5-VL-72B |

---

## Architecture

```
CLIENT (ta machine / CI / script)         KOYEB (scale-to-zero)
┌────────────────────────────┐            ┌────────────────────────┐
│                            │            │                        │
│  Agent Loop (Python)       │   HTTPS    │  SGLang                │
│                            │ ─────────► │  OpenAI-compatible API │
│  1. Construire le prompt   │            │                        │
│     (texte + images)       │ ◄───────── │  Qwen2.5-VL-72B       │
│                            │   JSON     │  2x A100 80GB          │
│  2. Appeler /v1/chat/      │            │  (tensor parallel=2)   │
│     completions            │            │                        │
│                            │            └────────────────────────┘
│  3. Si tool_call reçu :    │
│     - Exécuter localement  │
│       (lire fichier,       │
│        écrire code,        │
│        prendre screenshot, │
│        lancer commande)    │
│                            │
│  4. Renvoyer le résultat   │
│     au LLM                 │
│                            │
│  5. Boucler jusqu'à        │
│     réponse finale         │
│                            │
└────────────────────────────┘
```

**Principe clé** : le serveur Koyeb ne fait **que de l'inférence**. Toute l'exécution d'outils (filesystem, shell, screenshot) se fait côté client. Cela simplifie le déploiement, la sécurité, et le coût.

### Tools exposés au modèle (via function calling)

```json
[
  {
    "name": "read_file",
    "description": "Lire le contenu d'un fichier",
    "parameters": { "path": "string" }
  },
  {
    "name": "write_file",
    "description": "Écrire du contenu dans un fichier",
    "parameters": { "path": "string", "content": "string" }
  },
  {
    "name": "edit_file",
    "description": "Remplacer une portion de texte dans un fichier",
    "parameters": { "path": "string", "old_text": "string", "new_text": "string" }
  },
  {
    "name": "run_command",
    "description": "Exécuter une commande shell et retourner stdout/stderr",
    "parameters": { "command": "string", "timeout_seconds": "integer" }
  },
  {
    "name": "take_screenshot",
    "description": "Capturer l'écran ou une fenêtre et retourner l'image",
    "parameters": { "target": "string (full_screen | window_name | url)" }
  },
  {
    "name": "inspect_image",
    "description": "Le modèle reçoit une image pour analyse visuelle",
    "parameters": { "image_path": "string", "question": "string" }
  },
  {
    "name": "list_files",
    "description": "Lister les fichiers dans un répertoire",
    "parameters": { "path": "string", "pattern": "string" }
  },
  {
    "name": "search_code",
    "description": "Chercher un pattern dans les fichiers du projet",
    "parameters": { "pattern": "string", "path": "string", "file_glob": "string" }
  }
]
```

L'agent client reçoit ces tool calls, les exécute localement, et renvoie les résultats au LLM pour le tour suivant.

---

## Hardware Koyeb

### Configuration cible : le plus gros possible

| Paramètre | Valeur |
|-----------|--------|
| **GPU** | **4x H100 80GB** (si disponible) ou **2x A100 80GB** |
| **VRAM totale** | 320 GB (4x H100) ou 160 GB (2x A100) |
| **Précision** | **BF16 pleine précision** — pas de quantization |
| **Tensor Parallelism** | 4 (H100) ou 2 (A100) |
| **RAM CPU** | 128 GB |
| **Stockage** | 300 GB (poids modèle + KV cache) |
| **Scale-to-zero** | Oui — le service s'éteint après inactivité |
| **Cold start estimé** | 3-5 min (chargement 144 GB de poids depuis disque) |

### Configuration "modèle ultime" (si Koyeb propose 8x GPU)

| Paramètre | Valeur |
|-----------|--------|
| **GPU** | 8x H100 80GB (640 GB VRAM) |
| **Modèle** | Qwen3-VL-235B-A22B (MoE, ~470 GB BF16) |
| **TP** | 8 |
| **Avantage** | Le plus gros VLM open-weight existant, qualité maximale |
| **Cold start** | ~8-15 min |

### Fallback si les gros GPU ne sont pas disponibles

| Variante | GPU | Précision | Cold start |
|----------|-----|-----------|------------|
| Qwen2.5-VL-72B BF16 | 2x A100 80GB | BF16 | ~3-5 min |
| Qwen2.5-VL-72B AWQ INT4 | 1x A100 80GB | INT4 | ~2 min |
| Qwen2.5-VL-7B FP16 | 1x L40S 48GB | FP16 | ~30 s |

> **Recommandation** : viser d'abord **4x H100** avec le 72B BF16 (marge de VRAM pour un long contexte). Si indisponible, **2x A100 80GB** en BF16. La quantization est un dernier recours.

---

## Phases du POC

### Phase 1 — Inference nue sur Koyeb

**But** : le modèle tourne, répond aux requêtes vision + texte.

- [ ] Dockerfile : SGLang + CUDA 12.x + Qwen2.5-VL-72B-Instruct (BF16)
- [ ] Déploiement Koyeb GPU multi-GPU (4x H100 ou 2x A100 80GB)
- [ ] Valider `/v1/chat/completions` (texte seul)
- [ ] Valider vision : envoyer un screenshot, recevoir une description
- [ ] Valider tool calling : envoyer des tools, recevoir un `tool_call`
- [ ] Mesurer : TTFT, tokens/s, coût par requête

**Critère de succès** : le modèle retourne un `tool_call` structuré après analyse d'un screenshot.

### Phase 2 — Agent client avec tool calling

**But** : boucle agent complète côté client.

- [ ] Script Python client avec boucle agent (prompt → tool_call → exécution → résultat → prompt)
- [ ] Implémenter les tools : `read_file`, `write_file`, `edit_file`, `run_command`
- [ ] Implémenter `take_screenshot` (via Playwright ou scrot)
- [ ] Tester un scénario complet : "lis ce fichier, trouve le bug, corrige-le, lance les tests"
- [ ] Gérer les erreurs : timeout, tool call invalide, boucle infinie (max turns)

**Critère de succès** : l'agent corrige un bug simple dans un fichier Python en 3-5 tool calls sans intervention.

### Phase 3 — Inspection visuelle

**But** : l'agent analyse des captures d'écran pour détecter des anomalies.

- [ ] Envoyer des screenshots d'interfaces au modèle
- [ ] Tester la détection : éléments manquants, texte tronqué, erreurs visuelles, layout cassé
- [ ] Comparer les résultats Qwen2.5-VL-72B vs 7B pour évaluer le delta qualité
- [ ] Intégrer l'inspection visuelle dans la boucle agent (screenshot → analyse → action corrective)

**Critère de succès** : le modèle identifie correctement 80%+ des anomalies visuelles sur un jeu de test de 20 screenshots.

### Phase 4 — Optimisation scale-to-zero

- [ ] Mesurer et optimiser le cold start (pre-sharding, modèle sur SSD NVMe)
- [ ] Évaluer AWQ vs GPTQ vs BF16 (qualité vs vitesse vs VRAM)
- [ ] Tester Qwen3-VL comme drop-in replacement si SGLang le supporte
- [ ] Ajouter métriques : latence P50/P95, coût/tâche, taux de succès agent

---

## Stack technique

```
Serveur (Koyeb)
  Modèle       : Qwen2.5-VL-72B-Instruct (BF16 pleine précision)
  Cible ultime : Qwen3-VL-235B-A22B (si supporté)
  Inference    : SGLang (OpenAI-compatible API)
  GPU          : 4x H100 80GB (idéal) ou 2x A100 80GB (minimum)
  Container    : Docker (CUDA 12.x)
  Scale        : Scale-to-zero, facturation à la seconde

Client (local)
  Langage      : Python 3.11+
  Agent loop   : Custom (requests/httpx vers l'API SGLang)
  Tools        : subprocess, pathlib, Playwright (screenshots)
  Pas de dépendance MCP côté serveur
```

---

## Risques

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Cold start 3-5 min (72B BF16) | Inutilisable en interactif | Explorer le warm pool Koyeb. Acceptable pour du batch/async. |
| Koyeb n'offre pas 4x H100 | Config cible impossible | Fallback 2x A100 80GB. Ou AWQ INT4 sur 1x A100 en dernier recours. |
| SGLang incompatible Qwen2.5-VL-72B | Blocage | Fallback sur vLLM. Tester avant le déploiement Koyeb. |
| Tool calling pas assez fiable pour le chaînage | Agent bloqué | Max 20 tours, timeout par tour, validation JSON stricte du tool_call |
| Qwen3-VL-235B pas supporté par SGLang | Modèle ultime inaccessible | Rester sur le 72B BF16 qui est prouvé. Réévaluer quand le support mature. |
| Coût multi-GPU élevé | Budget | Monitoring coût/tâche. Usage limité à 2h/session. Scale-to-zero strict. |

---

## Décisions prises

- **Pas de serveur MCP** côté infra — l'exécution d'outils est côté client
- **Pas de fine-tuning** — on utilise le modèle tel quel (instruct)
- **Scale-to-zero** — le service dort quand il n'est pas utilisé
- **Qualité > latence** — on accepte quelques secondes par tour pour un meilleur raisonnement
- **BF16 pleine précision** — pas de quantization, viser la qualité maximale
- **Multi-GPU** — 4x H100 idéal, 2x A100 minimum
