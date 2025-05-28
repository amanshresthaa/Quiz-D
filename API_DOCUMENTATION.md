# Quiz Generation API Documentation

## Base URL
```
http://localhost:8000
```

## Authentication

All protected endpoints require an API key in the Authorization header:

```http
Authorization: Bearer your-api-key-here
```

### Setting Up Authentication

1. **Environment Variables:**
   ```bash
   export REQUIRE_API_KEY=true
   export API_KEY=your-secure-api-key
   ```

2. **Multiple API Keys:**
   ```bash
   export API_KEYS='["key1", "key2", "key3"]'
   ```

## Rate Limits

| Endpoint Type | Limit | Window |
|---------------|-------|--------|
| Quiz Generation | 10 requests | 5 minutes |
| Question Generation | 30 requests | 5 minutes |
| Content Operations | 20 requests | 5 minutes |

## Endpoints

### Health & Monitoring

#### GET /health
Basic health check (no authentication required)

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-05-28T09:58:36.123456",
  "version": "1.0.0",
  "config_valid": true
}
```

#### GET /health/detailed
Comprehensive system status (no authentication required)

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-05-28T09:58:36.123456",
  "version": "1.0.0",
  "config_valid": true,
  "metrics": {
    "cpu_percent": 15.2,
    "memory_percent": 45.8,
    "disk_percent": 23.1
  },
  "components": {
    "database": "healthy",
    "vector_store": "healthy",
    "dspy": "healthy"
  }
}
```

#### GET /metrics
Application metrics in JSON format

**Response:**
```json
{
  "request_metrics": {
    "total_requests": 1234,
    "avg_response_time": 0.245,
    "error_rate": 0.02
  },
  "system_metrics": {
    "cpu_percent": 15.2,
    "memory_percent": 45.8
  }
}
```

#### GET /metrics/prometheus
Prometheus-compatible metrics export

### Content Management

#### POST /content/ingest
Ingest and process content for quiz generation

**Authentication:** Required (Content limits)

**Request:**
```json
{
  "title": "Python Programming Guide",
  "text": "Python is a high-level programming language...",
  "source": "python_guide.txt",
  "metadata": {
    "category": "programming",
    "difficulty": "beginner"
  }
}
```

**Response:**
```json
{
  "content_id": "550e8400-e29b-41d4-a716-446655440000",
  "chunks_created": 5,
  "message": "Content ingested successfully"
}
```

#### GET /content
List all ingested content

**Authentication:** Optional

**Response:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Python Programming Guide",
    "text": "Python is a high-level...",
    "source": "python_guide.txt",
    "content_type": "text",
    "metadata": {...},
    "created_at": "2025-05-28T09:58:36.123456"
  }
]
```

#### GET /content/{content_id}
Get specific content by ID

**Authentication:** Optional

#### POST /content/search
Search content using vector similarity

**Authentication:** Required

**Request:**
```json
{
  "query": "Python loops and conditionals",
  "limit": 10,
  "similarity_threshold": 0.7
}
```

### Question Generation

#### POST /generate/question
Generate a single question from a topic

**Authentication:** Required (Question limits)

**Request:**
```json
{
  "topic_or_query": "Python list comprehensions",
  "question_type": "multiple_choice",
  "difficulty": "medium"
}
```

**Response:**
```json
{
  "question": {
    "id": "q_550e8400-e29b-41d4-a716-446655440000",
    "text": "What is the correct syntax for a list comprehension in Python?",
    "type": "multiple_choice",
    "options": [
      "[x for x in range(10)]",
      "{x for x in range(10)}",
      "(x for x in range(10))",
      "x for x in range(10)"
    ],
    "correct_answer": "[x for x in range(10)]",
    "explanation": "List comprehensions use square brackets...",
    "difficulty": "medium",
    "metadata": {...}
  },
  "error": null,
  "processing_time": 2.345
}
```

#### POST /generate/questions
Generate multiple questions from a topic

**Authentication:** Required (Question limits)

**Request:**
```json
{
  "topic_or_query": "Python basics",
  "num_questions": 5,
  "question_types": ["multiple_choice", "true_false"],
  "difficulty": "easy"
}
```

**Response:**
```json
{
  "questions": [...],
  "count": 5,
  "error": null,
  "processing_time": 8.567
}
```

### Quiz Generation

#### POST /quiz/generate
Generate a complete quiz from existing content

**Authentication:** Required (Quiz limits)

**Request:**
```json
{
  "content_ids": ["550e8400-e29b-41d4-a716-446655440000"],
  "num_questions": 10,
  "question_types": ["multiple_choice"],
  "difficulty_levels": ["easy", "medium"],
  "title": "Python Programming Quiz",
  "description": "Test your Python knowledge"
}
```

**Response:**
```json
{
  "quiz_id": "quiz_550e8400-e29b-41d4-a716-446655440000",
  "message": "Quiz generated successfully"
}
```

#### POST /generate/quick-quiz
Generate a quiz directly from a topic (no content ingestion required)

**Authentication:** Required (Quiz limits)

**Request:**
```json
{
  "title": "Python Basics Quiz",
  "description": "A quick quiz about Python programming",
  "topic_or_query": "Python programming fundamentals",
  "num_questions": 5,
  "question_types": ["multiple_choice"],
  "difficulty": "easy"
}
```

**Response:**
```json
{
  "quiz": {
    "id": "quiz_550e8400-e29b-41d4-a716-446655440000",
    "title": "Python Basics Quiz",
    "description": "A quick quiz about Python programming",
    "questions": [...],
    "created_at": "2025-05-28T09:58:36.123456",
    "metadata": {...}
  },
  "count": 5,
  "processing_time": 15.234
}
```

#### GET /quiz/{quiz_id}
Get a specific quiz by ID

**Authentication:** Optional

## Error Responses

### Authentication Errors
```json
{
  "detail": "Authentication failed",
  "error": "401: Invalid API key"
}
```

### Rate Limiting Errors
```json
{
  "detail": "Rate limit exceeded",
  "retry_after": 300
}
```

### Validation Errors
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "topic_or_query"],
      "msg": "Field required",
      "input": {...}
    }
  ]
}
```

### Server Errors
```json
{
  "detail": "Internal server error",
  "error": "500: An unexpected error occurred"
}
```

## Data Models

### Question Types
- `multiple_choice`: Multiple choice question with options
- `true_false`: True/false question
- `short_answer`: Short text answer
- `essay`: Long form essay question

### Difficulty Levels
- `easy`: Basic level questions
- `medium`: Intermediate level questions  
- `hard`: Advanced level questions

## Rate Limiting Headers

Responses include rate limiting information:

```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1640995200
```

## Security Headers

All responses include security headers:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
Referrer-Policy: strict-origin-when-cross-origin
```

## Example Usage

### Python Client Example

```python
import requests

# Configuration
BASE_URL = "http://localhost:8000"
API_KEY = "your-api-key-here"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Ingest content
content_data = {
    "title": "Python Guide",
    "text": "Python is a programming language...",
    "source": "guide.txt"
}
response = requests.post(f"{BASE_URL}/content/ingest", 
                        headers=headers, json=content_data)
content_result = response.json()
content_id = content_result["content_id"]

# Generate quiz
quiz_data = {
    "content_ids": [content_id],
    "num_questions": 5,
    "question_types": ["multiple_choice"],
    "title": "Python Quiz"
}
response = requests.post(f"{BASE_URL}/quiz/generate", 
                        headers=headers, json=quiz_data)
quiz_result = response.json()
```

### cURL Examples

```bash
# Health check
curl http://localhost:8000/health

# Generate question with authentication
curl -X POST http://localhost:8000/generate/question \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"topic_or_query": "Python basics"}'

# Get metrics
curl http://localhost:8000/metrics
```

## CLI Tool Usage

```bash
# Install dependencies
pip install click PyYAML requests

# Health check
python quiz_cli.py health

# Ingest content
python quiz_cli.py ingest content.txt --title "My Content"

# Generate question
python quiz_cli.py question "Python loops"

# Generate quiz
python quiz_cli.py quiz "Python basics" --num 5 --output quiz.json

# Batch operations
python quiz_cli.py batch operations.yaml
```

## Support

For issues and questions:
- Check the application logs
- Verify API key configuration
- Ensure all required environment variables are set
- Review rate limiting status in response headers
