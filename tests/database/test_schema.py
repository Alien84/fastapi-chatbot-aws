import pytest
import psycopg2
import docker
import time
from sqlalchemy import create_engine, inspect, MetaData, Table, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager
import os

class TestDatabaseSchema:
    
    @classmethod
    def setup_class(cls):
        """Set up test database container"""
        cls.client = docker.from_env()
        
        # Start PostgreSQL container
        cls.db_container = cls.client.containers.run(
            "postgres:14",
            environment={
                "POSTGRES_DB": "test_chatbot",
                "POSTGRES_USER": "test_user",
                "POSTGRES_PASSWORD": "test_password"
            },
            ports={'5432/tcp': 5434},
            detach=True,
            remove=True
        )
        
        # Wait for database to be ready
        time.sleep(10)
        
        cls.db_url = "postgresql://test_user:test_password@localhost:5434/test_chatbot"
        cls.engine = create_engine(cls.db_url)
    
    @classmethod
    def teardown_class(cls):
        """Clean up test database container"""
        cls.db_container.stop()
    
    @contextmanager
    def get_db_connection(self):
        """Context manager for database connections"""
        conn = psycopg2.connect(
            host='localhost',
            port=5434,
            database='test_chatbot',
            user='test_user',
            password='test_password'
        )
        try:
            yield conn
        finally:
            conn.close()
    
    def test_table_creation(self):
        """Test that tables are created correctly"""
        # Import your models
        import sys
        sys.path.append('../../app')
        from main import Base, MessageRecord
        
        # Create tables
        Base.metadata.create_all(bind=self.engine)
        
        # Inspect the created tables
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        
        # Assert chatbot_messages table exists
        assert 'chatbot_messages' in tables
        
        # Check columns
        columns = inspector.get_columns('chatbot_messages')
        column_names = [col['name'] for col in columns]
        
        expected_columns = ['id', 'content', 'response', 'created_at']
        for col in expected_columns:
            assert col in column_names
        
        # Check data types
        column_types = {col['name']: str(col['type']) for col in columns}
        assert 'INTEGER' in column_types['id']
        assert 'TEXT' in column_types['content']
        assert 'TEXT' in column_types['response']
    
    def test_sentiment_columns_addition(self):
        """Test that sentiment analysis columns can be added"""
        # First create base table
        import sys
        sys.path.append('../../app')
        from main import Base
        Base.metadata.create_all(bind=self.engine)
        
        # Add sentiment columns (simulating Lambda function behavior)
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                ALTER TABLE chatbot_messages 
                ADD COLUMN IF NOT EXISTS sentiment VARCHAR(20),
                ADD COLUMN IF NOT EXISTS sentiment_confidence FLOAT,
                ADD COLUMN IF NOT EXISTS analyzed_at TIMESTAMP;
            """)
            
            conn.commit()
            cursor.close()
        
        # Verify columns were added
        inspector = inspect(self.engine)
        columns = inspector.get_columns('chatbot_messages')
        column_names = [col['name'] for col in columns]
        
        assert 'sentiment' in column_names
        assert 'sentiment_confidence' in column_names
        assert 'analyzed_at' in column_names
    
    def test_data_integrity_constraints(self):
        """Test database constraints and data integrity"""
        import sys
        sys.path.append('../../app')
        from main import Base
        Base.metadata.create_all(bind=self.engine)
        
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Test NOT NULL constraints
            try:
                cursor.execute("""
                    INSERT INTO chatbot_messages (content, response) 
                    VALUES (NULL, 'response')
                """)
                conn.commit()
                assert False, "Should have failed due to NOT NULL constraint"
            except psycopg2.IntegrityError:
                conn.rollback()  # Expected behavior
            
            # Test valid insertion
            cursor.execute("""
                INSERT INTO chatbot_messages (content, response) 
                VALUES ('test content', 'test response')
            """)
            conn.commit()
            
            # Verify insertion
            cursor.execute("SELECT COUNT(*) FROM chatbot_messages")
            count = cursor.fetchone()[0]
            assert count == 1
            
            cursor.close()
    
    def test_performance_with_large_dataset(self):
        """Test database performance with larger dataset"""
        import sys
        sys.path.append('../../app')
        from main import Base
        Base.metadata.create_all(bind=self.engine)
        
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Insert 1000 test records
            start_time = time.time()
            
            for i in range(1000):
                cursor.execute("""
                    INSERT INTO chatbot_messages (content, response) 
                    VALUES (%s, %s)
                """, (f'Test message {i}', f'Test response {i}'))
            
            conn.commit()
            insert_time = time.time() - start_time
            
            # Test query performance
            start_time = time.time()
            cursor.execute("""
                SELECT * FROM chatbot_messages 
                ORDER BY created_at DESC 
                LIMIT 50
            """)
            results = cursor.fetchall()
            query_time = time.time() - start_time
            
            cursor.close()
            
            # Assert performance benchmarks
            assert insert_time < 5.0, f"Insert took too long: {insert_time}s"
            assert query_time < 0.5, f"Query took too long: {query_time}s"
            assert len(results) == 50
    
    def test_connection_pooling(self):
        """Test database connection pooling behavior"""
        from sqlalchemy import create_engine
        from sqlalchemy.pool import QueuePool
        
        # Create engine with connection pooling
        pooled_engine = create_engine(
            self.db_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600
        )
        
        # Test multiple concurrent connections
        import threading
        
        def test_connection(thread_id):
            with pooled_engine.connect() as conn:
                result = conn.execute("SELECT 1 as test").fetchone()
                assert result[0] == 1
                return True
        
        threads = []
        results = []
        
        for i in range(15):  # More than pool_size to test overflow
            thread = threading.Thread(target=lambda: results.append(test_connection(i)))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All connections should succeed
        assert len(results) == 15
        assert all(results)