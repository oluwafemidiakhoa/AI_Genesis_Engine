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
PROJECT_DIR = "foundry_project"
openai_client = None
app_process = None

# --- TOOLSET (Finalized and Stable) ---
def list_files(path: str = ".") -> str:
    full_path = os.path.join(PROJECT_DIR, path)
    if not os.path.isdir(full_path):
        return f"Error: '{path}' is not a directory."
    try:
        files = os.listdir(full_path)
        return "\n".join(files) if files else "(empty directory)"
    except Exception as e: return f"Error listing files: {e}"

def write_file(path: str, content: str) -> str:
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f: f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}."
    except Exception as e: return f"Error writing to file: {e}"

def run_shell_command(command: str) -> str:
    try:
        result = subprocess.run(command, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=180)
        return f"COMMAND:\n$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e: return f"Error executing shell command: {e}"

def launch_server(command: str) -> str:
    global app_process
    if app_process: app_process.kill()
    try:
        app_process = subprocess.Popen(
            command, shell=True, cwd=PROJECT_DIR, 
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
            text=True, bufsize=1, universal_newlines=True
        )
        return f"Successfully launched server process with command: '{command}'."
    except Exception as e: return f"Error launching server: {e}"

def finish_mission(reason: str) -> str:
    return f"Mission finished. Reason: {reason}"

# --- INITIALIZATION & UTILITIES ---
def initialize_clients():
    global openai_client
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key: return "❌ Missing Secret: `OPENAI_API_KEY`", False
    try:
        openai_client = openai.OpenAI(api_key=openai_key)
        openai_client.models.list()
        return "✅ Foundry is Online. Configure your boilerplate below.", True
    except Exception as e: return f"❌ API Initialization Failed: {e}", False

def stream_process_output(process, queue):
    for line in iter(process.stdout.readline, ''): queue.put(line)
    process.stdout.close()

# --- THE PROMPT ENGINEER ---
def assemble_prompt(backend, database, features):
    """Assembles a perfect, unambiguous prompt from user selections."""
    
    # Base Instruction
    prompt = f"You will generate a production-ready boilerplate for a web application. The core backend framework will be {backend}."

    # Database Integration
    if database == "PostgreSQL (SQLAlchemy)":
        prompt += "\n- Integrate PostgreSQL as the database using the SQLAlchemy ORM. Create a basic user model (id, email, hashed_password). The database connection URL must be configurable via an environment variable `DATABASE_URL`."
    elif database == "SQLite (local)":
        prompt += "\n- Use a local SQLite database for simplicity. Configure it within the main application file."
    
    # Feature Integration
    if "User Authentication (Email/Password)" in features:
        prompt += "\n- Implement a complete user authentication system. It must include API endpoints or routes for user registration, login (issuing a JWT or session cookie), logout, and a protected route that requires authentication."
    
    if "Stripe Payments (Subscription Boilerplate)" in features:
        prompt += "\n- Integrate the Stripe API for subscription payments. Include a basic pricing page, a checkout session creation endpoint, and a webhook handler to listen for successful payment events. Stripe API keys must be configurable via environment variables."
        
    if "React (Vite) Frontend" in features:
         prompt += "\n- Create a separate `frontend` directory. Inside, scaffold a basic React application using Vite. The React app should include a sample component that makes a `fetch` call to the backend API."
    
    if "Dockerfile for Deployment" in features:
        prompt += "\n- Generate a multi-stage `Dockerfile` that creates a production-ready container for the application."

    prompt += "\n\nYour task is to think step-by-step and use the available tools to create all necessary files and install all dependencies to make this boilerplate fully functional. Begin by creating the project file structure."
    return prompt

# --- THE FOUNDRY ORCHESTRATOR ---
def run_foundry_mission(backend, database, features, max_steps=40):
    global app_process
    
    mission_log = "[MISSION LOG: START]\n"
    yield mission_log, [], "", gr.update(visible=False, value=None)

    if os.path.exists(PROJECT_DIR): shutil.rmtree(PROJECT_DIR)
    os.makedirs(PROJECT_DIR, exist_ok=True)
    
    # 1. Assemble the perfect prompt
    initial_prompt = assemble_prompt(backend, database, features)
    mission_log += f"Foundry AI: Assembling mission parameters...\n---\n{initial_prompt}\n---\n"
    
    # 2. Run the Singularity Agent with the assembled prompt
    conversation = [
        {"role": "system", "content": "You are an elite autonomous AI software developer. Your goal is to achieve the user's objective by executing a sequence of tool calls. Think step-by-step. To run a web server, you MUST use the `launch_server` tool. When the entire boilerplate is built and runnable, call `finish_mission`."},
        {"role": "user", "content": f"My objective is: {initial_prompt}"}
    ]
    
    tools = [
        {"type": "function", "function": {"name": "list_files", "description": "Lists files in a directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
        {"type": "function", "function": {"name": "write_file", "description": "Writes content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
        {"type": "function", "function": {"name": "run_shell_command", "description": "Executes a short-lived command that finishes.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "launch_server", "description": "Launches a long-running server process in the background.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "finish_mission", "description": "Call this when the objective is complete.", "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}}
    ]
    
    for i in range(max_steps):
        mission_log += f"\n--- Step {i+1}/{max_steps} ---\nAgent is thinking...\n"
        current_file_list = [f for f in os.listdir(PROJECT_DIR)] if os.path.isdir(PROJECT_DIR) else []
        yield mission_log, current_file_list, "", None
        
        try:
            response = openai_client.chat.completions.create(model="gpt-4o", messages=conversation, tools=tools, tool_choice="auto")
            response_message = response.choices[0].message
            conversation.append(response_message)
            
            if not response_message.tool_calls: break

            tool_responses = []
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                mission_log += f"Action: Calling `{function_name}` with args: {function_args}\n"
                
                tool_function = globals()[function_name]
                result = tool_function(**function_args)
                mission_log += f"Result:\n---\n{result}\n---\n"
                
                if function_name == "finish_mission":
                    mission_log += "--- MISSION COMPLETE ---"
                    zip_path = os.path.join(PROJECT_DIR, "foundry_app.zip")
                    with zipfile.ZipFile(zip_path, 'w') as zf:
                        for root, _, files in os.walk(PROJECT_DIR):
                            for file in files:
                                if file != os.path.basename(zip_path):
                                    zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), PROJECT_DIR))
                    
                    terminal_text = ""
                    if app_process:
                        output_queue = Queue()
                        thread = threading.Thread(target=stream_process_output, args=(app_process, output_queue))
                        thread.daemon = True; thread.start()
                        time.sleep(2)
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
with gr.Blocks(theme=gr.themes.Soft(primary_hue="emerald", secondary_hue="green"), title="The Foundry") as demo:
    gr.Markdown("# 🏭 The Foundry: Your AI Boilerplate Factory")
    status_bar = gr.Textbox("System Offline. Click 'Activate Engine' to begin.", label="System Status", interactive=False)
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ Configure Your Boilerplate")
            
            with gr.Accordion("Backend Settings", open=True):
                backend_choice = gr.Radio(["Flask", "FastAPI"], label="Backend Framework", value="Flask")
                database_choice = gr.Radio(["PostgreSQL (SQLAlchemy)", "SQLite (local)", "None"], label="Database", value="SQLite (local)")
            
            with gr.Accordion("Core Features", open=True):
                features_choice = gr.CheckboxGroup([
                    "User Authentication (Email/Password)",
                    "Stripe Payments (Subscription Boilerplate)",
                ], label="Add Features")
            
            with gr.Accordion("Frontend & Deployment", open=False):
                frontend_choice = gr.CheckboxGroup([
                    "React (Vite) Frontend",
                    "Dockerfile for Deployment"
                ], label="Add-ons")
            
            launch_btn = gr.Button("🚀 Forge Boilerplate", variant="primary", interactive=False)
            download_zip_btn = gr.DownloadButton(label="Download Boilerplate as .zip", visible=False)

        with gr.Column(scale=2):
            gr.Markdown("### 📜 Foundry Log")
            mission_log_output = gr.Textbox(label="Live Log", lines=25, interactive=False, autoscroll=True)
            live_terminal = gr.Textbox(label="Live App Terminal", lines=5, interactive=False, autoscroll=True)

    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    
    activate_btn = gr.Button("Activate Engine") # This button is now separate
    demo.load(handle_activation, [], [status_bar, launch_btn]) # Activate on page load

    launch_btn.click(
        fn=run_foundry_mission, 
        inputs=[backend_choice, database_choice, features_choice], # The prompt is now assembled from these
        outputs=[mission_log_output, gr.Textbox(visible=False), live_terminal, download_zip_btn] # Hide file_tree for simplicity
    )

if __name__ == "__main__":
    demo.launch(debug=True)