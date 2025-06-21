import json
import boto3
import uuid
import logging
from datetime import datetime
from botocore.exceptions import ClientError
import re

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize clients globally
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table = dynamodb.Table("ChatLogs")

# UUID validation
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)

def validate_session_id(session_id):
    return bool(UUID_PATTERN.match(session_id))

def lambda_handler(event, context):
    try:
        logger.info(f"Received event: {json.dumps(event, indent=2)}")
        
        # Parse input
        body = event.get("body", {})
        if isinstance(body, str):
            body = json.loads(body)
        
        user_input = body.get("message", "").strip()
        session_id = body.get("sessionId", str(uuid.uuid4()))

        # Validate input
        if not user_input:
            raise ValueError("Missing or empty 'message' in request body.")
        if len(user_input) > 1000:
            raise ValueError("Input exceeds maximum length of 1000 characters.")
        if not validate_session_id(session_id):
            session_id = str(uuid.uuid4())

        # Prepare payload for Nova Micro
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": user_input}]
                }
            ]
        }

        # Invoke Bedrock
        try:
            response = bedrock.invoke_model(
                modelId="amazon.nova-micro-v1:0",
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json"
            )
            response_body = json.loads(response['body'].read())
            logger.info(f"Bedrock response: {json.dumps(response_body, indent=2)}")
            
            # Handle the Nova response structure correctly
            try:
                # Extract text from the response based on Nova's structure
                if 'output' in response_body and 'message' in response_body['output'] and 'content' in response_body['output']['message']:
                    content = response_body['output']['message']['content']
                    if isinstance(content, list) and len(content) > 0 and 'text' in content[0]:
                        answer = content[0]['text']
                    else:
                        answer = str(content)
                elif 'message' in response_body and 'content' in response_body['message']:
                    content = response_body['message']['content']
                    if isinstance(content, list) and len(content) > 0 and 'text' in content[0]:
                        answer = content[0]['text']
                    else:
                        answer = str(content)
                else:
                    # Fallback
                    answer = "Response received but could not extract text content."
                    logger.warning(f"Could not extract text from response: {json.dumps(response_body)}")
            except Exception as e:
                logger.error(f"Error extracting text from response: {str(e)}")
                answer = f"Error processing response: {str(e)}"
        except ClientError as e:
            logger.error(f"Bedrock error: {e.response['Error']['Code']}")
            raise Exception(f"Bedrock invocation failed: {e.response['Error']['Message']}")

        # Log to DynamoDB
        try:
            table.put_item(
                Item={
                    "sessionId": session_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "userInput": user_input,
                    "modelResponse": answer
                }
                # Removed the problematic condition expression
            )
        except ClientError as e:
            logger.error(f"DynamoDB error: {str(e)}")
            raise Exception(f"DynamoDB write failed: {str(e)}")

        # Return response
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "sessionId": session_id,
                "response": answer
            }),
            "isBase64Encoded": False
        }

    except Exception as e:
        logger.error(f"ERROR: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
            "isBase64Encoded": False
        }
