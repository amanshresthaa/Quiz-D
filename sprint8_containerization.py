#!/usr/bin/env python3
"""
Sprint 8: Deployment Containerization & Automation
Docker containerization and deployment automation for production readiness.
"""

import os
import json
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DockerContainerizer:
    """Docker containerization manager"""
    
    def __init__(self, project_root: str = "/Users/amankumarshrestha/Downloads/Quiz-D"):
        self.project_root = Path(project_root)
        self.deployment_dir = self.project_root / "deployment"
        self.deployment_dir.mkdir(exist_ok=True)
    
    def create_dockerfile(self) -> str:
        """Create optimized Dockerfile for production"""
        dockerfile_content = """# Multi-stage Docker build for Quiz Generation Application
# Stage 1: Build stage
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Production stage
FROM python:3.11-slim

# Create non-root user for security
RUN groupadd -r quizapp && useradd -r -g quizapp quizapp

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/quizapp/.local

# Make sure scripts in .local are usable
ENV PATH=/home/quizapp/.local/bin:$PATH

# Copy application code
COPY app/ ./app/
COPY *.py ./
COPY *.md ./
COPY static/ ./static/ 
COPY templates/ ./templates/

# Create necessary directories
RUN mkdir -p logs data

# Set proper ownership
RUN chown -R quizapp:quizapp /app

# Switch to non-root user
USER quizapp

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app
ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=8000
ENV UVICORN_WORKERS=4

# Start command
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
"""
        
        dockerfile_path = self.project_root / "Dockerfile"
        with open(dockerfile_path, 'w') as f:
            f.write(dockerfile_content)
        
        logger.info(f"Created Dockerfile at {dockerfile_path}")
        return str(dockerfile_path)
    
    def create_dockerignore(self) -> str:
        """Create .dockerignore file"""
        dockerignore_content = """# Python
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

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Logs
*.log
logs/

# Development files
.env
.env.local
.env.development
.env.test

# Docker
Dockerfile*
docker-compose*.yml

# Git
.git/
.gitignore

# Documentation (only during build)
*.md
docs/

# Test files
test_*
*_test.py
tests/

# Temporary files
tmp/
temp/
*.tmp

# Database files (should be mounted)
*.db
*.sqlite
*.sqlite3

# Deployment files
deployment/
kubernetes/
helm/
"""
        
        dockerignore_path = self.project_root / ".dockerignore"
        with open(dockerignore_path, 'w') as f:
            f.write(dockerignore_content)
        
        logger.info(f"Created .dockerignore at {dockerignore_path}")
        return str(dockerignore_path)
    
    def create_docker_compose(self) -> str:
        """Create docker-compose.yml for local development and testing"""
        compose_content = """version: '3.8'

services:
  quiz-app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: quiz-generation-app
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DATABASE_URL=postgresql://quiz_user:quiz_password@db:5432/quiz_db
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    depends_on:
      - db
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  db:
    image: postgres:15-alpine
    container_name: quiz-postgres
    environment:
      - POSTGRES_DB=quiz_db
      - POSTGRES_USER=quiz_user
      - POSTGRES_PASSWORD=quiz_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./deployment/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U quiz_user -d quiz_db"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    container_name: quiz-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: quiz-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deployment/nginx.conf:/etc/nginx/nginx.conf
      - ./deployment/ssl:/etc/nginx/ssl
    depends_on:
      - quiz-app
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:

networks:
  default:
    name: quiz-network
"""
        
        compose_path = self.project_root / "docker-compose.yml"
        with open(compose_path, 'w') as f:
            f.write(compose_content)
        
        logger.info(f"Created docker-compose.yml at {compose_path}")
        return str(compose_path)
    
    def create_production_compose(self) -> str:
        """Create production docker-compose with additional services"""
        prod_compose_content = """version: '3.8'

services:
  quiz-app:
    build:
      context: .
      dockerfile: Dockerfile
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DATABASE_URL=postgresql://quiz_user:${POSTGRES_PASSWORD}@db:5432/quiz_db
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    depends_on:
      - db
      - redis
    networks:
      - app-network

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=quiz_db
      - POSTGRES_USER=quiz_user
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./deployment/init.sql:/docker-entrypoint-initdb.d/init.sql
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
    networks:
      - app-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U quiz_user -d quiz_db"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deployment/nginx.conf:/etc/nginx/nginx.conf
      - ./deployment/ssl:/etc/nginx/ssl
    depends_on:
      - quiz-app
    networks:
      - app-network
    deploy:
      resources:
        limits:
          memory: 512M

  monitoring:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./deployment/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    networks:
      - app-network

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./deployment/grafana:/etc/grafana/provisioning
    networks:
      - app-network

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:

networks:
  app-network:
    driver: overlay
    attachable: true
"""
        
        prod_compose_path = self.deployment_dir / "docker-compose.prod.yml"
        with open(prod_compose_path, 'w') as f:
            f.write(prod_compose_content)
        
        logger.info(f"Created production docker-compose at {prod_compose_path}")
        return str(prod_compose_path)
    
    def create_nginx_config(self) -> str:
        """Create Nginx configuration"""
        nginx_config = """user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log notice;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
    access_log /var/log/nginx/access.log main;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 100M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=quiz:10m rate=5r/s;

    # Upstream servers
    upstream quiz_app {
        least_conn;
        server quiz-app:8000 max_fails=3 fail_timeout=30s;
    }

    # HTTP to HTTPS redirect
    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }

    # HTTPS server
    server {
        listen 443 ssl http2;
        server_name _;

        # SSL configuration
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Referrer-Policy "no-referrer-when-downgrade" always;
        add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        # API endpoints with rate limiting
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://quiz_app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 30s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }

        # Quiz generation endpoints with stricter rate limiting
        location /quiz/ {
            limit_req zone=quiz burst=10 nodelay;
            proxy_pass http://quiz_app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # Static files
        location /static/ {
            alias /app/static/;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # Health check
        location /health {
            proxy_pass http://quiz_app;
            access_log off;
        }

        # All other requests
        location / {
            proxy_pass http://quiz_app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
"""
        
        nginx_config_path = self.deployment_dir / "nginx.conf"
        with open(nginx_config_path, 'w') as f:
            f.write(nginx_config)
        
        logger.info(f"Created Nginx config at {nginx_config_path}")
        return str(nginx_config_path)
    
    def create_deployment_scripts(self) -> Dict[str, str]:
        """Create deployment automation scripts"""
        scripts = {}
        
        # Build script
        build_script = """#!/bin/bash
# Build and prepare Docker images for deployment

set -e

echo "=== Quiz Generation App - Build Script ==="
echo "Starting build process..."

# Set variables
IMAGE_NAME="quiz-generation-app"
VERSION=${1:-latest}
REGISTRY=${REGISTRY:-""}

echo "Building Docker image: ${IMAGE_NAME}:${VERSION}"

# Build the Docker image
docker build -t ${IMAGE_NAME}:${VERSION} .

# Tag for registry if specified
if [ ! -z "$REGISTRY" ]; then
    docker tag ${IMAGE_NAME}:${VERSION} ${REGISTRY}/${IMAGE_NAME}:${VERSION}
    echo "Tagged image for registry: ${REGISTRY}/${IMAGE_NAME}:${VERSION}"
fi

# Run security scan
echo "Running security scan..."
if command -v trivy &> /dev/null; then
    trivy image ${IMAGE_NAME}:${VERSION}
else
    echo "Trivy not found, skipping security scan"
fi

echo "Build completed successfully!"
echo "Image: ${IMAGE_NAME}:${VERSION}"
echo "Size: $(docker images ${IMAGE_NAME}:${VERSION} --format 'table {{.Size}}')"
"""
        
        build_script_path = self.deployment_dir / "build.sh"
        with open(build_script_path, 'w') as f:
            f.write(build_script)
        os.chmod(build_script_path, 0o755)
        scripts['build'] = str(build_script_path)
        
        # Deploy script
        deploy_script = """#!/bin/bash
# Deploy Quiz Generation App

set -e

echo "=== Quiz Generation App - Deploy Script ==="

# Set variables
ENVIRONMENT=${1:-development}
VERSION=${2:-latest}

echo "Deploying to environment: ${ENVIRONMENT}"
echo "Version: ${VERSION}"

# Load environment variables
if [ -f ".env.${ENVIRONMENT}" ]; then
    source .env.${ENVIRONMENT}
    echo "Loaded environment variables from .env.${ENVIRONMENT}"
fi

# Choose docker-compose file based on environment
if [ "$ENVIRONMENT" = "production" ]; then
    COMPOSE_FILE="deployment/docker-compose.prod.yml"
else
    COMPOSE_FILE="docker-compose.yml"
fi

echo "Using compose file: ${COMPOSE_FILE}"

# Stop existing containers
echo "Stopping existing containers..."
docker-compose -f ${COMPOSE_FILE} down

# Pull latest images (if using registry)
if [ ! -z "$REGISTRY" ]; then
    echo "Pulling latest images..."
    docker-compose -f ${COMPOSE_FILE} pull
fi

# Start services
echo "Starting services..."
docker-compose -f ${COMPOSE_FILE} up -d

# Wait for services to be healthy
echo "Waiting for services to be healthy..."
sleep 30

# Check health
echo "Checking service health..."
docker-compose -f ${COMPOSE_FILE} ps

# Run health check
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Deployment successful - Application is healthy"
else
    echo "❌ Deployment failed - Application health check failed"
    docker-compose -f ${COMPOSE_FILE} logs quiz-app
    exit 1
fi

echo "Deployment completed successfully!"
"""
        
        deploy_script_path = self.deployment_dir / "deploy.sh"
        with open(deploy_script_path, 'w') as f:
            f.write(deploy_script)
        os.chmod(deploy_script_path, 0o755)
        scripts['deploy'] = str(deploy_script_path)
        
        # Backup script
        backup_script = """#!/bin/bash
# Backup Quiz Generation App data

set -e

echo "=== Quiz Generation App - Backup Script ==="

BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "${BACKUP_DIR}"

echo "Creating backup in: ${BACKUP_DIR}"

# Backup database
echo "Backing up database..."
docker-compose exec -T db pg_dump -U quiz_user quiz_db > "${BACKUP_DIR}/database.sql"

# Backup application data
echo "Backing up application data..."
if [ -d "./data" ]; then
    cp -r ./data "${BACKUP_DIR}/"
fi

# Backup logs
echo "Backing up logs..."
if [ -d "./logs" ]; then
    cp -r ./logs "${BACKUP_DIR}/"
fi

# Create backup info
cat > "${BACKUP_DIR}/backup_info.txt" << EOF
Backup created: $(date)
Database: Included
Application data: $([ -d "./data" ] && echo "Included" || echo "Not found")
Logs: $([ -d "./logs" ] && echo "Included" || echo "Not found")
Docker images: $(docker images --format "table {{.Repository}}:{{.Tag}}" | grep quiz)
EOF

# Compress backup
echo "Compressing backup..."
tar -czf "${BACKUP_DIR}.tar.gz" -C "./backups" "$(basename "${BACKUP_DIR}")"
rm -rf "${BACKUP_DIR}"

echo "Backup completed: ${BACKUP_DIR}.tar.gz"
echo "Size: $(du -h "${BACKUP_DIR}.tar.gz" | cut -f1)"
"""
        
        backup_script_path = self.deployment_dir / "backup.sh"
        with open(backup_script_path, 'w') as f:
            f.write(backup_script)
        os.chmod(backup_script_path, 0o755)
        scripts['backup'] = str(backup_script_path)
        
        logger.info("Created deployment scripts")
        return scripts
    
    def create_kubernetes_manifests(self) -> Dict[str, str]:
        """Create Kubernetes deployment manifests"""
        manifests = {}
        
        # Create kubernetes directory
        k8s_dir = self.deployment_dir / "kubernetes"
        k8s_dir.mkdir(exist_ok=True)
        
        # Namespace
        namespace_yaml = """apiVersion: v1
kind: Namespace
metadata:
  name: quiz-app
  labels:
    name: quiz-app
"""
        
        namespace_path = k8s_dir / "namespace.yaml"
        with open(namespace_path, 'w') as f:
            f.write(namespace_yaml)
        manifests['namespace'] = str(namespace_path)
        
        # ConfigMap
        configmap_yaml = """apiVersion: v1
kind: ConfigMap
metadata:
  name: quiz-app-config
  namespace: quiz-app
data:
  ENVIRONMENT: "production"
  LOG_LEVEL: "INFO"
  UVICORN_HOST: "0.0.0.0"
  UVICORN_PORT: "8000"
  UVICORN_WORKERS: "4"
"""
        
        configmap_path = k8s_dir / "configmap.yaml"
        with open(configmap_path, 'w') as f:
            f.write(configmap_yaml)
        manifests['configmap'] = str(configmap_path)
        
        # Secret
        secret_yaml = """apiVersion: v1
kind: Secret
metadata:
  name: quiz-app-secret
  namespace: quiz-app
type: Opaque
data:
  # Base64 encoded values - replace with actual encoded secrets
  OPENAI_API_KEY: ""
  DATABASE_URL: ""
  POSTGRES_PASSWORD: ""
"""
        
        secret_path = k8s_dir / "secret.yaml"
        with open(secret_path, 'w') as f:
            f.write(secret_yaml)
        manifests['secret'] = str(secret_path)
        
        # Deployment
        deployment_yaml = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: quiz-app
  namespace: quiz-app
  labels:
    app: quiz-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: quiz-app
  template:
    metadata:
      labels:
        app: quiz-app
    spec:
      containers:
      - name: quiz-app
        image: quiz-generation-app:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: quiz-app-config
        - secretRef:
            name: quiz-app-secret
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: logs
          mountPath: /app/logs
        - name: data
          mountPath: /app/data
      volumes:
      - name: logs
        emptyDir: {}
      - name: data
        persistentVolumeClaim:
          claimName: quiz-app-data
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: quiz-app-data
  namespace: quiz-app
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
"""
        
        deployment_path = k8s_dir / "deployment.yaml"
        with open(deployment_path, 'w') as f:
            f.write(deployment_yaml)
        manifests['deployment'] = str(deployment_path)
        
        # Service
        service_yaml = """apiVersion: v1
kind: Service
metadata:
  name: quiz-app-service
  namespace: quiz-app
  labels:
    app: quiz-app
spec:
  selector:
    app: quiz-app
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: quiz-app-ingress
  namespace: quiz-app
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - quiz-app.example.com
    secretName: quiz-app-tls
  rules:
  - host: quiz-app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: quiz-app-service
            port:
              number: 80
"""
        
        service_path = k8s_dir / "service.yaml"
        with open(service_path, 'w') as f:
            f.write(service_yaml)
        manifests['service'] = str(service_path)
        
        logger.info(f"Created Kubernetes manifests in {k8s_dir}")
        return manifests
    
    def create_environment_files(self) -> Dict[str, str]:
        """Create environment configuration files"""
        env_files = {}
        
        # Development environment
        dev_env = """# Development Environment Configuration
ENVIRONMENT=development
LOG_LEVEL=DEBUG
DEBUG=true

# API Configuration
UVICORN_HOST=0.0.0.0
UVICORN_PORT=8000
UVICORN_WORKERS=1
UVICORN_RELOAD=true

# Database
DATABASE_URL=postgresql://quiz_user:quiz_password@localhost:5432/quiz_db

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI (set your actual API key)
OPENAI_API_KEY=your_openai_api_key_here

# Security
SECRET_KEY=your_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Rate Limiting
ENABLE_RATE_LIMITING=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Monitoring
ENABLE_MONITORING=true
METRICS_ENDPOINT=/metrics
"""
        
        dev_env_path = self.project_root / ".env.development"
        with open(dev_env_path, 'w') as f:
            f.write(dev_env)
        env_files['development'] = str(dev_env_path)
        
        # Production environment template
        prod_env = """# Production Environment Configuration
ENVIRONMENT=production
LOG_LEVEL=INFO
DEBUG=false

# API Configuration
UVICORN_HOST=0.0.0.0
UVICORN_PORT=8000
UVICORN_WORKERS=4
UVICORN_RELOAD=false

# Database (use strong password)
POSTGRES_PASSWORD=your_strong_postgres_password_here
DATABASE_URL=postgresql://quiz_user:${POSTGRES_PASSWORD}@db:5432/quiz_db

# Redis
REDIS_URL=redis://redis:6379/0

# OpenAI (set your actual API key)
OPENAI_API_KEY=your_openai_api_key_here

# Security (generate strong keys)
SECRET_KEY=your_very_strong_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Rate Limiting
ENABLE_RATE_LIMITING=true
RATE_LIMIT_REQUESTS=50
RATE_LIMIT_WINDOW=60

# Monitoring
ENABLE_MONITORING=true
METRICS_ENDPOINT=/metrics

# Grafana
GRAFANA_PASSWORD=your_grafana_admin_password_here

# SSL/TLS
SSL_CERT_PATH=/etc/nginx/ssl/cert.pem
SSL_KEY_PATH=/etc/nginx/ssl/key.pem
"""
        
        prod_env_path = self.project_root / ".env.production.template"
        with open(prod_env_path, 'w') as f:
            f.write(prod_env)
        env_files['production'] = str(prod_env_path)
        
        logger.info("Created environment configuration files")
        return env_files
    
    def generate_deployment_report(self) -> Dict[str, Any]:
        """Generate comprehensive deployment report"""
        report = {
            "deployment_setup": {
                "timestamp": datetime.now().isoformat(),
                "project_root": str(self.project_root),
                "deployment_directory": str(self.deployment_dir)
            },
            "files_created": {},
            "docker_setup": {
                "dockerfile": "Created multi-stage production Dockerfile",
                "docker_compose": "Created development and production compose files",
                "dockerignore": "Created comprehensive .dockerignore",
                "nginx_config": "Created production Nginx configuration"
            },
            "kubernetes_setup": {
                "manifests": "Created complete Kubernetes manifests",
                "components": ["namespace", "configmap", "secret", "deployment", "service", "ingress"]
            },
            "automation_scripts": {
                "build_script": "Automated Docker image building",
                "deploy_script": "Automated deployment process",
                "backup_script": "Automated backup process"
            },
            "security_features": [
                "Non-root user in containers",
                "Multi-stage Docker builds",
                "Security headers in Nginx",
                "Resource limits in Kubernetes",
                "Health checks and monitoring",
                "SSL/TLS configuration"
            ],
            "deployment_ready": True
        }
        
        # Save report
        report_path = self.deployment_dir / "deployment_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        return report

def main():
    """Main containerization process"""
    logger.info("=" * 60)
    logger.info("STARTING DEPLOYMENT CONTAINERIZATION")
    logger.info("=" * 60)
    
    containerizer = DockerContainerizer()
    
    try:
        # Create Docker files
        logger.info("Creating Docker configuration...")
        containerizer.create_dockerfile()
        containerizer.create_dockerignore()
        containerizer.create_docker_compose()
        containerizer.create_production_compose()
        containerizer.create_nginx_config()
        
        # Create deployment scripts
        logger.info("Creating deployment automation scripts...")
        scripts = containerizer.create_deployment_scripts()
        
        # Create Kubernetes manifests
        logger.info("Creating Kubernetes manifests...")
        manifests = containerizer.create_kubernetes_manifests()
        
        # Create environment files
        logger.info("Creating environment configuration files...")
        env_files = containerizer.create_environment_files()
        
        # Generate report
        report = containerizer.generate_deployment_report()
        
        logger.info("=" * 60)
        logger.info("DEPLOYMENT CONTAINERIZATION COMPLETED")
        logger.info(f"Files created in: {containerizer.deployment_dir}")
        logger.info("Docker: Dockerfile, docker-compose.yml, .dockerignore")
        logger.info("Scripts: build.sh, deploy.sh, backup.sh")
        logger.info("Kubernetes: Complete manifests for production deployment")
        logger.info("Environment: Development and production configurations")
        logger.info("=" * 60)
        
        return report
        
    except Exception as e:
        logger.error(f"Containerization failed: {e}")
        raise

if __name__ == "__main__":
    main()
