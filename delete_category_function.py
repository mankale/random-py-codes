import json
import boto3
import logging
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ProductCategories')

def lambda_handler(event, context):
    """
    Lambda function to delete categories from the ProductCategories DynamoDB table.
    Main categories can only be deleted if they have no subcategories.
    
    Expected input format from Amazon Bedrock agent:
    {
        "messageVersion": "1.0",
        "agent": {
            "name": "productcatalogagent",
            "id": "IIDWUKXRYS"
        },
        "inputText": "Delete category electronics",
        "sessionId": "session-id",
        "actionGroup": "deletecategoryfunction",
        "apiPath": "/delete-category",
        "httpMethod": "POST",
        "parameters": [
            {
                "name": "categoryName",
                "type": "string",
                "value": "electronics"
            },
            {
                "name": "subcategoryPath",
                "type": "string",
                "value": "mobiles:apple"  # Optional
            }
        ]
    }
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Check if this is an Amazon Bedrock agent request
        if 'messageVersion' in event and 'parameters' in event:
            # Extract parameters from Bedrock agent request format
            parameters = {}
            for param in event.get('parameters', []):
                parameters[param['name']] = param['value']
            
            # Check for required parameters
            if 'categoryName' not in parameters:
                return format_bedrock_response(400, {
                    'status': 'error',
                    'message': 'Missing required parameter: categoryName'
                })
            
            category_name = parameters['categoryName'].lower()
            subcategory_path = parameters.get('subcategoryPath', None)
        else:
            # Handle direct Lambda invocation format
            if 'categoryName' not in event:
                return format_response(400, {
                    'status': 'error',
                    'message': 'Missing required parameter: categoryName'
                })
            
            category_name = event['categoryName'].lower()
            subcategory_path = event.get('subcategoryPath', None)
        
        # If subcategory path is provided, delete that specific subcategory
        if subcategory_path:
            if 'messageVersion' in event:
                return format_bedrock_response(*delete_subcategory_internal(category_name, subcategory_path))
            else:
                return delete_subcategory(category_name, subcategory_path)
        else:
            # If only category name is provided, attempt to delete the main category
            if 'messageVersion' in event:
                return format_bedrock_response(*delete_main_category_internal(category_name))
            else:
                return delete_main_category(category_name)
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        if 'messageVersion' in event:
            return format_bedrock_response(500, {
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            })
        else:
            return format_response(500, {
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            })

def format_response(status_code, body_dict):
    """Format response for direct Lambda invocation"""
    return {
        'statusCode': status_code,
        'body': json.dumps(body_dict)
    }

def format_bedrock_response(status_code, body_dict):
    """Format response for Amazon Bedrock agent"""
    response_body = body_dict
    
    # Create the Bedrock agent response format
    bedrock_response = {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": "deletecategoryfunction",
            "apiPath": "/delete-category",
            "httpMethod": "POST",
            "httpStatusCode": status_code,
            "responseBody": {
                "application/json": response_body
            }
        }
    }
    
    return bedrock_response

def delete_subcategory_internal(category_name, subcategory_path):
    """Delete a specific subcategory and return status code and response body"""
    try:
        # Check if the subcategory exists
        response = table.get_item(
            Key={
                'category': category_name,
                'subcategory': subcategory_path
            }
        )
        
        if 'Item' not in response:
            return 404, {
                'status': 'error',
                'message': f'Subcategory {subcategory_path} not found in category {category_name}'
            }
        
        # Delete the subcategory
        table.delete_item(
            Key={
                'category': category_name,
                'subcategory': subcategory_path
            }
        )
        
        return 200, {
            'status': 'success',
            'message': f'Successfully deleted subcategory {subcategory_path} from category {category_name}'
        }
        
    except ClientError as e:
        logger.error(f"DynamoDB error: {e.response['Error']['Message']}")
        return 500, {
            'status': 'error',
            'message': f"DynamoDB error: {e.response['Error']['Message']}"
        }

def delete_subcategory(category_name, subcategory_path):
    """Delete a specific subcategory - wrapper for direct Lambda invocation"""
    status_code, body = delete_subcategory_internal(category_name, subcategory_path)
    return format_response(status_code, body)

def delete_main_category_internal(category_name):
    """
    Delete a main category, but only if it has no subcategories.
    Returns status code and response body.
    """
    try:
        # First check if the main category exists
        response = table.get_item(
            Key={
                'category': category_name,
                'subcategory': 'main'
            }
        )
        
        if 'Item' not in response:
            return 404, {
                'status': 'error',
                'message': f'Main category {category_name} not found'
            }
        
        # Check if there are any subcategories for this main category
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('category').eq(category_name)
        )
        
        # If there are items other than the main category itself, we can't delete the main category
        if response['Count'] > 1:
            return 400, {
                'status': 'error',
                'message': f'Cannot delete main category {category_name} because it has subcategories. Delete all subcategories first.'
            }
        
        # If we reach here, we can safely delete the main category
        table.delete_item(
            Key={
                'category': category_name,
                'subcategory': 'main'
            }
        )
        
        return 200, {
            'status': 'success',
            'message': f'Successfully deleted main category {category_name}'
        }
        
    except ClientError as e:
        logger.error(f"DynamoDB error: {e.response['Error']['Message']}")
        return 500, {
            'status': 'error',
            'message': f"DynamoDB error: {e.response['Error']['Message']}"
        }

def delete_main_category(category_name):
    """Delete a main category - wrapper for direct Lambda invocation"""
    status_code, body = delete_main_category_internal(category_name)
    return format_response(status_code, body)
