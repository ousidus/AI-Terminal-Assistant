#!/usr/bin/env python3
"""
Enhanced CLI commands for ChromaDB RAG system
"""
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
from datetime import datetime

from chroma_rag import ChromaCommandRAG

console = Console()

@click.group()
def rag_cli():
    """🧠 RAG Knowledge Base Management"""
    pass

@rag_cli.command()
@click.option('--category', '-c', help='Filter by category')
@click.option('--min-safety', type=int, default=1, help='Minimum safety level to show')
@click.option('--max-safety', type=int, default=5, help='Maximum safety level to show')
def list_commands(category, min_safety, max_safety):
    """📋 List all commands in the knowledge base"""
    rag = ChromaCommandRAG()
    
    # Get statistics first
    stats = rag.get_command_statistics()
    
    console.print(f"[bold blue]📊 Knowledge Base Statistics[/bold blue]")
    console.print(f"Total Commands: [green]{stats['total_commands']}[/green]")
    console.print(f"Total Queries: [cyan]{stats['total_queries']}[/cyan]")
    console.print(f"Success Rate: [green]{(stats['successful_executions']/max(stats['executed_queries'], 1)*100):.1f}%[/green]\n")
    
    # Show categories
    if stats['categories']:
        table = Table(title="📂 Commands by Category", show_header=True, header_style="bold magenta")
        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right", style="green")
        table.add_column("Avg Safety", justify="center", style="yellow")
        table.add_column("Success Rate", justify="right", style="green")
        
        for cat_name, cat_data in stats['categories'].items():
            if category and category.lower() not in cat_name.lower():
                continue
                
            avg_safety = cat_data['avg_safety'] or 1.0
            if not (min_safety <= avg_safety <= max_safety):
                continue
                
            safety_color = "green" if avg_safety <= 2 else "yellow" if avg_safety <= 3 else "red"
            success_rate = (cat_data['success_rate'] or 1.0) * 100
            
            table.add_row(
                cat_name,
                str(cat_data['count']),
                f"[{safety_color}]{avg_safety:.1f}[/{safety_color}]",
                f"{success_rate:.1f}%"
            )
        
        console.print(table)

@rag_cli.command()
@click.argument('query')
@click.option('--top-k', '-k', default=5, help='Number of similar commands to show')
@click.option('--min-similarity', '-s', default=0.3, type=float, help='Minimum similarity threshold')
def search_detailed(query, top_k, min_similarity):
    """🔍 Detailed search with similarity scores and metadata"""
    rag = ChromaCommandRAG()
    
    console.print(f"[bold blue]🔍 Searching for:[/bold blue] [cyan]'{query}'[/cyan]\n")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Searching knowledge base...", total=None)
        results = rag.search_similar_commands(query, top_k=top_k, min_similarity=min_similarity)
        progress.update(task, completed=100)
    
    if not results:
        console.print("[yellow]No similar commands found.[/yellow]")
        return
    
    for i, cmd in enumerate(results, 1):
        # Color coding based on similarity
        if cmd['similarity_score'] >= 0.8:
            border_color = "green"
            score_color = "bold green"
        elif cmd['similarity_score'] >= 0.6:
            border_color = "yellow" 
            score_color = "bold yellow"
        else:
            border_color = "red"
            score_color = "bold red"
        
        # Safety level styling
        safety_level = cmd['safety_level']
        safety_color = "green" if safety_level <= 2 else "yellow" if safety_level <= 3 else "red"
        
        # Create detailed panel
        content = f"""[bold]Query:[/bold] {cmd['query']}
[bold]Command:[/bold] [green]{cmd['command']}[/green]
[bold]Description:[/bold] {cmd['description']}
[bold]Category:[/bold] [cyan]{cmd['category']}[/cyan]
[bold]Safety Level:[/bold] [{safety_color}]{safety_level}/5[/{safety_color}]
[bold]Usage Count:[/bold] {cmd['usage_count']}
[bold]Success Rate:[/bold] [green]{cmd['success_rate']*100:.1f}%[/green]
[bold]Similarity:[/bold] [{score_color}]{cmd['similarity_score']:.3f}[/{score_color}]"""

        if cmd['last_used']:
            content += f"\n[bold]Last Used:[/bold] [dim]{cmd['last_used']}[/dim]"
        
        panel = Panel(
            content,
            title=f"[bold]Result #{i}[/bold]",
            border_style=border_color,
            padding=(1, 1)
        )
        console.print(panel)

@rag_cli.command()
@click.argument('old_query')
@click.argument('new_query')
@click.argument('new_command')
@click.option('--description', '-d', default="", help='Updated description')
@click.option('--safety', '-s', default=1, type=int, help='Safety level (1-5)')
def update_command(old_query, new_query, new_command, description, safety):
    """✏️ Update an existing command in the knowledge base"""
    rag = ChromaCommandRAG()
    
    # Search for the command to update
    results = rag.search_similar_commands(old_query, top_k=1, min_similarity=0.9)
    
    if not results:
        console.print(f"[red]❌ No exact match found for query: '{old_query}'[/red]")
        return
    
    console.print(f"[yellow]📝 Updating command...[/yellow]")
    
    # Add the new version (ChromaDB will handle the update)
    cmd_id = rag.add_command(new_query, new_command, description, "updated", safety)
    
    console.print(f"[green]✅ Command updated successfully![/green]")
    console.print(f"[cyan]New ID:[/cyan] {cmd_id}")

@rag_cli.command()
def export_knowledge():
    """📤 Export knowledge base to JSON file"""
    rag = ChromaCommandRAG()
    
    console.print("[blue]📤 Exporting knowledge base...[/blue]")
    
    # Get all commands by searching with a broad query
    all_commands = rag.search_similar_commands("command", top_k=1000, min_similarity=0.0)
    
    export_data = {
        "exported_at": datetime.now().isoformat(),
        "total_commands": len(all_commands),
        "commands": all_commands,
        "statistics": rag.get_command_statistics()
    }
    
    filename = f"knowledge_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    import json
    with open(filename, 'w') as f:
        json.dump(export_data, f, indent=2, default=str)
    
    console.print(f"[green]✅ Knowledge base exported to:[/green] [cyan]{filename}[/cyan]")
    console.print(f"[dim]Total commands exported: {len(all_commands)}[/dim]")

@rag_cli.command()
@click.argument('filename')
def import_knowledge(filename):
    """📥 Import knowledge base from JSON file"""
    rag = ChromaCommandRAG()
    
    try:
        import json
        with open(filename, 'r') as f:
            data = json.load(f)
        
        console.print(f"[blue]📥 Importing from:[/blue] [cyan]{filename}[/cyan]")
        
        commands = data.get('commands', [])
        imported_count = 0
        
        with Progress(console=console) as progress:
            task = progress.add_task("Importing commands...", total=len(commands))
            
            for cmd in commands:
                try:
                    rag.add_command(
                        query=cmd['query'],
                        command=cmd['command'],
                        description=cmd.get('description', ''),
                        category=cmd.get('category', 'imported'),
                        safety_level=cmd.get('safety_level', 1)
                    )
                    imported_count += 1
                    progress.advance(task)
                except Exception as e:
                    console.print(f"[red]Failed to import: {cmd['query']} - {e}[/red]")
        
        console.print(f"[green]✅ Successfully imported {imported_count}/{len(commands)} commands[/green]")
        
    except FileNotFoundError:
        console.print(f"[red]❌ File not found:[/red] {filename}")
    except json.JSONDecodeError:
        console.print(f"[red]❌ Invalid JSON file:[/red] {filename}")
    except Exception as e:
        console.print(f"[red]❌ Import error:[/red] {e}")

@rag_cli.command()
@click.confirmation_option(prompt='Are you sure you want to reset the entire knowledge base?')
def reset():
    """🗑️ Reset the entire knowledge base (DANGEROUS)"""
    rag = ChromaCommandRAG()
    
    console.print("[red]🗑️ Resetting knowledge base...[/red]")
    rag.reset_database()
    console.print("[green]✅ Knowledge base reset complete![/green]")
    console.print("[yellow]Default commands have been reloaded.[/yellow]")

if __name__ == "__main__":
    rag_cli()