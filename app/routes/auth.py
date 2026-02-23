from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt
import os

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    monthly_income: float
    location: str
    profession_type: str = ""
    occupation: str = ""
    financial_goal: str = ""

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# Simulação de banco de dados (por enquanto)
fake_db = {}
@router.post("/register")
async def register(user: UserRegister):
    try:
        print(f"===== RECEBENDO REGISTRO =====")
        print(f"Email: {user.email}")
        print(f"Nome: {user.name}")
        print(f"Renda: {user.monthly_income}")
        print(f"Localização: {user.location}")
        print(f"Tipo de perfil: {user.profession_type}")
        print(f"Ocupação: {user.occupation}")
        print(f"Objetivo: {user.financial_goal}")
        
        # Verificar se usuário já existe
        if user.email in fake_db:
            print(f"Email já cadastrado: {user.email}")
            raise HTTPException(status_code=400, detail="Email já cadastrado")
        
        # Criar novo usuário
        print("Criando hash da senha...")
        password_hash = pwd_context.hash(user.password)
        print("Hash criado com sucesso")
        
        user_data = {
            "id": len(fake_db) + 1,
            "name": user.name,
            "email": user.email,
            "password_hash": password_hash,
            "monthly_income": user.monthly_income,
            "location": user.location,
            "profession_type": user.profession_type,
            "occupation": user.occupation,
            "financial_goal": user.financial_goal,
            "created_at": datetime.utcnow()
        }
        
        print(f"Salvando usuário no banco de dados...")
        fake_db[user.email] = user_data
        print(f"Usuário {user.email} cadastrado com sucesso! ID: {user_data['id']}")
        print(f"Total de usuários no banco: {len(fake_db)}")
        
        return {"message": "Usuário criado com sucesso!", "id": user_data["id"]}
        
    except HTTPException:
        print("Exceção HTTP capturada")
        raise
    except Exception as e:
        print(f"❌ ERRO DETALHADO: {str(e)}")
        print(f"Tipo do erro: {type(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
@router.post("/login")
async def login(user: UserLogin):
    try:
        print(f"Tentativa de login: {user.email}")
        
        # Buscar usuário
        db_user = fake_db.get(user.email)
        if not db_user:
            raise HTTPException(status_code=401, detail="Email ou senha inválidos")
        
        # Verificar senha
        if not pwd_context.verify(user.password, db_user["password_hash"]):
            raise HTTPException(status_code=401, detail="Email ou senha inválidos")
        
        # Gerar token JWT
        JWT_SECRET = os.getenv("JWT_SECRET", "minha-chave-secreta-temporaria")
        token = jwt.encode(
            {
                "user_id": db_user["id"],
                "email": db_user["email"],
                "exp": datetime.utcnow() + timedelta(days=7)
            },
            JWT_SECRET,
            algorithm="HS256"
        )
        
        print(f"Login bem-sucedido: {user.email}")
        
        return {
            "token": token,
            "user": {
                "id": db_user["id"],
                "name": db_user["name"],
                "email": db_user["email"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erro no login: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")