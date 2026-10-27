"""Tests for ComputerTool — all OS interactions mocked."""

import json
from unittest.mock import MagicMock, patch

import pytest

from jarvis.config import ComputerConfig
from jarvis.models.approval import RiskLevel
from jarvis.tools.base import InvalidOperationError
from jarvis.tools.computer_tool import ComputerTool


@pytest.fixture
def config() -> ComputerConfig:
    return ComputerConfig(
        screenshot_dir="/tmp/test_screenshots",
        blocked_applications=["Terminal", "iTerm", "System Preferences", "System Settings"],
    )


@pytest.fixture
def tool(config: ComputerConfig) -> ComputerTool:
    return ComputerTool(config)


class TestComputerToolMeta:
    def test_name(self, tool: ComputerTool) -> None:
        assert tool.name == "computer"

    def test_operations_count(self, tool: ComputerTool) -> None:
        assert len(tool.operations()) == 10

    def test_safe_operations(self, tool: ComputerTool) -> None:
        ops = tool.operations()
        assert ops["screenshot"] == RiskLevel.SAFE
        assert ops["get_screen_info"] == RiskLevel.SAFE
        assert ops["list_windows"] == RiskLevel.SAFE

    def test_approval_operations(self, tool: ComputerTool) -> None:
        ops = tool.operations()
        for op in [
            "open_application", "focus_window", "mouse_click",
            "mouse_move", "type_text", "key_press", "scroll",
        ]:
            assert ops[op] == RiskLevel.REQUIRES_APPROVAL

    def test_risk_level_for(self, tool: ComputerTool) -> None:
        assert tool.risk_level_for("screenshot") == RiskLevel.SAFE
        assert tool.risk_level_for("mouse_click") == RiskLevel.REQUIRES_APPROVAL


class TestComputerToolValidation:
    async def test_invalid_operation_raises(self, tool: ComputerTool) -> None:
        with pytest.raises(InvalidOperationError):
            await tool.execute("nonexistent", "/tmp")


class TestScreenshot:
    @patch("jarvis.tools.computer_tool.pyautogui")
    @patch("jarvis.tools.computer_tool.os.makedirs")
    async def test_screenshot_success(
        self, mock_makedirs: MagicMock, mock_pyautogui: MagicMock, tool: ComputerTool
    ) -> None:
        mock_img = MagicMock()
        mock_pyautogui.screenshot.return_value = mock_img

        result = await tool.execute("screenshot", "/tmp")

        assert result.success is True
        assert "Screenshot saved to" in result.output
        mock_makedirs.assert_called_once()
        mock_img.save.assert_called_once()

    @patch("jarvis.tools.computer_tool.pyautogui")
    @patch("jarvis.tools.computer_tool.os.makedirs")
    async def test_screenshot_failure(
        self, mock_makedirs: MagicMock, mock_pyautogui: MagicMock, tool: ComputerTool
    ) -> None:
        mock_pyautogui.screenshot.side_effect = RuntimeError("no display")

        result = await tool.execute("screenshot", "/tmp")

        assert result.success is False
        assert "Screenshot failed" in (result.error or "")


class TestGetScreenInfo:
    @patch("jarvis.tools.computer_tool.pyautogui")
    async def test_get_screen_info(
        self, mock_pyautogui: MagicMock, tool: ComputerTool
    ) -> None:
        mock_pyautogui.size.return_value = (1920, 1080)
        mock_pyautogui.position.return_value = (500, 300)

        result = await tool.execute("get_screen_info", "/tmp")

        assert result.success is True
        info = json.loads(result.output)
        assert info["screen_width"] == 1920
        assert info["screen_height"] == 1080
        assert info["mouse_x"] == 500
        assert info["mouse_y"] == 300


class TestListWindows:
    @patch("jarvis.tools.computer_tool.subprocess.run")
    async def test_list_windows_success(
        self, mock_run: MagicMock, tool: ComputerTool
    ) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Finder, Safari, Code\n",
            stderr="",
        )

        result = await tool.execute("list_windows", "/tmp")

        assert result.success is True
        windows = json.loads(result.output)
        assert windows == ["Finder", "Safari", "Code"]

    @patch("jarvis.tools.computer_tool.subprocess.run")
    async def test_list_windows_failure(
        self, mock_run: MagicMock, tool: ComputerTool
    ) -> None:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="osascript error"
        )

        result = await tool.execute("list_windows", "/tmp")

        assert result.success is False
        assert "osascript failed" in (result.error or "")


class TestOpenApplication:
    @patch("jarvis.tools.computer_tool.subprocess.run")
    async def test_open_application_success(
        self, mock_run: MagicMock, tool: ComputerTool
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = await tool.execute("open_application", "/tmp", name="Safari")

        assert result.success is True
        assert "Opened application 'Safari'" in result.output
        mock_run.assert_called_once_with(
            ["open", "-a", "Safari"],
            capture_output=True, text=True, timeout=10,
        )

    async def test_open_application_missing_name(self, tool: ComputerTool) -> None:
        result = await tool.execute("open_application", "/tmp")

        assert result.success is False
        assert "name is required" in (result.error or "")

    async def test_open_application_blocked(self, tool: ComputerTool) -> None:
        result = await tool.execute("open_application", "/tmp", name="Terminal")

        assert result.success is False
        assert "blocked" in (result.error or "")


class TestFocusWindow:
    @patch("jarvis.tools.computer_tool.subprocess.run")
    async def test_focus_window_success(
        self, mock_run: MagicMock, tool: ComputerTool
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = await tool.execute("focus_window", "/tmp", name="Safari")

        assert result.success is True
        assert "Focused application 'Safari'" in result.output

    async def test_focus_window_blocked(self, tool: ComputerTool) -> None:
        result = await tool.execute("focus_window", "/tmp", name="iTerm")

        assert result.success is False
        assert "blocked" in (result.error or "")

    async def test_focus_window_missing_name(self, tool: ComputerTool) -> None:
        result = await tool.execute("focus_window", "/tmp")

        assert result.success is False
        assert "name is required" in (result.error or "")


class TestMouseClick:
    @patch("jarvis.tools.computer_tool.pyautogui")
    async def test_mouse_click_success(
        self, mock_pyautogui: MagicMock, tool: ComputerTool
    ) -> None:
        mock_pyautogui.size.return_value = (1920, 1080)

        result = await tool.execute("mouse_click", "/tmp", x=100, y=200)

        assert result.success is True
        assert "Clicked at (100, 200)" in result.output
        mock_pyautogui.click.assert_called_once_with(100, 200, button="left")

    @patch("jarvis.tools.computer_tool.pyautogui")
    async def test_mouse_click_right_button(
        self, mock_pyautogui: MagicMock, tool: ComputerTool
    ) -> None:
        mock_pyautogui.size.return_value = (1920, 1080)

        result = await tool.execute("mouse_click", "/tmp", x=100, y=200, button="right")

        assert result.success is True
        mock_pyautogui.click.assert_called_once_with(100, 200, button="right")

    @patch("jarvis.tools.computer_tool.pyautogui")
    async def test_mouse_click_out_of_bounds(
        self, mock_pyautogui: MagicMock, tool: ComputerTool
    ) -> None:
        mock_pyautogui.size.return_value = (1920, 1080)

        result = await tool.execute("mouse_click", "/tmp", x=2000, y=200)

        assert result.success is False
        assert "out of screen bounds" in (result.error or "")

    async def test_mouse_click_missing_coords(self, tool: ComputerTool) -> None:
        result = await tool.execute("mouse_click", "/tmp")

        assert result.success is False
        assert "x and y are required" in (result.error or "")


class TestMouseMove:
    @patch("jarvis.tools.computer_tool.pyautogui")
    async def test_mouse_move_success(
        self, mock_pyautogui: MagicMock, tool: ComputerTool
    ) -> None:
        mock_pyautogui.size.return_value = (1920, 1080)

        result = await tool.execute("mouse_move", "/tmp", x=500, y=400)

        assert result.success is True
        assert "Moved mouse to (500, 400)" in result.output
        mock_pyautogui.moveTo.assert_called_once_with(500, 400)

    @patch("jarvis.tools.computer_tool.pyautogui")
    async def test_mouse_move_out_of_bounds(
        self, mock_pyautogui: MagicMock, tool: ComputerTool
    ) -> None:
        mock_pyautogui.size.return_value = (1920, 1080)

        result = await tool.execute("mouse_move", "/tmp", x=-1, y=0)

        assert result.success is False
        assert "out of screen bounds" in (result.error or "")


class TestTypeText:
    @patch("jarvis.tools.computer_tool.pyautogui")
    async def test_type_text_success(
        self, mock_pyautogui: MagicMock, tool: ComputerTool
    ) -> None:
        result = await tool.execute("type_text", "/tmp", text="hello world")

        assert result.success is True
        assert "Typed 11 characters" in result.output
        mock_pyautogui.write.assert_called_once_with("hello world", interval=0.02)

    async def test_type_text_missing(self, tool: ComputerTool) -> None:
        result = await tool.execute("type_text", "/tmp")

        assert result.success is False
        assert "text is required" in (result.error or "")


class TestKeyPress:
    @patch("jarvis.tools.computer_tool.pyautogui")
    async def test_key_press_combo(
        self, mock_pyautogui: MagicMock, tool: ComputerTool
    ) -> None:
        result = await tool.execute("key_press", "/tmp", keys="command+c")

        assert result.success is True
        assert "Pressed key combo: command+c" in result.output
        mock_pyautogui.hotkey.assert_called_once_with("command", "c")

    @patch("jarvis.tools.computer_tool.pyautogui")
    async def test_key_press_single(
        self, mock_pyautogui: MagicMock, tool: ComputerTool
    ) -> None:
        result = await tool.execute("key_press", "/tmp", keys="enter")

        assert result.success is True
        mock_pyautogui.hotkey.assert_called_once_with("enter")

    async def test_key_press_missing(self, tool: ComputerTool) -> None:
        result = await tool.execute("key_press", "/tmp")

        assert result.success is False
        assert "keys is required" in (result.error or "")


class TestScroll:
    @patch("jarvis.tools.computer_tool.pyautogui")
    async def test_scroll_up(
        self, mock_pyautogui: MagicMock, tool: ComputerTool
    ) -> None:
        result = await tool.execute("scroll", "/tmp", clicks=3)

        assert result.success is True
        assert "Scrolled up by 3 clicks" in result.output
        mock_pyautogui.scroll.assert_called_once_with(3)

    @patch("jarvis.tools.computer_tool.pyautogui")
    async def test_scroll_down(
        self, mock_pyautogui: MagicMock, tool: ComputerTool
    ) -> None:
        result = await tool.execute("scroll", "/tmp", clicks=-5)

        assert result.success is True
        assert "Scrolled down by 5 clicks" in result.output

    async def test_scroll_missing_clicks(self, tool: ComputerTool) -> None:
        result = await tool.execute("scroll", "/tmp")

        assert result.success is False
        assert "clicks is required" in (result.error or "")


class TestApplicationBlocklist:
    async def test_blocked_apps_cannot_open(self, tool: ComputerTool) -> None:
        for app in ["Terminal", "iTerm", "System Preferences", "System Settings"]:
            result = await tool.execute("open_application", "/tmp", name=app)
            assert result.success is False
            assert "blocked" in (result.error or "")

    async def test_blocked_apps_cannot_focus(self, tool: ComputerTool) -> None:
        for app in ["Terminal", "iTerm"]:
            result = await tool.execute("focus_window", "/tmp", name=app)
            assert result.success is False
            assert "blocked" in (result.error or "")

    @patch("jarvis.tools.computer_tool.subprocess.run")
    async def test_allowed_app_can_open(
        self, mock_run: MagicMock, tool: ComputerTool
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = await tool.execute("open_application", "/tmp", name="Safari")

        assert result.success is True

    def test_allowlist_restricts(self) -> None:
        config = ComputerConfig(
            allowed_applications=["Safari", "Chrome"],
            blocked_applications=[],
        )
        t = ComputerTool(config)
        assert t._is_allowed("Safari") is True
        assert t._is_allowed("Firefox") is False

    def test_blocklist_case_insensitive(self, tool: ComputerTool) -> None:
        assert tool._is_blocked("terminal") is True
        assert tool._is_blocked("TERMINAL") is True
        assert tool._is_blocked("Terminal") is True

    def test_default_config(self) -> None:
        t = ComputerTool()
        assert t.name == "computer"
        assert len(t.operations()) == 10
