import gradio as gr
import openai
import google.generativeai as genai
import os
import json
import subprocess
import time
import re
import threading
from queue import Queue
import zipfile
from io import BytesIO

# --- CONFIGURATION & STATE ---
PROJECT_DIR = "olympus_project"
openai_client, gemini_model = None, None
app_process = None

# --- TOOLS (Finalized) ---
def create_directory(path: str) -> str:
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        os.makedirs(full_path, exist_ok=True)
        return f"Successfully created directory: {path}"
    except Exception as e: return f"Error creating directory: {e}"

def install_dependencies(requirements_path: str) -> (str, bool):
    full_req_path = os.path.join(PROJECT_DIR, requirements_path)
    if not os.path.exists(full_req_path):
        return f"Error: {requirements_path} not found.", False
    try:
        command = f"pip install -r {os.path.basename(full_req_path)}"
        cwd = os.path.dirname(full_req_path)
        result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120)
        output = f"$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        return output, "ERROR:" not in result.stderr.upper()
    except Exception as e: return f"Error installing dependencies: {e}", False

def run_python_server(script_path: str) -> str:
    global app_process
    if app_process: app_process.kill()
    full_script_path = os.path.join(PROJECT_DIR, script_path)
    if not os.path.exists(full_script_path): return f"Error: Script '{script_path}' not found."
    try:
        command = f"python {os.path.basename(full_script_path)}"
        cwd = os.path.dirname(full_script_path)
        app_process = subprocess.Popen(command, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        return f"Successfully started background process for '{script_path}'."
    except Exception as e: return f"Error starting background process: {e}"

def write_file(path: str, content: str) -> str:
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f: f.write(content)
        return f"Successfully wrote to {path}."
    except Exception as e: return f"Error writing to file: {e}"

# Other tools are the same
def stream_process_output(process, queue):
    for line in iter(process.stdout.readline, ''): queue.put(line)
    process.stdout.close()
def initialize_clients():
    global openai_client, gemini_model
    keys = {"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"), "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY")}
    if not all(keys.values()): return "❌ Missing OpenAI or Google API Key.", False
    try:
        openai_client = openai.OpenAI(api_key=keys["OPENAI_API_KEY"])
        openai_client.models.list()
        genai.configure(api_key=keys["GOOGLE_API_KEY"])
        gemini_model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")
        gemini_model.generate_content("ping")
        return "✅ All engines online. Olympus is ready.", True
    except Exception as e: return f"❌ API Initialization Failed: {e}", False
def parse_json_from_string(text: str) -> dict or list:
    match = re.search(r'```json\s*([\s\S]*?)\s*```|([\s\S]*)', text)
    if match:
        json_str = match.group(1) or match.group(2)
        try: return json.loads(json_str.strip())
        except json.JSONDecodeError as e: raise ValueError(f"Failed to decode JSON. Error: {e}. Text: '{json_str[:200]}...'")
    raise ValueError("No JSON found.")

# --- THE OLYMPUS ORCHESTRATOR ---
def run_olympus_mission(initial_prompt):
    mission_log = "Mission Log: [START]\n"
    yield mission_log, gr.update(choices=[]), "", gr.update(visible=False, value=None)
    
    os.makedirs(PROJECT_DIR, exist_ok=True)
    
    # Phase 1: Architect creates a high-level plan for code and structure.
    mission_log += "Architect (Gemini): Creating high-level application blueprint...\n"
    yield mission_log, None, None, None
    
    architect_prompt = (
        "You are The Architect. Create a logical, step-by-step plan to create the necessary files and directories for the user's goal. "
        "Do NOT include steps for dependency installation; this will be handled automatically. "
        "The plan MUST be a valid JSON array of tasks. Each task is an object with `agent` ('Lead_Developer' or 'Tooling_Specialist') and `instruction` keys. "
        "Use 'Tooling_Specialist' ONLY for `create_directory`. Use 'Lead_Developer' for writing ALL files. "
        "Your entire response must be ONLY the raw JSON array."
    )
    gemini_json_config = genai.types.GenerationConfig(response_mime_type="application/json")
    try:
        response = gemini_model.generate_content(f"{architect_prompt}\n\nUser Goal: {initial_prompt}", generation_config=gemini_json_config)
        task_list = parse_json_from_string(response.text)
        mission_log += f"Architect: Blueprint generated with {len(task_list)} tasks.\n"
        yield mission_log, None, None, None
    except Exception as e:
        mission_log += f"Architect: [FATAL ERROR] Failed to create a valid plan. Reason: {e}\n"
        yield mission_log, None, None, None
        return

    # Phase 2: Execution Loop for file/directory creation
    all_python_code = ""
    current_files = {}
    for i, task in enumerate(task_list):
        task_num, instruction, chosen_agent = i + 1, task['instruction'], task['agent']
        mission_log += f"\n--- Building Task {task_num}/{len(task_list)} ---\n"
        mission_log += f"Engine (Olympus Protocol): Delegating to `{chosen_agent}`. Instruction: `{instruction}`\n"
        yield mission_log, gr.update(choices=list(current_files.keys())), "", None
        
        try:
            if chosen_agent == 'Tooling_Specialist':
                result = create_directory(instruction.split("'")[1])
                mission_log += f"Tooling Specialist Result: {result}\n"
            elif chosen_agent == 'Lead_Developer':
                developer_prompt = "You are the Lead Developer (GPT-4o). Write the full content for the specified file. Output MUST be a JSON object with a single key `code`."
                response = openai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": developer_prompt},{"role": "user", "content": instruction}], response_format={"type": "json_object"})
                code_content = json.loads(response.choices[0].message.content)['code']
                file_path_prompt = "You are a file system manager. Based on the instruction, determine the correct relative file path. Respond with a JSON object with one key: `path`."
                response = gemini_model.generate_content(f"{file_path_prompt}\n\nInstruction: {instruction}", generation_config=gemini_json_config)
                file_path = parse_json_from_string(response.text)['path']
                result = write_file(file_path, code_content)
                mission_log += f"Lead Developer: Code generated. Result: {result}\n"
                current_files[file_path] = code_content
                if file_path.endswith('.py'):
                    all_python_code += f"\n\n# --- Content from {file_path} ---\n" + code_content
        except Exception as e:
            mission_log += f"Engine: [FATAL ERROR] Task failed. Reason: {e}\n"
            yield mission_log, gr.update(choices=list(current_files.keys())), "", None
            return

    # OLYMPUS UPGRADE: Phase 3 - Automated Dependency Analysis
    mission_log += "\n--- Build Complete. Analyzing Code for Dependencies ---\n"
    yield mission_log, gr.update(choices=list(current_files.keys())), "", None
    
    analyst_prompt = (
        "You are a Dependency Analyst. Read the following Python code and identify all external libraries that must be installed via pip. "
        "Ignore standard libraries. Respond with a single JSON object: `{\"dependencies\": [\"library1\", \"library2\"]}`."
    )
    try:
        response = gemini_model.generate_content(f"{analyst_prompt}\n\nCode:\n{all_python_code}", generation_config=gemini_json_config)
        dependencies = parse_json_from_string(response.text).get('dependencies', [])
        mission_log += f"Dependency Analyst: Identified dependencies: {', '.join(dependencies)}\n"
        
        # Phase 4: Create and install from requirements.txt
        req_path = "requirements.txt"
        result = write_file(req_path, "\n".join(dependencies))
        mission_log += f"Engine: Generated `requirements.txt`. Result: {result}\n"
        current_files[req_path] = "\n".join(dependencies)
        
        mission_log += "Engine: Installing all identified dependencies...\n"
        yield mission_log, gr.update(choices=list(current_files.keys())), "", None
        
        install_result, success = install_dependencies(req_path)
        mission_log += f"Tooling Specialist Result:\n---\n{install_result}\n---\n"
        if not success:
             mission_log += "Engine: [TASK FAILED] Dependency installation failed. Aborting.\n"
             yield mission_log, gr.update(choices=list(current_files.keys())), "", None
             return

    except Exception as e:
        mission_log += f"Engine: [FATAL ERROR] Dependency analysis failed. Reason: {e}\n"
        yield mission_log, gr.update(choices=list(current_files.keys())), "", None
        return

    # Phase 5: Run the application
    main_script = next((f for f in current_files if f.endswith('app.py') or f.endswith('main.py')), None)
    if not main_script:
        mission_log += "--- Mission Complete (No runnable script found) ---\n"
        # Final yield with download button
    else:
        mission_log += "\n--- Starting Application ---\n"
        yield mission_log, gr.update(choices=list(current_files.keys())), "", None
        run_result = run_python_server(main_script)
        mission_log += f"Tooling Specialist Result: {run_result}\n"
        mission_log += "\n--- Mission Complete ---"
        
    # Finalization and Download
    zip_path = os.path.join(PROJECT_DIR, "ai_generated_app.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # ... (zip logic is the same)
        for root, dirs, files_on_disk in os.walk(PROJECT_DIR):
            for file in files_on_disk:
                if file == os.path.basename(zip_path): continue
                file_path_on_disk = os.path.join(root, file)
                arcname = os.path.relpath(file_path_on_disk, PROJECT_DIR)
                zf.write(file_path_on_disk, arcname)
    yield mission_log, gr.update(choices=list(current_files.keys())), "", gr.update(visible=True, value=zip_path)

# --- GRADIO UI ---
with gr.Blocks(theme=gr.themes.Default(primary_hue="yellow", secondary_hue="amber"), title="Olympus Framework") as demo:
    gr.Markdown("# 🏛️ Olympus: The Self-Aware AI Developer")
    # ... UI is the same ...
    status_bar = gr.Textbox("System Offline. Click 'Activate Engines' to begin.", label="System Status", interactive=False)
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ Controls")
            activate_btn = gr.Button("Activate Engines")
            gr.Markdown("### 🌳 Project Files")
            file_tree = gr.Radio(label="File System", interactive=True)
            download_zip_btn = gr.DownloadButton(label="Download Project as .zip", visible=False)
        with gr.Column(scale=3):
            gr.Markdown("### 📝 Mission Control")
            mission_prompt = gr.Textbox(label="High-Level Objective", placeholder="e.g., Build a Python Flask web app that generates a QR code.")
            launch_btn = gr.Button("🚀 Launch Mission", variant="primary", interactive=False)
            gr.Markdown("### 📜 Mission Log")
            mission_log_output = gr.Textbox(label="Mission Log", lines=20, interactive=False, autoscroll=True)
    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    activate_btn.click(handle_activation, [], [status_bar, launch_btn])
    launch_btn.click(fn=run_olympus_mission, inputs=[mission_prompt], outputs=[mission_log_output, file_tree, gr.Textbox(visible=False), download_zip_btn])

if __name__ == "__main__":
    demo.launch(debug=True)