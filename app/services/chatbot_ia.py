import httpx
import asyncio
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.user import User
from app.models.opportunity import Opportunity
from typing import List, Dict

class ChatbotIAService:
    @staticmethod
    def _build_context_prompt(db: Session, current_user: User) -> str:
        # Extraire le contexte utilisateur
        domain = current_user.studyDomain or "Général"
        level = current_user.educationLevel or "Non spécifié"
        skills = ", ".join(current_user.skills) if current_user.skills else "Non spécifié"
        
        # Trouver des bourses/opportunités qui correspondent grossièrement
        opps = db.query(Opportunity).filter(
            Opportunity.isActive == True
        ).limit(5).all() # Simplification: dans un vrai RAG, utiliser un VectorDB ou filter par domaine.
        
        opps_text = ""
        for o in opps:
            opps_text += f"- Titre: {o.title}\n  Domaine: {o.domain}\n  Organisation: {o.organization}\n  Date limite: {o.deadline}\n\n"
            
        # Trouver des mentors
        mentors = db.query(User).filter(
            User.roleType == "professional"
        ).limit(5).all()
        
        mentors_text = ""
        for m in mentors:
            job = m.jobTitle or "Professionnel"
            work_domain = m.workDomain or "Non défini"
            mentors_text += f"- {m.firstName} {m.lastName} : {job} chez {work_domain}\n"

        prompt = f"""Tu es LeRéseauIA, l'assistant virtuel intelligent de la plateforme éducative et professionnelle 'LeRéseau.sn'. 
Ton rôle est d'aider les étudiants et professionnels en répondant par rapport à leurs profils et aux données de la plateforme. 
Tu dois rester concis, professionnel et toujours proposer des pistes d'orientation claires.

--- CONTEXTE UTILISATEUR ACTUEL ---
Prénom complet: {current_user.firstName} {current_user.lastName}
Niveau d'étude: {level}
Domaine d'étude: {domain}
Compétences: {skills}

--- OPPORTUNITÉS (BOURSES/EMPLOIS) DISPONIBLES SUR LA PLATEFORME ---
{opps_text if opps_text else "Aucune opportunité spécifique pour le moment."}

--- MENTORS DISPONIBLES SUR LA PLATEFORME ---
{mentors_text if mentors_text else "Aucun mentor spécifique trouvé."}

Tu te baseras sur ce contexte pour recommander des bourses ou des mentors de la plateforme si cela est pertinent. 
Cependant, si la réponse ou l'information demandée ne se trouve pas dans ce contexte local, tu as l'autorisation totale d'utiliser tes propres connaissances globales (recherche d'informations générales, conseils d'orientation, astuces académiques ou autres bourses mondiales) pour fournir la réponse la plus adéquate et complète possible.
Si l'utilisateur ne demande rien de précis, salue-le par son prénom et lance la discussion sur son domaine !
"""
        return prompt

    # Liste ordonnée de modèles gratuits actifs sur OpenRouter (Mai 2026)
    FREE_MODELS_FALLBACK = [
        "google/gemma-4-31b-it:free",
        "google/gemma-4-26b-a4b-it:free",
        "nvidia/nemotron-nano-9b-v2:free",
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "openai/gpt-oss-20b:free",
        "minimax/minimax-m2.5:free",
        "tencent/hy3-preview:free",
        "inclusionai/ring-2.6-1t:free",
    ]

    @staticmethod
    async def ask_question(db: Session, current_user: User, question: str, history: List[Dict[str, str]] = None) -> str:
        if history is None:
            history = []
            
        system_content = ChatbotIAService._build_context_prompt(db, current_user)
        
        messages = [{"role": "system", "content": system_content}]
        
        # Ajouter l'historique valide (filtrer les faux champs Swagger)
        if history:
            for item in history:
                if isinstance(item, dict) and "role" in item and "content" in item:
                    messages.append({"role": item["role"], "content": item["content"]})
        
        messages.append({"role": "user", "content": question})
        
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://lereseau.sn",
            "X-Title": "LeReseau.sn Chatbot",
        }
        
        # Construire la liste de modèles à essayer : le modèle configuré en premier, puis les fallbacks
        models_to_try = [settings.OPENROUTER_MODEL] + [
            m for m in ChatbotIAService.FREE_MODELS_FALLBACK if m != settings.OPENROUTER_MODEL
        ]
        
        def _call_model_sync(model: str) -> str | None:
            """Appel synchrone à OpenRouter — exécuté dans un thread pool pour éviter les blocages DNS sur Windows."""
            payload = {"model": model, "messages": messages}
            try:
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(
                        f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    if response.status_code == 429:
                        print(f"[Chatbot] Modèle {model} rate-limité (429), essai du suivant...")
                        return None
                    if response.status_code != 200:
                        print(f"[Chatbot] Erreur API ({response.status_code}) avec {model}: {response.text}")
                        return None
                    data = response.json()
                    if "error" in data:
                        print(f"[Chatbot] Erreur objet avec {model}: {data['error']}")
                        return None
                    choices = data.get("choices", [])
                    if not choices:
                        print(f"[Chatbot] Aucun choices avec {model}: {data}")
                        return None
                    content = choices[0].get("message", {}).get("content", "")
                    if content:
                        print(f"[Chatbot] ✅ Réponse obtenue via: {model}")
                        return content
                    return None
            except Exception as e:
                print(f"[Chatbot] Exception avec {model}: {e}")
                return None

        # Essayer chaque modèle dans un thread séparé (résout le problème DNS async sur Windows)
        for model in models_to_try:
            result = await asyncio.to_thread(_call_model_sync, model)
            if result:
                return result
        
        return "Je suis temporairement surchargé. Tous les serveurs d'IA gratuits sont actuellement saturés. Veuillez réessayer dans quelques instants. ⏳"
