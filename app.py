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
PROJECT_DIR = "apex_project" # Renamed for the final version
openai_client, gemini_model = None, None
app_process = None

# --- TOOLS (No changes) ---
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
    full_path = os.path.join(cwd, path)
    try:
        with open(full_path, 'r', encoding='utf-8') as f: return f.read()
    except Exception as e: return f"Error reading file: {e}"

def stream_process_output(process, queue):
    for line in iter(process.stdout.readline, ''): queue.put(line)
    process.stdout.close()

def run_background_app(command: str, cwd: str) -> str:
    global app_process
    if app_process: app_process.kill()
    try:
        app_process = subprocess.Popen(command, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        return f"Successfully started background process for '{command}'."
    except Exception as e: return f"Error starting background process: {e}"

# --- INITIALIZATION & UTILITIES (No changes) ---
def initialize_clients():
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
        return "✅ All engines online. The Apex Framework is ready.", True
    except Exception as e: return f"❌ API Initialization Failed: {e}", False

def parse_json_from_string(text: str) -> dict or list:
    match = re.search(r'```json\s*([\s\S]*?)\s*```|([\s\S]*)', text)
    if match:
        json_str = match.group(1) or match.group(2)
        try: return json.loads(json_str.strip())
        except json.JSONDecodeError as e: raise ValueError(f"Failed to decode JSON. Error: {e}. Text: '{json_str[:200]}...'")
    raise ValueError("No JSON found.")

def execute_tooling_task(instruction: str, cwd: str):
    tooling_model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest", tools=[oracle_search, execute_shell_command, write_file, read_file, run_background_app])
    response = tooling_model.generate_content(instruction)
    if not response.candidates or not response.candidates[0].content.parts or not response.candidates[0].content.parts[0].function_call:
        if "cd " in instruction:
            new_dir = instruction.split("cd ")[1].strip()
            new_cwd = os.path.normpath(os.path.join(cwd, new_dir))
            if os.path.isdir(new_cwd): return f"Successfully changed directory to {new_cwd}", new_cwd, True
            else: return f"Error: Directory '{new_cwd}' not found.", cwd, False
        return f"Tooling Specialist decided no tool was necessary.", cwd, True
    function_call = response.candidates[0].content.parts[0].function_call
    tool_name, tool_args = function_call.name, dict(function_call.args)
    if tool_name in ["execute_shell_command", "run_background_app", "write_file", "read_file"]:
        tool_args["cwd"] = cwd
    result = globals()[tool_name](**tool_args)
    success = "Error" not in str(result) and "ERROR" not in str(result)
    if isinstance(result, tuple): return result[0], cwd, result[1]
    else: return result, cwd, success

# --- APEX ORCHESTRATOR ---
def run_apex_mission(initial_prompt):
    mission_log = "Mission Log: [START]\n"
    yield mission_log, gr.update(choices=[]), "", gr.update(visible=False, value=None)
    
    os.makedirs(PROJECT_DIR, exist_ok=True)
    
    # Phase 1: Architect plans
    mission_log += "Architect (Gemini): Creating a state-aware project plan...\n"
    yield mission_log, None, None, None
    architect_prompt = (
        "You are The Architect. Create a logical, step-by-step plan as a JSON array of tasks. "
        "Each task has `agent` ('Lead_Developer' for all file creation; 'Tooling_Specialist' for commands/searches) and `instruction`. "
        "The system has a stateful `cd` command. You MUST `cd` into a directory before running commands like `pip` within it. "
        "Be specific with file paths. Your entire response must be ONLY the raw JSON array."
    )
    gemini_json_config = genai.types.GenerationConfig(response_mime_type="application/json")
    try:
        response = gemini_model.generate_content(f"{architect_prompt}\n\nUser Goal: {initial_prompt}", generation_config=gemini_json_config)
        task_list = parse_json_from_string(response.text)
        mission_log += f"Architect: Plan generated with {len(task_list)} tasks.\n"
        yield mission_log, None, None, None
    except Exception as e:
        mission_log += f"Architect: [FATAL ERROR] Failed to create a valid plan. Reason: {e}\n"
        yield mission_log, None, None, None
        return

    # Phase 2: Execution Loop
    current_files = {}
    current_working_directory = PROJECT_DIR
    for i, task in enumerate(task_list):
        task_num, instruction, chosen_agent = i + 1, task['instruction'], task['agent']
        mission_log += f"\n--- Executing Task {task_num}/{len(task_list)} ---\n"
        mission_log += f"Engine: Delegating to `{chosen_agent}`. Instruction: `{instruction}`\n"
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

    # Finalization and Download
    mission_log += "\n--- Mission Complete ---\n"
    
    # APEX UPGRADE: Save zip to disk and yield the path
    zip_filename = "ai_generated_app.zip"
    zip_path = os.path.join(PROJECT_DIR, zip_filename)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files_on_disk in os.walk(PROJECT_DIR):
            for file in files_on_disk:
                if file == zip_filename: continue # Don't add the zip to itself
                file_path_on_disk = os.path.join(root, file)
                arcname = os.path.relpath(file_path_on_disk, PROJECT_DIR)
                zf.write(file_path_on_disk, arcname)
                
    terminal_text = ""
    if app_process:
        # (Live terminal streaming logic is the same)
        mission_log += "--- Application is Running ---\n"
        output_queue = Queue()
        thread = threading.Thread(target=stream_process_output, args=(app_process, output_queue))
        thread.daemon = True
        thread.start()
        # Give a moment for initial output
        time.sleep(2)
        while not output_queue.empty():
            terminal_text += output_queue.get()
        # We don't need to keep streaming forever, just show the startup
    
    yield mission_log, gr.update(choices=list(current_files.keys())), terminal_text, gr.update(visible=True, value=zip_path)

# --- GRADIO UI ---
with gr.Blocks(theme=gr.themes.Default(primary_hue="teal", secondary_hue="green"), title="Apex Framework") as demo:
    gr.Markdown("# 🏆 Apex: The Autonomous AI Developer")
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
            gr.Markdown("### 📜 Mission Log & Live Terminal")
            mission_log_output = gr.Textbox(label="Mission Log", lines=15, interactive=False, autoscroll=True)
            terminal_output = gr.Textbox(label="Live App Terminal", lines=10, interactive=False, autoscroll=True)

    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    
    activate_btn.click(handle_activation, [], [status_bar, launch_btn])
    launch_btn.click(fn=run_apex_mission, inputs=[mission_prompt], outputs=[mission_log_output, file_tree, terminal_output, download_zip_btn])

if __name__ == "__main__":
    demo.launch(debug=True)