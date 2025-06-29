import gradio as gr
import openai
import google.generativeai as genai
import os
import json
import subprocess
import time
import shutil
import re
import threading
from queue import Queue
import zipfile

# --- CONFIGURATION & STATE ---
PROJECT_DIR = "pantheon_project"
openai_client, gemini_model = None, None
app_process = None

# --- THE PANTHEON TOOLSET ---
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
    """Executes a short-lived shell command and returns its output."""
    try:
        result = subprocess.run(command, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=120)
        return f"COMMAND:\n$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e: return f"Error executing shell command: {e}"

def launch_server(command: str) -> str:
    """Launches a long-running server process in the background."""
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
    """Call this when the user's objective is complete."""
    return f"Mission finished. Reason: {reason}"

# --- INITIALIZATION ---
def initialize_clients():
    global openai_client, gemini_model
    openai_key = os.getenv("OPENAI_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    if not openai_key or not google_key:
        return "❌ Missing Secrets: Please set `OPENAI_API_KEY` and `GOOGLE_API_KEY` in repository secrets.", False
    try:
        openai_client = openai.OpenAI(api_key=openai_key)
        genai.configure(api_key=google_key)
        gemini_model = genai.GenerativeModel("gemini-1.5-pro-latest")
        openai_client.models.list()
        gemini_model.generate_content("ping")
        return "✅ All engines online. The Pantheon Framework is ready.", True
    except Exception as e: return f"❌ API Initialization Failed: {e}", False

# --- UTILITIES ---
def stream_process_output(process, queue):
    for line in iter(process.stdout.readline, ''): queue.put(line)
    process.stdout.close()

# --- THE MASTER CRAFTSMAN (INNER LOOP) ---
def execute_step(step_instruction: str, mission_log: str):
    mission_log += f"Master Craftsman (GPT-4o): Starting task: '{step_instruction}'\n"
    
    conversation = [
        {"role": "system", "content": "You are a Master Craftsman, an expert AI developer. Complete the user's high-level instruction by calling a sequence of functions. Call multiple tools in one turn if needed. When the instruction is fully complete, you MUST call `step_complete`."},
        {"role": "user", "content": step_instruction}
    ]
    
    tools = [
        {"type": "function", "function": {"name": "list_files", "description": "Lists files in a directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
        {"type": "function", "function": {"name": "write_file", "description": "Writes content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
        {"type": "function", "function": {"name": "run_shell_command", "description": "Executes a short-lived command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "launch_server", "description": "Launches a long-running server process.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "step_complete", "description": "Call this when the current high-level step is finished.", "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}}
    ]
    
    for _ in range(10): # Max 10 turns per high-level step
        response = openai_client.chat.completions.create(model="gpt-4o", messages=conversation, tools=tools, tool_choice="auto")
        response_message = response.choices[0].message
        conversation.append(response_message)
        
        if not response_message.tool_calls:
            mission_log += "Craftsman: Decided to end step without calling `step_complete`.\n"
            return mission_log, False

        tool_responses = []
        for tool_call in response_message.tool_calls:
            function_name, function_args = tool_call.function.name, json.loads(tool_call.function.arguments)
            mission_log += f"Craftsman: Calling tool `{function_name}` with args: {function_args}\n"
            
            if function_name == "step_complete":
                mission_log += f"Craftsman: Step finished. Reason: {function_args.get('reason')}\n"
                return mission_log, True
            
            tool_function = globals()[function_name]
            result = tool_function(**function_args)
            mission_log += f"Tool Result: {result}\n"
            tool_responses.append({"tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": result})
        
        conversation.extend(tool_responses)

    mission_log += "Craftsman: Max tool calls reached for this step. Moving on.\n"
    return mission_log, False

# --- THE PANTHEON ORCHESTRATOR ---
def run_pantheon_mission(initial_prompt):
    mission_log = "Mission Log: [START]\n"
    yield mission_log, gr.update(choices=[]), "", gr.update(visible=False, value=None)

    if os.path.exists(PROJECT_DIR): shutil.rmtree(PROJECT_DIR)
    os.makedirs(PROJECT_DIR, exist_ok=True)
    
    # Phase 1: Architect (Gemini) creates the natural language plan
    mission_log += "Architect (Gemini): Creating high-level project plan...\n"
    yield mission_log, None, None, None
    
    architect_prompt = "You are The Architect. Create a high-level, logical, step-by-step plan in natural language to achieve the user's goal. Do not write code. Just provide a numbered list of instructions for an expert developer to follow."
    response = gemini_model.generate_content(f"{architect_prompt}\n\nUser Goal: {initial_prompt}")
    plan = [step.strip() for step in response.text.split('\n') if step.strip() and re.match(r'^\d+\.', step.strip())]
    
    if not plan:
        mission_log += "Architect: [FATAL ERROR] Failed to create a valid plan.\n"
        yield mission_log, None, None, None
        return
        
    mission_log += f"Architect: Plan generated with {len(plan)} steps.\n"
    yield mission_log, None, None, None

    # Phase 2: Orchestrator executes the plan step-by-step
    for i, step_instruction in enumerate(plan):
        mission_log += f"\n--- Executing Plan Step {i+1}/{len(plan)} ---\n"
        yield mission_log, os.listdir(PROJECT_DIR) or ["(empty)"], "", None
        
        mission_log, success = execute_step(step_instruction, mission_log)
        
        if not success:
            mission_log += f"Engine: [MISSION FAILED] The Master Craftsman could not complete step {i+1}. Aborting.\n"
            yield mission_log, os.listdir(PROJECT_DIR) or ["(empty)"], "", None
            return
            
        yield mission_log, os.listdir(PROJECT_DIR) or ["(empty)"], "", None

    mission_log += "\n--- MISSION COMPLETE ---"
    
    zip_path = os.path.join(PROJECT_DIR, "pantheon_app.zip")
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for root, _, files in os.walk(PROJECT_DIR):
            for file in files:
                if file != os.path.basename(zip_path):
                    zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), PROJECT_DIR))
    
    terminal_text = ""
    if app_process:
        mission_log += "\n--- Application is Running Live ---\n"
        output_queue = Queue()
        thread = threading.Thread(target=stream_process_output, args=(app_process, output_queue))
        thread.daemon = True
        thread.start()
        time.sleep(3)
        while not output_queue.empty(): terminal_text += output_queue.get()
    
    yield mission_log, os.listdir(PROJECT_DIR) or ["(empty)"], terminal_text, gr.update(visible=True, value=zip_path)


# --- GRADIO UI ---
with gr.Blocks(theme=gr.themes.Soft(primary_hue="blue", secondary_hue="sky"), title="Pantheon Framework") as demo:
    gr.Markdown("# 🏛️ Pantheon: The Autonomous AI Developer")
    status_bar = gr.Textbox("System Offline. Click 'Activate Engines' to begin.", label="System Status", interactive=False)
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ Controls")
            activate_btn = gr.Button("Activate Engines")
            gr.Markdown("### 🌳 Project Files")
            file_tree = gr.Radio(label="File System", interactive=True, value=None)
            download_zip_btn = gr.DownloadButton(label="Download Project as .zip", visible=False)
        
        with gr.Column(scale=3):
            gr.Markdown("### 📝 Mission Control")
            mission_prompt = gr.Textbox(label="High-Level Objective", placeholder="Build a beautiful, modern login page with a glassmorphism effect and a Flask backend.", lines=3)
            launch_btn = gr.Button("🚀 Launch Mission", variant="primary", interactive=False)
            gr.Markdown("### 📜 Mission Log & Live Terminal")
            mission_log_output = gr.Textbox(label="Live Log", lines=20, interactive=False, autoscroll=True)
            live_terminal = gr.Textbox(label="Live App Terminal", lines=5, interactive=False, autoscroll=True)

    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    
    activate_btn.click(handle_activation, [], [status_bar, launch_btn])
    launch_btn.click(fn=run_pantheon_mission, inputs=[mission_prompt], outputs=[mission_log_output, file_tree, live_terminal, download_zip_btn])

if __name__ == "__main__":
    demo.launch(debug=True)