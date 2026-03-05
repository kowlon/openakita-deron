"""
Unit tests for Demo Skills

Tests the four demo skills used for multi-task orchestration testing:
- demo-echo-json: JSON echo with trace info
- demo-context-hash: SHA256 digest calculation
- demo-json-diff: JSON comparison
- demo-schema-check: Schema validation
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


# Get the skills directory
SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"


class TestDemoEchoJson:
    """Test demo-echo-json skill"""

    @pytest.fixture
    def script_path(self):
        return SKILLS_DIR / "demo-echo-json" / "scripts" / "echo.py"

    def test_basic_echo(self, script_path):
        """Test basic JSON echo"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"test": "value"}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["ok"] is True
        assert output["payload"]["test"] == "value"

    def test_trace_id_passthrough(self, script_path):
        """Test trace_id is passed through"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"trace_id": "test-trace-001"}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["trace_id"] == "test-trace-001"

    def test_received_at_timestamp(self, script_path):
        """Test received_at timestamp is present"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"data": "test"}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "received_at" in output
        assert "T" in output["received_at"]  # ISO format

    def test_repeat_parameter(self, script_path):
        """Test --repeat parameter adds __repeat__ field"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"x": 1}', "--repeat", "3"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["payload"]["__repeat__"] == 3

    def test_invalid_json(self, script_path):
        """Test invalid JSON input"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", "not valid json"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 2
        assert "invalid json" in result.stderr

    def test_non_object_input(self, script_path):
        """Test non-object JSON input"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '[1, 2, 3]'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 2
        assert "must be a JSON object" in result.stderr

    def test_nested_json(self, script_path):
        """Test nested JSON object"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"outer": {"inner": {"deep": "value"}}}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["payload"]["outer"]["inner"]["deep"] == "value"

    def test_unicode_handling(self, script_path):
        """Test Unicode characters in JSON"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"message": "你好世界"}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["payload"]["message"] == "你好世界"


class TestDemoContextHash:
    """Test demo-context-hash skill"""

    @pytest.fixture
    def script_path(self):
        return SKILLS_DIR / "demo-context-hash" / "scripts" / "hash.py"

    def test_sha256_hash(self, script_path):
        """Test SHA256 hash calculation"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"text": "hello"}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["ok"] is True
        assert output["algorithm"] == "sha256"
        assert len(output["digest"]) == 64  # SHA256 hex length
        assert output["length"] == 5

    def test_sha256_known_value(self, script_path):
        """Test SHA256 produces known value"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"text": "hello", "algorithm": "sha256"}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        # Known SHA256 of "hello"
        assert output["digest"] == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    def test_sha512_algorithm(self, script_path):
        """Test SHA512 algorithm"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"text": "test", "algorithm": "sha512"}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["algorithm"] == "sha512"
        assert len(output["digest"]) == 128  # SHA512 hex length

    def test_md5_algorithm(self, script_path):
        """Test MD5 algorithm"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"text": "test", "algorithm": "md5"}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["algorithm"] == "md5"
        assert len(output["digest"]) == 32  # MD5 hex length

    def test_empty_text(self, script_path):
        """Test empty text"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"text": ""}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["ok"] is True
        assert output["length"] == 0

    def test_unsupported_algorithm(self, script_path):
        """Test unsupported algorithm"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"text": "test", "algorithm": "unknown"}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 2
        assert "unsupported algorithm" in result.stderr

    def test_text_length_tracking(self, script_path):
        """Test text length is tracked"""
        test_text = "a" * 1000
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", json.dumps({"text": test_text})],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["length"] == 1000

    def test_unicode_text(self, script_path):
        """Test Unicode text handling"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"text": "你好世界"}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["ok"] is True
        assert output["length"] == 4  # 4 Chinese characters


class TestDemoJsonDiff:
    """Test demo-json-diff skill"""

    @pytest.fixture
    def script_path(self):
        return SKILLS_DIR / "demo-json-diff" / "scripts" / "diff.py"

    def test_no_difference(self, script_path):
        """Test identical objects have no difference"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"before": {"a": 1}, "after": {"a": 1}}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["ok"] is True
        assert output["changed_paths"] == []
        assert output["counts"]["modified"] == 0

    def test_modified_value(self, script_path):
        """Test modified value detection"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"before": {"a": 1}, "after": {"a": 2}}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "a" in output["changed_paths"]
        assert output["counts"]["modified"] == 1

    def test_added_field(self, script_path):
        """Test added field detection"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"before": {"a": 1}, "after": {"a": 1, "b": 2}}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "b" in output["changed_paths"]
        assert output["counts"]["added"] == 1

    def test_removed_field(self, script_path):
        """Test removed field detection"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"before": {"a": 1, "b": 2}, "after": {"a": 1}}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "b" in output["changed_paths"]
        assert output["counts"]["removed"] == 1

    def test_nested_changes(self, script_path):
        """Test nested object changes"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"before": {"outer": {"inner": 1}}, "after": {"outer": {"inner": 2}}}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "outer.inner" in output["changed_paths"]

    def test_list_changes(self, script_path):
        """Test list changes"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"before": [1, 2, 3], "after": [1, 4, 3]}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["counts"]["modified"] >= 1

    def test_list_length_change(self, script_path):
        """Test list length change"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"before": [1, 2], "after": [1, 2, 3]}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["counts"]["added"] == 1

    def test_summary_format(self, script_path):
        """Test summary string format"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"before": {"a": 1, "b": 2}, "after": {"a": 1, "c": 3}}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "modified=" in output["summary"]
        assert "added=" in output["summary"]
        assert "removed=" in output["summary"]


class TestDemoSchemaCheck:
    """Test demo-schema-check skill"""

    @pytest.fixture
    def script_path(self):
        return SKILLS_DIR / "demo-schema-check" / "scripts" / "check.py"

    def test_valid_draft_v1(self, script_path):
        """Test valid demo_draft_v1 schema"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"schema_id": "demo_draft_v1", "data": {"title": "Test", "bullets": ["a", "b"]}}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["ok"] is True
        assert output["errors"] == []

    def test_valid_final_v1(self, script_path):
        """Test valid demo_final_v1 schema"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"schema_id": "demo_final_v1", "data": {"title": "Test", "bullets": ["a"], "approved": true}}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["ok"] is True
        assert output["errors"] == []

    def test_missing_title(self, script_path):
        """Test missing required field"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"schema_id": "demo_draft_v1", "data": {"bullets": ["a"]}}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 3  # Validation failed
        output = json.loads(result.stdout)
        assert output["ok"] is False
        assert any("title" in e for e in output["errors"])

    def test_missing_bullets(self, script_path):
        """Test missing bullets field"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"schema_id": "demo_draft_v1", "data": {"title": "Test"}}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 3
        output = json.loads(result.stdout)
        assert output["ok"] is False
        assert any("bullets" in e for e in output["errors"])

    def test_wrong_type_bullets(self, script_path):
        """Test wrong type for bullets"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"schema_id": "demo_draft_v1", "data": {"title": "Test", "bullets": "not array"}}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 3
        output = json.loads(result.stdout)
        assert any("bullets" in e and "array" in e for e in output["errors"])

    def test_final_v1_missing_approved(self, script_path):
        """Test demo_final_v1 missing approved field"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"schema_id": "demo_final_v1", "data": {"title": "Test", "bullets": ["a"]}}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 3
        output = json.loads(result.stdout)
        assert any("approved" in e for e in output["errors"])

    def test_unknown_schema(self, script_path):
        """Test unknown schema_id"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"schema_id": "unknown_schema", "data": {}}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 3  # Script exits with 3 for errors
        output = json.loads(result.stdout)
        assert output["ok"] is False
        assert any("unknown schema_id" in e for e in output["errors"])

    def test_approved_wrong_type(self, script_path):
        """Test approved field wrong type"""
        result = subprocess.run(
            [sys.executable, str(script_path), "--json", '{"schema_id": "demo_final_v1", "data": {"title": "Test", "bullets": ["a"], "approved": "yes"}}'],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 3
        output = json.loads(result.stdout)
        assert any("approved" in e and "boolean" in e for e in output["errors"])


class TestDemoSkillsIntegration:
    """Integration tests combining multiple demo skills"""

    @pytest.fixture
    def echo_script(self):
        return SKILLS_DIR / "demo-echo-json" / "scripts" / "echo.py"

    @pytest.fixture
    def hash_script(self):
        return SKILLS_DIR / "demo-context-hash" / "scripts" / "hash.py"

    @pytest.fixture
    def diff_script(self):
        return SKILLS_DIR / "demo-json-diff" / "scripts" / "diff.py"

    @pytest.fixture
    def check_script(self):
        return SKILLS_DIR / "demo-schema-check" / "scripts" / "check.py"

    def test_echo_to_hash_flow(self, echo_script, hash_script):
        """Test flow from echo to hash (simulating context passing)"""
        # Step 1: Generate JSON with echo
        echo_result = subprocess.run(
            [sys.executable, str(echo_script), "--json", '{"trace_id": "flow-test", "data": "test"}'],
            capture_output=True,
            text=True,
        )
        assert echo_result.returncode == 0
        echo_output = json.loads(echo_result.stdout)

        # Step 2: Use echo output as input to hash
        hash_result = subprocess.run(
            [sys.executable, str(hash_script), "--json", json.dumps({"text": json.dumps(echo_output)})],
            capture_output=True,
            text=True,
        )
        assert hash_result.returncode == 0
        hash_output = json.loads(hash_result.stdout)

        # Verify flow
        assert echo_output["trace_id"] == "flow-test"
        assert hash_output["ok"] is True
        assert hash_output["length"] > 0

    def test_diff_detects_echo_change(self, echo_script, diff_script):
        """Test diff can detect changes in echo output"""
        # Generate original
        original_result = subprocess.run(
            [sys.executable, str(echo_script), "--json", '{"value": 1}'],
            capture_output=True,
            text=True,
        )
        original = json.loads(original_result.stdout)

        # Generate modified
        modified_result = subprocess.run(
            [sys.executable, str(echo_script), "--json", '{"value": 2}'],
            capture_output=True,
            text=True,
        )
        modified = json.loads(modified_result.stdout)

        # Compare
        diff_result = subprocess.run(
            [sys.executable, str(diff_script), "--json", json.dumps({
                "before": original["payload"],
                "after": modified["payload"]
            })],
            capture_output=True,
            text=True,
        )
        diff_output = json.loads(diff_result.stdout)

        assert "value" in diff_output["changed_paths"]
        assert diff_output["counts"]["modified"] == 1

    def test_schema_validates_echo_output(self, echo_script, check_script):
        """Test schema check validates echo output"""
        # Generate valid data
        echo_result = subprocess.run(
            [sys.executable, str(echo_script), "--json", '{"title": "My Title", "bullets": ["item1", "item2"]}'],
            capture_output=True,
            text=True,
        )
        echo_output = json.loads(echo_result.stdout)

        # Validate against schema
        check_result = subprocess.run(
            [sys.executable, str(check_script), "--json", json.dumps({
                "schema_id": "demo_draft_v1",
                "data": echo_output["payload"]
            })],
            capture_output=True,
            text=True,
        )
        check_output = json.loads(check_result.stdout)

        assert check_output["ok"] is True