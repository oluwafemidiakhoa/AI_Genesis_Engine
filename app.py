import gradio as gr
import openai
import google.generativeai as genai
import os
import json
import subprocess
import time
import shutil

# --- CONFIGURATION & STATE ---
PROJECT_DIR = "metropolis_project"
openai_client, gemini_model = None, None

# --- TOOL DEFINITIONS ---
def write_file(path: str, content: str) -> str:
    """Writes or overwrites a file with the given content."""
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}."
    except Exception as e:
        return f"Error writing to file: {e}"

def run_shell_command(command: str) -> str:
    """Executes a shell command in the project directory."""
    try:
        result = subprocess.run(command, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=120)
        return f"COMMAND:\n$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e:
        return f"Error executing shell command: {e}"

def finish_mission(reason: str) -> str:
    """Declares the mission complete."""
    return f"Mission finished. Reason: {reason}"

# --- INITIALIZATION ---
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
        return "✅ All engines online. Metropolis is ready to build.", True
    except Exception as e:
        return f"❌ API Initialization Failed: {e}", False

# --- THE METROPOLIS ORCHESTRATOR ---
def run_metropolis_mission(initial_prompt, max_steps=20):
    mission_log = "Mission Log: [START]\n"
    yield mission_log, gr.update(choices=[])

    if os.path.exists(PROJECT_DIR):
        shutil.rmtree(PROJECT_DIR)
    os.makedirs(PROJECT_DIR, exist_ok=True)
    
    # Phase 1: Architect creates the high-level product plan
    mission_log += "Architect (Gemini): Creating high-level product roadmap...\n"
    yield mission_log, None
    
    architect_prompt = (
        "You are The Architect. Create a high-level plan to build the user's requested application. "
        "The plan MUST be a numbered list of natural language steps. "
        "Crucially, you must separate UI design from implementation. A typical plan should look like: "
        "1. Design the UI for the main page. "
        "2. Implement the frontend HTML for the main page using Tailwind CSS. "
        "3. Implement the backend server logic in a file named `app.py`. "
        "4. Create a `requirements.txt` file. "
        "5. Install dependencies. "
        "6. Run the application."
    )
    response = gemini_model.generate_content(f"{architect_prompt}\n\nUser Goal: {initial_prompt}")
    plan = [step.strip() for step in response.text.split('\n') if step.strip() and re.match(r'^\d+\.', step.strip())]
    
    if not plan:
        mission_log += "Architect: [FATAL ERROR] Failed to create a valid plan.\n"
        yield mission_log, None
        return
        
    mission_log += f"Architect: Plan generated with {len(plan)} steps.\n"
    yield mission_log, None

    # Phase 2: Execute the plan with specialized agents
    design_spec = ""
    for i, step_instruction in enumerate(plan):
        mission_log += f"\n--- Executing Step {i+1}/{len(plan)}: {step_instruction} ---\n"
        yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR) or ["(empty)"])
        
        # Determine agent based on instruction
        if "design the ui" in step_instruction.lower():
            agent_name = "UI/UX Designer"
            mission_log += f"Engine: Delegating to {agent_name} (Gemini)...\n"
            yield mission_log, None
            
            designer_prompt = (
                "You are a world-class UI/UX Designer. You will be given a design task. "
                "Your job is to produce a detailed 'design specification' in plain English. "
                "Describe the layout, components, colors, and fonts. "
                "CRITICAL: You must specify styles using Tailwind CSS utility classes (e.g., `bg-blue-500`, `shadow-lg`, `rounded-xl`, `flex items-center`)."
            )
            response = gemini_model.generate_content(f"{designer_prompt}\n\nTask: {step_instruction}")
            design_spec = response.text
            mission_log += f"Designer's Spec:\n---\n{design_spec}\n---\n"

        elif "implement the frontend" in step_instruction.lower():
            agent_name = "Frontend Engineer"
            mission_log += f"Engine: Delegating to {agent_name} (GPT-4o)...\n"
            yield mission_log, None
            
            frontend_prompt = (
                "You are an expert Frontend Engineer who specializes in Tailwind CSS. "
                "Your task is to write the HTML for a component based on a design specification. "
                "You MUST use the Tailwind Play CDN script in the `<head>` for styling. "
                "The output must be a single block of perfect, complete HTML code. Do not add explanations."
            )
            context = f"Instruction: {step_instruction}\n\nDesign Specification:\n{design_spec}"
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": frontend_prompt},
                    {"role": "user", "content": context}
                ]
            )
            code_content = response.choices[0].message.content
            write_file("templates/index.html", code_content)
            mission_log += "Frontend Engineer: Wrote `templates/index.html`.\n"

        else: # Default to the backend/tooling agent for all other tasks
            agent_name = "Backend Developer & Tooling Specialist"
            mission_log += f"Engine: Delegating to {agent_name} (GPT-4o)...\n"
            yield mission_log, None
            
            # This agent uses the function-calling loop from the Singularity framework
            conversation = [
                {"role": "system", "content": "You are an expert Backend Developer and Tooling Specialist. Execute the user's instruction by calling the appropriate function. Call `finish_mission` when the entire project is complete and running."},
                {"role": "user", "content": step_instruction}
            ]
            tools = [
                {"type": "function", "function": {"name": "write_file", "description": "Writes content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
                {"type": "function", "function": {"name": "run_shell_command", "description": "Executes a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}
            ]
            
            response = openai_client.chat.completions.create(model="gpt-4o", messages=conversation, tools=tools, tool_choice="auto")
            response_message = response.choices[0].message

            if response_message.tool_calls:
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    result = globals()[function_name](**function_args)
                    mission_log += f"Backend/Tooling: Called `{function_name}`. Result: {result}\n"

        yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR) or ["(empty)"])

    mission_log += "\n--- MISSION COMPLETE ---"
    yield mission_log, gr.update(choices=os.listdir(PROJECT_DIR) or ["(empty)"])


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
        
        with gr.Column(scale=3):
            gr.Markdown("### 📝 Mission Control")
            mission_prompt = gr.Textbox(label="High-Level Objective", placeholder="e.g., Build a beautiful, modern login page with a glassmorphism effect.")
            launch_btn = gr.Button("🚀 Launch Mission", variant="primary", interactive=False)
            gr.Markdown("### 📜 Mission Log")
            mission_log_output = gr.Textbox(label="Live Log", lines=25, interactive=False, autoscroll=True)

    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    
    activate_btn.click(handle_activation, [], [status_bar, launch_btn])
    launch_btn.click(fn=run_metropolis_mission, inputs=[mission_prompt], outputs=[mission_log_output, file_tree])

if __name__ == "__main__":
    demo.launch(debug=True)