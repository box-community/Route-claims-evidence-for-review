"""Live end-to-end test against a real Box enterprise.

Uploads a throwaway evidence file to the Claims Review folder, posts it to
/reviews, and checks the published Automate workflow was found and started and
the file was tagged with the claim. Then re-tags the file to check existing
metadata is replaced, and checks /reviews rejects invalid requests.

Each run starts the real workflow, so the workflow's reviewer receives a task.
The file is deleted at the end. Reads the same variables as .env.example from
the environment or a local .env.
"""

import io
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from box_sdk_gen import (  # noqa: E402
    GetFileMetadataByIdScope,
    UploadFileAttributes,
    UploadFileAttributesParentField,
)

from app import app  # noqa: E402
from automate import MAX_FILES_PER_RUN  # noqa: E402
from box_client import get_box_client  # noqa: E402
from claims_metadata import tag_evidence  # noqa: E402

REQUIRED_ENV = [
    "BOX_CLIENT_ID",
    "BOX_CLIENT_SECRET",
    "BOX_USER_ID",
    "BOX_CLAIMS_FOLDER_ID",
    "BOX_CLAIMS_TEMPLATE_KEY",
    "BOX_CLAIMS_WORKFLOW_NAME",
]


def read_claim(client, file_id: str) -> dict:
    metadata = client.file_metadata.get_file_metadata_by_id(
        file_id,
        GetFileMetadataByIdScope.ENTERPRISE,
        os.getenv("BOX_CLAIMS_TEMPLATE_KEY"),
    )
    return metadata.extra_data or {}


def check_validation(test_client) -> None:
    invalid = [
        {"file_ids": ["1"]},
        {"claim_id": "CLM-1", "file_ids": []},
        {"claim_id": "CLM-1", "file_ids": ["1"] * (MAX_FILES_PER_RUN + 1)},
    ]
    for payload in invalid:
        response = test_client.post("/reviews", json=payload)
        assert response.status_code == 400, f"{payload} returned {response.status_code}"


def check_review(test_client, client, file_id: str, claim_id: str) -> None:
    response = test_client.post("/reviews", json={"claim_id": claim_id, "file_ids": [file_id]})
    body = response.get_json()
    assert response.status_code == 202, f"/reviews returned {response.status_code}: {body}"
    assert body["status"] == "review_started", body
    assert body["workflow"] == os.getenv("BOX_CLAIMS_WORKFLOW_NAME"), body
    print(f"Started '{body['workflow']}' for {claim_id}")

    claim = read_claim(client, file_id)
    assert claim.get("claimId") == claim_id, claim
    assert claim.get("reviewStatus") == "in_review", claim


def check_retag(client, file_id: str, claim_id: str) -> None:
    tag_evidence(client, [file_id], claim_id)
    assert read_claim(client, file_id).get("claimId") == claim_id, "Metadata was not replaced"
    print("Re-tagging replaced the existing claim metadata")


def main() -> None:
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if missing:
        sys.exit(f"Missing environment variables: {', '.join(missing)}")

    client = get_box_client()
    test_client = app.test_client()
    run_id = os.getenv("GITHUB_RUN_ID") or f"local-{int(time.time())}"

    check_validation(test_client)

    uploaded = client.uploads.upload_file(
        UploadFileAttributes(
            name=f"ci-run-{run_id}-evidence.txt",
            parent=UploadFileAttributesParentField(id=os.getenv("BOX_CLAIMS_FOLDER_ID")),
        ),
        io.BytesIO(b"Test evidence uploaded by the live test. Safe to delete.\n"),
    )
    file_id = uploaded.entries[0].id
    print(f"Uploaded evidence file {file_id}")

    try:
        check_review(test_client, client, file_id, f"CI-{run_id}")
        check_retag(client, file_id, f"CI-{run_id}-resubmitted")
        print("Live test passed")
    finally:
        client.files.delete_file_by_id(file_id)
        print(f"Deleted evidence file {file_id}")


if __name__ == "__main__":
    main()
