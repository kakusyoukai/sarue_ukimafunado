# Lambda Maintenance Handler (sarue_ukimafunado)

ALB（Application Load Balancer）からのリクエストを処理し、メンテナンス中はS3から取得したメンテナンス画面を返すLambda関数です。

## 機能

1. **ALBリクエスト処理**: Application Load Balancerからのリクエストを受け取り処理します
2. **メンテナンスモード**: メンテナンス中は、S3からメンテナンス画面を取得して返します
3. **パラメータ置換**: メンテナンス画面内のプレースホルダーをALBイベントやコンテキストの値で置き換えます
4. **特別URL処理**: 特定のURLパスにアクセスされた場合、別のLambda関数を呼び出して特別な処理を実施します

## 必要要件

- Python 3.13
- AWS Lambda
- AWS S3 (メンテナンス画面の保存用)
- boto3

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

Lambda関数には以下の環境変数を設定してください：

| 変数名 | 説明 | デフォルト値 |
|--------|------|-------------|
| `MAINTENANCE_MODE` | メンテナンスモードの有効/無効 (`true`/`false`) | `true` |
| `S3_BUCKET` | メンテナンス画面を格納するS3バケット名 | `maintenance-pages` |
| `S3_KEY` | メンテナンス画面のS3キー（ファイルパス） | `maintenance.html` |
| `SPECIAL_URL_PATH` | 特別な処理を行うURLパスのプレフィックス | `/special` |
| `SPECIAL_LAMBDA_ARN` | 特別な処理を行うLambda関数のARN | `""` (空文字列) |

### 3. S3バケットの準備

メンテナンス画面HTMLファイルをS3にアップロードしてください：

```bash
aws s3 cp maintenance.html s3://your-bucket-name/maintenance.html
```

### 4. Lambda関数の作成

#### AWS CLIを使用する場合

```bash
# Lambda関数用のZIPファイルを作成
zip -r lambda_function.zip lambda_handler.py

# Lambda関数を作成
aws lambda create-function \
  --function-name maintenance-handler \
  --runtime python3.13 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/lambda-execution-role \
  --handler lambda_handler.lambda_handler \
  --zip-file fileb://lambda_function.zip \
  --environment Variables="{MAINTENANCE_MODE=true,S3_BUCKET=your-bucket,S3_KEY=maintenance.html}"
```

#### AWS SAMを使用する場合

`template.yaml`を作成して、SAM CLIでデプロイします。

### 5. IAMロールの設定

Lambda実行ロールには以下の権限が必要です：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::your-bucket-name/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": "arn:aws:lambda:REGION:ACCOUNT_ID:function:special-function-name"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

## メンテナンス画面のカスタマイズ

メンテナンス画面（HTMLファイル）には以下のプレースホルダーを使用できます：

| プレースホルダー | 説明 |
|----------------|------|
| `{{REQUEST_ID}}` | Lambda リクエストID |
| `{{TIMESTAMP}}` | 現在のタイムスタンプ（ISO 8601形式） |
| `{{PATH}}` | リクエストパス |
| `{{METHOD}}` | HTTPメソッド |
| `{{SOURCE_IP}}` | 送信元IPアドレス |
| `{{USER_AGENT}}` | ユーザーエージェント文字列 |
| `{{HOST}}` | ホストヘッダー |
| `{{FUNCTION_NAME}}` | Lambda関数名 |

例：
```html
<p>リクエストID: {{REQUEST_ID}}</p>
<p>アクセス時刻: {{TIMESTAMP}}</p>
```

## 使用方法

### メンテナンスモードの切り替え

```bash
# メンテナンスモードを有効化
aws lambda update-function-configuration \
  --function-name maintenance-handler \
  --environment Variables="{MAINTENANCE_MODE=true,S3_BUCKET=your-bucket,S3_KEY=maintenance.html}"

# メンテナンスモードを無効化
aws lambda update-function-configuration \
  --function-name maintenance-handler \
  --environment Variables="{MAINTENANCE_MODE=false,S3_BUCKET=your-bucket,S3_KEY=maintenance.html}"
```

### 特別なURLの設定

特定のURLパスで別のLambda関数を呼び出す場合：

```bash
aws lambda update-function-configuration \
  --function-name maintenance-handler \
  --environment Variables="{MAINTENANCE_MODE=true,S3_BUCKET=your-bucket,S3_KEY=maintenance.html,SPECIAL_URL_PATH=/special,SPECIAL_LAMBDA_ARN=arn:aws:lambda:REGION:ACCOUNT:function:special-handler}"
```

これにより、`/special`で始まるパスにアクセスすると、指定されたLambda関数が呼び出されます。

## テスト

ユニットテストを実行するには：

```bash
# テスト用の依存関係をインストール
pip install -r requirements-dev.txt

# テストを実行
pytest test_lambda_handler.py -v
```

## ALBとの統合

ALB（Application Load Balancer）でこのLambda関数をターゲットとして設定してください：

1. ALBのターゲットグループを作成（ターゲットタイプ: Lambda）
2. このLambda関数をターゲットとして登録
3. ALBリスナールールで、適切なパスパターンまたは条件でこのターゲットグループにルーティング

## アーキテクチャ

```
Internet
    ↓
Application Load Balancer (ALB)
    ↓
Lambda Function (この関数)
    ↓
    ├── メンテナンスモード時 → S3からメンテナンス画面取得
    ├── 特別URL時 → 別のLambda関数を呼び出し
    └── 通常時 → 通常レスポンス
```

## ファイル構成

- `lambda_handler.py`: メインのLambda関数コード
- `maintenance.html`: メンテナンス画面のサンプルHTMLテンプレート
- `requirements.txt`: 本番環境用の依存関係
- `requirements-dev.txt`: 開発・テスト用の依存関係
- `test_lambda_handler.py`: ユニットテスト

## トラブルシューティング

### S3からメンテナンス画面を取得できない場合

Lambda関数は自動的にフォールバックのメンテナンス画面を返します。以下を確認してください：

- S3バケット名とキーが正しく設定されているか
- Lambda実行ロールにS3読み取り権限があるか
- S3バケットとLambda関数が同じリージョンにあるか

### 特別Lambda関数を呼び出せない場合

- `SPECIAL_LAMBDA_ARN`が正しく設定されているか
- Lambda実行ロールに対象Lambda関数の呼び出し権限があるか
- 対象Lambda関数が存在し、アクティブであるか

## サポート

問題が発生した場合は、GitHubのIssueを作成してください。