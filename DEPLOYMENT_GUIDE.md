# Quiz Generation API - Production Deployment Guide

## 🚀 Overview

This guide covers deploying the Quiz Generation API to production environments with proper security, monitoring, and scalability configurations.

## 📋 Prerequisites

- Python 3.11+
- OpenAI API key
- Database (PostgreSQL recommended for production)
- Redis (optional, for advanced rate limiting)
- SSL certificate for HTTPS

## 🔧 Environment Configuration

### Required Environment Variables

```bash
# API Configuration
export API_HOST=0.0.0.0
export API_PORT=8000
export WORKERS=4

# OpenAI Integration
export OPENAI_API_KEY=sk-your-openai-api-key-here

# Authentication & Security
export REQUIRE_API_KEY=true
export API_KEY=your-secure-production-api-key
# OR for multiple keys:
export API_KEYS='["key1", "key2", "key3"]'

# Database
export DATABASE_URL=postgresql://user:password@localhost:5432/quiz_db

# Production Settings
export ENVIRONMENT=production
export DEBUG=false
export LOG_LEVEL=INFO
```

### Optional Configuration

```bash
# Rate Limiting
export RATE_LIMIT_QUIZ=10
export RATE_LIMIT_QUESTIONS=30
export RATE_LIMIT_CONTENT=20
export RATE_LIMIT_WINDOW=300

# Timeouts
export API_TIMEOUT=30
export QUIZ_GENERATION_TIMEOUT=300
export QUESTION_GENERATION_TIMEOUT=120

# CORS (if serving web clients)
export CORS_ALLOWED_ORIGINS='["https://yourdomain.com"]'
export CORS_ALLOWED_METHODS='["GET", "POST"]'

# Monitoring
export METRICS_ENABLED=true
export LOG_JSON_FORMAT=true
export SYSTEM_MONITORING_INTERVAL=60
```

## 🐳 Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 quizapp
RUN chown -R quizapp:quizapp /app
USER quizapp

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  quiz-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/quiz_db
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - REQUIRE_API_KEY=true
      - API_KEY=${API_KEY}
      - ENVIRONMENT=production
    depends_on:
      - db
      - redis
    restart: unless-stopped
    volumes:
      - ./data:/app/data
    networks:
      - quiz-network

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=quiz_db
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - quiz-network
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    networks:
      - quiz-network
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/ssl/certs
    depends_on:
      - quiz-api
    networks:
      - quiz-network
    restart: unless-stopped

networks:
  quiz-network:
    driver: bridge

volumes:
  postgres_data:
```

### Build and Run

```bash
# Build the image
docker-compose build

# Run in production
docker-compose up -d

# View logs
docker-compose logs -f quiz-api

# Scale the application
docker-compose up -d --scale quiz-api=3
```

## ☸️ Kubernetes Deployment

### Namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: quiz-app
```

### ConfigMap

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: quiz-config
  namespace: quiz-app
data:
  API_HOST: "0.0.0.0"
  API_PORT: "8000"
  WORKERS: "4"
  ENVIRONMENT: "production"
  DEBUG: "false"
  LOG_LEVEL: "INFO"
  REQUIRE_API_KEY: "true"
  METRICS_ENABLED: "true"
  LOG_JSON_FORMAT: "true"
```

### Secrets

```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: quiz-secrets
  namespace: quiz-app
type: Opaque
data:
  openai-api-key: <base64-encoded-openai-key>
  api-key: <base64-encoded-api-key>
  database-url: <base64-encoded-database-url>
```

### Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: quiz-api
  namespace: quiz-app
  labels:
    app: quiz-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: quiz-api
  template:
    metadata:
      labels:
        app: quiz-api
    spec:
      containers:
      - name: quiz-api
        image: quiz-api:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: quiz-config
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: quiz-secrets
              key: openai-api-key
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: quiz-secrets
              key: api-key
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: quiz-secrets
              key: database-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
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
        - name: data-volume
          mountPath: /app/data
      volumes:
      - name: data-volume
        persistentVolumeClaim:
          claimName: quiz-data-pvc
```

### Service

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: quiz-api-service
  namespace: quiz-app
spec:
  selector:
    app: quiz-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

### Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: quiz-api-ingress
  namespace: quiz-app
  annotations:
    kubernetes.io/ingress.class: "nginx"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
spec:
  tls:
  - hosts:
    - api.yourdomain.com
    secretName: quiz-api-tls
  rules:
  - host: api.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: quiz-api-service
            port:
              number: 80
```

### Deploy to Kubernetes

```bash
# Apply all configurations
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secrets.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml

# Check deployment status
kubectl get pods -n quiz-app
kubectl get services -n quiz-app
kubectl describe deployment quiz-api -n quiz-app

# View logs
kubectl logs -f deployment/quiz-api -n quiz-app

# Scale deployment
kubectl scale deployment quiz-api --replicas=5 -n quiz-app
```

## 🔧 Nginx Configuration

### nginx.conf

```nginx
events {
    worker_connections 1024;
}

http {
    upstream quiz_app {
        server quiz-api:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/s;

    server {
        listen 80;
        server_name api.yourdomain.com;
        
        # Redirect HTTP to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name api.yourdomain.com;

        # SSL Configuration
        ssl_certificate /etc/ssl/certs/certificate.crt;
        ssl_certificate_key /etc/ssl/certs/private.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
        ssl_prefer_server_ciphers off;

        # Security Headers
        add_header X-Content-Type-Options nosniff;
        add_header X-Frame-Options DENY;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
        add_header Content-Security-Policy "default-src 'self'";
        add_header Referrer-Policy "strict-origin-when-cross-origin";

        # Rate limiting
        location / {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://quiz_app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Timeouts
            proxy_connect_timeout 30s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }

        # Stricter rate limiting for auth endpoints
        location ~ ^/(generate|quiz) {
            limit_req zone=auth burst=5 nodelay;
            proxy_pass http://quiz_app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health checks (no rate limiting)
        location /health {
            proxy_pass http://quiz_app;
        }
    }
}
```

## 📊 Monitoring Setup

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'quiz-api'
    static_configs:
      - targets: ['quiz-api:8000']
    metrics_path: '/metrics/prometheus'
```

### Grafana Dashboard

Key metrics to monitor:
- Request rate and response times
- Error rates by endpoint
- Authentication success/failure rates
- Rate limiting triggers
- System resources (CPU, memory, disk)
- Quiz generation success rates

### Alerting Rules

```yaml
# alerts.yml
groups:
- name: quiz-api
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: High error rate detected

  - alert: SlowResponses
    expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 10
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: Slow API responses detected
```

## 🔐 Security Hardening

### Database Security

```sql
-- Create dedicated database user
CREATE USER quiz_app WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE quiz_db TO quiz_app;
GRANT USAGE ON SCHEMA public TO quiz_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO quiz_app;

-- Enable SSL
ALTER SYSTEM SET ssl = on;
ALTER SYSTEM SET ssl_cert_file = 'server.crt';
ALTER SYSTEM SET ssl_key_file = 'server.key';
```

### API Key Management

```python
# Secure API key generation
import secrets
import string

def generate_api_key(length=32):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# Example
api_key = generate_api_key()
print(f"Generated API key: {api_key}")
```

### Firewall Rules

```bash
# UFW configuration
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

## 🔄 CI/CD Pipeline

### GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy Quiz API

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    - name: Run tests
      run: |
        python -m pytest tests/
        python test_api.py

  build-and-deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Build Docker image
      run: |
        docker build -t quiz-api:${{ github.sha }} .
    - name: Deploy to production
      run: |
        # Deploy steps here
        echo "Deploying to production..."
```

## 📋 Deployment Checklist

### Pre-deployment
- [ ] Environment variables configured
- [ ] SSL certificates installed
- [ ] Database migrations applied
- [ ] API keys generated and secured
- [ ] Monitoring systems configured
- [ ] Backup procedures tested
- [ ] Security scan completed

### Post-deployment
- [ ] Health checks passing
- [ ] Authentication working
- [ ] Rate limiting functional
- [ ] Monitoring alerts configured
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] Team notified

## 🚨 Troubleshooting

### Common Issues

1. **Authentication failures**
   ```bash
   # Check environment variables
   docker exec quiz-api env | grep API_KEY
   ```

2. **Database connection errors**
   ```bash
   # Test database connectivity
   docker exec quiz-api python -c "from app.database import engine; print(engine.url)"
   ```

3. **High memory usage**
   ```bash
   # Monitor memory usage
   docker stats quiz-api
   ```

4. **SSL certificate issues**
   ```bash
   # Check certificate validity
   openssl x509 -in certificate.crt -text -noout
   ```

### Log Analysis

```bash
# View application logs
docker logs quiz-api | jq '.'

# Monitor error rates
docker logs quiz-api | grep ERROR | wc -l

# Check authentication logs
docker logs quiz-api | grep "Authentication"
```

## 📞 Support

For production support:
1. Check application logs first
2. Verify monitoring dashboards
3. Review security alerts
4. Contact development team with relevant log excerpts

---

**This deployment guide ensures a secure, scalable, and maintainable production deployment of the Quiz Generation API.**
