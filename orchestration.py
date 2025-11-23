import subprocess
import json
import time
from datetime import datetime
import os
import re

# --- Configuration for a single experiment (Double-sided, CIVAC, All 1s) ---
BINARY_NAME = './rowhammer'
RESULTS_DIR = 'results'
HAMMER_PROFILE = {
    "profile_name": "DSH_CIVAC_ALL_ONES",
    "description": "Double-sided, DC CIVAC flush, All 1s pattern",
    # Inputs piped to C program: 1\n (All 1s), 2\n (Double-sided), 2\n (DC CIVAC)
    "inputs": "1\n2\n2\n" 
}
# --- End Configuration ---

def run_experiment(profile):
    """Executes the C binary and captures output."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting experiment: {profile['profile_name']}")
    
    # Use Popen to run binary and pipe inputs and outputs
    try:
        process = subprocess.Popen(
            [BINARY_NAME],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Send the predefined inputs (1\n2\n2\n) to the C binary
        stdout_data, stderr_data = process.communicate(input=profile['inputs'])
        
        if process.returncode != 0:
            print(f"Error executing C binary (Exit Code: {process.returncode}):\n{stderr_data}")
            return None
            
        print(f"[{datetime.now().strftime('%H:%M:%S')}] C execution finished. Processing logs...")
        return stdout_data

    except FileNotFoundError:
        print(f"Error: Binary '{BINARY_NAME}' not found. Did you compile it correctly?")
        return None

def parse_and_log(stdout_data, profile):
    """Parses C output, creates JSON log, and saves files."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file_base = os.path.join(RESULTS_DIR, f"run_{timestamp}_{profile['profile_name']}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    # 1. Save Raw Log
    with open(f"{log_file_base}.log", "w") as f:
        f.write(stdout_data)
    
    # 2. Parse Flips
    flips_data = []
    total_flips = 0
    
    # Regex to capture the flip details from the C script's output
    flip_pattern = re.compile(
        r"attacker1:(?P<attk_pa1>[0-9a-f]+)\tattacker2:(?P<attk_pa2>[0-9a-f]+)\n"
        r"cnt:(?P<cnt>\d+) victim:(?P<victim_pa>[0-9a-f]+) becomes (?P<after_val>[0-9a-f]+)"
    )

    pattern_input = profile['inputs'][0]
    expected_before = "0xffffffff" if pattern_input == '1' else "0x00000000"

    for match in flip_pattern.finditer(stdout_data):
        flip_details = match.groupdict()
        flips_data.append({
            "attacker_rows": [f"0x{flip_details['attk_pa1']}", f"0x{flip_details['attk_pa2']}"],
            "victim_address": f"0x{flip_details['victim_pa']}",
            "before_value": expected_before,
            "after_value": f"0x{flip_details['after_val']}",
        })
        total_flips = int(flip_details['cnt']) 

    json_output = {
        "timestamp": datetime.fromtimestamp(time.time()).isoformat(),
        "pattern": "all_ones" if pattern_input == '1' else "all_zeros",
        "mode": "civac" if profile['inputs'][4] == '2' else "cvac",
        "hammer_type": "double_sided" if profile['inputs'][2] == '2' else "one_sided",
        "total_flips_in_run": total_flips,
        "bit_flips": flips_data
    }
    
    # 3. Save JSON Log
    with open(f"{log_file_base}.json", "w") as f:
        json.dump(json_output, f, indent=2)

    print(f"Successfully saved logs to {log_file_base}.*")
    if total_flips > 0:
        print(f"🎉 SUCCESS! Detected {total_flips} bit flips!")
    else:
        print("⚠️ No bit flips detected in this run.")
    
    return total_flips > 0

if __name__ == "__main__":
    output = run_experiment(HAMMER_PROFILE)
    if output:
        parse_and_log(output, HAMMER_PROFILE)