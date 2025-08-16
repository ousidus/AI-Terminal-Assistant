#!/usr/bin/env python3
import subprocess
import argparse
import os
import time
import sys
import google.generativeai as genai
from rich.console import Console
from rich.spinner import Spinner
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm
from rich import print as rprint

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
console = Console()

def print_banner():
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                   AI Terminal Assistant                      ║
    ║              Transform natural language to commands          ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    rprint(f"[bold cyan]{banner}[/bold cyan]")

def generate_command(prompt):
    if not GEMINI_API_KEY:
        console.print("[bold red]❌ Error:[/bold red] GEMINI_API_KEY environment variable is not set", style="red")
        console.print("\n[yellow]💡 To fix this:[/yellow]")
        console.print("1. Get your API key from: https://makersuite.google.com/app/apikey")
        console.print("2. Run: export GEMINI_API_KEY=\"your_api_key_here\"")
        sys.exit(1)
    
    with console.status("[bold green]🤖 Thinking... Generating command", spinner="dots"):
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-pro')
            
            system_prompt = f"""
            You are a Linux/macOS command expert. Convert the following natural language request into a single terminal command.
            Only respond with the command itself, no explanations or additional text.
            Make sure the command works on both Linux and macOS when possible.
            
            Request: {prompt}
            """
            
            response = model.generate_content(system_prompt)
            time.sleep(0.5)  
            return response.text.strip()
            
        except Exception as e:
            console.print(f"[bold red]❌ Error generating command:[/bold red] {str(e)}")
            sys.exit(1)

def main():
    print_banner()
    
    parser = argparse.ArgumentParser(description="Ask Linux commands in natural language")
    parser.add_argument("query", type=str, help="Your natural language command")
    parser.add_argument("--execute", action="store_true", help="Execute the generated command")
    args = parser.parse_args()

    # Display user input in a nice panel
    user_panel = Panel(
        f"[bold white]{args.query}[/bold white]",
        title="[bold blue]📝 Your Request[/bold blue]",
        border_style="blue",
        padding=(0, 1)
    )
    console.print(user_panel)

    try:
        cmd = generate_command(args.query)
        
        cmd_panel = Panel(
            f"[bold green]{cmd}[/bold green]",
            title="[bold yellow]⚡ Generated Command[/bold yellow]",
            border_style="green",
            padding=(0, 1)
        )
        console.print(cmd_panel)

        if args.execute:
            console.print("\n[bold yellow]⚠️  About to execute this command...[/bold yellow]")
            
            if Confirm.ask("[bold cyan]Do you want to proceed?[/bold cyan]", default=True):
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
            else:
                console.print("[yellow]⏸️  Command execution cancelled.[/yellow]")
        else:
            console.print("\n[dim]💡 Tip: Add --execute to run the command automatically[/dim]")

    except KeyboardInterrupt:
        console.print("\n[yellow]⏸️  Operation cancelled by user.[/yellow]")
    except Exception as e:
        console.print(f"[bold red]❌ Unexpected error:[/bold red] {str(e)}")

if __name__ == "__main__":
    main()
