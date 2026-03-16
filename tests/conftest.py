"""Global test fixtures."""

import pytest


@pytest.fixture
def sample_agent_config():
    from tests.fixtures.agents import SAMPLE_AGENT_CONFIG
    return dict(SAMPLE_AGENT_CONFIG)


@pytest.fixture
def sample_token_usage():
    from tests.fixtures.messages import make_token_usage
    return make_token_usage()
