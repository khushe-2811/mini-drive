# Mini-Drive Lite

A Django 5 application that lets authenticated users upload, download, and semantically search files. Built for Windows-compatibility with SQLite and without Docker.

## Features

- Upload and download files (stored on-disk using Django's FileField)
- Automatic processing of uploaded files:
  - PDF thumbnails (first page rendered to PNG)
  - Text extraction (from PDFs and text files)
  - OpenAI embedding generation for semantic search
- Semantic search using OpenAI embeddings and cosine similarity
- Expiring share links for file sharing (valid for 12 hours)
- REST API endpoints for file upload and search
- Bootstrap 5 UI with light/dark theme support
- HTMX for progressive enhancement (upload progress, etc.)

## Setup

### Prerequisites

- Python 3.12
- Windows 10/11 (also works on Linux/Mac)
- OpenAI API key

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/mini-drive-lite.git
cd mini-drive-lite

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env to add your OpenAI API key

# Run migrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Start the development server
python manage.py runserver
```

## Environment Variables

| Variable | Example | Description |
|----------|---------|-------------|
| SECRET_KEY | django-insecure-... | Django secret key |
| DEBUG | 1 | Development mode (1=True, 0=False) |
| ALLOWED_HOSTS | localhost,127.0.0.1 | Comma-separated list of allowed hosts |
| OPENAI_API_KEY | sk-*** | Your OpenAI API key |
| MEDIA_ROOT | media | Directory for file storage |
| EMBED_MODEL | text-embedding-3-small | OpenAI embedding model |
| MAX_STORAGE_MB | 5000 | Per-user storage quota in MB |

## Usage

### Web Interface

1. **Login**: Visit `http://localhost:8000/login/` and log in with your credentials
2. **Upload**: Upload files via the Upload page
3. **View**: View your files on the Dashboard
4. **Search**: Use the semantic search to find files by content
5. **Share**: Create temporary share links that expire after 12 hours

### API Endpoints

- `POST /api/upload/` - Upload a file (multipart/form-data)
- `GET /api/search/?q=query` - Search files by content
- `GET /api/files/` - List all your files

## Background Tasks

File processing runs in the foreground (Celery is configured in eager mode, so no separate worker is needed).

## Notes

- PDF thumbnails are generated for the first page only
- Embeddings are stored in a JSON field (SQLite-compatible)
- Files are stored in the MEDIA_ROOT directory
- Storage quota is enforced per user 

## Deployment on Render.com

### Prerequisites
- A Render.com account
- Your project pushed to a Git repository (GitHub, GitLab, or Bitbucket)

### Steps to Deploy

1. **Create a New Web Service**
   - Log in to your Render.com dashboard
   - Click "New +" and select "Web Service"
   - Connect your Git repository
   - Choose the repository containing your Mini-Drive project

2. **Configure the Web Service**
   - Name: Choose a name for your service
   - Environment: Python
   - Build Command: `./build.sh`
   - Start Command: `gunicorn minidrive.wsgi:application`
   - Plan: Choose a plan that fits your needs (Free tier available for testing)

3. **Environment Variables**
   Add the following environment variables in Render's dashboard:
   ```
   SECRET_KEY=your-secret-key
   DEBUG=0
   ALLOWED_HOSTS=your-render-app-url.onrender.com
   OPENAI_API_KEY=your-openai-api-key
   MEDIA_ROOT=media
   EMBED_MODEL=text-embedding-3-small
   MAX_STORAGE_MB=5000
   DJANGO_SUPERUSER_USERNAME=testuser (change accordingly)
   DJANGO_SUPERUSER_EMAIL=testuser@example.com (change accordingly)
   DJANGO_SUPERUSER_PASSWORD=testuser123 (change accordingly)
   ```

4. **Database Configuration**
   - The project uses SQLite by default, which is suitable for small deployments
   - For production, consider using PostgreSQL:
     - Add `dj-database-url` to requirements.txt
     - Update settings.py to use PostgreSQL when DATABASE_URL is present

5. **Static and Media Files**
   - Static files are automatically collected during build
   - For media files, consider using a service like AWS S3:
     - Add `django-storages` to requirements.txt
     - Configure S3 settings in settings.py

6. **Deploy**
   - Click "Create Web Service"
   - Render will automatically build and deploy your application
   - The first deploy might take a few minutes

### Post-Deployment

1. **Create Admin User**
   - Access your deployed application
   - Run the following command in Render's shell:
     ```bash
     python manage.py createsuperuser
     ```

2. **Monitor Your Application**
   - Use Render's dashboard to monitor logs and performance
   - Set up alerts for any issues

### Important Notes

- The free tier of Render.com will spin down after 15 minutes of inactivity
- Consider upgrading to a paid plan for production use
- Regularly backup your database
- Monitor your OpenAI API usage and costs
- Keep your dependencies updated for security 