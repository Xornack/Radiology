"""Catppuccin-inspired stylesheet for MainWindow.

Extracted from main_window.py so the window module stays focused on
widget wiring and state. Colors come from the Catppuccin Mocha palette.
"""

MAIN_WINDOW_QSS = """
    #rootWidget {
        background: #1e1e2e;
        border: 1px solid #585b70;
        border-radius: 8px;
    }
    #titleBar {
        background: #24273a;
        border-bottom: 1px solid #45475a;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
    }
    #appTitle {
        color: #cdd6f4;
        font-size: 13px;
        font-weight: bold;
    }
    #winBtn {
        background: #313244;
        color: #cdd6f4;
        border: none;
        border-radius: 4px;
        font-size: 16px;
    }
    #winBtn:hover { background: #45475a; }
    #closeBtn {
        background: #313244;
        color: #cdd6f4;
        border: none;
        border-radius: 4px;
        font-size: 16px;
    }
    #closeBtn:hover { background: #f38ba8; color: #1e1e2e; }
    QTextEdit {
        background: #181825;
        color: #cdd6f4;
        border: none;
        font-family: 'Segoe UI', sans-serif;
        font-size: 13px;
        padding: 6px;
    }
    #actionBar {
        background: #1e1e2e;
        border-top: 1px solid #45475a;
    }
    #impressionBtn, #structureBtn {
        background: #89b4fa;
        color: #1e1e2e;
        border: none;
        border-radius: 4px;
        padding: 6px 14px;
        font-size: 12px;
        font-weight: bold;
    }
    #impressionBtn:hover, #structureBtn:hover { background: #b4befe; }
    #impressionBtn:disabled, #structureBtn:disabled { background: #45475a; color: #7f849c; }
    #recordBtn {
        background: #f38ba8;
        color: #1e1e2e;
        border: none;
        border-radius: 4px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: bold;
    }
    #recordBtn:hover { background: #eba0ac; }
    #recordBtn:disabled { background: #45475a; color: #7f849c; }
    #stopBtn {
        background: #fab387;
        color: #1e1e2e;
        border: none;
        border-radius: 4px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: bold;
    }
    #stopBtn:hover { background: #f5c2a7; }
    #stopBtn:disabled { background: #45475a; color: #7f849c; }
    #clearBtn {
        background: #313244;
        color: #cdd6f4;
        border: none;
        border-radius: 4px;
        padding: 6px 12px;
        font-size: 12px;
    }
    #clearBtn:hover { background: #45475a; }
    #micRow { background: #1e1e2e; }
    #micLabel { color: #a6adc8; font-size: 11px; }
    #micCombo {
        background: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 4px;
        padding: 3px 6px;
        font-size: 11px;
    }
    #micCombo:disabled { background: #1e1e2e; color: #7f849c; }
    #refreshBtn {
        background: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 4px;
        font-size: 14px;
    }
    #refreshBtn:hover { background: #45475a; }
    #refreshBtn:disabled { background: #1e1e2e; color: #7f849c; }
    #micCombo QAbstractItemView {
        background: #181825;
        color: #cdd6f4;
        selection-background-color: #45475a;
    }
    #modeRow { background: #1e1e2e; }
    #modeLabel { color: #a6adc8; font-size: 11px; }
    #modeCombo {
        background: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 4px;
        padding: 3px 6px;
        font-size: 11px;
    }
    #modeCombo:disabled { background: #1e1e2e; color: #7f849c; }
    #modeCombo QAbstractItemView {
        background: #181825;
        color: #cdd6f4;
        selection-background-color: #45475a;
    }
    #sttRow { background: #1e1e2e; }
    #sttLabel { color: #a6adc8; font-size: 11px; }
    #sttCombo {
        background: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 4px;
        padding: 3px 6px;
        font-size: 11px;
    }
    #sttCombo:disabled { background: #1e1e2e; color: #7f849c; }
    #sttCombo QAbstractItemView {
        background: #181825;
        color: #cdd6f4;
        selection-background-color: #45475a;
    }
"""
