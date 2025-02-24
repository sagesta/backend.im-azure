from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.responses import FileResponse
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient
import os
import json
import requests

app = FastAPI()

# Azure Configuration
vault_url = os.environ.get('KEY_VAULT_URL', 'https://your-key-vault.vault.azure.net/')
storage_account_url = os.environ.get('STORAGE_ACCOUNT_URL', 'https://your-storage-account.blob.core.windows.net')
container_name = 'backend-artifacts'

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
    
    # Upload to Azure Blob Storage
    blob_client = blob_service_client.get_blob_client(container=container_name, blob='helloworld.py')
    with open(file_path, 'rb') as data:
        blob_client.upload_blob(data)
    
    # Trigger deployment and testing in AKS
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

@app.get('/api/get-fixed-helloworld')
async def get_fixed_helloworld():
    """Return the corrected HelloWorld script."""
    fixed_file_path = os.path.join('app', 'helloworld_fixed.py')
    return FileResponse(fixed_file_path, filename='helloworld_fixed.py', media_type='application/octet-stream')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)