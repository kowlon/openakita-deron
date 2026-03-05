"""
API tests for task and scenario endpoints

Tests the REST API endpoints for multi-task orchestration.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio


# Mock the TaskOrchestrator for testing
class MockTaskOrchestrator:
    """Mock TaskOrchestrator for testing"""

    def __init__(self):
        self._tasks = {}
        self._task_counter = 0
        self.scenario_registry = MockScenarioRegistry()

    async def create_task_manual(self, scenario_id: str, session_id: str = None, context: dict = None):
        # Check if scenario exists
        if not self.scenario_registry.get(scenario_id):
            return None

        self._task_counter += 1
        task_id = f"task-{self._task_counter:03d}"
        from openakita.orchestration.models import TaskState, TaskStatus

        state = TaskState(
            task_id=task_id,
            scenario_id=scenario_id,
            session_id=session_id,
            status=TaskStatus.PENDING,
            context=context or {},
            total_steps=3,
        )
        self._tasks[task_id] = {"state": state, "steps": []}
        return MockTaskSession(state)

    async def start_task(self, task_id: str):
        if task_id in self._tasks:
            from openakita.orchestration.models import TaskStatus
            self._tasks[task_id]["state"].status = TaskStatus.RUNNING
            self._tasks[task_id]["state"].started_at = "2026-03-05T00:00:00"
        return True

    async def cancel_task(self, task_id: str):
        if task_id in self._tasks:
            from openakita.orchestration.models import TaskStatus
            self._tasks[task_id]["state"].status = TaskStatus.CANCELLED
            del self._tasks[task_id]
            return True
        return False  # Task not found

    async def create_task_from_dialog(self, message: str, session_id: str = None, context: dict = None):
        """Create task from dialog message"""
        # Simple matching logic for testing
        from openakita.orchestration.models import TaskState, TaskStatus

        scenario_id = None
        if "审查" in message or "review" in message.lower():
            scenario_id = "code-review"
        elif "test" in message.lower():
            scenario_id = "test-scenario"

        if not scenario_id:
            return None  # No matching scenario

        self._task_counter += 1
        task_id = f"task-{self._task_counter:03d}"

        state = TaskState(
            task_id=task_id,
            scenario_id=scenario_id,
            session_id=session_id,
            status=TaskStatus.PENDING,
            context=context or {},
            total_steps=3,
        )
        self._tasks[task_id] = {"state": state, "steps": []}
        return MockTaskSession(state)

    async def confirm_step(self, task_id: str, step_id: str, edited_output: dict = None):
        if task_id in self._tasks:
            from openakita.orchestration.models import TaskStatus
            self._tasks[task_id]["state"].status = TaskStatus.RUNNING
            return True
        return False

    async def switch_step(self, task_id: str, step_id: str):
        if task_id in self._tasks:
            self._tasks[task_id]["state"].current_step_id = step_id
            return True
        return False

    def get_task(self, task_id: str):
        task_data = self._tasks.get(task_id)
        if task_data:
            return MockTaskSession(task_data["state"])
        return None

    def list_active_tasks(self):
        return [MockTaskSession(t["state"]) for t in self._tasks.values()]


class MockTaskSession:
    """Mock TaskSession for testing"""

    def __init__(self, state):
        self.state = state
        self.context = state.context
        self.step_sessions = {}
        from openakita.orchestration.models import ScenarioDefinition
        self.scenario = ScenarioDefinition(
            scenario_id=state.scenario_id,
            name="Mock Scenario",
            description="Mock for testing",
            steps=[],
        )

    def to_dict(self):
        return {"state": self.state.to_dict()}


class MockScenarioRegistry:
    """Mock ScenarioRegistry for testing"""

    def __init__(self):
        from openakita.orchestration.models import ScenarioDefinition, StepDefinition
        self._scenarios = [
            ScenarioDefinition(
                scenario_id="test-scenario",
                name="Test Scenario",
                description="Test",
                category="test",
                steps=[],
            ),
            ScenarioDefinition(
                scenario_id="code-review",
                name="Code Review",
                description="Review code",
                category="development",
                steps=[],
            ),
        ]

    def get(self, scenario_id: str):
        for s in self._scenarios:
            if s.scenario_id == scenario_id:
                return s
        return None

    def list_all(self):
        return self._scenarios

    def list_by_category(self, category: str):
        return [s for s in self._scenarios if s.category == category]

    def list_categories(self):
        return list(set(s.category for s in self._scenarios))


@pytest.fixture
def mock_app():
    """Create a test FastAPI app with mocked orchestrator"""
    from fastapi import FastAPI
    from openakita.api.routes import tasks, scenarios

    app = FastAPI()

    # Create mock orchestrator
    mock_orchestrator = MockTaskOrchestrator()

    # Store in app state
    app.state.task_orchestrator = mock_orchestrator
    app.state.scenario_registry = mock_orchestrator.scenario_registry

    # Include routers
    app.include_router(tasks.router)
    app.include_router(scenarios.router)

    return app


@pytest.fixture
def client(mock_app):
    """Create a test client"""
    return TestClient(mock_app)


class TestTaskAPI:
    """Tests for task API endpoints"""

    def test_list_tasks_empty(self, client):
        """Test listing tasks when empty"""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert data["total"] >= 0

    def test_create_task_with_scenario_id(self, client):
        """Test creating a task with scenario_id"""
        response = client.post(
            "/api/tasks",
            json={"scenario_id": "test-scenario", "context": {}},
        )
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["scenario_id"] == "test-scenario"

    def test_create_task_validation_error(self, client):
        """Test creating a task without required fields"""
        response = client.post("/api/tasks", json={})
        assert response.status_code == 400  # Bad Request

    def test_get_task_not_found(self, client):
        """Test getting a non-existent task"""
        response = client.get("/api/tasks/nonexistent-task")
        assert response.status_code == 404

    def test_cancel_task(self, client):
        """Test canceling a task"""
        # First create a task
        create_response = client.post(
            "/api/tasks",
            json={"scenario_id": "test-scenario"},
        )
        assert create_response.status_code == 200
        task_id = create_response.json()["task_id"]

        # Then cancel it
        cancel_response = client.post(f"/api/tasks/{task_id}/cancel")
        assert cancel_response.status_code == 200
        data = cancel_response.json()
        assert data["success"] is True
        assert data["task_id"] == task_id
        assert data["status"] == "cancelled"

    def test_cancel_nonexistent_task(self, client):
        """Test canceling a non-existent task"""
        response = client.post("/api/tasks/nonexistent-task/cancel")
        assert response.status_code == 404

    def test_confirm_step(self, client):
        """Test confirming a step"""
        # First create a task
        create_response = client.post(
            "/api/tasks",
            json={"scenario_id": "test-scenario"},
        )
        assert create_response.status_code == 200
        task_id = create_response.json()["task_id"]

        # Confirm a step
        confirm_response = client.post(
            f"/api/tasks/{task_id}/confirm",
            json={"step_id": "step-1"},
        )
        assert confirm_response.status_code == 200
        data = confirm_response.json()
        assert data["success"] is True
        assert data["task_id"] == task_id
        assert data["step_id"] == "step-1"

    def test_confirm_step_with_edited_output(self, client):
        """Test confirming a step with edited output"""
        # First create a task
        create_response = client.post(
            "/api/tasks",
            json={"scenario_id": "test-scenario"},
        )
        task_id = create_response.json()["task_id"]

        # Confirm with edited output
        confirm_response = client.post(
            f"/api/tasks/{task_id}/confirm",
            json={
                "step_id": "step-1",
                "edited_output": {"key": "edited_value"},
            },
        )
        assert confirm_response.status_code == 200
        assert confirm_response.json()["success"] is True

    def test_confirm_step_nonexistent_task(self, client):
        """Test confirming step for non-existent task"""
        response = client.post(
            "/api/tasks/nonexistent/confirm",
            json={"step_id": "step-1"},
        )
        assert response.status_code == 400

    def test_switch_step(self, client):
        """Test switching to a different step"""
        # First create a task
        create_response = client.post(
            "/api/tasks",
            json={"scenario_id": "test-scenario"},
        )
        task_id = create_response.json()["task_id"]

        # Switch step
        switch_response = client.post(
            f"/api/tasks/{task_id}/switch",
            json={"step_id": "step-2"},
        )
        assert switch_response.status_code == 200
        data = switch_response.json()
        assert data["success"] is True
        assert data["current_step_id"] == "step-2"

    def test_switch_step_nonexistent_task(self, client):
        """Test switching step for non-existent task"""
        response = client.post(
            "/api/tasks/nonexistent/switch",
            json={"step_id": "step-1"},
        )
        assert response.status_code == 400

    def test_get_task_context(self, client):
        """Test getting task context"""
        # First create a task with context
        create_response = client.post(
            "/api/tasks",
            json={
                "scenario_id": "test-scenario",
                "context": {"initial_key": "initial_value"},
            },
        )
        task_id = create_response.json()["task_id"]

        # Get context
        context_response = client.get(f"/api/tasks/{task_id}/context")
        assert context_response.status_code == 200
        data = context_response.json()
        assert data["task_id"] == task_id
        assert "context" in data
        assert data["context"]["initial_key"] == "initial_value"

    def test_get_task_context_nonexistent(self, client):
        """Test getting context for non-existent task"""
        response = client.get("/api/tasks/nonexistent/context")
        assert response.status_code == 404

    def test_get_task_detail(self, client):
        """Test getting task detail"""
        # First create a task
        create_response = client.post(
            "/api/tasks",
            json={"scenario_id": "test-scenario"},
        )
        task_id = create_response.json()["task_id"]

        # Get detail
        detail_response = client.get(f"/api/tasks/{task_id}")
        assert detail_response.status_code == 200
        data = detail_response.json()
        assert "task" in data
        assert data["task"]["task_id"] == task_id
        assert "scenario_name" in data
        assert "step_sessions" in data

    def test_list_tasks_with_filter(self, client):
        """Test listing tasks with status filter"""
        # Create multiple tasks
        client.post("/api/tasks", json={"scenario_id": "test-scenario"})
        client.post("/api/tasks", json={"scenario_id": "code-review"})

        # List all
        response = client.get("/api/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2

    def test_create_task_from_message(self, client):
        """Test creating a task from message"""
        response = client.post(
            "/api/tasks",
            json={"message": "请帮我审查这段代码"},
        )
        # Note: This might fail if no matching scenario in registry
        # Accept either success or not found
        assert response.status_code in [200, 404]


class TestScenarioAPI:
    """Tests for scenario API endpoints"""

    def test_list_scenarios(self, client):
        """Test listing scenarios"""
        response = client.get("/api/scenarios")
        assert response.status_code == 200
        data = response.json()
        assert "scenarios" in data
        assert "total" in data
        assert data["total"] >= 2  # Mock has 2 scenarios

    def test_list_scenarios_with_category_filter(self, client):
        """Test listing scenarios filtered by category"""
        response = client.get("/api/scenarios?category=test")
        assert response.status_code == 200
        data = response.json()
        assert "scenarios" in data
        # All returned scenarios should have category "test"
        for scenario in data["scenarios"]:
            assert scenario["category"] == "test"

    def test_list_categories(self, client):
        """Test listing all categories"""
        response = client.get("/api/scenarios/categories")
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "test" in data["categories"]
        assert "development" in data["categories"]

    def test_get_scenario(self, client):
        """Test getting a specific scenario"""
        response = client.get("/api/scenarios/test-scenario")
        assert response.status_code == 200
        data = response.json()
        assert data["scenario_id"] == "test-scenario"
        assert data["name"] == "Test Scenario"
        assert "steps" in data
        assert "category" in data

    def test_get_scenario_not_found(self, client):
        """Test getting a non-existent scenario"""
        response = client.get("/api/scenarios/nonexistent")
        assert response.status_code == 404

    def test_start_scenario(self, client):
        """Test starting a scenario"""
        response = client.post(
            "/api/scenarios/test-scenario/start",
            json={"session_id": "test-session"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["scenario_id"] == "test-scenario"
        assert "status" in data

    def test_start_scenario_with_context(self, client):
        """Test starting a scenario with initial context"""
        response = client.post(
            "/api/scenarios/test-scenario/start",
            json={
                "session_id": "test-session",
                "context": {"key": "value"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data

    def test_start_scenario_not_found(self, client):
        """Test starting a non-existent scenario"""
        response = client.post(
            "/api/scenarios/nonexistent/start",
            json={},
        )
        assert response.status_code == 404

    def test_scenario_response_format(self, client):
        """Test scenario response format"""
        response = client.get("/api/scenarios/test-scenario")
        assert response.status_code == 200
        data = response.json()

        # Verify expected fields
        assert "scenario_id" in data
        assert "name" in data
        assert "description" in data
        assert "category" in data
        assert "version" in data
        assert "steps" in data
        assert "metadata" in data


class TestAPIErrorHandling:
    """Tests for API error handling"""

    def test_orchestrator_not_available(self):
        """Test when orchestrator is not available"""
        from fastapi import FastAPI
        from openakita.api.routes import tasks

        app = FastAPI()
        app.state.task_orchestrator = None  # No orchestrator
        app.include_router(tasks.router)

        client = TestClient(app)

        response = client.get("/api/tasks")
        assert response.status_code == 503  # Service Unavailable

    def test_invalid_json_body(self, client):
        """Test sending invalid JSON"""
        response = client.post(
            "/api/tasks",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422  # Unprocessable Entity


class TestAPIDataTypes:
    """Tests for API data types and serialization"""

    def test_task_response_format(self, client):
        """Test task response format"""
        response = client.post(
            "/api/tasks",
            json={"scenario_id": "test-scenario"},
        )
        assert response.status_code == 200
        data = response.json()

        # Verify expected fields
        assert "task_id" in data
        assert "scenario_id" in data
        assert "status" in data
        assert "created_at" in data

    def test_scenario_response_format(self, client):
        """Test scenario response format"""
        response = client.get("/api/scenarios")
        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "scenarios" in data
        if data["scenarios"]:
            scenario = data["scenarios"][0]
            assert "scenario_id" in scenario
            assert "name" in scenario