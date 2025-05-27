# Générateur de Jeu de Données d’Images Synthétiques de Déchets

Ce projet propose un pipeline complet pour générer un jeu de données d’images synthétiques représentant divers types de déchets dans différents environnements et conditions. Ensuite, le jeu de données est automatiquement téléversé sur le Hugging Face Hub. Il utilise une API externe de génération d’images pour créer des images réalistes à partir de prompts détaillés dérivés de configurations prédéfinies (types de déchets, zones, etc.).

## Fonctionnalités

* **Génération configurable de jeux de données** : Définissez différents types de déchets, zones (résidentielle, commerciale, industrielle), couleurs, matériaux, formes, tailles, états de dégradation, environnements, conditions d’éclairage, arrière-plans et obstacles.
* **Génération automatisée des prompts** : Crée automatiquement des prompts détaillés pour l’API d’image à partir de combinaisons de caractéristiques prédéfinies.
* **Génération d’images en parallèle** : Utilise le multithreading pour générer des images en lots, améliorant ainsi l’efficacité.
* **Gestion des métadonnées** : Sauvegarde les images générées avec des métadonnées détaillées (type de déchet, zone, variations, prompt, etc.) dans un format structuré.
* **Intégration Hugging Face Hub** : Prépare et téléverse le jeu de données (images et métadonnées) dans un dépôt spécifié sur le Hugging Face Hub.
* **Génération automatique de la fiche du jeu de données** : Crée automatiquement un `README.md` pour le dépôt Hugging Face, incluant description, statistiques, structure et exemples d’utilisation.
* **Exportation des annotations (prévu)** : Des emplacements sont prévus pour exporter des annotations dans des formats comme COCO ou YOLO.

## Installation

1. **Cloner le dépôt :**

   ```bash
   git clone <repository_url>
   cd <repository_directory>
   ```

2. **Installer les dépendances :**
   Assurez-vous d’avoir Python 3.6 ou supérieur installé. Installez les bibliothèques requises avec :

   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Le projet utilise des variables d’environnement pour les informations sensibles comme les clés API. Créez un fichier `.env` à la racine du projet s’il n’existe pas encore.

Ajoutez les variables suivantes dans ce fichier `.env` :

```env
IMAGE_ROUTER_API_KEY=your_image_generation_api_key
HF_TOKEN=your_huggingface_token
```

* **`IMAGE_ROUTER_API_KEY`** : Clé API pour le service de génération d’images (`https://ir-api.myqa.cc`).
* **`HF_TOKEN`** : Jeton d’accès Hugging Face avec les droits d’écriture pour téléverser un jeu de données. Vous pouvez en générer un dans les paramètres de votre compte Hugging Face, sous "Access Tokens".

## Utilisation

Le projet comporte deux étapes principales : la génération du jeu de données et son téléversement.

### 1. Générer le jeu de données

Lancez le fichier `script.py` pour générer le jeu de données d’images synthétiques.

```bash
python script.py
```

Le script va créer un dossier (par défaut : `waste_dataset`) contenant deux sous-dossiers : `images` et `metadata`.
Vous pouvez modifier les paramètres de génération (nombre d’images par type, taille des lots, zones à inclure, etc.) dans le bloc `if __name__ == "__main__":` de `script.py`.

### 2. Téléverser sur Hugging Face Hub

Une fois le jeu de données généré, utilisez le script `upload_to_hf.py` pour le téléverser sur votre dépôt Hugging Face.

```bash
python upload_to_hf.py
```

Avant cela, assurez-vous de définir les variables `DATASET_PATH` et `REPO_NAME` dans le bloc `if __name__ == "__main__":` du fichier `upload_to_hf.py`, correspondant à votre dossier de données et au nom du dépôt Hugging Face (ex. `VotreNomUtilisateur/nom-du-dataset`).

Le script utilisera automatiquement le `HF_TOKEN` depuis le fichier `.env` pour se connecter, préparer le jeu de données, générer une fiche (`README.md`) et tout téléverser sur le dépôt spécifié.

## Structure du projet

```
.
├── .env                 # Variables d’environnement (clés API, tokens)
├── .gitignore           # Fichiers à ne pas suivre avec Git
├── dataset/             # Répertoire potentiel pour les datasets
├── env/                 # Environnement virtuel éventuel
├── requirements.txt     # Dépendances Python
├── script.py            # Script principal de génération d’images synthétiques
├── upload_to_hf.py      # Script de téléversement vers Hugging Face Hub
└── README.md            # Ce fichier
```

Structure typique du dossier généré (`waste_dataset`) :

```
waste_dataset/
├── images/              # Fichiers d’images générées (.png)
├── metadata/            # Métadonnées associées à chaque image (.json)
└── generation_stats.json# Statistiques de génération
```