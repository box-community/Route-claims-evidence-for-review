from dataclasses import dataclass

from box_sdk_gen import BoxClient
from box_sdk_gen.networking.fetch_options import FetchOptions, ResponseFormat

BOX_API_BASE = "https://api.box.com/2.0"
AUTOMATE_HEADERS = {"box-version": "2026.0"}

MAX_FILES_PER_RUN = 20


@dataclass(frozen=True)
class WorkflowAction:
    """A published Automate workflow that can be started through the API."""

    workflow_id: str
    action_id: str
    name: str


def list_workflow_actions(client: BoxClient, folder_id: str) -> list[WorkflowAction]:
    response = client.make_request(
        FetchOptions(
            url=f"{BOX_API_BASE}/automate_workflows",
            method="GET",
            params={"folder_id": folder_id},
            headers=AUTOMATE_HEADERS,
            response_format=ResponseFormat.JSON,
        )
    )

    return [
        WorkflowAction(
            workflow_id=entry["workflow"]["id"],
            action_id=entry["id"],
            name=entry["workflow"].get("name", ""),
        )
        for entry in response.data.get("entries") or []
    ]


def find_workflow_action(
    client: BoxClient, folder_id: str, workflow_name: str
) -> WorkflowAction:
    actions = list_workflow_actions(client, folder_id)

    if not actions:
        raise LookupError(
            f"No Automate workflow actions on folder {folder_id}. Confirm the "
            "workflow is published and its Manual Start trigger uses this folder."
        )

    for action in actions:
        if action.name == workflow_name:
            return action

    available = ", ".join(sorted(action.name for action in actions))
    raise LookupError(
        f"Workflow {workflow_name!r} not found on folder {folder_id}. "
        f"Available workflows: {available}."
    )


def start_workflow(
    client: BoxClient, action: WorkflowAction, file_ids: list[str]
) -> None:
    client.make_request(
        FetchOptions(
            url=f"{BOX_API_BASE}/automate_workflows/{action.workflow_id}/start",
            method="POST",
            headers=AUTOMATE_HEADERS,
            data={"workflow_action_id": action.action_id, "file_ids": file_ids},
            response_format=ResponseFormat.JSON,
        )
    )
