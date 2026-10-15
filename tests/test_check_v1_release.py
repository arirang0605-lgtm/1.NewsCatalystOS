"""Release tool only surfaces missing validation; it never creates tags."""
import json

from scripts import check_v1_release as cli


def test_release_report_lists_missing_required_real_validation(capsys):
    assert cli.main(["--completed","1_1,1_2"])==4
    report=json.loads(capsys.readouterr().out)
    assert report["done"]==2
    assert report["total"]==36
    assert "6_6" in report["missing_task_ids"]
    assert "FIVE_TRADING_SESSIONS_OBSERVATION_PENDING" in report["follow_ups"]
    assert "REAL_AI_PROVIDER_CALLS_NOT_VERIFIED" in report["release_blockers"]
    assert report["v1_git_tag_authorized"] is False


def test_invalid_completion_input_never_tags_or_crashes(capsys):
    assert cli.main(["--completed","7_1"])==4
    report=json.loads(capsys.readouterr().out)
    assert report["status"]=="DATA_UNAVAILABLE"
    assert report["v1_git_tag_authorized"] is False
