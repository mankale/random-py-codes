import logging
import boto3
import json
import re
from decimal import Decimal
from typing import Dict, Any
from http import HTTPStatus

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ProductCategories')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Helper class to convert Decimal to float for JSON serialization
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """
    AWS Lambda handler for processing Bedrock agent requests.
    """
    responses = []
    api_path = event['apiPath']
    logger.info('API Path')
    logger.info(api_path)

    if api_path == '/categories':
        # Scan the entire table
        response = table.scan()
        items = response['Items']
        
        # Handle pagination if there are more items
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response['Items'])
        
        # Convert items to JSON string
        json_response = json.dumps(items, cls=DecimalEncoder)
    
    elif re.match(r'^/categories/[^/]+$', api_path):
        # Extract the category name from the path
        category = api_path.split('/')[-1]
        logger.info(f'Fetching subcategories for main category: {category}')
        
        # Query the table for items with the specified main category
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('category').eq(category)
        )
        items = response['Items']
        
        # Handle pagination if there are more items
        while 'LastEvaluatedKey' in response:
            response = table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('category').eq(category),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response['Items'])
        
        if not items:
            # Return 404 if no items found for the category
            http_status = 404
            json_response = json.dumps({"status": "error", "message": f"Category '{category}' not found"})
        else:
            http_status = 200
            # Convert items to JSON string
            json_response = json.dumps(items, cls=DecimalEncoder)
    
    response_body = {
        'application/json': {
            'body': json.dumps(json_response)
        }
    }

    action_response = {
        'actionGroup': event['actionGroup'],
        'apiPath': event['apiPath'],
        'httpMethod': event['httpMethod'],
        'httpStatusCode': 200,
        'responseBody': response_body
    }
    responses.append(action_response)

    api_response = {
        'messageVersion': '1.0', 
        'response': action_response}
        
    return api_response