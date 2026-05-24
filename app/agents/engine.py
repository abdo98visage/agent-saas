"""
Agent Runtime Engine - the heart of the platform.

Loads agent config from DB, resolves tools, builds prompts,
calls LLM, executes tools, and manages memory - all config-driven.
"""
import time
import json
from uuid import uuid4
from typing import Dict, List, Optional

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.db import supabase
from app.tools import get_tool, get_tools
from app.services.token_tracker import track_token_usage
from app.services.logger import log_agent_run, log_tool_call


class AgentEngine:
    """
    Config-driven agent runtime.
    
    No hardcoded agents - everything comes from DB:
    - system prompts
    - enabled tools
    - model selection
    - temperature
    """

    def __init__(self):
        self.openai = AsyncOpenAI(api_key=settings.openai_api_key)

    async def load_agent(self, agent_slug: str) -> Optional[Dict]:
        """Load agent configuration from Supabase."""
        response = supabase.table("agents").select("*").eq("slug", agent_slug).eq("active", True).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None

    async def load_conversation_history(self, conversation_id: str, limit: int = 20) -> List[Dict]:
        """Load recent messages from a conversation."""
        response = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=True).limit(limit).execute()
        
        messages = response.data or []
        messages.reverse()  # Chronological order
        
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
        ]

    async def load_memory(self, conversation_id: str) -> str:
        """Load conversation summary/memory."""
        response = supabase.table("conversation_memory").select("summary").eq("conversation_id", conversation_id).order("created_at", desc=True).limit(1).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]["summary"]
        return ""

    async def save_message(self, conversation_id: str, organization_id: str, role: str, content: str):
        """Save a message to the database."""
        supabase.table("messages").insert({
            "id": str(uuid4()),
            "conversation_id": conversation_id,
            "organization_id": organization_id,
            "role": role,
            "content": content,
        }).execute()

    def build_prompt(self, agent_config: Dict, user_message: str, memory: str, history: List[Dict]) -> List[Dict]:
        """Build the message list for the LLM call."""
        messages = [
            {"role": "system", "content": agent_config["system_prompt"]}
        ]
        
        # Add memory/summary as context
        if memory:
            messages.append({
                "role": "system",
                "content": f"Previous conversation summary: {memory}"
            })
        
        # Add conversation history
        messages.extend(history)
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        return messages

    async def call_llm(self, messages: List[Dict], model: str, temperature: float) -> Dict:
        """Call the LLM and track usage."""
        try:
            response = await self.openai.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=4096,
            )
            
            message = response.choices[0].message
            usage = response.usage
            
            return {
                "content": message.content,
                "role": message.role,
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "model": response.model,
            }
            
        except Exception as e:
            return {
                "content": f"Error calling LLM: {str(e)}",
                "role": "assistant",
                "input_tokens": 0,
                "output_tokens": 0,
                "error": str(e),
            }

    async def execute_tool(self, tool_name: str, tool_input: Dict, organization_id: str) -> Dict:
        """Execute a single tool and log the result."""
        tool = get_tool(tool_name)
        if not tool:
            return {"error": f"Tool not found: {tool_name}"}
        
        start = time.time()
        try:
            result = await tool.execute(tool_input)
            latency = int((time.time() - start) * 1000)
            
            # Log tool call
            await log_tool_call(
                organization_id=organization_id,
                tool_name=tool_name,
                input_data=tool_input,
                output_data=result,
                status="success",
                latency_ms=latency,
            )
            
            return result
            
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            
            await log_tool_call(
                organization_id=organization_id,
                tool_name=tool_name,
                input_data=tool_input,
                output_data=None,
                status="failed",
                latency_ms=latency,
                error_message=str(e),
            )
            
            return {"error": str(e)}

    async def run(self, agent_slug: str, user_message: str, organization_id: str, conversation_id: str = None, model: str = None, temperature: float = None) -> Dict:
        """
        Full agent execution flow:
        
        1. Load agent config from DB
        2. Load conversation history
        3. Load memory/summary
        4. Build prompt
        5. Call LLM
        6. Parse tool calls (if any)
        7. Execute tools
        8. Store messages
        9. Track token usage
        10. Return response
        """
        run_id = str(uuid4())
        start = time.time()
        
        try:
            # 1. Load agent config
            agent_config = await self.load_agent(agent_slug)
            if not agent_config:
                return {"error": f"Agent not found: {agent_slug}"}
            
            agent_model = model or agent_config.get("model", settings.default_model)
            agent_temp = temperature if temperature is not None else agent_config.get("temperature", settings.default_temperature)
            
            # 2. Load conversation history
            history = []
            if conversation_id:
                history = await self.load_conversation_history(conversation_id)
            
            # 3. Load memory
            memory = ""
            if conversation_id:
                memory = await self.load_memory(conversation_id)
            
            # 4. Build prompt
            messages = self.build_prompt(agent_config, user_message, memory, history)
            
            # 5. Call LLM
            result = await self.call_llm(messages, agent_model, agent_temp)
            
            latency = int((time.time() - start) * 1000)
            
            # 6-7. Check for tool calls in response
            # If the LLM returns a tool call, we execute it
            tool_results = []
            if "tool_calls" in result:
                for tool_call in result["tool_calls"]:
                    tool_result = await self.execute_tool(
                        tool_call["name"],
                        tool_call["input"],
                        organization_id,
                    )
                    tool_results.append(tool_result)
            
            # 8. Save messages
            if conversation_id:
                await self.save_message(conversation_id, organization_id, "user", user_message)
                await self.save_message(conversation_id, organization_id, "assistant", result["content"])
            
            # 9. Track token usage
            estimated_cost = (result.get("input_tokens", 0) * 0.000001 + result.get("output_tokens", 0) * 0.000003)  # GPT-4o-mini pricing approx
            await track_token_usage(
                organization_id=organization_id,
                model=result.get("model", agent_model),
                input_tokens=result.get("input_tokens", 0),
                output_tokens=result.get("output_tokens", 0),
                estimated_cost=estimated_cost,
                agent_run_id=run_id,
            )
            
            # 10. Log agent run
            await log_agent_run(
                organization_id=organization_id,
                agent_id=agent_config["id"],
                conversation_id=conversation_id,
                input_prompt=user_message,
                output=result["content"],
                status="completed",
                latency_ms=latency,
            )
            
            return {
                "response": result["content"],
                "tool_results": tool_results if tool_results else None,
                "model": result.get("model", agent_model),
                "tokens_used": result.get("input_tokens", 0) + result.get("output_tokens", 0),
                "latency_ms": latency,
            }
            
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            
            await log_agent_run(
                organization_id=organization_id,
                agent_id=None,
                conversation_id=conversation_id,
                input_prompt=user_message,
                output=None,
                status="failed",
                error_message=str(e),
                latency_ms=latency,
            )
            
            return {"error": str(e)}


# Singleton instance
agent_engine = AgentEngine()
