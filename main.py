from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, status, Request, Form
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select, SQLModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from datetime import datetime
import os
import aiofiles
import json
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from database.session import get_session, engine
from models.user import User, UserCreate, UserResponse
from models.document import Document, DocumentCreate, DocumentUpdate
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_current_admin, get_current_manager
)
from services.weather import get_weather

# Create tables
SQLModel.metadata.create_all(engine)

app = FastAPI(title="SendIt API", version="1.0.0")

# CONFIGURATION
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", 5 * 1024 * 1024))
ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".docx"]

# RATE LIMITING
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ============================================================
# 1. AUTHENTICATION ENDPOINTS
# ============================================================
@app.post("/register", tags=["Authentication"])
@limiter.limit("5/minute")
async def register(
    request: Request,
    user_data: UserCreate,
    session: Session = Depends(get_session)
):
    """Register a new user."""
    # ======================================================
    # PASSWORD VALIDATION - FIX FOR BCRYPT 72-BYTE LIMIT
    # ======================================================
    
    # Check password length in bytes (for UTF-8)
    password_bytes = user_data.password.encode('utf-8')
    if len(password_bytes) > 72:
        raise HTTPException(
            status_code=400,
            detail="Password is too long for bcrypt. Maximum 72 bytes (about 72 characters)."
        )
    
    # Check minimum length
    if len(user_data.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters"
        )
    
    # Check if username exists
    existing_user = session.exec(
        select(User).where(User.username == user_data.username)
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Check if email exists
    existing_email = session.exec(
        select(User).where(User.email == user_data.email)
    ).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return {
        "message": "User registered successfully",
        "user": UserResponse.model_validate(user)
    }

@app.post("/login", tags=["Authentication"])
@limiter.limit("5/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session)
):
    """Login and get access token."""
    user = session.exec(
        select(User).where(User.username == form_data.username)
    ).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")
    
    # Update last login
    user.last_login = datetime.utcnow()
    session.commit()
    
    access_token = create_access_token({"sub": user.username, "role": user.role})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user)
    }

# ============================================================
# 2. DOCUMENT UPLOAD ENDPOINT
# ============================================================

@app.post("/documents/upload", tags=["Documents"])
@limiter.limit("10/hour")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    city: str = Form(...),
    description: Optional[str] = Form(None),
    country: str = Form("Kenya"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Upload a document with validation. Enriches with weather data."""
    
    # 1. Validate file extension
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # 2. Read and validate file size
    contents = await file.read()
    file_size = len(contents)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {MAX_FILE_SIZE // (1024 * 1024)} MB"
        )
    
    # 3. Generate safe filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{current_user.id}_{file.filename.replace(' ', '_')}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    # 4. Save file asynchronously
    async with aiofiles.open(file_path, 'wb') as out_file:
        await out_file.write(contents)
    
    # 5. Create document record
    document = Document(
        filename=safe_filename,
        original_filename=file.filename,
        file_size=file_size,
        file_type=file.content_type or "application/octet-stream",
        city=city,
        country=country,
        description=description,
        uploader_id=current_user.id,
        file_path=file_path,
        status="processing"
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    
    # 6. Enrich with weather data (external API call)
    try:
        weather_data = await get_weather(city, country)
        if weather_data and "error" not in weather_data:
            document.weather_data = json.dumps(weather_data)
            document.weather_fetched_at = datetime.utcnow()
            document.status = "enriched"
            session.commit()
    except Exception as e:
        print(f"Weather API error: {e}")
        document.status = "uploaded"
        session.commit()
    
    return {
        "message": "Document uploaded successfully",
        "document_id": document.id,
        "filename": document.original_filename,
        "status": document.status
    }

# ============================================================
# 3. DOCUMENT LISTING ENDPOINTS
# ============================================================

@app.get("/documents", tags=["Documents"])
@limiter.limit("30/minute")
def list_documents(
    request: Request,
    status: Optional[str] = None,
    city: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """List all documents with optional filters."""
    query = select(Document)
    
    # Managers and admins see all; staff see only their own
    if current_user.role not in ["admin", "manager"]:
        query = query.where(Document.uploader_id == current_user.id)
    
    if status:
        query = query.where(Document.status == status)
    if city:
        query = query.where(Document.city == city)
    
    documents = session.exec(query).all()
    return documents

@app.get("/documents/{document_id}", tags=["Documents"])
@limiter.limit("30/minute")
def get_document(
    request: Request,
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get a specific document."""
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Staff can only view their own documents
    if current_user.role not in ["admin", "manager"] and document.uploader_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return document

@app.patch("/documents/{document_id}", tags=["Documents"])
@limiter.limit("30/minute")
def update_document(
    request: Request,
    document_id: int,
    document_update: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Update document metadata."""
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Staff can only update their own documents
    if current_user.role not in ["admin", "manager"] and document.uploader_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Update fields if provided
    if document_update.city is not None:
        document.city = document_update.city
    if document_update.country is not None:
        document.country = document_update.country
    if document_update.description is not None:
        document.description = document_update.description
    
    document.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(document)
    
    return document

@app.delete("/documents/{document_id}", tags=["Documents"])
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_manager),
    session: Session = Depends(get_session)
):
    """Delete a document (managers and admins only)."""
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete physical file
    if os.path.exists(document.file_path):
        os.remove(document.file_path)
    
    session.delete(document)
    session.commit()
    return {"message": "Document deleted successfully"}

# ============================================================
# 4. DOCUMENT ENRICHMENT ENDPOINTS
# ============================================================

@app.post("/documents/{document_id}/enrich", tags=["Documents"])
@limiter.limit("5/minute")
async def enrich_document(
    request: Request,
    document_id: int,
    current_user: User = Depends(get_current_manager),
    session: Session = Depends(get_session)
):
    """Manually trigger weather enrichment for a document."""
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status == "enriched":
        return {"message": "Document already enriched"}
    
    weather_data = await get_weather(document.city, document.country)
    if weather_data and "error" not in weather_data:
        document.weather_data = json.dumps(weather_data)
        document.weather_fetched_at = datetime.utcnow()
        document.status = "enriched"
        session.commit()
        return {
            "message": "Document enriched successfully",
            "weather": weather_data
        }
    else:
        document.status = "failed"
        session.commit()
        raise HTTPException(status_code=500, detail="Failed to enrich document with weather data")

@app.get("/documents/{document_id}/weather", tags=["Documents"])
@limiter.limit("10/minute")
def get_document_weather(
    request: Request,
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get the weather data associated with a document."""
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Staff can only view their own documents
    if current_user.role not in ["admin", "manager"] and document.uploader_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not document.weather_data:
        raise HTTPException(status_code=404, detail="No weather data available for this document")
    
    return {
        "document_id": document.id,
        "city": document.city,
        "country": document.country,
        "weather": json.loads(document.weather_data)
    }

# ============================================================
# 5. EXERCISE 1: SEARCH ENDPOINT
# ============================================================

@app.get("/documents/search", tags=["Documents"])
@limiter.limit("20/minute")
def search_documents(
    request: Request,
    q: Optional[str] = None,
    city: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Search documents with multiple filters."""
    query = select(Document)
    
    # Staff see only their own documents
    if current_user.role not in ["admin", "manager"]:
        query = query.where(Document.uploader_id == current_user.id)
    
    # Apply filters
    if q:
        query = query.where(
            (Document.original_filename.contains(q)) |
            (Document.description.contains(q)) |
            (Document.city.contains(q))
        )
    if city:
        query = query.where(Document.city == city)
    if status:
        query = query.where(Document.status == status)
    if date_from:
        query = query.where(Document.uploaded_at >= date_from)
    if date_to:
        query = query.where(Document.uploaded_at <= date_to)
    
    # Order by most recent first
    query = query.order_by(Document.uploaded_at.desc())
    
    documents = session.exec(query).all()
    return documents

# ============================================================
# 6. EXERCISE 2: DOCUMENT VERSIONING
# ============================================================

@app.post("/documents/{document_id}/versions", tags=["Documents"])
@limiter.limit("10/hour")
async def create_version(
    request: Request,
    document_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Create a new version of an existing document."""
    original_doc = session.get(Document, document_id)
    if not original_doc:
        raise HTTPException(status_code=404, detail="Original document not found")
    
    # Check permission
    if current_user.role not in ["admin", "manager"] and original_doc.uploader_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Validate file
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File type not allowed")
    
    contents = await file.read()
    file_size = len(contents)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")
    
    # Create new version
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{current_user.id}_v{getattr(original_doc, 'version', 1) + 1}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    async with aiofiles.open(file_path, 'wb') as out_file:
        await out_file.write(contents)
    
    # Create new document record
    version = Document(
        filename=safe_filename,
        original_filename=file.filename,
        file_size=file_size,
        file_type=file.content_type or "application/octet-stream",
        city=original_doc.city,
        country=original_doc.country,
        description=original_doc.description,
        uploader_id=current_user.id,
        file_path=file_path,
        status="uploaded",
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    
    return {
        "message": "New version created",
        "version_id": version.id,
        "version_number": getattr(original_doc, 'version', 1) + 1
    }

# ============================================================
# 7. EXERCISE 3: WEBHOOK ENDPOINTS
# ============================================================

# Webhook storage (in-memory for demo)
webhooks = []

@app.post("/webhooks/register", tags=["Webhooks"])
def register_webhook(
    request: Request,
    webhook_data: dict,  # Changed from individual parameters
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Register a webhook for document events (admin only)."""
    
    # Extract values from dictionary
    webhook_url = webhook_data.get("webhook_url")
    event_type = webhook_data.get("event_type")
    
    # Validate required fields
    if not webhook_url:
        raise HTTPException(status_code=400, detail="webhook_url is required")
    
    if not event_type:
        raise HTTPException(status_code=400, detail="event_type is required")
    
    # Validate event type (case insensitive)
    allowed_events = ["document.enriched", "document.uploaded"]
    if event_type not in allowed_events:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid event type. Must be 'document.enriched' or 'document.uploaded'"
        )
    
    # Create webhook
    webhook = {
        "id": len(webhooks) + 1,
        "url": webhook_url,
        "event_type": event_type,
        "registered_by": current_user.id,
        "registered_at": datetime.utcnow().isoformat()
    }
    webhooks.append(webhook)
    
    return {
        "message": "Webhook registered successfully",
        "webhook": webhook
    }
@app.get("/webhooks", tags=["Webhooks"])
def list_webhooks(
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """List all registered webhooks (admin only)."""
    return {"webhooks": webhooks}

@app.delete("/webhooks/{webhook_id}", tags=["Webhooks"])
def delete_webhook(
    webhook_id: int,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Delete a webhook by ID (admin only)."""
    for i, webhook in enumerate(webhooks):
        if webhook["id"] == webhook_id:
            deleted = webhooks.pop(i)
            return {"message": "Webhook deleted successfully", "webhook": deleted}
    
    raise HTTPException(status_code=404, detail="Webhook not found")

# ============================================================
# 8. USER MANAGEMENT ENDPOINTS
# ============================================================

@app.get("/users/me", tags=["Users"])
def get_current_user_info(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get current user information."""
    return UserResponse.model_validate(current_user)

@app.get("/users", tags=["Users"])
def list_users(
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """List all users (admin only)."""
    users = session.exec(select(User)).all()
    return [UserResponse.model_validate(user) for user in users]

@app.get("/users/{user_id}", tags=["Users"])
def get_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get a specific user (admin only)."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)

# ============================================================
# 9. ROOT & HEALTH ENDPOINTS
# ============================================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information."""
    return {
        "message": "SendIt API is running!",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health", tags=["Root"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

# ============================================================
# 10. RUN THE APP
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)