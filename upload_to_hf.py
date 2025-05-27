import os
import json
from pathlib import Path
from datasets import Dataset, DatasetDict, Image
from huggingface_hub import HfApi, login
import pandas as pd
from typing import Dict, List
import logging
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HuggingFaceUploader:
    """Upload waste dataset to Hugging Face Hub"""
    
    def __init__(self, dataset_path: str, repo_name: str):
        self.dataset_path = Path(dataset_path)
        self.repo_name = repo_name
        self.api = HfApi()
        
        # Vérifier que le dataset existe
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset path not found: {dataset_path}")
    
    def login_hf(self, token: str = None):
        """Se connecter à Hugging Face"""
        if token:
            login(token=token)
        else:
            # Utilise le token depuis l'environnement ou demande interactivement
            login()
        logger.info("Connecté à Hugging Face")
    
    def prepare_dataset(self) -> DatasetDict:
        """Préparer le dataset pour Hugging Face"""
        logger.info("Préparation du dataset...")
        
        # Collecter toutes les métadonnées
        metadata_files = list((self.dataset_path / "metadata").glob("*.json"))
        
        if not metadata_files:
            raise ValueError("Aucun fichier de métadonnées trouvé")
        
        # Préparer les données
        data = []
        for metadata_file in metadata_files:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # Vérifier que l'image existe
            image_path = Path(metadata['image_path'])
            if image_path.exists():
                data.append({
                    'image': str(image_path),
                    'waste_type': metadata['waste_type'],
                    'zone': metadata['zone'],
                    'category': metadata['category'],
                    'color': metadata['variations']['color'],
                    'material': metadata['variations']['material'],
                    'shape': metadata['variations']['shape'],
                    'size': metadata['variations']['size'],
                    'degradation': metadata['variations']['degradation'],
                    'environment': metadata['variations']['environment'],
                    'lighting': metadata['variations']['lighting'],
                    'background': metadata['variations']['background'],
                    'prompt': metadata['prompt']
                })
        
        logger.info(f"Trouvé {len(data)} images avec métadonnées")
        
        # Créer un DataFrame puis convertir en Dataset
        df = pd.DataFrame(data)
        
        # Diviser en train/test (80/20)
        train_size = int(0.8 * len(df))
        train_df = df[:train_size]
        test_df = df[train_size:]
        
        # Créer les datasets avec colonnes Image
        train_dataset = Dataset.from_pandas(train_df).cast_column("image", Image())
        test_dataset = Dataset.from_pandas(test_df).cast_column("image", Image())
        
        dataset_dict = DatasetDict({
            'train': train_dataset,
            'test': test_dataset
        })
        
        logger.info(f"Dataset préparé: {len(train_dataset)} train, {len(test_dataset)} test")
        return dataset_dict
    
    def create_dataset_card(self) -> str:
        """Créer la carte du dataset"""
        # Analyser les statistiques du dataset
        metadata_files = list((self.dataset_path / "metadata").glob("*.json"))
        
        waste_types = set()
        zones = set()
        categories = set()
        
        for metadata_file in metadata_files:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            waste_types.add(metadata['waste_type'])
            zones.add(metadata['zone'])
            categories.add(metadata['category'])
        
        card = f"""
# Dataset de Déchets pour Classification

## Description
Ce dataset contient des images synthétiques de déchets générées par IA pour l'entraînement de modèles de classification et détection.

## Statistiques
- **Total d'images**: {len(metadata_files)}
- **Types de déchets**: {len(waste_types)}
- **Zones**: {len(zones)} 
- **Catégories**: {len(categories)}

## Types de déchets
{', '.join(sorted(waste_types))}

## Zones
{', '.join(sorted(zones))}

## Catégories
{', '.join(sorted(categories))}

## Structure du dataset
- `image`: Image du déchet
- `waste_type`: Type de déchet
- `zone`: Zone où le déchet a été trouvé
- `category`: Catégorie du déchet
- `color`: Couleur du déchet
- `material`: Matériau du déchet
- `shape`: Forme du déchet
- `size`: Taille du déchet
- `degradation`: État de dégradation
- `environment`: Environnement
- `lighting`: Conditions d'éclairage
- `background`: Arrière-plan
- `prompt`: Prompt utilisé pour la génération

## Utilisation
```python
from datasets import load_dataset

dataset = load_dataset("{self.repo_name}")
```

## Licence
Ce dataset est généré synthétiquement et peut être utilisé pour la recherche et l'éducation.
"""
        return card.strip()
    
    def upload_dataset(self, private: bool = False):
        """Upload le dataset vers Hugging Face"""
        logger.info("Début de l'upload...")
        
        # Préparer le dataset
        dataset_dict = self.prepare_dataset()
        
        # Créer la carte du dataset
        dataset_card = self.create_dataset_card()
        
        # Upload le dataset
        dataset_dict.push_to_hub(
            self.repo_name,
            private=private,
            token=True  # Utilise le token de l'environnement
        )
        
        # Upload la carte du dataset
        readme_path = "README.md"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(dataset_card)
        
        self.api.upload_file(
            path_or_fileobj=readme_path,
            path_in_repo="README.md",
            repo_id=self.repo_name,
            repo_type="dataset"
        )
        
        # Nettoyer
        os.remove(readme_path)
        
        logger.info(f"Dataset uploadé avec succès: https://huggingface.co/datasets/{self.repo_name}")
    
    def update_dataset(self, commit_message: str = "Update dataset"):
        """Mettre à jour un dataset existant"""
        logger.info("Mise à jour du dataset...")
        
        dataset_dict = self.prepare_dataset()
        dataset_dict.push_to_hub(
            self.repo_name,
            commit_message=commit_message,
            token=True
        )
        
        logger.info("Dataset mis à jour avec succès")

# Exemple d'utilisation
if __name__ == "__main__":
    # Configuration
    DATASET_PATH = "waste_dataset"  # Chemin vers votre dataset local
    REPO_NAME = "Yoannoza/waste-dataset"  # Nom du repo sur HF
    HF_TOKEN = os.getenv("HF_TOKEN")  # Token Hugging Face
    
    # Créer l'uploader
    uploader = HuggingFaceUploader(DATASET_PATH, REPO_NAME)
    
    # Se connecter à Hugging Face
    uploader.login_hf(HF_TOKEN)
    
    # Upload le dataset
    uploader.upload_dataset(private=True)  # Mettre True pour un dataset privé
    
    print(f"Dataset disponible sur: https://huggingface.co/datasets/{REPO_NAME}")