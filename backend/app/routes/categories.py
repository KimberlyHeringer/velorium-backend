"""
Rotas de Categorias Personalizadas
Arquivo: backend/app/routes/categories.py

Funcionalidade: CRUD de categorias personalizadas do usuário

📋 ENDPOINTS:
  - GET /api/v1/categories - Listar categorias do usuário (com paginação)
  - POST /api/v1/categories - Criar categoria
  - PUT /api/v1/categories/{id} - Editar categoria
  - DELETE /api/v1/categories/{id} - Remover categoria

🔧 VALIDAÇÕES:
  - Nome único por usuário
  - Value (slug) único por usuário
  - ObjectId válido
  - Campos permitidos no update
  - Paginação (page, limit)

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 ÚLTIMA ATUALIZAÇÃO: 10/07/2026
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.models.custom_category import (
    CustomCategory, 
    CustomCategoryCreate, 
    CustomCategoryUpdate,
    CustomCategoryResponse
)
from app.models.user import UserResponse
from app.services.category_service import CategoryService
from app.utils.auth import get_current_user
from app.utils.validators import convert_objectid_to_str, validate_object_id
from app.utils.logger import setup_logger
from app.utils.rate_limiter import limiter, get_user_rate_limit_key
from app.utils.i18n import get_message, get_language_from_request
from app.utils.exceptions import I18nHTTPException, NotFoundException, ValidationException

logger = setup_logger(__name__)

router = APIRouter(prefix="/categories", tags=["Categorias Personalizadas"])


# ================================================================
# ENDPOINTS
# ================================================================

@router.get("/", response_model=dict)
@limiter.limit("30/minute")
async def get_categories(
    request: Request,
    type: Optional[str] = Query(None, description="Filtrar por tipo (expense, income, goal, investment, bill)"),
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página (máx 100)"),
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Lista todas as categorias personalizadas do usuário com paginação.
    
    🔧 PAGINAÇÃO:
        - Padrão: 20 itens por página
        - Máximo: 100 itens por página
        - Ordenação: alfabética (name)
    
    Args:
        type: Filtrar por tipo (expense, income, goal, investment, bill)
        page: Número da página (padrão: 1)
        limit: Itens por página (padrão: 20, máximo: 100)
    
    Returns:
        dict: {
            "items": Lista de categorias,
            "total": Total de itens,
            "page": Página atual,
            "limit": Itens por página,
            "pages": Total de páginas
        }
    """
    try:
        service = CategoryService(db)
        result = await service.get_categories(
            str(current_user.id), 
            type,
            page,
            limit
        )
        return result
    except Exception as e:
        logger.error(f"❌ Erro ao listar categorias: {e}")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_SERVER",
            request=request
        )


@router.post("/", response_model=CustomCategoryResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_category(
    request: Request,
    category_data: CustomCategoryCreate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Cria uma nova categoria personalizada com validação de duplicatas.
    
    🔧 VALIDAÇÕES:
        - Nome não pode ser duplicado por usuário
        - Value (slug) gerado automaticamente e único
    
    Args:
        category_data: Dados da categoria
    
    Returns:
        CustomCategoryResponse: Categoria criada
    """
    try:
        service = CategoryService(db)
        category = await service.create_category(
            str(current_user.id),
            category_data.model_dump()
        )
        return category
    except ValueError as e:
        if "já existe" in str(e):
            raise ValidationException(
                message_key="CATEGORY_ALREADY_EXISTS",
                request=request
            )
        raise ValidationException(
            message_key="ERROR_VALIDATION",
            request=request
        )
    except Exception as e:
        logger.error(f"❌ Erro ao criar categoria: {e}")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_SERVER",
            request=request
        )


@router.put("/{category_id}", response_model=CustomCategoryResponse)
@limiter.limit("15/minute")
async def update_category(
    request: Request,
    category_id: str,
    category_data: CustomCategoryUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Atualiza uma categoria personalizada com validação de duplicatas.
    
    🔧 VALIDAÇÕES:
        - ObjectId válido
        - Campos permitidos (name, value, iconName, color, type)
        - Nome não pode ser duplicado (se alterado)
        - Value (slug) atualizado automaticamente se nome mudar
    
    Args:
        category_id: ID da categoria
        category_data: Dados para atualizar
    
    Returns:
        CustomCategoryResponse: Categoria atualizada
    """
    # Valida ObjectId
    if not validate_object_id(category_id):
        raise ValidationException(
            message_key="ERROR_INVALID_ID",
            request=request,
            field_name="category_id"
        )
    
    try:
        service = CategoryService(db)
        category = await service.update_category(
            category_id,
            str(current_user.id),
            category_data.model_dump(exclude_unset=True)
        )
        return category
    except ValueError as e:
        error_msg = str(e)
        if "não encontrada" in error_msg:
            raise NotFoundException(
                message_key="CATEGORY_NOT_FOUND",
                request=request
            )
        elif "já existe" in error_msg:
            raise ValidationException(
                message_key="CATEGORY_ALREADY_EXISTS",
                request=request
            )
        elif "inválido" in error_msg:
            raise ValidationException(
                message_key="ERROR_INVALID_ID",
                request=request,
                field_name="category_id"
            )
        else:
            raise ValidationException(
                message_key="ERROR_VALIDATION",
                request=request
            )
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar categoria: {e}")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_SERVER",
            request=request
        )


@router.delete("/{category_id}", response_model=dict)
@limiter.limit("10/minute")
async def delete_category(
    request: Request,
    category_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db=Depends(get_database)
):
    """
    Remove (soft delete) uma categoria personalizada.
    
    🔧 SOFT DELETE:
        - Marca is_deleted = True
        - Registra deleted_at
        - Dados permanecem no banco (recuperáveis)
    
    Args:
        category_id: ID da categoria
    
    Returns:
        dict: Status da operação
    """
    # Valida ObjectId
    if not validate_object_id(category_id):
        raise ValidationException(
            message_key="ERROR_INVALID_ID",
            request=request,
            field_name="category_id"
        )
    
    try:
        service = CategoryService(db)
        await service.delete_category(category_id, str(current_user.id))
        
        language = get_language_from_request(request)
        return {
            "message": get_message("CATEGORY_DELETED", language),
            "success": True,
            "id": category_id
        }
    except ValueError as e:
        if "não encontrada" in str(e):
            raise NotFoundException(
                message_key="CATEGORY_NOT_FOUND",
                request=request
            )
        raise ValidationException(
            message_key="ERROR_VALIDATION",
            request=request
        )
    except Exception as e:
        logger.error(f"❌ Erro ao deletar categoria: {e}")
        raise I18nHTTPException(
            status_code=500,
            message_key="ERROR_SERVER",
            request=request
        )


# ================================================================
# DECISÕES DOCUMENTADAS
# ================================================================

"""
📋 CHANGELOG - 10/07/2026
──────────────────────────────────────────────────────────────

✅ CRIADO:
   1. Endpoint GET /categories com paginação (page, limit)
   2. Endpoint POST /categories com validação de duplicatas
   3. Endpoint PUT /categories/{id} com validações
   4. Endpoint DELETE /categories/{id} com soft delete

✅ MELHORIAS:
   5. Validação de ObjectId
   6. Filtro de campos permitidos no update
   7. Paginação (padrão 20, máximo 100)
   8. Rate limiting (GET: 30/min, POST: 20/min, PUT: 15/min, DELETE: 10/min)
   9. I18n completo
   10. Logs estruturados
   11. Tratamento de erros específicos

✅ PADRÕES SEGUIDOS:
   - Rate limiting
   - I18n completo
   - Validações de entrada
   - Logs estruturados
   - Documentação completa

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 ÚLTIMA ATUALIZAÇÃO: 10/07/2026
"""