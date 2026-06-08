"""Tests for ``parrotia.formats`` — all output serializers and the WRITERS registry."""

from __future__ import annotations

import json

import pytest

from parrotia.formats import (
    WRITERS,
    _format_timestamp,
    to_json,
    to_markdown,
    to_srt,
    to_txt,
    to_vtt,
)
from parrotia.transcriber import Segment, TranscriptionResult


# ===================================================================
# Timestamp formatting
# ===================================================================


class TestFormatTimestamp:
    def test_zero(self):
        assert _format_timestamp(0.0, separator=",") == "00:00:00,000"

    def test_negative_clamps_to_zero(self):
        assert _format_timestamp(-5.0, separator=",") == "00:00:00,000"

    def test_simple_seconds(self):
        assert _format_timestamp(1.5, separator=",") == "00:00:01,500"

    def test_minutes(self):
        assert _format_timestamp(65.0, separator=".") == "00:01:05.000"

    def test_hours(self):
        assert _format_timestamp(3661.123, separator=",") == "01:01:01,123"

    def test_dot_separator(self):
        assert _format_timestamp(0.5, separator=".") == "00:00:00.500"

    def test_large_value(self):
        # 2 h 30 m 15 s 750 ms
        assert _format_timestamp(9015.75, separator=",") == "02:30:15,750"

    def test_rounding(self):
        # 1.9999 s should round to 2.000
        assert _format_timestamp(1.9999, separator=",") == "00:00:02,000"


# ===================================================================
# Plain text writer
# ===================================================================


class TestToTxt:
    def test_basic(self, sample_result):
        txt = to_txt(sample_result)
        lines = txt.strip().split("\n")
        assert len(lines) == 3
        assert lines[0] == "Hello, this is a test."
        assert lines[2] == "Final segment of the audio."

    def test_ends_with_newline(self, sample_result):
        assert to_txt(sample_result).endswith("\n")

    def test_empty_segments(self, empty_result):
        txt = to_txt(empty_result)
        assert txt.strip() == ""

    def test_single_segment(self):
        r = TranscriptionResult(
            source_name="a.mp3",
            model="tiny",
            language="en",
            duration=5.0,
            segments=[Segment(0.0, 5.0, "Only line.")],
        )
        assert to_txt(r).strip() == "Only line."


# ===================================================================
# Markdown writer
# ===================================================================


class TestToMarkdown:
    def test_contains_header(self, sample_result):
        md = to_markdown(sample_result)
        assert "# Transcript — test_audio.mp3" in md

    def test_contains_model(self, sample_result):
        md = to_markdown(sample_result)
        assert "**Model:** tiny" in md

    def test_contains_language(self, sample_result):
        md = to_markdown(sample_result)
        assert "**Language:** en" in md

    def test_language_probability_shown(self, sample_result):
        md = to_markdown(sample_result)
        assert "confidence 98%" in md

    def test_no_probability_when_none(self, result_no_probability):
        md = to_markdown(result_no_probability)
        assert "confidence" not in md

    def test_contains_timestamps(self, sample_result):
        md = to_markdown(sample_result)
        assert "**[00:00:00.000]**" in md

    def test_ends_with_newline(self, sample_result):
        assert to_markdown(sample_result).endswith("\n")

    def test_empty_segments(self, empty_result):
        md = to_markdown(empty_result)
        assert "# Transcript" in md
        # Should still have metadata, just no timestamped lines


# ===================================================================
# SRT writer
# ===================================================================


class TestToSrt:
    def test_block_count(self, sample_result):
        srt = to_srt(sample_result)
        # Each block starts with a number; count numbered lines
        numbered = [ln for ln in srt.split("\n") if ln.strip().isdigit()]
        assert len(numbered) == 3

    def test_uses_comma_separator(self, sample_result):
        srt = to_srt(sample_result)
        assert "00:00:00,000 --> 00:00:10,500" in srt

    def test_sequential_indices(self, sample_result):
        srt = to_srt(sample_result)
        lines = srt.split("\n")
        indices = [int(ln) for ln in lines if ln.strip().isdigit()]
        assert indices == [1, 2, 3]

    def test_ends_with_newline(self, sample_result):
        assert to_srt(sample_result).endswith("\n")

    def test_no_webvtt_header(self, sample_result):
        srt = to_srt(sample_result)
        assert "WEBVTT" not in srt


# ===================================================================
# VTT writer
# ===================================================================


class TestToVtt:
    def test_starts_with_webvtt(self, sample_result):
        vtt = to_vtt(sample_result)
        assert vtt.startswith("WEBVTT")

    def test_uses_dot_separator(self, sample_result):
        vtt = to_vtt(sample_result)
        assert "00:00:00.000 --> 00:00:10.500" in vtt

    def test_block_count(self, sample_result):
        vtt = to_vtt(sample_result)
        numbered = [ln for ln in vtt.split("\n") if ln.strip().isdigit()]
        assert len(numbered) == 3

    def test_ends_with_newline(self, sample_result):
        assert to_vtt(sample_result).endswith("\n")


# ===================================================================
# JSON writer
# ===================================================================


class TestToJson:
    def test_valid_json(self, sample_result):
        raw = to_json(sample_result)
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_all_metadata_fields(self, sample_result):
        data = json.loads(to_json(sample_result))
        assert data["source"] == "test_audio.mp3"
        assert data["model"] == "tiny"
        assert data["language"] == "en"
        assert data["duration"] == 30.0
        assert data["language_probability"] == 0.98

    def test_segments_structure(self, sample_result):
        data = json.loads(to_json(sample_result))
        segs = data["segments"]
        assert len(segs) == 3
        assert all("start" in s and "end" in s and "text" in s for s in segs)

    def test_first_segment_values(self, sample_result):
        data = json.loads(to_json(sample_result))
        s = data["segments"][0]
        assert s["start"] == 0.0
        assert s["end"] == 10.5
        assert s["text"] == "Hello, this is a test."

    def test_null_probability(self, result_no_probability):
        data = json.loads(to_json(result_no_probability))
        assert data["language_probability"] is None

    def test_empty_segments(self, empty_result):
        data = json.loads(to_json(empty_result))
        assert data["segments"] == []

    def test_unicode_preserved(self):
        r = TranscriptionResult(
            source_name="日本語.mp3",
            model="tiny",
            language="ja",
            duration=1.0,
            segments=[Segment(0.0, 1.0, "こんにちは世界")],
        )
        data = json.loads(to_json(r))
        assert data["source"] == "日本語.mp3"
        assert data["segments"][0]["text"] == "こんにちは世界"

    def test_ends_with_newline(self, sample_result):
        assert to_json(sample_result).endswith("\n")


# ===================================================================
# WRITERS registry
# ===================================================================


class TestWritersRegistry:
    def test_all_formats_registered(self):
        expected = {"txt", "md", "srt", "vtt", "json"}
        assert set(WRITERS.keys()) == expected

    @pytest.mark.parametrize(
        "fmt,ext",
        [
            ("txt", ".txt"),
            ("md", ".md"),
            ("srt", ".srt"),
            ("vtt", ".vtt"),
            ("json", ".json"),
        ],
    )
    def test_extensions(self, fmt, ext):
        assert WRITERS[fmt][0] == ext

    @pytest.mark.parametrize("fmt", list(WRITERS.keys()))
    def test_all_writers_callable(self, fmt, sample_result):
        ext, writer = WRITERS[fmt]
        output = writer(sample_result)
        assert isinstance(output, str)
        assert len(output) > 0

    @pytest.mark.parametrize("fmt", list(WRITERS.keys()))
    def test_all_writers_handle_empty_result(self, fmt, empty_result):
        """Every writer must handle an empty result without crashing."""
        ext, writer = WRITERS[fmt]
        output = writer(empty_result)
        assert isinstance(output, str)
