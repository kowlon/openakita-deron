#!/bin/bash
# Test Data Setup Script
# Prepares test data and environment

set -e

echo "═══════════════════════════════════════════════════════════════"
echo "                    Setting Up Test Data                        "
echo "═══════════════════════════════════════════════════════════════"

# Create test scenarios directory
mkdir -p scenarios

# Create test demo flow scenario
cat > scenarios/test-demo-flow.yaml << 'EOF'
# Demo 技能流程测试场景

schema_version: "1.0"
scenario_id: "test-demo-flow"
name: "Demo 技能流程测试"
description: "Test flow with demo skills"
category: "test"
version: "1.0"

trigger_patterns:
  - type: keyword
    keywords:
      - "测试demo流程"
      - "demo flow test"
    priority: 1

steps:
  - step_id: "echo"
    name: "Generate Test Data"
    description: "Generate test data using demo-echo-json"
    output_key: "echo_result"
    requires_confirmation: false
    system_prompt: "Generate test data"

  - step_id: "hash"
    name: "Calculate Hash"
    description: "Calculate SHA256 hash"
    output_key: "hash_result"
    requires_confirmation: false
    dependencies:
      - echo
    system_prompt: "Calculate hash"

  - step_id: "validate"
    name: "Validate Data"
    description: "Validate schema"
    output_key: "validation_result"
    requires_confirmation: true
    dependencies:
      - echo
    system_prompt: "Validate data"

  - step_id: "summary"
    name: "Generate Report"
    description: "Generate final report"
    output_key: "final_report"
    requires_confirmation: false
    dependencies:
      - echo
      - hash
      - validate
    system_prompt: "Generate report"
EOF

# Create test edit flow scenario
cat > scenarios/test-edit-flow.yaml << 'EOF'
# 编辑流程测试场景

schema_version: "1.0"
scenario_id: "test-edit-flow"
name: "编辑流程测试"
description: "Test edit and diff flow"
category: "test"
version: "1.0"

trigger_patterns:
  - type: keyword
    keywords:
      - "测试编辑流程"
      - "edit flow test"
    priority: 1

steps:
  - step_id: "generate"
    name: "Generate Initial Data"
    description: "Generate initial data"
    output_key: "initial_data"
    requires_confirmation: true
    system_prompt: "Generate initial data"

  - step_id: "diff"
    name: "Compare Changes"
    description: "Compare differences"
    output_key: "diff_result"
    requires_confirmation: false
    dependencies:
      - generate
    system_prompt: "Compare changes"

  - step_id: "finalize"
    name: "Finalize"
    description: "Generate final version"
    output_key: "final_version"
    requires_confirmation: false
    dependencies:
      - generate
      - diff
    system_prompt: "Finalize"
EOF

echo "Test scenarios created successfully"

# Create test data directory
mkdir -p tests/data

# Create mock API responses
cat > tests/data/mock_tasks.json << 'EOF'
{
  "tasks": [
    {
      "task_id": "task-001",
      "scenario_id": "test-demo-flow",
      "status": "running",
      "total_steps": 4,
      "completed_steps": 2
    },
    {
      "task_id": "task-002",
      "scenario_id": "test-edit-flow",
      "status": "completed",
      "total_steps": 3,
      "completed_steps": 3
    }
  ],
  "total": 2
}
EOF

cat > tests/data/mock_scenarios.json << 'EOF'
{
  "scenarios": [
    {
      "scenario_id": "test-demo-flow",
      "name": "Demo 技能流程测试",
      "description": "Test demo skills flow",
      "category": "test",
      "steps": 4
    },
    {
      "scenario_id": "test-edit-flow",
      "name": "编辑流程测试",
      "description": "Test edit flow",
      "category": "test",
      "steps": 3
    }
  ],
  "total": 2
}
EOF

echo "Test data created successfully"

# Setup complete
echo "═══════════════════════════════════════════════════════════════"
echo "                    Setup Complete                              "
echo "═══════════════════════════════════════════════════════════════"