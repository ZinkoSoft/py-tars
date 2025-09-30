import asyncio, orjson, os, logging
from pydantic import BaseModel
from aiomqtt import Client as Mqtt
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-bridge")

class McpToolSpec(BaseModel):
    server: str
    name: str
    description: str | None = None
    parameters: dict  # JSON Schema

def tool_to_openai_function(server_name, t) -> dict:
    # t is an MCP Tool (SDK object) with .name, .description, .input_schema (JSONSchema)
    return {
        "type": "function",
        "function": {
            "name": f"mcp:{server_name}:{t.name}",
            "description": t.description or "",
            "parameters": t.input_schema or {"type":"object","properties":{}}
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

async def main():
    host = os.getenv("MQTT_HOST", "127.0.0.1")
    port = int(os.getenv("MQTT_PORT", "1883"))
    user = os.getenv("MQTT_USER")
    pwd = os.getenv("MQTT_PASS")
    
    async with Mqtt(hostname=host, port=port, username=user, password=pwd) as mqtt:
        logger.info("Connected to MQTT")

        # Load YAML, iterate servers → connect & enumerate tools
        servers = await load_servers_yaml()
        tool_funcs = []
        sessions: dict[str, ClientSession] = {}
        active_contexts = []  # Keep context managers alive for the program duration

        for s in servers:
            try:
                params = StdioServerParameters(
                    command=s["command"],
                    args=s.get("args", []),
                    env=s.get("env", {})
                )
                # Start the stdio client context manager
                context = stdio_client(params)
                cm = await context.__aenter__()
                active_contexts.append((context, cm))  # Store both context and result
                
                read_stream, write_stream = cm
                sess = ClientSession(read_stream, write_stream)
                await sess.initialize()
                sessions[s["name"]] = sess
                logger.info(f"Connected to MCP server: {s['name']}")

                # List tools (per MCP spec)
                tools = await sess.list_tools()
                for t in tools:
                    if s.get("tools_allowlist") and t.name not in s["tools_allowlist"]:
                        continue
                    tool_funcs.append(tool_to_openai_function(s["name"], t))
                    logger.debug(f"Added tool: {s['name']}:{t.name}")
            except Exception as e:
                logger.error(f"Failed to connect to MCP server {s['name']}: {e}")
                continue

        # Publish merged registry for llm-worker
        await mqtt.publish("llm/tools/registry", orjson.dumps({"tools": tool_funcs}), qos=1)
        logger.info(f"Published {len(tool_funcs)} tools to registry")

        # Publish health
        await mqtt.publish("system/health/mcp-bridge", orjson.dumps({"ok": True, "event": "ready"}), retain=True)

        # Handle tool calls from llm-worker
        await mqtt.subscribe("llm/tool.call.request/#")
        logger.info("Subscribed to tool call requests")
        async for m in mqtt.messages:
                try:
                    req = orjson.loads(m.payload)
                    _, server, tool = req["name"].split(":", 2)  # "mcp:server:tool"
                    args = req.get("arguments", {})
                    logger.info(f"Tool call: {server}:{tool} with args: {args}")
                    result = await sessions[server].call_tool(tool, args)  # SDK invoke
                    await mqtt.publish("llm/tool.call.result", orjson.dumps({
                        "call_id": req["call_id"], "result": result
                    }), qos=1)
                    logger.debug(f"Tool call result published for call_id: {req['call_id']}")
                except Exception as e:
                    logger.error(f"Tool call failed: {e}")
                    # Publish error result
                    try:
                        call_id = req.get("call_id", "unknown")
                        await mqtt.publish("llm/tool.call.result", orjson.dumps({
                            "call_id": call_id, "error": str(e)
                        }), qos=1)
                    except:
                        pass

        # Cleanup: close all active contexts
        for context, _ in active_contexts:
            try:
                await context.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing context: {e}")

if __name__ == "__main__":
    asyncio.run(main())