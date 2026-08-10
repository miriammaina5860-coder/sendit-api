# fix_pydantic_errors.ps1
Write-Host "Fixing Pydantic/SQLModel errors..." -ForegroundColor Green

# Fix models/document.py
Write-Host "Updating models/document.py..." -ForegroundColor Yellow
@"
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
    status: str = Field(default="uploaded")
    
    city: str = Field(index=True, default="")
    country: str = Field(default="Kenya")
    
    weather_data: Optional[str] = Field(default=None)
    weather_fetched_at: Optional[datetime] = Field(default=None)
    
    description: Optional[str] = Field(default=None)
    uploader_id: int = Field(foreign_key="user.id")
    uploader: "User" = Relationship(back_populates="documents")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    file_path: str = Field(default="")

class DocumentCreate(SQLModel):
    city: str = Field(min_length=2, max_length=100)
    country: str = Field(default="Kenya", min_length=2, max_length=100)
    description: Optional[str] = Field(default=None)

class DocumentUpdate(SQLModel):
    city: Optional[str] = Field(default=None, min_length=2, max_length=100)
    country: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = Field(default=None)
"@ | Out-File -FilePath "models\document.py" -Encoding UTF8

# Fix models/user.py
Write-Host "Updating models/user.py..." -ForegroundColor Yellow
@"
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .document import Document

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, min_length=3, max_length=50)
    email: str = Field(unique=True, index=True)
    hashed_password: str = Field(default="")
    full_name: str = Field(min_length=2, max_length=100)
    role: str = Field(default="staff")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = Field(default=None)

    documents: List["Document"] = Relationship(back_populates="uploader")

class UserCreate(SQLModel):
    username: str = Field(min_length=3, max_length=50)
    email: str
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=100)
    role: str = Field(default="staff")

class UserLogin(SQLModel):
    username: str
    password: str

class UserResponse(SQLModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
"@ | Out-File -FilePath "models\user.py" -Encoding UTF8

Write-Host "`nFiles fixed!" -ForegroundColor Green
Write-Host ""
Write-Host "If you still get errors, try using Python 3.11:" -ForegroundColor Yellow
Write-Host "py -3.11 -m venv venv_311" -ForegroundColor Cyan
Write-Host ".\venv_311\Scripts\activate" -ForegroundColor Cyan
Write-Host "pip install -r requirements.txt" -ForegroundColor Cyan
Write-Host "uvicorn main:app --reload" -ForegroundColor Cyan