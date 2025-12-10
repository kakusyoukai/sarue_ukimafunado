# Example ALB Events

このディレクトリには、Lambda関数のテストに使用できるALBイベントのサンプルが含まれています。

## ファイル一覧

### 1. alb-event-normal.json
通常のHTTPリクエスト（メンテナンスモードでの動作確認用）

**使用方法:**
```bash
aws lambda invoke \
  --function-name maintenance-handler \
  --payload file://examples/alb-event-normal.json \
  response.json
```

### 2. alb-event-special-url.json
特別なURL（/special）へのリクエスト（別Lambda関数呼び出しのテスト用）

**使用方法:**
```bash
aws lambda invoke \
  --function-name maintenance-handler \
  --payload file://examples/alb-event-special-url.json \
  response.json
```

### 3. alb-event-api-request.json
API POST リクエスト（通常動作モードのテスト用）

**使用方法:**
```bash
aws lambda invoke \
  --function-name maintenance-handler \
  --payload file://examples/alb-event-api-request.json \
  response.json
```

## ローカルテスト

Python環境で直接テストすることもできます：

```python
import json
from lambda_handler import lambda_handler

class MockContext:
    request_id = 'test-request-123'
    function_name = 'test-function'
    function_version = '1'
    memory_limit_in_mb = 128

# イベントの読み込み
with open('examples/alb-event-normal.json', 'r') as f:
    event = json.load(f)

# Lambda関数の実行
context = MockContext()
response = lambda_handler(event, context)

print(json.dumps(response, indent=2, ensure_ascii=False))
```
