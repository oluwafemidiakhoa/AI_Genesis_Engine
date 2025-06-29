import gradio as gr
import openai
import google.generativeai as genai
import os
import json
import subprocess
import time
import shutil
import re
import requests

# --- CONFIGURATION & STATE ---
PROJECT_DIR = "cosmic_forge_project"
openai_client, gemini_model = None, None

# --- TOOL DEFINITIONS ---
def web_search(query: str) -> str:
    """Performs a direct, programmatic web search using the Serper.dev API for maximum reliability."""
    serper_api_key = os.getenv("SERPER_API_KEY")
    if not serper_api_key: return "Error: SERPER_API_KEY secret not found."
    print(f"Tooling Agent: Performing web search for '{query}'...")
    try:
        response = requests.post("https://google.serper.dev/search", headers={'X-API-KEY': serper_api_key, 'Content-Type': 'application/json'}, data=json.dumps({"q": query}))
        response.raise_for_status()
        results = response.json()
        summary = "Search Results:\n"
        if "organic" in results:
            for item in results["organic"][:5]:
                summary += f"- Title: {item.get('title')}\n  Link: {item.get('link')}\n  Snippet: {item.get('snippet')}\n\n"
        return summary
    except Exception as e: return f"Error during web search: {e}"

def write_file(path: str, content: str) -> str:
    full_path = os.path.join(PROJECT_DIR, path)
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f: f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}."
    except Exception as e: return f"Error writing to file: {e}"

def run_shell_command(command: str) -> str:
    try:
        result = subprocess.run(command, shell=True, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=300)
        return f"COMMAND:\n$ {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e: return f"Error executing shell command: {e}"

# --- INITIALIZATION ---
def initialize_clients():
    global openai_client, gemini_model
    keys = {"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"), "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"), "SERPER_API_KEY": os.getenv("SERPER_API_KEY")}
    missing_keys = [k for k, v in keys.items() if not v]
    if missing_keys: return f"❌ Missing Secrets: {', '.join(missing_keys)}", False
    try:
        openai_client = openai.OpenAI(api_key=keys["OPENAI_API_KEY"])
        genai.configure(api_key=keys["GOOGLE_API_KEY"])
        gemini_model = genai.GenerativeModel("gemini-1.5-pro-latest")
        return "✅ All systems online. The Cosmic Forge is active.", True
    except Exception as e: return f"❌ API Initialization Failed: {e}", False

def parse_json_from_string(text: str) -> dict or list:
    match = re.search(r'```json\s*([\s\S]*?)\s*```|([\s\S]*)', text)
    json_str = (match.group(1) or match.group(2)).strip()
    try: return json.loads(json_str)
    except json.JSONDecodeError as e: raise ValueError(f"Failed to decode JSON. Text: '{json_str[:200]}...'")

# --- THE COSMIC FORGE ORCHESTRATOR ---
def run_cosmic_forge(initial_prompt):
    mission_log = "[MISSION LOG: START]\n"
    yield mission_log, gr.update(visible=False)

    if os.path.exists(PROJECT_DIR): shutil.rmtree(PROJECT_DIR)
    os.makedirs(PROJECT_DIR, exist_ok=True)

    # 1. The Strategist creates the high-level component plan
    mission_log += "--- Phase: Strategy ---\n"
    mission_log += "Strategist (Gemini): Designing high-level component architecture...\n"
    yield mission_log, None

    strategist_prompt = ("You are The Strategist, a CTO-level AI. Analyze the user's request and define the major software components required to build it. "
                         "Your output MUST be a JSON object with a single key 'components', which is an array of strings. "
                         "Example: {\"components\": [\"UserAuthenticationAPI\", \"DataProcessingService\", \"ReactFrontend\"]}")
    try:
        response = gemini_model.generate_content(f"{strategist_prompt}\n\nUser Request: {initial_prompt}", generation_config=genai.types.GenerationConfig(response_mime_type="application/json"))
        strategy = parse_json_from_string(response.text)
        components = strategy.get("components", [])
        mission_log += f"Strategist: Plan involves {len(components)} components: {', '.join(components)}\n"
        yield mission_log, None
    except Exception as e:
        mission_log += f"[FATAL ERROR] The Strategist failed to create a valid plan: {e}\n"
        yield mission_log, None
        return

    # 2. The Orchestrator iterates through each component, attempting to build it
    for component in components:
        mission_log += f"\n--- Phase: Building Component: {component} ---\n"
        yield mission_log, None
        
        last_error = ""
        for attempt in range(3): # Allow up to 3 self-healing attempts per component
            mission_log += f"Build Attempt {attempt + 1}/3 for {component}...\n"
            
            # 2a. The Task Decomposer creates a micro-plan
            mission_log += f"Task Decomposer (GPT-4o): Breaking down '{component}' into executable steps...\n"
            yield mission_log, None
            
            decomposer_prompt = ("You are The Task Decomposer. Given a software component to build and an error from a previous attempt (if any), "
                                 "create a detailed, step-by-step checklist of tool calls to build it. Your output must be a JSON object with a key 'tasks', "
                                 "which is an array of objects. Each object must have `tool_name` and `parameters` keys.")
            context = f"Component to build: {component}.\nUser's main goal: {initial_prompt}.\n"
            if last_error:
                context += f"Last attempt failed. Error report: {last_error}. Create a new plan to fix this."

            response = openai_client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": decomposer_prompt}, {"role": "user", "content": context}], response_format={"type": "json_object"})
            micro_plan = json.loads(response.choices[0].message.content).get("tasks", [])
            
            # 2b. The Executor runs the micro-plan
            execution_summary = ""
            for task in micro_plan:
                tool_name = task.get("tool_name")
                parameters = task.get("parameters", {})
                mission_log += f"Executor: Calling tool `{tool_name}` with parameters: {parameters}\n"
                yield mission_log, None
                
                try:
                    result = globals()[tool_name](**parameters)
                    mission_log += f"Executor Result:\n---\n{result}\n---\n"
                    execution_summary += f"Task '{tool_name}' result: {result}\n"
                except Exception as e:
                    execution_summary += f"Task '{tool_name}' failed: {e}\n"
                    mission_log += f"[ERROR] Executor failed to run tool: {e}\n"

            # 2c. The Code Reviewer inspects the work
            mission_log += f"Code Reviewer (Gemini): Reviewing the result for '{component}'...\n"
            yield mission_log, None
            
            reviewer_prompt = ("You are The Code Reviewer. Given the original goal for a component and a summary of the execution, "
                               "determine if the component was built successfully. Your output must be a JSON object with keys "
                               "`status` ('success' or 'failure') and `reason` (a brief explanation).")
            context = f"Component Goal: {component}.\nExecution Summary:\n{execution_summary}"
            response = gemini_model.generate_content(f"{reviewer_prompt}\n\n{context}", generation_config=genai.types.GenerationConfig(response_mime_type="application/json"))
            review = parse_json_from_string(response.text)
            
            mission_log += f"Code Reviewer Verdict: {review.get('status').upper()}. Reason: {review.get('reason')}\n"
            
            if review.get("status") == "success":
                break # Exit the retry loop and move to the next component
            else:
                last_error = review.get('reason') # Set the error for the next attempt
        else: # This 'else' belongs to the 'for' loop, it runs if the loop completes without a 'break'
            mission_log += f"[FATAL ERROR] Component '{component}' failed to build after all attempts. Aborting mission.\n"
            yield mission_log, None
            return

    mission_log += "\n--- MISSION COMPLETE ---"
    
    # Final step: Create and provide download link
    zip_path = os.path.join(PROJECT_DIR, "cosmic_forge_app.zip")
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for root, _, files in os.walk(PROJECT_DIR):
            for file in files:
                if file != os.path.basename(zip_path):
                    zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), PROJECT_DIR))
    
    yield mission_log, gr.update(visible=True, value=zip_path)

# --- GRADIO UI ---
with gr.Blocks(theme=gr.themes.Monochrome(), title="Cosmic Forge") as demo:
    gr.Markdown("# 🔥 Cosmic Forge: The Autonomous AI Developer")
    status_bar = gr.Textbox("System Offline. Click 'Activate Engines' to begin.", label="System Status", interactive=False)
    
    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("### 🚀 Mission Control")
            mission_prompt = gr.Textbox(label="High-Level Objective", placeholder="e.g., A microservices-based URL shortener with a Redis backend and a React frontend.", lines=4)
            launch_btn = gr.Button("Forge Application", variant="primary", interactive=False)
            download_zip_btn = gr.DownloadButton(label="Download Forged App as .zip", visible=False)
        with gr.Column(scale=3):
            gr.Markdown("### 📜 Mission Log")
            mission_log_output = gr.Textbox(label="Live Log", lines=25, interactive=False, autoscroll=True)

    def handle_activation():
        message, success = initialize_clients()
        return {status_bar: gr.update(value=message), launch_btn: gr.update(interactive=success)}
    
    activate_btn = gr.Button("Activate Engines") # Moved button outside for better layout
    status_bar.change(handle_activation, [], [status_bar, launch_btn]) # Auto-activate if secrets are present
    demo.load(handle_activation, [], [status_bar, launch_btn]) # Activate on page load
    
    launch_btn.click(fn=run_cosmic_forge, inputs=[mission_prompt], outputs=[mission_log_output, download_zip_btn])

if __name__ == "__main__":
    demo.launch(debug=True)