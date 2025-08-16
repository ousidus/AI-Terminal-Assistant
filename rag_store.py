#!/usr/bin/env python3
"""
RAG Vector Store for command knowledge base
"""
import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Tuple
import sqlite3
from datetime import datetime

class CommandRAGStore:
    def __init__(self, db_path: str = "commands.db", vector_dim: int = 384):
        self.db_path = db_path
        self.vector_dim = vector_dim
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = faiss.IndexFlatIP(vector_dim)  # Inner product for similarity
        
        self._init_database()
        self._load_default_commands()
    
    def _init_database(self):
        """Initialize SQLite database for command storage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Commands table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                command TEXT NOT NULL,
                description TEXT,
                category TEXT,
                safety_level INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _load_default_commands(self):
        """Load default command knowledge base"""
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
                "query": "delete all files recursively",
                "command": "rm -rf {path}",
                "description": "DANGEROUS: Recursively delete files and directories",
                "category": "filesystem",
                "safety_level": 5
            },
            {
                "query": "format disk",
                "command": "mkfs.ext4 {device}",
                "description": "EXTREMELY DANGEROUS: Format a disk partition",
                "category": "system",
                "safety_level": 5
            },
            {
                "query": "kill all processes",
                "command": "pkill -f {pattern}",
                "description": "DANGEROUS: Kill processes matching pattern",
                "category": "process",
                "safety_level": 4
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
            }
        ]
        
        # Check if commands already exist
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM commands")
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Add default commands
            for cmd in default_commands:
                self.add_command(**cmd)
        
        conn.close()
        self._rebuild_index()
    
    def add_command(self, query: str, command: str, description: str = "", 
                   category: str = "general", safety_level: int = 1):
        """Add a new command to the knowledge base"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO commands (query, command, description, category, safety_level)
            VALUES (?, ?, ?, ?, ?)
        ''', (query, command, description, category, safety_level))
        
        conn.commit()
        conn.close()
        
        # Update vector index
        self._rebuild_index()
    
    def _rebuild_index(self):
        """Rebuild FAISS index with all commands"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, query, description FROM commands")
        commands = cursor.fetchall()
        conn.close()
        
        if not commands:
            return
        
        # Create embeddings
        texts = [f"{cmd[1]} {cmd[2]}" for cmd in commands]  # query + description
        embeddings = self.model.encode(texts)
        
        # Normalize embeddings for cosine similarity
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        
        # Rebuild index
        self.index = faiss.IndexFlatIP(self.vector_dim)
        self.index.add(embeddings.astype('float32'))
        
        # Store command IDs for retrieval
        self.command_ids = [cmd[0] for cmd in commands]
    
    def search_similar_commands(self, query: str, top_k: int = 3) -> List[Dict]:
        """Search for similar commands using vector similarity"""
        if self.index.ntotal == 0:
            return []
        
        # Encode query
        query_embedding = self.model.encode([query])
        query_embedding = query_embedding / np.linalg.norm(query_embedding, axis=1, keepdims=True)
        
        # Search
        scores, indices = self.index.search(query_embedding.astype('float32'), top_k)
        
        # Retrieve commands
        results = []
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx >= len(self.command_ids):
                continue
                
            cmd_id = self.command_ids[idx]
            cursor.execute('''
                SELECT query, command, description, category, safety_level 
                FROM commands WHERE id = ?
            ''', (cmd_id,))
            
            result = cursor.fetchone()
            if result:
                results.append({
                    'query': result[0],
                    'command': result[1],
                    'description': result[2],
                    'category': result[3],
                    'safety_level': result[4],
                    'similarity_score': float(score)
                })
        
        conn.close()
        return results
    
    def add_to_history(self, user_query: str, generated_command: str, 
                      executed: bool = False, success: bool = None):
        """Add query to history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO query_history (user_query, generated_command, executed, success)
            VALUES (?, ?, ?, ?)
        ''', (user_query, generated_command, executed, success))
        
        conn.commit()
        conn.close()
    
    def get_history(self, limit: int = 10) -> List[Dict]:
        """Get recent query history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_query, generated_command, executed, success, timestamp
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
                'timestamp': row[4]
            })
        
        conn.close()
        return results
    
    def get_safety_level(self, command: str) -> int:
        """Analyze command safety level"""
        dangerous_patterns = {
            5: ['rm -rf', 'mkfs', 'dd if=', 'format', 'fdisk', '>/dev/'],
            4: ['kill -9', 'pkill', 'killall', 'sudo rm', 'chmod 777'],
            3: ['sudo', 'mv', 'cp -r', 'chown', 'chmod'],
            2: ['rm', 'rmdir', 'unzip', 'tar -x']
        }
        
        command_lower = command.lower()
        for level, patterns in dangerous_patterns.items():
            for pattern in patterns:
                if pattern in command_lower:
                    return level
        
        return 1  # Safe by default