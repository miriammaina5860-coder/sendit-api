# install_correct.ps1
Write-Host "Installing correct package versions..." -ForegroundColor Green

# Fix PATH if needed
$env:Path += ";C:\Users\hp\AppData\Local\Python\pythoncore-3.14-64\Scripts"

# Install packages with correct versions
pip install pydantic==2.10.3 pydantic-core==2.27.1 fastapi==0.115.5 uvicorn[standard]==0.34.0 sqlmodel==0.0.22 psycopg2-binary python-dotenv passlib bcrypt python-jose python-multipart aiofiles httpx slowapi

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nTrying without version pins..." -ForegroundColor Yellow
    pip install pydantic fastapi uvicorn[standard] sqlmodel psycopg2-binary python-dotenv passlib bcrypt python-jose python-multipart aiofiles httpx slowapi
}

Write-Host "`nVerifying installation..." -ForegroundColor Green
pip list | Select-String -Pattern "pydantic|fastapi|uvicorn"

Write-Host "`nReady! Run: uvicorn main:app --reload" -ForegroundColor Cyan