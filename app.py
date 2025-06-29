import gradio as gr
import openai
import google.generativeai as genai
import os
import json
import subprocess
import time

# --- CONFIGURATION & STATE ---
PROJECT_DIR = "helios_reborn_project"
openai_client, gemini_model = None, None

# --- TOOL DEFINITIONS ---
# These are the actions the AI can take.
def list_files(path: str = ".") -> str:
    """Lists all files and directories in a given path within the project."""
    full_path = os.path.join(PROJECT_DIR, path)
    if not os.path.isdir(full_path):
        os.makedirs(full_path, exist_ok=True)
    try:
        files = os.listdir(full_path)
        return "\n".join(files) if files else "(empty directory)"
    except Exception as e: return f"Error listing files: {e}"

def write_file(path: str, content: str) -> str:
    """Writes or overwrites a file with the given content."""
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f: f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}."
    except Exception as e: return f"Error writing to file: {e}"

def run_shell_command(command: str) -> str:
    """Executes a shell command in the project directory."""
    try:
        result = subprocess.run(command, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=120)
        return f"COMMAND:\n$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e: return f"Error executing shell command: {e}"

def step_complete(reason: str) -> str:
    """Call this function when you believe the current step's instruction is fully completed."""
    return f"Step marked as complete. Reason: {reason}"

# --- INITIALIZATION ---
def initialize_clients():
    global openai_client, gemini_model
    openai_key = os.getenv("OPENAI_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    if not openai_key or not google_key:
        return "❌ Missing Secrets: Please set `OPENAI_API_KEY` and `GOOGLE_API_KEY` in repository secrets.", False
    try:
        openai_client = openai.OpenAI(api_key=openai_key)
        openai_client.models.list()
        genai.configure(api_key=google_key)
        gemini_model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")
        gemini_model.generate_content("ping")
        return "✅ All engines online. Helios Reborn awaits your command.", True
    except Exception as e: return f"❌ API Initialization Failed: {e}", False

# --- THE MASTER CRAFTSMAN (INNER LOOP) ---
def execute_step(step_instruction: str, mission_log: str):
    """Executes a single high-level step using GPT-4o in a tool-calling loop."""
    mission_log += f"Master Craftsman (GPT-4o): Starting task: '{step_instruction}'\n"
    
    conversation = [
        {
            "role": "system",
            "content": (
                "You are a Master Craftsman, an expert AI developer. Your goal is to complete the user's high-level instruction by calling a sequence of functions. "
                "Think step-by-step. You can call multiple tools in one turn if needed. "
                "When you are confident the instruction is fully complete, you MUST call the `step_complete` function."
            )
        },
        {"role": "user", "content": step_instruction}
    ]
    
    tools = [
        {"type": "function", "function": {"name": "list_files", "description": "Lists files in a directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
        {"type": "function", "function": {"name": "write_file", "description": "Writes content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
        {"type": "function", "function": {"name": "run_shell_command", "description": "Executes a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "step_complete", "description": "Call this when the current high-level step is finished.", "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}}
    ]
    
    for _ in range(10): # Max 10 tool calls per step
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=conversation,
            tools=tools,
            tool_choice="auto"
        )
        response_message = response.choices[0].message
        conversation.append(response_message)
        
        if not response_message.tool_calls:
            mission_log += "Craftsman: Decided to end step without calling `step_complete`.\n"
            return mission_log, False # Step failed

        tool_responses = []
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            mission_log += f"Craftsman: Calling tool `{function_name}` with args: {function_args}\n"
            
            if function_name == "step_complete":
                mission_log += f"Craftsman: Step finished. Reason: {function_args.get('reason')}\n"
                return mission_log, True # Step succeeded
            
            tool_function = globals()[function_name]
            result = tool_function(**function_args)
            mission_log += f"Tool Result: {result}\n"
            
            tool_responses.append(
                {"tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": result}
            )
        
        conversation.extend(tool_responses) # Add all tool responses to the conversation

    mission_log += "Craftsman: Max tool calls reached for this step. Moving on.\n"
    return mission_log, False # Step failed

# --- THE HELIOS REBORN ORCHESTRATOR (OUTER LOOP) ---
def run_helios_reborn_mission(initial_prompt):
    mission_log = "Mission Log: [START]\n"
    yield mission_log, gr.update(choices=[])

    if os.path.exists(PROJECT_DIR):
        import shutil
        shutil.rmtree(PROJECT_DIR)
    os.makedirs(PROJECT_DIR, exist_ok=True)
    
    # Phase 1: Architect (Gemini) creates the natural language plan
    mission_log += "Architect (Gemini): Creating high-level project plan...\n"
    yield mission_log, None
    
    architect_prompt = (
        "You are The Architect. Create a high-level, logical, step-by-step plan in natural language to achieve the user's goal. "
        "Do not write code. Just provide a numbered list of instructions for an expert developer to follow. "
        "For example: 1. Create the main application file `app.py`. 2. Add Flask boilerplate to `app.py`... etc."
    )
    response = gemini_model.generate_content(f"{architect_prompt}\n\nUser Goal: {initial_prompt}")
    plan = [step.strip() for step in response.text.split('\n') if step.strip() and re.match(r'^\d+\.', step.strip())]
    
    if not plan:
        mission_log += "Architect: [FATAL ERROR] Failed to create a valid plan.\n"
        yield mission_log, None
        return
        
    mission_log += f"Architect: Plan generated with {len(plan)} steps.\n"
    yield mission_log, None

    # Phase 2: Orchestrator executes the plan step-by-step
    for i, step_instruction in enumerate(plan):
        mission_log += f"\n--- Executing Plan Step {i+1}/{len(plan)} ---\n"
        yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR) or ["(empty)"])
        
        mission_log, success = execute_step(step_instruction, mission_log)
        
        if not success:
            mission_log += f"Engine: [MISSION FAILED] The Master Craftsman could not complete step {i+1}. Aborting.\n"
            yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR) or ["(empty)"])
            return
            
        yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR) or ["(empty)"])

    mission_log += "\n--- MISSION COMPLETE ---"
    yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR) or ["(empty)"])


# --- GRADIO UI ---
with gr.Blocks(theme=gr.themes.Soft(primary_hue="sky", secondary_hue="blue"), title="Helios Reborn") as demo:
    gr.Markdown("# ☀️ Helios Reborn: The Autonomous AI Developer")
    status_bar = gr.Textbox("System Offline. Click 'Activate Engines' to begin.", label="System Status", interactive=False)
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ Controls")
            activate_btn = gr.Button("Activate Engines")
            gr.Markdown("### 🌳 Project Files")
            file_tree = gr.Radio(label="File System", interactive=True)
        
        with gr.Column(scale=3):
            gr.Markdown("### 📝 Mission Control")
            mission_prompt = gr.Textbox(label="High-Level Objective", placeholder="Build a simple Flask app that returns the current time as a JSON object.")
            launch_btn = gr.Button("🚀 Launch Mission", variant="primary", interactive=False)
            gr.Markdown("### 📜 Mission Log")
            mission_log_output = gr.Textbox(label="Live Log", lines=25, interactive=False, autoscroll=True)

    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    
    activate_btn.click(handle_activation, [], [status_bar, launch_btn])
    launch_btn.click(fn=run_helios_reborn_mission, inputs=[mission_prompt], outputs=[mission_log_output, file_tree])

if __name__ == "__main__":
    demo.launch(debug=True)