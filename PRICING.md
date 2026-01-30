# Comparaison Pricing GPU : Koyeb vs GCP vs AWS

> **Contrainte budget** : max **€30/jour** (~$32/jour)
> **Usage** : 2h/jour en mode on/off, scale-to-zero le reste du temps
> **Budget max par heure** : ~$16/h
> **Objectif** : le modèle le plus gros possible dans ce budget

---

## Prix vérifiés (janvier 2026)

### Koyeb — Prix par heure, facturation à la seconde

| GPU | VRAM | $/h | Source |
|-----|------|-----|--------|
| 1x L4 | 24 GB | $0.70 | koyeb.com/pricing |
| 1x L40S | 48 GB | $1.20 | koyeb.com/pricing |
| 1x A100 PCIe | 80 GB | $1.60 | koyeb.com/pricing |
| 1x A100 SXM | 80 GB | $2.15 | koyeb.com/pricing |
| 1x H100 | 80 GB | $2.50 | koyeb.com/pricing |
| 1x H200 | 141 GB | $3.00 | koyeb.com/pricing |
| 1x B200 | 180 GB | $5.50 | koyeb.com/pricing |
| **2x A100 PCIe** | **160 GB** | **$3.20** | koyeb.com/pricing |
| **2x H100** | **160 GB** | **$5.00** | koyeb.com/pricing |
| **2x H200** | **282 GB** | **$6.00** | koyeb.com/pricing |
| **4x A100 PCIe** | **320 GB** | **$6.40** | koyeb.com/pricing |
| **4x H100** | **320 GB** | **$10.00** | koyeb.com/pricing |
| **4x H200** | **564 GB** | **$12.00** | koyeb.com/pricing |
| 8x A100 PCIe | 640 GB | $12.80 | koyeb.com/pricing |
| 8x H100 | 640 GB | $20.00 | koyeb.com/pricing |
| 8x H200 | 1128 GB | $24.00 | koyeb.com/pricing |

Scale-to-zero : **natif, $0 quand idle**, facturation à la seconde.

### GCP — Prix on-demand par heure (us-central1)

| Instance | GPU | VRAM | $/h on-demand | $/h Spot |
|----------|-----|------|---------------|----------|
| g2-standard-4 | 1x L4 | 24 GB | $0.70 | ~$0.21 |
| a2-highgpu-2g | 2x A100 40GB | 80 GB | $7.35 | ~$1.90 |
| a2-ultragpu-2g | 2x A100 80GB | 160 GB | $10.14 | ~$0.62 |
| a2-ultragpu-4g | 4x A100 80GB | 320 GB | $20.28 | ~$1.25 |
| **a3-highgpu-4g** | **4x H100 80GB** | **320 GB** | **$43.69** | **~$40** |
| a3-highgpu-8g | 8x H100 80GB | 640 GB | $88.49 | ~$23-82 |

Cloud Run GPU : L4 seulement ($0.67/h GPU + CPU/RAM ≈ $1.65/h total). Pas de A100/H100.
Scale-to-zero GKE : via KEDA, $0 quand 0 pods. Cloud Run : natif.
**Note** : Les A3 (H100) ont des réductions Spot très faibles sur GCP.

Sources : Holori, Economize.cloud, CloudPrice, Vantage — cross-référencés. Prix dynamiques JS sur cloud.google.com.

### AWS — Prix par heure (us-east-1, post-réduction juin 2025)

| Instance | GPU | VRAM | $/h on-demand | $/h Spot |
|----------|-----|------|---------------|----------|
| g5.2xlarge | 1x A10G | 24 GB | $1.21 | ~$0.36 |
| g5.12xlarge | 4x A10G | 96 GB | $5.67 | ~$0.66-1.70 |
| g6.xlarge | 1x L4 | 24 GB | $0.80 | ~$0.24 |
| **p4d.24xlarge** | **8x A100 40GB** | **320 GB** | **$21.96** | **~$9.83** |
| p4de.24xlarge | 8x A100 80GB | 640 GB | $27.45 | ~$12-14 |
| p5.48xlarge | 8x H100 80GB | 640 GB | $55.04 | ~$13-16.50 |

Scale-to-zero EC2 : custom (ECS capacity provider, terminate instance). Pas natif.
SageMaker Async : scale-to-zero natif mais surcoût ~70% vs EC2 brut.

Sources : Vantage instances.vantage.sh (jan. 2026), Economize.cloud, aws.amazon.com/ec2/pricing.

---

## Calcul budget : €30/jour = $32/jour = $16/h max (2h/jour)

### Configurations dans le budget (≤ $16/h)

| # | Cloud | Config | VRAM | $/h | €/jour (2h) | Modèle max |
|---|-------|--------|------|-----|-------------|------------|
| **1** | **Koyeb** | **4x H200** | **564 GB** | **$12.00** | **€22.40** | **Qwen3-VL-235B-A22B (MoE) ✅** |
| **2** | **Koyeb** | **4x H100** | **320 GB** | **$10.00** | **€18.70** | **Qwen2.5-VL-72B BF16 ✅** |
| 3 | Koyeb | 8x A100 PCIe | 640 GB | $12.80 | €23.90 | Qwen3-VL-235B-A22B ✅ |
| 4 | Koyeb | 4x A100 PCIe | 320 GB | $6.40 | €11.96 | Qwen2.5-VL-72B BF16 ✅ |
| 5 | Koyeb | 2x H200 | 282 GB | $6.00 | €11.21 | Qwen2.5-VL-72B BF16 ✅ |
| 6 | Koyeb | 2x H100 | 160 GB | $5.00 | €9.35 | Qwen2.5-VL-72B BF16 (juste) ✅ |
| 7 | Koyeb | 1x B200 | 180 GB | $5.50 | €10.28 | Qwen2.5-VL-72B BF16 ✅ |
| 8 | GCP | 2x A100 80GB (on-demand) | 160 GB | $10.14 | €18.96 | Qwen2.5-VL-72B BF16 (juste) ✅ |
| 9 | GCP | 2x A100 40GB (on-demand) | 80 GB | $7.35 | €13.74 | Qwen2.5-VL-72B AWQ INT4 ⚠️ |
| 10 | AWS | g5.12xlarge (on-demand) | 96 GB | $5.67 | €10.60 | Qwen2.5-VL-72B AWQ INT4 ⚠️ |
| 11 | AWS | p4d.24xlarge Spot | 320 GB | ~$9.83 | ~€18.38 | Qwen2.5-VL-72B BF16 ✅ |
| 12 | AWS | p5.48xlarge Spot | 640 GB | ~$13-16.50 | ~€24-31 | Qwen3-VL-235B-A22B ✅ (si ~$13) |

### Configurations hors budget (> $16/h)

| Cloud | Config | VRAM | $/h | €/jour (2h) | Verdict |
|-------|--------|------|-----|-------------|---------|
| Koyeb | 8x H100 | 640 GB | $20.00 | €37.40 | ❌ +24% budget |
| GCP | 4x H100 (on-demand) | 320 GB | $43.69 | €81.70 | ❌ ×2.7 budget |
| GCP | 8x H100 (on-demand) | 640 GB | $88.49 | €165.48 | ❌ ×5.5 budget |
| AWS | p4d on-demand | 320 GB | $21.96 | €41.07 | ❌ +37% budget |
| AWS | p5 on-demand | 640 GB | $55.04 | €102.92 | ❌ ×3.4 budget |

---

## Verdict

### Koyeb gagne massivement

Koyeb est **3 à 5x moins cher** que GCP/AWS pour les GPU H100/H200, avec un scale-to-zero natif et une facturation à la seconde. Ce n'est pas un petit écart — c'est un facteur multiplicatif.

| Comparaison | Koyeb | GCP | AWS |
|-------------|-------|-----|-----|
| 4x H100 80GB (320 GB VRAM) | **$10/h** | $43.69/h | N/A (pas de 4x H100) |
| 8x H100 80GB (640 GB VRAM) | **$20/h** | $88.49/h | $55.04/h |
| Ratio vs Koyeb | 1x | 4.4x | 2.75x |
| Scale-to-zero | Natif, $0 | KEDA (complexe) | Custom (fragile) |

### Recommandation par palier

#### Option 1 : Modèle maximum — €22/jour
```
Koyeb 4x H200 (564 GB VRAM) — $12/h
→ Qwen3-VL-235B-A22B (MoE, ~470 GB BF16)
→ Le plus gros VLM open-weight existant
→ €22.40/jour pour 2h
```

#### Option 2 : Meilleur rapport qualité/prix — €19/jour
```
Koyeb 4x H100 (320 GB VRAM) — $10/h
→ Qwen2.5-VL-72B BF16 pleine précision
→ 320 GB VRAM = marge massive pour long contexte
→ €18.70/jour pour 2h
```

#### Option 3 : Budget serré — €12/jour
```
Koyeb 4x A100 PCIe (320 GB VRAM) — $6.40/h
→ Qwen2.5-VL-72B BF16
→ A100 moins rapides que H100 mais suffisantes
→ €11.96/jour pour 2h
```

#### Option 4 : Budget minimal — €9/jour
```
Koyeb 2x H100 (160 GB VRAM) — $5/h
→ Qwen2.5-VL-72B BF16 (juste, 144 GB sur 160 GB)
→ Peu de marge pour le KV cache
→ €9.35/jour pour 2h
```

### Et GCP/AWS ?

GCP et AWS ne sont compétitifs que dans deux cas :

1. **GCP Spot A100 80GB** ($0.62/h pour 2x A100 80GB) — prix imbattable si disponible, mais les Spot sont interruptibles et peu fiables pour des sessions de 2h.

2. **AWS p4d Spot** (~$9.83/h pour 8x A100 40GB, 320 GB VRAM) — dans le budget, mais Spot = interruptions possibles et scale-to-zero complexe.

Pour un usage **fiable et prévisible** à €30/jour max, **Koyeb est la seule option qui offre H100/H200 multi-GPU dans le budget avec scale-to-zero natif**.

---

## Résumé exécutif

```
Budget        : €30/jour max
Usage         : 2h/jour, scale-to-zero
Gagnant       : Koyeb (3-5x moins cher que GCP/AWS en multi-GPU)

Config recommandée :
  Koyeb 4x H200 (564 GB VRAM)
  $12/h → €22.40/jour (2h)
  → Peut faire tourner Qwen3-VL-235B-A22B (le plus gros VLM existant)

Fallback :
  Koyeb 4x H100 (320 GB VRAM)
  $10/h → €18.70/jour (2h)
  → Qwen2.5-VL-72B BF16 pleine précision

GCP/AWS : hors budget pour du multi-GPU H100 on-demand.
Seules les Spot instances AWS/GCP rentrent dans le budget,
mais elles sont interruptibles et le scale-to-zero n'est pas natif.
```
