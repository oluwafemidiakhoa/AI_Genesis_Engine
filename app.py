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
PROJECT_DIR = "metropolis_final"
openai_client, gemini_model = None, None
app_process = None

# --- TOOL DEFINITIONS (WITH LIVE SERVER & DOWNLOAD) ---
def write_file(path: str, content: str) -> str:
    """Writes or overwrites a file with the given content."""
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f: f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}."
    except Exception as e: return f"Error writing to file: {e}"

def run_shell_command(command: str) -> str:
    """Executes a short-lived shell command in the project directory."""
    try:
        result = subprocess.run(command, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=120)
        return f"COMMAND:\n$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e: return f"Error executing shell command: {e}"

def run_background_app(command: str) -> str:
    """Launches a long-running server process (like Flask) in the background."""
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
    """Declares the mission complete."""
    return f"Mission finished. Reason: {reason}"

# --- UTILITIES ---
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
        return "✅ All engines online. Metropolis is ready to build.", True
    except Exception as e: return f"❌ API Initialization Failed: {e}", False

def stream_process_output(process, queue):
    for line in iter(process.stdout.readline, ''):
        queue.put(line)
    process.stdout.close()

# --- THE METROPOLIS ORCHESTRATOR ---
def run_metropolis_mission(initial_prompt):
    mission_log = "Mission Log: [START]\n"
    yield mission_log, gr.update(choices=[]), "", gr.update(visible=False, value=None)

    if os.path.exists(PROJECT_DIR):
        shutil.rmtree(PROJECT_DIR)
    os.makedirs(PROJECT_DIR, exist_ok=True)
    
    # Phase 1: Architect creates the plan
    mission_log += "Architect (Gemini): Creating high-level product roadmap...\n"
    yield mission_log, None, None, None
    
    architect_prompt = (
        "You are The Architect. Create a high-level plan to build the user's requested application. "
        "The plan MUST be a numbered list of natural language steps. "
        "Separate UI design from implementation. A typical plan is: "
        "1. Design the UI. "
        "2. Implement the frontend HTML with Tailwind CSS. "
        "3. Implement the backend `app.py`. "
        "4. Create `requirements.txt`. "
        "5. Install dependencies. "
        "6. Launch the server using the `run_background_app` tool."
    )
    response = gemini_model.generate_content(f"{architect_prompt}\n\nUser Goal: {initial_prompt}")
    plan = [step.strip() for step in response.text.split('\n') if step.strip() and re.match(r'^\d+\.', step.strip())]
    
    if not plan:
        mission_log += "Architect: [FATAL ERROR] Failed to create a valid plan.\n"
        yield mission_log, None, None, None
        return
        
    mission_log += f"Architect: Plan generated with {len(plan)} steps.\n"
    yield mission_log, None, None, None

    # Phase 2: Execute the plan with specialized agents
    design_spec = ""
    for i, step_instruction in enumerate(plan):
        mission_log += f"\n--- Executing Step {i+1}/{len(plan)}: {step_instruction} ---\n"
        yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR) or ["(empty)"]), "", None
        time.sleep(1)
        
        agent_name = "Backend/Tooling Specialist" # Default agent
        if "design the ui" in step_instruction.lower(): agent_name = "UI/UX Designer"
        elif "implement the frontend" in step_instruction.lower(): agent_name = "Frontend Engineer"

        mission_log += f"Engine: Delegating to {agent_name}...\n"
        yield mission_log, None, None, None
        
        if agent_name == "UI/UX Designer":
            designer_prompt = "You are a world-class UI/UX Designer... (same as before)"
            response = gemini_model.generate_content(f"{designer_prompt}\n\nTask: {step_instruction}")
            design_spec = response.text
            mission_log += f"Designer's Spec:\n---\n{design_spec}\n---\n"
        elif agent_name == "Frontend Engineer":
            frontend_prompt = "You are an expert Frontend Engineer... (same as before)"
            context = f"Instruction: {step_instruction}\n\nDesign Specification:\n{design_spec}"
            response = openai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": frontend_prompt}, {"role": "user", "content": context}])
            code_content = response.choices[0].message.content.strip().replace("```html", "").replace("```", "")
            result = write_file("templates/index.html", code_content)
            mission_log += f"Frontend Engineer: Wrote `templates/index.html`. Result: {result}\n"
        else: # Backend/Tooling Agent
            conversation = [
                {"role": "system", "content": "You are an expert Backend Developer and Tooling Specialist. Execute the user's instruction by calling the appropriate function. Use `run_background_app` to start servers. Call `finish_mission` when the entire project is complete and running."},
                {"role": "user", "content": step_instruction}
            ]
            tools = [
                {"type": "function", "function": {"name": "write_file", "description": "Writes content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
                {"type": "function", "function": {"name": "run_shell_command", "description": "Executes a short-lived shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
                {"type": "function", "function": {"name": "run_background_app", "description": "Launches a long-running server process.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}
            ]
            response = openai_client.chat.completions.create(model="gpt-4o", messages=conversation, tools=tools, tool_choice="auto")
            response_message = response.choices[0].message
            if response_message.tool_calls:
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    result = globals()[function_name](**function_args)
                    mission_log += f"Backend/Tooling: Called `{function_name}`. Result: {result}\n"

        yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR) or ["(empty)"]), "", None

    mission_log += "\n--- MISSION COMPLETE ---"
    
    # Finalization: Prepare download and stream terminal output
    zip_path = os.path.join(PROJECT_DIR, "metropolis_app.zip")
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for root, _, files in os.walk(PROJECT_DIR):
            for file in files:
                if file != os.path.basename(zip_path):
                    zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), PROJECT_DIR))

    terminal_text = ""
    if app_process:
        mission_log += "\n--- Application is Running Live ---"
        output_queue = Queue()
        thread = threading.Thread(target=stream_process_output, args=(app_process, output_queue))
        thread.daemon = True
        thread.start()
        time.sleep(3) # Wait for server to boot
        while not output_queue.empty():
            terminal_text += output_queue.get()
    
    yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR) or ["(empty)"]), terminal_text, gr.update(visible=True, value=zip_path)

# --- GRADIO UI ---
with gr.Blocks(theme=gr.themes.Glass(), title="Metropolis Framework") as demo:
    gr.Markdown("# 🏙️ Metropolis: The Autonomous AI Product Studio")
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
            mission_prompt = gr.Textbox(label="High-Level Objective", placeholder="e.g., Build a beautiful, modern login page with a glassmorphism effect.")
            launch_btn = gr.Button("🚀 Launch Mission", variant="primary", interactive=False)
            gr.Markdown("### 📜 Mission Log & Live Terminal")
            mission_log_output = gr.Textbox(label="Live Log", lines=20, interactive=False, autoscroll=True)
            live_terminal = gr.Textbox(label="Live App Terminal", lines=5, interactive=False, autoscroll=True)

    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    
    activate_btn.click(handle_activation, [], [status_bar, launch_btn])
    launch_btn.click(fn=run_metropolis_mission, inputs=[mission_prompt], outputs=[mission_log_output, file_tree, live_terminal, download_zip_btn])

if __name__ == "__main__":
    demo.launch(debug=True)