import os
import boto3
import tempfile
from pathlib import Path
from flask import Blueprint, request, jsonify

upload_blueprint = Blueprint("upload", __name__)
s3 = boto3.client("s3")

def get_pipeline_list():
    configs = Path("dag_configs").glob("*.yaml")
    return sorted([p.stem for p in configs])

@upload_blueprint.route("/upload-pipeline", methods=["POST"])
def handle_upload():
    form_data = request.form
    user_id = form_data.get("user_id")
    text = form_data.get("text", "").strip()

    pipeline_list = get_pipeline_list()
    numbered_list = "\n".join([f"{i+1}. {p}" for i, p in enumerate(pipeline_list)])

    if not text:
        return jsonify({
            "response_type": "ephemeral",
            "text": (
                "👋 Are you creating a *new pipeline* or uploading to an *existing one*?\n"
                "Type `new` or `existing` to continue."
            )
        })

    if text.lower() == "new":
        return jsonify({
            "response_type": "ephemeral",
            "text": (
                "🆕 *Creating a new pipeline!*\n"
                "Please reply with the name of your new pipeline (e.g., `orders_2024`) and attach a CSV file."
            )
        })

    if text.lower() == "existing":
        return jsonify({
            "response_type": "ephemeral",
            "text": (
                f"📂 Here are existing pipelines:\n{numbered_list}\n\n"
                "Please reply with the number of the pipeline you want to use and upload your CSV file."
            )
        })

    if text.isdigit() and 1 <= int(text) <= len(pipeline_list):
        pipeline = pipeline_list[int(text) - 1]
    else:
        pipeline = text

    file = request.files.get("file")
    if not file:
        return jsonify({"text": "📎 Please attach a CSV file to upload."}), 400

    filename = file.filename
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        file.save(temp.name)

    bucket = os.environ.get("S3_BUCKET", "chewy-ingest")
    key = f"{pipeline}/{filename}"
    s3.upload_file(temp.name, bucket, key)

    return jsonify({
        "response_type": "in_channel",
        "text": f"✅ File uploaded to `s3://{bucket}/{key}` for pipeline *{pipeline}*."
    })
