# scripts/test_runner.py
import pytest
import os
import json
from kubernetes import client, config

def run_tests(namespace):
    """Run tests in the specified Kubernetes namespace."""
    config.load_kube_config()
    v1 = client.CoreV1Api()

    # Locate test pod logs
    pod_list = v1.list_namespaced_pod(namespace=namespace)
    test_pod = next(p for p in pod_list.items if p.metadata.name == "helloworld-test-pod")
    log = v1.read_namespaced_pod_log(name=test_pod.metadata.name, namespace=namespace)

    # Parse test results (simplified)
    if "PASSED" in log or "Hello, World!" in log:
        return {"status": "success", "details": log}
    return {"status": "failure", "details": log}

if __name__ == "__main__":
    import sys
    namespace = sys.argv[1]
    result = run_tests(namespace)
    print(json.dumps(result))