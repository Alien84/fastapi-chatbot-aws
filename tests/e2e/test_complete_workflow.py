import pytest
import requests
import time
import boto3
import psycopg2
import docker
from concurrent.futures import ThreadPoolExecutor
import json

class TestCompleteWorkflow:
    
    @classmethod
    def setup_class(cls):
        """Set up complete test environment"""
        cls.docker_client = docker.from_env()
        
        # Start test database
        cls.db_container = cls.docker_client.containers.run(
            "postgres:14",
            environment={
                "POSTGRES_DB": "e2e_test",
                "POSTGRES_USER": "e2e_user",
                "POSTGRES_PASSWORD": "e2e_password"
            },
            ports={'5432/tcp': 5438},
            detach=True,
            remove=True
        )
        
        time.sleep(10)
        
        # Database connection details
        cls.db_config = {
            'host': 'localhost',
            'port': 5438,
            'database': 'e2e_test',
            'user': 'e2e_user',
            'password': 'e2e_password'
        }
        
        # Start application container
        cls.app_container = cls.docker_client.containers.run(
            "chatbot-test:latest",  # Assumes container was built in previous tests
            environment={
                "DB_HOST": "host.docker.internal",
                "DB_PORT": "5438",
                "DB_NAME": "e2e_test",
                "DB_USERNAME": "e2e_user",
                "DB_PASSWORD": "e2e_password"
            },
            ports={'8000/tcp': 8002},
            detach=True,
            remove=True,
            extra_hosts={'host.docker.internal': 'host-gateway'}
        )
        
        time.sleep(15)  # Wait for app to start
        
        cls.api_base_url = "http://localhost:8002"
    
    @classmethod
    def teardown_class(cls):
        """Clean up test environment"""
        cls.app_container.stop()
        cls.db_container.stop()
    
    def get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(
            host=self.db_config['host'],
            port=self.db_config['port'],
            database=self.db_config['database'],
            user=self.db_config['user'],
            password=self.db_config['password']
        )
    
    def test_complete_user_journey(self):
        """Test complete user journey from API to database"""
        # Step 1: Verify application is healthy
        health_response = requests.get(f"{self.api_base_url}/health", timeout=10)
        assert health_response.status_code == 200
        assert health_response.json()["status"] == "healthy"
        
        # Step 2: Send multiple chat messages
        messages = [
            "Hello, how are you?",
            "I'm having a great day!",
            "Can you help me with something?",
            "Thank you for your assistance."
        ]
        
        message_ids = []
        for message in messages:
            response = requests.post(
                f"{self.api_base_url}/chat",
                json={"content": message},
                timeout=10
            )
            assert response.status_code == 200
            
            data = response.json()
            assert "message_id" in data
            assert data["response"] == f"You said: {message}"
            
            message_ids.append(data["message_id"])
        
        # Step 3: Verify messages are stored in database
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM chatbot_messages")
        count = cursor.fetchone()[0]
        assert count == len(messages)
        
        # Verify message content
        cursor.execute("SELECT id, content, response FROM chatbot_messages ORDER BY created_at")
        db_messages = cursor.fetchall()
        
        for i, (db_id, db_content, db_response) in enumerate(db_messages):
            assert db_content == messages[i]
            assert db_response == f"You said: {messages[i]}"
            assert db_id in message_ids
        
        cursor.close()
        conn.close()
        
        # Step 4: Test history endpoint
        history_response = requests.get(f"{self.api_base_url}/history", timeout=10)
        assert history_response.status_code == 200
        
        history_data = history_response.json()
        assert history_data["total_count"] == len(messages)
        assert len(history_data["history"]) == len(messages)
        
        print("✅ Complete user journey test passed")
    
    def test_concurrent_user_sessions(self):
        """Test multiple concurrent user sessions"""
        def simulate_user_session(user_id):
            session_messages = [
                f"User {user_id} message 1",
                f"User {user_id} message 2",
                f"User {user_id} message 3"
            ]
            
            results = []
            for message in session_messages:
                try:
                    response = requests.post(
                        f"{self.api_base_url}/chat",
                        json={"content": message},
                        timeout=10
                    )
                    results.append({
                        'user_id': user_id,
                        'success': response.status_code == 200,
                        'message': message
                    })
                except Exception as e:
                    results.append({
                        'user_id': user_id,
                        'success': False,
                        'error': str(e),
                        'message': message
                    })
            
            return results
        
        # Simulate 10 concurrent users
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(simulate_user_session, i) for i in range(10)]
            all_results = []
            
            for future in futures:
                all_results.extend(future.result())
        
        # Verify all requests succeeded
        successful_requests = [r for r in all_results if r['success']]
        success_rate = len(successful_requests) / len(all_results)
        
        assert success_rate > 0.95, f"Concurrent sessions success rate too low: {success_rate:.1%}"
        
        # Verify database integrity
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM chatbot_messages")
        total_messages = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        expected_messages = 10 * 3  # 10 users × 3 messages each
        assert total_messages >= expected_messages * 0.95, "Some messages were lost"
        
        print(f"✅ Concurrent sessions test passed: {success_rate:.1%} success rate")
    
    def test_error_recovery_workflow(self):
        """Test system behavior under error conditions"""
        # Test 1: Invalid input handling
        invalid_inputs = [
            {"content": ""},  # Empty content
            {"content": "A" * 10000},  # Too long content
            {},  # Missing content
            {"invalid_field": "test"}  # Invalid field
        ]
        
        for invalid_input in invalid_inputs:
            response = requests.post(
                f"{self.api_base_url}/chat",
                json=invalid_input,
                timeout=10
            )
            assert response.status_code in [400, 422], f"Should reject invalid input: {invalid_input}"
        
        # Test 2: System recovery after errors
        # Send valid request after invalid ones
        valid_response = requests.post(
            f"{self.api_base_url}/chat",
            json={"content": "This should work after errors"},
            timeout=10
        )
        assert valid_response.status_code == 200
        
        # Test 3: Database consistency after errors
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Check that invalid requests didn't create database entries
        cursor.execute("SELECT content FROM chatbot_messages WHERE content = ''")
        empty_content_messages = cursor.fetchall()
        assert len(empty_content_messages) == 0, "Invalid messages should not be stored"
        
        cursor.close()
        conn.close()
        
        print("✅ Error recovery workflow test passed")
    
    def test_data_consistency_across_endpoints(self):
        """Test data consistency across different API endpoints"""
        # Send test messages
        test_messages = ["Consistency test 1", "Consistency test 2", "Consistency test 3"]
        sent_message_ids = []
        
        for message in test_messages:
            response = requests.post(
                f"{self.api_base_url}/chat",
                json={"content": message},
                timeout=10
            )
            assert response.status_code == 200
            sent_message_ids.append(response.json()["message_id"])
        
        # Get data via history endpoint
        history_response = requests.get(f"{self.api_base_url}/history", timeout=10)
        history_data = history_response.json()
        
        # Get data via individual message endpoints
        individual_messages = []
        for message_id in sent_message_ids:
            response = requests.get(f"{self.api_base_url}/message/{message_id}/sentiment", timeout=10)
            if response.status_code == 200:
                individual_messages.append(response.json())
        
        # Verify consistency
        history_messages = {msg["id"]: msg for msg in history_data["history"]}
        
        for message_id in sent_message_ids:
            # Message should exist in history
            assert message_id in history_messages, f"Message {message_id} missing from history"
            
            # Find corresponding individual message
            individual_msg = next((msg for msg in individual_messages if msg["message_id"] == message_id), None)
            if individual_msg:
                # Content should match
                assert history_messages[message_id]["content"] == individual_msg["content"]
        
        # Verify database consistency
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, content, response FROM chatbot_messages WHERE id = ANY(%s)", (sent_message_ids,))
        db_messages = cursor.fetchall()
        
        assert len(db_messages) == len(sent_message_ids), "Database message count mismatch"
        
        for db_id, db_content, db_response in db_messages:
            assert db_id in sent_message_ids
            history_msg = history_messages[db_id]
            assert history_msg["content"] == db_content
            assert history_msg["response"] == db_response
        
        cursor.close()
        conn.close()
        
        print("✅ Data consistency test passed")
    
    def test_performance_under_realistic_load(self):
        """Test system performance under realistic load patterns"""
        import random
        
        def realistic_user_behavior(user_id, duration_seconds=30):
            """Simulate realistic user behavior"""
            start_time = time.time()
            messages_sent = 0
            
            while time.time() - start_time < duration_seconds:
                # Random delay between messages (1-10 seconds)
                time.sleep(random.uniform(1, 10))
                
                message = f"User {user_id} realistic message {messages_sent + 1}"
                
                try:
                    response = requests.post(
                        f"{self.api_base_url}/chat",
                        json={"content": message},
                        timeout=15
                    )
                    
                    if response.status_code == 200:
                        messages_sent += 1
                        
                        # Occasionally check history
                        if random.random() < 0.3:  # 30% chance
                            requests.get(f"{self.api_base_url}/history?limit=5", timeout=10)
                            
                except Exception as e:
                    print(f"User {user_id} request failed: {e}")
            
            return messages_sent
        
        # Simulate 5 users for 30 seconds each
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(realistic_user_behavior, i, 30) for i in range(5)]
            results = [future.result() for future in futures]
        
        total_duration = time.time() - start_time
        total_messages = sum(results)
        
        # Performance assertions
        assert total_messages > 0, "No messages were sent successfully"
        assert total_duration < 45, "Test took too long"  # Should complete within reasonable time
        
        # Check system is still responsive
        health_response = requests.get(f"{self.api_base_url}/health", timeout=10)
        assert health_response.status_code == 200
        
        # Check database integrity
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM chatbot_messages")
        db_message_count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        # Allow for some message loss, but not too much
        assert db_message_count >= total_messages * 0.9, "Too many messages lost"
        
        print(f"✅ Realistic load test passed: {total_messages} messages in {total_duration:.1f}s")
    
    def test_graceful_shutdown_and_restart(self):
        """Test graceful shutdown and restart behavior"""
        # Send some messages before shutdown
        pre_shutdown_response = requests.post(
            f"{self.api_base_url}/chat",
            json={"content": "Message before shutdown"},
            timeout=10
        )
        assert pre_shutdown_response.status_code == 200
        
        # Get initial message count
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM chatbot_messages")
        pre_shutdown_count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        # Restart application container
        self.app_container.restart()
        time.sleep(15)  # Wait for restart
        
        # Verify application is healthy after restart
        health_response = requests.get(f"{self.api_base_url}/health", timeout=15)
        assert health_response.status_code == 200
        
        # Verify data persisted through restart
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM chatbot_messages")
        post_restart_count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        assert post_restart_count == pre_shutdown_count, "Data should persist through restart"
        
        # Send message after restart
        post_restart_response = requests.post(
            f"{self.api_base_url}/chat",
            json={"content": "Message after restart"},
            timeout=10
        )
        assert post_restart_response.status_code == 200
        
        print("✅ Graceful shutdown and restart test passed")