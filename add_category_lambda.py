import json
import boto3
import os
from botocore.exceptions import ClientError

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('PRODUCT_CATEGORIES_TABLE', 'ProductCategories')
table = dynamodb.Table(table_name)

def lambda_handler(event, context):
    """
    Lambda function to add a new category or subcategory to the ProductCategories DynamoDB table.
    This function is designed to be invoked by an Amazon Bedrock agent as part of an action group.
    
    Expected input format from Bedrock agent:
    {
        "messageVersion": "1.0",
        "agent": {...},
        "inputText": "...",
        "sessionAttributes": {...},
        "promptSessionAttributes": {...},
        "actionGroup": "...",
        "apiPath": "/addcategory",
        "parameters": [
            {
                "name": "category",
                "type": "string",
                "value": "..."
            },
            {
                "name": "subcategory",
                "type": "string",
                "value": "..."
            },
            {
                "name": "description",
                "type": "string",
                "value": "..."
            },
            {
                "name": "level",
                "type": "number",
                "value": ...
            }
        ]
    }
    """
    try:
        # Extract parameters from Bedrock agent request
        api_path = event.get('apiPath')
        
        # Verify this is the correct API path
        if api_path != '/addcategory':
            return build_bedrock_response(False, f"Invalid API path: {api_path}")
        
        # Extract parameters from the Bedrock agent request
        parameters = event.get('parameters', [])
        param_dict = {param['name']: param['value'] for param in parameters if 'value' in param}
        
        # Validate required fields
        if 'category' not in param_dict:
            return build_bedrock_response(False, "Category is required")
        
        if 'description' not in param_dict:
            return build_bedrock_response(False, "Description is required")
        
        # Extract fields
        category = param_dict['category'].lower()
        description = param_dict['description']
        
        # Handle main category vs subcategory
        if 'subcategory' in param_dict and param_dict['subcategory']:
            subcategory = param_dict['subcategory'].lower()
            
            # Check if parent category exists
            parent_category = category
            try:
                response = table.get_item(
                    Key={
                        'category': parent_category,
                        'subcategory': parent_category
                    }
                )
                if 'Item' not in response:
                    return build_bedrock_response(False, f"Parent category '{parent_category}' does not exist")
            except ClientError as e:
                return build_bedrock_response(False, f"Error checking parent category: {str(e)}")
            
            # Determine level
            if 'level' in param_dict:
                level = int(param_dict['level'])
            else:
                # Auto-determine level based on subcategory format
                level = 2 if ':' not in subcategory else subcategory.count(':') + 2
            
            # Check if subcategory already exists
            try:
                response = table.get_item(
                    Key={
                        'category': category,
                        'subcategory': subcategory
                    }
                )
                if 'Item' in response:
                    return build_bedrock_response(False, f"Subcategory '{subcategory}' already exists under category '{category}'")
            except ClientError as e:
                return build_bedrock_response(False, f"Error checking subcategory: {str(e)}")
            
            # Add subcategory
            item = {
                'category': category,
                'subcategory': subcategory,
                'description': description,
                'level': level
            }
        else:
            # This is a main category
            subcategory = category  # For main categories, subcategory equals category
            
            # Check if category already exists
            try:
                response = table.get_item(
                    Key={
                        'category': category,
                        'subcategory': subcategory
                    }
                )
                if 'Item' in response:
                    return build_bedrock_response(False, f"Category '{category}' already exists")
            except ClientError as e:
                return build_bedrock_response(False, f"Error checking category: {str(e)}")
            
            # Add main category
            item = {
                'category': category,
                'subcategory': subcategory,
                'description': description,
                'level': 1  # Main categories are always level 1
            }
        
        # Write to DynamoDB
        try:
            table.put_item(Item=item)
            
            # Return success response
            if 'subcategory' in param_dict and param_dict['subcategory']:
                success_message = f"Successfully added subcategory '{subcategory}' under category '{category}'"
            else:
                success_message = f"Successfully added main category '{category}'"
                
            return build_bedrock_response(True, success_message, item)
            
        except ClientError as e:
            return build_bedrock_response(False, f"Error adding category to database: {str(e)}")
            
    except Exception as e:
        return build_bedrock_response(False, f"Unexpected error: {str(e)}")

def build_bedrock_response(success, message, data=None):
    """
    Helper function to build response for Amazon Bedrock agent
    
    Args:
        success (bool): Whether the operation was successful
        message (str): Message to return to the agent
        data (dict, optional): Additional data to include in the response
    
    Returns:
        dict: Formatted response for Bedrock agent
    """
    response_content = {
        "success": success,
        "message": message
    }
    
    if data:
        response_content["data"] = data
    
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": "ProductCategoryManagement",
            "apiPath": "/addcategory",
            "httpMethod": "POST",
            "httpStatusCode": 200 if success else 400,
            "responseBody": {
                "application/json": json.dumps(response_content)
            }
        }
    }
