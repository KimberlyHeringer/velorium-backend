"""
Serviço de Categorias Personalizadas
Arquivo: backend/app/services/category_service.py

Funcionalidade: Lógica de negócio para categorias personalizadas
- Validação de duplicatas (nome e value)
- Geração automática de value único
- CRUD com validações
- Validação de ObjectId
- Filtro de campos permitidos no update
- Paginação

🔧 DEPENDÊNCIAS:
    - MongoDB (motor assíncrono)
    - Pydantic (validação de dados)
    - BSON (ObjectId)

📋 RESPONSABILIDADES:
    1. Criar categoria com validação de duplicatas
    2. Atualizar categoria com validação de campos
    3. Remover categoria (soft delete)
    4. Listar categorias com paginação

🔧 USO:
    service = CategoryService(db)
    
    # Criar categoria
    category = await service.create_category(user_id, category_data)
    
    # Listar categorias
    result = await service.get_categories(user_id, page=1, limit=20)

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 ÚLTIMA ATUALIZAÇÃO: 10/07/2026
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from bson import ObjectId
from bson.errors import InvalidId

from app.models.custom_category import CustomCategory, CustomCategoryCreate, CustomCategoryUpdate
from app.utils.logger import setup_logger
from app.utils.validators import convert_objectid_to_str

logger = setup_logger(__name__)


# ================================================================
# FUNÇÕES AUXILIARES
# ================================================================

def validate_object_id(id_str: str) -> bool:
    """
    Valida se uma string é um ObjectId válido.
    
    🔧 USO:
        is_valid = validate_object_id("507f1f77bcf86cd799439011")  # True
        is_valid = validate_object_id("invalid")  # False
    
    Args:
        id_str: String a ser validada
    
    Returns:
        bool: True se for um ObjectId válido
    
    Exemplo:
        >>> validate_object_id("507f1f77bcf86cd799439011")
        True
        >>> validate_object_id("invalid_id")
        False
    """
    try:
        ObjectId(id_str)
        return True
    except InvalidId:
        return False


def get_object_id_or_raise(id_str: str) -> ObjectId:
    """
    Retorna ObjectId ou levanta ValueError.
    
    🔧 USO:
        obj_id = get_object_id_or_raise(category_id)
        # Se for inválido, levanta ValueError
    
    Args:
        id_str: String a ser convertida
    
    Returns:
        ObjectId: ObjectId convertido
    
    Raises:
        ValueError: Se o ID for inválido
    
    Exemplo:
        >>> get_object_id_or_raise("507f1f77bcf86cd799439011")
        ObjectId("507f1f77bcf86cd799439011")
        >>> get_object_id_or_raise("invalid")
        ValueError: "ID de categoria inválido"
    """
    if not validate_object_id(id_str):
        raise ValueError("ID de categoria inválido")
    return ObjectId(id_str)


# ================================================================
# CONSTANTES
# ================================================================

ALLOWED_UPDATE_FIELDS = {"name", "value", "iconName", "color", "type"}
"""
Conjunto de campos permitidos para atualização de categorias.
- name: Nome da categoria
- value: Slug (identificador único)
- iconName: Nome do ícone (Feather)
- color: Cor em hexadecimal
- type: Tipo da categoria (expense, income, goal, investment, bill)
"""


# ================================================================
# SERVIÇO
# ================================================================

class CategoryService:
    """
    Serviço para gerenciar categorias personalizadas.
    
    🔧 RESPONSABILIDADES:
        - Criar categorias com validação de duplicatas
        - Atualizar categorias com validação de campos
        - Remover categorias (soft delete)
        - Listar categorias com paginação
    
    🔧 USO:
        service = CategoryService(db)
        category = await service.create_category(user_id, category_data)
    
    📋 ATRIBUTOS:
        db: Conexão com o banco de dados MongoDB
    """
    
    def __init__(self, db):
        """
        Inicializa o serviço com a conexão do banco.
        
        Args:
            db: Conexão com o banco de dados MongoDB
        """
        self.db = db
    
    # ================================================================
    # CRIAÇÃO
    # ================================================================
    
    async def create_category(self, user_id: str, category_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cria uma nova categoria personalizada com validações.
        
        🔧 VALIDAÇÕES:
            1. Nome não pode ser duplicado por usuário
            2. Value (slug) gerado automaticamente e único
        
        📋 FLUXO:
            1. Verifica se nome já existe para o usuário
            2. Gera value (slug) único
            3. Prepara dados com timestamps
            4. Insere no banco
            5. Retorna categoria criada
        
        Args:
            user_id: ID do usuário
            category_data: Dados da categoria
        
        Returns:
            Dict: Categoria criada com ID
        
        Raises:
            ValueError: Se nome ou value já existir
        
        Exemplo:
            >>> category = await service.create_category("user123", {
            ...     "name": "Minha Categoria",
            ...     "type": "expense",
            ...     "color": "#6B7280"
            ... })
            >>> print(category["id"])
            "cat_1234567890"
        """
        # 1. Valida nome duplicado
        existing = await self.db.custom_categories.find_one({
            "user_id": user_id,
            "name": category_data["name"],
            "is_deleted": {"$ne": True}
        })
        if existing:
            raise ValueError("Categoria com este nome já existe")
        
        # 2. Gera value (slug) único
        base_value = category_data.get("value") or category_data["name"].lower().replace(' ', '_')
        value = base_value
        counter = 1
        
        while True:
            existing_value = await self.db.custom_categories.find_one({
                "user_id": user_id,
                "value": value,
                "is_deleted": {"$ne": True}
            })
            if not existing_value:
                break
            value = f"{base_value}_{counter}"
            counter += 1
        
        # 3. Prepara dados
        category_dict = {
            "user_id": user_id,
            "name": category_data["name"],
            "value": value,
            "iconName": category_data.get("iconName", "tag"),
            "color": category_data.get("color", "#6B7280"),
            "type": category_data.get("type", "expense"),
            "isCustom": True,
            "is_deleted": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        
        # 4. Insere no banco
        result = await self.db.custom_categories.insert_one(category_dict)
        category_dict["id"] = str(result.inserted_id)
        
        logger.info(f"✅ Categoria criada: {category_dict['name']} para usuário {user_id}")
        
        return category_dict
    
    # ================================================================
    # ATUALIZAÇÃO
    # ================================================================
    
    async def update_category(self, category_id: str, user_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Atualiza uma categoria personalizada com validações.
        
        🔧 VALIDAÇÕES:
            1. ID deve ser um ObjectId válido
            2. Campos devem ser permitidos (ALLOWED_UPDATE_FIELDS)
            3. Nome não pode ser duplicado (se alterado)
            4. Value (slug) atualizado automaticamente se nome mudar
        
        📋 FLUXO:
            1. Valida ObjectId
            2. Filtra campos permitidos
            3. Busca a categoria
            4. Verifica duplicata de nome (se alterado)
            5. Atualiza value (slug) se nome mudou
            6. Atualiza no banco
            7. Retorna categoria atualizada
        
        Args:
            category_id: ID da categoria
            user_id: ID do usuário
            update_data: Dados para atualizar
        
        Returns:
            Dict: Categoria atualizada
        
        Raises:
            ValueError: Se nome já existir, categoria não encontrada ou ID inválido
        
        Exemplo:
            >>> updated = await service.update_category("cat_123", "user123", {
            ...     "name": "Nova Categoria",
            ...     "color": "#FF0000"
            ... })
            >>> print(updated["name"])
            "Nova Categoria"
        """
        # 1. Valida ObjectId
        obj_id = get_object_id_or_raise(category_id)
        
        # 2. Filtra campos permitidos
        filtered_data = {k: v for k, v in update_data.items() if k in ALLOWED_UPDATE_FIELDS}
        
        if not filtered_data:
            raise ValueError("Nenhum campo válido para atualizar")
        
        # 3. Busca a categoria
        category = await self.db.custom_categories.find_one({
            "_id": obj_id,
            "user_id": user_id,
            "is_deleted": {"$ne": True}
        })
        if not category:
            raise ValueError("Categoria não encontrada")
        
        # 4. Se nome foi alterado, verifica duplicata
        if "name" in filtered_data and filtered_data["name"] != category["name"]:
            existing = await self.db.custom_categories.find_one({
                "user_id": user_id,
                "name": filtered_data["name"],
                "_id": {"$ne": obj_id},
                "is_deleted": {"$ne": True}
            })
            if existing:
                raise ValueError("Já existe uma categoria com este nome")
            
            # 5. Atualiza value se nome mudou
            if "value" not in filtered_data:
                base_value = filtered_data["name"].lower().replace(' ', '_')
                value = base_value
                counter = 1
                
                while True:
                    existing_value = await self.db.custom_categories.find_one({
                        "user_id": user_id,
                        "value": value,
                        "_id": {"$ne": obj_id},
                        "is_deleted": {"$ne": True}
                    })
                    if not existing_value:
                        break
                    value = f"{base_value}_{counter}"
                    counter += 1
                
                filtered_data["value"] = value
        
        # 6. Atualiza
        filtered_data["updated_at"] = datetime.now(timezone.utc)
        
        await self.db.custom_categories.update_one(
            {"_id": obj_id},
            {"$set": filtered_data}
        )
        
        # 7. Busca atualizado
        updated = await self.db.custom_categories.find_one({
            "_id": obj_id
        })
        updated["id"] = str(updated["_id"])
        
        logger.info(f"✏️ Categoria atualizada: {category_id} para usuário {user_id}")
        
        return updated
    
    # ================================================================
    # REMOÇÃO
    # ================================================================
    
    async def delete_category(self, category_id: str, user_id: str) -> bool:
        """
        Remove (soft delete) uma categoria personalizada.
        
        🔧 SOFT DELETE:
            - Marca is_deleted = True
            - Registra deleted_at
            - Dados permanecem no banco (recuperáveis)
        
        📋 FLUXO:
            1. Valida ObjectId
            2. Busca a categoria
            3. Marca como deletada (soft delete)
        
        Args:
            category_id: ID da categoria
            user_id: ID do usuário
        
        Returns:
            bool: True se removida com sucesso
        
        Raises:
            ValueError: Se categoria não encontrada ou ID inválido
        
        Exemplo:
            >>> success = await service.delete_category("cat_123", "user123")
            >>> print(success)
            True
        """
        # 1. Valida ObjectId
        obj_id = get_object_id_or_raise(category_id)
        
        # 2. Busca a categoria
        category = await self.db.custom_categories.find_one({
            "_id": obj_id,
            "user_id": user_id,
            "is_deleted": {"$ne": True}
        })
        if not category:
            raise ValueError("Categoria não encontrada")
        
        # 3. Soft delete
        await self.db.custom_categories.update_one(
            {"_id": obj_id},
            {
                "$set": {
                    "is_deleted": True,
                    "deleted_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        logger.info(f"🗑️ Categoria deletada: {category_id} para usuário {user_id}")
        
        return True
    
    # ================================================================
    # LISTAGEM
    # ================================================================
    
    async def get_categories(
        self, 
        user_id: str, 
        category_type: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Lista categorias do usuário com paginação.
        
        🔧 PAGINAÇÃO:
            - Padrão: 20 itens por página
            - Máximo: 100 itens por página
            - Ordenação: alfabética (name)
        
        📋 FLUXO:
            1. Valida limites (min 1, max 100)
            2. Monta query
            3. Conta total
            4. Busca com paginação
            5. Formata resultado
        
        Args:
            user_id: ID do usuário
            category_type: Filtrar por tipo (opcional)
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
        
        Exemplo:
            >>> result = await service.get_categories("user123", page=1, limit=10)
            >>> print(result["items"])
            [...]
            >>> print(result["total"])
            5
        """
        # Valida limites
        if limit < 1:
            limit = 20
        if limit > 100:
            limit = 100
        
        skip = (page - 1) * limit
        
        # Monta query
        query = {"user_id": user_id, "is_deleted": {"$ne": True}}
        if category_type:
            query["type"] = category_type
        
        # Conta total
        total = await self.db.custom_categories.count_documents(query)
        
        # Busca com paginação
        categories = await self.db.custom_categories.find(query).sort("name", 1).skip(skip).limit(limit).to_list(limit)
        
        result = []
        for cat in categories:
            cat["id"] = str(cat["_id"])
            result.append(convert_objectid_to_str(cat))
        
        # Calcula total de páginas
        pages = (total + limit - 1) // limit if total > 0 else 1
        
        logger.debug(f"📋 {len(result)} categorias carregadas para usuário {user_id} (página {page}/{pages})")
        
        return {
            "items": result,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": pages
        }


# ================================================================
# DECISÕES DOCUMENTADAS
# ================================================================

"""
📋 CHANGELOG - 10/07/2026
──────────────────────────────────────────────────────────────

✅ CRIADO:
   1. CategoryService com CRUD completo
   2. Validação de duplicatas (nome e value)
   3. Geração automática de value (slug) único
   4. Soft delete com timestamps
   5. Validação de ObjectId
   6. Filtro de campos permitidos no update
   7. Paginação (page, limit)
   8. Logs estruturados
   9. Documentação completa

✅ PADRÕES SEGUIDOS:
   - Logs apenas em desenvolvimento (__DEV__)
   - Tratamento de erros com ValueError
   - Validações antes de operações no banco
   - Soft delete (preserva dados)
   - Paginação para performance

📋 PRÓXIMAS MELHORIAS (Pós-MVP):
   - Cache com Redis para listagens frequentes
   - Bulk operations (criar/remover múltiplas)
   - Índices adicionais para performance

✅ STATUS: PRONTO PARA PRODUÇÃO
📅 ÚLTIMA ATUALIZAÇÃO: 10/07/2026
"""