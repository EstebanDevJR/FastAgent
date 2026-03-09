import asyncio
from dataclasses import dataclass
from pathlib import Path
import json
import statistics
import time

import typer
from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class BenchResult:
    ok: bool
    latency_ms: float
    status_code: int
    error: str


async def _single_request(client, url: str, message: str, timeout: float) -> BenchResult:
    start = time.perf_counter()
    try:
        response = await client.post(url, json={"message": message}, timeout=timeout)
        latency = (time.perf_counter() - start) * 1000
        return BenchResult(ok=response.status_code < 400, latency_ms=latency, status_code=response.status_code, error="")
    except Exception as exc:
        latency = (time.perf_counter() - start) * 1000
        return BenchResult(ok=False, latency_ms=latency, status_code=0, error=str(exc))


async def _run_benchmark(url: str, total: int, concurrency: int, message: str, timeout: float) -> list[BenchResult]:
    import httpx

    semaphore = asyncio.Semaphore(max(1, concurrency))

    async with httpx.AsyncClient() as client:
        async def _wrapped() -> BenchResult:
            async with semaphore:
                return await _single_request(client, url=url, message=message, timeout=timeout)

        tasks = [_wrapped() for _ in range(total)]
        return await asyncio.gather(*tasks)


def run_bench(
    base_url: str = typer.Option("http://127.0.0.1:8000", "--base-url", help="API base URL."),
    endpoint: str = typer.Option("/chat", "--endpoint", help="Endpoint to benchmark."),
    total: int = typer.Option(50, "--total", help="Total requests."),
    concurrency: int = typer.Option(10, "--concurrency", help="Concurrent requests."),
    message: str = typer.Option("hello", "--message", help="Payload message."),
    timeout: float = typer.Option(15.0, "--timeout", help="Per-request timeout in seconds."),
    output_json: Path | None = typer.Option(None, "--output-json", help="Optional JSON report path."),
) -> None:
    if total <= 0 or concurrency <= 0:
        console.print("[red]Error:[/red] --total and --concurrency must be > 0")
        raise typer.Exit(code=1)

    url = base_url.rstrip("/") + endpoint

    try:
        results = asyncio.run(_run_benchmark(url, total, concurrency, message, timeout))
    except ImportError:
        console.print("[red]Error:[/red] httpx is required for bench. Install dependencies first.")
        raise typer.Exit(code=1)

    latencies = [r.latency_ms for r in results]
    success = [r for r in results if r.ok]
    failures = [r for r in results if not r.ok]

    p50 = statistics.median(latencies) if latencies else 0.0
    p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies, default=0.0)
    p99 = statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else max(latencies, default=0.0)

    table = Table(title="FastAgent Benchmark")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("url", url)
    table.add_row("total", str(total))
    table.add_row("concurrency", str(concurrency))
    table.add_row("success", str(len(success)))
    table.add_row("failed", str(len(failures)))
    table.add_row("success_rate", f"{(len(success) / total) * 100:.2f}%")
    table.add_row("latency_p50_ms", f"{p50:.2f}")
    table.add_row("latency_p95_ms", f"{p95:.2f}")
    table.add_row("latency_p99_ms", f"{p99:.2f}")
    table.add_row("latency_avg_ms", f"{statistics.mean(latencies):.2f}" if latencies else "0.00")
    console.print(table)

    if output_json is not None:
        report = {
            "url": url,
            "total": total,
            "concurrency": concurrency,
            "success": len(success),
            "failed": len(failures),
            "success_rate": (len(success) / total) if total else 0,
            "latency_ms": {
                "p50": p50,
                "p95": p95,
                "p99": p99,
                "avg": statistics.mean(latencies) if latencies else 0,
            },
            "failures": [
                {
                    "status_code": item.status_code,
                    "error": item.error,
                }
                for item in failures[:25]
            ],
        }
        output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        console.print(f"[green]Report written:[/green] {output_json}")

    if failures and len(success) == 0:
        raise typer.Exit(code=1)
