# app/tests/test_helloworld.py
import pytest
import subprocess

def test_helloworld_output():
    """Test that HelloWorld prints 'Hello, World!' without errors."""
    try:
        result = subprocess.run(['python', '../helloworld.py'], capture_output=True, text=True)
        assert "Hello, World!" in result.stdout
        assert result.stderr == ""  # No errors
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Test failed with error: {e.stderr}")