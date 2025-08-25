"""
Tests for CourseSearchTool.execute method to identify search functionality issues.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from search_tools import CourseSearchTool, ToolManager
from vector_store import SearchResults


class TestCourseSearchTool(unittest.TestCase):
    """Test CourseSearchTool.execute method with various scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_vector_store = Mock()
        self.search_tool = CourseSearchTool(self.mock_vector_store)

    def test_successful_search_with_results(self):
        """Test successful search returning formatted results"""
        # Mock successful search results
        mock_results = SearchResults(
            documents=[
                "Course content about Python programming",
                "Advanced Python concepts",
            ],
            metadata=[
                {"course_title": "Python Basics", "lesson_number": 1},
                {"course_title": "Python Basics", "lesson_number": 2},
            ],
            distances=[0.1, 0.2],
            error=None,
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = (
            "http://example.com/lesson1"
        )

        # Execute search
        result = self.search_tool.execute("Python programming")

        # Verify results
        self.assertIn("Python Basics", result)
        self.assertIn("Lesson 1", result)
        self.assertIn("Course content about Python programming", result)
        self.assertEqual(len(self.search_tool.last_sources), 2)

    def test_search_with_error(self):
        """Test search that returns an error"""
        # Mock error results
        mock_results = SearchResults(
            documents=[], metadata=[], distances=[], error="Database connection failed"
        )
        self.mock_vector_store.search.return_value = mock_results

        # Execute search
        result = self.search_tool.execute("test query")

        # Verify error is returned
        self.assertEqual(result, "Database connection failed")

    def test_search_with_no_results(self):
        """Test search that returns no results"""
        # Mock empty results
        mock_results = SearchResults(
            documents=[], metadata=[], distances=[], error=None
        )
        self.mock_vector_store.search.return_value = mock_results

        # Execute search
        result = self.search_tool.execute("nonexistent content")

        # Verify empty results message
        self.assertEqual(result, "No relevant content found.")

    def test_search_with_course_filter_no_results(self):
        """Test search with course filter that finds no results"""
        # Mock empty results
        mock_results = SearchResults(
            documents=[], metadata=[], distances=[], error=None
        )
        self.mock_vector_store.search.return_value = mock_results

        # Execute search with course filter
        result = self.search_tool.execute(
            "test query", course_name="Nonexistent Course"
        )

        # Verify filtered empty results message
        self.assertEqual(
            result, "No relevant content found in course 'Nonexistent Course'."
        )

    def test_search_with_lesson_filter_no_results(self):
        """Test search with lesson filter that finds no results"""
        # Mock empty results
        mock_results = SearchResults(
            documents=[], metadata=[], distances=[], error=None
        )
        self.mock_vector_store.search.return_value = mock_results

        # Execute search with lesson filter
        result = self.search_tool.execute("test query", lesson_number=99)

        # Verify filtered empty results message
        self.assertEqual(result, "No relevant content found in lesson 99.")

    def test_search_with_both_filters_no_results(self):
        """Test search with both course and lesson filters that finds no results"""
        # Mock empty results
        mock_results = SearchResults(
            documents=[], metadata=[], distances=[], error=None
        )
        self.mock_vector_store.search.return_value = mock_results

        # Execute search with both filters
        result = self.search_tool.execute(
            "test query", course_name="Test Course", lesson_number=5
        )

        # Verify filtered empty results message
        self.assertEqual(
            result, "No relevant content found in course 'Test Course' in lesson 5."
        )

    def test_search_with_course_filter_success(self):
        """Test successful search with course filtering"""
        # Mock successful search results
        mock_results = SearchResults(
            documents=["Filtered course content"],
            metadata=[{"course_title": "Machine Learning", "lesson_number": 3}],
            distances=[0.1],
            error=None,
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = None

        # Execute search with course filter
        result = self.search_tool.execute("ML concepts", course_name="Machine Learning")

        # Verify search was called with correct parameters
        self.mock_vector_store.search.assert_called_once_with(
            query="ML concepts", course_name="Machine Learning", lesson_number=None
        )

        # Verify results
        self.assertIn("Machine Learning", result)
        self.assertIn("Lesson 3", result)
        self.assertIn("Filtered course content", result)

    def test_search_with_lesson_filter_success(self):
        """Test successful search with lesson filtering"""
        # Mock successful search results
        mock_results = SearchResults(
            documents=["Lesson specific content"],
            metadata=[{"course_title": "Data Science", "lesson_number": 1}],
            distances=[0.15],
            error=None,
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = (
            "http://example.com/lesson1"
        )

        # Execute search with lesson filter
        result = self.search_tool.execute("data analysis", lesson_number=1)

        # Verify search was called with correct parameters
        self.mock_vector_store.search.assert_called_once_with(
            query="data analysis", course_name=None, lesson_number=1
        )

        # Verify results and source tracking
        self.assertIn("Data Science", result)
        self.assertIn("Lesson 1", result)
        self.assertIn("Lesson specific content", result)
        self.assertEqual(len(self.search_tool.last_sources), 1)
        self.assertEqual(
            self.search_tool.last_sources[0]["link"], "http://example.com/lesson1"
        )

    def test_results_formatting_with_missing_metadata(self):
        """Test result formatting when metadata is missing some fields"""
        # Mock results with incomplete metadata
        mock_results = SearchResults(
            documents=["Content with missing metadata"],
            metadata=[{"course_title": "Unknown Course"}],  # Missing lesson_number
            distances=[0.2],
            error=None,
        )
        self.mock_vector_store.search.return_value = mock_results

        # Execute search
        result = self.search_tool.execute("test query")

        # Verify results handle missing metadata gracefully
        self.assertIn("Unknown Course", result)
        self.assertNotIn("Lesson", result)  # Should not include lesson info
        self.assertIn("Content with missing metadata", result)

    def test_results_formatting_with_unknown_course(self):
        """Test result formatting when course_title is missing"""
        # Mock results with missing course_title
        mock_results = SearchResults(
            documents=["Content with unknown course"],
            metadata=[{"lesson_number": 2}],  # Missing course_title
            distances=[0.3],
            error=None,
        )
        self.mock_vector_store.search.return_value = mock_results

        # Execute search
        result = self.search_tool.execute("test query")

        # Verify results handle missing course title gracefully
        self.assertIn("unknown", result)  # Should use 'unknown' as default
        self.assertIn("Lesson 2", result)
        self.assertIn("Content with unknown course", result)

    def test_source_tracking_reset(self):
        """Test that sources are properly tracked and can be reset"""
        # Mock successful search results
        mock_results = SearchResults(
            documents=["Test content"],
            metadata=[{"course_title": "Test Course", "lesson_number": 1}],
            distances=[0.1],
            error=None,
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = "http://example.com/test"

        # Execute search
        self.search_tool.execute("test query")

        # Verify sources are tracked
        self.assertEqual(len(self.search_tool.last_sources), 1)

        # Reset sources
        self.search_tool.last_sources = []
        self.assertEqual(len(self.search_tool.last_sources), 0)


class TestToolManager(unittest.TestCase):
    """Test ToolManager functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool_manager = ToolManager()
        self.mock_vector_store = Mock()
        self.search_tool = CourseSearchTool(self.mock_vector_store)

    def test_register_tool(self):
        """Test tool registration"""
        self.tool_manager.register_tool(self.search_tool)

        # Verify tool is registered
        self.assertIn("search_course_content", self.tool_manager.tools)

    def test_get_tool_definitions(self):
        """Test getting tool definitions for AI"""
        self.tool_manager.register_tool(self.search_tool)

        definitions = self.tool_manager.get_tool_definitions()

        # Verify tool definition structure
        self.assertEqual(len(definitions), 1)
        self.assertEqual(definitions[0]["name"], "search_course_content")
        self.assertIn("description", definitions[0])
        self.assertIn("input_schema", definitions[0])

    def test_execute_tool_success(self):
        """Test successful tool execution through manager"""
        # Setup mock search results
        mock_results = SearchResults(
            documents=["Manager test content"],
            metadata=[{"course_title": "Manager Test", "lesson_number": 1}],
            distances=[0.1],
            error=None,
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = None

        # Register tool and execute
        self.tool_manager.register_tool(self.search_tool)
        result = self.tool_manager.execute_tool(
            "search_course_content", query="test query"
        )

        # Verify execution
        self.assertIn("Manager Test", result)
        self.assertIn("Manager test content", result)

    def test_execute_nonexistent_tool(self):
        """Test executing a tool that doesn't exist"""
        result = self.tool_manager.execute_tool("nonexistent_tool", query="test")

        # Verify error message
        self.assertEqual(result, "Tool 'nonexistent_tool' not found")

    def test_get_last_sources(self):
        """Test retrieving sources from last search"""
        # Setup mock search with sources
        mock_results = SearchResults(
            documents=["Source test content"],
            metadata=[{"course_title": "Source Test", "lesson_number": 2}],
            distances=[0.1],
            error=None,
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = (
            "http://example.com/source"
        )

        # Register tool and execute
        self.tool_manager.register_tool(self.search_tool)
        self.tool_manager.execute_tool("search_course_content", query="test query")

        # Get sources
        sources = self.tool_manager.get_last_sources()

        # Verify sources
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["text"], "Source Test - Lesson 2")
        self.assertEqual(sources[0]["link"], "http://example.com/source")

    def test_reset_sources(self):
        """Test resetting sources across all tools"""
        # Setup and execute search to create sources
        mock_results = SearchResults(
            documents=["Reset test content"],
            metadata=[{"course_title": "Reset Test", "lesson_number": 1}],
            distances=[0.1],
            error=None,
        )
        self.mock_vector_store.search.return_value = mock_results
        self.mock_vector_store.get_lesson_link.return_value = None

        self.tool_manager.register_tool(self.search_tool)
        self.tool_manager.execute_tool("search_course_content", query="test query")

        # Verify sources exist
        self.assertTrue(len(self.tool_manager.get_last_sources()) > 0)

        # Reset sources
        self.tool_manager.reset_sources()

        # Verify sources are cleared
        self.assertEqual(len(self.tool_manager.get_last_sources()), 0)


if __name__ == "__main__":
    unittest.main()
