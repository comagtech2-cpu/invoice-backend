#!/bin/bash

# Render Deployment Helper Script
# This script helps prepare your Django backend for deployment

set -e

echo "🚀 Invoice SaaS - Render Deployment Preparation"
echo "=================================================="

# Check if we're in the backend directory
if [ ! -f "manage.py" ]; then
    echo "❌ Error: Please run this script from the backend directory"
    exit 1
fi

# Create .env file from template if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created. Please update it with your production values."
else
    echo "✅ .env file already exists"
fi

# Install dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Run migrations
echo ""
echo "🗄️  Running database migrations..."
python manage.py migrate

# Collect static files
echo ""
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

# Run tests
echo ""
echo "🧪 Running tests..."
python manage.py test --no-input

echo ""
echo "✅ Preparation complete!"
echo ""
echo "📋 Next steps:"
echo "1. Review and update your .env file with production values"
echo "2. Commit changes: git add . && git commit -m 'Prepare for Render deployment'"
echo "3. Push to GitHub: git push origin main"
echo "4. Go to https://dashboard.render.com and create a new Web Service"
echo "5. Connect your GitHub repository"
echo "6. Configure environment variables in Render settings"
echo "7. Monitor deployment logs"
echo ""
echo "📖 Full guide: See RENDER_DEPLOYMENT.md"
