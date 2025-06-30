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
PROJECT_DIR = "chronos_project"
openai_client = None
app_process = None

# --- THE CHRONOS TOOLSET ---
def list_files(path: str = ".") -> str:
    full_path = os.path.join(PROJECT_DIR, path)
    if not os.path.isdir(full_path): return f"Error: Directory '{path}' does not exist."
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

def run_shell_command(command: str, cwd: str = PROJECT_DIR) -> str:
    try:
        result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120)
        return f"COMMAND:\n$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e: return f"Error executing shell command: {e}"
    
def change_directory(path: str) -> str:
    """Note to AI: This only changes the 'current directory' for future commands in this session."""
    return f"Directory changed to {path}. Future shell commands will run here."

def launch_server(command: str, cwd: str = PROJECT_DIR) -> str:
    global app_process
    if app_process: app_process.kill()
    try:
        app_process = subprocess.Popen(command, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
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
        return "✅ Engine Online. The Chronos Framework is ready.", True
    except Exception as e: return f"❌ API Initialization Failed: {e}", False

def stream_process_output(process, queue):
    for line in iter(process.stdout.readline, ''): queue.put(line)
    process.stdout.close()

# --- THE CHRONOS ORCHESTRATOR ---
def run_chronos_mission(initial_prompt, max_steps=25):
    global app_process
    
    mission_log = "[MISSION LOG: START]\n"
    yield mission_log, [], "", gr.update(visible=False, value=None)

    if os.path.exists(PROJECT_DIR): shutil.rmtree(PROJECT_DIR)
    os.makedirs(PROJECT_DIR, exist_ok=True)
    
    # Chronos State
    current_working_directory = PROJECT_DIR
    
    conversation = [
        {"role": "system", "content": "You are an autonomous AI developer. Your goal is to achieve the user's objective by calling a sequence of functions. Think step-by-step. You have a file system and a shell. Use `change_directory` to navigate. Use `launch_server` for long-running processes like web servers. When the objective is complete, call `finish_mission`."},
        {"role": "user", "content": f"My objective is: {initial_prompt}"}
    ]
    
    tools = [
        {"type": "function", "function": {"name": "list_files", "description": "Lists files in a directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
        {"type": "function", "function": {"name": "write_file", "description": "Writes content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
        {"type": "function", "function": {"name": "run_shell_command", "description": "Executes a short-lived command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "change_directory", "description": "Changes the working directory for subsequent shell commands.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
        {"type": "function", "function": {"name": "launch_server", "description": "Launches a long-running server process.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "finish_mission", "description": "Call this when the objective is complete.", "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}}
    ]
    
    for i in range(max_steps):
        mission_log += f"\n--- Step {i+1}/{max_steps} ---\nChronos Agent is thinking...\n"
        current_file_list = [f for f in os.listdir(current_working_directory)] if os.path.isdir(current_working_directory) else []
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
                
                # Pass CWD to tools that need it
                if function_name in ["run_shell_command", "launch_server"]:
                    function_args["cwd"] = current_working_directory

                tool_function = globals()[function_name]
                result = tool_function(**function_args)
                
                # Update CWD if 'cd' was called
                if function_name == "change_directory":
                    new_path = os.path.join(PROJECT_DIR, function_args["path"])
                    if os.path.isdir(new_path):
                        current_working_directory = new_path
                    else:
                        result = f"Error: Directory '{function_args['path']}' does not exist."

                mission_log += f"Result:\n---\n{result}\n---\n"
                
                if function_name == "finish_mission":
                    mission_log += "--- MISSION COMPLETE ---"
                    zip_path = os.path.join(PROJECT_DIR, "chronos_app.zip")
                    with zipfile.ZipFile(zip_path, 'w') as zf:
                        for root, _, files in os.walk(PROJECT_DIR):
                            for file in files:
                                if file != os.path.basename(zip_path): zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), PROJECT_DIR))
                    
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
with gr.Blocks(theme=gr.themes.Soft(primary_hue="amber", secondary_hue="orange"), title="Chronos Framework") as demo:
    gr.Markdown("# ⌛ Chronos: The Autonomous AI Developer")
    status_bar = gr.Textbox("System Offline. Click 'Activate Engine' to begin.", label="System Status", interactive=False)
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ Controls")
            activate_btn = gr.Button("Activate Engine")
            gr.Markdown("### 🌳 Project Files")
            file_tree = gr.CheckboxGroup(label="File System", interactive=False)
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
    launch_btn.click(fn=run_chronos_mission, inputs=[mission_prompt], outputs=[mission_log_output, file_tree, live_terminal, download_zip_btn])

if __name__ == "__main__":
    demo.launch(debug=True)