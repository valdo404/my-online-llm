# POC : Inference Open-Weight pour Inspection Visuelle & Dev Agentique — AWS

## Objectif

Déployer un LLM open-weight multimodal sur AWS (scale-to-zero) capable de :
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

> Ces modèles MoE nécessitent 8x H100 80GB. AWS propose `p5.48xlarge` (8x H100 80GB, 640 GB VRAM).

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
CLIENT (ta machine / CI / script)         AWS (scale-to-zero)
┌────────────────────────────┐            ┌────────────────────────┐
│                            │            │                        │
│  Agent Loop (Python)       │   HTTPS    │  SGLang                │
│                            │ ─────────► │  OpenAI-compatible API │
│  1. Construire le prompt   │            │                        │
│     (texte + images)       │ ◄───────── │  Qwen2.5-VL-72B       │
│                            │   JSON     │  GPU A100/A10G/H100    │
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

**Principe clé** : le serveur AWS ne fait **que de l'inférence**. Toute l'exécution d'outils (filesystem, shell, screenshot) se fait côté client.

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

## Infrastructure AWS — Options de déploiement

### Option A : SageMaker Inference (endpoint async — recommandé)

SageMaker permet de déployer des modèles custom avec scale-to-zero natif via les endpoints asynchrones.

| Paramètre | Valeur |
|-----------|--------|
| **Service** | SageMaker Async Inference Endpoint |
| **GPU** | `ml.g5.12xlarge` (4x A10G, 96 GB VRAM) ou `ml.p4d.24xlarge` (8x A100 40GB) |
| **Scale-to-zero** | Oui — natif SageMaker Async (min instances = 0) |
| **Cold start** | Instance provisioning + modèle S3 download : 5-10 min |
| **Facturation** | Par seconde d'instance active |
| **Avantage** | Intégration IAM, CloudWatch, VPC, S3, modèle versionné |
| **Inconvénient** | Overhead SageMaker, cold start long, async uniquement pour scale-to-zero |

**Instances GPU recommandées :**

| Instance | GPU | VRAM | Convient pour | Coût/h (on-demand) |
|----------|-----|------|---------------|---------------------|
| `ml.g5.2xlarge` | 1x A10G | 24 GB | 7B FP16 | ~$1.50/h |
| `ml.g5.12xlarge` | 4x A10G | 96 GB | 72B AWQ INT4 (TP=4) | ~$7.00/h |
| `ml.g5.48xlarge` | 8x A10G | 192 GB | 72B BF16 (TP=8) | ~$16.00/h |
| `ml.p4d.24xlarge` | 8x A100 40GB | 320 GB | 72B BF16 (TP=2, surplus) | ~$32.00/h |
| `ml.p5.48xlarge` | 8x H100 80GB | 640 GB | Overkill pour ce POC | ~$65.00/h |

**Configuration SageMaker recommandée :**

```python
import sagemaker
from sagemaker.model import Model

model = Model(
    image_uri="YOUR_ECR_IMAGE",  # SGLang + Qwen2.5-VL-72B-AWQ
    role="arn:aws:iam::ACCOUNT:role/SageMakerRole",
    model_data="s3://bucket/models/Qwen2.5-VL-72B-Instruct-AWQ/",
    env={
        "MODEL_NAME": "Qwen/Qwen2.5-VL-72B-Instruct-AWQ",
        "TENSOR_PARALLEL": "4",
        "PORT": "8080",
    },
)

async_config = sagemaker.async_inference.AsyncInferenceConfig(
    output_path="s3://bucket/inference-output/",
    max_concurrent_invocations_per_instance=1,
)

predictor = model.deploy(
    instance_type="ml.g5.12xlarge",
    initial_instance_count=0,  # scale-to-zero
    async_inference_config=async_config,
    endpoint_name="visual-agent-llm",
)
```

### Option B : ECS Fargate + EC2 GPU (meilleur contrôle)

ECS permet plus de contrôle sur le container et le réseau, avec auto-scaling custom.

| Paramètre | Valeur |
|-----------|--------|
| **Service** | ECS sur EC2 GPU (pas Fargate — Fargate n'a pas de GPU) |
| **GPU** | `g5.2xlarge` (1x A10G) à `p4d.24xlarge` (8x A100) |
| **Scale-to-zero** | Via capacity provider + custom scaling (moins natif) |
| **Cold start** | EC2 launch + container start + modèle : 3-8 min |
| **Facturation** | Par seconde d'instance EC2 |
| **Avantage** | Flexibilité totale, Spot instances possibles (-60-70% coût) |
| **Inconvénient** | Plus complexe à configurer, scale-to-zero moins propre |

**Configuration ECS :**

```json
{
  "family": "visual-agent-sglang",
  "requiresCompatibilities": ["EC2"],
  "containerDefinitions": [
    {
      "name": "sglang",
      "image": "ACCOUNT.dkr.ecr.REGION.amazonaws.com/visual-agent-sglang:latest",
      "command": [
        "python", "-m", "sglang.launch_server",
        "--model-path", "/models/Qwen2.5-VL-72B-Instruct-AWQ",
        "--tp", "4",
        "--port", "8080"
      ],
      "resourceRequirements": [
        { "type": "GPU", "value": "4" }
      ],
      "memory": 65536,
      "cpu": 16384,
      "portMappings": [
        { "containerPort": 8080, "protocol": "tcp" }
      ]
    }
  ]
}
```

**Spot instances** : `g5.12xlarge` Spot = ~$2-3/h vs ~$7/h on-demand. Excellent pour du batch/async. Risque d'interruption mitigé par le fait que l'agent est stateless (pas de state côté serveur).

### Option C : Lambda + EFS (expérimental, petits modèles uniquement)

| Paramètre | Valeur |
|-----------|--------|
| **Service** | Lambda avec GPU (preview 2025) |
| **GPU** | Limité aux petits modèles |
| **Scale-to-zero** | Natif Lambda |
| **Convient pour** | 7B quantifié maximum. Pas viable pour 72B. |

> Non recommandé pour ce POC — Lambda GPU est encore trop limité pour des modèles 72B.

### Option D : Bedrock Custom Model Import

| Paramètre | Valeur |
|-----------|--------|
| **Service** | Amazon Bedrock |
| **Import** | Custom Model Import (supporte Qwen/LLaMA/Mistral architectures) |
| **Scale-to-zero** | Non garanti (Bedrock gère le scaling) |
| **Avantage** | Zéro infra à gérer, API Bedrock standard |
| **Inconvénient** | Moins de contrôle, pricing opaque, support VLM custom incertain |

> À explorer mais pas recommandé pour le POC initial — trop de dépendance au support Bedrock pour Qwen2.5-VL.

---

## Comparaison des options AWS

| Critère | SageMaker Async | ECS + EC2 GPU | Lambda GPU | Bedrock Import |
|---------|----------------|---------------|------------|----------------|
| **Scale-to-zero** | Natif | Custom (complexe) | Natif | Non garanti |
| **Multi-GPU** | Oui | Oui | Non | N/A |
| **Cold start** | 5-10 min | 3-8 min | ~1 min (7B) | Inconnu |
| **Simplicité** | Moyen | Complexe | Simple | Très simple |
| **72B AWQ** | Oui (g5.12xlarge) | Oui | Non | Peut-être |
| **7B FP16** | Oui (g5.2xlarge) | Oui | Peut-être | Peut-être |
| **Coût idle** | $0 | ~$0 (avec effort) | $0 | Variable |
| **Spot instances** | Non | Oui (-60-70%) | Non | Non |
| **Coût/h GPU** | ~$7/h (g5.12xlarge) | ~$2-3/h (Spot) | N/A | Variable |

**Recommandation** : **ECS + EC2 GPU** avec `p5.48xlarge` (8x H100) pour le modèle le plus gros possible. Scale-to-zero custom via capacity provider. Spot instances si disponibles pour réduire le coût.

---

## Hardware AWS

### Configuration cible : le plus gros possible

| Paramètre | Valeur |
|-----------|--------|
| **Instance** | **`p5.48xlarge`** (8x H100 80GB) |
| **GPU** | 8x NVIDIA H100 80GB |
| **VRAM totale** | **640 GB** |
| **Modèle** | Qwen2.5-VL-72B-Instruct **BF16** (~144 GB) — marge massive pour long contexte |
| **Tensor Parallelism** | 4 ou 8 |
| **RAM CPU** | 2 TB |
| **Stockage** | Modèle sur S3 ou EBS snapshot |
| **Scale-to-zero** | ECS capacity provider (terminate instance quand idle) |
| **Cold start** | ~5-8 min (EC2 launch + container + modèle) |
| **Région** | `us-east-1` |
| **Coût/h** | ~$65/h (on-demand), ~$25-30/h (Spot si disponible) |

### Configuration "modèle ultime" (235B MoE)

| Paramètre | Valeur |
|-----------|--------|
| **Instance** | `p5.48xlarge` (8x H100 80GB, 640 GB VRAM) |
| **Modèle** | Qwen3-VL-235B-A22B (MoE, ~470 GB BF16) |
| **TP** | 8 |
| **Avantage** | Le plus gros VLM open-weight existant sur le plus gros GPU AWS |

### Alternatives

| Variante | Instance | GPU | VRAM | Précision | Coût/h |
|----------|----------|-----|------|-----------|--------|
| **72B BF16 (recommandé)** | `p4d.24xlarge` | 8x A100 40GB | 320 GB | BF16 | ~$32/h |
| 72B BF16 (min) | `p4de.24xlarge` | 8x A100 80GB | 640 GB | BF16 | ~$40/h |
| 72B BF16 H100 | `p5.48xlarge` | 8x H100 80GB | 640 GB | BF16 | ~$65/h |
| 72B AWQ fallback | `g5.12xlarge` | 4x A10G | 96 GB | INT4 | ~$7/h |
| 7B FP16 budget | `g5.2xlarge` | 1x A10G | 24 GB | FP16 | ~$1.50/h |

### Optimisation cold start AWS

- **S3 → instance** : les poids (~144 GB BF16) sont téléchargés depuis S3 au démarrage. Bande passante : 100 Gbps sur p5 → ~12s pour 144 GB.
- **EBS snapshot** : pré-charger les poids sur un snapshot EBS io2 attaché à l'instance. Élimine le download S3.
- **FSx for Lustre** : filesystem parallèle haute performance, idéal pour charger rapidement des poids depuis S3.
- **Capacity Reservations** : réserver une instance p5 pour garantir la disponibilité (coût même quand idle, mais instantané).
- **Spot instances** : `p5.48xlarge` Spot = ~$25-30/h vs ~$65/h on-demand. Interruptions possibles mais l'agent est stateless.

---

## Phases du POC

### Phase 1 — Inference nue sur AWS

**But** : le modèle tourne, répond aux requêtes vision + texte.

- [ ] Dockerfile : SGLang + CUDA 12.x + Qwen2.5-VL-72B-Instruct (BF16)
- [ ] Push image vers ECR
- [ ] Upload poids modèle sur S3 (ou préparer EBS snapshot)
- [ ] Déployer ECS + EC2 GPU (`p4d.24xlarge` 8x A100 ou `p5.48xlarge` 8x H100)
- [ ] Valider `/v1/chat/completions` (texte seul) via le endpoint
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
- [ ] Adapter le client pour l'API async SageMaker (polling S3 output)

**Critère de succès** : l'agent corrige un bug simple dans un fichier Python en 3-5 tool calls sans intervention.

### Phase 3 — Inspection visuelle

**But** : l'agent analyse des captures d'écran pour détecter des anomalies.

- [ ] Envoyer des screenshots d'interfaces au modèle
- [ ] Tester la détection : éléments manquants, texte tronqué, erreurs visuelles, layout cassé
- [ ] Comparer les résultats Qwen2.5-VL-72B vs 7B pour évaluer le delta qualité
- [ ] Intégrer l'inspection visuelle dans la boucle agent (screenshot → analyse → action corrective)

**Critère de succès** : le modèle identifie correctement 80%+ des anomalies visuelles sur un jeu de test de 20 screenshots.

### Phase 4 — Optimisation coût et cold start

- [ ] Évaluer ECS + Spot vs SageMaker (économie de 60-70%)
- [ ] Optimiser le cold start (EBS snapshot, SageMaker Fast Launch)
- [ ] Évaluer AWQ vs GPTQ vs BF16 (qualité vs vitesse vs VRAM)
- [ ] Tester Qwen3-VL comme drop-in replacement si SGLang le supporte
- [ ] Ajouter métriques CloudWatch : latence P50/P95, coût/tâche, taux de succès agent

---

## Stack technique

```
Serveur (AWS)
  Modèle       : Qwen2.5-VL-72B-Instruct (BF16 pleine précision)
  Cible ultime : Qwen3-VL-235B-A22B (si supporté, 8x H100)
  Inference    : SGLang (OpenAI-compatible API)
  GPU          : 8x H100 80GB (p5.48xlarge) ou 8x A100 40GB (p4d.24xlarge)
  Container    : Docker (CUDA 12.x), ECR
  Compute      : ECS + EC2 GPU (scale-to-zero via capacity provider)
  Stockage     : S3 / EBS snapshot / FSx Lustre
  Alternative  : SageMaker Async pour plus de simplicité

Client (local)
  Langage      : Python 3.11+
  Agent loop   : Custom (requests/httpx vers l'endpoint ECS)
  Tools        : subprocess, pathlib, Playwright (screenshots)
  Pas de dépendance MCP côté serveur
```

---

## Coûts estimés AWS

| Scénario | Config | Coût/h active | Coût idle | Coût estimé/mois (2h/jour) |
|----------|--------|---------------|-----------|---------------------------|
| **Recommandé** | ECS p4d.24xlarge (8x A100) | ~$32/h | $0 | ~$1920/mois |
| Maximum | ECS p5.48xlarge (8x H100) | ~$65/h | $0 | ~$3900/mois |
| Max + Spot | ECS p5.48xlarge Spot | ~$25-30/h | $0 | ~$1650/mois |
| Fallback | ECS g5.12xlarge (4x A10G, AWQ) | ~$7/h | $0 | ~$420/mois |
| Budget | ECS g5.2xlarge Spot (7B) | ~$0.50/h | $0 | ~$30/mois |

> **Note** : AWS est le plus cher des trois clouds pour ce use case, mais offre les plus grosses instances GPU (p5.48xlarge = 8x H100). Les Spot instances réduisent le coût de 50-60% sur les p5.

---

## Risques

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Cold start 5-10 min (SageMaker + 72B) | Inutilisable en interactif | SageMaker Fast Launch. EBS snapshot. Fallback g5.2xlarge/7B (~2 min). |
| Coût AWS plus élevé que Koyeb/GCP | Budget | ECS + Spot instances pour -60-70%. Commencer par 7B. |
| Spot instance interrompue | Agent interrompu | Agent est stateless côté serveur. Re-envoyer la requête. Checkpointing côté client. |
| SageMaker Async ajoute de la latence (S3 polling) | UX dégradée | Polling agressif (1s interval). Ou passer à Real-Time endpoint (mais pas de scale-to-zero). |
| SGLang incompatible Qwen2.5-VL-72B sur A10G | Blocage | Fallback sur vLLM. Tester en local. Alternative : p4d.24xlarge (A100). |
| Quota GPU insuffisant | Déploiement bloqué | Demander quota increase `us-east-1`. Avoir `us-west-2` en fallback. |

---

## Décisions prises

- **Pas de serveur MCP** côté infra — l'exécution d'outils est côté client
- **Pas de fine-tuning** — on utilise le modèle tel quel (instruct)
- **Scale-to-zero** — SageMaker Async (natif) ou ECS + custom scaling
- **Qualité > latence** — on accepte quelques secondes par tour pour un meilleur raisonnement
- **BF16 pleine précision** — pas de quantization, viser la qualité maximale
- **Multi-GPU** — 8x A100 (p4d) ou 8x H100 (p5) pour le 72B avec marge
- **ECS + EC2 GPU** plutôt que SageMaker pour le contrôle et les Spot instances
- **Spot instances** pour réduire le coût de 50-60%
- **Région `us-east-1`** pour la meilleure disponibilité GPU
