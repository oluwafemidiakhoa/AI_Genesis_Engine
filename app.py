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
PROJECT_DIR = "oracle_project"
openai_client, gemini_model = None, None
app_process = None

# --- ORACLE UPGRADE: THE ULTIMATE SEARCH TOOL ---
def oracle_search(query: str) -> str:
    """Performs a direct, programmatic web search using the Serper.dev API."""
    serper_api_key = os.getenv("SERPER_API_KEY")
    if not serper_api_key:
        return "Error: SERPER_API_KEY secret not found."
    
    print(f"The Oracle: Performing direct web search for '{query}'...")
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query})
    headers = {'X-API-KEY': serper_api_key, 'Content-Type': 'application/json'}
    
    try:
        response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        results = response.json()
        
        summary = "Search Results:\n"
        if "organic" in results:
            for item in results["organic"][:4]: # Top 4 results
                summary += f"- Title: {item.get('title')}\n  Link: {item.get('link')}\n  Snippet: {item.get('snippet')}\n\n"
        return summary if summary else "No results found."
    except Exception as e:
        return f"Error connecting to The Oracle (Serper API): {e}"

# Other tools (execute_shell_command, etc.) remain the same.
def execute_shell_command(command: str, cwd: str = PROJECT_DIR) -> str:
    try:
        if "cd " in command:
            new_dir = command.split("cd ")[1].strip()
            target_path = os.path.join(cwd, new_dir)
            if os.path.isdir(target_path): return f"Successfully changed directory to {target_path}", True
            else: return f"Error: Directory '{target_path}' not found.", False
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

def initialize_clients():
    global openai_client, gemini_model
    openai_key = os.getenv("OPENAI_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    serper_key = os.getenv("SERPER_API_KEY")
    if not all([openai_key, google_key, serper_key]):
        return "❌ Missing Secrets: Please set `OPENAI_API_KEY`, `GOOGLE_API_KEY`, and `SERPER_API_KEY` and restart.", False
    try:
        openai_client = openai.OpenAI(api_key=openai_key)
        openai_client.models.list()
        genai.configure(api_key=google_key)
        gemini_model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")
        gemini_model.generate_content("ping")
        return "✅ All engines online. The Oracle is waiting.", True
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
        return f"Tooling Specialist decided no tool was necessary for: '{instruction}'.", cwd, True
    function_call = response.candidates[0].content.parts[0].function_call
    tool_name = function_call.name
    tool_args = dict(function_call.args)
    
    if tool_name in ["execute_shell_command", "run_background_app", "write_file", "read_file"]:
        tool_args["cwd"] = cwd
    
    if tool_name == "execute_shell_command":
        result, success = globals()[tool_name](**tool_args)
        if "cd " in tool_args.get("command", "") and success:
            new_dir = tool_args["command"].split("cd ")[1].strip()
            new_cwd = os.path.normpath(os.path.join(cwd, new_dir))
            if os.path.isdir(new_cwd): return result, new_cwd, success
        return result, cwd, success
    else:
        result = globals()[tool_name](**tool_args)
        return result, cwd, "Error" not in result

# --- ORACLE ORCHESTRATOR ---
def run_oracle_mission(initial_prompt):
    mission_log = "Mission Log: [START]\n"
    yield mission_log, gr.update(choices=[]), "", gr.update(visible=False, value=None)
    
    os.makedirs(PROJECT_DIR, exist_ok=True)
    
    # Phase 1: Architect plans
    mission_log += "Architect (Gemini): Creating initial project plan...\n"
    yield mission_log, None, None, None
    
    architect_prompt = (
        "You are The Architect, an expert AI system designer. Create a logical, step-by-step plan for the user's goal. "
        "Your primary tool for information gathering is `oracle_search`. Use it to find libraries and API details. "
        "The plan MUST be a valid JSON array of tasks. Each task is an object with `agent` and `instruction` keys. "
        "AGENTS: 'Lead_Developer' for writing all application files; 'Tooling_Specialist' for all other actions (searching, shell commands). "
        "Be specific with file paths (e.g., 'my_app/requirements.txt'). Your entire response must be ONLY the raw JSON array."
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
        task_num = i + 1
        instruction = task['instruction']
        chosen_agent = task['agent']
        mission_log += f"\n--- Executing Task {task_num}/{len(task_list)} ---\n"
        mission_log += f"Engine: Delegating to `{chosen_agent}`. Instruction: `{instruction}`\n"
        yield mission_log, gr.update(choices=list(current_files.keys())), "", None
        time.sleep(1)
        try:
            result = ""
            success = True
            if chosen_agent == 'Lead_Developer':
                developer_prompt = "You are the Lead Developer (GPT-4o). Write the full content for a single application file as instructed. Output MUST be a JSON object with a single key `code`."
                response = openai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": developer_prompt},{"role": "user", "content": instruction}], response_format={"type": "json_object"})
                code_content = json.loads(response.choices[0].message.content)['code']
                file_path_prompt = "You are a file system manager. Based on the instruction, determine the correct relative file path. Respond with a JSON object with one key: `path`."
                response = gemini_model.generate_content(f"{file_path_prompt}\n\nInstruction: {instruction}", generation_config=gemini_json_config)
                file_path = parse_json_from_string(response.text)['path']
                result = write_file(file_path, code_content, cwd=current_working_directory)
                mission_log += f"Lead Developer: Code generated. Result: {result}\n"
                current_files[file_path] = code_content
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

    mission_log += "\n--- Mission Complete ---"
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files_on_disk in os.walk(PROJECT_DIR):
            for file in files_on_disk:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, PROJECT_DIR)
                zf.write(file_path, arcname)
    zip_buffer.seek(0)
    downloadable_zip = (zip_buffer, "ai_generated_app.zip")
    yield mission_log, gr.update(choices=list(current_files.keys())), "", gr.update(visible=True, value=downloadable_zip)

# --- GRADIO UI ---
with gr.Blocks(theme=gr.themes.Default(primary_hue="blue", secondary_hue="sky"), title="Oracle Framework") as demo:
    gr.Markdown("# 🔮 Oracle: The AI Developer with Unfiltered Vision")
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
            gr.Markdown("### 📜 Mission Log & Live Terminal")
            mission_log_output = gr.Textbox(label="Mission Log", lines=15, interactive=False, autoscroll=True)
            terminal_output = gr.Textbox(label="Live App Terminal", lines=10, interactive=False, autoscroll=True)
    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    activate_btn.click(handle_activation, [], [status_bar, launch_btn])
    launch_btn.click(fn=run_oracle_mission, inputs=[mission_prompt], outputs=[mission_log_output, file_tree, terminal_output, download_zip_btn])

if __name__ == "__main__":
    demo.launch(debug=True)