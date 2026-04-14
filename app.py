# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mysql.connector
import os
import re
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="TranspoBot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 3306)),
    "user":     os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "transpobot"),
    "ssl_disabled": False,
    "charset": "utf8mb4",
}

LLM_API_KEY  = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL    = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")

DB_SCHEMA = (
    "Tables MySQL disponibles:\n"
    "vehicules(id, immatriculation, type, capacite, statut, kilometrage, date_acquisition)\n"
    "chauffeurs(id, nom, prenom, telephone, numero_permis, categorie_permis, disponibilite, vehicule_id, date_embauche)\n"
    "lignes(id, code, nom, origine, destination, distance_km, duree_minutes)\n"
    "tarifs(id, ligne_id, type_client, prix)\n"
    "trajets(id, ligne_id, chauffeur_id, vehicule_id, date_heure_depart, date_heure_arrivee, statut, nb_passagers, recette)\n"
    "incidents(id, trajet_id, type, description, gravite, date_incident, resolu)\n"
)

SYSTEM_PROMPT = (
    "Tu es TranspoBot, assistant de gestion de transport.\n"
    "Tu generes des requetes SQL a partir de questions en langage naturel.\n\n"
    + DB_SCHEMA +
    "\nREGLES:\n"
    "1. Genere UNIQUEMENT des requetes SELECT.\n"
    "2. Reponds en JSON: {\"sql\": \"SELECT ...\", \"explication\": \"...\"}\n"
    "3. Si impossible: {\"sql\": null, \"explication\": \"...\"}\n"
    "4. LIMIT 100 maximum.\n"
)

def get_db():
    conn = mysql.connector.connect(**DB_CONFIG)
    conn.cmd_query("SET NAMES utf8mb4")
    return conn

def execute_query(sql):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

async def ask_llm(question):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question},
                ],
                "temperature": 0,
            },
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError("Reponse LLM invalide")

class ChatMessage(BaseModel):
    question: str

@app.post("/api/chat")
async def chat(msg: ChatMessage):
    try:
        llm_response = await ask_llm(msg.question)
        sql = llm_response.get("sql")
        explication = llm_response.get("explication", "")
        if not sql:
            return {"answer": explication, "data": [], "sql": None}
        data = execute_query(sql)
        return {"answer": explication, "data": data, "sql": sql, "count": len(data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
def get_stats():
    stats = {}
    queries = {
        "total_trajets":    "SELECT COUNT(*) as n FROM trajets WHERE statut='termine'",
        "trajets_en_cours": "SELECT COUNT(*) as n FROM trajets WHERE statut='en_cours'",
        "vehicules_actifs": "SELECT COUNT(*) as n FROM vehicules WHERE statut='actif'",
        "incidents_ouverts":"SELECT COUNT(*) as n FROM incidents WHERE resolu=FALSE",
        "recette_totale":   "SELECT COALESCE(SUM(recette),0) as n FROM trajets WHERE statut='termine'",
    }
    for key, sql in queries.items():
        result = execute_query(sql)
        stats[key] = result[0]["n"] if result else 0
    return stats

@app.get("/api/vehicules")
def get_vehicules():
    return execute_query("SELECT * FROM vehicules ORDER BY immatriculation")

@app.get("/api/chauffeurs")
def get_chauffeurs():
    return execute_query(
        "SELECT c.*, v.immatriculation FROM chauffeurs c "
        "LEFT JOIN vehicules v ON c.vehicule_id = v.id ORDER BY c.nom"
    )

@app.get("/api/trajets/recent")
def get_trajets_recent():
    return execute_query(
        "SELECT t.*, l.nom as ligne, ch.nom as chauffeur_nom, v.immatriculation "
        "FROM trajets t "
        "JOIN lignes l ON t.ligne_id = l.id "
        "JOIN chauffeurs ch ON t.chauffeur_id = ch.id "
        "JOIN vehicules v ON t.vehicule_id = v.id "
        "ORDER BY t.date_heure_depart DESC LIMIT 20"
    )

@app.get("/api/lignes")
def get_lignes():
    return execute_query("SELECT * FROM lignes ORDER BY code")

@app.get("/api/incidents")
def get_incidents():
    return execute_query(
        "SELECT i.*, t.date_heure_depart, l.nom as ligne, ch.nom as chauffeur "
        "FROM incidents i "
        "JOIN trajets t ON i.trajet_id = t.id "
        "JOIN lignes l ON t.ligne_id = l.id "
        "JOIN chauffeurs ch ON t.chauffeur_id = ch.id "
        "ORDER BY i.date_incident DESC"
    )

@app.get("/")
def root():
    return FileResponse("index.html")

@app.get("/health")
def health():
    return {"status": "ok", "app": "TranspoBot"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
