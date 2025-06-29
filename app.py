import gradio as gr
import openai
import os
import json
import subprocess
import time
import threading
from queue import Queue
import shutil
import zipfile
from io import BytesIO

# --- CONFIGURATION & STATE ---
PROJECT_DIR = "hyperion_project"
openai_client = None
app_process = None # Global handle for our running server process

# --- THE HYPERION TOOLSET ---
def list_files(path: str = ".") -> str:
    """Lists all files and directories in a given path within the project."""
    full_path = os.path.join(PROJECT_DIR, path)
    if not os.path.isdir(full_path):
        os.makedirs(full_path, exist_ok=True)
    try:
        files = os.listdir(full_path)
        return "\n".join(files) if files else "(empty directory)"
    except Exception as e: return f"Error listing files: {e}"

def write_file(path: str, content: str) -> str:
    """Writes or overwrites a file with the given content."""
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f: f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}."
    except Exception as e: return f"Error writing to file: {e}"

def run_shell_command(command: str) -> str:
    """Executes a short-lived shell command (like ls, pip, etc.) and returns its output."""
    try:
        result = subprocess.run(command, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=120)
        return f"COMMAND:\n$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e: return f"Error executing shell command: {e}"

def launch_server(command: str) -> str:
    """Launches a long-running server process in the background (e.g., 'python app.py')."""
    global app_process
    if app_process:
        app_process.kill() # Ensure any old server is stopped first
    try:
        app_process = subprocess.Popen(
            command, shell=True, cwd=PROJECT_DIR, 
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
            text=True, bufsize=1
        )
        return f"Successfully launched server process with command: '{command}'. It is now running in the background."
    except Exception as e:
        return f"Error launching server: {e}"

def finish_mission(reason: str) -> str:
    """Declares the mission complete."""
    return f"Mission finished. Reason: {reason}"

# --- UTILITIES ---
def initialize_clients():
    global openai_client
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return "❌ Missing Secret: `OPENAI_API_KEY`", False
    try:
        openai_client = openai.OpenAI(api_key=openai_key)
        openai_client.models.list()
        return "✅ Engine Online. Hyperion Framework is ready.", True
    except Exception as e: return f"❌ API Initialization Failed: {e}", False

def stream_process_output(process, queue):
    for line in iter(process.stdout.readline, ''):
        queue.put(line)
    process.stdout.close()

# --- THE HYPERION ORCHESTRATOR ---
def run_hyperion_mission(initial_prompt, max_steps=15):
    global app_process
    
    mission_log = "Mission Log: [START]\n"
    # HYPERION UPGRADE: Yield an update for the download button at the start
    yield mission_log, gr.update(choices=[]), "", gr.update(visible=False, value=None)

    if os.path.exists(PROJECT_DIR):
        shutil.rmtree(PROJECT_DIR)
    os.makedirs(PROJECT_DIR, exist_ok=True)
    
    conversation = [
        {"role": "system", "content": "You are an autonomous AI developer... (same prompt as Ascension)"},
        {"role": "user", "content": f"Here is my objective: {initial_prompt}"}
    ]
    
    tools = [
        {"type": "function", "function": {"name": "list_files", "description": "Lists files in a directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
        {"type": "function", "function": {"name": "write_file", "description": "Writes content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
        {"type": "function", "function": {"name": "run_shell_command", "description": "Executes a short-lived command that finishes.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "launch_server", "description": "Launches a long-running server process in the background.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "finish_mission", "description": "Call this when the objective is complete.", "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}}
    ]
    
    for i in range(max_steps):
        mission_log += f"\n--- Step {i+1}/{max_steps} ---\nAI is thinking...\n"
        yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR) or ["(empty)"]), "", None
        
        response = openai_client.chat.completions.create(model="gpt-4o", messages=conversation, tools=tools, tool_choice="auto")
        response_message = response.choices[0].message
        conversation.append(response_message)
        
        if not response_message.tool_calls: break

        tool_responses = []
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            mission_log += f"Action: Calling `{function_name}` with args: {function_args}\n"
            yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR) or ["(empty)"]), "", None
            
            tool_function = globals()[function_name]
            result = tool_function(**tool_args)
            mission_log += f"Result: {result}\n"
            
            if function_name == "finish_mission":
                mission_log += "--- MISSION COMPLETE ---"
                # Prepare and yield the download link
                zip_path = os.path.join(PROJECT_DIR, "ai_generated_app.zip")
                with zipfile.ZipFile(zip_path, 'w') as zf:
                    for root, _, files in os.walk(PROJECT_DIR):
                        for file in files:
                            if file != os.path.basename(zip_path):
                                zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), PROJECT_DIR))
                
                terminal_text = ""
                if app_process:
                    output_queue = Queue()
                    thread = threading.Thread(target=stream_process_output, args=(app_process, output_queue))
                    thread.daemon = True
                    thread.start()
                    time.sleep(2)
                    while not output_queue.empty(): terminal_text += output_queue.get()
                
                yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR) or ["(empty)"]), terminal_text, gr.update(visible=True, value=zip_path)
                return

            tool_responses.append({"tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": result})
        
        conversation.extend(tool_responses)
        yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR) or ["(empty)"]), "", None

    mission_log += "\n--- Max steps reached. Mission concluding. ---"
    yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR) or ["(empty)"]), "", None

# --- GRADIO UI (with Download Button) ---
with gr.Blocks(theme=gr.themes.Soft(primary_hue="blue"), title="Hyperion Framework") as demo:
    gr.Markdown("# ✨ Hyperion: The Autonomous AI Developer")
    status_bar = gr.Textbox("System Offline. Click 'Activate Engine' to begin.", label="System Status", interactive=False)
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ Controls")
            activate_btn = gr.Button("Activate Engine")
            gr.Markdown("### 🌳 Project Files")
            file_tree = gr.Radio(label="File System", interactive=True, value=None)
            # HYPERION UPGRADE: Added the download button
            download_zip_btn = gr.DownloadButton(label="Download Project as .zip", visible=False)

        with gr.Column(scale=3):
            gr.Markdown("### 📝 Mission Control")
            mission_prompt = gr.Textbox(label="High-Level Objective", placeholder="Build a simple Flask app that returns the current time as a JSON object.")
            launch_btn = gr.Button("🚀 Launch Mission", variant="primary", interactive=False)
            gr.Markdown("### 📜 Mission Log & Live Terminal")
            mission_log_output = gr.Textbox(label="Live Log", lines=20, interactive=False, autoscroll=True)
            live_terminal = gr.Textbox(label="Live App Terminal", lines=5, interactive=False, autoscroll=True)

    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    
    activate_btn.click(handle_activation, [], [status_bar, launch_btn])
    # HYPERION UPGRADE: Added download button to the outputs list
    launch_btn.click(fn=run_hyperion_mission, inputs=[mission_prompt], outputs=[mission_log_output, file_tree, live_terminal, download_zip_btn])

if __name__ == "__main__":
    demo.launch(debug=True)