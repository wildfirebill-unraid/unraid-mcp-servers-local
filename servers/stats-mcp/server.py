import json
import math as _math

import numpy as np
from scipy import stats as scipy_stats

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


class StatsServer(Server):
    def __init__(self):
        super().__init__("stats")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="describe", description="Descriptive statistics for a list of values",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "values": {"type": "array", "items": {"type": "number"}, "description": "Array of numbers"}
                     },
                     "required": ["values"]
                 }),
            Tool(name="correlation", description="Pearson correlation coefficient between two datasets",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "x_values": {"type": "array", "items": {"type": "number"}, "description": "X values"},
                         "y_values": {"type": "array", "items": {"type": "number"}, "description": "Y values"}
                     },
                     "required": ["x_values", "y_values"]
                 }),
            Tool(name="linear_regression", description="Linear regression: slope, intercept, r-squared",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "x_values": {"type": "array", "items": {"type": "number"}, "description": "X values"},
                         "y_values": {"type": "array", "items": {"type": "number"}, "description": "Y values"}
                     },
                     "required": ["x_values", "y_values"]
                 }),
            Tool(name="quartiles", description="Compute Q1, Q2 (median), Q3, and IQR",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "values": {"type": "array", "items": {"type": "number"}, "description": "Array of numbers"}
                     },
                     "required": ["values"]
                 }),
            Tool(name="z_score", description="Calculate z-scores for all values",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "values": {"type": "array", "items": {"type": "number"}, "description": "Array of numbers"}
                     },
                     "required": ["values"]
                 }),
            Tool(name="covariance", description="Sample covariance between two datasets",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "x_values": {"type": "array", "items": {"type": "number"}, "description": "X values"},
                         "y_values": {"type": "array", "items": {"type": "number"}, "description": "Y values"}
                     },
                     "required": ["x_values", "y_values"]
                 }),
            Tool(name="frequency_table", description="Frequency distribution of values into bins",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "values": {"type": "array", "items": {"type": "number"}, "description": "Array of numbers"},
                         "bins": {"type": "integer", "description": "Number of bins"}
                     },
                     "required": ["values", "bins"]
                 }),
            Tool(name="random_sample", description="Generate random sample from a distribution",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "n": {"type": "integer", "description": "Number of samples"},
                         "distribution": {"type": "string", "description": "Distribution: 'normal', 'uniform', 'poisson', 'binomial', 'exponential'"},
                         "params_json": {"type": "string", "description": "Distribution parameters as JSON. For normal: {\"loc\":0,\"scale\":1}. For uniform: {\"loc\":0,\"scale\":1}. For poisson: {\"lam\":1}. For binomial: {\"n\":10,\"p\":0.5}. For exponential: {\"scale\":1}."}
                     },
                     "required": ["n", "distribution"]
                 }),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "describe":
                v = np.array(args["values"], dtype=float)
                if len(v) == 0:
                    raise ValueError("Values array is empty")
                return [TextContent(type="text", text=json.dumps({
                    "count": int(len(v)),
                    "mean": float(np.mean(v)),
                    "median": float(np.median(v)),
                    "stddev": float(np.std(v, ddof=1)),
                    "variance": float(np.var(v, ddof=1)),
                    "min": float(np.min(v)),
                    "max": float(np.max(v)),
                    "q1": float(np.percentile(v, 25)),
                    "q3": float(np.percentile(v, 75)),
                    "sum": float(np.sum(v))
                }))]

            elif name == "correlation":
                x = np.array(args["x_values"], dtype=float)
                y = np.array(args["y_values"], dtype=float)
                if len(x) != len(y):
                    raise ValueError("Arrays must have same length")
                if len(x) < 2:
                    raise ValueError("Need at least 2 data points")
                r, p = scipy_stats.pearsonr(x, y)
                return [TextContent(type="text", text=json.dumps({
                    "correlation": float(r),
                    "p_value": float(p),
                    "n": int(len(x))
                }))]

            elif name == "linear_regression":
                x = np.array(args["x_values"], dtype=float)
                y = np.array(args["y_values"], dtype=float)
                if len(x) != len(y):
                    raise ValueError("Arrays must have same length")
                if len(x) < 2:
                    raise ValueError("Need at least 2 data points")
                slope, intercept, r_val, p_val, std_err = scipy_stats.linregress(x, y)
                return [TextContent(type="text", text=json.dumps({
                    "slope": float(slope),
                    "intercept": float(intercept),
                    "r_squared": float(r_val ** 2),
                    "r": float(r_val),
                    "p_value": float(p_val),
                    "std_error": float(std_err) if not _math.isnan(std_err) else None,
                    "n": int(len(x))
                }))]

            elif name == "quartiles":
                v = np.array(args["values"], dtype=float)
                q1 = float(np.percentile(v, 25))
                q2 = float(np.median(v))
                q3 = float(np.percentile(v, 75))
                iqr = q3 - q1
                return [TextContent(type="text", text=json.dumps({
                    "q1": q1,
                    "q2_median": q2,
                    "q3": q3,
                    "iqr": iqr,
                    "min": float(np.min(v)),
                    "max": float(np.max(v))
                }))]

            elif name == "z_score":
                v = np.array(args["values"], dtype=float)
                mu = np.mean(v)
                sigma = np.std(v, ddof=0)
                if sigma == 0:
                    zs = [0.0] * len(v)
                else:
                    zs = [float((x - mu) / sigma) for x in v]
                return [TextContent(type="text", text=json.dumps({
                    "z_scores": zs,
                    "mean": float(mu),
                    "stddev": float(sigma)
                }))]

            elif name == "covariance":
                x = np.array(args["x_values"], dtype=float)
                y = np.array(args["y_values"], dtype=float)
                if len(x) != len(y):
                    raise ValueError("Arrays must have same length")
                if len(x) < 2:
                    raise ValueError("Need at least 2 data points")
                cov = float(np.cov(x, y, ddof=1)[0][1])
                return [TextContent(type="text", text=json.dumps({
                    "covariance": cov,
                    "n": int(len(x))
                }))]

            elif name == "frequency_table":
                v = np.array(args["values"], dtype=float)
                bins = int(args["bins"])
                if bins < 1:
                    raise ValueError("Bins must be >= 1")
                counts, edges = np.histogram(v, bins=bins)
                frequencies = []
                for i in range(len(counts)):
                    frequencies.append({
                        "bin_start": float(edges[i]),
                        "bin_end": float(edges[i + 1]),
                        "count": int(counts[i]),
                        "relative_frequency": float(counts[i] / len(v))
                    })
                return [TextContent(type="text", text=json.dumps({
                    "bins": bins,
                    "total": int(len(v)),
                    "frequencies": frequencies
                }))]

            elif name == "random_sample":
                n = int(args["n"])
                dist = args.get("distribution", "normal")
                params = json.loads(args.get("params_json", "{}")) if args.get("params_json") else {}
                rng = np.random.default_rng()
                if dist == "normal":
                    samples = rng.normal(loc=params.get("loc", 0), scale=params.get("scale", 1), size=n)
                elif dist == "uniform":
                    samples = rng.uniform(low=params.get("loc", 0), high=params.get("loc", 0) + params.get("scale", 1), size=n)
                elif dist == "poisson":
                    samples = rng.poisson(lam=params.get("lam", 1), size=n)
                elif dist == "binomial":
                    samples = rng.binomial(n=params.get("n", 10), p=params.get("p", 0.5), size=n)
                elif dist == "exponential":
                    samples = rng.exponential(scale=params.get("scale", 1), size=n)
                else:
                    raise ValueError(f"Unknown distribution: {dist}")
                return [TextContent(type="text", text=json.dumps({
                    "distribution": dist,
                    "n": n,
                    "params": params,
                    "samples": [float(s) for s in samples]
                }))]

            else:
                raise ValueError(f"Unknown tool: {name}")

        except json.JSONDecodeError as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Invalid JSON: {str(e)}"}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = StatsServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
