import os
import pandas as pd
import time
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()

# Initialize the new SDK client
# Ensure your GOOGLE_API_KEY is in your .env file
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

def run_compliance_batch():
    print("Uploading legal documents to Gemini File API...")
    files = []
    data_dir = "data"
    
    # 1. Upload files
    if not os.path.exists(data_dir):
        print(f"Error: Directory '{data_dir}' not found.")
        return

    for filename in sorted(os.listdir(data_dir)):
        if filename.endswith(".pdf"):
            path = os.path.join(data_dir, filename)
            print(f"Uploading {filename}...")
            # New SDK upload syntax
            file = client.files.upload(file=path) 
            files.append(file)
    
    # 2. Wait for files to process
    print("Waiting for files to process...")
    for f in files:
        while True:
            f = client.files.get(name=f.name)
            if f.state.name == "ACTIVE":
                break
            if f.state.name == "FAILED":
                raise Exception(f"File {f.name} failed to process")
            time.sleep(2)

    # 3. Process the CSV
    if not os.path.exists("input.csv"):
        print("Error: input.csv not found.")
        return

    df = pd.read_csv("input.csv")
    if 'Analysis' not in df.columns:
        df['Analysis'] = ""

    for index, row in df.iterrows():
        # Skip if already analyzed
        if pd.notna(df.at[index, 'Analysis']) and str(df.at[index, 'Analysis']).strip() != "":
            continue
            
        print(f"Processing row {index + 1} of {len(df)}...")
        
        prompt = (f"""
You are a specialized medical reporting assistant. Your task is to generate a legally compliant ultrasound report of just 1-2 lines 
based on provided fetal head circumference (in mm), LMP(Last Menstrual Period) Gestational Age or GA of the patient, 
and the scenario type, i.e. if the HC and LMP GA align or not (COMPLIANT or MISMATCH).

YOUR TASKS:
REPORT: Generate a formal report of 1-2 lines with compliant by both ISUOG guidelines and the Indian PC-PNDT Act guidelines and return
the report in the following strict JSON format:
{{
    "report": "Your generated report here"
}}

Data: {row.to_dict()}""")
        
        try:
            # New SDK model generate_content syntax
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[*files, prompt]
            )
            df.at[index, 'Analysis'] = response.text
            df.to_csv("output_final.csv", index=False)
            
            # Respect rate limits
            time.sleep(2) 
            
        except Exception as e:
            print(f"Error on row {index + 1}: {e}")
            time.sleep(10)

    # 4. Cleanup
    print("Cleaning up files...")
    for f in files:
        client.files.delete(name=f.name)
    print("Process complete. Results saved to output_final.csv")

if __name__ == "__main__":
    run_compliance_batch()
