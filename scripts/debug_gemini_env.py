import google.generativeai as genai
import os
import toml

def debug_env():
    print(f"DEBUG: GenAI Library Version: {genai.__version__}")
    
    # Load Key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key and os.path.exists(".streamlit/secrets.toml"):
        try:
            config = toml.load(".streamlit/secrets.toml")
            api_key = config.get("GEMINI_API_KEY")
        except:
            pass
            
    if not api_key:
        print("ERROR: No API Key found.")
        return

    genai.configure(api_key=api_key)
    
    print("Listing Available Models:")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
    except Exception as e:
        print(f"List Models Failed: {e}")

if __name__ == "__main__":
    debug_env()
