"""测试 Ollama 服务状态"""
import requests

try:
    response = requests.get('http://localhost:11434/api/tags', timeout=10)
    print('Ollama Status: OK')
    print('Models:')
    for m in response.json().get('models', []):
        print('  - ' + m.get('name'))
except Exception as e:
    print('Ollama Status: ERROR - ' + str(e))
