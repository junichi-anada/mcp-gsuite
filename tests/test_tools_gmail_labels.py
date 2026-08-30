import json
from unittest.mock import MagicMock, patch

import pytest

from mcp_gsuite import tools_gmail


USER_ID = "user@example.com"


class TestListLabelsToolHandler:
    def test_lists_labels_via_gmail_service(self):
        handler = tools_gmail.ListLabelsToolHandler()
        fake_labels = [
            {"id": "Label_1", "name": "clients/re-buysell", "type": "user"},
            {"id": "INBOX", "name": "INBOX", "type": "system"},
        ]

        with patch.object(tools_gmail.gmail, "GmailService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.list_labels.return_value = fake_labels
            mock_service_cls.return_value = mock_service

            result = handler.run_tool({tools_gmail.toolhandler.USER_ID_ARG: USER_ID})

        mock_service_cls.assert_called_once_with(user_id=USER_ID)
        mock_service.list_labels.assert_called_once_with()
        assert json.loads(result[0].text) == fake_labels

    def test_missing_user_id_raises(self):
        handler = tools_gmail.ListLabelsToolHandler()
        with pytest.raises(RuntimeError):
            handler.run_tool({})


class TestModifyLabelsToolHandler:
    def test_dry_run_defaults_true_and_does_not_call_gmail_api(self):
        handler = tools_gmail.ModifyLabelsToolHandler()

        with patch.object(tools_gmail.gmail, "GmailService") as mock_service_cls:
            result = handler.run_tool({
                tools_gmail.toolhandler.USER_ID_ARG: USER_ID,
                "message_id": "msg123",
                "add_label_ids": ["Label_1"],
                "remove_label_ids": ["Label_2"],
            })

        mock_service_cls.assert_not_called()
        payload = json.loads(result[0].text)
        assert payload["dry_run"] is True
        assert payload["message_id"] == "msg123"
        assert payload["would_add"] == ["Label_1"]
        assert payload["would_remove"] == ["Label_2"]

    def test_dry_run_explicit_false_calls_gmail_api(self):
        handler = tools_gmail.ModifyLabelsToolHandler()
        fake_result = {"id": "msg123", "labelIds": ["Label_1", "INBOX"]}

        with patch.object(tools_gmail.gmail, "GmailService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.modify_message_labels.return_value = fake_result
            mock_service_cls.return_value = mock_service

            result = handler.run_tool({
                tools_gmail.toolhandler.USER_ID_ARG: USER_ID,
                "message_id": "msg123",
                "add_label_ids": ["Label_1"],
                "dry_run": False,
            })

        mock_service.modify_message_labels.assert_called_once_with(
            message_id="msg123",
            add_label_ids=["Label_1"],
            remove_label_ids=None,
        )
        assert json.loads(result[0].text) == fake_result

    def test_unread_in_add_labels_is_rejected(self):
        handler = tools_gmail.ModifyLabelsToolHandler()

        with patch.object(tools_gmail.gmail, "GmailService") as mock_service_cls:
            with pytest.raises(RuntimeError, match="protected"):
                handler.run_tool({
                    tools_gmail.toolhandler.USER_ID_ARG: USER_ID,
                    "message_id": "msg123",
                    "add_label_ids": ["UNREAD"],
                    "dry_run": False,
                })

        mock_service_cls.assert_not_called()

    def test_unread_in_remove_labels_is_rejected(self):
        handler = tools_gmail.ModifyLabelsToolHandler()

        with patch.object(tools_gmail.gmail, "GmailService") as mock_service_cls:
            with pytest.raises(RuntimeError, match="protected"):
                handler.run_tool({
                    tools_gmail.toolhandler.USER_ID_ARG: USER_ID,
                    "message_id": "msg123",
                    "remove_label_ids": ["UNREAD"],
                    "dry_run": False,
                })

        mock_service_cls.assert_not_called()

    def test_no_labels_specified_raises(self):
        handler = tools_gmail.ModifyLabelsToolHandler()
        with pytest.raises(RuntimeError, match="add_label_ids or remove_label_ids"):
            handler.run_tool({
                tools_gmail.toolhandler.USER_ID_ARG: USER_ID,
                "message_id": "msg123",
            })

    def test_missing_message_id_raises(self):
        handler = tools_gmail.ModifyLabelsToolHandler()
        with pytest.raises(RuntimeError, match="message_id"):
            handler.run_tool({
                tools_gmail.toolhandler.USER_ID_ARG: USER_ID,
                "add_label_ids": ["Label_1"],
            })

    def test_missing_user_id_raises(self):
        handler = tools_gmail.ModifyLabelsToolHandler()
        with pytest.raises(RuntimeError, match=tools_gmail.toolhandler.USER_ID_ARG):
            handler.run_tool({
                "message_id": "msg123",
                "add_label_ids": ["Label_1"],
            })


class TestGmailServiceLabelMethods:
    def _make_service(self):
        service = tools_gmail.gmail.GmailService.__new__(tools_gmail.gmail.GmailService)
        service.service = MagicMock()
        return service

    def test_list_labels_returns_labels(self):
        service = self._make_service()
        fake_labels = [{"id": "INBOX", "name": "INBOX", "type": "system"}]
        service.service.users.return_value.labels.return_value.list.return_value.execute.return_value = {
            "labels": fake_labels
        }

        result = service.list_labels()

        assert result == fake_labels

    def test_list_labels_returns_empty_on_error(self):
        service = self._make_service()
        service.service.users.side_effect = Exception("boom")

        result = service.list_labels()

        assert result == []

    def test_modify_message_labels_builds_correct_body(self):
        service = self._make_service()
        fake_result = {"id": "msg123", "labelIds": ["Label_1"]}
        modify_mock = service.service.users.return_value.messages.return_value.modify
        modify_mock.return_value.execute.return_value = fake_result

        result = service.modify_message_labels(
            message_id="msg123",
            add_label_ids=["Label_1"],
            remove_label_ids=["Label_2"],
        )

        modify_mock.assert_called_once_with(
            userId="me",
            id="msg123",
            body={"addLabelIds": ["Label_1"], "removeLabelIds": ["Label_2"]},
        )
        assert result == fake_result

    def test_modify_message_labels_returns_none_on_error(self):
        service = self._make_service()
        service.service.users.side_effect = Exception("boom")

        result = service.modify_message_labels(message_id="msg123", add_label_ids=["Label_1"])

        assert result is None
