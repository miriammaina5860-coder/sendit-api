# fix_fastapi.ps1
Write-Host "Fixing FastAPI/Pydantic compatibility..." -ForegroundColor Green

# Uninstall problematic packages
Write-Host "Uninstalling old packages..." -ForegroundColor Yellow
pip uninstall fastapi uvicorn pydantic sqlmodel -y

# Install latest versions
Write-Host "Installing latest compatible versions..." -ForegroundColor Yellow
pip install fastapi>=0.115.0
pip install uvicorn[standard]>=0.30.0
pip install sqlmodel>=0.0.22
pip install pydantic>=2.9.0

# Install rest of dependencies
pip install python-dotenv passlib bcrypt python-jose python-multipart aiofiles httpx slowapi

# Verify installations
Write-Host "`nInstalled versions:" -ForegroundColor Green
pip show fastapi | findstr Version
pip show uvicorn | findstr Version
pip show pydantic | findstr Version
pip show sqlmodel | findstr Version

Write-Host "`nNow try running: uvicorn main:app --reload" -ForegroundColor Cyan