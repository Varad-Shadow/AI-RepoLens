"""Unit tests for evidence-based technology detection."""

from __future__ import annotations

from repolens.analyzer.tech_detect import detect_technologies


def test_dependency_detection_is_confirmed_with_evidence() -> None:
    detections = detect_technologies(
        ["requirements.txt"],
        dependencies={"python": ["flask", "pytest"]},
    )

    by_name = {item.name: item for item in detections}
    assert by_name["Flask"].confidence == "confirmed"
    assert by_name["Flask"].evidence
    assert by_name["pytest"].confidence == "confirmed"


def test_config_marker_detection_is_confirmed() -> None:
    detections = detect_technologies(["next.config.js", "Dockerfile"])
    by_name = {item.name: item for item in detections}

    assert by_name["Next.js"].confidence == "confirmed"
    assert by_name["Docker"].confidence == "confirmed"


def test_directory_convention_detection_is_likely() -> None:
    detections = detect_technologies(["app/models/user.rb", "app/controllers/users.rb"])

    assert detections[0].name == "MVC-style application"
    assert detections[0].confidence == "likely"


def test_import_only_detection_is_possible() -> None:
    detections = detect_technologies(
        ["src/app.py"],
        file_contents={"src/app.py": "from fastapi import FastAPI\n"},
    )

    assert detections[0].name == "FastAPI"
    assert detections[0].confidence == "possible"


def test_confirmed_confidence_wins_over_import_only() -> None:
    detections = detect_technologies(
        ["requirements.txt", "src/app.py"],
        dependencies={"python": ["fastapi"]},
        file_contents={"src/app.py": "from fastapi import FastAPI\n"},
    )

    assert detections[0].name == "FastAPI"
    assert detections[0].confidence == "confirmed"
    assert len(detections[0].evidence) == 2


def test_every_detection_has_evidence() -> None:
    detections = detect_technologies(
        ["package.json", "src/main.tsx"],
        dependencies={"javascript": ["react"]},
    )

    assert detections
    assert all(item.evidence for item in detections)