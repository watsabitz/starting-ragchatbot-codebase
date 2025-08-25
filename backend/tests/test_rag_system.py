"""
Tests for RAG system integration to identify content-query handling issues.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from rag_system import RAGSystem
from vector_store import SearchResults
from models import Course, Lesson, CourseChunk


class MockConfig:
    """Mock configuration for testing"""
    def __init__(self):
        self.CHUNK_SIZE = 800
        self.CHUNK_OVERLAP = 100
        self.CHROMA_PATH = "./test_chroma_db"
        self.EMBEDDING_MODEL = "test-model"
        self.MAX_RESULTS = 5
        self.ANTHROPIC_API_KEY = "sk-ant-test-key"
        self.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
        self.MAX_HISTORY = 2


class TestRAGSystem(unittest.TestCase):
    """Test RAG system integration"""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies"""
        self.config = MockConfig()
        
        # Patch all the external dependencies
        self.vector_store_patcher = patch('rag_system.VectorStore')
        self.ai_generator_patcher = patch('rag_system.AIGenerator')
        self.document_processor_patcher = patch('rag_system.DocumentProcessor')
        self.session_manager_patcher = patch('rag_system.SessionManager')
        
        # Start the patches
        self.mock_vector_store_class = self.vector_store_patcher.start()
        self.mock_ai_generator_class = self.ai_generator_patcher.start()
        self.mock_doc_processor_class = self.document_processor_patcher.start()
        self.mock_session_manager_class = self.session_manager_patcher.start()
        
        # Create mock instances
        self.mock_vector_store = Mock()
        self.mock_ai_generator = Mock()
        self.mock_doc_processor = Mock()
        self.mock_session_manager = Mock()
        
        # Configure the class mocks to return our instances
        self.mock_vector_store_class.return_value = self.mock_vector_store
        self.mock_ai_generator_class.return_value = self.mock_ai_generator
        self.mock_doc_processor_class.return_value = self.mock_doc_processor
        self.mock_session_manager_class.return_value = self.mock_session_manager
        
        # Create RAG system
        self.rag_system = RAGSystem(self.config)
        
    def tearDown(self):
        """Clean up patches"""
        self.vector_store_patcher.stop()
        self.ai_generator_patcher.stop()
        self.document_processor_patcher.stop()
        self.session_manager_patcher.stop()
        
    def test_rag_system_initialization(self):
        """Test RAG system initializes all components correctly"""
        # Verify all components were initialized with correct parameters
        self.mock_doc_processor_class.assert_called_once_with(
            self.config.CHUNK_SIZE, 
            self.config.CHUNK_OVERLAP
        )
        self.mock_vector_store_class.assert_called_once_with(
            self.config.CHROMA_PATH, 
            self.config.EMBEDDING_MODEL, 
            self.config.MAX_RESULTS
        )
        self.mock_ai_generator_class.assert_called_once_with(
            self.config.ANTHROPIC_API_KEY, 
            self.config.ANTHROPIC_MODEL
        )
        self.mock_session_manager_class.assert_called_once_with(
            self.config.MAX_HISTORY
        )
        
        # Verify search tool is registered
        self.assertIsNotNone(self.rag_system.search_tool)
        self.assertIsNotNone(self.rag_system.tool_manager)
        
    def test_query_without_session(self):
        """Test query processing without session ID"""
        # Setup mocks
        self.mock_ai_generator.generate_response.return_value = "Test response"
        self.rag_system.tool_manager.get_last_sources = Mock(return_value=[])
        self.rag_system.tool_manager.reset_sources = Mock()
        
        # Execute query
        response, sources = self.rag_system.query("What is Python?")
        
        # Verify response
        self.assertEqual(response, "Test response")
        self.assertEqual(sources, [])
        
        # Verify AI generator was called correctly
        self.mock_ai_generator.generate_response.assert_called_once()
        call_args = self.mock_ai_generator.generate_response.call_args
        
        # Check the query was formatted correctly
        self.assertIn("Answer this question about course materials: What is Python?", 
                     call_args.kwargs["query"])
        
        # Check no conversation history
        self.assertIsNone(call_args.kwargs["conversation_history"])
        
        # Check tools were provided
        self.assertIsNotNone(call_args.kwargs["tools"])
        self.assertIsNotNone(call_args.kwargs["tool_manager"])
        
        # Verify session manager was not used
        self.mock_session_manager.get_conversation_history.assert_not_called()
        self.mock_session_manager.add_exchange.assert_not_called()
        
    def test_query_with_session(self):
        """Test query processing with session ID"""
        # Setup mocks
        self.mock_session_manager.get_conversation_history.return_value = "Previous: Hello\nResponse: Hi there"
        self.mock_ai_generator.generate_response.return_value = "Response with history"
        self.rag_system.tool_manager.get_last_sources = Mock(return_value=[
            {"text": "Course A - Lesson 1", "link": "http://example.com"}
        ])
        self.rag_system.tool_manager.reset_sources = Mock()
        
        # Execute query with session
        response, sources = self.rag_system.query("Continue discussion", session_id="session_123")
        
        # Verify response
        self.assertEqual(response, "Response with history")
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["text"], "Course A - Lesson 1")
        
        # Verify session management
        self.mock_session_manager.get_conversation_history.assert_called_once_with("session_123")
        self.mock_session_manager.add_exchange.assert_called_once_with(
            "session_123", "Continue discussion", "Response with history"
        )
        
        # Verify AI generator received history
        call_args = self.mock_ai_generator.generate_response.call_args
        self.assertEqual(call_args.kwargs["conversation_history"], "Previous: Hello\nResponse: Hi there")
        
    def test_query_with_sources_from_search(self):
        """Test query that returns sources from search tool"""
        # Setup mocks for successful search
        mock_sources = [
            {"text": "Machine Learning Course - Lesson 2", "link": "http://ml-course.com/lesson2"},
            {"text": "Python Basics - Lesson 1", "link": None}
        ]
        
        self.mock_ai_generator.generate_response.return_value = "Based on the course material..."
        self.rag_system.tool_manager.get_last_sources = Mock(return_value=mock_sources)
        self.rag_system.tool_manager.reset_sources = Mock()
        
        # Execute query
        response, sources = self.rag_system.query("Explain machine learning")
        
        # Verify sources are returned
        self.assertEqual(response, "Based on the course material...")
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0]["text"], "Machine Learning Course - Lesson 2")
        self.assertEqual(sources[0]["link"], "http://ml-course.com/lesson2")
        self.assertEqual(sources[1]["text"], "Python Basics - Lesson 1")
        self.assertIsNone(sources[1]["link"])
        
        # Verify sources were retrieved and reset
        self.rag_system.tool_manager.get_last_sources.assert_called_once()
        self.rag_system.tool_manager.reset_sources.assert_called_once()
        
    def test_query_ai_generator_failure(self):
        """Test query handling when AI generator fails"""
        # Setup AI generator to raise exception
        self.mock_ai_generator.generate_response.side_effect = Exception("API Error")
        
        # Execute query - should raise exception
        with self.assertRaises(Exception) as context:
            self.rag_system.query("Test query")
            
        self.assertIn("API Error", str(context.exception))
        
    def test_query_tool_manager_interaction(self):
        """Test that query properly interacts with tool manager"""
        # Setup mocks
        self.mock_ai_generator.generate_response.return_value = "Tool-based response"
        
        # Mock tool manager methods
        mock_tool_definitions = [{"name": "search_course_content", "description": "Search courses"}]
        self.rag_system.tool_manager.get_tool_definitions = Mock(return_value=mock_tool_definitions)
        self.rag_system.tool_manager.get_last_sources = Mock(return_value=[])
        self.rag_system.tool_manager.reset_sources = Mock()
        
        # Execute query
        response, sources = self.rag_system.query("Search for Python course")
        
        # Verify tool interactions
        self.rag_system.tool_manager.get_tool_definitions.assert_called_once()
        
        # Verify AI generator received tool definitions and manager
        call_args = self.mock_ai_generator.generate_response.call_args
        self.assertEqual(call_args.kwargs["tools"], mock_tool_definitions)
        self.assertEqual(call_args.kwargs["tool_manager"], self.rag_system.tool_manager)
        
    def test_add_course_document_success(self):
        """Test successful course document addition"""
        # Setup mocks
        mock_course = Course(title="Test Course", instructor="Test Instructor")
        mock_chunks = [
            CourseChunk(content="Chunk 1", course_title="Test Course", chunk_index=0),
            CourseChunk(content="Chunk 2", course_title="Test Course", chunk_index=1)
        ]
        
        self.mock_doc_processor.process_course_document.return_value = (mock_course, mock_chunks)
        
        # Execute
        course, chunk_count = self.rag_system.add_course_document("test.pdf")
        
        # Verify results
        self.assertEqual(course.title, "Test Course")
        self.assertEqual(chunk_count, 2)
        
        # Verify document processing
        self.mock_doc_processor.process_course_document.assert_called_once_with("test.pdf")
        
        # Verify vector store updates
        self.mock_vector_store.add_course_metadata.assert_called_once_with(mock_course)
        self.mock_vector_store.add_course_content.assert_called_once_with(mock_chunks)
        
    def test_add_course_document_failure(self):
        """Test course document addition failure handling"""
        # Setup document processor to raise exception
        self.mock_doc_processor.process_course_document.side_effect = Exception("File not found")
        
        # Execute
        course, chunk_count = self.rag_system.add_course_document("nonexistent.pdf")
        
        # Verify failure handling
        self.assertIsNone(course)
        self.assertEqual(chunk_count, 0)
        
        # Vector store should not be called
        self.mock_vector_store.add_course_metadata.assert_not_called()
        self.mock_vector_store.add_course_content.assert_not_called()
        
    def test_get_course_analytics(self):
        """Test course analytics retrieval"""
        # Setup mock vector store
        self.mock_vector_store.get_course_count.return_value = 3
        self.mock_vector_store.get_existing_course_titles.return_value = [
            "Course A", "Course B", "Course C"
        ]
        
        # Execute
        analytics = self.rag_system.get_course_analytics()
        
        # Verify results
        self.assertEqual(analytics["total_courses"], 3)
        self.assertEqual(len(analytics["course_titles"]), 3)
        self.assertIn("Course A", analytics["course_titles"])
        
        # Verify vector store calls
        self.mock_vector_store.get_course_count.assert_called_once()
        self.mock_vector_store.get_existing_course_titles.assert_called_once()


class TestRAGSystemSearchTool(unittest.TestCase):
    """Test RAG system search tool integration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = MockConfig()
        
        # Only patch external dependencies, not search tools
        with patch('rag_system.VectorStore'), \
             patch('rag_system.AIGenerator'), \
             patch('rag_system.DocumentProcessor'), \
             patch('rag_system.SessionManager'):
            self.rag_system = RAGSystem(self.config)
        
        # Mock the vector store for search tool
        self.rag_system.vector_store = Mock()
        self.rag_system.search_tool.store = self.rag_system.vector_store
        
    def test_search_tool_registration(self):
        """Test that search tool is properly registered"""
        # Verify tool is registered in tool manager
        tool_definitions = self.rag_system.tool_manager.get_tool_definitions()
        self.assertEqual(len(tool_definitions), 1)
        self.assertEqual(tool_definitions[0]["name"], "search_course_content")
        
    def test_search_tool_execution_success(self):
        """Test successful search tool execution through tool manager"""
        # Setup mock search results
        mock_results = SearchResults(
            documents=["Python is a programming language"],
            metadata=[{"course_title": "Python Course", "lesson_number": 1}],
            distances=[0.1],
            error=None
        )
        self.rag_system.vector_store.search.return_value = mock_results
        self.rag_system.vector_store.get_lesson_link.return_value = None
        
        # Execute through tool manager
        result = self.rag_system.tool_manager.execute_tool(
            "search_course_content", 
            query="What is Python?"
        )
        
        # Verify result
        self.assertIn("Python Course", result)
        self.assertIn("Lesson 1", result)
        self.assertIn("Python is a programming language", result)
        
        # Verify sources were tracked
        sources = self.rag_system.tool_manager.get_last_sources()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["text"], "Python Course - Lesson 1")
        
    def test_search_tool_execution_error(self):
        """Test search tool execution with vector store error"""
        # Setup mock error results
        mock_results = SearchResults(
            documents=[],
            metadata=[],
            distances=[],
            error="Vector store connection failed"
        )
        self.rag_system.vector_store.search.return_value = mock_results
        
        # Execute through tool manager
        result = self.rag_system.tool_manager.execute_tool(
            "search_course_content", 
            query="test query"
        )
        
        # Verify error is returned
        self.assertEqual(result, "Vector store connection failed")
        
        # Verify no sources were created
        sources = self.rag_system.tool_manager.get_last_sources()
        self.assertEqual(len(sources), 0)
        
    def test_search_tool_empty_results(self):
        """Test search tool execution with no results"""
        # Setup mock empty results
        mock_results = SearchResults(
            documents=[],
            metadata=[],
            distances=[],
            error=None
        )
        self.rag_system.vector_store.search.return_value = mock_results
        
        # Execute through tool manager
        result = self.rag_system.tool_manager.execute_tool(
            "search_course_content", 
            query="nonexistent topic"
        )
        
        # Verify empty results message
        self.assertEqual(result, "No relevant content found.")


class TestRAGSystemIntegrationScenarios(unittest.TestCase):
    """Test real-world integration scenarios"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = MockConfig()
        
        # Mock all dependencies
        with patch('rag_system.VectorStore') as mock_vs, \
             patch('rag_system.AIGenerator') as mock_ai, \
             patch('rag_system.DocumentProcessor') as mock_dp, \
             patch('rag_system.SessionManager') as mock_sm:
            
            self.mock_vector_store = Mock()
            self.mock_ai_generator = Mock()
            
            mock_vs.return_value = self.mock_vector_store
            mock_ai.return_value = self.mock_ai_generator
            mock_dp.return_value = Mock()
            mock_sm.return_value = Mock()
            
            self.rag_system = RAGSystem(self.config)
            
        # Replace search tool's vector store with our mock
        self.rag_system.search_tool.store = self.mock_vector_store
        
    def test_content_query_success_scenario(self):
        """Test successful content query end-to-end"""
        # Setup vector store to return relevant content
        mock_results = SearchResults(
            documents=["Python is a high-level programming language"],
            metadata=[{"course_title": "Programming Fundamentals", "lesson_number": 2}],
            distances=[0.15],
            error=None
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = "http://course.com/lesson2"
        
        # Setup AI generator to simulate tool use
        self.mock_ai_generator.generate_response.return_value = "Python is a versatile programming language used for web development, data science, and automation."
        
        # Execute query
        response, sources = self.rag_system.query("What is Python programming?")
        
        # Verify successful response
        self.assertIn("programming language", response.lower())
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["text"], "Programming Fundamentals - Lesson 2")
        self.assertEqual(sources[0]["link"], "http://course.com/lesson2")
        
    def test_content_query_failure_scenario(self):
        """Test content query failure scenarios"""
        # Scenario 1: Vector store error
        mock_results = SearchResults(
            documents=[],
            metadata=[],
            distances=[],
            error="Database connection timeout"
        )
        self.mock_vector_store.search.return_value = mock_results
        
        # AI should still generate response even if search fails
        self.mock_ai_generator.generate_response.return_value = "I encountered an issue searching the course materials."
        
        # Execute query
        response, sources = self.rag_system.query("Explain machine learning")
        
        # Verify graceful failure handling
        self.assertIn("issue", response.lower())
        self.assertEqual(len(sources), 0)
        
    def test_api_key_missing_scenario(self):
        """Test scenario where API key is missing or invalid"""
        # Setup AI generator to return API key error
        self.mock_ai_generator.generate_response.return_value = "I'm sorry, but I need a valid Anthropic API key to generate responses. Please set a valid ANTHROPIC_API_KEY in your .env file."
        
        # Execute query
        response, sources = self.rag_system.query("Any question")
        
        # Verify API key error is handled
        self.assertIn("valid Anthropic API key", response)
        self.assertIn(".env file", response)


if __name__ == "__main__":
    unittest.main()