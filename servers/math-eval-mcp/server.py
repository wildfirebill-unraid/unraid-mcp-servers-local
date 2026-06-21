import json
from typing import Any

import sympy
from sympy import sympify, symbols, solve, simplify as sympy_simplify, N, latex
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

ALLOWED_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)

SYMPY_FUNCTIONS = {
    "sin": "Trigonometric sine", "cos": "Trigonometric cosine",
    "tan": "Trigonometric tangent", "asin": "Inverse sine",
    "acos": "Inverse cosine", "atan": "Inverse tangent",
    "sinh": "Hyperbolic sine", "cosh": "Hyperbolic cosine",
    "tanh": "Hyperbolic tangent", "exp": "Exponential function (e^x)",
    "log": "Natural logarithm", "log10": "Base-10 logarithm",
    "sqrt": "Square root", "Abs": "Absolute value",
    "floor": "Floor function", "ceiling": "Ceiling function",
    "factorial": "Factorial", "gamma": "Gamma function",
    "erf": "Error function", "erfc": "Complementary error function"
}

SYMPY_CONSTANTS = {
    "pi": 3.14159265358979, "E": 2.71828182845905,
    "oo": "Infinity", "I": "Imaginary unit"
}


def _safe_parse(expr_str: str) -> Any:
    return parse_expr(expr_str, transformations=ALLOWED_TRANSFORMATIONS)


class MathEvalServer(Server):
    def __init__(self):
        super().__init__("math-eval")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="evaluate", description="Evaluate a mathematical expression safely",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "expression": {"type": "string", "description": "Mathematical expression to evaluate e.g. 'sin(pi/4) + 2^3'"}
                     },
                     "required": ["expression"]
                 }),
            Tool(name="evaluate_with_vars", description="Evaluate expression with variable substitutions",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "expression": {"type": "string", "description": "Expression with variables e.g. 'x^2 + y'" },
                         "variables_json": {"type": "string", "description": "JSON object mapping variable names to values e.g. '{\"x\": 3, \"y\": 5}'"}
                     },
                     "required": ["expression", "variables_json"]
                 }),
            Tool(name="list_functions", description="List all available functions and constants",
                 inputSchema={
                     "type": "object",
                     "properties": {}
                 }),
            Tool(name="solve_equation", description="Solve an equation for a variable",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "equation": {"type": "string", "description": "Equation to solve e.g. 'x**2 - 4 = 0' or 'x^2 - 4'" },
                         "variable": {"type": "string", "description": "Variable to solve for e.g. 'x'"}
                     },
                     "required": ["equation", "variable"]
                 }),
            Tool(name="simplify", description="Simplify a mathematical expression",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "expression": {"type": "string", "description": "Expression to simplify e.g. 'x^2 + 2*x + 1'"}
                     },
                     "required": ["expression"]
                 }),
            Tool(name="plot_expression", description="Evaluate expression over a range and return value table (ASCII plot data)",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "expression": {"type": "string", "description": "Expression to evaluate e.g. 'sin(x)'"},
                         "x_min": {"type": "number", "description": "Minimum x value"},
                         "x_max": {"type": "number", "description": "Maximum x value"},
                         "steps": {"type": "integer", "description": "Number of steps (default 50)", "default": 50}
                     },
                     "required": ["expression", "x_min", "x_max"]
                 }),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "evaluate":
                expr = _safe_parse(args["expression"])
                result = N(expr)
                return [TextContent(type="text", text=json.dumps({
                    "expression": args["expression"],
                    "result": str(result),
                    "result_float": float(result) if result.is_Number else None
                }))]

            elif name == "evaluate_with_vars":
                expr = _safe_parse(args["expression"])
                variables = json.loads(args["variables_json"])
                subs = {symbols(k): v for k, v in variables.items()}
                result = N(expr.subs(subs))
                return [TextContent(type="text", text=json.dumps({
                    "expression": args["expression"],
                    "variables": variables,
                    "result": str(result),
                    "result_float": float(result) if result.is_Number else None
                }))]

            elif name == "list_functions":
                funcs = []
                for name_, desc in SYMPY_FUNCTIONS.items():
                    funcs.append({"name": name_, "description": desc})
                for name_, val in SYMPY_CONSTANTS.items():
                    funcs.append({"name": name_, "description": f"Constant: {val}"})
                return [TextContent(type="text", text=json.dumps({"functions": funcs}))]

            elif name == "solve_equation":
                eq_str = args["equation"]
                var = symbols(args["variable"])
                if "=" in eq_str:
                    left, right = eq_str.split("=", 1)
                    eq = sympy.Eq(_safe_parse(left), _safe_parse(right))
                else:
                    eq = _safe_parse(eq_str)
                solutions = solve(eq, var)
                sol_strs = [str(s) for s in solutions]
                return [TextContent(type="text", text=json.dumps({
                    "equation": args["equation"],
                    "variable": args["variable"],
                    "solutions": sol_strs,
                    "solution_count": len(sol_strs)
                }))]

            elif name == "simplify":
                expr = _safe_parse(args["expression"])
                result = sympy_simplify(expr)
                return [TextContent(type="text", text=json.dumps({
                    "expression": args["expression"],
                    "simplified": str(result),
                    "latex": latex(result)
                }))]

            elif name == "plot_expression":
                x = symbols("x")
                expr = _safe_parse(args["expression"])
                x_min = float(args["x_min"])
                x_max = float(args["x_max"])
                steps = int(args.get("steps", 50))
                if steps < 2:
                    steps = 2
                step = (x_max - x_min) / (steps - 1)
                points = []
                for i in range(steps):
                    xv = x_min + i * step
                    try:
                        yv = float(N(expr.subs({x: xv})))
                        points.append({"x": round(xv, 6), "y": round(yv, 6)})
                    except Exception:
                        points.append({"x": round(xv, 6), "y": None})
                return [TextContent(type="text", text=json.dumps({
                    "expression": args["expression"],
                    "x_min": x_min,
                    "x_max": x_max,
                    "steps": steps,
                    "points": points
                }))]

            else:
                raise ValueError(f"Unknown tool: {name}")

        except json.JSONDecodeError as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Invalid JSON: {str(e)}"}))]
        except (ValueError, TypeError, SyntaxError) as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Evaluation error: {str(e)}"}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = MathEvalServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
