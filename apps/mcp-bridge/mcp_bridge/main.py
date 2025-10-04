import asyncio
import logging
import os

import yaml
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.streamable_http import streamablehttp_client

from .mqtt_client import MCPBridgeMQTTClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-bridge")


def tool_to_openai_function(server_name, t) -> dict:
    # t is an MCP Tool (SDK object) with .name, .description, .inputSchema (JSONSchema)
    # Note: MCP uses camelCase (inputSchema), not snake_case (input_schema)
    # OpenAI function names: use underscores instead of colons (colons may cause issues)
    return {
        "type": "function",
        "function": {
            "name": f"mcp__{server_name}__{t.name}",
            "description": t.description or "",
            "parameters": t.inputSchema or {"type":"object","properties":{}}
        }
    }

async def load_servers_yaml():
    """Load MCP server configuration from YAML file."""
    yaml_path = os.getenv("MCP_SERVERS_YAML", "/config/mcp.server.yml")
    try:
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)
        servers = config.get("servers", []) or []  # Handle None case when key exists with no value
        logger.info(f"Loaded {len(servers)} MCP servers from {yaml_path}")
        return servers
    except Exception as e:
        logger.error(f"Failed to load MCP servers YAML: {e}")
        return []

async def heartbeat_loop(mqtt):
    """Send periodic health heartbeats.
    
    Args:
        mqtt: Connected MQTT client
    """
    try:
        while True:
            await asyncio.sleep(60)
            await MCPBridgeMQTTClient.publish_health(mqtt, event="heartbeat")
    except asyncio.CancelledError:
        logger.debug("Heartbeat loop cancelled")

async def handle_tool_call(mqtt, payload: bytes, sessions: dict):
    """Handle tool execution request from llm-worker.
    
    Args:
        mqtt: Connected MQTT client
        payload: JSON payload from llm/tools/call topic
                 Expected: {call_id, tool_name, arguments}
        sessions: Dict of server_name -> ClientSession
    """
    import orjson
    
    try:
        data = orjson.loads(payload)
        call_id = data.get("call_id")
        tool_name = data.get("tool_name")
        arguments = data.get("arguments", {})
        
        if not call_id or not tool_name:
            logger.error(f"Invalid tool call request: missing call_id or tool_name")
            return
        
        logger.info(f"Executing tool call: {tool_name} (call_id={call_id})")
        
        # Parse tool name: mcp__server-name__tool-name
        if not tool_name.startswith("mcp__"):
            await MCPBridgeMQTTClient.publish_tool_result(
                mqtt, call_id, error=f"Not an MCP tool: {tool_name}"
            )
            return
        
        parts = tool_name.split("__")
        if len(parts) != 3:
            await MCPBridgeMQTTClient.publish_tool_result(
                mqtt, call_id, error=f"Invalid MCP tool name format: {tool_name}"
            )
            return
        
        _, server_name, mcp_tool_name = parts
        
        # Get session for this server
        session = sessions.get(server_name)
        if not session:
            await MCPBridgeMQTTClient.publish_tool_result(
                mqtt, call_id, error=f"Server not connected: {server_name}"
            )
            return
        
        # Execute tool via MCP
        try:
            logger.debug(f"Calling MCP tool: {server_name}:{mcp_tool_name} with args: {arguments}")
            result = await session.call_tool(mcp_tool_name, arguments)
            
            # Extract content from CallToolResult
            if hasattr(result, 'content') and result.content:
                # result.content is a list of content items
                content_text = " ".join(
                    item.text if hasattr(item, 'text') else str(item)
                    for item in result.content
                )
                logger.info(f"Tool {tool_name} succeeded: {content_text[:100]}")
                await MCPBridgeMQTTClient.publish_tool_result(mqtt, call_id, content=content_text)
            else:
                logger.warning(f"Tool {tool_name} returned no content")
                await MCPBridgeMQTTClient.publish_tool_result(mqtt, call_id, content="")
                
        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}", exc_info=True)
            await MCPBridgeMQTTClient.publish_tool_result(mqtt, call_id, error=str(e))
            
    except Exception as e:
        logger.error(f"Error handling tool call: {e}", exc_info=True)

async def main():
    # Initialize MQTT client
    mqtt_client = MCPBridgeMQTTClient()
    
    async with await mqtt_client.connect() as mqtt:
        logger.info("Connected to MQTT")

        # Load YAML, iterate servers → connect & enumerate tools
        servers = await load_servers_yaml()
        tool_funcs = []
        sessions: dict[str, ClientSession] = {}
        active_contexts = []  # Keep context managers alive for the program duration

        for s in servers:
            try:
                logger.info(f"Connecting to MCP server: {s['name']}...")
                transport = s.get("transport", "stdio")
                
                if transport == "http":
                    # HTTP/streamable-http transport
                    url = s.get("url")
                    if not url:
                        logger.error(f"HTTP transport requires 'url' for server {s['name']}")
                        continue
                    
                    logger.debug(f"Connecting via HTTP to {url}")
                    context = streamablehttp_client(url)
                    try:
                        read_stream, write_stream, _ = await context.__aenter__()
                        active_contexts.append((context, (read_stream, write_stream)))
                    except Exception as e:
                        logger.error(f"❌ Failed to connect to HTTP MCP server {s['name']} at {url}: {type(e).__name__}: {e}")
                        continue
                    
                elif transport == "stdio":
                    # stdio transport
                    params = StdioServerParameters(
                        command=s["command"],
                        args=s.get("args", []),
                        env=s.get("env", {})
                    )
                    logger.debug(f"Starting stdio client for {s['name']}")
                    context = stdio_client(params)
                    cm = await context.__aenter__()
                    active_contexts.append((context, cm))
                    read_stream, write_stream = cm
                    
                else:
                    logger.error(f"Unknown transport '{transport}' for server {s['name']}")
                    continue
                
                logger.debug(f"Creating ClientSession for {s['name']}")
                sess = ClientSession(read_stream, write_stream)
                
                # ClientSession needs to be entered as a context manager
                logger.debug(f"Entering ClientSession context for {s['name']}")
                try:
                    await sess.__aenter__()
                except Exception as e:
                    logger.error(f"❌ Error entering session context for {s['name']}: {e}", exc_info=True)
                    continue
                
                logger.info(f"Initializing MCP session for {s['name']}...")
                try:
                    # Try initializing with a reasonable timeout
                    init_result = await asyncio.wait_for(sess.initialize(), timeout=30.0)
                    logger.info(f"✅ Session initialized for {s['name']}: {init_result}")
                except asyncio.TimeoutError:
                    logger.error(f"❌ Timeout (30s) initializing session for {s['name']}")
                    logger.error(f"   This usually means the MCP server is not responding to initialize request")
                    continue
                except Exception as e:
                    logger.error(f"❌ Error initializing session for {s['name']}: {type(e).__name__}: {e}", exc_info=True)
                    continue
                    
                sessions[s["name"]] = sess
                logger.info(f"✅ Connected to MCP server: {s['name']}")

                # List tools (per MCP spec)
                logger.debug(f"Listing tools from {s['name']}")
                tools_result = await sess.list_tools()
                tools = tools_result.tools if hasattr(tools_result, 'tools') else tools_result
                logger.info(f"Found {len(tools)} tools in {s['name']}")
                
                for t in tools:
                    if s.get("tools_allowlist") and t.name not in s["tools_allowlist"]:
                        logger.debug(f"Skipping tool {t.name} (not in allowlist)")
                        continue
                    tool_funcs.append(tool_to_openai_function(s["name"], t))
                    logger.info(f"✅ Added tool: {s['name']}:{t.name}")
            except Exception as e:
                logger.error(f"❌ Failed to connect to MCP server {s['name']}: {e}", exc_info=True)
                continue

        # Publish merged registry for llm-worker (retained so new subscribers get it)
        await MCPBridgeMQTTClient.publish_tool_registry(mqtt, tool_funcs)

        # Publish health
        await MCPBridgeMQTTClient.publish_health(mqtt, event="ready")

        logger.info("✅ MCP Bridge ready - tool registry published, monitoring tool calls and LLM health")
        
        # Keep the service alive, maintain MCP connections, and handle tool execution
        try:
            heartbeat_task = asyncio.create_task(heartbeat_loop(mqtt))
            
            # CRITICAL: Start message iterator BEFORE subscribing to avoid asyncio-mqtt bug
            # where subscriptions after iterator start don't deliver messages
            async with mqtt.messages() as messages:
                # Subscribe to LLM worker health to detect restarts
                await MCPBridgeMQTTClient.subscribe_llm_health(mqtt)

                # Subscribe to tool call requests
                await MCPBridgeMQTTClient.subscribe_tool_calls(mqtt)
                
                # Small delay to ensure subscriptions are fully registered
                await asyncio.sleep(0.1)
                
                async for message in messages:
                    logger.debug("Received message: topic=%s payload_len=%d", message.topic, len(message.payload))
                    
                    # Handle tool execution requests
                    if message.topic == "llm/tools/call":
                        logger.info("📞 Tool call received: %s", message.payload.decode())
                        asyncio.create_task(handle_tool_call(mqtt, message.payload, sessions))
                    
                    # Check if LLM worker restarted
                    elif MCPBridgeMQTTClient.is_llm_ready_event(message.payload):
                        logger.info("🔄 LLM worker restarted - re-publishing tool registry")
                        await MCPBridgeMQTTClient.publish_tool_registry(mqtt, tool_funcs)
                        # CRITICAL: Publish a second non-retained message to work around asyncio-mqtt
                        # retained message delivery issue. The retained message ensures persistence,
                        # but non-retained ensures immediate delivery to active subscribers.
                        # Wait for LLM to fully start its message loop (0.5s delay + processing time)
                        await asyncio.sleep(1.0)
                        await MCPBridgeMQTTClient.publish_tool_registry_non_retained(mqtt, tool_funcs)
        except asyncio.CancelledError:
            logger.info("Shutdown signal received")
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        finally:
            # Cleanup: close all active contexts
            logger.info("Closing MCP connections...")
            for context, _ in active_contexts:
                try:
                    await context.__aexit__(None, None, None)
                except Exception as e:
                    logger.error(f"Error closing context: {e}")

if __name__ == "__main__":
    asyncio.run(main())