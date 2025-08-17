@echo off
REM IDM-VTON Backend Deployment Script for Windows
REM This script deploys the IDM-VTON backend for use with uwear-virtual-shop

echo 🚀 Starting IDM-VTON Backend Deployment...

REM Check if Docker is installed
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not installed. Please install Docker Desktop first.
    exit /b 1
)

REM Check if Docker Compose is installed
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker Compose is not installed. Please install Docker Compose first.
    exit /b 1
)

echo [INFO] Checking prerequisites...

REM Create necessary directories
echo [INFO] Creating directories...
if not exist "data\cache" mkdir "data\cache"
if not exist "data\results" mkdir "data\results"
if not exist "logs" mkdir "logs"
if not exist "models" mkdir "models"

REM Set up environment file
if not exist ".env" (
    echo [INFO] Creating .env file from template...
    copy ".env.example" ".env" >nul
    echo [WARNING] Please edit .env file with your configuration before starting the service
) else (
    echo [INFO] .env file already exists
)

REM Check if models are available
echo [INFO] Checking model files...
if not exist "ckpt" (
    echo [WARNING] Model files not found in ckpt/ directory
    echo [WARNING] Please download the required model files:
    echo   1. DensePose model: model_final_162be9.pkl
    echo   2. Human parsing models: parsing_atr.onnx, parsing_lip.onnx
    echo   3. OpenPose model: body_pose_model.pth
    echo   4. IP-Adapter: ip-adapter-plus_sdxl_vit-h.bin
    echo   5. Image encoder: config.json, model.safetensors
    echo [WARNING] You can download them from: https://huggingface.co/yisol/IDM-VTON
)

REM Build Docker image
echo [INFO] Building Docker image...
docker build -t idm-vton:latest .

if %errorlevel% neq 0 (
    echo [ERROR] Failed to build Docker image
    exit /b 1
)

echo [SUCCESS] Docker image built successfully

REM Start services
echo [INFO] Starting services with Docker Compose...
docker-compose up -d

if %errorlevel% neq 0 (
    echo [ERROR] Failed to start services
    exit /b 1
)

echo [SUCCESS] Services started successfully

REM Wait for services to be ready
echo [INFO] Waiting for services to be ready...
timeout /t 10 /nobreak >nul

REM Check if the API is responding
echo [INFO] Checking API health...
curl -f http://localhost:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo [SUCCESS] API is healthy and responding
) else (
    echo [WARNING] API health check failed. The service might still be starting up.
    echo [WARNING] You can check the logs with: docker-compose logs -f
)

REM Display deployment information
echo.
echo [SUCCESS] 🎉 IDM-VTON Backend Deployment Complete!
echo.
echo 📋 Deployment Information:
echo   • API URL: http://localhost:8000
echo   • Health Check: http://localhost:8000/health
echo   • API Documentation: http://localhost:8000/docs
echo   • Metrics: http://localhost:8000/api/v1/metrics
echo.
echo 🔧 Configuration:
echo   • Edit .env file to customize settings
echo   • Check logs: docker-compose logs -f
echo   • Stop services: docker-compose down
echo.
echo 🌐 For uwear-virtual-shop integration:
echo   • Set VITE_IDM_VTON_API_URL=http://your-server-ip:8000
echo   • Set VITE_IDM_VTON_API_KEY=your_api_key (if configured)
echo.
echo 📊 Monitoring:
echo   • Resource usage: docker stats
echo   • API metrics: http://localhost:8000/api/v1/metrics
echo   • Service logs: docker-compose logs -f idm-vton
echo.

REM Check if Redis is running
docker-compose ps redis | findstr "Up" >nul
if %errorlevel% equ 0 (
    echo [SUCCESS] Redis is running for caching and background tasks
) else (
    echo [WARNING] Redis is not running. Caching and background tasks will be limited.
)

echo [INFO] Deployment script completed successfully!
pause
