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
PROJECT_DIR = "zeus_project"
openai_client, gemini_model = None, None
app_process = None

# --- TOOL DEFINITIONS ---
def write_file(path: str, content: str) -> str:
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f: f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}."
    except Exception as e: return f"Error writing to file: {e}"

def run_shell_command(command: str) -> str:
    try:
        result = subprocess.run(command, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=180)
        return f"COMMAND:\n$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e: return f"Error executing shell command: {e}"

def launch_server(command: str) -> str:
    global app_process
    if app_process: app_process.kill()
    try:
        app_process = subprocess.Popen(command, shell=True, cwd=PROJECT_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
        return f"Successfully launched server process with command: '{command}'."
    except Exception as e: return f"Error launching server: {e}"

def finish_mission(reason: str) -> str:
    return f"Mission finished. Reason: {reason}"

# --- INITIALIZATION ---
def initialize_clients():
    global openai_client, gemini_model
    openai_key = os.getenv("OPENAI_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    if not openai_key or not google_key: return "❌ Missing Secrets: Please set `OPENAI_API_KEY` and `GOOGLE_API_KEY`.", False
    try:
        openai_client = openai.OpenAI(api_key=openai_key)
        genai.configure(api_key=google_key)
        gemini_model = genai.GenerativeModel("gemini-1.5-pro-latest")
        return "✅ All engines online. The Zeus Framework is ready.", True
    except Exception as e: return f"❌ API Initialization Failed: {e}", False

# --- UTILITIES ---
def stream_process_output(process, queue):
    for line in iter(process.stdout.readline, ''): queue.put(line)
    process.stdout.close()

# --- THE ZEUS ORCHESTRATOR ---
def run_zeus_mission(initial_prompt, max_steps=40):
    global app_process
    mission_log = "[MISSION LOG: START]\n"
    yield mission_log, [], "", gr.update(visible=False, value=None)

    if os.path.exists(PROJECT_DIR): shutil.rmtree(PROJECT_DIR)
    os.makedirs(PROJECT_DIR, exist_ok=True)
    
    # --- PHASE 1: STRATEGY (GEMINI) ---
    mission_log += "--- Phase 1: Business & Product Strategy ---\n"
    mission_log += "The Strategist (Gemini): Analyzing business idea and formulating a Product Requirements Document (PRD)...\n"
    yield mission_log, [], "", None
    
    strategist_prompt = (
        "You are The Strategist, an AI with a PhD in Business and an expert in software product management. "
        "Take the user's simple idea and transform it into a sophisticated, viable product concept. "
        "Your output must be a detailed Product Requirements Document (PRD) in Markdown format. "
        "The PRD must include a final section titled exactly: '## High-Level Implementation Plan'."
    )
    try:
        response = gemini_model.generate_content(f"{strategist_prompt}\n\nUser Idea: {initial_prompt}")
        prd = response.text
        mission_log += f"The Strategist: PRD generated.\n---\n{prd}\n---\n"
        
        # ZEUS UPGRADE: More resilient regex to find the plan section
        plan_section_match = re.search(r'(?i)^\s*##\s*High-Level Implementation Plan\s*$([\s\S]*)', prd, re.MULTILINE)
        if not plan_section_match: raise ValueError("PRD does not contain a valid '## High-Level Implementation Plan' section.")
        
        plan_text = plan_section_match.group(1)
        plan = [step.strip() for step in plan_text.split('\n') if step.strip() and re.match(r'^\s*\d+\.', step.strip())]
        if not plan: raise ValueError("Implementation plan section is empty or incorrectly formatted.")
        
        yield mission_log, [], "", None
    except Exception as e:
        mission_log += f"The Strategist: [FATAL ERROR] Failed to create or parse a valid PRD. Reason: {e}\n"
        yield mission_log, [], "", None
        return

    # --- PHASE 2: EXECUTION (GPT-4o) ---
    mission_log += f"\n--- Phase 2: Engineering Sprint (Executing {len(plan)} steps) ---\n"
    
    conversation = [
        {"role": "system", "content": "You are The Executor, an elite autonomous AI developer. Your goal is to execute a high-level plan, step by step, using the tools provided. Think carefully and call the appropriate function for each step. When the entire plan is complete and the application is running, call `finish_mission`."},
        {"role": "user", "content": f"The full Product Requirements Document is:\n{prd}\n\n The implementation plan you must follow is:\n{json.dumps(plan, indent=2)}\n\nBegin with the first step."}
    ]
    
    tools = [
        {"type": "function", "function": {"name": "write_file", "description": "Writes content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
        {"type": "function", "function": {"name": "run_shell_command", "description": "Executes a short-lived command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "launch_server", "description": "Launches a long-running server process.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "finish_mission", "description": "Call this when the entire plan is complete.", "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}}
    ]

    for i in range(max_steps):
        mission_log += f"\n--- Step {i+1}/{max_steps} ---\nExecutor (GPT-4o) is thinking...\n"
        
        current_file_list = []
        for root, dirs, files in os.walk(PROJECT_DIR):
            for name in files: current_file_list.append(os.path.relpath(os.path.join(root, name), PROJECT_DIR))
            for name in dirs: current_file_list.append(os.path.relpath(os.path.join(root, name), PROJECT_DIR) + "/")
        yield mission_log, current_file_list, "", None

        try:
            response = openai_client.chat.completions.create(model="gpt-4o", messages=conversation, tools=tools, tool_choice="auto")
            response_message = response.choices[0].message
            conversation.append(response_message)
            
            if not response_message.tool_calls:
                mission_log += "Executor chose not to act. Concluding mission.\n"
                break

            tool_responses = []
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                mission_log += f"Action: Calling `{function_name}` with args: {function_args}\n"
                
                tool_function = globals()[function_name]
                result = tool_function(**function_args)
                mission_log += f"Result:\n---\n{result}\n---\n"
                
                if function_name == "finish_mission":
                    mission_log += "\n--- MISSION COMPLETE ---"
                    zip_path = os.path.join(PROJECT_DIR, "zeus_app.zip")
                    with zipfile.ZipFile(zip_path, 'w') as zf:
                        for root, _, files in os.walk(PROJECT_DIR):
                            for file in files:
                                if file != os.path.basename(zip_path): zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), PROJECT_DIR))
                    
                    terminal_text = ""
                    if app_process:
                        output_queue = Queue()
                        thread = threading.Thread(target=stream_process_output, args=(app_process, output_queue))
                        thread.daemon = True
                        thread.start()
                        time.sleep(3)
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
with gr.Blocks(theme=gr.themes.Soft(primary_hue="purple", secondary_hue="orange"), title="Zeus Framework") as demo:
    gr.Markdown("# ⚡ Zeus: The Autonomous AI Product Studio")
    status_bar = gr.Textbox("System Offline. Click 'Activate Engines' to begin.", label="System Status", interactive=False)
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ Controls")
            activate_btn = gr.Button("Activate Engines")
            gr.Markdown("### 🌳 Project Files")
            file_tree = gr.CheckboxGroup(label="File System", interactive=False)
            download_zip_btn = gr.DownloadButton(label="Download Venture as .zip", visible=False)
        
        with gr.Column(scale=3):
            gr.Markdown("### 💡 Venture Idea")
            mission_prompt = gr.Textbox(label="Describe your business or app idea", placeholder="e.g., A better to-do list app.", lines=3)
            launch_btn = gr.Button("🚀 Forge Venture", variant="primary", interactive=False)
            gr.Markdown("### 📜 Mission Log & Live Terminal")
            mission_log_output = gr.Textbox(label="Live Log", lines=20, interactive=False, autoscroll=True)
            live_terminal = gr.Textbox(label="Live App Terminal", lines=5, interactive=False, autoscroll=True)

    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    
    activate_btn.click(handle_activation, [], [status_bar, launch_btn])
    launch_btn.click(fn=run_zeus_mission, inputs=[mission_prompt], outputs=[mission_log_output, file_tree, live_terminal, download_zip_btn])

if __name__ == "__main__":
    demo.launch(debug=True)