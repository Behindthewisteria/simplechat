# lambda/index.py
import json
import os
import re
import urllib.request  # 標準ライブラリの urllib.request を使用
from botocore.exceptions import ClientError


# Lambda コンテキストからリージョンを抽出する関数
def extract_region_from_arn(arn):
    # ARN 形式: arn:aws:lambda:region:account-id:function:function-name
    match = re.search('arn:aws:lambda:([^:]+):', arn)
    if match:
        return match.group(1)
    return "us-east-1"  # デフォルト値

# 外部APIを呼び出す関数
def call_external_api(api_url, data=None, headers=None):
    try:
        # リクエストの準備
        if data:
            data = json.dumps(data).encode('utf-8')
        
        # リクエストオブジェクトの作成
        request = urllib.request.Request(
            url=api_url,
            data=data,
            headers=headers or {"Content-Type": "application/json"}
        )
        
        # APIの呼び出し
        with urllib.request.urlopen(request) as response:
            response_data = response.read().decode('utf-8')
            return json.loads(response_data)
    except Exception as e:
        print(f"外部API呼び出しエラー: {str(e)}")
        return {"error": str(e)}

def lambda_handler(event, context):
    try:
        # リージョン情報を取得（設定のため保持）
        region = extract_region_from_arn(context.invoked_function_arn)
        print(f"Lambda executing in region: {region}")
        
        print("Received event:", json.dumps(event))
        
        # Cognitoで認証されたユーザー情報を取得
        user_info = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            user_info = event['requestContext']['authorizer']['claims']
            print(f"Authenticated user: {user_info.get('email') or user_info.get('cognito:username')}")
        
        # リクエストボディの解析
        body = json.loads(event['body'])
        message = body['message']
        conversation_history = body.get('conversationHistory', [])
        
        # 外部APIの設定を取得
        api_url = body.get('https://3c49-35-185-90-217.ngrok-free.app/')
        api_data = body.get('apiData', {})
        api_headers = body.get('apiHeaders', {})
        
        if not api_url:
            raise Exception("API URL is required")
            
        print(f"Calling external API: {api_url}")
        
        # ユーザーメッセージを追加
        messages = conversation_history.copy()
        messages.append({
            "role": "user",
            "content": message
        })
        
        # 外部APIに渡すデータを準備
        if api_data is None:
            api_data = {}
        
        # 会話履歴とメッセージをAPIデータに追加
        api_data.update({
            "messages": [{"role": msg["role"], "content": msg["content"]} for msg in messages],
            "user_info": user_info
        })
        
        # 外部APIを呼び出し
        api_response = call_external_api(api_url, api_data, api_headers)
        
        # APIレスポンスからアシスタント応答を抽出
        if "error" in api_response:
            raise Exception(f"External API error: {api_response['error']}")
        
        # APIレスポンスの形式に応じて処理
        assistant_response = ""
        if isinstance(api_response, dict):
            # レスポンスが辞書形式の場合
            assistant_response = api_response.get("response", 
                               api_response.get("message", 
                               api_response.get("content", 
                               api_response.get("text", 
                               str(api_response)))))
        else:
            # 文字列またはその他の形式の場合
            assistant_response = str(api_response)
        
        # アシスタントの応答を会話履歴に追加
        messages.append({
            "role": "assistant",
            "content": assistant_response
        })
        
        # 成功レスポンスの返却
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": True,
                "response": assistant_response,
                "conversationHistory": messages
            })
        }
        
    except Exception as error:
        print("Error:", str(error))
        
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": False,
                "error": str(error)
            })
        }