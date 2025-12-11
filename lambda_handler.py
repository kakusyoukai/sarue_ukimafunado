"""
Lambda function to handle ALB requests with maintenance mode support.

This Lambda function:
- Receives requests from an Application Load Balancer (ALB)
- Returns a maintenance page from S3 during maintenance mode
- Replaces parameters in the maintenance page with values from ALB event/context
- Routes specific URLs to invoke another Lambda function for special processing
"""

import json
import os
import boto3
from typing import Dict, Any

# Initialize AWS clients (lazy initialization to avoid region errors during import)
s3_client = None
lambda_client = None

def get_s3_client():
    """Get or create S3 client."""
    global s3_client
    if s3_client is None:
        s3_client = boto3.client('s3')
    return s3_client

def get_lambda_client():
    """Get or create Lambda client."""
    global lambda_client
    if lambda_client is None:
        lambda_client = boto3.client('lambda')
    return lambda_client

def get_config():
    """Get configuration from environment variables (runtime)."""
    return {
        'MAINTENANCE_MODE': os.environ.get('MAINTENANCE_MODE', 'true').lower() == 'true',
        'S3_BUCKET': os.environ.get('S3_BUCKET', 'maintenance-pages'),
        'S3_KEY': os.environ.get('S3_KEY', 'maintenance.html'),
        'SPECIAL_URL_PATH': os.environ.get('SPECIAL_URL_PATH', '/special'),
        'SPECIAL_LAMBDA_ARN': os.environ.get('SPECIAL_LAMBDA_ARN', '')
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler function for ALB requests.
    
    Args:
        event: ALB event containing request information
        context: Lambda context object
    
    Returns:
        Dict containing status code, headers, and body for ALB response
    """
    try:
        config = get_config()
        
        # Extract request information from ALB event
        request_path = event.get('path', '/')
        http_method = event.get('httpMethod', 'GET')
        query_params = event.get('queryStringParameters') or {}
        headers = event.get('headers') or {}
        
        # Check if this is a special URL that should invoke another Lambda
        if should_invoke_special_lambda(request_path, config):
            return invoke_special_lambda(event, context, config)
        
        # If in maintenance mode, return maintenance page
        if config['MAINTENANCE_MODE']:
            return get_maintenance_response(event, context, config)
        
        # Normal processing (when not in maintenance mode)
        # This would typically forward to your application
        return {
            'statusCode': 200,
            'statusDescription': '200 OK',
            'isBase64Encoded': False,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'message': 'Service is operational',
                'path': request_path
            })
        }
        
    except Exception as e:
        return handle_error(e)


def should_invoke_special_lambda(path: str, config: Dict[str, Any] = None) -> bool:
    """
    Check if the request path matches the special URL pattern.
    
    Args:
        path: Request path
        config: Configuration dict (optional, will fetch if not provided)
    
    Returns:
        True if should invoke special Lambda, False otherwise
    """
    if config is None:
        config = get_config()
    return path.startswith(config['SPECIAL_URL_PATH'])


def invoke_special_lambda(event: Dict[str, Any], context: Any, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Invoke another Lambda function for special URL processing.
    
    Args:
        event: ALB event to pass to the special Lambda
        context: Lambda context
        config: Configuration dict (optional, will fetch if not provided)
    
    Returns:
        Response from the special Lambda function
    """
    if config is None:
        config = get_config()
        
    if not config['SPECIAL_LAMBDA_ARN']:
        return {
            'statusCode': 503,
            'statusDescription': '503 Service Unavailable',
            'isBase64Encoded': False,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'error': 'Special Lambda ARN not configured'
            })
        }
    
    try:
        # Invoke the special Lambda function
        response = get_lambda_client().invoke(
            FunctionName=config['SPECIAL_LAMBDA_ARN'],
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'event': event,
                'context': {
                    'function_name': context.function_name,
                    'function_version': context.function_version,
                    'request_id': context.request_id,
                    'memory_limit_in_mb': context.memory_limit_in_mb
                }
            })
        )
        
        # Parse the response from the special Lambda
        payload = json.loads(response['Payload'].read())
        
        # Return the response from the special Lambda
        return payload
        
    except Exception as e:
        return {
            'statusCode': 500,
            'statusDescription': '500 Internal Server Error',
            'isBase64Encoded': False,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'error': f'Error invoking special Lambda: {str(e)}'
            })
        }


def get_maintenance_response(event: Dict[str, Any], context: Any, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Fetch maintenance page from S3 and return with parameter replacement.
    
    Args:
        event: ALB event containing request information
        context: Lambda context
        config: Configuration dict (optional, will fetch if not provided)
    
    Returns:
        ALB response with maintenance page
    """
    if config is None:
        config = get_config()
        
    try:
        # Fetch maintenance page from S3
        response = get_s3_client().get_object(Bucket=config['S3_BUCKET'], Key=config['S3_KEY'])
        maintenance_html = response['Body'].read().decode('utf-8')
        
        # Replace parameters in the maintenance page
        maintenance_html = replace_parameters(maintenance_html, event, context)
        
        return {
            'statusCode': 503,
            'statusDescription': '503 Service Unavailable',
            'isBase64Encoded': False,
            'headers': {
                'Content-Type': 'text/html; charset=utf-8',
                'Retry-After': '3600'
            },
            'body': maintenance_html
        }
        
    except Exception as e:
        # If we can't fetch the maintenance page, return a simple fallback
        return get_fallback_maintenance_response(str(e))


def replace_parameters(html: str, event: Dict[str, Any], context: Any) -> str:
    """
    Replace template parameters in the HTML with actual values.
    
    Parameters that can be replaced:
    - {{REQUEST_ID}}: Lambda request ID
    - {{TIMESTAMP}}: Current timestamp
    - {{PATH}}: Request path
    - {{METHOD}}: HTTP method
    - {{SOURCE_IP}}: Source IP address
    - {{USER_AGENT}}: User agent string
    - {{HOST}}: Host header
    - {{FUNCTION_NAME}}: Lambda function name
    
    Args:
        html: HTML template with {{PARAMETER}} placeholders
        event: ALB event
        context: Lambda context
    
    Returns:
        HTML with parameters replaced
    """
    import datetime
    
    # Extract values from event and context
    replacements = {
        'REQUEST_ID': context.request_id,
        'TIMESTAMP': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'PATH': event.get('path', '/'),
        'METHOD': event.get('httpMethod', 'GET'),
        'SOURCE_IP': event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown'),
        'USER_AGENT': event.get('headers', {}).get('user-agent', 'unknown'),
        'HOST': event.get('headers', {}).get('host', 'unknown'),
        'FUNCTION_NAME': context.function_name,
    }
    
    # Replace all parameters in the HTML
    for key, value in replacements.items():
        pattern = '{{' + key + '}}'
        html = html.replace(pattern, str(value))
    
    return html


def get_fallback_maintenance_response(error_message: str) -> Dict[str, Any]:
    """
    Return a simple fallback maintenance page when S3 fetch fails.
    
    Args:
        error_message: Error message to include in logs
    
    Returns:
        ALB response with fallback maintenance page
    """
    fallback_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Maintenance</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                text-align: center;
                padding: 50px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
                background-color: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
            }
            p {
                color: #666;
                line-height: 1.6;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔧 Maintenance in Progress</h1>
            <p>We're currently performing scheduled maintenance to improve our service.</p>
            <p>Please check back soon. We apologize for any inconvenience.</p>
        </div>
    </body>
    </html>
    """
    
    return {
        'statusCode': 503,
        'statusDescription': '503 Service Unavailable',
        'isBase64Encoded': False,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8',
            'Retry-After': '3600'
        },
        'body': fallback_html
    }


def handle_error(error: Exception) -> Dict[str, Any]:
    """
    Handle unexpected errors and return appropriate response.
    
    Args:
        error: Exception that occurred
    
    Returns:
        ALB error response
    """
    return {
        'statusCode': 500,
        'statusDescription': '500 Internal Server Error',
        'isBase64Encoded': False,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'error': 'Internal server error',
            'message': str(error)
        })
    }
