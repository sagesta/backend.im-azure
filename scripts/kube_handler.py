# scripts/kube_handler.py
from kubernetes import client, config
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import os
import time
import json
import requests

def trigger_deployment(script_name):
    """Trigger deployment and testing of HelloWorld in AKS from Gitea."""
    # Load Kubernetes config (assuming cluster access is configured)
    config.load_kube_config()
    v1 = client.CoreV1Api()
    apps_v1 = client.AppsV1Api()

    # Get AKS and Gitea configuration from Key Vault
    config_data = get_config_from_keyvault()
    namespace = f"helloworld-{os.urandom(8).hex()}"  # Dynamic namespace

    # Create namespace
    try:
        v1.create_namespace(body=client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace)))
    except client.ApiException:
        pass  # Namespace already exists

    # Pull script from Gitea repository
    gitea_host = config_data['gitea_host']
    gitea_repo = f"{gitea_host}/org/backend-im/raw/main/{script_name}"
    response = requests.get(gitea_repo, auth=('user', 'token'))  # Replace with Gitea credentials
    if response.status_code != 200:
        return {"status": "failure", "details": f"Failed to fetch script from Gitea: {response.text}"}

    # Save script temporarily
    script_path = os.path.join('/tmp', script_name)
    with open(script_path, 'wb') as f:
        f.write(response.content)

    # Deploy test pod with HelloWorld script
    pod_manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": "helloworld-test-pod", "namespace": namespace},
        "spec": {
            "containers": [{
                "name": "helloworld-container",
                "image": "python:3.12-slim",
                "command": ["python", f"/app/{script_name}"],
                "volumeMounts": [{
                    "name": "shared-data",
                    "mountPath": "/app"
                }],
                "livenessProbe": {
                    "httpGet": {"path": "/api/health", "port": 5000},
                    "initialDelaySeconds": 30,
                    "periodSeconds": 10
                },
                "readinessProbe": {
                    "httpGet": {"path": "/api/health", "port": 5000},
                    "initialDelaySeconds": 5,
                    "periodSeconds": 5
                }
            }],
            "volumes": [{
                "name": "shared-data",
                "emptyDir": {}
            }]
        }
    }
    v1.create_namespaced_pod(body=pod_manifest, namespace=namespace)

    # Wait for pod to start and retrieve logs
    time.sleep(10)  # Wait for pod to initialize
    try:
        log = v1.read_namespaced_pod_log(name="helloworld-test-pod", namespace=namespace)
        if "NameError: name 'undefined_variable' is not defined" in log:
            return {"status": "failure", "details": "Script contains an undefined variable 'undefined_variable'"}
        return {"status": "success", "details": log}
    except Exception as e:
        return {"status": "failure", "details": str(e)}

def deploy_to_production(script_name, namespace="production"):
    """Deploy corrected script to production in AKS."""
    config.load_kube_config()
    v1 = client.CoreV1Api()
    apps_v1 = client.AppsV1Api()

    # Create or use production namespace
    try:
        v1.create_namespace(body=client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace)))
    except client.ApiException:
        pass  # Namespace already exists

    # Pull corrected script from Gitea
    config_data = get_config_from_keyvault()
    gitea_host = config_data['gitea_host']
    gitea_repo = f"{gitea_host}/org/backend-im/raw/main/{script_name}"
    response = requests.get(gitea_repo, auth=('user', 'token'))  # Replace with Gitea credentials
    if response.status_code != 200:
        return {"status": "failure", "details": f"Failed to fetch script from Gitea: {response.text}"}

    script_path = os.path.join('/tmp', script_name)
    with open(script_path, 'wb') as f:
        f.write(response.content)

    # Deploy as a Kubernetes Deployment
    deployment_manifest = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "helloworld-prod", "namespace": namespace},
        "spec": {
            "replicas": 2,  # Ensure scalability
            "selector": {"matchLabels": {"app": "helloworld"}},
            "template": {
                "metadata": {"labels": {"app": "helloworld"}},
                "spec": {
                    "containers": [{
                        "name": "helloworld-container",
                        "image": "bkimcr25x7z.azurecr.io/backend-im:latest",
                        "command": ["python", f"/app/{script_name}"],
                        "volumeMounts": [{
                            "name": "shared-data",
                            "mountPath": "/app"
                        }],
                        "livenessProbe": {
                            "httpGet": {"path": "/api/health", "port": 5000},
                            "initialDelaySeconds": 30,
                            "periodSeconds": 10
                        },
                        "readinessProbe": {
                            "httpGet": {"path": "/api/health", "port": 5000},
                            "initialDelaySeconds": 5,
                            "periodSeconds": 5
                        }
                    }],
                    "volumes": [{
                        "name": "shared-data",
                        "emptyDir": {}
                    }]
                }
            }
        }
    }
    apps_v1.create_namespaced_deployment(body=deployment_manifest, namespace=namespace)

    # Create a Service for external access
    service_manifest = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": "helloworld-service", "namespace": namespace},
        "spec": {
            "selector": {"app": "helloworld"},
            "ports": [{"port": 80, "targetPort": 5000}],
            "type": "LoadBalancer"
        }
    }
    v1.create_namespaced_service(body=service_manifest, namespace=namespace)

    # Configure HorizontalPodAutoscaler
    autoscaling_v1 = client.AutoscalingV1Api()
    hpa_manifest = {
        "apiVersion": "autoscaling/v1",
        "kind": "HorizontalPodAutoscaler",
        "metadata": {"name": "helloworld-hpa", "namespace": namespace},
        "spec": {
            "scaleTargetRef": {"apiVersion": "apps/v1", "kind": "Deployment", "name": "helloworld-prod"},
            "minReplicas": 1,
            "maxReplicas": 5,
            "targetCPUUtilizationPercentage": 70
        }
    }
    autoscaling_v1.create_namespaced_horizontal_pod_autoscaler(body=hpa_manifest, namespace=namespace)

def get_config_from_keyvault():
    """Fetch AKS and Gitea configuration from Azure Key Vault."""
    vault_url = os.environ.get('KEY_VAULT_URL', 'https://bkimkv25x7z.vault.azure.net/')
    credential = get_azure_credentials()
    secret_client = SecretClient(vault_url=vault_url, credential=credential)
    
    config = {
        'aks_cluster_name': secret_client.get_secret('AKS-CLUSTER-NAME').value,
        'aks_resource_group': secret_client.get_secret('AKS-RESOURCE-GROUP').value,
        'gitea_host': secret_client.get_secret('GITEA_HOST').value
    }
    return config

def get_azure_credentials():
    """Retrieve Azure credentials using DefaultAzureCredential."""
    from azure_auth import get_azure_credentials  # Circular import handled here
    return get_azure_credentials()