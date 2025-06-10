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
        # Compter les vraies images
        valid_images = 0
        waste_types = set()
        
        for metadata_file in list((self.dataset_path / "metadata").glob("*.json")):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                image_path = Path(metadata['image_path'])
                if image_path.exists():
                    valid_images += 1
                    waste_types.add(metadata['waste_type'])
            except:
                continue
        
        train_count = int(0.8 * valid_images)
        test_count = valid_images - train_count
        
        card = f"""---
            dataset_info:
            features:
            - name: image
                dtype: image
            - name: waste_type
                dtype: string
            - name: category
                dtype: string
            splits:
            - name: train
                num_examples: {train_count}
            - name: test
                num_examples: {test_count}
            task_categories:
            - image-classification
            tags:
            - waste-classification
            - synthetic-data
            license: apache-2.0
            ---

            # Waste Classification Dataset

            ## Description
            Synthetic waste images for AI model training.

            ## Dataset Info
            - **Total Images**: {valid_images}
            - **Classes**: {len(waste_types)}
            - **Split**: {train_count} train / {test_count} test

            ## Classes
            {', '.join(sorted(waste_types))}

            ## Usage
            ```python
            from datasets import load_dataset
            dataset = load_dataset("{self.repo_name}")
            ##License

            Apache 2.0 - Free for research and commercial use. 
            """
        return card
    
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
    uploader.upload_dataset(private=False)  # Mettre True pour un dataset privé
    
    print(f"Dataset disponible sur: https://huggingface.co/datasets/{REPO_NAME}")