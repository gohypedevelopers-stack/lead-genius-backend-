"""
Base repository with generic CRUD operations.
"""
import uuid
from typing import TypeVar, Generic, Type, Optional, List, Any
from datetime import datetime

from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import func

from backend.core.pagination import create_paginated_response

ModelType = TypeVar("ModelType", bound=SQLModel)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository with CRUD operations.
    Inherit and specify the model class.
    """
    
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session
    
    async def create(self, obj_in: dict) -> ModelType:
        """Create a new record."""
        db_obj = self.model(**obj_in)
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj
    
    async def get(self, id: uuid.UUID) -> Optional[ModelType]:
        """Get a record by ID."""
        return await self.session.get(self.model, id)
    
    async def get_by_field(self, field: str, value: Any) -> Optional[ModelType]:
        """Get a record by a specific field."""
        query = select(self.model).where(getattr(self.model, field) == value)
        result = await self.session.exec(query)
        return result.first()
    
    async def list(
        self, 
        org_id: Optional[uuid.UUID] = None,
        filters: Optional[dict] = None,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> List[ModelType]:
        """List all records with optional filters."""
        query = select(self.model)
        
        # Filter by organization if model has org_id
        if org_id and hasattr(self.model, 'org_id'):
            query = query.where(self.model.org_id == org_id)
        
        # Apply additional filters
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field) and value is not None:
                    query = query.where(getattr(self.model, field) == value)
        
        # Apply ordering
        if hasattr(self.model, order_by):
            order_column = getattr(self.model, order_by)
            query = query.order_by(order_column.desc() if order_desc else order_column)
        
        result = await self.session.exec(query)
        return result.all()
    
    async def list_paginated(
        self,
        org_id: Optional[uuid.UUID] = None,
        filters: Optional[dict] = None,
        page: int = 1,
        limit: int = 20,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> dict:
        """List records with pagination."""
        # Build base query
        query = select(self.model)
        
        if org_id and hasattr(self.model, 'org_id'):
            query = query.where(self.model.org_id == org_id)
        
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field) and value is not None:
                    query = query.where(getattr(self.model, field) == value)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.exec(count_query)
        total = total_result.one()
        
        # Apply ordering
        if hasattr(self.model, order_by):
            order_column = getattr(self.model, order_by)
            query = query.order_by(order_column.desc() if order_desc else order_column)
        
        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        
        result = await self.session.exec(query)
        items = result.all()
        
        return create_paginated_response(items, total, page, limit)
    
    async def update(self, id: uuid.UUID, obj_in: dict) -> Optional[ModelType]:
        """Update a record."""
        db_obj = await self.get(id)
        if not db_obj:
            return None
        
        for field, value in obj_in.items():
            if hasattr(db_obj, field) and value is not None:
                setattr(db_obj, field, value)
        
        # Update timestamp if exists
        if hasattr(db_obj, 'updated_at'):
            db_obj.updated_at = datetime.utcnow()
        
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj
    
    async def delete(self, id: uuid.UUID) -> bool:
        """Delete a record."""
        db_obj = await self.get(id)
        if not db_obj:
            return False
        
        await self.session.delete(db_obj)
        await self.session.commit()
        return True
    
    async def count(self, org_id: Optional[uuid.UUID] = None, filters: Optional[dict] = None) -> int:
        """Count records."""
        query = select(func.count()).select_from(self.model)
        
        if org_id and hasattr(self.model, 'org_id'):
            query = query.where(self.model.org_id == org_id)
        
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field) and value is not None:
                    query = query.where(getattr(self.model, field) == value)
        
        result = await self.session.exec(query)
        return result.one()
    
    async def exists(self, id: uuid.UUID) -> bool:
        """Check if a record exists."""
        obj = await self.get(id)
        return obj is not None
