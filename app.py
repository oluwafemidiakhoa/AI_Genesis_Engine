import gradio as gr
import openai
import google.generativeai as genai
import os
import json
import subprocess
import time
import re

# --- CONFIGURATION & STATE ---
PROJECT_DIR = "world_model_project"
openai_client, gemini_model = None, None

# The single source of truth for the AI's world
world_state = {"files": {}}

# --- TOOLS THAT MODIFY THE WORLD STATE ---
def write_file(path: str, content: str) -> str:
    """Writes content to a file and updates the world state."""
    global world_state
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Update world state
        path_parts = path.split('/')
        current_level = world_state["files"]
        for part in path_parts[:-1]:
            current_level = current_level.setdefault(part, {})
        current_level[path_parts[-1]] = content
        
        return f"Successfully wrote {len(content)} bytes to {path}."
    except Exception as e:
        return f"Error writing to file: {e}"

def run_shell_command(command: str) -> str:
    """Executes a shell command and updates the world state if it creates files/dirs."""
    global world_state
    try:
        # We can't easily track shell changes, so we'll rescan the file system after.
        result = subprocess.run(command, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=120)
        
        # Rescan and update world state
        new_file_state = {}
        for root, dirs, files in os.walk(PROJECT_DIR):
            path = root.split(os.sep)
            current_level = new_file_state
            for part in path[1:]:
                current_level = current_level.setdefault(part, {})
            for f in files:
                current_level[f] = "" # We don't read content for this simple update
        world_state["files"] = new_file_state
        
        return f"COMMAND:\n$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e:
        return f"Error executing shell command: {e}"

def step_complete(reason: str) -> str:
    """Marks a high-level step as complete."""
    return f"Step finished. Reason: {reason}"

# --- INITIALIZATION ---
def initialize_clients():
    global openai_client, gemini_model
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return "❌ Missing Secret: `OPENAI_API_KEY`", False
    try:
        openai_client = openai.OpenAI(api_key=openai_key)
        openai_client.models.list()
        return "✅ Engine Online. World Model is active.", True
    except Exception as e:
        return f"❌ API Initialization Failed: {e}", False

# --- THE WORLD MODEL ORCHESTRATOR ---
def run_world_model_mission(initial_prompt, max_steps=15):
    global world_state
    
    mission_log = "Mission Log: [START]\n"
    yield mission_log, json.dumps(world_state, indent=2)

    # Reset the world for a new mission
    if os.path.exists(PROJECT_DIR):
        import shutil
        shutil.rmtree(PROJECT_DIR)
    os.makedirs(PROJECT_DIR, exist_ok=True)
    world_state = {"files": {}}
    
    conversation = [
        {"role": "user", "content": f"Here is my objective: {initial_prompt}"}
    ]
    
    tools = [
        {"type": "function", "function": {"name": "write_file", "description": "Writes content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
        {"type": "function", "function": {"name": "run_shell_command", "description": "Executes a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "step_complete", "description": "Call this when the objective is complete.", "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}}
    ]
    
    for i in range(max_steps):
        # Inject the current world state into the system prompt
        system_prompt = (
            "You are an autonomous AI developer. Your goal is to achieve the user's objective by calling a sequence of functions. "
            "You have access to a file system and a shell. Think step-by-step. "
            "When you believe the objective is complete, call the `step_complete` function. "
            "Here is the current state of your file system:\n"
            f"```json\n{json.dumps(world_state, indent=2)}\n```"
        )
        
        messages = [{"role": "system", "content": system_prompt}] + conversation
        
        mission_log += f"\n--- Step {i+1}/{max_steps} ---\n"
        mission_log += "AI is thinking...\n"
        yield mission_log, json.dumps(world_state, indent=2)
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        response_message = response.choices[0].message
        conversation.append(response_message)
        
        if not response_message.tool_calls:
            break

        tool_responses = []
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            mission_log += f"Action: Calling `{function_name}` with args: {function_args}\n"
            yield mission_log, json.dumps(world_state, indent=2)
            
            if function_name == "step_complete":
                mission_log += f"Result: {function_args.get('reason')}\n--- MISSION COMPLETE ---"
                yield mission_log, json.dumps(world_state, indent=2)
                return
            
            tool_function = globals()[function_name]
            result = tool_function(**function_args)
            
            mission_log += f"Result: {result}\n"
            yield mission_log, json.dumps(world_state, indent=2)
            
            tool_responses.append({"tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": result})
        
        conversation.extend(tool_responses)

    mission_log += "\n--- Max steps reached. Mission concluding. ---"
    yield mission_log, json.dumps(world_state, indent=2)

# --- GRADIO UI ---
with gr.Blocks(theme=gr.themes.Monochrome(), title="World Model Framework") as demo:
    gr.Markdown("# 🤖 World Model: The Autonomous AI Developer")
    status_bar = gr.Textbox("System Offline. Click 'Activate Engine' to begin.", label="System Status", interactive=False)
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ Controls")
            activate_btn = gr.Button("Activate Engine")
            gr.Markdown("### 🌍 World State")
            world_state_view = gr.Code(label="File System View (JSON)", language="json", interactive=False)
        
        with gr.Column(scale=3):
            gr.Markdown("### 📝 Mission Control")
            mission_prompt = gr.Textbox(label="High-Level Objective", placeholder="Build a simple Flask app that returns the current time.")
            launch_btn = gr.Button("🚀 Launch Mission", variant="primary", interactive=False)
            gr.Markdown("### 📜 Mission Log")
            mission_log_output = gr.Textbox(label="Live Log", lines=25, interactive=False, autoscroll=True)

    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    
    activate_btn.click(handle_activation, [], [status_bar, launch_btn])
    launch_btn.click(fn=run_world_model_mission, inputs=[mission_prompt], outputs=[mission_log_output, world_state_view])

if __name__ == "__main__":
    demo.launch(debug=True)