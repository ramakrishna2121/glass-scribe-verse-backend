# Glass Scribe Verse - Backend

FastAPI backend for the Glass Scribe Verse blog and community platform.

## Features

- User authentication with Clerk JWT verification
- Blog CRUD operations with search functionality
- Community management and posting
- MongoDB integration
- RESTful API endpoints

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run the development server:
```bash
uvicorn main:app --reload
```

## API Documentation

Once running, visit `http://localhost:8000/docs` for interactive API documentation.

## Project Structure

- `main.py` - FastAPI application entry point
- `app/` - Application modules
  - `routers/` - API route handlers
  - `models/` - Data models
  - `utils/` - Utility functions
  - `database.py` - Database configuration

## Docker

Build and run with Docker:
```bash
docker build -t glass-scribe-verse-backend .
docker run -p 8000:8000 glass-scribe-verse-backend
```
