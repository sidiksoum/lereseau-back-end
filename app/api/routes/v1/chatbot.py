from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.dependencies.auth import get_db, get_current_active_user
from app.models.user import User
from app.services.chatbot_ia import ChatbotIAService
from pydantic import BaseModel
from typing import List, Dict, Optional

router = APIRouter()

class ChatRequest(BaseModel):
    question: str
    history: Optional[List[Dict[str, str]]] = None # [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

class ChatResponse(BaseModel):
    answer: str

@router.post("/ask", response_model=ChatResponse)
async def ask_chatbot(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not req.question or len(req.question.strip()) == 0:
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide.")
        
    answer = await ChatbotIAService.ask_question(
        db=db, 
        current_user=current_user, 
        question=req.question, 
        history=req.history
    )
    
    return ChatResponse(answer=answer)
