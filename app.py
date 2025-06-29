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

# --- CONFIGURATION & STATE ---
PROJECT_DIR = "odyssey_project"
openai_client, gemini_model = None, None

# --- TOOLS (No changes) ---
def web_search(query: str) -> str:
    try:
        print(f"Tooling Specialist: Performing web search for '{query}'...")
        response = requests.get(f"https://html.duckduckgo.com/html/?q={query}", headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, 'html.parser')
        snippets = [p.get_text() for p in soup.find_all('a', class_='result__a')]
        return "Search Results:\n" + "\n".join(f"- {s}" for s in snippets[:5]) if snippets else "No results found."
    except Exception as e: return f"Error during web search: {e}"

def execute_shell_command(command: str) -> str:
    try:
        if not os.path.exists(PROJECT_DIR): os.makedirs(PROJECT_DIR)
        print(f"Tooling Specialist: Executing shell command `{command}`...")
        result = subprocess.run(command, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=120)
        return f"$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e: return f"Error executing shell command: {e}"

def write_file(path: str, content: str) -> str:
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        print(f"Tooling Specialist: Writing to file `{full_path}`...")
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f: f.write(content)
        return f"Successfully wrote to {path}."
    except Exception as e: return f"Error writing to file: {e}"

def read_file(path: str) -> str:
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        with open(full_path, 'r', encoding='utf-8') as f: return f.read()
    except Exception as e: return f"Error reading file: {e}"


# --- API & AGENT INITIALIZATION (No changes from last version) ---
def initialize_clients():
    global openai_client, gemini_model
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return "❌ Missing Secret: `OPENAI_API_KEY` not found.", False
    google_key = os.getenv("GOOGLE_API_KEY")
    if not google_key:
        return "❌ Missing Secret: `GOOGLE_API_KEY` not found.", False
    try:
        openai_client = openai.OpenAI(api_key=openai_key)
        openai_client.models.list()
        genai.configure(api_key=google_key)
        gemini_model = genai.GenerativeModel(
            model_name="gemini-1.5-pro-latest",
            tools=[web_search, execute_shell_command, write_file, read_file]
        )
        gemini_model.generate_content("ping", generation_config=genai.types.GenerationConfig(max_output_tokens=5))
        return "✅ All engines are online. The Odyssey awaits your command.", True
    except Exception as e:
        return f"❌ API Initialization Failed: {e}", False

# --- UTILITY FUNCTION FOR RESILIENT PARSING ---
def parse_json_from_string(text: str) -> dict or list:
    """Finds and parses the first valid JSON object or array in a string."""
    # Regex to find content between ```json and ``` or the first `{` or `[` to the last `}` or `]`
    match = re.search(r'```json\s*([\s\S]*?)\s*```|([\s\S]*)', text)
    if match:
        json_str = match.group(1) or match.group(2)
        try:
            return json.loads(json_str.strip())
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to decode JSON after extraction. Error: {e}. Extracted text: '{json_str[:200]}...'")
    raise ValueError("No JSON object or array found in the AI response.")


# --- ODYSSEY ORCHESTRATOR (UPGRADED WITH AEGIS PROTOCOL) ---
def run_odyssey(initial_prompt):
    if not openai_client or not gemini_model:
        yield "Mission Log: [ERROR] API clients not initialized. Activate the engines first.", None
        return

    mission_log = "Mission Log: [START]\n"
    yield mission_log, gr.update(choices=[])
    
    # Phase 1: Architect (Gemini) creates the plan with AEGIS protocol
    mission_log += "Architect (Gemini): Analyzing user request and creating a step-by-step project plan...\n"
    yield mission_log, None
    
    # UPGRADE: More robust prompt
    architect_prompt = (
        "You are The Architect, an expert AI system designer. Your ONLY task is to create a step-by-step plan for the user's goal. "
        "The plan MUST be a valid JSON array of tasks. Each task is an object with two keys: `agent` (either 'Lead_Developer' or 'Tooling_Specialist') "
        "and `instruction` (a clear command for that agent). "
        "CRITICAL: Do NOT output any text, explanations, or markdown fences like ```json. Your entire response must be ONLY the raw JSON array, starting with `[` and ending with `]`."
    )
    
    # UPGRADE: Enforce JSON response from the API
    gemini_json_config = genai.types.GenerationConfig(
        response_mime_type="application/json"
    )
    
    try:
        response = gemini_model.generate_content(
            f"{architect_prompt}\n\nUser Goal: {initial_prompt}",
            generation_config=gemini_json_config
        )
        # UPGRADE: Use the resilient parser
        task_list = parse_json_from_string(response.text)
        mission_log += f"Architect: Plan generated with {len(task_list)} tasks.\n"
        yield mission_log, None
    except Exception as e:
        mission_log += f"Architect: [FATAL ERROR] Failed to create a valid plan. Reason: {e}\n"
        yield mission_log, None
        return

    # Phase 2: Execution Loop (No changes needed here, the logic is sound)
    current_files = {}
    for i, task in enumerate(task_list):
        task_num = i + 1
        mission_log += f"\n--- Executing Task {task_num}/{len(task_list)} ---\n"
        mission_log += f"Engine: Delegating to `{task['agent']}` with instruction: `{task['instruction']}`\n"
        yield mission_log, gr.update(choices=list(current_files.keys()))
        time.sleep(1)
        
        try:
            if task['agent'] == 'Lead_Developer':
                developer_prompt = (
                    "You are the Lead Developer, an expert coder using GPT-4o. Write the code as instructed. "
                    "Your output MUST be a JSON object with a single key `code` containing the full, raw code."
                )
                response = openai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": developer_prompt},{"role": "user", "content": task['instruction']}], response_format={"type": "json_object"})
                code_content = json.loads(response.choices[0].message.content)['code']
                
                file_path_prompt = (
                    "You are a file system manager. Based on the instruction and code, determine the correct file path. "
                    "Respond with a JSON object with one key: `path`."
                )
                response = gemini_model.generate_content(f"{file_path_prompt}\n\nInstruction: {task['instruction']}\n\nCode:\n{code_content}", generation_config=gemini_json_config)
                file_path = parse_json_from_string(response.text)['path']
                result = write_file(file_path, code_content)
                mission_log += f"Lead Developer: Code generated. Result: {result}\n"
                current_files[file_path] = code_content
            
            elif task['agent'] == 'Tooling_Specialist':
                response = gemini_model.generate_content(task['instruction'])
                function_call = response.candidates[0].content.parts[0].function_call
                tool_name = function_call.name
                tool_args = dict(function_call.args)
                tool_function = globals()[tool_name]
                result = tool_function(**tool_args)
                mission_log += f"Tooling Specialist: Executed `{tool_name}`. Result:\n---\n{result}\n---\n"
            
            yield mission_log, gr.update(choices=list(current_files.keys()))

        except Exception as e:
            mission_log += f"Engine: [FATAL ERROR] Task failed. Reason: {e}\nAborting mission.\n"
            yield mission_log, gr.update(choices=list(current_files.keys()))
            return

    mission_log += "\n--- Mission Complete ---"
    yield mission_log, gr.update(choices=list(current_files.keys()))

# --- GRADIO UI (No changes) ---
with gr.Blocks(theme=gr.themes.Default(primary_hue="orange", secondary_hue="blue"), title="Odyssey Framework") as demo:
    gr.Markdown("# 🚀 Odyssey: An Autonomous AI Software Development Framework")
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
            launch_btn = gr.Button("🚀 Launch Odyssey", variant="primary", interactive=False)
            
            gr.Markdown("### 📜 Mission Log")
            mission_log_output = gr.Textbox(label="Live Log", lines=20, interactive=False, autoscroll=True)

    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    
    activate_btn.click(handle_activation, [], [status_bar, launch_btn])
    
    launch_btn.click(
        fn=run_odyssey,
        inputs=[mission_prompt],
        outputs=[mission_log_output, file_tree]
    )

if __name__ == "__main__":
    demo.launch(debug=True)