import pytest
import psycopg2
import docker
import time
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
sys.path.append('../../app')
from main import Base, MessageRecord

class TestDatabaseDataOperations:
    
    @classmethod
    def setup_class(cls):
        """Set up test database"""
        cls.client = docker.from_env()
        
        cls.db_container = cls.client.containers.run(
            "postgres:14",
            environment={
                "POSTGRES_DB": "test_data_ops",
                "POSTGRES_USER": "test_user",
                "POSTGRES_PASSWORD": "test_password"
            },
            ports={'5432/tcp': 5435},
            detach=True,
            remove=True
        )
        
        time.sleep(10)
        
        cls.db_url = "postgresql://test_user:test_password@localhost:5435/test_data_ops"
        cls.engine = create_engine(cls.db_url)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        
        # Create tables
        Base.metadata.create_all(bind=cls.engine)
    
    @classmethod
    def teardown_class(cls):
        """Clean up"""
        cls.db_container.stop()
    
    def setup_method(self):
        """Clean database before each test"""
        with self.engine.connect() as conn:
            conn.execute("DELETE FROM chatbot_messages")
            conn.commit()
    
    def test_message_crud_operations(self):
        """Test Create, Read, Update, Delete operations"""
        db = self.SessionLocal()
        
        # CREATE
        message = MessageRecord(
            content="Test message",
            response="Test response"
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        
        assert message.id is not None
        assert message.created_at is not None
        
        # READ
        retrieved = db.query(MessageRecord).filter(MessageRecord.id == message.id).first()
        assert retrieved.content == "Test message"
        assert retrieved.response == "Test response"
        
        # UPDATE (simulate Lambda adding sentiment)
        retrieved.sentiment = "POSITIVE"
        retrieved.sentiment_confidence = 0.95
        retrieved.analyzed_at = datetime.utcnow()
        db.commit()
        
        # Verify update
        updated = db.query(MessageRecord).filter(MessageRecord.id == message.id).first()
        assert updated.sentiment == "POSITIVE"
        assert updated.sentiment_confidence == 0.95
        assert updated.analyzed_at is not None
        
        # DELETE
        db.delete(updated)
        db.commit()
        
        # Verify deletion
        deleted = db.query(MessageRecord).filter(MessageRecord.id == message.id).first()
        assert deleted is None
        
        db.close()
    
    def test_pagination_queries(self):
        """Test pagination functionality"""
        db = self.SessionLocal()
        
        # Insert test data
        for i in range(25):
            message = MessageRecord(
                content=f"Message {i}",
                response=f"Response {i}"
            )
            db.add(message)
        
        db.commit()
        
        # Test pagination
        page1 = db.query(MessageRecord).order_by(MessageRecord.created_at.desc()).limit(10).all()
        page2 = db.query(MessageRecord).order_by(MessageRecord.created_at.desc()).offset(10).limit(10).all()
        page3 = db.query(MessageRecord).order_by(MessageRecord.created_at.desc()).offset(20).limit(10).all()
        
        assert len(page1) == 10
        assert len(page2) == 10
        assert len(page3) == 5
        
        # Verify no overlap
        page1_ids = {msg.id for msg in page1}
        page2_ids = {msg.id for msg in page2}
        page3_ids = {msg.id for msg in page3}
        
        assert len(page1_ids.intersection(page2_ids)) == 0
        assert len(page2_ids.intersection(page3_ids)) == 0
        
        db.close()
    
    def test_date_filtering(self):
        """Test date-based filtering for cleanup operations"""
        db = self.SessionLocal()
        
        # Insert messages with different dates
        current_time = datetime.utcnow()
        old_time = current_time - timedelta(days=35)
        recent_time = current_time - timedelta(days=5)
        
        # Old message
        old_message = MessageRecord(
            content="Old message",
            response="Old response"
        )
        db.add(old_message)
        db.commit()
        
        # Manually set old date
        with self.engine.connect() as conn:
            conn.execute(
                "UPDATE chatbot_messages SET created_at = %s WHERE id = %s",
                (old_time, old_message.id)
            )
            conn.commit()
        
        # Recent message
        recent_message = MessageRecord(
            content="Recent message",
            response="Recent response"
        )
        db.add(recent_message)
        db.commit()
        
        # Test cleanup query (delete messages older than 30 days)
        cutoff_date = current_time - timedelta(days=30)
        old_messages = db.query(MessageRecord).filter(
            MessageRecord.created_at < cutoff_date
        ).all()
        
        assert len(old_messages) == 1
        assert old_messages[0].content == "Old message"
        
        # Test that recent messages are not affected
        recent_messages = db.query(MessageRecord).filter(
            MessageRecord.created_at >= cutoff_date
        ).all()
        
        assert len(recent_messages) == 1
        assert recent_messages[0].content == "Recent message"
        
        db.close()
    
    def test_concurrent_access(self):
        """Test concurrent database access"""
        import threading
        
        def insert_messages(thread_id, num_messages):
            db = self.SessionLocal()
            try:
                for i in range(num_messages):
                    message = MessageRecord(
                        content=f"Thread {thread_id} message {i}",
                        response=f"Thread {thread_id} response {i}"
                    )
                    db.add(message)
                db.commit()
                return True
            except Exception as e:
                db.rollback()
                print(f"Thread {thread_id} error: {e}")
                return False
            finally:
                db.close()
        
        threads = []
        results = []
        
        for i in range(5):
            thread = threading.Thread(target=lambda tid=i: results.append(insert_messages(tid, 10)))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All threads should succeed
        assert all(results)
        
        # Verify total count
        db = self.SessionLocal()
        total_count = db.query(MessageRecord).count()
        assert total_count == 50  # 5 threads × 10 messages each
        db.close()
    
    def test_transaction_rollback(self):
        """Test transaction rollback behavior"""
        db = self.SessionLocal()
        
        try:
            # Insert first message
            message1 = MessageRecord(
                content="First message",
                response="First response"
            )
            db.add(message1)
            
            # Insert second message that will cause an error
            message2 = MessageRecord(
                content=None,  # This should cause an error
                response="Second response"
            )
            db.add(message2)
            
            db.commit()  # This should fail
            assert False, "Should have failed due to NULL constraint"
            
        except Exception:
            db.rollback()
            
            # Verify that first message was also rolled back
            count = db.query(MessageRecord).count()
            assert count == 0
        
        finally:
            db.close()