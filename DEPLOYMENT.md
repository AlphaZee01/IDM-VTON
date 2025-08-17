# IDM-VTON Backend Deployment Guide

This guide explains how to deploy the IDM-VTON backend for use with the uwear-virtual-shop frontend.

## 🚀 Quick Start

### Prerequisites

- **Docker** and **Docker Compose** installed
- **NVIDIA GPU** with CUDA support (recommended)
- **8GB+ RAM** (16GB+ recommended)
- **50GB+ storage** for models and data

### One-Click Deployment

#### Windows
```cmd
deploy.bat
```

#### Linux/macOS
```bash
chmod +x deploy.sh
./deploy.sh
```

## 📋 Manual Deployment Steps

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/IDM-VTON.git
cd IDM-VTON
```

### 2. Download Model Files
Download the required model files from [Hugging Face](https://huggingface.co/yisol/IDM-VTON):

```bash
# Create models directory
mkdir -p ckpt

# Download model files (you'll need to manually download these)
# - ckpt/densepose/model_final_162be9.pkl
# - ckpt/humanparsing/parsing_atr.onnx
# - ckpt/humanparsing/parsing_lip.onnx
# - ckpt/openpose/ckpts/body_pose_model.pth
# - ckpt/ip_adapter/ip-adapter-plus_sdxl_vit-h.bin
# - ckpt/image_encoder/config.json
# - ckpt/image_encoder/model.safetensors
```

### 3. Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env  # or use your preferred editor
```

### 4. Build and Deploy
```bash
# Build Docker image
docker build -t idm-vton:latest .

# Start services
docker-compose up -d
```

### 5. Verify Deployment
```bash
# Check if API is responding
curl http://localhost:8000/health

# Check service logs
docker-compose logs -f idm-vton
```

## ⚙️ Configuration

### Environment Variables

Edit `.env` file to customize the deployment:

```bash
# Application Settings
APP_NAME=IDM-VTON API
APP_VERSION=1.0.0
DEBUG=false
LOG_LEVEL=INFO

# Server Settings
HOST=0.0.0.0
PORT=8000

# GPU Settings
DEVICE=cuda
CUDA_VISIBLE_DEVICES=0

# Model Settings
MODEL_PATH=./models
CKPT_PATH=./ckpt
DATA_PATH=./data
HF_MODEL_NAME=yisol/IDM-VTON

# Performance Settings
BATCH_SIZE=1
MAX_CONCURRENT_REQUESTS=5
MAX_PROCESSING_TIME=300
MAX_MEMORY_USAGE=8192
REQUEST_TIMEOUT=300

# Redis Settings
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_URL=redis://localhost:6379/0

# Security Settings
API_KEY_HEADER=X-API-Key
ALLOWED_ORIGINS=*
RATE_LIMIT_PER_MINUTE=60

# File Upload Settings
MAX_FILE_SIZE=10485760
ALLOWED_IMAGE_FORMATS=jpg,jpeg,png
```

### Production Configuration

For production deployment, consider these settings:

```bash
# Security
DEBUG=false
ALLOWED_ORIGINS=https://your-frontend-domain.com
API_KEY_HEADER=X-API-Key
API_KEY=your-secure-api-key

# Performance
MAX_CONCURRENT_REQUESTS=10
MAX_MEMORY_USAGE=16384
MAX_PROCESSING_TIME=600

# Redis (for production)
REDIS_URL=redis://your-redis-server:6379/0
REDIS_PASSWORD=your-redis-password
```

## 🌐 Frontend Integration

### uwear-virtual-shop Configuration

In your uwear-virtual-shop project, update the environment variables:

```bash
# .env file in uwear-virtual-shop
VITE_IDM_VTON_API_URL=http://your-backend-ip:8000
VITE_IDM_VTON_API_KEY=your_api_key_here
```

### API Endpoints

The backend provides these endpoints:

- **Health Check**: `GET /health`
- **Model Status**: `GET /api/v1/status`
- **Create Try-On**: `POST /api/v1/tryon`
- **Check Status**: `GET /api/v1/tryon/{task_id}`
- **Download Result**: `GET /api/v1/tryon/{task_id}/result`
- **Metrics**: `GET /api/v1/metrics`

## 📊 Monitoring

### Health Checks
```bash
# Check API health
curl http://localhost:8000/health

# Check model status
curl http://localhost:8000/api/v1/status
```

### Metrics
```bash
# View Prometheus metrics
curl http://localhost:8000/api/v1/metrics
```

### Logs
```bash
# View service logs
docker-compose logs -f idm-vton

# View Redis logs
docker-compose logs -f redis
```

### Resource Usage
```bash
# Check Docker resource usage
docker stats

# Check disk usage
du -sh data/
```

## 🔧 Troubleshooting

### Common Issues

#### 1. GPU Not Available
```bash
# Check NVIDIA Docker
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi

# If not working, install NVIDIA Docker:
# https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
```

#### 2. Out of Memory
```bash
# Reduce batch size and concurrent requests
BATCH_SIZE=1
MAX_CONCURRENT_REQUESTS=2
MAX_MEMORY_USAGE=4096
```

#### 3. Model Loading Errors
```bash
# Check model files exist
ls -la ckpt/

# Verify model paths in .env
CKPT_PATH=./ckpt
```

#### 4. Redis Connection Issues
```bash
# Check Redis is running
docker-compose ps redis

# Restart Redis
docker-compose restart redis
```

### Performance Optimization

#### 1. Enable Caching
```bash
# Ensure Redis is running
docker-compose up -d redis

# Check cache hit rate
curl http://localhost:8000/api/v1/metrics | grep cache
```

#### 2. GPU Optimization
```bash
# Use mixed precision
DEVICE=cuda
# Models will automatically use FP16 when available
```

#### 3. Memory Management
```bash
# Monitor memory usage
docker stats idm-vton

# Clear GPU cache periodically
# This happens automatically every 5 minutes
```

## 🔒 Security Considerations

### Production Security

1. **API Key Authentication**
   ```bash
   API_KEY_HEADER=X-API-Key
   API_KEY=your-secure-api-key
   ```

2. **CORS Configuration**
   ```bash
   ALLOWED_ORIGINS=https://your-frontend-domain.com
   ```

3. **Rate Limiting**
   ```bash
   RATE_LIMIT_PER_MINUTE=60
   ```

4. **File Upload Limits**
   ```bash
   MAX_FILE_SIZE=10485760  # 10MB
   ```

### Network Security

- Use HTTPS in production
- Configure firewall rules
- Use reverse proxy (nginx/traefik)
- Enable API key authentication

## 📈 Scaling

### Horizontal Scaling

1. **Load Balancer Setup**
   ```bash
   # Run multiple instances
   docker-compose up -d --scale idm-vton=3
   ```

2. **Redis Cluster**
   ```bash
   # Use Redis cluster for high availability
   REDIS_URL=redis://redis-cluster:6379/0
   ```

3. **Shared Storage**
   ```bash
   # Use shared storage for models and cache
   # Mount NFS or cloud storage
   ```

### Performance Tuning

1. **GPU Optimization**
   - Use multiple GPUs
   - Enable TensorRT optimization
   - Use model quantization

2. **Memory Optimization**
   - Increase system RAM
   - Use SSD storage
   - Optimize batch processing

3. **Network Optimization**
   - Use CDN for static assets
   - Enable compression
   - Optimize image formats

## 🚀 Deployment Options

### Local Development
```bash
# Development mode
DEBUG=true docker-compose up
```

### Production Server
```bash
# Production deployment
./deploy.sh
```

### Cloud Deployment

#### AWS
```bash
# Use AWS ECS or EKS
# Configure auto-scaling
# Use AWS ElastiCache for Redis
```

#### Google Cloud
```bash
# Use Google Cloud Run or GKE
# Configure Cloud Memorystore for Redis
```

#### Azure
```bash
# Use Azure Container Instances or AKS
# Configure Azure Cache for Redis
```

## 📞 Support

For deployment issues:

1. Check the logs: `docker-compose logs -f`
2. Verify configuration: `cat .env`
3. Test API endpoints: `curl http://localhost:8000/health`
4. Check resource usage: `docker stats`

## 📚 Additional Resources

- [IDM-VTON Paper](https://arxiv.org/abs/2403.05139)
- [Hugging Face Model](https://huggingface.co/yisol/IDM-VTON)
- [Docker Documentation](https://docs.docker.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
