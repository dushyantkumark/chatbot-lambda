#!/bin/bash
# This script is used to create an image, retag image then push the image to ecr. Update the ecr new image to lambda function
# Variables
REPO="<account_id>.dkr.ecr.us-east-1.amazonaws.com/chatbot-lambda"
TAG="v1"
FUNCTION_NAME="chatbotLambda"

echo "🔧 Building Docker image..."
docker buildx build --platform linux/amd64 -t chatbot-lambda:${TAG} . --load

echo "🔗 Tagging image..."
docker tag chatbot-lambda:${TAG} ${REPO}:${TAG}

echo "🔐 Logging into Amazon ECR..."
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account_id>.dkr.ecr.us-east-1.amazonaws.com

echo "📤 Pushing image to ECR..."
docker push ${REPO}:${TAG}

echo "🚀 Updating Lambda function code..."
aws lambda update-function-code \
  --function-name ${FUNCTION_NAME} \
  --image-uri ${REPO}:${TAG}

echo "✅ Deployment complete."

