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
PROJECT_DIR = "prometheus_v_project"
openai_client, gemini_model = None, None
app_process = None

# --- THE PROMETHEUS-V TOOLSET ---
def web_search(query: str) -> str:
    """Performs a web search to find libraries, APIs, or documentation."""
    # This can be expanded with a dedicated search API like Serper for more power
    try:
        search_model = genai.GenerativeModel("gemini-1.5-pro-latest")
        response = search_model.generate_content(f"Perform a web search for the following query and return a concise summary: {query}")
        return f"Web Search Summary:\n{response.text}"
    except Exception as e: return f"Error during web search: {e}"

def write_file(path: str, content: str) -> str:
    """Writes content to a file, creating directories as needed."""
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f: f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}."
    except Exception as e: return f"Error writing to file: {e}"

def run_shell_command(command: str) -> str:
    """Executes a short-lived shell command."""
    try:
        result = subprocess.run(command, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=180)
        return f"COMMAND:\n$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e: return f"Error executing shell command: {e}"

def launch_server(command: str) -> str:
    """Launches a long-running server process."""
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
    """Call this when the user's objective is fully complete."""
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
        openai_client.models.list()
        gemini_model.generate_content("ping")
        return "✅ All engines online. The Prometheus-V Venture Studio is ready.", True
    except Exception as e: return f"❌ API Initialization Failed: {e}", False

# --- UTILITIES ---
def stream_process_output(process, queue):
    for line in iter(process.stdout.readline, ''): queue.put(line)
    process.stdout.close()

# --- THE PROMETHEUS-V ORCHESTRATOR ---
def run_venture_mission(initial_prompt, max_steps=30):
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
        "The PRD must include sections for: "
        "1. **Product Vision:** A compelling, ambitious vision for the product. "
        "2. **Key Features:** A list of core features that provide a competitive advantage. "
        "3. **Recommended Tech Stack:** Suggest a professional, modern tech stack (e.g., FastAPI, React/Next.js, Tailwind CSS, PostgreSQL). "
        "4. **Monetization Strategy:** Propose a viable business model (e.g., Freemium, Subscription, Tiered Pricing). "
        "5. **High-Level Implementation Plan:** A natural language, numbered list of the major engineering steps required to build the MVP."
    )
    try:
        response = gemini_model.generate_content(f"{strategist_prompt}\n\nUser Idea: {initial_prompt}")
        prd = response.text
        mission_log += f"The Strategist: PRD generated.\n---\n{prd}\n---\n"
        
        # Extract the implementation plan from the PRD
        plan_section = re.search(r'High-Level Implementation Plan\s*\n-*\s*([\s\S]*)', prd, re.IGNORECASE)
        if not plan_section: raise ValueError("PRD does not contain a valid 'High-Level Implementation Plan' section.")
        plan = [step.strip() for step in plan_section.group(1).split('\n') if step.strip() and re.match(r'^\d+\.', step.strip())]
        if not plan: raise ValueError("Implementation plan is empty or incorrectly formatted.")
        
        yield mission_log, [], "", None
    except Exception as e:
        mission_log += f"The Strategist: [FATAL ERROR] Failed to create a valid PRD. Reason: {e}\n"
        yield mission_log, [], "", None
        return

    # --- PHASE 2: EXECUTION (GPT-4o) ---
    mission_log += "\n--- Phase 2: Engineering Sprint ---\n"
    
    for i, step_instruction in enumerate(plan):
        mission_log += f"\n--- Executing Plan Step {i+1}/{len(plan)}: {step_instruction} ---\n"
        yield mission_log, os.listdir(PROJECT_DIR) or [], "", None
        
        # The Master Craftsman Loop
        conversation = [
            {"role": "system", "content": "You are a Master Craftsman, an elite AI full-stack developer. Your goal is to complete the user's high-level instruction by calling a sequence of functions. When the instruction is fully complete, you MUST call `step_complete`."},
            {"role": "user", "content": f"Full Product Plan (for context):\n{prd}\n\nYour current task:\n{step_instruction}"}
        ]
        tools = [
            {"type": "function", "function": {"name": "web_search", "description": "Searches the web for information.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
            {"type": "function", "function": {"name": "write_file", "description": "Writes content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
            {"type": "function", "function": {"name": "run_shell_command", "description": "Executes a short-lived command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
            {"type": "function", "function": {"name": "launch_server", "description": "Launches a long-running server process.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
            {"type": "function", "function": {"name": "step_complete", "description": "Call this when the current high-level step is finished.", "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}}
        ]

        for _ in range(15): # Max 15 tool calls per step
            response = openai_client.chat.completions.create(model="gpt-4o", messages=conversation, tools=tools, tool_choice="auto")
            response_message = response.choices[0].message
            conversation.append(response_message)
            
            if not response_message.tool_calls:
                mission_log += "Craftsman: Decided to end step without calling `step_complete`.\n"
                break

            tool_responses = []
            for tool_call in response_message.tool_calls:
                function_name, function_args = tool_call.function.name, json.loads(tool_call.function.arguments)
                mission_log += f"Craftsman: Calling tool `{function_name}` with args: {function_args}\n"
                
                if function_name == "step_complete":
                    mission_log += f"Craftsman: Step finished. Reason: {function_args.get('reason')}\n"
                    break # Exit the inner tool-calling loop
                
                tool_function = globals()[function_name]
                result = tool_function(**function_args)
                mission_log += f"Tool Result: {result}\n"
                tool_responses.append({"tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": result})
            
            conversation.extend(tool_responses)

            if any(call.function.name == 'step_complete' for call in response_message.tool_calls):
                break # Exit outer loop if step is complete
        else: # This runs if the inner loop finishes without a break
             mission_log += f"Craftsman: Max tool calls reached for this step. Moving on.\n"

        yield mission_log, os.listdir(PROJECT_DIR) or [], "", None

    mission_log += "\n--- MISSION COMPLETE ---"
    
    zip_path = os.path.join(PROJECT_DIR, "prometheus_v_app.zip")
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for root, _, files in os.walk(PROJECT_DIR):
            for file in files:
                if file != os.path.basename(zip_path):
                    zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), PROJECT_DIR))
    
    terminal_text = ""
    if app_process:
        mission_log += "\n--- Application is Running Live ---\n"
        output_queue = Queue()
        thread = threading.Thread(target=stream_process_output, args=(app_process, output_queue))
        thread.daemon = True
        thread.start()
        time.sleep(3)
        while not output_queue.empty(): terminal_text += output_queue.get()
    
    yield mission_log, os.listdir(PROJECT_DIR) or [], terminal_text, gr.update(visible=True, value=zip_path)


# --- GRADIO UI ---
with gr.Blocks(theme=gr.themes.Soft(primary_hue="purple", secondary_hue="orange"), title="Prometheus-V Framework") as demo:
    gr.Markdown("# 🔥 Prometheus-V: The AI Venture Studio")
    status_bar = gr.Textbox("System Offline. Click 'Activate Engines' to begin.", label="System Status", interactive=False)
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ Controls")
            activate_btn = gr.Button("Activate Engines")
            gr.Markdown("### 🌳 Project Files")
            file_tree = gr.Radio(label="File System", interactive=True, value=None)
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
    launch_btn.click(fn=run_venture_mission, inputs=[mission_prompt], outputs=[mission_log_output, file_tree, live_terminal, download_zip_btn])

if __name__ == "__main__":
    demo.launch(debug=True)