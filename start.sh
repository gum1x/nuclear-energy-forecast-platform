

echo "🚀 Starting Nuclear Forecast Enterprise Setup..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your API keys before continuing."
    echo "   Required API keys: EIA_API_KEY, NERC_API_KEY, WORLDBANK_API_KEY"
    read -p "Press Enter after updating .env file..."
fi

echo "🔨 Building Docker images..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

echo "⏳ Waiting for services to start..."
sleep 30

echo "🔍 Checking service health..."

if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API service is healthy"
else
    echo "❌ API service is not responding"
fi

if docker-compose exec -T db pg_isready -U nuclear_user > /dev/null 2>&1; then
    echo "✅ Database is ready"
else
    echo "❌ Database is not ready"
fi

if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is ready"
else
    echo "❌ Redis is not ready"
fi

echo ""
echo "🎉 Nuclear Forecast Enterprise is now running!"
echo ""
echo "📊 Access Points:"
echo "   • API Documentation: http://localhost:8000/docs"
echo "   • Dashboard: http://localhost:8050"
echo "   • Health Check: http://localhost:8000/health"
echo "   • Metrics: http://localhost:8000/metrics"
echo ""
echo "🔧 Management Commands:"
echo "   • View logs: docker-compose logs -f"
echo "   • Stop services: docker-compose down"
echo "   • Restart services: docker-compose restart"
echo "   • Scale workers: docker-compose up -d --scale worker=3"
echo ""
echo "📚 Documentation: See README.md for detailed usage instructions"
