"""Tests for the intent classifier."""

from jarvis.orchestrator.intent import IntentType, classify


class TestQueryIntents:
    def test_check_my_projects(self) -> None:
        result = classify("check my projects")
        assert result.intent == IntentType.QUERY

    def test_whats_broken(self) -> None:
        result = classify("what's broken?")
        assert result.intent == IntentType.QUERY

    def test_status(self) -> None:
        result = classify("status")
        assert result.intent == IntentType.QUERY

    def test_open_issues(self) -> None:
        result = classify("open issues")
        assert result.intent == IntentType.QUERY

    def test_ci_status(self) -> None:
        result = classify("ci status")
        assert result.intent == IntentType.QUERY

    def test_list_tasks(self) -> None:
        result = classify("list all tasks")
        assert result.intent == IntentType.QUERY

    def test_show_projects(self) -> None:
        result = classify("show me projects")
        assert result.intent == IntentType.QUERY

    def test_how_many(self) -> None:
        result = classify("how many tasks are running?")
        assert result.intent == IntentType.QUERY

    def test_whats_the_status(self) -> None:
        result = classify("what's the progress on this?")
        assert result.intent == IntentType.QUERY


class TestWorkflowIntents:
    def test_fix_issue_72(self) -> None:
        result = classify("fix issue #72")
        assert result.intent == IntentType.WORKFLOW
        assert result.issue_number == 72

    def test_handle_hash_5(self) -> None:
        result = classify("handle #5")
        assert result.intent == IntentType.WORKFLOW
        assert result.issue_number == 5

    def test_resolve_hash_100(self) -> None:
        result = classify("resolve #100")
        assert result.intent == IntentType.WORKFLOW
        assert result.issue_number == 100

    def test_take_care_of_issue_42(self) -> None:
        result = classify("take care of issue #42")
        assert result.intent == IntentType.WORKFLOW
        assert result.issue_number == 42

    def test_work_on_issue(self) -> None:
        result = classify("work on #33")
        assert result.intent == IntentType.WORKFLOW
        assert result.issue_number == 33

    def test_implement_issue(self) -> None:
        result = classify("implement #15")
        assert result.intent == IntentType.WORKFLOW
        assert result.issue_number == 15

    def test_close_issue(self) -> None:
        result = classify("close #8")
        assert result.intent == IntentType.WORKFLOW
        assert result.issue_number == 8

    def test_address_issue(self) -> None:
        result = classify("address issue #99")
        assert result.intent == IntentType.WORKFLOW
        assert result.issue_number == 99

    def test_bare_issue_number_no_workflow_keyword(self) -> None:
        """Issue number without workflow keyword → QUERY (no action verb)."""
        result = classify("issue #42")
        assert result.intent == IntentType.QUERY
        assert result.issue_number == 42


class TestActionIntents:
    def test_test_project(self) -> None:
        result = classify("test MinaarTech")
        assert result.intent == IntentType.ACTION

    def test_fix_login_page(self) -> None:
        result = classify("fix the login page")
        assert result.intent == IntentType.ACTION

    def test_deploy_staging(self) -> None:
        result = classify("deploy staging")
        assert result.intent == IntentType.ACTION

    def test_generic_message(self) -> None:
        result = classify("run the migration scripts")
        assert result.intent == IntentType.ACTION


class TestIssueExtraction:
    def test_hash_number(self) -> None:
        result = classify("fix #72")
        assert result.issue_number == 72

    def test_issue_word_number(self) -> None:
        result = classify("look at issue 99")
        assert result.issue_number == 99

    def test_bug_hash(self) -> None:
        result = classify("fix bug #5")
        assert result.issue_number == 5

    def test_no_issue(self) -> None:
        result = classify("deploy staging")
        assert result.issue_number is None


class TestProjectHintExtraction:
    def test_test_project_name(self) -> None:
        result = classify("test MinaarTech")
        assert result.project_hint == "MinaarTech"

    def test_run_project(self) -> None:
        result = classify("run MyProject")
        assert result.project_hint == "MyProject"

    def test_check_project(self) -> None:
        result = classify("check SomeApp")
        assert result.project_hint == "SomeApp"

    def test_deploy_project(self) -> None:
        result = classify("deploy StagingServer")
        assert result.project_hint == "StagingServer"

    def test_no_hint(self) -> None:
        result = classify("what's the weather?")
        assert result.project_hint is None


class TestEdgeCases:
    def test_empty_message(self) -> None:
        result = classify("")
        assert result.intent == IntentType.QUERY
        assert result.confidence == "low"

    def test_whitespace_only(self) -> None:
        result = classify("   ")
        assert result.intent == IntentType.QUERY
        assert result.confidence == "low"

    def test_case_insensitive_query(self) -> None:
        result = classify("STATUS")
        assert result.intent == IntentType.QUERY

    def test_case_insensitive_workflow(self) -> None:
        result = classify("FIX #42")
        assert result.intent == IntentType.WORKFLOW

    def test_no_action_keyword_fallback_query(self) -> None:
        """Messages without action keywords fall through to QUERY."""
        result = classify("hello world")
        assert result.intent == IntentType.QUERY

    def test_conversational_message_is_query(self) -> None:
        result = classify("what's the weather today?")
        assert result.intent == IntentType.QUERY

    def test_action_keyword_triggers_action(self) -> None:
        result = classify("add dark mode to the settings page")
        assert result.intent == IntentType.ACTION
