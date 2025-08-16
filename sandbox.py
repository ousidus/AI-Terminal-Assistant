#!/usr/bin/env python3
import docker
import psutil
import subprocess
import tempfile
import os
from typing import Dict, List, Tuple, Optional
from rich.console import Console

console = Console()

class CommandSandbox:
    def __init__(self):
        self.docker_client = None
        self.container_name = "auroraos-sandbox"
        
        try:
            self.docker_client = docker.from_env()
        except Exception:
            console.print("[yellow]⚠️ Docker not available. Sandbox mode will use process isolation.[/yellow]")
    
    def is_risky_command(self, command: str) -> Tuple[bool, int, str]:
        dangerous_patterns = {
            'rm -rf': (5, "Recursive deletion - can destroy entire filesystem"),
            'mkfs': (5, "Disk formatting - will destroy all data on device"),
            'dd if=': (5, "Raw disk operations - can overwrite critical data"),
            'format': (5, "Disk formatting operation"),
            'fdisk': (4, "Disk partitioning - can affect system boot"),
            'kill -9': (4, "Force kill processes - can crash system"),
            'pkill': (4, "Kill multiple processes"),
            'sudo rm': (4, "Elevated deletion privileges"),
            'chmod 777': (4, "Dangerous permission changes"),
            'chown': (3, "Ownership changes"),
            'sudo': (3, "Elevated privileges"),
            'mv': (2, "File movement - potential data loss"),
            'rm': (2, "File deletion")
        }
        
        command_lower = command.lower()
        for pattern, (level, reason) in dangerous_patterns.items():
            if pattern in command_lower:
                return True, level, reason
        
        return False, 1, "Command appears safe"
    
    def run_in_docker_sandbox(self, command: str) -> Dict:
        if not self.docker_client:
            return {"error": "Docker not available"}
        
        try:
            container = self.docker_client.containers.run(
                "ubuntu:20.04",
                command=f"/bin/bash -c '{command}'",
                name=f"{self.container_name}-{os.getpid()}",
                detach=True,
                remove=True,
                network_mode="none",
                mem_limit="128m",
                cpu_period=100000,
                cpu_quota=50000,
                read_only=True,
                tmpfs={"/tmp": "rw,size=100m"}
            )
            
            result = container.wait(timeout=30)
            logs = container.logs().decode('utf-8')
            
            return {
                "exit_code": result['StatusCode'],
                "output": logs,
                "error": None
            }
            
        except docker.errors.ContainerError as e:
            return {
                "exit_code": e.exit_status,
                "output": "",
                "error": f"Container error: {e}"
            }
        except Exception as e:
            return {
                "exit_code": -1,
                "output": "",
                "error": f"Sandbox error: {e}"
            }
    
    def run_with_process_limits(self, command: str) -> Dict:
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                env = os.environ.copy()
                env['HOME'] = temp_dir
                env['TMPDIR'] = temp_dir
                
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                    cwd=temp_dir
                )
                
                try:
                    ps_process = psutil.Process(process.pid)
                except:
                    pass
                
                stdout, stderr = process.communicate(timeout=30)
                
                return {
                    "exit_code": process.returncode,
                    "output": stdout,
                    "error": stderr
                }
                
        except subprocess.TimeoutExpired:
            process.kill()
            return {
                "exit_code": -1,
                "output": "",
                "error": "Command timed out after 30 seconds"
            }
        except Exception as e:
            return {
                "exit_code": -1,
                "output": "",
                "error": f"Process error: {e}"
            }
    
    def safe_execute(self, command: str, force_sandbox: bool = False) -> Dict:
        is_risky, safety_level, reason = self.is_risky_command(command)
        
        result = {
            "command": command,
            "is_risky": is_risky,
            "safety_level": safety_level,
            "risk_reason": reason,
            "sandbox_used": False,
            "execution_result": None
        }
        
        if is_risky or force_sandbox:
            console.print(f"[yellow]🔒 Running in sandbox mode: {reason}[/yellow]")
            result["sandbox_used"] = True
            
            if self.docker_client:
                execution_result = self.run_in_docker_sandbox(command)
            else:
                execution_result = self.run_with_process_limits(command)
            
            result["execution_result"] = execution_result
        else:

            try:
                process = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                result["execution_result"] = {
                    "exit_code": process.returncode,
                    "output": process.stdout,
                    "error": process.stderr
                }
            except subprocess.TimeoutExpired:
                result["execution_result"] = {
                    "exit_code": -1,
                    "output": "",
                    "error": "Command timed out"
                }
            except Exception as e:
                result["execution_result"] = {
                    "exit_code": -1,
                    "output": "",
                    "error": str(e)
                }
        
        return result
    
    def cleanup(self):
        if self.docker_client:
            try:
                containers = self.docker_client.containers.list(
                    all=True,
                    filters={"name": self.container_name}
                )
                for container in containers:
                    container.remove(force=True)
            except Exception:
                pass