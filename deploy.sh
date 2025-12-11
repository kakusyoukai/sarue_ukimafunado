#!/bin/bash

# デプロイスクリプト for Lambda Maintenance Handler

set -e

echo "Lambda Maintenance Handler デプロイスクリプト"
echo "=============================================="

# 設定
FUNCTION_NAME=${FUNCTION_NAME:-"maintenance-handler"}
RUNTIME="python3.13"
HANDLER="lambda_handler.lambda_handler"
ROLE_ARN=${LAMBDA_ROLE_ARN}
S3_BUCKET=${S3_BUCKET:-"maintenance-pages"}
S3_KEY=${S3_KEY:-"maintenance.html"}
MAINTENANCE_MODE=${MAINTENANCE_MODE:-"true"}

# 引数チェック
if [ -z "$ROLE_ARN" ]; then
    echo "エラー: LAMBDA_ROLE_ARN 環境変数が設定されていません"
    echo "使用方法: LAMBDA_ROLE_ARN=arn:aws:iam::ACCOUNT:role/ROLE ./deploy.sh"
    exit 1
fi

echo "設定:"
echo "  Function Name: $FUNCTION_NAME"
echo "  Runtime: $RUNTIME"
echo "  Role ARN: $ROLE_ARN"
echo "  S3 Bucket: $S3_BUCKET"
echo "  S3 Key: $S3_KEY"
echo "  Maintenance Mode: $MAINTENANCE_MODE"
echo ""

# 依存関係をインストール
echo "依存関係をインストール中..."
pip install -r requirements.txt -t ./package/

# Lambda関数ファイルをパッケージにコピー
echo "Lambda関数をパッケージング中..."
cp lambda_handler.py ./package/

# ZIPファイルを作成
cd package
zip -r ../lambda_function.zip .
cd ..

echo "ZIPファイル作成完了: lambda_function.zip"

# Lambda関数が存在するかチェック
if aws lambda get-function --function-name $FUNCTION_NAME 2>/dev/null; then
    echo "既存のLambda関数を更新中..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://lambda_function.zip
    
    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --handler $HANDLER \
        --environment Variables="{MAINTENANCE_MODE=$MAINTENANCE_MODE,S3_BUCKET=$S3_BUCKET,S3_KEY=$S3_KEY,SPECIAL_URL_PATH=/special,SPECIAL_LAMBDA_ARN=}"
else
    echo "新しいLambda関数を作成中..."
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --role $ROLE_ARN \
        --handler $HANDLER \
        --zip-file fileb://lambda_function.zip \
        --timeout 30 \
        --memory-size 256 \
        --environment Variables="{MAINTENANCE_MODE=$MAINTENANCE_MODE,S3_BUCKET=$S3_BUCKET,S3_KEY=$S3_KEY,SPECIAL_URL_PATH=/special,SPECIAL_LAMBDA_ARN=}"
fi

# クリーンアップ
echo "クリーンアップ中..."
rm -rf package
rm lambda_function.zip

echo ""
echo "デプロイ完了！"
echo "Lambda関数名: $FUNCTION_NAME"
