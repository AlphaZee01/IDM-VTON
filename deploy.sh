#!/bin/bash

# IDM-VTON Backend Deployment Script
# This script deploys the IDM-VTON backend for use with uwear-virtual-shop

set -e

echo "🚀 Starting IDM-VTON Backend Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root"
   exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if NVIDIA Docker is available (for GPU support)
if ! docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi &> /dev/null; then
    print_warning "NVIDIA Docker not available. GPU acceleration will not work."
    print_warning "Install NVIDIA Docker for GPU support: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
fi

print_status "Checking prerequisites..."

# Create necessary directories
print_status "Creating directories..."
mkdir -p data/cache
mkdir -p data/results
mkdir -p logs
mkdir -p models

# Set up environment file
if [ ! -f .env ]; then
    print_status "Creating .env file from template..."
    cp .env.example .env
    print_warning "Please edit .env file with your configuration before starting the service"
else
    print_status ".env file already exists"
fi

# Check if models are available
print_status "Checking model files..."
if [ ! -d "ckpt" ] || [ -z "$(ls -A ckpt 2>/dev/null)" ]; then
    print_warning "Model files not found in ckpt/ directory"
    print_warning "Please download the required model files:"
    echo "  1. DensePose model: model_final_162be9.pkl"
    echo "  2. Human parsing models: parsing_atr.onnx, parsing_lip.onnx"
    echo "  3. OpenPose model: body_pose_model.pth"
    echo "  4. IP-Adapter: ip-adapter-plus_sdxl_vit-h.bin"
    echo "  5. Image encoder: config.json, model.safetensors"
    print_warning "You can download them from: https://huggingface.co/yisol/IDM-VTON"
fi

# Build Docker image
print_status "Building Docker image..."
docker build -t idm-vton:latest .

if [ $? -eq 0 ]; then
    print_success "Docker image built successfully"
else
    print_error "Failed to build Docker image"
    exit 1
fi

# Start services
print_status "Starting services with Docker Compose..."
docker-compose up -d

if [ $? -eq 0 ]; then
    print_success "Services started successfully"
else
    print_error "Failed to start services"
    exit 1
fi

# Wait for services to be ready
print_status "Waiting for services to be ready..."
sleep 10

# Check if the API is responding
print_status "Checking API health..."
if curl -f http://localhost:8000/health &> /dev/null; then
    print_success "API is healthy and responding"
else
    print_warning "API health check failed. The service might still be starting up."
    print_warning "You can check the logs with: docker-compose logs -f"
fi

# Display deployment information
echo ""
print_success "🎉 IDM-VTON Backend Deployment Complete!"
echo ""
echo "📋 Deployment Information:"
echo "  • API URL: http://localhost:8000"
echo "  • Health Check: http://localhost:8000/health"
echo "  • API Documentation: http://localhost:8000/docs"
echo "  • Metrics: http://localhost:8000/api/v1/metrics"
echo ""
echo "🔧 Configuration:"
echo "  • Edit .env file to customize settings"
echo "  • Check logs: docker-compose logs -f"
echo "  • Stop services: docker-compose down"
echo ""
echo "🌐 For uwear-virtual-shop integration:"
echo "  • Set VITE_IDM_VTON_API_URL=http://your-server-ip:8000"
echo "  • Set VITE_IDM_VTON_API_KEY=your_api_key (if configured)"
echo ""
echo "📊 Monitoring:"
echo "  • Resource usage: docker stats"
echo "  • API metrics: http://localhost:8000/api/v1/metrics"
echo "  • Service logs: docker-compose logs -f idm-vton"
echo ""

# Check if Redis is running
if docker-compose ps redis | grep -q "Up"; then
    print_success "Redis is running for caching and background tasks"
else
    print_warning "Redis is not running. Caching and background tasks will be limited."
fi

print_status "Deployment script completed successfully!"
