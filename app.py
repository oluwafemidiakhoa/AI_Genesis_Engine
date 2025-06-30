import gradio as gr
import openai
import os
import json
import subprocess
import time
import shutil
import threading
from queue import Queue
import zipfile

# --- CONFIGURATION & STATE ---
PROJECT_DIR = "boilerplate_forge"
openai_client = None
app_process = None

# --- TOOLSET (Finalized) ---
def write_file(path: str, content: str) -> str:
    """Writes content to a file, creating directories as needed."""
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f: f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}."
    except Exception as e: return f"Error writing to file: {e}"

def run_shell_command(command: str) -> str:
    """Executes a short-lived shell command."""
    try:
        result = subprocess.run(command, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=300) # Increased timeout for installs
        return f"COMMAND:\n$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e: return f"Error executing shell command: {e}"

def launch_server(command: str) -> str:
    """Launches a long-running server process."""
    global app_process
    if app_process: app_process.kill()
    try:
        app_process = subprocess.Popen(
            command, shell=True, cwd=PROJECT_DIR, 
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
            text=True, bufsize=1, universal_newlines=True
        )
        return f"Successfully launched background process with command: '{command}'."
    except Exception as e: return f"Error launching server: {e}"

def finish_mission(reason: str) -> str:
    """Call this when the user's objective is complete."""
    return f"Mission finished. Reason: {reason}"

# --- INITIALIZATION & UTILITIES ---
def initialize_clients():
    global openai_client
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key: return "❌ Missing Secret: `OPENAI_API_KEY`", False
    try:
        openai_client = openai.OpenAI(api_key=openai_key)
        openai_client.models.list()
        return "✅ Forge is hot. Select a boilerplate to begin.", True
    except Exception as e: return f"❌ API Initialization Failed: {e}", False

def stream_process_output(process, queue):
    for line in iter(process.stdout.readline, ''): queue.put(line)
    process.stdout.close()

# --- THE "GOLDEN PATH" PROMPTS ---
BOILERPLATE_PROMPTS = {
    "SaaS Boilerplate (Flask + Stripe)": (
        "You are an expert in building Software-as-a-Service applications. "
        "Your task is to build a robust boilerplate using Python with Flask, a PostgreSQL database, Stripe for payments, and basic user authentication. "
        "The workflow is: "
        "1. Create the full project structure including directories for models, views, and controllers (MVC pattern). "
        "2. Write the Python code for `app.py`, including routes for user signup, login, logout, and a placeholder dashboard page. "
        "3. Write the user model with fields for email and password hashing. "
        "4. Create HTML templates using Tailwind CSS for the layout, login, signup, and dashboard pages. The design should be clean and professional. "
        "5. Write placeholder code for Stripe checkout integration. "
        "6. Create a `requirements.txt` with all necessary libraries (Flask, SQLAlchemy, psycopg2-binary, Flask-Login, stripe, etc.). "
        "7. Create a `Dockerfile` and `docker-compose.yml` to containerize the application for easy deployment. "
        "8. Finish the mission with a summary of the created architecture."
    ),
    "AI-Powered API (FastAPI + VectorDB)": (
        "You are an expert in building AI-native APIs. "
        "Your task is to build a boilerplate for an AI service using FastAPI for high performance and connecting to a vector database like Pinecone or Weaviate. "
        "The workflow is: "
        "1. Create the project structure. "
        "2. Write the main `main.py` file with FastAPI. Create an API endpoint `/embed` that takes text, and a placeholder endpoint `/query` that takes a query and is meant to find similar items. "
        "3. Write a service module (`vector_db_service.py`) that contains placeholder functions to connect to, upsert data into, and query a vector database. Include comments explaining where to put the API keys. "
        "4. Write a `requirements.txt` file including `fastapi`, `uvicorn`, and a relevant vector DB client library (e.g., `pinecone-client`). "
        "5. Create a `Dockerfile` for the FastAPI application. "
        "6. Finish the mission explaining how to run the service."
    ),
    "Headless CMS Blog (Next.js + Strapi)": (
        "You are an expert in building modern web frontends with headless CMS backends. "
        "Your task is to build the frontend boilerplate for a blog using Next.js and Tailwind CSS, designed to fetch data from a Strapi backend. "
        "The workflow is: "
        "1. Run the shell command `npx create-next-app@latest . -y --ts --tailwind --eslint --app`. "
        "2. Create pages for the blog index (`/pages/index.js`) and individual posts (`/pages/blog/[slug].js`). "
        "3. In the index page, write placeholder code to fetch a list of blog posts from a Strapi API endpoint (e.g., `http://localhost:1337/api/posts`). "
        "4. In the slug page, write placeholder code to fetch a single post by its slug. "
        "5. Create simple, clean UI components for the post list and post view using Tailwind CSS. "
        "6. Finish the mission explaining that the user needs to set up their own Strapi backend."
    )
}

# --- THE FORGE ORCHESTRATOR ---
def run_forge_mission(boilerplate_choice, max_steps=40):
    global app_process
    
    mission_log = "[FORGE LOG: START]\n"
    yield mission_log, [], "", gr.update(visible=False, value=None)

    if os.path.exists(PROJECT_DIR): shutil.rmtree(PROJECT_DIR)
    os.makedirs(PROJECT_DIR, exist_ok=True)
    
    initial_prompt = BOILERPLATE_PROMPTS.get(boilerplate_choice)
    if not initial_prompt:
        mission_log += "Error: Invalid boilerplate choice."
        yield mission_log, [], "", None
        return
        
    conversation = [
        {"role": "system", "content": "You are The Forge, an elite autonomous AI software developer. Your sole purpose is to execute the user's high-level objective by generating a complete, production-ready boilerplate. Think step-by-step and use your tools to build the entire application as specified."},
        {"role": "user", "content": f"My objective is to build the '{boilerplate_choice}'. Here is the full specification and plan:\n\n{initial_prompt}"}
    ]
    
    tools = [
        {"type": "function", "function": {"name": "write_file", "description": "Writes content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
        {"type": "function", "function": {"name": "run_shell_command", "description": "Executes a short-lived command that finishes.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "launch_server", "description": "Launches a long-running server process in the background.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "finish_mission", "description": "Call this when the objective is fully complete.", "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}}
    ]
    
    for i in range(max_steps):
        # ... (Execution loop is the same as the final Genesis version) ...
        mission_log += f"\n--- Step {i+1}/{max_steps} ---\nForge is working...\n"
        current_file_list = [f for f in os.listdir(PROJECT_DIR)] if os.path.isdir(PROJECT_DIR) else []
        yield mission_log, current_file_list, "", None
        
        try:
            response = openai_client.chat.completions.create(model="gpt-4o", messages=conversation, tools=tools, tool_choice="auto")
            response_message = response.choices[0].message
            conversation.append(response_message)
            
            if not response_message.tool_calls:
                mission_log += "Agent chose not to act. Concluding mission.\n"
                break

            tool_responses = []
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                mission_log += f"Action: Calling `{function_name}` with args: {function_args}\n"
                
                tool_function = globals()[function_name]
                result = tool_function(**function_args)
                mission_log += f"Result:\n---\n{result}\n---\n"
                
                if function_name == "finish_mission":
                    mission_log += "--- FORGE COMPLETE ---"
                    zip_path = os.path.join(PROJECT_DIR, f"{boilerplate_choice.split(' ')[0].lower()}_boilerplate.zip")
                    with zipfile.ZipFile(zip_path, 'w') as zf:
                        for root, _, files in os.walk(PROJECT_DIR):
                            for file in files:
                                if file != os.path.basename(zip_path): zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), PROJECT_DIR))
                    
                    terminal_text = ""
                    if app_process:
                        output_queue = Queue()
                        thread = threading.Thread(target=stream_process_output, args=(app_process, output_queue)); thread.daemon = True; thread.start()
                        time.sleep(3)
                        while not output_queue.empty(): terminal_text += output_queue.get()
                    
                    yield mission_log, current_file_list, terminal_text, gr.update(visible=True, value=zip_path)
                    return

                tool_responses.append({"tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": result})
            
            conversation.extend(tool_responses)
        except Exception as e:
            mission_log += f"Engine: [FATAL ERROR] An unexpected error occurred: {e}\nAborting mission."
            yield mission_log, current_file_list, "", None
            return

    mission_log += "\n--- Max steps reached. Mission concluding. ---"
    yield mission_log, current_file_list, "", None

# --- GRADIO UI ---
with gr.Blocks(theme=gr.themes.Soft(primary_hue="blue", secondary_hue="sky"), title="The Boilerplate Forge") as demo:
    gr.Markdown("# 🔥 The Boilerplate Forge: Your AI-Powered SaaS Starter")
    status_bar = gr.Textbox("System Offline. Click 'Activate Engine' to begin.", label="System Status", interactive=False)
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ Controls")
            activate_btn = gr.Button("Activate Engine")
            gr.Markdown("### 🌳 Project Files")
            file_tree = gr.CheckboxGroup(label="Generated Files", interactive=False)
            download_zip_btn = gr.DownloadButton(label="Download Boilerplate as .zip", visible=False)
        
        with gr.Column(scale=3):
            gr.Markdown("### 🚀 Select a Boilerplate to Forge")
            boilerplate_selector = gr.Radio(
                label="Choose your stack:",
                choices=list(BOILERPLATE_PROMPTS.keys()),
                value="SaaS Boilerplate (Flask + Stripe)"
            )
            launch_btn = gr.Button("Forge Boilerplate", variant="primary", interactive=False)
            gr.Markdown("### 📜 Forge Log & Live Terminal")
            mission_log_output = gr.Textbox(label="Live Log", lines=20, interactive=False, autoscroll=True)
            live_terminal = gr.Textbox(label="Live App Terminal", lines=5, interactive=False, autoscroll=True)

    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    
    activate_btn.click(handle_activation, [], [status_bar, launch_btn])
    launch_btn.click(fn=run_forge_mission, inputs=[boilerplate_selector], outputs=[mission_log_output, file_tree, live_terminal, download_zip_btn])

if __name__ == "__main__":
    demo.launch(debug=True)