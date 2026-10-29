"""Computer automation tool — pyautogui-based desktop interaction."""

import json
import logging
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyautogui

from jarvis.config import ComputerConfig
from jarvis.models.approval import RiskLevel
from jarvis.tools.base import BaseTool, InvalidOperationError, ToolResult

logger = logging.getLogger(__name__)

# Safety: moving mouse to corner aborts any pyautogui action
pyautogui.FAILSAFE = True


class ComputerTool(BaseTool):
    """Desktop automation tool using pyautogui."""

    def __init__(self, config: ComputerConfig | None = None) -> None:
        self._config = config or ComputerConfig()
        pyautogui.PAUSE = self._config.mouse_move_delay

    @property
    def name(self) -> str:
        return "computer"

    def operations(self) -> dict[str, RiskLevel]:
        return {
            "screenshot": RiskLevel.SAFE,
            "get_screen_info": RiskLevel.SAFE,
            "list_windows": RiskLevel.SAFE,
            "open_application": RiskLevel.REQUIRES_APPROVAL,
            "focus_window": RiskLevel.REQUIRES_APPROVAL,
            "mouse_click": RiskLevel.REQUIRES_APPROVAL,
            "mouse_move": RiskLevel.REQUIRES_APPROVAL,
            "type_text": RiskLevel.REQUIRES_APPROVAL,
            "key_press": RiskLevel.REQUIRES_APPROVAL,
            "scroll": RiskLevel.REQUIRES_APPROVAL,
        }

    async def execute(
        self, operation: str, working_dir: str, **kwargs: str | int | list[str]
    ) -> ToolResult:
        if operation not in self.operations():
            raise InvalidOperationError(self.name, operation)

        dispatch: dict[str, Any] = {
            "screenshot": self._screenshot,
            "get_screen_info": self._get_screen_info,
            "list_windows": self._list_windows,
            "open_application": self._open_application,
            "focus_window": self._focus_window,
            "mouse_click": self._mouse_click,
            "mouse_move": self._mouse_move,
            "type_text": self._type_text,
            "key_press": self._key_press,
            "scroll": self._scroll,
        }
        handler = dispatch[operation]
        return await handler(**kwargs)

    def _is_blocked(self, app_name: str) -> bool:
        """Check if an application is blocked."""
        for blocked in self._config.blocked_applications:
            if blocked.lower() == app_name.lower():
                return True
        return False

    def _is_allowed(self, app_name: str) -> bool:
        """Check if an application is allowed (blocklist + allowlist)."""
        if self._is_blocked(app_name):
            return False
        if self._config.allowed_applications:
            return any(a.lower() == app_name.lower() for a in self._config.allowed_applications)
        return True

    def _check_bounds(self, x: int, y: int) -> str | None:
        """Return error message if coordinates are out of screen bounds."""
        screen_w, screen_h = pyautogui.size()
        if x < 0 or x >= screen_w or y < 0 or y >= screen_h:
            return f"Coordinates ({x}, {y}) out of screen bounds ({screen_w}x{screen_h})"
        return None

    async def _screenshot(self, **kwargs: str | int | list[str]) -> ToolResult:
        screenshot_dir = self._config.screenshot_dir
        os.makedirs(screenshot_dir, exist_ok=True)
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = str(Path(screenshot_dir) / filename)

        try:
            img = pyautogui.screenshot()
            img.save(filepath)
            return ToolResult(success=True, output=f"Screenshot saved to {filepath}")
        except Exception as exc:
            return ToolResult(
                success=False, output="", error=f"Screenshot failed: {exc}", exit_code=1
            )

    async def _get_screen_info(self, **kwargs: str | int | list[str]) -> ToolResult:
        try:
            screen_w, screen_h = pyautogui.size()
            mouse_x, mouse_y = pyautogui.position()
            info = {
                "screen_width": screen_w,
                "screen_height": screen_h,
                "mouse_x": mouse_x,
                "mouse_y": mouse_y,
            }
            return ToolResult(success=True, output=json.dumps(info))
        except Exception as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to get screen info: {exc}",
                exit_code=1,
            )

    async def _list_windows(self, **kwargs: str | int | list[str]) -> ToolResult:
        try:
            script = (
                'tell application "System Events" to get the name of every process '
                "whose visible is true"
            )
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"osascript failed: {result.stderr.strip()}",
                    exit_code=1,
                )
            windows = [w.strip() for w in result.stdout.strip().split(", ") if w.strip()]
            return ToolResult(success=True, output=json.dumps(windows))
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, output="", error="Timed out listing windows", exit_code=1
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to list windows: {exc}",
                exit_code=1,
            )

    async def _open_application(self, **kwargs: str | int | list[str]) -> ToolResult:
        app_name = kwargs.get("name")
        if not isinstance(app_name, str) or not app_name:
            return ToolResult(success=False, output="", error="name is required", exit_code=1)

        if not self._is_allowed(app_name):
            return ToolResult(
                success=False,
                output="",
                error=f"Application '{app_name}' is blocked",
                exit_code=1,
            )

        try:
            result = subprocess.run(
                ["open", "-a", app_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Failed to open '{app_name}': {result.stderr.strip()}",
                    exit_code=1,
                )
            return ToolResult(success=True, output=f"Opened application '{app_name}'")
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error=f"Timed out opening '{app_name}'",
                exit_code=1,
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to open application: {exc}",
                exit_code=1,
            )

    async def _focus_window(self, **kwargs: str | int | list[str]) -> ToolResult:
        app_name = kwargs.get("name")
        if not isinstance(app_name, str) or not app_name:
            return ToolResult(success=False, output="", error="name is required", exit_code=1)

        if not self._is_allowed(app_name):
            return ToolResult(
                success=False,
                output="",
                error=f"Application '{app_name}' is blocked",
                exit_code=1,
            )

        try:
            safe_name = app_name.replace("\\", "").replace('"', "")
            script = f'tell application "{safe_name}" to activate'
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Failed to focus '{app_name}': {result.stderr.strip()}",
                    exit_code=1,
                )
            return ToolResult(success=True, output=f"Focused application '{app_name}'")
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error=f"Timed out focusing '{app_name}'",
                exit_code=1,
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to focus window: {exc}",
                exit_code=1,
            )

    async def _mouse_click(self, **kwargs: str | int | list[str]) -> ToolResult:
        x = kwargs.get("x")
        y = kwargs.get("y")
        if x is None or y is None:
            return ToolResult(success=False, output="", error="x and y are required", exit_code=1)

        try:
            x_int, y_int = int(str(x)), int(str(y))
        except ValueError:
            return ToolResult(
                success=False,
                output="",
                error="x and y must be integers",
                exit_code=1,
            )

        bounds_error = self._check_bounds(x_int, y_int)
        if bounds_error:
            return ToolResult(success=False, output="", error=bounds_error, exit_code=1)

        try:
            button = str(kwargs.get("button", "left"))
            pyautogui.click(x_int, y_int, button=button)
            return ToolResult(
                success=True, output=f"Clicked at ({x_int}, {y_int}) with {button} button"
            )
        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Click failed: {exc}", exit_code=1)

    async def _mouse_move(self, **kwargs: str | int | list[str]) -> ToolResult:
        x = kwargs.get("x")
        y = kwargs.get("y")
        if x is None or y is None:
            return ToolResult(success=False, output="", error="x and y are required", exit_code=1)

        try:
            x_int, y_int = int(str(x)), int(str(y))
        except ValueError:
            return ToolResult(
                success=False,
                output="",
                error="x and y must be integers",
                exit_code=1,
            )

        bounds_error = self._check_bounds(x_int, y_int)
        if bounds_error:
            return ToolResult(success=False, output="", error=bounds_error, exit_code=1)

        try:
            pyautogui.moveTo(x_int, y_int)
            return ToolResult(success=True, output=f"Moved mouse to ({x_int}, {y_int})")
        except Exception as exc:
            return ToolResult(
                success=False, output="", error=f"Mouse move failed: {exc}", exit_code=1
            )

    async def _type_text(self, **kwargs: str | int | list[str]) -> ToolResult:
        text = kwargs.get("text")
        if not isinstance(text, str) or not text:
            return ToolResult(success=False, output="", error="text is required", exit_code=1)

        try:
            pyautogui.write(text, interval=0.02)
            return ToolResult(success=True, output=f"Typed {len(text)} characters")
        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Type failed: {exc}", exit_code=1)

    async def _key_press(self, **kwargs: str | int | list[str]) -> ToolResult:
        keys = kwargs.get("keys")
        if not isinstance(keys, str) or not keys:
            return ToolResult(success=False, output="", error="keys is required", exit_code=1)

        try:
            key_list = [k.strip() for k in keys.split("+")]
            pyautogui.hotkey(*key_list)
            return ToolResult(success=True, output=f"Pressed key combo: {keys}")
        except Exception as exc:
            return ToolResult(
                success=False, output="", error=f"Key press failed: {exc}", exit_code=1
            )

    async def _scroll(self, **kwargs: str | int | list[str]) -> ToolResult:
        clicks = kwargs.get("clicks")
        if clicks is None:
            return ToolResult(success=False, output="", error="clicks is required", exit_code=1)

        try:
            clicks_int = int(str(clicks))
        except ValueError:
            return ToolResult(
                success=False,
                output="",
                error="clicks must be an integer",
                exit_code=1,
            )

        try:
            pyautogui.scroll(clicks_int)
            direction = "up" if clicks_int > 0 else "down"
            return ToolResult(
                success=True, output=f"Scrolled {direction} by {abs(clicks_int)} clicks"
            )
        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Scroll failed: {exc}", exit_code=1)
