# make_project_archive.py
import os
import zipfile

# 📌 Устанавливаем рабочую директорию — корень проекта
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

EXCLUDED_EXTENSIONS = {
    ".pyc", ".pyo", ".log", ".tmp", ".parquet", ".csv", ".gz",
    ".ipynb", ".db", ".db-shm", ".db-wal", ".json"
}

EXCLUDED_DIRS = {
    "__pycache__", ".vscode", ".idea", ".ipynb_checkpoints",
    "venv", ".venv", "env", ".env", "myenv", ".myenv", ".git"
}


ALWAYS_INCLUDE_DIRS = {
    "logs", "data/temp"
}

MAX_FILE_SIZE_MB = 1
PROJECT_ROOT = "."
OUTPUT_ZIP = "project_clean.zip"

def should_include(file_path, rel_path):
    if os.path.isdir(file_path):
        return False
    if any(part in EXCLUDED_DIRS for part in rel_path.split(os.sep)):
        return False
    if os.path.splitext(file_path)[1].lower() in EXCLUDED_EXTENSIONS:
        return False
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        return False
    return True

def zip_project():
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            rel_dir = os.path.relpath(root, PROJECT_ROOT)
            if rel_dir == ".":
                rel_dir = ""
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.join(rel_dir, file)
                if should_include(file_path, rel_path):
                    zipf.write(file_path, rel_path)

        # Сохраняем пустые, но важные папки
        for always_dir in ALWAYS_INCLUDE_DIRS:
            abs_path = os.path.join(PROJECT_ROOT, always_dir)
            if os.path.isdir(abs_path):
                if not any(os.scandir(abs_path)):  # если пусто
                    zinfo = zipfile.ZipInfo(always_dir + "/")
                    zipf.writestr(zinfo, "")
    print(f"✅ Архив создан: {OUTPUT_ZIP} (с фильтрацией и пустыми папками)")

if __name__ == "__main__":
    zip_project()

