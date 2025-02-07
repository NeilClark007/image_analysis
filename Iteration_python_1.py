import boto3
import logging
from botocore.exceptions import ClientError
import json
import base64

logger = logging.getLogger(__name__)
rekognition = boto3.client('rekognition')

def lambda_handler(event, context):
    try:
        # Parse EventBridge event
        # EventBridge events have a 'detail' section where you can put custom parameters
        if 'detail' in event:
            bucket_name = event['detail'].get('bucket')
            object_key = event['detail'].get('object')
            
            if not bucket_name or not object_key:
                raise ValueError('Missing bucket or object key in EventBridge event detail')
                
            # Process S3 image using bucket and key from EventBridge event
            response = rekognition.detect_labels(
                Image={
                    'S3Object': {
                        'Bucket': bucket_name,
                        'Name': object_key
                    }
                }
            )
            
            lambda_response = {
                "statusCode": 200,
                "body": json.dumps(response)
            }
            
            labels = [label['Name'] for label in response['Labels']]
            print(f"Labels found in {bucket_name}/{object_key}:")
            print(labels)
            
        else:
            raise ValueError("Invalid event structure - expected EventBridge event")

    except ClientError as client_err:
        error_message = "Couldn't analyze image: " + client_err.response['Error']['Message']
        
        lambda_response = {
            'statusCode': 400,
            'body': {
                "Error": client_err.response['Error']['Code'],
                "ErrorMessage": error_message
            }
        }
        logger.error("Error function %s: %s",
                    context.invoked_function_arn, error_message)

    except ValueError as val_error:
        lambda_response = {
            'statusCode': 400,
            'body': {
                "Error": "ValueError",
                "ErrorMessage": format(val_error)
            }
        }
        logger.error("Error function %s: %s",
                     context.invoked_function_arn, format(val_error))

    return lambda_response
