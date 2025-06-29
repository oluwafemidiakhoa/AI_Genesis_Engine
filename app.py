import gradio as gr
import openai
import google.generativeai as genai
import os
import json
import subprocess
import requests
from bs4 import BeautifulSoup
import time

# --- CONFIGURATION & STATE ---
PROJECT_DIR = "odyssey_project"
# Clients will be initialized after keys are provided
openai_client, gemini_model = None, None

# --- TOOL DEFINITIONS FOR THE TOOLING SPECIALIST ---
def web_search(query: str) -> str:
    """Performs a web search using DuckDuckGo and returns the top results' text content."""
    try:
        print(f"Tooling Specialist: Performing web search for '{query}'...")
        response = requests.get(f"https://html.duckduckgo.com/html/?q={query}", headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        snippets = [p.get_text() for p in soup.find_all('a', class_='result__a')]
        return "Search Results:\n" + "\n".join(f"- {s}" for s in snippets[:5]) if snippets else "No results found."
    except Exception as e:
        return f"Error during web search: {e}"

def execute_shell_command(command: str) -> str:
    """Executes a shell command in the project directory and captures its output."""
    try:
        if not os.path.exists(PROJECT_DIR): os.makedirs(PROJECT_DIR)
        print(f"Tooling Specialist: Executing shell command `{command}`...")
        result = subprocess.run(command, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=120)
        output = f"$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        return output
    except Exception as e:
        return f"Error executing shell command: {e}"

def write_file(path: str, content: str) -> str:
    """Writes or overwrites a file in the project directory."""
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        print(f"Tooling Specialist: Writing to file `{full_path}`...")
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {path}."
    except Exception as e:
        return f"Error writing to file: {e}"

def read_file(path: str) -> str:
    """Reads the content of a file from the project directory."""
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Error: File not found."
    except Exception as e:
        return f"Error reading file: {e}"

# --- API & AGENT INITIALIZATION ---
def initialize_clients(openai_key, google_key):
    global openai_client, gemini_model
    try:
        openai_client = openai.OpenAI(api_key=openai_key)
        openai_client.models.list() # Test call
        genai.configure(api_key=google_key)
        gemini_model = genai.GenerativeModel(
            model_name="gemini-1.5-pro-latest",
            tools=[web_search, execute_shell_command, write_file, read_file] # Register tools with Gemini
        )
        return "✅ All clients initialized successfully. The Odyssey awaits your command.", True
    except Exception as e:
        return f"❌ API Initialization Failed: {e}", False

# --- THE ODYSSEY ORCHESTRATOR ---
def run_odyssey(initial_prompt):
    if not openai_client or not gemini_model:
        yield "Mission Log: [ERROR] API clients not initialized. Please enter valid keys.", None
        return

    mission_log = "Mission Log: [START]\n"
    yield mission_log, gr.update(choices=[])

    # 1. Architect Agent (Gemini) creates the plan
    mission_log += "Architect (Gemini): Analyzing user request and creating a step-by-step project plan...\n"
    yield mission_log, None
    architect_prompt = (
        "You are The Architect, a world-class AI system designer. Your job is to take a user's high-level goal and break it down into a detailed, "
        "step-by-step plan. The plan should be a JSON array of tasks. Each task must be an object with two keys: "
        "`agent` (either 'Lead_Developer' for writing app code, or 'Tooling_Specialist' for using tools) and `instruction` "
        "(a clear, specific command for that agent). Be logical and thorough. For example, search for libraries before using them, "
        "and install dependencies before running code. Output ONLY the raw JSON array."
    )
    try:
        response = gemini_model.generate_content(f"{architect_prompt}\n\nUser Goal: {initial_prompt}")
        task_list = json.loads(response.text)
        mission_log += f"Architect: Plan generated with {len(task_list)} tasks.\n"
        yield mission_log, None
    except Exception as e:
        mission_log += f"Architect: [FATAL ERROR] Failed to create a valid plan. Reason: {e}\n"
        yield mission_log, None
        return

    # 2. Execute the plan task by task
    current_files = {}
    for i, task in enumerate(task_list):
        task_num = i + 1
        mission_log += f"\n--- Executing Task {task_num}/{len(task_list)} ---\n"
        mission_log += f"Engine: Delegating to `{task['agent']}` with instruction: `{task['instruction']}`\n"
        yield mission_log, None
        time.sleep(1)

        try:
            if task['agent'] == 'Lead_Developer':
                # Delegate to GPT-4o for coding
                developer_prompt = (
                    "You are the Lead Developer, an expert coder using GPT-4o. Your task is to write the code as instructed. "
                    "Your output MUST be a JSON object containing a single key `code` with the full, raw code as its value. "
                    "Do not add any explanations or other text. Just the JSON."
                )
                response = openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": developer_prompt},
                        {"role": "user", "content": task['instruction']}
                    ],
                    response_format={"type": "json_object"}
                )
                code_content = json.loads(response.choices[0].message.content)['code']
                
                # We need to ask Gemini where to save this code
                file_path_prompt = (
                    "You are a file system manager. Based on the user instruction and the generated code, determine the correct file path to save this code to. "
                    "Respond with a JSON object with one key: `path`. For example: {\"path\": \"src/main.py\"}."
                )
                response = gemini_model.generate_content(f"{file_path_prompt}\n\nInstruction: {task['instruction']}\n\nCode:\n{code_content}")
                file_path = json.loads(response.text)['path']
                
                # Use the Tooling Specialist to save the file
                result = write_file(file_path, code_content)
                mission_log += f"Lead Developer: Code generated. Result: {result}\n"
                current_files[file_path] = code_content
            
            elif task['agent'] == 'Tooling_Specialist':
                # Delegate to Gemini with function calling
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


# --- GRADIO UI ---
with gr.Blocks(theme=gr.themes.Default(primary_hue="orange", secondary_hue="blue"), title="Odyssey Framework") as demo:
    gr.Markdown("# 🚀 Odyssey: An Autonomous AI Software Development Framework")
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 🔑 API Credentials")
            openai_key_input = gr.Textbox(label="OpenAI API Key", type="password")
            google_key_input = gr.Textbox(label="Google AI Studio Key", type="password")
            activate_btn = gr.Button("Activate Engines")
            
            gr.Markdown("### 🌳 Project Files")
            file_tree = gr.Radio(label="File System", interactive=True)

        with gr.Column(scale=3):
            gr.Markdown("### 📝 Mission Control")
            mission_prompt = gr.Textbox(label="High-Level Objective", placeholder="e.g., Build a Python Flask web app that generates a QR code from user text input.")
            launch_btn = gr.Button("🚀 Launch Odyssey", variant="primary", interactive=False)
            
            gr.Markdown("### 📜 Mission Log")
            mission_log_output = gr.Textbox(label="Live Log", lines=20, interactive=False, autoscroll=True)

    def handle_activation(openai_key, google_key):
        message, success = initialize_clients(openai_key, google_key)
        return {
            status_bar: gr.update(value=message),
            launch_btn: gr.update(interactive=success)
        }
    
    status_bar = gr.Textbox("", label="System Status", interactive=False)
    activate_btn.click(handle_activation, [openai_key_input, google_key_input], [status_bar, launch_btn])
    
    launch_btn.click(
        fn=run_odyssey,
        inputs=[mission_prompt],
        outputs=[mission_log_output, file_tree]
    )

if __name__ == "__main__":
    demo.launch(debug=True)