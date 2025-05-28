#!/usr/bin/env python3
"""
Command Line Interface for Quiz Generation System

This CLI tool provides a convenient way to interact with the Quiz Generation API
from the command line, supporting file input, various output formats, and
authentication.
"""

import click
import json
import yaml
import os
import sys
import requests
from pathlib import Path
from typing import Dict, Any, Optional
import time

# Default API configuration
DEFAULT_API_HOST = "localhost"
DEFAULT_API_PORT = 8000
DEFAULT_API_BASE = f"http://{DEFAULT_API_HOST}:{DEFAULT_API_PORT}"


class QuizCLI:
    """Main CLI class for Quiz Generation."""
    
    def __init__(self, api_base: str, api_key: Optional[str] = None):
        self.api_base = api_base.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        
        # Set authentication header if API key is provided
        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            })
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to the API."""
        url = f"{self.api_base}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    click.echo(f"API Error: {error_detail.get('detail', 'Unknown error')}", err=True)
                except:
                    click.echo(f"HTTP Error {e.response.status_code}: {e.response.text}", err=True)
            else:
                click.echo(f"Connection Error: {str(e)}", err=True)
            sys.exit(1)
    
    def health_check(self) -> bool:
        """Check if the API is healthy."""
        try:
            response = self._make_request('GET', '/health')
            return response.get('status') == 'healthy'
        except:
            return False
    
    def ingest_content(self, title: str, text: str, source: Optional[str] = None) -> Dict[str, Any]:
        """Ingest content into the system."""
        data = {
            'title': title,
            'text': text,
            'source': source or 'cli'
        }
        return self._make_request('POST', '/content/ingest', data)
    
    def generate_question(self, topic: str, question_type: str = 'multiple_choice', 
                         difficulty: str = 'medium') -> Dict[str, Any]:
        """Generate a single question."""
        data = {
            'topic_or_query': topic,
            'question_type': question_type,
            'difficulty': difficulty
        }
        return self._make_request('POST', '/generate/question', data)
    
    def generate_questions(self, topic: str, num_questions: int = 5, 
                          question_type: str = 'multiple_choice', 
                          difficulty: str = 'medium') -> Dict[str, Any]:
        """Generate multiple questions."""
        data = {
            'topic_or_query': topic,
            'num_questions': num_questions,
            'question_type': question_type,
            'difficulty': difficulty
        }
        return self._make_request('POST', '/generate/questions', data)
    
    def generate_quick_quiz(self, title: str, topic: str, num_questions: int = 5,
                           difficulty: str = 'medium') -> Dict[str, Any]:
        """Generate a complete quiz."""
        data = {
            'title': title,
            'topic_or_query': topic,
            'num_questions': num_questions,
            'difficulty': difficulty
        }
        return self._make_request('POST', '/generate/quick-quiz', data)


def load_config_file(config_path: str) -> Dict[str, Any]:
    """Load configuration from file."""
    path = Path(config_path)
    if not path.exists():
        click.echo(f"Config file not found: {config_path}", err=True)
        sys.exit(1)
    
    try:
        with open(path, 'r') as f:
            if path.suffix.lower() in ['.yml', '.yaml']:
                return yaml.safe_load(f)
            else:
                return json.load(f)
    except Exception as e:
        click.echo(f"Error loading config file: {str(e)}", err=True)
        sys.exit(1)


def save_output(data: Dict[str, Any], output_path: str, format_type: str):
    """Save output to file."""
    path = Path(output_path)
    
    try:
        with open(path, 'w') as f:
            if format_type == 'json':
                json.dump(data, f, indent=2)
            elif format_type == 'yaml':
                yaml.dump(data, f, default_flow_style=False)
            else:
                # Pretty print for text format
                f.write(format_output(data, 'text'))
        
        click.echo(f"Output saved to: {output_path}")
    except Exception as e:
        click.echo(f"Error saving output: {str(e)}", err=True)


def format_output(data: Dict[str, Any], format_type: str) -> str:
    """Format output for display."""
    if format_type == 'json':
        return json.dumps(data, indent=2)
    elif format_type == 'yaml':
        return yaml.dump(data, default_flow_style=False)
    elif format_type == 'text':
        # Custom text formatting for better readability
        if 'questions' in data:
            # Multiple questions
            output = []
            for i, q in enumerate(data['questions'], 1):
                output.append(f"\n--- Question {i} ---")
                output.append(f"Question: {q.get('question', 'N/A')}")
                output.append(f"Type: {q.get('type', 'N/A')}")
                output.append(f"Difficulty: {q.get('difficulty', 'N/A')}")
                if 'options' in q:
                    output.append("Options:")
                    for opt in q['options']:
                        output.append(f"  - {opt}")
                output.append(f"Answer: {q.get('answer', 'N/A')}")
                if 'explanation' in q:
                    output.append(f"Explanation: {q['explanation']}")
            return '\n'.join(output)
        elif 'question' in data:
            # Single question
            output = []
            output.append(f"Question: {data.get('question', 'N/A')}")
            output.append(f"Type: {data.get('type', 'N/A')}")
            output.append(f"Difficulty: {data.get('difficulty', 'N/A')}")
            if 'options' in data:
                output.append("Options:")
                for opt in data['options']:
                    output.append(f"  - {opt}")
            output.append(f"Answer: {data.get('answer', 'N/A')}")
            if 'explanation' in data:
                output.append(f"Explanation: {data['explanation']}")
            return '\n'.join(output)
        else:
            # Default JSON format for other responses
            return json.dumps(data, indent=2)
    else:
        return str(data)


# CLI Commands

@click.group()
@click.option('--api-host', default=DEFAULT_API_HOST, help='API host')
@click.option('--api-port', default=DEFAULT_API_PORT, help='API port')
@click.option('--api-key', help='API key for authentication')
@click.option('--config', help='Config file path (JSON or YAML)')
@click.pass_context
def cli(ctx, api_host, api_port, api_key, config):
    """Quiz Generation CLI - Generate quizzes from the command line."""
    
    # Load configuration from file if provided
    if config:
        config_data = load_config_file(config)
        api_host = config_data.get('api_host', api_host)
        api_port = config_data.get('api_port', api_port)
        api_key = config_data.get('api_key', api_key)
    
    # Check environment variables
    api_key = api_key or os.getenv('QUIZ_API_KEY')
    
    api_base = f"http://{api_host}:{api_port}"
    ctx.ensure_object(dict)
    ctx.obj['client'] = QuizCLI(api_base, api_key)


@cli.command()
@click.pass_context
def health(ctx):
    """Check API health status."""
    client = ctx.obj['client']
    
    if client.health_check():
        click.echo("✅ API is healthy and ready")
    else:
        click.echo("❌ API is not responding or unhealthy", err=True)
        sys.exit(1)


@cli.command()
@click.option('--title', required=True, help='Content title')
@click.option('--file', 'file_path', help='Read content from file')
@click.option('--text', help='Content text (if not using --file)')
@click.option('--source', help='Content source identifier')
@click.option('--output', help='Output file path')
@click.option('--format', 'output_format', type=click.Choice(['json', 'yaml', 'text']), 
              default='json', help='Output format')
@click.pass_context
def ingest(ctx, title, file_path, text, source, output, output_format):
    """Ingest content into the system."""
    client = ctx.obj['client']
    
    # Get content text
    if file_path:
        try:
            with open(file_path, 'r') as f:
                content_text = f.read()
            source = source or file_path
        except Exception as e:
            click.echo(f"Error reading file: {str(e)}", err=True)
            sys.exit(1)
    elif text:
        content_text = text
    else:
        click.echo("Error: Must provide either --file or --text", err=True)
        sys.exit(1)
    
    # Ingest content
    with click.progressbar(length=1, label='Ingesting content') as bar:
        result = client.ingest_content(title, content_text, source)
        bar.update(1)
    
    # Output result
    if output:
        save_output(result, output, output_format)
    else:
        click.echo(format_output(result, output_format))


@cli.command()
@click.option('--topic', required=True, help='Question topic or query')
@click.option('--type', 'question_type', type=click.Choice(['multiple_choice', 'true_false', 'short_answer']),
              default='multiple_choice', help='Question type')
@click.option('--difficulty', type=click.Choice(['easy', 'medium', 'hard']), 
              default='medium', help='Question difficulty')
@click.option('--output', help='Output file path')
@click.option('--format', 'output_format', type=click.Choice(['json', 'yaml', 'text']), 
              default='text', help='Output format')
@click.pass_context
def question(ctx, topic, question_type, difficulty, output, output_format):
    """Generate a single question."""
    client = ctx.obj['client']
    
    with click.progressbar(length=1, label='Generating question') as bar:
        result = client.generate_question(topic, question_type, difficulty)
        bar.update(1)
    
    # Output result
    if output:
        save_output(result, output, output_format)
    else:
        click.echo(format_output(result, output_format))


@cli.command()
@click.option('--topic', required=True, help='Questions topic or query')
@click.option('--count', default=5, help='Number of questions to generate')
@click.option('--type', 'question_type', type=click.Choice(['multiple_choice', 'true_false', 'short_answer']),
              default='multiple_choice', help='Question type')
@click.option('--difficulty', type=click.Choice(['easy', 'medium', 'hard']), 
              default='medium', help='Question difficulty')
@click.option('--output', help='Output file path')
@click.option('--format', 'output_format', type=click.Choice(['json', 'yaml', 'text']), 
              default='text', help='Output format')
@click.pass_context
def questions(ctx, topic, count, question_type, difficulty, output, output_format):
    """Generate multiple questions."""
    client = ctx.obj['client']
    
    with click.progressbar(length=1, label=f'Generating {count} questions') as bar:
        result = client.generate_questions(topic, count, question_type, difficulty)
        bar.update(1)
    
    # Output result
    if output:
        save_output(result, output, output_format)
    else:
        click.echo(format_output(result, output_format))


@cli.command()
@click.option('--title', required=True, help='Quiz title')
@click.option('--topic', required=True, help='Quiz topic or query')
@click.option('--count', default=5, help='Number of questions in quiz')
@click.option('--difficulty', type=click.Choice(['easy', 'medium', 'hard']), 
              default='medium', help='Quiz difficulty')
@click.option('--output', help='Output file path')
@click.option('--format', 'output_format', type=click.Choice(['json', 'yaml', 'text']), 
              default='text', help='Output format')
@click.pass_context
def quiz(ctx, title, topic, count, difficulty, output, output_format):
    """Generate a complete quiz."""
    client = ctx.obj['client']
    
    with click.progressbar(length=1, label=f'Generating quiz with {count} questions') as bar:
        result = client.generate_quick_quiz(title, topic, count, difficulty)
        bar.update(1)
    
    # Output result
    if output:
        save_output(result, output, output_format)
    else:
        click.echo(format_output(result, output_format))


@cli.command()
@click.option('--input-file', required=True, help='Input file with batch requests (JSON/YAML)')
@click.option('--output-dir', help='Output directory for results')
@click.option('--format', 'output_format', type=click.Choice(['json', 'yaml', 'text']), 
              default='json', help='Output format')
@click.pass_context
def batch(ctx, input_file, output_dir, output_format):
    """Process batch requests from file."""
    client = ctx.obj['client']
    
    # Load batch requests
    try:
        batch_data = load_config_file(input_file)
    except:
        sys.exit(1)
    
    if 'requests' not in batch_data:
        click.echo("Error: Batch file must contain 'requests' array", err=True)
        sys.exit(1)
    
    requests_list = batch_data['requests']
    output_dir = Path(output_dir) if output_dir else Path('.')
    output_dir.mkdir(exist_ok=True)
    
    with click.progressbar(requests_list, label='Processing batch requests') as bar:
        for i, request in enumerate(bar):
            try:
                request_type = request.get('type')
                if request_type == 'question':
                    result = client.generate_question(
                        request['topic'],
                        request.get('question_type', 'multiple_choice'),
                        request.get('difficulty', 'medium')
                    )
                elif request_type == 'questions':
                    result = client.generate_questions(
                        request['topic'],
                        request.get('count', 5),
                        request.get('question_type', 'multiple_choice'),
                        request.get('difficulty', 'medium')
                    )
                elif request_type == 'quiz':
                    result = client.generate_quick_quiz(
                        request['title'],
                        request['topic'],
                        request.get('count', 5),
                        request.get('difficulty', 'medium')
                    )
                else:
                    click.echo(f"Unknown request type: {request_type}", err=True)
                    continue
                
                # Save result
                output_file = output_dir / f"result_{i+1:03d}.{output_format}"
                save_output(result, str(output_file), output_format)
                
            except Exception as e:
                click.echo(f"Error processing request {i+1}: {str(e)}", err=True)


if __name__ == '__main__':
    cli()
