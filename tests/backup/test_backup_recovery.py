import pytest
import psycopg2
import docker
import time
import subprocess
import tempfile
import os
import requests

class TestBackupRecovery:
    
    @classmethod
    def setup_class(cls):
        """Set up test environment with database"""
        cls.docker_client = docker.from_env()
        
        # Start primary database
        cls.primary_db = cls.docker_client.containers.run(
            "postgres:14",
            environment={
                "POSTGRES_DB": "backup_test",
                "POSTGRES_USER": "backup_user",
                "POSTGRES_PASSWORD": "backup_password"
            },
            ports={'5432/tcp': 5439},
            detach=True,
            remove=True
        )
        
        time.sleep(10)
        
        cls.db_config = {
            'host': 'localhost',
            'port': 5439,
            'database': 'backup_test',
            'user': 'backup_user',
            'password': 'backup_password'
        }
    
    @classmethod
    def teardown_class(cls):
        """Clean up"""
        cls.primary_db.stop()
    
    def get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(
            host=self.db_config['host'],
            port=self.db_config['port'],
            database=self.db_config['database'],
            user=self.db_config['user'],
            password=self.db_config['password']
        )
    
    def test_database_backup_creation(self):
        """Test database backup creation"""
        # Create test data
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Create test table and data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chatbot_messages (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        test_data = [
            ("Backup test message 1", "Response 1"),
            ("Backup test message 2", "Response 2"),
            ("Backup test message 3", "Response 3")
        ]
        
        for content, response in test_data:
            cursor.execute(
                "INSERT INTO chatbot_messages (content, response) VALUES (%s, %s)",
                (content, response)
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Create backup using pg_dump
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.sql', delete=False) as backup_file:
            backup_path = backup_file.name
        
        try:
            # Run pg_dump
            subprocess.run([
                'pg_dump',
                '-h', self.db_config['host'],
                '-p', str(self.db_config['port']),
                '-U', self.db_config['user'],
                '-d', self.db_config['database'],
                '-f', backup_path,
                '--no-password'
            ], env={**os.environ, 'PGPASSWORD': self.db_config['password']}, check=True)
            
            # Verify backup file was created and has content
            assert os.path.exists(backup_path)
            
            with open(backup_path, 'r') as f:
                backup_content = f.read()
            
            assert len(backup_content) > 0
            assert 'chatbot_messages' in backup_content
            assert 'Backup test message' in backup_content
            
            print("✅ Database backup created successfully")
            
        finally:
            # Clean up backup file
            if os.path.exists(backup_path):
                os.unlink(backup_path)
    
    def test_database_restore_process(self):
        """Test database restore process"""
        # Create initial data
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chatbot_messages (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        cursor.execute("DELETE FROM chatbot_messages")  # Clear existing data
        
        original_data = [
            ("Original message 1", "Original response 1"),
            ("Original message 2", "Original response 2")
        ]
        
        for content, response in original_data:
            cursor.execute(
                "INSERT INTO chatbot_messages (content, response) VALUES (%s, %s)",
                (content, response)
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Create backup
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.sql', delete=False) as backup_file:
            backup_path = backup_file.name
        
        try:
            subprocess.run([
                'pg_dump',
                '-h', self.db_config['host'],
                '-p', str(self.db_config['port']),
                '-U', self.db_config['user'],
                '-d', self.db_config['database'],
                '-f', backup_path,
                '--no-password'
            ], env={**os.environ, 'PGPASSWORD': self.db_config['password']}, check=True)
            
            # Modify data (simulate data loss)
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chatbot_messages")
            cursor.execute(
                "INSERT INTO chatbot_messages (content, response) VALUES (%s, %s)",
                ("Modified message", "Modified response")
            )
            conn.commit()
            cursor.close()
            conn.close()
            
            # Verify data was modified
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT content FROM chatbot_messages")
            current_data = cursor.fetchall()
            cursor.close()
            conn.close()
            
            assert len(current_data) == 1
            assert current_data[0][0] == "Modified message"
            
            # Restore from backup
            # First, drop and recreate the table
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS chatbot_messages")
            conn.commit()
            cursor.close()
            conn.close()
            
            # Restore using psql
            subprocess.run([
                'psql',
                '-h', self.db_config['host'],
                '-p', str(self.db_config['port']),
                '-U', self.db_config['user'],
                '-d', self.db_config['database'],
                '-f', backup_path
            ], env={**os.environ, 'PGPASSWORD': self.db_config['password']}, check=True)
            
            # Verify restoration
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT content FROM chatbot_messages ORDER BY id")
            restored_data = cursor.fetchall()
            cursor.close()
            conn.close()
            
            assert len(restored_data) == 2
            assert restored_data[0][0] == "Original message 1"
            assert restored_data[1][0] == "Original message 2"
            
            print("✅ Database restore process successful")
            
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)
    
    def test_point_in_time_recovery_simulation(self):
        """Test point-in-time recovery simulation"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chatbot_messages (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        cursor.execute("DELETE FROM chatbot_messages")
        
        # Insert data at different points in time
        time_points = []
        
        # Time point 1
        cursor.execute(
            "INSERT INTO chatbot_messages (content, response) VALUES (%s, %s)",
            ("Message at time 1", "Response at time 1")
        )
        conn.commit()
        time_points.append(("Time 1", 1))
        time.sleep(1)
        
        # Time point 2
        cursor.execute(
            "INSERT INTO chatbot_messages (content, response) VALUES (%s, %s)",
            ("Message at time 2", "Response at time 2")
        )
        conn.commit()
        time_points.append(("Time 2", 2))
        time.sleep(1)
        
        # Time point 3 (simulate bad data)
        cursor.execute(
            "INSERT INTO chatbot_messages (content, response) VALUES (%s, %s)",
            ("Bad message", "Bad response")
        )
        conn.commit()
        time_points.append(("Time 3", 3))
        
        # Verify all data exists
        cursor.execute("SELECT COUNT(*) FROM chatbot_messages")
        total_count = cursor.fetchone()[0]
        assert total_count == 3
        
        # Simulate recovery to time point 2 (remove time point 3 data)
        cursor.execute("DELETE FROM chatbot_messages WHERE content = 'Bad message'")
        conn.commit()
        
        # Verify recovery
        cursor.execute("SELECT COUNT(*) FROM chatbot_messages")
        recovered_count = cursor.fetchone()[0]
        assert recovered_count == 2
        
        cursor.execute("SELECT content FROM chatbot_messages ORDER BY id")
        remaining_messages = cursor.fetchall()
        assert "Bad message" not in [msg[0] for msg in remaining_messages]
        
        cursor.close()
        conn.close()
        
        print("✅ Point-in-time recovery simulation successful")
    
    def test_backup_validation(self):
        """Test backup validation and integrity checks"""
        # Create test data
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chatbot_messages (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        cursor.execute("DELETE FROM chatbot_messages")
        
        test_messages = [
            ("Validation test 1", "Response 1"),
            ("Validation test 2", "Response 2"),
            ("Validation test 3", "Response 3")
        ]
        
        for content, response in test_messages:
            cursor.execute(
                "INSERT INTO chatbot_messages (content, response) VALUES (%s, %s)",
                (content, response)
            )
        
        conn.commit()
        
        # Get original data count
        cursor.execute("SELECT COUNT(*) FROM chatbot_messages")
        original_count = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        # Create backup
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.sql', delete=False) as backup_file:
            backup_path = backup_file.name
        
        try:
            subprocess.run([
                'pg_dump',
                '-h', self.db_config['host'],
                '-p', str(self.db_config['port']),
                '-U', self.db_config['user'],
                '-d', self.db_config['database'],
                '-f', backup_path,
                '--no-password'
            ], env={**os.environ, 'PGPASSWORD': self.db_config['password']}, check=True)
            
            # Validate backup file
            with open(backup_path, 'r') as f:
                backup_content = f.read()
            
            # Check backup contains expected content
            validation_checks = [
                ('Table definition', 'CREATE TABLE' in backup_content),
                ('Data content', 'Validation test 1' in backup_content),
                ('All test data', all(msg[0] in backup_content for msg in test_messages)),
                ('File size', len(backup_content) > 1000),  # Reasonable size
                ('SQL structure', 'INSERT INTO' in backup_content or 'COPY' in backup_content)
            ]
            
            for check_name, check_result in validation_checks:
                assert check_result, f"Backup validation failed: {check_name}"
            
            print("✅ Backup validation successful")
            
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)
    
    def test_automated_backup_schedule_simulation(self):
        """Test automated backup schedule simulation"""
        import threading
        import queue
        
        # Simulate automated backup process
        backup_queue = queue.Queue()
        
        def simulate_backup_job(job_id):
            """Simulate a backup job"""
            try:
                time.sleep(0.1)  # Simulate backup time
                
                # Create temporary backup
                with tempfile.NamedTemporaryFile(mode='w+', suffix='.sql', delete=False) as backup_file:
                    backup_path = backup_file.name
                
                subprocess.run([
                    'pg_dump',
                    '-h', self.db_config['host'],
                    '-p', str(self.db_config['port']),
                    '-U', self.db_config['user'],
                    '-d', self.db_config['database'],
                    '-f', backup_path,
                    '--no-password'
                ], env={**os.environ, 'PGPASSWORD': self.db_config['password']}, check=True)
                
                # Validate backup
                backup_valid = os.path.exists(backup_path) and os.path.getsize(backup_path) > 0
                
                # Clean up
                if os.path.exists(backup_path):
                    os.unlink(backup_path)
                
                backup_queue.put({
                    'job_id': job_id,
                    'success': backup_valid,
                    'timestamp': time.time()
                })
                
            except Exception as e:
                backup_queue.put({
                    'job_id': job_id,
                    'success': False,
                    'error': str(e),
                    'timestamp': time.time()
                })
        
        # Run multiple backup jobs concurrently (simulate scheduled backups)
        threads = []
        for i in range(3):
            thread = threading.Thread(target=simulate_backup_job, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all backup jobs to complete
        for thread in threads:
            thread.join(timeout=30)
        
        # Collect results
        results = []
        while not backup_queue.empty():
            results.append(backup_queue.get())
        
        # Validate results
        assert len(results) == 3, "Not all backup jobs completed"
        
        successful_backups = [r for r in results if r['success']]
        assert len(successful_backups) == 3, f"Some backups failed: {len(successful_backups)}/3"
        
        print("✅ Automated backup schedule simulation successful")