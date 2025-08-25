"""
Tests for AIGenerator to identify tool calling and API communication issues.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, Mock, patch

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from ai_generator import AIGenerator


class MockAnthropicContent:
    """Mock Anthropic content block for tool use"""

    def __init__(
        self, content_type, text=None, name=None, input_data=None, tool_use_id=None
    ):
        self.type = content_type
        self.text = text
        self.name = name
        self.input = input_data or {}
        self.id = tool_use_id


class MockAnthropicResponse:
    """Mock Anthropic API response"""

    def __init__(self, content_blocks, stop_reason="end_turn"):
        self.content = content_blocks
        self.stop_reason = stop_reason


class TestAIGenerator(unittest.TestCase):
    """Test AIGenerator functionality"""

    def setUp(self):
        """Set up test fixtures"""
        # Test with valid-looking API key
        self.ai_generator = AIGenerator("sk-ant-test-key", "claude-sonnet-4-20250514")

    def test_initialization_with_valid_key(self):
        """Test AIGenerator initialization with valid API key"""
        ai_gen = AIGenerator("sk-ant-valid-key", "claude-sonnet-4-20250514")

        # Should initialize client (even though it's mocked)
        self.assertEqual(ai_gen.api_key, "sk-ant-valid-key")
        self.assertEqual(ai_gen.model, "claude-sonnet-4-20250514")

    def test_initialization_with_invalid_key(self):
        """Test AIGenerator initialization with invalid API key"""
        ai_gen = AIGenerator("invalid-key", "claude-sonnet-4-20250514")

        # Should not initialize client
        self.assertIsNone(ai_gen.client)

    def test_initialization_with_placeholder_key(self):
        """Test AIGenerator initialization with placeholder API key"""
        ai_gen = AIGenerator("sk-ant-placeholder-key", "claude-sonnet-4-20250514")

        # Should not initialize client due to placeholder detection
        self.assertIsNone(ai_gen.client)

    def test_generate_response_without_client(self):
        """Test response generation when client is not initialized"""
        ai_gen = AIGenerator("invalid-key", "claude-sonnet-4-20250514")

        response = ai_gen.generate_response("Test query")

        # Should return API key error message
        self.assertIn("valid Anthropic API key", response)
        self.assertIn(".env file", response)

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_simple_text(self, mock_anthropic_class):
        """Test simple text response generation"""
        # Setup mock client and response
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MockAnthropicResponse(
            [MockAnthropicContent("text", text="This is a simple response")]
        )
        mock_client.messages.create.return_value = mock_response

        # Create AI generator and generate response
        ai_gen = AIGenerator("sk-ant-test-key", "claude-sonnet-4-20250514")
        ai_gen.client = mock_client

        response = ai_gen.generate_response("What is Python?")

        # Verify response
        self.assertEqual(response, "This is a simple response")

        # Verify API call parameters
        call_args = mock_client.messages.create.call_args
        self.assertEqual(call_args.kwargs["model"], "claude-sonnet-4-20250514")
        self.assertEqual(call_args.kwargs["temperature"], 0)
        self.assertEqual(call_args.kwargs["max_tokens"], 800)
        self.assertIn("What is Python?", call_args.kwargs["messages"][0]["content"])

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_with_conversation_history(self, mock_anthropic_class):
        """Test response generation with conversation history"""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MockAnthropicResponse(
            [MockAnthropicContent("text", text="Response with history")]
        )
        mock_client.messages.create.return_value = mock_response

        # Create AI generator
        ai_gen = AIGenerator("sk-ant-test-key", "claude-sonnet-4-20250514")
        ai_gen.client = mock_client

        # Generate response with history
        history = "Previous: What is ML? Answer: Machine Learning basics..."
        response = ai_gen.generate_response(
            "Tell me more", conversation_history=history
        )

        # Verify response
        self.assertEqual(response, "Response with history")

        # Verify history was included in system prompt
        call_args = mock_client.messages.create.call_args
        system_content = call_args.kwargs["system"]
        self.assertIn("Previous conversation:", system_content)
        self.assertIn("What is ML?", system_content)

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_with_tools_no_tool_use(self, mock_anthropic_class):
        """Test response generation with tools available but not used"""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MockAnthropicResponse(
            [MockAnthropicContent("text", text="General knowledge response")],
            stop_reason="end_turn",
        )
        mock_client.messages.create.return_value = mock_response

        # Create AI generator and mock tool manager
        ai_gen = AIGenerator("sk-ant-test-key", "claude-sonnet-4-20250514")
        ai_gen.client = mock_client

        mock_tools = [{"name": "search_tool", "description": "Search courses"}]
        mock_tool_manager = Mock()

        # Generate response
        response = ai_gen.generate_response(
            "What is 2+2?", tools=mock_tools, tool_manager=mock_tool_manager
        )

        # Verify response
        self.assertEqual(response, "General knowledge response")

        # Verify tools were provided to API
        call_args = mock_client.messages.create.call_args
        self.assertEqual(call_args.kwargs["tools"], mock_tools)
        self.assertEqual(call_args.kwargs["tool_choice"], {"type": "auto"})

        # Tool manager should not be called
        mock_tool_manager.execute_tool.assert_not_called()

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_with_tool_use(self, mock_anthropic_class):
        """Test response generation when AI uses tools"""
        # Setup mock client
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock initial response with tool use
        initial_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="search_course_content",
                    input_data={"query": "Python basics"},
                    tool_use_id="tool_1",
                )
            ],
            stop_reason="tool_use",
        )

        # Mock final response after tool execution
        final_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "text", text="Based on the course content, Python is..."
                )
            ]
        )

        # Setup client to return both responses
        mock_client.messages.create.side_effect = [initial_response, final_response]

        # Create AI generator and mock tool manager
        ai_gen = AIGenerator("sk-ant-test-key", "claude-sonnet-4-20250514")
        ai_gen.client = mock_client

        mock_tools = [
            {"name": "search_course_content", "description": "Search courses"}
        ]
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = (
            "Course content about Python programming"
        )

        # Generate response
        response = ai_gen.generate_response(
            "What is Python?", tools=mock_tools, tool_manager=mock_tool_manager
        )

        # Verify final response
        self.assertEqual(response, "Based on the course content, Python is...")

        # Verify tool was executed
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", query="Python basics"
        )

        # Verify two API calls were made
        self.assertEqual(mock_client.messages.create.call_count, 2)

    @patch("ai_generator.anthropic.Anthropic")
    def test_generate_response_tool_execution_failure(self, mock_anthropic_class):
        """Test response generation when tool execution fails"""
        # Setup mock client
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock initial response with tool use
        initial_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="search_course_content",
                    input_data={"query": "test"},
                    tool_use_id="tool_1",
                )
            ],
            stop_reason="tool_use",
        )

        # Mock final response after tool execution
        final_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "text", text="I couldn't find relevant course content."
                )
            ]
        )

        mock_client.messages.create.side_effect = [initial_response, final_response]

        # Create AI generator and mock tool manager that returns error
        ai_gen = AIGenerator("sk-ant-test-key", "claude-sonnet-4-20250514")
        ai_gen.client = mock_client

        mock_tools = [
            {"name": "search_course_content", "description": "Search courses"}
        ]
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = (
            "Search error: Database connection failed"
        )

        # Generate response
        response = ai_gen.generate_response(
            "Find course content", tools=mock_tools, tool_manager=mock_tool_manager
        )

        # Verify response handles tool error
        self.assertEqual(response, "I couldn't find relevant course content.")

        # Verify tool was called and returned error
        mock_tool_manager.execute_tool.assert_called_once()

    @patch("ai_generator.anthropic.Anthropic")
    def test_handle_tool_execution_message_construction(self, mock_anthropic_class):
        """Test proper message construction during tool execution"""
        # Setup mock client
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock responses
        initial_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="test_tool",
                    input_data={"param": "value"},
                    tool_use_id="tool_1",
                )
            ],
            stop_reason="tool_use",
        )

        final_response = MockAnthropicResponse(
            [MockAnthropicContent("text", text="Final response")]
        )

        mock_client.messages.create.side_effect = [initial_response, final_response]

        # Create AI generator
        ai_gen = AIGenerator("sk-ant-test-key", "claude-sonnet-4-20250514")
        ai_gen.client = mock_client

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        # Generate response
        response = ai_gen.generate_response(
            "Test query", tools=[{"name": "test_tool"}], tool_manager=mock_tool_manager
        )

        # Verify final API call structure
        final_call_args = mock_client.messages.create.call_args_list[1]
        messages = final_call_args.kwargs["messages"]

        # Should have: user message, assistant tool use, tool result
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[2]["role"], "user")

        # Tool result message should have correct structure
        tool_result_content = messages[2]["content"][0]
        self.assertEqual(tool_result_content["type"], "tool_result")
        self.assertEqual(tool_result_content["tool_use_id"], "tool_1")
        self.assertEqual(tool_result_content["content"], "Tool result")

    @patch("ai_generator.anthropic.Anthropic")
    def test_multiple_tool_calls(self, mock_anthropic_class):
        """Test handling multiple tool calls in one response"""
        # Setup mock client
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock initial response with multiple tool uses
        initial_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="tool_1",
                    input_data={"query": "test1"},
                    tool_use_id="call_1",
                ),
                MockAnthropicContent(
                    "tool_use",
                    name="tool_2",
                    input_data={"query": "test2"},
                    tool_use_id="call_2",
                ),
            ],
            stop_reason="tool_use",
        )

        final_response = MockAnthropicResponse(
            [MockAnthropicContent("text", text="Multiple tools used")]
        )

        mock_client.messages.create.side_effect = [initial_response, final_response]

        # Create AI generator
        ai_gen = AIGenerator("sk-ant-test-key", "claude-sonnet-4-20250514")
        ai_gen.client = mock_client

        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = ["Result 1", "Result 2"]

        # Generate response
        response = ai_gen.generate_response(
            "Use multiple tools",
            tools=[{"name": "tool_1"}, {"name": "tool_2"}],
            tool_manager=mock_tool_manager,
        )

        # Verify response
        self.assertEqual(response, "Multiple tools used")

        # Verify both tools were called
        self.assertEqual(mock_tool_manager.execute_tool.call_count, 2)

        # Verify final message structure includes both tool results
        final_call_args = mock_client.messages.create.call_args_list[1]
        tool_results = final_call_args.kwargs["messages"][2]["content"]
        self.assertEqual(len(tool_results), 2)

    @patch("ai_generator.anthropic.Anthropic")
    def test_api_call_exception_handling(self, mock_anthropic_class):
        """Test handling of API call exceptions"""
        # Setup mock client that raises exception
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API Error")

        # Create AI generator
        ai_gen = AIGenerator("sk-ant-test-key", "claude-sonnet-4-20250514")
        ai_gen.client = mock_client

        # Should raise exception when API call fails
        with self.assertRaises(Exception):
            ai_gen.generate_response("Test query")


class TestAIGeneratorSystemPrompt(unittest.TestCase):
    """Test AIGenerator system prompt functionality"""

    def test_system_prompt_content(self):
        """Test that system prompt contains expected instructions"""
        ai_gen = AIGenerator("sk-ant-test-key", "claude-sonnet-4-20250514")

        prompt = ai_gen.SYSTEM_PROMPT

        # Verify key instructions are present
        self.assertIn("search tool", prompt.lower())
        self.assertIn("course content", prompt.lower())
        self.assertIn("educational", prompt.lower())
        self.assertIn("up to 2 sequential searches", prompt.lower())
        self.assertIn("sequential search examples", prompt.lower())

    def test_system_prompt_with_history_formatting(self):
        """Test system prompt formatting with conversation history"""
        ai_gen = AIGenerator("sk-ant-test-key", "claude-sonnet-4-20250514")

        history = "User: What is Python?\nAssistant: Python is a programming language."

        # Simulate how system content is built in generate_response
        system_content = f"{ai_gen.SYSTEM_PROMPT}\n\nPrevious conversation:\n{history}"

        # Verify proper formatting
        self.assertIn("Previous conversation:", system_content)
        self.assertIn("What is Python?", system_content)
        self.assertIn("programming language", system_content)


class TestSequentialToolCalling(unittest.TestCase):
    """Test sequential tool calling functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.ai_generator = AIGenerator("sk-ant-test-key", "claude-sonnet-4-20250514")

    @patch("ai_generator.anthropic.Anthropic")
    def test_single_round_backward_compatibility(self, mock_anthropic_class):
        """Test that single-round tool execution still works (backward compatibility)"""
        # Setup mock client
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock single tool use response followed by final response
        tool_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="search_tool",
                    input_data={"query": "test"},
                    tool_use_id="tool_1",
                )
            ],
            stop_reason="tool_use",
        )

        final_response = MockAnthropicResponse(
            [MockAnthropicContent("text", text="Single round response")],
            stop_reason="end_turn",
        )

        mock_client.messages.create.side_effect = [tool_response, final_response]

        # Setup AI generator and tools
        self.ai_generator.client = mock_client
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        # Execute
        response = self.ai_generator.generate_response(
            "Test query",
            tools=[{"name": "search_tool"}],
            tool_manager=mock_tool_manager,
        )

        # Verify
        self.assertEqual(response, "Single round response")
        self.assertEqual(mock_client.messages.create.call_count, 2)
        mock_tool_manager.execute_tool.assert_called_once()

    @patch("ai_generator.anthropic.Anthropic")
    def test_two_round_sequential_execution(self, mock_anthropic_class):
        """Test two-round sequential tool execution"""
        # Setup mock client
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock responses for 2-round execution
        initial_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="search_tool",
                    input_data={"query": "course X lesson 4"},
                    tool_use_id="tool_1",
                )
            ],
            stop_reason="tool_use",
        )

        second_round_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="search_tool",
                    input_data={"query": "related courses"},
                    tool_use_id="tool_2",
                )
            ],
            stop_reason="tool_use",
        )

        final_response = MockAnthropicResponse(
            [MockAnthropicContent("text", text="Two round final response")],
            stop_reason="end_turn",
        )

        mock_client.messages.create.side_effect = [
            initial_response,
            second_round_response,
            final_response,
        ]

        # Setup AI generator and tools
        self.ai_generator.client = mock_client
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = [
            "First tool result",
            "Second tool result",
        ]

        # Execute
        response = self.ai_generator.generate_response(
            "Find courses related to lesson 4 of course X",
            tools=[{"name": "search_tool"}],
            tool_manager=mock_tool_manager,
        )

        # Verify
        self.assertEqual(response, "Two round final response")
        self.assertEqual(mock_client.messages.create.call_count, 3)
        self.assertEqual(mock_tool_manager.execute_tool.call_count, 2)

    @patch("ai_generator.anthropic.Anthropic")
    def test_termination_after_max_rounds(self, mock_anthropic_class):
        """Test termination after maximum 2 rounds"""
        # Setup mock client
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock responses - AI keeps requesting tools
        round_1_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="search_tool",
                    input_data={"query": "query1"},
                    tool_use_id="tool_1",
                )
            ],
            stop_reason="tool_use",
        )

        round_2_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="search_tool",
                    input_data={"query": "query2"},
                    tool_use_id="tool_2",
                )
            ],
            stop_reason="tool_use",
        )

        # Final response after max rounds
        final_response = MockAnthropicResponse(
            [MockAnthropicContent("text", text="Max rounds reached response")],
            stop_reason="end_turn",
        )

        mock_client.messages.create.side_effect = [
            round_1_response,
            round_2_response,
            final_response,
        ]

        # Setup AI generator and tools
        self.ai_generator.client = mock_client
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        # Execute
        response = self.ai_generator.generate_response(
            "Complex query",
            tools=[{"name": "search_tool"}],
            tool_manager=mock_tool_manager,
        )

        # Verify termination after 2 rounds
        self.assertEqual(response, "Max rounds reached response")
        self.assertEqual(mock_client.messages.create.call_count, 3)
        self.assertEqual(mock_tool_manager.execute_tool.call_count, 2)

    @patch("ai_generator.anthropic.Anthropic")
    def test_termination_no_tool_use_blocks(self, mock_anthropic_class):
        """Test termination when AI doesn't request more tools"""
        # Setup mock client
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock responses - first tool use, then final response
        tool_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="search_tool",
                    input_data={"query": "test"},
                    tool_use_id="tool_1",
                )
            ],
            stop_reason="tool_use",
        )

        # Second response has no tool_use blocks
        final_response = MockAnthropicResponse(
            [MockAnthropicContent("text", text="Final response without tools")],
            stop_reason="end_turn",
        )

        mock_client.messages.create.side_effect = [tool_response, final_response]

        # Setup AI generator and tools
        self.ai_generator.client = mock_client
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        # Execute
        response = self.ai_generator.generate_response(
            "Test query",
            tools=[{"name": "search_tool"}],
            tool_manager=mock_tool_manager,
        )

        # Verify early termination
        self.assertEqual(response, "Final response without tools")
        self.assertEqual(mock_client.messages.create.call_count, 2)
        self.assertEqual(mock_tool_manager.execute_tool.call_count, 1)

    @patch("ai_generator.anthropic.Anthropic")
    def test_termination_on_tool_failure(self, mock_anthropic_class):
        """Test graceful termination when tool execution fails"""
        # Setup mock client
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock tool use response
        tool_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="search_tool",
                    input_data={"query": "test"},
                    tool_use_id="tool_1",
                )
            ],
            stop_reason="tool_use",
        )

        # Mock final response after tool failure
        final_response = MockAnthropicResponse(
            [MockAnthropicContent("text", text="Response despite tool failure")],
            stop_reason="end_turn",
        )

        mock_client.messages.create.side_effect = [tool_response, final_response]

        # Setup AI generator with failing tool
        self.ai_generator.client = mock_client
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = Exception("Tool failed")

        # Execute
        response = self.ai_generator.generate_response(
            "Test query",
            tools=[{"name": "search_tool"}],
            tool_manager=mock_tool_manager,
        )

        # Verify graceful handling
        self.assertEqual(response, "Response despite tool failure")
        self.assertEqual(mock_client.messages.create.call_count, 2)
        mock_tool_manager.execute_tool.assert_called_once()

    @patch("ai_generator.anthropic.Anthropic")
    def test_context_preservation_across_rounds(self, mock_anthropic_class):
        """Test that conversation context is preserved between rounds"""
        # Setup mock client
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock two-round execution
        initial_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="search_tool",
                    input_data={"query": "first search"},
                    tool_use_id="tool_1",
                )
            ],
            stop_reason="tool_use",
        )

        second_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="search_tool",
                    input_data={"query": "second search"},
                    tool_use_id="tool_2",
                )
            ],
            stop_reason="tool_use",
        )

        final_response = MockAnthropicResponse(
            [MockAnthropicContent("text", text="Context preserved response")],
            stop_reason="end_turn",
        )

        mock_client.messages.create.side_effect = [
            initial_response,
            second_response,
            final_response,
        ]

        # Setup AI generator with conversation history
        self.ai_generator.client = mock_client
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        # Execute with history
        response = self.ai_generator.generate_response(
            "Current query",
            conversation_history="Previous: Hello\nAssistant: Hi there",
            tools=[{"name": "search_tool"}],
            tool_manager=mock_tool_manager,
        )

        # Verify context preservation
        self.assertEqual(response, "Context preserved response")

        # Check that all API calls included conversation history
        for call_args in mock_client.messages.create.call_args_list:
            system_content = call_args.kwargs["system"]
            self.assertIn("Previous conversation:", system_content)
            self.assertIn("Hello", system_content)

    @patch("ai_generator.anthropic.Anthropic")
    def test_message_history_construction(self, mock_anthropic_class):
        """Test proper message history construction across rounds"""
        # Setup mock client
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock two-round execution
        initial_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="search_tool",
                    input_data={"query": "test"},
                    tool_use_id="tool_1",
                )
            ],
            stop_reason="tool_use",
        )

        final_response = MockAnthropicResponse(
            [MockAnthropicContent("text", text="Final")], stop_reason="end_turn"
        )

        mock_client.messages.create.side_effect = [initial_response, final_response]

        # Setup AI generator
        self.ai_generator.client = mock_client
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        # Execute
        self.ai_generator.generate_response(
            "Test query",
            tools=[{"name": "search_tool"}],
            tool_manager=mock_tool_manager,
        )

        # Verify message structure in final API call
        final_call = mock_client.messages.create.call_args_list[1]
        messages = final_call.kwargs["messages"]

        # Should have: user query, assistant tool use, tool results
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[2]["role"], "user")

    @patch("ai_generator.anthropic.Anthropic")
    def test_tools_preserved_across_rounds(self, mock_anthropic_class):
        """Test that tools parameter is preserved in subsequent API calls"""
        # Setup mock client
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock two-round execution
        initial_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="search_tool",
                    input_data={"query": "test"},
                    tool_use_id="tool_1",
                )
            ],
            stop_reason="tool_use",
        )

        second_response = MockAnthropicResponse(
            [MockAnthropicContent("text", text="Final response")],
            stop_reason="end_turn",
        )

        mock_client.messages.create.side_effect = [initial_response, second_response]

        # Setup AI generator
        self.ai_generator.client = mock_client
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result"

        # Execute
        self.ai_generator.generate_response(
            "Test query",
            tools=[{"name": "search_tool", "description": "Search tool"}],
            tool_manager=mock_tool_manager,
        )

        # Verify tools are preserved in all API calls
        for call_args in mock_client.messages.create.call_args_list:
            self.assertIn("tools", call_args.kwargs)
            tools = call_args.kwargs["tools"]
            self.assertEqual(len(tools), 1)
            self.assertEqual(tools[0]["name"], "search_tool")

    @patch("ai_generator.anthropic.Anthropic")
    def test_complex_multi_search_scenario(self, mock_anthropic_class):
        """Test complex scenario requiring multiple searches"""
        # Setup mock client
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Mock the example flow from requirements
        initial_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="search_course_content",
                    input_data={"query": "course X", "course_name": "course X"},
                    tool_use_id="tool_1",
                )
            ],
            stop_reason="tool_use",
        )

        second_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "tool_use",
                    name="search_course_content",
                    input_data={"query": "lesson 4 topic from course X"},
                    tool_use_id="tool_2",
                )
            ],
            stop_reason="tool_use",
        )

        final_response = MockAnthropicResponse(
            [
                MockAnthropicContent(
                    "text",
                    text="Found related courses that discuss the same topic as lesson 4",
                )
            ],
            stop_reason="end_turn",
        )

        mock_client.messages.create.side_effect = [
            initial_response,
            second_response,
            final_response,
        ]

        # Setup AI generator
        self.ai_generator.client = mock_client
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = [
            "Course X outline with lesson 4: Advanced Topics",
            "Related courses covering Advanced Topics",
        ]

        # Execute the example query
        response = self.ai_generator.generate_response(
            "Search for a course that discusses the same topic as lesson 4 of course X",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager,
        )

        # Verify the complex workflow
        self.assertEqual(
            response, "Found related courses that discuss the same topic as lesson 4"
        )
        self.assertEqual(mock_client.messages.create.call_count, 3)
        self.assertEqual(mock_tool_manager.execute_tool.call_count, 2)

        # Verify tool parameters evolved across rounds
        tool_calls = mock_tool_manager.execute_tool.call_args_list
        first_call = tool_calls[0][1]  # kwargs from first call
        second_call = tool_calls[1][1]  # kwargs from second call

        self.assertIn("course X", first_call["query"])
        self.assertIn("lesson 4", second_call["query"])


if __name__ == "__main__":
    unittest.main()
