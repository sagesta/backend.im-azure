import requests
import os

# Upload faulty helloworld.py
url = 'http://localhost:5000/api/deploy-helloworld'
with open('app/helloworld.py', 'rb') as f:
    files = {'file': f}
    response = requests.post(url, files=files)
    print("Deployment response:", response.json())

# Get fixed helloworld.py
fixed_url = 'http://localhost:5000/api/get-fixed-helloworld'
response = requests.get(fixed_url)
with open('helloworld_fixed_received.py', 'wb') as f:
    f.write(response.content)
print("Received fixed HelloWorld script")