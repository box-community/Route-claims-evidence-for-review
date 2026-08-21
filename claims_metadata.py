import os

from box_sdk_gen import (
    BoxAPIError,
    BoxClient,
    CreateFileMetadataByIdScope,
    UpdateFileMetadataByIdRequestBody,
    UpdateFileMetadataByIdRequestBodyOpField,
    UpdateFileMetadataByIdScope,
)
from dotenv import load_dotenv

load_dotenv()

HTTP_CONFLICT = 409


def tag_evidence(client: BoxClient, file_ids: list[str], claim_id: str) -> None:
    """Attach claim context to each evidence file so the workflow can read it."""
    template_key = os.getenv("BOX_CLAIMS_TEMPLATE_KEY")
    values = {"claimId": claim_id, "reviewStatus": "in_review"}

    for file_id in file_ids:
        try:
            client.file_metadata.create_file_metadata_by_id(
                file_id=file_id,
                scope=CreateFileMetadataByIdScope.ENTERPRISE,
                template_key=template_key,
                request_body=values,
            )
        except BoxAPIError as error:
            if error.response_info.status_code != HTTP_CONFLICT:
                raise
            _replace_metadata(client, file_id, template_key, values)


def _replace_metadata(
    client: BoxClient, file_id: str, template_key: str, values: dict[str, str]
) -> None:
    """Overwrite an existing instance, for evidence resubmitted on the same claim."""
    client.file_metadata.update_file_metadata_by_id(
        file_id=file_id,
        scope=UpdateFileMetadataByIdScope.ENTERPRISE,
        template_key=template_key,
        request_body=[
            UpdateFileMetadataByIdRequestBody(
                op=UpdateFileMetadataByIdRequestBodyOpField.REPLACE,
                path=f"/{key}",
                value=value,
            )
            for key, value in values.items()
        ],
    )
