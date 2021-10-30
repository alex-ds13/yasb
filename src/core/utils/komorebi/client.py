import subprocess
import json
import time
from contextlib import suppress
from typing import Optional


def add_index(dictionary: dict, dictionary_index: int) -> dict:
    dictionary['index'] = dictionary_index
    return dictionary


class KomorebiClient:
    def __init__(
            self,
            komorebic_path: str = "komorebic.exe",
            timeout_secs: int = 1
    ):
        super().__init__()
        self._timeout_secs = timeout_secs
        self._komorebic_path = komorebic_path
        self._previous_poll_offline = False

    def _log_error(self, exception: Exception, msg: str = None):
        print(f"{self._komorebic_path} : {msg}", exception)

    def query_state(self) -> Optional[dict]:
        with suppress(json.JSONDecodeError, subprocess.SubprocessError):
            proc = subprocess.Popen([self._komorebic_path, "state"],  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            stdout, stderr = proc.communicate(timeout=self._timeout_secs)
            return json.loads(stdout)

    def get_screens(self, state: dict) -> list:
        return state['monitors']['elements']

    def get_screen_by_hwnd(self, state: dict, screen_hwnd: int) -> Optional[dict]:
        for i, screen in enumerate(self.get_screens(state)):
            if screen.get('id', None) == screen_hwnd:
                return add_index(screen, i)

    def get_workspaces(self, screen: dict) -> list:
        return [add_index(workspace, i) for i, workspace in enumerate(screen['workspaces']['elements'])]

    def get_workspace_by_index(self, screen: dict, workspace_index: int) -> Optional[dict]:
        return self.get_workspaces(screen)[workspace_index]

    def get_focused_workspace(self, screen: dict):
        focused_workspace_index = screen['workspaces']['focused']
        focused_workspace = self.get_workspace_by_index(screen, focused_workspace_index)
        focused_workspace['index'] = focused_workspace_index
        return focused_workspace

    def workspace_has_windows(self, workspace: dict):
        containers = workspace['containers']['elements']
        if workspace.get('floating_windows', []):
            return True

        for container in containers:
            if container.get('windows', {}).get('elements', []):
                return True

        return False

    def get_workspace_by_window_hwnd(self, workspaces: list[Optional[dict]], window_hwnd: int) -> Optional[dict]:
        for i, workspace in enumerate(workspaces):

            for floating_window in workspace['floating_windows']:
                if floating_window['hwnd'] == window_hwnd:
                    return add_index(workspace, i)

            if ('containers' not in workspace) or ('elements' not in workspace['containers']):
                continue

            for container in workspace['containers']['elements']:
                if ('windows' not in container) or ('elements' not in container['windows']):
                    continue

                for managed_window in container['windows']['elements']:
                    if managed_window['hwnd'] == window_hwnd:
                        return add_index(workspace, i)

    def activate_workspace(self, ws_idx: int) -> None:
        subprocess.Popen([self._komorebic_path, "focus-workspace", str(ws_idx)])

    def next_workspace(self) -> None:
        try:
            subprocess.Popen([self._komorebic_path, "cycle-workspace", "next"])
        except subprocess.SubprocessError as e:
            self._log_error(e, "Failed to cycle komorebi workspace")

    def prev_workspace(self) -> None:
        try:
            subprocess.Popen([self._komorebic_path, "cycle-workspace", "prev"])
        except subprocess.SubprocessError as e:
            self._log_error(e, "Failed to cycle komorebi workspace")

    def toggle_focus_mouse(self) -> None:
        try:
            subprocess.Popen([self._komorebic_path, "toggle-focus-follows-mouse"])
        except subprocess.SubprocessError as e:
            self._log_error(e, "Failed to toggle focus-follows-mouse")

    def wait_until_subscribed_to_pipe(self, pipe_name: str):
        proc = subprocess.Popen(
            [self._komorebic_path, "subscribe", pipe_name],
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = proc.communicate()

        if stderr:
            print("Failed to subscribe komorebi to named pipe:", stderr.decode('utf-8'))
            print("Retrying indefinitely until komorebi is online...")

        while proc.returncode != 0:
            time.sleep(2)
            proc = subprocess.Popen(
                [self._komorebic_path, "subscribe", pipe_name],
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            proc.communicate()