"""
Test configuration and shared fixtures for the RAG system tests.
"""

import pytest
from unittest.mock import Mock, patch
import tempfile
import os
import sys
from pathlib import Path

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config import Config
from rag_system import RAGSystem
from vector_store import SearchResults
from models import Course, Lesson, CourseChunk


class TestConfig(Config):
    """Test configuration with safe defaults"""
    def __init__(self):
        super().__init__()
        self.CHUNK_SIZE = 800
        self.CHUNK_OVERLAP = 100
        self.CHROMA_PATH = "./test_chroma_db"
        self.EMBEDDING_MODEL = "test-model"
        self.MAX_RESULTS = 5
        self.ANTHROPIC_API_KEY = "sk-ant-test-key"
        self.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
        self.MAX_HISTORY = 2


@pytest.fixture
def test_config():
    """Fixture providing test configuration"""
    return TestConfig()


@pytest.fixture
def mock_vector_store():
    """Fixture providing a mocked vector store"""
    mock_store = Mock()
    mock_store.search.return_value = SearchResults(
        documents=["Test document content"],
        metadata=[{"course_title": "Test Course", "lesson_number": 1}],
        distances=[0.1],
        error=None
    )
    mock_store.get_lesson_link.return_value = None
    mock_store.get_course_count.return_value = 1
    mock_store.get_existing_course_titles.return_value = ["Test Course"]
    return mock_store


@pytest.fixture
def mock_ai_generator():
    """Fixture providing a mocked AI generator"""
    mock_ai = Mock()
    mock_ai.generate_response.return_value = "Test AI response"
    return mock_ai


@pytest.fixture
def mock_document_processor():
    """Fixture providing a mocked document processor"""
    mock_processor = Mock()
    test_course = Course(
        title="Test Course",
        instructor="Test Instructor",
        lessons=[Lesson(lesson_number=0, title="Introduction")]
    )
    test_chunks = [
        CourseChunk(content="Test content", course_title="Test Course", chunk_index=0)
    ]
    mock_processor.process_course_document.return_value = (test_course, test_chunks)
    return mock_processor


@pytest.fixture
def mock_session_manager():
    """Fixture providing a mocked session manager"""
    mock_session = Mock()
    mock_session.get_conversation_history.return_value = None
    mock_session.create_session.return_value = "test-session-123"
    return mock_session


@pytest.fixture
def mocked_rag_system(test_config, mock_vector_store, mock_ai_generator, 
                     mock_document_processor, mock_session_manager):
    """Fixture providing a fully mocked RAG system"""
    with patch('rag_system.VectorStore') as mock_vs_class, \
         patch('rag_system.AIGenerator') as mock_ai_class, \
         patch('rag_system.DocumentProcessor') as mock_dp_class, \
         patch('rag_system.SessionManager') as mock_sm_class:
        
        # Configure class mocks to return our instances
        mock_vs_class.return_value = mock_vector_store
        mock_ai_class.return_value = mock_ai_generator
        mock_dp_class.return_value = mock_document_processor
        mock_sm_class.return_value = mock_session_manager
        
        # Create RAG system
        rag_system = RAGSystem(test_config)
        
        # Replace search tool's vector store with our mock
        rag_system.search_tool.store = mock_vector_store
        
        return rag_system


@pytest.fixture
def sample_search_results():
    """Fixture providing sample search results"""
    return SearchResults(
        documents=[
            "Python is a high-level programming language.",
            "Machine learning is a subset of AI."
        ],
        metadata=[
            {"course_title": "Python Fundamentals", "lesson_number": 1},
            {"course_title": "AI Basics", "lesson_number": 3}
        ],
        distances=[0.1, 0.2],
        error=None
    )


@pytest.fixture
def sample_courses():
    """Fixture providing sample course objects"""
    return [
        Course(
            title="Python Fundamentals",
            instructor="John Doe",
            lessons=[
                Lesson(lesson_number=0, title="Introduction to Python"),
                Lesson(lesson_number=1, title="Variables and Data Types")
            ]
        ),
        Course(
            title="AI Basics",
            instructor="Jane Smith",
            lessons=[
                Lesson(lesson_number=0, title="What is AI?"),
                Lesson(lesson_number=1, title="Machine Learning Basics")
            ]
        )
    ]


@pytest.fixture
def sample_course_chunks():
    """Fixture providing sample course chunks"""
    return [
        CourseChunk(
            content="Python is a versatile programming language",
            course_title="Python Fundamentals",
            lesson_number=1,
            chunk_index=0
        ),
        CourseChunk(
            content="Variables store data values in Python",
            course_title="Python Fundamentals", 
            lesson_number=1,
            chunk_index=1
        )
    ]


@pytest.fixture
def temp_directory():
    """Fixture providing a temporary directory for tests"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_api_request_data():
    """Fixture providing sample API request data"""
    return {
        "valid_query": {
            "query": "What is Python programming?",
            "session_id": "test-session-123"
        },
        "query_without_session": {
            "query": "Explain machine learning basics"
        },
        "empty_query": {
            "query": "",
            "session_id": "test-session-123"
        }
    }


@pytest.fixture
def expected_api_responses():
    """Fixture providing expected API response structures"""
    return {
        "successful_query": {
            "answer": "Python is a programming language...",
            "sources": [
                {
                    "text": "Python Fundamentals - Lesson 1",
                    "link": "http://example.com/lesson1"
                }
            ],
            "session_id": "test-session-123"
        },
        "course_stats": {
            "total_courses": 2,
            "course_titles": ["Python Fundamentals", "AI Basics"]
        }
    }


@pytest.fixture(autouse=True)
def cleanup_test_environment():
    """Fixture to clean up test environment after each test"""
    yield
    # Cleanup any test artifacts if needed
    test_chroma_path = Path("./test_chroma_db")
    if test_chroma_path.exists():
        import shutil
        shutil.rmtree(test_chroma_path, ignore_errors=True)