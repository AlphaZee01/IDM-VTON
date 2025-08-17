#!/bin/bash

# IDM-VTON Render Deployment Script
# This script prepares the repository for deployment on Render

set -e

echo "🚀 Preparing IDM-VTON for Render Deployment..."

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

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    print_error "Please run this script from the IDM-VTON root directory"
    exit 1
fi

print_status "Checking prerequisites..."

# Check if render.yaml exists
if [ ! -f "render.yaml" ]; then
    print_error "render.yaml not found. Please ensure it exists in the root directory."
    exit 1
fi

# Check if requirements-render.txt exists
if [ ! -f "requirements-render.txt" ]; then
    print_error "requirements-render.txt not found. Please ensure it exists in the root directory."
    exit 1
fi

print_success "Prerequisites check passed"

# Create necessary directories
print_status "Creating directories..."
mkdir -p data/cache
mkdir -p data/results
mkdir -p logs
mkdir -p models

# Check if .gitignore includes necessary entries
print_status "Checking .gitignore..."
if [ ! -f ".gitignore" ]; then
    print_warning ".gitignore not found. Creating one..."
    cat > .gitignore << EOF
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# Environment variables
.env
.env.local
.env.production

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
logs/
*.log

# Data (keep structure but ignore content)
data/cache/*
data/results/*
!data/cache/.gitkeep
!data/results/.gitkeep

# Models (optional - uncomment if you don't want to track model files)
# ckpt/

# Temporary files
*.tmp
*.temp
EOF
    print_success ".gitignore created"
else
    print_success ".gitignore exists"
fi

# Create .gitkeep files for empty directories
print_status "Creating .gitkeep files..."
touch data/cache/.gitkeep
touch data/results/.gitkeep
touch logs/.gitkeep
touch models/.gitkeep

# Check model files
print_status "Checking model files..."
if [ ! -d "ckpt" ] || [ -z "$(ls -A ckpt 2>/dev/null)" ]; then
    print_warning "Model files not found in ckpt/ directory"
    print_warning "You have several options for model files:"
    echo ""
    echo "1. **Git LFS (Recommended for small teams):"
    echo "   git lfs install"
    echo "   git lfs track 'ckpt/**/*'"
    echo "   git add .gitattributes"
    echo "   # Then download and add model files"
    echo ""
    echo "2. **External Storage (Recommended for production):"
    echo "   - Upload model files to cloud storage (AWS S3, Google Cloud, etc.)"
    echo "   - Update the model loading code to download from URLs"
    echo ""
    echo "3. **Build-time Download:"
    echo "   - Add download commands to render.yaml buildCommand"
    echo ""
    echo "Required model files:"
    echo "  - ckpt/densepose/model_final_162be9.pkl"
    echo "  - ckpt/humanparsing/parsing_atr.onnx"
    echo "  - ckpt/humanparsing/parsing_lip.onnx"
    echo "  - ckpt/openpose/ckpts/body_pose_model.pth"
    echo "  - ckpt/ip_adapter/ip-adapter-plus_sdxl_vit-h.bin"
    echo "  - ckpt/image_encoder/config.json"
    echo "  - ckpt/image_encoder/model.safetensors"
    echo ""
    echo "Download from: https://huggingface.co/yisol/IDM-VTON"
else
    print_success "Model files found in ckpt/ directory"
fi

# Create a simple health check test
print_status "Creating health check test..."
cat > test_health.py << EOF
#!/usr/bin/env python3
"""
Simple health check test for Render deployment
"""
import requests
import sys
import time

def test_health_check(url):
    """Test the health check endpoint"""
    try:
        response = requests.get(f"{url}/health", timeout=10)
        if response.status_code == 200:
            print(f"✅ Health check passed: {response.json()}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_api_status(url):
    """Test the API status endpoint"""
    try:
        response = requests.get(f"{url}/api/v1/status", timeout=10)
        if response.status_code == 200:
            print(f"✅ API status check passed: {response.json()}")
            return True
        else:
            print(f"❌ API status check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API status check error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_health.py <your-render-url>")
        print("Example: python test_health.py https://your-app.onrender.com")
        sys.exit(1)
    
    url = sys.argv[1].rstrip('/')
    print(f"Testing deployment at: {url}")
    
    # Wait a bit for the service to be ready
    print("Waiting for service to be ready...")
    time.sleep(5)
    
    health_ok = test_health_check(url)
    status_ok = test_api_status(url)
    
    if health_ok and status_ok:
        print("🎉 All tests passed! Your deployment is working correctly.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Check your deployment logs.")
        sys.exit(1)
EOF

chmod +x test_health.py
print_success "Health check test created"

# Create deployment checklist
print_status "Creating deployment checklist..."
cat > RENDER_CHECKLIST.md << EOF
# Render Deployment Checklist

## Pre-Deployment
- [ ] Repository is connected to Render
- [ ] render.yaml is configured correctly
- [ ] requirements-render.txt is ready
- [ ] Model files are available (see options below)
- [ ] Environment variables are configured in Render dashboard

## Model Files Options
- [ ] **Option 1**: Git LFS (for small teams)
  - [ ] git lfs install
  - [ ] git lfs track 'ckpt/**/*'
  - [ ] git add .gitattributes
  - [ ] Download and add model files
  - [ ] git add ckpt/
  - [ ] git commit -m "Add model files via Git LFS"
  - [ ] git push

- [ ] **Option 2**: External Storage (recommended for production)
  - [ ] Upload model files to cloud storage
  - [ ] Update model loading code to download from URLs
  - [ ] Set MODEL_DOWNLOAD_URL environment variable

- [ ] **Option 3**: Build-time Download
  - [ ] Add download commands to render.yaml buildCommand
  - [ ] Test build process

## Post-Deployment
- [ ] Health check passes: \`python test_health.py https://your-app.onrender.com\`
- [ ] API status endpoint responds correctly
- [ ] Redis service is connected
- [ ] Persistent disk is mounted correctly
- [ ] Logs are accessible in Render dashboard
- [ ] Frontend can connect to the API
- [ ] CORS is configured for frontend domain

## Environment Variables to Set in Render
\`\`\`bash
# Application Settings
PYTHON_VERSION=3.10.0
PORT=8000
HOST=0.0.0.0
DEBUG=false
LOG_LEVEL=INFO

# GPU Settings (CPU-only on Render)
DEVICE=cpu
CUDA_VISIBLE_DEVICES=""

# Model Paths
MODEL_PATH=/opt/render/project/src/models
CKPT_PATH=/opt/render/project/src/ckpt
DATA_PATH=/opt/render/project/src/data
HF_MODEL_NAME=yisol/IDM-VTON

# Performance Settings (Optimized for Render)
BATCH_SIZE=1
MAX_CONCURRENT_REQUESTS=3
MAX_PROCESSING_TIME=300
MAX_MEMORY_USAGE=4096
REQUEST_TIMEOUT=300

# Redis Settings (from your Redis service)
REDIS_URL=redis://your-redis-service-url:6379/0

# Security Settings
API_KEY_HEADER=X-API-Key
ALLOWED_ORIGINS=*
RATE_LIMIT_PER_MINUTE=30

# File Upload Settings
MAX_FILE_SIZE=10485760
ALLOWED_IMAGE_FORMATS=jpg,jpeg,png

# Logging Settings
LOG_FORMAT=json
ENABLE_METRICS=true
METRICS_PORT=9090
\`\`\`

## Testing Commands
\`\`\`bash
# Test health check
curl https://your-app.onrender.com/health

# Test API status
curl https://your-app.onrender.com/api/v1/status

# Test with Python script
python test_health.py https://your-app.onrender.com
\`\`\`

## Troubleshooting
- Check Render dashboard logs
- Verify environment variables are set correctly
- Ensure model files are accessible
- Check Redis connection
- Monitor memory usage
EOF

print_success "Deployment checklist created"

# Display next steps
echo ""
print_success "🎉 IDM-VTON is ready for Render deployment!"
echo ""
echo "📋 Next Steps:"
echo "1. Push your code to GitHub:"
echo "   git add ."
echo "   git commit -m 'Prepare for Render deployment'"
echo "   git push"
echo ""
echo "2. Deploy on Render:"
echo "   - Go to render.com"
echo "   - Click 'New +' → 'Blueprint'"
echo "   - Connect your GitHub repository"
echo "   - Click 'Apply' to deploy"
echo ""
echo "3. Configure environment variables in Render dashboard"
echo ""
echo "4. Test your deployment:"
echo "   python test_health.py https://your-app.onrender.com"
echo ""
echo "📚 Documentation:"
echo "   - RENDER_DEPLOYMENT.md - Complete deployment guide"
echo "   - RENDER_CHECKLIST.md - Step-by-step checklist"
echo "   - render.yaml - Render configuration"
echo "   - requirements-render.txt - CPU-optimized dependencies"
echo ""
print_status "Deployment preparation completed successfully!"
