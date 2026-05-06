@echo off
REM Render Deployment Helper Script for Windows
REM This script helps prepare your Django backend for deployment

setlocal enabledelayedexpansion

echo.
echo 🚀 Invoice SaaS - Render Deployment Preparation
echo ==================================================

REM Check if we're in the backend directory
if not exist "manage.py" (
    echo ❌ Error: Please run this script from the backend directory
    exit /b 1
)

REM Create .env file from template if it doesn't exist
if not exist ".env" (
    echo 📝 Creating .env file from template...
    copy .env.example .env
    echo ✅ .env file created. Please update it with your production values.
) else (
    echo ✅ .env file already exists
)

REM Install dependencies
echo.
echo 📦 Installing Python dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

REM Run migrations
echo.
echo 🗄️  Running database migrations...
python manage.py migrate

REM Collect static files
echo.
echo 📁 Collecting static files...
python manage.py collectstatic --noinput

REM Run tests
echo.
echo 🧪 Running tests...
python manage.py test --no-input

echo.
echo ✅ Preparation complete!
echo.
echo 📋 Next steps:
echo 1. Review and update your .env file with production values
echo 2. Commit changes: git add . ^& git commit -m "Prepare for Render deployment"
echo 3. Push to GitHub: git push origin main
echo 4. Go to https://dashboard.render.com and create a new Web Service
echo 5. Connect your GitHub repository
echo 6. Configure environment variables in Render settings
echo 7. Monitor deployment logs
echo.
echo 📖 Full guide: See RENDER_DEPLOYMENT.md
echo.
pause
