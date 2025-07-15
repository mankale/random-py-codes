import boto3
import json
import os
from datetime import datetime

def create_product_categories_table(delete_if_exists=False):
    """
    Creates a DynamoDB table for product categories with category as partition key
    and subcategory as sort key. The table is designed to support all product catalog
    search service requirements including retrieving, suggesting, adding, and deleting
    categories.
    
    Parameters:
    - delete_if_exists (bool): If True, deletes the table if it already exists
    
    Returns:
    - DynamoDB Table resource
    """
    dynamodb = boto3.resource('dynamodb')
    table_name = 'ProductCategories'
    
    # Check if table already exists and delete if requested
    existing_tables = [table.name for table in dynamodb.tables.all()]
    if table_name in existing_tables:
        if delete_if_exists:
            print(f"Table {table_name} already exists. Deleting...")
            dynamodb.Table(table_name).delete()
            dynamodb.Table(table_name).wait_until_not_exists()
            print(f"Table {table_name} deleted.")
        else:
            print(f"Table {table_name} already exists. Using existing table.")
            return dynamodb.Table(table_name)
    
    # Create the table with enhanced schema
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {
                'AttributeName': 'category',
                'KeyType': 'HASH'  # Partition key
            },
            {
                'AttributeName': 'subcategory',
                'KeyType': 'RANGE'  # Sort key
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'category',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'subcategory',
                'AttributeType': 'S'
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        },
        Tags=[
            {
                'Key': 'Purpose',
                'Value': 'ProductCatalogSearchService'
            }
        ]
    )
    
    # Wait until the table exists
    table.meta.client.get_waiter('table_exists').wait(TableName=table_name)
    print(f"Table created successfully: {table.table_name}")
    return table

def populate_sample_data(table):
    """
    Populates the DynamoDB table with sample product category data.
    
    Parameters:
    - table: DynamoDB Table resource to populate
    """
    try:
        # Try to load from product_categories.json first
        if os.path.exists('product_categories.json'):
            with open('product_categories.json', 'r') as file:
                categories = json.load(file)
                
            for item in categories:
                table.put_item(
                    Item={
                        'category': item['main_category'].lower(),
                        'subcategory': item['sub_category'].lower(),
                        'description': item.get('description', ''),
                        'attributes': item.get('attributes', []),
                        'last_updated': item.get('last_updated', datetime.now().strftime('%Y-%m-%d')),
                        'active': True
                    }
                )
            print(f"Loaded {len(categories)} categories from product_categories.json")
            
        # Also try to load from product_category_hierarchy.json for more structured data
        elif os.path.exists('product_category_hierarchy.json'):
            with open('product_category_hierarchy.json', 'r') as file:
                hierarchy = json.load(file)
            
            count = 0
            for main_category in hierarchy.get('product_categories', {}).get('main_categories', []):
                category_name = main_category['name'].lower()
                
                # Add the main category itself with a special subcategory value
                table.put_item(
                    Item={
                        'category': category_name,
                        'subcategory': '_main',  # Special value to identify main category entries
                        'description': f"Main category for {category_name}",
                        'last_updated': datetime.now().strftime('%Y-%m-%d'),
                        'active': True
                    }
                )
                count += 1
                
                # Add all subcategories
                for subcategory in main_category.get('subcategories', []):
                    table.put_item(
                        Item={
                            'category': category_name,
                            'subcategory': subcategory['name'].lower(),
                            'description': f"Subcategory of {category_name}",
                            'subcategory_id': subcategory.get('id', ''),
                            'last_updated': datetime.now().strftime('%Y-%m-%d'),
                            'active': True
                        }
                    )
                    count += 1
            
            print(f"Loaded {count} categories from product_category_hierarchy.json")
        else:
            print("No sample data files found. Table created but empty.")
    except Exception as e:
        print(f"Error populating sample data: {str(e)}")

if __name__ == "__main__":
    # Create the table (set delete_if_exists=True to recreate if it exists)
    table = create_product_categories_table(delete_if_exists=False)
    
    # Populate with sample data if table was just created
    if table:
        populate_sample_data(table)
        print("DynamoDB setup complete!")
