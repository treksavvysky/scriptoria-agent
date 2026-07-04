> [!IMPORTANT]
> **SUPERSEDED (2026-07-04).** This IntelliSwarm-era file-management agent is retired. The Scriptoria name and librarian role live on in the **cortex-os** repo ("The Library"), where Scriptoria is the record librarian (curation, retrieval, digests) over the System Memory Index. This repo is archived for lineage; its code is not the successor.

# Scriptoria Agent

**Scriptoria** is a dedicated AI agent within the *IntelliSwarm* ecosystem, responsible for file management, code organization, and structured project documentation. Scriptoria acts as a librarian, archivist, and scribe—ensuring clarity, consistency, and order within a collaborative multi-agent system.

## 📌 Purpose

Scriptoria was built to handle the following responsibilities:

* Create, read, update, and delete (CRUD) files across agent-managed projects.
* Maintain structured project directories.
* Record, update, and version documentation (e.g., README.md, changelogs, agent manifests).
* Facilitate conversations between agents by managing log files and summaries.

## 🧠 Role in IntelliSwarm

Scriptoria serves as:

* **File Management Assistant**: Maintains all files relevant to active agents, development projects, and experiments.
* **Communication Hub**: Stores and serves messages, logs, and persistent memory files for inter-agent dialogue.
* **Documentation Manager**: Automatically generates or updates markdown files for codebases, APIs, and agent behavior.

## 🚀 Features

* Python-based implementation, easily extended with functions exposed to GPT agents.
* Integration-ready for OpenAI API function calling.
* Simple and secure file system operations.
* Intelligent pattern-based updates (e.g., regex-driven modifications).

## 🏗️ Directory Structure

```bash
scriptoria_agent/
├── __init__.py
├── file_manager.py        # Core logic for CRUD and directory operations
├── docgen.py              # Markdown file generation and management
├── message_store.py       # Persistent storage for inter-agent communication
├── utils.py               # Utilities for path handling, encoding, formatting
└── agent_manifest.json    # Metadata describing Scriptoria's functions and state
```

## 📦 Installation

```bash
git clone https://github.com/YOUR_USERNAME/scriptoria-agent.git
cd scriptoria-agent
pip install -e .
```

## 🧪 Usage

Scriptoria can be invoked programmatically via function calls or CLI commands:

```python
from scriptoria_agent.file_manager import write_file
write_file("notes/todo.md", "- [ ] Add agent function support")
```

### API Endpoints

The agent also exposes a minimal HTTP API for file operations:

| Method | Endpoint    | Description                     |
| ------ | ----------- | ------------------------------- |
| POST   | `/move-file` | Move or rename a file or directory within the workspace |

## 🧩 Integrations

* Works seamlessly with **FionnAI**, **Task Master**, and other IntelliSwarm agents.
* Can serve function calls through OpenAI’s API ecosystem using function specs.
* Planned integration with sandboxed execution environments for secure file ops.

## 🛡️ Security

* All file operations are sandbox-aware.
* Future features include scoped access control per agent.

## 📖 License

MIT License

## 👨‍💻 Author

George Loudon — [treksavvysky](https://github.com/treksavvysky)

---

> *"Every idea deserves to be written well. Scriptoria ensures it is."*