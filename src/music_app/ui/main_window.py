from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from music_app.ai.clap import CLAPAnalyzer
from music_app.config import AppConfig
from music_app.domain import AnalysisResult, TrackTags
from music_app.identify.acoustid import AcoustIDClient
from music_app.identify.fingerprint import fingerprint_file
from music_app.identify.itunes import ITunesClient
from music_app.identify.pipeline import AnalysisPipeline
from music_app.library.history import HistoryStore
from music_app.library.scanner import discover_audio_files
from music_app.library.tags import MutagenTagIO
from music_app.ui.workers import AnalysisWorker


class MainWindow(QMainWindow):
    def __init__(self, *, config=None, pipeline=None, tag_io=None, history=None) -> None:
        super().__init__()
        self.setWindowTitle("Music-")
        self.resize(1180, 760)
        self.setAcceptDrops(True)

        self.config = config or AppConfig.load()
        self.tag_io = tag_io or MutagenTagIO()
        self.history = history or HistoryStore(self.config.config_dir() / "history")
        self.pipeline = pipeline or self._build_pipeline()
        self.thread_pool = QThreadPool.globalInstance()
        self.tracks = []
        self.results: dict[Path, AnalysisResult] = {}
        self._workers: set[AnalysisWorker] = set()
        self._pending = 0

        self._build_ui()

    def _build_pipeline(self) -> AnalysisPipeline:
        catalogs = [ITunesClient()] if self.config.enable_itunes else []
        acoustid_client = None
        fingerprinter = None
        if self.config.enable_acoustid and self.config.acoustid_client_key.strip():
            acoustid_client = AcoustIDClient(self.config.acoustid_client_key)
            fingerprinter = fingerprint_file
        ai_analyzer = CLAPAnalyzer() if self.config.enable_ai else None
        return AnalysisPipeline(
            catalogs=catalogs,
            fingerprinter=fingerprinter,
            acoustid_client=acoustid_client,
            ai_analyzer=ai_analyzer,
            preselect_confidence=self.config.preselect_confidence,
        )

    def _build_ui(self) -> None:
        root = QWidget(self)
        outer = QVBoxLayout(root)

        toolbar = QHBoxLayout()
        self.add_files_button = QPushButton("Add Files")
        self.add_folder_button = QPushButton("Add Folder")
        self.analyze_button = QPushButton("Analyze")
        self.apply_button = QPushButton("Apply Selected")
        self.undo_button = QPushButton("Undo Last")
        self.apply_button.setEnabled(False)
        self.mode_label = QLabel("Preview mode · nothing is written until Apply Selected")
        self.mode_label.setStyleSheet("font-weight: 600;")
        for button in (
            self.add_files_button,
            self.add_folder_button,
            self.analyze_button,
            self.apply_button,
            self.undo_button,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.mode_label)
        outer.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.track_table = QTableWidget(0, 5)
        self.track_table.setHorizontalHeaderLabels(
            ["Apply", "File", "Artist / Title", "Status", "Confidence"]
        )
        self.track_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.track_table.setAlternatingRowColors(True)
        self.track_table.horizontalHeader().setStretchLastSection(True)
        splitter.addWidget(self.track_table)

        self.inspector_tabs = QTabWidget()
        self.current_table = self._make_detail_table()
        self.proposed_table = self._make_detail_table()
        self.evidence_table = QTableWidget(0, 2)
        self.evidence_table.setHorizontalHeaderLabels(["Evidence", "Value"])
        self.evidence_table.horizontalHeader().setStretchLastSection(True)
        self.inspector_tabs.addTab(self.current_table, "Current")
        self.inspector_tabs.addTab(self.proposed_table, "Proposed")
        self.inspector_tabs.addTab(self.evidence_table, "Evidence")
        splitter.addWidget(self.inspector_tabs)
        splitter.setSizes([700, 480])
        outer.addWidget(splitter, 1)

        status = QHBoxLayout()
        self.status_label = QLabel(self._provider_status_text())
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        status.addWidget(self.status_label, 1)
        status.addWidget(self.progress)
        outer.addLayout(status)

        self.setCentralWidget(root)
        self.add_files_button.clicked.connect(self._choose_files)
        self.add_folder_button.clicked.connect(self._choose_folder)
        self.analyze_button.clicked.connect(self.analyze_all)
        self.apply_button.clicked.connect(self.apply_selected)
        self.undo_button.clicked.connect(self.undo_last)
        self.track_table.itemSelectionChanged.connect(self._show_selected_track)
        self.track_table.itemChanged.connect(self._refresh_apply_state)

    @staticmethod
    def _make_detail_table() -> QTableWidget:
        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Field", "Value"])
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _provider_status_text(self) -> str:
        parts = ["iTunes: on" if self.config.enable_itunes else "iTunes: off"]
        parts.append("AcoustID: on" if self.config.enable_acoustid else "AcoustID: off")
        parts.append("Local AI: on" if self.config.enable_ai else "Local AI: off")
        return " · ".join(parts)

    def _choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Add music files",
            "",
            "Audio (*.mp3 *.flac *.m4a *.mp4 *.ogg *.opus *.wav *.aiff *.aif)",
        )
        if files:
            self.add_paths([Path(item) for item in files])

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Add music folder")
        if folder:
            self.add_paths([Path(folder)])

    def add_paths(self, paths) -> None:
        known = {track.path.resolve() for track in self.tracks}
        errors = []
        for path in discover_audio_files(paths):
            if path.resolve() in known:
                continue
            try:
                track = self.tag_io.read_track(path)
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
                continue
            self.tracks.append(track)
            known.add(path.resolve())
            self._append_track_row(track)
        if errors:
            self.status_label.setText(" | ".join(errors[:3]))

    def _append_track_row(self, track) -> None:
        row = self.track_table.rowCount()
        self.track_table.insertRow(row)
        apply_item = QTableWidgetItem()
        apply_item.setFlags(apply_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        apply_item.setCheckState(Qt.CheckState.Unchecked)
        apply_item.setData(Qt.ItemDataRole.UserRole, str(track.path))
        self.track_table.setItem(row, 0, apply_item)
        self.track_table.setItem(row, 1, QTableWidgetItem(track.path.name))
        hint = " — ".join(
            part for part in (track.tags.artist or track.filename_hints.artist, track.tags.title or track.filename_hints.title) if part
        )
        self.track_table.setItem(row, 2, QTableWidgetItem(hint))
        self.track_table.setItem(row, 3, QTableWidgetItem("Queued"))
        self.track_table.setItem(row, 4, QTableWidgetItem("—"))

    def analyze_all(self) -> None:
        if not self.tracks:
            return
        self._pending = len(self.tracks)
        self.progress.setRange(0, len(self.tracks))
        self.progress.setValue(0)
        for track in self.tracks:
            worker = AnalysisWorker(self.pipeline, track)
            self._workers.add(worker)
            worker.signals.result.connect(self._analysis_ready)
            worker.signals.error.connect(self._analysis_worker_error)
            worker.signals.finished.connect(lambda w=worker: self._analysis_finished(w))
            self.thread_pool.start(worker)

    def _analysis_ready(self, result: AnalysisResult) -> None:
        self.results[result.track.path.resolve()] = result
        row = self._row_for_path(result.track.path)
        if row is None:
            return
        self.track_table.item(row, 3).setText("Ready" if not result.errors else "Ready · warnings")
        self.track_table.item(row, 4).setText(f"{result.match.confidence:.1%}" if result.match else "No match")
        apply_item = self.track_table.item(row, 0)
        apply_item.setCheckState(
            Qt.CheckState.Checked if result.preselected and result.changes else Qt.CheckState.Unchecked
        )
        if self.track_table.currentRow() == row:
            self._show_result(result)

    def _analysis_worker_error(self, detail: str) -> None:
        self.status_label.setText("Analysis worker error; see terminal/log output")
        print(detail)

    def _analysis_finished(self, worker: AnalysisWorker) -> None:
        self._workers.discard(worker)
        completed = self.progress.maximum() - len(self._workers)
        self.progress.setValue(max(0, completed))
        self._pending = max(0, self._pending - 1)

    def _row_for_path(self, path: Path) -> int | None:
        target = str(path.resolve())
        for row in range(self.track_table.rowCount()):
            item = self.track_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == target:
                return row
        return None

    def _refresh_apply_state(self, _item=None) -> None:
        enabled = False
        for row in range(self.track_table.rowCount()):
            item = self.track_table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                path = Path(item.data(Qt.ItemDataRole.UserRole))
                result = self.results.get(path.resolve())
                if result and result.changes:
                    enabled = True
                    break
        self.apply_button.setEnabled(enabled)

    def apply_selected(self) -> None:
        applied = 0
        for row in range(self.track_table.rowCount()):
            item = self.track_table.item(row, 0)
            if not item or item.checkState() != Qt.CheckState.Checked:
                continue
            path = Path(item.data(Qt.ItemDataRole.UserRole))
            result = self.results.get(path.resolve())
            if result is None or not result.changes:
                continue
            self.history.record(path, result.changes)
            self.tag_io.write_fields(path, {change.field: change.new for change in result.changes})
            self.track_table.item(row, 3).setText("Applied")
            item.setCheckState(Qt.CheckState.Unchecked)
            applied += 1
        if applied:
            self.status_label.setText(f"Applied metadata to {applied} track(s). Undo Last is available.")
        self._refresh_apply_state()

    def undo_last(self) -> None:
        try:
            entry = self.history.undo_last(self.tag_io)
        except Exception as exc:
            QMessageBox.critical(self, "Undo failed", str(exc))
            return
        if entry is None:
            self.status_label.setText("Nothing to undo.")
            return
        self.status_label.setText(f"Undid Music- metadata changes for {entry.path.name}")

    def _show_selected_track(self) -> None:
        row = self.track_table.currentRow()
        if row < 0:
            return
        item = self.track_table.item(row, 0)
        if item is None:
            return
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        result = self.results.get(path.resolve())
        if result is not None:
            self._show_result(result)
        else:
            track = next((t for t in self.tracks if t.path.resolve() == path.resolve()), None)
            if track is not None:
                self._populate_tags(self.current_table, track.tags)
                self.proposed_table.setRowCount(0)
                self.evidence_table.setRowCount(0)

    def _show_result(self, result: AnalysisResult) -> None:
        self._populate_tags(self.current_table, result.track.tags)
        self._populate_tags(self.proposed_table, result.proposed_tags)
        evidence = []
        if result.match:
            evidence.extend(
                [
                    ("Winning source", result.match.candidate.source),
                    ("Confidence", f"{result.match.confidence:.1%}"),
                    ("Band", result.confidence_band),
                ]
            )
        if result.ai:
            if result.ai.genres:
                evidence.append(("AI genre", f"{result.ai.genres[0][0]} ({result.ai.genres[0][1]:.1%})"))
            if result.ai.moods:
                evidence.append(("AI mood", f"{result.ai.moods[0][0]} ({result.ai.moods[0][1]:.1%})"))
        for error in result.errors:
            evidence.append(("Warning", error))
        self.evidence_table.setRowCount(len(evidence))
        for row, (name, value) in enumerate(evidence):
            self.evidence_table.setItem(row, 0, QTableWidgetItem(name))
            self.evidence_table.setItem(row, 1, QTableWidgetItem(value))

    @staticmethod
    def _populate_tags(table: QTableWidget, tags: TrackTags) -> None:
        rows = [(item.name.replace("_", " ").title(), getattr(tags, item.name)) for item in fields(TrackTags)]
        table.setRowCount(len(rows))
        for row, (name, value) in enumerate(rows):
            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem(value or ""))

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self.add_paths(paths)
        event.acceptProposedAction()
