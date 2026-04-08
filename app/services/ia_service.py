from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.ia_service import obter_resposta_ia

router = APIRouter()

class PerguntaRequest(BaseModel):
    prompt_context: str
    pergunta_usuario: str

class RespostaResponse(BaseModel):
    resposta: str

@router.post("/perguntar", response_model=RespostaResponse)
async def perguntar_ia(request: PerguntaRequest):
    try:
        resposta = obter_resposta_ia(request.prompt_context, request.pergunta_usuario)
        return RespostaResponse(resposta=resposta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))