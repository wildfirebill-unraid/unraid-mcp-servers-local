import os
import json
import subprocess
import tempfile
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

BASE = os.environ.get("MEDIA_CONVERT_PATH", "/data")

def resolve_path(user_path: str, check_exists: bool = True) -> str:
    p = os.path.normpath(os.path.join(BASE, user_path))
    if not p.startswith(os.path.normpath(BASE)):
        raise ValueError("Path traversal denied")
    if check_exists and not os.path.exists(p):
        raise FileNotFoundError(f"Path not found: {p}")
    return p

def run_ffmpeg(args: list[str]) -> str:
    result = subprocess.run(["ffmpeg", "-y"] + args, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error: {result.stderr}")
    return result.stdout

server = Server("media-convert-mcp")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="convert_video",
            description="Transcode video using ffmpeg",
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Input file path"},
                    "output": {"type": "string", "description": "Output file path"},
                    "codec": {"type": "string", "description": "Video codec (h264 or h265)", "default": "h264"},
                    "crf": {"type": "integer", "description": "CRF value 0-51 (lower = better)", "default": 23},
                    "resolution": {"type": "string", "description": "Target resolution (e.g. 1280:720)"},
                    "bitrate": {"type": "string", "description": "Target bitrate (e.g. 2M)"}
                },
                "required": ["input", "output"]
            }
        ),
        Tool(
            name="extract_audio",
            description="Extract audio track from video",
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Input video path"},
                    "output_format": {"type": "string", "description": "Output format (mp3/aac/flac)", "default": "mp3"},
                    "track_index": {"type": "integer", "description": "Audio track index (0-based)", "default": 0}
                },
                "required": ["input"]
            }
        ),
        Tool(
            name="get_thumbnail",
            description="Generate thumbnail image at a specific time",
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Input video path"},
                    "time": {"type": "string", "description": "Time position (e.g. 00:01:30 or 90)"},
                    "output": {"type": "string", "description": "Output image path"},
                    "size": {"type": "string", "description": "Thumbnail size (e.g. 320x240)"}
                },
                "required": ["input", "time", "output"]
            }
        ),
        Tool(
            name="concat_videos",
            description="Concatenate multiple video files",
            inputSchema={
                "type": "object",
                "properties": {
                    "files": {"type": "array", "items": {"type": "string"}, "description": "List of input video paths"},
                    "output": {"type": "string", "description": "Output file path"}
                },
                "required": ["files", "output"]
            }
        ),
        Tool(
            name="compress_media",
            description="Compress video file to target size",
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Input video path"},
                    "output": {"type": "string", "description": "Output file path"},
                    "target_size_mb": {"type": "number", "description": "Target file size in MB"}
                },
                "required": ["input", "output", "target_size_mb"]
            }
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "convert_video":
        inp = resolve_path(arguments["input"])
        out = resolve_path(arguments["output"], check_exists=False)
        codec = arguments.get("codec", "h264")
        vcodec = "libx264" if codec == "h264" else "libx265"
        args = ["-i", inp, "-c:v", vcodec, "-crf", str(arguments.get("crf", 23))]
        if "resolution" in arguments:
            args.extend(["-vf", f"scale={arguments['resolution']}"])
        if "bitrate" in arguments:
            args.extend(["-b:v", arguments["bitrate"]])
        args.append(out)
        run_ffmpeg(args)
        return [TextContent(type="text", text=json.dumps({"status": "ok", "output": out}))]
    elif name == "extract_audio":
        inp = resolve_path(arguments["input"])
        fmt = arguments.get("output_format", "mp3")
        codec_map = {"mp3": "libmp3lame", "aac": "aac", "flac": "flac"}
        ext_map = {"mp3": "mp3", "aac": "m4a", "flac": "flac"}
        codec_name = codec_map.get(fmt, "libmp3lame")
        ext = ext_map.get(fmt, "mp3")
        track = arguments.get("track_index", 0)
        base_name = os.path.splitext(os.path.basename(inp))[0]
        out_path = resolve_path(f"{base_name}_audio.{ext}", check_exists=False)
        args = ["-i", inp, "-map", f"0:a:{track}", "-c:a", codec_name, "-y", out_path]
        run_ffmpeg(args)
        return [TextContent(type="text", text=json.dumps({"status": "ok", "output": out_path}))]
    elif name == "get_thumbnail":
        inp = resolve_path(arguments["input"])
        out = resolve_path(arguments["output"], check_exists=False)
        args = ["-i", inp, "-ss", arguments["time"], "-vframes", "1"]
        if "size" in arguments:
            args.extend(["-s", arguments["size"]])
        args.append(out)
        run_ffmpeg(args)
        return [TextContent(type="text", text=json.dumps({"status": "ok", "output": out}))]
    elif name == "concat_videos":
        files = arguments["files"]
        resolved = [resolve_path(f) for f in files]
        out = resolve_path(arguments["output"], check_exists=False)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            concat_path = f.name
            for rf in resolved:
                f.write(f"file '{rf}'\n")
        try:
            args = ["-f", "concat", "-safe", "0", "-i", concat_path, "-c", "copy", out]
            run_ffmpeg(args)
        finally:
            os.unlink(concat_path)
        return [TextContent(type="text", text=json.dumps({"status": "ok", "output": out}))]
    elif name == "compress_media":
        inp = resolve_path(arguments["input"])
        out = resolve_path(arguments["output"], check_exists=False)
        target_bytes = arguments["target_size_mb"] * 1024 * 1024
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", inp],
            capture_output=True, text=True
        )
        info = json.loads(probe.stdout)
        duration = float(info["format"]["duration"])
        target_bitrate = int((target_bytes * 8) / duration)
        target_bitrate_k = max(target_bitrate // 1000, 100)
        args = ["-i", inp, "-c:v", "libx264", "-b:v", f"{target_bitrate_k}k", "-pass", "1", "-f", "mp4", os.devnull]
        run_ffmpeg(args)
        args = ["-i", inp, "-c:v", "libx264", "-b:v", f"{target_bitrate_k}k", "-pass", "2", out]
        run_ffmpeg(args)
        os.remove("ffmpeg2pass-0.log")
        os.remove("ffmpeg2pass-0.log.mbtree")
        return [TextContent(type="text", text=json.dumps({"status": "ok", "output": out, "target_bitrate_kbps": target_bitrate_k}))]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="media-convert-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
