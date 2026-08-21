import os

from box_sdk_gen import BoxAPIError
from dotenv import load_dotenv
from flask import Flask, jsonify, request

from automate import MAX_FILES_PER_RUN, find_workflow_action, start_workflow
from box_client import get_box_client
from claims_metadata import tag_evidence

load_dotenv()
app = Flask(__name__)


@app.get("/")
def index():
    return jsonify(
        {
            "service": "Route claims evidence for review",
            "endpoints": {
                "POST /reviews": (
                    "Tag selected evidence files with a claim ID and start "
                    "the Box Automate review workflow"
                ),
                "GET /health": "Liveness check",
            },
            "local_test": (
                "curl -X POST http://127.0.0.1:5000/reviews "
                '-H "Content-Type: application/json" '
                "-d @sample_review.json"
            ),
        }
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.post("/reviews")
def start_review():
    payload = request.get_json(silent=True) or {}
    claim_id = payload.get("claim_id")
    file_ids = payload.get("file_ids") or []

    if not claim_id:
        return jsonify({"error": "claim_id is required"}), 400
    if not file_ids:
        return jsonify({"error": "file_ids must list at least one file"}), 400
    if len(file_ids) > MAX_FILES_PER_RUN:
        return jsonify(
            {"error": f"Box Automate accepts at most {MAX_FILES_PER_RUN} files per run"}
        ), 400

    client = get_box_client()
    folder_id = os.getenv("BOX_CLAIMS_FOLDER_ID")
    workflow_name = os.getenv("BOX_CLAIMS_WORKFLOW_NAME")

    try:
        tag_evidence(client, file_ids, claim_id)
        action = find_workflow_action(client, folder_id, workflow_name)
        start_workflow(client, action, file_ids)
    except LookupError as error:
        return jsonify({"error": str(error)}), 404
    except BoxAPIError as error:
        return jsonify({"error": error.message}), error.response_info.status_code

    return jsonify(
        {
            "status": "review_started",
            "claim_id": claim_id,
            "workflow": action.name,
            "file_ids": file_ids,
        }
    ), 202


if __name__ == "__main__":
    app.run(port=5000)
