SendIt API - Document Management & Enrichment System
📌 Overview

SendIt API is a document management and enrichment system for a Nyeri courier company. It digitizes document handling with features like:

- ✅ Document upload with validation (PDF, JPG, PNG, DOCX)
- 🌤️ Automatic weather data enrichment (Open-Meteo API)
- 🔐 Role-based access control (Admin, Manager, Staff)
- 📡 Webhook notifications for document events
- 📝 Document versioning and tracking
- 🔍 Advanced search with multiple filters

---
 🚀 Quick Start

Prerequisites
- Python 3.11+
- Docker & Docker Compose

Installation

```bash
Clone the repository
git clone https://github.com/yourusername/sendit-api.git
cd sendit-api

Start PostgreSQL
docker-compose up -d

Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

Install dependencies
pip install -r requirements.txt

Create .env file
cp .env.example .env

Run the application
uvicorn main:app --reload
