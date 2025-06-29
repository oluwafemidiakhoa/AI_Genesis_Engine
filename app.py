import gradio as gr
import openai
import google.generativeai as genai
import os
import json
import subprocess
import requests
import time
import re
import threading
from queue import Queue
import zipfile
from io import BytesIO

# --- CONFIGURATION & STATE ---
PROJECT_DIR = "alpha_omega_project"
openai_client, gemini_model = None, None
app_process = None

# --- TOOLS (Finalized) ---
def oracle_search(query: str) -> str:
    serper_api_key = os.getenv("SERPER_API_KEY")
    if not serper_api_key: return "Error: SERPER_API_KEY secret not found."
    print(f"The Oracle: Performing direct web search for '{query}'...")
    url, payload = "https://google.serper.dev/search", json.dumps({"q": query})
    headers = {'X-API-KEY': serper_api_key, 'Content-Type': 'application/json'}
    try:
        response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        results = response.json()
        summary = "Search Results:\n"
        if "organic" in results:
            for item in results["organic"][:4]:
                summary += f"- Title: {item.get('title')}\n  Link: {item.get('link')}\n  Snippet: {item.get('snippet')}\n\n"
        return summary
    except Exception as e: return f"Error connecting to The Oracle: {e}"

def execute_shell_command(command: str, cwd: str = PROJECT_DIR) -> (str, bool):
    try:
        print(f"Tooling Specialist: Executing shell command `{command}` in `{cwd}`...")
        result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120)
        output = f"$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        return output, result.returncode == 0
    except Exception as e: return f"Error executing shell command: {e}", False

def write_file(path: str, content: str, cwd: str = PROJECT_DIR) -> str:
    full_path = os.path.join(cwd, path)
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f: f.write(content)
        return f"Successfully wrote to {path}."
    except Exception as e: return f"Error writing to file: {e}"

def read_file(path: str, cwd: str = PROJECT_DIR) -> str:
    # ... (same as before)
    full_path = os.path.join(cwd, path)
    try:
        with open(full_path, 'r', encoding='utf-8') as f: return f.read()
    except Exception as e: return f"Error reading file: {e}"

def stream_process_output(process, queue):
    # ... (same as before)
    for line in iter(process.stdout.readline, ''): queue.put(line)
    process.stdout.close()

def run_background_app(command: str, cwd: str) -> str:
    # ... (same as before)
    global app_process
    if app_process: app_process.kill()
    try:
        app_process = subprocess.Popen(command, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        return f"Successfully started background process for '{command}'."
    except Exception as e: return f"Error starting background process: {e}"

# --- INITIALIZATION & UTILITIES ---
def initialize_clients():
    # ... (same as before)
    global openai_client, gemini_model
    keys = {"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"), "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"), "SERPER_API_KEY": os.getenv("SERPER_API_KEY")}
    missing_keys = [k for k, v in keys.items() if not v]
    if missing_keys: return f"❌ Missing Secrets: {', '.join(missing_keys)}", False
    try:
        openai_client = openai.OpenAI(api_key=keys["OPENAI_API_KEY"])
        openai_client.models.list()
        genai.configure(api_key=keys["GOOGLE_API_KEY"])
        gemini_model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")
        gemini_model.generate_content("ping")
        return "✅ All engines online. The Alpha & Omega Framework is ready.", True
    except Exception as e: return f"❌ API Initialization Failed: {e}", False

def parse_json_from_string(text: str) -> dict or list:
    # ... (same as before)
    match = re.search(r'```json\s*([\s\S]*?)\s*```|([\s\S]*)', text)
    if match:
        json_str = match.group(1) or match.group(2)
        try: return json.loads(json_str.strip())
        except json.JSONDecodeError as e: raise ValueError(f"Failed to decode JSON. Error: {e}. Text: '{json_str[:200]}...'")
    raise ValueError("No JSON found.")

def execute_tooling_task(instruction: str, cwd: str):
    # ... (same as before)
    tooling_model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest", tools=[oracle_search, execute_shell_command, write_file, read_file, run_background_app])
    response = tooling_model.generate_content(instruction)
    if not response.candidates or not response.candidates[0].content.parts or not response.candidates[0].content.parts[0].function_call:
        return f"Tooling Specialist decided no tool was necessary.", cwd, True
    function_call = response.candidates[0].content.parts[0].function_call
    tool_name, tool_args = function_call.name, dict(function_call.args)
    if tool_name in ["execute_shell_command", "run_background_app", "write_file", "read_file"]:
        tool_args["cwd"] = cwd
    if tool_name == "execute_shell_command" and tool_args.get("command", "").startswith("cd "):
        new_dir = tool_args["command"].split("cd ", 1)[1].strip()
        new_cwd = os.path.normpath(os.path.join(cwd, new_dir))
        if os.path.isdir(new_cwd): return f"Successfully changed directory to {new_cwd}", new_cwd, True
        else: return f"Error: Directory '{new_cwd}' not found.", cwd, False
    result = globals()[tool_name](**tool_args)
    success = "Error" not in str(result) and "ERROR" not in str(result)
    if isinstance(result, tuple): return result[0], cwd, result[1]
    else: return result, cwd, success

# --- THE ALPHA & OMEGA ORCHESTRATOR ---
def run_alpha_omega_mission(initial_prompt):
    mission_log = "Mission Log: [START]\n"
    yield mission_log, gr.update(choices=[]), "", gr.update(visible=False, value=None)
    
    os.makedirs(PROJECT_DIR, exist_ok=True)
    
    # Phase 1: Architect plans
    mission_log += "Architect (Gemini): Creating a high-level sequence of instructions...\n"
    yield mission_log, None, None, None
    
    # ALPHA & OMEGA UPGRADE: The final, perfected prompt.
    architect_prompt = (
        "You are The Architect, an expert AI system designer. Create a logical, step-by-step plan to achieve the user's goal. "
        "The plan MUST be a valid JSON array of tasks. Each task object should have a single key: `instruction`. "
        "Be explicit and tool-oriented in your instructions. "
        "For example, instead of 'Create a directory', say 'Run the command: mkdir my_app'. "
        "Instead of 'search for libraries', say 'Use oracle_search to find libraries for X'. "
        "Instead of 'install dependencies', say 'Run the command: pip install -r requirements.txt'. "
        "Your entire response must be ONLY the raw JSON array."
    )
    gemini_json_config = genai.types.GenerationConfig(response_mime_type="application/json")
    try:
        response = gemini_model.generate_content(f"{architect_prompt}\n\nUser Goal: {initial_prompt}", generation_config=gemini_json_config)
        task_list = parse_json_from_string(response.text)
        mission_log += f"Architect: Plan generated with {len(task_list)} tasks. Orchestrator will now assign agents.\n"
        yield mission_log, None, None, None
    except Exception as e:
        mission_log += f"Architect: [FATAL ERROR] Failed to create a valid plan. Reason: {e}\n"
        yield mission_log, None, None, None
        return

    # Phase 2: Execution Loop with perfected delegation
    current_files, current_working_directory = {}, PROJECT_DIR
    
    # ALPHA & OMEGA UPGRADE: A more robust keyword list.
    tooling_keywords = r'\b(run the command|mkdir|cd|pip|python|source|install|search)\b'
    
    for i, task in enumerate(task_list):
        task_num, instruction = i + 1, task['instruction']
        
        # The Rule of Law: a regex search makes the keyword matching foolproof.
        if re.search(tooling_keywords, instruction, re.IGNORECASE):
            chosen_agent = 'Tooling_Specialist'
        else:
            chosen_agent = 'Lead_Developer'

        mission_log += f"\n--- Executing Task {task_num}/{len(task_list)} ---\n"
        mission_log += f"Engine (Alpha & Omega Protocol): Assigning `{chosen_agent}`. Instruction: `{instruction}`\n"
        yield mission_log, gr.update(choices=list(current_files.keys())), "", None
        time.sleep(1)
        
        try:
            success = True
            if chosen_agent == 'Lead_Developer':
                developer_prompt = "You are the Lead Developer (GPT-4o). Write the full content for the specified file. Output MUST be a JSON object with a single key `code`."
                response = openai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": developer_prompt},{"role": "user", "content": instruction}], response_format={"type": "json_object"})
                code_content = json.loads(response.choices[0].message.content)['code']
                file_path_prompt = "You are a file system manager. Based on the instruction, determine the correct relative file path. Respond with a JSON object with one key: `path`."
                response = gemini_model.generate_content(f"{file_path_prompt}\n\nInstruction: {instruction}", generation_config=gemini_json_config)
                file_path = parse_json_from_string(response.text)['path']
                result = write_file(file_path, code_content, cwd=current_working_directory)
                mission_log += f"Lead Developer: Code generated. Result: {result}\n"
                current_files[file_path] = code_content
                success = "Error" not in result
            elif chosen_agent == 'Tooling_Specialist':
                result, current_working_directory, success = execute_tooling_task(instruction, current_working_directory)
                mission_log += f"Tooling Specialist Result:\n---\n{result}\n---\n"
            if not success:
                mission_log += f"Engine: [TASK FAILED] An error occurred. Aborting mission.\n"
                yield mission_log, gr.update(choices=list(current_files.keys())), "", None
                return
            yield mission_log, gr.update(choices=list(current_files.keys())), "", None
        except Exception as e:
            mission_log += f"Engine: [FATAL ERROR] Task failed. Reason: {e}\nAborting mission.\n"
            yield mission_log, gr.update(choices=list(current_files.keys())), "", None
            return

    # Finalization
    mission_log += "\n--- Mission Complete ---"
    zip_path = os.path.join(PROJECT_DIR, "ai_generated_app.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files_on_disk in os.walk(PROJECT_DIR):
            for file in files_on_disk:
                if file == os.path.basename(zip_path): continue
                file_path_on_disk = os.path.join(root, file)
                arcname = os.path.relpath(file_path_on_disk, PROJECT_DIR)
                zf.write(file_path_on_disk, arcname)
    yield mission_log, gr.update(choices=list(current_files.keys())), "", gr.update(visible=True, value=zip_path)

# --- GRADIO UI ---
with gr.Blocks(theme=gr.themes.Default(primary_hue="blue", secondary_hue="indigo"), title="Alpha & Omega Framework") as demo:
    gr.Markdown("# 🌌 Alpha & Omega: The Autonomous AI Developer")
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
            mission_prompt = gr.Textbox(label="High-Level Objective", placeholder="e.g., Build a real-time stock dashboard using the Yahoo Finance API.")
            launch_btn = gr.Button("🚀 Launch Mission", variant="primary", interactive=False)
            gr.Markdown("### 📜 Mission Log")
            mission_log_output = gr.Textbox(label="Mission Log", lines=20, interactive=False, autoscroll=True)
    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    activate_btn.click(handle_activation, [], [status_bar, launch_btn])
    launch_btn.click(fn=run_alpha_omega_mission, inputs=[mission_prompt], outputs=[mission_log_output, file_tree, gr.Textbox(visible=False), download_zip_btn])

if __name__ == "__main__":
    demo.launch(debug=True)