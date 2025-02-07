import boto3
import logging
from botocore.exceptions import ClientError
import json

logger = logging.getLogger(__name__)
rekognition = boto3.client('rekognition')
s3 = boto3.client('s3')

def lambda_handler(event, context):
    try:
        # Parse EventBridge event
        if 'detail' in event:
            # Extract the actual string values from the nested dictionaries
            bucket_detail = event['detail'].get('bucket', {})
            object_detail = event['detail'].get('object', {})
            
            # Get the actual bucket name and object key
            bucket_name = bucket_detail.get('name') if isinstance(bucket_detail, dict) else bucket_detail
            object_key = object_detail.get('key') if isinstance(object_detail, dict) else object_detail
            
            if not bucket_name or not object_key:
                raise ValueError('Missing bucket name or object key in event detail')
            
            # Process S3 image using bucket and key
            response = rekognition.detect_labels(
                Image={
                    'S3Object': {
                        'Bucket': str(bucket_name),  # Ensure string type
                        'Name': str(object_key)      # Ensure string type
                    }
                },
                MinConfidence=95  # Set minimum confidence threshold to 95%
            )
            
            # Filter labels with confidence >= 95%
            high_confidence_labels = [
                {
                    'Name': label['Name'],
                    'Confidence': label['Confidence']
                }
                for label in response['Labels']
                if label['Confidence'] >= 95
            ]

            # Get existing object metadata
            object_metadata = s3.head_object(Bucket=bucket_name, Key=object_key)
            
            # Prepare new metadata
            metadata = object_metadata.get('Metadata', {})
            
            # Convert labels to metadata format
            # Join label names with confidence scores
            label_strings = [f"{label['Name']}:{label['Confidence']:.2f}" for label in high_confidence_labels]
            metadata['rekognition-labels'] = ','.join(label_strings)
            
            # Copy object to itself with new metadata
            s3.copy_object(
                Bucket=bucket_name,
                Key=object_key,
                CopySource={'Bucket': bucket_name, 'Key': object_key},
                Metadata=metadata,
                MetadataDirective='REPLACE'
            )
            
            lambda_response = {
                "statusCode": 200,
                "body": json.dumps({
                    "Labels": high_confidence_labels,
                    "ImageLocation": f"{bucket_name}/{object_key}",
                    "MetadataUpdated": True
                })
            }
            
            # Print results for CloudWatch logs
            print(f"High confidence (>95%) labels found in {bucket_name}/{object_key}:")
            for label in high_confidence_labels:
                print(f"Label: {label['Name']}, Confidence: {label['Confidence']:.2f}%")
            
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
        logger.error("Error in function %s: %s",
                    context.invoked_function_arn, error_message)

    except ValueError as val_error:
        lambda_response = {
            'statusCode': 400,
            'body': {
                "Error": "ValueError",
                "ErrorMessage": str(val_error)
            }
        }
        logger.error("Error in function %s: %s",
                     context.invoked_function_arn, str(val_error))

    return lambda_response
