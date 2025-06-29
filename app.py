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

# --- CONFIGURATION, TOOLS, and INITIALIZATION (No changes) ---
PROJECT_DIR = "odyssey_project"
openai_client, gemini_model = None, None
# All tool functions (web_search, etc.) and initialize_clients remain the same.
def web_search(query: str) -> str:
    try:
        print(f"Tooling Specialist: Performing web search for '{query}'...")
        response = requests.get(f"https://html.duckduckgo.com/html/?q={query}", headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, 'html.parser')
        snippets = [p.get_text() for p in soup.find_all('a', class_='result__a')]
        return "Search Results:\n" + "\n".join(f"- {s}" for s in snippets[:5]) if snippets else "No results found."
    except Exception as e: return f"Error during web search: {e}"
def execute_shell_command(command: str, cwd: str = PROJECT_DIR) -> str: # CHRONOS UPGRADE: Accept CWD
    try:
        if "cd " in command: # CHRONOS UPGRADE: Handle cd command specially
            new_dir = command.split("cd ")[1].strip()
            target_path = os.path.join(cwd, new_dir)
            if os.path.isdir(target_path):
                return f"Successfully changed directory to {target_path}"
            else:
                return f"Error: Directory '{target_path}' not found."
        
        print(f"Tooling Specialist: Executing shell command `{command}` in `{cwd}`...")
        result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120)
        return f"$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e: return f"Error executing shell command: {e}"
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
def initialize_clients():
    global openai_client, gemini_model
    openai_key = os.getenv("OPENAI_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    if not openai_key: return "❌ Missing Secret: `OPENAI_API_KEY` not found.", False
    if not google_key: return "❌ Missing Secret: `GOOGLE_API_KEY` not found.", False
    try:
        openai_client = openai.OpenAI(api_key=openai_key)
        openai_client.models.list()
        genai.configure(api_key=google_key)
        # Note: We pass the tools to the model when we want to use them.
        gemini_model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")
        gemini_model.generate_content("ping")
        return "✅ All engines are online. Chronos awaits your command.", True
    except Exception as e: return f"❌ API Initialization Failed: {e}", False
def parse_json_from_string(text: str) -> dict or list:
    match = re.search(r'```json\s*([\s\S]*?)\s*```|([\s\S]*)', text)
    if match:
        json_str = match.group(1) or match.group(2)
        try: return json.loads(json_str.strip())
        except json.JSONDecodeError as e: raise ValueError(f"Failed to decode JSON. Error: {e}. Text: '{json_str[:200]}...'")
    raise ValueError("No JSON found.")

# --- THE "SUPER-TOOL" FOR THE TOOLING SPECIALIST ---
def execute_tooling_task(instruction: str, cwd: str):
    """Lets Gemini decide which tool to use and executes it."""
    # Create a temporary model instance with tools enabled
    tooling_model = genai.GenerativeModel(
        model_name="gemini-1.5-pro-latest",
        tools=[web_search, execute_shell_command, write_file, read_file]
    )
    response = tooling_model.generate_content(instruction)
    
    # Check if a function call was returned
    if not response.candidates or not response.candidates[0].content.parts or not response.candidates[0].content.parts[0].function_call:
        return f"Tooling Specialist decided no tool was necessary for: '{instruction}'.", cwd

    function_call = response.candidates[0].content.parts[0].function_call
    tool_name = function_call.name
    tool_args = dict(function_call.args)
    tool_function = globals()[tool_name]
    
    # CHRONOS UPGRADE: Manage current working directory state
    if tool_name == "execute_shell_command" and "cd " in tool_args.get("command", ""):
        new_dir = tool_args["command"].split("cd ")[1].strip()
        new_cwd = os.path.normpath(os.path.join(cwd, new_dir))
        if os.path.isdir(new_cwd):
            return f"Successfully changed directory to {new_cwd}", new_cwd
        else:
            return f"Error: Directory '{new_cwd}' not found.", cwd
    elif tool_name == "execute_shell_command":
        tool_args["cwd"] = cwd # Pass the current directory to the shell command

    result = tool_function(**tool_args)
    return result, cwd # Return the original cwd if not a cd command

# --- ODYSSEY ORCHESTRATOR (UPGRADED WITH CHRONOS LOGIC) ---
def run_odyssey(initial_prompt):
    mission_log = "Mission Log: [START]\n"
    yield mission_log, gr.update(choices=[])
    
    # Chronos State:
    current_working_directory = PROJECT_DIR
    
    # Phase 1: Architect (Gemini)
    mission_log += "Architect (Gemini): Analyzing user request and creating a step-by-step project plan...\n"
    yield mission_log, None
    
    architect_prompt = (
        "You are The Architect, an expert AI system designer. Create a logical, step-by-step plan for the user's goal. "
        "The plan MUST be a valid JSON array of tasks. Each task is an object with `agent` and `instruction` keys. "
        "CRITICAL AGENT ROLES: "
        "- Use 'Lead_Developer' for writing the application's source code files (e.g., .py, .js, .html, .css). "
        "- Use 'Tooling_Specialist' for ALL other actions: web searches, creating directories, and running shell commands like 'pip' or 'python'. "
        "Create efficient plans. For example, create all requirements in one step. Your entire response must be ONLY the raw JSON array."
    )
    gemini_json_config = genai.types.GenerationConfig(response_mime_type="application/json")
    try:
        response = gemini_model.generate_content(f"{architect_prompt}\n\nUser Goal: {initial_prompt}", generation_config=gemini_json_config)
        task_list = parse_json_from_string(response.text)
        mission_log += f"Architect: Plan generated with {len(task_list)} tasks.\n"
        yield mission_log, None
    except Exception as e:
        mission_log += f"Architect: [FATAL ERROR] Failed to create a valid plan. Reason: {e}\n"
        yield mission_log, None
        return

    # Phase 2: Execution Loop with Chronos State Management
    current_files = {}
    for i, task in enumerate(task_list):
        task_num = i + 1
        instruction = task['instruction']
        chosen_agent = task['agent']
        mission_log += f"\n--- Executing Task {task_num}/{len(task_list)} ---\n"
        mission_log += f"Engine: Delegating to `{chosen_agent}`. Instruction: `{instruction}`\n"
        yield mission_log, gr.update(choices=list(current_files.keys()))
        time.sleep(1)

        try:
            result = ""
            if chosen_agent == 'Lead_Developer':
                # CHRONOS UPGRADE: Broadened role for Lead Developer
                developer_prompt = (
                    "You are the Lead Developer (GPT-4o). Your task is to write the full content for a single application file as instructed. "
                    "This includes Python, JavaScript, HTML, CSS, Markdown, etc. "
                    "Your output MUST be a JSON object with a single key `code` containing the full, raw code."
                )
                response = openai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": developer_prompt},{"role": "user", "content": instruction}], response_format={"type": "json_object"})
                code_content = json.loads(response.choices[0].message.content)['code']
                
                file_path_prompt = "You are a file system manager. Based on the instruction, determine the correct relative file path (e.g., `src/app.py`). Respond with a JSON object with one key: `path`."
                response = gemini_model.generate_content(f"{file_path_prompt}\n\nInstruction: {instruction}", generation_config=gemini_json_config)
                file_path = parse_json_from_string(response.text)['path']
                
                result = write_file(file_path, code_content)
                mission_log += f"Lead Developer: Code generated. Result: {result}\n"
                current_files[file_path] = code_content
            
            elif chosen_agent == 'Tooling_Specialist':
                result, new_cwd = execute_tooling_task(instruction, current_working_directory)
                current_working_directory = new_cwd # Update state
                mission_log += f"Tooling Specialist Result:\n---\n{result}\n---\n"

            if "Error:" in result or "ERROR:" in result:
                mission_log += f"Engine: [TASK FAILED] An error occurred. Aborting mission.\n"
                yield mission_log, gr.update(choices=list(current_files.keys()))
                return

            yield mission_log, gr.update(choices=list(current_files.keys()))

        except Exception as e:
            mission_log += f"Engine: [FATAL ERROR] Task failed. Reason: {e}\nAborting mission.\n"
            yield mission_log, gr.update(choices=list(current_files.keys()))
            return

    mission_log += "\n--- Mission Complete ---"
    yield mission_log, gr.update(choices=list(current_files.keys()))

# --- GRADIO UI (No changes) ---
with gr.Blocks(theme=gr.themes.Default(primary_hue="orange", secondary_hue="blue"), title="Chronos Framework") as demo:
    gr.Markdown("# ⌛ Chronos: An AI Development Framework with State & Memory")
    status_bar = gr.Textbox("System Offline. Click 'Activate Engines' to begin.", label="System Status", interactive=False)
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ Controls")
            activate_btn = gr.Button("Activate Engines")
            gr.Markdown("### 🌳 Project Files")
            file_tree = gr.Radio(label="File System", interactive=True)
        with gr.Column(scale=3):
            gr.Markdown("### 📝 Mission Control")
            mission_prompt = gr.Textbox(label="High-Level Objective", placeholder="e.g., Build a Python Flask web app that generates a QR code from user text input.")
            launch_btn = gr.Button("🚀 Launch Mission", variant="primary", interactive=False)
            gr.Markdown("### 📜 Mission Log")
            mission_log_output = gr.Textbox(label="Live Log", lines=20, interactive=False, autoscroll=True)
    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    activate_btn.click(handle_activation, [], [status_bar, launch_btn])
    launch_btn.click(fn=run_odyssey, inputs=[mission_prompt], outputs=[mission_log_output, file_tree])

if __name__ == "__main__":
    demo.launch(debug=True)