---
title: AI Genesis Engine
emoji: 🏆
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 5.35.0
app_file: app.py
pinned: false
short_description: Enhanced Chatbot for Software Engineering
---

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference




🧬 AI Genesis Engine
An Interactive AI Development Environment that Builds, Tests, Deploys, and Refines Software in a Continuous Loop.
![alt text](https://img.shields.io/badge/build-passing-green)
![alt text](https://img.shields.io/badge/License-MIT-yellow.svg)
![alt text](https://img.shields.io/badge/python-3.9+-blue.svg)
The AI Genesis Engine is not just a code generator; it's a self-contained, interactive development environment powered by a multi-agent AI system. It orchestrates a sophisticated workflow that mirrors professional software development, enabling a user to take an idea from a single sentence to a live, deployed web application.
The core philosophy is the "Build, Test, Debug, Refine" loop, where the AI can execute its own code, analyze the output and errors, and iteratively self-correct until the application is functional.
(A conceptual screenshot of the IDE-like layout)
✨ Core Features
🧠 Dual-Model AI Core: Leverages the distinct strengths of the world's leading models:
Google Gemini 1.5 Pro: For high-level reasoning, architectural planning, and multi-file logic structuring.
Meta Code Llama 70B: For expert-level, syntactically precise code generation.
🔁 Self-Correcting Loop: The engine executes the generated code, captures terminal output (including errors), and feeds it back to the AI. The AI can then debug its own SyntaxError, ModuleNotFoundError, or runtime bugs.
🖥️ Integrated Development Environment (IDE) in your Browser:
Live File Tree: See your entire application's file structure dynamically update as the AI works.
Code Editor: View and edit any generated file with full syntax highlighting.
Live Terminal: Watch in real-time as the AI installs dependencies (pip install) and runs your application.
🚀 One-Click Deployment: Once your application is running successfully, a single click uses ngrok to instantly create a secure, public URL, making your app live on the internet for testing and sharing.
💬 Conversational Refinement: After the initial build, engage in a continuous dialogue with the AI. Ask for new features, UI changes, or bug fixes. The AI maintains full context of the codebase and conversation history.
Workflow: Idea to Live App in 4 Steps
The entire user experience is designed to be a seamless progression from concept to reality.
1. Activation & Setup
Provide your API keys for Hugging Face, Google AI, and (optionally) Ngrok. The engine validates them and unlocks the main workspace.
2. The Initial Build
Describe your application in plain English (e.g., "A Flask API for a blog"). Click "Build New App" and watch as the engine executes a 4-phase build process:
Phase 1: Planning (Gemini): The AI creates a detailed JSON architectural plan.
Phase 2: Generation (Code Llama): The AI writes all the code based on the approved plan.
Phase 3: Dependency Installation: The AI runs pip install -r requirements.txt in the live terminal.
Phase 4: Test Run: The AI attempts to run the main application script to check for immediate errors.
3. Interactive Refinement
With the first version built, the refinement loop begins.
Analyze: Review the code in the editor and the output in the terminal.
Instruct: Use the chat to tell the AI what to do next. Examples:
"The app crashed with a KeyError. Please analyze the terminal output and fix the bug."
"Add a new database model for 'Comments' and an endpoint to post them."
Iterate: The AI will modify the files, and you can immediately see the changes and re-test.
4. Live Deployment
Once you're satisfied, click the "Deploy App" button. The engine starts the application server and tunnels it through ngrok, providing you with a public URL.
🛠️ Tech Stack
Backend: Python 3.9+
UI Framework: Gradio
AI Models: Google Gemini 1.5 Pro, Meta Code Llama 70B
API Clients: huggingface_hub, google-generativeai
Deployment: pyngrok
Execution: Python subprocess
🚀 Getting Started
Follow these steps to get the AI Genesis Engine running on your local machine.
Prerequisites
Python 3.9 or higher
Git
Installation
Clone the repository:
Generated bash
git clone https://github.com/your-username/ai-genesis-engine.git
cd ai-genesis-engine
Use code with caution.
Bash
Install the required Python packages:
Generated bash
pip install -r requirements.txt
# Or, if you don't have a requirements.txt file yet:
pip install gradio huggingface_hub google-generativeai pyngrok
Use code with caution.
Bash
API Keys
To use the engine, you need to acquire three API keys:
Hugging Face: A User Access Token with write permissions. Get it from hf.co/settings/tokens.
Google AI Studio (Gemini): An API Key. Get it from aistudio.google.com/app/apikey.
Ngrok (Recommended): An authtoken for stable deployment tunnels. Get it from the ngrok Dashboard.
How to Run
Execute the main script from your terminal:
Generated bash
python genesis_engine.py
Use code with caution.
Bash
Open the application:
The terminal will provide a local URL (e.g., http://127.0.0.1:7860). Open this link in your web browser.
Activate the Engine:
Enter your three API keys in the sidebar and click "Activate Engine". The workspace will unlock upon successful validation. You are now ready to build.
🗺️ Roadmap & Future Vision
The AI Genesis Engine is a foundation. Future development could include:
Fully Automated Debugging Loop: The AI automatically re-runs tests after a fix without user prompting.
Test-Driven Development (TDD): Instruct the AI to write pytest files first, then write the application code to make the tests pass.
Frontend-Backend Symbiosis: A more sophisticated planner that can generate a React/Vue frontend that correctly communicates with a generated Python/Node.js backend.
Dockerization: An action to automatically generate a Dockerfile and docker-compose.yml for the project.
Persistent State: Save and load entire project states, allowing you to stop and resume complex development sessions.
🤝 Contributing
Contributions are welcome! If you have ideas for new features, bug fixes, or improvements, please open an issue to discuss it first.
📄 License
This project is licensed under the MIT License. See the LICENSE file for details.