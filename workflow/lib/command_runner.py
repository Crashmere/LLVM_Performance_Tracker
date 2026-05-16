import subprocess
from datetime import datetime
from pathlib import Path


class CommandRunner:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_snakemake(cls, snakemake_obj) -> "CommandRunner":
        return cls(Path(snakemake_obj.log[0]))

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")

    def run(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> bool:
        cmd_str = [str(part) for part in cmd if part]
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now().strftime('%H:%M:%S')}] Executing: {' '.join(cmd_str)}\n")
            f.write(f"Working Directory: {cwd or Path.cwd()}\n")
            f.write("-" * 40 + "\n")
            f.flush()
            try:
                subprocess.run(cmd_str, cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT, check=True)
                return True
            except subprocess.CalledProcessError as e:
                self.log(f"[ERROR] Command failed with exit code {e.returncode}.")
                return False
