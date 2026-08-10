from music_app.ui.main_window import MainWindow


def test_main_window_exposes_safe_primary_actions(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "Music-"
    assert window.apply_button.isEnabled() is False
    assert "Preview" in window.mode_label.text()
    assert window.add_files_button.text() == "Add Files"
    assert window.add_folder_button.text() == "Add Folder"
    assert window.analyze_button.text() == "Analyze"
    assert window.undo_button.text() == "Undo Last"
