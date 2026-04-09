# TranspoBot — Projet GLSi L3 ESP/UCAD

## Démarrage rapide

1. Créer la base de données :
   mysql -u root -p < schema.sql

2. Configurer l'environnement :
   cp .env.example .env
   # Éditer .env avec vos valeurs

3. Installer les dépendances :
   pip install -r requirements.txt

4. Lancer le backend :
   python app.py

5. Ouvrir index.html dans un navigateur
   (mettre l'URL du backend dans la variable API de index.html)

## Livrables à rendre
- Lien plateforme déployée (Railway/Render)
- Lien interface de chat
- Rapport PDF (MCD, MLD, architecture, tests)
- Présentation PowerPoint (démo)

## Technologies
- Backend : FastAPI (Python)
- Base de données : MySQL
- LLM : OpenAI GPT / Ollama (local)
- Frontend : HTML/CSS/JS vanilla
