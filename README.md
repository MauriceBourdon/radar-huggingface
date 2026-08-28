# Radar Hugging Face

Capteur incrémental Hugging Face pour la veille IA/ComfyUI.

Objectif : détecter les nouveaux modèles, LoRA, adapters, quantifications et weights pertinents, conserver un historique glissant et produire un delta strict exploitable par le Radar quotidien et Discord.

## Principes V1

- scan léger toutes les 4 heures ;
- historique 30 jours ;
- enrichissement uniquement des modèles nouveaux ou modifiés ;
- model card + fichiers/weights + licence/tags quand disponibles ;
- classification base model / LoRA / adapter / quantization / utility ;
- recherche multi-familles sans dépendre du mot `ComfyUI` ;
- `feed.json`, `feed.md`, `summary.txt` ;
- Discord basé uniquement sur les événements du run courant ;
- benchmark initial : signaux Wildminder MiniMax H3 Characters, LTX-2.5 Face Swap, LTX-2.5 Dolly-in et MiniMax H3 Prompt Rewriter.

## Mode contrôle temporaire

Pendant le benchmark parallèle de Radar AI, le collector, le feed et le scheduling legacy restent
inchangés. L'étape Discord du workflow est explicitement désactivée : elle apparaît comme ignorée
dans GitHub Actions et ne peut plus rendre rouge un run dont la collecte et la persistence ont
réussi. Le script `discord_notifier.py` est conservé intact pour permettre un rollback simple après
le benchmark.
