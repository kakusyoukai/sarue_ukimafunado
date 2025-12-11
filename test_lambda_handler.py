"""
Unit tests for Lambda maintenance handler.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path to import lambda_handler
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lambda_handler


class TestLambdaHandler:
    """Test cases for the main Lambda handler function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_context = Mock()
        self.mock_context.request_id = 'test-request-id-123'
        self.mock_context.function_name = 'test-function'
        self.mock_context.function_version = '1'
        self.mock_context.memory_limit_in_mb = 128
        
        self.sample_alb_event = {
            'path': '/test',
            'httpMethod': 'GET',
            'headers': {
                'host': 'example.com',
                'user-agent': 'Test-Agent/1.0'
            },
            'queryStringParameters': {
                'param1': 'value1'
            },
            'requestContext': {
                'identity': {
                    'sourceIp': '192.168.1.1'
                }
            }
        }
    
    @patch.dict(os.environ, {'MAINTENANCE_MODE': 'false'})
    def test_normal_operation_mode(self):
        """Test handler when not in maintenance mode."""
        response = lambda_handler.lambda_handler(self.sample_alb_event, self.mock_context)
        
        assert response['statusCode'] == 200
        assert response['statusDescription'] == '200 OK'
        assert 'Service is operational' in response['body']
    
    @patch.dict(os.environ, {
        'MAINTENANCE_MODE': 'true',
        'S3_BUCKET': 'test-bucket',
        'S3_KEY': 'test-key.html'
    })
    @patch('lambda_handler.s3_client')
    def test_maintenance_mode(self, mock_s3):
        """Test handler returns maintenance page when in maintenance mode."""
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=lambda: b'<html>Maintenance {{REQUEST_ID}}</html>')
        }
        
        response = lambda_handler.lambda_handler(self.sample_alb_event, self.mock_context)
        
        assert response['statusCode'] == 503
        assert response['statusDescription'] == '503 Service Unavailable'
        assert 'test-request-id-123' in response['body']
        assert 'Maintenance' in response['body']
        mock_s3.get_object.assert_called_once_with(Bucket='test-bucket', Key='test-key.html')
    
    @patch.dict(os.environ, {
        'MAINTENANCE_MODE': 'true',
        'SPECIAL_URL_PATH': '/special',
        'SPECIAL_LAMBDA_ARN': 'arn:aws:lambda:us-east-1:123456789012:function:special-function'
    })
    @patch('lambda_handler.get_lambda_client')
    def test_special_url_invokes_lambda(self, mock_get_lambda):
        """Test that special URL invokes another Lambda function."""
        mock_lambda_client = Mock()
        mock_get_lambda.return_value = mock_lambda_client
        special_event = self.sample_alb_event.copy()
        special_event['path'] = '/special/endpoint'
        
        mock_response = {
            'statusCode': 200,
            'body': json.dumps({'result': 'special'})
        }
        mock_lambda_client.invoke.return_value = {
            'Payload': MagicMock(read=lambda: json.dumps(mock_response).encode())
        }
        
        response = lambda_handler.lambda_handler(special_event, self.mock_context)
        
        assert response['statusCode'] == 200
        mock_lambda_client.invoke.assert_called_once()
    
    @patch.dict(os.environ, {'SPECIAL_URL_PATH': '/special'})
    def test_should_invoke_special_lambda(self):
        """Test URL pattern matching for special Lambda invocation."""
        assert lambda_handler.should_invoke_special_lambda('/special') == True
        assert lambda_handler.should_invoke_special_lambda('/special/path') == True
        assert lambda_handler.should_invoke_special_lambda('/normal') == False
        assert lambda_handler.should_invoke_special_lambda('/') == False


class TestParameterReplacement:
    """Test cases for parameter replacement functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_context = Mock()
        self.mock_context.request_id = 'req-123'
        self.mock_context.function_name = 'test-func'
        
        self.sample_event = {
            'path': '/test/path',
            'httpMethod': 'POST',
            'headers': {
                'host': 'test.example.com',
                'user-agent': 'Mozilla/5.0'
            },
            'requestContext': {
                'identity': {
                    'sourceIp': '10.0.0.1'
                }
            }
        }
    
    def test_replace_parameters_basic(self):
        """Test basic parameter replacement."""
        html = '<html>Request: {{REQUEST_ID}}, Path: {{PATH}}</html>'
        result = lambda_handler.replace_parameters(html, self.sample_event, self.mock_context)
        
        assert 'req-123' in result
        assert '/test/path' in result
        assert '{{REQUEST_ID}}' not in result
        assert '{{PATH}}' not in result
    
    def test_replace_parameters_all_types(self):
        """Test all parameter types are replaced."""
        html = '''
        Request: {{REQUEST_ID}}
        Timestamp: {{TIMESTAMP}}
        Path: {{PATH}}
        Method: {{METHOD}}
        IP: {{SOURCE_IP}}
        Agent: {{USER_AGENT}}
        Host: {{HOST}}
        Function: {{FUNCTION_NAME}}
        '''
        result = lambda_handler.replace_parameters(html, self.sample_event, self.mock_context)
        
        assert 'req-123' in result
        assert '/test/path' in result
        assert 'POST' in result
        assert '10.0.0.1' in result
        assert 'Mozilla/5.0' in result
        assert 'test.example.com' in result
        assert 'test-func' in result
        # Timestamp should be present in ISO format
        assert '-' in result and ':' in result
    
    def test_replace_parameters_no_placeholders(self):
        """Test HTML without placeholders remains unchanged."""
        html = '<html><body>No placeholders here</body></html>'
        result = lambda_handler.replace_parameters(html, self.sample_event, self.mock_context)
        
        assert result == html


class TestMaintenanceResponse:
    """Test cases for maintenance response generation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_context = Mock()
        self.mock_context.request_id = 'test-req'
        self.mock_context.function_name = 'test-func'
        
        self.sample_event = {
            'path': '/',
            'httpMethod': 'GET',
            'headers': {'host': 'example.com'},
            'requestContext': {'identity': {'sourceIp': '1.2.3.4'}}
        }
    
    @patch.dict(os.environ, {'S3_BUCKET': 'test-bucket', 'S3_KEY': 'test.html'})
    @patch('lambda_handler.get_s3_client')
    def test_get_maintenance_response_success(self, mock_get_s3):
        """Test successful retrieval of maintenance page."""
        mock_s3 = Mock()
        mock_get_s3.return_value = mock_s3
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=lambda: b'<html>Maintenance</html>')
        }
        
        response = lambda_handler.get_maintenance_response(self.sample_event, self.mock_context)
        
        assert response['statusCode'] == 503
        assert 'text/html' in response['headers']['Content-Type']
        assert 'Maintenance' in response['body']
    
    @patch.dict(os.environ, {'S3_BUCKET': 'test-bucket', 'S3_KEY': 'test.html'})
    @patch('lambda_handler.get_s3_client')
    def test_get_maintenance_response_s3_error(self, mock_get_s3):
        """Test fallback when S3 fetch fails."""
        mock_s3 = Mock()
        mock_get_s3.return_value = mock_s3
        mock_s3.get_object.side_effect = Exception('S3 error')
        
        response = lambda_handler.get_maintenance_response(self.sample_event, self.mock_context)
        
        assert response['statusCode'] == 503
        assert 'Maintenance in Progress' in response['body']
    
    def test_get_fallback_maintenance_response(self):
        """Test fallback maintenance page generation."""
        response = lambda_handler.get_fallback_maintenance_response('Test error')
        
        assert response['statusCode'] == 503
        assert 'Maintenance in Progress' in response['body']
        assert 'text/html' in response['headers']['Content-Type']


class TestSpecialLambdaInvocation:
    """Test cases for special Lambda invocation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_context = Mock()
        self.mock_context.request_id = 'test-req'
        self.mock_context.function_name = 'main-func'
        self.mock_context.function_version = '1'
        self.mock_context.memory_limit_in_mb = 256
        
        self.sample_event = {
            'path': '/special/endpoint',
            'httpMethod': 'GET',
            'headers': {}
        }
    
    @patch.dict(os.environ, {'SPECIAL_LAMBDA_ARN': ''})
    def test_invoke_special_lambda_no_arn(self):
        """Test error when special Lambda ARN is not configured."""
        response = lambda_handler.invoke_special_lambda(self.sample_event, self.mock_context)
        
        assert response['statusCode'] == 503
        assert 'not configured' in response['body']
    
    @patch.dict(os.environ, {
        'SPECIAL_LAMBDA_ARN': 'arn:aws:lambda:us-east-1:123456789012:function:special'
    })
    @patch('lambda_handler.get_lambda_client')
    def test_invoke_special_lambda_success(self, mock_get_lambda):
        """Test successful invocation of special Lambda."""
        mock_lambda_client = Mock()
        mock_get_lambda.return_value = mock_lambda_client
        expected_response = {
            'statusCode': 200,
            'body': json.dumps({'result': 'success'})
        }
        mock_lambda_client.invoke.return_value = {
            'Payload': MagicMock(read=lambda: json.dumps(expected_response).encode())
        }
        
        response = lambda_handler.invoke_special_lambda(self.sample_event, self.mock_context)
        
        assert response['statusCode'] == 200
        assert 'success' in response['body']
    
    @patch.dict(os.environ, {
        'SPECIAL_LAMBDA_ARN': 'arn:aws:lambda:us-east-1:123456789012:function:special'
    })
    @patch('lambda_handler.get_lambda_client')
    def test_invoke_special_lambda_error(self, mock_get_lambda):
        """Test error handling when special Lambda invocation fails."""
        mock_lambda_client = Mock()
        mock_get_lambda.return_value = mock_lambda_client
        mock_lambda_client.invoke.side_effect = Exception('Lambda invocation failed')
        
        response = lambda_handler.invoke_special_lambda(self.sample_event, self.mock_context)
        
        assert response['statusCode'] == 500
        assert 'Error invoking special Lambda' in response['body']


class TestErrorHandling:
    """Test cases for error handling."""
    
    def test_handle_error(self):
        """Test error response generation."""
        error = Exception('Test error message')
        response = lambda_handler.handle_error(error)
        
        assert response['statusCode'] == 500
        assert response['statusDescription'] == '500 Internal Server Error'
        assert 'Test error message' in response['body']
        assert 'application/json' in response['headers']['Content-Type']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
