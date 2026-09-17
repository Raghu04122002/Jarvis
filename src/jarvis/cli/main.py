"""Jarvis CLI — command-line interface."""

import click
from rich.console import Console
from rich.table import Table

from jarvis import __version__

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="jarvis")
def cli() -> None:
    """Jarvis — Local-first personal AI orchestration system."""


@cli.command()
@click.option("--host", default="127.0.0.1", help="Bind host")
@click.option("--port", default=8000, type=int, help="Bind port")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(host: str, port: int, reload: bool) -> None:
    """Start the Jarvis API server."""
    import uvicorn

    from jarvis.config import load_config
    from jarvis.logging import setup_logging

    config = load_config()
    setup_logging(config.logging)

    console.print(f"[bold green]Jarvis v{__version__}[/] starting on {host}:{port}")

    uvicorn.run(
        "jarvis.main:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )


# --- Task commands ---


@cli.group()
def task() -> None:
    """Manage Jarvis tasks."""


def _api_url() -> str:
    from jarvis.config import load_config

    config = load_config()
    return f"http://{config.server.host}:{config.server.port}"


@task.command("create")
@click.argument("message")
def task_create(message: str) -> None:
    """Create a new task from a natural-language request."""
    import httpx

    try:
        resp = httpx.Client(base_url=_api_url()).post("/chat", json={"message": message})
        resp.raise_for_status()
    except httpx.ConnectError:
        console.print("[red]Error:[/] Cannot connect to Jarvis server. Is it running?")
        raise SystemExit(1)

    data = resp.json()
    console.print(f"[bold green]Task created:[/] {data['task_id']}")
    console.print(f"[bold]Title:[/] {data['title']}")
    console.print(f"[bold]Status:[/] {data['status']}")
    if data.get("plan"):
        console.print("[bold]Plan:[/]")
        for i, step in enumerate(data["plan"], 1):
            console.print(f"  {i}. {step}")
    console.print(f"\n{data.get('message', '')}")


@task.command("list")
@click.option("--status", default=None, help="Filter by status")
@click.option("--limit", default=20, type=int, help="Max results")
def task_list(status: str | None, limit: int) -> None:
    """List tasks."""
    import httpx

    try:
        params: dict[str, str | int] = {"limit": limit}
        if status:
            params["status"] = status
        resp = httpx.Client(base_url=_api_url()).get("/tasks", params=params)
        resp.raise_for_status()
    except httpx.ConnectError:
        console.print("[red]Error:[/] Cannot connect to Jarvis server. Is it running?")
        raise SystemExit(1)

    tasks = resp.json()
    if not tasks:
        console.print("[dim]No tasks found.[/]")
        return

    table = Table(title="Tasks")
    table.add_column("ID", style="cyan")
    table.add_column("Title", max_width=50)
    table.add_column("Status", style="bold")
    table.add_column("Priority")
    table.add_column("Created")

    for t in tasks:
        status_style = {
            "completed": "green",
            "failed": "red",
            "cancelled": "dim",
            "running": "yellow",
            "planning": "blue",
        }.get(t["status"], "")
        table.add_row(
            t["id"],
            t["title"][:50],
            f"[{status_style}]{t['status']}[/{status_style}]" if status_style else t["status"],
            t["priority"],
            t["created_at"][:19],
        )

    console.print(table)


@task.command("get")
@click.argument("task_id")
def task_get(task_id: str) -> None:
    """Get details of a specific task."""
    import httpx

    try:
        client = httpx.Client(base_url=_api_url())
        resp = client.get(f"/tasks/{task_id}")
        if resp.status_code == 404:
            console.print(f"[red]Task not found:[/] {task_id}")
            raise SystemExit(1)
        resp.raise_for_status()
    except httpx.ConnectError:
        console.print("[red]Error:[/] Cannot connect to Jarvis server. Is it running?")
        raise SystemExit(1)

    t = resp.json()
    console.print(f"[bold cyan]Task {t['id']}[/]")
    console.print(f"  [bold]Title:[/]    {t['title']}")
    console.print(f"  [bold]Status:[/]   {t['status']}")
    console.print(f"  [bold]Priority:[/] {t['priority']}")
    console.print(f"  [bold]Request:[/]  {t['request']}")
    console.print(f"  [bold]Created:[/]  {t['created_at'][:19]}")
    if t.get("plan"):
        console.print("  [bold]Plan:[/]")
        for i, step in enumerate(t["plan"], 1):
            console.print(f"    {i}. {step}")
    if t.get("result"):
        console.print(f"  [bold]Result:[/]  {t['result']}")
    if t.get("error"):
        console.print(f"  [bold red]Error:[/]   {t['error']}")


@task.command("cancel")
@click.argument("task_id")
def task_cancel(task_id: str) -> None:
    """Cancel a task."""
    import httpx

    try:
        resp = httpx.Client(base_url=_api_url()).post(f"/tasks/{task_id}/cancel")
        if resp.status_code == 404:
            console.print(f"[red]Task not found:[/] {task_id}")
            raise SystemExit(1)
        if resp.status_code == 409:
            console.print(f"[red]Cannot cancel:[/] {resp.json()['detail']}")
            raise SystemExit(1)
        resp.raise_for_status()
    except httpx.ConnectError:
        console.print("[red]Error:[/] Cannot connect to Jarvis server. Is it running?")
        raise SystemExit(1)

    t = resp.json()
    console.print(f"[bold yellow]Task {t['id']} cancelled.[/]")
