"""Workflow and activity constants.

Translated from go_companion/internal/workflow/constants.go
"""

from datetime import timedelta

from temporalio.common import RetryPolicy

# --- Tool Names ---
RETURN_TO_PARENT_TOOL_NAME = "return_to_parent_agent"

# --- Limits ---
MAX_DELEGATION_DEPTH = 5
MAX_AUTO_APPROVE_DEPTH = 100

# --- Error Types ---
ERR_TYPE_STALE_TOOL_RESULT = "STALE_TOOL_RESULT"

# --- Activity Names ---
ACTIVITY_PROCESS_USER_MESSAGE = "ProcessUserMessage"
ACTIVITY_PROCESS_CLIENT_TOOL_RESULT = "ProcessClientToolResult"
ACTIVITY_PROCESS_END_CONVERSATION = "ProcessEndConversation"
ACTIVITY_REJECT_PENDING_TOOL = "RejectPendingTool"
ACTIVITY_EXECUTE_SERVER_TOOL = "ExecuteServerTool"
ACTIVITY_FORWARD_TO_CHILD = "ForwardToChildWorkflow"
ACTIVITY_PERSIST_MESSAGES = "PersistMessages"

# --- Update Names ---
UPDATE_PROCESS_USER_MESSAGE = "ProcessUserMessage"
UPDATE_PROCESS_SERVER_TOOL_APPROVAL = "ProcessServerToolApproval"
UPDATE_PROCESS_CLIENT_TOOL_RESULT = "ProcessClientToolResult"
UPDATE_PROCESS_END_CONVERSATION = "ProcessEndConversation"
UPDATE_PROCESS_AGENT_TOOL = "ProcessAgentTool"

# --- Session Status ---
SESSION_STATUS_RUNNING = "running"
SESSION_STATUS_COMPLETED = "completed"
SESSION_STATUS_FAILED = "failed"
SESSION_STATUS_TERMINATED = "terminated"

# --- Retry Policy ---
# Aligned to timeout constraints:
# - Single attempt must finish within 2m30s
# - 3 attempts (original + 2 retries)
# - Fast initial retry for network blips
ACTIVITY_START_TO_CLOSE_TIMEOUT = timedelta(minutes=2, seconds=30)
ACTIVITY_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(milliseconds=500),
    backoff_coefficient=1.5,
    maximum_interval=timedelta(seconds=5),
    maximum_attempts=3,
)
