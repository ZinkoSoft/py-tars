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
        servers = config.get("servers", [])
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
                    read_stream, write_stream, _ = await context.__aenter__()
                    active_contexts.append((context, (read_stream, write_stream)))
                    
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

        # Subscribe to LLM worker health to detect restarts
        await MCPBridgeMQTTClient.subscribe_llm_health(mqtt)

        # Tool execution is now handled directly by llm-worker via direct MCP connections
        # mcp-bridge only handles tool discovery and registry publishing
        logger.info("✅ MCP Bridge ready - tool registry published, monitoring LLM health")
        logger.info("   (Tool execution is handled by llm-worker)")
        
        # Keep the service alive, maintain MCP connections, and monitor LLM health
        try:
            heartbeat_task = asyncio.create_task(heartbeat_loop(mqtt))
            
            async with mqtt.messages() as messages:
                async for message in messages:
                    # Check if LLM worker restarted
                    if MCPBridgeMQTTClient.is_llm_ready_event(message.payload):
                        logger.info("🔄 LLM worker restarted - re-publishing tool registry")
                        await MCPBridgeMQTTClient.publish_tool_registry(mqtt, tool_funcs)
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