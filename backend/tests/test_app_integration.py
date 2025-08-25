"""
Integration tests for the complete FastAPI application.
Tests the actual app.py with mocked dependencies to avoid static file mount issues.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
import sys
import os
from pathlib import Path

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture
def mock_rag_system():
    """Create a comprehensive mock RAG system"""
    mock_rag = Mock()
    mock_rag.query.return_value = ("Test response from RAG", [])
    mock_rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Test Course A", "Test Course B"]
    }
    mock_rag.add_course_folder.return_value = (2, 150)
    
    # Mock session manager
    mock_rag.session_manager = Mock()
    mock_rag.session_manager.create_session.return_value = "test-session-id"
    
    return mock_rag


@pytest.fixture
def app_with_mocked_dependencies(mock_rag_system):
    """Create the actual FastAPI app with mocked dependencies"""
    
    # Mock all the problematic imports and dependencies
    with patch('app.config') as mock_config, \
         patch('app.RAGSystem') as mock_rag_class, \
         patch('os.path.exists') as mock_exists, \
         patch('app.StaticFiles') as mock_static_files:
        
        # Configure mocks
        mock_config.return_value = Mock()  
        mock_rag_class.return_value = mock_rag_system
        mock_exists.return_value = False  # Prevent document loading
        mock_static_files.return_value = Mock()  # Mock static files
        
        # Import and create app after mocking
        from app import app
        
        # Replace the rag_system instance with our mock
        app.dependency_overrides = {}
        
        # Store mock for test access
        app.state.test_rag_system = mock_rag_system
        
        yield app
        
        # Clean up
        app.dependency_overrides = {}


@pytest.fixture
def test_client_with_real_app(app_with_mocked_dependencies):
    """Create test client with the real FastAPI app"""
    return TestClient(app_with_mocked_dependencies)


@pytest.mark.integration
class TestAppIntegration:
    """Test the complete FastAPI application integration"""
    
    def test_startup_event_no_docs_folder(self, app_with_mocked_dependencies):
        """Test startup event when docs folder doesn't exist"""
        # The mocked os.path.exists returns False, so no documents should be loaded
        # This test verifies the app starts successfully even without docs
        app = app_with_mocked_dependencies
        assert app is not None
        assert hasattr(app.state, 'test_rag_system')
    
    def test_query_endpoint_integration(self, test_client_with_real_app):
        """Test /api/query endpoint with real app structure"""
        client = test_client_with_real_app
        
        response = client.post("/api/query", json={
            "query": "What is machine learning?",
            "session_id": "integration-test-session"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure matches Pydantic model
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        
        # Verify the response contains expected data
        assert data["answer"] == "Test response from RAG"
        assert isinstance(data["sources"], list)
        assert data["session_id"] == "integration-test-session"
    
    def test_courses_endpoint_integration(self, test_client_with_real_app):
        """Test /api/courses endpoint with real app structure"""
        client = test_client_with_real_app
        
        response = client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure matches Pydantic model  
        assert "total_courses" in data
        assert "course_titles" in data
        
        # Verify the response contains expected data
        assert data["total_courses"] == 2
        assert len(data["course_titles"]) == 2
        assert "Test Course A" in data["course_titles"]
    
    def test_cors_middleware_integration(self, test_client_with_real_app):
        """Test CORS middleware is properly configured"""
        client = test_client_with_real_app
        
        # Make a preflight request
        response = client.options("/api/query", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type"
        })
        
        # Verify CORS headers are present
        assert response.status_code == 200
        headers = response.headers
        
        assert "access-control-allow-origin" in headers
        assert headers["access-control-allow-origin"] == "*"
        assert "access-control-allow-methods" in headers
        assert "access-control-allow-headers" in headers
    
    def test_trusted_host_middleware_integration(self, test_client_with_real_app):
        """Test trusted host middleware allows requests"""
        client = test_client_with_real_app
        
        # Make request with custom host header
        response = client.post("/api/query", 
            json={"query": "test"},
            headers={"Host": "custom-host.example.com"}
        )
        
        # Should be allowed due to "*" in allowed_hosts
        assert response.status_code == 200
    
    def test_pydantic_model_validation_integration(self, test_client_with_real_app):
        """Test Pydantic model validation in real app"""
        client = test_client_with_real_app
        
        # Test invalid request (missing required field)
        response = client.post("/api/query", json={
            "session_id": "test"  # Missing required 'query' field
        })
        
        assert response.status_code == 422  # Unprocessable Entity
        error_data = response.json()
        assert "detail" in error_data
        
        # Verify validation error mentions the missing field
        error_details = str(error_data["detail"])
        assert "query" in error_details
    
    def test_exception_handling_integration(self, test_client_with_real_app, app_with_mocked_dependencies):
        """Test exception handling in real app"""
        client = test_client_with_real_app
        app = app_with_mocked_dependencies
        
        # Configure mock to raise exception
        mock_rag = app.state.test_rag_system
        mock_rag.query.side_effect = Exception("Integration test exception")
        
        # Make request that should trigger exception
        response = client.post("/api/query", json={
            "query": "This will cause an exception"
        })
        
        # Verify exception is properly handled
        assert response.status_code == 500
        error_data = response.json()
        assert error_data["detail"] == "Integration test exception"
    
    def test_session_creation_integration(self, test_client_with_real_app, app_with_mocked_dependencies):
        """Test session creation when no session_id provided"""
        client = test_client_with_real_app
        app = app_with_mocked_dependencies
        
        # Make request without session_id
        response = client.post("/api/query", json={
            "query": "Create new session for me"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have created a new session
        assert data["session_id"] == "test-session-id"
        
        # Verify session manager was called
        mock_rag = app.state.test_rag_system
        mock_rag.session_manager.create_session.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_async_endpoint_behavior(self, app_with_mocked_dependencies):
        """Test that async endpoints work correctly"""
        from httpx import AsyncClient
        
        app = app_with_mocked_dependencies
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Test async query endpoint
            response = await client.post("/api/query", json={
                "query": "Async test query"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            
            # Test async courses endpoint  
            response = await client.get("/api/courses")
            
            assert response.status_code == 200
            data = response.json()
            assert "total_courses" in data
    
    def test_api_title_and_metadata(self, app_with_mocked_dependencies):
        """Test app metadata and OpenAPI specification"""
        app = app_with_mocked_dependencies
        
        # Verify app title
        assert app.title == "Course Materials RAG System"
        
        # Test OpenAPI endpoint
        with TestClient(app) as client:
            response = client.get("/openapi.json")
            assert response.status_code == 200
            
            openapi_data = response.json()
            assert openapi_data["info"]["title"] == "Course Materials RAG System"
    
    def test_docs_endpoint_accessibility(self, app_with_mocked_dependencies):
        """Test that API documentation endpoints are accessible"""
        app = app_with_mocked_dependencies
        
        with TestClient(app) as client:
            # Test Swagger UI endpoint
            docs_response = client.get("/docs")
            assert docs_response.status_code == 200
            
            # Test ReDoc endpoint
            redoc_response = client.get("/redoc")
            assert redoc_response.status_code == 200


@pytest.mark.integration
class TestStaticFileHandling:
    """Test static file handling without actually mounting problematic directories"""
    
    def test_app_creation_without_static_files(self, mock_rag_system):
        """Test that app can be created without mounting static files"""
        
        with patch('app.config') as mock_config, \
             patch('app.RAGSystem') as mock_rag_class, \
             patch('os.path.exists') as mock_exists:
            
            # Configure mocks
            mock_config.return_value = Mock()
            mock_rag_class.return_value = mock_rag_system
            mock_exists.return_value = False
            
            # Mock StaticFiles to prevent actual mounting
            with patch('app.StaticFiles') as mock_static_files:
                mock_static_files.return_value = Mock()
                
                # Import should work without errors
                from app import app
                
                assert app is not None
                assert app.title == "Course Materials RAG System"
    
    def test_static_file_mount_prevention(self, mock_rag_system):
        """Test that static file mounting is properly mocked in tests"""
        
        with patch('app.config') as mock_config, \
             patch('app.RAGSystem') as mock_rag_class, \
             patch('os.path.exists') as mock_exists, \
             patch('app.StaticFiles') as mock_static_files:
            
            mock_config.return_value = Mock()
            mock_rag_class.return_value = mock_rag_system  
            mock_exists.return_value = False
            
            # StaticFiles should be mocked and not actually mount
            mock_static_instance = Mock()
            mock_static_files.return_value = mock_static_instance
            
            # Import app
            from app import app
            
            # Verify StaticFiles was called (mocked) but didn't cause errors
            mock_static_files.assert_called_once_with(directory="../frontend", html=True)
            
            # App should still function for API endpoints
            with TestClient(app) as client:
                response = client.post("/api/query", json={"query": "test"})
                assert response.status_code == 200