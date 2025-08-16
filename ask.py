#!/usr/bin/env python3
import subprocess
import os
import time
import sys
import click
import google.generativeai as genai
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm
from rich import print as rprint
from typing import Optional, List, Dict
from datetime import datetime

from chroma_rag import ChromaCommandRAG
from sandbox import CommandSandbox

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
console = Console()
rag_store = ChromaCommandRAG()
sandbox_manager = CommandSandbox()

def print_banner():
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                   AI Terminal Assistant                      ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    rprint(f"[bold cyan]{banner}[/bold cyan]")

def show_similar_commands(query: str, show_output: bool = True):
    """Show similar commands from RAG store"""
    similar = rag_store.search_similar_commands(query, top_k=3)
    
    if similar and show_output:
        console.print("\n[bold blue]🔍 Similar commands found in knowledge base:[/bold blue]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Query", style="dim", width=30)
        table.add_column("Command", style="green", width=40)
        table.add_column("Safety", justify="center", width=10)
        table.add_column("Score", justify="right", width=10)
        
        for cmd in similar:
            safety_color = "green" if cmd['safety_level'] <= 2 else "yellow" if cmd['safety_level'] <= 3 else "red"
            safety_text = f"[{safety_color}]{cmd['safety_level']}/5[/{safety_color}]"
            score_text = f"{cmd['similarity_score']:.2f}"
            
            table.add_row(
                cmd['query'][:28] + "..." if len(cmd['query']) > 28 else cmd['query'],
                cmd['command'][:38] + "..." if len(cmd['command']) > 38 else cmd['command'],
                safety_text,
                score_text
            )
        
        console.print(table)
    
    return similar

def generate_command_with_rag(prompt: str) -> str:
    if not GEMINI_API_KEY:
        console.print("[bold red]❌ Error:[/bold red] GEMINI_API_KEY environment variable is not set")
        console.print("\n[yellow]💡 To fix this:[/yellow]")
        console.print("1. Get your API key from: https://makersuite.google.com/app/apikey")
        console.print("2. Run: export GEMINI_API_KEY=\"your_api_key_here\"")
        sys.exit(1)
    
    similar_commands = rag_store.search_similar_commands(prompt, top_k=3)
    
    with console.status("[bold green]🤖 Thinking... Generating command with RAG", spinner="dots"):
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-pro')
            
            rag_context = ""
            if similar_commands:
                rag_context = "\n\nSimilar commands from knowledge base:\n"
                for cmd in similar_commands:
                    rag_context += f"- Query: '{cmd['query']}' -> Command: '{cmd['command']}'\n"
            
            system_prompt = f"""
            You are a Linux/macOS command expert. Convert the following natural language request into a single terminal command.
            Only respond with the command itself, no explanations or additional text.
            Make sure the command works on both Linux and macOS when possible.
            
            {rag_context}
            
            User Request: {prompt}
            
            Generate the most appropriate single command:
            """
            
            response = model.generate_content(system_prompt)
            time.sleep(0.3)
            
            generated_cmd = response.text.strip()
            
            safety_level = rag_store.get_safety_level(generated_cmd)
            rag_store.add_command(
                query=prompt,
                command=generated_cmd,
                description=f"AI generated for: {prompt}",
                category="ai_generated",
                safety_level=safety_level
            )
            
            return generated_cmd
            
        except Exception as e:
            console.print(f"[bold red]❌ Error generating command:[/bold red] {str(e)}")
            sys.exit(1)

@click.group()
def cli():
    """🌟 AI Terminal Assistant with RAG & Sandbox"""
    pass

@cli.command()
@click.argument('query')
@click.option('--execute', '-e', is_flag=True, help='Execute the generated command')
@click.option('--dry-run', '-d', is_flag=True, help='Show command without executing')
@click.option('--sandbox', '-s', is_flag=True, help='Force sandbox execution')
@click.option('--show-similar', is_flag=True, help='Show similar commands from knowledge base')
@click.option('--no-banner', is_flag=True, help='Skip banner display')
def ask(query, execute, dry_run, sandbox, show_similar, no_banner):
    
    if not no_banner:
        print_banner()
    
    if query:
        user_panel = Panel(
            f"[bold white]{query}[/bold white]",
            title="[bold blue]📝 Your Request[/bold blue]",
            border_style="blue",
            padding=(0, 1)
        )
        console.print(user_panel)
        
        if show_similar:
            show_similar_commands(query)
        
    try:
        cmd = generate_command_with_rag(query)
        
        cmd_panel = Panel(
            f"[bold green]{cmd}[/bold green]",
            title="[bold yellow]⚡ Generated Command[/bold yellow]",
            border_style="green",
            padding=(0, 1)
        )
        console.print(cmd_panel)
        
        is_risky, safety_level, reason = sandbox_manager.is_risky_command(cmd)
        if is_risky:
            console.print(f"[bold red]⚠️ RISKY COMMAND DETECTED[/bold red]")
            console.print(f"[yellow]Risk Level: {safety_level}/5 - {reason}[/yellow]")
        
        should_execute = False
        force_sandbox_mode = sandbox  
        
        if dry_run:
            console.print("[bold cyan]🔍 DRY RUN MODE - Command not executed[/bold cyan]")
            rag_store.add_to_history(query, cmd, executed=False)
            
        elif execute or sandbox:
            if execute and not sandbox and is_risky and safety_level >= 4:
                console.print("[bold red]❌ High-risk command detected. Use --sandbox flag for safe execution.[/bold red]")
                return
            
            if not sandbox and is_risky:
                console.print(f"\n[bold yellow]⚠️ About to execute risky command (Level {safety_level})...[/bold yellow]")
            else:
                console.print("\n[bold yellow]⚠️ About to execute command...[/bold yellow]")
            
            should_execute = Confirm.ask("[bold cyan]Do you want to proceed?[/bold cyan]", default=True)
        else:
            console.print()
            should_execute = Confirm.ask("[bold cyan]🚀 Do you want to execute this command?[/bold cyan]", default=False)
        
        if should_execute:
            use_sandbox = force_sandbox_mode or (is_risky and safety_level >= 3)
            
            if use_sandbox:
                console.print("\n[bold green]🔒 Executing in sandbox mode...[/bold green]")
                result = sandbox_manager.safe_execute(cmd, force_sandbox=True)
                
                if result["execution_result"]["exit_code"] == 0:
                    console.print("[bold green]✅ Command executed successfully in sandbox![/bold green]")
                    if result["execution_result"]["output"]:
                        output_panel = Panel(
                            result["execution_result"]["output"],
                            title="[bold green]📤 Sandbox Output[/bold green]",
                            border_style="green",
                            padding=(0, 1)
                        )
                        console.print(output_panel)
                else:
                    console.print("[bold red]❌ Command failed in sandbox![/bold red]")
                    if result["execution_result"]["error"]:
                        error_panel = Panel(
                            result["execution_result"]["error"],
                            title="[bold red]🚨 Sandbox Error[/bold red]",
                            border_style="red",
                            padding=(0, 1)
                        )
                        console.print(error_panel)
                
                rag_store.add_to_history(query, cmd, executed=True, 
                                       success=result["execution_result"]["exit_code"] == 0)
            else:
                console.print("\n[bold green]🚀 Executing command...[/bold green]")
                
                with console.status("[bold blue]Running command...", spinner="bouncingBar"):
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode == 0:
                    console.print("[bold green]✅ Command executed successfully![/bold green]")
                    if result.stdout:
                        output_panel = Panel(
                            result.stdout,
                            title="[bold green]📤 Output[/bold green]",
                            border_style="green",
                            padding=(0, 1)
                        )
                        console.print(output_panel)
                else:
                    console.print("[bold red]❌ Command failed![/bold red]")
                    if result.stderr:
                        error_panel = Panel(
                            result.stderr,
                            title="[bold red]🚨 Error Output[/bold red]",
                            border_style="red",
                            padding=(0, 1)
                        )
                        console.print(error_panel)
                
                rag_store.add_to_history(query, cmd, executed=True, success=result.returncode == 0)
        else:
            if not dry_run:
                console.print("[yellow]⏸️ Command execution cancelled.[/yellow]")
                console.print("\n[dim]💡 Tip: Use -e/--execute to run automatically, -d/--dry-run to preview, or -s/--sandbox for safe execution[/dim]")
                rag_store.add_to_history(query, cmd, executed=False)

    except KeyboardInterrupt:
        console.print("\n[yellow]⏸️ Operation cancelled by user.[/yellow]")
    except Exception as e:
        console.print(f"[bold red]❌ Unexpected error:[/bold red] {str(e)}")

@cli.command()
@click.option('--limit', '-l', default=10, help='Number of history entries to show')
def history(limit):
    console.print("[bold blue]📜 Query History[/bold blue]\n")
    
    history_entries = rag_store.get_history(limit)
    
    if not history_entries:
        console.print("[yellow]No history entries found.[/yellow]")
        return
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Time", style="dim", width=20)
    table.add_column("Query", style="cyan", width=30)
    table.add_column("Command", style="green", width=35)
    table.add_column("Status", justify="center", width=10)
    
    for entry in history_entries:
        timestamp = datetime.fromisoformat(entry['timestamp']).strftime("%Y-%m-%d %H:%M")
        
        status = "❌" if entry['executed'] and entry['success'] is False else \
                "✅" if entry['executed'] and entry['success'] is True else \
                "⏸️" if not entry['executed'] else "?"
        
        table.add_row(
            timestamp,
            entry['user_query'][:28] + "..." if len(entry['user_query']) > 28 else entry['user_query'],
            entry['generated_command'][:33] + "..." if len(entry['generated_command']) > 33 else entry['generated_command'],
            status
        )
    
    console.print(table)

@cli.command()
@click.argument('query')
@click.argument('command')
@click.option('--description', '-d', default="", help='Command description')
@click.option('--category', '-c', default="user", help='Command category')
@click.option('--safety', '-s', default=1, type=int, help='Safety level (1-5)')
def learn(query, command, description, category, safety):
    rag_store.add_command(query, command, description, category, safety)
    console.print(f"[bold green]✅ Added command to knowledge base:[/bold green]")
    console.print(f"[cyan]Query:[/cyan] {query}")
    console.print(f"[green]Command:[/green] {command}")
    console.print(f"[yellow]Safety Level:[/yellow] {safety}/5")

@cli.command()
@click.argument('query')
def search(query):
    similar = show_similar_commands(query, show_output=False)
    
    if similar:
        console.print(f"\n[bold blue]🔍 Found {len(similar)} similar commands:[/bold blue]")
        show_similar_commands(query, show_output=True)
    else:
        console.print("[yellow]No similar commands found in knowledge base.[/yellow]")

@cli.command()
def cleanup():
    console.print("[bold blue]🧹 Cleaning up sandbox resources...[/bold blue]")
    sandbox_manager.cleanup()
    console.print("[bold green]✅ Cleanup completed![/bold green]")

@cli.command()
def stats():
    stats = rag_store.get_command_statistics()
    
    console.print("[bold blue]📊 Knowledge Base Statistics[/bold blue]\n")
    
    main_stats = f"""[bold]Total Commands:[/bold] [green]{stats['total_commands']}[/green]
[bold]Total Queries:[/bold] [cyan]{stats['total_queries']}[/cyan]
[bold]Executed Queries:[/bold] [yellow]{stats['executed_queries']}[/yellow]
[bold]Successful Executions:[/bold] [green]{stats['successful_executions']}[/green]
[bold]Success Rate:[/bold] [green]{(stats['successful_executions']/max(stats['executed_queries'], 1)*100):.1f}%[/green]
[bold]Avg Execution Time:[/bold] [cyan]{stats['avg_execution_time']:.2f}s[/cyan]"""
    
    panel = Panel(
        main_stats,
        title="[bold green]📈 Overall Statistics[/bold green]",
        border_style="green",
        padding=(1, 1)
    )
    console.print(panel)
    
    if stats['categories']:
        console.print("\n[bold blue]📂 Commands by Category[/bold blue]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Category", style="cyan")
        table.add_column("Commands", justify="right", style="green")
        table.add_column("Avg Safety", justify="center", style="yellow")
        table.add_column("Success Rate", justify="right", style="green")
        
        for cat_name, cat_data in stats['categories'].items():
            avg_safety = cat_data['avg_safety'] or 1.0
            safety_color = "green" if avg_safety <= 2 else "yellow" if avg_safety <= 3 else "red"
            success_rate = (cat_data['success_rate'] or 1.0) * 100
            
            table.add_row(
                cat_name,
                str(cat_data['count']),
                f"[{safety_color}]{avg_safety:.1f}[/{safety_color}]",
                f"{success_rate:.1f}%"
            )
        
        console.print(table)

if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]⏸️ Operation cancelled by user.[/yellow]")
    finally:
        sandbox_manager.cleanup()