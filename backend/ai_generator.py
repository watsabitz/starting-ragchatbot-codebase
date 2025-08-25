import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Search Tool Usage:
- Use the search tool **only** for questions about specific course content or detailed educational materials
- **Up to 2 sequential searches allowed per query** - you can reason about previous search results and perform additional searches if needed
- For complex queries requiring multiple searches (e.g., comparisons, multi-part questions, cross-course information), perform sequential searches
- Synthesize all search results into accurate, fact-based responses
- If search yields no results, state this clearly without offering alternatives

Sequential Search Examples:
- "Find lesson 4 content from course X, then search for other courses covering the same topic"
- "Compare approaches between different courses on the same subject"
- Multi-part questions requiring information from different lessons or courses

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Search first, then answer
- **Complex queries**: Use up to 2 searches to gather comprehensive information
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.client = None
        
        # Only initialize client if we have a valid-looking API key
        if api_key and api_key.startswith('sk-ant-') and not 'placeholder' in api_key.lower():
            try:
                self.client = anthropic.Anthropic(api_key=api_key)
            except Exception as e:
                print(f"Warning: Failed to initialize Anthropic client: {e}")
                self.client = None
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            
        Returns:
            Generated response as string
        """
        
        # Check if we have a valid client
        if not self.client:
            return "I'm sorry, but I need a valid Anthropic API key to generate responses. Please set a valid ANTHROPIC_API_KEY in your .env file."
        
        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history 
            else self.SYSTEM_PROMPT
        )
        
        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }
        
        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}
        
        # Get response from Claude
        response = self.client.messages.create(**api_params)
        
        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._handle_tool_execution(response, api_params, tool_manager)
        
        # Return direct response
        return response.content[0].text
    
    def _handle_tool_execution(self, initial_response, base_params: Dict[str, Any], tool_manager):
        """
        Handle execution of tool calls with support for up to 2 sequential rounds.
        
        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools
            
        Returns:
            Final response text after tool execution
        """
        # Maximum sequential rounds allowed
        MAX_ROUNDS = 2
        
        # Start with existing messages
        messages = base_params["messages"].copy()
        current_response = initial_response
        
        # Sequential tool execution loop
        for round_num in range(MAX_ROUNDS):
            # Check if current response has tool use
            if current_response.stop_reason != "tool_use":
                # No more tools requested, return current response
                return current_response.content[0].text
                
            # Add AI's tool use response to conversation
            messages.append({"role": "assistant", "content": current_response.content})
            
            # Execute all tool calls in this round
            tool_results = []
            tool_execution_failed = False
            
            for content_block in current_response.content:
                if content_block.type == "tool_use":
                    try:
                        tool_result = tool_manager.execute_tool(
                            content_block.name, 
                            **content_block.input
                        )
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": tool_result
                        })
                    except Exception as e:
                        # Tool execution failed, mark for graceful handling
                        tool_execution_failed = True
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": f"Tool execution failed: {str(e)}"
                        })
            
            # Add tool results to conversation
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            
            # If tool execution failed, return with error context
            if tool_execution_failed:
                # Make final API call with tools still available for error handling
                final_params = {
                    **self.base_params,
                    "messages": messages,
                    "system": base_params["system"],
                    "tools": base_params.get("tools"),  # Keep tools available
                    "tool_choice": {"type": "auto"}
                }
                
                try:
                    final_response = self.client.messages.create(**final_params)
                    return final_response.content[0].text
                except Exception:
                    # If final call fails, return best available response
                    return "I encountered an issue while searching for information. Please try rephrasing your question."
            
            # If this is the last round, make final call without expecting more tools
            if round_num == MAX_ROUNDS - 1:
                # Final API call - tools available but expecting final answer
                final_params = {
                    **self.base_params,
                    "messages": messages,
                    "system": base_params["system"],
                    "tools": base_params.get("tools"),  # Keep tools available
                    "tool_choice": {"type": "auto"}
                }
                
                final_response = self.client.messages.create(**final_params)
                return final_response.content[0].text
            
            # Continue to next round - make API call with tools available
            next_params = {
                **self.base_params,
                "messages": messages,
                "system": base_params["system"],
                "tools": base_params.get("tools"),  # Critical fix: keep tools available
                "tool_choice": {"type": "auto"}
            }
            
            # Get response for next round
            current_response = self.client.messages.create(**next_params)
        
        # Should not reach here, but fallback to final response
        return current_response.content[0].text