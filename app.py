import gradio as gr
import openai
import google.generativeai as genai
import os
import json
import subprocess
import requests
from bs4 import BeautifulSoup
import time
import re
import threading
from queue import Queue
import zipfile
from io import BytesIO

# --- CONFIGURATION, TOOLS, INITIALIZATION, etc. (Mostly unchanged) ---
PROJECT_DIR = "prometheus_project"
openai_client, gemini_model = None, None
app_process = None

def web_search(query: str) -> str:
    # PROMETHEUS UPGRADE: Add retries
    for attempt in range(2):
        try:
            print(f"Tooling Specialist: Performing web search for '{query}' (Attempt {attempt+1})...")
            response = requests.get(f"https://html.duckduckgo.com/html/?q={query}", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            snippets = [p.get_text() for p in soup.find_all('a', class_='result__a')]
            return "Search Results:\n" + "\n".join(f"- {s}" for s in snippets[:5]) if snippets else "No results found."
        except requests.exceptions.Timeout:
            print("Web search timed out, retrying...")
            time.sleep(1)
        except Exception as e:
            return f"Error during web search: {e}"
    return "Error: Web search failed after multiple retries."

# Other tools (write_file, read_file) are the same
def write_file(path: str, content: str) -> str:
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f: f.write(content)
        return f"Successfully wrote to {path}."
    except Exception as e: return f"Error writing to file: {e}"
def read_file(path: str) -> str:
    full_path = os.path.join(PROJECT_DIR, path)
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
    if not openai_key or not google_key: return "❌ Set secrets and restart.", False
    try:
        openai_client = openai.OpenAI(api_key=openai_key)
        openai_client.models.list()
        genai.configure(api_key=google_key)
        gemini_model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")
        gemini_model.generate_content("ping")
        return "✅ All engines online. Prometheus awaits.", True
    except Exception as e: return f"❌ API Initialization Failed: {e}", False
def parse_json_from_string(text: str) -> dict or list:
    match = re.search(r'```json\s*([\s\S]*?)\s*```|([\s\S]*)', text)
    if match:
        json_str = match.group(1) or match.group(2)
        try: return json.loads(json_str.strip())
        except json.JSONDecodeError as e: raise ValueError(f"Failed to decode JSON. Error: {e}. Text: '{json_str[:200]}...'")
    raise ValueError("No JSON found.")

# --- PROMETHEUS UPGRADE: The Intelligent Dependency Checker ---
def execute_shell_command(command: str, cwd: str = PROJECT_DIR) -> str:
    # If it's a pip install command, use the dry-run check first
    if command.startswith("pip install"):
        dry_run_command = command.replace("pip install", "pip install --dry-run")
        print(f"Dependency Agent: Performing dry run: `{dry_run_command}`")
        dry_run_result = subprocess.run(dry_run_command, shell=True, cwd=cwd, capture_output=True, text=True)
        dry_run_output = dry_run_result.stdout + dry_run_result.stderr

        # Ask the DependencyConflictAgent to analyze the dry run
        conflict_agent_prompt = (
            "You are a Python dependency expert. Analyze the following `pip install --dry-run` output. "
            "Your ONLY job is to determine if installing these packages would cause a dependency conflict with essential libraries like 'gradio'. "
            "Respond with a single JSON object: `{\"conflict\": true/false, \"reason\": \"A brief explanation of the conflict, or 'None' if no conflict exists.\"}`."
        )
        gemini_json_config = genai.types.GenerationConfig(response_mime_type="application/json")
        response = gemini_model.generate_content(f"{conflict_agent_prompt}\n\nDry Run Output:\n{dry_run_output}", generation_config=gemini_json_config)
        analysis = parse_json_from_string(response.text)

        if analysis.get("conflict"):
            reason = analysis.get("reason")
            error_message = f"Dependency Conflict Detected by Agent! Reason: {reason}. Aborting installation to prevent system failure."
            print(error_message)
            return error_message

    # If no conflict, proceed with the actual command
    try:
        print(f"Tooling Specialist: Executing shell command `{command}` in `{cwd}`...")
        result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120)
        return f"$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e:
        return f"Error executing shell command: {e}"

def execute_tooling_task(instruction: str, cwd: str):
    tooling_model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest", tools=[web_search, execute_shell_command, write_file, read_file, run_background_app])
    response = tooling_model.generate_content(instruction)
    if not response.candidates or not response.candidates[0].content.parts or not response.candidates[0].content.parts[0].function_call:
        return f"Tooling Specialist decided no tool was necessary.", cwd
    function_call = response.candidates[0].content.parts[0].function_call
    tool_name = function_call.name
    tool_args = dict(function_call.args)
    if tool_name in ["execute_shell_command", "run_background_app"]: tool_args["cwd"] = cwd
    
    # Handle cd separately to manage state
    if tool_name == "execute_shell_command" and "cd " in tool_args.get("command", ""):
        new_dir = tool_args["command"].split("cd ")[1].strip()
        new_cwd = os.path.normpath(os.path.join(cwd, new_dir))
        if os.path.isdir(new_cwd):
            return f"Successfully changed directory to {new_cwd}", new_cwd
        else:
            return f"Error: Directory '{new_cwd}' not found.", cwd

    result = globals()[tool_name](**tool_args)
    return result, cwd

# --- ODYSSEY ORCHESTRATOR & UI (No other changes needed) ---
def run_odyssey(initial_prompt):
    # This entire orchestrator function can remain the same.
    # The new intelligent logic is self-contained within execute_shell_command.
    mission_log = "Mission Log: [START]\n"
    yield mission_log, gr.update(choices=[]), "", gr.update(visible=False, value=None)
    os.makedirs(PROJECT_DIR, exist_ok=True)
    current_working_directory = PROJECT_DIR
    mission_log += "Architect (Gemini): Creating a logical, efficient project plan...\n"
    yield mission_log, None, None, None
    architect_prompt = (
        "You are The Architect, an expert AI system designer. Create a logical, step-by-step plan for the user's goal. "
        "The plan MUST be a valid JSON array of tasks. Each task is an object with `agent` and `instruction` keys. "
        "CRITICAL AGENT ROLES: "
        "- Use 'Lead_Developer' ONLY for writing the application's source code and text files (e.g., .py, .js, .html, .css, .txt). "
        "- Use 'Tooling_Specialist' for ALL other actions: web searches, and running shell commands like 'mkdir', 'pip', or 'python'. "
        "Be efficient: install all requirements in a single step. Your entire response must be ONLY the raw JSON array."
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
    current_files = {}
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
            if chosen_agent == 'Lead_Developer':
                developer_prompt = (
                    "You are the Lead Developer (GPT-4o). Your task is to write the full content for a single application file as instructed. "
                    "This includes Python, JavaScript, HTML, CSS, and requirements.txt. "
                    "Your output MUST be a JSON object with a single key `code` containing the full, raw code."
                )
                response = openai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": developer_prompt},{"role": "user", "content": instruction}], response_format={"type": "json_object"})
                code_content = json.loads(response.choices[0].message.content)['code']
                file_path_prompt = "You are a file system manager. Based on the instruction, determine the correct relative file path. Respond with a JSON object with one key: `path`."
                response = gemini_model.generate_content(f"{file_path_prompt}\n\nInstruction: {instruction}", generation_config=gemini_json_config)
                file_path = parse_json_from_string(response.text)['path']
                result = write_file(file_path, code_content)
                mission_log += f"Lead Developer: Code generated. Result: {result}\n"
                current_files[file_path] = code_content
            elif chosen_agent == 'Tooling_Specialist':
                result, current_working_directory = execute_tooling_task(instruction, current_working_directory)
                mission_log += f"Tooling Specialist Result:\n---\n{result}\n---\n"
            if "Error:" in str(result) or "ERROR:" in str(result) or "Conflict Detected" in str(result):
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
        for filename, content in current_files.items(): zf.writestr(filename, content)
    zip_buffer.seek(0)
    downloadable_zip = (zip_buffer, "ai_generated_app.zip")
    terminal_text = ""
    if app_process:
        mission_log += "\n--- Application is Running ---"
        output_queue = Queue()
        thread = threading.Thread(target=stream_process_output, args=(app_process, output_queue))
        thread.daemon = True
        thread.start()
        while thread.is_alive() or not output_queue.empty():
            while not output_queue.empty():
                terminal_text += output_queue.get()
                yield mission_log, gr.update(choices=list(current_files.keys())), terminal_text, gr.update(visible=True, value=downloadable_zip)
            time.sleep(0.5)
    yield mission_log, gr.update(choices=list(current_files.keys())), terminal_text, gr.update(visible=True, value=downloadable_zip)

with gr.Blocks(theme=gr.themes.Default(primary_hue="blue", secondary_hue="sky"), title="Prometheus Framework") as demo:
    gr.Markdown("# 🔥 Prometheus: The AI Developer with Environmental Awareness")
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
            mission_prompt = gr.Textbox(label="High-Level Objective", placeholder="e.g., Build a Python Flask web app that generates a QR code from user text input.")
            launch_btn = gr.Button("🚀 Launch Mission", variant="primary", interactive=False)
            gr.Markdown("### 📜 Mission Log & Live Terminal")
            mission_log_output = gr.Textbox(label="Mission Log", lines=15, interactive=False, autoscroll=True)
            terminal_output = gr.Textbox(label="Live App Terminal", lines=10, interactive=False, autoscroll=True)
    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    activate_btn.click(handle_activation, [], [status_bar, launch_btn])
    launch_btn.click(fn=run_odyssey, inputs=[mission_prompt], outputs=[mission_log_output, file_tree, terminal_output, download_zip_btn])

if __name__ == "__main__":
    demo.launch(debug=True)