# POC : Inference Open-Weight pour Inspection Visuelle & Dev Agentique — GCP

## Objectif

Déployer un LLM open-weight multimodal sur Google Cloud Platform (scale-to-zero) capable de :
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
| **Params** | 72B dense — **BF16 pleine précision** |
| **VRAM requise** | ~144 GB (nécessite multi-GPU) |
| **Vision** | Images, documents, vidéo, OCR, localisation UI (bounding boxes/points), résolution dynamique |
| **Tool calling** | Format natif Qwen, compatible OpenAI `tools` — chaînage multi-tours |
| **Code** | Entraîné sur du code, capable de générer/éditer du code structuré |
| **Licence** | Qwen License (commercial autorisé avec conditions) |
| **Écosystème** | Backbone de UI-TARS, supporté par vLLM et SGLang |

**Modèle encore plus gros à évaluer :**

| Modèle | Params | Actifs | VRAM BF16 | Statut |
|--------|--------|--------|-----------|--------|
| **Qwen3-VL-235B-A22B** | 235B MoE | 22B | ~470 GB | Si supporté par SGLang — potentiellement le plus capable |
| **InternVL3.5-241B-A28B** | 241B MoE | 28B | ~480 GB | SOTA sur ScreenSpot-v2 (92.9%) |

> Ces modèles MoE nécessitent 8x H100 80GB. GCP propose ces instances via GKE (a3-highgpu-8g).

**Pourquoi Qwen2.5-VL-72B comme baseline :**

| Alternative | Verdict |
|-------------|---------|
| Qwen3-VL-235B-A22B | Le candidat ultime si le support inference est mature. À tester en priorité. |
| UI-TARS-1.5-7B | Trop petit et conçu pour le pilotage d'interface, pas pour le dev agentique. |
| Qwen3-VL-72B | Plus récent (sept. 2025), support SGLang moins mature. À réévaluer. |
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
CLIENT (ta machine / CI / script)         GCP (scale-to-zero)
┌────────────────────────────┐            ┌────────────────────────┐
│                            │            │                        │
│  Agent Loop (Python)       │   HTTPS    │  SGLang                │
│                            │ ─────────► │  OpenAI-compatible API │
│  1. Construire le prompt   │            │                        │
│     (texte + images)       │ ◄───────── │  Qwen2.5-VL-72B       │
│                            │   JSON     │  GPU A100/L4/H100      │
│  2. Appeler /v1/chat/      │            │                        │
│     completions            │            └────────────────────────┘
│                            │
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

**Principe clé** : le serveur GCP ne fait **que de l'inférence**. Toute l'exécution d'outils (filesystem, shell, screenshot) se fait côté client.

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

---

## Infrastructure GCP — Options de déploiement

### Option A : Cloud Run GPU (recommandé — scale-to-zero natif)

Cloud Run supporte les GPU depuis 2024. C'est l'option la plus proche du modèle Koyeb (serverless, scale-to-zero, facturation à la requête).

| Paramètre | Valeur |
|-----------|--------|
| **Service** | Cloud Run (2nd gen) |
| **GPU** | NVIDIA L4 (24 GB) ou A100 (40/80 GB) |
| **Disponibilité GPU** | L4 : `us-central1`, `europe-west1` ; A100 : régions limitées |
| **Scale-to-zero** | Oui — natif Cloud Run |
| **Cold start** | Container pull + chargement modèle. L4/7B : ~1-2 min. A100/72B AWQ : ~3-5 min |
| **Facturation** | Par requête (CPU/RAM/GPU-seconds pendant l'exécution) |
| **Concurrence** | 1 requête par instance (modèle GPU = concurrence 1) |
| **Timeout max** | 60 min par requête |
| **Image Docker** | Custom (SGLang + modèle pré-téléchargé dans l'image ou GCS) |

**Limites Cloud Run GPU :**
- Max 1x GPU par instance (pas de tensor parallelism multi-GPU)
- L4 = 24 GB VRAM → contraint au 7B FP16 ou 72B INT4 très agressif
- A100 40 GB → 72B AWQ INT4 serré (~40 GB), ou 7B FP16 confortable
- A100 80 GB → 72B AWQ INT4 confortable

**Configuration recommandée pour le POC :**

```yaml
# Cloud Run service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: visual-agent-llm
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/gpu-type: "nvidia-a100-80gb"
        run.googleapis.com/gpu-count: "1"
        autoscaling.knative.dev/minScale: "0"
        autoscaling.knative.dev/maxScale: "1"
    spec:
      containerConcurrency: 1
      timeoutSeconds: 3600
      containers:
        - image: gcr.io/PROJECT/visual-agent-sglang:latest
          ports:
            - containerPort: 8080
          resources:
            limits:
              cpu: "8"
              memory: "64Gi"
              nvidia.com/gpu: "1"
          env:
            - name: MODEL_NAME
              value: "Qwen/Qwen2.5-VL-72B-Instruct-AWQ"
```

### Option B : GKE Autopilot + GPU

Pour le multi-GPU (tensor parallelism sur 72B BF16), GKE est nécessaire.

| Paramètre | Valeur |
|-----------|--------|
| **Service** | GKE Autopilot |
| **GPU** | 2x A100 80GB ou 2x H100 80GB |
| **Scale-to-zero** | Via KEDA ou HPA custom (scale to 0 pods) |
| **Cold start** | Pod scheduling + image pull + modèle : 5-10 min |
| **Facturation** | Par pod (GPU réservé tant que le pod tourne) |
| **Tensor Parallelism** | 2 ou 4 (multi-GPU dans un même noeud) |

**Configuration GKE :**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: visual-agent-sglang
spec:
  replicas: 0  # scale-to-zero via KEDA
  template:
    spec:
      containers:
        - name: sglang
          image: gcr.io/PROJECT/visual-agent-sglang:latest
          command:
            - python
            - -m
            - sglang.launch_server
            - --model-path=Qwen/Qwen2.5-VL-72B-Instruct
            - --tp=2
            - --port=8080
          resources:
            limits:
              nvidia.com/gpu: "2"
              memory: "128Gi"
              cpu: "16"
      nodeSelector:
        cloud.google.com/gke-accelerator: nvidia-tesla-a100
      tolerations:
        - key: nvidia.com/gpu
          operator: Exists
          effect: NoSchedule
---
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: visual-agent-scaler
spec:
  scaleTargetRef:
    name: visual-agent-sglang
  minReplicaCount: 0
  maxReplicaCount: 1
  triggers:
    - type: prometheus
      metadata:
        query: sum(rate(http_requests_total{service="visual-agent"}[5m]))
        threshold: "0.01"
```

### Option C : Vertex AI (endpoint custom)

| Paramètre | Valeur |
|-----------|--------|
| **Service** | Vertex AI Custom Prediction |
| **GPU** | A100 / H100 |
| **Scale-to-zero** | Oui (min replicas = 0) |
| **Cold start** | 5-15 min (provisioning + modèle) |
| **Avantage** | Intégration monitoring, IAM, VPC, logs natifs |
| **Inconvénient** | Overhead Vertex, moins de contrôle sur le container |

---

## Comparaison des options GCP

| Critère | Cloud Run GPU | GKE Autopilot | Vertex AI |
|---------|--------------|---------------|-----------|
| **Scale-to-zero** | Natif | Via KEDA | Natif |
| **Multi-GPU** | Non (1 GPU max) | **Oui (jusqu'à 8x H100)** | Oui |
| **Cold start** | 2-5 min | 5-10 min | 5-15 min |
| **Simplicité** | Très simple | Complexe | Moyen |
| **72B BF16** | Non (1 GPU) | **Oui (2-4x H100/A100)** | Oui |
| **235B MoE** | Non | **Oui (8x H100)** | Possible |
| **Coût idle** | $0 | $0 (KEDA) | $0 |
| **Coût/heure GPU** | ~$3.5/h (A100) | ~$12-25/h (multi-H100) | Variable |

**Recommandation** : **GKE avec 4x H100 80GB** (`a3-highgpu-4g`) pour le 72B BF16 avec marge VRAM. Scale-to-zero via KEDA. Si le Qwen3-VL-235B est visé, passer à `a3-highgpu-8g` (8x H100).

---

## Hardware GCP

### Configuration cible (GKE — le plus gros possible)

| Paramètre | Valeur |
|-----------|--------|
| **Service** | GKE Autopilot |
| **GPU** | **4x H100 80GB** (`a3-highgpu-4g`) |
| **VRAM totale** | 320 GB |
| **Modèle** | Qwen2.5-VL-72B-Instruct **BF16** (~144 GB) — marge pour long contexte |
| **Tensor Parallelism** | 4 |
| **RAM CPU** | 128 GB |
| **Scale-to-zero** | Via KEDA (0 pods quand inactif) |
| **Cold start** | ~5-10 min (scheduling pod + chargement modèle) |
| **Région** | `us-central1` |

### Configuration "modèle ultime" (8x H100)

| Paramètre | Valeur |
|-----------|--------|
| **GPU** | **8x H100 80GB** (`a3-highgpu-8g`) |
| **VRAM totale** | 640 GB |
| **Modèle** | Qwen3-VL-235B-A22B (MoE, ~470 GB BF16) |
| **TP** | 8 |
| **Cold start** | ~10-15 min |
| **Coût/h** | ~$25-30/h |

### Fallback si les H100 ne sont pas disponibles

| Variante | GPU | Précision | Cold start | Coût/h |
|----------|-----|-----------|------------|--------|
| Qwen2.5-VL-72B BF16 | 2x A100 80GB | BF16 | ~5-8 min | ~$7/h |
| Qwen2.5-VL-72B AWQ | 1x A100 80GB (Cloud Run) | INT4 | ~3-5 min | ~$3.5/h |
| Qwen2.5-VL-7B FP16 | 1x L4 24GB (Cloud Run) | FP16 | ~1-2 min | ~$0.7/h |

### Optimisation cold start GCP

- **Artifact Registry** : stocker l'image Docker dans la même région que le service
- **GCS FUSE** : monter les poids depuis un bucket GCS (~144 GB BF16, bande passante ~100 Gbps sur H100 nodes)
- **Image pré-buildée** : pour les modèles plus petits. Le 72B BF16 (~144 GB) est trop lourd pour une image Docker.
- **Node pool réservé** : réserver 1 noeud `a3-highgpu-4g` pour réduire le cold start (mais coût continu ~$25/h)

---

## Phases du POC

### Phase 1 — Inference nue sur GCP Cloud Run

**But** : le modèle tourne, répond aux requêtes vision + texte.

- [ ] Dockerfile : SGLang + CUDA 12.x + Qwen2.5-VL-72B-Instruct (BF16)
- [ ] Push image vers Artifact Registry (`gcr.io/PROJECT/visual-agent-sglang`)
- [ ] Déployer GKE Autopilot avec 4x H100 80GB (`a3-highgpu-4g`, `us-central1`)
- [ ] Valider `/v1/chat/completions` (texte seul)
- [ ] Valider vision : envoyer un screenshot, recevoir une description
- [ ] Valider tool calling : envoyer des tools, recevoir un `tool_call`
- [ ] Mesurer : TTFT, tokens/s, cold start, coût par requête

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

- [ ] Mesurer et optimiser le cold start (image pré-buildée vs GCS FUSE)
- [ ] Évaluer AWQ vs GPTQ vs BF16 (qualité vs vitesse vs VRAM)
- [ ] Tester Qwen3-VL comme drop-in replacement si SGLang le supporte
- [ ] Si multi-GPU nécessaire : migrer vers GKE Autopilot avec KEDA
- [ ] Ajouter métriques : latence P50/P95, coût/tâche, taux de succès agent

---

## Stack technique

```
Serveur (GCP GKE)
  Modèle       : Qwen2.5-VL-72B-Instruct (BF16 pleine précision)
  Cible ultime : Qwen3-VL-235B-A22B (si supporté, 8x H100)
  Inference    : SGLang (OpenAI-compatible API)
  GPU          : 4x H100 80GB (a3-highgpu-4g) — TP=4
  Container    : Docker (CUDA 12.x), Artifact Registry
  Scale        : Scale-to-zero via KEDA
  Région       : us-central1

Client (local)
  Langage      : Python 3.11+
  Agent loop   : Custom (requests/httpx vers l'API SGLang)
  Tools        : subprocess, pathlib, Playwright (screenshots)
  Pas de dépendance MCP côté serveur
```

---

## Coûts estimés GCP

| Scénario | Config | Coût/heure active | Coût idle | Coût estimé/mois (2h/jour) |
|----------|--------|-------------------|-----------|---------------------------|
| **Recommandé** | GKE 4x H100 + 72B BF16 | ~$25/h | $0 (KEDA) | ~$1500/mois |
| Ultime | GKE 8x H100 + 235B MoE | ~$50/h | $0 (KEDA) | ~$3000/mois |
| Fallback | GKE 2x A100 + 72B BF16 | ~$7/h | $0 (KEDA) | ~$420/mois |
| Budget | Cloud Run 1x A100 + 72B AWQ | ~$3.50/h | $0 | ~$210/mois |

> Facturation GCP : par seconde d'utilisation GPU. Avec KEDA scale-to-zero, pas de coût quand le service dort. Pour 2h/jour, le coût réel est contrôlé.

---

## Risques

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Cold start 3-5 min (Cloud Run + 72B) | Inutilisable en interactif | Image pré-buildée avec poids. Fallback L4/7B (~1 min). Min instances=1 si budget le permet. |
| Cloud Run GPU limité à 1x GPU | Pas de tensor parallelism | Utiliser AWQ INT4 (tient sur 1x A100 80GB). Passer à GKE pour multi-GPU. |
| Quota GPU insuffisant dans la région | Déploiement bloqué | Demander quota increase sur `us-central1`. Avoir `europe-west1` en fallback. |
| SGLang incompatible Qwen2.5-VL-72B | Blocage | Fallback sur vLLM. Tester en local avant le déploiement GCP. |
| Tool calling pas assez fiable | Agent bloqué | Max 20 tours, timeout par tour, validation JSON stricte du tool_call |
| Image Docker trop grosse (40+ GB) | Cold start long | Utiliser GCS FUSE pour charger les poids séparément. Multi-stage build. |

---

## Décisions prises

- **Pas de serveur MCP** côté infra — l'exécution d'outils est côté client
- **Pas de fine-tuning** — on utilise le modèle tel quel (instruct)
- **Scale-to-zero** — Cloud Run natif (ou GKE + KEDA)
- **Qualité > latence** — on accepte quelques secondes par tour pour un meilleur raisonnement
- **BF16 pleine précision** — pas de quantization, viser la qualité maximale
- **Multi-GPU** — 4x H100 via GKE, 8x H100 pour le modèle ultime (235B MoE)
- **Région `us-central1`** pour la meilleure disponibilité GPU
