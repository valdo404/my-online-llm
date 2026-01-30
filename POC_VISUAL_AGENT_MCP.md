# POC : Visual Agentic LLM + MCP sur Koyeb

## Objectif

Déployer un LLM open-weight multimodal capable de :
1. **Percevoir** des captures d'écran (desktop, mobile, web)
2. **Raisonner** sur les actions à effectuer (clic, saisie, navigation)
3. **Exploiter MCP** (Model Context Protocol) pour interagir avec des outils externes (bases de données, APIs, navigateur, filesystem, etc.)
4. Tourner sur **infrastructure Koyeb** avec démarrage à la demande

---

## Choix technologiques

### Modèle : Qwen2.5-VL-72B-Instruct

| Critère | Décision |
|---------|----------|
| **Modèle retenu** | `Qwen/Qwen2.5-VL-72B-Instruct` |
| **Pourquoi pas UI-TARS** | UI-TARS-1.5-7B est le meilleur agent GUI pur (42.5% OSWorld), mais son tool calling MCP est limité au framework UI-TARS Desktop. Qwen2.5-VL-72B combine vision + tool calling natif de qualité production, et sert de backbone à UI-TARS lui-même. |
| **Pourquoi pas Qwen3-VL** | Qwen3-VL est plus récent (sept. 2025) mais l'écosystème d'inférence (vLLM, SGLang) est plus mature pour Qwen2.5-VL. Le 72B est un compromis qualité/déployabilité. |
| **Alternative si budget limité** | Qwen2.5-VL-7B (même architecture, tient sur un seul GPU 24 GB) |
| **Alternative MoE** | Qwen3-VL-30B-A3B (30B params, seulement 3B actifs — excellent ratio qualité/coût) |
| **Licence** | Qwen License (usage commercial autorisé avec conditions) — les variantes 3B/7B sont Apache 2.0 |

**Capacités clés du modèle :**
- Vision : images, documents, vidéo (1h+), OCR, localisation d'éléments UI (bounding boxes, points)
- Agent : entraîné sur des screenshots d'interfaces (mobile, web, desktop) avec annotations d'éléments
- Tool calling : format natif Qwen pour function calling, compatible OpenAI tool format
- Résolution dynamique : adapte automatiquement la résolution d'entrée

### Moteur d'inférence : SGLang

| Critère | Décision |
|---------|----------|
| **Moteur retenu** | SGLang |
| **Pourquoi** | **6.4x plus de débit** et **3.7x moins de latence** que les alternatives sur les workloads agentic/tool-calling, grâce à RadixAttention (réutilisation du KV cache entre les tours de conversation MCP) |
| **Alternative** | vLLM (meilleur time-to-first-token, écosystème plus large) |
| **API exposée** | OpenAI-compatible (`/v1/chat/completions` avec tools) |
| **Multi-GPU** | Tensor parallelism natif (2x ou 4x GPU pour le 72B) |

**Pourquoi SGLang est critique pour MCP :**
MCP implique des conversations multi-tours avec appels d'outils répétés. À chaque tour, le contexte (system prompt + historique + définitions d'outils) est largement identique. RadixAttention de SGLang réutilise le KV cache de ces préfixes communs, réduisant drastiquement le calcul redondant.

### Couche MCP : MCP-Bridge + Qwen-Agent

| Composant | Rôle |
|-----------|------|
| **MCP-Bridge** | Proxy HTTP entre l'API OpenAI-compatible de SGLang et les MCP Servers. Injecte automatiquement les définitions d'outils MCP dans chaque requête. |
| **Qwen-Agent** | Framework agent natif Qwen avec support MCP intégré, Code Interpreter, et RAG. Utilisé comme orchestrateur de haut niveau. |
| **MCP Servers** | Playwright (navigation web), Filesystem, PostgreSQL, et custom servers selon les besoins |

---

## Architecture du POC

```
┌─────────────────────────────────────────────────────────────┐
│                        KOYEB                                │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  MCP Servers  │    │  MCP-Bridge  │    │   SGLang     │  │
│  │              │    │   (proxy)    │    │  (inference)  │  │
│  │ - Playwright │◄──►│              │◄──►│              │  │
│  │ - Filesystem │    │  Injecte les │    │ Qwen2.5-VL   │  │
│  │ - PostgreSQL │    │  tools MCP   │    │    -72B      │  │
│  │ - Custom     │    │  dans les    │    │              │  │
│  │              │    │  requêtes    │    │ 2-4x GPU     │  │
│  └──────────────┘    └──────────────┘    │ (A100/H100)  │  │
│                                          └──────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  Qwen-Agent                           │  │
│  │           (orchestrateur / agent loop)                │  │
│  │                                                       │  │
│  │  1. Reçoit une tâche utilisateur                     │  │
│  │  2. Prend un screenshot (via MCP Playwright)         │  │
│  │  3. Envoie screenshot + contexte au LLM (SGLang)     │  │
│  │  4. LLM retourne une action (clic, saisie, tool call)│  │
│  │  5. Exécute l'action via MCP Server approprié        │  │
│  │  6. Boucle jusqu'à complétion                        │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Hardware Koyeb

### Configuration cible pour Qwen2.5-VL-72B

| Paramètre | Valeur |
|-----------|--------|
| **GPU** | 2x A100 80GB ou 4x L40S 48GB |
| **VRAM totale** | 160 GB (2x A100) ou 192 GB (4x L40S) |
| **Précision** | BF16 (72B ≈ 144 GB) ou INT8 (≈ 72 GB, 1x A100 possible) |
| **RAM CPU** | 64 GB minimum |
| **Stockage** | 200 GB (poids du modèle + cache) |
| **Tensor Parallelism** | 2 (2x A100) ou 4 (4x L40S) |

### Configuration alternative (budget réduit)

| Variante | GPU | Estimation coût/heure |
|----------|-----|----------------------|
| Qwen2.5-VL-72B INT4 | 1x A100 80GB | ~$2-3/h |
| Qwen2.5-VL-7B FP16 | 1x L40S 48GB | ~$1-1.5/h |
| Qwen3-VL-30B-A3B | 1x L40S 48GB | ~$1-1.5/h (MoE, rapide) |

> **Note** : Koyeb facture à la seconde avec scale-to-zero. Le modèle ne coûte rien quand il ne tourne pas, mais le cold start (chargement des poids) prend 2-5 minutes pour un 72B.

---

## Phases du POC

### Phase 1 — Inference de base (Semaine 1)

**Objectif** : Faire tourner Qwen2.5-VL-72B sur Koyeb avec SGLang

- [ ] Créer un Dockerfile avec SGLang + dépendances Qwen2.5-VL
- [ ] Configurer le déploiement Koyeb multi-GPU
- [ ] Valider l'API OpenAI-compatible (`/v1/chat/completions`)
- [ ] Tester l'inférence vision : envoyer une image + prompt, recevoir une réponse
- [ ] Mesurer latence (TTFT, tokens/s) et coût

**Critère de succès** : Le modèle répond correctement à une question sur une capture d'écran en < 10s.

### Phase 2 — MCP Integration (Semaine 2)

**Objectif** : Connecter le LLM à des outils via MCP

- [ ] Déployer MCP-Bridge en tant que proxy devant SGLang
- [ ] Configurer un MCP Server Filesystem (lecture/écriture de fichiers)
- [ ] Configurer un MCP Server PostgreSQL (requêtes SQL)
- [ ] Valider le cycle complet : requête → LLM décide d'appeler un outil → MCP-Bridge route vers le MCP Server → résultat retourné au LLM → réponse finale
- [ ] Tester avec 3-5 scénarios de tool calling

**Critère de succès** : Le LLM utilise spontanément les outils MCP pour répondre à des questions nécessitant des données externes.

### Phase 3 — Visual Agentic (Semaine 3)

**Objectif** : Agent visuel complet qui navigue dans une interface

- [ ] Ajouter MCP Server Playwright (contrôle navigateur)
- [ ] Implémenter la boucle agent avec Qwen-Agent :
  - Screenshot → Analyse → Action → Screenshot → ...
- [ ] Tester sur un scénario web simple (ex : recherche Google, remplir un formulaire)
- [ ] Implémenter le grounding visuel (clic sur coordonnées précises)
- [ ] Ajouter la gestion d'erreurs et les retries

**Critère de succès** : L'agent complète une tâche web en 5+ étapes sans intervention humaine.

### Phase 4 — Optimisation et production (Semaine 4)

- [ ] Optimiser le cold start (pré-chargement, quantization)
- [ ] Ajouter des métriques (latence, coût, taux de succès)
- [ ] Évaluer le passage à Qwen3-VL si le support SGLang est mature
- [ ] Comparer avec UI-TARS-1.5-7B en mode quantifié pour les tâches GUI pures
- [ ] Documenter l'architecture finale

---

## Stack technique résumé

```
Langage      : Python 3.11+
Modèle       : Qwen2.5-VL-72B-Instruct (HuggingFace)
Inference    : SGLang (OpenAI-compatible API)
MCP Bridge   : MCP-Bridge (github.com/SecretiveShell/MCP-Bridge)
Agent        : Qwen-Agent (github.com/QwenLM/Qwen-Agent)
MCP Servers  : Playwright, Filesystem, PostgreSQL
Infra        : Koyeb (GPU on-demand, scale-to-zero)
Container    : Docker (CUDA 12.x + SGLang + modèle)
```

---

## Risques identifiés

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Cold start trop long (72B) | UX dégradée | Quantization INT4, ou fallback sur 7B. Explorer le warm pool Koyeb. |
| SGLang ne supporte pas encore Qwen2.5-VL-72B correctement | Blocage | Fallback sur vLLM (support mature pour Qwen2.5-VL) |
| Tool calling du 72B pas assez fiable | Boucles infinies | Limiter le nombre de tours agent, ajouter un timeout, human-in-the-loop |
| Coût GPU multi-GPU sur Koyeb | Budget | Commencer par le 7B, valider l'architecture, puis scaler |
| MCP-Bridge ne gère pas bien le streaming vision | Latence | Contribuer upstream ou forker. Alternative : Qwen-Agent natif MCP. |
| Grounding visuel imprécis (mauvaises coordonnées de clic) | Agent échoue | Fine-tuner sur un dataset GUI spécifique, ou utiliser UI-TARS-7B en complément |

---

## Questions ouvertes pour l'utilisateur

1. **Cas d'usage concret** : Quel type de tâche l'agent visuel doit-il accomplir ? (navigation web, automatisation desktop, scraping, test UI, autre ?)
2. **Budget GPU mensuel** : Quel est le budget acceptable pour l'infrastructure Koyeb ?
3. **Latence vs qualité** : Préfères-tu un modèle plus petit mais rapide (7B, < 2s) ou plus gros mais précis (72B, 5-10s) ?
4. **MCP Servers prioritaires** : Quels outils externes sont les plus importants ? (navigateur, DB, APIs, filesystem, Git, autre ?)
5. **Fréquence d'utilisation** : À quelle fréquence l'agent sera-t-il sollicité ? (impacte le choix scale-to-zero vs always-on)
6. **Fine-tuning** : Souhaites-tu fine-tuner le modèle sur tes propres données/tâches ?
