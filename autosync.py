import subprocess
import time

# Sync every 3 minutes (180 seconds)
INTERVAL = 180 

def git_sync():
    try:
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if status.stdout.strip():
            print("[Phantom Engine Backup] Changes detected. Syncing to GitHub...")
            subprocess.run(["git", "add", "."])
            subprocess.run(["git", "commit", "-m", "Auto-backup: safe sync checkpoint"])
            subprocess.run(["git", "push", "origin", "main"])
            print("[Phantom Engine Backup] Successfully pushed to GitHub!")
        else:
            print("[Phantom Engine Backup] No changes to sync.")
    except Exception as e:
        print(f"[Phantom Engine Backup] Error during sync: {e}")

if __name__ == "__main__":
    print("Phantom Engine Auto-Sync Background Service Started.")
    while True:
        git_sync()
        time.sleep(INTERVAL)
