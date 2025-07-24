import pytest
import docker
import requests
import time
import json

class TestDockerContainers:
    
    @classmethod
    def setup_class(cls):
        """Set up Docker client"""
        cls.client = docker.from_env()
    
    def test_application_container_build(self):
        """Test that application container builds successfully"""
        try:
            # Build the container
            image, logs = self.client.images.build(
                path="../../app",
                tag="chatbot-test:latest",
                rm=True
            )
            
            # Verify image was created
            assert image is not None
            assert len(image.tags) > 0
            
            print("Container built successfully")
            
        except docker.errors.BuildError as e:
            pytest.fail(f"Container build failed: {e}")
    
    def test_container_startup_and_health(self):
        """Test container startup and health check"""
        # Build container first
        image, _ = self.client.images.build(
            path="../../app",
            tag="chatbot-test:latest",
            rm=True
        )
        
        # Start container with test database
        db_container = self.client.containers.run(
            "postgres:14",
            environment={
                "POSTGRES_DB": "test_container",
                "POSTGRES_USER": "test_user", 
                "POSTGRES_PASSWORD": "test_password"
            },
            detach=True,
            remove=True,
            name="test-db"
        )
        
        time.sleep(10)  # Wait for DB to start
        
        # Start application container
        app_container = self.client.containers.run(
            "chatbot-test:latest",
            environment={
                "DB_HOST": "test-db",
                "DB_PORT": "5432",
                "DB_NAME": "test_container",
                "DB_USERNAME": "test_user",
                "DB_PASSWORD": "test_password"
            },
            ports={'8000/tcp': 8001},
            links={'test-db': 'test-db'},
            detach=True,
            remove=True
        )
        
        # Wait for application to start
        time.sleep(15)
        
        try:
            # Test health endpoint
            response = requests.get("http://localhost:8001/health", timeout=10)
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database"] == "connected"
            
            # Test basic functionality
            chat_response = requests.post(
                "http://localhost:8001/chat",
                json={"content": "Test message"},
                timeout=10
            )
            assert chat_response.status_code == 200
            
            print("Container health check passed")
            
        finally:
            # Clean up containers
            app_container.stop()
            db_container.stop()
    
    def test_container_resource_limits(self):
        """Test container resource usage"""
        # Build container
        image, _ = self.client.images.build(
            path="../../app",
            tag="chatbot-resource-test:latest",
            rm=True
        )
        
        # Start with resource limits
        container = self.client.containers.run(
            "chatbot-resource-test:latest",
            environment={
                "DB_HOST": "localhost",
                "DB_PORT": "5432",
                "DB_NAME": "test",
                "DB_USERNAME": "test",
                "DB_PASSWORD": "test"
            },
            mem_limit="256m",  # 256MB memory limit
            cpu_period=100000,
            cpu_quota=50000,   # 50% CPU limit
            detach=True,
            remove=True
        )
        
        time.sleep(10)
        
        try:
            # Check container stats
            stats = container.stats(stream=False)
            
            # Verify memory usage is within limits
            memory_usage = stats['memory_stats']['usage']
            memory_limit = stats['memory_stats']['limit']
            
            assert memory_usage < memory_limit, "Memory usage exceeds limit"
            
            # Test that container is still responsive
            container.reload()
            assert container.status == "running"
            
            print(f"Container memory usage: {memory_usage / 1024 / 1024:.2f} MB")
            
        finally:
            container.stop()
    
    def test_container_environment_variables(self):
        """Test container environment variable handling"""
        # Test with missing environment variables
        container = self.client.containers.run(
            "postgres:14",  # Use postgres as test container
            environment={},  # No environment variables
            detach=True,
            remove=True
        )
        
        time.sleep(5)
        
        try:
            # Container should fail to start properly without required env vars
            container.reload()
            logs = container.logs().decode('utf-8')
            
            # PostgreSQL should show errors about missing configuration
            assert "database system is ready" not in logs or "FATAL" in logs
            
        finally:
            container.stop()
    
    def test_container_networking(self):
        """Test container networking configuration"""
        # Create a custom network
        network = self.client.networks.create("test-network")
        
        try:
            # Start database container on custom network
            db_container = self.client.containers.run(
                "postgres:14",
                environment={
                    "POSTGRES_DB": "test_network",
                    "POSTGRES_USER": "test_user",
                    "POSTGRES_PASSWORD": "test_password"
                },
                network="test-network",
                name="test-network-db",
                detach=True,
                remove=True
            )
            
            time.sleep(10)
            
            # Start application container on same network
            app_container = self.client.containers.run(
                "alpine:latest",
                command="ping -c 3 test-network-db",
                network="test-network",
                detach=True,
                remove=True
            )
            
            # Wait for ping to complete
            app_container.wait()
            
            # Check ping results
            logs = app_container.logs().decode('utf-8')
            assert "3 packets transmitted, 3 received" in logs or "3 packets transmitted, 3 packets received" in logs
            
            print("Container networking test passed")
            
        finally:
            # Clean up
            db_container.stop()
            network.remove()