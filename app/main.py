# app/main.py
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.responses import FileResponse
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient
import os
import json
import requests
import git  # For interacting with Gitea repository (optional, for local testing)

app = FastAPI()

# Azure Configuration
vault_url = os.environ.get('KEY_VAULT_URL', 'https://bkimkv25x7z.vault.azure.net/')
storage_account_url = os.environ.get('STORAGE_ACCOUNT_URL', 'https://bkimst25x7z.blob.core.windows.net')
container_name = 'backend-artifacts'
gitea_repo_url = os.environ.get('GITEA_REPO_URL', 'http://gitea-host:3000/org/backend-im')  # Replace with your Gitea URL

# Initialize Azure clients
credential = DefaultAzureCredential()
secret_client = SecretClient(vault_url=vault_url, credential=credential)
blob_service_client = BlobServiceClient(account_url=storage_account_url, credential=credential)

@app.get('/api/health')
async def health_check():
    """Health check endpoint for the service."""
    return {"status": "healthy", "message": "Backend is running"}

@app.post('/api/deploy-helloworld')
async def deploy_helloworld(file: UploadFile = File(...)):
    """Deploy, test, and handle HelloWorld script with error, then return fixed version."""
    if file.filename != 'helloworld.py':
        raise HTTPException(status_code=400, detail="File must be named helloworld.py")
    
    # Save the uploaded file temporarily
    file_path = os.path.join('/tmp', 'helloworld.py')
    with open(file_path, 'wb') as f:
        f.write(await file.read())
    
    # Optionally commit to Gitea repository for version control
    try:
        repo = git.Repo.init('/tmp')
        repo.index.add(['helloworld.py'])
        repo.index.commit('Update HelloWorld script')
        repo.remote('origin').push()
    except Exception as e:
        print(f"Warning: Could not push to Gitea: {e}")

    # Upload to Azure Blob Storage
    blob_client = blob_service_client.get_blob_client(container=container_name, blob='helloworld.py')
    with open(file_path, 'rb') as data:
        blob_client.upload_blob(data)
    
    # Trigger deployment and testing in AKS via Gitea webhook or direct call
    from scripts.kube_handler import trigger_deployment
    test_result = trigger_deployment('helloworld.py')
    
    if test_result.get('status') == 'failure':
        # Return the error details
        return {
            "status": "error",
            "message": "Test failed",
            "error_details": test_result.get('details', 'Unknown error'),
            "fix": "Here's the corrected version:"
        }, status.HTTP_500_INTERNAL_SERVER_ERROR
    
    return {"status": "success", "message": "HelloWorld deployed successfully"}, status.HTTP_200_OK

@app.post('/api/gitea-webhook')  # Endpoint for Gitea webhook
async def handle_gitea_webhook(payload: dict = None):
    """Handle webhook from Gitea to trigger deployment."""
    if not payload or 'ref' not in payload or 'repository' not in payload:
        raise HTTPException(status_code=400, detail="Invalid Gitea webhook payload")
    
    if payload['ref'] == 'refs/heads/main':
        # Trigger deployment for main branch push
        from scripts.kube_handler import trigger_deployment
        test_result = trigger_deployment('helloworld.py')
        return {"status": "triggered", "result": test_result}
    
    return {"status": "ignored", "message": "Not a main branch push"}

@app.get('/api/get-fixed-helloworld')
async def get_fixed_helloworld():
    """Return the corrected HelloWorld script."""
    fixed_file_path = os.path.join('app', 'helloworld_fixed.py')
    return FileResponse(fixed_file_path, filename='helloworld_fixed.py', media_type='application/octet-stream')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)