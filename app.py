import gradio as gr
import openai
import os
import json
import subprocess
import time

# --- CONFIGURATION & STATE ---
PROJECT_DIR = "singularity_project"
openai_client = None

# --- THE SINGULARITY TOOLSET: Simple, direct functions ---
def list_files(path: str = ".") -> str:
    """Lists all files and directories in a given path within the project."""
    full_path = os.path.join(PROJECT_DIR, path)
    if not os.path.isdir(full_path):
        os.makedirs(full_path, exist_ok=True) # Create if it doesn't exist
    try:
        return "\n".join(os.listdir(full_path)) or "(empty directory)"
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

def finish_mission(reason: str) -> str:
    """Declares the mission complete."""
    return f"Mission finished. Reason: {reason}"

# --- INITIALIZATION (Reads from Environment) ---
def initialize_clients():
    """Reads the OpenAI API key from environment secrets and initializes the client."""
    global openai_client
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return "❌ Missing Secret: `OPENAI_API_KEY` not found in repository secrets. Please add it and restart the Space.", False
    try:
        openai_client = openai.OpenAI(api_key=openai_key)
        openai_client.models.list() # Test call to verify the key is valid
        return "✅ Engine Online. Singularity is ready.", True
    except openai.AuthenticationError:
        return "❌ OpenAI Authentication Error: The provided API key is invalid.", False
    except Exception as e:
        return f"❌ API Initialization Failed: {e}", False

# --- THE SINGULARITY ORCHESTRATOR ---
def run_singularity_mission(initial_prompt, max_steps=25):
    if not openai_client:
        yield "Mission Log: [ERROR] API client not initialized. Activate the engine first.", gr.update(choices=[])
        return

    # Clean and create project directory for a fresh run
    if os.path.exists(PROJECT_DIR):
        import shutil
        shutil.rmtree(PROJECT_DIR)
    os.makedirs(PROJECT_DIR, exist_ok=True)
    
    conversation = [
        {
            "role": "system",
            "content": (
                "You are an autonomous AI software developer. Your goal is to achieve the user's objective by calling a sequence of functions. "
                "You have access to a file system and a shell. Think step-by-step. "
                "1. First, understand the goal. `list_files` to see the current state (it will be empty). "
                "2. Then, write the necessary code file(s) using `write_file`. "
                "3. If dependencies are needed, write a `requirements.txt` file. "
                "4. Then, run `run_shell_command` to `pip install -r requirements.txt`. "
                "5. Finally, `run_shell_command` to execute the code (e.g., `python app.py`). "
                "When you believe the user's goal is complete, call the `finish_mission` function."
            )
        },
        {"role": "user", "content": f"Here is my objective: {initial_prompt}"}
    ]
    
    tools = [
        {"type": "function", "function": {"name": "list_files", "description": "Lists files in a directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "The path to list relative to the project root."}}}}},
        {"type": "function", "function": {"name": "write_file", "description": "Writes content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
        {"type": "function", "function": {"name": "run_shell_command", "description": "Executes a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {"name": "finish_mission", "description": "Call this when the objective is complete.", "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}}
    ]
    
    mission_log = "Mission Log: [START]\n"
    yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR))

    for i in range(max_steps):
        mission_log += f"\n--- Step {i+1}/{max_steps} ---\n"
        mission_log += "Singularity is thinking...\n"
        yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR))
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=conversation,
                tools=tools,
                tool_choice="auto"
            )
            response_message = response.choices[0].message
            conversation.append(response_message)
            
            if not response_message.tool_calls:
                mission_log += "AI chose not to call a tool. Finishing mission due to inactivity.\n"
                break

            tool_call = response_message.tool_calls[0]
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            mission_log += f"Action: Calling function `{function_name}` with args: {function_args}\n"
            yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR))
            
            if function_name == "finish_mission":
                mission_log += f"Result: {function_args.get('reason')}\n--- MISSION COMPLETE ---"
                yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR))
                return

            tool_function = globals()[function_name]
            result = tool_function(**function_args)
            
            mission_log += f"Result:\n---\n{result}\n---\n"
            yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR))

            conversation.append(
                {"tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": result}
            )
        except Exception as e:
            mission_log += f"Engine: [FATAL ERROR] An unexpected error occurred: {e}\nAborting mission."
            yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR))
            return

    mission_log += "\n--- Max steps reached. Mission concluding. ---"
    yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR))

# --- GRADIO UI (Polished) ---
with gr.Blocks(theme=gr.themes.Default(primary_hue="slate", secondary_hue="gray"), title="Singularity Framework") as demo:
    gr.Markdown("# ✨ Singularity: The Autonomous AI Developer")
    status_bar = gr.Textbox("System Offline. Click 'Activate Engine' to begin.", label="System Status", interactive=False)
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ Controls")
            # The API key input is now removed.
            activate_btn = gr.Button("Activate Engine")
            gr.Markdown("### 🌳 Project Files")
            file_tree = gr.Radio(label="File System", interactive=True)
        
        with gr.Column(scale=3):
            gr.Markdown("### 📝 Mission Control")
            mission_prompt = gr.Textbox(label="High-Level Objective", placeholder="Build a simple Flask app that returns the current time as a JSON object.")
            launch_btn = gr.Button("🚀 Launch Mission", variant="primary", interactive=False)
            gr.Markdown("### 📜 Mission Log")
            mission_log_output = gr.Textbox(label="Live Log", lines=25, interactive=False, autoscroll=True)

    def handle_activation():
        # The activation function no longer needs any inputs.
        message, success = initialize_clients()
        return {
            status_bar: gr.update(value=message),
            launch_btn: gr.update(interactive=success)
        }
    
    # The click event now has no inputs.
    activate_btn.click(handle_activation, [], [status_bar, launch_btn])
    launch_btn.click(fn=run_singularity_mission, inputs=[mission_prompt], outputs=[mission_log_output, file_tree])

if __name__ == "__main__":
    demo.launch(debug=True)