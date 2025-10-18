import requests

API_URL = "https://api-inference.huggingface.co/models/BAAI/bge-small-en-v1.5"
headers = {"Authorization": "Bearer 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"}

data = {"inputs": ["This is a sample text to embed."]}

response = requests.post(API_URL, headers=headers, json=data)
print(response.status_code)
print(response.json())
