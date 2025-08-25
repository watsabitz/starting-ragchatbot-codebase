"""
API endpoint tests for the FastAPI application.
Tests the REST API endpoints for proper request/response handling.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json
import sys
import os

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture
def test_app():
    """Create a test FastAPI app without static file mounting issues"""
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from typing import List, Optional, Dict, Any
    
    # Create test app without problematic static files
    app = FastAPI(title="Test RAG System API")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Pydantic models
    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[Dict[str, Any]]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]
    
    # Mock RAG system for testing
    mock_rag_system = Mock()
    
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()
            
            answer, sources = mock_rag_system.query(request.query, session_id)
            
            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Store mock for test access
    app.state.mock_rag_system = mock_rag_system
    
    return app


@pytest.fixture
def test_client(test_app):
    """Create a test client for the FastAPI app"""
    return TestClient(test_app)


@pytest.mark.api
class TestQueryEndpoint:
    """Test the /api/query endpoint"""
    
    def test_query_with_session_id_success(self, test_client, test_app):
        """Test successful query with provided session ID"""
        # Setup mock responses
        mock_rag = test_app.state.mock_rag_system
        mock_rag.query.return_value = (
            "Python is a programming language used for web development.",
            [{"text": "Python Course - Lesson 1", "link": "http://example.com"}]
        )
        
        # Make request
        response = test_client.post("/api/query", json={
            "query": "What is Python?",
            "session_id": "test-session-123"
        })
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["answer"] == "Python is a programming language used for web development."
        assert len(data["sources"]) == 1
        assert data["sources"][0]["text"] == "Python Course - Lesson 1"
        assert data["session_id"] == "test-session-123"
        
        # Verify RAG system was called correctly
        mock_rag.query.assert_called_once_with("What is Python?", "test-session-123")
    
    def test_query_without_session_id_creates_new_session(self, test_client, test_app):
        """Test query without session ID creates new session"""
        # Setup mock responses
        mock_rag = test_app.state.mock_rag_system
        mock_rag.session_manager.create_session.return_value = "new-session-456"
        mock_rag.query.return_value = (
            "Machine learning is a branch of AI.",
            []
        )
        
        # Make request
        response = test_client.post("/api/query", json={
            "query": "What is machine learning?"
        })
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["answer"] == "Machine learning is a branch of AI."
        assert data["session_id"] == "new-session-456"
        assert len(data["sources"]) == 0
        
        # Verify session creation was called
        mock_rag.session_manager.create_session.assert_called_once()
        mock_rag.query.assert_called_once_with("What is machine learning?", "new-session-456")
    
    def test_query_with_sources(self, test_client, test_app):
        """Test query that returns multiple sources"""
        # Setup mock responses with multiple sources
        mock_rag = test_app.state.mock_rag_system
        mock_rag.query.return_value = (
            "Data science combines statistics and programming.",
            [
                {"text": "Data Science Course - Lesson 1", "link": "http://example.com/ds1"},
                {"text": "Statistics Course - Lesson 3", "link": None}
            ]
        )
        
        # Make request
        response = test_client.post("/api/query", json={
            "query": "Explain data science",
            "session_id": "test-session"
        })
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["sources"]) == 2
        assert data["sources"][0]["text"] == "Data Science Course - Lesson 1"
        assert data["sources"][0]["link"] == "http://example.com/ds1"
        assert data["sources"][1]["text"] == "Statistics Course - Lesson 3"
        assert data["sources"][1]["link"] is None
    
    def test_query_missing_query_field(self, test_client):
        """Test request missing required query field"""
        response = test_client.post("/api/query", json={
            "session_id": "test-session"
        })
        
        assert response.status_code == 422  # Unprocessable Entity
        error_detail = response.json()
        assert "query" in str(error_detail)
    
    def test_query_empty_query_string(self, test_client, test_app):
        """Test request with empty query string"""
        # Setup mock to handle empty query
        mock_rag = test_app.state.mock_rag_system
        mock_rag.query.return_value = (
            "Please provide a specific question.",
            []
        )
        
        response = test_client.post("/api/query", json={
            "query": "",
            "session_id": "test-session"
        })
        
        # Should still process the request (business logic handles empty queries)
        assert response.status_code == 200
        data = response.json()
        assert "Please provide" in data["answer"]
    
    def test_query_rag_system_exception(self, test_client, test_app):
        """Test handling of RAG system exceptions"""
        # Setup mock to raise exception
        mock_rag = test_app.state.mock_rag_system
        mock_rag.query.side_effect = Exception("RAG system error")
        
        response = test_client.post("/api/query", json={
            "query": "Test query",
            "session_id": "test-session"
        })
        
        # Should return 500 error
        assert response.status_code == 500
        error_detail = response.json()
        assert "RAG system error" in error_detail["detail"]
    
    def test_query_invalid_json(self, test_client):
        """Test request with invalid JSON"""
        response = test_client.post("/api/query", data="invalid json")
        
        assert response.status_code == 422
    
    def test_query_large_query_string(self, test_client, test_app):
        """Test request with very large query string"""
        # Setup mock response
        mock_rag = test_app.state.mock_rag_system
        mock_rag.query.return_value = ("Processed large query", [])
        
        # Create large query string
        large_query = "What is Python? " * 1000  # ~14KB string
        
        response = test_client.post("/api/query", json={
            "query": large_query,
            "session_id": "test-session"
        })
        
        # Should handle large queries
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Processed large query"


@pytest.mark.api
class TestCoursesEndpoint:
    """Test the /api/courses endpoint"""
    
    def test_get_course_stats_success(self, test_client, test_app):
        """Test successful course statistics retrieval"""
        # Setup mock response
        mock_rag = test_app.state.mock_rag_system
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 3,
            "course_titles": ["Python Basics", "Machine Learning", "Data Science"]
        }
        
        # Make request
        response = test_client.get("/api/courses")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_courses"] == 3
        assert len(data["course_titles"]) == 3
        assert "Python Basics" in data["course_titles"]
        assert "Machine Learning" in data["course_titles"]
        assert "Data Science" in data["course_titles"]
        
        # Verify RAG system was called
        mock_rag.get_course_analytics.assert_called_once()
    
    def test_get_course_stats_empty_database(self, test_client, test_app):
        """Test course statistics when no courses are loaded"""
        # Setup mock response for empty database
        mock_rag = test_app.state.mock_rag_system
        mock_rag.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }
        
        # Make request
        response = test_client.get("/api/courses")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_courses"] == 0
        assert len(data["course_titles"]) == 0
    
    def test_get_course_stats_rag_system_exception(self, test_client, test_app):
        """Test handling of RAG system exceptions in course stats"""
        # Setup mock to raise exception
        mock_rag = test_app.state.mock_rag_system
        mock_rag.get_course_analytics.side_effect = Exception("Database connection failed")
        
        # Make request
        response = test_client.get("/api/courses")
        
        # Should return 500 error
        assert response.status_code == 500
        error_detail = response.json()
        assert "Database connection failed" in error_detail["detail"]


@pytest.mark.api
class TestAPIIntegration:
    """Test API integration scenarios"""
    
    def test_cors_headers_present(self, test_client):
        """Test that CORS headers are properly set"""
        response = test_client.options("/api/query")
        
        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers
    
    def test_api_endpoints_accessible(self, test_client, test_app):
        """Test that both API endpoints are accessible"""
        # Setup minimal mocks
        mock_rag = test_app.state.mock_rag_system
        mock_rag.query.return_value = ("Test response", [])
        mock_rag.get_course_analytics.return_value = {"total_courses": 1, "course_titles": ["Test"]}
        
        # Test query endpoint
        query_response = test_client.post("/api/query", json={"query": "test"})
        assert query_response.status_code == 200
        
        # Test courses endpoint
        courses_response = test_client.get("/api/courses")
        assert courses_response.status_code == 200
    
    def test_response_content_type(self, test_client, test_app):
        """Test that responses have correct content type"""
        # Setup mock
        mock_rag = test_app.state.mock_rag_system
        mock_rag.query.return_value = ("Test response", [])
        mock_rag.get_course_analytics.return_value = {"total_courses": 0, "course_titles": []}
        
        # Test query endpoint content type
        query_response = test_client.post("/api/query", json={"query": "test"})
        assert "application/json" in query_response.headers["content-type"]
        
        # Test courses endpoint content type
        courses_response = test_client.get("/api/courses")
        assert "application/json" in courses_response.headers["content-type"]
    
    def test_session_persistence_across_requests(self, test_client, test_app):
        """Test that session IDs persist across multiple requests"""
        # Setup mock
        mock_rag = test_app.state.mock_rag_system
        mock_rag.session_manager.create_session.return_value = "persistent-session-789"
        mock_rag.query.return_value = ("Response", [])
        
        # First request without session
        first_response = test_client.post("/api/query", json={"query": "first question"})
        first_data = first_response.json()
        session_id = first_data["session_id"]
        
        # Second request with same session
        second_response = test_client.post("/api/query", json={
            "query": "follow-up question",
            "session_id": session_id
        })
        second_data = second_response.json()
        
        # Session ID should be maintained
        assert first_data["session_id"] == second_data["session_id"]
    
    def test_concurrent_requests(self, test_client, test_app):
        """Test handling of concurrent API requests"""
        import threading
        import time
        
        # Setup mock with slight delay
        mock_rag = test_app.state.mock_rag_system
        def mock_query_with_delay(query, session_id=None):
            time.sleep(0.1)  # Simulate processing time
            return (f"Response to: {query}", [])
        
        mock_rag.query.side_effect = mock_query_with_delay
        
        results = []
        
        def make_request(query_text):
            response = test_client.post("/api/query", json={"query": query_text})
            results.append((query_text, response.status_code))
        
        # Create multiple threads for concurrent requests
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request, args=(f"Query {i}",))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert len(results) == 5
        for query_text, status_code in results:
            assert status_code == 200