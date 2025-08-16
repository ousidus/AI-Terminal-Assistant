#!/usr/bin/env python3
"""
ChromaDB-based RAG Vector Store for command knowledge base
"""
import os
import json
import chromadb
import sqlite3
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from chromadb.config import Settings

class ChromaCommandRAG:
    def __init__(self, db_path: str = "commands.db", chroma_path: str = "./chroma_db"):
        self.db_path = db_path
        self.chroma_path = chroma_path
        
        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=chroma_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        self.collection = self.chroma_client.get_or_create_collection(
            name="command_knowledge",
            metadata={"description": "Terminal commands knowledge base"},
            embedding_function=chromadb.utils.embedding_functions.DefaultEmbeddingFunction()
        )
        
        self._init_database()
        self._load_default_commands()
    
    def _init_database(self):
        """Initialize SQLite database for additional metadata and history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Commands metadata table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS commands_metadata (
                id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                command TEXT NOT NULL,
                description TEXT,
                category TEXT,
                safety_level INTEGER DEFAULT 1,
                usage_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP
            )
        ''')
        
        # Query history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS query_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_query TEXT NOT NULL,
                generated_command TEXT NOT NULL,
                executed BOOLEAN DEFAULT FALSE,
                success BOOLEAN DEFAULT NULL,
                execution_time REAL DEFAULT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Performance metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_type TEXT,
                similarity_score REAL,
                execution_success BOOLEAN,
                user_satisfaction INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _load_default_commands(self):
        """Load default command knowledge base into ChromaDB"""
        default_commands = [
            {
                "query": "list files in directory",
                "command": "ls -la",
                "description": "List all files including hidden ones with detailed info",
                "category": "filesystem",
                "safety_level": 1
            },
            {
                "query": "show disk usage",
                "command": "df -h",
                "description": "Show disk space usage in human readable format",
                "category": "system",
                "safety_level": 1
            },
            {
                "query": "find process by name",
                "command": "ps aux | grep {process_name}",
                "description": "Find running processes by name",
                "category": "process",
                "safety_level": 1
            },
            {
                "query": "show memory usage",
                "command": "free -h",
                "description": "Display memory usage in human readable format",
                "category": "system",
                "safety_level": 1
            },
            {
                "query": "show running processes",
                "command": "top",
                "description": "Display running processes in real-time",
                "category": "process",
                "safety_level": 1
            },
            {
                "query": "find large files",
                "command": "find . -type f -size +100M -exec ls -lh {} \\;",
                "description": "Find files larger than 100MB",
                "category": "filesystem",
                "safety_level": 1
            },
            {
                "query": "compress directory to tar",
                "command": "tar -czf {output}.tar.gz {directory}",
                "description": "Create compressed tar archive",
                "category": "archive",
                "safety_level": 1
            },
            {
                "query": "extract tar archive",
                "command": "tar -xzf {archive}.tar.gz",
                "description": "Extract tar.gz archive",
                "category": "archive",
                "safety_level": 2
            },
            {
                "query": "monitor system resources",
                "command": "htop",
                "description": "Interactive process monitor with resource usage",
                "category": "monitoring",
                "safety_level": 1
            },
            {
                "query": "search text in files",
                "command": "grep -r \"{pattern}\" .",
                "description": "Search for text pattern recursively in files",
                "category": "search",
                "safety_level": 1
            },
            {
                "query": "show network connections",
                "command": "netstat -tuln",
                "description": "Show active network connections and listening ports",
                "category": "network",
                "safety_level": 1
            },
            {
                "query": "copy files recursively",
                "command": "cp -r {source} {destination}",
                "description": "Copy files and directories recursively",
                "category": "filesystem",
                "safety_level": 2
            },
            {
                "query": "change file permissions",
                "command": "chmod {permissions} {file}",
                "description": "Change file or directory permissions",
                "category": "filesystem",
                "safety_level": 3
            },
            {
                "query": "kill process by name",
                "command": "pkill -f {pattern}",
                "description": "DANGEROUS: Kill processes matching pattern",
                "category": "process",
                "safety_level": 4
            },
            {
                "query": "delete all files recursively",
                "command": "rm -rf {path}",
                "description": "EXTREMELY DANGEROUS: Recursively delete files and directories",
                "category": "filesystem",
                "safety_level": 5
            },
            {
                "query": "format disk partition",
                "command": "mkfs.ext4 {device}",
                "description": "EXTREMELY DANGEROUS: Format a disk partition",
                "category": "system",
                "safety_level": 5
            }
        ]
        
        # Check if collection is empty
        if self.collection.count() == 0:
            self._batch_add_commands(default_commands)
    
    def _batch_add_commands(self, commands: List[Dict]):
        """Add multiple commands to ChromaDB in batch"""
        documents = []
        metadatas = []
        ids = []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for i, cmd in enumerate(commands):
            cmd_id = f"cmd_{i}_{hash(cmd['query'] + cmd['command']) % 10000}"
            
            # Prepare document for embedding (query + description + command)
            document = f"Query: {cmd['query']} Description: {cmd['description']} Command: {cmd['command']}"
            documents.append(document)
            
            # Prepare metadata for ChromaDB
            metadata = {
                "query": cmd["query"],
                "command": cmd["command"],
                "category": cmd["category"],
                "safety_level": cmd["safety_level"]
            }
            metadatas.append(metadata)
            ids.append(cmd_id)
            
            # Store additional metadata in SQLite
            cursor.execute('''
                INSERT OR REPLACE INTO commands_metadata 
                (id, query, command, description, category, safety_level)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (cmd_id, cmd["query"], cmd["command"], cmd["description"], 
                  cmd["category"], cmd["safety_level"]))
        
        # Add to ChromaDB
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        conn.commit()
        conn.close()
    
    def add_command(self, query: str, command: str, description: str = "", 
                   category: str = "user", safety_level: int = 1) -> str:
        """Add a single command to the knowledge base"""
        cmd_id = f"user_{hash(query + command + str(datetime.now().timestamp())) % 100000}"
        
        # Prepare document for embedding
        document = f"Query: {query} Description: {description} Command: {command}"
        
        # Add to ChromaDB
        self.collection.add(
            documents=[document],
            metadatas=[{
                "query": query,
                "command": command,
                "category": category,
                "safety_level": safety_level
            }],
            ids=[cmd_id]
        )
        
        # Store in SQLite
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO commands_metadata 
            (id, query, command, description, category, safety_level)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (cmd_id, query, command, description, category, safety_level))
        conn.commit()
        conn.close()
        
        return cmd_id
    
    def search_similar_commands(self, query: str, top_k: int = 5, 
                              min_similarity: float = 0.5) -> List[Dict]:
        """Search for similar commands using ChromaDB vector similarity"""
        if self.collection.count() == 0:
            return []
        
        # Search in ChromaDB
        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, self.collection.count()),
            include=["documents", "metadatas", "distances"]
        )
        
        if not results["documents"] or not results["documents"][0]:
            return []
        
        # Process results
        similar_commands = []
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for i, (metadata, distance) in enumerate(zip(results["metadatas"][0], results["distances"][0])):
            # Convert distance to similarity score (ChromaDB returns distances, lower is better)
            similarity_score = 1.0 / (1.0 + distance)
            
            if similarity_score < min_similarity:
                continue
            
            # Get additional metadata from SQLite
            cursor.execute('''
                SELECT description, usage_count, success_rate, last_used
                FROM commands_metadata WHERE query = ? AND command = ?
            ''', (metadata["query"], metadata["command"]))
            
            db_result = cursor.fetchone()
            
            command_info = {
                "query": metadata["query"],
                "command": metadata["command"],
                "category": metadata["category"],
                "safety_level": metadata["safety_level"],
                "similarity_score": similarity_score,
                "distance": distance,
                "description": db_result[0] if db_result else "",
                "usage_count": db_result[1] if db_result else 0,
                "success_rate": db_result[2] if db_result else 1.0,
                "last_used": db_result[3] if db_result else None
            }
            
            similar_commands.append(command_info)
        
        conn.close()
        
        # Sort by similarity score (highest first)
        similar_commands.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        return similar_commands
    
    def update_command_usage(self, command_id: str, success: bool = True, execution_time: float = None):
        """Update command usage statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Update usage statistics
        cursor.execute('''
            UPDATE commands_metadata 
            SET usage_count = usage_count + 1,
                last_used = CURRENT_TIMESTAMP,
                success_rate = (success_rate * usage_count + ?) / (usage_count + 1)
            WHERE id = ?
        ''', (1.0 if success else 0.0, command_id))
        
        conn.commit()
        conn.close()
    
    def add_to_history(self, user_query: str, generated_command: str, 
                      executed: bool = False, success: bool = None, 
                      execution_time: float = None):
        """Add query to history with enhanced tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO query_history 
            (user_query, generated_command, executed, success, execution_time)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_query, generated_command, executed, success, execution_time))
        
        conn.commit()
        conn.close()
    
    def get_history(self, limit: int = 10) -> List[Dict]:
        """Get recent query history with enhanced information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_query, generated_command, executed, success, 
                   execution_time, timestamp
            FROM query_history 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'user_query': row[0],
                'generated_command': row[1],
                'executed': row[2],
                'success': row[3],
                'execution_time': row[4],
                'timestamp': row[5]
            })
        
        conn.close()
        return results
    
    def get_command_statistics(self) -> Dict:
        """Get overall statistics about the knowledge base"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Command count by category
        cursor.execute('''
            SELECT category, COUNT(*), AVG(safety_level), AVG(success_rate)
            FROM commands_metadata 
            GROUP BY category
        ''')
        categories = cursor.fetchall()
        
        # Total commands
        total_commands = self.collection.count()
        
        # History statistics
        cursor.execute('''
            SELECT COUNT(*), 
                   SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END),
                   AVG(execution_time)
            FROM query_history
        ''')
        history_stats = cursor.fetchone()
        
        conn.close()
        
        return {
            "total_commands": total_commands,
            "categories": {cat[0]: {"count": cat[1], "avg_safety": cat[2], "success_rate": cat[3]} 
                          for cat in categories},
            "total_queries": history_stats[0] or 0,
            "executed_queries": history_stats[1] or 0,
            "successful_executions": history_stats[2] or 0,
            "avg_execution_time": history_stats[3] or 0.0
        }
    
    def get_safety_level(self, command: str) -> int:
        """Analyze command safety level with enhanced patterns"""
        dangerous_patterns = {
            5: ['rm -rf', 'mkfs', 'dd if=', 'format', 'fdisk', '>/dev/', 'sudo dd', 'wipefs'],
            4: ['kill -9', 'pkill', 'killall', 'sudo rm', 'chmod 777', 'chown -R', 'sudo chmod'],
            3: ['sudo', 'mv', 'cp -r', 'chown', 'chmod', 'mount', 'umount', 'systemctl'],
            2: ['rm', 'rmdir', 'unzip', 'tar -x', 'git reset --hard', 'npm install -g']
        }
        
        command_lower = command.lower()
        for level, patterns in dangerous_patterns.items():
            for pattern in patterns:
                if pattern in command_lower:
                    return level
        
        return 1  # Safe by default
    
    def cleanup(self):
        """Clean up ChromaDB resources"""
        try:
            # ChromaDB handles cleanup automatically
            pass
        except Exception:
            pass
    
    def reset_database(self):
        """Reset the entire knowledge base (use with caution)"""
        # Reset ChromaDB collection
        self.chroma_client.delete_collection("command_knowledge")
        self.collection = self.chroma_client.get_or_create_collection(
            name="command_knowledge",
            metadata={"description": "Terminal commands knowledge base"},
            embedding_function=chromadb.utils.embedding_functions.DefaultEmbeddingFunction()
        )
        
        # Reset SQLite database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM commands_metadata")
        cursor.execute("DELETE FROM query_history")
        cursor.execute("DELETE FROM performance_metrics")
        conn.commit()
        conn.close()
        
        # Reload default commands
        self._load_default_commands()