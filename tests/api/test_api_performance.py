import pytest
import time
import threading
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
from unittest.mock import patch
import docker
import sys
sys.path.append('../../app')

class TestAPIPerformance:
    
    @classmethod
    def setup_class(cls):
        """Set up test environment"""
        cls.client = docker.from_env()
        
        # Start test database
        cls.db_container = cls.client.containers.run(
            "postgres:14",
            environment={
                "POSTGRES_DB": "test_perf",
                "POSTGRES_USER": "test_user",
                "POSTGRES_PASSWORD": "test_password"
            },
            ports={'5432/tcp': 5437},
            detach=True,
            remove=True
        )
        
        time.sleep(10)
        
        cls.env_vars = {
            'DB_HOST': 'localhost',
            'DB_PORT': '5437',
            'DB_NAME': 'test_perf',
            'DB_USERNAME': 'test_user',
            'DB_PASSWORD': 'test_password'
        }
    
    @classmethod
    def teardown_class(cls):
        """Clean up"""
        cls.db_container.stop()
    
    def test_response_time_benchmarks(self):
        """Test API response time benchmarks"""
        with patch.dict('os.environ', self.env_vars):
            from main import app
            
            client = TestClient(app)
            
            # Warm up
            for _ in range(5):
                client.get("/health")
            
            # Test health endpoint performance
            health_times = []
            for _ in range(100):
                start = time.time()
                response = client.get("/health")
                end = time.time()
                
                assert response.status_code == 200
                health_times.append(end - start)
            
            # Test chat endpoint performance
            chat_times = []
            for i in range(50):
                start = time.time()
                response = client.post("/chat", json={"content": f"Test message {i}"})
                end = time.time()
                
                assert response.status_code == 200
                chat_times.append(end - start)
            
            # Test history endpoint performance
            history_times = []
            for _ in range(50):
                start = time.time()
                response = client.get("/history?limit=10")
                end = time.time()
                
                assert response.status_code == 200
                history_times.append(end - start)
            
            # Assert performance benchmarks
            assert statistics.mean(health_times) < 0.1, "Health endpoint too slow"
            assert statistics.mean(chat_times) < 0.5, "Chat endpoint too slow"
            assert statistics.mean(history_times) < 0.3, "History endpoint too slow"
            
            # Print performance summary
            print(f"\nPerformance Summary:")
            print(f"Health endpoint: {statistics.mean(health_times)*1000:.2f}ms avg")
            print(f"Chat endpoint: {statistics.mean(chat_times)*1000:.2f}ms avg")
            print(f"History endpoint: {statistics.mean(history_times)*1000:.2f}ms avg")
    
    def test_concurrent_requests(self):
        """Test concurrent request handling"""
        with patch.dict('os.environ', self.env_vars):
            from main import app
            
            client = TestClient(app)
            
            def make_request(thread_id):
                try:
                    response = client.post("/chat", json={"content": f"Concurrent message {thread_id}"})
                    return {
                        'thread_id': thread_id,
                        'success': response.status_code == 200,
                        'response_time': response.elapsed.total_seconds() if hasattr(response, 'elapsed') else 0
                    }
                except Exception as e:
                    return {
                        'thread_id': thread_id,
                        'success': False,
                        'error': str(e)
                    }
            
            # Test with 20 concurrent requests
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(make_request, i) for i in range(20)]
                results = [future.result() for future in as_completed(futures)]
            
            # Analyze results
            successful = [r for r in results if r['success']]
            failed = [r for r in results if not r['success']]
            
            success_rate = len(successful) / len(results)
            
            assert success_rate > 0.9, f"Too many failed requests: {len(failed)}/20"
            print(f"Concurrent test: {success_rate:.1%} success rate")
    
    def test_memory_usage_under_load(self):
        """Test memory usage under sustained load"""
        import psutil
        import os
        
        with patch.dict('os.environ', self.env_vars):
            from main import app
            
            client = TestClient(app)
            
            # Get initial memory usage
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Generate sustained load
            for i in range(200):
                client.post("/chat", json={"content": f"Load test message {i}"})
                
                if i % 50 == 0:
                    current_memory = process.memory_info().rss / 1024 / 1024  # MB
                    print(f"After {i} requests: {current_memory:.2f} MB")
            
            # Final memory check
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory
            
            # Memory increase should be reasonable (less than 100MB for 200 requests)
            assert memory_increase < 100, f"Memory increase too high: {memory_increase:.2f} MB"
            
            print(f"Memory usage: {initial_memory:.2f} MB -> {final_memory:.2f} MB")
    
    def test_database_connection_pooling_performance(self):
        """Test database connection pooling under load"""
        with patch.dict('os.environ', self.env_vars):
            from main import app
            
            client = TestClient(app)
            
            def make_db_intensive_request(thread_id):
                start_time = time.time()
                
                # Make chat request (writes to DB)
                chat_response = client.post("/chat", json={"content": f"DB test {thread_id}"})
                
                # Make history request (reads from DB)
                history_response = client.get("/history?limit=5")
                
                end_time = time.time()
                
                return {
                    'thread_id': thread_id,
                    'success': chat_response.status_code == 200 and history_response.status_code == 200,
                    'duration': end_time - start_time
                }
            
            # Test with 30 concurrent DB-intensive requests
            with ThreadPoolExecutor(max_workers=30) as executor:
                futures = [executor.submit(make_db_intensive_request, i) for i in range(30)]
                results = [future.result() for future in as_completed(futures)]
            
            # Analyze results
            successful = [r for r in results if r['success']]
            durations = [r['duration'] for r in successful]
            
            success_rate = len(successful) / len(results)
            avg_duration = statistics.mean(durations) if durations else 0
            
            assert success_rate > 0.9, f"DB connection pooling issues: {success_rate:.1%}"
            assert avg_duration < 2.0, f"DB operations too slow: {avg_duration:.2f}s"
            
            print(f"DB pooling test: {success_rate:.1%} success, {avg_duration:.3f}s avg")
   
    def test_large_payload_handling(self):
       """Test handling of large payloads"""
       with patch.dict('os.environ', self.env_vars):
           from main import app
           
           client = TestClient(app)
           
           # Test various payload sizes
           payload_sizes = [100, 1000, 4000, 4999]  # Last one is just under limit
           results = []
           
           for size in payload_sizes:
               content = "A" * size
               start_time = time.time()
               
               response = client.post("/chat", json={"content": content})
               
               end_time = time.time()
               duration = end_time - start_time
               
               results.append({
                   'size': size,
                   'success': response.status_code == 200,
                   'duration': duration
               })
           
           # All should succeed
           for result in results:
               assert result['success'], f"Failed with payload size {result['size']}"
           
           # Duration should not increase dramatically with size
           durations = [r['duration'] for r in results]
           assert max(durations) < 1.0, "Large payload processing too slow"
           
           # Test payload that exceeds limit
           oversized_content = "A" * 6000
           response = client.post("/chat", json={"content": oversized_content})
           assert response.status_code == 422, "Should reject oversized payload"