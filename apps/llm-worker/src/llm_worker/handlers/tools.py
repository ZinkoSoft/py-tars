"""Tool calling and execution."""

from __future__ import annotations

import logging
from typing import List

import orjson as json

from ..mcp_client import get_mcp_client
from ..providers.base import LLMResult

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Handles MCP tool execution and conversation management."""

    def __init__(self, mqtt_client=None):
        self.tools: List[dict] = []
        self._initialized = False
        self.mqtt_client = mqtt_client

    async def load_tools_from_registry(self, registry_payload: dict) -> None:
        """Load tools from MCP bridge registry and initialize client."""
        logger.info(
            "load_tools_from_registry called with payload keys: %s", list(registry_payload.keys())
        )
        try:
            self.tools = registry_payload.get("tools", [])
            logger.info("Loaded %d tools from registry", len(self.tools))

            if self.tools:
                logger.info("First tool format: %s", self.tools[0] if self.tools else "N/A")
                mcp_client = get_mcp_client()
                await mcp_client.initialize_from_registry(registry_payload)
                self._initialized = True
                logger.info(
                    "MCP client initialized with %d tools (servers will connect on-demand)",
                    len(self.tools),
                )
            else:
                logger.warning("No tools found in registry payload!")
        except Exception as e:
            logger.error("Failed to load tools: %s", e, exc_info=True)

    def extract_tool_calls(self, result: LLMResult) -> List[dict]:
        """Extract tool calls from LLM result."""
        if hasattr(result, "tool_calls") and result.tool_calls:
            return result.tool_calls
        return []

    async def execute_tool_calls(
        self, tool_calls: List[dict], mqtt_client_wrapper=None, client=None
    ) -> List[dict]:
        """Execute tool calls directly via MCP protocol.

        Args:
            tool_calls: List of tool calls from LLM
            mqtt_client_wrapper: MQTT client wrapper (for helper methods)
            client: Actual asyncio-mqtt Client (for publishing)

        Returns:
            List of results with call_id and content/error
        """
        if not self._initialized:
            logger.warning("Tool executor not initialized")
            return []

        mcp_client = get_mcp_client()
        mqtt_wrapper = mqtt_client_wrapper or self.mqtt_client
        mqtt_client = client
        results = []

        for call in tool_calls:
            call_id = call.get("id")
            if not call_id:
                continue

            tool_name = call.get("function", {}).get("name")
            arguments_str = call.get("function", {}).get("arguments", "{}")

            try:
                arguments = json.loads(arguments_str)
                logger.info("Executing tool: %s with args: %s", tool_name, arguments)

                # Execute tool directly via MCP
                result = await mcp_client.execute_tool(tool_name, arguments)

                # Parse content if it's a JSON string
                content = result.get("content", "")
                if content:
                    try:
                        parsed = json.loads(content)
                        # If result contains MQTT publish request, handle it
                        if mqtt_client and isinstance(parsed, dict) and "mqtt_publish" in parsed:
                            mqtt_data = parsed.pop("mqtt_publish")
                            await self._publish_tool_mqtt(mqtt_wrapper, mqtt_client, mqtt_data)
                            # Update content with the parsed result (without mqtt_publish)
                            result["content"] = json.dumps(parsed).decode("utf-8")
                    except json.JSONDecodeError:
                        # Content is not JSON, leave as is
                        pass

                result["call_id"] = call_id
                results.append(result)

            except Exception as e:
                logger.error("Tool %s failed: %s", tool_name, e, exc_info=True)
                results.append({"call_id": call_id, "error": str(e)})

        return results

    async def _publish_tool_mqtt(self, mqtt_wrapper, client, mqtt_data: dict) -> None:
        """Publish tool result data to MQTT.

        Args:
            mqtt_wrapper: MQTT client wrapper with helper methods
            client: Actual asyncio-mqtt Client
            mqtt_data: Dict with topic, event_type, data, source
        """
        try:
            from tars.contracts.envelope import Envelope

            topic = mqtt_data.get("topic")
            event_type = mqtt_data.get("event_type")
            data = mqtt_data.get("data")
            source = mqtt_data.get("source", "mcp-tool")

            # Wrap in envelope
            envelope = Envelope.new(
                event_type=event_type,
                data=data,
                source=source,
            )

            # Publish to MQTT using asyncio-mqtt client
            await client.publish(
                topic,
                envelope.model_dump_json().encode(),
                qos=1,
            )
            logger.info(f"Published tool result to MQTT: {topic}")

        except Exception as e:
            logger.error(f"Failed to publish tool MQTT data: {e}", exc_info=True)

    @staticmethod
    def format_tool_messages(tool_results: List[dict]) -> List[dict]:
        """Format tool results as OpenAI chat messages."""
        messages = []
        for result in tool_results:
            error = result.get("error")
            content = result.get("content") if not error else error
            messages.append(
                {"role": "tool", "content": content or "", "tool_call_id": result["call_id"]}
            )
        return messages
