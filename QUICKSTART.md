# Quick Start Guide

## 概要 (Overview)

このガイドでは、Lambda Maintenance Handlerを素早くセットアップして使用する方法を説明します。

## 前提条件 (Prerequisites)

- AWSアカウント
- AWS CLI設定済み
- Python 3.13環境
- S3バケット

## セットアップ手順 (Setup Steps)

### 1. S3バケットの作成と準備

```bash
# S3バケットの作成
aws s3 mb s3://your-maintenance-bucket

# メンテナンス画面のアップロード
aws s3 cp maintenance.html s3://your-maintenance-bucket/maintenance.html
```

### 2. IAMロールの作成

```bash
# ロールポリシーの作成
aws iam create-role \
  --role-name lambda-maintenance-handler-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "Service": "lambda.amazonaws.com"
        },
        "Action": "sts:AssumeRole"
      }
    ]
  }'

# ポリシーのアタッチ
aws iam put-role-policy \
  --role-name lambda-maintenance-handler-role \
  --policy-name lambda-maintenance-handler-policy \
  --policy-document file://iam-policy.json
```

### 3. Lambda関数のデプロイ

#### オプション A: AWS SAMを使用

```bash
# 初回デプロイ
sam build
sam deploy --guided

# 以降のデプロイ
sam build && sam deploy
```

#### オプション B: デプロイスクリプトを使用

```bash
# 環境変数を設定
export LAMBDA_ROLE_ARN="arn:aws:iam::YOUR_ACCOUNT_ID:role/lambda-maintenance-handler-role"
export S3_BUCKET="your-maintenance-bucket"
export S3_KEY="maintenance.html"
export MAINTENANCE_MODE="true"

# デプロイ実行
./deploy.sh
```

### 4. ALBとの統合

```bash
# Lambda関数をALBターゲットとして追加
aws elbv2 create-target-group \
  --name maintenance-handler-tg \
  --target-type lambda \
  --protocol HTTP

# Lambda関数を登録
aws elbv2 register-targets \
  --target-group-arn YOUR_TARGET_GROUP_ARN \
  --targets Id=arn:aws:lambda:REGION:ACCOUNT:function:maintenance-handler

# ALBルールの作成
aws elbv2 create-rule \
  --listener-arn YOUR_LISTENER_ARN \
  --conditions Field=path-pattern,Values='/*' \
  --priority 1 \
  --actions Type=forward,TargetGroupArn=YOUR_TARGET_GROUP_ARN
```

## 使用例 (Usage Examples)

### 例1: メンテナンスモードの有効化

```bash
aws lambda update-function-configuration \
  --function-name maintenance-handler \
  --environment Variables="{
    MAINTENANCE_MODE=true,
    S3_BUCKET=your-maintenance-bucket,
    S3_KEY=maintenance.html
  }"
```

### 例2: メンテナンスモードの無効化

```bash
aws lambda update-function-configuration \
  --function-name maintenance-handler \
  --environment Variables="{
    MAINTENANCE_MODE=false,
    S3_BUCKET=your-maintenance-bucket,
    S3_KEY=maintenance.html
  }"
```

### 例3: 特別なURLの設定

```bash
# 別のLambda関数を作成（例: 健康診断用）
aws lambda create-function \
  --function-name health-check-handler \
  --runtime python3.13 \
  --role YOUR_ROLE_ARN \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://health-check.zip

# メンテナンスハンドラに特別URLを設定
aws lambda update-function-configuration \
  --function-name maintenance-handler \
  --environment Variables="{
    MAINTENANCE_MODE=true,
    S3_BUCKET=your-maintenance-bucket,
    S3_KEY=maintenance.html,
    SPECIAL_URL_PATH=/health,
    SPECIAL_LAMBDA_ARN=arn:aws:lambda:REGION:ACCOUNT:function:health-check-handler
  }"
```

## テスト (Testing)

### ローカルテスト

```bash
# 依存関係のインストール
pip install -r requirements-dev.txt

# テスト実行
pytest test_lambda_handler.py -v
```

### Lambda関数のテスト

```bash
# テストイベントの作成
cat > test-event.json << 'EOF'
{
  "path": "/test",
  "httpMethod": "GET",
  "headers": {
    "host": "example.com",
    "user-agent": "Test-Agent/1.0"
  },
  "requestContext": {
    "identity": {
      "sourceIp": "192.168.1.1"
    }
  }
}
EOF

# Lambda関数の呼び出し
aws lambda invoke \
  --function-name maintenance-handler \
  --payload file://test-event.json \
  response.json

# レスポンスの確認
cat response.json
```

## トラブルシューティング (Troubleshooting)

### Lambda関数のログ確認

```bash
# CloudWatch Logsでログを確認
aws logs tail /aws/lambda/maintenance-handler --follow
```

### S3アクセスエラー

```bash
# Lambda関数のIAMロールを確認
aws iam get-role --role-name lambda-maintenance-handler-role

# S3バケットのアクセス権限を確認
aws s3api get-bucket-policy --bucket your-maintenance-bucket
```

### Lambda呼び出しエラー

```bash
# Lambda関数の詳細を確認
aws lambda get-function --function-name maintenance-handler

# 環境変数の確認
aws lambda get-function-configuration --function-name maintenance-handler
```

## パフォーマンス最適化 (Performance Optimization)

### Lambda関数の設定

```bash
# メモリとタイムアウトの調整
aws lambda update-function-configuration \
  --function-name maintenance-handler \
  --memory-size 512 \
  --timeout 30
```

### プロビジョニング済み同時実行数

```bash
# プロビジョニング済み同時実行数の設定
aws lambda put-provisioned-concurrency-config \
  --function-name maintenance-handler \
  --provisioned-concurrent-executions 5 \
  --qualifier $LATEST
```

## コスト管理 (Cost Management)

- Lambda呼び出し回数を監視
- CloudWatch Logsの保持期間を適切に設定
- S3ライフサイクルポリシーの活用

## セキュリティベストプラクティス (Security Best Practices)

1. IAMロールは最小権限の原則に従う
2. S3バケットのバケットポリシーで適切なアクセス制御
3. Lambda関数のVPC内配置（必要に応じて）
4. 環境変数に機密情報を含めない（AWS Secrets Managerを使用）

## サポート (Support)

問題が発生した場合は、GitHubのIssueを作成してください：
https://github.com/kakusyoukai/sarue_ukimafunado/issues
