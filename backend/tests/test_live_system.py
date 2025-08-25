"""
Live system tests to identify actual runtime issues with the RAG chatbot.
"""

import os
import sys
import unittest

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from ai_generator import AIGenerator
from config import config
from rag_system import RAGSystem
from search_tools import CourseSearchTool, ToolManager
from vector_store import SearchResults, VectorStore


class TestLiveVectorStore(unittest.TestCase):
    """Test the actual vector store with real ChromaDB data"""

    def setUp(self):
        """Set up live vector store"""
        self.vector_store = VectorStore(
            config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS
        )

    def test_vector_store_connection(self):
        """Test if vector store can connect to ChromaDB"""
        try:
            # Try to get course count - this tests basic connectivity
            course_count = self.vector_store.get_course_count()
            print(f"Found {course_count} courses in vector store")
            self.assertIsInstance(course_count, int)
        except Exception as e:
            self.fail(f"Vector store connection failed: {e}")

    def test_existing_courses_data(self):
        """Test if there are courses in the vector store"""
        try:
            course_titles = self.vector_store.get_existing_course_titles()
            print(f"Course titles: {course_titles}")

            # Should have some courses based on server logs
            self.assertGreater(
                len(course_titles), 0, "No courses found in vector store"
            )

            # Test getting course metadata
            metadata = self.vector_store.get_all_courses_metadata()
            print(f"Course metadata count: {len(metadata)}")
            self.assertGreater(len(metadata), 0, "No course metadata found")

        except Exception as e:
            self.fail(f"Failed to retrieve course data: {e}")

    def test_vector_search_functionality(self):
        """Test basic vector search functionality"""
        try:
            # Test a basic search
            results = self.vector_store.search("Python programming")
            print(f"Search results error: {results.error}")
            print(f"Search results count: {len(results.documents)}")

            if results.error:
                self.fail(f"Vector search failed with error: {results.error}")

            # Should find some results given the course content
            if len(results.documents) == 0:
                print(
                    "WARNING: No search results found - this might indicate indexing issues"
                )
            else:
                print(f"First result: {results.documents[0][:100]}...")

        except Exception as e:
            self.fail(f"Vector search failed: {e}")

    def test_search_with_course_filter(self):
        """Test search with course name filtering"""
        try:
            # Get a course title to test with
            course_titles = self.vector_store.get_existing_course_titles()
            if course_titles:
                test_course = course_titles[0]
                print(f"Testing search with course filter: {test_course}")

                results = self.vector_store.search(
                    "introduction", course_name=test_course
                )

                print(f"Filtered search error: {results.error}")
                print(f"Filtered search results: {len(results.documents)}")

                if results.error:
                    self.fail(f"Filtered search failed: {results.error}")

        except Exception as e:
            self.fail(f"Filtered search test failed: {e}")


class TestLiveSearchTool(unittest.TestCase):
    """Test CourseSearchTool with real vector store"""

    def setUp(self):
        """Set up live search tool"""
        self.vector_store = VectorStore(
            config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS
        )
        self.search_tool = CourseSearchTool(self.vector_store)

    def test_search_tool_basic_query(self):
        """Test CourseSearchTool with basic query"""
        try:
            result = self.search_tool.execute("Python programming")
            print(f"Search tool result length: {len(result)}")
            print(f"Search tool result preview: {result[:200]}...")

            # Should not return an error message
            self.assertNotIn("Search error:", result)
            self.assertNotIn("Database connection", result)

            # Should either have results or a "No relevant content found" message
            if "No relevant content found" in result:
                print("WARNING: Search tool found no relevant content")
            else:
                # Should have formatted results
                self.assertTrue(len(result) > 0)
                print(f"Sources tracked: {len(self.search_tool.last_sources)}")

        except Exception as e:
            self.fail(f"Search tool execution failed: {e}")

    def test_search_tool_with_filters(self):
        """Test CourseSearchTool with course and lesson filters"""
        try:
            # Get available courses
            course_titles = self.vector_store.get_existing_course_titles()
            if course_titles:
                test_course = course_titles[0]

                # Test with course filter
                result = self.search_tool.execute(
                    "introduction", course_name=test_course
                )

                print(f"Filtered search result: {result[:200]}...")

                # Should not be an error
                self.assertNotIn("Search error:", result)

        except Exception as e:
            self.fail(f"Filtered search tool test failed: {e}")


class TestLiveAIGenerator(unittest.TestCase):
    """Test AI generator with actual API (if key is available)"""

    def setUp(self):
        """Set up AI generator"""
        self.ai_generator = AIGenerator(
            config.ANTHROPIC_API_KEY, config.ANTHROPIC_MODEL
        )

    def test_api_key_validation(self):
        """Test if API key is valid and client is initialized"""
        if not self.ai_generator.client:
            print(
                "WARNING: AI Generator client not initialized - likely invalid API key"
            )
            print(f"API Key starts with: {config.ANTHROPIC_API_KEY[:10]}...")
            self.skipTest("No valid API key available for testing")
        else:
            print("AI Generator client successfully initialized")

    def test_simple_response_generation(self):
        """Test simple response generation without tools"""
        if not self.ai_generator.client:
            self.skipTest("No valid API key available")

        try:
            response = self.ai_generator.generate_response("What is 2 + 2?")
            print(f"AI response: {response}")

            self.assertIsInstance(response, str)
            self.assertTrue(len(response) > 0)
            self.assertNotIn("valid Anthropic API key", response)

        except Exception as e:
            self.fail(f"AI response generation failed: {e}")

    def test_response_with_tools(self):
        """Test response generation with tools available"""
        if not self.ai_generator.client:
            self.skipTest("No valid API key available")

        try:
            # Setup tool manager
            vector_store = VectorStore(
                config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS
            )
            search_tool = CourseSearchTool(vector_store)
            tool_manager = ToolManager()
            tool_manager.register_tool(search_tool)

            # Test with a course-related question
            response = self.ai_generator.generate_response(
                "What is Python programming?",
                tools=tool_manager.get_tool_definitions(),
                tool_manager=tool_manager,
            )

            print(f"AI response with tools: {response[:200]}...")

            self.assertIsInstance(response, str)
            self.assertTrue(len(response) > 0)
            self.assertNotIn("valid Anthropic API key", response)

            # Check if sources were generated
            sources = tool_manager.get_last_sources()
            print(f"Sources generated: {len(sources)}")

        except Exception as e:
            self.fail(f"AI response with tools failed: {e}")


class TestLiveRAGSystem(unittest.TestCase):
    """Test complete RAG system with real configuration"""

    def setUp(self):
        """Set up live RAG system"""
        self.rag_system = RAGSystem(config)

    def test_rag_system_initialization(self):
        """Test RAG system initializes without errors"""
        try:
            # Test basic functionality
            analytics = self.rag_system.get_course_analytics()
            print(f"RAG system analytics: {analytics}")

            self.assertIn("total_courses", analytics)
            self.assertIn("course_titles", analytics)

        except Exception as e:
            self.fail(f"RAG system initialization failed: {e}")

    def test_content_query_execution(self):
        """Test actual content query execution (the main issue)"""
        try:
            print("Testing content query that reportedly returns 'query failed'...")

            # Test a typical content query
            response, sources = self.rag_system.query("What is Python programming?")

            print(f"Query response: {response}")
            print(f"Sources count: {len(sources)}")
            if sources:
                print(f"First source: {sources[0]}")

            # This is the key test - should not return "query failed"
            self.assertNotEqual(response.lower(), "query failed")
            self.assertNotIn("query failed", response.lower())

            # Should not be an API key error
            self.assertNotIn("valid Anthropic API key", response)

            # Should be a meaningful response
            self.assertTrue(len(response) > 10)

        except Exception as e:
            print(f"Content query execution failed: {e}")
            # This might be the actual issue - capture it
            self.fail(f"RAG system query failed: {e}")

    def test_general_knowledge_query(self):
        """Test general knowledge query (should work without search)"""
        try:
            response, sources = self.rag_system.query("What is 2 + 2?")

            print(f"General query response: {response}")
            print(f"General query sources: {len(sources)}")

            # Should not fail
            self.assertNotIn("query failed", response.lower())
            self.assertNotIn("valid Anthropic API key", response)

            # Should be a simple answer
            self.assertTrue(len(response) > 0)

        except Exception as e:
            self.fail(f"General knowledge query failed: {e}")

    def test_session_functionality(self):
        """Test session-based queries"""
        try:
            # First query
            response1, _ = self.rag_system.query("Hello", session_id="test_session")
            print(f"Session query 1: {response1}")

            # Follow-up query
            response2, _ = self.rag_system.query(
                "What did I just say?", session_id="test_session"
            )
            print(f"Session query 2: {response2}")

            # Should not fail
            self.assertNotIn("query failed", response1.lower())
            self.assertNotIn("query failed", response2.lower())

        except Exception as e:
            self.fail(f"Session query failed: {e}")


class TestSystemDiagnostics(unittest.TestCase):
    """Diagnostic tests to identify specific failure points"""

    def test_environment_configuration(self):
        """Test environment and configuration"""
        print(f"ChromaDB path exists: {os.path.exists(config.CHROMA_PATH)}")
        print(f"API key configured: {bool(config.ANTHROPIC_API_KEY)}")
        print(
            f"API key format valid: {config.ANTHROPIC_API_KEY.startswith('sk-ant-') if config.ANTHROPIC_API_KEY else False}"
        )
        print(f"Embedding model: {config.EMBEDDING_MODEL}")
        print(f"Max results: {config.MAX_RESULTS}")

        # Basic assertions
        self.assertTrue(
            os.path.exists(config.CHROMA_PATH), "ChromaDB path does not exist"
        )
        self.assertTrue(bool(config.ANTHROPIC_API_KEY), "API key not configured")

    def test_component_dependencies(self):
        """Test if all required components can be imported and initialized"""
        try:
            # Test imports
            import anthropic
            from chromadb import PersistentClient
            from sentence_transformers import SentenceTransformer

            print("All required packages are importable")

            # Test basic initialization
            embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)
            print(f"Embedding model loaded: {type(embedding_model)}")

        except Exception as e:
            self.fail(f"Component dependency test failed: {e}")


if __name__ == "__main__":
    # Run with verbose output to capture all diagnostic information
    unittest.main(verbosity=2)
