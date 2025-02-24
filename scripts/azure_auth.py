# scripts/azure_auth.py
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import os

def get_azure_credentials():
    """Retrieve Azure credentials using DefaultAzureCredential."""
    credential = DefaultAzureCredential()
    return credential

def get_config_from_keyvault():
    """Fetch configuration from Azure Key Vault."""
    vault_url = os.environ.get('KEY_VAULT_URL', 'https://bkimkv25x7z.vault.azure.net/')
    credential = get_azure_credentials()
    secret_client = SecretClient(vault_url=vault_url, credential=credential)
    
    config = {
        'storage_account_url': secret_client.get_secret('STORAGE-ACCOUNT-URL').value,
        'aks_cluster_name': secret_client.get_secret('AKS-CLUSTER-NAME').value,
        'aks_resource_group': secret_client.get_secret('AKS-RESOURCE-GROUP').value,
        'gitea_host': secret_client.get_secret('GITEA_HOST').value  # New Gitea configuration
    }
    return config