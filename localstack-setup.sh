#!/bin/bash
# Lateos LocalStack Setup Script
# Run this script to configure LocalStack credentials and start services

set -e

echo "🚀 Lateos LocalStack Setup"
echo "=========================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

echo "✅ Docker is running"

# Create .env.local from .env.example if it doesn't exist
if [ ! -f .env.local ]; then
    echo "📝 Creating .env.local from .env.example..."
    cp .env.example .env.local
    echo "✅ .env.local created"
else
    echo "✅ .env.local already exists"
fi

# Configure AWS CLI profile for LocalStack
echo "🔧 Configuring AWS CLI profile for LocalStack..."

# Create .aws directory if it doesn't exist
mkdir -p ~/.aws

# Check if localstack profile already exists
if ! grep -q "\[profile localstack\]" ~/.aws/config 2>/dev/null; then
    echo "" >> ~/.aws/config
    echo "[profile localstack]" >> ~/.aws/config
    echo "region = us-east-1" >> ~/.aws/config
    echo "output = json" >> ~/.aws/config
    echo "✅ Added localstack profile to ~/.aws/config"
else
    echo "✅ localstack profile already exists in ~/.aws/config"
fi

# Configure credentials
if ! grep -q "\[localstack\]" ~/.aws/credentials 2>/dev/null; then
    echo "" >> ~/.aws/credentials
    echo "[localstack]" >> ~/.aws/credentials
    echo "aws_access_key_id = test" >> ~/.aws/credentials
    echo "aws_secret_access_key = test" >> ~/.aws/credentials
    echo "✅ Added localstack credentials to ~/.aws/credentials"
else
    echo "✅ localstack credentials already exist in ~/.aws/credentials"
fi

# Start LocalStack
echo "🐳 Starting LocalStack..."
docker-compose up -d

# Wait for LocalStack to be ready
echo "⏳ Waiting for LocalStack to be ready..."
timeout 30 bash -c 'until curl -s http://localhost:4566/_localstack/health | grep -q "\"dynamodb\": \"available\""; do sleep 1; done' || {
    echo "⚠️  LocalStack may not be fully ready yet. Check logs with: docker-compose logs -f"
}

echo ""
echo "✅ LocalStack Setup Complete!"
echo ""
echo "📋 Next Steps:"
echo "   1. Verify LocalStack is running: curl http://localhost:4566/_localstack/health"
echo "   2. Test AWS CLI: aws --profile localstack --endpoint-url=http://localhost:4566 s3 ls"
echo "   3. View logs: docker-compose logs -f localstack"
echo "   4. Stop LocalStack: docker-compose down"
echo ""
echo "🔗 LocalStack Dashboard: http://localhost:4566/_localstack/init"
