#!/bin/bash

# Sage - AI Executive Assistant Setup Script
# This script sets up the development environment

set -e

echo "========================================"
echo "  Sage - AI Executive Assistant Setup"
echo "========================================"
echo ""

# Check for required tools
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo "Error: $1 is required but not installed."
        exit 1
    fi
}

echo "Checking required tools..."
check_command docker
check_command docker-compose
echo "All required tools are installed."
echo ""

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env

    # Generate secrets
    SECRET_KEY=$(openssl rand -hex 32)
    NEXTAUTH_SECRET=$(openssl rand -hex 32)

    # Update .env with generated secrets
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/your-secret-key-here-generate-with-openssl-rand-hex-32/$SECRET_KEY/" .env
        sed -i '' "s/your-nextauth-secret-generate-with-openssl-rand-hex-32/$NEXTAUTH_SECRET/" .env
    else
        # Linux
        sed -i "s/your-secret-key-here-generate-with-openssl-rand-hex-32/$SECRET_KEY/" .env
        sed -i "s/your-nextauth-secret-generate-with-openssl-rand-hex-32/$NEXTAUTH_SECRET/" .env
    fi

    echo ".env file created with generated secrets."
    echo ""
    echo "IMPORTANT: Please edit .env and add your API keys:"
    echo "  - ANTHROPIC_API_KEY"
    echo "  - GOOGLE_CLIENT_ID"
    echo "  - GOOGLE_CLIENT_SECRET"
    echo "  - FIREFLIES_API_KEY (optional)"
    echo "  - ALPHA_VANTAGE_API_KEY (optional)"
    echo ""
else
    echo ".env file already exists."
fi

# Create credentials directory for Google OAuth
echo "Creating credentials directory..."
mkdir -p credentials

# Build and start services
echo ""
echo "Building Docker containers..."
docker-compose build

echo ""
echo "Starting services..."
docker-compose up -d postgres redis qdrant

# Wait for PostgreSQL to be ready
echo ""
echo "Waiting for PostgreSQL to be ready..."
sleep 5

# Run database migrations
echo ""
echo "Running database migrations..."
docker-compose run --rm backend alembic upgrade head

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "To start the full application:"
echo "  make dev"
echo ""
echo "Or start individual services:"
echo "  docker-compose up -d"
echo ""
echo "Access the application:"
echo "  Frontend: http://localhost:3000"
echo "  Backend API: http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "Don't forget to configure Google OAuth:"
echo "  1. Go to Google Cloud Console"
echo "  2. Create OAuth 2.0 credentials"
echo "  3. Add http://localhost:8000/api/v1/auth/google/callback as redirect URI"
echo "  4. Update GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env"
echo ""
