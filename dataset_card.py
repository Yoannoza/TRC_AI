import os
import json
from pathlib import Path
from huggingface_hub import HfApi, login
import pandas as pd
from typing import Dict, List, Set, Tuple
import logging
from datetime import datetime
from collections import Counter, defaultdict
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GenerateurCarteDatasetComplet:
    """Générer une carte de dataset complète pour Hugging Face Hub"""
    
    def __init__(self, dataset_path: str, repo_name: str):
        self.dataset_path = Path(dataset_path)
        self.repo_name = repo_name
        self.api = HfApi()
        
        # Vérifier que le dataset existe
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Chemin du dataset introuvable : {dataset_path}")
    
    def login_hf(self, token: str = None):
        """Connexion à Hugging Face"""
        if token:
            login(token=token)
        else:
            login()
        logger.info("Connecté à Hugging Face")
    
    def analyser_dataset(self) -> Dict:
        """Analyser le dataset et extraire des statistiques complètes"""
        logger.info("Analyse du dataset en cours...")
        
        metadata_files = list((self.dataset_path / "metadata").glob("*.json"))
        
        if not metadata_files:
            raise ValueError("Aucun fichier de métadonnées trouvé")
        
        # Initialiser les conteneurs d'analyse
        analysis = {
            'total_images': len(metadata_files),
            'waste_types': Counter(),
            'zones': Counter(),
            'categories': Counter(),
            'colors': Counter(),
            'materials': Counter(),
            'shapes': Counter(),
            'sizes': Counter(),
            'degradation_states': Counter(),
            'environments': Counter(),
            'lighting_conditions': Counter(),
            'backgrounds': Counter(),
            'zone_waste_distribution': defaultdict(Counter),
            'category_zone_distribution': defaultdict(Counter),
            'file_sizes': [],
            'missing_images': [],
            'generation_date_range': {'earliest': None, 'latest': None}
        }
        
        # Analyser chaque fichier de métadonnées
        for metadata_file in metadata_files:
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # Vérifier si l'image existe
                image_path = Path(metadata.get('image_path', ''))
                if not image_path.exists():
                    analysis['missing_images'].append(str(metadata_file))
                    continue
                
                # Obtenir la taille du fichier
                try:
                    size_mb = image_path.stat().st_size / (1024 * 1024)
                    analysis['file_sizes'].append(size_mb)
                except:
                    pass
                
                # Extraire les champs de métadonnées
                waste_type = metadata.get('waste_type', 'inconnu')
                zone = metadata.get('zone', 'inconnue')
                category = metadata.get('category', 'inconnue')
                variations = metadata.get('variations', {})
                
                # Compter les occurrences
                analysis['waste_types'][waste_type] += 1
                analysis['zones'][zone] += 1
                analysis['categories'][category] += 1
                analysis['zone_waste_distribution'][zone][waste_type] += 1
                analysis['category_zone_distribution'][category][zone] += 1
                
                # Compter les variations
                for key in ['color', 'material', 'shape', 'size', 'degradation', 
                           'environment', 'lighting', 'background']:
                    value = variations.get(key, 'inconnu')
                    if key == 'degradation':
                        analysis['degradation_states'][value] += 1
                    elif key == 'lighting':
                        analysis['lighting_conditions'][value] += 1
                    else:
                        analysis[f"{key}s"][value] += 1
                
                # Suivre les dates de génération
                gen_date = metadata.get('generated_at')
                if gen_date:
                    if not analysis['generation_date_range']['earliest'] or gen_date < analysis['generation_date_range']['earliest']:
                        analysis['generation_date_range']['earliest'] = gen_date
                    if not analysis['generation_date_range']['latest'] or gen_date > analysis['generation_date_range']['latest']:
                        analysis['generation_date_range']['latest'] = gen_date
                        
            except Exception as e:
                logger.warning(f"Erreur lors du traitement de {metadata_file}: {e}")
                continue
        
        # Calculer des statistiques supplémentaires
        if analysis['file_sizes']:
            analysis['avg_file_size_mb'] = sum(analysis['file_sizes']) / len(analysis['file_sizes'])
            analysis['total_size_mb'] = sum(analysis['file_sizes'])
        else:
            analysis['avg_file_size_mb'] = 0
            analysis['total_size_mb'] = 0
        
        logger.info(f"Analyse terminée : {analysis['total_images']} images analysées")
        return analysis
    
    def creer_entete_yaml(self, analysis: Dict) -> str:
        """Créer l'en-tête YAML pour la carte du dataset"""
        
        # Extraire les valeurs uniques pour les tags
        waste_types = list(analysis['waste_types'].keys())
        categories = list(analysis['categories'].keys())
        zones = list(analysis['zones'].keys())
        
        yaml_header = f"""---
            license: cc-by-4.0
            task_categories:
            - image-classification
            - object-detection
            - computer-vision
            language:
            - fr
            - en
            tags:
            - donnees-synthetiques
            - gestion-dechets
            - ia-environnementale
            - vision-par-ordinateur
            - classification-images
            - detection-objets
            - recyclage
            - durabilite
            - detection-dechets
            - contexte-africain
            size_categories:
            - {self._obtenir_categorie_taille(analysis['total_images'])}
            dataset_info:
            features:
            - name: image
                dtype: image
            - name: waste_type
                dtype: string
            - name: zone
                dtype: string
            - name: category
                dtype: string
            - name: color
                dtype: string
            - name: material
                dtype: string
            - name: shape
                dtype: string
            - name: size
                dtype: string
            - name: degradation
                dtype: string
            - name: environment
                dtype: string
            - name: lighting
                dtype: string
            - name: background
                dtype: string
            - name: prompt
                dtype: string
            splits:
            - name: train
                num_bytes: {int(analysis['total_size_mb'] * 0.8 * 1024 * 1024)}
                num_examples: {int(analysis['total_images'] * 0.8)}
            - name: test
                num_bytes: {int(analysis['total_size_mb'] * 0.2 * 1024 * 1024)}
                num_examples: {int(analysis['total_images'] * 0.2)}
            download_size: {int(analysis['total_size_mb'] * 1024 * 1024)}
            dataset_size: {int(analysis['total_size_mb'] * 1024 * 1024)}
            configs:
            - config_name: default
            data_files:
            - split: train
                path: data/train-*
            - split: test
                path: data/test-*
        ---"""
        return yaml_header
            
    def _obtenir_categorie_taille(self, num_images: int) -> str:
        """Obtenir la catégorie de taille pour le dataset"""
        if num_images < 1000:
            return "n<1K"
        elif num_images < 10000:
            return "1K<n<10K"
        elif num_images < 100000:
            return "10K<n<100K"
        elif num_images < 1000000:
            return "100K<n<1M"
        else:
            return "n>1M"
    
    def creer_carte_complete(self, analysis: Dict) -> str:
        """Créer une carte de dataset complète"""
        
        # En-tête YAML
        yaml_header = self.creer_entete_yaml(analysis)
        
        # Contenu principal
        card_content = f"""
        # 🗑️ Dataset Synthétique de Déchets pour la Gestion Environnementale Pilotée par l'IA

        ## 📊 Aperçu du Dataset

        Ce dataset contient **{analysis['total_images']:,} images synthétiques de haute qualité** de différents types de déchets, conçues pour entraîner des modèles de vision par ordinateur destinés à la détection, classification et gestion des déchets. Les images sont générées à l'aide de techniques d'IA de pointe et couvrent divers environnements urbains africains, incluant les zones résidentielles, commerciales et industrielles.

        ### 🎯 Caractéristiques Clés

        - **{analysis['total_images']:,} images synthétiques** réparties sur {len(analysis['waste_types'])} types de déchets
        - **{len(analysis['zones'])} zones distinctes** : {', '.join(analysis['zones'].keys())}
        - **{len(analysis['categories'])} catégories de déchets** : {', '.join(analysis['categories'].keys())}
        - **Métadonnées riches** avec plus de 12 attributs par image
        - **Focus sur le contexte africain** avec des environnements localisés
        - **Images haute résolution** ({analysis['avg_file_size_mb']:.2f} MB en moyenne)
        - **Variations complètes** en éclairage, matériaux, états de dégradation

        ## 🏗️ Structure du Dataset

        ### Répartition des Images par Zone
        {self._creer_tableau_distribution(analysis['zones'], 'Zone', 'Images')}

        ### Répartition des Types de Déchets
        {self._creer_tableau_distribution(analysis['waste_types'], 'Type de Déchet', 'Images')}

        ### Répartition des Catégories
        {self._creer_tableau_distribution(analysis['categories'], 'Catégorie', 'Images')}

        ## 🔍 Statistiques Détaillées

        ### Caractéristiques Physiques
        - **Couleurs** : {len(analysis['colors'])} variantes ({', '.join(list(analysis['colors'].keys())[:10])}{'...' if len(analysis['colors']) > 10 else ''})
        - **Matériaux** : {len(analysis['materials'])} types ({', '.join(list(analysis['materials'].keys()))})
        - **Formes** : {len(analysis['shapes'])} formes ({', '.join(list(analysis['shapes'].keys()))})
        - **Tailles** : {len(analysis['sizes'])} catégories ({', '.join(list(analysis['sizes'].keys()))})
        - **États de Dégradation** : {len(analysis['degradation_states'])} niveaux ({', '.join(list(analysis['degradation_states'].keys()))})

        ### Contexte Environnemental
        - **Environnements** : {len(analysis['environments'])} lieux ({', '.join(list(analysis['environments'].keys())[:5])}{'...' if len(analysis['environments']) > 5 else ''})
        - **Conditions d'Éclairage** : {len(analysis['lighting_conditions'])} types ({', '.join(list(analysis['lighting_conditions'].keys()))})
        - **Arrière-plans** : {len(analysis['backgrounds'])} variantes ({', '.join(list(analysis['backgrounds'].keys())[:5])}{'...' if len(analysis['backgrounds']) > 5 else ''})

        ### Spécifications Techniques
        - **Taille Totale du Dataset** : {analysis['total_size_mb']:.1f} MB
        - **Taille Moyenne d'Image** : {analysis['avg_file_size_mb']:.2f} MB
        - **Format d'Image** : PNG
        - **Résolution** : 1024x1024 pixels
        - **Période de Génération** : {analysis['generation_date_range']['earliest'][:10] if analysis['generation_date_range']['earliest'] else 'N/A'} à {analysis['generation_date_range']['latest'][:10] if analysis['generation_date_range']['latest'] else 'N/A'}

        ## 🚀 Démarrage Rapide

        ### Chargement du Dataset

        ```python
        from datasets import load_dataset

        # Charger le dataset complet
        dataset = load_dataset("{self.repo_name}")

        # Charger une division spécifique
        train_dataset = load_dataset("{self.repo_name}", split="train")
        test_dataset = load_dataset("{self.repo_name}", split="test")

        # Afficher les informations de base
        print(f"Échantillons d'entraînement : {{len(train_dataset)}}")
        print(f"Échantillons de test : {{len(test_dataset)}}")
        print(f"Caractéristiques : {{train_dataset.features}}")
        ```

        ### Explorer les Données

        ```python
        import matplotlib.pyplot as plt
        from collections import Counter

        # Charger le dataset
        dataset = load_dataset("{self.repo_name}", split="train")

        # Afficher une image avec ses métadonnées
        sample = dataset[0]
        plt.figure(figsize=(10, 6))

        plt.subplot(1, 2, 1)
        plt.imshow(sample['image'])
        plt.title(f"{{sample['waste_type']}} dans {{sample['zone']}}")
        plt.axis('off')

        plt.subplot(1, 2, 2)
        metadata_text = f"""
        Type_de_Déchet : {{sample['waste_type']}}
        Zone : {{sample['zone']}}
        Catégorie : {{sample['category']}}
        Couleur : {{sample['color']}}
        Matériau : {{sample['material']}}
        Taille : {{sample['size']}}
        Environnement : {{sample['environment']}}
        Éclairage : {{sample['lighting']}}
        """
        plt.text(0.1, 0.5, metadata_text, fontsize=10, verticalalignment='center')
        plt.axis('off')
        plt.tight_layout()
        plt.show()

        # Analyser la distribution
        waste_types = [item['waste_type'] for item in dataset]
        waste_counter = Counter(waste_types)
        print("Top 5 des types de déchets :")
        for waste_type, count in waste_counter.most_common(5):
            print(f"  {{waste_type}} : {{count}} images")
        ```

        ## 🎯 Cas d'Usage

        ### 1. **Modèles de Classification de Déchets**
        Entraîner des modèles de classification d'images pour identifier différents types de déchets :
        ```python
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        # Exemple avec un vision transformer
        processor = AutoImageProcessor.from_pretrained("google/vit-base-patch16-224")
        model = AutoModelForImageClassification.from_pretrained("google/vit-base-patch16-224", 
                                                            num_labels=len(unique_waste_types))
        ```

        ### 2. **Systèmes de Détection d'Objets**
        Développer des systèmes de détection de déchets pour les applications de ville intelligente :
        ```python
        # Convertir au format de détection d'objets (YOLO, COCO)
        # Les annotations de boîtes englobantes peuvent être dérivées des objets de déchets centrés
        ```

        ### 3. **Surveillance Environnementale**
        Construire des systèmes automatisés pour :
        - 🏙️ **Gestion de Ville Intelligente** : Détection automatisée de déchets en zones urbaines
        - ♻️ **Optimisation du Recyclage** : Systèmes de tri automatisé
        - 📊 **Analytiques des Déchets** : Surveillance des modèles et tendances de déchets
        - 🌍 **Recherche Environnementale** : Étude de la distribution des déchets dans différentes zones

        ### 4. **Applications Éducatives**
        Parfait pour :
        - 🎓 **Cours de Vision par Ordinateur** : Enseigner la classification d'images et la détection d'objets
        - 🌱 **Éducation Environnementale** : Sensibilisation à la gestion des déchets
        - 🔬 **Projets de Recherche** : Base de référence pour la recherche en IA de gestion des déchets

        ## 📋 Schéma du Dataset

        | Caractéristique | Type | Description | Exemples de Valeurs |
        |------------------|------|-------------|---------------------|
        | `image` | Image | Image de déchet haute résolution | Objet PIL Image |
        | `waste_type` | string | Type spécifique de déchet | "bouteille_plastique", "carton_emballage" |
        | `zone` | string | Zone environnementale | "résidentielle", "commerciale", "industrielle" |
        | `category` | string | Catégorie de déchet | "ménager", "recyclable", "dangereux" |
        | `color` | string | Couleur principale du déchet | "transparent", "bleu", "brun" |
        | `material` | string | Composition matérielle | "PET", "carton ondulé", "aluminium" |
        | `shape` | string | Forme physique | "cylindrique", "boîte", "plat" |
        | `size` | string | Taille relative | "petit", "moyen", "grand" |
        | `degradation` | string | État de condition | "neuf", "usagé", "cassé" |
        | `environment` | string | Lieu spécifique | "Yamcity", "WalMart", "GDIZ" |
        | `lighting` | string | Condition d'éclairage | "naturelle", "éclairage LED", "projecteurs" |
        | `background` | string | Cadre d'arrière-plan | "rue pavée", "parking", "entrepôt" |
        | `prompt` | string | Prompt de génération | Description textuelle détaillée |

        ## 🌍 Contexte Géographique et Culturel

        Ce dataset se concentre spécifiquement sur les **environnements urbains africains**, incluant :

        ### Zones Résidentielles
        - **Villes d'Afrique de l'Ouest** : Yamcity, Cotonou, Lagos, Accra, Bamako, Lomé
        - **Cadres Typiques** : Quartiers locaux, marchés traditionnels, rues résidentielles

        ### Zones Commerciales  
        - **Centres Commerciaux** : WalMart, Super U, China Mall
        - **Districts d'Affaires** : Zones commerciales modernes à travers l'Afrique de l'Ouest

        ### Zones Industrielles
        - **Zones Économiques** : GDIZ, Lagos Industrial Park, Ouagadougou Tech Zone
        - **Centres de Fabrication** : Bobo-Dioulasso Industrial Estate, Port Harcourt Energy Zone

        ## ⚖️ Considérations Éthiques et Limitations

        ### ✅ Forces
        - **Données Synthétiques** : Aucun problème de confidentialité avec de vraies personnes ou lieux
        - **Représentation Diverse** : Multiples contextes urbains africains
        - **Couverture Complète** : Grande variété de types et conditions de déchets
        - **Haute Qualité** : Images cohérentes et haute résolution

        ### ⚠️ Limitations
        - **Nature Synthétique** : Peut ne pas capturer toutes les nuances des déchets réels
        - **Portée Géographique** : Concentré sur les contextes africains (peut ne pas se généraliser globalement)
        - **Instantané Temporel** : Généré à une période spécifique
        - **Artefacts IA** : Artefacts potentiels du processus de génération d'images

        ### 🤝 Usage Responsable
        - Compléter avec des données réelles quand possible
        - Considérer l'adaptation de domaine pour d'autres régions géographiques
        - Valider les performances du modèle sur des ensembles de test réels
        - Utiliser à des fins éducatives et de recherche

        ## 📈 Résultats de Référence

        *À venir : Performance des modèles de base sur diverses tâches de vision par ordinateur*

        ## 🔗 Ressources Connexes

        - **[Rapport sur la Gestion des Déchets en Afrique](https://example.com)** - Contexte sur les défis des déchets
        - **[Vision par Ordinateur pour la Durabilité](https://example.com)** - Recherche connexe
        - **[Initiative Villes Intelligentes Africaines](https://example.com)** - Contexte d'implémentation

        ## 📄 Citation

        Si vous utilisez ce dataset dans votre recherche, veuillez citer :

        ```bibtex
        @dataset{{waste_synthetic_dataset_2024,
        title={{Dataset Synthétique de Déchets pour la Gestion Environnementale Pilotée par l'IA}},
        author={{Votre Nom}},
        year={{2024}},
        publisher={{Hugging Face}},
        url={{https://huggingface.co/datasets/{self.repo_name}}}
        }}
        ```

        ## 🤝 Contribuer

        Nous accueillons les contributions pour améliorer ce dataset :

        1. **Signaler des Problèmes** : Trouvé des données manquantes ou incorrectes ? Ouvrez un problème
        2. **Suggérer des Améliorations** : Idées pour des types de déchets ou environnements supplémentaires
        3. **Partager les Résultats** : Faites-nous savoir comment vous utilisez le dataset
        4. **Collaborer** : Intéressé par l'expansion du dataset ? Collaborons !

        ## 📞 Contact

        Pour questions, suggestions ou collaborations, veuillez nous contacter via :
        - **Hugging Face** : [@{self.repo_name.split('/')[0]}](https://huggingface.co/{self.repo_name.split('/')[0]})
        - **Dépôt du Dataset** : [Problèmes](https://huggingface.co/datasets/{self.repo_name}/discussions)

        ## 📜 Licence

        Ce dataset est publié sous la **Licence Creative Commons Attribution 4.0 International (CC BY 4.0)**.

        Vous êtes libre de :
        - ✅ **Partager** : Copier et redistribuer le matériel
        - ✅ **Adapter** : Remixer, transformer et construire sur le matériel
        - ✅ **Usage Commercial** : Utiliser à des fins commerciales

        Sous les conditions suivantes :
        - 📝 **Attribution** : Donner un crédit approprié et indiquer si des changements ont été apportés
        - 🔗 **Lien vers la Licence** : Inclure un lien vers la licence

        ## 🔄 Historique des Versions

        - **v1.0.0** ({datetime.now().strftime('%Y-%m-%d')}) : Version initiale avec {analysis['total_images']:,} images
        - {len(analysis['waste_types'])} types de déchets à travers {len(analysis['zones'])} zones
        - Métadonnées complètes avec {len(analysis['colors'])} variantes de couleur
        - Focus sur le contexte urbain africain

        ---

        *Généré le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Taille du Dataset : {analysis['total_size_mb']:.1f} MB | Images : {analysis['total_images']:,}*
    """
        return card_content

    def _creer_tableau_distribution(self, counter: Counter, header1: str, header2: str) -> str:
        """Créer un tableau markdown à partir d'un objet Counter"""
        table = f"| {header1} | {header2} | Pourcentage |\n"
        table += "|" + "-" * (len(header1) + 2) + "|" + "-" * (len(header2) + 2) + "|" + "-" * 13 + "|\n"
        
        total = sum(counter.values())
        for item, count in counter.most_common():
            percentage = (count / total) * 100
            table += f"| {item} | {count:,} | {percentage:.1f}% |\n"
        
        return table
    
    def uploader_carte_dataset(self, private: bool = False):
        """Générer et uploader une carte de dataset complète"""
        logger.info("Génération de la carte de dataset complète...")
        
        # Analyser le dataset
        analysis = self.analyser_dataset()
        
        # Créer la carte complète
        dataset_card = self.creer_carte_complete(analysis)
        
        # Sauvegarder localement d'abord
        readme_path = "README_complet.md"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(dataset_card)
        
        logger.info(f"Carte du dataset sauvegardée localement : {readme_path}")
        
        # Uploader vers Hugging Face
        try:
            self.api.upload_file(
                path_or_fileobj=readme_path,
                path_in_repo="README.md",
                repo_id=self.repo_name,
                repo_type="dataset",
                commit_message="Ajouter une carte de dataset complète avec analyse détaillée et documentation"
            )
            
            logger.info(f"Carte de dataset complète uploadée avec succès !")
            logger.info(f"Voir à : https://huggingface.co/datasets/{self.repo_name}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'upload de la carte du dataset : {e}")
            raise
        
        finally:
            # Nettoyer le fichier local
            if os.path.exists(readme_path):
                os.remove(readme_path)
        
        return analysis

# Exemple d'utilisation
if __name__ == "__main__":
    # Configuration
    DATASET_PATH = "waste_dataset"  # Chemin vers votre dataset local
    REPO_NAME = "Yoannoza/waste-dataset"  # Nom de votre dépôt HF
    HF_TOKEN = os.getenv("HF_TOKEN")  # Token Hugging Face
    
    try:
        # Créer le générateur de carte
        generateur_carte = GenerateurCarteDatasetComplet(DATASET_PATH, REPO_NAME)
        
        # Se connecter à Hugging Face
        generateur_carte.login_hf(HF_TOKEN)
        
        # Générer et uploader la carte de dataset complète
        analysis = generateur_carte.uploader_carte_dataset(private=False)
        
        print(f"\n✅ Carte du dataset uploadée avec succès !")
        print(f"📊 Statistiques du Dataset :")
        print(f"   • Total Images : {analysis['total_images']:,}")
        print(f"   • Types de Déchets : {len(analysis['waste_types'])}")
        print(f"   • Zones : {len(analysis['zones'])}")
        print(f"   • Taille Totale : {analysis['total_size_mb']:.1f} MB")
        print(f"🔗 Voir à : https://huggingface.co/datasets/{REPO_NAME}")
        
    except Exception as e:
        print(f"❌ Erreur : {e}")
        logging.error(f"Échec de la génération de la carte du dataset : {e}")