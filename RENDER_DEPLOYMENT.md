# IDM-VTON Backend Deployment on Render

This guide explains how to deploy the IDM-VTON backend on Render for use with the uwear-virtual-shop frontend.

## 🚀 Quick Deployment

### Prerequisites

- **Render Account**: Sign up at [render.com](https://render.com)
- **GitHub Repository**: Your IDM-VTON backend code
- **Model Files**: Downloaded from Hugging Face

### One-Click Deployment

1. **Fork/Clone the Repository**
   ```bash
   git clone https://github.com/your-username/IDM-VTON.git
   cd IDM-VTON
   ```

2. **Connect to Render**
   - Go to [render.com](https://render.com)
   - Click "New +" → "Blueprint"
   - Connect your GitHub repository
   - Select the repository with your IDM-VTON backend

3. **Deploy with Blueprint**
   - Render will automatically detect the `render.yaml` file
   - Click "Apply" to deploy both the API and Redis services

## 📋 Manual Deployment Steps

### 1. Create Web Service

1. **Go to Render Dashboard**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository

2. **Configure Service**
   ```
   Name: idm-vton-api
   Environment: Python
   Region: Choose closest to your users
   Branch: main (or your default branch)
   Root Directory: ./
   ```

3. **Build & Deploy Settings**
   ```
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn api.main:app --host 0.0.0.0 --port $PORT --workers 1
   ```

### 2. Create Redis Service

1. **Create Redis Instance**
   - Click "New +" → "Redis"
   - Name: `idm-vton-redis`
   - Plan: Starter (free tier)

2. **Configure Redis**
   ```
   Name: idm-vton-redis
   Plan: Starter
   Region: Same as your web service
   ```

### 3. Configure Environment Variables

In your web service settings, add these environment variables:

```bash
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

# Model Configuration
IMAGE_WIDTH=768
IMAGE_HEIGHT=1024
NUM_INFERENCE_STEPS=30
GUIDANCE_SCALE=2.0

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

# Optional: API Key for authentication
# API_KEY=your-secret-api-key-here
```

### 4. Add Persistent Disk

1. **Create Disk**
   - In your web service settings
   - Go to "Disks" tab
   - Click "Add Disk"
   - Name: `idm-vton-data`
   - Size: 10GB
   - Mount Path: `/opt/render/project/src/data`

### 5. Configure Health Check

```
Health Check Path: /health
```

## 🔧 Render-Specific Configuration

### CPU-Only Optimization

Since Render doesn't support GPU in the starter plan, we've optimized for CPU:

```python
# In your config.py or environment variables
DEVICE=cpu
CUDA_VISIBLE_DEVICES=""

# Reduced model parameters for CPU
NUM_INFERENCE_STEPS=20  # Reduced from 30
MAX_CONCURRENT_REQUESTS=3  # Reduced from 5
MAX_MEMORY_USAGE=4096  # Reduced from 8192
```

### Memory Management

Render has memory limits, so we've optimized:

```bash
# Environment variables for Render
MAX_MEMORY_USAGE=4096  # 4GB limit
MAX_CONCURRENT_REQUESTS=3  # Conservative limit
BATCH_SIZE=1  # Single batch processing
```

### Redis Configuration

```bash
# Redis connection from Render service
REDIS_URL=redis://your-redis-service-url:6379/0

# Redis settings in render.yaml
maxmemoryPolicy: allkeys-lru
```

## 📁 Model File Management

### Option 1: Git LFS (Recommended)

1. **Install Git LFS**
   ```bash
   git lfs install
   git lfs track "ckpt/**/*"
   git add .gitattributes
   ```

2. **Add Model Files**
   ```bash
   git add ckpt/
   git commit -m "Add model files via Git LFS"
   git push
   ```

### Option 2: External Storage

1. **Upload to Cloud Storage**
   - Upload model files to AWS S3, Google Cloud Storage, or similar
   - Update the model loading code to download from URLs

2. **Environment Variables**
   ```bash
   MODEL_DOWNLOAD_URL=https://your-storage-url.com/models/
   ```

### Option 3: Build-time Download

Add to your `render.yaml`:

```yaml
buildCommand: |
  pip install -r requirements.txt
  mkdir -p data/cache data/results logs models ckpt
  # Download model files during build
  curl -L https://huggingface.co/yisol/IDM-VTON/resolve/main/ckpt/densepose/model_final_162be9.pkl -o ckpt/densepose/model_final_162be9.pkl
  # Add more model downloads as needed
```

## 🌐 Frontend Integration

### Update uwear-virtual-shop Configuration

In your uwear-virtual-shop project, update the environment variables:

```bash
# .env file in uwear-virtual-shop
VITE_IDM_VTON_API_URL=https://your-render-app.onrender.com
VITE_IDM_VTON_API_KEY=your_api_key_here
```

### CORS Configuration

Make sure your Render service allows your frontend domain:

```bash
# Environment variable in Render
ALLOWED_ORIGINS=https://your-frontend-domain.com,http://localhost:3000
```

## 📊 Monitoring and Logs

### View Logs

1. **In Render Dashboard**
   - Go to your web service
   - Click "Logs" tab
   - View real-time logs

2. **API Health Check**
   ```bash
   curl https://your-render-app.onrender.com/health
   ```

3. **Metrics Endpoint**
   ```bash
   curl https://your-render-app.onrender.com/api/v1/metrics
   ```

### Performance Monitoring

- **Render Dashboard**: Monitor CPU, memory, and disk usage
- **Application Metrics**: Use the `/api/v1/metrics` endpoint
- **Health Checks**: Monitor `/health` endpoint

## 🔧 Troubleshooting

### Common Issues

#### 1. Build Failures
```bash
# Check build logs in Render dashboard
# Common issues:
# - Missing dependencies in requirements.txt
# - Python version mismatch
# - Memory limits during build
```

#### 2. Runtime Errors
```bash
# Check application logs
# Common issues:
# - Model files not found
# - Redis connection issues
# - Memory limits exceeded
```

#### 3. Performance Issues
```bash
# Optimize for Render constraints:
# - Reduce MAX_CONCURRENT_REQUESTS
# - Reduce NUM_INFERENCE_STEPS
# - Use smaller image dimensions
```

### Performance Optimization

#### 1. CPU Optimization
```python
# Use CPU-optimized settings
DEVICE=cpu
NUM_INFERENCE_STEPS=15  # Further reduce for speed
IMAGE_WIDTH=512  # Reduce image size
IMAGE_HEIGHT=768
```

#### 2. Memory Optimization
```bash
# Conservative memory settings
MAX_MEMORY_USAGE=2048  # 2GB
MAX_CONCURRENT_REQUESTS=2
BATCH_SIZE=1
```

#### 3. Caching Strategy
```bash
# Enable aggressive caching
REDIS_URL=redis://your-redis-service-url:6379/0
# Cache results for longer periods
CACHE_TTL=7200  # 2 hours
```

## 💰 Cost Optimization

### Free Tier Limits

- **Web Service**: 750 hours/month
- **Redis**: 30 days free trial
- **Disk**: 1GB free

### Paid Plans

- **Starter**: $7/month for web service
- **Standard**: $25/month for better performance
- **Performance**: $50/month for GPU support (if available)

### Cost-Saving Tips

1. **Use Free Tier Wisely**
   - Optimize for CPU-only processing
   - Use aggressive caching
   - Implement request queuing

2. **Scale Down When Not in Use**
   - Use Render's auto-suspend feature
   - Implement usage-based scaling

3. **Optimize Resource Usage**
   - Reduce memory footprint
   - Use efficient image formats
   - Implement result caching

## 🔒 Security Considerations

### Production Security

1. **API Key Authentication**
   ```bash
   # Set in Render environment variables
   API_KEY=your-secure-api-key-here
   ```

2. **CORS Configuration**
   ```bash
   # Restrict to your frontend domain
   ALLOWED_ORIGINS=https://your-frontend-domain.com
   ```

3. **Rate Limiting**
   ```bash
   # Conservative rate limits for Render
   RATE_LIMIT_PER_MINUTE=30
   ```

4. **File Upload Limits**
   ```bash
   # Limit file sizes
   MAX_FILE_SIZE=5242880  # 5MB
   ```

## 🚀 Deployment Checklist

- [ ] Repository connected to Render
- [ ] Environment variables configured
- [ ] Model files uploaded/downloaded
- [ ] Redis service created and connected
- [ ] Persistent disk configured
- [ ] Health check endpoint working
- [ ] Frontend environment variables updated
- [ ] CORS configured for frontend domain
- [ ] API key authentication set up (optional)
- [ ] Performance monitoring configured
- [ ] Logs accessible and monitored

## 📞 Support

### Render Support
- [Render Documentation](https://render.com/docs)
- [Render Community](https://community.render.com)
- [Render Status](https://status.render.com)

### Application Support
- Check logs in Render dashboard
- Monitor health check endpoint
- Review performance metrics
- Test API endpoints manually

## 📚 Additional Resources

- [Render Python Guide](https://render.com/docs/deploy-python)
- [Render Redis Guide](https://render.com/docs/deploy-redis)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [IDM-VTON Model](https://huggingface.co/yisol/IDM-VTON)

---

**Note**: This deployment guide is specifically optimized for Render's infrastructure and constraints. The configuration prioritizes stability and cost-effectiveness over maximum performance.
