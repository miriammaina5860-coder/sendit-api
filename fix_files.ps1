# fix_files.ps1
Write-Host "Fixing all files..." -ForegroundColor Green

# Fix models/document.py
Write-Host "Fixing models/document.py..." -ForegroundColor Yellow
@'
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import Optional

class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    original_filename: str
    file_size: int
    file_type: str
    status: str = Field(default="uploaded")
    city: str = Field(index=True)
    country: str = Field(default="Kenya")
    weather_data: Optional[str] = Field(default=None)
    weather_fetched_at: Optional[datetime] = None
    description: Optional[str] = None
    uploader_id: int = Field(foreign_key="user.id")
    uploader: "User" = Relationship(back_populates="documents")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    file_path: str

class DocumentCreate(SQLModel):
    city: str = Field(min_length=2, max_length=100)
    country: str = Field(default="Kenya", min_length=2, max_length=100)
    description: Optional[str] = None

class DocumentUpdate(SQLModel):
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    country: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
'@ | Out-File -FilePath "models\document.py" -Encoding UTF8

Write-Host "All files fixed!" -ForegroundColor Green
Write-Host "Now run: python -m uvicorn main:app --reload" -ForegroundColor Cyan