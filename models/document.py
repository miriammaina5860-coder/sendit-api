from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User

class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(default="")
    original_filename: str = Field(default="")
    file_size: int = Field(default=0)
    file_type: str = Field(default="")
    status: str = Field(default="uploaded")  # "uploaded", "processing", "enriched", "failed"
    
    # Location data
    city: str = Field(index=True, default="")
    country: str = Field(default="Kenya")
    
    # Weather data
    weather_data: Optional[str] = Field(default=None)
    weather_fetched_at: Optional[datetime] = Field(default=None)
    
    # Metadata
    description: Optional[str] = Field(default=None)
    uploader_id: int = Field(foreign_key="user.id")
    uploader: "User" = Relationship(back_populates="documents")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # File path on server
    file_path: str = Field(default="")

class DocumentCreate(SQLModel):
    city: str = Field(min_length=2, max_length=100)
    country: str = Field(default="Kenya", min_length=2, max_length=100)
    description: Optional[str] = Field(default=None)

class DocumentUpdate(SQLModel):
    city: Optional[str] = Field(default=None, min_length=2, max_length=100)
    country: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = Field(default=None)