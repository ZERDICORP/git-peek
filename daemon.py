import os
import sys
import time
import subprocess
import configparser


def load_config(path):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Конфиг {path} не найден.")

    config = configparser.ConfigParser()
    config.read(path)

    settings = config["settings"]
    _repo_path = settings.get("repo_path")
    _script_path = settings.get("script_path")
    _check_interval = settings.getint("check_interval", fallback=60)
    _trigger_keyword = settings.get("trigger_keyword", fallback="git-peek-trigger")

    if not os.path.isdir(os.path.join(_repo_path, ".git")):
        raise ValueError(f"{_repo_path} не является git-репозиторием")

    if not os.path.isfile(_script_path):
        raise ValueError(f"Скрипт {_script_path} не найден")

    return _repo_path, _script_path, _check_interval, _trigger_keyword


def get_current_branch(local_repo):
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=local_repo, check=True, stdout=subprocess.PIPE
    )
    return result.stdout.decode().strip()


def fetch_origin(local_repo):
    subprocess.run(["git", "fetch"], cwd=local_repo, check=True)


def get_latest_origin_commit(local_repo, branch):
    hash_result = subprocess.run(
        ["git", "rev-parse", f"origin/{branch}"],
        cwd=local_repo, check=True, stdout=subprocess.PIPE
    )
    msg_result = subprocess.run(
        ["git", "log", "-1", "--pretty=%s", f"origin/{branch}"],
        cwd=local_repo, check=True, stdout=subprocess.PIPE
    )

    commit_hash = hash_result.stdout.decode().strip()
    commit_msg = msg_result.stdout.decode().strip()

    return commit_hash, commit_msg


def execute_script(_script_path):
    try:
        result = subprocess.run(["bash", _script_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"[SCRIPT OUT]\n{result.stdout.decode().strip()}")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Ошибка при выполнении скрипта:\n{e.stderr.decode().strip()}")


def daemon_loop(_repo_path, _script_path, _interval, _trigger_keyword):
    try:
        branch = get_current_branch(_repo_path)
        print(f"[INFO] Текущая ветка: {branch}")
    except Exception as e:
        print(f"[ERROR] Не удалось определить ветку: {e}")
        return

    last_trigger_hash = None

    while True:
        try:
            fetch_origin(_repo_path)
            commit_hash, commit_msg = get_latest_origin_commit(_repo_path, branch)

            if _trigger_keyword in commit_msg:
                if commit_hash != last_trigger_hash:
                    print(f"git peek '{commit_hash}'")
                    execute_script(_script_path)
                    last_trigger_hash = commit_hash
                else:
                    print("[INFO] Триггер уже обработан.")
            else:
                print("[INFO] Нет триггера в последнем коммите.")

        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Git ошибка: {e}")

        time.sleep(_interval)


if __name__ == "__main__":
    config_path = "gpeek.conf"
    try:
        repo_path, script_path, interval, trigger_keyword = load_config(config_path)
        daemon_loop(repo_path, script_path, interval, trigger_keyword)
    except Exception as e:
        print(f"[FATAL] {e}")
        sys.exit(1)
