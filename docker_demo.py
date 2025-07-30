#!/usr/bin/env python3
"""
Example script demonstrating Scriptoria Agent usage in Docker.
This script can be used to test the FileManager functionality.
"""

import pathlib
import logging
from scriptoria.file_manager import FileManager

def setup_logging():
    """Setup basic logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def demo_file_operations(workspace_path="/app/workspace"):
    """Demonstrate basic file operations."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Create workspace if it doesn't exist
    workspace = pathlib.Path(workspace_path)
    workspace.mkdir(exist_ok=True)
    
    # Initialize FileManager
    fm = FileManager(workspace)
    
    logger.info("=== Scriptoria Agent Docker Demo ===")
    
    # Test 1: Create a file
    test_content = "Hello from Scriptoria Agent running in Docker!\n"
    fm.write("demo.txt", test_content)
    logger.info("✅ Created demo.txt")
    
    # Test 2: Read the file
    content = fm.read("demo.txt")
    logger.info(f"✅ Read content: {content.strip()}")
    
    # Test 3: Create directory structure
    fm.ensure_dir("projects/test-project")
    fm.write("projects/test-project/README.md", "# Test Project\n\nThis is a test project.")
    logger.info("✅ Created directory structure with README")
    
    # Test 4: List directory contents
    files = fm.list_dir(".")
    logger.info(f"✅ Workspace contents: {[str(f) for f in files]}")
    
    # Test 5: Append to file
    fm.append("demo.txt", "Appended line from Docker container!\n")
    updated_content = fm.read("demo.txt")
    logger.info(f"✅ Updated content: {updated_content}")
    
    # Test 6: Copy file
    fm.copy("demo.txt", "demo_copy.txt")
    logger.info("✅ Created copy of demo.txt")
    
    logger.info("=== Demo completed successfully! ===")

if __name__ == "__main__":
    demo_file_operations()
